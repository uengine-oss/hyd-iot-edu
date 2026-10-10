"""Publishing executable definitions, with their forms inside the immutable version.

Product reference: vue3 ProcessGPTBackend.putRawDefinition/getExecutionDefinition.
HYD deliberately requires an exact version and rejects unsupported execution shapes.
"""
from copy import deepcopy
from hydcommon.process_contracts import pinned_form, validate_fields
from . import engine, alert_policy, effect_parts, approval_part

# C2: 승인 뒤 실행 부품(effect_parts.TOOLS — MCP 호출 · ERP 발주 · 시간 대기 · 정비 수행 모사 · 입고 확인)도 process 가 실행하는 서비스다
SERVICE_TOOLS = {'incident:command', 'incident:reobserve', 'enterprise:WO_CREATE', *effect_parts.TOOLS}
# C2: 승인 경로가 승인한 카드의 발주 값(공급사 · 부품 · 수량 · 단가 · 금액)을 확정해 넣는다 — 금액 분기(구매팀장 추가 승인)의 근거라 task 가 낼 수 없다
# 캡스톤 G1: 일반 사람 승인(approval_part)이 고른 안의 사본(approved_option)도 승인 경로만 넣는다
PROTECTED_OUTPUTS = {'incident','commands','approved_by','approved_by_name','approved_role','chosen_option', *approval_part.SERVER_VALUES,
                     *effect_parts.PURCHASE_VALUES}


