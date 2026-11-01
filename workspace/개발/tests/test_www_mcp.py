"""도구 연결 화면(it/portal/www/mcp.js)의 서버 카드 — 「에이전트 도구로 고를 수 있음」(마지막 연결 검사 통과 기록)과 지금 다시 잰 상태가 갈릴 때.

실제 index.html · mcp.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 응답(서버 목록 · 그 서버 도구 목록)만 이 시험이 준다
(꼴은 procsvc GET /api/mcp/servers · GET /api/mcp/servers/{name}/tools)."""
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served

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
            page.locator("button[data-tab='mcp']").first.click()
            card = page.locator("#mcpServers [data-name='tool-wear']")
            card.wait_for(timeout=15000)
            page.wait_for_function("!document.querySelector(\"#mcpServers [data-name='tool-wear']\").textContent.includes('연결 확인 중')",
                                   timeout=15000)
            text = card.inner_text()
            b.close()
    finally:
        served.close()
    assert said in text, text
    assert tools['status'] == 'ok' or '에이전트 도구로 고를 수 있음' not in text, text
