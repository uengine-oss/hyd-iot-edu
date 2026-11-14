"""기본 제공 흐름의 그림 — 사람이 배치한 그림 정보(BPMNDiagram)가 흐름마다 들어 있고, 정의와 어긋나지 않고, 실제로 그렸을 때 읽히는가.

대상 다섯: 수업 흐름 A · B · C(it/process/procsvc/course_flows.json 의 BPMN 원문), 기준 흐름 「설비 이상 조치」(definitions/anomaly_response.bpmn),
「교대 인수인계」(definitions/shift_handover.bpmn — 학생이 수업에서 가져오는 그 파일이 제공 정의 shift_handover 의 그림이기도 하다).
단계가 하나뿐인 흐름 셋(미지원 경보 현장 검토 · 에이전트에게 질문하기 · 문서 원천의 에이전트 추출 제안)은 그림 파일을 두지 않는다 — 화면이 정의에서 그린다.

읽히는가는 실제 브라우저(Playwright Chromium)에서 화면이 쓰는 보기 부품(vendor/bpmn-js)으로 그린 뒤, 그려진 요소의 좌표로 잰다:
상자 겹침 · 선이 상자를 지남 · 선 포갬 · 선 교차 · 이름이 상자 · 선 · 다른 이름과 겹침 · 상자 이름 세 줄 이상 · 차선 밖 — 모두 0.
(화면의 자동 배치를 재는 test_www_bpmnLayout.py 와 같은 잣대에, 사람이 배치한 그림이라 선 포갬 · 교차 · 이름 겹침을 더했다.)
"""
import json
import re
import xml.etree.ElementTree as ET

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import DEFINITIONS, ROOT, WWW, Served
from procsvc import bpmn_import, bpmn_store, course_policy as cp

BPMN = '{http://www.omg.org/spec/BPMN/20100524/MODEL}'
DI = '{http://www.omg.org/spec/BPMN/20100524/DI}'
PROVIDED = {'설비 이상 조치': ('anomaly_response_v22.json', 'anomaly_response.bpmn'), '교대 인수인계': ('shift_handover_v1.json', 'shift_handover.bpmn')}
PICTURES = {**{cp.COURSE_FLOWS[d][2]['name']: cp.COURSE_FLOWS[d][1] for d in cp.COURSE_FLOWS},
            **{name: (DEFINITIONS / bpmn).read_text(encoding='utf-8') for name, (_, bpmn) in PROVIDED.items()}}
#: 화면 용어 정본(workspace/개발/문서/UIUX_PLAN.md 4절)이 쓰지 않는 말 — 그림의 이름(단계 · 갈림 · 선 · 끝 · 차선)에 없어야 한다
BANNED = ('작업지시', '재관측', '거절', '에스컬레이션', '상급자', 'PLC', 'ERP', '==', '정비 오더')
LANES = {'AI 에이전트', '담당자', '시스템', '운전원', '생산관리자', '인계자', '인수자'}
#: 한 갈림에서 나가는 가지가 넷(들어오는 선까지 다섯)이라 마름모의 네 꼭짓점으로 나눌 수 없는 곳 — 두 가지가 줄기를 함께 쓰고 갈라진 뒤에 이름이 붙는다
SHARED_STEM = {'설비 이상 조치': {frozenset({'seq_gw_purchase', 'seq_gw_other'})}}


def _definition(name):
    return json.loads((DEFINITIONS / PROVIDED[name][0]).read_text(encoding='utf-8'))


def _elements(xml):
    """그림 원문의 흐름 요소 {id: (꼬리표, 이름)} · 선 {id: 이름} · 차선 {이름: [요소 id]} · 그림 정보가 가리키는 id 들."""
    root = ET.fromstring(xml.encode('utf-8'))
    process = root.find(BPMN + 'process')
    nodes = {el.get('id'): (el.tag.split('}')[-1], el.get('name') or '') for el in process if re.search(r'(Event|ask|Gateway)$', el.tag)}
    flows = {el.get('id'): el.get('name') or '' for el in process.findall(BPMN + 'sequenceFlow')}
    lanes = {lane.get('name'): [r.text.strip() for r in lane.findall(BPMN + 'flowNodeRef')] for lane in process.iter(BPMN + 'lane')}
    shapes = [s.get('bpmnElement') for s in root.iter(DI + 'BPMNShape')]
    edges = [e.get('bpmnElement') for e in root.iter(DI + 'BPMNEdge')]
    return nodes, flows, lanes, shapes, edges


