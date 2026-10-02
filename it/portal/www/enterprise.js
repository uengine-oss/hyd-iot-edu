/* L7 ~ L9 views: 온톨로지 지식 지도 · 조치 판단 규칙 (DMN · BSC) · 업무 프로세스·시스템 연계 — ontology v2.
   Loaded after app.js and reuses its helpers ($, el, esc, fmt, getJ, postJ, state, selectTab).
   Data: agent (8091) for the ontology and the decision engine, process (8080) for approval, enterprise-sim (8095) for ERP/MES/…  */
API.ent = P(8095);

// columns of the knowledge map = layers of the ontology v2 schema (it/neo4j/v2/schema.json)
const ONTO_GROUPS = [
  { key: 'value', title: '전략목표 (BSC)', color: '#6d28d9', labels: ['Perspective', 'Objective', 'Measure'] },
  { key: 'process', title: '프로세스 (BPMN)', color: '#1d4ed8', labels: ['Process', 'Event', 'Task', 'Gateway'] },
  { key: 'resource', title: '리소스', color: '#6b7280', labels: ['OrgUnit', 'Role', 'System', 'Asset', 'Component', 'Sensor', 'Actuator', 'StateVariable', 'Part', 'Supplier'] },
  { key: 'diagnosis', title: '설비 진단 (ISO 13374)', color: '#b42318', labels: ['AnomalyPattern', 'Symptom', 'FailureMode', 'Cause', 'Evidence', 'ManualSection'] },
  { key: 'skill', title: '스킬 = SOP · 규칙 (DMN)', color: '#0f766e', labels: ['Skill', 'Step', 'Action', 'Decision', 'DecisionTable', 'Rule', 'InputData', 'KnowledgeSource'] },
  { key: 'external', title: '외부 변수 · 예측 · 사례', color: '#9a6700', labels: ['ExternalVariable', 'Forecast', 'Incident', 'DecisionCase'] },
];
const LABEL_KO = { Perspective: 'BSC 관점', Objective: '전략 목표 (조직 목표)', Measure: '성과 지표', Process: '프로세스', Event: '이벤트', Task: '작업', Gateway: '게이트웨이',
  OrgUnit: '부서', Role: '역할', System: '시스템', Asset: '설비', Component: '구성 요소', Sensor: '센서', Actuator: '구동기', StateVariable: '상태 변수',
  Part: '부품', Supplier: '공급사', AnomalyPattern: '이상 패턴', Symptom: '증상', FailureMode: '고장 유형', Cause: '원인', Evidence: '증거', ManualSection: '매뉴얼 절',
  Skill: '조치 방법 (스킬 = SOP)', Step: 'SOP 단계', Action: '원자 조치', Decision: 'DMN 판단', DecisionTable: '결정표', Rule: '규칙', InputData: '입력 데이터',
  KnowledgeSource: '지식 출처', ExternalVariable: '외부 변수', Forecast: '예측', Incident: '사건', DecisionCase: '판단 사례' };
