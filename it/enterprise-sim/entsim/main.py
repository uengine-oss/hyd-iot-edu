"""enterprise-sim (L9 연계 대상): mock ERP · MES · CMMS · QMS · SCM · EMS in one small process.

Two backends, one HTTP contract:
  ENTERPRISE_BACKEND=memory   (default) data.py dictionaries + SQLite state — no other service needed
  ENTERPRISE_BACKEND=supabase the Supabase `ent` schema (it/supabase) — the same rows the agent reads through enterprise-mcp
The agent reaches these endpoints only through InputData nodes of the ontology (which system holds which fact);
only the process service may POST /api/exec after a human approved a decision.
"""
import logging
import os

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse

from hydcommon.metrics import Registry
from hydcommon.service import make_app
from . import data
from .state import EnterpriseState, memory_tables, snapshot_view

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
                       "cmms_history": self._cmms_history, "cmms_tasks": data.cmms_tasks, "qms_lots": data.qms_lots, "scm_suppliers": data.scm_suppliers, "ems_demand": data.ems_demand,
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

    def _cmms_history(self, asset: str) -> dict:
        data._check(asset)                                           # 모르는 설비는 KeyError(404) — 상태를 읽기 전에
        done, orders = self.st.maintenance_records(asset)
        return data.cmms_history(asset, done, orders)

    def read(self, name: str, **params) -> dict:
        fn = self._reads[name]
        return fn(*[v for v in params.values()]) if params else fn()

    def execute(self, req: dict) -> dict:
        return self.st.execute(req)

    def transactions(self, decision: str | None = None) -> list[dict]:
        return self.st.transactions(decision)

    def snapshot(self) -> dict:
        snap = self.st.snapshot()
        # A086: hours as of now. 칸 이름 · 표 이름은 업무 DB 백엔드와 같은 한 모양(state.snapshot_view, 점검 E9)
        return snapshot_view([data.current_order(o) for o in snap["mes"]["orders"]], memory_tables(snap))

    def reset_spare_stock(self, part: str | None = None) -> dict:
        return self.st.reset_spare_stock(part)

    def reset_pm_counters(self, asset: str | None = None) -> dict:
        return self.st.reset_pm_counters(asset)

    def reset(self) -> None:
        self.st.reset()
        self.st.reanchor()       # A086: the teaching scenario's times start again from now (Supabase: ent.reanchor_scenario_times)

    def reanchor(self) -> None:
        self.st.reanchor()       # 저장 상태에도 남겨 재시작이 기준점을 옮기지 않는다(점검 E8)

    def scenario_times_stale(self) -> bool:
        return data.scenario_times_stale()

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


try:                                                    # 업무 DB 백엔드의 연결 · 잠금 · 시간 초과(일시 장애) 예외
    import psycopg
    _DB_UNAVAILABLE: tuple = (psycopg.OperationalError, psycopg.InterfaceError)
except ImportError:                                     # psycopg 없는 메모리 전용 설치 — 이 예외가 날 곳이 없다
    _DB_UNAVAILABLE = ()


def _db_unavailable_detail(e: Exception) -> str:
    msg = (str(e).splitlines() or [type(e).__name__])[0][:250]
    state = getattr(e, "sqlstate", None)
    if state is None or str(state).startswith("08"):
        return f"업무 DB에 연결하지 못했습니다 — 잠시 뒤 다시 시도하세요: {msg}"
    return f"업무 DB가 지금 처리하지 못했습니다({state}) — 잠시 뒤 다시 시도하세요: {msg}"


def _is_db_unavailable(e: Exception) -> bool:
    return isinstance(e, _DB_UNAVAILABLE) or type(e).__name__ in ("OperationalError", "InterfaceError")


async def _db_unavailable(_request: Request, e: Exception):
    """업무 DB 일시 장애는 거절 · 서버 오류가 아니라 503(다시 시도) — 조회 · 초기화 · 기준점 끝점 모두(점검 E11, /api/exec 는 아래에서 같은 규칙)."""
    return JSONResponse(status_code=503, content={"detail": _db_unavailable_detail(e)})


for _cls in _DB_UNAVAILABLE:
    app.add_exception_handler(_cls, _db_unavailable)


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


def _scenario_reset(fn, arg):
    """B · C [초기화]가 다른 시나리오가 잡은 수량 때문에 되돌릴 수 없으면(예: B 오더가 시작값보다 많이 출고) 이유를 그대로 409 로 낸다 —
    두 백엔드 모두 'INVALID:' 로 시작하는 거절이다(2026-10-23 점검 E1 · E2 · E3)."""
    try:
        return fn(arg)
    except KeyError as e:                       # 모르는 부품 · 설비: 두 백엔드 모두 404(메모리는 KeyError → 500, 업무 DB 는 빈 200 이었다, 점검 E11)
        raise HTTPException(404, f"unknown {e.args[0] if e.args else arg}")
    except Exception as e:  # noqa: BLE001 — 메모리 ValueError · 업무 DB 22023
        msg = str(e).splitlines()[0] if str(e) else type(e).__name__
        if msg.startswith("INVALID:"):
            raise HTTPException(409, msg[:300])
        raise


@app.post("/erp/spare/reset")
def reset_spare(body: dict | None = None):
    """수업 초기화(포털 [초기화] → process /api/scenario/C/reset): 그 부품의 열린 발주를 닫고 재고를 기준값으로 — 진행 중 정기 정비
    오더가 잡은 수량은 남긴다. body = {part_no} (없으면 전부)."""
    return _scenario_reset(ent.reset_spare_stock, (body or {}).get("part_no"))


@app.get("/cmms/pm_status")
def pm_status(asset: str | None = Query(default=None)):
    """CMMS: 정기 정비 계획 · 운전시간 계수기(설비별 한 행: 운전시간 · 주기 · 허용 오차 · 기한까지 · 예정된 정비 시간까지 · 묶음 후보 · 부품 영향)."""
    return _read("CMMS", "pm_status", asset=asset)


@app.post("/cmms/pm/reset")
def pm_reset(body: dict | None = None):
    """수업 초기화(포털 [초기화] → process /api/scenario/B/reset): 운전시간 계수기 · 이번 회차 오더 표시를 수업 시작값으로. body = {asset} (없으면 전부)."""
    return _scenario_reset(ent.reset_pm_counters, (body or {}).get("asset"))


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
        if _is_db_unavailable(e):    # 연결 장애 · 교착 · 시간 초과는 거절이 아니다(2026-10-23 점검: 400으로 나가 「거절」로 읽혔다)
            raise HTTPException(503, _db_unavailable_detail(e))
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
    # 스택이 뜰 때, 기준점이 이미 지났으면(가장 이른 시나리오 기한이 지금 이전) 지금으로 — 오래 떠 있던 DB 의 '납기까지 −1 h' 같은 지난 시각으로
    # 판단하지 않게. 지나지 않았으면 옮기지 않는다: 예정된 정비 시간 id 가 기준점 시각을 품어, 재시작(compose 재생성 · OOM)이 옮기면 승인 대기 중인
    # B 카드의 창이 사라졌다(점검 E8). 수업 중 기준점은 process 가 설비 처리 건이 없을 때만 옮긴다(scenario_buttons.may_reanchor).
    if ent.scenario_times_stale():
        log.info("scenario time anchor has passed — re-anchoring to now")
        ent.reanchor()
