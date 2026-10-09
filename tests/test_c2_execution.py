"""C2 (확정 TODO C, 2026-10-09 확정 흐름) 시나리오 세 흐름 — bpmn.io 그림 → 일반 부품으로 가져오기 → 등록 · 배포 → 실제 런타임(MemoryRepo ·
실제 Incident 상태기계 · 승인 경로)으로 끝까지. 세 흐름 모두 같은 뼈대다:

    시작(감지) → 에이전트 판단 · 제안 → 담당자 승인(1회) → 시스템 처리 → 시스템 결과 확인 → ◇ → 결과 보고(정상 | 미달) → 끝

  A 긴급 대응: 쿨러 경보 → 제안 → 운전원 승인(멈추지 않는 승인 지연 알림 타이머) → 냉각 명령 → 재관측 → 정상이면 작업지시 → 결과 보고
  B 정기 정비: PM_DUE(운전시간 계수기) → 정비 일정 제안 → 승인 → 정비 오더 · 생산팀 공지 → 예정된 정비 시간에 정비 → 시운전 확인 → 결과 보고
  C 예비품 구매: SPARE_BELOW_MIN(재고) → 발주안 제안 → 구매 담당 승인 → ERP 발주 · 공급사 메일 → 입고 확인(납기 초과 타이머) → 결과 보고

2차 승인 · 사람 확인 task 는 없다. 미달 가지(A 냉각 미회복 · B 시운전 기준 미달 · C 납기 초과)는 실제로 밟아 본다.
뒤쪽에는 부품 일반 시험(가져오기 거절 · 설정 오류 · 승인 기록 없는 효과 거절 · 작업지시 뒤 재관측)이 있다."""
from copy import deepcopy
from datetime import timedelta

import pytest

from procsvc import bpmn_import as B, business_monitor, decisions, engine, machine
from entsim import state as entstate
from test_instance_mode import world, ALERT, NOW, NoFx, _row  # noqa: F401  (world 는 fixture)

NS = 'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'
USERS = [{"id": "role:purchasing", "username": "구매 담당"}]


def xml(body: str, pid: str, lanes: str = "") -> str:
    lane_set = f"<bpmn:laneSet id=\"LS\">{lanes}</bpmn:laneSet>" if lanes else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<bpmn:definitions {NS} id="D1"><bpmn:process id="{pid}" name="{pid}">'
            f'{lane_set}{body}</bpmn:process></bpmn:definitions>')


def lanes(person: list[str], agent: list[str], system: list[str]) -> str:
    def lane(lid, name, nodes):
        return f'<bpmn:lane id="{lid}" name="{name}">' + "".join(f"<bpmn:flowNodeRef>{n}</bpmn:flowNodeRef>" for n in nodes) + "</bpmn:lane>"
    return lane("L_person", "담당자", person) + lane("L_agent", "에이전트", agent) + lane("L_system", "시스템", system)


def agent_task(instruction: str) -> dict:
    """'판단 · 제안' 에이전트 task 하나 = task:decide (기준 task:rank 계약, 앞 단계 없이 경보 값만 받음). 결과 decision · decision_id 는
    승인 경로가 믿는 값이라 이 부품만 낸다. 에이전트가 그 안에서 진단 · 후보 · 규정 · 순위(evaluate_cards)를 하고 카드를 낸다."""
    return {"part": "task:decide", "instruction": instruction}


def report(outcome: str, title: str, summary: str = "") -> dict:
    return {"part": "svc:report", "config": {"outcome": outcome, "title": title, "summary": summary}}


# ================================================================ A 긴급 대응
A_FLOW = xml("""
  <bpmn:startEvent id="Start" name="쿨러 과열 경보"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:task id="T_agent" name="원인 진단 · 냉각 조치 제안"/>
  <bpmn:userTask id="T_approve" name="운전원 승인"/>
  <bpmn:boundaryEvent id="B_overdue" name="승인 지연" attachedToRef="T_approve" cancelActivity="false"><bpmn:timerEventDefinition id="TD1"/></bpmn:boundaryEvent>
  <bpmn:serviceTask id="T_notice" name="승인 지연 알림"/>
  <bpmn:serviceTask id="T_cmd" name="냉각 명령"/>
  <bpmn:serviceTask id="T_reobs" name="재관측"/>
  <bpmn:exclusiveGateway id="G_ok" name="유온 정상?"/>
  <bpmn:serviceTask id="T_wo" name="작업지시 등록"/>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 정상"/>
  <bpmn:serviceTask id="R_fail" name="결과 보고: 미달"/>
  <bpmn:endEvent id="E_notice" name="알림"/>
  <bpmn:endEvent id="E_end" name="끝"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="T_cmd"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_cmd" targetRef="T_reobs"/>
  <bpmn:sequenceFlow id="F5" sourceRef="T_reobs" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="예" sourceRef="G_ok" targetRef="T_wo"/>
  <bpmn:sequenceFlow id="F_no" name="아니오" sourceRef="G_ok" targetRef="R_fail"/>
  <bpmn:sequenceFlow id="F6" sourceRef="T_wo" targetRef="R_ok"/>
  <bpmn:sequenceFlow id="F7" sourceRef="R_ok" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F8" sourceRef="R_fail" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F9" sourceRef="B_overdue" targetRef="T_notice"/>
  <bpmn:sequenceFlow id="F10" sourceRef="T_notice" targetRef="E_notice"/>""", "Process_A",
             lanes(["T_approve"], ["T_agent"], ["T_notice", "T_cmd", "T_reobs", "T_wo", "R_ok", "R_fail"]))


