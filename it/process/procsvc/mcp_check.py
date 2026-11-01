"""U3 (A2 MCP 부분) — MCP 서버 읽기 전용 클라이언트: 연결 상태 · 도구 목록 · 읽기 전용 도구 시험 호출.

process-gpt-mcp-validator(validator.py)의 절차(세션 열기 → initialize → 도구 적재 → 시간 제한 → 실패 사유)를 따르되
langchain_mcp_adapters 대신 표준 라이브러리 transport와 JSON Schema 입력 검증을 쓴다.
서버 설정은 읽기만 한다(tenants.mcp). 저장·등록·수정·삭제는 mcp_registry 가 한다.

transport — 포털 · process 가 연결하는 도구 서버는 HTTP 주소 하나다
  streamable_http  : POST 한 번에 JSON 또는 SSE 로 응답(MCP 2025-03-26+). Mcp-Session-Id 를 되돌려 준다.
  sse              : GET 스트림의 endpoint 이벤트로 POST 주소를 받고, 응답은 스트림으로 온다(MCP 2024-11-05).
  명령형(stdio)    : 받지 않는다(STDIO_REFUSED). process 안에서 남의 명령을 띄우지 않는다 — 명령으로 띄우는 서버는 HTTP 로 띄워
                     그 주소를 등록한다(내 PC 의 도구에서 stdio 로 쓰는 서버는 그 PC 설정에 둔다).
  그 밖(websocket …): 명확한 설정 오류.
읽기 상한: 응답 메시지 하나 MAX_WIRE_BYTES, 시간은 세션 마감(timeout) — 스트림을 읽는 줄마다 두 상한을 함께 본다(_sse_events).

읽기 전용 판정(read_only_verdict): 서버가 도구에 readOnlyHint=true 를 붙였고(MCP 2025-03-26 ToolAnnotations), 이름이
쓰기·실행을 뜻하지 않을 때만 시험 호출을 허용한다. 표시가 없거나 쓰기로 표시했거나 이름이 쓰기(submit · write · delete …)면
사유와 함께 거부한다. 호출 직전에 서버에서 도구 목록을 다시 받아 판정한다(클라이언트가 보낸 판정은 믿지 않는다).

결과는 사람이 읽는 한국어 사유(error)와 분류(error_kind: config · refused · unreachable · timeout · auth · not_mcp ·
protocol · server · closed · too_large · busy)로 돌려준다. 폴백·빈 성공은 없다: 도구 목록을 받지 못하면 status 는 'failed' 다.
서버 응답 본문은 오류 문구에 싣지 않는다 — 아무 주소에나 요청을 보내 그 응답을 화면으로 읽는 길이 되지 않게.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import logging
import queue
import re
import socket
import threading
import time
from contextlib import contextmanager
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from jsonschema import exceptions as schema_errors
from jsonschema.validators import validator_for
from referencing import Registry
from referencing.exceptions import NoSuchResource, Unresolvable

from .mcp_secrets import is_reference_only

log = logging.getLogger("process.mcp_check")
PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "hyd-process-mcp-check", "version": "1.0"}
DEFAULT_TIMEOUT = 10.0
MAX_TIMEOUT = 60.0
TRANSPORTS = ("streamable_http", "sse")
_TRANSPORT_ALIASES = {"http": "streamable_http", "streamable-http": "streamable_http", "streamablehttp": "streamable_http",
                      "url": "streamable_http", "sse": "sse", "streamable_http": "streamable_http"}
STDIO_REFUSED = ("명령형(stdio) 서버는 포털에 등록하지 않습니다 — 서버를 HTTP(Streamable HTTP)로 띄워 그 주소를 등록하세요 "
                 "(내 PC 의 도구에서 명령으로 띄워 쓰는 서버는 그 PC 의 설정에 둡니다)")
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
PORTAL_SLOTS = 3                                 # 포털이 여는 연결(목록 · 써 보기 · 연결 검사 · 등록)은 동시에 이만큼 — 스레드 · 메모리(A131)
ADDRESS_REFUSED = "링크로컬 · 미지정 · 멀티캐스트 주소라 도구 서버 주소가 될 수 없습니다"
LOOPBACK_REFUSED = ("이 컴퓨터 자신(루프백)을 가리켜 process 컨테이너 자신에 닿습니다 — 내 PC에서 띄운 서버는 localhost · 127.0.0.1 대신 "
                    "host.docker.internal 로 적으세요")
_SLOTS = threading.BoundedSemaphore(PORTAL_SLOTS)


# ---------------------------------------------------------------- 주소 규칙(P3-06) — 이름 · 숫자 IP 모두 실제로 닿는 주소로 판정
def _ip_problem(ip, *, student: bool) -> str | None:
    ip = getattr(ip, "ipv4_mapped", None) or ip
    if ip.is_link_local or ip.is_unspecified or ip.is_multicast:
        return ADDRESS_REFUSED
    if student and ip.is_loopback:
        return LOOPBACK_REFUSED
    return None


def address_problem(hostname: str, *, student: bool) -> str | None:
    """그 이름이 가리키는 모든 주소를 본다(`2852039166` · `0` · 그런 주소로 풀리는 이름 포함). 학생 서버(student)는 루프백도 거절 —
    process 컨테이너 안의 루프백은 process 자신이다. 이름을 찾을 수 없으면 None — 연결 검사가 「주소를 찾을 수 없습니다」로 실패시킨다."""
    found = []
    try:                                                    # 숫자 표기(10진 · 16진 · 8진 · 줄인 점 표기)는 운영체제와 상관없이 같은 주소로 읽는다
        found.append(socket.inet_ntoa(socket.inet_aton(hostname)))
    except OSError:
        pass
    try:
        found += [info[4][0] for info in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)]
    except (socket.gaierror, UnicodeError):
        pass
    for address in found:
        problem = _ip_problem(ipaddress.ip_address(address.split("%")[0]), student=student)
        if problem:
            return f"url: '{hostname}' 는 {problem}"
    return None


def _guarded_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, **kw):
    """연결한 뒤 실제 상대 주소를 다시 본다 — 검사와 연결 사이에 이름이 다른 주소로 바뀌어도(DNS 재결합) 링크로컬 등에는 보내지 않는다."""
    sock = socket.create_connection(address, timeout, source_address, **kw)
    problem = _ip_problem(ipaddress.ip_address(sock.getpeername()[0].split("%")[0]), student=False)
    if problem:
        sock.close()
        raise CheckError("config", f"'{address[0]}' 는 {problem}")
    return sock


class _GuardedHttp(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_connection(http.client.HTTPConnection), req)


class _GuardedHttps(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_connection(http.client.HTTPSConnection), req, context=self._context)


def _connection(base):
    def make(*args, **kw):
        conn = base(*args, **kw)
        conn._create_connection = _guarded_connection
        return conn
    return make


_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}), _GuardedHttp(), _GuardedHttps())   # 프록시 없이 직접 · 상대 주소 확인


class CheckError(Exception):
    """사람이 읽는 실패 사유 + 분류."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind, self.message = kind, message


