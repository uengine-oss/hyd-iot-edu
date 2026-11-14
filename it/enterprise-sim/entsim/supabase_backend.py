"""enterprise-sim backed by the Supabase `ent` schema — 업무 데이터의 한 벌.

reads return {"system", "facts", "records"}, POST /api/exec runs one approved skill transaction idempotently. The difference is where the truth lives — in the
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
WRITE_TABLES = ("work_orders", "purchase_requests", "goods_receipts")


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
        """승인된 거래 하나. 되돌리기는 원거래 id(compensates)를 싣고 온다 — 그 모양 하나로 업무 DB 의 되돌리기 함수를 고른다(스킬 이름 표를
        여기 두지 않는다: 2026-10-30 검진 G2-01, 손 표에 원문 정비 범위 취소가 빠져 늘 「없는 거래」로 거절됐다). 어느 거래가 되돌릴 수 있는지는
        업무 DB 함수가 정한다."""
        fn = "ent.exec_compensation" if req.get("compensates") else "ent.exec_skill"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"select {fn}(%s::jsonb)", (json.dumps(req, ensure_ascii=False),))
            tx = _json(cur.fetchone()[0])
            conn.commit()
        return tx

    #: 지금 업무 시스템이 다루지 않는 옛 거래(마이그레이션 069 가 지운 표본 거래가 옛 DB 에 남긴 행)의 되돌리기 까닭
    LEGACY_REASON = "지금 업무 시스템이 다루지 않는 옛 거래라 되돌리지 않는다"

    def transactions(self, decision: str | None = None) -> list[dict]:
        """거래 원장. 원거래 행마다 되돌리기 계약(ent.skill_contracts)을 싣는다: inverse = 되돌리기 스킬(없으면 null),
        irreversible_reason = 되돌릴 수 없는 까닭(되돌릴 수 있으면 null). 되돌리기 행(compensates 있음)은 둘 다 null."""
        with self._connect() as conn, conn.cursor() as cur:
            query = ("select t.id, t.t, t.system, t.skill, t.ref, t.detail, t.asset, t.decision_id, t.option_id, t.requested_by, "
                     "nullif(t.compensates, ''), t.before, t.after, "
                     "case when coalesce(t.compensates, '') = '' and c.kind is distinct from 'inverse' then c.inverse end, "
                     "case when coalesce(t.compensates, '') = '' and c.kind is distinct from 'inverse' and c.inverse is null "
                     "then coalesce(c.irreversible_reason, %s) end "
                     "from ent.transactions t left join ent.skill_contracts c on c.skill = t.skill")
            if decision is None:
                cur.execute(query + " order by t.t desc limit 300", (self.LEGACY_REASON,))
            else:
                cur.execute(query + " where t.decision_id=%s order by t.t, t.id", (self.LEGACY_REASON, decision))
            rows = cur.fetchall()
        keys = ("id", "t", "system", "skill", "ref", "detail", "asset", "decision", "option", "by", "compensates", "before", "after",
                "inverse", "irreversible_reason")
        return [dict(zip(keys, (str(v) if k == "t" else v for k, v in zip(keys, r)))) for r in rows]

    #: /api/state 의 표마다 최근 행 수 — 포털 처리 탭은 6 · 12행만 그리는데 2.5초마다 표 전체를 읽었다(검진 G2-11)
    SNAPSHOT_ROWS = 50

    def snapshot(self) -> dict:
        tables: dict = {}
        with self._connect() as conn, conn.cursor() as cur:
            # A086: hours are computed from the stored due/free times; the frozen legacy columns are not shown
            cur.execute("select to_jsonb(o) - 'due_in_h' - 'alt_free_h' || jsonb_build_object('due_in_h', ent.hours_from_now(o.due_at), "
                        "'alt_free_h', ent.hours_from_now(o.alt_free_at)) from ent.production_orders o order by o.order_id")
            orders = [_json(r[0]) for r in cur.fetchall()]
            for table in WRITE_TABLES:
                cur.execute(f"select to_jsonb(x) from ent.{table} x order by x.created_at desc limit %s", (self.SNAPSHOT_ROWS,))
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
                # 시작(scripts/start_all.sh)이 마이그레이션을 적용한다 — 그 단계를 건너뛰고 컨테이너만 켠 PC 는 여기서 멈춘다
                raise RuntimeError("업무 DB 가 이 코드보다 오래됐습니다(ent.scenario_times_stale 없음 — 마이그레이션 20261023000061 미적용). "
                                   "시스템을 끈 뒤 시작 파일(시작.bat · 시작.command)로 다시 켜면 업무 DB 업데이트(마이그레이션)를 함께 합니다") from e
            return bool(cur.fetchone()[0])

    def health(self) -> dict:
        """건강 검사: 연결 한 번에 설비 행 수 · 거래 수(2026-10-30 검진 G2-20 — 예전에는 연결 두 번 + 거래 300행을 읽어 300에서 잘린 수를 냈다)."""
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("select (select count(*) from ent.assets), (select count(*) from ent.transactions)")
                assets, transactions = cur.fetchone()
        except Exception as e:  # noqa: BLE001 — 건강 검사는 까닭을 담아 503 으로 답한다(삼키지 않는다)
            return {"ok": False, "error": (str(e).splitlines() or [type(e).__name__])[0][:200]}
        return {"ok": assets > 0, "assets": assets, "transactions": transactions}
