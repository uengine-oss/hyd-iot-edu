"""Business-DB tools over the Supabase `ent` schema — what the WMS sample's wms-mcp is to ProcessGPT.

Reads only. Every tool answers in the envelope the WMS sample uses ({"result": "ok", "document": …} / {"result": "error",
"error_kind", "message"}); the document of a named read is the {"system", "facts", "records"} record the agent's decision
engine already understands (enterprise-sim), so the ontology InputData -SOURCED_FROM-> System links keep working.
`describe_schema` hands the agent the DDL-level view it needs to write its own SELECT (`query`); `query` runs it through
sql_guard on a read-only, time-boxed connection.
"""
from __future__ import annotations

import json
from typing import Callable

from .sql_guard import guard
from .catalog import CATALOG_SQL, render

READ_RPCS = {
    "mes_orders": ("ent.mes_orders", ("asset",)),
    "erp_contract": ("ent.erp_contract", ("asset",)),
    "erp_inventory": ("ent.erp_inventory", ("asset",)),
    "cmms_history": ("ent.cmms_history", ("asset",)),
    "qms_lots": ("ent.qms_lots", ("asset",)),
    "scm_suppliers": ("ent.scm_suppliers", ("part",)),
    "ems_demand": ("ent.ems_demand", ()),
}

def ok(document) -> dict:
    return {"result": "ok", "document": document}


def error(kind: str, message: str, **extra) -> dict:
    """kind: INVALID (rejected input) | UNKNOWN (database / unexpected) — the WMS sample's error_kind vocabulary."""
    return {"result": "error", "error_kind": kind, "message": message, **extra}


class EnterpriseTools:
    def __init__(self, connect: Callable[[], object], statement_timeout_ms: int = 5000):
        self._connect, self._timeout_ms = connect, statement_timeout_ms

    def _begin_read(self, cur):
        cur.execute("set transaction read only")
        cur.execute(f"set local statement_timeout = {int(self._timeout_ms)}")
        cur.execute("set local search_path = pg_catalog, ent")

    # ---- fixed reads (the ontology's named sources)
    def read(self, name: str, **params) -> dict:
        fn, arg_names = READ_RPCS[name]
        args = [params.get(a) for a in arg_names]
        with self._connect() as conn, conn.cursor() as cur:
            self._begin_read(cur)
            cur.execute(f"select {fn}({', '.join(['%s'] * len(args))})", args)
            row = cur.fetchone()
        value = row[0] if row else None
        return ok(value if isinstance(value, dict) else json.loads(value or "{}"))

    # ---- the agent's own SQL (회의 6번)
    def describe_schema(self) -> str:
        """Quoted query/ingestion DDL with actual comments, types and constraints."""
        return render(self.describe_catalog()['document'])

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
        return ok({"statement": statement, "columns": columns, "rows": rows, "row_count": len(rows)})
