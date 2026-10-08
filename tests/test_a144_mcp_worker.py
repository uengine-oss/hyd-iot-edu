"""A144 bundle 2 — enterprise-mcp envelope (item 35/390), dmn-mcp cause basis (item 33), worker pause duplicate
handling (item 32) and the single ALLOWED_TOOLS default (item 35/711)."""
import inspect
from pathlib import Path

import psycopg
import pytest

from agentsvc.tools import mcp_kg
from dmn_mcp import tools as dmn
from enterprise_mcp import sql_guard                    # server.py needs fastmcp (container only); it is checked as text below
from enterprise_mcp.tools import EnterpriseTools, guarded
from procsvc import procdb
from test_dmn_mcp import FakeKG, FakeTSDB
from test_enterprise_mcp import D, FakeConn
from test_worker import _fake_exec, _repo, _settings
from worker import hitl, workspace
from worker.runner import Runner
from worker.settings import DEFAULT_ALLOWED_TOOLS, Settings

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- enterprise-mcp
class BrokenConn:
    def __enter__(self):
        raise psycopg.OperationalError("connection to server at \"host.docker.internal\" failed: Connection refused\n\tmore")

    def __exit__(self, *a):
        return False


def test_fixed_reads_and_catalog_answer_a_db_failure_in_the_error_envelope():
    tools = EnterpriseTools(lambda: BrokenConn())
    for call in (lambda: tools.read("mes_orders", asset="HYD-01"), tools.describe_catalog, tools.describe_schema):
        with pytest.raises(psycopg.OperationalError):          # the raw tool raises …
            call()
        out = guarded(call)()                                   # … the served tool answers the envelope
        assert out["result"] == "error" and out["error_kind"] == "UNKNOWN" and out["message"].startswith("database: connection to server")
        assert "\n" not in out["message"]


def test_query_rejection_and_db_failure_carry_the_statement():
    tools = EnterpriseTools(lambda: BrokenConn())
    rejected = guarded(tools.query)(sql="delete from ent.assets")
    assert rejected == {"result": "error", "error_kind": "INVALID", "message": rejected["message"], "statement": "delete from ent.assets"}
    assert rejected["message"].startswith("rejected: ")
    failed = guarded(tools.query)(sql="select 1 from ent.assets")
    assert failed["result"] == "error" and failed["error_kind"] == "UNKNOWN" and failed["statement"] == "select 1 from ent.assets"
    with pytest.raises(KeyError):                               # an unknown fixed read is a programming error, not a DB error
        guarded(tools.read)("drop_everything")


def test_describe_schema_answers_in_the_envelope_with_the_ddl_as_document():
    catalog = {'catalog': 'postgres', 'schema': 'ent', 'relations': [
        {'name': 'assets', 'kind': 'r', 'comment': '설비', 'constraints': [], 'columns': [
            {'name': 'code', 'type': 'text', 'nullable': False, 'default': None, 'comment': None}]}]}
    out = EnterpriseTools(lambda: FakeConn([], [(catalog,)])).describe_schema()
    assert out["result"] == "ok" and isinstance(out["document"], str) and 'create table "ent"."assets"' in out["document"]
    assert "comment on table \"ent\".\"assets\" is '설비'" in out["document"]


def test_server_lists_all_ten_tools_and_guards_each_one():
    text = (ROOT / "it" / "enterprise-mcp" / "enterprise_mcp" / "server.py").read_text(encoding="utf-8")
    head = text.split('"""')[1]
    for name in ("mes_orders", "erp_contract", "erp_inventory", "cmms_history", "qms_lots", "scm_suppliers", "ems_demand",
                 "describe_schema", "describe_catalog", "query"):
        assert name in head, name
    assert text.count("@mcp.tool(annotations=READ)\n") == 10 and text.count("return guarded(") == 10 and "def describe_schema() -> dict" in text
    assert sql_guard.__all__ == ["MAX_ROWS", "READ_FUNCTIONS", "SqlRejected", "guard"] and sql_guard.guard is __import__("hydcommon.sql_read", fromlist=["guard"]).guard