def a_mapping():
    return {"name": "긴급 대응 (시험)", "start": {"kind": "alert", "patterns": ["COOLER_DEGRADATION"]}, "lanes": {},
            "tasks": {"T_agent": agent_task("쿨러 과열의 원인을 진단하고 냉각 조치 카드를 낸다"),
                      "T_approve": {"part": "task:select"},
                      "T_notice": report("승인 지연", "{asset} 냉각 조치 승인 지연", "승인 대기 중 — 경보 {alert.alertId}"),
                      "T_cmd": {"part": "task:command"}, "T_reobs": {"part": "task:reobserve"}, "T_wo": {"part": "task:work-order"},
                      "R_ok": report("정상", "{asset} 긴급 대응 결과", "유온 정상 · 경보 해제, 작업지시 {work_order.ref}"),
                      "R_fail": report("미달", "{asset} 긴급 대응 결과", "재관측 기준 미달 — 승인자 {approved_by}")},
            "timers": {"B_overdue": "PT10M"},
            "flows": {"F_yes": {"var": "recovered", "op": "==", "value": True}, "F_no": {"default": True}}}


def a_decision(inc_id):
    opt = {"id": "skill:fan-max-derate", "sopId": "SOP-COOL-12", "name": "팬 최대 + 부하 80 %", "kind": "control", "feasible": True, "rank": 1,
           "approver": {"id": "role:prod-mgr", "name": "생산관리자", "level": 2},
           "actions": [{"code": "FAN_SET", "kind": "command", "param": "fan_pct", "value": 100, "target": "sys:scada"},
                       {"code": "LOAD_SET", "kind": "command", "param": "load_pct", "value": 80, "target": "sys:scada"},
                       {"code": "WO_CREATE", "kind": "transaction", "value": "SOP-COOL-14", "target": "sys:cmms"}],
           "violations": [], "penalties": [], "warnings": []}
    return decisions.new({"id": "DEC-A-1", "schema": "v2", "asset": "HYD-01",
                          "origin": {"kind": "alert", "incident": inc_id, "cause": "cause:cooler-fin-fouling", "failureMode": "fm:cooling-loss"},
                          "recommended": opt["id"], "explanation": "납기 오더 진행 중 — 팬 최대 + 부하 80 %", "options": [opt],
                          "roles": {"role:operator": {"level": 1}, "role:prod-mgr": {"level": 2}}})


GUIDE = {"recommended": [
    {"code": "FAN_SET", "actionId": "act:fan-set", "kind": "command", "param": "fan_pct", "value": 100, "paramRange": [0, 100]},
    {"code": "LOAD_SET", "actionId": "act:load-set", "kind": "command", "param": "load_pct", "value": 80, "paramRange": [50, 100]},
    {"code": "WO_CREATE", "actionId": "act:wo", "kind": "work_order"}], "causes": [{"id": "cause:cooler-fin-fouling"}],
    "topCause": "cause:cooler-fin-fouling"}


def open_a(world):
    deploy(world, A_FLOW, a_mapping(), "a_emergency")
    rt = world["rt"]
    inst = rt.on_alert_raise(dict(ALERT, alertId="HYD-01-A-1"), now=NOW)
    assert inst["proc_def_id"] == "a_emergency"
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = a_decision(inc.id)
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss",
                                               "guide_card": GUIDE, "decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    assert inc.card["recommended"] == GUIDE["recommended"]                  # 설비 명령 승인은 가이드 카드의 조치만 받는다
    return rt, inst, inc, d


def a_approve_and_ack(rt, inst, inc, d):
    rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "이생산", "role:prod-mgr", now=NOW)
    assert inc.state == "AWAITING_ACK" and _row(rt, inst, "T_cmd")["status"] == "SUBMITTED"
    machine.on_status(inc, {"cmdId": inc.cmd_id, "result": "DONE", "t": "2026-10-03T12:00:05Z"}, NOW, NoFx(), time_scale=20)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    assert inc.state == "RE_OBSERVING" and _row(rt, inst, "T_reobs")["status"] == "SUBMITTED"


def test_a_cooling_recovers_then_work_order_and_a_normal_result_report(world):
    rt, inst, inc, d = open_a(world)
    a_approve_and_ack(rt, inst, inc, d)
    machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, NoFx())
    machine.on_timer(inc, "reobs", NOW, 50.0, NoFx(), time_scale=20)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert done["status"] == "COMPLETED" and inc.state == "CLOSED" and world["executed"][-1][1] == "WO_CREATE"
    rep = engine.variables(done)["result_report"]
    assert (rep["outcome"], rep["level"]) == ("정상", "ok") and "WO-1003-AB12" in rep["summary"] and rep["refs"]["work_order"] == "WO-1003-AB12"
    assert _row(rt, inst, "R_fail")["status"] != "DONE" and "RESULT_REPORT" in world["audits"]


def test_a_cooling_not_recovered_takes_the_shortfall_branch_without_a_human_task(world):
    rt, inst, inc, d = open_a(world)
    a_approve_and_ack(rt, inst, inc, d)
    machine.on_timer(inc, "reobs", NOW, 61.0, NoFx(), time_scale=20)          # 유온 61 ℃ — 기준(55 ℃) 밖, 경보 해제 없음
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert inc.state == "ESCALATED" and done["status"] == "COMPLETED" and done["end_event"] == "E_end"
    rep = engine.variables(done)["result_report"]
    assert (rep["outcome"], rep["level"]) == ("미달", "fail") and "이생산" in rep["summary"]
    assert _row(rt, inst, "T_wo")["status"] != "DONE" and all(w["user_id"] != "role:prod-mgr" or w["activity_id"] == "T_approve"
                                                              for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"]))


def test_a_approval_overdue_only_notifies_and_the_operator_can_still_approve(world):
    rt, inst, inc, d = open_a(world)
    timer = _row(rt, inst, "B_overdue")
    assert timer["due_date"] == engine.now_iso(NOW + timedelta(seconds=600 / 20))               # 사람 응답 타이머는 배속만
    rt.fire_timeouts(now=NOW + timedelta(seconds=31))
    rt.reconcile_services(now=NOW + timedelta(seconds=31))                         # 시스템 task 는 2초 폴링이 실행한다
    notice = _row(rt, inst, "T_notice")
    assert notice["status"] == "DONE" and notice["output"]["result_report"]["level"] == "info"
    assert _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS" and inc.state == "AWAITING_APPROVAL"   # 알림만, 승인은 계속
    assert rt.repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING"
    a_approve_and_ack(rt, inst, inc, d)                                           # 알림 뒤에도 승인할 수 있다(마감이 아니다)
    machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, NoFx())
    machine.on_timer(inc, "reobs", NOW, 50.0, NoFx(), time_scale=20)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert done["status"] == "COMPLETED" and done["end_event"] == "E_end" and engine.variables(done)["result_report"]["outcome"] == "정상"


