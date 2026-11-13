/* A122 — business-process flow drawn straight from the process definition JSON (workspace/개발/문서/UIUX_PLAN.md §4).
   Lanes are the three doers only: 에이전트 (sys:agent) · 담당자 (role:*) · 시스템 (sys:scada · sys:process · sys:cmms · start/end).
   Columns are "longest distance from the start event" (same rule as instanceSteps.js flowGraph). A boundary timer is a small
   circle on its task's border. Node colour = state of the newest work item for that activity (done · current · skipped · fail).
   Nothing here changes the definition or calls the engine.
   A141 — the same diagram in two orientations. Layout is computed on an abstract (primary = depth, secondary = lane) grid and
   mapped to the screen: horizontal (1440, unchanged look) or vertical (narrow widths such as 1024: lanes become columns,
   depth runs downward, so the diagram fits the width and never scrolls sideways).
   2026-11-14 — 보기는 둘이다(디자인 기준 6-2): 전체 흐름(render — 레인 · 모든 분기)과 진행 길(renderPath — 처리 건 한 건이 지나온 길과 남은 길만 한 줄).
   그림은 줄여서 끼워 맞추지 않는다. 제 크기로 놓고 넘치면 옆으로 밀며, [전체 흐름 보기]는 큰 판(openFull)을 연다. */
