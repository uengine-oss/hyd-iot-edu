/* 흐름 그림 — bpmn-js NavigatedViewer(보기 전용)로 그린다(디자인 기준 6-2). 포털은 그리지 않는다: 그림의 모양과 배치는 bpmn.io 에서 그린 그대로이고,
   여기서는 색(어두운 캔버스)과 처리 건의 상태 표시(끝남 · 지금 · 남음 · 멈춤)만 얹는다. loaded after instanceSteps.js(단계 상태 규칙 hydSteps).

   그림의 원본(xmlOf):
     ① 포털로 가져와 등록한 흐름(정의에 bpmnImport 가 있다) — GET /api/flows/{id}/versions/{v}/bpmn 이 준 .bpmn 원본.
        배치 정보(BPMNDiagram)가 없으면 hydBpmnLayout.ensureLayout 으로 자동 배치하고 그 사실을 그림 위에 알린다.
     ② 그림 원본 없이 정의(JSON)로만 등록된 흐름 — 정의의 단계 · 갈림 · 선으로 BPMN XML 을 만들고(defToXml) 자동 배치한다. 그 사실도 그림 위에 알린다.
   처리 건 화면(instances.js)이 쓰는 것:
     pathModel(def, workitems, instance)   지나온 단계와 남은 길(「몇 단계 가운데 몇 번째」 · 「남은 단계」 줄)
     show(host, { key, title, load })       흐름 화면(flows.js)의 흐름 그림: 상태 표시 없이 그림만, 축소 · 확대 · 화면에 맞춤 · 전체 흐름 보기
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
    // 남은 길: 지금 단계(없으면 마지막으로 지나온 단계)에서 **정해진 데까지만** 잇는다. 길이 갈리는 곳(나가는 선이 둘 이상인 갈림)을 만나면 거기서 멈추고,
    // 그 뒤는 가지마다 따로 적는다(fork) — 어느 가지로 갈지는 아직 나지 않은 결과(승인 · 반려, 효과 확인의 판정)가 정한다. 한 길을 골라 끝까지 지어 적지 않는다
    let end = null, fork = null;
    const gwName = new Map((def.gateways || []).map(g => [g.id, g.name || '']));
    const outsOf = id => (next.get(id) || []).filter(q => !(events.get(q.target) || {}).attachedTo);
    // 한 점에서 앞으로: 단계 이름을 모으다가 갈림(more) · 끝 이벤트(end) · 이미 지나온 곳에서 멈춘다
    const walk = (from, seen) => {
      const steps = []; let cur = from, more = null, stop = null;
      for (let guard = 0; cur && guard < 200; guard++) {
        if (seen.has(cur)) break;
        seen.add(cur);
        if (acts.has(cur)) { const a = acts.get(cur); steps.push({ id: cur, name: a.name, state: 'todo', who: who(a), role: a.role || '' }); }
        else if ((events.get(cur) || {}).type === 'endEvent') { stop = events.get(cur); break; }
        const outs = outsOf(cur);
        if (outs.length > 1) { more = { id: cur, name: gwName.get(cur) || '', outs }; break; }
        cur = outs[0] && outs[0].target;
      }
      return { steps, more, end: stop };
    };
    if (finished) end = events.get(instance.end_event) || null;
    else {
      const live = nodes.filter(n => n.state === 'now' || n.state === 'hold');
      const at = (live[live.length - 1] || nodes[nodes.length - 1] || {}).id || ((def.events || []).find(x => x.type === 'startEvent') || {}).id;
      const seen = new Set(nodes.map(n => n.id));
      seen.delete(at);
      const ahead = at ? walk(at, seen) : { steps: [], more: null, end: null };
      ahead.steps.filter(x => x.id !== at).forEach(x => nodes.push(x));
      end = ahead.end;
      if (ahead.more) fork = { name: ahead.more.name, branches: ahead.more.outs.map(q => {
        const b = walk(q.target, new Set(seen));
        return { label: q.name || (q.condition ? '' : '그 밖'), steps: b.steps.map(x => x.name), more: b.more ? b.more.name : null, end: b.end ? b.end.name || '' : null };
      }) };
    }
    const start = (def.events || []).find(x => x.type === 'startEvent') || null;
    return { nodes, start, end, fork, finished, started: latest.size > 0 };
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
  /* 정의의 id ↔ 그림(XML)의 id — 대응은 이 한 곳이다.
     정의로만 등록된 흐름의 id 는 task:draft · seq:0 처럼 쌍점을 품는다. XML 의 id 에는 쌍점을 쓸 수 없어(접두사가 붙은 이름으로 읽힌다) 그대로 쓰면
     bpmn-js 가 선의 양 끝을 찾지 못해 선이 하나도 그려지지 않고, 자동 배치 부품도 멈춘다. XML 에 쓸 수 없는 글자를 _x<코드>_ 로 바꾼다.
     XML 에 그대로 쓸 수 있는 id(가져온 그림의 id)는 바뀌지 않는다. 그림을 만드는 쪽(defToXml)과 상태 표시 · 누름을 잇는 쪽(paint · focus · onPick)이 모두 이 둘을 쓴다 */
  const DEF_ID = new Map();
  function xid(id) {
    const s = String(id ?? '');
    if (/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(s)) return s;
    const x = (/^[A-Za-z_]/.test(s) ? '' : '_') + s.replace(/[^A-Za-z0-9_.-]/g, c => `_x${c.codePointAt(0).toString(16)}_`);
    DEF_ID.set(x, s);
    return x;
  }
  const defIdOf = x => (DEF_ID.has(x) ? DEF_ID.get(x) : x);
  // 정의(JSON) → BPMN XML(배치 정보 없음). 이름은 화면 이름 사전(UI.flowName)을 거친다. 경계 이벤트는 붙은 단계와 멈춤 여부를 그대로 싣는다
  function defToXml(def) {
    const pid = 'Process_' + String(def.processDefinitionId || 'flow').replace(/[^A-Za-z0-9_]/g, '_');
    const name = n => n ? ` name="${xa(UI.flowName(n))}"` : '';
    const xa_id = id => xa(xid(id));
    const TASK = { userTask: 'userTask', serviceTask: 'serviceTask', scriptTask: 'scriptTask', manualTask: 'manualTask', task: 'task' };
    const evDef = x => x.eventDefinition === 'timer' ? '<bpmn:timerEventDefinition/>' : x.eventDefinition === 'message' ? '<bpmn:messageEventDefinition/>' : '';
    const parts = [];
    (def.events || []).forEach(x => {
      if (x.type === 'boundaryEvent' || x.attachedTo) parts.push(`<bpmn:boundaryEvent id="${xa_id(x.id)}"${name(x.name)} attachedToRef="${xa_id(x.attachedTo)}"${x.cancelActivity === false ? ' cancelActivity="false"' : ''}>${evDef(x)}</bpmn:boundaryEvent>`);
      else if (x.type === 'endEvent') parts.push(`<bpmn:endEvent id="${xa_id(x.id)}"${name(x.name)}/>`);
      else if (x.type === 'startEvent') parts.push(`<bpmn:startEvent id="${xa_id(x.id)}"${name(x.name)}>${evDef(x)}</bpmn:startEvent>`);
      else parts.push(`<bpmn:intermediateCatchEvent id="${xa_id(x.id)}"${name(x.name)}>${evDef(x)}</bpmn:intermediateCatchEvent>`);
    });
    (def.activities || []).forEach(a => { const t = TASK[a.type] || 'task'; parts.push(`<bpmn:${t} id="${xa_id(a.id)}"${name(a.name)}/>`); });
    (def.gateways || []).forEach(g => { const t = /^(exclusive|parallel|inclusive|eventBased)Gateway$/.test(g.type || '') ? g.type : 'exclusiveGateway'; parts.push(`<bpmn:${t} id="${xa_id(g.id)}"${name(g.name)}/>`); });
    const ids = new Set([...(def.events || []), ...(def.activities || []), ...(def.gateways || [])].map(x => x.id));
    (def.sequences || []).filter(q => ids.has(q.source) && ids.has(q.target)).forEach((q, i) =>
      parts.push(`<bpmn:sequenceFlow id="${xa_id(q.id || `Flow_${i}`)}"${q.name ? ` name="${xa(UI.flowSeq(q.name) || q.name)}"` : ''} sourceRef="${xa_id(q.source)}" targetRef="${xa_id(q.target)}"/>`));
    return `<?xml version="1.0" encoding="UTF-8"?><bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_${pid}" targetNamespace="http://bpmn.io/schema/bpmn"><bpmn:process id="${pid}"${name(def.processDefinitionName)} isExecutable="false">${parts.join('')}</bpmn:process></bpmn:definitions>`;
  }
  // 그림 원문 하나({ xml, source, note? }) → 배치 정보가 없으면 자동으로 놓은 것({ …, laidOut: true }). 이미 놓인 것은 그대로 돌려준다
  async function laidOutSrc(src) {
    if (/<(\w+:)?BPMNDiagram[\s>]/.test(src.xml)) return { laidOut: false, ...src };
    await UI.need('bpmn-layout');
    const laid = await hydBpmnLayout.ensureLayout(src.xml);
    return { ...src, xml: laid.xml, laidOut: laid.laidOut };
  }
  // 흐름 판본마다 한 번만 읽고 배치한다(같은 Promise). 실패하면 지워 다음에 다시 읽는다
  const XML = new Map();
  function xmlOf(def) {
    const key = `${def.processDefinitionId}@${def.version}`;
    if (XML.has(key)) return XML.get(key);
    const job = (async () => {
      // 모든 흐름에서 서버에 그림 원본을 묻는다(가져온 흐름의 .bpmn, 기본 제공 흐름의 사람이 배치한 그림). 200 이면 그 그림을 쓰고, 그림이 없으면(204 · 404) 정의에서 만들어 자동으로 놓는다.
      // 그 밖의 상태는 오류다(조용히 자동 배치로 떨어지지 않는다). 서버는 그림의 id 를 xid 규칙(task:draft → task_x3a_draft)으로 바꿔 내준다 — 받은 그림을 쓸 때는
      // 정의의 모든 id 에 xid 를 불러 정의 id ↔ 그림 id 대응(DEF_ID)을 채운다(정의에서 만들 때는 defToXml 이 같은 일을 한다). 상태 표시 · 누름(defIdOf)이 이 대응을 쓴다
      let xml, source = 'definition';
      const r = await fetch(`${API.process}/api/flows/${encodeURIComponent(def.processDefinitionId)}/versions/${encodeURIComponent(def.version)}/bpmn`);
      if (r.status === 200) {
        xml = await r.text(); source = 'file';
        if (!/^\s*</.test(xml)) throw new Error('흐름 그림 원본이 BPMN 이 아닙니다(서버가 다른 것을 돌려주었습니다)');
        ['events', 'activities', 'gateways', 'sequences'].forEach(k => (def[k] || []).forEach(x => { if (x && x.id != null) xid(x.id); }));
      }
      else if (r.status !== 204 && r.status !== 404) throw new Error(`흐름 그림 원본을 읽지 못했습니다(${r.status})`);
      if (!xml) xml = defToXml(def);
      return laidOutSrc({ xml, source });
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
    const def = view.definition || {}, a = (def.activities || []).find(x => x.id === id) || {};
    const ep = a.agent || ((def.roles || []).find(r => r.name === a.role) || {}).endpoint || '';
    if (ep === 'sys:agent' || /^agent:/.test(ep) || a.orchestration === 'cliagents') return '지금 · AI 판단 중';
    if (/^role:|^user:/.test(ep)) return (view.workitems || []).some(w => w.activity_id === id && w.status === 'SUBMITTED') ? '지금 · 다음 단계로 넘기는 중' : '지금 · 담당자 차례';
    return '지금 · 시스템 처리 중';
  }
  function paint(D, view, mine) {
    const canvas = D.viewer.get('canvas'), reg = D.viewer.get('elementRegistry'), overlays = D.viewer.get('overlays');
    const m = marksOf(view);
    overlays.clear();
    reg.forEach(el => {
      if (skip(el)) return;
      MARKERS.forEach(k => canvas.removeMarker(el.id, k));
      const s = m.st[defIdOf(el.id)];
      canvas.addMarker(el.id, s === 'done' ? 'is-done' : s === 'now' ? 'is-now' : s === 'hold' ? 'is-hold' : s === 'fail' ? 'is-fail' : 'is-todo');
      if (s === 'done' && isBox(el)) overlays.add(el.id, { position: { top: -8, right: 10 }, html: '<div class="bpmn-check"></div>' });
    });
    // 지금 단계 꼬리표는 상자 위 가운데에 둔다. 그 자리에 선 이름(「전달」 · 「예」)이 놓여 있으면 가리지 않게 상자 아래로 내린다
    const labels = reg.filter(x => x.type === 'label' && x.labelTarget && x.labelTarget.waypoints);
    m.now.forEach(id => { const el = reg.get(xid(id)); if (!el || skip(el)) return; const s = m.st[id];
      const text = tipText(view, id, s, mine), half = Math.max(40, text.length * 7 + 20) / 2, cx = el.x + el.width / 2;      // 꼬리표가 차지할 자리(글자 수로 어림한 폭, 높이 24 + 꼬리 12)
      const hit = labels.some(l => l.x < cx + half && l.x + l.width > cx - half && l.y < el.y && l.y + l.height > el.y - 40);
      overlays.add(el.id, { position: hit ? { bottom: -12, left: el.width / 2 } : { top: -12, left: el.width / 2 }, html: `<div class="bpmn-tip" data-state="${e(s)}"${hit ? ' data-side="below"' : ''}><i></i>${e(text)}</div>` }); });
    D.marks = m;
    return m;
  }
  // 고른 요소(지금 단계, 끝난 건은 닿은 끝)가 캔버스의 왼쪽 40 % 자리에 오게. 그림이 캔버스보다 작으면 가운데에 둔다
  // zmin: 이 배율 아래로는 줄이지 않는다 — 상자 글자(13px)가 읽히는 크기(약 12px)를 지킨다. 넘치는 쪽은 끌어서 본다
  function focus(D, zmin = 0.92) {
    const canvas = D.viewer.get('canvas'), reg = D.viewer.get('elementRegistry');
    const vb = canvas.viewbox(), o = vb.outer, inner = vb.inner;
    if (!o.width || !o.height || !inner.width) return;
    const m = D.marks || { now: [] };
    const at = id => (id ? reg.get(xid(id)) : null);
    const target = at(m.now[m.now.length - 1]) || (m.finished && (at(m.lastDone) || at(m.end))) || null;
    const bar = 44;                                                   // 캔버스 위 도구 줄 자리
    const z = Math.min(1, Math.max(zmin, (o.height - bar - 16) / inner.height));
    const w = o.width / z, h = o.height / z, pad = 24;
    const cx = target ? target.x + target.width / 2 : inner.x, cy = target ? target.y + target.height / 2 : inner.y + inner.height / 2;
    let x = inner.width + 2 * pad <= w ? inner.x - (w - inner.width) / 2 : Math.min(Math.max(inner.x - pad, cx - w * (m.finished ? 0.6 : 0.4)), inner.x + inner.width + pad - w);
    let y = inner.height + bar / z + pad <= h ? inner.y - (h - inner.height) / 2 - bar / z / 2 : Math.min(Math.max(inner.y - pad - (bar + 22) / z, cy - h * 0.55), inner.y + inner.height + pad - h);      // 위 도구 줄과 지금 단계의 꼬리표 자리를 비운다
    canvas.viewbox({ x, y, width: w, height: h });
  }
  // 전체를 맞춰 보이되 가장자리에 붙지 않게 조금 물린다(위 도구 줄 자리도 비운다)
  function fit(D) { const canvas = D.viewer.get('canvas'); canvas.zoom('fit-viewport', 'auto'); canvas.zoom(canvas.zoom() * 0.9); }
  // 흐름 화면의 그림: 전체가 글자를 읽을 만한 크기로 들어가면 전체를 맞추고, 너무 길어 작아지면 시작 쪽을 읽을 만한 크기로 연다(나머지는 끌어서 · 전체 흐름 보기로)
  function fitReadable(D) {
    fit(D);
    const canvas = D.viewer.get('canvas'), vb = canvas.viewbox(), o = vb.outer, inner = vb.inner;
    D.partial = false;
    if (canvas.zoom() >= 0.8 || !o.width || !inner.width) return;      // 0.8 아래로 줄면 상자 글자(13px)가 10px 밑으로 내려가 읽히지 않는다
    D.partial = true;                                                  // 시작 쪽만 보인다 — 그림 위 알림이 그 사실과 나머지를 보는 길을 말한다
    const z = Math.min(1, Math.max(0.8, (o.height - 60) / inner.height)), w = o.width / z, h = o.height / z;
    // 위 도구 막대(44px)가 그림의 상자를 가리지 않게: 그림이 판보다 높으면 맨 윗줄을 막대 아래에서 시작하고, 낮으면 가운데에 두되 막대 자리는 비운다
    const top = inner.y - 56 / z, mid = inner.y + inner.height / 2 - h / 2 - 12 / z;
    canvas.viewbox({ x: inner.x - 24, y: Math.min(mid, top), width: w, height: h });
  }
  async function draw(container, view, opts = {}) {
    await UI.need('bpmn');
    // opts.src: 그림 원문을 주는 함수(흐름 화면 — 가져온 그림 · 등록 전 초안). 없으면 처리 건의 흐름 판본에서 읽는다
    const src = opts.src ? await laidOutSrc(await opts.src()) : await xmlOf(view.definition);
    const viewer = new BpmnJS(viewerOptions(container));
    try { await viewer.importXML(src.xml); } catch (err) { viewer.destroy(); throw new Error('BPMN 그림을 열지 못했습니다 — ' + (err.message || err)); }
    const D = { viewer, src, marks: null };
    if (!opts.plain) paint(D, view, opts.mine);      // plain: 상태 표시 없이 그림만(흐름 화면)
    if (opts.fit) openAt(D, opts.plain); else if (opts.plain) fitReadable(D); else focus(D);
    if (opts.onPick) viewer.get('eventBus').on('element.click', ev => { const el = ev.element; if (!skip(el) && isBox(el)) opts.onPick(defIdOf(el.id)); });
    return D;
  }
  const LEGEND = '<span><i style="background:var(--cv-green)"></i>끝남</span><span><i style="background:var(--cv-now)"></i>지금</span><span><i></i>남음</span>';
  // 자동 배치 알림은 학생이 가져온 흐름에만, 흐름 화면에서만 띄운다(mine) — 기본 제공 흐름과 처리 건 화면에서는 학생이 할 일이 없는 말이라 띄우지 않는다
  const noticeText = (src, mine) => !mine ? '' : src.note || (!src.laidOut ? '' : src.source === 'file' ? '배치 정보가 없어 자동으로 놓았습니다 — bpmn.io에서 열어 배치를 고치면 그대로 보입니다'
    : '그림 원본 없이 등록된 흐름이라 단계 정의에서 자동으로 그렸습니다');
  const zoomBy = (D, dir) => { const canvas = D.viewer.get('canvas'); canvas.zoom(Math.min(2.5, Math.max(0.2, canvas.zoom() * (dir > 0 ? 1.2 : 1 / 1.2)))); };
  // 캔버스 도구의 누름(진행 길 · 흐름 그림이 함께 쓴다): 축소 · 확대 · 지금 단계로 · 화면에 맞춤 · 전체 흐름
  function wireHost(host) {
    if (host._flowWired) return;
    host._flowWired = true;
    host.addEventListener('click', ev => {
      const F = host._flow, D = F && F.D; if (!D) return;
      const zb = ev.target.closest('[data-flow-zoom]');
      if (zb) zoomBy(D, zb.dataset.flowZoom === '1' ? 1 : -1);
      else if (ev.target.closest('[data-flow-now]')) focus(D);
      else if (ev.target.closest('[data-flow-fit]')) fit(D);
      else if (ev.target.closest('[data-flow-all]')) openFull(F.view, F.plain ? { plain: true, title: F.plain.title, mine: F.plain.mine, src: () => D.src } : F.opts);
    });
  }
  const zoomTools = `<button type="button" data-flow-zoom="-1" aria-label="축소" data-tooltip="축소" data-side="bottom">${UI.icon('minus')}</button><button type="button" data-flow-zoom="1" aria-label="확대" data-tooltip="확대" data-side="bottom">${UI.icon('plus')}</button>`;

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
      <span class="cv-tools" role="group" aria-label="그림 도구">${zoomTools}<button type="button" data-flow-now aria-label="지금 단계로" data-tooltip="지금 단계로" data-side="bottom">${UI.icon('locate-fixed')}</button><button type="button" class="wide" data-flow-all>${UI.icon('maximize-2')}전체 흐름</button></span></div>
      <div class="bpmn" data-flow-stage role="img" aria-label="진행 길"></div><div class="flow-wait" data-flow-wait>${UI.loading('', 'compact')}</div></div>`;
    const stage = host.querySelector('[data-flow-stage]'), wait = host.querySelector('[data-flow-wait]');
    draw(stage, view, { mine: opts.mine, onPick: id => host._flow && host._flow.opts.onPick && host._flow.opts.onPick(id) }).then(D => {
      if (host._flow !== F) { D.viewer.destroy(); return; }    // 그리는 사이 다른 처리 건을 골랐다
      F.D = D; wait.remove();
      if (F.view !== view || F.opts !== opts) { paint(D, F.view, F.opts.mine); focus(D); }
    }).catch(err => {
      if (host._flow !== F) return;
      console.error('[hydFlow] 진행 길을 그리지 못했습니다', key, err);
      wait.innerHTML = UI.errorBlock('흐름 그림을 그리지 못했습니다', err.message, { retry: true });
      wait.querySelector('[data-retry]')?.addEventListener('click', () => { host._flow = null; mount(host, F.view, F.opts); });
    });
    wireHost(host);
  }

  /* 흐름 그림 한 장(상태 표시 없이) — 흐름 화면이 쓴다. o = { key, title, cap, mine, load() → { xml, source?, note? } }.
     같은 key 로 다시 부르면 다시 그리지 않는다(끌어 옮긴 자리 · 배율이 남는다). 캔버스 위에는 도구 막대 하나만 둔다 — 어느 그림인지(cap: 판본 · 초안)와
     알림(내가 가져온 흐름을 자동으로 놓았다는 것 · 긴 흐름의 시작 쪽만 열었다는 것)은 캔버스 바깥의 한 줄이다 */
  function show(host, o) {
    let F = host._flow;
    if (F && F.key === o.key) return;
    if (F && F.D) F.D.viewer.destroy();
    F = host._flow = { key: o.key, plain: o, view: null, D: null };
    host.innerHTML = `<div class="canvas flow-canvas"><div class="canvas-bar"><span class="grow"></span>
      <span class="cv-tools" role="group" aria-label="그림 도구">${zoomTools}<button type="button" data-flow-fit aria-label="화면에 맞춤" data-tooltip="화면에 맞춤" data-side="bottom">${UI.icon('scan')}</button><button type="button" class="wide" data-flow-all>${UI.icon('maximize-2')}전체 흐름</button></span></div>
      <div class="bpmn" data-flow-stage role="img" aria-label="${e(o.title || '흐름 그림')}"></div><div class="flow-wait" data-flow-wait>${UI.loading('', 'compact')}</div></div>
      <p class="flow-cap muted"><span data-flow-cap>${e(o.cap || '')}</span><span data-flow-note hidden></span></p>`;
    const wait = host.querySelector('[data-flow-wait]');
    draw(host.querySelector('[data-flow-stage]'), null, { plain: true, src: o.load }).then(D => {
      if (host._flow !== F) { D.viewer.destroy(); return; }
      F.D = D; wait.remove();
      // 그림 위 알림: 어떻게 놓은 그림인지 + (길어서 시작 쪽만 열었으면) 나머지를 보는 길
      const note = host.querySelector('[data-flow-note]'), text = [noticeText(D.src, o.mine), D.partial ? '긴 흐름이라 시작 쪽을 읽을 크기로 열었습니다. 끌어서 옮기거나 [전체 흐름]으로 한 번에 봅니다' : ''].filter(Boolean).join(' · ');
      note.hidden = !text; note.textContent = text;
    }).catch(err => {
      if (host._flow !== F) return;
      console.error('[hydFlow] 흐름 그림을 그리지 못했습니다', o.key, err);
      wait.innerHTML = UI.errorBlock('흐름 그림을 그리지 못했습니다', err.message, { retry: true });
      wait.querySelector('[data-retry]')?.addEventListener('click', () => { host._flow = null; show(host, o); });
    });
    wireHost(host);
  }

  /* 전체 흐름: 큰 대화상자. 전체가 글자를 읽을 만한 크기로 들어가면 전체를 맞추고, 작아지면 읽을 만한 크기로 지금 단계 둘레(상태 표시가 없는 그림은 시작 쪽)를 연다 —
     넘치는 쪽은 끌어서 보고, [화면에 맞춤]을 누르면 전체가 한 번에 보인다. 닫으면 그림을 치운다 */
  const READABLE = 0.85;
  // 상태 표시가 없는 그림(흐름 화면의 [전체 흐름 보기])은 이름대로 늘 전체를 맞춰 연다 — 글자가 작아지면 그림 위 알림이 키우는 길을 말한다(D.small)
  function openAt(D, plain) {
    fit(D);
    D.small = !!plain && D.viewer.get('canvas').zoom() < 0.7;
    if (plain || D.viewer.get('canvas').zoom() >= READABLE) return;
    focus(D, READABLE);
  }
  function openFull(view, opts = {}) {
    document.querySelector('dialog.flow-dialog')?.remove();
    const dlg = document.createElement('dialog');
    dlg.className = 'dialog flow-dialog';
    const title = opts.title || UI.flowName(((view || {}).definition || {}).processDefinitionName || '') || '흐름';
    dlg.setAttribute('aria-label', `전체 흐름 — ${title}`);
    dlg.innerHTML = `<div><div class="canvas"><div class="canvas-bar">${opts.plain ? '' : `<span class="cv-legend">${LEGEND}</span>`}<span class="cv-legend flow-title">${e(view && view.instance?.proc_inst_name || title)}</span><span class="grow"></span>
      <span class="cv-tools" role="group" aria-label="그림 도구"><button type="button" data-fd-zoom="-1" aria-label="축소">${UI.icon('minus')}</button><button type="button" data-fd-zoom="1" aria-label="확대">${UI.icon('plus')}</button><button type="button" class="wide" data-fd-fit>${UI.icon('scan')}화면에 맞춤</button><button type="button" class="wide" data-fd-close>${UI.icon('x')}닫기</button></span></div>
      <div class="bpmn" data-fd-stage role="img" aria-label="전체 흐름"></div><p class="flow-note" data-flow-note hidden></p><div class="flow-wait" data-flow-wait>${UI.loading('', 'compact')}</div></div></div>`;
    document.body.append(dlg);
    let D = null, down = false;
    dlg.addEventListener('pointerdown', ev => { down = ev.target === dlg; });
    dlg.addEventListener('click', ev => {
      if ((ev.target === dlg && down) || ev.target.closest('[data-fd-close]')) { dlg.close(); return; }
      if (!D) return;
      const zb = ev.target.closest('[data-fd-zoom]');
      if (zb) zoomBy(D, zb.dataset.fdZoom === '1' ? 1 : -1);
      else if (ev.target.closest('[data-fd-fit]')) fit(D);
    });
    dlg.addEventListener('close', () => { if (D) D.viewer.destroy(); dlg.remove(); });
    dlg.showModal();
    draw(dlg.querySelector('[data-fd-stage]'), view, { mine: opts.mine, fit: true, plain: opts.plain, src: opts.src }).then(d => {
      if (!dlg.isConnected) { d.viewer.destroy(); return; }
      D = d; dlg.querySelector('[data-flow-wait]').remove();
      const note = dlg.querySelector('[data-flow-note]'), text = [opts.plain ? noticeText(d.src, opts.mine) : '', d.small ? '전체를 한 화면에 맞췄습니다 — 글자가 작으면 [+]로 키우고 끌어서 봅니다' : ''].filter(Boolean).join(' · ');
      note.hidden = !text; note.textContent = text;
    }).catch(err => { console.error('[hydFlow] 전체 흐름을 그리지 못했습니다', err); const w = dlg.querySelector('[data-flow-wait]'); if (w) w.innerHTML = UI.errorBlock('흐름 그림을 그리지 못했습니다', err.message); });
    dlg.querySelector('[data-fd-close]').focus();
    return dlg;
  }

  window.hydFlow = { pathModel, marksOf, defToXml, xmlOf, xid, defIdOf, mount, show, openFull };
})();
