"""Rework planning from a pinned definition and durable producer evidence.

Control/data/boundary dependencies are conservative: all possible affected branches
are included. This plan does not authorize execution or undo external effects.
"""
from copy import deepcopy
import ast
import hashlib
import json

from . import engine


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def ancestors(defn, node):
    found, queue = set(), [s['source'] for s in defn.sequences if s['target'] == node]
    while queue:
        current = queue.pop()
        if current in found:
            continue
        found.add(current)
        queue.extend(s['source'] for s in defn.sequences if s['target'] == current)
    return found


def plan(defn, inst, workitems, workitem_id, approvals=()):
    """Calculate dependencies without changing any input or guessing missing inputs."""
    if inst.get('proc_def_id') != defn.id or inst.get('proc_def_version') != defn.raw.get('version'):
        raise ValueError('재작업에는 인스턴스의 고정 정의 판본이 필요합니다')
    rows = {w['id']: w for w in workitems}
    if len(rows) != len(workitems):
        raise ValueError('중복 작업 ID가 있습니다')
    for row in workitems:
        if (row.get('proc_inst_id') != inst['proc_inst_id'] or row.get('tenant_id') != inst.get('tenant_id')
                or row.get('proc_def_id') != defn.id or row.get('version') != inst['proc_def_version']):
            raise ValueError('다른 인스턴스/tenant/정의 판본의 작업이 섞였습니다')
        defn.node_kind(row['activity_id'])
    root = rows.get(workitem_id)
    if not root or root['activity_id'] not in defn.activities:
        raise ValueError('재작업 시작점은 이 인스턴스의 업무 작업이어야 합니다')
    reasons = {}
    def add(node, reason):
        bucket = reasons.setdefault(node, [])
        if reason not in bucket:
            bucket.append(reason)
    add(root['activity_id'], {'kind': 'requested', 'workitem': workitem_id})
    changed = True
    while changed:
        before = set(reasons)
        outputs = {key for aid in reasons for key in defn.activities.get(aid, {}).get('outputData', [])}
        for node in list(reasons):
            for sequence in defn.outgoing(node):
                add(sequence['target'], {'kind': 'flow', 'source': node, 'sequence': sequence['id']})
            for event in defn.attached_events(node):
                add(event['id'], {'kind': 'boundary', 'source': node})
        for aid, activity in defn.activities.items():
            for key in sorted(outputs.intersection(activity.get('inputData') or [])):
                binding = (activity.get('inputBindings') or {}).get(key)
                if binding is not None and binding.get('activity') not in reasons:
                    continue
                add(aid, {'kind': 'input', 'variable': key})
        # Conditions consume variables even when the target task has no inputData.
        for sequence in defn.sequences:
            if sequence.get('condition'):
                names = {n.id for n in ast.walk(engine.compile_condition(sequence['condition'])) if isinstance(n, ast.Name)}
                for key in sorted(names & outputs):
                    add(sequence['source'], {'kind': 'condition', 'variable': key, 'sequence': sequence['id']})
                    # A gateway has no review work item of its own. Re-run the
                    # actual preceding work rather than inventing a new token.
                    if sequence['source'] in defn.gateways:
                        from . import dependency_schedule
                        for prior in dependency_schedule.control_predecessors(defn, sequence['source']):
                            add(prior, {'kind':'condition_recheck', 'gateway':sequence['source'],
                                        'variable':key, 'sequence':sequence['id']})
                    elif sequence['source'] in defn.events:
                        attached=defn.attached_activity(sequence['source'])
                        if attached:
                            add(attached['id'], {'kind':'condition_recheck', 'event':sequence['source'],
                                                'variable':key, 'sequence':sequence['id']})
        affected_ids = {w['id'] for w in workitems if w['activity_id'] in reasons}
        for row in workitems:
            for ref in sorted(set(row.get('reference_ids') or []) & affected_ids):
                add(row['activity_id'], {'kind': 'reference', 'workitem': ref})
        changed = before != set(reasons)

    blockers = []
    def block(code, **detail):
        item = dict(code=code, **detail)
        if item not in blockers:
            blockers.append(item)
    if inst.get('status') != 'RUNNING' or inst.get('is_deleted'):
        block('instance_not_running')
    seed = inst.get('initial_variables')
    if not isinstance(seed, dict):
        block('initial_inputs_unavailable')
        seed = {}
    # rework_count also counts same-request CMMS retries; it cannot order generations.
    latest = engine._by_activity(workitems)
    for aid, last in latest.items():
        if sum(w['activity_id'] == aid and engine.workitem_order(w) == engine.workitem_order(last) for w in workitems) > 1:
            block('ambiguous_workitem_order', activity=aid)
    if latest.get(root['activity_id'], {}).get('id') != workitem_id:
        block('start_workitem_superseded', workitem=workitem_id)
    if root['status'] not in {'DONE', 'PENDING', 'IN_PROGRESS', 'SUBMITTED'}:
        block('start_workitem_not_reached', workitem=workitem_id)

    invalid_keys = {key for aid in reasons for key in defn.activities.get(aid, {}).get('outputData', [])}
    current = engine.variables(inst)
    sources = inst.get('variable_sources') or {}
    values = deepcopy(seed)
    restored, retained, invalidated = [], [], []
    prior_nodes = ancestors(defn, root['activity_id'])
    for key, value in current.items():
        source = sources.get(key) or {}
        producer = rows.get(source.get('id')) if source.get('kind') == 'workitem' else None
        affected = key in invalid_keys or (producer is not None and producer['activity_id'] in reasons)
        if affected:
            invalidated.append(key)
            # The root may overwrite its own input variable. Restore the last
            # valid causal predecessor, not blindly the original instance seed.
            producers = [w for aid, w in latest.items() if aid in prior_nodes and aid not in reasons
                         and w['status'] == 'DONE' and key in defn.activities.get(aid, {}).get('outputData', [])
                         and key in (w.get('output') or {})]
            last_producers = [w for w in producers if not any(w['activity_id'] in ancestors(defn, other['activity_id'])
                                                             for other in producers if other['id'] != w['id'])]
            if len(last_producers) == 1:
                previous = last_producers[0]
                values[key] = deepcopy(previous['output'][key])
                retained.append({'variable': key, 'workitem': previous['id']})
                continue
            if len(last_producers) > 1:
                block('ambiguous_previous_producer', variable=key, workitems=[w['id'] for w in last_producers])
                values.pop(key, None)
                continue
            if key in seed:
                restored.append(key)
            else:
                values.pop(key, None)
            continue
        if source.get('kind') == 'input' and key in seed and seed[key] == value:
            continue
        if (producer is not None and producer['status'] == 'DONE'
                and latest[producer['activity_id']]['id'] == producer['id']
                and source.get('activity') == producer['activity_id']
                and source.get('version') == producer.get('version')
                and key in defn.activities.get(producer['activity_id'], {}).get('outputData', [])
                and key in (producer.get('output') or {}) and producer['output'][key] == value):
            values[key] = deepcopy(value)
            retained.append({'variable': key, 'workitem': producer['id']})
        else:
            values.pop(key, None)
            block('variable_provenance_requires_review', variable=key, source=deepcopy(source))
    # Every approval remains evidence, even if it belongs to another branch.
    approval_view = []
    for row in approvals:
        if row.get('proc_inst_id') != inst['proc_inst_id'] or row.get('tenant_id') != inst.get('tenant_id'):
            raise ValueError('다른 인스턴스/tenant의 승인 기록이 섞였습니다')
        approval_view.append({k: deepcopy(row.get(k)) for k in ('todo_id', 'decision_id', 'status', 'attempts', 'error')})
        if row.get('status') != 'DISCARDED':
            block('approval_requires_review', workitem=row['todo_id'])
    started_services = [w['id'] for w in workitems
                        if defn.activities.get(w['activity_id'], {}).get('type') in engine.SERVICE_TYPES
                        and (w['status'] not in {'TODO', 'CANCELLED'} or w.get('output') or w.get('log'))]
    for wid in started_services:
        block('service_effects_require_review', workitem=wid)
    if current.get('incident') or seed.get('incident'):
        block('incident_rework_effect_contract_pending')
    # The dependency plan can be wider than one control-flow restart. Do not
    # silently leave disconnected, already-consumed branches as dormant TODOs.
    control, queue = set(), [root['activity_id']]
    while queue:
        node = queue.pop()
        if node in control:
            continue
        control.add(node)
        queue.extend(s['target'] for s in defn.outgoing(node))
        queue.extend(e['id'] for e in defn.attached_events(node))
    outside = sorted(set(reasons) - control)
    from . import dependency_schedule
    schedule, schedule_blockers = dependency_schedule.propose(
        defn, inst, workitems, set(reasons), control, root['activity_id'])
    blockers.extend(schedule_blockers)
    roles = sorted({defn.role_endpoint(a.get('role')) for a in defn.activities.values()
                    if a.get('type') in engine.USER_TYPES and defn.role_endpoint(a.get('role'))})
    candidate_sources = {key: {'kind': 'input'} for key in values}
    for entry in retained:
        producer = rows[entry['workitem']]
        candidate_sources[entry['variable']] = {'kind': 'workitem', 'id': producer['id'],
            'activity': producer['activity_id'], 'version': producer['version']}
    affected_work = [w for w in workitems if w['activity_id'] in reasons]
    return {
        'instance': inst['proc_inst_id'], 'definition_id': defn.id, 'version': inst['proc_def_version'],
        'start_workitem': workitem_id, 'affected_nodes': sorted(reasons), 'reasons': reasons,
        'affected_workitems': [{'id': w['id'], 'activity': w['activity_id'], 'status': w['status'],
                                'consumer': w.get('consumer')} for w in affected_work],
        'cancel_workitems': [w['id'] for w in affected_work if w['status'] not in engine.TERMINAL_STATUSES],
        'invalidated_variables': sorted(invalidated), 'restored_input_variables': sorted(restored),
        'retained_outputs': retained, 'candidate_variables': values, 'candidate_sources': candidate_sources,
        'approvals': approval_view, 'started_services': started_services, 'blockers': blockers,
        'dependency_schedule': schedule,
        'snapshot_token': fingerprint({'definition': defn.raw, 'instance': inst,
                                      'workitems': sorted(workitems, key=lambda w: w['id']),
                                      'approvals': sorted(approvals, key=lambda a: a['todo_id'])}),
        'execution_available': not blockers and bool(roles), 'request_roles': roles,
        'scope': '조회는 상태를 변경하지 않습니다. 새 세대 요청은 관측 상태와 담당 역할을 다시 검사합니다. 외부 효과 보상은 수행하지 않습니다.',
    }


