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


# ---------------------------------------------------------------- 막힘마다 학생이 읽는 문장 — 엔진이 실제로 그 막힘을 내는 처리 건에서
def _branch_case():
    """a → 분기(x == '1' 이면 b, 아니면 d) — x = '1' 로 끝난 처리 건(b 는 끝났고 d 는 흐름이 닿지 않은 채 취소)."""
    acts = [{'id': 'a', 'name': 'a', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'outputData': ['x']},
            {'id': 'b', 'name': 'b', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'inputData': ['x']},
            {'id': 'd', 'name': 'd', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'inputData': ['x']}]
    defn = _defn(gateways=[{'id': 'g', 'type': 'exclusiveGateway'}], activities=acts,
                 sequences=[('s', 'a'), ('a', 'g'), ('g', 'b', "x == '1'"), ('g', 'd', "x != '1'"), ('b', 'e'), ('d', 'e')])
    inst = engine.new_instance(defn, {}, now=T0)
    rows = engine.start(defn, inst, now=T0).created
    by = {w['activity_id']: w for w in rows}
    for aid, out in (('a', {'x': '1'}), ('b', {})):
        engine.submit(defn, inst, by[aid], out, now=T0)
        engine.process_submitted(defn, inst, by[aid], rows, now=T0)
    assert (by['d']['status'], inst['status']) == ('CANCELLED', 'COMPLETED')
    return defn, inst, rows


def _gateway_without_its_review():
    """분기만 다시 판단하려 한다 — 분기 조건을 낼 앞 단계(a)는 다시 하지 않는다."""
    defn, inst, rows = _branch_case()
    return defn, inst, rows, {'g', 'b'}, {'b'}, 'b'


def _two_producers():
    """a 와 a2 가 같은 값 x 를 낸다 — 둘 다 다시 하면 b 는 어느 쪽의 새 x 를 기다릴지 정할 수 없다."""
    acts = [{'id': 'a', 'name': 'a', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'outputData': ['x']},
            {'id': 'a2', 'name': 'a2', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'outputData': ['x']},
            {'id': 'b', 'name': 'b', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'inputData': ['x']}]
    defn = _defn(sequences=[('s', 'a'), ('a', 'a2'), ('a2', 'b'), ('b', 'e')], activities=acts)
    inst = engine.new_instance(defn, {}, now=T0)
    return defn, inst, engine.start(defn, inst, now=T0).created, {'a', 'a2', 'b'}, {'a'}, 'a'


def _reference_superseded():
    """b 가 참조한 a 의 결과 뒤에 a 의 새 세대가 끝났다 — b 부터 다시 하면 b 가 참조한 결과는 이제 a 의 최신이 아니다."""
    defn = _defn()
    inst, rows, by = _done_case(defn)
    redone = dict(engine.new_workitem(defn, inst, defn.activities['a'], T0), generation=1, status='DONE')
    assert by['a']['id'] in by['b']['reference_ids']
    return defn, inst, rows + [redone], {'b', 'c'}, set(), 'b'


def _never_reached_entry():
    """흐름이 닿지 않아 취소된 단계(분기의 가지 않은 쪽)부터 다시 하려 한다."""
    defn, inst, rows = _branch_case()
    return defn, inst, rows, {'d'}, set(), 'd'


def _root_needs_new_result():
    """b 부터 다시 하는데 a 도 다시 한다 — 시작 단계 b 가 이번에 새로 만들어질 a 의 결과를 입력으로 받는다."""
    defn = _defn()
    inst, rows, _ = _done_case(defn)
    return defn, inst, rows, {'a', 'b', 'c'}, {'b'}, 'b'


def _waiting_on_each_other():
    """a 는 b 의 결과 y 를, b 는 a 의 결과 x 를 입력으로 받는다 — 둘 다 다시 하면 서로의 새 결과를 기다린다."""
    acts = [{'id': 'a', 'name': 'a', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'inputData': ['y'], 'outputData': ['x']},
            {'id': 'b', 'name': 'b', 'type': 'userTask', 'role': 'r', 'tool': 'formHandler:f', 'inputData': ['x'], 'outputData': ['y']}]
    defn = _defn(sequences=[('s', 'a'), ('a', 'b'), ('b', 'e')], activities=acts)
    inst = engine.new_instance(defn, {}, now=T0)
    return defn, inst, engine.start(defn, inst, now=T0).created, {'a', 'b'}, set(), 'a'


@pytest.mark.parametrize('codes, case', [
    ({'condition_replay_requires_arrival'}, _gateway_without_its_review),
    ({'ambiguous_dependency_producer'}, _two_producers),
    ({'dependency_reference_requires_review'}, _reference_superseded),
    ({'dependency_control_arrival_unavailable'}, _never_reached_entry),
    ({'rework_root_dependency_requires_review'}, _root_needs_new_result),
    ({'dependency_cycle_requires_review', 'rework_root_dependency_requires_review'}, _waiting_on_each_other),     # 시작 단계 a 도 b 의 새 결과를 기다린다
], ids=['분기만 다시', '같은 값의 생산자 둘', '참조한 결과가 바뀜', '흐름이 닿지 않은 시작 단계', '시작 단계가 새 결과를 기다림', '서로 기다림'])
def test_다시_수행을_막는_까닭마다_엔진이_그_막힘을_내고_학생이_읽는_문장이_있다(codes, case):
    """P4-03 · W1-09: 막힘 문장의 주인은 rework.BLOCKER_TEXT 하나다. 다시 수행 계획(rework.plan)은 이 모듈이 낸 막힘을 rework.blocker 로 문장으로
    바꾼다 — 표에 없는 코드는 그 자리에서 KeyError 다. 막힘마다 그것을 실제로 내는 처리 건에서 같은 길로 바꿔 문장이 있는지 본다."""
    from procsvc import rework
    _, blockers = dependency_schedule.propose(*case())
    assert {b['code'] for b in blockers} == codes, blockers
    assert all(rework.blocker(**b)['text'] for b in blockers)
