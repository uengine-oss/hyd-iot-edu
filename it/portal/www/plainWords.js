/* A161 처리 기록 — 쉬운 말 사전. 도구 이름 · 시스템 · 값 이름 · 단위 · 규칙 식 · 실행 코드를 사람 말로 바꾼다.
   처리 기록(caseRecord.js)이 쓰고, 다른 화면도 window.hydWords 로 쓸 수 있다. 사전에 없는 것은 지어내지 않고 원래 이름을 그대로 둔다.
   원래 이름(id)은 기본으로 숨기고, 화면의 "원래 이름 보기"를 켜면 이름 옆에 작게 보인다(showIds).

   참고: n8n 실행 화면은 노드 이름을 사람이 붙인 이름으로 보이고 원래 종류(type)는 패널 안쪽에만 둔다
   (https://docs.n8n.io/workflows/executions/), Dify tracing-panel 의 노드 제목도 같은 방식이다(web/app/components/workflow/run/node.tsx). */
(function () {
  const W = { showIds: false };
  try { W.showIds = localStorage.getItem('hyd:record:ids') === '1'; } catch (_) { /* 저장소가 없으면 기본(숨김) */ }

  /* ---------------------------------------------------------------- 시스템 (어디에 물었나 · 어디에 했나) */
  const SERVERS = {
    neo4j: '지식 그래프', 'hyd-dmn': '판단 엔진', enterprise: '업무 DB (생산 · 구매 · 정비)', 'enterprise-maint': '정비 업무 DB',
    'enterprise-purchase': '구매 업무 DB', 'hyd-effects': '메일 · 알림', effects: '메일 · 알림',
  };
  const SYSTEMS = {
    'sys:cmms': '정비 시스템 (CMMS)', 'sys:erp': 'ERP (구매 · 재고)', 'sys:mes': '생산 시스템 (MES)', 'sys:scm': '공급망 (SCM)', 'sys:qms': '품질 시스템',
    'sys:scada': '설비 제어', 'sys:plc': '설비 제어 (PLC)', 'sys:agent': 'AI 일꾼', 'sys:process': '처리 엔진', 'sys:erp-monitor': 'ERP 재고 감시', 'sys:cmms-monitor': '정비 계수기 감시',
    'actr:pump-drive': '펌프 구동부', 'actr:fan-drive': '쿨러 팬 구동부', 'sys:tsdb': '센서 기록 DB', detector: '센서 경보 감지기',
  };
  W.system = id => {
    if (!id) return '';
    if (SYSTEMS[id]) return SYSTEMS[id];
    if (/^sen:/.test(id)) return `센서 ${String(id).slice(4).toUpperCase()}`;
    if (/^sys:/.test(id) || /^actr:/.test(id)) return (UI.names && UI.names[id]) || id.replace(/^\w+:/, '').replace(/[-_]/g, ' ');
    return SERVERS[id] || id;
  };

  /* ---------------------------------------------------------------- 값 이름 · 단위 (센서 태그 · 판단 사실 · 업무 값) */
  const F = {
    ts1: ['유온', '℃'], ts2: ['유온 2', '℃'], ts4: ['캐비닛 온도', '℃'], t_amb: ['주변 온도', '℃'], ce: ['냉각 효율', '%'], ps1: ['토출 압력', 'bar'], fs1: ['유량', 'L/min'],
    vs1: ['진동', 'mm/s'], load: ['펌프 부하', '%'], loadsp: ['펌프 부하 설정', '%'], fanspeedsp: ['쿨러 팬 속도 설정', '%'], valvesp: ['메인 밸브 개도 설정', '%'], load_pct: ['펌프 부하', '%'], fan_pct: ['팬 속도', '%'], score: ['경보 점수', ''], ts1_slope: ['유온 상승 속도', '℃/s'],
    vs1_slope: ['진동 상승 속도', 'mm/s²'], cooler_health: ['쿨러 상태', ''], plc_mode: ['운전 모드', ''], plc_state: ['설비 상태', ''], hot_lot_qty: ['출하 대기 로트', '개'],
    order_due_h: ['납기까지', 'h'], fan100_hours: ['팬 100 % 운전 누적', 'h'], standby_ready: ['예비 설비 준비', ''], order_customer_tier: ['고객 등급', ''],
    order_penalty_per_h: ['지연 보상', '만원/h'], hot_lot_claim: ['출하 로트 클레임', '만원'], oil_analysis_out_of_spec: ['오일 분석 기준 밖', ''],
    cause: ['판정 원인', ''], pattern: ['경보 패턴', ''], failure_mode: ['고장 유형', ''],
    // 정기 정비 (CMMS 계수기 · 계획)
    hours_since_pm: ['마지막 정비 뒤 운전시간', 'h'], pm_since_h: ['마지막 정비 뒤 운전시간', 'h'], pm_interval_h: ['정비 주기', 'h'], pm_tolerance_pct: ['허용 오차', '%'],
    pm_notice_h: ['사전 알림', 'h'], pm_due_in_h: ['정비 기한까지', 'h'], pm_limit_in_h: ['허용 한도까지', 'h'], hours_at_next_window: ['이번 정비 시간의 운전시간', 'h'],
    hours_at_following_window: ['다음 정비 시간의 운전시간', 'h'], pm_crew_available: ['정비 가능 인원', '명'], spare_available: ['정비 키트 재고', '개'],
    night_window_in_h: ['야간 정비 시간까지', 'h'], night_window_at: ['야간 정비 시간', ''], cycle: ['정비 회차', '회'], package: ['정비 묶음', ''], kit_qty: ['키트 수량', '개'],
    kit_part_no: ['키트 부품', ''], bundle_peer: ['함께 정비할 설비', ''], bundle_peer_since_h: ['함께 정비할 설비 운전시간', 'h'], pm_window_open: ['정비 시간 열림', ''],
    // 예비품 (ERP 재고 · 견적)
    part_no: ['부품 번호', ''], name: ['이름', ''], on_hand: ['현재고', '개'], reserved: ['정비 예약', '개'], available: ['가용 재고', '개'], on_order: ['입고 예정', '개'],
    spare_gap: ['가용 재고', '개'], reorder_point: ['재주문점', '개'], target_stock: ['목표 재고', '개'], need_qty: ['필요 수량', '개'], need_by_days: ['필요일까지', '일'],
    below_since: ['기준 아래로 내려간 시각', ''], spare_quotes: ['공급사 견적', ''], po_amount: ['발주 금액', '만원'], lead_slack_days: ['납기 여유', '일'],
    supplier_fail_rate: ['공급사 불량률(비율)', ''], approved_amount: ['승인 금액', '만원'], approved_qty: ['수량', '개'], approved_supplier: ['공급사', ''],
    approved_unit_price: ['단가', '만원'], approved_part_no: ['부품', ''], lead_d: ['리드타임', '일'], delay_d: ['공급사 지연', '일'],
    // 업무 사실 (MES · ERP)
    due_in_h: ['납기까지', 'h'], remaining_qty: ['남은 수량', '개'], rate_per_h: ['시간당 생산', '개/h'], alt_rate_per_h: ['대체 설비 시간당', '개/h'], alt_free_h: ['대체 설비 빌 때까지', 'h'],
    changeover_h: ['전환 시간', 'h'], fg_stock: ['완제품 재고', '개'], ship_in_h: ['출하까지', 'h'], penalty_per_h: ['지연 보상', '만원/h'], failure_cost: ['고장 비용', '만원'],
    claim_cost: ['클레임 비용', '만원'], customer_tier: ['고객 등급', ''], order_id: ['생산 주문', ''], sales_order: ['판매 계약', ''],
  };
  W.fieldName = key => { const k = String(key || ''); const f = F[k] || F[k.toLowerCase()]; return f ? f[0] : (UI.terms['var.' + k] || k.replace(/_/g, ' ')); };
  W.unit = key => { const k = String(key || ''); const f = F[k] || F[k.toLowerCase()]; return f ? f[1] : ''; };
  W.known = key => !!(F[key] || F[String(key || '').toLowerCase()]);
  const STATES = { REMOTE_AUTO: '원격 자동', REMOTE_MANUAL: '원격 수동', LOCAL: '현장 제어', RUN: '운전 중', STOP: '정지', TRIP: '보호 정지', PASS: '통과', DONE: '완료' };
  W.num = v => {
    if (typeof v !== 'number' || !Number.isFinite(v)) return v;
    const a = Math.abs(v);
    return v.toLocaleString('ko-KR', { maximumFractionDigits: a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3 });
  };
  // 값 하나를 화면 말로: 숫자는 자릿수 · 단위, 참거짓은 예 · 아니요, 상태 코드는 한국어, id 는 이름
  W.value = (key, v) => {
    if (v == null || v === '') return '–';
    if (v === true) return '예';
    if (v === false) return '아니요';
    if (typeof v === 'number') { const u = W.unit(key); return `${W.num(v)}${u ? ' ' + u : ''}`; }
    if (typeof v === 'string') {
      if (/^\d{4}-\d\d-\d\dT/.test(v)) return UI.dateTime(v);
      if (STATES[v]) return STATES[v];
      if (key === 'pattern' || /^[A-Z][A-Z_]+$/.test(v) && W.pattern(v) !== v) return W.pattern(v);
      return W.text(v);
    }
    if (Array.isArray(v)) return `${v.length}건`;
    return '…';
  };

  /* ---------------------------------------------------------------- 경보 패턴 · 규칙 식 */
  const PATTERNS = { PM_DUE: '정기 정비 도래', SPARE_BELOW_MIN: '예비품 재고 기준 이탈' };
  W.pattern = code => (typeof PATTERN_LABEL !== 'undefined' && PATTERN_LABEL[code]) || PATTERNS[code] || UI.idText(code || '');
  const OPS = { '>': '보다 높음', '>=': '이상', '<': '보다 낮음', '<=': '이하', '==': '같음', '!=': '다름' };
  W.op = op => OPS[op] || op;
  W.sym = op => ({ '>=': '≥', '<=': '≤', '==': '=', '!=': '≠' })[op] || op;
  // "TS1 > 55 and CE < 70 and slope(TS1) > 0" → "유온 > 55 ℃ 그리고 냉각 효율 < 70 % 그리고 유온 오르는 중"
  // 설비 태그: 센서(TS1 · PS1 …) · 냉각 효율(CE) · 구동 설정값(LoadSP · FanSpeedSP · ValveSP, it/neo4j/v2/instances.cypher 의 Actuator resource)
  const TAG = String.raw`[A-Z]{2,3}\d|CE|LoadSP|FanSpeedSP|ValveSP`;
  W.rule = expr => {
    if (!expr) return '';
    return String(expr)
      .replace(/PLC\.state\s*==\s*'(\w+)'/g, (m, st) => `설비 상태 ${STATES[st] || st}`)
      .replace(/slope\((\w+)\)\s*>\s*0(?:\.0+)?/gi, (m, t) => `${W.fieldName(t.toLowerCase())} 오르는 중`)
      .replace(/slope\((\w+)\)\s*<=\s*0(?:\.0+)?/gi, (m, t) => `${W.fieldName(t.toLowerCase())} 더 오르지 않음`)
      .replace(new RegExp(String.raw`\b(${TAG})\s*(>=|<=|>|<|==)\s*(-?[\d.]+)`, 'g'), (m, t, op, n) => `${W.fieldName(t.toLowerCase())} ${op} ${n}${W.unit(t.toLowerCase()) ? ' ' + W.unit(t.toLowerCase()) : ''}`)
      .replace(new RegExp(String.raw`\b(${TAG})\b`, 'g'), t => W.fieldName(t.toLowerCase()))
      .replace(/\s+and\s+/gi, ' 그리고 ').replace(/\s+or\s+/gi, ' 또는 ').replace(/>=/g, '≥').replace(/<=/g, '≤');
  };
  // 기준 [tag, op, limit] → "유온 < 55 ℃"
  W.criterion = c => Array.isArray(c) && c.length === 3 ? `${W.fieldName(String(c[0]).toLowerCase())} ${W.sym(c[1])} ${W.num(c[2])}${W.unit(String(c[0]).toLowerCase()) ? ' ' + W.unit(String(c[0]).toLowerCase()) : ''}` : '';

  /* ---------------------------------------------------------------- 실행 코드 (승인 뒤 시스템이 하는 일) */
  const CODES = {
    FAN_SET: ['쿨러 팬 속도', '%'], LOAD_SET: ['펌프 부하', '%'], PUMP_SELECT: ['펌프 전환', ''], WO_CREATE: ['작업지시 등록', ''], WO_COMPLETE: ['작업지시 완료', ''],
    PR_CREATE: ['ERP 발주', ''], GR_CONFIRM: ['입고 · 검수', ''], PM_RESET: ['운전시간 계수기 리셋', ''], MAIL: ['메일', ''],
  };
  W.code = c => (CODES[c] || [c])[0];
  // {code, value} 또는 {code, load_pct: 70} → "펌프 부하 70 %"
  W.action = a => {
    if (!a) return '';
    const spec = CODES[a.code];
    const val = a.value != null ? a.value : a.load_pct != null ? a.load_pct : a.fan_pct != null ? a.fan_pct : a.pump != null ? a.pump : null;
    if (!spec) return `${a.name || a.code}${val != null ? ' ' + val : ''}`;
    if (spec[1] && val != null) return `${spec[0]} ${val} ${spec[1]}`;
    return val != null && !/^(sup|SOP)/.test(String(val)) ? `${spec[0]} ${UI.idText(val)}` : spec[0];
  };

  /* ---------------------------------------------------------------- 도구 (무엇을 물었고 무엇을 받았나) */
  const unescapeU = s => String(s).replace(/\\u([0-9a-fA-F]{4})/g, (m, h) => String.fromCharCode(parseInt(h, 16)));
  function parse(x) {
    if (x == null) return null;
    if (typeof x !== 'string') {
      if (Array.isArray(x) && x.length && x.every(y => y && y.type === 'text' && typeof y.text === 'string')) return parse(x.map(y => y.text).join('\n'));
      return x;
    }
    const t = x.trim();
    if (/^[[{]/.test(t)) { try { return JSON.parse(t); } catch (_) { return t; } }
    return t;
  }
  const doc = o => (o && typeof o === 'object' && !Array.isArray(o) && 'document' in o) ? o.document : o;
  const nm = id => W.idName(id);
  const list = (arr, n = 3) => arr.filter(Boolean).slice(0, n).join(', ') + (arr.filter(Boolean).length > n ? ` 외 ${arr.filter(Boolean).length - n}` : '');
  const factsLine = (o, n = 4) => Object.entries(o || {}).filter(([k, v]) => W.known(k) && v != null && typeof v !== 'object').slice(0, n).map(([k, v]) => `${W.fieldName(k)} ${W.value(k, v)}`).join(' · ');
  // 지식 그래프 질의 → 사람 말 (무엇과 연결된 무엇을 찾았나)
  function cypherAsk(q) {
    const s = String(q || '');
    const ids = [...s.matchAll(/id\s*[:=]\s*['"]([^'"]+)['"]/g)].map(m => nm(m[1]));
    const labels = [...s.matchAll(/\(\w*:(\w+)/g)].map(m => m[1]);
    const rels = [...s.matchAll(/\[:?(\w*):?([A-Z_]+)\]/g)].map(m => m[2]);
    const LBL = { Skill: '조치 방법', Role: '승인 역할', Incident: '사건', Cause: '원인', FailureMode: '고장 유형', Symptom: '증상', Part: '부품', Measure: '성과 지표', Rule: '규칙', Manual: '매뉴얼' };
    const REL = { APPROVED_BY: '승인 역할', ADDRESSES: '다루는 원인', RAISED_BY: '경보로 열린 사건', MITIGATED_BY: '완화 조치', REMEDIED_BY: '근본 조치', PREVENTED_BY: '예방 조치', INVOLVES_PART: '쓰는 부품', AFFECTS: '영향' };
    if (ids.length) return `‘${list(ids, 2)}’와 연결된 것`;
    if (/\$ids|\$id/.test(s) && labels.length) return `${list(labels.map(l => LBL[l] || l), 2)}${rels.length ? '의 ' + list(rels.map(r => REL[r] || r), 2) : ''}`;
    if (labels.length) return list(labels.map(l => LBL[l] || l), 3);
    return '그래프 질의';
  }
  function rowsGot(o) {
    const v = parse(o);
    if (Array.isArray(v)) {
      const names = v.map(r => r && typeof r === 'object' ? (r.name || r['s.name'] || r.n || r.id || r.sid || Object.values(r).find(x => typeof x === 'string')) : r).map(x => typeof x === 'string' ? nm(unescapeU(x)) : '');
      return `${v.length}건${names.filter(Boolean).length ? ' · ' + list([...new Set(names)], 3) : ''}`;
    }
    return '';
  }
  const TOOLS = {
    ToolSearch: { name: '쓸 도구 불러오기', minor: true, ask: i => list(String(i.query || '').replace(/^select:/, '').split(',').map(t => W.toolName(t.trim())), 4), got: o => Array.isArray(o) ? `${o.length}개 준비됨` : '' },
    Write: { name: '파일 쓰기', minor: true, ask: i => UI.baseName(i.file_path || ''), got: () => '썼음' },
    Edit: { name: '파일 고치기', minor: true, ask: i => UI.baseName(i.file_path || ''), got: () => '고침' },
    Read: { name: '파일 읽기', minor: true, ask: i => UI.baseName(i.file_path || '') },
    Bash: { name: '명령 실행', minor: true, ask: i => i.description || UI.clean(String(i.command || '')).slice(0, 60) },
    Glob: { name: '파일 찾기', minor: true, ask: i => i.pattern || '' }, Grep: { name: '내용 찾기', minor: true, ask: i => i.pattern || '' },
    Skill: { name: '스킬 읽기', ask: i => i.skill || i.name || '' },
    'mcp__neo4j__read_neo4j_cypher': { name: '지식 그래프 조회', sys: '지식 그래프', ask: i => cypherAsk(i.query), got: rowsGot },
    'mcp__neo4j__get_neo4j_schema': { name: '지식 그래프 구조 보기', sys: '지식 그래프', ask: () => '어떤 종류의 노드 · 관계가 있나' },
    'mcp__hyd-dmn__diagnose': { name: '원인 진단', sys: '판단 엔진', ask: i => `${i.asset || ''} ‘${W.pattern(i.pattern)}’ 경보의 원인`,
      got: o => { const d = doc(parse(o)) || {}; const c = (d.causes || []).find(x => x.id === d.topCause) || (d.causes || [])[0]; return c ? `가장 유력한 원인 ‘${c.name}’ (점수 ${W.num(c.score)})` : ''; } },
    'mcp__hyd-dmn__business_causes': { name: '업무 경보 원인 찾기', sys: '판단 엔진 · 지식 그래프', ask: i => `${i.asset || ''} ‘${W.pattern(i.pattern)}’ 경보의 원인`,
      got: o => { const d = doc(parse(o)) || {}; return [d.cause && `원인 ‘${nm(d.cause)}’`, d.failure_mode && `고장 유형 ‘${nm(d.failure_mode)}’`, d.part && `부품 ${nm(d.part)}`].filter(Boolean).join(' · '); } },
    'mcp__hyd-dmn__timeseries_query': { name: '센서 기록 조회', sys: '센서 기록 DB', ask: i => UI.clean(String(i.sql || i.query || '')).replace(/\s+/g, ' ').slice(0, 80) },
    'mcp__hyd-dmn__timeseries_schema': { name: '센서 기록 구조 보기', sys: '센서 기록 DB' },
    'mcp__hyd-dmn__dmn_rules': { name: '판단 규칙표 보기', sys: '판단 엔진', ask: i => nm(i.decision || ''),
      got: o => { const d = doc(parse(o)); return Array.isArray(d) && d[0] ? `‘${d[0].decisionName || nm(d[0].decision)}’ 규칙 ${(d[0].rules || []).length || d.length}개` : ''; } },
    'mcp__hyd-dmn__evaluate_cards': { name: '대안 평가 (후보 · 규정 · 득실 · 순위)', sys: '판단 엔진', ask: i => [i.asset, nm(i.failure_mode || ''), nm(i.cause || '')].filter(Boolean).join(' · ') },
    'mcp__hyd-dmn__gather_facts': { name: '판단 사실 모으기', sys: '판단 엔진', ask: i => [i.asset, nm(i.failure_mode || '')].filter(Boolean).join(' · '),
      got: o => factsLine((doc(parse(o)) || {}).facts) },
    'mcp__hyd-dmn__precedents': { name: '과거 선택 조회', sys: '판단 엔진', ask: i => nm(i.failure_mode || ''),
      got: o => { const d = doc(parse(o)); return Array.isArray(d) ? `${d.length}건 · ${list(d.map(x => nm(x.skill)), 2)}` : ''; } },
    'mcp__hyd-dmn__submit_decision': { name: '판단 제출', sys: '판단 엔진', ask: i => i.recommended ? `추천 ‘${nm(i.recommended)}’` : (i.asset || ''),
      got: o => { const d = doc(parse(o)) || {}; return d.id ? `판단 ${d.id} 저장${d.recommended ? ` · 추천 ‘${nm(d.recommended)}’` : ''}` : ''; } },
    'mcp__hyd-dmn__forecast_actions': { name: '조치 효과 예측', sys: '판단 엔진' },
    'mcp__hyd-dmn__tradeoffs': { name: '성과 지표 득실 경로', sys: '판단 엔진 · 지식 그래프' },
    'mcp__hyd-dmn__inputs': { name: '판단 입력 보기', sys: '판단 엔진' },
    'mcp__enterprise__mes_orders': { name: '생산 주문 조회', sys: '생산 시스템 (MES)', ask: i => i.asset || '', got: o => factsLine((doc(parse(o)) || {}).facts) },
    'mcp__enterprise__erp_contract': { name: '계약 조회', sys: 'ERP', ask: i => i.asset || '', got: o => factsLine((doc(parse(o)) || {}).facts) },
    'mcp__enterprise__erp_inventory': { name: '완제품 재고 조회', sys: 'ERP', ask: i => i.asset || '', got: o => factsLine((doc(parse(o)) || {}).facts) },
    'mcp__enterprise__query': { name: '업무 DB 질의', sys: '업무 DB', ask: i => UI.clean(String(i.sql || i.query || '')).replace(/\s+/g, ' ').slice(0, 80), got: rowsGot },
    'mcp__hyd-effects__send_mail': { name: '메일 보내기', sys: '메일', ask: i => `${i.to || ''}${i.subject ? ` · 제목 ‘${i.subject}’` : ''}`, got: () => '보냄' },
  };
  // 업무 MCP 는 서버가 셋(전부 · 정비용 · 구매용)이라 도구 이름으로 한 번 더 찾는다
  const BIZ = {
    pm_status: { name: '정비 계수기 · 계획 조회', sys: '정비 시스템 (CMMS)' }, maintenance_windows: { name: '정비 시간 계획 조회', sys: '정비 시스템 (CMMS)' },
    cmms_history: { name: '정비 이력 조회', sys: '정비 시스템 (CMMS)' }, mes_orders: TOOLS['mcp__enterprise__mes_orders'], spare_stock: { name: '예비품 재고 조회', sys: 'ERP' },
    part_quotes: { name: '공급사 견적 조회', sys: '공급망 (SCM)' }, scm_suppliers: { name: '공급사 조회', sys: '공급망 (SCM)' },
    erp_contract: TOOLS['mcp__enterprise__erp_contract'], erp_inventory: TOOLS['mcp__enterprise__erp_inventory'], query: TOOLS['mcp__enterprise__query'],
  };
  function spec(raw) {
    const t = String(raw || '');
    if (TOOLS[t]) return TOOLS[t];
    const m = /^mcp__([^_]+(?:[-_][^_]+)*?)__(.+)$/.exec(t);
    if (m && /^enterprise/.test(m[1]) && BIZ[m[2]]) return Object.assign({ ask: i => i.asset || i.part || '', got: o => factsLine((doc(parse(o)) || {}).facts) || rowsGot((doc(parse(o)))) }, BIZ[m[2]], { sys: BIZ[m[2]].sys || SERVERS[m[1]] });
    if (m) return { name: (UI.terms['tool.' + t]) || m[2].replace(/_/g, ' '), sys: SERVERS[m[1]] || m[1] };
    return { name: UI.terms['tool.' + t] || t };
  }
  W.toolName = raw => spec(raw).name;
  W.toolSystem = raw => spec(raw).sys || '';
  W.minorTool = raw => !!spec(raw).minor;
  // 물은 것 한 줄
  W.ask = (raw, input) => {
    const s = spec(raw), i = parse(input) || {};
    // 사전이 모양을 모르면 아래 일반 요약(원래 값은 화면의 "물은 원문"에 그대로 있다). 사전 결함은 콘솔에 도구 이름과 함께 남긴다
    try { if (s.ask) { const a = s.ask(typeof i === 'object' ? i : {}); if (a) return UI.clean(a); } } catch (err) { console.warn('[hydWords] 물음 요약 실패', raw, err); }
    if (typeof i !== 'object') return UI.clean(String(i)).slice(0, 80);
    return Object.entries(i).filter(([, v]) => v != null && typeof v !== 'object').slice(0, 3).map(([k, v]) => `${W.fieldName(k)} ${UI.clean(UI.idText(String(v))).slice(0, 30)}`).join(' · ');
  };
  // 받은 것 한 줄 (잘림 · 막힘 · 실패는 상태로 따로)
  W.got = (raw, output) => {
    const s = spec(raw);
    try { if (s.got) { const g = s.got(output); if (g) return UI.clean(g); } } catch (err) { console.warn('[hydWords] 받음 요약 실패', raw, err); }
    return window.hydTrace ? hydTrace.outBrief(output, 120) : '';
  };

  /* ---------------------------------------------------------------- id → 이름: 이 처리 건이 아는 이름(판단 · 진단 카드 · 역할) → 사전(names.json) → 종류 + 꼬리
     사전에 아직 없는 id(새로 적재한 시나리오의 조치 · 역할)도 원래 id 를 그대로 드러내지 않는다. 원래 id 는 "원래 이름 보기"에서. */
  const KIND = { cause: '원인', skill: '조치', fm: '고장 유형', sv: '상태 값', msr: '성과 지표', role: '역할', sup: '공급사', part: '부품', rule: '규칙', evd: '증거',
    pattern: '경보 패턴', sys: '시스템', dec: '판단 규칙', sym: '증상', action: '동작', actr: '구동부', sen: '센서', comp: '부품', asset: '설비', dept: '부서', user: '사용자' };
  W.caseNames = {};
  W.idName = id => {
    if (id == null || id === '') return '';
    const k = String(id);
    if (W.caseNames[k]) return W.caseNames[k];
    if (UI.names && UI.names[k]) return UI.names[k];
    if (UI.performers && UI.performers[k]) return UI.performers[k];
    const m = /^([a-z]+):(.+)$/.exec(k);
    if (m && KIND[m[1]]) return `${KIND[m[1]]} ${m[2].replace(/[-_]+/g, ' ')}`;
    return k;
  };
  W.text = t => UI.words(String(t ?? '').replace(UI.ID_RE, m => W.idName(m)));

  /* ---------------------------------------------------------------- 조사: 앞말 끝소리로 고른다 ("발주를" · "씰 마모를" · "WO-1009-E85A를" · "김운전이")
     pair = '을/를' · '이/가' · '은/는' · '과/와' · '으로/로'. 끝 글자가 한글 · 숫자 · 영문이 아니면 "을(를)" 처럼 둘 다 쓴다 */
  const DIGIT_FINAL = { 0: 21, 1: 8, 2: 0, 3: 16, 4: 0, 5: 0, 6: 1, 7: 8, 8: 8, 9: 0 };      // 영 · 일 · 이 · 삼 · 사 · 오 · 육 · 칠 · 팔 · 구 의 받침(0 없음, 8 ㄹ)
  const LETTER_FINAL = { L: 8, M: 16, N: 4, R: 8 };                                          // 엘 · 엠 · 엔 · 알 (나머지 영문 이름은 받침 없음)
  function finalOf(word) {
    const c = String(word ?? '').trim().replace(/[\s’'")\]]+$/, '').slice(-1);
    if (!c) return null;
    const code = c.charCodeAt(0);
    if (code >= 0xAC00 && code <= 0xD7A3) return (code - 0xAC00) % 28;
    if (/\d/.test(c)) return DIGIT_FINAL[c];
    if (/[A-Za-z]/.test(c)) return LETTER_FINAL[c.toUpperCase()] || 0;
    if (c === '%' || c === '℃') return 0;                                                    // 퍼센트 · 도
    return null;
  }
  W.josa = (word, pair) => {
    const [withFinal, without] = pair.split('/'), f = finalOf(word);
    if (f == null) return `${withFinal}(${without})`;
    if (withFinal === '으로') return f && f !== 8 ? '으로' : '로';
    return f ? withFinal : without;
  };
  W.who = id => (UI.performers && UI.performers[id]) || W.idName(id) || '–';

  /* ---------------------------------------------------------------- 원래 이름(id) 보이기 */
  W.id = id => W.showIds && id ? ` <code class="cr-id">${esc(id)}</code>` : '';
  W.setShowIds = on => { W.showIds = !!on; try { localStorage.setItem('hyd:record:ids', on ? '1' : '0'); } catch (_) { /* 이 브라우저에서만 */ } };
  W.parse = parse; W.doc = doc;
  window.hydWords = W;
})();
