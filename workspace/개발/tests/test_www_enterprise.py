"""지식 지도 · 규칙 판단 · 업무 시스템 기록 화면(it/portal/www/enterprise.js).

- 업무 시스템 보드: 업무 상태(/api/state)가 주는 표만 그린다.
- 지식 지도(Cytoscape.js): 항목의 표시(고름 · 이어짐 · 경로 · 검색과 그 겹침), 이상 패턴 경로, 고른 항목 둘레에 이웃을 모으는 자리와 그 자리를 비켜 주는 자리를
  정하는 판정이 정해진 대로다. 마지막 시험은 실제 브라우저에서 점을 눌러 보고 — 이웃이 고른 점 둘레에 모이는지, 고름을 풀면 제자리로 돌아가는지, 같은 그래프가
  늘 같은 자리에 놓이는지, 겹친 상태의 글자가 캔버스 바탕과 대비되는지, 관계 이름이 한국어인지를 잰다.

enterprise.js 는 실릴 때 화면 요소를 찾으므로 node 시험은 브라우저 쪽만 최소 대역(요소 · 탭 표)으로 두고 실제 모듈을 싣는다."""
import json
import math
import re

import pytest
from conftest import ROOT
from www_node import run

# 브라우저 대역: 어떤 요소를 찾아도 같은 빈 요소, 바깥 요청은 실패. 화면 모듈 코드는 그대로 돈다
PRELUDE = r"""
const __fakeNode = () => new Proxy({ addEventListener() {}, append() {}, querySelector: () => __fakeNode(), querySelectorAll: () => [], classList: { toggle() {}, add() {} },
  dataset: {}, style: {}, value: '', innerHTML: '' }, { get: (t, k) => k in t ? t[k] : () => __fakeNode() });
globalThis.document = { getElementById: __fakeNode, querySelector: __fakeNode, querySelectorAll: () => [], createElement: __fakeNode, readyState: 'complete', addEventListener() {} };
globalThis.$ = () => __fakeNode(); globalThis.el = __fakeNode; globalThis.state = { tab: 'main' }; globalThis.selectTab = () => {};
globalThis.hydTabs = { onShow() {} }; globalThis.getJ = () => Promise.reject(new Error('대역')); globalThis.postJ = globalThis.getJ;
globalThis.keyboardItem = () => {}; globalThis.ResizeObserver = class { observe() {} }; globalThis.CSS = { escape: s => s }; globalThis.fmt = v => String(v); globalThis.API = { agent: '', process: '', ent: '' };
"""
FILES = ['ui.js', 'plainWords.js', 'approvalCard.js', 'enterprise.js']
STATE = {'mes': {'orders': [{'order_id': 'MO-1', 'asset': 'HYD-01', 'due_in_h': 30}]},
         'cmms': {'work_orders': [{'id': 'WO-1', 'asset': 'HYD-01', 'task': '핀 세척', 'window': '야간'}]},
         'erp': {'purchase_requests': [{'id': 'PR-1', 'supplierName': 'B-OEM', 'status': 'ORDERED'}],
                 'goods_receipts': [{'id': 'GR-1', 'part_no': 'P-SEAL', 'qty': 2, 'inspection': '합격'}]}}


def test_업무_보드는_지금_업무_상태의_표만_읽고_뺀_칸이_없어도_그린다():
    """FE 070이 대체 출하 · 로트 처분 · 전력 칸을 /api/state에서 뺐다 — 화면이 erp.shipments 를 읽으면 보드 전체가 멈췄다."""
    got = run(FILES, "out(hydEnt.systemBoards(DATA).map(([sys, rows]) => [sys, rows.map(r => r.a || r.order_id || r.id)]))", STATE, prelude=PRELUDE)
    assert got == [['생산 관리', ['MO-1']], ['정비 관리', ['WO-1']], ['구매 · 재고 관리', ['PR-1', 'GR-1']]]


def test_구매_카드의_공급사는_그_카드가_정한_견적의_업무_DB_이름으로_보이고_다른_공급사는_그대로다():
    """넘김 FW → FT 덧: 공급사(sup:*)는 이름 사전에 없어 조치 줄이 「구매 요청 sup:c」로 보였다 — 카드가 정한 공급사(resolvedSupplier)의 견적 이름이 정본."""
    option = {'resolvedSupplier': {'id': 'sup:c', 'quote': {'name': '대성유압'}}}
    got = run(FILES, "out([hydCards.actionLabel({ code: 'PR_CREATE', value: 'sup:c' }, DATA), hydCards.actionLabel({ code: 'PR_CREATE', value: 'sup:a' }, DATA)])",
              option, prelude=PRELUDE)
    assert got == ['구매 요청 대성유압', '구매 요청 sup:a']


def test_관계_종류마다_따로_쓴_한국어_이름이_있어_다른_관계를_같은_이름으로_읽지_않는다():
    """오른쪽 판은 이어진 항목을 관계 이름으로 묶어 보인다 — 유온 센서 판에서 쿨러 쪽(MONITORED_BY)과 증상 쪽(OBSERVED_BY) 묶음이 둘 다
    「관측 센서」로 보여, 서로 다른 관계 유형을 같은 관계로 읽게 했다. 스키마의 관계 종류마다 이름이 있고, 두 종류가 한 이름을 함께 쓰지 않는다."""
    names = run(FILES, "out(RELATION_KO)", prelude=PRELUDE)
    types = [r['type'] for r in json.loads((ROOT / 'it' / 'neo4j' / 'v2' / 'schema.json').read_text(encoding='utf-8'))['relationships']]
    assert [t for t in types if not names.get(t)] == []
    shared = {}
    for t, name in names.items():
        shared.setdefault(name, []).append(t)
    assert {name: ts for name, ts in shared.items() if len(ts) > 1} == {}
    assert names['MONITORED_BY'] == '감시 센서' and names['OBSERVED_BY'] == '관측 센서'


