"""MemoryRepo behaves like the Supabase tables and RPCs the engine and the worker use:
fetch_pending_task / save_task_result (agent-sdk function.sql), claim_submitted (completion polling), events, round trips."""
from datetime import datetime, timezone
from pathlib import Path

from procsvc import engine, procdb

DEF_PATH = Path(__file__).resolve().parents[1] / "it" / "process" / "definitions" / "anomaly_response.json"
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def _start(repo):
    defn = engine.Definition.load(DEF_PATH)
    repo.upsert_proc_def(defn.raw)
    inst = engine.new_instance(defn, {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION"}, now=NOW)
    adv = engine.start(defn, inst, now=NOW)
    repo.insert_instance(inst)
    repo.insert_workitems(adv.created)
    repo.update_instance(inst)
    return defn, inst


def test_fetch_pending_task_hands_out_in_progress_agent_rows_once():
    repo = procdb.MemoryRepo()
    defn, inst = _start(repo)
    assert len(repo.list_workitems(proc_inst_id=inst["proc_inst_id"])) == 9                 # every activity pre-created
    assert repo.fetch_pending_task("hyd-process", "w1") == []                                # other orchestration sees nothing
    got = repo.fetch_pending_task("cliagents", "worker-a:1")
    assert len(got) == 1 and got[0]["activity_id"] == "task:diagnose" and got[0]["status"] == "IN_PROGRESS"
    assert got[0]["draft_status"] == "STARTED" and got[0]["consumer"] == "worker-a:1"
    assert repo.fetch_pending_task("cliagents", "worker-b:2") == []                          # STARTED → not handed out twice
    assert repo.list_workitems(status="TODO", agent_orch="cliagents")                        # the later agent tasks are only planned


def test_save_task_result_final_makes_the_row_submitted_for_the_engine():
    repo = procdb.MemoryRepo()
    defn, inst = _start(repo)
    (wi,) = repo.fetch_pending_task("cliagents", "w")
    repo.save_task_result(wi["id"], {"text": "…", "cause": "cause:x"}, final=False)
    row = repo.get_workitem(wi["id"])
    assert row["status"] == "IN_PROGRESS" and row["draft"]["cause"] == "cause:x" and row["draft_status"] == "STARTED"
    repo.save_task_result(wi["id"], {"cause": "cause:x", "failure_mode": "fm:y", "guide_card": {}}, final=True)
    row = repo.get_workitem(wi["id"])
    assert row["status"] == "SUBMITTED" and row["output"]["failure_mode"] == "fm:y" and row["draft_status"] == "COMPLETED" and row["consumer"] is None
    assert repo.fetch_pending_task("cliagents", "w") == []                                   # SUBMITTED is the engine's, not the worker's


def test_draft_mode_keeps_the_row_for_a_person():
    repo = procdb.MemoryRepo()
    defn, inst = _start(repo)
    (wi,) = repo.fetch_pending_task("cliagents", "w")
    repo.update_workitem(wi | {"agent_mode": "DRAFT"})
    repo.save_task_result(wi["id"], {"cause": "cause:x"}, final=True)
    row = repo.get_workitem(wi["id"])
    assert row["status"] == "IN_PROGRESS" and row["draft"] == {"cause": "cause:x"} and row["draft_status"] == "COMPLETED" and row["output"] is None


def test_update_task_error_and_feedback_requeue():
    repo = procdb.MemoryRepo()
    defn, inst = _start(repo)
    (wi,) = repo.fetch_pending_task("cliagents", "w")
    repo.update_task_error(wi["id"])
    assert repo.get_workitem(wi["id"])["draft_status"] == "FAILED" and repo.get_workitem(wi["id"])["consumer"] is None
    assert repo.fetch_pending_task("cliagents", "w") == []                                   # FAILED stays for a person to look at
    repo.set_draft_status(wi["id"], "FB_REQUESTED")
    assert repo.fetch_pending_task("cliagents", "w")[0]["id"] == wi["id"]                    # feedback requeues it


def test_claim_submitted_is_the_engines_queue():
    repo = procdb.MemoryRepo()
    defn, inst = _start(repo)
    (wi,) = repo.fetch_pending_task("cliagents", "w")
    assert repo.claim_submitted("engine") == []
    repo.save_task_result(wi["id"], {"cause": "c", "failure_mode": "f", "guide_card": {}}, final=True)
    got = repo.claim_submitted("engine")
    assert len(got) == 1 and got[0]["id"] == wi["id"] and got[0]["consumer"] == "engine"
    assert repo.claim_submitted("engine-2") == []                                            # held by the first engine


def test_engine_round_trip_through_repo_until_human_task():
    repo = procdb.MemoryRepo()
    defn, inst = _start(repo)
    outputs = {"task:diagnose": {"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss"},
               "task:candidates": {"candidates": ["skill:fan-max-derate"]}, "task:compliance": {"compliance": {}},
               "task:rank": {"decision_id": "DEC-1"}}
    for _ in range(4):
        (wi,) = repo.fetch_pending_task("cliagents", "w")
        repo.save_task_result(wi["id"], outputs[wi["activity_id"]], final=True)
        (wi,) = repo.claim_submitted("engine")
        inst = repo.get_instance(wi["proc_inst_id"])
        rows = [r if r["id"] != wi["id"] else wi for r in repo.list_workitems(proc_inst_id=inst["proc_inst_id"])]
        adv = engine.process_submitted(defn, inst, wi, rows, now=NOW)
        for r in adv.updated:
            repo.update_workitem(r)
        repo.insert_workitems(adv.created)
        repo.update_instance(inst)
    mine = repo.list_workitems(status="IN_PROGRESS", user_id="role:operator")
    assert len(mine) == 1 and mine[0]["activity_id"] == "task:select"
    saved = repo.get_instance(inst["proc_inst_id"])
    assert saved["status"] == "RUNNING" and saved["current_activity_ids"] == ["task:select"]
    assert engine.variables(saved)["decision_id"] == "DEC-1" and engine.variables(saved)["cause"] == "cause:cooler-fin-fouling"
    done = repo.list_workitems(proc_inst_id=inst["proc_inst_id"], status="DONE")
    assert [w["activity_id"] for w in done] == ["task:diagnose", "task:candidates", "task:compliance", "task:rank"]
    timer = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "ev:select-timeout")
    assert timer["status"] == "IN_PROGRESS" and timer["due_date"]


def test_events_notifications_users_forms_tenant():
    repo = procdb.MemoryRepo()
    defn, inst = _start(repo)
    (wi,) = repo.fetch_pending_task("cliagents", "w")
    repo.record_events([{"job_id": "run-1", "todo_id": wi["id"], "proc_inst_id": inst["proc_inst_id"], "crew_type": "result",
                         "event_type": "task_started", "data": {"goal": "원인 진단"}},
                        {"job_id": "run-1", "todo_id": wi["id"], "proc_inst_id": inst["proc_inst_id"], "crew_type": "tool",
                         "event_type": "tool_usage_started", "data": {"tool": "mcp__neo4j__read_neo4j_cypher"}}])
    assert [e["event_type"] for e in repo.list_events(todo_id=wi["id"])] == ["task_started", "tool_usage_started"]
    assert all(e["id"] for e in repo.list_events(proc_inst_id=inst["proc_inst_id"])) and repo.list_events(todo_id="nope") == []
    repo.insert_notification({"title": "질문", "type": "workitem_bpm", "user_id": "role:operator", "url": f"/todolist/{wi['id']}"})
    assert repo.notifications[0]["url"].endswith(wi["id"])
    repo.upsert_user({"id": "role:operator", "username": "운전원", "is_agent": False})
    repo.upsert_user({"id": "sys:agent", "username": "AI 에이전트", "is_agent": True, "agent_type": "agent"})
    assert [u["id"] for u in repo.list_users(["sys:agent", "role:operator"])] == ["role:operator", "sys:agent"]
    repo.upsert_form({"id": "select_card", "fields_json": [{"key": "chosen_skill", "type": "select"}]})
    assert repo.get_form("select_card")["fields_json"][0]["key"] == "chosen_skill" and repo.get_form("nope") is None
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": {"mcpServers": {"neo4j": {"command": "uvx"}}}})
    assert repo.get_tenant()["mcp"]["mcpServers"]["neo4j"]["command"] == "uvx"


def test_repo_returns_copies_not_live_objects():
    repo = procdb.MemoryRepo()
    defn, inst = _start(repo)
    a = repo.get_instance(inst["proc_inst_id"])
    a["status"] = "COMPLETED"
    assert repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING"


def test_make_repo_respects_env(monkeypatch):
    monkeypatch.setenv("PROCESS_REPO", "memory")
    assert isinstance(procdb.make_repo(), procdb.MemoryRepo)
    monkeypatch.setenv("PROCESS_REPO", "pg")
    r = procdb.make_repo()
    assert isinstance(r, procdb.PgRepo) and r.dsn.endswith("/postgres")   # constructing does not connect
