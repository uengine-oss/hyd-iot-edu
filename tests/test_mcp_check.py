"""U3 (A2 MCP 부분) — 도구 지도 · 도구 써 보기 · 호출 기록 (읽기 전용).

가짜 서버로: 도구 목록(이름 · 설명 · 입력 형식 · 읽기 전용 판정, stdio · streamable_http JSON/SSE · sse), 연결 실패 사유
(연결 거부 · 주소 없음 · 인증 · MCP 아님 · 시간 초과 · 프로세스 종료 · 명령 없음), 읽기 전용 도구 실제 호출 결과,
쓰기 · 표시 없음 도구 거부(서버에 닿지 않음), 결과 크기 제한, 비밀값 가림(설정 · 결과 · 호출 기록), 쓰기 API 없음."""
from __future__ import annotations

import json
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import mcp_api, mcp_calls, mcp_check, procdb
from procsvc.mcp_check import MASK

ROOT = Path(__file__).resolve().parents[1]
FAKE = str(ROOT / "tests" / "fixtures" / "mcp_fake_server.py")
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import mcp_fake_server  # noqa: E402
from mcp_fake_server import TOOLS, respond  # noqa: E402


# ---------------------------------------------------------------- 가짜 HTTP 서버들 (스레드)
class _Handler(BaseHTTPRequestHandler):
    mode = "json"                       # json | sse | auth | html | slow | sse-transport
    sessions: dict = {}
    stream_queues: dict = {}

    def log_message(self, *a):          # 조용히
        pass

    def _read(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")

    def do_DELETE(self):
        self.send_response(200); self.end_headers()

    def do_GET(self):
        if self.mode == "sse-transport" and self.path.startswith("/sse"):
            q = queue.Queue(); _Handler.stream_queues["s1"] = q
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            self.wfile.write(b"event: endpoint\ndata: /messages?session_id=s1\n\n"); self.wfile.flush()
            while True:
                msg = q.get()
                if msg is None:
                    return
                self.wfile.write(f"event: message\ndata: {json.dumps(msg)}\n\n".encode()); self.wfile.flush()
        self.send_response(404); self.end_headers()

    def do_POST(self):
        mode = self.mode
        if mode == "auth":
            self.send_response(401); self.end_headers(); return
        if mode == "html":
            body = b"<html><body>Not Found</body></html>"
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(body); return
        if mode == "slow":
            time.sleep(2.0)
        try:
            self._serve_mcp(mode)
        except (BrokenPipeError, ConnectionResetError):      # 느린 서버 시험: 클라이언트가 먼저 끊는다
            pass

    def _serve_mcp(self, mode):
        msg = self._read()
        if mode == "sse-transport":
            out = respond(msg)
            self.send_response(202); self.end_headers()
            if out is not None:
                _Handler.stream_queues["s1"].put(out)
            return
        if "Accept" not in self.headers or "text/event-stream" not in self.headers["Accept"]:
            self.send_response(406); self.end_headers(); return
        if msg.get("method") == "initialize":
            _Handler.sessions[self.server.server_port] = "sess-" + str(self.server.server_port)
        elif self.headers.get("Mcp-Session-Id") != _Handler.sessions.get(self.server.server_port):
            self.send_response(400); self.end_headers(); self.wfile.write(b"missing session"); return
        out = respond(msg)
        if out is None:
            self.send_response(202); self.end_headers(); return
        if mode == "sse":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
            self.send_header("Mcp-Session-Id", _Handler.sessions[self.server.server_port]); self.end_headers()
            self.wfile.write(b": keepalive\n\n" + f"event: message\ndata: {json.dumps(out)}\n\n".encode())
            return
        body = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", _Handler.sessions[self.server.server_port]); self.end_headers(); self.wfile.write(body)


def _serve(mode: str):
    handler = type("H", (_Handler,), {"mode": mode})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture
def http_server():
    servers = []

    def start(mode="json"):
        srv = _serve(mode); servers.append(srv)
        return f"http://127.0.0.1:{srv.server_port}/mcp"
    yield start
    for q in list(_Handler.stream_queues.values()):
        q.put(None)
    for srv in servers:
        srv.shutdown(); srv.server_close()


NAMES = [t["name"] for t in TOOLS]


# ---------------------------------------------------------------- 정상 서버 → 도구 목록 · 입력 형식 · 읽기 전용 판정
def test_stdio_fake_server_lists_tools_over_two_pages_with_schema_and_verdict():
    spec = mcp_check.normalize({"command": sys.executable, "args": [FAKE], "env": {"NEO4J_PASSWORD": "x"}})
    out = mcp_check.check(spec, timeout=10)
    assert out["status"] == "ok", out["error"]
    tools = {t["name"]: t for t in out["tools"]}
    assert list(tools) == NAMES                                                      # 두 페이지(nextCursor)를 다 읽었다
    assert tools["add"]["description"] == "두 수를 더한다" and tools["add"]["input_schema"]["required"] == ["a", "b"]
    assert tools["add"]["annotations"] == {"readOnlyHint": True, "destructiveHint": False}
    assert tools["add"]["callable"] is True and tools["add"]["refuse_reason"] is None
    assert tools["greet"]["callable"] is False and "readOnlyHint" in tools["greet"]["refuse_reason"]
    assert tools["submit_note"]["callable"] is False and "쓰기 도구" in tools["submit_note"]["refuse_reason"]
    assert tools["delete_rows"]["callable"] is False and "'delete'" in tools["delete_rows"]["refuse_reason"]
    assert out["server_info"] == {"name": "fake-mcp", "version": "0.1"} and out["protocol_version"] == mcp_check.PROTOCOL_VERSION
    assert out["error"] is None and out["elapsed_ms"] >= 0 and out["checked_at"].endswith("Z")


@pytest.mark.parametrize("mode", ["json", "sse"])
def test_streamable_http_lists_tools_and_echoes_the_session_id(http_server, mode):
    url = http_server(mode)
    out = mcp_check.check(mcp_check.normalize({"type": "url", "url": url, "transport": "streamable_http"}), timeout=5)
    assert out["status"] == "ok", out["error"]
    assert [t["name"] for t in out["tools"]] == NAMES


def test_legacy_sse_transport_lists_tools(http_server):
    url = http_server("sse-transport").replace("/mcp", "/sse")
    out = mcp_check.check(mcp_check.normalize({"url": url, "transport": "sse"}), timeout=5)
    assert out["status"] == "ok", out["error"]
    assert [t["name"] for t in out["tools"]] == NAMES


# ---------------------------------------------------------------- 잘못된 서버 → 사람이 읽는 사유 (폴백 · 빈 성공 없음)
def test_connection_refused_names_the_host_and_port():
    srv = _serve("json"); port = srv.server_port; srv.shutdown(); srv.server_close()
    out = mcp_check.check(mcp_check.normalize({"url": f"http://127.0.0.1:{port}/mcp"}), timeout=3)
    assert out["status"] == "failed" and out["error_kind"] == "refused" and out["tools"] == []
    assert out["error"].startswith("연결 거부") and f"127.0.0.1:{port}" in out["error"]


def test_unknown_host_is_reported_as_unreachable():
    out = mcp_check.check(mcp_check.normalize({"url": "http://no-such-mcp-host.invalid:8198/mcp"}), timeout=5)
    assert out["status"] == "failed" and out["error_kind"] == "unreachable"
    assert "no-such-mcp-host.invalid" in out["error"] and "주소를 찾을 수 없습니다" in out["error"]


def test_http_401_is_an_auth_failure(http_server):
    out = mcp_check.check(mcp_check.normalize({"url": http_server("auth")}), timeout=3)
    assert out["error_kind"] == "auth" and "인증 실패 (HTTP 401)" in out["error"]


def test_html_page_is_not_an_mcp_endpoint(http_server):
    out = mcp_check.check(mcp_check.normalize({"url": http_server("html")}), timeout=3)
    assert out["error_kind"] == "not_mcp" and "MCP 끝점이 아닙니다" in out["error"] and "text/html" in out["error"]


def test_slow_server_times_out_with_the_limit_in_the_message(http_server):
    out = mcp_check.check(mcp_check.normalize({"url": http_server("slow")}), timeout=0.5)
    assert out["error_kind"] == "timeout" and "0.5초" in out["error"] and "시간 초과" in out["error"]


def test_missing_command_says_it_is_not_in_the_process_container():
    out = mcp_check.check(mcp_check.normalize({"command": "uvx-not-installed-here", "args": ["x"]}), timeout=3)
    assert out["error_kind"] == "exec" and "'uvx-not-installed-here' 명령을 이 서비스(process 컨테이너)에서 찾을 수 없습니다" in out["error"]
    assert "워커" in out["error"]


def test_server_process_that_exits_reports_its_stderr():
    out = mcp_check.check(mcp_check.normalize({"command": sys.executable, "args": [FAKE, "--exit-early"]}), timeout=5)
    assert out["error_kind"] == "closed" and "종료 코드 3" in out["error"] and "NEO4J_URI" in out["error"]


def test_unsupported_transport_and_bad_url_are_config_errors():
    with pytest.raises(ValueError, match="transport: 'websocket'"):
        mcp_check.normalize({"transport": "websocket", "url": "ws://x"})
    with pytest.raises(ValueError, match="url: http://"):
        mcp_check.normalize({"url": "dmn-mcp:8198/mcp"})
    with pytest.raises(ValueError, match="command"):
        mcp_check.normalize({"transport": "stdio"})


def test_seed_shapes_normalize_to_the_three_transports():
    seed = json.loads((ROOT / "it" / "supabase" / "seed.sql").read_text(encoding="utf-8").split("'{\n  \"mcpServers\"")[1].split("}'::jsonb")[0].join(['{\n  "mcpServers"', "}"]))
    kinds = {name: mcp_check.normalize(spec)["transport"] for name, spec in seed["mcpServers"].items()}
    assert kinds == {"neo4j": "stdio", "enterprise": "streamable_http", "hyd-dmn": "streamable_http"}
    assert mcp_check.normalize({"type": "sse", "url": "http://x/sse"})["transport"] == "sse"
    assert mcp_check.normalize({"type": "http", "url": "http://x/mcp"})["transport"] == "streamable_http"


# ---------------------------------------------------------------- 도구 써 보기: 읽기 전용만 실제 호출
@pytest.fixture
def fake_stdio():
    return mcp_check.normalize({"command": sys.executable, "args": [FAKE]})


def test_read_only_tool_call_returns_the_real_result(http_server):
    spec = mcp_check.normalize({"url": http_server("json")})
    mcp_fake_server.CALLS.clear()
    out = mcp_check.call(spec, "add", {"a": 2, "b": 3.5}, timeout=5)
    assert out["status"] == "ok", out["error"]
    assert json.loads(out["result"]["text"]) == {"sum": 5.5} and out["result"]["is_error"] is False and out["result"]["truncated"] is False
    assert mcp_fake_server.CALLS == ["add"]
    bad = mcp_check.call(spec, "add", {"a": "x", "b": 1}, timeout=5)            # 도구가 오류를 돌려주면 숨기지 않는다
    assert bad["status"] == "ok" and bad["result"]["is_error"] is True and "숫자" in bad["result"]["text"]


@pytest.mark.parametrize("tool,phrase", [("submit_note", "쓰기 도구(readOnlyHint=false)"), ("greet", "읽기 전용(readOnlyHint)으로 표시하지 않았습니다"),
                                         ("delete_rows", "이름의 'delete'")])
def test_write_or_unmarked_tools_are_refused_before_reaching_the_server(http_server, tool, phrase):
    spec = mcp_check.normalize({"url": http_server("json")})
    mcp_fake_server.CALLS.clear()
    out = mcp_check.call(spec, tool, {}, timeout=5)
    assert out["status"] == "refused" and out["error_kind"] == "not_read_only" and phrase in out["error"] and out["result"] is None
    assert mcp_fake_server.CALLS == []                                              # 서버의 tools/call 에 닿지 않았다


def test_unknown_tool_and_bad_arguments_are_refused(fake_stdio):
    out = mcp_check.call(fake_stdio, "no_such", {}, timeout=10)
    assert out["status"] == "refused" and out["error_kind"] == "no_tool" and "'no_such'" in out["error"]
    out = mcp_check.call(fake_stdio, "add", ["not", "an", "object"], timeout=10)
    assert out["status"] == "refused" and out["error_kind"] == "input"


def test_large_results_are_cut_at_the_limit(fake_stdio):
    out = mcp_check.call(fake_stdio, "big_dump", {}, timeout=10, max_chars=1000)
    r = out["result"]
    assert out["status"] == "ok" and r["truncated"] is True and r["size_chars"] == 50_000 and r["limit_chars"] == 1000
    assert len(r["text"]) < 1100 and r["text"].endswith("(잘림)")


def test_call_result_masks_secrets_but_keeps_business_values(fake_stdio):
    out = mcp_check.call(fake_stdio, "lookup", {"asset": "HYD-01"}, timeout=10)
    doc = json.loads(out["result"]["text"])
    assert doc["dsn"] == MASK and doc["password"] == MASK and doc["key"] == "a" and doc["asset"] == "HYD-01"
    assert "s3cret" not in out["result"]["text"] and "pw@" not in doc["note"] and "abcdef123456" not in doc["note"]
    assert doc["note"] == f"접속 postgresql://u:{MASK}@h/x · Bearer {MASK}"


def test_read_only_verdict_rules():
    v = mcp_check.read_only_verdict
    assert v({"name": "describe_schema", "annotations": {"readOnlyHint": True}}) == (True, None)
    assert v({"name": "createOrder", "annotations": {"readOnlyHint": True}})[0] is False          # camelCase 도 쓰기 이름
    assert v({"name": "mes_orders", "annotations": {"readOnlyHint": True}})[0] is True            # 'orders' 는 조회
    assert "destructiveHint" in v({"name": "x", "annotations": {"destructiveHint": True}})[1]
    assert v({"name": "query", "annotations": {}})[0] is False                                     # 표시 없음 = 거부(기본 닫힘)


def test_repo_mcp_servers_mark_every_tool_and_only_submit_decision_writes():
    """dmn-mcp · enterprise-mcp 의 도구마다 ToolAnnotations 가 붙어 있다 — 표시를 빼면 이 시험이 잡는다."""
    import re
    marks = {}
    for path in ("it/dmn-mcp/dmn_mcp/server.py", "it/enterprise-mcp/enterprise_mcp/server.py"):
        src = (ROOT / path).read_text(encoding="utf-8")
        assert "@mcp.tool\n" not in src, f"{path}: 표시 없는 도구가 있습니다"
        marks.update(dict((name, mark) for mark, name in re.findall(r"@mcp\.tool\(annotations=(READ|WRITE)\)\ndef (\w+)", src)))
    # A11: dmn fabric_query (read) added → 15 + 10; C2: enterprise spare_stock · part_quotes · maintenance_windows (read) → 15 + 13
    assert len(marks) == 28 and [n for n, m in marks.items() if m == "WRITE"] == ["submit_decision"]
    for name, mark in marks.items():
        ok, _ = mcp_check.read_only_verdict({"name": name, "annotations": {"readOnlyHint": mark == "READ"}})
        assert ok is (mark == "READ"), name


def test_repo_mcp_server_annotations_only_use_module_level_names():
    """pydantic 은 도구 타입 힌트(from __future__ annotations 문자열)를 서버 모듈 전역에서 평가한다 —
    import 하지 않은 이름(A158: dmn-mcp CROSS_QUERIES)이 있으면 컨테이너가 시작하자마자 죽는다. 그 이름을 여기서 잡는다."""
    import ast, builtins
    for path in ("it/dmn-mcp/dmn_mcp/server.py", "it/enterprise-mcp/enterprise_mcp/server.py"):
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        bound = set(dir(builtins))
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                bound |= {(a.asname or a.name).split(".")[0] for a in node.names}
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    bound |= {n.id for n in ast.walk(t) if isinstance(n, ast.Name)}
        for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
            args = fn.args.args + fn.args.kwonlyargs
            for expr in [a.annotation for a in args if a.annotation] + ([fn.returns] if fn.returns else []):
                local = {n.id for c in ast.walk(expr) if isinstance(c, ast.comprehension)
                         for n in ast.walk(c.target) if isinstance(n, ast.Name)}
                missing = {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)} - bound - local
                assert not missing, f"{path}:{fn.lineno} {fn.name} 타입 힌트에 정의되지 않은 이름: {sorted(missing)}"


