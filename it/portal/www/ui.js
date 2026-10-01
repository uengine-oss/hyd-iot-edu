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
  },
  status(value) {
    return this.states[value] || value || "–";
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
