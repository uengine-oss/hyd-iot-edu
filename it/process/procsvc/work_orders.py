"""Durable CMMS request and real receipt; no synthetic work-order identities."""
from copy import deepcopy

from . import machine


def request_for_option(option):
    actions = [a for a in option.get('actions', []) if a.get('code') == 'WO_CREATE']
    if len(actions) > 1:
        raise ValueError('multiple WO_CREATE actions need distinct execution identities')
    if not option.get('id') or not option.get('sopId'):
        raise ValueError('work order requires the selected skill and SOP')
    action = actions[0] if actions else {}
    if action.get('target') not in (None, 'sys:cmms'):
        raise ValueError('WO_CREATE must target the configured CMMS system')
    return {'skill':option['id'], 'sop':option['sopId'], 'code':'WO_CREATE',
            'name':action.get('name') or '정비 작업지시',
            'system':action.get('target') or 'sys:cmms',
            'value':action.get('value') if actions else f"선택한 조치 이후 정비 점검: {option.get('name')}",
            'param':action.get('param'),
            'source':'approved-action' if actions else 'process-definition-followup'}


def prepare(ctx, decision, item, *, allow_before_recovery=False):
    """Save exactly the request that will be retried before calling CMMS."""
    inc_id = (decision.get('origin') or {}).get('incident')
    if not inc_id:
        return None
    inc = ctx.incidents.get(inc_id)
    if inc is None or inc.asset != decision.get('asset'):
        raise ValueError('work order Incident/asset does not match the approved decision')
    option = next(o for o in decision['options'] if o['id'] == decision['chosen'])
    commands = any(a.get('kind') == 'command' for a in option.get('actions', []))
    request = {'decision':decision['id'], 'option':decision['chosen'],
               'option_name':option.get('name'), 'by':decision.get('approvedBy'),
               'item':deepcopy(item), 'work_order_only':not commands}
    if not request['by']:
        raise ValueError('work order has no approving person')
    if inc.work_order_request is not None:
        if inc.work_order_request != request:
            raise ValueError('work order retry conflicts with its saved request')
    else:
        if inc.state != 'RESOLVED' and not ((not commands or allow_before_recovery) and inc.state == 'AWAITING_APPROVAL'):
            raise ValueError(f'work order requires confirmed recovery or an approved work-order-only choice: {inc.state}')
        inc.work_order_request = request
        try:
            ctx.persist()
        except Exception:
            inc.work_order_request = None
            raise
    # Closed is an idempotent response replay; escalation requires human review.
    if inc.state not in ('RESOLVED', 'AWAITING_APPROVAL', 'CLOSED'):
        raise ValueError(f'work order needs review after Incident state {inc.state}')
    if commands and inc.state == 'AWAITING_APPROVAL' and not allow_before_recovery:
        raise ValueError('work order must wait for confirmed plant recovery')
    return inc


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
