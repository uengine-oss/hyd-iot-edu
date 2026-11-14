"""Bridge committed approval snapshots to the legacy Incident/decision store."""
from copy import deepcopy

from hydcommon.timeutil import now_iso
from . import decisions, machine
from . import definition as incident_def


def approval_refusal(state: str, reason: str | None = None) -> str:
    """승인 대기가 아닌 사건의 승인 거절 사유(사람이 읽는 문장 + 할 일). 전에는 영어 내부 사유('incident is …; approval requires review')였다."""
    if state == 'RESOLVED_WITHOUT_ACTION':
        return ('경보가 조치 전에 이미 풀려(사건: 조치 전 자연 회복) 승인할 수 없습니다 — 설비 명령이 필요 없습니다. '
                '처리 건은 「조치 전 해소」로 닫힙니다(닫히지 않았으면 화면을 새로 고치세요)')
    label = incident_def.state_label(state)
    # 에스컬레이션 사유는 코드(ACK_TIMEOUT …)라 사람 문장으로 바꾼다(definition.escalation_cause) — 거절 사유는 사람이 적은 글 그대로
    cause = incident_def.escalation_cause(reason) if state == 'ESCALATED' else None
    tail = f' — {cause[0]}' if cause else f', 사유 {reason}' if reason and state in incident_def.TERMINAL and state != 'ESCALATED' else ''
    if state in incident_def.TERMINAL:
        return f'사건이 이미 끝나 승인할 수 없습니다(사건: {label}{tail}) — 같은 경보로 다시 조치하려면 새 판단이 필요합니다'
    return f'사건이 승인 대기 상태가 아니라 승인할 수 없습니다(지금: {label}) — 진행 중인 조치가 끝난 뒤 화면을 새로 고치세요'


def require_reviewed_commands(option, commands):
    """An approved forecast may authorize only the exact actions it displayed."""
    expected = []
    for action in option.get('actions') or []:
        if action.get('kind') == 'command':
            item = {'code': action['code']}
            if action.get('param'):
                item[action['param']] = action.get('value')
            expected.append(item)
    if expected != commands:
        raise ValueError('검토한 카드와 실행 조치값이 다릅니다. 변경한 조치의 새 예측 카드를 검토하세요')


_NO_DECISION = '판단 기록({})을 찾을 수 없습니다 — 처리 건 화면을 새로 고친 뒤 지금 판단으로 다시 하세요'


@machine._transition
def record_execution(d, result):
    """Record the latest outcome per approved atomic action, idempotently."""
    entry = {'skill':result.get('skill'), 'code':result.get('code'),
             'status':'DONE' if result.get('ok') else 'FAILED', 'ref':result.get('ref'),
             'system':result.get('system'), 'detail':result.get('detail') or result.get('error'), 't':now_iso()}
    rows = d.setdefault('executions', [])
    prior = next((x for x in rows if (x.get('skill'), x.get('code')) == (entry['skill'], entry['code'])), None)
    if prior is not None and prior.get('status') == 'DONE' and entry['status'] == 'DONE':
        if prior.get('ref') != entry['ref']:
            raise ValueError(f"승인한 같은 조치({entry['code']})를 업무 시스템이 서로 다른 기록 번호로 두 번 처리했습니다"
                             f"({prior.get('ref')} · {entry['ref']}) — 업무 시스템 실행 이력을 확인해야 합니다")
    elif prior is not None:
        prior.update(entry)
    else:
        rows.append(entry)
    opt = next((o for o in d.get('options', []) if o['id']==d.get('chosen')), {})
    expected = {a.get('code') for a in opt.get('actions', []) if a.get('kind')!='command'}
    done = {x.get('code') for x in rows if x['status']=='DONE'}
    d['state'] = 'PARTIAL' if any(x['status']=='FAILED' for x in rows) else ('EXECUTED' if expected <= done else 'APPROVED')


