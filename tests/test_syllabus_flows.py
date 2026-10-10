"""실라버스 8~10일차(2026-10-10, 통합반 87~115행)의 수업 흐름 세 개 — scripts/c3_flows.py 의 실제 정의를 실제 런타임(MemoryRepo · 실제
Incident 상태기계 · 승인 경로)으로 일곱 결말까지 돌린다. DECISIONS 112 의 'B · C 는 설비까지 가지 않는다'를 실라버스가 대체했다.

  설비 결함 인지 · 조치   정상 승인(냉각 → 재관측 정상) · 승인 거절(설비 명령 없음, 사건 '운전원 거부') · 조치 미달(재관측 기준 밖)
  정기 정비               정비 오더 · 공지 → 예약 시각 대기 → 정비 → 시운전: 정상(다음 정비 시점 갱신) · 시운전 미달(갱신 안 함)
  예비품 구매             ERP 발주 → 공급사 메일 → 입고 대기: 정상 입고(발주와 일치) · 납기 초과(기한 타이머)

비정상 결말은 결과 값을 넣지 않고 원인 쪽 입력으로 만든다 — 시운전 미달 · 조치 미달 시험은 실제 설비 물리(plantsim)가 낸 값을 판정에 넣는다.
그 밖에: 거절 권한 · 사유 · 거절 값을 내지 않는 흐름의 거절 요청, 흐름 사전 검사(승인 앞 설비 명령 · 반려 경로의 효과 · 반려 경로가 열린 채 끝남 ·
끊긴 선), 발주와 어긋난 입고, 수업 입력 API 의 거절 사유."""
import asyncio
from copy import deepcopy
from datetime import timedelta

import pytest
from fastapi import HTTPException

from entsim import state as entstate
from plantsim import thermal
from plantsim.plant import Plant
from procsvc import bpmn_import as B, effect_parts, engine, machine, scenario_buttons as SB
from procsvc import instances as I
from test_instance_mode import world, NOW, _row, NoFx  # noqa: F401  (world 는 fixture)
import test_c2_execution as c2
import test_c3_assembly as c3

FLOWS = c3._flows()
APPROVER = ("이생산", "role:prod-mgr")


def catalog(world):
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    return B.catalog(base, c3.AGENTS)


def checked(world, did, source=None, mapping=None):
    _, src, m = FLOWS.FLOWS[did]
    return B.check(B.parse_bpmn(source or src), deepcopy(mapping or m), {"catalog": catalog(world), "definition_id": did, "version": "1",
                                                                         "file_name": f"{did}.bpmn", "xml_sha256": "x"})


def deploy(world, did):
    r = checked(world, did)
    assert r["ok"], r["problems"]
    rt = world["rt"]
    rt.register_definition(r["definition"])
    rt.deploy_definition(did, "1", "tester", "실라버스 흐름 시험")
    return r["definition"]


def events(rt, inst, job=None):
    rows = rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])
    return [e for e in rows if job in (None, e["job_id"])]


def jobs(rt, inst):
    return [e["job_id"] for e in events(rt, inst)]


# ================================================================ 흐름 모양 (실라버스 문구 그대로)
@pytest.mark.parametrize("did,order", [
    ("c3_cooling", ["원인 진단 · 냉각 조치 제안", "운전원 승인", "냉각 명령", "재관측", "작업지시 등록", "결과 보고: 정상"]),
    ("c3_pm", ["정비 제안", "보전팀장 승인", "정비 오더 · 생산 공지", "예약 시각 대기", "정비", "시운전 확인", "결과 보고: 정상"]),
    ("c3_spare", ["구매 제안", "구매 담당 승인", "ERP 발주", "공급사 메일", "입고 대기 · 확인", "결과 보고: 입고 완료"])])
def test_the_normal_path_of_each_flow_has_the_tasks_the_syllabus_lists_in_order(world, did, order):
    d = deploy(world, did)
    names = {a["id"]: a["name"] for a in d["activities"]}
    nxt = {}
    for s in d["sequences"]:
        nxt.setdefault(s["source"], []).append(s)
    path, node = [], next(e["id"] for e in d["events"] if e["type"] == "startEvent")
    while node in nxt:                                  # 분기에서는 조건 선(승인 · 정상)을 따라간다
        outs = nxt[node]
        node = next((s for s in outs if s.get("condition")), outs[0])["target"]
        if node in names:
            path.append(names[node])
    assert path == order
    assert sum(1 for a in d["activities"] if a["tool"] == B.APPROVAL_TOOL) == 1          # 사람 승인은 흐름마다 한 번
    assert "incident:command" not in {a["tool"] for a in d["activities"]} or did == "c3_cooling"   # 정비 · 구매는 PLC 설비 명령을 내지 않는다
    assert [l["name"] for l in B.parse_bpmn(FLOWS.FLOWS[did][1])["lanes"]] == ["담당자", "에이전트", "시스템"]


def test_names_on_screen_follow_the_syllabus():
    assert [m["name"] for _, _, m in FLOWS.FLOWS.values()] == ["설비 결함 인지 · 조치", "정기 정비", "예비품 구매"]
    assert (SB.A_TITLE, SB.SCENARIOS["B"]["title"], SB.SCENARIOS["C"]["title"]) == ("설비 결함 인지 · 조치", "정기 정비", "예비품 구매")
    assert (SB.SCENARIOS["B"]["button"], SB.SCENARIOS["C"]["button"], SB.SCENARIOS["B"]["label"]) == ("정기 정비", "예비품 구매", "정기 정비 도래")


def test_pm_test_run_criteria_are_the_manuals_not_the_alarm_lines():
    """시운전 합격 기준은 매뉴얼 PM-02 의 PM-2.9 다(경보선 165 bar · 8.0 l/min 보다 높다) — 흐름 설정이 매뉴얼 글과 같은 값을 쓴다."""
    manual = (c3.ROOT / "it" / "portal" / "www" / "samples" / "PM-02_powerpack-pm-checklist.md").read_text(encoding="utf-8")
    line = next(l for l in manual.splitlines() if "15분 시운전" in l)
    crit = FLOWS.PM_TEST_RUN["criteria"]
    assert f"PS1 {crit['PS1'][1]:g} bar 이상" in line and f"FS1 {crit['FS1'][1]:g} l/min 이상" in line and f"VS1 {crit['VS1'][1]:g} mm/s 미만" in line
    assert FLOWS.PM_TEST_RUN["settle"] == "PT15M" and crit["PS1"][1] > effect_parts.TEST_RUN_CRITERIA["PS1"][1]


# ================================================================ 설비 결함 인지 · 조치: 정상 승인 · 승인 거절 · 조치 미달
def open_a(world):
    deploy(world, "c3_cooling")
    rt = world["rt"]
    inst = rt.on_alert_raise(dict(c2.ALERT, alertId="HYD-01-A-1"), now=NOW)
    assert inst["proc_def_id"] == "c3_cooling"
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = c2.a_decision(inc.id)
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": c2.GUIDE,
                                               "decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    return rt, inst, inc, d


def approve_and_ack(rt, inst, inc, d):
    rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], *APPROVER, now=NOW)
    machine.on_status(inc, {"cmdId": inc.cmd_id, "result": "DONE", "t": "2026-10-03T12:00:05Z"}, NOW, NoFx(), time_scale=20)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)


def test_a_approved_card_cools_reobserves_and_ends_normally(world):
    rt, inst, inc, d = open_a(world)
    assert inc.cmd_id is None                                                   # 승인 전에는 설비 명령이 없다
    approve_and_ack(rt, inst, inc, d)
    assert _row(rt, inst, "T_approve")["output"]["approval"] == "승인" and inc.state == "RE_OBSERVING"
    machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, NoFx())
    machine.on_timer(inc, "reobs", NOW, 50.0, NoFx(), time_scale=20)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    rep = engine.variables(done)["result_report"]
    assert (done["status"], done["end_event"], rep["outcome"], inc.state) == ("COMPLETED", "E_ok", "정상", "CLOSED")
    assert _row(rt, inst, "R_rejected")["status"] != "DONE" and _row(rt, inst, "R_fail")["status"] != "DONE"


