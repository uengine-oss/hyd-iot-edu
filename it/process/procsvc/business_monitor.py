"""업무 경보 계약 — 업무 DB 의 값이 기준을 넘었다는 경보(시나리오 B · C)의 모양. 감지기(det)는 센서만 읽으므로 업무 조건은 여기서 정한다.
  * SPARE_BELOW_MIN (시나리오 C, ERP): 예비품 가용 재고(현재고 − 정비 예약 + 입고 예정) < 재주문점
  * PM_DUE          (시나리오 B, CMMS): 마지막 정기 정비 뒤 운전시간 ≥ 주기 − 사전 알림(2,000 − 50 h)

수업은 포털 [정기 점검] · [재고 보충] 버튼(scenario_buttons)이 지금 업무 행 하나를 읽어 이 계약의 경보를 만든다(센서 경보 · 사람 입력 경보(B7)와
같은 모양 `alertId · asset · pattern · severity · state=RAISE · t · evidence`, 출처 `source: "erp" | "cmms"`). 같은 원천 접수 경로
(main._admit_alert → source_inbox → 경보 정책 → start_definition → Incident)로 가고, 어느 흐름이 여는지는 경보 정책(flow_deploy.route_definition)이
정한다 — 이 패턴을 받는 배포 흐름이 없으면 기준 흐름의 unsupported → 사람 검토(alert_triage).

업무 값을 스스로 읽어 경보를 여는 감시 루프는 없다(2026-10-30 건강검진 P4-27에서 지움 — 수업 시작 상태가 곧 도래 · 이탈이라 켜면 누르기 전에
처리 건이 열리고, 켜는 길도 쓰는 곳도 없었다). 규칙의 근거 값(evidence)은 버튼 경보의 근거가 된다.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

from hydcommon.maintenance_policy import PM_PATTERN
from hydcommon.skill_scope import PURCHASE_PATTERN

ERP_SOURCE = "erp"
CMMS_SOURCE = "cmms"
SOURCES = (ERP_SOURCE, CMMS_SOURCE)

# 업무 경보 패턴 계약. policy = 흐름 정의 alertPolicy.patterns 의 회복 기준(alert_policy.validate 계약). 업무 경보에는 센서 재관측이 없다 —
# 태그는 이탈 표시(1 = 이탈)이고, 처리 건은 효과 확인(입고)으로 닫힌다. 명령 · 재관측을 넣은 흐름이면 해제 없음 → 상급자 확인.
PATTERNS: dict[str, dict] = {
    PURCHASE_PATTERN: {
        "name": "예비품 재고 기준 이탈 (ERP 재고 감시)",
        "severity": "warning",
        "read": "spare_stock", "source": ERP_SOURCE,
        "policy": {"tag": "ERP_SPARE_BELOW_MIN", "op": "<", "limit": 1.0, "requireClear": True},
    },
    PM_PATTERN: {
        "name": "정기 정비 도래 (CMMS 운전시간 계수기)",
        "severity": "info",
        "read": "pm_status", "source": CMMS_SOURCE,
        "policy": {"tag": "CMMS_PM_DUE", "op": "<", "limit": 1.0, "requireClear": True},
    },
}


def policy_patterns() -> dict[str, dict]:
    """흐름 가져오기의 경보 시작 패턴에 보탤 {패턴: 회복 기준}."""
    return {code: deepcopy(p["policy"]) for code, p in PATTERNS.items()}


def is_business_alert(alert) -> bool:
    return (isinstance(alert, dict) and alert.get("pattern") in PATTERNS
            and alert.get("source") == PATTERNS[alert["pattern"]].get("source", ERP_SOURCE))


@dataclass(frozen=True)
class MonitorRule:
    pattern: str
    read: str                                         # enterprise_read 이름 (records 목록을 돌려준다)
    evidence: Callable[[dict], dict]                  # 업무 행 하나 → 경보 근거 값


def _spare_evidence(row: dict) -> dict:
    keys = ("part_no", "name", "on_hand", "reserved", "available", "on_order", "spare_gap", "reorder_point", "target_stock", "need_qty",
            "below_since")
    return {k: row.get(k) for k in keys if k in row} | {"spare_below_min": True}


#: 정기 정비 경보의 근거 = 판단에 쓰는 CMMS 계수기 · 계획 값(ent.pm_status 한 행). 에이전트는 같은 값을 보전용 업무 MCP 로 다시 읽는다.
PM_EVIDENCE = ("plan_id", "package", "cycle", "pm_since_h", "pm_interval_h", "pm_tolerance_pct", "pm_notice_h", "pm_due_in_h", "pm_limit_in_h",
               "pm_window_open", "night_window_id", "night_window_at", "night_window_in_h", "night_within_limit", "weekend_within_limit",
               "monthly_within_limit", "bundle_peer", "bundle_peer_since_h", "bundle_crew_ok", "kit_part_no", "kit_qty", "spare_gap_after_pm",
               "spare_gap_after_bundle", "due_since",
               # 온톨로지 B 판단 입력 이름(scenario_structure.cypher) 그대로
               "hours_since_pm", "hours_at_next_window", "hours_at_following_window", "pm_crew_available", "spare_available")


def _pm_evidence(row: dict) -> dict:
    return {k: row.get(k) for k in PM_EVIDENCE if k in row} | {"pm_due": True}


RULES: tuple[MonitorRule, ...] = (
    MonitorRule(pattern=PURCHASE_PATTERN, read="spare_stock", evidence=_spare_evidence),
    MonitorRule(pattern=PM_PATTERN, read="pm_status", evidence=_pm_evidence),
)
