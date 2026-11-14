"""업무 시스템 거래의 이름 표와 /api/state 모양. 거래 자체 · 어느 거래가 되돌릴 수 있는지는 업무 DB(ent 스키마)의 함수가 정한다
(ent.exec_skill · ent.exec_compensation, 마이그레이션 20261030000069). 메모리판 업무 시뮬레이터는 2026-10-30 지웠다 — 학생 PC 는 업무 DB 한 벌이다."""
from __future__ import annotations

#: 업무 거래의 한국어 이름 — 포털 이름 사전(names.json)의 재료(workspace/개발/scripts/portal_names.py). v2 그래프에는 업무 거래 스킬이 없어
#: 이 표가 유일한 이름 출처다. 업무 DB 함수가 받는 거래와 같은 목록이어야 한다(test_entsim_state 가 실제 DB 로 대조한다).
SKILL_NAMES = {
    "skill:schedule-maintenance": "정비 요청 발행",
    "skill:schedule-maintenance-scoped": "정비 묶음 · 설비 범위별 정비 요청 등록",
    "skill:reschedule-maintenance": "기존 정비 요청 일정 변경",
    "skill:complete-maintenance": "정비 완료 · 부품 소모",
    "skill:pm-reset": "운전시간 계수기 리셋 · 다음 기한 기록",
    "skill:procure-part": "부품 구매요청",
    "skill:receive-goods": "입고 · 검수",
    "skill:delay-delivery": "공급사 납기 지연 통보",
    "skill:cancel-work-order": "정비 요청 취소",
    "skill:cancel-purchase-request": "구매요청 취소",
    "skill:cancel-maintenance-scoped": "등록한 원문 정비 범위 전체 취소",
}


SNAPSHOT_TABLES = {"cmms": ("work_orders",), "erp": ("purchase_requests", "goods_receipts")}
_ALIASES = {"work_orders": (("window", "window_label"),), "purchase_requests": (("supplierName", "supplier_name"),)}


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