def test_a_rejected_card_issues_no_plant_command_and_closes_as_operator_rejection(world):
    rt, inst, inc, d = open_a(world)
    fresh = rt.repo.get_instance(inst["proc_inst_id"])            # 앞 회차의 승인 값이 남아 있던 처리 건이라도 거절 뒤에는 비어 있어야 한다
    engine.set_variables(rt.definition_for(fresh), fresh, {"approved_by": "앞 회차 승인자", "commands": [{"code": "FAN_SET", "fan_pct": 100}],
                                                           "chosen_option": {"id": "skill:old"}})
    rt.repo.update_instance(fresh)
    out = rt.reject_card(_row(rt, inst, "T_approve")["id"], d["id"], *APPROVER, "생산 납기가 급해 지금은 감속할 수 없음", now=NOW)
    assert out["rejected"] is True
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert (done["status"], done["end_event"]) == ("COMPLETED", "E_rejected")
    # 설비 쓰기 0건: 사건에 명령 id 가 없고, 명령 · 재관측 · 작업지시 task 는 시작되지 않았다
    assert inc.cmd_id is None and inc.state == "REJECTED_BY_OPERATOR" and world["executed"] == []
    assert all(_row(rt, inst, t)["status"] in ("TODO", "CANCELLED") for t in ("T_cmd", "T_reobs", "T_wo", "R_ok", "R_fail"))
    assert (v["approval"], v["approval_reason"]) == ("반려", "생산 납기가 급해 지금은 감속할 수 없음")
    assert v.get("approved_by") is None and v.get("commands") is None and v.get("chosen_option") is None
    rep = v["result_report"]
    assert (rep["outcome"], rep["level"], rep["incident_closed"]) == ("반려", "rejected", True) and "납기가 급해" in rep["summary"]
    assert world["book"][d["id"]]["state"] == "REJECTED" and world["book"][d["id"]]["reason"].startswith("생산 납기")
    row = events(rt, inst, "APPROVAL_REJECTED")[0]["data"]
    assert (row["name"], row["by"], row["role"]) == ("거절 접수", "이생산", "role:prod-mgr") and "설비 명령" in row["effects"]
    assert "APPROVAL_REJECTED" in world["audits"] and "APPROVAL_ACCEPTED" not in jobs(rt, inst)
    assert rt.repo.list_approvals(inst["proc_inst_id"], rt.tenant_id) == []      # 전달할 승인 기록이 없다


def test_a_rejection_needs_a_reason_and_a_role_that_may_approve_the_card(world):
    rt, inst, inc, d = open_a(world)
    wid = _row(rt, inst, "T_approve")["id"]
    with pytest.raises(ValueError, match="거절 사유"):
        rt.reject_card(wid, d["id"], *APPROVER, "   ", now=NOW)
    with pytest.raises(PermissionError, match="거절 권한 없음"):                 # 운전원(등급 1)은 생산관리자 승인 카드를 거절할 수 없다
        rt.reject_card(wid, d["id"], "김운전", "role:operator", "사유", now=NOW)
    with pytest.raises(ValueError, match="does not belong"):
        rt.reject_card(wid, "DEC-OTHER", *APPROVER, "사유", now=NOW)
    assert _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS" and inc.state == "AWAITING_APPROVAL"
    assert world["book"][d["id"]]["state"] == "PENDING_APPROVAL" and events(rt, inst, "APPROVAL_REJECTED") == []
    rt.reject_card(wid, d["id"], *APPROVER, "사유", now=NOW)
    with pytest.raises(ValueError, match="이미 처리된 승인"):                    # 두 번 거절하지 않는다
        rt.reject_card(wid, d["id"], *APPROVER, "사유", now=NOW)


def test_a_flow_whose_approval_step_gives_no_rejection_value_refuses_the_rejection(world):
    """승인만 하는 부품(task:select)으로 등록한 흐름은 거절 뒤 갈 길이 없다 — 조용히 넘기지 않고 사유와 함께 거절한다."""
    rt, inst, inc, d = c2.open_a(world)
    with pytest.raises(ValueError, match="거절 값을 내지 않아"):
        rt.reject_card(_row(rt, inst, "T_approve")["id"], d["id"], *APPROVER, "사유", now=NOW)
    assert _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS" and inc.state == "AWAITING_APPROVAL"


