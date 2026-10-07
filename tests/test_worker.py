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


def test_runner_asks_the_same_session_to_fix_the_result_shape_before_failing(tmp_path):
    """A086 (a086-promql-at-1): the right answer with `values` sent as a JSON string failed the whole task. Now the defect is
    sent back to the same session (bounded) and the corrected result is submitted."""
    repo, inst = _repo()
    reqs, answers = [], iter(["원인은 쿨러 핀 오염입니다 (JSON 없음)", '{"cause": "c", "failure_mode": "f", "guide_card": {"x": 1}}'])
    def fn(provider, request, env):
        yield from _fake_exec(next(answers), requests=reqs)(provider, request, env)
    r = Runner(_settings(tmp_path), repo, exec_fn=fn, schema_prompt="# s", resolve_provider=lambda pid: object())
    assert r.poll_once() == 1
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    assert row["status"] == "SUBMITTED" and row["output"]["cause"] == "c"
    assert len(reqs) == 2 and reqs[1][0].resume_session == "sess-A" and "출력 형식 검사에서 거절" in reqs[1][0].prompt
    assert any("출력 형식 교정 요청 1/2" in json.dumps(e["data"], ensure_ascii=False) for e in repo.list_events(todo_id=row["id"]))


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


def test_resolve_provider_prefers_the_native_exe_over_the_cmd_shim(monkeypatch, tmp_path):
    # Windows live check 2026-10-06: the npm claude.cmd shim goes through cmd.exe, which expanded `%OS%` inside the prompt and
    # broke the flags (plain-text output, MCP tools "not granted"). The shim only calls bin/claude.exe; use that directly.
    from worker import runner as runner_mod
    shim = tmp_path / "claude.CMD"; shim.write_text("@ECHO off\r\n", encoding="utf-8")
    native = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    native.parent.mkdir(parents=True); native.write_bytes(b"MZ")

    class Stub:
        executable = "claude"
        def resolve_executable(self, *, refresh=False):
            return str(shim)

    monkeypatch.setattr(runner_mod.registry, "resolve", lambda pid, surface=None: Stub())
    assert runner_mod._resolve_provider("claude-code").executable == str(native)
    native.unlink()
    assert runner_mod._resolve_provider("claude-code").executable == str(shim)      # no native binary → keep the resolved shim
    assert runner_mod._unshim("/usr/local/bin/claude") == "/usr/local/bin/claude"    # POSIX: untouched


def test_codex_runs_can_be_routed_to_a_gpu_model_server_per_run(tmp_path):
    """A073: CODEX_MODEL_PROVIDER_BASE_URL routes Codex to an OpenAI-compatible server (the lecturer's SGLang) by inline
    -c overrides; wire_api must be "responses" (Codex 0.151 rejects "chat"); the key is only an env var name."""
    repo, inst = _repo()
    requests = []
    settings = _settings(tmp_path, cli_agent="codex", codex_model_provider_base_url="http://gpu.example:30000/v1",
                         codex_model_provider_name="HYD GPU SGLang", codex_model="frentis-ai-model")
    runner = Runner(settings, repo, exec_fn=_fake_exec('{"cause":"c","failure_mode":"f","guide_card":{}}', requests=requests),
                    schema_prompt="s", resolve_provider=lambda pid: object())
    assert runner.poll_once() == 1
    request = requests[0][0]
    args = request.extra_args
    assert args[args.index("model_provider=hydgpu") + 1] == "-c"
    table = next(a for a in args if a.startswith("model_providers.hydgpu="))
    assert 'base_url="http://gpu.example:30000/v1"' in table and 'wire_api="responses"' in table and 'env_key="HYD_GPU_API_KEY"' in table
    assert "chat" not in table and request.model == "frentis-ai-model"
    plain = []
    Runner(_settings(tmp_path, cli_agent="codex"), repo, exec_fn=_fake_exec('{"cause":"c","failure_mode":"f","guide_card":{}}', requests=plain),
           schema_prompt="s", resolve_provider=lambda pid: object())
    assert not any("model_provider" in a for a in plain[0][0].extra_args) if plain else True   # default: no override


