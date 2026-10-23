"""C3 B · C 단순화 (2026-10-09 확정 지시 — '설비까지 안 가기로 함, 처리되면 끝'): 포털 '결함 실험'의 시나리오 버튼.

  [정기 점검] (B, HYD-02)  — 화면 표시 '정기 점검 도래' = CMMS ent.pm_status.pm_alert (운전시간 ≥ 1,950 h 이고 이번 회차 정비 오더 없음)
  [재고 보충] (C, HYD-03)  — 화면 표시 '재고 보충 필요' = ERP ent.spare_stock 씰 키트 가용 < 재주문점
  [초기화]                 — 그 시나리오의 업무 데이터를 수업 시작값으로(표시가 다시 켜진다)

버튼은 지금 업무 DB 한 행을 읽어, 업무 감시(business_monitor)와 **같은 계약**의 경보(alertId · asset · pattern · evidence · source)를 만들어
같은 원천 접수 경로로 보낸다(main._admit_human_alert → 경보 정책 → 배포된 B · C 흐름 → 처리 건 + 사건). 처리 건 시작이 사람 버튼이라는 것만
다르고, 근거 값(evidence)은 감시와 같은 칸이다. 경보 id 끝에 누른 시각을 붙여 초기화 뒤 다시 누르면 새 처리 건이 된다.

거절(409): 표시가 꺼져 있음(이미 처리됨 — 초기화 먼저) · 같은 시나리오 처리 건이 진행 중 · 그 패턴을 여는 흐름이 배포되지 않음.

시나리오 시각 기준점(생산 오더 납기 · 예정된 정비 시간)은 설비 처리 건이 하나도 진행 중이 아닐 때만 지금으로 옮긴다(may_reanchor). 예정된 정비
시간 id 가 기준점 시각을 품고 있어서, 진행 중인 처리 건이 승인 뒤 낼 작업지시의 창이 사라지기 때문이다.
예외(P12, audit2 2026-10-23): 흐름이 스스로 '승인 지연'을 선언한 처리 건 — 열린 일이 사람 단계뿐이고 그 단계의 멈추지 않는 지연 타이머가 이미
울린 처리 건(무응답 실습은 설계상 스스로 끝나지 않는다) — 은 기준점을 붙잡지 않는다. 붙잡으면 업무 시각이 벽시계로 줄어(enterprise-sim
data._at · hours_from_now) 이후 모든 판단이 틀어진다: 납기까지 남은 시간(order_due_h)이 순위 정책의 납기 항목(clamp((24 - due) / 24))과 카드
글(「납기까지 N h」)로 들어가고, 6시간 뒤에는 음수가 된다. 옮긴 뒤 그 처리 건을 승인하면 승인 때 다시 읽는 업무 값이 바뀌어 새 판단을 요구받거나
(agent approval-check 의 근거 기준점 비교) 옛 정비 시간 id 가 거절된다 — 그래서 옮길 때 그 처리 건 기록에 남긴다(main._reanchor_if_idle).
막은 처리 건과 붙잡지 않은 처리 건은 reanchor_blockers 가 이름과 함께 돌려준다(응답 · 감사 기록 · 화면).

  [쿨러 열화 주입] · [쿨러 복구] (A, HYD-01) — plant-sim 주입에 누름 id(origin)를 싣는다. 설비 상태(plant.status injection)에 남은 그 id 로,
  주입이 일으킨 경보가 연 처리 건에 기록을 붙인다(main._link_injection). 시간 창으로 짐작하지 않는다.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Callable

from hydcommon import topics

from . import business_monitor, engine

SCENARIOS: dict[str, dict] = {
    "B": {"pattern": "PM_DUE", "asset": "HYD-02", "read": "pm_status", "params": {"asset": "HYD-02"}, "flag": "pm_alert",
          "subject": "HYD-02", "label": "정기 점검 도래", "button": "정기 점검", "title": "정기 정비",
          "show": ("pm_since_h", "pm_interval_h", "pm_due_in_h", "pm_limit_in_h", "night_window_at", "pm_planned_wo", "pm_planned_window"),
          "reset": ("/cmms/pm/reset", {})},       # 세 대 모두 — 묶음 후보 HYD-03 계수기도 판단 사실이다
    "C": {"pattern": "SPARE_BELOW_MIN", "asset": "HYD-03", "read": "spare_stock", "params": {"part": "P-PMP-SEAL"},
          "flag": "below_reorder_point", "subject": "P-PMP-SEAL", "label": "재고 보충 필요", "button": "재고 보충", "title": "예비품 구매",
          "show": ("part_no", "name", "on_hand", "reserved", "on_order", "available", "reorder_point", "target_stock", "need_qty"),
          "reset": ("/erp/spare/reset", {"part_no": "P-PMP-SEAL"})},
}

A_ASSET = "HYD-01"
#: A 의 쿨러 열화 세기. 시나리오 A 는 "경보가 났고 보호 정지(65 ℃) 전에 식힌다"이다 — moderate(쿨러 0.55)는 평형 62.5 ℃로 경보만 내고,
#: high(0.43)는 평형 70 ℃로 주입 뒤 시뮬레이션 약 30분(20배속 실제 90초)에 보호 정지한다(A146 열모델). 20배속은 설비 물리만 빠르게 하고
#: 에이전트 판단(실측 46~79초)은 빠르게 하지 못하므로 high 는 실제 시간으로 약 25분의 판단 지연과 같다 — 보호 정지 장면을 보일 때만 쓴다.
A_SEVERITY = "moderate"
A_BUTTONS: dict[str, dict] = {
    "degrade": {"button": "쿨러 열화 주입", "fault": {"type": "cooler_degradation", "severity": A_SEVERITY}},
    # 복구 = 쿨러를 정상으로 + 승인한 조치가 바꾼 팬 · 부하 지령을 평소 운전점으로(operating_point). 지령을 그대로 두면 팬 100 % · 부하 80 % 라
    # moderate 열화의 평형이 경보선(55 ℃) 아래여서 다음 [쿨러 열화 주입]이 경보를 내지 못한다
    "restore": {"button": "쿨러 복구", "fault": {"type": "restore", "component": "cooler", "operating_point": True}},
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


def _runs(rt, spec: dict) -> list[dict]:
    """그 시나리오 설비의 처리 건 전부(최신 먼저) 중 이 버튼 경보로 열린 것. 테넌트 전체 최신 N건으로 자르지 않는다 — 질문 · 시험 실행
    처리 건이 위로 쌓여도 진행 중인 처리 건을 놓치지 않게."""
    prefix = event_prefix(spec)
    # 사람 검토(alert_triage)는 흐름이 없을 때의 대기열이지 그 시나리오의 처리 건이 아니다
    return [i for i in rt.repo.list_instances(None, None, rt.tenant_id, asset=spec["asset"])
            if str(i.get("start_event_id") or "").startswith(prefix) and i.get("proc_def_id") != "alert_triage"]


OPEN_STATUSES = ("NEW", "IN_PROGRESS", "SUBMITTED", "PENDING")


def _approval_overdue(defn: engine.Definition, inst: dict, rows: list[dict]) -> list[dict] | None:
    """흐름이 '승인 지연'을 선언하고 사람만 기다리는 처리 건이면 그 사람 단계들, 아니면 None. 열린 일(이벤트 행 제외)이 모두 사람 단계(userTask)이고
    단계마다 붙은 멈추지 않는 타이머(cancelActivity=false) 중 하나가 이미 울렸어야(DONE) 한다. 예정 시각을 기다리는 단계가 있으면 아니다."""
    from . import dependency_schedule
    open_rows = [r for r in rows if r.get("status") in OPEN_STATUSES and r["activity_id"] not in defn.events]
    if not open_rows or dependency_schedule.waiting(inst, rows):
        return None
    done_timers = {r["activity_id"] for r in rows if r.get("status") == "DONE"}
    out = []
    for r in open_rows:
        act = defn.activities.get(r["activity_id"]) or {}
        fired = [e["id"] for e in defn.attached_events(r["activity_id"])
                 if engine.non_interrupting(defn, e["id"]) and e.get("timer") and e["id"] in done_timers]
        if act.get("type") != "userTask" or not fired:
            return None
        out.append({"activity": r["activity_id"], "name": act.get("name") or r["activity_id"], "timer": fired[0]})
    return out


def reanchor_blockers(rt) -> dict:
    """진행 중인 설비 처리 건(A · B · C — 설비 값이 있는 처리 건)을 기준점 판단으로 나눈다.
    blocked_by = 기준점을 붙잡는 처리 건(하나라도 있으면 옮기지 않는다), overdue = 승인 지연을 선언하고 사람만 기다려 붙잡지 않는 처리 건."""
    blocked, overdue = [], []
    for inst in rt.repo.list_instances("RUNNING", None, rt.tenant_id):
        v = engine.variables(inst)
        if v.get("asset") not in topics.ASSETS:
            continue
        item = {"instance": inst["proc_inst_id"], "definition": inst.get("proc_def_id"), "asset": v.get("asset"),
                "started_at": inst.get("start_date")}
        try:
            defn = rt.definition_for(inst)
            rows = rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"], limit=None)
        except (KeyError, LookupError, ValueError) as e:     # 정의를 읽지 못한 처리 건은 붙잡는 쪽으로 — 사유를 싣는다
            blocked.append(dict(item, name=inst.get("proc_inst_name") or inst.get("proc_def_id"), waiting_on=[], why=f"정의를 읽지 못함: {e}"))
            continue
        item["name"] = defn.name
        waiting = _approval_overdue(defn, inst, rows)
        if waiting is not None:
            overdue.append(dict(item, waiting_on=[w["name"] for w in waiting], why="승인 지연 — 사람 응답만 기다림"))
        else:
            live = [r for r in rows if r.get("status") in OPEN_STATUSES and r["activity_id"] not in defn.events]
            blocked.append(dict(item, waiting_on=[r.get("activity_name") or r["activity_id"] for r in live], why="진행 중"))
    return {"blocked_by": blocked, "overdue": overdue}


def may_reanchor(rt) -> bool:
    """기준점을 붙잡는 설비 처리 건이 하나도 없으면 True (reanchor_blockers)."""
    return not reanchor_blockers(rt)["blocked_by"]


def reanchor_event(proc_inst_id: str, at: str, button: str | None) -> dict:
    """승인 지연 중인 처리 건 기록: 기준점이 옮겨졌다 — 지금 승인하면 바뀐 업무 값으로 다시 확인한다."""
    return {"job_id": "SCENARIO_REANCHOR", "todo_id": None, "proc_inst_id": proc_inst_id, "crew_type": "result", "event_type": "task_working",
            "data": {"name": "시나리오 시각 기준점 옮김(승인 지연 중)", "at": at, "button": button,
                     "goal": "승인 지연 중에 수업 버튼이 시나리오 시각 기준점(납기 · 예정된 정비 시간)을 지금으로 옮겼습니다 — 지금 승인하면 "
                             "바뀐 업무 값으로 다시 확인해 새 판단이 필요할 수 있습니다"}}


def _brief(inst: dict | None) -> dict | None:
    if not inst:
        return None
    report = (engine.variables(inst).get("result_report") or {})
    return {"instance": inst["proc_inst_id"], "status": inst.get("status"), "started_at": inst.get("start_date"), "ended_at": inst.get("end_date"),
            "outcome": report.get("outcome")}


def status(read: Callable[[str, dict], dict], rt=None, last_press: Callable[[str], dict | None] | None = None) -> dict:
    """시나리오마다: 표시(alert) · 표시 글 · 근거 값 몇 개 · 진행 중 처리 건 · 마지막 처리 건. 업무 시스템을 못 읽으면 그 시나리오만 error
    (사유를 화면에 보인다). presses = 설비마다 마지막 수업 버튼(누가 · 언제 · 무엇)."""
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
    presses = {a: last_press(a) for a in (A_ASSET, *(sp["asset"] for sp in SCENARIOS.values()))} if last_press else {}
    return {"scenarios": out, "presses": presses, "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def who(body: dict | None) -> dict:
    """포털이 보낸 누름 주체(지금 고른 '나' — 로그인 없음). 없으면 '나 미선택'이라고 남긴다(지어내지 않는다)."""
    body = body or {}
    roles = body.get("roles") if isinstance(body.get("roles"), list) else ([body["role"]] if body.get("role") else [])
    return {"by": str(body.get("by") or "나 미선택")[:80], "user_id": str(body.get("user_id") or "")[:80] or None,
            "roles": [str(r)[:60] for r in roles][:5]}


def press_event(proc_inst_id: str, button: str, asset: str, person: dict, at: str, extra: dict | None = None) -> dict:
    """처리 건 자체에 남는 '버튼을 누른 사람 · 때' 기록(처리 기록 화면 · 실시간 기록이 읽는 events 표).
    name 은 무엇을 눌렀나만, 누른 사람은 by 한 칸에만 싣는다 — 다른 기록 줄처럼 화면이 name 옆에 by 를 붙인다(이름 두 번 금지)."""
    return {"job_id": "SCENARIO_BUTTON", "todo_id": None, "proc_inst_id": proc_inst_id, "crew_type": "human", "event_type": "task_working",
            "data": dict(extra or {}, name=f"수업 버튼 [{button}]", button=button, asset=asset, by=person["by"],
                         user_id=person.get("user_id"), roles=person.get("roles"), at=at)}


def injection_origin(button: str, person: dict) -> dict:
    """plant-sim 주입에 싣는 누름 — id 로 처리 건과 이어진다."""
    return {"id": f"PRESS-{uuid.uuid4().hex[:12]}", "button": button, **person,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def _instant(at) -> datetime:
    """ISO 글(plant-sim 'Z' · 처리 건 '+00:00') 또는 DB 시각 → UTC 시각."""
    return (at if isinstance(at, datetime) else datetime.fromisoformat(str(at).replace("Z", "+00:00"))).astimezone(timezone.utc)


def case_of_injection(rt, asset: str, injection: dict) -> str | None:
    """그 주입 id 로 연결된(SCENARIO_BUTTON 기록에 injection_id 가 있는) 처리 건. 그 설비 처리 건을 최신부터 보되 주입 시각보다 먼저 열린
    처리 건에서 멈춘다(주입이 연 처리 건은 주입 뒤에 열린다) — 건수로 자르지 않는다."""
    since = _instant(injection["at"])
    for inst in rt.repo.list_instances(None, None, rt.tenant_id, asset=asset):
        if _instant(inst["start_date"]) < since:
            return None
        if any(e.get("job_id") == "SCENARIO_BUTTON" and (e.get("data") or {}).get("injection_id") == injection["id"]
               for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])):
            return inst["proc_inst_id"]
    return None


def build_alert(key: str, row: dict, now: datetime | None = None, person: dict | None = None) -> dict:
    """업무 감시와 같은 계약의 경보. 근거 값은 감시 규칙의 evidence 그대로 + 누가 · 언제 · 무엇으로 시작했는지."""
    spec = SCENARIOS[key]
    rule = _rule(spec["pattern"])
    pat = business_monitor.PATTERNS[spec["pattern"]]
    clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    source = pat["source"]
    person = person or who(None)
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
        raise Refused(f"{spec['asset']} {spec['title']} 처리 건이 이미 진행 중입니다 — 카드의 '처리 중' 표시를 눌러 그 처리 건을 보세요")
    if not route(spec["pattern"]):
        raise Refused(f"'{spec['label']}' 경보로 시작하는 {spec['title']} 흐름이 배포되어 있지 않습니다 — [관리] 탭의 「흐름 판본 배포 · 비교 · 되돌리기」에서 배포하세요(흐름 가져오기는 등록까지만 합니다)")
    return {"alert": build_alert(key, row, person=person), "row": row}


class NotStarted(Exception):
    """경보는 접수됐는데 배포된 흐름의 처리 건이 없다(HTTP 409, 경보가 실제로 간 곳 포함) — '처리 건 시작'이라고 답하지 않는다.
    접수와 확인 사이에 배포가 바뀐 상태 충돌이다(서버 고장이 아니다)."""


def _went_to(rt, alert_id: str) -> str:
    """경보가 실제로 연 처리 건(기준 흐름 · 사람 검토) — 거절 사유에 싣는다."""
    for did, label in ((rt.defn.id, "기준 흐름"), ("alert_triage", "사람 검토(경보 분류)")):
        inst = rt.repo.find_event_instance(rt.tenant_id, did, alert_id)
        if inst is not None:
            return f" — 경보는 {label}의 처리 건 {inst['proc_inst_id']}(으)로 열렸습니다"
    return " — 경보가 연 처리 건을 찾지 못했습니다"


def started(rt, key: str, alert: dict, definition: str | None, person: dict | None = None) -> dict:
    spec = SCENARIOS[key]
    if not definition:
        raise NotStarted(f"{spec['title']}: 경보 {alert['alertId']} 를 접수하는 사이 '{spec['label']}' 경보를 여는 흐름의 배포가 내려갔습니다"
                         f"{_went_to(rt, alert['alertId'])}. [관리] 탭의 「흐름 판본 배포 · 비교 · 되돌리기」에서 다시 배포한 뒤 누르세요")
    inst = rt.repo.find_event_instance(rt.tenant_id, definition, alert["alertId"])
    if inst is None:
        raise NotStarted(f"{spec['title']}: 경보 {alert['alertId']} 를 접수했지만 흐름 {definition} 의 처리 건이 열리지 않았습니다"
                         f"{_went_to(rt, alert['alertId'])}. 접수하는 사이 배포가 바뀌었을 수 있습니다 — 흐름 배포 화면을 확인한 뒤 다시 누르세요")
    if person:
        ev = alert["evidence"]
        rt.repo.record_events([press_event(inst["proc_inst_id"], SCENARIOS[key]["button"], alert["asset"], person, ev.get("requested_at"),
                                           {"alertId": alert["alertId"]})])
    return {"scenario": key, "alertId": alert["alertId"], "definition": definition,
            "instance": inst["proc_inst_id"], "incident": engine.variables(inst).get("incident"), "evidence": alert["evidence"]}


def last_instance(rt, key: str) -> dict | None:
    runs = _runs(rt, SCENARIOS[key])
    return runs[0] if runs else None
