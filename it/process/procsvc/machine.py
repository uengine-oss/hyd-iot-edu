"""Incident state machine (L9, pure logic). IO happens through the Effects interface so it can be unit-tested.

v3 section 9 sequence: approve → action.cmd (expiresAt = +120 s) → ACK within 30 s → re-observe 15 min (÷ TIME_SCALE)
→ CLEAR and TS1 < 55 → work order → close.  Failures escalate; the process never retries a command.
"""
from dataclasses import dataclass, field
from datetime import datetime
import itertools
import secrets

from hydcommon.timeutil import now_iso, plus_seconds, to_iso
from . import definition as d

_cmd_seq = itertools.count(1)
_inc_seq = itertools.count(1)


def new_incident_id(now: datetime | None = None) -> str:
    """INC-MMDD-NN plus a random suffix: unique across container restarts (the id keys audit rows and the ontology Incident node)."""
    now = now or datetime.now()
    return f"INC-{now.strftime('%m%d')}-{next(_inc_seq):02d}-{secrets.token_hex(2)}"


class Effects:
    def emit_cmd(self, cmd: dict) -> None: ...
    def emit_audit(self, evt: dict) -> None: ...
    def set_timer(self, name: str, seconds: float) -> None: ...


@dataclass
class Incident:
    id: str
    asset: str
    alert_id: str
    card: dict
    state: str = "GUIDE_RECEIVED"
    reason: str | None = None
    history: list[dict] = field(default_factory=list)
    cmd_id: str | None = None
    expires_at: str | None = None
    approved_by: str | None = None
    actions: list[dict] = field(default_factory=list)
    ack: dict | None = None
    cleared: bool = False
    work_order: dict | None = None
    reobs_extensions: int = 0
    created: str = field(default_factory=now_iso)
    closed: str | None = None

    @classmethod
    def from_card(cls, incident_id: str, card: dict) -> "Incident":
        alert = card.get("alert") or {}
        card = dict(card, incident=incident_id)
        return cls(id=incident_id, asset=alert.get("asset", "?"), alert_id=alert.get("alertId", "?"), card=card)

    def to_dict(self) -> dict:
        return {"id": self.id, "asset": self.asset, "alertId": self.alert_id, "state": self.state, "reason": self.reason,
                "history": self.history, "cmdId": self.cmd_id, "expiresAt": self.expires_at, "approvedBy": self.approved_by,
                "actions": self.actions, "ack": self.ack, "cleared": self.cleared, "workOrder": self.work_order,
                "reobsExtensions": self.reobs_extensions,
                "created": self.created, "closed": self.closed, "card": self.card, "terminal": self.state in d.TERMINAL}


def _go(inc: Incident, state: str, note: str | None = None) -> None:
    inc.state = state
    inc.history.append({"state": state, "t": now_iso(), "note": note})
    if state in d.TERMINAL:
        inc.closed = now_iso()


def _audit(inc: Incident, fx: Effects, actor: str, event: str, detail: dict | None = None) -> None:
    fx.emit_audit({"t": now_iso(), "incident": inc.id, "asset": inc.asset, "actor": actor, "event": event, "detail": detail or {}})


# ---------------------------------------------------------------- transitions
def on_card(inc: Incident) -> None:
    inc.history.append({"state": "GUIDE_RECEIVED", "t": now_iso(), "note": f"alert {inc.alert_id}"})
    _go(inc, "AWAITING_APPROVAL")


def _validate_actions(inc: Incident, actions: list[dict]) -> list[dict]:
    """Every approved action must exist on the card with its value inside the ontology paramRange."""
    by_code = {a["code"]: a for a in inc.card.get("recommended") or []}
    out = []
    for a in actions:
        rec = by_code.get(a.get("code"))
        if not rec:
            raise ValueError(f"action {a.get('code')} is not on the guide card")
        if rec.get("kind") != "command":
            continue
        param, rng = rec.get("param"), rec.get("paramRange")
        val = a.get(param)
        if val is None:
            raise ValueError(f"action {a['code']} needs parameter {param}")
        if rng and not (rng[0] <= float(val) <= rng[1]):
            raise ValueError(f"{param}={val} outside paramRange {rng} for {a['code']}")
        out.append({"code": a["code"], param: val})
    if not out:
        raise ValueError("no command action to approve")
    return out


def on_approve(inc: Incident, approved_by: str, actions: list[dict], now: datetime, fx: Effects, time_scale: float = 20.0) -> dict:
    if inc.state != "AWAITING_APPROVAL":
        raise ValueError(f"cannot approve in state {inc.state}")
    acts = _validate_actions(inc, actions)
    inc.approved_by, inc.actions = approved_by, acts
    # v3 form CMD-MMDD-NNNN plus a random suffix: the gateway and PLC de-duplicate on cmdId, and an in-memory
    # counter restarts with the container, so a bare sequence number would be rejected as DUPLICATE after a restart.
    inc.cmd_id = f"CMD-{now.strftime('%m%d')}-{next(_cmd_seq):04d}-{secrets.token_hex(2)}"
    inc.expires_at = to_iso(plus_seconds(now, d.CMD_EXPIRY_S))
    cmd = {"cmdId": inc.cmd_id, "asset": inc.asset, "incident": inc.id, "source": "HITL", "actions": acts,
           "approvedBy": approved_by, "issuedAt": to_iso(now), "expiresAt": inc.expires_at}
    _audit(inc, fx, "operator", "GUIDE_APPROVED", {"approvedBy": approved_by, "actions": acts})
    _go(inc, "CMD_ISSUED", inc.cmd_id)
    fx.emit_cmd(cmd)
    _audit(inc, fx, "process", "CMD_PUBLISHED", {"cmdId": inc.cmd_id, "expiresAt": inc.expires_at})
    _go(inc, "AWAITING_ACK")
    fx.set_timer("ack", d.ACK_TIMEOUT_S)
    return cmd


