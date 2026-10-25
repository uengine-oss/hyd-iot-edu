"""audit2(2026-10-23) process 결함의 고친 뒤 동작 — .evidence/audit2/process.md P1 · P3 · P4 · P5 · P7 · P8 · P11, agent.md 4.

  P1  배포 중인 흐름은 [이 흐름 지우기]로 지우지 않는다(409 · 먼저 배포를 내리라는 사유). 내린 뒤에는 지워진다.
  P3  에스컬레이션 단계가 없는 수업 흐름에서 승인 전에 경보가 풀리면 처리 건이 '조치 전 해소'로 닫힌다(승인 · 타이머 취소, 기술 끝).
      승인 거절 사유는 한국어 문장이다.
  P4  GET /api/todolist?proc_inst_id=… 는 그 처리 건의 행을 빠짐없이, 처리 건 없이 읽으면 넘칠 때 오래된 행부터 뺀다.
  P5  PLC 거절 · ACK 시간 초과로 ESCALATED 된 A 흐름의 결과 보고는 실제 사유를 싣고 '재관측 기준 미달'로 쓰지 않는다.
  P7  승인에 붙은 끊는 타이머 가지가 사건을 닫지 않고 끝나면 사전 검사가 거절한다.
  P8  [정기 점검] · [재고 보충] 접수 실패 · 대기 초과는 409 · 503 + 사유, 누름 기록(error 칸)이 남는다.
  P11 C 승인 중 ERP 무응답은 503 + 사유, 승인 task 는 그대로 IN_PROGRESS.
  agent 4  approval-check 의 409 detail 이 승인 보류 사유로 그대로 올라온다."""
import asyncio
import io
import json
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import timedelta

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from procsvc import bpmn_import as B, current_approval, engine, flow_deploy, instance_mode, instances, machine
from test_instance_mode import world, NOW, ALERT, _row, NoFx  # noqa: F401  (world 는 fixture)
from test_approval_stage import FLOWS, MGR, OVERDUE_S, catalog, checked, opened, approve
from test_bpmn_import import api  # noqa: F401  (fixture)
from test_c3_bc_review import buttons, deploy, _reader  # noqa: F401  (fixture)
import test_c2_execution as c2
import test_c3_assembly as c3


# ================================================================ P1
def _deploy_class_flow(api):
    c, rt, repo, audit = api
    repo.upsert_user({"id": "agent:cooling", "username": "냉각 긴급 대응 에이전트", "is_agent": True, "agent_type": "agent",
                      "tools": "neo4j,enterprise,hyd-dmn", "tenant_id": "hyd"})
    _, src, mapping = c3._flows().FLOWS["c3_cooling"]
    assert c.post("/api/flows/import", json={"xml": src, "definition_id": "c3_cooling"}).status_code in (200, 201)
    r = c.post("/api/flows/c3_cooling/register", json={"mapping": mapping})
    assert r.status_code == 201, r.text
    rt.deploy_definition("c3_cooling", r.json()["version"], by="강사", reason="수업 흐름")
    return r.json()["version"]


def test_p1_delete_refuses_a_flow_deployed_on_the_alert_path(api):
    c, rt, repo, audit = api
    version = _deploy_class_flow(api)
    d = c.delete("/api/flows/c3_cooling?by=학생")
    assert d.status_code == 409, d.text
    reason = d.json()["detail"]["reason"]
    assert "배포된 흐름" in reason and "먼저 배포를 내리세요" in reason and "COOLER_DEGRADATION" in reason
    assert flow_deploy.route_definition(rt, "COOLER_DEGRADATION").id == "c3_cooling"          # 경보 경로는 그대로
    assert repo.get_proc_def("c3_cooling", version=version) is not None                      # 판본 원문도 그대로
    assert not any(a[2] == "FLOW_DELETED" for a in audit)


def test_p1_a_withdrawn_flow_can_be_deleted(api):
    c, rt, repo, audit = api
    version = _deploy_class_flow(api)
    flow_deploy.deploy_reset(rt, "강사")                                                     # 배포를 내린다
    d = c.delete("/api/flows/c3_cooling?by=학생")
    assert d.status_code == 200, d.text
    assert repo.get_proc_def("c3_cooling", version=version) is None


# ================================================================ P3
def test_p3_alert_cleared_before_approval_closes_the_class_flow_case(world):
    rt, inst, inc, d, out = opened(world, "c3_cooling")
    machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, NoFx())
    assert inc.state == "RESOLVED_WITHOUT_ACTION"
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert (done["status"], done["end_event"]) == ("COMPLETED", instances.InstanceRuntime.BEFORE_ACTION_END_EVENT)
    assert _row(rt, inst, "T_approve")["status"] == "CANCELLED" and _row(rt, inst, "B_overdue")["status"] == "CANCELLED"
    assert "조치 전 해소" in _row(rt, inst, "T_approve")["log"]
    v = engine.variables(done)
    rep = v["result_report"]
    assert (rep["outcome"], rep["level"], rep["incident_closed"]) == ("조치 전 해소", "info", False)
    assert "경보가 풀렸습니다" in rep["summary"] and v["incident_outcome"] == "RESOLVED_WITHOUT_ACTION"
    assert inc.state == "RESOLVED_WITHOUT_ACTION" and inc.cmd_id is None and out.calls == []        # 설비 명령 · 업무 처리 없음
    assert v.get("approval") is None                                                                # '반려'로 남지 않는다
    with pytest.raises(ValueError) as e:                                                            # 닫힌 뒤 [승인] 은 한국어 사유
        approve(rt, inst, d)
    assert "조치 전 해소" in str(e.value) and "requires review" not in str(e.value)
    assert any(ev["job_id"] == "INCIDENT_ENDED_BEFORE_ACTION" for ev in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"]))


def test_p3_a_missed_callback_is_closed_by_the_housekeeping_pass(world):
    rt, inst, inc, d, out = opened(world, "c3_cooling")
    machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, NoFx())          # on_incident_update 를 놓쳤다(재시작 등)
    assert rt.reconcile_terminal_incidents(now=NOW) == 1
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert done["end_event"] == instances.InstanceRuntime.BEFORE_ACTION_END_EVENT
    assert rt.reconcile_terminal_incidents(now=NOW) == 0                                  # 한 번만


