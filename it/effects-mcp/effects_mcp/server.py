"""effects-mcp (hyd-effects): 사람 승인 뒤 process 의 시스템 task 가 부르는 **쓰기** MCP 서버 (FastMCP, streamable HTTP).

    docker: MCP_PORT=8197 SMTP_HOST=host.docker.internal SMTP_PORT=54325 ENTERPRISE_URL=http://enterprise-sim:8095
    tools : send_mail · add_calendar_entry · record_case   (3; 모두 쓰기 — readOnlyHint=false, idempotency_key 로 멱등)

에이전트에게는 붙이지 않는다: tenants.mcp 에 등록하지 않고(워커가 모름), process 의 EFFECT_MCP_SERVERS 로만 부른다
(procsvc/instance_mode.py). 포털 '도구 써 보기'도 readOnlyHint=false 라 거절한다(mcp_check.read_only_verdict).
"""
from __future__ import annotations

import os
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .tools import EffectTools, Ledger

mcp = FastMCP("hyd-effects-mcp", instructions=(
    "사람이 승인한 처리 건의 시스템 task 가 부르는 쓰기 도구다(메일 · CMMS 일정 · 처리 건 기록). 에이전트용이 아니다. "
    "idempotency_key 가 같으면 두 번째 호출은 첫 결과를 돌려준다."))
tools = EffectTools(Ledger(os.getenv("EFFECTS_STATE_PATH", "/data/effects.sqlite3")))
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
Key = Annotated[str | None, Field(description="멱등 키 — process 가 '처리 건:작업' 으로 넣는다. 같은 키의 재호출은 첫 결과를 돌려준다")]


@mcp.tool(annotations=WRITE)
def send_mail(to: Annotated[str | list[str], Field(description="받는 주소 (쉼표로 여럿, 예: purchasing@hyd.local)")],
              subject: Annotated[str, Field(description="제목")],
              body: Annotated[str, Field(description="본문 (일반 글)")],
              cc: Annotated[str | list[str] | None, Field(description="참조 주소")] = None,
              idempotency_key: Key = None) -> dict:
    """메일 한 통을 SMTP 로 보낸다. 수업 기본은 Supabase 로컬 Inbucket(웹 http://localhost:54324) — 실제 발송 없음."""
    return tools.send_mail(to, subject, body, cc=cc, idempotency_key=idempotency_key)


@mcp.tool(annotations=WRITE)
def add_calendar_entry(asset: Annotated[str, Field(description="설비 코드 (HYD-01 | HYD-02 | HYD-03)")],
                       title: Annotated[str, Field(description="일정 이름 (예: 펌프 씰 교체 — 야간 정비창)")],
                       starts_at: Annotated[str | None, Field(description="시작 시각 ISO-8601 (비우면 지금)")] = None,
                       duration_h: Annotated[float | None, Field(description="길이(시간)")] = None,
                       wo_ref: Annotated[str | None, Field(description="연결할 작업지시 번호")] = None,
                       note: Annotated[str | None, Field(description="메모")] = None,
                       idempotency_key: Key = None) -> dict:
    """CMMS 정비 · 생산 공지 일정을 등록한다(ent.cmms_calendar)."""
    return tools.add_calendar_entry(asset, title, starts_at=starts_at, duration_h=duration_h, wo_ref=wo_ref, note=note,
                                    idempotency_key=idempotency_key)


@mcp.tool(annotations=WRITE)
def record_case(title: Annotated[str, Field(description="기록 제목")],
                body: Annotated[str, Field(description="기록 본문 (무슨 일이 있었고 무엇을 했나)")],
                asset: Annotated[str | None, Field(description="설비 코드")] = None,
                proc_inst_id: Annotated[str | None, Field(description="처리 건 id")] = None,
                idempotency_key: Key = None) -> dict:
    """처리 건 기록 한 장을 남긴다(ent.case_records) — 지식 자산화용."""
    return tools.record_case(title, body, asset=asset, proc_inst_id=proc_inst_id, idempotency_key=idempotency_key)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request):
    from starlette.responses import JSONResponse
    return JSONResponse({"ok": True, "tools": ["send_mail", "add_calendar_entry", "record_case"]})


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8197")), path="/mcp", uvicorn_config={"ws": "none"})