# ---------------------------------------------------------------- 그림 정보가 있고 요소와 맞는가
@pytest.mark.parametrize('name', list(PICTURES))
def test_그림_정보가_모든_단계와_선을_빠짐없이_한_번씩_놓는다(name):
    """배치 정보(BPMNDiagram)가 있어야 화면이 자동으로 놓지 않는다. 그림에 없는 단계 · 선, 요소가 없는 상자 · 선이 없어야 한다."""
    nodes, flows, lanes, shapes, edges = _elements(PICTURES[name])
    lane_ids = {l.get('id') for l in ET.fromstring(PICTURES[name].encode('utf-8')).iter(BPMN + 'lane')}
    assert sorted(s for s in shapes if s not in lane_ids) == sorted(nodes), '상자와 요소가 하나씩 맞아야 한다'
    assert sorted(edges) == sorted(flows), '선과 연결이 하나씩 맞아야 한다'
    assert lane_ids <= set(shapes) and len(lane_ids) >= 3, '차선마다 그림 정보가 있어야 한다'


@pytest.mark.parametrize('name', list(PICTURES))
def test_차선이_누가_하는_단계인지를_말하고_모든_요소가_차선_하나에_든다(name):
    nodes, _, lanes, _, _ = _elements(PICTURES[name])
    assert set(lanes) <= LANES, f'차선 이름은 화면 용어로: {set(lanes) - LANES}'
    assert 'AI 에이전트' in lanes and len(lanes) >= 3
    listed = [n for members in lanes.values() for n in members]
    assert sorted(listed) == sorted(nodes), '요소마다 차선 하나'


@pytest.mark.parametrize('name', list(PICTURES))
def test_그림의_이름에_화면_용어가_쓰지_않는_말이_없다(name):
    nodes, flows, _, _, _ = _elements(PICTURES[name])
    names = [n for _, n in nodes.values()] + list(flows.values())
    assert not [n for n in names if any(b in n for b in BANNED)], [n for n in names if any(b in n for b in BANNED)]
    ends = [n for tag, n in nodes.values() if tag == 'endEvent']
    assert all(len(n) >= 2 and n not in ('끝', '종료', '완료') for n in ends), f'끝의 이름은 어디서 끝났는지를 말한다: {ends}'
    gateways = [n for tag, n in nodes.values() if tag.endswith('Gateway')]
    assert len(set(gateways)) == len(gateways) or name == '냉각 긴급 대응', f'갈림마다 구별되는 이름: {gateways}'


@pytest.mark.parametrize('definition', sorted(cp.COURSE_FLOWS))
def test_수업_흐름의_결과_요약_틀에_정본이_쓰지_않는_말과_겹친_마침표가_없다(definition):
    """요약 틀의 사유({approval_reason})는 사람이 적은 문장이라 마침표로 끝날 수 있다 — 그 뒤에 마침표를 또 찍지 않는다."""
    texts = [str(c.get(k)) for t in cp.COURSE_FLOWS[definition][2]['tasks'].values() if isinstance(t, dict)
             for c in [t.get('config') or {}] for k in ('summary', 'title', 'outcome') if c.get(k)]
    assert texts and not [t for t in texts if any(b in t for b in ('작업지시', '재관측', '거절'))]
    assert not [t for t in texts if '{approval_reason}.' in t]


