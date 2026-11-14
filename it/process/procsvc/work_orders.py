"""Durable CMMS request and real receipt; no synthetic work-order identities."""
from copy import deepcopy

from . import machine


def request_for_option(option):
    from hydcommon.execution_scope import require_executable
    require_executable(option)
    change = [a for a in option.get('actions',[]) if a.get('code') == 'WO_RESCHEDULE']
    if change:
        plan = option.get('maintenancePlan')
        if len(change) != 1 or not isinstance(plan,dict) or plan.get('code') != 'WO_RESCHEDULE':
            raise ValueError('PM 일정 변경의 승인된 기존 오더와 목표 창 근거가 없습니다')
        return dict(skill=option['id'],sop=option['sopId'],system='sys:cmms',
                    value=change[0].get('value'),source='approved-action',**deepcopy(plan))
    if option.get('source_id') and not option.get('actions'):
        raise ValueError('원문 절차의 빈 Action을 새 정비 오더 발행으로 대체하지 않습니다')
    actions = [a for a in option.get('actions', []) if a.get('code') == 'WO_CREATE']
    if len(actions) > 1:
        raise ValueError('한 조치 후보에 정비 요청 동작이 둘 이상이라 어느 것을 낼지 정할 수 없습니다 — 판단을 다시 받으세요')
    if not option.get('id') or not option.get('sopId'):
        raise ValueError('승인한 조치 후보에 조치 방법(SOP)이 없어 정비 요청을 낼 수 없습니다 — 판단을 다시 받으세요')
    action = actions[0] if actions else {}
    if action.get('target') not in (None, 'sys:cmms'):
        raise ValueError(f"정비 요청은 정비 시스템(CMMS)으로만 냅니다 — 조치 후보의 대상이 {action.get('target')} 입니다")
    return {'skill':option['id'], 'sop':option['sopId'], 'code':'WO_CREATE',
            'name':action.get('name') or '정비 요청',
            'system':action.get('target') or 'sys:cmms',
            'value':action.get('value') if actions else f"선택한 조치 이후 정비 점검: {option.get('name')}",
            'param':action.get('param'),
            'source':'approved-action' if actions else 'process-definition-followup',
            **({'schedule_plan':deepcopy(option['maintenancePlan'])} if option.get('maintenancePlan') else {})}


def no_maintenance_time(option) -> str:
    """승인한 카드가 즉시 시행이 아닌데 정비 시점이 없을 때의 까닭 — 작업지시 등록(instances._run_work_order)과 정비 수행(service_parts)이 같이 쓴다."""
    return (f"승인한 조치 후보 「{(option or {}).get('name') or (option or {}).get('id') or '?'}」는 즉시 시행이 아닌데 정비를 언제 할지 정한 시각이 없습니다 — "
            "시점을 지어내 정비하지 않습니다. 정비 시스템(CMMS)의 예정된 정비 시간을 확인한 뒤 판단을 다시 받으세요")


def prepare(ctx, decision, item):
    """Save exactly the request that will be retried before calling CMMS."""
    inc_id = (decision.get('origin') or {}).get('incident')
    if not inc_id:
        return None
    inc = ctx.incidents.get(inc_id)
    if inc is None or inc.asset != decision.get('asset'):
        raise ValueError('정비 요청의 사건 · 설비가 승인한 판단과 다릅니다 — 처리 건 화면에서 지금 판단을 확인하세요')
    option = next(o for o in decision['options'] if o['id'] == decision['chosen'])
    commands = any(a.get('kind') == 'command' for a in option.get('actions', []))
    request = {'decision':decision['id'], 'option':decision['chosen'],
               'option_name':option.get('name'), 'by':decision.get('approvedBy'),
               'item':deepcopy(item), 'work_order_only':not commands}
    if not request['by']:
        raise ValueError('정비 요청을 승인한 사람 기록이 없어 낼 수 없습니다 — 사람 승인 뒤에만 정비 요청을 냅니다')
    with machine.STATE_LOCK:   # A143: the saved request and its rollback are one step for a concurrent snapshot
        if inc.work_order_request is not None:
            if inc.work_order_request != request:
                raise ValueError('다시 보내는 정비 요청이 처음 저장한 요청과 다릅니다 — 같은 요청만 다시 보냅니다')
        else:
            if inc.state != 'RESOLVED' and not (not commands and inc.state == 'AWAITING_APPROVAL'):
                raise ValueError(f'정비 요청은 설비 회복이 확인됐거나 정비 요청만 고른 승인 뒤에 냅니다 — 지금 사건: {_state_name(inc.state)}')
            inc.work_order_request = request
            try:
                ctx.persist()
            except Exception:
                inc.work_order_request = None
                raise
    # Closed is an idempotent response replay; escalation requires human review.
    if inc.state not in ('RESOLVED', 'AWAITING_APPROVAL', 'CLOSED'):
        raise ValueError(f'사건이 {_state_name(inc.state)} 상태로 바뀌어 정비 요청을 내지 않았습니다 — 처리 건 화면에서 사건 상태를 확인하세요')
    if commands and inc.state == 'AWAITING_APPROVAL':
        raise ValueError('설비 명령 뒤 회복이 확인되기 전에는 정비 요청을 내지 않습니다 — 효과 확인이 끝난 뒤 다시 하세요')
    return inc


def _state_name(state):
    from . import definition
    return definition.state_label(state)


class _Audit(machine.Effects):
    def __init__(self):
        self.events = []

    def emit_audit(self, event):
        self.events.append(event)


def confirm(ctx, inc, item, result):
    if inc is None:
        return
    before = deepcopy(inc.__dict__)
    fx = _Audit()
    request = inc.work_order_request
    receipt = dict(result, name=item.get('name'), sop=item.get('sop'), requested_value=item.get('value'),
                   source=item.get('source'), decision=request['decision'])
    with machine.STATE_LOCK:   # A143: __dict__.clear()+update() rollback must not be captured half-way by a snapshot
        try:
            inc.approved_by = request['by']
            machine.on_work_order(inc, receipt, fx, work_order_only=request['work_order_only'])
            ctx.persist()
        except Exception:
            inc.__dict__.clear()
            inc.__dict__.update(before)
            raise
    for event in fx.events:
        ctx.audit(inc.asset, event['actor'], event['event'], event['detail'], incident=inc.id)
    if getattr(ctx, 'after_incident', None):
        ctx.after_incident(inc)
