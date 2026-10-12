import io
import json
import time
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from procsvc import mcp_registry, worker_credentials
from worker import bridge, runtime_credentials


KEY = "isolated-worker-key-" * 3
TOKEN = "isolated-oauth-access-token"


@pytest.fixture
def setup_runtime(monkeypatch, tmp_path):
    key = tmp_path / "worker.key"
    key.write_text(KEY, encoding="utf-8")
    monkeypatch.setenv("HYD_WORKER_RUNTIME_KEY_FILE", str(key))
    entry = {"url": "https://tools.example/mcp", "type": "url", "headers": {},
             "hyd": {"oauth_connection": "connection-one"}}
    entry["hyd"]["gate"] = {"fingerprint": bridge.config_fingerprint(entry),
                            "read_tools": ["list_items"], "blocked_tools": ["write_item"]}
    row = {"id": "todo-one", "tenant_id": "hyd", "consumer": "worker-one:claim-one",
           "status": "IN_PROGRESS", "draft_status": "STARTED", "lease_until": time.time() + 120}
    rt = SimpleNamespace(tenant_id="hyd", repo=SimpleNamespace(get_workitem=lambda wid: row if wid == row["id"] else None))
    monkeypatch.setattr(mcp_registry, "store_for", lambda repo: SimpleNamespace(servers=lambda tenant: {"personal": entry}))
    resolved_calls = []

    def resolve(repo, tenant, name, original):
        resolved_calls.append(deepcopy(original))
        return dict(original, headers={"Authorization": "Bearer " + TOKEN}), [TOKEN]

    monkeypatch.setattr(worker_credentials.mcp_secrets, "runtime_spec", resolve)
    body = {"tenant_id": "hyd", "todo_id": row["id"], "consumer": row["consumer"],
            "servers": {"personal": bridge.config_fingerprint(entry)}}
    return rt, row, entry, body, resolved_calls


@pytest.mark.parametrize("change,status", [("key", 403), ("tenant", 403), ("todo", 409),
    ("consumer", 409), ("pending", 409), ("closed", 409), ("draft", 409), ("fingerprint", 409)])
def test_resolver_denies_unowned_or_stale_requests(setup_runtime, change, status):
    rt, row, entry, body, calls = setup_runtime
    auth = "Bearer " + KEY
    if change == "key": auth = "Bearer wrong"
    elif change == "tenant": body["tenant_id"] = "other"
    elif change == "todo": body["todo_id"] = "not-found"
    elif change == "consumer": body["consumer"] = "other-worker"
    elif change == "pending": row["status"] = "PENDING"
    elif change == "closed": row["status"] = "COMPLETED"
    elif change == "draft": row["draft_status"] = None
    else: body["servers"]["personal"] = "old"
    with pytest.raises(HTTPException) as failure:
        worker_credentials.resolve(rt, body, auth)
    assert failure.value.status_code == status
    assert not calls
    assert TOKEN not in str(failure.value.detail)


def test_actual_resolver_to_codex_bridge_preserves_gate_and_cleanup(setup_runtime, monkeypatch, tmp_path):
    rt, row, entry, body, calls = setup_runtime
    original = deepcopy(entry)
    request_seen = []

    class Response(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *args): self.close()

    def request(req, timeout):
        assert timeout == 30
        request_seen.append(req)
        reply = worker_credentials.resolve(rt, json.loads(req.data), req.get_header("Authorization"))
        return Response(json.dumps(reply).encode())

    monkeypatch.setattr(runtime_credentials.urllib.request, "build_opener", lambda *args: SimpleNamespace(open=request))
    config = runtime_credentials.attach({"mcpServers": {"personal": entry}}, row, "hyd")
    assert TOKEN not in json.dumps(bridge.without_secrets(config))
    assert bridge.config_fingerprint(entry) == body["servers"]["personal"]
    gate = bridge.gate_servers(config, trusted=[])
    assert gate.read_tools == {"personal": ["list_items"]}
    assert gate.blocked_tools == {"personal": ["write_item"]}
    result = bridge.install(tmp_path, gate.config, provider_id="codex", read_tools=gate.read_tools)
    native = (tmp_path / "codex-mcp.toml").read_text(encoding="utf-8")
    assert TOKEN not in native and KEY not in native and '"enabled_tools"=["list_items"]' in native
    assert '"http_headers"' in native
    assert "HydRuntime " in native and "/internal/worker/mcp/personal" in native
    assert any(v.startswith("HydRuntime ") for v in result.redaction_values)
    assert TOKEN not in repr(result) and "HydRuntime " not in repr(result)
    bridge.cleanup(tmp_path)
    assert not (tmp_path / "codex-mcp.toml").exists()
    assert entry == original and calls == [original]
    assert request_seen[0].get_method() == "POST" and len(request_seen) == 1


