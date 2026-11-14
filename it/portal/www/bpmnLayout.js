/* 배치 정보(BPMNDiagram)가 없는 BPMN 을 받았을 때 자동으로 배치한다 — window.hydBpmnLayout.ensureLayout(xml) → { xml, laidOut }.
   UI.need('bpmn-layout') 이 vendor/bpmn-auto-layout/bpmn-auto-layout.min.js(전역 BpmnAutoLayout) 다음에 이 파일을 싣는다.
   bpmn-auto-layout 은 각 요소의 <incoming> · <outgoing> 으로 선을 찾는다. bpmn.io 가 저장한 파일에는 늘 있지만 손이나 AI 가 쓴 XML 에는 없을 수 있어,
   없으면 선(sequenceFlow)의 sourceRef · targetRef 에서 채운 뒤 배치한다(채우지 않으면 선이 하나도 그려지지 않고 상자가 한 줄로 쌓인다 — 2026-11-14 실측).
   자동 배치는 차선(lane)을 그리지 않는다. laidOut 이 true 면 화면이 그 사실을 그림 위에 알린다(디자인 기준 6-2).
   자동 배치 부품이 놓지 못하는 흐름(다시 수행 가지가 있는 흐름 — 내부 오류)은 이 파일의 단순 층 배치(simpleLayout)로 놓는다 — 그림을 못 보이는 일이 없게. */