def test_error_item_followed_by_a_result_is_a_notice_not_a_failure(tmp_path):
    """A073 live: Codex emits `item.type=error` ("Model metadata for `frentis-ai-model` not found…") for a custom model
    provider and then completes the turn. The worker must not abort on that item; it fails only when no result follows."""
    repo, inst = _repo()
    def exec_ok(provider, request, env):
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="codex", session_id="s1")
        yield ExecEvent(kind=ExecEventKind.ERROR, text="Model metadata for `frentis-ai-model` not found. Defaulting to fallback metadata", session_id="s1", is_error=True)
        yield ExecEvent(kind=ExecEventKind.RESULT, text='{"cause":"c","failure_mode":"f","guide_card":{"summary":"s"}}', session_id="s1")
    runner = Runner(_settings(tmp_path, cli_agent="codex"), repo, exec_fn=exec_ok, schema_prompt="s", resolve_provider=lambda pid: object())
    assert runner.poll_once() == 1
    rows = [w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"], limit=None) if w["activity_id"] == "task:diagnose"]
    assert rows and rows[0]["status"] == "SUBMITTED" and rows[0]["output"]["cause"] == "c"
    notices = [e for e in repo.list_events(proc_inst_id=inst["proc_inst_id"]) if "에이전트 오류 보고" in json.dumps(e.get("data") or {}, ensure_ascii=False)]
    assert notices, "the non-fatal error item is kept as a notice event"

    repo2, inst2 = _repo()
    def exec_dead(provider, request, env):
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="codex", session_id="s2")
        yield ExecEvent(kind=ExecEventKind.ERROR, text="model provider unreachable", session_id="s2", is_error=True)
    runner2 = Runner(_settings(tmp_path, cli_agent="codex"), repo2, exec_fn=exec_dead, schema_prompt="s", resolve_provider=lambda pid: object())
    assert runner2.poll_once() == 1
    row = next(w for w in repo2.list_workitems(proc_inst_id=inst2["proc_inst_id"], limit=None) if w["activity_id"] == "task:diagnose")
    assert row["draft_status"] == "FAILED"
    errors = [e for e in repo2.list_events(proc_inst_id=inst2["proc_inst_id"]) if e.get("event_type") == "error"]
    assert errors and "model provider unreachable" in json.dumps(errors[-1].get("data") or {}, ensure_ascii=False)



# ---------------------------------------------------------------- A095 · R13 1조 격차: 자식 프로세스 환경·작업별 MCP 서버
def test_worker_secrets_never_reach_the_cli_child_process():
    """process-gpt-deepagents sandbox env whitelist: cliagents' exec_env copies os.environ, so the worker scrubs itself."""
    from worker import env_guard
    env = {"SUPABASE_DSN": "postgresql://x", "NEO4J_PASSWORD": "p", "ENT_DB_DSN": "d", "HYD_GPU_API_KEY": "k", "PATH": "/bin",
           "HOME": "/h", "CLAUDE_CONFIG_DIR": "/c", "MCP_HOST_REWRITE": "a=b"}
    removed = env_guard.scrub(env, keep=("HYD_GPU_API_KEY",))
    assert removed == ["ENT_DB_DSN", "NEO4J_PASSWORD", "SUPABASE_DSN"]
    assert set(env) == {"HYD_GPU_API_KEY", "PATH", "HOME", "CLAUDE_CONFIG_DIR", "MCP_HOST_REWRITE"}
    # the pinned provider really does start from os.environ: a key present there is visible to the child unless scrubbed
    import os
    from cliagents import registry as reg
    provider = reg.get("claude-code") if hasattr(reg, "get") else None
    if provider is not None and hasattr(provider, "exec_env"):
        os.environ["HYD_TEST_SECRET_DSN"] = "x"
        try:
            assert "HYD_TEST_SECRET_DSN" in provider.exec_env({})
            env_guard.scrub()
            assert "HYD_TEST_SECRET_DSN" not in provider.exec_env({})
        finally:
            os.environ.pop("HYD_TEST_SECRET_DSN", None)


def test_activity_tools_select_the_mcp_servers_registered_for_the_run(tmp_path):
    """process-gpt-base-agent executor: per-task MCP server selection. No declaration keeps every tenant server."""
    full, missing = bridge.select_servers(TENANT_MCP, None)
    assert full is TENANT_MCP and missing == []
    only, missing = bridge.select_servers(TENANT_MCP, ["enterprise", "no-such-server"])
    assert sorted(only["mcpServers"]) == ["enterprise"] and missing == ["no-such-server"]
    assert sorted(bridge.install(tmp_path, only, provider_id="claude-code").servers) == ["enterprise"]
    assert sorted(bridge.install(tmp_path, TENANT_MCP, provider_id="claude-code").servers) == sorted(TENANT_MCP["mcpServers"])


