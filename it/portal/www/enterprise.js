/* 지식 지도 · 규칙 판단 · 업무 시스템 기록 (enterprise.js) — ontology v2.
   Loaded after app.js and reuses its helpers ($, el, esc, fmt, getJ, postJ, state, selectTab).
   Data: agent for the ontology and the decision engine, process for approval, enterprise-sim for ERP/MES/… — all through the same-origin table API (layers.js).
   A122: wording from UI.terms; action-candidate card = title · chips · score · one line · evidence folded. */

// 지식 지도의 묶음 = 온톨로지 v2 의 층(it/neo4j/v2/schema.json). 이름에 프레임워크 이름을 쓰지 않는다(명칭표).
// at: 캔버스에서 그 묶음이 모이는 자리(0 ~ 1, 왼쪽 위가 0,0). 색은 canvas.css 의 [data-g="<key>"] 가 정한다(어두운 캔버스와 밝은 상세 칸의 짝 색).
const ONTO_GROUPS = [
  { key: 'value', title: '전략 목표', at: [0.16, 0.16], labels: ['Perspective', 'Objective', 'Measure'] },
  { key: 'process', title: '프로세스', at: [0.46, 0.06], labels: ['Process', 'Event', 'Task', 'Gateway'] },
  { key: 'resource', title: '자원', at: [0.14, 0.72], labels: ['OrgUnit', 'Role', 'System', 'Asset', 'Component', 'Sensor', 'Actuator', 'StateVariable', 'Part', 'Supplier'] },
  { key: 'diagnosis', title: '설비 진단', at: [0.42, 0.46], labels: ['AnomalyPattern', 'Symptom', 'FailureMode', 'Cause', 'Evidence', 'ManualSection'] },
  { key: 'skill', title: '조치 방법과 규칙', at: [0.8, 0.4], labels: ['Skill', 'Step', 'Action', 'Decision', 'DecisionTable', 'Rule', 'InputData', 'KnowledgeSource'] },
  { key: 'external', title: '외부 변수 · 예측 · 사례', at: [0.62, 0.94], labels: ['ExternalVariable', 'Forecast', 'Incident', 'DecisionCase'] },
  // G4: 학생 이름 공간의 업무 고유 클래스(students/<ID>/schema.json) — v2 에 없는 레이블은 모두 이 묶음에 그린다
  { key: 'student', title: '내 업무 개념', at: [0.38, 0.96], labels: [], other: true },
];
const LABEL_KO = { Perspective: '관점', Objective: '전략 목표', Measure: '성과 지표', Process: '프로세스', Event: '이벤트', Task: '단계', Gateway: '분기',
  OrgUnit: '부서', Role: '역할', System: '시스템', Asset: '설비', Component: '구성 요소', Sensor: '센서', Actuator: '구동기', StateVariable: '상태 변수',
  Part: '부품', Supplier: '공급사', AnomalyPattern: '이상 패턴', Symptom: '증상', FailureMode: '고장 유형', Cause: '원인', Evidence: '증거', ManualSection: '매뉴얼 절',
  Skill: '조치 방법', Step: '절차 단계', Action: '세부 동작', Decision: '판단', DecisionTable: '결정표', Rule: '규칙', InputData: '입력 데이터',
  KnowledgeSource: '지식 출처', ExternalVariable: '외부 변수', Forecast: '예측', Incident: '사건', DecisionCase: '판단 사례' };
// 지식 지도 상세 칸의 속성 이름(그래프 속성 키 → 화면 이름). 여기에 없는 키(적재 출처 · 해시 · 정책 원문 같은 내부 값)는 「그 밖의 속성」 접기에 원래 이름으로 둔다
const PROP_KO = { description: '설명', annotation: '풀이', text: '내용', title: '제목', excerpt: '원문 발췌', citation: '인용 위치', ref: '참조 번호', order: '순서',
  aliases: '다른 이름', kind: '종류', code: '코드', unit: '단위', variable: '변수', tag: '태그', zone: '구역', level: '수준', scope: '범위', source: '출처',
  kpiRole: '지표 성격', frequency: '측정 주기', direction: '좋은 방향', target: '목표', normal: '정상 범위', min: '최소', max: '최대', limit: '한도',
  rule: '규칙 식', formula: '계산식', when: '조건', effect: '효과', expect: '기대 값', hitPolicy: '적용 방식', weight: '가중치', prior: '사전 확률', penalty: '감점',
  threshold: '임계값', thresholdWarn: '경고 임계값', thresholdCrit: '위험 임계값', detectionMode: '감지 방식', holdSeconds: '지속 시간(초)',
  windowSeconds: '관찰 구간(초)', slopeWindowSeconds: '기울기 구간(초)', clearRule: '해제 규칙', clearHoldSeconds: '해제 지속 시간(초)', severity: '심각도',
  sopId: '절차 번호', executable: '실행 가능', isExecutable: '실행 가능', partNo: '부품 번호', avl: '승인 공급사', oem: '순정품', resource: '자원',
  question: '질문', note: '비고', virtual: '가상 값' };
const PROP_VALUE_KO = { kpiRole: { lagging: '후행 지표(결과)', leading: '선행 지표(결과를 움직이는 요인)' }, direction: { UP: '높을수록 좋음', DOWN: '낮을수록 좋음' } };
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
  form: { msg: '' }, lastDetailSig: null, decShown: 20,
  definitionNames: {}, definitionNamesError: '' };

/* ------------------------------------------------ tab hooks */
hydTabs.onShow(name => {
  if (name === 'ontology') loadGraph();
  if (name === 'decision') loadDecisionView();
  if (name === 'process') refreshProcess();
});
async function loadPatterns() {
  if (!ent.patterns || !ent.patterns.length) { try { ent.patterns = await getJ(API.agent + '/api/ontology/patterns'); ent.patternsError = ''; } catch (e) { ent.patterns = null; ent.patternsError = e.message; } }
  return ent.patterns || [];
}