def test_p3_approval_on_a_cleared_incident_is_refused_in_korean(world):
    rt, inst, inc, d, out = opened(world, "c3_cooling")
    inc.state = "RESOLVED_WITHOUT_ACTION"                                                  # 처리 건이 닫히기 전에 누른 [승인]
    with pytest.raises(ValueError) as e:
        approve(rt, inst, d)
    msg = str(e.value)
    assert "경보가 조치 전에 이미 풀려" in msg and "승인할 수 없습니다" in msg and "approval requires review" not in msg
    assert _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS" and inc.cmd_id is None


def test_p3_a_case_escalated_before_approval_is_closed_with_its_reason(world):
    rt, inst, inc, d, out = opened(world, "c3_pm")
    inc.state, inc.reason = "ESCALATED", "PROCESS_RESTART_REVIEW"
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    rep = engine.variables(done)["result_report"]
    assert done["end_event"] == instances.InstanceRuntime.BEFORE_ACTION_END_EVENT and rep["outcome"] == "조치 전 에스컬레이션"
    assert "PROCESS_RESTART_REVIEW" in rep["summary"] and out.calls == []


def test_p3_the_rejection_branch_still_ends_through_its_own_report(world):
    """반려 보고가 사건을 닫으면(REJECTED_BY_OPERATOR) 흐름이 스스로 E_rejected 로 끝난다 — 기술 끝이 가로채지 않는다."""
    rt, inst, inc, d, out = opened(world, "c3_cooling")
    rt.reject_card(_row(rt, inst, "T_approve")["id"], d["id"], *MGR, "생산 일정", now=NOW)
    rt.reconcile_terminal_incidents(now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert (done["end_event"], engine.variables(done)["result_report"]["outcome"]) == ("E_rejected", "반려")


# ================================================================ P4
def test_p4_todolist_by_case_returns_every_row_and_the_open_list_keeps_the_newest(world):
    rt = world["rt"]
    for i in range(205):
        rt.on_alert_raise(dict(ALERT, alertId=f"OLD-{i}"), now=NOW + timedelta(seconds=i))
    newest = rt.on_alert_raise(dict(ALERT, alertId="NEW-1"), now=NOW + timedelta(hours=1))
    app = FastAPI()
    instance_mode.mount(app, "instance")
    client = TestClient(app)
    mine = [w for w in rt.repo.list_workitems(proc_inst_id=newest["proc_inst_id"], limit=None) if w["status"] == "IN_PROGRESS"]
    assert mine
    by_case = client.get(f"/api/todolist?proc_inst_id={newest['proc_inst_id']}&status=IN_PROGRESS&limit=1")   # limit 이 있어도 자르지 않는다
    assert by_case.status_code == 200 and sorted(r["id"] for r in by_case.json()) == sorted(w["id"] for w in mine)
    every = rt.repo.list_workitems(proc_inst_id=newest["proc_inst_id"], limit=None)
    assert len(every) > 1
    all_rows = client.get(f"/api/todolist?proc_inst_id={newest['proc_inst_id']}&limit=1").json()
    assert sorted(r["id"] for r in all_rows) == sorted(w["id"] for w in every)
    open_rows = client.get("/api/todolist?status=IN_PROGRESS")
    rows = open_rows.json()
    assert len(rows) == 200 and open_rows.headers.get("X-Todolist-Truncated") == "1"
    assert any(r["proc_inst_id"] == newest["proc_inst_id"] for r in rows)                       # 가장 새 처리 건이 보인다
    assert not any(r["proc_inst_id"] == rt.repo.list_instances(None, None, rt.tenant_id)[-1]["proc_inst_id"] for r in rows)
    assert [r["start_date"] for r in rows] == sorted(r["start_date"] for r in rows)                # 순서는 그대로 오래된 것부터
    few = client.get("/api/todolist?status=IN_PROGRESS&limit=500")
    assert "X-Todolist-Truncated" not in few.headers


def test_p4_repo_newest_keeps_the_latest_rows_in_ascending_order():
    """내 작업함(inbox_view)도 같은 저장소 호출(newest=True, 500행)을 쓴다."""
    from procsvc import procdb
    repo = procdb.MemoryRepo()
    for i in range(3):
        repo.workitems[f"w{i}"] = {"id": f"w{i}", "proc_inst_id": "p", "status": "IN_PROGRESS", "start_date": f"2026-10-23T00:00:0{i}Z", "tenant_id": "hyd"}
    assert [w["id"] for w in repo.list_workitems(status="IN_PROGRESS", limit=2, newest=True)] == ["w1", "w2"]
    assert [w["id"] for w in repo.list_workitems(status="IN_PROGRESS", limit=2)] == ["w0", "w1"]          # 기본은 전과 같다
    assert [w["id"] for w in repo.list_workitems(status="IN_PROGRESS", limit=None, newest=True)] == ["w0", "w1", "w2"]


# ================================================================ P5
def _escalated(world, how):
    rt, inst, inc, d, out = opened(world, "c3_cooling")
    approve(rt, inst, d)
    assert inc.state == "AWAITING_ACK"
    if how == "reject":
        machine.on_status(inc, {"cmdId": inc.cmd_id, "result": "REJECTED", "reason": "MODE_LOCAL", "t": "2026-10-03T12:00:05Z"}, NOW, NoFx(), time_scale=20)
    else:
        machine.on_timer(inc, "ack", NOW, None, NoFx(), time_scale=20, cmd_id=inc.cmd_id)
    assert inc.state == "ESCALATED"
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    rt.reconcile_services(now=NOW + timedelta(seconds=5))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    return inc, done, engine.variables(done)["result_report"]


def test_p5_plc_rejection_is_reported_with_its_reason_not_as_a_reobservation_shortfall(world):
    inc, done, rep = _escalated(world, "reject")
    assert done["end_event"] == "E_end" and rep["outcome"] == "미달"                         # 흐름의 결과는 그대로
    assert "PLC 에서 거절" in rep["summary"] and "MODE_LOCAL" in rep["summary"] and "재관측 기준 미달" not in rep["summary"]
    assert rep["cause"]["reason"] == "PLC REJECTED: MODE_LOCAL" and rep["cause"]["reobserved"] is False
    assert rep["facts"]["incident_reason"] == "PLC REJECTED: MODE_LOCAL" and "재관측 기준 미달" in rep["template_summary"]
    assert engine.variables(done)["incident_reason"] == inc.reason


def test_p5_ack_timeout_is_reported_as_no_ack(world):
    inc, done, rep = _escalated(world, "ack")
    assert "ACK" in rep["summary"] and "30초" in rep["summary"] and "재관측 기준 미달" not in rep["summary"]
    assert rep["cause"]["reason"] == "ACK_TIMEOUT"


def test_p5_a_real_reobservation_shortfall_keeps_the_flow_wording(world):
    rt, inst, inc, d, out = opened(world, "c3_cooling")
    approve(rt, inst, d)
    machine.on_status(inc, {"cmdId": inc.cmd_id, "result": "DONE", "t": "2026-10-03T12:00:05Z"}, NOW, NoFx(), time_scale=20)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    machine.on_timer(inc, "reobs", NOW, 70.0, NoFx(), time_scale=20)                         # 기준 밖 → MITIGATION_FAILED
    assert (inc.state, inc.reason) == ("ESCALATED", "MITIGATION_FAILED")
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    rep = engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))["result_report"]
    assert rep["outcome"] == "미달" and "재관측 기준 미달" in rep["summary"] and "cause" not in rep


