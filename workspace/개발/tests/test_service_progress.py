"""시스템 시도 관측 기록(procsvc/service_progress.py) — 처리 건 전이와 따로 커밋되는 도구 호출 관측의 소유 · 형식 검사."""
import pytest

from procsvc import service_progress as sp

PID, TODO, OWNER = 'c3_cooling.x', 'todo-1', 'engine:service:1'


def _row(**changes):
    row = {'id': 'e1', 'proc_inst_id': PID, 'todo_id': TODO, 'job_id': 'MCP_EFFECT_CALL', 'event_type': 'tool_usage_started',
           'data': {'system_observation': True, 'attempt_id': 'a1'}}
    row.update(changes)
    return row


@pytest.mark.parametrize('rows, error', [
    ([_row()], None),
    ([_row(job_id='SYSTEM_ATTEMPT_COMMITTED', event_type='task_working')], None),
    ([], 'empty'),
    ([_row(proc_inst_id='other')], 'case mismatch'),
    ([_row(id=None)], 'case mismatch'),
    ([_row(data={'attempt_id': 'a1'})], 'correlation missing'),
    ([_row(event_type='task_completed')], 'only observational'),
    ([_row(job_id='MCP_EFFECT_CALL', event_type='task_working')], 'only observational'),
], ids=['도구 시작', '시도 닫기', '빈 목록', '다른 처리 건', 'id 없음', '시도 id 없음', '완료 기록', '닫기가 아닌 작업 기록'])
def test_관측_기록은_그_단계의_도구_호출과_시도_닫기만_받는다(rows, error):
    if error is None:
        sp.validate_rows(rows, PID, TODO)
    else:
        with pytest.raises(ValueError, match=error):
            sp.validate_rows(rows, PID, TODO)


INST = {'tenant_id': 'hyd', 'proc_inst_id': PID, 'status': 'RUNNING', 'is_deleted': False}
ITEM = {'tenant_id': 'hyd', 'proc_inst_id': PID, 'id': TODO, 'status': 'SUBMITTED', 'agent_orch': 'hyd-process', 'consumer': OWNER}


@pytest.mark.parametrize('inst, item, consumer, error', [
    (INST, ITEM, OWNER, None),
    (dict(INST, tenant_id='other'), ITEM, OWNER, 'tenant mismatch'),
    (INST, dict(ITEM, proc_inst_id='x'), OWNER, 'case mismatch'),
    (dict(INST, status='COMPLETED'), ITEM, OWNER, 'committed SYSTEM claim'),
    (INST, dict(ITEM, agent_orch='cliagents'), OWNER, 'committed SYSTEM claim'),
    (INST, ITEM, 'someone-else', 'committed SYSTEM claim'),
], ids=['점유한 시스템 단계', '다른 테넌트', '다른 처리 건', '끝난 처리 건', 'AI 단계', '다른 점유자'])
def test_관측은_그_시스템_단계를_지금_점유한_실행만_남길_수_있다(inst, item, consumer, error):
    if error is None:
        sp.require_owner(inst, item, 'hyd', PID, TODO, consumer)
    else:
        with pytest.raises(PermissionError, match=error):
            sp.require_owner(inst, item, 'hyd', PID, TODO, consumer)


def test_시도_닫기는_그_시도를_시작한_점유자만_한다():
    start = {'data': {'attempt_id': 'a1', 'owner_claim_hash': sp.owner_hash(OWNER)}}
    close = {'data': {'attempt_id': 'a1'}}
    sp.require_closure(INST, ITEM, start, 'hyd', PID, TODO, OWNER, close)
    with pytest.raises(PermissionError, match='no owned invocation'):
        sp.require_closure(INST, ITEM, start, 'hyd', PID, TODO, 'other-owner', close)
    assert sp.owner_hash(OWNER) == sp.owner_hash(OWNER) != sp.owner_hash('other-owner')