# ------------------------------------------------------------------ 지식 지도의 판정(DOM 없이 도는 부분)
STATE_CASES = [
    # (설명, 상태, 항목 → 표시)
    ('아무것도 고르지 않음', dict(sel=None, near=[], path=None, match=[], query=False), {'a': [], 'b': []}),
    ('고름: 고른 것 · 이어진 것은 밝고 나머지는 흐리다', dict(sel='a', near=['b'], path=None, match=[], query=False), {'a': ['pick'], 'b': ['near'], 'c': ['dim']}),
    ('검색: 걸린 것만 밝다', dict(sel=None, near=[], path=None, match=['b'], query=True), {'a': ['dim'], 'b': ['hit']}),
    ('검색 결과가 없어도 검색 중이면 모두 흐리다', dict(sel=None, near=[], path=None, match=[], query=True), {'a': ['dim']}),
    ('겹침: 고른 것이 검색에도 걸렸다', dict(sel='a', near=['b'], path=None, match=['a', 'b'], query=True), {'a': ['pick', 'hit'], 'b': ['near', 'hit'], 'c': ['dim']}),
    ('이상 패턴 경로', dict(sel=None, near=[], path=['a', 'b'], match=[], query=False), {'a': ['path'], 'b': ['path'], 'c': ['dim']}),
    ('겹침: 경로 위의 항목을 고르고 검색에도 걸렸다', dict(sel='a', near=['c'], path=['a', 'b'], match=['a', 'd'], query=True),
     {'a': ['pick', 'path', 'hit'], 'b': ['path'], 'c': ['near'], 'd': ['hit'], 'e': ['dim']}),
]
MARK_JS = """const s = { sel: DATA.s.sel, near: new Set(DATA.s.near), path: DATA.s.path && new Set(DATA.s.path), match: new Set(DATA.s.match), query: DATA.s.query };
out({ nodes: Object.fromEntries(DATA.ids.map(id => [id, hydEnt.kgMarks(id, s)])), edges: DATA.pairs.map(([a, b, type]) => hydEnt.kgEdgeMarks(a, b, s, type)) })"""


@pytest.mark.parametrize('said, s, want', STATE_CASES, ids=[c[0] for c in STATE_CASES])
def test_항목의_표시는_고름_이어짐_경로_검색과_그_겹침을_가른다(said, s, want):
    got = run(FILES, MARK_JS, {'s': s, 'ids': sorted(want), 'pairs': []}, prelude=PRELUDE)
    assert got['nodes'] == want


def test_선은_고른_항목에_닿으면_밝고_경로의_관계면_경로_선이며_그_밖은_상태가_있을_때만_흐리다():
    pairs = [['a', 'b', 'DETECTS'], ['b', 'c', 'INDICATES'], ['c', 'd', 'HAS_STEP']]
    marks = lambda s: run(FILES, MARK_JS, {'s': s, 'ids': [], 'pairs': pairs}, prelude=PRELUDE)['edges']
    assert marks(dict(sel=None, near=[], path=None, match=[], query=False)) == [[], [], []]
    assert marks(dict(sel='b', near=['a', 'c'], path=None, match=[], query=False)) == [['near'], ['near'], ['dim']]
    # 두 끝이 경로 안이어도 경로의 관계(감지 증상 · 나타내는 고장 …)가 아니면 길로 치지 않는다 — 조치 방법끼리 · 원인과 조치 방법 사이의 선이 길을 가리지 않게
    assert marks(dict(sel=None, near=[], path=['a', 'b', 'c', 'd'], match=[], query=False)) == [['path'], ['path'], ['dim']]
    assert marks(dict(sel='a', near=['b'], path=['b', 'c'], match=[], query=False)) == [['near'], ['path'], ['dim']]      # 고른 항목에 닿은 선이 경로보다 앞선다
    assert marks(dict(sel=None, near=[], path=None, match=['a'], query=True)) == [['dim'], ['dim'], ['dim']]


SMALL = {'nodes': [{'id': 'pattern:cool', 'label': 'AnomalyPattern', 'name': '쿨러 성능 저하', 'props': {'description': '냉각 효율이 떨어져 유온이 오르는 패턴', 'severity': 'HIGH'}},
                   {'id': 'sym:hot', 'label': 'Symptom', 'name': '유온 상승', 'props': {}}, {'id': 'sym:ce', 'label': 'Symptom', 'name': '냉각 효율 저하', 'props': {}},
                   {'id': 'fm:cool', 'label': 'FailureMode', 'name': '쿨러 냉각 성능 상실', 'props': {}}, {'id': 'cause:fin', 'label': 'Cause', 'name': '쿨러 핀 오염', 'props': {}},
                   {'id': 'skill:fan', 'label': 'Skill', 'name': '팬 최대 운전', 'props': {'sopId': 'SOP-COOL-11'}},
                   {'id': 'skill:wash', 'label': 'Skill', 'name': '쿨러 핀 세척', 'props': {}}, {'id': 'role:op', 'label': 'Role', 'name': '운전원', 'props': {}},
                   {'id': 'obj:up', 'label': 'Objective', 'name': '설비 가용성 확보', 'props': {}}, {'id': 'comp:fan', 'label': 'Component', 'name': '쿨러 팬', 'props': {}}],
         'edges': [{'from': 'pattern:cool', 'to': 'sym:hot', 'type': 'DETECTS'}, {'from': 'pattern:cool', 'to': 'sym:ce', 'type': 'DETECTS'}, {'from': 'sym:hot', 'to': 'fm:cool', 'type': 'INDICATES'},
                   {'from': 'cause:fin', 'to': 'fm:cool', 'type': 'CAUSES'}, {'from': 'fm:cool', 'to': 'skill:fan', 'type': 'MITIGATED_BY'}, {'from': 'fm:cool', 'to': 'skill:wash', 'type': 'REMEDIED_BY'},
                   {'from': 'skill:fan', 'to': 'role:op', 'type': 'APPROVED_BY'}, {'from': 'skill:fan', 'to': 'comp:fan', 'type': 'TARGETS'}, {'from': 'skill:wash', 'to': 'cause:fin', 'type': 'ADDRESSES'}]}


def test_이상_패턴_경로는_패턴에서_증상_고장_유형_원인_조치_방법까지이고_없는_패턴은_경로가_없다():
    got = run(FILES, "const p = hydEnt.kgPath(DATA, 'pattern:cool'); out({ ids: [...p.ids].sort(), symptoms: p.symptoms, modes: p.modes, causes: p.causes, skills: p.skills, none: hydEnt.kgPath(DATA, 'pattern:none'), off: hydEnt.kgPath(DATA, null) })",
              SMALL, prelude=PRELUDE)
    assert got['symptoms'] == ['sym:hot', 'sym:ce'] and got['modes'] == ['fm:cool'] and got['causes'] == ['cause:fin'] and got['skills'] == ['skill:fan', 'skill:wash']
    assert got['ids'] == sorted(['pattern:cool', 'sym:hot', 'sym:ce', 'fm:cool', 'cause:fin', 'skill:fan', 'skill:wash'])      # 승인 역할 · 대상 부품 · 전략 목표는 길이 아니다
    assert got['none'] is None and got['off'] is None


def test_이어진_것은_방향과_관계로_묶이고_많은_묶음이_먼저다():
    got = run(FILES, "out(hydEnt.kgRelGroups(DATA.edges, 'fm:cool'))", SMALL, prelude=PRELUDE)
    assert got == {'out': [['MITIGATED_BY', ['skill:fan']], ['REMEDIED_BY', ['skill:wash']]], 'inn': [['CAUSES', ['cause:fin']], ['INDICATES', ['sym:hot']]]}
    got = run(FILES, "out(hydEnt.kgRelGroups(DATA.edges, 'pattern:cool'))", SMALL, prelude=PRELUDE)
    assert got == {'out': [['DETECTS', ['sym:hot', 'sym:ce']]], 'inn': []}


