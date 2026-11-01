"""L4 CEP (the Flink MATCH_RECOGNIZE job) as an explicit state machine per asset and pattern.

Every held pattern walks the same four phases; only its raise / clear conditions differ:

  IDLE      --raise holds for hold_s--> RAISED   (emit RAISE)
  RAISED    --clear holds for clear_hold_s--> IDLE  (emit CLEAR, same alertId)

The raise / clear predicates, hold seconds and names are the Neo4j AnomalyPattern definitions (TESTS · clearRule ·
holdSeconds · name — it/neo4j/v2/instances.cypher); pattern_runtime evaluates them and drives `_step` here. Times are
simulated seconds (the caller converts wall clock with TIME_SCALE).

PLC trips are not held patterns: the PLC's own trip is authoritative, and `trip_alert` turns its cause into the trip
pattern's code (TRIP_PATTERNS — the graph names those codes, detectionMode plc-trip). CLEAR keeps the original pattern.
"""
from dataclasses import dataclass
import secrets

from hydcommon.topics import asset_key

TRIP_PATTERNS = {'OVERTEMP': 'OVERHEAT_TRIP', 'LOW_PRESSURE': 'LOW_PRESSURE_TRIP', 'HIGH_VIBRATION': 'HIGH_VIBRATION_TRIP'}


@dataclass
class CepState:
    phase: str = "IDLE"            # IDLE | CANDIDATE | RAISED | CLEARING
    since: float | None = None
    alert_id: str | None = None
    seq: int = 0
    last_t: float | None = None


@dataclass
class TripState:
    tripped: bool = False
    alert_id: str | None = None
    seq: int = 0
    pattern: str | None = None
    reason: str | None = None


def _alert(asset: str, alert_id: str, pattern: str, state: str, severity: str, t_iso: str | None, evidence: dict,
           name: str | None = None) -> dict:
    """The alerts-topic record (hydcommon.schemas.alert_record). `name` is the pattern's display name from the graph."""
    return {"alertId": alert_id, "asset": asset, "pattern": pattern, "name": name, "severity": severity, "state": state,
            "t": t_iso, "evidence": evidence}


def interrupt(st: CepState) -> None:
    """Unknown data cancels a pending hold; it cannot clear a raised alert."""
    if st.phase == 'CANDIDATE':
        st.phase = 'IDLE'
    elif st.phase == 'CLEARING':
        st.phase = 'RAISED'
    st.since = None


def _step(st: CepState, asset: str, t_sim: float, pattern: str, severity: str, cond: bool, clear: bool,
          hold_s: float, t_iso: str | None, ev: dict, max_gap_s: float | None = None, name: str | None = None) -> dict | None:
    """One tick of the four-phase machine shared by every held pattern."""
    if max_gap_s is not None and st.last_t is not None:
        if t_sim <= st.last_t:
            return None
        if t_sim - st.last_t > max_gap_s:
            interrupt(st)
    st.last_t = t_sim
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
            return _alert(asset, st.alert_id, pattern, "RAISE", severity, t_iso, ev, name)
    elif st.phase == "RAISED":
        if clear:
            st.phase, st.since = "CLEARING", t_sim
    elif st.phase == "CLEARING":
        if not clear:
            st.phase, st.since = "RAISED", None
        elif t_sim - st.since >= hold_s:
            aid = st.alert_id
            st.phase, st.since, st.alert_id = "IDLE", None, None
            return _alert(asset, aid, pattern, "CLEAR", severity, t_iso, ev, name)
    return None


def trip_alert(st: TripState, asset: str, tripped: bool, t_iso: str, reason: str | None, names: dict) -> dict | None:
    """RAISE when the PLC enters TRIP, CLEAR (same alertId and pattern) when it leaves it. A cause outside TRIP_PATTERNS is
    PLC_TRIP (no graph pattern names it). `names`: pattern code -> display name from the graph."""
    if tripped and not st.tripped:
        st.tripped = True
        st.seq += 1
        st.alert_id = f"ALT-{asset_key(asset)}-TRIP-{st.seq:03d}-{secrets.token_hex(2)}"
        st.pattern = TRIP_PATTERNS.get(reason, 'PLC_TRIP')
        st.reason = reason
        return _alert(asset, st.alert_id, st.pattern, "RAISE", "CRITICAL", t_iso, {"trip": reason}, names.get(st.pattern))
    if not tripped and st.tripped:
        st.tripped = False
        aid, pattern, original_reason = st.alert_id, st.pattern, st.reason
        st.alert_id, st.pattern, st.reason = None, None, None
        return _alert(asset, aid, pattern, "CLEAR", "CRITICAL", t_iso, {'trip': original_reason}, names.get(pattern))
    return None
