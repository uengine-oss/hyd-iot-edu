"""enterprise-mcp: FastMCP server (streamable HTTP) exposing the business DB to the agent. Same pattern as wms-mcp.

    docker: ENTERPRISE_DSN=<dedicated reader DSN> MCP_PORT=8199
    tools : mes_orders · erp_contract · erp_inventory · cmms_history · qms_lots · scm_suppliers · ems_demand (7 fixed reads) ·
            spare_stock · part_quotes · maintenance_windows · pm_status (C2: 4 fixed reads) ·
            describe_schema · describe_catalog · query   (14; all read-only, all answer in the {result, document} envelope —
            a DB failure is {"result": "error", "error_kind": "UNKNOWN"}, never a raised exception)

    C2 (확정 2026-10-09, 업무 MCP 를 보전용 · 구매용 둘로): 같은 코드를 ENTERPRISE_MCP_TOOLSET 으로 나눠 띄운다. 시나리오 에이전트는 필요한
    서버만 붙인다(B 정기 정비 → 보전용, C 예비품 구매 → 구매용). 두 서버의 도구는 겹치지 않고, 둘 다 읽기만 한다(쓰기는 승인 뒤 process).
        all          (기본, 서버 이름 enterprise)        위 14개 전부 — 기존 흐름 · 랩업 SQL(query) 그대로
        maintenance  (enterprise-maint, 포트 8196)       pm_status(계획 · 계수기 · 키트 영향) · maintenance_windows · cmms_history(작업지시 · 백로그) · mes_orders
        purchasing   (enterprise-purchase, 포트 8195)    spare_stock(ERP 재고) · part_quotes · scm_suppliers(SCM · 공급사)
    나눈 서버에는 자유 SQL(query · describe_*)을 두지 않는다 — 두 서버의 경계를 SQL 이 넘지 않게.
"""
from __future__ import annotations

import os
from typing import Annotated

import psycopg
from fastmcp import FastMCP
from pydantic import Field

from .tools import EnterpriseTools, guarded
from hydcommon.enterprise import reader_connection as connect_reader

DSN = os.getenv("ENTERPRISE_DSN", "postgresql://hyd_enterprise_reader:hyd-enterprise-read-local@host.docker.internal:54322/postgres")
TOOLSETS = {
    "maintenance": ("pm_status", "maintenance_windows", "cmms_history", "mes_orders"),
    "purchasing": ("spare_stock", "part_quotes", "scm_suppliers"),
}
TOOLSET = os.getenv("ENTERPRISE_MCP_TOOLSET", "all")
if TOOLSET not in ("all", *TOOLSETS):
    raise SystemExit(f"ENTERPRISE_MCP_TOOLSET={TOOLSET!r} — all | maintenance | purchasing")
SERVER_NAMES = {"all": "hyd-enterprise-mcp", "maintenance": "hyd-enterprise-maint-mcp", "purchasing": "hyd-enterprise-purchase-mcp"}
WHAT = {"all": "업무 시스템(ERP · MES · CMMS · QMS · SCM · EMS)", "maintenance": "보전 업무(CMMS 정비 계획 · 운전시간 계수기 · 작업지시 · MES 생산 오더)",
        "purchasing": "구매 업무(ERP 예비품 재고 · SCM 공급사 견적)"}
mcp = FastMCP(SERVER_NAMES[TOOLSET], instructions=(
    f"유압설비 교육 공장의 {WHAT[TOOLSET]}을 읽는 도구다. 금액은 만원, 시간은 h. "
    "값은 현재 DB 의 것이며 바뀔 수 있다. 쓰기는 없다 — 조치 실행은 사람이 승인한 뒤 process 서비스가 한다."))
def reader_connection():
    return connect_reader(DSN)


tools = EnterpriseTools(reader_connection)
READ = {"readOnlyHint": True, "destructiveHint": False}       # MCP ToolAnnotations — 포털 도구 써 보기는 readOnlyHint=true 만 부른다 (procsvc/mcp_check.py)

Asset = Annotated[str, Field(description="설비 코드 (HYD-01 | HYD-02 | HYD-03)")]


@mcp.tool(annotations=READ)
def mes_orders(asset: Asset) -> dict:
    """MES: 이 설비가 지금 돌리는 생산오더 (납기까지 남은 시간 due_in_h, 남은 수량, 시간당 생산 가치, 대체 설비)."""
    return guarded(tools.read)("mes_orders", asset=asset)


@mcp.tool(annotations=READ)
def erp_contract(asset: Asset) -> dict:
    """ERP: 그 오더의 계약 조건 (고객 등급, 납기 지연 시 시간당 보상 penalty_per_h, 고장 비용, 클레임 비용)."""
    return guarded(tools.read)("erp_contract", asset=asset)


@mcp.tool(annotations=READ)
def erp_inventory(asset: Asset) -> dict:
    """ERP: 완제품 재고 (품목, 수량, 출하 소요 시간)."""
    return guarded(tools.read)("erp_inventory", asset=asset)


@mcp.tool(annotations=READ)
def cmms_history(asset: Asset) -> dict:
    """CMMS: 정비 기준(세척 주기 · 비용 · 다음 야간 정비창)과 과거 작업지시, 발행된 작업지시."""
    return guarded(tools.read)("cmms_history", asset=asset)


