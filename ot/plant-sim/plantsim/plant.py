"""Plant = three hydraulic units + their soft-PLCs + fault injection + simulated clock.

Wall-clock 1 s == TIME_SCALE simulated seconds (sub-stepped 1 s at a time so the
thermal model stays stable).

바깥 변화 기록(plant.status 의 outside): 승인한 길(명령 관문을 지난 HITL 명령 · 처리 엔진이 승인 뒤 내는 정비 복구) 밖에서 설비가 바뀔 때마다
설비별 번호(seq)가 하나 오르고 마지막 변화(무엇 · 누가 · 언제)가 남는다 — 결함 주입 · 결함 되돌림 · 설비 초기화 · 현장 패널 · 운전 화면의 수동
쓰기 · 운전 모드 변경. 가상 설비가 다시 켜지면 boot 가 바뀐다. 처리 엔진은 처리 건이 열린 뒤 이 기록이 바뀌었으면 그 뒤의 회복을 승인한 조치의
효과로도 자연 회복으로도 치지 않는다(procsvc machine.outside_change).
"""
from dataclasses import dataclass, field
import math
import secrets
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
# Physical domain of each disturbance variable (a fault target outside it, NaN or infinite is refused): cooler health 0..1
# (0 = no forced cooling), leakage fraction 0..0.5 (beyond half the flow the pump model has no meaning), bearing wear 0..1.
DOMAIN = {"cooler_health": (0.0, 1.0), "leak": (0.0, 0.5), "bearing_wear": (0.0, 1.0)}
MAX_RAMP_S = 86400.0
# C2: 정비 수행 모사의 복구 대상 → 외란 변수. 지식 지도(온톨로지)의 이름과 가상 설비의 외란 변수를 잇는 정본은 이 표 한 곳이다:
# 구성 요소(Component id comp:*)와 외란 상태 변수(StateVariable id sv:* — 위 FAULT_KINDS 주석의 대응과 같다). 처리 엔진의 정비 수행은 승인한
# 조치 방법이 지식에서 다루는 원인의 외란 변수 · 구성 요소 id 를 targets 로 보낸다. 이 표에 없는 id 는 가상 설비가 모형으로 갖지 않은 것이다.
COMPONENTS = {"cooler": "cooler_health", "comp:cooler": "cooler_health", "sv:fouling": "cooler_health",
              "pump": "leak", "pump-a": "leak", "comp:pump-a": "leak", "sv:leak": "leak",
              "fan": "bearing_wear", "comp:fan": "bearing_wear", "sv:bearing-wear": "bearing_wear"}
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
# 바깥 변화 기록의 사람 말(plant.status outside.what — 처리 건의 사유 문장이 그대로 싣는다)
FAULT_WORDS = {"cooler_degradation": "쿨러 열화", "pump_leakage": "펌프 누설", "fan_vibration": "팬 베어링 마모"}
SOURCE_WORDS = {"LOCAL": "현장 패널", "FUXA": "운전 화면(FUXA)"}


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
    # C3: who asked for the last fault injection/restore on this unit ({id, kind, by, user_id, roles, at}) — published in
    # plant.status so the process links the case this injection causes to the button press by id (no time-window guess)
    injection: dict | None = None
    # 마지막 바깥 변화(이 모듈 머리말) {seq, kind, what, by, at} — kind: boot · fault · restore · reset · manual · mode
    outside: dict = field(default_factory=dict)

    @property
    def fault(self) -> Fault | None:
        """The fault being injected right now (the first ramp still running), kept for the status/snapshot contract."""
        return next(iter(self.faults.values()), None)


def _outside(u: Unit, kind: str, what: str, by: str | None = None) -> None:
    """승인한 길 밖의 변화 하나를 그 설비의 바깥 변화 기록에 남긴다(번호 + 1)."""
    u.outside = {"seq": int(u.outside.get("seq", -1)) + 1, "kind": kind, "what": what, "by": by, "at": now_iso()}


