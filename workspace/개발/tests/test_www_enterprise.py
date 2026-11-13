"""지식 지도 · 규칙 판단 · 업무 시스템 기록 화면(it/portal/www/enterprise.js).

- 업무 시스템 보드: 업무 상태(/api/state)가 주는 표만 그린다.
- 지식 지도: 배치는 같은 데이터면 늘 같은 자리이고(서버가 준 차례와 무관), 화면에 맞추면 항목이 캔버스 안에 있으며, 항목의 모양(고름 · 이어짐 · 경로 · 검색과
  그 겹침)과 보일 이름을 가르는 판정이 정해진 대로다. 마지막 시험은 실제 브라우저에서 눌러 보고 글자와 캔버스 바탕의 대비를 잰다.

enterprise.js 는 실릴 때 화면 요소를 찾으므로 node 시험은 브라우저 쪽만 최소 대역(요소 · 탭 표)으로 두고 실제 모듈을 싣는다."""
import math
import re

import pytest
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


# ------------------------------------------------------------------ 지식 지도의 배치
# 수업 데이터 크기(항목 330여 개 · 연결 730여 개)의 그래프. 종류별 수는 수업 그래프(HYD-01)와 같고, 연결은 정해진 식으로 만든다(난수 없음).
# 'MyThing' 은 온톨로지 v2 에 없는 종류다 — 「내 업무 개념」 묶음에 놓인다.
COUNTS = {'Perspective': 4, 'Objective': 8, 'Measure': 21, 'Process': 3, 'OrgUnit': 7, 'Role': 7, 'System': 10, 'Asset': 1, 'Component': 6, 'Sensor': 5, 'Actuator': 3,
          'StateVariable': 11, 'Part': 4, 'Supplier': 3, 'AnomalyPattern': 9, 'Symptom': 6, 'FailureMode': 2, 'Cause': 5, 'Evidence': 6, 'ManualSection': 25, 'Skill': 19, 'Step': 74,
          'Action': 9, 'Decision': 4, 'DecisionTable': 4, 'Rule': 25, 'InputData': 36, 'KnowledgeSource': 11, 'ExternalVariable': 4, 'MyThing': 5}
CANVAS = (727, 598)      # 1440 × 900 화면에서 지식 지도 캔버스의 크기(잰 값)


def graph():
    nodes = [{'id': f'{label.lower()}:{i:03d}', 'label': label, 'name': f'{label} {i}', 'props': {}} for label, n in COUNTS.items() for i in range(n)]
    total = len(nodes)
    pairs = {(i, (i * 7 + 3) % total) for i in range(total)} | {(i, (i * 13 + 5) % total) for i in range(total)} | {(i, (i * 31 + 11) % total) for i in range(0, total, 4)}
    edges = [{'from': nodes[a]['id'], 'to': nodes[b]['id'], 'type': 'LEADS_TO'} for a, b in sorted(pairs) if a != b]
    return {'nodes': nodes, 'edges': edges}


def layout(g):
    return run(FILES, "const lay = hydEnt.layoutGraph(DATA); out({ lay, fit: hydEnt.fitView(lay.bounds, %d, %d), pad: hydEnt.KG.PAD })" % CANVAS, g, prelude=PRELUDE)


def test_지식_지도의_배치는_같은_데이터면_서버가_준_차례가_달라도_같은_자리다():
    """볼 때마다 자리가 바뀌면 지도를 익힐 수 없다. 배치에는 난수가 없고, 항목과 연결을 id 순으로 세운 뒤 계산한다."""
    g = graph()
    assert len(g['nodes']) == 337 and len(g['edges']) > 700
    first = layout(g)['lay']
    again = layout(g)['lay']
    turned = layout({'nodes': g['nodes'][::-1], 'edges': g['edges'][3:] + g['edges'][:3]})['lay']      # 같은 데이터, 다른 차례
    assert first == again == turned
    assert len(first['nodes']) == 337 and {n['id'] for n in first['nodes']} == {n['id'] for n in g['nodes']}
    # 데이터가 다르면 자리도 달라진다(늘 같은 값을 돌려주는 것이 아니다)
    fewer = layout({'nodes': g['nodes'][:-40], 'edges': [e for e in g['edges'] if e['from'] in {n['id'] for n in g['nodes'][:-40]} and e['to'] in {n['id'] for n in g['nodes'][:-40]}]})['lay']
    assert fewer['bounds'] != first['bounds']


