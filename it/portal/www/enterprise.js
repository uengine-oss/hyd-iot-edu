/* 지식 지도 · 조치 판단 규칙 · 승인과 실행 (enterprise.js) — ontology v2.
   Loaded after app.js and reuses its helpers ($, el, esc, fmt, getJ, postJ, state, selectTab).
   Data: agent (8091) for the ontology and the decision engine, process (8080) for approval, enterprise-sim (8095) for ERP/MES/…
   A122: wording from UI.terms; action-candidate card = title · chips · score · one line · evidence folded (UIUX_PLAN §1.1 · §1.3 · §1.5). */
API.ent = P(8095);

// columns of the knowledge map = layers of the ontology v2 schema (it/neo4j/v2/schema.json); titles without framework names (명칭표)
const ONTO_GROUPS = [
  { key: 'value', title: '전략 목표', color: '#6d28d9', labels: ['Perspective', 'Objective', 'Measure'] },
  { key: 'process', title: '프로세스', color: '#1d4ed8', labels: ['Process', 'Event', 'Task', 'Gateway'] },
  { key: 'resource', title: '자원', color: '#6b7280', labels: ['OrgUnit', 'Role', 'System', 'Asset', 'Component', 'Sensor', 'Actuator', 'StateVariable', 'Part', 'Supplier'] },
  { key: 'diagnosis', title: '설비 진단', color: '#b42318', labels: ['AnomalyPattern', 'Symptom', 'FailureMode', 'Cause', 'Evidence', 'ManualSection'] },
  { key: 'skill', title: '조치 방법과 규칙', color: '#0f766e', labels: ['Skill', 'Step', 'Action', 'Decision', 'DecisionTable', 'Rule', 'InputData', 'KnowledgeSource'] },
  { key: 'external', title: '외부 변수 · 예측 · 사례', color: '#9a6700', labels: ['ExternalVariable', 'Forecast', 'Incident', 'DecisionCase'] },
  // G4: 학생 이름 공간의 업무 고유 클래스(students/<ID>/schema.json) — v2 에 없는 레이블은 모두 이 칸에 그린다
  { key: 'student', title: '내 업무 개념', color: '#be185d', labels: [], other: true },
];
const LABEL_KO = { Perspective: '관점', Objective: '전략 목표', Measure: '성과 지표', Process: '프로세스', Event: '이벤트', Task: '단계', Gateway: '분기',
  OrgUnit: '부서', Role: '역할', System: '시스템', Asset: '설비', Component: '구성 요소', Sensor: '센서', Actuator: '구동기', StateVariable: '상태 변수',
  Part: '부품', Supplier: '공급사', AnomalyPattern: '이상 패턴', Symptom: '증상', FailureMode: '고장 유형', Cause: '원인', Evidence: '증거', ManualSection: '매뉴얼 절',
  Skill: '조치 방법', Step: '절차 단계', Action: '세부 동작', Decision: '판단', DecisionTable: '결정표', Rule: '규칙', InputData: '입력 데이터',
  KnowledgeSource: '지식 출처', ExternalVariable: '외부 변수', Forecast: '예측', Incident: '사건', DecisionCase: '판단 사례' };
const RELATION_KO = {
  IN_PERSPECTIVE: '속한 관점', SUPPORTS: '받쳐 주는 목표', MEASURES: '측정하는 목표', OWNED_BY: '담당 부서', INFLUENCES: '영향 (+/−)',
  ACHIEVES: '달성하는 조직 목표', HAS_NODE: '흐름 노드', SEQUENCE_FLOW: '다음 단계', ATTACHED_TO: '경계 이벤트', PERFORMED_BY: '수행자', READS: '읽는 데이터',
  PRODUCES: '만드는 데이터', INVOKES: '부르는 판단', EXECUTES: '실행하는 조치 방법', CORRELATES: '시작시키는 경보', ACTS_ON: '대상 설비',
  MEMBER_OF: '소속 부서', HAS_COMPONENT: '구성 요소', MONITORED_BY: '관측 센서', ACTUATED_BY: '구동 장치', OBSERVES: '읽는 상태 변수', MANIPULATES: '바꾸는 변수',
  USES_PART: '교체 부품', SUPPLIED_BY: '공급사', HAS_SKILL: '수행 가능한 조치 방법', SOURCED_FROM: '데이터 출처', REPRESENTS: '나타내는 변수 · 지표',
  DETECTS: '감지 증상', OBSERVED_BY: '관측 센서', INDICATES: '나타내는 고장', OCCURS_IN: '발생 위치', LEADS_TO: '이어지는 고장', CAUSES: '일으키는 고장',
  INVOLVES_PART: '관련 부품', DISTURBS: '움직이는 외란', EVIDENCED_BY: '확증 근거', MITIGATED_BY: '즉시 완화', REMEDIED_BY: '근본 조치', PREVENTED_BY: '예방 조치',
  ADDRESSES: '해당 원인', HAS_STEP: '절차 단계', REFERS_TO: '근거 매뉴얼', PART_OF: '속한 문서', CONSISTS_OF: '세부 동작', TARGETS: '조치 대상',
  APPROVED_BY: '승인 역할', AFFECTS: '움직이는 변수 · 지표', REQUIRES_INPUT: '필요한 입력', REQUIRES_DECISION: '먼저 내릴 판단', IMPLEMENTED_BY: '결정표',
  GOVERNED_BY: '통제 출처', HAS_RULE: '규칙', TESTS: '임계값 검사', OUTPUTS: '고르는 결과', APPLIES_TO: '적용 대상', PENALIZES: '감점 지표',
  DERIVED_FROM: '근거 출처', FORECASTS: '예측 대상', ASSUMES: '가정한 조치', GIVEN: '가정한 원인', ON_ASSET: '설비', RAISED_BY: '경보 패턴',
  DIAGNOSED_AS: '판정 원인', INSTANCE_OF: '판단 정의', CHOSE: '고른 조치', DECIDED_BY: '판단한 역할', FOR_INCIDENT: '대상 사건',
};
const ent = { graph: null, graphAsset: null, sel: null, hidden: new Set(), focus: null, search: '', patterns: null, result: null,
  decisions: [], decSel: null, decDetail: null, entState: null, tx: [], roles: null, busy: false,
  form: { by: '홍길동', role: null, reason: '', option: null }, lastDetailSig: null, decShown: 20 };

/* ------------------------------------------------ tab hooks */
const _selectTab = selectTab;
selectTab = function (name) {
  _selectTab(name);
  if (name === 'ontology') loadGraph();
  if (name === 'decision') loadDecisionView();
  if (name === 'process') refreshProcess();
};
async function loadPatterns() {
  if (!ent.patterns || !ent.patterns.length) { try { ent.patterns = await getJ(API.agent + '/api/ontology/patterns'); } catch (e) { ent.patterns = null; } }
  return ent.patterns || [];
}

