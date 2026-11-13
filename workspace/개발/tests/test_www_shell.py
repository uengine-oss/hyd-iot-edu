"""포털의 뼈대(it/portal/www/index.html 주 메뉴 표 · app.js 메뉴 줄과 위 막대 · shell.js 주소와 화면 찾기) — 메뉴 여덟에 화면 22개가 딸리고, 화면은 어느 길로 열어도
그 화면이 든 메뉴가 펼쳐지고 그 화면이 고른 상태가 된다. 사건 한 건의 판단 · 승인 · 결과는 처리 건 화면 한 곳에만 있다(다른 화면에 사본 구역이 없다).

앞의 시험은 index.html 을 글로 읽고, 뒤의 시험은 실제 index.html 을 실제 브라우저(Playwright Chromium)로 연다. 서비스 요청(/svc/**)은 모두 끊는다 —
여기서 보는 것은 데이터가 아니라 메뉴 · 주소 · 화면 제목 · 화면 찾기다. 떠 있는 스택과 업무 DB 가 필요 없다."""
import re
from html.parser import HTMLParser

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

# 메뉴 여덟과 메뉴마다 딸린 화면(차례대로) — 스펙 「3-1」의 목표 메뉴. 화면 이름은 index.html 의 view-<이름> 이자 주소 #/<이름>
WANT = [('main', ['main']), ('instances', ['instances']), ('knowledge', ['ontology', 'skills', 'knowledge', 'fabric']), ('flows', ['flows']),
        ('agents', ['agents', 'mcp', 'ask']), ('plant', ['scenario', 'oil', 'trends', 'incidents', 'process']),
        ('trial', ['decision', 'whatif', 'eval', 'compare']), ('system', ['home', 'kpi', 'admin'])]
SCREENS = [tab for _, tabs in WANT for tab in tabs]


