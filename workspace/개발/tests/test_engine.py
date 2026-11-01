"""처리 건 엔진의 순수 규칙(procsvc/engine.py) — DB 없이 정의 · 행으로 판정한다."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from procsvc import engine

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)


def _defn(activities, sequences, gateways=(), events=None, roles=(('담당', 'user:kim-op'),), data=()):
    events = events or [{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent', 'name': '끝'}]
    return engine.Definition.from_dict({
        'processDefinitionId': 'probe', 'processDefinitionName': 'probe', 'version': '1',
        'activities': activities, 'events': events, 'gateways': list(gateways), 'data': list(data),
        'roles': [{'name': n, 'endpoint': e} for n, e in roles],
        'sequences': [{'id': f's{i}', **s} for i, s in enumerate(sequences)]})


def _human(aid, **extra):
    return dict(id=aid, name=aid, type='userTask', role='담당', tool='formHandler:f', **extra)


def _agent(aid, **extra):
    return dict(id=aid, name=aid, type='userTask', role='담당', agentMode='COMPLETE', orchestration='cliagents', tool='formHandler:f', **extra)


def _service(aid, tool):
    return dict(id=aid, name=aid, type='serviceTask', tool=tool)


def _run(defn, values=None):
    inst = engine.new_instance(defn, values or {}, now=T0)
    adv = engine.start(defn, inst, now=T0)
    return inst, {w['activity_id']: w for w in adv.created}


@pytest.fixture
def compression():
    """수업용 대기 압축 60 — 테스트가 끝나면 앞 값으로 되돌린다(G5b-11: 전에는 전역에 남겨 뒤 테스트가 그 값으로 돌았다)."""
    before = engine.wait_compression()
    engine.configure_wait_compression(60)
    yield 60
    engine.configure_wait_compression(before)


# ---------------------------------------------------------------- 시간 규칙: 경계 타이머 = 그 타이머가 감싼 일의 시계
@pytest.mark.parametrize('activity, scale, expected_s', [
    (_human('approve'), 20, 600),                                         # 사람 단계 — 벽시계(#2)
    (_human('approve'), 1, 600),
    (_agent('think'), 20, 600),                                           # 에이전트 단계 — 벽시계(P1-12: 전에는 배속을 곱해 30초)
    (_service('cmd', 'incident:command'), 20, 600),                       # 명령 ACK — 벽시계(ACK 30초 자체가 벽시계)
    (_service('mail', 'mcp:call'), 20, 600),                              # IT 시스템 단계 — 벽시계
    (_service('reobs', 'incident:reobserve'), 20, 30),                    # 재관측 — 배속(가상 설비 시간)
    (_service('test', 'plant:test-run'), 20, 30),                         # 시운전 — 배속
    (_service('wait', 'process:wait'), 20, 600 / (20 * 60)),              # 기다리는 부품 — 배속 × 수업 압축
    (_service('gr', 'enterprise:GR_CONFIRM'), 20, 600 / (20 * 60)),
    (_service('fix', 'plant:restore'), 20, 600 / (20 * 60)),
    (_service('wait', 'process:wait'), 0.5, 600 / 60),                   # 배속이 1보다 작아도 압축은 배속 1 기준
])
def test_경계_타이머의_마감은_그_타이머가_감싼_일의_시계로_잰다(compression, activity, scale, expected_s):
    event = {'id': 'late', 'type': 'boundaryEvent', 'eventDefinition': 'timer', 'timer': 'PT10M'}
    defn = _defn([activity], [], events=[{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}, event])
    row = engine.new_event_workitem(defn, {'proc_inst_id': 'p', 'tenant_id': 'hyd'}, event, T0, engine.timer_scale(activity, scale))
    due = datetime.fromisoformat(row['due_date'].replace('Z', '+00:00'))
    assert due - T0 == timedelta(seconds=expected_s)


@pytest.mark.parametrize('factor', [0.5, 0, -1, float('nan'), float('inf')])
def test_수업_대기_압축은_1_이상의_유한한_수만_받는다(compression, factor):
    with pytest.raises(ValueError, match='1 이상의 유한한 수'):
        engine.configure_wait_compression(factor)
    assert engine.wait_compression() == compression


# ---------------------------------------------------------------- #15 · P1-07 닫힌 가지로 병렬 합류가 막히면 처리 건을 닫는다 — 끝 이름은 까닭대로
def _parallel():
    return _defn([_agent('x'), _agent('y'), _agent('z'), _human('after')],
                 [dict(source='start', target='split'), dict(source='split', target='x'), dict(source='split', target='y'),
                  dict(source='split', target='z'), dict(source='x', target='join'), dict(source='y', target='join'),
                  dict(source='z', target='join'), dict(source='join', target='after'), dict(source='after', target='end')],
                 gateways=[{'id': 'split', 'type': 'parallelGateway'}, {'id': 'join', 'type': 'parallelGateway'}])


def _finish(defn, inst, rows, aid):
    engine.submit(defn, inst, rows[aid], {}, now=T0)
    return engine.process_submitted(defn, inst, rows[aid], list(rows.values()), now=T0)


@pytest.mark.parametrize('closed, end', [
    (dict(status='CANCELLED', draft_status='CANCELLED'), engine.HUMAN_CLOSE_END_EVENT),       # 사람이 [닫기]
    (dict(status='CANCELLED', draft_status=None), engine.JOIN_UNREACHABLE_END_EVENT),        # 사람이 닫지 않았는데 취소된 가지
])
def test_닫힌_가지가_병렬_합류로_들어가면_남은_가지가_끝날_때_까닭대로_기술_끝으로_닫는다(closed, end):
    """#15: 전에는 남은 가지가 합류에 닿아도 합류가 영영 열리지 않아 처리 건이 RUNNING 인데 열린 일 0으로 남았다.
    P1-07: 사람이 닫지 않았는데도 「사람이 닫음」으로 끝났다."""
    defn = _parallel()
    inst, rows = _run(defn)
    rows['x'].update(**closed)
    _finish(defn, inst, rows, 'y')
    adv = _finish(defn, inst, rows, 'z')
    assert adv.ended == end and inst['status'] == 'COMPLETED' and inst['end_event'] == end
    assert rows['after']['status'] == 'CANCELLED', '닿지 않은 다음 단계는 취소로 정리한다'
    # E3: 학생이 읽는 작업 행 기록은 끝 id 가 아니라 끝 이름(end_label 과 같은 정본)으로 까닭을 적는다
    label = engine.TECHNICAL_ENDS[end]
    assert f'처리 건 끝 — {label}' in rows['after']['log'] and end not in rows['after']['log']


def test_가지가_모두_끝나면_병렬_합류가_열린다():
    defn = _parallel()
    inst, rows = _run(defn)
    for aid in ('x', 'y', 'z'):
        adv = _finish(defn, inst, rows, aid)
    assert adv.ended is None and rows['after']['status'] == 'IN_PROGRESS' and inst['status'] == 'RUNNING'


def test_다른_가지가_아직_진행_중이면_닫은_가지가_있어도_기다린다():
    defn = _parallel()
    inst, rows = _run(defn)
    rows['x'].update(status='CANCELLED', draft_status='CANCELLED')
    adv = _finish(defn, inst, rows, 'y')                         # z 는 아직 진행 중
    assert adv.ended is None and inst['status'] == 'RUNNING' and rows['z']['status'] == 'IN_PROGRESS'


# ---------------------------------------------------------------- A-11 깨진 흐름 선 속성은 조용히 빈 값이 되지 않는다
@pytest.mark.parametrize('properties, result', [
    (None, {}), ({'default': True}, {'default': True}), (json.dumps({'priority': 2}), {'priority': 2}),
    ('{"default": tr', ValueError), ('[1, 2]', ValueError), (7, ValueError),
])
def test_흐름_선_properties는_객체만_받고_깨진_값은_선_id를_붙여_실패한다(properties, result):
    seq = {'id': 'flow-9', 'source': 'a', 'target': 'b', 'properties': properties}
    if result is ValueError:
        with pytest.raises(ValueError, match='flow-9'):
            engine.sequence_properties(seq)
    else:
        assert engine.sequence_properties(seq) == result


# ---------------------------------------------------------------- P1-03 분기 조건과 값의 자료형
def _gauge():
    return _defn([_human('read', outputData=['reading']), _human('high'), _human('low')],
                 [dict(source='start', target='read'), dict(source='read', target='g'),
                  dict(id='hot', source='g', target='high', condition='reading > 70'), dict(id='else', source='g', target='low'),
                  dict(source='high', target='end'), dict(source='low', target='end')],
                 gateways=[{'id': 'g', 'type': 'exclusiveGateway'}], data=[{'name': 'reading', 'type': 'Number'}])


@pytest.mark.parametrize('reading, reached', [(75, 'high'), (70, 'low'), (None, 'low'), ('75', TypeError)])
def test_분기_조건은_값의_자료형이_맞으면_가지를_고르고_다르면_흐름_선_id를_붙여_실패한다(reading, reached):
    """P1-03: 전에는 글 값 '75' > 70 이 TypeError 로 사람 제출을 500 으로 만들고 값이 사라졌다."""
    defn = _gauge()
    inst, rows = _run(defn)
    engine.submit(defn, inst, rows['read'], {'reading': reading}, now=T0)
    if reached is TypeError:
        with pytest.raises(engine.ConditionTypeError, match="흐름 선 hot.*'75'"):
            engine.process_submitted(defn, inst, rows['read'], list(rows.values()), now=T0)
        return
    adv = engine.process_submitted(defn, inst, rows['read'], list(rows.values()), now=T0)
    assert [w['activity_id'] for w in adv.reached] == [reached]


@pytest.mark.parametrize('condition, words', [
    ("len(reading) > 1", '함수 호출'), ("reading.value > 1", '점'), ("reading[0] > 1", '대괄호'), ("reading + 1 > 2", '계산'),
    ("reading >", '읽을 수 없습니다'),
])
def test_분기_조건은_값_비교만_받고_거절_까닭을_쉬운_말로_말한다(condition, words):
    with pytest.raises(ValueError, match=words):
        engine.compile_condition(condition)


@pytest.mark.parametrize('expr, values, result', [
    ("x > 3", {}, False), ("x > 3", {'x': 4}, True), ("x in ['a', 'b']", {'x': 'a'}, True), ("x not in ['a']", {'x': 'b'}, True),
    ("x == 1 and not y", {'x': 1, 'y': False}, True), ("x is None", {}, True),
])
def test_분기_조건_판정_표(expr, values, result):
    assert engine.eval_condition(expr, values) is result


@pytest.mark.parametrize('text, seconds', [('PT10M', 600), ('P1DT2H', 93600), ('PT1S', 1), ('PT', 0)])
def test_ISO_시간_길이를_초로_읽는다(text, seconds):
    assert engine.iso_duration_seconds(text) == seconds


@pytest.mark.parametrize('text', ['P1W', 'PT1.5S', '10M', ''])
def test_읽을_수_없는_ISO_시간_길이는_예를_들어_거절한다(text):
    with pytest.raises(ValueError, match='PT10M'):
        engine.iso_duration_seconds(text)


# ---------------------------------------------------------------- 실행하는 활동 종류
@pytest.mark.parametrize('kind', ['businessRuleTask', 'scriptTask', 'sendTask', 'receiveTask', 'subProcess'])
def test_실행하지_않는_활동_종류의_정의는_읽지_않는다(kind):
    """P1-20 · P1-21: A116 전 모양(businessRuleTask)과 실행 갈래가 없는 종류를 받던 호환 갈래를 지웠다."""
    with pytest.raises(ValueError, match='userTask'):
        _defn([dict(_human('a'), type=kind)], [dict(source='start', target='a'), dict(source='a', target='end')])


def test_끝난_단계를_다시_제출하면_단계_이름으로_거절한다():
    defn = _defn([_human('a')], [dict(source='start', target='a'), dict(source='a', target='end')])
    inst, rows = _run(defn)
    _finish(defn, inst, rows, 'a')
    with pytest.raises(ValueError, match="'a' 단계는 이미 끝났습니다"):
        engine.submit(defn, inst, rows['a'], {}, now=T0)


def test_정의에_없는_값을_내면_낼_수_있는_값을_말하며_거절한다():
    defn = _defn([_human('a', outputData=['ok'])], [dict(source='start', target='a'), dict(source='a', target='end')])
    inst, rows = _run(defn)
    with pytest.raises(ValueError, match='ok 뿐입니다.*extra'):
        engine.submit(defn, inst, rows['a'], {'extra': 1}, now=T0)


# ---------------------------------------------------------------- P1-32 같은 전이 사슬에서 다시 들어간 단계는 옛 행보다 늦게 시작한다
def test_같은_시각에_다시_들어간_단계의_새_행은_옛_행보다_늦게_시작해_마지막_행이_갈리지_않는다():
    defn = _defn([_human('a', outputData=['again'])],
                 [dict(source='start', target='a'), dict(source='a', target='g'),
                  dict(source='g', target='a', condition='again == True'), dict(source='g', target='end')],
                 gateways=[{'id': 'g', 'type': 'exclusiveGateway'}], data=[{'name': 'again', 'type': 'Boolean'}])
    inst, rows = _run(defn)
    first = rows['a']
    engine.submit(defn, inst, first, {'again': True}, now=T0)
    adv = engine.process_submitted(defn, inst, first, [first], now=T0)        # 같은 시각(T0) 그대로
    fresh = next(w for w in adv.created if w['activity_id'] == 'a')
    assert fresh['status'] == 'IN_PROGRESS'
    assert engine.workitem_order(fresh) > engine.workitem_order(first), (fresh['start_date'], first['start_date'])


# ---------------------------------------------------------------- P1-08 · P1-29 처리 건이 끝난 곳의 이름
def _ended(end_event, **variables):
    defn = _defn([_human('a')], [dict(source='start', target='a'), dict(source='a', target='end')])
    inst, rows = _run(defn, variables)
    engine.finish(defn, inst, list(rows.values()), end_event, T0)
    return defn, inst


def test_업무_끝이면_정의의_끝_이름이고_기술_끝이면_표의_이름이다():
    defn, inst = _ended('end')
    assert engine.end_label(defn, inst) == '끝'
    for end, name in engine.TECHNICAL_ENDS.items():
        defn, inst = _ended(end)
        assert engine.end_label(defn, inst) == name


def test_조치_전_종료는_그_결과를_이름으로_쓴다():
    defn, inst = _ended(engine.BEFORE_ACTION_END_EVENT, result_report={'outcome': '조치 전 해소'})
    assert engine.end_label(defn, inst) == '조치 전 해소'


def test_사람이_닫기_전에_흐름이_업무_끝에_닿았으면_그_끝도_함께_말한다():
    defn = _defn([_human('a')], [dict(source='start', target='a'), dict(source='a', target='end')])
    inst, rows = _run(defn)
    inst['flow_state']['end_arrivals'].append({'event': 'end', 'source': 'a', 'workitem': rows['a']['id'], 'generation': 0})
    engine.finish(defn, inst, list(rows.values()), engine.HUMAN_CLOSE_END_EVENT, T0)
    assert engine.end_label(defn, inst) == '사람이 닫음 (흐름이 닿은 끝: 끝)'


def test_정의에도_기술_끝_표에도_없는_끝은_좌표를_붙여_실패한다():
    defn, inst = _ended('end')
    inst['end_event'] = 'nowhere'
    with pytest.raises(ValueError, match="'nowhere'.*probe@1"):
        engine.end_label(defn, inst)
    with pytest.raises(ValueError, match='nowhere'):
        engine.finish(defn, inst, [], 'nowhere', T0)


def test_처리_건을_끝내면_닿지_않은_단계와_열린_시한_행을_취소한다():
    timer = {'id': 'late', 'type': 'boundaryEvent', 'eventDefinition': 'timer', 'timer': 'PT10M', 'attachedTo': 'a'}
    defn = _defn([_human('a', attachedEvents=['late']), _human('b')],
                 [dict(source='start', target='a'), dict(source='a', target='b'), dict(source='b', target='end'),
                  dict(source='late', target='end')],
                 events=[{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}, timer])
    inst = engine.new_instance(defn, {}, now=T0)
    adv = engine.start(defn, inst, now=T0)
    rows = adv.created
    changed = engine.finish(defn, inst, rows, engine.HUMAN_CLOSE_END_EVENT, T0, reason='시험')
    assert {w['activity_id'] for w in changed} == {'b', 'late'} and all(w['status'] == 'CANCELLED' for w in changed)
    assert next(w for w in rows if w['activity_id'] == 'a')['status'] == 'IN_PROGRESS', '살아 있는 단계는 호출자가 다룬다'


# ---------------------------------------------------------------- W1-01 흐름 순서
def test_흐름_순서는_앞_단계가_먼저이고_붙은_이벤트는_그_단계_뒤다():
    timer = {'id': 'late', 'type': 'boundaryEvent', 'eventDefinition': 'timer', 'timer': 'PT10M', 'attachedTo': 'b'}
    defn = _defn([_human('c'), _human('b', attachedEvents=['late']), _human('a')],
                 [dict(source='start', target='a'), dict(source='a', target='b'), dict(source='b', target='c'),
                  dict(source='c', target='end'), dict(source='late', target='end')],
                 events=[{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}, timer])
    order = engine.flow_order(defn)
    assert order['a'] < order['b'] < order['late'] and order['b'] < order['c']
