/* 흐름 그림 — bpmn-js NavigatedViewer(보기 전용)로 그린다(디자인 기준 6-2). 포털은 그리지 않는다: 그림의 모양과 배치는 bpmn.io 에서 그린 그대로이고,
   여기서는 색(어두운 캔버스)과 처리 건의 상태 표시(끝남 · 지금 · 남음 · 멈춤)만 얹는다. loaded after instanceSteps.js(단계 상태 규칙 hydSteps).

   그림의 원본(xmlOf):
     ① 포털로 가져와 등록한 흐름(정의에 bpmnImport 가 있다) — GET /api/flows/{id}/versions/{v}/bpmn 이 준 .bpmn 원본.
        배치 정보(BPMNDiagram)가 없으면 hydBpmnLayout.ensureLayout 으로 자동 배치하고 그 사실을 그림 위에 알린다.
     ② 그림 원본 없이 정의(JSON)로만 등록된 흐름 — 정의의 단계 · 갈림 · 선으로 BPMN XML 을 만들고(defToXml) 자동 배치한다. 그 사실도 그림 위에 알린다.
   처리 건 화면(instances.js)이 쓰는 것:
     pathModel(def, workitems, instance)   지나온 단계와 남은 길(「몇 단계 가운데 몇 번째」 · 「남은 단계」 줄)
     mount(host, view, { mine, onPick })    진행 길 캔버스: 지금 단계가 왼쪽 40 % 자리에 오게 열고, 축소 · 확대 · 지금 단계로 · 전체 흐름(큰 대화상자)
   2초마다 다시 읽어도 같은 처리 건이면 그림을 다시 싣지 않는다 — 상태 표시만 바꾸고, 끌어 옮긴 자리와 배율은 그대로 둔다. 지금 단계가 바뀐 때에만 그 단계로 옮긴다. */