# ================================================================ P7
def _my_cool(world, src):
    _, _, m = FLOWS.FLOWS["c3_cooling"]
    return B.check(B.parse_bpmn(src), deepcopy(m), {"catalog": catalog(world), "definition_id": "my_cool", "version": "1",
                                                     "file_name": "my.bpmn", "xml_sha256": "x"})


def test_p7_precheck_refuses_an_interrupting_overdue_timer_that_ends_without_closing_the_incident(world):
    _, src, _ = FLOWS.FLOWS["c3_cooling"]
    src2 = src.replace(' cancelActivity="false"', '')                                      # bpmn.io 기본값: 끊는 타이머
    assert src2 != src
    r = _my_cool(world, src2)
    hits = [p for p in r["problems"] if "끊는 타이머" in p["reason"]]
    assert not r["ok"] and hits and hits[0]["where"]["id"] == "B_overdue"
    assert "사건을 닫는 결과 보고 없이 끝납니다" in hits[0]["reason"] and "'알림'" in hits[0]["reason"]


def test_p7_an_interrupting_timer_whose_branch_closes_the_incident_passes(world):
    _, src, m = FLOWS.FLOWS["c3_cooling"]
    src2 = src.replace(' cancelActivity="false"', '')
    m = deepcopy(m)
    m["tasks"]["T_notice"] = {"part": "svc:report", "config": {"outcome": "지연", "title": "{asset} 승인 지연", "summary": "기한 안에 승인하지 않음"}}
    r = B.check(B.parse_bpmn(src2), m, {"catalog": catalog(world), "definition_id": "my_cool", "version": "1",
                                        "file_name": "my.bpmn", "xml_sha256": "x"})
    assert not [p for p in r["problems"] if "끊는 타이머" in p["reason"]], r["problems"]
    assert checked(world, "c3_cooling")["ok"]                                              # 수업 흐름(끊지 않는 타이머)은 그대로 통과


# ================================================================ P8
@pytest.mark.parametrize("exc,code,text", [(ValueError("접수 당시 정의와 원천 경보 정책이 일치하지 않습니다"), 409, "경보를 접수하지 못했습니다"),
                                           (TimeoutError("원천 접수 7 처리 대기 중: PENDING"), 503, "경보 접수 확인 시간이 지났습니다")])
def test_p8_scenario_admission_failure_answers_with_a_reason_and_a_press_record(buttons, monkeypatch, exc, code, text):
    main = buttons["main"]

    async def broken(alert):
        raise exc
    monkeypatch.setattr(main, "_admit_human_alert", broken)
    with pytest.raises(HTTPException) as e:
        asyncio.run(main.scenario_start("B", {"by": "박정비"}))
    assert e.value.status_code == code and text in e.value.detail and str(exc) in e.value.detail
    press = [a for a in buttons["audits"] if a[2] == "SCENARIO_BUTTON"]
    assert press and text in press[-1][3]["error"] and press[-1][3]["instance"] is None
    r = TestClient(main.app, raise_server_exceptions=False).post("/api/scenario/B/start", json={"by": "박정비"})
    assert r.status_code == code and text in r.json()["detail"]


