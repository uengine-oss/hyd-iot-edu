"""Read-only incident evidence and admission of rework before external effects.

Original cards and approval payloads remain evidence. Supersession lives in the
PG generation receipt, so no SQLite mutation can survive a rolled-back request.
"""
from copy import deepcopy

from . import engine, rework

RUNTIME_CONSENT = {'commands', 'chosen_option', 'approved_by', 'approved_role'}


def no_effects(evidence, approvals):
    """Absence requires the whole incident and every related decision ledger."""
    incident = evidence['incident']
    decisions = evidence['decisions']
    ledgers = evidence['enterprise_receipts']
    return (not any(incident.get(k) for k in ('cmdId', 'actions', 'ack', 'workOrder', 'workOrderRequest'))
            and set(ledgers) == {d['id'] for d in decisions}
            and all(not d.get('executions') and ledgers[d['id']] == [] for d in decisions)
            and all(a.get('results') == [] for a in approvals))


def unissued_commands(defn, inst, work, approvals, evidence):
    """Only the durable-intent Incident command handler can prove no send.

    PENDING is a stopped claim, not an in-flight SUBMITTED service. The handler
    persists cmdId/actions before publishing. Unknown handlers remain blocked.
    Caller holds the owning transition lock while checking and committing.
    """
    if not no_effects(evidence, approvals):
        return set()
    v = engine.variables(inst)
    inc = evidence['incident']
    if inc.get('id') != v.get('incident') or inc.get('asset') != v.get('asset'):
        return set()
    decisions = {d['id']: d for d in evidence['decisions']}
    rows = {w['id']: w for w in work}
    current = [a for a in approvals if a['status'] != 'DISCARDED']
    if len(current) != 1:
        return set()
    a = current[0]; p = a['payload']; selection = rows.get(a['todo_id'])
    d = decisions.get(a['decision_id'])
    generation = int(inst.get('rework_generation') or 0)
    if (a['status'] != 'DELIVERED' or not selection or not d
            or a.get('tenant_id') != inst.get('tenant_id') or a.get('proc_inst_id') != inst['proc_inst_id']
            or selection['status'] != 'DONE' or int(selection.get('generation') or 0) != generation
            or d.get('process_approval_id') != a['todo_id'] or d.get('state') != 'APPROVED'
            or d.get('chosen') != p.get('option') or a['decision_id'] != v.get('decision_id')
            or p.get('incident') != inc['id'] or p.get('asset') != inc['asset']
            or not p.get('commands') or p['commands'] != v.get('commands')
            or p.get('by') != v.get('approved_by') or p.get('role') != v.get('approved_role')):
        return set()
    option = deepcopy(p['plan']['option']); option['kind'] = 'control'
    if v.get('chosen_option') != option:
        return set()
    return {w['id'] for w in work
            if w['status'] == 'PENDING' and not w.get('consumer') and not w.get('output')
            and 'action.cmd ' not in (w.get('log') or '') and 'waiting ACK' not in (w.get('log') or '')
            and w.get('tenant_id') == inst.get('tenant_id') and w.get('proc_inst_id') == inst['proc_inst_id']
            and w.get('version') == inst['proc_def_version'] and int(w.get('generation') or 0) == generation
            and defn.activities.get(w['activity_id'], {}).get('type') in engine.SERVICE_TYPES
            and defn.activities[w['activity_id']].get('tool') == 'incident:command'
            and selection['activity_id'] in rework.ancestors(defn, w['activity_id'])}


def collect(ctx, inst):
    values = engine.variables(inst)
    inc = ctx.incidents.get(values.get('incident'))
    if inc is None or inc.asset != values.get('asset'):
        raise ValueError('재작업 사건 원문/설비를 확인할 수 없습니다')
    if ctx.approval_receipts is None:
        raise ValueError('재작업 기업 실행 원장 조회가 연결되지 않았습니다')
    decisions = sorted((deepcopy(d) for d in list(ctx.book.values())
                        if (d.get('origin') or {}).get('incident') == inc.id), key=lambda d: d['id'])
    ledgers = {}
    for decision in decisions:
        if decision.get('asset') != inc.asset:
            raise ValueError('사건 판단의 설비가 일치하지 않습니다')
        receipts = ctx.approval_receipts(decision['id'])
        if not isinstance(receipts, list) or any(not isinstance(r, dict) or r.get('decision') != decision['id'] for r in receipts):
            raise ValueError('재작업 기업 실행 원장의 응답 계약이 다릅니다')
        ledgers[decision['id']] = deepcopy(receipts)
    # Full snapshots include commands, acknowledgements, recovery, guide and
    # source identity. Do not reduce absence of effects to cmdId alone.
    return {'incident': dict(deepcopy(inc.to_dict()), recovery=deepcopy(inc.recovery)), 'decisions': decisions, 'enterprise_receipts': ledgers,
            'scope': 'owning Incident and all its decision ledgers; no external effect reversed'}


