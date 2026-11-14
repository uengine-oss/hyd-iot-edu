"""포털 공용 부품(it/portal/www/ui.js)이 실제 브라우저에서 내는 것 — 원문 판(UI.raw) · 번호 조각(UI.id) · 한 줄 코드(UI.code) · 빈 상태(UI.empty)
· 조치 후보 표(UI.optionsTable) · 화면 머리(UI.pageHead)와 더 보기 메뉴. 서비스 없이 화면 파일만 낸 포털에서, 부품을 본문에 그려 놓고 보이는 것과 누른 결과를 본다."""
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

SCREENS = ['main', 'instances', 'ontology', 'skills', 'knowledge', 'fabric', 'flows', 'agents', 'mcp', 'ask', 'scenario', 'oil', 'trends', 'incidents', 'process',
           'decision', 'whatif', 'eval', 'compare', 'home', 'kpi', 'admin']


@pytest.fixture(scope='module')
def portal():
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={'width': 1440, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
            page = ctx.new_page()
            page.route('**/svc/**', lambda route: route.abort('connectionrefused'))
            page.goto(served.url + '/index.html')
            page.wait_for_function('() => window.hydShell && window.hydMenu')
            yield page
            b.close()
    finally:
        served.close()


def draw(page, expr):
    """부품 하나를 지금 화면의 본문 맨 위 시험 칸(#partsProbe)에 그린다. expr 은 HTML 을 돌려주는 JS 식."""
    page.evaluate("""expr => { let box = document.getElementById('partsProbe');
      if (!box) { box = document.createElement('div'); box.id = 'partsProbe'; document.querySelector('main .view.active').prepend(box); }
      box.innerHTML = (0, eval)(expr); }""", expr)
    return page.locator('#partsProbe')


def test_원문_판은_접힌_한_줄로_시작하고_펼치면_들여쓴_JSON이_색으로_나뉘고_높이가_넘치지_않는다(portal):
    page = portal
    big = "({ pattern: 'COOLER_DEGRADATION', rows: Array.from({ length: 80 }, (_, i) => ({ i, name: '값 ' + i, ok: i % 2 === 0, none: null })) })"
    box = draw(page, f"UI.raw({big}, {{ title: '결과 원문' }})")
    fold = box.locator('details.raw')
    assert fold.count() == 1 and not fold.evaluate('d => d.open'), '원문 판은 접힌 채로 시작한다'
    summary = fold.locator('summary').inner_text()
    assert summary.startswith('결과 원문') and 'JSON' in summary and '자' in summary, summary
    assert not box.locator('pre.code').is_visible(), '접힌 동안에는 원문이 보이지 않는다'
    fold.locator('summary').click()
    pre = box.locator('pre.code')
    pre.wait_for(state='visible')
    text = pre.inner_text()
    assert text.startswith('{\n  "pattern": "COOLER_DEGRADATION",\n  "rows": [\n    {\n      "i": 0,'), text[:120]      # 들여쓴 JSON, 코드 값은 이름으로 바꾸지 않는다
    page.wait_for_function("() => document.querySelectorAll('#partsProbe pre.code .token').length > 50")       # 구문 강조(Prism)가 실제로 입혀졌다
    colors = page.evaluate("""() => { const c = k => getComputedStyle(document.querySelector('#partsProbe pre.code .token.' + k)).color;
      return [c('property'), c('string'), c('number'), getComputedStyle(document.querySelector('#partsProbe pre.code')).color]; }""")
    assert len(set(colors)) == 4, f'이름 · 글 · 숫자 · 바탕 글의 색이 서로 달라야 한다: {colors}'
    size = pre.evaluate('p => [p.clientHeight, p.scrollHeight]')
    assert size[0] <= 322 and size[1] > 1000, f'긴 원문은 판 안에서 스크롤된다(높이 한도 320): {size}'


def test_원문_판의_복사_단추는_원문_전체를_클립보드에_넣는다(portal):
    page = portal
    box = draw(page, "UI.raw({ a: 1, note: '한 줄' })")
    box.locator('summary').click()
    box.locator('[data-raw-copy]').click()
    page.wait_for_function("async () => (await navigator.clipboard.readText()).includes('\"note\": \"한 줄\"')")
    assert page.evaluate('() => navigator.clipboard.readText()') == '{\n  "a": 1,\n  "note": "한 줄"\n}'


@pytest.mark.parametrize('expr, shown', [
    ("UI.raw('{\"a\":[1,2]}')", '{\n  "a": [\n    1,\n    2\n  ]\n}'),              # 한 줄 JSON 글도 들여써 보인다
    ("UI.raw('MATCH (n) RETURN n', { lang: 'cypher' })", 'MATCH (n) RETURN n'),     # JSON 이 아닌 글은 받은 그대로
    ("UI.raw('/home/user/x/result.json 을 claude-opus-4 가 썼다', { mask: true })", 'result.json 을 AI 모델 가 썼다'),      # mask: 이 PC 경로 · 모델 이름만 가린다
])
def test_원문_판은_받은_글을_한_가지_모양으로_보인다(portal, expr, shown):
    box = draw(portal, expr)
    assert box.locator('pre.code').evaluate('p => p.textContent') == shown


def test_빈_값은_원문_판을_그리지_않는다(portal):
    assert portal.evaluate("() => [UI.raw(null), UI.raw(''), UI.raw(undefined)]") == ['', '', '']


def test_번호_조각은_해시를_줄여_보이고_누르면_전체를_복사한다(portal):
    page = portal
    sha = '6fdb99a4' + 'c' * 56
    box = draw(page, f"UI.id('{sha}', {{ label: '원문 지문' }}) + UI.id('WO-1114-C81AA49475BF')")
    chips = box.locator('.idc')
    assert chips.nth(0).inner_text().replace('\n', ' ') == '원문 지문 6fdb99a4…'
    assert chips.nth(1).inner_text() == 'WO-1114-C81AA49475BF', '사람이 읽는 번호는 줄이지 않는다'
    assert chips.nth(0).get_attribute('title') == sha
    chips.nth(0).click()
    page.wait_for_function(f"async () => (await navigator.clipboard.readText()) === '{sha}'")


def test_한_줄_코드는_좁은_칸에서도_꺾이지_않고_가로로_넘긴다(portal):
    expr = "'<div style=\"width:220px\">' + UI.code(\"TS1 < 52 and slope(TS1) <= 0 and mean(CE, 30s) >= 70 and state == 'RUN'\") + '</div>'"
    box = draw(portal, expr)
    m = box.locator('.codeline').evaluate('c => ({ h: c.clientHeight, sw: c.scrollWidth, cw: c.clientWidth, line: parseFloat(getComputedStyle(c).lineHeight) })')
    assert m['h'] <= m['line'] + 10, f'한 줄이어야 한다: {m}'
    assert m['sw'] > m['cw'], f'넘치는 글은 가로 스크롤이다: {m}'


def test_빈_상태는_아이콘_제목_설명과_그_화면으로_가는_단추를_낸다(portal):
    page = portal
    box = draw(page, "UI.empty({ icon: 'inbox', title: '아직 처리 건이 없습니다', sub: '결함을 넣으면 생깁니다.', action: { label: '결함 시뮬레이션 열기', tab: 'scenario' } })")
    empty = box.locator('section.empty')
    assert empty.locator('header figure svg use').get_attribute('href').endswith('#inbox')
    assert empty.locator('h3').inner_text() == '아직 처리 건이 없습니다' and empty.locator('header p').inner_text() == '결함을 넣으면 생깁니다.'
    empty.locator('footer button').click()
    assert page.evaluate('() => state.tab') == 'scenario', '빈 상태의 단추가 그 화면을 연다'
    open_screen(page, 'main')
    # 목록 안의 한 줄 꼴(제목, 설명)은 아이콘 · 단추가 없다
    box = draw(page, "UI.empty('이 종류가 없습니다', '「전체」를 고르면 보입니다.')")
    assert box.locator('figure').count() == 0 and box.locator('footer').count() == 0 and box.locator('h3').inner_text() == '이 종류가 없습니다'


def test_조치_후보_표는_칸이_같고_값이_없는_칸은_그리지_않으며_막대는_점수에_비례한다(portal):
    rows = """[{ rank: 1, name: '부하 70 %와 야간 핀 세척', code: 'SOP-COOL-13', kind: '설비 제어 · 정비 요청', score: 3, role: '운전원', pick: true },
      { rank: 2, name: '팬 최대 운전', code: 'SOP-COOL-11', kind: '설비 제어', score: 1.5, role: '운전원', note: '1순위보다 1.55점 낮음' },
      { rank: '–', name: '쿨러 교체', kind: '정비 요청', scoreHtml: '제외', role: '설비보전팀장', out: true }]"""
    box = draw(portal, f"UI.optionsTable({rows})")
    assert box.locator('thead th').all_inner_texts() == ['순위', '조치 후보', '종류', '점수', '', '승인 역할']
    cells = box.locator('tbody tr').nth(1).locator('td').all_inner_texts()
    assert cells[0] == '2' and cells[1].split('\n')[0].replace('\xa0', ' ').startswith('팬 최대 운전') and 'SOP-COOL-11' in cells[1] and '1순위보다 1.55점 낮음' in cells[1]
    assert cells[2] == '설비 제어' and cells[3] == '1.50', cells      # 소수 둘째 자리, + 부호 없음
    assert cells[5] == '운전원'
    widths = box.locator('tbody .bar > i').evaluate_all('xs => xs.map(i => i.style.width)')
    assert widths == ['100%', '50%', '0%'], widths                                          # 1순위가 가득, 절반 점수는 절반, 제외된 안은 0
    assert box.locator('tbody tr').nth(0).get_attribute('data-pick') is not None and box.locator('tbody tr').nth(2).get_attribute('data-out') is not None
    assert box.locator('tbody tr').nth(2).locator('td').nth(3).inner_text() == '제외'
    kind = box.locator('tbody tr').nth(0).locator('.badge')
    assert kind.evaluate('b => b.getBoundingClientRect().height') < 30, '종류는 두 줄로 꺾이지 않는다'
    # 종류 · 승인 역할이 하나도 없으면 그 칸이 없다. 화면마다 더하는 칸은 오른쪽에 붙는다
    box = draw(portal, "UI.optionsTable([{ rank: 1, name: '가', score: 2, extra: ['1위', '−96,276원'] }], { extra: [{ label: '손익 순위' }, { label: '예상 손익', num: true }] })")
    assert box.locator('thead th').all_inner_texts() == ['순위', '조치 후보', '점수', '', '손익 순위', '예상 손익']


def test_화면_머리는_제목_한_문장_도구와_더_보기_메뉴를_내고_메뉴의_동작이_그_단추로_눌린다(portal):
    page = portal
    box = draw(page, """UI.pageHead('flows', { sub: '한 문장입니다.', tools: UI.btn('add', { label: '흐름 가져오기', attrs: 'id="probeAdd"' }), more: [{ act: 'reload', attrs: 'id="probeReload"' }] })""")
    assert box.locator('.page-head h1').inner_text() == page.evaluate("() => UI.t('nav.flows')")
    assert box.locator('.page-head p').inner_text() == '한 문장입니다.'
    assert box.locator('.page-tools > button.btn').count() == 1, '머리의 주 단추는 하나'
    assert not box.locator('[role=menu]').is_visible(), '더 보기 메뉴는 닫힌 채로 시작한다'
    page.evaluate("() => { window.__reloaded = 0; document.getElementById('probeReload').addEventListener('click', () => { window.__reloaded += 1; }); }")
    box.locator('.dropdown-menu > button').click()
    item = box.locator('[role=menuitem]')
    item.wait_for(state='visible')
    assert item.inner_text().strip() == '다시 읽기'
    item.click()
    assert page.evaluate('() => window.__reloaded') == 1


@pytest.mark.parametrize('tab', SCREENS)
def test_모든_화면의_머리는_같은_짜임이고_거르기_단추와_상태_알약을_두지_않으며_한_문장이_한_줄이다(portal, tab):
    page = portal
    page.evaluate("() => document.getElementById('partsProbe')?.remove()")      # 앞 시험이 그려 둔 부품 칸을 치운다
    open_screen(page, tab)
    head = page.locator(f'#view-{tab} .page-head')
    head.first.wait_for(state='visible')
    assert head.count() == 1 and head.locator('h1').count() == 1
    assert head.locator('.seg').count() == 0, '거르기 묶음 단추는 머리가 아니라 목록 바로 위에 둔다'
    assert head.locator('.live-pill').count() == 0, '살아 있음 표시는 위 막대와 메뉴 줄 아래에만 둔다'
    shown = head.locator('.page-tools > .btn:visible, .page-tools > a.btn:visible')
    primary = [b for b in shown.evaluate_all("xs => xs.map(b => b.dataset.variant || 'primary')") if b == 'primary']
    assert len(primary) <= 1, '머리의 주 단추는 하나까지'
    assert head.locator('.page-tools > .btn:visible:disabled').count() == 0, '누를 수 없는 단추를 머리에 두지 않는다'
    p = head.locator('p')
    if p.count():
        m = p.first.evaluate('p => ({ h: p.getBoundingClientRect().height, line: parseFloat(getComputedStyle(p).lineHeight) })')
        assert m['h'] <= m['line'] * 1.5, f'{tab}: 머리의 한 문장이 두 줄로 넘어간다({m})'


def test_되돌리기는_관리_내_설정_한_곳에만_있고_다른_화면은_그곳으로_보낸다(portal):
    page = portal
    for tab, scope in [('flows', 'flows'), ('agents', 'agents'), ('mcp', 'mcp')]:
        open_screen(page, tab)
        view = page.locator(f'#view-{tab}')
        link = view.locator('[data-go-reset]')
        link.wait_for(state='visible')
        assert view.locator('button', has_text='되돌리기').locator('visible=true').count() == 0, f'{tab} 화면에 되돌리기 단추의 사본이 있다'
        link.click()
        assert page.evaluate('() => state.tab') == 'admin'
        assert page.locator('#configBundlePanel').evaluate('d => d.open')
        assert page.locator('#cfgResetScope').input_value() == scope, '보낸 화면의 범위가 골라져 있다'
        assert page.locator('#cfgReset').is_visible()
