import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from procsvc import mcp_oauth as O, mcp_registry as R, mcp_secrets as S, procdb

RESOURCE = "https://mcp.example.com/mcp"
ISSUER = "https://auth.example.com"
REAL_DNS = O.socket.getaddrinfo


def test_official_calendar_preset_read_scopes():
    preset = next(p for p in O.CATALOG if p['id'] == 'google-calendar')
    assert set(preset['scopes']) == {'https://www.googleapis.com/auth/calendar.calendarlist.readonly', 'https://www.googleapis.com/auth/calendar.events.freebusy', 'https://www.googleapis.com/auth/calendar.events.readonly'}


class Fake:
    def __init__(self):
        self.calls = []
        self.reject = False
        self.dynamic = True
        self.broken = False

    def request(self, method, url, data=None, headers=None):
        self.calls.append((method, url, data, headers))
        if self.broken:
            raise O.OAuthError("endpoint_unavailable", "서버 불가", 502)
        if url == RESOURCE:
            return 401, {"www-authenticate": 'Bearer resource_metadata="https://mcp.example.com/resource", scope="read"'}, {}
        if url.endswith("/resource"):
            return 200, {}, {"resource": RESOURCE, "authorization_servers": [ISSUER]}
        if "well-known" in url:
            body = {"issuer": ISSUER, "authorization_endpoint": ISSUER + "/authorize", "token_endpoint": ISSUER + "/token", "code_challenge_methods_supported": ["S256"]}
            if self.dynamic:
                body["registration_endpoint"] = ISSUER + "/register"
            return 200, {}, body
        if url.endswith("/register"):
            return 201, {}, {"client_id": "fake-client", "token_endpoint_auth_method": "none"}
        if url.endswith("/token"):
            return (400, {}, {"error": "SECRET_RAW_ERROR"}) if self.reject else (200, {}, {"access_token": "PRIVATE_ACCESS_TOKEN", "refresh_token": "PRIVATE_REFRESH_TOKEN", "expires_in": 90, "token_type": "Bearer"})
        raise AssertionError(url)


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(O.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 443))])
    repo = procdb.MemoryRepo()
    repo.upsert_tenant({"id": "hyd", "mcp": {"mcpServers": {}}})
    env = {"HYD_MCP_OAUTH_KEY": Fernet.generate_key().decode(), "HYD_MCP_OAUTH_CALLBACK_URL": "http://localhost:8088/api/mcp/connections/callback"}
    fake = Fake()
    now = [1000]
    svc = O.Service(repo, "hyd", env, fake, lambda: now[0])
    return svc, repo, env, fake, now


def begin(svc):
    row = svc.prepare({"url": RESOURCE, "auth_mode": "oauth"})
    result = svc.start(row["id"], "browser")
    state = parse_qs(urlsplit(result["authorization_url"]).query)["state"][0]
    return row, result, state


def test_pkce_encrypted_storage_binding_and_replay(setup):
    svc, repo, env, fake, now = setup
    row, result, state = begin(svc)
    params = parse_qs(urlsplit(result["authorization_url"]).query)
    assert params["code_challenge_method"] == ["S256"]
    assert params["resource"] == [RESOURCE]
    assert not R.store_for(repo).servers("hyd")
    for s, binding, code in [("wrong", "browser", "invalid_state"), (state, "another", "invalid_binding")]:
        with pytest.raises(O.OAuthError) as exc:
            svc.callback(s, binding, "code")
        assert exc.value.code == code
    public, message = svc.callback(state, "browser", "code")
    assert public["status"] == "login_complete"
    assert message["state"] == result["state"] != state
    assert message["attempt_id"] == result["attempt_id"]
    with pytest.raises(O.OAuthError, match="이미 완료"):
        svc.callback(state, "browser", "code")
    assert "PRIVATE_ACCESS_TOKEN" not in str(repo._mcp_secrets)


