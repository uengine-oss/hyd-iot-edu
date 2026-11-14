"""사건(Incident)의 상태 표 · 시한 · 에스컬레이션 사유 문장 — machine.py 가 사건을 이 상태들로 옮긴다.

    GUIDE_RECEIVED → AWAITING_APPROVAL → CMD_ISSUED → AWAITING_ACK → ACKED → RE_OBSERVING → RESOLVED → WORK_ORDER_CREATED → CLOSED
    끝(실패 · 다른 결말): ESCALATED(책임자 확인 — 사유 코드 Incident.reason) · REJECTED_BY_OPERATOR · RESOLVED_WITHOUT_ACTION

회복 기준(태그 · 비교 · 한계)은 처리 건 정의의 alertPolicy 하나가 갖는다(코드에 사본을 두지 않는다 — P1-20). 상태 · 사유의 사람 이름은
이 파일 하나가 갖고 다른 모듈은 state_label · escalation_cause 로 읽는다.
"""
from hydcommon.words import particle
# (state id, 사람 이름, BPMN element type)
STEPS = [
    ("GUIDE_RECEIVED", "판단 카드 받음", "startEvent"),
    ("AWAITING_APPROVAL", "담당자 승인 대기", "userTask"),
    ("CMD_ISSUED", "설비 명령 보냄(유효 120초)", "serviceTask"),
    ("AWAITING_ACK", "설비 응답 기다림(30초)", "receiveTask"),
    ("ACKED", "설비 응답 받음", "intermediateEvent"),
    ("RE_OBSERVING", "효과 확인 중(설비 시간 15분)", "timerEvent"),
    ("RESOLVED", "회복 판정(경보 해제 · 회복 기준 충족)", "exclusiveGateway"),
    ("WORK_ORDER_CREATED", "정비 요청 등록", "serviceTask"),
    ("CLOSED", "종결", "endEvent"),
]
FAILURE_STATES = {
    "ESCALATED": "책임자 확인",
    "REJECTED_BY_OPERATOR": "담당자 반려",
    "RESOLVED_WITHOUT_ACTION": "조치 전 자연 회복(경보 해제)",
}
TERMINAL = {"CLOSED", "ESCALATED", "REJECTED_BY_OPERATOR", "RESOLVED_WITHOUT_ACTION"}

ACK_TIMEOUT_S = 30           # wall clock (v3 7.3) — 명령 단계 행의 마감(due_date)으로 저장해 폴링이 판정한다
CMD_EXPIRY_S = 120           # wall clock (v3 7.2)
REOBSERVE_SIM_S = 15 * 60    # simulated seconds; divided by TIME_SCALE — 재관측 단계 행의 마감으로 저장한다(service_parts._reobserve)
REOBSERVE_MAX_EXTENSIONS = 3   # extra third-windows while the value is already inside the limit but the detector CLEAR (hysteresis held 60 s)
                               # has not landed yet. A072 run 4 (1x): one extension ended 3 s before CLEAR arrived → MITIGATION_FAILED on a recovered plant.


def state_label(state: str | None) -> str:
    """사건 상태 → 사람 이름(처리 기록 · 거절 사유 · 작업지시 문장이 같은 이름을 쓴다). 표에 없는 상태는 사건 기록이 어긋난 것 — 실패한다."""
    names = dict((s, label) for s, label, _ in STEPS) | FAILURE_STATES
    if state not in names:
        raise ValueError(f"사건 상태 {state!r}{particle(state, '은')} 사건 상태 표(definition.STEPS · FAILURE_STATES)에 없습니다")
    return names[state]


def as_json() -> dict:
    return {"steps": [{"id": s, "label": l, "type": t} for s, l, t in STEPS],
            "failure": [{"id": k, "label": v} for k, v in FAILURE_STATES.items()],
            "terminal": sorted(TERMINAL),
            "timers": {"ack_timeout_s": ACK_TIMEOUT_S, "cmd_expiry_s": CMD_EXPIRY_S,
                       "reobserve_sim_s": REOBSERVE_SIM_S, "reobserve_max_extensions": REOBSERVE_MAX_EXTENSIONS}}


