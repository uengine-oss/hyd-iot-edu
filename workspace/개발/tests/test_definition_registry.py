"""정의 등록 검사(procsvc/definition_registry.py) — 실행 엔진이 못 다루는 모양을 등록 전에 거절한다."""
import json
from copy import deepcopy

import pytest

from procsvc import definition_registry
from procsvc.definition_registry import validate_definition

from conftest import DEFINITIONS

PROVIDED = ['anomaly_response_v22.json', 'alert_triage_v1.json', 'ask_agent_v1.json', 'shift_handover_v1.json']


def _flow(activities, sequences, gateways=(), events=None, data=(), forms=None, **top):
    """최소 정의: 사람 단계는 폼 'f'(outputData 와 같은 key), 담당 역할 '담당'."""
    keys = sorted({o for a in activities for o in a.get('outputData', [])})
    forms = forms if forms is not None else {'f': {'fields_json': [{'key': k, 'type': 'text', 'text': k} for k in keys]}}
    for a in activities:
        if a['type'] == 'userTask':
            a.setdefault('role', '담당')
            a['tool'] = 'formHandler:f'
            a['outputData'] = keys
    return {'processDefinitionId': 'probe', 'processDefinitionName': '시험 흐름', 'version': '1', 'forms': forms,
            'activities': activities, 'gateways': list(gateways), 'data': list(data),
            'events': events or [{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}],
            'roles': [{'name': '담당', 'endpoint': 'user:kim-op'}],
            'sequences': [{'id': f's{i}', **s} for i, s in enumerate(sequences)], **top}


def _task(aid, **extra):
    return {'id': aid, 'name': aid, 'type': 'userTask', **extra}


def _chain(second_gateway_outgoing):
    """승인 → 분기1(approval) → 분기2(recovered) → 끝들. second_gateway_outgoing = 분기2 의 나가는 선들."""
    forms = {'pick': {'fields_json': [{'key': 'approval', 'type': 'text', 'text': '결정'}, {'key': 'recovered', 'type': 'text', 'text': '회복'}]}}
    return {'processDefinitionId': 'chain', 'processDefinitionName': '분기 연쇄', 'version': '1', 'forms': forms,
            'activities': [{'id': 'pick', 'name': '고르기', 'type': 'userTask', 'role': '담당', 'tool': 'formHandler:pick',
                            'outputData': ['approval', 'recovered']}],
            'events': [{'id': 'start', 'type': 'startEvent'}, {'id': 'ok', 'type': 'endEvent'}, {'id': 'no', 'type': 'endEvent'},
                       {'id': 'other', 'type': 'endEvent'}],
            'gateways': [{'id': 'g1', 'type': 'exclusiveGateway'}, {'id': 'g2', 'type': 'exclusiveGateway', 'name': '회복 분기'}],
            'roles': [{'name': '담당', 'endpoint': 'user:kim-op'}],
            'data': [{'name': 'approval', 'type': 'text'}, {'name': 'recovered', 'type': 'text'}],
            'sequences': [{'id': 's0', 'source': 'start', 'target': 'pick'}, {'id': 's1', 'source': 'pick', 'target': 'g1'},
                          {'id': 's2', 'source': 'g1', 'target': 'g2', 'condition': "approval == '승인'"},
                          {'id': 's3', 'source': 'g1', 'target': 'no'}, *second_gateway_outgoing]}


# ---------------------------------------------------------------- #16 · P1-36 배타 분기의 모양
def test_분기에서_바로_이어지는_분기에_그_밖의_경우가_없으면_등록하지_않는다():
    """#16: 앞 작업의 진행 판정은 분기 한 단계만 본다 — 두 번째 분기의 조건이 모두 거짓이면 흐름이 오류 없이 사라졌다."""
    raw = _chain([{'id': 's4', 'source': 'g2', 'target': 'ok', 'condition': "recovered == 'yes'"},
                  {'id': 's5', 'source': 'g2', 'target': 'other', 'condition': "recovered == 'no'"}])
    with pytest.raises(ValueError, match='회복 분기.*그 밖의 경우'):
        validate_definition(raw)