def test_encrypted_values_never_public_or_resolved(setup):
    svc, repo, env, fake, now = setup
    row, result, state = begin(svc)
    svc.callback(state, "browser", "code")
    raw = str(repo._mcp_secrets)
    assert "PRIVATE_ACCESS_TOKEN" not in raw and "PRIVATE_REFRESH_TOKEN" not in raw
    assert "PRIVATE_ACCESS_TOKEN" not in json.dumps(svc.listing())
    assert S.load(repo, "hyd", {}) == {}
    assert S.overview(repo, "hyd", {}, {})["secrets"] == []
    key = next(iter(repo._mcp_secrets))[1]
    assert not S.valid_key(key)
    with pytest.raises(S.SecretError):
        S.put(repo, "hyd", key, "replace", "test", "now")
    assert O.Service(repo, "other", env, fake).store.rows() == []
    with pytest.raises(O.OAuthError):
        O.Service(repo, "other", env, fake).store.get(row["id"])
    bad = dict(env, HYD_MCP_OAUTH_KEY=Fernet.generate_key().decode())
    with pytest.raises(O.OAuthError, match="記録|기록"):
        O.Service(repo, "hyd", bad, fake).store.rows()


@pytest.mark.parametrize("mode,expected", [("denied", "denied"), ("expired", "expired"), ("issuer", "issuer_mismatch"), ("rejected", "token_rejected")])
def test_callback_negative_consumes_state(setup, mode, expected):
    svc, repo, env, fake, now = setup
    row, result, state = begin(svc)
    if mode == "expired":
        now[0] += 601
    fake.reject = mode == "rejected"
    out, message = svc.callback(state, "browser", "code", "access_denied" if mode == "denied" else None, "https://wrong.example" if mode == "issuer" else None)
    assert out["status"] == "failed" and out["reason_code"] == expected
    assert "SECRET_RAW_ERROR" not in str(out)
    assert not R.store_for(repo).servers("hyd")
    with pytest.raises(O.OAuthError):
        svc.callback(state, "browser", "code")


def test_discovery_client_missing_cancel_and_storage_missing(setup):
    svc, repo, env, fake, now = setup
    row = svc.prepare({"url": RESOURCE, "auth_mode": "oauth"})
    fake.dynamic = False
    with pytest.raises(O.OAuthError) as exc:
        svc.start(row["id"], "browser")
    assert exc.value.code == "client_not_configured"
    fake.broken = True
    with pytest.raises(O.OAuthError) as exc:
        svc.start(row["id"], "browser")
    assert exc.value.code == "endpoint_unavailable"
    fake.broken = False
    fake.dynamic = True
    start = svc.start(row["id"], "browser")
    state = parse_qs(urlsplit(start["authorization_url"]).query)["state"][0]
    assert svc.cancel(row["id"])["reason_code"] == "cancelled"
    with pytest.raises(O.OAuthError):
        svc.callback(state, "browser", "code")
    missing = O.Service(repo, "hyd", {}, fake)
    assert not missing.listing()["configuration"]["storage_ready"]
    with pytest.raises(O.OAuthError) as exc:
        missing.prepare({"url": RESOURCE, "auth_mode": "oauth"})
    assert exc.value.code == "storage_not_configured"


def check_record(ok=True):
    return {"status": "ok" if ok else "failed", "fingerprint": "old", "tools": [{"name": "get", "read_only": True, "description": "PRIVATE_ACCESS_TOKEN"}], "checked_at": "now"}


