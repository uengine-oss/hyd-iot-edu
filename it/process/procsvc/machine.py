"""Incident state machine (L9, pure logic). IO happens through the Effects interface so it can be unit-tested.

v3 section 9 sequence: approve → action.cmd (expiresAt = +120 s) → ACK within 30 s → re-observe 15 min (÷ TIME_SCALE)
→ CLEAR and the pattern's recovery criterion → work order → close. Failures escalate; the process never retries a command.

시한은 여기서 재지 않는다(메모리 타이머 없음). ACK 마감(ack_due_at)은 사건에 적고, 명령 단계 작업 행이 그 시각을 저장해 폴링이
판정한다(on_ack_timeout). 재관측 창 · 연장 · 판정 규칙은 재관측 단계 하나(service_parts._reobserve)가 갖고, 이 기계는 그 판정을
사건에 적기만 한다(on_reobservation). 그래서 process 가 다시 켜져도 재관측은 저장한 마감으로 이어진다.
"""
from hydcommon.words import particle
from dataclasses import dataclass, field
from copy import deepcopy
from datetime import datetime
import functools
import itertools
import secrets
import threading

from hydcommon.timeutil import now_iso, plus_seconds, to_iso
from . import definition as d

_cmd_seq = itertools.count(1)
_inc_seq = itertools.count(1)

# A143 (remaining-sweep 13): Incidents and decisions are mutated on the event-loop thread (legacy handlers, timers) and on
# executor threads (instance-mode hooks, approval delivery), and store.save() snapshots them from either side. Every
# transition below and every snapshot capture (store.Store.save) holds this lock, so a snapshot never contains a state
# that disagrees with its own history and a decision is never captured between clear() and update(). Re-entrant: a
# transition's Effects may persist. Nothing blocking (network, DB) runs under it — the callers do their I/O before or
# after the transition (command: Kafka between on_approve and on_command_sent; re-observation: tag reads before
# on_reobservation; enterprise: exec_skill before record_execution / on_work_order).
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
    def emit_audit(self, evt: dict) -> None: ...


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
    ack_due_at: str | None = None       # 명령을 보낸 뒤 ACK 를 기다리는 마감(벽시계, definition.ACK_TIMEOUT_S) — 명령 단계 행이 이 시각을 저장한다
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
    outside_at_open: dict | None = None  # 사건이 열릴 때 그 설비의 바깥 변화 기록(plant.status outside) — outside_change 가 이것과 견준다

    @property
    def pattern(self) -> str | None:
        return ((self.card or {}).get("alert") or {}).get("pattern")

    @property
    def recovery(self) -> tuple[str, str, float] | None:
        """(tag, op, limit) the re-observation reads for this incident's alert pattern — 사건을 연 흐름의 경보 정책(alertPolicy)이 정한
        기준 하나(코드 상수로 대신하지 않는다 — P1-20). 정책의 패턴이 다르거나 기준이 없으면 None(재관측으로 판정할 기준이 없다)."""
        policy = self.recovery_policy or {}
        if policy.get('pattern') != self.pattern:
            return None
        criterion = policy.get('criterion')
        return tuple(criterion) if criterion else None

    @property
    def supported(self) -> bool:
        """이 사건을 연 흐름이 이 경보 종류를 받는가(경보 정책의 response 길). 시계열 회복 기준(recovery)은 선택이다 — 없으면 회복은 원천의
        해제뿐이고(alert_policy 머리말), 그래도 받는 경보다. 받지 않는 경보(triage)의 사건은 처음부터 현장 검토다."""
        policy = self.recovery_policy or {}
        return policy.get('pattern') == self.pattern and policy.get('route') == 'response'

    @classmethod
    def from_card(cls, incident_id: str, card: dict, recovery_policy: dict) -> "Incident":
        """경보 하나의 사건. recovery_policy = 그 경보를 받은 흐름의 경보 정책(alert_policy.for_definition) — 없으면 만들지 않는다."""
        alert = card.get("alert") or {}
        card = dict(deepcopy(card), incident=incident_id)
        if not isinstance(recovery_policy, dict) or 'criterion' not in recovery_policy:
            raise ValueError(f"사건 {incident_id}: 경보 정책(회복 기준)이 없는 사건은 만들지 않습니다 — 경보는 경보 정책이 있는 흐름으로만 엽니다")
        return cls(id=incident_id, asset=alert.get("asset", "?"), alert_id=alert.get("alertId", "?"), card=card,
                   recovery_policy=deepcopy(recovery_policy))

    def to_dict(self) -> dict:
        # pattern: 이 사건을 연 경보의 종류(이상 패턴 코드) — 목록 응답은 card 를 싣지 않으므로(크다) 화면이 이름을 쓰려면 이 칸이 있어야 한다
        return {"id": self.id, "asset": self.asset, "alertId": self.alert_id, "pattern": self.pattern, "state": self.state, "reason": self.reason,
                "history": self.history, "cmdId": self.cmd_id, "approvalId": self.approval_id, "expiresAt": self.expires_at,
                "ackDueAt": self.ack_due_at, "approvedBy": self.approved_by,
                "actions": self.actions, "ack": self.ack, "cleared": self.cleared, "workOrder": self.work_order,
                "workOrderRequest": self.work_order_request,
                "reobsExtensions": self.reobs_extensions,
                "recoveryPolicy": self.recovery_policy, "superseded": self.superseded, "reobsSeries": self.reobs_series,
                "created": self.created, "closed": self.closed, "card": self.card, "terminal": self.state in d.TERMINAL}


