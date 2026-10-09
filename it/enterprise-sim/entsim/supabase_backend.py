"""enterprise-sim backed by the Supabase `ent` schema (ENTERPRISE_BACKEND=supabase).

Same HTTP contract as the in-memory backend (data.py + state.py): reads return {"system", "facts", "records"},
POST /api/exec runs one approved skill transaction idempotently. The difference is where the truth lives — in the
business DB the agent also reads through enterprise-mcp — so what the agent saw and what the process changed are
the same rows (회의 L350~353: 업무 데이터는 RDB 에).
"""
from __future__ import annotations

import json
from typing import Callable

READS = {
    "mes_orders": ("ent.mes_orders", ("asset",)), "erp_contract": ("ent.erp_contract", ("asset",)), "erp_inventory": ("ent.erp_inventory", ("asset",)),
    "cmms_history": ("ent.cmms_history", ("asset",)), "cmms_tasks": ("ent.cmms_tasks", ("asset",)), "qms_lots": ("ent.qms_lots", ("asset",)), "scm_suppliers": ("ent.scm_suppliers", ("part",)),
    "ems_demand": ("ent.ems_demand", ()),
    # C2 (migration 20261009000045)
    "spare_stock": ("ent.spare_stock_read", ("part",)), "part_quotes": ("ent.part_quotes_read", ("part",)),
    "maintenance_windows": ("ent.maintenance_windows_read", ("asset",)), "purchase_order": ("ent.purchase_order_read", ("ref",)),
    "pm_status": ("ent.pm_status_read", ("asset",)),
}
WRITE_TABLES = ("work_orders", "purchase_requests", "shipments", "lot_dispositions", "ems_actions", "goods_receipts")


def _json(value):
    return value if isinstance(value, (dict, list)) or value is None else json.loads(value)


class SupabaseEnterprise:
    def __init__(self, connect: Callable[[], object]):
        self._connect = connect

    # ---- reads
    def read(self, name: str, **params) -> dict:
        fn, arg_names = READS[name]
        args = [params.get(a) for a in arg_names]
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"select {fn}({', '.join(['%s'] * len(args))})", args)
            row = cur.fetchone()
        out = _json(row[0]) if row else None
        if not out or out.get("facts") is None:
            raise KeyError(params.get("asset") or params.get("part") or params.get("ref") or name)
        return out

    # ---- writes (process service only)
    def execute(self, req: dict) -> dict:
        from .state import COMPENSATION_SKILLS
        fn = "ent.exec_compensation" if req.get("skill") in COMPENSATION_SKILLS else "ent.exec_skill"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"select {fn}(%s::jsonb)", (json.dumps(req, ensure_ascii=False),))
            tx = _json(cur.fetchone()[0])
            conn.commit()
        return tx

    def transactions(self, decision: str | None = None) -> list[dict]:
        with self._connect() as conn, conn.cursor() as cur:
            query = "select id, t, system, skill, ref, detail, asset, decision_id, option_id, requested_by, compensates, before, after from ent.transactions"
            if decision is None:
                cur.execute(query + " order by t desc limit 300")
            else:
                cur.execute(query + " where decision_id=%s order by t,id", (decision,))
            rows = cur.fetchall()
        keys = ("id", "t", "system", "skill", "ref", "detail", "asset", "decision", "option", "by", "compensates", "before", "after")   # A103
        return [dict(zip(keys, (str(v) if k == "t" else v for k, v in zip(keys, r)))) for r in rows]

    def snapshot(self) -> dict:
        out: dict = {}
        with self._connect() as conn, conn.cursor() as cur:
            # A086: hours are computed from the stored due/free times; the frozen legacy columns are not shown
            cur.execute("select to_jsonb(o) - 'due_in_h' - 'alt_free_h' || jsonb_build_object('due_in_h', ent.hours_from_now(o.due_at), "
                        "'alt_free_h', ent.hours_from_now(o.alt_free_at)) from ent.production_orders o order by o.order_id")
            out["mes"] = {"orders": [_json(r[0]) for r in cur.fetchall()]}
            for table in WRITE_TABLES:
                cur.execute(f"select to_jsonb(x) from ent.{table} x order by x.created_at desc")
                out.setdefault(_system_of(table), {})[table] = [_json(r[0]) for r in cur.fetchall()]
        return out

    def reset_spare_stock(self, part: str | None = None) -> dict:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("select ent.reset_spare_stock(%s)", (part,))
            out = _json(cur.fetchone()[0])
            conn.commit()
        return out

    def reset_pm_counters(self, asset: str | None = None) -> dict:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("select ent.reset_pm_counters(%s)", (asset,))
            out = _json(cur.fetchone()[0])
            conn.commit()
        return out

    def reset(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("select ent.reset_executions()")
            conn.commit()

    def ping(self) -> bool:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("select count(*) from ent.assets")
                return cur.fetchone()[0] > 0
        except Exception:  # noqa: BLE001
            return False


def _system_of(table: str) -> str:
    return {"work_orders": "cmms", "purchase_requests": "erp", "shipments": "erp", "lot_dispositions": "qms", "ems_actions": "ems",
            "goods_receipts": "erp"}[table]