# ---------------------------------------------------------------- 정의와 그림이 어긋나지 않는가(기준 흐름 · 교대 인수인계)
@pytest.mark.parametrize('name', list(PROVIDED))
def test_제공_정의의_그림_파일은_정의와_요소_선_이름이_같고_화면이_찾는_id_로_나간다(name):
    raw = _definition(name)
    xml = bpmn_store.provided_diagram(raw, PICTURES[name])
    nodes, flows, _, shapes, edges = _elements(xml)
    want = [x['id'] for k in ('events', 'activities', 'gateways') for x in raw[k]]
    assert sorted(nodes) == sorted(bpmn_store.xid(i) for i in want)
    assert sorted(flows) == sorted(bpmn_store.xid(q['id']) for q in raw['sequences'])
    assert set(nodes) <= set(shapes) and set(flows) == set(edges), '바꾼 id 가 그림 정보에도 똑같이 쓰인다'
    assert {bpmn_store.xid(x['id']): x['name'] for k in ('events', 'activities', 'gateways') for x in raw[k]} == {i: n for i, (_, n) in nodes.items()}
    assert not [i for i in list(nodes) + list(flows) if ':' in i], 'XML 의 id 에 쌍점을 쓰지 않는다'


@pytest.mark.parametrize('change, words', [
    (lambda raw: raw['activities'][0].update(name='다른 이름'), '이름이 다릅니다'),
    (lambda raw: raw['activities'].append(dict(raw['activities'][0], id='task:new-step')), '그림에 없습니다'),
    (lambda raw: raw['sequences'].pop(), '정의에 없습니다'),
    (lambda raw: raw['sequences'][-1].update(target=raw['sequences'][0]['target']), '이어진 곳이 다릅니다'),
])
@pytest.mark.parametrize('name', list(PROVIDED))
def test_정의를_고치고_그림을_그대로_두면_어긋난_곳을_말하며_그림을_만들지_않는다(name, change, words):
    raw = _definition(name)
    change(raw)
    with pytest.raises(bpmn_store.DiagramMismatch, match=words):
        bpmn_store.provided_diagram(raw, PICTURES[name])


def test_교대_인수인계는_학생이_가져오는_그림과_제공_정의의_그림이_같은_파일이다():
    """두 벌의 정의(학생이 가져오는 ShiftHandover · 제공 정의 shift_handover)가 서로 다른 그림으로 보이지 않게 — 그림 파일은 하나다.
    그 파일이 수업 단계의 가져오기 대조 원본(course_policy.HANDOVER)이고, 제공 정의와 단계 · 선 · 이름이 같다."""
    assert cp.HANDOVER['xml'] == PICTURES['교대 인수인계']
    raw = _definition('교대 인수인계')
    parsed = bpmn_import.parse_bpmn(cp.HANDOVER['xml'])
    key = lambda i: re.sub(r'[^A-Za-z0-9]', '_', i)
    assert {t['id']: t['name'] for t in parsed['tasks']} == {key(a['id']): a['name'] for a in raw['activities']}
    assert {g['id']: g['name'] for g in parsed['gateways']} == {key(g['id']): g['name'] for g in raw['gateways']}
    assert {f['id']: (f['source'], f['target'], f['name']) for f in parsed['flows']} == \
           {key(q['id']): (key(q['source']), key(q['target']), q.get('name', '')) for q in raw['sequences']}


