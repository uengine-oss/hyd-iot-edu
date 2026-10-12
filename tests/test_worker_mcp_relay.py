import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import instance_mode, mcp_oauth, mcp_registry, procdb
from procsvc import mcp_worker_relay as relay


@pytest.fixture
def live_relay(monkeypatch, tmp_path):
    received, refreshes = [], []
    behavior = {"status": 200, "sse": False}
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *args): pass
        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.path == "/token":
                refreshes.append(raw)
                body = {"access_token": "RELAY_PROVIDER_SECOND_TOKEN", "refresh_token": "ROTATED_REFRESH_TOKEN", "expires_in": 600, "token_type": "Bearer"}
                wire = json.dumps(body).encode()
                ctype, status = "application/json", 200
            else:
                received.append((json.loads(raw), dict(self.headers)))
                body = {"jsonrpc": "2.0", "id": json.loads(raw).get("id"), "result": {"echo": self.headers.get("Authorization")}}
                wire = json.dumps(body).encode()
                ctype, status = "application/json", behavior["status"]
                if behavior["sse"]:
                    wire = b"event: message\ndata: " + wire + b"\n\n"
                    ctype = "text/event-stream"
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Connection", "close")
            if self.path == "/mcp": self.send_header("Mcp-Session-Id", "isolated-session")
            self.send_header("Content-Length", str(len(wire)))
            self.end_headers()
            # Deliberately split a token across TCP writes; the relay must not leak either full body value.
            cut = wire.find(b"PROVIDER") + 4
            self.wfile.write(wire[:cut]); self.wfile.flush()
            self.wfile.write(wire[cut:]); self.wfile.flush()
        def do_DELETE(self):
            received.append(("DELETE", dict(self.headers)))
            self.send_response(204); self.send_header("Content-Length", "0"); self.end_headers()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    key = "ISOLATED_RUNTIME_KEY_NOT_CLI_" * 2
    path = tmp_path / "worker.key"
    path.write_text(key, encoding="utf-8")
    monkeypatch.setenv("HYD_WORKER_RUNTIME_KEY_FILE", str(path))
    monkeypatch.setenv("HYD_MCP_OAUTH_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HYD_MCP_OAUTH_PRIVATE_ORIGINS", origin)
    repo = procdb.MemoryRepo()
    entry = {"url": origin + "/mcp", "type": "url", "transport": "streamable_http", "headers": {},
             "hyd": {"oauth_connection": "isolated-connection"}}
    entry["hyd"]["gate"] = {"fingerprint": mcp_registry.fingerprint(entry), "read_tools": ["list_items"], "blocked_tools": ["delete_items"]}
    repo.upsert_tenant({"id": "hyd", "mcp": {"mcpServers": {"personal": entry}}})
    row = {"id": "isolated-todo", "tenant_id": "hyd", "consumer": "isolated-worker:one",
           "status": "IN_PROGRESS", "draft_status": "STARTED", "lease_until": time.time() + 120}
    repo.workitems[row["id"]] = row
    service = mcp_oauth.Service(repo, "hyd")
    service.store.put({"id": "isolated-connection", "name": "personal", "url": entry["url"], "status": "connected", "auth_mode": "oauth",
                       "tokens": {"access_token": "RELAY_PROVIDER_FIRST_TOKEN", "refresh_token": "ISOLATED_REFRESH_TOKEN", "expires": time.time() + 600},
                       "client": {"client_id": "isolated-client"}, "client_method": "none",
                       "discovery": {"metadata": {"token_endpoint": origin + "/token"}}})
    monkeypatch.setattr(instance_mode, "_runtime", SimpleNamespace(repo=repo, tenant_id="hyd"))
    monkeypatch.setattr(relay, "_sessions", {})
    app = FastAPI()
    instance_mode.mount(app, "instance")
    with TestClient(app) as client:
        request = {"tenant_id": "hyd", "todo_id": row["id"], "consumer": row["consumer"], "servers": {"personal": mcp_registry.fingerprint(entry)}}
        descriptor = client.post("/internal/worker/mcp-runtime", headers={"Authorization": "Bearer " + key}, json=request)
        assert descriptor.status_code == 200, descriptor.text
        spec = descriptor.json()["servers"]["personal"]
        assert key not in descriptor.text and "RELAY_PROVIDER_FIRST_TOKEN" not in descriptor.text
        yield SimpleNamespace(client=client, spec=spec, service=service, row=row, entry=entry,
                              received=received, refreshes=refreshes, behavior=behavior, key=key, request=request)
    server.shutdown(); server.server_close(); thread.join(timeout=3)