GATHER_JS = "const g = hydEnt.kgGather(DATA.c, DATA.left, DATA.right, DATA.box); out({ at: Object.fromEntries(g.at), labelW: g.labelW, bounds: g.bounds })"


def test_이웃은_고른_항목의_왼쪽과_오른쪽_호에_세로로_놓이고_이름을_쓸_간격을_지킨다():
    """견본의 흠: 고르면 이웃이 제자리에 남아 선이 길어졌다. 이웃은 고른 항목 둘레(호)로 모이고, 이름을 한 줄씩 쓸 수 있게 세로 간격이 17px 이상이다."""
    c, box = {'x': 1000, 'y': 500}, {'w': 764, 'h': 698}
    left, right = ['head:L:RAISED_BY', 'l1', 'l2'], ['head:R:TESTS'] + [f'r{i}' for i in range(20)] + ['head:R:IMPLEMENTED_BY', 'r20']
    got = run(FILES, GATHER_JS, {'c': c, 'left': left, 'right': right, 'box': box}, prelude=PRELUDE)
    at = got['at']
    assert set(at) == set(left + right)
    assert all(at[i]['side'] == 'L' and at[i]['x'] < c['x'] - 90 for i in left) and all(at[i]['side'] == 'R' and at[i]['x'] > c['x'] + 90 for i in right)
    for ids in (left, right):                                             # 받은 차례대로 위에서 아래로, 줄 사이는 17 ~ 26
        ys = [at[i]['y'] for i in ids]
        gaps = [b - a for a, b in zip(ys, ys[1:])]
        assert all(17 - 1e-6 <= g <= 26 + 1e-6 for g in gaps), gaps
        assert abs((ys[0] + ys[-1]) / 2 - c['y']) < 1                     # 고른 항목의 높이를 가운데로
    # 모은 것 전체(이름 폭 포함)가 캔버스 폭 안에 들어온다 — 화면이 고른 것과 이웃을 다 보이게 옮길 수 있다
    b = got['bounds']
    assert b['x1'] - b['x0'] <= box['w'] and all(b['x0'] <= p['x'] <= b['x1'] and b['y0'] <= p['y'] <= b['y1'] for p in at.values())
    assert max(math.dist((p['x'], p['y']), (c['x'], c['y'])) for p in at.values()) < 420      # 이웃은 고른 항목 가까이에 있다(선이 짧다)
    # 좁은 캔버스(휴대폰 폭): 이름 폭을 줄여서라도 캔버스 안에 넣는다
    small = run(FILES, GATHER_JS, {'c': c, 'left': left, 'right': right[:6], 'box': {'w': 358, 'h': 440}}, prelude=PRELUDE)
    assert small['bounds']['x1'] - small['bounds']['x0'] <= 358 + 1 and 56 <= small['labelW'] < got['labelW']
    # 한 줄에 다 못 놓을 만큼 많으면 바깥쪽에 줄을 더하고, 관계 이름 줄을 줄의 맨 끝에 혼자 남기지 않는다
    many = ['head:R:A'] + [f'a{i}' for i in range(33)] + ['head:R:B'] + [f'b{i}' for i in range(30)]
    wide = run(FILES, GATHER_JS, {'c': c, 'left': [], 'right': many, 'box': box}, prelude=PRELUDE)['at']
    cols = {}
    for i in many:
        cols.setdefault(round(wide[i]['x'] - 210 * math.sqrt(max(0, 1 - ((wide[i]['y'] - c['y']) / 300) ** 2))), None)
    xs_of = lambda i: wide[i]['x']
    assert xs_of('b29') - xs_of('a0') > 150                                # 뒤의 것은 바깥 줄에 있다
    below_head = [i for i in many if not i.startswith('head:') and abs(wide[i]['y'] - wide['head:R:B']['y'] - 17) < 10 and abs(wide[i]['x'] - wide['head:R:B']['x']) < 60]
    assert below_head, '관계 이름 줄 아래에 그 묶음의 첫 이웃이 같은 줄에 있어야 한다'


def test_모은_자리에_있던_다른_항목은_상자_밖으로_비켜_나고_먼_항목은_제자리다():
    js = "out(DATA.pts.map(p => hydEnt.kgMakeRoom(DATA.c, DATA.box, p)))"
    c, box = {'x': 0, 'y': 0}, {'x0': -300, 'x1': 300, 'y0': -200, 'y1': 200}
    pts = [{'x': 10, 'y': 0}, {'x': 150, 'y': 0}, {'x': 299, 'y': 0}, {'x': 0, 'y': -100}, {'x': 320, 'y': 0}, {'x': 700, 'y': 0}, {'x': 0, 'y': 0}, {'x': 200, 'y': 150}]
    got = run(FILES, js, {'c': c, 'box': box, 'pts': pts}, prelude=PRELUDE)
    inside = lambda p: box['x0'] < p['x'] < box['x1'] and box['y0'] < p['y'] < box['y1']
    assert not any(inside(p) for p in got), got                             # 상자 안에 남는 것이 없다
    assert got[5] == {'x': 700, 'y': 0}                                     # 상자에서 먼 항목은 그대로
    assert got[0]['x'] < got[1]['x'] < got[2]['x'] < got[4]['x'] < 700      # 같은 방향에서는 거리의 차례가 바뀌지 않는다(포개지지 않는다)
    assert got[3]['x'] == 0 and got[3]['y'] < -200                          # 방향은 그대로


# ------------------------------------------------------------------ 실제 브라우저: 눌러서 고르고, 검색하고, 겹친 상태의 글자가 읽히는지 잰다
# 그림 속 글자색(Cytoscape 가 그 항목에 계산한 색)과 캔버스 바탕색으로 WCAG 대비를 잰다. 글자가 실제로 그려지는 항목만(안 보이거나 확대해야 보이는 이름은 뺀다)
CONTRAST_JS = r"""() => {
  const parse = c => { const m = /^rgba?\(([^)]+)\)/.exec(c); if (!m) throw new Error('모르는 색: ' + c); return m[1].split(/[, /]+/).slice(0, 3).map(Number); };
  const lum = c => { const [r, g, b] = parse(c).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const cy = hydEnt.kg.cy, bg = lum(getComputedStyle(document.querySelector('.kg-canvas')).backgroundColor), z = cy.zoom();
  return cy.nodes().filter(n => n.visible() && n.style('label') && Number(n.style('text-opacity')) > 0 && Number(n.style('opacity')) > 0.5
      && parseFloat(n.style('font-size')) * z >= parseFloat(n.style('min-zoomed-font-size'))).map(n => {
    const L = lum(n.style('color')); return { id: n.id(), text: n.style('label'), cls: n.classes().join(' '), px: +(parseFloat(n.style('font-size')) * z).toFixed(1),
      ratio: +((Math.max(L, bg) + 0.05) / (Math.min(L, bg) + 0.05)).toFixed(2) }; });
}"""
POS_JS = "() => Object.fromEntries(hydEnt.kg.cy.nodes().filter(n => !n.hasClass('gtitle') && !n.hasClass('rhead')).map(n => [n.id(), [Math.round(n.position('x')), Math.round(n.position('y'))]]))"


