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

# 메뉴 여덟과 메뉴마다 딸린 화면(차례대로) — 이야기 차례(UIUX_PLAN.md 0절: 지식을 넣는다 → 사건이 생긴다 → AI가 판단하고 사람이 승인하고 결과가 남는다 → 내 것으로 바꾼다 → 시험한다 → 바탕).
# 화면 이름은 index.html 의 view-<이름> 이자 주소 #/<이름>
WANT = [('main', ['main']), ('knowledge', ['knowledge', 'ontology', 'skills', 'fabric']), ('plant', ['scenario', 'oil', 'trends', 'incidents', 'process']),
        ('instances', ['instances']), ('flows', ['flows']), ('agents', ['agents', 'mcp', 'ask']),
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
    # (내가 할 일은 처리 건 화면의 목록 #instList 의 「내 차례」 묶음이다 — 따로 둔 #todoList 목록과 거르기 줄 #instTabs 는 없앴다)
    for el, view in [('definitionDeployPanel', 'flows'), ('flowsStart', 'flows'), ('instList', 'instances'), ('noticeView', 'instances'),
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
    (lambda h: h.replace('<div id="incList" aria-live="polite"></div>', '<div id="incList" aria-live="polite"></div><div id="hitlPanel"></div>'), '#hitlPanel 구역이 남아 있다'),
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


# 메뉴 줄이 접힌 상태가 자리를 잡았다: html[data-rail=mini] 이고, 접는 움직임이 끝났고, 메뉴 줄의 폭이 아이콘 하나가 들어갈 만큼(아이콘 폭의 네 배 안쪽)이다
MINI = """() => { const nav = document.querySelector('#sidebar > nav'), ic = document.querySelector("#menuList [data-menu='main'] > svg").getBoundingClientRect();
          return document.documentElement.dataset.rail === 'mini' && !document.getAnimations().some(a => a.effect && a.effect.target && a.effect.target.closest('#sidebar'))
            && nav.getBoundingClientRect().width < 4 * ic.width; }"""


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
    # 제목이 보이는 그 순간에 읽는다 — 화면 모듈이 머리를 다시 그리는 사이(에이전트 · 성과 지표는 읽기에 실패하면 머리째 다시 그린다)에 읽으면 제목이 없는 순간이 잡힌다
    seen = "t => { const hs = [...document.querySelectorAll(`#view-${t} h1`)].filter(h => h.checkVisibility()).map(h => h.textContent.trim()); return hs.length ? hs : null; }"
    titles = page.wait_for_function(seen, arg=tab, timeout=15000).json_value()
    assert titles == [page.evaluate('t => hydMenu.name(t)', tab)]
    assert page.inner_text('#pageLocation') == titles[0]


def test_위_막대에는_접기와_위치와_연결_상태와_화면_찾기와_알림_종만_있고_나머지는_메뉴_줄에_있다(portal):
    """셸(디자인기준 3-1): 위 막대에는 메뉴 줄 접기 │ 세로 선 │ 위치(메뉴 › 화면) … 실시간 점 · 화면 찾기 · 알림 종만 있다. 서비스 상태와 배속 · 지금 단계는 메뉴 줄 맨 아래에,
    내 할 일 건수는 메뉴 「처리 건」 곁에 있다. 본문 위의 탭 줄은 없고(화면은 메뉴 줄에서 고른다), 화면의 차례는 메뉴 표(hydMenu.screens)가 갖는다."""
    page = portal
    assert page.evaluate('() => hydMenu.screens') == SCREENS
    assert page.locator('#subTabs, .page-navigation, #pagePrev, #pageNext, #pagePosition').count() == 0
    shown = "ns => ns.filter(n => n.checkVisibility() && !n.matches('.topbar-space')).map(n => n.id || n.className)"      # .topbar-space 는 사이를 벌리는 빈 칸이다
    for tab in ('main', 'decision', 'instances'):                                    # 어느 메뉴의 화면에서도 위 막대에 놓이는 것은 이 다섯(과 접기 단추 뒤의 세로 선)뿐이다(메뉴마다 붙는 안내 문장 같은 것이 없다)
        page.evaluate('([t]) => selectTab(t)', [tab])
        assert page.eval_on_selector_all('.topbar > *', shown) == ['railToggle', 'topbar-sep', 'crumb', 'streamTicker', 'kbarOpen', 'shellBell'], tab
    assert page.locator('#simT, #openCount, .topbar #healthDots, .topbar #courseStatus, .topbar #scale').count() == 0
    page.evaluate("() => selectTab('skills')")
    assert page.inner_text('.crumb').split() == ['지식', '조치', '방법']          # 메뉴 › 화면 — 사이의 꺾쇠는 그림이라 글에 없다
    assert page.title() == '조치 방법 · HYD 포털'
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
    """위 막대 첫 단추로 메뉴 줄을 접는다(아이콘 열만 남는 폭, 고른 값은 브라우저에 남는다). 접힌 채로는 안의 화면 목록이 보이지 않으므로 아이콘을 누르면 그 메뉴에서
    마지막으로 본 화면(없으면 첫 화면)이 열린다. 다시 누르면 펴진다. 단추의 이름은 누르면 일어날 일을 말한다(펴져 있으면 「접기」, 접혀 있으면 「펴기」)."""
    page = portal
    page.evaluate("() => { selectTab('compare'); selectTab('main'); }")
    assert page.get_attribute('#railToggle', 'aria-label') == '메뉴 줄 접기'
    page.click('#railToggle')
    try:
        page.wait_for_function(MINI)                     # 접힌 메뉴 줄은 아이콘 하나가 들어갈 폭이다(아이콘 폭의 네 배 안쪽)
        assert page.evaluate("() => [document.documentElement.dataset.rail, localStorage.getItem('hyd.rail'), railToggle.getAttribute('aria-label')]") == ['mini', 'mini', '메뉴 줄 펴기']
        assert page.eval_on_selector_all('#menuList ul ul a, #menuList a > span, #menuList summary > span', 'ns => ns.filter(n => n.checkVisibility()).length') == 0
        page.click("#menuList summary[data-menu='trial']")
        assert page.evaluate('() => state.tab') == 'compare'              # 그 메뉴에서 마지막으로 본 화면
        page.click("#menuList summary[data-menu='system']")
        assert page.evaluate('() => state.tab') == 'home'                 # 본 적이 없으면 첫 화면
    finally:
        page.click('#railToggle')
    assert page.evaluate("() => [document.documentElement.dataset.rail || '', localStorage.getItem('hyd.rail'), railToggle.getAttribute('aria-label')]") == ['', 'full', '메뉴 줄 접기']
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


def test_상표의_마크는_메뉴_아이콘_열과_왼쪽_선이_같고_이름은_한_줄이다(portal):
    """왼쪽 위 상표(디자인기준 3-1): 마크는 24~28px 이고 그 왼쪽 선이 아래 메뉴 항목의 아이콘 열과 같다. 제품 이름은 한 줄이고 부제 줄이 없다.
    상표 줄의 높이는 위 막대와 같아 두 줄의 아랫선이 한 선으로 이어진다. 메뉴 줄을 접어도 마크는 아이콘 열의 가운데에 남는다."""
    page = portal
    page.evaluate("() => selectTab('main')")
    settled = "() => !document.getAnimations().some(a => a.effect && a.effect.target && a.effect.target.closest('#sidebar'))"      # 메뉴 줄을 접고 펴는 움직임(0.2초)이 끝난 뒤에 잰다
    page.wait_for_function(settled)
    box = "s => { const r = document.querySelector(s).getBoundingClientRect(); return { left: r.left, top: r.top, w: r.width, h: r.height, mid: r.left + r.width / 2, bottom: r.bottom }; }"
    mark, icon, name = (page.evaluate(box, s) for s in ('#brandHome .brand-mark', "#menuList a[data-tab='main'] > svg", '#brandHome .brand-name'))
    assert abs(mark['left'] - icon['left']) < 0.5, (mark, icon)
    assert 24 <= mark['w'] <= 28 and mark['w'] == mark['h']
    line = page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('#brandHome .brand-name')).lineHeight)")
    assert name['h'] <= line + 0.5, '제품 이름이 두 줄로 놓였다'
    assert page.eval_on_selector_all('#brandHome > *', 'ns => ns.filter(n => n.checkVisibility()).length') == 2          # 마크와 이름뿐 — 부제 줄이 없다
    assert abs(page.evaluate(box, '#sidebar > nav > header')['bottom'] - page.evaluate(box, '.topbar')['bottom']) <= 1
    page.click('#brandHome')
    assert page.evaluate("() => [state.tab, document.querySelectorAll('#sidebar a[aria-current=page]').length]") == ['main', 1]      # 상표는 홈으로 가는 링크이고 메뉴 항목이 아니다
    page.click('#railToggle')
    try:
        page.wait_for_function(MINI)
        page.wait_for_function(settled)
        mark, icon = (page.evaluate(box, s) for s in ('#brandHome .brand-mark', "#menuList a[data-tab='main'] > svg"))
        assert abs(mark['mid'] - icon['mid']) < 0.5 and page.is_visible('#brandHome .brand-name') is False
    finally:
        page.click('#railToggle')


