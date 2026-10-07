from datetime import timedelta

from procsvc import machine, definition as d, definition
from hydcommon.timeutil import now, parse_iso

CARD = {
    "incident": None,
    "alert": {"alertId": "ALT-hyd01-0001", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "severity": "HIGH", "state": "RAISE"},
    "freshness": {"ok": True, "age_s": 1.0},
    "causes": [{"id": "cause:cooler-fin-fouling", "name": "핀 오염", "score": 0.5, "evidence": []}],
    "topCause": "cause:cooler-fin-fouling",
    "recommended": [
        {"code": "FAN_BOOST", "actionId": "act:fan-boost", "name": "팬 상향", "kind": "command", "param": "fan_pct", "value": 100, "paramRange": [80, 100]},
        {"code": "REDUCE_LOAD", "actionId": "act:reduce-load", "name": "부하 저감", "kind": "command", "param": "load_pct", "value": 80, "paramRange": [60, 90]},
        {"code": "COOLER_CLEAN_WO", "actionId": "act:cooler-clean-wo", "name": "세척 WO", "kind": "work_order", "param": None, "value": None, "paramRange": None},
    ],
    "citations": ["cause:cooler-fin-fouling", "act:fan-boost"], "summary": "s",
}


class FX(machine.Effects):
    def __init__(self):
        self.cmds, self.audits, self.timers = [], [], []

    def emit_cmd(self, cmd): self.cmds.append(cmd)
    def emit_audit(self, evt): self.audits.append(evt)
    def set_timer(self, name, seconds): self.timers.append((name, seconds))


def new_incident():
    inc = machine.Incident.from_card("INC-0923-01", CARD)
    machine.on_card(inc)
    return inc


def approve(inc, fx, t=None):
    machine.on_approve(inc, "OP-17", [{"code": "FAN_BOOST", "fan_pct": 100}, {"code": "REDUCE_LOAD", "load_pct": 80}], t or now(), fx, time_scale=20)


def test_card_moves_to_awaiting_approval():
    inc = new_incident()
    assert inc.state == "AWAITING_APPROVAL" and inc.asset == "HYD-01" and inc.alert_id == "ALT-hyd01-0001"
    assert inc.history[-1]["state"] == "AWAITING_APPROVAL"


def test_happy_path_to_closed():
    inc, fx = new_incident(), FX()
    t = now()
    approve(inc, fx, t)
    assert inc.state == "AWAITING_ACK"
    cmd = fx.cmds[0]
    assert cmd["asset"] == "HYD-01" and cmd["incident"] == "INC-0923-01" and cmd["source"] == "HITL" and cmd["approvedBy"] == "OP-17"
    assert cmd["actions"] == [{"code": "FAN_BOOST", "fan_pct": 100}, {"code": "REDUCE_LOAD", "load_pct": 80}]
    assert abs((parse_iso(cmd["expiresAt"]) - t).total_seconds() - 120) < 1
    assert ("ack", 30) in fx.timers
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": cmd["cmdId"], "result": "DONE", "mode": "REMOTE_AUTO"}, t, fx)
    assert inc.state == "RE_OBSERVING" and inc.ack["result"] == "DONE"
    assert ("reobs", 900 / 20) in fx.timers
    machine.on_alert(inc, {"alertId": "ALT-hyd01-0001", "state": "CLEAR"}, fx)
    assert inc.cleared and inc.state == "RE_OBSERVING"
    machine.on_timer(inc, "reobs", t + timedelta(seconds=45), latest_ts1=49.5, fx=fx)
    assert inc.state == 'RESOLVED' and inc.work_order is None
    machine.on_work_order(inc, {'ok':True, 'ref':'WO-CMMS-actual', 'code':'COOLER_CLEAN_WO'}, fx)
    assert inc.state == "CLOSED"
    assert inc.work_order and inc.work_order["code"] == "COOLER_CLEAN_WO"
    states = [h["state"] for h in inc.history]
    assert states[-3:] == ["RESOLVED", "WORK_ORDER_CREATED", "CLOSED"]
    assert any(a["event"] == "INCIDENT_CLOSED" for a in fx.audits)


def test_ack_timeout_escalates():
    inc, fx = new_incident(), FX()
    approve(inc, fx)
    machine.on_timer(inc, "ack", now() + timedelta(seconds=31), latest_ts1=57.0, fx=fx)
    assert inc.state == "ESCALATED" and inc.reason == "ACK_TIMEOUT"