const RELATION_KO = {
  IN_PERSPECTIVE: '속한 관점', SUPPORTS: '받쳐 주는 목표', MEASURES: '측정하는 목표', OWNED_BY: '담당 부서', INFLUENCES: '영향 (+/−)',
  ACHIEVES: '달성하는 조직 목표', HAS_NODE: '흐름 노드', SEQUENCE_FLOW: '다음 단계', ATTACHED_TO: '경계 이벤트', PERFORMED_BY: '수행자', READS: '읽는 데이터',
  PRODUCES: '만드는 데이터', INVOKES: '부르는 판단', EXECUTES: '실행하는 스킬', CORRELATES: '시작시키는 경보', ACTS_ON: '대상 설비',
  MEMBER_OF: '소속 부서', HAS_COMPONENT: '구성 요소', MONITORED_BY: '관측 센서', ACTUATED_BY: '구동 장치', OBSERVES: '읽는 상태 변수', MANIPULATES: '바꾸는 변수',
  USES_PART: '교체 부품', SUPPLIED_BY: '공급사', HAS_SKILL: '수행 가능한 스킬', SOURCED_FROM: '데이터 출처', REPRESENTS: '나타내는 변수 · 지표',
  DETECTS: '감지 증상', OBSERVED_BY: '관측 센서', INDICATES: '나타내는 고장', OCCURS_IN: '발생 위치', LEADS_TO: '이어지는 고장', CAUSES: '일으키는 고장',
  INVOLVES_PART: '관련 부품', DISTURBS: '움직이는 외란', EVIDENCED_BY: '확증 근거', MITIGATED_BY: '즉시 완화 SOP', REMEDIED_BY: '근본 조치 SOP',
  ADDRESSES: '해당 원인', HAS_STEP: 'SOP 단계', REFERS_TO: '근거 매뉴얼', PART_OF: '속한 문서', CONSISTS_OF: '원자 조치', TARGETS: '조치 대상',
  APPROVED_BY: '승인 역할', AFFECTS: '움직이는 변수 · 지표', REQUIRES_INPUT: '필요한 입력', REQUIRES_DECISION: '먼저 내릴 판단', IMPLEMENTED_BY: '결정표',
  GOVERNED_BY: '통제 출처', HAS_RULE: '규칙', TESTS: '임계값 검사', OUTPUTS: '고르는 결과', APPLIES_TO: '적용 대상 스킬', PENALIZES: '감점 지표',
  DERIVED_FROM: '근거 출처', FORECASTS: '예측 대상', ASSUMES: '가정한 스킬', GIVEN: '가정한 원인', ON_ASSET: '설비', RAISED_BY: '경보 패턴',
  DIAGNOSED_AS: '판정 원인', INSTANCE_OF: '판단 정의', CHOSE: '고른 스킬', DECIDED_BY: '판단한 역할', FOR_INCIDENT: '대상 사건',
};
const ent = { graph: null, graphAsset: null, sel: null, hidden: new Set(), focus: null, search: '', patterns: null, result: null,
  decisions: [], decSel: null, decDetail: null, entState: null, tx: [], roles: null, busy: false,
  form: { by: '홍길동', role: null, reason: '' }, lastDetailSig: null };

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
  const pats = await loadPatterns();
  const sel = $('#ontoFocus');
  if (sel.options.length <= 1) pats.forEach(p => sel.append(new Option(`${p.name} (${p.code})`, p.id)));
  drawGraph();
}
function groupOf(label) { return ONTO_GROUPS.findIndex(g => g.labels.includes(label)); }
function focusSet() {
  // the path the agent walks for one anomaly pattern: pattern → symptoms → failure modes → causes · evidence → SOP skills
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
      for (const s of add(walk(fm, ['MITIGATED_BY', 'REMEDIED_BY']))) {
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
  let svg = `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="온톨로지 지식 지도">`;
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
    // Local selection highlights direct relations; a scenario keeps its broader
    // path visible as context. Dimming never removes nodes or navigation links.
    const cls = hot ? 'o-edge hot' : inFocus ? 'o-edge focus' : (focus || ent.sel) ? 'o-edge dim' : 'o-edge';
    const nm = id => g.nodes.find(n => n.id === id)?.name || id;
    const path = `<path d="${d}" class="${cls}"><title>${esc(nm(e.from))} → ${esc(RELATION_KO[e.type] || e.type)} → ${esc(nm(e.to))} (${esc(e.type)})</title></path>`;
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
    const label = String(n.name || n.id); const short = label;
    svg += `<g class="${cls}" data-id="${esc(id)}" tabindex="0"><rect x="${p.x}" y="${p.y}" width="${BOX}" height="${H}" rx="4" style="--c:${color}"/>` +
      `<text x="${p.x + 7}" y="${p.y + 17}">${esc(short)}</text><title>${esc(LABEL_KO[n.label] || n.label)} · ${esc(n.id)}\n${esc(label)}</title></g>`;
  }
  svg += '</svg>';
  const box = $('#ontoMap'); const scroll = [box.scrollLeft,box.scrollTop]; box.innerHTML = svg; box.scrollLeft=scroll[0]; box.scrollTop=scroll[1];
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
  const skills = counts.Skill || 0, rules = counts.Rule || 0, kpis = counts.Measure || 0;
  const matches = [...box.querySelectorAll('.o-node.match')];
  $('#ontoStats').innerHTML = `노드 ${g.nodes.length}개 · 관계 ${g.edges.length}개 · 조치 방법(SOP) <b>${skills}</b> · DMN 규칙 <b>${rules}</b> · BSC 성과 지표 <b>${kpis}</b>` + (focus ? ` · 강조 경로 ${focus.size}개 노드` : '') + (q ? ` · 검색 결과 ${matches.length}개` : '') + (box.scrollWidth > box.clientWidth ? ' · 지도 안에서 좌우로 이동' : '');
  if (q && matches.length) { const r = matches[0].getBBox(); box.scrollLeft = Math.max(0, r.x - 20); box.scrollTop = Math.max(0, r.y - 60); }
  renderNodePanel();
}
function renderNodePanel() {
  const box = $('#ontoNode');
  const g = ent.graph; if (!g || !ent.sel) { box.innerHTML = '<div class="muted">항목을 누르면 직접 연결된 관계를 강조합니다. 연결된 이름을 눌러 다음 지식으로 이동하세요.</div>'; return; }
  const n = g.nodes.find(x => x.id === ent.sel); if (!n) return;
  const props = Object.entries(n.props || {}).filter(([k]) => !['id', 'name'].includes(k));
  const outE = g.edges.filter(e => e.from === n.id), inE = g.edges.filter(e => e.to === n.id);
  const nm = id => { const x = g.nodes.find(y => y.id === id); return x ? x.name : id; };
  const rel = (list, dir) => list.map(e => { const other = dir === 'out' ? e.to : e.from; return `<li><span title="${esc(e.type)}">${dir === 'out' ? '→' : '←'} ${esc(RELATION_KO[e.type] || e.type)}</span> <a href="#" data-go="${esc(other)}">${esc(nm(other))}</a></li>`; }).join('');
  box.innerHTML = `<div class="col"><div class="o-kind">${esc(LABEL_KO[n.label] || n.label)} <span class="muted">(${esc(n.label)})</span></div><h3>${esc(n.name)}</h3><div class="muted mono">${esc(n.id)}</div>` +
    (props.length ? '<table class="kvt">' + props.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(typeof v === 'string' ? v : JSON.stringify(v))}</td></tr>`).join('') + '</table>' : '') + '</div><div class="col">' +
    (outE.length ? `<h4>나가는 관계 ${outE.length}</h4><ul class="rels">${rel(outE, 'out')}</ul>` : '') + (inE.length ? `<h4>들어오는 관계 ${inE.length}</h4><ul class="rels">${rel(inE, 'in')}</ul>` : '') + '</div>';
  box.querySelectorAll('[data-go]').forEach(a => a.addEventListener('click', ev => { ev.preventDefault(); ent.sel = a.dataset.go; drawGraph(); renderNodePanel(); const node=[...$('#ontoMap').querySelectorAll('.o-node')].find(n=>n.dataset.id===ent.sel); if(node) { const r=node.getBBox(); $('#ontoMap').scrollTo({left:Math.max(0,r.x-20),top:Math.max(0,r.y-60)}); } }));
}
function initOntology() {
  const map = $('#ontoMap'); map.tabIndex=0; map.setAttribute('role','region'); map.setAttribute('aria-label','지식 지도, 가로와 세로로 이동 가능');
  let width=0; new ResizeObserver(() => { if(map.clientWidth && map.clientWidth!==width) {width=map.clientWidth; if(ent.graph) drawGraph();} }).observe(map);
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
    catch (e) { $('#ontoTplText').textContent = '질의를 불러오지 못했습니다: ' + e.message; }
  }));
  renderNodePanel();
}

/* ================================================= action cards (shared with the HITL panel in hitl.js) */
const KIND_KO = { command: 'PLC 명령', transaction: '시스템 트랜잭션' };
function signNum(v) { return (v > 0 ? '+' : '') + Number(v).toFixed(2); }
function effChip(x, cls) {
  const t = `${x.name} ${x.dir === 1 ? '↑' : '↓'}${x.owner ? ' [' + x.owner + ']' : ''}`;
  return `<span class="${cls}" title="경로 강도 ${x.weight}${x.conds && x.conds.length ? ' · 조건: ' + x.conds.join(', ') : ''}">${esc(t)}</span>`;
}
function ruleChip(r, cls, label) {
  return `<span class="${cls}" title="${esc((r.when || '') + (r.sources && r.sources.length ? ' · 근거 ' + r.sources.join(', ') : ''))}">${esc(label)} · ${esc(r.annotation || r.rule)}</span>`;
}
function cardHtml(o, opt = {}) {
  const hasCmd = (o.actions || []).some(a => a.kind === 'command'), hasTx = (o.actions || []).some(a => a.kind !== 'command');
  const fc = (o.forecast || []).map(f => `${esc(f.name)} ${esc(f.value)}${esc(f.unit)} <span class="muted">(${esc(f.method)})</span>`).join(' · ');
  const uncond = x => !x.conditional, cond = x => x.conditional;
  const sp = o.scoreParts || {};
  const head = `<span class="hrank">${o.feasible ? o.rank : '–'}</span>
    <span class="hbody"><span class="htitle"><span class="mono">${esc(o.sopId || '')}</span> ${esc(o.name)}${o.id === opt.rec ? ' <em class="star">권고</em>' : ''}${hasCmd ? ' <em class="ot">PLC 명령</em>' : ''}${hasTx ? ' <em class="tx">작업지시 · 구매</em>' : ''}${o.id === opt.chosen ? ' <em class="done">결정됨</em>' : ''}${o.feasible ? '' : ' <em class="hard">제외</em>'}</span>
      <span class="muted">${esc(o.description || '')}</span>
      <span class="hbar"><i style="width:${Math.min(100, Math.round(Math.abs(o.score || 0) / (opt.maxAbs || 1) * 100))}%" class="${(o.score || 0) >= 0 ? 'pos' : 'neg'}"></i><b class="num">점수 ${signNum(o.score || 0)}</b>
        <span class="muted" title="온톨로지 순위 규칙(dec:rank-actions)의 식">BSC ${signNum(sp.bsc || 0)} · 예측 ${signNum(sp.forecast || 0)} · 경고 ${signNum(sp.warn || 0)} · 감점 ${signNum(sp.penalty || 0)} · 선례 ${signNum(sp.precedent || 0)}</span></span>
      ${fc ? `<span class="hfc">예측: ${fc}</span>` : ''}
      <span class="hkpi">${(o.gains || []).filter(uncond).map(x => effChip(x, 'pos')).join('')}${(o.losses || []).filter(uncond).map(x => effChip(x, 'neg')).join('')}</span>
      ${(o.gains || []).some(cond) || (o.losses || []).some(cond) ? `<span class="hkpi cond"><span class="muted">조건부:</span>${(o.gains || []).filter(cond).map(x => effChip(x, 'pos')).join('')}${(o.losses || []).filter(cond).map(x => effChip(x, 'neg')).join('')}</span>` : ''}
      <span class="hskill">${(o.actions || []).map(a => `<span title="${esc(KIND_KO[a.kind] || a.kind)}">${esc(a.code)}${a.value != null ? '=' + esc(a.value) : ''} → ${esc(a.targetName || a.target || '')}</span>`).join('') || '<span class="none">원자 조치 없음</span>'}</span>
      <span class="hmeta">승인: ${esc((o.approver || {}).name || '–')}${o.precedent && o.precedent.n ? ` · 선례 ${o.precedent.n}건 (${Math.round(o.precedent.share * 100)} %)` : ''}
        ${(o.violations || []).map(v => ruleChip(v, 'hard', '제외')).join('')}${(o.penalties || []).map(v => ruleChip(v, 'soft', `감점 ${v.penalty}`)).join('')}${(o.warnings || []).map(v => ruleChip(v, 'soft', '경고')).join('')}</span>
      <details class="source-detail hsrc"><summary>출처 보기 — 고른 규칙 · SOP 단계 · 매뉴얼</summary>
        <div>${(o.selectedBy || []).map(r => `<div><b>${esc(r.rule)}</b> <code>${esc(r.when || '')}</code> — ${esc(r.annotation || '')} <span class="muted">근거 ${esc((r.sources || []).join(', '))}</span></div>`).join('')}</div>
        <ol>${(o.steps || []).map(s => `<li>${esc(s.text)} ${s.manual ? `<span class="muted" title="${esc(s.manual.excerpt || '')}">[${esc(s.manual.ref)} ${esc(s.manual.title || '')}]</span>` : ''}</li>`).join('')}</ol>
        ${o.precedent && o.precedent.reasons && o.precedent.reasons.length ? '<div class="muted">선례 사유: ' + o.precedent.reasons.map(esc).join(' / ') + '</div>' : ''}
      </details>
    </span>`;
  if (!opt.selectable) return `<div class="hopt ${o.feasible ? '' : 'out'} ${o.id === opt.rec ? 'rec' : ''}">${'<span></span>' + head}</div>`;
  return `<label class="hopt ${o.feasible ? '' : 'out'} ${opt.selected ? 'sel' : ''} ${o.id === opt.rec ? 'rec' : ''} ${o.id === opt.chosen ? 'chosen' : ''}">
    <input type="radio" name="${opt.name || 'hopt'}" value="${esc(o.id)}" ${opt.selected ? 'checked' : ''} ${o.feasible && opt.pending ? '' : 'disabled'}>${head}</label>`;
}
window.hydCards = { cardHtml };

/* ================================================= L8 조치 판단 규칙 (DMN · BSC) */
async function loadDecisionView() {
  const sel = $('#decPattern');
  if (sel.options.length) return;
  const pats = await loadPatterns();
  pats.forEach(p => sel.append(new Option(`${p.name} (${p.code})${p.failureModes && p.failureModes.length ? ' → ' + p.failureModes.join(', ') : ''}`, p.code)));
  if (!pats.length) $('#decResult').innerHTML = '<div class="muted">에이전트에서 이상 패턴을 불러오지 못했습니다. 에이전트 연결을 확인하세요.</div>';
}
async function runDecision() {
  if (ent.busy) return; ent.busy = true;
  const b = $('#decRun'); b.disabled = true; b.textContent = '판단 중…';
  const facts = {};
  if ($('#decMode').value) facts.plc_mode = $('#decMode').value;
  if ($('#decState').value) facts.plc_state = $('#decState').value;
  if ($('#decFan').value !== '') facts.fan100_hours = Number($('#decFan').value);
  if ($('#decStandby').value) facts.standby_ready = $('#decStandby').value === 'true';
  $('#decResult').innerHTML = '<div class="muted">에이전트가 온톨로지의 규칙을 사실에 대어 보고 있습니다…</div>';
  try { ent.result = await postJ(API.agent + '/api/agent/decide', { asset: $('#decAsset').value, pattern: $('#decPattern').value, facts }); renderDecision(); }
  catch (e) { $('#decResult').innerHTML = `<div class="muted">판단 실패: ${esc(e.message)}</div>`; }
  finally { ent.busy = false; b.disabled = false; b.textContent = '판단 실행'; }
}
function renderDecision() {
  const d = ent.result; const box = $('#decResult');
  if (!d || !d.result) { box.innerHTML = `<div class="muted">${esc(d && (d.error || d.status) || '')}</div>`; return; }
  const r = d.result, opts = r.options || [];
  const maxAbs = Math.max(1, ...opts.map(o => Math.abs(o.score || 0)));
  let html = `<div class="dec-head"><h2>${esc((d.scenario || {}).name || '')} <span class="muted">${esc(d.asset || '')} · ${esc(d.id)}</span></h2>
    <span class="pill ${d.status === 'EVALUATED' ? 'CLOSED' : 'ESCALATED'}">${esc(UI.status(d.status))}</span></div>`;
  html += `<div class="summary">${esc(r.explanation || '')}</div>`;
  html += '<h2>원인 판정 (T1 · 증거)</h2><div class="table-scroll"><table class="prov"><tr><th>원인</th><th>고장 유형</th><th>점수</th><th>증거</th></tr>' +
    (d.causes || []).map((c, i) => `<tr class="${i === 0 ? 'rec' : ''}"><td><b>${esc(c.name)}</b>${i === 0 ? ' <span class="star">판정</span>' : ''}</td><td>${esc(c.failureMode || '')}</td><td class="num">${esc(c.score)}</td>` +
      `<td>${(c.evidence || []).map(e => `<span class="${e.passed ? 'pos' : 'neg'}">${esc(e.name)} = ${esc(e.value ?? '–')}</span>`).join('<br>') || '–'}</td></tr>`).join('') + '</table></div>';
  html += `<h2>조치 카드 ${opts.length}장 (스킬 = SOP)</h2><div class="hitl-opts">` + opts.map(o => cardHtml(o, { rec: r.recommended, maxAbs })).join('') + '</div>';
  if (r.rankRule) html += `<p class="muted">순위 규칙 <b>${esc(r.rankRule.rule)}</b>: ${esc(r.rankRule.annotation || '')}</p>`;
  const tr = r.trace || [];
  html += '<h2>규칙 판정 (DMN)</h2><div class="table-scroll"><table class="prov"><tr><th>판단</th><th>규칙</th><th>대상 카드</th><th>조건 (임계값)</th><th>결과</th></tr>' +
    tr.map(t => `<tr class="${t.fired ? 'rec' : ''}"><td>${esc(t.decision === 'dec:action-candidates' ? '후보 선택' : '규정 적합성')}</td><td class="mono">${esc(t.rule)}</td>` +
      `<td>${esc(t.skill ? ((opts.find(o => o.id === t.skill) || {}).sopId || t.skill) : '—')}</td><td><code>${esc(t.when || '')}</code></td>` +
      `<td>${t.fired ? '<b>발동</b>' : (t.unknown && t.unknown.length ? '<span class="muted">사실 없음: ' + esc(t.unknown.join(', ')) + '</span>' : '해당 없음')}</td></tr>`).join('') + '</table></div>';
  html += '<h2>규칙이 검사한 사실과 출처 (InputData → 시스템 · 센서)</h2><div class="table-scroll"><table class="prov facts-table"><tr><th>입력 데이터</th><th>출처</th><th>값</th><th>가져온 방법</th></tr>' +
    (d.provenance || []).map(p => `<tr><td>${esc(p.name)} <span class="mono muted">${esc(p.variable)}</span></td><td><b>${esc(p.sourceName || p.source)}</b></td>` +
      `<td>${p.error ? '<span class="neg">' + esc(p.error) + '</span>' : esc(JSON.stringify(p.value))}</td><td class="muted">${esc(p.how || '')}</td></tr>`).join('') + '</table></div>';
  html += `<details class="technical"><summary>판단 과정 확인</summary>` + traceHtml({ id: d.id, status: d.status, started: d.created, steps: d.steps || [] }) + '</details>';
  box.innerHTML = html;
}
$('#decRun').addEventListener('click', runDecision);

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
  list.innerHTML = ent.decisions.length ? '' : '<div class="muted">아직 제출된 판단이 없습니다. 결함 시뮬레이션으로 경보를 발생시키면 에이전트가 조치 카드를 제출합니다.</div>';
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
  if (!d) { ent.lastDetailSig = null; box.innerHTML = '<div class="empty">목록에서 판단을 선택하면 승인 화면을 확인할 수 있습니다.</div>'; return; }
  // the 2.5 s refresh must not wipe what the approver is typing or selecting: redraw only when the decision changed
  const sig = d.id + '|' + d.state + '|' + (d.executions || []).length + '|' + (d.history || []).length;
  if (sig === ent.lastDetailSig && box.querySelector('.opts')) return;
  ent.lastDetailSig = sig;
  const roles = Object.entries(d.roles || {}).sort((a, b) => b[1].level - a[1].level);
  const pending = d.state === 'PENDING_APPROVAL';
  let html = `<h2 style="margin-top:0">${esc((d.scenario || {}).name || '')} <span class="pill ${esc(d.state)}">${esc(UI.status(d.state))}</span></h2>
    <div class="muted">${esc(d.id)} · ${esc(d.asset || '')} · 제출 ${esc(UI.dateTime(d.created))}${(d.origin || {}).incident ? ' · 인시던트 ' + esc(d.origin.incident) : ''}</div>
    <div class="summary">${esc(d.explanation || '')}</div>`;
  if (pending) html += `<div class="who"><label>승인자 <input id="decBy" value="${esc(ent.form.by)}"></label><label>역할 <select id="decRole">${roles.map(([id, r]) => `<option value="${esc(id)}" ${id === ent.form.role ? 'selected' : ''}>${esc(r.name)} (${esc(r.dept)}, 직급 ${r.level})</option>`).join('')}</select></label>
      <span class="muted">카드(SOP)에 지정된 승인 역할이나 더 높은 직급으로 승인할 수 있습니다. 설비 인시던트의 PLC 명령은 이상 확인 · 조치 화면에서 결정합니다.</span></div>`;
  html += '<div class="table-scroll"><table class="opts"><thead><tr><th>조치 카드 (스킬 = SOP)</th><th>점수</th><th>승인 역할</th><th>원자 조치 → 대상</th><th>승인</th></tr></thead><tbody>';
  for (const o of d.options || []) {
    html += `<tr class="${o.id === d.recommended ? 'rec' : ''} ${o.feasible ? '' : 'out'} ${o.id === d.chosen ? 'chosen' : ''}"><td><b><span class="mono">${esc(o.sopId || '')}</span> ${esc(o.name)}</b>${o.id === d.recommended ? ' <span class="star">권고</span>' : ''}${o.feasible ? '' : ' <span class="hard">' + esc(((o.violations || [])[0] || {}).annotation || '제외') + '</span>'}</td>` +
      `<td data-label="점수" class="num ${(o.score || 0) >= 0 ? 'pos' : 'neg'}">${esc(o.score ?? '–')}</td><td data-label="승인 역할">${esc((o.approver || {}).name || '–')}</td>` +
      `<td data-label="원자 조치 → 대상">${(o.actions || []).map(a => `${esc(a.code)}${a.value != null ? '=' + esc(a.value) : ''} → <b>${esc(a.targetName || a.target || '')}</b>`).join('<br>') || '–'}</td>` +
      `<td>${pending && o.feasible ? `<button class="btn small" data-approve="${esc(o.id)}">이 카드로 승인</button>` : o.id === d.chosen ? '승인됨' : ''}</td></tr>`;
  }
  html += '</tbody></table></div>';
  if (pending) html += `<div class="approve-row"><input type="text" id="decReason" placeholder="반려 사유" value="${esc(ent.form.reason)}"><button class="btn" id="decReject">반려</button><span id="decMsg" class="neg">${esc(ent.form.msg || '')}</span></div>`;
  if ((d.executions || []).length) html += '<h2>실행 결과 (L9 → 기업 시스템)</h2><div class="table-scroll" tabindex="0" role="region" aria-label="실행 결과 표"><table class="prov"><tr><th>카드 · 조치</th><th>시스템</th><th>결과</th><th>참조</th><th>내용</th></tr>' +
    d.executions.map(x => `<tr><td>${esc(x.skill)}${x.code ? ' · ' + esc(x.code) : ''}</td><td>${esc(x.system || '')}</td><td><span class="pill ${x.status === 'DONE' ? 'CLOSED' : x.status === 'VIA_HITL' ? 'AWAITING_APPROVAL' : 'ESCALATED'}">${esc(UI.status(x.status))}</span></td><td class="mono">${esc(x.ref || '')}</td><td>${esc(x.detail || '')}</td></tr>`).join('') + '</table></div>';
  html += '<h2>이력</h2><div class="audit">' + (d.history || []).map(h => UI.eventRecord({time:h.t,name:h.state,actor:h.by,detail:h.reason || '',raw:h})).join('') + '</div>';
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
    finally { controls.forEach(c => c.disabled = false); b.textContent = '이 카드로 승인'; }
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
  if (!s) { box.innerHTML = '<div class="muted">기업 시스템에 연결할 수 없습니다. 연결 상태를 확인해 주세요.</div>'; return; }
  const t = (rows, cols, labels) => rows.length ? '<div class="table-scroll" tabindex="0"><table><thead><tr>' + labels.map(x=>`<th>${esc(x)}</th>`).join('') + '</tr></thead><tbody>' + rows.slice(0, 6).map(r => '<tr>' + cols.map(c => `<td>${esc(r[c] ?? '–')}</td>`).join('') + '</tr>').join('') + '</tbody></table></div>' : '<div class="muted">변경 없음</div>';
  const boards = [
    ['MES', '생산오더', t(s.mes.orders.map(o => ({ ...o, where: o.moved_from ? `${o.moved_from} → ${o.asset}` : o.asset })), ['order_id', 'where', 'due_in_h'], ['생산오더','설비','납기까지 (시간)'])],
    ['CMMS', '작업지시', t(s.cmms.work_orders, ['id', 'asset', 'task', 'window'], ['작업번호','설비','작업','정비 시점'])],
    ['ERP', '구매요청 · 출하', t([...s.erp.purchase_requests.map(p => ({ a: p.id, b: p.supplierName, c: p.status })), ...s.erp.shipments.map(x => ({ a: x.id, b: `${x.item} ${x.qty}개`, c: x.from }))], ['a', 'b', 'c'], ['참조번호','대상','상태 · 출고처'])],
    ['QMS', '격리 · 출하 승인', t([...s.qms.holds.map(h => ({ a: h.lot, b: h.status })), ...s.qms.releases.map(h => ({ a: h.lot, b: h.status }))], ['a', 'b'], ['로트','상태'])],
    ['EMS', '수요 제어', t(s.ems.actions, ['action'], ['실행 내용'])],
  ];
  box.innerHTML = boards.map(([sys, title, body]) => `<div class="board"><header><b>${sys}</b><span>${title}</span></header>${body}</div>`).join('');
  $('#txList').innerHTML = ent.tx.length ? ent.tx.slice(0, 12).map(x => UI.eventRecord({time:x.t,name:x.system.replace(/^sys:/,'').toUpperCase(),actor:x.by,detail:x.detail,raw:x})).join('') : '<div class="muted">아직 시스템 실행 이력이 없습니다.</div>';
}

initOntology();
setInterval(() => { if (state.tab === 'process') refreshProcess(); }, 2500);
window.hydApp.selectTab = selectTab;          // the recorder and ?present=1 hooks must see the L7~L9 loaders too
window.hydEnt = { ent, runDecision, loadGraph, refreshProcess, loadDecisionView };
