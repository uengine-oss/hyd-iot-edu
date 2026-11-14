/* 지식 지도 · 규칙 판단 · 업무 시스템 기록 (enterprise.js) — ontology v2.
   Loaded after app.js and reuses its helpers ($, el, esc, fmt, getJ, postJ, state, selectTab).
   Data: agent for the ontology and the decision engine, process for approval, enterprise-sim for ERP/MES/… — all through the same-origin table API (layers.js).
   A122: wording from UI.terms; action-candidate card = title · chips · score · one line · evidence folded. */

// 지식 지도의 묶음 = 온톨로지 v2 의 층(it/neo4j/v2/schema.json). 이름에 프레임워크 이름을 쓰지 않는다(명칭표).
// at: 지도에서 그 묶음이 모이는 자리(0 ~ 1, 왼쪽 위가 0,0). color: 어두운 캔버스의 색(portal-kit.css --cv-violet · --cv-blue · --cv-ink-2 · --cv-red · --cv-teal · --cv-amber 의 값 —
// 캔버스에 그리는 Cytoscape 는 CSS 변수를 읽지 못해 값을 적는다. 디자인 기준 2-2 · 6-3). 오른쪽 밝은 칸에서는 같은 색을 점에만 쓴다.
const ONTO_GROUPS = [
  { key: 'value', title: '전략 목표', at: [0.13, 0.2], color: '#b794f6', labels: ['Perspective', 'Objective', 'Measure'] },
  { key: 'process', title: '프로세스', at: [0.4, 0.08], color: '#7aa2ff', labels: ['Process', 'Event', 'Task', 'Gateway'] },
  { key: 'resource', title: '자원', at: [0.14, 0.74], color: '#9aa7b5', labels: ['OrgUnit', 'Role', 'System', 'Asset', 'Component', 'Sensor', 'Actuator', 'StateVariable', 'Part', 'Supplier'] },
  { key: 'diagnosis', title: '설비 진단', at: [0.4, 0.5], color: '#f07167', labels: ['AnomalyPattern', 'Symptom', 'FailureMode', 'Cause', 'Evidence', 'ManualSection'] },
  { key: 'skill', title: '조치 방법과 규칙', at: [0.76, 0.46], color: '#2dd4bf', labels: ['Skill', 'Step', 'Action', 'Decision', 'DecisionTable', 'Rule', 'InputData', 'KnowledgeSource'] },
  { key: 'external', title: '외부 변수 · 예측 · 사례', at: [0.45, 0.93], color: '#f5a623', labels: ['ExternalVariable', 'Forecast', 'Incident', 'DecisionCase'] },
  // G4: 학생 이름 공간의 업무 고유 클래스(students/<ID>/schema.json) — v2 에 없는 레이블은 모두 이 묶음에 그린다
  { key: 'student', title: '내 업무 개념', at: [0.8, 0.92], color: '#f472b6', labels: [], other: true },
];
const LABEL_KO = { Perspective: '관점', Objective: '전략 목표', Measure: '성과 지표', Process: '프로세스', Event: '이벤트', Task: '단계', Gateway: '분기',
  OrgUnit: '부서', Role: '역할', System: '시스템', Asset: '설비', Component: '구성 요소', Sensor: '센서', Actuator: '구동기', StateVariable: '상태 변수',
  Part: '부품', Supplier: '공급사', AnomalyPattern: '이상 패턴', Symptom: '증상', FailureMode: '고장 유형', Cause: '원인', Evidence: '증거', ManualSection: '매뉴얼 절',
  Skill: '조치 방법', Step: '절차 단계', Action: '세부 동작', Decision: '판단', DecisionTable: '결정표', Rule: '규칙', InputData: '입력 데이터',
  KnowledgeSource: '지식 출처', ExternalVariable: '외부 변수', Forecast: '예측', Incident: '사건', DecisionCase: '판단 사례' };
// 지식 지도 상세 칸의 속성 이름(그래프 속성 키 → 화면 이름). 여기에 없는 키(적재 출처 · 해시 · 정책 원문 같은 내부 값)는 「그 밖의 속성」 접기에 원래 이름으로 둔다
const PROP_KO = { description: '설명', annotation: '풀이', text: '내용', title: '제목', excerpt: '원문 발췌', citation: '인용 위치', ref: '참조 번호', order: '순서',
  aliases: '다른 이름', kind: '종류', unit: '단위', tag: '태그', zone: '구역', level: '수준', scope: '범위', source: '출처',
  kpiRole: '지표 성격', frequency: '측정 주기', direction: '좋은 방향', target: '목표', normal: '정상 범위', min: '최소', max: '최대', limit: '한도',
  rule: '규칙 식', formula: '계산식', when: '조건', effect: '효과', expect: '기대 값', hitPolicy: '적용 방식', weight: '가중치', prior: '사전 확률', penalty: '감점',
  threshold: '임계값', thresholdWarn: '경고 임계값', thresholdCrit: '위험 임계값', detectionMode: '감지 방식', holdSeconds: '지속 시간(초)',
  windowSeconds: '관찰 구간(초)', slopeWindowSeconds: '기울기 구간(초)', clearRule: '해제 규칙', clearHoldSeconds: '해제 지속 시간(초)', severity: '심각도',
  sopId: '절차 번호', executable: '실행 가능', isExecutable: '실행 가능', partNo: '부품 번호', avl: '승인 공급사', oem: '순정품', 
  question: '질문', note: '비고', virtual: '가상 값' };
// 속성 값의 화면 말(열거 값). 여기에 없는 값은 받은 그대로 보인다. 식별자 성격의 값(코드 · 변수 · 자원 이름)은 이름표(PROP_KO)에 두지 않아 「그 밖의 속성」 접기로 간다
const PROP_VALUE_KO = { kpiRole: { lagging: '후행 지표(결과)', leading: '선행 지표(결과를 움직이는 요인)' }, direction: { UP: '높을수록 좋음', DOWN: '낮을수록 좋음' },
  severity: { CRITICAL: '매우 높음', HIGH: '높음', MEDIUM: '보통', LOW: '낮음' },
  detectionMode: { held: '조건이 지속 시간 동안 이어지면 경보', 'plc-trip': 'PLC 보호 정지 신호가 오면 경보' },
  effect: { SELECT: '후보로 고름', EXCLUDE: '후보에서 제외', PENALTY: '감점', WARN: '경고', RANK: '순위 매김' },
  hitPolicy: { UNIQUE: '맞는 규칙 하나', PRIORITY: '맞는 규칙 가운데 우선순위가 높은 것', COLLECT: '맞는 규칙 모두' },
  kind: { command: '설비 명령', control: '설비 제어', work_order: '정비 요청', transaction: '업무 거래', reference: '참고 절차', manual: '매뉴얼', policy: '정책', regulation: '규정', strategy: '전략',
    controlled: '제어되는 변수', manipulated: '조작하는 변수', disturbance: '외란' },
  expect: { gte: '이상', gt: '초과', lte: '이하', lt: '미만', eq: '같음' }, scope: { purchase: '구매' }, zone: { OT: 'OT(현장)', DMZ: 'DMZ(경계망)', IT: 'IT(업무)' } };