# ---------------------------------------------------------------- 실제로 그렸을 때 읽히는가
PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<link rel="stylesheet" href="/vendor/bpmn-js/diagram-js.css"><link rel="stylesheet" href="/vendor/bpmn-js/bpmn-js.css">
<style>@font-face { font-family: "Pretendard Variable"; font-weight: 45 920; src: url("/vendor/pretendard/PretendardVariable.woff2") format("woff2-variations"); }
html, body { margin: 0 } #stage { width: 1376px; height: 760px }</style></head>
<body><div id="stage"></div><script src="/vendor/bpmn-js/bpmn-navigated-viewer.production.min.js"></script></body></html>"""

# 그림 하나를 화면과 같은 글자 설정으로 그리고(큰 판 1376 × 760 에 맞춤), 그려진 요소의 좌표로 판정한다
JUDGE = """async xml => {
  await document.fonts.load('13px "Pretendard Variable"'); await document.fonts.ready;      // 글자 폭은 그릴 때 잰다 — 글꼴이 먼저 실려 있어야 화면과 같은 줄바꿈이다
  document.getElementById('stage').innerHTML = '';
  const viewer = new BpmnJS({ container: '#stage', textRenderer: { defaultStyle: { fontFamily: 'Pretendard Variable, sans-serif', fontSize: 13 }, externalStyle: { fontSize: 12 } } });
  const imported = await viewer.importXML(xml);
  const canvas = viewer.get('canvas'), reg = viewer.get('elementRegistry');
  canvas.zoom('fit-viewport', 'auto');
  const d = { zoom: canvas.zoom(), warnings: imported.warnings.map(w => w.message), shapes: [], edges: [], texts: [] };
  reg.forEach(el => {
    if (!el.parent) return;
    const gfx = reg.getGraphics(el), t = gfx.querySelector('text'), b = t ? t.getBBox() : null;
    if (el.waypoints) d.edges.push({ id: el.id, pts: el.waypoints.map(p => [p.x, p.y]) });
    else if (el.type === 'label') d.texts.push({ of: el.labelTarget && el.labelTarget.id, kind: 'label', x: el.x + (b ? b.x : 0), y: el.y + (b ? b.y : 0), w: b ? b.width : 0, h: b ? b.height : 0, text: t ? t.textContent : '' });
    else { d.shapes.push({ id: el.id, type: el.type, x: el.x, y: el.y, w: el.width, h: el.height, host: el.host && el.host.id });
      if (t && /Task$/.test(el.type)) d.texts.push({ of: el.id, kind: 'box', lines: t.querySelectorAll('tspan').length, text: t.textContent, w: b.width, boxW: el.width }); }
  });
  viewer.destroy();
  const boxes = d.shapes.filter(s => !/Lane|Participant/.test(s.type)), lanes = d.shapes.filter(s => /Lane/.test(s.type));
  const hit = (a, b, m = 0) => a.x < b.x + b.w - m && b.x < a.x + a.w - m && a.y < b.y + b.h - m && b.y < a.y + a.h - m;
  const res = { zoom: d.zoom, warnings: d.warnings, lanes: lanes.length, boxes: boxes.length, edges: d.edges.length,
                overlap: [], through: [], stacked: [], crossing: [], onBox: [], onLabel: [], onLine: [], threeLines: [], wideText: [], outside: [] };
  boxes.forEach((a, i) => boxes.slice(i + 1).forEach(b => { if (a.host !== b.id && b.host !== a.id && hit(a, b)) res.overlap.push(a.id + ' × ' + b.id); }));
  const segs = [];
  d.edges.forEach(e => { for (let i = 0; i + 1 < e.pts.length; i++) segs.push({ id: e.id, a: e.pts[i], b: e.pts[i + 1], first: i === 0, last: i + 2 === e.pts.length }); });
  const box = s => ({ L: Math.min(s.a[0], s.b[0]), R: Math.max(s.a[0], s.b[0]), T: Math.min(s.a[1], s.b[1]), B: Math.max(s.a[1], s.b[1]) });
  segs.forEach(s => { const { L, R, T, B } = box(s);
    boxes.forEach(b => { if (b.type === 'bpmn:BoundaryEvent') return;
      const touch = p => p[0] >= b.x - 1 && p[0] <= b.x + b.w + 1 && p[1] >= b.y - 1 && p[1] <= b.y + b.h + 1;
      const m = (s.first && touch(s.a)) || (s.last && touch(s.b)) ? 2 : 1;      // 제 양 끝 상자는 변에 닿는다 — 그 안으로 파고드는 것만 잡는다
      if (L < b.x + b.w - m && R > b.x + m && T < b.y + b.h - m && B > b.y + m) res.through.push(s.id + ' → ' + b.id); }); });
  segs.forEach((s, i) => segs.slice(i + 1).forEach(t => { if (s.id === t.id) return;
    const sh = Math.abs(s.a[1] - s.b[1]) < 0.5, th = Math.abs(t.a[1] - t.b[1]) < 0.5, sv = Math.abs(s.a[0] - s.b[0]) < 0.5, tv = Math.abs(t.a[0] - t.b[0]) < 0.5;
    const ov = (a1, a2, b1, b2) => Math.min(Math.max(a1, a2), Math.max(b1, b2)) - Math.max(Math.min(a1, a2), Math.min(b1, b2));
    if (sh && th && Math.abs(s.a[1] - t.a[1]) < 6 && ov(s.a[0], s.b[0], t.a[0], t.b[0]) > 6) res.stacked.push([s.id, t.id]);
    else if (sv && tv && Math.abs(s.a[0] - t.a[0]) < 6 && ov(s.a[1], s.b[1], t.a[1], t.b[1]) > 6) res.stacked.push([s.id, t.id]);
    else if ((sh && tv) || (sv && th)) { const h = sh ? s : t, v = sh ? t : s, x = v.a[0], y = h.a[1];
      if (x > Math.min(h.a[0], h.b[0]) + 1 && x < Math.max(h.a[0], h.b[0]) - 1 && y > Math.min(v.a[1], v.b[1]) + 1 && y < Math.max(v.a[1], v.b[1]) - 1) res.crossing.push(s.id + ' + ' + t.id); } }));
  const labels = d.texts.filter(t => t.kind === 'label' && t.text);
  const touches = (t, b) => { if (!hit(t, b, 1)) return false; const cx = b.x + b.w / 2, cy = b.y + b.h / 2;      // 이름 사각형이 상자의 실제 모양(마름모 · 원 · 사각형)에 닿는가
    const px = Math.min(Math.max(cx, t.x), t.x + t.w), py = Math.min(Math.max(cy, t.y), t.y + t.h);
    if (/Gateway/.test(b.type)) return Math.abs(px - cx) / (b.w / 2) + Math.abs(py - cy) / (b.h / 2) < 0.97;
    if (/Event/.test(b.type)) return Math.hypot(px - cx, py - cy) < b.w / 2 - 0.5;
    return true; };
  labels.forEach(t => {
    boxes.forEach(b => { if (touches(t, b)) res.onBox.push(`「${t.text}」 × ${b.id}`); });
    segs.forEach(s => { const { L, R, T, B } = box(s); if (L < t.x + t.w - 1 && R > t.x + 1 && T < t.y + t.h - 2 && B > t.y + 2) res.onLine.push(`「${t.text}」 × ${s.id}`); });
    lanes.forEach(l => [l.y, l.y + l.h].forEach(y => { if (y > t.y + 1 && y < t.y + t.h - 1) res.onLine.push(`「${t.text}」 × 차선 경계`); }));
    if (lanes.length && !lanes.some(l => t.x >= l.x + 30 && t.x + t.w <= l.x + l.w && t.y + t.h > l.y && t.y < l.y + l.h)) res.outside.push(`「${t.text}」`);
  });
  labels.forEach((a, i) => labels.slice(i + 1).forEach(b => { if (hit(a, b, 1)) res.onLabel.push(`「${a.text}」 × 「${b.text}」`); }));
  d.texts.filter(t => t.kind === 'box').forEach(t => { if (t.lines > 2) res.threeLines.push(`${t.of}「${t.text}」 ${t.lines}줄`); if (t.w > t.boxW - 6) res.wideText.push(`${t.of}「${t.text}」`); });
  if (lanes.length) boxes.forEach(b => { const cx = b.x + b.w / 2, cy = b.y + b.h / 2; if (!lanes.some(l => cx > l.x + 30 && cx < l.x + l.w && cy > l.y && cy < l.y + l.h)) res.outside.push(b.id); });
  return res;
}"""


@pytest.fixture(scope='module')
def chromium():
    """브라우저 하나와 화면 파일(it/portal/www)을 내주는 정적 서버 하나 — 이 파일의 그림 시험이 함께 쓴다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            yield browser, served.url
            browser.close()
    finally:
        served.close()


