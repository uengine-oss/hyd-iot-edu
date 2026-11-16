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


def test_원문_판은_접힌_한_줄로_시작하고_펼치면_JSON이_접히는_나무로_보이고_높이가_넘치지_않는다(portal):
    """원문(디자인기준 4-20): 늘 접힌 한 줄. 펼치면 밝은 코드 상자 안에 JSON 이 들여쓴 나무로 보인다 — 화면 사전에 있는 키는 한국어 이름표와 원래 키가 나란히, 값은 종류마다 색이 다르고,
    객체 · 배열은 든 것의 수를 단 접히는 마디다(둘째 깊이까지 펼쳐 있고 더 깊은 것은 눌러 편다). 긴 원문은 상자 안에서 스크롤된다."""
    page = portal
    big = "({ pattern: 'COOLER_DEGRADATION', cooler_health: 0.72, rows: Array.from({ length: 80 }, (_, i) => ({ i, name: '값 ' + i, ok: i % 2 === 0, none: null })) })"
    box = draw(page, f"UI.raw({big}, {{ title: '결과 원문' }})")
    fold = box.locator('details.raw')
    assert fold.count() == 1 and not fold.evaluate('d => d.open'), '원문 판은 접힌 채로 시작한다'
    summary = fold.locator('summary').first.inner_text()
    assert summary.startswith('결과 원문') and 'JSON' in summary and '자' in summary, summary
    assert not box.locator('pre.code').is_visible() and box.locator('[data-json-tree]').count() == 0, '접힌 동안에는 원문이 보이지 않는다(나무도 아직 그리지 않는다)'
    fold.locator('summary').first.click()
    tree = box.locator('[data-json-tree]')
    tree.wait_for(state='visible')
    assert not box.locator('pre.code').is_visible(), '나무가 보이는 동안 글 원문은 숨는다(복사 단추가 그 글을 복사한다)'
    seen = page.evaluate("""() => { const t = document.querySelector('#partsProbe [data-json-tree]'), rows = [...t.children], cs = n => getComputedStyle(n);
      const leaf = rows.find(r => r.matches('.jt-l') && r.textContent.includes('COOLER_DEGRADATION')), arr = rows.find(r => r.matches('details.jt-n'));
      const first = arr.querySelector('.jt-ch > details'), wantName = hydWords.fieldName('cooler_health'), named = rows.find(r => r.querySelector('.jt-raw') && r.querySelector('.jt-raw').textContent === 'cooler_health');
      const pic = { bg: cs(t).backgroundColor, ink: cs(t).color, string: cs(leaf.querySelector('.jt-v')).color, top: rows.length, value: leaf.querySelector('.jt-v').textContent,
        count: arr.querySelector('summary .jt-c').textContent, arrOpen: arr.open, kids: arr.querySelectorAll(':scope > .jt-ch > details').length, firstOpen: first.open, firstDrawn: first.querySelectorAll('.jt-l').length,
        indent: first.getBoundingClientRect().left - arr.getBoundingClientRect().left, label: named ? named.querySelector('.jt-k').textContent : null, wantName,
        size: [t.clientHeight, t.scrollHeight, innerHeight] };
      return pic; }""")
    inner = tree.locator('.jt-ch > details').first
    inner.locator('summary').click()                                      # 접힌 마디를 누르면 그때 안쪽을 그린다
    inner.locator('.jt-l').first.wait_for(state='visible')
    leaves = inner.locator('.jt-l .jt-v').evaluate_all("ns => ns.map(n => [n.dataset.t, getComputedStyle(n).color])")
    seen['opened'], seen['colors'] = [t for t, _ in leaves], [c for _, c in leaves]
    assert seen['top'] == 3 and seen['value'] == '"COOLER_DEGRADATION"', seen      # 코드 값은 이름으로 바꾸지 않는다
    assert seen['wantName'] == '쿨러 상태' and seen['label'] == seen['wantName'], f"화면 사전에 있는 키는 한국어 이름표가 붙는다: {seen['label']!r}"
    assert (seen['count'], seen['arrOpen'], seen['kids']) == ('[80]', True, 80), seen
    assert seen['firstOpen'] is False and seen['firstDrawn'] == 0 and seen['indent'] > 8, f'더 깊은 마디는 접힌 채이고 안쪽은 펼 때 그린다: {seen}'
    assert seen['opened'] == ['number', 'string', 'boolean', 'null'], seen
    assert len(set(seen['colors'])) >= 3 and seen['string'] != seen['ink'], f'값의 종류마다 색이 다르다: {seen["colors"]}'
    assert seen['size'][0] < seen['size'][1] and seen['size'][0] <= seen['size'][2] / 2, f'긴 원문은 상자 안에서 스크롤된다: {seen["size"]}'
    light = page.evaluate("""c => { const x = document.createElement('canvas').getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 1, 1); x.fillStyle = c; x.fillRect(0, 0, 1, 1); return [...x.getImageData(0, 0, 1, 1).data].slice(0, 3); }""", seen['bg'])
    assert min(light) >= 235, f'원문 상자는 밝은 상자다(어두운 판이 아니다): {light}'