def call(fixture, name="list_items", headers=None, request_id=1):
    return fixture.client.post(fixture.spec["path"], headers=dict(fixture.spec["headers"], **(headers or {})),
                               json={"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {"name": name, "arguments": {}}})


def test_actual_http_mid_run_expiry_refreshes_next_request_without_replay(live_relay):
    f = live_relay
    first = call(f)
    assert first.status_code == 200 and first.headers["cache-control"] == "no-store"
    assert "FIRST_TOKEN" not in first.text and "[비밀 값 가림]" in first.text
    row = f.service.store.get("isolated-connection")
    row["tokens"]["expires"] = time.time() - 1
    f.service.store.put(row)
    second = call(f, headers={"Mcp-Session-Id": "isolated-session"}, request_id=2)
    assert second.status_code == 200 and "SECOND_TOKEN" not in second.text
    assert len(f.refreshes) == 1 and b"grant_type=refresh_token" in f.refreshes[0]
    assert len(f.received) == 2
    assert f.received[0][1]["Authorization"] == "Bearer RELAY_PROVIDER_FIRST_TOKEN"
    assert f.received[1][1]["Authorization"] == "Bearer RELAY_PROVIDER_SECOND_TOKEN"
    assert f.key not in str(f.received) and "HydRuntime" not in str(f.received)
    assert f.service.store.get("isolated-connection")["tokens"]["refresh_token"] == "ROTATED_REFRESH_TOKEN"


def test_sse_split_token_is_masked_and_session_delete_is_bound(live_relay):
    f = live_relay
    f.behavior["sse"] = True
    response = call(f)
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    assert "event: message" in response.text and "FIRST_TOKEN" not in response.text
    assert "[비밀 값 가림]" in response.text
    deleted = f.client.delete(f.spec["path"], headers=dict(f.spec["headers"], **{"MCP-Session-ID": "isolated-session"}))
    assert deleted.status_code == 204 and len(f.received) == 2
    closed = call(f, headers={"Mcp-Session-Id": "isolated-session"}, request_id=2)
    assert closed.status_code == 403 and len(f.received) == 2
    get = f.client.get(f.spec["path"], headers=f.spec["headers"])
    assert get.status_code == 405 and len(f.received) == 2


def test_same_provider_session_cannot_cross_job_capabilities(live_relay):
    f = live_relay
    assert call(f).status_code == 200
    # A second broker issuance represents a distinct job capability, even with the same current claim.
    second = f.client.post("/internal/worker/mcp-runtime", headers={"Authorization": "Bearer " + f.key}, json=f.request)
    other = second.json()["servers"]["personal"]
    response = f.client.post(other["path"], headers=dict(other["headers"], **{"Mcp-Session-Id": "isolated-session"}),
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert response.status_code == 403 and len(f.received) == 1


def test_signed_capability_expiry_lifetime_and_server_binding(live_relay):
    import base64
    import hashlib
    import hmac
    f = live_relay
    authorization = f.spec["headers"]["Authorization"]
    encoded, _ = authorization.removeprefix("HydRuntime ").split(".")
    binding = json.loads(base64.urlsafe_b64decode(encoded))
    for expiry in (time.time() - 1, time.time() + 7200):
        altered = dict(binding, expires=expiry)
        encoded_new = base64.urlsafe_b64encode(json.dumps(altered).encode()).decode()
        signature = hmac.new(f.key.encode(), encoded_new.encode(), hashlib.sha256).hexdigest()
        response = f.client.post(f.spec["path"], headers={"Authorization": "HydRuntime " + encoded_new + "." + signature},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert response.status_code == 403
    wrong_server = f.client.post("/internal/worker/mcp/other", headers=f.spec["headers"],
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert wrong_server.status_code == 403 and not f.received


@pytest.mark.parametrize("negative", ["write", "unknown_session", "other_claim", "expired_lease", "gate_changed", "key_rotation"])
def test_current_authority_negative_never_contacts_upstream(live_relay, negative, monkeypatch, tmp_path):
    f = live_relay
    headers, name = {}, "list_items"
    if negative == "write": name = "delete_items"
    elif negative == "unknown_session": headers["Mcp-Session-Id"] = "another-run"
    elif negative == "other_claim": f.row["consumer"] = "another-worker"
    elif negative == "expired_lease": f.row["lease_until"] = time.time() - 1
    elif negative == "gate_changed":
        entry = dict(f.entry, url="https://different.example/mcp")
        mcp_registry.store_for(f.service.repo).replace_server("hyd", "personal", entry)
    else:
        path = tmp_path / "rotated.key"; path.write_text("ROTATED_ISOLATED_KEY_" * 3)
        monkeypatch.setenv("HYD_WORKER_RUNTIME_KEY_FILE", str(path))
    response = call(f, name=name, headers=headers)
    assert response.status_code in (403, 409) and not f.received and not f.refreshes
    assert "RELAY_PROVIDER" not in response.text and f.key not in response.text


def test_upstream_auth_failure_invalidates_connection_without_retry(live_relay):
    f = live_relay
    f.behavior["status"] = 401
    response = call(f)
    assert response.status_code == 401 and len(f.received) == 1
    assert "재실행하지 않았습니다" in response.text and "FIRST_TOKEN" not in response.text
    row = f.service.store.get("isolated-connection")
    assert row["status"] == "login_required" and "tokens" not in row
    again = call(f, request_id=2)
    assert again.status_code == 401 and len(f.received) == 1 and not f.refreshes


def test_oauth_legacy_sse_is_explicitly_refused_not_treated_as_streamable(live_relay):
    f = live_relay
    entry = dict(f.entry, transport="sse")
    entry["hyd"]["gate"]["fingerprint"] = mcp_registry.fingerprint(entry)
    mcp_registry.store_for(f.service.repo).replace_server("hyd", "personal", entry)
    body = dict(f.request, servers={"personal": mcp_registry.fingerprint(entry)})
    response = f.client.post("/internal/worker/mcp-runtime", headers={"Authorization": "Bearer " + f.key}, json=body)
    assert response.status_code == 422 and "기존 SSE" in response.text
    assert not f.received and not f.refreshes
