"""판단 ↔ 생산 작업 · 세대 묶기(procsvc/decision_scope.py) — 판단은 그것을 낸 작업 · 세대에만 붙는다(세대와 상관없이 같은 규칙)."""
import pytest

from procsvc import decision_scope, engine

DEFN = engine.Definition.from_dict({
    'processDefinitionId': 'p', 'processDefinitionName': 'p', 'version': '1',
    'activities': [{'id': 'T_agent', 'name': '판단', 'type': 'userTask', 'role': 'a', 'agentMode': 'COMPLETE', 'orchestration': 'cliagents',
                    'tool': 'formHandler:f', 'outputData': ['decision_id']},
                   {'id': 'T_note', 'name': '메모', 'type': 'userTask', 'role': 'a', 'agentMode': 'COMPLETE', 'orchestration': 'cliagents',
                    'tool': 'formHandler:g', 'outputData': ['note']}],
    'events': [{'id': 's', 'type': 'startEvent'}, {'id': 'e', 'type': 'endEvent'}], 'roles': [{'name': 'a', 'endpoint': 'sys:agent'}],
    'sequences': [{'id': 'f1', 'source': 's', 'target': 'T_agent'}, {'id': 'f2', 'source': 'T_agent', 'target': 'T_note'},
                  {'id': 'f3', 'source': 'T_note', 'target': 'e'}]})


def _case(generation=0):
    inst = {'proc_inst_id': 'p.1', 'tenant_id': 'hyd', 'proc_def_version': '1', 'status': 'RUNNING', 'rework_generation': generation,
            'variables_data': [{'key': 'incident', 'value': 'INC-1'}, {'key': 'asset', 'value': 'HYD-01'}]}
    wi = {'id': 'w-1', 'tenant_id': 'hyd', 'proc_inst_id': 'p.1', 'version': '1', 'generation': generation, 'activity_id': 'T_agent',
          'status': 'IN_PROGRESS', 'draft_status': 'STARTED', 'consumer': 'worker-1', 'agent_orch': 'cliagents'}
    scope = dict(decision_scope.expected(inst, wi), consumer='worker-1')
    return inst, wi, scope


@pytest.mark.parametrize('generation', [0, 2])
def test_그_작업_세대의_유효한_실행이_낸_판단만_받는다(generation):
    inst, wi, scope = _case(generation)
    decision_scope.validate_submission(inst, DEFN, wi, scope)


@pytest.mark.parametrize('change, words', [
    (lambda inst, wi, scope: scope.update(generation=1), '작업/세대/정의 판본'),
    (lambda inst, wi, scope: scope.update(workitem='w-other'), '작업/세대/정의 판본'),
    (lambda inst, wi, scope: scope.update(consumer='late-worker'), 'worker claim'),
    (lambda inst, wi, scope: wi.update(draft_status='COMPLETED'), 'worker claim'),
    (lambda inst, wi, scope: inst.update(status='COMPLETED'), '종료된 인스턴스'),
    (lambda inst, wi, scope: wi.update(activity_id='T_note'), '판단 ID를 출력하는'),
    (lambda inst, wi, scope: wi.update(version='2'), '소유권/판본'),
])
def test_다른_작업_세대_늦은_실행_끝난_처리_건의_판단은_받지_않는다(change, words):
    inst, wi, scope = _case()
    change(inst, wi, scope)
    with pytest.raises(ValueError, match=words):
        decision_scope.validate_submission(inst, DEFN, wi, scope)


def test_범위가_없는_판단은_0세대에도_받지_않는다():
    """P1-20: 전에는 0세대 판단을 범위 없이 받던 호환 갈래가 있었다(워커 · dmn-mcp 는 늘 범위를 싣는다)."""
    inst, wi, _ = _case(0)
    with pytest.raises(ValueError, match='process_scope'):
        decision_scope.validate_submission(inst, DEFN, wi, None)


@pytest.mark.parametrize('decision, ok', [
    ({'state': 'PENDING_APPROVAL', 'asset': 'HYD-01', 'origin': {'incident': 'INC-1'}}, True),
    ({'state': 'APPROVED', 'asset': 'HYD-01', 'origin': {'incident': 'INC-1'}}, False),        # 이미 처리한 판단 재사용
    ({'state': 'PENDING_APPROVAL', 'asset': 'HYD-01', 'origin': {'incident': 'INC-9'}}, False),  # 다른 사건의 판단
    (None, False),
])
def test_작업_결과의_판단은_그_작업_세대가_새로_낸_승인_대기_판단이어야_한다(decision, ok):
    inst, wi, scope = _case()
    if decision is not None:
        decision = dict(decision, origin=dict(decision['origin'], process_scope=decision_scope.expected(inst, wi)))
    if ok:
        decision_scope.validate_output(inst, wi, decision)
    else:
        with pytest.raises(ValueError):
            decision_scope.validate_output(inst, wi, decision)