# ================================================================ B 정기 정비
B_FLOW = xml("""
  <bpmn:startEvent id="Start" name="정기 정비 도래"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:task id="T_agent" name="정비 일정 제안"/>
  <bpmn:userTask id="T_approve" name="설비보전팀장 승인"/>
  <bpmn:serviceTask id="T_wo" name="정비 오더 · 생산팀 공지"/>
  <bpmn:serviceTask id="T_do" name="예정된 시간에 정비 수행"/>
  <bpmn:serviceTask id="T_run" name="시운전 확인"/>
  <bpmn:exclusiveGateway id="G_pass" name="기준 통과?"/>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 정상"/>
  <bpmn:serviceTask id="R_fail" name="결과 보고: 미달"/>
  <bpmn:endEvent id="E_end" name="끝"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="T_wo"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_wo" targetRef="T_do"/>
  <bpmn:sequenceFlow id="F5" sourceRef="T_do" targetRef="T_run"/>
  <bpmn:sequenceFlow id="F6" sourceRef="T_run" targetRef="G_pass"/>
  <bpmn:sequenceFlow id="F_yes" name="예" sourceRef="G_pass" targetRef="R_ok"/>
  <bpmn:sequenceFlow id="F_no" name="아니오" sourceRef="G_pass" targetRef="R_fail"/>
  <bpmn:sequenceFlow id="F7" sourceRef="R_ok" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F8" sourceRef="R_fail" targetRef="E_end"/>""", "Process_B",
             lanes(["T_approve"], ["T_agent"], ["T_wo", "T_do", "T_run", "R_ok", "R_fail"]))

PRODUCTION_NOTICE = {"to": "production@hyd.local", "subject": "[정비 공지] {asset} {work_order.after.window}",
                     "body": "작업지시 {work_order.ref} — 예정된 정비 시간에 {asset} 정지"}


def b_mapping():
    return {"name": "정기 정비 (시험)", "start": {"kind": "alert", "patterns": ["PM_DUE"]}, "lanes": {},
            "tasks": {"T_agent": agent_task("운전시간 · 허용 오차 · 생산 오더 · 인력 · 부품을 저울질해 정비 일정 카드를 낸다"),
                      "T_approve": {"part": "task:select"},
                      "T_wo": {"part": "task:work-order", "config": {"mail": PRODUCTION_NOTICE, "window_var": "alert.evidence.night_window_id"}},
                      "T_do": {"part": "svc:maintenance", "config": {"component": "pump", "sop": "SOP-PMP-04",
                                                                     "until": "work_order.after.window_starts_at"}},
                      "T_run": {"part": "svc:test-run"},
                      "R_ok": report("정상", "{asset} 정기 정비 결과", "시운전 정상 — {test_run.counter.detail}"),
                      "R_fail": report("미달", "{asset} 정기 정비 결과", "시운전 기준 미달 — 계수기는 리셋하지 않음")},
            "timers": {}, "flows": {"F_yes": {"var": "passed", "op": "==", "value": True}, "F_no": {"default": True}}}


def pm_alert():
    st = entstate.EnterpriseState()
    for a in ("HYD-01", "HYD-02", "HYD-03"):
        st.execute({"skill": "skill:pm-advance", "decision": f"cls-{a}", "asset": a, "params": {"hours": 300}})
    alert = business_monitor.build_alert(business_monitor.RULES[1], st.pm_status("HYD-02")["facts"], NOW)
    assert alert["alertId"] == "CMMS-PM_DUE-HYD-02-C1"
    return alert


def b_decision(inc_id):
    opt = {"id": "skill:pm-tonight-single", "sopId": "SOP-PM-21", "name": "오늘 밤 HYD-02 단독 정기 정비", "kind": "work_order", "feasible": True,
           "rank": 1, "approver": {"id": "role:prod-mgr", "name": "생산관리자", "level": 2},
           "actions": [{"code": "WO_CREATE", "kind": "transaction", "value": "SOP-PM-21", "target": "sys:cmms"}],
           "violations": [], "penalties": [], "warnings": []}
    return decisions.new({"id": "DEC-B-1", "schema": "v2", "asset": "HYD-02",
                          "origin": {"kind": "alert", "incident": inc_id, "cause": "cause:pm-interval", "failureMode": "fm:volumetric-loss"},
                          "recommended": opt["id"], "explanation": "허용 오차 안 · 납기 영향 최소", "options": [opt],
                          "roles": {"role:operator": {"level": 1}, "role:prod-mgr": {"level": 2}}})


def run_b(world, readings):
    deploy(world, B_FLOW, b_mapping(), "b_pm")
    out = Outside(world)
    out.tags = dict(readings)
    rt = world["rt"]
    inst = rt.on_alert_raise(pm_alert(), now=NOW)
    assert inst["proc_def_id"] == "b_pm"
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = b_decision(inc.id)
    world["book"][d["id"]] = d
    window = engine.variables(inst)["alert"]["evidence"]["night_window_id"]
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "김보전", "role:prod-mgr", now=NOW)
    return rt, inst, inc, out, window


GOOD = {"PS1": 182.0, "FS1": 9.0, "VS1": 0.6}