class DecisionDelivery:
    def __init__(self, ctx):
        self.ctx = ctx

    def effects(self, row):
        """Read the owning Incident, local outcomes, and complete enterprise ledger.

        An empty recent-transactions page cannot prove absence of older effects.
        A failed/absent source must propagate, never become an empty list.
        """
        payload = row['payload']
        inc = self.ctx.incidents.get(payload.get('incident'))
        decision = self.ctx.book.get(row['decision_id'])
        if inc is None or inc.asset != payload.get('asset') or decision is None:
            raise ValueError('사건 · 판단 원문을 확인할 수 없습니다')
        if ((decision.get('origin') or {}).get('incident') != inc.id
                or decision.get('asset') != inc.asset):
            raise ValueError('판단과 사건의 소유 관계가 다릅니다')
        if self.ctx.approval_receipts is None:
            raise ValueError('기업 실행 원장 조회가 연결되지 않았습니다')
        receipts = self.ctx.approval_receipts(row['decision_id'])
        if not isinstance(receipts, list) or any(not isinstance(r, dict) or r.get('decision') != row['decision_id'] for r in receipts):
            raise ValueError('기업 실행 원장의 응답 계약이 다릅니다')
        return {'incident': {'id': inc.id, 'state': inc.state, 'cmdId': inc.cmd_id,
                             'workOrder': inc.work_order, 'workOrderRequest': inc.work_order_request, 'cleared': inc.cleared},
                'decision': row['decision_id'], 'local_executions': deepcopy(decision.get('executions', [])),
                'enterprise_receipts': receipts, 'delivery_results': deepcopy(row.get('results', [])),
                'checked_at': now_iso(), 'scope': 'complete decision ledger and owning Incident; no effect was reversed'}

    def prepare(self, decision_id, option_id, by, role, reason):
        d = self.ctx.book.get(decision_id)
        if d is None:
            raise ValueError(_NO_DECISION.format(decision_id))
        snapshot = deepcopy(d)
        plan = decisions.approve(snapshot, option_id, by, role, reason)
        return plan | {'_snapshot':snapshot}

    def check_rejection(self, decision_id, role):
        """조치 카드를 거절할 수 있는 역할인가: 이 판단의 안 하나라도 그 승인 역할(또는 더 높은 역할)이면 거절도 할 수 있다(고치지 않는다).
        실행 준비는 보지 않는다 — 모든 안이 재고 · 규정으로 빠진 판단도 그 역할이 거절로 닫을 수 있어야 한다(2026-10-23 라이브: B가 승인 단계에 갇힘)."""
        d = self.ctx.book.get(decision_id)
        if d is None:
            raise ValueError(_NO_DECISION.format(decision_id))
        if d['state'] != 'PENDING_APPROVAL':
            raise ValueError(f"이 판단은 {decisions.STATE_WORDS.get(d['state'], d['state'])} — 거절할 수 없습니다. 화면을 새로 고쳐 지금 상태를 보세요")
        if not any(decisions.holds_approver_role(d, option, role) for option in d.get('options') or []):
            raise PermissionError('거절 권한 없음: 이 판단의 조치를 승인할 수 있는 역할만 거절할 수 있습니다')

    def reject(self, decision_id, by, reason):
        """커밋된 거절을 판단 원문에 남긴다(REJECTED · 누가 · 사유). 이미 거절로 남은 판단이면 그대로 둔다(재실행에 안전)."""
        d = self.ctx.book.get(decision_id)
        if d is None:
            raise ValueError(_NO_DECISION.format(decision_id))
        if d['state'] == 'REJECTED':
            return
        decisions.reject(d, by, reason)
        self.ctx.persist()                         # 저장이 사건 · 판단 그래프 반영을 깨운다

    def close_unapproved(self, decision_id, reason):
        """처리 건이 승인 없이 끝났으면 승인 대기 판단을 끝낸다(CLOSED_UNAPPROVED). 이미 끝난 판단(승인 · 거절 · 실행)은 그대로 — 재실행에 안전."""
        d = self.ctx.book.get(decision_id)
        if d is None:
            raise ValueError(_NO_DECISION.format(decision_id))
        if d['state'] != 'PENDING_APPROVAL':
            return
        decisions.close_unapproved(d, reason)
        self.ctx.persist()

    def preview(self, decision_id, option_id, parameters, scope):
        if self.ctx.reviews is None:
            raise ValueError('검토본 저장소가 연결되지 않았습니다')
        return self.ctx.reviews().create(decision_id,option_id,parameters,scope)

    def prepare_review(self, decision_id, option_id, by, role, reason, review_id, scope):
        if self.ctx.reviews is None:
            raise ValueError('검토본 저장소가 연결되지 않았습니다')
        snapshot = self.ctx.reviews().snapshot(review_id,decision_id,option_id,scope)
        plan = decisions.approve(snapshot,option_id,by,role,reason)
        return plan | {'_snapshot':snapshot}

    def validate(self, payload):
        snapshot = payload['plan']['_snapshot']
        inc_id = (snapshot.get('origin') or {}).get('incident')
        if inc_id != payload.get('incident') or snapshot.get('asset') != payload.get('asset'):
            raise ValueError('승인한 판단이 이 사건 · 설비의 판단이 아닙니다 — 처리 건 화면에서 지금 판단을 다시 고르세요')
        inc = self.ctx.incidents.get(inc_id)
        if inc is None or inc.asset != payload['asset']:
            raise ValueError(f'승인한 사건({inc_id})을 찾을 수 없습니다 — 처리 서비스가 사건 기록을 잃었습니다. 시스템 관리자에게 알리세요')
        if inc.state != 'AWAITING_APPROVAL':
            raise ValueError(approval_refusal(inc.state, inc.reason))
        option = next(o for o in snapshot['options'] if o['id'] == payload['option'])
        if payload.get('commands'):
            machine._validate_actions(option, payload['commands'])
        require_reviewed_commands(option, payload.get('commands') or [])
        # 현재 조건 검사 연결(ctx.check_approval = main._check_current_approval)이 검사 · 감사 · 허용 판정(current_approval.require)을 한 번에 한다
        args = (snapshot, payload['option'], payload['role']) + ((payload['consented_at'],) if payload.get('consented_at') else ())
        payload['current_check'] = self.ctx.check_approval(*args)

    def deliver(self, row):
        payload = row['payload']
        self.validate(payload)
        snapshot = deepcopy(payload['plan']['_snapshot'])
        with machine.STATE_LOCK:   # A143: clear()+update() must not be captured half-way by a concurrent snapshot
            d = self.ctx.book.setdefault(row['decision_id'], {})
            owner = d.get('process_approval_id')
            if owner not in (None, row['todo_id']):
                raise ValueError('이 판단은 이미 다른 승인으로 전달됐습니다 — 같은 판단을 두 번 승인하지 않습니다')
            # Keep completed results when replaying the same intent, but never use mutable card inputs.
            executions = deepcopy(d.get('executions', [])) if owner == row['todo_id'] else []
            d.clear()
            d.update(snapshot, process_approval_id=row['todo_id'], executions=executions)
            self.ctx.persist()
        results = []
        # C2: 흐름의 시스템 task 가 실행하는 거래(작업지시, 흐름에 발주 task 가 있으면 발주)는 여기서 실행하지 않는다
        deferred = set(payload.get('deferred') or ['WO_CREATE'])
        for item in payload['plan'].get('enterprise', []):
            if item.get('code') in deferred:
                continue
            result = self.ctx.exec_skill(d, deepcopy(item))
            if result.get('ok') is not True:
                raise RuntimeError(result.get('error') or str(result))
            record_execution(d, result)
            self.ctx.persist()
            results.append(result)
        return results
