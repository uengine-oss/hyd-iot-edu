"""데이터 원천 화면(it/portal/www/fabric.js).

- 원천을 읽는 중과 못 읽은 것을 구별하는지: node 에서 실제 화면 파일을 싣는다.
- 보기 탭의 차례 · 상태 한 줄 · 「원천과 표」에서 고른 줄이 다시 그려도 남는지: 실제 index.html 을 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의
  process 응답(원천 · 연결 · 표의 열 · 최신 행)만 이 시험이 준다(꼴은 procsvc/fabric_api.py)."""
import pytest

from www_node import run

FILES = ['ui.js', 'plainWords.js', 'fabric.js']
EL = "const el = { innerHTML: '', addEventListener: () => {}, querySelector: () => null };"      # 화면이 다시 그릴 때 표 목록의 스크롤 자리를 찾는다 — 이 대역에는 목록이 없다


# 서버 요청(app.js getJ — 브라우저 밖에서는 실리지 않는다)만 시스템 밖 대역으로 둔다. 화면 코드(fabric.js)는 실제 파일 그대로다.
@pytest.mark.parametrize('request_fn, expect_fail', [
    ('() => new Promise(() => {})', False),                                # 응답 전: 읽는 중
    ("() => Promise.reject(new Error('연결 거부'))", True),                 # 실제로 못 읽음: 읽기 실패와 그 까닭
])
def test_원천은_응답_전에는_읽는_중이고_못_읽었을_때만_읽기_실패와_까닭을_보인다(request_fn, expect_fail):
    """1회차 04 촬영 검토(2026-11-03): 화면을 열 때마다 응답 전 0.1초 동안 실패 표시가 보였다. 숫자 카드를 걷은 뒤에도(처음 보이는 보기 = 원천과 표)
    응답 전에는 실패를 말하지 않고, 실제로 못 읽었을 때만 「읽지 못했습니다」와 서버의 까닭 · [다시 시도]가 나온다."""
    html = run(FILES, EL + "hydFabric.mount(el); for (let i = 0; i < 50; i++) await Promise.resolve(); out(el.innerHTML)",
               prelude=f"globalThis.API = {{ process: '' }}; globalThis.getJ = {request_fn};")
    assert ('원천 상태를 읽지 못했습니다' in html) == expect_fail, html[:400]
    assert ('연결 거부' in html) == expect_fail and ('data-retry' in html) == expect_fail
    assert '원천과 표' in html


SOURCES = [{'id': 'hyd-enterprise', 'label': '업무 DB', 'ok': True, 'read_only': True, 'engine': 'PostgreSQL', 'user': 'reader', 'schema': 'ent',
            'tables': [{'name': 'assets'}, {'name': 'parts'}, {'name': 'suppliers'}]},
           {'id': 'hyd-timeseries', 'label': '시계열 DB', 'ok': True, 'read_only': True, 'engine': 'TimescaleDB', 'user': 'reader', 'schema': 'public', 'tables': [{'name': 'readings'}]}]
LINKS = {'graph': {'ok': True}, 'classes': [{'klass': 'Asset', 'label': '설비', 'key': 'code', 'source': 'hyd-enterprise', 'source_label': '업무 DB', 'table': 'assets', 'column': 'code',
                                             'state': 'OK', 'matched': [{'key': 'HYD-01'}], 'unmatched': []}],
         'inputs': [{'name': '부품 단가', 'state': 'UNBOUND', 'source': 'sys:erp'}]}


