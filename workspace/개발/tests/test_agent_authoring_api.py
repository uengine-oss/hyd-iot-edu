"""에이전트 · 스킬 만들기 API(procsvc/agent_authoring_api.py) — 학생 PC 구성(world)에서 포털과 같은 경로로."""
import pytest

TENANT = 'hyd'


@pytest.fixture
def my_agent(world):
    status, body = world.api('POST', '/api/agents', {'name': 'API 시험 에이전트', 'goal': '점검', 'tools': ['neo4j']})
    assert status == 201, body
    yield body
    world.api('DELETE', f"/api/agents/{body['id']}")


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
