"""포털 화면 순회 — 떠 있는 포털(환경 변수 HYD_TEST_PORTAL_URL, 예: http://127.0.0.1:8088)의 메뉴를 두 화면 크기(1366 · 1920)에서 실제
브라우저(Playwright Chromium)로 하나씩 열고, 학생이 겪는 문제를 판정한다. 쓰기 단추는 누르지 않는다(학생 상태를 바꾸지 않음).

메뉴마다: 콘솔 오류 0 · 실패한 요청 0 · 14초 뒤에도 남은 「…하는 중」 로딩 문구 없음 · 내부어(설정 이름 · 영문 경보 코드 · 표 이름) 없음 ·
가로 넘침 없음 · 「눌리는데 거절」 없음 — 서버 수업 경계(GET /api/course-access)가 막은 행동 키를 단 요소는 꺼져 있고 서버 까닭을 보인다.
메뉴 목록은 index.html 의 주 메뉴(.rail nav button[data-tab])에서 읽는다. 메뉴 잠금은 없다(모든 메뉴가 열린다).
서버가 꺼져 있거나 이 판과 다르면 그 사실이 실패 문장에 그대로 나온다(조용히 건너뛰지 않는다).
"""
import os
import re
import time
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
INDEX = ROOT / 'it' / 'portal' / 'www' / 'index.html'
SIZES = [(1366, 768), (1920, 1080)]
LOADING_LIMIT_S = 14
# 로딩 자리 표시: 「…중…」(말줄임표로 끝나는 진행 표시)와 말줄임표 없는 몇 가지. 「승인을 기다리는 중입니다」 같은 진행 상태 문장은 로딩이 아니다
LOADING = re.compile(r'([가-힣]+ 중…|불러오는 중|연결 확인 중|조회 중)')
JARGON = re.compile(r'(AI_MODE|AGENT_BRIDGE|PROCESS_MODE|LLM_API_KEY|RunFailed|Traceback|\.env\b|tenants\.mcp|tenant_\w+|is_agent|users 표|'
                    r'Claude Code|Inbucket|provenance|API 키|undefined|NaN|\[object Object\]|\bnull\b|'
                    r'COOLER_DEGRADATION|PUMP_LEAKAGE|FAN_VIBRATION|OIL_ANALYSIS|PM_DUE|SPARE_BELOW_MIN|HTTP \d{3}|status \d{3}|설비 시간 배율)')
# 수업 단계에서 그 메뉴에 반드시 있어야 하는 행동 키(막힌 단추가 꺼진 채 보이는지 볼 자리)
EXPECTED_ACTIONS = {'mcp': ['tool_servers.register'], 'admin': ['config.import']}


