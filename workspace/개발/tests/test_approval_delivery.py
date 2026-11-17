"""승인 전달(procsvc/approval_delivery.py) — 사람 승인 하나는 한 번 전달되고, 실패는 기록되며 끝없이 다시 보내지 않는다.

실제 엔진 · 실제 agent(승인 현재 조건 검사) · 실제 업무 시스템으로 흐름 A(냉각)를 돌린다. 「다시 보내지 않았다」는 승인 행의 시도 수 ·
기록(attempts · history)으로 판정한다(대체물의 호출 수를 세지 않는다).
"""
import re

import pytest

from conftest import OPERATOR
from procsvc import approval_delivery
from procsvc.inbox import NOT_A_PERSON


def test_전달_뒤_흐름_진행이_실패해도_승인을_다시_전달하지_않고_실패를_기록한다(world):
    """#17: 전에는 전달과 흐름 진행이 한 트랜잭션이라, 진행이 실패하면 전달까지 되돌아가 2초마다 현재 조건 검사 · 전달을 되풀이했고
    실패 기록도 없었다. 이제 전달은 한 번 커밋되고, 진행 실패는 그 단계의 오류로 남아 세 번이면 멈춘다."""
    alert, pid, decision = world.start_cooling()
    with world.storage_fails('todolist', f"NEW.proc_inst_id = '{pid}' AND NEW.activity_id = 'T_cmd' AND NEW.status = 'SUBMITTED'"):
        world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
        world.poll(3)
        approve = world.row(pid, 'T_approve')
        approval = world.rt.repo.get_approval(approve['id'], 'hyd')
        assert approval['status'] == 'DELIVERED' and approval['attempts'] == 1
        assert [h['status'] for h in approval['history']].count('DELIVERED') == 1, '전달은 한 번'
        errors = [e for e in world.events(todo=approve['id']) if e['job_id'] == 'TASK_ERROR']
        assert approve['status'] == 'PENDING' and len(errors) == 3, (approve['status'], len(errors))
        assert '3번 실패해 멈췄습니다' in errors[-1]['data']['friendly'], 'A-06: 학생이 읽을 문장(무엇이 · 다음에 무엇을)'
    assert world.kafka.of('action.cmd') == [], '진행이 막힌 동안 설비 명령은 나가지 않는다'


def test_전달_자체가_저장소에서_연달아_실패하면_세_번째에_실패로_멈추고_다시_전달할_수_있다(world):
    """P4-17: 전에는 전달 바깥(트랜잭션 · 저장소) 실패를 로그에만 남기고 2초마다 끝없이 다시 보냈다 — 화면엔 「전달 대기」만 보였다."""
    alert, pid, decision = world.start_cooling()
    # 전달을 세 번 다시 하는 동안에도 설비는 1초마다 보고한다 — 보고가 끊기면 승인 현재 조건 검사가 관측 공백(503)으로 멈춰 이 시험이 재려는
    # 저장소 실패가 아니라 그 503으로 실패했다(2026-11-01 판단끝_테스트)
    with world.reporting('HYD-01'), world.storage_fails('process_approval_outbox', "NEW.status = 'DELIVERED'"):
        world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
        approve = world.row(pid, 'T_approve')
        for _ in range(approval_delivery.DELIVERY_STOP_AFTER):
            world.poll()
        approval = world.rt.repo.get_approval(approve['id'], 'hyd')
        assert approval['status'] == 'FAILED' and approval['history'][-1]['kind'] == 'transient', approval['history'][-1]
        assert '연달아 처리되지 못해 멈췄습니다' in approval['error'] and '저장소가 이 쓰기를 거절함' in approval['error']
        assert any(e['job_id'] == 'APPROVAL_DELIVERY' and e['event_type'] == 'error' for e in world.events(todo=approve['id']))
        attempts = approval['attempts']
        world.poll(2)
        assert world.rt.repo.get_approval(approve['id'], 'hyd')['attempts'] == attempts, '멈춘 승인을 폴링이 다시 보내지 않는다'
    # 전수 검사 01 지적 4: 다시 전달 · 폐기는 「누가」가 비어 있지 않은지만 봐서 자유 글 이름이 승인 기록에 남았다 — 등록된 사람 사용자이고
    # 내세운 역할의 구성원이어야 한다(승인 · 거절과 같은 규칙)
    for call in (world.rt.retry_approval, world.rt.preview_approval_discard,
                 lambda wid, by, role: world.rt.discard_approval(wid, by, role, '시험 폐기', 'req-1')):
        for by, role, words in (('강사', OPERATOR['role'], re.escape(NOT_A_PERSON)), ('user:nobody', OPERATOR['role'], '없는 사람 사용자'),
                                (OPERATOR['by'], 'role:nobody', '역할이 아니어서')):
            with pytest.raises(PermissionError, match=words):
                call(approve['id'], by, role)
    after = world.rt.repo.get_approval(approve['id'], 'hyd')
    assert (after['status'], len(after['history'])) == ('FAILED', len(approval['history'])), '거절된 요청은 승인 기록을 바꾸지 않는다'
    with world.reporting('HYD-01'):
        world.rt.retry_approval(approve['id'], OPERATOR['by'], OPERATOR['role'])
    after = world.rt.repo.get_approval(approve['id'], 'hyd')
    assert after['status'] == 'DELIVERED', '사람이 다시 전달하면 전달된다'
    assert [(h.get('by'), h.get('role')) for h in after['history'] if h.get('reason') == 'manual retry'] == [(OPERATOR['by'], OPERATOR['role'])]


def test_전달_때_현재_조건이_승인을_받지_않으면_실패로_남고_같은_동의를_다시_보내지_않는다(world):
    """접수 뒤 전달 전에 업무 기준점(납기 · 예정된 정비 시간)이 옮겨지면 실제 agent 의 현재 조건 검사가 그 동의를 받지 않는다."""
    alert, pid, decision = world.start_cooling()
    with world.storage_fails('process_approval_outbox', "NEW.status = 'DELIVERED'"):
        world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)       # 접수 · 첫 전달(저장소가 막아 대기로 남음)
    approve = world.row(pid, 'T_approve')
    world.main._entsim_post('/api/reanchor', {})                           # 판단 뒤 업무 시각 기준점이 바뀜(수업 버튼과 같은 길)
    world.poll()
    approval = world.rt.repo.get_approval(approve['id'], 'hyd')
    assert approval['status'] == 'FAILED' and approval['history'][-1]['kind'] == 'review_required', approval['history'][-1]
    world.poll(2)
    assert world.rt.repo.get_approval(approve['id'], 'hyd')['status'] == 'FAILED', '실패한 동의를 폴링이 다시 보내지 않는다'
    with pytest.raises(ValueError, match='새 판단과 승인'):
        world.rt.retry_approval(approve['id'], OPERATOR['by'], OPERATOR['role'])
    assert world.kafka.of('action.cmd') == []
