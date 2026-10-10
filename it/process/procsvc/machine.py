"""Incident state machine (L9, pure logic). IO happens through the Effects interface so it can be unit-tested.

v3 section 9 sequence: approve → action.cmd (expiresAt = +120 s) → ACK within 30 s → re-observe 15 min (÷ TIME_SCALE)
→ CLEAR and the pattern's recovery criterion (definition.RECOVERY: TS1 < 55 · PS1 >= 165 · VS1 < 1.2) → work order → close.
Failures escalate; the process never retries a command.
"""
from dataclasses import dataclass, field
from copy import deepcopy
from datetime import datetime
import functools
import itertools
import secrets
import threading

from hydcommon import schemas
from hydcommon.timeutil import now_iso, plus_seconds, to_iso
from . import definition as d

_cmd_seq = itertools.count(1)
_inc_seq = itertools.count(1)

# A143 (remaining-sweep 13): Incidents and decisions are mutated on the event-loop thread (legacy handlers, timers) and on
# executor threads (instance-mode hooks, approval delivery), and store.save() snapshots them from either side. Every
# transition below and every snapshot capture (store.Store.save) holds this lock, so a snapshot never contains a state
# that disagrees with its own history and a decision is never captured between clear() and update(). Re-entrant: a
# transition's Effects may persist (emit_cmd → persist → save). Nothing blocking (network, DB) runs under it — the
# callers do their I/O before or after the transition (timer: latest_tag before on_timer; enterprise: exec_skill before
# record_execution / on_work_order).
STATE_LOCK = threading.RLock()


def _transition(fn):
    @functools.wraps(fn)
    def locked(*args, **kwargs):
        with STATE_LOCK:
            return fn(*args, **kwargs)
    return locked


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
    approval_id: str | None = None      # A148: the approval ledger record id the gateway matches the command against
    expires_at: str | None = None
    approved_by: str | None = None
    actions: list[dict] = field(default_factory=list)
    ack: dict | None = None
    cleared: bool = False
    work_order: dict | None = None
    work_order_request: dict | None = None
    reobs_extensions: int = 0
    created: str = field(default_factory=now_iso)
    closed: str | None = None
    recovery_policy: dict | None = None
    superseded: list[dict] = field(default_factory=list)   # commands/work orders of generations retired by rework (A072)
    reobs_series: dict | None = None    # A161-G3: the recovery tag's sampled values during the re-observation window (reobs_series.py)

    @property
    def pattern(self) -> str | None:
        return ((self.card or {}).get("alert") or {}).get("pattern")

    @property
    def recovery(self) -> tuple[str, str, float] | None:
        """(tag, op, limit) the re-observation reads for this incident's alert pattern."""
        if self.recovery_policy is not None:
            if self.recovery_policy.get('pattern') != self.pattern:
                return None
            criterion=self.recovery_policy.get('criterion')
            return tuple(criterion) if criterion else None
        return d.recovery_for(self.pattern)

    @classmethod
    def from_card(cls, incident_id: str, card: dict, recovery_policy=None) -> "Incident":
        alert = card.get("alert") or {}
        card = dict(deepcopy(card), incident=incident_id)
        if recovery_policy is None:
            recovery_policy={'pattern':alert.get('pattern'),'criterion':d.recovery_for(alert.get('pattern')),
                             'definition':'legacy-incident','version':'explicit-patterns-v1'}
        return cls(id=incident_id, asset=alert.get("asset", "?"), alert_id=alert.get("alertId", "?"), card=card,
                   recovery_policy=deepcopy(recovery_policy))

    def to_dict(self) -> dict:
        return {"id": self.id, "asset": self.asset, "alertId": self.alert_id, "state": self.state, "reason": self.reason,
                "history": self.history, "cmdId": self.cmd_id, "approvalId": self.approval_id, "expiresAt": self.expires_at, "approvedBy": self.approved_by,
                "actions": self.actions, "ack": self.ack, "cleared": self.cleared, "workOrder": self.work_order,
                "workOrderRequest": self.work_order_request,
                "reobsExtensions": self.reobs_extensions,
                "recoveryPolicy": self.recovery_policy, "superseded": self.superseded, "reobsSeries": self.reobs_series,
                "created": self.created, "closed": self.closed, "card": self.card, "terminal": self.state in d.TERMINAL}