def _go(inc: Incident, state: str, note: str | None = None, reobservation: dict | None = None) -> None:
    """사건 이력 한 줄. reobservation = 재관측 시작 · 판정의 칸(화면이 문장에서 뽑지 않게): tag · op · limit · sim_s, 판정이면 value(못 읽었으면
    None) · cleared · recovered · extensions."""
    inc.state = state
    entry = {"state": state, "t": now_iso(), "note": note}
    if reobservation is not None:
        entry["reobservation"] = dict(reobservation)
    inc.history.append(entry)
    if state in d.TERMINAL:
        inc.closed = now_iso()


def _audit(inc: Incident, fx: Effects, actor: str, event: str, detail: dict | None = None) -> None:
    fx.emit_audit({"t": now_iso(), "incident": inc.id, "asset": inc.asset, "actor": actor, "event": event, "detail": detail or {}})


# ---------------------------------------------------------------- transitions
@_transition
def on_card(inc: Incident) -> None:
    inc.history.append({"state": "GUIDE_RECEIVED", "t": now_iso(), "note": f"alert {inc.alert_id}"})
    if not inc.supported:
        inc.reason='UNSUPPORTED_ALERT_PATTERN'
        _go(inc,'ESCALATED',inc.reason)
    else:
        _go(inc, "AWAITING_APPROVAL")


def _validate_actions(option: dict, actions: list[dict]) -> list[dict]:
    """승인한 명령마다 승인한 판단 카드(조치 방법 한 장 — decisions 의 option)의 설비 명령이고, 값이 그 조치의 온톨로지 범위(min · max)
    안이어야 한다. 기준은 판단 카드 하나다 — 가이드 카드는 원인 · 근거와 조치 방법 목록까지라 명령을 싣지 않는다(검진 G1-04, 한바퀴3 고침 1)."""
    name = f"{option.get('sopId') or option.get('id')} {option.get('name') or ''}".strip()
    by_code = {a["code"]: a for a in option.get("actions") or [] if a.get("kind") == "command" and a.get("code")}
    out = []
    for a in actions:
        rec = by_code.get(a.get("code"))
        if not rec:
            raise ValueError(f"승인한 조치 「{name}」에 없는 설비 명령({a.get('code')})은 보낼 수 없습니다 — 처리 건 화면을 새로 고쳐 조치 후보를 다시 고르세요")
        param = rec.get("param")
        if not param:                       # e.g. RESET: a command without a parameter
            out.append({"code": a["code"]})
            continue
        val = a.get(param)
        if val is None:
            raise ValueError(f"설비 명령 「{rec.get('name') or a['code']}」에 값이 없습니다 — 조치 후보의 조치값을 확인하세요")
        lo, hi = rec.get("min"), rec.get("max")
        if lo is not None and hi is not None and not (lo <= float(val) <= hi):
            raise ValueError(f"설비 명령 「{rec.get('name') or a['code']}」의 값 {val}{particle(val, '이')} 허용 범위 {lo}~{hi} 밖입니다")
        out.append({"code": a["code"], param: val})
    if not out:
        raise ValueError(f"승인한 조치 「{name}」에는 보낼 설비 명령이 없습니다")
    return out


@_transition
def on_approve(inc: Incident, approved_by: str, option: dict, actions: list[dict], now: datetime, fx: Effects) -> dict:
    """승인한 판단 카드(option)의 명령을 사건에 적고(CMD_ISSUED) 보낼 action.cmd 를 돌려준다. 보내는 일은 호출자가 이 전이 밖에서 한다 — 승인 원장 송신이
    확인된 뒤에 명령을 보내고(A148: cmd-gateway 는 원장 기록이 있는 명령만 넘긴다), 결과를 on_command_sent / on_command_send_failed 로 적는다."""
    if inc.state != "AWAITING_APPROVAL":
        raise ValueError(f"cannot approve in state {inc.state}")
    if inc.recovery is None:
        raise ValueError('이 경보에 명시된 회복 기준이 없습니다. 사람 검토가 필요합니다')
    acts = _validate_actions(option, actions)
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
    return cmd