def serve_onto(holder, width=1366):
    """holder['graph'] = 그래프 응답. 시험이 바꾸고 [다시 읽기]를 누르면 새 그래프가 온다."""
    import json

    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from playwright.sync_api import sync_playwright

    from conftest import WWW, Served, open_screen
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    give = lambda body: (lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(body, ensure_ascii=False)))
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': width, 'height': 768})
            page.route('**/svc/**', lambda route: route.abort('connectionrefused'))
            page.route('**/svc/agent/api/ontology/graph**', lambda route: give(holder['graph'])(route))
            page.route('**/svc/agent/api/ontology/patterns', give([{'id': 'pattern:cool', 'code': 'COOLER_DEGRADATION', 'name': '쿨러 성능 저하', 'failureModes': ['쿨러 냉각 성능 상실']}]))
            page.route('**/svc/agent/api/ontology/namespaces', give([]))
            page.route('**/svc/process/api/process/definitions', give([]))
            page.route('**/svc/plant-sim/api/state', give({'units': {'HYD-01': {}, 'HYD-02': {}}}))      # 설비 고르기의 목록은 가상 설비 서비스가 준다
            page.goto(served.url + '/index.html')
            page.wait_for_function('() => window.hydEnt && window.hydMenu')
            open_screen(page, 'ontology')
            page.wait_for_function("() => hydEnt.kg.cy && hydEnt.kg.cy.nodes().length > 0")
            yield page
            b.close()
    finally:
        served.close()


HOLDER = {'graph': SMALL}      # 그래프 응답(시험이 바꾸고 [다시 읽기]를 누른다)


@pytest.fixture
def onto():
    """서비스 없이 화면 파일만 낸 포털의 지식 지도. 그래프 · 이상 패턴 · 지식 묶음 · 흐름 이름 응답만 이 시험이 주고 그 밖의 서비스 요청은 끊는다.
    시험마다 브라우저를 새로 띄운다 — 한 브라우저를 세 시험이 이어 쓰면, 부하로 한 시험의 브라우저가 죽었을 때 뒤 시험이 함께 실패하고 앞 시험이 남긴 그래프 · 화면 상태에 기댄다."""
    HOLDER['graph'] = SMALL
    yield from serve_onto(HOLDER)


def marks(page):
    return page.evaluate("() => Object.fromEntries(hydEnt.kg.cy.nodes().filter(n => !n.hasClass('gtitle') && !n.hasClass('rhead')).map(n => [n.id(), ['pick', 'near', 'path', 'hit', 'dim', 'off'].filter(c => n.hasClass(c)).join(' ')]))")


def settle(page):
    """항목 · 화면이 옮겨 가기를 다 마칠 때까지 기다린다. 정해 둔 시간(0.5초)만 기다리면 부하가 걸린 PC에서 움직임(0.34 ~ 0.38초)이 그 안에 끝나지 않아
    옮겨 가는 도중의 자리를 재게 된다 — 움직임이 실제로 멎은 것을 확인한 뒤, 이름을 다시 고를 틈(멎고 0.09 ~ 0.44초 뒤)을 둔다."""
    page.wait_for_timeout(120)
    page.wait_for_function("() => { const cy = hydEnt.kg.cy; return !!cy && !cy.animated() && !cy.nodes().some(n => n.animated()); }", timeout=20000)
    page.wait_for_timeout(480)


def tap(page, node):
    """그림의 점을 실제로 누른다(캔버스 안 그 점의 화면 자리를 마우스로)."""
    settle(page)                                                            # 점이 아직 옮겨 가는 중이면 누를 자리가 어긋난다
    at = page.evaluate("id => { const p = hydEnt.kg.cy.getElementById(id).renderedPosition(), b = document.getElementById('ontoMap').getBoundingClientRect(); return [b.left + p.x, b.top + p.y]; }", node)
    page.mouse.click(*at)
    settle(page)


# 오른쪽 판과 캔버스의 폭: side = 판의 폭(닫혀 있으면 0), map = 캔버스 자리의 폭, frame = 두 칸 틀의 폭, cy = 그림이 아는 캔버스 폭
SIDE_JS = "() => { const w = s => document.querySelector(s).getBoundingClientRect().width; return { side: w('#ontoNode'), map: w('#ontoMap'), frame: w('#view-ontology .kg'), cy: hydEnt.kg.cy.width() }; }"