# ================================================================ P11
def test_p11_approval_with_erp_down_is_a_503_with_a_reason(world):
    rt, inst, inc, d, out = opened(world, "c3_spare")

    def down(name, params):
        raise urllib.error.URLError("[Errno 111] Connection refused")
    rt.hooks.enterprise_read = down
    app = FastAPI()
    instance_mode.mount(app, "instance")
    instance_mode._ctx = world["ctx"]
    wid = _row(rt, inst, "T_approve")["id"]
    r = TestClient(app, raise_server_exceptions=False).post(f"/api/todolist/{wid}/select",
        json={"decision": d["id"], "option": d["options"][0]["id"], "by": MGR[0], "role": MGR[1]})
    assert r.status_code == 503, r.text
    assert "ERP 견적" in r.json()["detail"] and "enterprise-sim" in r.json()["detail"] and "Connection refused" in r.json()["detail"]
    assert _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS" and out.calls == []          # 상태는 그대로, 다시 누를 수 있다


# ================================================================ agent.md 4
def _refusing(status, body):
    def refuse(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, status, "x", {}, io.BytesIO(body))
    return refuse


def test_agent4_approval_check_409_detail_reaches_the_person(monkeypatch):
    detail = "현재 ERP 부족부품과 명시 구매 Part가 일치하지 않습니다"
    monkeypatch.setattr(urllib.request, "urlopen", _refusing(409, json.dumps({"detail": detail}).encode()))
    with pytest.raises(current_approval.ApprovalReviewRequired) as e:
        current_approval.check({"id": "DEC-1"}, "skill:x", "role:purchasing")
    assert detail in str(e.value) and "원천 연결" not in str(e.value)
    assert e.value.report["allowed"] is False and e.value.report["reasons"] == [detail]


def test_agent4_other_agent_errors_keep_the_connection_wording_with_the_code(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _refusing(500, b"not json"))
    with pytest.raises(ValueError) as e:
        current_approval.check({"id": "DEC-1"}, "skill:x", "role:purchasing")
    assert not isinstance(e.value, current_approval.ApprovalReviewRequired)
    assert "원천 연결" in str(e.value) and "500" in str(e.value)

    def unreachable(request, timeout=None):
        raise urllib.error.URLError("refused")
    monkeypatch.setattr(urllib.request, "urlopen", unreachable)
    with pytest.raises(ValueError) as e:
        current_approval.check({"id": "DEC-1"}, "skill:x", "role:purchasing")
    assert "원천 연결" in str(e.value)


# ======================================================================================================================
# 2차(2026-10-23): P9(사용자 결정) · P2 · P6 · P10 · P12 · NotStarted 409 · 수업 흐름 [닫기] 거절 문구
#   P9  포털 [기준 흐름으로 되돌리기]는 강사가 배포한 수업 흐름(class_flow)을 남기고 학생이 배포한 흐름만 내린다(응답 kept). 강사 스크립트는
#       include_class=true 로 수업 흐름도 내린다. 수업 흐름 표시는 배포가 남긴다(흐름 id 로 짐작하지 않음).
#   P2  사람이 닫은 질문은 'closed'(답이 나왔습니다 · 서버 판정 없음).
#   P6  [정기 점검] 두 요청이 겹쳐도 처리 건은 하나, 두 번째는 409.
#   P10 기준 파일 판본이 바뀐 뒤 사람이 배포한 판본으로 기동해도 되돌리기 · 비교가 새 기준 판본으로 간다. 같은 번호의 다른 원문이 있으면 사유로 거절.
#   P12 승인 지연을 선언하고 사람만 기다리는 처리 건은 기준점을 붙잡지 않는다. 막은 처리 건은 이름으로 응답에 실린다.
from entsim import state as entstate  # noqa: E402
from test_flow_deploy import _student_flow  # noqa: E402
from test_instance_mode import DEFS  # noqa: E402
import test_b5_ask as b5  # noqa: E402
from procsvc import ask, procdb, scenario_buttons as SB  # noqa: E402


def _class_deploy(world, did, by="강사"):
    r = checked(world, did)
    assert r["ok"], r["problems"]
    rt = world["rt"]
    rt.register_definition(r["definition"])
    return rt.deploy_definition(did, "1", by, "수업 흐름 배포", class_flow=True)


def _class_world(world):
    for did in ("c3_cooling", "c3_pm", "c3_spare"):
        assert _class_deploy(world, did)["class_flow"] is True
    rt = world["rt"]
    rt.register_definition(_student_flow(rt))                                              # 학생이 만든 흐름 하나
    rt.deploy_definition("student_pump", "1.0", by="학생1", reason="내 흐름 시험")
    return rt


