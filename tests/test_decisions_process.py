"""L9 decision approval: the approver role comes from the ontology (Option -APPROVED_BY-> Role); a higher role level may
approve for a lower one; OT skills are never executed from this path (they go through the HITL incident + gateway)."""
import pytest

from procsvc import decisions

ROLES = {"role:operator": {"name": "운전원", "level": 1}, "role:prod-mgr": {"name": "생산관리자", "level": 2},
         "role:purchasing-mgr": {"name": "구매팀장", "level": 2}, "role:plant-mgr": {"name": "공장장", "level": 3}}


def dec(**over):
    d = {"id": "DEC-1", "scenario": {"id": "sc:delivery-vs-maintenance", "name": "납기 vs 보전"}, "asset": "HYD-01", "roles": ROLES,
         "recommended": "opt:sc1-derate",
         "options": [
             {"id": "opt:sc1-derate", "name": "감속 운전 + 야간 세척", "feasible": True, "approver": {"id": "role:prod-mgr", "name": "생산관리자", "level": 2},
              "skills": [{"id": "skill:cooling-adjust", "system": "sys:scada"}, {"id": "skill:schedule-maintenance", "system": "sys:cmms"}]},
             {"id": "opt:sc1-continue", "name": "계속 운전", "feasible": False, "approver": {"id": "role:operator", "level": 1}, "skills": [],
              "violations": [{"policy": "pol:ts1-limit", "name": "65 ℃"}]},
             {"id": "opt:sc1-stop", "name": "즉시 정지", "feasible": True, "approver": {"id": "role:plant-mgr", "level": 3},
              "skills": [{"id": "skill:schedule-maintenance", "system": "sys:cmms"}]}]}
    return d | over


def test_new_decision_waits_for_approval():
    d = decisions.new(dec())
    assert d["state"] == "PENDING_APPROVAL" and d["id"] == "DEC-1"


def test_approver_role_must_match_or_outrank():
    d = decisions.new(dec())
    with pytest.raises(PermissionError):
        decisions.approve(d, "opt:sc1-stop", by="김생산", role="role:prod-mgr")         # needs 공장장
    plan = decisions.approve(d, "opt:sc1-derate", by="김생산", role="role:prod-mgr")
    assert d["state"] == "APPROVED" and d["chosen"] == "opt:sc1-derate"
    assert [p["skill"] for p in plan["enterprise"]] == ["skill:schedule-maintenance"]
    assert [p["skill"] for p in plan["ot"]] == ["skill:cooling-adjust"]


def test_higher_role_may_approve_for_a_lower_one():
    d = decisions.new(dec())
    decisions.approve(d, "opt:sc1-derate", by="박공장장", role="role:plant-mgr")
    assert d["approvedRole"] == "role:plant-mgr"


def test_infeasible_option_cannot_be_approved():
    d = decisions.new(dec())
    with pytest.raises(ValueError):
        decisions.approve(d, "opt:sc1-continue", by="x", role="role:plant-mgr")


def test_override_of_the_recommendation_is_recorded():
    d = decisions.new(dec())
    decisions.approve(d, "opt:sc1-stop", by="박공장장", role="role:plant-mgr")
    assert d["override"] is True


def test_cannot_approve_twice_and_reject_needs_pending():
    d = decisions.new(dec())
    decisions.approve(d, "opt:sc1-derate", by="x", role="role:prod-mgr")
    with pytest.raises(ValueError):
        decisions.approve(d, "opt:sc1-derate", by="x", role="role:prod-mgr")
    with pytest.raises(ValueError):
        decisions.reject(d, by="x", reason="late")


def test_execution_results_close_the_decision():
    d = decisions.new(dec())
    plan = decisions.approve(d, "opt:sc1-derate", by="x", role="role:prod-mgr")
    decisions.record_execution(d, [{"skill": "skill:schedule-maintenance", "ok": True, "ref": "WO-1"}], plan)
    assert d["state"] == "EXECUTED"
    assert d["executions"][-1]["skill"] == "skill:cooling-adjust" and d["executions"][-1]["status"] == "VIA_HITL"
    decisions.record_execution(d2 := decisions.new(dec(id="DEC-2")), [{"skill": "skill:schedule-maintenance", "ok": False, "error": "down"}],
                               decisions.approve(d2, "opt:sc1-stop", by="x", role="role:plant-mgr"))
    assert d2["state"] == "PARTIAL"
