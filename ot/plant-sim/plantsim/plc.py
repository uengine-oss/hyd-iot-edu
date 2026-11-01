"""soft-PLC (L1): operating modes, command ownership, command validation, hard interlock.

Mirrors v3 section 7.1/7.2 (OT PLC row):
  format -> mode/source match -> expiry (PLC clock) -> last-32 cmdId dedupe -> write range -> hard interlock -> apply
A rejected command changes nothing and is not remembered as seen (only an executed cmdId blocks a replay).

Who may write in which mode (one writer per mode, the machine-side panel always):
  REMOTE_AUTO    HITL (cmd-gateway, cmd/auto) · FUXA (cmd/manual) · LOCAL (the panel at the machine, POST /api/manual)
  REMOTE_MANUAL  FUXA · LOCAL                       — a FUXA / panel write in REMOTE_AUTO switches here (manual wins;
  LOCAL          LOCAL                                automatic commands need a human to switch back)
Writes: FanSpeedSP, LoadSP, Reset, PumpSelect (0 = A, 1 = B; ontology actr:pump-selector), Stop (planned stop, state STOP).
Interlocks (ontology AFFECTS notes): TS1 > 65 OVERTEMP, PS1 < 130 LOW_PRESSURE, VS1 >= 2.0 HIGH_VIBRATION. No automatic reset.
TEXT is the one table of the Korean words FUXA and the portal show for modes, states, results, reasons and trip causes.
"""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import secrets
import time

from hydcommon.schemas import MODES
from hydcommon.timeutil import parse_iso
from hydcommon.forecast import MODEL_ID
from hydcommon.plant_model import LOAD_MIN_PCT, RESET_TS1, TRIP_PS1, TRIP_TS1, TRIP_VS1
from . import thermal

DEDUP_N = 32
WRITE_RANGES = {"FanSpeedSP": (0.0, 100.0), "LoadSP": (LOAD_MIN_PCT, 100.0), "Reset": (1, 1), "PumpSelect": (0, 1), "Stop": (1, 1)}
PUMP_OF = {0: "A", 1: "B"}
WRITERS = {"REMOTE_AUTO": {"HITL", "FUXA", "LOCAL"}, "REMOTE_MANUAL": {"FUXA", "LOCAL"}, "LOCAL": {"LOCAL"}}
SOURCES = {"HITL", "FUXA", "LOCAL"}
TEXT = {"REMOTE_AUTO": "원격 자동", "REMOTE_MANUAL": "원격 수동", "LOCAL": "현장 제어",
        "RUN": "운전 중", "TRIP": "보호 정지", "STOP": "계획 정지", "DONE": "완료", "REJECTED": "거절",
        "OUT_OF_RANGE": "허용 범위 초과", "MODE_MISMATCH": "운전 모드 확인 필요", "INTERLOCK_TRIP": "보호 정지 중 (리셋만 가능)",
        "RESET_TOO_HOT": "유온이 55 ℃ 아래로 내려간 뒤 리셋", "EXPIRED": "명령 시한 지남", "DUPLICATE": "이미 실행한 명령",
        "BAD_EXPIRY": "명령 시한을 읽을 수 없음", "BAD_FORMAT": "명령 형식이 맞지 않음", "NO_WRITES": "바꿀 값이 없음",
        "UNKNOWN_RESOURCE": "없는 설정 항목", "UNKNOWN_SOURCE": "허용되지 않은 명령 출처",
        "OVERTEMP": "유온 높음", "LOW_PRESSURE": "토출 압력 낮음", "HIGH_VIBRATION": "팬 진동 높음"}


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


def _format_problem(cmd, source) -> str | None:
    if not isinstance(cmd, dict):
        return "BAD_FORMAT"
    if not isinstance(cmd.get("cmdId"), str) or not cmd["cmdId"].strip():
        return "BAD_FORMAT"
    writes = cmd.get("writes")
    if not isinstance(writes, list) or not all(isinstance(w, dict) and "res" in w and "v" in w for w in writes):
        return "BAD_FORMAT"
    if not writes:
        return "NO_WRITES"
    exp = cmd.get("expiresAt")
    if source == "HITL" and exp is None or exp is not None and not isinstance(exp, str):
        return "BAD_EXPIRY"
    return None