def test_실시간_점은_연결_상태만_말하고_다시_이어지면_연결됨으로_돌아온다(portal):
    """위 막대의 실시간 점(liveStream.js paintTicker): 점과 그 이름표(마우스를 올리면 뜨는 글)는 실시간 연결 상태만 말한다 — 활동을 받아도 그 이름으로 바뀌지 않고, 받은 활동은 누르면 펼쳐지는 판에 있다.
    끊긴 뒤 활동을 한 번이라도 받았던 화면도 다시 이어지면 「실시간 연결됨」(살아 있는 초록 점)으로 돌아온다(앞 판은 다음 활동이 올 때까지 「끊김」이 남았다)."""
    page = portal
    pill = """() => { const t = document.getElementById('streamTicker'), d = t.querySelector('summary .dot');
      return { text: t.querySelector('summary > span').textContent.trim(), tone: d.dataset.tone || '', live: d.hasAttribute('data-live'), detail: t.querySelector('.ticker-detail').textContent }; }"""
    page.wait_for_function("() => ['retry', 'off'].includes(hydStream.conn().state)", timeout=20000)      # 이 포털은 서비스 요청이 모두 끊겨 있다
    down = page.evaluate(pill)
    assert down['text'] == page.evaluate('() => hydStream.conn().text') and down['text'] in ('다시 연결 중', '끊김 · 다시 연결을 시도하는 중') and down['live'] is False
    page.evaluate("() => hydStream.push({ id: 'pill-probe', event_type: 'human_asked', timestamp: new Date().toISOString(), data: { text: '팬 속도를 올려도 됩니까?' } }, true)")
    got = page.evaluate(pill)
    assert (got['text'], got['live']) == (down['text'], False)                    # 점과 그 이름표는 연결 상태 그대로
    assert '사람에게 질문' in got['detail'] and '팬 속도를 올려도 됩니까?' in got['detail'] and got['detail'].count('사람에게 질문') == 1
    # 실시간 통로만 이어 준다: 이어진 순간의 알약을 적어 둔다(이 대역은 답을 보내고 곧 끊으므로 그 뒤에는 다시 「다시 연결 중」이 된다)
    page.evaluate(f"() => {{ window.pillSeen = []; hydStream.onConn(c => window.pillSeen.push([c.state, ({pill})()])); }}")
    stream = '**/svc/process/api/events/stream**'
    page.route(stream, lambda route: route.fulfill(status=200, content_type='text/event-stream', body=': 이어짐\n\n'))
    try:
        page.evaluate('() => hydStream.connect()')
        page.wait_for_function("() => window.pillSeen.some(([s]) => s === 'on')", timeout=20000)
    finally:
        page.unroute(stream)
    on = next(seen for state, seen in page.evaluate('() => window.pillSeen') if state == 'on')
    assert (on['text'], on['tone'], on['live']) == ('실시간 연결됨', 'ok', True)
    assert '팬 속도를 올려도 됩니까?' in on['detail']                              # 받은 활동은 펼친 판에 남아 있다