def test_지식_지도를_눌러_고르면_이웃이_모이고_겹친_상태에서도_글자가_읽히며_풀면_제자리로_돌아간다(onto):
    """「요소를 클릭하면 글자가 흰색이 되어 안 보인다」(고른 것 + 검색에 걸린 것이 겹칠 때)와 「고르면 이웃이 흩어져 선이 길다」를 실제 화면에서 잰다."""
    page = onto
    low = lambda: [x for x in page.evaluate(CONTRAST_JS) if x['ratio'] < 4.5]
    home = page.evaluate(POS_JS)
    assert set(marks(page).values()) == {''} and not low() and page.inner_text('#ontoStats') == '항목 10 · 연결 9'
    # 설비 고르기는 서버가 준 설비 목록이다(화면에 적어 둔 이름이 아니다)
    assert page.locator('#ontoAsset option').all_inner_texts() == ['HYD-01', 'HYD-02']
    # 아무것도 고르지 않았을 때 오른쪽 판은 닫혀 있고 캔버스가 틀의 폭을 다 쓴다(디자인 기준 6-3) — 무엇을 누르면 되는지는 캔버스 아래 안내 한 줄이 말하고,
    # 묶음의 목록(이름 · 수)은 캔버스 아래 조각 한 곳에만 있다(같은 목록을 두 곳에 두지 않는다)
    shut = page.evaluate(SIDE_JS)
    assert shut['side'] == 0 and abs(shut['map'] - shut['frame']) <= 1 and abs(shut['cy'] - shut['map']) <= 1, shut
    assert page.is_hidden('#ontoNode') and '점을 누르면' in page.inner_text('#ontoHint')
    assert len([t for t in page.locator('#view-ontology .cv-chip').all_inner_texts() if '설비 진단' in t]) == 1, '묶음 목록은 캔버스 아래 조각에 있다'
    z0 = page.evaluate('hydEnt.kg.cy.zoom()')
    # 지도의 묶음 이름을 누르면 그 묶음의 항목 이름이 종류별로 다 보이고 지도는 그 묶음만 밝게 크게 보인다
    page.evaluate("() => hydEnt.kg.cy.nodes('.gtitle').filter(n => n.data('g') === 'diagnosis').emit('tap')")
    settle(page)
    # 고른 것이 생기면 오른쪽 판이 열리고, 캔버스는 그만큼 좁아진 폭을 곧바로 안다(이웃을 모으는 자리와 화면 옮기기가 열린 뒤의 폭으로 정해진다)
    wide = page.evaluate(SIDE_JS)
    assert wide['side'] >= 300 and abs(wide['map'] + wide['side'] - wide['frame']) <= 2 and abs(wide['cy'] - wide['map']) <= 1, wide
    opened = page.inner_text("#ontoNode")
    assert '증상\n2' in opened and all(name in opened for name in ('쿨러 성능 저하', '유온 상승', '냉각 효율 저하', '쿨러 냉각 성능 상실', '쿨러 핀 오염'))
    got = marks(page)
    assert got['fm:cool'] == '' and got['skill:fan'] == 'dim' and got['obj:up'] == 'dim' and page.evaluate('hydEnt.kg.cy.zoom()') > z0
    page.click("#ontoNode [data-kg-group-close]")      # 닫으면 전체로 — 판도 닫히고 캔버스가 다시 폭을 다 쓴다
    settle(page)
    assert set(marks(page).values()) == {''} and abs(page.evaluate('hydEnt.kg.cy.zoom()') - z0) < 1e-6
    assert page.evaluate(SIDE_JS) == shut
    # 눌러서 고름: 고른 것 · 바로 이어진 것만 밝고 나머지는 흐리다. 오른쪽 칸에 묶음 · 종류 → 이름 → ID → 속성 → 이어진 것이 나온다
    tap(page, 'fm:cool')
    assert marks(page) == {'pattern:cool': 'dim', 'sym:hot': 'near', 'sym:ce': 'dim', 'fm:cool': 'pick', 'cause:fin': 'near', 'skill:fan': 'near', 'skill:wash': 'near', 'role:op': 'dim', 'obj:up': 'dim', 'comp:fan': 'dim'}
    assert not low()
    panel = page.inner_text('#ontoNode')
    assert page.evaluate(SIDE_JS)['side'] >= 300
    assert '설비 진단 · 고장 유형' in panel and page.inner_text('#ontoNode h2') == '쿨러 냉각 성능 상실' and 'fm:cool' in panel and '팬 최대 운전' in panel
    # 이웃이 고른 점 둘레에 모였다: 고른 점은 제자리, 이 항목을 가리키는 것은 왼쪽 · 이 항목이 가리키는 것은 오른쪽, 모두 가까이
    now = page.evaluate(POS_JS)
    c = now['fm:cool']
    assert c == home['fm:cool']
    assert now['sym:hot'][0] < c[0] and now['cause:fin'][0] < c[0] and now['skill:fan'][0] > c[0] and now['skill:wash'][0] > c[0]
    assert all(math.dist(now[i], c) < 260 for i in ('sym:hot', 'cause:fin', 'skill:fan', 'skill:wash')), now
    # 고른 것과 이웃이 모두 캔버스 안에 보인다(화면이 옮겨 갔다)
    box = page.locator('#ontoMap').bounding_box()
    seen = page.evaluate("ids => ids.map(id => { const p = hydEnt.kg.cy.getElementById(id).renderedPosition(); return [p.x, p.y]; })", ['fm:cool', 'sym:hot', 'cause:fin', 'skill:fan', 'skill:wash'])
    assert all(0 < x < box['width'] and 50 < y < box['height'] - 50 for x, y in seen), seen
    # 관계 이름은 한국어다(영문 관계 종류를 그대로 내지 않는다) — 캔버스의 관계 이름 줄과 오른쪽 칸 모두
    heads = page.evaluate("() => hydEnt.kg.cy.nodes('.rhead').map(n => n.data('name'))")
    assert sorted(heads) == sorted(['→ 완화 조치', '→ 근본 조치', '일으키는 고장 →', '나타내는 고장 →'])
    assert not re.search(r'[A-Z]{3,}_?[A-Z]*', ' '.join(heads) + page.inner_text('#ontoNode .node-sec:has(.rel-group)'))
    # 겹침: 고른 채로 이름을 검색한다 — 고른 것이 검색에도 걸린다. 고른 것 · 검색에 걸린 것 · 둘 다인 것의 글자가 모두 그려지고 읽힌다
    page.fill('#ontoSearch', '쿨러')
    settle(page)                                                            # 흐리던 항목이 밝아지고(0.18초) 이름을 다시 고른 뒤
    got = marks(page)
    assert got['fm:cool'] == 'pick hit' and got['pattern:cool'] == 'hit' and got['skill:wash'] == 'near hit' and got['sym:hot'] == 'near' and got['role:op'] == 'dim'
    seen = {x['id']: x for x in page.evaluate(CONTRAST_JS)}
    assert not [x for x in seen.values() if x['ratio'] < 4.5], seen
    assert {'fm:cool', 'pattern:cool', 'skill:wash', 'sym:hot'} <= set(seen) and all(seen[i]['px'] >= 11.5 for i in ('fm:cool', 'pattern:cool', 'skill:wash', 'sym:hot')), seen
    assert '검색 결과 5개' in page.inner_text('#ontoStats') and page.is_visible('#ontoNext')
    # 오른쪽 칸의 이어진 항목을 누르면 그 항목이 골라지고, 이웃이 새로 고른 점 둘레에 모인다
    page.click("#ontoNode [data-go='skill:fan']")
    settle(page)
    assert marks(page)['skill:fan'] == 'pick' and page.inner_text('#ontoNode h2') == '팬 최대 운전'
    now = page.evaluate(POS_JS)
    assert now['skill:fan'] == home['skill:fan'] and all(math.dist(now[i], now['skill:fan']) < 260 for i in ('fm:cool', 'role:op', 'comp:fan'))
    # 고른 항목을 다시 누르면 풀리고, 검색을 지우면 처음 모양으로 — 모든 항목이 제자리로 돌아간다
    tap(page, 'skill:fan')
    page.fill('#ontoSearch', '')
    settle(page)
    assert set(marks(page).values()) == {''} and page.is_hidden('#ontoNext') and page.evaluate(POS_JS) == home
    assert page.is_hidden('#ontoNode')                                      # 고른 것이 없으면 판은 다시 닫힌다
    assert page.evaluate("() => hydEnt.kg.cy.nodes('.rhead').length") == 0
    # 찾기 칸에서 Enter: 걸린 항목을 차례로 고른다
    page.fill('#ontoSearch', '유온')
    page.press('#ontoSearch', 'Enter')
    settle(page)
    assert marks(page)['sym:hot'] == 'pick hit' and not low()
    page.fill('#ontoSearch', '')
    page.keyboard.press('Escape')                                           # 찾기 칸의 Esc 는 지도에 닿지 않는다 — 지도에 초점을 두고 Esc 로 푼다
    page.focus('#ontoMap')
    page.keyboard.press('Escape')
    settle(page)
    assert set(marks(page).values()) == {''}
    # 이상 패턴 경로: 그 패턴에서 조치 방법까지 가는 길만 밝고, 왼쪽에서 오른쪽으로 놓인다(패턴 → 증상 → 고장 유형 → 원인 · 조치 방법)
    page.select_option('#ontoFocus', 'pattern:cool')
    settle(page)
    got = marks(page)
    assert got['pattern:cool'] == 'path' and got['skill:fan'] == 'path' and got['cause:fin'] == 'path' and got['obj:up'] == 'dim' and got['role:op'] == 'dim' and not low()
    now = page.evaluate(POS_JS)
    assert now['pattern:cool'][0] < now['sym:hot'][0] < now['fm:cool'][0] < now['skill:fan'][0] and now['cause:fin'][0] == now['skill:fan'][0] and now['cause:fin'][1] < now['skill:fan'][1]
    assert '강조 경로 7개' in page.inner_text('#ontoStats')
    page.select_option('#ontoFocus', '')
    settle(page)
    assert page.evaluate(POS_JS) == home
    # 묶음 끄기: 그 묶음의 항목이 사라지고, 다시 켜면 돌아온다
    page.click("#ontoLayers [data-layer='skill']")
    assert marks(page)['skill:fan'] == 'off'
    # 끈 묶음의 항목은 그림에서 사라진다 — Cytoscape 는 표시(.off)의 모양을 다음 그리기 때 계산하므로 누른 직후가 아니라 그려진 뒤에 센다
    page.wait_for_function("() => hydEnt.kg.cy.nodes().filter(n => !n.hasClass('gtitle') && !n.visible()).length === 2", timeout=15000)
    assert page.get_attribute("#ontoLayers [data-layer='skill']", 'aria-pressed') == 'false'
    page.click("#ontoLayers [data-layer='skill']")
    assert set(marks(page).values()) == {''}
    # 확대 · 축소 · 화면에 맞춤, 끌어서 옮기기
    page.click('#ontoFit')
    settle(page)
    k0 = page.evaluate('hydEnt.kg.cy.zoom()')
    page.click('#ontoZoomIn')
    assert page.evaluate('hydEnt.kg.cy.zoom()') > k0
    pan = page.evaluate('hydEnt.kg.cy.pan().x')
    page.mouse.move(box['x'] + 40, box['y'] + box['height'] - 120)
    page.mouse.down()
    page.mouse.move(box['x'] + 120, box['y'] + box['height'] - 160, steps=4)
    page.mouse.up()
    assert round(page.evaluate('hydEnt.kg.cy.pan().x') - pan) == 80 and set(marks(page).values()) == {''}      # 끌기는 고르기가 아니다
    page.click('#ontoFit')
    settle(page)
    assert abs(page.evaluate('hydEnt.kg.cy.zoom()') - k0) < 5e-3                                          # 같은 보기로 돌아온다
    out = page.evaluate("() => { const cy = hydEnt.kg.cy; return cy.nodes().filter(n => { const p = n.renderedPosition(); return p.x < 0 || p.x > cy.width() || p.y < 0 || p.y > cy.height(); }).length; }")
    assert out == 0                                                         # 화면에 맞추면 모든 항목이 캔버스 안에 있다