def test_tools_gate_refresh_failure_disconnect_runtime(setup, monkeypatch):
    svc, repo, env, fake, now = setup
    row, result, state = begin(svc)
    svc.callback(state, "browser", "code")
    monkeypatch.setattr(R, "run_check", lambda *a: check_record(False))
    assert svc.check(row["id"])["reason_code"] == "tools_check_failed"
    assert not R.store_for(repo).servers("hyd")
    row, result, state = begin(svc)
    svc.callback(state, "browser", "code")
    monkeypatch.setattr(R, "run_check", lambda *a: check_record())
    assert svc.check(row["id"])["status"] == "connected"
    entry = R.store_for(repo).servers("hyd")[row["name"]]
    assert entry["headers"] == {}
    assert entry["hyd"]["gate"]["fingerprint"] == R.fingerprint(entry)
    assert "PRIVATE_ACCESS_TOKEN" not in json.dumps(R.store_for(repo).checks("hyd"))
    monkeypatch.setattr(O, "Service", lambda r, t, environ=None: svc)
    resolved, used = S.runtime_spec(repo, "hyd", row["name"], entry, env)
    assert resolved["headers"]["Authorization"] == "Bearer PRIVATE_ACCESS_TOKEN"
    assert "PRIVATE_ACCESS_TOKEN" in used
    now[0] += 100
    fake.reject = True
    with pytest.raises(S.SecretError):
        S.runtime_spec(repo, "hyd", row["name"], entry, env)
    assert svc.store.get(row["id"])["reason_code"] == "refresh_rejected"
    assert svc.cancel(row["id"], True)["status"] == "disconnected"
    assert not R.store_for(repo).servers("hyd")


def test_ssrf_and_discovery_resource_issuer_pkce_validation(setup, monkeypatch):
    svc, repo, env, fake, now = setup
    for url in ["http://example.com/mcp", "https://u:p@example.com/mcp", "https://example.com/mcp?token=secret"]:
        with pytest.raises(O.OAuthError):
            O.validate_url(url, env)
    monkeypatch.setattr(O.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("169.254.169.254", 80))])
    with pytest.raises(O.OAuthError):
        O.validate_url("https://metadata.test", {"HYD_MCP_OAUTH_PRIVATE_ORIGINS": "https://metadata.test"})


def test_http_api_callback_cookie_and_secret_free_responses(setup, monkeypatch):
    svc, repo, env, fake, now = setup
    monkeypatch.setattr(O, "Service", lambda *a, **k: svc)
    monkeypatch.setattr(R, "run_check", lambda *a: check_record())
    app = FastAPI()
    O.mount(app, runtime_factory=lambda: SimpleNamespace(repo=repo, tenant_id="hyd"), audit=lambda *a: None)
    client = TestClient(app)
    assert client.post("/api/mcp/connections/prepare", json={"url": RESOURCE, "auth_mode": "oauth"}, headers={"Origin": "https://evil.example"}).status_code == 403
    row = client.post("/api/mcp/connections/prepare", json={"url": RESOURCE, "auth_mode": "oauth"}).json()
    result = client.post(f'/api/mcp/connections/{row["id"]}/start')
    assert "HttpOnly" in result.headers["set-cookie"] and "SameSite=lax" in result.headers["set-cookie"]
    state = parse_qs(urlsplit(result.json()["authorization_url"]).query)["state"][0]
    assert client.get("/api/mcp/connections/callback", params={"state": state, "code": "code"}).status_code == 200
    out = client.post(f'/api/mcp/connections/{row["id"]}/check')
    assert out.json()["status"] == "connected"
    assert "PRIVATE_ACCESS_TOKEN" not in out.text
    assert "PRIVATE_REFRESH_TOKEN" not in client.get("/api/mcp/connections").text