def apply_command(p: PlcState, u: thermal.UnitState, cmd: dict, source: str, now: datetime) -> CmdResult:
    cmd_id = cmd.get("cmdId") if isinstance(cmd, dict) and isinstance(cmd.get("cmdId"), str) else ""

    # 0. format: an id, a non-empty list of {res, v}; an automatic command must carry its expiry
    problem = _format_problem(cmd, source)
    if problem:
        return _reject(p, cmd_id, problem, source)
    writes = cmd["writes"]

    # 1. mode / source ownership
    if source not in SOURCES:
        return _reject(p, cmd_id, "UNKNOWN_SOURCE", source)
    if source not in WRITERS[p.mode]:
        return _reject(p, cmd_id, "MODE_MISMATCH", source)

    # 2. expiry (PLC clock)
    exp = cmd.get("expiresAt")
    if exp is not None:
        try:
            if parse_iso(exp) <= now:
                return _reject(p, cmd_id, "EXPIRED", source)
        except ValueError:
            return _reject(p, cmd_id, "BAD_EXPIRY", source)

    # 3. duplicate cmdId (last 32 executed)
    if cmd_id in p.recent_cmd_ids:
        return _reject(p, cmd_id, "DUPLICATE", source)

    # 4. write range
    for w in writes:
        res, v = w["res"], w["v"]
        if res not in WRITE_RANGES:
            return _reject(p, cmd_id, "UNKNOWN_RESOURCE", source)
        lo, hi = WRITE_RANGES[res]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            return _reject(p, cmd_id, "OUT_OF_RANGE", source)

    # 5. hard interlock
    is_reset = any(w["res"] == "Reset" for w in writes)
    if p.state == "TRIP" and not is_reset:
        return _reject(p, cmd_id, "INTERLOCK_TRIP", source)
    if is_reset and u.ts1 >= RESET_TS1:
        return _reject(p, cmd_id, "RESET_TOO_HOT", source)

    p.recent_cmd_ids.append(cmd_id)
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

    if source != "HITL" and p.mode == "REMOTE_AUTO":
        p.mode = "REMOTE_MANUAL"   # manual always wins; auto actions need a human to re-enable

    p.last_cmd_id, p.last_result, p.last_reason, p.last_source = cmd_id, "DONE", None, source
    return CmdResult(cmd_id, "DONE", None, applied)


def set_mode(p: PlcState, mode: str, requester: str) -> bool:
    if requester not in ("FUXA", "LOCAL") or mode not in MODES:
        return False
    p.mode = mode
    return True


def normalize_manual(payload, source: str) -> dict:
    """A manual write in either form — FUXA's bare {"FanSpeedSP": 80} or the v3 {"writes": [...]} — becomes one command with
    its own id (FUXA-… or LOCAL-…, kept when the sender gave a non-empty one). Keys that are not PLC resources are not writes
    (FUXA sends only its bound tags); a payload with no write is refused by apply_command as NO_WRITES."""
    payload = payload if isinstance(payload, dict) else {}
    given = payload.get("cmdId")
    cmd_id = given if isinstance(given, str) and given.strip() else f"{source}-{int(time.time() * 1000)}-{secrets.token_hex(2)}"
    writes = payload["writes"] if "writes" in payload else [{"res": k, "v": v} for k, v in payload.items() if k in WRITE_RANGES]
    return {"cmdId": cmd_id, "source": source, "writes": writes}


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
        **{f + "_text": TEXT.get(v, v) or "–" for f, v in (("mode", p.mode), ("state", p.state), ("result", p.last_result),
                                                            ("reason", p.last_reason), ("trip", p.trip))},
    }