def _go(inc: Incident, state: str, note: str | None = None) -> None:
    inc.state = state
    inc.history.append({"state": state, "t": now_iso(), "note": note})
    if state in d.TERMINAL:
        inc.closed = now_iso()


def _audit(inc: Incident, fx: Effects, actor: str, event: str, detail: dict | None = None) -> None:
    fx.emit_audit({"t": now_iso(), "incident": inc.id, "asset": inc.asset, "actor": actor, "event": event, "detail": detail or {}})


# ---------------------------------------------------------------- transitions
@_transition
def on_card(inc: Incident) -> None:
    inc.history.append({"state": "GUIDE_RECEIVED", "t": now_iso(), "note": f"alert {inc.alert_id}"})
    if inc.recovery is None:
        inc.reason='UNSUPPORTED_ALERT_PATTERN'
        _go(inc,'ESCALATED',inc.reason)
    else:
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
        if not param:                       # e.g. RESET: a command without a parameter
            out.append({"code": a["code"]})
            continue
        val = a.get(param)
        if val is None:
            raise ValueError(f"action {a['code']} needs parameter {param}")
        if rng and not (rng[0] <= float(val) <= rng[1]):
            raise ValueError(f"{param}={val} outside paramRange {rng} for {a['code']}")
        out.append({"code": a["code"], param: val})
    if not out:
        raise ValueError("no command action to approve")
    return out


@_transition
def on_approve(inc: Incident, approved_by: str, actions: list[dict], now: datetime, fx: Effects, time_scale: float = 20.0) -> dict:
    if inc.state != "AWAITING_APPROVAL":
        raise ValueError(f"cannot approve in state {inc.state}")
    if inc.recovery is None:
        raise ValueError('이 경보에 명시된 회복 기준이 없습니다. 사람 검토가 필요합니다')
    acts = _validate_actions(inc, actions)
    inc.approved_by, inc.actions = approved_by, acts
    # v3 form CMD-MMDD-NNNN plus a random suffix: the gateway and PLC de-duplicate on cmdId, and an in-memory
    # counter restarts with the container, so a bare sequence number would be rejected as DUPLICATE after a restart.
    inc.cmd_id = f"CMD-{now.strftime('%m%d')}-{next(_cmd_seq):04d}-{secrets.token_hex(2)}"
    inc.approval_id = f"APR-{now.strftime('%m%d')}-{secrets.token_hex(4)}"
    inc.expires_at = to_iso(plus_seconds(now, d.CMD_EXPIRY_S))
    cmd = {"cmdId": inc.cmd_id, "asset": inc.asset, "incident": inc.id, "source": "HITL", "actions": acts,
           "approvedBy": approved_by, "approvalId": inc.approval_id, "issuedAt": to_iso(now), "expiresAt": inc.expires_at}
    _audit(inc, fx, "operator", "GUIDE_APPROVED", {"approvedBy": approved_by, "actions": acts})
    _go(inc, "CMD_ISSUED", inc.cmd_id)
    # A148: the approval ledger record goes out on the audit topic *before* the command — cmd-gateway forwards only a
    # command whose cmdId has this record and whose fingerprint (HMAC over the approved fields) matches it.
    _audit(inc, fx, "process", schemas.CMD_APPROVAL_LEDGER_EVENT, schemas.approval_ledger_record(cmd))
    fx.emit_cmd(cmd)
    _audit(inc, fx, "process", "CMD_PUBLISHED", {"cmdId": inc.cmd_id, "expiresAt": inc.expires_at})
    _go(inc, "AWAITING_ACK")
    fx.set_timer("ack", d.ACK_TIMEOUT_S)
    return cmd


REOPENABLE = {"AWAITING_APPROVAL", "ACKED", "RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED", "ESCALATED"}