def test_b_pm_due_case_waits_for_the_scheduled_time_maintains_checks_and_resets_the_counter(world):
    rt, inst, inc, out, window = run_b(world, GOOD)
    wo = out.calls[0]
    assert wo["code"] == "WO_CREATE" and wo["window"] == window                     # 승인된 정비 시간이 작업지시에 실린다
    assert inc.state == "CLOSED" and out.mails[0][2]["to"] == "production@hyd.local" and out.mails[0][3].endswith(":notice")
    do = _row(rt, inst, "T_do")
    assert do["status"] == "SUBMITTED" and do["draft"]["wait"]["real_s"] == pytest.approx(9 * 3600 / 1200)   # 9 h → 27 s (배속 × 수업 압축)
    rt.reconcile_services(now=NOW + timedelta(seconds=10))
    assert out.restores == [] and _row(rt, inst, "T_do")["status"] == "SUBMITTED"            # 아직 예정된 시간 전
    rt.reconcile_services(now=NOW + timedelta(seconds=28))
    assert out.restores == [("HYD-02", "pump")] and [c["code"] for c in out.calls] == ["WO_CREATE", "WO_COMPLETE"]
    run = _row(rt, inst, "T_run")
    assert run["status"] == "SUBMITTED" and run["draft"]["settle"]["real_s"] == 30.0          # 안정 10 분 ÷ 20배속 (압축 없음 — 물리)
    rt.reconcile_services(now=NOW + timedelta(seconds=60))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert done["status"] == "COMPLETED" and v["passed"] is True and [c["code"] for c in out.calls][-1] == "PM_RESET"
    assert v["result_report"]["outcome"] == "정상" and "계수기 리셋" in v["result_report"]["summary"]
    assert {r["tag"]: r["ok"] for r in v["test_run"]["readings"]} == {"PS1": True, "FS1": True, "VS1": True}


def test_b_test_run_below_criteria_takes_the_shortfall_branch_and_keeps_the_counter(world):
    rt, inst, inc, out, _ = run_b(world, dict(GOOD, PS1=158.0))                 # 정비 뒤에도 압력 158 bar < 165 (정비 불량)
    rt.reconcile_services(now=NOW + timedelta(seconds=28))
    rt.reconcile_services(now=NOW + timedelta(seconds=60))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert done["status"] == "COMPLETED" and v["passed"] is False and v["result_report"]["outcome"] == "미달"
    assert "PM_RESET" not in [c["code"] for c in out.calls]                       # 미달이면 계수기를 리셋하지 않는다
    assert next(r for r in v["test_run"]["readings"] if r["tag"] == "PS1") == {"tag": "PS1", "op": ">=", "limit": 165.0, "value": 158.0, "ok": False}


def test_b_unknown_reading_is_a_shortfall_not_a_pass(world):
    rt, inst, inc, out, _ = run_b(world, dict(GOOD, VS1=None))
    rt.reconcile_services(now=NOW + timedelta(seconds=28))
    rt.reconcile_services(now=NOW + timedelta(seconds=60))
    assert engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))["passed"] is False


# ================================================================ C 예비품 구매
C_FLOW = xml("""
  <bpmn:startEvent id="Start" name="재고 기준 이탈"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:task id="T_agent" name="발주안 제안"/>
  <bpmn:userTask id="T_approve" name="구매 담당 승인"/>
  <bpmn:serviceTask id="T_po" name="ERP 발주 · 공급사 메일"/>
  <bpmn:serviceTask id="T_gr" name="입고 확인"/>
  <bpmn:boundaryEvent id="B_late" name="납기 초과" attachedToRef="T_gr"><bpmn:timerEventDefinition id="TD1"/></bpmn:boundaryEvent>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 입고 완료"/>
  <bpmn:serviceTask id="R_late" name="결과 보고: 지연"/>
  <bpmn:endEvent id="E_done" name="입고 완료"/>
  <bpmn:endEvent id="E_late" name="지연"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="T_po"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_po" targetRef="T_gr"/>
  <bpmn:sequenceFlow id="F5" sourceRef="T_gr" targetRef="R_ok"/>
  <bpmn:sequenceFlow id="F6" sourceRef="R_ok" targetRef="E_done"/>
  <bpmn:sequenceFlow id="F7" sourceRef="B_late" targetRef="R_late"/>
  <bpmn:sequenceFlow id="F8" sourceRef="R_late" targetRef="E_late"/>""", "Process_C",
             lanes(["T_approve"], ["T_agent"], ["T_po", "T_gr", "R_ok", "R_late"]))

SUPPLIER_MAIL = {"to": "supplier@hyd.local, receiving@hyd.local", "subject": "[발주] {approved_part_no} {approved_qty}개",
                 "body": "공급사 {approved_supplier}, 금액 {approved_amount}만원, 발주 번호 {purchase_order.ref}"}


def c_mapping(late="P6D"):
    return {"name": "예비품 구매 (시험)", "start": {"kind": "alert", "patterns": ["SPARE_BELOW_MIN"]}, "lanes": {},
            "tasks": {"T_agent": agent_task("필요량을 정하고 공급사를 총비용 · 품질 · 납기 · 규정으로 비교해 발주 카드를 낸다"),
                      "T_approve": {"part": "task:select"},
                      "T_po": {"part": "svc:erp-po", "config": {"mail": SUPPLIER_MAIL}},
                      "T_gr": {"part": "svc:goods-receipt"},
                      "R_ok": report("입고 완료", "{approved_part_no} 발주 결과", "{goods_receipt.detail}"),
                      "R_late": report("지연", "{approved_part_no} 발주 결과", "납기 초과 — 발주 {purchase_order.ref}, 공급사 {approved_supplier}")},
            "timers": {"B_late": late}, "flows": {}}


def stock_alert(need_qty=6):
    row = {"part_no": "P-PMP-SEAL", "name": "펌프 축 씰 키트", "on_hand": 3, "reserved": 2, "available": 1, "on_order": 0, "spare_gap": -1,
           "reorder_point": 2, "target_stock": 7, "need_qty": need_qty, "below_reorder_point": True,
           "below_since": "2026-10-03T11:59:00+00:00", "reserved_for": "HYD-03"}
    return business_monitor.build_alert(business_monitor.RULES[0], row, NOW)