@_transition
def on_flow_approved(inc: Incident, approved_by: str, fx: Effects) -> bool:
    """사람이 승인했고 승인한 안에 이 흐름이 낼 설비 명령이 없다(정비 요청만 · 발주 · 승인 뒤 MCP 호출 …) — 승인 대기를 끝내고 「승인 — 흐름이
    실행 중」(APPROVED_EXECUTING)으로 간다. 그 뒤 끝은 흐름의 업무 효과(on_work_order · on_business_effect)나 결과 보고(on_result_report)가 정한다.
    전에는 이런 사건이 닫힐 때까지 승인 대기로 남아, 승인 뒤 몇 분 동안 사건 목록 · 해제 응답이 승인 전이라고 말했고 승인 전에만 여는 문(판단 접수 ·
    원인 진단 바꾸기)이 열려 있었다. 승인 대기가 아닌 사건(이미 이 상태 — 같은 승인 단계를 다시 처리 · 끝난 사건)은 그대로 둔다(False)."""
    if inc.state != "AWAITING_APPROVAL":
        return False
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise ValueError(f"사건 {inc.id}: 승인한 사람 기록이 없는 승인은 적지 않습니다")
    inc.approved_by = approved_by
    _audit(inc, fx, "operator", "GUIDE_APPROVED", {"approvedBy": approved_by, "actions": []})
    _go(inc, "APPROVED_EXECUTING", "사람 승인 — 설비 명령 없이 흐름이 실행")
    return True


@_transition
def on_command_sent(inc: Incident, cmd_id: str, now: datetime, fx: Effects) -> None:
    """원장과 명령이 Kafka 에 실린 것을 확인한 뒤: ACK 를 기다린다. 마감은 사건에 적고(벽시계 ACK_TIMEOUT_S) 명령 단계 행이 저장한다."""
    if inc.state != "CMD_ISSUED" or inc.cmd_id != cmd_id:
        raise ValueError(f"명령 {cmd_id}{particle(cmd_id, '을')} 보낸 사건 상태가 아닙니다 (지금 {inc.state}, 명령 {inc.cmd_id})")
    inc.ack_due_at = to_iso(plus_seconds(now, d.ACK_TIMEOUT_S))
    _audit(inc, fx, "process", "CMD_PUBLISHED", {"cmdId": inc.cmd_id, "expiresAt": inc.expires_at, "ackDueAt": inc.ack_due_at})
    _go(inc, "AWAITING_ACK")


@_transition
def on_command_send_failed(inc: Incident, cmd_id: str, error: str, fx: Effects) -> bool:
    """승인 원장이나 명령을 Kafka 에 싣지 못했다 — 설비에 닿았는지 알 수 없으므로 다시 보내지 않고 사람 검토로 넘긴다."""
    if inc.state != "CMD_ISSUED" or inc.cmd_id != cmd_id:
        return False
    inc.reason = "CMD_SEND_FAILED"
    _audit(inc, fx, "process", "CMD_SEND_FAILED", {"cmdId": cmd_id, "error": error[:500]})
    _go(inc, "ESCALATED", f"설비 명령을 명령 통로에 싣지 못함 — {error[:200]}")
    return True


#: 재작업이 다시 열 수 있는 사건 상태 — 이 표 하나(재작업 효과 판정 effect_compensation 도 이것을 쓴다, P4-10). 끝난 사건(definition.TERMINAL)과
#: 명령이 오가는 중(CMD_ISSUED · AWAITING_ACK)은 다시 열지 않는다 — 끝난 사건은 새 경보가 새 처리 건으로 다룬다.
REOPENABLE = {"AWAITING_APPROVAL", "APPROVED_EXECUTING", "ACKED", "RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED"}


@_transition
def on_rework_reopen(inc: Incident, request_id: str, by: str, role: str, reason: str, effects: dict, fx: Effects) -> bool:
    """A rework retired the generation that issued this incident's command. Nothing is sent to the PLC: the command,
    its ACK and any work order move to `superseded` and the incident waits for the next generation's approval.
    Idempotent per request id. AWAITING_ACK (command in flight) and CLOSED are refused."""
    if any(s.get("request_id") == request_id and s.get("kind") != "recheck" for s in inc.superseded):
        return False                                      # 같은 요청 id 는 한 번만(요청 id 는 superseded 기록에 남는다)
    if inc.state not in REOPENABLE:
        raise ValueError(f"cannot reopen incident for rework in state {inc.state}")
    inc.superseded.append({"request_id": request_id, "state_before": inc.state, "cmdId": inc.cmd_id, "actions": inc.actions,
                           "ack": inc.ack, "expiresAt": inc.expires_at, "approvedBy": inc.approved_by, "workOrder": inc.work_order,
                           "workOrderRequest": inc.work_order_request, "reason_before": inc.reason, "effects": effects,
                           "by": by, "role": role, "reason": reason, "t": now_iso()})
    inc.cmd_id, inc.expires_at, inc.ack_due_at, inc.approved_by, inc.actions, inc.ack = None, None, None, None, [], None
    inc.work_order, inc.work_order_request, inc.reobs_extensions, inc.reason, inc.closed = None, None, 0, None, None
    _audit(inc, fx, "operator", "INCIDENT_REOPENED", {"request_id": request_id, "by": by, "role": role, "reason": reason,
                                                       "superseded": inc.superseded[-1]["cmdId"], "effects": effects})
    _go(inc, "AWAITING_APPROVAL", f"다시 수행으로 사건을 다시 엶 — 새 판단 · 승인을 기다림 (요청 {request_id})")
    return True