# ================================================================ P9
def test_p9_portal_reset_keeps_the_class_flows_and_withdraws_only_the_student_flow(world):
    rt = _class_world(world)
    table = flow_deploy.routes(rt)
    assert {f["definition"]: f["class_flow"] for f in table["flows"]} == \
        {"c3_cooling": True, "c3_pm": True, "c3_spare": True, "student_pump": False}
    assert {r["pattern"]: r["source"] for r in table["routes"]}["PM_DUE"] == "수업 흐름" and table["reset_needed"]
    out = flow_deploy.deploy_reset(rt, "학생1")
    assert [(c["definition"], c["action"]) for c in out["changes"]] == [("student_pump", "withdraw")]
    assert sorted(k["definition"] for k in out["kept"]) == ["c3_cooling", "c3_pm", "c3_spare"]
    kept = {k["definition"]: k for k in out["kept"]}
    assert kept["c3_pm"]["name"] == "정기 정비" and kept["c3_pm"]["patterns"] == ["PM_DUE"] and kept["c3_pm"]["deployed_by"] == "강사"
    assert "수업 흐름이라 남김" in kept["c3_pm"]["text"] and out["include_class"] is False and out["already_reference"] is False
    assert "수업 흐름 3개" in out["message"] and "정기 정비" in out["message"]
    for pattern, did in (("COOLER_DEGRADATION", "c3_cooling"), ("PM_DUE", "c3_pm"), ("SPARE_BELOW_MIN", "c3_spare")):
        assert flow_deploy.route_definition(rt, pattern).id == did                        # B · C 버튼이 멈추지 않는다
    assert flow_deploy.route_definition(rt, "PUMP_LEAKAGE").id == "anomaly_response"
    assert out["routes"]["reset_needed"] is False and out["routes"]["at_reference"] is False
    again = flow_deploy.deploy_reset(rt, "학생1")                                         # 다시 눌러도 수업 흐름은 그대로
    assert again["changes"] == [] and len(again["kept"]) == 3 and again["message"].startswith("되돌릴 내 흐름이 없습니다")


def test_p9_the_instructor_reset_with_include_class_also_withdraws_the_class_flows(world):
    rt = _class_world(world)
    out = flow_deploy.deploy_reset(rt, "강사", "수업 끝", include_class=True)
    assert sorted(c["definition"] for c in out["changes"]) == ["c3_cooling", "c3_pm", "c3_spare", "student_pump"]
    assert out["kept"] == [] and out["routes"]["at_reference"] and out["include_class"] is True
    assert all(c["class_flow"] for c in out["changes"] if c["definition"].startswith("c3_"))
    assert flow_deploy.route_definition(rt, "PM_DUE").id == "anomaly_response"


def test_p9_the_mark_belongs_to_the_deployment_not_to_the_flow_id(world):
    """표시는 배포가 가진다 — id 접두어로 짐작하지 않는다. 수업 흐름으로 배포돼 있는 동안 표시 없는 배포는 거절하고(2026-10-25: 그 배포가
    표시를 지워 [기준 흐름으로 되돌리기]가 수업 흐름을 내렸다), 강사가 내린 뒤에는 같은 id 라도 표시 없이 배포하면 학생 흐름이다.
    기준 흐름에는 표시를 붙이지 않는다."""
    rt = world["rt"]
    _class_deploy(world, "c3_pm")
    r = checked(world, "c3_pm")
    raw = dict(deepcopy(r["definition"]), version="2")
    rt.register_definition(raw)
    with pytest.raises(ValueError, match="강사가 배포한 수업 흐름"):
        rt.deploy_definition("c3_pm", "2", "학생1", "수업 흐름을 고쳐 배포")
    assert rt.definition_status("c3_pm")["class_flow"] is True
    flow_deploy.deploy_reset(rt, "강사", "수업 끝", include_class=True)                  # 강사가 내린 뒤
    rt.deploy_definition("c3_pm", "2", "학생1", "같은 id 를 내 흐름으로")
    assert rt.definition_status("c3_pm")["class_flow"] is False
    out = flow_deploy.deploy_reset(rt, "학생1")
    assert [c["definition"] for c in out["changes"]] == ["c3_pm"] and out["kept"] == []
    raw3 = dict(deepcopy(r["definition"]), version="3")
    rt.register_definition(raw3)
    rt.deploy_definition("c3_pm", "3", "강사", "다시 수업 흐름", class_flow=True)
    assert rt.definition_status("c3_pm")["class_flow"] is True
    rt.register_definition(dict(deepcopy(r["definition"]), version="4"))                  # 새 판본 등록은 배포 표시를 건드리지 않는다
    assert flow_deploy.routes(rt)["flows"][0]["class_flow"] is True
    with pytest.raises(ValueError, match="기준 흐름"):
        rt.deploy_definition("anomaly_response", "2.2", "강사", "x", class_flow=True)


def test_p9_http_contract_and_the_instructor_script(world, monkeypatch):
    rt = world["rt"]
    monkeypatch.setattr(instance_mode, "_runtime", rt)
    app = FastAPI()
    instance_mode.mount(app, "instance")
    client = TestClient(app)
    r = checked(world, "c3_pm")
    rt.register_definition(r["definition"])
    dep = client.post("/api/process/definitions/c3_pm/deploy", json={"version": "1", "by": "c3-assembly", "reason": "C3", "class_flow": True})
    assert dep.status_code == 200 and dep.json()["class_flow"] is True
    portal = client.post("/api/flows/deploy-reset", json={"by": "학생1"}).json()           # 포털 본문(include_class 없음)
    assert portal["changes"] == [] and [k["definition"] for k in portal["kept"]] == ["c3_pm"]
    assert client.get("/api/flows/deployments").json()["flows"][0]["class_flow"] is True
    teacher = client.post("/api/flows/deploy-reset", json={"by": "강사", "include_class": True}).json()
    assert [c["definition"] for c in teacher["changes"]] == ["c3_pm"] and teacher["kept"] == []
    # 강사 스크립트: deploy 는 class_flow, deploy-reset 은 include_class 를 싣는다
    mod = c3._flows()
    calls = []
    monkeypatch.setattr(mod, "call", lambda m, p, body=None: calls.append((m, p, body)) or {"version": "1", "changes": [], "kept": []})
    assert mod.main(["c3_flows.py", "deploy-reset", "강사"]) == 0 and calls[-1][2]["include_class"] is True
    calls.clear()
    assert mod.main(["c3_flows.py", "deploy"]) == 0
    deploys = [b for m, p, b in calls if p.endswith("/deploy")]
    assert len(deploys) == 3 and all(b["class_flow"] is True for b in deploys)


