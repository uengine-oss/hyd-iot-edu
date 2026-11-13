// 배치 정보(BPMNDiagram)가 없는 BPMN 을 받았을 때 자동으로 배치한다. vendor/bpmn-auto-layout/bpmn-auto-layout.min.js 를 먼저 실어야 한다.
// bpmn-auto-layout 은 각 요소의 <incoming> · <outgoing> 으로 선을 찾는다. bpmn.io 가 저장한 파일에는 늘 있지만 손이나 AI 가 쓴 XML 에는 없을 수 있어,
// 없으면 선(sequenceFlow)의 sourceRef · targetRef 에서 채운 뒤 배치한다(채우지 않으면 선이 하나도 그려지지 않고 상자가 한 줄로 쌓인다 — 2026-11-14 실측).
// 자동 배치는 차선(lane)을 그리지 않는다. 돌려주는 값: { xml, laidOut } — laidOut 이 true 면 화면이 「자동으로 놓았습니다」라고 알린다.
export async function ensureLayout(xml) {
  if (/<(\w+:)?BPMNDiagram[\s>]/.test(xml)) return { xml, laidOut: false };
  const NS = 'http://www.omg.org/spec/BPMN/20100524/MODEL';
  const doc = new DOMParser().parseFromString(xml, 'application/xml');
  if (doc.querySelector('parsererror')) throw new Error('BPMN XML 을 읽지 못했습니다: ' + doc.querySelector('parsererror').textContent.slice(0, 200));
  const byId = {}; doc.querySelectorAll('[id]').forEach((e) => { byId[e.getAttribute('id')] = e; });
  const prefix = doc.documentElement.prefix ? doc.documentElement.prefix + ':' : '';
  doc.querySelectorAll('sequenceFlow').forEach((flow) => {
    for (const [ref, tag] of [['sourceRef', 'outgoing'], ['targetRef', 'incoming']]) {
      const owner = byId[flow.getAttribute(ref)]; if (!owner) continue;
      const has = [...owner.children].some((c) => c.localName === tag && c.textContent.trim() === flow.getAttribute('id'));
      if (!has) { const el = doc.createElementNS(NS, prefix + tag); el.textContent = flow.getAttribute('id'); owner.insertBefore(el, owner.firstChild); }
    }
  });
  return { xml: await globalThis.BpmnAutoLayout.layoutProcess(new XMLSerializer().serializeToString(doc)), laidOut: true };
}
