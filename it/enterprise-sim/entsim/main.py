"""enterprise-sim (L9 연계 대상): mock ERP · MES · CMMS · QMS · SCM · EMS in one small process.

Two backends, one HTTP contract:
  ENTERPRISE_BACKEND=memory   (default) data.py dictionaries + SQLite state — no other service needed
  ENTERPRISE_BACKEND=supabase the Supabase `ent` schema (it/supabase) — the same rows the agent reads through enterprise-mcp
The agent reaches these endpoints only through InputData nodes of the ontology (which system holds which fact);
only the process service may POST /api/exec after a human approved a decision.
"""
import logging
import os

from fastapi import HTTPException, Query

from hydcommon.metrics import Registry
from hydcommon.service import make_app
from . import data
from .state import EnterpriseState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("enterprise-sim")
BACKEND = os.getenv("ENTERPRISE_BACKEND", "memory")
reg = Registry()
c_reads = reg.counter("enterprise_reads_total", "reads by system")
c_exec = reg.counter("enterprise_exec_total", "executed skills by system")


class MemoryEnterprise:
    """data.py reads + state.py writes behind the same four methods the Supabase backend has."""

    def __init__(self):
        self.st = EnterpriseState(os.getenv("ENTERPRISE_STATE_PATH"))
        self._reads = {"mes_orders": self._mes_orders, "erp_contract": data.erp_contract, "erp_inventory": data.erp_inventory,
                       "cmms_history": data.cmms_history, "cmms_tasks": data.cmms_tasks, "qms_lots": data.qms_lots, "scm_suppliers": data.scm_suppliers, "ems_demand": data.ems_demand,
                       # C2: 예비품 재고(바뀌는 값 → state) · 부품별 견적 · 다가오는 예정된 정비 시간 · 발주 한 건
                       "spare_stock": self.st.spare_stock, "part_quotes": data.part_quotes, "maintenance_windows": data.maintenance_windows,
                       "purchase_order": self.st.purchase_order,
                       # C2 시나리오 B: 정기 정비 계획 · 운전시간 계수기 (설비별 한 행)
                       "pm_status": self.st.pm_status}

    def _mes_orders(self, asset: str) -> dict:
        out = data.mes_orders(asset)
        live = [data.current_order(o) for o in self.st.snapshot()["mes"]["orders"] if o["asset"] == asset or o.get("moved_from") == asset]
        out["records"] = live or out["records"]
        return out

    def read(self, name: str, **params) -> dict:
        fn = self._reads[name]
        return fn(*[v for v in params.values()]) if params else fn()

    def execute(self, req: dict) -> dict:
        return self.st.execute(req)

    def transactions(self, decision: str | None = None) -> list[dict]:
        return self.st.transactions(decision)

    def snapshot(self) -> dict:
        snap = self.st.snapshot()
        snap["mes"]["orders"] = [data.current_order(o) for o in snap["mes"]["orders"]]   # A086: hours as of now
        return snap

    def reset_spare_stock(self, part: str | None = None) -> dict:
        return self.st.reset_spare_stock(part)

    def reset_pm_counters(self, asset: str | None = None) -> dict:
        return self.st.reset_pm_counters(asset)

    def reset(self) -> None:
        self.st.reset()
        data.reanchor()          # A086: the teaching scenario's times start again from now (Supabase: ent.reanchor_scenario_times)

    def reanchor(self) -> None:
        data.reanchor()

    def archive(self, ref: str | None = None) -> dict:
        return self.st.archive(ref)

    def ping(self) -> bool:
        return True


def _backend():
    if BACKEND == "supabase":
        import psycopg
        from .supabase_backend import SupabaseEnterprise
        dsn = os.getenv("SUPABASE_DSN", "postgresql://postgres:postgres@host.docker.internal:54322/postgres")
        return SupabaseEnterprise(lambda: psycopg.connect(dsn, connect_timeout=5))
    return MemoryEnterprise()


ent = _backend()
app = make_app(f"enterprise-sim (mock ERP/MES/CMMS/QMS/SCM/EMS for L7-L9 scenarios, backend={BACKEND})", reg,
               lambda: {"ok": ent.ping(), "backend": BACKEND, "transactions": len(ent.transactions()) if ent.ping() else None})


def _read(system: str, name: str, **params):
    try:
        out = ent.read(name, **params)
    except KeyError:
        raise HTTPException(404, f"unknown {next(iter(params.values()), '')}")
    c_reads.inc(system=system)
    return out


@app.get("/mes/orders")
def mes_orders(asset: str = Query("HYD-01")):
    return _read("MES", "mes_orders", asset=asset)


@app.get("/erp/contract")
def erp_contract(asset: str = Query("HYD-01")):
    return _read("ERP", "erp_contract", asset=asset)


@app.get("/erp/inventory")
def erp_inventory(asset: str = Query("HYD-01")):
    return _read("ERP", "erp_inventory", asset=asset)


@app.get("/cmms/history")
def cmms_history(asset: str = Query("HYD-01")):
    return _read("CMMS", "cmms_history", asset=asset)


