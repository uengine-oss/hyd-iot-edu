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
                       "cmms_history": data.cmms_history, "qms_lots": data.qms_lots, "scm_suppliers": data.scm_suppliers, "ems_demand": data.ems_demand}

    def _mes_orders(self, asset: str) -> dict:
        out = data.mes_orders(asset)
        live = [o for o in self.st.snapshot()["mes"]["orders"] if o["asset"] == asset or o.get("moved_from") == asset]
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
        return self.st.snapshot()

    def reset(self) -> None:
        self.st.reset()

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


@app.get("/qms/lots")
def qms_lots(asset: str = Query("HYD-01")):
    return _read("QMS", "qms_lots", asset=asset)


@app.get("/scm/suppliers")
def scm_suppliers(part: str = Query("P-CLR-CORE")):
    return _read("SCM", "scm_suppliers", part=part)


@app.get("/ems/demand")
def ems_demand():
    return _read("EMS", "ems_demand")


@app.post("/api/exec")
def execute(req: dict):
    try:
        tx = ent.execute(req)
    except ValueError as e:
        raise HTTPException(400, str(e))
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
    ent.reset()
    return {"ok": True}