def test_배치한_항목은_서로_겹치지_않고_같은_종류끼리_모이며_화면에_맞추면_캔버스_안에_있다():
    g = graph()
    got = layout(g)
    lay, fit, pad = got['lay'], got['fit'], got['pad']
    label = {n['id']: n['label'] for n in g['nodes']}
    pts = {n['id']: (n['x'], n['y']) for n in lay['nodes']}
    # 화면에 맞춘 배율로 옮기면 모든 점이 캔버스의 여백(안내 줄 · 층 칩 자리) 안쪽에 있다
    w, h = CANVAS
    for x, y in pts.values():
        sx, sy = x * fit['k'] + fit['tx'], y * fit['k'] + fit['ty']
        assert pad['l'] - 0.5 <= sx <= w - pad['r'] + 0.5 and pad['t'] - 0.5 <= sy <= h - pad['b'] + 0.5, (sx, sy)
    # 점끼리 겹치지 않는다: 화면에 맞춘 배율에서 가장 가까운 두 점의 사이가 점 지름(7px)보다 넓다
    ids = sorted(pts)
    near = min(math.dist(pts[a], pts[b]) for i, a in enumerate(ids) for b in ids[i + 1:])
    assert near * fit['k'] > 7, (near, fit['k'])
    # 같은 종류는 그 종류의 원 안에 모여 있고, 종류 원끼리는 겹치지 않는다
    types = lay['types']
    assert sorted(t['label'] for t in types) == sorted(COUNTS) and all(t['count'] == COUNTS[t['label']] for t in types)
    center = {t['label']: (t['x'], t['y'] + t['r']) for t in types}
    radius = {t['label']: t['r'] for t in types}
    for i, (x, y) in pts.items():
        assert math.dist((x, y), center[label[i]]) <= radius[label[i]] + 1, (i, label[i])
    for i, a in enumerate(types):
        for b in types[i + 1:]:
            assert math.dist(center[a['label']], center[b['label']]) >= a['r'] + b['r'], (a['label'], b['label'])
    # 온톨로지 v2 에 없는 종류는 「내 업무 개념」 묶음(student)에 놓인다
    assert {t['key'] for t in types if t['label'] == 'MyThing'} == {'student'}
    assert {gr['key']: gr['count'] for gr in lay['groups']} == {'value': 33, 'process': 3, 'resource': 57, 'diagnosis': 53, 'skill': 182, 'external': 4, 'student': 5}


STATE_CASES = [
    # (설명, 상태, 항목 → 클래스)
    ('아무것도 고르지 않음', dict(sel=None, near=[], path=None, match=[], query=False), {'a': 'o-node', 'b': 'o-node'}),
    ('고름: 고른 것 · 이어진 것은 밝고 나머지는 흐리다', dict(sel='a', near=['b'], path=None, match=[], query=False), {'a': 'o-node sel', 'b': 'o-node near', 'c': 'o-node far'}),
    ('검색: 걸린 것만 밝다', dict(sel=None, near=[], path=None, match=['b'], query=True), {'a': 'o-node far', 'b': 'o-node match'}),
    ('검색 결과가 없어도 검색 중이면 모두 흐리다', dict(sel=None, near=[], path=None, match=[], query=True), {'a': 'o-node far'}),
    ('겹침: 고른 것이 검색에도 걸렸다', dict(sel='a', near=['b'], path=None, match=['a', 'b'], query=True), {'a': 'o-node sel match', 'b': 'o-node near match', 'c': 'o-node far'}),
    ('이상 패턴 경로', dict(sel=None, near=[], path=['a', 'b'], match=[], query=False), {'a': 'o-node path', 'b': 'o-node path', 'c': 'o-node far'}),
    ('겹침: 경로 위의 항목을 고르고 검색에도 걸렸다', dict(sel='a', near=['c'], path=['a', 'b'], match=['a', 'd'], query=True),
     {'a': 'o-node sel path match', 'b': 'o-node path', 'c': 'o-node near', 'd': 'o-node match', 'e': 'o-node far'}),
]
CLASS_JS = """const s = { sel: DATA.s.sel, near: new Set(DATA.s.near), path: DATA.s.path && new Set(DATA.s.path), match: new Set(DATA.s.match), query: DATA.s.query };
out({ nodes: Object.fromEntries(DATA.ids.map(id => [id, hydEnt.kgNodeClass(id, s)])), edges: DATA.pairs.map(([a, b]) => hydEnt.kgEdgeClass(a, b, s)) })"""


