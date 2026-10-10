"""포털 '결함 실험'의 시나리오 버튼과 수업 입력. 시나리오 이름은 실라버스(2026-10-10) 표기를 쓴다:
설비 결함 인지 · 조치(A, HYD-01) / 정기 정비(B, HYD-02) / 예비품 구매(C, HYD-03).

  [정기 정비] (B)    — 화면 표시 '정기 정비 도래' = CMMS ent.pm_status.pm_alert (운전시간 ≥ 1,950 h 이고 이번 회차 정비 오더 없음)
  [예비품 구매] (C)  — 화면 표시 '재고 보충 필요' = ERP ent.spare_stock 씰 키트 가용 < 재주문점
  [초기화]           — 그 시나리오의 업무 데이터를 수업 시작값으로(표시가 다시 켜진다). B 는 HYD-02 설비 시뮬레이터도 정상으로 되돌린다
                       (정비 · 시운전이 설비 값을 읽고, 수업 입력 '정비 불량'이 설비에 남기 때문)

수업 입력(CLASS_INPUTS, 실라버스 104 · 111 · 114행의 비정상 결말) — 결과 값을 넣지 않는다. 시뮬레이터의 **원인**을 바꾸고, 흐름이 실제
재관측 · 시운전 · 납기 타이머로 그 결말에 이른다:
  A 조치 미달    [쿨러 열화 + 팬 구동부 고장 주입]  plant-sim: 쿨러 열화(moderate) + 팬이 지령을 따르지 않음 → 승인한 냉각 명령이 접수돼도
                                                    유온이 회복 기준 안으로 오지 않는다(재관측 미달)
  B 시운전 미달  [정비 불량 예약]                   plant-sim: 다음 정비가 내부 누설을 남긴다 → 시운전 값이 PM-02 기준에 못 미친다
  C 납기 초과    [공급사 납기 지연 통보]            enterprise-sim: 열린 발주의 입고 예정이 늦어진다 → 납기 기한 타이머가 먼저 울린다

버튼은 지금 업무 DB 한 행을 읽어, 업무 감시(business_monitor)와 **같은 계약**의 경보(alertId · asset · pattern · evidence · source)를 만들어
같은 원천 접수 경로로 보낸다(main._admit_human_alert → 경보 정책 → 배포된 B · C 흐름 → 처리 건 + 사건). 처리 건 시작이 사람 버튼이라는 것만
다르고, 근거 값(evidence)은 감시와 같은 칸이다. 경보 id 끝에 누른 시각을 붙여 초기화 뒤 다시 누르면 새 처리 건이 된다.

거절(409): 표시가 꺼져 있음(이미 처리됨 — 초기화 먼저) · 같은 시나리오 처리 건이 진행 중 · 그 패턴을 여는 흐름이 배포되지 않음.

시나리오 시각 기준점(생산 오더 납기 · 예정된 정비 시간)은 설비 처리 건이 하나도 진행 중이 아닐 때만 지금으로 옮긴다(may_reanchor). 예정된 정비
시간 id 가 기준점 시각을 품고 있어서, 진행 중인 처리 건이 승인 뒤 낼 작업지시의 창이 사라지기 때문이다.

  [쿨러 열화 주입] · [쿨러 복구] (A, HYD-01) — plant-sim 주입에 누름 id(origin)를 싣는다. 설비 상태(plant.status injection)에 남은 그 id 로,
  주입이 일으킨 경보가 연 처리 건에 기록을 붙인다(main._link_injection). 시간 창으로 짐작하지 않는다.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Callable

from hydcommon import topics

from . import business_monitor, effect_parts, engine

SCENARIOS: dict[str, dict] = {
    "B": {"pattern": "PM_DUE", "asset": "HYD-02", "read": "pm_status", "params": {"asset": "HYD-02"}, "flag": "pm_alert",
          "subject": "HYD-02", "label": "정기 정비 도래", "button": "정기 정비", "title": "정기 정비",
          "show": ("pm_since_h", "pm_interval_h", "pm_due_in_h", "pm_limit_in_h", "night_window_at", "pm_planned_wo", "pm_planned_window"),
          "reset": ("/cmms/pm/reset", {})},       # 세 대 모두 — 묶음 후보 HYD-03 계수기도 판단 사실이다
    "C": {"pattern": "SPARE_BELOW_MIN", "asset": "HYD-03", "read": "spare_stock", "params": {"part": "P-PMP-SEAL"},
          "flag": "below_reorder_point", "subject": "P-PMP-SEAL", "label": "재고 보충 필요", "button": "예비품 구매", "title": "예비품 구매",
          "show": ("part_no", "name", "on_hand", "reserved", "on_order", "available", "reorder_point", "target_stock", "need_qty"),
          "reset": ("/erp/spare/reset", {"part_no": "P-PMP-SEAL"})},
}

A_ASSET = "HYD-01"
#: A 의 쿨러 열화 세기. 시나리오 A 는 "경보가 났고 보호 정지(65 ℃) 전에 식힌다"이다 — moderate(쿨러 0.55)는 평형 62.5 ℃로 경보만 내고,
#: high(0.43)는 평형 70 ℃로 주입 뒤 시뮬레이션 약 30분(20배속 실제 90초)에 보호 정지한다(A146 열모델). 20배속은 설비 물리만 빠르게 하고
#: 에이전트 판단(실측 46~79초)은 빠르게 하지 못하므로 high 는 실제 시간으로 약 25분의 판단 지연과 같다 — 보호 정지 장면을 보일 때만 쓴다.
A_SEVERITY = "moderate"
A_TITLE = "설비 결함 인지 · 조치"
_COOLER_FAULT = {"type": "cooler_degradation", "severity": A_SEVERITY}
#: faults = plant-sim 주입 목록(한 번 누름 = 같은 누름 id). opens_case = 이 누름이 경보 → 처리 건을 일으킨다(시각 기준점을 먼저 맞춘다)
A_BUTTONS: dict[str, dict] = {
    "degrade": {"button": "쿨러 열화 주입", "faults": [_COOLER_FAULT], "opens_case": True},
    # 수업 입력(조치 미달): 경보까지는 [쿨러 열화 주입]과 같은 물리다(팬 한계 60 % = 지금 팬 속도). 승인한 '팬 100 %' 명령은 PLC 가 접수하지만
    # 팬이 따라오지 않아 냉각이 모자란다. 쿨러 열화 세기만으로는 이 결말이 나오지 않는다(ot/plant-sim thermal.py 머리말의 계산)
    "degrade-stuck-fan": {"button": "쿨러 열화 + 팬 구동부 고장 주입", "faults": [_COOLER_FAULT, {"type": "fan_drive_fault"}],
                          "opens_case": True, "class_input": "조치 미달",
                          "cause": "설비 시뮬레이터: 쿨러 열화에 더해 팬 구동부가 속도 지령을 따르지 않는다(팬이 지금 속도에 머묾)"},
    # 복구 = 쿨러 · 팬 구동부를 정상으로 + 조치로 바뀐 팬 · 부하 지령을 평소 운전점으로(안 그러면 팬 100 % 인 채라 다음 열화 주입이 경보를 내지 못한다)
    "restore": {"button": "쿨러 복구", "faults": [{"type": "restore", "component": "cooler"}, {"type": "restore", "component": "fan-drive"},
                                                {"type": "operating_point"}]},
}
B_ASSET, C_ASSET = SCENARIOS["B"]["asset"], SCENARIOS["C"]["asset"]
#: B [초기화]가 설비 시뮬레이터에 보내는 것: 예약된 정비 불량을 풀고(잔류 0) HYD-02 를 정상으로
B_PLANT_RESET = [{"type": "maintenance_defect", "target": 0}, {"type": "restore"}]
B_POOR_MAINTENANCE = {"button": "정비 불량 예약", "fault": {"type": "maintenance_defect"}, "class_input": "시운전 미달"}
#: fallback_days = 흐름에 납기 기한 타이머가 없을 때의 지연 일수. 타이머가 있으면 그 기한을 넘기는 가장 작은 일수를 쓴다(default_delay_days)
C_DELAY = {"button": "공급사 납기 지연 통보", "skill": "skill:delay-delivery", "fallback_days": 3, "class_input": "납기 초과"}
DELAY_DAYS_MAX = 60      # enterprise-sim skill:delay-delivery 가 받는 범위(0 초과 60 이하)
#: 포털이 그릴 수업 입력 목록(GET /api/scenario/status 의 class_inputs) — 요청 경로 · 버튼 글 · 어떤 결말을 위한 입력인지 · 누를 때
CLASS_INPUTS = [
    {"scenario": "A", "asset": A_ASSET, "path": "/api/scenario/A/degrade-stuck-fan", "button": A_BUTTONS["degrade-stuck-fan"]["button"],
     "outcome": "조치 미달", "when": "[쿨러 열화 주입] 대신 누른다 — 경보 · 추천 · 승인은 같고, 재관측에서 미달로 끝난다"},
    {"scenario": "B", "asset": B_ASSET, "path": "/api/scenario/B/poor-maintenance", "button": B_POOR_MAINTENANCE["button"],
     "outcome": "시운전 미달", "when": "정비 단계가 시작되기 전(처리 건을 열기 전이나 예약 시각 대기 중)에 누른다"},
    {"scenario": "C", "asset": C_ASSET, "path": "/api/scenario/C/delay-delivery", "button": C_DELAY["button"],
     "outcome": "납기 초과", "when": "발주가 난 뒤 입고 대기 중에 누른다 (body days: 늦어지는 일수 — 비우면 납기 기한을 넘기는 가장 작은 일수)"},
]


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


def may_reanchor(rt) -> bool:
    """설비 처리 건(A · B · C — 설비 값이 있는 처리 건)이 하나도 진행 중이 아니면 True."""
    return not any(engine.variables(i).get("asset") in topics.ASSETS for i in rt.repo.list_instances("RUNNING", None, rt.tenant_id))


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
    return {"scenarios": out, "presses": presses, "class_inputs": [dict(i) for i in CLASS_INPUTS],
            "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def running_case(rt, key: str) -> dict | None:
    """그 시나리오의 진행 중 처리 건(없으면 None)."""
    return next((i for i in _runs(rt, SCENARIOS[key]) if i.get("status") == "RUNNING"), None)


def open_purchase_order(rt) -> tuple[dict, dict]:
    """예비품 구매 처리 건 중 발주가 났고 아직 입고 대기인 것 → (처리 건, 발주 영수증). 없으면 Refused(사람이 읽는 사유)."""
    inst = running_case(rt, "C")
    if inst is None:
        raise Refused("진행 중인 예비품 구매 처리 건이 없습니다 — [예비품 구매]로 처리 건을 열고 발주가 난 뒤에 누르세요")
    values = engine.variables(inst)
    po = values.get("purchase_order")
    if not isinstance(po, dict) or not po.get("ref"):
        raise Refused("아직 발주 전입니다 — 구매 담당이 승인해 ERP 발주가 난 뒤(입고 대기 중)에 누르세요")
    if values.get("goods_receipt"):
        raise Refused(f"발주 {po['ref']} 는 이미 입고됐습니다 — 납기 지연을 알릴 열린 발주가 없습니다")
    return inst, po


def requested_delay_days(body: dict | None) -> float | None:
    """요청이 준 지연 일수(없으면 None — default_delay_days 가 정한다). 숫자가 아니거나 범위 밖이면 ValueError."""
    if "days" not in (body or {}):
        return None
    days = body["days"]
    if isinstance(days, bool) or not isinstance(days, (int, float)) or not 0 < days <= DELAY_DAYS_MAX:
        raise ValueError(f"days 는 0 보다 크고 {DELAY_DAYS_MAX} 이하인 숫자입니다 (받은 값: {days!r})")
    return float(days)


def default_delay_days(rt, inst: dict, po: dict) -> float:
    """지연 일수를 주지 않았을 때: 그 처리 건 흐름의 입고 대기에 붙은 납기 기한 타이머를 넘기는 가장 작은 정수 일수
    (리드타임 + 이미 알린 지연 + 일수 > 기한). 승인한 공급사의 리드타임이 달라도 지연 결과에 이른다. 기한 타이머가 없으면 fallback_days."""
    defn = rt.definition_for(inst)
    receipt = next((a["id"] for a in defn.activities.values() if a.get("tool") == effect_parts.GR_TOOL), None)
    timers = [e["timer"] for e in (defn.attached_events(receipt) if receipt else []) if e.get("eventDefinition") == "timer" and e.get("timer")]
    if not timers:
        return float(C_DELAY["fallback_days"])
    after = po.get("after") if isinstance(po.get("after"), dict) else {}
    deadline_d = min(engine.iso_duration_seconds(t) for t in timers) / 86400
    slack = deadline_d - float(after.get("lead_d") or 0) - float(after.get("delay_d") or 0)
    return float(max(1, int(slack // 1) + 1))


def injection_event(proc_inst_id: str, asset: str, injection: dict, extra: dict) -> dict:
    """설비 주입이 연 처리 건의 누름 기록. 수업 입력으로 한 주입이면(누름에 class_input 이 실려 있다) '수업 입력' 줄로 남긴다."""
    spec = next((b for b in A_BUTTONS.values() if b["button"] == injection.get("button") and b.get("class_input")), None)
    if spec is None or injection.get("class_input") != spec["class_input"]:
        return press_event(proc_inst_id, injection["button"], asset, injection, injection["at"], extra)
    return class_input_event(proc_inst_id, spec, asset, injection, injection["at"], spec["cause"], extra)


def class_input_event(proc_inst_id: str, spec: dict, asset: str, person: dict, at: str, cause: str, extra: dict | None = None) -> dict:
    """처리 건 기록의 '수업 입력' 줄: 어떤 버튼 · 누가 · 언제 · 시뮬레이터의 무엇을 바꿨는지(cause). 결과가 아니라 원인을 바꿨다는 것을 적는다."""
    row = press_event(proc_inst_id, spec["button"], asset, person, at, dict(extra or {}, class_input=spec["class_input"], cause=cause))
    row["data"]["name"] = f"수업 입력 [{spec['button']}]"
    row["data"]["content"] = f"{cause} — 결과 값을 넣지 않고 원인만 바꿨다(결말은 흐름의 실제 판정이 낸다)"
    return row


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
        raise Refused(f"'{spec['label']}' 경보로 시작하는 {spec['title']} 흐름이 배포되어 있지 않습니다 — 흐름 가져오기에서 배포하세요")
    return {"alert": build_alert(key, row, person=person), "row": row}


class NotStarted(Exception):
    """경보는 접수됐는데 배포된 흐름의 처리 건이 없다(HTTP 500, 좌표 포함) — '처리 건 시작'이라고 답하지 않는다."""


def started(rt, key: str, alert: dict, definition: str, person: dict | None = None) -> dict:
    inst = rt.repo.find_event_instance(rt.tenant_id, definition, alert["alertId"])
    if inst is None:
        raise NotStarted(f"{SCENARIOS[key]['title']}: 경보 {alert['alertId']} 를 접수했지만 흐름 {definition} 의 처리 건이 열리지 않았습니다")
    if person:
        ev = alert["evidence"]
        rt.repo.record_events([press_event(inst["proc_inst_id"], SCENARIOS[key]["button"], alert["asset"], person, ev.get("requested_at"),
                                           {"alertId": alert["alertId"]})])
    return {"scenario": key, "alertId": alert["alertId"], "definition": definition,
            "instance": inst["proc_inst_id"], "incident": engine.variables(inst).get("incident"), "evidence": alert["evidence"]}


def last_instance(rt, key: str) -> dict | None:
    runs = _runs(rt, SCENARIOS[key])
    return runs[0] if runs else None
