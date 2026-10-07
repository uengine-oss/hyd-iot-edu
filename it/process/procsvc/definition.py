"""Mini-BPMN process definition (L9). The portal draws STEPS as lanes; machine.py moves an Incident through them.

    GUIDE_RECEIVED → AWAITING_APPROVAL → CMD_ISSUED → AWAITING_ACK → ACKED → RE_OBSERVING → RESOLVED → WORK_ORDER_CREATED → CLOSED
    failure paths: ESCALATED (ACK_TIMEOUT / PLC REJECTED / MITIGATION_FAILED), REJECTED_BY_OPERATOR, RESOLVED_WITHOUT_ACTION
"""
# (state id, label, BPMN element type)
STEPS = [
    ("GUIDE_RECEIVED", "가이드 카드 수신", "startEvent"),
    ("AWAITING_APPROVAL", "운전원 승인·수정·거부", "userTask"),
    ("CMD_ISSUED", "action.cmd 발행 (만료 +120 s)", "serviceTask"),
    ("AWAITING_ACK", "PLC ACK 대기 (30 s)", "receiveTask"),
    ("ACKED", "ACK DONE", "intermediateEvent"),
    ("RE_OBSERVING", "15분 재관측 (시간 배율 적용)", "timerEvent"),
    ("RESOLVED", "완화 판정 (CLEAR ∧ 패턴별 회복 기준)", "exclusiveGateway"),
    ("WORK_ORDER_CREATED", "작업지시 생성", "serviceTask"),
    ("CLOSED", "종결", "endEvent"),
]
FAILURE_STATES = {
    "ESCALATED": "에스컬레이션 (ACK 없음 / PLC 거부 / 완화 실패)",
    "REJECTED_BY_OPERATOR": "운전원 거부",
    "RESOLVED_WITHOUT_ACTION": "조치 전 자연 회복 (CLEAR)",
}
TERMINAL = {"CLOSED", "ESCALATED", "REJECTED_BY_OPERATOR", "RESOLVED_WITHOUT_ACTION"}

ACK_TIMEOUT_S = 30           # wall clock (v3 7.3)
CMD_EXPIRY_S = 120           # wall clock (v3 7.2)
REOBSERVE_SIM_S = 15 * 60    # simulated seconds; divided by TIME_SCALE
REOBSERVE_TS1_MAX = 55.0
REOBSERVE_MAX_EXTENSIONS = 3   # extra third-windows while the value is already inside the limit but the detector CLEAR (hysteresis held 60 s)
                               # has not landed yet. A072 run 4 (1x): one extension ended 3 s before CLEAR arrived → MITIGATION_FAILED on a recovered plant.
# Recovery criterion per alert pattern: (tag re-read from TimescaleDB, operator, limit). The limits are the ontology's:
# TS1 55 ℃ (reset line), PS1 165 bar (sv:ps1 -> msr:throughput "PS1 < 165 bar에서 사이클 지연"), VS1 1.2 mm/s (pattern raise line).
RECOVERY = {"COOLER_DEGRADATION": ("TS1", "<", REOBSERVE_TS1_MAX),
            "PUMP_LEAKAGE": ("PS1", ">=", 165.0), "FAN_VIBRATION": ("VS1", "<", 1.2)}


def recovery_for(pattern: str | None) -> tuple[str, str, float] | None:
    return RECOVERY.get(pattern) if isinstance(pattern,str) else None


def recovered(pattern: str | None, value: float | None) -> bool:
    if value is None or recovery_for(pattern) is None:
        return False
    _, op, limit = recovery_for(pattern)
    return value < limit if op == "<" else value >= limit


def as_json() -> dict:
    return {"steps": [{"id": s, "label": l, "type": t} for s, l, t in STEPS],
            "failure": [{"id": k, "label": v} for k, v in FAILURE_STATES.items()],
            "terminal": sorted(TERMINAL),
            "timers": {"ack_timeout_s": ACK_TIMEOUT_S, "cmd_expiry_s": CMD_EXPIRY_S,
                       "reobserve_sim_s": REOBSERVE_SIM_S, "reobserve_ts1_max": REOBSERVE_TS1_MAX,
                       "reobserve_max_extensions": REOBSERVE_MAX_EXTENSIONS,
                       "recovery": {p: {"tag": t, "op": o, "limit": l} for p, (t, o, l) in RECOVERY.items()}}}