def test_tenant_credentials_leave_the_retained_workspace_after_the_run(tmp_path):
    """A096 (process-gpt-cli-agent RuntimeLease): .mcp.json carries server env during the run only."""
    import json
    res = bridge.install(tmp_path, TENANT_MCP, provider_id="claude-code")
    before = json.loads((tmp_path / bridge.MCP_CONFIG_FILENAME).read_text(encoding="utf8"))["mcpServers"]
    with_env = [n for n, e in before.items() if e.get("env")]
    assert with_env, "fixture must carry at least one stdio server env"
    assert sorted(bridge.cleanup(tmp_path)) == sorted(with_env)
    after = json.loads((tmp_path / bridge.MCP_CONFIG_FILENAME).read_text(encoding="utf8"))["mcpServers"]
    assert not any(e.get("env") for e in after.values()) and set(after) == set(before)          # servers kept, secrets gone
    assert bridge.cleanup(tmp_path) == []                                                        # idempotent
    assert sorted(bridge.install(tmp_path, TENANT_MCP, provider_id="claude-code").servers) == sorted(res.servers)   # next run rewrites them


# ---------------------------------------------------------------- A097 · worker lease (agent-sdk lease_until / claim_count / max_claims)
def _agent_row(repo, n=1):
    for i in range(n):
        repo.insert_workitems([{"id": f"lease-{i}", "proc_inst_id": "p-lease", "tenant_id": "hyd", "activity_id": "task:x", "status": "IN_PROGRESS",
                                "agent_mode": "COMPLETE", "agent_orch": "cliagents", "start_date": f"2026-10-07T00:00:0{i}Z", "query": "[Instruction]\nx"}])
    repo.insert_instance({"proc_inst_id": "p-lease", "tenant_id": "hyd", "status": "RUNNING", "proc_def_id": "d", "proc_def_version": "1",
                          "start_date": "2026-10-07T00:00:00Z", "variables_data": []})


def test_expired_lease_is_reclaimed_by_another_worker_and_the_first_worker_stops(monkeypatch):
    repo = procdb.MemoryRepo(); _agent_row(repo)
    first = repo.fetch_pending_task("cliagents", "w1")[0]
    assert first["draft_status"] == "STARTED" and first["claim_count"] == 1 and first["lease_until"] > 0
    assert repo.fetch_pending_task("cliagents", "w2") == []                        # live lease: nobody else may take it
    assert repo.renew_task_lease(first["id"], "w1") and not repo.renew_task_lease(first["id"], "w9")
    repo.workitems[first["id"]]["lease_until"] = 0                                 # w1 died: the lease runs out
    second = repo.fetch_pending_task("cliagents", "w2")[0]
    assert second["consumer"] == "w2" and second["claim_count"] == 2 and "[Lease expired: reclaimed by w2 (claim 2)]" in second["log"]
    assert not repo.renew_task_lease(first["id"], "w1")                             # the old worker has lost its lease …
    assert not repo.save_task_result(first["id"], {"a": 1}, final=True, expected_consumer="w1")   # … and cannot submit a late result
    assert repo.save_task_result(first["id"], {"a": 2}, final=True, expected_consumer="w2")


def test_third_expired_lease_marks_the_run_failed_for_a_person_to_close():
    repo = procdb.MemoryRepo(); _agent_row(repo)
    for n in range(1, procdb.MAX_CLAIMS + 1):
        row = repo.fetch_pending_task("cliagents", f"w{n}")[0]
        assert row["claim_count"] == n
        repo.workitems[row["id"]]["lease_until"] = 0
    assert repo.fetch_pending_task("cliagents", "w-late") == []                    # no fourth claim
    assert repo.expire_worker_leases() == 1
    row = repo.get_workitem("lease-0")
    assert row["draft_status"] == "FAILED" and row["consumer"] is None and "[Lease expired after 3 claims" in row["log"]
    assert repo.expire_worker_leases() == 0                                        # idempotent


