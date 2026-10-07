/* A122 — business-process flow drawn straight from the process definition JSON (docs/handoff/UIUX_PLAN.md §4, option B).
   Lanes are the three doers only: 에이전트 (sys:agent) · 담당자 (role:*) · 시스템 (sys:scada · sys:process · sys:cmms · start/end).
   Columns are "longest distance from the start event" (same rule as instanceSteps.js flowGraph). A boundary timer is a small
   circle on its task's border. Node colour = state of the newest work item for that activity (done · current · skipped · fail).
   Nothing here changes the definition or calls the engine.
   A141 — the same diagram in two orientations. Layout is computed on an abstract (primary = depth, secondary = lane) grid and
   mapped to the screen: horizontal (1440, unchanged look) or vertical (narrow widths such as 1024: lanes become columns,
   depth runs downward, so the diagram fits the width and never scrolls sideways). */
(function () {
  const LANES = [['agent', 'flow.lane.agent'], ['human', 'flow.lane.human'], ['system', 'flow.lane.system']];
  const TW = 120, TH = 44, GW = 18, EV = 15;
  // PITCH: distance between depths on the primary axis · ROW: distance between stacked nodes on the secondary axis · HEAD: lane header size on the primary axis
  const METRICS = {
    horizontal: { PITCH: 142, HEAD: 96, TOP: 8, LANE_MIN: 88, ROW: 62, vertical: false },
    vertical: { PITCH: 72, HEAD: 30, TOP: 8, LANE_MIN: 150, ROW: TW + 14, vertical: true },
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
    const step = window.hydSteps ? window.hydSteps.stepStateOf : s => s === 'DONE' ? 'done' : s === 'CANCELLED' ? 'skipped' : ['IN_PROGRESS', 'SUBMITTED', 'PENDING', 'NEW'].includes(s) ? 'current' : 'todo';
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

  function render(def, { workitems = null, instance = null, caption = '', vertical = false } = {}) {
    if (!def || !(def.activities || []).length) return `<div class="flow-cap"><span>${esc(caption)}</span></div>`;
    const M = vertical ? METRICS.vertical : METRICS.horizontal;
    const g = build(def, M), st = states(def, g, workitems, instance);
    const primary = vertical ? g.primary : Math.max(g.primary, M.HEAD + 3 * M.PITCH);
    const w = vertical ? g.secondary : primary, h = vertical ? primary : g.secondary;
    // abstract → screen
    const X = (p, s) => vertical ? s : p, Y = (p, s) => vertical ? p : s;
    const mv = (p, s) => `M${X(p, s)} ${Y(p, s)}`, lp = p => (vertical ? 'V' : 'H') + p, ls = s => (vertical ? 'H' : 'V') + s;
    const halfP = n => n.kind === 'task' ? (vertical ? TH / 2 : TW / 2) : n.kind === 'gateway' ? GW : EV;
    const halfS = n => n.kind === 'task' ? (vertical ? TW / 2 : TH / 2) : n.kind === 'gateway' ? GW : EV;
    let s = `<svg viewBox="0 0 ${w} ${h}" ${vertical ? `style="max-width:${w}px"` : ''} role="img" aria-label="${esc(UI.t('proc.flow'))}"><defs><marker id="fArr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#6b7a8c"/></marker><marker id="fArrD" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#2e9e6a"/></marker></defs>`;
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
        s += `<g class="${cls}"><rect x="${cx - TW / 2}" y="${cy - TH / 2}" width="${TW}" height="${TH}" rx="8"/><text x="${cx}" y="${cy + (roleName ? -2 : 4)}" text-anchor="middle" class="f-t">${esc(name)}</text>${roleName ? `<text x="${cx}" y="${cy + 13}" text-anchor="middle" class="f-s">${esc(roleName)}</text>` : ''}</g>`;
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
    const fitButton = vertical ? '' : `<button type="button" class="btn small" data-flow-fit aria-pressed="false">${esc(UI.t('btn.fit'))}</button>`;
    return `<div class="flow-cap"><span>${caption}</span><span class="row-wrap">${legend}${fitButton}</span></div><div class="flow-scroll${vertical ? ' vert' : ''}" tabindex="0" role="region" aria-label="${esc(UI.t('proc.flow'))}">${s}</div>`;
  }

  // Keep scroll position and the fit toggle across redraws of the same diagram.
  // A141: `fold` = summary html → the diagram sits inside a closed details (narrow widths: the action stays near the top); open state survives redraws
  function mount(box, html, key, { fold = '' } = {}) {
    const old = box.querySelector('.flow-scroll');
    const same = box.dataset.flowKey === key;
    const left = same && old ? old.scrollLeft : 0, fit = same && old?.classList.contains('fit');
    const wasOpen = same && !!box.querySelector('details.flow-fold[open]');
    box.innerHTML = fold ? `<details class="fold flow-fold" ${wasOpen ? 'open' : ''}><summary>${fold}</summary><div class="fold-body">${html}</div></details>` : html;
    box.dataset.flowKey = key;
    const region = box.querySelector('.flow-scroll'), button = box.querySelector('[data-flow-fit]');
    if (!region || !button) return;
    region.classList.toggle('fit', !!fit); region.scrollLeft = left;
    button.setAttribute('aria-pressed', String(!!fit)); button.textContent = fit ? UI.t('btn.unfit') : UI.t('btn.fit');
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-flow-fit]'); if (!b) return;
    const region = b.closest('.flow-cap').nextElementSibling; if (!region) return;
    const fit = region.classList.toggle('fit');
    b.setAttribute('aria-pressed', String(fit)); b.textContent = fit ? UI.t('btn.unfit') : UI.t('btn.fit');
  });
  // A141: narrow viewport (≤ 1100 px, the same breakpoint as the rest of the shell) → vertical orientation. 1440 keeps the horizontal diagram.
  function narrow() { return window.innerWidth <= 1100; }

  // Definition lookup for screens that have no instance in hand (승인과 실행 before a decision is linked):
  // the newest registered version of the anomaly_response definition, read once.
  let defCache = null;
  async function latestDefinition() {
    if (defCache) return defCache;
    try {
      const list = await getJ(API.process + '/api/process/definitions');
      const mine = list.filter(d => d.id === 'anomaly_response' && d.form_source !== 'legacy-live').sort((a, b) => String(b.version).localeCompare(String(a.version), undefined, { numeric: true }));
      const pick = mine[0]; if (!pick) return null;
      defCache = await getJ(API.process + '/api/process/definitions/' + encodeURIComponent(pick.id) + '?version=' + encodeURIComponent(pick.version));
    } catch (e) { defCache = null; }
    return defCache;
  }
  window.hydFlow = { render, mount, latestDefinition, narrow };
})();
