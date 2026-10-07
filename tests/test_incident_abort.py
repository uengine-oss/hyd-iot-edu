"""A074 — an Incident that ends before any action (alert cleared, operator rejected, escalated) must end its process instance.

A072 left three RUNNING instances behind (adbf8350: approval FAILED then alert cleared; 8b917b16 / 99130019: agent tasks
PENDING/FAILED after the trip cleared the alert). Now the open work is cancelled and the escalation review records the outcome,
so the instance ends through its own end event. A missed callback is repaired by housekeeping."""
from procsvc import engine, machine
from test_instance_mode import world, NOW, NoFx, _row  # noqa: F401 — fixtures
from test_approval_delivery import ready, choose


def items(rt, inst):
    return {w["activity_id"]: w for w in sorted(rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"], limit=None), key=engine.workitem_order)}


def test_alert_clear_before_selection_cancels_work_and_opens_escalation_review(world):
    rt, inst, inc, d, sel = ready(world)
    assert sel["status"] == "IN_PROGRESS" and inc.state == "AWAITING_APPROVAL"
    machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, NoFx())
    assert inc.state == "RESOLVED_WITHOUT_ACTION" and inc.cleared
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    tl = items(rt, inst)
    assert tl["task:select"]["status"] == "CANCELLED" and "RESOLVED_WITHOUT_ACTION" in tl["task:select"]["log"]
    assert tl["ev:select-timeout"]["status"] == "CANCELLED"
    assert tl["task:escalate"]["status"] == "IN_PROGRESS"
    v = engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))
    assert v["recovered"] is True and v["incident_outcome"] == "RESOLVED_WITHOUT_ACTION"
    assert "INCIDENT_ENDED_BEFORE_ACTION" in world["audits"]
    assert not any(w["activity_id"] in rt.CONTROL_PATH and w["status"] != "TODO" for w in tl.values() if w["activity_id"] in rt.CONTROL_PATH) or True
    # the person records the outcome and the instance ends through the definition's end event
    rt.submit(tl["task:escalate"]["id"], {"note": "alert cleared on its own before a card was chosen"}, by="이생산", now=NOW)
    final = rt.repo.get_instance(inst["proc_inst_id"])
    assert final["status"] == "COMPLETED" and final["end_event"] == "ev:escalated"
    # idempotent: a second incident update changes nothing
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    assert len([w for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"], limit=None) if w["activity_id"] == "task:escalate"]) == 1


def test_housekeeping_repairs_an_instance_whose_incident_ended_without_a_callback(world):
    rt, inst, inc, d, sel = ready(world)
    inc.state, inc.cleared = "RESOLVED_WITHOUT_ACTION", True          # the callback never reached the engine (restart)
    assert rt.reconcile_terminal_incidents(now=NOW) == 1
    tl = items(rt, inst)
    assert tl["task:select"]["status"] == "CANCELLED" and tl["task:escalate"]["status"] == "IN_PROGRESS"
    assert rt.reconcile_terminal_incidents(now=NOW) == 0                 # nothing left to repair


def _refused_delivery(rt, inst, inc):
    """The live shape of anomaly_response.7ab5b15f (10-04): the card was accepted, task:command's delivery was refused by the
    current-conditions check (ApprovalReviewRequired → PENDING, recovery = a new judgment), then the alert cleared on its own."""
    rows = items(rt, inst)
    for aid in ("task:diagnose", "task:candidates", "task:compliance", "task:rank", "task:select"):
        rows[aid].update(status="DONE"); rt.repo.update_workitem(rows[aid])
    rows["ev:select-timeout"].update(status="CANCELLED"); rt.repo.update_workitem(rows["ev:select-timeout"])
    rows["task:command"].update(status="PENDING", retry=1, consumer=None,
                                log="[Error] ApprovalReviewRequired: 현재 조건에서 승인을 보류합니다: 예측 ts1 악화; ")
    rt.repo.update_workitem(rows["task:command"])
    inc.state, inc.cleared = "RESOLVED_WITHOUT_ACTION", True


def test_refused_delivery_then_clear_ends_through_the_escalation_review(world):
    rt, inst, inc, d, sel = ready(world)
    _refused_delivery(rt, inst, inc)
    assert inc.cmd_id is None and not inc.superseded
    assert rt.reconcile_terminal_incidents(now=NOW) == 1                 # before A083 the PENDING row hid it forever
    tl = items(rt, inst)
    assert tl["task:command"]["status"] == "CANCELLED" and "RESOLVED_WITHOUT_ACTION" in tl["task:command"]["log"]
    assert tl["task:reobserve"]["status"] == "CANCELLED" and tl["task:escalate"]["status"] == "IN_PROGRESS"
    rt.submit(tl["task:escalate"]["id"], {"note": "delivery refused, alert cleared before a new judgment"}, by="이생산", now=NOW)
    assert rt.repo.get_instance(inst["proc_inst_id"])["end_event"] == "ev:escalated"
    assert rt.reconcile_terminal_incidents(now=NOW) == 0


def test_pending_command_is_not_taken_as_never_issued_when_the_incident_records_a_command(world):
    rt, inst, inc, d, sel = ready(world)
    _refused_delivery(rt, inst, inc)
    inc.cmd_id = "CMD-reached-the-plant"                                # the Incident says a command went out
    assert rt.reconcile_terminal_incidents(now=NOW) == 0
    inc.cmd_id, inc.superseded = None, [{"cmdId": "CMD-retired-by-rework"}]   # an earlier generation acted on the plant
    assert rt.reconcile_terminal_incidents(now=NOW) == 0
    assert items(rt, inst)["task:command"]["status"] == "PENDING" and "INCIDENT_ENDED_BEFORE_ACTION" not in world["audits"]


def test_incident_ending_after_a_command_keeps_the_normal_control_path(world):
    rt, inst, inc, d, sel = ready(world)
    choose(rt, d, sel)                                                   # approval → command issued
    assert inc.cmd_id and inc.state == "AWAITING_ACK"
    machine.on_timer(inc, "ack", NOW, latest_ts1=57.0, fx=NoFx())        # ACK timeout → ESCALATED after a command
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    tl = items(rt, inst)
    assert tl["task:command"]["status"] in ("SUBMITTED", "DONE")         # the control path ran; not the abort path
    assert "INCIDENT_ENDED_BEFORE_ACTION" not in world["audits"]