class _Page(HTMLParser):
    """index.html 에서 주 메뉴 표 · 화면 구역 · 요소 id 가 든 화면을 읽는다."""

    def __init__(self):
        super().__init__()
        self.in_nav, self.menus, self.views, self.view, self.where = False, [], [], None, {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'nav' and a.get('aria-label') == '주 메뉴':
            self.in_nav = True
        elif tag == 'button' and self.in_nav and 'data-menu' in a:
            self.menus.append((a['data-menu'], (a.get('data-tabs') or '').split()))
        if tag == 'section' and 'view' in (a.get('class') or '').split():
            self.view = a['id'][len('view-'):]
            self.views.append(self.view)
        if a.get('id'):
            self.where[a['id']] = self.view

    def handle_endtag(self, tag):
        if tag == 'nav':
            self.in_nav = False
        if tag == 'main':
            self.view = None


def problems(html):
    """주 메뉴 표와 화면 구역이 스펙의 구조와 어긋난 곳(없으면 빈 목록)."""
    p = _Page()
    p.feed(html)
    out = []
    if p.menus != WANT:
        out.append(f'주 메뉴 표가 다르다: {p.menus}')
    screens = [t for _, tabs in p.menus for t in tabs]
    if sorted(screens) != sorted(p.views):
        out.append(f'메뉴에 없는 화면 {sorted(set(p.views) - set(screens))} · 화면이 없는 메뉴 항목 {sorted(set(screens) - set(p.views))}')
    # 한 가지는 한 곳: 흐름을 경보에 쓰는 배포는 흐름 화면에, 내가 할 일과 알림은 처리 건 화면에
    # (내가 할 일은 처리 건 화면의 탭 줄 #instTabs 의 「내 할 일」 탭과 그 목록 #instList 다 — 따로 둔 #todoList 목록은 한 장 개편에서 없앴다)
    for el, view in [('definitionDeployPanel', 'flows'), ('flowsStart', 'flows'), ('instTabs', 'instances'), ('instList', 'instances'), ('noticeView', 'instances'),
                     ('sourceEventsPanel', 'admin'), ('definitionEditor', 'admin'), ('configBundlePanel', 'admin'), ('sysBoards', 'process'), ('txList', 'process'), ('scada', 'incidents')]:
        if p.where.get(el) != view:
            out.append(f'#{el} 은(는) {view} 화면에 있어야 한다 — 지금 {p.where.get(el)}')
    # 처리 건 화면의 사본이던 구역: 조치 후보 카드(설비 회로) · 처리 건 흐름 그림(업무 시스템 기록) · 옛 내 작업함 화면
    for el in ('hitlPanel', 'procBpmn', 'inboxView', 'todoList'):
        if el in p.where:
            out.append(f'#{el} 구역이 남아 있다({p.where[el]} 화면) — 처리 건 화면의 사본이다')
    return out


INDEX = (WWW / 'index.html').read_text(encoding='utf8')


def test_주_메뉴는_여덟이고_화면_22개가_빠짐없이_딸려_있다():
    assert len(SCREENS) == 22 and problems(INDEX) == []


@pytest.mark.parametrize('broken, said', [
    (lambda h: h.replace('data-tabs="agents mcp ask"', 'data-tabs="agents mcp"'), "메뉴에 없는 화면 ['ask']"),          # 화면 하나가 메뉴에서 빠짐 — 갈 길이 없는 화면
    (lambda h: h.replace('id="noticeView"', 'id="noticeGone"'), '#noticeView 은(는) instances 화면에 있어야 한다'),          # 알림 자리가 처리 건 화면에서 사라짐
    (lambda h: h.replace('<div class="scada" id="scada"></div>', '<div class="scada" id="scada"></div><div id="hitlPanel"></div>'), '#hitlPanel 구역이 남아 있다'),
])
def test_구조가_어긋나면_잡는다(broken, said):
    """위 판정을 일부러 깨뜨려 본다 — 잡지 못하면 없는 검사다."""
    html = broken(INDEX)
    assert html != INDEX, '깨뜨릴 자리를 찾지 못했다(index.html 이 바뀌었다 — 이 시험의 바꿔치기 글을 맞춘다)'
    assert any(said in line for line in problems(html)), problems(html)


@pytest.fixture(scope='module')
def portal():
    """서비스 없이 화면 파일만 낸 포털 한 탭. 이 파일이 끝나면 브라우저를 닫는다(뒤 시험에 이벤트 루프를 남기지 않게 — test_portal_ui 와 같은 까닭)."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1366, 'height': 768})
            page.route('**/svc/**', lambda route: route.abort('connectionrefused'))
            page.goto(served.url + '/index.html')
            page.wait_for_function('() => window.hydShell && window.hydMenu')
            yield page
            b.close()
    finally:
        served.close()


def chosen(page):
    """메뉴 줄이 지금 보여 주는 것: 고른 메뉴(menu) · 펼쳐진 메뉴(open) · 그 안에 보이는 화면 줄(tabs) · 그 가운데 고른 화면(on)."""
    return page.evaluate("""() => ({ tab: state.tab,
      menu: [...document.querySelectorAll('#menuList [data-menu]')].filter(n => n.matches('a[aria-current=page], summary[data-active=true]')).map(n => n.dataset.menu),
      open: [...document.querySelectorAll('#menuList details[open] > summary')].map(s => s.dataset.menu),
      on: [...document.querySelectorAll('#menuList ul ul a[aria-current=page]')].map(a => a.dataset.tab),
      tabs: [...document.querySelectorAll('#menuList details[open] ul a[data-tab]')].map(a => a.dataset.tab),
      view: [...document.querySelectorAll('main .view.active')].map(v => v.id), hash: location.hash })""")


def expect(page, menu, tab):
    tabs = dict(WANT)[menu]
    many = len(tabs) > 1
    assert chosen(page) == {'tab': tab, 'menu': [menu], 'open': [menu] if many else [], 'on': [tab] if many else [], 'tabs': tabs if many else [],
                            'view': [f'view-{tab}'], 'hash': f'#/{tab}'}


@pytest.mark.parametrize('menu, tab', [(m, t) for m, tabs in WANT for t in tabs])
def test_화면을_함수_주소_단추_어느_길로_열어도_그_메뉴가_펼쳐지고_그_화면이_고른_상태가_된다(portal, menu, tab):
    page = portal
    away = 'main' if tab != 'main' else 'home'
    page.evaluate('([t]) => selectTab(t)', [tab])                       # 화면 코드가 부르는 길
    expect(page, menu, tab)
    page.evaluate('([t]) => selectTab(t)', [away])
    page.evaluate("([t]) => { location.hash = '#/' + t; }", [tab])        # 주소(링크 · 새로 고침 · 뒤로 가기)
    page.wait_for_function('t => state.tab === t', arg=tab)
    expect(page, menu, tab)
    page.evaluate('([t]) => selectTab(t)', [away])
    page.evaluate("""([t]) => { const b = Object.assign(document.createElement('button'), { id: 'goProbe' }); b.dataset.goTab = t; document.body.append(b); b.click(); b.remove(); }""", [tab])   # 화면 안의 [data-go-tab] 단추
    expect(page, menu, tab)
    page.evaluate('([t]) => selectTab(t)', [away])
    open_screen(page, tab)                                               # 학생이 누르는 길: 메뉴 줄에서 메뉴를 펼치고 그 화면을 누른다
    expect(page, menu, tab)


# 화면 제목(h1)은 메뉴 줄의 화면 이름(ui.js nav.<화면>)과 같고 화면마다 하나다 — 제목을 스스로 그리는 화면 모듈(agents · mcp · eval · kpi)도 같다
@pytest.mark.parametrize('tab', SCREENS)
def test_화면_제목은_메뉴_줄의_이름과_같고_하나뿐이다(portal, tab):
    page = portal
    open_screen(page, tab)
    page.wait_for_function("t => [...document.querySelectorAll(`#view-${t} h1`)].some(h => h.checkVisibility())", arg=tab, timeout=15000)
    titles = page.eval_on_selector_all(f'#view-{tab} h1', 'hs => hs.filter(h => h.checkVisibility()).map(h => h.textContent.trim())')
    assert titles == [page.evaluate('t => hydMenu.name(t)', tab)]
    assert page.inner_text('#pageLocation') == titles[0]


def test_위_막대에는_접기와_위치와_연결_상태와_화면_찾기와_알림_종만_있고_나머지는_메뉴_줄에_있다(portal):
    """틀(디자인 기준 3절): 위 막대에는 메뉴 줄 접기 · 위치(메뉴 › 화면) · 실시간 연결 상태 · 화면 찾기 · 알림 종만 있다. 서비스 상태와 배속 · 지금 단계는 메뉴 줄 맨 아래에,
    내 할 일 건수는 메뉴 「처리 건」 곁에 있다. 본문 위의 탭 줄은 없고(화면은 메뉴 줄에서 고른다), 화면의 차례는 메뉴 표(hydMenu.screens)가 갖는다."""
    page = portal
    assert page.evaluate('() => hydMenu.screens') == SCREENS
    assert page.locator('#subTabs, .page-navigation, #pagePrev, #pageNext, #pagePosition').count() == 0
    shown = "ns => ns.filter(n => n.checkVisibility() && !n.matches('.topbar-space')).map(n => n.id || n.className)"      # .topbar-space 는 사이를 벌리는 빈 칸이다
    assert page.eval_on_selector_all('.topbar > *', shown) == ['railToggle', 'crumb', 'streamTicker', 'kbarOpen', 'shellBell']
    assert page.locator('#simT, #openCount, .topbar #healthDots, .topbar #courseStatus, .topbar #scale').count() == 0
    page.evaluate("() => selectTab('skills')")
    assert page.inner_text('.crumb').split() == ['지식', '조치', '방법']          # 메뉴 › 화면 — 사이의 꺾쇠는 그림이라 글에 없다
    assert page.title() == '조치 방법 · HYD'
    page.evaluate("() => selectTab('main')")
    assert page.inner_text('.crumb').strip() == '홈'                                  # 화면이 하나뿐인 메뉴는 화면 이름만
    assert page.eval_on_selector_all('#sidebar > nav > footer > *', "ns => ns.map(n => n.id)") == ['courseStatus', 'railStatus']
    assert page.locator("#menuList a[data-menu='instances'] #navTodo").count() == 1
    # 이 포털은 서비스 요청(/svc/**)이 모두 끊겨 있다 — 메뉴 줄 맨 아래 한 줄이 「n개 응답 없음」과 점의 색(초록이 아님 · 살아 있는 점이 아님)으로 그 사실을 말하고,
    # 누르면 시스템 구성으로 간다. 내 할 일 수를 못 읽었으면 건수 점은 0(빈 점)이 아니라 「?」다
    page.wait_for_function("() => /응답 없음/.test(document.getElementById('healthDots').textContent)", timeout=20000)
    up, total, down = map(int, re.fullmatch(r'서비스 (\d+)/(\d+) · (\d+)개 응답 없음', page.inner_text('#healthDots').strip()).groups())
    assert down > 0 and up + down == total
    assert page.evaluate("() => [healthDot.dataset.tone, healthDot.hasAttribute('data-live')]") == ['warn' if up else 'danger', False]
    assert '응답 없음: ' in page.get_attribute('#railStatus', 'title')
    page.wait_for_function("() => document.getElementById('navTodo').textContent === '?'", timeout=20000)
    assert '읽지 못했습니다' in page.get_attribute("#menuList a[data-menu='instances']", 'title')
    page.click('#railStatus')
    assert page.evaluate('() => state.tab') == 'home'


def test_메뉴는_고른_것만_펼쳐지고_다른_메뉴를_펼치면_앞의_것이_접힌다(portal):
    """화면이 여럿인 메뉴의 이름 줄을 누르면 그 메뉴만 펼쳐져 안의 화면이 보인다(화면은 바뀌지 않는다). 화면을 고르면 그 화면의 메뉴가 펼쳐진 채 남는다."""
    page = portal
    page.evaluate("() => selectTab('skills')")
    assert chosen(page)['open'] == ['knowledge']
    page.click("#menuList summary[data-menu='agents']")
    seen = chosen(page)
    assert (seen['tab'], seen['open'], seen['tabs'], seen['menu']) == ('skills', ['agents'], ['agents', 'mcp', 'ask'], ['knowledge'])
    page.click("#menuList a[data-tab='mcp']")
    expect(page, 'agents', 'mcp')


def test_메뉴_줄을_접으면_아이콘만_남고_아이콘을_누르면_그_메뉴의_화면이_열린다(portal):
    """위 막대 첫 단추로 메뉴 줄을 접는다(폭 56px, 고른 값은 브라우저에 남는다). 접힌 채로는 안의 화면 목록이 보이지 않으므로 아이콘을 누르면 그 메뉴에서
    마지막으로 본 화면(없으면 첫 화면)이 열린다. 다시 누르면 펴진다."""
    page = portal
    page.evaluate("() => { selectTab('compare'); selectTab('main'); }")
    page.click('#railToggle')
    try:
        page.wait_for_function("() => Math.round(document.querySelector('#sidebar > nav').getBoundingClientRect().width) === 56")
        assert page.evaluate("() => [document.documentElement.dataset.rail, localStorage.getItem('hyd.rail'), railToggle.getAttribute('aria-expanded')]") == ['mini', 'mini', 'false']
        assert page.eval_on_selector_all('#menuList ul ul a, #menuList a > span, #menuList summary > span', 'ns => ns.filter(n => n.checkVisibility()).length') == 0
        page.click("#menuList summary[data-menu='trial']")
        assert page.evaluate('() => state.tab') == 'compare'              # 그 메뉴에서 마지막으로 본 화면
        page.click("#menuList summary[data-menu='system']")
        assert page.evaluate('() => state.tab') == 'home'                 # 본 적이 없으면 첫 화면
    finally:
        page.click('#railToggle')
    assert page.evaluate("() => [document.documentElement.dataset.rail || '', localStorage.getItem('hyd.rail')]") == ['', 'full']
    page.locator("#menuList a[data-tab='kpi']").wait_for(state='visible', timeout=3000)      # 펴면 펼쳐진 메뉴 안의 화면 이름이 다시 보인다


def test_화면_찾기는_Ctrl_K로_열고_이름으로_걸러_Enter로_그_화면에_간다(portal):
    """화면 찾기(shell.js — 키트의 명령 팔레트): 화면 22개가 메뉴 표 그대로 들어 있고, 이름(띄어쓰기를 빼고 적어도)으로 걸러 Enter 로 간다. 맞는 것이 없으면 그렇게 말한다."""
    page = portal
    page.evaluate("() => selectTab('main')")
    left = "() => [...document.querySelectorAll('#kbarMenu [role=menuitem]')].filter(n => n.getAttribute('aria-hidden') !== 'true').map(n => n.dataset.tab)"
    page.keyboard.press('Control+k')
    page.wait_for_function("() => document.getElementById('kbar').open && document.activeElement.id === 'kbarInput'")
    assert page.evaluate(left) == SCREENS
    page.keyboard.type('지식지도')                                        # 「지식 지도」를 붙여 적어도 찾는다
    assert page.evaluate(left) == ['ontology']
    page.fill('#kbarInput', '없는 화면 이름')
    assert page.evaluate(left) == [] and page.get_attribute('#kbarMenu', 'data-empty') == '맞는 화면이 없습니다.'
    page.fill('#kbarInput', '채점')
    assert page.evaluate(left) == ['eval']
    page.keyboard.press('Enter')
    page.wait_for_function("() => state.tab === 'eval'")
    assert page.evaluate("() => document.getElementById('kbar').open") is False
    expect(page, 'trial', 'eval')
    page.click('#kbarOpen')                                               # 위 막대의 단추로도 열린다 — 지난번에 거른 글은 남지 않는다
    page.wait_for_function("() => document.getElementById('kbar').open")
    assert page.input_value('#kbarInput') == '' and page.evaluate(left) == SCREENS
    page.keyboard.press('Escape')
    page.wait_for_function("() => !document.getElementById('kbar').open")


def test_옛_내_작업함_주소는_처리_건_화면으로_가고_종은_그_화면의_알림을_편다(portal):
    page = portal
    page.evaluate("() => { selectTab('main'); location.hash = '#/inbox'; }")
    page.wait_for_function("() => state.tab === 'instances' && location.hash.startsWith('#/instances')")
    assert page.locator('#view-inbox').count() == 0 and page.locator("#menuList [data-menu='inbox'], #menuList [data-tab='inbox']").count() == 0
    page.evaluate("() => selectTab('main')")
    assert page.evaluate("() => document.getElementById('noticeFold').open") is False
    page.click('#shellBell')
    assert page.evaluate("() => [state.tab, document.getElementById('noticeFold').open]") == ['instances', True]


def test_판단_실험_화면들에만_위치_옆에_안내_한_문장이_보인다(portal):
    page = portal
    notes = {}
    for tab in SCREENS:
        page.evaluate('([t]) => selectTab(t)', [tab])
        notes[tab] = page.inner_text('#menuNote') if page.is_visible('#menuNote') else ''
    said = '판단 엔진에 조건을 넣어 결과를 미리 봅니다.'
    assert notes == {tab: (said if tab in dict(WANT)['trial'] else '') for tab in SCREENS}
