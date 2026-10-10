"""C2 (확정 TODO C) 업무 표 기준값 감시 → 경보 — 업무 DB 의 값이 기준을 넘으면 처리 건을 스스로 연다. 감지기(det)는 센서만 읽으므로
업무 DB 의 조건은 여기서 본다. 규칙 둘:
  * SPARE_BELOW_MIN (시나리오 C, ERP): 예비품 가용 재고(현재고 − 정비 예약 + 입고 예정) < 재주문점
  * PM_DUE          (시나리오 B, CMMS): 마지막 정기 정비 뒤 운전시간 ≥ 주기 − 사전 알림(2,000 − 50 h)

  C3 부터 수업은 포털 [정기 정비] · [예비품 구매] 버튼(scenario_buttons)이 같은 규칙의 근거 값으로 처리 건을 연다. 이 감시는 '업무 데이터가
  기준을 넘으면 스스로 연다'는 자동 시작 방식으로 남아 있고 기본은 꺼짐(BUSINESS_MONITOR=0) — 수업 시작 상태가 곧 도래 · 이탈이라 켜 두면
  누르기 전에 처리 건이 열린다. 경보 계약(build_alert · PATTERNS · RULES의 evidence)은 버튼과 같이 쓴다.

  감시 규칙 하나 = (읽을 업무 데이터 · 조건 · 회차 키 · 경보 모양). 규칙이 조건을 만족하면 센서 경보 · 사람 입력 경보(B7)와 **같은 계약**
  (`alertId · asset · pattern · severity · state=RAISE · t · evidence`, 출처 `source: "erp" | "cmms"`)의 경보를 만들어 같은 원천 접수 경로
  (main._admit_human_alert → source_inbox → 경보 정책 → start_definition → Incident)로 보낸다. 어느 흐름이 여는지는 경보 정책
  (B4 flow_deploy.route_definition)이 정한다 — 이 패턴을 받는 배포 흐름이 없으면 기준 흐름의 unsupported → 사람 검토(alert_triage).

  회차(episode): 같은 이탈이 이어지는 동안은 같은 alertId 라 몇 번을 보아도 처리 건은 하나다(start_definition 의 event_id 중복 거절).
  재고는 재주문점 아래로 내려간 시각(below_since), 정기 정비는 계수기 회차(cycle — 리셋마다 +1)가 회차 키다. 해제(CLEAR) 경보는 보내지
  않는다 — 처리 건은 효과 확인(입고 확인 · 시운전 확인)과 결과 보고로 닫힌다.

  새 감시 추가: RULES 에 MonitorRule 하나(read 이름 · triggered · episode · alert)와 PATTERNS 에 패턴 계약 하나를 더하면 된다. 루프 · 접수 ·
  중복 처리 · 흐름 가져오기의 경보 패턴 목록(bpmn_import.catalog)은 그대로 쓴다.
"""
from __future__ import annotations

import asyncio
import logging
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from hydcommon import topics

log = logging.getLogger("process.business_monitor")
ERP_SOURCE = "erp"
CMMS_SOURCE = "cmms"
SOURCES = (ERP_SOURCE, CMMS_SOURCE)

# 업무 경보 패턴 계약. policy = 흐름 정의 alertPolicy.patterns 의 회복 기준(alert_policy.validate 계약). 업무 경보에는 센서 재관측이 없다 —
# 태그는 감시 규칙의 이탈 표시(1 = 이탈)이고, 처리 건은 효과 확인(입고)으로 닫힌다. 명령 · 재관측을 넣은 흐름이면 해제 없음 → 상급자 확인.
PATTERNS: dict[str, dict] = {
    "SPARE_BELOW_MIN": {
        "name": "예비품 재고 기준 이탈 (ERP 재고 감시)",
        "severity": "warning",
        "read": "spare_stock", "source": ERP_SOURCE,
        "policy": {"tag": "ERP_SPARE_BELOW_MIN", "op": "<", "limit": 1.0, "requireClear": True},
    },
    "PM_DUE": {
        "name": "정기 정비 도래 (CMMS 운전시간 계수기)",
        "severity": "info",
        "read": "pm_status", "source": CMMS_SOURCE,
        "policy": {"tag": "CMMS_PM_DUE", "op": "<", "limit": 1.0, "requireClear": True},
    },
}


def policy_patterns() -> dict[str, dict]:
    """B3 가져오기의 경보 시작 패턴에 보탤 {패턴: 회복 기준}."""
    return {code: deepcopy(p["policy"]) for code, p in PATTERNS.items()}


def is_business_alert(alert) -> bool:
    return (isinstance(alert, dict) and alert.get("pattern") in PATTERNS
            and alert.get("source") == PATTERNS[alert["pattern"]].get("source", ERP_SOURCE))


