"""Instance runtime with the ProcessGPT semantics: alert → instance + incident → agent rows (fetch_pending_task /
save_task_result) → engine polling → human selection (form) → PLC path as service tasks → closed / escalated → projection."""
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from procsvc import engine, instances, procdb

DEF_PATH = Path(__file__).resolve().parents[1] / "it" / "process" / "definitions" / "anomaly_response.json"
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
ALERT = {"alertId": "HYD-01-COOLER_DEGRADATION-1", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "state": "RAISE"}
OPTION_CONTROL = {"id": "skill:fan-max-derate", "sopId": "SOP-COOL-02", "name": "팬 최대 + 부하 80 %", "kind": "control",
                  "actions": [{"code": "FAN_SET", "kind": "command", "param": "fan_pct", "value": 100}, {"code": "LOAD_SET", "kind": "command", "param": "load_pct", "value": 80},
                              {"code": "WO_CREATE", "kind": "transaction", "value": "쿨러 세척"}]}
OPTION_WO = {"id": "skill:clean-cooler", "sopId": "SOP-COOL-03", "name": "쿨러 세척 작업지시", "kind": "work_order",
             "actions": [{"code": "WO_CREATE", "kind": "transaction", "value": "쿨러 핀 세척"}]}
AGENT_OUTPUTS = {"task:diagnose": {"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"recommended": []}},
                 "task:candidates": {"candidates": ["skill:fan-max-derate", "skill:clean-cooler"]}, "task:compliance": {"compliance": {}},
                 "task:rank": {"decision": {"recommended": "skill:fan-max-derate"}, "decision_id": "DEC-1003-001"}}


class FakeHooks(instances.Hooks):
    def __init__(self, option=OPTION_CONTROL):
        self.calls, self.cypher, self.audits, self.cards = [], [], [], []
        self.option, self.inc_state = option, "AWAITING_APPROVAL"
        super().__init__(
            new_incident=lambda alert: {"id": "INC-1003-01"},
            update_incident_card=lambda inc_id, card: self.cards.append((inc_id, card)),
            approve_commands=self._approve_commands,
            incident_state=lambda inc_id: self.inc_state,
            decision_option=lambda did, oid: self.option if oid == self.option["id"] else None,
            approve_decision=self._approve_decision,
            exec_enterprise=lambda did, item: {"ok": True, "ref": f"REF-{item['code']}", "code": item["code"], "system": item.get("system")},
            record_cypher=lambda q, **p: self.cypher.append(p) or [dict(projection_key=p['id'],projection_revision=p['revision'],projection_hash=p['payload_hash'])],
            audit=lambda asset, actor, event, detail, incident=None: self.audits.append(event))

    def _approve_commands(self, inc_id, commands, by):
        self.calls.append(("approve_commands", inc_id, commands, by))
        self.inc_state = "AWAITING_ACK"
        return {"cmdId": "CMD-1003-0001"}

    def _approve_decision(self, did, option, by, role, reason):
        self.calls.append(("approve_decision", did, option, by, role))
        acts = self.option.get("actions") or []
        return {"enterprise": [{"skill": self.option["id"], "code": a["code"], "system": "sys:cmms"} for a in acts if a["kind"] != "command"],
                "ot": [{"code": a["code"]} for a in acts if a["kind"] == "command"]}

    def _deny(self, *a):
        raise PermissionError("승인 권한 없음")


@pytest.fixture
def rt():
    hooks = FakeHooks()
    return instances.InstanceRuntime(procdb.MemoryRepo(), engine.Definition.load(DEF_PATH), hooks, time_scale=20.0), hooks


def _worker_turn(rt, outputs=AGENT_OUTPUTS):
    """What the cliagents worker does: fetch_pending_task → save_task_result(final); then the engine polls."""
    (wi,) = rt.repo.fetch_pending_task("cliagents", "worker-test")
    rt.repo.save_task_result(wi["id"], outputs[wi["activity_id"]], final=True)
    assert rt.poll_once(now=NOW) == 1
    return wi


def _agent_tasks(rt):
    for _ in range(4):
        _worker_turn(rt)


def _by(rt, inst, activity_id):
    return next((w for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == activity_id), None)


def test_incident_lookup_finds_older_execution_beyond_ui_page(rt):
    runtime,hooks=rt
    hooks.new_incident=lambda alert:{'id':alert['alertId']}
    first=runtime.on_alert_raise(dict(ALERT,alertId='old-incident'),now=NOW)
    for n in range(105):
        runtime.on_alert_raise(dict(ALERT,alertId=f'new-{n}'),now=NOW+timedelta(seconds=n+1))
    found=runtime.instance_of_incident('old-incident')
    assert found and found['proc_inst_id']==first['proc_inst_id']


def test_incident_lookup_does_not_choose_other_tenant(rt):
    runtime,hooks=rt
    own=runtime.on_alert_raise(ALERT,now=NOW)
    foreign=instances.InstanceRuntime(runtime.repo,runtime.defn,FakeHooks(),tenant_id='other')
    foreign.on_alert_raise(ALERT,now=NOW+timedelta(seconds=1))
    assert runtime.instance_of_incident('INC-1003-01')['proc_inst_id']==own['proc_inst_id']


def test_raise_opens_one_instance_with_incident_every_task_planned_and_the_first_in_progress(rt):
    rt, hooks = rt
    inst = rt.on_alert_raise(ALERT, now=NOW)
    assert inst and inst["status"] == "RUNNING" and engine.variables(inst)["incident"] == "INC-1003-01"
    assert engine.variables(inst)["alert_id"] == ALERT["alertId"] and inst["proc_inst_name"] == "설비 이상 조치 HYD-01"
    assert rt.on_alert_raise(ALERT, now=NOW) is None                      # duplicate RAISE ignored
    assert rt.on_alert_raise({"alertId": "x"}, now=NOW) is None           # malformed
    items = rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])
    assert len(items) == 9 and {w["status"] for w in items} == {"IN_PROGRESS", "TODO"}
    assert [w["activity_id"] for w in items if w["status"] == "IN_PROGRESS"] == ["task:diagnose"]
    assert "INSTANCE_STARTED" in hooks.audits and len(hooks.cypher) == 1 and hooks.cypher[0]["status"] == "RUNNING"
    assert rt.repo.get_proc_def("anomaly_response")["ontology_ref"] == "proc:anomaly-response"