def c_decision(inc_id):
    opts = []
    for sup, sop, name, rank, warn in (("sup:b", "SOP-PUR-11", "B-OEM 표준 발주", 1, "300만 원 초과 — 구매팀장 추가 승인(전결 기준, 표시만)"),
                                       ("sup:a", "SOP-PUR-12", "A정밀 대체 발주", 2, None)):
        opts.append({"id": f"skill:{sop.lower()}", "sopId": sop, "name": name, "kind": "work_order", "feasible": True, "rank": rank,
                     "approver": {"id": "role:prod-mgr", "name": "생산관리자", "level": 2},
                     "actions": [{"code": "PR_CREATE", "kind": "transaction", "value": sup, "target": "sys:erp"}],
                     "violations": [], "penalties": [], "warnings": [{"annotation": warn}] if warn else []})
    return decisions.new({"id": "DEC-C-1", "schema": "v2", "asset": "HYD-03",
                          "origin": {"kind": "alert", "incident": inc_id, "cause": "cause:pump-seal-wear", "failureMode": "fm:volumetric-loss"},
                          "recommended": opts[0]["id"], "explanation": "결품 방지 · 총비용", "options": opts,
                          "roles": {"role:operator": {"level": 1}, "role:prod-mgr": {"level": 2}}})


def open_c(world, need_qty=6, late="P6D", supplier="sup:b"):
    deploy(world, C_FLOW, c_mapping(late), "c_purchase")
    out = Outside(world)
    rt = world["rt"]
    inst = rt.on_alert_raise(stock_alert(need_qty), now=NOW)
    assert inst["proc_def_id"] == "c_purchase"
    inc = world["incidents"][engine.variables(inst)["incident"]]
    assert inc.state == "AWAITING_APPROVAL"
    d = c_decision(inc.id)
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    opt = next(o for o in d["options"] if o["actions"][0]["value"] == supplier)
    return rt, inst, inc, d, opt, out


def c_approve(rt, inst, d, opt):
    return rt.select(_row(rt, inst, "T_approve")["id"], d["id"], opt["id"], "박구매", "role:prod-mgr", now=NOW)


def test_c_one_approval_orders_mails_receives_and_reports_even_over_the_delegation_limit(world):
    rt, inst, inc, d, opt, out = open_c(world)
    res = c_approve(rt, inst, d, opt)
    assert res["purchase"]["approved_amount"] == 330 and res["purchase"]["quote"]["lead_d"] == 5     # 300만 원 초과 — 2차 승인 없이 바로 발주
    v = engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))
    assert (v["approved_supplier"], v["approved_qty"], v["approved_unit_price"], v["approved_amount"]) == ("sup:b", 6, 55, 330)
    assert [c["code"] for c in out.calls] == ["PR_CREATE"] and out.calls[0]["amount"] == 330 and out.calls[0]["qty"] == 6
    server, tool, args, key = out.mails[0]
    assert (server, tool) == ("hyd-effects", "send_mail") and args["subject"] == "[발주] P-PMP-SEAL 6개"
    assert "금액 330만원" in args["body"] and "PR-1" in args["body"] and key.endswith(":notice")
    assert _row(rt, inst, "T_po")["output"]["purchase_order"]["notice"]["tool"] == "send_mail"
    gr = _row(rt, inst, "T_gr")
    assert gr["status"] == "SUBMITTED" and gr["draft"]["wait"]["real_s"] == pytest.approx(5 * 86400 / (20 * 60), rel=1e-3)
    assert _row(rt, inst, "B_late")["due_date"] == engine.now_iso(NOW + timedelta(seconds=6 * 86400 / 1200))   # 납기 초과 6일 → 7.2분
    rt.reconcile_services(now=NOW + timedelta(seconds=100))
    assert _row(rt, inst, "T_gr")["status"] == "SUBMITTED"
    rt.reconcile_services(now=NOW + timedelta(seconds=361))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert [c["code"] for c in out.calls] == ["PR_CREATE", "GR_CONFIRM"] and done["end_event"] == "E_done" and inc.state == "CLOSED"
    assert v["received"] is True and v["result_report"]["outcome"] == "입고 완료" and v["result_report"]["summary"] == "입고 · 검수 합격"
    events = [e["job_id"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])]
    assert "MCP_EFFECT_CALL" in events and "GOODS_RECEIVED" in events and "RESULT_REPORT" in events


def test_c_supplier_delay_makes_the_due_date_timer_fire_and_a_delay_report_without_receipt(world):
    rt, inst, inc, d, opt, out = open_c(world)
    c_approve(rt, inst, d, opt)
    out.delay_d = 3                                                               # 수업 버튼 '공급사 납기 지연 +3일'
    rt.reconcile_services(now=NOW + timedelta(seconds=361))                       # 원래 입고 예정 — 늦어진 예정을 다시 읽고 더 기다린다
    gr = _row(rt, inst, "T_gr")
    assert gr["status"] == "SUBMITTED" and gr["draft"]["wait"]["delay_d"] == 3
    rt.fire_timeouts(now=NOW + timedelta(seconds=433))                            # 납기 초과(6일) 타이머가 입고(5 + 3일)보다 먼저
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert done["end_event"] == "E_late" and _row(rt, inst, "T_gr")["status"] == "CANCELLED"
    assert [c["code"] for c in out.calls] == ["PR_CREATE"] and inc.state == "ESCALATED"      # 입고는 기록하지 않았다
    assert (v["result_report"]["outcome"], v["result_report"]["level"]) == ("지연", "fail") and "PR-1" in v["result_report"]["summary"]
    assert "RECEIPT_DELAYED" in [e["job_id"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])]