def test_처리_건_곁의_건수는_내_차례인_처리_건_수이고_없으면_그리지_않는다(portal):
    """메뉴 「처리 건」 곁의 동그라미(app.js refreshTodoCount): 사람 단계가 열렸거나 AI 에이전트가 질문한 처리 건을 건 단위로 센다(한 건에 단계가 둘이어도 1).
    AI 에이전트나 시스템이 일하는 중인 건은 세지 않는다. 0 이면 동그라미를 그리지 않는다."""
    page = portal
    todo = '**/svc/process/api/todolist**'
    rows = [{'proc_inst_id': 'inst-a', 'agent_orch': None, 'agent_mode': None},                                      # 사람 단계
            {'proc_inst_id': 'inst-a', 'agent_orch': None, 'agent_mode': None},                                      # 같은 건의 사람 단계 하나 더
            {'proc_inst_id': 'inst-b', 'agent_orch': 'cliagents', 'agent_mode': 'draft', 'draft_status': 'HUMAN_ASKED'},   # AI 에이전트가 사람에게 물은 건
            {'proc_inst_id': 'inst-c', 'agent_orch': 'cliagents', 'agent_mode': 'draft', 'draft_status': 'STARTED'},       # AI 에이전트가 일하는 중
            {'proc_inst_id': 'inst-d', 'agent_orch': 'service', 'agent_mode': None}]                                 # 시스템 단계
    seen = "() => { const n = document.getElementById('navTodo'); return [n.textContent, n.getAttribute('aria-label'), n.checkVisibility()]; }"
    try:
        page.route(todo, lambda route: route.fulfill(json=rows))
        page.evaluate('() => refreshTodoCount()')
        assert page.evaluate(seen) == ['2', '내가 할 일 2건', True]
        page.unroute(todo)
        page.route(todo, lambda route: route.fulfill(json=rows[3:]))
        page.evaluate('() => refreshTodoCount()')
        assert page.evaluate(seen) == ['', None, False]
    finally:
        page.unroute(todo)


