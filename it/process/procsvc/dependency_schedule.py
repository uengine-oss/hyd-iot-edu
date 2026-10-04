"""Durable rework admission: control arrival AND exact fresh producer completion.

This is a DAG data/reference scheduler. Cross-path conditions restart their
actual preceding review; boundary timers start only when that new review opens.
"""
from copy import deepcopy
import ast
from . import engine


def condition_variables(defn, activity):
    """Conditions judged after this work, traversing gateways but no next task."""
    found,seen,queue=set(),set(),[activity]
    while queue:
        node=queue.pop()
        if node in seen: continue
        seen.add(node)
        for sequence in defn.outgoing(node):
            if sequence.get('condition'):
                found.update(n.id for n in ast.walk(engine.compile_condition(sequence['condition'])) if isinstance(n,ast.Name))
            if sequence['target'] in defn.gateways: queue.append(sequence['target'])
    return found


def control_predecessors(defn, node):
    """Activities whose new completion or attached event must precede arrival."""
    found,seen,queue=set(),set(),[s['source'] for s in defn.sequences if s['target']==node]
    while queue:
        prior=queue.pop()
        if prior in seen: continue
        seen.add(prior)
        if prior in defn.activities:
            found.add(prior)
        elif prior in defn.gateways:
            queue.extend(s['source'] for s in defn.sequences if s['target']==prior)
        else:
            attached=defn.attached_activity(prior)
            if attached: found.add(attached['id'])
    return found


def propose(defn, inst, workitems, affected, control, root):
    outside = affected - control
    if not outside:
        return None, []
    latest = engine._by_activity(workitems)
    by_id = {w['id']:w for w in workitems}
    old_schedule = (inst.get('flow_state') or {}).get('dependency_schedule', {})
    activities = affected & set(defn.activities)
    specs, blockers = {}, []
    for gateway in sorted(affected & set(defn.gateways)):
        if not (control_predecessors(defn,gateway) & activities):
            blockers.append(dict(code='condition_replay_requires_arrival',gateway=gateway))
    for event in sorted(affected & set(defn.events)):
        if defn.events[event]['type'] not in {'startEvent','endEvent'}:
            attached=defn.attached_activity(event)
            if not attached or attached['id'] not in activities:
                blockers.append(dict(code='condition_replay_requires_arrival',event=event))
    for aid in sorted(activities):
        old = latest.get(aid, {})
        required, retained = {}, []
        conditions=condition_variables(defn,aid)
        consumed=conditions | set().union(*(condition_variables(defn,e['id']) for e in defn.attached_events(aid)))
        own_conditions=conditions & set(defn.activities[aid].get('outputData') or [])
        for key in sorted(set(defn.activities[aid].get('inputData') or []) | consumed):
            binding=(defn.activities[aid].get('inputBindings') or {}).get(key)
            if key in (defn.activities[aid].get('outputData') or []) and key not in (defn.activities[aid].get('inputData') or []):
                producers=[]
            elif binding is not None and key not in consumed:
                producers=[binding['activity']] if binding.get('activity') in activities else []
            else:
                producers = sorted(p for p in activities if p != aid and key in (defn.activities[p].get('outputData') or []))
            if len(producers) > 1:
                blockers.append(dict(code='ambiguous_dependency_producer', activity=aid, variable=key, producers=producers))
            elif producers:
                required.setdefault(producers[0], []).append(key)
        for ref in old.get('reference_ids') or []:
            producer = by_id.get(ref)
            if producer and producer['activity_id'] in activities and producer['activity_id'] != aid:
                required.setdefault(producer['activity_id'], [])
            elif producer and producer['activity_id'] != aid:
                if producer['status'] != 'DONE' or latest[producer['activity_id']]['id'] != ref:
                    blockers.append(dict(code='dependency_reference_requires_review', activity=aid, workitem=ref))
                retained.append(dict(workitem=ref, activity=producer['activity_id'],
                                     generation=int(producer.get('generation') or 0), variables=[]))
            elif not producer:
                blockers.append(dict(code='dependency_reference_requires_review', activity=aid, workitem=ref))
        # Rewriting a waiting generation retains its exact admission evidence.
        previous = old_schedule.get(old.get('id'), {})
        arrival=(inst.get('flow_state') or {}).get('activity_arrivals',{}).get(old.get('id'))
        proven=bool(arrival and arrival['activity']==aid and arrival['generation']==int(old.get('generation') or 0))
        admitted = old.get('status') in engine.LIVE_STATUSES | {'DONE'} or previous.get('flow_arrived', False) or proven
        predecessors = control_predecessors(defn, aid)
        is_entry = aid == root or (aid in outside and not (predecessors & activities))
        if is_entry and admitted and not any(s['target'] == aid for s in defn.sequences):
            blockers.append(dict(code='dependency_control_arrival_unavailable', activity=aid))
        if is_entry and old.get('status')=='CANCELLED' and not admitted:
            blockers.append(dict(code='dependency_control_arrival_unavailable',activity=aid,workitem=old['id']))
        specs[aid] = dict(requires=required, flow_arrived=bool(is_entry and admitted),
                          admission_workitem=old.get('id') if is_entry and admitted else None, retained=retained,
                          condition_names=sorted(conditions),condition_dependencies=sorted(consumed),own_conditions=sorted(own_conditions))
    # A dependency/control cycle cannot be satisfied by pretending SUBMITTED is DONE.
    edges = {aid:set(spec['requires']) | (control_predecessors(defn, aid) & activities)
             for aid,spec in specs.items()}
    if specs[root]['requires']:
        blockers.append(dict(code='rework_root_dependency_requires_review', activity=root))
    remaining = set(edges)
    while remaining:
        ready = {a for a in remaining if not (edges[a] & remaining)}
        if not ready:
            blockers.append(dict(code='dependency_cycle_requires_review', activities=sorted(remaining)))
            break
        remaining -= ready
    return specs, blockers