class _Menus(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth, self.menus = 0, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'nav' and a.get('aria-label') == '주 메뉴':
            self.depth = 1
        elif tag == 'button' and self.depth and 'data-tab' in a:
            self.menus.append(a['data-tab'])

    def handle_endtag(self, tag):
        if tag == 'nav':
            self.depth = 0


def _menus():
    p = _Menus()
    p.feed(INDEX.read_text(encoding='utf8'))
    return p.menus


MENUS = _menus()


@pytest.fixture(scope='session')
def portal_url():
    url = os.environ.get('HYD_TEST_PORTAL_URL')
    if not url:
        pytest.fail('HYD_TEST_PORTAL_URL 이 없어 화면 순회를 돌리지 못했다 — 스택을 켠 PC에서 HYD_TEST_PORTAL_URL=http://127.0.0.1:8088 을 주고 다시 돌린다',
                    pytrace=False)
    return url.rstrip('/')


@pytest.fixture(scope='session')
def browser(portal_url):        # 포털 주소가 없으면 브라우저를 열지 않는다(뒤 테스트의 스레드에 이벤트 루프를 남기지 않게)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


class Tour:
    """한 화면 크기의 브라우저 탭 하나. 메뉴를 열 때마다 그 사이의 콘솔 오류 · 실패한 요청만 모은다."""

    def __init__(self, browser, url, size):
        self.ctx = browser.new_context(viewport={'width': size[0], 'height': size[1]}, locale='ko-KR')
        self.page = self.ctx.new_page()
        self.events = []
        self.page.on('console', lambda m: self.events.append(('콘솔 오류', m.text[:300])) if m.type == 'error' else None)
        self.page.on('pageerror', lambda e: self.events.append(('스크립트 오류', str(e)[:300])))
        self.page.on('response', lambda r: self.events.append(('실패 요청', f'{r.status} {r.request.method} {r.url[:160]}')) if r.status >= 400 else None)
        self.page.on('requestfailed', lambda r: self.events.append(('실패 요청', f'{r.failure} {r.method} {r.url[:160]}'))
                     if 'ERR_ABORTED' not in str(r.failure) else None)
        self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
        self.page.wait_for_function("() => window.hydCourseAccess && (window.hydCourseAccess.access || window.hydCourseAccess.error)", timeout=30000)
        self.access = self.page.evaluate('() => window.hydCourseAccess.access')
        self.access_error = self.page.evaluate('() => window.hydCourseAccess.error')

    def open(self, tab):
        self.events.clear()
        self.page.click(f'.rail nav button[data-tab="{tab}"]')
        try:
            self.page.wait_for_load_state('networkidle', timeout=10000)
        except Exception:  # noqa: BLE001 — 실시간 연결(SSE)이 있는 화면은 조용해지지 않는다; 아래 조건 대기가 판정한다
            pass
        started = time.monotonic()
        try:   # 로딩 문구가 사라질 때까지(최대 14초) 조건을 다시 본다
            self.page.wait_for_function("re => !new RegExp(re).test(document.querySelector('main').innerText)", arg=LOADING.pattern,
                                        timeout=LOADING_LIMIT_S * 1000, polling=500)
        except Exception:  # noqa: BLE001 — 14초 뒤에도 남은 로딩 문구는 아래에서 판정한다
            pass
        return time.monotonic() - started

    def text(self):
        return self.page.evaluate("() => document.querySelector('main').innerText")

    def words(self):
        """학생이 읽는 문장 — 보이는 글자 중 원문 칸(pre · code, 「원문」 접기)은 뺀다(원문은 개발자용으로 접어 두는 것이 규칙)."""
        return self.page.evaluate("""() => {
          const out = [], w = document.createTreeWalker(document.querySelector('main .view.active'), NodeFilter.SHOW_TEXT);
          let n; while ((n = w.nextNode())) { const e = n.parentElement; if (e && !e.closest('pre, code') && e.checkVisibility()) out.push(n.textContent); }
          return out.join(' ');
        }""")

    def overflow(self):
        return self.page.evaluate("""() => {
          const out = [];
          const pageScroll = document.documentElement.scrollWidth > window.innerWidth + 1;
          for (const el of document.querySelectorAll('main .view.active *')) {
            const cs = getComputedStyle(el);
            if (!el.offsetParent || ['auto', 'scroll', 'hidden', 'clip'].includes(cs.overflowX) || cs.textOverflow === 'ellipsis') continue;
            if (el.children.length === 0 && el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2)
              out.push((el.tagName + '.' + (typeof el.className === 'string' ? el.className : '')).slice(0, 60) + ': ' + (el.innerText || '').slice(0, 40));
            if (out.length >= 8) break;
          }
          return { pageScroll, clipped: out };
        }""")

    def actions(self):
        return self.page.evaluate("""() => [...document.querySelectorAll('main .view.active [data-course-action]')]
          .map(n => ({ key: n.dataset.courseAction, disabled: n.disabled, title: n.title, label: (n.innerText || n.value || '').trim().slice(0, 40) }))""")


@pytest.fixture(scope='session')
def tours(browser, portal_url):
    made = {}

    def get(size):
        if size not in made:
            made[size] = Tour(browser, portal_url, size)
        return made[size]
    yield get
    for t in made.values():
        t.ctx.close()


CASES = [(size, tab) for size in SIZES for tab in MENUS]


def _id(case):
    (w, h), tab = case
    return f'{w}x{h}-{tab}'


def test_주_메뉴는_23개이고_하나도_잠겨_있지_않다(tours):
    page = tours(SIZES[0]).page
    menus = page.eval_on_selector_all('.rail nav button[data-tab]', 'bs => bs.map(b => ({ tab: b.dataset.tab, disabled: b.disabled }))')
    assert len(menus) == 23 and [m['tab'] for m in menus] == MENUS
    assert [m['tab'] for m in menus if m['disabled']] == []


def test_상단에_지금_단계가_한_줄로_보인다(tours):
    t = tours(SIZES[0])
    assert t.access is not None, f'수업 범위(GET /api/course-access)를 읽지 못했다: {t.access_error}'
    line = t.page.inner_text('#courseStatus')
    expected = f"지금 단계: {t.access['label']}"
    assert line.startswith(expected), line
    if t.access.get('expired'):
        assert 'PBL 기한 지남' in line


def test_수업_범위를_못_읽으면_잠그지_않고_다시_시도를_보인다(browser, portal_url):
    """처리 서비스가 늦게 뜬 상황(수업 범위 요청이 끊김) — 메뉴 · 단추를 잠그지 않고, 실패 문구와 [다시 시도]가 보이며 누르면 다시 읽는다."""
    ctx = browser.new_context(viewport={'width': 1366, 'height': 768}, locale='ko-KR')
    try:
        page = ctx.new_page()
        page.route('**/api/course-access', lambda route: route.abort('connectionrefused'))
        page.goto(portal_url, wait_until='domcontentloaded')
        page.wait_for_function("() => window.hydCourseAccess && window.hydCourseAccess.error", timeout=30000)
        assert page.inner_text('#courseStatus [data-course-retry]') == '다시 시도'
        assert page.get_attribute('#courseStatus', 'title').startswith('수업 범위를 읽지 못했습니다')
        assert page.eval_on_selector_all('.rail nav button[data-tab]', 'bs => bs.filter(b => b.disabled).length') == 0
        page.click('.rail nav button[data-tab="mcp"]')
        page.wait_for_selector('#mcpAdd', state='attached')       # 접어 둔 운영자 칸 안에 있다
        assert page.eval_on_selector('#mcpAdd', 'b => b.disabled') is False      # 모를 때는 막지 않는다 — 서버가 판정
        # 자동 재시도(3초 · 10초 · 30초 뒤)와 구별한다: 첫 자동 재시도가 지나간 직후에 누르면 다음 자동 재시도(10초 뒤)보다 먼저 요청이 나가야 한다
        with page.expect_request('**/api/course-access', timeout=8000):
            pass
        page.wait_for_selector('#courseStatus [data-course-retry]')
        with page.expect_request('**/api/course-access', timeout=2000):     # 누르면 바로 다시 읽는다
            page.click('#courseStatus [data-course-retry]')
    finally:
        ctx.close()


@pytest.mark.parametrize('case', CASES, ids=[_id(c) for c in CASES])
def test_메뉴를_열면_오류_로딩_내부어_넘침_눌리는데_거절이_없다(tours, case):
    size, tab = case
    t = tours(size)
    t.open(tab)
    text = t.text()
    problems = [] if t.access else [f'수업 범위(GET /api/course-access)를 읽지 못해 「눌리는데 거절」을 판정할 수 없다: {t.access_error}']
    problems += [f'{kind}: {what}' for kind, what in t.events]
    loading = sorted(set(LOADING.findall(text)))
    if loading:
        problems.append(f'{LOADING_LIMIT_S}초 뒤에도 남은 로딩 문구: {", ".join(loading)}')
    jargon = sorted(set(m.group(0) for m in JARGON.finditer(t.words())))
    if jargon:
        problems.append(f'내부어: {", ".join(jargon)}')
    ov = t.overflow()
    if ov['pageScroll']:
        problems.append('페이지 가로 스크롤')
    problems += [f'글자 잘림: {c}' for c in ov['clipped']]
    blocked = {k: a['reason'] for k, a in ((t.access or {}).get('actions') or {}).items() if a and a.get('allowed') is False}
    present = t.actions()
    for a in present:
        if a['key'] in blocked and not (a['disabled'] and a['title'] == blocked[a['key']]):
            problems.append(f"눌리는데 거절: 「{a['label']}」({a['key']}) 단추가 {'켜져' if not a['disabled'] else '까닭 없이 꺼져'} 있다")
        if a['key'] not in blocked and a['disabled'] and a['title']:
            problems.append(f"열린 행동인데 꺼짐: 「{a['label']}」({a['key']}) — {a['title']}")
    for key in EXPECTED_ACTIONS.get(tab, []):
        if key in blocked and not any(a['key'] == key for a in present):
            problems.append(f'수업 단계에서 막힌 행동 {key} 의 단추가 화면에 표시되지 않았다(행동 키를 단 요소 없음)')
    assert not problems, '\n'.join(problems)