def test_JSON이_아닌_원문은_글_그대로_색으로_나뉜다(portal):
    page = portal
    box = draw(page, "UI.raw('MATCH (n:Asset {id: \"HYD-01\"}) RETURN n.name LIMIT 5', { lang: 'cypher' })")
    box.locator('summary').click()
    pre = box.locator('pre.code')
    pre.wait_for(state='visible')
    assert box.locator('[data-json-tree]').count() == 0 and pre.inner_text().startswith('MATCH (n:Asset')
    page.wait_for_function("() => document.querySelectorAll('#partsProbe pre.code .token').length > 3")       # 구문 강조(Prism)가 실제로 입혀졌다


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


def test_빈_상태는_한_덩어리_문장과_단추_하나이고_아이콘_상자와_굵은_제목이_없다(portal):
    """빈 상태(디자인기준 4-10): 「무엇이 아직 없는지 + 어떻게 하면 생기는지」 한 문단 + 그 일을 하는 단추 하나. 아이콘 상자 · 굵은 제목 · 따로 선 설명 줄을 그리지 않는다.
    부르는 쪽이 아이콘 이름을 주어도 그리지 않는다(부르는 법은 그대로다)."""
    page = portal
    box = draw(page, "UI.empty({ icon: 'inbox', title: '아직 처리 건이 없습니다', sub: '결함을 넣으면 생깁니다.', action: { label: '결함 시뮬레이션 열기', tab: 'scenario' } })")
    empty = box.locator('section.empty')
    assert empty.locator('figure, svg.ic:not(button svg), h1, h2, h3, h4, b, strong').count() == 0, '아이콘 상자 · 굵은 제목이 없다'
    assert empty.locator('p').count() == 1 and empty.locator('p').inner_text() == '아직 처리 건이 없습니다. 결함을 넣으면 생깁니다.'
    look = empty.evaluate("""e => { const p = e.querySelector('p'), b = e.querySelector('button'), cs = getComputedStyle(p), er = e.getBoundingClientRect(), pr = p.getBoundingClientRect(), br = b.getBoundingClientRect();
      return { weight: Number(cs.fontWeight), align: cs.textAlign, mid: Math.abs((pr.left + pr.right) / 2 - (er.left + er.right) / 2) < 1, below: br.top >= pr.bottom, buttons: e.querySelectorAll('button, a').length,
               muted: cs.color === getComputedStyle(document.querySelector('.page-head p')).color }; }""")
    assert look == {'weight': 400, 'align': 'center', 'mid': True, 'below': True, 'buttons': 1, 'muted': True}, look
    empty.locator('footer button').click()
    assert page.evaluate('() => state.tab') == 'scenario', '빈 상태의 단추가 그 화면을 연다'
    open_screen(page, 'main')
    # 목록 안의 한 줄 꼴(제목, 설명)도 같은 한 문단이고 단추가 없다. 제목이 문장으로 끝나면 마침표를 더하지 않는다
    box = draw(page, "UI.empty('이 종류가 없습니다', '「전체」를 고르면 보입니다.') + UI.empty('아직 답이 없습니다.', '질문을 보내면 여기에 쌓입니다.')")
    assert box.locator('figure, h3, footer').count() == 0
    assert box.locator('section.empty p').all_inner_texts() == ['이 종류가 없습니다. 「전체」를 고르면 보입니다.', '아직 답이 없습니다. 질문을 보내면 여기에 쌓입니다.']