/* ================================================= 지식 지도 */
async function loadNamespaces(force) {
  // G4: 학생 이름 공간(화면 이름 「지식 묶음」) 목록(맨 위 = 기본 지식 = ns 없는 노드). 못 읽으면 고르기 칸에 사유를 보이고 다음 "다시 읽기"에 또 읽는다
  const sel = $('#ontoNs'); if (!sel || (sel.dataset.loaded && !force)) return;
  const keep = sel.value;
  let list;
  try { list = await getJ(API.agent + '/api/ontology/namespaces'); }
  catch (e) {   // 이미 받은 이름 공간은 그대로 두고 사유 한 줄만 붙인다(고른 것이 사라지지 않게)
    sel.querySelectorAll('option[data-note]').forEach(o => o.remove());
    sel.append(nsNote(`더 넣은 지식 묶음 목록을 읽지 못함 — ${e.message}`));
    sel.title = `더 넣은 지식 묶음 목록을 읽지 못했습니다: ${e.message}`; delete sel.dataset.loaded;
    return;
  }
  sel.querySelectorAll('option:not([value=""]), option[data-note]').forEach(o => o.remove());
  list.forEach(x => sel.append(new Option(`${x.ns} · 항목 ${x.nodes}개`, x.ns)));
  if (!list.length) sel.append(nsNote('더 넣은 지식 묶음 없음'));
  sel.title = ''; sel.dataset.loaded = '1';
  if (list.some(x => x.ns === keep)) sel.value = keep;
  else if (keep) { sel.value = ''; UI.toast(`지식 묶음 ${keep}이(가) 그래프에 없어 기본 지식으로 돌아갑니다`, { tone: 'neg' }); loadGraph(true); }
}
const nsNote = text => { const o = new Option(text, ''); o.disabled = true; o.dataset.note = '1'; return o; };
async function loadGraph(force) {
  const asset = $('#ontoAsset').value + '|' + (($('#ontoNs') || {}).value || '');
  if (ent.graph && ent.graphAsset === asset && !force) { drawGraph(); return; }
  $('#ontoStats').textContent = UI.t('loading');
  loadNamespaces(force);
  const [code, ns] = asset.split('|');
  const current = () => $('#ontoAsset').value + '|' + (($('#ontoNs') || {}).value || '');
  try {
    const graph = await getJ(API.agent + '/api/ontology/graph?asset=' + encodeURIComponent(code) + (ns ? '&ns=' + encodeURIComponent(ns) : ''));
    if (current() !== asset) return;
    if (!Array.isArray(graph?.nodes) || !Array.isArray(graph?.edges)) throw new Error('지식 지도 응답 형식이 올바르지 않습니다. 다시 조회하세요.');
    if (ent.graphAsset !== asset) ent.sel = null;
    ent.graph = graph; ent.graphAsset = asset;
    $('#ontoError').innerHTML = '';
  }
  catch (e) {
    if (current() !== asset) return;
    // 다시 연 화면은 다시 읽어야 한다 — 앞서 받은 지도를 되살아난 것처럼 보이지 않는다. 사유는 캔버스 위 밝은 자리에 보인다
    ent.graph = null; kg.of = null; kg.state = null;
    $('#ontoMap').innerHTML = ''; $('#ontoLayers').innerHTML = ''; $('#ontoNode').innerHTML = ''; $('#ontoNode').dataset.sig = '';
    $('#ontoHint').textContent = '지도를 그리지 못했습니다';
    $('#ontoStats').textContent = UI.t('error.load');
    $('#ontoError').innerHTML = UI.errorBlock(UI.t('onto.loadFail'), e.message, { retry: true });
    $('#ontoError').querySelector('[data-retry]')?.addEventListener('click', () => loadGraph(true));
    return;
  }
  // Relational definitions own user-created flow names; a graph id is not a display name.
  try {
    const defs = requireList(await getJ(API.process + '/api/process/definitions'), '흐름 이름 목록');
    if (current() !== asset) return;
    const names = {};
    defs.filter(d => d.name && d.name !== d.id).forEach(d => {
      names[d.id + '@' + d.version] = d.name;
      if (!names[d.id] || d.deployed) names[d.id] = d.name;
    });
    ent.definitionNames = names; ent.definitionNamesError = '';
  } catch (e) {
    if (current() !== asset) return;
    ent.definitionNames = {}; ent.definitionNamesError = '흐름 이름을 읽지 못했습니다: ' + e.message;
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
// 이름 · 설명 속 경보 패턴 코드(COOLER_DEGRADATION 등)는 UI.words 가 사람 이름으로 바꾼다
const nodeName = n => {
  if (n.name && n.name !== n.id) return UI.words(n.name);
  if (n.props?.annotation || n.props?.title) return UI.words(n.props.annotation || n.props.title);
  const id = n.props?.definition_id || n.id;
  if (n.label === 'Process' || n.label === 'ProcessVersion') {
    const registered = ent.definitionNames[id + '@' + n.props?.version] || ent.definitionNames[id];
    if (registered) return String(registered);
    if (UI.terms['def.' + id]) return UI.terms['def.' + id];
    const known = UI.name(n.id);
    if (known !== n.id) return String(known);
    return ent.definitionNamesError ? '흐름 이름 확인 불가' : '이름 미등록 흐름';
  }
  return String(UI.name(n.id));
};
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
/* ================================================= 지식 지도 그림 — 어두운 캔버스의 점과 선 (디자인 기준 5-10 · 6-3)
   배치에는 난수가 없다. 같은 데이터면 늘 같은 자리다(항목과 연결을 id 순으로 세운 뒤 계산하므로 서버가 준 차례가 달라도 같다).
     ① 종류(조치 방법 · 절차 단계 · 규칙 …)마다 작은 원 하나: 그 종류의 항목을 연결이 많은 것부터 가운데에서 바깥으로 해바라기 꼴로 놓는다.
     ② 묶음(전략 목표 · 자원 …) 안에서 종류 원들을 큰 것부터, 이미 놓인 원에 닿으면서 묶음 가운데에 가장 가까운 자리에 채운다.
     ③ 묶음을 ONTO_GROUPS.at 의 자리에 두고, 정해진 횟수만큼 종류 원을 가운데와 제 묶음 쪽으로 당기면서 겹친 원을 떼어 낸다(다른 묶음과는 더 넓게).
   그리기: 좌표에 배율을 곱해 화면 좌표로 그린다. 글자는 확대 · 축소와 무관하게 같은 크기다(이름 12px, 묶음 · 종류 이름 11px).
     이름은 서로 겹치지 않는 것만 보인다 — 고른 것 → 이어진 것 → 검색에 걸린 것 → 경로 → 연결이 많은 것 차례로 자리를 잡고, 확대할수록 더 많이 보인다.
     숨은 이름은 점에 마우스를 올리거나 탭으로 가면 보인다. */
const KG = { SP: 46, R: 5, R_SEL: 11, NAME_MAX: 18, PAD: { l: 24, r: 24, t: 92, b: 64 }, ZOOM_MAX: 2.5, HALO: 120 };
const KG_GOLDEN = Math.PI * (3 - Math.sqrt(5));
const kgDist = (ax, ay, bx, by) => Math.sqrt((ax - bx) * (ax - bx) + (ay - by) * (ay - by));

/** 원들을 겹치지 않게 채운다: 큰 것부터, 이미 놓인 원에 닿으면서 가운데(0,0)에 가장 가까운 자리.
    각 원에 x · y 를 적고 둘러싸는 반지름을 돌려준다(가운데는 넓이로 잰 중심) */
function kgPack(circles) {
  const order = circles.map((c, i) => i).sort((a, b) => circles[b].r - circles[a].r || a - b), placed = [];
  for (const i of order) {
    const c = circles[i];
    if (!placed.length) { c.x = 0; c.y = 0; placed.push(c); continue; }
    let best = null;
    const tryAt = (x, y) => {
      if (placed.some(p => kgDist(p.x, p.y, x, y) < p.r + c.r - 1e-6)) return;
      const d = x * x + y * y;
      if (!best || d < best.d - 1e-6) best = { x, y, d };
    };
    for (const p of placed) for (let k = 0; k < 36; k++) { const th = k * Math.PI / 18; tryAt(p.x + (p.r + c.r) * Math.cos(th), p.y + (p.r + c.r) * Math.sin(th)); }      // 놓인 원 하나에 닿는 자리
    for (let a = 0; a < placed.length; a++) for (let b = a + 1; b < placed.length; b++) {                                                                        // 놓인 원 둘에 함께 닿는 자리
      const p = placed[a], q = placed[b], ra = p.r + c.r, rb = q.r + c.r, d = kgDist(p.x, p.y, q.x, q.y);
      if (d < 1e-6 || d > ra + rb) continue;
      const along = (ra * ra - rb * rb + d * d) / (2 * d), h2 = ra * ra - along * along; if (h2 < 0) continue;
      const h = Math.sqrt(h2), ux = (q.x - p.x) / d, uy = (q.y - p.y) / d, mx = p.x + ux * along, my = p.y + uy * along;
      tryAt(mx - uy * h, my + ux * h); tryAt(mx + uy * h, my - ux * h);
    }
    c.x = best.x; c.y = best.y; placed.push(c);
  }
  let sw = 0, cx = 0, cy = 0;
  for (const c of circles) { const w = c.r * c.r; sw += w; cx += c.x * w; cy += c.y * w; }
  cx /= sw || 1; cy /= sw || 1;
  let R = 0;
  for (const c of circles) { c.x -= cx; c.y -= cy; R = Math.max(R, Math.sqrt(c.x * c.x + c.y * c.y) + c.r); }
  return R;
}
/** 그래프 → 항목 자리. DOM 을 쓰지 않는다(시험이 node 에서 그대로 부른다).
    돌려주는 값: { nodes: [{id, x, y, g, deg}], groups: [{key, count, capX, capY}], types: [{key, label, x, y, r, count}], bounds } — g 는 ONTO_GROUPS 의 번호 */
function layoutGraph(graph) {
  const SP = KG.SP, C = SP * 0.56;      // 해바라기 꼴에서 이웃 점 사이가 SP 쯤 되는 계수
  const nodes = (graph.nodes || []).map(n => ({ id: String(n.id), label: String(n.label), g: groupOf(n.label) })).filter(n => n.g >= 0)
    .sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  const at = new Map(nodes.map((n, i) => [n.id, i]));
  const N = nodes.length, deg = new Array(N).fill(0);
  for (const e of graph.edges || []) { const a = at.get(String(e.from)), b = at.get(String(e.to)); if (a != null && b != null && a !== b) { deg[a]++; deg[b]++; } }

  // ① · ② 묶음마다: 종류 원을 만들고 묶음 안에 채운다
  const groups = [];
  ONTO_GROUPS.forEach((gr, gi) => {
    const byLabel = new Map();
    nodes.forEach((n, i) => { if (n.g === gi) (byLabel.get(n.label) || byLabel.set(n.label, []).get(n.label)).push(i); });
    if (!byLabel.size) return;
    const rank = l => { const k = gr.labels.indexOf(l); return k < 0 ? gr.labels.length : k; };
    const types = [...byLabel.keys()].sort((a, b) => rank(a) - rank(b) || (a < b ? -1 : 1)).map(label => {
      const members = byLabel.get(label).sort((p, q) => deg[q] - deg[p] || p - q);      // 연결이 많은 것부터(같으면 id 순)
      return { label, members, r: C * Math.sqrt(members.length) + SP * 0.4, x: 0, y: 0 };
    });
    const r = kgPack(types);
    groups.push({ key: gr.key, gi, types, r, count: types.reduce((s, t) => s + t.members.length, 0), x: 0, y: 0 });
  });

  // ③ 묶음을 at 자리에 두고 종류 원 단위로 모은다: 가운데와 제 묶음 중심으로 당기고, 겹친 원은 떼어 낸다(다른 묶음과는 더 넓게). 큰 원이 덜 움직인다
  const span = Math.sqrt(groups.reduce((s, g) => s + g.r * g.r, 0)) * 1.5;
  const discs = [];
  groups.forEach(g => { const [ax, ay] = ONTO_GROUPS[g.gi].at; g.x = (ax - 0.5) * span * 1.3; g.y = (ay - 0.5) * span; g.types.forEach(t => { t.x += g.x; t.y += g.y; t.group = g; discs.push(t); }); });
  for (let it = 0; it < 480; it++) {
    if (it < 400) {
      for (const g of groups) { let sw = 0, cx = 0, cy = 0; for (const t of g.types) { const w = t.r * t.r; sw += w; cx += t.x * w; cy += t.y * w; } g.x = cx / sw; g.y = cy / sw; }
      for (const t of discs) { t.x += (t.group.x - t.x) * 0.03 - t.x * 0.006; t.y += (t.group.y - t.y) * 0.03 - t.y * 0.009; }      // 세로로 조금 더 당겨 가로로 긴 캔버스에 맞춘다
    }
    for (let i = 0; i < discs.length; i++) for (let j = i + 1; j < discs.length; j++) {      // 마지막 80번은 떼어 놓기만 한다
      const a = discs[i], b = discs[j], need = a.r + b.r + (a.group === b.group ? SP * 0.35 : SP * 1.1);
      let dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy);
      if (d >= need) continue;
      if (d < 1e-6) { dx = 1; dy = (j - i) * 0.37; d = Math.sqrt(dx * dx + dy * dy); }
      const push = (need - d) / d, wa = b.r * b.r / (a.r * a.r + b.r * b.r), wb = 1 - wa;
      a.x -= dx * push * wa; a.y -= dy * push * wa; b.x += dx * push * wb; b.y += dy * push * wb;
    }
  }
  groups.forEach(g => { g.x = 0; g.y = 0; });      // 종류 원의 좌표가 이제 전체 좌표다

  // ④ 좌표
  const round = v => Math.round(v * 10) / 10;
  const out = new Array(N), types = [];
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const g of groups) {
    let top = null;
    for (const t of g.types) {
      const cx = g.x + t.x, cy = g.y + t.y, n = t.members.length;
      t.members.forEach((i, k) => {
        const rr = n === 1 ? 0 : C * Math.sqrt(k + 0.5), th = k * KG_GOLDEN, x = round(cx + rr * Math.cos(th)), y = round(cy + rr * Math.sin(th));
        out[i] = { id: nodes[i].id, x, y, g: g.gi, deg: deg[i] };
        x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
      });
      const inner = t.r - SP * 0.4;
      const type = { key: g.key, label: t.label, x: round(cx), y: round(cy - inner), r: round(inner), count: n };
      types.push(type);
      if (!top || type.y < top.y) top = type;
    }
    g.capX = top.x; g.capY = top.y;      // 묶음 이름은 그 묶음에서 가장 위에 있는 종류 원 위에 쓴다
  }
  if (!N) { x0 = y0 = 0; x1 = y1 = 1; }
  return {
    nodes: out,
    groups: groups.map(g => ({ key: g.key, count: g.count, capX: g.capX, capY: g.capY })),
    types,
    bounds: { x0: round(x0), y0: round(y0), x1: round(x1), y1: round(y1) },
  };
}
/** 배치 전체가 폭 w · 높이 h 의 캔버스에 들어오는 배율과 옮김. 캔버스 안 도구 · 층 칩이 놓일 여백(pad)을 뺀다 */
function fitView(bounds, w, h, pad = KG.PAD) {
  const bw = Math.max(1, bounds.x1 - bounds.x0), bh = Math.max(1, bounds.y1 - bounds.y0);
  const iw = Math.max(40, w - pad.l - pad.r), ih = Math.max(40, h - pad.t - pad.b);
  const k = Math.min(iw / bw, ih / bh, 1.4);
  return { k, tx: pad.l + (iw - bw * k) / 2 - bounds.x0 * k, ty: pad.t + (ih - bh * k) / 2 - bounds.y0 * k };
}
// 이름의 화면 폭 어림: 한글 · 한자는 글자 크기만큼, 그 밖은 0.58배. 잴 요소 없이 계산해 배치와 시험이 같은 값을 쓴다
const kgTextW = (text, size = 12) => { let w = 0; for (const ch of String(text)) w += ch.charCodeAt(0) > 0x2E7F ? size : ch === ' ' ? size * 0.32 : size * 0.58; return w; };
const kgShort = name => { const a = Array.from(String(name)); return a.length > KG.NAME_MAX ? a.slice(0, KG.NAME_MAX - 1).join('').trimEnd() + '…' : String(name); };
// 점의 반지름: 화면에 맞춘 작은 배율에서는 점끼리 붙지 않게 줄인다
const kgDotR = k => k < 0.42 ? 3.5 : k < 0.62 ? 4 : KG.R;
/** 겹치지 않게 보일 글자를 고른다(화면 좌표). 앞선 것(prio 큰 것)이 먼저 자리를 잡는다.
    항목 이름 {id, x, y, r, w, prio, top, lit} — 점 오른쪽에 쓰고, 오른쪽 끝(maxX)을 넘거나 막히면 왼쪽에(왼쪽 끝 minX 를 넘지 않을 때), top 이면 늘 점 위에 쓴다.
    고정 글자 {id, box: [x0, y0, x1, y1], prio, lit} — 묶음 · 종류 이름처럼 자리가 정해진 것.
    보통 글자는 점 위에 쓰지 않는다. 돌려주는 값: Map(id → 'R' | 'L' | 'T' | 'B') */
function pickLabels(items, minX = -Infinity, maxX = Infinity) {
  const order = items.slice().sort((a, b) => b.prio - a.prio || (a.id < b.id ? -1 : 1));
  const dots = items.filter(o => !o.box), placed = [], out = new Map();
  // 밝은 글자(lit — 고른 것과 이어진 것 · 검색 · 경로 · 묶음 이름)는 흐린 점 위에 써도 된다(글자 뒤에 바탕색 테두리가 있다). 밝은 점과 다른 글자만 피한다
  const hit = (r, self) => placed.some(p => r[0] < p[2] && p[0] < r[2] && r[1] < p[3] && p[1] < r[3])
    || dots.some(o => o !== self && (o.lit || !self.lit) && o.x + o.r > r[0] && o.x - o.r < r[2] && o.y + o.r > r[1] && o.y - o.r < r[3]);
  for (const it of order) {
    if (it.top) { placed.push([it.x - it.w / 2 - 2, it.y - it.r - 28, it.x + it.w / 2 + 2, it.y - it.r - 6]); out.set(it.id, 'T'); continue; }
    if (it.box) { if (!hit(it.box, it)) { placed.push(it.box); out.set(it.id, 'B'); } continue; }
    const right = [it.x + it.r + 4, it.y - 9, it.x + it.r + 8 + it.w, it.y + 8], left = [it.x - it.r - 8 - it.w, it.y - 9, it.x - it.r - 4, it.y + 8];
    const side = right[2] <= maxX && !hit(right, it) ? 'R' : left[0] >= minX && !hit(left, it) ? 'L' : null;
    if (side) { placed.push(side === 'R' ? right : left); out.set(it.id, side); }
  }
  return out;
}
/** 항목 하나의 모양 클래스. s = { sel, near: Set, path: Set | null, match: Set, query: boolean }.
    밝은 것 = 고른 것(sel) · 바로 이어진 것(near) · 이상 패턴 경로(path) · 검색에 걸린 것(match). 그 가운데 하나라도 켜져 있으면 나머지는 흐리다(far) */
function kgNodeClass(id, s) {
  const sel = id === s.sel, near = !sel && s.near.has(id), path = !!s.path && s.path.has(id), match = s.match.has(id);
  const far = !(sel || near || path || match) && (s.sel != null || !!s.path || s.query);
  return ['o-node', sel && 'sel', near && 'near', path && 'path', match && 'match', far && 'far'].filter(Boolean).join(' ');
}
function kgEdgeClass(a, b, s) {
  if (s.sel != null && (a === s.sel || b === s.sel)) return 'kg-e hot';
  if (s.path && s.path.has(a) && s.path.has(b)) return 'kg-e path';
  return s.sel != null || s.path || s.query ? 'kg-e dim' : 'kg-e';
}

