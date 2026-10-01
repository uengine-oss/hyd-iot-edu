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
  },
  status(value) {
    return this.states[value] || value || "–";
  },
  dateTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value || '–' : date.toLocaleString('ko-KR');
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
