"""instance_mode wiring with the real Incident state machine and decision rules, MemoryRepo, and fake IO:
alert → instance + Incident → legacy-agent bridge plays the four agent tasks through the worker RPCs → person selects a card
(role check) → action.cmd through machine.on_approve → ACK → re-observation → CMMS work order → ev:closed → Execution layer."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from procsvc import decisions as declib, engine, instance_mode, machine

DEFS = Path(__file__).resolve().parents[1] / "it" / "process" / "definitions"
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
ALERT = {"alertId": "HYD-01-COOLER_DEGRADATION-7", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "state": "RAISE"}
GUIDE_CARD_ACTIONS = [
    {"code": "FAN_SET", "actionId": "act:fan-set", "kind": "command", "param": "fan_pct", "value": 100, "paramRange": [0, 100], "sop": {"id": "SOP-COOL-02", "steps": []}},
    {"code": "LOAD_SET", "actionId": "act:load-set", "kind": "command", "param": "load_pct", "value": 80, "paramRange": [50, 100], "sop": {"id": "SOP-COOL-02", "steps": []}},
    {"code": "WO_CREATE", "actionId": "act:wo", "kind": "work_order", "sop": {"id": "SOP-COOL-02", "steps": []}},
]


class NoFx(machine.Effects):
    def emit_cmd(self, cmd): pass
    def emit_audit(self, evt): pass
    def set_timer(self, name, seconds): pass


def _decision_payload(incident_id: str) -> dict:
    option = {"id": "skill:fan-max-derate", "sopId": "SOP-COOL-02", "name": "팬 최대 + 부하 80 %", "kind": "control", "feasible": True, "rank": 1,
              "approver": {"id": "role:prod-mgr", "name": "생산관리자", "level": 2},
              "actions": [{"code": "FAN_SET", "kind": "command", "param": "fan_pct", "value": 100, "target": "sys:scada"},
                          {"code": "LOAD_SET", "kind": "command", "param": "load_pct", "value": 80, "target": "sys:scada"},
                          {"code": "WO_CREATE", "kind": "transaction", "value": "쿨러 세척", "target": "sys:cmms"}],
              "violations": [], "penalties": [], "warnings": [{"annotation": "예측 유온 55.4 ℃"}]}
    return {"id": "DEC-1003-001-ab12", "schema": "v2", "asset": "HYD-01",
            "origin": {"kind": "alert", "incident": incident_id, "cause": "cause:cooler-fin-fouling", "failureMode": "fm:cooling-loss"},
            "recommended": "skill:fan-max-derate", "explanation": "납기 오더 진행 중", "options": [option],
            "roles": {"role:operator": {"level": 1}, "role:prod-mgr": {"level": 2}}}


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setenv("PROCESS_REPO", "memory")
    monkeypatch.setattr(instance_mode, "DEFINITIONS_DIR", DEFS)
    monkeypatch.setattr(instance_mode, "AGENT_BRIDGE", "legacy")
    incidents, book, audits, cypher, executed = {}, {}, [], [], []

    def approve_incident(inc, by, commands):
        cmd = machine.on_approve(inc, by, commands, NOW, NoFx(), time_scale=20)
        rt = instance_mode.current()
        rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)       # what main._after does, synchronously here
        return cmd

    def exec_skill(d, item):
        executed.append((d["id"], item["code"]))
        return {"ok": True, "ref": "WO-1003-AB12", "skill": item["skill"], "code": item["code"], "system": item["system"], "detail": "쿨러 세척 — 야간 정비창"}

    ctx = instance_mode.ProcessContext(
        incidents=incidents, book=book, state={"incidents": 0}, time_scale=20.0, persist=lambda: None,
        audit=lambda asset, actor, event, detail, incident=None: audits.append(event),
        cypher=lambda q, **p: cypher.append(p) or [dict(projection_key=p['id'],projection_revision=p['revision'],projection_hash=p['payload_hash'])], exec_skill=exec_skill, record_decision=lambda d: None,
        approve_incident=approve_incident, get_loop=lambda: None,
        check_approval=lambda *args: {'allowed': True, 'scope': 'unit-test-source-double'})
    rt = instance_mode.build(ctx)
    return {"rt": rt, "ctx": ctx, "incidents": incidents, "book": book, "audits": audits, "cypher": cypher, "executed": executed}


def _row(rt, inst, activity_id):
    return next((w for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == activity_id), None)


def test_alert_opens_instance_and_incident_once(world):
    rt, incidents = world["rt"], world["incidents"]
    inst = rt.on_alert_raise(ALERT)
    assert len(incidents) == 1
    inc = next(iter(incidents.values()))
    assert inc.state == "AWAITING_APPROVAL" and inc.alert_id == ALERT["alertId"] and engine.variables(inst)["incident"] == inc.id
    assert "INCIDENT_OPENED" in world["audits"] and world["ctx"].state["mode"] == "instance" and world["ctx"].state["incidents"] == 1
    assert rt.on_alert_raise(ALERT, now=NOW) is None and len(incidents) == 1        # a second RAISE neither opens an instance nor an incident


def test_bridge_then_select_then_plc_path_closes_the_instance(world):
    rt, incidents, book = world["rt"], world["incidents"], world["book"]
    inst = rt.on_alert_raise(ALERT)
    inc = next(iter(incidents.values()))
    # the legacy agent would POST its guide card (/api/incidents) and its ranked cards (/api/decisions)
    inc.card = dict(inc.card, recommended=GUIDE_CARD_ACTIONS, causes=[{"id": "cause:cooler-fin-fouling"}], topCause="cause:cooler-fin-fouling")
    d = declib.new(_decision_payload(inc.id))
    book[d["id"]] = d
    instance_mode._bridge_legacy_agent(d)
    items = {w["activity_id"]: w for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])}
    assert [items[a]["status"] for a in ("task:diagnose", "task:candidates", "task:compliance", "task:rank")] == ["DONE"] * 4
    assert items["task:select"]["status"] == "IN_PROGRESS" and items["ev:select-timeout"]["status"] == "IN_PROGRESS"
    assert all(items[a]["draft_status"] == "COMPLETED" and items[a]["consumer"] is None for a in ("task:diagnose", "task:rank"))
    assert [e["event_type"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])].count("task_completed") == 4
    saved = rt.repo.get_instance(inst["proc_inst_id"])
    assert engine.variables(saved)["decision_id"] == d["id"] and engine.variables(saved)["cause"] == "cause:cooler-fin-fouling"
    assert inc.card["recommended"] == GUIDE_CARD_ACTIONS                     # diagnose output re-applied the card unchanged

    sel = items["task:select"]
    # an operator may not pick a card that needs the production manager (ontology role level)
    with pytest.raises(PermissionError):
        rt.select(sel["id"], d["id"], "skill:fan-max-derate", by="OP-17", role="role:operator", now=NOW)
    assert d["state"] == "PENDING_APPROVAL" and rt.repo.get_workitem(sel["id"])["status"] == "IN_PROGRESS"

    with pytest.raises(ValueError, match='실행 조치값'):
        rt.select(sel['id'],d['id'],'skill:fan-max-derate',by='이생산',role='role:prod-mgr',fan_pct=95,now=NOW)
    out = rt.select(sel["id"], d["id"], "skill:fan-max-derate", by="이생산", role="role:prod-mgr", reason="납기", now=NOW)
    assert d["state"] == "APPROVED" and d["chosen"] == "skill:fan-max-derate"
    assert inc.state == "AWAITING_ACK" and inc.actions == [{"code": "FAN_SET", "fan_pct": 100}, {"code": "LOAD_SET", "load_pct": 80}] and inc.cmd_id
    assert out["enterprise_results"] == []                                        # WO_CREATE waits for task:work-order
    cmd_task = _row(rt, inst, "task:command")
    assert cmd_task["status"] == "SUBMITTED" and inc.cmd_id in cmd_task["log"]

    # PLC ACK DONE → RE_OBSERVING: task:command done, task:reobserve waiting
    machine.on_status(inc, {"cmdId": inc.cmd_id, "result": "DONE", "t": "2026-10-03T12:00:05Z"}, NOW, NoFx(), time_scale=20)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    assert inc.state == "RE_OBSERVING" and _row(rt, inst, "task:command")["status"] == "DONE" and _row(rt, inst, "task:reobserve")["status"] == "SUBMITTED"

    # alert CLEAR + re-observation timer with TS1 50 ℃ → RESOLVED → … → CLOSED
    machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, NoFx())
    machine.on_timer(inc, "reobs", NOW, 50.0, NoFx(), time_scale=20)
    assert inc.state == "RESOLVED" and inc.work_order is None
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    assert inc.state == 'CLOSED' and inc.work_order['id'] == 'WO-1003-AB12'
    saved = rt.repo.get_instance(inst["proc_inst_id"])
    assert saved["status"] == "COMPLETED" and saved["end_event"] == "ev:closed" and engine.variables(saved)["recovered"] is True
    assert world["executed"] == [(d["id"], "WO_CREATE")] and d["state"] == "EXECUTED"
    assert d["executions"][-1]["code"] == "WO_CREATE" and d["executions"][-1]["ref"] == "WO-1003-AB12"
    assert world["cypher"][-1]["incident"] == inc.id and world["cypher"][-1]["status"] == "COMPLETED"
    assert {w["status"] for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])} == {"DONE", "CANCELLED"}


def test_bridge_feeds_only_its_own_instance_when_two_are_open(world):
    # two alerts → two instances both waiting on task:diagnose; the second decision must not land in the first (live check 10-04)
    rt, incidents, book = world["rt"], world["incidents"], world["book"]
    a1 = rt.on_alert_raise(ALERT)
    a2 = rt.on_alert_raise(dict(ALERT, alertId="HYD-02-PUMP_LEAKAGE-1", asset="HYD-02", pattern="PUMP_LEAKAGE"))
    inc2 = next(i for i in incidents.values() if i.asset == "HYD-02")
    d = declib.new(dict(_decision_payload(inc2.id), id="DEC-1003-002-cd34", asset="HYD-02"))
    book[d["id"]] = d
    instance_mode._bridge_legacy_agent(d)
    s1 = {w["activity_id"]: w for w in rt.repo.list_workitems(proc_inst_id=a1["proc_inst_id"])}
    s2 = {w["activity_id"]: w for w in rt.repo.list_workitems(proc_inst_id=a2["proc_inst_id"])}
    assert s1["task:diagnose"]["status"] == "IN_PROGRESS" and s1["task:diagnose"].get("draft_status") is None and s1["task:diagnose"].get("consumer") is None
    assert all(s2[a]["status"] == "DONE" for a in ("task:diagnose", "task:candidates", "task:compliance", "task:rank")) and s2["task:select"]["status"] == "IN_PROGRESS"


def test_bridge_ignores_decisions_without_a_running_instance(world):
    rt, book = world["rt"], world["book"]
    d = declib.new(_decision_payload("INC-nobody"))
    book[d["id"]] = d
    instance_mode._bridge_legacy_agent(d)                                       # no exception
    assert rt.repo.list_instances() == []


def test_ack_timeout_escalates(world):
    rt, incidents, book = world["rt"], world["incidents"], world["book"]
    inst = rt.on_alert_raise(ALERT)
    inc = next(iter(incidents.values()))
    inc.card = dict(inc.card, recommended=GUIDE_CARD_ACTIONS)
    d = declib.new(_decision_payload(inc.id))
    book[d["id"]] = d
    instance_mode._bridge_legacy_agent(d)
    rt.select(_row(rt, inst, "task:select")["id"], d["id"], "skill:fan-max-derate", by="이생산", role="role:prod-mgr", now=NOW)
    machine.on_timer(inc, "ack", NOW, None, NoFx(), time_scale=20)                # 30 s without ACK
    assert inc.state == "ESCALATED" and inc.reason == "ACK_TIMEOUT"
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    esc = _row(rt, inst, "task:escalate")
    assert esc["status"] == "IN_PROGRESS" and esc["user_id"] == "role:prod-mgr"
    assert engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))["recovered"] is False


def test_worker_status_reports_unreachable_as_a_state(monkeypatch):
    from procsvc import instance_mode
    out = instance_mode.worker_status("http://127.0.0.1:9")            # nothing listens there
    assert out["reachable"] is False and out["health"] is None and out["error"] and out["url"] == "http://127.0.0.1:9"
    calls = []

    def fake_get(url, timeout=2.0):
        calls.append(url)
        return {"status": "ok", "runs_in_flight": 1} if url.endswith("/health") else {"agents": [{"agent_id": "claude-code", "installed": True, "default": True}]}
    monkeypatch.setattr(instance_mode, "_get_json", fake_get)
    out = instance_mode.worker_status("http://w:8097")
    assert out["reachable"] and out["health"]["runs_in_flight"] == 1 and out["agents"][0]["agent_id"] == "claude-code" and calls == ["http://w:8097/health", "http://w:8097/agents"]


@pytest.mark.parametrize('target_index',[0,11])
def test_legacy_bridge_claims_only_its_instance_without_disturbing_other_queues(world,target_index):
    rt=world['rt']
    runs=[rt.on_alert_raise(dict(ALERT,alertId=f'claim-{i}'),now=NOW) for i in range(14)]
    target=runs[target_index]['proc_inst_id']
    rows=[_row(rt,i,'task:diagnose') for i in runs]
    other=rows[1]
    other.update(draft_status='FB_REQUESTED',draft={'text':'previous attempt'})
    rt.repo.update_workitem(other)
    before={w['id']:rt.repo.get_workitem(w['id']) for w in rows}
    claimed=instance_mode._claim_own(target)
    assert claimed is not None and claimed['proc_inst_id']==target
    for wid,prior in before.items():
        if wid!=claimed['id']:
            assert rt.repo.get_workitem(wid)==prior,'another instance was claimed or its feedback state changed'
    assert instance_mode._claim_own(target) is None


def test_legacy_bridge_recovers_transient_empty_claim_without_resubmitting_decision(world, monkeypatch):
    rt = world['rt']
    inst = rt.on_alert_raise(ALERT, now=NOW)
    inc = next(iter(world['incidents'].values()))
    inc.card = dict(inc.card, recommended=GUIDE_CARD_ACTIONS)
    decision = declib.new(_decision_payload(inc.id))
    world['book'][decision['id']] = decision
    real_claim = instance_mode._claim_own
    calls = []
    def contended(pid):
        calls.append(pid)
        return None if len(calls) == 4 else real_claim(pid)
    with monkeypatch.context() as patch:
        patch.setattr(instance_mode, '_claim_own', contended)
        instance_mode._bridge_legacy_agent(decision)
    assert _row(rt, inst, 'task:rank')['status'] == 'IN_PROGRESS'
    instance_mode.reconcile_legacy_decisions()
    assert _row(rt, inst, 'task:select')['status'] == 'IN_PROGRESS'
    events = rt.repo.list_events(proc_inst_id=inst['proc_inst_id'])
    assert sum(e['event_type'] == 'task_started' for e in events) == 4
    instance_mode.reconcile_legacy_decisions()
    assert len(rt.repo.list_events(proc_inst_id=inst['proc_inst_id'])) == len(events)


def test_legacy_recovery_does_not_take_over_a_real_worker_run(world):
    rt = world['rt']
    inst = rt.on_alert_raise(ALERT, now=NOW)
    inc = next(iter(world['incidents'].values()))
    decision = declib.new(_decision_payload(inc.id))
    world['book'][decision['id']] = decision
    first = _row(rt, inst, 'task:diagnose')
    rt.repo.record_events([{'job_id':'codex:started', 'todo_id':first['id'], 'proc_inst_id':inst['proc_inst_id'],
                           'event_type':'task_started', 'crew_type':'agent', 'data':{'name':'codex'}}])
    rt.repo.record_events([{'job_id':f'filler-{i}', 'todo_id':first['id'], 'proc_inst_id':inst['proc_inst_id'],
                           'event_type':'task_working', 'crew_type':'agent', 'data':{}} for i in range(550)])
    instance_mode.reconcile_legacy_decisions()
    assert _row(rt, inst, 'task:diagnose')['status'] == 'IN_PROGRESS'
    assert _row(rt, inst, 'task:diagnose').get('draft_status') != 'COMPLETED'