@pytest.mark.parametrize('default_flow', [
    {'id': 's5', 'source': 'g2', 'target': 'other'},                                                     # 조건 없는 선
    {'id': 's5', 'source': 'g2', 'target': 'other', 'condition': "recovered == 'no'", 'properties': {'default': True}},
])
def test_이어지는_분기에_기본_선이_있으면_등록한다(default_flow):
    raw = _chain([{'id': 's4', 'source': 'g2', 'target': 'ok', 'condition': "recovered == 'yes'"}, default_flow])
    assert validate_definition(raw).id == 'chain'


def test_배타_분기에_그_밖의_경우_선이_둘이면_등록하지_않는다():
    """P1-36: 전에는 엔진이 조건 없는 선 둘 중 첫째를 조용히 골랐다(흐름 가져오기만 거절했다)."""
    raw = _chain([{'id': 's4', 'source': 'g2', 'target': 'ok'}, {'id': 's5', 'source': 'g2', 'target': 'other'}])
    with pytest.raises(ValueError, match='그 밖의 경우.*2개.*s4, s5'):
        validate_definition(raw)


def _timer_to_gateway(default):
    timer = {'id': 'late', 'type': 'boundaryEvent', 'eventDefinition': 'timer', 'timer': 'PT10M', 'attachedTo': 'a', 'name': '시한'}
    outs = [{'source': 'g', 'target': 'b', 'condition': "x == 'y'"}] + ([{'source': 'g', 'target': 'end'}] if default else [])
    return _flow([_task('a', outputData=['x'], attachedEvents=['late']), _task('b')],
                 [{'source': 'start', 'target': 'a'}, {'source': 'a', 'target': 'end'}, {'source': 'late', 'target': 'g'}, *outs,
                  {'source': 'b', 'target': 'end'}],
                 gateways=[{'id': 'g', 'type': 'exclusiveGateway', 'name': '시한 뒤'}],
                 events=[{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}, timer],
                 data=[{'name': 'x', 'type': 'text'}])


def test_시한_뒤_분기에_그_밖의_경우가_없으면_등록하지_않는다():
    """P1-36: 경계 타이머 → 분기의 조건이 모두 거짓이면 아무도 닫을 수 없는 이벤트 행이 「진행 멈춤」으로 남았다."""
    with pytest.raises(ValueError, match='시한 뒤.*단계가 아닌 곳.*그 밖의 경우'):
        validate_definition(_timer_to_gateway(default=False))
    assert validate_definition(_timer_to_gateway(default=True)).id == 'probe'


# ---------------------------------------------------------------- P1-07 단계와 그 단계를 끊는 시한이 같은 병렬 합류로
def _split_join(timer_to):
    timer = {'id': 'late', 'type': 'boundaryEvent', 'eventDefinition': 'timer', 'timer': 'PT10M', 'attachedTo': 'a', 'name': '시한'}
    seqs = [{'source': 'start', 'target': 'p'}, {'source': 'p', 'target': 'a'}, {'source': 'p', 'target': 'b'},
            {'source': 'a', 'target': timer_to if timer_to == 'm' else 'j'}, {'source': 'b', 'target': 'j'}, {'source': 'j', 'target': 'end'}]
    gateways = [{'id': 'p', 'type': 'parallelGateway'}, {'id': 'j', 'type': 'parallelGateway', 'name': '모임'}]
    if timer_to == 'm':            # 단계 길과 시한 길을 배타 분기로 먼저 모은 뒤 합류의 한 입구로
        seqs += [{'source': 'late', 'target': 'm'}, {'source': 'm', 'target': 'c'}, {'source': 'c', 'target': 'j'}]
        gateways.append({'id': 'm', 'type': 'exclusiveGateway'})
        tasks = [_task('a', attachedEvents=['late']), _task('b'), _task('c')]
    else:
        seqs.append({'source': 'late', 'target': 'j'})
        tasks = [_task('a', attachedEvents=['late']), _task('b')]
    return _flow(tasks, seqs, gateways=gateways,
                 events=[{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}, timer])


