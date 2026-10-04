"""Process-instance engine with the ProcessGPT completion semantics (pure logic):
definition JSON → instance (RUNNING) → every reachable activity TODO → reached IN_PROGRESS → SUBMITTED → engine DONE/PENDING
→ gateways (XOR priority/default) → boundary timer as an event work item → CANCELLED alternatives → end events."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from procsvc import engine

DEF_PATH = Path(__file__).resolve().parents[1] / "it" / "process" / "definitions" / "anomaly_response.json"
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
AGENT_OUTPUTS = {"task:diagnose": {"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"topCause": "cause:cooler-fin-fouling"}},
                 "task:candidates": {"candidates": ["skill:fan-max", "skill:fan-max-derate", "skill:clean-cooler"]},
                 "task:compliance": {"compliance": {"skill:fan-max": {"warn": ["rule:ts1-warn"]}}},
                 "task:rank": {"decision": {"recommended": "skill:fan-max-derate"}, "decision_id": "DEC-1003-001"}}


@pytest.fixture
def defn():
    return engine.Definition.load(DEF_PATH)


class World:
    """Rows as a repo would hold them, so the engine can be driven like the runtime drives it."""

    def __init__(self, defn, values=None, time_scale=1.0):
        self.defn, self.time_scale = defn, time_scale
        self.inst = engine.new_instance(defn, values or {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "alert": {"alertId": "A1"}}, now=NOW)
        self.rows: list[dict] = []
        self.apply(engine.start(defn, self.inst, now=NOW, time_scale=time_scale))

    def apply(self, adv):
        for r in adv.created:
            if r not in self.rows:
                self.rows.append(r)
        return adv

    def row(self, activity_id, status=None):
        rows = [r for r in self.rows if r["activity_id"] == activity_id and (status is None or r["status"] == status)]
        return rows[-1] if rows else None

    def turn_in(self, activity_id, output):
        row = self.row(activity_id)
        engine.submit(self.defn, self.inst, row, output, now=NOW)
        return self.apply(engine.process_submitted(self.defn, self.inst, row, self.rows, now=NOW, time_scale=self.time_scale))

    def statuses(self):
        return {r["activity_id"]: r["status"] for r in self.rows}

    def agent_tasks(self):
        for aid in ("task:diagnose", "task:candidates", "task:compliance", "task:rank"):
            assert self.row(aid)["status"] == "IN_PROGRESS", aid
            self.turn_in(aid, AGENT_OUTPUTS[aid])


def test_definition_matches_ontology_v2_flow_nodes(defn):
    assert len(defn.activities) == 9 and len(defn.gateways) == 2 and len(defn.events) == 4 and len(defn.sequences) == 15
    assert defn.raw["ontologyRef"] == "proc:anomaly-response"
    agent_tasks = [a for a in defn.activities.values() if a["type"] == "businessRuleTask"]
    assert [a["id"] for a in agent_tasks] == ["task:diagnose", "task:candidates", "task:compliance", "task:rank"]
    assert all(a["orchestration"] == "cliagents" and a["agentMode"] == "COMPLETE" and a["tool"].startswith("formHandler:") for a in agent_tasks)
    assert defn.activities["task:select"]["attachedEvents"] == ["ev:select-timeout"] and defn.attached_activity("ev:select-timeout")["id"] == "task:select"


def test_start_pre_creates_every_activity_todo_and_reaches_the_first(defn):
    w = World(defn)
    assert w.inst["status"] == "RUNNING" and w.inst["proc_inst_id"].startswith("anomaly_response.")
    assert w.inst["role_bindings"][0] == {"name": "AI 에이전트", "endpoint": "sys:agent", "resolutionRule": defn.roles["AI 에이전트"]["resolutionRule"]}
    assert engine.variables(w.inst)["asset"] == "HYD-01" and w.inst["variables_data"][0]["key"] == "asset"
    assert len(w.rows) == 9 and w.statuses() == {"task:diagnose": "IN_PROGRESS", "task:candidates": "TODO", "task:compliance": "TODO", "task:rank": "TODO",
                                                "task:select": "TODO", "task:command": "TODO", "task:reobserve": "TODO", "task:work-order": "TODO", "task:escalate": "TODO"}
    first = w.row("task:diagnose")
    assert first["agent_orch"] == "cliagents" and first["agent_mode"] == "COMPLETE" and first["user_id"] == "sys:agent" and first["draft_status"] is None
    assert first["tool"] == "formHandler:diagnose" and "[Instruction]" in first["query"] and "[InputData]" in first["query"] and '"pattern": "COOLER_DEGRADATION"' in first["query"]
    assert w.row("task:select")["agent_mode"] is None and w.row("task:select")["agent_orch"] is None and w.row("task:command")["agent_orch"] == "hyd-process"
    assert w.inst["current_activity_ids"] == ["task:diagnose"] and w.inst["participants"] == ["sys:agent"]


def test_submitted_is_the_engines_turn_done_then_next_in_progress(defn):
    w = World(defn)
    row = w.row("task:diagnose")
    engine.submit(defn, w.inst, row, AGENT_OUTPUTS["task:diagnose"], now=NOW)
    assert row["status"] == "SUBMITTED" and row["output"]["cause"] == "cause:cooler-fin-fouling"
    assert w.statuses()["task:candidates"] == "TODO"                       # nothing moves until the engine processes it
    adv = w.apply(engine.process_submitted(defn, w.inst, row, w.rows, now=NOW))
    assert row["status"] == "DONE" and row["end_date"] == "2026-10-03T12:00:00.000Z" and not adv.pending
    nxt = w.row("task:candidates")
    assert nxt["status"] == "IN_PROGRESS" and [r["activity_id"] for r in adv.reached] == ["task:candidates"]
    assert '"failure_mode": "fm:cooling-loss"' in nxt["query"] and nxt["reference_ids"] == [row["id"]]
    assert engine.variables(w.inst)["cause"] == "cause:cooler-fin-fouling" and w.inst["current_activity_ids"] == ["task:candidates"]


def test_four_agent_tasks_then_human_task_with_timer_event_row(defn):
    w = World(defn)
    w.agent_tasks()
    sel = w.row("task:select")
    assert sel["status"] == "IN_PROGRESS" and sel["user_id"] == "role:operator" and sel["tool"] == "formHandler:select_card"
    timer = w.row("ev:select-timeout")
    assert timer and timer["status"] == "IN_PROGRESS" and timer["user_id"] == "sys:process" and timer["due_date"] == "2026-10-03T12:10:00.000Z"
    assert engine.variables(w.inst)["decision_id"] == "DEC-1003-001"
    assert set(w.inst["participants"]) == {"sys:agent", "role:operator"}          # the timer is a system row, not a participant


def test_timer_scales_with_time_scale(defn):
    w = World(defn, time_scale=20)
    for aid in ("task:diagnose", "task:candidates", "task:compliance", "task:rank"):
        w.turn_in(aid, {})
    assert w.row("ev:select-timeout")["due_date"] == "2026-10-03T12:00:30.000Z"       # 600 s / 20


def test_control_skill_goes_command_reobserve_work_order_closed_and_cancels_the_rest(defn):
    w = World(defn)
    w.agent_tasks()
    adv = w.turn_in("task:select", {"chosen_skill": "skill:fan-max-derate", "chosen_skill_kind": "control"})
    assert "gw:control" in adv.visited and w.row("ev:select-timeout")["status"] == "CANCELLED"
    sel = w.row("task:select")
    assert sel["status"] == "DONE" and sel["gateway_decisions"]["gw:control"]["selected"] == ["seq:gw-command"]
    assert sel["gateway_decisions"]["gw:control"]["sequences"]["seq:gw-workorder"]["eval"] is False
    cmd = w.row("task:command")
    assert cmd["status"] == "SUBMITTED" and cmd["agent_orch"] == "hyd-process" and cmd["user_id"] == "sys:scada"     # service task: straight to the engine
    w.apply(engine.process_submitted(defn, w.inst, cmd, w.rows, now=NOW))
    assert cmd["status"] == "DONE" and w.row("task:reobserve")["status"] == "SUBMITTED"
    w.turn_in("task:reobserve", {"recovered": True})
    wo = w.row("task:work-order")
    assert wo["status"] == "SUBMITTED" and wo["user_id"] == "sys:cmms" and w.row("task:escalate")["status"] == "TODO"
    adv = w.turn_in("task:work-order", {"work_order": {"id": "WO-1"}})
    assert adv.ended == "ev:closed" and w.inst["status"] == "COMPLETED" and w.inst["end_event"] == "ev:closed"
    assert w.inst["end_date"] == "2026-10-03T12:00:00.000Z" and w.inst["current_activity_ids"] == []
    assert w.row("task:escalate")["status"] == "CANCELLED"                 # the branch not taken, once the instance ended
    assert {r["status"] for r in w.rows} == {"DONE", "CANCELLED"}


def test_work_order_only_skill_skips_plc_command(defn):
    w = World(defn)
    w.agent_tasks()
    w.turn_in("task:select", {"chosen_skill": "skill:clean-cooler", "chosen_skill_kind": "work_order"})
    assert w.row("task:work-order")["status"] == "SUBMITTED" and w.row("task:command")["status"] == "TODO"
    w.turn_in("task:work-order", {"work_order": {"id": "WO-2"}})
    assert w.inst["end_event"] == "ev:closed" and w.row("task:command")["status"] == "CANCELLED" and w.row("task:reobserve")["status"] == "CANCELLED"


def test_not_recovered_escalates_to_production_manager_and_ends_escalated(defn):
    w = World(defn)
    w.agent_tasks()
    w.turn_in("task:select", {"chosen_skill": "skill:fan-max", "chosen_skill_kind": "control"})
    w.turn_in("task:command", {})
    w.turn_in("task:reobserve", {"recovered": False})
    esc = w.row("task:escalate")
    assert esc["status"] == "IN_PROGRESS" and esc["user_id"] == "role:prod-mgr" and w.row("task:work-order")["status"] == "TODO"
    adv = w.turn_in("task:escalate", {})
    assert adv.ended == "ev:escalated" and w.inst["status"] == "COMPLETED" and w.inst["end_event"] == "ev:escalated"
    assert w.row("task:work-order")["status"] == "CANCELLED"


def test_selection_timeout_event_fires_cancels_the_human_task_and_escalates(defn):
    w = World(defn)
    w.agent_tasks()
    timer = w.row("ev:select-timeout")
    adv = w.apply(engine.fire_event(defn, w.inst, timer, w.rows, now=NOW))
    assert timer["status"] == "DONE" and "fired at" in timer["log"]
    assert w.row("task:select")["status"] == "CANCELLED" and "ev:select-timeout completed first" in w.row("task:select")["log"]
    assert 'task:select' not in w.inst['current_activity_ids']
    assert w.row("task:escalate")["status"] == "IN_PROGRESS" and [r["activity_id"] for r in adv.reached] == ["task:escalate"]
    with pytest.raises(ValueError):
        engine.fire_event(defn, w.inst, timer, w.rows, now=NOW)                       # already fired
    with pytest.raises(ValueError, match="not an event"):
        engine.fire_event(defn, w.inst, w.row("task:escalate"), w.rows, now=NOW)


def test_unmet_gateway_conditions_leave_the_item_pending_with_a_reason(defn):
    w = World(defn)
    w.agent_tasks()
    adv = w.turn_in("task:select", {"chosen_skill": "x", "chosen_skill_kind": "unknown"})
    sel = w.row("task:select")
    assert adv.pending and sel["status"] == "PENDING" and "PROCEED_CONDITION_NOT_MET" in sel["log"]
    assert sel["gateway_decisions"]["gw:control"]["selected"] == [] and w.row("task:command")["status"] == "TODO"
    assert w.inst["status"] == "RUNNING" and w.row("ev:select-timeout")["status"] == "IN_PROGRESS"


def test_xor_picks_one_by_priority_then_default_flow():
    d = {"processDefinitionId": "p", "processDefinitionName": "p", "roles": [{"name": "r", "endpoint": "u"}],
         "events": [{"id": "s", "type": "startEvent"}, {"id": "e", "type": "endEvent"}],
         "activities": [{"id": "a", "name": "a", "type": "userTask", "role": "r", "outputData": ["x"]},
                        {"id": "b1", "name": "b1", "type": "userTask", "role": "r"}, {"id": "b2", "name": "b2", "type": "userTask", "role": "r"},
                        {"id": "b3", "name": "b3", "type": "userTask", "role": "r"}],
         "gateways": [{"id": "g", "type": "exclusiveGateway"}],
         "sequences": [{"id": "s1", "source": "s", "target": "a"}, {"id": "s2", "source": "a", "target": "g"},
                       {"id": "s3", "source": "g", "target": "b1", "condition": "x > 1", "properties": {"priority": 2}},
                       {"id": "s4", "source": "g", "target": "b2", "condition": "x > 0", "properties": {"priority": 1}},
                       {"id": "s5", "source": "g", "target": "b3", "properties": {"default": True}},
                       {"id": "s6", "source": "b1", "target": "e"}, {"id": "s7", "source": "b2", "target": "e"}, {"id": "s8", "source": "b3", "target": "e"}]}
    defn = engine.Definition.from_dict(d)
    w = World(defn, values={})
    w.turn_in("a", {"x": 5})                                     # both conditions true → priority 1 wins
    assert w.statuses() == {"a": "DONE", "b1": "TODO", "b2": "IN_PROGRESS", "b3": "TODO"}
    w2 = World(defn, values={})
    w2.turn_in("a", {"x": -1})                                   # none true → default flow
    assert w2.statuses()["b3"] == "IN_PROGRESS" and w2.row("a")["gateway_decisions"]["g"]["selected"] == []


def test_output_outside_declared_outputData_is_refused(defn):
    w = World(defn)
    with pytest.raises(ValueError, match="may only output"):
        engine.submit(defn, w.inst, w.row("task:diagnose"), {"chosen_skill": "skill:fan-max"}, now=NOW)


def test_processing_requires_submitted_and_same_instance(defn):
    w = World(defn)
    row = w.row("task:diagnose")
    with pytest.raises(ValueError, match="not SUBMITTED"):
        engine.process_submitted(defn, w.inst, row, w.rows, now=NOW)
    w.turn_in("task:diagnose", {})
    with pytest.raises(ValueError, match="already DONE"):
        engine.submit(defn, w.inst, row, {}, now=NOW)
    other = World(defn, values={"asset": "HYD-02"})
    with pytest.raises(ValueError, match="does not belong"):
        engine.submit(defn, w.inst, other.row("task:diagnose"), {}, now=NOW)


def test_condition_evaluator_is_whitelisted():
    assert engine.eval_condition("chosen_skill_kind == 'control'", {"chosen_skill_kind": "control"})
    assert engine.eval_condition("recovered != True", {"recovered": None})
    assert engine.eval_condition("ts1 < 55 and cleared", {"ts1": 52.1, "cleared": True})
    assert not engine.eval_condition("ts1 < 55", {})
    assert engine.eval_condition("kind in ['control', 'work_order']", {"kind": "control"})
    for bad in ("__import__('os')", "a.b == 1", "f(x)", "x if y else z", "[v for v in a]", "1 + 1 == 2"):
        with pytest.raises(ValueError):
            engine.compile_condition(bad)


def test_iso_duration():
    assert engine.iso_duration_seconds("PT10M") == 600
    assert engine.iso_duration_seconds("PT1H30M") == 5400
    assert engine.iso_duration_seconds("P1DT2S") == 86402
    with pytest.raises(ValueError):
        engine.iso_duration_seconds("10 minutes")


def test_definition_validation_catches_broken_files():
    d = json.loads(DEF_PATH.read_text(encoding="utf-8"))
    d["sequences"].append({"id": "x", "source": "task:rank", "target": "nowhere"})
    with pytest.raises(ValueError, match="unknown node"):
        engine.Definition.from_dict(d)
    d = json.loads(DEF_PATH.read_text(encoding="utf-8"))
    d["sequences"][6]["condition"] = "__import__('os').system('x')"
    with pytest.raises(ValueError):
        engine.Definition.from_dict(d)
    d = json.loads(DEF_PATH.read_text(encoding="utf-8"))
    d["activities"][0]["role"] = "없는 역할"
    with pytest.raises(ValueError, match="undefined role"):
        engine.Definition.from_dict(d)
    d = json.loads(DEF_PATH.read_text(encoding="utf-8"))
    d["activities"][4]["attachedEvents"] = ["ev:nope"]
    with pytest.raises(ValueError, match="unknown event"):
        engine.Definition.from_dict(d)


def test_timeline_lists_every_activity_in_flow_order(defn):
    w = World(defn)
    w.turn_in("task:diagnose", {"cause": "c", "failure_mode": "f"})
    tl = engine.timeline(defn, w.inst, w.rows)
    assert [t["activity_id"] for t in tl] == ["task:diagnose", "task:candidates", "task:compliance", "task:rank", "task:select",
                                              "task:command", "task:reobserve", "task:work-order", "task:escalate"]
    assert tl[0]["status"] == "DONE" and tl[1]["status"] == "IN_PROGRESS" and tl[4]["status"] == "TODO"
    assert tl[4]["performer"] == "role:operator" and tl[0]["orchestration"] == "cliagents"