const kg = { of: null, key: null, nodes: [], byId: new Map(), edges: [], adj: new Map(), groups: [], types: [], bounds: null, state: null,
  view: { k: 1, tx: 0, ty: 0 }, fitK: 1, moved: false, size: [0, 0], matches: [], matchAt: 0, ms: {} };
const kgCollator = new Intl.Collator('ko');      // 이름 순 — 비교할 때마다 새로 만들면 느리다
const kgTitle = key => ONTO_GROUPS.find(x => x.key === key).title;

function kgBuild(g) {
  const t0 = performance.now(); kg.state = null;
  const lay = layoutGraph(g);
  const t1 = performance.now();
  const raw = new Map(g.nodes.map(n => [String(n.id), n]));
  const rank = p => { const labels = ONTO_GROUPS[p.g].labels, k = labels.indexOf(raw.get(p.id).label); return k < 0 ? labels.length : k; };
  kg.nodes = lay.nodes.map(p => { const n = raw.get(p.id), name = nodeName(n), short = kgShort(name);
    return { ...p, n, name, short, w: kgTextW(short), kind: LABEL_KO[n.label] || n.label, key: ONTO_GROUPS[p.g].key, rank: rank(p), el: null }; })
    .sort((a, b) => a.g - b.g || a.rank - b.rank || kgCollator.compare(a.name, b.name) || (a.id < b.id ? -1 : 1));      // 탭으로 도는 차례 = 묶음 → 종류 → 이름
  kg.byId = new Map(kg.nodes.map(n => [n.id, n]));
  kg.adj = new Map(kg.nodes.map(n => [n.id, new Set()]));
  kg.edges = [];
  for (const e of g.edges) {
    const a = kg.byId.get(String(e.from)), b = kg.byId.get(String(e.to)); if (!a || !b || a === b) continue;
    kg.adj.get(a.id).add(b.id); kg.adj.get(b.id).add(a.id);
    kg.edges.push({ a, b, type: e.type, el: null });
  }
  kg.groups = lay.groups.map(gr => ({ ...gr, text: kgTitle(gr.key), el: null }));
  kg.types = lay.types.map(t => ({ ...t, text: `${LABEL_KO[t.label] || t.label} ${t.count}`, el: null }));
  kg.groups.forEach(gr => { gr.w = kgTextW(gr.text, 11) + 6; });
  kg.types.forEach(t => { t.w = kgTextW(t.text, 11) + 4; });
  kg.bounds = lay.bounds;
  // 선: 한 번 휘는 곡선(휨은 길이의 12 %, 최대 36). 좌표는 배치 좌표 그대로 두고 선 묶음에 배율을 건다(굵기는 배율과 무관 — CSS non-scaling-stroke)
  const edgeHtml = kg.edges.map((e, i) => {
    const dx = e.b.x - e.a.x, dy = e.b.y - e.a.y, len = Math.sqrt(dx * dx + dy * dy) || 1, bend = Math.min(36, len * 0.12);
    const mx = (e.a.x + e.b.x) / 2 - dy / len * bend, my = (e.a.y + e.b.y) / 2 + dx / len * bend;
    return `<path class="kg-e" data-i="${i}" d="M${e.a.x} ${e.a.y}Q${mx.toFixed(1)} ${my.toFixed(1)} ${e.b.x} ${e.b.y}"><title>${esc(e.a.name)} → ${esc(RELATION_KO[e.type] || e.type)} → ${esc(e.b.name)}</title></path>`;
  }).join('');
  // 종류마다 옅은 바탕 원(묶음 색) — 같은 종류가 한 덩어리로 읽힌다
  const blobHtml = kg.types.map(t => `<circle class="kg-blob" data-g="${t.key}" cx="${t.x}" cy="${(t.y + t.r).toFixed(1)}" r="${(t.r + KG.SP * 0.3).toFixed(1)}"/>`).join('');
  const capHtml = kg.types.map((t, i) => `<text class="kg-type" data-i="${i}" text-anchor="middle">${esc(t.text)}</text>`).join('') +
    kg.groups.map(gr => `<text class="kg-group" data-g="${gr.key}" text-anchor="middle">${esc(gr.text)}</text>`).join('');
  const nodeHtml = kg.nodes.map(n => `<g class="o-node" data-id="${esc(n.id)}" data-g="${n.key}" tabindex="0" role="button" aria-pressed="false" aria-label="${esc(n.kind)} ${esc(n.name)}">` +
    `<circle class="kg-hit" r="8"/><circle class="kg-ring" r="9"/><circle class="kg-dot" r="${KG.R}"/><title>${esc(n.kind)}\n${esc(n.name)}</title></g>`).join('');
  // 이름은 점과 다른 층에 둔다: 점의 묶음(g)에는 원만 있어 누르는 자리가 점 그대로이고, 이름은 모든 점 위에 그려진다
  const labelHtml = kg.nodes.map((n, i) => `<text class="kg-lbl lo" data-i="${i}">${esc(n.short)}</text>`).join('');
  const map = $('#ontoMap');
  map.innerHTML = `<svg class="kg-svg" role="group" aria-label="지식 지도"><defs><radialGradient id="kgHalo"><stop offset="0" stop-opacity=".36"/><stop offset="1" stop-opacity="0"/></radialGradient></defs>` +
    `<g class="kg-world"><circle class="kg-halo" r="${KG.HALO}" fill="url(#kgHalo)"/><g class="kg-edges">${blobHtml}${edgeHtml}</g><g class="kg-caps">${capHtml}</g><g class="kg-nodes">${nodeHtml}</g><g class="kg-labels" aria-hidden="true">${labelHtml}</g></g></svg>`;
  map.querySelectorAll('.o-node').forEach(el => { const n = kg.byId.get(el.dataset.id); n.el = el; n.hit = el.querySelector('.kg-hit'); n.dot = el.querySelector('.kg-dot'); n.ring = el.querySelector('.kg-ring'); });
  map.querySelectorAll('.kg-lbl').forEach(el => { kg.nodes[+el.dataset.i].lbl = el; });
  map.querySelectorAll('.kg-e').forEach(el => { kg.edges[+el.dataset.i].el = el; });
  map.querySelectorAll('.kg-type').forEach(el => { kg.types[+el.dataset.i].el = el; });
  kg.groups.forEach(gr => { gr.el = map.querySelector(`.kg-group[data-g="${gr.key}"]`); });
  // 층 칩(캔버스 아래쪽 — 범례를 겸한다): 항목이 있는 묶음만. 묶음별 개수는 오른쪽 칸에 있다
  $('#ontoLayers').innerHTML = kg.groups.map(gr => `<button type="button" class="cv-chip" data-layer="${gr.key}" data-g="${gr.key}" aria-pressed="true"><i></i>${esc(gr.text)}</button>`).join('');
  [...ent.hidden].forEach(key => { if (!kg.groups.some(gr => gr.key === key)) ent.hidden.delete(key); });
  const fresh = kg.key !== ent.graphAsset;
  kg.of = g; kg.key = ent.graphAsset;
  kgResize(fresh || !kg.moved);
  kg.ms = { layout: +(t1 - t0).toFixed(1), build: +(performance.now() - t1).toFixed(1), nodes: kg.nodes.length, edges: kg.edges.length };
}
// 캔버스 크기에 SVG 를 맞춘다. refit 이면 전체가 보이게 다시 맞춘다(사람이 옮기거나 확대한 뒤에는 그 보기를 지킨다)
function kgResize(refit) {
  const map = $('#ontoMap'), svg = map.querySelector('.kg-svg'); if (!svg || !kg.bounds) return;
  const w = map.clientWidth, h = map.clientHeight; if (!w || !h) return;
  kg.size = [w, h];
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.setAttribute('width', w); svg.setAttribute('height', h);
  const pad = { ...KG.PAD, b: Math.max(KG.PAD.b, ($('#ontoLayers').offsetHeight || 0) + 40) };      // 층 칩이 두 줄이 되면 그만큼 비운다
  const fit = fitView(kg.bounds, w, h, pad);
  kg.fitK = fit.k; kg.fit = fit;
  if (refit) { kg.view = { ...fit }; kg.moved = false; }
  kgApplyView();
}
function kgFit() { kg.moved = false; kgGlide(); kgResize(true); }
function kgGlide() { const world = $('#ontoMap .kg-world'); if (!world) return; world.classList.add('glide'); clearTimeout(kgGlide.timer); kgGlide.timer = setTimeout(() => world.classList.remove('glide'), 320); }
function kgZoomTo(k, cx, cy) {
  const v = kg.view, next = Math.max(Math.min(kg.fitK, 0.5), Math.min(KG.ZOOM_MAX, k));
  if (cx == null) { cx = kg.size[0] / 2; cy = kg.size[1] / 2; }
  kg.view = { k: next, tx: cx - (cx - v.tx) / v.k * next, ty: cy - (cy - v.ty) / v.k * next };
  kg.moved = true; kgApplyView();
}
function kgApplyView() {
  const map = $('#ontoMap'), world = map.querySelector('.kg-world'); if (!world) return;
  const { k, tx, ty } = kg.view;
  world.style.transform = `translate(${tx.toFixed(1)}px, ${ty.toFixed(1)}px)`;
  if (kgApplyView.k === k && kgApplyView.of === kg.of) return;      // 옮기기만 했으면 여기까지
  kgApplyView.k = k; kgApplyView.of = kg.of;
  map.querySelector('.kg-edges').setAttribute('transform', `scale(${k})`);
  for (const n of kg.nodes) n.el.setAttribute('transform', `translate(${(n.x * k).toFixed(1)} ${(n.y * k).toFixed(1)})`);
  for (const t of kg.types) { t.el.setAttribute('x', (t.x * k).toFixed(1)); t.el.setAttribute('y', (t.y * k - 9).toFixed(1)); }
  for (const gr of kg.groups) { gr.el.setAttribute('x', (gr.capX * k).toFixed(1)); gr.el.setAttribute('y', (gr.capY * k - 24).toFixed(1)); }
  kgSizes(); kgHalo(); kgPlaceLabels();
}
// 점의 반지름: 고른 것 11, 밝은 것은 보통보다 2 크게, 보통은 배율에 따라 3.5 ~ 5(연결이 많으면 조금 더).
// 누르는 자리(kg-hit)는 점보다 넓되 이웃 점의 자리와 겹치지 않게 이웃 사이의 절반까지만 넓힌다
function kgSizes() {
  const base = kgDotR(kg.view.k), reach = Math.min(12, KG.SP * kg.view.k * 0.46);
  for (const n of kg.nodes) {
    const hub = n.deg >= 12 ? 1.5 : n.deg >= 6 ? 0.75 : 0;
    const r = !n.cls ? base + hub : n.cls.includes(' sel') ? KG.R_SEL : /(near|path|match)/.test(n.cls) ? base + 2 : base + hub;
    const hit = Math.max(r + 1, reach);
    if (n.r !== r) { n.r = r; n.dot.setAttribute('r', r); n.ring.setAttribute('r', r + 4); }
    if (n.hitR !== hit) { n.hitR = hit; n.hit.setAttribute('r', hit.toFixed(1)); }
  }
}
function kgHalo() {
  const halo = $('#ontoMap .kg-halo'); if (!halo) return;
  const lit = kg.byId.get(ent.sel) || (ent.focus && kg.byId.get(ent.focus)) || null;
  const on = !!lit && !ent.hidden.has(lit.key);
  halo.classList.toggle('on', on);
  if (on) { halo.setAttribute('cx', (lit.x * kg.view.k).toFixed(1)); halo.setAttribute('cy', (lit.y * kg.view.k).toFixed(1)); $('#kgHalo').dataset.g = lit.key; }
}
// 지금 상태(고름 · 경로 · 검색 · 끈 묶음)를 화면에 입힌다. DOM 을 다시 만들지 않고 클래스와 반지름만 바꾼다
function kgApplyState() {
  if (!kg.of) return;
  const q = ent.search.trim().toLowerCase();
  if (ent.sel != null && (!kg.byId.has(ent.sel) || ent.hidden.has(kg.byId.get(ent.sel).key))) ent.sel = null;      // 끈 묶음의 항목은 고른 채로 두지 않는다
  const path = focusSet();
  const match = new Set(q ? kg.nodes.filter(n => !ent.hidden.has(n.key) && (n.name.toLowerCase().includes(q) || n.id.toLowerCase().includes(q))).map(n => n.id) : []);
  const s = { sel: ent.sel, near: ent.sel != null ? kg.adj.get(ent.sel) : new Set(), path, match, query: !!q };
  kg.state = s;
  for (const n of kg.nodes) {
    const cls = kgNodeClass(n.id, s) + (ent.hidden.has(n.key) ? ' off' : '');
    if (n.cls !== cls) { n.cls = cls; n.el.setAttribute('class', cls); n.el.setAttribute('aria-pressed', String(n.id === s.sel)); }
  }
  const edgesBox = $('#ontoMap .kg-edges'), raise = [];
  for (const e of kg.edges) {
    const cls = kgEdgeClass(e.a.id, e.b.id, s) + (ent.hidden.has(e.a.key) || ent.hidden.has(e.b.key) ? ' off' : '');
    if (e.cls !== cls) { e.cls = cls; e.el.setAttribute('class', cls); }
    if (cls === 'kg-e hot') { e.el.dataset.g = (e.a.id === s.sel ? e.b : e.a).key; raise.push(e.el); }      // 밝은 선은 상대 항목의 묶음 색
    else if (cls === 'kg-e path') raise.push(e.el);
  }
  raise.forEach(el => edgesBox.append(el));                                                                  // 밝은 선을 흐린 선 위에 그린다
  $('#ontoMap').querySelectorAll('.kg-blob').forEach(c => c.classList.toggle('off', ent.hidden.has(c.dataset.g)));
  $('#ontoLayers').querySelectorAll('[data-layer]').forEach(b => b.setAttribute('aria-pressed', String(!ent.hidden.has(b.dataset.layer))));
  kg.matches = kg.nodes.filter(n => match.has(n.id)).map(n => n.id);
  if (kg.matchAt >= kg.matches.length) kg.matchAt = 0;
  kgSizes(); kgHalo(); kgPlaceLabels();
  const fmtN = v => Number(v).toLocaleString('ko-KR'), word = ent.search.trim();
  $('#ontoHint').textContent = s.sel != null ? '고른 항목과 바로 이어진 것만 밝게 보입니다'
    : path ? `「${kg.byId.get(ent.focus)?.name || ''}」에서 조치 방법까지 가는 길의 항목 ${fmtN(path.size)}개가 밝게 보입니다`
    : q ? (match.size ? `이름에 「${word}」이 든 항목 ${fmtN(match.size)}개가 밝게 보입니다` : `이름에 「${word}」이 든 항목이 없습니다`)
    : '항목을 누르면 바로 이어진 것만 밝게 보입니다';
  $('#ontoStats').textContent = `항목 ${fmtN(kg.of.nodes.length)} · 연결 ${fmtN(kg.of.edges.length)}` + (path ? ` · 강조 경로 ${fmtN(path.size)}개` : '') + (q ? ` · 검색 결과 ${fmtN(match.size)}개` : '');
  const next = $('#ontoNext'); next.hidden = match.size < 2; next.textContent = `다음 찾기 ${Math.min(kg.matchAt + 1, match.size)} / ${match.size}`;
  ontoNote(ent.definitionNamesError ? ent.definitionNamesError + ' 흐름 항목의 이름이 「흐름 이름 확인 불가」로 보입니다. [다시 읽기]를 누르세요.' : '');
}
// 보일 글자를 다시 고른다(배율 · 상태가 바뀔 때). 차례: 고른 항목 → 묶음 이름 → 이어진 것 · 검색 · 경로 → 종류 이름 → 나머지(연결이 많은 것부터)
function kgPlaceLabels() {
  if (!kg.of || !kg.state) return;
  const k = kg.view.k, s = kg.state;
  const prio = n => n.id === s.sel ? 9e6 : (s.near.has(n.id) ? 6e6 : s.match.has(n.id) ? 5e6 : s.path && s.path.has(n.id) ? 4e6 : n.cls.includes(' far') ? -1e3 : 0) + n.deg;
  const items = kg.nodes.filter(n => !ent.hidden.has(n.key)).map(n => ({ id: n.id, x: n.x * k, y: n.y * k, r: n.r, w: n.id === s.sel ? kgTextW(n.short, 14) : n.w, prio: prio(n), top: n.id === s.sel, lit: /(sel|near|path|match)/.test(n.cls) }));
  const caps = [];
  kg.groups.forEach(gr => { if (!ent.hidden.has(gr.key)) caps.push({ id: 'group:' + gr.key, box: [gr.capX * k - gr.w / 2, gr.capY * k - 35, gr.capX * k + gr.w / 2, gr.capY * k - 21], prio: 8e6, lit: true }); });
  kg.types.forEach((t, i) => { if (!ent.hidden.has(t.key)) caps.push({ id: 'type:' + i, box: [t.x * k - t.w / 2, t.y * k - 20, t.x * k + t.w / 2, t.y * k - 6], prio: 3e6 + t.count }); });
  // 이름이 캔버스 밖으로 나가지 않게: 화면에 맞췄을 때 배치 좌우에 남는 폭 안에서만 쓴다
  const [w] = kg.size, f = kg.fit || kg.view;
  const sides = pickLabels(items.concat(caps), kg.bounds.x0 * k - (f.tx + kg.bounds.x0 * f.k - 8), kg.bounds.x1 * k + (w - f.tx - kg.bounds.x1 * f.k - 8));
  for (const n of kg.nodes) {
    const side = sides.get(n.id) || '', gap = n.r + 6, x = n.x * k, y = n.y * k;
    // 자리를 못 잡은 이름(lo)은 숨겨 두고, 점에 마우스를 올리거나 탭으로 가면 오른쪽에 보인다(initOntology 의 hover)
    const cls = 'kg-lbl' + n.cls.slice('o-node'.length) + (side ? '' : ' lo') + (n.hover ? ' hover' : '');
    const at = side === 'T' ? [x, y - n.r - 9, 'middle'] : side === 'L' ? [x - gap, y + 4, 'end'] : [x + gap, y + 4, 'start'];
    const sig = cls + '|' + at.join('|');
    if (n.lblSig === sig) continue;
    n.lblSig = sig;
    n.lbl.setAttribute('class', cls); n.lbl.setAttribute('x', at[0].toFixed(1)); n.lbl.setAttribute('y', at[1].toFixed(1)); n.lbl.setAttribute('text-anchor', at[2]);
  }
  kg.groups.forEach(gr => gr.el.classList.toggle('off', !sides.has('group:' + gr.key)));
  kg.types.forEach((t, i) => t.el.classList.toggle('off', !sides.has('type:' + i)));
}
function drawGraph() {
  const g = ent.graph; if (!g) return;
  if (kg.of !== g) kgBuild(g);
  kgApplyState();
  renderNodePanel();
}
function kgPick(id) {
  ent.sel = id == null || ent.sel === id ? null : id;
  kgApplyState(); renderNodePanel();
}
// 그 항목이 캔버스 안(도구 · 칩에 가리지 않는 곳)에 보이게 지도를 옮긴다. 이미 보이면 그대로 둔다(always 면 늘 가운데로)
function kgReveal(id, always) {
  const n = kg.byId.get(id); if (!n) return;
  const { k, tx, ty } = kg.view, [w, h] = kg.size, sx = n.x * k + tx, sy = n.y * k + ty;
  if (!always && sx > 24 && sx < w - 24 && sy > 52 && sy < h - 56) return;
  kg.view = { k, tx: w / 2 - n.x * k, ty: h / 2 - n.y * k }; kg.moved = true;
  kgGlide(); kgApplyView();
}
// 통계 줄 아래의 오류 한 줄(흐름 이름 읽기 실패) — 회색 통계 글에 이어 붙이지 않는다
function ontoNote(text) { const n = $('#ontoNote'); n.textContent = text; n.hidden = !text; }

