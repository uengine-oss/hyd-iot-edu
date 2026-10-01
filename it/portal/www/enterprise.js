/* L7 ~ L9 views: 온톨로지 지식 지도 · 전사 의사결정 시나리오 · 업무 프로세스·시스템 연계.
   Loaded after app.js and reuses its helpers ($, el, esc, fmt, getJ, postJ, state, selectTab).
   Data: agent (8091) for the ontology and the decision engine, process (8080) for approval, enterprise-sim (8095) for ERP/MES/…  */
API.ent = P(8095);

const ONTO_GROUPS = [
  { key: 'asset', title: '설비 · 관측', color: '#6b7280', labels: ['Asset', 'Component', 'Sensor', 'Actuator', 'AnomalyPattern', 'Symptom'] },
  { key: 'failure', title: '고장 지식', color: '#b42318', labels: ['FailureMode', 'Cause', 'Evidence'] },
  { key: 'action', title: '조치 지식', color: '#9a6700', labels: ['Action', 'Constraint', 'Procedure', 'Step', 'ManualSection'] },
  { key: 'org', title: '조직 · KPI · 규정', color: '#6d28d9', labels: ['Goal', 'Department', 'Role', 'KPI', 'Policy'] },
  { key: 'sys', title: '시스템 · 스킬 · 프로세스', color: '#0f766e', labels: ['System', 'InfoType', 'Skill', 'BusinessProcess', 'Supplier'] },
  { key: 'decision', title: '판단 · 사례', color: '#1d4ed8', labels: ['Scenario', 'Option', 'Decision', 'Incident', 'Alert', 'ManualUpload'] },
];
const LABEL_KO = { Asset: '설비', Component: '부품', Sensor: '센서', Actuator: '구동기', AnomalyPattern: '이상 패턴', Symptom: '증상', FailureMode: '고장모드',
  Cause: '원인', Evidence: '증거 규칙', Action: '조치', Constraint: '제약', Procedure: 'SOP', Step: 'SOP 단계', ManualSection: '매뉴얼 절', Goal: '전사 목표',
  Department: '부서', Role: '역할', KPI: 'KPI', Policy: '규정', System: '기업 시스템', InfoType: '정보 유형', Skill: '에이전트 스킬', BusinessProcess: '업무 프로세스',
  Supplier: '공급사', ManualUpload: '매뉴얼 적재', Scenario: '판단 시나리오', Option: '대안', Decision: '판단 사례', Incident: '인시던트', Alert: '경보' };
const RELATION_KO = {
  HAS_COMPONENT: '구성 부품', MONITORED_BY: '관측 센서', ACTUATED_BY: '구동 장치', DETECTS: '감지 증상', INDICATES: '나타내는 고장',
  OCCURS_IN: '발생 위치', CAUSES: '일으키는 고장', EVIDENCED_BY: '판단 근거', LEADS_TO: '이어지는 현상',
  MITIGATED_BY: '완화 조치', REMEDIED_BY: '근본 조치', TARGETS: '조치 대상', REQUIRES: '필요 조건', FOLLOWS: '따르는 절차',
  HAS_STEP: '절차 단계', REFERS_TO: '참조 매뉴얼', IMPLEMENTS: '수행하는 조치', EXECUTED_IN: '실행 프로세스', EXECUTED_VIA: '실행 시스템',
  APPROVED_BY: '승인 담당', REQUIRES_INFO: '필요한 정보', NEEDS_INFO: '판단에 필요한 정보', HELD_IN: '정보 보유 시스템',
  USES_SKILL: '사용 스킬', HAS_OPTION: '선택 가능한 대안', TRIGGERS_DECISION: '연결된 판단 상황', IMPACTS: '영향받는 지표',
  OWNED_BY: '담당 부서', CONTRIBUTES_TO: '기여하는 목표', GOVERNS: '적용 대상', MEMBER_OF: '소속 부서', BUYS_FROM: '구매처',
  DECIDED: '선택한 대안', ABOUT: '관련 상황', FOR: '대상 설비', TRIGGERED_BY: '발생 계기', DIAGNOSED_AS: '진단 원인',
  RESOLVED_BY: '해결 조치', INSTANCE_OF: '해당 패턴', INGESTED: '등록된 지식', OBSERVED_BY: '관측 센서',
  USES: '사용 대상', SUPPORTS: '지원 대상', RUNS_ON: '실행 기반', ENFORCED_BY: '준수 확인 시스템',
};
const ent = { graph: null, graphAsset: null, sel: null, hidden: new Set(), focus: null, search: '', scenarios: null, result: null, persp: 'enterprise',
  decisions: [], decSel: null, decDetail: null, entState: null, tx: [], roles: null, busy: false,
  form: { by: '홍길동', role: null, reason: '' }, lastDetailSig: null };

/* ------------------------------------------------ tab hooks */
const _selectTab = selectTab;
selectTab = function (name) {
  _selectTab(name);
  if (name === 'ontology') loadGraph();
  if (name === 'decision') loadScenarios();
  if (name === 'process') refreshProcess();
};
// incident-linked decisions are shown by the HITL panel (hitl.js)