def validate_definition(raw):
    if not isinstance(raw, dict):
        raise ValueError('정의는 JSON 객체여야 합니다')
    alert_policy.validate(raw)
    for key in ('processDefinitionId', 'processDefinitionName', 'version'):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError(f'{key}는 비어 있지 않은 문자열이어야 합니다')
    if not isinstance(raw.get('forms'), dict):
        raise ValueError('forms에 버전별 폼 계약을 포함해야 합니다 (폼이 없으면 {})')
    all_ids = []
    for collection in ('activities','events','gateways','sequences','roles','data'):
        values = raw.get(collection, [])
        if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
            raise ValueError(f'{collection}은 객체 목록이어야 합니다')
        field = 'name' if collection in ('roles','data') else 'id'
        ids = [v.get(field) for v in values]
        if any(not isinstance(i,str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
            raise ValueError(f'{collection}의 {field}가 없거나 중복됩니다')
        if collection in ('activities','events','gateways'):
            all_ids.extend(ids)
    if len(set(all_ids)) != len(all_ids):
        raise ValueError('흐름 노드 ID는 정의 내에서 유일해야 합니다')
    for a in raw.get('activities',[]):
        for field in ('inputData','outputData','attachedEvents'):
            values=a.get(field,[])
            if not isinstance(values,list) or any(not isinstance(v,str) for v in values) or len(set(values))!=len(values):
                raise ValueError(f'{field}는 중복 없는 문자열 목록이어야 합니다')
    for s in raw.get('sequences',[]):
        if s.get('condition') is not None and not isinstance(s['condition'],str):
            raise ValueError('분기 condition은 문자열이어야 합니다')
        props=engine._properties(s)
        if 'priority' in props and type(props['priority']) is not int:
            raise ValueError('분기 priority는 정수여야 합니다')
        if 'default' in props and type(props['default']) is not bool:
            raise ValueError('분기 default는 boolean이어야 합니다')
    _normalize_agent_activities(raw)
    try:
        defn = engine.Definition.from_dict(deepcopy(raw))
    except (KeyError, TypeError, SyntaxError) as e:
        raise ValueError(f'정의 구조가 올바르지 않습니다: {e}') from e
    for form in raw['forms'].values():
        if not isinstance(form, dict):
            raise ValueError('폼은 fields_json을 가진 객체여야 합니다')
        validate_fields(form.get('fields_json'))
        if any(f['key'] == '__human_input__' for f in form['fields_json']):
            raise ValueError('__human_input__은 에이전트 질문 제어용 예약 필드입니다')
    from . import input_bindings
    input_bindings.validate(defn)
    for a in defn.activities.values():
        kind = a['type']
        if PROTECTED_OUTPUTS.intersection(a.get('outputData') or []):
            raise ValueError('Incident와 승인 명령 값은 서버 승인 경로에서만 만들 수 있습니다')
        if kind not in {'userTask','manualTask','serviceTask'}:
            raise ValueError(f'아직 실행을 지원하지 않는 활동 타입: {kind}')
        if kind == 'serviceTask':
            if a.get('tool') not in SERVICE_TOOLS:
                raise ValueError(f"지원하지 않는 서비스 도구: {a.get('tool')}")
            if a.get('agentMode') not in engine.NO_MODE or a.get('orchestration') not in (None,'hyd-process'):
                raise ValueError('서비스 작업은 hyd-process에서 실행합니다')
            effect_parts.validate(a)
        else:
            form = pinned_form(raw, a.get('tool'))
            if form is None:
                raise ValueError(f"활동 {a['id']}에는 formHandler 도구와 버전별 폼이 필요합니다")
            fields = {f['key'] for f in form['fields_json']}
            if fields != set(a.get('outputData') or []):
                raise ValueError(f"활동 {a['id']}의 outputData와 폼 key가 다릅니다")
            if a.get('tool') == approval_part.TOOL:
                approval_part.validate(a)
                approval_part.validate_form(form, a['id'])
            if engine.is_agent(a):
                if a.get('orchestration') != engine.AGENT_ORCH:
                    raise ValueError(f"에이전트 활동 {a['id']}: HYD는 orchestration {engine.AGENT_ORCH}만 실행합니다 ({a.get('orchestration')})")
                if a.get('agent') is not None and (not isinstance(a['agent'], str) or not a['agent'].strip()):
                    raise ValueError(f"에이전트 활동 {a['id']}의 agent는 비어 있지 않은 문자열이어야 합니다")
            elif a.get('orchestration') not in engine.NO_MODE:
                raise ValueError('사람 작업에는 orchestration을 지정할 수 없습니다')
    for g in defn.gateways.values():
        if g.get('type') == 'parallelGateway':
            # A100: a parallel split takes every outgoing flow (no conditions); a parallel join (≥2 incoming) waits for every
            # incoming path, so each incoming source must be an activity or an event whose row can finish (not a gateway).
            if any(s.get('condition') for s in defn.outgoing(g['id'])):
                raise ValueError(f"병렬 게이트웨이 {g['id']}의 나가는 흐름에는 조건을 둘 수 없습니다 (모든 가지를 동시에 시작)")
            if len(defn.incoming(g['id'])) > 1 and any(s['source'] in defn.gateways for s in defn.incoming(g['id'])):
                raise ValueError(f"병렬 합류 {g['id']}로 들어오는 흐름의 출발은 활동 또는 이벤트여야 합니다 (게이트웨이 직결 불가)")
        elif g.get('type') != 'exclusiveGateway':
            raise ValueError('등록 경로는 현재 exclusiveGateway와 parallelGateway만 검증되었습니다')
    for e in defn.events.values():
        if e.get('type') not in {'startEvent','endEvent','boundaryEvent'}:
            raise ValueError(f"지원하지 않는 이벤트: {e.get('type')}")
        if e['type'] == 'boundaryEvent':
            if e.get('eventDefinition') != 'timer' or not defn.attached_activity(e['id']):
                raise ValueError('boundaryEvent는 활동에 연결된 timer여야 합니다')
            if engine.iso_duration_seconds(e.get('timer')) <= 0:
                raise ValueError('timer 기간은 0보다 커야 합니다')
            if 'cancelActivity' in e and not isinstance(e['cancelActivity'], bool):
                raise ValueError('boundaryEvent cancelActivity는 true/false입니다 (false = 멈추지 않는 알림 타이머)')
    # Loop re-entry exists in the engine; joins/cancellation across iterations still
    # need integration coverage before the public registration contract accepts it.
    # B3: a definition that declares loopPolicy "guarded" (bpmn_import writes it for a drawn back edge) is checked by
    # _guarded_loops instead — every cycle leaves through an exclusive gateway and holds no parallel gateway.
    visiting, visited = set(), set()
    def visit(n):
        if n in visiting:
            if raw.get('loopPolicy') == 'guarded':
                return
            raise ValueError('등록 경로의 반복 실행은 아직 검증되지 않았습니다')
        if n in visited:
            return
        visiting.add(n)
        for s in defn.outgoing(n):
            visit(s['target'])
        visiting.remove(n); visited.add(n)
    for n in all_ids:
        visit(n)
    if raw.get('loopPolicy') == 'guarded':
        _guarded_loops(defn)
    elif raw.get('loopPolicy') is not None:
        raise ValueError("loopPolicy는 'guarded'만 지원합니다")
    if not any(e['type'] == 'endEvent' for e in defn.events.values()):
        raise ValueError('endEvent가 필요합니다')
    _static_connectivity(defn, all_ids)
    _condition_variables(defn)
    return defn


def _normalize_agent_activities(raw):
    """A116 (r14 B5): store agent activities in the product's shape — userTask + agentMode DRAFT|COMPLETE + orchestration —
    so a definition made with the ProcessGPT designer registers here unchanged and a definition made here runs on the
    product's polling service (which handles userTask/manualTask only; a businessRuleTask would never be picked up).
    `businessRuleTask` + agentMode (HYD's shape before A116) is accepted and rewritten; agentMode none/null/'' is dropped;
    an agent activity without orchestration gets cliagents (the product would default to crewai-deep-research)."""
    for a in raw.get('activities', []):
        if not isinstance(a, dict):
            continue
        if a.get('agentMode') in engine.NO_MODE:
            a.pop('agentMode', None)
        elif isinstance(a.get('agentMode'), str) and a['agentMode'].upper() in engine.AGENT_MODES:
            a['agentMode'] = a['agentMode'].upper()
        else:
            raise ValueError(f"활동 {a.get('id')}의 agentMode는 none, DRAFT, COMPLETE 중 하나여야 합니다")
        if a.get('orchestration') in engine.NO_MODE:
            a.pop('orchestration', None)
        if a.get('type') == 'businessRuleTask':
            if 'agentMode' not in a:
                raise ValueError(f"활동 {a.get('id')}: businessRuleTask는 agentMode DRAFT/COMPLETE가 있는 에이전트 작업일 때만 "
                                 "userTask + agentMode로 등록합니다 (제품 엔진은 businessRuleTask를 실행하지 않습니다)")
            a['type'] = 'userTask'
        if a.get('type') in engine.USER_TYPES and 'agentMode' in a and 'orchestration' not in a:
            a['orchestration'] = engine.AGENT_ORCH


def _condition_variables(defn):
    """A098 (bpmn-process-generation-skill 08-reference-info: a gateway condition may only read a variable some earlier
    task writes). Every name a sequence condition reads must be a declared process variable (data) that an activity
    produces (outputData) or the server sets (PROTECTED_OUTPUTS); otherwise the gateway would judge on a value that
    can never exist and the instance would stall at 'cannot proceed'.

    A143 (remaining-sweep 19, D01 "outputData of the activity before the gateway"): the producer must also be able to run
    before the gateway judges. HYD allows a producer on another branch of the same instance (condition-recheck-v1: `a` on
    a parallel path writes x, `g` after `b` reads it — the engine waits for it, docs/rework-conditions.md), so the rule is
    not "ancestor of the gateway" but "reachable from the start without passing through the gateway". A variable whose
    every producer sits behind the gateway (reachable only through it) can never exist when the gateway first judges,
    and the instance would wait forever."""
    import ast
    produced = {o for a in defn.activities.values() for o in (a.get('outputData') or [])} | PROTECTED_OUTPUTS
    host_of = {ev['id']: a['id'] for a in defn.activities.values() for ev in defn.attached_events(a['id'])}
    def reachable_without(blocked):
        reach, stack = set(), [e['id'] for e in defn.start_events()]
        while stack:
            n = stack.pop()
            if n in reach or n == blocked:
                continue
            reach.add(n)
            stack.extend([t['target'] for t in defn.outgoing(n)] + [ev for ev, host in host_of.items() if host == n])
        return reach
    for s in defn.sequences:
        cond = s.get('condition')
        if not cond:
            continue
        names = {n.id for n in ast.walk(engine.compile_condition(cond)) if isinstance(n, ast.Name)} - {'True', 'False', 'None'}
        undeclared = sorted(n for n in names if n not in defn.data)
        if undeclared:
            raise ValueError(f"분기 {s.get('id')}의 조건이 선언되지 않은 변수를 읽습니다: {', '.join(undeclared)} (data에 선언)")
        unproduced = sorted(n for n in names if n not in produced)
        if unproduced:
            raise ValueError(f"분기 {s.get('id')}의 조건 변수 {', '.join(unproduced)}를 어떤 활동도 내지 않습니다 (outputData)")
        gateway = s['source']
        before = reachable_without(gateway)
        producers = {n: sorted(a['id'] for a in defn.activities.values() if n in (a.get('outputData') or [])) for n in names - PROTECTED_OUTPUTS}
        behind = sorted(n for n, acts in producers.items() if acts and not any(a in before for a in acts))
        if behind:
            raise ValueError(f"분기 {s.get('id')}의 조건 변수 {', '.join(behind)}는 게이트웨이 {gateway} 뒤의 활동"
                             f"({', '.join(a for n in behind for a in producers[n])})만 내므로 판정 시점에 존재할 수 없습니다")


def _static_connectivity(defn, all_ids):
    """A096 (process-gpt-bpmn-extractor process_validator._static_check · bpmn-process-generation-skill, R13 2차): a
    definition is refused when a node cannot be reached from the start, cannot reach an end, or an endEvent is never
    entered. A boundary event (activity.attachedEvents or event.attachedTo) is reached through its host activity. The
    extractor's fourth rule (no fan-out off a non-gateway) is `_gatewayless_splits` (A115)."""
    host_of = {ev['id']: a['id'] for a in defn.activities.values() for ev in defn.attached_events(a['id'])}
    def next_of(n):
        return [s['target'] for s in defn.outgoing(n)] + [ev for ev, host in host_of.items() if host == n]
    reach, stack = set(), [e['id'] for e in defn.start_events()]
    while stack:
        n = stack.pop()
        if n in reach:
            continue
        reach.add(n); stack.extend(next_of(n))
    unreached = [n for n in all_ids if n not in reach]
    if unreached:
        raise ValueError(f"시작 이벤트에서 도달할 수 없는 노드: {', '.join(unreached)}")
    ends = {e['id'] for e in defn.events.values() if e['type'] == 'endEvent'}
    # B3: backward reachability from the ends (a memoised DFS marked a node on a guarded loop dead when its only way out
    # went back through a node already on the trail)
    pred = {}
    for n in all_ids:
        for m in next_of(n):
            pred.setdefault(m, []).append(n)
    alive, stack = set(), list(ends)
    while stack:
        n = stack.pop()
        if n in alive:
            continue
        alive.add(n); stack.extend(pred.get(n, []))
    dead = [n for n in all_ids if n not in alive]
    if dead:
        raise ValueError(f"종료 이벤트에 이르지 못하는 노드: {', '.join(dead)}")
    entered = {s['target'] for s in defn.sequences}
    never = sorted(e for e in ends if e not in entered)
    if never:
        raise ValueError(f"들어오는 흐름이 없는 endEvent: {', '.join(never)}")
    _gatewayless_splits(defn)


def _gatewayless_splits(defn):
    """A115 (r14 A6; bpmn-extractor process_validator._static_check `uncontrolled_split`). The engine fires every
    non-false outgoing flow of a non-gateway node, so a split without a gateway that meets again downstream runs the
    meeting activity once per branch (g1_probe: D DONE, then D created again when C finishes). The extractor only warns
    (score 1, fed to its repair loop) and skips start events; registration here refuses it, start events included,
    because the duplicate run happens the same way from a start event. Branches go through an exclusiveGateway
    (choose one) or a parallelGateway (all, joined by a parallel join)."""
    for n in [*defn.activities, *defn.events]:
        targets = sorted({s['target'] for s in defn.outgoing(n)})
        if len(targets) > 1:
            raise ValueError(f"노드 {n}가 게이트웨이 없이 {len(targets)}갈래로 나뉩니다 (→ {', '.join(targets)}). "
                             "갈림은 exclusiveGateway(하나 선택) 또는 parallelGateway(모두 진행)를 거쳐야 합니다")


def _guarded_loops(defn):
    """B3 (bpmn.io import, engine re-entry engine.py `_advance` "re-entry (loop) → a fresh row"): a cycle is accepted only
    when one of its exclusive gateways has a flow leaving the cycle (the loop can end) and it holds no parallel gateway
    (a join across iterations has no integration coverage). Effects inside a cycle need a fresh human approval each time —
    bpmn_import checks that before registration; the engine's Incident path refuses a second command anyway."""
    nodes = [*defn.activities, *defn.events, *defn.gateways]
    host_of = {ev['id']: a['id'] for a in defn.activities.values() for ev in defn.attached_events(a['id'])}
    succ = {n: [s['target'] for s in defn.outgoing(n)] + [ev for ev, host in host_of.items() if host == n] for n in nodes}
    index, low, on, stack, comps, counter = {}, {}, set(), [], [], [0]
    def strong(v):
        index[v] = low[v] = counter[0]; counter[0] += 1
        stack.append(v); on.add(v)
        for w in succ.get(v, []):
            if w not in index:
                strong(w); low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = set()
            while True:
                w = stack.pop(); on.discard(w); comp.add(w)
                if w == v:
                    break
            if len(comp) > 1 or v in succ.get(v, []):
                comps.append(comp)
    for v in nodes:
        if v not in index:
            strong(v)
    for comp in comps:
        exits = [n for n in comp if defn.gateways.get(n, {}).get('type') == 'exclusiveGateway'
                 and any(s['target'] not in comp for s in defn.outgoing(n))]
        if not exits:
            raise ValueError(f"반복 경로({', '.join(sorted(comp))})에서 빠져나갈 배타 게이트웨이가 없습니다")
        if any(defn.gateways.get(n, {}).get('type') == 'parallelGateway' for n in comp):
            raise ValueError(f"반복 경로({', '.join(sorted(comp))}) 안의 병렬 게이트웨이는 아직 검증되지 않았습니다")