def test_c_cheaper_alternative_is_ordered_when_the_buyer_picks_it(world):
    rt, inst, inc, d, opt, out = open_c(world, supplier="sup:a")
    assert c_approve(rt, inst, d, opt)["purchase"]["approved_amount"] == 210
    assert [c["code"] for c in out.calls] == ["PR_CREATE"] and out.calls[0]["value"] == "sup:a"


def test_c_unknown_quantity_refuses_the_approval(world):
    rt, inst, inc, d, opt, out = open_c(world, need_qty=None)
    with pytest.raises(ValueError, match="수량"):
        c_approve(rt, inst, d, opt)
    assert _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS" and out.calls == []


# ================================================================ 가져오기 · 등록 검사 (일반 부품)
def deploy(world, source, mapping, did):
    _, r = imported(world, source, mapping, did)
    assert r["ok"], r["problems"]
    rt = world["rt"]
    rt.register_definition(r["definition"])
    rt.deploy_definition(did, "1", "tester", "C2 시험")
    return r["definition"]


def imported(world, source, mapping, did):
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    cat = B.catalog(base, USERS)
    parsed = B.parse_bpmn(source)
    return cat, B.check(parsed, mapping, {"catalog": cat, "definition_id": did, "version": "1", "file_name": f"{did}.bpmn", "xml_sha256": "x"})


def test_catalog_offers_the_generic_parts_and_both_business_patterns(world):
    cat, r = imported(world, C_FLOW, c_mapping(), "c_purchase")
    parts = {p["key"]: p for p in cat["parts"]}
    for key, tool in (("svc:mcp-call", "mcp:call"), ("svc:erp-po", "enterprise:PR_CREATE"), ("svc:wait", "process:wait"),
                      ("svc:maintenance", "plant:restore"), ("svc:goods-receipt", "enterprise:GR_CONFIRM"),
                      ("svc:test-run", "plant:test-run"), ("svc:report", "process:report")):
        assert parts[key]["group"] == "general" and parts[key]["kind"] == "service" and parts[key]["tool"] == tool
    assert parts["svc:wait"]["effect"] is None and parts["svc:report"]["effect"] is None and parts["svc:erp-po"]["effect"] == "ERP 발주"
    assert {"SPARE_BELOW_MIN", "PM_DUE"} <= set(cat["patterns"]) and set(cat["business_patterns"]) == {"SPARE_BELOW_MIN", "PM_DUE"}
    assert r["ok"], r["problems"]
    d = r["definition"]
    acts = {a["id"]: a for a in d["activities"]}
    assert len(acts) == 6 and acts["T_po"]["service"]["mail"]["to"].startswith("supplier@")
    assert acts["T_gr"]["outputData"] == ["goods_receipt", "received"] and acts["R_late"]["outputData"] == ["result_report"]
    assert d["alertPolicy"]["patterns"]["SPARE_BELOW_MIN"]["tag"] == "ERP_SPARE_BELOW_MIN"
    assert not any(s.get("condition") and "approved_amount" in s["condition"] for s in d["sequences"])   # 금액 분기 없음


def test_shapes_stay_small_enough_to_draw(world):
    """세 흐름 모두 task 6~8개 · 레인 3개(담당자 / 에이전트 / 시스템), 사람 task 는 승인 하나."""
    for src, mapping, did in ((A_FLOW, a_mapping(), "a"), (B_FLOW, b_mapping(), "b"), (C_FLOW, c_mapping(), "c")):
        parsed = B.parse_bpmn(src)
        assert len(parsed["tasks"]) <= 8 and [l["name"] for l in parsed["lanes"]] == ["담당자", "에이전트", "시스템"]
        _, r = imported(world, src, mapping, did)
        assert r["ok"], r["problems"]
        humans = [a for a in r["definition"]["activities"] if a.get("tool") == "formHandler:select_card"]
        assert len(humans) == 1


def test_non_interrupting_timer_is_imported_as_a_notice_branch(world):
    _, r = imported(world, A_FLOW, a_mapping(), "a")
    ev = next(e for e in r["definition"]["events"] if e["id"] == "B_overdue")
    assert ev["cancelActivity"] is False and ev["timer"] == "PT10M"


def test_mcp_write_before_the_human_approval_is_refused(world):
    m = c_mapping()
    m["tasks"]["T_agent"] = {"part": "svc:mcp-call", "config": {"server": "hyd-effects", "tool": "send_mail", "arguments": {"to": "x@y"}}}
    _, r = imported(world, C_FLOW, m, "bad")
    assert not r["ok"] and any("사람 승인" in p["reason"] and p["where"]["id"] == "T_agent" for p in r["problems"])


@pytest.mark.parametrize("key,config,phrase", [
    ("svc:mcp-call", {"server": "Bad Name", "tool": "send_mail"}, "MCP 서버 이름"),
    ("svc:wait", {}, "duration(기간) 또는 until"),
    ("svc:wait", {"duration": "9시간"}, "읽을 수 없습니다"),
    ("svc:maintenance", {"component": "boiler"}, "복구 부품"),
    ("svc:test-run", {"criteria": {"PS1": ["~", 1]}}, "시운전 기준"),
    ("svc:report", {"outcome": "대충"}, "결과 보고의 결과"),
    ("svc:erp-po", {"mail": {"subject": "x"}}, "받는 사람"),
])
def test_part_config_problems_are_reported_at_the_task(world, key, config, phrase):
    m = c_mapping()
    m["tasks"]["R_ok"] = {"part": key, "config": config}
    _, r = imported(world, C_FLOW, m, "bad")
    assert not r["ok"] and any(phrase in p["reason"] and p["where"]["id"] == "R_ok" and p["field"] == "config" for p in r["problems"]), r["problems"]


def test_work_order_mail_config_is_checked(world):
    m = b_mapping()
    m["tasks"]["T_wo"] = {"part": "task:work-order", "config": {"mail": {"to": "p@hyd.local"}}}
    _, r = imported(world, B_FLOW, m, "bad")
    assert not r["ok"] and any("제목" in p["reason"] and p["where"]["id"] == "T_wo" for p in r["problems"])