def test_p9_flows_reset_after_the_portal_reset_keeps_the_class_flow_definitions(api):
    """학생 랩 순서: 흐름 배포 화면 [기준 흐름으로 되돌리기] → 흐름 가져오기 [기준으로 되돌리기]. 수업 흐름 정의 · 판본은 남고 경보 경로도 그대로."""
    c, rt, repo, audit = api
    version = _deploy_class_flow(api)                                                       # 가져오기 · 등록(포털과 같은 API)
    rt.repo.clear_deployment("c3_cooling", rt.tenant_id, actor="강사", reason="다시 배포")
    rt.deploy_definition("c3_cooling", version, by="c3-assembly", reason="수업", class_flow=True)
    _, _, mapping = c3._flows().FLOWS["c3_cooling"]
    assert c.post("/api/flows/c3_cooling/register", json={"mapping": mapping}).status_code == 201  # 판본을 하나 더 등록해도 표시는 그대로
    assert flow_deploy.deploy_reset(rt, "학생")["kept"][0]["definition"] == "c3_cooling"
    assert c.post("/api/flows/reset").status_code == 200
    assert flow_deploy.route_definition(rt, "COOLER_DEGRADATION").id == "c3_cooling"
    assert repo.get_proc_def("c3_cooling", version=version) is not None


# ================================================================ P2
def test_p2_a_question_a_person_closed_reads_closed_not_answered(world, tmp_path):
    rt = world["rt"]
    b5._people(rt)
    v = b5._ask(rt)
    b5._work(rt, tmp_path, b5._cli("JSON 없이 말로만 답함"))
    b5._work(rt, tmp_path, b5._cli("또 JSON 없음"))
    before = ask.view(rt, v["id"])
    assert before["state"] == "failed"
    out = rt.close_agent_task(before["workitem"], "강사", "워커가 계속 실패해 닫음")
    assert out["instance_ended"] is True and out["end_event"] == "closed-by-human"
    d = ask.view(rt, v["id"])
    assert d["state"] == "closed" and d["message"].startswith("사람이 닫은 질문입니다") and "워커가 계속 실패해 닫음" in d["message"]
    assert d["result"] is None                                                             # 답이 없으니 서버 판정도 없다
    assert [h["state"] for h in ask.history(rt) if h["id"] == v["id"]] == ["closed"]


# ================================================================ P6
def test_p6_two_overlapping_scenario_presses_open_one_case(buttons, monkeypatch):
    main, rt = buttons["main"], buttons["rt"]
    seq = iter(range(100))
    real_build = SB.build_alert

    def later_alert(*a, **k):                                                              # 1초 넘게 떨어진 두 누름 = 서로 다른 경보 id
        alert = real_build(*a, **k)
        return dict(alert, alertId=f"{alert['alertId']}-{next(seq)}")
    monkeypatch.setattr(SB, "build_alert", later_alert)

    async def slow_admit(alert):
        await asyncio.sleep(0.05)                                                          # 원천 접수 대기(검사와 처리 건 사이의 틈)
        rt.on_alert_raise(alert, now=NOW)
    monkeypatch.setattr(main, "_admit_human_alert", slow_admit)

    async def both():
        return await asyncio.gather(main.scenario_start("B", {"by": "탭1"}), main.scenario_start("B", {"by": "탭2"}),
                                    return_exceptions=True)
    results = asyncio.run(both())
    ok = [r for r in results if isinstance(r, dict)]
    refused = [r for r in results if isinstance(r, HTTPException)]
    assert len(ok) == 1 and len(refused) == 1 and refused[0].status_code == 409 and "이미 진행 중" in refused[0].detail
    running = [i for i in rt.repo.list_instances("RUNNING", None, rt.tenant_id) if i["proc_def_id"] == "c3_pm"]
    assert [i["proc_inst_id"] for i in running] == [ok[0]["instance"]]


# ================================================================ NotStarted → 409 + 경보가 간 곳
def test_not_started_names_where_the_alert_went(world):
    rt = world["rt"]
    st = entstate.EnterpriseState()
    alert = SB.build_alert("C", st.spare_stock("P-PMP-SEAL")["facts"], now=NOW)
    triage = rt.on_alert_raise(alert, now=NOW)                                             # 흐름이 내려가 경보가 기준 흐름 쪽으로 갔다
    with pytest.raises(SB.NotStarted) as e:
        SB.started(rt, "C", alert, None)
    assert "배포가 내려갔습니다" in str(e.value) and triage["proc_inst_id"] in str(e.value)


