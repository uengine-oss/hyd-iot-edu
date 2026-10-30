"""Instance runtime wiring for the process service — 학생 PC 의 단 하나의 구성(처리 건 엔진 + Supabase PostgreSQL + AI 워커 하나).

main.py calls into this module at two points: startup and every Incident transition. 경보로 처리 건을 여는 길은 main 의 원천
접수 하나다(admit_alert). Everything else (hooks, the engine polling loop, HTTP routes) lives here.

    main.py ──build(ctx) · start_loops──▶ InstanceRuntime(PgRepo, definition, hooks) + polling loop
                                         (SUBMITTED → engine, 마감 지난 타이머 · 대기 행, 워커 임대 정리, 오래 붙잡힌 소비자)
            ──on_incident_update(inc)──▶ service tasks task:command / task:reobserve are turned in from Incident states
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
import urllib.request
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from functools import partial

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from hydcommon.timeutil import now_iso
from . import engine, instances, machine, procdb, reobs_series, work_orders
from .definition_registry import validate_definition
from .approval_hooks import DecisionDelivery, record_execution as _record_execution
from . import task_deferral
from . import approval_part

log = logging.getLogger("process.instance_mode")

DEFINITIONS_DIR = Path(os.getenv("PROCESS_DEFINITIONS", "/srv/definitions"))
DEFINITION_FILE = os.getenv("PROCESS_DEFINITION_FILE", "anomaly_response_v22.json")   # A116: 2.2 = 2.1 in the product's agent-task shape
POLL_INTERVAL_S = float(os.getenv("ENGINE_POLL_INTERVAL_S", "2"))     # the product polls every 5 s; faster here for the classroom
WORKER_URL = os.getenv("WORKER_URL", "http://agent-worker:8097")       # the cliagents worker's /health · /agents (monitoring, 회의 L434)
STALE_CLEANUP_EVERY = 150                                              # × POLL_INTERVAL_S ≈ 5 min (the product's cleanup_task)
LEASE_SWEEP_EVERY = 30                                                 # × POLL_INTERVAL_S ≈ 1 min: 임대가 세 번 끝난 워커 실행 → FAILED (A-10)
# A151 (A148 item 70-A): how long startup waits for an unreachable DB before giving up and letting the restart policy act
STARTUP_DB_WAIT_S = float(os.getenv("PROCESS_STARTUP_DB_WAIT_S", "60"))
# C2 (확정 TODO C) 승인 뒤 실행 부품의 연결 · 수업 설정 (git 이력 39f447ce:문서/시스템/검증_기록/2026-10-09/c2-execution.md)
ENTERPRISE_URL = os.getenv("ENTERPRISE_URL", "http://enterprise-sim:8095")
# 정비 수행 모사: 실습 시뮬레이터 조작(현장 정비 대역)이지 설비 명령 경로(PLC)가 아니다. 컨테이너에서는 compose 서비스 이름(ot-net)으로 간다.
# 호스트에서 직접 띄우면 PLANT_SIM_URL=http://127.0.0.1:8000 (compose.yaml 이 컨테이너에는 항상 값을 넣는다).
PLANT_SIM_URL = os.getenv("PLANT_SIM_URL", "http://plant-sim:8000")
# 수업용 대기 압축(결정 4): 기다리는 부품(시간 대기 · 입고 확인)과 그 경계 타이머만 배속 × 이 배율로 줄인다. 60 이면 20배속에서 납기 5일 → 6분.
WAIT_COMPRESSION = float(os.getenv("PROCESS_WAIT_COMPRESSION", "60"))
# 승인 뒤 MCP 호출 부품이 부르는 서버(이름 → tenants.mcp 와 같은 설정). 기본은 수업용 hyd-effects(메일 → Inbucket · CMMS 일정 · 처리 건 기록).
# 여기에 없는 이름은 tenants.mcp 에서 연결 검사를 통과한(설정 해시가 같은) 서버만 쓴다.
EFFECT_MCP_SERVERS = json.loads(os.getenv("EFFECT_MCP_SERVERS") or json.dumps(
    {"hyd-effects": {"type": "url", "url": "http://effects-mcp:8197/mcp", "transport": "streamable_http"}}))
# 하-04 · 하-05: 업무 시뮬레이터의 쓰기 끝점과 승인 뒤 메일 도구(effects-mcp)는 이 값이 맞는 호출만 받는다 — process 만 아는 값이다
# (에이전트 · 워커 · 포털에는 넘기지 않는다). 없으면 process 가 뜨지 않는다(main._startup).
CALLER_HEADER = "X-HYD-Process-Caller"


def caller_headers() -> dict:
    token = os.environ.get("PROCESS_CALLER_TOKEN", "")
    if not token:
        raise RuntimeError("PROCESS_CALLER_TOKEN 이 설정되지 않아 업무 시스템 쓰기 · 승인 뒤 메일 도구를 부를 수 없습니다 — 시작.bat 을 다시 실행하세요")
    return {CALLER_HEADER: token}


ENTERPRISE_READS = {"part_quotes": ("/scm/quotes", "part"), "purchase_order": ("/erp/purchase_orders/{ref}", None),
                    "spare_stock": ("/erp/spare_stock", "part"), "maintenance_windows": ("/cmms/windows", "asset"),
                    "pm_status": ("/cmms/pm_status", "asset")}


@dataclass
class ProcessContext:
    """What the runtime needs from main.py — passed explicitly instead of importing main (no circular import)."""
    incidents: dict
    book: dict
    state: dict
    time_scale: float
    persist: Callable[[], None]
    audit: Callable[..., None]                      # (asset, actor, event, detail, incident=None)
    cypher: Callable[..., list]                     # (query, **params) -> rows   (Neo4j write transaction)
    exec_skill: Callable[[dict, dict], dict]        # (decision, item) -> enterprise transaction result
    record_decision: Callable[[dict], None]
    approve_incident: Callable[..., dict]           # (incident, by, commands, at) -> action.cmd (송신 확인 뒤)
    get_loop: Callable[[], asyncio.AbstractEventLoop | None]
    check_approval: Callable[[dict, str, str], dict]  # must reread current policy/sources; explicit test double in unit tests
    after_incident: Callable | None = None
    reviews: Callable | None = None
    record_incident: Callable | None = None
    approval_receipts: Callable | None = None
    exec_compensation: Callable | None = None     # (request) → enterprise /api/exec with a compensation skill (A072)
    latest_tag: Callable[[str, str], float | None] | None = None   # C2: (asset, tag) → 최신값 (작업지시 뒤 재관측)
    window_series: Callable | None = None     # A161-G3: (incident, after, since) → 재관측 창의 값 흐름 (reobs_series.build 모양)


_runtime: instances.InstanceRuntime | None = None
_ctx: ProcessContext | None = None
_poll_task: asyncio.Task | None = None
_poll_status: dict = {"status": "preparing", "last_success_at": None, "failure_kind": None}
EVENTS_PAGE_MAX = 5000        # A161-G4: one /api/events page at most (the instance view itself reads instances.EVENTS_WINDOW)
PAYLOAD_CHUNK_CHARS = 200_000 # A161-G2: one /api/event-payloads chunk
stream_clients = 0            # A131: open /api/events/stream generators (memory diagnostics; must return to 0 after disconnects)


def current() -> instances.InstanceRuntime | None:
    return _runtime


def runtime_readiness() -> dict:
    """Read the actual loop state without I/O or exposing connection exceptions."""
    status = dict(_poll_status)
    if _poll_task is None:
        status["status"] = "preparing"
    elif _poll_task.done():
        status["status"] = "cancelled" if _poll_task.cancelled() else "stopped"
    return {**status, "ready": status["status"] == "ready"}


# ---------------------------------------------------------------- lifecycle
async def event_stream(repo, since: str | None, is_disconnected, interval: float = 0.5, keepalive_s: float = 15.0,
                       fetch: Callable | None = None, ts_key: str = "timestamp", history: int = 60):
    """Events use post-commit publication cursors, so late commits cannot hide behind an earlier timestamp.
    Explicit fetch/ts_key keep the existing timestamp contract for notifications."""
    global stream_clients
    if fetch is None and hasattr(repo, 'list_stream_events'):
        fetch, ts_key = repo.list_stream_events, 'stream_cursor'
    stream_clients += 1
    try:
        async for frame in _event_frames(repo, since, is_disconnected, interval, keepalive_s, fetch or repo.list_events_since, ts_key, history):
            yield frame
    finally:
        stream_clients -= 1


def _sse_id(e: dict, ts_key: str) -> str:
    """Carry the selected cursor as SSE id; automatic reconnect resumes inclusively and deduplicates event IDs."""
    ts = str(e.get(ts_key) or "").replace("\n", "")
    return f"id: {ts}\n" if ts else ""


async def _event_frames(repo, since, is_disconnected, interval, keepalive_s, fetch, ts_key, history):
    seen: set[str] = set()
    cursor = since
    if cursor is None:
        for e in await asyncio.to_thread(fetch, None, history):          # a short history so the panel is not empty
            seen.add(e["id"]); cursor = max(cursor or "", str(e.get(ts_key) or ""))
            yield "event: history\n" + _sse_id(e, ts_key) + "data: " + json.dumps(e, ensure_ascii=False, default=str) + "\n\n"
    idle = 0.0
    while not await is_disconnected():
        rows = await asyncio.to_thread(fetch, cursor, 300)
        fresh = [e for e in rows if e["id"] not in seen]
        if fresh:
            for e in fresh:
                ts = str(e.get(ts_key) or "")
                if cursor is None or ts > cursor:
                    cursor, seen = ts, {e["id"]}
                else:
                    seen.add(e["id"])
                yield _sse_id(e, ts_key) + "data: " + json.dumps(e, ensure_ascii=False, default=str) + "\n\n"
            idle = 0.0
        else:
            idle += interval
            if idle >= keepalive_s:
                idle = 0.0
                yield ": keepalive\n\n"
        await asyncio.sleep(interval)


def build(ctx: ProcessContext, repo: procdb.PgRepo | None = None, clock: Callable | None = None) -> instances.InstanceRuntime:
    """Create the runtime (repo + definition + hooks) and make it current. No background tasks — unit-testable.
    repo: 기본은 SUPABASE_DSN 의 PgRepo(시험은 시험 DB 의 PgRepo). clock: () → 지금(UTC) — 엔진의 모든 시각 판정이 이것을 쓴다."""
    global _runtime, _ctx
    _ctx = ctx
    repo = repo or procdb.PgRepo()
    defn = _bootstrap_definition(repo, os.getenv('TENANT_ID','hyd'))
    # B4: 기준 흐름 = 기동 파일(PROCESS_DEFINITION_FILE)의 판본 — 배포된 학생 판본으로 기동해도 "기준 흐름으로 되돌리기"는 이 판본으로 간다.
    # P10: 그 판본 원문을 먼저 등록해 둔다(운영 포인터 · 머리의 마지막 등록 원문은 아래 런타임이 기동 정의로 둔다)
    seed = engine.Definition.load(DEFINITIONS_DIR / DEFINITION_FILE)
    base_problem = _register_reference(repo, seed, defn, os.getenv('TENANT_ID','hyd'))
    engine.configure_wait_compression(WAIT_COMPRESSION)
    _runtime = instances.InstanceRuntime(repo, defn, _hooks(ctx), time_scale=ctx.time_scale,
                                        tenant_id=os.getenv('TENANT_ID','hyd'), consumer=f"process-engine:{procdb.consumer_name()}",
                                        clock=clock)
    triage = _runtime.register_definition(json.loads((DEFINITIONS_DIR/'alert_triage_v1.json').read_text(encoding='utf-8')))
    _runtime.base_version, _runtime.reference_ids, _runtime.base_problem = seed.raw['version'], {seed.id, triage['id']}, base_problem
    from . import ask
    ask.register_definition(_runtime, DEFINITIONS_DIR)     # B5: 에이전트에게 질문하기 (정식 정의 ask_agent 1.0)
    _runtime.register_definition(json.loads((DEFINITIONS_DIR/'shift_handover_v1.json').read_text(encoding='utf-8')))
    ctx.state["mode"], ctx.state["supabase"] = "instance", repo.ping()
    log.info("instance runtime: definition %s@%s (%d activities), repo %s", defn.id, defn.raw.get('version'),
             len(defn.activities), type(repo).__name__)
    return _runtime


def _register_reference(repo, seed: engine.Definition, booted: engine.Definition, tenant_id: str) -> str | None:
    """P10 (audit2 2026-10-23): 사람이 배포한 판본으로 기동하면(booted ≠ seed) 기준 파일 판본은 런타임이 등록하지 않는다 — 저장소 갱신으로 파일이
    새 판본이 되면 [기준 흐름으로 되돌리기]가 '등록되지 않은 정의 판본', [기준과 비교]가 '기준 판본 원문이 없습니다'로 막혔다. 기준 판본을
    불변 등록한다(운영 포인터는 그대로 — 등록은 배포가 아니다). 같은 번호에 다른 원문이 이미 있으면 등록하지 않고 사유를 돌려준다
    (flow_deploy 가 되돌리기 · 비교를 그 사유로 거절 — 같은 번호의 다른 원문으로 조용히 되돌리지 않게). 기동은 막지 않는다."""
    if booted.raw.get('version') == seed.raw.get('version'):
        return None                                     # InstanceRuntime 이 기동 정의(= 기준 파일)를 이미 등록했다
    try:
        repo.upsert_proc_def(deepcopy(seed.raw), tenant_id)
    except ValueError as e:
        problem = (f'기준 파일 {DEFINITION_FILE}의 판본 {seed.id}@{seed.raw.get("version")}을(를) 등록하지 못해 기준으로 되돌리거나 비교할 수 '
                   f'없습니다 — 같은 판본 번호로 다른 원문이 이미 등록돼 있습니다({e}). 기준 파일의 판본 번호를 올리세요')
        log.error("instance mode: %s", problem)
        return problem
    log.info("instance mode: reference version %s@%s registered (deployed version %s kept)", seed.id, seed.raw.get('version'),
             booted.raw.get('version'))
    return None


def _bootstrap_definition(repo, tenant_id: str) -> engine.Definition:
    """U4 (TODO 4): the file (PROCESS_DEFINITION_FILE) is only the first seed. Once a deployed ("운영") version exists in the DB
    for that definition id — set by the deploy/rollback API or an earlier seed — startup loads *that* version and the file is
    not consulted, so a deployment survives restarts and a changed file no longer silently switches the alert flow."""
    seed = engine.Definition.load(DEFINITIONS_DIR / DEFINITION_FILE)
    deployed = repo.deployed_version(seed.id, tenant_id)
    last = repo.list_deployments(seed.id, tenant_id, limit=1)
    if last and last[0].get('action') == 'seed':
        # B4: nobody deployed this id through the API (only a boot seed or the migration backfill of the old "last registered"
        # pointer) — the file is still the reference, as before U4. A person's deploy/rollback/reset is what survives restarts.
        return seed
    if deployed and deployed != seed.raw.get('version'):
        row = repo.get_proc_def(seed.id, tenant_id, version=deployed)
        if not row or not row.get('definition'):
            raise LookupError(f'배포 판본 {seed.id}@{deployed}의 정의 원문이 없습니다 (proc_def_version)')
        log.info("instance mode: deployed version %s@%s is used instead of the seed file %s", seed.id, deployed, DEFINITION_FILE)
        return engine.Definition.from_dict(row['definition'])
    return seed


def start(ctx: ProcessContext) -> instances.InstanceRuntime:
    """build() plus the polling loop. Call from the FastAPI startup event (needs a running loop)."""
    rt = build(ctx)
    start_loops(rt, ctx)
    return rt


def start_loops(rt: instances.InstanceRuntime, ctx: ProcessContext) -> None:
    """The background loops of start(), split off so main.py can retry build() alone without starting a loop twice."""
    global _poll_task
    if _poll_task is not None and not _poll_task.done():
        raise RuntimeError("instance polling already running")
    _poll_status.update(status="preparing", last_success_at=None, failure_kind=None)
    _poll_task = asyncio.create_task(_polling())


def _transient_db_errors() -> tuple[type[BaseException], ...]:
    import psycopg
    return (psycopg.OperationalError, psycopg.InterfaceError)


async def retry_startup(step: Callable[[], object], what: str, state: dict, budget_s: float | None = None,
                        first_delay: float = 2.0):
    """A151 (A148 item 70-A, 2026-10-08): a process restarted while the DB was paused died in startup on the first
    `psycopg.OperationalError` (procdb.PgRepo._conn, connect_timeout=5, no retry) and only the compose restart policy brought it
    back (RestartCount 0→1). Startup steps that touch the DB now retry connection errors with a bounded backoff
    (2, 4, 8, 16 s … — the sleeps add up to at most `budget_s`, default PROCESS_STARTUP_DB_WAIT_S=60). Meanwhile /healthz is
    not ready (uvicorn serves nothing before startup ends, and state['startup_db_error'] keeps it 503 afterwards until cleared).
    Anything that is not a connection error, or a DB still down after the budget, is raised as before."""
    budget = STARTUP_DB_WAIT_S if budget_s is None else budget_s
    transient = _transient_db_errors()
    waited, delay, attempt = 0.0, first_delay, 0
    while True:
        attempt += 1
        try:
            out = step()
            if inspect.isawaitable(out):
                out = await out
        except transient as exc:
            state['startup_db_error'] = f"{what}: {type(exc).__name__}: {str(exc)[:200]}"
            pause = min(delay, budget - waited)
            if pause <= 0:
                log.error("startup %s: DB still unreachable after %d attempts / %.0f s of waiting; giving up", what, attempt, waited)
                raise
            log.warning("startup %s: DB unreachable (attempt %d, %s); retrying in %.0f s", what, attempt, type(exc).__name__, pause)
            await asyncio.sleep(pause)
            waited += pause
            delay *= 2
            continue
        state.pop('startup_db_error', None)
        if attempt > 1:
            log.info("startup %s: DB reachable after %d attempts (%.0f s of waiting)", what, attempt, waited)
        return out


def sweep_worker_leases(rt: instances.InstanceRuntime) -> int:
    """A097 · A-10: 임대가 세 번 끝난 워커 실행을 FAILED 로 — 사람이 [닫기]로 닫을 수 있게(A082). 엔진 폴링의 정리 주기에서 돈다."""
    n = rt.repo.expire_worker_leases()
    if n:
        log.warning("worker lease sweep: %d run(s) marked FAILED after %d expired claims", n, procdb.MAX_CLAIMS)
    return n


def poll_round(rt: instances.InstanceRuntime, tick: int) -> list[str]:
    """폴링 한 바퀴(B-11). 일마다 따로 가둔다 — 처리 건 하나 · 일 하나의 예외가 타이머 발화나 다른 일을 멈추지 않는다(처리 건 단위
    격리는 각 일 안에서 한다). 돌려줌 = 실패한 일의 이름(비면 성공)."""
    steps = [("engine", rt.poll_once), ("timers", rt.fire_timeouts)]
    if tick % LEASE_SWEEP_EVERY == 0:
        steps.append(("worker leases", lambda: sweep_worker_leases(rt)))
    if tick % STALE_CLEANUP_EVERY == 0:
        steps.append(("stale consumers", rt.repo.cleanup_stale_consumers))
    failed = []
    for name, step in steps:
        try:
            step()
        except Exception:  # noqa: BLE001 — 기록하고 다음 일로(실패는 /healthz 의 runtime.failure_kind 로 보인다)
            log.exception("instance polling: %s failed", name)
            failed.append(name)
    return failed


async def _polling() -> None:
    """The completion polling of ProcessGPT: SUBMITTED rows → engine; boundary timers; worker leases ~1 min; stale consumers ~5 min."""
    tick = 0
    try:
        while True:
            await asyncio.sleep(POLL_INTERVAL_S)
            tick += 1
            failed = await _in_executor(poll_round, _runtime, tick)
            if failed:
                _poll_status.update(status="failed", failure_kind=", ".join(failed))
            else:
                _poll_status.update(status="ready", last_success_at=now_iso(), failure_kind=None)
    except asyncio.CancelledError:
        _poll_status.update(status="cancelled")
        raise
    except Exception as exc:
        _poll_status.update(status="stopped", failure_kind=type(exc).__name__)
        log.warning("instance polling stopped (%s)", type(exc).__name__)
        raise
    finally:
        if _poll_status["status"] != "cancelled":
            _poll_status.update(status="stopped")


def _in_executor(fn, *args):
    return asyncio.get_running_loop().run_in_executor(None, fn, *args)


def _schedule(fn, *args) -> None:
    """Fire-and-forget on a worker thread, from any thread (uses the loop main.py recorded at startup)."""
    loop = _ctx.get_loop() if _ctx else None
    if loop is not None:
        loop.run_in_executor(None, fn, *args)


# ---------------------------------------------------------------- entry points main.py calls
def on_incident_update(inc: machine.Incident) -> None:
    if _runtime is not None:
        _schedule(_runtime.on_incident_update, inc.state, inc.id, inc.cleared)


# ---------------------------------------------------------------- hooks: how the runtime touches the Incident / decision world of main.py
def _hooks(ctx: ProcessContext) -> instances.Hooks:
    from .rework_effects import collect as collect_rework_effects
    delivery = DecisionDelivery(ctx)
    def open_incident(alert: dict, recovery_policy=None) -> dict:
        existing = _open_incident_for(ctx, alert.get("alertId"))
        if existing:
            if existing.asset != alert.get('asset') or existing.pattern != alert.get('pattern'):
                raise ValueError('경보 ID의 원천 설비/패턴이 기존 사건과 다릅니다')
            if ctx.record_incident:
                ctx.record_incident(existing)
            return {"id": existing.id}
        triage = recovery_policy is not None and recovery_policy.get('route') == 'triage'
        card = {"alert": alert, "recommended": [], "causes": [], "citations": [],
                "summary": "지원하는 회복 기준이 없어 현장 검토가 필요합니다" if triage else "에이전트 판단 대기 (프로세스 인스턴스가 열었다)"}
        inc = machine.Incident.from_card(machine.new_incident_id(), card,recovery_policy=recovery_policy)
        machine.on_card(inc)
        ctx.incidents[inc.id] = inc
        ctx.state["incidents"] = len(ctx.incidents)
        ctx.persist()
        if ctx.record_incident:
            ctx.record_incident(inc)
        ctx.audit(inc.asset, "process", "INCIDENT_OPENED", {"alertId": inc.alert_id, "via": "instance"}, incident=inc.id)
        return {"id": inc.id}

    def update_incident_card(inc_id: str, card: dict) -> None:
        inc = ctx.incidents.get(inc_id)
        if inc is None:
            raise ValueError('가이드를 저장할 원천 사건이 없습니다')
        alert = card.get('alert')
        if alert is not None and not isinstance(alert,dict):
            raise ValueError('가이드의 원천 경보는 객체여야 합니다')
        # diagnose(asset, pattern) returns only those source fields. The engine
        # already owns the full original event; omissions do not replace it.
        identity={'alertId':inc.alert_id,'asset':inc.asset,'pattern':inc.pattern}
        if any(k in (alert or {}) and alert[k]!=v for k,v in identity.items()):
            raise ValueError('가이드가 원천 경보 ID/설비/패턴을 변경할 수 없습니다')
        if card.get('incident') not in (None,inc.id):
            raise ValueError('가이드가 원천 사건 ID를 변경할 수 없습니다')
        if inc.state != 'AWAITING_APPROVAL' or inc.recovery is None:
            raise ValueError('현재 사건은 가이드 변경을 받을 수 없습니다')
        inc.card = dict(card, incident=inc.id, alert=inc.card.get('alert'))
        ctx.persist()

    def approve_commands(inc_id: str, commands: list[dict], by: str, at=None) -> dict:
        inc = ctx.incidents.get(inc_id)
        if inc is None:
            raise ValueError(f"no such incident {inc_id}")
        return ctx.approve_incident(inc, by, commands, at)

    def _incident_change(inc_id: str, change) -> bool:
        """사건 전이 하나(machine.on_*) → 저장 · 감사 · 처리 건 갱신. change(inc, fx) 가 False 면 아무것도 하지 않는다."""
        inc = ctx.incidents.get(inc_id)
        if inc is None:
            raise ValueError(f"no such incident {inc_id}")
        fx = work_orders._Audit()
        changed = change(inc, fx)
        if changed:
            ctx.persist()
            for event in fx.events:
                ctx.audit(event["asset"], event["actor"], event["event"], event["detail"], incident=inc.id)
            if ctx.after_incident:
                ctx.after_incident(inc)
        return bool(changed)

    def ack_timeout(inc_id: str, cmd_id: str) -> bool:
        return _incident_change(inc_id, lambda inc, fx: machine.on_ack_timeout(inc, cmd_id, fx))

    def reobservation_extended(inc_id: str, cmd_id: str, reading: dict, extension: int, seconds: float) -> bool:
        return _incident_change(inc_id, lambda inc, fx: machine.on_reobservation_extended(inc, cmd_id, reading, extension, seconds, fx))

    def reobservation_verdict(inc_id: str, cmd_id: str, passed: bool, reading: dict, extensions: int) -> bool:
        return _incident_change(inc_id, lambda inc, fx: machine.on_reobservation(inc, cmd_id, passed, reading, extensions, fx))

    def incident_state(inc_id: str) -> str | None:
        inc = ctx.incidents.get(inc_id)
        return inc.state if inc is not None else None

    def reopen_incident(inc_id: str, request_id: str, by: str, role: str, reason: str, effects: dict) -> bool:
        return _incident_change(inc_id, lambda inc, fx: machine.on_rework_reopen(inc, request_id, by, role, reason, effects, fx))

    def reopen_for_recheck(inc_id: str, request_id: str, by: str, reason: str) -> bool:
        # B7: 작업지시로만 닫힌 사건 — 흐름이 재분석 뒤 새 판단 · 승인으로 되돌아가면 다음 승인을 받도록 다시 연다(machine.on_recheck_reopen)
        return _incident_change(inc_id, lambda inc, fx: machine.on_recheck_reopen(inc, request_id, by, reason, fx))

    def incident_snapshot(inc_id: str) -> dict | None:
        inc=ctx.incidents.get(inc_id)
        return {'state':inc.state,'cleared':inc.cleared,'cmdId':inc.cmd_id,'superseded':bool(inc.superseded),
                'workOrder':bool(inc.work_order),'reason':inc.reason,'ackDueAt':inc.ack_due_at} if inc is not None else None

    def decision_option(decision_id: str, option_id: str) -> dict | None:
        d = ctx.book.get(decision_id) or {}
        return next((o for o in d.get("options", []) if o["id"] == option_id), None)

    def exec_enterprise(decision_id: str, item: dict) -> dict:
        d = ctx.book.get(decision_id)
        if d is None or not d.get("chosen"):
            return {"ok": False, "error": f"decision {decision_id} not approved", "code": item.get("code"), "system": item.get("system")}
        inc = work_orders.prepare(ctx, d, item) if item.get('code') == 'WO_CREATE' else None
        result = ctx.exec_skill(d, item)
        if item.get('code') == 'WO_CREATE' and result.get('ok') is True:
            if not isinstance(result.get('ref'), str) or not result['ref'].strip():
                result = dict(result, ok=False, error='CMMS success requires an actual nonempty reference')
        _record_execution(d, result)
        ctx.persist()
        if item.get('code') == 'WO_CREATE' and result.get('ok') is True:
            work_orders.confirm(ctx, inc, item, result)
        return result

    def close_incident_effect(inc_id: str, receipt: dict) -> bool:
        return _incident_change(inc_id, lambda inc, fx: machine.on_business_effect(inc, receipt, fx))

    def close_incident_result(inc_id: str, level: str, summary: str) -> bool:
        return _incident_change(inc_id, lambda inc, fx: machine.on_result_report(inc, level, summary, fx))

    def recovery_reading(inc_id: str, since: str | None = None, after: str = "work_order") -> dict | None:
        """사건의 회복 기준 태그 최신값 · 경보 해제 · (since 가 있으면) 재관측 창의 값 흐름. after = 'command' | 'work_order'(창의 종류)."""
        inc = ctx.incidents.get(inc_id)
        if inc is None or inc.recovery is None:
            return None
        tag, op, limit = inc.recovery
        value = ctx.latest_tag(inc.asset, tag) if ctx.latest_tag else None
        inside = value is not None and (value < limit if op == "<" else value >= limit)
        reading = {"tag": tag, "op": op, "limit": limit, "value": value, "inside": inside, "cleared": bool(inc.cleared),
                   "criterion": f"{tag} {op} {limit}"}
        if since and ctx.window_series is not None:
            # A161-G3: the re-observation window (since = its start) — the trend goes on the reading (the step's
            # REOBSERVATION event) and on the Incident (reobsSeries)
            try:
                series = ctx.window_series(inc, after, since)
            except Exception as e:  # noqa: BLE001 — the trend is supporting evidence; the verdict never waits for it, but the gap is recorded
                log.warning("re-observation series for %s could not be read", inc_id, exc_info=True)
                series = reobs_series.unavailable(f"재관측 창의 값을 읽지 못했습니다: {type(e).__name__}: {str(e)[:200]}", tag=tag, op=op,
                                                  limit=limit, since=since, until=None, after=after, extensions=inc.reobs_extensions)
            if series:
                reading["series"] = series
                machine.record_reobs_series(inc, series)
                ctx.persist()
        return reading

    def _runtime_server(server: str, call) -> dict:
        """등록 · 검사 도장 확인 → 비밀 자리표시자 채우기 → call(spec, entry) → 비밀 값 가리기. 실패는 status · error 로 답한다."""
        from . import mcp_check, mcp_secrets
        try:
            entry = _effect_server(server)
            spec = mcp_check.normalize(entry)
        except (LookupError, ValueError) as e:
            return {"status": "failed", "error": str(e), "error_kind": "config"}
        rt = current()
        if rt is None:
            return {"status": "failed", "error": instances.NOT_READY, "error_kind": "config"}
        try:            # G2: ${SECRET:KEY} 는 부르기 직전에만 채운다 — 값이 없으면 빈 토큰으로 부르지 않고 사유로 멈춘다
            spec, used = mcp_secrets.runtime_spec(rt.repo, rt.tenant_id, server, entry)
            spec = mcp_check.normalize(spec)
        except mcp_secrets.SecretError as e:
            return {"status": "failed", "error": e.reason, "error_kind": "secret"}
        # 서버가 토큰을 되돌려 줘도(오류 본문 · 에코) 영수증 · 감사 · 처리 기록에 값이 남지 않게
        return mcp_secrets.redact(call(spec, entry), used)

    def mcp_call(server: str, tool: str, arguments: dict, key: str) -> dict:
        from . import mcp_check
        return _runtime_server(server, lambda spec, entry: mcp_check.call_effect(spec, tool, arguments, idempotency_key=key, timeout=20.0))

    def mcp_read(server: str, tool: str, arguments: dict) -> dict:
        """G3 읽기 확인: 포털 써 보기와 같은 판정(mcp_check.call — 호출 직전 다시 받은 목록에서 read_only_verdict, 강사 확인 목록 포함).
        쓰기 도구면 tools/call 없이 status=refused 로 돌아온다."""
        from . import mcp_check, mcp_registry
        return _runtime_server(server, lambda spec, entry: mcp_check.call(spec, tool, arguments, 20.0,
                                                                         confirmed=frozenset(mcp_registry.confirmed_of(entry))))

    def _effect_server(name: str) -> dict:
        if name in EFFECT_MCP_SERVERS:
            entry = EFFECT_MCP_SERVERS[name]       # process 설정의 승인 뒤 쓰기 서버 — process 만 아는 값을 실어 부른다(하-04)
            return dict(entry, headers={**(entry.get("headers") or {}), **caller_headers()})
        from . import mcp_registry
        rt = current()
        servers = mcp_registry.store_for(rt.repo).servers(rt.tenant_id) if rt is not None else {}
        entry = servers.get(name)
        if entry is None:
            raise LookupError(f"MCP 서버 '{name}' 이(가) 없습니다 (EFFECT_MCP_SERVERS 또는 MCP 서버 등록)")
        gate = ((entry.get(mcp_registry.META_KEY) or {}).get("gate") or {}) if isinstance(entry, dict) else {}
        if name not in mcp_registry.BASE_SERVERS and gate.get("fingerprint") != mcp_registry.fingerprint(entry):
            raise LookupError(f"MCP 서버 '{name}' 은(는) 연결 검사를 통과한 설정이 아닙니다 — 포털 MCP 화면에서 다시 검사하세요")
        return entry

    return instances.Hooks(new_incident=open_incident, update_incident_card=update_incident_card, approve_commands=approve_commands,
                           incident_state=incident_state, incident_snapshot=incident_snapshot,
                           decision_option=decision_option, get_decision=lambda did: ctx.book.get(did), approve_decision=delivery.prepare,
                           preview_decision=delivery.preview, approve_review=delivery.prepare_review,
                           validate_approval=delivery.validate, deliver_approval=delivery.deliver, record_approval=delivery.record,
                           check_rejection=delivery.check_rejection, reject_decision=delivery.reject,
                           approval_effects=delivery.effects, rework_effects=lambda inst: collect_rework_effects(ctx, inst),
                           reopen_incident=reopen_incident, reopen_for_recheck=reopen_for_recheck, exec_compensation=ctx.exec_compensation,
                           exec_enterprise=exec_enterprise, record_cypher=ctx.cypher, query_cypher=ctx.cypher,
                           ensure_actor_schema=lambda: ctx.cypher(instances.ACTOR_CONSTRAINT_Q), audit=ctx.audit,
                           enterprise_read=enterprise_read, mcp_call=mcp_call, mcp_read=mcp_read, plant_restore=plant_restore,
                           close_incident_effect=close_incident_effect, recovery_reading=recovery_reading,
                           read_tag=ctx.latest_tag, close_incident_result=close_incident_result, ack_timeout=ack_timeout,
                           reobservation_extended=reobservation_extended, reobservation_verdict=reobservation_verdict)


def enterprise_read(name: str, params: dict) -> dict:
    """C2: enterprise-sim 읽기(견적 · 발주 · 재고 · 예정된 정비 시간). 실패는 예외 — 값 없이 진행하지 않는다."""
    from urllib.parse import quote, urlencode
    path, key = ENTERPRISE_READS[name]
    params = dict(params or {})
    if "{ref}" in path:
        path = path.replace("{ref}", quote(str(params.pop("ref")), safe=""))
    url = ENTERPRISE_URL + path + (("?" + urlencode({k: v for k, v in params.items() if v is not None})) if params else "")
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def plant_restore(asset: str, component: str | None) -> dict:
    """C2 정비 수행 모사: plant-sim POST /api/fault {asset, type: restore[, component]}. 응답을 그대로 돌려준다(ok 표시 추가)."""
    body = {"asset": asset, "type": "restore"}
    if component:
        body["component"] = component
    req = urllib.request.Request(PLANT_SIM_URL + "/api/fault", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return dict(json.loads(r.read()), ok=True, url=PLANT_SIM_URL)
    except Exception as e:  # noqa: BLE001 — 사유를 남기고 실패로
        return {"ok": False, "error": f"설비 시뮬레이터 복구 요청 실패({PLANT_SIM_URL}): {str(e)[:200]}"}


def _open_incident_for(ctx: ProcessContext, alert_id: str | None) -> machine.Incident | None:
    return next((i for i in list(ctx.incidents.values()) if i.alert_id == alert_id), None)


# ---------------------------------------------------------------- agent worker monitoring
def _get_json(url: str, timeout: float = 2.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def worker_status(url: str = WORKER_URL) -> dict:
    """/health (runs_in_flight · polls · handled · last_poll) and /agents (which CLIs are installed) of the cliagents worker.
    Unreachable is a normal classroom state (the worker may run on the lecturer's PC or not at all), so it is reported, not raised."""
    out = {"url": url, "reachable": False, "agent_orch": "cliagents", "health": None, "agents": [], "error": None}
    try:
        out["health"] = _get_json(f"{url}/health")
        out["reachable"] = True
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        return out
    try:
        out["agents"] = (_get_json(f"{url}/agents") or {}).get("agents") or []
    except Exception as e:  # noqa: BLE001
        out["error"] = f"agents: {type(e).__name__}: {str(e)[:120]}"
    return out


# ---------------------------------------------------------------- HTTP routes (registered in every mode; 409 unless instance mode is on)
class StartReq(BaseModel):
    alert: dict | None = None
    definition_id: str | None = None
    version: str | None = None
    event_id: str | None = None
    variables: dict = Field(default_factory=dict)
    name: str | None = None


class DefinitionReq(BaseModel):
    definition: dict


class RollbackReq(BaseModel):
    by: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)


