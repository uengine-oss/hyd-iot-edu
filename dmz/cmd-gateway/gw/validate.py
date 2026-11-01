"""cmd-gateway validation (v3 7.2, DMZ row): the seven checks every downward command must pass, and the OT alert board.

  ① SCHEMA (fields · known asset · each action's parameter, hydcommon.schemas.validate_action_cmd)  ② WHITELIST
  ③ EXPIRED  ④ DUPLICATE (cmdId already forwarded)  ⑤ APPROVAL (ledger, A148)  ⑥ MODE (PLC REMOTE_AUTO)  ⑦ RATE_LIMIT (2/s)
Pure logic — no IO — so it can be tested and read in a lecture. A rejected command is not remembered as seen.

⑤ (A148): Kafka has no authentication, so a client that can write `action.cmd` could get the PLC to act. process writes an
approval record on the audit topic before each command (`hydcommon.schemas.CMD_APPROVAL_LEDGER_EVENT`: cmdId · approvalId ·
HMAC fingerprint of the approved fields); the gateway keeps those records (`GatewayState.approvals`, fed by main.py's audit
consumer) and forwards a command only when its cmdId has a record, the approvalId matches and the fingerprint recomputed
from the command equals the recorded one. A forged command has no record; a tampered one (other actions / asset / expiry)
has a different fingerprint; without the key no record can be forged; the first record of a cmdId is kept (a later record
for the same cmdId cannot replace it).

The alert board: the OT display (FUXA) shows, per unit, the alerts that are raised and not yet cleared — never "the last
event", which turned green while a trip was still active when an older alert cleared after it.
"""
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple

from hydcommon.schemas import ACTION_WHITELIST, CMD_APPROVAL_LEDGER_EVENT, actions_to_writes, cmd_fingerprint, validate_action_cmd
from hydcommon.timeutil import parse_iso

RATE_LIMIT_PER_S = 2
APPROVALS_KEPT = 512
#: The checks validate() applies, in order (a rejection names one of them; gw/main adds PUBLISH_CHECK when the broker did
#: not take a command that passed them all). The forwarded-command audit record lists exactly these, so an auditor can match a later rejection's `check` to the list a pass went through.
CHECKS = ("SCHEMA", "WHITELIST", "EXPIRED", "DUPLICATE", "APPROVAL", "MODE", "RATE_LIMIT")
#: Rejection after every check passed: the plant MQTT broker did not take the command (gw/main.handle_command, G3b-14).
PUBLISH_CHECK = "MQTT"
#: What a person reads for each rejection (the audit record's reason_text; process shows it on the case).
CHECK_TEXT = {"SCHEMA": "명령 형식이 맞지 않아 설비로 보내지 않았습니다",
              "WHITELIST": "이 설비가 받지 않는 조치라 보내지 않았습니다",
              "EXPIRED": "명령 시한이 지나 보내지 않았습니다",
              "DUPLICATE": "이미 보낸 명령이라 다시 보내지 않았습니다",
              "APPROVAL": "승인 기록과 맞지 않는 명령이라 보내지 않았습니다",
              "MODE": "설비가 원격 자동 모드가 아니어서 보내지 않았습니다 — 운전 모드를 원격 자동으로 돌린 뒤 다시 승인합니다",
              "RATE_LIMIT": "1초에 너무 많은 명령이 와서 보내지 않았습니다",
              # 검사는 통과했지만 설비 쪽 MQTT 브로커가 그 명령을 받지 않음(연결 끊김) — 보내지 못한 명령을 「보냄」으로 적지 않는다(G3b-14)
              PUBLISH_CHECK: "설비 통신(MQTT)이 끊겨 명령을 설비로 보내지 못했습니다 — 설비 연결이 돌아온 뒤 다시 승인합니다"}


@dataclass
class GatewayState:
    seen_cmd_ids: deque = field(default_factory=lambda: deque(maxlen=256))
    last_status: dict = field(default_factory=dict)        # asset id -> latest plant/{a}/status payload
    per_second: dict = field(default_factory=dict)         # epoch second -> commands passed
    approvals: OrderedDict = field(default_factory=OrderedDict)   # cmdId -> process approval ledger record (A148)


class Decision(NamedTuple):
    ok: bool
    check: str            # PASS | one of CHECKS | PUBLISH_CHECK
    reason: str | None
    mqtt_payload: dict | None