@_transition
def on_recheck_reopen(inc: Incident, request_id: str, by: str, reason: str, fx: Effects) -> bool:
    """B7: a work-order-only case (no PLC command ever issued) closed on its CMMS receipt, but the flow's later check — a
    person's re-analysis after the maintenance — went back to a new judgment and approval. The closed work order moves to
    `superseded` (kept, never undone) and the Incident waits for the next approval. Only that closure may reopen: a case
    that issued a command, or ended any other way (escalated · rejected · cleared), is not reopened here. Idempotent per
    request id (the re-entered work item).
    설비 명령 없이 흐름이 실행 중인 사건(APPROVED_EXECUTING — 승인 뒤 MCP 호출 · 기다림 · 확인이 미달이라 흐름이 새 판단 · 승인으로 되돌아감)도 같다:
    앞 승인은 `superseded` 로 옮기고 다음 승인을 기다린다(되돌아간 뒤에도 「승인 — 실행 중」으로 남으면 새 판단 접수 · 반려가 막힌다)."""
    if any(s.get("request_id") == request_id and s.get("kind") == "recheck" for s in inc.superseded):
        return False
    closed_by_work_order = inc.state == "CLOSED" and not inc.cmd_id and bool(inc.work_order)
    if not (closed_by_work_order or inc.state == "APPROVED_EXECUTING") or not inc.supported:
        raise ValueError(f"재분석 뒤 다시 판단은 설비 명령 없이 작업지시로 닫혔거나 승인 뒤 흐름이 실행 중인 사건만 엽니다 "
                         f"(지금 {d.state_label(inc.state)}, 명령 {inc.cmd_id or '없음'})")
    inc.superseded.append({"request_id": request_id, "kind": "recheck", "state_before": inc.state, "cmdId": None, "actions": inc.actions,
                           "ack": None, "approvedBy": inc.approved_by, "workOrder": inc.work_order,
                           "workOrderRequest": inc.work_order_request, "reason_before": inc.reason, "closed_before": inc.closed,
                           "by": by, "reason": reason, "t": now_iso()})
    inc.approved_by, inc.actions, inc.work_order, inc.work_order_request = None, [], None, None
    inc.reason, inc.closed = None, None
    _audit(inc, fx, "operator", "INCIDENT_REOPENED", {"request_id": request_id, "by": by, "reason": reason, "kind": "recheck",
                                                       "superseded_work_order": (inc.superseded[-1]["workOrder"] or {}).get("id")})
    _go(inc, "AWAITING_APPROVAL", f"재분석 뒤 다시 판단 — 사건을 다시 엶 (단계 {request_id})")
    return True


@_transition
def on_reject(inc: Incident, by: str, reason: str, fx: Effects) -> None:
    if inc.state != "AWAITING_APPROVAL":
        raise ValueError(f"cannot reject in state {inc.state}")
    inc.reason = reason
    _audit(inc, fx, "operator", "GUIDE_REJECTED", {"by": by, "reason": reason})
    _go(inc, "REJECTED_BY_OPERATOR", reason)


@_transition
def on_status(inc: Incident, status: dict, now: datetime, fx: Effects) -> None:
    """plant.status carries the PLC ACK as cmdId/result. Only the incident's own cmdId counts (stale/retained ids are ignored).
    ACK DONE 이면 재관측 상태로 간다 — 창 · 판정은 재관측 단계가 저장한 마감으로 한다(service_parts._reobserve)."""
    if inc.state != "AWAITING_ACK" or not inc.cmd_id or status.get("cmdId") != inc.cmd_id:
        return
    result = status.get("result")
    if result not in ("DONE", "REJECTED"):
        return
    said = None
    if result == "REJECTED":
        # 사유 코드(MODE_MISMATCH …)는 감사 · ack 에 두고, 사람이 읽는 사유는 PLC 가 상태에 함께 싣는 문장(plc.status_payload reason_text —
        # 「운전 모드 확인 필요」)이다. 전에는 코드가 결과 보고 문장에 그대로 실렸다(「…(사유 MODE_MISMATCH)」 — 2026-11-22 F4)
        # 문장 없이 온 거절도 거절이다 — 실패로 던지면 사건이 응답 대기로 남아 뒤에 「설비 응답이 오지 않음」(ACK 시간 초과)이라는 틀린 까닭으로
        # 닫힌다(설비는 응답했다). 문장이 없다는 사실과 사유 코드를 그대로 적는다(가상 설비는 늘 문장을 싣는다 — plc.TEXT)
        said = status.get("reason_text")
        if not isinstance(said, str) or not said.strip() or said.strip() == "–":
            said = f"설비가 거절 사유 문장을 보내지 않음 — 사유 코드 {status.get('reason') or '없음'}"
        said = said.strip()
    inc.ack = {"result": result, "reason": status.get("reason"), "interlock": status.get("interlock"), "t": status.get("t"),
               **({"reason_text": said} if said else {})}
    if result == "DONE":
        _audit(inc, fx, "plc", "ACK_DONE", {"cmdId": inc.cmd_id})
        _go(inc, "ACKED")
        tag, op, limit = inc.recovery or (None, None, None)
        _go(inc, "RE_OBSERVING", f"효과 확인 시작 — 설비 시간 {d.REOBSERVE_SIM_S // 60}분 동안 지켜본다",
            reobservation={"tag": tag, "op": op, "limit": limit, "sim_s": d.REOBSERVE_SIM_S})
    else:
        inc.reason = f"PLC REJECTED: {inc.ack['reason_text']}"
        _audit(inc, fx, "plc", "ACK_REJECTED", {"cmdId": inc.cmd_id, "reason": status.get("reason"), "reason_text": inc.ack["reason_text"]})
        _go(inc, "ESCALATED", f"PLC 가 명령을 거절함 — {inc.ack['reason_text']}")