# ---------------------------------------------------------------- 설정 정규화 · 비밀값 가림
def normalize(spec, *, student: bool = False) -> dict:
    """tenants.mcp 의 서버 한 칸을 검사 가능한 형태로 만든다. 잘못된 입력은 ValueError('칸: 사유').
    student: 학생 서버(기준 다섯 밖 — 포털 · 출발본 · SQL 로 넣은 것)면 루프백도 거절한다(address_problem)."""
    if not isinstance(spec, dict):
        raise ValueError("설정은 객체({command…} 또는 {url…})여야 합니다")
    transport = spec.get("transport") or spec.get("type")
    if spec.get("command") or str(transport or "").strip().lower() == "stdio":
        raise ValueError(STDIO_REFUSED)
    if transport is None and not spec.get("url"):
        raise ValueError("url: 도구 서버의 HTTP 주소가 필요합니다 (예: http://host.docker.internal:8301/mcp)")
    key = str(transport or "streamable_http").strip().lower()
    if key not in _TRANSPORT_ALIASES:
        raise ValueError(f"transport: '{transport}' 는 지원하지 않습니다 (가능: streamable_http · sse)")
    out: dict = {"transport": _TRANSPORT_ALIASES[key]}
    url = spec.get("url") or spec.get("serverUrl")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url: HTTP 서버는 주소가 필요합니다")
    url = url.strip()
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("url: http:// 또는 https:// 로 시작하는 주소여야 합니다 (예: http://dmn-mcp:8198/mcp)")
    problem = address_problem(parsed.hostname, student=student)
    if problem:
        raise ValueError(problem)
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