(function () {
  const e = s => esc(s);
  const cv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  /* ---------------------------------------------------------------- 지나온 단계와 남은 길(그림과 상관없이 정의 · 작업 행으로 계산) */
  function pathModel(def, workitems, instance) {
    const roles = new Map((def.roles || []).map(r => [r.name, r.endpoint]));
    const acts = new Map((def.activities || []).map(a => [a.id, a]));
    const events = new Map((def.events || []).map(x => [x.id, x]));
    const gateways = new Set((def.gateways || []).map(g => g.id));
    const next = new Map();
    (def.sequences || []).forEach(q => { if (!next.has(q.source)) next.set(q.source, []); next.get(q.source).push(q); });
    // 지나온 단계: 활동마다 가장 최근 작업 행 하나(다시 수행하면 마지막 회차), 시작한 차례대로. 예정(TODO)과 엔진이 시작 전에 취소한 가지는 지나온 것이 아니다
    const latest = latestRows(workitems, id => acts.has(id));
    const order = Object.fromEntries((def.activities || []).map((a, i) => [a.id, i]));
    const passed = [...latest.values()].sort((a, b) => String(a.start_date || '').localeCompare(String(b.start_date || '')) || order[a.activity_id] - order[b.activity_id]);
    const finished = !!instance && ['COMPLETED', 'CANCELLED'].includes(instance.status);
    const who = a => { const ep = a.agent || roles.get(a.role) || ''; return ep === 'sys:agent' || /^agent:/.test(ep) || a.orchestration === 'cliagents' ? 'agent' : /^role:|^user:/.test(ep) ? 'human' : 'system'; };
    const nodes = passed.map(w => ({ id: w.activity_id, wid: w.id, name: acts.get(w.activity_id).name, state: rowState(w), who: who(acts.get(w.activity_id)), role: acts.get(w.activity_id).role || '' }));
    // 남은 길: 지금 단계(없으면 마지막으로 지나온 단계)에서 끝 이벤트까지. 갈림에서는 조건이 붙은 가지 가운데 정의에 먼저 적힌 것(일이 진행되는 가지 — 「승인」 「예」)을 따라간다.
    // 조건 없는 가지는 그 밖의 경우(반려 · 미달 · 그 밖)의 길이라 남은 길로 보이지 않는다. 실제로 그 가지를 타면 지나온 길에 그대로 나온다
    let end = null;
    if (finished) end = events.get(instance.end_event) || null;
    else {
      const live = nodes.filter(n => n.state === 'now' || n.state === 'hold');
      let cur = (live[live.length - 1] || nodes[nodes.length - 1] || {}).id || ((def.events || []).find(x => x.type === 'startEvent') || {}).id;
      const seen = new Set(nodes.map(n => n.id));
      for (let guard = 0; cur && guard < 200; guard++) {
        const outs = (next.get(cur) || []).filter(q => !(events.get(q.target) || {}).attachedTo);
        const q = outs.find(x => x.condition && !seen.has(x.target)) || outs.find(x => !seen.has(x.target));
        if (!q) break;
        cur = q.target; seen.add(cur);
        if (acts.has(cur)) { const a = acts.get(cur); nodes.push({ id: cur, name: a.name, state: 'todo', who: who(a), role: a.role || '' }); }
        else if (!gateways.has(cur) && (events.get(cur) || {}).type === 'endEvent') { end = events.get(cur); break; }
      }
    }
    const start = (def.events || []).find(x => x.type === 'startEvent') || null;
    return { nodes, start, end, finished, started: latest.size > 0 };
  }
  function latestRows(workitems, known) {
    const latest = new Map();
    (workitems || []).forEach(w => {
      if (!known(w.activity_id) || w.status === 'TODO') return;
      if (w.status === 'CANCELLED' && /^cancelled:/i.test(String(w.log || '').trim())) return;
      const o = latest.get(w.activity_id);
      if (!o || (w.generation || 0) > (o.generation || 0) || ((w.generation || 0) === (o.generation || 0) && String(w.start_date || '') >= String(o.start_date || ''))) latest.set(w.activity_id, w);
    });
    return latest;
  }
  const rowState = w => w.draft_status === 'FAILED' || w.status === 'FAILED' || w.status === 'CANCELLED' ? 'fail' : hydSteps.stepStateOf(w.status) === 'current' ? (w.status === 'PENDING' ? 'hold' : 'now') : 'done';

  /* ---------------------------------------------------------------- 요소마다의 상태: 끝남(done) · 지금(now) · 보류(hold) · 멈춤(fail) · 남음(todo)
     단계는 가장 최근 작업 행의 상태, 갈림과 선은 실제로 지나간 것만 끝남(가지 않은 가지는 남음으로 흐리게), 끝 이벤트는 처리 건이 닿은 것만 끝남. */
  function marksOf(view) {
    const def = view.definition || {}, inst = view.instance || {}, st = {};
    const ids = new Set([...(def.activities || []), ...(def.events || []), ...(def.gateways || [])].map(x => x.id));
    const latest = latestRows(view.workitems, id => ids.has(id));
    const evIds = new Set((def.events || []).map(x => x.id));
    // 이벤트(경계 타이머 등)의 작업 행은 울렸을 때(끝났을 때)만 지나간 것이다 — 걸어 둔 타이머를 「지금」으로 그리지 않는다
    latest.forEach((w, id) => { const s = rowState(w); if (!evIds.has(id) || s === 'done') st[id] = s; });
    const start = (def.events || []).find(x => x.type === 'startEvent');
    const started = latest.size > 0 || inst.status === 'RUNNING' || inst.status === 'COMPLETED';
    if (start && started) st[start.id] = 'done';
    (def.events || []).forEach(x => { if (x.type === 'endEvent' && inst.end_event === x.id) st[x.id] = 'done'; });
    const seqs = def.sequences || [], visited = id => !!st[id];
    // 갈림은 작업 행이 없다: 들어온 쪽이 끝났고 나간 쪽 가운데 하나라도 지나갔으면 끝남. 갈림이 이어지면(갈림 → 갈림) 한 번 더 본다
    for (let pass = 0; pass < 4; pass++) {
      (def.gateways || []).forEach(g => {
        if (st[g.id]) return;
        const ins = seqs.filter(q => q.target === g.id), outs = seqs.filter(q => q.source === g.id);
        if (ins.some(q => st[q.source] === 'done') && outs.some(q => visited(q.target))) st[g.id] = 'done';
      });
    }
    // 경계 타이머의 선은 타이머가 울렸을 때(그 작업 행이 끝났을 때)만 지나간 것이다
    seqs.forEach(q => { if (st[q.source] === 'done' && visited(q.target)) st[q.id] = 'done'; });
    const now = [...latest.entries()].filter(([id, w]) => !evIds.has(id) && ['now', 'hold', 'fail'].includes(rowState(w)) && w.status !== 'CANCELLED')
      .sort((a, b) => String(a[1].start_date || '').localeCompare(String(b[1].start_date || ''))).map(([id]) => id);
    // 끝난 건에서 그림이 처음 보일 자리: 마지막으로 지나온 단계(끝 이벤트 바로 앞)
    const lastDone = [...latest.entries()].filter(([id, w]) => !evIds.has(id) && rowState(w) === 'done').sort((a, b) => String(a[1].end_date || a[1].start_date || '').localeCompare(String(b[1].end_date || b[1].start_date || ''))).map(([id]) => id).pop() || null;
    return { st, now, finished: ['COMPLETED', 'CANCELLED'].includes(inst.status), end: inst.end_event || null, lastDone };
  }

  /* ---------------------------------------------------------------- 그림 원본 */
  const xa = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  // 정의(JSON) → BPMN XML(배치 정보 없음). 이름은 화면 이름 사전(UI.flowName)을 거친다. 경계 이벤트는 붙은 단계와 멈춤 여부를 그대로 싣는다
  function defToXml(def) {
    const pid = 'Process_' + String(def.processDefinitionId || 'flow').replace(/[^A-Za-z0-9_]/g, '_');
    const name = n => n ? ` name="${xa(UI.flowName(n))}"` : '';
    const TASK = { userTask: 'userTask', serviceTask: 'serviceTask', scriptTask: 'scriptTask', manualTask: 'manualTask', task: 'task' };
    const evDef = x => x.eventDefinition === 'timer' ? '<bpmn:timerEventDefinition/>' : x.eventDefinition === 'message' ? '<bpmn:messageEventDefinition/>' : '';
    const parts = [];
    (def.events || []).forEach(x => {
      if (x.type === 'boundaryEvent' || x.attachedTo) parts.push(`<bpmn:boundaryEvent id="${xa(x.id)}"${name(x.name)} attachedToRef="${xa(x.attachedTo)}"${x.cancelActivity === false ? ' cancelActivity="false"' : ''}>${evDef(x)}</bpmn:boundaryEvent>`);
      else if (x.type === 'endEvent') parts.push(`<bpmn:endEvent id="${xa(x.id)}"${name(x.name)}/>`);
      else if (x.type === 'startEvent') parts.push(`<bpmn:startEvent id="${xa(x.id)}"${name(x.name)}>${evDef(x)}</bpmn:startEvent>`);
      else parts.push(`<bpmn:intermediateCatchEvent id="${xa(x.id)}"${name(x.name)}>${evDef(x)}</bpmn:intermediateCatchEvent>`);
    });
    (def.activities || []).forEach(a => { const t = TASK[a.type] || 'task'; parts.push(`<bpmn:${t} id="${xa(a.id)}"${name(a.name)}/>`); });
    (def.gateways || []).forEach(g => { const t = /^(exclusive|parallel|inclusive|eventBased)Gateway$/.test(g.type || '') ? g.type : 'exclusiveGateway'; parts.push(`<bpmn:${t} id="${xa(g.id)}"${name(g.name)}/>`); });
    const ids = new Set([...(def.events || []), ...(def.activities || []), ...(def.gateways || [])].map(x => x.id));
    (def.sequences || []).filter(q => ids.has(q.source) && ids.has(q.target)).forEach((q, i) =>
      parts.push(`<bpmn:sequenceFlow id="${xa(q.id || `Flow_${i}`)}"${q.name ? ` name="${xa(UI.flowSeq(q.name) || q.name)}"` : ''} sourceRef="${xa(q.source)}" targetRef="${xa(q.target)}"/>`));
    return `<?xml version="1.0" encoding="UTF-8"?><bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_${pid}" targetNamespace="http://bpmn.io/schema/bpmn"><bpmn:process id="${pid}"${name(def.processDefinitionName)} isExecutable="false">${parts.join('')}</bpmn:process></bpmn:definitions>`;
  }
  // 흐름 판본마다 한 번만 읽고 배치한다(같은 Promise). 실패하면 지워 다음에 다시 읽는다
  const XML = new Map();
  function xmlOf(def) {
    const key = `${def.processDefinitionId}@${def.version}`;
    if (XML.has(key)) return XML.get(key);
    const job = (async () => {
      let xml, source = 'definition';
      if (def.bpmnImport) {
        const r = await fetch(`${API.process}/api/flows/${encodeURIComponent(def.processDefinitionId)}/versions/${encodeURIComponent(def.version)}/bpmn`);
        if (r.ok) { xml = await r.text(); source = 'file'; }
        else if (r.status !== 404) throw new Error(`흐름 그림 원본을 읽지 못했습니다(${r.status})`);
      }
      if (!xml) xml = defToXml(def);
      if (/<(\w+:)?BPMNDiagram[\s>]/.test(xml)) return { xml, source, laidOut: false };
      await UI.need('bpmn-layout');
      const laid = await hydBpmnLayout.ensureLayout(xml);
      return { xml: laid.xml, source, laidOut: laid.laidOut };
    })();
    XML.set(key, job);
    job.catch(() => XML.delete(key));
    return job;
  }

  /* ---------------------------------------------------------------- 그리기 */
  const viewerOptions = container => ({ container, bpmnRenderer: { defaultFillColor: cv('--cv-node'), defaultStrokeColor: '#8493a8', defaultLabelColor: cv('--cv-ink') },
    textRenderer: { defaultStyle: { fontFamily: 'Pretendard Variable, sans-serif', fontSize: 13 }, externalStyle: { fontSize: 12 } } });
  const MARKERS = ['is-done', 'is-now', 'is-todo', 'is-fail', 'is-hold'];
  const skip = el => !el || el.type === 'label' || el.type === 'bpmn:Lane' || el.type === 'bpmn:Participant' || el.type === 'bpmn:Process' || el.type === 'bpmn:Collaboration' || !el.parent;
  const isBox = el => /Task$|SubProcess$|CallActivity$/.test(el.type || '');
  // 지금 단계의 꼬리표: 누구 차례인지(내 차례 · AI 판단 중 · 시스템 처리 중) — 멈춤 · 보류는 그 말로
  function tipText(view, id, state, mine) {
    if (state === 'fail') return '멈춤';
    if (state === 'hold') return '보류';
    if ((mine || []).includes(id)) return '지금 · 내 차례';
    if ((view.workitems || []).some(w => w.activity_id === id && w.status === 'SUBMITTED')) return '지금 · 다음 단계로 넘기는 중';
    const def = view.definition || {}, a = (def.activities || []).find(x => x.id === id) || {};
    const ep = a.agent || ((def.roles || []).find(r => r.name === a.role) || {}).endpoint || '';
    if (ep === 'sys:agent' || /^agent:/.test(ep) || a.orchestration === 'cliagents') return '지금 · AI 판단 중';
    if (/^role:|^user:/.test(ep)) return '지금 · 담당자 차례';
    return '지금 · 시스템 처리 중';
  }
  function paint(D, view, mine) {
    const canvas = D.viewer.get('canvas'), reg = D.viewer.get('elementRegistry'), overlays = D.viewer.get('overlays');
    const m = marksOf(view);
    overlays.clear();
    reg.forEach(el => {
      if (skip(el)) return;
      MARKERS.forEach(k => canvas.removeMarker(el.id, k));
      const s = m.st[el.id];
      canvas.addMarker(el.id, s === 'done' ? 'is-done' : s === 'now' ? 'is-now' : s === 'hold' ? 'is-hold' : s === 'fail' ? 'is-fail' : 'is-todo');
      if (s === 'done' && isBox(el)) overlays.add(el.id, { position: { top: -8, right: 10 }, html: '<div class="bpmn-check"></div>' });
    });
    m.now.forEach(id => { const el = reg.get(id); if (!el || skip(el)) return; const s = m.st[id]; overlays.add(id, { position: { top: -12, left: el.width / 2 }, html: `<div class="bpmn-tip" data-state="${e(s)}"><i></i>${e(tipText(view, id, s, mine))}</div>` }); });
    D.marks = m;
    return m;
  }
  // 고른 요소(지금 단계, 끝난 건은 닿은 끝)가 캔버스의 왼쪽 40 % 자리에 오게. 그림이 캔버스보다 작으면 가운데에 둔다
  function focus(D) {
    const canvas = D.viewer.get('canvas'), reg = D.viewer.get('elementRegistry');
    const vb = canvas.viewbox(), o = vb.outer, inner = vb.inner;
    if (!o.width || !o.height || !inner.width) return;
    const m = D.marks || { now: [] };
    const target = reg.get(m.now[m.now.length - 1]) || (m.finished && (reg.get(m.lastDone) || reg.get(m.end))) || null;
    const bar = 44;                                                   // 캔버스 위 도구 줄 자리
    const z = Math.min(1, Math.max(0.72, (o.height - bar - 16) / inner.height));
    const w = o.width / z, h = o.height / z, pad = 24;
    const cx = target ? target.x + target.width / 2 : inner.x, cy = target ? target.y + target.height / 2 : inner.y + inner.height / 2;
    let x = inner.width + 2 * pad <= w ? inner.x - (w - inner.width) / 2 : Math.min(Math.max(inner.x - pad, cx - w * (m.finished ? 0.6 : 0.4)), inner.x + inner.width + pad - w);
    let y = inner.height + bar / z + pad <= h ? inner.y - (h - inner.height) / 2 - bar / z / 2 : Math.min(Math.max(inner.y - pad - (bar + 22) / z, cy - h * 0.55), inner.y + inner.height + pad - h);      // 위 도구 줄과 지금 단계의 꼬리표 자리를 비운다
    canvas.viewbox({ x, y, width: w, height: h });
  }
  // 전체를 맞춰 보이되 가장자리에 붙지 않게 조금 물린다(위 도구 줄 자리도 비운다)
  function fit(D) { const canvas = D.viewer.get('canvas'); canvas.zoom('fit-viewport', 'auto'); canvas.zoom(canvas.zoom() * 0.9); }
  async function draw(container, view, opts = {}) {
    await UI.need('bpmn');
    const src = await xmlOf(view.definition);
    const viewer = new BpmnJS(viewerOptions(container));
    await viewer.importXML(src.xml);
    const D = { viewer, src, marks: null };
    paint(D, view, opts.mine);
    if (opts.fit) fit(D); else focus(D);
    if (opts.onPick) viewer.get('eventBus').on('element.click', ev => { const el = ev.element; if (!skip(el) && isBox(el)) opts.onPick(el.id); });
    return D;
  }
  const LEGEND = '<span><i style="background:var(--cv-green)"></i>끝남</span><span><i style="background:var(--cv-now)"></i>지금</span><span><i></i>남음</span>';
  const noticeText = src => !src.laidOut ? '' : src.source === 'file' ? '배치 정보가 없어 자동으로 놓았습니다 — bpmn.io 에서 열어 배치를 고치면 그대로 보입니다'
    : '그림 원본 없이 등록된 흐름이라 단계 정의에서 자동으로 그렸습니다';

  /* 진행 길 캔버스. host 는 instances.js 가 한 건의 뼈대에 둔 칸 하나다. 같은 처리 건 · 같은 흐름 판본이면 상태 표시만 고친다 */
  function mount(host, view, opts = {}) {
    const def = view.definition || {}, pid = view.instance.proc_inst_id;
    if (!(def.activities || []).length) { host.innerHTML = UI.empty('그릴 흐름이 없습니다', '이 처리 건의 흐름 정의에 단계가 없습니다.', 'compact'); host._flow = null; return; }
    const key = `${pid}|${def.processDefinitionId}@${def.version}`;
    const sig = JSON.stringify([(view.workitems || []).map(w => [w.id, w.status, w.draft_status]), view.instance.status, view.instance.end_event, opts.mine || []]);
    let F = host._flow;
    if (F && F.key === key) {
      F.view = view; F.opts = opts;
      if (F.sig === sig || !F.D) { F.sig = sig; return; }      // 그리는 중이면 끝난 뒤 가장 새 view 로 칠한다
      const before = (F.D.marks.now || []).join('|');
      F.sig = sig; paint(F.D, view, opts.mine);
      if ((F.D.marks.now || []).join('|') !== before) focus(F.D);
      return;
    }
    if (F && F.D) F.D.viewer.destroy();
    F = host._flow = { key, sig, view, opts, D: null };
    host.innerHTML = `<div class="canvas flow-canvas"><div class="canvas-bar"><span class="cv-legend" data-flow-legend>${LEGEND}</span><span class="grow"></span>
      <span class="cv-tools" role="group" aria-label="그림 도구"><button type="button" data-flow-zoom="-1" aria-label="축소" data-tooltip="축소" data-side="bottom">${UI.icon('minus')}</button><button type="button" data-flow-zoom="1" aria-label="확대" data-tooltip="확대" data-side="bottom">${UI.icon('plus')}</button><button type="button" data-flow-now aria-label="지금 단계로" data-tooltip="지금 단계로" data-side="bottom">${UI.icon('locate-fixed')}</button><button type="button" class="wide" data-flow-all>${UI.icon('maximize-2')}전체 흐름</button></span></div>
      <div class="bpmn" data-flow-stage role="img" aria-label="진행 길"></div><p class="flow-note" data-flow-note hidden></p><div class="flow-wait" data-flow-wait>${UI.loading('', 'compact')}</div></div>`;
    const stage = host.querySelector('[data-flow-stage]'), wait = host.querySelector('[data-flow-wait]');
    draw(stage, view, { mine: opts.mine, onPick: id => host._flow && host._flow.opts.onPick && host._flow.opts.onPick(id) }).then(D => {
      if (host._flow !== F) { D.viewer.destroy(); return; }    // 그리는 사이 다른 처리 건을 골랐다
      F.D = D; wait.remove();
      const note = host.querySelector('[data-flow-note]'), text = noticeText(D.src);
      note.hidden = !text; note.textContent = text;
      if (F.view !== view || F.opts !== opts) { paint(D, F.view, F.opts.mine); focus(D); }
    }).catch(err => {
      if (host._flow !== F) return;
      console.error('[hydFlow] 진행 길을 그리지 못했습니다', key, err);
      wait.innerHTML = UI.errorBlock('흐름 그림을 그리지 못했습니다', err.message, { retry: true });
      wait.querySelector('[data-retry]')?.addEventListener('click', () => { host._flow = null; mount(host, F.view, F.opts); });
    });
    if (host._flowWired) return;
    host._flowWired = true;
    host.addEventListener('click', ev => {
      const F2 = host._flow, D = F2 && F2.D; if (!D) return;
      const canvas = D.viewer.get('canvas');
      const zb = ev.target.closest('[data-flow-zoom]');
      if (zb) { canvas.zoom(Math.min(2.5, Math.max(0.3, canvas.zoom() * (zb.dataset.flowZoom === '1' ? 1.2 : 1 / 1.2)))); return; }
      if (ev.target.closest('[data-flow-now]')) { focus(D); return; }
      if (ev.target.closest('[data-flow-all]')) openFull(F2.view, F2.opts);
    });
  }

  /* 전체 흐름: 큰 대화상자에 전체를 맞춰 연다(같은 상태 표시). 닫으면 그림을 치운다 */
  function openFull(view, opts = {}) {
    document.querySelector('dialog.flow-dialog')?.remove();
    const dlg = document.createElement('dialog');
    dlg.className = 'dialog flow-dialog';
    const title = UI.flowName((view.definition || {}).processDefinitionName || '') || '흐름';
    dlg.setAttribute('aria-label', `전체 흐름 — ${title}`);
    dlg.innerHTML = `<div><div class="canvas"><div class="canvas-bar"><span class="cv-legend">${LEGEND}</span><span class="cv-legend flow-title">${e(title)}${view.instance?.proc_inst_name ? ` · ${e(view.instance.proc_inst_name)}` : ''}</span><span class="grow"></span>
      <span class="cv-tools" role="group" aria-label="그림 도구"><button type="button" data-fd-zoom="-1" aria-label="축소">${UI.icon('minus')}</button><button type="button" data-fd-zoom="1" aria-label="확대">${UI.icon('plus')}</button><button type="button" class="wide" data-fd-fit>${UI.icon('scan')}화면에 맞춤</button><button type="button" class="wide" data-fd-close>${UI.icon('x')}닫기</button></span></div>
      <div class="bpmn" data-fd-stage role="img" aria-label="전체 흐름"></div><p class="flow-note" data-flow-note hidden></p><div class="flow-wait" data-flow-wait>${UI.loading('', 'compact')}</div></div></div>`;
    document.body.append(dlg);
    let D = null, down = false;
    dlg.addEventListener('pointerdown', ev => { down = ev.target === dlg; });
    dlg.addEventListener('click', ev => {
      if ((ev.target === dlg && down) || ev.target.closest('[data-fd-close]')) { dlg.close(); return; }
      if (!D) return;
      const canvas = D.viewer.get('canvas'), zb = ev.target.closest('[data-fd-zoom]');
      if (zb) canvas.zoom(Math.min(2.5, Math.max(0.2, canvas.zoom() * (zb.dataset.fdZoom === '1' ? 1.2 : 1 / 1.2))));
      else if (ev.target.closest('[data-fd-fit]')) fit(D);
    });
    dlg.addEventListener('close', () => { if (D) D.viewer.destroy(); dlg.remove(); });
    dlg.showModal();
    draw(dlg.querySelector('[data-fd-stage]'), view, { mine: opts.mine, fit: true }).then(d => {
      if (!dlg.isConnected) { d.viewer.destroy(); return; }
      D = d; dlg.querySelector('[data-flow-wait]').remove();
      const note = dlg.querySelector('[data-flow-note]'), text = noticeText(d.src);
      note.hidden = !text; note.textContent = text;
    }).catch(err => { console.error('[hydFlow] 전체 흐름을 그리지 못했습니다', err); const w = dlg.querySelector('[data-flow-wait]'); if (w) w.innerHTML = UI.errorBlock('흐름 그림을 그리지 못했습니다', err.message); });
    dlg.querySelector('[data-fd-close]').focus();
    return dlg;
  }

  window.hydFlow = { pathModel, marksOf, defToXml, xmlOf, mount, openFull };
})();
