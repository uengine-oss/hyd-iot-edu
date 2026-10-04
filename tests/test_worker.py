"""agent-worker (the cliagents agent type) against MemoryRepo and a fake CLI: prompt sections and the output contract,
outcome parsing, event translation, the MCP bridge from tenants.mcp, HITL pause/resume, cancellation, failure."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cliagents import ExecEvent, ExecEventKind, Permission

from procsvc import engine, procdb
from worker import bridge, context, events as ui_events, hitl, outcome, prompt
from worker.runner import Runner
from worker.settings import Settings

DEF_PATH = Path(__file__).resolve().parents[1] / "it" / "process" / "definitions" / "anomaly_response.json"
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
FORM_DIAGNOSE = {"id": "diagnose", "fields_json": [{"key": "cause", "type": "text", "text": "원인 노드 id"}, {"key": "failure_mode", "type": "text", "text": "고장 유형"},
                                                   {"key": "guide_card", "type": "object", "text": "가이드 카드"}]}
TENANT_MCP = {"mcpServers": {"neo4j": {"command": "uvx", "args": ["mcp-neo4j-cypher@0.4.1", "--transport", "stdio"], "env": {"NEO4J_URI": "bolt://neo4j:7687"}},
                             "enterprise": {"type": "url", "url": "http://enterprise-mcp:8199/mcp", "transport": "streamable_http"},
                             "hyd-dmn": {"type": "url", "url": "http://dmn-mcp:8198/mcp", "transport": "streamable_http"}}}


def _repo():
    repo = procdb.MemoryRepo()
    defn = engine.Definition.load(DEF_PATH)
    repo.upsert_proc_def(defn.raw)
    repo.upsert_form(FORM_DIAGNOSE)
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": TENANT_MCP})
    repo.upsert_user({"id": "sys:agent", "username": "AI 에이전트", "is_agent": True, "agent_type": "agent", "goal": "원인 진단"})
    repo.upsert_user({"id": "role:operator", "username": "운전원", "email": "operator@hyd.local", "is_agent": False})
    inst = engine.new_instance(defn, {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "alert": {"alertId": "A"}, "incident": "INC-1"}, now=NOW)
    adv = engine.start(defn, inst, now=NOW)
    repo.insert_instance(inst)
    repo.insert_workitems(adv.created)
    repo.update_instance(inst)
    return repo, inst


def _settings(tmp_path, **over):
    return Settings(workspace_root=tmp_path, schema_prompt_path=tmp_path / "none.md", consumer="t:1", cancel_check_every_s=0, **over)


def _fake_exec(answer: str, session="sess-A", is_error=False, requests=None, permission_refusal=None, on_event=None):
    def fn(provider, request, env):
        if requests is not None:
            requests.append((request, env))
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="claude-sonnet-4-6", session_id=session)
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__neo4j__read_neo4j_cypher", tool_input={"query": "MATCH …"}, tool_use_id="t1", session_id=session)
        if on_event:
            on_event()
        yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="mcp__neo4j__read_neo4j_cypher", text="[…]", tool_use_id="t1", session_id=session)
        if permission_refusal:
            yield ExecEvent(kind=ExecEventKind.PERMISSION_REQUEST, tool="Bash", text=permission_refusal, tool_use_id="t2", session_id=session, is_error=True)
        yield ExecEvent(kind=ExecEventKind.RESULT, text=answer, session_id=session, is_error=is_error)
    return fn


# ---------------------------------------------------------------- prompt · contract
def test_prompt_has_the_product_sections_and_a_json_contract_from_the_form():
    row = {"activity_name": "원인 진단", "query": "[Instruction]\n경보 패턴에서 원인을 찾는다\n\n[InputData]\n{\"pattern\": \"COOLER_DEGRADATION\"}"}
    extras = {"users": [{"username": "운전원"}], "agents": [{"username": "AI 에이전트", "goal": "원인 진단"}], "summarized_feedback": "원인 근거가 약했다",
              "form_fields": FORM_DIAGNOSE["fields_json"] + [{"key": "kind", "type": "select", "text": "종류", "items": [{"control": "즉시 제어"}, {"work_order": "작업지시"}]}]}
    text = prompt.build(row, extras, workdir="/workspace/hyd/t1")
    for section in ("## 업무", "## 지시사항", "## 참여자", "## 이전 결과에 대한 피드백", "## 작업 공간", "## 결과 제출 형식"):
        assert section in text
    assert "- 담당자: 운전원" in text and "- 에이전트: AI 에이전트 (원인 진단)" in text and "COOLER_DEGRADATION" in text
    assert "`cause`: 원인 노드 id" in text and "허용값(이 중 하나를 그대로): `control`(즉시 제어), `work_order`(작업지시)" in text
    assert '"guide_card": ""' in text and "허용값 중 하나를 그대로" in text
    assert prompt.field_keys(FORM_DIAGNOSE["fields_json"]) == ["cause", "failure_mode", "guide_card"]
    assert "최종 결과 본문을 그대로" in prompt.output_contract(None)
    assert "담당자 응답: 네" in prompt.resume_prompt("네") and "새로 진행" in prompt.resume_prompt("네", restarted=True, previous_summary="…")


# ---------------------------------------------------------------- outcome
def test_outcome_reads_direct_fenced_or_trailing_json_and_reports_mismatches():
    fields = FORM_DIAGNOSE["fields_json"]
    text = "근거를 모았다.\n```json\n{\"cause\": \"cause:x\", \"failure_mode\": \"fm:y\", \"guide_card\": {\"a\": 1}, \"extra\": 2}\n```\n끝."
    out = outcome.interpret(text, fields)
    assert out.contract_met and out.outputs == {"cause": "cause:x", "failure_mode": "fm:y", "guide_card": {"a": 1}} and out.payload["text"] == text
    trailing = '설명을 먼저 쓴다 {"note": 1} 그리고 답 {"cause": "c", "failure_mode": "f", "guide_card": {"k": "v"}}'
    assert outcome.interpret(trailing, fields).outputs["cause"] == "c"
    assert outcome.interpret('{"cause": "c", "failure_mode": "f", "guide_card": {}}', fields).contract_met is False      # empty object is blank
    missing = outcome.interpret('{"cause": "c"}', fields)
    assert not missing.contract_met and missing.missing_fields == ["failure_mode", "guide_card"] and "비어 있습니다" in missing.mismatch_reason
    assert not outcome.interpret("원인은 쿨러 핀 오염입니다.", fields).contract_met
    free = outcome.interpret("자유 서술", context.FREEFORM_FIELDS)
    assert free.contract_met and free.outputs == {} and free.payload == {"text": "자유 서술"}


# ---------------------------------------------------------------- events
def test_exec_events_become_ui_events_and_event_rows():
    ui = ui_events.translate(ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__neo4j__read_neo4j_cypher", tool_input={"query": "MATCH (n) RETURN n"}, tool_use_id="t1"))
    assert ui[0].type == "tool_start" and ui[0].data["tool"] == "mcp__neo4j__read_neo4j_cypher"
    row = ui_events.row_of(ui[0], job_id="run-1", todo_id="w1", proc_inst_id="p1", crew_type="cliagents:claude-code")
    assert row["event_type"] == "tool_usage_started" and row["data"]["input"]["query"].startswith("MATCH")
    end = ui_events.translate(ExecEvent(kind=ExecEventKind.TOOL_END, tool="x", text="y" * 5000, is_error=False))[0]
    assert end.type == "tool_end" and end.data["output"].endswith("(생략됨)")
    assert ui_events.translate(ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT, text="…"))[0].type == "text"
    assert ui_events.row_of(ui_events.translate(ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT, text="…"))[0], job_id="j", todo_id="w", proc_inst_id=None, crew_type="c") is None
    assert ui_events.translate(ExecEvent(kind=ExecEventKind.RESULT, text="done")) == []
    assert ui_events.translate(ExecEvent(kind=ExecEventKind.UNKNOWN, raw={"type": "hook"}))[0].type == "agent_log"
    assert ui_events.task_started({"activity_name": "원인 진단", "query": "q"}, "Claude Code") == {"goal": "원인 진단", "name": "Claude Code", "role": "CLI 코딩 에이전트", "task_description": "q"}


# ---------------------------------------------------------------- bridge · hitl
def test_bridge_writes_stdio_and_http_servers_from_tenant_mcp(tmp_path):
    res = bridge.install(tmp_path, TENANT_MCP, provider_id="claude-code", isolate_config_dir=False)
    cfg = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert cfg["neo4j"] == {"command": "uvx", "args": ["mcp-neo4j-cypher@0.4.1", "--transport", "stdio"], "env": {"NEO4J_URI": "bolt://neo4j:7687"}}
    assert cfg["enterprise"] == {"type": "http", "url": "http://enterprise-mcp:8199/mcp"} and sorted(res.servers) == ["enterprise", "hyd-dmn", "neo4j"]
    assert res.env == {}                                                     # subscription login: config dir is not relocated
    isolated = bridge.install(tmp_path, TENANT_MCP, provider_id="claude-code", isolate_config_dir=True)
    assert isolated.env["CLAUDE_CONFIG_DIR"].endswith("claude-code") and Path(isolated.env["CLAUDE_CONFIG_DIR"]).is_dir()
    assert sorted(bridge.install(tmp_path, None).servers) == ["enterprise", "hyd-dmn", "neo4j"]   # idempotent merge keeps earlier entries


def test_codex_bridge_native_transports_and_provider_specific_arguments(tmp_path):
    import tomllib
    rw = {"neo4j:7687": "127.0.0.1:7687"}
    res = bridge.install(tmp_path, TENANT_MCP, provider_id="codex", host_rewrite=rw)
    config = tomllib.loads(Path(res.config_path).read_text(encoding="utf-8"))
    servers = config["mcp_servers"]
    assert servers["neo4j"]["env"]["NEO4J_URI"] == "bolt://127.0.0.1:7687"
    assert servers["enterprise"]["url"] == "http://enterprise-mcp:8199/mcp"
    assert servers["neo4j"]["enabled_tools"] == ["get_neo4j_schema", "read_neo4j_cypher"]
    assert all(s["required"] for s in servers.values())
    assert res.env == {} and "--ignore-user-config" in res.extra_args
    assert res.extra_args[res.extra_args.index('--disable')+1] == 'apps'
    assert not (tmp_path / ".mcp.json").exists()
    repo, inst = _repo()
    requests = []
    runner = Runner(_settings(tmp_path, cli_agent="codex"), repo,
                    exec_fn=_fake_exec('{"cause":"c","failure_mode":"f","guide_card":{}}', requests=requests),
                    schema_prompt="s", resolve_provider=lambda pid: object())
    assert runner.poll_once() == 1
    assert "--allowedTools" not in requests[0][0].extra_args
    assert "--ignore-user-config" in requests[0][0].extra_args


def test_codex_session_parser_and_resume_flags(tmp_path, monkeypatch):
    from cliagents import ExecRequest
    from worker.codex_provider import WorkerCodexProvider
    provider = WorkerCodexProvider()
    monkeypatch.setattr(provider, "resolve_executable", lambda: "codex")
    parser = provider.exec_parser()
    event = parser.feed({"type": "thread.started", "thread_id": "session-42"})[0]
    assert event.session_id == "session-42"
    argv = provider.exec_argv(ExecRequest(prompt="continue", workdir=str(tmp_path),
                                         permission=Permission.READ_ONLY, resume_session=event.session_id))
    assert argv.index("--sandbox") < argv.index("resume")
    assert argv.index("--cd") < argv.index("resume")
    assert argv[-3:] == ["resume", "session-42", "continue"]


def test_cli_error_with_valid_json_is_still_failed(tmp_path):
    repo, inst = _repo()
    runner = Runner(_settings(tmp_path), repo,
                    exec_fn=_fake_exec('{"cause":"c","failure_mode":"f","guide_card":{}}', is_error=True),
                    schema_prompt="s", resolve_provider=lambda pid: object())
    runner.poll_once()
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    assert row["draft_status"] == "FAILED" and row["output"] is None


def test_cli_startup_failure_retains_stderr(monkeypatch):
    from worker import runner
    from cliagents.execution import _LAST_RUN
    def broken_stream(*args, **kwargs):
        yield ExecEvent(kind=ExecEventKind.RESULT, text="")
        _LAST_RUN.returncode = 1
        _LAST_RUN.stderr = "required MCP server failed to initialize"
    monkeypatch.setattr(runner, "stream_exec", broken_stream)
    with pytest.raises(runner.RunFailed, match="required MCP server failed"):
        list(runner._exec_stream(None, None, None))


def test_hitl_pause_is_written_down_and_resumed(tmp_path):
    req = hitl.PendingRequest(run_id="r", agent_id="claude-code", session_id="s1", question="Bash를 써도 됩니까?\n(retry 3)", fingerprint=hitl.fingerprint("Bash", "Bash를 써도 됩니까?\n(retry 3)"))
    assert hitl.remember(tmp_path, req) and not hitl.remember(tmp_path, req)           # same question twice → one notification
    assert hitl.recall(tmp_path).session_id == "s1" and hitl.fingerprint("Bash", "Bash를 써도 됩니까?\n(retry 9)") == req.fingerprint
    plan = hitl.plan_resume(tmp_path, workspace_exists=True)
    assert plan.session_id == "s1" and not plan.restarted
    hitl.clear(tmp_path)
    assert hitl.recall(tmp_path) is None and hitl.plan_resume(tmp_path, workspace_exists=False).restarted


# ---------------------------------------------------------------- runner
def test_runner_claims_runs_traces_and_submits_through_the_worker_rpcs(tmp_path):
    repo, inst = _repo()
    reqs = []
    answer = '```json\n{"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"recommended": []}}\n```'
    r = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec(answer, requests=reqs), schema_prompt="# s", resolve_provider=lambda pid: object())
    assert r.poll_once() == 1
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    assert row["status"] == "SUBMITTED" and row["draft_status"] == "COMPLETED" and row["consumer"] is None
    assert row["output"]["cause"] == "cause:cooler-fin-fouling" and row["output"]["cliagents_session_id"] == "sess-A" and row["output"]["text"] == answer
    assert [e["event_type"] for e in repo.list_events(todo_id=row["id"])] == ["task_started", "task_working", "tool_usage_started", "tool_usage_finished", "task_completed"]
    assert repo.list_events(todo_id=row["id"])[0]["crew_type"] == "result" and repo.list_events(todo_id=row["id"])[0]["data"]["goal"] == "원인 진단"
    request, env = reqs[0]
    assert request.permission is Permission.WORKSPACE_WRITE and request.resume_session is None and "--allowedTools" in request.extra_args and env is None
    assert "## 결과 제출 형식" in request.prompt and "`cause`: 원인 노드 id" in request.prompt and "- 에이전트: AI 에이전트" in request.prompt
    ws = Path(request.workdir)
    assert ws == tmp_path / "hyd" / row["id"] and (ws / ".mcp.json").exists() and (ws / "CLAUDE.md").exists() and (ws / "outputs" / "result.json").exists()
    trace = [json.loads(line) for p in ws.glob("*.events.jsonl") for line in p.read_text(encoding="utf-8").splitlines()]
    assert any(e["tool_input"] == {"query": "MATCH …"} for e in trace)
    assert trace[-1]["session_id"] == "sess-A"
    assert r.poll_once() == 0                                               # SUBMITTED belongs to the engine now


def test_runner_resumes_the_instance_session_for_the_next_task(tmp_path):
    repo, inst = _repo()
    reqs = []
    first = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    repo.update_workitem(first | {"output": {"text": "…", "cliagents_session_id": "sess-A"}, "draft_status": None})     # as if the previous run stored it
    r = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec('{"cause": "c", "failure_mode": "f", "guide_card": {"x": 1}}', requests=reqs), schema_prompt="# s", resolve_provider=lambda pid: object())
    assert r.poll_once() == 1 and reqs[0][0].resume_session == "sess-A"


def test_runner_contract_mismatch_marks_failed_with_an_error_event(tmp_path):
    repo, inst = _repo()
    r = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec("원인은 쿨러입니다 (JSON 없음)"), schema_prompt="# s", resolve_provider=lambda pid: object())
    r.poll_once()
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    assert row["status"] == "IN_PROGRESS" and row["draft_status"] == "FAILED" and row["consumer"] is None and row["output"] is None
    err = repo.list_events(todo_id=row["id"])[-1]
    assert err["event_type"] == "error" and err["job_id"] == "TASK_ERROR" and "RunFailed" in err["data"]["raw_error"] and "JSON 객체가 아닙니다" in err["data"]["raw_error"]
    assert repo.fetch_pending_task("cliagents", "x") == []                   # FAILED waits for a person


def test_runner_pauses_as_a_human_question_and_resumes_after_the_answer(tmp_path):
    repo, inst = _repo()
    reqs = []
    r = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec("", permission_refusal="Claude requested permissions to use Bash, but you haven't granted it yet.", requests=reqs),
               schema_prompt="# s", resolve_provider=lambda pid: object())
    r.poll_once()
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    assert row["status"] == "IN_PROGRESS" and row["draft_status"] == "HUMAN_ASKED" and row["consumer"] is None
    asked = [e for e in repo.list_events(todo_id=row["id"]) if e["event_type"] == "human_asked"]
    assert len(asked) == 1 and asked[0]["status"] == "ASKED" and "Bash" in asked[0]["data"]["text"] and asked[0]["job_id"].startswith("human_asked_")
    assert repo.notifications[0]["url"] == f"/todolist/{row['id']}" and repo.notifications[0]["user_id"] == "role:operator"
    assert hitl.recall(tmp_path / "hyd" / row["id"]).session_id == "sess-A"
    # the person answers (process /human-response): feedback + FB_REQUESTED → the worker resumes the same session
    repo.update_workitem(repo.get_workitem(row["id"]) | {"feedback": {"human_answer": "네, Bash 없이 MCP 로만 진행하세요", "job_id": asked[0]["job_id"]}, "draft_status": "FB_REQUESTED"})
    r2 = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec('{"cause": "c", "failure_mode": "f", "guide_card": {"x": 1}}', requests=reqs), schema_prompt="# s", resolve_provider=lambda pid: object())
    assert r2.poll_once() == 1
    assert reqs[1][0].resume_session == "sess-A" and reqs[1][0].prompt.startswith("담당자 응답: 네, Bash 없이")
    assert repo.get_workitem(row["id"])["status"] == "SUBMITTED" and hitl.recall(tmp_path / "hyd" / row["id"]) is None


def test_runner_stops_when_a_person_cancels_mid_run(tmp_path):
    repo, inst = _repo()
    first = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    cancel = lambda: repo.update_workitem(repo.get_workitem(first["id"]) | {"draft_status": "CANCELLED"})
    r = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec('{"cause": "c", "failure_mode": "f", "guide_card": {"x": 1}}', on_event=cancel), schema_prompt="# s", resolve_provider=lambda pid: object())
    r.poll_once()
    row = repo.get_workitem(first["id"])
    assert row["status"] == "IN_PROGRESS" and row["draft_status"] == "CANCELLED" and row["output"] is None
    assert repo.list_events(todo_id=row["id"])[-1]["event_type"] == "task_cancelled"


def test_runner_treats_cli_error_result_as_failure(tmp_path):
    repo, inst = _repo()
    r = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec("rate limited", is_error=True), schema_prompt="# s", resolve_provider=lambda pid: object())
    r.poll_once()
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    assert row["draft_status"] == "FAILED" and "rate limited" in repo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]


@pytest.mark.parametrize('operation',['save_task_result','update_task_error'])
def test_late_result_or_error_cannot_overwrite_cancellation(tmp_path,monkeypatch,operation):
    repo,inst=_repo()
    first=next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='task:diagnose')
    original=getattr(repo,operation)
    def race(wid,*args,**kwargs):
        repo.update_workitem(repo.get_workitem(wid)|{'status':'CANCELLED','draft_status':'CANCELLED'})
        return original(wid,*args,**kwargs)
    monkeypatch.setattr(repo,operation,race)
    r=Runner(_settings(tmp_path),repo,exec_fn=_fake_exec('{"cause":"c","failure_mode":"f","guide_card":{"observed":true}}',
             is_error=operation=='update_task_error'),schema_prompt='',resolve_provider=lambda _:object())
    r.poll_once()
    fresh=repo.get_workitem(first['id'])
    assert fresh['status']=='CANCELLED' and fresh['draft_status']=='CANCELLED'
    assert fresh.get('output') is None and fresh['consumer'] is None
    assert not any(e['event_type']=='task_completed' for e in repo.list_events(todo_id=first['id']))


def test_activity_capabilities_read_the_designers_agent_config():
    defn = json.loads(DEF_PATH.read_text(encoding="utf-8"))
    defn["activities"][0]["agentConfig"] = {"cli": "codex", "model": "o4-mini", "permission": "read_only"}
    caps = context.activity_capabilities(defn, "task:diagnose")
    assert caps["agent_config"] == {"cli": "codex", "model": "o4-mini", "permission": "read_only"} and context.activity_capabilities(defn, "nope") == {}


def test_bridge_rewrites_container_hosts_for_a_host_run(tmp_path):
    rw = bridge.parse_host_rewrite("neo4j:7687=127.0.0.1:7687, enterprise-mcp:8199=127.0.0.1:8199,bad")
    assert rw == {"neo4j:7687": "127.0.0.1:7687", "enterprise-mcp:8199": "127.0.0.1:8199"}
    bridge.install(tmp_path, TENANT_MCP, host_rewrite=rw)
    cfg = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert cfg["neo4j"]["env"]["NEO4J_URI"] == "bolt://127.0.0.1:7687" and cfg["enterprise"]["url"] == "http://127.0.0.1:8199/mcp"
    assert cfg["hyd-dmn"]["url"] == "http://dmn-mcp:8198/mcp"                     # not in the map → unchanged


def test_resolve_provider_hands_the_cli_its_full_path(monkeypatch):
    # Windows: Popen(["claude", ...]) fails with WinError 2 because the npm shim is claude.cmd; the resolved path must be used
    from worker import runner as runner_mod

    class Stub:
        executable = "claude"

        def resolve_executable(self, *, refresh=False):
            return "C:/Users/x/AppData/Roaming/npm/claude.cmd"

    monkeypatch.setattr(runner_mod.registry, "resolve", lambda pid, surface=None: Stub())
    assert runner_mod._resolve_provider("claude-code").executable.endswith("claude.cmd")

    class Missing(Stub):
        def resolve_executable(self, *, refresh=False):
            raise RuntimeError("not installed")

    monkeypatch.setattr(runner_mod.registry, "resolve", lambda pid, surface=None: Missing())
    assert runner_mod._resolve_provider("claude-code").executable == "claude"
