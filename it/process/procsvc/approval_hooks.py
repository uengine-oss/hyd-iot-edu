"""Bridge committed approval snapshots to the legacy Incident/decision store."""
from copy import deepcopy

from hydcommon.timeutil import now_iso
from . import decisions, machine, current_approval


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


def record_execution(d, result):
    """Record the latest outcome per approved atomic action, idempotently."""
    entry = {'skill':result.get('skill'), 'code':result.get('code'),
             'status':'DONE' if result.get('ok') else 'FAILED', 'ref':result.get('ref'),
             'system':result.get('system'), 'detail':result.get('detail') or result.get('error'), 't':now_iso()}
    rows = d.setdefault('executions', [])
    prior = next((x for x in rows if (x.get('skill'), x.get('code')) == (entry['skill'], entry['code'])), None)
    if prior is not None and prior.get('status') == 'DONE' and entry['status'] == 'DONE':
        if prior.get('ref') != entry['ref']:
            raise ValueError('same approved action returned conflicting execution references')
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
            raise ValueError('사건/판단 원문을 확인할 수 없습니다')
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
            raise ValueError('no such decision')
        snapshot = deepcopy(d)
        plan = decisions.approve(snapshot, option_id, by, role, reason)
        return plan | {'_snapshot':snapshot}

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
            raise ValueError('decision does not belong to this incident/asset')
        inc = self.ctx.incidents.get(inc_id)
        if inc is None or inc.asset != payload['asset']:
            raise ValueError('approval incident is unavailable')
        if inc.state != 'AWAITING_APPROVAL':
            raise ValueError(f'incident is {inc.state}; approval requires review')
        if payload.get('commands'):
            machine._validate_actions(inc, payload['commands'])
        option = next(o for o in snapshot['options'] if o['id'] == payload['option'])
        require_reviewed_commands(option, payload.get('commands') or [])
        report = current_approval.require(self.ctx.check_approval, snapshot, payload['option'], payload['role'])
        payload['current_check'] = report

    def deliver(self, row):
        payload = row['payload']
        self.validate(payload)
        snapshot = deepcopy(payload['plan']['_snapshot'])
        d = self.ctx.book.setdefault(row['decision_id'], {})
        owner = d.get('process_approval_id')
        if owner not in (None, row['todo_id']):
            raise ValueError('decision belongs to a different committed approval')
        # Keep completed results when replaying the same intent, but never use mutable card inputs.
        executions = deepcopy(d.get('executions', [])) if owner == row['todo_id'] else []
        d.clear()
        d.update(snapshot, process_approval_id=row['todo_id'], executions=executions)
        self.ctx.persist()
        results = []
        for item in payload['plan'].get('enterprise', []):
            if item.get('code') == 'WO_CREATE':
                continue
            result = self.ctx.exec_skill(d, deepcopy(item))
            if result.get('ok') is not True:
                raise RuntimeError(result.get('error') or str(result))
            record_execution(d, result)
            self.ctx.persist()
            results.append(result)
        return results

    def record(self, row):
        d = self.ctx.book.get(row['decision_id'])
        if d:
            self.ctx.record_decision(deepcopy(d))