def _paint(page, color):
    """색 글(oklch · color-mix · rgb)을 흰 바탕 위에 칠한 한 점의 [r, g, b] — 브라우저가 실제로 칠하는 값."""
    return page.evaluate("""c => { const x = document.createElement('canvas').getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 1, 1); x.fillStyle = c; x.fillRect(0, 0, 1, 1); return [...x.getImageData(0, 0, 1, 1).data].slice(0, 3); }""", color)


def _contrast(a, b):
    def lum(rgb):
        r, g, bl = [(v / 255 / 12.92) if v / 255 <= 0.03928 else ((v / 255 + 0.055) / 1.055) ** 2.4 for v in rgb]
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl
    hi, lo = max(lum(a), lum(b)), min(lum(a), lum(b))
    return (hi + 0.05) / (lo + 0.05)


def test_상태_알약은_점_없는_알약이고_상태마다_색이_다르며_글이_읽힌다(portal):
    """상태 알약(디자인기준 4-5 · 2-2): 앞에 점을 그리지 않는다. 보통 · 진행 중 · 정상 · 주의 · 실패 · 내 차례의 바탕이 서로 다르고, 글과 바탕의 대비가 4.5 이상이다.
    내 차례와 실패는 채운 알약(짙은 바탕 · 흰 글)이고 나머지는 옅은 바탕이다. 상태 코드는 UI.tones 표대로 색이 정해진다."""
    page = portal
    box = draw(page, "['neutral', 'accent', 'success', 'warning', 'danger', 'mine'].map(t => UI.chipText('상태 글 12', t)).join(' ') + UI.chip('FAILED') + UI.chip('IN_PROGRESS') + UI.chip('DONE') + UI.chip('PENDING') + UI.chip('TODO')")
    pills = box.locator('.tag').evaluate_all("""ns => ns.map(n => { const cs = getComputedStyle(n), dot = getComputedStyle(n, '::before');
      return { text: n.textContent, bg: cs.backgroundColor, ink: cs.color, dot: dot.content, h: n.getBoundingClientRect().height, round: parseFloat(cs.borderTopLeftRadius) >= n.getBoundingClientRect().height / 2,
               kids: n.children.length, size: parseFloat(cs.fontSize) }; })""")
    assert all(p['dot'] in ('none', 'normal') and p['kids'] == 0 for p in pills), f'알약 앞에 점이 없다: {[p["dot"] for p in pills]}'
    assert all(p['round'] and p['h'] == pills[0]['h'] and p['size'] == pills[0]['size'] for p in pills), pills
    tone = {name: (_paint(page, p['bg']), _paint(page, p['ink'])) for name, p in zip(['보통', '진행', '정상', '주의', '실패', '내 차례'], pills[:6])}
    assert len({tuple(bg) for bg, _ in tone.values()}) == 6, f'상태마다 바탕이 다르다: {tone}'
    low = {name: round(_contrast(bg, ink), 2) for name, (bg, ink) in tone.items() if _contrast(bg, ink) < 4.5}
    assert not low, f'글과 바탕의 대비가 4.5 아래인 알약: {low}'
    for name in ('실패', '내 차례'):                                           # 채운 알약: 바탕이 짙고 글이 희다
        assert sum(tone[name][0]) < sum(tone[name][1]), (name, tone[name])
    for name in ('보통', '진행', '정상', '주의'):                              # 옅은 알약: 바탕이 밝고 글이 짙다
        assert sum(tone[name][0]) > sum(tone[name][1]) and min(tone[name][0]) >= 190, (name, tone[name])
    by_code = {p['text']: p['bg'] for p in pills[6:]}
    assert [by_code['실패'], by_code['진행 중'], by_code['완료'], by_code['보류'], by_code['예정']] == [pills[4]['bg'], pills[1]['bg'], pills[2]['bg'], pills[3]['bg'], pills[0]['bg']]


