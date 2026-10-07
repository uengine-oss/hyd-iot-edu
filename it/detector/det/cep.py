"""L4 CEP (the Flink MATCH_RECOGNIZE job) as an explicit state machine per asset and pattern.

Every pattern walks the same four phases; only its raise / clear conditions differ:

  IDLE      --raise holds for hold_s--> RAISED   (emit RAISE)
  RAISED    --clear holds for hold_s--> IDLE     (emit CLEAR, same alertId)

What the running detector executes is `_step` (the phase machine) and `trip_alert`, driven by pattern_runtime with the
raise/clear predicates and hold seconds loaded from the Neo4j AnomalyPattern definitions (TESTS · clearRule · holdSeconds).
The fixed thresholds below (RAISE_TS1 … CLEAR_VS1) and evaluate / evaluate_pump / evaluate_fan are the *reference*
predicates of the three teaching patterns — the lecture text and tests/test_cep.py use them; main.py does not call them,
and the names cep_state / pump_state / fan_state on AssetState are display aliases of the runtime's pattern states
(main.DISPLAY_STATES), not executable predicates:

  COOLER_DEGRADATION  raise: TS1 > 55 and CE < 70 and slope(TS1) > 0          clear: TS1 < 52 and slope(TS1) <= 0
  PUMP_LEAKAGE        raise: PS1 < 165 and FS1 < 8.0 and LoadSP >= 80         clear: (PS1 >= 168 and FS1 >= 8.0) or LoadSP < 80
  FAN_VIBRATION       raise: VS1 > 1.2 and slope(VS1) > 0                      clear: VS1 < 1.1
  *_TRIP              Preserve the PLC trip cause; CLEAR keeps the original pattern (no hold).

The clear lines sit below the raise lines (hysteresis) so a value hovering at the threshold does not flap. The pump
pattern needs LoadSP >= 80 because discharge pressure is naturally lower at low load; dropping the load therefore ends the
match (the leak is masked, not gone — the re-observation of the process still checks PS1 >= 165).
Times are simulated seconds (the caller converts wall clock with TIME_SCALE).
"""
from dataclasses import dataclass
import secrets

from hydcommon.topics import asset_key

RAISE_TS1, RAISE_CE, CLEAR_TS1 = 55.0, 70.0, 52.0
RAISE_PS1, RAISE_FS1, RAISE_LOAD, CLEAR_PS1 = 165.0, 8.0, 80.0, 168.0
RAISE_VS1, CLEAR_VS1 = 1.2, 1.1
HOLD_S = 60.0


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


def _alert(asset: str, alert_id: str, pattern: str, state: str, severity: str, t_iso: str | None, evidence: dict) -> dict:
    return {"alertId": alert_id, "asset": asset, "pattern": pattern, "severity": severity, "state": state,
            "t": t_iso, "evidence": evidence}


def interrupt(st: CepState) -> None:
    """Unknown data cancels a pending hold; it cannot clear a raised alert."""
    if st.phase == 'CANDIDATE':
        st.phase = 'IDLE'
    elif st.phase == 'CLEARING':
        st.phase = 'RAISED'
    st.since = None


def _step(st: CepState, asset: str, t_sim: float, pattern: str, severity: str, cond: bool, clear: bool,
          hold_s: float, t_iso: str | None, ev: dict, max_gap_s: float | None = None) -> dict | None:
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
            return _alert(asset, st.alert_id, pattern, "RAISE", severity, t_iso, ev)
    elif st.phase == "RAISED":
        if clear:
            st.phase, st.since = "CLEARING", t_sim
    elif st.phase == "CLEARING":
        if not clear:
            st.phase, st.since = "RAISED", None
        elif t_sim - st.since >= hold_s:
            aid = st.alert_id
            st.phase, st.since, st.alert_id = "IDLE", None, None
            return _alert(asset, aid, pattern, "CLEAR", severity, t_iso, ev)
    return None