@pytest.mark.parametrize('said, s, want', STATE_CASES, ids=[c[0] for c in STATE_CASES])
def test_항목의_모양은_고름_이어짐_경로_검색과_그_겹침을_가른다(said, s, want):
    got = run(FILES, CLASS_JS, {'s': s, 'ids': sorted(want), 'pairs': []}, prelude=PRELUDE)
    assert got['nodes'] == want


def test_선은_고른_항목에_닿으면_밝고_경로_안이면_경로_선이며_그_밖은_상태가_있을_때만_흐리다():
    pairs = [['a', 'b'], ['b', 'c'], ['c', 'd']]
    cls = lambda s: run(FILES, CLASS_JS, {'s': s, 'ids': [], 'pairs': pairs}, prelude=PRELUDE)['edges']
    assert cls(dict(sel=None, near=[], path=None, match=[], query=False)) == ['kg-e', 'kg-e', 'kg-e']
    assert cls(dict(sel='b', near=['a', 'c'], path=None, match=[], query=False)) == ['kg-e hot', 'kg-e hot', 'kg-e dim']
    assert cls(dict(sel=None, near=[], path=['b', 'c', 'd'], match=[], query=False)) == ['kg-e dim', 'kg-e path', 'kg-e path']
    assert cls(dict(sel='a', near=['b'], path=['b', 'c'], match=[], query=False)) == ['kg-e hot', 'kg-e path', 'kg-e dim']      # 고른 항목에 닿은 선이 경로보다 앞선다
    assert cls(dict(sel=None, near=[], path=None, match=['a'], query=True)) == ['kg-e dim', 'kg-e dim', 'kg-e dim']


def boxes(items, sides):
    """pickLabels 가 고른 자리의 글자 상자(enterprise.js pickLabels 와 같은 식)."""
    out = {}
    for it in items:
        side = sides.get(it['id'])
        if side == 'R':
            out[it['id']] = (it['x'] + it['r'] + 4, it['y'] - 9, it['x'] + it['r'] + 8 + it['w'], it['y'] + 8)
        elif side == 'L':
            out[it['id']] = (it['x'] - it['r'] - 8 - it['w'], it['y'] - 9, it['x'] - it['r'] - 4, it['y'] + 8)
        elif side == 'T':
            out[it['id']] = (it['x'] - it['w'] / 2 - 2, it['y'] - it['r'] - 28, it['x'] + it['w'] / 2 + 2, it['y'] - it['r'] - 6)
        elif side == 'B':
            out[it['id']] = tuple(it['box'])
    return out


