"""Business-DB tools over the Supabase `ent` schema — what the WMS sample's wms-mcp is to ProcessGPT.

Reads only. Every tool answers in the envelope the WMS sample uses ({"result": "ok", "document": …} / {"result": "error",
"error_kind", "message"}); the document of a named read is the {"system", "facts", "records"} record the agent's decision
engine already understands (enterprise-sim), so the ontology InputData -SOURCED_FROM-> System links keep working.
`describe_catalog` (structured) and `describe_schema` (the same metadata rendered as quoted DDL text in `document`) hand
the agent the view it needs to write its own SELECT (`query`); `query` runs it through the shared read-only guard
(hydcommon.sql_read) on a read-only, time-boxed connection. `guarded` turns a DB/connection failure of any tool into the
error envelope (error_kind UNKNOWN) and a refused input (an unknown asset · part, a rejected statement, a bad catalog page)
into INVALID, so a tool never raises a stack trace at the MCP client.
"""
from __future__ import annotations

import functools
import json
from typing import Callable

import psycopg
from hydcommon.tool_result import checked

from hydcommon.sql_read import SqlRejected, guard

from .catalog import CATALOG_SQL, render

READ_RPCS = {
    "mes_orders": ("ent.mes_orders", ("asset",)),
    "erp_contract": ("ent.erp_contract", ("asset",)),
    "erp_inventory": ("ent.erp_inventory", ("asset",)),
    "cmms_history": ("ent.cmms_history", ("asset",)),
    "qms_lots": ("ent.qms_lots", ("asset",)),
    "scm_suppliers": ("ent.scm_suppliers", ("part",)),
    "ems_demand": ("ent.ems_demand", ()),
    # C2 (migration 20261009000045): 예비품 재고 · 부품별 공급사 견적 · 다가오는 예정된 정비 시간
    "spare_stock": ("ent.spare_stock_read", ("part",)),
    "part_quotes": ("ent.part_quotes_read", ("part",)),
    "maintenance_windows": ("ent.maintenance_windows_read", ("asset",)),
    "pm_status": ("ent.pm_status_read", ("asset",)),     # 시나리오 B: 정기 정비 계획 · 운전시간 계수기
}

def ok(document) -> dict:
    return {"result": "ok", "document": document}


def error(kind: str, message: str, **extra) -> dict:
    """kind: INVALID (rejected input) | UNKNOWN (database / unexpected) — the WMS sample's error_kind vocabulary."""
    return {"result": "error", "error_kind": kind, "message": message, **extra}


def guarded(fn):
    """Envelope every failure of a tool: a refused input (ValueError — SqlRejected, an unknown asset · part, a bad catalog page)
    → INVALID, psycopg/connection/runtime errors → UNKNOWN (first line of the DB message, no stack trace). KeyError (unknown
    fixed read name) is a programming error and still raises."""
    @functools.wraps(fn)
    def run(*a, **kw):
        try:
            return fn(*a, **kw)
        except ValueError as e:
            return error("INVALID", f"거절: {e}", **({"statement": kw["sql"]} if "sql" in kw else {}))
        except (psycopg.Error, RuntimeError, OSError) as e:
            return error("UNKNOWN", f"업무 DB 오류: {str(e).splitlines()[0][:200] if str(e) else type(e).__name__}",
                         **({"statement": kw["sql"]} if "sql" in kw else {}))
    return run


class EnterpriseTools:
    def __init__(self, connect: Callable[[], object], statement_timeout_ms: int = 5000):
        self._connect, self._timeout_ms = connect, statement_timeout_ms

    def _begin_read(self, cur):
        cur.execute("set transaction read only")
        cur.execute(f"set local statement_timeout = {int(self._timeout_ms)}")
        cur.execute("set local search_path = pg_catalog, ent")

    # ---- fixed reads (the ontology's named sources)
    def read(self, name: str, **params) -> dict:
        """One named read. 규칙 하나: 업무 DB 함수가 사실(facts)을 돌려주지 않으면 그 대상이 없는 것이다(INVALID) — entsim 의 404 와 같은 규칙.
        비울 수 있는 인자(pm_status 의 설비 · spare_stock 의 부품)는 비우면 함수가 전체를 돌려준다(2026-10-30 검진 G2-04: 설비를 비우면
        「등록되지 않은 설비」로 거절됐고, 없는 부품은 「0건 성공」이었다)."""
        fn, arg_names = READ_RPCS[name]
        args = [params.get(a) for a in arg_names]
        with self._connect() as conn, conn.cursor() as cur:
            self._begin_read(cur)
            cur.execute(f"select {fn}({', '.join(['%s'] * len(args))})", args)
            row = cur.fetchone()
        value = row[0] if row else None
        document = value if isinstance(value, dict) or value is None else json.loads(value)
        if not isinstance(document, dict) or document.get("facts") is None:
            given = ", ".join(f"{a}={params.get(a)}" for a in arg_names if params.get(a) is not None)
            raise ValueError(f"업무 DB 에 그 대상의 자료가 없습니다({given or '값 없음 — 이 조회는 대상이 필요합니다'}). "
                             "실제 설비 코드(HYD-01 · HYD-02 · HYD-03)와 부품 번호(spare_stock 결과)를 확인하세요")
        return ok(document)

    # ---- the agent's own SQL (회의 6번)
    def describe_schema(self) -> dict:
        """Quoted query/ingestion DDL with actual comments, types and constraints, as `document` (a string) in the envelope.
        (It used to return the bare string; FastMCP then sent {"result": "<ddl>"}, colliding with the envelope's
        result=ok|error vocabulary — a client checking result == "ok" saw DDL instead.)"""
        return ok(render(self.describe_catalog()['document']))

    def describe_catalog(self) -> dict:
        """One live catalog statement, restricted to reader-visible ent tables/views."""
        with self._connect() as conn, conn.cursor() as cur:
            self._begin_read(cur)
            cur.execute(CATALOG_SQL)
            row = cur.fetchone()
        return ok(row[0])

    def query(self, sql: str) -> dict:
        """One guarded SELECT on a read-only connection. Returns columns, rows (≤ 200) and the statement actually run."""
        statement = guard(sql)
        with self._connect() as conn, conn.cursor() as cur:
            self._begin_read(cur)
            cur.execute(statement)
            columns = [d.name for d in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
        document = {"statement": statement, "columns": columns, "rows": rows,
                    "row_count": len(rows), "row_limit": 200, "at_row_limit": len(rows) == 200}
        try:
            return ok(checked(document))
        except ValueError as exc:
            raise SqlRejected(str(exc)) from exc