# 수업 데이터 크기(항목 330여 개 · 연결 730여 개)의 그래프. 종류별 수는 수업 그래프(HYD-01)와 같고, 연결은 정해진 식으로 만든다(난수 없음)
COUNTS = {'Perspective': 4, 'Objective': 8, 'Measure': 21, 'Process': 3, 'OrgUnit': 7, 'Role': 7, 'System': 10, 'Asset': 1, 'Component': 6, 'Sensor': 5, 'Actuator': 3,
          'StateVariable': 11, 'Part': 4, 'Supplier': 3, 'AnomalyPattern': 9, 'Symptom': 6, 'FailureMode': 2, 'Cause': 5, 'Evidence': 6, 'ManualSection': 25, 'Skill': 19, 'Step': 74,
          'Action': 9, 'Decision': 4, 'DecisionTable': 4, 'Rule': 25, 'InputData': 36, 'KnowledgeSource': 11, 'ExternalVariable': 4}


def big_graph():
    nodes = [{'id': f'{label.lower()}:{i:03d}', 'label': label, 'name': f'{label} 항목의 긴 이름 {i}번', 'props': {'severity': 'HIGH', 'detectionMode': 'held', 'code': 'COOLER_DEGRADATION',
              'rule': 'TS1 > 55 and CE < 70'} if label == 'AnomalyPattern' else {}} for label, n in COUNTS.items() for i in range(n)]
    total = len(nodes)
    pairs = {(i, (i * 7 + 3) % total) for i in range(total)} | {(i, (i * 13 + 5) % total) for i in range(total)} | {(i, 60 + i % 3) for i in range(0, total, 5)}
    return {'nodes': nodes, 'edges': [{'from': nodes[a]['id'], 'to': nodes[b]['id'], 'type': 'LEADS_TO'} for a, b in sorted(pairs) if a != b]}


# 화면에 그려진 이름(점 · 묶음 이름 · 관계 이름 줄)의 상자와 점의 상자를 Cytoscape 가 그린 그대로 읽어, 이름끼리 겹친 쌍 · 이름이 다른 점을 덮은 쌍 · 캔버스 안 도구 자리에 쓴 이름을 센다
OVERLAP_JS = r"""() => {
  const cy = hydEnt.kg.cy, cross = (a, b) => a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2, shrink = (b, d) => ({ x1: b.x1 + d, y1: b.y1 + d, x2: b.x2 - d, y2: b.y2 - d });
  const shown = cy.nodes().filter(n => n.visible() && n.style('label') && Number(n.style('text-opacity')) > 0 && Number(n.style('opacity')) > 0.5);
  const labels = shown.map(n => ({ id: n.id(), box: shrink(n.renderedBoundingBox({ includeNodes: false, includeLabels: true, includeOverlays: false }), 1.5) }));
  const dots = cy.nodes().filter(n => n.visible() && !n.hasClass('gtitle') && !n.hasClass('rhead') && Number(n.style('opacity')) > 0.5).map(n => ({ id: n.id(), box: shrink(n.renderedBoundingBox({ includeLabels: false, includeOverlays: false }), 1.5) }));
  const bar = document.querySelector('#view-ontology .canvas-bar'), foot = document.getElementById('ontoLayers'), top = bar.offsetTop + bar.offsetHeight, low = foot.offsetTop;
  const pairs = [], covered = [], tools = [];
  labels.forEach((a, i) => { labels.slice(i + 1).forEach(b => { if (cross(a.box, b.box)) pairs.push([a.id, b.id]); });
    dots.forEach(d => { if (d.id !== a.id && cross(a.box, d.box)) covered.push([a.id, d.id]); });
    const inside = a.box.x2 > 0 && a.box.x1 < cy.width() && a.box.y2 > 0 && a.box.y1 < cy.height();      // 캔버스 밖으로 나간 이름은 보이지 않는다
    if (inside && (a.box.y1 < top || a.box.y2 > low)) tools.push(a.id); });
  return { labels: labels.length, plain: shown.filter(n => n.hasClass('lab')).length, pairs, covered, tools };
}"""