def cross(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def test_이름은_겹치지_않게_고르고_고른_것과_밝은_것이_먼저_자리를_잡는다():
    pick = lambda items, lo=-1e9, hi=1e9: run(FILES, "out(Object.fromEntries(hydEnt.pickLabels(DATA.items, DATA.lo, DATA.hi)))", {'items': items, 'lo': lo, 'hi': hi}, prelude=PRELUDE)
    dot = lambda i, x, y, prio=0, **more: dict(id=i, x=x, y=y, r=5, w=60, prio=prio, **more)
    # 나란한 두 점: 보통 이름은 다른 점 위에 쓰지 않는다 — a 는 오른쪽에 b 의 점이 있어 왼쪽에, b 는 오른쪽에 쓴다
    assert pick([dot('a', 100, 100, 5), dot('b', 130, 100, 1)]) == {'a': 'L', 'b': 'R'}
    assert pick([dot('a', 100, 100, 5), dot('b', 100, 140, 1)]) == {'a': 'R', 'b': 'R'}                 # 줄이 다르면 둘 다 오른쪽
    assert pick([dot('a', 100, 100, 1)], hi=150) == {'a': 'L'}                                          # 오른쪽 끝을 넘으면 왼쪽에
    assert pick([dot('a', 100, 100, 1)], lo=60, hi=150) == {}                                           # 왼쪽 끝도 넘으면 숨긴다
    # 고른 항목의 이름은 늘 점 위에. 밝은 이름(lit)은 흐린 점 f 위에 써도 된다 — 그 자리를 먼저 잡아 f 의 이름은 숨는다
    assert pick([dot('s', 100, 100, 9, top=True, lit=True), dot('n', 108, 100, 5, lit=True), dot('f', 150, 100, 0)]) == {'s': 'T', 'n': 'R'}
    # 같은 자리에서 n 이 보통 이름이면 f 의 점을 피해 왼쪽으로 가는데, 거기에는 밝은 점 s 가 있어 숨는다. f 는 제 오른쪽에 쓴다
    assert pick([dot('s', 100, 100, 9, top=True, lit=True), dot('n', 108, 100, 5), dot('f', 150, 100, 0)]) == {'s': 'T', 'f': 'R'}
    # 묶음 이름처럼 자리가 정해진 글자(box)도 같은 판에서 자리를 다툰다
    got = pick([dict(id='cap', box=[90, 60, 150, 74], prio=8, lit=True), dot('a', 100, 100, 1), dict(id='cap2', box=[100, 64, 160, 78], prio=3)])
    assert got == {'cap': 'B', 'a': 'R'}
    # 수업 데이터 크기의 배치에서: 고른 글자끼리 겹치지 않고, 보통 이름은 어떤 점도 덮지 않는다
    g = graph()
    lay, fit = (lambda got: (got['lay'], got['fit']))(layout(g))
    items = [dict(id=n['id'], x=n['x'] * fit['k'], y=n['y'] * fit['k'], r=3.5, w=7 * len(n['id']), prio=n['deg']) for n in lay['nodes']]
    sides = pick(items)
    placed = boxes(items, sides)
    assert 10 < len(placed) < len(items)                                                                 # 화면에 맞춘 배율에서는 일부만 보인다(전부도 0도 아니다)
    keys = sorted(placed)
    assert not [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:] if cross(placed[a], placed[b])]
    assert not [(k, it['id']) for k in keys for it in items if it['id'] != k and cross(placed[k], (it['x'] - it['r'], it['y'] - it['r'], it['x'] + it['r'], it['y'] + it['r']))]


# ------------------------------------------------------------------ 실제 브라우저: 눌러서 고르고, 검색하고, 겹친 상태의 글자가 읽히는지 잰다
SMALL = {'nodes': [{'id': 'pattern:cool', 'label': 'AnomalyPattern', 'name': '쿨러 성능 저하', 'props': {'description': '냉각 효율이 떨어져 유온이 오르는 패턴'}},
                   {'id': 'sym:hot', 'label': 'Symptom', 'name': '유온 상승', 'props': {}}, {'id': 'sym:ce', 'label': 'Symptom', 'name': '냉각 효율 저하', 'props': {}},
                   {'id': 'fm:cool', 'label': 'FailureMode', 'name': '쿨러 냉각 성능 상실', 'props': {}}, {'id': 'skill:fan', 'label': 'Skill', 'name': '팬 최대 운전', 'props': {'sopId': 'SOP-COOL-11'}},
                   {'id': 'skill:wash', 'label': 'Skill', 'name': '쿨러 핀 세척', 'props': {}}, {'id': 'role:op', 'label': 'Role', 'name': '운전원', 'props': {}},
                   {'id': 'obj:up', 'label': 'Objective', 'name': '설비 가용성 확보', 'props': {}}, {'id': 'comp:fan', 'label': 'Component', 'name': '쿨러 팬', 'props': {}}],
         'edges': [{'from': 'pattern:cool', 'to': 'sym:hot', 'type': 'DETECTS'}, {'from': 'pattern:cool', 'to': 'sym:ce', 'type': 'DETECTS'}, {'from': 'sym:hot', 'to': 'fm:cool', 'type': 'INDICATES'},
                   {'from': 'fm:cool', 'to': 'skill:fan', 'type': 'MITIGATED_BY'}, {'from': 'fm:cool', 'to': 'skill:wash', 'type': 'REMEDIED_BY'}, {'from': 'skill:fan', 'to': 'role:op', 'type': 'APPROVED_BY'},
                   {'from': 'skill:fan', 'to': 'comp:fan', 'type': 'TARGETS'}]}