def test_effect_part_refuses_to_run_without_an_approval_record(world):
    rt, inst, inc, d, opt, out = open_c(world)
    wi = _row(rt, inst, "T_po")
    with pytest.raises(ValueError, match="사람 승인 뒤에만"):
        rt._run_purchase_order(rt.repo.get_instance(inst["proc_inst_id"]), wi, NOW)
    assert out.calls == []


# ================================================================ 가짜 바깥 (업무 · 메일 · 설비 · 시계열)
class Outside:
    def __init__(self, world, lead_d=5):
        self.calls, self.mails, self.restores, self.lead_d, self.delay_d = [], [], [], lead_d, 0
        ctx, rt = world["ctx"], world["rt"]
        ctx.exec_skill = self.exec_skill
        rt.hooks.enterprise_read = self.read
        rt.hooks.mcp_call = self.mcp
        rt.hooks.plant_restore = self.restore
        rt.hooks.read_tag = lambda asset, tag: self.tags.get(tag)
        ctx.latest_tag = lambda asset, tag: self.value
        self.value = 48.0
        self.tags = dict(GOOD)

    QUOTES = [{"supplier": "sup:a", "name": "A정밀", "price": 35, "lead_d": 2, "avl": True},
              {"supplier": "sup:b", "name": "B-OEM", "price": 55, "lead_d": 5, "avl": True},
              {"supplier": "sup:c", "name": "C트레이딩", "price": 20, "lead_d": 1, "avl": False}]

    def read(self, name, params):
        if name == "part_quotes":
            assert params == {"part": "P-PMP-SEAL"}
            return {"records": deepcopy(self.QUOTES)}
        if name == "purchase_order":
            return {"facts": {"id": params["ref"], "lead_d": self.lead_d, "delay_d": self.delay_d}}
        raise KeyError(name)

    def exec_skill(self, d, item):
        self.calls.append(deepcopy(item))
        code = item["code"]
        out = {"ok": True, "skill": item["skill"], "code": code, "system": item.get("system")}
        if code == "PR_CREATE":
            return out | {"ref": "PR-1", "detail": f"{item['qty']}개 발주", "after": {"lead_d": self.lead_d, "delay_d": 0, "amount": item["amount"]}}
        if code == "GR_CONFIRM":
            return out | {"ref": "GR-1", "detail": "입고 · 검수 합격"}
        if code == "WO_CREATE":
            return out | {"ref": "WO-1", "detail": "작업지시", "after": {"window": "야간 정비 시간 10-03 21:00",
                                                                     "window_starts_at": engine.now_iso(NOW + timedelta(hours=9))}}
        if code == "WO_COMPLETE":
            return out | {"ref": "WO-1", "detail": "작업지시 WO-1 완료"}
        if code == "PM_RESET":
            return out | {"ref": "PMR-1", "detail": "HYD-02 운전시간 계수기 리셋 (1950 h 에 정기 정비) — 다음 기한 2000 h"}
        raise AssertionError(code)

    def mcp(self, server, tool, arguments, key):
        self.mails.append((server, tool, deepcopy(arguments), key))
        return {"status": "ok", "result": {"is_error": False, "text": '{"result": "ok"}'}, "arguments": arguments, "idempotent": True}

    def restore(self, asset, component):
        self.restores.append((asset, component))
        return {"ok": True, "asset": asset, "kind": "restore", "targets": {"leak": 0.0}}


# ================================================================ 일반 정비형: 작업지시(정비 시간) → 대기 → 정비 모사 → 작업지시 뒤 재관측
MAINT = xml("""
  <bpmn:startEvent id="Start" name="경보"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:task id="T_agent" name="제안"/>
  <bpmn:userTask id="T_approve" name="제안 승인"/>
  <bpmn:serviceTask id="T_wo" name="CMMS 예약"/>
  <bpmn:serviceTask id="T_wait" name="예정된 정비 시간까지 대기"/>
  <bpmn:serviceTask id="T_do" name="정비 수행 (모사)"/>
  <bpmn:serviceTask id="T_check" name="효과 재관측"/>
  <bpmn:exclusiveGateway id="G_rec" name="회복?"/>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 정상"/>
  <bpmn:serviceTask id="R_fail" name="결과 보고: 미달"/>
  <bpmn:endEvent id="E_end" name="끝"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="T_wo"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_wo" targetRef="T_wait"/>
  <bpmn:sequenceFlow id="F5" sourceRef="T_wait" targetRef="T_do"/>
  <bpmn:sequenceFlow id="F6" sourceRef="T_do" targetRef="T_check"/>
  <bpmn:sequenceFlow id="F7" sourceRef="T_check" targetRef="G_rec"/>
  <bpmn:sequenceFlow id="F_ok" name="회복" sourceRef="G_rec" targetRef="R_ok"/>
  <bpmn:sequenceFlow id="F_no" name="미회복" sourceRef="G_rec" targetRef="R_fail"/>
  <bpmn:sequenceFlow id="F8" sourceRef="R_ok" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F9" sourceRef="R_fail" targetRef="E_end"/>""", "Process_maint")


def maint_mapping():
    return {"name": "정비형 (시험)", "start": {"kind": "alert", "patterns": ["COOLER_DEGRADATION"]}, "lanes": {},
            "tasks": {"T_agent": agent_task("정비 시점을 고른다"),
                      "T_approve": {"part": "task:select"},
                      "T_wo": {"part": "task:work-order"},
                      "T_wait": {"part": "svc:wait", "config": {"until": "work_order.after.window_starts_at", "label": "예정된 정비 시간까지"}},
                      "T_do": {"part": "svc:maintenance", "config": {"component": "cooler", "sop": "SOP-COOL-04"}},
                      "T_check": {"part": "task:reobserve"},
                      "R_ok": report("정상", "{asset} 정비 결과"), "R_fail": report("미달", "{asset} 정비 결과")},
            "timers": {}, "flows": {"F_ok": {"var": "recovered", "op": "==", "value": True}, "F_no": {"default": True}}}