@_transition
def on_gateway_rejected(inc: Incident, cmd_id: str, check: str, text: str, fx: Effects) -> bool:
    """G3b-9: 명령 관문(cmd-gateway)이 이 사건의 명령을 설비로 넘기지 않고 거절했다(audit CMD_REJECTED — check: MODE · APPROVAL … ,
    text: 관문의 학생 문장). 실행되지 않은 것이 확실하므로 30초 응답 없음(ACK 시간 초과)을 기다리지 않고 그 까닭으로 닫는다. 다른 명령
    (재작업으로 바뀐 것)의 거절이나 이미 응답이 온 명령이면 그대로 둔다(False)."""
    if inc.state not in ("CMD_ISSUED", "AWAITING_ACK") or not inc.cmd_id or inc.cmd_id != cmd_id:
        return False
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"명령 관문의 거절 {cmd_id}에 까닭 문장이 없습니다(check {check!r})")
    inc.ack = {"result": "REJECTED", "reason": check, "rejectedBy": "cmd-gateway", "text": text}
    inc.reason = f"{d.GATEWAY_REJECTED}: {text.strip()}"
    _audit(inc, fx, "cmd-gateway", "CMD_REJECTED", {"cmdId": inc.cmd_id, "check": check})
    _go(inc, "ESCALATED", f"명령 관문이 명령을 거절함 — {text.strip()[:200]}")
    return True


def active_trip(asset: str, incidents, since: str | None = None) -> str | None:
    """그 설비가 보호 정지 중이거나, since(이 사건이 열린 시각) 뒤에 보호 정지가 있었으면 그 사유. 보호 정지는 감지기가 따로 경보(근거
    {"trip": 사유})를 올리고 PLC 가 TRIP 을 벗어날 때 같은 경보를 해제한다(detector cep.trip_alert). 사람이 보호 정지를 먼저 풀고 냉각 경보가
    나중에 풀려도 그 사이 설비가 멈춰 식은 값이다 — 회복이 아니다(독립 검증 2026-11-02). 돌려주는 사유는 그 보호 정지 경보의 이름(감지기가
    지식 지도의 패턴 이름을 싣는다 — 「과열 인터록 트립」)이고, 이름이 없는 경보(지식 지도에 없는 보호 정지 사유)만 PLC 의 사유 코드다 — 그 밖에
    아는 말이 없다. 전에는 늘 코드(OVERTEMP)가 결과 보고 문장에 실렸다."""
    for other in incidents:
        alert = (other.card or {}).get("alert") or {}
        evidence = alert.get("evidence") or {}
        if other.asset == asset and evidence.get("trip") and (not other.cleared or (since is not None and other.created >= since)):
            return str(alert.get("name") or evidence["trip"])
    return None


def outside_change(before: dict | None, now: dict | None) -> dict | None:
    """설비의 바깥 변화 기록(plant.status outside — 가상 설비가 싣는다: boot · seq · what · by · at) 둘을 견준다. before(사건이 열릴 때 ·
    효과 확인 창이 시작될 때) 뒤에 승인한 길(명령 관문을 지난 명령 · 승인 뒤 정비 복구) 밖에서 설비가 바뀌었으면 지금 기록, 아니면 None.
    한쪽이라도 기록이 없으면(그 기록을 싣지 않는 원천 — 실설비 등, 또는 사건이 열릴 때 설비 상태를 아직 받지 못함) 견줄 것이 없어 None 이다 —
    그런 설비의 수동 조작은 PLC 가 운전 모드(원격 수동 · 현장 제어)와 마지막 명령 출처로 알린다."""
    if not isinstance(before, dict) or not isinstance(now, dict):
        return None
    if (now.get("boot"), now.get("seq")) == (before.get("boot"), before.get("seq")):
        return None
    return dict(now)


def outside_words(change: dict) -> str:
    """바깥 변화 기록 → 사유 문장에 싣는 말(가상 설비의 what · 누가 · 언제)."""
    what = str(change.get("what") or change.get("kind") or "기록 없음")
    who = f" · {change['by']}" if change.get("by") else ""
    return f"{what}{who}" + (f" · {change['at']}" if change.get("at") else "")


