"""처리 건 엔진의 순수 규칙(procsvc/engine.py) — DB 없이 정의 · 행으로 판정한다."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from procsvc import engine

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)


def _defn(activities, sequences, gateways=(), events=None, roles=(('담당', 'user:kim-op'),)):
    events = events or [{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}]
    return engine.Definition.from_dict({
        'processDefinitionId': 'probe', 'processDefinitionName': 'probe', 'version': '1',
        'activities': activities, 'events': events, 'gateways': list(gateways),
        'roles': [{'name': n, 'endpoint': e} for n, e in roles],
        'sequences': [dict(id=f's{i}', **s) for i, s in enumerate(sequences)]})


def _human(aid, **extra):
    return dict(id=aid, name=aid, type='userTask', role='담당', tool='formHandler:defaultForm', **extra)


def _agent(aid):
    return dict(id=aid, name=aid, type='userTask', role='담당', agentMode='COMPLETE', orchestration='cliagents', tool='formHandler:defaultForm')


# ---------------------------------------------------------------- #2 사람 단계 시한은 벽시계
@pytest.mark.parametrize('activity, scale, expected_s', [
    (_human('approve'), 20, 600),                       # 사람 단계 — 배속을 곱하지 않는다
    (_human('approve'), 1, 600),
    (_agent('think'), 20, 30),                          # 에이전트 단계 — 배속 그대로(설비 시간)
    (dict(_human('wait'), type='serviceTask', tool='process:wait'), 20, 600 / (20 * 60)),   # 기다리는 부품 — 배속 × 수업 압축
])
def test_경계_타이머의_마감은_사람_단계면_벽시계_그_밖은_배속_규칙이다(activity, scale, expected_s):
    engine.configure_wait_compression(60)
    event = {'id': 'late', 'type': 'boundaryEvent', 'eventDefinition': 'timer', 'timer': 'PT10M'}
    row = engine.new_event_workitem(_defn([activity], [], events=[{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}, event]),
                                    {'proc_inst_id': 'p', 'tenant_id': 'hyd'}, event, T0, engine.timer_scale(activity, scale))
    due = datetime.fromisoformat(row['due_date'].replace('Z', '+00:00'))
    assert due - T0 == timedelta(seconds=expected_s)


# ---------------------------------------------------------------- #15 닫은 가지로 병렬 합류가 막히면 처리 건을 닫는다
def _parallel():
    return _defn([_agent('x'), _agent('y'), _human('after')],
                 [dict(source='start', target='split'), dict(source='split', target='x'), dict(source='split', target='y'),
                  dict(source='x', target='join'), dict(source='y', target='join'), dict(source='join', target='after'),
                  dict(source='after', target='end')],
                 gateways=[{'id': 'split', 'type': 'parallelGateway'}, {'id': 'join', 'type': 'parallelGateway'}])


def _run(defn):
    inst = engine.new_instance(defn, {}, now=T0)
    adv = engine.start(defn, inst, now=T0)
    return inst, {w['activity_id']: w for w in adv.created}


def test_닫은_가지가_병렬_합류로_들어가면_남은_가지가_끝날_때_처리_건을_사람_닫음으로_끝낸다():
    """#15: 전에는 남은 가지가 합류에 닿아도 합류가 영영 열리지 않아 처리 건이 RUNNING 인데 열린 일 0으로 남았다."""
    defn = _parallel()
    inst, rows = _run(defn)
    rows['x'].update(status='CANCELLED')                         # 사람이 멈춘 에이전트 단계를 [닫기]
    engine.submit(defn, inst, rows['y'], {}, now=T0)
    adv = engine.process_submitted(defn, inst, rows['y'], list(rows.values()), now=T0)
    assert adv.ended == engine.HUMAN_CLOSE_END_EVENT and inst['status'] == 'COMPLETED'
    assert rows['after']['status'] == 'CANCELLED', '닿지 않은 다음 단계는 취소로 정리한다'


def test_두_가지가_모두_끝나면_병렬_합류가_열린다():
    defn = _parallel()
    inst, rows = _run(defn)
    for aid in ('x', 'y'):
        engine.submit(defn, inst, rows[aid], {}, now=T0)
        adv = engine.process_submitted(defn, inst, rows[aid], list(rows.values()), now=T0)
    assert adv.ended is None and rows['after']['status'] == 'IN_PROGRESS' and inst['status'] == 'RUNNING'


def test_다른_가지가_아직_진행_중이면_닫은_가지가_있어도_기다린다():
    defn = _parallel()
    inst, rows = _run(defn)
    rows['x'].update(status='CANCELLED')
    rows['y'].update(status='IN_PROGRESS')
    after = engine.Advance()
    engine._advance(defn, inst, 'split', list(rows.values()), after, T0, 1.0)
    assert after.ended is None and inst['status'] == 'RUNNING'


# ---------------------------------------------------------------- A-11 깨진 흐름 선 속성은 조용히 빈 값이 되지 않는다
@pytest.mark.parametrize('properties, result', [
    (None, {}), ({'default': True}, {'default': True}), (json.dumps({'priority': 2}), {'priority': 2}),
    ('{"default": tr', ValueError), ('[1, 2]', ValueError), (7, ValueError),
])
def test_흐름_선_properties는_객체만_받고_깨진_값은_선_id를_붙여_실패한다(properties, result):
    seq = {'id': 'flow-9', 'source': 'a', 'target': 'b', 'properties': properties}
    if result is ValueError:
        with pytest.raises(ValueError, match='flow-9'):
            engine._properties(seq)
    else:
        assert engine._properties(seq) == result