# ================================================================ P10
def _reboot_with_newer_reference(world, monkeypatch, tmp_path, newer_version="2.4", collide=False):
    import shutil
    rt, ctx = world["rt"], world["ctx"]
    repo = rt.repo
    raw = json.loads((DEFS / "anomaly_response_v22.json").read_text(encoding="utf-8"))
    raw["version"] = "2.3"
    rt.register_definition(raw)
    rt.deploy_definition("anomaly_response", "2.3", "학생", "U4 실습")                     # 사람이 배포한 판본
    if collide:                                                                            # 같은 번호로 다른 원문을 먼저 등록해 둠
        other = json.loads((DEFS / "anomaly_response_v22.json").read_text(encoding="utf-8"))
        other["version"], other["description"] = newer_version, "학생이 먼저 쓴 같은 번호"
        rt.register_definition(other)
    newer = json.loads((DEFS / "anomaly_response_v22.json").read_text(encoding="utf-8"))
    newer["version"] = newer_version
    for f in DEFS.iterdir():
        if f.is_file():
            shutil.copy(f, tmp_path / f.name)
    (tmp_path / "anomaly_response_next.json").write_text(json.dumps(newer, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(instance_mode, "DEFINITIONS_DIR", tmp_path)
    monkeypatch.setattr(instance_mode, "DEFINITION_FILE", "anomaly_response_next.json")
    monkeypatch.setattr(procdb, "make_repo", lambda: repo)                                 # 같은 DB 로 재기동
    return instance_mode.build(ctx), newer


def test_p10_reset_and_compare_reach_the_new_reference_version_after_a_file_upgrade(world, monkeypatch, tmp_path):
    rt2, newer = _reboot_with_newer_reference(world, monkeypatch, tmp_path)
    assert (rt2.defn.raw["version"], rt2.base_version, rt2.base_problem) == ("2.3", "2.4", None)
    assert rt2.repo.deployed_version("anomaly_response", "hyd") == "2.3"                   # 등록은 배포가 아니다
    assert rt2.repo.get_proc_def("anomaly_response", "hyd", version="2.4")["definition"] == newer
    diff = flow_deploy.compare_with_reference(rt2, "anomaly_response")
    assert diff["reference"] == {"definition": "anomaly_response", "version": "2.4"} and diff["target"]["version"] == "2.3"
    out = flow_deploy.deploy_reset(rt2, "학생")
    assert [(c["definition"], c["action"], c["from"], c["to"]) for c in out["changes"]] == [("anomaly_response", "reset", "2.3", "2.4")]
    assert rt2.repo.deployed_version("anomaly_response", "hyd") == "2.4"


def test_p10_a_reference_version_number_already_taken_by_other_text_is_refused_with_its_reason(world, monkeypatch, tmp_path):
    rt2, _ = _reboot_with_newer_reference(world, monkeypatch, tmp_path, collide=True)
    assert rt2.base_problem and "같은 판본 번호로 다른 원문" in rt2.base_problem                # 기동은 된다(사유만 남김)
    with pytest.raises(ValueError, match="같은 판본 번호로 다른 원문"):
        flow_deploy.deploy_reset(rt2, "학생")
    assert rt2.repo.deployed_version("anomaly_response", "hyd") == "2.3"                   # 남의 원문으로 '되돌리지' 않았다
    monkeypatch.setattr(instance_mode, "_runtime", rt2)
    app = FastAPI()
    instance_mode.mount(app, "instance")
    client = TestClient(app)
    for r in (client.post("/api/flows/deploy-reset", json={"by": "학생"}),
              client.get("/api/flows/deploy-compare", params={"definition": "anomaly_response"})):
        assert r.status_code == 409 and "같은 판본 번호로 다른 원문" in r.json()["detail"]


# ================================================================ P12
@pytest.fixture
def anchor(world, monkeypatch):
    """승인 대기 c3_pm 처리 건 하나 + process main 버튼(enterprise-sim 호출은 기록만)."""
    from procsvc import main
    rt, inst, inc, d, out = opened(world, "c3_pm")
    st, posts, audits = entstate.EnterpriseState(), [], []
    monkeypatch.setattr(main, "PROCESS_MODE", "instance")
    monkeypatch.setattr(main.instance_mode, "current", lambda: rt)
    monkeypatch.setattr(main.instance_mode, "enterprise_read", _reader(st))
    monkeypatch.setattr(main, "_entsim_post", lambda path, body: posts.append(path) or {"ok": True})
    monkeypatch.setattr(main, "_audit", lambda *a, **k: audits.append(a))
    return {"main": main, "rt": rt, "inst": inst, "posts": posts, "audits": audits}


def test_p12_a_case_waiting_past_its_approval_deadline_no_longer_holds_the_scenario_clock(anchor):
    main, rt, inst, posts = anchor["main"], anchor["rt"], anchor["inst"], anchor["posts"]
    pid = inst["proc_inst_id"]
    first = asyncio.run(main.scenario_reset("B", {"by": "강사"}))                           # 기한 전 승인 대기 = 붙잡는다(원래 동작)
    assert first["reanchored"] is False and "/api/reanchor" not in posts
    held = first["reanchor"]["blocked_by"]
    assert [b["instance"] for b in held] == [pid] and held[0]["name"] == "정기 정비" and held[0]["asset"] == "HYD-02"
    assert held[0]["waiting_on"] and held[0]["why"] == "진행 중"
    late = NOW + timedelta(seconds=OVERDUE_S + 1)                                         # 흐름이 '승인 지연'을 선언
    rt.fire_timeouts(now=late)
    rt.reconcile_services(now=late)
    assert _row(rt, inst, "T_notice")["status"] == "DONE" and _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS"
    now_inst = rt.repo.get_instance(pid)
    rows = rt.repo.list_workitems(proc_inst_id=pid, limit=None)
    raw = deepcopy(rt.definition_for(now_inst).raw)                                       # 같은 모양인데 기다리는 단계가 사람 단계가 아니면 붙잡는다
    next(a for a in raw["activities"] if a["id"] == "T_approve")["type"] = "serviceTask"
    assert SB._approval_overdue(engine.Definition.from_dict(raw), now_inst, rows) is None
    assert SB._approval_overdue(rt.definition_for(now_inst), now_inst, rows)[0]["activity"] == "T_approve"
    posts.clear()
    second = asyncio.run(main.scenario_reset("B", {"by": "강사"}))
    assert second["reanchored"] is True and "/api/reanchor" in posts
    assert second["reanchor"]["blocked_by"] == [] and [o["instance"] for o in second["reanchor"]["overdue"]] == [pid]
    assert second["reanchor"]["overdue"][0]["why"].startswith("승인 지연")
    ev = [e for e in rt.repo.list_events(proc_inst_id=pid) if e["job_id"] == "SCENARIO_REANCHOR"]
    assert ev and "새 판단이 필요할 수 있습니다" in ev[0]["data"]["goal"]                   # 그 처리 건 기록에 남는다
    press = [a for a in anchor["audits"] if a[2] == "SCENARIO_BUTTON"][-1][3]
    assert press["reanchored"] is True and press["reanchor_overdue"] == [pid] and press["reanchor_blocked_by"] == []
    assert rt.repo.get_instance(pid)["status"] == "RUNNING"                               # 처리 건은 그대로 사람을 기다린다


def test_p12_an_agent_still_working_keeps_holding_the_clock(world):
    """사람 단계가 아닌 일이 열려 있으면(판단 중) 기한과 상관없이 붙잡는다."""
    _class_deploy(world, "c3_pm")
    rt = world["rt"]
    st = entstate.EnterpriseState()
    inst = rt.on_alert_raise(SB.build_alert("B", st.pm_status("HYD-02")["facts"], now=NOW), now=NOW)
    found = SB.reanchor_blockers(rt)
    assert [b["instance"] for b in found["blocked_by"]] == [inst["proc_inst_id"]] and found["overdue"] == []
    assert SB.may_reanchor(rt) is False


# ================================================================ 수업 흐름 판단 실패 [닫기] 거절 문구
def test_close_refusal_names_only_paths_the_flow_has(world):
    _class_deploy(world, "c3_cooling")
    rt = world["rt"]
    inst = rt.on_alert_raise(dict(c2.ALERT, alertId="HYD-01-A-close"), now=NOW)
    assert inst["proc_def_id"] == "c3_cooling"
    agent = _row(rt, inst, "T_agent")
    agent.update(status="PENDING")
    rt.repo.update_workitem(agent)
    with pytest.raises(ValueError) as e:
        rt.close_agent_task(agent["id"], "강사", "판단 실패")
    msg = str(e.value)
    assert "사건이 아직 진행 중" in msg and "에스컬레이션" not in msg and "[다시 수행]" in msg
    ref = rt.on_alert_raise({"alertId": "ALT-close-ref", "asset": "HYD-02", "pattern": "PUMP_LEAKAGE", "state": "RAISE"}, now=NOW)
    # ↑ 기준 흐름(에스컬레이션 단계 있음)은 그 길도 말한다
    assert ref["proc_def_id"] == "anomaly_response"
    first = next(w for w in rt.repo.list_workitems(proc_inst_id=ref["proc_inst_id"], limit=None) if w["status"] == "IN_PROGRESS")
    first.update(status="PENDING")
    rt.repo.update_workitem(first)
    with pytest.raises(ValueError) as e2:
        rt.close_agent_task(first["id"], "강사", "판단 실패")
    assert "에스컬레이션 검토" in str(e2.value) and "[다시 수행]" in str(e2.value)


def test_class_flow_id_is_not_taken_over_by_a_student(api):
    """2026-10-25 학생 행위 점검: 학생이 수업 흐름 id 로 가져오면 강사 초안을 덮었고, 그 id 로 등록한 판본을 표시 없이 배포하면 수업 흐름이
    학생 흐름이 되어 [기준 흐름으로 되돌리기]가 내렸다(B · C 멈춤). 지금 수업 흐름으로 배포된 id 는 표시 없이 가져오기 · 배포를 거절한다."""
    c, rt, repo, audit = api
    repo.upsert_user({"id": "agent:cooling", "username": "냉각 긴급 대응 에이전트", "is_agent": True, "agent_type": "agent",
                      "tools": "neo4j,enterprise,hyd-dmn", "tenant_id": "hyd"})
    _, src, mapping = c3._flows().FLOWS["c3_cooling"]
    assert c.post("/api/flows/import", json={"xml": src, "definition_id": "c3_cooling", "class_flow": True}).status_code == 200
    v1 = c.post("/api/flows/c3_cooling/register", json={"mapping": mapping}).json()["version"]
    rt.deploy_definition("c3_cooling", v1, by="강사", reason="수업 흐름", class_flow=True)
    r = c.post("/api/flows/import", json={"xml": src, "definition_id": "c3_cooling"})
    assert r.status_code == 409 and "강사가 배포한 수업 흐름 id" in r.json()["detail"]["reason"] and "my_cooling" in r.json()["detail"]["reason"]
    assert c.post("/api/flows/import", json={"xml": src, "definition_id": "c3_cooling", "class_flow": True}).status_code == 200   # 강사 스크립트
    v2 = c.post("/api/flows/c3_cooling/register", json={"mapping": mapping}).json()["version"]
    with pytest.raises(ValueError, match="강사가 배포한 수업 흐름"):
        rt.deploy_definition("c3_cooling", v2, by="학생1", reason="내가 다시 배포")
    assert flow_deploy.route_definition(rt, "COOLER_DEGRADATION").id == "c3_cooling"
    assert rt.deploy_definition("c3_cooling", v2, by="강사", reason="수업 흐름 갱신", class_flow=True)["class_flow"] is True
    assert c.post("/api/flows/import", json={"xml": src, "definition_id": "my_cooling"}).status_code == 200            # 내 id 는 된다