# ---------------------------------------------------------------- 비밀값 가림
def test_secrets_are_masked_in_config_views():
    spec = mcp_check.normalize({"command": "uvx", "args": ["mcp-neo4j-cypher"], "env": {"NEO4J_URI": "bolt://neo4j:7687", "NEO4J_PASSWORD": "hydpass123", "NEO4J_READ_ONLY": "true"}})
    shown = mcp_check.masked(spec)
    assert shown["env"] == {"NEO4J_URI": "bolt://neo4j:7687", "NEO4J_PASSWORD": MASK, "NEO4J_READ_ONLY": "true"}
    assert spec["env"]["NEO4J_PASSWORD"] == "hydpass123"                       # 원본은 그대로
    http = mcp_check.normalize({"url": "http://user:pw@host:1/mcp", "headers": {"Authorization": "Bearer t", "X-Trace": "1"}})
    shown = mcp_check.masked(http)
    assert shown["url"] == f"http://user:{MASK}@host:1/mcp" and shown["headers"] == {"Authorization": MASK, "X-Trace": "1"}
    nested = mcp_check.mask_value({"rows": [{"api_key": "sk-1", "primary_key": ["id"], "key": "b"}], "s": "password=abc host=db"})
    assert nested == {"rows": [{"api_key": MASK, "primary_key": ["id"], "key": "b"}], "s": f"password={MASK} host=db"}