@_transition
def on_rework_reopen(inc: Incident, request_id: str, by: str, role: str, reason: str, effects: dict, fx: Effects) -> bool:
    """A rework retired the generation that issued this incident's command. Nothing is sent to the PLC: the command,
    its ACK and any work order move to `superseded` and the incident waits for the next generation's approval.
    Idempotent per request id. AWAITING_ACK (command in flight) and CLOSED are refused."""
    if any(h.get("note") == f"reopened for rework {request_id}" for h in inc.history):
        return False
    if inc.state not in REOPENABLE:
        raise ValueError(f"cannot reopen incident for rework in state {inc.state}")
    inc.superseded.append({"request_id": request_id, "state_before": inc.state, "cmdId": inc.cmd_id, "actions": inc.actions,
                           "ack": inc.ack, "expiresAt": inc.expires_at, "approvedBy": inc.approved_by, "workOrder": inc.work_order,
                           "workOrderRequest": inc.work_order_request, "reason_before": inc.reason, "effects": effects,
                           "by": by, "role": role, "reason": reason, "t": now_iso()})
    inc.cmd_id, inc.expires_at, inc.approved_by, inc.actions, inc.ack = None, None, None, [], None
    inc.work_order, inc.work_order_request, inc.reobs_extensions, inc.reason, inc.closed = None, None, 0, None, None
    _audit(inc, fx, "operator", "INCIDENT_REOPENED", {"request_id": request_id, "by": by, "role": role, "reason": reason,
                                                       "superseded": inc.superseded[-1]["cmdId"], "effects": effects})
    _go(inc, "AWAITING_APPROVAL", f"reopened for rework {request_id}")
    return True


@_transition
def on_recheck_reopen(inc: Incident, request_id: str, by: str, reason: str, fx: Effects) -> bool:
    """B7: a work-order-only case (no PLC command ever issued) closed on its CMMS receipt, but the flow's later check — a
    person's re-analysis after the maintenance — went back to a new judgment and approval. The closed work order moves to
    `superseded` (kept, never undone) and the Incident waits for the next approval. Only that closure may reopen: a case
    that issued a command, or ended any other way (escalated · rejected · cleared), is not reopened here. Idempotent per
    request id (the re-entered work item)."""
    if any(h.get("note") == f"reopened for recheck {request_id}" for h in inc.history):
        return False
    if inc.state != "CLOSED" or inc.cmd_id or not inc.work_order or inc.recovery is None:
        raise ValueError(f"재분석 뒤 다시 판단은 설비 명령 없이 작업지시로 닫힌 사건만 엽니다 (지금 {inc.state}, 명령 {inc.cmd_id or '없음'})")
    inc.superseded.append({"request_id": request_id, "kind": "recheck", "state_before": inc.state, "cmdId": None, "actions": inc.actions,
                           "ack": None, "approvedBy": inc.approved_by, "workOrder": inc.work_order,
                           "workOrderRequest": inc.work_order_request, "reason_before": inc.reason, "closed_before": inc.closed,
                           "by": by, "reason": reason, "t": now_iso()})
    inc.approved_by, inc.actions, inc.work_order, inc.work_order_request = None, [], None, None
    inc.reason, inc.closed = None, None
    _audit(inc, fx, "operator", "INCIDENT_REOPENED", {"request_id": request_id, "by": by, "reason": reason, "kind": "recheck",
                                                       "superseded_work_order": (inc.superseded[-1]["workOrder"] or {}).get("id")})
    _go(inc, "AWAITING_APPROVAL", f"reopened for recheck {request_id}")
    return True


@_transition
def on_reject(inc: Incident, by: str, reason: str, fx: Effects) -> None:
    if inc.state != "AWAITING_APPROVAL":
        raise ValueError(f"cannot reject in state {inc.state}")
    inc.reason = reason
    _audit(inc, fx, "operator", "GUIDE_REJECTED", {"by": by, "reason": reason})
    _go(inc, "REJECTED_BY_OPERATOR", reason)


@_transition
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


@_transition
def on_alert(inc: Incident, alert: dict, fx: Effects) -> None:
    if alert.get("alertId") != inc.alert_id or alert.get("state") != "CLEAR":
        return
    inc.cleared = True
    _audit(inc, fx, "detector", "ALERT_CLEARED", {"alertId": inc.alert_id})
    if inc.state == "AWAITING_APPROVAL":
        if inc.recovery is None:
            inc.reason='UNSUPPORTED_ALERT_PATTERN'
            _go(inc,'ESCALATED',inc.reason)
        else:
            _go(inc, "RESOLVED_WITHOUT_ACTION", "cleared before any action")