@app.get("/cmms/tasks")
def cmms_tasks(asset: str = Query("HYD-01")):
    return _read("CMMS", "cmms_tasks", asset=asset)


@app.get("/qms/lots")
def qms_lots(asset: str = Query("HYD-01")):
    return _read("QMS", "qms_lots", asset=asset)


@app.get("/scm/suppliers")
def scm_suppliers(part: str = Query("P-CLR-CORE")):
    return _read("SCM", "scm_suppliers", part=part)


@app.get("/ems/demand")
def ems_demand():
    return _read("EMS", "ems_demand")


# ---------------------------------------------------------------- C2 (확정 TODO C): 예비품 재고 · 견적 · 예정된 정비 시간 · 발주 조회
@app.get("/erp/spare_stock")
def spare_stock(part: str | None = Query(default=None)):
    """ERP: 중요 예비품 재고(가용 = 실물 - 예약, 재주문점 · 목표 · 입고 예정 · 필요량)와 최근 재고 이동. part 없으면 전부."""
    return _read("ERP", "spare_stock", part=part)


@app.get("/scm/quotes")
def part_quotes(part: str = Query("P-PMP-SEAL")):
    """SCM: 부품별 공급사 견적(단가 · 불량률 · 리드타임 · AVL)."""
    return _read("SCM", "part_quotes", part=part)


@app.get("/cmms/windows")
def maintenance_windows(asset: str = Query("HYD-02")):
    """CMMS: 다가오는 예정된 정비 시간(야간 · 주말)과 등록된 일정."""
    return _read("CMMS", "maintenance_windows", asset=asset)


@app.get("/erp/purchase_orders/{ref}")
def purchase_order(ref: str):
    """ERP: 발주 한 건(수량 · 금액 · 입고 예정 · 상태)과 그 입고 기록."""
    return _read("ERP", "purchase_order", ref=ref)


@app.post("/erp/spare/reset")
def reset_spare(body: dict | None = None):
    """수업 초기화(포털 [초기화] → process /api/scenario/C/reset): 예비품 재고를 기준값으로. body = {part_no} (없으면 전부)."""
    return ent.reset_spare_stock((body or {}).get("part_no"))


@app.get("/cmms/pm_status")
def pm_status(asset: str | None = Query(default=None)):
    """CMMS: 정기 정비 계획 · 운전시간 계수기(설비별 한 행: 운전시간 · 주기 · 허용 오차 · 기한까지 · 예정된 정비 시간까지 · 묶음 후보 · 부품 영향)."""
    return _read("CMMS", "pm_status", asset=asset)


@app.post("/cmms/pm/reset")
def pm_reset(body: dict | None = None):
    """수업 초기화(포털 [초기화] → process /api/scenario/B/reset): 운전시간 계수기 · 이번 회차 오더 표시를 수업 시작값으로. body = {asset} (없으면 전부)."""
    return ent.reset_pm_counters((body or {}).get("asset"))


@app.post("/api/exec")
def execute(req: dict):
    try:
        tx = ent.execute(req)
    except ValueError as e:
        # A143 (remaining-sweep 16): the memory backend raises the idempotency conflict as ValueError; same code as supabase
        msg = str(e)
        raise HTTPException(409 if "idempotency" in msg else 400, msg)
    except Exception as e:  # noqa: BLE001 — database errors from ent.exec_skill (unknown skill, idempotency conflict)
        msg = str(e).splitlines()[0]
        raise HTTPException(409 if "idempotency" in msg else 400, msg[:300])
    c_exec.inc(system=tx["system"])
    log.info("exec %s %s -> %s (%s)", tx["skill"], tx["asset"], tx["ref"], tx.get("decision"))
    return tx


@app.get("/api/transactions")
def transactions(decision: str | None = Query(default=None, min_length=1)):
    return ent.transactions(decision)


@app.get("/api/state")
def snapshot():
    return ent.snapshot()


@app.post("/api/reset")
def reset():
    """수업 · 검사 초기화: 운영 상태(진행 중 오더 · 재고 · 계수기 · 시각 기준점)를 시작값으로. 실행 기록은 지우지 않고 보관한다(GET /api/archive)."""
    ent.reset()
    return {"ok": True}


@app.post("/api/reanchor")
def reanchor():
    """시나리오 시각 기준점을 지금으로(생산 오더 납기 · 예정된 정비 시간 · 출하). 시나리오를 시작하거나 초기화할 때 process 가 부른다."""
    ent.reanchor()
    return {"ok": True}


@app.get("/api/archive")
def archive(ref: str | None = Query(default=None)):
    """초기화가 보관한 실행 기록(작업지시 · 발주 · 입고 · 거래 원장). ref = WO · PR · GR · TX id 또는 판단 id."""
    return ent.archive(ref)


@app.on_event("startup")
def _anchor_on_start():
    # 스택이 뜰 때 시나리오 시각 기준점을 지금으로 — 오래 떠 있던 DB 의 '납기까지 −1 h' 같은 지난 시각으로 판단하지 않게
    ent.reanchor()