def test_보이는_이름은_서로_겹치지_않고_점과_캔버스_안_도구를_가리지_않는다(onto):
    """「전체 보기에서 이름이 포개져 읽을 수 없다 · 확대해도 풀리지 않는다 · 이름이 찾기 칸과 묶음 조각 위에 그려진다」를 수업 크기의 그래프로 실제 화면에서 잰다."""
    page = onto

    def reload(graph):
        HOLDER['graph'] = graph
        page.evaluate("() => { hydEnt.kg.cy.scratch('old', true); }")
        page.click('#ontologyHeadMore-trigger')      # 다시 읽기는 화면 머리의 더 보기 안에 있다
        page.click('#ontoReload')
        page.wait_for_function("() => hydEnt.kg.cy && !hydEnt.kg.cy.scratch('old')", timeout=60000)      # 수업 크기 그래프의 배치는 부하가 걸리면 몇 초가 걸린다
        settle(page)

    def clean(said):
        # 화면과 항목이 옮겨 가기를 다 마친 뒤(정해 둔 시간이 아니라 움직임이 실제로 멎은 뒤) 이름을 다시 고를 틈(화면이 멎고 0.09초 뒤에 고른다)을 두고 잰다 —
        # 0.7초로 정해 두었을 때는 찾기가 화면을 옮기는 동안(0.38초 + 그동안 미뤄지는 이름 고르기) 재서 「찾기에 걸린 이름 0개」로 읽혔다
        settle(page)
        got = page.evaluate(OVERLAP_JS)
        assert not got['pairs'] and not got['covered'] and not got['tools'], (said, got)
        return got
    try:
        reload(big_graph())
        first = clean('전체 보기')
        assert first['plain'] >= 12, first                                  # 전체 보기에서도 이름이 여럿 보인다(다 숨겨서 겹침을 없앤 것이 아니다)
        for i in range(3):                                                  # 확대하면 이름이 더 보이고, 그래도 겹치지 않는다
            page.click('#ontoZoomIn')
        zoomed = clean('세 번 확대')
        assert zoomed['plain'] > 0
        box = page.locator('#ontoMap').bounding_box()                       # 끌어 옮긴 뒤에도
        page.mouse.move(box['x'] + 300, box['y'] + 300)
        page.mouse.down()
        page.mouse.move(box['x'] + 180, box['y'] + 120, steps=4)
        page.mouse.up()
        clean('끌어 옮김')
        page.click('#ontoFit')
        page.fill('#ontoSearch', 'Step')                                    # 찾기에 걸린 74개: 보이는 이름끼리 겹치지 않는다
        found = clean('찾기')
        assert found['plain'] > 0
        page.fill('#ontoSearch', '')
        page.evaluate("() => hydEnt.kg.cy.nodes('.gtitle').filter(n => n.data('g') === 'skill').emit('tap')")     # 지도의 묶음 이름을 눌러 그 묶음을 크게 본 때
        opened = clean('묶음 펼침')
        assert opened['plain'] > 0 and page.locator("#ontoNode .kg-group[data-group='skill']").count() == 1 and page.locator("#ontoNode [data-go]").count() == 182      # 그 묶음의 항목 이름은 오른쪽 칸에 다 있다
        page.click("#ontoNode [data-kg-group-close]")
        tap(page, 'decision:000')                                           # 고른 때(이웃을 모은 줄 + 그 밖의 이름)
        clean('고름')
        # 고른 항목의 속성 값: 열거 값은 한국어로, 식은 식 그대로, 식별자 성격의 코드는 「그 밖의 속성」 접기 안에
        tap(page, 'decision:000')
        page.fill('#ontoSearch', 'AnomalyPattern 항목의 긴 이름 0번')
        page.press('#ontoSearch', 'Enter')
        settle(page)
        head = page.inner_text('#ontoNode .node-sec >> nth=0')
        assert '심각도' in head and '높음' in head and 'HIGH' not in head and '조건이 지속 시간 동안 이어지면 경보' in head and 'held' not in head
        assert 'TS1 > 55 and CE < 70' in head and 'COOLER_DEGRADATION' not in head
        assert page.locator('#ontoNode .node-fold .fold:not([open])').count() == 1 and 'COOLER_DEGRADATION' in page.locator('#ontoNode .node-fold').inner_html()
        page.fill('#ontoSearch', '')
    finally:
        page.focus('#ontoMap')
        page.keyboard.press('Escape')
        reload(SMALL)


def test_같은_그래프는_서버가_준_차례가_달라도_늘_같은_자리에_놓인다(onto):
    """볼 때마다 자리가 바뀌면 지도를 익힐 수 없다. 난수를 고정하고 항목 · 연결을 id 순으로 세운 뒤 배치한다. 데이터가 다르면 자리도 달라진다."""
    page = onto

    def reload(graph):
        HOLDER['graph'] = graph
        page.evaluate("() => { hydEnt.kg.cy.scratch('old', true); }")
        page.click('#ontologyHeadMore-trigger')      # 다시 읽기는 화면 머리의 더 보기 안에 있다
        page.click('#ontoReload')
        page.wait_for_function("() => hydEnt.kg.cy && !hydEnt.kg.cy.scratch('old')", timeout=60000)      # 새로 그린 지도
        return page.evaluate(POS_JS)
    try:
        a = reload(SMALL)
        assert reload(SMALL) == a                                               # 다시 읽어도 같은 자리
        assert reload({'nodes': SMALL['nodes'][::-1], 'edges': SMALL['edges'][3:] + SMALL['edges'][:3]}) == a      # 같은 데이터, 다른 차례
        b = reload({'nodes': SMALL['nodes'][:-2], 'edges': [e for e in SMALL['edges'] if e['to'] not in ('obj:up', 'comp:fan')]})
        assert len(b) == 8 and {k: v for k, v in a.items() if k in b} != b      # 데이터가 다르면 자리도 달라진다
    finally:
        reload(SMALL)


