"""U3 시험용 가짜 MCP 서버 (의존성 없음). initialize → tools/list(두 페이지) → tools/call.

도구: add · lookup · big_dump(읽기 전용 표시) / greet(표시 없음) / submit_note(쓰기 표시) / delete_rows(읽기 전용이라 표시했지만 이름이 쓰기)
  python mcp_fake_server.py                 stdio (줄 단위 JSON-RPC)
  python mcp_fake_server.py --exit-early    initialize 전에 stderr 에 사유를 쓰고 종료 (프로세스 종료 사유 시험)

HTTP 변형(streamable_http · sse · 401 · HTML · 지연)은 test_mcp_check.py 가 스레드 서버로 띄운다 — respond() 를 같이 쓴다.
CALLS 는 실제로 불린 도구 이름 — 거부된 쓰기 도구가 서버에 닿지 않았는지 시험이 본다.
"""
import json
import sys

READ = {"readOnlyHint": True, "destructiveHint": False}
TOOLS = [
    {"name": "add", "description": "두 수를 더한다", "annotations": READ,
     "inputSchema": {"type": "object", "properties": {"a": {"type": "number", "description": "첫 수"}, "b": {"type": "number"}}, "required": ["a", "b"]}},
    {"name": "lookup", "description": "설비 연결 정보를 읽는다", "annotations": READ,
     "inputSchema": {"type": "object", "properties": {"asset": {"type": "string", "description": "설비 코드"},
                                                      "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None}}, "required": ["asset"]}},
    {"name": "big_dump", "description": "큰 결과", "annotations": READ, "inputSchema": {"type": "object", "properties": {}}},
    {"name": "greet", "description": "이름으로 인사한다 (표시 없음)", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}}},
    {"name": "submit_note", "description": "메모를 저장한다", "annotations": {"readOnlyHint": False},
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}}},
    {"name": "delete_rows", "description": "행을 지운다", "annotations": READ, "inputSchema": {"type": "object", "properties": {}}},
]
CALLS: list[str] = []


def _text(value) -> dict:
    return {"content": [{"type": "text", "text": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}], "isError": False}


def call(name: str, args: dict) -> dict:
    CALLS.append(name)
    if name == "add":
        if not isinstance(args.get("a"), (int, float)) or not isinstance(args.get("b"), (int, float)):
            return {"content": [{"type": "text", "text": "a, b 는 숫자여야 합니다"}], "isError": True}
        return _text({"sum": args["a"] + args["b"]})
    if name == "lookup":
        doc = {"asset": args.get("asset"), "dsn": "postgresql://reader:s3cret@db:5432/ent", "password": "hydpass123", "key": "a",
               "note": "접속 postgresql://u:pw@h/x · Bearer abcdef123456", "rows": list(range(args.get("limit") or 2))}
        return {"content": [{"type": "text", "text": json.dumps(doc, ensure_ascii=False)}], "structuredContent": doc, "isError": False}
    if name == "big_dump":
        return _text("가" * 50_000)
    if name in ("greet", "submit_note", "delete_rows"):
        return _text("불렸다: " + name)
    raise KeyError(name)


def respond(msg: dict):
    method, rid = msg.get("method"), msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": msg["params"].get("protocolVersion", "2025-06-18"),
                                                       "capabilities": {"tools": {}}, "serverInfo": {"name": "fake-mcp", "version": "0.1"}}}
    if method == "tools/list":
        cursor = (msg.get("params") or {}).get("cursor")
        if cursor is None:
            return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS[:1], "nextCursor": "page2"}}
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS[1:]}}
    if method == "tools/call":
        params = msg.get("params") or {}
        try:
            return {"jsonrpc": "2.0", "id": rid, "result": call(params.get("name"), params.get("arguments") or {})}
        except KeyError:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": f"Unknown tool: {params.get('name')}"}}
    if rid is None:
        return None                                              # 알림에는 답하지 않는다
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}}


def main():
    if "--exit-early" in sys.argv:
        sys.stderr.write("fatal: NEO4J_URI 환경변수가 없습니다\n")
        sys.stderr.flush()
        sys.exit(3)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        out = respond(json.loads(line))
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
