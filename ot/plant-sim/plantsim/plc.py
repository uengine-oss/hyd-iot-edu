"""soft-PLC (L1): operating modes, command ownership, command validation, hard interlock.

Mirrors v3 section 7.1/7.2 (OT PLC row):
  mode/source match -> expiry (PLC clock) -> last-32 cmdId dedupe -> write range -> hard interlock

Writes: FanSpeedSP, LoadSP, Reset, PumpSelect (0 = A, 1 = B; ontology actr:pump-selector), Stop (planned stop, state STOP).
Interlocks (ontology AFFECTS notes): TS1 > 65 OVERTEMP, PS1 < 130 LOW_PRESSURE, VS1 >= 2.0 HIGH_VIBRATION. No automatic reset.
"""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import time

from hydcommon.schemas import MODES
from hydcommon.timeutil import parse_iso
from hydcommon.forecast import MODEL_ID
from . import thermal

TRIP_TS1 = thermal.TRIP_TS1
TRIP_PS1 = thermal.TRIP_PS1
TRIP_VS1 = thermal.TRIP_VS1
RESET_TS1 = 55.0
LOAD_MIN = 60.0
DEDUP_N = 32
WRITE_RANGES = {"FanSpeedSP": (0.0, 100.0), "LoadSP": (LOAD_MIN, 100.0), "Reset": (1, 1), "PumpSelect": (0, 1), "Stop": (1, 1)}
PUMP_OF = {0: "A", 1: "B"}


@dataclass
class PlcState:
    mode: str = "REMOTE_AUTO"
    state: str = "RUN"            # RUN | TRIP | STOP (planned stop by command; Reset restarts)
    trip: str | None = None       # OVERTEMP | LOW_PRESSURE | HIGH_VIBRATION
    recent_cmd_ids: deque = field(default_factory=lambda: deque(maxlen=DEDUP_N))
    last_cmd_id: str | None = None
    last_result: str | None = None
    last_reason: str | None = None
    last_source: str | None = None


@dataclass
class CmdResult:
    cmd_id: str
    result: str                   # DONE | REJECTED
    reason: str | None
    writes_applied: dict


def check_interlock(p: PlcState, u: thermal.UnitState) -> None:
    """Hard interlocks on a running unit: TS1 above 65 C, discharge pressure under 130 bar, fan vibration at or above
    2.0 mm/s. The first one that holds trips the unit; there is no automatic reset."""
    if p.state != "RUN":
        return
    if u.ts1 > TRIP_TS1:
        p.state, p.trip = "TRIP", "OVERTEMP"
    elif u.ps1 < TRIP_PS1:
        p.state, p.trip = "TRIP", "LOW_PRESSURE"
    elif u.vs1 >= TRIP_VS1:
        p.state, p.trip = "TRIP", "HIGH_VIBRATION"


def _reject(p: PlcState, cmd_id: str, reason: str, source: str) -> CmdResult:
    p.last_cmd_id, p.last_result, p.last_reason, p.last_source = cmd_id, "REJECTED", reason, source
    return CmdResult(cmd_id, "REJECTED", reason, {})


def apply_command(p: PlcState, u: thermal.UnitState, cmd: dict, source: str, now: datetime) -> CmdResult:
    cmd_id = str(cmd.get("cmdId", ""))
    writes = cmd.get("writes") or []

    # 1. mode / source ownership
    if source == "HITL":
        if p.mode != "REMOTE_AUTO":
            return _reject(p, cmd_id, "MODE_MISMATCH", source)
    elif source == "FUXA":
        if p.mode == "LOCAL":
            return _reject(p, cmd_id, "MODE_MISMATCH", source)
    else:
        return _reject(p, cmd_id, "UNKNOWN_SOURCE", source)

    # 2. expiry (PLC clock)
    exp = cmd.get("expiresAt")
    if exp:
        try:
            if parse_iso(exp) <= now:
                return _reject(p, cmd_id, "EXPIRED", source)
        except ValueError:
            return _reject(p, cmd_id, "BAD_EXPIRY", source)

    # 3. duplicate cmdId (last 32)
    if cmd_id in p.recent_cmd_ids:
        return _reject(p, cmd_id, "DUPLICATE", source)
    p.recent_cmd_ids.append(cmd_id)

    # 4. write range
    for w in writes:
        res, v = w.get("res"), w.get("v")
        if res not in WRITE_RANGES:
            return _reject(p, cmd_id, "UNKNOWN_RESOURCE", source)
        lo, hi = WRITE_RANGES[res]
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return _reject(p, cmd_id, "OUT_OF_RANGE", source)
        if not (lo <= fv <= hi):
            return _reject(p, cmd_id, "OUT_OF_RANGE", source)

    # 5. hard interlock
    is_reset = any(w.get("res") == "Reset" for w in writes)
    if p.state == "TRIP" and not is_reset:
        return _reject(p, cmd_id, "INTERLOCK_TRIP", source)
    if is_reset and u.ts1 >= RESET_TS1:
        return _reject(p, cmd_id, "RESET_TOO_HOT", source)

    applied = {}
    for w in writes:
        res, v = w["res"], float(w["v"])
        if res == "FanSpeedSP":
            u.fan_pct = v
        elif res == "LoadSP":
            u.load_pct = v
        elif res == "Reset":
            p.state, p.trip = "RUN", None
        elif res == "PumpSelect":
            u.pump = PUMP_OF[int(round(v))]
        elif res == "Stop":
            p.state, p.trip = "STOP", None
        applied[res] = v

    if source == "FUXA" and p.mode == "REMOTE_AUTO":
        p.mode = "REMOTE_MANUAL"   # manual always wins; auto actions need a human to re-enable

    p.last_cmd_id, p.last_result, p.last_reason, p.last_source = cmd_id, "DONE", None, source
    return CmdResult(cmd_id, "DONE", None, applied)


def set_mode(p: PlcState, mode: str, requester: str) -> bool:
    if requester not in ("FUXA", "LOCAL") or mode not in MODES:
        return False
    p.mode = mode
    return True


def normalize_manual(payload: dict) -> dict:
    """FUXA writes a bare {"FanSpeedSP": 80}; turn it into the v3 cmd/manual form."""
    if "writes" in payload:
        return payload
    writes = [{"res": k, "v": v} for k, v in payload.items() if k in WRITE_RANGES]
    return {"cmdId": f"FUXA-{int(time.time() * 1000)}", "source": "FUXA", "writes": writes}


def status_payload(asset: str, p: PlcState, u: thermal.UnitState, now_iso: str) -> dict:
    return {
        "asset": asset,
        "t": now_iso,
        "mode": p.mode,
        "state": p.state,
        "forecast_model": MODEL_ID,
        "ts1": u.ts1,
        "t_amb": u.t_amb,
        "trip": p.trip,
        "fan_pct": u.fan_pct,
        "load_pct": u.load_pct,
        "cooler_health": round(u.cooler_health, 3),
        "leak": round(u.leak, 3),
        "bearing_wear": round(u.bearing_wear, 3),
        "pump": u.pump,
        "cmdId": p.last_cmd_id,
        "result": p.last_result,
        "reason": p.last_reason,
        "source": p.last_source,
        "interlock": "TRIP" if p.state == "TRIP" else "PASS",
    }