@_transition
def on_timer(inc: Incident, name: str, now: datetime, latest_ts1: float | None, fx: Effects, time_scale: float = 20.0,
             cmd_id: str | None = None, series: dict | None = None) -> None:
    """latest_ts1: the latest value of the incident's recovery tag (inc.recovery[0]); the name is historical — for a
    cooler incident it is TS1, for a pump incident PS1, for a fan incident VS1.
    cmd_id: the command that armed this timer. A timer armed for a command that a rework has since superseded (A072) must
    not judge the next command's window; it is recorded and ignored.
    series: A161-G3 — the window's sampled values (reobs_series.build), kept on the Incident and summarised in the audit."""
    if cmd_id is not None and cmd_id != inc.cmd_id:
        _audit(inc, fx, "process", "TIMER_IGNORED", {"timer": name, "armedFor": cmd_id, "current": inc.cmd_id, "state": inc.state})
        return
    if name == "ack" and inc.state == "AWAITING_ACK":
        inc.reason = "ACK_TIMEOUT"
        _audit(inc, fx, "process", "ACK_TIMEOUT", {"cmdId": inc.cmd_id})
        _go(inc, "ESCALATED", "no ACK within 30 s")
    elif name == "reobs" and inc.state == "RE_OBSERVING":
        if inc.recovery is None:
            inc.reason='UNSUPPORTED_RECOVERY_CRITERION'
            _audit(inc,fx,'process',inc.reason,{'pattern':inc.pattern})
            _go(inc,'ESCALATED',inc.reason)
            return
        tag, op, limit = inc.recovery
        value = latest_ts1
        inside = value is not None and {'<':lambda:value<limit,'>=':lambda:value>=limit}[op]()
        ok = inc.cleared and inside
        trend = _keep_series(inc, series, extending=not ok and inside and inc.reobs_extensions < d.REOBSERVE_MAX_EXTENSIONS)
        if not ok and inside and inc.reobs_extensions < d.REOBSERVE_MAX_EXTENSIONS:
            # the value is already inside the limit but the detector's CLEAR (hysteresis line held 60 s) has not landed yet:
            # give it one more third of the window instead of escalating a recovery that is visibly under way
            inc.reobs_extensions += 1
            secs = d.REOBSERVE_SIM_S / max(1.0, time_scale) / 3
            _audit(inc, fx, "process", "REOBSERVATION_EXTENDED", {"tag": tag, "value": value, "ts1": value if tag == "TS1" else None,
                                                                  "cleared": inc.cleared, "extension": inc.reobs_extensions, "seconds": round(secs, 1),
                                                                  **trend})
            fx.set_timer("reobs", secs)
            return
        _audit(inc, fx, "process", "REOBSERVATION", {"cleared": inc.cleared, "tag": tag, "value": value, "criterion": f"{tag} {op} {limit}",
                                                     "ts1": value if tag == "TS1" else None, "passed": ok, "extensions": inc.reobs_extensions,
                                                     **trend})
        if not ok:
            inc.reason = "MITIGATION_FAILED"
            _go(inc, "ESCALATED", f"cleared={inc.cleared} {tag}={value} (criterion {tag} {op} {limit})")
            return
        _go(inc, "RESOLVED", f"{tag} {value} {op} {limit}")
        # Recovery is an observation. The CMMS service supplies an actual receipt
        # before this Incident can claim a work order and close.


def _keep_series(inc: Incident, series: dict | None, *, extending: bool) -> dict:
    """A161-G3: store the window's values on the Incident (the extension count it covers included) and return the compact
    audit summary {"series": {samples · min · max · first · last · inside_share}} — the points stay on the Incident only."""
    if not series:
        return {}
    inc.reobs_series = dict(series, extensions=inc.reobs_extensions + (1 if extending else 0))
    return {"series": {k: series.get(k) for k in ("samples", "min", "max", "first", "last", "inside_share", "from", "to", "error")
                       if k != "error" or series.get("error")}}


@_transition
def record_reobs_series(inc: Incident, series: dict | None) -> None:
    """A161-G3: the work-order re-observation (service_parts) reads its window outside on_timer; it keeps its series here."""
    if series:
        inc.reobs_series = dict(series)


