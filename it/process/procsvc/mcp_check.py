"""U3 (A2 MCP 부분) — MCP 서버 읽기 전용 클라이언트: 연결 상태 · 도구 목록 · 읽기 전용 도구 시험 호출.

process-gpt-mcp-validator(validator.py)의 절차(세션 열기 → initialize → 도구 적재 → 시간 제한 → 실패 사유)를 따르되
langchain_mcp_adapters 대신 표준 라이브러리만 쓴다(process 컨테이너의 requirements 를 늘리지 않는다).
서버 설정은 읽기만 한다(tenants.mcp — 랩업에서 추가한 서버도 같은 칸). 저장·등록·수정·삭제는 없다.

transport
  stdio            : 명령을 process 컨테이너 안에서 띄워 줄 단위 JSON-RPC. 명령이 이 컨테이너에 없으면 그 사실이 실패 사유다
                     (명령형 서버는 워커 PC 에서 돈다 — it/agent-worker/worker/bridge.py).
  streamable_http  : POST 한 번에 JSON 또는 SSE 로 응답(MCP 2025-03-26+). Mcp-Session-Id 를 되돌려 준다.
  sse              : GET 스트림의 endpoint 이벤트로 POST 주소를 받고, 응답은 스트림으로 온다(MCP 2024-11-05).
  그 밖(websocket …): 명확한 설정 오류.

읽기 전용 판정(read_only_verdict): 서버가 도구에 readOnlyHint=true 를 붙였고(MCP 2025-03-26 ToolAnnotations), 이름이
쓰기·실행을 뜻하지 않을 때만 시험 호출을 허용한다. 표시가 없거나 쓰기로 표시했거나 이름이 쓰기(submit · write · delete …)면
사유와 함께 거부한다. 호출 직전에 서버에서 도구 목록을 다시 받아 판정한다(클라이언트가 보낸 판정은 믿지 않는다).

결과는 사람이 읽는 한국어 사유(error)와 분류(error_kind: config · exec · refused · unreachable · timeout · auth · not_mcp ·
protocol · server · closed · too_large)로 돌려준다. 폴백·빈 성공은 없다: 도구 목록을 받지 못하면 status 는 'failed' 다.
"""
from __future__ import annotations

import http.client
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "hyd-process-mcp-check", "version": "1.0"}
DEFAULT_TIMEOUT = 10.0
MAX_TIMEOUT = 60.0
TRANSPORTS = ("stdio", "streamable_http", "sse")
_TRANSPORT_ALIASES = {"http": "streamable_http", "streamable-http": "streamable_http", "streamablehttp": "streamable_http",
                      "url": "streamable_http", "stdio": "stdio", "sse": "sse", "streamable_http": "streamable_http"}
MASK = "********"
# 설정(env · headers) 이름: OPENAI_API_KEY · NEO4J_PASSWORD · Authorization … — 환경변수 이름의 *KEY 는 거의 비밀이다.
SECRET_KEY_RE = re.compile(r"(pass|pwd|secret|token|key|auth|dsn|credential|cookie|signature)", re.I)
# 도구 입력·결과 안의 칸 이름: 'key'(공급사 키 a·b·c)·'primary_key' 같은 업무 값은 가리지 않고, 비밀을 뜻하는 이름만.
SECRET_FIELD_RE = re.compile(r"(passw|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|authorization|^auth$|dsn|credential|cookie|signature)", re.I)
_URL_PASSWORD_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^\s:/@]+:)([^@\s/]+)(@)")
_KV_PASSWORD_RE = re.compile(r"((?:password|passwd|pwd|secret|token|api[_-]?key)\s*[=:]\s*)(['\"]?)([^\s'\"&;,]+)", re.I)
_BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]{6,}")
MAX_WIRE_BYTES = 2_000_000                       # 서버 응답 한 개의 상한 — 넘으면 too_large 로 끊는다(메모리 A131)
MAX_RESULT_CHARS = 20_000                        # 화면에 돌려주는 결과 글자 수 상한 — 넘으면 잘라 truncated 로 알린다
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 컨테이너 안 서비스는 프록시 없이 직접 간다