// 식(규칙 식 · 해제 규칙 · 계산식 · 조건)은 식 그대로 고정폭 글꼴로 보인다. 태그는 설비 값 이름 뒤에 태그 코드를 작게 붙인다
const PROP_EXPR = ['rule', 'clearRule', 'formula', 'when'];
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
  // G4: 학생 이름 공간(화면 이름 「지식 묶음」) 목록(맨 위 = 기본 지식 = ns 없는 노드). 더 넣은 묶음이 없으면 고르기 칸을 보이지 않는다(고를 것이 하나뿐인 칸을 두지 않는다).
  // 못 읽으면 칸을 보이고 사유를 적는다 — 다음 [다시 읽기]에 또 읽는다
  const sel = $('#ontoNs'); if (!sel || (sel.dataset.loaded && !force)) return;
  const keep = sel.value;
  let list;
  try { list = await getJ(API.agent + '/api/ontology/namespaces'); }
  catch (e) {   // 이미 받은 이름 공간은 그대로 두고 사유 한 줄만 붙인다(고른 것이 사라지지 않게)
    sel.querySelectorAll('option[data-note]').forEach(o => o.remove());
    sel.append(nsNote(`더 넣은 지식 묶음 목록을 읽지 못함 — ${e.message}`));
    sel.title = `더 넣은 지식 묶음 목록을 읽지 못했습니다: ${e.message}`; delete sel.dataset.loaded; sel.hidden = false;
    return;
  }
  sel.querySelectorAll('option:not([value=""]), option[data-note]').forEach(o => o.remove());
  list.forEach(x => sel.append(new Option(`${x.ns} · 항목 ${x.nodes}개`, x.ns)));
  sel.title = ''; sel.dataset.loaded = '1'; sel.hidden = !list.length;
  if (list.some(x => x.ns === keep)) sel.value = keep;
  else if (keep) { sel.value = ''; UI.toast(`지식 묶음 ${keep}이(가) 그래프에 없어 기본 지식으로 돌아갑니다`, { tone: 'neg' }); loadGraph(true); }
}
const nsNote = text => { const o = new Option(text, ''); o.disabled = true; o.dataset.note = '1'; return o; };
const ontoShown = () => !!$('#view-ontology')?.classList?.contains('active');
// 설비 고르기의 목록은 서버가 준다(plant /api/state 의 units — 유압 설비 화면이 읽는 그 응답). 화면에 설비 이름을 적어 두지 않는다
async function ontoAssets() {
  const sel = $('#ontoAsset'); if (sel.options.length) return;
  const units = (state.plant && state.plant.units) || (await getJ(API.plant + '/api/state')).units || {};
  if (!Object.keys(units).length) throw new Error('설비 상태 응답에 설비가 없습니다. 가상 설비 서비스를 확인한 뒤 다시 시도하세요.');
  Object.keys(units).forEach(a => sel.append(new Option(a, a)));
}
async function loadGraph(force) {
  // 가려진 동안에는 그리지 않는다(캔버스의 크기가 0 이라 배치할 수 없다) — 다음에 이 화면을 열 때 다시 읽는다. 문서 적재 · 되돌리기 뒤에 다른 화면이 부른다
  if (!ontoShown()) { if (force) ent.stale = true; return; }
  if (ent.stale) { force = true; ent.stale = false; }
  try { await ontoAssets(); }
  catch (e) {
    ent.graph = null; kgDrop();
    $('#ontoStats').textContent = UI.t('error.load'); $('#ontoNode').dataset.sig = '';
    $('#ontoNode').innerHTML = `<div class="node-sec">${UI.errorBlock('설비 목록을 읽지 못했습니다', e.message, { retry: true })}</div>`;
    $('#ontoNode').querySelector('[data-retry]')?.addEventListener('click', () => loadGraph(true));
    return;
  }
  const asset = $('#ontoAsset').value + '|' + (($('#ontoNs') || {}).value || '');
  if (ent.graph && ent.graphAsset === asset && !force) { drawGraph(); return; }
  $('#ontoStats').textContent = UI.t('loading');
  if (!ent.graph) $('#ontoNode').innerHTML = `<div class="node-sec">${UI.loading('')}</div>`;
  loadNamespaces(force);
  const [code, ns] = asset.split('|');
  const current = () => $('#ontoAsset').value + '|' + (($('#ontoNs') || {}).value || '');
  try {
    const [graph] = await Promise.all([getJ(API.agent + '/api/ontology/graph?asset=' + encodeURIComponent(code) + (ns ? '&ns=' + encodeURIComponent(ns) : '')), UI.need('graph')]);
    if (current() !== asset) return;
    if (!Array.isArray(graph?.nodes) || !Array.isArray(graph?.edges)) throw new Error('지식 지도 응답 형식이 올바르지 않습니다. 다시 조회하세요.');
    if (ent.graphAsset !== asset) ent.sel = null;
    ent.graph = graph; ent.graphAsset = asset;
  }
  catch (e) {
    if (current() !== asset) return;
    // 다시 연 화면은 다시 읽어야 한다 — 앞서 받은 지도를 되살아난 것처럼 보이지 않는다. 까닭과 [다시 시도]는 오른쪽 밝은 칸에 보인다
    ent.graph = null; kgDrop();
    $('#ontoLayers').innerHTML = ''; $('#ontoNode').dataset.sig = '';
    $('#ontoHint').textContent = '지도를 그리지 못했습니다';
    $('#ontoStats').textContent = UI.t('error.load');
    $('#ontoNode').innerHTML = `<div class="node-sec">${UI.errorBlock(UI.t('onto.loadFail'), e.message, { retry: true })}</div>`;
    $('#ontoNode').querySelector('[data-retry]')?.addEventListener('click', () => loadGraph(true));
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
/** 이상 패턴 하나의 경로: 패턴 → 감지 증상 → 그 증상이 나타내는 고장 유형 → 그 고장을 일으키는 원인 · 그 고장의 조치 방법(디자인 기준 6-3).
    AI가 한 경보를 판단할 때 걷는 길의 뼈대다. 절차 단계 · 근거 매뉴얼 · 규칙처럼 그 뒤에 딸린 것은 조치 방법을 눌러서 본다.
    → null(패턴이 그래프에 없음) | { ids: Set, pattern, symptoms: [], modes: [], causes: [], skills: [] }. 선은 KG.PATH_RELS 의 관계만 길로 친다 */
function kgPath(graph, focus) {
  if (!focus || !graph || !(graph.nodes || []).some(n => String(n.id) === focus)) return null;
  const out = new Map(), inn = new Map();
  for (const e of graph.edges) { const a = String(e.from), b = String(e.to); (out.get(a) || out.set(a, []).get(a)).push(e); (inn.get(b) || inn.set(b, []).get(b)).push(e); }
  const walk = (ids, types, dir = 'out') => [...new Set(ids.flatMap(id => ((dir === 'out' ? out : inn).get(id) || []).filter(e => types.includes(e.type)).map(e => String(dir === 'out' ? e.to : e.from))))];
  const symptoms = walk([focus], ['DETECTS']), modes = walk(symptoms, ['INDICATES']);
  const causes = walk(modes, ['CAUSES'], 'in'), skills = walk(modes, ['MITIGATED_BY', 'REMEDIED_BY', 'PREVENTED_BY']);
  return { ids: new Set([focus, ...symptoms, ...modes, ...causes, ...skills]), pattern: focus, symptoms, modes, causes, skills };
}
/** 경로를 왼쪽에서 오른쪽으로 놓는 자리(배율 1 에서 화면 px): 이상 패턴 | 증상 | 고장 유형 | 원인(위) · 조치 방법(아래). 패턴은 제자리(center)에 둔다.
    앞의 세 줄은 이름을 점 아래에 쓰고(줄 사이로 선이 지나간다), 마지막 줄은 이름을 오른쪽에 쓴다. 'head:' 로 시작하는 id 는 그 줄 · 묶음의 이름 자리다.
    → { at: Map(id → { x, y, side: 'B' | 'R' }), labelW, colW(앞 세 줄의 이름 폭), bounds } */
function kgPathLay(center, path, box) {
  const [sMin, sMax] = KG.STEP, availH = Math.max(120, box.h - 230);
  const labelW = Math.round(Math.max(56, Math.min(KG.LABEL, box.w * 0.28)));
  const gap = Math.max(96, Math.min(190, (box.w - labelW - 110) / 3)), at = new Map();
  const col = (ids, head, k) => {      // 앞 세 줄: 세로 간격 50, 가운데 맞춤. 줄 이름은 맨 위 점의 위에
    const H = (ids.length - 1) * 50;
    ids.forEach((id, i) => at.set(id, { x: center.x + k * gap, y: center.y - H / 2 + i * 50, side: 'B' }));
    at.set('head:B:' + head, { x: center.x + k * gap, y: center.y - H / 2 - 28, side: 'B' });
    return H / 2;
  };
  let halfH = Math.max(col([path.pattern], '이상 패턴', 0), col(path.symptoms, '증상', 1), col(path.modes, '고장 유형', 2)) + 30;
  const last = [...(path.causes.length ? ['head:R:원인', ...path.causes] : []), ...(path.skills.length ? ['head:R:조치 방법', ...path.skills] : [])];
  const step = last.length > 1 ? Math.max(sMin, Math.min(sMax, availH / (last.length - 1))) : 0, H = (last.length - 1) * step;
  last.forEach((id, i) => at.set(id, { x: center.x + 3 * gap, y: Math.round((center.y - H / 2 + i * step) * 10) / 10, side: 'R' }));
  halfH = Math.max(halfH, H / 2);
  return { at, labelW, colW: Math.round(gap - 18), bounds: { x0: center.x - gap / 2 - 8, x1: center.x + 3 * gap + (last.length ? labelW + 24 : gap / 2), y0: center.y - halfH - 34, y1: center.y + halfH + 34 } };
}

/* ================================================= 지식 지도 그림 — 어두운 캔버스에 Cytoscape.js(vendor/cytoscape, 배치는 fcose)로 그린다 (디자인 기준 5-9 · 6-3)
   배치: 묶음(전략 목표 · 자원 …)마다 fcose 로 안을 놓고, 묶음을 ONTO_GROUPS.at 의 자리에 둔 뒤 겹친 묶음을 밀어낸다. 난수를 고정하고 항목 · 연결을 id 순으로
     세운 뒤 배치하므로 같은 그래프는 서버가 준 차례가 달라도 늘 같은 자리다. 배치의 크기는 항목 수로 정한다(캔버스 크기와 무관).
   이상 패턴 경로: 그 패턴에서 증상 · 고장 유형 · 원인 · 조치 방법까지의 길(kgPath)만 밝게 하고 왼쪽에서 오른쪽으로 줄지어 놓는다(kgPathLay). 고른 것이 있으면 고름이 앞선다.
   상태: 고름(pick) · 바로 이어짐(near) · 이상 패턴 경로(path) · 검색에 걸림(hit)이 서로 겹칠 수 있고, 어느 하나라도 켜지면 나머지는 흐리다(dim) — kgMarks.
   고름: 고른 항목은 제자리에 두고 이어진 항목을 그 둘레로 모은다 — 고른 항목을 가리키는 것은 왼쪽 호, 고른 항목이 가리키는 것은 오른쪽 호에 관계 이름별로
     세로로 놓고(kgGather), 이름은 호의 바깥쪽에 쓴다. 관계 묶음마다 그 위에 관계 이름(한국어, RELATION_KO)을 한 줄 적는다. 화면은 그 전체가 보이게 옮겨 간다.
     고름을 풀면 항목과 화면이 제자리로 돌아간다.
   글자: 캔버스 바탕 위에 바탕색 테두리와 함께 쓰고, 확대 배율과 상관없이 화면에서 같은 크기다. 고른 것 · 모은 이웃 · 경로의 이름은 늘 보이고, 그 밖의 이름은
     서로 겹치지 않고 점과 캔버스 안 도구를 가리지 않는 것만 보인다 — 검색에 걸린 것, 이어진 수가 많은 것부터 자리를 잡고(kgPlaceLabels) 확대할수록 더 많이 보인다.
     숨은 이름은 점에 마우스를 올리면 보인다. 전체에서 무엇이 들어 있는지는 오른쪽 칸의 목차(묶음 → 종류 → 항목 이름)로 읽고, 묶음을 펼치면 지도도 그 묶음을 크게 보인다(kgGroup). */
const KG = { SEED: 20261114, HUB: 14, ZOOM_MAX: 3, ZOOM_PICK: 1.25, STEP: [17, 26], STEP_TIGHT: 15, LABEL: 180, BG: '#16202d', NOW: '#8b93ff', HIT: '#f5c46b', BLUE: '#7aa2ff',
  PATH_RELS: ['DETECTS', 'INDICATES', 'CAUSES', 'MITIGATED_BY', 'REMEDIED_BY', 'PREVENTED_BY'],
  FONT: 11.5, FONT_HUB: 12.5, NAME_W: 120, NAME_W_HUB: 180, NAME_W_HIT: 220,      // 이름의 글자 크기(px)와 한 줄 폭의 한도 — 넘으면 말줄임
  nearSize: ele => 11 + ele.data('size') * 0.14 };      // 모은 이웃의 점은 화면에서 13 ~ 17px(이어진 수의 차이는 남기되 세로 간격 안에 들어오게)
const kgCollator = new Intl.Collator('ko');
// 이름의 화면 폭(px): 브라우저에서는 실제 글꼴로 재고, 잴 수 없는 곳(시험의 node)에서는 어림한다(한글 · 한자는 글자 크기만큼, 그 밖은 0.6배)
function kgTextW(text, px, weight = 500) {
  if (typeof document !== 'undefined' && document.createElement) {
    const ctx = kgTextW.ctx || (kgTextW.ctx = document.createElement('canvas').getContext?.('2d'));
    if (ctx && ctx.measureText) { ctx.font = `${weight} ${px}px "Pretendard Variable", Pretendard, sans-serif`; const w = ctx.measureText(String(text)).width; if (w > 0) return w; }
  }
  let w = 0; for (const ch of String(text)) w += ch.charCodeAt(0) > 0x2E7F ? px : ch === ' ' ? px * 0.3 : px * 0.6; return w;
}
/** 겹치지 않게 보일 이름을 고른다(화면 좌표). 늘 보이는 이름이 서로 포개지거나 점에 가려 읽히지 않던 것을 막는다.
    items: [{ id, x, y, r(점 반지름), w, h(이름 상자), prio }] — prio 가 큰 것부터 자리를 잡는다. fixed: 이미 자리가 정해진 글자 상자들 [x0, y0, x1, y1](고른 항목 · 모은 이웃 · 묶음 이름).
    discs: 가리면 안 되는 점들 [{ id, x, y, r }]. zones: 글자를 쓰지 않는 자리(캔버스 안 도구 줄 · 묶음 조각). size: 캔버스 { w, h }.
    이름은 점 아래 → 위 → 오른쪽 → 왼쪽 차례로 빈 자리를 찾고, 없으면 보이지 않는다(확대하면 자리가 생겨 나온다). → Map(id → 'b' | 't' | 'r' | 'l') */
function kgPlaceLabels(items, fixed, discs, zones, size) {
  const placed = fixed.map(b => b.slice()), out = new Map(), PAD = 3;
  const cross = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
  const free = (box, self) => box[0] >= 2 && box[2] <= size.w - 2 && box[1] >= 2 && box[3] <= size.h - 2 && !zones.some(z => cross(box, z)) && !placed.some(p => cross(box, p))
    && !discs.some(d => d.id !== self && d.x + d.r > box[0] && d.x - d.r < box[2] && d.y + d.r > box[1] && d.y - d.r < box[3]);
  for (const it of items.slice().sort((a, b) => b.prio - a.prio || (a.id < b.id ? -1 : 1))) {
    const { x, y, r, w, h } = it, g = 4;
    const at = { b: [x - w / 2 - PAD, y + r + g - 1, x + w / 2 + PAD, y + r + g + h + PAD], t: [x - w / 2 - PAD, y - r - g - h - PAD, x + w / 2 + PAD, y - r - g + 1],
      r: [x + r + g - 1, y - h / 2 - PAD, x + r + g + w + 2 * PAD, y + h / 2 + PAD], l: [x - r - g - w - 2 * PAD, y - h / 2 - PAD, x - r - g + 1, y + h / 2 + PAD] };
    const side = ['b', 't', 'r', 'l'].find(k => free(at[k], it.id));
    if (side) { placed.push(at[side]); out.set(it.id, side); }
  }
  return out;
}
const kgSize = deg => Math.round(14 + Math.min(26, Math.sqrt(deg) * 5.2));      // 점의 지름: 이어진 수의 제곱근에 비례(14 ~ 40)

/** 항목 하나의 표시. s = { sel, near: Set, path: Set | null, match: Set, query: boolean, only: Set | null } → ['pick' | 'near', 'path', 'hit', 'dim'] 가운데 해당하는 것.
    밝은 것 = 고른 것(pick) · 바로 이어진 것(near) · 이상 패턴 경로(path) · 검색에 걸린 것(hit). 그 가운데 하나라도 켜져 있으면 나머지는 흐리다(dim).
    only = 펼쳐 보는 묶음의 항목들: 고름 · 경로 · 검색이 없을 때 그 묶음 밖의 항목이 흐리다 */
function kgMarks(id, s) {
  const pick = id === s.sel, near = !pick && s.near.has(id), path = !!s.path && s.path.has(id), hit = s.match.has(id);
  const dim = !(pick || near || path || hit) && (s.sel != null || !!s.path || s.query || (!!s.only && !s.only.has(id)));
  return [pick && 'pick', near && 'near', path && 'path', hit && 'hit', dim && 'dim'].filter(Boolean);
}
/** 선의 표시: 고른 항목에 닿으면 near, 아니고 두 끝이 모두 경로 안이며 관계(type)가 경로의 관계(KG.PATH_RELS)면 path, 그 밖은 상태가 하나라도 있을 때 dim */
function kgEdgeMarks(a, b, s, type) {
  if (s.sel != null && (a === s.sel || b === s.sel)) return ['near'];
  if (s.path && s.path.has(a) && s.path.has(b) && KG.PATH_RELS.includes(type)) return ['path'];
  return s.sel != null || s.path || s.query || (s.only && !(s.only.has(a) && s.only.has(b))) ? ['dim'] : [];
}
/** 한 항목에 이어진 것을 방향 · 관계 종류로 묶는다 → { out: [[type, [id…]]…], inn: […] }. out = 이 항목이 가리키는 것, inn = 이 항목을 가리키는 것.
    묶음은 많은 것부터(같으면 관계 종류 이름 순), 묶음 안은 받은 차례. 오른쪽 칸과 캔버스의 모으기가 같은 차례를 쓴다 */
function kgRelGroups(edges, id) {
  const out = new Map(), inn = new Map();
  const put = (m, type, other) => { const list = m.get(type) || m.set(type, []).get(type); if (!list.includes(other)) list.push(other); };
  for (const e of edges) { const a = String(e.from), b = String(e.to); if (a === b) continue; if (a === id) put(out, e.type, b); if (b === id) put(inn, e.type, a); }
  const order = m => [...m.entries()].sort((p, q) => q[1].length - p[1].length || (p[0] < q[0] ? -1 : 1));
  return { out: order(out), inn: order(inn) };
}
/** 모은 자리를 비워 주는 자리: 고른 항목 둘레의 상자(box) 안에 있던 다른 항목(at)은 상자 밖으로 나가고, 상자 가까이 있던 항목은 그만큼 물러난다.
    고른 항목에서 본 방향은 그대로 두고 거리만 늘린다 — 상자 가장자리까지의 거리 R 에 대해 안쪽(r ≤ R)은 R + 0.35 r, 바깥쪽은 r + 0.35 R × (1 − (r − R) / R)(r ≥ 2R 이면 그대로).
    거리의 차례가 바뀌지 않으므로 항목끼리 포개지지 않는다 */
function kgMakeRoom(center, box, at) {
  let dx = at.x - center.x, dy = at.y - center.y, r = Math.hypot(dx, dy);
  if (r < 1e-6) { dx = 0; dy = 1; r = 1e-6; }
  const ux = dx / r, uy = dy / r;
  const R = Math.min(ux ? (ux > 0 ? box.x1 - center.x : center.x - box.x0) / Math.abs(ux) : Infinity, uy ? (uy > 0 ? box.y1 - center.y : center.y - box.y0) / Math.abs(uy) : Infinity);
  const to = r <= R ? R + 0.35 * r : r + 0.35 * R * Math.max(0, 1 - (r - R) / R);
  return { x: Math.round((center.x + ux * to) * 10) / 10, y: Math.round((center.y + uy * to) * 10) / 10 };
}
/** 고른 항목(center) 둘레에 이웃을 모으는 자리. 좌표는 배치 좌표이고 배율 1 에서 화면 px 과 같다.
    left · right = 위에서 아래로 놓을 이웃 id 들(left = 고른 항목을 가리키는 것, right = 고른 항목이 가리키는 것). box = 캔버스 { w, h }.
    id 가 'head:' 로 시작하는 것은 관계 이름 줄이다(그 아래 이웃들의 관계 이름을 적는 자리 — 줄의 맨 끝에 혼자 남기지 않는다).
    한 쪽의 이웃은 세로 간격 17 ~ 26 으로 타원 호에 놓는다(이름을 바깥쪽에 한 줄씩 쓸 수 있는 간격). 한 줄에 다 못 놓으면 바깥쪽에 줄을 더해 고르게 나눈다.
    → { at: Map(id → { x, y, side: 'L' | 'R' }), labelW(이름을 쓸 폭), bounds: { x0, y0, x1, y1 }(고른 항목 · 이웃 · 이름이 다 들어가는 상자) } */
function kgGather(center, left, right, box) {
  const [sMin, sMax] = KG.STEP, availH = Math.max(120, box.h - 230);
  const rx = Math.max(96, Math.min(210, (box.w - 2 * KG.LABEL - 64) / 2));
  const labelW = Math.round(Math.max(56, Math.min(KG.LABEL, (box.w - 2 * rx - 48) / 2)));
  const cap = Math.floor(availH / KG.STEP_TIGHT) + 1, at = new Map();      // 한 줄에 놓는 수의 한도: 화면을 조금 줄여 맞췄을 때 줄 사이가 STEP_TIGHT 아래로 내려가지 않는 만큼
  const split = ids => {
    if (ids.length <= cap) return ids.length ? [ids] : [];
    const per = Math.ceil(ids.length / Math.ceil(ids.length / cap)), cols = []; let cur = [];
    ids.forEach((id, i) => { if (cur.length >= per && !String(ids[i - 1]).startsWith('head:')) { cols.push(cur); cur = []; } cur.push(id); });
    cols.push(cur);
    return cols;
  };
  let halfH = 0; const reach = { L: 0, R: 0 };
  const place = (ids, side) => {
    const sign = side === 'R' ? 1 : -1, cols = split(ids);
    const heights = cols.map(col => (col.length - 1) * (col.length > 1 ? Math.max(sMin, Math.min(sMax, availH / (col.length - 1))) : 0));
    const ry = Math.max(rx, Math.max(0, ...heights) / 2 / 0.72);      // 호의 끝에서도 가로로 0.69 rx 만큼은 떨어진다. 바깥 줄은 같은 호를 이름 폭만큼 옮긴 것이다
    cols.forEach((col, c) => {
      const n = col.length, H = heights[c], step = n > 1 ? H / (n - 1) : 0;
      col.forEach((id, i) => {
        const y = n > 1 ? -H / 2 + i * step : 0, x = rx * Math.sqrt(1 - (y / ry) * (y / ry)) + c * (labelW + 36);
        at.set(id, { x: Math.round((center.x + sign * x) * 10) / 10, y: Math.round((center.y + y) * 10) / 10, side });
      });
      halfH = Math.max(halfH, H / 2); reach[side] = rx + c * (labelW + 36) + labelW + 16;
    });
  };
  place(left, 'L'); place(right, 'R');
  return { at, labelW, bounds: { x0: center.x - Math.max(reach.L, 90), x1: center.x + Math.max(reach.R, 90), y0: center.y - halfH - 56, y1: center.y + halfH + 28 } };
}

const kg = { cy: null, of: null, key: null, home: new Map(), raw: new Map(), deg: new Map(), labelW: KG.LABEL, colW: 120, back: null, moved: false, matches: [], matchAt: 0, state: null, raf: 0, at: null };
const kgColor = n => ONTO_GROUPS[groupOf(n.label)].color;
const kgKey = n => ONTO_GROUPS[groupOf(n.label)].key;
const kgPx = px => ele => px / ele.cy().zoom();      // 화면에서 늘 같은 크기
const kgStill = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
function kgDrop() { if (kg.cy) kg.cy.destroy(); Object.assign(kg, { cy: null, of: null, key: null, home: new Map(), back: null, state: null, at: null }); }

function kgStyle() {
  const font = 'Pretendard Variable, Pretendard, sans-serif', BG = KG.BG;
  return [
    { selector: 'node', style: { width: 'data(size)', height: 'data(size)', 'background-color': 'data(color)', 'background-opacity': 0.92, 'border-width': 1.5, 'border-color': BG,
        label: '', color: '#d5dde8', 'font-family': font, 'font-size': kgPx(KG.FONT), 'font-weight': 500, 'text-valign': 'bottom', 'text-halign': 'center', 'text-margin-y': kgPx(4), 'text-margin-x': 0,
        'text-max-width': kgPx(KG.NAME_W), 'text-wrap': 'ellipsis', 'min-zoomed-font-size': 0, 'text-outline-color': BG, 'text-outline-width': kgPx(2.5), 'text-outline-opacity': 1, 'overlay-opacity': 0,
        'transition-property': 'opacity, border-width, border-color', 'transition-duration': 180 } },
    // 이름: 겹치지 않게 자리를 잡은 것만 보인다(kgLabels 가 lab 과 자리 lp 를 단다). 글자는 화면에서 늘 같은 크기이고 캔버스 바탕색 테두리를 둘러 점 · 선 위에서도 읽힌다
    { selector: 'node.lab', style: { label: 'data(name)' } },
    { selector: 'node.lab[?hub]', style: { 'font-size': kgPx(KG.FONT_HUB), 'font-weight': 600, color: '#ffffff', 'text-max-width': kgPx(KG.NAME_W_HUB) } },
    { selector: 'node.lab[lp = "t"]', style: { 'text-valign': 'top', 'text-margin-y': kgPx(-4) } },
    { selector: 'node.lab[lp = "r"]', style: { 'text-valign': 'center', 'text-halign': 'right', 'text-margin-x': kgPx(4), 'text-margin-y': 0 } },
    { selector: 'node.lab[lp = "l"]', style: { 'text-valign': 'center', 'text-halign': 'left', 'text-margin-x': kgPx(-4), 'text-margin-y': 0 } },
    { selector: 'edge', style: { width: 1, 'line-color': '#53637a', opacity: 0.38, 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#53637a', 'arrow-scale': 0.7,
        'font-family': font, 'font-size': kgPx(10.5), 'font-weight': 500, color: '#c5cdf8', 'text-background-color': BG, 'text-background-opacity': 0.92, 'text-background-padding': 2, 'text-background-shape': 'roundrectangle',
        'overlay-opacity': 0, 'transition-property': 'opacity, line-color', 'transition-duration': 180 } },
    { selector: 'node.gtitle', style: { width: 1, height: 1, 'background-opacity': 0, 'border-width': 0, label: 'data(name)', color: 'data(color)', 'font-size': kgPx(13), 'font-weight': 600, 'text-valign': 'top', 'text-margin-y': 0,
        'text-max-width': 600, 'text-wrap': 'none', 'text-outline-width': kgPx(4), 'text-opacity': 0.95 } },
    { selector: 'node.tuck', style: { 'text-opacity': 0 } },
    { selector: '.dim', style: { opacity: 0.1, 'text-opacity': 0 } },
    { selector: 'edge.dim', style: { opacity: 0.04 } },
    { selector: 'node.hover', style: { label: 'data(name)', color: '#ffffff', 'font-size': kgPx(12), 'text-opacity': 1, 'text-max-width': kgPx(260), 'z-index': 70 } },
    { selector: 'node.path', style: { 'border-color': '#ffffff', 'border-width': kgPx(1.5), color: '#ffffff', 'z-index': 40 } },
    { selector: 'node.path[side]', style: { label: 'data(name)', 'font-size': kgPx(12) } },
    // 경로를 줄로 놓았을 때(고른 것이 없을 때): 앞 세 줄은 이름을 점 아래에, 마지막 줄은 오른쪽에
    { selector: 'node.path[side = "B"]', style: { width: kgPx(18), height: kgPx(18), 'text-margin-y': kgPx(5), 'text-max-width': ele => kg.colW / ele.cy().zoom() } },
    { selector: 'node.path[side = "R"]', style: { width: ele => KG.nearSize(ele) / ele.cy().zoom(), height: ele => KG.nearSize(ele) / ele.cy().zoom(), 'text-valign': 'center', 'text-halign': 'right', 'text-margin-x': kgPx(6), 'text-margin-y': 0,
        'text-max-width': ele => kg.labelW / ele.cy().zoom() } },
    { selector: 'edge.path', style: { opacity: 0.9, width: kgPx(1.4), 'line-color': KG.BLUE, 'target-arrow-color': KG.BLUE, 'arrow-scale': 0.9, 'z-index': 35 } },
    { selector: 'node.near', style: { width: ele => KG.nearSize(ele) / ele.cy().zoom(), height: ele => KG.nearSize(ele) / ele.cy().zoom(), 'border-color': '#ffffff', 'border-width': kgPx(1.5), label: 'data(name)', color: '#ffffff', 'font-size': kgPx(12), 'text-valign': 'center', 'text-margin-y': 0,
        'text-max-width': ele => kg.labelW / ele.cy().zoom(), 'z-index': 50 } },
    { selector: 'node.near[side = "R"]', style: { 'text-halign': 'right', 'text-margin-x': kgPx(6) } },
    { selector: 'node.near[side = "L"]', style: { 'text-halign': 'left', 'text-margin-x': kgPx(-6) } },
    { selector: 'edge.near', style: { opacity: 0.95, width: kgPx(1.5), 'line-color': KG.NOW, 'target-arrow-color': KG.NOW, 'arrow-scale': 0.9, 'z-index': 45 } },
    // 관계 이름: 모은 이웃의 줄에서 관계 묶음마다 그 위에 한 줄로 적는다(선을 따라 적으면 선이 모이는 곳에서 글이 겹치고 기운다). 점은 그리지 않는다
    { selector: 'node.rhead', style: { width: 1, height: 1, 'background-opacity': 0, 'border-width': 0, label: 'data(name)', color: '#aab2ff', 'font-size': kgPx(10.5), 'font-weight': 600, 'text-valign': 'center',
        'text-margin-y': 0, 'text-wrap': 'none', 'text-max-width': 600, events: 'no', 'z-index': 48 } },
    { selector: 'node.rhead[side = "R"]', style: { 'text-halign': 'right', 'text-margin-x': kgPx(-2) } },
    { selector: 'node.rhead[side = "L"]', style: { 'text-halign': 'left', 'text-margin-x': kgPx(2) } },
    { selector: 'node.rhead[side = "B"]', style: { 'text-halign': 'center', color: '#9aa7b5' } },
    { selector: 'node.hit', style: { 'border-color': KG.HIT, 'border-width': kgPx(2.5), color: KG.HIT, 'font-size': kgPx(KG.FONT_HUB), 'font-weight': 600, 'text-max-width': kgPx(KG.NAME_W_HIT), 'z-index': 60 } },
    { selector: 'node.pick', style: { width: kgPx(26), height: kgPx(26), 'border-color': '#ffffff', 'border-width': kgPx(3), 'underlay-color': KG.NOW, 'underlay-opacity': 0.35, 'underlay-padding': kgPx(8), 'underlay-shape': 'ellipse', color: '#ffffff',
        label: 'data(name)', 'font-size': kgPx(14), 'font-weight': 700, 'z-index': 99, 'text-wrap': 'none', 'text-max-width': 2000, 'text-valign': 'top', 'text-halign': 'center', 'text-margin-y': kgPx(-8), 'text-margin-x': 0 } },
    { selector: 'node.pick.hit', style: { 'border-color': KG.HIT, color: '#ffe6ad' } },      // 고른 것이 검색에도 걸렸다: 테두리는 검색의 노랑, 글자는 밝은 노랑
    { selector: '.off', style: { display: 'none' } },
  ];
}
// 묶음 안의 배치(fcose)와 묶음의 자리. 난수를 고정해 같은 그래프는 늘 같은 자리에 놓인다
function kgLayout(cy) {
  const rnd = Math.random; let seed = KG.SEED;
  Math.random = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };
  const total = cy.nodes().length, world = [80 * Math.sqrt(total), 62 * Math.sqrt(total)], boxes = [];
  try {
    for (const gr of ONTO_GROUPS) {
      const ns = cy.nodes().filter(n => n.data('g') === gr.key); if (!ns.length) continue;
      ns.union(ns.edgesWith(ns)).layout({ name: 'fcose', quality: 'proof', randomize: true, animate: false, fit: false, nodeRepulsion: 3600, idealEdgeLength: 38, edgeElasticity: 0.4, gravity: 0.8,
        nodeSeparation: 40, packComponents: true, tile: true, numIter: 2500 }).run();
      const bb = ns.boundingBox({ includeLabels: false });
      boxes.push({ gr, ns, cx: gr.at[0] * world[0], cy: gr.at[1] * world[1], r: Math.max(bb.w, bb.h) / 2 + 34, ox: bb.x1 + bb.w / 2, oy: bb.y1 + bb.h / 2 });
    }
  } finally { Math.random = rnd; }
  for (let k = 0; k < 80; k++) for (const a of boxes) for (const b of boxes) {
    if (a === b) continue;
    const dx = b.cx - a.cx, dy = b.cy - a.cy, d = Math.hypot(dx, dy) || 1, need = a.r + b.r;
    if (d < need) { const m = (need - d) / 2 / d; a.cx -= dx * m; a.cy -= dy * m; b.cx += dx * m; b.cy += dy * m; }
  }
  for (const b of boxes) {
    b.ns.shift({ x: b.cx - b.ox, y: b.cy - b.oy });
    cy.add({ group: 'nodes', data: { id: 'title:' + b.gr.key, name: `${b.gr.title} ${b.ns.length}`, color: b.gr.color, g: b.gr.key }, classes: 'gtitle', position: { x: b.cx, y: b.cy - b.r + 22 }, selectable: false, grabbable: false });
  }
  return boxes.map(b => ({ key: b.gr.key, title: b.gr.title, color: b.gr.color, count: b.ns.length }));
}
function kgBuild(g) {
  kgDrop();
  const raw = new Map(g.nodes.map(n => [String(n.id), n])), deg = new Map();
  const edges = g.edges.map(e => ({ from: String(e.from), to: String(e.to), type: String(e.type) })).filter(e => raw.has(e.from) && raw.has(e.to) && e.from !== e.to)
    .sort((a, b) => a.from < b.from ? -1 : a.from > b.from ? 1 : a.to < b.to ? -1 : a.to > b.to ? 1 : a.type < b.type ? -1 : a.type > b.type ? 1 : 0);
  edges.forEach(e => { deg.set(e.from, (deg.get(e.from) || 0) + 1); deg.set(e.to, (deg.get(e.to) || 0) + 1); });
  const elements = [...raw.keys()].sort().map(id => { const n = raw.get(id), d = deg.get(id) || 0;
    return { data: { id, name: nodeName(n), kind: LABEL_KO[n.label] || n.label, g: kgKey(n), color: kgColor(n), size: kgSize(d), deg: d, hub: d >= KG.HUB } }; })
    .concat(edges.map((e, i) => ({ data: { id: 'e' + i, source: e.from, target: e.to, type: e.type, rel: RELATION_KO[e.type] || e.type } })));
  const cy = kg.cy = cytoscape({ container: $('#ontoMap'), elements, minZoom: 0.12, maxZoom: KG.ZOOM_MAX, boxSelectionEnabled: false, autoungrabify: true, style: kgStyle() });
  const groups = kgLayout(cy);
  kg.home = new Map(cy.nodes().not('.gtitle').map(n => [n.id(), { ...n.position() }]));
  Object.assign(kg, { of: g, key: ent.graphAsset, raw, deg, back: null, moved: false, at: null });
  // 묶음 조각(캔버스 아래쪽 — 범례를 겸한다): 항목이 있는 묶음만. 누르면 그 묶음이 꺼지고 켜진다
  $('#ontoLayers').innerHTML = groups.map(gr => `<button type="button" class="cv-chip" data-layer="${gr.key}" aria-pressed="true" style="--c:${gr.color}"><i></i>${esc(gr.title)}<span class="num">${gr.count}</span></button>`).join('');
  [...ent.hidden].forEach(key => { if (!groups.some(gr => gr.key === key)) ent.hidden.delete(key); });
  if (ent.group && !groups.some(gr => gr.key === ent.group)) ent.group = null;
  if (ent.sel != null && !kg.home.has(ent.sel)) ent.sel = null;
  kgFit(true);
  cy.on('zoom', () => { if (!kg.raf) kg.raf = requestAnimationFrame(() => { kg.raf = 0; if (kg.cy === cy) cy.style().update(); }); });
  cy.on('scrollzoom dragpan pinchzoom', () => { kg.moved = true; });
  cy.on('viewport', () => kgLabelsSoon());
  cy.on('tap', 'node', ev => { if (ev.target.hasClass('gtitle')) kgGroup(ent.group === ev.target.data('g') ? null : ev.target.data('g')); else kgPick(ev.target.id()); });
  cy.on('tap', ev => { if (ev.target === cy && ent.sel != null) kgPick(null); });      // 빈 곳을 누르면 고른 것이 풀린다
  cy.on('mouseover', 'node', ev => { if (!ev.target.hasClass('gtitle')) ev.target.addClass('hover'); $('#ontoMap').style.cursor = 'pointer'; });
  cy.on('mouseout', 'node', ev => { ev.target.removeClass('hover'); $('#ontoMap').style.cursor = ''; });
}
// 보일 이름을 다시 고른다(kgPlaceLabels). 부르는 때: 그린 뒤 · 상태가 바뀐 뒤 · 항목이 옮겨 간 뒤 · 화면을 옮기거나 확대한 뒤 · 캔버스 크기가 바뀐 뒤
function kgLabels() {
  const cy = kg.cy; if (!cy) return;
  const W = cy.width(), H = cy.height(), z = cy.zoom(); if (!W || !H) return;
  const bar = $('#view-ontology .canvas-bar'), foot = $('#ontoLayers'), hint = $('#ontoHint');
  const top = bar && bar.offsetHeight ? bar.offsetTop + bar.offsetHeight + 4 : 0, low = Math.min(foot && foot.offsetHeight ? foot.offsetTop : H, hint && hint.offsetHeight ? hint.offsetTop : H) - 4;
  const zones = [[0, 0, W, top], [0, low, W, H]];      // 캔버스 안 도구 줄 · 안내 한 줄 · 묶음 조각 자리에는 이름을 쓰지 않는다
  const fixed = [], discs = [], items = [];
  const box = (n, px, weight, maxW, how) => {      // 자리가 정해진 글자(고른 항목 · 모은 이웃 · 줄 이름 · 묶음 이름)의 상자
    const p = n.renderedPosition(), r = n.renderedWidth() / 2, w = Math.min(maxW, kgTextW(n.data('name'), px, weight)) + 6, h = px * 1.4;
    return how === 'T' ? [p.x - w / 2, p.y - r - h - 10, p.x + w / 2, p.y - r - 2] : how === 'B' ? [p.x - w / 2, p.y + r + 2, p.x + w / 2, p.y + r + h + 8]
      : how === 'R' ? [p.x + r + 3, p.y - h / 2 - 2, p.x + r + w + 9, p.y + h / 2 + 2] : how === 'L' ? [p.x - r - w - 9, p.y - h / 2 - 2, p.x - r - 3, p.y + h / 2 + 2] : [p.x - w / 2, p.y - h / 2, p.x + w / 2, p.y + h / 2];
  };
  cy.nodes().forEach(n => {
    if (!n.visible()) return;
    if (n.hasClass('gtitle')) {      // 묶음 이름: 테두리(4px)까지 넉넉히 잡는다. 캔버스 안 도구 자리에 걸리면 그동안 보이지 않는다
      const b = box(n, 13, 600, 600, 'T'), wide = [b[0] - 8, b[1] - 12, b[2] + 8, b[3] + 8], tucked = zones.some(zn => wide[0] < zn[2] && zn[0] < wide[2] && wide[1] < zn[3] && zn[1] < wide[3]);
      if (n.hasClass('tuck') !== tucked) n.toggleClass('tuck', tucked);
      if (!n.hasClass('dim') && !tucked) fixed.push(wide);
      return;
    }
    if (n.hasClass('rhead')) { fixed.push(box(n, 10.5, 600, 600, n.data('side') === 'B' ? 'C' : n.data('side'))); return; }
    if (n.hasClass('dim')) return;
    const p = n.renderedPosition(), r = n.renderedWidth() / 2;
    discs.push({ id: n.id(), x: p.x, y: p.y, r: r + 1 });
    if (n.hasClass('pick')) fixed.push(box(n, 14, 700, 2000, 'T'));
    else if (n.hasClass('near')) fixed.push(box(n, 12, 500, kg.labelW, n.data('side') || 'R'));
    else if (n.hasClass('path') && n.data('side')) fixed.push(box(n, 12, 500, n.data('side') === 'B' ? kg.colW : kg.labelW, n.data('side')));
    else {
      const hit = n.hasClass('hit'), hub = n.data('hub'), px = hit || hub ? KG.FONT_HUB : KG.FONT;
      items.push({ id: n.id(), x: p.x, y: p.y, r, w: Math.min(hit ? KG.NAME_W_HIT : hub ? KG.NAME_W_HUB : KG.NAME_W, kgTextW(n.data('name'), px, hit || hub ? 600 : 500)) + 2, h: px * 1.3,
        prio: (hit ? 1e6 : n.hasClass('path') ? 5e5 : 0) + n.data('deg') });
    }
  });
  const sides = kgPlaceLabels(items, fixed, discs, zones, { w: W, h: H });
  cy.batch(() => cy.nodes().forEach(n => {
    const side = sides.get(n.id());
    if (side) { if (n.data('lp') !== side) n.data('lp', side); n.addClass('lab'); }
    else if (n.hasClass('lab')) n.removeClass('lab');
  }));
}
// 조금 뒤에 한 번(끌거나 확대하는 동안은 기다렸다가 멈춘 뒤, 항목이 옮겨 가는 동안은 다 옮겨 간 뒤)
function kgLabelsSoon(ms = 90) { clearTimeout(kg.labelTimer); kg.labelTimer = setTimeout(() => { if (kg.cy) kgLabels(); }, ms); }
// 화면을 상자(배치 좌표)가 다 보이게 옮긴다. 위의 도구 줄과 아래의 묶음 조각 자리는 비운다
function kgShow(box, max, still = kgStill()) {
  const cy = kg.cy, W = cy.width(), H = cy.height(), top = 82, bottom = 78, side = 16;      // 위의 도구 줄 · 아래의 안내 한 줄과 묶음 조각 자리
  const bw = Math.max(1, box.x1 - box.x0), bh = Math.max(1, box.y1 - box.y0);
  const zoom = Math.max(cy.minZoom(), Math.min(max, (W - 2 * side) / bw, (H - top - bottom) / bh));
  const pan = { x: W / 2 - (box.x0 + bw / 2) * zoom, y: top + (H - top - bottom) / 2 - (box.y0 + bh / 2) * zoom };
  cy.stop();
  if (still) cy.viewport({ zoom, pan }); else cy.animate({ zoom, pan }, { duration: 380, easing: 'ease-out-cubic' });
}
const kgBoxOf = eles => { const b = eles.boundingBox({ includeLabels: false }); return { x0: b.x1 - 40, x1: b.x2 + 40, y0: b.y1 - 40, y1: b.y2 + 40 }; };
// 전체가 보이게 맞춘다: 보이는 점들의 자리로만 잰다(이름의 크기는 배율에 따라 달라져 같은 지도가 다르게 맞춰진다)
function kgFit(still) {
  const cy = kg.cy; if (!cy) return;
  kg.moved = false;
  const shown = cy.nodes().filter(n => n.visible());
  if (shown.length) kgShow(kgBoxOf(shown), 1.6, still === true || kgStill());
}
function kgZoomBy(f) { const cy = kg.cy; if (!cy) return; kg.moved = true; cy.zoom({ level: cy.zoom() * f, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); }
// 고른 항목의 이웃을 그 둘레로 모으고(kgGather) 그 자리에 있던 다른 항목은 비켜 주며(kgMakeRoom), 고름을 풀면 모두 제자리로 돌려보낸다. 모은 줄에는 관계 묶음마다 관계 이름 한 줄(rhead)을 끼운다 —
// 나가는 쪽은 「→ 감지 증상」, 들어오는 쪽은 「경보 패턴 →」(관계 이름은 화살표를 따라 읽는 말이다)
function kgArrange() {
  const cy = kg.cy, sel = ent.sel, want = new Map();
  cy.batch(() => { cy.nodes('.rhead').remove(); cy.nodes().filter(n => n.data('side')).forEach(n => n.removeData('side')); });
  kg.at = null;
  if (sel != null) {
    const used = new Set([sel]);
    const shown = id => kg.home.has(id) && !ent.hidden.has(kgKey(kg.raw.get(id))) && !used.has(id) && !!used.add(id);
    const rel = kgRelGroups(kg.of.edges, sel);
    const slots = (groups, side) => groups.map(([type, ids]) => [type, ids.filter(shown)]).filter(([, ids]) => ids.length).flatMap(([type, ids]) => [`head:${side}:${type}`, ...ids]);
    const right = slots(rel.out, 'R'), left = slots(rel.inn, 'L'), home = kg.home.get(sel);
    const lay = kgGather(home, left, right, { w: cy.width(), h: cy.height() });
    kg.labelW = lay.labelW; kg.at = lay;
    cy.batch(() => lay.at.forEach((p, id) => {
      if (!id.startsWith('head:')) { want.set(id, p); cy.getElementById(id).data('side', p.side); return; }
      const name = RELATION_KO[id.slice(7)] || id.slice(7);
      cy.add({ group: 'nodes', data: { id, name: p.side === 'R' ? '→ ' + name : name + ' →', side: p.side }, classes: 'rhead', position: { x: home.x, y: home.y }, selectable: false, grabbable: false });
      want.set(id, p);
    }));
    kg.home.forEach((at, id) => { if (id !== sel && !want.has(id)) want.set(id, kgMakeRoom(home, lay.bounds, at)); });      // 그 자리에 있던 다른 항목은 비켜 준다
  } else if (kg.state && kg.state.route) {
    // 이상 패턴 경로: 패턴 | 증상 | 고장 유형 | 원인 · 조치 방법의 줄로 놓는다(끈 묶음의 항목은 뺀다). 이름 순
    const on = ids => ids.filter(id => kg.home.has(id) && !ent.hidden.has(kgKey(kg.raw.get(id)))).sort((a, b) => kgCollator.compare(cy.getElementById(a).data('name'), cy.getElementById(b).data('name')) || (a < b ? -1 : 1));
    const r = kg.state.route, home = kg.home.get(r.pattern);
    if (home && !ent.hidden.has(kgKey(kg.raw.get(r.pattern)))) {
      const lay = kgPathLay(home, { pattern: r.pattern, symptoms: on(r.symptoms), modes: on(r.modes), causes: on(r.causes), skills: on(r.skills) }, { w: cy.width(), h: cy.height() });
      kg.labelW = lay.labelW; kg.colW = lay.colW; kg.at = lay;
      const mid = { x: (lay.bounds.x0 + lay.bounds.x1) / 2, y: (lay.bounds.y0 + lay.bounds.y1) / 2 };
      cy.batch(() => lay.at.forEach((p, id) => {
        if (!id.startsWith('head:')) { want.set(id, p); cy.getElementById(id).data('side', p.side); return; }
        cy.add({ group: 'nodes', data: { id, name: id.slice(7), side: p.side }, classes: 'rhead', position: { x: home.x, y: home.y }, selectable: false, grabbable: false });
        want.set(id, p);
      }));
      kg.home.forEach((at, id) => { if (!want.has(id)) want.set(id, kgMakeRoom(mid, lay.bounds, at)); });
    }
  }
  const still = kgStill();
  cy.nodes('.lab').removeClass('lab');      // 옮겨 가는 동안에는 이름을 걷고, 다 옮겨 간 뒤 다시 고른다
  kgLabelsSoon(still ? 30 : 440);
  cy.nodes().not('.gtitle').forEach(n => {
    const to = want.get(n.id()) || kg.home.get(n.id()), p = n.position();
    if (Math.abs(p.x - to.x) < 0.5 && Math.abs(p.y - to.y) < 0.5 && !n.animated()) return;
    n.stop(true, false);
    if (still) n.position({ x: to.x, y: to.y }); else n.animate({ position: { x: to.x, y: to.y } }, { duration: 340, easing: 'ease-out-cubic' });
  });
}
// 지금 상태(고름 · 경로 · 검색 · 끈 묶음)를 그림에 입힌다. 그림을 다시 만들지 않고 표시만 바꾼다
function kgApplyState() {
  const cy = kg.cy; if (!cy || !kg.of) return;
  const q = ent.search.trim().toLowerCase(), off = id => ent.hidden.has(kgKey(kg.raw.get(id)));
  if (ent.sel != null && (!kg.home.has(ent.sel) || off(ent.sel))) ent.sel = null;      // 끈 묶음의 항목은 고른 채로 두지 않는다
  const route = kgPath(kg.of, ent.focus), path = route ? route.ids : null;
  const ids = [...kg.home.keys()];
  const match = new Set(q ? ids.filter(id => !off(id) && (cy.getElementById(id).data('name').toLowerCase().includes(q) || id.toLowerCase().includes(q))) : []);
  const near = new Set();
  if (ent.sel != null) cy.getElementById(ent.sel).neighborhood('node').forEach(n => near.add(n.id()));
  if (ent.group && ent.hidden.has(ent.group)) ent.group = null;
  const only = ent.group ? new Set(ids.filter(id => kgKey(kg.raw.get(id)) === ent.group)) : null;
  const s = { sel: ent.sel, near, path, match, query: !!q, only };
  const arrange = !kg.state || kg.state.sel !== s.sel || kg.state.hidden !== [...ent.hidden].sort().join('|') || kg.state.focus !== ent.focus;
  kg.state = { ...s, route, hidden: [...ent.hidden].sort().join('|'), focus: ent.focus };
  const ALL = 'pick near path hit dim';
  cy.batch(() => {
    cy.nodes().forEach(n => {
      if (n.hasClass('rhead')) return;
      if (n.hasClass('gtitle')) { n.toggleClass('off', ent.hidden.has(n.data('g'))).toggleClass('dim', s.sel != null || !!s.path || s.query || (!!ent.group && ent.group !== n.data('g'))); return; }
      n.removeClass(ALL).addClass(kgMarks(n.id(), s).join(' ')).toggleClass('off', off(n.id()));
    });
    cy.edges().forEach(e => e.removeClass('near path dim').addClass(kgEdgeMarks(e.data('source'), e.data('target'), s, e.data('type')).join(' ')));
  });
  if (arrange) kgArrange(); else kgLabelsSoon(220);      // 흐리던 항목이 밝아지는 0.18초 뒤에
  $('#ontoLayers').querySelectorAll('[data-layer]').forEach(b => b.setAttribute('aria-pressed', String(!ent.hidden.has(b.dataset.layer))));
  // 검색에 걸린 것의 차례: 묶음 → 이름
  kg.matches = ids.filter(id => match.has(id)).sort((a, b) => groupOf(kg.raw.get(a).label) - groupOf(kg.raw.get(b).label) || kgCollator.compare(cy.getElementById(a).data('name'), cy.getElementById(b).data('name')) || (a < b ? -1 : 1));
  if (kg.matchAt >= kg.matches.length) kg.matchAt = 0;
  const fmtN = v => Number(v).toLocaleString('ko-KR'), word = ent.search.trim();
  $('#ontoHint').textContent = s.sel != null ? '왼쪽은 고른 항목을 가리키는 것, 오른쪽은 고른 항목이 가리키는 것입니다. 빈 곳을 누르면 제자리로 돌아갑니다'
    : path ? `「${cy.getElementById(ent.focus).data('name') || ''}」 경보에서 증상 · 고장 유형 · 원인 · 조치 방법으로 가는 길입니다. 항목을 누르면 그 항목에 이어진 것이 보입니다`
    : q ? (match.size ? `이름에 「${word}」이 든 항목 ${fmtN(match.size)}개가 밝게 보입니다. Enter 를 누르면 차례로 고릅니다` : `이름에 「${word}」이 든 항목이 없습니다`)
    : ent.group ? `「${ONTO_GROUPS.find(x => x.key === ent.group).title}」 묶음만 밝게 보입니다. 확대하면 이름이 더 보이고, 묶음 이름을 다시 누르면 전체로 돌아갑니다`
    : '점을 누르면 이어진 항목이 그 둘레에 모입니다. 묶음 이름을 누르면 그 묶음을 크게 봅니다';
  $('#ontoStats').textContent = `항목 ${fmtN(kg.of.nodes.length)} · 연결 ${fmtN(kg.of.edges.length)}` + (path ? ` · 강조 경로 ${fmtN(path.size)}개` : '') + (q ? ` · 검색 결과 ${fmtN(match.size)}개` : '');
  const next = $('#ontoNext'); next.hidden = match.size < 2;
  next.querySelector('.num').textContent = `${Math.min(kg.matchAt + 1, match.size)} / ${match.size}`;
  ontoNote(ent.definitionNamesError ? ent.definitionNamesError + ' 흐름 항목의 이름이 「흐름 이름 확인 불가」로 보입니다. [다시 읽기]를 누르세요.' : '');
}
function drawGraph() {
  const g = ent.graph; if (!g) return;
  if (kg.of !== g) kgBuild(g);
  kgApplyState();
  renderNodePanel();
}
// 항목을 고르거나(같은 항목을 다시 누르면 풀린다) 푼다. 고르면 화면이 고른 것과 이웃이 다 보이게 옮겨 가고, 풀면 고르기 전의 화면으로 돌아간다
function kgPick(id) {
  const cy = kg.cy; if (!cy) return;
  const was = ent.sel;
  ent.sel = id == null || ent.sel === id ? null : id;
  if (was == null && ent.sel != null) kg.back = { zoom: cy.zoom(), pan: { ...cy.pan() } };
  kgApplyState(); renderNodePanel();
  if (ent.sel != null && kg.at) kgShow(kg.at.bounds, KG.ZOOM_PICK);
  else if (ent.sel == null && was != null && kg.back) { cy.stop(); if (kgStill()) cy.viewport(kg.back); else cy.animate(kg.back, { duration: 340, easing: 'ease-out-cubic' }); kg.back = null; }
}
// 묶음 하나를 크게 본다(key) 또는 전체로 돌아간다(null): 그 묶음만 밝게 하고 그 묶음이 캔버스에 차게 옮긴다. 오른쪽 칸의 묶음 접기와 지도의 묶음 이름이 함께 쓴다
function kgGroup(key) {
  const cy = kg.cy; if (!cy) return;
  ent.group = key || null;
  if (ent.sel != null) { kg.back = null; kgPick(null); } else { kgApplyState(); renderNodePanel(); }
  if (ent.focus) return;      // 이상 패턴 경로를 보는 중이면 그 화면을 지킨다
  const own = ent.group ? cy.nodes().filter(n => !n.hasClass('gtitle') && !n.hasClass('rhead') && n.data('g') === ent.group && n.visible()) : null;
  if (own && own.length) kgShow(kgBoxOf(own), 2.2); else kgFit();
}
// 흐름 이름을 못 읽었을 때의 한 줄(화면 머리 아래) — 통계 글에 이어 붙이지 않는다
function ontoNote(text) { const n = $('#ontoNote'); n.textContent = text; n.hidden = !text; }

/* ---------------- 오른쪽 칸(밝은 판): 묶음 · 종류 → 이름 → ID → 속성 → 이어진 항목(관계 이름별 조각) → 그 밖의 속성 ---------------- */
function renderNodePanel() {
  const box = $('#ontoNode');
  const g = ent.graph; if (!g || !kg.cy) return;
  const n = ent.sel != null ? kg.raw.get(ent.sel) : null;
  const sig = JSON.stringify([ent.graphAsset, ent.sel, ent.sel == null ? ent.group : '', g.nodes.length, g.edges.length, UI.namesVersion, ent.definitionNamesError]);
  if (box.dataset.sig === sig && box.innerHTML) return;      // 검색 · 확대처럼 고른 항목이 그대로인 동안에는 다시 그리지 않는다(읽던 자리 · 편 접기가 유지된다)
  box.dataset.sig = sig;
  const chip = (id, extra = '') => { const m = kg.raw.get(id); return m ? `<button type="button" class="chip" data-go="${esc(id)}" style="--c:${kgColor(m)}" title="${esc(LABEL_KO[m.label] || m.label)}"><i></i><span>${esc(nodeName(m))}</span>${extra}</button>` : ''; };
  if (!n) {
    // 아무것도 고르지 않았을 때: 이 지도에 무엇이 들어 있는지의 목차 — 묶음마다 종류와 수가 한 줄로 보이고, 묶음을 펼치면 그 묶음의 항목 이름이 종류별로 다 보인다
    // (펼친 묶음은 지도에서도 크게 보인다 — kgGroup). 이름을 누르면 그 항목이 골라진다. 그 아래에 가장 많이 이어진 항목
    const top = [...kg.home.keys()].sort((a, b) => (kg.deg.get(b) || 0) - (kg.deg.get(a) || 0) || (a < b ? -1 : 1)).slice(0, 6);
    const byLabel = new Map();
    [...kg.home.keys()].forEach(id => { const l = kg.raw.get(id).label; (byLabel.get(l) || byLabel.set(l, []).get(l)).push(id); });
    const nameOf = id => kg.cy.getElementById(id).data('name');
    byLabel.forEach(ids => ids.sort((a, b) => kgCollator.compare(nameOf(a), nameOf(b)) || (a < b ? -1 : 1)));
    let groupsN = 0;
    const index = ONTO_GROUPS.map((gr, gi) => {
      const labels = gr.other ? [...byLabel.keys()].filter(l => groupOf(l) === gi).sort() : gr.labels.filter(l => byLabel.has(l));
      if (!labels.length) return '';
      groupsN++;
      const total = labels.reduce((sum, l) => sum + byLabel.get(l).length, 0), open = ent.group === gr.key;
      // 항목 이름은 펼친 묶음에만 그린다(닫힌 묶음까지 다 그리면 조각이 수백 개다)
      const body = open ? labels.map(l => { const ids = byLabel.get(l);
        return `<section class="rel-group"><h4>${esc(LABEL_KO[l] || l)} <span class="num">${ids.length}</span></h4><div class="chips">${ids.slice(0, 12).map(id => chip(id)).join('')}` +
          (ids.length > 12 ? `<details class="rel-more"><summary class="chip">+${ids.length - 12}</summary><div class="chips">${ids.slice(12).map(id => chip(id)).join('')}</div></details>` : '') + `</div></section>`; }).join('') : '';
      return `<details class="fold kg-group" data-group="${gr.key}"${open ? ' open' : ''}><summary><span class="gtag" style="--c:${gr.color}"><i></i>${esc(gr.title)}</span><span class="muted num">${total}</span>` +
        `<span class="kg-kinds">${labels.map(l => `${esc(LABEL_KO[l] || l)} ${byLabel.get(l).length}`).join(' · ')}</span></summary><div class="fold-body">${body}</div></details>`;
    }).join('');
    box.innerHTML = `<div class="node-head kg-index-head"><h2>이 지도에 들어 있는 것</h2><p>항목 ${kg.home.size.toLocaleString('ko-KR')}개가 묶음 ${groupsN}개에 들어 있습니다. 묶음을 펼치면 항목 이름이 보이고, 이름이나 지도의 점을 누르면 그 항목의 속성과 이어진 항목이 나옵니다.</p></div>` +
      `<div class="kg-index">${index}</div>` +
      (top.length ? `<div class="node-sec"><h3>가장 많이 이어진 항목</h3><div class="chips">${top.map(id => chip(id, `<span class="num muted">${kg.deg.get(id) || 0}</span>`)).join('')}</div></div>` : '');
    box.querySelectorAll('details.kg-group > summary').forEach(sum => sum.addEventListener('click', ev => { ev.preventDefault(); const key = sum.parentElement.dataset.group; kgGroup(ent.group === key ? null : key); }));
  } else {
    const group = ONTO_GROUPS[groupOf(n.label)], id = String(n.id);
    const lead = n.props?.description || '';                 // 한 줄 설명은 서버가 준 값이 있을 때만(화면이 지어 붙이지 않는다)
    const props = Object.entries(n.props || {}).filter(([k, v]) => !['id', 'name', 'description'].includes(k) && v !== '' && v != null);
    const named = props.filter(([k]) => PROP_KO[k]), other = props.filter(([k]) => !PROP_KO[k]);
    const value = (v, k) => { const text = typeof v === 'string' ? v : typeof v === 'boolean' ? (v ? '예' : '아니요') : Array.isArray(v) && v.every(x => typeof x !== 'object') ? v.join(', ') : typeof v === 'number' ? String(v) : JSON.stringify(v);
      if (PROP_EXPR.includes(k)) return `<span class="mono">${esc(text)}</span>`;
      if (k === 'tag') { const name = window.hydWords.fieldName(text.toLowerCase()); return name && name !== text.toLowerCase() ? `${esc(name)} <span class="mono muted">${esc(text)}</span>` : `<span class="mono">${esc(text)}</span>`; }
      return text.length > 160 ? `<details class="kv-more"><summary>${esc(text.slice(0, 60))}…</summary><div>${esc(text)}</div></details>` : esc(text); };
    // 이어진 것을 관계 이름별로 묶는다. 관계 이름표(RELATION_KO)는 나가는 쪽에서 본 말이라(증상 → 고장 「나타내는 고장」) 들어오는 쪽에 그대로 붙이면 거꾸로 읽힌다 —
    // 나가는 관계는 관계 이름으로, 들어오는 관계는 상대의 종류(증상 · 원인 …)로 묶고 관계 이름은 작게 곁들인다
    const rel = kgRelGroups(g.edges, id), groups = [];
    rel.out.forEach(([type, ids]) => groups.push({ dir: 'out', title: RELATION_KO[type] || type, note: '', ids }));
    const inn = new Map();
    rel.inn.forEach(([type, ids]) => ids.forEach(o => { const kind = LABEL_KO[kg.raw.get(o)?.label] || kg.raw.get(o)?.label || '이어진 항목', key = kind + '|' + type;
      (inn.get(key) || inn.set(key, { dir: 'in', title: kind, note: RELATION_KO[type] || type, ids: [] }).get(key)).ids.push(o); }));
    groups.push(...inn.values());
    const total = groups.reduce((sum, x) => sum + x.ids.length, 0);
    const relHtml = groups.map(x => `<section class="rel-group" data-dir="${x.dir}"><h4>${UI.icon(x.dir === 'out' ? 'arrow-right' : 'arrow-left')}${esc(x.title)} <span class="num">${x.ids.length}</span>${x.note ? `<span class="rel-note">${esc(x.note)}</span>` : ''}</h4>` +
      `<div class="chips">${x.ids.slice(0, 14).map(o => chip(o)).join('')}${x.ids.length > 14 ? `<details class="rel-more"><summary class="chip">+${x.ids.length - 14}</summary><div class="chips">${x.ids.slice(14).map(o => chip(o)).join('')}</div></details>` : ''}</div></section>`).join('');
    box.innerHTML = `<div class="node-head fade-in"><span class="gtag" style="--c:${group.color}"><i></i>${esc(group.title)} · ${esc(LABEL_KO[n.label] || n.label)}</span><h2>${esc(nodeName(n))}</h2><p class="mono">${esc(id)}</p>` +
      (lead ? `<p class="node-lead">${esc(UI.words(lead))}</p>` : '') + `</div>` +
      (named.length ? `<div class="node-sec"><dl class="kv">${named.map(([k, v]) => `<dt>${esc(PROP_KO[k])}</dt><dd>${value((PROP_VALUE_KO[k] || {})[v] || v, k)}</dd>`).join('')}</dl></div>` : '') +
      `<div class="node-sec"><h3>이어진 항목<span class="num">${total}</span></h3>${relHtml || '<p class="muted">이어진 항목이 없습니다.</p>'}</div>` +
      (other.length ? `<div class="node-sec node-fold">${UI.fold(`그 밖의 속성<span class="muted num">${other.length}</span>`, `<dl class="kv">${other.map(([k, v]) => `<dt class="mono">${esc(k)}</dt><dd>${value(v)}</dd>`).join('')}</dl>`)}</div>` : '');
    box.scrollTop = 0;
  }
  box.querySelectorAll('[data-go]').forEach(a => a.addEventListener('click', () => { const id = a.dataset.go; if (ent.sel !== id) kgPick(id); }));
}
function initOntology() {
  const map = $('#ontoMap');
  // 캔버스 크기가 바뀌면 그림도 따라간다. 사람이 옮기거나 확대하지 않았고 고른 것이 없으면 전체가 보이게 다시 맞춘다
  new ResizeObserver(() => { const cy = kg.cy; if (!cy || !map.clientWidth) return; cy.resize(); if (!kg.moved && ent.sel == null && !ent.focus && !ent.group) kgFit(true); else kgLabelsSoon(); }).observe(map);
  // 키보드: 화살표로 옮기고 + · − 로 확대 · 축소, 0 은 화면에 맞춤, Esc 는 고른 것 풀기. 항목은 찾기 칸에서 이름을 치고 Enter 로 고르거나 오른쪽 칸의 조각으로 고른다
  map.addEventListener('keydown', ev => {
    const cy = kg.cy; if (!cy || ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const move = { ArrowLeft: [48, 0], ArrowRight: [-48, 0], ArrowUp: [0, 48], ArrowDown: [0, -48] }[ev.key];
    if (move) { ev.preventDefault(); kg.moved = true; cy.panBy({ x: move[0], y: move[1] }); }
    else if (ev.key === '+' || ev.key === '=') { ev.preventDefault(); kgZoomBy(1.25); }
    else if (ev.key === '-') { ev.preventDefault(); kgZoomBy(1 / 1.25); }
    else if (ev.key === '0') { ev.preventDefault(); kgFit(); }
    else if (ev.key === 'Escape' && ent.sel != null) { ev.preventDefault(); kgPick(null); }
  });
  $('#ontoZoomOut').addEventListener('click', () => kgZoomBy(1 / 1.25));
  $('#ontoZoomIn').addEventListener('click', () => kgZoomBy(1.25));
  $('#ontoFit').addEventListener('click', () => kgFit());
  // 묶음 조각: 누르면 그 묶음을 끄고 켠다
  $('#ontoLayers').addEventListener('click', ev => {
    const b = ev.target.closest('[data-layer]'); if (!b) return;
    ent.hidden.has(b.dataset.layer) ? ent.hidden.delete(b.dataset.layer) : ent.hidden.add(b.dataset.layer);
    kgApplyState(); renderNodePanel();
  });
  $('#ontoAsset').addEventListener('change', () => loadGraph(true));
  $('#ontoNs').addEventListener('change', () => { ent.sel = null; loadGraph(true); });
  // 이상 패턴 경로: 그 패턴에서 증상 · 고장 유형 · 원인 · 조치 방법까지 가는 길만 밝게 하고 줄로 놓은 뒤, 그 길이 다 보이게 옮긴다. 「전체」로 돌리면 제자리로
  $('#ontoFocus').addEventListener('change', ev => {
    ent.focus = ev.target.value || null;
    if (ent.sel != null) kgPick(null); else { kgApplyState(); renderNodePanel(); }
    const cy = kg.cy; if (!cy) return;
    if (ent.focus && kg.at) kgShow(kg.at.bounds, 1.1); else if (!ent.focus) kgFit();
  });
  // 이름 찾기: 치는 대로 걸린 항목이 밝아지고(노란 테두리) 그것들이 보이게 옮긴다. Enter · [다음]은 걸린 항목을 차례로 고른다(Shift+Enter 는 앞 항목)
  const goMatch = step => {
    if (!kg.matches.length) return;
    const at = kg.matches.indexOf(ent.sel);
    kg.matchAt = at < 0 ? 0 : (at + step + kg.matches.length) % kg.matches.length;
    const id = kg.matches[kg.matchAt];
    if (ent.sel !== id) kgPick(id); else kgApplyState();
  };
  $('#ontoSearch').addEventListener('input', ev => {
    ent.search = ev.target.value; kg.matchAt = 0; drawGraph();
    const cy = kg.cy; if (!cy || ent.sel != null) return;
    const hits = cy.nodes('.hit');
    if (hits.length) kgShow(kgBoxOf(hits), 1.1); else if (!ent.search.trim() && !kg.moved) kgFit();
  });
  $('#ontoSearch').addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); goMatch(ev.shiftKey ? -1 : 1); } });
  $('#ontoNext').addEventListener('click', () => goMatch(1));
  $('#ontoReload').addEventListener('click', () => loadGraph(true));
  // 질의 보기(문서 등록 화면 아래의 접기): 지식 지도를 읽는 질의문을 종류별로 보인다
  document.querySelectorAll('#ontoTpl button').forEach(b => b.addEventListener('click', async () => {
    document.querySelectorAll('#ontoTpl button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
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

/* ================================================= 규칙 판단(판단 실험)
   짜임(디자인 기준 5-6): 왼쪽 조건 판(index.html #decForm) → 오른쪽 결과(#decResult). 결과는 결론 한 줄과 숫자 넷 → 조치 후보 비교(.opts) → 근거(원인 · 증거) → 원문 접기.
   판단 한 번은 1초 안에 끝난다 — 그동안은 결과 자리에 읽는 중 줄(스켈레톤)을 두고 단추가 「판단하는 중 · 걸린 시간」으로 바뀐다 */
const decEmpty = () => `<section class="empty"><header><figure>${UI.icon('scale')}</figure><h3>아직 모의 판단을 하지 않았습니다</h3><p>왼쪽에서 설비와 이상 패턴을 고르고 [모의 판단]을 누르면 1순위 조치와 그 근거가 여기에 보입니다.</p></header></section>`;
async function loadDecisionView() {
  const sel = $('#decPattern'), box = $('#decResult');
  if (!box.innerHTML) box.innerHTML = decEmpty();
  // 설비 목록은 서버가 준다(plant /api/state 의 units — 유압 설비 화면이 읽는 그 응답). 화면에 설비 이름을 적어 두지 않는다
  const assetSel = $('#decAsset');
  if (!assetSel.options.length) {
    try { const units = (state.plant && state.plant.units) || (await getJ(API.plant + '/api/state')).units || {}; Object.keys(units).forEach(a => assetSel.append(new Option(a, a))); ent.assetsError = Object.keys(units).length ? '' : '설비 상태 응답에 설비가 없습니다'; }
    catch (e) { ent.assetsError = e.message; }
  }
  if (sel.options.length && assetSel.options.length) return;
  const pats = sel.options.length ? [...sel.options] : await loadPatterns();
  if (!sel.options.length)
  pats.forEach(p => sel.append(new Option(`${p.name}${p.failureModes && p.failureModes.length ? ' → ' + p.failureModes.join(', ') : ''}`, p.code)));
  $('#decRun').disabled = !pats.length || !assetSel.options.length;
  if (!pats.length) box.innerHTML = UI.errorBlock(UI.t('dec.noPatterns'), ent.patternsError || '지식 그래프에 이상 패턴이 없습니다', { retry: true });
  else if (!assetSel.options.length) box.innerHTML = UI.errorBlock('설비 목록을 읽지 못했습니다', ent.assetsError, { retry: true });
  else if (box.querySelector('.alert')) box.innerHTML = decEmpty();      // 다시 읽어 됐으면 앞의 오류 판을 거둔다
  box.querySelector('[data-retry]')?.addEventListener('click', () => loadDecisionView());
}
async function runDecision() {
  if (ent.busy) return; ent.busy = true;
  ent.result = null; // A failed new request must not retain the previous successful judgment.
  const end = hydLive.busy($('#decRun'), '판단하는 중'), box = $('#decResult');
  const facts = {};
  if ($('#decMode').value) facts.plc_mode = $('#decMode').value;
  if ($('#decState').value) facts.plc_state = $('#decState').value;
  if ($('#decFan').value !== '') facts.fan100_hours = Number($('#decFan').value);
  if ($('#decStandby').value) facts.standby_ready = $('#decStandby').value === 'true';
  box.innerHTML = `<section class="panel"><div class="panel-head">${UI.loading()}</div></section>`;
  try { ent.result = await postJ(API.agent + '/api/agent/decide', { asset: $('#decAsset').value, pattern: $('#decPattern').value, facts }); ent.facts = facts; renderDecision(); }
  catch (e) { box.innerHTML = UI.errorBlock(UI.t('dec.failed'), e.message, { retry: true }); }
  finally { ent.busy = false; end(false); }
  box.querySelector('[data-retry]')?.addEventListener('click', runDecision);
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
// 처리 과정 원문: 판단 서비스가 거친 단계가 한 줄씩(키트 .line — 이름 · 한 일 · 시각). 단계 이름은 화면 말로 적고, 서버가 남긴 설명과 출력 원문은 그 아래 접기에 둔다
const DEC_STEPS = { ontology: ['판단 규칙 읽기', '지식에서 이 판단의 결정표와 규칙을 읽습니다.'], facts: ['판단에 쓸 값 가져오기', '규칙이 검사할 값을 지식이 정한 출처(업무 시스템 · 센서)에서 가져옵니다.'],
  forecast: ['조치별 예측', '조치마다 설비 예측 모델로 조치 뒤 값을 계산합니다.'], candidates: ['조치 후보 고르기', '고장 유형과 설비 상태 규칙으로 후보를 고릅니다.'],
  compliance: ['규정 적합성 검사', '후보마다 규칙의 기준에 대어 제외 · 감점 · 경고를 정합니다.'], tradeoffs: ['성과 득실과 선례', '조치가 성과 지표에 주는 득실과 같은 고장 유형의 선례를 모읍니다.'],
  rank: ['점수와 순위', '순위 규칙의 식으로 점수를 내고 순위를 정합니다.'] };
function decTrace(steps) {
  return `<div class="stream-log" style="max-height:none;padding:0">` + steps.map(s => {
    const [name, note] = DEC_STEPS[s.name] || UI.steps[s.name] || [s.name, s.note || ''];
    const ok = s.status === 'DONE', raw = [s.note ? `설명: ${s.note}` : '', s.output == null ? '' : JSON.stringify(s.output, null, 1)].filter(Boolean).join('\n\n');
    return `<div class="line" data-kind="${ok ? 'ok' : 'fail'}">${UI.icon(ok ? 'check' : 'x')}<span class="line-text"><b>${esc(name)}</b><span class="line-sub">${esc(ok ? note : UI.status(s.status) + (note ? ' · ' + note : ''))}</span></span><span class="line-time num">${esc(UI.time(s.t))}</span></div>` +
      UI.fold(esc(UI.t('raw')), raw ? `<pre class="code">${esc(raw)}</pre>` : '<p class="muted">출력 데이터가 없습니다.</p>');
  }).join('') + '</div>';
}
// 결과(디자인 기준 5-6): 결론 한 줄 + 숫자 넷 → 조치 후보 비교(.opts — 1순위와 진 안이 왜 졌는지) → 근거(판정 원인과 증거) → 접기(판단에 쓴 값 · 후보별 근거 · 점수 계산 · 적용한 규칙 · 처리 과정 원문)
function renderDecision() {
  const d = ent.result; const box = $('#decResult');
  if (!d || !d.result) { box.innerHTML = UI.errorBlock(UI.status(d && d.status) || UI.t('dec.failed'), (d && d.error) || '판단 결과가 오지 않았습니다. 조건을 바꿔 다시 눌러 보세요.'); return; }
  const r = d.result, opts = r.options || [], causes = d.causes || [], c0 = causes[0], trace = r.trace || [];
  const maxAbs = Math.max(1, ...opts.map(o => Math.abs(o.score || 0)));
  // 결론 문장은 서버가 준 설명의 첫 문장 그대로다(화면이 지어 붙이지 않는다). 첫 문장이 후보마다의 사유를 줄줄이 단 긴 문장이면(「…제외됐다: A(…); B(…)」) 쌍점 앞까지만 큰 글로 두고 나머지는 그 아래 줄글로 내린다
  const text = UI.idText(r.explanation), sentence = firstSentence(text), colon = sentence.length > 110 ? sentence.indexOf(': ') : -1;
  const first = colon > 0 ? sentence.slice(0, colon) + '.' : sentence, rest = String(text || '').slice(colon > 0 ? colon + 2 : sentence.length).trim();
  const top = opts.find(o => o.id === r.recommended) || null;
  const feasible = opts.filter(o => o.feasible), second = feasible.filter(o => !top || o.id !== top.id).sort((a, b) => (a.rank || 99) - (b.rank || 99))[0];
  const gap = top && second && Number.isFinite(top.score) && Number.isFinite(second.score) ? `<small>2순위보다 ${(top.score - second.score).toFixed(2)} 높음</small>` : '';
  const fact = (label, value) => `<div><dt>${esc(label)}</dt><dd>${value}</dd></div>`;

  // 머리: 결론(큰 글) · 무엇을 언제 판단했나 · 숫자 넷
  let html = `<section class="panel"><div class="panel-head"><div><div class="result-label">${UI.icon('sparkles')}결론 ${UI.chip(d.status)}</div><h2>${esc(first)}</h2>` +
    `<p>${esc([d.asset, UI.idText((d.scenario || {}).name || ''), '모의 판단 ' + UI.dateTime(d.created)].filter(Boolean).join(' · '))}</p></div></div>` +
    `<dl class="turn-facts">${fact(UI.t('dec.causeTop') + ' 원인', c0 ? esc(UI.idText(c0.name)) : '없음')}${fact('1순위 점수', top && Number.isFinite(top.score) ? `<span class="num">${signNum(top.score)}</span>${gap}` : '–')}` +
    `${fact(UI.t('dec.candidates'), `<span class="num">${feasible.length}</span><small>개 가능${opts.length - feasible.length ? ` · ${opts.length - feasible.length}개 제외` : ''}</small>`)}` +
    `${fact('발동한 규칙', `<span class="num">${trace.filter(t => t.fired).length}</span><small>/ ${trace.length}개</small>`)}</dl>`;
  // 2026-10-25 수업 점검: 바꾼 판단 조건을 읽는 규칙이 지금 지식에 없으면 결과가 그대로라 학생이 고장으로 오해했다(HM-8에는 보호 정지 규칙이 없다)
  const unused = unusedFacts(ent.facts, trace);
  const notes = (rest ? `<p class="result-sub">${esc(rest)}</p>` : '') +
    (unused.length ? `<p class="muted" role="status">${esc(unused.map(k => UI.t(FACT_LABEL[k])).join(', '))}: 지금 지식의 규칙 가운데 이 조건을 읽는 규칙이 없어 결과에 영향이 없습니다.</p>` : '') +
    (d.moneyError ? `<p class="muted" data-tone="danger" role="status">손익(원)을 계산하지 못했습니다: ${esc(d.moneyError)}</p>` : '');
  if (notes) html += `<div class="panel-sec">${notes}</div>`;

  // 조치 후보 비교: 1순위 줄이 맨 위(제품색 면). 진 안은 둘째 줄에 까닭 — 제외된 안은 걸린 규칙, 남은 안은 감점 규칙과 1순위와의 점수 차
  const kind = o => [(o.actions || []).some(a => a.kind === 'command') ? UI.t('chip.control') : '', (o.actions || []).some(a => a.kind !== 'command') ? UI.t('chip.workOrder') : ''].filter(Boolean).join(' · ');
  const why = o => {
    if (!o.feasible) return `<small>제외 — ${esc((o.violations || []).map(v => UI.ruleLabel(v)).join(' · ') || '걸린 규칙 이름 없음')}</small>`;
    if (top && o.id === top.id) return '';
    const parts = [];
    if ((o.penalties || []).length) parts.push('감점 — ' + o.penalties.map(v => UI.ruleLabel(v)).join(' · '));
    if (top && Number.isFinite(o.score) && Number.isFinite(top.score)) parts.push(`1순위보다 ${(top.score - o.score).toFixed(2)}점 낮음`);
    return parts.length ? `<small>${esc(parts.join(' · '))}</small>` : '';
  };
  const ordered = opts.slice().sort((a, b) => (b.id === r.recommended) - (a.id === r.recommended) || (b.feasible ? 1 : 0) - (a.feasible ? 1 : 0) || (a.rank || 99) - (b.rank || 99));
  html += `<div class="panel-sec"><h3>${esc(UI.t('dec.candidates'))} 비교<span class="muted">${opts.length}개${top ? ' 가운데 1순위' : ''}</span></h3>` + (opts.length
    ? `<div class="table-container"><table class="opts"><thead><tr><th></th><th>조치</th><th>구분</th><th class="num">${esc(UI.t('card.score'))}</th><th></th><th>${esc(UI.t('card.approver'))}</th></tr></thead><tbody>` +
      ordered.map(o => `<tr${o.id === r.recommended ? ' data-pick' : ''}><td><span class="rank num">${o.feasible ? esc(o.rank) : '–'}</span></td>` +
        `<td><b>${esc(UI.idText(o.name))}</b>${o.sopId ? ` <span class="muted mono">${esc(o.sopId)}</span>` : ''}${o.feasible ? '' : ' ' + UI.chipText(UI.t('chip.excluded'), 'danger')}${why(o)}</td><td>${esc(kind(o))}</td>` +
        `<td class="num">${Number.isFinite(o.score) ? signNum(o.score) : '–'}</td><td><div class="bar"><i style="width:${o.feasible ? Math.min(100, Math.round(Math.abs(o.score || 0) / maxAbs * 100)) : 0}%"></i></div></td><td>${esc((o.approver || {}).name || '–')}</td></tr>`).join('') +
      '</tbody></table></div>' : UI.empty(UI.t('inc.noCandidates'), '이 설비와 이상 패턴에 맞는 조치 방법이 지식에 없습니다.', 'compact')) + '</div>';

  // 근거: 판정 원인 한 줄과 그 증거(충족 여부는 상태 뱃지와 글로), 다른 원인 후보는 접기
  const evidenceLines = c => (c.evidence || []).map(e => { const unknown = e.status === 'UNKNOWN' || e.passed == null || e.value == null || !!e.error;
    const unit = window.hydWords.unit(e.tag);
    return `<li>${UI.icon(unknown ? 'circle-dashed' : e.passed ? 'check' : 'x')}<span><b>${esc(e.name)}</b> ${UI.chipText(UI.t(unknown ? 'inc.unknown' : e.passed ? 'inc.pass' : 'inc.fail'), unknown ? 'neutral' : e.passed ? 'success' : 'danger')} ${esc(UI.t('inc.observed'))} <span class="num">${esc(fmt(e.value, 3))}</span>${unit ? ' ' + esc(unit) : ''}</span></li>`; }).join('')
    || `<li>${UI.icon('info')}<span>${esc(UI.t('inc.noEvidence'))}</span></li>`;
  const causeLine = c => `<li>${UI.icon('search')}<span><b>${esc(UI.idText(c.name))}</b>${c.failureMode ? ' · 고장 유형 ' + esc(UI.idText(c.failureMode)) : ''} · ${esc(UI.t('card.score'))} <span class="num">${esc(c.score)}</span></span></li>`;
  if (c0) html += `<div class="panel-sec"><h3>근거<span class="muted">${esc(UI.t('dec.causeTop'))} 원인과 관측 값</span></h3><ul class="evid">${causeLine(c0)}${evidenceLines(c0)}</ul>` +
    (causes.length > 1 ? UI.fold(`${esc(UI.t('dec.causeMore'))}<span class="muted">${causes.length - 1}개</span>`, causes.slice(1).map(c => `<ul class="evid">${causeLine(c)}${evidenceLines(c)}</ul>`).join('<br>')) : '') + '</div>';

  // 원문 접기: 판단에 쓴 값 · 후보별 근거 카드 · 점수 계산 방법 · 적용한 규칙 · 처리 과정 원문과 판단 번호
  const prov = d.provenance || [];
  const tr = trace.slice().sort((a, b) => (b.fired ? 1 : 0) - (a.fired ? 1 : 0) || (b.skill ? 1 : 0) - (a.skill ? 1 : 0));      // 발동한 규칙이 위로
  const target = t => t.skill ? UI.idText((opts.find(o => o.id === t.skill) || {}).name || t.skill) : '';
  html += '<div class="panel-sec">' +
    UI.fold(`${esc(UI.t('dec.inputs'))}<span class="muted">${prov.length}개 · 출처와 가져온 방법</span>`, prov.length
      ? `<div class="table-container"><table class="table"><thead><tr><th>${esc(UI.t('dec.col.input'))}</th><th>${esc(UI.t('dec.col.value'))}</th><th>${esc(UI.t('dec.col.source'))}</th><th>${esc(UI.t('dec.col.how'))}</th></tr></thead><tbody>` +
        prov.map(p => `<tr><td>${esc(p.name)}</td><td>${p.error ? `<span class="muted" data-tone="danger">${esc(p.error)}</span>` : esc(factValue(p.variable, p.value))}</td><td>${esc(p.sourceName || UI.who(p.source))}</td><td class="muted">${esc(p.how || '')}</td></tr>`).join('') + '</tbody></table></div>'
      : `<p class="muted">이 판단은 입력 값의 출처를 남기지 않았습니다.</p>`) +
    UI.fold(`조치 후보별 근거 · 예측 · 절차<span class="muted">${opts.length}개</span>`, `<div class="hitl-opts">` + opts.map(o => cardHtml(o, { rec: r.recommended, maxAbs, decision: { ...r, facts: d.facts, origin: d.origin } })).join('') + '</div>') +
    (r.rankRule ? UI.fold(esc(UI.t('card.scoreHow')), `<p class="muted">${esc(r.rankRule.annotation || '')}</p>`) : '') +
    UI.fold(`${esc(UI.t('dec.rules'))}<span class="muted">${tr.filter(t => t.fired).length}개 발동 · 전체 ${tr.length}개</span>`,
      `<div class="table-container"><table class="table"><thead><tr><th>${esc(UI.t('dec.col.rule'))}</th><th>${esc(UI.t('dec.col.target'))}</th><th>${esc(UI.t('dec.col.result'))}</th></tr></thead><tbody>` +
      tr.map(t => `<tr><td>${esc(UI.ruleLabel(t))}<p class="muted">${esc(t.decision === 'dec:action-candidates' ? UI.t('dec.ruleSelect') : UI.t('dec.ruleCompliance'))}</p>${UI.fold(esc(UI.t('raw')), `<code>${esc(t.rule)}</code> <code>${esc(t.when || '')}</code>`)}</td><td>${esc(target(t))}</td>` +
        `<td>${t.fired ? UI.chipText(UI.t('dec.fired'), 'accent') : (t.unknown && t.unknown.length ? `<span class="muted">${esc(UI.t('dec.noFact'))}: ${esc(t.unknown.map(k => window.hydWords.fieldName(k)).join(', '))}</span>` : `<span class="muted">${esc(UI.t('dec.notApplicable'))}</span>`)}</td></tr>`).join('') + '</tbody></table></div>') +
    UI.fold(`${esc(UI.t('dec.trace'))} 원문<span class="muted">판단 번호 포함</span>`, `<dl class="kv"><dt>판단 번호</dt><dd class="mono">${esc(d.id)}</dd></dl>` + decTrace(d.steps || [])) +
    '</div>';
  const scope = UI.evaluationHtml(r, d);      // 평가 범위(모의 순위인지 실행 조건 검사인지)는 서버 기록 그대로, 맨 아래 한 줄
  if (scope) html += `<div class="panel-sec">${scope}</div>`;
  box.innerHTML = html + '</section>';
}

$('#decForm').addEventListener('submit', e => { e.preventDefault(); runDecision(); });

/* ================================================= 업무 시스템 기록(유압 설비)
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
    if (ent.decisionsError) list.innerHTML = UI.errorBlock(UI.t('proc.listError'), ent.decisionsError);
    const paged = UI.page(ent.decisions, ent.decShown, d => d.id === ent.decSel);
    for (const d of paged.rows) {
      const it = el('button', 'row'); it.type = 'button';
      it.setAttribute('aria-current', String(d.id === ent.decSel));
      it.dataset.itemId = d.id;
      it.innerHTML = `<span class="row-ic">${UI.icon('scale')}</span><span class="row-title">${esc(UI.idText((d.scenario || {}).name || ''))}</span>${UI.chip(d.state)}` +
        `<span class="row-meta">${esc(d.asset || '')} · ${esc(UI.dateTime(d.created))}${(d.origin || {}).kind !== 'alert' ? ' · ' + esc(UI.t('proc.manual')) : ''}${d.override ? ' · ' + esc(UI.t('proc.override')) : ''}</span>`;
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
  let html = `<header class="bz-orphan-head"><h2>${esc(UI.idText(sc.name || ''))} ${UI.chip(d.state)}</h2><p class="muted">${esc(d.asset || '')}${d.approvedBy ? ` · ${esc(UI.t('inc.approvedBy'))} ${esc(UI.who(d.approvedBy))}` : ''}</p></header>`;
  html += UI.evaluationHtml(d) + summaryBlock(d.explanation);
  html += UI.metaFold([[UI.t('dec.asset'), esc(d.asset || '')], ['고장 유형', esc(UI.idText(sc.failureMode || ''))], [UI.t('dec.cause'), esc(UI.idText(sc.cause || ''))], [UI.t('proc.submitted'), esc(UI.dateTime(d.created))], ['ID', `<span class="mono">${esc(d.id)}</span>`]], 'fold.case');
  // 판단은 처리 건의 승인 단계에서만 승인 · 반려한다(서버에 판단 단독 승인 길이 없다 — test_main.test_처리_건_밖의_옛_승인_경로는_없다).
  // 이 절에 오는 것은 처리 건 없이 남은 판단뿐이라, 승인을 기다리는 것이면 승인할 길이 없음을 그대로 알린다
  if (pending) {
    html += `<div class="hitl-opts">${opts.map(o => cardHtml(o, { rec: d.recommended, chosen: d.chosen, maxAbs, decision: d })).join('')}</div>` +
      `<div class="alert" role="status">${UI.icon('info')}<h2>이 판단은 승인하거나 반려할 수 없습니다</h2><section>경보로 열린 처리 건 없이 제출된 판단입니다. 판단은 처리 건 안에서만 승인합니다. 결함 시뮬레이션으로 경보를 내어 처리 건을 열고 그 승인 단계에서 고르세요.</section></div>`;
  } else {
    html += `<h3 class="bz-orphan-sec">${esc(UI.t('decisions'))}</h3><div class="hitl-opts">` + opts.map(o => cardHtml(o, { rec: d.recommended, chosen: d.chosen, maxAbs, decision: d })).join('') + '</div>';
  }
  if ((d.executions || []).length) html += `<h3 class="bz-orphan-sec">${esc(UI.t('proc.executions'))}</h3><div class="bz-orphan-cards">` +
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
  const sum = $('#bzSummary');
  if (!s) {
    sum.innerHTML = ''; $('#txList').innerHTML = '';
    box.innerHTML = ent.entError ? UI.errorBlock(UI.t('proc.noEnt'), ent.entError + ' — 2.5초마다 다시 읽습니다') : '<div class="skeleton" style="height:180px"></div>'.repeat(3);
    return;
  }
  const boards = systemBoards(s);
  // 결론 먼저: 업무 시스템마다 남은 기록이 몇 건인가 → 그 아래에 시스템마다 표 한 장 → 거래 기록
  sum.innerHTML = boards.map(([sys, rows]) => `<div class="stat"><span class="stat-label">${esc(sys)}</span><span class="stat-value num">${rows.length}<small>건</small></span></div>`).join('') +
    `<div class="stat"><span class="stat-label">거래 기록</span><span class="stat-value num">${ent.tx.length}<small>건</small></span></div>`;
  // 표 한 장 = 업무 시스템 하나. 숫자 칸은 오른쪽 맞춤, 여섯 줄까지 보이고 나머지는 몇 건인지 적는다
  const cell = v => `<td${typeof v === 'number' ? ' class="num"' : ''}>${esc(v ?? '–')}</td>`;
  const t = (rows, cols, labels) => rows.length ? '<div class="table-container" tabindex="0"><table class="table"><thead><tr>' + labels.map((x, i) => `<th${rows.every(r => typeof r[cols[i]] === 'number') ? ' class="num"' : ''}>${esc(x)}</th>`).join('') + '</tr></thead><tbody>' +
    rows.slice(0, 6).map(r => '<tr>' + cols.map(c => cell(r[c])).join('') + '</tr>').join('') + '</tbody></table></div>' + (rows.length > 6 ? `<p class="bz-note">${rows.length}건 가운데 6건만 보입니다(외 ${rows.length - 6}건).</p>` : '') : `<p class="bz-none">${esc(UI.t('proc.noChange'))}</p>`;
  box.innerHTML = boards.map(([sys, rows, cols, labels]) => `<section class="panel bz-board"><div class="panel-head"><h2>${esc(sys)}</h2></div>${t(rows, cols, labels)}</section>`).join('');
  $('#txList').innerHTML = ent.tx.length ? ent.tx.slice(0, 12).map(x => UI.eventRecord({ time: x.t, name: UI.who(x.system), actor: x.by, detail: x.detail, raw: x, extra: txDiffFold(x) })).join('') : `<p class="bz-none">${esc(UI.t('proc.noTx'))}</p>`;
}
// A147: 거래가 바꾼 행의 변경 전·후 — 바뀐 항목만, 기본 닫힘. 기록이 없는 거래(before/after 둘 다 없음)는 접기도 없다
function txDiffFold(x) {
  const b = x.before || null, a = x.after || null;
  if (!b && !a) return '';
  const show = v => v == null || v === '' ? '–' : typeof v === 'object' ? JSON.stringify(v) : /^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(String(v)) ? UI.dateTime(v) : String(v);
  const keys = [...new Set([...Object.keys(b || {}), ...Object.keys(a || {})])].filter(k => JSON.stringify((b || {})[k] ?? null) !== JSON.stringify((a || {})[k] ?? null));
  const body = !keys.length ? `<p class="muted">${esc(UI.t('tx.noDiff'))}</p>`
    : `${b ? '' : `<p class="muted">${esc(UI.t('tx.created'))}</p>`}<div class="table-container"><table class="table"><thead><tr><th>${esc(UI.t('tx.col.field'))}</th><th>${esc(UI.t('tx.col.before'))}</th><th>${esc(UI.t('tx.col.after'))}</th></tr></thead><tbody>` +
      keys.map(k => `<tr><td title="${esc(k)}">${esc(window.hydWords.fieldName(k))}</td><td>${esc(show((b || {})[k]))}</td><td><b>${esc(show((a || {})[k]))}</b></td></tr>`).join('') + '</tbody></table></div>';
  return UI.fold(`${esc(UI.t('tx.beforeAfter'))} ${keys.length}`, body);
}

initOntology();
setInterval(() => { if (state.tab === 'process') refreshProcess(); }, 2500);
// kgMarks · kgEdgeMarks · kgRelGroups · kgGather · kgMakeRoom · kgPath · kgPathLay: 지식 지도의 상태 판정과 이웃을 모으고 비켜 주는 자리(DOM 없이 도는 부분 — 시험이 그대로 부른다). kg: 지금 그린 지도(kg.cy = Cytoscape)
window.hydEnt = { ent, systemBoards, runDecision, loadGraph, refreshProcess, loadDecisionView, renderDecision, kgMarks, kgEdgeMarks, kgRelGroups, kgGather, kgMakeRoom, kgPath, kgPathLay, kgPlaceLabels, KG, kg, RELATION_KO };
