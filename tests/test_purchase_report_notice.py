"""PR-07 manager reporting is a notice, with the original single approval."""
from datetime import timedelta

import pytest

from entsim import state as entstate
from procsvc import effect_parts, engine, scenario_buttons as SB
from test_instance_mode import world, NOW, _row  # noqa: F401
from test_c3_bc_simplified import deploy, Stock
import test_c2_execution as c2


@pytest.mark.parametrize("delivery_failure", [False, True])
def test_manager_report_is_atomic_and_retry_does_not_repeat_purchase(world, monkeypatch, delivery_failure):
    deploy(world, "c3_spare")
    out = Stock(world)
    rt = world["rt"]
    rt.repo.upsert_user({"id": "user:manager", "username": "구매팀장", "is_agent": False, "tenant_id": "hyd"})
    rt.repo.set_role_member("hyd", "role:purchasing-mgr", "user:manager", True)
    inst = rt.on_alert_raise(SB.build_alert("C", entstate.EnterpriseState().spare_stock("P-PMP-SEAL")["facts"], now=NOW), now=NOW)
    pid = inst["proc_inst_id"]
    decision = c2.c_decision(engine.variables(inst)["incident"])
    world["book"][decision["id"]] = decision
    rt.submit(_row(rt, inst, "T_agent")["id"], {"decision": {"recommended": decision["recommended"]}, "decision_id": decision["id"]}, now=NOW)
    insert = rt.repo.insert_notification

    def broken(note):
        result = insert(note)
        if note["user_id"] == "user:manager" and note["type"] == "process_notice":
            raise RuntimeError("notification storage failure after insert")
        return result

    if delivery_failure:
        monkeypatch.setattr(rt.repo, "insert_notification", broken)
    rt.select(_row(rt, inst, "T_approve")["id"], decision["id"], decision["options"][0]["id"], "정구매", "role:prod-mgr", now=NOW)
    if delivery_failure:
        assert rt.repo.get_instance(pid)["status"] != "COMPLETED"
        assert _row(rt, inst, "R_ok")["status"] != "DONE"
        assert not [n for n in rt.repo.notifications if n["user_id"] == "user:manager"]
        monkeypatch.setattr(rt.repo, "insert_notification", insert)
        rt.poll_once(now=NOW + timedelta(seconds=60))
    assert rt.repo.get_instance(pid)["status"] == "COMPLETED"
    notes = [n for n in rt.repo.notifications if n["user_id"] == "user:manager" and n["type"] == "process_notice"]
    assert len(notes) == 1 and notes[0]["url"] == f"/instances/{pid}"
    assert "입고 완료" in notes[0]["title"]
    assert [call["code"] for call in out.calls] == ["PR_CREATE", "GR_CONFIRM"]
    assert "user:manager" not in rt.repo.get_instance(pid)["participants"]


@pytest.mark.parametrize("amount,expected", [(299, False), (300, False), (301, True)])
def test_report_threshold_uses_approved_amount(amount, expected):
    import test_c3_assembly as c3
    config = c3._flows().C_MAPPING["tasks"]["R_ok"]["config"]
    assert config["notify"][0]["role"] == "role:purchasing-mgr"
    assert engine.eval_condition(config["notify"][0]["when"], {"approved_amount": amount}) is expected


@pytest.mark.parametrize("notify", [None, {}, [{}], [{"role": "user:any", "when": "True"}],
                                    [{"role": "role:purchasing-mgr", "when": "f()"}],
                                    [{"role": "role:purchasing-mgr", "when": "("}]])
def test_invalid_report_recipients_are_rejected_before_deployment(notify):
    activity = effect_parts.activity_for("svc:report", {"id": "R"},
                                         {"outcome": "입고 완료", "notify": notify}, [], None)
    with pytest.raises(ValueError, match="notify"):
        effect_parts.validate(activity)