@mcp.tool(annotations=READ)
def qms_lots(asset: Asset) -> dict:
    """QMS: 고온 구간에 생산된 로트와 검사 비용 · 불량 확률 · 클레임."""
    return guarded(tools.read)("qms_lots", asset=asset)


@mcp.tool(annotations=READ)
def scm_suppliers(part: Annotated[str, Field(description="부품 번호 (기본 P-CLR-CORE 쿨러 코어)")] = "P-CLR-CORE") -> dict:
    """SCM: 부품 표준단가와 공급사 견적 (가격 · 고장률 · 납기 · 승인 공급사 여부 avl)."""
    return guarded(tools.read)("scm_suppliers", part=part)


@mcp.tool(annotations=READ)
def ems_demand() -> dict:
    """EMS: 오늘 오후 전력 수요 대 계약 전력, 팬 증속 부하, 피크 시간대."""
    return guarded(tools.read)("ems_demand")


@mcp.tool(annotations=READ)
def spare_stock(part: Annotated[str | None, Field(description="부품 번호 (예: P-PMP-SEAL). 비우면 모든 중요 예비품")] = None) -> dict:
    """ERP: 중요 예비품 재고 — 실물 · 예약 · 가용(실물-예약) · 입고 예정 · 재주문점 · 목표 재고 · 필요량(목표-가용-입고 예정) · 재주문점 이탈 여부와 최근 재고 이동."""
    return guarded(tools.read)("spare_stock", part=part)


@mcp.tool(annotations=READ)
def part_quotes(part: Annotated[str, Field(description="부품 번호 (예: P-PMP-SEAL 펌프 축 씰 키트)")] = "P-PMP-SEAL") -> dict:
    """SCM: 부품별 공급사 견적 — 단가(만원) · 불량률 · 리드타임(일) · 승인 공급사(avl). 발주 금액 = 단가 × 수량."""
    return guarded(tools.read)("part_quotes", part=part)


@mcp.tool(annotations=READ)
def maintenance_windows(asset: Asset) -> dict:
    """CMMS: 다가오는 정비창(야간 정비창 · 주말 계획 정지)의 id · 시작 · 끝 · 지금부터 몇 시간, 등록된 정비 일정."""
    return guarded(tools.read)("maintenance_windows", asset=asset)


@mcp.tool(annotations=READ)
def pm_status(asset: Annotated[str | None, Field(description="설비 코드 (HYD-01 | HYD-02 | HYD-03). 비우면 세 대 모두")] = None) -> dict:
    """CMMS: 정기 정비 계획 · 운전시간 계수기 — 마지막 정기 정비 뒤 운전시간 · 주기 · 허용 오차 · 기한까지(h) · 허용 한계까지(h) · 예정된 정비 시간
    (야간 · 주말 · 월간)까지(h)와 한계 안 여부 · 묶음 후보 설비 · 야간 정비 인력 · 정비 부품(씰 키트)을 쓰면 재고가 재주문점보다 얼마나 남는지."""
    return guarded(tools.read)("pm_status", asset=asset)


@mcp.tool(annotations=READ)
def describe_schema() -> dict:
    """현재 ent 원천의 인용 식별자·타입·주석·키 관계를 DDL 문자열로 읽는다 ({result: ok, document: "<DDL>"}). 조회/적재용이며 DB 백업은 아니다."""
    return guarded(tools.describe_schema)()


@mcp.tool(annotations=READ)
def describe_catalog() -> dict:
    """현재 DB의 실제 컬럼 의미(주석)·정밀도·기본값·키 관계와 table/view 구분. 없는 의미는 추측하지 않는다."""
    return guarded(tools.describe_catalog)()


@mcp.tool(annotations=READ)
def query(sql: Annotated[str, Field(description="ent 스키마에 대한 SELECT 한 문장. 쓰기 · 시스템 스키마 · 다중 문장은 거절된다. 최대 200행")]) -> dict:
    """읽기 전용 SQL 실행 (규칙 조건을 데이터에 대어 볼 때). {result: ok, document: {statement, columns, rows, row_count}} 를 돌려준다. 거절은 error_kind INVALID, DB 오류는 UNKNOWN."""
    return guarded(tools.query)(sql=sql)


if TOOLSET != "all":
    # 나눈 서버는 자기 도구만 남긴다(도구 정의 · 표시는 위 한 곳 — 시험이 이 파일의 표시를 센다)
    import asyncio as _asyncio
    for _name in [t for t in _asyncio.run(mcp.get_tools()) if t not in TOOLSETS[TOOLSET]]:
        mcp.remove_tool(_name)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request):
    """compose healthcheck (the /mcp endpoint itself needs MCP headers, so a plain GET there is not a health probe)."""
    from starlette.responses import JSONResponse
    try:
        with reader_connection() as c:
            role, readonly = c.execute("select current_user, current_setting('transaction_read_only')").fetchone()
        return JSONResponse({"ok": readonly == 'on', "role": role, "read_only": readonly == 'on'}, status_code=200 if readonly == 'on' else 503)
    except (psycopg.Error, RuntimeError) as e:
        return JSONResponse({"ok": False, "error": str(e).splitlines()[0][:120]}, status_code=503)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8199")), path="/mcp", uvicorn_config={"ws": "none"})