class DeployReq(RollbackReq):
    version: str = Field(min_length=1, max_length=200)
    # P9: 시작.bat 이 부르는 수업 흐름 설치(course_bootstrap — 프로세스 안 호출만, course_policy 가 그 밖은 거절)만 True — 포털의 [기준 흐름으로 되돌리기]가 남기는 '수업 흐름' 배포
    class_flow: bool = False


class SubmitReq(BaseModel):
    output: dict | None = None
    by: str | None = None


class ApproveReq(BaseModel):
    decision: str                       # approval_part.APPROVE | approval_part.REJECT
    option: str | None = None           # 고른 안의 구분 값(설정 key, 기본 slot) — 반려에는 없다
    by: str
    role: str
    reason: str = ""


class CloseReq(BaseModel):
    by: str
    reason: str


class SelectReq(BaseModel):
    decision: str
    option: str
    by: str                             # 포털의 "나"(user:*) — 누가 승인했는지 모르는 승인은 받지 않는다(A-04)
    role: str
    reason: str = ""
    fan_pct: float | None = None
    load_pct: float | None = None
    review_id: str | None = None


class RejectCardReq(BaseModel):
    decision: str
    by: str
    role: str
    reason: str = Field(min_length=1, max_length=2000)


class ReviewReq(BaseModel):
    decision: str
    option: str
    parameters: dict = Field(default_factory=dict)