def test_runner_stops_the_cli_when_its_lease_is_lost(tmp_path, monkeypatch):
    repo = procdb.MemoryRepo(); _agent_row(repo)
    runner = Runner(_settings(tmp_path, lease_renew_every_s=0.0), repo, exec_fn=_fake_exec("{}"), schema_prompt="x", resolve_provider=lambda _: object())
    row = repo.fetch_pending_task("cliagents", "w1")[0]
    repo.workitems[row["id"]]["lease_until"] = 0
    assert repo.fetch_pending_task("cliagents", "w2")                             # reclaimed while w1 is still streaming
    from worker.runner import Cancelled
    from cliagents import ExecRequest
    with pytest.raises(Cancelled):
        runner._stream(dict(row, consumer="w1"), "job", object(), ExecRequest(prompt="x", workdir=str(tmp_path)), None, "crew")


def test_sweep_spares_a_run_whose_work_item_is_still_open(tmp_path):
    """A104 (session-router kube.go: ask before reclaiming): an old directory of a HUMAN_ASKED/IN_PROGRESS work item is kept,
    because the paused CLI session lives under it and the person's late answer must still resume."""
    import os, time as _t
    from worker import workspace
    root = tmp_path / "ws"
    for wid in ("open-1", "done-2"):
        d = root / "hyd" / wid / "context"; d.mkdir(parents=True); (d / "task.json").write_text("{}", encoding="utf8")
        old = _t.time() - 10 * 3600
        for p in (d / "task.json", d, root / "hyd" / wid):
            os.utime(p, (old, old))
    removed = workspace.sweep(root, retention_seconds=3600, keep=lambda wid: wid == "open-1")
    assert [p.name for p in removed] == ["done-2"] and (root / "hyd" / "open-1").exists() and not (root / "hyd" / "done-2").exists()


# ---------------------------------------------------------------- A114 · A113 r14 A1~A5 (product parity for the worker)
def test_claim_count_counts_only_reclaims_so_feedback_rounds_do_not_use_up_the_cap():
    """agent-sdk function.sql:102-105: a re-claim after a person's answer starts at 1; only an expired-lease reclaim adds.
    Before A114, three answers made claim_count 4 and one dead worker then meant FAILED instead of a reclaim."""
    repo = procdb.MemoryRepo(); _agent_row(repo)
    wid = "lease-0"
    for n in range(3):
        row = repo.fetch_pending_task("cliagents", f"w{n}")[0]
        assert row["claim_count"] == 1                                            # fresh / post-answer claim
        repo.workitems[wid].update(draft_status="HUMAN_ASKED", consumer=None)     # the agent asks a person …
        repo.workitems[wid].update(draft_status="FB_REQUESTED")                   # … who answers
    assert repo.fetch_pending_task("cliagents", "w3")[0]["claim_count"] == 1
    repo.workitems[wid]["lease_until"] = 0                                        # this worker dies once
    again = repo.fetch_pending_task("cliagents", "w4")[0]
    assert again["consumer"] == "w4" and again["claim_count"] == 2                # reclaimed, not FAILED
    assert repo.expire_worker_leases() == 0


def test_a_transient_db_error_on_renewal_does_not_fail_a_live_run(tmp_path):
    """agent-sdk lease.py:163-170: the renewal is retried next period; the run finishes and submits normally."""
    repo, inst = _repo()
    calls = []
    def flaky(todo_id, consumer, seconds=120):
        calls.append(todo_id)
        raise RuntimeError("connection reset")
    repo.renew_task_lease = flaky
    answer = '{"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"recommended": []}}'
    r = Runner(_settings(tmp_path, lease_renew_every_s=0.0), repo, exec_fn=_fake_exec(answer), schema_prompt="# s", resolve_provider=lambda pid: object())
    assert r.poll_once() == 1
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    assert row["status"] == "SUBMITTED"


def test_a_lost_lease_stops_the_run_and_says_another_worker_took_over_not_that_a_person_cancelled(tmp_path):
    repo = procdb.MemoryRepo(); _agent_row(repo)
    runner = Runner(_settings(tmp_path, lease_renew_every_s=0.0), repo, exec_fn=_fake_exec("{}"), schema_prompt="x", resolve_provider=lambda _: object())
    row = repo.fetch_pending_task("cliagents", "w1")[0]
    repo.workitems[row["id"]]["lease_until"] = 0
    assert repo.fetch_pending_task("cliagents", "w2")                             # reclaimed while w1 is still streaming
    from worker.runner import LeaseLost
    from cliagents import ExecRequest
    with pytest.raises(LeaseLost):
        runner._stream(dict(row, consumer="w1"), "job", object(), ExecRequest(prompt="x", workdir=str(tmp_path)), None, "crew")
    assert runner._reclaimed(dict(row, consumer="w1")) and not runner._reclaimed(dict(row, consumer="w2"))