# ---------------------------------------------------------------- API (MemoryRepo + TestClient)
DEF = json.loads((ROOT / "it" / "process" / "definitions" / "anomaly_response_v22.json").read_text(encoding="utf-8"))


@pytest.fixture
def client(http_server):
    url = http_server("json")
    repo = procdb.MemoryRepo()
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": {"mcpServers": {
        "fake": {"type": "url", "url": url, "transport": "streamable_http", "headers": {"Authorization": "Bearer secret-token"}},
        "neo4j": {"command": "uvx-not-here", "args": ["mcp-neo4j-cypher"], "env": {"NEO4J_PASSWORD": "hydpass123"}},   # 이 PC 에 uvx 가 있어도 '명령 없음' 경로
        "odd": {"transport": "websocket", "url": "ws://x"}}}})
    repo.upsert_user({"id": "sys:agent", "username": "AI 에이전트", "is_agent": True, "agent_type": "agent", "tools": "fake,neo4j", "tenant_id": "hyd"})
    repo.upsert_user({"id": "sys:scada", "username": "SCADA", "is_agent": True, "agent_type": "system", "tools": "fake", "tenant_id": "hyd"})
    repo.upsert_user({"id": "role:operator", "username": "운전원", "is_agent": False, "tools": "fake", "tenant_id": "hyd"})
    repo.upsert_proc_def(DEF)
    rt = SimpleNamespace(repo=repo, tenant_id="hyd")
    audits = []
    app = FastAPI()
    mcp_api.register(app, runtime_factory=lambda: rt, audit=lambda *a: audits.append(a))
    c = TestClient(app)
    c.repo, c.audits, c.url = repo, audits, url
    return c