def on_reject(inc: Incident, by: str, reason: str, fx: Effects) -> None:
    if inc.state != "AWAITING_APPROVAL":
        raise ValueError(f"cannot reject in state {inc.state}")
    inc.reason = reason
    _audit(inc, fx, "operator", "GUIDE_REJECTED", {"by": by, "reason": reason})
    _go(inc, "REJECTED_BY_OPERATOR", reason)


def on_status(inc: Incident, status: dict, now: datetime, fx: Effects, time_scale: float = 20.0) -> None:
    """plant.status carries the PLC ACK as cmdId/result. Only the incident's own cmdId counts (stale/retained ids are ignored)."""
    if inc.state != "AWAITING_ACK" or not inc.cmd_id or status.get("cmdId") != inc.cmd_id:
        return
    result = status.get("result")
    if result not in ("DONE", "REJECTED"):
        return
    inc.ack = {"result": result, "reason": status.get("reason"), "interlock": status.get("interlock"), "t": status.get("t")}
    if result == "DONE":
        _audit(inc, fx, "plc", "ACK_DONE", {"cmdId": inc.cmd_id})
        _go(inc, "ACKED")
        secs = d.REOBSERVE_SIM_S / max(1.0, time_scale)
        _go(inc, "RE_OBSERVING", f"{d.REOBSERVE_SIM_S} sim-s = {secs:.0f} s")
        fx.set_timer("reobs", secs)
    else:
        inc.reason = f"PLC REJECTED: {status.get('reason')}"
        _audit(inc, fx, "plc", "ACK_REJECTED", {"cmdId": inc.cmd_id, "reason": status.get("reason")})
        _go(inc, "ESCALATED", inc.reason)


def on_alert(inc: Incident, alert: dict, fx: Effects) -> None:
    if alert.get("alertId") != inc.alert_id or alert.get("state") != "CLEAR":
        return
    inc.cleared = True
    _audit(inc, fx, "detector", "ALERT_CLEARED", {"alertId": inc.alert_id})
    if inc.state == "AWAITING_APPROVAL":
        _go(inc, "RESOLVED_WITHOUT_ACTION", "cleared before any action")


def on_timer(inc: Incident, name: str, now: datetime, latest_ts1: float | None, fx: Effects, time_scale: float = 20.0) -> None:
    if name == "ack" and inc.state == "AWAITING_ACK":
        inc.reason = "ACK_TIMEOUT"
        _audit(inc, fx, "process", "ACK_TIMEOUT", {"cmdId": inc.cmd_id})
        _go(inc, "ESCALATED", "no ACK within 30 s")
    elif name == "reobs" and inc.state == "RE_OBSERVING":
        cool = latest_ts1 is not None and latest_ts1 < d.REOBSERVE_TS1_MAX
        ok = inc.cleared and cool
        if not ok and cool and inc.reobs_extensions < d.REOBSERVE_MAX_EXTENSIONS:
            # temperature is already under the limit but the detector's CLEAR (52 C held 60 s) has not landed yet:
            # give it one more third of the window instead of escalating a recovery that is visibly under way
            inc.reobs_extensions += 1
            secs = d.REOBSERVE_SIM_S / max(1.0, time_scale) / 3
            _audit(inc, fx, "process", "REOBSERVATION_EXTENDED", {"ts1": latest_ts1, "cleared": inc.cleared, "extension": inc.reobs_extensions, "seconds": round(secs, 1)})
            fx.set_timer("reobs", secs)
            return
        _audit(inc, fx, "process", "REOBSERVATION", {"cleared": inc.cleared, "ts1": latest_ts1, "passed": ok, "extensions": inc.reobs_extensions})
        if not ok:
            inc.reason = "MITIGATION_FAILED"
            _go(inc, "ESCALATED", f"cleared={inc.cleared} ts1={latest_ts1}")
            return
        _go(inc, "RESOLVED", f"TS1 {latest_ts1} < {d.REOBSERVE_TS1_MAX}")
        wo = next((a for a in inc.card.get("recommended") or [] if a.get("kind") == "work_order"), None)
        if wo:
            inc.work_order = {"id": f"WO-{inc.id}", "code": wo["code"], "name": wo.get("name"), "actionId": wo.get("actionId"),
                              "sop": (wo.get("sop") or {}).get("id"), "t": now_iso()}
            _audit(inc, fx, "process", "WORK_ORDER_CREATED", inc.work_order)
        _go(inc, "WORK_ORDER_CREATED", inc.work_order["id"] if inc.work_order else "no work order on card")
        _audit(inc, fx, "process", "INCIDENT_CLOSED", {"cmdId": inc.cmd_id, "workOrder": inc.work_order})
        _go(inc, "CLOSED")