#: 처리 건이 끝나 사건을 책임자 확인으로 닫은 사유 코드의 머리(machine.on_process_ended) — 뒤에 처리 건이 끝난 곳의 이름이 붙는다
PROCESS_ENDED = "PROCESS_ENDED"
#: 명령 관문(cmd-gateway)이 명령을 설비로 넘기지 않고 거절했다(machine.on_status 의 rejectedBy) — 뒤에 관문의 사유가 붙는다
GATEWAY_REJECTED = "GATEWAY_REJECTED"
#: 승인 전에 경보가 풀렸는데 같은 설비가 보호 정지(PLC TRIP) 중이었다 — 회복이 아니라 설비가 멈춰 값이 내려간 것(machine.on_alert) — 뒤에 보호 정지 사유
TRIPPED_BEFORE_ACTION = "TRIPPED_BEFORE_ACTION"
#: 결과 보고(svc:report)가 미달 · 지연으로 사건을 닫았다(machine.on_result_report) — 결과 보고의 틀이 그 문장이다
RESULT_REPORT = "RESULT_REPORT"


def escalation_cause(reason: str | None) -> tuple[str, bool] | None:
    """ESCALATED 사건의 사유(Incident.reason) → (사람이 읽는 실제 사유, 재관측으로 판정했는가).
    재관측 기준 미달(MITIGATION_FAILED)과 결과 보고가 직접 올린 에스컬레이션(RESULT_REPORT)은 None — 흐름의 보고 틀이 맞다.
    명령 거절 · ACK 시간 초과 · 재시작 같은 다른 사유는 재관측 미달이 아니므로 결과 보고가 이 문장을 싣는다. 모르는 사유 코드는 사건 기록이
    어긋난 것이라 좌표를 붙여 실패한다(코드를 학생 문장에 그대로 싣지 않는다 — P1-26)."""
    if reason in (None, "MITIGATION_FAILED", RESULT_REPORT):     # None: 결과 보고가 사유 없이 닫던 고침 전 기록(P1-31) — 같은 뜻
        return None
    if not isinstance(reason, str) or not reason:
        raise ValueError(f"에스컬레이션 사유 {reason!r}{particle(reason, '을')} 읽을 수 없습니다")
    code, _, detail = reason.partition(":")
    detail = detail.strip()
    if code == "PLC REJECTED":
        return (f"설비 명령이 PLC 에서 거절됐습니다(사유 {detail or '없음'}) — 명령이 실행되지 않아 효과 확인을 하지 않았습니다. "
                "운전 모드 · 인터록을 확인하세요", False)
    if code == GATEWAY_REJECTED:
        return (f"명령 관문이 설비 명령을 넘기지 않고 거절했습니다 — {detail or '까닭 없음'}. 명령은 설비에 닿지 않아 효과 확인을 하지 않았습니다", False)
    if code == "ACK_TIMEOUT":
        return (f"설비 명령의 응답(ACK)이 {ACK_TIMEOUT_S}초 안에 오지 않았습니다 — 명령이 실행됐는지 알 수 없어 효과 확인을 하지 않았습니다. "
                "PLC · 명령 게이트웨이 연결을 확인하세요", False)
    if code == "CMD_SEND_FAILED":
        return ("설비 명령을 명령 통로(Kafka)에 싣지 못했습니다 — 명령이 설비에 닿았는지 알 수 없어 다시 보내지 않고 효과 확인을 하지 않았습니다. "
                "명령 통로 연결을 확인하고 설비 상태를 사람이 확인하세요", False)
    if code == "PROCESS_RESTART_REVIEW":
        return ("설비 명령의 응답(ACK)을 기다리는 중에 process 가 다시 시작돼 명령이 실행됐는지 알 수 없습니다 — 효과 확인을 하지 않았습니다. "
                "설비 상태를 사람이 확인하세요", False)
    if code == "UNSUPPORTED_RECOVERY_CRITERION":
        return ("이 경보 패턴에는 회복 기준이 없어 효과 확인으로 판정하지 못했습니다", True)
    if code == "UNSUPPORTED_ALERT_PATTERN":
        return ("이 경보 패턴에는 회복 기준이 없어 처리 흐름 대신 현장 검토로 넘겼습니다", False)
    if code == TRIPPED_BEFORE_ACTION:
        return (f"승인 전에 경보가 풀렸지만 설비가 보호 정지(사유 {detail or '없음'}) 중이었습니다 — 회복이 아니라 설비가 멈춰 값이 내려간 것이라 "
                "조치 없이 끝내지 않고 책임자 확인으로 넘겼습니다. 보호 정지 원인과 쿨러 · 설비 상태를 사람이 확인하세요", False)
    if code == PROCESS_ENDED:
        return (f"처리 건이 「{detail or '끝'}」{particle(detail or '끝', '으로')} 끝나 사건을 책임자 확인으로 닫았습니다 — 조치가 끝까지 가지 않았으니 설비 상태를 사람이 "
                "확인하세요", False)
    raise ValueError(f"에스컬레이션 사유 {reason!r}의 문장이 없습니다(definition.escalation_cause)")
