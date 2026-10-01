"""enterprise-sim (L9 연계 대상): mock ERP · MES · CMMS · QMS · SCM · EMS in one small process.

The agent reaches these endpoints only through InfoType nodes of the ontology (which system holds which fact);
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
reg = Registry()
c_reads = reg.counter("enterprise_reads_total", "reads by system")
c_exec = reg.counter("enterprise_exec_total", "executed skills by system")
st = EnterpriseState(os.getenv("ENTERPRISE_STATE_PATH"))
app = make_app("enterprise-sim (mock ERP/MES/CMMS/QMS/SCM/EMS for L7-L9 scenarios)", reg, lambda: {"ok": True, "transactions": len(st.transactions())})


def _read(system: str, fn, *args):
    try:
        out = fn(*args)
    except KeyError:
        raise HTTPException(404, f"unknown asset {args[0] if args else ''}")
    c_reads.inc(system=system)
    return out


@app.get("/mes/orders")
def mes_orders(asset: str = Query("HYD-01")):
    out = _read("MES", data.mes_orders, asset)
    out["records"] = [o for o in st.snapshot()["mes"]["orders"] if o["asset"] == asset or o.get("moved_from") == asset] or out["records"]
    return out


@app.get("/erp/contract")
def erp_contract(asset: str = Query("HYD-01")):
    return _read("ERP", data.erp_contract, asset)


@app.get("/erp/inventory")
def erp_inventory(asset: str = Query("HYD-01")):
    return _read("ERP", data.erp_inventory, asset)


@app.get("/cmms/history")
def cmms_history(asset: str = Query("HYD-01")):
    return _read("CMMS", data.cmms_history, asset)


@app.get("/qms/lots")
def qms_lots(asset: str = Query("HYD-01")):
    return _read("QMS", data.qms_lots, asset)


@app.get("/scm/suppliers")
def scm_suppliers(part: str = Query("P-CLR-CORE")):
    return _read("SCM", data.scm_suppliers, part)


@app.get("/ems/demand")
def ems_demand():
    return _read("EMS", data.ems_demand)


@app.post("/api/exec")
def execute(req: dict):
    try:
        tx = st.execute(req)
    except ValueError as e:
        raise HTTPException(400, str(e))
    c_exec.inc(system=tx["system"])
    log.info("exec %s %s -> %s (%s)", tx["skill"], tx["asset"], tx["ref"], tx["decision"])
    return tx


@app.get("/api/transactions")
def transactions():
    return st.transactions()


@app.get("/api/state")
def snapshot():
    return st.snapshot()


@app.post("/api/reset")
def reset():
    st.reset()
    return {"ok": True}