class HumanResponseReq(BaseModel):
    job_id: str
    answer: str
    by: str = "담당자"


class ReassessmentReq(BaseModel):
    deferral_id: str = Field(min_length=1,max_length=200)
    request_id: str = Field(min_length=1,max_length=200)
    by: str = Field(min_length=1,max_length=200)
    reason: str = Field(min_length=1,max_length=2000)


class ApprovalRetryReq(BaseModel):
    by: str
    role: str


class ApprovalDiscardReq(ApprovalRetryReq):
    reason: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(min_length=1, max_length=200)


class ReworkReq(ApprovalDiscardReq):
    workitem_id: str
    snapshot_token: str = Field(min_length=64, max_length=64)


class EffectReq(ApprovalDiscardReq):
    effects: list[str] | None = None


def _rt() -> instances.InstanceRuntime:
    if _runtime is None:
        raise HTTPException(503, instances.NOT_READY)
    return _runtime


def mount(app: FastAPI, *, admit_alert: Callable) -> None:
    """admit_alert(alert) → 접수 결과(async, main 의 원천 접수) — 강의 도우미가 경보로 처리 건을 열 때도 같은 길로 간다(B-10)."""
    @app.post("/internal/worker/mcp-runtime")
    async def worker_mcp_runtime(request: Request):
        from .worker_credentials import resolve
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 16_384:
                raise HTTPException(413, "실행 연결 요청이 허용 크기를 초과했습니다")
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            raise HTTPException(422, "실행 연결 요청은 올바른 JSON이어야 합니다") from None
        if not isinstance(body, dict):
            raise HTTPException(422, "실행 연결 요청은 객체여야 합니다")
        from fastapi.responses import JSONResponse
        result = await _in_executor(resolve, _rt(), body, request.headers.get("authorization"))
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @app.api_route("/internal/worker/mcp/{name}", methods=["POST", "GET", "DELETE"])
    async def worker_mcp_relay(name: str, request: Request):
        from .mcp_worker_relay import forward, MAX_BODY
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_BODY:
                raise HTTPException(413, "도구 요청이 허용 크기를 초과했습니다")
        return await _in_executor(partial(forward, _rt(), name, request.headers.get("authorization"),
                                          request.method, dict(request.headers), bytes(raw)))

    @app.get("/api/process/mode")
    def process_mode_info():
        rt = _runtime
        return {"mode": "instance", "definition": rt.defn.id if rt else None,
                "deployed_version": rt.repo.deployed_version(rt.defn.id, rt.tenant_id) if rt else None,
                "repo": type(rt.repo).__name__ if rt else None, "time_scale": rt.time_scale if rt else None, "engine": rt.consumer if rt else None}

    @app.get("/api/process/definition")
    def process_definition():
        """The deployed version of the alert definition — what the next RAISE opens (U4)."""
        try:
            return _rt().deployed_definition().raw
        except LookupError as e:
            raise HTTPException(409, str(e))

    from . import flow_deploy
    flow_deploy.mount(app, lambda: _runtime)    # B4: /api/flows/deployments · /api/flows/deploy-reset · /api/flows/deploy-compare

    @app.get('/api/process/definitions/{definition_id}/versions')
    async def definition_versions(definition_id: str):
        """U4: every registered version with the deployed one marked, deployability (validate_definition) and the deployment history."""
        try:
            return await _in_executor(_rt().definition_status, definition_id)
        except LookupError as e:
            raise HTTPException(404, str(e))

    @app.get('/api/process/definitions/{definition_id}/compare')
    async def compare_definition_versions(definition_id: str, from_version: str, to_version: str):
        """U4: added / removed / changed steps, flows, conditions, variables, roles and forms between two versions, as people read it."""
        try:
            return await _in_executor(_rt().compare_definitions, definition_id, from_version, to_version)
        except LookupError as e:
            raise HTTPException(404, str(e))

    @app.post('/api/process/definitions/{definition_id}/deploy')
    async def deploy_definition(definition_id: str, req: DeployReq):
        """U4: make a version the one new alerts open. Refused unless it passes validate_definition; open instances keep theirs."""
        try:
            return await _in_executor(lambda: _rt().deploy_definition(definition_id, req.version, req.by, req.reason, class_flow=req.class_flow))
        except LookupError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(409, str(e))

    @app.post('/api/process/definitions/{definition_id}/rollback')
    async def rollback_definition(definition_id: str, req: RollbackReq):
        """U4: back to the version deployed before the current one."""
        try:
            return await _in_executor(_rt().rollback_definition, definition_id, req.by, req.reason)
        except LookupError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(409, str(e))

    @app.get('/api/process/definitions')
    async def list_definitions():
        rt = _rt()
        rows = await _in_executor(rt.repo.list_definitions, rt.tenant_id)
        deployed = {}
        for r in rows:
            if r['id'] not in deployed:
                deployed[r['id']] = await _in_executor(rt.repo.deployed_version, r['id'], rt.tenant_id)
        return [{'id':r['id'],'name':r.get('name'),'version':r['prod_version'],'registered_at':r.get('registered_at'),
                 'deployed':r['prod_version']==deployed.get(r['id']),'deployed_version':deployed.get(r['id']),
                 'form_source':'definition-version' if 'forms' in r['definition'] else 'legacy-live'} for r in rows]

    @app.get('/api/process/definitions/{definition_id}')
    async def get_definition(definition_id: str, version: str):
        rt = _rt()
        row = await _in_executor(lambda: rt.repo.get_proc_def(definition_id, rt.tenant_id, version=version))
        if row is None:
            raise HTTPException(404, 'no such definition version')
        return row['definition']

    @app.post('/api/process/definitions', status_code=201)
    async def publish_definition(req: DefinitionReq):
        rt = _rt()
        try:
            validate_definition(req.definition)
        except ValueError as e:
            raise HTTPException(400,str(e))
        try:
            return await _in_executor(rt.register_definition, req.definition)
        except ValueError as e:
            raise HTTPException(409,str(e))

    @app.get("/api/events/stream")
    async def events_stream(request: Request, since: str | None = None):
        """A091: server-sent stream of the product's events table (agent tool calls, task transitions, human answers …).
        The portal shows them as they happen instead of re-reading an instance every two seconds."""
        # A browser retry keeps the original URL but sends its newer last id.
        since = request.headers.get("last-event-id") or since or None
        return StreamingResponse(event_stream(_rt().repo, since, request.is_disconnected), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/instances")
    async def list_instances(status: str | None = None, limit: int = 100, incident: str | None = None):
        rt = _rt()
        rows = await _in_executor(rt.repo.list_instances, status, min(max(limit,1),500), rt.tenant_id, incident)
        # List cards need the outcome badge, never complete proposals/source documents.
        fields = {'result_report': ('level', 'verdict', 'ok', 'status', 'outcome'),
                  'test_run': ('ok', 'verdict'), 'goods_receipt': ('ok',)}
        for row in rows:
            values = engine.variables(row)
            summary = []
            for key in ('asset', 'incident', 'recovered', 'received', *fields):
                value = values.get(key)
                if key in fields and isinstance(value, dict):
                    value = {k: v for k in fields[key] if isinstance(v := value.get(k), (str, bool, int, float))}
                if isinstance(value, (str, bool, int, float, dict)):
                    summary.append({'key': key, 'value': value})
            row['variables_data'] = summary
            for detail_field in ('variables', 'initial_variables', 'variable_sources', 'flow_state'):
                row.pop(detail_field, None)
        return rows

    @app.get("/api/instances/{proc_inst_id}")
    async def get_instance(proc_inst_id: str):
        try:
            view = await _in_executor(_rt().instance_view, proc_inst_id)
        except instances.InstanceRemoved as e:
            raise HTTPException(404, str(e))
        if view is None:
            raise HTTPException(404, "no such instance")
        return view

    @app.get("/api/instances/{proc_inst_id}/graph")
    async def get_instance_graph(proc_inst_id: str):
        """The instance as the ontology's Execution layer holds it (ProcessInstance · WorkItem · INSTANCE_OF · EXECUTES · ASSIGNED_TO · ROLE_BOUND)."""
        try:
            view = await _in_executor(_rt().execution_view, proc_inst_id)
        except instances.InstanceRemoved as e:
            raise HTTPException(404, str(e))
        if view is None:
            raise HTTPException(404, "no such instance")
        return view

    @app.get('/api/instances/{proc_inst_id}/rework-preview')
    async def preview_rework(proc_inst_id: str, workitem_id: str):
        try:
            return await _in_executor(_rt().preview_rework, proc_inst_id, workitem_id)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except (ValueError, LookupError) as e:
            raise HTTPException(409, str(e))
        except OSError as e:
            raise HTTPException(503, '재작업 효과 조회가 실패했습니다: ' + str(e)[:200])

    @app.get('/api/instances/{proc_inst_id}/effects')
    async def instance_effects(proc_inst_id: str):
        """External effects of the case with reversibility, receipts and what still blocks rework (A072)."""
        try:
            return await _in_executor(_rt().effects_view, proc_inst_id)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except (ValueError, LookupError) as e:
            raise HTTPException(409, str(e))
        except OSError as e:
            raise HTTPException(503, '효과 조회가 실패했습니다: ' + str(e)[:200])

    @app.post('/api/instances/{proc_inst_id}/effects/compensate')
    async def compensate_effects(proc_inst_id: str, req: EffectReq):
        try:
            return await _in_executor(_rt().compensate_effects, proc_inst_id, req.request_id, req.by, req.role, req.reason, req.effects)
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except KeyError as e:
            raise HTTPException(404, str(e))
        except (ValueError, LookupError) as e:
            raise HTTPException(409, str(e))
        except OSError as e:
            raise HTTPException(503, '보상 접수 또는 효과 조회가 실패했습니다: ' + str(e)[:200])

    @app.post('/api/instances/{proc_inst_id}/effects/review')
    async def review_effects(proc_inst_id: str, req: EffectReq):
        try:
            return await _in_executor(_rt().review_effects, proc_inst_id, req.request_id, req.by, req.role, req.reason, req.effects)
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except KeyError as e:
            raise HTTPException(404, str(e))
        except (ValueError, LookupError) as e:
            raise HTTPException(409, str(e))
        except OSError as e:
            raise HTTPException(503, '확인 접수 또는 효과 조회가 실패했습니다: ' + str(e)[:200])

    @app.post('/api/instances/{proc_inst_id}/rework')
    async def request_rework(proc_inst_id: str, req: ReworkReq):
        try:
            return await _in_executor(_rt().request_rework, proc_inst_id, req.workitem_id,
                req.request_id, req.snapshot_token, req.by, req.role, req.reason)
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except KeyError as e:
            raise HTTPException(404, str(e))
        except (ValueError, LookupError) as e:
            raise HTTPException(409, str(e))
        except OSError as e:
            raise HTTPException(503, '재작업 접수 또는 효과 조회가 실패했습니다: ' + str(e)[:200])

    @app.get("/api/agents/status")
    async def agents_status():
        """Which agent workers are up and what they are doing — the product's '어떤 에이전트들이 지금 동작하고 있다' panel (회의 L434)."""
        return await _in_executor(worker_status)

    @app.post("/api/instances/start")
    async def start_instance(req: StartReq):
        """정의 하나를 직접 시작하거나(definition_id · version · event_id), 손으로 쓴 경보로 처리 건을 연다(alert). 경보는 Kafka 경보와
        같은 원천 접수 → 경보 정책 → 배포 흐름 길 하나로만 간다(B-10) — 어느 흐름이 여는지는 정책이 정하고, 같은 경보는 같은 처리 건이다."""
        rt = _rt()
        try:
            if req.alert is not None:
                policy = await _in_executor(rt.alert_policy, req.alert.get('pattern'))
                target = policy['target']
                if req.definition_id and (req.definition_id, req.version or target['version']) != (target['definition'], target['version']):
                    raise HTTPException(409, f"이 경보({req.alert.get('pattern')})는 배포된 흐름 {target['definition']} {target['version']}이(가) 엽니다 — "
                                             "흐름을 바꾸려면 그 흐름을 배포하세요")
                admitted = await admit_alert(req.alert)
                if admitted.get('duplicate'):
                    raise HTTPException(409, f"이 경보로 이미 열린 처리 건이 있습니다: {admitted.get('instance')}")
                inst = await _in_executor(rt.repo.get_instance, admitted['instance'])
            elif req.definition_id:
                inst = await _in_executor(rt.start_definition, req.definition_id, req.version, req.event_id, req.variables, None, req.name)
                if inst is None:
                    raise HTTPException(409, f"같은 요청 id({req.event_id})로 이미 시작한 처리 건이 있습니다")
            else:
                raise ValueError('시작할 정의(definition_id · version · event_id) 또는 경보(alert)가 필요합니다')
        except LookupError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        except TimeoutError as e:
            raise HTTPException(503, str(e))
        return inst

    @app.get("/api/todolist")
    async def list_todolist(response: Response, status: str | None = None, user_id: str | None = None, agent_orch: str | None = None,
                            proc_inst_id: str | None = None, limit: int = 200):
        """작업 행 목록(오래된 것부터). P4 (audit2): proc_inst_id 를 주면 그 처리 건의 행을 자르지 않고 모두 돌려준다(처리 건 화면 계약:
        ?proc_inst_id=<id>&status=IN_PROGRESS). 처리 건 없이 읽으면 limit(최대 500)을 넘는 만큼 **가장 오래된** 행을 뺀다(전에는 가장 새 행이
        빠졌다) — 잘렸으면 머리 X-Todolist-Truncated: 1."""
        rt = _rt()
        if proc_inst_id:
            return await _in_executor(lambda: rt.repo.list_workitems(proc_inst_id, status, user_id, agent_orch, None, rt.tenant_id))
        cap = min(max(limit, 1), 500)
        rows = await _in_executor(lambda: rt.repo.list_workitems(None, status, user_id, agent_orch, cap + 1, rt.tenant_id, newest=True))
        if len(rows) > cap:
            response.headers["X-Todolist-Truncated"] = "1"
            rows = rows[1:]
        return rows

    @app.get("/api/todolist/{wid}")
    async def get_todolist_item(wid: str):
        rt = _rt()
        try:
            return await _in_executor(rt.workitem_view,wid)
        except KeyError:
            raise HTTPException(404, "no such work item")
        except instances.InstanceRemoved as e:
            raise HTTPException(404, str(e))
        except (ValueError,LookupError) as e:
            raise HTTPException(409,str(e))

    @app.post("/api/todolist/{wid}/submit")
    async def submit_todolist_item(wid: str, req: SubmitReq):
        """A person turns a work item in (the product's form submission): output stored, SUBMITTED, engine processes it."""
        try:
            rt = _rt()
            item = await _in_executor(rt.workitem_view,wid)
            if item['tool'] == 'formHandler:select_card':
                raise HTTPException(403,'조치 카드 승인은 /select의 역할 검사를 거쳐야 합니다')
            if item['tool'] == approval_part.TOOL:
                raise HTTPException(403,'사람 승인(안 고르기)은 /approve의 역할 검사를 거쳐야 합니다')
            if item.get('agent_mode') or item.get('agent_orch'):
                raise HTTPException(403,'사람 작업만 이 경로로 제출할 수 있습니다')
            return await _in_executor(rt.submit_human, wid, req.output, req.by)
        except KeyError:
            raise HTTPException(404, "no such work item")
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post('/api/todolist/{wid}/close')
    async def close_agent_task(wid: str, req: CloseReq):
        """A082: a person closes a stuck agent task (PENDING / run failed) with a reason; never a human task or a live one."""
        try:
            return await _in_executor(_rt().close_agent_task, wid, req.by, req.reason)
        except KeyError:
            raise HTTPException(404, 'no such work item')
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(409, str(e))

    @app.post('/api/todolist/{wid}/cancel')
    async def cancel_agent_task(wid: str, req: CloseReq):
        """A097: a person cancels a running agent task; the worker stops on its next check and releases the claim."""
        try:
            return await _in_executor(_rt().cancel_agent_task, wid, req.by, req.reason)
        except KeyError:
            raise HTTPException(404, 'no such work item')
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(409, str(e))

    @app.post('/api/todolist/{wid}/decision-preview')
    async def preview_card(wid: str, req: ReviewReq):
        try:
            return await _in_executor(_rt().preview_choice,wid,req.decision,req.option,req.parameters)
        except KeyError:
            raise HTTPException(404,'no such selection task')
        except ValueError as exc:
            raise HTTPException(409,str(exc))

    @app.post("/api/todolist/{wid}/select")
    async def select_card(wid: str, req: SelectReq):
        """The human task (task:select): one action card = one SOP skill. The role check comes from the ontology (Skill -APPROVED_BY-> Role)."""
        rt = _rt()
        try:
            out = await _in_executor(lambda: rt.select(wid, req.decision, req.option, req.by, req.role, req.reason,
                                    req.fan_pct, req.load_pct, review_id=req.review_id))
            approval = await _in_executor(rt.repo.get_approval, wid, rt.tenant_id)
            out['approval_status'] = approval['status']
            out['enterprise_results'] = approval['results']
            return out
        except KeyError:
            raise HTTPException(404, "no such selection task")
        except PermissionError as e:
            _ctx.audit("-", req.by, "DECISION_DENIED", {"decision": req.decision, "option": req.option, "role": req.role, "reason": str(e)})
            raise HTTPException(403, str(e))
        except instances.SourceUnavailable as e:      # P11: ERP 무응답 — 상태는 되돌려졌고 다시 누를 수 있다
            raise HTTPException(503, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/api/todolist/{wid}/reject-card")
    async def reject_card(wid: str, req: RejectCardReq):
        """조치 카드 승인 단계(formHandler:select_card)의 거절: 설비 명령 · 업무 거래 없이 흐름의 반려 가지로 간다. 승인(/select)과 같은 역할 검사."""
        try:
            return await _in_executor(_rt().reject_card, wid, req.decision, req.by, req.role, req.reason)
        except KeyError:
            raise HTTPException(404, "no such selection task")
        except PermissionError as e:
            _ctx.audit("-", req.by, "DECISION_DENIED", {"decision": req.decision, "option": None, "role": req.role, "reason": str(e)})
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/api/todolist/{wid}/approve")
    async def approve_option(wid: str, req: ApproveReq):
        """캡스톤 G1 일반 사람 승인(formHandler:approve): 에이전트가 낸 안 하나를 승인하거나 반려한다. 승인자 = "나"(역할 구성원 검사)."""
        try:
            return await _in_executor(_rt().approve, wid, req.decision, req.option, req.by, req.role, req.reason)
        except KeyError:
            raise HTTPException(404, "no such approval task")
        except PermissionError as e:
            _ctx.audit("-", req.by, "APPROVAL_DENIED", {"workitem": wid, "role": req.role, "reason": str(e)})
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post('/api/todolist/{wid}/approval-retry')
    async def retry_approval(wid: str, req: ApprovalRetryReq):
        try:
            return await _in_executor(_rt().retry_approval, wid, req.by, req.role)
        except KeyError:
            raise HTTPException(404, 'no such approval work item')
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(409, str(e))

    @app.post('/api/todolist/{wid}/work-order-retry')
    async def retry_work_order(wid: str, req: ApprovalRetryReq):
        rt=_rt()
        try:
            await _in_executor(rt.retry_work_order, wid, req.by, req.role)
            return await _in_executor(rt.repo.get_workitem,wid)
        except KeyError:
            raise HTTPException(404,'no such work item')
        except PermissionError as e:
            raise HTTPException(403,str(e))
        except ValueError as e:
            raise HTTPException(409,str(e))

    @app.post('/api/todolist/{wid}/approval-discard-preview')
    async def preview_approval_discard(wid: str, req: ApprovalRetryReq):
        try:
            return await _in_executor(_rt().preview_approval_discard, wid, req.by, req.role)
        except KeyError:
            raise HTTPException(404, 'no such approval work item')
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        except Exception as exc:
            raise HTTPException(503, '실행 효과 조회 실패: ' + str(exc)[:200])

    @app.post('/api/todolist/{wid}/approval-discard')
    async def discard_approval(wid: str, req: ApprovalDiscardReq):
        try:
            return await _in_executor(_rt().discard_approval, wid, req.by, req.role, req.reason, req.request_id)
        except KeyError:
            raise HTTPException(404, 'no such approval work item')
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        except Exception as exc:
            raise HTTPException(503, '폐기 처리 실패: ' + str(exc)[:200])

    @app.post('/api/todolist/{wid}/reassess')
    async def reassess_task(wid: str, req: ReassessmentReq):
        rt=_rt()
        try:
            return await _in_executor(partial(task_deferral.reassess,rt.repo,rt.tenant_id,wid,
                                              **req.model_dump()))
        except KeyError:
            raise HTTPException(404,'no such work item')
        except ValueError as exc:
            raise HTTPException(409,str(exc))

    @app.post("/api/todolist/{wid}/human-response")
    async def human_response(wid: str, req: HumanResponseReq):
        """A person answers the agent's question (human_asked → human_response); the worker resumes the task."""
        try:
            return await _in_executor(_rt().answer_human, wid, req.job_id, req.answer, req.by)
        except KeyError:
            raise HTTPException(404, "no such work item")
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(409,str(e))

    @app.get("/api/events")
    async def list_events(response: Response, proc_inst_id: str | None = None, todo_id: str | None = None, limit: int = 500,
                          before: str | None = None, page: bool = False):
        """Newest `limit` events, oldest first (unchanged default). A161-G4 paging: `before=<event id>` returns the page just
        older than that event (keyset on timestamp · id). Every answer says whether older rows remain — headers
        X-Events-Has-More (1/0) and X-Events-Before (the cursor for the next older page) — and `page=true` wraps the rows as
        {events, has_more, before} for a client that cannot read headers."""
        rt = _rt()
        if not proc_inst_id and not todo_id:
            raise HTTPException(400,'proc_inst_id 또는 todo_id를 지정하세요')
        try:
            if proc_inst_id and await _in_executor(rt.instance_view,proc_inst_id) is None:
                raise HTTPException(404,'no such instance')
        except instances.InstanceRemoved as e:
            raise HTTPException(404,str(e))
        if todo_id:
            try:
                await _in_executor(rt.workitem_view,todo_id)
            except KeyError:
                raise HTTPException(404,'no such work item')
        limit = max(1, min(int(limit), EVENTS_PAGE_MAX))
        try:
            rows = await _in_executor(rt.repo.list_events, proc_inst_id, todo_id, limit + 1, before)
        except LookupError as e:                       # an unknown cursor is an error, not an empty "no older rows" page
            raise HTTPException(404, str(e)) from e
        has_more = len(rows) > limit
        rows = rows[-limit:]
        cursor = rows[0]["id"] if has_more and rows else None
        response.headers["X-Events-Has-More"] = "1" if has_more else "0"
        if cursor:
            response.headers["X-Events-Before"] = str(cursor)
        return {"events": rows, "has_more": has_more, "before": cursor} if page else rows

    @app.get("/api/event-payloads/{payload_id}")
    async def get_event_payload(payload_id: str, offset: int = 0, limit: int = PAYLOAD_CHUNK_CHARS):
        """A161-G2: the full tool result an events row points at (data.full_output.ref), in chunks of `limit` characters."""
        rt = _rt()
        if not re.fullmatch(r"[0-9a-f]{64}", payload_id or ""):
            raise HTTPException(400, "payload id 는 sha256 16진수 64자입니다")
        row = await _in_executor(rt.repo.get_event_payload, payload_id)
        if not row:
            raise HTTPException(404, "no such payload")
        # a payload is read only through its case: no case or another tenant's case → not found (fail closed)
        inst = await _in_executor(rt.repo.get_instance, row["proc_inst_id"]) if row.get("proc_inst_id") else None
        if not inst or inst.get("tenant_id") != rt.tenant_id:
            raise HTTPException(404, "no such payload")
        if inst.get("is_deleted"):
            raise HTTPException(404, instances.REMOVED_REASON)
        content = row.get("content") or ""
        offset, limit = max(0, int(offset)), max(1, min(int(limit), PAYLOAD_CHUNK_CHARS))
        end = offset + limit
        return {**{k: row.get(k) for k in ("id", "chars", "content_type", "source", "tool", "tool_use_id", "job_id", "todo_id",
                                         "proc_inst_id", "meta", "created_at")},
                "offset": offset, "content": content[offset:end], "next_offset": end if end < len(content) else None}

    @app.get("/api/users")
    async def list_users():
        rt = _rt()
        return await _in_executor(rt.repo.list_users,None,rt.tenant_id)

    @app.get("/api/forms/{form_id}")
    async def get_form(form_id: str):
        rt = _rt()
        form = await _in_executor(rt.repo.get_form, form_id, rt.tenant_id)
        if form is None:
            raise HTTPException(404, "no such form")
        return form