def record_approval(st: GatewayState, audit_event: dict) -> str:
    """Keep process's approval ledger record from an audit-topic event. 'kept' · 'same' (that record again) · 'conflict'
    (another record for a cmdId already recorded — not kept) · 'ignored' (not a ledger record)."""
    if not isinstance(audit_event, dict) or audit_event.get("actor") != "process" or audit_event.get("event") != CMD_APPROVAL_LEDGER_EVENT:
        return "ignored"
    rec = audit_event.get("detail")
    if not isinstance(rec, dict) or not rec.get("cmdId") or not rec.get("approvalId") or not rec.get("fingerprint"):
        return "ignored"
    known = st.approvals.get(rec["cmdId"])
    if known is not None:
        return "same" if known == rec else "conflict"
    st.approvals[rec["cmdId"]] = dict(rec)
    while len(st.approvals) > APPROVALS_KEPT:
        st.approvals.popitem(last=False)
    return "kept"


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
    bad = [a["code"] for a in cmd["actions"] if a["code"] not in ACTION_WHITELIST]
    if bad:
        return Decision(False, "WHITELIST", f"action not allowed: {bad}", None)
    # ③ expiry
    try:
        exp = parse_iso(cmd["expiresAt"])
    except ValueError:
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
    # ⑥ PLC mode (from the latest retained status)
    status = st.last_status.get(cmd["asset"])
    if not status:
        return Decision(False, "MODE", f"no status seen for {cmd['asset']}", None)
    if status.get("mode") != "REMOTE_AUTO":
        return Decision(False, "MODE", f"PLC mode is {status.get('mode')} (REMOTE_AUTO required)", None)
    # ⑦ rate limit
    sec = int(now.timestamp())
    st.per_second = {k: v for k, v in st.per_second.items() if k >= sec - 5}
    if st.per_second.get(sec, 0) >= RATE_LIMIT_PER_S:
        return Decision(False, "RATE_LIMIT", f"more than {RATE_LIMIT_PER_S} commands in one second", None)

    st.per_second[sec] = st.per_second.get(sec, 0) + 1
    st.seen_cmd_ids.append(cmd["cmdId"])
    payload = {"cmdId": cmd["cmdId"], "source": "HITL", "expiresAt": cmd["expiresAt"],
               "writes": actions_to_writes(cmd["actions"])}
    return Decision(True, "PASS", None, payload)


class AlertBoard:
    """Per asset, the alerts raised and not yet cleared (alertId -> pattern · name · severity · since)."""

    def __init__(self):
        self.active: dict[str, dict] = {}

    def apply(self, alert: dict) -> dict:
        """One checked alerts-topic record (hydcommon.schemas.alert_record) -> that asset's new display."""
        items = self.active.setdefault(alert["asset"], {})
        if alert["state"] == "RAISE":
            items[alert["alertId"]] = {"alertId": alert["alertId"], "pattern": alert["pattern"], "name": alert.get("name"),
                                       "severity": alert["severity"], "since": alert["t"]}
        else:
            items.pop(alert["alertId"], None)
        return self.display(alert["asset"], last=alert)

    def display(self, asset: str, last: dict | None = None) -> dict:
        """plant/{a}/alert (retained): level 2 while any alert is active, else 0 (FUXA semaphore); display_text names them."""
        items = sorted(self.active.get(asset, {}).values(), key=lambda i: i["since"])
        names = [i["name"] or i["pattern"] for i in items]
        text = f"경보 {len(items)}건 · " + ", ".join(names) if items else "경보 없음"
        return {"level": 2 if items else 0, "count": len(items), "active": items, "display_text": text,
                "last": None if last is None else {k: last.get(k) for k in ("alertId", "pattern", "name", "state", "t")}}

    def restore(self, asset: str, retained: dict) -> bool:
        """After a gateway restart the retained display is the only memory of the active alerts: load it once per asset
        (only when nothing is known for that asset yet — a live alert always wins)."""
        if asset in self.active or not isinstance(retained, dict) or not isinstance(retained.get("active"), list):
            return False
        loaded = {}
        for item in retained["active"]:
            if not isinstance(item, dict) or not isinstance(item.get("alertId"), str) or not isinstance(item.get("since"), str):
                return False
            loaded[item["alertId"]] = {k: item.get(k) for k in ("alertId", "pattern", "name", "severity", "since")}
        self.active[asset] = loaded
        return True
