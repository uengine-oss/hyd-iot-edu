"""Publishing executable definitions, with their forms inside the immutable version.

Product reference: vue3 ProcessGPTBackend.putRawDefinition/getExecutionDefinition.
HYD deliberately requires an exact version and rejects unsupported execution shapes.
"""
from copy import deepcopy
from hydcommon.process_contracts import pinned_form, validate_fields
from . import engine, alert_policy

SERVICE_TOOLS = {'incident:command', 'incident:reobserve', 'enterprise:WO_CREATE'}
PROTECTED_OUTPUTS = {'incident','commands','approved_by','approved_role','chosen_option'}


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
        if kind not in {'userTask','manualTask','businessRuleTask','serviceTask'}:
            raise ValueError(f'아직 실행을 지원하지 않는 활동 타입: {kind}')
        if kind == 'serviceTask':
            if a.get('tool') not in SERVICE_TOOLS:
                raise ValueError(f"지원하지 않는 서비스 도구: {a.get('tool')}")
            if a.get('agentMode') or a.get('orchestration') not in (None,'hyd-process'):
                raise ValueError('서비스 작업은 hyd-process에서 실행합니다')
        else:
            form = pinned_form(raw, a.get('tool'))
            if form is None:
                raise ValueError(f"활동 {a['id']}에는 formHandler 도구와 버전별 폼이 필요합니다")
            fields = {f['key'] for f in form['fields_json']}
            if fields != set(a.get('outputData') or []):
                raise ValueError(f"활동 {a['id']}의 outputData와 폼 key가 다릅니다")
            if kind == 'businessRuleTask' and (a.get('agentMode') not in ('DRAFT','COMPLETE') or a.get('orchestration') != 'cliagents'):
                raise ValueError(f"에이전트 활동 {a['id']}에는 agentMode DRAFT/COMPLETE와 orchestration cliagents가 필요합니다")
            if kind in ('userTask','manualTask') and (a.get('agentMode') or a.get('orchestration')):
                raise ValueError('사람 작업에는 agentMode/orchestration을 지정할 수 없습니다')
    for g in defn.gateways.values():
        if g.get('type') != 'exclusiveGateway':
            raise ValueError('등록 경로는 현재 exclusiveGateway만 검증되었습니다')
    for e in defn.events.values():
        if e.get('type') not in {'startEvent','endEvent','boundaryEvent'}:
            raise ValueError(f"지원하지 않는 이벤트: {e.get('type')}")
        if e['type'] == 'boundaryEvent':
            if e.get('eventDefinition') != 'timer' or not defn.attached_activity(e['id']):
                raise ValueError('boundaryEvent는 활동에 연결된 timer여야 합니다')
            if engine.iso_duration_seconds(e.get('timer')) <= 0:
                raise ValueError('timer 기간은 0보다 커야 합니다')
    # Loop re-entry exists in the engine; joins/cancellation across iterations still
    # need integration coverage before the public registration contract accepts it.
    visiting, visited = set(), set()
    def visit(n):
        if n in visiting:
            raise ValueError('등록 경로의 반복 실행은 아직 검증되지 않았습니다')
        if n in visited:
            return
        visiting.add(n)
        for s in defn.outgoing(n):
            visit(s['target'])
        visiting.remove(n); visited.add(n)
    for n in all_ids:
        visit(n)
    if not any(e['type'] == 'endEvent' for e in defn.events.values()):
        raise ValueError('endEvent가 필요합니다')
    return defn