def test_rejection_endpoint_answers_with_the_reason_codes_and_ends_the_case(world):
    """POST /api/todolist/{id}/reject-card — 포털의 [거절] 이 부를 경로. 사유 없음 422(요청 계약) · 권한 없음 403 · 모르는 task 404 · 두 번째 거절 400."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from procsvc import instance_mode
    rt, inst, inc, d = open_a(world)
    app = FastAPI()
    instance_mode.mount(app, "instance")
    c = TestClient(app)
    url = f"/api/todolist/{_row(rt, inst, 'T_approve')['id']}/reject-card"
    body = {"decision": d["id"], "by": APPROVER[0], "role": APPROVER[1], "reason": "납기 우선"}
    assert c.post(url, json=dict(body, reason="")).status_code == 422
    assert c.post(url, json=dict(body, role="role:operator")).status_code == 403
    assert c.post("/api/todolist/nope/reject-card", json=body).status_code == 404
    assert c.post(url.replace("reject-card", "submit"), json={"output": {"approval": "반려", "approval_reason": "x"}}).status_code == 403
    assert inc.state == "AWAITING_APPROVAL" and inc.cmd_id is None
    r = c.post(url, json=body)
    assert r.status_code == 200 and r.json()["rejected"] is True and r.json()["approval"] == "반려"
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert (done["status"], done["end_event"], inc.state, inc.cmd_id) == ("COMPLETED", "E_rejected", "REJECTED_BY_OPERATOR", None)
    assert c.post(url, json=body).status_code == 400


def stuck_fan_unit(with_fan_fault: bool):
    """[쿨러 열화 + 팬 구동부 고장 주입](수업 입력)이 설비에 보내는 주입을 실제 설비 모델에 넣고 경보 뒤 평형까지 돌린다."""
    plant = Plant(time_scale=1, assets=["HYD-01"])
    spec = SB.A_BUTTONS["degrade-stuck-fan" if with_fan_fault else "degrade"]
    for fault in spec["faults"]:
        plant.inject("HYD-01", fault["type"], severity=fault.get("severity"), origin={"id": "PRESS-1", "button": spec["button"]})
    plant.tick(6000)
    return plant


@pytest.mark.parametrize("with_fan_fault,recovers", [(False, True), (True, False)])
def test_a_shortfall_comes_from_the_plant_cause_not_from_an_injected_result(world, with_fan_fault, recovers):
    """조치 미달의 원인 쪽 입력: 팬 구동부 고장이 있으면 승인한 '팬 100 % · 부하 80 %' 명령을 PLC 가 접수(DONE)해도 재관측 창(15분) 끝의 유온이
    회복 기준(55 ℃) 밖이다. 같은 열화 · 같은 명령이라도 팬이 따라오면 회복한다. 재관측 값은 설비 모델이 낸 값을 그대로 쓴다."""
    plant = stuck_fan_unit(with_fan_fault)
    unit = plant.units["HYD-01"]
    before = unit.state.ts1
    assert 55.0 < before < thermal.TRIP_TS1 and unit.ctrl.state == "RUN"         # 경보는 나고 보호 정지는 없다(두 경우 같은 물리)
    cmd = plant.command("HYD-01", {"cmdId": "C-1", "writes": [{"res": "FanSpeedSP", "v": 100}, {"res": "LoadSP", "v": 80}]}, source="HITL")
    assert cmd.result == "DONE" and plant.tags("HYD-01")["FanSpeedSP"] == 100      # 명령은 접수됐다 — 접수는 효과가 아니다
    plant.tick(engine_reobserve_s())
    ts1 = plant.units["HYD-01"].state.ts1
    assert (ts1 < 55.0) is recovers and unit.ctrl.state == "RUN"
    rt, inst, inc, d = open_a(world)
    approve_and_ack(rt, inst, inc, d)
    if recovers:
        machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, NoFx())
    machine.on_timer(inc, "reobs", NOW, round(ts1, 2), NoFx(), time_scale=20)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    rep = engine.variables(done)["result_report"]
    assert (done["end_event"], rep["outcome"], inc.state) == (("E_ok", "정상", "CLOSED") if recovers else ("E_fail", "미달", "ESCALATED"))


def engine_reobserve_s() -> int:
    from procsvc import definition
    return int(definition.REOBSERVE_SIM_S)


def test_cooler_fouling_alone_cannot_make_the_action_fall_short_without_tripping_first():
    """왜 팬 구동부 고장인가(설계 근거): 쿨러 열화 세기만으로는 '보호 정지 전에 승인 + 조치 미달'이 나오지 않는다 — 조치(팬 100 · 부하 80)가
    55 ℃ 로 못 내리는 세기는 조치 전(팬 60 · 부하 90)에 65 ℃ 보호 정지를 넘는다."""
    for health in [h / 100 for h in range(20, 100)]:
        action_fails = thermal.equilibrium_ts1(80, 100, health) >= 55.0
        trips_before = thermal.equilibrium_ts1(90, 60, health) > thermal.TRIP_TS1
        assert not action_fails or trips_before, health


# ================================================================ 흐름 사전 검사 (실라버스 102행)
def _problems(r, text):
    return [p for p in r["problems"] if text in p["reason"]]


def test_precheck_refuses_a_plant_command_before_the_approval(world):
    _, src, m = FLOWS.FLOWS["c3_cooling"]
    src = (src.replace('<bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>',
                       '<bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_cmd"/>')
              .replace('<bpmn:sequenceFlow id="F4" sourceRef="T_cmd" targetRef="T_reobs"/>',
                       '<bpmn:sequenceFlow id="F4" sourceRef="T_cmd" targetRef="T_approve"/>')
              .replace('<bpmn:sequenceFlow id="F_approved" name="승인" sourceRef="G_approved" targetRef="T_cmd"/>',
                       '<bpmn:sequenceFlow id="F_approved" name="승인" sourceRef="G_approved" targetRef="T_reobs"/>'))
    r = checked(world, "c3_cooling", src, m)
    assert not r["ok"] and _problems(r, "설비 명령 부품 앞 경로에 사람 승인")


def test_precheck_refuses_a_rejection_path_that_reaches_the_command(world):
    _, src, m = FLOWS.FLOWS["c3_cooling"]
    m = deepcopy(m)
    m["flows"]["F_approved"] = {"default": True}                                   # 승인 조건 없이 명령으로
    m["flows"]["F_rejected"] = {"var": "approval", "op": "==", "value": "반려"}
    r = checked(world, "c3_cooling", src, m)
    hit = _problems(r, "반려(또는 조건 없는) 경로로 설비 명령 부품에 닿습니다")
    assert not r["ok"] and hit and "'운전원 승인' → '승인?' → '냉각 명령'" in hit[0]["reason"]


def test_precheck_refuses_a_rejection_path_that_ends_without_closing_the_incident(world):
    _, src, m = FLOWS.FLOWS["c3_cooling"]
    src = (src.replace('<bpmn:sequenceFlow id="F_rejected" name="거절" sourceRef="G_approved" targetRef="R_rejected"/>',
                       '<bpmn:sequenceFlow id="F_rejected" name="거절" sourceRef="G_approved" targetRef="E_rejected"/>')
              .replace('<bpmn:serviceTask id="R_rejected" name="결과 보고: 승인 거절"/>', "")
              .replace('<bpmn:sequenceFlow id="F11" sourceRef="R_rejected" targetRef="E_rejected"/>', "")
              .replace("<bpmn:flowNodeRef>R_rejected</bpmn:flowNodeRef>", ""))
    m = deepcopy(m)
    del m["tasks"]["R_rejected"]
    r = checked(world, "c3_cooling", src, m)
    hit = _problems(r, "반려 경로가 결과 보고(반려) 없이 끝납니다")
    assert not r["ok"] and hit and "'거절 종료'" in hit[0]["reason"]


def test_precheck_refuses_a_broken_line(world):
    _, src, m = FLOWS.FLOWS["c3_cooling"]
    r = checked(world, "c3_cooling", src.replace('<bpmn:sequenceFlow id="F8" sourceRef="R_fail" targetRef="E_fail"/>', ""), m)
    assert not r["ok"] and _problems(r, "끊긴 선")


def test_precheck_refuses_mixing_the_two_card_approval_parts(world):
    _, src, m = FLOWS.FLOWS["c3_cooling"]
    src = (src.replace('<bpmn:userTask id="T_approve" name="운전원 승인"/>',
                       '<bpmn:userTask id="T_approve" name="운전원 승인"/><bpmn:userTask id="T_again" name="한 번 더 승인"/>')
              .replace('<bpmn:sequenceFlow id="F_approved" name="승인" sourceRef="G_approved" targetRef="T_cmd"/>',
                       '<bpmn:sequenceFlow id="F_approved" name="승인" sourceRef="G_approved" targetRef="T_again"/>'
                       '<bpmn:sequenceFlow id="F_again" sourceRef="T_again" targetRef="T_cmd"/>'))
    m = deepcopy(m)
    m["tasks"]["T_again"] = {"part": "task:select", "role": "운전원"}
    r = checked(world, "c3_cooling", src, m)
    assert not r["ok"] and _problems(r, "함께 쓸 수 없습니다")


def test_the_rejectable_part_is_offered_next_to_the_approve_only_part(world):
    parts = {p["key"]: p for p in catalog(world)["parts"]}
    plain, rejectable = parts["task:select"], parts["task:select-or-reject"]
    assert plain["outputs"] == ["chosen_skill", "chosen_skill_kind"] and rejectable["outputs"] == [*plain["outputs"], "approval", "approval_reason"]
    assert plain["tool"] == rejectable["tool"] == B.APPROVAL_TOOL and rejectable["approval"] is True and rejectable["name"] == "조치 카드 승인 · 거절"
    fields = {f["key"]: f for f in rejectable["form"]["fields_json"]}
    assert fields["chosen_skill"]["required"] is False and fields["approval"]["items"] == ["승인", "반려"]
    assert "required" not in {k for f in plain["form"]["fields_json"] for k in f}       # 기준 부품의 폼은 그대로


# ================================================================ 정기 정비: 정상 · 시운전 미달
def pm_readings(defect: bool) -> dict:
    """정비 뒤 시운전이 읽는 값 — 실제 설비 모델에서: (수업 입력이 있으면) 정비 불량 예약 → 정비(펌프 복구) → 시운전 시간만큼 운전."""
    plant = Plant(time_scale=1, assets=["HYD-02"])
    plant.tick(60)
    if defect:
        plant.inject("HYD-02", SB.B_POOR_MAINTENANCE["fault"]["type"])
        plant.tick(60)
        assert plant.tags("HYD-02")["PS1"] > 178 and plant.tags("HYD-02")["FS1"] > 8.8      # 예약만으로는 설비 값이 바뀌지 않는다
    plant.inject("HYD-02", "restore", component=FLOWS.B_MAPPING["tasks"]["T_do"]["config"]["component"])
    plant.tick(int(engine.iso_duration_seconds(FLOWS.PM_TEST_RUN["settle"])))
    assert plant.units["HYD-02"].ctrl.state == "RUN"
    return {k: plant.tags("HYD-02")[k] for k in ("PS1", "FS1", "VS1")}


def run_b(world, readings, window="keep", defect_left=None):
    deploy(world, "c3_pm")
    out = c2.Outside(world)
    out.tags, out.defect_left = dict(readings), dict(defect_left or {})
    rt = world["rt"]
    row = entstate.EnterpriseState().pm_status("HYD-02")["facts"]
    inst = rt.on_alert_raise(SB.build_alert("B", row, now=NOW, person=SB.who({"by": "강사"})), now=NOW)
    assert inst["proc_def_id"] == "c3_pm"
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = c2.b_decision(inc.id)
    if window != "keep":
        d["options"][0]["window"] = window
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "김보전", "role:prod-mgr", now=NOW)
    return rt, inst, inc, out, row


WAIT_S, SETTLE_S = 9 * 3600 / 1200, 15 * 60 / 20          # 예약 시각까지 9 h ÷ (20배속 × 수업 압축 60) · 시운전 15분 ÷ 20배속


def test_b_orders_notifies_waits_for_the_booked_time_maintains_test_runs_and_renews_the_next_maintenance(world):
    rt, inst, inc, out, row = run_b(world, pm_readings(defect=False))
    assert [c["code"] for c in out.calls] == ["WO_CREATE"] and out.calls[0]["window"] == row["night_window_id"]
    assert out.mails[0][2]["to"] == "production@hyd.local" and "WO-1" in out.mails[0][2]["subject"]
    handed = events(rt, inst, "WORK_ORDER_REGISTERED")[0]["data"]["handed_over"]
    assert handed["정비 오더"] == "WO-1" and handed["예약 시각"] == engine.now_iso(NOW + timedelta(hours=9))
    wait = _row(rt, inst, "T_wait")
    assert wait["status"] == "SUBMITTED" and wait["draft"]["wait"]["real_s"] == pytest.approx(WAIT_S) and wait["due_date"]
    rt.reconcile_services(now=NOW + timedelta(seconds=WAIT_S - 2))
    assert _row(rt, inst, "T_wait")["status"] == "SUBMITTED" and out.restores == []        # 예약 시각 전 — 기다리는 작업이 남아 있다
    rt.reconcile_services(now=NOW + timedelta(seconds=WAIT_S + 1))
    assert out.restores == [("HYD-02", "pump")] and [c["code"] for c in out.calls] == ["WO_CREATE", "WO_COMPLETE"]
    run = _row(rt, inst, "T_run")
    assert run["status"] == "SUBMITTED" and run["draft"]["settle"]["real_s"] == SETTLE_S
    rt.reconcile_services(now=NOW + timedelta(seconds=WAIT_S + SETTLE_S + 2))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert (done["status"], done["end_event"], v["passed"]) == ("COMPLETED", "E_ok", True) and out.calls[-1]["code"] == "PM_RESET"
    assert {r["tag"]: (r["limit"], r["ok"]) for r in v["test_run"]["readings"]} == {"PS1": (178.0, True), "FS1": (8.8, True), "VS1": (1.2, True)}
    rep = v["result_report"]
    assert rep["outcome"] == "정상" and "다음 정비 시점 갱신" in rep["summary"] and "계수기 리셋" in rep["summary"]
    vals = {r["name"]: r for r in rep["values"]}
    assert vals["다음 정비 시점"]["ok"] is True and vals["정비 오더"]["value"] == "WO-1" and vals["압력 (PS1)"]["limit"] == "≥ 178 bar"
    seen = jobs(rt, inst)
    for job in ("WORK_ORDER_REGISTERED", "WAIT_STARTED", "WAIT_ENDED", "MAINTENANCE_DONE", "TEST_RUN_STARTED", "TEST_RUN", "PM_COUNTER_RESET",
                "RESULT_REPORT"):
        assert job in seen, job
    assert seen.index("WAIT_ENDED") < seen.index("MAINTENANCE_DONE") < seen.index("TEST_RUN") < seen.index("PM_COUNTER_RESET")


def test_b_poor_maintenance_fails_the_test_run_and_keeps_the_next_maintenance_point(world):
    """시운전 미달의 원인 쪽 입력: 정비 불량(잔류 누설)이 남은 설비의 실제 값이 PM-2.9 기준에 못 미친다. 경보선(165 bar · 8.0 l/min)보다는
    높아 새 경보는 나지 않는다."""
    readings = pm_readings(defect=True)
    assert 165.0 < readings["PS1"] < 178.0 and 8.0 < readings["FS1"] < 8.8
    rt, inst, inc, out, _ = run_b(world, readings, defect_left={"leak": thermal.RESIDUAL_LEAK})
    rt.reconcile_services(now=NOW + timedelta(seconds=WAIT_S + 1))
    rt.reconcile_services(now=NOW + timedelta(seconds=WAIT_S + SETTLE_S + 2))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert (done["status"], done["end_event"], v["passed"]) == ("COMPLETED", "E_fail", False)
    assert "PM_RESET" not in [c["code"] for c in out.calls]                       # 다음 정비 시점을 갱신하지 않는다
    rep = v["result_report"]
    assert (rep["outcome"], rep["level"]) == ("미달", "fail") and "갱신하지 않았습니다" in rep["summary"] and "WO-1" in rep["summary"]
    vals = {r["name"]: r for r in rep["values"]}
    assert vals["압력 (PS1)"]["ok"] is False and vals["유량 (FS1)"]["ok"] is False and vals["진동 (VS1)"]["ok"] is True
    assert vals["다음 정비 시점"] == {"name": "다음 정비 시점", "value": "갱신하지 않음 (시운전 미달)", "ok": False}
    kept = events(rt, inst, "PM_COUNTER_KEPT")[0]["data"]
    assert [r["tag"] for r in kept["failed"]] == ["PS1", "FS1"] and "PM_COUNTER_RESET" not in jobs(rt, inst)
    done_row = events(rt, inst, "MAINTENANCE_DONE")[0]["data"]
    assert done_row["simulator"]["defect_left"] == {"leak": thermal.RESIDUAL_LEAK} and "정비 불량" in done_row["content"]


def test_b_immediate_card_has_no_booked_time_so_the_wait_is_recorded_as_skipped(world):
    rt, inst, inc, out, _ = run_b(world, pm_readings(defect=False), window={"immediate": True, "name": "즉시 (지금 정지하고 시행)", "label": "즉시"})
    assert out.restores == [("HYD-02", "pump")]                                   # 예약 시각 대기 없이 바로 정비
    assert _row(rt, inst, "T_wait")["output"]["waited"]["immediate"] is True
    seen = jobs(rt, inst)
    assert "WAIT_SKIPPED" in seen and "WAIT_STARTED" not in seen and "WAIT_ENDED" not in seen


# ================================================================ 예비품 구매: 정상 입고 · 납기 초과
LEAD_S, DEADLINE_S = 5 * 86400 / 1200, 6 * 86400 / 1200            # 리드타임 5일 · 납기 기한 6일 ÷ (20배속 × 수업 압축 60)


def open_c(world):
    deploy(world, "c3_spare")
    out = c2.Outside(world)
    rt = world["rt"]
    row = entstate.EnterpriseState().spare_stock("P-PMP-SEAL")["facts"]
    inst = rt.on_alert_raise(SB.build_alert("C", row, now=NOW), now=NOW)
    assert inst["proc_def_id"] == "c3_spare"
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = c2.c_decision(inc.id)
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    return rt, inst, inc, d, out


def approve_c(rt, inst, d):
    return rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "정구매", "role:prod-mgr", now=NOW)


def test_c_order_hands_its_number_item_quantity_and_due_date_to_the_mail_and_the_waiting_receipt(world):
    rt, inst, inc, d, out = open_c(world)
    assert out.calls == [] and out.mails == []                                    # 승인 전에는 발주도 메일도 없다
    approve_c(rt, inst, d)
    assert [c["code"] for c in out.calls] == ["PR_CREATE"]
    expected_at = engine.now_iso(NOW + timedelta(days=5))
    handed = events(rt, inst, "PURCHASE_ORDERED")[0]["data"]["handed_over"]
    assert handed == {"발주 번호": "PR-1", "품목": "P-PMP-SEAL", "수량": 6, "공급사": "sup:b", "금액(만원)": 330, "리드타임(일)": 5, "입고 예정": expected_at}
    server, tool, args, _ = out.mails[0]                                          # 메일은 발주와 따로인 task — 발주가 넘긴 값이 인자로 들어간다
    assert (server, tool) == ("hyd-effects", "send_mail") and _row(rt, inst, "T_mail")["status"] == "DONE"
    assert args["subject"] == "[발주] P-PMP-SEAL 6개 — 발주 번호 PR-1" and expected_at in args["body"] and "리드타임 5일" in args["body"]
    call = next(e for e in events(rt, inst, "MCP_EFFECT_CALL") if e["event_type"] == "tool_usage_started")["data"]
    assert call["input"]["subject"] == args["subject"]                            # 넘어간 값이 처리 기록의 도구 호출 입력에 그대로 보인다
    gr = _row(rt, inst, "T_gr")                                                   # 외부 결과를 기다리는 작업이 실제로 남는다
    assert gr["status"] == "SUBMITTED" and gr["draft"]["wait"]["real_s"] == pytest.approx(LEAD_S) and gr["due_date"]
    waiting = events(rt, inst, "RECEIPT_WAIT")[0]["data"]
    assert waiting["expecting"] == {"발주 번호": "PR-1", "품목": "P-PMP-SEAL", "수량": 6, "리드타임(일)": 5, "입고 예정": expected_at}
    assert _row(rt, inst, "B_late")["due_date"] == engine.now_iso(NOW + timedelta(seconds=DEADLINE_S))
    assert rt.repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING" and inc.state == "AWAITING_APPROVAL"
    rt.reconcile_services(now=NOW + timedelta(seconds=LEAD_S - 5))
    assert _row(rt, inst, "T_gr")["status"] == "SUBMITTED" and [c["code"] for c in out.calls] == ["PR_CREATE"]


def test_c_receipt_that_matches_the_order_completes_the_purchase(world):
    rt, inst, inc, d, out = open_c(world)
    approve_c(rt, inst, d)
    rt.reconcile_services(now=NOW + timedelta(seconds=LEAD_S + 1))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert (done["status"], done["end_event"], v["received"], inc.state) == ("COMPLETED", "E_ok", True, "CLOSED")
    assert [c["code"] for c in out.calls] == ["PR_CREATE", "GR_CONFIRM"] and _row(rt, inst, "B_late")["status"] == "CANCELLED"
    match = v["goods_receipt"]["match"]
    assert match["ok"] is True and [(r["name"], r["ordered"], r["received"]) for r in match["rows"]] == [
        ("발주 번호", "PR-1", "PR-1"), ("품목", "P-PMP-SEAL", "P-PMP-SEAL"), ("수량", 6, 6)]
    rep = v["result_report"]
    assert rep["outcome"] == "입고 완료" and "발주 PR-1 와 일치" in rep["summary"]
    assert {r["name"]: r["value"] for r in rep["values"]}["입고 기록 ↔ 발주"] == "일치"
    seen = jobs(rt, inst)
    assert seen.index("RECEIPT_WAIT") < seen.index("RECEIPT_MATCH") < seen.index("GOODS_RECEIVED") < seen.index("RESULT_REPORT")


def test_c_supplier_delay_lets_the_deadline_pass_and_ends_as_a_delay_without_a_receipt(world):
    """납기 초과의 원인 쪽 입력: 공급사 납기 지연 통보(ERP 발주의 입고 예정이 늦어짐). 입고 대기가 늦어진 예정을 다시 읽어 더 기다리고,
    납기 기한 타이머가 먼저 울려 지연 결과로 닫힌다 — 입고는 기록하지 않는다."""
    rt, inst, inc, d, out = open_c(world)
    approve_c(rt, inst, d)
    out.delay_d = SB.default_delay_days(rt, inst, {"after": {"lead_d": 5, "delay_d": 0}})
    assert out.delay_d == 2                                                       # 기한 6일을 넘기는 가장 작은 지연(리드타임 5일 + 2일)
    rt.reconcile_services(now=NOW + timedelta(seconds=LEAD_S + 1))               # 원래 입고 예정 — 늦어진 예정을 읽고 더 기다린다
    gr = _row(rt, inst, "T_gr")
    assert gr["status"] == "SUBMITTED" and gr["draft"]["wait"]["delay_d"] == 2 and "RECEIPT_DELAYED" in jobs(rt, inst)
    rt.fire_timeouts(now=NOW + timedelta(seconds=DEADLINE_S + 1))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert (done["status"], done["end_event"]) == ("COMPLETED", "E_late") and _row(rt, inst, "T_gr")["status"] == "CANCELLED"
    assert [c["code"] for c in out.calls] == ["PR_CREATE"] and "goods_receipt" not in v and inc.state == "ESCALATED"
    rep = v["result_report"]
    assert (rep["outcome"], rep["level"]) == ("지연", "fail") and "PR-1" in rep["summary"]
    vals = {r["name"]: r for r in rep["values"]}
    assert vals["발주 번호"]["value"] == "PR-1" and vals["입고"] == {"name": "입고", "value": "기한 안에 확인되지 않음", "ok": False}


def test_c_receipt_that_differs_from_the_order_does_not_complete_the_purchase(world):
    """입고 기록이 발주와 어긋나면(수량 5 ≠ 발주 6) 구매 완료로 넘기지 않는다 — 입고 task 가 사유와 함께 멈춘다."""
    rt, inst, inc, d, out = open_c(world)
    approve_c(rt, inst, d)
    out.received = {"qty": 5}
    for i in range(I.MAX_RETRIES):
        rt.reconcile_services(now=NOW + timedelta(seconds=LEAD_S + 1 + i))
        rt.poll_once(now=NOW + timedelta(seconds=LEAD_S + 1 + i))
    w = _row(rt, inst, "T_gr")
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert w["status"] == "PENDING" and "수량 발주 6 / 입고 5 불일치" in w["log"] and done["status"] == "RUNNING"
    assert "result_report" not in engine.variables(done) and "received" not in engine.variables(done)


def test_receipt_match_never_counts_a_missing_field_as_a_match():
    values = {"approved_part_no": "P-PMP-SEAL", "approved_qty": 6}
    ok = effect_parts.receipt_match("PR-1", values, {"after": {"pr_id": "PR-1", "part_no": "P-PMP-SEAL", "qty": 6}})
    assert ok["ok"] is True and "일치" in ok["text"]
    assert effect_parts.receipt_match("PR-1", values, {"ref": "GR-1"})["ok"] is False                    # 입고 행이 없다
    assert effect_parts.receipt_match("PR-1", values, {"after": {"pr_id": "PR-2", "part_no": "P-PMP-SEAL", "qty": 6}})["ok"] is False
    assert effect_parts.receipt_match("PR-1", {"approved_qty": 6}, {"after": {"pr_id": "PR-1", "qty": 6}})["ok"] is False   # 승인 값도 입고 값도 없는 칸


def test_goods_receipt_no_longer_takes_an_immediate_setting():
    act = effect_parts.activity_for("svc:goods-receipt", {"id": "T_gr"}, {"immediate": True}, [], None)
    with pytest.raises(ValueError, match="모르는 설정 칸 immediate"):
        effect_parts.validate(act)


# ================================================================ 수업 입력 (원인 쪽) — 설비 모델 · API
def test_stuck_fan_changes_nothing_until_the_fan_is_asked_to_speed_up():
    normal, stuck = stuck_fan_unit(False), stuck_fan_unit(True)
    assert stuck.units["HYD-01"].state.ts1 == pytest.approx(normal.units["HYD-01"].state.ts1)          # 경보까지 같은 물리
    assert stuck.units["HYD-01"].state.fan_limit == thermal.STUCK_FAN_LIMIT == 60.0
    assert stuck.status("HYD-01")["injection"]["id"] == "PRESS-1" and stuck.snapshot()["units"]["HYD-01"]["disturbances"]["fan_limit"] == 60.0
    stuck.command("HYD-01", {"cmdId": "C-9", "writes": [{"res": "FanSpeedSP", "v": 100}, {"res": "LoadSP", "v": 80}]}, source="HITL")
    for fault in SB.A_BUTTONS["restore"]["faults"]:                # [쿨러 복구]: 쿨러 · 팬 구동부 정상 + 조치로 바뀐 지령을 평소 운전점으로
        stuck.inject("HYD-01", fault["type"], component=fault.get("component"), ramp_sim_s=1 if fault["type"] == "restore" else None)
    stuck.tick(5)
    state = stuck.units["HYD-01"].state
    assert (state.cooler_health, state.fan_limit, state.fan_pct, state.load_pct) == (1.0, thermal.FAN_LIMIT_HEALTHY, 60.0, 90.0)
    stuck.tick(6000)                                               # 평소 운전점이라 다음 열화 주입이 다시 경보를 낸다(팬 100 % 로 남으면 55 ℃ 를 넘지 못한다)
    stuck.inject("HYD-01", "cooler_degradation", severity=SB.A_SEVERITY)
    stuck.tick(6000)
    assert stuck.units["HYD-01"].state.ts1 > 55.0


def test_maintenance_defect_is_used_up_by_the_one_maintenance_that_covers_it():
    plant = Plant(time_scale=1, assets=["HYD-02"])
    armed = plant.inject("HYD-02", "maintenance_defect")
    assert armed["maintenance_defect_armed"] == {"leak": thermal.RESIDUAL_LEAK} and armed["targets"] == {}
    assert plant.status("HYD-02")["maintenance_defect"] == {"leak": thermal.RESIDUAL_LEAK} and plant.units["HYD-02"].state.leak == 0.0
    other = plant.inject("HYD-02", "restore", component="cooler")                  # 다른 부품의 정비는 이 불량과 무관하다
    assert other["maintenance_defect_left"] == {} and plant.units["HYD-02"].maintenance_defect
    done = plant.inject("HYD-02", "restore", component="pump", ramp_sim_s=1)
    assert done["maintenance_defect_left"] == {"leak": thermal.RESIDUAL_LEAK} and done["maintenance_defect_armed"] == {}
    plant.tick(5)
    assert plant.units["HYD-02"].state.leak == thermal.RESIDUAL_LEAK
    again = plant.inject("HYD-02", "restore", component="pump", ramp_sim_s=1)      # 다음 정비는 제대로 된다
    plant.tick(5)
    assert again["maintenance_defect_left"] == {} and plant.units["HYD-02"].state.leak == 0.0
    plant.inject("HYD-02", "maintenance_defect")
    for fault in SB.B_PLANT_RESET:                                                # B [초기화]: 예약을 풀고 정상으로
        plant.inject("HYD-02", fault["type"], fault.get("target"), ramp_sim_s=1)
    plant.tick(5)
    assert plant.units["HYD-02"].maintenance_defect == {} and plant.units["HYD-02"].state.leak == 0.0
    with pytest.raises(ValueError, match="residual"):
        plant.inject("HYD-02", "maintenance_defect", 1.5)


def test_class_inputs_are_listed_for_the_portal_and_name_real_endpoints():
    from procsvc import main
    paths = {r.path for r in main.app.routes}
    listed = SB.status(lambda name, params: {"facts": None})["class_inputs"]
    assert [(i["scenario"], i["outcome"]) for i in listed] == [("A", "조치 미달"), ("B", "시운전 미달"), ("C", "납기 초과")]
    for item in listed:
        assert item["path"] in paths or item["path"].replace("/A/degrade-stuck-fan", "/A/{act}") in paths, item["path"]
        assert item["button"] and item["when"]


@pytest.fixture
def api(world, monkeypatch):
    """process main 의 수업 입력 API 를 실제 런타임 위에서 부른다. 시뮬레이터로 나가는 요청은 기록하고, 설비 요청은 실제 설비 모델이 받는다."""
    from procsvc import main
    deploy(world, "c3_pm")
    deploy(world, "c3_spare")
    rt, st = world["rt"], entstate.EnterpriseState()
    plant = Plant(time_scale=1, assets=["HYD-01", "HYD-02", "HYD-03"])
    sent = {"plant": [], "ent": [], "audit": []}

    def plant_post(path, body):
        sent["plant"].append(body)
        body = dict(body)
        out = plant.inject(body.pop("asset"), body.pop("type"), body.pop("target", None), **body)
        main.plant_status[out["asset"]] = plant.status(out["asset"])
        return out

    def ent_post(path, body):
        sent["ent"].append((path, body))
        return {"id": "TX-1", "ref": body.get("params", {}).get("ref"), "detail": f"발주 {body['params']['ref']} 납기 {body['params']['days']:g}일 지연 통보"} \
            if path == "/api/exec" else {"ok": True}

    read = lambda name, params: {"pm_status": lambda: st.pm_status(params.get("asset")), "spare_stock": lambda: st.spare_stock(params.get("part"))}[name]()
    monkeypatch.setattr(main, "PROCESS_MODE", "instance")
    monkeypatch.setattr(main.instance_mode, "current", lambda: rt)
    monkeypatch.setattr(main.instance_mode, "enterprise_read", read)
    monkeypatch.setattr(main, "_plant_post", plant_post)
    monkeypatch.setattr(main, "_entsim_post", ent_post)
    monkeypatch.setattr(main, "_scenario_route", lambda p: {"PM_DUE": "c3_pm", "SPARE_BELOW_MIN": "c3_spare"}[p])
    monkeypatch.setattr(main, "_audit", lambda asset, actor, event, detail, **k: sent["audit"].append({"asset": asset, "event": event, "detail": detail}))
    monkeypatch.setattr(main, "_last_press", lambda asset, button=None: next(
        ({k: a["detail"].get(k) for k in ("button", "by", "at", "instance")} for a in reversed(sent["audit"])
         if a["asset"] == asset and button in (None, a["detail"].get("button"))), None))
    monkeypatch.setattr(main, "plant_status", {})

    async def admit(alert):
        rt.on_alert_raise(alert, now=NOW)
    monkeypatch.setattr(main, "_admit_human_alert", admit)
    return {"main": main, "rt": rt, "plant": plant, "sent": sent, "world": world}


def test_poor_maintenance_pressed_before_the_case_is_carried_into_the_case_record(api):
    main, rt, plant = api["main"], api["rt"], api["plant"]
    res = asyncio.run(main.scenario_b_poor_maintenance({"by": "강사"}))
    assert res["class_input"] == "시운전 미달" and res["instance"] is None and "내부 누설 0.05" in res["cause"]
    assert plant.units["HYD-02"].maintenance_defect == {"leak": thermal.RESIDUAL_LEAK} and plant.units["HYD-02"].state.leak == 0.0
    started = asyncio.run(main.scenario_start("B", {"by": "강사"}))
    rows = [e["data"] for e in rt.repo.list_events(proc_inst_id=started["instance"]) if e["data"].get("class_input")]
    assert len(rows) == 1 and rows[0]["name"] == "수업 입력 [정비 불량 예약]" and rows[0]["armed_before_case"] is True
    assert "결과 값을 넣지 않고 원인만" in rows[0]["content"]
    asyncio.run(main.scenario_reset("B", {"by": "강사"}))                          # [초기화]는 설비의 예약도 푼다
    assert plant.units["HYD-02"].maintenance_defect == {} and [b["type"] for b in api["sent"]["plant"][-2:]] == ["maintenance_defect", "restore"]


def test_poor_maintenance_pressed_while_the_case_waits_is_recorded_on_it_and_refused_after_the_maintenance(api):
    main, rt = api["main"], api["rt"]
    started = asyncio.run(main.scenario_start("B", {"by": "강사"}))
    res = asyncio.run(main.scenario_b_poor_maintenance({"by": "강사"}))
    assert res["instance"] == started["instance"]
    rows = [e["data"] for e in rt.repo.list_events(proc_inst_id=started["instance"]) if e["data"].get("class_input")]
    assert len(rows) == 1 and rows[0]["by"] == "강사" and rows[0]["cause"].startswith("설비 시뮬레이터")
    inst = rt.repo.get_instance(started["instance"])
    engine.set_variables(rt.definition_for(inst), inst, {"maintenance": {"done_at": "x"}})
    rt.repo.update_instance(inst)
    with pytest.raises(HTTPException) as e:                                      # 정비가 끝난 뒤의 예약은 이번 처리 건에 듣지 않는다
        asyncio.run(main.scenario_b_poor_maintenance({"by": "강사"}))
    assert e.value.status_code == 409 and "정비가 이미 끝났습니다" in e.value.detail


def test_delay_delivery_needs_an_open_order_and_tells_the_erp_about_that_order(api):
    main, rt, world_ = api["main"], api["rt"], api["world"]
    with pytest.raises(HTTPException) as e:
        asyncio.run(main.scenario_c_delay_delivery({"by": "강사"}))
    assert e.value.status_code == 409 and "진행 중인 예비품 구매 처리 건이 없습니다" in e.value.detail
    started = asyncio.run(main.scenario_start("C", {"by": "강사"}))
    with pytest.raises(HTTPException) as e:
        asyncio.run(main.scenario_c_delay_delivery({"by": "강사"}))
    assert e.value.status_code == 409 and "아직 발주 전" in e.value.detail
    out = c2.Outside(world_)
    inst = rt.repo.get_instance(started["instance"])
    d = c2.c_decision(engine.variables(inst)["incident"])
    world_["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    approve_c(rt, inst, d)
    with pytest.raises(HTTPException) as e:
        asyncio.run(main.scenario_c_delay_delivery({"by": "강사", "days": 0}))
    assert e.value.status_code == 400 and "days" in e.value.detail
    res = asyncio.run(main.scenario_c_delay_delivery({"by": "강사"}))
    path, body = api["sent"]["ent"][-1]
    assert path == "/api/exec" and body["skill"] == "skill:delay-delivery" and body["params"] == {"ref": "PR-1", "days": 2.0}
    assert res["purchase_order"] == "PR-1" and res["days"] == 2.0 and res["class_input"] == "납기 초과"
    row = next(e["data"] for e in rt.repo.list_events(proc_inst_id=started["instance"]) if e["data"].get("class_input"))
    assert row["name"] == "수업 입력 [공급사 납기 지연 통보]" and row["purchase_order"] == "PR-1" and "납기 2일 지연" in row["cause"]
    assert asyncio.run(main.scenario_c_delay_delivery({"by": "강사", "days": 4}))["days"] == 4.0          # 일수를 직접 줄 수도 있다
    inst = rt.repo.get_instance(started["instance"])
    engine.set_variables(rt.definition_for(inst), inst, {"goods_receipt": {"ref": "GR-1"}})
    rt.repo.update_instance(inst)
    with pytest.raises(HTTPException) as e:
        asyncio.run(main.scenario_c_delay_delivery({"by": "강사"}))
    assert e.value.status_code == 409 and "이미 입고" in e.value.detail and out.calls


def test_stuck_fan_button_sends_both_faults_under_one_press_and_marks_the_case_as_a_class_input(api):
    main, rt, plant = api["main"], api["rt"], api["plant"]
    res = asyncio.run(main.scenario_a_button("degrade-stuck-fan", {"by": "강사"}))
    sent = api["sent"]["plant"]
    assert [b["type"] for b in sent] == ["cooler_degradation", "fan_drive_fault"] and len({b["origin"]["id"] for b in sent}) == 1
    assert res["class_input"] == "조치 미달" and len(res["plant"]) == 2 and plant.status("HYD-01")["injection"]["class_input"] == "조치 미달"
    inst = rt.on_alert_raise(dict(c2.ALERT, alertId="HYD-01-A-77"), now=NOW)
    main._link_injection(inst)
    row = next(e["data"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"]) if e["job_id"] == "SCENARIO_BUTTON")
    assert row["name"] == "수업 입력 [쿨러 열화 + 팬 구동부 고장 주입]" and row["class_input"] == "조치 미달" and "팬 구동부" in row["cause"]
    assert row["injection_id"] == res["injection_id"]
    plain = asyncio.run(main.scenario_a_button("degrade", {"by": "강사"}))          # 보통 주입은 수업 입력으로 적지 않는다
    assert plain["class_input"] is None and "class_input" not in plant.status("HYD-01")["injection"]


# ================================================================ 버튼 · 초기화 · 업무 거절 (앞 판 시험에서 그대로 유효한 것)
class FakeRt:
    tenant_id = "hyd"

    def __init__(self, instances=()):
        self.repo = self
        self._inst = list(instances)

    def list_instances(self, status=None, limit=100, tenant_id=None, incident_id=None, asset=None):
        rows = [i for i in self._inst if status in (None, i.get("status")) and asset in (None, i.get("asset"))]
        return rows[:limit]


def test_buttons_show_the_alerts_refuse_when_handled_running_or_undeployed_and_reset_brings_them_back():
    st = entstate.EnterpriseState()
    read = lambda name, params: {"pm_status": lambda: st.pm_status(params.get("asset")),
                                 "spare_stock": lambda: st.spare_stock(params.get("part"))}[name]()
    s = SB.status(read, FakeRt())["scenarios"]
    assert (s["B"]["asset"], s["B"]["alert"], s["B"]["label"]) == ("HYD-02", True, "정기 정비 도래")
    assert (s["C"]["asset"], s["C"]["alert"], s["C"]["label"], s["C"]["facts"]["available"]) == ("HYD-03", True, "재고 보충 필요", 1)
    route = lambda pattern: "c3_pm" if pattern == "PM_DUE" else None
    with pytest.raises(SB.Refused, match="배포"):
        SB.prepare("C", read, FakeRt(), route)                                     # C 흐름이 배포되지 않음
    running = {"proc_inst_id": "c3_pm.1", "status": "RUNNING", "start_event_id": "CMMS-PM_DUE-HYD-02-20261009010101", "asset": "HYD-02"}
    with pytest.raises(SB.Refused, match="진행 중"):
        SB.prepare("B", read, FakeRt([running]), route)
    s = SB.status(read, FakeRt([running]))["scenarios"]
    assert s["B"]["running"]["instance"] == "c3_pm.1" and s["C"]["running"] is None
    prep = SB.prepare("B", read, FakeRt(), route)
    assert prep["alert"]["pattern"] == "PM_DUE" and prep["alert"]["evidence"]["hours_since_pm"] == 1950
    assert prep["alert"]["evidence"]["trigger"].endswith("[정기 정비] 버튼")
    st.execute({"decision": "D-B", "skill": "skill:schedule-maintenance", "asset": "HYD-02",
                "params": {"task": "정기 점검", "window_id": st.pm_status("HYD-02")["facts"]["night_window_id"]}})
    assert SB.status(read)["scenarios"]["B"]["alert"] is False                     # 정비 오더가 잡힘 → 표시 꺼짐
    with pytest.raises(SB.Refused, match="이미 처리"):
        SB.prepare("B", read, FakeRt(), route)
    st.reset_pm_counters()
    assert SB.status(read)["scenarios"]["B"]["alert"] is True                      # [초기화] → 다시 켜짐
    with pytest.raises(KeyError):
        SB.prepare("A", read, FakeRt(), route)


def test_the_button_presser_and_time_are_recorded_on_the_case_itself(world):
    """누가 · 언제 눌렀나 — 업무 DB 원장만이 아니라 처리 건 자체(시작 경보 근거 + SCENARIO_BUTTON 기록)에 남는다."""
    deploy(world, "c3_pm")
    rt = world["rt"]
    person = SB.who({"by": "박정비", "user_id": "user:park-maint", "roles": ["role:maint-mgr"]})
    alert = SB.build_alert("B", entstate.EnterpriseState().pm_status("HYD-02")["facts"], now=NOW, person=person)
    ev = alert["evidence"]
    assert (ev["requested_by"], ev["requested_user"], ev["requested_roles"]) == ("박정비", "user:park-maint", ["role:maint-mgr"]) and ev["requested_at"]
    rt.on_alert_raise(alert, now=NOW)
    out = SB.started(rt, "B", alert, "c3_pm", person)
    rows = [e for e in rt.repo.list_events(proc_inst_id=out["instance"]) if e["job_id"] == "SCENARIO_BUTTON"]
    assert len(rows) == 1 and rows[0]["data"]["by"] == "박정비" and rows[0]["data"]["at"] == ev["requested_at"] and rows[0]["data"]["button"] == "정기 정비"
    assert engine.variables(rt.repo.get_instance(out["instance"]))["alert"]["evidence"]["requested_by"] == "박정비"
    assert SB.who({})["by"] == "나 미선택"                                         # 고르지 않았으면 지어내지 않는다


def test_b_notice_mail_names_the_approver_by_name_not_by_user_id(world):
    """공지 메일 본문은 서버가 사용자 표에서 찾은 이름(approved_by_name)을 쓴다 — 받는 사람에게 가는 글에 사용자 id 를 내지 않는다."""
    deploy(world, "c3_pm")
    out = c2.Outside(world)
    rt = world["rt"]
    rt.repo.upsert_user({"id": "user:park-maint", "username": "박정비", "is_agent": False, "tenant_id": "hyd"})
    rt.repo.set_role_member("hyd", "role:prod-mgr", "user:park-maint", True)
    row = entstate.EnterpriseState().pm_status("HYD-02")["facts"]
    inst = rt.on_alert_raise(SB.build_alert("B", row, now=NOW, person=SB.who({"by": "박정비", "user_id": "user:park-maint"})), now=NOW)
    d = c2.b_decision(engine.variables(inst)["incident"])
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "user:park-maint", "role:prod-mgr", now=NOW)
    v = engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))
    assert (v["approved_by"], v["approved_by_name"]) == ("user:park-maint", "박정비")      # id 는 권한 · 감사, 이름은 사람이 읽는 글
    body = out.mails[0][2]["body"]
    assert body.endswith("(승인 박정비)") and "user:" not in body
    for did, (_, _, m) in FLOWS.FLOWS.items():                                   # 틀 자체에도 id 변수를 쓰지 않는다
        texts = [str(t.get("config")) for t in m["tasks"].values()]
        assert not [t for t in texts if "{approved_by}" in t], did


def test_an_approver_id_without_a_name_in_the_user_table_fails_loudly(world):
    deploy(world, "c3_pm")
    c2.Outside(world)
    rt = world["rt"]
    rt.repo.upsert_user({"id": "user:nameless", "username": "", "is_agent": False, "tenant_id": "hyd"})
    rt.repo.set_role_member("hyd", "role:prod-mgr", "user:nameless", True)
    inst = rt.on_alert_raise(SB.build_alert("B", entstate.EnterpriseState().pm_status("HYD-02")["facts"], now=NOW), now=NOW)
    d = c2.b_decision(engine.variables(inst)["incident"])
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    with pytest.raises(LookupError, match="user:nameless"):
        rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "user:nameless", "role:prod-mgr", now=NOW)


@pytest.mark.parametrize("did,agent", [("c3_pm", "agent:pm-plan"), ("c3_spare", "agent:spare-buy")])
def test_the_scenario_agent_chosen_in_the_flow_is_the_task_performer(world, did, agent):
    """흐름 가져오기에서 고른 시나리오 에이전트가 판단 task 의 담당자(user_id)다 — 워커는 담당자 프로필의 SKILL · MCP 서버로 돈다."""
    deploy(world, did)
    rt = world["rt"]
    st = entstate.EnterpriseState()
    row = st.pm_status("HYD-02")["facts"] if did == "c3_pm" else st.spare_stock("P-PMP-SEAL")["facts"]
    inst = rt.on_alert_raise(SB.build_alert("B" if did == "c3_pm" else "C", row, now=NOW), now=NOW)
    t = _row(rt, inst, "T_agent")
    assert t["user_id"] == agent and t["assignees"][0]["endpoint"] == agent


class Refusing(c2.Outside):
    """업무 시스템이 승인된 거래를 거절한다(예: 그 사이 공급사가 승인 목록에서 빠짐 · 정비 시간이 지나감)."""
    def __init__(self, world, code):
        super().__init__(world)
        self.refuse = code

    def exec_skill(self, d, item):
        if item["code"] == self.refuse:
            self.calls.append(deepcopy(item))
            return {"ok": False, "code": item["code"], "error": f"INVALID: {item['code']} refused by the business system"}
        return super().exec_skill(d, item)


@pytest.mark.parametrize("did,code,task", [("c3_pm", "WO_CREATE", "T_wo"), ("c3_spare", "PR_CREATE", "T_po")])
def test_a_business_refusal_stops_the_case_loudly_and_the_alert_stays_on(world, did, code, task):
    """비해피 가지: 승인 뒤 업무 시스템이 거래를 거절하면 처리 건은 끝나지 않는다 — 재시도 3회 뒤 PENDING · 사유 보존, 결과 보고 없음
    (성공한 척하지 않는다). 표시를 끄는 업무 변화(오더 · 입고)가 없으니 '정기 정비 도래' · '재고 보충 필요'는 그대로다."""
    deploy(world, did)
    out = Refusing(world, code)
    rt = world["rt"]
    st = entstate.EnterpriseState()
    key = "B" if did == "c3_pm" else "C"
    row = st.pm_status("HYD-02")["facts"] if key == "B" else st.spare_stock("P-PMP-SEAL")["facts"]
    inst = rt.on_alert_raise(SB.build_alert(key, row, now=NOW), now=NOW)
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = c2.b_decision(inc.id) if key == "B" else c2.c_decision(inc.id)
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "승인자", "role:prod-mgr", now=NOW)
    for i in range(I.MAX_RETRIES):
        rt.poll_once(now=NOW + timedelta(seconds=10 * (i + 1)))
    w = _row(rt, inst, task)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert w["status"] == "PENDING" and "refused by the business system" in w["log"] and done["status"] == "RUNNING"
    assert "result_report" not in engine.variables(done)
    errors = [e for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"]) if e["job_id"] == "TASK_ERROR"]
    assert errors and errors[-1]["data"]["service_result"]["error"].startswith("INVALID")
    assert out.calls[-1]["code"] == code and not [c for c in out.calls if c["code"] == "GR_CONFIRM"] and out.mails == []


def test_injection_origin_carries_the_press_and_finds_its_case(world):
    """A: 누름 id 가 설비 주입에 실리고, 그 id 로 연결된 처리 건을 시간 창 없이 찾는다."""
    rt = world["rt"]
    person = SB.who({"by": "김운전", "user_id": "user:kim-op", "roles": ["role:operator"]})
    origin = SB.injection_origin("쿨러 열화 주입", person)
    assert origin["id"].startswith("PRESS-") and origin["by"] == "김운전" and origin["button"] == "쿨러 열화 주입" and origin["at"]
    inst = rt.on_alert_raise(dict(c2.ALERT, alertId="HYD-01-A-9"), now=NOW)
    injected = dict(origin, at=NOW.isoformat())                                 # 주입은 처리 건보다 먼저(NOW)
    assert SB.case_of_injection(rt, "HYD-01", injected) is None
    rt.repo.record_events([SB.press_event(inst["proc_inst_id"], origin["button"], "HYD-01", origin, origin["at"], {"injection_id": origin["id"]})])
    assert SB.case_of_injection(rt, "HYD-01", injected) == inst["proc_inst_id"]
    assert SB.case_of_injection(rt, "HYD-01", dict(injected, id="PRESS-other")) is None
    assert SB.A_BUTTONS["degrade"]["faults"] == [{"type": "cooler_degradation", "severity": SB.A_SEVERITY}]


def test_the_lesson_reset_keeps_executions_in_the_archive_and_reanchors_times():
    """업무 초기화(/api/reset)는 운영 상태만 시작값으로 되돌리고, 끝난 처리 건이 가리키는 작업지시 · 발주 · 원장은 보관한다(지우지 않음)."""
    from fastapi.testclient import TestClient
    from entsim import main as entmain
    entmain.ent.st.reset()
    client = TestClient(entmain.app)
    wo = client.post("/api/exec", json={"skill": "skill:schedule-maintenance", "decision": "D-ARC", "asset": "HYD-02",
                                        "params": {"task": "정기 점검"}}).json()
    assert client.get("/api/archive", params={"ref": wo["ref"]}).json()["records"] == []
    assert client.post("/api/reset").json() == {"ok": True}
    assert client.get("/api/transactions").json() == []                           # 운영 상태는 시작값
    kept = client.get("/api/archive", params={"ref": wo["ref"]}).json()["records"]
    assert {r["table"] for r in kept} == {"work_orders", "transactions"} and len({r["reset_no"] for r in kept}) == 1
    assert client.get("/api/archive", params={"ref": "D-ARC"}).json()["records"]     # 판단 id 로도 따라간다
    assert client.post("/api/reanchor").json() == {"ok": True}
    entmain.ent.st.reset()


def test_a_missing_stock_row_after_receipt_fails_the_task_loudly(world):
    """입고 뒤 재고를 읽지 못하면 결과 보고를 지어내지 않는다 — 입고 task 가 사유와 함께 실패(재시도 · PENDING)."""
    rt, inst, inc, d, out = open_c(world)
    out.read = lambda name, params: {"facts": None} if name == "spare_stock" else c2.Outside.read(out, name, params)
    rt.hooks.enterprise_read = out.read
    approve_c(rt, inst, d)
    rt.reconcile_services(now=NOW + timedelta(seconds=LEAD_S + 1))
    w = _row(rt, inst, "T_gr")
    assert w["status"] == "SUBMITTED" and "ERP 재고에 P-PMP-SEAL 행이 없습니다" in w["log"]
    assert "result_report" not in engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))