# ---------------------------------------------------------------- dmn-mcp: the cause must have a diagnosis basis
def test_evaluate_cards_refuses_a_cause_without_diagnosis_basis():
    t = dmn.DmnTools(kg=FakeKG(), tsdb=FakeTSDB())
    verified = t._diagnosed_cause("HYD-01", "COOLER_DEGRADATION", "cause:cooler-fin-fouling", "fm:cooling-loss")
    assert verified == {"id": "cause:cooler-fin-fouling", "name": "쿨러 핀 오염", "failureModeId": "fm:cooling-loss", "failureMode": "냉각 능력 상실"}
    assert t.kg.calls[-1] == ("t1", "COOLER_DEGRADATION", "HYD-01")
    with pytest.raises(ValueError, match="진단 지식\\(T1\\)에 없는 원인"):
        t._diagnosed_cause("HYD-01", "COOLER_DEGRADATION", "cause:made-up", "fm:cooling-loss")
    with pytest.raises(ValueError, match="고장 유형 fm:other의 원인이 아닙니다"):
        t._diagnosed_cause("HYD-01", "COOLER_DEGRADATION", "cause:cooler-fin-fouling", "fm:other")
    with pytest.raises(ValueError):
        t._diagnosed_cause("HYD-01", "COOLER_DEGRADATION", "", "fm:cooling-loss")
    out = dmn.enveloped(lambda: t.evaluate_cards("HYD-01", "COOLER_DEGRADATION", "cause:made-up", "fm:cooling-loss"))()
    assert out["result"] == "error" and out["error_kind"] == "INVALID" and "cause:made-up" in out["message"]
    out = dmn.enveloped(lambda: t.submit_decision("HYD-01", "COOLER_DEGRADATION", "cause:made-up", "fm:cooling-loss", "INC-1"))()
    assert out["result"] == "error" and out["error_kind"] == "INVALID"


def test_evaluate_cards_records_the_cause_basis_in_the_decision_origin(monkeypatch):
    t = dmn.DmnTools(kg=FakeKG(), tsdb=FakeTSDB())
    seen = {}

    def fake_decide(kg, registry, tsdb, asset, pattern, cause, origin=None, overrides=None, do_submit=True):
        seen.update(cause=cause, origin=origin, do_submit=do_submit)
        return {"id": "DEC-1", "status": "EVALUATED", "result": {"options": []}}

    monkeypatch.setattr(dmn.decidelib, "decide", fake_decide)
    t.evaluate_cards("HYD-01", "COOLER_DEGRADATION", "cause:cooler-fin-fouling", "fm:cooling-loss")
    assert seen["cause"]["name"] == "쿨러 핀 오염" and seen["origin"]["cause_basis"] == dmn.CAUSE_BASIS and seen["do_submit"] is False
    assert "T1" in dmn.CAUSE_BASIS and "diagnose" in dmn.CAUSE_BASIS


def test_dead_graph_forecast_reader_is_gone():
    assert not hasattr(mcp_kg.KnowledgeGraph, "forecasts")
    assert "t3_forecasts" not in inspect.getsource(mcp_kg)


# ---------------------------------------------------------------- worker: pause duplicates
def _ask_twice(tmp_path, question):
    repo, inst = _repo()
    r = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec("", permission_refusal=question), schema_prompt="# s", resolve_provider=lambda pid: object())
    r.poll_once()
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    ws = workspace.for_run(tmp_path, row["id"], tenant_id="hyd")
    return repo, row, ws, r