def install(inst, specs, created, request_id):
    if specs is None:
        return
    state = inst.setdefault('flow_state', {})
    schedule = state.setdefault('dependency_schedule', {})
    by_activity = {w['activity_id']:w for w in created}
    retired = {wid:entry for wid,entry in schedule.items() if entry['activity'] in by_activity}
    if retired:
        state.setdefault('superseded_dependency_schedules', []).append(dict(request_id=request_id, entries=deepcopy(retired)))
        for wid in retired: schedule.pop(wid)
    for aid,spec in specs.items():
        row = by_activity[aid]
        schedule[row['id']] = dict(activity=aid, generation=row['generation'], request_id=request_id,
            flow_arrived=spec['flow_arrived'], admission_workitem=spec['admission_workitem'], state='WAITING',
            condition_names=spec.get('condition_names',[]),own_conditions=spec.get('own_conditions',[]),
            requires=[dict(workitem=by_activity[p]['id'], activity=p, generation=by_activity[p]['generation'], variables=keys,
                           condition_variables=sorted(set(keys)&set(spec.get('condition_dependencies',[]))))
                      for p,keys in spec['requires'].items()] + deepcopy(spec['retained']))


def entry(inst, row):
    return (inst.get('flow_state') or {}).get('dependency_schedule', {}).get(row['id'])


def ready(inst, row, workitems):
    spec = entry(inst, row)
    if spec is None:
        return True
    if not spec['flow_arrived']:
        return False
    by_id = {w['id']:w for w in workitems}
    latest = engine._by_activity(workitems)
    missing = []
    for key in spec.get('initial_inputs',[]):
        if not isinstance(inst.get('initial_variables'),dict) or key not in inst['initial_variables']:
            missing.append(dict(variable=key,reason='initial_input_unavailable'))
    for dep in spec['requires']:
        producer = by_id.get(dep['workitem'])
        valid = (producer and producer['status'] == 'DONE' and producer['generation'] == dep['generation']
                 and producer['activity_id'] == dep['activity']
                 and producer.get('tenant_id') == inst.get('tenant_id')
                 and producer['proc_inst_id'] == inst['proc_inst_id']
                 and producer['version'] == inst['proc_def_version']
                 and latest[dep['activity']]['id'] == producer['id'])
        if not valid:
            missing.append(dict(workitem=dep['workitem'], reason='producer_not_done_or_superseded'))
            continue
        for key in set(dep['variables']) | set(dep.get('condition_variables',[])):
            source = (inst.get('variable_sources') or {}).get(key) or {}
            if (key not in (producer.get('output') or {}) or
                    ((dep.get('mode')!='bound' or key in dep.get('condition_variables',[])) and (source.get('id') != producer['id']
                     or key not in engine.variables(inst) or engine.variables(inst)[key] != producer['output'][key]))):
                missing.append(dict(workitem=dep['workitem'], variable=key, reason='fresh_output_unavailable'))
    spec['waiting_for'] = missing
    return not missing


def opened(inst, row):
    spec = entry(inst, row)
    if spec is not None:
        spec['state'] = 'OPENED'
        row['reference_ids'] = list(dict.fromkeys(row.get('reference_ids', []) + [d['workitem'] for d in spec['requires']]))


def completion_missing(defn, inst, row, workitems):
    """A submitted recheck cannot default from a missing fresh condition value."""
    spec=entry(inst,row); parent=None
    if spec is None:
        attached=defn.attached_activity(row['activity_id'])
        parent=engine._by_activity(workitems).get(attached['id']) if attached else None
        spec=entry(inst,parent) if parent else None
    if spec is None: return []
    values=engine.variables(inst)
    names=condition_variables(defn,row['activity_id']) if parent else spec.get('condition_names',[])
    missing=[key for key in names if key not in values]
    producer=parent or row
    own=set(names)&set(defn.activities.get(producer['activity_id'],{}).get('outputData') or [])
    missing.extend(key for key in own if key not in (producer.get('output') or {}))
    return sorted(set(missing))


def waiting(inst, workitems):
    return any((entry(inst,w) or {}).get('flow_arrived') and w['status'] == 'TODO' for w in workitems)