# 화면의 글자색 · 캔버스 바탕색으로 WCAG 대비를 잰다. 색은 rgb(…) · color(srgb …) 두 꼴로 온다(color-mix 는 뒤의 꼴)
CONTRAST_JS = r"""() => {
  const parse = c => { let m = /^rgba?\(([^)]+)\)/.exec(c); if (m) return m[1].split(/[, /]+/).slice(0, 3).map(Number);
    m = /^color\(srgb ([^)]+)\)/.exec(c); if (m) return m[1].split(/[ /]+/).slice(0, 3).map(v => Number(v) * 255); throw new Error('모르는 색: ' + c); };
  const lum = c => { const [r, g, b] = parse(c).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const bg = lum(getComputedStyle(document.querySelector('.kg-canvas')).backgroundColor);
  return [...document.querySelectorAll('#ontoMap .kg-lbl')].filter(t => getComputedStyle(t).display !== 'none').map(t => {
    const L = lum(getComputedStyle(t).fill); return { text: t.textContent, cls: t.getAttribute('class'), ratio: +((Math.max(L, bg) + 0.05) / (Math.min(L, bg) + 0.05)).toFixed(2) }; });
}"""


@pytest.fixture(scope='module')
def onto():
    """서비스 없이 화면 파일만 낸 포털의 지식 지도. 그래프 · 이상 패턴 · 지식 묶음 · 흐름 이름 응답만 이 시험이 주고 그 밖의 서비스 요청은 끊는다."""
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
            page = b.new_page(viewport={'width': 1366, 'height': 768})
            page.route('**/svc/**', lambda route: route.abort('connectionrefused'))
            page.route('**/svc/agent/api/ontology/graph**', give(SMALL))
            page.route('**/svc/agent/api/ontology/patterns', give([{'id': 'pattern:cool', 'code': 'COOLER_DEGRADATION', 'name': '쿨러 성능 저하', 'failureModes': ['쿨러 냉각 성능 상실']}]))
            page.route('**/svc/agent/api/ontology/namespaces', give([]))
            page.route('**/svc/process/api/process/definitions', give([]))
            page.goto(served.url + '/index.html')
            page.wait_for_function('() => window.hydEnt && window.hydMenu')
            open_screen(page, 'ontology')
            page.wait_for_function("() => document.querySelectorAll('#ontoMap .o-node').length === 9")
            yield page
            b.close()
    finally:
        served.close()


def classes(page):
    return page.evaluate("() => Object.fromEntries([...document.querySelectorAll('#ontoMap .o-node')].map(n => [n.dataset.id, n.getAttribute('class').replace('o-node', '').trim()]))")


