"""승인 단계는 세 시나리오가 같다 (사용자 결정 2026-10-10) — scripts/c3_flows.py 의 실제 정의를 실제 런타임(MemoryRepo · 실제 Incident)으로.

  승인    → 처리되고 끝난다(A: 냉각 명령 → 재관측, B: 정비 오더 · 공지, C: 발주 · 입고)
  거절    → 설비 명령 · 업무 처리 0건, 결과 보고(반려) → 거절 종결, 사건 '운전원 거부'. B · C 의 업무 표시는 처리되지 않았으므로 켜진 채다
  무응답  → 그 단계에서 그대로 기다린다. 기한이 지나면 멈추지 않는 '승인 지연' 타이머가 알림만 낸다(자동 취소 · 자동 거절 없음)

그 밖에: 거절 권한 · 사유 · 두 번 거절 · 거절 값을 내지 않는 흐름, 흐름 사전 검사(반려 경로가 효과에 닿음 · 반려 경로가 사건을 연 채 끝남 ·
두 승인 부품 섞기), HTTP 경로."""
from copy import deepcopy
from datetime import timedelta

import pytest

from entsim import state as entstate
from procsvc import bpmn_import as B, engine, machine, scenario_buttons as SB
from test_instance_mode import world, NOW, _row, NoFx  # noqa: F401  (world 는 fixture)
import test_c2_execution as c2
import test_c3_assembly as c3

FLOWS = c3._flows()
MGR = ("이생산", "role:prod-mgr")          # 시험 판단의 카드 승인자(등급 2)
OVERDUE_S = 600 / 20                       # 승인 지연 기한 PT10M ÷ 20배속(사람 응답 타이머는 배속만)


def catalog(world):
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    return B.catalog(base, c3.AGENTS)


def checked(world, did, source=None, mapping=None):
    _, src, m = FLOWS.FLOWS[did]
    return B.check(B.parse_bpmn(source or src), deepcopy(mapping or m), {"catalog": catalog(world), "definition_id": did, "version": "1",
                                                                         "file_name": f"{did}.bpmn", "xml_sha256": "x"})


def opened(world, did):
    """흐름을 배포하고 처리 건을 열어 에이전트 판단까지 끝낸다 → 승인 대기. (rt, 처리 건, 사건, 판단, 업무 대역)"""
    r = checked(world, did)
    assert r["ok"], r["problems"]
    rt = world["rt"]
    rt.register_definition(r["definition"])
    rt.deploy_definition(did, "1", "tester", "승인 단계 시험")
    out = c2.Outside(world)
    st = entstate.EnterpriseState()
    alert = {"c3_cooling": lambda: dict(c2.ALERT, alertId="HYD-01-A-1"),
             "c3_pm": lambda: SB.build_alert("B", st.pm_status("HYD-02")["facts"], now=NOW),
             "c3_spare": lambda: SB.build_alert("C", st.spare_stock("P-PMP-SEAL")["facts"], now=NOW)}[did]()
    inst = rt.on_alert_raise(alert, now=NOW)
    assert inst["proc_def_id"] == did
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = {"c3_cooling": c2.a_decision, "c3_pm": c2.b_decision, "c3_spare": c2.c_decision}[did](inc.id)
    world["book"][d["id"]] = d
    output = {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}
    if did == "c3_cooling":
        output.update(cause="cause:cooler-fin-fouling", failure_mode="fm:cooling-loss", guide_card=c2.GUIDE)
    rt.submit(_row(rt, inst, "T_agent")["id"], output, now=NOW)
    return rt, inst, inc, d, out


def approve(rt, inst, d):
    return rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], *MGR, now=NOW)


def jobs(rt, inst):
    return [e["job_id"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])]


THREE = ["c3_cooling", "c3_pm", "c3_spare"]
EFFECT_TASKS = {"c3_cooling": ("T_cmd", "T_reobs", "T_wo"), "c3_pm": ("T_wo",), "c3_spare": ("T_po", "T_gr")}