@_transition
def on_alert(inc: Incident, alert: dict, fx: Effects, trip: str | None = None, outside: dict | None = None,
             outside_unknown: str | None = None) -> None:
    """경보 해제. trip = 같은 설비가 지금 보호 정지 중이면 그 사유(풀리지 않은 보호 정지 경보의 근거 — main._apply_source_event).
    보호 정지 중의 해제는 회복이 아니다(설비가 멈춰 값이 내려갔다) — 「조치 전 자연 회복」으로 끝내지 않고 책임자 확인으로.
    outside = 사건이 열린 뒤 설비가 승인한 길 밖에서 바뀐 기록(outside_change — [설비 초기화] · [쿨러 복구] · 현장 패널 · 가상 설비 재시작).
    그 뒤의 해제는 자연 회복이 아니다(바깥에서 설비를 되돌렸다) — 책임자 확인으로.
    outside_unknown = 해제가 난 때까지 바뀌었는지 모르는 까닭(받은 바깥 변화 기록이 끊겼다 — main.outside_at_clear). 모르면 자연 회복이라고
    단정하지 않는다 — 그 까닭으로 책임자 확인으로.
    「조치 전」은 승인 대기(AWAITING_APPROVAL)뿐이다. 사람이 승인한 뒤의 사건(APPROVED_EXECUTING · 명령이 오가는 상태)은 해제만 적고, 끝은 흐름의
    업무 효과 · 결과 보고 · 효과 확인이 정한다."""
    if alert.get("alertId") != inc.alert_id or alert.get("state") != "CLEAR":
        return
    inc.cleared = True
    _audit(inc, fx, "detector", "ALERT_CLEARED",
           {"alertId": inc.alert_id, **({"trip": trip} if trip else {}), **({"outside": outside} if outside else {}),
            **({"outside_unknown": outside_unknown} if outside_unknown else {}),
            **({"after_approval": True} if inc.state == "APPROVED_EXECUTING" else {})})
    if inc.state == "AWAITING_APPROVAL":
        if not inc.supported:
            inc.reason='UNSUPPORTED_ALERT_PATTERN'
            _go(inc,'ESCALATED',inc.reason)
        elif trip:
            inc.reason = f"{d.TRIPPED_BEFORE_ACTION}: {trip}"
            _go(inc, "ESCALATED", f"조치 전에 경보가 풀렸지만 설비가 보호 정지 중({trip})")
        elif outside:
            inc.reason = f"{d.OUTSIDE_CHANGE}: {outside_words(outside)}"
            _go(inc, "ESCALATED", f"조치 전에 경보가 풀렸지만 그 전에 설비가 승인한 조치 밖에서 바뀜({outside_words(outside)})"[:300])
        elif outside_unknown:
            inc.reason = f"{d.OUTSIDE_UNKNOWN}: {outside_unknown}"
            _go(inc, "ESCALATED", f"조치 전에 경보가 풀렸지만 그 전에 설비가 승인한 조치 밖에서 바뀌었는지 모름({outside_unknown})"[:300])
        else:
            _go(inc, "RESOLVED_WITHOUT_ACTION", "조치 전에 경보가 풀림")


@_transition
def on_ack_timeout(inc: Incident, cmd_id: str, fx: Effects) -> bool:
    """명령 단계 행이 저장한 ACK 마감이 지났는데 그 명령의 ACK 가 오지 않았다. 다른 명령(재작업으로 바뀐 것)의 마감은 무시한다."""
    if inc.state != "AWAITING_ACK" or inc.cmd_id != cmd_id:
        return False
    inc.reason = "ACK_TIMEOUT"
    _audit(inc, fx, "process", "ACK_TIMEOUT", {"cmdId": inc.cmd_id, "ackDueAt": inc.ack_due_at})
    _go(inc, "ESCALATED", f"설비 응답(ACK)이 {d.ACK_TIMEOUT_S}초 안에 오지 않음")
    return True


def _series_summary(series: dict | None) -> dict:
    """A161-G3: the compact audit summary {"series": {samples · min · max · first · last · inside_share}} — the points stay on the Incident."""
    if not series:
        return {}
    return {"series": {k: series.get(k) for k in ("samples", "min", "max", "first", "last", "inside_share", "from", "to", "error")
                       if k != "error" or series.get("error")}}


@_transition
def on_reobservation_extended(inc: Incident, cmd_id: str, reading: dict, extension: int, seconds: float, fx: Effects) -> bool:
    """재관측 단계가 창을 늘렸다(값은 기준 안, 감지기 해제 대기) — 사건에는 연장 횟수와 감사 기록만 남는다."""
    if inc.state != "RE_OBSERVING" or inc.cmd_id != cmd_id:
        return False
    inc.reobs_extensions = extension
    if reading.get("series"):
        inc.reobs_series = dict(reading["series"], extensions=extension)
    _audit(inc, fx, "process", "REOBSERVATION_EXTENDED", {
        "tag": reading.get("tag"), "value": reading.get("value"), "ts1": reading.get("value") if reading.get("tag") == "TS1" else None,
        "cleared": reading.get("cleared"), "extension": extension, "seconds": round(seconds, 1), **_series_summary(reading.get("series"))})
    return True