def test_지식_지도를_눌러_고르고_검색하고_겹친_상태에서도_글자가_읽힌다(onto):
    """「요소를 클릭하면 글자가 흰색이 되어 안 보인다」(고른 것 + 검색에 걸린 것이 겹칠 때)를 실제 화면에서 잰다. 글자는 늘 어두운 캔버스 위에 쓰고 대비는 4.5 이상이어야 한다."""
    page = onto
    low = lambda: [x for x in page.evaluate(CONTRAST_JS) if x['ratio'] < 4.5]
    assert set(classes(page).values()) == {''} and not low() and page.inner_text('#ontoStats') == '항목 9 · 연결 7'
    # 눌러서 고름: 고른 것 · 바로 이어진 것만 밝고 나머지는 흐리다. 오른쪽 칸에 종류 · 이름 · 서버가 준 설명 · 이어진 것이 나온다
    page.click("#ontoMap [data-id='pattern:cool']")
    assert classes(page) == {'pattern:cool': 'sel', 'sym:hot': 'near', 'sym:ce': 'near', 'fm:cool': 'far', 'skill:fan': 'far', 'skill:wash': 'far', 'role:op': 'far', 'obj:up': 'far', 'comp:fan': 'far'}
    assert page.locator('#ontoMap .kg-e.hot').count() == 2 and not low()
    panel = page.inner_text('#ontoNode')
    assert '이상 패턴 · 설비 진단' in panel and '쿨러 성능 저하' in panel and '냉각 효율이 떨어져 유온이 오르는 패턴' in panel and '유온 상승' in panel
    assert page.get_attribute("#ontoMap [data-id='pattern:cool']", 'aria-pressed') == 'true'
    # 겹침: 고른 채로 이름을 검색한다 — 고른 것이 검색에도 걸린다
    page.fill('#ontoSearch', '쿨러')
    got = classes(page)
    assert got['pattern:cool'] == 'sel match' and got['fm:cool'] == 'match' and got['sym:hot'] == 'near' and got['role:op'] == 'far'
    seen = page.evaluate(CONTRAST_JS)
    assert not [x for x in seen if x['ratio'] < 4.5], seen
    assert any('sel' in x['cls'] and 'match' in x['cls'] and x['text'] == '쿨러 성능 저하' for x in seen)      # 겹친 항목의 이름이 화면에 보인다(숨겨지지 않았다)
    assert '검색 결과 4개' in page.inner_text('#ontoStats') and page.is_visible('#ontoNext')
    # 오른쪽 칸의 이어진 항목을 누르면 그 항목이 골라진다
    page.click("#ontoNode [data-go='sym:hot']")
    assert classes(page)['sym:hot'] == 'sel' and page.inner_text('#ontoNode h2') == '유온 상승'
    # 고른 항목을 다시 누르면 풀리고, 검색을 지우면 처음 모양으로 돌아온다
    page.click("#ontoMap [data-id='sym:hot']")
    page.fill('#ontoSearch', '')
    assert set(classes(page).values()) == {''} and page.is_hidden('#ontoNext')
    # 이상 패턴 경로: 그 패턴에서 조치 방법까지 가는 길이 밝다
    page.select_option('#ontoFocus', 'pattern:cool')
    got = classes(page)
    assert got['pattern:cool'] == 'path' and got['skill:fan'] == 'path' and got['obj:up'] == 'far' and not low()
    page.select_option('#ontoFocus', '')
    # 묶음 끄기: 그 묶음의 항목과 거기에 닿은 선이 사라지고, 다시 켜면 돌아온다
    page.click("#ontoLayers [data-layer='skill']")
    assert classes(page)['skill:fan'] == 'off' and page.locator('#ontoMap .o-node.off').count() == 2 and page.locator('#ontoMap .kg-e.off').count() == 4
    assert page.get_attribute("#ontoLayers [data-layer='skill']", 'aria-pressed') == 'false'
    page.click("#ontoLayers [data-layer='skill']")
    assert set(classes(page).values()) == {''}
    # 키보드: 항목에 초점을 두고 Enter 로 고르고, Esc 로 푼다
    page.focus("#ontoMap [data-id='fm:cool']")
    page.keyboard.press('Enter')
    assert classes(page)['fm:cool'] == 'sel'
    page.keyboard.press('Escape')
    assert set(classes(page).values()) == {''}
    # 확대 · 축소 · 화면에 맞춤, 끌어서 옮기기
    page.click('#ontoFit')
    k0 = page.evaluate('kg.view.k')
    page.click('#ontoZoomIn')
    assert page.evaluate('kg.view.k') > k0
    box = page.locator('#ontoMap').bounding_box()
    tx = page.evaluate('kg.view.tx')
    page.mouse.move(box['x'] + 40, box['y'] + box['height'] - 120)
    page.mouse.down()
    page.mouse.move(box['x'] + 120, box['y'] + box['height'] - 160, steps=4)
    page.mouse.up()
    assert round(page.evaluate('kg.view.tx') - tx) == 80 and set(classes(page).values()) == {''}      # 끌기는 고르기가 아니다
    page.click('#ontoFit')
    assert abs(page.evaluate('kg.view.k') - k0) < 1e-9
    # 모든 항목이 캔버스 안에 있다(화면에 맞춤은 0.28초 동안 미끄러져 간다 — 그 뒤에 잰다)
    page.wait_for_function("() => !document.querySelector('#ontoMap .kg-world').classList.contains('glide')")
    out = page.evaluate("""() => { const c = document.getElementById('ontoMap').getBoundingClientRect();
      return [...document.querySelectorAll('#ontoMap .kg-dot')].map(d => d.getBoundingClientRect()).filter(r => r.left < c.left || r.right > c.right || r.top < c.top || r.bottom > c.bottom).length; }""")
    assert out == 0
