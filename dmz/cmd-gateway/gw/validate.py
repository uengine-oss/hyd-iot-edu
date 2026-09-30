"""cmd-gateway validation (v3 7.2, DMZ row): the five checks every downward command must pass.

  ① schema  ② action whitelist  ③ expiry  ④ cmdId duplicate  ⑤ PLC mode == REMOTE_AUTO + rate limit (2/s)
Pure logic — no IO — so it can be unit-tested and read in a lecture.
"""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple

from hydcommon.schemas import ACTION_WHITELIST, actions_to_writes, validate_action_cmd
from hydcommon.timeutil import parse_iso

RATE_LIMIT_PER_S = 2


@dataclass
class GatewayState:
    seen_cmd_ids: deque = field(default_factory=lambda: deque(maxlen=256))
    last_status: dict = field(default_factory=dict)        # asset id -> latest plant/{a}/status payload
    per_second: dict = field(default_factory=dict)         # epoch second -> commands passed


class Decision(NamedTuple):
    ok: bool
    check: str            # PASS | SCHEMA | WHITELIST | EXPIRED | DUPLICATE | MODE | RATE_LIMIT
    reason: str | None
    mqtt_payload: dict | None


def validate(cmd: dict, st: GatewayState, now: datetime) -> Decision:
    # ① schema
    errs = validate_action_cmd(cmd)
    if errs:
        return Decision(False, "SCHEMA", "; ".join(errs), None)
    # ② whitelist
    codes = [a["code"] for a in cmd["actions"]]
    bad = [c for c in codes if c not in ACTION_WHITELIST]
    if bad:
        return Decision(False, "WHITELIST", f"action not allowed: {bad}", None)
    # ③ expiry
    try:
        exp = parse_iso(cmd["expiresAt"])
    except (ValueError, TypeError):
        return Decision(False, "EXPIRED", "unparseable expiresAt", None)
    if exp <= now:
        return Decision(False, "EXPIRED", f"expired at {cmd['expiresAt']}", None)
    # ④ duplicate
    if cmd["cmdId"] in st.seen_cmd_ids:
        return Decision(False, "DUPLICATE", f"cmdId {cmd['cmdId']} already forwarded", None)
    # ⑤ PLC mode (from the latest retained status) + rate limit
    status = st.last_status.get(cmd["asset"])
    if not status:
        return Decision(False, "MODE", f"no status seen for {cmd['asset']}", None)
    if status.get("mode") != "REMOTE_AUTO":
        return Decision(False, "MODE", f"PLC mode is {status.get('mode')} (REMOTE_AUTO required)", None)
    sec = int(now.timestamp())
    st.per_second = {k: v for k, v in st.per_second.items() if k >= sec - 5}
    if st.per_second.get(sec, 0) >= RATE_LIMIT_PER_S:
        return Decision(False, "RATE_LIMIT", f"more than {RATE_LIMIT_PER_S} commands in one second", None)

    st.per_second[sec] = st.per_second.get(sec, 0) + 1
    st.seen_cmd_ids.append(cmd["cmdId"])
    payload = {"cmdId": cmd["cmdId"], "source": "HITL", "expiresAt": cmd["expiresAt"],
               "writes": actions_to_writes(cmd["actions"])}
    return Decision(True, "PASS", None, payload)


def alert_to_ot(alert: dict) -> dict:
    """Relay an IT alert to plant/{a}/alert (display only, retained). level 2 = RAISE, 0 = CLEAR (FUXA semaphore)."""
    raised = alert.get("state") == "RAISE"
    return {"alertId": alert.get("alertId"), "pattern": alert.get("pattern"), "severity": alert.get("severity"),
            "state": alert.get("state"), "level": 2 if raised else 0, "t": alert.get("t"),
            "text": f"{'RAISE' if raised else 'CLEAR'} {alert.get('pattern')} ({alert.get('alertId')})"}