def maintenance_decision(inc_id):
    opt = {"id": "skill:wo-cooler-clean", "sopId": "SOP-COOL-04", "name": "쿨러 핀 세척", "kind": "work_order", "feasible": True, "rank": 1,
           "approver": {"id": "role:prod-mgr", "name": "생산관리자", "level": 2},
           "actions": [{"code": "WO_CREATE", "kind": "transaction", "value": "SOP-COOL-04", "target": "sys:cmms"}],
           "violations": [], "penalties": [], "warnings": []}
    return decisions.new({"id": "DEC-M-1", "schema": "v2", "asset": "HYD-01",
                          "origin": {"kind": "alert", "incident": inc_id, "cause": "cause:cooler-fin-fouling", "failureMode": "fm:cooling-loss"},
                          "recommended": opt["id"], "explanation": "야간 정비 시간", "options": [opt],
                          "roles": {"role:operator": {"level": 1}, "role:prod-mgr": {"level": 2}}})


def run_maintenance(world, value):
    deploy(world, MAINT, maint_mapping(), "maint_plan")
    out = Outside(world)
    out.value = value
    rt = world["rt"]
    inst = rt.on_alert_raise(dict(ALERT, alertId="HYD-01-C2-1"), now=NOW)
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = maintenance_decision(inc.id)
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "manager", "role:prod-mgr", now=NOW)
    return rt, inst, inc, out


def test_maintenance_window_reaches_the_work_order_and_the_flow_waits_until_it(world):
    rt, inst, inc, out = run_maintenance(world, 48.0)
    assert out.calls[0]["code"] == "WO_CREATE" and "window" not in out.calls[0]          # 정비 시점 값이 없으면 전과 같다(CMMS 기본)
    assert inc.state == "CLOSED" and inc.work_order["id"] == "WO-1"
    wait = _row(rt, inst, "T_wait")
    assert wait["status"] == "SUBMITTED" and wait["draft"]["wait"]["real_s"] == pytest.approx(9 * 3600 / 1200)
    rt.reconcile_services(now=NOW + timedelta(seconds=10))
    assert _row(rt, inst, "T_wait")["status"] == "SUBMITTED" and out.restores == []


def test_maintenance_runs_then_real_reobservation_closes_the_case(world):
    rt, inst, inc, out = run_maintenance(world, 48.0)
    rt.reconcile_services(now=NOW + timedelta(seconds=30))
    assert [c["code"] for c in out.calls] == ["WO_CREATE", "WO_COMPLETE"] and out.calls[1]["ref"] == "WO-1" and out.calls[1]["sop"] == "SOP-COOL-04"
    assert out.restores == [("HYD-01", "cooler")]
    check = _row(rt, inst, "T_check")
    assert check["status"] == "SUBMITTED" and check["draft"]["reobserve"]["window_s"] == 45.0
    # 이전: 사건이 CLOSED 라는 이유만으로 recovered=True 가 바로 나갔다 — 이제 사건 갱신이 와도 관측 창을 기다린다
    rt.on_incident_update(inc.state, inc.id, True, now=NOW + timedelta(seconds=31))
    assert _row(rt, inst, "T_check")["status"] == "SUBMITTED"
    inc.cleared = True
    rt.reconcile_services(now=NOW + timedelta(seconds=80))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert done["status"] == "COMPLETED" and engine.variables(done)["recovered"] is True
    assert engine.variables(done)["result_report"]["outcome"] == "정상"
    notes = [e["job_id"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])]
    assert "MAINTENANCE_DONE" in notes and "REOBSERVATION" in notes


def test_reobservation_outside_the_criterion_reports_a_shortfall(world):
    rt, inst, inc, out = run_maintenance(world, 61.0)
    rt.reconcile_services(now=NOW + timedelta(seconds=30))
    inc.cleared = True
    rt.reconcile_services(now=NOW + timedelta(seconds=80))
    v = engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))
    assert v["recovered"] is False and v["result_report"]["outcome"] == "미달"


def test_reobservation_waits_for_the_clear_while_the_value_is_inside(world):
    rt, inst, inc, out = run_maintenance(world, 48.0)
    rt.reconcile_services(now=NOW + timedelta(seconds=30))
    rt.reconcile_services(now=NOW + timedelta(seconds=80))          # 값은 기준 안, 경보 해제 아직 → 3분의 1 창 연장
    check = _row(rt, inst, "T_check")
    assert check["status"] == "SUBMITTED" and check["draft"]["reobserve"]["extensions"] == 1
    inc.cleared = True
    rt.reconcile_services(now=NOW + timedelta(seconds=100))
    assert engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))["recovered"] is True


# ---------------------------------------------------------------- 승인 전달: 흐름이 실행할 발주는 미룬다
def test_approval_delivery_still_runs_purchase_in_flows_without_an_order_task(world):
    from test_approval_delivery import ready, choose
    rt, inst, inc, d, wi = ready(world, purchase=True)
    choose(rt, d, wi)
    assert ("DEC-1003-001-ab12", "PR_CREATE") in world["executed"]          # 기준 흐름은 전과 같다(발주 task 가 없으니 승인 전달이 낸다)


def test_result_report_closes_an_open_incident_by_level():
    inc = machine.Incident(id="INC-1", asset="HYD-03", alert_id="X", card={}, state="AWAITING_APPROVAL")
    assert machine.on_result_report(inc, "fail", "지연", NoFx()) is True and inc.state == "ESCALATED"
    assert machine.on_result_report(inc, "ok", "x", NoFx()) is False                     # 이미 끝난 사건은 그대로
    with pytest.raises(ValueError):
        machine.on_result_report(machine.Incident(id="INC-2", asset="HYD-01", alert_id="Y", card={}, state="AWAITING_APPROVAL"), "info", "", NoFx())