def test_oauth_missing_credentials_fails_even_trusted_server(setup_runtime):
    _, _, entry, _, _ = setup_runtime
    with pytest.raises(RuntimeError, match="자격증명"):
        bridge.gate_servers({"mcpServers": {"personal": entry}}, trusted=["personal"])


def test_no_oauth_does_not_require_broker_or_key(monkeypatch):
    monkeypatch.setenv("HYD_WORKER_RUNTIME_KEY_FILE", "does-not-exist")
    config = {"mcpServers": {"legacy": {"url": "http://legacy/mcp"}}}
    assert runtime_credentials.attach(config, {}, "hyd") is config


def test_missing_key_and_external_plain_http_fail_closed(setup_runtime, monkeypatch):
    _, row, entry, _, _ = setup_runtime
    config = {"mcpServers": {"personal": entry}}
    monkeypatch.setenv("HYD_WORKER_RUNTIME_KEY_FILE", "does-not-exist")
    with pytest.raises(runtime_credentials.RuntimeConnectionError, match="인증 파일"):
        runtime_credentials.attach(config, row, "hyd")
    monkeypatch.setenv("PROCESS_URL", "http://external.example")
    with pytest.raises(runtime_credentials.RuntimeConnectionError, match="HTTPS"):
        runtime_credentials.attach(config, row, "hyd")


def test_runner_auth_failure_never_launches_cli_and_records_public_reason(tmp_path, monkeypatch):
    from test_worker import _repo, _settings
    from worker import context
    from worker.runner import Runner
    repo, inst = _repo()
    original_prepare = context.prepare
    def prepare(*args):
        ctx = original_prepare(*args)
        ctx.tenant_mcp = {"mcpServers": {"neo4j": {"url": "https://tools.example/mcp",
                         "hyd": {"oauth_connection": "connected"}}}}
        return ctx
    monkeypatch.setattr(context, "prepare", prepare)
    monkeypatch.setenv("HYD_WORKER_RUNTIME_KEY_FILE", str(tmp_path / "absent"))
    def cli(*args):
        pytest.fail("failed OAuth must not launch CLI")
    runner = Runner(_settings(tmp_path), repo, exec_fn=cli, resolve_provider=lambda pid: object())
    assert runner.poll_once() == 1
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    assert row["draft_status"] == "FAILED"
    events = repo.list_events(inst["proc_inst_id"])
    assert any("실행 연결 인증 파일" in json.dumps(e, ensure_ascii=False) for e in events)
    assert not any(e["event_type"] == "task_started" for e in events)


def test_stream_echo_is_redacted_before_trace_public_rows_and_final(tmp_path):
    from cliagents import ExecEvent, ExecEventKind, ExecRequest, Permission
    from test_worker import _repo, _settings
    from worker.runner import Runner
    repo, inst = _repo()
    row = repo.fetch_pending_task("cliagents", "owned-claim", tenant_id="hyd")[0]
    def cli(*args):
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__personal__list_items",
                        tool_input={"echo": TOKEN}, tool_use_id="one")
        yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="mcp__personal__list_items",
                        tool_output={"echo": TOKEN}, tool_use_id="one")
        yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT, text="확인 " + TOKEN)
        yield ExecEvent(kind=ExecEventKind.RESULT, text="완료 " + TOKEN)
    runner = Runner(_settings(tmp_path), repo, exec_fn=cli)
    trace = tmp_path / "trace.jsonl"
    request = ExecRequest(prompt="test", workdir=str(tmp_path), permission=Permission.READ_ONLY)
    final, _, _ = runner._stream(row, "run-isolated", object(), request, None, "cliagents:codex",
                                trace_path=trace, redaction_values=[TOKEN])
    stored = json.dumps(repo.list_events(inst["proc_inst_id"]), ensure_ascii=False)
    assert TOKEN not in final + stored + trace.read_text(encoding="utf-8")
    assert "[비밀 값 가림]" in final and "[비밀 값 가림]" in stored