def test_plc_rejected_escalates():
    inc, fx = new_incident(), FX()
    approve(inc, fx)
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": inc.cmd_id, "result": "REJECTED", "reason": "MODE_MISMATCH"}, now(), fx)
    assert inc.state == "ESCALATED" and "MODE_MISMATCH" in inc.reason


def test_ack_ignores_stale_cmd_id():
    inc, fx = new_incident(), FX()
    approve(inc, fx)
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": "CMD-OLD", "result": "DONE"}, now(), fx)
    assert inc.state == "AWAITING_ACK"
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": None, "result": None}, now(), fx)
    assert inc.state == "AWAITING_ACK"


def test_clear_before_approval_closes_incident():
    inc, fx = new_incident(), FX()
    machine.on_alert(inc, {"alertId": "ALT-hyd01-0001", "state": "CLEAR"}, fx)
    assert inc.state == "RESOLVED_WITHOUT_ACTION" and inc.state in definition.TERMINAL


def test_reobserve_fails_when_hot():
    inc, fx = new_incident(), FX()
    approve(inc, fx)
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": inc.cmd_id, "result": "DONE"}, now(), fx)
    machine.on_timer(inc, "reobs", now() + timedelta(seconds=45), latest_ts1=58.0, fx=fx)
    assert inc.state == "ESCALATED" and inc.reason == "MITIGATION_FAILED"


def test_approve_rejects_out_of_range():
    inc, fx = new_incident(), FX()
    try:
        machine.on_approve(inc, "OP-17", [{"code": "REDUCE_LOAD", "load_pct": 50}], now(), fx, time_scale=20)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "load_pct" in str(e)
    assert inc.state == "AWAITING_APPROVAL" and not fx.cmds


def test_operator_reject():
    inc, fx = new_incident(), FX()
    machine.on_reject(inc, "OP-17", "already handled on site", fx)
    assert inc.state == "REJECTED_BY_OPERATOR" and any(a["event"] == "GUIDE_REJECTED" for a in fx.audits)


def test_definition_lists_bpmn_steps_in_order():
    ids = [s[0] for s in definition.STEPS]
    assert ids[0] == "GUIDE_RECEIVED" and ids[-1] == "CLOSED" and "AWAITING_ACK" in ids
    assert definition.TERMINAL >= {"CLOSED", "ESCALATED", "REJECTED_BY_OPERATOR", "RESOLVED_WITHOUT_ACTION"}


def test_cmd_ids_unique_across_process_restarts():
    """cmd-gateway and the PLC de-duplicate on cmdId; a restarted process must never reuse one (seen in the demo run)."""
    import itertools
    ids = set()
    for restart in range(3):
        machine._cmd_seq = itertools.count(1)          # what a container restart does to the in-memory counter
        inc, fx = new_incident(), FX()
        approve(inc, fx)
        assert inc.cmd_id.startswith("CMD-")
        ids.add(inc.cmd_id)
    assert len(ids) == 3, ids


def test_incident_ids_unique_across_process_restarts():
    import itertools
    ids = set()
    for restart in range(3):
        machine._inc_seq = itertools.count(1)
        ids.add(machine.new_incident_id())
    assert len(ids) == 3, ids


def test_reobserve_extends_once_when_cooling_but_not_yet_cleared():
    """Seen in scenario run 3: TS1 already < 55 C at the verdict but the detector's CLEAR (52 C held 60 s) landed 3 s later."""
    inc, fx = new_incident(), FX()
    approve(inc, fx)
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": inc.cmd_id, "result": "DONE"}, now(), fx)
    machine.on_timer(inc, "reobs", now() + timedelta(seconds=45), latest_ts1=52.2, fx=fx, time_scale=20)
    assert inc.state == "RE_OBSERVING" and inc.reobs_extensions == 1
    assert ("reobs", 900 / 20 / 3) in fx.timers                     # one extension of a third of the window
    assert any(a["event"] == "REOBSERVATION_EXTENDED" for a in fx.audits)
    machine.on_alert(inc, {"alertId": "ALT-hyd01-0001", "state": "CLEAR"}, fx)
    machine.on_timer(inc, "reobs", now() + timedelta(seconds=60), latest_ts1=50.9, fx=fx, time_scale=20)
    assert inc.state == "RESOLVED" and inc.work_order is None