# ───────── 셸(디자인기준 3-1 — shadcn sidebar-07 inset)과 홈(5-4)의 모양: 실제 브라우저에서 잰 관계로 판정한다 ─────────

def test_메뉴_줄은_이야기_차례로_놓이고_지식_메뉴는_문서_등록부터다(portal):
    """왼쪽 메뉴가 화면에 놓인 차례(위에서 아래로)가 이야기 차례다: 홈 → 지식 → 유압 설비 → 처리 건 → 흐름 → AI 에이전트 → 판단 실험 → 시스템.
    지식을 펼치면 문서 등록(지식을 넣는 화면)이 맨 위다. 차례는 표의 글이 아니라 실제로 그려진 줄의 세로 자리로 본다."""
    page = portal
    page.evaluate("() => selectTab('skills')")
    rows = page.evaluate("""() => [...document.querySelectorAll('#menuList [data-menu]')].filter(n => n.checkVisibility())
      .map(n => [n.dataset.menu, n.getBoundingClientRect().top]).sort((a, b) => a[1] - b[1]).map(r => r[0])""")
    assert rows == ['main', 'knowledge', 'plant', 'instances', 'flows', 'agents', 'trial', 'system'], rows
    page.locator("#menuList a[data-tab='fabric']").wait_for(state='visible', timeout=3000)      # 펼치는 움직임이 끝난 뒤에 잰다
    # 펼치는 움직임이 끝나 「유압 설비」 줄이 지식의 마지막 화면 줄 아래에 멈출 때까지 기다린다(잇따른 두 번의 물음에서 자리가 같다)
    page.wait_for_function("""() => { const y = document.querySelector("#menuList summary[data-menu='plant']").getBoundingClientRect().top, was = window.menuProbeY;
      window.menuProbeY = y; return was === y && y > document.querySelector("#menuList a[data-tab='fabric']").getBoundingClientRect().top; }""", polling=120, timeout=5000)
    inner = page.evaluate("""() => [...document.querySelectorAll("#menuList details[open] ul a[data-tab]")].filter(n => n.checkVisibility())
      .map(n => [n.dataset.tab, n.getBoundingClientRect().top]).sort((a, b) => a[1] - b[1]).map(r => r[0])""")
    assert inner == ['knowledge', 'ontology', 'skills', 'fabric'], inner
    tops = page.evaluate("""() => { const y = s => document.querySelector(s).getBoundingClientRect().top;
      return [y("#menuList summary[data-menu='knowledge']"), y("#menuList a[data-tab='fabric']"), y("#menuList summary[data-menu='plant']"), y("#menuList a[data-menu='instances']")]; }""")
    assert tops == sorted(tops), f'사건이 생기는 곳(유압 설비)과 처리 건이 지식 아래에 차례로 놓인다: {tops}'


