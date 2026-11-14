"""포털의 유압 설비 · 시스템 구성 화면(it/portal/www/app.js) — 실제 포털 파일을 이 PC 포트에 띄우고 실제 브라우저(Playwright Chromium)로 연다.
서비스(/svc/…)는 띄우지 않고 그 응답만 이 시험이 정한다(시스템 밖의 것) — 화면 코드는 고치지 않은 그대로 돈다.
 - 결함 주입 뒤의 과정(hydLive.follow)은 사실이 실제로 올 때만 다음 줄로 넘어간다(시간으로 넘기지 않는다). 다른 경보의 사건으로는 넘어가지 않는다.
 - 구조 그림은 부품 표(layers.js)의 부품을 모두 놓고, 응답 없는 부품을 그 이름으로 말하며, 선택 도구는 응답 없음으로 세지 않는다.
 - 추이의 기준선은 감지기의 조건식에서 읽는다(태그와 숫자를 바로 견주는 항만)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served


@pytest.fixture(scope='module')
def served():
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    s = Served(app)
    yield s
    s.close()


@pytest.fixture(scope='module')
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def unit(asset, ts1=48.0, health=1.0, faults=()):
    return {'tags': {'TS1': ts1, 'TS3': 39.0, 'CE': 84.0, 'CP': 8.1, 'PS1': 182.0, 'FS1': 9.0, 'VS1': 0.58, 'EPS1': 2.9, 'FanSpeedSP': 60.0, 'LoadSP': 90.0},
            'status': {'asset': asset, 'mode': 'REMOTE_AUTO', 'state': 'RUN', 'cooler_health': health, 'pump': 'A', 'cmdId': None, 'result': None, 'reason': None, 'trip_text': '–'},
            'faults': list(faults), 'disturbances': {'cooler_health': health, 'leak': 0.0, 'bearing_wear': 0.0}}


class World:
    """시험이 정하는 서비스 응답: 설비 상태 · 감지기 상태 · 사건 목록 · 서비스 응답 여부."""
    def __init__(self):
        self.units = {a: unit(a) for a in ('HYD-01', 'HYD-02', 'HYD-03')}
        self.phase, self.alert, self.incidents, self.down, self.extra = 'IDLE', None, [], set(), {}

    def answer(self, route):
        req = route.request
        path = req.url.split('://', 1)[1].split('/', 1)[1].split('?')[0] if '/' in req.url.split('://', 1)[1] else ''
        path = '/' + path
        send = lambda body, status=200: route.fulfill(status=status, content_type='application/json', body=json.dumps(body))
        if not path.startswith('/svc/'):
            return route.fulfill(status=200, body='') if ':' in req.url.split('://', 1)[1].split('/')[0] and not req.url.startswith(self.base) else route.continue_()
        service = path.split('/')[2]
        if path.endswith('/healthz'):
            return send({'ok': True}) if service not in self.down else send({'detail': 'down'}, 503)
        if path == '/svc/plant-sim/api/state':
            return send({'time_scale': 20.0, 'sim_t': 100.0, 'units': self.units})
        if path == '/svc/detector/api/detector/state':
            pat = lambda a: {'COOLER_DEGRADATION': {'phase': self.phase if a == 'HYD-01' else 'IDLE', 'alert_id': self.alert if a == 'HYD-01' else None}}
            return send({'time_scale': 20.0, 'assets': {a: {'patterns': pat(a)} for a in self.units}})
        if path == '/svc/process/api/incidents':
            return send(self.incidents)
        if path == '/svc/process/api/scenario/status':
            return send({'scenarios': {}, 'presses': {}})
        if path == '/svc/process/api/scenario/A/degrade':
            return send({'at': '2026-01-01T00:00:00Z'})
        if path == '/svc/process/api/todolist':
            return send([])
        if path == '/svc/cmd-gateway/api/gateway/log':
            return send([])
        if path in self.extra:
            return send(self.extra[path])
        return send({'detail': 'Not Found'}, 404)


@pytest.fixture
def world(browser, served):
    w = World(); w.base = served.url
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.route('**/*', w.answer)
    w.page = page
    yield w
    page.close()


def steps(page):
    return page.eval_on_selector_all('#labFollow .lv-step', "ns => ns.map(n => [n.dataset.step, n.className.replace('lv-step ', '')])")


def wait_step(page, key, state):
    page.wait_for_function("([k, s]) => document.querySelector(`#labFollow .lv-step[data-step='${k}']`)?.classList.contains(s)", arg=[key, state], timeout=8000)


def test_결함_주입_뒤의_과정은_사실이_올_때만_다음_줄로_넘어간다(world):
    w, page = world, world.page
    page.goto(w.base + '/index.html#/scenario')
    page.wait_for_selector("#units .unit[data-asset='HYD-01'] button[data-act='degrade']")
    assert not page.is_visible('#labFollowPanel')                       # 누르기 전에는 과정 판이 없다
    page.click("#units .unit[data-asset='HYD-01'] button[data-act='degrade']")
    wait_step(page, 'inject', 'run')
    page.wait_for_timeout(3500)                                           # 사실이 없으면 시간이 지나도 넘어가지 않는다
    assert steps(page) == [['inject', 'run'], ['rise', 'wait'], ['detect', 'wait'], ['alert', 'wait'], ['case', 'wait']]
    w.units['HYD-01'] = unit('HYD-01', ts1=49.0, health=0.9, faults=['cooler_degradation'])
    wait_step(page, 'inject', 'ok'); wait_step(page, 'rise', 'run')
    page.wait_for_timeout(2500)
    assert steps(page)[1:] == [['rise', 'run'], ['detect', 'wait'], ['alert', 'wait'], ['case', 'wait']]      # 유온이 기준 아래면 그대로
    w.units['HYD-01'] = unit('HYD-01', ts1=56.2, health=0.6, faults=['cooler_degradation'])
    wait_step(page, 'rise', 'ok'); wait_step(page, 'detect', 'run')
    w.phase = 'CANDIDATE'
    wait_step(page, 'detect', 'ok'); wait_step(page, 'alert', 'run')
    w.phase, w.alert = 'RAISED', 'ALT-new'
    wait_step(page, 'alert', 'ok'); wait_step(page, 'case', 'run')
    # 다른 경보로 열린 사건(지난 것)으로는 「처리 건이 열렸습니다」가 되지 않는다
    w.incidents = [{'id': 'INC-old', 'asset': 'HYD-01', 'alertId': 'ALT-old', 'state': 'AWAITING_APPROVAL', 'terminal': False, 'created': '2026-01-01T00:00:00Z'}]
    page.wait_for_timeout(4500)
    assert steps(page)[-1] == ['case', 'run']
    w.incidents.append({'id': 'INC-new', 'asset': 'HYD-01', 'alertId': 'ALT-new', 'state': 'GUIDE_RECEIVED', 'terminal': False, 'created': '2026-01-01T00:01:00Z'})
    wait_step(page, 'case', 'ok')
    assert page.inner_text("#labFollow .lv-step[data-step='case'] [data-lv-go]") == '처리 건에서 보기'
    assert '56.2' in page.inner_text("#labFollow .lv-step[data-step='rise']")      # 넘어간 때의 값이 그 줄에 남는다


def test_구조_그림은_부품_표의_부품을_모두_놓고_응답_없는_부품을_이름으로_말한다(world):
    w, page = world, world.page
    w.down = {'detector'}
    page.goto(w.base + '/index.html#/home')
    page.wait_for_function("document.getElementById('sysSum').textContent.includes('응답 없음')", timeout=15000)
    table = page.evaluate("LAYERS.flatMap(L => L.comps.map(c => ({key: c.name.split(' ')[0], role: c.role, real: c.real || '', optional: !!c.optional, health: !!c.health, layer: L.name})))")
    drawn = page.eval_on_selector_all('#stack .sys-nd', 'ns => Object.fromEntries(ns.map(n => [n.dataset.key, n.dataset.st]))')
    assert sorted(drawn) == sorted(c['key'] for c in table)              # 표의 부품이 빠짐없이, 표에 없는 부품 없이
    assert drawn['detector'] == 'down' and page.inner_text('#sysSum') == '응답 없음 1 — detector'
    assert all(drawn[c['key']] == 'opt' for c in table if c['optional'])      # 선택 도구는 응답 없음으로 세지 않는다
    assert all(drawn[c['key']] == 'none' for c in table if not c['health'])   # 상태를 재지 않는 부품은 점이 없다
    assert all(drawn[c['key']] == 'ok' for c in table if c['health'] and not c['optional'] and c['key'] != 'detector')
    # 올리면 정보 띠에 그 부품의 하는 일 · 현업 대응 · 계층(모두 부품 표의 글)과 상태가 보인다
    for key in ('detector', 'cmd-gateway', 'agent-worker'):
        c = next(x for x in table if x['key'] == key)
        page.hover(f"#stack .sys-nd[data-key='{key}']")
        info = page.inner_text('#sysInfo')
        assert c['role'] in info and f"현업에서는 {c['real']}" in info and c['layer'] in info, info
        assert ('응답 없음' if key == 'detector' else '정상') in info
    # 다시 응답하면 요약이 정상으로 돌아온다
    w.down = set()
    # 머리의 요약은 응답 없는 서비스가 있을 때만 보인다 — 정상일 때의 「서비스 n/n」은 메뉴 줄 아래 한 곳에 있다
    page.wait_for_function("document.getElementById('sysSum').hidden", timeout=15000)
    assert not page.is_visible('#sysSum')


def test_추이의_기준선은_감지기_조건식에서_태그와_숫자를_바로_견주는_항만_읽는다(world):
    page = world.page
    page.goto(world.base + '/index.html')
    page.wait_for_function("typeof limitsFromCatalog === 'function'")
    got = page.evaluate("""limitsFromCatalog({applied: {names: {A: '쿨러 성능 저하', B: '펌프 내부 누설'}, catalog: {
        A: {condition: 'CE < 70.0 and TS1 > 55.0 and slope(TS1) > 0.0'},
        B: {condition: 'FS1 < 8.0 and LoadSP >= 80.0 and PLC.state == "RUN" and PS1 < 165.0'}}}})""")
    assert got == {'CE': [{'value': 70, 'below': True, 'pattern': '쿨러 성능 저하'}], 'TS1': [{'value': 55, 'below': False, 'pattern': '쿨러 성능 저하'}],
                   'FS1': [{'value': 8, 'below': True, 'pattern': '펌프 내부 누설'}], 'PS1': [{'value': 165, 'below': True, 'pattern': '펌프 내부 누설'}]}


def test_설비_회로는_처리_건으로_보내는_줄만_갖고_상태_이름을_따로_부르지_않는다(world):
    """같은 것을 두 이름 · 두 색으로 보이지 않는다: 줄은 처리 건 화면의 거르기와 같은 말(진행 중 / 처리 완료)만 하고, 처리 건의 상태 이름(반려 · 종결 · 효과 확인 중 …)은 처리 건 화면에만 있다."""
    w, page = world, world.page
    w.incidents = [
        {'id': 'INC-a', 'asset': 'HYD-01', 'alertId': 'ALT-a', 'state': 'REJECTED_BY_OPERATOR', 'terminal': True, 'created': '2026-01-01T00:00:00Z', 'closed': '2026-01-01T00:05:00Z'},
        {'id': 'INC-b', 'asset': 'HYD-01', 'alertId': 'ALT-b', 'state': 'RE_OBSERVING', 'terminal': False, 'created': '2026-01-01T01:00:00Z'},
        {'id': 'INC-c', 'asset': 'HYD-02', 'alertId': 'ALT-c', 'state': 'CLOSED', 'terminal': True, 'created': '2026-01-01T02:00:00Z', 'closed': '2026-01-01T02:05:00Z'}]
    page.goto(w.base + '/index.html#/incidents')
    page.wait_for_selector('#incList .case-link')
    # 고른 설비(HYD-01)의 것만 센다: 두 건 가운데 진행 중 하나. 목록의 사본은 없고, 링크는 진행 중인 그 처리 건을 연다
    assert page.eval_on_selector_all('#incList .case-link b', 'ns => ns.map(n => n.textContent)') == ['2', '1'] and page.locator('#incList .row').count() == 0
    assert page.get_attribute('#incList .case-link .btn', 'data-open-incident') == 'INC-b'
    text = page.inner_text('#view-incidents')
    assert not any(word in text for word in ('반려', '종결', '효과 확인', '재관측', '사건'))
    assert '열린 처리 건이 있습니다' in page.inner_text('#scadaInfo') and page.get_attribute('#scadaInfo .open', 'data-open-incident') == 'INC-b'
    page.click("#scada [data-asset='HYD-03']")
    assert page.inner_text('#scadaInfo .open').strip() == '결함 시뮬레이션 열기'
    assert page.eval_on_selector_all('#incList .case-link b', 'ns => ns.map(n => n.textContent)') == [] or page.inner_text('#incList .case-link b') == '0'      # HYD-03 은 열린 적이 없다
    assert page.get_attribute('#incList .case-link .btn', 'data-go-tab') == 'scenario'


def test_거래_기록은_무엇을_어느_설비에_어느_조치_방법으로_언제_누가를_칸으로_나눠_보인다(world):
    """서버가 이어 붙인 문장(detail)과 영문 제품 이름이 줄의 머리에 나오지 않는다 — 원문은 접기 안에만 있다."""
    w, page = world, world.page
    detail = 'HYD-01 SOP-COOL-11 팬 최대 운전 → 작업지시 선택한 조치 이후 정비 점검: 팬 최대 운전 — 즉시'
    order = {'id': 'WO-1', 'asset': 'HYD-01', 'task': 'SOP-COOL-11 팬 최대 운전 → 작업지시', 'status': '배정됨', 'option_id': 'skill:x', 'window_label': '야간 정비 시간 11-14 19:00'}
    w.extra = {'/svc/enterprise-sim/api/state': {'mes': {'orders': []}, 'cmms': {'work_orders': [order]}, 'erp': {'purchase_requests': [], 'goods_receipts': []}},
               '/svc/enterprise-sim/api/transactions': [{'id': 'TX-1', 't': '2026-01-01T00:00:00Z', 'system': 'sys:cmms', 'skill': 'skill:schedule-maintenance', 'ref': 'WO-1',
                                                         'detail': detail, 'asset': 'HYD-01', 'option': 'skill:x', 'by': 'user:me', 'compensates': None, 'before': None, 'after': order}],
               '/svc/process/api/decisions': []}
    page.goto(w.base + '/index.html#/process')
    page.wait_for_selector('#txList .event-record')
    page.evaluate("UI.names['skill:x'] = '팬 최대 운전'; UI.namesVersion += 1")
    page.wait_for_function("document.querySelector('#txList details.tx summary').innerText.includes('팬 최대 운전')", timeout=8000)
    # 표의 머리 줄과 그 줄의 칸이 같은 차례다 — 칸 이름으로 값을 읽는다
    assert page.eval_on_selector_all('#txList .tx-head span', 'ns => ns.map(n => n.textContent).filter(Boolean)') == ['시각', '종류', '업무 시스템', '설비', '조치 방법', '정비 시점', '번호', '누가']
    cells = page.eval_on_selector_all('#txList details.tx summary > span', "ns => Object.fromEntries(ns.map(n => [n.dataset.col, n.textContent]))")
    assert {k: cells[k] for k in ('종류', '업무 시스템', '설비', '조치 방법', '정비 시점', '번호')} == {'종류': '정비 요청', '업무 시스템': cells['업무 시스템'], '설비': 'HYD-01', '조치 방법': '팬 최대 운전',
                                                                                 '정비 시점': '야간 정비 시간 11-14 19:00', '번호': 'WO-1'}
    assert '정비 관리' in cells['업무 시스템'] and cells['누가'] not in ('', 'user:me')
    shown = page.inner_text('#txList details.tx summary')
    assert '작업지시' not in shown and 'CMMS' not in shown
    # 줄을 누르면 그 줄 아래에 변경 전 · 후와 원문이 열린다(원문은 접힌 채)
    page.click('#txList details.tx summary')
    assert page.evaluate("(() => { const d = document.querySelector('#txList details.tx'); return [d.open, !!d.querySelector('.tx-body table'), d.querySelector('.tx-body details.raw').open]; })()") == [True, True, False]
    page.click('#bzTabs [data-bz-view="now"]')
    # 정비 관리 표도 같은 칸으로 — 정비 시점이 보인다
    assert page.eval_on_selector_all('#sysBoards table tbody tr:first-child td', 'ns => ns.map(n => n.textContent)') == ['WO-1', 'HYD-01', '팬 최대 운전', '야간 정비 시간 11-14 19:00', '배정됨']


def test_결함_시뮬레이션은_범위를_한_번만_말하고_단추가_하는_일은_도움말로_닿는다(world):
    """화면은 읽는 곳이 아니라 보고 누르는 곳이다: 「명령 관문을 거치지 않는다」는 화면에 한 번만 보이고, 설명 문단 대신 단추마다 도움말(올리거나 초점을 주면 나온다)이 있다."""
    w, page = world, world.page
    page.goto(w.base + '/index.html#/scenario')
    page.wait_for_selector("#units .unit[data-asset='HYD-01'] button[data-act='degrade']")
    for card in page.locator('#units .unit details').all():      # 접기를 모두 펴도 되풀이되지 않는다
        card.evaluate('d => { d.open = true; }')
    text = page.inner_text('#view-scenario')
    assert text.count('명령 관문을 거치지 않습니다') == 1
    # 카드에 늘 보이는 설명 문장은 사실 한 줄까지 — 결함 절에 문단이 없다
    assert page.eval_on_selector_all("#units .lab-exp > p:not(.lab-note)", "ns => ns.every(n => n.getBoundingClientRect().height <= 24)")
    assert page.inner_text("#units .unit[data-asset='HYD-01'] .repeat-guide") == ''      # 그 상황이 아니면 안내 줄이 없다
    # 도움말: 주입 단추에 초점을 주면 그 단추가 하는 일이 뜬다(키보드로도 닿는다)
    button = "#units .unit[data-asset='HYD-01'] button[data-act='degrade']"
    tip = page.get_attribute(button, 'data-tooltip')
    assert tip and '경보' in tip
    page.focus(button)
    page.keyboard.press('Shift+Tab'); page.keyboard.press('Tab')      # 키보드로 옮겨 온 초점
    assert page.evaluate("sel => document.activeElement === document.querySelector(sel) && document.activeElement.matches(':focus-visible')", button)
    page.wait_for_timeout(500)                                          # 도움말이 나타나는 움직임(0.15초)이 끝난 뒤에 잰다
    shown = page.evaluate("sel => { const s = getComputedStyle(document.querySelector(sel), '::before'); return [s.content, s.visibility, s.opacity]; }", button)
    assert tip in shown[0] and shown[1] == 'visible' and float(shown[2]) > 0, shown
    # 결함이 걸린 채 새 경보가 나지 않는 상황이 되면 그때만 한 줄
    w.units['HYD-01'] = unit('HYD-01', ts1=50.0, health=0.55)
    page.wait_for_function("document.querySelector(\"#units .unit[data-asset='HYD-01'] .repeat-guide\").textContent.includes('쿨러 복구')", timeout=8000)


def test_진행_중인_처리_건이_있는_업무_사건의_시작_단추는_꺼져_있고_눌러도_요청을_보내지_않고_까닭을_말한다(world):
    """한 바퀴 23: 정기 정비 처리 건이 진행 중인데 [정기 정비 시작]이 켜져 있어 누르면 409 가 났다. 누를 수 없으면 꺼 두고 까닭을 한 줄로 말하며,
    그 건으로 가는 길(카드 아래 「처리 건에서 보기」)을 둔다. 사건 줄의 pattern 으로 이 경보 종류의 사건만 잇는다."""
    w, page = world, world.page
    running = {'instance': 'c3_pm.1', 'status': 'RUNNING', 'started_at': '2026-11-14T00:08:43Z', 'ended_at': None, 'outcome': None}
    scen = {'key': 'B', 'asset': 'HYD-02', 'pattern': 'PM_DUE', 'label': '정기 점검 도래', 'button': '정기 점검', 'title': '정기 정비', 'alert': True,
            'facts': {'pm_since_h': 1950, 'pm_interval_h': 2000, 'pm_due_in_h': 50}, 'running': running, 'last': running, 'events': []}
    posts = []
    page.on('request', lambda r: posts.append(r.url) if r.method == 'POST' else None)
    w.extra['/svc/process/api/scenario/status'] = {'scenarios': {'B': scen}, 'presses': {}}
    orig = w.answer
    page.unroute('**/*')
    page.route('**/*', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(w.extra['/svc/process/api/scenario/status']))
               if route.request.url.split('?')[0].endswith('/api/scenario/status') else orig(route))
    page.goto(w.base + '/index.html#/scenario')
    start = page.locator("#units .unit[data-asset='HYD-02'] button[data-act='biz-start']")
    start.wait_for(timeout=8000)
    assert start.get_attribute('aria-disabled') == 'true' and '진행 중인 처리 건이 있어' in start.get_attribute('data-tooltip')
    assert page.locator("#units .unit[data-asset='HYD-02'] .unit-go").is_visible()      # 그 건으로 가는 길
    start.click(force=True)
    page.wait_for_function("document.querySelector('#scenarioMsg').textContent.includes('진행 중인 처리 건이 있어')", timeout=8000)
    assert not any('/api/scenario/B/start' in u for u in posts), posts                   # 서버에 409 를 받으러 가지 않는다