def test_full_control_path_closes_with_work_order_and_execution_layer(rt):
    rt, hooks = rt
    inst = rt.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(rt)
    sel = _by(rt, inst, "task:select")
    assert sel["status"] == "IN_PROGRESS" and sel["user_id"] == "role:operator"
    assert hooks.cards == [("INC-1003-01", {"recommended": []})]          # diagnose output became the incident's guide card
    assert _by(rt, inst, "ev:select-timeout")["status"] == "IN_PROGRESS"
    out = rt.select(sel["id"], "DEC-1003-001", "skill:fan-max-derate", by="이생산", role="role:prod-mgr", reason="납기", fan_pct=90, now=NOW)
    assert ("approve_decision", "DEC-1003-001", "skill:fan-max-derate", "이생산", "role:prod-mgr") in hooks.calls
    cmd_call = next(c for c in hooks.calls if c[0] == "approve_commands")
    assert cmd_call[1] == "INC-1003-01" and cmd_call[2] == [{"code": "FAN_SET", "fan_pct": 90}, {"code": "LOAD_SET", "load_pct": 80}] and cmd_call[3] == "이생산"
    assert out["enterprise_results"] == []                               # WO_CREATE is deferred to task:work-order, not run at approval
    assert _by(rt, inst, "task:select")["status"] == "DONE" and _by(rt, inst, "ev:select-timeout")["status"] == "CANCELLED"
    cmd = _by(rt, inst, "task:command")
    assert cmd["status"] == "SUBMITTED" and "waiting ACK" in cmd["log"] and cmd["consumer"]       # a service task waiting for the ACK
    assert rt.poll_once(now=NOW) == 0                                     # held by the service → the poll does not touch it
    # PLC ACK → RE_OBSERVING
    rt.on_incident_update("RE_OBSERVING", "INC-1003-01", cleared=False, now=NOW)
    assert _by(rt, inst, "task:command")["status"] == "DONE" and _by(rt, inst, "task:reobserve")["status"] == "SUBMITTED"
    # re-observation passed → RESOLVED → work order via CMMS → closed
    rt.on_incident_update("RESOLVED", "INC-1003-01", cleared=True, now=NOW)
    saved = rt.repo.get_instance(inst["proc_inst_id"])
    assert saved["status"] == "COMPLETED" and saved["end_event"] == "ev:closed"
    wo = _by(rt, inst, "task:work-order")
    assert wo["status"] == "DONE" and wo["output"]["work_order"]["ref"] == "REF-WO_CREATE"
    assert engine.variables(saved)["recovered"] is True and engine.variables(saved)["chosen_skill_kind"] == "control"
    assert "role:prod-mgr" in saved["participants"] and "role:operator" in saved["participants"]   # the manager who took the operator's task is a participant (live check 10-04)
    assert _by(rt, inst, "task:escalate")["status"] == "CANCELLED"
    last = hooks.cypher[-1]
    assert last["process"] == "proc:anomaly-response" and last["status"] == "COMPLETED" and last["bindings"][1] == {"role": "운전원", "endpoint": "role:operator"}
    assert {i["activity"] for i in last["items"] if i["status"] == "DONE"} == {"task:diagnose", "task:candidates", "task:compliance", "task:rank", "task:select",
                                                                              "task:command", "task:reobserve", "task:work-order"}
    assert {w["status"] for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])} == {"DONE", "CANCELLED"}


