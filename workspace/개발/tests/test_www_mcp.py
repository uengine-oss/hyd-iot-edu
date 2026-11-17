"""도구 연결 화면(it/portal/www/mcp.js)의 서버 카드 — 「에이전트 도구로 고를 수 있음」(마지막 연결 검사 통과 기록)과 지금 다시 잰 상태가 갈릴 때.

실제 index.html · mcp.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 응답(서버 목록 · 그 서버 도구 목록)만 이 시험이 준다
(꼴은 procsvc GET /api/mcp/servers · GET /api/mcp/servers/{name}/tools)."""
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

SERVER = {'name': 'tool-wear', 'transport': 'streamable_http', 'url': 'http://host.docker.internal:8301/mcp', 'headers': {},
          'config_error': None, 'agents': [{'id': 'agent:u-1', 'name': '공구 마모 판단 에이전트'}], 'tasks': [], 'origin': 'user',
          'origin_text': '내가 등록', 'mine': True, 'editable': True, 'selectable': True, 'reason': None, 'description': None,
          'check': {'status': 'ok', 'checked_at': '2026-11-01T09:24:23Z', 'tool_count': 1}, 'read_confirmed': [], 'secrets': []}


@pytest.mark.parametrize('tools, said', [
    ({'status': 'failed', 'error': '이름을 찾을 수 없음', 'error_kind': 'unreachable', 'tools': []},
     '지난 연결 검사는 통과했지만 지금은 연결되지 않습니다(주소 없음)'),
    ({'status': 'ok', 'tools': [{'name': 'read_tool_wear', 'read': True}]}, '에이전트 도구로 고를 수 있음'),
], ids=['지금 연결 안 됨', '지금도 연결됨'])
def test_고를_수_있는_학생_서버가_지금_연결되지_않으면_카드가_그렇다고_말한다(tools, said):
    """2026-11-01 메뉴 눈 확인(17): PBL에서 등록한 서버를 끈 뒤 카드에 「주소 없음」과 「에이전트 도구로 고를 수 있음」이 나란히 떠 지금 붙여도
    되는 것처럼 읽혔다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        url = route.request.url.split('?')[0]
        if url.endswith('/api/mcp/servers/tool-wear/tools'):
            return route.fulfill(json=tools)
        if url.endswith('/api/mcp/servers'):
            return route.fulfill(json={'servers': [SERVER], 'list_timeout_s': 5})
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'mcp')
            card = page.locator("#mcpServers [data-name='tool-wear']")
            card.wait_for(timeout=15000)
            page.wait_for_function("!document.querySelector(\"#mcpServers [data-name='tool-wear']\").textContent.includes('연결 확인 중')",
                                   timeout=15000)
            text = card.inner_text()
            card.click()                                                  # 상세 화면도 같은 문장(카드 · 상세가 한 함수 stampGap)
            page.wait_for_function("document.querySelector('#mcpDetail') && document.querySelector('#mcpDetail').textContent.includes('tool-wear')",
                                   timeout=15000)
            detail = page.locator('#mcpDetail').inner_text()
            b.close()
    finally:
        served.close()
    if tools['status'] == 'ok':      # 고를 수 있는 것은 보통이라 목록 줄에는 도구 수만 두고(줄마다 같은 말을 되풀이하지 않는다), 그 말은 상세에 한 번 있다
        assert '도구 1개' in text and said not in text and said in detail, (text, detail)
    else:
        assert said in text and said in detail, (text, detail)
    assert tools['status'] == 'ok' or ('에이전트 도구로 고를 수 있음' not in text and '에이전트 도구로 고를 수 있음' not in detail), (text, detail)


def test_도구_서버를_지울_때_그_서버를_부르는_흐름_단계를_확인_창이_말하고_지운_뒤에도_가리키는_단계를_상세_자리에_남긴다():
    """서버 목록이 서버마다 주는 flow_steps(「승인 뒤 MCP 호출」 단계)가 지우기 확인 창에 에이전트와 함께 보이고, 쓰는 것이 있으면 force 로 보내며,
    지우기 응답의 flow_steps_still_calling_it 을 결과로 남긴다. 전에는 에이전트 단계(tasks)만 보였고, 흐름 단계만 쓰는 서버는 force=false 로 보내 409 가 났다."""
    from playwright.sync_api import sync_playwright
    step = {'definition': 'reorder', 'definition_name': '비품 재주문', 'version': '1', 'activity_id': 'Task_order', 'activity_name': '발주 넣기', 'tool': 'place_order',
            'read_check': False, 'latest': True, 'running': 2}
    server = dict(SERVER, agents=[], flow_steps=[step], tasks=[{'definition': 'reorder', 'definition_name': '비품 재주문', 'version': '1', 'activity_id': 'Task_plan',
                                                               'activity_name': '재주문안 제안', 'agent': '재주문 에이전트', 'fixed_tools': None},
                                                              {'definition': 'reorder', 'definition_name': '비품 재주문', 'version': '1', 'activity_id': 'Task_check',
                                                               'activity_name': '재고 확인', 'agent': '재주문 에이전트', 'fixed_tools': None}])
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    state, deletes = {'servers': [server]}, []

    def answer(route):
        url, method = route.request.url, route.request.method
        path = url.split('?')[0]
        if method == 'DELETE' and path.endswith('/api/mcp/servers/tool-wear'):
            deletes.append(url.split('?')[1])
            state['servers'] = []
            return route.fulfill(json={'name': 'tool-wear', 'deleted': True, 'agents_still_naming_it': [], 'flow_steps_still_calling_it': [step]})
        if path.endswith('/api/mcp/servers/tool-wear/tools'):
            return route.fulfill(json={'status': 'ok', 'tools': [{'name': 'place_order', 'read': False}]})
        if path.endswith('/api/mcp/servers'):
            return route.fulfill(json={'servers': state['servers'], 'list_timeout_s': 5})
        if path.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'mcp')
            page.locator("#mcpServers [data-name='tool-wear']").click()
            page.wait_for_selector('#mcpDetail [data-mcp-calls]', state='attached', timeout=15000)
            # 쓰는 곳은 첫 화면에 한 줄(건수)이고 접혀 있다 — 펼치면 직접 부르는 흐름 단계는 따로 한 묶음, 에이전트 단계는 흐름마다 한 줄(단계 둘이 한 줄에)
            uses = page.locator('#mcpDetail .mcp-uses')
            assert not uses.evaluate('d => d.open') and '흐름 1' in uses.locator('summary').inner_text() and '부르는 흐름 단계 1' in uses.locator('summary').inner_text()
            assert page.locator('#mcpDetail [data-mcp-calls]').is_hidden()
            uses.locator('summary').click()
            page.locator('#mcpDetail [data-mcp-calls] .row').first.wait_for(timeout=8000)      # 펼친 내용이 보일 때까지
            calls = page.inner_text('#mcpDetail [data-mcp-calls]')
            assert '비품 재주문' in calls and '발주 넣기' in calls and '도구 place_order' in calls and '진행 중 2건' in calls
            assert page.locator('#mcpDetail [data-mcp-flows] .row').count() == 1 and '재주문안 제안 · 재고 확인' in page.inner_text('#mcpDetail [data-mcp-flows]')
            page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
            page.locator('#mcpMore-trigger').click()                          # 고치기 · 지우기는 상세 머리의 「…」 안
            page.locator('#mcpDelete').click()
            said = page.inner_text('dialog.confirm-dialog')
            assert '이 서버를 쓰는 에이전트는 없습니다' in said and '「비품 재주문」의 「발주 넣기」(도구 place_order · 진행 중인 처리 건 2건)' in said
            assert '실행될 때 서버가 없다는 까닭으로 멈춥니다' in said
            page.locator("dialog.confirm-dialog button[value='ok']").click()
            page.wait_for_selector('#mcpDetail [data-mcp-removed]', timeout=8000)
            assert deletes == ['force=true&by=user%3Ame']                    # 흐름 단계만 쓰는 서버도 확인을 거쳤으므로 force 로 지운다
            left = page.inner_text('#mcpDetail [data-mcp-removed]')
            assert '아직 가리키는 곳이 있습니다' in left and '비품 재주문' in left and '발주 넣기' in left and '도구 place_order' in left
            b.close()
    finally:
        served.close()


def test_도구를_써_보면_받은_결과가_모양대로_첫_화면에_보이고_원문은_접혀_있다():
    """수업 한 바퀴에서 찾음: 판단 시스템의 입력 자료 도구를 써 보면 「결과를 받았습니다 · n자」와 접힌 원문 둘만 보여 학생이 결과를 읽지 못했다.
    결과의 모양(객체 안의 배열 → 표, 값 → 이름–값 줄, 값의 배열 → 목록)으로 그리는 한 규칙이라 도구 이름과 무관하다 — 여기서는 학생 서버의 도구로 본다."""
    import json
    from playwright.sync_api import sync_playwright
    doc = {'result': 'ok', 'document': [{'id': 'in:cause', 'name': '판정 원인', 'table': None, 'source': 'sys:agent'}, {'id': 'in:ce', 'name': '냉각 효율', 'table': None, 'source': 'sen:ce'}],
           'tags': ['읽기', '조회'], 'summary': {'count': 2, 'deep': {'a': {'b': 1}}}}
    tool = {'name': 'read_tool_wear', 'callable': True, 'confirmable': False, 'description': '', 'input_schema': {'type': 'object', 'properties': {}}}
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        url = route.request.url.split('?')[0]
        if url.endswith('/tools/read_tool_wear/call'):
            text = json.dumps(doc, ensure_ascii=False)
            return route.fulfill(json={'elapsed_ms': 12, 'arguments': {}, 'result': {'is_error': False, 'truncated': False, 'size_chars': len(text), 'limit_chars': 20000, 'text': text}})
        if url.endswith('/api/mcp/servers/tool-wear/tools'):
            return route.fulfill(json={'status': 'ok', 'tools': [tool]})
        if url.endswith('/api/mcp/servers'):
            return route.fulfill(json={'servers': [SERVER], 'list_timeout_s': 5})
        if url.endswith('/api/inbox/users'):
            return route.fulfill(json=[{'id': 'user:me', 'name': '담당자', 'roles': []}])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'mcp')
            page.locator("#mcpPane [data-try='read_tool_wear']").click()
            page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
            page.locator('#mcpCall').click()
            shape = page.locator('#mcpResult [data-mcp-shape]')
            shape.wait_for(timeout=8000)
            # 객체 안의 배열은 표: 줄 둘, 모든 줄에서 값이 없는 열(table)은 빠지고 그 사실을 말한다
            cells = shape.locator('table tbody tr').evaluate_all('rows => rows.map(r => [...r.children].map(td => td.textContent))')
            heads = shape.locator('table thead th').all_inner_texts()
            assert cells == [['in:cause', '판정 원인', 'sys:agent'], ['in:ce', '냉각 효율', 'sen:ce']] and len(heads) == 3, (heads, cells)
            assert '값이 없는 열 1개는 뺐습니다' in shape.inner_text()
            # 값은 이름–값 줄, 값의 배열은 목록, 셋째 깊이를 넘는 것은 한 줄 글
            assert shape.locator('dl.kv dd').first.inner_text() == 'ok' and shape.locator('ul li').all_inner_texts() == ['읽기', '조회']
            assert '{"b":1}' in shape.inner_text()
            # 보이는 결과는 접힌 원문 밖에 있고(창에서 실제로 보인다), 원문 둘은 접혀 있다
            assert shape.locator('table tbody tr').first.is_visible()
            folds = page.locator('#mcpResult details')
            assert folds.count() == 2 and not any(folds.nth(i).evaluate('d => d.open') for i in range(2))
            assert page.evaluate("!document.querySelector('#mcpResult [data-mcp-shape]').closest('details')")
            b.close()
    finally:
        served.close()
