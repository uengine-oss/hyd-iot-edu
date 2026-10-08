"""Plant = three hydraulic units + their soft-PLCs + fault injection + simulated clock.

Wall-clock 1 s == TIME_SCALE simulated seconds (sub-stepped 1 s at a time so the
thermal model stays stable).
"""
from dataclasses import dataclass, field
import threading

from hydcommon.topics import ASSETS
from hydcommon.timeutil import now, now_iso
from . import thermal, plc


# fault kind -> (UnitState attribute it ramps, default target). Each kind is one ontology disturbance variable:
# cooler_degradation = sv:fouling (cooler_health), pump_leakage = sv:leak, fan_vibration = sv:bearing-wear.
FAULT_KINDS = {"cooler_degradation": ("cooler_health", thermal.DEGRADED_HEALTH),
               "pump_leakage": ("leak", thermal.DEGRADED_LEAK),
               "fan_vibration": ("bearing_wear", thermal.DEGRADED_BEARING)}
HEALTHY = {"cooler_health": 1.0, "leak": 0.0, "bearing_wear": 0.0}
# Named fault strengths. "high" is every kind's default (the lecture scenes that end in a PLC trip keep using it);
# "moderate" is defined for the cooler only: TS1 settles at ~62.5 C, so the alarm stays up without the 65 C trip
# (the window a coding-agent worker needs at TIME_SCALE 20, A146). The trip itself is untouched (plc.check_interlock).
SEVERITY = {"cooler_degradation": {"high": thermal.DEGRADED_HEALTH, "moderate": thermal.MODERATE_HEALTH},
            "pump_leakage": {"high": thermal.DEGRADED_LEAK},
            "fan_vibration": {"high": thermal.DEGRADED_BEARING}}
# Default ramp per kind (simulated seconds) when the caller gives none. Bearing wear ramps over 900 s: FAN_VIBRATION needs
# VS1 > 1.2 *and still rising* for its 60 s hold, and over 300 s VS1 rose above 1.2 for only ~57 s (noise-free) — at
# TIME_SCALE 20 (one sample = 20 sim-s) the raise then hung on sample phase and noise (A160: live miss after 151 s).
# 900 s gives ~169 s of rise above the line (> hold + three samples). The detection rule (pattern:fan-vibration) is unchanged.
DEFAULT_RAMP_S = {"cooler_degradation": 300.0, "pump_leakage": 300.0, "fan_vibration": 900.0, "restore": 300.0}


@dataclass
class Fault:
    kind: str                 # cooler_degradation | pump_leakage | fan_vibration | restore
    attr: str                 # UnitState attribute being ramped
    target: float
    rate_per_s: float         # change per simulated second (signed)


@dataclass
class Unit:
    asset: str
    state: thermal.UnitState = field(default_factory=thermal.UnitState)
    ctrl: plc.PlcState = field(default_factory=plc.PlcState)
    faults: dict[str, Fault] = field(default_factory=dict)   # attr -> ramp in progress
    dirty_status: bool = True

    @property
    def fault(self) -> Fault | None:
        """The fault being injected right now (the first ramp still running), kept for the status/snapshot contract."""
        return next(iter(self.faults.values()), None)