@dataclass(frozen=True)
class MonitorRule:
    pattern: str
    read: str                                         # enterprise_read 이름 (records 목록을 돌려준다)
    triggered: Callable[[dict], bool]
    episode: Callable[[dict], str | None]             # 이탈 회차 키 (같은 회차 = 같은 경보)
    subject: Callable[[dict], str]                    # 경보 id 에 들어갈 대상 (부품 번호 · 설비)
    asset: Callable[[dict], str | None]
    evidence: Callable[[dict], dict]


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


def _digits(value) -> str:
    return re.sub(r"[^0-9]", "", str(value or ""))[:14]


RULES: tuple[MonitorRule, ...] = (
    MonitorRule(pattern="SPARE_BELOW_MIN", read="spare_stock",
                triggered=lambda r: bool(r.get("below_reorder_point")) and bool(r.get("below_since")),
                episode=lambda r: _digits(r.get("below_since")), subject=lambda r: str(r.get("part_no")),
                asset=lambda r: r.get("reserved_for"), evidence=_spare_evidence),
    MonitorRule(pattern="PM_DUE", read="pm_status",
                triggered=lambda r: r.get("pm_due") is True,
                episode=lambda r: f"C{r.get('cycle')}" if r.get("cycle") is not None else None, subject=lambda r: str(r.get("asset")),
                asset=lambda r: r.get("asset"), evidence=_pm_evidence),
)


def alert_id(rule: MonitorRule, row: dict) -> str:
    stamp = re.sub(r"[^0-9A-Za-z]", "", str(rule.episode(row) or ""))[:24]
    prefix = str(PATTERNS.get(rule.pattern, {}).get("source", ERP_SOURCE)).upper()
    return f"{prefix}-{rule.pattern}-{re.sub(r'[^A-Za-z0-9-]', '', rule.subject(row))}-{stamp}"


def build_alert(rule: MonitorRule, row: dict, now: datetime | None = None) -> dict | None:
    """규칙 하나 · 업무 행 하나 → 경보(조건이 아니면 None). 설비 키가 없거나 모르는 설비면 None(사유는 로그)."""
    if not rule.triggered(row) or not rule.episode(row):
        return None
    asset = rule.asset(row)
    if asset not in topics.ASSETS:
        log.warning("business monitor %s: %s has no known asset (%r) — alert not raised", rule.pattern, rule.subject(row), asset)
        return None
    spec = PATTERNS[rule.pattern]
    t = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    source = spec.get("source", ERP_SOURCE)
    return {"alertId": alert_id(rule, row), "asset": asset, "pattern": rule.pattern, "severity": spec["severity"], "state": "RAISE", "t": t,
            "evidence": rule.evidence(row), "source": source, "observedBy": {"id": f"sys:{source}-monitor", "name": spec["name"]}}


def scan_once(read: Callable[[str, dict], dict], seen: set[str], rules=RULES, now: datetime | None = None) -> list[dict]:
    """업무 데이터를 한 번 읽어 새 경보 목록을 돌려준다(이미 보낸 회차 · 경보는 seen 으로 거른다). 규칙 하나의 읽기 실패는 그 규칙만 건너뛴다
    (다른 업무 시스템의 감시는 계속 — 실패는 로그). 모든 규칙이 실패하면 예외."""
    out, failures = [], []
    for rule in rules:
        try:
            rows = (read(rule.read, {}) or {}).get("records") or []
        except Exception as e:  # noqa: BLE001
            failures.append(f"{rule.pattern}: {e}")
            log.warning("business monitor %s read failed: %s", rule.pattern, e)
            continue
        for row in rows:
            alert = build_alert(rule, row, now)
            if alert and alert["alertId"] not in seen:
                out.append(alert)
    if failures and len(failures) == len(rules):
        raise RuntimeError("; ".join(failures))
    return out


async def run(read: Callable[[str, dict], dict], admit, interval_s: float, audit=lambda *a, **k: None, rules=RULES) -> None:
    """감시 루프: interval_s 마다 scan_once → admit(alert)(원천 접수 경로). 접수한 경보는 seen 에 두어 다시 보내지 않는다(재시작 뒤 한 번 더
    보내도 원천 접수 · start_definition 이 같은 alertId 를 한 처리 건으로 묶는다). 실패는 기록하고 다음 주기에 다시 본다."""
    seen: set[str] = set()
    while True:
        try:
            alerts = await asyncio.to_thread(scan_once, read, seen, rules)
            for alert in alerts:
                try:
                    await admit(alert)
                    seen.add(alert["alertId"])
                    audit(alert["asset"], alert["observedBy"]["id"], "BUSINESS_ALERT_RAISED",
                          {"alertId": alert["alertId"], "pattern": alert["pattern"], "evidence": alert["evidence"]})
                    log.info("business monitor raised %s (%s)", alert["alertId"], alert["pattern"])
                except Exception as e:  # noqa: BLE001
                    log.warning("business monitor could not admit %s: %s", alert.get("alertId"), e)
        except Exception as e:  # noqa: BLE001 — enterprise-sim 이 잠시 없을 수 있다
            log.warning("business monitor read failed: %s", e)
        await asyncio.sleep(interval_s)