# ================================================================ 승인 → 처리되고 끝난다
@pytest.mark.parametrize("did", THREE)
def test_approval_carries_the_approval_value_and_the_case_is_processed_to_its_normal_end(world, did):
    rt, inst, inc, d, out = opened(world, did)
    assert out.calls == [] and out.mails == [] and inc.cmd_id is None             # 승인 전에는 설비 명령도 업무 처리도 없다
    approve(rt, inst, d)
    assert _row(rt, inst, "T_approve")["output"]["approval"] == "승인"
    if did == "c3_cooling":                                                      # A: 조치 → 유온 재확인 → 종결(원래 동작)
        machine.on_status(inc, {"cmdId": inc.cmd_id, "result": "DONE", "t": "2026-10-03T12:00:05Z"}, NOW, NoFx(), time_scale=20)
        rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
        machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, NoFx())
        machine.on_timer(inc, "reobs", NOW, 50.0, NoFx(), time_scale=20)
        rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    rep = engine.variables(done)["result_report"]
    assert (done["status"], done["end_event"], rep["level"], inc.state) == ("COMPLETED", "E_end", "ok", "CLOSED")
    assert _row(rt, inst, "R_rejected")["status"] != "DONE" and _row(rt, inst, "B_overdue")["status"] == "CANCELLED"
    assert [c["code"] for c in out.calls] == {"c3_cooling": ["WO_CREATE"], "c3_pm": ["WO_CREATE"], "c3_spare": ["PR_CREATE", "GR_CONFIRM"]}[did]  # A 는 회복 뒤 후속 작업지시