@_transition
def on_work_order(inc: Incident, receipt: dict, fx: Effects, *, work_order_only: bool = False) -> None:
    ref = receipt.get('ref')
    if receipt.get('ok') is not True or not isinstance(ref, str) or not ref.strip():
        raise ValueError('CMMS success requires an actual nonempty reference')
    if inc.work_order:
        if inc.work_order.get('id') != ref:
            raise ValueError('conflicting CMMS receipt for the same Incident')
        if inc.state == 'CLOSED':
            return
    if inc.state != 'RESOLVED' and not (work_order_only and inc.state == 'AWAITING_APPROVAL'):
        raise ValueError(f'cannot record work order in state {inc.state}')
    inc.work_order = dict(receipt, id=ref, t=now_iso())
    _audit(inc, fx, 'process', 'WORK_ORDER_CREATED', inc.work_order)
    _go(inc, 'WORK_ORDER_CREATED', ref)
    _audit(inc, fx, 'process', 'INCIDENT_CLOSED', {'cmdId':inc.cmd_id, 'workOrder':inc.work_order,
                                                'work_order_only':work_order_only})
    _go(inc, 'CLOSED')



@_transition
def on_business_effect(inc: Incident, receipt: dict, fx: Effects) -> bool:
    """C2: 설비 명령 · 작업지시 없이 업무 효과로 끝나는 처리 건(예비품 구매: 발주 → 입고 확인)의 사건 종결. 승인 대기(AWAITING_APPROVAL)에서
    효과 확인 영수증으로 닫는다. 이미 끝난 사건은 그대로 둔다(False). 명령이 나간 사건은 재관측 · 작업지시로 닫히므로 거절한다."""
    ref = receipt.get('ref')
    if receipt.get('ok') is not True or not isinstance(ref, str) or not ref.strip():
        raise ValueError('업무 효과 종결에는 실제 영수증 번호가 필요합니다')
    if inc.state in d.TERMINAL:
        return False
    if inc.state != 'AWAITING_APPROVAL' or inc.cmd_id:
        raise ValueError(f'업무 효과로 닫을 수 없는 사건 상태입니다: {inc.state}')
    _audit(inc, fx, 'process', 'INCIDENT_CLOSED', {'businessEffect': dict(receipt), 'cmdId': None})
    _go(inc, 'CLOSED', f"business effect {receipt.get('kind') or ''} {ref}".strip())
    return True


@_transition
def on_result_report(inc: Incident, level: str, summary: str, fx: Effects) -> bool:
    """C2: 결과 보고(svc:report)가 흐름의 끝에서 사건을 닫는다 — 정상(ok)은 CLOSED, 미달 · 지연(fail)은 ESCALATED(사람 task 없이 결과만 남김),
    반려(rejected, 캡스톤 G1 사람 승인의 반려 가지)는 on_reject 와 같은 REJECTED_BY_OPERATOR(명령 전 승인 대기 사건만).
    이미 끝난 사건 · 설비 명령이 진행 중인 사건(명령 · ACK · 재관측은 사건이 스스로 판정)은 그대로 둔다(False)."""
    if level not in ('ok', 'fail', 'rejected'):
        raise ValueError('결과 보고 등급은 ok · fail · rejected 입니다')
    if inc.state in d.TERMINAL or inc.state in ('CMD_ISSUED', 'AWAITING_ACK', 'RE_OBSERVING'):
        return False
    if level == 'rejected':
        if inc.state != 'AWAITING_APPROVAL':
            raise ValueError(f'반려 결과 보고는 승인 대기 중인 사건만 닫습니다 (사건 {inc.id} 상태 {inc.state})')
        inc.reason = summary
        _audit(inc, fx, 'process', 'GUIDE_REJECTED', {'resultReport': summary, 'level': level})
        _go(inc, 'REJECTED_BY_OPERATOR', f"result report: {summary}"[:300])
        return True
    _audit(inc, fx, 'process', 'INCIDENT_CLOSED' if level == 'ok' else 'INCIDENT_ESCALATED', {'resultReport': summary, 'level': level})
    _go(inc, 'CLOSED' if level == 'ok' else 'ESCALATED', f"result report: {summary}"[:300])
    return True