class CheckError(Exception):
    """사람이 읽는 실패 사유 + 분류."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind, self.message = kind, message


# ---------------------------------------------------------------- 설정 정규화 · 비밀값 가림
def normalize(spec) -> dict:
    """tenants.mcp 의 서버 한 칸을 검사 가능한 형태로 만든다. 잘못된 입력은 ValueError('칸: 사유')."""
    if not isinstance(spec, dict):
        raise ValueError("설정은 객체({command…} 또는 {url…})여야 합니다")
    transport = spec.get("transport") or spec.get("type")
    if transport is None:
        transport = "stdio" if spec.get("command") else ("streamable_http" if spec.get("url") else None)
    if transport is None:
        raise ValueError("transport: command(명령형) 또는 url(HTTP) 가운데 하나는 있어야 합니다")
    key = str(transport).strip().lower()
    if key not in _TRANSPORT_ALIASES:
        raise ValueError(f"transport: '{transport}' 는 지원하지 않습니다 (가능: stdio · streamable_http · sse)")
    transport = _TRANSPORT_ALIASES[key]
    out: dict = {"transport": transport}
    if transport == "stdio":
        command = spec.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command: 명령형(stdio) 서버는 실행할 명령이 필요합니다")
        out["command"] = command.strip()
        args = spec.get("args") or []
        if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
            raise ValueError("args: 문자열 목록이어야 합니다")
        out["args"] = list(args)
        out["env"] = _str_map(spec.get("env"), "env")
        if spec.get("cwd"):
            out["cwd"] = str(spec["cwd"])
    else:
        url = spec.get("url") or spec.get("serverUrl")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url: HTTP 서버는 주소가 필요합니다")
        url = url.strip()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("url: http:// 또는 https:// 로 시작하는 주소여야 합니다 (예: http://dmn-mcp:8198/mcp)")
        out["url"] = url
        out["type"] = "url"                                     # bridge.py 가 읽는 제품 형태를 유지한다
        out["headers"] = _str_map(spec.get("headers"), "headers")
    return out


def _str_map(value, field: str) -> dict:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ValueError(f"{field}: 이름→값 객체여야 합니다")
    return {k: ("" if v is None else str(v)) for k, v in value.items()}


def is_secret_key(key: str) -> bool:
    return bool(SECRET_KEY_RE.search(key or ""))


def mask_url(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    if not p.password:
        return url
    host = p.hostname or ""
    if p.port:
        host += f":{p.port}"
    netloc = f"{p.username}:{MASK}@{host}" if p.username else f"{MASK}@{host}"
    return urllib.parse.urlunsplit((p.scheme, netloc, p.path, p.query, p.fragment))


def masked(spec: dict) -> dict:
    """응답용 사본: env·headers 의 비밀스러운 이름은 값을 가리고, url 의 비밀번호도 가린다."""
    out = json.loads(json.dumps(spec))
    for field in ("env", "headers"):
        if isinstance(out.get(field), dict):
            out[field] = {k: (MASK if is_secret_key(k) and v != "" else v) for k, v in out[field].items()}
    if isinstance(out.get("url"), str):
        out["url"] = mask_url(out["url"])
    return out


def mask_text(text: str) -> str:
    """문자열 안의 비밀: 주소의 비밀번호(postgresql://u:pw@h), password=… 꼴, Bearer 토큰."""
    text = _URL_PASSWORD_RE.sub(lambda m: m.group(1) + MASK + m.group(3), text)
    text = _KV_PASSWORD_RE.sub(lambda m: m.group(1) + m.group(2) + MASK, text)
    return _BEARER_RE.sub(lambda m: m.group(1) + MASK, text)


def mask_value(value, _depth: int = 0):
    """도구 입력·결과(사전 · 목록 · 문자열)의 비밀값을 가린 사본. 비밀 이름의 칸은 값 통째로, 문자열은 mask_text."""
    if _depth > 40:
        return value
    if isinstance(value, dict):
        return {k: (MASK if isinstance(k, str) and SECRET_FIELD_RE.search(k) and isinstance(v, (str, int, float)) and v not in ("", None)
                    else mask_value(v, _depth + 1)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_value(v, _depth + 1) for v in value]
    if isinstance(value, str):
        return mask_text(value)
    return value


# ---------------------------------------------------------------- JSON-RPC 공통
def _parse_message(raw, *, where: str) -> dict:
    try:
        msg = json.loads(raw) if not isinstance(raw, (dict, list)) else raw
    except (TypeError, ValueError):
        snippet = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        raise CheckError("protocol", f"프로토콜 오류 — {where}이(가) MCP(JSON-RPC 2.0) 형식이 아닙니다: {snippet.strip()[:120]!r}")
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        raise CheckError("protocol", f"프로토콜 오류 — {where}에 jsonrpc 2.0 봉투가 없습니다: {json.dumps(msg, ensure_ascii=False)[:120]}")
    return msg


def _result_of(msg: dict, method: str) -> dict:
    if "error" in msg:
        err = msg["error"] if isinstance(msg["error"], dict) else {"message": str(msg["error"])}
        raise CheckError("server", f"서버가 {method} 요청에 오류를 돌려줬습니다 (코드 {err.get('code', '?')}): {err.get('message', '')}".strip())
    result = msg.get("result")
    if not isinstance(result, dict):
        raise CheckError("protocol", f"프로토콜 오류 — {method} 응답에 result 객체가 없습니다")
    return result


def _iter_sse(lines) -> "iter[tuple[str, str]]":
    """(event, data) 쌍. lines 는 bytes 줄 반복자."""
    event, data = "message", []
    for line in lines:
        line = line.decode("utf-8", "replace").rstrip("\r\n")
        if line == "":
            if data:
                yield event, "\n".join(data)
            event, data = "message", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        yield event, "\n".join(data)


class _Session:
    """transport 에 독립적인 요청 순서. transport 는 send(payload, deadline) 와 recv(deadline) 를 갖는다."""

    def __init__(self, transport, timeout: float):
        self.t, self.timeout, self._id = transport, timeout, 0
        self.deadline = time.monotonic() + timeout

    def remaining(self) -> float:
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise CheckError("timeout", f"{self.timeout:g}초 안에 응답하지 않았습니다 (시간 초과). 서버가 느리거나 방화벽이 막고 있을 수 있습니다")
        return left

    def request(self, method: str, params: dict) -> dict:
        self._id += 1
        rid = self._id
        self.t.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}, self)
        while True:
            msg = self.t.recv(self)
            if msg.get("id") == rid and ("result" in msg or "error" in msg):
                return _result_of(msg, method)
            # 서버가 먼저 보내는 알림·요청(logging, ping 등)은 건너뛴다

    def notify(self, method: str, params: dict) -> None:
        self.t.send({"jsonrpc": "2.0", "method": method, "params": params}, self)