(function () {
  const LANES = [['agent', 'flow.lane.agent'], ['human', 'flow.lane.human'], ['system', 'flow.lane.system']];
  const TW = 132, TH = 48, GW = 18, EV = 12;
  // 상자 안 글자 폭(12px 글꼴, 한글 1칸 · 영문 · 숫자 · 기호 0.6칸)으로 나눈다 — 상자 안쪽 116px ≈ 9칸(디자인 기준 6-2)
  const MAXW = 9, width = t => [...t].reduce((w, c) => w + (/[ㄱ-힣]/.test(c) ? 1 : 0.6), 0);
  function fitLines(name, max) {
    if (width(name) <= MAXW) return [name];
    const parts = name.split(' · ');                     // 「원인 진단 · 냉각 조치 제안」은 가운뎃점에서 먼저 나눈다
    if (max > 1 && parts.length === 2 && parts.every(x => width(x) <= MAXW)) return parts;
    const words = name.split(' ').filter(w => w !== '·'), lines = [];
    let cur = '';
    for (const w of words) { const next = cur ? cur + ' ' + w : w; if (cur && width(next) > MAXW) { lines.push(cur); cur = w; } else cur = next; }
    if (cur) lines.push(cur);
    const out = lines.slice(0, max);
    if (lines.length > max || width(out[out.length - 1]) > MAXW) {
      let last = lines.slice(max - 1).join(' ');
      while (width(last + '…') > MAXW && last.length > 1) last = last.slice(0, -1);
      out[max - 1] = last.trimEnd() + '…';
    }
    return out;
  }
  // PITCH: distance between depths on the primary axis · ROW: distance between stacked nodes on the secondary axis · HEAD: lane header size on the primary axis
  const METRICS = {
    horizontal: { PITCH: 168, HEAD: 96, TOP: 8, LANE_MIN: 96, ROW: 72, vertical: false },
    vertical: { PITCH: 76, HEAD: 30, TOP: 8, LANE_MIN: 160, ROW: TW + 14, vertical: true },
  };

  function laneOf(node, roleEndpoint) {
    if (node.kind === 'event' && (node.type === 'startEvent')) return 'system';
    const ep = node.agent || roleEndpoint || '';
    if (ep === 'sys:agent' || node.orchestration === 'cliagents') return 'agent';
    if (/^role:/.test(ep)) return 'human';
    if (/^sys:/.test(ep)) return 'system';
    return null;        // gateways and end events inherit their predecessor's lane
  }

  function build(def, M) {
    const roles = new Map((def.roles || []).map(r => [r.name, r.endpoint]));
    const nodes = new Map();
    (def.events || []).forEach(e => nodes.set(e.id, { id: e.id, kind: 'event', type: e.type, name: e.name, attachedTo: e.attachedTo, def: e }));
    (def.activities || []).forEach(a => nodes.set(a.id, { id: a.id, kind: 'task', name: a.name, role: a.role, agent: a.agent, orchestration: a.orchestration, def: a }));
    (def.gateways || []).forEach(g => nodes.set(g.id, { id: g.id, kind: 'gateway', name: g.name, def: g }));
    // boundary events sit on their task: route their outgoing flows from the task
    const hostOf = id => { const n = nodes.get(id); return n && n.kind === 'event' && n.attachedTo ? n.attachedTo : id; };
    const seqs = (def.sequences || []).filter(s => nodes.has(s.source) && nodes.has(s.target));
    const next = new Map(), prev = new Map();
    seqs.forEach(s => {
      const from = hostOf(s.source);
      if (!next.has(from)) next.set(from, []); next.get(from).push(s.target);
      if (!prev.has(s.target)) prev.set(s.target, []); prev.get(s.target).push(from);
    });
    // longest path from the start (DFS post-order, back edges ignored)
    const start = (def.events || []).find(e => e.type === 'startEvent');
    const depth = new Map(); const back = new Set();
    if (start) {
      const visiting = new Set(), visited = new Set(), post = [];
      const visit = id => { visiting.add(id); (next.get(id) || []).forEach(t => { if (visiting.has(t)) back.add(id + '>' + t); else if (!visited.has(t)) visit(t); }); visiting.delete(id); visited.add(id); post.push(id); };
      visit(start.id); depth.set(start.id, 0);
      post.reverse().forEach(from => { const d = depth.get(from); if (d === undefined) return; (next.get(from) || []).forEach(t => { if (back.has(from + '>' + t)) return; if ((depth.get(t) ?? -1) < d + 1) depth.set(t, d + 1); }); });
    }
    // lanes: explicit for tasks and the start; inherited from the predecessor for gateways and end events
    const lane = new Map();
    const resolve = id => {
      if (lane.has(id)) return lane.get(id);
      const n = nodes.get(id); let l = laneOf(n, roles.get(n.role));
      if (!l) { const p = (prev.get(id) || [])[0]; l = p ? resolve(p) : 'system'; }
      lane.set(id, l); return l;
    };
    const placed = [...nodes.values()].filter(n => !(n.kind === 'event' && n.attachedTo));
    placed.forEach(n => resolve(n.id));
    // rows inside a lane: nodes sharing (lane, depth) stack along the secondary axis
    const cols = new Map();
    placed.forEach(n => { const k = lane.get(n.id) + ':' + (depth.get(n.id) ?? 0); if (!cols.has(k)) cols.set(k, []); cols.get(k).push(n); });
    const laneRows = { agent: 1, human: 1, system: 1 };
    cols.forEach((list, k) => { const l = k.split(':')[0]; laneRows[l] = Math.max(laneRows[l], list.length); });
    const laneSize = {}, laneS0 = {}; let s = M.TOP;
    LANES.forEach(([l]) => { laneS0[l] = s; laneSize[l] = Math.max(M.LANE_MIN, laneRows[l] * M.ROW + 26); s += laneSize[l]; });
    const pos = new Map();      // abstract {p, s}
    cols.forEach((list, k) => {
      const [l, d] = k.split(':');
      list.forEach((n, i) => pos.set(n.id, { p: M.HEAD + Number(d) * M.PITCH + M.PITCH / 2, s: laneS0[l] + laneSize[l] / 2 + (i - (list.length - 1) / 2) * M.ROW }));
    });
    const maxDepth = Math.max(0, ...[...depth.values()]);
    return { nodes, seqs, hostOf, pos, lane, depth, laneSize, laneS0, secondary: s + 8, primary: M.HEAD + (maxDepth + 1) * M.PITCH + 8, start };
  }

  function states(def, g, workitems, instance) {
    const st = {}; const latest = new Map();
    (workitems || []).forEach(w => { const o = latest.get(w.activity_id); if (!o || (w.generation || 0) > (o.generation || 0) || ((w.generation || 0) === (o.generation || 0) && (w.start_date || '') >= (o.start_date || ''))) latest.set(w.activity_id, w); });
    const step = hydSteps.stepStateOf;   // 단계 상태 규칙은 instanceSteps.js 하나(먼저 실린다)
    g.nodes.forEach(n => {
      const w = latest.get(n.id);
      let s = w ? step(w.status) : 'todo';
      if (w && (w.draft_status === 'FAILED' || w.status === 'FAILED')) s = 'fail';
      st[n.id] = s;
    });
    if (latest.size && g.start) st[g.start.id] = 'done';
    const finished = instance && ['COMPLETED', 'CANCELLED'].includes(instance.status);
    g.nodes.forEach(n => {
      if (n.kind === 'event' && n.type === 'endEvent') st[n.id] = instance && instance.end_event === n.id ? 'done' : (finished ? 'skipped' : 'todo');
      if (n.kind === 'gateway') { const outs = g.seqs.filter(s => s.source === n.id).map(s => st[s.target]); st[n.id] = outs.some(x => x === 'done' || x === 'current') ? 'done' : (finished ? 'skipped' : 'todo'); }
    });
    if (finished) g.nodes.forEach(n => { if (st[n.id] === 'todo') st[n.id] = 'skipped'; });
    return st;
  }

  // caption 은 호출하는 쪽이 이미 esc 한 HTML 조각이다(hitl.js: 처리 건 이름 + 상태 칩) — 여기서 다시 esc 하지 않는다
  function render(def, { workitems = null, instance = null, caption = '', vertical = false } = {}) {
    if (!def || !(def.activities || []).length) return `<div class="flow-cap"><span>${caption}</span></div>`;
    const M = vertical ? METRICS.vertical : METRICS.horizontal;
    const g = build(def, M), st = states(def, g, workitems, instance);
    const primary = vertical ? g.primary : Math.max(g.primary, M.HEAD + 3 * M.PITCH);
    const w = vertical ? g.secondary : primary, h = vertical ? primary : g.secondary;
    // abstract → screen
    const X = (p, s) => vertical ? s : p, Y = (p, s) => vertical ? p : s;
    const mv = (p, s) => `M${X(p, s)} ${Y(p, s)}`, lp = p => (vertical ? 'V' : 'H') + p, ls = s => (vertical ? 'H' : 'V') + s;
    const halfP = n => n.kind === 'task' ? (vertical ? TH / 2 : TW / 2) : n.kind === 'gateway' ? GW : EV;
    const halfS = n => n.kind === 'task' ? (vertical ? TW / 2 : TH / 2) : n.kind === 'gateway' ? GW : EV;
    let s = `<svg viewBox="0 0 ${w} ${h}" data-flow-w="${w}" style="${vertical ? `max-width:${w}px` : `width:${w}px;min-width:0;max-width:none`}" role="img" aria-label="${esc(UI.t('proc.flow'))}"><defs><marker id="fArr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#6b7a8c"/></marker><marker id="fArrD" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#2e9e6a"/></marker></defs>`;
    LANES.forEach(([l, term], i) => {
      const s0 = g.laneS0[l], size = g.laneSize[l];
      if (vertical) s += `<rect x="${s0}" y="4" width="${size}" height="${h - 8}" class="f-lane ${i % 2 ? 'alt' : ''}"/><rect x="${s0}" y="4" width="${size}" height="${M.HEAD - 8}" class="f-lanehead"/><text x="${s0 + size / 2}" y="${4 + (M.HEAD - 8) / 2 + 4}" text-anchor="middle" class="f-lanet">${esc(UI.t(term))}</text>`;
      else s += `<rect x="4" y="${s0}" width="${w - 8}" height="${size}" class="f-lane ${i % 2 ? 'alt' : ''}"/><rect x="4" y="${s0}" width="${M.HEAD - 12}" height="${size}" class="f-lanehead"/><text x="16" y="${s0 + size / 2 + 4}" class="f-lanet">${esc(UI.t(term))}</text>`;
    });
    // boundary timer: on the task's secondary+ edge (bottom when horizontal, right when vertical), near the primary+ end
    const timerPos = id => { const n = g.nodes.get(id); const host = g.nodes.get(n.attachedTo); const a = g.pos.get(n.attachedTo); return a ? { p: a.p + halfP(host) - (vertical ? 10 : 14), s: a.s + halfS(host) } : null; };
    const label = (p, s, text) => vertical ? `<text x="${s + 12}" y="${p + 4}" class="f-flowt">${esc(text)}</text>` : `<text x="${p}" y="${s}" class="f-flowt">${esc(text)}</text>`;
    // edges
    g.seqs.forEach(sq => {
      const fromBoundary = g.hostOf(sq.source) !== sq.source;
      const A = g.nodes.get(g.hostOf(sq.source)), B = g.nodes.get(sq.target);
      const a = g.pos.get(A.id), b = g.pos.get(B.id); if (!a || !b) return;
      const da = g.depth.get(A.id) ?? 0, db = g.depth.get(B.id) ?? 0;
      const ap = a.p + halfP(A), bp = b.p - halfP(B);
      let d, lpos;
      if (fromBoundary) {                                   // from the timer, out to the lane channel, along it, over to the target
        const t = timerPos(sq.source); const chan = g.laneS0[g.lane.get(A.id)] + g.laneSize[g.lane.get(A.id)] - 10;
        d = `${mv(t.p, t.s + 7)} ${ls(chan)} ${lp(bp - M.PITCH / 2 + 24)} ${ls(b.s)} ${lp(bp)}`; lpos = [t.p + 14, chan - 5];
      } else if (db - da > 1 && a.s === b.s) {              // long skip inside one lane: route along the lane channel past the nodes in between
        const chan = g.laneS0[g.lane.get(A.id)] + g.laneSize[g.lane.get(A.id)] - 10;
        d = `${mv(ap, a.s)} ${lp(ap + 16)} ${ls(chan)} ${lp(bp - 16)} ${ls(b.s)} ${lp(bp)}`; lpos = [ap + 24, chan - 5];
      } else if (db - da > 1) {                             // long skip across lanes: move to the target lane first
        const mid = ap + 16;
        d = `${mv(ap, a.s)} ${lp(mid)} ${ls(b.s)} ${lp(bp)}`; lpos = [mid + 6, b.s - 6];
      } else if (a.s === b.s) { d = `${mv(ap, a.s)} ${lp(bp)}`; lpos = [(ap + bp) / 2, a.s - 6]; }
      else { const mid = (ap + bp) / 2; d = `${mv(ap, a.s)} ${lp(mid)} ${ls(b.s)} ${lp(bp)}`; lpos = [mid + 4, (a.s + b.s) / 2 - 6]; }
      const done = (st[A.id] === 'done' || st[A.id] === 'current') && (st[B.id] === 'done' || st[B.id] === 'current');
      s += `<path d="${d}" class="f-flow${done ? ' done' : ''}" marker-end="url(#${done ? 'fArrD' : 'fArr'})"/>`;
      const text = UI.flowSeq(sq.name);
      if (text) s += label(lpos[0], lpos[1], text);
    });
    // nodes (shapes are screen-sized; only their centres move with the orientation)
    g.nodes.forEach(n => {
      if (n.kind === 'event' && n.attachedTo) return;
      const q = g.pos.get(n.id); if (!q) return;
      const cx = X(q.p, q.s), cy = Y(q.p, q.s);
      const cls = `f-node ${st[n.id] || 'todo'}`;
      const name = UI.flowName(n.name);
      if (n.kind === 'task') {
        const roleName = g.lane.get(n.id) === 'human' ? n.role : '';
        const lines = fitLines(name, roleName ? 1 : 2), y0 = cy + (roleName ? -2 : lines.length > 1 ? -3 : 4);
        const title = lines.some(l => l.endsWith('…')) ? `<title>${esc(name)}</title>` : '';     // 줄여 쓴 이름은 마우스를 올리면 전체
        s += `<g class="${cls}" data-node="${esc(n.id)}">${title}<rect x="${cx - TW / 2}" y="${cy - TH / 2}" width="${TW}" height="${TH}" rx="10"/>`
          + lines.map((l, i) => `<text x="${cx}" y="${y0 + i * 14}" text-anchor="middle" class="f-t">${esc(l)}</text>`).join('')
          + `${roleName ? `<text x="${cx}" y="${cy + 13}" text-anchor="middle" class="f-s">${esc(roleName)}</text>` : ''}</g>`;
      } else if (n.kind === 'gateway') {
        const lab = vertical ? `<text x="${cx + GW + 6}" y="${cy + 4}" class="f-s">${esc(name)}</text>` : `<text x="${cx}" y="${cy - GW - 6}" text-anchor="middle" class="f-s">${esc(name)}</text>`;
        s += `<g class="${cls}"><path d="M${cx} ${cy - GW} L${cx + GW} ${cy} L${cx} ${cy + GW} L${cx - GW} ${cy} Z"/><text x="${cx}" y="${cy + 5}" text-anchor="middle" class="f-g">×</text>${lab}</g>`;
      } else {
        const lab = vertical ? `<text x="${cx + EV + 6}" y="${cy + 4}" class="f-s">${esc(name)}</text>` : `<text x="${cx}" y="${cy + EV + 14}" text-anchor="middle" class="f-s">${esc(name)}</text>`;
        s += `<g class="${cls} ${n.type === 'endEvent' ? 'end' : 'start'}"><circle cx="${cx}" cy="${cy}" r="${EV}"/>${lab}</g>`;
      }
    });
    // boundary timers on their task border
    g.nodes.forEach(n => {
      if (!(n.kind === 'event' && n.attachedTo)) return;
      const t = timerPos(n.id); if (!t) return;
      const tx = X(t.p, t.s), ty = Y(t.p, t.s);
      const used = st[n.id] === 'done';
      s += `<g class="f-timer ${used ? 'done' : ''}"><circle cx="${tx}" cy="${ty}" r="9"/><circle cx="${tx}" cy="${ty}" r="6.5"/><path d="M${tx} ${ty - 4} V${ty} H${tx + 3}"/><title>${esc(UI.flowName(n.name))}</title></g>`;
    });
    s += '</svg>';
    const legend = `<span class="f-legend"><span><i class="done"></i>${esc(UI.t('proc.legend.done'))}</span><span><i class="current"></i>${esc(UI.t('proc.legend.now'))}</span><span><i class="fail"></i>${esc(UI.t('proc.legend.stop'))}</span><span><i class="skipped"></i>${esc(UI.t('proc.legend.skipped'))}</span></span>`;
    // [전체 흐름 보기]: 이 그림을 큰 판(openFull)에 제 크기로 연다 — 확대 · 축소 · 맞춤 · 닫기. 세로 배치(좁은 폭)에서도 같다
    const fitButton = `<button type="button" class="btn small" data-flow-full>${esc(UI.t('btn.fit'))}</button>`;
    return `<div class="flow-cap"><span>${caption}</span><span class="row-wrap">${legend}${fitButton}</span></div><div class="flow-scroll${vertical ? ' vert' : ''}" tabindex="0" role="region" aria-label="${esc(UI.t('proc.flow'))}">${s}</div>`;
  }

  // 같은 그림을 다시 그릴 때 옆으로 민 자리를 지킨다.
  // A141: `fold` = summary html → the diagram sits inside a closed details (narrow widths: the action stays near the top); open state survives redraws
  function mount(box, html, key, { fold = '' } = {}) {
    const old = box.querySelector('.flow-scroll');
    const same = box.dataset.flowKey === key;
    const left = same && old ? old.scrollLeft : 0;
    const wasOpen = same && !!box.querySelector('details.flow-fold[open]');
    box.innerHTML = fold ? `<details class="fold flow-fold" ${wasOpen ? 'open' : ''}><summary>${fold}</summary><div class="fold-body">${html}</div></details>` : html;
    box.dataset.flowKey = key;
    const region = box.querySelector('.flow-scroll');
    if (region) region.scrollLeft = left;
  }

  /* ---------------------------------------------------------------- 진행 길 (디자인 기준 6-2 1번 · 견본 sample_instances)
     처리 건 한 건이 실제로 지나온 단계와, 지금 단계에서 끝까지 가는 기본 길만 한 줄로 놓는다. 레인 · 분기 마름모 · 가지 않은 가지는 그리지 않는다
     (그것은 전체 흐름 그림의 몫이다). 맡은 쪽은 상자의 둘째 줄에 글로 쓴다. 상태는 색만이 아니라 선 모양(실선 · 굵은 선과 빛 · 점선)과 표시 · 글자로도 가른다. */
  const PW = 132, PGAP = 28, PEV = 9, PPAD = 24, PTOP = 44;   // 상자 폭 · 상자 사이 · 이벤트 원 반지름 · 좌우 여백 · 위 도구 줄 자리
  function pathModel(def, workitems, instance) {
    const roles = new Map((def.roles || []).map(r => [r.name, r.endpoint]));
    const acts = new Map((def.activities || []).map(a => [a.id, a]));
    const events = new Map((def.events || []).map(e => [e.id, e]));
    const gateways = new Set((def.gateways || []).map(g => g.id));
    const next = new Map();
    (def.sequences || []).forEach(q => { if (!next.has(q.source)) next.set(q.source, []); next.get(q.source).push(q); });
    // 지나온 단계: 활동마다 가장 최근 작업 행 하나(다시 수행하면 마지막 회차), 시작한 차례대로. 예정(TODO)과 엔진이 시작 전에 취소한 가지는 지나온 것이 아니다
    const latest = new Map();
    (workitems || []).forEach(w => {
      if (!acts.has(w.activity_id) || w.status === 'TODO') return;
      if (w.status === 'CANCELLED' && /^cancelled:/i.test(String(w.log || '').trim())) return;
      const o = latest.get(w.activity_id);
      if (!o || (w.generation || 0) > (o.generation || 0) || ((w.generation || 0) === (o.generation || 0) && String(w.start_date || '') >= String(o.start_date || ''))) latest.set(w.activity_id, w);
    });
    const order = Object.fromEntries((def.activities || []).map((a, i) => [a.id, i]));
    const passed = [...latest.values()].sort((a, b) => String(a.start_date || '').localeCompare(String(b.start_date || '')) || order[a.activity_id] - order[b.activity_id]);
    const finished = !!instance && ['COMPLETED', 'CANCELLED'].includes(instance.status);
    const stateOf = w => w.draft_status === 'FAILED' || w.status === 'FAILED' || w.status === 'CANCELLED' ? 'fail' : hydSteps.stepStateOf(w.status) === 'current' ? (w.status === 'PENDING' ? 'hold' : 'now') : 'done';
    const who = a => { const ep = a.agent || roles.get(a.role) || ''; return ep === 'sys:agent' || a.orchestration === 'cliagents' ? 'agent' : /^role:|^user:/.test(ep) ? 'human' : 'system'; };
    const nodes = passed.map(w => ({ id: w.activity_id, wid: w.id, name: acts.get(w.activity_id).name, state: stateOf(w), who: who(acts.get(w.activity_id)), role: acts.get(w.activity_id).role || '' }));
    // 남은 길: 지금 단계(없으면 마지막으로 지나온 단계)에서 끝 이벤트까지. 갈림에서는 조건이 붙은 가지 가운데 정의에 먼저 적힌 것(일이 진행되는 가지 — 「승인」 「예」)을 따라간다.
    // 조건 없는 가지는 그 밖의 경우(반려 · 미달 · 그 밖)의 길이라 남은 길로 보이지 않는다. 실제로 그 가지를 타면 지나온 길에 그대로 나온다
    let end = null;
    if (finished) end = events.get(instance.end_event) || null;
    else {
      const live = nodes.filter(n => n.state === 'now' || n.state === 'hold');
      let cur = (live[live.length - 1] || nodes[nodes.length - 1] || {}).id || ((def.events || []).find(e => e.type === 'startEvent') || {}).id;
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
    const start = (def.events || []).find(e => e.type === 'startEvent') || null;
    return { nodes, start, end, finished, started: latest.size > 0 };
  }
  const WHO = { agent: 'AI 에이전트', system: '시스템' };
  const PSTATE = { done: '끝남', now: '지금', hold: '보류', fail: '멈춤', todo: '남음' };
  // mine: 지금 내가 처리할 단계의 활동 id 들(「담당자 · 내 차례」로 쓴다)
  function renderPath(def, { workitems = null, instance = null, mine = [] } = {}) {
    if (!def || !(def.activities || []).length) return '';
    const m = pathModel(def, workitems, instance);
    const lines = m.nodes.map(n => fitLines(UI.flowName(n.name), 2));
    const two = lines.some(l => l.length > 1), BH = two ? 62 : 48;
    const cy = PTOP + 20 + BH / 2, h = cy + BH / 2 + 34;
    const edge = (x1, x2, cls) => `<path class="cv-edge ${cls}" d="M${x1} ${cy}H${x2 - 2}" marker-end="url(#pArr${cls === 'done' ? 'D' : ''})"/>`;
    const parts = [];
    const sx = PPAD + PEV;
    let x = sx + PEV;
    let prevState = m.started || m.finished ? 'done' : 'todo';
    const startName = UI.flowName((m.start || {}).name || '시작');
    parts.push(`<circle class="cv-ev ${prevState === 'done' ? 'done' : ''}" cx="${sx}" cy="${cy}" r="${PEV}"/><text class="cv-cap" x="${PPAD}" y="${cy + BH / 2 + 20}">${esc(startName)}</text>`);
    let nowX = null;
    m.nodes.forEach((n, i) => {
      const bx = x + PGAP, cx = bx + PW / 2, top = cy - BH / 2;
      parts.push(edge(x, bx, prevState === 'done' && n.state !== 'todo' ? 'done' : 'todo'));
      const live = n.state === 'now' || n.state === 'hold';
      const whoText = n.who === 'human' ? (mine.includes(n.id) && live ? '담당자 · 내 차례' : n.role || '담당자') : WHO[n.who];
      const tail = n.state === 'fail' ? ' · 멈춤' : n.state === 'hold' ? ' · 보류' : '';
      const l = lines[i], y0 = top + (two ? (l.length > 1 ? 19 : 26) : 20);
      const halo = live ? `<rect class="cv-halo" x="${bx}" y="${top}" width="${PW}" height="${BH}" rx="10"/>` : '';
      const mark = n.state === 'done' ? `<path class="cv-tick" d="M${bx + PW - 17} ${top + 10}l3 3 5-6"/>` : n.state === 'fail' ? `<path class="cv-tick" d="M${bx + PW - 16} ${top + 7}l6 6m0-6l-6 6"/>` : '';
      parts.push(`<g class="cv-node ${n.state === 'hold' ? 'now hold' : n.state}" data-path-node="${esc(n.id)}"${n.wid ? ` data-path-step="${esc(n.wid)}" tabindex="0" role="button" aria-label="${esc(`${UI.flowName(n.name)} — ${PSTATE[n.state]}. 단계 기록에서 보기`)}"` : ''}><title>${esc(`${UI.flowName(n.name)} — ${PSTATE[n.state]}`)}</title>${halo}<rect x="${bx}" y="${top}" width="${PW}" height="${BH}" rx="10"/>${mark}`
        + l.map((t, j) => `<text class="t" x="${cx}" y="${y0 + j * 15}" text-anchor="middle">${esc(t)}</text>`).join('')
        + `<text class="who" x="${cx}" y="${cy + BH / 2 - 9}" text-anchor="middle">${esc(whoText + tail)}</text></g>`);
      if (nowX == null && (live || n.state === 'fail')) nowX = cx;
      prevState = n.state === 'done' ? 'done' : 'todo';
      x = bx + PW;
    });
    const ex = x + PGAP + PEV, w = ex + PEV + PPAD;
    const ended = m.finished;
    parts.push(edge(x, ex - PEV, ended ? 'done' : 'todo'));
    const endName = UI.flowName((ended && instance && instance.end_label) || (m.end || {}).name || '끝');
    parts.push(`<circle class="cv-ev end ${ended ? 'done' : ''}" cx="${ex}" cy="${cy}" r="${PEV}"/><text class="cv-cap" x="${w - PPAD}" y="${cy + BH / 2 + 20}" text-anchor="end">${esc(endName)}</text>`);
    const glow = nowX != null ? `<ellipse cx="${nowX}" cy="${cy}" rx="120" ry="58" fill="url(#pGlow)"/>` : '';
    const label = `진행 길: ${[startName, ...m.nodes.map(n => `${UI.flowName(n.name)}(${PSTATE[n.state]})`), endName].join(', ')}`;
    const svg = `<svg viewBox="0 0 ${w} ${h}" data-flow-w="${w}" style="width:${w}px" role="img" aria-label="${esc(label)}"><defs>
      <marker id="pArrD" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="cv-arr done" d="M0 1 9 5 0 9z"/></marker>
      <marker id="pArr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="cv-arr" d="M0 1 9 5 0 9z"/></marker>
      <radialGradient id="pGlow"><stop offset="0" class="cv-glow-0"/><stop offset="1" class="cv-glow-1"/></radialGradient></defs>${glow}${parts.join('')}</svg>`;
    const has = st => m.nodes.some(n => n.state === st);
    const legend = `<span class="cv-legend"><span class="lg-done"><i></i>끝남</span><span class="lg-now"><i></i>지금</span>${has('fail') ? '<span class="lg-fail"><i></i>멈춤</span>' : ''}<span class="lg-todo"><i></i>남음</span></span>`;
    return `<div class="canvas path-canvas" data-path data-path-now="${nowX == null ? '' : nowX}"><div class="cv-bar">${legend}<span class="cv-tools" role="group" aria-label="그림 크기"><button type="button" data-path-zoom="-1" aria-label="축소" title="축소">−</button><button type="button" data-path-zoom="1" aria-label="확대" title="확대">+</button><button type="button" data-path-fit aria-label="화면에 맞춤" aria-pressed="false" title="화면에 맞춤">⤢</button></span></div><div class="cv-scroll" tabindex="0" role="region" aria-label="진행 길">${svg}</div></div>`;
  }
  // 같은 처리 건의 진행 길을 다시 그릴 때: 배율과 옆으로 민 자리를 지킨다. 처음 그리거나 지금 단계가 바뀌면 지금 상자가 가운데 오게 민다
  function mountPath(box, html, key) {
    const same = box.dataset.flowKey === key;
    if (same && box._pathHtml === html) return;
    const old = box.querySelector('.cv-scroll'), oldNow = box.querySelector('[data-path]')?.dataset.pathNow;
    const left = old ? old.scrollLeft : 0, zoom = same ? +(box.dataset.zoomNow || 1) : 1, fit = same && box.dataset.fitNow === '1';
    box.innerHTML = html; box._pathHtml = html; box.dataset.flowKey = key; box.dataset.zoomNow = String(zoom); box.dataset.fitNow = fit ? '1' : '';
    const region = box.querySelector('.cv-scroll'), now = box.querySelector('[data-path]')?.dataset.pathNow;
    if (!region) return;
    if (!region._drag) { region._drag = true; drag(region); }
    applyPathZoom(box);
    const z = +(box.dataset.zoomShown || 1);
    if (same && old && oldNow === now) region.scrollLeft = left;
    else if (now) region.scrollLeft = Math.max(0, +now * z - region.clientWidth / 2);
    else region.scrollLeft = region.scrollWidth;                  // 끝난 건: 끝 쪽(결과)이 보이게
  }
  const ZMIN = 0.5, ZMAX = 2, FIT_MIN = 0.85;                     // 맞춤은 글자가 11px 아래로 내려가지 않는 배율에서 멈춘다(6-2 2번)
  function applyPathZoom(box) {
    const svg = box.querySelector('.cv-scroll svg'), region = box.querySelector('.cv-scroll'); if (!svg || !region) return;
    const natural = +svg.dataset.flowW, fit = box.dataset.fitNow === '1';
    const z = fit ? Math.min(1, Math.max(FIT_MIN, (region.clientWidth - 2) / natural)) : +(box.dataset.zoomNow || 1);
    svg.style.width = Math.round(natural * z) + 'px';
    box.dataset.zoomShown = String(z);
    const b = box.querySelector('[data-path-fit]'); if (b) { b.setAttribute('aria-pressed', String(fit)); b.title = fit ? '원래 크기로' : '화면에 맞춤'; b.setAttribute('aria-label', b.title); }
  }

  /* ---------------------------------------------------------------- 전체 흐름 큰 판: 확대 · 축소 · 맞춤 · 닫기
     전에는 [전체 흐름 보기]가 그림 칸의 svg 최소 폭(980px)만 풀었다. 칸이 980px 보다 넓으면 아무것도 바뀌지 않았고, 좁으면 이미 줄어든 그림이
     조금 더 줄 뿐이었다(폭 1,700px 그림이 700px 칸에서 12px 글자가 5px). 좁은 폭(세로 배치)에서는 단추 자체가 없었다.
     이제 그림을 제 크기로 큰 판에 띄우고, 판 안에서 끌어 옮기고 확대 · 축소한다. html = render(...) 가 돌려준 조각 또는 그 안의 svg. */
  function openFull(html, title = '') {
    document.querySelector('dialog.flow-dialog')?.remove();
    const holder = document.createElement('div'); holder.innerHTML = html;
    const src = holder.querySelector('svg');
    const dlg = document.createElement('dialog');
    dlg.className = 'flow-dialog';
    dlg.setAttribute('aria-label', title ? `${title} — ${UI.t('btn.fit')}` : UI.t('btn.fit'));
    const legend = holder.querySelector('.f-legend');
    dlg.innerHTML = `<header class="fd-head"><div class="fd-title"><h3>${esc(UI.t('proc.flow'))}</h3>${title ? `<p>${esc(title)}</p>` : ''}</div>
      <span class="fd-tools"><span class="fd-zoom num" data-fd-pct aria-live="polite"></span><span class="seg" role="group" aria-label="그림 크기"><button type="button" data-fd-zoom="-1" aria-label="축소">−</button><button type="button" data-fd-zoom="1" aria-label="확대">+</button><button type="button" data-fd-fit>화면에 맞춤</button><button type="button" data-fd-one>100 %</button></span><button type="button" class="btn small" data-fd-close>닫기</button></span></header>
      ${legend ? `<div class="fd-legend">${legend.outerHTML}<span class="muted">끌어서 옮기고 휠로 확대합니다</span></div>` : ''}
      <div class="fd-stage flow-scroll" tabindex="0" role="region" aria-label="${esc(UI.t('proc.flow'))}">${src ? src.outerHTML : UI.empty('그릴 흐름이 없습니다', '흐름 정의에 단계가 없습니다.')}</div>`;
    document.body.append(dlg);
    const stage = dlg.querySelector('.fd-stage'), svg = stage.querySelector('svg');
    const natural = svg ? +(svg.dataset.flowW || svg.viewBox.baseVal.width) : 0;
    let z = 1;
    const set = (nz, keep) => {
      if (!svg) return;
      const hh = () => Math.max(1, svg.getBoundingClientRect().height);
      const rx = keep ? (stage.scrollLeft + stage.clientWidth / 2) / (natural * z) : 0, ry = keep ? (stage.scrollTop + stage.clientHeight / 2) / hh() : 0;
      z = Math.min(ZMAX, Math.max(ZMIN, Math.round(nz * 100) / 100));
      svg.style.cssText = `width:${Math.round(natural * z)}px;min-width:0;max-width:none`;
      dlg.querySelector('[data-fd-pct]').textContent = `${Math.round(z * 100)} %`;
      if (keep) { stage.scrollLeft = rx * natural * z - stage.clientWidth / 2; stage.scrollTop = ry * hh() - stage.clientHeight / 2; }
    };
    const fit = () => { if (!svg) return; const vb = svg.viewBox.baseVal, pad = 26; set(Math.min((stage.clientWidth - pad) / vb.width, (stage.clientHeight - pad) / vb.height) * (vb.width / natural)); stage.scrollLeft = 0; stage.scrollTop = 0; };
    dlg.addEventListener('click', e => {
      if (e.target === dlg || e.target.closest('[data-fd-close]')) { dlg.close(); return; }
      const zb = e.target.closest('[data-fd-zoom]'); if (zb) { set(z + 0.1 * +zb.dataset.fdZoom, true); return; }
      if (e.target.closest('[data-fd-fit]')) { fit(); return; }
      if (e.target.closest('[data-fd-one]')) set(1, true);
    });
    stage.addEventListener('wheel', e => { if (!svg) return; e.preventDefault(); set(z + (e.deltaY < 0 ? 0.1 : -0.1), true); }, { passive: false });
    drag(stage);
    dlg.addEventListener('close', () => dlg.remove());
    dlg.showModal();
    set(1);
    const cur = stage.querySelector('.f-node.current');           // 지금 단계(없으면 그림의 처음)가 보이게
    if (cur) { const r = cur.getBoundingClientRect(), sr = stage.getBoundingClientRect(); stage.scrollLeft += r.left - sr.left - stage.clientWidth / 2 + r.width / 2; stage.scrollTop += r.top - sr.top - stage.clientHeight / 2 + r.height / 2; }
    dlg.querySelector('[data-fd-close]').focus();
    return dlg;
  }
  // 캔버스를 끌어서 옮긴다(단추를 누른 것은 끌기가 아니다 — 4px 넘게 움직였을 때만). 끈 직후의 click 은 data-dragged 로 가려 상자가 눌리지 않게 한다
  function drag(region) {
    let from = null;
    region.addEventListener('pointerdown', e => { if (e.button !== 0 || e.target.closest('button')) return; from = { x: e.clientX, y: e.clientY, l: region.scrollLeft, t: region.scrollTop, moved: false }; });
    region.addEventListener('pointermove', e => {
      if (!from) return;
      const dx = e.clientX - from.x, dy = e.clientY - from.y;
      if (!from.moved && Math.abs(dx) + Math.abs(dy) < 4) return;
      if (!from.moved) { from.moved = true; region.classList.add('dragging'); if (region.setPointerCapture) region.setPointerCapture(e.pointerId); }
      region.scrollLeft = from.l - dx; region.scrollTop = from.t - dy;
    });
    const stop = () => { if (from && from.moved) { region.dataset.dragged = '1'; setTimeout(() => { delete region.dataset.dragged; }, 0); } from = null; region.classList.remove('dragging'); };
    region.addEventListener('pointerup', stop); region.addEventListener('pointercancel', stop);
  }
  document.addEventListener('click', e => {
    const full = e.target.closest('[data-flow-full]');
    if (full) {                       // 흐름 그림 위의 [전체 흐름 보기]: 바로 아래 그림을 큰 판으로
      const cap = full.closest('.flow-cap'), region = cap && cap.nextElementSibling;
      if (region && region.querySelector('svg')) openFull(cap.outerHTML + region.outerHTML, full.dataset.flowTitle || '');
      return;
    }
    const zb = e.target.closest('[data-path-zoom]'), fb = e.target.closest('[data-path-fit]');
    if (!zb && !fb) return;
    const box = (zb || fb).closest('[data-path]').parentElement;
    if (zb) { const z = Math.min(ZMAX, Math.max(ZMIN, Math.round((+(box.dataset.zoomShown || box.dataset.zoomNow || 1) + 0.1 * +zb.dataset.pathZoom) * 10) / 10)); box.dataset.zoomNow = String(z); box.dataset.fitNow = ''; }
    else box.dataset.fitNow = box.dataset.fitNow === '1' ? '' : '1';
    applyPathZoom(box);
  });
  // A141: narrow viewport (≤ 1100 px, the same breakpoint as the rest of the shell) → vertical orientation. 1440 keeps the horizontal diagram.
  function narrow() { return window.innerWidth <= 1100; }

  window.hydFlow = { render, mount, narrow, renderPath, mountPath, pathModel, openFull, drag };
})();