def test_처음_보이는_보기는_원천과_표이고_숫자_카드_없이_한_줄로_상태를_말하며_고른_줄은_다시_그려도_남는다():
    """2026-11-16: 위의 숫자 카드 둘이 탭 이름 · 표와 같은 수를 겹쳐 보였고, 처음 보이는 보기가 빈 조건 칸이었다. 「원천과 표」에서 고른 줄이 다시 그릴 때
    남는지는 아무도 화면에서 보지 못했다(기록 「작업자가 보지 못한 화면 상태」)."""
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from playwright.sync_api import sync_playwright

    from conftest import WWW, Served, open_screen
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        path = route.request.url.split('?')[0]
        if path.endswith('/api/fabric/sources'):
            return route.fulfill(json=SOURCES)
        if path.endswith('/api/fabric/links'):
            return route.fulfill(json=LINKS)
        if path.endswith('/api/fabric/queries'):
            return route.fulfill(json=[])
        if path.endswith('/tables'):
            return route.fulfill(json={'tables': [{'name': n, 'comment': '', 'columns': [{'name': 'code', 'type': 'text', 'pk': True, 'fk': '', 'comment': '식별 번호'}]} for n in ('assets', 'parts', 'suppliers')]})
        if path.endswith('/sample'):
            return route.fulfill(json={'columns': ['code'], 'rows': [['P-1']], 'row_count': 1, 'statement': 'select code from parts limit 5'})
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'fabric')
            page.wait_for_selector('#fabricView [data-fab-table]', timeout=15000)
            tabs = page.locator('#fabricView [role=tab]')
            assert [t.split('\n')[0] for t in tabs.all_inner_texts()] == ['원천과 표', '두 DB 묶어 보기', '지식 지도 ↔ 표 · 열']
            assert tabs.nth(0).get_attribute('aria-selected') == 'true'
            # 숫자 카드가 없다 — 상태는 탭 안의 한 줄이고, 탭 이름 뒤 건수와 같은 수를 큰 숫자로 또 보이지 않는다
            assert page.locator('#fabricView .stat').count() == 0
            # 상태 한 줄은 원천의 수와 그 이름을 함께 말한다 — 이름은 아래 목록의 묶음 머리와 같다(대역 2026-11-16: 「원천 3개」인데 첫 원천의 표가 한 화면을 채워 「하나뿐」으로 읽혔다)
            line, heads = page.inner_text('#fabricView .fab-line'), page.evaluate("[...document.querySelectorAll('#fabricView .fab-tables .rows-group')].map(g => g.firstChild.textContent)")
            assert heads == [x['label'] for x in SOURCES] and f'원천 {len(heads)}개({" · ".join(heads)})' in line and '모두 연결' in line and '읽기 전용' in line, (line, heads)
            current = lambda: page.locator("#fabricView [data-fab-table][aria-current='true']").all_inner_texts()
            assert current() == [] and '표를 고르세요' in page.inner_text('#fabricView .panel')
            page.click("#fabricView [data-fab-table='hyd-enterprise|parts']")
            page.wait_for_function("document.querySelector('#fabricView .panel')?.textContent.includes('P-1')", timeout=15000)      # 열 · 최신 행이 온 뒤(그사이 두 번 다시 그린다)
            assert current() == ['parts'] and page.inner_text('#fabricView .pane-title h2') == 'parts'
            page.click("#fabricView [data-fab-tab='links']")
            assert '판단 입력 1개는 표 · 열이 아직 정해지지 않았습니다' in page.inner_text('#fabricView .fab-line')
            page.click("#fabricView [data-fab-tab='sources']")                     # 보기를 바꿨다 와도
            assert current() == ['parts'] and 'P-1' in page.inner_text('#fabricView .panel')
            open_screen(page, 'skills')
            open_screen(page, 'fabric')                                            # 다른 화면에 다녀와도(셸이 다시 읽는다)
            page.wait_for_function("document.querySelectorAll('#fabricView [data-fab-table]').length === 4", timeout=15000)
            assert current() == ['parts'] and page.inner_text('#fabricView .pane-title h2') == 'parts'
            b.close()
    finally:
        served.close()


def test_표와_열이_정해지지_않은_판단_입력의_문서_등록_열기는_업무_DB_표_정의_보기로_데려간다():
    """눌러 보기(2026-11-16): 「표 · 열 미연결 — 표와 열은 문서 등록의 「업무 DB 표 정의」에서 정합니다 [문서 등록 열기]」를 누르면 문서 등록의 「매뉴얼」 보기가 열렸다 —
    말한 자리와 데려간 자리가 달랐다. 누른 뒤 보이는 보기가 그 줄이 꺽쇠로 말한 이름의 보기여야 한다."""
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from playwright.sync_api import sync_playwright

    from conftest import WWW, Served, open_screen
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        path = route.request.url.split('?')[0]
        if path.endswith('/api/fabric/sources'):
            return route.fulfill(json=SOURCES)
        if path.endswith('/api/fabric/links'):
            return route.fulfill(json=LINKS)
        if path.endswith('/api/fabric/queries') or path.endswith('/api/kg/manuals') or path.endswith('/api/kg/skills') or path.endswith('/api/kg/ingests'):
            return route.fulfill(json=[])
        if path.endswith('/api/kg/manuals/sources'):
            return route.fulfill(json={'items': [], 'offset': 0, 'limit': 50, 'total': 0, 'next_offset': None})
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            open_screen(page, 'fabric')
            page.wait_for_selector('#fabricView [role=tab]', timeout=15000)
            page.locator('#fabricView [role=tab]').nth(2).click()
            go = page.locator('#fabricView button', has_text='문서 등록 열기').first
            go.wait_for(timeout=8000)
            line = go.evaluate("b => b.parentElement.innerText")
            named = __import__('re').findall(r'「([^」]+)」', line)
            assert named, line
            go.click()
            page.wait_for_selector('#view-knowledge.active', timeout=8000)
            picked = page.locator('#docKinds [role=tab][aria-selected=true]').inner_text().strip()
            panes = page.evaluate("[...document.querySelectorAll('#view-knowledge [data-doc-pane]')].filter(p => !p.hidden).map(p => p.dataset.docPane)")
            assert picked == named[0] and panes == ['ddl'], (picked, named, panes)
            b.close()
    finally:
        served.close()