def is_secret_value(key: str, value) -> bool:
    """설정 칸 값 하나가 비밀인가 — 화면 가림(masked)과 출발본 내보내기(config_bundle)의 한 판정.
    비밀 이름(Authorization · *TOKEN …)의 값이거나 값 안에 비밀번호 · 토큰 꼴이 있으면 비밀. '${SECRET:X}' 같은 비밀 이름 참조는 비밀이 아니다."""
    if not isinstance(value, str) or value == "" or is_reference_only(value):
        return False
    return is_secret_key(key) or mask_text(value) != value


def masked(spec: dict) -> dict:
    """응답용 사본: 접속 헤더의 비밀 값은 가리고, url 의 비밀번호도 가린다."""
    out = json.loads(json.dumps(spec))
    for field in ("headers",):
        if isinstance(out.get(field), dict):
            # G2: '${SECRET:KEY}' · 'Bearer ${SECRET:KEY}' 는 비밀이 아니라 비밀의 이름이라 그대로 보인다(값은 mcp_secrets 표에만)
            out[field] = {k: (MASK if is_secret_value(k, v) else v) for k, v in out[field].items()}
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
        raise CheckError("protocol", f"프로토콜 오류 — {where}이(가) MCP(JSON-RPC 2.0) 형식이 아닙니다. 주소가 도구 서버의 MCP 끝점인지 확인하세요")
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        raise CheckError("protocol", f"프로토콜 오류 — {where}에 jsonrpc 2.0 봉투가 없습니다. 주소가 도구 서버의 MCP 끝점인지 확인하세요")
    return msg


def _result_of(msg: dict, method: str) -> dict:
    if "error" in msg:
        err = msg["error"] if isinstance(msg["error"], dict) else {"message": str(msg["error"])}
        raise CheckError("server", f"서버가 {method} 요청에 오류를 돌려줬습니다 (코드 {err.get('code', '?')}): {err.get('message', '')}".strip())
    result = msg.get("result")
    if not isinstance(result, dict):
        raise CheckError("protocol", f"프로토콜 오류 — {method} 응답에 result 객체가 없습니다")
    return result


def _sse_events(stream, before_read=None) -> "iter[tuple[str, str]]":
    """(event, data) 쌍. stream 은 readline(limit) 을 가진 응답. 줄 하나 · 이벤트 하나의 data 가 MAX_WIRE_BYTES 를 넘으면 그 자리에서
    too_large 로 멈추고(다 모은 뒤가 아니라), before_read 가 있으면 줄을 읽기 전마다 부른다(세션 마감 확인 · 소켓 시간 맞추기) —
    「: ping」만 보내는 서버도 마감에서 끝난다."""
    event, data, size = "message", [], 0
    while True:
        if before_read is not None:
            before_read()
        raw = stream.readline(MAX_WIRE_BYTES + 1)
        if not raw:
            break
        if len(raw) > MAX_WIRE_BYTES:
            raise _too_large()
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if line == "":
            if data:
                yield event, "\n".join(data)
            event, data, size = "message", [], 0
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            part = line[5:].lstrip()
            size += len(part)
            if size > MAX_WIRE_BYTES:
                raise _too_large()
            data.append(part)
    if data:
        yield event, "\n".join(data)