# 문서에서 뽑은 절차 단계: id 는 문서 · 원문 해시가 이어진 250자, 이름은 원문 한 문장(실제 그래프의 PM-02 「시운전 확인」 단계와 같은 꼴)
DOC_SID = 'manual:39989446-ba9c-4800-8be2-e2f3e798a29d:2a757bd43772774a3b85c99779b3acef501f8d4dbc2cdbf9f851394ba841ae4a'
DOC_ROOT = 'manual:4010c166b291e580108f81f875ed1a133af9e5fe6f7e169ecb3496752729294d:39989446-ba9c-4800-8be2-e2f3e798a29d:2a757bd43772774a3b85c99779b3acef501f8d4dbc2cdbf9f851394ba841ae4a'
STEP_ID = DOC_ROOT + ':reference:0e198b6a22cda70d2eca141b696a3caa0edc0da05478bbdb6296cc17952dc664:1'
STEP_NAME = '정비 뒤 부하 90 %로 15분 시운전해 토출 압력 PS1 178 bar 이상, 유량 FS1 8.8 l/min 이상, 팬 진동 VS1 1.2 mm/s 미만이 유지되면 정상이다.'
MANUAL = {'nodes': SMALL['nodes'] + [
    {'id': STEP_ID, 'label': 'Step', 'name': STEP_NAME, 'props': {'text': STEP_NAME, 'order': 1, 'source_id': DOC_SID,
                                                                 'citation': json.dumps({'page': 1, 'quote': STEP_NAME, 'source_id': DOC_SID}, ensure_ascii=False)}},
    {'id': DOC_ROOT + ':section:313cd9c0', 'label': 'ManualSection', 'name': '시운전 확인', 'props': {'source_id': DOC_SID}},
    {'id': 'skill:sop-pm-2-9', 'label': 'Skill', 'name': '시운전 확인', 'props': {}},
    {'id': 'ks:' + DOC_ROOT[:90], 'label': 'KnowledgeSource', 'name': 'PM-02_powerpack-pm-checklist.md', 'props': {'kind': 'manual', 'source_id': DOC_SID}}],
    'edges': SMALL['edges'] + [{'from': 'skill:sop-pm-2-9', 'to': STEP_ID, 'type': 'HAS_STEP'}, {'from': STEP_ID, 'to': DOC_ROOT + ':section:313cd9c0', 'type': 'REFERS_TO'},
                               {'from': DOC_ROOT + ':section:313cd9c0', 'to': 'ks:' + DOC_ROOT[:90], 'type': 'PART_OF'}]}


def test_문서에서_뽑은_항목을_고르면_이름과_출처가_앞에_있고_해시_id는_한_줄로_줄며_캔버스_이름은_잘리지_않는다():
    """2026-11-25 실제 브라우저 탐사(1366 × 768): 매뉴얼 절 · 절차 단계를 고르면 오른쪽 판의 이름 바로 아래에 250자 해시 id 가 일곱 줄로 펼쳐졌고,
    캔버스 위 그 이름은 한 줄로 그려져 양 끝이 캔버스 밖으로 잘렸다.
    지금: 판의 머리는 이름 → 출처 문서(그 항목의 source_id 와 같은 지식 출처의 이름) → ID 차례이고, ID 는 한 줄 조각으로 줄어 끝이 「…」이며 전체는 말풍선(누르면 복사)에 있다.
    캔버스 위 고른 항목의 이름은 두 호 사이 폭 안에서 두 줄까지 쓰고 넘치면 끝을 말줄임하며, 그 점에 마우스를 올리면 전체 이름이 말풍선으로 나온다. 다른 이름과 겹치지 않는다."""
    holder = {'graph': MANUAL}
    gen = serve_onto(holder)
    page = next(gen)
    try:
        tap(page, STEP_ID)
        head = page.evaluate(r"""id => { const h = document.querySelector('#ontoNode .node-head'), idc = h.querySelector('.node-id .idc'), R = e => e.getBoundingClientRect();
          const order = [...h.querySelectorAll('h2, .node-src, .node-id')].map(e => e.matches('h2') ? 'name' : e.matches('.node-src') ? 'src' : 'id');
          const elsewhere = [...h.querySelectorAll('*')].filter(e => !(idc && (e === idc || idc.contains(e))) && [...e.childNodes].some(c => c.nodeType === 3 && c.textContent.includes(id.slice(0, 40))));
          return { order, name: h.querySelector('h2').textContent, src: h.querySelector('.node-src')?.textContent.trim() || '', elsewhere: elsewhere.length,
            idc: idc && { title: idc.title, cut: idc.scrollWidth > idc.clientWidth, ellipsis: getComputedStyle(idc).textOverflow, display: getComputedStyle(idc).display, height: R(idc).height, inside: R(idc).right <= R(h).right + 0.5 } }; }""", STEP_ID)
        assert head['order'] == ['name', 'src', 'id'] and head['name'] == STEP_NAME, head
        assert head['src'] == '출처 문서 PM-02_powerpack-pm-checklist.md', head['src']
        assert head['elsewhere'] == 0 and head['idc'] and head['idc']['title'] == STEP_ID, head      # 해시 id 는 ID 조각 한 곳에만(전체는 그 말풍선)
        # 한 줄로 줄고 끝이 「…」 — text-overflow 는 블록 상자의 글에만 그려진다(키트 조각의 inline-flex 는 말줄임 없이 자른다)
        assert head['idc']['cut'] and head['idc']['ellipsis'] == 'ellipsis' and head['idc']['display'] in ('block', 'inline-block') and head['idc']['height'] <= 24 and head['idc']['inside'], head['idc']
        # 캔버스: 고른 항목의 이름은 두 줄까지 · 끝이 말줄임 · 캔버스 안이고, 보이는 이름끼리 겹치지 않는다
        pick = page.evaluate(r"""id => { const cy = hydEnt.kg.cy, n = cy.getElementById(id), b = n.renderedBoundingBox({ includeNodes: false, includeLabels: true, includeOverlays: false });
          return { lines: n.style('label').split('\n'), x1: b.x1, x2: b.x2, w: cy.width() }; }""", STEP_ID)
        assert 1 < len(pick['lines']) <= 2 and pick['lines'][-1].endswith('…') and STEP_NAME.startswith(pick['lines'][0]), pick
        assert pick['x1'] >= 0 and pick['x2'] <= pick['w'], pick
        got = page.evaluate(OVERLAP_JS)
        assert not got['pairs'] and not got['covered'], got
        # 잘린 이름의 점에 마우스를 올리면 전체 이름이 말풍선으로, 잘리지 않은 이름의 점에서는 말풍선이 없다
        at = lambda nid: page.evaluate("id => { const p = hydEnt.kg.cy.getElementById(id).renderedPosition(), b = document.getElementById('ontoMap').getBoundingClientRect(); return [b.left + p.x, b.top + p.y]; }", nid)
        page.mouse.move(*at(STEP_ID))
        page.wait_for_timeout(200)
        assert page.get_attribute('#ontoMap', 'title') == STEP_NAME
        page.mouse.move(*at('skill:sop-pm-2-9'))
        page.wait_for_timeout(200)
        assert page.get_attribute('#ontoMap', 'title') == ''
        # 출처를 모르는 항목(손으로 넣은 지식)에는 출처 줄이 없고 ID 는 그대로 조각이다
        tap(page, STEP_ID)                                                      # 고른 것을 풀고(다시 누름) 다른 항목을 고른다
        tap(page, 'fm:cool')
        assert page.locator('#ontoNode .node-src').count() == 0 and page.inner_text('#ontoNode .node-id .idc').endswith('fm:cool')
    finally:
        gen.close()