def evaluate(st: CepState, asset: str, t_sim: float, ts1: float, ce: float, slope: float,
             hold_s: float = HOLD_S, t_iso: str | None = None, score: float | None = None,
             max_gap_s: float | None = None) -> dict | None:
    """COOLER_DEGRADATION (pattern:cooler-degradation)."""
    cond = ts1 > RAISE_TS1 and ce < RAISE_CE and slope > 0
    clear = ts1 < CLEAR_TS1 and slope <= 0
    ev = {"ts1": ts1, "ce": ce, "ts1_slope": round(slope, 4), "score": score}
    return _step(st, asset, t_sim, "COOLER_DEGRADATION", "HIGH", cond, clear, hold_s, t_iso, ev, max_gap_s)


def evaluate_pump(st: CepState, asset: str, t_sim: float, ps1: float, fs1: float, load: float,
                  hold_s: float = HOLD_S, t_iso: str | None = None, score: float | None = None,
                  running: bool = True, max_gap_s: float | None = None) -> dict | None:
    """PUMP_LEAKAGE (pattern:pump-leakage): discharge pressure and flow both low while the unit is loaded."""
    # A retained load setpoint is not evidence that the pump is running.
    # Stop/TRIP cancels an unraised candidate; it cannot prove an existing leak
    # repaired, so neither RAISE nor CLEAR is permitted while stopped.
    cond = running and ps1 < RAISE_PS1 and fs1 < RAISE_FS1 and load >= RAISE_LOAD
    clear = running and ((ps1 >= CLEAR_PS1 and fs1 >= RAISE_FS1) or load < RAISE_LOAD)
    ev = {"ps1": ps1, "fs1": fs1, "load": load, "score": score}
    return _step(st, asset, t_sim, "PUMP_LEAKAGE", "HIGH", cond, clear, hold_s, t_iso, ev, max_gap_s)


def evaluate_fan(st: CepState, asset: str, t_sim: float, vs1: float, vs1_slope: float,
                 hold_s: float = HOLD_S, t_iso: str | None = None, score: float | None = None,
                 max_gap_s: float | None = None) -> dict | None:
    """FAN_VIBRATION (pattern:fan-vibration): vibration above 1.2 mm/s and still rising."""
    cond = vs1 > RAISE_VS1 and vs1_slope > 0
    # Decision 13 specifies sustained lower-threshold hysteresis. Normal
    # sub-threshold vibration can fluctuate; slope belongs to onset detection.
    clear = vs1 < CLEAR_VS1
    ev = {"vs1": vs1, "vs1_slope": round(vs1_slope, 5), "score": score}
    return _step(st, asset, t_sim, "FAN_VIBRATION", "HIGH", cond, clear, hold_s, t_iso, ev, max_gap_s)


def trip_alert(st: TripState, asset: str, tripped: bool, t_iso: str | None = None, reason: str | None = None) -> dict | None:
    if tripped and not st.tripped:
        st.tripped = True
        st.seq += 1
        st.alert_id = f"ALT-{asset_key(asset)}-TRIP-{st.seq:03d}-{secrets.token_hex(2)}"
        st.pattern = {'OVERTEMP':'OVERHEAT_TRIP','LOW_PRESSURE':'LOW_PRESSURE_TRIP',
                      'HIGH_VIBRATION':'HIGH_VIBRATION_TRIP'}.get(reason,'PLC_TRIP')
        st.reason = reason
        return _alert(asset, st.alert_id, st.pattern, "RAISE", "CRITICAL", t_iso, {"trip": reason})
    if not tripped and st.tripped:
        st.tripped = False
        aid, st.alert_id = st.alert_id, None
        pattern, original_reason = st.pattern, st.reason
        st.pattern, st.reason = None, None
        return _alert(asset, aid, pattern or 'PLC_TRIP', "CLEAR", "CRITICAL", t_iso, {'trip':original_reason})
    return None
