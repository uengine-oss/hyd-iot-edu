"""Explicit HYD input source contract, distinct from the product's optional read list.

inputBindings maps an inputData key to {activity: producer_id} or {initial: true}.
The binding requires source presence and preserves the value used when work opens.
"""
from copy import deepcopy
from . import engine


def validate(defn):
    edges={n:[] for n in list(defn.activities)+list(defn.events)+list(defn.gateways)}
    for s in defn.sequences: edges[s['source']].append(s['target'])
    for aid in defn.activities:
        edges[aid].extend(e['id'] for e in defn.attached_events(aid))
    reachable,queue=set(),[defn.start_events()[0]['id']]
    while queue:
        node=queue.pop()
        if node in reachable: continue
        reachable.add(node); queue.extend(edges[node])
    for aid,a in defn.activities.items():
        bindings=a.get('inputBindings',{})
        if not isinstance(bindings,dict): raise ValueError('inputBindings는 입력별 출처 객체여야 합니다')
        for key,source in bindings.items():
            if key not in (a.get('inputData') or []) or not isinstance(source,dict):
                raise ValueError('inputBindings는 inputData의 입력과 명시 출처가 필요합니다')
            if source=={'initial':True} and type(source.get('initial')) is bool:
                continue
            if set(source)!={'activity'} or not isinstance(source['activity'],str):
                raise ValueError('inputBindings 출처는 activity 또는 initial:true 하나여야 합니다')
            producer=source['activity']
            if producer==aid or producer not in defn.activities or key not in (defn.activities[producer].get('outputData') or []):
                raise ValueError('inputBindings 생산 작업과 선언 출력이 일치해야 합니다')
            if producer not in reachable:
                raise ValueError('inputBindings 생산 작업은 시작 흐름에서 도달 가능해야 합니다')
            edges[producer].append(aid)
    active,seen=set(),set()
    def visit(n):
        if n in active: raise ValueError('inputBindings와 제어 흐름에 순환 의존이 있습니다')
        if n in seen: return
        active.add(n)
        for nxt in edges[n]: visit(nxt)
        active.remove(n); seen.add(n)
    # Existing loop validation owns definitions without bindings.
    if any(a.get('inputBindings') for a in defn.activities.values()):
        for n in edges: visit(n)


def install(defn,inst,workitems,created):
    latest=engine._by_activity(workitems)
    for row in created:
        bindings=defn.activities.get(row['activity_id'],{}).get('inputBindings') or {}
        if not bindings: continue
        schedule=inst.setdefault('flow_state',{}).setdefault('dependency_schedule',{})
        spec=schedule.setdefault(row['id'],dict(activity=row['activity_id'],generation=row['generation'],
            request_id=row.get('rework_request_id'),flow_arrived=False,admission_workitem=None,state='WAITING',requires=[]))
        # Mandatory bindings replace variable-name inference, not actual control references.
        for dep in spec['requires']:
            dep['variables']=[k for k in dep['variables'] if k not in bindings]
        spec['initial_inputs']=[]
        for key,source in bindings.items():
            if source.get('initial') is True:
                spec['initial_inputs'].append(key)
            else:
                producer=latest.get(source['activity'])
                if producer is None:
                    raise ValueError('inputBindings 생산 작업은 시작 흐름에서 도달 가능해야 합니다')
                dep=dict(workitem=producer['id'],activity=producer['activity_id'],generation=producer['generation'],
                         variables=[key],mode='bound')
                if dep not in spec['requires']: spec['requires'].append(dep)


def snapshot(defn,inst,row,workitems,inputs):
    bindings=defn.activities[row['activity_id']].get('inputBindings') or {}
    if not bindings: return inputs
    spec=inst['flow_state']['dependency_schedule'][row['id']]
    by_id={w['id']:w for w in workitems}
    sources={k:deepcopy((inst.get('variable_sources') or {}).get(k)) for k in inputs}
    for key,source in bindings.items():
        if source.get('initial') is True:
            inputs[key]=deepcopy(inst['initial_variables'][key]); sources[key]={'kind':'input'}
        else:
            dep=next(d for d in spec['requires'] if d.get('mode')=='bound' and key in d['variables'])
            producer=by_id[dep['workitem']]
            inputs[key]=deepcopy(producer['output'][key])
            sources[key]=dict(kind='workitem',id=producer['id'],activity=producer['activity_id'],
                              generation=producer['generation'],version=producer['version'])
    inst['flow_state'].setdefault('input_snapshots',{})[row['id']]=dict(inputs=deepcopy(inputs),sources=sources)
    return inputs
