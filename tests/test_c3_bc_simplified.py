"""C3 B · C 단순화 (2026-10-09 확정 지시 — '설비까지 안 가기로 함, 처리되면 끝').

  B 정기 정비: [정기 점검] 버튼 → 정비 계획 제안 → 설비보전팀장 승인(1회) → 정비 오더 등록 · 생산팀 공지 메일 → 결과 보고 → 끝
  C 예비품 구매: [재고 보충] 버튼 → 발주안 제안 → 구매 담당 승인(1회) → ERP 발주 · 공급사 메일 → 입고 · 재고 반영(바로) → 결과 보고 → 끝

예정된 정비 시간 대기 · 정비 모사 · 시운전 · 납기 대기는 없다. 수업 시작 상태가 곧 기본값(HYD-02 '정기 점검 도래' · HYD-03 '재고 보충 필요')이고,
처리 건이 끝나면 표시가 꺼지며, [초기화]가 다시 켠다. 흐름은 scripts/c3_flows.py 의 실제 정의를 실제 런타임(MemoryRepo · Incident)으로 돌린다."""
from copy import deepcopy

import pytest

from entsim import state as entstate
from procsvc import bpmn_import as B, effect_parts, engine, scenario_buttons as SB
from test_instance_mode import world, NOW, _row  # noqa: F401  (world 는 fixture)
import test_c2_execution as c2
import test_c3_assembly as c3


def deploy(world, did):
    _, src, mapping = c3._flows().FLOWS[did]
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    r = B.check(B.parse_bpmn(src), deepcopy(mapping), {"catalog": B.catalog(base, c3.AGENTS), "definition_id": did, "version": "1",
                                                       "file_name": f"{did}.bpmn", "xml_sha256": "x"})
    assert r["ok"], r["problems"]
    rt.register_definition(r["definition"])
    rt.deploy_definition(did, "1", "tester", "C3 B · C 단순화 시험")
    return r["definition"]


class Stock(c2.Outside):
    """입고 뒤 재고 읽기(spare_stock)까지 답하는 업무 시스템 대역."""
    def read(self, name, params):
        if name == "spare_stock":
            return {"facts": {"part_no": params["part"], "on_hand": 9, "reserved": 2, "on_order": 0, "available": 7, "reorder_point": 2,
                              "below_reorder_point": False}}
        return super().read(name, params)


@pytest.mark.parametrize("did,tasks", [("c3_pm", 4), ("c3_spare", 5)])
def test_b_and_c_are_small_three_lane_flows_with_one_approval_and_no_plant_parts(world, did, tasks):
    d = deploy(world, did)
    parsed = B.parse_bpmn(c3._flows().FLOWS[did][1])
    assert len(parsed["tasks"]) == tasks and [l["name"] for l in parsed["lanes"]] == ["담당자", "에이전트", "시스템"]
    tools = [a.get("tool") for a in d["activities"]]
    assert sum(1 for t in tools if str(t).startswith("formHandler:select")) == 1
    assert not {effect_parts.RESTORE_TOOL, effect_parts.TEST_RUN_TOOL, effect_parts.WAIT_TOOL, "incident:command"} & set(tools)
    assert parsed["boundaries"] == [] and parsed["gateways"] == []              # 납기 · 승인 지연 타이머 · 정상/미달 분기 없음


def test_b_button_case_registers_the_work_order_mails_and_ends_without_going_to_the_plant(world):
    deploy(world, "c3_pm")
    out = c2.Outside(world)
    st = entstate.EnterpriseState()
    row = st.pm_status("HYD-02")["facts"]
    assert row["pm_alert"] is True                                                 # 수업 시작 상태 = 정기 점검 도래
    alert = SB.build_alert("B", row, now=NOW, person=SB.who({"by": "강사"}))
    assert alert["alertId"].startswith("CMMS-PM_DUE-HYD-02-") and alert["evidence"]["trigger"].endswith("[정기 점검] 버튼")
    rt = world["rt"]
    inst = rt.on_alert_raise(alert, now=NOW)
    assert inst["proc_def_id"] == "c3_pm"
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = c2.b_decision(inc.id)
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "김보전", "role:prod-mgr", now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert done["status"] == "COMPLETED" and done["end_event"] == "E_end" and inc.state == "CLOSED"
    assert [c["code"] for c in out.calls] == ["WO_CREATE"] and out.calls[0]["window"] == row["night_window_id"]
    assert out.restores == [] and out.mails[0][2]["to"] == "production@hyd.local" and "WO-1" in out.mails[0][2]["subject"]
    rep = v["result_report"]
    assert (rep["outcome"], rep["level"]) == ("정상", "ok") and "WO-1" in rep["summary"]
    vals = {r["name"]: r for r in rep["values"]}
    assert vals["정비 오더"]["value"] == "WO-1" and vals["정비 시점"]["value"].startswith("야간 정비 시간") and vals["공지 메일"]["ok"] is True


