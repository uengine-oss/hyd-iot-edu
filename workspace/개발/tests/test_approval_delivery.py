"""승인 전달(procsvc/approval_delivery.py) — 사람 승인 하나는 한 번 전달되고, 뒤따르는 흐름 진행의 실패는 기록된다."""
from test_instances import OPERATOR, _start_cooling


def test_전달_뒤_흐름_진행이_실패해도_승인을_다시_전달하지_않고_실패를_기록한다(world):
    """#17: 전에는 전달과 흐름 진행이 한 트랜잭션이라, 진행이 실패하면 전달까지 되돌아가 2초마다 현재 조건 검사 · 전달을 되풀이했고
    실패 기록도 없었다. 이제 전달은 한 번 커밋되고, 진행 실패는 그 단계의 오류로 남아 세 번이면 멈춘다."""
    alert, pid, decision = _start_cooling(world)
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    with world.storage_fails('todolist', f"NEW.proc_inst_id = '{pid}' AND NEW.activity_id = 'T_cmd' AND NEW.status = 'SUBMITTED'"):
        world.rt.select(approve['id'], decision, 'skill:sop-cool-11', **OPERATOR)
        checks = len(world.services.verdict['checked'])
        world.poll(3)
        approval = world.rt.repo.get_approval(approve['id'], 'hyd')
        assert approval['status'] == 'DELIVERED' and approval['attempts'] == 1
        assert [h['status'] for h in approval['history']].count('DELIVERED') == 1
        assert len(world.services.verdict['checked']) == checks, '전달(현재 조건 검사)을 되풀이하지 않는다'
        row = world.row(pid, 'T_approve')
        errors = [e for e in world.events(todo=row['id']) if e['job_id'] == 'TASK_ERROR']
        assert row['status'] == 'PENDING' and len(errors) == 3, (row['status'], len(errors))
        assert '3번 실패해 멈췄습니다' in errors[-1]['data']['friendly'], 'A-06: 학생이 읽을 문장(무엇이 · 다음에 무엇을)'
    assert world.kafka.of('action.cmd') == [], '진행이 막힌 동안 설비 명령은 나가지 않는다'


def test_전달_때_현재_조건이_승인을_받지_않으면_실패로_남고_같은_동의를_다시_보내지_않는다(world):
    alert, pid, decision = _start_cooling(world)
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    world.services.verdict.update(refuse='현재 유온이 검토한 예측보다 높습니다', refuse_after=len(world.services.verdict['checked']) + 1)
    world.rt.select(approve['id'], decision, 'skill:sop-cool-11', **OPERATOR)        # 접수 때 검사는 받고, 전달 때 검사가 거절한다
    approval = world.rt.repo.get_approval(approve['id'], 'hyd')
    assert approval['status'] == 'FAILED' and approval['history'][-1]['kind'] == 'review_required'
    assert any(e['job_id'] == 'APPROVAL_DELIVERY' and e['event_type'] == 'error' for e in world.events(todo=approve['id']))
    world.poll(2)
    assert world.rt.repo.get_approval(approve['id'], 'hyd')['status'] == 'FAILED', '실패한 동의를 폴링이 다시 보내지 않는다'
    import pytest
    with pytest.raises(ValueError, match='새 판단과 승인'):
        world.rt.retry_approval(approve['id'], OPERATOR['by'], OPERATOR['role'])
    assert world.kafka.of('action.cmd') == []
