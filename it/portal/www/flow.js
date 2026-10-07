/* A122 — business-process flow drawn straight from the process definition JSON (docs/handoff/UIUX_PLAN.md §4, option B).
   Lanes are the three doers only: 에이전트 (sys:agent) · 담당자 (role:*) · 시스템 (sys:scada · sys:process · sys:cmms · start/end).
   Columns are "longest distance from the start event" (same rule as instanceSteps.js flowGraph). A boundary timer is a small
   circle on its task's border. Node colour = state of the newest work item for that activity (done · current · skipped · fail).
   Nothing here changes the definition or calls the engine. */
(function () {
  const LANES = [['agent', 'flow.lane.agent'], ['human', 'flow.lane.human'], ['system', 'flow.lane.system']];
  const PITCH = 142, TW = 120, TH = 44, LEFT = 96, TOP = 8, GW = 18, EV = 15, LANE_MIN = 88, ROW = 62;

  function laneOf(node, roleEndpoint) {
    if (node.kind === 'event' && (node.type === 'startEvent')) return 'system';
    const ep = node.agent || roleEndpoint || '';
    if (ep === 'sys:agent' || node.orchestration === 'cliagents') return 'agent';
    if (/^role:/.test(ep)) return 'human';
    if (/^sys:/.test(ep)) return 'system';
    return null;        // gateways and end events inherit their predecessor's lane
  }

  function build(def) {
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
    // rows inside a lane: nodes sharing (lane, column) stack vertically
    const cols = new Map();
    placed.forEach(n => { const k = lane.get(n.id) + ':' + (depth.get(n.id) ?? 0); if (!cols.has(k)) cols.set(k, []); cols.get(k).push(n); });
    const laneRows = { agent: 1, human: 1, system: 1 };
    cols.forEach((list, k) => { const l = k.split(':')[0]; laneRows[l] = Math.max(laneRows[l], list.length); });
    const laneH = {}, laneY = {}; let y = TOP;
    LANES.forEach(([l]) => { laneY[l] = y; laneH[l] = Math.max(LANE_MIN, laneRows[l] * ROW + 26); y += laneH[l]; });
    const pos = new Map();
    cols.forEach((list, k) => {
      const [l, d] = k.split(':');
      list.forEach((n, i) => pos.set(n.id, { x: LEFT + Number(d) * PITCH + PITCH / 2, y: laneY[l] + laneH[l] / 2 + (i - (list.length - 1) / 2) * ROW }));
    });
    const maxDepth = Math.max(0, ...[...depth.values()]);
    return { nodes, seqs, hostOf, pos, lane, depth, laneH, laneY, height: y + 8, width: LEFT + (maxDepth + 1) * PITCH + 8, start };
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

  function render(def, { workitems = null, instance = null, caption = '' } = {}) {
    if (!def || !(def.activities || []).length) return `<div class="flow-cap"><span>${esc(caption)}</span></div>`;
    const g = build(def), st = states(def, g, workitems, instance);
    const w = Math.max(g.width, LEFT + 3 * PITCH), h = g.height;
    let s = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(UI.t('proc.flow'))}"><defs><marker id="fArr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#6b7a8c"/></marker><marker id="fArrD" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#2e9e6a"/></marker></defs>`;
    LANES.forEach(([l, term], i) => {
      s += `<rect x="4" y="${g.laneY[l]}" width="${w - 8}" height="${g.laneH[l]}" class="f-lane ${i % 2 ? 'alt' : ''}"/><rect x="4" y="${g.laneY[l]}" width="${LEFT - 12}" height="${g.laneH[l]}" class="f-lanehead"/><text x="16" y="${g.laneY[l] + g.laneH[l] / 2 + 4}" class="f-lanet">${esc(UI.t(term))}</text>`;
    });
    const half = n => n.kind === 'task' ? TW / 2 : n.kind === 'gateway' ? GW : EV;
    const timerPos = id => { const n = g.nodes.get(id); const p = g.pos.get(n.attachedTo); return p ? { x: p.x + TW / 2 - 14, y: p.y + TH / 2 } : null; };
    // edges
    g.seqs.forEach(sq => {
      const fromBoundary = g.hostOf(sq.source) !== sq.source;
      const A = g.nodes.get(g.hostOf(sq.source)), B = g.nodes.get(sq.target);
      const a = g.pos.get(A.id), b = g.pos.get(B.id); if (!a || !b) return;
      const da = g.depth.get(A.id) ?? 0, db = g.depth.get(B.id) ?? 0;
      const ax = a.x + half(A), bx = b.x - half(B);
      let d, lx, ly;
      if (fromBoundary) {                                   // from the timer circle, down the lane channel, over to the target
        const t = timerPos(sq.source); const chan = g.laneY[g.lane.get(A.id)] + g.laneH[g.lane.get(A.id)] - 10;
        d = `M${t.x} ${t.y + 7} V${chan} H${bx - PITCH / 2 + 24} V${b.y} H${bx}`; lx = t.x + 14; ly = chan - 5;
      } else if (db - da > 1 && a.y === b.y) {              // long skip inside one lane: route under the nodes in between
        const chan = g.laneY[g.lane.get(A.id)] + g.laneH[g.lane.get(A.id)] - 10;
        d = `M${ax} ${a.y} H${ax + 16} V${chan} H${bx - 16} V${b.y} H${bx}`; lx = ax + 24; ly = chan - 5;
      } else if (db - da > 1) {                             // long skip across lanes: drop to the target lane first
        const mid = ax + 16;
        d = `M${ax} ${a.y} H${mid} V${b.y} H${bx}`; lx = mid + 6; ly = b.y - 6;
      } else if (a.y === b.y) { d = `M${ax} ${a.y} H${bx}`; lx = (ax + bx) / 2; ly = a.y - 6; }
      else { const mid = (ax + bx) / 2; d = `M${ax} ${a.y} H${mid} V${b.y} H${bx}`; lx = mid + 4; ly = (a.y + b.y) / 2 - 6; }
      const done = (st[A.id] === 'done' || st[A.id] === 'current') && (st[B.id] === 'done' || st[B.id] === 'current');
      s += `<path d="${d}" class="f-flow${done ? ' done' : ''}" marker-end="url(#${done ? 'fArrD' : 'fArr'})"/>`;
      const label = UI.flowSeq(sq.name);
      if (label) s += `<text x="${lx}" y="${ly}" class="f-flowt">${esc(label)}</text>`;
    });
    // nodes
    g.nodes.forEach(n => {
      if (n.kind === 'event' && n.attachedTo) return;
      const p = g.pos.get(n.id); if (!p) return;
      const cls = `f-node ${st[n.id] || 'todo'}`;
      const label = UI.flowName(n.name);
      if (n.kind === 'task') {
        const roleName = g.lane.get(n.id) === 'human' ? n.role : '';
        s += `<g class="${cls}"><rect x="${p.x - TW / 2}" y="${p.y - TH / 2}" width="${TW}" height="${TH}" rx="8"/><text x="${p.x}" y="${p.y + (roleName ? -2 : 4)}" text-anchor="middle" class="f-t">${esc(label)}</text>${roleName ? `<text x="${p.x}" y="${p.y + 13}" text-anchor="middle" class="f-s">${esc(roleName)}</text>` : ''}</g>`;
      } else if (n.kind === 'gateway') {
        s += `<g class="${cls}"><path d="M${p.x} ${p.y - GW} L${p.x + GW} ${p.y} L${p.x} ${p.y + GW} L${p.x - GW} ${p.y} Z"/><text x="${p.x}" y="${p.y + 5}" text-anchor="middle" class="f-g">×</text><text x="${p.x}" y="${p.y - GW - 6}" text-anchor="middle" class="f-s">${esc(label)}</text></g>`;
      } else {
        s += `<g class="${cls} ${n.type === 'endEvent' ? 'end' : 'start'}"><circle cx="${p.x}" cy="${p.y}" r="${EV}"/><text x="${p.x}" y="${p.y + EV + 14}" text-anchor="middle" class="f-s">${esc(label)}</text></g>`;
      }
    });
    // boundary timers on their task border
    g.nodes.forEach(n => {
      if (!(n.kind === 'event' && n.attachedTo)) return;
      const t = timerPos(n.id); if (!t) return;
      const used = st[n.id] === 'done';
      s += `<g class="f-timer ${used ? 'done' : ''}"><circle cx="${t.x}" cy="${t.y}" r="9"/><circle cx="${t.x}" cy="${t.y}" r="6.5"/><path d="M${t.x} ${t.y - 4} V${t.y} H${t.x + 3}"/><title>${esc(UI.flowName(n.name))}</title></g>`;
    });
    s += '</svg>';
    const legend = `<span class="f-legend"><span><i class="done"></i>${esc(UI.t('proc.legend.done'))}</span><span><i class="current"></i>${esc(UI.t('proc.legend.now'))}</span><span><i class="fail"></i>${esc(UI.t('proc.legend.stop'))}</span><span><i class="skipped"></i>${esc(UI.t('proc.legend.skipped'))}</span></span>`;
    return `<div class="flow-cap"><span>${caption}</span><span class="row-wrap">${legend}<button type="button" class="btn small" data-flow-fit aria-pressed="false">${esc(UI.t('btn.fit'))}</button></span></div><div class="flow-scroll" tabindex="0" role="region" aria-label="${esc(UI.t('proc.flow'))}">${s}</div>`;
  }

  // Keep scroll position and the fit toggle across redraws of the same diagram.
  function mount(box, html, key) {
    const old = box.querySelector('.flow-scroll');
    const same = box.dataset.flowKey === key;
    const left = same && old ? old.scrollLeft : 0, fit = same && old?.classList.contains('fit');
    box.innerHTML = html; box.dataset.flowKey = key;
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
  window.hydFlow = { render, mount, latestDefinition };
})();
