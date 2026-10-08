"""B2 (확정 TODO B, DECISIONS 110 ①) — MCP 서버 등록 · 고치기 · 지우기 + 연결 검사 게이트 + 되돌리기 + 워커 실행 제한.

완료 기준(TODO B2): 잘못된 서버는 사유와 함께 거절, 정상 서버는 도구 목록, 쓰기 도구는 선택 불가.
더해서: 기준 서버 수정 · 삭제 거절, 새 서버 등록이 기본 에이전트 실행 설정을 바꾸지 않음, 워커가 실제 실행에서
검사 통과 서버의 읽기 표시 도구만 허용, 되돌리기는 학생 서버와 검사 기록만 지움.
가짜 서버는 U3 시험의 것(tests/fixtures/mcp_fake_server.py: 읽기 add · lookup · big_dump / 표시 없음 greet / 쓰기 submit_note /
이름이 쓰기 delete_rows)을 그대로 쓴다.
"""
from __future__ import annotations

import json
import re
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import mcp_api, mcp_check, mcp_registry, procdb
from procsvc.agents_store import agent_settings
from procsvc.mcp_check import MASK
from worker import bridge
from worker.settings import DEFAULT_ALLOWED_TOOLS, Settings

ROOT = Path(__file__).resolve().parents[1]
FAKE = str(ROOT / "tests" / "fixtures" / "mcp_fake_server.py")
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import mcp_fake_server  # noqa: E402
from test_mcp_check import _Handler, _serve  # noqa: E402  — U3 의 가짜 HTTP 서버(스레드)