@pytest.mark.parametrize("path", ["read", "approved_system"])
def test_system_and_read_hooks_pass_original_oauth_identity_before_normalizing(setup_runtime, monkeypatch, path):
    from procsvc import instance_mode, mcp_check
    rt, _, entry, _, calls = setup_runtime
    monkeypatch.setattr(instance_mode, "_runtime", rt)
    context = SimpleNamespace(book={}, incidents={}, exec_compensation=None, cypher=lambda *a, **k: [],
                              audit=lambda *a, **k: None, latest_tag=None)
    hooks = instance_mode._hooks(context)
    received = []
    def invoke(spec, *args, **kwargs):
        received.append(spec)
        return {"status": "ok", "echo": spec["headers"]["Authorization"]}
    monkeypatch.setattr(mcp_check, "call", invoke)
    monkeypatch.setattr(mcp_check, "call_effect", invoke)
    result = hooks.mcp_read("personal", "list_items", {}) if path == "read" else hooks.mcp_call("personal", "write_item", {}, "approved-idempotency-key")
    assert calls == [entry] and received[0]["headers"]["Authorization"] == "Bearer " + TOKEN
    assert "hyd" not in received[0] and TOKEN not in json.dumps(result)
    assert result["status"] == "ok"


def test_broker_redirect_does_not_forward_global_key(setup_runtime, monkeypatch):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    _, row, entry, _, _ = setup_runtime
    followed = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(307)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/unexpected")
            self.send_header("Content-Length", "0")
            self.end_headers()
            if self.path == "/unexpected": followed.append(self.headers.get("Authorization"))
        def do_GET(self):
            followed.append(self.headers.get("Authorization"))
            self.send_response(200); self.end_headers()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    monkeypatch.setenv("PROCESS_URL", f"http://127.0.0.1:{server.server_port}")
    try:
        with pytest.raises(runtime_credentials.RuntimeConnectionError, match="실행 인증"):
            runtime_credentials.attach({"mcpServers": {"personal": entry}}, row, "hyd")
        assert not followed
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


@pytest.mark.parametrize("controlled", [True, False])
def test_produced_connection_reason_is_visible_in_four_actual_public_consumers(tmp_path, controlled):
    import subprocess
    from pathlib import Path
    from test_worker import _repo, _settings
    from worker.runner import Runner, RunFailed
    repo, inst = _repo()
    row = repo.fetch_pending_task("cliagents", "owned-consumer", tenant_id="hyd")[0]
    reason = "로그인 연결이 만료되었거나 사용할 수 없습니다. 다시 연결을 확인하세요"
    error = runtime_credentials.RuntimeConnectionError(reason) if controlled else RunFailed("REMOTE_PRIVATE_BODY")
    Runner(_settings(tmp_path), repo)._fail(row, "isolated-job", error)
    event = next(e for e in repo.list_events(inst["proc_inst_id"]) if e["event_type"] == "error")
    expected = reason if controlled else "에이전트 실행이 실패했습니다. 담당자가 확인한 뒤 다시 보낼 수 있습니다."
    assert event["data"]["friendly"] == expected
    assert event["data"]["raw_error"].endswith(str(error))
    source = r"""
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const input=JSON.parse(fs.readFileSync(0,'utf8')),www=process.argv[1];
const ctx={console,document:{readyState:'loading',querySelectorAll:()=>[],querySelector:()=>null,getElementById:()=>null,addEventListener:()=>{}},location:{hash:''},setTimeout:()=>0,clearTimeout:()=>{},setInterval:()=>0,clearInterval:()=>{},localStorage:{getItem:()=>null},addEventListener:()=>{}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext('const esc=s=>String(s??"");',ctx);
for(const file of ['ui.js','plainWords.js','trace.js'])vm.runInContext(fs.readFileSync(path.join(www,file),'utf8'),ctx);
for(const [file,expose]of [['liveStream.js','window.connectionTestLive={describe};'],['taskDetail.js','window.connectionTestDetail={timelineItems};'],['caseRecord.js','window.connectionTestRecord={rowsOf};']]){
  const original=fs.readFileSync(path.join(www,file),'utf8');
  vm.runInContext(original.replace(/\}\)\(\);\s*$/,expose+'})();'),ctx);
}
const e=input.event,w={id:e.todo_id};
const results={liveStream:ctx.connectionTestLive.describe(e).text,trace:ctx.hydTrace.rowsOf([e],w)[0].text,taskDetail:ctx.connectionTestDetail.timelineItems(w,[e],{},false)[0].text,record:ctx.connectionTestRecord.rowsOf([e])[0].text};
for(const [name,text]of Object.entries(results))assert.equal(text,input.expected,name+' must display the actionable connection reason by default');
process.stdout.write(JSON.stringify(results));
"""
    www = Path(__file__).resolve().parents[1] / "it" / "portal" / "www"
    result = subprocess.run(["node", "-e", source, str(www)], input=json.dumps({"event": event, "expected": expected}),
                            capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)) == 4