@pytest.fixture(scope='module')
def viewer(chromium):
    """화면 파일 가운데 보기 부품(vendor/bpmn-js)과 글꼴만 쓴다 — 포털의 화면 코드와 서버 응답은 쓰지 않는다."""
    browser, url = chromium
    pg = browser.new_page(viewport={'width': 1440, 'height': 900})
    pg.route('**/blank.html', lambda route: route.fulfill(body=PAGE, content_type='text/html'))
    pg.goto(url + '/blank.html')
    pg.wait_for_function("typeof BpmnJS !== 'undefined'")
    yield pg
    pg.close()


@pytest.mark.parametrize('name', list(PICTURES))
def test_그린_그림에서_상자와_선과_이름이_서로_겹치지_않는다(viewer, name):
    got = viewer.evaluate(JUDGE, PICTURES[name])
    nodes, flows, lanes, _, _ = _elements(PICTURES[name])
    assert got['warnings'] == [] and (got['boxes'], got['edges'], got['lanes']) == (len(nodes), len(flows), len(lanes)), got
    assert got['overlap'] == [], f"상자 겹침: {got['overlap']}"
    assert got['through'] == [], f"선이 상자 안을 지남: {got['through']}"
    stacked = {frozenset(pair) for pair in got['stacked']} - SHARED_STEM.get(name, set())
    assert stacked == set(), f'선끼리 포개짐: {sorted(map(sorted, stacked))}'
    assert got['crossing'] == [], f"선끼리 가로지름: {got['crossing']}"
    assert got['onBox'] == [] and got['onLabel'] == [] and got['onLine'] == [], f"이름이 상자 · 다른 이름 · 선과 겹침: {got['onBox'] + got['onLabel'] + got['onLine']}"
    assert got['threeLines'] == [] and got['wideText'] == [], f"상자 이름이 세 줄 이상이거나 상자보다 넓음: {got['threeLines'] + got['wideText']}"
    assert got['outside'] == [], f"차선 밖: {got['outside']}"


