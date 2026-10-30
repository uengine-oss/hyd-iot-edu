"""effects-mcp (hyd-effects): 사람 승인 뒤 process 의 시스템 task 가 부르는 **쓰기** MCP 서버 (FastMCP, streamable HTTP).

    docker: MCP_PORT=8197 SMTP_HOST=host.docker.internal SMTP_PORT=54325
    tools : send_mail   (1; 쓰기 — readOnlyHint=false, idempotency_key 로 멱등). 공급사 · 생산팀 메일은 수업 메일함 Inbucket 으로만 간다

에이전트에게는 붙이지 않는다: tenants.mcp 에 등록하지 않고(워커가 모름), process 의 EFFECT_MCP_SERVERS 로만 부른다
(procsvc/instance_mode.py). 포털 '도구 써 보기'도 readOnlyHint=false 라 거절한다(mcp_check.read_only_verdict).
하-04: 관례만으로 막지 않는다 — 쓰기 도구는 process 만 아는 값(PROCESS_CALLER_TOKEN, 머리글 X-HYD-Process-Caller)이 맞는 호출만 받는다.
값이 설정되지 않았으면 서버를 띄우지 않는다(조용히 아무나 받지 않게).
"""
from __future__ import annotations

import hmac
import os
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from pydantic import Field

from .tools import EffectTools, Ledger

mcp = FastMCP("hyd-effects-mcp", instructions=(
    "사람이 승인한 처리 건의 시스템 task 가 부르는 메일 도구다(수업 메일함, 실제 발송 없음). 에이전트용이 아니다. "
    "idempotency_key 가 같으면 두 번째 호출은 첫 결과를 돌려준다."))
tools = EffectTools(Ledger(os.getenv("EFFECTS_STATE_PATH", "/data/effects.sqlite3")))
CALLER_HEADER = "X-HYD-Process-Caller"
CALLER_TOKEN = os.environ.get("PROCESS_CALLER_TOKEN", "")
if not CALLER_TOKEN:
    raise RuntimeError("PROCESS_CALLER_TOKEN 이 설정되지 않아 effects-mcp 를 띄우지 않습니다 — 승인 뒤 쓰기 도구를 process 만 부르게 하는 값입니다")


def _require_process() -> None:
    """하-04: 이 호출에 process 만 아는 값이 실렸는가. 아니면 도구를 실행하지 않고 거절한다."""
    got = get_http_headers(include_all=True).get(CALLER_HEADER.lower(), "")
    if not hmac.compare_digest(got.encode(), CALLER_TOKEN.encode()):
        raise ToolError("이 메일 도구는 사람 승인을 거친 process 의 시스템 단계만 부를 수 있습니다")
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
Key = Annotated[str | None, Field(description="멱등 키 — process 가 '처리 건:작업' 으로 넣는다. 같은 키의 재호출은 첫 결과를 돌려준다")]


@mcp.tool(annotations=WRITE)
def send_mail(to: Annotated[str | list[str], Field(description="받는 주소 (쉼표로 여럿, 예: purchasing@hyd.local)")],
              subject: Annotated[str, Field(description="제목")],
              body: Annotated[str, Field(description="본문 (일반 글)")],
              cc: Annotated[str | list[str] | None, Field(description="참조 주소")] = None,
              idempotency_key: Key = None) -> dict:
    """메일 한 통을 SMTP 로 보낸다. 수업 기본은 Supabase 로컬 Inbucket(웹 http://localhost:54324) — 실제 발송 없음."""
    _require_process()
    return tools.send_mail(to, subject, body, cc=cc, idempotency_key=idempotency_key)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request):
    from starlette.responses import JSONResponse
    return JSONResponse({"ok": True, "tools": ["send_mail"]})


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8197")), path="/mcp", uvicorn_config={"ws": "none"})
