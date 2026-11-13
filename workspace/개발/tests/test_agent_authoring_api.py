"""에이전트 · 스킬 만들기 API(procsvc/agent_authoring_api.py) — 학생 PC 구성(world)에서 포털과 같은 경로로."""
import pytest

TENANT = 'hyd'


@pytest.fixture
def my_agent(world):
    status, body = world.api('POST', '/api/agents', {'name': 'API 시험 에이전트', 'goal': '점검', 'tools': ['neo4j']})
    assert status == 201, body
    yield body
    status, out = world.api('DELETE', f"/api/agents/{body['id']}?by=user:me")
    assert status in (200, 404), out                       # 시험이 이미 지웠으면 404


def test_폼_선택지는_서버마다_붙일_수_있는지와_수업_모델을_준다(world):
    status, body = world.api('GET', '/api/agent-authoring/options')
    assert status == 200
    assert all({'name', 'selectable', 'reason'} <= set(s) for s in body['servers'])
    assert len(body['models']) == 1


def test_고치기에_빠진_칸이_있으면_422로_거절하고_바꾸지_않는다(world, my_agent):
    status, body = world.api('PUT', f"/api/agents/{my_agent['id']}", {'name': 'API 시험 에이전트', 'goal': '바꿈'})
    assert status == 422 and '빠진 칸' in body['detail']
    assert world.api('GET', f"/api/agents/{my_agent['id']}")[1]['goal'] == '점검'


def test_모든_칸을_보내면_고친다(world, my_agent):
    body = {'name': 'API 시험 에이전트', 'role': '', 'goal': '바꿈', 'persona': '', 'model': '', 'tools': ['neo4j'], 'skills': [], 'work_rules': None}
    status, out = world.api('PUT', f"/api/agents/{my_agent['id']}", body)
    assert (status, out['goal']) == (200, '바꿈')


def test_기본_에이전트는_고칠_수_없고_복제하라고_말한다(world):
    body = {'name': 'x', 'role': '', 'goal': 'x', 'persona': '', 'model': '', 'tools': [], 'skills': [], 'work_rules': None}
    status, out = world.api('PUT', '/api/agents/agent:cooling', body)
    assert status == 403 and '복제해서 고치기' in out['detail']


@pytest.mark.parametrize('by', ['', '?by=', '?by=%20'], ids=['칸 없음', '빈 칸', '공백'])
def test_누가_없이_온_에이전트_지우기는_이름을_지어_넣지_않고_400_으로_거절하고_지우지_않는다(world, my_agent, by):
    """옛 판은 「누가」가 비면 처리 엔진(sys:process)이 한 일로 적었다 — 사람이 지웠는데 열린 단계의 담당 이력에 시스템 수행자가 남았다."""
    status, out = world.api('DELETE', f"/api/agents/{my_agent['id']}{by}")
    assert status == 400 and '담당자 정보 없이 온 요청' in out['detail'], out
    assert world.api('GET', f"/api/agents/{my_agent['id']}")[0] == 200


def test_담당자를_실은_에이전트_지우기는_지운다(world, my_agent):
    status, out = world.api('DELETE', f"/api/agents/{my_agent['id']}?by=user:me")
    assert status == 200 and out['deleted'] == my_agent['id'], out
    assert world.api('GET', f"/api/agents/{my_agent['id']}")[0] == 404


@pytest.mark.parametrize('method, path, body', [
    ('POST', '/api/agents/reset', {}),
    ('POST', '/api/agents/reset', None),
    ('PUT', '/api/agent-assignments', {'definition_id': 'shift_handover', 'activity_id': 'task:draft'}),      # 수업 단계에서 배정이 열려 있는 단계
], ids=['되돌리기 빈 본문', '되돌리기 본문 없음', '단계 배정'])
def test_누가_없이_온_되돌리기와_단계_배정도_400_으로_거절하고_바꾸지_않는다(world, my_agent, method, path, body):
    before = world.api('GET', '/api/agent-assignments')[1]['steps']
    if body and 'definition_id' in body:
        body = dict(body, agent_id=my_agent['id'])
    status, out = world.api(method, path, body)
    assert status == 400 and '담당자 정보 없이 온 요청' in out['detail'], out
    assert world.api('GET', f"/api/agents/{my_agent['id']}")[0] == 200                 # 내가 만든 에이전트가 그대로다
    assert world.api('GET', '/api/agent-assignments')[1]['steps'] == before


def test_열려_있던_단계를_기본_담당으로_돌린_기록에는_지운_사람이_남는다(world):
    """내 에이전트에 배정된 단계가 열려 있을 때 그 에이전트를 지우면 단계는 기본 담당으로 돌아간다 — 그 이력(task_assignments)의 「누가」는 지운 사람이다."""
    import psycopg
    from conftest import start_handover
    status, agent = world.api('POST', '/api/agents', {'name': '이력 시험 에이전트', 'goal': '인계안'})
    assert status == 201, agent
    assert world.api('PUT', '/api/agent-assignments', {'definition_id': 'shift_handover', 'activity_id': 'task:draft', 'agent_id': agent['id'],
                                                       'by': 'user:me'})[0] == 200
    inst = start_handover(world.rt)
    try:
        [row] = [w for w in world.rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'], limit=None) if w['activity_id'] == 'task:draft']
        assert row['user_id'] == agent['id']
        status, out = world.api('DELETE', f"/api/agents/{agent['id']}?by=user:me")
        assert status == 200 and [t['todo_id'] for t in out['returned_tasks']] == [row['id']], out
        with psycopg.connect(world.dsn) as db:
            rows = db.execute("SELECT from_user_id, to_user_id, by_user FROM task_assignments WHERE todo_id=%s ORDER BY created_at", (row['id'],)).fetchall()
        assert [r[2] for r in rows] == ['user:me', 'user:me']                         # 배정을 적용한 기록(배정한 사람) · 되돌린 기록(지운 사람)
        assert rows[-1][0] == agent['id']
    finally:
        with psycopg.connect(world.dsn) as db, db.transaction():
            db.execute("UPDATE todolist SET status='CANCELLED' WHERE proc_inst_id=%s AND status NOT IN ('DONE','CANCELLED')", (inst['proc_inst_id'],))
            db.execute("UPDATE bpm_proc_inst SET status='CANCELLED' WHERE proc_inst_id=%s", (inst['proc_inst_id'],))
        world.api('DELETE', f"/api/agents/{agent['id']}?by=user:me")
