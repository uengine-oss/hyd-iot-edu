"""포털의 유압 설비 · 시스템 구성 화면(it/portal/www/app.js · oilInput.js · enterprise.js 의 업무 시스템 기록) — 실제 포털 파일을 이 PC 포트에 띄우고 실제 브라우저(Playwright Chromium)로 연다.
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
        self.broker, self.left_out, self.asked = {'plant-sim', 'connect-ingest', 'cmd-gateway'}, [], []      # 브로커에 붙었다고 답하는 서비스 · 감지기가 뺀 패턴 · 화면이 부른 주소
        self.scen = {'scenarios': {}, 'presses': {}}      # 업무 사건의 상태(GET /api/scenario/status)
        self.conflict, self.oil, self.sent_oil = None, None, None      # 시작을 409 로 거절할 때의 응답 · 오일 분석 입력의 응답 · 화면이 보낸 입력

    def answer(self, route):
        req = route.request
        path = req.url.split('://', 1)[1].split('/', 1)[1].split('?')[0] if '/' in req.url.split('://', 1)[1] else ''
        path = '/' + path
        self.asked.append(req.url)
        send = lambda body, status=200: route.fulfill(status=status, content_type='application/json', body=json.dumps(body))
        if not path.startswith('/svc/'):
            return route.fulfill(status=200, body='') if ':' in req.url.split('://', 1)[1].split('/')[0] and not req.url.startswith(self.base) else route.continue_()
        service = path.split('/')[2]
        if path.endswith('/healthz'):
            if service in self.down:
                return send({'detail': 'down'}, 503)
            body = {'ok': True}
            if service in ('plant-sim', 'connect-ingest', 'cmd-gateway'):
                body['mqtt'] = service in self.broker
            if service == 'detector':
                body['patterns'] = {'ready': True, 'error': None, 'rejected': self.left_out}
            return send(body)
        if path == '/svc/plant-sim/api/state':
            return send({'time_scale': 20.0, 'sim_t': 100.0, 'units': self.units})
        if path == '/svc/detector/api/detector/state':
            pat = lambda a: {'COOLER_DEGRADATION': {'phase': self.phase if a == 'HYD-01' else 'IDLE', 'alert_id': self.alert if a == 'HYD-01' else None}}
            return send({'time_scale': 20.0, 'assets': {a: {'patterns': pat(a)} for a in self.units}})
        if path == '/svc/process/api/incidents':
            return send(self.incidents)
        if path == '/svc/process/api/scenario/status':
            return send(self.scen)
        if path.startswith('/svc/process/api/scenario/') and path.endswith('/start') and self.conflict:
            return send(self.conflict, 409)
        if path == '/svc/process/api/human-alerts' and req.method == 'POST':
            self.sent_oil = json.loads(req.post_data)
            return send(self.oil)
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
    # 과정 판은 설비 카드 아래에 펼쳐진다 — 누른 카드를 아래로 밀어내지 않는다
    assert page.evaluate("document.getElementById('labFollowPanel').getBoundingClientRect().top >= document.getElementById('units').getBoundingClientRect().bottom")
    assert '56.2' in page.inner_text("#labFollow .lv-step[data-step='rise']")      # 넘어간 때의 값이 그 줄에 남는다


def test_구조_그림은_부품_표의_부품을_모두_놓고_응답_없는_부품을_이름으로_말한다(world):
    w, page = world, world.page
    w.down = {'detector'}
    page.goto(w.base + '/index.html#/home')
    page.wait_for_function("document.getElementById('sysSum').textContent.includes('응답 없음')", timeout=15000)
    table = page.evaluate("LAYERS.flatMap((L, i) => L.comps.map(c => ({key: c.name.split(' ')[0], role: c.role, real: c.real || '', optional: !!c.optional, health: !!c.health, layer: `Layer ${LAYERS.length - i}`, nets: c.nets})))")
    drawn = page.eval_on_selector_all('#stack .sys-nd', 'ns => Object.fromEntries(ns.map(n => [n.dataset.key, n.dataset.st]))')
    assert sorted(drawn) == sorted(c['key'] for c in table)              # 표의 부품이 빠짐없이, 표에 없는 부품 없이
    assert drawn['detector'] == 'down' and page.inner_text('#sysSum') == '응답 없음 1 — detector'
    assert all(drawn[c['key']] == 'opt' for c in table if c['optional'])      # 선택 도구는 응답 없음으로 세지 않는다
    # 그림이 읽히는가: 부품 상자끼리 8px 넘게 떨어져 있고, 길의 이름표가 어느 상자와도 겹치지 않으며, 상자 안의 이름이 상자 밖으로 나가지 않는다
    geo = page.evaluate('''() => { const r = e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
      return { boxes: [...document.querySelectorAll('#stack .sys-nd')].map(n => ({ key: n.dataset.key, box: r(n.querySelector('.box')), texts: [...n.querySelectorAll('text')].map(r) })),
               labels: [...document.querySelectorAll('#stack .sys-p-t')].map(t => ({ text: t.textContent, box: r(t) })) }; }''')
    hit = lambda a, b, pad=0: a[0] < b[2] + pad and b[0] < a[2] + pad and a[1] < b[3] + pad and b[1] < a[3] + pad
    boxes = geo['boxes']
    assert len(boxes) >= 17 and geo['labels']
    assert not [(a['key'], b['key']) for i, a in enumerate(boxes) for b in boxes[i + 1:] if hit(a['box'], b['box'], 8)]
    assert not [(lab['text'], b['key']) for lab in geo['labels'] for b in boxes if hit(lab['box'], b['box'])]
    assert not [b['key'] for b in boxes for t in b['texts'] if t[0] < b['box'][0] or t[2] > b['box'][2] - 4]
    # 그림 전체가 창(1440 × 900) 안에 스크롤 없이 들어오고, 그렇게 맞춰도 부품 이름이 화면에서 14px 아래로 내려가지 않는다(사용자: 「시스템구성은 아직 여유가 너무 없어보이고」)
    fit = page.evaluate('''() => { const s = document.querySelector('#stack svg').getBoundingClientRect(), st = document.getElementById('stack'), t = document.querySelector('#stack .sys-nd .t'), bx = document.querySelector('#stack .sys-nd .box');
      return { svg: [s.left, s.top, s.right, s.bottom], win: [innerWidth, innerHeight], pan: st.scrollWidth - st.clientWidth, name: parseFloat(getComputedStyle(t).fontSize) * bx.getBoundingClientRect().width / bx.width.baseVal.value }; }''')
    assert fit['svg'][0] >= 232 and fit['svg'][1] >= 48 and fit['svg'][2] <= fit['win'][0] and fit['svg'][3] <= fit['win'][1] and fit['pan'] <= 1, fit
    assert fit['name'] >= 14, fit
    # 밝은 캔버스에서 읽히는가: 부품 이름 · 서비스 이름은 상자 면과, 길의 이름표 · 영역 이름 · 계층 이름은 캔버스 바탕과 대비 4.5 이상
    low = page.evaluate(r'''() => { const lum = c => { let m = /^rgba?\(([^)]+)\)/.exec(c), v; if (m) v = m[1].split(/[, /]+/).slice(0, 3).map(x => Number(x) / 255); else { m = /^color\(srgb ([^)]+)\)/.exec(c); if (!m) throw new Error('모르는 색: ' + c); v = m[1].split(/[ /]+/).slice(0, 3).map(Number); }
        const [r, g, b] = v.map(x => x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
      const ratio = (a, b) => { const x = lum(a), y = lum(b); return +((Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)).toFixed(2); };
      const fill = e => getComputedStyle(e).fill, bg = getComputedStyle(document.querySelector('.sys-arch')).backgroundColor, out = [];
      document.querySelectorAll('#stack .sys-nd').forEach(n => n.querySelectorAll('text').forEach(t => out.push([n.dataset.key + ' ' + t.getAttribute('class'), ratio(fill(t), fill(n.querySelector('.box')))])));
      document.querySelectorAll('#stack .sys-p-t, #stack .sys-row-t, #stack .sys-row-cap, #stack .sys-row-n, #stack .sys-band-s, #stack .sys-band-n, #stack .sys-lg-t').forEach(t => out.push([t.textContent, ratio(fill(t), bg)]));
      return out.filter(x => x[1] < 4.5); }''')
    assert not low, low
    assert all(drawn[c['key']] == 'none' for c in table if not c['health'])   # 상태를 재지 않는 부품은 점이 없다
    assert all(drawn[c['key']] == 'ok' for c in table if c['health'] and not c['optional'] and c['key'] != 'detector')
    # 올리면 정보 띠에 그 부품의 하는 일 · 현업 대응 · 계층 · 붙은 망(모두 부품 표의 글)과 상태가 보인다
    for key in ('detector', 'cmd-gateway', 'agent-worker', 'EMQX', 'plant-sim', 'TimescaleDB'):
        c = next(x for x in table if x['key'] == key)
        page.hover(f"#stack .sys-nd[data-key='{key}']")
        info = page.inner_text('#sysInfo')
        assert c['role'] in info and f"현업에서는 {c['real']}" in info and c['layer'] in info and all(n in info for n in c['nets']), info      # 계층은 왼쪽 줄 이름과 같은 번호(Layer n)로
        assert page.evaluate("(() => { const i = document.getElementById('sysInfo'); return i.scrollHeight - i.clientHeight; })()") <= 0, key      # 카드 안을 굴리지 않고 다 읽힌다
        assert ('응답 없음' if key == 'detector' else '상태 확인 대상 아님' if key == 'TimescaleDB' else '정상') in info
        # 정보 카드는 그림의 빈 칸에 뜬다 — 어느 부품 상자도 가리지 않는다
        card = page.evaluate("(() => { const b = document.getElementById('sysInfo').getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; })()")
        now = page.evaluate("[...document.querySelectorAll('#stack .sys-nd')].map(n => { const b = n.querySelector('.box').getBoundingClientRect(); return { key: n.dataset.key, box: [b.left, b.top, b.right, b.bottom] }; })")
        assert not [b['key'] for b in now if hit(card, b['box'])], (key, card)
    # 다시 응답하면 요약이 정상으로 돌아온다
    w.down = set()
    # 머리의 요약은 응답 없는 서비스가 있을 때만 보인다 — 정상일 때의 「서비스 n/n」은 메뉴 줄 아래 한 곳에 있다
    page.wait_for_function("document.getElementById('sysSum').hidden", timeout=15000)
    assert not page.is_visible('#sysSum')


def test_MQTT_브로커의_상태는_관리_화면이_아니라_브로커에_붙는_서비스들의_mqtt_값으로_읽는다(world):
    """메시지 중계기의 관리 화면 · 관리 API(18083)는 꺼져 있다. 화면이 그 주소의 상태를 읽으면 늘 「1개 응답 없음」이 되어, 시작 창이 「서비스 상태 점이
    초록이면 됩니다」라고 한 학생은 설치가 실패했다고 읽는다. 브로커의 상태는 그 브로커에 붙는 세 서비스(가상 설비 · 수집 중계 · 명령 관문)의 /healthz 가
    말하는 mqtt 값이다: 하나라도 붙어 있으면 살아 있고, 셋 다 떨어졌다고 하면 응답 없음이다. 여는 화면은 없다."""
    w, page = world, world.page
    page.goto(w.base + '/index.html#/home')
    state = lambda: page.get_attribute("#stack .sys-nd[data-key='EMQX']", 'data-st')
    page.wait_for_function("document.querySelector(\"#stack .sys-nd[data-key='EMQX']\").dataset.st === 'ok'", timeout=15000)
    assert '14/14' in page.inner_text('#healthDots') and page.get_attribute('#healthDot', 'data-tone') == 'ok'
    assert page.get_attribute("#stack .sys-nd[data-key='EMQX']", 'href') is None          # 누르면 열리는 화면이 없다
    page.hover("#stack .sys-nd[data-key='EMQX']")
    assert '여는 화면이 없습니다' in page.inner_text('#sysInfo') and page.locator('#sysInfo [data-sys-open]').count() == 0
    w.broker = {'cmd-gateway'}                                                            # 한 서비스만 붙어 있어도 브로커는 살아 있다
    page.wait_for_timeout(6000)
    assert state() == 'ok'
    w.broker = set()                                                                      # 셋 다 「브로커에 붙지 못했다」고 답한다
    page.wait_for_function("document.querySelector(\"#stack .sys-nd[data-key='EMQX']\").dataset.st === 'down'", timeout=15000)
    assert page.inner_text('#sysSum') == '응답 없음 1 — EMQX' and '13/14' in page.inner_text('#healthDots')
    assert not [u for u in w.asked if ':18083' in u], '꺼 둔 관리 화면의 주소를 부른다'


def test_감지기가_감지에서_뺀_이상_패턴은_서비스_점이_초록인_채로_묻히지_않는다(world):
    """조건식이 틀린 이상 패턴은 그것만 감지에서 빠지고 감지기는 정상으로 답한다(/healthz 의 patterns.rejected). 화면이 그 칸을 읽지 않으면 서비스 점은
    초록이고, 그 패턴의 결함은 넣어도 조용히 경보가 나지 않는다. 메뉴 줄 · 시스템 구성 머리 · 결함 시뮬레이션이 빠진 패턴과 까닭을 말한다."""
    w, page = world, world.page
    page.goto(w.base + '/index.html#/scenario')
    page.wait_for_function("document.getElementById('healthDots').textContent.includes('14/14')", timeout=15000)
    assert page.is_hidden('#labLeftOut') and page.get_attribute('#healthDot', 'data-tone') == 'ok'
    w.left_out = [{'code': 'MY_PATTERN', 'id': 'pattern:my', 'reason': "DefinitionError: unknown tag 'TS9'"}, {'code': None, 'id': 'pattern:two', 'reason': '지속 시간이 0초입니다'}]
    page.wait_for_function("!document.getElementById('labLeftOut').hidden", timeout=15000)
    said = page.inner_text('#labLeftOut')
    assert '이상 패턴 2개가 감지에서 빠져 있습니다' in said and 'MY_PATTERN' in said
    assert "조건식을 읽지 못했습니다 (원문: DefinitionError: unknown tag 'TS9')" in said      # 영문 까닭은 한국어 틀 + 원문 그대로
    assert 'pattern:two — 지속 시간이 0초입니다' in said                                       # 한국어 까닭은 그대로
    assert page.get_attribute('#healthDot', 'data-tone') == 'warn' and '감지에서 빠진 패턴 2' in page.inner_text('#healthDots')
    page.goto(w.base + '/index.html#/home')
    page.wait_for_function("!document.getElementById('sysSum').hidden", timeout=15000)
    assert page.inner_text('#sysSum') == '감지에서 빠진 이상 패턴 2'
    w.left_out = []
    page.wait_for_function("document.getElementById('sysSum').hidden", timeout=15000)


def test_추이의_기준선은_감지기_조건식에서_태그와_숫자를_바로_견주는_항만_읽는다(world):
    page = world.page
    page.goto(world.base + '/index.html')
    page.wait_for_function("typeof limitsFromCatalog === 'function'")
    got = page.evaluate("""limitsFromCatalog({applied: {names: {A: '쿨러 성능 저하', B: '펌프 내부 누설'}, catalog: {
        A: {condition: 'CE < 70.0 and TS1 > 55.0 and slope(TS1) > 0.0'},
        B: {condition: 'FS1 < 8.0 and LoadSP >= 80.0 and PLC.state == "RUN" and PS1 < 165.0'}}}})""")
    assert got == {'CE': [{'value': 70, 'below': True, 'pattern': '쿨러 성능 저하'}], 'TS1': [{'value': 55, 'below': False, 'pattern': '쿨러 성능 저하'}],
                   'FS1': [{'value': 8, 'below': True, 'pattern': '펌프 내부 누설'}], 'PS1': [{'value': 165, 'below': True, 'pattern': '펌프 내부 누설'}]}


SYS_GEO = r'''() => { const svg = document.querySelector('#stack svg'), k = svg.getScreenCTM().a;
  const R = e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
  const pts = p => { const n = p.getTotalLength(), m = p.getScreenCTM(), out = []; for (let d = 0; d <= n; d += 2) { const q = p.getPointAtLength(d); out.push([q.x * m.a + m.e, q.y * m.d + m.f]); } return out; };
  return { scale: k,
    labels: [...svg.querySelectorAll('.sys-p-t')].map(t => ({ text: t.textContent, i: t.dataset.i, box: R(t), font: parseFloat(getComputedStyle(t).fontSize) * k })),
    boxes: [...svg.querySelectorAll('.sys-nd')].map(n => ({ key: n.dataset.key, box: R(n.querySelector('.box')) })),
    paths: [...svg.querySelectorAll('path.sys-p[data-i]')].map(p => ({ i: p.dataset.i, kind: p.dataset.k, pts: pts(p) })),
    words: [...svg.querySelectorAll('.sys-band-t, .sys-band-s, .sys-band-n, .sys-row-t, .sys-row-cap, .sys-row-n, .sys-lg-t')].map(t => ({ text: t.textContent, box: R(t) })),
    small: [...svg.querySelectorAll('text')].filter(t => t.textContent.trim()).map(t => [t.textContent, +(parseFloat(getComputedStyle(t).fontSize) * k).toFixed(2)]).filter(x => x[1] < 13) }; }'''


def _gap(a, b):
    """두 상자 사이의 가장 가까운 거리(겹치면 0)."""
    dx, dy = max(a[0] - b[2], b[0] - a[2], 0), max(a[1] - b[3], b[1] - a[3], 0)
    return (dx * dx + dy * dy) ** 0.5


def test_명령이_내려가는_길과_그_이름표는_다른_선_상자_이름표와_겹치지_않고_글자_높이만큼_떨어져_있다(world):
    """사용자: 「검증할 명령 수행 화살표를 세로로 좀 높여서」 — 「검증할 명령」 · 「검증을 통과한 명령」 길이 상자 사이의 좁은 틈에 이름표와 함께 끼어 있었다.
    1440 × 900 창의 실제 브라우저에서 잰다: 두 길이 다른 길과 나란히 포개지지 않고(가로지르는 것은 길이 아니다) 지나는 상자가 없으며, 그림의 모든 이름표가 상자 · 다른 이름표 · 다른 길과
    겹치지 않고, 두 이름표는 가장 가까운 상자 · 다른 이름표에서 그 글자 높이 이상 떨어져 있다. 그림의 글자는 그 창에서 13px 아래로 줄지 않는다."""
    w, page = world, world.page
    page.goto(w.base + '/index.html#/home')
    page.wait_for_selector('#stack .sys-nd')
    page.wait_for_timeout(400)
    g = page.evaluate(SYS_GEO)
    hit = lambda a, b: a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
    inside = lambda p, b, pad=0: b[0] + pad < p[0] < b[2] - pad and b[1] + pad < p[1] < b[3] - pad
    labels = {x['text']: x for x in g['labels']}
    assert {'검증할 명령', '검증을 통과한 명령'} <= set(labels), list(labels)
    paths = {p['i']: p for p in g['paths']}
    for name in ('검증할 명령', '검증을 통과한 명령'):
        lab, own = labels[name], paths[labels[name]['i']]
        assert own['kind'] == 'cmd'
        # 길: 어느 상자도 지나지 않는다(끝은 상자의 가장자리에 닿는다)
        assert not [(name, b['key']) for b in g['boxes'] for p in own['pts'] if inside(p, b['box'], 3)]
        # 길: 다른 길과 나란히 포개지지 않는다 — 4px 안에 다른 길이 있는 구간이 가로지르는 폭(12px)보다 길지 않다
        for other in g['paths']:
            if other['i'] == own['i']:
                continue
            run = longest = 0
            for p in own['pts']:
                near = any(abs(p[0] - q[0]) < 4 and abs(p[1] - q[1]) < 4 for q in other['pts'])
                run = run + 2 if near else 0
                longest = max(longest, run)
            assert longest <= 12, (name, other['i'], longest)
        # 이름표: 가장 가까운 상자 · 다른 이름표(길의 이름표와 영역 · 계층 · 범례의 글)에서 글자 높이 이상
        near_box = min(_gap(lab['box'], b['box']) for b in g['boxes'])
        near_word = min(_gap(lab['box'], o['box']) for o in g['labels'] + g['words'] if o is not lab)
        assert near_box >= lab['font'] and near_word >= lab['font'], (name, round(near_box, 1), round(near_word, 1), round(lab['font'], 1))
    # 모든 이름표: 상자 · 다른 이름표 · 다른 길(제 길은 빼고) 위에 놓이지 않는다
    for lab in g['labels']:
        assert not [b['key'] for b in g['boxes'] if hit(lab['box'], b['box'])], lab['text']
        assert not [o['text'] for o in g['labels'] + g['words'] if o is not lab and hit(lab['box'], o['box'])], lab['text']
        assert not [p['i'] for p in g['paths'] if p['i'] != lab['i'] and any(inside(q, lab['box'], 2) for q in p['pts'])], lab['text']
    assert not g['small'], g['small']      # 그림의 글자(부품 이름 · 서비스 이름 · 계층 · 망 · 길의 이름표 · 범례)가 화면에서 13px 이상
    # 범례는 그림 안에 있다 — 캔버스 위에 줄을 따로 차지하지 않고, 영역 띠 · 상자와 겹치지 않는다
    lg = page.evaluate("[...document.querySelectorAll('#stack .sys-lg-t')].map(t => t.textContent)")
    assert lg == ['값이 올라가는 길', '승인된 명령이 내려가는 길', 'AI가 지식을 읽는 길', '명령 길 밖의 조작']
    assert page.locator('#view-home .canvas-bar').count() == 0


def test_설비_회로는_고른_설비를_크게_나머지를_작게_놓아_캔버스를_채우고_처리_건으로_보내는_한_줄만_갖는다(world):
    """같은 것을 두 이름 · 두 색으로 보이지 않는다: 아래 한 줄은 처리 건 화면의 거르기와 같은 말(진행 중)만 하고, 처리 건의 상태 이름(반려 · 종결 · 효과 확인 중 …)은 처리 건 화면에만 있다.
    회로 셋을 한 줄에 놓아 캔버스의 위아래가 비던 것(카드 높이 260px 남짓)을, 고른 설비 하나를 크게 · 나머지 둘을 작게 놓아 채운다."""
    w, page = world, world.page
    w.incidents = [
        {'id': 'INC-a', 'asset': 'HYD-01', 'alertId': 'ALT-a', 'state': 'REJECTED_BY_OPERATOR', 'terminal': True, 'created': '2026-01-01T00:00:00Z', 'closed': '2026-01-01T00:05:00Z'},
        {'id': 'INC-b', 'asset': 'HYD-01', 'alertId': 'ALT-b', 'state': 'RE_OBSERVING', 'terminal': False, 'created': '2026-01-01T01:00:00Z'},
        {'id': 'INC-c', 'asset': 'HYD-02', 'alertId': 'ALT-c', 'state': 'CLOSED', 'terminal': True, 'created': '2026-01-01T02:00:00Z', 'closed': '2026-01-01T02:05:00Z'}]
    page.goto(w.base + '/index.html#/incidents')
    page.wait_for_selector('#incList .hc-cases b')
    # 고른 설비(HYD-01)의 것만 센다: 두 건 가운데 진행 중 하나. 목록의 사본은 없고, 링크는 하나이며 진행 중인 그 처리 건을 연다
    assert page.eval_on_selector_all('#incList .hc-cases b', 'ns => ns.map(n => n.textContent)') == ['2', '1'] and page.locator('#incList .row').count() == 0
    assert page.locator('#incList a, #incList button').count() == 1 and page.get_attribute('#incList .go', 'data-open-incident') == 'INC-b'
    assert 'HYD-01의 경보로 열린 처리 건' in page.inner_text('#incList')
    text = page.inner_text('#view-incidents')
    assert not any(word in text for word in ('반려', '종결', '효과 확인', '재관측', '사건', '열린 처리 건 없음'))
    # 캔버스: 고른 설비의 카드가 가장 크고(나머지의 두 배 넘는 넓이) 세 카드와 아래 한 줄이 창(1440 × 900) 안에 스크롤 없이 보이며, 카드와 한 줄이 캔버스 높이의 대부분을 쓴다(위아래가 비지 않는다)
    seen = page.evaluate(r'''() => { const lum = c => { let m = /^rgba?\(([^)]+)\)/.exec(c), v; if (m) v = m[1].split(/[, /]+/).slice(0, 3).map(x => Number(x) / 255); else { m = /^color\(srgb ([^)]+)\)/.exec(c); if (!m) throw new Error('모르는 색: ' + c); v = m[1].split(/[ /]+/).slice(0, 3).map(Number); }
        const [r, g, b] = v.map(x => x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
      const ratio = (a, b) => { const x = lum(a), y = lum(b); return +((Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)).toFixed(2); };
      const R = e => e.getBoundingClientRect(), inside = e => { const b = R(e); return b.width > 0 && b.top >= 0 && b.bottom <= innerHeight && b.left >= 0 && b.right <= innerWidth; };
      const cards = [...document.querySelectorAll('#scada .ucard')], cv = R(document.querySelector('.hc-canvas')), line = R(document.querySelector('#incList .hc-line'));
      const shown = c => [...c.querySelectorAll('svg text, svg tspan')].filter(t => t.textContent.trim() && t.getBoundingClientRect().width > 0);
      const big = cards.find(c => c.getAttribute('aria-pressed') === 'true'), k = big.querySelector('svg').getScreenCTM().a;
      return { cards: cards.map(inside), line: inside(document.querySelector('#incList .hc-line')), scroll: document.documentElement.scrollHeight - innerHeight,
        area: cards.map(c => [c.dataset.asset, c.getAttribute('aria-pressed'), Math.round(R(c).width * R(c).height)]),
        used: (Math.max(...cards.map(c => R(c).bottom)) - Math.min(...cards.map(c => R(c).top)) + line.height) / cv.height,
        overlap: cards.flatMap((a, i) => cards.slice(i + 1).filter(b => R(a).left < R(b).right && R(b).left < R(a).right && R(a).top < R(b).bottom && R(b).top < R(a).bottom)).length,
        small: shown(big).map(t => [t.textContent, +(parseFloat(getComputedStyle(t).fontSize) * k).toFixed(1)]).filter(x => x[1] < 13),
        tiny: cards.filter(c => c !== big).flatMap(c => shown(c).map(t => t.textContent)),
        low: shown(big).filter(t => !t.closest('.hc-sensor')).map(t => [t.textContent, ratio(getComputedStyle(t).fill, getComputedStyle(big).backgroundColor)]).filter(x => x[1] < 4.5) }; }''')
    assert seen['cards'] == [True, True, True] and seen['line'] and seen['scroll'] <= 0 and not seen['overlap'], seen
    area = {a: n for a, _, n in seen['area']}
    assert [p for _, p, _ in seen['area']] == ['true', 'false', 'false'] and area['HYD-01'] > 2 * area['HYD-02'] and area['HYD-02'] == area['HYD-03'], seen['area']
    assert seen['used'] >= 0.85, seen['used']
    assert not seen['small'] and not seen['low'], seen      # 크게 놓인 회로의 글자는 13px 이상이고 흰 카드 위에서 읽힌다
    assert not seen['tiny'], seen['tiny']                    # 작게 놓인 회로는 읽히지 않는 값 글자를 그리지 않는다 — 머리 줄의 유온 하나
    assert page.inner_text("#scada [data-asset='HYD-02'] .hc-now") == '유온 48.0 ℃'
    # 작은 카드를 누르면 그 설비가 크게 바뀌고 아래 줄이 그 설비의 것이 된다
    page.click("#scada [data-asset='HYD-03']")
    page.wait_for_function("document.querySelector(\"#scada [data-asset='HYD-03']\").getAttribute('aria-pressed') === 'true'")
    area3 = page.evaluate("Object.fromEntries([...document.querySelectorAll('#scada .ucard')].map(c => [c.dataset.asset, Math.round(c.getBoundingClientRect().width * c.getBoundingClientRect().height)]))")
    assert area3['HYD-03'] > 2 * area3['HYD-01'], area3
    assert page.eval_on_selector_all('#incList .hc-cases b', 'ns => ns.map(n => n.textContent)') == ['0']      # HYD-03 은 열린 적이 없다
    assert page.get_attribute('#incList .go', 'data-go-tab') == 'scenario' and '결함 시뮬레이션에서 결함 넣기' in page.inner_text('#incList .go')
    assert page.locator('#incList a, #incList button').count() == 1 and '열린 처리 건 없음' not in page.inner_text('#view-incidents')      # 빈 자리를 지키는 「없음」 글을 두지 않는다 — 가는 길 하나뿐
    # 좁은 폭에서는 고른 설비가 위에 온 폭으로, 나머지 둘이 그 아래 나란히
    page.set_viewport_size({'width': 900, 'height': 900})
    try:
        page.wait_for_timeout(300)
        r = page.evaluate("Object.fromEntries([...document.querySelectorAll('#scada .ucard')].map(c => { const b = c.getBoundingClientRect(); return [c.dataset.asset, [Math.round(b.left), Math.round(b.top), Math.round(b.width)]]; }))")
        assert r['HYD-03'][1] < r['HYD-01'][1] == r['HYD-02'][1] and r['HYD-03'][2] > 1.8 * r['HYD-01'][2], r
        assert page.evaluate('document.documentElement.scrollWidth - innerWidth') <= 0
        # 더 좁은 폭(390 · 640): 그림이 카드 폭에 맞춰 줄어도 크게 놓인 회로의 글자는 13px 아래로 줄지 않고(줄어든 만큼 글자를 키운다), 글자끼리 겹치지 않으며, 카드는 한 줄에 하나(390)
        for width in (640, 390):
            page.set_viewport_size({'width': width, 'height': 844})
            page.wait_for_timeout(400)
            got = page.evaluate('''() => { const big = document.querySelector('#scada .ucard[aria-pressed="true"]'), k = big.querySelector('svg').getScreenCTM().a;
              const ts = [...big.querySelectorAll('svg text')].filter(t => t.textContent.trim() && t.getBoundingClientRect().width > 0), R = t => t.getBoundingClientRect();
              return { small: ts.map(t => [...t.querySelectorAll('tspan'), t].map(n => [n.textContent, +(parseFloat(getComputedStyle(n).fontSize) * k).toFixed(1)])).flat().filter(x => x[1] < 13),
                hit: ts.flatMap((a, i) => ts.slice(i + 1).filter(b => R(a).left < R(b).right - 1 && R(b).left < R(a).right - 1 && R(a).top < R(b).bottom - 1 && R(b).top < R(a).bottom - 1).map(b => [a.textContent, b.textContent])),
                lefts: new Set([...document.querySelectorAll('#scada .ucard')].map(c => Math.round(c.getBoundingClientRect().left))).size, over: document.documentElement.scrollWidth - innerWidth }; }''')
            assert not got['small'] and not got['hit'] and got['over'] <= 0, (width, got)
            assert got['lefts'] == (1 if width == 390 else 2), (width, got['lefts'])
    finally:
        page.set_viewport_size({'width': 1440, 'height': 900})


def test_거래_기록은_무엇을_어느_설비에_어느_조치_방법으로_언제를_칸으로_나눠_보이고_그_처리_건으로_가는_링크를_준다(world):
    """서버가 이어 붙인 문장(detail)과 영문 제품 이름이 줄의 머리에 나오지 않는다 — 원문은 접기 안에만 있다. 건수는 보기 탭의 이름 뒤 한 곳에만 있다(탭과 겹치던 숫자 카드 넷은 없다)."""
    w, page = world, world.page
    detail = 'HYD-01 SOP-COOL-11 팬 최대 운전 → 작업지시 선택한 조치 이후 정비 점검: 팬 최대 운전 — 즉시'
    order = {'id': 'WO-1', 'asset': 'HYD-01', 'task': 'SOP-COOL-11 팬 최대 운전 → 작업지시', 'status': '배정됨', 'option_id': 'skill:x', 'window_label': '야간 정비 시간 11-14 19:00'}
    pr = {'id': 'PR-1', 'qty': 6, 'part': '펌프 축 씰 키트', 'part_no': 'P-PMP-SEAL', 'asset': 'HYD-03', 'status': '승인됨 → 발주', 'supplier': 'sup:a', 'supplier_name': 'A정밀 (저가)', 'option_id': 'skill:y', 'requested_by': 'user:me'}
    gr = {'id': 'GR-1', 'qty': 5, 'ordered_qty': 6, 'rejected_qty': 1, 'fail_rate': 0.12, 'inspection': '1개 불합격 · 반품', 'pr_id': 'PR-1', 'part_no': 'P-PMP-SEAL'}
    tx = lambda n, skill, ref, asset, option, dec, before, after: {'id': f'TX-{n}', 't': f'2026-01-01T00:0{n}:00Z', 'system': 'sys:cmms' if ref.startswith('WO') else 'sys:erp', 'skill': skill, 'ref': ref,
                                                                 'detail': detail, 'asset': asset, 'option': option, 'decision': dec, 'by': 'user:me', 'compensates': None, 'before': before, 'after': after}
    w.extra = {'/svc/enterprise-sim/api/state': {'mes': {'orders': []}, 'cmms': {'work_orders': [order]}, 'erp': {'purchase_requests': [dict(pr, supplierName='A정밀 (저가)')], 'goods_receipts': [gr]}},
               '/svc/enterprise-sim/api/transactions': [tx(3, 'skill:receive-goods', 'GR-1', 'HYD-03', 'skill:y', 'DEC-2', pr, gr), tx(2, 'skill:procure-part', 'PR-1', 'HYD-03', 'skill:y', 'DEC-2', None, pr),
                                                         tx(1, 'skill:schedule-maintenance', 'WO-1', 'HYD-01', 'skill:x', 'DEC-1', None, order)] + [tx(0, 'skill:schedule-maintenance', f'WO-old{i}', 'HYD-02', 'skill:x', 'DEC-none', None, order) for i in range(5)],
               '/svc/process/api/decisions': [{'id': 'DEC-1', 'origin': {'incident': 'INC-1', 'process_scope': {'instance': 'anomaly.1'}}}, {'id': 'DEC-2', 'origin': {'incident': 'INC-2', 'process_scope': {'instance': 'c3_spare.2'}}}]}
    page.goto(w.base + '/index.html#/process')
    page.wait_for_selector('#txList .event-record')
    page.evaluate("UI.names['skill:x'] = '팬 최대 운전'; UI.names['skill:y'] = '대체 승인 공급사 발주'; UI.namesVersion += 1")
    page.wait_for_function("document.querySelector('#txList').innerText.includes('팬 최대 운전')", timeout=8000)
    # 표의 머리 줄과 그 줄의 칸이 같은 차례 · 같은 세로선이다 — 칸 이름으로 값을 읽는다
    assert page.eval_on_selector_all('#txList .tx-head span', 'ns => ns.map(n => n.textContent).filter(Boolean)') == ['시각', '종류', '설비', '조치 방법', '내용', '번호']
    rows = page.eval_on_selector_all('#txList details.tx > summary', "ss => ss.map(s => Object.fromEntries([...s.querySelectorAll(':scope > span[data-col]')].map(n => [n.dataset.col, n.textContent])))")
    assert len(rows) == 6      # 여섯 줄까지 보이고 나머지는 「n건 더 보기」
    assert {k: rows[2][k] for k in ('종류', '설비', '조치 방법', '내용', '번호')} == {'종류': '정비 요청', '설비': 'HYD-01', '조치 방법': '팬 최대 운전', '내용': '야간 정비 시간 11-14 19:00', '번호': 'WO-1'}
    assert rows[1]['내용'] == '펌프 축 씰 키트 6개 · A정밀 (저가)' and rows[0]['내용'].startswith('5개 입고 (발주 6개) · 검수'), rows[:2]      # 고른 공급사와 그 결과(일부 불합격)가 줄에서 읽힌다
    lefts = page.evaluate("[...document.querySelectorAll('#txList .tx-head span')].map((h, i) => [...document.querySelectorAll('#txList details.tx > summary')].every(s => Math.abs(s.querySelectorAll(':scope > span[data-col]')[i].getBoundingClientRect().left - h.getBoundingClientRect().left) < 1))")
    assert all(lefts), lefts
    shown = page.inner_text('#txList')
    assert '작업지시' not in shown and 'CMMS' not in shown and 'ERP' not in shown
    # 줄의 오른쪽 끝: 그 거래를 낳은 판단의 처리 건으로 가는 링크(모르는 판단의 거래에는 없다) — 누르면 줄이 펴지지 않고 그 처리 건이 열린다
    links = page.eval_on_selector_all('#txList details.tx > summary', "ss => ss.map(s => (s.querySelector('.go') || {dataset: {}}).dataset.openInst || '')")
    assert links == ['c3_spare.2', 'c3_spare.2', 'anomaly.1', '', '', ''], links
    page.locator('#txList details.tx > summary .go').nth(2).click()
    page.wait_for_function("state.tab === 'instances'")
    assert page.evaluate("location.hash").startswith('#/instances')
    page.goto(w.base + '/index.html#/process')
    page.wait_for_selector('#txList .event-record')
    assert page.evaluate("document.querySelectorAll('#txList details.tx[open]').length") == 0
    # 건수는 탭 이름 뒤에만: 숫자 카드가 없고, 탭이 거래 8건 · 지금 기록 3건을 말한다
    assert page.locator('#view-process .stat').count() == 0
    assert page.eval_on_selector_all('#bzTabs [role=tab]', 'ns => ns.map(n => n.innerText.replace(/\\s+/g, " ").trim())') == ['거래 기록 8', '지금 기록 3']
    page.click('#txList [data-tx-more]')
    assert page.locator('#txList details.tx').count() == 8 and page.locator('#txList [data-tx-more]').count() == 0
    # 줄을 누르면 그 줄 아래에 업무 시스템 · 누가, 변경 전 · 후(칸 이름과 값이 화면 말)와 원문(접힌 채)이 열린다
    page.locator('#txList details.tx > summary').nth(0).click()
    opened = page.evaluate("(() => { const d = document.querySelector('#txList details.tx'); return [d.open, d.querySelector('.tx-body details.raw').open, d.querySelector('.tx-body > p').textContent, [...d.querySelectorAll('.tx-body tbody tr')].map(r => [...r.children].map(c => c.textContent))]; })()")
    assert opened[0] and not opened[1] and '담당자' in opened[2] and 'user:me' not in opened[2], opened[:3]
    diff = {r[0]: r[1:] for r in opened[3]}
    assert diff['수량'] == ['6', '5'] and diff['조치 방법'] == ['대체 승인 공급사 발주', '–'] and diff['불량률'] == ['–', '12 %'] and diff['요청한 사람'][0] not in ('user:me', '–'), diff
    assert not [k for k in diff if k.isascii()], list(diff)      # 영문 칸 이름이 남지 않는다
    page.click('#bzTabs [data-bz-view="now"]')
    # 정비 관리 표도 같은 칸으로 — 정비 시점이 보인다
    assert page.eval_on_selector_all('#sysBoards table tbody tr:first-child td', 'ns => ns.map(n => n.textContent)')[:5] == ['WO-1', 'HYD-01', '팬 최대 운전', '야간 정비 시간 11-14 19:00', '배정됨']


SCEN_B = {'key': 'B', 'asset': 'HYD-02', 'pattern': 'PM_DUE', 'label': '정기 점검 도래', 'button': '정기 정비 시작', 'title': '정기 정비', 'alert': True,
          'facts': {'pm_since_h': 1950, 'pm_interval_h': 2000, 'pm_due_in_h': 50}, 'running': None, 'last': None, 'events': []}
SCEN_C = {'key': 'C', 'asset': 'HYD-03', 'pattern': 'SPARE_BELOW_MIN', 'label': '재고 보충 필요', 'button': '예비품 구매 시작', 'title': '예비품 구매', 'alert': True,
          'facts': {'part_no': 'P-PMP-SEAL', 'name': '펌프 축 씰 키트', 'available': 1, 'reorder_point': 2, 'need_qty': 6, 'on_order': 0}, 'running': None, 'last': None,
          'events': [{'act': 'delay', 'button': '공급사 납기 지연', 'enabled': False, 'why': '진행 중인 예비품 구매 처리 건이 없어 늦출 발주가 없습니다', 'path': '/api/scenario/C/delay'}]}

LAB_ROWS = '''() => [...document.querySelectorAll('#units .unit')].map(c => { const cb = c.getBoundingClientRect();
  const at = e => { const b = e.getBoundingClientRect(); return [Math.round(b.top - cb.top), Math.round(b.left - cb.left)]; };
  const kind = b => ({ degrade: '일으키기', 'biz-start': '일으키기', 'biz-event': '바깥 사건', restore: '되돌리기', 'biz-reset': '되돌리기' })[b.dataset.act];
  const btns = [...c.querySelectorAll('.lab-buttons > button')];
  return { asset: c.dataset.asset, top: Math.round(cb.top), height: Math.round(cb.height), buttons: btns.map(b => [kind(b), ...at(b)]), rows: new Set([...c.querySelectorAll('.lab-buttons > *')].map(b => at(b)[0])).size,
    lines: ['.card > header, :scope > header', '.lab-what', '.lab-fact', '.lab-buttons', '.lab-field > summary'].map(s => at(c.querySelector(s))[0]), fold: at(c.querySelector('.lab-field > summary')) }; })'''


def lab_world(w, **more):
    w.scen = {'scenarios': {'B': dict(SCEN_B, **more.get('B', {})), 'C': dict(SCEN_C, **more.get('C', {}))}, 'presses': {}, 'reset_button': '업무 데이터 초기화'}


def test_결함_시뮬레이션_카드_셋은_같은_종류의_단추가_같은_줄_같은_차례에_서고_줄_수가_같다(world):
    """사용자: 「업무데이터 초기화 등등은 일관성 있게 배치를 — 요소에 따라서 위치가 다르면 일관성 문제」. 바깥 사건 단추가 있는 HYD-03 카드만 단추가 두 줄이 되어
    [업무 데이터 초기화]의 자리가 카드마다 달랐다. 실제 브라우저에서 단추의 카드 안 자리로 잰다: 일으키기 · 되돌리기가 세 카드에서 같은 높이 · 같은 왼쪽 선에 서고,
    바깥 사건은 일으키기와 같은 줄의 둘째 칸에 서며(없는 카드는 그 자리가 빈다), 단추 줄 수와 카드 안의 줄 차례(머리 · 사건 이름 · 값 한 줄 · 단추 · 현장 패널)가 같다."""
    w, page = world, world.page
    lab_world(w)
    page.goto(w.base + '/index.html#/scenario')
    page.wait_for_selector("#units .unit[data-asset='HYD-03'] button[data-act='biz-event']")
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(300)

    def check(cards, rows):
        assert [c['asset'] for c in cards] == ['HYD-01', 'HYD-02', 'HYD-03']
        by = lambda c, kind: [b[1:] for b in c['buttons'] if b[0] == kind]
        assert [[b[0] for b in c['buttons']] for c in cards] == [['일으키기', '되돌리기'], ['일으키기', '되돌리기'], ['일으키기', '바깥 사건', '되돌리기']]      # 같은 차례(없는 것은 빠진다)
        for kind in ('일으키기', '되돌리기'):
            assert len({tuple(by(c, kind)[0]) for c in cards}) == 1, (kind, [by(c, kind) for c in cards])      # 카드 안 같은 높이 · 같은 왼쪽 선
        start, undo, event = by(cards[2], '일으키기')[0], by(cards[2], '되돌리기')[0], by(cards[2], '바깥 사건')[0]
        assert undo[0] > start[0] and undo[1] == start[1]                                               # 되돌리기는 일으키기 아랫줄의 같은 왼쪽 선
        assert [c['rows'] for c in cards] == [rows] * 3, [c['rows'] for c in cards]                         # 단추 줄 수가 세 카드에서 같다
        assert len({tuple(c['lines']) for c in cards}) == 1 and cards[0]['lines'] == sorted(cards[0]['lines']), [c['lines'] for c in cards]      # 줄의 차례와 높이가 같다
        return start, undo, event

    cards = page.evaluate(LAB_ROWS)
    start, undo, event = check(cards, 2)
    assert event[0] == start[0] and event[1] > start[1]                                                 # 바깥 사건은 일으키기와 같은 줄의 오른쪽 칸
    assert len({c['top'] for c in cards}) == 1 and len({c['height'] for c in cards}) == 1                   # 한 줄에 나란한 카드 셋은 높이가 같다
    # 카드가 좁아 단추 둘이 나란히 못 서는 폭: 단추가 한 칸으로 쌓여도 줄 수 · 차례가 같다(없는 바깥 사건의 자리는 빈 줄)
    page.set_viewport_size({'width': 1040, 'height': 900})
    try:
        page.wait_for_timeout(300)
        narrow = page.evaluate(LAB_ROWS)
        if len({c['top'] for c in narrow}) == 1:
            s2, u2, e2 = check(narrow, 3)
            assert s2[0] < e2[0] < u2[0] and s2[1] == e2[1] == u2[1]
            assert page.evaluate('document.documentElement.scrollWidth - innerWidth') <= 0
    finally:
        page.set_viewport_size({'width': 1440, 'height': 900})


def test_결함_시뮬레이션은_범위를_한_번만_말하고_단추의_도움말은_카드의_사건_이름과_값_줄을_덮지_않는다(world):
    """화면은 읽는 곳이 아니라 보고 누르는 곳이다: 「명령 관문을 거치지 않는다」는 화면에 한 번만 보이고, 설명 문단 대신 단추마다 도움말(올리거나 초점을 주면 나온다)이 있다.
    도움말은 단추 아래에 뜬다 — 위에 뜨면 카드의 사건 이름 · 값 줄을 덮는다. 설비의 큰 값(큰 유온 · 눈금 막대 · 값 세 칸)은 이 화면에 없다(실시간 모니터링 한 곳)."""
    w, page = world, world.page
    lab_world(w)
    page.goto(w.base + '/index.html#/scenario')
    page.wait_for_selector("#units .unit[data-asset='HYD-03'] button[data-act='biz-event']")
    page.evaluate('document.fonts.ready')
    for card in page.locator('#units .unit details').all():      # 접기를 모두 펴도 되풀이되지 않는다
        card.evaluate('d => { d.open = true; }')
    text = page.inner_text('#view-scenario')
    assert text.count('명령 관문을 거치지 않습니다') == 1
    assert page.locator('#units .unit-big, #units .gauge, #units .unit-grid').count() == 0
    # 카드에 늘 보이는 글은 사건 이름 한 줄과 그 사건이 보는 값 한 줄 — 문단이 없다
    assert page.eval_on_selector_all("#units .lab-what, #units .lab-fact", "ns => ns.length === 6 && ns.every(n => n.getBoundingClientRect().height <= 26)")
    assert page.inner_text("#units .unit[data-asset='HYD-01'] .lab-fact") == '유온 48.0 ℃ · 쿨러 성능 100 %'
    assert page.inner_text("#units .unit[data-asset='HYD-02'] .lab-fact") == '운전 시간 1950 h / 정비 주기 2000 h — 기한까지 50 h'
    assert page.inner_text("#units .unit[data-asset='HYD-01'] .repeat-guide") == ''      # 그 상황이 아니면 안내 줄이 없다
    # 아래 고정 줄(처리 건으로 가는 길)은 진행 중인 처리 건이 있는 카드에만 나타난다 — 「열린 처리 건 없음」으로 빈 자리를 지키지 않는다
    assert page.eval_on_selector_all('#units .unit > footer', 'fs => fs.length === 3 && fs.every(f => f.getBoundingClientRect().height === 0)') and '열린 처리 건 없음' not in text
    # 도움말: 주입 단추에 초점을 주면(키보드로도 닿는다) 그 단추가 하는 일이 단추 아래에 뜬다 — 카드의 머리 줄 · 사건 이름 · 값 줄과 겹치지 않는다
    button = "#units .unit[data-asset='HYD-01'] button[data-act='degrade']"
    tip = page.get_attribute(button, 'data-tooltip')
    assert tip and '경보' in tip
    page.focus(button)
    page.keyboard.press('Shift+Tab'); page.keyboard.press('Tab')      # 키보드로 옮겨 온 초점
    assert page.evaluate("sel => document.activeElement === document.querySelector(sel) && document.activeElement.matches(':focus-visible')", button)
    page.wait_for_timeout(500)                                          # 도움말이 나타나는 움직임(0.15초)이 끝난 뒤에 잰다
    shown = page.evaluate("""sel => { const b = document.querySelector(sel), s = getComputedStyle(b, '::before'), r = b.getBoundingClientRect(), card = b.closest('.unit');
      const top = r.top + parseFloat(s.top), box = [r.left + parseFloat(s.left), top, r.left + parseFloat(s.left) + parseFloat(s.width), top + parseFloat(s.height)];
      const lines = [...card.querySelectorAll(':scope > header, .lab-what, .lab-fact')].map(n => { const q = n.getBoundingClientRect(); return [q.left, q.top, q.right, q.bottom]; });
      return { content: s.content, visibility: s.visibility, opacity: s.opacity, box, below: top >= r.top + r.height / 2, covers: lines.filter(q => q[0] < box[2] && box[0] < q[2] && q[1] < box[3] && box[1] < q[3]).length }; }""", button)
    assert tip in shown['content'] and shown['visibility'] == 'visible' and float(shown['opacity']) > 0, shown
    assert shown['below'] and shown['covers'] == 0, shown
    assert page.eval_on_selector_all('#units .lab-buttons [data-tooltip]', "bs => bs.every(b => b.dataset.side === 'bottom')")
    # 결함이 걸린 채 새 경보가 나지 않는 상황이 되면 그때만 한 줄
    w.units['HYD-01'] = unit('HYD-01', ts1=50.0, health=0.55)
    page.wait_for_function("document.querySelector(\"#units .unit[data-asset='HYD-01'] .repeat-guide\").textContent.includes('쿨러 복구')", timeout=8000)
    assert page.inner_text("#units .unit[data-asset='HYD-01'] .lab-fact") == '유온 50.0 ℃ · 쿨러 성능 55 %'
    # 설비 초기화는 화면 머리의 더 보기(「…」) 안에 있다 — 누르면 먼저 묻는다
    assert not page.is_visible('#btnReset')
    page.click('#scenarioHeadMore-trigger'); page.click('#btnReset')
    page.wait_for_selector('dialog.confirm-dialog[open] button[value=ok]', state='attached')
    assert '설비 3기를 정상 운전점으로' in page.inner_text('dialog.confirm-dialog[open] form')


def test_진행_중인_처리_건이_있는_업무_사건의_시작_단추는_꺼져_있고_서버가_겹쳐_열기를_거절하면_그_처리_건으로_가는_길을_준다(world):
    """한 바퀴 23: 정기 정비 처리 건이 진행 중인데 [정기 정비 시작]이 켜져 있어 누르면 409 가 났다. 누를 수 없으면 꺼 두고 까닭을 한 줄로 말하며,
    그 건으로 가는 길(카드 아래 고정 줄 「처리 건에서 보기」)을 둔다. 화면이 아직 모르는 사이에 눌러 서버가 409 로 거절하면, 까닭 옆에 그 처리 건으로 가는 링크가 붙는다."""
    w, page = world, world.page
    running = {'instance': 'c3_pm.1', 'status': 'RUNNING', 'started_at': '2026-11-14T00:08:43Z', 'ended_at': None, 'outcome': None}
    posts = []
    page.on('request', lambda r: posts.append(r.url) if r.method == 'POST' else None)
    lab_world(w, B={'running': running, 'last': running})
    page.goto(w.base + '/index.html#/scenario')
    start = page.locator("#units .unit[data-asset='HYD-02'] button[data-act='biz-start']")
    start.wait_for(timeout=8000)
    assert start.get_attribute('aria-disabled') == 'true' and '진행 중인 처리 건이 있어' in start.get_attribute('data-tooltip')
    go = page.locator("#units .unit[data-asset='HYD-02'] > footer .go")
    assert go.is_visible() and go.inner_text().strip() == '처리 건에서 보기' and go.get_attribute('data-open-inst') == 'c3_pm.1'      # 그 건으로 가는 길
    assert not page.locator("#units .unit[data-asset='HYD-03'] > footer").is_visible()                                            # 진행 중인 건이 없는 카드에는 그 줄이 없다
    # 아래 고정 줄이 있는 카드와 없는 카드에서 단추 · 현장 패널 접기의 높이가 같다
    cards = page.evaluate(LAB_ROWS)
    assert len({tuple(c['lines']) for c in cards}) == 1 and len({c['height'] for c in cards}) == 1, cards
    start.click(force=True)
    page.wait_for_function("document.querySelector('#scenarioMsg').textContent.includes('진행 중인 처리 건이 있어')", timeout=8000)
    assert not any('/api/scenario/B/start' in u for u in posts), posts                   # 서버에 409 를 받으러 가지 않는다
    # 화면이 아직 모를 때(다른 창에서 막 시작했다): 눌리고, 서버의 409 를 까닭 + 그 처리 건 링크로 보인다
    lab_world(w)
    w.conflict = {'detail': 'HYD-02 정기 정비 처리 건이 이미 진행 중입니다', 'instance': 'c3_pm.1', 'started_at': '2026-11-14T00:08:43Z'}
    page.wait_for_function("document.querySelector(\"#units .unit[data-asset='HYD-02'] button[data-act='biz-start']\").getAttribute('aria-disabled') !== 'true'", timeout=8000)
    page.click("#units .unit[data-asset='HYD-02'] button[data-act='biz-start']")
    page.wait_for_selector('#scenarioMsg a.go')
    assert '이미 진행 중입니다' in page.inner_text('#scenarioMsg') and page.get_attribute('#scenarioMsg', 'data-tone') == 'danger'
    assert page.get_attribute('#scenarioMsg a.go', 'href') == '#/instances/c3_pm.1' and page.inner_text('#scenarioMsg a.go').strip().endswith('처리 건에서 보기')
    page.click('#scenarioMsg a.go')
    page.wait_for_function("location.hash === '#/instances/c3_pm.1'")


def test_실시간_모니터링의_설비_카드는_열린_처리_건이_있을_때만_아래_줄을_갖는다(world):
    """「열린 처리 건 없음」 줄로 빈 자리를 지키지 않는다(상태일 때만 나타난다). 설비의 큰 값은 이 화면에 있다."""
    w, page = world, world.page
    w.incidents = [{'id': 'INC-b', 'asset': 'HYD-02', 'alertId': 'ALT-b', 'state': 'AWAITING_APPROVAL', 'terminal': False, 'created': '2026-01-01T01:00:00Z'}]
    page.goto(w.base + '/index.html#/trends')
    page.wait_for_selector("#monUnits .unit[data-asset='HYD-02'] > footer .go")
    page.wait_for_function("document.querySelector(\"#monUnits .unit[data-asset='HYD-02'] > footer\").getBoundingClientRect().height > 0", timeout=8000)
    feet = page.eval_on_selector_all('#monUnits .unit', "cs => Object.fromEntries(cs.map(c => [c.dataset.asset, c.querySelector(':scope > footer').getBoundingClientRect().height > 0]))")
    assert feet == {'HYD-01': False, 'HYD-02': True, 'HYD-03': False}
    assert page.get_attribute("#monUnits .unit[data-asset='HYD-02'] > footer .go", 'data-open-incident') == 'INC-b' and '열린 처리 건 없음' not in page.inner_text('#view-trends')
    big = page.eval_on_selector_all('#monUnits .unit-big', 'ns => ns.map(n => n.innerText.replace(/\\s+/g, ""))')
    assert big == ['48.0℃'] * 3 and page.locator('#monUnits .gauge').count() == 3
    tops = page.eval_on_selector_all('#monUnits .unit', "cs => cs.map(c => [Math.round(c.getBoundingClientRect().top), Math.round(c.querySelector('.unit-grid').getBoundingClientRect().top)])")
    assert len({tuple(t) for t in tops}) == 1, tops      # 아래 줄이 있는 카드와 없는 카드에서 값의 자리가 같다
    w.incidents = []
    page.wait_for_function("document.querySelector(\"#monUnits .unit[data-asset='HYD-02'] > footer\").getBoundingClientRect().height === 0", timeout=8000)


def test_오일_분석_입력은_폼_한_칸이고_보낸_결과가_폼_아래에_나오며_처리_건이_열리면_그리로_가는_길을_준다(world):
    """빈 오른쪽 결과 칸을 두지 않는다 — 결과는 보낸 뒤에만, 폼 바로 아래에 나타난다. 기준 이탈을 보내 처리 건이 열리면 결과 카드의 아래 고정 줄에 「처리 건에서 보기」가 있다."""
    w, page = world, world.page
    w.extra['/svc/process/api/human-alerts/form'] = {'assets': ['HYD-01', 'HYD-02', 'HYD-03'], 'patterns': [{'code': 'OIL_ANALYSIS', 'items': [{'key': 'tan', 'text': '산가 TAN', 'unit': 'mgKOH/g'}, {'key': 'water', 'text': '수분', 'unit': 'ppm'}]}]}
    w.extra['/svc/process/api/users/me'] = {'id': 'user:me', 'name': '담당자', 'roles': []}
    errors = []
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'UI.toast' in m.text else None)
    page.goto(w.base + '/index.html#/oil')
    page.wait_for_selector('#oilSend')
    page.evaluate("window.hydInbox.me = () => ({ id: 'user:me', name: '담당자', roles: [] }); window.dispatchEvent(new Event('hyd:me'))")
    page.wait_for_function("!document.querySelector('#oilSend').disabled")
    # 폼 한 칸: 결과 자리(빈 상태 문단 · 오른쪽 칸)가 없고, 입력 칸의 왼쪽 선 · 폭이 같으며, 주 단추가 칸 맨 아래 칸 폭 가득이다
    assert page.locator('#oilView .oil-result, #oilView .empty, #oilView .io-out').count() == 0
    shape = page.evaluate("""() => { const f = document.querySelector('.oil-form').getBoundingClientRect(), R = e => e.getBoundingClientRect();
      const ins = [...document.querySelectorAll('.oil-form select, .oil-form input[type=number], .oil-form textarea')].map(R), b = R(document.querySelector('#oilSend'));
      return { lefts: new Set(ins.map(r => Math.round(r.left))).size, widths: new Set(ins.map(r => Math.round(r.width))).size, full: Math.abs(b.width - f.width) < 2, last: b.top > Math.max(...ins.map(r => r.bottom)), w: f.width }; }""")
    assert shape['lefts'] == 1 and shape['widths'] == 1 and shape['full'] and shape['last'] and shape['w'] <= 520, shape
    # 필수 칸을 비운 채 보내면 요청 없이 그 자리에 까닭
    page.click('#oilSend')
    assert '설비를 고르세요' in page.inner_text('.oil-why')
    page.select_option('#oilAsset', 'HYD-02'); page.select_option('#oilItem', 'tan'); page.check("input[name=oilOut][value='1']")
    w.oil = {'raised': True, 'reason': '산가 TAN 기준 이탈 — 센서 경보와 같은 경로로 경보를 보냈습니다', 'definition': {'name': '미지원 경보 현장 검토', 'version': '1.0'}, 'route': 'triage', 'route_text': '이 경보를 여는 배포 흐름이 없어 사람 검토로 갔습니다', 'instance': 'alert_triage.9'}
    page.click('#oilSend')
    page.wait_for_selector('.oil-result footer .go')
    out = page.evaluate("""() => { const f = document.querySelector('.oil-form').getBoundingClientRect(), r = document.querySelector('.oil-result').getBoundingClientRect(); return { below: r.top >= f.bottom, left: Math.round(r.left - f.left), w: Math.round(r.width - f.width) }; }""")
    assert out == {'below': True, 'left': 0, 'w': 0}, out
    assert '경보를 만들었습니다' in page.inner_text('.oil-result header') and '미지원 경보 현장 검토' in page.inner_text('.oil-result')
    assert w.sent_oil['asset'] == 'HYD-02' and w.sent_oil['out_of_spec'] is True and w.sent_oil['by'] == 'user:me'
    assert not errors, errors      # 보낸 뒤의 알림이 모르는 색 이름으로 콘솔 오류를 내지 않는다
    go = page.locator('.oil-result footer .go')
    assert go.inner_text().strip() == '처리 건에서 보기' and go.get_attribute('data-open-inst') == 'alert_triage.9'
    go.click()
    page.wait_for_function("state.tab === 'instances'")
    # 기준 안: 경보를 만들지 않았다는 결과가 같은 자리에, 가는 길 없이
    page.goto(w.base + '/index.html#/oil')
    page.wait_for_selector('#oilSend')
    page.evaluate("window.hydInbox.me = () => ({ id: 'user:me', name: '담당자', roles: [] }); window.dispatchEvent(new Event('hyd:me'))")
    page.select_option('#oilAsset', 'HYD-02'); page.select_option('#oilItem', 'tan'); page.check("input[name=oilOut][value='0']")
    w.oil = {'raised': False, 'reason': '산가 TAN이 기준 안이라 경보를 만들지 않았습니다'}
    page.click('#oilSend')
    page.wait_for_selector('.oil-result')
    assert '경보를 만들지 않았습니다' in page.inner_text('.oil-result header') and page.locator('.oil-result footer').count() == 0


def test_목록과_상세_조건과_결과는_같은_두_칸_뼈대다(world):
    """화면 정돈 6단계: 목록 + 상세(.split)와 조건 → 결과(.io)는 한 뼈대다 — 왼쪽 칸 │ 세로 선 하나 │ 오른쪽 칸. 화면마다 칸 폭 · 선의 자리가 같고, 칸을 상자(테두리)에 넣지 않는다.
    전에는 조건 칸만 테두리 상자(320px)였고 목록 화면은 선으로 가른 칸(340px)이라 같은 틀의 화면이 서로 다른 제품처럼 보였다."""
    w, page = world, world.page

    def frame(tab, sel):
        page.goto(w.base + f'/index.html#/{tab}')
        page.wait_for_selector(f'#view-{tab}.active {sel}')
        return page.evaluate("""sel => { const f = document.querySelector(sel), [a, b] = f.children, ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect(), ca = getComputedStyle(a), cb = getComputedStyle(b);
          const first = [...a.querySelectorAll('*')].find(n => n.getBoundingClientRect().height > 0) || a;      // 왼쪽 칸에서 처음 보이는 것(거르기 · 묶음 머리 · 목록 · 칸 이름 — 화면마다 다르다)
          return { left: Math.round(ra.left), split: Math.round(rb.left), line: cb.borderLeftWidth,
                   boxed: [ca.borderTopWidth, ca.borderRightWidth, ca.borderBottomWidth, ca.borderLeftWidth, cb.borderTopWidth, cb.borderRightWidth, cb.borderBottomWidth].some(x => x !== '0px'),
                   firstTop: Math.round(first.getBoundingClientRect().top - ra.top) }; }""", f'#view-{tab} {sel}')
    frames = [frame('skills', '.split'), frame('instances', '.split'), frame('decision', '.io')]
    assert len({(f['left'], f['split']) for f in frames}) == 1, frames      # 왼쪽 선과 세로 선의 자리가 세 화면에서 같다
    assert all(f['line'] == '1px' and not f['boxed'] for f in frames), frames
    assert all(f['firstTop'] == 0 for f in frames), str([f['firstTop'] for f in frames]) + ' '                # 왼쪽 칸의 첫 줄(거르기 · 칸 이름)이 칸 맨 위에서 시작한다
    # 좁은 폭에서는 두 칸이 위아래로 쌓이고 세로 선 대신 가로 선 하나
    page.set_viewport_size({'width': 900, 'height': 900})
    try:
        f = frame('decision', '.io')
        stacked = page.evaluate("() => { const [a, b] = document.querySelector('#view-decision .io').children; return b.getBoundingClientRect().top >= a.getBoundingClientRect().bottom && getComputedStyle(b).borderTopWidth === '1px'; }")
        assert stacked and f['line'] == '0px', f
    finally:
        page.set_viewport_size({'width': 1440, 'height': 900})