/* ---------------- 오른쪽 상세 칸(밝은 틀): 종류 → 이름 → 설명 → 속성 → 이어진 것을 뜻별로 ---------------- */
function renderNodePanel() {
  const box = $('#ontoNode');
  const g = ent.graph; if (!g) { box.innerHTML = ''; return; }
  const n = ent.sel != null ? g.nodes.find(x => String(x.id) === ent.sel) : null;
  const sig = JSON.stringify([ent.graphAsset, ent.sel, g.nodes.length, g.edges.length, UI.namesVersion, ent.definitionNamesError]);
  if (box.dataset.sig === sig && box.innerHTML) return;      // 검색 · 확대처럼 고른 항목이 그대로인 동안에는 다시 그리지 않는다(읽던 자리 · 편 접기가 유지된다)
  box.dataset.sig = sig;
  if (!n) {
    // 아무것도 고르지 않았을 때: 지도 읽는 법 한 줄과 묶음별 개수
    const counts = {}; g.nodes.forEach(x => { counts[x.label] = (counts[x.label] || 0) + 1; });
    const rows = ONTO_GROUPS.map((gr, gi) => {
      const labels = gr.other ? Object.keys(counts).filter(l => groupOf(l) === gi).sort() : gr.labels.filter(l => counts[l]);
      const total = labels.reduce((sum, l) => sum + counts[l], 0);
      return total ? `<li data-g="${gr.key}"><span class="kg-kind"><i></i>${esc(gr.title)}</span><b class="num">${total}</b><small>${labels.map(l => `${esc(LABEL_KO[l] || l)} ${counts[l]}`).join(' · ')}</small></li>` : '';
    }).join('');
    box.innerHTML = `<section><p class="label">지도 읽는 법</p><p class="kg-lead">점 하나가 항목 하나이고 색이 묶음입니다. 같은 종류끼리 모여 있습니다. 항목을 누르면 그 항목과 바로 이어진 것만 밝게 보입니다. 빈 곳을 끌어 옮기고 휠로 확대하면 이름이 더 보입니다.</p></section>` +
      `<section><p class="label">묶음별 항목</p><ul class="kg-counts">${rows}</ul></section>`;
    return;
  }
  const me = kg.byId.get(ent.sel), group = ONTO_GROUPS[groupOf(n.label)];
  const lead = n.props?.description || '';                 // 한 줄 설명은 서버가 준 값이 있을 때만(화면이 지어 붙이지 않는다)
  const props = Object.entries(n.props || {}).filter(([k]) => !['id', 'name', 'description'].includes(k));
  const named = props.filter(([k]) => PROP_KO[k]), other = props.filter(([k]) => !PROP_KO[k]);
  const byId = id => g.nodes.find(y => y.id === id) || { id };
  // 이어진 것을 뜻으로 묶는다. 관계 이름표(RELATION_KO)는 나가는 쪽에서 본 말이라(증상 → 고장 「나타내는 고장」) 들어오는 쪽에 그대로 붙이면
  // 거꾸로 읽힌다 — 나가는 관계는 관계 이름으로, 들어오는 관계는 상대의 종류(증상 · 원인 …)로 묶고 관계 이름은 작게 곁들인다.
  // 방향이 다르면 이름이 같아도 다른 묶음이다(공급사 · 설비 · 규칙처럼 관계 이름과 종류 이름이 같은 낱말인 것이 있다)
  const groups = new Map();
  const add = (dir, title, o, note) => { const key = dir + title; if (!groups.has(key)) groups.set(key, { title, items: [] }); groups.get(key).items.push({ other: o, note }); };
  g.edges.filter(e => e.from === n.id).forEach(e => { const o = byId(e.to); add('out:', RELATION_KO[e.type] || e.type, o, LABEL_KO[o.label] || o.label || ''); });
  g.edges.filter(e => e.to === n.id).forEach(e => { const o = byId(e.from); add('in:', LABEL_KO[o.label] || o.label || '이어진 항목', o, RELATION_KO[e.type] || e.type); });
  const keyOf = o => { const gi = groupOf(o.label); return gi >= 0 ? ONTO_GROUPS[gi].key : ''; };
  const groupHtml = [...groups.values()].map(({ title, items }) => {
    const notes = [...new Set(items.map(i => i.note).filter(Boolean))], keys = [...new Set(items.map(i => keyOf(i.other)))];
    const one = notes.length === 1 && notes[0] !== title ? ` <span class="rel-note">${esc(notes[0])}</span>` : '';
    return `<section class="rel-group" data-g="${keys.length === 1 ? keys[0] : ''}"><h4><i></i>${esc(title)} <span class="n">${items.length}</span>${one}</h4>
      <ul class="rels">${items.map(i => `<li><a href="#" data-go="${esc(i.other.id)}"><span>${esc(nodeName(i.other))}</span>${notes.length > 1 && i.note ? `<small>${esc(i.note)}</small>` : ''}</a></li>`).join('')}</ul></section>`;
  }).join('');
  const value = v => { const text = typeof v === 'string' ? v : typeof v === 'boolean' ? (v ? '예' : '아니요') : Array.isArray(v) && v.every(x => typeof x !== 'object') ? v.join(', ') : typeof v === 'number' ? String(v) : JSON.stringify(v); return text.length > 160 ? UI.fold(esc(text.slice(0, 60)) + '…', `<div class="kv-long">${esc(text)}</div>`, { cls: 'small' }) : esc(text); };
  box.innerHTML = `<section class="node-head" data-g="${group.key}"><span class="kg-kind o-kind"><i></i>${esc(LABEL_KO[n.label] || n.label)} · ${esc(group.title)}</span><h2>${esc(nodeName(n))}</h2>` +
    (lead ? `<p class="kg-lead">${esc(UI.words(lead))}</p>` : '') +
    `<dl class="kv"><dt>이어진 항목</dt><dd class="num">${me ? kg.adj.get(me.id).size : 0}</dd>${named.map(([k, v]) => `<dt>${esc(PROP_KO[k])}</dt><dd>${value((PROP_VALUE_KO[k] || {})[v] || v)}</dd>`).join('')}</dl>` +
    (['Process', 'ProcessVersion'].includes(n.label) ? UI.metaFold([['흐름 식별자', esc(n.id)]]) : '') +
    (other.length ? UI.fold(`그 밖의 속성 ${other.length}개 (원래 이름)`, '<dl class="kv">' + other.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${value(v)}</dd>`).join('') + '</dl>', { cls: 'small' }) : '') + '</section>' +
    `<section class="node-rels">${groupHtml || `<p class="kg-lead">이어진 항목이 없습니다</p>`}</section>`;
  box.scrollTop = 0;
  box.querySelectorAll('[data-go]').forEach(a => a.addEventListener('click', ev => { ev.preventDefault(); const id = a.dataset.go; ent.sel = null; kgPick(id); kgReveal(id); }));
}
function initOntology() {
  const map = $('#ontoMap');
  new ResizeObserver(() => { if (kg.of && (map.clientWidth !== kg.size[0] || map.clientHeight !== kg.size[1])) kgResize(!kg.moved); }).observe(map);
  // 끌어서 옮기기 · 두 손가락으로 확대(터치) · 누르면 고르기. 4px 넘게 움직였을 때만 끌기로 본다(누르기와 구분)
  const ptr = new Map(); let drag = null, pinch = null, dragged = false;
  map.addEventListener('pointerdown', ev => {
    if (ev.button > 0 || !kg.of) return;
    ptr.set(ev.pointerId, [ev.clientX, ev.clientY]);
    if (ptr.size === 1) { drag = { id: ev.pointerId, x: ev.clientX, y: ev.clientY, tx: kg.view.tx, ty: kg.view.ty, on: false }; dragged = false; }
    else if (ptr.size === 2) { const [p, q] = [...ptr.values()]; pinch = { d: kgDist(p[0], p[1], q[0], q[1]) || 1, k: kg.view.k }; drag = null; dragged = true; }
  });
  map.addEventListener('pointermove', ev => {
    if (!ptr.has(ev.pointerId)) return;
    ptr.set(ev.pointerId, [ev.clientX, ev.clientY]);
    if (pinch && ptr.size === 2) { const [p, q] = [...ptr.values()], box = map.getBoundingClientRect(); kgZoomTo(pinch.k * kgDist(p[0], p[1], q[0], q[1]) / pinch.d, (p[0] + q[0]) / 2 - box.left, (p[1] + q[1]) / 2 - box.top); return; }
    if (!drag || drag.id !== ev.pointerId) return;
    const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
    if (!drag.on) { if (Math.abs(dx) + Math.abs(dy) < 4) return; drag.on = true; dragged = true; map.setPointerCapture(ev.pointerId); map.classList.add('dragging'); }
    kg.view = { k: kg.view.k, tx: drag.tx + dx, ty: drag.ty + dy }; kg.moved = true; kgApplyView();
  });
  const end = ev => { ptr.delete(ev.pointerId); if (ptr.size < 2) pinch = null; if (drag && drag.id === ev.pointerId) { map.classList.remove('dragging'); drag = null; } };
  map.addEventListener('pointerup', end); map.addEventListener('pointercancel', end);
  map.addEventListener('click', ev => {
    if (dragged) { dragged = false; return; }
    const node = ev.target.closest('.o-node');
    if (node) kgPick(node.dataset.id); else if (ent.sel != null && ev.target.closest('.kg-svg')) kgPick(null);      // 빈 곳을 누르면 고른 것이 풀린다
  });
  map.addEventListener('wheel', ev => {
    if (!kg.of) return;
    ev.preventDefault();
    const box = map.getBoundingClientRect(), dy = ev.deltaMode === 1 ? ev.deltaY * 32 : ev.deltaY;
    kgZoomTo(kg.view.k * Math.exp(-dy * 0.0016), ev.clientX - box.left, ev.clientY - box.top);
  }, { passive: false });
  // 키보드: 탭으로 항목을 돌고 Enter · 스페이스로 고른다. 화살표로 옮기고 + · − 로 확대 · 축소, 0 은 화면에 맞춤, Esc 는 고른 것 풀기
  map.addEventListener('keydown', ev => {
    if (!kg.of || ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const node = ev.target.closest('.o-node');
    if (node && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); kgPick(node.dataset.id); return; }
    const move = { ArrowLeft: [48, 0], ArrowRight: [-48, 0], ArrowUp: [0, 48], ArrowDown: [0, -48] }[ev.key];
    if (move) { ev.preventDefault(); kg.view = { k: kg.view.k, tx: kg.view.tx + move[0], ty: kg.view.ty + move[1] }; kg.moved = true; kgApplyView(); }
    else if (ev.key === '+' || ev.key === '=') { ev.preventDefault(); kgZoomTo(kg.view.k * 1.25); }
    else if (ev.key === '-') { ev.preventDefault(); kgZoomTo(kg.view.k / 1.25); }
    else if (ev.key === '0') { ev.preventDefault(); kgFit(); }
    else if (ev.key === 'Escape' && ent.sel != null) { ev.preventDefault(); kgPick(null); }
  });
  // 숨은 이름: 점에 마우스를 올리거나 탭으로 가면 그 점의 이름을 보인다
  const hover = (ev, on) => { const node = ev.target.closest('.o-node'), n = node && kg.byId.get(node.dataset.id); if (n && !!n.hover !== on) { n.hover = on; n.lbl.classList.toggle('hover', on); } };
  map.addEventListener('pointerover', ev => hover(ev, true));
  map.addEventListener('pointerout', ev => hover(ev, false));
  map.addEventListener('focusin', ev => { const node = ev.target.closest('.o-node'); if (node && node.matches(':focus-visible')) { hover(ev, true); kgReveal(node.dataset.id); } });
  map.addEventListener('focusout', ev => hover(ev, false));
  $('#ontoZoomOut').addEventListener('click', () => { if (kg.of) { kgGlide(); kgZoomTo(kg.view.k / 1.25); } });
  $('#ontoZoomIn').addEventListener('click', () => { if (kg.of) { kgGlide(); kgZoomTo(kg.view.k * 1.25); } });
  $('#ontoFit').addEventListener('click', () => { if (kg.of) kgFit(); });
  // 층 칩: 누르면 그 묶음을 끄고 켠다
  $('#ontoLayers').addEventListener('click', ev => {
    const b = ev.target.closest('[data-layer]'); if (!b) return;
    ent.hidden.has(b.dataset.layer) ? ent.hidden.delete(b.dataset.layer) : ent.hidden.add(b.dataset.layer);
    kgApplyState(); renderNodePanel();
  });
  $('#ontoAsset').addEventListener('change', () => loadGraph(true));
  $('#ontoNs').addEventListener('change', () => { ent.sel = null; loadGraph(true); });
  $('#ontoFocus').addEventListener('change', ev => { ent.focus = ev.target.value || null; ent.sel = null; drawGraph(); if (ent.focus) kgReveal(ent.focus); });
  // 이름 검색: 치는 대로 걸린 항목이 밝아지고 첫 항목이 보이게 옮긴다. Enter · [다음 찾기]는 다음 항목으로(Shift+Enter 는 앞 항목으로)
  const goMatch = step => { if (!kg.matches.length) return; kg.matchAt = (kg.matchAt + step + kg.matches.length) % kg.matches.length; kgApplyState(); kgReveal(kg.matches[kg.matchAt], true); };
  $('#ontoSearch').addEventListener('input', ev => { ent.search = ev.target.value; kg.matchAt = 0; drawGraph(); if (kg.matches.length) kgReveal(kg.matches[0]); });
  $('#ontoSearch').addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); goMatch(ev.shiftKey ? -1 : 1); } });
  $('#ontoNext').addEventListener('click', () => goMatch(1));
  $('#ontoReload').addEventListener('click', () => loadGraph(true));
  // 질의 보기(문서 등록 화면 아래의 접기): 지식 지도를 읽는 질의문을 종류별로 보인다
  document.querySelectorAll('#ontoTpl button').forEach(b => b.addEventListener('click', async () => {
    try { const t = await getJ(API.agent + '/api/ontology/template/' + b.dataset.t); $('#ontoTplText').textContent = t.text; }
    catch (e) { $('#ontoTplText').textContent = UI.t('error.load') + ': ' + e.message; }
  }));
}

/* ================================================= action candidate cards (shared with hitl.js and instances.js) */
function signNum(v) { return (v > 0 ? '+' : '') + Number(v).toFixed(2); }
function effChip(x, cls) {
  const t = `${x.name} ${x.dir === 1 ? '↑' : '↓'}${x.owner ? ' · ' + x.owner : ''}`;
  return `<span class="${cls}" title="영향 강도 ${x.weight}${x.conds && x.conds.length ? ' · 조건: ' + x.conds.join(', ') : ''}">${esc(t)}</span>`;
}
function ruleChip(r, cls, label) {
  return `<span class="${cls}" title="${esc((r.when || '') + (r.sources && r.sources.length ? ' · 근거 ' + r.sources.join(', ') : ''))}">${esc(label)} · ${esc(UI.ruleLabel(r))}${r.annotation || UI.names[r.rule] ? '' : UI.fold('규칙 원문',`<pre>${esc(JSON.stringify(r,null,2))}</pre>`,{cls:'small'})}</span>`;
}
// FAN_SET=100 → "팬 100 %" (명칭표 "카드"): the action code and target stay in the evidence fold
const ACTION_KO = { FAN_SET: ['팬', ' %'], LOAD_SET: ['부하', ' %'], PUMP_SELECT: ['펌프', ''], WO_CREATE: [null, ''], PR_CREATE: ['구매 요청', ''] };
function actionLabel(a, option) {
  const spec = ACTION_KO[a.code];
  if (spec && spec[0] === null) return UI.t('workOrder');
  // 값이 id 면 이름으로 — 숫자 값(팬 % 등)은 그대로. 구매 요청의 공급사(sup:…)는 그래프 시드가 아니라 업무 DB 동기화로 생겨 이름 사전에 없다:
  // 그 카드가 정한 공급사의 견적 이름(resolvedSupplier.quote.name — 업무 DB ent.suppliers.name)으로
  const resolved = option && option.resolvedSupplier;
  const supplier = a.code === 'PR_CREATE' && resolved && resolved.id === a.value && resolved.quote && resolved.quote.name;
  const value = supplier || (a.value != null ? UI.idText(String(a.value)) : null);
  if (spec) return `${spec[0]}${value != null ? ' ' + value + spec[1] : ''}`;
  return `${a.name || a.code}${value != null ? ' ' + value : ''}`;
}
function forecastLine(o) {
  const ts1 = (o.forecast || []).find(f => /유온|ts1/i.test(f.name || ''));
  if (ts1 && Number.isFinite(Number(ts1.value))) return `${UI.t('card.forecastTs1')} <b>${Number(ts1.value).toFixed(0)} ℃</b>`;
  const f = (o.forecast || [])[0];
  return f ? `${esc(f.name)} <b>${esc(f.value)}${esc(f.unit || '')}</b>` : '';
}
// 머리말 값: 예측이 고르는 근거인 안만 예측, 아니면 이 안의 업무 값(규칙은 approvalCard.js forecastDecides · ownValues 한 곳)
// decision: 같은 판단 {options, facts} — 카드 한 장만으로는 "안마다 예측이 갈리는가"를 알 수 없다
function headValue(o, decision) {
  if (!decision || !Array.isArray(decision.options)) throw new Error('cardHtml: opt.decision({options, facts})이 필요합니다');
  if (hydApprove.forecastDecides(o, decision.options)) return forecastLine(o);
  const v = hydApprove.ownValues(o, decision);
  return v.length ? `이 안의 값 <b>${esc(v.join(' · '))}</b>` : '';
}
function forecastContextHtml(c) {
  if (!c) return '';
  if (c.error) return `<p class="neg">${esc(c.error)}</p>`;
  const val = k => Number.isFinite(c.values?.[k]) ? Number(c.values[k]).toFixed(1) : '미확인';
  const inputLabels = { ts1: '현재 유온 ℃', t_amb: '주변 온도 ℃', fan_pct: '팬 %', load_pct: '부하 %', cooler_health: '냉각 성능 비율', leak: '누설 비율', bearing_wear: '베어링 마모', state: '설비 상태', pump: '운전 펌프' };
  return `<p>${esc(c.horizon_s)}초 뒤 유온 ${val('ts1')} ℃ · 압력 ${val('ps1')} bar · 진동 ${val('vs1')} mm/s · 구간 최대 유온 ${val('ts1_peak')} ℃</p>
    <p class="muted">설비 예측 모델의 계산입니다. 지금의 열화와 주변 온도가 그대로 유지된다는 조건이며, 조치 뒤 다시 잰 값이 아닙니다. 모델 ${esc(c.model_id)} · 판본 ${esc(c.model_revision)} · 입력 시점 ${esc(UI.dateTime(c.source_t))}</p>
    <p class="muted">${Object.entries(inputLabels).map(([k, label]) => `${label} ${esc(c.inputs?.[k] ?? '미확인')}`).join(' · ')}</p>`;
}
function cardHtml(o, opt = {}) {
  const evaluation=UI.evaluationInfo(o,opt.decision), blocked=UI.executionBlocked(o,opt.decision);
  const hasCmd = (o.actions || []).some(a => a.kind === 'command'), hasTx = (o.actions || []).some(a => a.kind !== 'command');
  const uncond = x => !x.conditional, cond = x => x.conditional;
  const sp = o.scoreParts || {};
  const scoreLabels = { bsc: UI.t('score.bsc'), forecast: UI.t('score.forecast'), warn: UI.t('score.warn'), penalty: UI.t('score.penalty'), precedent: UI.t('score.precedent'), delivery: UI.t('score.delivery'), quality: UI.t('score.quality') };
  const ranking = o.rankingEvidence;
  const chips = [o.id === opt.rec ? UI.chipText(evaluation.state==='analysis' ? '모의 1순위' : UI.t('chip.recommended'), 'accent') : '', hasCmd ? UI.chipText(UI.t('chip.control'), 'neutral') : '', hasTx ? UI.chipText(UI.t('chip.workOrder'), 'warning') : '',
    o.id === opt.chosen ? UI.chipText(UI.t('chip.chosen'), 'success') : '', o.feasible ? '' : UI.chipText(UI.t('chip.excluded'), 'danger')].join('');
  const line = [headValue(o, opt.decision), `${esc(UI.t('card.approver'))} <b>${esc((o.approver || {}).name || '–')}</b>`, o.precedent && o.precedent.n ? `${esc(UI.t('card.precedent'))} <b>${o.precedent.n}건 (${Math.round(o.precedent.share * 100)} %)</b> <span class="muted">${esc(UI.t('card.precedentFixed'))}</span>` : ''].filter(Boolean).map(x => `<span>${x}</span>`).join('');
  // A141: 성과 지표 칩 묶음 · 감점/경고 칩 · 절차 번호는 근거 접기 안으로 (화면에는 행동 근거인 점수 · 예상 유온 · 승인 역할 · 제외 사유만)
  const kpiAll = `<span class="hkpi">${(o.gains || []).filter(uncond).map(x => effChip(x, 'pos')).join('')}${(o.losses || []).filter(uncond).map(x => effChip(x, 'neg')).join('')}</span>`;
  const softAll = `${(o.penalties || []).map(v => ruleChip(v, 'soft', `${UI.t('card.penalty')} ${v.penalty}`)).join('')}${(o.warnings || []).map(v => ruleChip(v, 'soft', UI.t('card.warn'))).join('')}`;
  const evidence = `
    ${o.reviewed_choice ? `<p><b>${esc(UI.t('card.baseSop'))}</b> ${esc(o.reviewed_choice.reference_name || o.sopId)} · ${(o.reviewed_choice.reference_actions || []).map(a => esc(actionLabel(a, o))).join(' · ')}</p>` : ''}
    <dl>${o.sopId ? `<div><dt>${esc(UI.t('card.sop'))}</dt><dd>${esc(o.sopId)}</dd></div>` : ''}
    <div><dt>${esc(UI.t('card.score'))}</dt><dd>${Object.entries(sp).map(([key, value]) => `${esc(scoreLabels[key] || key)} ${Number.isFinite(value) ? signNum(value) : '미확인'}`).join(' · ') || '–'}</dd></div>
    ${(o.gains || []).some(uncond) || (o.losses || []).some(uncond) ? `<div><dt>${esc(UI.t('fold.kpi'))}</dt><dd>${kpiAll}</dd></div>` : ''}
    ${softAll ? `<div><dt>${esc(UI.t('fold.penalty'))}</dt><dd><span class="hmeta">${softAll}</span></dd></div>` : ''}
    <div><dt>${esc(UI.t('skill.actions'))}</dt><dd>${(o.actions || []).map(a => `${esc(actionLabel(a, o))} <span class="muted">(${esc(a.code)}${a.value != null ? '=' + esc(a.value) : ''}${a.targetName ? ' → ' + esc(a.targetName) : ''})</span>`).join(' · ') || esc(UI.t('card.noAction'))}</dd></div>
    ${(o.forecast || []).length ? `<div><dt>${esc(UI.t('score.forecast'))}</dt><dd>${(o.forecast || []).map(f => `<span title="계산 방법: ${esc(f.method)}">${esc(f.name)} ${esc(f.value)}${esc(f.unit || '')}</span>`).join(' · ')}</dd></div>` : ''}
    ${(o.gains || []).some(cond) || (o.losses || []).some(cond) ? `<div><dt>${esc(UI.t('card.expected'))}</dt><dd><span class="hkpi">${(o.gains || []).filter(cond).map(x => effChip(x, 'pos')).join('')}${(o.losses || []).filter(cond).map(x => effChip(x, 'neg')).join('')}</span></dd></div>` : ''}
    ${(o.selectedBy || []).length ? `<div><dt>${esc(UI.t('skill.rules'))}</dt><dd>${(o.selectedBy || []).map(r => `${esc(UI.ruleLabel(r))}${(r.sources || []).length ? ` <span class="muted">(${esc(r.sources.join(', '))})</span>` : ''}${r.annotation || UI.names[r.rule] ? '' : UI.fold('규칙 원문',`<pre>${esc(JSON.stringify(r,null,2))}</pre>`,{cls:'small'})}`).join('<br>')}</dd></div>` : ''}
    ${(o.steps || []).length ? `<div><dt>${esc(UI.t('card.steps'))}</dt><dd><ol class="dc-steps">${(o.steps || []).map(s => `<li>${esc(UI.idText(s.text))}${s.manual ? ` <span class="muted" title="${esc(s.manual.excerpt || '')}">[${esc(s.manual.ref)} ${esc(s.manual.title || '')}]</span>` : ''}</li>`).join('')}</ol></dd></div>` : ''}
    ${o.precedent && o.precedent.reasons && o.precedent.reasons.length ? `<div><dt>${esc(UI.t('card.precedent'))}</dt><dd>${o.precedent.reasons.map(esc).join(' / ')}</dd></div>` : ''}</dl>
    ${o.forecastContext ? UI.fold(esc(UI.t('card.forecastLimits')), forecastContextHtml(o.forecastContext), { cls: 'small' }) : ''}
    ${ranking ? UI.fold(esc(UI.t('card.scoreHow')), `${Object.entries(ranking.policy?.components || {}).map(([key, expr]) => `<div>${esc(scoreLabels[key] || key)}: <code>${esc(expr)}</code> = ${esc(sp[key])}</div>`).join('')}<div class="muted">${esc(ranking.conditionMode || '')}</div>`, { cls: 'small' }) : ''}
    ${(o.tradeoffEvaluation || []).length ? UI.fold(`${esc(UI.t('kpi'))} 경로와 조건 판정 ${o.tradeoffEvaluation.length}건`, o.tradeoffEvaluation.map(p => `<div><b>${esc(CHECK_STATUS[p.status] || p.status)}</b> ${esc(p.name)} · 강도 ${esc(p.weight)}<br><span class="muted">${esc((p.nodes || []).join(' → '))}</span>${(p.checks || []).filter(c => c.description || c.status !== 'TRUE').map(c => `<p>${esc(c.description)} · ${esc(CHECK_STATUS[c.status] || c.status)}<br>${Object.entries(c.inputs || {}).map(([alias, v]) => `<span title="${esc(alias)} · ${esc(v.variable)}">${esc(v.source === 'forecast' ? '후보 예측' : '현재 사실')} ${esc(window.hydWords.fieldName(v.variable))} = ${esc(v.value == null ? '미확인' : factValue(v.variable, v.value))}</span>`).join(' · ')}${c.error ? `<br>${esc(c.error)}` : ''}</p>`).join('')}</div>`).join(''), { cls: 'small' }) : ''}`;
  const head = `<span class="hrank">${o.feasible ? o.rank : '–'}</span>
    <span class="hbody"><span class="htitle">${esc(UI.idText(o.name))} ${chips}</span>
      ${o.description ? `<span class="hsub">${esc(UI.idText(o.description))}</span>` : ''}
      <span class="hbar"><i style="width:${Math.min(100, Math.round(Math.abs(o.score || 0) / (opt.maxAbs || 1) * 100))}%" class="${(o.score || 0) >= 0 ? 'pos' : 'neg'}"></i><b class="num">${esc(UI.t('card.score'))} ${signNum(o.score || 0)}</b></span>
      <span class="hline">${line}</span>
      ${UI.evaluationHtml(o,opt.decision)}
      ${window.hydWords?.purchaseContextHtml(o,opt.decision) || ''}
      ${window.hydWords?.maintenanceHtml(o) || ''}
      ${(o.violations || []).length ? `<span class="hmeta">${ruleChip(o.violations[0], 'hard', UI.t('chip.excluded'))}${o.violations.length > 1 ? `<span class="muted">+${o.violations.length - 1}</span>` : ''}</span>` : ''}
      ${o.money && window.hydWhatif ? hydWhatif.moneyFold(o.money) : ''}
      ${UI.fold(esc(UI.t('card.evidence')), ((o.violations || []).length > 1 ? `<p><b>${esc(UI.t('fold.violations'))}</b> <span class="hmeta">${o.violations.map(v => ruleChip(v, 'hard', UI.t('chip.excluded'))).join('')}</span></p>` : '') + evidence, { cls: 'small' })}
    </span>`;
  if (!opt.selectable) return `<div class="hopt ${o.feasible ? '' : 'out'} ${o.id === opt.rec ? 'rec' : ''} ${o.id === opt.chosen ? 'chosen' : ''}">${'<span></span>' + head}</div>`;
  return `<label class="hopt ${o.feasible ? '' : 'out'} ${opt.selected ? 'sel' : ''} ${o.id === opt.rec ? 'rec' : ''} ${o.id === opt.chosen ? 'chosen' : ''}">
    <input type="radio" name="${opt.name || 'hopt'}" value="${esc(o.id)}" ${opt.selected ? 'checked' : ''} ${(o.feasible || opt.reviewable) && opt.pending && !blocked ? '' : 'disabled'}>${head}</label>`;
}
function reviewMatches(review, decision, option, parameters, scope = {}) {
  const saved = review?.snapshot?.options?.[0]?.reviewed_choice?.parameters;
  return !!(review?.id && review?.snapshot?.id === decision && review?.snapshot?.options?.[0]?.id === option
    && review?.scope?.decision === decision && review?.scope?.option === option && saved
    && Object.entries(scope).every(([key, value]) => review.scope[key] === value)
    && Object.keys(saved).length === Object.keys(parameters).length
    && Object.entries(parameters).every(([key, value]) => saved[key] === value));
}
// shared "사건 / 선택 / 사유·담당" form pieces (UIUX_PLAN §1)
function rangeField(id, label, a, value) {
  return `<div class="field range"><label for="${id}">${esc(label)}</label><div class="range-row"><input type="range" id="${id}" min="${a.min ?? 0}" max="${a.max ?? 100}" value="${esc(value)}"><output for="${id}">${esc(value)} %</output></div></div>`;
}
window.hydCards = { cardHtml, reviewMatches, rangeField, actionLabel };

/* ================================================= 규칙 판단(판단 실험) */
async function loadDecisionView() {
  const sel = $('#decPattern');
  if (!$('#decResult').innerHTML) $('#decResult').innerHTML = UI.empty(UI.t('dec.empty'));
  if (sel.options.length) return;
  const pats = await loadPatterns();
  pats.forEach(p => sel.append(new Option(`${p.name}${p.failureModes && p.failureModes.length ? ' → ' + p.failureModes.join(', ') : ''}`, p.code)));
  if (!pats.length) $('#decResult').innerHTML = UI.errorBlock(UI.t('dec.noPatterns'), ent.patternsError || '지식 그래프에 이상 패턴이 없습니다', { retry: true });
  $('#decResult').querySelector('[data-retry]')?.addEventListener('click', () => loadDecisionView());
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
  try { ent.result = await postJ(API.agent + '/api/agent/decide', { asset: $('#decAsset').value, pattern: $('#decPattern').value, facts }); ent.facts = facts; renderDecision(); }
  catch (e) { $('#decResult').innerHTML = UI.errorBlock(UI.t('dec.failed'), e.message, { retry: true }); }
  finally { ent.busy = false; b.disabled = false; b.textContent = UI.t('btn.run'); }
  $('#decResult').querySelector('[data-retry]')?.addEventListener('click', runDecision);
}
// first sentence = up to a period followed by whitespace or the end ("점수 3.87" must not cut)
const firstSentence = text => { const m = String(text || '').match(/^[\s\S]*?[.。](?=\s|$)/); return m ? m[0] : String(text || ''); };
function summaryBlock(raw) {
  const text = UI.idText(raw);                       // A141: 레거시 판단의 fm:/cause: id → 이름
  const first = firstSentence(text), rest = String(text || '').slice(first.length).trim();
  return `<p class="dc-conclusion">${esc(first)}</p>${rest ? UI.fold(esc(UI.t('dec.summaryMore')), `<p class="dc-more">${esc(rest)}</p>`) : ''}`;
}
// 판단에 쓴 값 한 칸: 문자열 코드는 화면 말, 참거짓은 예 · 아니요, 숫자는 단위와 함께(plainWords.js value). 묶음 값만 원문
const factValue = (key, v) => v !== null && typeof v === 'object' ? JSON.stringify(v) : window.hydWords.value(key, v);
const CHECK_STATUS = { TRUE: '적용', FALSE: '미적용', UNKNOWN: '미확인' };
const FACT_LABEL = { plc_mode: 'dec.mode', plc_state: 'dec.state', standby_ready: 'dec.standby', fan100_hours: 'dec.fan' };
/** 학생이 바꾼 판단 조건 가운데 이번 판단의 어떤 규칙 조건(when)에도 나오지 않는 것 */
function unusedFacts(facts, trace) {
  return Object.keys(facts || {}).filter(k => FACT_LABEL[k] && !(trace || []).some(t => String(t.when || '').includes(k)));
}
// 결과(디자인 기준 5-8 · 5-3): 결론 한 문장 → 조치 순위 표(1순위와 진 안이 왜 졌는지) → 원인 → 판단에 쓴 값 표 → 접기(후보별 근거 · 점수 계산 · 적용한 규칙 · 처리 과정 원문)
function renderDecision() {
  const d = ent.result; const box = $('#decResult');
  if (!d || !d.result) { box.innerHTML = UI.empty(UI.status(d && d.status) || UI.t('dec.failed'), (d && d.error) || ''); return; }
  const r = d.result, opts = r.options || [];
  const maxAbs = Math.max(1, ...opts.map(o => Math.abs(o.score || 0)));
  const text = UI.idText(r.explanation), first = firstSentence(text), rest = String(text || '').slice(first.length).trim();      // 결론 문장은 서버가 준 설명의 첫 문장 그대로다(화면이 지어 붙이지 않는다)
  let html = `<header class="dc-head"><h2>${esc(UI.idText((d.scenario || {}).name || ''))}</h2>${UI.chip(d.status)}<p>${esc(d.asset || '')} · 모의 판단 ${esc(UI.dateTime(d.created))}</p></header>`;
  html += UI.evaluationHtml(r, d);
  html += `<p class="label">결론</p><p class="dc-conclusion">${esc(first)}</p>` + (rest ? UI.fold(esc(UI.t('dec.summaryMore')), `<p class="dc-more">${esc(rest)}</p>`) : '');
  // 2026-10-25 수업 점검: 바꾼 판단 조건을 읽는 규칙이 지금 지식에 없으면 결과가 그대로라 학생이 고장으로 오해했다(HM-8에는 보호 정지 규칙이 없다)
  const unused = unusedFacts(ent.facts, r.trace);
  if (unused.length) html += `<p class="dc-note" role="status">${esc(unused.map(k => UI.t(FACT_LABEL[k])).join(', '))}: 지금 지식의 규칙 가운데 이 조건을 읽는 규칙이 없어 결과에 영향이 없습니다.</p>`;
  if (d.moneyError) html += `<p class="neg" role="status">손익(원)을 계산하지 못했습니다: ${esc(d.moneyError)}</p>`;

  // 조치 순위: 1순위 줄이 맨 위(파란 면). 진 안은 둘째 줄에 까닭 — 제외된 안은 걸린 규칙, 남은 안은 감점 규칙과 1순위와의 점수 차
  const top = opts.find(o => o.id === r.recommended) || null;
  const kind = o => [(o.actions || []).some(a => a.kind === 'command') ? UI.t('chip.control') : '', (o.actions || []).some(a => a.kind !== 'command') ? UI.t('chip.workOrder') : ''].filter(Boolean).join(' · ');
  const why = o => {
    if (!o.feasible) return `<small class="out">제외 — ${esc((o.violations || []).map(v => UI.ruleLabel(v)).join(' · ') || '걸린 규칙 이름 없음')}</small>`;
    if (top && o.id === top.id) return '';
    const parts = [];
    if ((o.penalties || []).length) parts.push('감점 — ' + o.penalties.map(v => UI.ruleLabel(v)).join(' · '));
    if (top && Number.isFinite(o.score) && Number.isFinite(top.score)) parts.push(`1순위보다 ${(top.score - o.score).toFixed(2)}점 낮음`);
    return parts.length ? `<small>${esc(parts.join(' · '))}</small>` : '';
  };
  const ordered = opts.slice().sort((a, b) => (b.id === r.recommended) - (a.id === r.recommended));
  html += `<h3 class="dc-sec">${esc(UI.t('dec.candidates'))}<small>${opts.length}</small></h3>` + (opts.length ? `<div class="table-scroll" tabindex="0"><table class="tbl dc-table"><thead><tr><th>순위</th><th>조치</th><th>구분</th><th class="r">${esc(UI.t('card.score'))}</th></tr></thead><tbody>` +
    ordered.map(o => `<tr class="${o.id === r.recommended ? 'pick' : o.feasible ? '' : 'out'}"><td class="num">${o.feasible ? esc(o.rank) : '–'}</td><td><b>${esc(UI.idText(o.name))}</b>${why(o)}</td><td>${esc(kind(o))}</td><td class="r">${Number.isFinite(o.score) ? signNum(o.score) : '–'}</td></tr>`).join('') +
    '</tbody></table></div>' : UI.empty(UI.t('inc.noCandidates'), '', 'compact'));

  // 원인: 판정 원인 한 줄과 증거, 다른 원인 후보는 접기
  const causes = d.causes || [];
  const evidenceHtml = c => (c.evidence || []).length ? '<ul class="dc-evidence">' + c.evidence.map(e => { const unknown = e.status === 'UNKNOWN' || e.passed == null || e.value == null || !!e.error;
    const unit = window.hydWords.unit(e.tag);      // 충족 여부를 색만이 아니라 글자로
    return `<li><span>${esc(e.name)}</span><span class="${unknown ? 'unknown' : e.passed ? 'ok' : 'no'}">${esc(UI.t(unknown ? 'inc.unknown' : e.passed ? 'inc.pass' : 'inc.fail'))}</span><span>${esc(UI.t('inc.observed'))} ${esc(fmt(e.value, 3))}${unit ? ' ' + esc(unit) : ''}</span></li>`; }).join('') + '</ul>'
    : `<p class="dc-note">${esc(UI.t('inc.noEvidence'))}</p>`;
  if (causes.length) {
    const c0 = causes[0];
    html += `<h3 class="dc-sec">${esc(UI.t('dec.cause'))}</h3><dl class="kv"><dt>${esc(UI.t('dec.causeTop'))}</dt><dd><b>${esc(UI.idText(c0.name))}</b></dd>` +
      (c0.failureMode ? `<dt>고장 유형</dt><dd>${esc(UI.idText(c0.failureMode))}</dd>` : '') + `<dt>${esc(UI.t('card.score'))}</dt><dd class="num">${esc(c0.score)}</dd></dl>` + evidenceHtml(c0) +
      (causes.length > 1 ? UI.fold(`${esc(UI.t('dec.causeMore'))} ${causes.length - 1}`, causes.slice(1).map(c => `<p class="dc-more"><b>${esc(UI.idText(c.name))}</b> · ${esc(UI.t('card.score'))} ${esc(c.score)}${c.failureMode ? ' · ' + esc(UI.idText(c.failureMode)) : ''}</p>${evidenceHtml(c)}`).join('')) : '');
  }

  // 판단에 쓴 값
  const prov = d.provenance || [];
  html += `<h3 class="dc-sec">${esc(UI.t('dec.inputs'))}<small>${prov.length}</small></h3>` + (prov.length ? `<div class="table-scroll" tabindex="0"><table class="tbl"><thead><tr><th>${esc(UI.t('dec.col.input'))}</th><th>${esc(UI.t('dec.col.value'))}</th><th>${esc(UI.t('dec.col.source'))}</th><th>${esc(UI.t('dec.col.how'))}</th></tr></thead><tbody>` +
    prov.map(p => `<tr><td>${esc(p.name)}</td><td>${p.error ? '<span class="neg">' + esc(p.error) + '</span>' : esc(factValue(p.variable, p.value))}</td><td>${esc(p.sourceName || p.source)}</td><td class="muted">${esc(p.how || '')}</td></tr>`).join('') + '</tbody></table></div>'
    : `<p class="dc-note">이 판단은 입력 값의 출처를 남기지 않았습니다.</p>`);

  // 자세히: 후보별 근거 카드 · 점수 계산 방법 · 적용한 규칙 · 처리 과정 원문 · 판단 번호
  const tr = (r.trace || []).slice().sort((a, b) => (b.fired ? 1 : 0) - (a.fired ? 1 : 0) || (b.skill ? 1 : 0) - (a.skill ? 1 : 0));      // 발동한 규칙이 위로
  const target = t => t.skill ? ((opts.find(o => o.id === t.skill) || {}).name || t.skill) : '';
  html += '<div class="dc-folds">' +
    UI.fold(`조치 후보별 근거 · 예측 · 절차`, `<div class="hitl-opts">` + opts.map(o => cardHtml(o, { rec: r.recommended, maxAbs, decision: { ...r, facts: d.facts, origin: d.origin } })).join('') + '</div>') +
    (r.rankRule ? UI.fold(esc(UI.t('card.scoreHow')), `<p class="dc-more">${esc(r.rankRule.annotation || '')}</p>`) : '') +
    UI.fold(`${esc(UI.t('dec.rules'))} ${tr.length}`,
      `<div class="table-scroll" tabindex="0"><table class="tbl"><thead><tr><th>${esc(UI.t('dec.col.rule'))}</th><th>${esc(UI.t('dec.col.target'))}</th><th>${esc(UI.t('dec.col.result'))}</th></tr></thead><tbody>` +
      tr.map(t => `<tr class="${t.fired ? 'pick' : ''}"><td>${esc(UI.ruleLabel(t))}<small>${esc(t.decision === 'dec:action-candidates' ? UI.t('dec.ruleSelect') : UI.t('dec.ruleCompliance'))}</small>${UI.fold(esc(UI.t('raw')), `<code>${esc(t.rule)}</code> <code>${esc(t.when || '')}</code>`)}</td><td>${esc(target(t))}</td>` +
        `<td>${t.fired ? `<b>${esc(UI.t('dec.fired'))}</b>` : (t.unknown && t.unknown.length ? `<span class="muted">${esc(UI.t('dec.noFact'))}: ${esc(t.unknown.join(', '))}</span>` : esc(UI.t('dec.notApplicable')))}</td></tr>`).join('') + '</tbody></table></div>') +
    UI.fold(`${esc(UI.t('dec.trace'))} · 판단 번호`, `<dl class="kv"><dt>판단 번호</dt><dd class="mono">${esc(d.id)}</dd></dl>` + traceHtml({ id: d.id, status: d.status, started: d.created, steps: d.steps || [] })) +
    '</div>';
  box.innerHTML = html;
}

$('#decRun').addEventListener('click', runDecision);

/* ================================================= 업무 시스템 기록(유압 실습장)
   이 화면의 몫은 모의 업무 시스템의 표와 거래 전 · 후 값이다. AI 판단 · 조치 후보 · 승인 · 실행 결과는 처리 건 화면 한 곳에서 본다 — 여기에 그 사본(판단 목록 · 흐름 그림 · 조치 카드)을 두지 않는다.
   예외 하나: 처리 건 없이 제출된 판단. 지금 서버는 사건과 처리 건이 있는 판단만 받지만(process main.py 판단 접수), 옛 판에서 남은 것은 처리 건 화면에 나오지 않아
   이 화면이 유일한 길이다 — 그런 판단이 있을 때만 「처리 건 없이 제출된 판단」 절(#decOrphans)이 보인다. */
const orphan = d => !(d.origin || {}).incident;
async function refreshProcess() {
  if (state.tab !== 'process') return;
  try { ent.decisions = requireList(await getJ(API.process + '/api/decisions'), '판단 목록').filter(orphan); ent.decisionsError = ''; } catch (e) { ent.decisionsError = e.message; }
  try { [ent.entState, ent.tx] = await Promise.all([getJ(API.ent + '/api/state'), getJ(API.ent + '/api/transactions?limit=12')]); ent.entError = ''; } catch (e) { ent.entState = null; ent.tx = []; ent.entError = e.message; }
  if (!ent.decisions.some(d => d.id === ent.decSel)) { ent.decSel = ent.decisions.length ? ent.decisions[0].id : null; ent.decDetail = null; }
  const selected = ent.decSel;
  if (selected) {
    // 고른 판단을 못 읽으면 「판단을 선택하세요」(안 고른 것)로 보이지 않는다 — 사유를 두고 2.5초마다 다시 읽는다
    try { const detail = await getJ(API.process + '/api/decisions/' + selected); if (selected !== ent.decSel) return; ent.decDetail = detail; ent.decDetailError = ''; }
    catch (e) { if (selected !== ent.decSel) return; ent.decDetail = null; ent.decDetailError = e.message; }
  }
  renderProcess();
}
function renderProcess() {
  renderSystems();
  // 처리 건 없이 남은 판단이 없으면 그 절을 보이지 않는다(목록을 못 읽었으면 까닭을 보인다)
  $('#decOrphans').hidden = !ent.decisions.length && !ent.decisionsError;
  if ($('#decOrphans').hidden) return;
  const list = $('#decList');
  const sig = JSON.stringify([ent.decisions, ent.decSel, ent.decisionsError, ent.decShown, UI.namesVersion]);
  if (list.dataset.sig !== sig) {
    list.dataset.sig = sig;
    const focused = list.contains(document.activeElement) ? document.activeElement.dataset.itemId : null;
    const scroll = list.scrollTop;
    list.innerHTML = '';
    if (ent.decisionsError) list.innerHTML = `<div class="form-msg neg" role="alert">${esc(UI.t('proc.listError'))} (${esc(ent.decisionsError)})</div>`;
    const paged = UI.page(ent.decisions, ent.decShown, d => d.id === ent.decSel);
    for (const d of paged.rows) {
      const it = el('div', 'item' + (d.id === ent.decSel ? ' sel' : ''));
      keyboardItem(it);
      it.dataset.itemId = d.id;
      it.innerHTML = `<div class="row"><strong>${esc(UI.idText((d.scenario || {}).name || ''))}</strong>${UI.chip(d.state)}</div>` +
        `<span class="sub">${esc(d.asset || '')} · ${esc(UI.dateTime(d.created))}${(d.origin || {}).kind !== 'alert' ? ' · ' + esc(UI.t('proc.manual')) : ''}${d.override ? ' · ' + esc(UI.t('proc.override')) : ''}</span>`;
      it.addEventListener('click', async () => {
        if (ent.decSel === d.id && ent.decDetail) { UI.revealDetail($('#decDetail')); return; }
        ent.decSel = d.id; ent.decDetail = null; ent.form.msg = ''; ent.lastDetailSig = null;
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
}
function renderDecisionApproval() {
  const box = $('#decDetail'); const d = ent.decDetail;
  if (!d) { ent.lastDetailSig = null; box.innerHTML = ent.decSel && ent.decDetailError ? UI.errorBlock('고른 판단을 읽지 못했습니다', ent.decDetailError + ' — 잠시 뒤 다시 읽습니다') : UI.empty(UI.t('proc.select')); return; }
  // the 2.5 s refresh must not wipe what the approver is typing or selecting: redraw only when the decision changed
  const sig = d.id + '|' + d.state + '|' + (d.executions || []).length + '|' + (d.history || []).length + '|' + UI.namesVersion;
  if (sig === ent.lastDetailSig && box.querySelector('.hitl-opts')) return;
  ent.lastDetailSig = sig;
  const pending = d.state === 'PENDING_APPROVAL';
  const opts = d.options || [];
  const maxAbs = Math.max(1, ...opts.map(o => Math.abs(o.score || 0)));
  const sc = d.scenario || {};
  // A141: 제출 시각 · id · 사건 정보(설비 · 고장 유형 · 원인)는 접기로. 화면에는 제목 · 상태 · 한 줄 요약 · 선택 카드 · 사유 · 승인 버튼만
  let html = `<div class="detail-head"><div class="row"><h2>${esc(UI.idText(sc.name || ''))}</h2>${UI.chip(d.state)}</div><div class="sub">${esc(d.asset || '')}${d.approvedBy ? ` · ${esc(UI.t('inc.approvedBy'))} ${esc(UI.who(d.approvedBy))}` : ''}</div></div>`;
  html += UI.evaluationHtml(d) + summaryBlock(d.explanation);
  html += UI.metaFold([[UI.t('dec.asset'), esc(d.asset || '')], ['고장 유형', esc(UI.idText(sc.failureMode || ''))], [UI.t('dec.cause'), esc(UI.idText(sc.cause || ''))], [UI.t('proc.submitted'), esc(UI.dateTime(d.created))], ['ID', `<span class="mono">${esc(d.id)}</span>`]], 'fold.case');
  // 판단은 처리 건의 승인 단계에서만 승인 · 반려한다(서버에 판단 단독 승인 길이 없다 — test_main.test_처리_건_밖의_옛_승인_경로는_없다).
  // 이 절에 오는 것은 처리 건 없이 남은 판단뿐이라, 승인을 기다리는 것이면 승인할 길이 없음을 그대로 알린다
  if (pending) {
    html += `<div class="hitl-opts">${opts.map(o => cardHtml(o, { rec: d.recommended, chosen: d.chosen, maxAbs, decision: d })).join('')}</div>` +
      `<p class="neg" role="status">이 판단은 경보로 열린 처리 건 없이 제출돼 승인하거나 반려할 수 없습니다. 판단은 처리 건 안에서만 승인합니다. 결함 시뮬레이션으로 경보를 내어 처리 건을 열고 그 승인 단계에서 고르세요.</p>`;
  } else {
    html += `<h3 class="dc-sec">${esc(UI.t('decisions'))}</h3><div class="hitl-opts">` + opts.map(o => cardHtml(o, { rec: d.recommended, chosen: d.chosen, maxAbs, decision: d })).join('') + '</div>';
  }
  if ((d.executions || []).length) html += `<h3 class="dc-sec">${esc(UI.t('proc.executions'))}</h3><div class="cards two">` +
    d.executions.map(x => UI.card({ title: esc(UI.who(x.system) + (x.code ? ' · ' + actionLabel({ code: x.code }) : '')), chips: UI.chip(x.status), value: x.ref ? `<span class="kv mono">${esc(x.ref)}</span>` : '', sub: esc(x.detail || ''), cls: 'soft' })).join('') + '</div>';
  html += `<div class="dc-folds">` + UI.fold(`${esc(UI.t('proc.history'))} ${(d.history || []).length}`, '<div class="audit">' + (d.history || []).map(h => UI.eventRecord({ time: h.t, name: h.state, actor: h.by, detail: h.reason || '', raw: h })).join('') + '</div>') + '</div>';
  box.innerHTML = html;
}
// 업무 시스템 보드: 업무 상태(/api/state — 생산 주문 · 정비 오더 · 구매 요청 · 입고)에 있는 표만 그린다.
// 품질 처분 · 전력 · 대체 출하는 쓰는 거래가 없어 업무 DB에서 지웠다(FE 070) — 없는 칸을 읽지 않는다
function systemBoards(s) {
  return [
    ['생산 관리', s.mes.orders.map(o => ({ ...o, where: o.moved_from ? `${o.moved_from} → ${o.asset}` : o.asset })), ['order_id', 'where', 'due_in_h'], ['생산오더', '설비', '납기까지 (시간)']],
    ['정비 관리', s.cmms.work_orders, ['id', 'asset', 'task', 'window'], ['번호', '설비', '작업', '정비 시점']],
    ['구매 · 재고 관리', [...s.erp.purchase_requests.map(p => ({ a: p.id, b: p.supplierName, c: p.status })),
      ...s.erp.goods_receipts.map(g => ({ a: g.id, b: `${g.part_no || ''} ${g.qty}개 입고`, c: `검수 ${g.inspection}` }))], ['a', 'b', 'c'], ['번호', '대상', '상태']],
  ];
}
function renderSystems() {
  const box = $('#sysBoards'); const s = ent.entState;
  // 2.5초마다 불리지만 값이 같으면 다시 그리지 않는다 — 다시 그리면 펴 둔 「변경 전·후」 접기가 2.5초마다 닫힌다
  const sig = JSON.stringify([s, ent.tx, ent.entError, UI.namesVersion]);
  if (box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  if (!s) { box.innerHTML = ent.entError ? UI.errorBlock(UI.t('proc.noEnt'), ent.entError + ' — 2.5초마다 다시 읽습니다', { cls: 'compact' }) : UI.empty(UI.t('loading'), '', 'compact'); $('#txList').innerHTML = ''; return; }
  // 표 한 장 = 업무 시스템 하나. 숫자 칸은 오른쪽 정렬, 여섯 줄까지 보이고 나머지는 몇 건인지 적는다
  const cell = v => `<td${typeof v === 'number' ? ' class="r"' : ''}>${esc(v ?? '–')}</td>`;
  const t = (rows, cols, labels) => rows.length ? '<div class="table-scroll" tabindex="0"><table class="tbl"><thead><tr>' + labels.map((x, i) => `<th${rows.every(r => typeof r[cols[i]] === 'number') ? ' class="r"' : ''}>${esc(x)}</th>`).join('') + '</tr></thead><tbody>' +
    rows.slice(0, 6).map(r => '<tr>' + cols.map(c => cell(r[c])).join('') + '</tr>').join('') + '</tbody></table></div>' + (rows.length > 6 ? `<p class="bz-note">${rows.length}건 가운데 6건만 보입니다(외 ${rows.length - 6}건).</p>` : '') : UI.empty(UI.t('proc.noChange'), '', 'compact');
  box.innerHTML = systemBoards(s).map(([sys, rows, cols, labels]) => `<section class="board"><h2>${esc(sys)}<small>${rows.length}건</small></h2>${t(rows, cols, labels)}</section>`).join('');
  $('#txList').innerHTML = ent.tx.length ? ent.tx.slice(0, 12).map(x => UI.eventRecord({ time: x.t, name: UI.who(x.system), actor: x.by, detail: x.detail, raw: x, extra: txDiffFold(x) })).join('') : `<div class="muted">${esc(UI.t('proc.noTx'))}</div>`;
}
// A147: 거래가 바꾼 행의 변경 전·후 — 바뀐 항목만, 기본 닫힘. 기록이 없는 거래(before/after 둘 다 없음)는 접기도 없다
function txDiffFold(x) {
  const b = x.before || null, a = x.after || null;
  if (!b && !a) return '';
  const show = v => v == null || v === '' ? '–' : typeof v === 'object' ? JSON.stringify(v) : /^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(String(v)) ? UI.dateTime(v) : String(v);
  const keys = [...new Set([...Object.keys(b || {}), ...Object.keys(a || {})])].filter(k => JSON.stringify((b || {})[k] ?? null) !== JSON.stringify((a || {})[k] ?? null));
  const body = !keys.length ? `<p class="muted">${esc(UI.t('tx.noDiff'))}</p>`
    : `${b ? '' : `<p class="muted">${esc(UI.t('tx.created'))}</p>`}<div class="table-scroll"><table class="tbl"><thead><tr><th>${esc(UI.t('tx.col.field'))}</th><th>${esc(UI.t('tx.col.before'))}</th><th>${esc(UI.t('tx.col.after'))}</th></tr></thead><tbody>` +
      keys.map(k => `<tr><td title="${esc(k)}">${esc(window.hydWords.fieldName(k))}</td><td>${esc(show((b || {})[k]))}</td><td><b>${esc(show((a || {})[k]))}</b></td></tr>`).join('') + '</tbody></table></div>';
  return UI.fold(`${esc(UI.t('tx.beforeAfter'))} ${keys.length}`, body);
}

initOntology();
setInterval(() => { if (state.tab === 'process') refreshProcess(); }, 2500);
// layoutGraph · fitView · pickLabels · kgNodeClass · kgEdgeClass: 지식 지도의 배치와 상태 판정(DOM 없이 도는 부분 — 시험이 그대로 부른다)
window.hydEnt = { ent, systemBoards, runDecision, loadGraph, refreshProcess, loadDecisionView, renderDecision, layoutGraph, fitView, pickLabels, kgNodeClass, kgEdgeClass, KG };