def test_real_mcp_initialize_tools_gate_no_business_calls(setup, monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    svc, repo, env, fake, now = setup
    row, result, state = begin(svc)
    svc.callback(state, "browser", "code")
    methods = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.headers["Authorization"] == "Bearer PRIVATE_ACCESS_TOKEN"
            methods.append(msg["method"])
            if msg["method"] == "notifications/initialized":
                self.send_response(202)
                self.end_headers()
                return
            if msg["method"] == "initialize":
                result = {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}}, "serverInfo": {"name": "isolated", "version": "1"}}
            elif msg["method"] == "tools/list":
                result = {"tools": [{"name": "read_document", "inputSchema": {"type": "object"}, "annotations": {"readOnlyHint": True}}, {"name": "write_document", "inputSchema": {"type": "object"}, "annotations": {"readOnlyHint": False}}]}
            else:
                raise AssertionError("Business calls are prohibited")
            body = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    records = []
    original_check = R.run_check
    def observe(*args, **kwargs):
        record = original_check(*args, **kwargs)
        records.append(record)
        return record
    monkeypatch.setattr(R, "run_check", observe)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setattr(O.socket, "getaddrinfo", REAL_DNS)
        stored = svc.store.get(row["id"])
        stored["url"] = f"http://127.0.0.1:{server.server_port}/mcp"
        monkeypatch.setenv("HYD_MCP_OAUTH_PRIVATE_ORIGINS", f"http://127.0.0.1:{server.server_port}")
        svc.store.put(stored)
        assert svc.check(row["id"])["status"] == "connected", records
        entry = R.store_for(repo).servers("hyd")[row["name"]]
        assert entry["hyd"]["gate"]["read_tools"] == ["read_document"]
        assert entry["hyd"]["gate"]["blocked_tools"] == ["write_document"]
        assert methods == ["initialize", "notifications/initialized", "tools/list"]
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("kind,expected", [("redirect", "redirect_rejected"), ("large", "response_too_large"), ("timeout", "endpoint_unavailable")])
def test_transport_bounded_response_redirect_timeout(setup, monkeypatch, kind, expected):
    class Response:
        status = 302 if kind == "redirect" else 200
        def read(self, maximum):
            assert maximum == O.MAX_BODY + 1
            return b"x" * maximum if kind == "large" else b"{}"
        def getheaders(self):
            return []

    class Connection:
        def __init__(self, *args):
            pass
        def request(self, *args, **kwargs):
            if kind == "timeout":
                raise TimeoutError("PRIVATE_UNSAFE_ERROR")
        def getresponse(self):
            return Response()
        def close(self):
            pass

    monkeypatch.setattr(O, "_PinnedHTTPS", Connection)
    with pytest.raises(O.OAuthError) as exc:
        O.Transport({}).request("GET", RESOURCE)
    assert exc.value.code == expected
    assert "PRIVATE_UNSAFE_ERROR" not in str(exc.value)


@pytest.mark.parametrize("field,value,expected", [("resource", "https://wrong.example/mcp", "resource_mismatch"), ("issuer", "https://wrong.example", "issuer_mismatch"), ("code_challenge_methods_supported", ["plain"], "pkce_unsupported")])
def test_metadata_binding_negative(setup, field, value, expected):
    svc, repo, env, fake, now = setup
    original = fake.request
    def request(method, url, data=None, headers=None):
        status, h, body = original(method, url, data, headers)
        if field == "resource" and url.endswith("/resource") or field != "resource" and "well-known" in url:
            body[field] = value
        return status, h, body
    fake.request = request
    row = svc.prepare({"url": RESOURCE, "auth_mode": "oauth"})
    with pytest.raises(O.OAuthError) as exc:
        svc.start(row["id"], "browser")
    assert exc.value.code == expected
    assert not R.store_for(repo).servers("hyd")


def test_refresh_rotation_preserves_gate_and_secret_namespace_resolve(setup):
    svc, repo, env, fake, now = setup
    row, result, state = begin(svc)
    svc.callback(state, "browser", "code")
    stored = svc.store.get(row["id"])
    now[0] += 100
    assert svc.headers(stored) == {"Authorization": "Bearer PRIVATE_ACCESS_TOKEN"}
    assert fake.calls[-1][2]["grant_type"] == "refresh_token"
    assert svc.store.get(row["id"])["tokens"]["expires"] == 1190
    out, missing = S.resolve({"headers": {"Authorization": "${SECRET:HYD_OAUTH_PRIVATE}"}}, {"HYD_OAUTH_PRIVATE": "encrypted"})
    assert missing == ["HYD_OAUTH_PRIVATE"]