def test_본문_판은_옅은_회색_틀_안에_떠_있는_흰_둥근_판이고_좁은_폭에서는_띄우지_않는다(portal):
    """inset 짜임: 몸 바탕과 메뉴 줄은 같은 옅은 회색이고 그 사이에 선이 없다. 본문 판은 그 바탕보다 밝고, 위 · 오른쪽 · 아래로 같은 틈만큼 떠 있으며 모서리가 둥글고 그림자가 있다.
    판의 왼쪽 선은 메뉴 줄의 오른쪽 선이다. 창을 굴려도 판의 윗선(위 막대)은 그 틈 아래에 그대로 있고, 틈으로 본문이 비쳐 보이지 않는다. 좁은 폭에서는 판을 띄우지 않는다."""
    page = portal
    page.evaluate("() => { selectTab('skills'); scrollTo(0, 0); }")
    probe = """() => { const lum = c => { const x = document.createElement('canvas').getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 1, 1); x.fillStyle = c; x.fillRect(0, 0, 1, 1);
        const [r, g, b] = x.getImageData(0, 0, 1, 1).data; return [r, g, b]; };
      const main = document.querySelector('.app-main'), nav = document.querySelector('#sidebar > nav'), m = main.getBoundingClientRect(), n = nav.getBoundingClientRect(), cs = getComputedStyle(main);
      return { top: m.top, right: innerWidth - m.right, bottomGap: document.documentElement.scrollHeight - (m.bottom + scrollY), left: m.left - n.right, radius: parseFloat(cs.borderTopLeftRadius), shadow: cs.boxShadow,
        body: lum(getComputedStyle(document.body).backgroundColor), nav: lum(getComputedStyle(nav).backgroundColor), main: lum(cs.backgroundColor), navLine: parseFloat(getComputedStyle(nav).borderRightWidth),
        bar: document.querySelector('.topbar').getBoundingClientRect().top - m.top }; }"""
    wide = page.evaluate(probe)
    assert wide['top'] > 0 and wide['top'] == wide['right'] == wide['bottomGap'], f'위 · 오른쪽 · 아래 틈이 같다: {wide}'
    assert abs(wide['left']) < 0.5 and wide['navLine'] == 0, f'판은 메뉴 줄에 바로 붙고 그 사이에 선이 없다: {wide}'
    assert wide['radius'] >= 8 and wide['shadow'] != 'none', wide
    assert wide['body'] == wide['nav'] and sum(wide['main']) > sum(wide['body']), f'메뉴 줄은 몸 바탕과 같은 회색이고 본문 판은 그보다 밝다: {wide}'
    assert wide['bar'] == 0, '위 막대는 판의 첫 줄이다'
    # 창을 굴린 뒤: 위 막대는 창 위에서 같은 틈 아래에 붙어 있고, 그 틈의 가운데 점에는 본문이 아니라 셸 바탕이 있다
    page.evaluate("() => { document.querySelector('.page').style.minHeight = '2400px'; scrollTo(0, 900); }")
    try:
        page.wait_for_function('() => scrollY > 500')
        rolled = page.evaluate("""() => { const bar = document.querySelector('.topbar').getBoundingClientRect(), hit = document.elementFromPoint(bar.left + bar.width / 2, bar.top / 2);
          return { top: bar.top, hit: hit === document.querySelector('.app-main') || hit === document.body || hit === document.documentElement }; }""")
        assert rolled == {'top': wide['top'], 'hit': True}, rolled
    finally:
        page.evaluate("() => { document.querySelector('.page').style.minHeight = ''; scrollTo(0, 0); }")
    page.set_viewport_size({'width': 600, 'height': 900})
    try:
        page.wait_for_function("() => document.querySelector('.app-main').getBoundingClientRect().top === 0")
        narrow = page.evaluate(probe)
        assert (narrow['top'], narrow['right'], narrow['radius']) == (0, 0, 0), f'좁은 폭에서는 판을 띄우지 않는다: {narrow}'
    finally:
        page.set_viewport_size({'width': 1280, 'height': 720})


