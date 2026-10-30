"""업무 시스템 거래의 계약 표(스킬 → 시스템 · 되돌리기 · 이름)와 /api/state 모양. 거래 자체는 업무 DB(ent 스키마)의 함수가 한다
(supabase_backend). 메모리판 업무 시뮬레이터(data.py + SQLite 상태)는 2026-10-30 지웠다 — 학생 PC 는 업무 DB 한 벌이다."""
from __future__ import annotations

SKILLS = {
    "skill:schedule-maintenance-scoped": "sys:cmms",
    "skill:schedule-maintenance": "sys:cmms", "skill:reallocate-production": "sys:mes", "skill:procure-part": "sys:erp",
    "skill:hold-lot": "sys:qms", "skill:release-lot": "sys:qms", "skill:substitute-shipment": "sys:erp", "skill:demand-control": "sys:ems",
}
# Exact inverses the business systems really offer (A072, 2026-10-05). An inverse needs the original reference and only
# applies while the record is still in the state the forward transaction created. Everything else is irreversible:
# the process must get a person's acknowledgement instead of pretending to undo it (product compensation.py principle).
COMPENSATION_SKILLS = {
    "skill:cancel-work-order": "sys:cmms", "skill:cancel-purchase-request": "sys:erp",
    "skill:restore-production": "sys:mes", "skill:release-hold": "sys:qms",
}
INVERSE_OF = {"skill:schedule-maintenance": "skill:cancel-work-order", "skill:procure-part": "skill:cancel-purchase-request",
              "skill:reallocate-production": "skill:restore-production", "skill:hold-lot": "skill:release-hold"}
C2_COMPENSATION_SKILLS = {"skill:cancel-maintenance-scoped": "sys:cmms"}
C2_INVERSE_OF = {"skill:schedule-maintenance-scoped": "skill:cancel-maintenance-scoped"}
ALL_COMPENSATION_SKILLS = {**COMPENSATION_SKILLS, **C2_COMPENSATION_SKILLS}
ALL_INVERSE_OF = {**INVERSE_OF, **C2_INVERSE_OF}
# Korean display names of the business skills (system of record for the portal's names.json — A150). The v2 graph
# (it/neo4j/v2) does not carry these business skills, so this table is their only name source.
SKILL_NAMES = {
    "skill:cancel-maintenance-scoped": "등록한 원문 정비 범위 전체 취소",
    "skill:schedule-maintenance": "정비 작업지시 발행", "skill:reallocate-production": "생산오더 대체 설비 이관",
    "skill:procure-part": "부품 구매요청", "skill:hold-lot": "로트 격리 · 전수검사", "skill:release-lot": "로트 출하 승인",
    "skill:substitute-shipment": "완제품 재고 대체 출하", "skill:demand-control": "수요 제어 지시",
    "skill:cancel-work-order": "정비 작업지시 취소", "skill:cancel-purchase-request": "구매요청 취소",
    "skill:restore-production": "생산오더 원래 설비 복원", "skill:release-hold": "로트 격리 해제",
}
IRREVERSIBLE = {"skill:release-lot": "출하 승인은 출하 절차로 넘어가 되돌릴 수 없다",
                "skill:substitute-shipment": "대체 출하는 물류가 움직여 되돌릴 수 없다",
                "skill:demand-control": "수요 제어 지시는 이미 외부에 전달돼 되돌릴 수 없다"}
# C2 (확정 TODO C): 승인 뒤 실행 부품이 부르는 업무 거래 + 수업 원인 버튼(예비품 출고). ent.exec_skill(migration 20261009000045)과 같은 규칙.
# 되돌리기 계약이 없는 거래다(입고 · 정비 완료는 실물이 움직였고, 일정 · 기록 · 출고는 새 기록으로 바로잡는다) — effect_compensation 이 사유를 보인다.
C2_SKILLS = {"skill:receive-goods": "sys:erp", "skill:complete-maintenance": "sys:cmms", "skill:issue-spare": "sys:erp",
             "skill:reschedule-maintenance": "sys:cmms",
             # 시나리오 B: 운전시간 계수기(운전시간 진행 · 시운전 통과 뒤 리셋), 시나리오 C: 공급사 납기 지연 통보(입고 대기 흐름의 지연 가지)
             "skill:pm-advance": "sys:cmms", "skill:pm-reset": "sys:cmms", "skill:delay-delivery": "sys:scm"}
C2_IRREVERSIBLE = {"skill:receive-goods": "입고 · 검수는 실물이 창고에 들어와 되돌릴 수 없다(반품은 별도 절차)",
                   "skill:reschedule-maintenance": "정비 일정은 기존 오더 상태와 기한을 다시 검토한 새 일정 변경으로 정정한다",
                   "skill:complete-maintenance": "정비는 현장에서 이미 수행되어 되돌릴 수 없다",
                   "skill:issue-spare": "출고된 예비품은 반납 입고로 되돌린다(수업은 재고 초기화)",
                   "skill:pm-advance": "운전시간은 흘러간 시간이라 되돌리지 않는다(수업은 계수기 초기화)",
                   "skill:pm-reset": "정기 정비가 끝나 다음 주기가 시작됐다(정정은 새 기록으로)",
                   "skill:delay-delivery": "공급사가 알린 납기 변경이라 되돌리지 않는다"}
SKILLS.update(C2_SKILLS)
SKILL_NAMES.update({"skill:receive-goods": "입고 · 검수", "skill:complete-maintenance": "정비 완료 · 부품 소모",
                    "skill:schedule-maintenance-scoped": "원문 패키지와 설비 범위 정비 오더 등록",
                    "skill:reschedule-maintenance": "기존 PM 오더 일정 변경",
                    "skill:issue-spare": "예비품 출고",
                    "skill:pm-advance": "운전시간 계수기 진행", "skill:pm-reset": "운전시간 계수기 리셋 · 다음 기한 기록",
                    "skill:delay-delivery": "공급사 납기 지연 통보"})
SKILLS.update(ALL_COMPENSATION_SKILLS)


SNAPSHOT_TABLES = {"cmms": ("work_orders",), "erp": ("purchase_requests", "shipments", "goods_receipts"),
                   "qms": ("lot_dispositions",), "ems": ("ems_actions",)}
_ALIASES = {"work_orders": (("window", "window_label"),), "purchase_requests": (("supplierName", "supplier_name"),),
            "shipments": (("from", "source"),), "ems_actions": (("t", "created_at"),)}


def _view_row(table: str, row: dict) -> dict:
    out = dict(row)
    for a, b in _ALIASES.get(table, ()):
        value = out.get(a) if out.get(a) is not None else out.get(b)
        out[a] = out[b] = value
    return out


def snapshot_view(mes_orders: list[dict], tables: dict[str, list[dict]]) -> dict:
    """tables = 업무 DB 표 이름 → 행(최근 것부터) → /api/state 모양."""
    out = {"mes": {"orders": mes_orders}}
    for system, names in SNAPSHOT_TABLES.items():
        out[system] = {name: [_view_row(name, r) for r in tables.get(name, [])] for name in names}
    return out
