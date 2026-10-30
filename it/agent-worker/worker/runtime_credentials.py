"""로그인 연결(OAuth) MCP 서버의 실행 머리글을 process 에서 그 점유에 묶어 받는다 — 워커는 암호화 키를 쥐지 않는다(PBL 단계 기능)."""
import json
import urllib.error
import urllib.request

from . import bridge
from .course_access import RuntimeConnectionError, _NoRedirect, process_base, read_key


def attach(config, row, tenant_id, *, process_url, key_file):
    servers = (config or {}).get("mcpServers") or {}
    requested = {name: bridge.config_fingerprint(entry) for name, entry in servers.items()
                 if isinstance(entry, dict) and (entry.get("hyd") or {}).get("oauth_connection")}
    if not requested:
        return config
    url = process_base(process_url)
    key = read_key(key_file)
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