def test_실시간_연결_상태는_점_하나이고_올리면_글이_뜨고_누르면_방금_받은_활동이_펼쳐진다(portal):
    """위 막대의 실시간 연결 상태는 점 하나다(글이 자리를 차지하지 않는다). 마우스를 올리면 연결 상태 글이 뜨고, 누르면 방금 받은 활동이 펼쳐진다."""
    page = portal
    page.evaluate("() => selectTab('main')")
    page.wait_for_function("() => ['retry', 'off'].includes(hydStream.conn().state)", timeout=20000)
    page.mouse.move(600, 400)
    seen = """() => { const s = document.querySelector('#streamTicker > summary'), label = s.querySelector('span'), dot = s.querySelector('.dot').getBoundingClientRect(), box = s.getBoundingClientRect();
      return { shown: label.checkVisibility({ visibilityProperty: true, opacityProperty: true }), text: label.textContent.trim(), square: Math.abs(box.width - box.height) < 1,
               centered: Math.abs((dot.left + dot.right) / 2 - (box.left + box.right) / 2) < 1, open: document.getElementById('streamTicker').open }; }"""
    idle = page.evaluate(seen)
    assert idle['shown'] is False and idle['square'] and idle['centered'] and idle['text'] == page.evaluate('() => hydStream.conn().text'), idle
    page.hover('#streamTicker > summary')
    page.wait_for_function(f"() => ({seen})().shown")                     # 올리면 연결 상태 글이 뜬다
    page.click('#streamTicker > summary')
    opened = page.evaluate(seen)
    assert opened['open'] is True
    page.locator('#streamTicker .ticker-detail').wait_for(state='visible', timeout=3000)
    page.click('#streamTicker > summary')
    page.mouse.move(600, 400)


