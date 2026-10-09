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
    alert = SB.build_alert("B", row, by="강사", now=NOW)
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
    st.execute({"decision": "D-B", "skill": "skill:schedule-maintenance", "asset": "HYD-02", "params": {"task": "정기 점검"}})
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
