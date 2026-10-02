"""L9 action-card decision (ontology v2): the approver role comes from the ontology (Skill -APPROVED_BY-> Role); a higher
role level may approve for a lower one; PLC commands of the chosen SOP skill are never sent from this path (they go through
the HITL incident + gateway), system transactions (CMMS work order, ERP purchase request) are executed by L9."""
import pytest

from procsvc import decisions

ROLES = {"role:operator": {"name": "운전원", "level": 1}, "role:prod-mgr": {"name": "생산관리자", "level": 2},
         "role:maint-mgr": {"name": "설비보전팀장", "level": 2}, "role:plant-mgr": {"name": "공장장", "level": 3}}


PARAMS = {"FAN_SET": "fan_pct", "LOAD_SET": "load_pct", "PRESSURE_SET": "pressure_delta", "WO_CREATE": "sop"}


def act(code, kind, value, target):
    return {"id": "action:" + code.lower(), "code": code, "name": code, "kind": kind, "param": PARAMS.get(code), "value": value, "target": target}


def dec(**over):
    d = {"id": "DEC-1", "schema": "v2", "scenario": {"id": "dec:rank-actions", "name": "쿨러 냉각 성능 상실 조치 판단"}, "asset": "HYD-01",
         "roles": ROLES, "recommended": "skill:fan-max-derate",
         "options": [
             {"id": "skill:fan-max-derate", "sopId": "SOP-COOL-02", "name": "팬 최대 + 부하 80 %", "feasible": True,
              "approver": {"id": "role:prod-mgr", "name": "생산관리자", "level": 2},
              "actions": [act("FAN_SET", "command", 100, "actr:fan-drive"), act("LOAD_SET", "command", 80, "actr:pump-drive")]},
             {"id": "skill:derate-night-clean", "sopId": "SOP-COOL-03", "name": "부하 70 % + 야간 세척", "feasible": True,
              "approver": {"id": "role:prod-mgr", "name": "생산관리자", "level": 2},
              "actions": [act("LOAD_SET", "command", 70, "actr:pump-drive"), act("WO_CREATE", "transaction", "SOP-COOL-04", "sys:cmms")]},
             {"id": "skill:raise-pressure", "sopId": "SOP-PMP-03", "name": "압력 설정 상향", "feasible": False,
              "approver": {"id": "role:operator", "level": 1}, "actions": [act("PRESSURE_SET", "command", 10, "actr:pump-drive")],
              "violations": [{"rule": "rule:no-pressure-raise", "annotation": "누설 의심 시 압력 설정 상향 금지"}]},
             {"id": "skill:planned-stop", "sopId": "SOP-FAN-03", "name": "계획 정지", "feasible": True,
              "approver": {"id": "role:plant-mgr", "level": 3}, "actions": [act("WO_CREATE", "transaction", "SOP-FAN-04", "sys:cmms")]}]}
    return d | over


def test_new_decision_waits_for_approval():
    d = decisions.new(dec())
    assert d["state"] == "PENDING_APPROVAL" and d["id"] == "DEC-1"


def test_approver_role_must_match_or_outrank():
    d = decisions.new(dec())
    with pytest.raises(PermissionError):
        decisions.approve(d, "skill:planned-stop", by="김생산", role="role:prod-mgr")          # needs 공장장
    plan = decisions.approve(d, "skill:derate-night-clean", by="김생산", role="role:prod-mgr")
    assert d["state"] == "APPROVED" and d["chosen"] == "skill:derate-night-clean"
    assert [(p["code"], p["value"], p["system"]) for p in plan["enterprise"]] == [("WO_CREATE", "SOP-COOL-04", "sys:cmms")]
    assert [(p["code"], p["value"]) for p in plan["ot"]] == [("LOAD_SET", 70)]
    assert all(p["sop"] == "SOP-COOL-03" for p in plan["enterprise"] + plan["ot"])


def test_higher_role_may_approve_for_a_lower_one():
    d = decisions.new(dec())
    decisions.approve(d, "skill:fan-max-derate", by="박공장장", role="role:plant-mgr")
    assert d["approvedRole"] == "role:plant-mgr"


def test_excluded_card_cannot_be_approved():
    d = decisions.new(dec())
    with pytest.raises(ValueError) as e:
        decisions.approve(d, "skill:raise-pressure", by="x", role="role:plant-mgr")
    assert "압력 설정 상향 금지" in str(e.value)


def test_override_of_the_recommendation_is_recorded():
    d = decisions.new(dec())
    decisions.approve(d, "skill:planned-stop", by="박공장장", role="role:plant-mgr")
    assert d["override"] is True


def test_cannot_approve_twice_and_reject_needs_pending():
    d = decisions.new(dec())
    decisions.approve(d, "skill:fan-max-derate", by="x", role="role:prod-mgr")
    with pytest.raises(ValueError):
        decisions.approve(d, "skill:fan-max-derate", by="x", role="role:prod-mgr")
    with pytest.raises(ValueError):
        decisions.reject(d, by="x", reason="late")


def test_execution_results_close_the_decision():
    d = decisions.new(dec())
    plan = decisions.approve(d, "skill:derate-night-clean", by="x", role="role:prod-mgr")
    decisions.record_execution(d, [{"skill": "skill:derate-night-clean", "code": "WO_CREATE", "system": "sys:cmms", "ok": True, "ref": "WO-1"}], plan)
    assert d["state"] == "EXECUTED"
    assert d["executions"][0]["code"] == "WO_CREATE" and d["executions"][0]["ref"] == "WO-1"
    assert d["executions"][-1]["code"] == "LOAD_SET" and d["executions"][-1]["status"] == "VIA_HITL"
    d2 = decisions.new(dec(id="DEC-2"))
    decisions.record_execution(d2, [{"skill": "skill:planned-stop", "code": "WO_CREATE", "ok": False, "error": "down"}],
                               decisions.approve(d2, "skill:planned-stop", by="x", role="role:plant-mgr"))
    assert d2["state"] == "PARTIAL"