def test_work_order_only_card_skips_plc_and_closes(rt):
    rt, hooks = rt
    hooks.option = OPTION_WO
    inst = rt.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(rt)
    sel = _by(rt, inst, "task:select")
    rt.select(sel["id"], "DEC-1003-001", "skill:clean-cooler", by="김정비", role="role:maint-mgr", now=NOW)
    assert not any(c[0] == "approve_commands" for c in hooks.calls)
    saved = rt.repo.get_instance(inst["proc_inst_id"])
    assert saved["status"] == "COMPLETED" and saved["end_event"] == "ev:closed" and engine.variables(saved)["chosen_skill_kind"] == "work_order"
    assert _by(rt, inst, "task:command")["status"] == "CANCELLED"


def test_ack_timeout_escalates_to_production_manager(rt):
    rt, hooks = rt
    inst = rt.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(rt)
    rt.select(_by(rt, inst, "task:select")["id"], "DEC-1003-001", "skill:fan-max-derate", by="이생산", role="role:prod-mgr", now=NOW)
    rt.on_incident_update("ESCALATED", "INC-1003-01", cleared=False, now=NOW)       # no ACK within 30 s
    esc = _by(rt, inst, "task:escalate")
    assert esc["status"] == "IN_PROGRESS" and esc["user_id"] == "role:prod-mgr"
    saved = rt.repo.get_instance(inst["proc_inst_id"])
    assert saved["status"] == "RUNNING" and engine.variables(saved)["recovered"] is False
    rt.submit(esc["id"], {}, by="이생산", now=NOW)
    assert rt.repo.get_instance(inst["proc_inst_id"])["end_event"] == "ev:escalated"


def test_permission_denied_leaves_the_human_task_open(rt):
    rt, hooks = rt
    hooks.approve_decision = hooks._deny
    inst = rt.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(rt)
    sel = _by(rt, inst, "task:select")
    with pytest.raises(PermissionError):
        rt.select(sel["id"], "DEC-1003-001", "skill:fan-max-derate", by="OP-17", role="role:operator", now=NOW)
    assert rt.repo.get_workitem(sel["id"])["status"] == "IN_PROGRESS"
    with pytest.raises(ValueError, match="unknown option"):
        rt.select(sel["id"], "DEC-1003-001", "skill:nope", by="OP-17", role="role:operator", now=NOW)


def test_selection_timeout_fires_only_when_due(rt):
    rt, hooks = rt
    inst = rt.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(rt)
    assert rt.fire_timeouts(now=NOW + timedelta(seconds=10)) == []                     # due = 600 s / 20 = 30 s
    fired = rt.fire_timeouts(now=NOW + timedelta(seconds=31))
    assert len(fired) == 1 and fired[0]["activity_id"] == "ev:select-timeout" and fired[0]["status"] == "DONE"
    assert _by(rt, inst, "task:select")["status"] == "CANCELLED" and _by(rt, inst, "task:escalate")["status"] == "IN_PROGRESS"
    assert "SELECT_TIMEOUT" in hooks.audits


