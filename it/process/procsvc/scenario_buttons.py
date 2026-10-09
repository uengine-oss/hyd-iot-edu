"""C3 B · C 단순화 (2026-10-09 확정 지시 — '설비까지 안 가기로 함, 처리되면 끝'): 포털 '결함 실험'의 시나리오 버튼.

  [정기 점검] (B, HYD-02)  — 화면 표시 '정기 점검 도래' = CMMS ent.pm_status.pm_alert (운전시간 ≥ 1,950 h 이고 이번 회차 정비 오더 없음)
  [재고 보충] (C, HYD-03)  — 화면 표시 '재고 보충 필요' = ERP ent.spare_stock 씰 키트 가용 < 재주문점
  [초기화]                 — 그 시나리오의 업무 데이터를 수업 시작값으로(표시가 다시 켜진다)

버튼은 지금 업무 DB 한 행을 읽어, 업무 감시(business_monitor)와 **같은 계약**의 경보(alertId · asset · pattern · evidence · source)를 만들어
같은 원천 접수 경로로 보낸다(main._admit_human_alert → 경보 정책 → 배포된 B · C 흐름 → 처리 건 + 사건). 처리 건 시작이 사람 버튼이라는 것만
다르고, 근거 값(evidence)은 감시와 같은 칸이다. 경보 id 끝에 누른 시각을 붙여 초기화 뒤 다시 누르면 새 처리 건이 된다.

거절(409): 표시가 꺼져 있음(이미 처리됨 — 초기화 먼저) · 같은 시나리오 처리 건이 진행 중 · 그 패턴을 여는 흐름이 배포되지 않음.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable

from . import business_monitor, engine

SCENARIOS: dict[str, dict] = {
    "B": {"pattern": "PM_DUE", "asset": "HYD-02", "read": "pm_status", "params": {"asset": "HYD-02"}, "flag": "pm_alert",
          "subject": "HYD-02", "label": "정기 점검 도래", "button": "정기 점검", "title": "정기 정비",
          "show": ("pm_since_h", "pm_interval_h", "pm_due_in_h", "pm_limit_in_h", "night_window_at", "pm_planned_wo", "pm_planned_window")},
    "C": {"pattern": "SPARE_BELOW_MIN", "asset": "HYD-03", "read": "spare_stock", "params": {"part": "P-PMP-SEAL"},
          "flag": "below_reorder_point", "subject": "P-PMP-SEAL", "label": "재고 보충 필요", "button": "재고 보충", "title": "예비품 구매",
          "show": ("part_no", "name", "on_hand", "reserved", "on_order", "available", "reorder_point", "target_stock", "need_qty")},
}


class Refused(Exception):
    """사람이 읽는 거절 사유(HTTP 409)."""


def _rule(pattern: str) -> business_monitor.MonitorRule:
    return next(r for r in business_monitor.RULES if r.pattern == pattern)


def _row(read: Callable[[str, dict], dict], spec: dict) -> dict:
    res = read(spec["read"], dict(spec["params"])) or {}
    rows = res.get("records") or ([res["facts"]] if res.get("facts") else [])
    key, want = ("asset", spec["asset"]) if spec["read"] == "pm_status" else ("part_no", spec["subject"])
    row = next((r for r in rows if r.get(key) == want), None)
    if row is None:
        raise Refused(f"{spec['title']}: 업무 데이터({spec['read']})에 {want} 행이 없습니다")
    return row


def event_prefix(spec: dict) -> str:
    source = business_monitor.PATTERNS[spec["pattern"]]["source"].upper()
    return f"{source}-{spec['pattern']}-{re.sub(r'[^A-Za-z0-9-]', '', spec['subject'])}-"


def _runs(rt, spec: dict, limit: int = 60) -> list[dict]:
    prefix = event_prefix(spec)
    # 사람 검토(alert_triage)는 흐름이 없을 때의 대기열이지 그 시나리오의 처리 건이 아니다
    return [i for i in rt.repo.list_instances(limit=limit, tenant_id=rt.tenant_id)
            if str(i.get("start_event_id") or "").startswith(prefix) and i.get("proc_def_id") != "alert_triage"]


def _brief(inst: dict | None) -> dict | None:
    if not inst:
        return None
    report = (engine.variables(inst).get("result_report") or {})
    return {"instance": inst["proc_inst_id"], "status": inst.get("status"), "started_at": inst.get("start_date"), "ended_at": inst.get("end_date"),
            "outcome": report.get("outcome")}


def status(read: Callable[[str, dict], dict], rt=None) -> dict:
    """시나리오마다: 표시(alert) · 표시 글 · 근거 값 몇 개 · 진행 중 처리 건 · 마지막 처리 건. 업무 시스템을 못 읽으면 그 시나리오만 error."""
    out = {}
    for key, spec in SCENARIOS.items():
        item = {"key": key, "asset": spec["asset"], "pattern": spec["pattern"], "label": spec["label"], "button": spec["button"],
                "title": spec["title"]}
        try:
            row = _row(read, spec)
            item.update(alert=bool(row.get(spec["flag"])), facts={k: row.get(k) for k in spec["show"] if k in row})
        except Exception as e:  # noqa: BLE001 — 한 업무 시스템이 없어도 다른 시나리오는 보인다
            item.update(alert=None, error=str(e)[:200])
        if rt is not None:
            runs = _runs(rt, spec)
            item["running"] = _brief(next((i for i in runs if i.get("status") == "RUNNING"), None))
            item["last"] = _brief(runs[0] if runs else None)
        out[key] = item
    return {"scenarios": out, "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def who(body: dict | None) -> dict:
    """포털이 보낸 누름 주체(지금 고른 '나' — 로그인 없음). 없으면 '나 미선택'이라고 남긴다(지어내지 않는다)."""
    body = body or {}
    roles = body.get("roles") if isinstance(body.get("roles"), list) else ([body["role"]] if body.get("role") else [])
    return {"by": str(body.get("by") or "나 미선택")[:80], "user_id": str(body.get("user_id") or "")[:80] or None,
            "roles": [str(r)[:60] for r in roles][:5]}


def press_event(proc_inst_id: str, button: str, asset: str, person: dict, at: str, extra: dict | None = None) -> dict:
    """처리 건 자체에 남는 '버튼을 누른 사람 · 때' 기록(처리 기록 화면 · 실시간 기록이 읽는 events 표)."""
    return {"job_id": "SCENARIO_BUTTON", "todo_id": None, "proc_inst_id": proc_inst_id, "crew_type": "human", "event_type": "task_working",
            "data": dict(extra or {}, name=f"수업 버튼 [{button}] — {person['by']}", button=button, asset=asset, by=person["by"],
                         user_id=person.get("user_id"), roles=person.get("roles"), at=at)}


def build_alert(key: str, row: dict, by: str | None = None, now: datetime | None = None, person: dict | None = None) -> dict:
    """업무 감시와 같은 계약의 경보. 근거 값은 감시 규칙의 evidence 그대로 + 누가 · 언제 · 무엇으로 시작했는지."""
    spec = SCENARIOS[key]
    rule = _rule(spec["pattern"])
    pat = business_monitor.PATTERNS[spec["pattern"]]
    clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    source = pat["source"]
    person = person or who({"by": by})
    evidence = dict(rule.evidence(row), trigger=f"포털 결함 실험 · [{spec['button']}] 버튼", requested_by=person["by"],
                    requested_user=person.get("user_id"), requested_roles=person.get("roles"),
                    requested_at=clock.isoformat(timespec="seconds"))
    return {"alertId": event_prefix(spec) + clock.strftime("%Y%m%d%H%M%S"), "asset": spec["asset"], "pattern": spec["pattern"],
            "severity": pat["severity"], "state": "RAISE", "t": clock.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "evidence": evidence, "source": source,
            "observedBy": {"id": f"sys:{source}-monitor", "name": f"{pat['name']} — [{spec['button']}] 버튼"}}


def prepare(key: str, read: Callable[[str, dict], dict], rt, route: Callable[[str], str | None], person: dict | None = None) -> dict:
    """시작 전 확인 → 경보. route(pattern) = 그 패턴을 여는 배포 흐름 id(기준 흐름이면 None)."""
    if key not in SCENARIOS:
        raise KeyError(key)
    spec = SCENARIOS[key]
    row = _row(read, spec)
    if not row.get(spec["flag"]):
        raise Refused(f"{spec['asset']}에 '{spec['label']}' 표시가 없습니다 — 이미 처리됐습니다. [초기화]로 수업 시작 상태로 되돌린 뒤 누르세요")
    running = next((i for i in _runs(rt, spec) if i.get("status") == "RUNNING"), None)
    if running:
        raise Refused(f"{spec['title']} 처리 건이 이미 진행 중입니다 ({running['proc_inst_id']})")
    if not route(spec["pattern"]):
        raise Refused(f"{spec['pattern']} 경보를 여는 {spec['title']} 흐름이 배포되어 있지 않습니다 — 흐름 가져오기에서 배포하세요")
    return {"alert": build_alert(key, row, person=person), "row": row}


def started(rt, key: str, alert: dict, definition: str, person: dict | None = None) -> dict:
    inst = rt.repo.find_event_instance(rt.tenant_id, definition, alert["alertId"])
    if inst and person:
        ev = alert["evidence"]
        rt.repo.record_events([press_event(inst["proc_inst_id"], SCENARIOS[key]["button"], alert["asset"], person, ev.get("requested_at"),
                                           {"alertId": alert["alertId"]})])
    return {"scenario": key, "alertId": alert["alertId"], "definition": definition,
            "instance": inst["proc_inst_id"] if inst else None, "incident": engine.variables(inst).get("incident") if inst else None,
            "evidence": alert["evidence"]}


def last_instance(rt, key: str) -> dict | None:
    runs = _runs(rt, SCENARIOS[key])
    return runs[0] if runs else None
