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
