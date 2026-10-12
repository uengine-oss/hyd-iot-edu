"""Obtain fresh OAuth headers from process; the worker never holds its encryption key."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import bridge


class RuntimeConnectionError(RuntimeError):
    pass


def attach(config, row, tenant_id):
    servers = (config or {}).get("mcpServers") or {}
    requested = {name: bridge.config_fingerprint(entry) for name, entry in servers.items()
                 if isinstance(entry, dict) and (entry.get("hyd") or {}).get("oauth_connection")}
    if not requested:
        return config
    url = os.getenv("PROCESS_URL", "http://127.0.0.1:8080").rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname or \
            parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1", "process"}):
        raise RuntimeConnectionError("로그인 연결의 실행 주소는 HTTPS 또는 로컬 교육 서비스여야 합니다")
    default = (Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "HYD" / "mcp" / "worker-runtime.key"
               if os.name == "nt" else Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "hyd" / "mcp" / "worker-runtime.key")
    try:
        key = Path(os.getenv("HYD_WORKER_RUNTIME_KEY_FILE", str(default))).read_text(encoding="utf-8").strip()
    except OSError:
        raise RuntimeConnectionError("실행 연결 인증 파일이 준비되지 않았습니다. 연결 설정을 확인하세요") from None
    if len(key) < 32:
        raise RuntimeConnectionError("실행 연결 인증 파일이 올바르지 않습니다")
    body = {"tenant_id": tenant_id, "todo_id": row["id"], "consumer": row.get("consumer"), "servers": requested}
    request = urllib.request.Request(url + "/internal/worker/mcp-runtime", data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    try:
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(request, timeout=30) as response:
            raw = response.read(200_001)
        if len(raw) > 200_000:
            raise ValueError("oversize")
        reply = json.loads(raw)
    except urllib.error.HTTPError as exc:
        # Backend reasons are controlled and contain no provider body/token; no arbitrary HTTP text is logged.
        if exc.code == 401:
            raise RuntimeConnectionError("로그인 연결이 만료되었거나 사용할 수 없습니다. 다시 연결을 확인하세요") from None
        if exc.code == 422:
            raise RuntimeConnectionError("실행 연결 설정을 확인하세요. 기존 SSE 로그인 연결은 지원하지 않습니다") from None
        if exc.code == 503:
            raise RuntimeConnectionError("로그인 연결의 실행 인증 설정이 준비되지 않았습니다") from None
        raise RuntimeConnectionError("로그인 연결의 실행 인증을 확인하지 못했습니다. 다시 연결하거나 연결 상태를 확인하세요") from None
    except Exception:
        raise RuntimeConnectionError("로그인 연결의 실행 서비스를 읽지 못했습니다. 연결 상태를 확인하세요") from None
    if not isinstance(reply, dict) or any(reply.get(k) != body[k] for k in ("tenant_id", "todo_id", "consumer")):
        raise RuntimeConnectionError("실행 연결 응답의 담당 단계가 일치하지 않습니다")
    held = reply.get("servers")
    if not isinstance(held, dict) or set(held) != set(requested):
        raise RuntimeConnectionError("실행 연결 응답의 서버 목록이 일치하지 않습니다")
    for name, entry in held.items():
        headers = entry.get("headers") if isinstance(entry, dict) else None
        if not isinstance(entry, dict) or entry.get("fingerprint") != requested[name] or not isinstance(headers, dict) or not headers or \
                any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in headers.items()):
            raise RuntimeConnectionError("실행 연결 응답의 설정이나 자격증명이 올바르지 않습니다")
        if entry.get("path") != "/internal/worker/mcp/" + name:
            raise RuntimeConnectionError("실행 연결 응답의 중계 경로가 일치하지 않습니다")
        entry["url"] = url + entry["path"]
    return dict(config, **{bridge.RUNTIME_KEY: held})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