def _initialize(session: _Session) -> dict:
    init = session.request("initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO})
    session.t.on_initialized(init)
    session.notify("notifications/initialized", {})
    info = init.get("serverInfo") if isinstance(init.get("serverInfo"), dict) else {}
    return {"server_info": {"name": info.get("name"), "version": info.get("version")}, "protocol_version": init.get("protocolVersion")}


def _list_tools(session: _Session) -> list[dict]:
    tools, cursor = [], None
    for _ in range(50):                                          # 페이지 50장이면 도구 수천 개 — 그 이상은 설정 오류로 본다
        res = session.request("tools/list", {"cursor": cursor} if cursor else {})
        page = res.get("tools")
        if not isinstance(page, list):
            raise CheckError("protocol", "프로토콜 오류 — tools/list 응답에 tools 목록이 없습니다")
        for tool in page:
            if not isinstance(tool, dict) or not tool.get("name"):
                raise CheckError("protocol", "프로토콜 오류 — 이름 없는 도구가 있습니다")
            schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {"type": "object", "properties": {}}
            notes = tool.get("annotations") if isinstance(tool.get("annotations"), dict) else {}
            entry = {"name": str(tool["name"]), "title": str(tool.get("title") or notes.get("title") or "").strip() or None,
                     "description": str(tool.get("description") or "").strip(), "input_schema": schema,
                     "annotations": {k: notes[k] for k in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint") if k in notes}}
            ok, reason = read_only_verdict(entry)
            entry.update(callable=ok, refuse_reason=reason)
            tools.append(entry)
        cursor = res.get("nextCursor")
        if not cursor:
            break
    else:
        raise CheckError("protocol", "프로토콜 오류 — tools/list 의 nextCursor 가 끝나지 않습니다")
    return tools


# ---------------------------------------------------------------- 읽기 전용 판정
_WRITE_WORDS = ("write", "submit", "create", "insert", "update", "upsert", "delete", "remove", "drop", "truncate", "alter", "set",
                "patch", "send", "exec", "execute", "run", "command", "cmd", "approve", "reject", "start", "stop", "restart",
                "reset", "publish", "apply", "commit", "dispatch", "save", "mutate", "modify", "kill")


def _words(name: str) -> list[str]:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)          # createOrder → create_Order
    return [w for w in re.split(r"[^A-Za-z0-9]+", snake.lower()) if w]


def read_only_verdict(tool: dict) -> tuple[bool, str | None]:
    """(시험 호출 허용?, 거부 사유). 서버의 readOnlyHint=true 와 '쓰기가 아닌 이름'이 둘 다 맞아야 허용한다."""
    name = str(tool.get("name") or "")
    notes = tool.get("annotations") or {}
    hit = next((w for w in _words(name) if w in _WRITE_WORDS), None)
    if notes.get("destructiveHint") is True and notes.get("readOnlyHint") is not True:
        return False, "서버가 이 도구를 되돌릴 수 없는 쓰기(destructiveHint)로 표시했습니다 — 포털에서는 읽기 전용 도구만 써 볼 수 있습니다"
    if notes.get("readOnlyHint") is False:
        return False, "서버가 이 도구를 쓰기 도구(readOnlyHint=false)로 표시했습니다 — 처리 건 안에서 사람 승인 뒤에만 쓰입니다"
    if hit:
        return False, (f"이름의 '{hit}' 가 쓰기·실행을 뜻합니다 — 서버가 읽기 전용으로 표시했더라도 포털에서는 부르지 않습니다"
                       if notes.get("readOnlyHint") is True else f"이름의 '{hit}' 가 쓰기·실행을 뜻합니다 — 포털에서는 읽기 전용 도구만 써 볼 수 있습니다")
    if notes.get("readOnlyHint") is not True:
        return False, ("서버가 이 도구를 읽기 전용(readOnlyHint)으로 표시하지 않았습니다 — 서버 코드에서 도구에 "
                       "readOnlyHint=true 표시를 붙이면 써 볼 수 있습니다")
    return True, None


# ---------------------------------------------------------------- 도구 결과 정리
def shape_result(result: dict, max_chars: int = MAX_RESULT_CHARS) -> dict:
    """tools/call result → 화면용: 비밀값 가림, 글자 수 상한(넘으면 잘라 truncated=true, 원래 크기 size_chars)."""
    blocks = result.get("content") if isinstance(result.get("content"), list) else []
    parts = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            parts.append(str(block.get("text") or ""))
        elif kind in ("image", "audio"):
            parts.append(f"[{'그림' if kind == 'image' else '소리'} {block.get('mimeType') or ''} — 화면에 싣지 않음]")
        elif kind == "resource":
            res = block.get("resource") or {}
            parts.append(str(res.get("text") or f"[자료 {res.get('uri') or ''}]"))
        else:
            parts.append(f"[{kind or '알 수 없는'} 내용]")
    structured = result.get("structuredContent")
    text = "\n".join(parts)
    parsed = None
    if structured is not None:
        parsed = structured
    else:
        try:
            parsed = json.loads(text) if text.strip().startswith(("{", "[")) else None
        except ValueError:
            parsed = None
    pretty = json.dumps(mask_value(parsed), ensure_ascii=False, indent=2) if parsed is not None else mask_text(text)
    size = len(pretty)
    truncated = size > max_chars
    return {"is_error": bool(result.get("isError")), "text": pretty[:max_chars] + ("\n… (잘림)" if truncated else ""),
            "json": parsed is not None, "size_chars": size, "truncated": truncated, "limit_chars": max_chars}


# ---------------------------------------------------------------- stdio
class _Stdio:
    def __init__(self, spec: dict):
        self.command = spec["command"]
        exe = shutil.which(self.command)
        if exe is None:
            raise CheckError("exec", f"'{self.command}' 명령을 이 서비스(process 컨테이너)에서 찾을 수 없습니다. 명령형(stdio) 서버는 "
                                     "워커가 도는 PC 에서 실행되므로, 그 PC 에 설치돼 있는지는 워커 쪽에서 확인해야 합니다")
        env = dict(os.environ)
        env.update(spec.get("env") or {})
        try:
            self.proc = subprocess.Popen([exe, *spec.get("args", [])], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, env=env, cwd=spec.get("cwd") or None)
        except OSError as e:
            raise CheckError("exec", f"'{self.command}' 를 실행하지 못했습니다: {e.strerror or e}")
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()
        self.stderr_tail: list[str] = []
        threading.Thread(target=self._stderr, daemon=True).start()

    def _reader(self):
        for line in self.proc.stdout:
            if line.strip():
                self.q.put(line)
        self.q.put(None)

    def _stderr(self):
        for line in self.proc.stderr:
            self.stderr_tail.append(line.decode("utf-8", "replace").rstrip())
            del self.stderr_tail[:-8]

    def send(self, payload: dict, session: _Session):
        session.remaining()
        try:
            self.proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            raise self._exited()

    def recv(self, session: _Session) -> dict:
        try:
            line = self.q.get(timeout=session.remaining())
        except queue.Empty:
            raise CheckError("timeout", f"{session.timeout:g}초 안에 '{self.command}' 가 응답하지 않았습니다 (시간 초과)")
        if line is None:
            raise self._exited()
        if len(line) > MAX_WIRE_BYTES:
            raise _too_large()
        return _parse_message(line, where=f"'{self.command}' 의 출력")

    def _exited(self) -> CheckError:
        time.sleep(0.05)
        code = self.proc.poll()
        tail = " | ".join(self.stderr_tail[-3:])
        return CheckError("closed", f"'{self.command}' 서버 프로세스가 종료됐습니다" + (f" (종료 코드 {code})" if code is not None else "")
                          + (f": {tail[:300]}" if tail else ". 명령·인자·환경변수를 확인하세요"))

    def on_initialized(self, init: dict):
        pass

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def _too_large() -> CheckError:
    return CheckError("too_large", f"서버 응답 하나가 {MAX_WIRE_BYTES // 1_000_000} MB 를 넘어 읽기를 멈췄습니다 — 입력을 좁혀(기간 · 행 수) 다시 부르세요")


# ---------------------------------------------------------------- HTTP 공통
def _http_error(exc: Exception, url: str, timeout: float) -> CheckError:
    p = urllib.parse.urlsplit(url)
    host = f"{p.hostname}:{p.port or (443 if p.scheme == 'https' else 80)}"
    reason = getattr(exc, "reason", exc)
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        if code in (401, 403):
            return CheckError("auth", f"인증 실패 (HTTP {code}) — 접속 헤더의 토큰·키를 확인하세요")
        if code in (404, 405, 406, 415):
            return CheckError("not_mcp", f"MCP 끝점이 아닙니다 (HTTP {code}) — 주소 경로(보통 /mcp 또는 /sse)를 확인하세요")
        return CheckError("server", f"서버 오류 (HTTP {code}) — 서버 로그를 확인하세요")
    if isinstance(reason, (socket.timeout, TimeoutError)) or isinstance(exc, (socket.timeout, TimeoutError)):
        return CheckError("timeout", f"{timeout:g}초 안에 {host} 가 응답하지 않았습니다 (시간 초과). 서버가 느리거나 방화벽이 막고 있을 수 있습니다")
    if isinstance(reason, ConnectionRefusedError) or "refused" in str(reason).lower():
        return CheckError("refused", f"연결 거부 — {host} 에서 응답하는 서버가 없습니다. 서버가 켜져 있는지, 주소·포트가 맞는지 확인하세요")
    if isinstance(reason, socket.gaierror) or "name or service not known" in str(reason).lower() or "nodename" in str(reason).lower() \
            or "getaddrinfo" in str(reason).lower() or "temporary failure in name resolution" in str(reason).lower():
        return CheckError("unreachable", f"주소를 찾을 수 없습니다 — '{p.hostname}'. 컨테이너 서비스 이름(예: dmn-mcp)이나 호스트 이름을 확인하세요")
    if isinstance(reason, (ConnectionResetError, http.client.RemoteDisconnected, http.client.BadStatusLine)):
        return CheckError("closed", f"{host} 가 연결을 끊었습니다 — MCP 서버가 아니거나 TLS(https) 설정이 다를 수 있습니다")
    return CheckError("unreachable", f"{host} 에 연결하지 못했습니다: {str(reason)[:160]}")


def _open(req: urllib.request.Request, timeout: float):
    return _NO_PROXY.open(req, timeout=max(0.05, timeout))


class _StreamableHttp:
    def __init__(self, spec: dict):
        self.url, self.headers, self.session_id, self.protocol = spec["url"], dict(spec.get("headers") or {}), None, None
        self.pending: list[dict] = []

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **self.headers}
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        if self.protocol:
            h["MCP-Protocol-Version"] = self.protocol
        return h

    def send(self, payload: dict, session: _Session):
        left = session.remaining()
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers=self._headers(), method="POST")
        try:
            with _open(req, left) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if "id" not in payload:                              # 알림: 202/204, 본문 없음
                    return
                if ctype == "application/json":
                    body = resp.read(MAX_WIRE_BYTES + 1)
                    if len(body) > MAX_WIRE_BYTES:
                        raise _too_large()
                    self.pending.append(_parse_message(body, where="HTTP 응답"))
                elif ctype == "text/event-stream":
                    for event, data in _iter_sse(resp):
                        if len(data) > MAX_WIRE_BYTES:
                            raise _too_large()
                        if event != "message":
                            continue
                        msg = _parse_message(data, where="SSE 이벤트")
                        self.pending.append(msg)
                        if msg.get("id") == payload["id"] and ("result" in msg or "error" in msg):
                            break
                else:
                    body = resp.read(200)
                    raise CheckError("not_mcp", f"MCP 끝점이 아닙니다 — 응답이 JSON 도 SSE 도 아닙니다 (Content-Type {ctype or '없음'}, HTTP {resp.status}): "
                                                f"{body.decode('utf-8', 'replace').strip()[:80]!r}")
        except CheckError:
            raise
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            raise _http_error(e, self.url, session.timeout)

    def recv(self, session: _Session) -> dict:
        if not self.pending:
            raise CheckError("protocol", "프로토콜 오류 — 서버가 요청에 응답 메시지를 보내지 않았습니다")
        return self.pending.pop(0)

    def on_initialized(self, init: dict):
        self.protocol = init.get("protocolVersion") or PROTOCOL_VERSION

    def close(self):
        if not self.session_id:
            return
        try:                                                     # 스펙: 클라이언트는 세션을 DELETE 로 끝내는 것이 좋다(서버가 405 여도 무방)
            with _open(urllib.request.Request(self.url, headers=self._headers(), method="DELETE"), 2.0):
                pass
        except Exception:  # noqa: BLE001
            pass