def _home(page, *, incidents=None, todo=None):
    """홈을 열고, 처리 건 목록 · 내 할 일 목록을 준 값으로 읽게 한 뒤 단계 카드가 그 값으로 그려질 때까지 기다린다. 돌려주는 것은 카드 넷이 화면에 보이는 꼴이다."""
    routes = []
    if incidents is not None:
        routes.append(('**/svc/process/api/incidents', incidents))
    if todo is not None:
        routes.append(('**/svc/process/api/todolist**', todo))
    def answer(rows):
        return lambda route: route.fulfill(json=rows)
    for url, rows in routes:
        page.route(url, answer(rows))
    try:
        page.evaluate("() => { selectTab('main'); scrollTo(0, 0); return refreshSlow(); }")
        page.wait_for_function("() => document.querySelectorAll('#mainStages > .stat').length === 4")
        page.wait_for_timeout(1200)                                      # 홈은 1초마다 값이 바뀌었는지 보고 다시 그린다
        return page.evaluate("""() => [...document.querySelectorAll('#mainStages > .stat')].map(c => { const r = c.getBoundingClientRect(), pill = c.querySelector('.stat-pill .tag');
          return { label: c.querySelector('.stat-label').textContent.replace(/\\s+/g, ' ').trim(), value: c.querySelector('.stat-value').textContent.trim(), tab: c.dataset.goTab, go: c.querySelector('.go').textContent.trim(),
                   top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), width: Math.round(r.width), pill: pill ? pill.textContent.trim() : '', pillTone: pill ? pill.dataset.tone : '',
                   foot: Math.round(c.querySelector('.stat-foot').getBoundingClientRect().top) }; })""")
    finally:
        for url, _ in routes:
            page.unroute(url)


def test_홈의_단계_카드_넷은_이야기_차례로_한_줄에_서고_카드마다_지금_값과_그_화면으로_가는_길이_있다(portal):
    """홈(디자인기준 5-4): 그림 아래에 단계 카드 넷 — 지식 넣기 → 고장 내기 → 판단과 승인 → 결과 보기. 넓은 폭에서 같은 줄 · 같은 높이 · 같은 폭이고 아래 고정 줄(가는 길)이 같은 세로 자리에 선다.
    「판단과 승인」은 진행 중인 처리 건 수, 「결과 보기」는 처리 완료한 건 수를 읽은 값 그대로 보인다. 카드를 누르면 그 화면이 열린다. 옛 숫자 타일(설비 3기)과 「처음이라면 이 순서로」 줄은 없다."""
    page = portal
    page.set_viewport_size({'width': 1440, 'height': 900})
    try:
        rows = [{'id': 'a', 'terminal': False}, {'id': 'b', 'terminal': True}, {'id': 'c', 'terminal': True}, {'id': 'd', 'terminal': True}]
        cards = _home(page, incidents=rows, todo=[])
        assert [c['label'] for c in cards] == ['1 지식 넣기', '2 고장 내기', '3 판단과 승인', '4 결과 보기']
        assert [c['tab'] for c in cards] == ['knowledge', 'scenario', 'instances', 'instances']
        assert len({c['top'] for c in cards}) == 1 and len({c['bottom'] for c in cards}) == 1 and len({c['foot'] for c in cards}) == 1, f'카드 넷이 같은 줄 · 같은 높이이고 아래 고정 줄이 같은 자리다: {cards}'
        assert max(c['width'] for c in cards) - min(c['width'] for c in cards) <= 1 and [c['left'] for c in cards] == sorted(c['left'] for c in cards)
        assert cards[2]['value'].startswith('1') and cards[3]['value'].startswith('3'), f'진행 중 1건 · 처리 완료 3건: {cards}'
        assert cards[2]['pill'] == '', '내 차례가 없으면 알약을 그리지 않는다'
        assert all(c['go'] for c in cards)
        assert page.locator('#mainStats, #mainArch, #view-main .hm-steps, #view-main .sec-head').count() == 0
        assert '설비' not in ' '.join(c['label'] for c in cards)
        for i, tab in enumerate(['knowledge', 'scenario', 'instances', 'instances']):      # 카드를 누르면 그 화면이 열린다
            page.evaluate("() => { selectTab('main'); scrollTo(0, 0); }")
            page.locator('#mainStages > .stat').nth(i).click()
            assert page.evaluate('() => state.tab') == tab
    finally:
        page.set_viewport_size({'width': 1280, 'height': 720})