def test_prepare_deduplicates_and_observed_auth_failure_revokes(setup, monkeypatch):
    svc, repo, env, fake, now = setup
    row, result, state = begin(svc)
    assert svc.prepare({"url": RESOURCE, "auth_mode": "oauth"})["id"] == row["id"]
    svc.callback(state, "browser", "code")
    monkeypatch.setattr(R, "run_check", lambda *a: check_record())
    svc.check(row["id"])
    entry = R.store_for(repo).servers("hyd")[row["name"]]
    monkeypatch.setattr(O, "Service", lambda *a, **k: svc)
    O.mark_auth_failure(repo, "hyd", row["name"], entry, "missing_scope", env)
    stored = svc.store.get(row["id"])
    assert stored["status"] == "login_required" and stored["reason_code"] == "missing_scope"
    assert "tokens" not in stored
    with pytest.raises(O.OAuthError):
        O.access_headers(repo, "hyd", row["name"], entry, env)


def test_generic_auto_none_oauth_and_api_key_modes(setup, monkeypatch):
    svc, repo, env, fake, now = setup
    monkeypatch.setattr(R, "run_check", lambda *a: check_record())
    out = svc.prepare({"url": RESOURCE})
    assert out["status"] == "connected" and out["auth_mode"] == "auto"
    assert not fake.calls
    svc.cancel(out["id"], True)
    # A different name avoids deduplication with the deliberate disconnected record.
    monkeypatch.setattr(R, "run_check", lambda *a: dict(check_record(False), error_kind="auth"))
    out = svc.prepare({"url": RESOURCE, "name": "oauth-auto"})
    assert out["status"] == "login_required" and out["auth_mode"] == "oauth"
    original = fake.request
    fake.request = lambda method, url, *args: (404, {}, {})
    out = svc.prepare({"url": RESOURCE, "name": "key-only"})
    assert out["status"] == "preparation_required" and out["reason_code"] == "api_key_required"
    fake.request = original
    calls = []
    def checked(spec, timeout):
        calls.append(spec)
        assert spec["headers"] == {"X-API-Key": "PRIVATE_SERVICE_KEY"}
        return check_record()
    monkeypatch.setattr(R, "run_check", checked)
    keyed = svc.prepare({"url": RESOURCE, "name": "key-only", "auth_mode": "api_key", "access_key": "PRIVATE_SERVICE_KEY", "key_header": "X-API-Key", "key_prefix": ""})
    assert keyed["id"] == out["id"] and keyed["status"] == "connected"
    assert "PRIVATE_SERVICE_KEY" not in str(repo._mcp_secrets)
    assert "PRIVATE_SERVICE_KEY" not in json.dumps(svc.listing())
    svc.cancel(keyed["id"], True)
    assert "key_headers" not in svc.store.get(keyed["id"])


def test_invalid_key_is_not_stored_and_unknown_expiry_is_explicit(setup, monkeypatch):
    svc, repo, env, fake, now = setup
    with pytest.raises(O.OAuthError):
        svc.prepare({"url": RESOURCE, "auth_mode": "api_key", "access_key": "key\r\n", "key_header": "Authorization", "key_prefix": "Bearer"})
    assert not svc.store.rows()
    row, result, state = begin(svc)
    original = fake.request
    def request(method, url, data=None, headers=None):
        status, h, body = original(method, url, data, headers)
        if url.endswith("/token"):
            body.pop("expires_in", None)
        return status, h, body
    fake.request = request
    svc.callback(state, "browser", "code")
    stored = svc.store.get(row["id"])
    assert stored["tokens"]["expires"] is None
    now[0] += 100000
    before = len(fake.calls)
    assert svc.headers(stored)["Authorization"] == "Bearer PRIVATE_ACCESS_TOKEN"
    assert len(fake.calls) == before  # Unknown expiry is never invented or scheduled.
    assert S.redact({"result": "xyz"}, [S.OAuthSecret("xyz")])["result"] == S.REDACTED