@pytest.mark.parametrize('name', list(PICTURES))
def test_전체가_큰_판_한_장에_글자를_읽을_크기로_들어온다(viewer, name):
    """[전체 흐름 보기]의 큰 판(1440 × 900 화면의 그림 자리 1376 × 760)에 흐름 전체를 맞추고 화면처럼 가장자리를 물렸을 때(× 0.9)
    상자 글자(13px)가 10px 안팎으로 읽힌다. 이보다 길어지는 흐름은 그림을 줄이지 않고 접어서 놓는다."""
    got = viewer.evaluate(JUDGE, PICTURES[name])
    assert got['zoom'] * 0.9 >= 0.75, got['zoom']


# ---------------------------------------------------------------- 화면의 id 대응과 같은가
@pytest.fixture(scope='module')
def portal_page(chromium):
    browser, url = chromium
    pg = browser.new_page()
    pg.route('**/svc/**', lambda route: route.abort() if route.request.url.endswith('/stream') else route.fulfill(json={}))
    pg.goto(url + '/index.html')
    pg.wait_for_function("typeof UI !== 'undefined' && !!window.hydFlow")
    yield pg
    pg.close()


@pytest.mark.parametrize('name', list(PROVIDED))
def test_서버가_내주는_그림의_id_는_화면이_정의의_id_에서_만드는_id_와_같다(portal_page, name):
    """화면(flow.js)은 처리 건의 상태를 정의의 id(task:draft)로 받아 xid 로 그림의 요소를 찾는다 — 서버의 xid 가 같은 규칙이어야 상태 표시가 얹힌다.
    화면이 정의에서 만드는 그림(defToXml)의 id 와 서버가 내주는 그림의 id 를 맞댄다."""
    raw = _definition(name)
    made = portal_page.evaluate("def => [...new DOMParser().parseFromString(hydFlow.defToXml(def), 'application/xml').querySelector('process').children].map(el => el.getAttribute('id'))", raw)
    nodes, flows, _, _, _ = _elements(bpmn_store.provided_diagram(raw, PICTURES[name]))
    assert sorted(made) == sorted(list(nodes) + list(flows))