def test_한_단계와_그_단계를_끊는_시한이_같은_병렬_합류의_다른_입구로_들어가면_등록하지_않는다():
    """P1-07: 둘 중 하나만 일어나 합류가 열리지 않는데 등록됐고, 실행하면 아무도 닫지 않았는데 「사람이 닫음」으로 끝났다."""
    with pytest.raises(ValueError, match='병렬 합류 모임.*시한'):
        validate_definition(_split_join('j'))


def test_단계_길과_시한_길을_배타_분기로_먼저_모으면_등록한다():
    assert validate_definition(_split_join('m')).id == 'probe'


# ---------------------------------------------------------------- P1-03 분기 조건의 자료형
@pytest.mark.parametrize('kind, condition, ok', [
    ('Number', 'reading > 70', True), ('number', 'reading > 70', True), ('Text', 'reading > 70', False),
    ('Text', "reading == '높음'", True), ('Number', "reading == '높음'", False), ('Boolean', 'reading', True),
    ('Text', 'reading', False), ('Object', 'reading > 70', True),            # Object 는 비교 규칙이 없다 — 실행 때 엔진이 자료형으로 판정
])
def test_분기_조건이_선언한_자료형과_맞지_않으면_등록하지_않는다(kind, condition, ok):
    """P1-03: 전에는 형 검사가 흐름 가져오기 길에만 있어 JSON 으로 등록한 흐름이 실행 때 TypeError(500)로 멈췄다."""
    raw = _flow([_task('read', outputData=['reading']), _task('high')],
                [{'source': 'start', 'target': 'read'}, {'source': 'read', 'target': 'g'},
                 {'id': 'hot', 'source': 'g', 'target': 'high', 'condition': condition}, {'source': 'g', 'target': 'end'},
                 {'source': 'high', 'target': 'end'}],
                gateways=[{'id': 'g', 'type': 'exclusiveGateway'}], data=[{'name': 'reading', 'type': kind}])
    if ok:
        assert validate_definition(raw).id == 'probe'
    else:
        with pytest.raises(ValueError, match='분기 s?hot.*자료형'):
            validate_definition(raw)


# ---------------------------------------------------------------- P1-16 크기 · 깊이
def _line(n):
    tasks = [_task(f't{i}') for i in range(n)]
    seqs = [{'source': 'start', 'target': 't0'}] + [{'source': f't{i}', 'target': f't{i + 1}'} for i in range(n - 1)] + \
           [{'source': f't{n - 1}', 'target': 'end'}]
    return _flow(tasks, seqs)


def test_긴_직선_흐름도_재귀_한도_없이_검사한다():
    """P1-16: 전에는 1,600단계에서 RecursionError(사유 없는 500)였다. 한도 안(500단계)은 등록되고, 넘으면 쉬운 말로 거절한다."""
    longest = definition_registry.MAX_NODES - 1                 # 연결은 단계보다 하나 많다
    assert len(validate_definition(_line(longest)).activities) == longest
    with pytest.raises(ValueError, match=r'단계가 501개로 한도 500개'):
        validate_definition(_line(definition_registry.MAX_NODES + 1))


def test_너무_큰_정의는_글자_수로_거절한다():
    raw = _line(2)
    raw['description'] = '가' * definition_registry.MAX_DEFINITION_CHARS
    with pytest.raises(ValueError, match='너무 큽니다'):
        validate_definition(raw)


