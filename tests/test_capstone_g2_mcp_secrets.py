"""G2 (전체 과정 랩업 — docs/handoff/verification/2026-10-09/capstone-lab.md 5.2): 토큰이 필요한 MCP 서버(구글 등)를 붙이는 자리.

⓪ 워커가 에이전트용 .mcp.json 에 주소형 서버의 headers 를 함께 쓴다(전에는 {type, url} 만 써서 에이전트만 인증 실패).
① 설정에는 ${SECRET:KEY} 자리표시자만, 값은 비밀 값 표(또는 HYD_SECRET_<KEY>) — 연결 검사 · 써 보기 · 시스템 task · 워커가 직전에 채운다.
   값은 어떤 응답 · 설정 · 감사 기록에도 실리지 않고, 토큰을 갈아 끼워도 설정 해시(연결 검사 도장)는 그대로다.
② 강사 확인 읽기 목록: readOnlyHint 표시만 없는 도구를 강사가 확인하면 도장의 read_tools 에 들어간다(확인자 · 이유). 쓰기 표시 · 쓰기 이름은 안 된다.
③ 401/403 은 "인증이 만료되었거나 없습니다 — 연결을 다시 하세요" 로 갈라 보인다.
OAuth 흐름은 넣지 않는다(구글 인증은 사용자 몫).
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import mcp_api, mcp_check, mcp_registry, mcp_secrets, procdb
from worker import bridge, context, env_guard

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
from test_mcp_check import _Handler  # noqa: E402

TOKEN = "ya29.live-token-abcdef123456"
PLACEHOLDER = "Bearer ${SECRET:DRIVE_TOKEN}"
SEED = {"mcpServers": {"enterprise": {"type": "url", "url": "http://enterprise-mcp:8199/mcp", "transport": "streamable_http"}}}


class _TokenHandler(_Handler):
    """구글처럼 Authorization 토큰이 맞아야 응답하는 가짜 서버(틀리거나 없으면 401)."""
    mode = "json"
    expected = TOKEN

    def do_POST(self):
        if self.headers.get("Authorization") != f"Bearer {self.expected}":
            self.send_response(401); self.end_headers(); return
        self._serve_mcp("json")


@pytest.fixture
def token_url():
    servers = []

    def start():
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _TokenHandler)
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_port}/mcp"
    yield start
    for srv in servers:
        srv.shutdown(); srv.server_close()


@pytest.fixture
def api(monkeypatch):
    for k in [k for k in list(__import__("os").environ) if k.startswith(mcp_secrets.ENV_PREFIX)]:
        monkeypatch.delenv(k)
    repo = procdb.MemoryRepo()
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": json.loads(json.dumps(SEED))})
    rt = SimpleNamespace(repo=repo, tenant_id="hyd")
    audits = []
    app = FastAPI()
    mcp_api.register(app, runtime_factory=lambda: rt, audit=lambda *a: audits.append(a))
    mcp_registry.mount(app, runtime_factory=lambda: rt, audit=lambda *a: audits.append(a))
    mcp_secrets.mount(app, runtime_factory=lambda: rt, audit=lambda *a: audits.append(a))
    c = TestClient(app)
    c.repo, c.audits = repo, audits
    return c


def servers(c) -> dict:
    return c.repo.get_tenant("hyd")["mcp"]["mcpServers"]


def detail(r) -> str:
    d = r.json()["detail"]
    return d["reason"] if isinstance(d, dict) else d


DRIVE = lambda url: {"name": "my-drive", "transport": "streamable_http", "url": url, "headers": {"Authorization": PLACEHOLDER}}  # noqa: E731


# ---------------------------------------------------------------- 자리표시자 규칙 (mcp-hub resolve_template 와 같은 모양)
def test_placeholders_are_read_from_headers_and_env_only_and_filled_from_values():
    entry = {"type": "url", "url": "https://x/mcp", "headers": {"Authorization": PLACEHOLDER, "X-Org": "hyd"}}
    assert mcp_secrets.references(entry) == ["DRIVE_TOKEN"]
    filled, missing = mcp_secrets.resolve(entry, {"DRIVE_TOKEN": TOKEN})
    assert filled["headers"] == {"Authorization": f"Bearer {TOKEN}", "X-Org": "hyd"} and missing == []
    assert entry["headers"]["Authorization"] == PLACEHOLDER                                   # 원본(설정)은 그대로
    _, missing = mcp_secrets.resolve(entry, {})
    assert missing == ["DRIVE_TOKEN"]
    assert mcp_secrets.misplaced({"url": "https://x/${SECRET:T}"}) and mcp_secrets.misplaced({"command": "npx", "args": ["--token=${SECRET:T}"]})
    assert mcp_secrets.misplaced({"headers": {"A": "${SECRET:lower}"}})
    assert mcp_secrets.is_reference_only(PLACEHOLDER) and mcp_secrets.is_reference_only("${SECRET:A}")
    assert not mcp_secrets.is_reference_only("Bearer abc ${SECRET:A}") and not mcp_secrets.is_reference_only("Bearer abc")
    assert mcp_secrets.literal_secrets({"headers": {"Authorization": "Bearer abc"}, "env": {"API_KEY": "${SECRET:K}"}}) == ["headers.Authorization"]
    assert mcp_secrets.env_values({"HYD_SECRET_DRIVE_TOKEN": "v", "HYD_SECRET_bad": "x", "OTHER": "y"}) == {"DRIVE_TOKEN": "v"}


# ---------------------------------------------------------------- 포털: 등록 · 비밀 값 · 연결 검사 · 401 문구
def test_a_token_server_registers_with_a_placeholder_and_the_token_never_comes_back(api, token_url):
    url = token_url()
    no_secret = api.post("/api/mcp/servers", json=DRIVE(url))
    assert no_secret.status_code == 422 and no_secret.json()["detail"]["check"]["error_kind"] == "secret"
    assert "DRIVE_TOKEN" in detail(no_secret) and "비밀 값" in detail(no_secret)
    put = api.put("/api/mcp/secrets/DRIVE_TOKEN", json={"value": TOKEN, "by": "강사"})
    assert put.status_code == 200 and TOKEN not in put.text
    r = api.post("/api/mcp/servers", json=DRIVE(url))
    assert r.status_code == 201, r.text
    assert r.json()["warnings"] == [] and "greet" in r.json()["gate"]["blocked_tools"]
    assert servers(api)["my-drive"]["headers"] == {"Authorization": PLACEHOLDER}                # 설정에는 이름만
    listed = api.get("/api/mcp/servers").text
    secrets = api.get("/api/mcp/secrets").json()
    assert TOKEN not in listed and TOKEN not in json.dumps(secrets) and TOKEN not in json.dumps(api.audits, ensure_ascii=False)
    shown = {s["name"]: s for s in json.loads(listed)["servers"]}["my-drive"]
    assert shown["headers"] == {"Authorization": PLACEHOLDER}                                    # 비밀 이름은 가리지 않아도 된다
    assert secrets["secrets"] == [{"key": "DRIVE_TOKEN", "stored": True, "from_env": False, "updated_at": secrets["secrets"][0]["updated_at"],
                                   "updated_by": "강사", "used_by": ["my-drive"], "missing": False}]
    # 도구 지도 써 보기도 부르기 직전에 채운다
    called = api.post("/api/mcp/servers/my-drive/tools/add/call", json={"arguments": {"a": 1, "b": 2}})
    assert called.status_code == 200 and "3" in called.json()["result"]["text"]


def test_swapping_an_expired_token_keeps_the_stamp_and_401_says_to_reconnect(api, token_url):
    url = token_url()
    api.put("/api/mcp/secrets/DRIVE_TOKEN", json={"value": TOKEN})
    assert api.post("/api/mcp/servers", json=DRIVE(url)).status_code == 201
    stamp = servers(api)["my-drive"]["hyd"]["gate"]["fingerprint"]
    api.put("/api/mcp/secrets/DRIVE_TOKEN", json={"value": "expired-000000"})
    bad = api.post("/api/mcp/servers/my-drive/check", json={}).json()
    assert bad["check"]["error_kind"] == "auth" and "인증이 만료되었거나 없습니다" in bad["check"]["error"] and "연결을 다시 하세요" in bad["check"]["error"]
    assert "expired-000000" not in json.dumps(bad, ensure_ascii=False)
    api.put("/api/mcp/secrets/DRIVE_TOKEN", json={"value": TOKEN})
    ok = api.post("/api/mcp/servers/my-drive/check", json={}).json()
    assert ok["check"]["status"] == "ok" and servers(api)["my-drive"]["hyd"]["gate"]["fingerprint"] == stamp   # 토큰을 바꿔도 해시는 그대로


def test_secret_api_validates_and_reset_removes_the_secrets(api):
    assert api.put("/api/mcp/secrets/drive-token", json={"value": "x"}).status_code == 422
    assert api.put("/api/mcp/secrets/DRIVE_TOKEN", json={"value": ""}).status_code == 422
    assert api.put("/api/mcp/secrets/DRIVE_TOKEN", json={"value": "${SECRET:OTHER}"}).status_code == 422
    assert api.delete("/api/mcp/secrets/NOPE").status_code == 404
    assert api.put("/api/mcp/secrets/DRIVE_TOKEN", json={"value": TOKEN}).status_code == 200
    assert api.post("/api/mcp/reset", json={}).json()["removed_secrets"] == 1
    assert api.get("/api/mcp/secrets").json()["secrets"] == []


def test_misplaced_placeholders_and_literal_tokens(api, token_url):
    url = token_url()
    r = api.post("/api/mcp/servers", json={"name": "in-url", "transport": "streamable_http", "url": url + "?key=${SECRET:K}"})
    assert r.status_code == 422 and "headers · env 값에만" in detail(r)
    lit = api.post("/api/mcp/check", json={"transport": "streamable_http", "url": url, "headers": {"Authorization": f"Bearer {TOKEN}"}})
    assert lit.json()["check"]["status"] == "ok" and "${SECRET:이름}" in lit.json()["warnings"][0] and TOKEN not in lit.text


def test_env_fallback_fills_when_the_table_has_no_value(api, token_url, monkeypatch):
    monkeypatch.setenv("HYD_SECRET_DRIVE_TOKEN", TOKEN)
    assert api.post("/api/mcp/servers", json=DRIVE(token_url())).status_code == 201
    row = api.get("/api/mcp/secrets").json()["secrets"][0]
    assert row["from_env"] is True and row["missing"] is False and row["stored"] is False


# ---------------------------------------------------------------- ② 강사 확인 읽기 목록
def test_lecturer_confirms_an_unmarked_tool_as_read_and_the_gate_takes_it(api, token_url):
    api.put("/api/mcp/secrets/DRIVE_TOKEN", json={"value": TOKEN})
    assert api.post("/api/mcp/servers", json=DRIVE(token_url())).status_code == 201
    before = {t["name"]: t for t in {s["name"]: s for s in api.get("/api/mcp/selectable").json()["servers"]}["my-drive"]["tools"]}
    assert before["greet"]["selectable"] is False and before["greet"]["confirmable"] is True and before["submit_note"]["confirmable"] is False
    assert api.post("/api/mcp/servers/my-drive/tools/greet/call", json={"arguments": {"name": "a"}}).status_code == 403
    no_reason = api.post("/api/mcp/servers/my-drive/read-confirm", json={"tool": "greet", "by": "강사"})
    assert no_reason.status_code == 422 and "이유" in detail(no_reason)
    for tool in ("submit_note", "delete_rows"):                      # 쓰기 표시 · 쓰기 이름은 확인할 수 없다
        r = api.post("/api/mcp/servers/my-drive/read-confirm", json={"tool": tool, "by": "강사", "reason": "문서상 읽기"})
        assert r.status_code == 422 and "확인할 수 없습니다" in detail(r)
    assert api.post("/api/mcp/servers/my-drive/read-confirm", json={"tool": "add", "by": "강사", "reason": "x"}).status_code == 409
    ok = api.post("/api/mcp/servers/my-drive/read-confirm", json={"tool": "greet", "by": "강사", "reason": "인사 문자열만 돌려준다(쓰기 없음)"})
    assert ok.status_code == 200, ok.text
    gate = servers(api)["my-drive"]["hyd"]["gate"]
    assert "greet" in gate["read_tools"] and "greet" not in gate["blocked_tools"] and gate["confirmed_tools"] == ["greet"]
    assert servers(api)["my-drive"]["hyd"]["read_confirmed"]["greet"]["by"] == "강사"
    after = {t["name"]: t for t in {s["name"]: s for s in api.get("/api/mcp/selectable").json()["servers"]}["my-drive"]["tools"]}
    assert after["greet"]["selectable"] is True and after["greet"]["confirmed"]["reason"].startswith("인사")
    assert api.post("/api/mcp/servers/my-drive/tools/greet/call", json={"arguments": {"name": "a"}}).status_code == 200
    # 다시 검사해도 확인은 남고, 도장은 확인을 반영해 다시 계산된다
    api.post("/api/mcp/servers/my-drive/check", json={})
    assert "greet" in servers(api)["my-drive"]["hyd"]["gate"]["read_tools"]
    off = api.post("/api/mcp/servers/my-drive/read-confirm", json={"tool": "greet", "on": False, "by": "강사"})
    assert off.status_code == 200 and "greet" in servers(api)["my-drive"]["hyd"]["gate"]["blocked_tools"]
    assert "read_confirmed" not in servers(api)["my-drive"]["hyd"]
    assert [a[2] for a in api.audits if a[2].startswith("MCP_READ")] == ["MCP_READ_CONFIRMED", "MCP_READ_UNCONFIRMED"]


def test_confirmable_rule():
    assert mcp_check.confirmable({"name": "search_files", "annotations": {}})
    assert mcp_check.confirmable({"name": "list_events"})
    assert not mcp_check.confirmable({"name": "create_event"})
    assert not mcp_check.confirmable({"name": "read_x", "annotations": {"readOnlyHint": False}})
    assert not mcp_check.confirmable({"name": "get_x", "annotations": {"destructiveHint": True}})
    assert not mcp_check.confirmable({"name": "get_x", "annotations": {"readOnlyHint": True}})       # 이미 읽기 — 확인할 필요 없음


# ---------------------------------------------------------------- ⓪ · ① 워커: headers 를 .mcp.json 에, 자리표시자는 직전에 채움
def _gated(entry: dict, read=("add",), blocked=("submit_note",)) -> dict:
    entry = dict(entry)
    entry["hyd"] = {"origin": "user", "gate": {"fingerprint": bridge.config_fingerprint(entry), "read_tools": list(read), "blocked_tools": list(blocked)}}
    return entry


def test_worker_writes_http_headers_and_fills_secrets_then_cleanup_removes_them(tmp_path):
    drive = _gated({"type": "url", "url": "https://drive.example/mcp", "transport": "streamable_http", "headers": {"Authorization": PLACEHOLDER}})
    plain = _gated({"type": "url", "url": "http://host.docker.internal:8301/mcp", "headers": {"X-Api-Key": "k-1"}})
    tenant = bridge.attach_secrets({"mcpServers": {"my-drive": drive, "my-plain": plain}}, {"DRIVE_TOKEN": TOKEN, "UNUSED": "zzz"})
    assert tenant[bridge.SECRETS_KEY] == {"DRIVE_TOKEN": TOKEN}                                    # 쓰는 비밀만 싣는다
    assert bridge.SECRETS_KEY not in bridge.without_secrets(tenant)
    gate = bridge.gate_servers(tenant, trusted=set())
    assert gate.dropped == {} and gate.read_tools == {"my-drive": ["add"], "my-plain": ["add"]}   # 해시는 자리표시자 설정으로 — 도장이 맞는다
    res = bridge.install(tmp_path, gate.config, provider_id="claude-code", read_tools=gate.read_tools)
    mcp = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["my-drive"] == {"type": "http", "url": "https://drive.example/mcp", "headers": {"Authorization": f"Bearer {TOKEN}"}}
    assert mcp["mcpServers"]["my-plain"]["headers"] == {"X-Api-Key": "k-1"} and bridge.SECRETS_KEY not in mcp and res.dropped == {}
    assert sorted(bridge.cleanup(tmp_path)) == ["my-drive", "my-plain"]
    after = (tmp_path / ".mcp.json").read_text(encoding="utf-8")
    assert TOKEN not in after and "k-1" not in after and "my-drive" in after


def test_worker_leaves_out_a_server_whose_secret_has_no_value_with_a_reason(tmp_path):
    drive = _gated({"type": "url", "url": "https://drive.example/mcp", "headers": {"Authorization": PLACEHOLDER}})
    tenant = bridge.attach_secrets({"mcpServers": {"my-drive": drive}}, {})
    gate = bridge.gate_servers(tenant, trusted=set())
    assert "my-drive" in gate.dropped and "DRIVE_TOKEN" in gate.dropped["my-drive"] and gate.config["mcpServers"] == {}
    res = bridge.install(tmp_path, {"mcpServers": {"my-drive": drive}}, provider_id="claude-code")      # 게이트를 거치지 않아도 빈 토큰으로 띄우지 않는다
    assert res.dropped == {"my-drive": "비밀 값 DRIVE_TOKEN 이(가) 없음"} and "my-drive" not in res.servers


def test_codex_gets_http_headers(tmp_path):
    drive = _gated({"type": "url", "url": "https://drive.example/mcp", "headers": {"Authorization": PLACEHOLDER}})
    gate = bridge.gate_servers(bridge.attach_secrets({"mcpServers": {"my-drive": drive}}, {"DRIVE_TOKEN": TOKEN}), trusted=set())
    bridge.install(tmp_path, gate.config, provider_id="codex", read_tools=gate.read_tools)
    toml = (tmp_path / "codex-mcp.toml").read_text(encoding="utf-8").replace(" ", "")
    assert f'"http_headers"={{"Authorization"="Bearer{TOKEN}"}}' in toml and '"enabled_tools"=["add"]' in toml


def test_portal_and_worker_fingerprints_agree_on_placeholder_headers():
    entry = {"type": "url", "url": "https://drive.example/mcp", "transport": "streamable_http", "headers": {"Authorization": PLACEHOLDER}}
    assert mcp_registry.fingerprint(entry) == bridge.config_fingerprint(entry)
    assert mcp_registry.fingerprint(entry) != mcp_registry.fingerprint(dict(entry, headers={}))       # headers 는 해시에 들어간다


def test_worker_context_carries_secrets_only_to_the_bridge(monkeypatch):
    for k in [k for k in list(__import__("os").environ) if k.startswith(mcp_secrets.ENV_PREFIX)]:
        monkeypatch.delenv(k)
    monkeypatch.setattr(env_guard, "_HELD", {"HYD_SECRET_CAL_TOKEN": "cal-999999"})
    repo = procdb.MemoryRepo()
    mcp_secrets.store_for(repo).put("hyd", "DRIVE_TOKEN", TOKEN, "강사", "t")
    cfg = {"mcpServers": {"my-drive": {"type": "url", "url": "https://d/mcp", "headers": {"Authorization": PLACEHOLDER}},
                          "my-cal": {"type": "url", "url": "https://c/mcp", "headers": {"Authorization": "Bearer ${SECRET:CAL_TOKEN}"}}}}
    out = context.with_secrets(repo, "hyd", cfg)
    assert out[bridge.SECRETS_KEY] == {"DRIVE_TOKEN": TOKEN, "CAL_TOKEN": "cal-999999"}
    ctx = context.Context(row={}, form_id="f", form_fields=[], tenant_mcp=out)
    assert bridge.SECRETS_KEY not in ctx.extras["tenant_mcp"] and TOKEN not in json.dumps(ctx.extras, ensure_ascii=False, default=str)
    assert context.with_secrets(repo, "hyd", SEED) is SEED                                             # 자리표시자가 없으면 그대로


def test_env_guard_holds_hyd_secrets_out_of_the_cli_environment(monkeypatch):
    monkeypatch.setattr(env_guard, "_HELD", {})
    env = {"HYD_SECRET_DRIVE": "v1", "PATH": "/bin"}
    assert env_guard.scrub(env) == ["HYD_SECRET_DRIVE"] and env == {"PATH": "/bin"}
    assert env_guard.held_secrets() == {"HYD_SECRET_DRIVE": "v1"}


def test_system_task_resolves_secrets_or_stops_with_a_reason():
    repo = procdb.MemoryRepo()
    spec = {"transport": "streamable_http", "url": "https://d/mcp", "headers": {"Authorization": PLACEHOLDER}}
    with pytest.raises(mcp_secrets.SecretError) as e:
        mcp_secrets.runtime_spec(repo, "hyd", "my-drive", spec, environ={})
    assert "DRIVE_TOKEN" in e.value.reason and "my-drive" in e.value.reason
    mcp_secrets.store_for(repo).put("hyd", "DRIVE_TOKEN", TOKEN, "강사", "t")
    assert mcp_secrets.runtime_spec(repo, "hyd", "my-drive", spec, environ={})["headers"]["Authorization"] == f"Bearer {TOKEN}"
    plain = {"transport": "streamable_http", "url": "https://d/mcp", "headers": {}}
    assert mcp_secrets.runtime_spec(repo, "hyd", "x", plain) is plain
