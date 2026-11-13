"""도구 연결 화면의 API(procsvc/mcp_api.py) — 학생 PC 구성(world: 실제 process · 실제 도구 서버들)에서 포털과 같은 경로로 부른다.

도구 지도의 「이 서버로 도는 단계 · 담당」은 워커가 실제로 도는 규칙(배정 반영 + 에이전트 도구 ∩ 단계 선언, 교대 · 질문은 정해진 조회 도구)으로 계산한다.
"""
import pytest

from procsvc import mcp_check

TENANT = 'hyd'
ME = 'user:me'                     # 이 PC의 담당자 — 포털은 써 보기에 늘 이 id 를 싣는다


def servers(world):
    status, body = world.api('GET', '/api/mcp/servers')
    assert status == 200, body
    return {s['name']: s for s in body['servers']}


def test_도구_지도의_단계는_실제_담당_에이전트의_도구로만_센다(world):
    names = {u['id']: u['username'] for u in world.rt.repo.list_users(None, TENANT)}
    view = servers(world)
    purchase = {(t['definition'], t['activity_id']) for t in view['enterprise-purchase']['tasks']}
    maint = {(t['definition'], t['activity_id']): t['agent'] for t in view['enterprise-maint']['tasks']}
    assert not any(d in ('c3_cooling', 'c3_pm') for d, _ in purchase)                 # 옛 판: 모든 서버가 모든 에이전트 단계를 맡았다
    assert maint.get(('c3_pm', 'T_agent')) == names['agent:pm-plan']
    assert all(t['agent'] != '인공지능 에이전트' for t in view['neo4j']['tasks'] if t['definition'].startswith('c3_'))


def test_교대_초안_단계는_정해진_조회_도구가_있는_서버로만_돈다(world):
    view = servers(world)
    handover = [t for s in view.values() for t in s['tasks'] if t['definition'] == 'shift_handover']
    assert handover and all(t['fixed_tools'] for t in handover)
    assert not any(t['definition'] == 'shift_handover' for t in view['enterprise-maint']['tasks'])


def test_기준_서버는_검사_없이도_에이전트에_붙일_수_있다고_보인다(world):
    view = servers(world)
    assert all(view[n]['selectable'] and view[n]['transport'] == 'streamable_http' for n in ('neo4j', 'enterprise', 'hyd-dmn'))


def test_지식_그래프_도구_목록은_목록_시간_한도_안에_온다(world):
    status, body = world.api('GET', '/api/mcp/servers/neo4j/tools')
    assert status == 200 and body['status'] == 'ok', body                              # H-9: 옛 판 명령형 서버는 매번 파이썬을 띄워 4초를 넘겼다
    assert {t['name'] for t in body['tools']} >= {'read_neo4j_cypher', 'get_neo4j_schema'}
    assert body['elapsed_ms'] < body['timeout_s'] * 1000


@pytest.mark.parametrize('tool, status', [('inputs', 200), ('submit_decision', 403), ('nope', 404)], ids=['읽기 도구', '쓰기 도구', '없는 도구'])
def test_써_보기는_읽기_도구만_부른다(world, tool, status):
    got, body = world.api('POST', f'/api/mcp/servers/hyd-dmn/tools/{tool}/call', {'arguments': {}, 'by': ME})
    assert got == status, body
    if status == 403:
        assert body['detail'] == '서버가 이 도구를 쓰기 도구로 표시했습니다 — 포털 써 보기에서는 쓰기 도구를 부르지 않습니다'


@pytest.mark.parametrize('body', [None, {'arguments': {}}, {'arguments': {}, 'by': ' '}], ids=['본문 없음', '칸 없음', '빈 칸'])
def test_써_보기는_담당자_없이_오면_도구를_부르기_전에_400_으로_거절한다(world, body):
    """없는 도구(nope)는 서버에 물어본 뒤에야 404 가 난다 — 그 전에 400 이면 서버를 부르기 전에 거절한 것이다. 써 보기 기록도 남지 않는다."""
    tried = [e for e in world.main.audit_log if e['event'] == 'MCP_TOOL_TRIED']
    got, out = world.api('POST', '/api/mcp/servers/hyd-dmn/tools/nope/call', body)
    assert got == 400 and '담당자 정보 없이 온 요청' in out['detail'], out
    assert [e for e in world.main.audit_log if e['event'] == 'MCP_TOOL_TRIED'] == tried


def test_포털_연결_자리가_다_차면_목록_요청은_503과_까닭을_받는다(world):
    held = [mcp_check.portal_slot(0.1) for _ in range(mcp_check.PORTAL_SLOTS)]
    for slot in held:
        slot.__enter__()
    try:
        status, body = world.api('GET', '/api/mcp/servers/hyd-dmn/tools')
    finally:
        for slot in held:
            slot.__exit__(None, None, None)
    assert status == 503 and '진행 중입니다' in body['detail']


@pytest.mark.parametrize('limit', [0, 201], ids=['0', '201'])
def test_호출_기록_목록_수는_범위_밖이면_거절한다(world, limit):
    status, _ = world.api('GET', f'/api/mcp/calls?limit={limit}')
    assert status == 400