class _Sse:
    """MCP 2024-11-05 HTTP+SSE: GET 스트림 → endpoint 이벤트 → POST 주소; 응답은 스트림의 message 이벤트."""

    def __init__(self, spec: dict, timeout: float):
        self.url, self.headers = spec["url"], dict(spec.get("headers") or {})
        self.q: queue.Queue = queue.Queue()
        self.endpoint: str | None = None
        self.resp = None
        req = urllib.request.Request(self.url, headers={"Accept": "text/event-stream", **self.headers}, method="GET")
        try:
            self.resp = _open(req, timeout)
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            raise _http_error(e, self.url, timeout)
        ctype = (self.resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "text/event-stream":
            raise CheckError("not_mcp", f"MCP(SSE) 끝점이 아닙니다 — GET 응답이 text/event-stream 이 아닙니다 (Content-Type {ctype or '없음'})")
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            for event, data in _iter_sse(self.resp):
                self.q.put((event, data))
        except Exception as e:  # noqa: BLE001
            self.q.put(("__error__", str(e)))
        self.q.put(None)

    def _next(self, session: _Session):
        try:
            item = self.q.get(timeout=session.remaining())
        except queue.Empty:
            raise CheckError("timeout", f"{session.timeout:g}초 안에 SSE 스트림으로 응답이 오지 않았습니다 (시간 초과)")
        if item is None:
            raise CheckError("closed", "서버가 SSE 스트림을 닫았습니다 — MCP 서버가 아니거나 세션을 거부했습니다")
        if item[0] == "__error__":
            raise CheckError("closed", f"SSE 스트림 읽기 실패: {item[1][:160]}")
        return item

    def send(self, payload: dict, session: _Session):
        while self.endpoint is None:
            event, data = self._next(session)
            if event == "endpoint":
                self.endpoint = urllib.parse.urljoin(self.url, data.strip())
        req = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json", **self.headers}, method="POST")
        try:
            with _open(req, session.remaining()) as resp:
                resp.read()
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            raise _http_error(e, self.endpoint, session.timeout)

    def recv(self, session: _Session) -> dict:
        while True:
            event, data = self._next(session)
            if event == "message":
                if len(data) > MAX_WIRE_BYTES:
                    raise _too_large()
                return _parse_message(data, where="SSE 이벤트")

    def on_initialized(self, init: dict):
        pass

    def close(self):
        try:
            self.resp.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- 진입점
def _now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _clamp(timeout) -> float:
    return float(min(max(timeout or DEFAULT_TIMEOUT, 0.1), MAX_TIMEOUT))


def _with_session(spec: dict, timeout: float, work) -> dict:
    """연결 → initialize → work(session, init) . 예외를 던지지 않고 status · error 로 답한다."""
    started = time.monotonic()
    out = {"status": "failed", "error": None, "error_kind": None, "server_info": None, "protocol_version": None,
           "checked_at": _now_z(), "elapsed_ms": 0, "transport": spec.get("transport")}
    transport = None
    try:
        kind = spec["transport"]
        if kind == "stdio":
            transport = _Stdio(spec)
        elif kind == "streamable_http":
            transport = _StreamableHttp(spec)
        elif kind == "sse":
            transport = _Sse(spec, timeout)
        else:
            raise CheckError("config", f"transport '{kind}' 는 이 서비스에서 연결할 수 없습니다 (가능: stdio · streamable_http · sse)")
        session = _Session(transport, timeout)
        init = _initialize(session)
        out.update(init)
        done = work(session)
        out.update(done)
        if "status" not in done:
            out["status"] = "ok"
    except CheckError as e:
        out.update(status="failed", error=e.message, error_kind=e.kind)
    except Exception as e:  # noqa: BLE001 — 분류 못 한 실패도 사유는 남긴다
        out.update(status="failed", error=f"예상하지 못한 오류: {type(e).__name__}: {str(e)[:160]}", error_kind="protocol")
    finally:
        if transport is not None:
            try:
                transport.close()
            except Exception:  # noqa: BLE001
                pass
    out["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    return out


def check(spec: dict, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """정규화된 설정으로 실제 연결 → 도구 목록(이름 · 설명 · 입력 형식 · 읽기 전용 판정). 실패면 tools=[] 와 사유."""
    out = _with_session(spec, _clamp(timeout), lambda session: {"tools": _list_tools(session)})
    out.setdefault("tools", [])
    return out


def call(spec: dict, tool: str, arguments: dict, timeout: float = DEFAULT_TIMEOUT, *, max_chars: int = MAX_RESULT_CHARS) -> dict:
    """읽기 전용 도구 하나를 실제로 부른다. 호출 직전 같은 세션에서 tools/list 를 다시 받아 판정한다.
    status: ok(결과 있음 — 도구가 오류를 돌려줘도 result.is_error 로 보인다) · refused(쓰기·표시 없음 · 없는 도구) · failed(연결·프로토콜)."""
    if not isinstance(arguments, dict):
        return {"status": "refused", "error": "입력은 이름→값 객체여야 합니다", "error_kind": "input", "result": None, "tool": tool}

    def work(session):
        tools = {t["name"]: t for t in _list_tools(session)}
        meta = tools.get(tool)
        if meta is None:
            return {"status": "refused", "error": f"서버에 '{tool}' 도구가 없습니다 (도구 목록을 다시 읽으세요)", "error_kind": "no_tool", "result": None}
        if not meta["callable"]:
            return {"status": "refused", "error": meta["refuse_reason"], "error_kind": "not_read_only", "result": None}
        res = session.request("tools/call", {"name": tool, "arguments": arguments})
        return {"status": "ok", "result": shape_result(res, max_chars)}

    out = _with_session(spec, _clamp(timeout), work)
    out["tool"] = tool
    out.setdefault("result", None)
    return out