def test_홈의_판단과_승인_카드는_내_차례가_있을_때만_주황_알약을_단다(portal):
    page = portal
    todo = [{'proc_inst_id': 'inst-a', 'agent_orch': None, 'agent_mode': None}, {'proc_inst_id': 'inst-b', 'agent_orch': None, 'agent_mode': None}]
    cards = _home(page, incidents=[{'id': 'a', 'terminal': False}, {'id': 'b', 'terminal': False}], todo=todo)
    assert [(c['pill'], c['pillTone']) for c in cards] == [('', ''), ('', ''), ('내 차례 2', 'mine'), ('', '')], cards
    cards = _home(page, incidents=[{'id': 'a', 'terminal': False}], todo=[])
    assert [c['pill'] for c in cards] == ['', '', '', ''], '내 차례가 없어지면 알약도 없어진다'


def test_홈의_카드는_읽지_못한_값을_0이나_없음으로_보이지_않는다(portal):
    """이 포털은 서비스 요청이 모두 끊겨 있다 — 지식 수 · 설비 값 · 처리 건 수를 읽지 못한 카드는 숫자 대신 「읽기 실패」를 보이고 까닭을 title 에 둔다."""
    page = portal
    page.evaluate("() => { selectTab('main'); state.incidents = []; state.incidentsRead = false; return refreshSlow(); }")
    page.wait_for_function("() => [...document.querySelectorAll('#mainStages > .stat')].filter(c => c.querySelector('.stat-value').textContent.trim() === '읽기 실패').length >= 3", timeout=20000)
    cards = page.evaluate("() => [...document.querySelectorAll('#mainStages > .stat')].map(c => [c.querySelector('.stat-value').textContent.trim(), c.dataset.tone || '', !!c.title])")
    assert cards[1] == ['읽기 실패', 'danger', True] and cards[2] == ['읽기 실패', 'danger', True] and cards[3] == ['읽기 실패', 'danger', True], cards
    assert not any(v in ('0', '없음') for v, _, _ in cards)


def test_홈_그림의_값이_지나는_길을_누르면_시스템_구성이_열리고_누를_수_있다는_것이_보인다(portal):
    """머리의 「시스템 구성 보기」 단추는 없다. 그림 가운데의 「값이 지나는 길」이 링크이고, 그 발치에 「시스템 구성 →」이 보이며 손가락 커서가 뜬다. 키보드로도 닿는다."""
    page = portal
    page.evaluate("() => { selectTab('main'); scrollTo(0, 0); }")
    link = page.locator('#mainHero a.hm-arch')
    assert link.count() == 1 and page.locator('#view-main .page-tools button, #mainArch').count() == 0
    seen = page.evaluate("""() => { const a = document.querySelector('#mainHero a.hm-arch'), t = a.querySelector('.hm-arch-t'), bus = a.querySelector('.m-bus rect').getBoundingClientRect(), r = t.getBoundingClientRect();
      return { cursor: getComputedStyle(a.querySelector('.m-bus rect')).cursor, text: t.textContent.trim(), shown: t.checkVisibility() && r.width > 0, below: r.top >= bus.bottom - 1,
               centered: Math.abs((r.left + r.right) / 2 - (bus.left + bus.right) / 2) < 3, underline: getComputedStyle(t).textDecorationLine }; }""")
    assert seen == {'cursor': 'pointer', 'text': '시스템 구성 →', 'shown': True, 'below': True, 'centered': True, 'underline': 'underline'}, seen
    link.locator('.m-bus rect').click()
    assert page.evaluate('() => state.tab') == 'home'
