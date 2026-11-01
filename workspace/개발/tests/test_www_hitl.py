"""지식 관리 화면(it/portal/www/hitl.js)의 업무 데이터 연결 이력 — 되돌리기 결과 문장이 학생에게 남는다.

실제 index.html · hitl.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 응답(연결 이력 · 되돌리기)만 이 시험이 준다
(꼴은 procsvc GET /api/kg/ingests · DELETE /api/kg/ingests/{batch})."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served

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
            page.locator("button[data-tab='knowledge']").first.click()
            page.wait_for_selector(f"#ddlHistory [data-clear='{BATCH}']", timeout=15000)
            page.once('dialog', lambda d: d.accept())
            page.locator(f"#ddlHistory [data-clear='{BATCH}']").click()
            page.wait_for_function("document.querySelectorAll('#ddlHistory [data-clear]').length === 0", timeout=15000)
            page.wait_for_timeout(300)
            assert page.inner_text('#ddlHistoryMsg') == '되돌리기 완료: 20 삭제 · 0 복원 · 1 유지'
            b.close()
    finally:
        served.close()


import pytest


@pytest.mark.parametrize('cache, said', [
    ({'key': 'k', 'reused': False, 'validated': True, 'origin': {'by': 'instructor'}}, '강사가 검토 · 서명한 추출본입니다(제공 문서라 AI를 부르지 않았습니다)'),
    (None, '추출 제안입니다. 원문을 대조하고 검토 후 적재하세요.'),
], ids=['제공 문서(강사 서명본)', '학생 문서(AI 추출)'])
def test_추출_미리보기는_제공_문서면_강사_서명본이라_AI를_부르지_않았다고_말한다(cache, said):
    """J4 D2(2026-11-01): 제공 문서 추출은 키가 있어도 늘 강사 서명본을 내고 AI 를 부르지 않는데(manual_api · manual_approved_cache), 검토
    화면은 「추출 제안입니다」라고만 해 학생이 AI 추출로 믿었다. 미리보기 응답 꼴은 procsvc manual_cache.result 의 preview(extraction.cache)."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    preview = {'source_id': 'manual:s1', 'document_id': 'HM-8', 'filename': 'HM-8_cooler-fan-manual.md', 'chars': 10, 'status': 'READY',
               'sections': [], 'procedures': [], 'warnings': [], 'knowledge': {}, 'validation': None,
               'extraction': {'cache': cache} if cache else {'method': 'agent'}}

    def answer(route):
        url = route.request.url.split('?')[0]
        if url.endswith('/api/kg/manuals/preview'):
            return route.fulfill(json=preview)
        if url.endswith('/extractions'):                                   # 추출 이력(manual_api extraction_history 꼴)
            return route.fulfill(json={'items': [], 'offset': 0, 'limit': 50, 'next_offset': None})
        if url.endswith('/api/kg/manuals/sources') or url.endswith('/api/kg/manuals'):
            return route.fulfill(json={'items': []})
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            page.locator("button[data-tab='knowledge']").first.click()
            page.set_input_files('#manualFile', files=[{'name': 'HM-8_cooler-fan-manual.md', 'mimeType': 'text/markdown', 'buffer': '# HM-8'.encode()}])
            page.locator('#manualPreview').click()
            page.wait_for_selector('#manualAgentStatus', state='attached', timeout=15000)
            text = page.locator('#manualAgentStatus').inner_text()
            b.close()
    finally:
        served.close()
    assert said in text, text