def test_reobserve_escalates_after_extensions_without_clear():
    """A072 run 4 (1x): the plant was inside the limit (51.86 C) and the detector CLEAR landed seconds after the single
    extension ended. Inside the limit the incident now waits up to REOBSERVE_MAX_EXTENSIONS (3) third-windows for CLEAR;
    a value that stays inside without ever clearing still escalates after the last one."""
    inc, fx = new_incident(), FX()
    approve(inc, fx)
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": inc.cmd_id, "result": "DONE"}, now(), fx)
    for n in range(1, d.REOBSERVE_MAX_EXTENSIONS + 1):
        machine.on_timer(inc, "reobs", now(), latest_ts1=53.0, fx=fx, time_scale=20)
        assert inc.state == "RE_OBSERVING" and inc.reobs_extensions == n
    assert fx.timers.count(("reobs", 900 / 20 / 3)) == d.REOBSERVE_MAX_EXTENSIONS
    machine.on_timer(inc, "reobs", now(), latest_ts1=53.0, fx=fx, time_scale=20)   # still no CLEAR → no further extension
    assert inc.state == "ESCALATED" and inc.reason == "MITIGATION_FAILED"


def test_reobserve_does_not_extend_when_still_hot():
    inc, fx = new_incident(), FX()
    approve(inc, fx)
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": inc.cmd_id, "result": "DONE"}, now(), fx)
    machine.on_timer(inc, "reobs", now(), latest_ts1=58.0, fx=fx, time_scale=20)
    assert inc.state == "ESCALATED"


def test_command_without_parameter_needs_no_value():
    """RESET (냉각 후 리셋 SOP) has no parameter: approving it must not ask for one."""
    card = dict(CARD, recommended=CARD["recommended"] + [{"code": "RESET", "actionId": "action:reset", "name": "리셋", "kind": "command",
                                                         "param": None, "value": 1, "paramRange": None}])
    inc = machine.Incident.from_card("INC-0923-09", card)
    machine.on_card(inc)
    fx = FX()
    cmd = machine.on_approve(inc, "OP-17", [{"code": "RESET"}], now(), fx, time_scale=20)
    assert cmd["actions"] == [{"code": "RESET"}] and inc.state == "AWAITING_ACK"


def test_timer_armed_for_a_superseded_command_is_ignored_after_rework_reopen():
    """A072 live run 4: the first command's 45 s re-observation timer fired inside the second command's window and escalated
    the case 6 s in. A timer judges only the command that armed it."""
    inc, fx = new_incident(), FX()
    t = now()
    approve(inc, fx, t)
    first = inc.cmd_id
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": first, "result": "DONE", "mode": "REMOTE_AUTO"}, t, fx)
    assert inc.state == "RE_OBSERVING"
    assert machine.on_rework_reopen(inc, "req-1", "이생산", "role:prod-mgr", "fan only was not enough", {"acknowledged": [f"plc:{first}"]}, fx)
    approve(inc, fx, t + timedelta(seconds=20))
    second = inc.cmd_id
    assert second != first
    machine.on_timer(inc, "ack", t + timedelta(seconds=30), latest_ts1=57.0, fx=fx, cmd_id=first)     # stale ack timer
    assert inc.state == "AWAITING_ACK" and fx.audits[-1]["event"] == "TIMER_IGNORED" and fx.audits[-1]["detail"]["armedFor"] == first
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": second, "result": "DONE", "mode": "REMOTE_AUTO"}, t + timedelta(seconds=23), fx)
    machine.on_timer(inc, "reobs", t + timedelta(seconds=45), latest_ts1=55.21, fx=fx, cmd_id=first)   # stale reobs timer, hot value
    assert inc.state == "RE_OBSERVING" and inc.reason is None
    machine.on_alert(inc, {"alertId": "ALT-hyd01-0001", "state": "CLEAR"}, fx)
    machine.on_timer(inc, "reobs", t + timedelta(seconds=68), latest_ts1=49.0, fx=fx, cmd_id=second)   # the current command's own window
    assert inc.state == "RESOLVED"
    machine.on_timer(inc, "reobs", t + timedelta(seconds=70), latest_ts1=49.0, fx=fx)                  # legacy callers without a binding still work
    assert inc.state == "RESOLVED"