# ================================================================ 거절 → 처리 없이 반려로 닫힌다
@pytest.mark.parametrize("did", THREE)
def test_rejection_does_nothing_to_plant_or_business_and_closes_the_case_as_rejected(world, did):
    rt, inst, inc, d, out = opened(world, did)
    fresh = rt.repo.get_instance(inst["proc_inst_id"])            # 앞 회차의 승인 값이 남아 있던 처리 건이라도 거절 뒤에는 비어 있어야 한다
    engine.set_variables(rt.definition_for(fresh), fresh, {"approved_by": "앞 회차 승인자", "commands": [{"code": "FAN_SET", "fan_pct": 100}],
                                                           "chosen_option": {"id": "skill:old"}})
    rt.repo.update_instance(fresh)
    res = rt.reject_card(_row(rt, inst, "T_approve")["id"], d["id"], *MGR, "이번 주 생산 일정상 진행하지 않음", now=NOW)
    assert res["rejected"] is True
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert (done["status"], done["end_event"]) == ("COMPLETED", "E_rejected")
    # 설비 명령 · 업무 처리 0건
    assert inc.cmd_id is None and out.calls == [] and out.mails == [] and out.restores == [] and world["executed"] == []
    assert all(_row(rt, inst, t)["status"] in ("TODO", "CANCELLED") for t in (*EFFECT_TASKS[did], "R_ok"))
    assert (v["approval"], v["approval_reason"]) == ("반려", "이번 주 생산 일정상 진행하지 않음")
    assert v.get("approved_by") is None and v.get("commands") is None and v.get("chosen_option") is None and v.get("approved_amount") is None
    rep = v["result_report"]
    assert (rep["outcome"], rep["level"], rep["incident_closed"]) == ("반려", "rejected", True) and "생산 일정상" in rep["summary"]
    assert inc.state == "REJECTED_BY_OPERATOR"                                    # 사건이 열린 채 남지 않는다
    assert world["book"][d["id"]]["state"] == "REJECTED"
    row = next(e["data"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"]) if e["job_id"] == "APPROVAL_REJECTED")
    assert (row["name"], row["by"], row["role"]) == ("거절 접수", "이생산", "role:prod-mgr")
    assert "APPROVAL_ACCEPTED" not in jobs(rt, inst) and rt.repo.list_approvals(inst["proc_inst_id"], rt.tenant_id) == []
    assert _row(rt, inst, "B_overdue")["status"] == "CANCELLED"                   # 지연 타이머도 함께 끝난다


def test_business_flags_stay_on_after_a_rejection_and_the_button_can_open_a_new_case(world):
    """B · C 는 거절하면 처리되지 않았으므로 업무 표시(정기 점검 도래 · 재고 보충 필요)가 켜진 채다 — 표시를 끄는 것은 정비 오더 · 입고뿐이다.
    끝난(거절된) 처리 건은 진행 중이 아니므로 버튼이 새 처리 건을 열 수 있다."""
    st = entstate.EnterpriseState()
    read = lambda name, params: {"pm_status": lambda: st.pm_status(params.get("asset")), "spare_stock": lambda: st.spare_stock(params.get("part"))}[name]()
    rt, inst, inc, d, out = opened(world, "c3_pm")
    rt.reject_card(_row(rt, inst, "T_approve")["id"], d["id"], *MGR, "사유", now=NOW)
    status = SB.status(read, rt)["scenarios"]
    assert status["B"]["alert"] is True and status["C"]["alert"] is True and status["B"]["running"] is None
    assert status["B"]["last"]["outcome"] == "반려"
    again = SB.prepare("B", read, rt, lambda pattern: "c3_pm")
    assert again["alert"]["pattern"] == "PM_DUE"


def test_a_rejection_needs_a_reason_and_a_role_that_may_approve_the_card(world):
    rt, inst, inc, d, out = opened(world, "c3_cooling")
    wid = _row(rt, inst, "T_approve")["id"]
    with pytest.raises(ValueError, match="거절 사유"):
        rt.reject_card(wid, d["id"], *MGR, "   ", now=NOW)
    with pytest.raises(PermissionError, match="거절 권한 없음"):                 # 운전원(등급 1)은 생산관리자 승인 카드를 거절할 수 없다
        rt.reject_card(wid, d["id"], "김운전", "role:operator", "사유", now=NOW)
    with pytest.raises(ValueError, match="does not belong"):
        rt.reject_card(wid, "DEC-OTHER", *MGR, "사유", now=NOW)
    assert _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS" and inc.state == "AWAITING_APPROVAL"
    assert world["book"][d["id"]]["state"] == "PENDING_APPROVAL" and "APPROVAL_REJECTED" not in jobs(rt, inst)
    rt.reject_card(wid, d["id"], *MGR, "사유", now=NOW)
    with pytest.raises(ValueError, match="이미 처리된 승인"):                    # 두 번 거절하지 않는다
        rt.reject_card(wid, d["id"], *MGR, "사유", now=NOW)


def test_a_flow_whose_approval_step_gives_no_rejection_value_refuses_the_rejection(world):
    """승인만 하는 부품(task:select)으로 등록한 흐름은 거절 뒤 갈 길이 없다 — 조용히 넘기지 않고 사유와 함께 거절한다."""
    rt, inst, inc, d = c2.open_a(world)
    with pytest.raises(ValueError, match="거절 값을 내지 않아"):
        rt.reject_card(_row(rt, inst, "T_approve")["id"], d["id"], *MGR, "사유", now=NOW)
    assert _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS" and inc.state == "AWAITING_APPROVAL"


def test_rejection_endpoint_answers_with_the_reason_codes_and_ends_the_case(world):
    """POST /api/todolist/{id}/reject-card — 포털의 [거절] 이 부를 경로. 사유 없음 422 · 권한 없음 403 · 모르는 task 404 · 두 번째 거절 400."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from procsvc import instance_mode
    rt, inst, inc, d, out = opened(world, "c3_spare")
    app = FastAPI()
    instance_mode.mount(app, "instance")
    c = TestClient(app)
    url = f"/api/todolist/{_row(rt, inst, 'T_approve')['id']}/reject-card"
    body = {"decision": d["id"], "by": MGR[0], "role": MGR[1], "reason": "예산 보류"}
    assert c.post(url, json=dict(body, reason="")).status_code == 422
    assert c.post(url, json=dict(body, role="role:operator")).status_code == 403
    assert c.post("/api/todolist/nope/reject-card", json=body).status_code == 404
    assert c.post(url.replace("reject-card", "submit"), json={"output": {"approval": "반려", "approval_reason": "x"}}).status_code == 403
    assert inc.state == "AWAITING_APPROVAL" and out.calls == []
    r = c.post(url, json=body)
    assert r.status_code == 200 and r.json()["rejected"] is True and r.json()["approval"] == "반려"
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert (done["status"], done["end_event"], inc.state, out.calls) == ("COMPLETED", "E_rejected", "REJECTED_BY_OPERATOR", [])
    assert c.post(url, json=body).status_code == 400


# ================================================================ 무응답 → 지연 알림만, 계속 기다린다
@pytest.mark.parametrize("did", THREE)
def test_no_answer_only_sends_the_overdue_notice_and_the_case_keeps_waiting_for_the_person(world, did):
    rt, inst, inc, d, out = opened(world, did)
    assert _row(rt, inst, "B_overdue")["due_date"] == engine.now_iso(NOW + timedelta(seconds=OVERDUE_S))      # 세 흐름 같은 기한
    rt.fire_timeouts(now=NOW + timedelta(seconds=OVERDUE_S - 1))
    assert (_row(rt, inst, "T_notice") or {"status": "TODO"})["status"] == "TODO"   # 기한 전에는 알림이 없다
    late = NOW + timedelta(seconds=OVERDUE_S + 1)
    rt.fire_timeouts(now=late)
    rt.reconcile_services(now=late)
    notice = _row(rt, inst, "T_notice")
    assert notice["status"] == "DONE" and notice["output"]["result_report"]["outcome"] == "승인 지연"
    assert notice["output"]["result_report"]["level"] == "info" and notice["output"]["result_report"]["incident_closed"] is False
    waiting = rt.repo.get_instance(inst["proc_inst_id"])
    # 자동 취소 · 자동 거절 없음: 승인 task 는 그대로, 사건도 승인 대기, 처리 0건
    assert waiting["status"] == "RUNNING" and _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS" and inc.state == "AWAITING_APPROVAL"
    assert out.calls == [] and inc.cmd_id is None and "approval" not in engine.variables(waiting)
    much_later = NOW + timedelta(hours=5)                                         # 아무리 지나도 스스로 끝나지 않는다
    rt.fire_timeouts(now=much_later)
    rt.reconcile_services(now=much_later)
    rt.poll_once(now=much_later)
    assert rt.repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING" and _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS"
    rt.reject_card(_row(rt, inst, "T_approve")["id"], d["id"], *MGR, "지연 알림 뒤 거절", now=NOW)        # 알림 뒤에도 사람이 닫을 수 있다
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert (done["status"], done["end_event"], inc.state) == ("COMPLETED", "E_rejected", "REJECTED_BY_OPERATOR")


def test_the_person_can_still_approve_after_the_overdue_notice(world):
    rt, inst, inc, d, out = opened(world, "c3_pm")
    late = NOW + timedelta(seconds=OVERDUE_S + 1)
    rt.fire_timeouts(now=late)
    rt.reconcile_services(now=late)
    approve(rt, inst, d)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert (done["status"], done["end_event"]) == ("COMPLETED", "E_end") and [c["code"] for c in out.calls] == ["WO_CREATE"]


# ================================================================ 흐름 모양 · 사전 검사
def test_the_three_flows_share_one_approval_stage(world):
    shapes = []
    for did in THREE:
        r = checked(world, did)
        assert r["ok"], (did, r["problems"])
        d = r["definition"]
        acts = {a["id"]: a for a in d["activities"]}
        timer = next(e for e in d["events"] if e["id"] == "B_overdue")
        shapes.append((acts["T_approve"]["tool"], acts["T_approve"]["outputData"][-2:], timer["timer"], timer.get("cancelActivity"),
                       acts["T_notice"]["service"]["outcome"], acts["R_rejected"]["service"]["outcome"],
                       sorted(e["id"] for e in d["events"] if e["type"] == "endEvent")))
        assert sum(1 for a in d["activities"] if a["tool"] == B.APPROVAL_TOOL) == 1          # 사람 승인은 흐름마다 한 번
    assert shapes == [(B.APPROVAL_TOOL, ["approval", "approval_reason"], "PT10M", False, "승인 지연", "반려", ["E_end", "E_notice", "E_rejected"])] * 3
    assert [m["name"] for _, _, m in FLOWS.FLOWS.values()] == ["냉각 긴급 대응", "정기 정비", "예비품 구매"]          # 이름은 원래대로


def _problems(r, text):
    return [p for p in r["problems"] if text in p["reason"]]


@pytest.mark.parametrize("did,effect,route", [("c3_cooling", "설비 명령", "'운전원 승인' → '승인?' → '냉각 명령'"),
                                              ("c3_pm", "작업지시", "'설비보전팀장 승인' → '승인?' → '정비 오더 등록 · 공지 메일'"),
                                              ("c3_spare", "ERP 발주", "'구매 담당 승인' → '승인?' → 'ERP 발주 · 공급사 메일'")])
def test_precheck_refuses_a_rejection_path_that_reaches_an_effect(world, did, effect, route):
    _, src, m = FLOWS.FLOWS[did]
    m = deepcopy(m)
    m["flows"]["F_approved"] = {"default": True}                                   # 승인 조건 없이 효과로
    m["flows"]["F_rejected"] = {"var": "approval", "op": "==", "value": "반려"}
    r = checked(world, did, src, m)
    hit = _problems(r, f"반려(또는 조건 없는) 경로로 {effect} 부품에 닿습니다")
    assert not r["ok"] and hit and route in hit[0]["reason"]


def test_precheck_refuses_a_rejection_path_that_ends_without_closing_the_incident(world):
    _, src, m = FLOWS.FLOWS["c3_pm"]
    src = (src.replace('<bpmn:sequenceFlow id="F_rejected" name="거절" sourceRef="G_approved" targetRef="R_rejected"/>',
                       '<bpmn:sequenceFlow id="F_rejected" name="거절" sourceRef="G_approved" targetRef="E_rejected"/>')
              .replace('<bpmn:serviceTask id="R_rejected" name="결과 보고: 거절"/>', "")
              .replace('<bpmn:sequenceFlow id="F_rej_end" sourceRef="R_rejected" targetRef="E_rejected"/>', "")
              .replace("<bpmn:flowNodeRef>R_rejected</bpmn:flowNodeRef>", ""))
    m = deepcopy(m)
    del m["tasks"]["R_rejected"]
    r = checked(world, "c3_pm", src, m)
    hit = _problems(r, "반려 경로가 결과 보고(반려) 없이 끝납니다")
    assert not r["ok"] and hit and "'거절 종결'" in hit[0]["reason"]


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