@_transition
def on_reobservation(inc: Incident, cmd_id: str, passed: bool, reading: dict, extensions: int, fx: Effects) -> bool:
    """재관측 단계의 판정을 사건에 적는다: 회복(기준 안 + 경보 해제)이면 RESOLVED, 아니면 ESCALATED(완화 실패). 판정 규칙은 재관측
    단계 하나가 갖는다 — 여기서는 다시 재지 않는다. 다른 명령의 창이었으면(재작업) 적지 않는다(False)."""
    if inc.state != "RE_OBSERVING" or inc.cmd_id != cmd_id:
        return False
    inc.reobs_extensions = extensions
    if reading.get("series"):
        inc.reobs_series = dict(reading["series"], extensions=extensions)
    tag, value, criterion = reading.get("tag"), reading.get("value"), reading.get("criterion")
    _audit(inc, fx, "process", "REOBSERVATION", {"cleared": reading.get("cleared"), "tag": tag, "value": value, "criterion": criterion,
                                                 "ts1": value if tag == "TS1" else None, "passed": bool(passed), "extensions": extensions,
                                                 **_series_summary(reading.get("series"))})
    fields = {"tag": tag, "op": reading.get("op"), "limit": reading.get("limit"), "value": value, "cleared": reading.get("cleared"),
              "recovered": bool(passed), "extensions": extensions, "sim_s": d.REOBSERVE_SIM_S * (1 + extensions / 3)}
    if not criterion:
        inc.reason = "UNSUPPORTED_RECOVERY_CRITERION"
        _go(inc, "ESCALATED", inc.reason, reobservation=fields)
    elif reading.get("outside"):
        # 효과 확인 창 동안(또는 사건이 열린 뒤) 설비가 승인한 조치 밖에서 바뀌었다 — 창의 값은 조치의 효과가 아니다(service_parts._reobserve)
        inc.reason = f"{d.OUTSIDE_CHANGE}: {outside_words(reading['outside'])}"
        _go(inc, "ESCALATED", f"효과를 잴 수 없음 — 설비가 승인한 조치 밖에서 바뀜({outside_words(reading['outside'])})"[:300],
            reobservation=fields)
    elif not passed:
        inc.reason = "MITIGATION_FAILED"
        _go(inc, "ESCALATED", f"회복 미달 — {tag} {value if value is not None else '값 없음'} (기준 {criterion}, "
                              f"경보 {'해제' if reading.get('cleared') else '그대로'})", reobservation=fields)
    else:
        # Recovery is an observation. The CMMS service supplies an actual receipt before this Incident can claim a work order and close.
        _go(inc, "RESOLVED", f"회복 — {tag} {value} (기준 {criterion})", reobservation=fields)
    return True


@_transition
def on_outside_after_work_order(inc: Incident, change: dict, fx: Effects) -> bool:
    """설비 명령 없이 작업지시로 닫힌 사건(on_work_order — 정비형 흐름)의 정비 뒤 효과 확인 창에서, 사건이 열린 뒤 설비가 승인한 조치 밖에서
    바뀐 것을 봤다(service_parts._reobserve). 창의 값은 정비의 효과가 아니다 — 회복 확인 없이 종결로 남기지 않고 그 까닭으로 책임자 확인으로
    바꾼다(결과 보고의 미달 보고가 같은 사건을 다시 닫지 않는다 — 이미 끝난 상태). 그런 사건이 아니면 그대로(False)."""
    if inc.state != "CLOSED" or inc.cmd_id or not inc.work_order:
        return False
    inc.reason = f"{d.OUTSIDE_CHANGE}: {outside_words(change)}"
    _audit(inc, fx, "process", "INCIDENT_ESCALATED", {"outside": change, "after": "work_order"})
    _go(inc, "ESCALATED", f"정비 뒤 효과를 잴 수 없음 — 설비가 승인한 조치 밖에서 바뀜({outside_words(change)})"[:300])
    return True


@_transition
def record_reobs_series(inc: Incident, series: dict | None) -> None:
    """A161-G3: 작업지시로 닫힌 사건의 재관측(service_parts._reobserve)은 사건 상태를 바꾸지 않는다 — 창의 값 흐름만 여기 남긴다."""
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
    if inc.state != 'RESOLVED' and not (work_order_only and inc.state == 'APPROVED_EXECUTING'):
        raise ValueError(f'cannot record work order in state {inc.state}')
    inc.work_order = dict(receipt, id=ref, t=now_iso())
    _audit(inc, fx, 'process', 'WORK_ORDER_CREATED', inc.work_order)
    _go(inc, 'WORK_ORDER_CREATED', ref)
    _audit(inc, fx, 'process', 'INCIDENT_CLOSED', {'cmdId':inc.cmd_id, 'workOrder':inc.work_order,
                                                'work_order_only':work_order_only})
    _go(inc, 'CLOSED')



