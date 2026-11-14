"""문서 등록 화면(it/portal/www/hitl.js)의 업무 DB 표 정의 연결 이력 — 되돌리기 결과 문장이 학생에게 남는다.

실제 index.html · hitl.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 응답(연결 이력 · 되돌리기)만 이 시험이 준다
(꼴은 procsvc GET /api/kg/ingests · DELETE /api/kg/ingests/{batch})."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

BATCH = 'ddl-legacy-plant-db-1'


def test_연결_배치를_되돌리면_이력을_다시_그린_뒤에도_되돌리기_완료_문장이_남는다():
    """한바퀴3 고침 4: 되돌리기 성공 문장을 쓴 직후 이력을 다시 그리며(loadIngests 가 알림 줄까지 새로 만듦) 문장이 지워져, 학생은 결과를
    볼 수 없었다(06 실습 · 통합 40행)."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    rows = [{'batch': BATCH, 'label': 'InputData', 'nodes': 20, 'source': 'legacy-plant-db.sql'}]

    def answer(route):
        url, method = route.request.url.split('?')[0], route.request.method
        if url.endswith('/api/kg/ingests/' + BATCH) and method == 'DELETE':
            rows.clear()
            return route.fulfill(json={'deleted': 20, 'restored': 0, 'retained': 1})
        if url.endswith('/api/kg/ingests'):
            return route.fulfill(json=list(rows))
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'knowledge')
            page.click("#docKinds [data-doc-kind='ddl']")      # 올릴 것: 업무 DB 표 정의(연결 이력은 그쪽 판 아래에 있다)
            page.wait_for_selector(f"#ddlHistory [data-clear='{BATCH}']", timeout=15000)
            page.locator(f"#ddlHistory [data-clear='{BATCH}']").click()
            page.locator("dialog.confirm-dialog button[value='ok']").click()      # 포털 확인 대화상자(UI.confirm)
            page.wait_for_function("document.querySelectorAll('#ddlHistory [data-clear]').length === 0", timeout=15000)
            page.wait_for_timeout(300)
            assert page.inner_text('#ddlHistoryMsg') == '되돌렸습니다. 지운 항목 20개 · 되살린 항목 0개 · 남긴 항목 1개'
            b.close()
    finally:
        served.close()
