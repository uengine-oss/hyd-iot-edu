"""흐름 그림의 원본 만들기와 자동 배치(it/portal/www/flow.js defToXml · bpmnLayout.js) — 실제 브라우저(Playwright Chromium)에서 실제 bpmn-js 로 그려 본다.

정의로만 등록된 흐름(그림 파일 없음)은 화면이 정의에서 BPMN 을 만들어 자동으로 놓는다. 그 정의의 id 는 `task:draft` · `seq:0` 처럼 쌍점을 품는다 —
XML 의 id 로는 쓸 수 없는 글자라 그대로 쓰면 선이 하나도 그려지지 않았다(2026-11-14 독립 검토 가-1). 실제 기동 정의 파일 둘로 잰다:
교대 인수인계(it/process/definitions/shift_handover_v1.json) · 설비 이상 조치(anomaly_response_v22.json).
서버 응답은 쓰지 않는다(화면 파일과 vendor 만 내준다 — 다른 요청은 빈 응답)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import ROOT, WWW, Served

DEFS = {name: json.loads((ROOT / 'it' / 'process' / 'definitions' / file).read_text(encoding='utf-8'))
        for name, file in [('교대 인수인계', 'shift_handover_v1.json'), ('설비 이상 조치', 'anomaly_response_v22.json')]}

# 그림 하나를 그리고(hydFlow.show — 흐름 화면이 쓰는 길) 그려진 요소를 센다. 그리고 배치된 XML 의 상자 · 선 좌표를 읽어 겹침과 가로지름을 찾는다
DRAW = """async def => {
  const host = document.createElement('div'); host.style.cssText = 'width:1200px;height:600px'; document.body.append(host);
  const xml = hydFlow.defToXml(def);
  hydFlow.show(host, { key: 'k', title: 't', mine: true, load: async () => ({ xml, source: 'definition' }) });      // mine: 내가 가져온 흐름 — 자동 배치 알림은 여기에만 뜬다
  for (let i = 0; i < 100 && !host._flow.D; i++) { if (host.querySelector('.alert')) throw new Error(host.querySelector('.alert').innerText); await new Promise(r => setTimeout(r, 100)); }
  const D = host._flow.D, reg = D.viewer.get('elementRegistry');
  const doc = new DOMParser().parseFromString(D.src.xml, 'application/xml');
  const shapes = [...doc.querySelectorAll('BPMNShape')].map(s => { const b = s.querySelector('Bounds'); return { id: s.getAttribute('bpmnElement'), x: +b.getAttribute('x'), y: +b.getAttribute('y'), w: +b.getAttribute('width'), h: +b.getAttribute('height') }; });
  const kind = id => doc.querySelector(`[id="${id}"]`).localName, attached = id => doc.querySelector(`[id="${id}"]`).getAttribute('attachedToRef');
  const overlaps = [];
  shapes.forEach((a, i) => shapes.slice(i + 1).forEach(b => {
    if (attached(a.id) === b.id || attached(b.id) === a.id) return;      // 경계 이벤트는 붙은 단계의 변에 걸쳐 놓는다
    if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) overlaps.push(a.id + ' × ' + b.id);
  }));
  const through = [];
  doc.querySelectorAll('BPMNEdge').forEach(edge => {
    const flow = doc.querySelector(`[id="${edge.getAttribute('bpmnElement')}"]`), ends = [flow.getAttribute('sourceRef'), flow.getAttribute('targetRef')];
    const own = new Set([...ends, ...ends.map(attached).filter(Boolean)]);      // 제 양 끝(경계 이벤트면 붙은 단계까지)은 닿는다
    const pts = [...edge.querySelectorAll('waypoint')].map(p => [+p.getAttribute('x'), +p.getAttribute('y')]);
    for (let i = 0; i + 1 < pts.length; i++) {
      const [x1, y1] = pts[i], [x2, y2] = pts[i + 1], L = Math.min(x1, x2), R = Math.max(x1, x2), T = Math.min(y1, y2), B = Math.max(y1, y2);
      shapes.forEach(s => { if (!own.has(s.id) && kind(s.id) !== 'boundaryEvent' && L < s.x + s.w - 1 && R > s.x + 1 && T < s.y + s.h - 1 && B > s.y + 1) through.push(flow.getAttribute('id') + ' → ' + s.id); });
    }
  });
  return { connections: reg.filter(el => el.waypoints).length, boxes: reg.filter(el => !el.waypoints && el.type !== 'label' && el.parent).length, laidOut: D.src.laidOut,
           note: host.querySelector('[data-flow-note]').textContent, overlaps, through, ids: reg.filter(el => !el.waypoints && el.type !== 'label' && el.parent).map(el => el.id).slice(0, 3) };
}"""


@pytest.fixture(scope='module')
def page():
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            pg = browser.new_page()
            pg.route('**/svc/**', lambda route: route.abort() if route.request.url.endswith('/stream') else route.fulfill(json={}))
            pg.goto(served.url + '/index.html')
            pg.wait_for_function("typeof UI !== 'undefined' && !!window.hydFlow")
            yield pg
            browser.close()
    finally:
        served.close()


@pytest.mark.parametrize('name', list(DEFS))
def test_쌍점이_든_id_의_정의도_선이_정의의_연결_수만큼_그려진다(page, name):
    """정의의 id(task:draft · seq:0)를 XML 에 쓸 수 있는 id 로 바꾸는 대응이 상자 · 선 · 선의 양 끝에 똑같이 쓰여야 선이 이어진다."""
    d = DEFS[name]
    assert any(':' in q['source'] for q in d['sequences']), '이 시험은 쌍점이 든 id 의 정의로 잰다'
    got = page.evaluate(DRAW, d)
    assert got['connections'] == len(d['sequences']), got
    assert got['boxes'] == len(d['events']) + len(d['activities']) + len(d['gateways']), got


@pytest.mark.parametrize('name', list(DEFS))
def test_자동으로_놓은_그림은_상자가_겹치지_않고_선이_다른_상자_안을_지나지_않는다(page, name):
    """자동 배치 부품이 놓지 못하는 흐름(가지가 다시 모이는 흐름)은 화면의 층 배치로 놓는다 — 그 그림에서 상자 겹침 0 · 선이 다른 상자 안을 지나는 곳 0."""
    got = page.evaluate(DRAW, DEFS[name])
    assert got['laidOut'] is True and '자동으로' in got['note'], got      # 자동으로 놓았다는 것을 그림 위에서 말한다
    assert got['overlaps'] == [], got['overlaps']
    assert got['through'] == [], got['through']


def test_상태_표시는_정의의_id_로_걸고_누른_단계도_정의의_id_로_돌려준다(page):
    """처리 건의 진행 길: 작업 행은 정의의 id(task:draft)로 온다 — 그림의 요소(바뀐 id)에 지금 표시가 얹히고, 그 상자를 누르면 정의의 id 가 돌아와야 한다."""
    d = dict(DEFS['교대 인수인계'], processDefinitionId='shift_handover_t', version='t')
    got = page.evaluate("""async def => {
      const host = document.createElement('div'); host.style.cssText = 'width:1200px;height:500px'; document.body.append(host);
      const picked = [];
      hydFlow.mount(host, { definition: def, instance: { proc_inst_id: 'p1', status: 'RUNNING' }, workitems: [{ id: 'w1', activity_id: 'task:draft', status: 'IN_PROGRESS', start_date: '2026-11-14T00:00:00Z' }] }, { mine: [], onPick: id => picked.push(id) });
      for (let i = 0; i < 100 && !host._flow.D; i++) await new Promise(r => setTimeout(r, 100));
      const now = [...host.querySelectorAll('.djs-shape.is-now')].map(n => n.getAttribute('data-element-id'));
      const el = host._flow.D.viewer.get('elementRegistry').get(now[0]);
      host._flow.D.viewer.get('eventBus').fire('element.click', { element: el });
      return { now: now.length, tip: host.querySelectorAll('.bpmn-tip').length, picked };
    }""", d)
    assert got == {'now': 1, 'tip': 1, 'picked': ['task:draft']}, got