def test_긴_글_접기는_140px에서_잘려_아래가_흐려지고_둥근_꺾쇠로_펼치면_전부_보인다(portal):
    """긴 글 접기(디자인기준 4-9 — UI.longText): 긴 글은 140px 까지만 보이고 아래가 흐려지며, 아래 가운데의 둥근 단추로 펼치면 전부 보인다. 다시 누르면 접힌다.
    140px 안에 다 들어가는 글에는 흐림도 단추도 없다. 높이는 브라우저에서 잰다."""
    page = portal
    long = "'<div class=\"prose\">' + Array.from({ length: 30 }, (_, i) => `<p>문단 ${i + 1} — 쿨러 팬 속도를 올린 뒤 15분 동안 유온을 다시 확인합니다.</p>`).join('') + '</div>'"
    box = draw(page, f"UI.longText({long}) + UI.longText('<p>짧은 글 한 줄</p>')")
    page.wait_for_function("() => document.querySelectorAll('#partsProbe [data-longtext]')[1].hasAttribute('data-fits')")      # 짧은 글은 잰 뒤에 「다 들어감」이 붙는다
    probe = """() => [...document.querySelectorAll('#partsProbe [data-longtext]')].map(b => { const body = b.querySelector('.longtext-body'), t = b.querySelector('.longtext-toggle'), cs = getComputedStyle(body),
        br = b.getBoundingClientRect(), tr = t.getBoundingClientRect(), last = body.querySelector('p:last-child');
      return { shown: Math.round(body.getBoundingClientRect().height), all: body.scrollHeight, fade: (cs.maskImage || cs.webkitMaskImage) !== 'none', button: t.checkVisibility(), expanded: t.getAttribute('aria-expanded'),
               round: tr.width === tr.height && parseFloat(getComputedStyle(t).borderTopLeftRadius) >= tr.width / 2, centered: Math.abs((tr.left + tr.right) / 2 - (br.left + br.right) / 2) < 1,
               atFoot: Math.abs(tr.bottom - br.bottom) < 1, lastSeen: last ? last.getBoundingClientRect().bottom <= body.getBoundingClientRect().bottom + 1 : true }; })"""
    closed, short = page.evaluate(probe)
    assert closed['shown'] == 140 and closed['all'] > 600 and closed['fade'] and closed['button'] and closed['expanded'] == 'false' and not closed['lastSeen'], closed
    assert closed['round'] and closed['centered'] and closed['atFoot'], f'둥근 단추가 아래 가운데에 있다: {closed}'
    assert short['shown'] == short['all'] < 140 and not short['fade'] and not short['button'], f'짧은 글은 자르지 않고 단추도 없다: {short}'
    box.locator('[data-longtext-toggle]').first.click()
    opened = page.evaluate(probe)[0]
    assert opened['shown'] == opened['all'] and not opened['fade'] and opened['expanded'] == 'true' and opened['lastSeen'], f'펼치면 전부 보인다: {opened}'
    box.locator('[data-longtext-toggle]').first.click()
    assert page.evaluate(probe)[0]['shown'] == 140