/* ================================================= L7 온톨로지 지식 지도 */
async function loadGraph(force) {
  const asset = $('#ontoAsset').value;
  if (ent.graph && ent.graphAsset === asset && !force) { drawGraph(); return; }
  $('#ontoStats').textContent = '불러오는 중…';
  try {
    const graph = await getJ(API.agent + '/api/ontology/graph?asset=' + encodeURIComponent(asset));
    if ($('#ontoAsset').value !== asset) return;
    if (ent.graphAsset !== asset) ent.sel = null;
    ent.graph = graph; ent.graphAsset = asset;
  }
  catch (e) {
    if ($('#ontoAsset').value !== asset) return;
    ent.graph = null; // A reopened tab must retry, not present cached data as recovered.
    $('#ontoNode').innerHTML = '';
    $('#ontoStats').textContent = '불러오기 실패';
    $('#ontoMap').innerHTML = `<div class="empty" role="alert" title="${esc(e.message)}">지식을 불러올 수 없습니다. 연결을 확인하고 ‘다시 읽기’를 눌러주세요.</div>`;
    return;
  }
  if (!ent.scenarios || !ent.scenarios.length) { try { ent.scenarios = await getJ(API.agent + '/api/agent/scenarios'); } catch (e) { ent.scenarios = null; } }
  const sel = $('#ontoFocus');
  if (sel.options.length <= 1) (ent.scenarios || []).forEach(s => sel.append(new Option(`판단 시나리오 ${s.scenario.no}. ${s.scenario.name}`, s.scenario.id)));
  drawGraph();
}
function groupOf(label) { return ONTO_GROUPS.findIndex(g => g.labels.includes(label)); }
function focusSet() {
  // nodes the agent touches for one decision scenario: scenario → options → skills → systems/processes/infos/policies/roles, KPIs → departments/goals, triggers
  if (!ent.focus || !ent.graph) return null;
  const out = new Map(), inn = new Map();
  for (const e of ent.graph.edges) { (out.get(e.from) || out.set(e.from, []).get(e.from)).push(e); (inn.get(e.to) || inn.set(e.to, []).get(e.to)).push(e); }
  const keep = new Set([ent.focus]);
  const walk = (id, types, dir = 'out') => ((dir === 'out' ? out : inn).get(id) || []).filter(e => types.includes(e.type)).map(e => dir === 'out' ? e.to : e.from);
  const opts = walk(ent.focus, ['HAS_OPTION']); opts.forEach(x => keep.add(x));
  walk(ent.focus, ['NEEDS_INFO']).forEach(i => { keep.add(i); walk(i, ['HELD_IN']).forEach(x => keep.add(x)); });
  walk(ent.focus, ['TRIGGERS_DECISION'], 'in').forEach(x => keep.add(x));
  walk(ent.focus, ['GOVERNS'], 'in').forEach(x => keep.add(x));
  for (const o of opts) {
    walk(o, ['APPROVED_BY', 'BUYS_FROM']).forEach(x => keep.add(x));
    for (const k of walk(o, ['IMPACTS'])) { keep.add(k); walk(k, ['OWNED_BY', 'CONTRIBUTES_TO']).forEach(x => keep.add(x)); }
    for (const s of walk(o, ['USES_SKILL'])) {
      keep.add(s); walk(s, ['EXECUTED_VIA', 'EXECUTED_IN', 'REQUIRES_INFO', 'IMPLEMENTS']).forEach(x => keep.add(x));
      walk(s, ['GOVERNS'], 'in').forEach(x => keep.add(x));
    }
  }
  walk(ent.focus, ['ABOUT'], 'in').forEach(x => keep.add(x));
  return keep;
}
function drawGraph() {
  const g = ent.graph; if (!g) return;
  const W = 192, BOX = 172, H = 26, GAP = 6, TOP = 34;
  const focus = focusSet();
  const q = ent.search.trim().toLowerCase();
  const cols = ONTO_GROUPS.map(() => []);
  for (const n of g.nodes) { const gi = groupOf(n.label); if (gi >= 0 && !ent.hidden.has(ONTO_GROUPS[gi].key)) cols[gi].push(n); }
  const visibleGroups = ONTO_GROUPS.map((gr, i) => ({ gr, i })).filter(x => !ent.hidden.has(x.gr.key));
  const pos = new Map(); let maxY = 0;
  visibleGroups.forEach(({ gr, i }, ci) => {
    let y = TOP;
    for (const lab of gr.labels) {
      const ns = cols[i].filter(n => n.label === lab).sort((a, b) => String(a.id).localeCompare(String(b.id)));
      if (!ns.length) continue;
      pos.set('hdr:' + gr.key + ':' + lab, { x: ci * W + 8, y: y + 10, text: `${LABEL_KO[lab] || lab} · ${ns.length}`, hdr: true });
      y += 16;
      for (const n of ns) { pos.set(n.id, { x: ci * W + 8, y, n }); y += H + GAP; }
      y += 6;
    }
    maxY = Math.max(maxY, y);
  });
  const width = visibleGroups.length * W + 10, height = maxY + 10;
  let svg = `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="온톨로지 지식 지도"><defs><marker id="ontoArrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7Z" fill="#c57905"/></marker></defs>`;
  visibleGroups.forEach(({ gr }, ci) => {
    svg += `<rect x="${ci * W + 2}" y="2" width="${W - 6}" height="${height - 4}" rx="6" fill="${gr.color}" fill-opacity="0.045"/>` +
      `<text x="${ci * W + 10}" y="20" class="o-colh" fill="${gr.color}">${esc(gr.title)}</text>`;
  });
  const selEdges = [];
  let edges = '';
  for (const e of g.edges) {
    const a = pos.get(e.from), b = pos.get(e.to); if (!a || !b) continue;
    const hot = ent.sel && (e.from === ent.sel || e.to === ent.sel);
    const inFocus = focus && focus.has(e.from) && focus.has(e.to);
    const x1 = a.x + BOX, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2;
    let d;
    if (Math.abs(a.x - b.x) < 5) { const bx = a.x + BOX + 14 + Math.min(40, Math.abs(y2 - y1) / 8); d = `M${x1},${y1} C${bx},${y1} ${bx},${y2} ${a.x + BOX},${y2}`; }
    else if (b.x > a.x) d = `M${x1},${y1} C${x1 + 30},${y1} ${x2 - 30},${y2} ${x2},${y2}`;
    else d = `M${a.x},${y1} C${a.x - 30},${y1} ${b.x + BOX + 30},${y2} ${b.x + BOX},${y2}`;
    // Selecting a node identifies its immediate edges; it must not erase the
    // indirect connections to causes, manuals, skills and business processes.
    const cls = hot ? 'o-edge hot' : inFocus ? 'o-edge focus' : focus ? 'o-edge dim' : 'o-edge';
    const nm = id => g.nodes.find(n => n.id === id)?.name || id;
    const path = `<path d="${d}" class="${cls}" ${hot ? 'marker-end="url(#ontoArrow)"' : ''}><title>${esc(nm(e.from))} → ${esc(RELATION_KO[e.type] || e.type)} → ${esc(nm(e.to))} (${esc(e.type)})</title></path>`;
    if (hot) selEdges.push({ path, e, mid: [(x1 + x2) / 2, (y1 + y2) / 2] }); else edges += path;
  }
  svg += edges + selEdges.map(s => s.path).join('');
  for (const [id, p] of pos) {
    if (p.hdr) { svg += `<text x="${p.x}" y="${p.y}" class="o-lab">${esc(p.text)}</text>`; continue; }
    const n = p.n, gi = groupOf(n.label), color = ONTO_GROUPS[gi].color;
    const match = q && (String(n.name).toLowerCase().includes(q) || String(n.id).toLowerCase().includes(q));
    const neighbor = ent.sel && g.edges.some(e => (e.from === ent.sel && e.to === id) || (e.to === ent.sel && e.from === id));
    const dim = focus && !focus.has(id) && !match && id !== ent.sel;
    const cls = ['o-node', id === ent.sel ? 'sel' : '', neighbor ? 'nb' : '', match ? 'match' : '', dim ? 'dim' : ''].join(' ');
    const label = String(n.name || n.id); const short = label.length > 22 ? label.slice(0, 21) + '…' : label;
    svg += `<g class="${cls}" data-id="${esc(id)}" tabindex="0"><rect x="${p.x}" y="${p.y}" width="${BOX}" height="${H}" rx="4" style="--c:${color}"/>` +
      `<text x="${p.x + 7}" y="${p.y + 17}">${esc(short)}</text><title>${esc(LABEL_KO[n.label] || n.label)} · ${esc(n.id)}\n${esc(label)}</title></g>`;
  }
  svg += '</svg>';
  const box = $('#ontoMap'); box.innerHTML = svg;
  // Fit the actual rendered Korean/Latin text, not a fixed character count.
  box.querySelectorAll('.o-node text').forEach(t => {
    const original = t.textContent;
    let short = original;
    while (t.getComputedTextLength() > BOX - 16 && short.length > 1) {
      short = short.slice(0, -1); t.textContent = short + '…';
    }
  });
  box.querySelectorAll('.o-node').forEach(gn => {
    gn.setAttribute('role', 'button');
    gn.setAttribute('aria-label', gn.querySelector('title').textContent);
    gn.setAttribute('aria-pressed', String(gn.dataset.id === ent.sel));
    const pick = () => { const id = gn.dataset.id; ent.sel = ent.sel === id ? null : id; drawGraph(); renderNodePanel();
      [...box.querySelectorAll('.o-node')].find(n => n.dataset.id === id)?.focus({preventScroll:true}); };
    gn.addEventListener('click', pick);
    gn.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); pick(); } });
  });
  const counts = {}; g.nodes.forEach(n => counts[n.label] = (counts[n.label] || 0) + 1);
  const ent_ = ['Department', 'Role', 'KPI', 'Goal', 'Policy', 'System', 'InfoType', 'Skill', 'BusinessProcess', 'Scenario', 'Option', 'Supplier', 'Decision'].reduce((s, l) => s + (counts[l] || 0), 0);
  const matches = [...box.querySelectorAll('.o-node.match')];
  $('#ontoStats').innerHTML = `노드 ${g.nodes.length}개 · 관계 ${g.edges.length}개 · 그중 전사 지식 <b>${ent_}</b>개` + (focus ? ` · 강조 경로 ${focus.size}개 노드` : '') + (q ? ` · 검색 결과 ${matches.length}개` : '');
  if (q && matches.length) { const r = matches[0].getBBox(); box.scrollLeft = Math.max(0, r.x - 20); box.scrollTop = Math.max(0, r.y - 60); }
  renderNodePanel();
}
function renderNodePanel() {
  const box = $('#ontoNode');
  const g = ent.graph; if (!g || !ent.sel) { box.innerHTML = '<div class="muted">노드를 선택하면 속성과 관계를 확인할 수 있습니다. 연결된 이름을 눌러 고장·조치·매뉴얼·스킬로 이어지는 관계를 따라가세요.</div>'; return; }
  const n = g.nodes.find(x => x.id === ent.sel); if (!n) return;
  const props = Object.entries(n.props || {}).filter(([k]) => !['id', 'name'].includes(k));
  const outE = g.edges.filter(e => e.from === n.id), inE = g.edges.filter(e => e.to === n.id);
  const nm = id => { const x = g.nodes.find(y => y.id === id); return x ? x.name : id; };
  const rel = (list, dir) => list.map(e => { const other = dir === 'out' ? e.to : e.from; return `<li><span title="${esc(e.type)}">${dir === 'out' ? '→' : '←'} ${esc(RELATION_KO[e.type] || e.type)}</span> <a href="#" data-go="${esc(other)}">${esc(nm(other))}</a></li>`; }).join('');
  box.innerHTML = `<div class="col"><div class="o-kind">${esc(LABEL_KO[n.label] || n.label)} <span class="muted">(${esc(n.label)})</span></div><h3>${esc(n.name)}</h3><div class="muted mono">${esc(n.id)}</div>` +
    (props.length ? '<table class="kvt">' + props.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(typeof v === 'string' ? v : JSON.stringify(v))}</td></tr>`).join('') + '</table>' : '') + '</div><div class="col">' +
    (outE.length ? `<h4>나가는 관계 ${outE.length}</h4><ul class="rels">${rel(outE, 'out')}</ul>` : '') + (inE.length ? `<h4>들어오는 관계 ${inE.length}</h4><ul class="rels">${rel(inE, 'in')}</ul>` : '') + '</div>';
  box.querySelectorAll('[data-go]').forEach(a => a.addEventListener('click', ev => { ev.preventDefault(); ent.sel = a.dataset.go; drawGraph(); renderNodePanel(); }));
}
function initOntology() {
  const chips = $('#ontoLayers');
  ONTO_GROUPS.forEach(gr => {
    const b = el('label', 'chiptoggle', `<input type="checkbox" checked value="${gr.key}"><i style="background:${gr.color}"></i>${esc(gr.title)}`);
    b.querySelector('input').addEventListener('change', ev => { ev.target.checked ? ent.hidden.delete(gr.key) : ent.hidden.add(gr.key); drawGraph(); });
    chips.append(b);
  });
  $('#ontoAsset').addEventListener('change', () => loadGraph(true));
  $('#ontoFocus').addEventListener('change', ev => { ent.focus = ev.target.value || null; ent.sel = null; drawGraph(); renderNodePanel(); });
  $('#ontoSearch').addEventListener('input', ev => { ent.search = ev.target.value; drawGraph(); });
  $('#ontoReload').addEventListener('click', () => loadGraph(true));
  document.querySelectorAll('#ontoTpl button').forEach(b => b.addEventListener('click', async () => {
    try { const t = await getJ(API.agent + '/api/ontology/template/' + b.dataset.t); $('#ontoTplText').textContent = t.text; }
    catch (e) { $('#ontoTplText').textContent = '템플릿을 읽을 수 없다: ' + e.message; }
  }));
  renderNodePanel();
}

/* ================================================= L8 전사 의사결정 시나리오 */
async function loadScenarios() {
  if (!ent.scenarios) { try { ent.scenarios = await getJ(API.agent + '/api/agent/scenarios'); } catch (e) { $('#scnCards').innerHTML = `<div class="muted">에이전트(8091)에 연결할 수 없다. ${esc(e.message)}</div>`; return; } }
  const box = $('#scnCards');
  if (box.dataset.ready) return;
  box.dataset.ready = '1'; box.innerHTML = '';
  for (const row of ent.scenarios) {
    const s = row.scenario, trig = (row.triggers || []).filter(t => t && t.id).map(t => esc(t.name || t.id)).join(', ');
    const card = el('article', 'scn');
    const assets = s.asset === 'ALL' ? '<option value="">전체 설비</option>' : ['HYD-01', 'HYD-02', 'HYD-03'].map(a => `<option ${a === s.asset ? 'selected' : ''}>${a}</option>`).join('');
    card.innerHTML = `<div class="scn-no">${s.no}</div><h3>${esc(s.name)}</h3><p>${esc(s.question)}</p>
      <div class="muted">온톨로지 트리거: ${trig || '없음'} · 대안 ${row.options}개${s.condition ? ' · 적용 조건 <code>' + esc(s.condition) + '</code>' : ''}</div>
      <div class="scn-run"><select aria-label="설비">${assets}</select><button class="btn primary">에이전트 판단 실행</button></div>`;
    card.querySelector('button').addEventListener('click', () => runDecision(s.id, card.querySelector('select').value || null, card));
    box.append(card);
  }
}
async function runDecision(sid, asset, card) {
  if (ent.busy) return; ent.busy = true;
  const buttons = [...document.querySelectorAll('.scn button')]; buttons.forEach(b => b.disabled = true);
  const activeButton = card?.querySelector('button'); if (activeButton) activeButton.textContent = '판단 중…';
  document.querySelectorAll('.scn').forEach(c => c.classList.toggle('on', c === card));
  $('#decResult').innerHTML = '<div class="muted">에이전트가 온톨로지를 따라 기업 시스템을 조회하고 있다…</div>';
  try { ent.result = await postJ(API.agent + '/api/agent/decide', { scenario: sid, asset }); ent.persp = 'enterprise'; renderDecision(); }
  catch (e) { $('#decResult').innerHTML = `<div class="muted">판단 실패: ${esc(e.message)}</div>`; }
  finally { ent.busy = false; buttons.forEach(b => { b.disabled = false; b.textContent = '에이전트 판단 실행'; }); }
  if (state.tab === 'decision') $('#decResult').scrollIntoView({block:'start'});
}
function won(x) { return x > 0 ? 'pos' : x < 0 ? 'neg' : ''; }
function money(v) { return v == null ? '–' : (v > 0 ? '+' : '') + Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 1 }); }
function renderDecision() {
  const d = ent.result; const box = $('#decResult');
  if (!d || !d.result) { box.innerHTML = `<div class="muted">${esc(d && (d.error || d.status) || '')}</div>`; return; }
  const r = d.result, scn = d.scenario || {}, opts = r.options, kpis = d.kpis || [];
  const name = id => (opts.find(o => o.id === id) || {}).name || id;
  const rec = opts.find(o => o.id === r.recommended);
  const depts = r.departments || [];
  const persp = ent.persp;
  const owners = []; kpis.forEach(k => { if (!owners.find(o => o.id === k.owner)) owners.push({ id: k.owner, name: k.ownerName, kpis: [] }); owners.find(o => o.id === k.owner).kpis.push(k); });
  const used = new Set(opts.flatMap(o => Object.keys(o.impacts)));
  const cols = owners.map(o => ({ ...o, kpis: o.kpis.filter(k => used.has(k.id)) })).filter(o => o.kpis.length);
  const pw = r.winners[persp];
  let html = `<div class="dec-head"><h2>${esc(scn.name || '')} <span class="muted">${esc(d.asset || '')} · ${esc(d.id)}</span></h2>
    <span class="pill ${d.status === 'SUBMITTED' ? 'AWAITING_APPROVAL' : 'CLOSED'}">${esc(UI.status(d.status))}</span></div>`;
  if (d.applicable === false) html += `<div class="note">이 설비는 적용 조건 <code>${esc(d.condition)}</code>을 만족하지 않는다. 경보로 자동 기동되면 제출되지 않지만, 학습용으로 평가 결과를 보여 준다.</div>`;
  html += `<div class="versus">
    <div><small>즉각 제어만 할 때 (L1~L6)</small><p>${esc(scn.immediate || '')}</p><span class="muted">센서값 하나를 보고 설비 하나를 제어한다.</span></div>
    <div class="win"><small>온톨로지 기반 전사 판단 (L7~L9)</small><p>${rec ? '권고: <b>' + esc(rec.name) + '</b>' : '실행 가능한 대안 없음'}</p><span>${esc(r.explanation)}</span></div></div>`;
  html += `<h2>관점 바꿔 보기</h2><div class="persp" role="tablist">` + [{ id: 'enterprise', name: '전사 (Goal: 전사 영업이익)' }, ...depts].map(p =>
    `<button role="tab" class="${p.id === persp ? 'on' : ''}" data-p="${esc(p.id)}">${esc(p.name)}<small>${esc(name(r.winners[p.id]) || '–')}</small></button>`).join('') + '</div>';
  const naive = persp !== 'enterprise' && r.naiveWinners[persp] && r.naiveWinners[persp] !== pw ? opts.find(o => o.id === r.naiveWinners[persp]) : null;
  html += `<p class="muted">${persp === 'enterprise' ? '모든 부서 KPI의 금액 영향을 합산한 순위다.' : '이 부서가 소유한 KPI만 보고 고른 1위다.'} 1위: <b>${esc(name(pw))}</b>` +
    (naive ? ` · 규정을 무시하면 <b>${esc(naive.name)}</b>를 골랐겠지만 <b>${esc(naive.violations[0].name)}</b> 위반으로 제외됐다.` : '') + '</p>';
  html += '<div class="mtx-wrap"><table class="mtx"><thead><tr><th rowspan="2">대안 (스킬 · 승인 역할)</th>' +
    cols.map(o => `<th colspan="${o.kpis.length}" class="${persp === 'enterprise' || persp === o.id ? '' : 'off'}">${esc(o.name)}</th>`).join('') +
    '<th rowspan="2">전사 합계<br><small>만원</small></th><th rowspan="2">규정</th></tr><tr>' +
    cols.flatMap(o => o.kpis.map(k => `<th class="k ${persp === 'enterprise' || persp === o.id ? '' : 'off'}">${esc(k.name)}</th>`)).join('') + '</tr></thead><tbody>';
  for (const o of opts) {
    const cls = [o.id === r.recommended ? 'rec' : '', o.id === pw ? 'pw' : '', o.feasible ? '' : 'out'].join(' ');
    html += `<tr class="${cls}"><td><b>${esc(o.name)}</b>${o.id === r.recommended ? ' <span class="star">권고</span>' : ''}<div class="muted">${esc(o.description || '')}</div>` +
      `<div class="skills">${(o.skills || []).map(s => `<span title="${esc(s.processName || '')}">${esc(s.name)} <i>${esc(s.systemName || '')}</i></span>`).join('') || '<span class="none">스킬 없음</span>'}</div>` +
      `<div class="muted">승인: ${esc((o.approver || {}).name || '–')}</div></td>`;
    for (const c of cols) for (const k of c.kpis) {
      const v = o.impacts[k.id]; const note = (o.notes || {})[k.id] || '';
      html += `<td class="num ${won(v)} ${persp === 'enterprise' || persp === c.id ? '' : 'off'}" title="${esc(note)}">${v == null ? '' : money(v)}</td>`;
    }
    html += `<td class="num tot ${won(o.total)}">${money(o.total)}</td><td>` +
      (o.violations || []).map(v => `<span class="hard" title="${esc(v.source)}">필수 규정 위반 · ${esc(v.name)}</span>`).join('') +
      (o.softPenalties || []).map(v => `<span class="soft" title="${esc(v.source)}">평가 불이익 · ${esc(v.name)} ${money(v.penalty)}</span>`).join('') +
      (o.errors || []).map(e => `<span class="hard">${esc(e)}</span>`).join('') + '</td></tr>';
  }
  html += '</tbody></table></div><p class="muted">셀에 마우스를 올리면 온톨로지에 저장된 산식 설명이 보인다. 금액은 만원, 양수는 이익·절감, 음수는 손실·비용이다.</p>';
  if (r.drivers && r.drivers.length) html += '<h2>권고를 만든 차이 (권고안 − 차선)</h2><div class="drivers">' + r.drivers.map(x => `<span class="${won(x.delta)}">${esc(x.name)} <b>${money(x.delta)}</b></span>`).join('') + '</div>';
  if (d.status === 'SUBMITTED') html += `<div class="approve-row"><button class="btn primary" id="goApprove">승인 화면으로 이동</button><span class="muted">권고안과 승인 역할을 확인한 뒤 실행을 결정합니다.</span></div>`;
  html += '<h2>판단에 사용한 기업 시스템 정보</h2><div class="table-scroll"><table class="prov"><tr><th>정보 유형 (InfoType)</th><th>시스템</th><th>엔드포인트</th><th>가져온 사실</th></tr>' +
    (d.provenance || []).map(p => `<tr><td>${esc(p.name || p.info)}<div class="muted mono">${esc(p.info)}</div></td><td><b>${esc(p.systemName || p.system)}</b></td><td class="mono">${esc(p.endpoint)}</td>` +
      `<td>${p.error ? '<span class="neg">' + esc(p.error) + '</span>' : Object.entries(p.facts || {}).map(([k, v]) => `<code>${esc(k)}=${esc(v)}</code>`).join(' ')}</td></tr>`).join('') + '</table></div>';
  html += `<details class="technical"><summary>판단 과정 확인</summary>` + traceHtml({ id: d.id, status: d.status, started: d.created, steps: d.steps || [] }) + '</details>';
  box.innerHTML = html;
  box.querySelectorAll('.persp button').forEach(b => b.addEventListener('click', () => { ent.persp = b.dataset.p; renderDecision(); }));
  const go = $('#goApprove'); if (go) go.addEventListener('click', () => { ent.decSel = d.id; selectTab('process'); });
}

/* ================================================= L9 업무 프로세스 · 시스템 연계 */
async function refreshProcess() {
  if (state.tab !== 'process') return;
  try { ent.decisions = await getJ(API.process + '/api/decisions'); ent.decisionsError = false; } catch (e) { ent.decisionsError = true; }
  try { [ent.entState, ent.tx] = await Promise.all([getJ(API.ent + '/api/state'), getJ(API.ent + '/api/transactions')]); } catch (e) { ent.entState = null; }
  if (!ent.decSel && ent.decisions.length) ent.decSel = ent.decisions[0].id;
  const selected = ent.decSel;
  if (selected) {
    try { const detail = await getJ(API.process + '/api/decisions/' + selected); if (selected !== ent.decSel) return; ent.decDetail = detail; }
    catch (e) { if (selected !== ent.decSel) return; ent.decDetail = null; }
  }
  renderProcess();
}
function renderProcess() {
  const list = $('#decList');
  const sig = JSON.stringify([ent.decisions, ent.decSel, ent.decisionsError]);
  if (list.dataset.sig !== sig) {
  list.dataset.sig = sig;
  const focused = list.contains(document.activeElement) ? document.activeElement.dataset.itemId : null;
  const scroll = list.scrollTop;
  list.innerHTML = ent.decisions.length ? '' : '<div class="muted">제출된 판단이 없다. 전사 의사결정 시나리오에서 실행하거나, 결함 시나리오 시뮬레이션에서 쿨러 열화를 주입하면 경보에서 자동으로 만들어진다.</div>';
  if (ent.decisionsError) list.innerHTML = '<div class="neg" role="status">판단 목록을 갱신할 수 없습니다. 연결을 확인하세요. 아래는 마지막으로 받은 목록입니다.</div>';
  for (const d of ent.decisions) {
    const it = el('div', 'item' + (d.id === ent.decSel ? ' sel' : ''));
    keyboardItem(it);
    it.dataset.itemId = d.id;
    it.innerHTML = `<div><b>${esc((d.scenario || {}).name || '')}</b> <span class="pill ${esc(d.state)}">${esc(UI.status(d.state))}</span></div>` +
      `<div class="muted">${esc(d.id)} · ${esc(d.asset || '')} · ${(d.origin || {}).kind === 'alert' ? '경보 ' + esc((d.origin || {}).alertId || '') : '수동 실행'}${d.override ? ' · 권고와 다른 안 승인' : ''}</div>`;
    it.addEventListener('click', async () => {
      if (ent.decSel === d.id && ent.decDetail) { UI.revealDetail($('#decDetail')); return; }
      ent.decSel = d.id; ent.decDetail = null; ent.form.msg = ''; ent.lastDetailSig = null;
      $('#decDetail').innerHTML = '<div class="empty" role="status">선택한 판단을 불러오는 중…</div>';
      await refreshProcess();
      if (ent.decSel === d.id) UI.revealDetail($('#decDetail'));
    });
    list.append(it);
  }
  if (focused) [...list.children].find(e => e.dataset.itemId === focused)?.focus({preventScroll:true});
  list.scrollTop = scroll;
  }
  renderDecisionApproval();
  renderSystems();
}
function renderDecisionApproval() {
  const box = $('#decDetail'); const d = ent.decDetail;
  if (!d) { ent.lastDetailSig = null; box.innerHTML = '<div class="empty">왼쪽에서 판단을 고르면 승인 화면이 나온다.</div>'; return; }
  // the 2.5 s refresh must not wipe what the approver is typing or selecting: redraw only when the decision changed
  const sig = d.id + '|' + d.state + '|' + (d.executions || []).length + '|' + (d.history || []).length;
  if (sig === ent.lastDetailSig && box.querySelector('.opts')) return;
  ent.lastDetailSig = sig;
  const roles = Object.entries(d.roles || {}).sort((a, b) => b[1].level - a[1].level);
  const pending = d.state === 'PENDING_APPROVAL';
  let html = `<h2 style="margin-top:0">${esc((d.scenario || {}).name || '')} <span class="pill ${esc(d.state)}">${esc(UI.status(d.state))}</span></h2>
    <div class="muted">${esc(d.id)} · ${esc(d.asset || '')} · 제출 ${esc((d.created || '').slice(11, 19))}${(d.origin || {}).incident ? ' · 인시던트 ' + esc(d.origin.incident) : ''}</div>
    <div class="summary">${esc(d.explanation || '')}</div>`;
  if (pending) html += `<div class="who"><label>승인자 <input id="decBy" value="${esc(ent.form.by)}"></label><label>역할 <select id="decRole">${roles.map(([id, r]) => `<option value="${esc(id)}" ${id === ent.form.role ? 'selected' : ''}>${esc(r.name)} (${esc(r.dept)}, 직급 ${r.level})</option>`).join('')}</select></label>
      <span class="muted">대안마다 승인 역할이 온톨로지(Option -APPROVED_BY-> Role)에 있다. 같은 역할이거나 더 높은 직급만 승인할 수 있다.</span></div>`;
  html += '<div class="table-scroll"><table class="opts"><tr><th>대안</th><th>전사 합계<br><small>만원</small></th><th>승인 역할</th><th>실행될 스킬 → 시스템</th><th></th></tr>';
  for (const o of d.options || []) {
    html += `<tr class="${o.id === d.recommended ? 'rec' : ''} ${o.feasible ? '' : 'out'} ${o.id === d.chosen ? 'chosen' : ''}"><td><b>${esc(o.name)}</b>${o.id === d.recommended ? ' <span class="star">권고</span>' : ''}${o.feasible ? '' : ' <span class="hard">' + esc((o.violations || [])[0] ? o.violations[0].name : '제외') + '</span>'}</td>` +
      `<td class="num ${won(o.total)}">${money(o.total)}</td><td>${esc((o.approver || {}).name || '–')}</td>` +
      `<td>${(o.skills || []).map(s => `${esc(s.name)} → <b>${esc(s.systemName || s.system)}</b>`).join('<br>') || '–'}</td>` +
      `<td>${pending && o.feasible ? `<button class="btn small" data-approve="${esc(o.id)}">이 안으로 승인</button>` : o.id === d.chosen ? '승인됨' : ''}</td></tr>`;
  }
  html += '</table></div>';
  if (pending) html += `<div class="approve-row"><input type="text" id="decReason" placeholder="반려 사유" value="${esc(ent.form.reason)}"><button class="btn" id="decReject">반려</button><span id="decMsg" class="neg">${esc(ent.form.msg || '')}</span></div>`;
  if ((d.executions || []).length) html += '<h2>실행 결과 (L9 → 기업 시스템)</h2><div class="table-scroll" tabindex="0" role="region" aria-label="실행 결과 표"><table class="prov"><tr><th>스킬</th><th>시스템</th><th>결과</th><th>참조</th><th>내용</th></tr>' +
    d.executions.map(x => `<tr><td>${esc(x.skill)}</td><td>${esc(x.system || '')}</td><td><span class="pill ${x.status === 'DONE' ? 'CLOSED' : x.status === 'VIA_HITL' ? 'AWAITING_APPROVAL' : 'ESCALATED'}">${esc(UI.status(x.status))}</span></td><td class="mono">${esc(x.ref || '')}</td><td>${esc(x.detail || '')}</td></tr>`).join('') + '</table></div>';
  html += '<h2>이력</h2><div class="audit">' + (d.history || []).map(h => `<div>${esc((h.t || '').slice(11, 19))} <b>${esc(h.state)}</b> ${esc(h.by || '')} ${esc(h.role || '')} ${esc(h.option || '')} ${esc(h.reason || '')}</div>`).join('') + '</div>';
  box.innerHTML = html;
  const by = $('#decBy'), role = $('#decRole'), reason = $('#decReason');
  if (by) by.addEventListener('input', () => ent.form.by = by.value);
  if (role) { ent.form.role = role.value; role.addEventListener('change', () => { ent.form.role = role.value; ent.form.msg = ''; }); }
  if (reason) reason.addEventListener('input', () => ent.form.reason = reason.value);
  box.querySelectorAll('[data-approve]').forEach(b => b.addEventListener('click', async () => {
    const controls = [...box.querySelectorAll('[data-approve],#decReject')];
    controls.forEach(c => c.disabled = true); b.textContent = '승인 중…';
    $('#decMsg').textContent = '승인 요청을 처리하고 있습니다.';
    try { ent.form.msg = ''; await postJ(API.process + `/api/decisions/${d.id}/approve`, { option: b.dataset.approve, by: $('#decBy').value || '승인자', role: $('#decRole').value }); await refreshProcess(); }
    catch (e) { ent.form.msg = e.message; if (ent.decSel === d.id) $('#decMsg').textContent = e.message; }
    finally { controls.forEach(c => c.disabled = false); b.textContent = '이 안으로 승인'; }
  }));
  const rj = $('#decReject'); if (rj) rj.addEventListener('click', async () => {
    if (!$('#decReason').value.trim()) { ent.form.msg = '반려 사유를 입력하세요.'; $('#decMsg').textContent = ent.form.msg; $('#decReason').focus(); return; }
    const controls = [...box.querySelectorAll('[data-approve],#decReject')];
    controls.forEach(c => c.disabled = true); rj.textContent = '반려 중…';
    try { await postJ(API.process + `/api/decisions/${d.id}/reject`, { by: $('#decBy').value, reason: $('#decReason').value }); await refreshProcess(); }
    catch (e) { if (ent.decSel === d.id) $('#decMsg').textContent = e.message; }
    finally { controls.forEach(c => c.disabled = false); rj.textContent = '반려'; }
  });
}
function renderSystems() {
  const box = $('#sysBoards'); const s = ent.entState;
  if (!s) { box.innerHTML = '<div class="muted">enterprise-sim(8095)에 연결할 수 없다.</div>'; return; }
  const t = (rows, cols) => rows.length ? '<table>' + rows.slice(0, 6).map(r => '<tr>' + cols.map(c => `<td>${esc(r[c] ?? '')}</td>`).join('') + '</tr>').join('') + '</table>' : '<div class="muted">변경 없음</div>';
  const boards = [
    ['MES', '생산오더', t(s.mes.orders.map(o => ({ ...o, where: o.moved_from ? `${o.moved_from} → ${o.asset}` : o.asset })), ['order_id', 'where', 'due_in_h'])],
    ['CMMS', '작업지시', t(s.cmms.work_orders, ['id', 'asset', 'task', 'window'])],
    ['ERP', '구매요청 · 출하', t([...s.erp.purchase_requests.map(p => ({ a: p.id, b: p.supplierName, c: p.status })), ...s.erp.shipments.map(x => ({ a: x.id, b: `${x.item} ${x.qty}개`, c: x.from }))], ['a', 'b', 'c'])],
    ['QMS', '격리 · 출하 승인', t([...s.qms.holds.map(h => ({ a: h.lot, b: h.status })), ...s.qms.releases.map(h => ({ a: h.lot, b: h.status }))], ['a', 'b'])],
    ['EMS', '수요 제어', t(s.ems.actions, ['action'])],
  ];
  box.innerHTML = boards.map(([sys, title, body]) => `<div class="board"><header><b>${sys}</b><span>${title}</span></header>${body}</div>`).join('');
  $('#txList').innerHTML = ent.tx.length ? ent.tx.slice(0, 12).map(x => `<div>${esc(x.t.slice(11, 19))} <b>${esc(x.system)}</b> ${esc(x.detail)} <span class="muted">${esc(x.ref)} · ${esc(x.decision || '')} · ${esc(x.by || '')}</span></div>`).join('') : '<div class="muted">아직 실행된 트랜잭션이 없다.</div>';
}

/* ------------------------------------------------ 이상 확인 & 조치: 인시던트에 연결된 전사 판단 */
async function fillIncidentDecisions() {
  const inc = state.detail; if (!inc) return;
  const host = document.getElementById('incDetail'); if (!host) return;
  let box = document.getElementById('incDecisions');
  if (!box) { box = el('div'); box.id = 'incDecisions'; const h = [...host.querySelectorAll('h2')].find(x => x.textContent.startsWith('가이드 카드')); host.insertBefore(box, h || null); }
  try {
    const all = await getJ(API.process + '/api/decisions');
    const mine = all.filter(d => (d.origin || {}).incident === inc.id);
    box.innerHTML = '<h2>전사 판단 (L7 → L8 → L9)</h2>' + (mine.length ? '<div class="linked">' + mine.map(d =>
      `<a href="#" data-dec="${esc(d.id)}"><b>${esc((d.scenario || {}).name || '')}</b> <span class="pill ${esc(d.state)}">${esc(UI.status(d.state))}</span></a>`).join('') +
      '</div><p class="muted">같은 경보를 온톨로지가 ERP·MES·CMMS·QMS 정보와 부서 KPI로 이어 판단한 결과다. 누르면 승인 화면으로 간다.</p>'
      : '<div class="muted">이 인시던트와 연결된 전사 판단이 없다.</div>');
    box.querySelectorAll('[data-dec]').forEach(a => a.addEventListener('click', ev => { ev.preventDefault(); ent.decSel = a.dataset.dec; selectTab('process'); }));
  } catch (e) { box.innerHTML = ''; }
}

initOntology();
setInterval(() => { if (state.tab === 'process') refreshProcess(); }, 2500);
window.hydApp.selectTab = selectTab;          // the recorder and ?present=1 hooks must see the L7~L9 loaders too
window.hydEnt = { ent, runDecision, loadGraph, refreshProcess };
