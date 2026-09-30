"""L4 CEP (the Flink MATCH_RECOGNIZE job) as an explicit state machine per asset.

COOLER_DEGRADATION
  IDLE      --cond holds for hold_s--> RAISED   (emit RAISE)
  RAISED    --clear holds for hold_s--> IDLE    (emit CLEAR, same alertId)
  cond  : TS1 > 55 and CE < 70 and TS1 slope > 0
  clear : TS1 < 52 and TS1 slope <= 0
OVERHEAT_TRIP : RAISE when the PLC status says TRIP, CLEAR when it is back to RUN.
Times are simulated seconds (the caller converts wall clock with TIME_SCALE).
"""
from dataclasses import dataclass
import secrets

from hydcommon.topics import asset_key

RAISE_TS1, RAISE_CE, CLEAR_TS1 = 55.0, 70.0, 52.0
HOLD_S = 60.0


@dataclass
class CepState:
    phase: str = "IDLE"            # IDLE | CANDIDATE | RAISED | CLEARING
    since: float | None = None
    alert_id: str | None = None
    seq: int = 0


@dataclass
class TripState:
    tripped: bool = False
    alert_id: str | None = None
    seq: int = 0


def _alert(asset: str, alert_id: str, pattern: str, state: str, severity: str, t_iso: str | None, evidence: dict) -> dict:
    return {"alertId": alert_id, "asset": asset, "pattern": pattern, "severity": severity, "state": state,
            "t": t_iso, "evidence": evidence}


def evaluate(st: CepState, asset: str, t_sim: float, ts1: float, ce: float, slope: float,
             hold_s: float = HOLD_S, t_iso: str | None = None, score: float | None = None) -> dict | None:
    cond = ts1 > RAISE_TS1 and ce < RAISE_CE and slope > 0
    clear = ts1 < CLEAR_TS1 and slope <= 0
    ev = {"ts1": ts1, "ce": ce, "ts1_slope": round(slope, 4), "score": score}

    if st.phase == "IDLE":
        if cond:
            st.phase, st.since = "CANDIDATE", t_sim
    elif st.phase == "CANDIDATE":
        if not cond:
            st.phase, st.since = "IDLE", None
        elif t_sim - st.since >= hold_s:
            st.seq += 1
            st.alert_id = f"ALT-{asset_key(asset)}-{st.seq:04d}-{secrets.token_hex(2)}"   # suffix: unique across restarts
            st.phase, st.since = "RAISED", None
            return _alert(asset, st.alert_id, "COOLER_DEGRADATION", "RAISE", "HIGH", t_iso, ev)
    elif st.phase == "RAISED":
        if clear:
            st.phase, st.since = "CLEARING", t_sim
    elif st.phase == "CLEARING":
        if not clear:
            st.phase, st.since = "RAISED", None
        elif t_sim - st.since >= hold_s:
            aid = st.alert_id
            st.phase, st.since, st.alert_id = "IDLE", None, None
            return _alert(asset, aid, "COOLER_DEGRADATION", "CLEAR", "HIGH", t_iso, ev)
    return None


def trip_alert(st: TripState, asset: str, tripped: bool, t_iso: str | None = None, reason: str | None = None) -> dict | None:
    if tripped and not st.tripped:
        st.tripped = True
        st.seq += 1
        st.alert_id = f"ALT-{asset_key(asset)}-TRIP-{st.seq:03d}-{secrets.token_hex(2)}"
        return _alert(asset, st.alert_id, "OVERHEAT_TRIP", "RAISE", "CRITICAL", t_iso, {"trip": reason or "OVERTEMP"})
    if not tripped and st.tripped:
        st.tripped = False
        aid, st.alert_id = st.alert_id, None
        return _alert(asset, aid, "OVERHEAT_TRIP", "CLEAR", "CRITICAL", t_iso, {})
    return None