def _bound_reads(resp, session: "_Session"):
    """응답 소켓의 읽기 한 번 시간을 세션에 남은 시간으로 맞추는 함수. 소켓 시간 제한은 읽기 한 번마다라 줄마다 다시 맞추지 않으면,
    조금씩 보내는 서버가 마감을 넘겨 스레드를 붙잡는다(실측: 1초마다 ping 이면 12초 — P3-05)."""
    sock = resp.fp.raw._sock                                          # http.client 응답의 소켓(urllib 응답도 같은 구조)

    def before_read():
        sock.settimeout(max(0.05, session.remaining()))
    return before_read


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
            schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else None
            notes = tool.get("annotations") if isinstance(tool.get("annotations"), dict) else {}
            entry = {"name": str(tool["name"]), "title": str(tool.get("title") or notes.get("title") or "").strip() or None,
                     "description": str(tool.get("description") or "").strip(), "input_schema": schema,
                     "annotations": {k: notes[k] for k in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint") if k in notes}}
            ok, reason = read_only_verdict(entry)
            entry.update(callable=ok, refuse_reason=reason, confirmable=confirmable(entry))
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
    """(시험 호출 허용?, 거부 사유). 서버의 readOnlyHint=true 와 '쓰기가 아닌 이름'이 둘 다 맞아야 허용한다.
    거부 사유는 도구 연결 화면에 그대로 보이는 학생 문장이다 — 표시 이름(readOnlyHint · destructiveHint)은 쓰지 않는다(한바퀴3). 예외는 표시가
    없는 도구 하나: 고칠 사람(서버를 쓰는 학생 · 강사)이 서버 코드에 적을 표시 이름 그대로가 할 일이라 이름을 둔다."""
    name = str(tool.get("name") or "")
    notes = tool.get("annotations") or {}
    hit = next((w for w in _words(name) if w in _WRITE_WORDS), None)
    if notes.get("destructiveHint") is True and notes.get("readOnlyHint") is not True:
        return False, "서버가 이 도구를 되돌릴 수 없는 쓰기 도구로 표시했습니다 — 포털에서는 읽기 전용 도구만 써 볼 수 있습니다"
    if notes.get("readOnlyHint") is False:
        return False, "서버가 이 도구를 쓰기 도구로 표시했습니다 — 포털 써 보기에서는 쓰기 도구를 부르지 않습니다"
    if hit:
        return False, (f"이름의 '{hit}' 가 쓰기·실행을 뜻합니다 — 서버가 읽기 전용으로 표시했더라도 포털에서는 부르지 않습니다"
                       if notes.get("readOnlyHint") is True else f"이름의 '{hit}' 가 쓰기·실행을 뜻합니다 — 포털에서는 읽기 전용 도구만 써 볼 수 있습니다")
    if notes.get("readOnlyHint") is not True:
        return False, ("서버가 이 도구를 읽기 전용(readOnlyHint)으로 표시하지 않았습니다 — 서버 코드에서 도구에 "
                       "readOnlyHint=true 표시를 붙이면 써 볼 수 있습니다")
    return True, None


def confirmable(tool: dict) -> bool:
    """G2 ②: 강사가 "이 도구는 읽기"로 확인해 줄 수 있는 도구 — 거부 사유가 '읽기 전용 표시 없음' 하나뿐일 때만.
    서버가 쓰기(readOnlyHint=false)나 되돌릴 수 없는 쓰기(destructiveHint)로 표시했거나 이름이 쓰기 · 실행을 뜻하면 확인할 수 없다
    (공개 구글 MCP 서버처럼 표시를 안 붙인 서버의 search · list · get 도구만 사람이 풀어 준다)."""
    notes = tool.get("annotations") or {}
    if notes.get("readOnlyHint") is True or notes.get("readOnlyHint") is False or notes.get("destructiveHint") is True:
        return False
    return not any(w in _WRITE_WORDS for w in _words(str(tool.get("name") or "")))


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
    # HYD 도구는 실패를 isError 대신 {"result": "error", …} 봉투로도 돌려준다(2026-10-25 수업 한 바퀴: 없는 표 조회가 초록 「결과」로 보였다)
    envelope_error = isinstance(parsed, dict) and parsed.get("result") == "error"
    return {"is_error": bool(result.get("isError")) or envelope_error, "text": pretty[:max_chars] + ("\n… (잘림)" if truncated else ""),
            "json": parsed is not None, "size_chars": size, "truncated": truncated, "limit_chars": max_chars}


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
            # G2 ③: 토큰이 필요한 서버는 만료가 흔하다 — 일반 연결 실패와 갈라 무엇을 할지 말한다(토큰을 다시 받는 일은 사람 몫)
            return CheckError("auth", f"인증 실패 (HTTP {code}) — 인증이 만료되었거나 없습니다. 토큰을 새로 받아 "
                                      "도구 연결 화면의 '비밀 값'(${SECRET:이름})에 넣고 연결 검사를 다시 누르세요")
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
    return CheckError("unreachable", f"{host} 에 연결하지 못했습니다 — 서버가 켜져 있는지, 주소·포트와 방화벽·네트워크 연결을 확인한 뒤 연결 검사를 다시 누르세요")


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
                before_read = _bound_reads(resp, session)
                if ctype == "application/json":
                    before_read()
                    body = resp.read(MAX_WIRE_BYTES + 1)
                    if len(body) > MAX_WIRE_BYTES:
                        raise _too_large()
                    self.pending.append(_parse_message(body, where="HTTP 응답"))
                elif ctype == "text/event-stream":
                    for event, data in _sse_events(resp, before_read):
                        if event != "message":
                            continue
                        msg = _parse_message(data, where="SSE 이벤트")
                        self.pending.append(msg)
                        if msg.get("id") == payload["id"] and ("result" in msg or "error" in msg):
                            break
                else:
                    raise CheckError("not_mcp", f"MCP 끝점이 아닙니다 — 응답이 JSON 도 SSE 도 아닙니다 (Content-Type {ctype or '없음'}, HTTP {resp.status}). "
                                                "주소 경로(보통 /mcp)를 확인하세요")
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
            for event, data in _sse_events(self.resp):
                self.q.put((event, data))
        except CheckError as e:
            self.q.put(("__error__", e))
        except Exception as e:  # noqa: BLE001 — 끊긴 사유는 받는 쪽이 closed 로 알린다(예외 글 · 본문은 싣지 않는다)
            self.q.put(("__error__", CheckError("closed", f"SSE 스트림 읽기가 끊겼습니다 ({type(e).__name__})")))
        self.q.put(None)

    def _next(self, session: _Session):
        try:
            item = self.q.get(timeout=session.remaining())
        except queue.Empty:
            raise CheckError("timeout", f"{session.timeout:g}초 안에 SSE 스트림으로 응답이 오지 않았습니다 (시간 초과)")
        if item is None:
            raise CheckError("closed", "서버가 SSE 스트림을 닫았습니다 — MCP 서버가 아니거나 세션을 거부했습니다")
        if item[0] == "__error__":
            raise item[1]
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
                resp.read(MAX_WIRE_BYTES + 1)                       # 응답은 스트림으로 온다 — POST 본문은 버린다(크기 상한 안에서)
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            raise _http_error(e, self.endpoint, session.timeout)

    def recv(self, session: _Session) -> dict:
        while True:
            event, data = self._next(session)
            if event == "message":
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


@contextmanager
def portal_slot(wait: float):
    """포털이 여는 연결 하나의 자리(동시에 PORTAL_SLOTS 개). 자리가 wait 초 안에 나지 않으면 CheckError(busy).
    도구 지도 · 써 보기(mcp_api)와 연결 검사 · 등록(mcp_registry.run_check)이 함께 쓴다. 처리 흐름 안의 호출(승인 뒤 시스템 task ·
    읽기 확인)은 쓰지 않는다 — 포털에서 누른 검사 때문에 처리 건이 기다리지 않게."""
    if not _SLOTS.acquire(timeout=max(0.0, wait)):
        raise CheckError("busy", f"다른 도구 연결 {PORTAL_SLOTS}개가 진행 중입니다 — 잠시 뒤 다시 누르세요")
    try:
        yield
    finally:
        _SLOTS.release()


def _with_session(spec: dict, timeout: float, work) -> dict:
    """연결 → initialize → work(session, init) . 예외를 던지지 않고 status · error 로 답한다."""
    started = time.monotonic()
    out = {"status": "failed", "error": None, "error_kind": None, "server_info": None, "protocol_version": None,
           "checked_at": _now_z(), "elapsed_ms": 0, "transport": spec.get("transport")}
    transport = None
    try:
        kind = spec["transport"]
        if kind == "streamable_http":
            transport = _StreamableHttp(spec)
        elif kind == "sse":
            transport = _Sse(spec, timeout)
        else:
            raise CheckError("config", f"transport '{kind}' 는 연결할 수 없습니다 (가능: streamable_http · sse)")
        session = _Session(transport, timeout)
        init = _initialize(session)
        out.update(init)
        done = work(session)
        out.update(done)
        if "status" not in done:
            out["status"] = "ok"
    except CheckError as e:
        out.update(status="failed", error=e.message, error_kind=e.kind)
    except Exception as e:  # noqa: BLE001 — 분류 못 한 실패도 사유는 남긴다. 예외 글은 싣지 않는다(머리글 값 같은 비밀이 섞일 수 있다 — P3-17)
        log.warning("MCP connection to %s failed unexpectedly: %s", spec.get("url"), type(e).__name__)
        out.update(status="failed", error=f"연결 중 예상하지 못한 오류가 났습니다({type(e).__name__}) — 주소와 접속 헤더 값을 확인하고 다시 검사하세요",
                   error_kind="protocol")
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


def call(spec: dict, tool: str, arguments: dict, timeout: float = DEFAULT_TIMEOUT, *, max_chars: int = MAX_RESULT_CHARS,
         confirmed: set[str] | frozenset[str] | None = None) -> dict:
    """읽기 전용 도구 하나를 실제로 부른다. 호출 직전 같은 세션에서 tools/list 를 다시 받아 판정한다.
    confirmed(G2 ②): 강사가 읽기로 확인한 도구 이름 — 그 자리에서 다시 받은 도구가 여전히 confirmable(표시 없음뿐)일 때만 부른다.
    status: ok(결과 있음 — 도구가 오류를 돌려줘도 result.is_error 로 보인다) · refused(쓰기·표시 없음 · 없는 도구) · failed(연결·프로토콜)."""
    if not isinstance(arguments, dict):
        return {"status": "refused", "error": "입력은 이름→값 객체여야 합니다", "error_kind": "input", "result": None, "tool": tool}

    def work(session):
        tools = {t["name"]: t for t in _list_tools(session)}
        meta = tools.get(tool)
        if meta is None:
            return {"status": "refused", "error": f"서버에 '{tool}' 도구가 없습니다 (도구 목록을 다시 읽으세요)", "error_kind": "no_tool", "result": None}
        if not meta["callable"] and not (confirmed and tool in confirmed and meta.get("confirmable")):
            return {"status": "refused", "error": meta["refuse_reason"], "error_kind": "not_read_only", "result": None}
        invalid = _argument_problem(meta, arguments)
        if invalid:
            return invalid
        res = session.request("tools/call", {"name": tool, "arguments": arguments})
        return {"status": "ok", "result": shape_result(res, max_chars)}

    out = _with_session(spec, _clamp(timeout), work)
    out["tool"] = tool
    out.setdefault("result", None)
    return out


IDEMPOTENCY_ARG = "idempotency_key"
#: JSON Schema 검사 낱말 → 학생 말(값은 싣지 않는다 — 거절된 값에 비밀이 있을 수 있다)
_SCHEMA_WORDS = {"required": "꼭 넣어야 할 칸이 빠졌습니다", "type": "값의 종류(글 · 숫자 · 목록 …)가 다릅니다",
                 "enum": "고를 수 있는 값이 아닙니다", "additionalProperties": "받지 않는 칸이 있습니다",
                 "minimum": "값이 너무 작습니다", "maximum": "값이 너무 큽니다", "exclusiveMinimum": "값이 너무 작습니다",
                 "exclusiveMaximum": "값이 너무 큽니다", "minLength": "글이 너무 짧습니다", "maxLength": "글이 너무 깁니다",
                 "pattern": "글의 모양이 정해진 규칙과 다릅니다", "format": "값의 형식이 다릅니다", "minItems": "목록 항목이 너무 적습니다",
                 "maxItems": "목록 항목이 너무 많습니다", "const": "정해진 값과 다릅니다"}


def _no_schema_retrieval(uri):
    # A tool schema may use its own $defs, but validation must not fetch URLs or
    # open files supplied by an MCP server.
    raise NoSuchResource(ref=uri)


def _argument_problem(meta: dict, arguments: dict) -> dict | None:
    """Validate against this session's advertised contract before tools/call.

    Never put ValidationError.message in the response: it includes rejected
    values, which may contain credentials. JSON Schema format is an annotation
    unless the schema's dialect says otherwise; no extra format policy is added.
    """
    schema = meta.get("input_schema")
    try:
        if not isinstance(schema, dict):
            raise ValueError("missing input schema")
        if schema.get("$schema") and validator_for(schema, default=None) is None:
            raise ValueError("unsupported schema dialect")
        validator = validator_for(schema)
        validator.check_schema(schema)
        error = next(validator(schema, registry=Registry(retrieve=_no_schema_retrieval)).iter_errors(arguments), None)
    except (schema_errors.SchemaError, Unresolvable, ValueError, TypeError, RecursionError):
        return {"status": "refused", "error": "도구의 입력 형식을 검증할 수 없습니다 — 서버의 inputSchema를 확인하세요",
                "error_kind": "input_schema", "result": None}
    if error is None:
        return None
    where = ".".join(str(p) for p in error.absolute_path) or "입력 전체"
    return {"status": "refused", "error": f"도구 입력이 서버가 정한 입력 형식과 맞지 않습니다 — {where}: {_SCHEMA_WORDS.get(error.validator, '형식 규칙')}",
            "error_kind": "input", "result": None}


def call_effect(spec: dict, tool: str, arguments: dict, *, idempotency_key: str | None = None, timeout: float = DEFAULT_TIMEOUT,
                max_chars: int = MAX_RESULT_CHARS) -> dict:
    """C2: 사람 승인 뒤 시스템 task(effect_parts 'mcp:call')만 부르는 쓰기 호출. 포털 써 보기 · 에이전트 도구 목록과는 다른 길이다 —
    읽기 전용 판정(read_only_verdict)을 하지 않는 대신 이 함수는 process 의 승인 뒤 부품에서만 불린다(instances._run_mcp_call).
    도구의 입력 형식에 idempotency_key 가 있으면 처리 건 · 작업 키를 넣어, 재시도해도 서버가 같은 호출로 알아보게 한다.
    status: ok(결과 — 도구 오류도 result.is_error 로) · refused(없는 도구) · failed(연결 · 프로토콜)."""
    if not isinstance(arguments, dict):
        return {"status": "refused", "error": "입력은 이름→값 객체여야 합니다", "error_kind": "input", "result": None, "tool": tool}

    def work(session):
        tools = {t["name"]: t for t in _list_tools(session)}
        meta = tools.get(tool)
        if meta is None:
            return {"status": "refused", "error": f"서버에 '{tool}' 도구가 없습니다", "error_kind": "no_tool", "result": None}
        args = dict(arguments)
        props = (meta.get("input_schema") or {}).get("properties") or {}
        if idempotency_key and IDEMPOTENCY_ARG in props and IDEMPOTENCY_ARG not in args:
            args[IDEMPOTENCY_ARG] = idempotency_key
        invalid = _argument_problem(meta, args)
        if invalid:
            return invalid
        res = session.request("tools/call", {"name": tool, "arguments": args})
        return {"status": "ok", "result": shape_result(res, max_chars), "arguments": mask_value(args),
                "idempotent": IDEMPOTENCY_ARG in args, "annotations": meta.get("annotations") or {}}

    out = _with_session(spec, _clamp(timeout), work)
    out["tool"] = tool
    out.setdefault("result", None)
    return out