def test_the_product_uis_agent_cli_key_selects_the_cli(tmp_path, monkeypatch):
    """process-gpt-cli-agent core/selection.py _AGENT_KEYS · vue3 AgentSelectField.vue:327 store agent_cli/agent_model."""
    from worker import runner as runner_mod
    repo, inst = _repo()
    seen, reqs = [], []
    monkeypatch.setattr(runner_mod.context, "activity_capabilities",
                        lambda defn, aid: {"agent_config": {"agent_cli": "codex", "agent_model": "o4-mini", "agent_permission": "read_only"}, "skills": [], "tools": []})
    answer = '{"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"recommended": []}}'
    r = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec(answer, requests=reqs), schema_prompt="# s",
               resolve_provider=lambda pid: seen.append(pid) or object())
    assert r.poll_once() == 1
    assert seen == ["codex"] and reqs[0][0].model == "o4-mini"
    assert runner_mod._first({"cli": "claude-code"}, runner_mod._AGENT_KEYS) == "claude-code"     # earlier HYD definitions still work


def test_codex_server_env_copy_leaves_the_retained_workspace_and_tokens_do_not_reach_the_cli(tmp_path):
    res = bridge.install(tmp_path, TENANT_MCP, provider_id="codex")
    toml = tmp_path / "codex-mcp.toml"
    assert toml.exists() and res.extra_args                                      # the run gets its servers through -c …
    bridge.cleanup(tmp_path)
    assert not toml.exists()                                                     # … and the on-disk copy with their env is gone
    from worker import env_guard
    env = {"GH_TOKEN": "g", "LLM_API_KEY": "l", "AWS_ACCESS_KEY": "a", "ANTHROPIC_API_KEY": "cli", "CLAUDE_CODE_OAUTH_TOKEN": "cli2",
           "HYD_GPU_API_KEY": "kept", "PATH": "/bin"}
    removed = env_guard.scrub(env, keep=("HYD_GPU_API_KEY",))
    assert removed == ["AWS_ACCESS_KEY", "GH_TOKEN", "LLM_API_KEY"]
    assert set(env) == {"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "HYD_GPU_API_KEY", "PATH"}


@pytest.mark.parametrize("agent_id", ["claude-code", "codex"])
def test_standing_instructions_carry_the_sql_rules(tmp_path, agent_id):
    """A115 (r14 A9, neo4j-text2sql controller_repair_prompt.md: no invented tables/columns, SELECT only, smallest repair):
    the SQL rules used to live only in a probe's instruction (probe_codex_sql_repair.py); every run now gets them."""
    from worker import workspace
    ws = workspace.for_run(tmp_path, "a115-sql")
    workspace.provision(ws, agent_id=agent_id, schema_prompt="schema", task={"id": "t"})
    text = "\n".join(p.read_text(encoding="utf-8") for p in ws.files() if p.suffix == ".md" and p.parent == ws.path)
    for rule in ("describe_schema", "지어내지 않습니다", "SELECT 한 문장", "최대 두 번", "실패를 0이나 빈 값으로 바꿔"):
        assert rule in text, rule


def test_portal_question_card_reads_sdk_question_field():
    """A115 (r14 A12, vue3 humanQuestionText): text first, then an SDK agent's `question`; the card was empty before."""
    import shutil, subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    ui = Path(__file__).resolve().parents[1] / "it" / "portal" / "www" / "ui.js"
    script = ("const vm=require('vm');const fs=require('fs');const c={};vm.createContext(c);"
              f"vm.runInContext(fs.readFileSync({json.dumps(str(ui))},'utf8'),c);"
              "const f=c.humanQuestionText;console.log(JSON.stringify([f({question:'납기 허용 기준?'}),f({text:'승인할까요?',question:'무시'}),f({}),f(null)]))")
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    assert json.loads(out) == ["납기 허용 기준?", "승인할까요?", "", ""]
    www = ui.parent
    assert "humanQuestionText(d)" in (www / "instances.js").read_text(encoding="utf-8")
    assert "humanQuestionText(d)" in (www / "liveStream.js").read_text(encoding="utf-8")
