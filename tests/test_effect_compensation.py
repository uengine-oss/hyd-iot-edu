"""A072 — external effects of a retired generation: exact compensation receipts, human acknowledgement, Incident reopen.

Product principle (process-gpt-completion compensation.py): invert only what is provably reversible; refuse the rest and
hand it to a person. HYD: enterprise inverses from the business systems, review receipts for PLC/irreversible effects,
and only then a new generation with a reopened Incident."""
from copy import deepcopy
import uuid

import pytest

from procsvc import engine, machine, effect_compensation as ec
from test_instance_mode import world, NOW  # noqa: F401 — fixtures
from test_approval_delivery import ready, choose
from test_incident_rework import produce


class FX(machine.Effects):
    def __init__(self): self.audits = []
    def emit_cmd(self, cmd): pass
    def emit_audit(self, evt): self.audits.append(evt)
    def set_timer(self, name, seconds): pass


def test_inverse_table_matches_the_enterprise_mock():
    from entsim import state
    assert ec.INVERSE_OF == state.INVERSE_OF and set(ec.IRREVERSIBLE) == set(state.IRREVERSIBLE)


def test_inventory_classifies_ledger_plc_and_unclear_records():
    evidence = {"incident": {"id": "INC-1", "cmdId": "CMD-1", "actions": [{"code": "FAN_SET", "fan_pct": 100}], "ack": {"result": "DONE"},
                             "workOrder": {"ref": "WO-9"}},
                "decisions": [{"id": "D-1", "executions": [{"status": "DONE", "code": "PR_CREATE", "ref": "PR-1"}, {"status": "FAILED", "code": "WO_CREATE", "ref": None}]}],
                "enterprise_receipts": {"D-1": [
                    {"id": "TX-1", "skill": "skill:procure-part", "system": "sys:erp", "ref": "PR-1"},
                    {"id": "TX-2", "skill": "skill:release-lot", "system": "sys:qms", "ref": "LOT-7"},
                    {"id": "TX-3", "skill": "skill:cancel-purchase-request", "system": "sys:erp", "ref": "PR-1", "compensates": "TX-1"}]}}
    effects = {e["id"]: e for e in ec.inventory(evidence)}
    assert effects["tx:TX-1"]["reversible"] and effects["tx:TX-1"]["compensated_by"] == "TX-3" and effects["tx:TX-1"]["inverse"] == "skill:cancel-purchase-request"
    assert not effects["tx:TX-2"]["reversible"] and "출하" in effects["tx:TX-2"]["irreversible_reason"]
    assert effects["plc:CMD-1"]["kind"] == "plc" and not effects["plc:CMD-1"]["reversible"]
    assert effects["cmms:WO-9"]["kind"] == "cmms" and "local:D-1:WO_CREATE" in effects    # work order not in ledger · failed local record
    assert "local:D-1:PR_CREATE" not in effects                                           # DONE and confirmed by the ledger → the ledger item speaks
    out = ec.resolution(list(effects.values()), [])
    assert out["compensated"] == ["tx:TX-1"] and set(out["pending"]) == {"tx:TX-2", "plc:CMD-1", "cmms:WO-9", "local:D-1:WO_CREATE"}
    review = {"kind": "review", "status": "RECORDED", "request_id": "r1", "effects": [effects["plc:CMD-1"], effects["tx:TX-2"]]}
    out = ec.resolution(list(effects.values()), [review])
    assert set(out["acknowledged"]) == {"plc:CMD-1", "tx:TX-2"} and set(out["pending"]) == {"cmms:WO-9", "local:D-1:WO_CREATE"}


