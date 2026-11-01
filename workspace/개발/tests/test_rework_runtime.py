"""다시 수행 실행(procsvc/rework_runtime.py) — 미리보기 표식을 다시 대조해 새 차수를 만들고, 같은 요청 id 는 같은 결과를 돌려준다."""
import uuid

import pytest

from conftest import OPERATOR


def _ready(world):
    alert, pid, decision = world.start_cooling()
    agent = world.row(pid, 'T_agent')
    return pid, agent, world.rt.preview_rework(pid, agent['id']), decision


def test_승인_전_판단_단계부터_새_차수를_만들면_그_단계가_다시_열리고_영수증이_남는다(world):
    pid, agent, plan, decision = _ready(world)
    rid = str(uuid.uuid4())
    result = world.rt.request_rework(pid, agent['id'], rid, plan['snapshot_token'], OPERATOR['by'], OPERATOR['role'], '근거가 바뀜')
    assert result['generation'] == 1 and world.inst(pid)['rework_generation'] == 1
    new = next(w for w in world.rows(pid) if w['id'] == result['start_workitem'])
    assert new['activity_id'] == 'T_agent' and new['supersedes_id'] == agent['id']
    assert world.rt.repo.get_rework('hyd', pid, rid)['result']['generation'] == 1
    assert any(e['job_id'] == 'PROCESS_REWORK' for e in world.events(pid))


def test_같은_요청_id로_다시_보내면_새_차수를_또_만들지_않고_처음_결과를_돌려준다(world):
    pid, agent, plan, decision = _ready(world)
    rid = str(uuid.uuid4())
    args = (pid, agent['id'], rid, plan['snapshot_token'], OPERATOR['by'], OPERATOR['role'], '근거가 바뀜')
    first = world.rt.request_rework(*args)
    assert world.rt.request_rework(*args) == first and world.inst(pid)['rework_generation'] == 1
    with pytest.raises(ValueError, match='다른 재작업 내용'):
        world.rt.request_rework(pid, agent['id'], rid, plan['snapshot_token'], OPERATOR['by'], OPERATOR['role'], '다른 사유')


@pytest.mark.parametrize('request_id, token, role, reason, error', [
    ('not-a-uuid', 'tok', 'role:operator', '사유', 'UUID여야'),
    (None, ' ', 'role:operator', '사유', '관측 token, 요청자, 역할, 사유'),
    (None, 'tok', 'role:operator', '', '관측 token, 요청자, 역할, 사유'),
    (None, 'tok', 'role:nobody', '사유', '사람 업무 담당 역할'),
], ids=['요청 id 꼴', '표식 없음', '사유 없음', '흐름에 없는 역할'])
def test_다시_수행_요청은_요청_id_표식_역할_사유를_검사한다(world, request_id, token, role, reason, error):
    pid, agent, plan, decision = _ready(world)
    with pytest.raises((ValueError, PermissionError), match=error):
        world.rt.request_rework(pid, agent['id'], request_id or str(uuid.uuid4()), token, OPERATOR['by'], role, reason)


def test_미리보기_뒤에_처리_건이_바뀌면_다시_확인하라고_거절한다(world):
    pid, agent, plan, decision = _ready(world)
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    with pytest.raises(ValueError, match='미리보기 이후 실행 상태가 바뀌었습니다'):
        world.rt.request_rework(pid, agent['id'], str(uuid.uuid4()), plan['snapshot_token'], OPERATOR['by'], OPERATOR['role'], '사유')
