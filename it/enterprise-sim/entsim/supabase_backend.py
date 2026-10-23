"""enterprise-sim backed by the Supabase `ent` schema (ENTERPRISE_BACKEND=supabase).

Same HTTP contract as the in-memory backend (data.py + state.py): reads return {"system", "facts", "records"},
POST /api/exec runs one approved skill transaction idempotently. The difference is where the truth lives — in the
business DB the agent also reads through enterprise-mcp — so what the agent saw and what the process changed are
the same rows (회의 L350~353: 업무 데이터는 RDB 에).
"""
from __future__ import annotations

import json
from typing import Callable

from .state import snapshot_view

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
        tables: dict = {}
        with self._connect() as conn, conn.cursor() as cur:
            # A086: hours are computed from the stored due/free times; the frozen legacy columns are not shown
            cur.execute("select to_jsonb(o) - 'due_in_h' - 'alt_free_h' || jsonb_build_object('due_in_h', ent.hours_from_now(o.due_at), "
                        "'alt_free_h', ent.hours_from_now(o.alt_free_at)) from ent.production_orders o order by o.order_id")
            orders = [_json(r[0]) for r in cur.fetchall()]
            for table in WRITE_TABLES:
                cur.execute(f"select to_jsonb(x) from ent.{table} x order by x.created_at desc")
                tables[table] = [_json(r[0]) for r in cur.fetchall()]
        return snapshot_view(orders, tables)        # 메모리 백엔드와 같은 한 모양(점검 E9)

    def reset_spare_stock(self, part: str | None = None) -> dict:
        return self._scenario_reset("ent.reset_spare_stock", part)

    def reset_pm_counters(self, asset: str | None = None) -> dict:
        return self._scenario_reset("ent.reset_pm_counters", asset)

    def _scenario_reset(self, fn: str, key: str | None) -> dict:
        """모르는 부품 · 설비면 아무것도 바꾸지 않고 KeyError(메모리 백엔드와 같이 404) — 예전에는 facts 가 빈 200 이었다(점검 E11)."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"select {fn}(%s)", (key,))
            out = _json(cur.fetchone()[0])
            if key is not None and (not out or out.get("facts") is None):
                conn.rollback()
                raise KeyError(key)
            conn.commit()
        return out

    def reset(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("select ent.reset_executions()")
            conn.commit()

    def reanchor(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("select ent.reanchor_scenario_times()")
            conn.commit()

    def scenario_times_stale(self) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            try:
                cur.execute("select ent.scenario_times_stale()")
            except Exception as e:                       # 연결 드라이버를 이 모듈이 고르지 않는다(connect 주입) — SQLSTATE 로 가린다
                if getattr(e, 'sqlstate', None) != '42883':   # undefined_function
                    raise
                # supabase start 는 이미 있는 업무 DB 에 새 마이그레이션을 적용하지 않는다(2026-10-23 실측) — 코드만 새로 받은 PC 는 여기서 멈춘다
                raise RuntimeError("업무 DB 마이그레이션이 이 코드보다 오래됐습니다(ent.scenario_times_stale 없음, 20261023000061 미적용). "
                                   "저장소 폴더에서 `cd it/supabase && npx -y supabase@2.119.0 migration up` 을 한 번 실행한 뒤 다시 켜세요") from e
            return bool(cur.fetchone()[0])

    def archive(self, ref: str | None = None) -> dict:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("select ent.execution_archive_read(%s)", (ref,))
            return _json(cur.fetchone()[0])

    def ping(self) -> bool:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("select count(*) from ent.assets")
                return cur.fetchone()[0] > 0
        except Exception:  # noqa: BLE001
            return False