def test_tool_map_lists_servers_masked_with_agents_and_tasks(client):
    r = client.get("/api/mcp/servers").json()
    assert r["source"] == "tenants.mcp" and [s["name"] for s in r["servers"]] == ["fake", "neo4j", "odd"]
    s = {x["name"]: x for x in r["servers"]}
    assert s["fake"]["headers"] == {"Authorization": MASK} and s["fake"]["url"] == client.url and s["fake"]["config_error"] is None
    assert s["neo4j"]["env"] == {"NEO4J_PASSWORD": MASK} and s["neo4j"]["command"] == "uvx-not-here"
    assert s["odd"]["config_error"].startswith("설정 오류 — transport")             # 손편집으로 깨진 칸도 줄로 남는다
    assert "secret-token" not in json.dumps(r) and "hydpass123" not in json.dumps(r)
    assert [a["id"] for a in s["fake"]["agents"]] == ["sys:agent"]                  # 시스템 · 사람은 에이전트가 아니다
    tasks = [t["activity_name"] for t in s["fake"]["tasks"]]
    assert tasks == ["원인 진단", "조치 후보 조회", "규정 검토", "우선순위 · 카드 작성"] and all(t["declared"] is False for t in s["fake"]["tasks"])
    assert s["odd"]["agents"] == []