def test_pending_item_stays_pending_and_the_engine_moves_on(rt):
    rt, hooks = rt
    inst = rt.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(rt)
    sel = _by(rt, inst, "task:select")
    out = rt.submit(sel["id"], {"chosen_skill": "x", "chosen_skill_kind": "unknown"}, by="OP-17", now=NOW)
    assert out["pending"] and rt.repo.get_workitem(sel["id"])["status"] == "PENDING" and "TASK_PENDING" in hooks.audits


def test_engine_poll_retries_then_blocks_without_claiming_completion(rt, monkeypatch):
    rt, hooks = rt
    inst = rt.on_alert_raise(ALERT, now=NOW)
    (wi,) = rt.repo.fetch_pending_task("cliagents", "w")
    rt.repo.save_task_result(wi["id"], AGENT_OUTPUTS["task:diagnose"], final=True)
    monkeypatch.setattr(engine, "process_submitted", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    for n in (1, 2, 3):
        assert rt.poll_once(now=NOW) == 1
        row = rt.repo.get_workitem(wi["id"])
        assert row["retry"] == n and "RuntimeError: boom" in row["log"]
        assert row["status"] == ("PENDING" if n == 3 else "SUBMITTED")
        assert row.get("end_date") is None
    assert rt.poll_once(now=NOW) == 0
    assert rt.repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING"
    assert [e["event_type"] for e in rt.repo.list_events(todo_id=wi["id"])] == ["error", "error", "error"]


def test_human_response_requeues_the_agent_task_with_feedback(rt):
    rt, hooks = rt
    inst = rt.on_alert_raise(ALERT, now=NOW)
    (wi,) = rt.repo.fetch_pending_task("cliagents", "w")
    rt.repo.set_draft_status(wi["id"], "HUMAN_ASKED", consumer=None)
    rt.repo.record_events([{"job_id": "human_asked_1", "todo_id": wi["id"], "proc_inst_id": inst["proc_inst_id"], "crew_type": "agent",
                            "event_type": "human_asked", "data": {"text": "PLC 모드를 확인해도 될까요?"}}])
    assert rt.repo.fetch_pending_task("cliagents", "w") == []
    rt.human_response(wi["id"], "human_asked_1", "네, 확인하세요", by="OP-17")
    again = rt.repo.fetch_pending_task("cliagents", "w")
    assert len(again) == 1 and again[0]["feedback"]["human_answer"] == "네, 확인하세요" and again[0]["draft_status"] == "STARTED"
    assert [e["event_type"] for e in rt.repo.list_events(todo_id=wi["id"])] == ["human_asked", "human_response"]


def test_incident_updates_for_unknown_incident_are_ignored(rt):
    rt, hooks = rt
    rt.on_alert_raise(ALERT, now=NOW)
    rt.on_incident_update("RESOLVED", "INC-other", cleared=True, now=NOW)        # no exception, no change
    assert rt.repo.list_instances(status="RUNNING")


def test_instance_view_has_timeline_and_events(rt):
    rt, hooks = rt
    inst = rt.on_alert_raise(ALERT, now=NOW)
    rt.repo.record_events([{"job_id": "r1", "todo_id": rt.repo.list_workitems()[0]["id"], "proc_inst_id": inst["proc_inst_id"], "event_type": "task_started", "data": {}}])
    v = rt.instance_view(inst["proc_inst_id"])
    assert v["instance"]["proc_inst_id"] == inst["proc_inst_id"] and len(v["timeline"]) == 9 and len(v["events"]) == 1
    assert v["timeline"][0]["status"] == "IN_PROGRESS" and v["timeline"][1]["status"] == "TODO" and rt.instance_view("nope") is None


GRAPH_ROW = {"instance": {"id": "PI-1", "status": "RUNNING", "tenant_id": "hyd"}, "process": "proc:anomaly-response", "process_name": "설비 이상 조치",
             "version": 1, "asset": "HYD-01", "incident": "INC-1003-01",
             "bindings": [None, {"role_name": "운전원", "endpoint": "role:operator", "kind": "Role"}],
             "items": [None, {"workitem": {"id": "W-1", "activity_id": "task:diagnose", "status": "DONE", "agent_orch": "cliagents", "agent_mode": "COMPLETE"},
                              "task": "task:diagnose", "task_name": "원인 진단", "task_type": "Task", "performer": "sys:agent", "performer_kind": "single"}]}


def test_execution_view_reads_the_projected_graph_back(rt):
    rt, hooks = rt
    inst = rt.on_alert_raise(ALERT, now=NOW)
    asked = []
    hooks.query_cypher = lambda q, **p: asked.append((q, p)) or [dict(GRAPH_ROW, instance=dict(GRAPH_ROW["instance"], id=p["id"]))]
    v = rt.execution_view(inst["proc_inst_id"])
    assert asked[0][1] == {"id": inst["proc_inst_id"]} and "MATCH (pi:ProcessInstance {id: $id})" in v["cypher"] and v["params"] == {"id": inst["proc_inst_id"]}
    g = v["graph"]
    assert g["instance"]["id"] == inst["proc_inst_id"] and g["process"] == {"id": "proc:anomaly-response", "name": "설비 이상 조치", "version": 1}
    assert g["asset"] == "HYD-01" and g["incident"] == "INC-1003-01" and g["bindings"] == [{"role_name": "운전원", "endpoint": "role:operator", "kind": "Role"}]
    assert g["workitems"] == [{"id": "W-1", "activity_id": "task:diagnose", "status": "DONE", "agent_orch": "cliagents", "agent_mode": "COMPLETE",
                               "executes": "task:diagnose", "executes_name": "원인 진단", "executes_type": "Task", "assigned_to": "sys:agent", "assigned_kind": "single"}]
    hooks.query_cypher = lambda q, **p: []
    assert rt.execution_view(inst["proc_inst_id"])["graph"] is None       # not projected yet (Neo4j down) is a state, not an error
    assert rt.execution_view("nope") is None
    assert instances.format_execution([{"instance": None}]) is None


def test_task_ids_can_change_without_changing_supported_service_or_form_contracts(rt):
    """A designer can rename activities; the declared tool still owns their behavior."""
    from copy import deepcopy

    original, hooks = rt
    raw = deepcopy(original.defn.raw)
    raw["processDefinitionId"] = "maintenance_variant"
    raw["ontologyRef"] = "proc:maintenance-variant"
    renamed = {"task:select": "choose", "task:command": "control", "task:reobserve": "verify", "task:work-order": "maintain"}
    for activity in raw["activities"]:
        activity["id"] = renamed.get(activity["id"], activity["id"])
    for event in raw["events"]:
        if "attachedTo" in event:
            event["attachedTo"] = renamed.get(event["attachedTo"], event["attachedTo"])
    for sequence in raw["sequences"]:
        for key in ("source", "target"):
            sequence[key] = renamed.get(sequence[key], sequence[key])
    runtime = instances.InstanceRuntime(procdb.MemoryRepo(), engine.Definition.from_dict(raw), hooks)
    inst = runtime.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(runtime)
    runtime.select(_by(runtime, inst, "choose")["id"], "DEC-1003-001", OPTION_CONTROL["id"], by="manager", role="role:prod-mgr", now=NOW)
    assert len([c for c in hooks.calls if c[0] == "approve_commands"]) == 1
    runtime.on_incident_update("RE_OBSERVING", "INC-1003-01", cleared=False, now=NOW)
    assert _by(runtime, inst, "control")["status"] == "DONE"
    runtime.on_incident_update("RESOLVED", "INC-1003-01", cleared=True, now=NOW)
    assert runtime.repo.get_instance(inst["proc_inst_id"])["status"] == "COMPLETED"
    assert _by(runtime, inst, "maintain")["output"]["work_order"]["ref"] == "REF-WO_CREATE"
    assert hooks.cypher[-1]["process"] == raw["ontologyRef"]


def test_failed_work_order_keeps_the_instance_open_and_records_the_actual_result(rt):
    runtime, hooks = rt
    hooks.option = OPTION_WO
    failure = {"ok": False, "error": "database unavailable", "system": "sys:cmms"}
    hooks.exec_enterprise = lambda did, item: failure
    inst = runtime.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(runtime)
    runtime.select(_by(runtime, inst, "task:select")["id"], "DEC-1003-001", OPTION_WO["id"], by="manager", role="role:maint-mgr", now=NOW)
    for _ in range(2):
        runtime.poll_once(now=NOW)
    item = _by(runtime, inst, "task:work-order")
    assert item["status"] == "PENDING" and item["retry"] == 3 and item["consumer"] is None
    assert item.get("end_date") is None and not item.get("output")
    assert runtime.repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING"
    errors = runtime.repo.list_events(todo_id=item["id"])
    assert len(errors) == 3 and errors[-1]["data"]["service_result"] == failure
    assert runtime.poll_once(now=NOW) == 0


def test_temporary_work_order_failure_retries_the_same_action_and_then_finishes(rt):
    runtime, hooks = rt
    hooks.option = OPTION_WO
    calls = []

    def execute(did, item):
        calls.append((did, item))
        return {"ok": False, "error": "temporary"} if len(calls) == 1 else {"ok": True, "ref": "WO-recovered"}

    hooks.exec_enterprise = execute
    inst = runtime.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(runtime)
    runtime.select(_by(runtime, inst, "task:select")["id"], "DEC-1003-001", OPTION_WO["id"], by="manager", role="role:maint-mgr", now=NOW)
    assert runtime.repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING"
    runtime.poll_once(now=NOW)
    assert len(calls) == 2 and calls[0] == calls[1]
    assert runtime.repo.get_instance(inst["proc_inst_id"])["status"] == "COMPLETED"
    assert _by(runtime, inst, "task:work-order")["output"]["work_order"]["ref"] == "WO-recovered"


def test_unknown_service_tool_is_reported_and_releases_the_claim(rt):
    runtime, hooks = rt
    hooks.option = OPTION_WO
    runtime.defn.activities["task:work-order"]["tool"] = "enterprise:NOT_IMPLEMENTED"
    runtime.defn.raw['version'] = 'unsupported-tool-test'
    runtime = instances.InstanceRuntime(runtime.repo, engine.Definition.from_dict(runtime.defn.raw), hooks)
    inst = runtime.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(runtime)
    runtime.select(_by(runtime, inst, "task:select")["id"], "DEC-1003-001", OPTION_WO["id"], by="manager", role="role:maint-mgr", now=NOW)
    item = _by(runtime, inst, "task:work-order")
    assert item["status"] == "SUBMITTED" and item["consumer"] is None
    assert "enterprise:NOT_IMPLEMENTED" in item["log"]
    assert runtime.repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING"


def test_rejected_command_is_not_completed_as_if_acknowledged(rt):
    runtime, hooks = rt
    inst = runtime.on_alert_raise(ALERT, now=NOW)
    _agent_tasks(runtime)
    def reject(*args):
        raise ValueError("command outside allowed range")
    hooks.approve_commands = reject
    runtime.select(_by(runtime, inst, "task:select")["id"], "DEC-1003-001", "skill:fan-max-derate", by="mgr", role="role:prod-mgr", now=NOW)
    runtime.poll_once(now=NOW)
    runtime.poll_once(now=NOW)
    command = _by(runtime, inst, "task:command")
    assert command["status"] == "PENDING" and command["retry"] == 3 and command["consumer"] is None
    assert "outside allowed range" in command["log"]
    assert _by(runtime, inst, "task:reobserve")["status"] == "TODO"
    assert runtime.repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING"


def test_completed_event_replay_and_concurrent_delivery_open_only_one_instance(rt):
    from concurrent.futures import ThreadPoolExecutor
    runtime, hooks = rt
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: runtime.on_alert_raise(ALERT, now=NOW), range(16)))
    assert len([r for r in results if r]) == 1
    inst = next(r for r in results if r)
    assert len(runtime.repo.instances) == 1
    inst["status"] = "COMPLETED"
    runtime.repo.update_instance(inst)
    assert runtime.on_alert_raise(ALERT, now=NOW) is None
    other_tenant = instances.InstanceRuntime(runtime.repo, runtime.defn, hooks, tenant_id="other")
    assert other_tenant.on_alert_raise(ALERT, now=NOW) is not None


def test_instance_start_rolls_back_partial_database_state(rt, monkeypatch):
    runtime, hooks = rt
    insert_items = runtime.repo.insert_workitems
    def fail(items):
        insert_items(items)
        raise RuntimeError("injected workitem storage failure")
    monkeypatch.setattr(runtime.repo, "insert_workitems", fail)
    with pytest.raises(RuntimeError, match="injected"):
        runtime.on_alert_raise(ALERT, now=NOW)
    assert not runtime.repo.instances and not runtime.repo.workitems
    monkeypatch.setattr(runtime.repo, "insert_workitems", insert_items)
    assert runtime.on_alert_raise(ALERT, now=NOW) is not None