SEED_MCP = {"mcpServers": {
    "neo4j": {"command": "uvx", "args": ["--with", "fastmcp==2.13.0.2", "mcp-neo4j-cypher@0.4.1", "--transport", "stdio"],
              "env": {"NEO4J_URI": "bolt://neo4j:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "hydpass123", "NEO4J_READ_ONLY": "true"}},
    "enterprise": {"type": "url", "url": "http://enterprise-mcp:8199/mcp", "transport": "streamable_http"},
    "hyd-dmn": {"type": "url", "url": "http://dmn-mcp:8198/mcp", "transport": "streamable_http"}}}
READ = ["add", "lookup", "big_dump"]
BLOCKED = ["greet", "submit_note", "delete_rows"]
STDIO = {"name": "my-fake", "transport": "stdio", "command": sys.executable, "args": [FAKE], "env": {"FAKE_TOKEN": "tok-123456"}}


def _closed_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    return port


@pytest.fixture
def http_url():
    servers = []

    def start(mode="json"):
        srv = _serve(mode); servers.append(srv)
        return f"http://127.0.0.1:{srv.server_port}/mcp"
    yield start
    for q in list(_Handler.stream_queues.values()):
        q.put(None)
    for srv in servers:
        srv.shutdown(); srv.server_close()


@pytest.fixture
def api():
    repo = procdb.MemoryRepo()
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": json.loads(json.dumps(SEED_MCP))})
    repo.upsert_user({"id": "sys:agent", "username": "AI 에이전트 (Claude Code)", "role": "agent", "is_agent": True, "agent_type": "agent",
                      "goal": "경보의 원인을 진단하고 조치 카드를 올린다", "tools": "neo4j,enterprise,hyd-dmn", "tenant_id": "hyd"})
    rt = SimpleNamespace(repo=repo, tenant_id="hyd")
    audits = []
    app = FastAPI()
    mcp_api.register(app, runtime_factory=lambda: rt, audit=lambda *a: audits.append(a))
    mcp_registry.mount(app, runtime_factory=lambda: rt, audit=lambda *a: audits.append(a))
    c = TestClient(app)
    c.repo, c.audits = repo, audits
    return c


def servers(c) -> dict:
    return c.repo.get_tenant("hyd")["mcp"]["mcpServers"]


def detail(r) -> str:
    d = r.json()["detail"]
    return d["reason"] if isinstance(d, dict) else d


# ---------------------------------------------------------------- 기준 = 시드 = 워커 기본 허용 목록 (세 곳이 같은 세 서버)
def test_base_servers_are_the_seed_servers_and_the_workers_trusted_servers():
    seed = (ROOT / "it" / "supabase" / "seed.sql").read_text(encoding="utf-8")
    block = seed[seed.index('"mcpServers"'):seed.index("}'::jsonb")]
    seeded = re.findall(r'^ {4}"([a-z0-9-]+)":\s*\{', block, re.M)
    assert seeded == list(mcp_registry.BASE_SERVERS)
    trusted = {a.split("__")[1] for a in DEFAULT_ALLOWED_TOOLS.split(",") if a.startswith("mcp__")}
    assert trusted == set(mcp_registry.BASE_SERVERS)


def test_portal_and_worker_compute_the_same_fingerprint():
    for entry in list(SEED_MCP["mcpServers"].values()) + [{"type": "url", "url": "http://x/mcp", "headers": {"A": "한글"}, "hyd": {"gate": {}}}]:
        assert mcp_registry.fingerprint(entry) == bridge.config_fingerprint(entry)
    e = {"command": "npx", "args": ["a"]}
    assert mcp_registry.fingerprint(e) == mcp_registry.fingerprint(dict(e, hyd={"origin": "user"}))    # 표시는 해시에 안 들어간다
    assert mcp_registry.fingerprint(e) != mcp_registry.fingerprint({"command": "npx", "args": ["b"]})


# ---------------------------------------------------------------- 정상 서버 → 도구 목록 · 게이트 · 저장
def test_register_a_working_stdio_server_stores_it_with_its_tools_and_gate(api):
    r = api.post("/api/mcp/servers", json=STDIO)
    assert r.status_code == 201, r.text
    body = r.json()
    assert [t["name"] for t in body["check"]["tools"]] == READ + BLOCKED and body["check"]["status"] == "ok"
    assert body["gate"]["read_tools"] == READ and body["gate"]["blocked_tools"] == BLOCKED
    entry = servers(api)["my-fake"]
    assert entry["command"] == sys.executable and entry["env"] == {"FAKE_TOKEN": "tok-123456"}            # 저장은 원래 값
    assert entry["hyd"]["origin"] == "user" and entry["hyd"]["gate"]["fingerprint"] == mcp_registry.fingerprint(entry)
    assert "tok-123456" not in r.text
    listed = {s["name"]: s for s in api.get("/api/mcp/servers").json()["servers"]}
    assert listed["my-fake"]["env"] == {"FAKE_TOKEN": MASK} and listed["my-fake"]["origin"] == "user" and listed["my-fake"]["editable"]
    assert listed["my-fake"]["check"]["status"] == "ok" and listed["my-fake"]["selectable"] is True
    assert listed["neo4j"]["origin"] == "seed" and listed["neo4j"]["editable"] is False and listed["neo4j"]["check"]["status"] == "never"
    assert "tok-123456" not in api.get("/api/mcp/servers").text and "hydpass123" not in api.get("/api/mcp/servers").text
    assert [a[2] for a in api.audits] == ["MCP_SERVER_REGISTERED"]


def test_register_http_server_masks_headers_and_dry_check_saves_nothing(api, http_url):
    url = http_url("json")
    dry = api.post("/api/mcp/check", json={"transport": "streamable_http", "url": url, "headers": {"Authorization": "Bearer secret-abcdef"}})
    assert dry.status_code == 200 and dry.json()["check"]["status"] == "ok" and dry.json()["config"]["headers"] == {"Authorization": MASK}
    assert "my-http" not in servers(api) and "secret-abcdef" not in dry.text
    r = api.post("/api/mcp/servers", json={"name": "my-http", "transport": "streamable_http", "url": url,
                                           "headers": {"Authorization": "Bearer secret-abcdef"}, "description": "가짜 HTTP"})
    assert r.status_code == 201, r.text
    assert servers(api)["my-http"]["headers"] == {"Authorization": "Bearer secret-abcdef"} and servers(api)["my-http"]["type"] == "url"
    s = {x["name"]: x for x in api.get("/api/mcp/servers").json()["servers"]}["my-http"]
    assert s["headers"] == {"Authorization": MASK} and s["description"] == "가짜 HTTP"


# ---------------------------------------------------------------- 잘못된 주소 · 명령 → 사유와 함께 거절 (저장 안 함)
@pytest.mark.parametrize("body,status,phrase", [
    ({"name": "bad-url", "transport": "streamable_http", "url": "ftp://x/mcp"}, 422, "url: http:// 또는 https://"),
    ({"name": "no-url", "transport": "streamable_http"}, 422, "url: HTTP 서버는 주소가 필요합니다"),
    ({"name": "odd", "transport": "websocket", "url": "ws://x"}, 422, "transport: 'websocket'"),
    ({"name": "shell", "transport": "stdio", "command": "bash", "args": ["-c", "rm -rf /"]}, 422, "셸('bash')은 등록하지 않습니다"),
    ({"name": "rm-it", "transport": "stdio", "command": "rm", "args": ["-rf", "/tmp/x"]}, 422, "허용한 실행기가 아닙니다"),
    ({"name": "Bad_Name", "transport": "stdio", "command": "npx"}, 422, "name: 소문자"),
    ({"name": "neo4j", "transport": "stdio", "command": "npx"}, 409, "기준(기본 제공) 서버 이름"),
])
def test_malformed_registrations_are_refused_with_a_reason(api, body, status, phrase):
    r = api.post("/api/mcp/servers", json=body)
    assert r.status_code == status and phrase in detail(r), r.text
    assert set(servers(api)) == set(SEED_MCP["mcpServers"])


def test_unreachable_or_dead_servers_are_refused_with_the_check_reason(api):
    port = _closed_port()
    r = api.post("/api/mcp/servers", json={"name": "down", "transport": "streamable_http", "url": f"http://127.0.0.1:{port}/mcp", "timeout": 3})
    assert r.status_code == 422 and "연결 검사 실패로 등록하지 않았습니다" in detail(r) and f"127.0.0.1:{port}" in detail(r)
    assert r.json()["detail"]["check"]["error_kind"] == "refused"
    dead = api.post("/api/mcp/servers", json={"name": "dead", "transport": "stdio", "command": sys.executable, "args": [FAKE, "--exit-early"], "timeout": 5})
    assert dead.status_code == 422 and dead.json()["detail"]["check"]["error_kind"] in ("closed", "exec"), dead.text
    missing = api.post("/api/mcp/servers", json={"name": "nope", "transport": "stdio", "command": "/no/such/dir/npx", "args": ["x"]})
    assert missing.status_code == 422 and missing.json()["detail"]["check"]["error_kind"] == "exec" and "process" in detail(missing)
    assert set(servers(api)) == set(SEED_MCP["mcpServers"]) and api.repo._mcp_checks == {}
    assert [a[2] for a in api.audits] == ["MCP_SERVER_REJECTED"] * 3


# ---------------------------------------------------------------- 선택 가능 도구(B1 이 쓰는 API) · 쓰기 도구 선택 불가
def test_selectable_lists_only_read_marked_tools_of_checked_servers(api):
    assert api.post("/api/mcp/servers", json=STDIO).status_code == 201
    sel = api.get("/api/mcp/selectable").json()
    s = {x["name"]: x for x in sel["servers"]}
    mine = s["my-fake"]
    assert mine["selectable"] is True and mine["agent_value"] == "my-fake" and mine["mine"] is True
    tools = {t["name"]: t for t in mine["tools"]}
    assert [n for n, t in tools.items() if t["selectable"]] == READ
    assert "readOnlyHint=false" in tools["submit_note"]["reason"] and "표시하지 않았습니다" in tools["greet"]["reason"]
    assert "'delete'" in tools["delete_rows"]["reason"] and tools["add"]["tool_id"] == "mcp__my-fake__add"
    assert [p["tool_id"] for p in sel["selectable_tools"]] == [f"mcp__my-fake__{n}" for n in READ]
    # 기준 서버도 검사 전에는 고를 수 없다(사유) — 검사는 기록만 남기고 기준 설정은 그대로
    # 합친 뒤 규칙: 기준 서버는 기본 에이전트가 쓰는 구성이라 검사 없이 고를 수 있다(워커가 기본 허용 목록으로 실행) — 학생 서버만 검사가 필요
    assert s["enterprise"]["selectable"] is True and s["enterprise"]["reason"] is None and s["enterprise"]["origin"] == "seed"
    assert s["enterprise"]["check"]["status"] == "never"          # 검사 상태는 그대로 보인다(참고)
    assert mcp_registry.refuse_reasons(mcp_registry.store_for(api.repo), "hyd", ["my-fake", "enterprise", "ghost"]) == [
        "ghost: 등록되지 않은 도구 서버입니다"]


def test_a_server_added_outside_the_portal_or_changed_after_its_check_is_not_selectable(api):
    assert api.post("/api/mcp/servers", json=STDIO).status_code == 201
    raw = servers(api)
    raw["sql-added"] = {"command": sys.executable, "args": [FAKE]}                                     # 랩업 SQL 경로(표시 없음)
    raw["my-fake"]["args"] = [FAKE, "--changed"]                                                     # 검사 뒤 손으로 바꿈
    api.repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": {"mcpServers": raw}})
    s = {x["name"]: x for x in api.get("/api/mcp/selectable").json()["servers"]}
    assert s["sql-added"]["origin"] == "external" and s["sql-added"]["check"]["status"] == "never" and not s["sql-added"]["selectable"]
    assert s["my-fake"]["check"]["status"] == "stale" and "설정이 바뀌었습니다" in s["my-fake"]["reason"]
    assert all(not t["selectable"] for t in s["my-fake"]["tools"])
    # 포털에서 다시 검사하면 학생 서버의 도장이 새 설정으로 바뀐다
    checked = api.post("/api/mcp/servers/sql-added/check", json={}).json()
    assert checked["check"]["status"] == "ok" and servers(api)["sql-added"]["hyd"]["gate"]["read_tools"] == READ


# ---------------------------------------------------------------- 기준 서버 보호
def test_base_servers_cannot_be_changed_or_deleted_and_checking_them_leaves_the_seed_alone(api, http_url):
    before = json.loads(json.dumps(servers(api)))
    for r in (api.put("/api/mcp/servers/enterprise", json={"transport": "streamable_http", "url": http_url("json")}),
              api.delete("/api/mcp/servers/hyd-dmn"), api.delete("/api/mcp/servers/neo4j?force=true")):
        assert r.status_code == 403 and "기준(기본 제공) 서버" in detail(r)
    chk = api.post("/api/mcp/servers/neo4j/check", json={"timeout": 2}).json()          # 이 PC 에 uvx 가 없거나 neo4j 가 없으면 실패 사유
    assert chk["check"]["status"] in ("ok", "failed")
    assert servers(api) == before and ("hyd", "neo4j") in api.repo._mcp_checks


# ---------------------------------------------------------------- 고치기 · 지우기
def test_update_keeps_masked_secrets_and_a_failing_update_keeps_the_old_config(api, http_url):
    url = http_url("json")
    assert api.post("/api/mcp/servers", json={"name": "my-http", "url": url, "headers": {"X-Api-Key": "k-999999"}}).status_code == 201
    ok = api.put("/api/mcp/servers/my-http", json={"url": url, "headers": {"X-Api-Key": MASK, "X-Team": "a"}, "description": "고침"})
    assert ok.status_code == 200, ok.text
    assert servers(api)["my-http"]["headers"] == {"X-Api-Key": "k-999999", "X-Team": "a"} and servers(api)["my-http"]["hyd"]["origin"] == "user"
    before = json.loads(json.dumps(servers(api)["my-http"]))
    bad = api.put("/api/mcp/servers/my-http", json={"url": f"http://127.0.0.1:{_closed_port()}/mcp", "timeout": 2})
    assert bad.status_code == 422 and "고치지 않았습니다" in detail(bad)
    assert servers(api)["my-http"] == before
    assert api.put("/api/mcp/servers/ghost", json={"url": url}).status_code == 404


def test_update_keeps_a_masked_password_inside_args(api):
    body = dict(STDIO, args=[FAKE, "--dsn", "postgresql://reader:pw-777777@db:5432/ent"])
    assert api.post("/api/mcp/servers", json=body).status_code == 201
    shown = {s["name"]: s for s in api.get("/api/mcp/servers").json()["servers"]}["my-fake"]
    assert shown["args"][-1] == f"postgresql://reader:{MASK}@db:5432/ent" and "pw-777777" not in api.get("/api/mcp/servers").text
    r = api.put("/api/mcp/servers/my-fake", json={"transport": "stdio", "command": sys.executable, "args": shown["args"], "env": shown["env"]})
    assert r.status_code == 200, r.text
    assert servers(api)["my-fake"]["args"][-1] == "postgresql://reader:pw-777777@db:5432/ent" and servers(api)["my-fake"]["env"] == {"FAKE_TOKEN": "tok-123456"}


def test_delete_refuses_while_an_agent_names_the_server_unless_forced(api):
    assert api.post("/api/mcp/servers", json=STDIO).status_code == 201
    api.repo.upsert_user({"id": "agent:mine", "username": "내 에이전트", "is_agent": True, "agent_type": "agent", "tools": "enterprise,my-fake", "tenant_id": "hyd"})
    r = api.delete("/api/mcp/servers/my-fake")
    assert r.status_code == 409 and "내 에이전트" in detail(r) and "my-fake" in servers(api)
    gone = api.delete("/api/mcp/servers/my-fake?force=true").json()
    assert gone["deleted"] and gone["agents_still_naming_it"] == ["내 에이전트"] and "my-fake" not in servers(api)
    assert ("hyd", "my-fake") not in api.repo._mcp_checks


# ---------------------------------------------------------------- 되돌리기
def test_reset_removes_student_servers_and_checks_and_keeps_the_seed(api):
    assert api.post("/api/mcp/servers", json=STDIO).status_code == 201
    raw = servers(api); raw["sql-added"] = {"type": "url", "url": "http://host.docker.internal:8301/mcp"}
    api.repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": {"mcpServers": raw}})
    api.post("/api/mcp/servers/enterprise/check", json={"timeout": 1})
    out = api.post("/api/mcp/reset", json={}).json()
    assert sorted(out["removed_servers"]) == ["my-fake", "sql-added"] and out["removed_checks"] == 2
    assert servers(api) == SEED_MCP["mcpServers"] and api.repo._mcp_checks == {}
    assert api.post("/api/mcp/reset", json={}).json() == {"removed_servers": [], "removed_checks": 0, "kept": list(SEED_MCP["mcpServers"])}


def test_legacy_mode_answers_503():
    app = FastAPI()
    mcp_registry.mount(app, runtime_factory=lambda: None, audit=lambda *a: None)
    c = TestClient(app)
    assert c.post("/api/mcp/servers", json=STDIO).status_code == 503 and c.get("/api/mcp/selectable").status_code == 503


# ---------------------------------------------------------------- 워커: 실제 실행에서도 읽기 표시 도구만 · 기본 에이전트 불변
def _worker_run(tmp_path, repo, cli="claude-code"):
    import test_u2_agents_skills as u2
    reqs = []

    def fake(provider, request, env):
        from cliagents import ExecEvent, ExecEventKind
        reqs.append(request)
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="m", session_id="s1")
        yield ExecEvent(kind=ExecEventKind.RESULT, text=u2.ANSWER, session_id="s1")
    from worker import workspace
    from worker.runner import Runner
    settings = Settings(workspace_root=tmp_path, schema_prompt_path=tmp_path / "none.md", consumer="t:1", cancel_check_every_s=0, cli_agent=cli)
    assert Runner(settings, repo, exec_fn=fake, schema_prompt="# s", resolve_provider=lambda pid: object()).poll_once() == 1
    row = next(w for w in repo.list_workitems(limit=None) if w["activity_id"] == "task:diagnose")
    return reqs[0], workspace.for_run(tmp_path, row["id"], tenant_id="hyd"), row


def _flags(request, flag):
    return request.extra_args[request.extra_args.index(flag) + 1].split(",") if flag in request.extra_args else None


def _seeded(tools="neo4j,enterprise,hyd-dmn"):
    import test_u2_agents_skills as u2
    repo, defn = u2._repo(tools=tools)
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": json.loads(json.dumps(SEED_MCP))})
    return repo, defn, u2


def test_registering_a_server_does_not_change_the_default_agents_run(tmp_path, api):
    repo, defn, u2 = _seeded()
    u2._start(repo, defn)
    before_req, before_ws, _ = _worker_run(tmp_path / "a", repo)
    before = (sorted(json.loads((before_ws.path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]), _flags(before_req, "--allowedTools"),
              _flags(before_req, "--disallowedTools"), agent_settings(repo, "hyd", "sys:agent").tools)
    # 포털 경로로 학생 서버 등록(같은 저장소)
    store = mcp_registry.store_for(repo)
    mcp_registry.register(store, "hyd", dict(STDIO))
    assert "my-fake" in store.servers("hyd")
    repo2, defn2, _ = _seeded()
    repo2.upsert_tenant(repo.get_tenant("hyd"))
    u2._start(repo2, defn2)
    after_req, after_ws, _ = _worker_run(tmp_path / "b", repo2)
    after = (sorted(json.loads((after_ws.path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]), _flags(after_req, "--allowedTools"),
             _flags(after_req, "--disallowedTools"), agent_settings(repo2, "hyd", "sys:agent").tools)
    assert before == after and before[0] == ["enterprise", "hyd-dmn", "neo4j"] and before[2] is None


def test_worker_runs_a_checked_student_server_with_read_tools_only(tmp_path):
    repo, defn, u2 = _seeded(tools="enterprise,my-fake,not-checked,changed")
    store = mcp_registry.store_for(repo)
    mcp_registry.register(store, "hyd", dict(STDIO))
    mcp_registry.register(store, "hyd", dict(STDIO, name="changed"))
    raw = store.servers("hyd")
    raw["not-checked"] = {"command": sys.executable, "args": [FAKE]}                                  # 랩업 SQL, 검사 안 함
    raw["changed"]["args"] = [FAKE, "--other"]                                                       # 검사 뒤 SQL 로 바꿈
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": {"mcpServers": raw}})
    u2._start(repo, defn)
    request, ws, row = _worker_run(tmp_path, repo)
    mcp = json.loads((ws.path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert sorted(mcp) == ["enterprise", "my-fake"] and "hyd" not in mcp["my-fake"]                    # 표시는 실행 설정에 섞이지 않는다
    allowed, denied = _flags(request, "--allowedTools"), _flags(request, "--disallowedTools")
    assert [a for a in allowed if a.startswith("mcp__my-fake__")] == [f"mcp__my-fake__{t}" for t in READ]
    assert "mcp__my-fake__*" not in allowed and denied == [f"mcp__my-fake__{t}" for t in BLOCKED]
    notices = [str(e["data"].get("content")) for e in repo.list_events(proc_inst_id=row["proc_inst_id"]) if (e.get("data") or {}).get("type") == "notice"]
    gate_note = next(n for n in notices if "연결 검사 게이트" in n)
    assert "not-checked(연결 검사를 통과하지 않은 서버)" in gate_note and "changed(검사한 뒤 설정이 바뀐 서버" in gate_note


def test_codex_enables_only_the_read_tools_of_a_gated_server(tmp_path):
    gate = bridge.gate_servers({"mcpServers": dict(SEED_MCP["mcpServers"], **{"x": dict(
        {"type": "url", "url": "http://x:1/mcp"}, hyd={"gate": {"fingerprint": bridge.config_fingerprint({"type": "url", "url": "http://x:1/mcp"}),
                                                              "read_tools": ["list_files"], "blocked_tools": ["write_file"]}})})},
        trusted={"neo4j", "enterprise", "hyd-dmn"})
    res = bridge.install(tmp_path, gate.config, provider_id="codex", read_tools=gate.read_tools)
    toml = (tmp_path / "codex-mcp.toml").read_text(encoding="utf-8")
    assert '"enabled_tools"=["list_files"]' in toml.replace(" ", "") and "write_file" not in toml and "x" in res.servers


def test_host_rewrite_happens_after_the_gate_so_the_stamp_still_matches(tmp_path):
    entry = {"type": "url", "url": "http://host.docker.internal:8301/mcp", "transport": "streamable_http"}
    entry["hyd"] = {"origin": "user", "gate": {"fingerprint": bridge.config_fingerprint(entry), "read_tools": ["read_file"], "blocked_tools": ["write_file"]}}
    gate = bridge.gate_servers({"mcpServers": {"my-folder": entry}}, trusted=set())
    assert gate.dropped == {} and gate.read_tools == {"my-folder": ["read_file"]}
    bridge.install(tmp_path, gate.config, provider_id="claude-code", host_rewrite=bridge.parse_host_rewrite("host.docker.internal:8301=127.0.0.1:8301"))
    assert json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["my-folder"] == {"type": "http", "url": "http://127.0.0.1:8301/mcp"}


def test_sse_servers_are_written_as_sse_for_claude_code(tmp_path):
    cfg = {"mcpServers": {"old-sse": {"type": "url", "url": "http://h:1/sse", "transport": "sse"}, "new": {"type": "url", "url": "http://h:2/mcp"}}}
    bridge.install(tmp_path, cfg, provider_id="claude-code")
    mcp = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert mcp["old-sse"]["type"] == "sse" and mcp["new"]["type"] == "http"


# ---------------------------------------------------------------- 포털 폼(node vm) — 입력 → 요청 본문
def test_portal_register_form_builds_the_request_body():
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node 없음")
    script = r"""
const vm = require('vm'); const fs = require('fs');
const ctx = { window: {}, console }; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const f = ctx.window.hydMcp.register;
const out = [];
out.push(f.bodyFrom({ name: 'my-folder', transport: 'stdio', command: 'npx', args: '-y @modelcontextprotocol/server-filesystem /data', env: 'ROOT=/data\nTOKEN=abc', description: '폴더' }));
out.push(f.bodyFrom({ name: 'notion', transport: 'streamable_http', url: 'http://host.docker.internal:8302/mcp', headers: 'Authorization=Bearer x' }));
for (const bad of [{ name: '', transport: 'stdio', command: 'npx' }, { name: 'a', transport: 'stdio', command: '' }, { name: 'a', transport: 'sse', url: '' }, { name: 'a', transport: 'stdio', command: 'npx', env: 'NOEQUALS' }]) {
  try { f.bodyFrom(bad); out.push('no error'); } catch (e) { out.push('ERR ' + e.message); }
}
console.log(JSON.stringify(out));
"""
    r = subprocess.run([node, "-e", script, str(ROOT / "it" / "portal" / "www" / "mcp.js")], capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out[0] == {"name": "my-folder", "transport": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"],
                      "env": {"ROOT": "/data", "TOKEN": "abc"}, "description": "폴더"}
    assert out[1] == {"name": "notion", "transport": "streamable_http", "url": "http://host.docker.internal:8302/mcp", "headers": {"Authorization": "Bearer x"}}
    assert out[2].startswith("ERR 이름") and out[3].startswith("ERR 명령") and out[4].startswith("ERR 주소") and "NOEQUALS" in out[5]