def test_단계_타임라인은_상태마다_점이_다르고_이음선이_점_가운데를_지나며_기계가_일할_때만_맥박친다(portal):
    """단계 타임라인(디자인기준 4-11 — UI.timeline): 점은 같은 크기의 원이고 끝남 · 지금 · 내 차례 · 실패 · 남음의 모양이 서로 다르다. 이음선은 점의 가운데 세로선을 지난다.
    맥박은 기계가 일하는 중(busy)인 지금 단계에만 있고, 사람을 기다리는 내 차례는 멈춘 모양이다. 갈림길은 돌린 사각이고 가지 않은 단계는 흐리다. 시각은 줄의 오른쪽 끝에 선다."""
    page = portal
    box = draw(page, """UI.timeline([{ state: 'done', name: '올리기', sub: '담당자 · HM-8 매뉴얼', time: '10:02' }, { state: 'now', busy: true, name: 'AI 추출', sub: '절 3/8을 읽는 중' },
      { state: 'mine', name: '조치 선택 · 승인', sub: '설비보전팀장' }, { state: 'fail', name: '설비에 명령' }, { state: 'done', gateway: true, name: '유온 정상?' }, { state: 'skip', name: '책임자 확인' }, { state: 'todo', name: '결과 보고' },
      { state: 'now', name: '효과 확인' }])""")
    steps = box.locator('.step').evaluate_all("""ns => ns.map(n => { const m = n.querySelector('.step-mark'), r = m.getBoundingClientRect(), cs = getComputedStyle(m), line = getComputedStyle(n, '::before'), row = n.getBoundingClientRect(),
        t = n.querySelector('.step-time'), title = n.querySelector('.step-title').getBoundingClientRect();
      return { state: n.dataset.state, w: Math.round(m.offsetWidth), h: Math.round(m.offsetHeight), look: cs.backgroundColor + '|' + cs.boxShadow, pulse: cs.animationName, radius: cs.borderTopLeftRadius, turn: cs.rotate,
               fade: parseFloat(getComputedStyle(n).opacity), lineMid: row.left + parseFloat(line.left) + parseFloat(line.width) / 2, markMid: row.left + m.offsetLeft + m.offsetWidth / 2, lineShown: line.display !== 'none',
               titleLeft: title.left, timeRight: t ? Math.round(row.right - t.getBoundingClientRect().right) : null, icon: m.querySelectorAll('svg').length }; })""")
    assert all((s['w'], s['h']) == (steps[0]['w'], steps[0]['h']) for s in steps) and steps[0]['w'] == steps[0]['h'], steps
    looks = {s['state']: s['look'] for s in steps[:4]} | {'todo': steps[6]['look']}
    assert len(set(looks.values())) == 5, f'끝남 · 지금 · 내 차례 · 실패 · 남음의 점이 서로 다르다: {looks}'
    assert [s['pulse'] != 'none' for s in steps] == [False, True, False, False, False, False, False, False], f'맥박은 기계가 일하는 지금 단계에만: {[s["pulse"] for s in steps]}'
    assert all(abs(s['lineMid'] - s['markMid']) < 0.6 for s in steps[:-1] if s['lineShown']) and steps[-1]['lineShown'] is False, steps
    assert steps[4]['turn'] not in ('none', '0deg') and steps[4]['radius'] != steps[0]['radius'], f'갈림길은 돌린 사각이다: {steps[4]}'
    assert steps[5]['fade'] < 1 and all(s['fade'] == 1 for i, s in enumerate(steps) if i != 5)
    assert len({round(s['titleLeft']) for s in steps}) == 1 and steps[0]['timeRight'] == 0 and steps[0]['icon'] == 1


def test_진행_막대는_센_값만큼만_차고_세그먼트는_고른_칸만_흰_알약이다(portal):
    """진행 막대(4-12 — UI.progress): 채움의 폭은 끝난 수 / 전체다. 세그먼트(4-6 — UI.tabs): 옅은 알약 안에서 고른 칸만 흰 알약이고 나머지는 바탕이 없다."""
    page = portal
    box = draw(page, "'<div style=\"width:400px\">' + UI.progress(3, 8, { label: '단계' }) + UI.progress(0, 5) + UI.progress(9, 4) + '</div>' + UI.tabs([['all', '전체', 12], ['mine', '내가 할 일', 2], ['done', '처리 완료', 7]], 'mine')")
    page.wait_for_timeout(900)                                            # 채움의 폭이 움직임을 마친 뒤에 잰다
    bars = box.locator('.pbar').evaluate_all("ns => ns.map(n => [n.firstElementChild.getBoundingClientRect().width / n.getBoundingClientRect().width, n.getAttribute('aria-valuenow'), n.getAttribute('aria-valuemax'), n.getBoundingClientRect().height])")
    assert [round(b[0], 2) for b in bars] == [0.38, 0, 1] and [(b[1], b[2]) for b in bars] == [('3', '8'), ('0', '5'), ('4', '4')], bars
    assert bars[0][3] <= 6, '진행 막대는 가는 선이다'
    seg = box.locator('.seg').evaluate("""s => { const cs = n => getComputedStyle(n), b = [...s.querySelectorAll('button')];
      return { box: cs(s).backgroundColor, on: b.filter(x => x.getAttribute('aria-pressed') === 'true').map(x => cs(x).backgroundColor), off: b.filter(x => x.getAttribute('aria-pressed') !== 'true').map(x => cs(x).backgroundColor),
               round: parseFloat(cs(b[1]).borderTopLeftRadius) >= b[1].offsetHeight / 2, oneLine: new Set(b.map(x => Math.round(x.getBoundingClientRect().top))).size === 1 }; }""")
    assert len(seg['on']) == 1 and seg['on'][0] not in seg['off'] + ['rgba(0, 0, 0, 0)'] and _paint(page, seg['on'][0]) == [255, 255, 255] and _paint(page, seg['box']) != [255, 255, 255], seg
    assert all(_paint(page, c) == _paint(page, seg['box']) or c == 'rgba(0, 0, 0, 0)' for c in seg['off']) and seg['round'] and seg['oneLine'], seg