def new_generation(defn, inst, workitems, proposal, request_id, now=None, time_scale=1.0):
    """Pure state transition; caller commits rows and immutable receipt atomically."""
    if proposal['blockers']:
        raise ValueError('재작업 검토가 필요합니다: ' + ', '.join(b['code'] for b in proposal['blockers']))
    latest = engine._by_activity(workitems)
    root = next(w for w in workitems if w['id'] == proposal['start_workitem'])
    inst['rework_generation'] = int(inst.get('rework_generation') or 0) + 1
    inst['rework_request_id'] = request_id
    inst['variables_data'] = []
    inst['variable_sources'] = {}
    for key, value in proposal['candidate_variables'].items():
        engine.set_variables(defn, inst, {key: deepcopy(value)}, source=proposal['candidate_sources'][key])
    adv = engine.Advance()
    affected = set(proposal['affected_nodes'])
    flow_state = inst.setdefault('flow_state', {})
    arrivals = flow_state.get('end_arrivals', [])
    # Separate paths can share one end event. Retire the arrival's producing
    # path, not every arrival at an affected endpoint.
    retired = [a for a in arrivals if a['source'] in affected]
    if retired:
        flow_state.setdefault('superseded_end_arrivals', []).append(
            {'request_id': request_id, 'arrivals': deepcopy(retired)})
        flow_state['end_arrivals'] = [a for a in arrivals if a not in retired]
    for row in workitems:
        if row['activity_id'] in affected and row['status'] not in engine.TERMINAL_STATUSES:
            row.update(status='CANCELLED', consumer=None, end_date=engine.now_iso(now),
                       log=(row.get('log') or '') + f'rework superseded: {request_id}; ')
            adv.updated.append(row)
    for aid in defn.activities:
        if aid not in affected:
            continue
        row = engine.new_workitem(defn, inst, defn.activities[aid], now)
        old = latest.get(aid)
        row.update(rework_request_id=request_id, supersedes_id=old['id'] if old else None,
                   rework_count=int((old or {}).get('rework_count') or 0) + 1)
        adv.created.append(row)
    from . import dependency_schedule
    dependency_schedule.install(inst, proposal.get('dependency_schedule'), adv.created, request_id)
    from . import input_bindings
    input_bindings.install(defn, inst, workitems + adv.created, adv.created)
    current = next(w for w in adv.created if w['activity_id'] == root['activity_id'])
    schedule = dependency_schedule.entry(inst, current)
    if schedule is not None:
        schedule['flow_arrived'] = True
    if not dependency_schedule.ready(inst, current, workitems + adv.created):
        inst['current_activity_ids'] = [aid for aid in inst.get('current_activity_ids', []) if aid not in affected]
        return adv
    timers = engine.reach(defn, inst, current, workitems + adv.created, now, time_scale)
    for row in timers:
        row.update(rework_request_id=request_id, supersedes_id=(latest.get(row['activity_id']) or {}).get('id'))
    adv.created.extend(timers)
    adv.reached = [current] + timers
    inst['current_activity_ids'] = [aid for aid in inst.get('current_activity_ids', []) if aid not in affected] + [root['activity_id']]
    return adv
