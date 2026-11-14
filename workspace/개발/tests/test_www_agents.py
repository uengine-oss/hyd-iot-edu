"""AI 에이전트 화면(it/portal/www/agents.js)이 지우기 · 기준으로 되돌리기 · 단계 배정 요청에 「누가」(이 PC의 담당자 id)를 싣는다.

서버는 이 세 요청에서 「누가」가 비면 400 으로 거절한다(agent_authoring_api — inbox.actor_or_400: 열린 단계의 담당이 바뀐 기록에 남는 값이다).
화면이 싣지 않으면 학생에게는 세 단추가 모두 「담당자 정보 없이 온 요청…」으로만 끝난다.

실제 index.html · agents.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 는 이 시험이 주는 작은 서버다: 읽기 응답의 꼴은
procsvc 의 것(GET /api/agents · /api/agents/{id} · /api/skills · /api/agent-assignments)이고, 쓰기 요청의 「누가」는 실제 검사 함수
(procsvc.inbox.actor_or_400)가 받는다 — 받은 값은 seen 에 남는다."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served
from procsvc.inbox import actor_or_400

ME = 'user:me'
MINE = {'id': 'agent:u-1a2b', 'name': '내 점검 에이전트', 'kind': 'agent', 'origin': 'user', 'editable': True, 'role': 'AI 에이전트',
        'goal': '점검 기록을 읽고 다음 점검을 정한다', 'model': None, 'tools': ['neo4j'], 'skills': [], 'work_rules': '', 'work_rules_detail': None, 'steps': []}
DETAIL = dict(MINE, tools=[{'name': 'neo4j', 'registered': True, 'description': ''}], persona='')
BOARD = {'steps': [{'definition_id': 'my_flow', 'activity_id': 'T_judge', 'name': '판단', 'default_agents': ['sys:agent'], 'definition_name': '내 흐름',
                    'version': '1', 'default_names': ['인공지능 에이전트'], 'assigned': None}],
         'roles': [], 'people': [{'id': ME, 'name': '담당자'}], 'orphans': [], 'agents': [{'id': MINE['id'], 'name': MINE['name'], 'origin': 'user'}]}


def _process(seen):
    api = FastAPI()

    @api.get('/api/inbox/users')
    async def users():
        return [{'id': ME, 'name': '담당자', 'roles': []}]

    @api.get('/api/agents')
    async def agents():
        return [] if 'deleted' in seen else [MINE]

    @api.get('/api/agents/{agent_id}')
    async def agent(agent_id: str):
        return DETAIL

    @api.get('/api/skills')
    async def skills():
        return []

    @api.get('/api/agent-assignments')
    async def board():
        return BOARD

    @api.put('/api/agent-assignments')
    async def assign(body: dict):
        seen['assigned'] = actor_or_400(body.get('by'))
        return {'definition_id': body['definition_id'], 'activity_id': body['activity_id'], 'agent_id': body['agent_id']}

    @api.delete('/api/agents/{agent_id}')
    async def delete(agent_id: str, by: str | None = None):
        seen['deleted'] = actor_or_400(by)
        return {'id': agent_id, 'deleted': True, 'returned_tasks': []}

    @api.post('/api/agents/reset')
    async def reset(body: dict | None = None):
        seen['reset'] = actor_or_400((body or {}).get('by'))
        return {'agents': 1, 'skills': 0, 'attachments': 0, 'assignments': 1, 'roles': 0, 'returned_tasks': []}
    app = FastAPI()
    app.mount('/svc/process', api)
    app.mount('/', StaticFiles(directory=WWW, html=True))
    return Served(app)


def _through(route):
    """이 시험의 process 가 답하는 길만 실제 서버로 보내고, 나머지 서비스 응답은 빈 값."""
    url = route.request.url.split('?')[0]
    known = ('/api/inbox/users', '/api/agents', '/api/skills', '/api/agent-assignments', '/api/agents/reset')
    if '/svc/process/' in url and (url.endswith(known) or '/api/agents/' in url):
        return route.continue_()
    return route.fulfill(json={})


def _sent(page, seen, key):
    """화면이 보낸 그 요청을 서버가 받아 준 값(「누가」). 서버가 400 으로 거절했으면 seen 에 남지 않는다 — 알림 창의 모양에 기대지 않고 서버 쪽에서 본다."""
    for _ in range(80):
        if key in seen:
            return seen[key]
        page.wait_for_timeout(100)
    raise AssertionError(f'{key} 요청을 서버가 받아 주지 않았다(「누가」 없이 왔거나 요청이 가지 않았다): {seen}')


def test_단계_배정_지우기_되돌리기_요청은_담당자_id_를_싣고_서버가_받아_준다():
    from playwright.sync_api import sync_playwright
    seen = {}
    served = _process(seen)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', _through)
            page.goto(served.url + '/index.html')
            page.wait_for_function('typeof selectTab === "function"')
            page.evaluate('selectTab("agents")')
            page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
            page.locator('[data-del-agent]').wait_for(timeout=8000)

            page.locator("[data-ag-tab='assign']").click()                          # 단계 배정
            page.locator("select[data-map='my_flow|T_judge']").select_option(MINE['id'])
            assert _sent(page, seen, 'assigned') == ME

            page.locator('[data-ag-reset]').click()                                 # 기준으로 되돌리기
            page.locator("dialog.confirm-dialog button[value='ok']").click()
            assert _sent(page, seen, 'reset') == ME
            page.wait_for_function('() => !document.querySelector("dialog.confirm-dialog[open]")')

            page.locator("[data-ag-tab='agents']").click()                          # 지우기
            page.locator('[data-del-agent]').click()
            page.locator("dialog.confirm-dialog button[value='ok']").click()
            assert _sent(page, seen, 'deleted') == ME
            page.wait_for_function("document.body.textContent.includes('AI 에이전트가 없습니다')", timeout=8000)      # 지운 뒤 목록을 다시 읽었다
            b.close()
    finally:
        served.close()