def admit(proposal, defn, inst, work, approvals, evidence):
    """Enrich the structural plan; never remove an unrelated blocker."""
    proposal = deepcopy(proposal)
    blockers = proposal['blockers']
    def block(code, **detail): blockers.append(dict(code=code, **detail))
    values = engine.variables(inst)
    incident = evidence['incident']
    decisions = {d['id']: d for d in evidence['decisions']}
    if incident.get('id') != values.get('incident') or incident.get('asset') != values.get('asset'):
        raise ValueError('효과 조회와 재작업 사건이 다릅니다')
    if incident.get('state') != 'AWAITING_APPROVAL' or incident.get('cleared') or not incident.get('recovery'):
        block('incident_not_active_for_rework')
    if any(incident.get(k) for k in ('cmdId', 'actions', 'ack', 'workOrder', 'workOrderRequest')):
        block('incident_effects_require_compensation')
    for did, decision in decisions.items():
        if decision.get('executions') or evidence['enterprise_receipts'][did]:
            block('decision_effects_require_compensation', decision=did)
        if (decision.get('chosen') or decision.get('state') not in {'PENDING_APPROVAL', 'REJECTED'}) and not any(
                a['decision_id'] == did for a in approvals):
            block('untracked_decision_consent', decision=did)
    if values.get('decision_id') and values['decision_id'] not in decisions:
        block('current_decision_original_missing')
    if not any('decision_id' in defn.activities.get(aid, {}).get('outputData', []) for aid in proposal['affected_nodes']):
        block('rework_requires_new_decision')
    affected = {w['id'] for w in proposal['affected_workitems']}
    unissued = unissued_commands(defn, inst, work, approvals, evidence) & affected
    retire = []
    for approval in approvals:
        if approval['decision_id'] not in decisions:
            block('approval_decision_original_missing', workitem=approval['todo_id'])
        if approval['status'] == 'DISCARDED':
            continue
        eligible = approval['status'] in {'PENDING', 'FAILED'} or (approval['status'] == 'DELIVERED' and bool(unissued))
        if (not eligible or approval['todo_id'] not in affected
                or approval.get('results')):
            block('approval_effects_require_review', workitem=approval['todo_id'])
        else:
            retire.append(approval['todo_id'])
    # Only runtime values proved by the same committed consent may be cleared.
    # Unknown runtime mutations keep their structural provenance blocker.
    owned = {}
    for approval in approvals:
        if approval['todo_id'] not in retire:
            continue
        p = approval['payload']; option = deepcopy(p['plan']['option'])
        option['kind'] = 'control' if any(a.get('kind') == 'command' for a in option.get('actions', [])) else 'work_order'
        owned.update(commands=p['commands'], chosen_option=option, approved_by=p['by'], approved_role=p['role'])
    clear = {k for k in RUNTIME_CONSENT if k in owned and values.get(k) == owned[k]
             and (inst.get('variable_sources') or {}).get(k, {}).get('kind') == 'runtime'}
    blockers[:] = [b for b in blockers
                   if b['code'] != 'incident_rework_effect_contract_pending'
                   and not (b['code'] == 'approval_requires_review' and b.get('workitem') in retire)
                   and not (b['code'] == 'service_effects_require_review' and b.get('workitem') in unissued)
                   and not (b['code'] == 'variable_provenance_requires_review' and b.get('variable') in clear)]
    for key in clear:
        proposal['candidate_variables'].pop(key, None)
        proposal['candidate_sources'].pop(key, None)
    proposal['invalidated_variables'] = sorted(set(proposal['invalidated_variables']) | clear)
    proposal['retire_approvals'] = retire
    proposal['unissued_commands'] = sorted(unissued)
    proposal['unissued_command_evidence'] = [deepcopy(w) for w in work if w['id'] in unissued]
    proposal['started_services'] = [wid for wid in proposal['started_services'] if wid not in unissued]
    proposal['retired_decisions'] = sorted(decisions)
    proposal['effects'] = deepcopy(evidence)
    proposal['snapshot_token'] = rework.fingerprint({'local': proposal['snapshot_token'], 'effects': evidence})
    proposal['execution_available'] = not blockers and bool(proposal['request_roles'])
    proposal['scope'] = '현재 사건과 전체 판단 원장을 재조회하고 효과가 없는 범위에서 새 작업/판단/승인을 시작합니다. 기존 조치는 보상하지 않습니다.'
    return proposal