class Plant:
    def __init__(self, time_scale: float, assets=ASSETS):
        self.time_scale = time_scale
        self.units: dict[str, Unit] = {a: Unit(asset=a) for a in assets}
        for i, u in enumerate(self.units.values()):
            u.state.rng.seed(i + 1)
            _outside(u, "boot", "가상 설비가 켜짐 — 결함 · 지령이 처음 값")
        self.boot = secrets.token_hex(4)          # 켜질 때마다 바뀐다 — 다시 켜진 설비의 번호(seq)는 0부터라 이것과 함께 견준다
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
                    plc.check_interlock(u.ctrl, u.state)
            self.sim_t += steps

    @staticmethod
    def _apply_fault(u: Unit, dt: float) -> None:
        for attr, f in list(u.faults.items()):
            cur = getattr(u.state, attr)
            if abs(cur - f.target) <= abs(f.rate_per_s * dt):
                setattr(u.state, attr, f.target)
                del u.faults[attr]
            else:
                setattr(u.state, attr, cur + f.rate_per_s * dt)

    # ---- fault injection API ----
    def inject(self, asset: str, kind: str, target: float | None = None, ramp_sim_s: float | None = None,
               severity: str | None = None, component: str | None = None, origin: dict | None = None,
               operating_point: bool = False, targets: list[str] | None = None, approved: dict | None = None) -> dict:
        """Ramp one disturbance variable towards `target` over `ramp_sim_s` simulated seconds (a slow degradation, not a
        step). `restore` ramps every disturbance back to its healthy value. Without `target`, `severity` picks a named
        strength from SEVERITY ("high" = the kind's default). Without `ramp_sim_s`, the kind's DEFAULT_RAMP_S.

        `operating_point` (restore only) also puts the fan and load set-points back to the normal operating point, at once
        (set-points are stepped, not ramped). A disturbance restore alone leaves the set-points an approved mitigation wrote
        (fan 100 %, load 80 %): with those, moderate cooler fouling settles under the 55 C alarm line, so the next cooler
        degradation would never raise an alert. The process's maintenance restore does not ask for it — only the lecture
        button that ends a scene does.

        `targets` (restore only) names what an approved maintenance action deals with, as knowledge-graph ids (COMPONENTS:
        comp:* · sv:*). Only those disturbances are restored: an empty list restores nothing, and ids this plant does not
        model come back in `not_modeled` (not an error — the knowledge may know causes the simulator has no variable for).

        `approved` (restore only) names the approved process step behind this restore {instance, step, approved_by} — the
        process's simulated field maintenance after a person's approval. It is the approved path, so it does not count as an
        outside change; every other injection or restore does (module docstring)."""
        if ramp_sim_s is None:
            if kind not in DEFAULT_RAMP_S:
                raise ValueError(f"unknown fault kind {kind}")
            ramp_sim_s = DEFAULT_RAMP_S[kind]
        if isinstance(ramp_sim_s, bool) or not isinstance(ramp_sim_s, (int, float)) or not 0 < ramp_sim_s <= MAX_RAMP_S:
            raise ValueError(f"ramp_sim_s must be a number in (0, {MAX_RAMP_S:g}] simulated seconds, got {ramp_sim_s!r}")
        if operating_point and kind != "restore":
            raise ValueError(f"operating_point goes with restore only (got {kind})")
        if targets is not None and (kind != "restore" or component is not None):
            raise ValueError("targets goes with restore only, and not together with component")
        if targets is not None and (not isinstance(targets, list) or any(not isinstance(t, str) or not t for t in targets)):
            raise ValueError("targets must be a list of knowledge-graph ids (comp:* · sv:*)")
        if approved is not None and (kind != "restore" or not isinstance(approved, dict)
                                     or not all(str(approved.get(k) or "").strip() for k in ("instance", "step", "approved_by"))):
            raise ValueError("approved goes with restore only and names the approved process step {instance, step, approved_by}")
        with self.lock:
            u = self.units[asset]
            if kind == "restore":
                if component is not None and component not in COMPONENTS:
                    raise ValueError(f"unknown component {component} (known: {sorted(COMPONENTS)})")
                only = ({COMPONENTS[t] for t in targets if t in COMPONENTS} if targets is not None
                        else {COMPONENTS[component]} if component else set(HEALTHY))
                plan = {attr: healthy for attr, healthy in HEALTHY.items()
                        if attr in only and (getattr(u.state, attr) != healthy or attr in u.faults)}
            elif kind in FAULT_KINDS:
                attr, default = FAULT_KINDS[kind]
                if target is None and severity is not None:
                    if severity not in SEVERITY[kind]:
                        raise ValueError(f"unknown severity {severity} for {kind} (known: {sorted(SEVERITY[kind])})")
                    default = SEVERITY[kind][severity]
                value = default if target is None else target
                lo, hi = DOMAIN[attr]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
                    raise ValueError(f"target for {kind} ({attr}) must be a number in [{lo:g}, {hi:g}], got {value!r}")
                plan = {attr: float(value)}
            else:
                raise ValueError(f"unknown fault kind {kind}")
            for attr, tgt in plan.items():
                rate = (tgt - getattr(u.state, attr)) / max(1.0, float(ramp_sim_s))
                u.faults[attr] = Fault(kind, attr, tgt, rate)
            # the unit's injection is always the *last* request: one without a press (the process's maintenance restore, a test
            # script) clears the previous press, so a later alert is never linked to a press that no longer describes the unit
            u.injection = dict(origin, kind=kind, at=now_iso()) if origin is not None else None
            setpoints = self._to_operating_point(u) if operating_point else None
            if approved is None:
                button = (origin or {}).get("button")
                head = f"[{button}] — " if button else ""
                if kind == "restore":
                    what = head + "결함을 정상으로 되돌림" + (" · 팬 · 부하 지령을 평소 운전점으로" if operating_point else "")
                else:
                    what = head + f"{FAULT_WORDS[kind]} 주입"
                _outside(u, "restore" if kind == "restore" else "fault", what, (origin or {}).get("by"))
            return {"asset": asset, "kind": kind, "targets": plan, "ramp_sim_s": ramp_sim_s,
                    "injection": u.injection,
                    "setpoints": setpoints,
                    **({"not_modeled": [t for t in targets if t not in COMPONENTS]} if targets is not None else {})}

    @staticmethod
    def _to_operating_point(u: Unit) -> dict:
        """Fan and load set-points back to normal. Returns what they were and what they are now (the caller shows both)."""
        before = {"FanSpeedSP": u.state.fan_pct, "LoadSP": u.state.load_pct}
        u.state.fan_pct, u.state.load_pct = thermal.NORMAL_FAN_PCT, thermal.NORMAL_LOAD_PCT
        return {"before": before, "after": {"FanSpeedSP": u.state.fan_pct, "LoadSP": u.state.load_pct}}

    def reset(self, button: str | None = None, by: str | None = None) -> None:
        """Every unit back to the healthy operating point: no faults, REMOTE_AUTO, RUN, fan 60, load 90, pump A, TS1 48.
        An outside change on every unit (button · by = the press behind it, when the caller names one)."""
        what = (f"[{button}] — " if button else "") + "설비 3기를 정상 운전점으로 되돌림(결함 · 보호 정지 · 팬 · 부하 지령)"
        with self.lock:
            for u in self.units.values():
                u.faults.clear()
                u.injection = None
                u.state.cooler_health, u.state.leak, u.state.bearing_wear, u.state.pump = 1.0, 0.0, 0.0, "A"
                u.state.fan_pct, u.state.load_pct = thermal.NORMAL_FAN_PCT, thermal.NORMAL_LOAD_PCT
                u.state.ts1 = thermal.NORMAL_TS1
                u.ctrl = plc.PlcState()
                _outside(u, "reset", what, by)

    # ---- commands (called from MQTT thread) ----
    def command(self, asset: str, cmd: dict, source: str) -> plc.CmdResult:
        """A PLC write. HITL (the approved command the gateway passed) is the approved path; a manual write (LOCAL panel · FUXA)
        that the PLC executed is an outside change."""
        with self.lock:
            u = self.units[asset]
            r = plc.apply_command(u.ctrl, u.state, cmd, source=source, now=now())
            if r.result == "DONE" and source != "HITL":
                writes = " · ".join(f"{res} {v:g}" for res, v in r.writes_applied.items())
                _outside(u, "manual", f"{SOURCE_WORDS.get(source, source)} 수동 조작 — {writes}", source)
            return r

    def set_mode(self, asset: str, mode: str, requester: str) -> bool:
        with self.lock:
            u = self.units[asset]
            before = u.ctrl.mode
            ok = plc.set_mode(u.ctrl, mode, requester)
            if ok and mode != before:
                _outside(u, "mode", f"{SOURCE_WORDS.get(requester, requester)}에서 운전 모드 변경 — {plc.TEXT[before]} → {plc.TEXT[mode]}",
                         requester)
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

    def status(self, asset: str, t: str | None = None) -> dict:
        """The PLC status of one unit measured at `t` (the tick's time; now when not given)."""
        u = self.units[asset]
        st = plc.status_payload(asset, u.ctrl, u.state, t or now_iso())
        st["sim_t"] = round(self.sim_t, 1)
        st["time_scale"] = self.time_scale
        st['disturbance_ramps'] = sorted(u.faults)
        st['injection'] = u.injection
        st['outside'] = dict(u.outside, boot=self.boot)
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
