"""Publishing executable definitions, with their forms inside the immutable version.

Product reference: vue3 ProcessGPTBackend.putRawDefinition/getExecutionDefinition.
HYD deliberately requires an exact version and rejects unsupported execution shapes.
"""
import json
from copy import deepcopy
from hydcommon.process_contracts import pinned_form, validate_fields
from . import engine, alert_policy, effect_parts, approval_part

# C2: 승인 뒤 실행 부품(effect_parts.TOOLS — MCP 호출 · ERP 발주 · 시간 대기 · 정비 수행 모사 · 입고 확인)도 process 가 실행하는 서비스다
SERVICE_TOOLS = {'incident:command', 'incident:reobserve', 'enterprise:WO_CREATE', *effect_parts.TOOLS}
# C2: 승인 경로가 승인한 카드의 발주 값(공급사 · 부품 · 수량 · 단가 · 금액)을 확정해 넣는다 — 금액 분기(구매팀장 추가 승인)의 근거라 task 가 낼 수 없다
# 캡스톤 G1: 일반 사람 승인(approval_part)이 고른 안의 사본(approved_option)도 승인 경로만 넣는다
PROTECTED_OUTPUTS = {'incident','commands','approved_by','approved_by_name','approved_role','chosen_option', *approval_part.SERVER_VALUES,
                     *effect_parts.PURCHASE_VALUES}


#: 정의 하나의 크기 상한(P1-16 — 큰 JSON 하나가 정의 판본 표에 남아 판본 목록 · 비교를 무겁게 하고, 긴 정의는 재귀 깊이 한도로 사유 없는 500 이었다).
#: 제공 정의 · 수업 흐름은 노드 30개 · 글 40,000자 안쪽이다(test_definition_registry 가 잰다).
MAX_NODES = 500
MAX_DEFINITION_CHARS = 500_000
_COLLECTION_WORDS = {'activities': '단계', 'events': '이벤트', 'gateways': '분기점', 'sequences': '연결'}


def validate_definition(raw):
    """등록 문지기 하나(JSON 등록 · 흐름 가져오기 · 배포 · 판본 상태가 모두 이것을 부른다). raw 는 고치지 않고, 저장할 모양(에이전트 단계를
    제품 모양으로 맞춘 사본)을 담은 Definition 을 돌려준다(defn.raw). 실패는 무엇이 · 어디서를 담은 ValueError."""
    if not isinstance(raw, dict):
        raise ValueError('정의는 JSON 객체여야 합니다')
    try:
        size = len(json.dumps(raw, ensure_ascii=False))
    except (TypeError, ValueError) as e:
        raise ValueError(f'정의를 JSON 으로 쓸 수 없습니다: {e}') from e
    if size > MAX_DEFINITION_CHARS:
        raise ValueError(f'정의가 너무 큽니다({size:,}자 — 한도 {MAX_DEFINITION_CHARS:,}자). 흐름을 나누거나 설명을 줄이세요')
    raw = deepcopy(raw)
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
        if collection in ('activities', 'events', 'gateways', 'sequences') and len(values) > MAX_NODES:
            raise ValueError(f'{_COLLECTION_WORDS[collection]}이(가) {len(values)}개로 한도 {MAX_NODES}개를 넘습니다. 흐름을 나누세요')
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
        props=engine.sequence_properties(s)
        if 'priority' in props and type(props['priority']) is not int:
            raise ValueError('분기 priority는 정수여야 합니다')
        if 'default' in props and type(props['default']) is not bool:
            raise ValueError('분기 default는 boolean이어야 합니다')
    _normalize_agent_activities(raw)
    try:
        defn = engine.Definition.from_dict(raw)
    except (KeyError, TypeError) as e:
        raise ValueError(f'정의 구조가 올바르지 않습니다: {e}') from e
    for form in raw['forms'].values():
        if not isinstance(form, dict):
            raise ValueError('폼은 fields_json을 가진 객체여야 합니다')
        validate_fields(form.get('fields_json'))
        if any(f['key'] == '__human_input__' for f in form['fields_json']):
            raise ValueError('__human_input__은 에이전트 질문 제어용 예약 필드입니다')
    for a in defn.activities.values():
        kind = a['type']
        if PROTECTED_OUTPUTS.intersection(a.get('outputData') or []):
            raise ValueError('Incident와 승인 명령 값은 서버 승인 경로에서만 만들 수 있습니다')
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
        else:
            _exclusive_shape(defn, g)
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
    # Loop re-entry exists in the engine; joins/cancellation across iterations still need integration coverage before the
    # public registration contract accepts it. B3: a definition that declares loopPolicy "guarded" (bpmn_import writes it for
    # a drawn back edge) is checked by _guarded_loops instead — every cycle leaves through an exclusive gateway and holds no
    # parallel gateway. 순회는 반복문이다(P1-16: 재귀는 긴 직선 흐름 1,600단계에서 RecursionError 로 사유 없는 500 이었다).
    policy = raw.get('loopPolicy')
    if policy is not None and policy != 'guarded':
        raise ValueError("loopPolicy는 'guarded'만 지원합니다")
    if policy is None and _has_cycle(defn, all_ids):
        raise ValueError('등록 경로의 반복 실행은 아직 검증되지 않았습니다 — 되돌아가는 선이 있는 흐름은 흐름 가져오기로 등록하세요(반복 검사를 거친다)')
    _exclusive_after_boundary_joins(defn)
    if policy == 'guarded':
        _guarded_loops(defn)
    if not any(e['type'] == 'endEvent' for e in defn.events.values()):
        raise ValueError('endEvent가 필요합니다')
    _static_connectivity(defn, all_ids)
    _condition_variables(defn)
    return defn