def test_숫자_카드와_설정_줄과_더_보기는_정한_자리에_선다(portal):
    """숫자 카드(4-17 — UI.statCard): 설명 → 큰 숫자 → 아래 한 줄, 상태 알약은 오른쪽 위, 다른 화면으로 가는 카드는 맨 아래 고정 줄의 오른쪽 끝에 링크. 높이가 다른 글이 들어도 나란한 카드의 아래 줄은 같은 자리다.
    설정 줄(4-16 — UI.settingRow): 왼쪽 이름과 설명, 오른쪽 끝 동작 하나, 줄 사이에 선. 「N개 더 보기」(4-14 — UI.moreButton): 숨은 개수가 문구에 있다."""
    page = portal
    box = draw(page, """'<div class="stats" style="grid-template-columns:repeat(2,300px)">' + UI.statCard({ label: '진행 중인 처리 건', value: '2', unit: '건', note: '짧은 한 줄', pill: UI.chipText('내 차례 1', 'mine'), tab: 'instances', go: '처리 건' })
      + UI.statCard({ label: '지식 항목', value: '336', unit: '개', note: '두 줄이 되는 긴 설명입니다. 매뉴얼을 올리면 AI가 판단에 쓰는 지식이 되고 지식 지도에 놓입니다.', tab: 'knowledge' }) + '</div>'
      + '<div class="settings" style="width:600px">' + UI.settingRow({ title: '내보내기', desc: '내가 만든 것을 파일 하나로 받습니다.', action: UI.btn('export', { variant: 'outline' }) }) + UI.settingRow({ title: '불러오기', desc: '받아 둔 파일을 올립니다.', action: UI.btn('load', { variant: 'outline' }) }) + '</div>'
      + UI.moreButton(12, 'data-probe-more', { what: '처리 완료', unit: '건' }) + UI.moreButton(0)""")
    cards = box.locator('.stat').evaluate_all("""ns => ns.map(c => { const r = c.getBoundingClientRect(), y = s => { const n = c.querySelector(s); return n ? n.getBoundingClientRect() : null; }, pill = y('.stat-pill'), go = y('.go');
      return { order: [y('.stat-label').top, y('.stat-value').top, y('.stat-note').top, y('.stat-foot').top], pillRight: pill ? Math.round(r.right - pill.right) : null, pillTop: pill ? Math.round(pill.top - r.top) : null,
               labelTop: Math.round(y('.stat-label').top - r.top), goRight: Math.round(r.right - go.right), foot: Math.round(y('.stat-foot').top), bottom: Math.round(r.bottom), num: parseFloat(getComputedStyle(c.querySelector('.stat-value')).fontSize),
               noteSize: parseFloat(getComputedStyle(c.querySelector('.stat-note')).fontSize), href: c.getAttribute('href'), goText: c.querySelector('.go').textContent }; })""")
    assert all(c['order'] == sorted(c['order']) for c in cards), cards
    assert cards[0]['pillRight'] == cards[0]['goRight'] and abs(cards[0]['pillTop'] - cards[0]['labelTop']) <= 2, f'알약은 오른쪽 위, 링크는 오른쪽 아래 — 같은 오른쪽 선: {cards[0]}'
    assert cards[0]['foot'] == cards[1]['foot'] and cards[0]['bottom'] == cards[1]['bottom'], f'글 길이가 달라도 아래 고정 줄은 같은 자리다: {cards}'
    assert cards[0]['num'] > 1.8 * cards[0]['noteSize'] and [c['href'] for c in cards] == ['#/instances', '#/knowledge'] and cards[1]['goText'] == page.evaluate("() => UI.t('nav.knowledge')")
    rows = box.locator('.setting').evaluate_all("""ns => ns.map(n => { const r = n.getBoundingClientRect(), a = n.querySelector('.setting-act').getBoundingClientRect(), b = n.querySelector('b'), p = n.querySelector('p');
      return { actRight: Math.round(r.right - a.right), acts: n.querySelectorAll('.setting-act > *').length, titleLeft: Math.round(b.getBoundingClientRect().left - r.left), under: p.getBoundingClientRect().top >= b.getBoundingClientRect().bottom - 1,
               bold: Number(getComputedStyle(b).fontWeight) >= 600, line: parseFloat(getComputedStyle(n).borderTopWidth), mid: Math.abs((a.top + a.bottom) / 2 - (r.top + r.bottom) / 2) < 2 }; })""")
    assert rows[0] | {'line': 0} == {'actRight': 0, 'acts': 1, 'titleLeft': 0, 'under': True, 'bold': True, 'line': 0, 'mid': True} and rows[1]['line'] >= 1 and rows[1]['actRight'] == 0, rows
    more = box.locator('.more-link')
    assert more.count() == 1 and more.inner_text() == '처리 완료 12건 더 보기' and more.evaluate("b => getComputedStyle(b).borderTopWidth") == '0px'


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


