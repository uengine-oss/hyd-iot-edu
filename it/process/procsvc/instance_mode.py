"""Instance mode wiring for the process service (PROCESS_MODE=instance).

main.py keeps the legacy behaviour and calls into this module at four points: startup, every Incident transition,
every alerts RAISE message, and when the legacy agent submits a decision. Everything else that instance mode needs
(hooks, the engine polling loop, HTTP routes) lives here so main.py stays a thin FastAPI shell.

    main.py ──start(ctx)──▶ InstanceRuntime(repo, definition, hooks) + polling loop (SUBMITTED → engine, timers, stale consumers)
            ──on_incident_update(inc)──▶ service tasks task:command / task:reobserve are turned in from Incident states
            ──on_alert_raise(alert)──▶ a RAISE opens an instance (message start event)
            ──bridge_legacy_agent(decision)──▶ AGENT_BRIDGE=legacy plays the four agent tasks through the worker's own RPCs
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from functools import partial

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from hydcommon.timeutil import now_iso
from . import decisions as declib, definition, engine, instances, machine, procdb, work_orders
from .definition_registry import validate_definition
from .approval_hooks import DecisionDelivery, record_execution as _record_execution
from . import task_deferral
from .legacy_assessment import LegacyAssessment

log = logging.getLogger("process.instance_mode")

DEFINITIONS_DIR = Path(os.getenv("PROCESS_DEFINITIONS", "/srv/definitions"))
DEFINITION_FILE = os.getenv("PROCESS_DEFINITION_FILE", "anomaly_response_v22.json")   # A116: 2.2 = 2.1 in the product's agent-task shape
# legacy: while the cliagents worker is absent, the legacy agent's card + decision complete the instance's agent tasks
#         through the same RPCs the worker would use (fetch_pending_task → save_task_result).   off: the tasks wait for the worker.
AGENT_BRIDGE = os.getenv("AGENT_BRIDGE", "legacy")
POLL_INTERVAL_S = float(os.getenv("ENGINE_POLL_INTERVAL_S", "2"))     # the product polls every 5 s; faster here for the classroom
WORKER_URL = os.getenv("WORKER_URL", "http://agent-worker:8097")       # the cliagents worker's /health · /agents (monitoring, 회의 L434)
STALE_CLEANUP_EVERY = 150                                              # × POLL_INTERVAL_S ≈ 5 min (the product's cleanup_task)
# A151 (A148 item 70-A): how long startup waits for an unreachable DB before giving up and letting the restart policy act
STARTUP_DB_WAIT_S = float(os.getenv("PROCESS_STARTUP_DB_WAIT_S", "60"))


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
    approve_incident: Callable[[object, str, list[dict]], dict]   # (incident, by, commands) -> action.cmd
    get_loop: Callable[[], asyncio.AbstractEventLoop | None]
    check_approval: Callable[[dict, str, str], dict]  # must reread current policy/sources; explicit test double in unit tests
    after_incident: Callable | None = None
    reviews: Callable | None = None
    record_incident: Callable | None = None
    approval_receipts: Callable | None = None
    accept_evaluation: Callable | None = None
    exec_compensation: Callable | None = None     # (request) → enterprise /api/exec with a compensation skill (A072)


_runtime: instances.InstanceRuntime | None = None
_ctx: ProcessContext | None = None
stream_clients = 0            # A131: open /api/events/stream generators (memory diagnostics; must return to 0 after disconnects)


def current() -> instances.InstanceRuntime | None:
    return _runtime


# ---------------------------------------------------------------- lifecycle
async def event_stream(repo, since: str | None, is_disconnected, interval: float = 0.7, keepalive_s: float = 15.0,
                       fetch: Callable | None = None, ts_key: str = "timestamp", history: int = 60):
    """Yield SSE frames for every event newer than the cursor; the cursor is the newest timestamp seen (ids seen at that
    timestamp are kept, so a batch sharing one timestamp is never lost or repeated). Ends when the client disconnects.
    U5: `fetch(since, limit)` and `ts_key` let the same generator stream another table (notifications, inbox_api)."""
    global stream_clients
    stream_clients += 1
    try:
        async for frame in _event_frames(repo, since, is_disconnected, interval, keepalive_s, fetch or repo.list_events_since, ts_key, history):
            yield frame
    finally:
        stream_clients -= 1


async def _event_frames(repo, since, is_disconnected, interval, keepalive_s, fetch, ts_key, history):
    seen: set[str] = set()
    cursor = since
    if cursor is None:
        for e in await asyncio.to_thread(fetch, None, history):          # a short history so the panel is not empty
            seen.add(e["id"]); cursor = max(cursor or "", str(e.get(ts_key) or ""))
            yield "event: history\ndata: " + json.dumps(e, ensure_ascii=False, default=str) + "\n\n"
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
                yield "data: " + json.dumps(e, ensure_ascii=False, default=str) + "\n\n"
            idle = 0.0
        else:
            idle += interval
            if idle >= keepalive_s:
                idle = 0.0
                yield ": keepalive\n\n"
        await asyncio.sleep(interval)


def build(ctx: ProcessContext) -> instances.InstanceRuntime:
    """Create the runtime (repo + definition + hooks) and make it current. No background tasks — unit-testable."""
    global _runtime, _ctx
    _ctx = ctx
    repo = procdb.make_repo()
    defn = engine.Definition.load(DEFINITIONS_DIR / DEFINITION_FILE)
    _runtime = instances.InstanceRuntime(repo, defn, _hooks(ctx), time_scale=ctx.time_scale,
                                        tenant_id=os.getenv('TENANT_ID','hyd'), consumer=f"process-engine:{procdb.consumer_name()}")
    _runtime.register_definition(json.loads((DEFINITIONS_DIR/'alert_triage_v1.json').read_text(encoding='utf-8')))
    ctx.state["mode"], ctx.state["supabase"] = "instance", repo.ping()
    log.info("instance mode: definition %s (%d activities), repo %s, agent bridge %s", defn.id, len(defn.activities), type(repo).__name__, AGENT_BRIDGE)
    return _runtime


def start(ctx: ProcessContext) -> instances.InstanceRuntime:
    """build() plus the polling loop. Call from the FastAPI startup event (needs a running loop)."""
    rt = build(ctx)
    start_loops(rt, ctx)
    return rt


def start_loops(rt: instances.InstanceRuntime, ctx: ProcessContext) -> None:
    """The background loops of start(), split off so main.py can retry build() alone without starting a loop twice."""
    asyncio.create_task(_polling())
    if AGENT_BRIDGE == 'legacy':
        asyncio.create_task(_legacy_polling(rt,ctx))


def _transient_db_errors() -> tuple[type[BaseException], ...]:
    try:
        import psycopg
    except ImportError:          # MemoryRepo-only environments: nothing is a DB connection error
        return ()
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


def _evaluate_legacy(alert):
    url=os.getenv('AGENT_URL','http://agent:8091')+'/api/agent/evaluate'
    req=urllib.request.Request(url,data=json.dumps({'alert':alert}).encode(),
                               headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=90) as response:
        data=response.read(2_000_001)
    if len(data)>2_000_000:raise ValueError('agent evaluation response exceeds 2 MB')
    return json.loads(data)


async def _legacy_polling(rt,ctx):
    worker=LegacyAssessment(rt,_evaluate_legacy,ctx.accept_evaluation,_bridge_legacy_agent)
    while True:
        try:
            await _in_executor(worker.tick)
        except Exception:
            log.exception('legacy assessment delivery failed; durable attempt retained')
        await asyncio.sleep(POLL_INTERVAL_S)


async def _polling() -> None:
    """The completion polling of ProcessGPT: SUBMITTED rows → engine; boundary timers; stale consumers every ~5 min."""
    tick = 0
    while True:
        await asyncio.sleep(POLL_INTERVAL_S)
        tick += 1
        try:
            await _in_executor(_runtime.poll_once)
            if AGENT_BRIDGE == 'legacy':
                await _in_executor(reconcile_legacy_decisions)
            await _in_executor(_runtime.fire_timeouts)
            if tick % STALE_CLEANUP_EVERY == 0:
                await _in_executor(_runtime.repo.cleanup_stale_consumers)
        except Exception as e:  # noqa: BLE001
            log.warning("polling: %s", e)


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


def on_alert_raise(alert: dict) -> None:
    if _runtime is not None:
        _schedule(_runtime.on_alert_raise, alert)


def bridge_legacy_agent(decision: dict) -> None:
    if _runtime is not None and AGENT_BRIDGE == "legacy":
        _schedule(_bridge_legacy_agent, decision)


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

    def approve_commands(inc_id: str, commands: list[dict], by: str) -> dict:
        inc = ctx.incidents.get(inc_id)
        if inc is None:
            raise ValueError(f"no such incident {inc_id}")
        return ctx.approve_incident(inc, by, commands)

    def incident_state(inc_id: str) -> str | None:
        inc = ctx.incidents.get(inc_id)
        return inc.state if inc is not None else None

    def reopen_incident(inc_id: str, request_id: str, by: str, role: str, reason: str, effects: dict) -> bool:
        inc = ctx.incidents.get(inc_id)
        if inc is None:
            raise ValueError(f"no such incident {inc_id}")
        fx = work_orders._Audit()
        changed = machine.on_rework_reopen(inc, request_id, by, role, reason, effects, fx)
        if changed:
            ctx.persist()
            for event in fx.events:
                ctx.audit(event["asset"], event["actor"], event["event"], event["detail"], incident=inc.id)
            if ctx.after_incident:
                ctx.after_incident(inc)
        return changed

    def incident_snapshot(inc_id: str) -> dict | None:
        inc=ctx.incidents.get(inc_id)
        return {'state':inc.state,'cleared':inc.cleared,'cmdId':inc.cmd_id,'superseded':bool(inc.superseded)} if inc is not None else None

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

    return instances.Hooks(new_incident=open_incident, update_incident_card=update_incident_card, approve_commands=approve_commands,
                           incident_state=incident_state, incident_snapshot=incident_snapshot,
                           decision_option=decision_option, get_decision=lambda did: ctx.book.get(did), approve_decision=delivery.prepare,
                           preview_decision=delivery.preview, approve_review=delivery.prepare_review,
                           validate_approval=delivery.validate, deliver_approval=delivery.deliver, record_approval=delivery.record,
                           approval_effects=delivery.effects, rework_effects=lambda inst: collect_rework_effects(ctx, inst),
                           reopen_incident=reopen_incident, exec_compensation=ctx.exec_compensation,
                           exec_enterprise=exec_enterprise, record_cypher=ctx.cypher, query_cypher=ctx.cypher, audit=ctx.audit)


def _open_incident_for(ctx: ProcessContext, alert_id: str | None) -> machine.Incident | None:
    return next((i for i in list(ctx.incidents.values()) if i.alert_id == alert_id), None)


# ---------------------------------------------------------------- legacy agent bridge
def reconcile_legacy_decisions() -> None:
    """Recover persisted legacy results after SKIP LOCKED or process restart.

    An empty claim can be temporary. Only an already identified legacy run is
    resumed; changing the default bridge must never take over a Codex run.
    """
    if AGENT_BRIDGE != 'legacy' or _runtime is None or _ctx is None:
        return
    by_incident = {}
    for d in list(_ctx.book.values()):
        inc_id = (d.get('origin') or {}).get('incident')
        if inc_id:
            by_incident.setdefault(inc_id, []).append(d)
    for inc_id, decisions in by_incident.items():
        inst = _runtime.instance_of_incident(inc_id)
        if not inst or inst['status'] != 'RUNNING' or inst.get('is_deleted') or int(inst.get('rework_generation') or 0) > 0:
            continue
        rows = _runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'], limit=None)
        if not any(w['activity_id'] in {'task:diagnose','task:candidates','task:compliance','task:rank'}
                   and w['status'] in {'IN_PROGRESS','SUBMITTED'} for w in rows):
            continue
        started = _runtime.repo.agent_task_origins(inst['proc_inst_id'], _runtime.tenant_id)
        if any(not job.startswith('legacy:') for job in started):
            continue
        jobs = {job[len('legacy:'):] for job in started}
        if len(jobs) > 1:
            log.error('legacy recovery refused mixed decision jobs: %s', inst['proc_inst_id'])
            continue
        candidates = [d for d in decisions if not jobs or d['id'] in jobs]
        if candidates:
            _bridge_legacy_agent(max(candidates, key=lambda d: d.get('created') or ''))


def _bridge_legacy_agent(decision: dict) -> None:
    """The legacy agent did diagnose → candidates → compliance → rank in one Python run. Replay its results into the
    instance's four agent tasks exactly the way the cliagents worker would: fetch_pending_task → save_task_result(final),
    then the engine processes each SUBMITTED row (poll_once) which opens the next one."""
    inc_id = (decision.get("origin") or {}).get("incident")
    inst = _runtime.instance_of_incident(inc_id) if inc_id else None
    if inst is None:
        return
    if int(inst.get('rework_generation') or 0) > 0 or (decision.get('origin') or {}).get('process_scope'):
        return  # old deterministic results cannot populate a new generation or a claimed CLI run
    rows=_runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'],limit=None)
    if any(w['activity_id']=='task:diagnose' and w['status'] in {'PENDING','IN_PROGRESS'}
           and (w.get('feedback') or {}).get('reassessment') for w in rows):
        return  # a prior decision cannot substitute for the requested fresh assessment
    outputs = _legacy_outputs(decision, _ctx.incidents.get(inc_id))
    job_id = f"legacy:{decision['id']}"
    for _ in range(len(outputs)):
        wi = _claim_own(inst["proc_inst_id"])
        if wi is None:
            return
        _event(job_id, wi, inst, "task_started", {"goal": wi.get("activity_name"), "name": "legacy agent", "role": "L8 판단 파이프라인 (LLM 워커 없음)",
                                                   "task_description": (wi.get("query") or "")[:200]})
        if not _runtime.repo.save_task_result(wi["id"], outputs.get(wi["activity_id"], {}), final=True,
                                              expected_consumer='legacy-agent'):
            return
        _event(job_id, wi, inst, "task_completed", {"output_keys": sorted(outputs.get(wi["activity_id"], {}))})
        _runtime.poll_once()


def _claim_own(proc_inst_id: str) -> dict | None:
    """The bridge has one decision; claim only that instance before applying LIMIT.

    The real worker still polls the tenant queue. Never claim unrelated rows and
    reset their draft state: that can lose FB_REQUESTED or strand a batch claim.
    """
    with _runtime._transition(proc_inst_id):
        inst = _runtime.repo.get_instance(proc_inst_id)
        if int(inst.get('rework_generation') or 0) > 0:
            return None
        rows = _runtime.repo.fetch_pending_task("cliagents", "legacy-agent", limit=1,
                    tenant_id=_runtime.tenant_id, proc_inst_id=proc_inst_id)
    return rows[0] if rows else None


def _legacy_outputs(d: dict, inc: machine.Incident | None) -> dict[str, dict]:
    origin, opts = d.get("origin") or {}, d.get("options") or []
    return {
        "task:diagnose": {"cause": origin.get("cause"), "failure_mode": origin.get("failureMode"), "guide_card": inc.card if inc else {}},
        "task:candidates": {"candidates": [o["id"] for o in opts]},
        "task:compliance": {"compliance": {o["id"]: {"feasible": o.get("feasible"),
                                                     "excluded": [v.get("annotation") for v in o.get("violations") or []],
                                                     "penalties": [p.get("annotation") for p in o.get("penalties") or []],
                                                     "warnings": [w.get("annotation") for w in o.get("warnings") or []]} for o in opts}},
        "task:rank": {"decision": {"recommended": d.get("recommended"), "explanation": d.get("explanation"),
                                   "order": [f"{o.get('rank')}. {o.get('sopId')} {o.get('name')}" for o in opts]}, "decision_id": d["id"]},
    }


def _event(job_id: str, wi: dict, inst: dict, event_type: str, data: dict) -> None:
    _runtime.repo.record_events([{"job_id": job_id, "todo_id": wi["id"], "proc_inst_id": inst["proc_inst_id"], "crew_type": "result",
                                  "event_type": event_type, "data": data}])


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


class SubmitReq(BaseModel):
    output: dict | None = None
    by: str | None = None


class CloseReq(BaseModel):
    by: str
    reason: str


class SelectReq(BaseModel):
    decision: str
    option: str
    by: str = "승인자"
    role: str
    reason: str = ""
    fan_pct: float | None = None
    load_pct: float | None = None
    review_id: str | None = None


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
        raise HTTPException(409, "process is in legacy mode (set PROCESS_MODE=instance)")
    return _runtime


def mount(app: FastAPI, process_mode: str) -> None:
    @app.get("/api/process/mode")
    def process_mode_info():
        rt = _runtime
        return {"mode": process_mode, "agent_bridge": AGENT_BRIDGE if rt else None, "definition": rt.defn.id if rt else None,
                "repo": type(rt.repo).__name__ if rt else None, "time_scale": rt.time_scale if rt else None, "engine": rt.consumer if rt else None}

    @app.get("/api/process/definition")
    def process_definition():
        return _rt().defn.raw

    @app.get('/api/process/definitions')
    async def list_definitions():
        rt = _rt()
        rows = await _in_executor(rt.repo.list_definitions, rt.tenant_id)
        return [{'id':r['id'],'name':r.get('name'),'version':r['prod_version'],
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
        return StreamingResponse(event_stream(_rt().repo, since, request.is_disconnected), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/instances")
    async def list_instances(status: str | None = None, limit: int = 100):
        rt = _rt()
        return await _in_executor(rt.repo.list_instances, status, min(max(limit,1),500), rt.tenant_id)

    @app.get("/api/instances/{proc_inst_id}")
    async def get_instance(proc_inst_id: str):
        view = await _in_executor(_rt().instance_view, proc_inst_id)
        if view is None:
            raise HTTPException(404, "no such instance")
        return view

    @app.get("/api/instances/{proc_inst_id}/graph")
    async def get_instance_graph(proc_inst_id: str):
        """The instance as the ontology's Execution layer holds it (ProcessInstance · WorkItem · INSTANCE_OF · EXECUTES · ASSIGNED_TO · ROLE_BOUND)."""
        view = await _in_executor(_rt().execution_view, proc_inst_id)
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
        """Lecture helper: open an instance from a hand-written alert (the normal path is the Kafka alerts RAISE message)."""
        rt = _rt()
        try:
            if req.definition_id:
                event_id = req.event_id or (req.alert or {}).get('alertId')
                inst = await _in_executor(rt.start_definition,req.definition_id,req.version,event_id,
                                          req.variables,req.alert,req.name)
            elif req.alert is not None:
                inst = await _in_executor(rt.on_alert_raise, req.alert)
            else:
                raise ValueError('정의 ID/버전/event_id 또는 alert가 필요합니다')
        except LookupError as e:
            raise HTTPException(404,str(e))
        except ValueError as e:
            raise HTTPException(400,str(e))
        if inst is None:
            raise HTTPException(409, "alert already has a running instance or is malformed (needs alertId, asset)")
        return inst

    @app.get("/api/todolist")
    async def list_todolist(status: str | None = None, user_id: str | None = None, agent_orch: str | None = None,
                            proc_inst_id: str | None = None, limit: int = 200):
        rt = _rt()
        return await _in_executor(rt.repo.list_workitems, proc_inst_id, status, user_id, agent_orch, min(max(limit,1),500), rt.tenant_id)

    @app.get("/api/todolist/{wid}")
    async def get_todolist_item(wid: str):
        rt = _rt()
        try:
            return await _in_executor(rt.workitem_view,wid)
        except KeyError:
            raise HTTPException(404, "no such work item")
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
            if item.get('agent_mode') or item.get('agent_orch'):
                raise HTTPException(403,'사람 작업만 이 경로로 제출할 수 있습니다')
            return await _in_executor(rt.submit, wid, req.output, req.by)
        except KeyError:
            raise HTTPException(404, "no such work item")
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
            return await _in_executor(_rt().human_response, wid, req.job_id, req.answer, req.by)
        except KeyError:
            raise HTTPException(404, "no such work item")
        except ValueError as e:
            raise HTTPException(409,str(e))

    @app.get("/api/events")
    async def list_events(proc_inst_id: str | None = None, todo_id: str | None = None, limit: int = 500):
        rt = _rt()
        if not proc_inst_id and not todo_id:
            raise HTTPException(400,'proc_inst_id 또는 todo_id를 지정하세요')
        if proc_inst_id and await _in_executor(rt.instance_view,proc_inst_id) is None:
            raise HTTPException(404,'no such instance')
        if todo_id:
            try:
                await _in_executor(rt.workitem_view,todo_id)
            except KeyError:
                raise HTTPException(404,'no such work item')
        return await _in_executor(rt.repo.list_events, proc_inst_id, todo_id, limit)

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