def test_되돌아가는_선은_반복_검사를_거친_흐름만_받고_빠져나갈_분기가_없으면_거절한다():
    raw = _flow([_task('a', outputData=['again'])],
                [{'source': 'start', 'target': 'a'}, {'source': 'a', 'target': 'g'}, {'source': 'g', 'target': 'a', 'condition': "again == '예'"},
                 {'source': 'g', 'target': 'end'}], gateways=[{'id': 'g', 'type': 'exclusiveGateway'}], data=[{'name': 'again', 'type': 'text'}])
    with pytest.raises(ValueError, match='반복 실행'):
        validate_definition(raw)
    assert validate_definition(dict(raw, loopPolicy='guarded')).id == 'probe'
    closed = deepcopy(raw)
    closed['sequences'] = [s for s in closed['sequences'] if s['target'] != 'end'] + [{'id': 'x', 'source': 'a', 'target': 'end'}]
    closed['activities'] = [dict(closed['activities'][0])]
    with pytest.raises(ValueError):
        validate_definition(dict(closed, loopPolicy='guarded', gateways=[{'id': 'g', 'type': 'parallelGateway'}]))


# ---------------------------------------------------------------- P1-34 · P1-20 입력을 고치지 않고, 옛 모양은 받지 않는다
def test_검사는_받은_정의를_고치지_않고_저장할_모양을_돌려준다():
    raw = _flow([_task('a', agentMode='complete', orchestration='cliagents')], [{'source': 'start', 'target': 'a'}, {'source': 'a', 'target': 'end'}])
    before = deepcopy(raw)
    defn = validate_definition(raw)
    assert raw == before, '검사가 입력을 고쳐 쓰면 부르는 쪽마다 사본 여부가 달라진다'
    assert defn.raw['activities'][0]['agentMode'] == 'COMPLETE'


def test_A116_전의_businessRuleTask_에이전트_단계는_받지_않는다():
    raw = _flow([_task('a', type='businessRuleTask', agentMode='COMPLETE')], [{'source': 'start', 'target': 'a'}, {'source': 'a', 'target': 'end'}])
    raw['activities'][0]['type'] = 'businessRuleTask'
    with pytest.raises(ValueError, match='userTask.*agentMode'):
        validate_definition(raw)


# ---------------------------------------------------------------- 제공 정의
@pytest.mark.parametrize('name', PROVIDED)
def test_제공_정의는_모두_등록_검사를_통과한다(name):
    raw = json.loads((DEFINITIONS / name).read_text(encoding='utf8'))
    assert validate_definition(raw).id == raw['processDefinitionId']
    assert len(json.dumps(raw, ensure_ascii=False)) < definition_registry.MAX_DEFINITION_CHARS / 10


def test_낸_흐름_정의는_내용을_바꾸면_판본_번호도_올린다():
    """등록한 정의 판본은 바꿀 수 없다(procdb.register_definition: 같은 번호 · 다른 원문이면 거절) — 이미 쓰던 DB 에서는 process 가 시작하지 못한다.
    2026-11-13: shift_handover 의 담당 자리를 고치고 번호를 1.2 로 둔 채 낼 뻔했다. 낸 판본의 내용 지문을 definition_versions.lock.json 에 두고 대조한다.
    정의를 고쳤으면 version 을 올리고 그 판본의 지문을 잠금 파일에 더한다(옛 판본 줄은 지우지 않는다)."""
    import hashlib, json
    from pathlib import Path
    here = Path(__file__).resolve()
    lock = json.loads((here.parent / 'definition_versions.lock.json').read_text(encoding='utf-8'))
    checked = 0
    for path in sorted((here.parents[3] / 'it' / 'process' / 'definitions').glob('*.json')):
        raw = json.loads(path.read_text(encoding='utf-8'))
        if 'processDefinitionId' not in raw:
            continue
        key = f"{raw['processDefinitionId']}@{raw['version']}"
        digest = hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        assert key in lock, f'{path.name}: {key} 의 지문이 잠금 파일에 없습니다 — 새 판본이면 지문 {digest} 을 더하세요'
        assert lock[key] == digest, f'{path.name}: {key} 는 이미 낸 판본인데 내용이 달라졌습니다 — version 을 올리세요'
        checked += 1
    assert checked >= 4