def test_c_button_case_orders_mails_and_receives_at_once_then_stock_is_above_the_reorder_line(world):
    deploy(world, "c3_spare")
    out = Stock(world)
    st = entstate.EnterpriseState()
    row = st.spare_stock("P-PMP-SEAL")["facts"]
    assert (row["available"], row["below_reorder_point"], row["need_qty"]) == (1, True, 6)
    rt = world["rt"]
    inst = rt.on_alert_raise(SB.build_alert("C", row, now=NOW), now=NOW)
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = c2.c_decision(inc.id)
    world["book"][d["id"]] = d
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    res = rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "정구매", "role:prod-mgr", now=NOW)
    assert res["purchase"]["approved_amount"] == 330                               # 300만 원 초과도 승인 1회 (경고는 카드 표시만)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    v = engine.variables(done)
    assert done["status"] == "COMPLETED" and done["end_event"] == "E_end" and inc.state == "CLOSED"
    assert [c["code"] for c in out.calls] == ["PR_CREATE", "GR_CONFIRM"] and out.mails[0][2]["subject"] == "[발주] P-PMP-SEAL 6개"
    assert _row(rt, inst, "T_gr")["draft"]["wait"]["immediate"] is True            # 리드타임 대기 없음
    assert v["goods_receipt"]["stock_after"]["available"] == 7
    vals = {r["name"]: r for r in v["result_report"]["values"]}
    assert vals["가용 재고"]["value"] == 7 and vals["가용 재고"]["ok"] is True and vals["가용 재고"]["limit"].startswith("≥ 2")
    assert vals["공급사 메일"]["ok"] is True
    events = [e["job_id"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])]
    assert "RECEIPT_IMMEDIATE" in events and "GOODS_RECEIVED" in events and "RECEIPT_WAIT" not in events


def test_immediate_receipt_setting_is_checked():
    act = effect_parts.activity_for("svc:goods-receipt", {"id": "T_gr"}, {"immediate": "yes"}, [], None)
    with pytest.raises(ValueError, match="immediate"):
        effect_parts.validate(act)
    effect_parts.validate(effect_parts.activity_for("svc:goods-receipt", {"id": "T_gr"}, {"immediate": True}, [], None))


class FakeRt:
    tenant_id = "hyd"

    def __init__(self, instances=()):
        self.repo = self
        self._inst = list(instances)

    def list_instances(self, limit=100, tenant_id=None, **_):
        return self._inst[:limit]


def test_buttons_show_the_alerts_refuse_when_handled_running_or_undeployed_and_reset_brings_them_back():
    st = entstate.EnterpriseState()
    read = lambda name, params: {"pm_status": lambda: st.pm_status(params.get("asset")),
                                 "spare_stock": lambda: st.spare_stock(params.get("part"))}[name]()
    s = SB.status(read, FakeRt())["scenarios"]
    assert (s["B"]["asset"], s["B"]["alert"], s["B"]["label"]) == ("HYD-02", True, "정기 점검 도래")
    assert (s["C"]["asset"], s["C"]["alert"], s["C"]["label"], s["C"]["facts"]["available"]) == ("HYD-03", True, "재고 보충 필요", 1)
    route = lambda pattern: "c3_pm" if pattern == "PM_DUE" else None
    with pytest.raises(SB.Refused, match="배포"):
        SB.prepare("C", read, FakeRt(), route)                                     # C 흐름이 배포되지 않음
    running = {"proc_inst_id": "c3_pm.1", "status": "RUNNING", "start_event_id": "CMMS-PM_DUE-HYD-02-20261009010101"}
    with pytest.raises(SB.Refused, match="진행 중"):
        SB.prepare("B", read, FakeRt([running]), route)
    s = SB.status(read, FakeRt([running]))["scenarios"]
    assert s["B"]["running"]["instance"] == "c3_pm.1" and s["C"]["running"] is None
    prep = SB.prepare("B", read, FakeRt(), route)
    assert prep["alert"]["pattern"] == "PM_DUE" and prep["alert"]["evidence"]["hours_since_pm"] == 1950
    st.execute({"decision": "D-B", "skill": "skill:schedule-maintenance", "asset": "HYD-02",
                "params": {"task": "정기 점검", "window_id": st.pm_status("HYD-02")["facts"]["night_window_id"]}})
    assert SB.status(read)["scenarios"]["B"]["alert"] is False                     # 처리됨 → 표시 꺼짐
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
    assert len(rows) == 1 and rows[0]["data"]["by"] == "박정비" and rows[0]["data"]["at"] == ev["requested_at"] and rows[0]["data"]["button"] == "정기 점검"
    assert engine.variables(rt.repo.get_instance(out["instance"]))["alert"]["evidence"]["requested_by"] == "박정비"
    assert SB.who({})["by"] == "나 미선택"                                         # 고르지 않았으면 지어내지 않는다


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


class Refusing(Stock):
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
    (성공한 척하지 않는다). 표시를 끄는 업무 변화(오더 · 입고)가 없으니 '정기 점검 도래' · '재고 보충 필요'는 그대로다."""
    from datetime import timedelta
    from procsvc import instances as I
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
    assert out.calls[-1]["code"] == code and not [c for c in out.calls if c["code"] == "GR_CONFIRM"]


def test_injection_origin_carries_the_press_and_finds_its_case(world):
    """A: 누름 id 가 설비 주입에 실리고, 그 id 로 연결된 처리 건을 시간 창 없이 찾는다."""
    rt = world["rt"]
    person = SB.who({"by": "김운전", "user_id": "user:kim-op", "roles": ["role:operator"]})
    origin = SB.injection_origin("쿨러 열화 주입", person)
    assert origin["id"].startswith("PRESS-") and origin["by"] == "김운전" and origin["button"] == "쿨러 열화 주입" and origin["at"]
    inst = rt.on_alert_raise(dict(c2.ALERT, alertId="HYD-01-A-9"), now=NOW)
    assert SB.case_of_injection(rt, "HYD-01", origin["id"]) is None
    rt.repo.record_events([SB.press_event(inst["proc_inst_id"], origin["button"], "HYD-01", origin, origin["at"], {"injection_id": origin["id"]})])
    assert SB.case_of_injection(rt, "HYD-01", origin["id"]) == inst["proc_inst_id"]
    assert SB.case_of_injection(rt, "HYD-01", "PRESS-other") is None
    assert SB.A_BUTTONS["degrade"]["fault"] == {"type": "cooler_degradation", "severity": SB.A_SEVERITY}


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