def _normalize_agent_activities(raw):
    """A116 (r14 B5): store agent activities in the product's shape — userTask + agentMode DRAFT|COMPLETE + orchestration —
    so a definition made with the ProcessGPT designer registers here unchanged and a definition made here runs on the
    product's polling service (which handles userTask/manualTask only). agentMode none/null/'' is dropped; an agent activity
    without orchestration gets cliagents (the product would default to crewai-deep-research). businessRuleTask(A116 전 HYD 모양)는
    받지 않는다 — 활동 종류 검사가 「userTask + agentMode 로 쓰세요」로 거절한다(옛 모양을 고쳐 받던 호환 갈래를 지움, P1-20)."""
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
        if a.get('type') in engine.USER_TYPES and 'agentMode' in a and 'orchestration' not in a:
            a['orchestration'] = engine.AGENT_ORCH


def _is_default(seq) -> bool:
    """배타 분기의 「그 밖의 경우」 선: properties.default 가 참이거나 조건이 없는 선(엔진 _allowed_targets 와 같은 기준)."""
    return engine.sequence_properties(seq).get('default') is True or not seq.get('condition')


def _exclusive_shape(defn, g):
    """배타 분기의 모양(P1-36 · #16). 엔진은 참인 조건 선 하나(여럿이면 priority · id 순)를, 없으면 기본 선을 탄다.
    ① 기본 선은 하나뿐이어야 한다 — 둘 이상이면 엔진이 첫째를 조용히 골랐다(흐름 가져오기는 이미 거절했다 — 그 규칙이 이 한 곳으로 왔다).
    ② 분기 앞이 단계가 아니면(다른 분기 · 시작 · 경계 타이머) 기본 선이 꼭 있어야 한다 — 단계 뒤 분기는 조건이 모두 거짓이면 그 단계가
       「진행 멈춤」(PENDING)으로 남아 사람이 다시 수행 · 닫기로 다룰 수 있지만, 앞이 분기 · 이벤트면 멈출 행이 없거나(흐름이 오류 없이 사라짐)
       아무도 닫을 수 없는 이벤트 행이 남는다."""
    name = g.get('name') or g['id']
    defaults = [s['id'] for s in defn.outgoing(g['id']) if _is_default(s)]
    if len(defaults) > 1:
        raise ValueError(f"분기 {name}에 「그 밖의 경우」 선(조건 없는 선 · 기본 선)이 {len(defaults)}개입니다({', '.join(defaults)}) — 하나만 두세요")
    feeders = [s['source'] for s in defn.incoming(g['id']) if s['source'] not in defn.activities]
    if feeders and not defaults:
        raise ValueError(f"분기 {name}는 단계가 아닌 곳({', '.join(sorted(set(feeders)))})에서 바로 이어지므로 「그 밖의 경우」(조건 없는 기본 선)가 "
                         "하나 있어야 합니다 — 조건이 모두 맞지 않을 때 흐름이 갈 곳이 없습니다")


def _forward(defn, starts, stop):
    """starts 에서 앞으로 닿는 노드(붙은 이벤트 포함), stop 노드에서 멈춘다."""
    host_of = {ev['id']: a['id'] for a in defn.activities.values() for ev in defn.attached_events(a['id'])}
    seen, stack = set(), list(starts)
    while stack:
        n = stack.pop()
        if n in seen or n == stop:
            continue
        seen.add(n)
        stack.extend([s['target'] for s in defn.outgoing(n)] + [ev for ev, host in host_of.items() if host == n])
    return seen


def _exclusive_after_boundary_joins(defn):
    """P1-07: 한 단계와 그 단계를 끊는 경계 타이머는 서로를 취소한다(단계가 끝나면 타이머 취소, 타이머가 울리면 단계 취소). 둘의 길이 같은
    병렬 합류의 다른 입구로 들어가면 그 합류는 처음부터 열릴 수 없다 — 등록하면 실행 때 아무도 닫지 않았는데 처리 건이 끝났다."""
    for a in defn.activities.values():
        for ev in defn.attached_events(a['id']):
            if ev.get('cancelActivity') is False:
                continue
            for g in defn.gateways.values():
                if not engine.is_parallel_join(defn, g['id']):
                    continue
                # 단계가 끝난 길(단계 자신 + 나가는 선 뒤)과 시한이 울린 길(시한 자신 + 그 뒤) — 단계에서 붙은 시한으로 건너가지 않는다
                done = {a['id']} | _forward(defn, [s['target'] for s in defn.outgoing(a['id'])], g['id'])
                fired = {ev['id']} | _forward(defn, [s['target'] for s in defn.outgoing(ev['id'])], g['id'])
                entries = {s['source'] for s in defn.incoming(g['id'])}
                if entries & (done - fired) and entries & (fired - done):
                    raise ValueError(f"병렬 합류 {g.get('name') or g['id']}에 단계 {a.get('name') or a['id']}의 길과 그 단계를 끊는 시한 "
                                     f"{ev.get('name') or ev['id']}의 길이 함께 들어갑니다 — 둘 중 하나만 일어나므로 합류가 열리지 않습니다. "
                                     "시한 길은 배타 분기로 모으거나 따로 끝나게 그리세요")


