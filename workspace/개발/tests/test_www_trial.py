"""판단 실험의 조건 판(it/portal/www/whatif.js · enterprise.js 규칙 판단) — 설비 목록을 화면이 지어내지 않고 서버에서 읽는다.

실제 index.html 을 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 서비스 응답(설비 상태 · 이상 패턴 · 판단)만 이 시험이 준다.
설비 상태 응답의 꼴은 plant-sim /api/state(units: {설비: {tags, status}}), 판단 응답의 꼴은 agent /api/agent/decide 다."""
import json

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

UNIT = {'tags': {'TS1': 48.0, 'CE': 84.0}, 'status': {'state': 'RUN', 'mode': 'REMOTE_AUTO'}}
PLANT = {'units': {'PRESS-07': UNIT, 'PRESS-08': UNIT}, 't': '2026-11-14T00:00:00Z'}      # 수업 설비 이름(HYD-0N)이 아닌 이름 — 화면에 박힌 목록이 있으면 드러난다
PATTERNS = [{'id': 'pattern:x', 'code': 'SEAL_WEAR', 'name': '씰 마모', 'failureModes': []}]


def _page(answers, sent):
    """index.html 을 띄우고, /svc/ 요청은 answers(주소 끝 → 응답 또는 (상태, 응답))로 답한다. POST 본문은 sent 에 남는다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        url = route.request.url.split('?')[0]
        if route.request.method == 'POST':
            sent.append((url, json.loads(route.request.post_data or '{}')))
        hit = next((body for tail, body in answers.items() if url.endswith(tail)), {})
        status, body = hit if isinstance(hit, tuple) else (200, hit)
        return route.fulfill(status=status, json=body)
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
    page = browser.new_page()
    page.route('**/svc/**', answer)
    page.goto(served.url + '/index.html')

    def close():
        browser.close()
        pw.stop()
        served.close()
    return page, close


def test_조건별_손익은_설비_목록을_서버의_설비_상태에서_읽고_고른_설비로_계산을_청한다():
    """해피패스 조사 9번: 화면 코드에 ['HYD-01','HYD-02','HYD-03']가 박혀 있어, 설비가 달라도 그 셋만 고를 수 있었다."""
    sent = []
    page, close = _page({'/plant-sim/api/state': PLANT, '/api/ontology/patterns': PATTERNS,
                         '/api/agent/whatif': (422, {'detail': '이 설비에는 씰 마모의 원인 지식이 없습니다'})}, sent)
    try:
        open_screen(page, 'whatif')
        page.wait_for_function("document.querySelectorAll('#wiAsset option').length > 0", timeout=8000)
        assert page.eval_on_selector_all('#wiAsset option', 'xs => xs.map(x => x.textContent)') == ['PRESS-07', 'PRESS-08']
        page.select_option('#wiAsset', 'PRESS-08')
        page.locator('#wiLoad').click()
        page.wait_for_selector("#whatifView [role='alert']", timeout=8000)
        asked = [body for url, body in sent if url.endswith('/api/agent/whatif')]
        assert asked == [{'asset': 'PRESS-08', 'pattern': 'SEAL_WEAR'}]
        # 서버가 거절하면 빈 결과가 아니라 서버의 까닭이 결과 자리에 남는다
        assert '이 설비에는 씰 마모의 원인 지식이 없습니다' in page.inner_text("#whatifView [role='alert']")
    finally:
        close()


def test_조건별_손익은_설비_목록을_읽지_못하면_빈_목록으로_두지_않고_까닭과_다시_시도를_보인다():
    sent = []
    page, close = _page({'/plant-sim/api/state': (503, {'detail': '설비 시뮬레이터가 응답하지 않습니다'}), '/api/ontology/patterns': PATTERNS}, sent)
    try:
        open_screen(page, 'whatif')
        page.wait_for_selector("#whatifView [role='alert']", timeout=15000)
        assert '설비 목록을 읽지 못했습니다' in page.inner_text("#whatifView [role='alert']")
        assert page.locator('#wiLoad').is_disabled() and page.locator("#whatifView [data-retry]").count() == 1
    finally:
        close()


def test_규칙_판단은_설비_목록을_서버에서_읽고_긴_첫_문장은_쌍점_앞까지만_결론으로_올린다():
    """규칙 판단의 설비 고르기도 화면에 박혀 있었다. 결론은 서버 설명의 첫 문장인데, 후보마다의 제외 사유가 한 문장에 줄줄이 달리면
    (가능한 조치가 없을 때) 큰 글 한 줄이 문단이 됐다 — 쌍점 앞까지만 결론에 두고 나머지는 그 아래로 내린다."""
    why = '; '.join(f'SOP-X-{n} 조치 {n} (현재 조치 예측을 확인할 수 없습니다: 지금 바뀌는 중인 외란이 있어 입력을 고정한 예측이 맞지 않습니다)' for n in range(1, 4))
    decided = {'id': 'EVAL-1', 'created': '2026-11-14T00:00:00Z', 'asset': 'PRESS-08', 'status': 'NO_FEASIBLE_OPTION', 'steps': [], 'causes': [], 'provenance': [],
               'scenario': {'name': '씰 마모 조치 판단'}, 'facts': {},
               'result': {'options': [], 'recommended': None, 'trace': [], 'explanation': f'씰 마모 — 후보 3장 모두 규정상 제외됐다: {why}.'}}
    sent = []
    page, close = _page({'/plant-sim/api/state': PLANT, '/api/ontology/patterns': PATTERNS, '/api/agent/decide': decided}, sent)
    try:
        open_screen(page, 'decision')
        page.wait_for_function("document.querySelectorAll('#decAsset option').length > 0 && document.querySelectorAll('#decPattern option').length > 0", timeout=8000)
        assert page.eval_on_selector_all('#decAsset option', 'xs => xs.map(x => x.value)') == ['PRESS-07', 'PRESS-08']
        page.select_option('#decAsset', 'PRESS-08')
        page.locator('#decRun').click()
        page.wait_for_selector('#decResult .panel-head h2', timeout=8000)
        assert [body for url, body in sent if url.endswith('/api/agent/decide')] == [{'asset': 'PRESS-08', 'pattern': 'SEAL_WEAR', 'facts': {}}]
        assert page.inner_text('#decResult .panel-head h2') == '씰 마모 — 후보 3장 모두 규정상 제외됐다.'
        assert 'SOP-X-3 조치 3' in page.inner_text('#decResult .result-sub')      # 나머지는 버리지 않고 결론 아래에 있다
    finally:
        close()
