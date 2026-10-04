/* Shared presentation helpers. API identifiers stay unchanged. */
const UI = {
  states: {
    PENDING_APPROVAL: "승인 대기",
    AWAITING_APPROVAL: "승인 대기",
    GUIDE_RECEIVED: "분석 완료",
    CMD_ISSUED: "명령 전송",
    AWAITING_ACK: "설비 응답 대기",
    ACKED: "설비 응답 완료",
    RE_OBSERVING: "효과 확인 중",
    RESOLVED: "이상 완화",
    WORK_ORDER_CREATED: "정비 요청 완료",
    CLOSED: "종결",
    ESCALATED: "추가 확인 필요",
    REJECTED_BY_OPERATOR: "조치 거부",
    RESOLVED_WITHOUT_ACTION: "자연 회복",
    APPROVED: "승인됨",
    EXECUTED: "실행 완료",
    PARTIAL: "일부 실행",
    REJECTED: "반려",
    FAILED: "실패",
    SUBMITTED: "검토 요청",
    DONE: "완료",
    RUNNING: "실행 중",
    RUN: "운전 중",
    TRIP: "보호 정지",
    STOP: "계획 정지",
    RAISED: "경보 발생",
    RAISE: "경보 발생",
    CLEAR: "경보 해제",
    CLEARING: "회복 확인 중",
    CANDIDATE: "이상 징후",
    IDLE: "감시 중",
    VIA_HITL: "설비 승인 필요",
    REMOTE_AUTO: "원격 자동",
    REMOTE_MANUAL: "원격 수동",
    LOCAL: "현장 제어",
    WITHHELD: "데이터 확인 필요",
    REJECTED_BY_GUARDRAIL: "제약 검증에서 중단",
    NO_FEASIBLE_OPTION: "실행 가능한 대안 없음",
    NOT_APPLICABLE: "적용 조건에 해당하지 않음",
    EVALUATED: "검토 완료",
    // process instances · todolist (ProcessGPT 상태값)
    NEW: "생성",
    TODO: "할 일",
    IN_PROGRESS: "진행 중",
    PENDING: "대기",
    HUMAN_ASKED: '사람 확인 대기', FB_REQUESTED: '피드백 반영', STARTED: '워커 실행 중', FAILED: '실패', CANCELLED: "취소",
    COMPLETED: "완료",
  },
  status(value) {
    return this.states[value] || value || "–";
  },
  dateTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value || '–' : date.toLocaleString('ko-KR');
  },
  time(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value || '–' : date.toLocaleTimeString('ko-KR', {hour12:false});
  },
  eventNames: {
    task_deferred:'진단·평가 보류', task_reassessment_requested:'새 평가 요청',
    GUIDE_SUBMITTED:'조치 가이드 제출', GUIDE_APPROVED:'조치 가이드 승인',
    DECISION_SUBMITTED:'업무 판단 제출', DECISION_APPROVED:'업무 판단 승인',
    DECISION_DENIED:'승인 권한 확인 실패', DECISION_REJECTED:'업무 판단 반려',
    CMD_ISSUED:'설비 명령 전송', ACK_RECEIVED:'설비 응답 수신',
    INCIDENT_CREATED:'인시던트 생성', INCIDENT_CLOSED:'인시던트 종결',
    STATE_CHANGED:'진행 상태 변경', REOBSERVE_DONE:'조치 효과 확인 완료',
    ACK_DONE:'설비 명령 완료', ALERT_CLEARED:'경보 해제', CMD_PUBLISHED:'설비 명령 발행',
    MANUAL_INGESTED:'매뉴얼 등록', REOBSERVATION:'조치 후 재관측', SKILL_EDITED:'스킬 수정',
    SKILL_EXECUTED:'스킬 실행',
  },
  eventRecord({time, name, actor='', detail='', raw}) {
    return `<article class="event-record"><header><time title="${esc(this.dateTime(time))}">${esc(this.time(time))}</time><strong>${esc(this.eventNames[name] || this.status(name))}</strong><span>${esc(actor)}</span></header>${detail ? `<p>${esc(detail)}</p>` : ''}${raw ? `<details><summary>원본 기록</summary><pre>${esc(JSON.stringify(raw,null,2))}</pre></details>` : ''}</article>`;
  },
  condition(value) {
    return {'cmms_cleans_60d >= 3':'최근 60일 동안 쿨러 세척 3회 이상','qms_hot_min > 0':'과열 구간에 생산된 로트가 있음'}[value] || value;
  },
  // Labels and units follow enterprise-sim/entsim/data.py. Unknown fields retain
  // their exact key/value; source records are always available beside the facts.
  facts: {
    due_in_h:['납기까지','시간'], remaining_qty:['생산 잔량','개'], rate_per_h:['생산 속도','개/시간'],
    hour_value:['생산 시간당 가치','만원/시간'], alt_asset:['대체 설비',''], alt_free_h:['대체 설비 가용 시간','시간'],
    alt_rate_per_h:['대체 설비 생산 속도','개/시간'], changeover_h:['설비 전환 시간','시간'], order_id:['생산오더',''],
    sales_order:['판매 주문',''], customer_tier:['고객 구분',''], penalty_per_h:['시간당 지체상금','만원/시간'],
    failure_cost:['돌발 고장 비용','만원'], claim_cost:['품질 클레임 비용','만원'],
    fg_item:['완제품 품목',''], fg_stock:['완제품 재고','개'], ship_in_h:['출하까지','시간'],
    cleans_60d:['최근 60일 세척 횟수','회'], last_clean_days:['마지막 세척 후','일'], clean_h:['세척 소요','시간'],
    clean_cost:['세척 비용','만원'], night_in_h:['야간 정비창까지','시간'], oil_risk_per_h:['시간당 작동유 위험 비용','만원/시간'], mtbf_h:['평균 고장 간격','시간'],
    hot_min:['과열 지속 시간','분'], auto_lot:['자동차 고객 로트',''], auto_qty:['자동차 고객 수량','개'],
    gen_lot:['일반 고객 로트',''], gen_qty:['일반 고객 수량','개'], inspect_h:['검사 소요','시간'],
    inspect_cost:['전수검사 비용','만원'], sample_cost:['표본검사 비용','만원'],
    gen_defect_p:['일반 고객 불량 확률','확률'], auto_defect_p:['자동차 고객 불량 확률','확률'],
    gen_claim:['일반 고객 클레임 손실','만원'], auto_claim:['자동차 고객 클레임 손실','만원'],
    std_price:['기준 구매 단가','만원'], contract_kw:['계약 전력','kW'], demand_kw:['현재 전력 수요','kW'],
    fan_boost_kw:['팬 증속 추가 전력','kW'], basic_rate:['기본 요금 단가','만원/kW'], peak_h:['피크 시간','시간'],
    peak_window:['피크 시간대',''], outdoor_c:['외기 온도','°C'], energy_rate:['전력량 요금 단가','만원/kWh'],
  },
  factList(facts) {
    return '<dl class="fact-list">' + Object.entries(facts || {}).map(([key,value]) => {
      const short = key.replace(/^(mes|erp|cmms|qms|scm|ems)_/, '');
      let spec = this.facts[short];
      const supplier = short.match(/^([abc])_(price|fail|lead_d|avl)$/);
      if (supplier) { const field={price:['구매 단가','만원'],fail:['고장 확률','확률'],lead_d:['납기','일'],avl:['승인 공급사','여부']}[supplier[2]]; spec=[supplier[1].toUpperCase()+' 공급사 '+field[0],field[1]]; }
      const [label,unit] = spec || [key,''];
      const shown = unit==='확률' ? Number(value)*100+' %' : unit==='여부' ? (value ? '예' : '아니요') : `${typeof value==='number' ? value.toLocaleString('ko-KR') : value}${unit ? ' '+unit : ''}`;
      return `<div title="${esc(key)}"><dt>${esc(label)}</dt><dd>${esc(shown)}</dd></div>`;
    }).join('')+'</dl>';
  },
  // Human-readable labels belong to the UI; API step names and raw records stay intact.
  steps: {
    freshness: ['데이터 상태 확인', '최근 데이터가 들어오는지, 분석에 사용할 수 있는지 확인합니다.'],
    t1_causes: ['고장 원인 조회', '경보와 증상에 연결된 고장 원인 후보를 찾습니다.'],
    evidence: ['관측값으로 근거 확인', '센서 이력에서 각 원인을 뒷받침하는 조건을 확인합니다.'],
    rank: ['원인 후보 비교', '사전확률과 관측 근거를 바탕으로 원인 후보의 순위를 정합니다.'],
    t2_actions: ['조치 방법과 정비 절차 조회', '원인에 연결된 조치, 허용 범위, 정비 절차와 매뉴얼을 찾습니다.'],
    card: ['조치 가이드 작성', '원인과 권장 조치를 근거와 함께 정리합니다.'],
    guardrail: ['제약과 근거 검증', '권고가 정해진 제약을 지키고 근거를 갖추었는지 검사합니다.'],
    submit: ['승인 절차로 전달', '판단 결과를 승인 담당자가 검토할 수 있도록 전달합니다.'],
    enterprise: ['관련 업무 판단 연결', '설비의 문제와 연결된 생산·정비·품질 등의 판단을 실행합니다.'],
    ontology_context: ['판단에 필요한 지식 조회', '상황에 연결된 대안, 스킬, 성과 지표와 규정을 찾습니다.'],
    precedents: ['이전 판단 사례 확인', '같은 상황에서 사람이 승인한 대안을 살펴봅니다.'],
    info_routing: ['정보를 가진 시스템 찾기', '필요한 정보를 어느 기업 시스템에서 조회할지 확인합니다.'],
    fetch: ['기업 시스템 정보 조회', '생산·정비·품질 등 관련 시스템에서 현재 정보를 읽습니다.'],
    impacts: ['대안별 영향 계산', '각 대안이 성과 지표에 미치는 금액 영향을 계산합니다.'],
    policies: ['규정 위반 확인', '제외해야 할 대안과 불이익을 반영할 대안을 구분합니다.'],
    perspectives: ['부서와 전사 관점 비교', '부서별 목표와 회사 전체 목표에서 유리한 대안을 비교합니다.'],
    recommend: ['권고안 정리', '권고안, 선택 근거와 필요한 승인 역할을 정리합니다.'],
    error: ['처리 실패', '실패 원인은 아래 처리 기록에서 확인할 수 있습니다.'],
  },
  revealDetail(detail) {
    const split = detail.closest(".split");
    if (
      split &&
      getComputedStyle(split).gridTemplateColumns.split(" ").length === 1
    ) {
      detail.scrollIntoView({ block: "start" });
    }
  },
  icon(name) {
    const paths = {
      home: "M3 10 12 3l9 7v11h-6v-7H9v7H3Z",
      map: "M4 4h6v6H4Zm10 10h6v6h-6ZM7 10v7h7M10 7h7v7",
      play: "m8 5 11 7-11 7Z",
      alert: "m12 3 10 18H2Zm0 6v5m0 3v1",
      chart: "M4 3v17h17M7 15l4-5 4 2 5-7",
      nodes:
        "M9 6h6M7 8v8m10-8v8M9 18h6M4 3h5v5H4Zm11 0h5v5h-5ZM4 16h5v5H4Zm11 0h5v5h-5Z",
      skills: "M5 3h14v18H5Zm4 5h6m-6 4h6m-6 4h4",
      decision: "M5 4h14v16H5Zm3 4 1 1 2-2m2 1h3M8 13l1 1 2-2m2 1h3",
      process: "M3 4h6v6H3Zm12 10h6v6h-6ZM9 7h9v7M6 10v7h9",
    };
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.home}"/></svg>`;
  },
};
