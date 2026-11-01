"""다시 수행의 입장 일정(procsvc/dependency_schedule.py) — 다시 들어간 단계는 흐름 도착과 생산자의 새 완료를 둘 다 기다린다."""
from datetime import datetime, timezone

import pytest

from procsvc import dependency_schedule, engine

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)


def _defn(gateways=(), sequences=None, activities=None):
    activities = activities or [
        {'id': 'a', 'name': 'a', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'outputData': ['x']},
        {'id': 'b', 'name': 'b', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'inputData': ['x'], 'outputData': ['y']},
        {'id': 'c', 'name': 'c', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'inputData': ['y']}]
    sequences = sequences or [('s', 'a'), ('a', 'b'), ('b', 'c'), ('c', 'e')]
    return engine.Definition.from_dict({
        'processDefinitionId': 'p', 'processDefinitionName': 'p', 'version': '1', 'activities': activities, 'gateways': list(gateways),
        'events': [{'id': 's', 'type': 'startEvent'}, {'id': 'e', 'type': 'endEvent'}], 'roles': [{'name': 'r', 'endpoint': 'user:x'}],
        'data': [{'name': 'x', 'type': 'Text'}, {'name': 'y', 'type': 'Text'}],
        'sequences': [{'id': f'f{i}', 'source': a, 'target': b, **({'condition': c} if c else {})}
                      for i, (a, b, *rest) in enumerate(sequences) for c in [rest[0] if rest else None]]})


def _done_case(defn):
    inst = engine.new_instance(defn, {}, now=T0)
    rows = engine.start(defn, inst, now=T0).created
    by = {w['activity_id']: w for w in rows}
    for aid, out in (('a', {'x': '1'}), ('b', {'y': '2'})):
        engine.submit(defn, inst, by[aid], out, now=T0)
        engine.process_submitted(defn, inst, by[aid], rows, now=T0)
    return inst, rows, by


def test_뒤_단계는_다시_들어간_앞_단계의_새_결과를_기다린다():
    defn = _defn()
    inst, rows, by = _done_case(defn)
    specs, blockers = dependency_schedule.propose(defn, inst, rows, {'a', 'b', 'c'}, {'a'}, 'a')
    assert blockers == [] and specs['b']['requires'] == {'a': ['x']} and specs['c']['requires'] == {'b': ['y']}
    assert specs['a']['flow_arrived'] and not specs['b']['flow_arrived'], '다시 수행의 시작 단계만 이미 흐름이 닿았다'


def test_새_결과가_생기기_전에는_닿아도_열지_않고_까닭을_남긴다():
    defn = _defn()
    inst, rows, by = _done_case(defn)
    specs, _ = dependency_schedule.propose(defn, inst, rows, {'b', 'c'}, set(), 'b')
    fresh = {aid: dict(engine.new_workitem(defn, inst, defn.activities[aid], T0), generation=1) for aid in ('b', 'c')}
    dependency_schedule.install(inst, specs, list(fresh.values()), 'REQ-1')
    spec = dependency_schedule.entry(inst, fresh['c'])
    spec['flow_arrived'] = True
    assert not dependency_schedule.ready(inst, fresh['c'], rows + list(fresh.values()))
    assert spec['waiting_for'] == [{'workitem': fresh['b']['id'], 'reason': 'producer_not_done_or_superseded'}]
    assert dependency_schedule.waiting(inst, list(fresh.values())), '흐름이 닿은 채 기다리는 TODO 는 열린 일이다(처리 건을 끝내지 않는다)'


def test_같은_값을_내는_생산자가_둘이면_막고_까닭_코드를_준다():
    acts = [{'id': 'a', 'name': 'a', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'outputData': ['x']},
            {'id': 'a2', 'name': 'a2', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'outputData': ['x']},
            {'id': 'b', 'name': 'b', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'inputData': ['x']}]
    defn = _defn(sequences=[('s', 'a'), ('a', 'a2'), ('a2', 'b'), ('b', 'e')], activities=acts)
    inst = engine.new_instance(defn, {}, now=T0)
    rows = engine.start(defn, inst, now=T0).created
    _, blockers = dependency_schedule.propose(defn, inst, rows, {'a', 'a2', 'b'}, {'a'}, 'a')
    assert {b['code'] for b in blockers} == {'ambiguous_dependency_producer'}


def test_시작_단계가_이번에_새로_만들_결과를_입력으로_받으면_막는다():
    defn = _defn()
    inst, rows, _ = _done_case(defn)
    _, blockers = dependency_schedule.propose(defn, inst, rows, {'a', 'b', 'c'}, {'b'}, 'b')
    assert 'rework_root_dependency_requires_review' in {b['code'] for b in blockers}


@pytest.mark.parametrize('code', ['condition_replay_requires_arrival', 'ambiguous_dependency_producer', 'dependency_reference_requires_review',
                                  'dependency_control_arrival_unavailable', 'rework_root_dependency_requires_review',
                                  'dependency_cycle_requires_review'])
def test_막힘_코드마다_학생이_읽는_문장이_있다(code):
    """P4-03 · W1-09: 막힘 문장의 주인은 rework.BLOCKER_TEXT 하나 — 이 모듈이 만드는 코드도 그 표에 있어야 화면이 뜻 없는 문장으로 메우지 않는다."""
    from procsvc import rework
    assert rework.blocker(code)['text'], '표에 없는 코드는 KeyError 로 실패한다'