def test_tool_list_endpoint_reports_status_and_reasons(client):
    ok = client.get("/api/mcp/servers/fake/tools?timeout=3").json()
    assert ok["status"] == "ok" and [t["name"] for t in ok["tools"]] == NAMES and ok["timeout_s"] == 3
    assert ok["tools"][0]["input_schema"]["properties"]["a"]["description"] == "첫 수"
    bad = client.get("/api/mcp/servers/neo4j/tools").json()
    assert bad["status"] == "failed" and bad["error_kind"] == "exec" and "'uvx-not-here'" in bad["error"] and bad["tools"] == []
    assert client.get("/api/mcp/servers/none/tools").status_code == 404
    assert client.get("/api/mcp/servers/odd/tools").status_code == 422
    assert client.get("/api/mcp/servers/fake/tools?timeout=99").status_code == 400


def test_try_endpoint_calls_read_only_and_refuses_writes(client):
    mcp_fake_server.CALLS.clear()
    r = client.post("/api/mcp/servers/fake/tools/lookup/call", json={"arguments": {"asset": "HYD-02", "limit": 1}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert json.loads(body["result"]["text"])["rows"] == [0] and body["arguments"] == {"asset": "HYD-02", "limit": 1}
    assert "s3cret" not in r.text and "hydpass123" not in r.text
    w = client.post("/api/mcp/servers/fake/tools/submit_note/call", json={"arguments": {"text": "x"}})
    assert w.status_code == 403 and "쓰기 도구" in w.json()["detail"]
    assert client.post("/api/mcp/servers/fake/tools/nope/call", json={}).status_code == 404
    assert client.post("/api/mcp/servers/fake/tools/add/call", json={"arguments": [1]}).status_code == 400
    down = client.post("/api/mcp/servers/neo4j/tools/read_neo4j_cypher/call", json={"arguments": {}})
    assert down.status_code == 502 and "uvx-not-here" in down.json()["detail"]
    assert mcp_fake_server.CALLS == ["lookup"]                                      # 쓰기 도구는 서버에 닿지 않았다
    assert [(a[2], a[3]["tool"], a[3]["status"]) for a in client.audits] == [
        ("MCP_TOOL_TRIED", "lookup", "ok"), ("MCP_TOOL_TRIED", "submit_note", "refused"), ("MCP_TOOL_TRIED", "nope", "refused"),
        ("MCP_TOOL_TRIED", "read_neo4j_cypher", "failed")]


def test_no_write_routes_exist(client):
    for method, path in [("post", "/api/mcp/servers"), ("put", "/api/mcp/servers/fake"), ("delete", "/api/mcp/servers/fake"),
                         ("post", "/api/mcp/servers/fake/check"), ("post", "/api/mcp/check")]:
        assert client.request(method.upper(), path, json={}).status_code in (404, 405), (method, path)
    assert set(client.repo.get_tenant("hyd")["mcp"]["mcpServers"]) == {"fake", "neo4j", "odd"}


def _event(i, kind, tool, todo, inst, data, ts):
    return {"id": f"e{i}", "job_id": "run-1", "todo_id": todo, "proc_inst_id": inst, "event_type": kind, "crew_type": "agent",
            "data": dict(data, tool=tool), "timestamp": ts}


def test_call_history_pairs_events_masks_secrets_and_links_to_the_task(client):
    repo = client.repo
    repo.instances["anomaly_response.i1"] = {"proc_inst_id": "anomaly_response.i1", "proc_inst_name": "HYD-01 쿨러 경보", "status": "RUNNING"}
    repo.workitems["w1"] = {"id": "w1", "proc_inst_id": "anomaly_response.i1", "activity_id": "task:diagnose", "activity_name": "원인 진단"}
    repo.record_events([
        _event(1, "tool_usage_started", "mcp__fake__lookup", "w1", "anomaly_response.i1", {"tool_use_id": "u1", "input": {"asset": "HYD-01", "password": "pw1"}}, "2026-10-08T01:00:00+00:00"),
        _event(2, "tool_usage_finished", "mcp__fake__lookup", "w1", "anomaly_response.i1",
               {"tool_use_id": "u1", "output": '{"dsn": "postgresql://r:s3cret@db/x", "rows": 3}', "is_error": False}, "2026-10-08T01:00:01.250000+00:00"),
        _event(3, "tool_usage_started", "fake/add", "w1", "anomaly_response.i1", {"tool_use_id": "u2", "input": {"a": 1, "b": 2}}, "2026-10-08T01:00:02+00:00"),
        _event(4, "tool_usage_started", "mcp__neo4j__read_neo4j_cypher", "w1", "anomaly_response.i1", {"tool_use_id": "u3", "input": "MATCH (n) RETURN n"}, "2026-10-08T01:00:03+00:00"),
        _event(5, "tool_usage_finished", "Read", "w1", "anomaly_response.i1", {"tool_use_id": "u4", "output": "file"}, "2026-10-08T01:00:04+00:00"),
    ])
    r = client.get("/api/mcp/calls?server=fake").json()
    calls = r["calls"]
    assert [(c["tool"], c["state"]) for c in calls] == [("add", "running"), ("lookup", "done")]          # 새것 먼저 · Codex 이름(fake/add)도 같은 서버
    lookup = calls[1]
    assert lookup["task_name"] == "원인 진단" and lookup["instance_name"] == "HYD-01 쿨러 경보" and lookup["duration_ms"] == 1250
    assert lookup["link"] == "#/instances/anomaly_response.i1/task/w1" and lookup["at"].startswith("2026-10-08T01:00:00")
    assert MASK in lookup["input_summary"] and "pw1" not in json.dumps(r) and "s3cret" not in json.dumps(r) and '"rows": 3' in lookup["output_summary"]
    assert [c["tool"] for c in client.get("/api/mcp/calls?server=fake&tool=lookup").json()["calls"]] == ["lookup"]
    assert [c["tool"] for c in client.get("/api/mcp/calls?server=neo4j").json()["calls"]] == ["read_neo4j_cypher"]
    assert {c["server"] for c in client.get("/api/mcp/calls").json()["calls"]} == {"fake", "neo4j"}       # MCP 아닌 도구(Read)는 빠진다
    assert client.get("/api/mcp/calls?limit=0").status_code == 400


def test_codex_style_server_names_match():
    assert mcp_calls.parse_tool("mcp__hyd-dmn__diagnose") == ("hyd-dmn", "diagnose")
    assert mcp_calls.parse_tool("hyd_dmn/diagnose") == ("hyd_dmn", "diagnose") and mcp_calls.same_server("hyd_dmn", "hyd-dmn")
    assert mcp_calls.parse_tool("Read") == (None, "Read") and not mcp_calls.same_server(None, "x")


def test_legacy_mode_answers_503():
    app = FastAPI()
    mcp_api.register(app, runtime_factory=lambda: None, audit=lambda *a: None)
    assert TestClient(app).get("/api/mcp/servers").status_code == 503


# ---------------------------------------------------------------- 포털 폼(입력 형식 → 칸 → 값) — node 가 있으면
def test_portal_form_builds_fields_and_rejects_bad_input():
    import shutil
    import subprocess
    node = shutil.which("node")
    if node is None:
        pytest.skip("node 없음")
    script = r"""
const vm = require('vm'); const fs = require('fs');
const ctx = { window: {} }; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const F = ctx.window.hydMcp.form;
const schema = { type: 'object', required: ['asset', 'n'], properties: {
  asset: { type: 'string', description: '설비 코드' }, n: { type: 'integer' }, x: { anyOf: [{ type: 'number' }, { type: 'null' }], default: null },
  kind: { enum: ['a', 'b'] }, on: { type: 'boolean' }, items: { type: 'array', items: { type: 'object' } } } };
const fields = F.fieldsOf(schema);
const good = F.argsFrom(fields, { asset: 'HYD-01', n: '3', x: '', kind: 'b', on: 'false', items: '[{"k":1}]' });
const bad = F.argsFrom(fields, { asset: '', n: '3.5', x: 'abc', items: '[oops' });
console.log(JSON.stringify({ types: fields.map(f => [f.key, f.type, f.required]), good, bad: bad.errors }));
"""
    out = subprocess.run([node, "-e", script, str(ROOT / "it" / "portal" / "www" / "mcp.js")], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["types"] == [["asset", "string", True], ["n", "integer", True], ["x", "number", False], ["kind", "enum", False],
                          ["on", "boolean", False], ["items", "json", False]]
    assert r["good"] == {"args": {"asset": "HYD-01", "n": 3, "kind": "b", "on": False, "items": [{"k": 1}]}, "errors": []}
    assert len(r["bad"]) == 4 and r["bad"][0] == "설비 코드: 필수 입력입니다" and "정수" in r["bad"][1] and "숫자" in r["bad"][2] and "JSON" in r["bad"][3]
