"""흐름 화면(it/portal/www/flows.js) — 다른 화면에서 바뀐 카탈로그(에이전트)가 다시 열 때 보인다.

실제 index.html · flows.js 를 실제 브라우저(Playwright Chromium)로 열고, 화면의 process 요청(/svc/process/…)은 실제 process 앱(world —
같은 라우트 · 같은 수업 경계)으로 넘긴다. 다른 서비스 요청은 빈 응답이다 — 이 판정과 무관하다."""
import json
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen
from procsvc.course_policy import HANDOVER

FLOW = 'ShiftHandover'
ME = 'user:kim-op'


def test_다른_화면에서_만든_에이전트가_흐름_화면을_다시_열면_단계의_에이전트_고르기에_나온다(world):
    """한바퀴3 고침: 흐름 화면은 카탈로그를 처음 열 때 한 번만 읽어(셸 show 없음), 실라버스 118행에서 만든 인수인계 에이전트를 119행의
    단계 에이전트 고르기에서 고를 수 없었다(새로 고침 전까지)."""
    from playwright.sync_api import sync_playwright
    status, out = world.api('DELETE', f'/api/flows/{FLOW}?by={ME}')
    assert status in (200, 404), out
    status, view = world.api('POST', '/api/flows/import', {'xml': HANDOVER['xml'], 'file_name': 'shift-handover.bpmn'})
    assert status == 200, view
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        parts = urlsplit(route.request.url)
        if not parts.path.startswith('/svc/process/'):
            return route.fulfill(json={})
        if parts.path.endswith('/stream'):              # 알림 스트림(SSE)은 끝나지 않는 응답이라 넘기지 않는다 — 이 판정과 무관
            return route.abort()
        path = parts.path[len('/svc/process'):] + (f'?{parts.query}' if parts.query else '')
        body = json.loads(route.request.post_data) if route.request.post_data else None
        status, out = world.api(route.request.method, path, body)
        return route.fulfill(status=status, json=out)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'flows')
            page.locator(f"#flowList [data-open='{FLOW}']").first.click()
            pick = page.locator("#flowEditor select[data-agent='task_draft']")
            pick.wait_for(timeout=15000)
            status, agent = world.api('POST', '/api/agents', {'name': '새 인수인계 에이전트', 'goal': '교대 인계안을 쓴다', 'tools': ['neo4j']})
            assert status in (200, 201), agent
            assert pick.locator(f"option[value='{agent['id']}']").count() == 0, '아직 다시 열지 않았다'
            open_screen(page, 'agents')          # 에이전트 화면에 갔다가
            open_screen(page, 'flows')           # 흐름 화면으로 돌아온다
            page.wait_for_function(f"!!document.querySelector(\"#flowEditor select[data-agent='task_draft'] option[value='{agent['id']}']\")",
                                   timeout=15000)
            b.close()
    finally:
        served.close()


def test_수업_단계의_제공_교대_매핑은_칸_줄_더하기_빼기도_잠겨_있다(world):
    """한바퀴3 고침: 잠금이 입력 칸만 덮어, 칸 줄 더하기 단추로 시작 입력 줄을 더할 수 있었고(새 줄은 잠기지 않음) 등록에서야 거절됐다."""
    from playwright.sync_api import sync_playwright
    status, out = world.api('DELETE', f'/api/flows/{FLOW}?by={ME}')
    assert status in (200, 404), out
    status, view = world.api('POST', '/api/flows/import', {'xml': HANDOVER['xml'], 'file_name': 'shift-handover.bpmn'})
    assert status == 200, view
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        parts = urlsplit(route.request.url)
        if not parts.path.startswith('/svc/process/') or parts.path.endswith('/stream'):
            return route.fulfill(json={}) if not parts.path.startswith('/svc/process/') else route.abort()
        path = parts.path[len('/svc/process'):] + (f'?{parts.query}' if parts.query else '')
        status, out = world.api(route.request.method, path, json.loads(route.request.post_data) if route.request.post_data else None)
        return route.fulfill(status=status, json=out)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'flows')
            page.locator(f"#flowList [data-open='{FLOW}']").first.click()
            page.locator("#flowEditor select[data-agent='task_draft']").wait_for(timeout=15000)
            adds = page.locator("#flowEditor section button[data-add], #flowEditor section button[data-del]")
            assert adds.count() > 0 and all(adds.nth(i).is_disabled() for i in range(adds.count()))
            assert page.locator("#flowEditor select[data-agent='task_draft']").is_enabled() and page.locator('#flowEditor #flowCheck').is_enabled()
            b.close()
    finally:
        served.close()
