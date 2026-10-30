"""enterprise-sim (L9 연계 대상): mock ERP · MES · CMMS · QMS · SCM · EMS in one small process.

업무 데이터는 Supabase 의 `ent` 스키마 한 벌이다(it/supabase) — 에이전트가 enterprise-mcp 로 읽는 것과 같은 행(메모리판은 2026-10-30 지움).
The agent reaches these endpoints only through InputData nodes of the ontology (which system holds which fact).
쓰기 끝점(/api/exec · 초기화 · 기준점)은 process 만 부른다 — 요청에 process 만 아는 값(실행 호출 토큰)이 있어야 받는다(하-05).
"""
import hmac
import logging
import os

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse

import psycopg

from hydcommon.metrics import Registry
from hydcommon.service import make_app
from .supabase_backend import SupabaseEnterprise

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("enterprise-sim")
reg = Registry()
c_reads = reg.counter("enterprise_reads_total", "reads by system")
c_exec = reg.counter("enterprise_exec_total", "executed skills by system")


SUPABASE_DSN = os.getenv("SUPABASE_DSN", "postgresql://postgres:postgres@host.docker.internal:54322/postgres")
# 하-05: 쓰기 끝점은 process 만 아는 값(머리글 X-HYD-Process-Caller)이 맞는 요청만 받는다 — 주석 「process 만 부른다」만으로 막지 않는다
CALLER_HEADER = "X-HYD-Process-Caller"
CALLER_TOKEN = os.environ.get("PROCESS_CALLER_TOKEN", "")
if not CALLER_TOKEN:
    raise RuntimeError("PROCESS_CALLER_TOKEN 이 설정되지 않아 enterprise-sim 을 띄우지 않습니다 — 업무 쓰기를 process 만 부르게 하는 값입니다")
WRITE_PATHS = frozenset({"/api/exec", "/api/reset", "/api/reanchor", "/erp/spare/reset", "/cmms/pm/reset"})
ent = SupabaseEnterprise(lambda: psycopg.connect(SUPABASE_DSN, connect_timeout=5))
app = make_app("enterprise-sim (mock ERP/MES/CMMS/QMS/SCM/EMS for L7-L9 scenarios, Supabase ent schema)", reg,
               lambda: {"ok": ent.ping(), "transactions": len(ent.transactions()) if ent.ping() else None})


_DB_UNAVAILABLE: tuple = (psycopg.OperationalError, psycopg.InterfaceError)   # 업무 DB 의 연결 · 잠금 · 시간 초과(일시 장애)


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


@app.middleware("http")
async def _process_only(request: Request, call_next):
    """하-05: 업무 쓰기(실행 · 초기화 · 기준점)는 process 만 — 값이 없거나 다르면 실행하지 않고 403."""
    if request.method == "POST" and request.url.path in WRITE_PATHS and not hmac.compare_digest(
            request.headers.get(CALLER_HEADER, "").encode(), CALLER_TOKEN.encode()):
        return JSONResponse(status_code=403, content={"detail": "업무 시스템 쓰기는 사람 승인을 거친 process 만 부를 수 있습니다"})
    return await call_next(request)


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
    업무 DB 는 'INVALID:' 로 시작하는 거절을 낸다(2026-10-23 점검 E1 · E2 · E3)."""
    try:
        return fn(arg)
    except KeyError as e:                       # 모르는 부품 · 설비: 404(업무 DB 는 빈 200 이었다, 점검 E11)
        raise HTTPException(404, f"unknown {e.args[0] if e.args else arg}")
    except Exception as e:  # noqa: BLE001 — 업무 DB 22023
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
