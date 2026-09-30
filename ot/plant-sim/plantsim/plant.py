"""Plant = three hydraulic units + their soft-PLCs + fault injection + simulated clock.

Wall-clock 1 s == TIME_SCALE simulated seconds (sub-stepped 1 s at a time so the
thermal model stays stable).
"""
from dataclasses import dataclass, field
import threading

from hydcommon.topics import ASSETS
from hydcommon.timeutil import now, now_iso
from . import thermal, plc


@dataclass
class Fault:
    kind: str                 # cooler_degradation | restore
    target_health: float
    rate_per_s: float         # health change per simulated second (signed)


@dataclass
class Unit:
    asset: str
    state: thermal.UnitState = field(default_factory=thermal.UnitState)
    ctrl: plc.PlcState = field(default_factory=plc.PlcState)
    fault: Fault | None = None
    dirty_status: bool = True


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
        f = u.fault
        if not f:
            return
        h = u.state.cooler_health
        if abs(h - f.target_health) <= abs(f.rate_per_s * dt):
            u.state.cooler_health = f.target_health
            u.fault = None
        else:
            u.state.cooler_health = h + f.rate_per_s * dt

    # ---- fault injection API ----
    def inject(self, asset: str, kind: str, target_health: float = thermal.DEGRADED_HEALTH, ramp_sim_s: float = 300.0) -> dict:
        with self.lock:
            u = self.units[asset]
            if kind == "cooler_degradation":
                target = float(target_health)
            elif kind == "restore":
                target = 1.0
            else:
                raise ValueError(f"unknown fault kind {kind}")
            delta = target - u.state.cooler_health
            rate = delta / max(1.0, float(ramp_sim_s))
            u.fault = Fault(kind, target, rate)
            return {"asset": asset, "kind": kind, "target_health": target, "ramp_sim_s": ramp_sim_s}

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
        return st

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "time_scale": self.time_scale,
                "sim_t": round(self.sim_t, 1),
                "units": {a: {"tags": self.tags(a), "status": self.status(a),
                              "fault": (u.fault.kind if u.fault else None)}
                          for a, u in self.units.items()},
            }