def _has_cycle(defn, nodes) -> bool:
    """되돌아가는 선이 있는가(반복문 DFS — 깊은 흐름에서도 재귀 한도에 걸리지 않는다)."""
    state = {}
    for root in nodes:
        if root in state:
            continue
        state[root] = 1
        stack = [(root, iter([s['target'] for s in defn.outgoing(root)]))]
        while stack:
            node, children = stack[-1]
            nxt = next(children, None)
            if nxt is None:
                state[node] = 2
                stack.pop()
            elif state.get(nxt) == 1:
                return True
            elif nxt not in state:
                state[nxt] = 1
                stack.append((nxt, iter([s['target'] for s in defn.outgoing(nxt)])))
    return False


#: 정의 data 의 자료형 이름 → 조건 자료형 검사(effect_parts.condition_type_problems)의 이름. 그 밖(Object · Array)은 비교 규칙이 없어 보지 않는다
_CONDITION_TYPES = {'text': 'Text', 'string': 'Text', 'number': 'Number', 'integer': 'Number', 'float': 'Number', 'boolean': 'Boolean'}


def _condition_variables(defn):
    """A098 (bpmn-process-generation-skill 08-reference-info: a gateway condition may only read a variable some earlier
    task writes). Every name a sequence condition reads must be a declared process variable (data) that an activity
    produces (outputData) or the server sets (PROTECTED_OUTPUTS); otherwise the gateway would judge on a value that
    can never exist and the instance would stall at 'cannot proceed'.

    A143 (remaining-sweep 19, D01 "outputData of the activity before the gateway"): the producer must also be able to run
    before the gateway judges. HYD allows a producer on another branch of the same instance (condition-recheck-v1: `a` on
    a parallel path writes x, `g` after `b` reads it — the engine waits for it, dependency_schedule), so the rule is
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
        # P1-03: 선언한 자료형과 맞지 않는 비교(글 값 > 70 · 수 값 in 수)는 실행 때 판정할 수 없다 — 등록 전에 거절한다. 검사기는 흐름 가져오기와
        # 같은 하나(effect_parts.condition_type_problems)다.
        types = {n: _CONDITION_TYPES[str(defn.data[n].get('type') or '').lower()] for n in names
                 if str(defn.data[n].get('type') or '').lower() in _CONDITION_TYPES}
        problems = effect_parts.condition_type_problems(cond, types)
        if problems:
            raise ValueError(f"분기 {s.get('id')}의 조건 {cond!r}이(가) 값의 자료형과 맞지 않습니다: {'; '.join(problems)}")
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
    comps = _strong_components(nodes, succ)
    for comp in comps:
        exits = [n for n in comp if defn.gateways.get(n, {}).get('type') == 'exclusiveGateway'
                 and any(s['target'] not in comp for s in defn.outgoing(n))]
        if not exits:
            raise ValueError(f"반복 경로({', '.join(sorted(comp))})에서 빠져나갈 배타 게이트웨이가 없습니다")
        if any(defn.gateways.get(n, {}).get('type') == 'parallelGateway' for n in comp):
            raise ValueError(f"반복 경로({', '.join(sorted(comp))}) 안의 병렬 게이트웨이는 아직 검증되지 않았습니다")


def _strong_components(nodes, succ):
    """강한 연결 요소(Tarjan, 반복문) 중 반복을 이루는 것(크기 2 이상 또는 자기 자신으로 돌아가는 노드)."""
    index, low, on, stack, comps, counter = {}, {}, set(), [], [], 0
    for root in nodes:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            v, i = work.pop()
            if i == 0:
                index[v] = low[v] = counter
                counter += 1
                stack.append(v)
                on.add(v)
            children = succ.get(v, [])
            if i > 0:
                low[v] = min(low[v], low[children[i - 1]])
            while i < len(children) and children[i] in index:
                w = children[i]
                if w in on:
                    low[v] = min(low[v], index[w])
                i += 1
            if i < len(children):
                work.append((v, i + 1))
                work.append((children[i], 0))
                continue
            if low[v] == index[v]:
                comp = set()
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.add(w)
                    if w == v:
                        break
                if len(comp) > 1 or v in children:
                    comps.append(comp)
    return comps