/* ================================================= 지식 지도 */
async function loadNamespaces() {
  // G4: 학생 이름 공간 목록(기본 = 수업 기준). 실패해도 지도는 수업 기준으로 그린다
  const sel = $('#ontoNs'); if (!sel || sel.dataset.loaded) return;
  try {
    const list = await getJ(API.agent + '/api/ontology/namespaces');
    list.forEach(x => sel.append(new Option(`${x.ns} · ${x.nodes}`, x.ns)));
    sel.dataset.loaded = '1';
  } catch (e) { /* 목록이 없으면 수업 기준만 */ }
}
async function loadGraph(force) {
  const asset = $('#ontoAsset').value + '|' + (($('#ontoNs') || {}).value || '');
  if (ent.graph && ent.graphAsset === asset && !force) { drawGraph(); return; }
  $('#ontoStats').textContent = UI.t('loading');
  loadNamespaces();
  const [code, ns] = asset.split('|');
  const current = () => $('#ontoAsset').value + '|' + (($('#ontoNs') || {}).value || '');
  try {
    const graph = await getJ(API.agent + '/api/ontology/graph?asset=' + encodeURIComponent(code) + (ns ? '&ns=' + encodeURIComponent(ns) : ''));
    if (current() !== asset) return;
    if (ent.graphAsset !== asset) ent.sel = null;
    ent.graph = graph; ent.graphAsset = asset;
  }
  catch (e) {
    if (current() !== asset) return;
    ent.graph = null; // A reopened tab must retry, not present cached data as recovered.
    $('#ontoNode').innerHTML = '';
    $('#ontoStats').textContent = UI.t('error.load');
    $('#ontoMap').innerHTML = `<div role="alert" title="${esc(e.message)}">${UI.empty(UI.t('onto.loadFail'), UI.t('onto.loadFailSub'))}</div>`;
    return;
  }
  const pats = await loadPatterns();
  const sel = $('#ontoFocus');
  if (sel.options.length <= 1) pats.forEach(p => sel.append(new Option(p.name, p.id)));
  drawGraph();
}
function groupOf(label) {
  const i = ONTO_GROUPS.findIndex(g => g.labels.includes(label));
  return i >= 0 ? i : ONTO_GROUPS.findIndex(g => g.other);
}
// A141: the graph API fills `name` with the id when a node has no name (Rule nodes) — then the names.json dictionary (annotation) applies
const nodeName = n => String(n.name && n.name !== n.id ? n.name : UI.name(n.id));
function focusSet() {
  // the path the agent walks for one anomaly pattern: pattern → symptoms → failure modes → causes · evidence → skills
  // → steps · manual · atomic actions · approver, the rules that select / limit each skill, its first KPI effects and forecasts
  if (!ent.focus || !ent.graph) return null;
  const out = new Map(), inn = new Map();
  for (const e of ent.graph.edges) { (out.get(e.from) || out.set(e.from, []).get(e.from)).push(e); (inn.get(e.to) || inn.set(e.to, []).get(e.to)).push(e); }
  const keep = new Set([ent.focus]);
  const walk = (id, types, dir = 'out') => ((dir === 'out' ? out : inn).get(id) || []).filter(e => types.includes(e.type)).map(e => dir === 'out' ? e.to : e.from);
  const add = xs => { xs.forEach(x => keep.add(x)); return xs; };
  add(walk(ent.focus, ['TESTS', 'DERIVED_FROM']));
  add(walk(ent.focus, ['CORRELATES'], 'in')).forEach(ev => add(walk(ev, ['HAS_NODE'], 'in')));
  for (const sy of add(walk(ent.focus, ['DETECTS']))) {
    for (const fm of add(walk(sy, ['INDICATES']))) {
      add(walk(fm, ['OCCURS_IN']));
      for (const c of add(walk(fm, ['CAUSES'], 'in'))) add(walk(c, ['EVIDENCED_BY', 'DISTURBS']));
      for (const s of add(walk(fm, ['MITIGATED_BY', 'REMEDIED_BY', 'PREVENTED_BY']))) {
        add(walk(s, ['APPROVED_BY', 'CONSISTS_OF', 'ADDRESSES']));
        for (const st of add(walk(s, ['HAS_STEP']))) add(walk(st, ['REFERS_TO']));
        add(walk(s, ['AFFECTS']));
        for (const r of add(walk(s, ['OUTPUTS', 'APPLIES_TO'], 'in'))) add(walk(r, ['DERIVED_FROM', 'TESTS']));
        add(walk(s, ['ASSUMES'], 'in'));
      }
    }
  }
  return keep;
}
function drawGraph() {
  const g = ent.graph; if (!g) return;
  const count = Math.max(1, ONTO_GROUPS.length - ent.hidden.size);
  const W = Math.max(192, Math.min(280, Math.floor(($('#ontoMap').clientWidth - 10) / count))), BOX = W - 20, H = 28, GAP = 6, TOP = 34;
  const focus = focusSet();
  const q = ent.search.trim().toLowerCase();
  const cols = ONTO_GROUPS.map(() => []);
  for (const n of g.nodes) { const gi = groupOf(n.label); if (gi >= 0 && !ent.hidden.has(ONTO_GROUPS[gi].key)) cols[gi].push(n); }
  const visibleGroups = ONTO_GROUPS.map((gr, i) => ({ gr, i })).filter(x => !ent.hidden.has(x.gr.key));
  const pos = new Map(); let maxY = 0;
  visibleGroups.forEach(({ gr, i }, ci) => {
    let y = TOP;
    const labs = gr.other ? [...new Set(cols[i].map(n => n.label))].sort() : gr.labels;   // G4: 학생 클래스 레이블은 그때그때
    for (const lab of labs) {
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
  let svg = `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="지식 지도">`;
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
    const cls = hot ? 'o-edge hot' : inFocus ? 'o-edge focus' : (focus || ent.sel) ? 'o-edge dim' : 'o-edge';
    const nm = id => nodeName(g.nodes.find(n => n.id === id) || { id });   // A141: 관계 말풍선도 이름 없는 규칙은 사전으로
    const path = `<path d="${d}" class="${cls}"><title>${esc(nm(e.from))} → ${esc(RELATION_KO[e.type] || e.type)} → ${esc(nm(e.to))}</title></path>`;
    if (hot) selEdges.push({ path, e, mid: [(x1 + x2) / 2, (y1 + y2) / 2] }); else edges += path;
  }
  svg += edges + selEdges.map(s => s.path).join('');
  for (const [id, p] of pos) {
    if (p.hdr) { svg += `<text x="${p.x}" y="${p.y}" class="o-lab">${esc(p.text)}</text>`; continue; }
    const n = p.n, gi = groupOf(n.label), color = ONTO_GROUPS[gi].color;
    const match = q && (String(n.name).toLowerCase().includes(q) || String(n.id).toLowerCase().includes(q));
    const neighbor = ent.sel && g.edges.some(e => (e.from === ent.sel && e.to === id) || (e.to === ent.sel && e.from === id));
    const dim = (focus || ent.sel) && !(focus && focus.has(id)) && id !== ent.sel && !neighbor && !match;
    const cls = ['o-node', id === ent.sel ? 'sel' : '', neighbor ? 'nb' : '', match ? 'match' : '', dim ? 'dim' : ''].join(' ');
    const label = nodeName(n);   // A141: 이름 없는 규칙 노드는 사전(annotation)으로, 없으면 id 그대로
    svg += `<g class="${cls}" data-id="${esc(id)}" tabindex="0"><rect x="${p.x}" y="${p.y}" width="${BOX}" height="${H}" rx="4" style="--c:${color}"/>` +
      `<text x="${p.x + 7}" y="${p.y + 17}">${esc(label)}</text><title>${esc(LABEL_KO[n.label] || n.label)}\n${esc(label)}</title></g>`;
  }
  svg += '</svg>';
  const box = $('#ontoMap'); const scroll = [box.scrollLeft, box.scrollTop]; box.innerHTML = svg; box.scrollLeft = scroll[0]; box.scrollTop = scroll[1];
  // Fit the actual rendered Korean/Latin text, not a fixed character count.
  box.querySelectorAll('.o-node text').forEach(t => {
    let short = t.textContent;
    while (t.getComputedTextLength() > BOX - 16 && short.length > 1) { short = short.slice(0, -1); t.textContent = short + '…'; }
  });
  box.querySelectorAll('.o-node').forEach(gn => {
    gn.setAttribute('role', 'button');
    gn.setAttribute('aria-label', gn.querySelector('title').textContent);
    gn.setAttribute('aria-pressed', String(gn.dataset.id === ent.sel));
    const pick = () => { const id = gn.dataset.id; ent.sel = ent.sel === id ? null : id; drawGraph(); renderNodePanel();
      [...box.querySelectorAll('.o-node')].find(n => n.dataset.id === id)?.focus({ preventScroll: true }); };
    gn.addEventListener('click', pick);
    gn.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); pick(); } });
  });
  const counts = {}; g.nodes.forEach(n => counts[n.label] = (counts[n.label] || 0) + 1);
  const matches = [...box.querySelectorAll('.o-node.match')];
  const fmtN = n => Number(n).toLocaleString('ko-KR');
  $('#ontoStats').textContent = UI.t('onto.stats', { n: fmtN(g.nodes.length), e: fmtN(g.edges.length), s: counts.Skill || 0, r: counts.Rule || 0, k: counts.Measure || 0 })
    + (focus ? ' · ' + UI.t('onto.path', { n: focus.size }) : '') + (q ? ' · ' + UI.t('onto.found', { n: matches.length }) : '') + (box.scrollWidth > box.clientWidth ? ' · ' + UI.t('onto.scroll') : '');
  if (q && matches.length) { const r = matches[0].getBBox(); box.scrollLeft = Math.max(0, r.x - 20); box.scrollTop = Math.max(0, r.y - 60); }
  renderNodePanel();
}
function renderNodePanel() {
  const box = $('#ontoNode');
  const g = ent.graph; if (!g || !ent.sel) { box.innerHTML = `<div class="muted">${esc(UI.t('onto.hint'))}</div>`; return; }
  const n = g.nodes.find(x => x.id === ent.sel); if (!n) return;
  const props = Object.entries(n.props || {}).filter(([k]) => !['id', 'name'].includes(k));
  const outE = g.edges.filter(e => e.from === n.id), inE = g.edges.filter(e => e.to === n.id);
  const nm = id => nodeName(g.nodes.find(y => y.id === id) || { id });
  const rel = (list, dir) => list.map(e => { const other = dir === 'out' ? e.to : e.from; return `<li><span>${dir === 'out' ? '→' : '←'} ${esc(RELATION_KO[e.type] || e.type)}</span> <a href="#" data-go="${esc(other)}">${esc(nm(other))}</a></li>`; }).join('');
  box.innerHTML = `<div class="col"><div class="o-kind">${esc(LABEL_KO[n.label] || n.label)}</div><h3>${esc(nodeName(n))}</h3>` +
    (props.length ? '<table class="kvt">' + props.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(typeof v === 'string' ? v : JSON.stringify(v))}</td></tr>`).join('') + '</table>' : '') + '</div><div class="col">' +
    (outE.length ? `<h4>${esc(UI.t('onto.out'))} ${outE.length}</h4><ul class="rels">${rel(outE, 'out')}</ul>` : '') + (inE.length ? `<h4>${esc(UI.t('onto.in'))} ${inE.length}</h4><ul class="rels">${rel(inE, 'in')}</ul>` : '') + '</div>';
  box.querySelectorAll('[data-go]').forEach(a => a.addEventListener('click', ev => { ev.preventDefault(); ent.sel = a.dataset.go; drawGraph(); renderNodePanel(); const node = [...$('#ontoMap').querySelectorAll('.o-node')].find(n => n.dataset.id === ent.sel); if (node) { const r = node.getBBox(); $('#ontoMap').scrollTo({ left: Math.max(0, r.x - 20), top: Math.max(0, r.y - 60) }); } }));
}
function initOntology() {
  const map = $('#ontoMap'); map.tabIndex = 0; map.setAttribute('role', 'region'); map.setAttribute('aria-label', '지식 지도, 가로와 세로로 이동 가능');
  let width = 0; new ResizeObserver(() => { if (map.clientWidth && map.clientWidth !== width) { width = map.clientWidth; if (ent.graph) drawGraph(); } }).observe(map);
  const chips = $('#ontoLayers');
  ONTO_GROUPS.forEach(gr => {
    const b = el('label', 'chiptoggle', `<input type="checkbox" checked value="${gr.key}"><i style="background:${gr.color}"></i>${esc(gr.title)}`);
    b.querySelector('input').addEventListener('change', ev => { ev.target.checked ? ent.hidden.delete(gr.key) : ent.hidden.add(gr.key); drawGraph(); });
    chips.append(b);
  });
  $('#ontoAsset').addEventListener('change', () => loadGraph(true));
  $('#ontoNs')?.addEventListener('change', () => { ent.sel = null; loadGraph(true); });
  $('#ontoFocus').addEventListener('change', ev => { ent.focus = ev.target.value || null; ent.sel = null; drawGraph(); renderNodePanel(); });
  $('#ontoSearch').addEventListener('input', ev => { ent.search = ev.target.value; drawGraph(); });
  $('#ontoReload').addEventListener('click', () => loadGraph(true));
  document.querySelectorAll('#ontoTpl button').forEach(b => b.addEventListener('click', async () => {
    try { const t = await getJ(API.agent + '/api/ontology/template/' + b.dataset.t); $('#ontoTplText').textContent = t.text; }
    catch (e) { $('#ontoTplText').textContent = UI.t('error.load') + ': ' + e.message; }
  }));
  renderNodePanel();
}

/* ================================================= action candidate cards (shared with hitl.js and instances.js) */
function signNum(v) { return (v > 0 ? '+' : '') + Number(v).toFixed(2); }
function effChip(x, cls) {
  const t = `${x.name} ${x.dir === 1 ? '↑' : '↓'}${x.owner ? ' · ' + x.owner : ''}`;
  return `<span class="${cls}" title="영향 강도 ${x.weight}${x.conds && x.conds.length ? ' · 조건: ' + x.conds.join(', ') : ''}">${esc(t)}</span>`;
}
function ruleChip(r, cls, label) {
  return `<span class="${cls}" title="${esc((r.when || '') + (r.sources && r.sources.length ? ' · 근거 ' + r.sources.join(', ') : ''))}">${esc(label)} · ${esc(UI.idText(r.annotation || UI.name(r.rule)))}</span>`;
}
// FAN_SET=100 → "팬 100 %" (명칭표 "카드"): the action code and target stay in the evidence fold
const ACTION_KO = { FAN_SET: ['팬', ' %'], LOAD_SET: ['부하', ' %'], PUMP_SELECT: ['펌프', ''], WO_CREATE: [null, ''], PR_CREATE: ['구매 요청', ''] };
function actionLabel(a) {
  const spec = ACTION_KO[a.code];
  if (spec && spec[0] === null) return UI.t('workOrder');
  if (spec) return `${spec[0]}${a.value != null ? ' ' + a.value + spec[1] : ''}`;
  return `${a.name || a.code}${a.value != null ? ' ' + a.value : ''}`;
}
function forecastLine(o) {
  const ts1 = (o.forecast || []).find(f => /유온|ts1/i.test(f.name || ''));
  if (ts1 && Number.isFinite(Number(ts1.value))) return `${UI.t('card.forecastTs1')} <b>${Number(ts1.value).toFixed(0)} ℃</b>`;
  const f = (o.forecast || [])[0];
  return f ? `${esc(f.name)} <b>${esc(f.value)}${esc(f.unit || '')}</b>` : '';
}
function forecastContextHtml(c) {
  if (!c) return '';
  if (c.error) return `<p class="neg">${esc(c.error)}</p>`;
  const val = k => Number.isFinite(c.values?.[k]) ? Number(c.values[k]).toFixed(1) : '미확인';
  const inputLabels = { ts1: '현재 유온 ℃', t_amb: '주변 온도 ℃', fan_pct: '팬 %', load_pct: '부하 %', cooler_health: '냉각 성능 비율', leak: '누설 비율', bearing_wear: '베어링 마모', state: '설비 상태', pump: '운전 펌프' };
  return `<p>${esc(c.horizon_s)}초 뒤 유온 ${val('ts1')} ℃ · 압력 ${val('ps1')} bar · 진동 ${val('vs1')} mm/s · 구간 최대 유온 ${val('ts1_peak')} ℃</p>
    <p class="muted">교육용 시뮬레이터 모델입니다. 현재 열화와 주변 온도가 유지된다는 조건의 계산이며 현장 설비의 검증된 예측이 아닙니다. 모델 ${esc(c.model_id)} · 판본 ${esc(c.model_revision)} · 입력 시점 ${esc(UI.dateTime(c.source_t))}</p>
    <p class="muted">${Object.entries(inputLabels).map(([k, label]) => `${label} ${esc(c.inputs?.[k] ?? '미확인')}`).join(' · ')}</p>`;
}
function cardHtml(o, opt = {}) {
  const hasCmd = (o.actions || []).some(a => a.kind === 'command'), hasTx = (o.actions || []).some(a => a.kind !== 'command');
  const uncond = x => !x.conditional, cond = x => x.conditional;
  const sp = o.scoreParts || {};
  const scoreLabels = { bsc: UI.t('score.bsc'), forecast: UI.t('score.forecast'), warn: UI.t('score.warn'), penalty: UI.t('score.penalty'), precedent: UI.t('score.precedent'), delivery: UI.t('score.delivery'), quality: UI.t('score.quality') };
  const ranking = o.rankingEvidence;
  const chips = [o.id === opt.rec ? UI.chipText(UI.t('chip.recommended'), 'accent') : '', hasCmd ? UI.chipText(UI.t('chip.control'), 'neutral') : '', hasTx ? UI.chipText(UI.t('chip.workOrder'), 'warning') : '',
    o.id === opt.chosen ? UI.chipText(UI.t('chip.chosen'), 'success') : '', o.feasible ? '' : UI.chipText(UI.t('chip.excluded'), 'danger')].join('');
  const line = [forecastLine(o), `${esc(UI.t('card.approver'))} <b>${esc((o.approver || {}).name || '–')}</b>`, o.precedent && o.precedent.n ? `${esc(UI.t('card.precedent'))} <b>${o.precedent.n}건 (${Math.round(o.precedent.share * 100)} %)</b> <span class="muted">${esc(UI.t('card.precedentFixed'))}</span>` : ''].filter(Boolean).map(x => `<span>${x}</span>`).join('');
  // A141: 성과 지표 칩 묶음 · 감점/경고 칩 · 절차 번호는 근거 접기 안으로 (화면에는 행동 근거인 점수 · 예상 유온 · 승인 역할 · 제외 사유만)
  const kpiAll = `<span class="hkpi">${(o.gains || []).filter(uncond).map(x => effChip(x, 'pos')).join('')}${(o.losses || []).filter(uncond).map(x => effChip(x, 'neg')).join('')}</span>`;
  const softAll = `${(o.penalties || []).map(v => ruleChip(v, 'soft', `${UI.t('card.penalty')} ${v.penalty}`)).join('')}${(o.warnings || []).map(v => ruleChip(v, 'soft', UI.t('card.warn'))).join('')}`;
  const evidence = `
    ${o.reviewed_choice ? `<p><b>${esc(UI.t('card.baseSop'))}</b> ${esc(o.reviewed_choice.reference_name || o.sopId)} · ${(o.reviewed_choice.reference_actions || []).map(a => esc(actionLabel(a))).join(' · ')}</p>` : ''}
    <dl>${o.sopId ? `<div><dt>${esc(UI.t('card.sop'))}</dt><dd>${esc(o.sopId)}</dd></div>` : ''}
    <div><dt>${esc(UI.t('card.score'))}</dt><dd>${Object.entries(sp).map(([key, value]) => `${esc(scoreLabels[key] || key)} ${Number.isFinite(value) ? signNum(value) : '미확인'}`).join(' · ') || '–'}</dd></div>
    ${(o.gains || []).some(uncond) || (o.losses || []).some(uncond) ? `<div><dt>${esc(UI.t('fold.kpi'))}</dt><dd>${kpiAll}</dd></div>` : ''}
    ${softAll ? `<div><dt>${esc(UI.t('fold.penalty'))}</dt><dd><span class="hmeta">${softAll}</span></dd></div>` : ''}
    <div><dt>${esc(UI.t('skill.actions'))}</dt><dd>${(o.actions || []).map(a => `${esc(actionLabel(a))} <span class="muted">(${esc(a.code)}${a.value != null ? '=' + esc(a.value) : ''}${a.targetName ? ' → ' + esc(a.targetName) : ''})</span>`).join(' · ') || esc(UI.t('card.noAction'))}</dd></div>
    ${(o.forecast || []).length ? `<div><dt>${esc(UI.t('score.forecast'))}</dt><dd>${(o.forecast || []).map(f => `${esc(f.name)} ${esc(f.value)}${esc(f.unit || '')} <span class="muted">(${esc(f.method)})</span>`).join(' · ')}</dd></div>` : ''}
    ${(o.gains || []).some(cond) || (o.losses || []).some(cond) ? `<div><dt>${esc(UI.t('card.expected'))}</dt><dd><span class="hkpi">${(o.gains || []).filter(cond).map(x => effChip(x, 'pos')).join('')}${(o.losses || []).filter(cond).map(x => effChip(x, 'neg')).join('')}</span></dd></div>` : ''}
    ${(o.selectedBy || []).length ? `<div><dt>${esc(UI.t('skill.rules'))}</dt><dd>${(o.selectedBy || []).map(r => `${esc(UI.idText(r.annotation || UI.name(r.rule)))}${(r.sources || []).length ? ` <span class="muted">(${esc(r.sources.join(', '))})</span>` : ''}`).join('<br>')}</dd></div>` : ''}
    ${(o.steps || []).length ? `<div><dt>${esc(UI.t('card.steps'))}</dt><dd><ol style="margin:0;padding-left:18px">${(o.steps || []).map(s => `<li>${esc(UI.idText(s.text))}${s.manual ? ` <span class="muted" title="${esc(s.manual.excerpt || '')}">[${esc(s.manual.ref)} ${esc(s.manual.title || '')}]</span>` : ''}</li>`).join('')}</ol></dd></div>` : ''}
    ${o.precedent && o.precedent.reasons && o.precedent.reasons.length ? `<div><dt>${esc(UI.t('card.precedent'))}</dt><dd>${o.precedent.reasons.map(esc).join(' / ')}</dd></div>` : ''}</dl>
    ${o.forecastContext ? UI.fold(esc(UI.t('card.forecastLimits')), forecastContextHtml(o.forecastContext), { cls: 'small' }) : ''}
    ${ranking ? UI.fold(esc(UI.t('card.scoreHow')), `${Object.entries(ranking.policy?.components || {}).map(([key, expr]) => `<div>${esc(scoreLabels[key] || key)}: <code>${esc(expr)}</code> = ${esc(sp[key])}</div>`).join('')}<div class="muted">${esc(ranking.conditionMode || '')}</div>`, { cls: 'small' }) : ''}
    ${(o.tradeoffEvaluation || []).length ? UI.fold(`${esc(UI.t('kpi'))} 경로와 조건 판정 ${o.tradeoffEvaluation.length}건`, o.tradeoffEvaluation.map(p => `<div><b>${esc({ TRUE: '적용', FALSE: '미적용', UNKNOWN: '미확인' }[p.status] || p.status)}</b> ${esc(p.name)} · 강도 ${esc(p.weight)}<br><span class="muted">${esc((p.nodes || []).join(' → '))}</span>${(p.checks || []).filter(c => c.description || c.status !== 'TRUE').map(c => `<p>${esc(c.description)} · ${esc(c.status)}<br>${Object.entries(c.inputs || {}).map(([alias, v]) => `${esc(alias)}: ${esc(v.source === 'forecast' ? '후보 예측' : '현재 사실')} ${esc(v.variable)} = ${esc(v.value ?? '미확인')}`).join(' · ')}${c.error ? `<br>${esc(c.error)}` : ''}</p>`).join('')}</div>`).join(''), { cls: 'small' }) : ''}`;
  const head = `<span class="hrank">${o.feasible ? o.rank : '–'}</span>
    <span class="hbody"><span class="htitle">${esc(UI.idText(o.name))} ${chips}</span>
      ${o.description ? `<span class="hsub">${esc(UI.idText(o.description))}</span>` : ''}
      <span class="hbar"><i style="width:${Math.min(100, Math.round(Math.abs(o.score || 0) / (opt.maxAbs || 1) * 100))}%" class="${(o.score || 0) >= 0 ? 'pos' : 'neg'}"></i><b class="num">${esc(UI.t('card.score'))} ${signNum(o.score || 0)}</b></span>
      <span class="hline">${line}</span>
      ${(o.violations || []).length ? `<span class="hmeta">${ruleChip(o.violations[0], 'hard', UI.t('chip.excluded'))}${o.violations.length > 1 ? `<span class="muted">+${o.violations.length - 1}</span>` : ''}</span>` : ''}
      ${o.money && window.hydWhatif ? hydWhatif.moneyFold(o.money) : ''}
      ${UI.fold(esc(UI.t('card.evidence')), ((o.violations || []).length > 1 ? `<p><b>${esc(UI.t('fold.violations'))}</b> <span class="hmeta">${o.violations.map(v => ruleChip(v, 'hard', UI.t('chip.excluded'))).join('')}</span></p>` : '') + evidence, { cls: 'small' })}
    </span>`;
  if (!opt.selectable) return `<div class="hopt ${o.feasible ? '' : 'out'} ${o.id === opt.rec ? 'rec' : ''} ${o.id === opt.chosen ? 'chosen' : ''}">${'<span></span>' + head}</div>`;
  return `<label class="hopt ${o.feasible ? '' : 'out'} ${opt.selected ? 'sel' : ''} ${o.id === opt.rec ? 'rec' : ''} ${o.id === opt.chosen ? 'chosen' : ''}">
    <input type="radio" name="${opt.name || 'hopt'}" value="${esc(o.id)}" ${opt.selected ? 'checked' : ''} ${(o.feasible || opt.reviewable) && opt.pending ? '' : 'disabled'}>${head}</label>`;
}
function reviewMatches(review, decision, option, parameters, scope = {}) {
  const saved = review?.snapshot?.options?.[0]?.reviewed_choice?.parameters;
  return !!(review?.id && review?.snapshot?.id === decision && review?.snapshot?.options?.[0]?.id === option
    && review?.scope?.decision === decision && review?.scope?.option === option && saved
    && Object.entries(scope).every(([key, value]) => review.scope[key] === value)
    && Object.keys(saved).length === Object.keys(parameters).length
    && Object.entries(parameters).every(([key, value]) => saved[key] === value));
}
// shared "사건 / 선택 / 사유·담당" form pieces (UIUX_PLAN §1.3, R5 · R6)
function rangeField(id, label, a, value) {
  return `<div class="field range"><label for="${id}">${esc(label)}</label><div class="range-row"><input type="range" id="${id}" min="${a.min ?? 0}" max="${a.max ?? 100}" value="${esc(value)}"><output for="${id}">${esc(value)} %</output></div></div>`;
}
function whoFields(prefix, form, roles, { roleHint = UI.t('form.hint.role'), reasonHint = UI.t('form.hint.reason') } = {}) {
  const asMe = window.hydInbox?.whoFields(prefix, form, roles, { reasonHint });   // U5: "나"를 골랐으면 승인자 = 나, 역할 = 내 역할(서버가 다시 검사)
  if (asMe) return asMe;
  return UI.section(UI.t('form.section.who'),
    UI.field({ label: UI.t('form.by'), required: true, input: `<input id="${prefix}By" value="${esc(form.by || '')}">` }) +
    UI.field({ label: UI.t('form.role'), required: true, hint: roleHint, input: `<select id="${prefix}Role">${roles.map(([id, r]) => `<option value="${esc(id)}" ${id === form.role ? 'selected' : ''}>${esc(r.name)}</option>`).join('')}</select>` }) +
    UI.field({ label: UI.t('form.reason'), cls: 'wide', hint: reasonHint, input: `<textarea id="${prefix}Reason" rows="2">${esc(form.reason || '')}</textarea>` }));
}
window.hydCards = { cardHtml, reviewMatches, rangeField, whoFields, actionLabel };

/* ================================================= 조치 판단 규칙 */
async function loadDecisionView() {
  const sel = $('#decPattern');
  if (!$('#decResult').innerHTML) $('#decResult').innerHTML = UI.empty(UI.t('dec.empty'));
  if (sel.options.length) return;
  const pats = await loadPatterns();
  pats.forEach(p => sel.append(new Option(`${p.name}${p.failureModes && p.failureModes.length ? ' → ' + p.failureModes.join(', ') : ''}`, p.code)));
  if (!pats.length) $('#decResult').innerHTML = UI.empty(UI.t('dec.noPatterns'));
}
async function runDecision() {
  if (ent.busy) return; ent.busy = true;
  ent.result = null; // A failed new request must not retain the previous successful judgment.
  const b = $('#decRun'); b.disabled = true; b.textContent = UI.t('btn.running');
  const facts = {};
  if ($('#decMode').value) facts.plc_mode = $('#decMode').value;
  if ($('#decState').value) facts.plc_state = $('#decState').value;
  if ($('#decFan').value !== '') facts.fan100_hours = Number($('#decFan').value);
  if ($('#decStandby').value) facts.standby_ready = $('#decStandby').value === 'true';
  $('#decResult').innerHTML = UI.empty(UI.t('dec.loading'));
  try { ent.result = await postJ(API.agent + '/api/agent/decide', { asset: $('#decAsset').value, pattern: $('#decPattern').value, facts }); renderDecision(); }
  catch (e) { $('#decResult').innerHTML = UI.empty(UI.t('dec.failed'), e.message); }
  finally { ent.busy = false; b.disabled = false; b.textContent = UI.t('btn.run'); }
}
// first sentence = up to a period followed by whitespace or the end ("점수 3.87" must not cut)
const firstSentence = text => { const m = String(text || '').match(/^[\s\S]*?[.。](?=\s|$)/); return m ? m[0] : String(text || ''); };
function summaryBlock(raw) {
  const text = UI.idText(raw);                       // A141: 레거시 판단의 fm:/cause: id → 이름
  const first = firstSentence(text), rest = String(text || '').slice(first.length).trim();
  return `<div class="summary prose"><p style="margin:0">${esc(first)}</p>${rest ? UI.fold(esc(UI.t('dec.summaryMore')), `<p style="margin:0">${esc(rest)}</p>`, { cls: 'small' }) : ''}</div>`;
}
function renderDecision() {
  const d = ent.result; const box = $('#decResult');
  if (!d || !d.result) { box.innerHTML = UI.empty(UI.status(d && d.status) || UI.t('dec.failed'), (d && d.error) || ''); return; }
  const r = d.result, opts = r.options || [];
  const maxAbs = Math.max(1, ...opts.map(o => Math.abs(o.score || 0)));
  // A141: 판단 시각 · id 는 상세 정보 접기로
  let html = `<div class="detail-head" style="margin-top:var(--s6)"><div class="row"><h2>${esc(UI.idText((d.scenario || {}).name || ''))}</h2>${UI.chip(d.status)}</div><div class="sub">${esc(d.asset || '')}</div></div>`;
  html += summaryBlock(r.explanation);
  if (d.moneyError) html += `<p class="neg" role="status">손익(원)을 계산하지 못했습니다: ${esc(d.moneyError)}</p>`;
  html += UI.metaFold([[UI.t('inst.stepTable.when'), esc(UI.dateTime(d.created))], ['ID', `<span class="mono">${esc(d.id)}</span>`]]);
  // 원인: 1위 큰 글씨 + 고장 유형 칩 + 증거, 2위 이하 접기 (C2)
  const causes = d.causes || [];
  const evidenceHtml = c => (c.evidence || []).map(e => { const unknown = e.status === 'UNKNOWN' || e.passed == null || e.value == null || !!e.error;
    return `<div class="kv-line"><span class="${unknown ? 'muted' : e.passed ? 'pos' : 'neg'}">${esc(e.name)}</span> = ${esc(fmt(e.value, 3))}${unknown ? ` · ${esc(UI.t('inc.unknown'))}` : ''}</div>`; }).join('') || `<span class="muted">${esc(UI.t('inc.noEvidence'))}</span>`;
  if (causes.length) {
    const top = causes[0];
    html += `<h2 class="sec">${esc(UI.t('dec.cause'))}</h2>` + UI.card({ title: esc(UI.idText(top.name)), chips: UI.chipText(UI.t('dec.causeTop'), 'accent') + (top.failureMode ? UI.chipText(UI.idText(top.failureMode), 'neutral') : ''), value: `<span class="kv">${esc(UI.t('card.score'))} ${esc(top.score)}</span>`, body: evidenceHtml(top) +
      (causes.length > 1 ? UI.fold(`${esc(UI.t('dec.causeMore'))} ${causes.length - 1}`, causes.slice(1).map(c => `<div style="margin-bottom:var(--s2)"><b>${esc(UI.idText(c.name))}</b> · ${esc(UI.t('card.score'))} ${esc(c.score)}${c.failureMode ? ' · ' + esc(UI.idText(c.failureMode)) : ''}${evidenceHtml(c)}</div>`).join(''), { cls: 'small' }) : '') });
  }
  html += `<h2 class="sec">${esc(UI.t('dec.candidates'))} <small>${opts.length}</small></h2><div class="hitl-opts">` + opts.map(o => cardHtml(o, { rec: r.recommended, maxAbs })).join('') + '</div>';
  html += '<div class="stack-list" style="margin-top:var(--s4)">';
  if (r.rankRule) html += UI.fold(esc(UI.t('card.scoreHow')), `<p style="margin:0">${esc(r.rankRule.annotation || '')}</p>`);
  // 적용한 규칙 (D5: folded; F2: fired rows first, rule id and condition inside the row)
  const tr = (r.trace || []).slice().sort((a, b) => (b.fired ? 1 : 0) - (a.fired ? 1 : 0) || (b.skill ? 1 : 0) - (a.skill ? 1 : 0));
  const target = t => t.skill ? ((opts.find(o => o.id === t.skill) || {}).name || t.skill) : '';
  html += UI.fold(`${esc(UI.t('dec.rules'))} <span class="chip tone-neutral sm">${tr.length}</span>`,
    `<table class="compact-table"><thead><tr><th>${esc(UI.t('dec.col.rule'))}</th><th>${esc(UI.t('dec.col.target'))}</th><th>${esc(UI.t('dec.col.result'))}</th></tr></thead><tbody>` +
    tr.map(t => `<tr class="${t.fired ? 'rec' : ''}"><td>${esc(UI.idText(t.annotation || UI.name(t.rule)))}<br><small class="muted">${esc(t.decision === 'dec:action-candidates' ? UI.t('dec.ruleSelect') : UI.t('dec.ruleCompliance'))}</small>${UI.fold(esc(UI.t('raw')), `<code>${esc(t.rule)}</code> <code>${esc(t.when || '')}</code>`, { cls: 'small' })}</td><td>${esc(target(t))}</td>` +
      `<td>${t.fired ? `<b>${esc(UI.t('dec.fired'))}</b>` : (t.unknown && t.unknown.length ? `<span class="muted">${esc(UI.t('dec.noFact'))}: ${esc(t.unknown.join(', '))}</span>` : esc(UI.t('dec.notApplicable')))}</td></tr>`).join('') + '</tbody></table>');
  html += UI.fold(`${esc(UI.t('dec.inputs'))} <span class="chip tone-neutral sm">${(d.provenance || []).length}</span>`,
    `<table class="compact-table"><thead><tr><th>${esc(UI.t('dec.col.input'))}</th><th>${esc(UI.t('dec.col.source'))}</th><th>${esc(UI.t('dec.col.value'))}</th><th>${esc(UI.t('dec.col.how'))}</th></tr></thead><tbody>` +
    (d.provenance || []).map(p => `<tr><td>${esc(p.name)}</td><td>${esc(p.sourceName || p.source)}</td><td>${p.error ? '<span class="neg">' + esc(p.error) + '</span>' : esc(JSON.stringify(p.value))}</td><td class="muted">${esc(p.how || '')}</td></tr>`).join('') + '</tbody></table>');
  html += UI.fold(esc(UI.t('dec.trace')), traceHtml({ id: d.id, status: d.status, started: d.created, steps: d.steps || [] })) + '</div>';
  box.innerHTML = html;
}
$('#decRun').addEventListener('click', runDecision);

/* ================================================= 승인과 실행 */
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
  const sig = JSON.stringify([ent.decisions, ent.decSel, ent.decisionsError, ent.decShown, UI.namesVersion]);
  if (list.dataset.sig !== sig) {
    list.dataset.sig = sig;
    const focused = list.contains(document.activeElement) ? document.activeElement.dataset.itemId : null;
    const scroll = list.scrollTop;
    list.innerHTML = ent.decisions.length ? '' : UI.empty(UI.t('proc.empty'), UI.t('proc.emptySub'), 'compact');
    if (ent.decisionsError) list.innerHTML = `<div class="neg" role="status">${esc(UI.t('proc.listError'))}</div>`;
    const paged = UI.page(ent.decisions, ent.decShown, d => d.id === ent.decSel);
    for (const d of paged.rows) {
      const it = el('div', 'item' + (d.id === ent.decSel ? ' sel' : ''));
      keyboardItem(it);
      it.dataset.itemId = d.id;
      it.innerHTML = `<div class="row"><strong>${esc(UI.idText((d.scenario || {}).name || ''))}</strong>${UI.chip(d.state)}</div>` +
        `<span class="sub">${esc(d.asset || '')} · ${esc(UI.dateTime(d.created))}${(d.origin || {}).kind !== 'alert' ? ' · ' + esc(UI.t('proc.manual')) : ''}${d.override ? ' · ' + esc(UI.t('proc.override')) : ''}</span>`;
      it.addEventListener('click', async () => {
        if (ent.decSel === d.id && ent.decDetail) { UI.revealDetail($('#decDetail')); return; }
        ent.decSel = d.id; ent.decDetail = null; ent.form.msg = ''; ent.form.option = null; ent.lastDetailSig = null;
        $('#decDetail').innerHTML = UI.empty(UI.t('loading'));
        await refreshProcess();
        if (ent.decSel === d.id) UI.revealDetail($('#decDetail'));
      });
      list.append(it);
    }
    if (paged.rest) { const more = el('div', '', UI.moreButton(paged.rest)); more.querySelector('button').addEventListener('click', () => { ent.decShown += UI.PAGE; list.dataset.sig = ''; renderProcess(); }); list.append(more); }
    if (focused) [...list.children].find(e => e.dataset.itemId === focused)?.focus({ preventScroll: true });
    list.scrollTop = scroll;
  }
  renderDecisionApproval();
  renderSystems();
}
function renderDecisionApproval() {
  const box = $('#decDetail'); const d = ent.decDetail;
  if (!d) { ent.lastDetailSig = null; box.innerHTML = UI.empty(UI.t('proc.select')); return; }
  // the 2.5 s refresh must not wipe what the approver is typing or selecting: redraw only when the decision changed
  const sig = d.id + '|' + d.state + '|' + (d.executions || []).length + '|' + (d.history || []).length + '|' + UI.namesVersion;
  if (sig === ent.lastDetailSig && box.querySelector('.hitl-opts')) return;
  ent.lastDetailSig = sig;
  const roles = Object.entries(d.roles || {}).sort((a, b) => a[1].level - b[1].level);
  const pending = d.state === 'PENDING_APPROVAL';
  const opts = d.options || [];
  const maxAbs = Math.max(1, ...opts.map(o => Math.abs(o.score || 0)));
  if (!ent.form.option || !opts.some(o => o.id === ent.form.option)) ent.form.option = d.recommended || (opts.find(o => o.feasible) || opts[0] || {}).id;
  if (!ent.form.role) ent.form.role = ((opts.find(o => o.id === ent.form.option) || {}).approver || {}).id || (roles[0] || [''])[0];
  const sc = d.scenario || {};
  // A141: 제출 시각 · id · 사건 정보(설비 · 고장 유형 · 원인)는 접기로. 화면에는 제목 · 상태 · 한 줄 요약 · 선택 카드 · 사유 · 승인 버튼만
  let html = `<div class="detail-head"><div class="row"><h2>${esc(UI.idText(sc.name || ''))}</h2>${UI.chip(d.state)}</div><div class="sub">${esc(d.asset || '')}${d.approvedBy ? ` · ${esc(UI.t('inc.approvedBy'))} ${esc(d.approvedBy)}` : ''}</div></div>`;
  html += summaryBlock(d.explanation);
  html += UI.metaFold([[UI.t('dec.asset'), esc(d.asset || '')], ['고장 유형', esc(UI.idText(sc.failureMode || ''))], [UI.t('dec.cause'), esc(UI.idText(sc.cause || ''))], [UI.t('proc.submitted'), esc(UI.dateTime(d.created))], ['ID', `<span class="mono">${esc(d.id)}</span>`]], 'fold.case');
  if (pending) {
    html += `<div class="form">` +
      UI.section(UI.t('form.section.choice'), `<div class="hitl-opts wide">${opts.map(o => cardHtml(o, { rec: d.recommended, chosen: d.chosen, selectable: true, selected: ent.form.option === o.id, pending: true, maxAbs, name: 'decOpt' })).join('')}</div>`) +
      whoFields('dec', ent.form, roles) +
      UI.actions(`<button class="btn outline" id="decReject">${esc(UI.t('btn.reject'))}</button><button class="btn primary" id="decApprove">${esc(UI.t('btn.approve'))}</button>`, ent.form.msg || '') + '</div>';
  } else {
    html += `<h3 style="font-size:14px;margin:var(--s4) 0 var(--s2)">${esc(UI.t('decisions'))}</h3><div class="hitl-opts">` + opts.map(o => cardHtml(o, { rec: d.recommended, chosen: d.chosen, maxAbs })).join('') + '</div>';
  }
  if ((d.executions || []).length) html += `<h3 style="font-size:14px;margin:var(--s4) 0 var(--s2)">${esc(UI.t('proc.executions'))}</h3><div class="cards two">` +
    d.executions.map(x => UI.card({ title: esc(UI.who(x.system) + (x.code ? ' · ' + actionLabel({ code: x.code }) : '')), chips: UI.chip(x.status), value: x.ref ? `<span class="kv mono">${esc(x.ref)}</span>` : '', sub: esc(x.detail || ''), cls: 'soft' })).join('') + '</div>';
  html += `<div style="margin-top:var(--s4)">` + UI.fold(`${esc(UI.t('proc.history'))} <span class="chip tone-neutral sm">${(d.history || []).length}</span>`, '<div class="audit">' + (d.history || []).map(h => UI.eventRecord({ time: h.t, name: h.state, actor: h.by, detail: h.reason || '', raw: h })).join('') + '</div>') + '</div>';
  box.innerHTML = html;
  const by = $('#decBy'), role = $('#decRole'), reason = $('#decReason');
  if (by) by.addEventListener('input', () => ent.form.by = by.value);
  if (role) { ent.form.role = role.value; role.addEventListener('change', () => { ent.form.role = role.value; ent.form.msg = ''; }); }
  if (reason) reason.addEventListener('input', () => ent.form.reason = reason.value);
  box.querySelectorAll('input[name=decOpt]').forEach(r => r.addEventListener('change', () => { ent.form.option = r.value; const o = opts.find(x => x.id === r.value); if (o && o.approver) ent.form.role = o.approver.id; ent.lastDetailSig = null; renderDecisionApproval(); }));
  const msg = t => { const m = box.querySelector('.form-msg'); if (m) m.textContent = t; else if (t) { ent.form.msg = t; ent.lastDetailSig = null; renderDecisionApproval(); } };
  const ap = $('#decApprove'); if (ap) ap.addEventListener('click', async () => {
    const controls = [...box.querySelectorAll('#decApprove,#decReject')];
    controls.forEach(c => c.disabled = true); ap.textContent = UI.t('proc.approving');
    try { ent.form.msg = ''; await postJ(API.process + `/api/decisions/${d.id}/approve`, { option: ent.form.option, by: ($('#decBy')?.value ?? ent.form.by) || '승인자', role: $('#decRole').value }); await refreshProcess(); }
    catch (e) { ent.form.msg = e.message; if (ent.decSel === d.id) msg(e.message); }
    finally { controls.forEach(c => c.disabled = false); ap.textContent = UI.t('btn.approve'); }
  });
  const rj = $('#decReject'); if (rj) rj.addEventListener('click', async () => {
    if (!$('#decReason').value.trim()) { ent.form.msg = UI.t('form.err.reason'); msg(ent.form.msg); $('#decReason').focus(); return; }
    const controls = [...box.querySelectorAll('#decApprove,#decReject')];
    controls.forEach(c => c.disabled = true); rj.textContent = UI.t('proc.rejecting');
    try { await postJ(API.process + `/api/decisions/${d.id}/reject`, { by: $('#decBy')?.value ?? ent.form.by, reason: $('#decReason').value }); await refreshProcess(); }
    catch (e) { if (ent.decSel === d.id) msg(e.message); }
    finally { controls.forEach(c => c.disabled = false); rj.textContent = UI.t('btn.reject'); }
  });
}
function renderSystems() {
  const box = $('#sysBoards'); const s = ent.entState;
  if (!s) { box.innerHTML = UI.empty(UI.t('proc.noEnt'), '', 'compact'); return; }
  const t = (rows, cols, labels) => rows.length ? '<div class="table-scroll" tabindex="0"><table><thead><tr>' + labels.map(x => `<th>${esc(x)}</th>`).join('') + '</tr></thead><tbody>' + rows.slice(0, 6).map(r => '<tr>' + cols.map(c => `<td>${esc(r[c] ?? '–')}</td>`).join('') + '</tr>').join('') + '</tbody></table></div>' : UI.empty(UI.t('proc.noChange'), '', 'compact');
  const boards = [
    ['MES', t(s.mes.orders.map(o => ({ ...o, where: o.moved_from ? `${o.moved_from} → ${o.asset}` : o.asset })), ['order_id', 'where', 'due_in_h'], ['생산오더', '설비', '납기까지 (시간)'])],
    ['CMMS', t(s.cmms.work_orders, ['id', 'asset', 'task', 'window'], ['번호', '설비', '작업', '정비 시점'])],
    ['ERP', t([...s.erp.purchase_requests.map(p => ({ a: p.id, b: p.supplierName, c: p.status })), ...s.erp.shipments.map(x => ({ a: x.id, b: `${x.item} ${x.qty}개`, c: x.from }))], ['a', 'b', 'c'], ['번호', '대상', '상태 · 출고처'])],
    // A098: the enterprise state exposes qms.lot_dispositions and ems.ems_actions (A086 schema)
    ['QMS', t((s.qms?.lot_dispositions || []).map(h => ({ a: h.lot || h.lot_id || h.id, b: h.disposition || h.status || '' })), ['a', 'b'], ['로트', '처분'])],
    ['EMS', t((s.ems?.ems_actions || []).map(x => ({ action: x.action || x.description || x.kind || JSON.stringify(x).slice(0, 80) })), ['action'], ['실행 내용'])],
  ];
  box.innerHTML = boards.map(([sys, body]) => `<div class="board"><header><b>${esc(UI.t('sys.' + sys))}</b><span>${esc(sys)}</span></header>${body}</div>`).join('');
  $('#txList').innerHTML = ent.tx.length ? ent.tx.slice(0, 12).map(x => UI.eventRecord({ time: x.t, name: UI.who(x.system), actor: x.by, detail: x.detail, raw: x, extra: txDiffFold(x) })).join('') : `<div class="muted">${esc(UI.t('proc.noTx'))}</div>`;
}
// A147 (DECISIONS 97 후속): 거래가 바꾼 행의 변경 전·후 — 바뀐 항목만, 기본 닫힘. 기록이 없는 거래(before/after 둘 다 없음)는 접기도 없다
function txDiffFold(x) {
  const b = x.before || null, a = x.after || null;
  if (!b && !a) return '';
  const show = v => v == null || v === '' ? '–' : typeof v === 'object' ? JSON.stringify(v) : /^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(String(v)) ? UI.dateTime(v) : String(v);
  const keys = [...new Set([...Object.keys(b || {}), ...Object.keys(a || {})])].filter(k => JSON.stringify((b || {})[k] ?? null) !== JSON.stringify((a || {})[k] ?? null));
  const body = !keys.length ? `<p class="muted">${esc(UI.t('tx.noDiff'))}</p>`
    : `${b ? '' : `<p class="muted">${esc(UI.t('tx.created'))}</p>`}<table class="compact-table"><thead><tr><th>${esc(UI.t('tx.col.field'))}</th><th>${esc(UI.t('tx.col.before'))}</th><th>${esc(UI.t('tx.col.after'))}</th></tr></thead><tbody>` +
      keys.map(k => `<tr><td class="mono">${esc(k)}</td><td>${esc(show((b || {})[k]))}</td><td><b>${esc(show((a || {})[k]))}</b></td></tr>`).join('') + '</tbody></table>';
  return UI.fold(`${esc(UI.t('tx.beforeAfter'))} <span class="chip tone-neutral sm">${keys.length}</span>`, body, { cls: 'small' });
}

initOntology();
setInterval(() => { if (state.tab === 'process') refreshProcess(); }, 2500);
window.hydApp.selectTab = selectTab;          // the recorder and ?present=1 hooks must see the loaders too
window.hydEnt = { ent, runDecision, loadGraph, refreshProcess, loadDecisionView, renderDecision };
