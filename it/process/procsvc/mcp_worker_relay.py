"""Claim-bound, read-only Streamable HTTP relay with credentials resolved per request."""
import json
import threading
import time

from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

from . import mcp_oauth, mcp_secrets, worker_credentials

MAX_BODY = 8_000_000
_sessions = {}
_session_lock = threading.Lock()
_FORWARDED = {"mcp-session-id", "mcp-protocol-version", "last-event-id"}


def _session(binding, sid, *, register=False):
    if not sid:
        return
    if len(sid) > 512 or "\r" in sid or "\n" in sid:
        raise HTTPException(422, "도구 연결 세션 값이 올바르지 않습니다")
    key = (binding["name"], binding["fingerprint"], sid)
    with _session_lock:
        for old in [k for k, v in _sessions.items() if v[1] <= time.time()]:
            del _sessions[old]
        owner = _sessions.get(key)
        if owner and (owner[0] != binding["nonce"] or owner[2]) or not owner and not register:
            raise HTTPException(403, "이 실행 단계에 속하지 않은 도구 연결 세션입니다")
        if register:
            if len(_sessions) >= 10_000 and not owner:
                raise HTTPException(503, "실행 연결 세션이 가득 찼습니다")
            _sessions[key] = (binding["nonce"], binding["expires"], False)


def _request_body(raw, entry):
    if len(raw) > MAX_BODY:
        raise HTTPException(413, "도구 요청이 허용 크기를 초과했습니다")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        raise HTTPException(422, "도구 요청은 올바른 JSON이어야 합니다") from None
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        raise HTTPException(422, "도구 요청은 단일 JSON-RPC 메시지여야 합니다")
    method = body.get("method")
    if method == "tools/call":
        params = body.get("params")
        name = params.get("name") if isinstance(params, dict) else None
        gate = entry["hyd"]["gate"]
        if name not in gate["read_tools"] or name in (gate.get("blocked_tools") or []):
            raise HTTPException(403, "승인 전 에이전트는 연결 검사에서 확인한 읽기 도구만 사용할 수 있습니다")
    elif method not in {"initialize", "ping", "tools/list", "notifications/initialized", "notifications/cancelled"}:
        raise HTTPException(403, "이 도구 요청은 승인 전 읽기 실행에서 허용하지 않습니다")
    return body


def forward(runtime, name, authorization, method, incoming_headers, raw=b"", *, transport=None):
    binding, entry = worker_credentials.authorize_relay(runtime, name, authorization)
    if method == "GET":
        raise HTTPException(405, "별도 GET 이벤트 스트림은 지원하지 않습니다. POST 응답 스트림을 사용하세요")
    if method not in {"POST", "DELETE"}:
        raise HTTPException(405, "지원하지 않는 도구 연결 요청입니다")
    incoming = {k.lower(): v for k, v in incoming_headers.items()}
    _session(binding, incoming.get("mcp-session-id"))
    if method == "POST":
        payload = _request_body(raw, entry)
    elif not incoming.get("mcp-session-id"):
        raise HTTPException(422, "끝낼 도구 연결 세션이 없습니다")
    try:
        spec, used = mcp_secrets.runtime_spec(runtime.repo, runtime.tenant_id, name, entry)
    except mcp_secrets.SecretError as exc:
        raise HTTPException(exc.status, exc.reason) from None
    headers = {k: v for k, v in incoming.items() if k in _FORWARDED}
    headers.update({"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})
    headers.update(spec.get("headers") or {})
    try:
        conn, response = (transport or mcp_oauth.Transport()).open(method, spec["url"], raw if method == "POST" else None,
                                                                 headers, timeout=30)
    except mcp_oauth.OAuthError as exc:
        raise HTTPException(exc.status, exc.reason) from None
    except Exception:
        raise HTTPException(502, "도구 연결 서버에 요청을 전달하지 못했습니다") from None
    try:
        if response.status in (401, 403):
            mcp_oauth.mark_auth_failure(runtime.repo, runtime.tenant_id, name, entry,
                                       "missing_scope" if response.status == 403 else "login_required")
            raise HTTPException(response.status, "외부 계정 연결 또는 권한을 다시 확인하세요. 요청을 재실행하지 않았습니다")
        if 300 <= response.status < 400:
            raise HTTPException(502, "도구 서버의 다른 주소 이동을 허용하지 않습니다")
        if response.status >= 400:
            raise HTTPException(response.status, "도구 연결 서버가 요청을 처리하지 못했습니다. 요청을 재실행하지 않았습니다")
        out = {k.lower(): v for k, v in response.getheaders()}
        sid = out.get("mcp-session-id")
        _session(binding, sid, register=True)
        if method == "DELETE":
            with _session_lock:
                session_key = (binding["name"], binding["fingerprint"], incoming["mcp-session-id"])
                _sessions[session_key] = (binding["nonce"], binding["expires"], True)
        safe_headers = {k: v for k, v in out.items() if k in _FORWARDED}
        safe_headers["Cache-Control"] = "no-store"
        secrets = used + [authorization, authorization.removeprefix("HydRuntime ")]
        safe_headers = mcp_secrets.redact(safe_headers, secrets)
        content_type = out.get("content-type", "").split(";")[0].strip().lower()
        if content_type == "text/event-stream":
            def frames():
                deadline = time.monotonic() + 60
                def stream_error(message):
                    error = {"jsonrpc": "2.0", "id": payload.get("id"),
                             "error": {"code": -32000, "message": message}}
                    return ("event: message\ndata: " + json.dumps(error, ensure_ascii=False) + "\n\n").encode()
                try:
                    block = bytearray()
                    while time.monotonic() < deadline:
                        line = response.readline(MAX_BODY + 1)
                        if not line:
                            if block:
                                yield mcp_secrets.redact(block.decode("utf-8"), secrets).encode()
                            return
                        block.extend(line)
                        if len(block) > MAX_BODY:
                            yield stream_error("도구 응답이 허용 크기를 초과했습니다")
                            return
                        if line in (b"\n", b"\r\n"):
                            yield mcp_secrets.redact(block.decode("utf-8"), secrets).encode()
                            block.clear()
                    yield stream_error("도구 응답 스트림의 대기 시간이 만료되었습니다")
                except Exception:
                    yield stream_error("도구 응답 스트림을 끝까지 읽지 못했습니다")
                finally:
                    conn.close()
            return StreamingResponse(frames(), status_code=response.status, media_type=content_type, headers=safe_headers,
                                     background=BackgroundTask(conn.close))
        value = response.read(MAX_BODY + 1)
        if len(value) > MAX_BODY:
            raise HTTPException(502, "도구 응답이 허용 크기를 초과했습니다")
        if value and content_type != "application/json":
            raise HTTPException(502, "도구 응답 형식을 확인할 수 없습니다")
        return Response(mcp_secrets.redact(value.decode("utf-8"), secrets), status_code=response.status,
                        media_type=content_type or None, headers=safe_headers)
    except Exception:
        conn.close()
        raise
    finally:
        if 'content_type' not in locals() or content_type != "text/event-stream":
            conn.close()