class Plant:
    def __init__(self, time_scale: float = 20.0, assets=ASSETS):
        self.time_scale = time_scale
        self.units: dict[str, Unit] = {a: Unit(asset=a) for a in assets}
        for i, u in enumerate(self.units.values()):
            u.state.rng.seed(i + 1)
        self.lock = threading.RLock()
        self.sim_t = 0.0

    # ---- simulation ----
    def tick(self, wall_dt: float) -> None:
        with self.lock:
            steps = max(1, int(round(wall_dt * self.time_scale)))
            for u in self.units.values():
                for _ in range(steps):
                    self._apply_fault(u, 1.0)
                    thermal.step(u.state, 1.0, running=(u.ctrl.state == "RUN"))
                    before = u.ctrl.state
                    plc.check_interlock(u.ctrl, u.state)
                    if before != u.ctrl.state:
                        u.dirty_status = True
            self.sim_t += steps

    @staticmethod
    def _apply_fault(u: Unit, dt: float) -> None:
        for attr, f in list(u.faults.items()):
            cur = getattr(u.state, attr)
            if abs(cur - f.target) <= abs(f.rate_per_s * dt):
                setattr(u.state, attr, f.target)
                del u.faults[attr]
                u.dirty_status = True  # publish the transition out of a non-stationary model domain
            else:
                setattr(u.state, attr, cur + f.rate_per_s * dt)

    # ---- fault injection API ----
    def inject(self, asset: str, kind: str, target: float | None = None, ramp_sim_s: float | None = None,
               severity: str | None = None) -> dict:
        """Ramp one disturbance variable towards `target` over `ramp_sim_s` simulated seconds (a slow degradation, not a
        step). `restore` ramps every disturbance back to its healthy value. Without `target`, `severity` picks a named
        strength from SEVERITY ("high" = the kind's default). Without `ramp_sim_s`, the kind's DEFAULT_RAMP_S."""
        if ramp_sim_s is None:
            if kind not in DEFAULT_RAMP_S:
                raise ValueError(f"unknown fault kind {kind}")
            ramp_sim_s = DEFAULT_RAMP_S[kind]
        with self.lock:
            u = self.units[asset]
            if kind == "restore":
                plan = {attr: healthy for attr, healthy in HEALTHY.items() if getattr(u.state, attr) != healthy or attr in u.faults}
            elif kind in FAULT_KINDS:
                attr, default = FAULT_KINDS[kind]
                if target is None and severity is not None:
                    if severity not in SEVERITY[kind]:
                        raise ValueError(f"unknown severity {severity} for {kind} (known: {sorted(SEVERITY[kind])})")
                    default = SEVERITY[kind][severity]
                plan = {attr: float(default if target is None else target)}
            else:
                raise ValueError(f"unknown fault kind {kind}")
            for attr, tgt in plan.items():
                rate = (tgt - getattr(u.state, attr)) / max(1.0, float(ramp_sim_s))
                u.faults[attr] = Fault(kind, attr, tgt, rate)
            if plan:
                u.dirty_status = True
            return {"asset": asset, "kind": kind, "targets": plan, "ramp_sim_s": ramp_sim_s,
                    "target_health": plan.get("cooler_health", u.state.cooler_health)}

    # ---- commands (called from MQTT thread) ----
    def command(self, asset: str, cmd: dict, source: str) -> plc.CmdResult:
        with self.lock:
            u = self.units[asset]
            r = plc.apply_command(u.ctrl, u.state, cmd, source=source, now=now())
            u.dirty_status = True
            return r

    def set_mode(self, asset: str, mode: str, requester: str) -> bool:
        with self.lock:
            u = self.units[asset]
            ok = plc.set_mode(u.ctrl, mode, requester)
            u.dirty_status = True
            return ok

    # ---- snapshots ----
    def tags(self, asset: str) -> dict[str, float]:
        s = self.units[asset].state
        return {
            "TS1": round(s.ts1, 2), "TS2": round(s.ts2, 2), "TS3": round(s.ts3, 2), "TS4": round(s.ts4, 2),
            "PS1": round(s.ps1, 2), "PS2": round(s.ps2, 2), "PS3": round(s.ps3, 3), "PS4": round(s.ps4, 3),
            "PS5": round(s.ps5, 3), "PS6": round(s.ps6, 3), "EPS1": round(s.eps1, 3),
            "FS1": round(s.fs1, 3), "FS2": round(s.fs2, 3), "VS1": round(s.vs1, 3),
            "CE": round(s.ce, 1), "CP": round(s.cp, 3), "SE": round(s.se, 1),
            "FanSpeedSP": s.fan_pct, "LoadSP": s.load_pct,
        }

    def status(self, asset: str) -> dict:
        u = self.units[asset]
        st = plc.status_payload(asset, u.ctrl, u.state, now_iso())
        st["sim_t"] = round(self.sim_t, 1)
        st["time_scale"] = self.time_scale
        st['disturbance_ramps'] = sorted(u.faults)
        return st

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "time_scale": self.time_scale,
                "sim_t": round(self.sim_t, 1),
                "units": {a: {"tags": self.tags(a), "status": self.status(a),
                              "fault": (u.fault.kind if u.fault else None),
                              "faults": [f.kind for f in u.faults.values()],
                              "disturbances": {"cooler_health": round(u.state.cooler_health, 3), "leak": round(u.state.leak, 3),
                                               "bearing_wear": round(u.state.bearing_wear, 3), "pump": u.state.pump}}
                          for a, u in self.units.items()},
            }
