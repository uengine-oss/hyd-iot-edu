"""에이전트 · 스킬 읽기 API(procsvc/agents_api.py) — 학생 PC 구성(world)에서 포털과 같은 경로로. 단계별 실행 설정은 워커와 같은 함수로 계산한다."""
from hydcommon.handover_tools import HANDOVER_READS
from procsvc import agents_api

TENANT = 'hyd'


def test_교대_인계_에이전트의_실행_설정은_교대_단계의_정해진_조회_도구만_보인다(world):
    status, card = world.api('GET', '/api/agents/agent:handover')
    assert status == 200, card
    steps = [s for s in card['run']['steps'] if s['definition_id'] == 'shift_handover']
    assert steps
    for s in steps:
        assert set(s['servers']) <= set(HANDOVER_READS)
        assert all(tools == list(HANDOVER_READS[name]) for name, tools in s['servers'].items())


def test_배정을_바꾸면_그_단계를_맡는_에이전트가_바로_바뀐다(world):
    status, _ = world.api('PUT', '/api/agent-assignments', {'definition_id': 'shift_handover', 'activity_id': 'task:draft',
                                                            'agent_id': 'agent:cooling', 'by': '수강생'})
    try:
        assert status == 200
        run = next(s for s in agents_api.step_runs(world.rt) if (s['definition_id'], s['activity_id']) == ('shift_handover', 'task:draft'))
        assert run['agent_id'] == 'agent:cooling'
        assert set(run['servers']) <= set(HANDOVER_READS)                                     # 교대 단계는 맡은 에이전트가 바뀌어도 정해진 조회 도구만
    finally:
        world.api('DELETE', '/api/agent-assignments/shift_handover/task:draft')


def test_없는_에이전트와_스킬은_404(world):
    assert world.api('GET', '/api/agents/agent:none')[0] == 404
    assert world.api('GET', '/api/skills/no-such-skill')[0] == 404