def test_the_same_unanswered_question_is_not_notified_twice(tmp_path):
    question = "Claude requested permissions to use Bash, but you haven't granted it yet."
    repo, row, ws, r = _ask_twice(tmp_path, question)
    assert row["draft_status"] == "HUMAN_ASKED" and len(repo.notifications) == 1
    first_job = repo.get_workitem(row["id"])["draft"]["_human_request"]["job_id"]
    # the row is handled again while the person has not answered (e.g. a worker restart re-drives the paused session)
    r._pause(repo.get_workitem(row["id"]), ws, "claude-code", "sess-A", question, "run-again")
    asked = [e for e in repo.list_events(todo_id=row["id"]) if e["event_type"] == "human_asked"]
    assert len(asked) == 1 and len(repo.notifications) == 1
    assert repo.get_workitem(row["id"])["draft"]["_human_request"]["job_id"] == first_job and repo.get_workitem(row["id"])["draft_status"] == "HUMAN_ASKED"
    assert hitl.recall(ws.path).job_id == first_job
    # a different question is a new ask
    r._pause(repo.get_workitem(row["id"]), ws, "claude-code", "sess-A", "다른 질문입니다", "run-again")
    assert len([e for e in repo.list_events(todo_id=row["id"]) if e["event_type"] == "human_asked"]) == 2 and len(repo.notifications) == 2


def test_the_same_question_after_an_answer_is_a_new_ask_and_the_cache_does_not_suppress_it(tmp_path):
    question = "Claude requested permissions to use Bash, but you haven't granted it yet."
    repo, row, ws, _ = _ask_twice(tmp_path, question)
    asked = [e for e in repo.list_events(todo_id=row["id"]) if e["event_type"] == "human_asked"]
    repo.update_workitem(repo.get_workitem(row["id"]) | {"feedback": {"human_answer": "네", "job_id": asked[0]["job_id"]}, "draft_status": "FB_REQUESTED"})
    assert hitl.pending_request(repo.get_workitem(row["id"])) is None          # answered → nothing pending
    r2 = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec("", permission_refusal=question), schema_prompt="# s", resolve_provider=lambda pid: object())
    assert r2.poll_once() == 1
    asked2 = [e for e in repo.list_events(todo_id=row["id"]) if e["event_type"] == "human_asked"]
    assert len(asked2) == 2 and asked2[1]["job_id"] != asked2[0]["job_id"] and len(repo.notifications) == 2
    assert hitl.recall(ws.path).job_id == asked2[1]["job_id"]
    assert hitl.pending_request(repo.get_workitem(row["id"])).job_id == asked2[1]["job_id"]


def test_pending_request_reads_only_a_well_formed_unanswered_db_record():
    req = hitl.PendingRequest(run_id="r", agent_id="claude-code", session_id="s", question="q", job_id="j1", fingerprint="claude-code::q")
    assert hitl.pending_request({"draft": {"_human_request": req.as_dict()}}).job_id == "j1"
    assert hitl.pending_request({"draft": {"_human_request": req.as_dict()}, "feedback": {"job_id": "j1"}}) is None
    assert hitl.pending_request({"draft": {"_human_request": req.as_dict()}, "feedback": {"job_id": "other"}}).job_id == "j1"
    assert hitl.pending_request({"draft": {"_human_request": {"unknown": 1}}}) is None
    assert hitl.pending_request({"draft": "not a dict"}) is None and hitl.pending_request({}) is None


# ---------------------------------------------------------------- worker: one ALLOWED_TOOLS default
def test_allowed_tools_default_lives_in_settings_and_includes_the_python_script_tools(monkeypatch):
    monkeypatch.setenv("ALLOWED_TOOLS", "")
    assert Settings().allowed_tools == DEFAULT_ALLOWED_TOOLS.split(",") and "Bash(python *)" in Settings().allowed_tools
    monkeypatch.delenv("ALLOWED_TOOLS")
    assert Settings().allowed_tools == DEFAULT_ALLOWED_TOOLS.split(",")
    monkeypatch.setenv("ALLOWED_TOOLS", "Read, Glob")
    assert Settings().allowed_tools == ["Read", "Glob"]