def test_reopen_archives_the_command_and_refuses_in_flight_or_closed():
    inc = machine.Incident.from_card("INC-R", {"alert": {"alertId": "A", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION"}, "recommended": []})
    machine.on_card(inc)
    inc.cmd_id, inc.actions, inc.ack, inc.state = "CMD-9", [{"code": "FAN_SET", "fan_pct": 100}], {"result": "DONE"}, "RE_OBSERVING"
    fx = FX()
    assert machine.on_rework_reopen(inc, "req-1", "이생산", "role:prod-mgr", "wrong cause", {"acknowledged": ["plc:CMD-9"]}, fx) is True
    assert inc.state == "AWAITING_APPROVAL" and inc.cmd_id is None and inc.actions == [] and inc.ack is None
    assert inc.superseded[-1]["cmdId"] == "CMD-9" and inc.superseded[-1]["state_before"] == "RE_OBSERVING"
    assert fx.audits[-1]["event"] == "INCIDENT_REOPENED" and inc.to_dict()["superseded"] == inc.superseded
    assert machine.on_rework_reopen(inc, "req-1", "이생산", "role:prod-mgr", "wrong cause", {}, fx) is False   # idempotent per request
    inc.state = "AWAITING_ACK"
    with pytest.raises(ValueError):
        machine.on_rework_reopen(inc, "req-2", "x", "role:prod-mgr", "r", {}, fx)
    inc.state = "CLOSED"
    with pytest.raises(ValueError):
        machine.on_rework_reopen(inc, "req-3", "x", "role:prod-mgr", "r", {}, fx)


def _delivered_with_command(world, monkeypatch, purchase=True):
    """Approval delivered (PR created in the enterprise), PLC command issued and acknowledged → RE_OBSERVING."""
    rt, inst, inc, decision, selection = ready(world, purchase=purchase)
    ledger = {}
    world["ctx"].approval_receipts = lambda did: deepcopy(ledger.get(did, []))
    calls = []

    def exec_compensation(body):
        calls.append(deepcopy(body))
        if body["params"]["ref"] == "PR-FAIL":
            raise ValueError("purchase request PR-FAIL cannot be cancelled in status 발주 완료")
        tx = {"id": "TX-UNDO-" + body["params"]["ref"], "skill": body["skill"], "system": "sys:erp", "ref": body["params"]["ref"],
              "detail": "cancelled", "decision": body["decision"], "compensates": body["compensates"]}
        ledger.setdefault(body["decision"], []).append(tx)
        return tx
    rt.hooks.exec_compensation = exec_compensation
    choose(rt, decision, selection)
    if purchase:
        ref = next(x["ref"] for x in decision["executions"] if x["code"] == "PR_CREATE")
        ledger[decision["id"]] = [{"id": "TX-PR", "skill": "skill:procure-part", "system": "sys:erp", "ref": ref, "decision": decision["id"]}]
    assert inc.cmd_id and inc.state == "AWAITING_ACK"
    machine.on_status(inc, {"asset": inc.asset, "cmdId": inc.cmd_id, "result": "DONE", "mode": "REMOTE_AUTO"}, NOW, FX(), time_scale=20)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    pid = inst["proc_inst_id"]
    rank = engine._by_activity(rt.repo.list_workitems(proc_inst_id=pid))["task:rank"]
    return rt, pid, inc, decision, selection, rank, calls, ledger


def test_effects_block_then_compensation_and_review_admit_rework_with_reopened_incident(world, monkeypatch):
    rt, pid, inc, decision, selection, rank, calls, ledger = _delivered_with_command(world, monkeypatch)
    assert inc.state == "RE_OBSERVING"
    view = rt.effects_view(pid)
    ids = {e["id"]: e for e in view["effects"]}
    plc, pr = f"plc:{inc.cmd_id}", "tx:TX-PR"
    assert ids[pr]["reversible"] and not ids[plc]["reversible"] and set(view["resolution"]["pending"]) == {pr, plc} and view["reopen_required"]
    p = rt.preview_rework(pid, rank["id"])
    assert not p["execution_available"] and {b["code"] for b in p["blockers"]} >= {ec.BLOCKER}
    with pytest.raises(ValueError, match="보상 요청으로"):          # a reversible transaction cannot be waved through by a review
        rt.review_effects(pid, str(uuid.uuid4()), "이생산", "role:prod-mgr", "x", [pr], now=NOW)
    with pytest.raises(PermissionError):                            # below the approving role
        rt.compensate_effects(pid, str(uuid.uuid4()), "김운전", "role:operator", "x", now=NOW)
    rid = str(uuid.uuid4())
    receipt = rt.compensate_effects(pid, rid, "이생산", "role:prod-mgr", "wrong cause, cancel the part order", now=NOW)
    assert receipt["status"] == "DELIVERED" and receipt["results"][0]["ok"] and calls[0]["skill"] == "skill:cancel-purchase-request"
    assert calls[0]["compensates"] == "TX-PR" and calls[0]["params"]["ref"] == ids[pr]["ref"]
    assert rt.compensate_effects(pid, rid, "이생산", "role:prod-mgr", "wrong cause, cancel the part order", now=NOW) == receipt and len(calls) == 1
    view = rt.effects_view(pid)
    assert view["resolution"]["compensated"] == [pr] and view["resolution"]["pending"] == [plc]
    with pytest.raises(ValueError):                                 # nothing reversible left to compensate
        rt.compensate_effects(pid, str(uuid.uuid4()), "이생산", "role:prod-mgr", "again", now=NOW)
    ack = rt.review_effects(pid, str(uuid.uuid4()), "이생산", "role:prod-mgr", "fan at 100 % confirmed on site; decide again", [plc], now=NOW)
    assert ack["status"] == "RECORDED" and ack["effects"][0]["id"] == plc and ack["history"][0]["incident"]["state"] == "RE_OBSERVING"
    p = rt.preview_rework(pid, rank["id"])
    assert p["execution_available"] and p["reopen_incident"] and p["effects_resolution"]["pending"] == []
    assert selection["id"] in p["retire_approvals"]
    token = p["snapshot_token"]
    result = rt.request_rework(pid, rank["id"], str(uuid.uuid4()), token, "이생산", "role:prod-mgr", "new judgment after cancelled order", now=NOW)
    assert result["generation"] == 1
    assert inc.state == "AWAITING_APPROVAL" and inc.cmd_id is None and inc.superseded[-1]["cmdId"] == ids[plc]["cmdId"]
    assert rt.repo.get_approval(selection["id"], rt.tenant_id)["status"] == "DISCARDED"
    new_decision, _ = produce(world, rt, pid, decision)
    current = engine._by_activity(rt.repo.list_workitems(proc_inst_id=pid))["task:select"]
    assert current["status"] == "IN_PROGRESS"
    choose(rt, new_decision, current)
    assert inc.cmd_id and inc.cmd_id != ids[plc]["cmdId"] and len(inc.superseded) == 1
    assert [r["kind"] for r in rt.instance_view(pid)["effects"]] == ["compensation", "review"]


def test_failed_compensation_keeps_the_block_and_replays_by_request(world, monkeypatch):
    rt, pid, inc, decision, selection, rank, calls, ledger = _delivered_with_command(world, monkeypatch)
    ledger[decision["id"]][0]["ref"] = "PR-FAIL"
    rid = str(uuid.uuid4())
    receipt = rt.compensate_effects(pid, rid, "이생산", "role:prod-mgr", "cancel", now=NOW)
    assert receipt["status"] == "FAILED" and "cannot be cancelled" in receipt["error"] and not receipt["results"][0]["ok"]
    assert not rt.preview_rework(pid, rank["id"])["execution_available"]
    assert rt.repo.get_effect_receipt(rt.tenant_id, pid, rid)["status"] == "FAILED"
    with pytest.raises(ValueError, match="같은 요청 ID"):
        rt.compensate_effects(pid, rid, "이생산", "role:prod-mgr", "different reason", now=NOW)
    assert rt.compensate_effects(pid, rid, "이생산", "role:prod-mgr", "cancel", now=NOW)["status"] == "FAILED" and len(calls) == 1


def test_review_rejects_unknown_resolved_or_in_flight_effects(world, monkeypatch):
    rt, pid, inc, decision, selection, rank, calls, ledger = _delivered_with_command(world, monkeypatch, purchase=False)
    plc = f"plc:{inc.cmd_id}"
    with pytest.raises(ValueError, match="현재 효과 목록"):
        rt.review_effects(pid, str(uuid.uuid4()), "이생산", "role:prod-mgr", "x", ["plc:nope"], now=NOW)
    rid = str(uuid.uuid4())
    ack = rt.review_effects(pid, rid, "이생산", "role:prod-mgr", "checked", [plc], now=NOW)
    assert rt.review_effects(pid, rid, "이생산", "role:prod-mgr", "checked", [plc], now=NOW) == ack
    with pytest.raises(ValueError, match="이미 해결"):
        rt.review_effects(pid, str(uuid.uuid4()), "이생산", "role:prod-mgr", "again", [plc], now=NOW)
    inc.state = "AWAITING_ACK"
    assert not rt.preview_rework(pid, rank["id"])["execution_available"]
    assert "incident_command_in_flight" in {b["code"] for b in rt.preview_rework(pid, rank["id"])["blockers"]}