@_transition
def on_business_effect(inc: Incident, receipt: dict, fx: Effects) -> bool:
    """C2: 설비 명령 · 작업지시 없이 업무 효과로 끝나는 처리 건(예비품 구매: 발주 → 입고 확인)의 사건 종결. 사람 승인 뒤 흐름이 실행 중인
    사건(APPROVED_EXECUTING)을 효과 확인 영수증으로 닫는다 — 승인 없는 사건(승인 대기)은 닫지 않는다. 이미 끝난 사건은 그대로 둔다(False).
    명령이 나간 사건은 재관측 · 작업지시로 닫히므로 거절한다."""
    ref = receipt.get('ref')
    if receipt.get('ok') is not True or not isinstance(ref, str) or not ref.strip():
        raise ValueError('업무 효과 종결에는 실제 영수증 번호가 필요합니다')
    if inc.state in d.TERMINAL:
        return False
    if inc.state != 'APPROVED_EXECUTING' or inc.cmd_id:
        raise ValueError(f'업무 효과로 닫을 수 없는 사건 상태입니다: {d.state_label(inc.state)}')
    _audit(inc, fx, 'process', 'INCIDENT_CLOSED', {'businessEffect': dict(receipt), 'cmdId': None})
    _go(inc, 'CLOSED', f"업무 처리로 종결 — {receipt.get('kind') or '영수증'} {ref}")
    return True


@_transition
def on_result_report(inc: Incident, level: str, summary: str, fx: Effects) -> bool:
    """C2: 결과 보고(svc:report)가 흐름의 끝에서 사건을 닫는다 — 정상(ok)은 CLOSED, 미달 · 지연(fail)은 ESCALATED(사람 task 없이 결과만 남김),
    반려(rejected, 캡스톤 G1 사람 승인의 반려 가지)는 on_reject 와 같은 REJECTED_BY_OPERATOR(승인 대기 사건만 — 승인 뒤 흐름이 실행 중인 사건은
    이미 승인한 것이라 반려로 닫지 않는다).
    이미 끝난 사건 · 설비 명령이 진행 중인 사건(명령 · ACK · 재관측은 사건이 스스로 판정)은 그대로 둔다(False)."""
    if level not in ('ok', 'fail', 'rejected'):
        raise ValueError('결과 보고 등급은 ok · fail · rejected 입니다')
    if level == 'fail' and inc.state == 'CLOSED' and not inc.cmd_id and inc.work_order:
        # 설비 명령 없이 작업지시로 닫힌 사건(on_work_order — 업무 처리로 종결)인데 흐름이 정비 뒤 재관측에서 회복하지 않아 미달로 보고했다
        # (흐름 A 작업지시만 갈래, 메인 결정 2026-10-31): 명령 갈래의 비회복과 같이 책임자 확인으로 바꾼다 — 종결로 남기면 회복 확인 없는 해피패스다
        inc.reason = d.RESULT_REPORT
        _audit(inc, fx, 'process', 'INCIDENT_ESCALATED', {'resultReport': summary, 'level': level, 'after': 'work_order'})
        _go(inc, 'ESCALATED', f"결과 보고: {summary}"[:300])
        return True
    if inc.state in d.TERMINAL or inc.state in ('CMD_ISSUED', 'AWAITING_ACK', 'RE_OBSERVING'):
        return False
    if level == 'rejected':
        if inc.state != 'AWAITING_APPROVAL':
            raise ValueError(f'반려 결과 보고는 승인 대기 중인 사건만 닫습니다 (사건 {inc.id} 지금: {d.state_label(inc.state)})')
        inc.reason = summary
        _audit(inc, fx, 'process', 'GUIDE_REJECTED', {'resultReport': summary, 'level': level})
        _go(inc, 'REJECTED_BY_OPERATOR', f"결과 보고: {summary}"[:300])
        return True
    if level == 'fail':
        inc.reason = d.RESULT_REPORT       # P1-31: 사유 칸을 비워 두지 않는다 — 문장은 결과 보고 틀이다(escalation_cause 는 None)
    _audit(inc, fx, 'process', 'INCIDENT_CLOSED' if level == 'ok' else 'INCIDENT_ESCALATED', {'resultReport': summary, 'level': level})
    _go(inc, 'CLOSED' if level == 'ok' else 'ESCALATED', f"결과 보고: {summary}"[:300])
    return True


@_transition
def on_process_ended(inc: Incident, end_label: str, fx: Effects) -> bool:
    """사건을 맡은 처리 건이 사건을 닫지 않고 끝났다(카드 선택 시한 → 상급자 호출 끝, 사람이 멈춘 AI 단계를 닫음, 승인 폐기 …). 처리 건은 끝났는데
    사건만 「승인 대기」로 남으면 아무도 닫을 수 없고 열린 사건 수가 부풀었다(P1-01 · H-10) — 책임자 확인(ESCALATED)으로 닫고 끝난 곳을 사유에
    남긴다. 이미 끝난 사건과 명령이 오가는 중(CMD_ISSUED · AWAITING_ACK · RE_OBSERVING — 사건이 스스로 판정한다)은 그대로 둔다(False)."""
    if inc.state in d.TERMINAL or inc.state in ('CMD_ISSUED', 'AWAITING_ACK', 'RE_OBSERVING'):
        return False
    inc.reason = f"{d.PROCESS_ENDED}: {end_label}"
    _audit(inc, fx, 'process', 'INCIDENT_ESCALATED', {'processEnded': end_label, 'stateBefore': inc.state})
    _go(inc, 'ESCALATED', f"처리 건이 「{end_label}」{particle(end_label, '으로')} 끝나 책임자 확인으로 닫음")
    return True