def test_입력_칸에_id_가_없어도_이름표는_그_칸과_이어지고_다시_그려도_같은_id_다():
    """흐름의 시작 폼(교대 인수인계의 「설비」 · 「작업 메모」)처럼 id 없이 만든 입력은 이름표와 이어지지 않았다(for 없음) — 이름표를 눌러도 칸이 잡히지
    않고 화면 읽기 도구가 칸의 이름을 모른다. 폼 부품(UI.field)이 한 번에 잇는다."""
    from www_node import run
    got = run(['ui.js'], """const a = UI.field({ label: '작업 메모', input: '<textarea data-sv="work_notes" rows="4"></textarea>' });
      const b = UI.field({ label: '작업 메모', input: '<textarea data-sv="work_notes" rows="4"></textarea>' });
      const c = UI.field({ label: '설비', input: '<select data-sv="asset"><option>HYD-01</option></select>' });
      const d = UI.field({ label: '이름', input: '<input id="skName" data-id="x">' });
      const pair = h => [/<label for="([^"]+)"/.exec(h)[1], /<(?:textarea|select|input)[^>]*?\\sid="([^"]+)"/.exec(h)[1]];
      out([pair(a), pair(b), pair(c), pair(d)])""")
    (fa, ia), (fb, ib), (fc, ic), (fd, idd) = got
    assert fa == ia and fc == ic and ia != ic            # 이름표의 for = 그 칸의 id, 칸마다 다르다
    assert ia == ib                                      # 같은 칸은 다시 그려도 같은 id(HTML 이 달라져 다시 그리기가 헛돌지 않는다)
    assert fd == idd == 'skName'                         # 이미 id 가 있으면 그대로(data-id 를 id 로 읽지 않는다)


def test_다시_그려도_사람이_편_접기는_열린_채이고_처음_나온_접기만_HTML_의_기본을_따른다(portal):
    """처리 건의 복구 묶음([다시 수행] · 실행 효과)은 2초마다 다시 그려진다. 다시 그릴 때마다 접기가 기본값(닫힘)으로 돌아가 학생이 연 [다시 수행]이
    2초 안에 저절로 닫혔다 — 주기적으로 다시 그리는 자리는 UI.swap 으로 바꾼다."""
    page = portal
    got = page.evaluate("""() => { const host = document.createElement('div'); document.querySelector('main .view.active').prepend(host);
      const html = open => UI.fold('다시 수행', '<p>폼</p>', { open }) + UI.fold('실행 효과 <span class="tag">확인할 조치 2</span>', '<p>표</p>');
      UI.swap(host, html(false));
      const first = [...host.querySelectorAll('details')].map(d => d.open);
      host.querySelector('details').open = true;                          // 사람이 [다시 수행]을 편다
      UI.swap(host, html(false));                                         // 2초 뒤 다시 그리기(기본은 닫힘)
      const kept = [...host.querySelectorAll('details')].map(d => d.open);
      host.querySelectorAll('details')[0].open = false;                   // 사람이 다시 접는다
      UI.swap(host, html(true));                                          // 기본이 열림으로 바뀌어도 사람이 접은 것은 접힌 채
      const closed = [...host.querySelectorAll('details')].map(d => d.open);
      UI.swap(host, html(true) + UI.fold('새 접기', '<p>x</p>', { open: true }));
      const fresh = [...host.querySelectorAll('details')].map(d => d.open);
      host.remove(); return { first, kept, closed, fresh }; }""")
    assert got == {'first': [False, False], 'kept': [True, False], 'closed': [False, False], 'fresh': [False, False, True]}, got