(function () {
  const NS = 'http://www.omg.org/spec/BPMN/20100524/MODEL';
  async function ensureLayout(xml) {
    if (/<(\w+:)?BPMNDiagram[\s>]/.test(xml)) return { xml, laidOut: false };
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    const bad = doc.querySelector('parsererror');
    if (bad) throw new Error('BPMN XML 을 읽지 못했습니다: ' + bad.textContent.slice(0, 200));
    const byId = {}; doc.querySelectorAll('[id]').forEach(e => { byId[e.getAttribute('id')] = e; });
    const prefix = doc.documentElement.prefix ? doc.documentElement.prefix + ':' : '';
    doc.querySelectorAll('sequenceFlow').forEach(flow => {
      for (const [ref, tag] of [['sourceRef', 'outgoing'], ['targetRef', 'incoming']]) {
        const owner = byId[flow.getAttribute(ref)]; if (!owner) continue;
        const has = [...owner.children].some(c => c.localName === tag && c.textContent.trim() === flow.getAttribute('id'));
        if (!has) { const el = doc.createElementNS(NS, prefix + tag); el.textContent = flow.getAttribute('id'); owner.insertBefore(el, owner.firstChild); }
      }
    });
    if (!window.BpmnAutoLayout) throw new Error('자동 배치 부품(BpmnAutoLayout)이 실리지 않았습니다 — UI.need(\'bpmn-layout\') 으로 싣습니다');
    try { return { xml: await window.BpmnAutoLayout.layoutProcess(new XMLSerializer().serializeToString(doc)), laidOut: true }; }
    catch (e) {
      // bpmn-auto-layout 1.3.0 의 한계: 여러 갈림에서 나온 가지가 같은 단계 · 같은 끝으로 다시 모이는 흐름(기준 흐름 「설비 이상 조치」, 교대 인수인계)을
      // 놓다가 내부 오류(Cannot read properties of undefined (reading 'splice'))로 멈춘다. id 가 바른 XML 로도 같다(2026-11-14 실측 — 최소 재현은
      // 「갈림 → 명령 / 정비 요청 / 보고」 + 「효과 확인 → 갈림 → 정비 요청」처럼 한 단계에 두 갈림의 가지가 모이는 꼴). 그런 흐름은 이 파일의 층 배치로 놓는다.
      // 조용히 바꾸지 않는다: 콘솔에 까닭을 남기고, 그림 위 알림은 어느 쪽이든 「자동으로 놓았습니다」다
      console.warn('[hydBpmnLayout] 자동 배치 부품이 이 흐름을 놓지 못해 층 배치로 그립니다:', e.message);
      return { xml: simpleLayout(doc), laidOut: true };
    }
  }

  /* 층 배치(자동 배치 부품이 놓지 못하는 흐름에만): 시작에서 왼쪽 → 오른쪽으로 층(칸)을 나누고(되돌아가는 선은 층 계산에서 뺀다), 층 안에서는 앞 단계의 줄에 가깝게 놓는다.
     상자는 격자의 칸 하나에 하나라 겹치지 않는다. 선은 상자가 없는 통로로만 다닌다: 칸과 칸 사이의 세로 통로, 줄과 줄 사이의 가로 통로.
     바로 옆 칸의 같은 줄(사이에 상자가 없을 때)만 곧게 잇고, 그 밖에는 「오른쪽 세로 통로 → 가로 통로 → 받는 상자 왼쪽 세로 통로」로 돌아간다 — 선이 다른 상자 안을 지나지 않는다.
     경계 이벤트는 붙은 단계의 아래 변에 두고, 거기서 나가는 선은 그 줄 아래의 가로 통로로 내려간다. 차선은 그리지 않는다. */
  const SIZE = el => /Task$|^task$|subProcess|callActivity|transaction/i.test(el.localName) ? [100, 80] : /Gateway$/.test(el.localName) ? [50, 50] : [36, 36];
  function simpleLayout(doc) {
    const DI = 'http://www.omg.org/spec/BPMN/20100524/DI', DC = 'http://www.omg.org/spec/DD/20100524/DC', DDI = 'http://www.omg.org/spec/DD/20100524/DI';
    const root = doc.documentElement, proc = doc.querySelector('process');
    if (!proc) throw new Error('BPMN XML 에 흐름(process)이 없습니다');
    doc.querySelectorAll('collaboration').forEach(n => n.remove());      // 보기용 사본이다 — 풀 · 차선 없이 흐름 하나만 그린다
    const isNode = c => /Event$|Task$|^task$|Gateway$|subProcess|callActivity|transaction/i.test(c.localName);
    const nodes = [...proc.children].filter(isNode), flows = [...proc.children].filter(c => c.localName === 'sequenceFlow');
    const id = n => n.getAttribute('id'), byId = Object.fromEntries(nodes.map(n => [id(n), n]));
    const host = n => (n.localName === 'boundaryEvent' ? n.getAttribute('attachedToRef') : null);
    const main = nodes.filter(n => !host(n));
    // 층 계산에 쓰는 선: 경계 이벤트에서 나가는 선은 붙은 단계에서 나가는 것으로 본다
    const from = f => { const s = byId[f.getAttribute('sourceRef')]; return s && host(s) ? host(s) : f.getAttribute('sourceRef'); };
    const edges = flows.map(f => ({ f, s: from(f), t: f.getAttribute('targetRef') })).filter(e => byId[e.s] && byId[e.t] && !host(byId[e.t]));
    const out = {}; edges.forEach(e => { (out[e.s] ||= []).push(e); });
    // 되돌아가는 선: 깊이 우선으로 훑다가 지금 길 위의 단계로 가는 선
    const state = {}, back = new Set();
    const walk = n => { state[n] = 1; (out[n] || []).forEach(e => { if (state[e.t] === 1) back.add(e); else if (!state[e.t]) walk(e.t); }); state[n] = 2; };
    const starts = main.filter(n => n.localName === 'startEvent').map(id);
    [...starts, ...main.map(id)].forEach(n => { if (!state[n]) walk(n); });
    const fwd = edges.filter(e => !back.has(e)), layer = {}, indeg = {};
    main.forEach(n => { layer[id(n)] = 0; indeg[id(n)] = 0; }); fwd.forEach(e => { indeg[e.t] += 1; });
    const queue = main.map(id).filter(n => !indeg[n]), order = [];
    while (queue.length) { const n = queue.shift(); order.push(n); fwd.filter(e => e.s === n).forEach(e => { layer[e.t] = Math.max(layer[e.t], layer[n] + 1); if (!(indeg[e.t] -= 1)) queue.push(e.t); }); }
    // 줄: 층마다 앞 단계 줄의 평균에 가장 가까운 빈 줄
    const row = {}, used = {};
    order.forEach(n => {
      const preds = fwd.filter(e => e.t === n && row[e.s] != null).map(e => row[e.s]);
      const want = preds.length ? Math.round(preds.reduce((a, b) => a + b, 0) / preds.length) : 0, taken = (used[layer[n]] ||= new Set());
      let r = want; for (let d = 0; taken.has(r); d += 1) { r = want + d + 1; if (!taken.has(r)) break; r = want - d - 1; if (r >= 0 && !taken.has(r)) break; r = want + d + 1; }
      row[n] = r; taken.add(r);
    });
    // 격자: 칸 = 상자 자리 100 × 80 + 오른쪽 세로 통로 100, 줄 = 상자 자리 80 + 아래 가로 통로 70
    const COL = 200, ROW = 150, X0 = 80, Y0 = 60, box = {}, cell = {};
    main.forEach(n => { const [w, h] = SIZE(n), k = id(n); cell[k] = [layer[k], row[k] || 0]; box[k] = { x: X0 + layer[k] * COL + (100 - w) / 2, y: Y0 + (row[k] || 0) * ROW + (80 - h) / 2, w, h }; });
    nodes.filter(host).forEach((n, i) => { const hb = box[host(n)]; if (hb) { cell[id(n)] = cell[host(n)]; box[id(n)] = { x: hb.x + hb.w - 46 - (i % 2) * 40, y: hb.y + hb.h - 18, w: 36, h: 36 }; } });
    const filled = new Set(main.map(n => cell[id(n)].join(',')));
    // 통로의 자리: 세로 통로 c 는 칸 c 의 오른쪽(c = -1 이면 첫 칸의 왼쪽), 가로 통로 r 는 줄 r 의 아래. 같은 통로를 쓰는 선은 옆 자리로 비켜 놓는다
    const vUse = {}, hUse = {};
    const vLane = c => X0 + c * COL + 116 + ((vUse[c] = (vUse[c] || 0) + 1) - 1) % 8 * 9;
    const hLane = r => Y0 + r * ROW + 108 + ((hUse[r] = (hUse[r] || 0) + 1) - 1) % 4 * 8;
    const el = (ns, name, attrs) => { const e = doc.createElementNS(ns, name); Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v)); return e; };
    const diagram = el(DI, 'bpmndi:BPMNDiagram', { id: 'BPMNDiagram_1' }), plane = el(DI, 'bpmndi:BPMNPlane', { id: 'BPMNPlane_1', bpmnElement: id(proc) });
    root.setAttribute('xmlns:bpmndi', DI); root.setAttribute('xmlns:dc', DC); root.setAttribute('xmlns:di', DDI);
    Object.entries(box).forEach(([k, b]) => {
      const shape = el(DI, 'bpmndi:BPMNShape', { id: k + '_di', bpmnElement: k, ...(byId[k].localName === 'exclusiveGateway' ? { isMarkerVisible: 'true' } : {}) });
      shape.appendChild(el(DC, 'dc:Bounds', { x: b.x, y: b.y, width: b.w, height: b.h })); plane.appendChild(shape);
    });
    flows.forEach(f => {
      const sk = f.getAttribute('sourceRef'), tk = f.getAttribute('targetRef'), s = box[sk], t = box[tk]; if (!s || !t) return;
      const [cs, rs] = cell[sk], [ct, rt] = cell[tk], fromBoundary = !!host(byId[sk]);
      const sy = s.y + s.h / 2, ty = t.y + t.h / 2, sx = s.x + s.w, tx = t.x;
      const clear = () => { for (let c = cs + 1; c < ct; c++) if (filled.has(c + ',' + rs)) return false; return true; };      // 같은 줄의 사이 칸이 비었는가
      let pts;
      if (fromBoundary) { const y = hLane(rs), g = vLane(ct - 1); pts = [[s.x + s.w / 2, s.y + s.h], [s.x + s.w / 2, y], [g, y], [g, ty], [tx, ty]]; }      // 경계 이벤트: 붙은 단계 아래의 가로 통로로
      else if (rs === rt && ct > cs && clear()) pts = [[sx, sy], [tx, ty]];                                    // 같은 줄, 사이에 상자 없음: 곧게
      else if (ct === cs + 1) { const g = vLane(cs); pts = [[sx, sy], [g, sy], [g, ty], [tx, ty]]; }          // 바로 옆 칸의 다른 줄: 사이 세로 통로 하나로
      else { const g1 = vLane(cs), y = hLane(rt > rs ? rs : rt < rs ? rs - 1 : rs), g2 = vLane(ct - 1); pts = [[sx, sy], [g1, sy], [g1, y], [g2, y], [g2, ty], [tx, ty]]; }      // 건너뛰거나 되돌아가는 선: 세로 통로 → 가로 통로 → 세로 통로
      const edge = el(DI, 'bpmndi:BPMNEdge', { id: id(f) + '_di', bpmnElement: id(f) });
      pts.forEach(([x, y]) => edge.appendChild(el(DDI, 'di:waypoint', { x: Math.round(x), y: Math.round(y) }))); plane.appendChild(edge);
    });
    diagram.appendChild(plane); root.appendChild(diagram);
    return new XMLSerializer().serializeToString(doc);
  }
  window.hydBpmnLayout = { ensureLayout };
})();
