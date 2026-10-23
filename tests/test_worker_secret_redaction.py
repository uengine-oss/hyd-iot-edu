"""W2 (2026-10-23 검수): ${SECRET:KEY}로 채운 헤더 값과 stdio 서버 env 비밀은 실행 중 작업 폴더 .mcp.json에 평문으로 쓰인다
(에이전트는 Read로 그 파일을 읽을 수 있다). 그 값들이 가리기 목록에 들어가 trace · events 행 · 오류 문구에 남지 않는다."""
import json

from cliagents import ExecEvent, ExecEventKind, ExecRequest
from procsvc.procdb import MemoryRepo
from worker import bridge
from worker.runner import Runner, RunFailed
from worker.settings import Settings

TOKEN = "ghp_SECRETVALUE_1234567890abcdef"
PW = "neo4j-real-password"
APIKEY = "sk-literal-header-key-998877"


def _tenant():
    return {"mcpServers": {
        "gh": {"type": "url", "url": "https://example.test/mcp", "headers": {"Authorization": "Bearer ${SECRET:GH_TOKEN}"}},
        "lit": {"type": "url", "url": "https://example.test/lit", "headers": {"X-Api-Key": APIKEY, "Accept": "application/json"}},
        "neo4j": {"command": "uvx", "args": ["mcp-neo4j-cypher"],
                  "env": {"NEO4J_URI": "bolt://neo4j:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": PW, "NEO4J_AUTH_MODE": "none"}},
    }, bridge.SECRETS_KEY: {"GH_TOKEN": TOKEN}}


def test_secrets_written_to_the_workspace_config_are_redaction_values(tmp_path):
    res = bridge.install(tmp_path, _tenant())
    written = (tmp_path / ".mcp.json").read_text()
    assert TOKEN in written and PW in written and APIKEY in written      # still needed by the CLI during the run
    for secret in (TOKEN, "Bearer " + TOKEN, PW, APIKEY):
        assert secret in res.redaction_values
    # settings under ordinary names, and short values under secret-looking names, are not hidden (tool names stay readable)
    for plain in ("neo4j", "bolt://neo4j:7687", "none", "application/json"):
        assert plain not in res.redaction_values


def test_codex_config_secrets_are_redaction_values_too(tmp_path):
    res = bridge.install(tmp_path, _tenant(), provider_id="codex")
    assert TOKEN in (tmp_path / "codex-mcp.toml").read_text()
    assert TOKEN in res.redaction_values and PW in res.redaction_values


def _stream_reading_the_config(tmp_path, final):
    res = bridge.install(tmp_path, _tenant())
    config = (tmp_path / ".mcp.json").read_text()

    def fn(provider, request, env):
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="claude", session_id="s")
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="Read", tool_input={"file_path": ".mcp.json"}, tool_use_id="r1", session_id="s")
        yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="Read", text=config, tool_use_id="r1", session_id="s")
        yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT, text=f"토큰은 {TOKEN}, 비밀번호는 {PW}", session_id="s")
        yield ExecEvent(kind=ExecEventKind.RESULT, text=final, session_id="s", is_error=final.startswith("ERR"))
    repo = MemoryRepo()
    row = {"id": "w2", "proc_inst_id": "p-w2", "activity_id": "t", "status": "IN_PROGRESS", "draft_status": "STARTED",
           "consumer": "c", "tenant_id": "hyd", "start_date": "2026-10-04T00:00:00Z"}
    repo.insert_workitems([row])
    runner = Runner(Settings(consumer="c", workspace_root=tmp_path, cancel_check_every_s=0), repo, exec_fn=fn, schema_prompt="")
    trace = tmp_path / "job.events.jsonl"
    return runner, repo, row, trace, res


def test_an_agent_that_reads_the_config_leaves_no_secret_in_trace_or_events(tmp_path):
    runner, repo, row, trace, res = _stream_reading_the_config(tmp_path, "done")
    text, _, _ = runner._stream(row, "job", object(), ExecRequest(prompt="x", workdir=str(tmp_path)), None, "cliagents:claude-code",
                                trace_path=trace, redaction_values=res.redaction_values)
    stored = trace.read_text() + json.dumps(repo.list_events(todo_id="w2"), ensure_ascii=False) + text
    stored += json.dumps(list(repo.event_payloads.values()), ensure_ascii=False, default=str)
    for secret in (TOKEN, PW, APIKEY):
        assert secret not in stored
    assert "bolt://neo4j:7687" in stored                                      # ordinary settings stay readable


def test_a_cli_error_carrying_the_secret_is_redacted(tmp_path):
    runner, repo, row, trace, res = _stream_reading_the_config(tmp_path, f"ERR auth failed with Bearer {TOKEN} / {PW}")
    try:
        runner._stream(row, "job", object(), ExecRequest(prompt="x", workdir=str(tmp_path)), None, "cliagents:claude-code",
                       trace_path=trace, redaction_values=res.redaction_values)
    except RunFailed as e:
        assert TOKEN not in str(e) and PW not in str(e) and "auth failed" in str(e)
    else:
        raise AssertionError("error result must fail the run")
