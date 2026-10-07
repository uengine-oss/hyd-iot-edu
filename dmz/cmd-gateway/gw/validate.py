"""cmd-gateway validation (v3 7.2, DMZ row): the six checks every downward command must pass.

  ① schema  ② action whitelist  ③ expiry  ④ cmdId duplicate  ⑤ approval ledger (A148)  ⑥ PLC mode == REMOTE_AUTO + rate limit (2/s)
Pure logic — no IO — so it can be unit-tested and read in a lecture.

⑤ (A148, remaining-sweep 69): Kafka has no authentication, so a client that can write `action.cmd` could get the PLC to act
(`.evidence/a148/69/`). process now writes an approval record on the audit topic before each command
(`hydcommon.schemas.CMD_APPROVAL_LEDGER_EVENT`: cmdId · approvalId · HMAC fingerprint of the approved fields); the gateway keeps
those records (`GatewayState.approvals`, fed by main.py's audit consumer) and forwards a command only when its cmdId has a
record, the approvalId matches and the fingerprint recomputed from the command equals the recorded one. A forged command has
no record; a tampered one (other actions / asset / expiry) has a different fingerprint; without the key no record can be forged.
"""
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple

from hydcommon.schemas import ACTION_WHITELIST, CMD_APPROVAL_LEDGER_EVENT, actions_to_writes, cmd_fingerprint, validate_action_cmd
from hydcommon.timeutil import parse_iso

RATE_LIMIT_PER_S = 2
APPROVALS_KEPT = 512
#: The check names a Decision can carry when it rejects, in the order validate() applies them. The forwarded-command
#: audit record lists exactly these, so an auditor can match a later rejection's `check` to the list a pass went through.
CHECKS = ("SCHEMA", "WHITELIST", "EXPIRED", "DUPLICATE", "APPROVAL", "MODE", "RATE_LIMIT")


@dataclass
class GatewayState:
    seen_cmd_ids: deque = field(default_factory=lambda: deque(maxlen=256))
    last_status: dict = field(default_factory=dict)        # asset id -> latest plant/{a}/status payload
    per_second: dict = field(default_factory=dict)         # epoch second -> commands passed
    approvals: OrderedDict = field(default_factory=OrderedDict)   # cmdId -> process approval ledger record (A148)


class Decision(NamedTuple):
    ok: bool
    check: str            # PASS | one of CHECKS (SCHEMA | WHITELIST | EXPIRED | DUPLICATE | APPROVAL | MODE | RATE_LIMIT)
    reason: str | None
    mqtt_payload: dict | None


def record_approval(st: GatewayState, audit_event: dict) -> bool:
    """Keep process's approval ledger record from an audit-topic event; anything else is ignored. True when kept."""
    if not isinstance(audit_event, dict) or audit_event.get("actor") != "process" or audit_event.get("event") != CMD_APPROVAL_LEDGER_EVENT:
        return False
    rec = audit_event.get("detail") or {}
    if not isinstance(rec, dict) or not rec.get("cmdId") or not rec.get("approvalId") or not rec.get("fingerprint"):
        return False
    st.approvals[rec["cmdId"]] = dict(rec)
    while len(st.approvals) > APPROVALS_KEPT:
        st.approvals.popitem(last=False)
    return True


def _approval_problem(cmd: dict, st: GatewayState) -> str | None:
    if not cmd.get("approvalId"):
        return "command carries no approvalId"
    rec = st.approvals.get(cmd["cmdId"])
    if rec is None:
        return f"no process approval record for cmdId {cmd['cmdId']}"
    if rec.get("approvalId") != cmd["approvalId"]:
        return f"approvalId {cmd['approvalId']} does not match the recorded {rec.get('approvalId')}"
    if cmd_fingerprint(cmd) != rec.get("fingerprint"):
        return "command fingerprint differs from the approval record (actions/asset/expiry/approver changed)"
    return None


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
    # ⑤ approval ledger (A148): process recorded this exact command before publishing it
    problem = _approval_problem(cmd, st)
    if problem:
        return Decision(False, "APPROVAL", problem, None)
    # ⑥ PLC mode (from the latest retained status) + rate limit
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
            "text": f"{'RAISE' if raised else 'CLEAR'} {alert.get('pattern')} ({alert.get('alertId')})",
            "display_text": f"{'경보 발생' if raised else '경보 해제'} · " +
                {"COOLER_DEGRADATION": "쿨러 성능 저하", "PUMP_LEAKAGE": "펌프 내부 누설", "FAN_VIBRATION": "팬 진동 상승",
                 "TEMP_TRIP": "유온 보호 정지", "OVERHEAT_TRIP": "유온 보호 정지"}.get(alert.get('pattern'), str(alert.get('pattern')))}


def upgrade_retained_alert(alert: dict) -> dict | None:
    """Enrich legacy display records without creating/changing an alarm event."""
    if (not isinstance(alert, dict) or alert.get("display_text")
            or alert.get("state") not in {"RAISE", "CLEAR"}
            or not alert.get("pattern") or not alert.get("alertId")):
        return None
    return {**alert, "display_text": alert_to_ot(alert)["display_text"]}
