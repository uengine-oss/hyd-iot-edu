"""process (L9): mini-BPMN engine. Guide card in -> human approval -> action.cmd -> ACK -> re-observe -> work order -> close.

Only this service may write action.cmd (the agent has no command authority). Timers are asyncio tasks;
the latest TS1 for the re-observation verdict comes from TimescaleDB.
"""
import asyncio
import copy
import json
import logging
import os
import urllib.error
import urllib.request
from contextlib import nullcontext

import psycopg
from fastapi import HTTPException
from pydantic import BaseModel

from hydcommon import topics
from hydcommon.kafka import consumer as make_consumer, producer as make_producer
from hydcommon.metrics import Registry
from hydcommon.service import make_app
from hydcommon.timeutil import now, now_iso
from . import decisions as declib, definition, ingest, graph_ingest, instance_mode, kgadmin, machine, work_orders, current_approval, engine
from .store import Store
from . import skill_graph
from . import ranking_policy
from . import bsc_conditions
from .knowledge_projection import KnowledgeReconciler
from .case_projection import CaseProjector, incident_params as _incident_params
from .source_inbox import PgSourceInbox, kafka_record, source_record
from .source_delivery import SourceDelivery, SourcePending

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("process")
TIME_SCALE = float(os.getenv("TIME_SCALE", "20"))
PG_DSN = os.getenv("PG_DSN", "postgresql://hyd:hyd@timescaledb:5432/hyd")
ENTERPRISE_URL = os.getenv("ENTERPRISE_URL", "http://enterprise-sim:8095")
# legacy  : the agent submits a guide card → Incident (v2 behaviour, scenario_test.py 62/62)
# instance: an alert opens a process instance; the agent and the people are tasks inside it (ProcessGPT-shaped, docs/HANDOFF.md)
PROCESS_MODE = os.getenv("PROCESS_MODE", "legacy")

reg = Registry()
c_inc = reg.counter("process_incidents_total", "incidents by terminal state")
g_open = reg.gauge("process_open_incidents", "incidents not in a terminal state")
state = {"kafka": False, "incidents": 0}
incidents: dict[str, machine.Incident] = {}
book: dict[str, dict] = {}          # action-card decisions (L9, ontology v2)
audit_log: list[dict] = []
SOURCE_BATCH_MAX = int(os.getenv('SOURCE_BATCH_MAX', '50'))   # A080: deliveries received per DB connection and per offset commit (~6 s at 20x)
plant_status: dict[str, dict] = {}   # latest plant.status per asset (PLC mode / state for the agent's DMN facts)
producer = None
loop: asyncio.AbstractEventLoop | None = None
store = None
source_inbox = None
source_delivery = None
case_projector = None
case_projection_event = None
case_projection_task = None
knowledge_reconciler = None


def persist():
    if store is not None:
        store.save(incidents, book, audit_log)
        _wake_case_projection()


class Fx(machine.Effects):
    """Effects for one incident: publish to Kafka, keep an audit copy, schedule timers."""

    def __init__(self, inc: machine.Incident):
        self.inc = inc

    def emit_cmd(self, cmd: dict) -> None:
        persist()  # durable CMD_ISSUED before any external side effect
        asyncio.run_coroutine_threadsafe(producer.send(topics.K_CMD, key=topics.asset_key(cmd["asset"]), value=cmd), loop)

    def emit_audit(self, evt: dict) -> None:
        audit_log.insert(0, evt)
        del audit_log[500:]
        asyncio.run_coroutine_threadsafe(producer.send(topics.K_AUDIT, key=topics.asset_key(self.inc.asset), value=evt), loop)

    def set_timer(self, name: str, seconds: float) -> None:
        cmd_id = self.inc.cmd_id          # the timer belongs to this command; a rework may supersede it before it fires
        loop.call_soon_threadsafe(lambda: asyncio.create_task(fire_timer(self.inc.id, name, seconds, cmd_id)))


async def fire_timer(inc_id: str, name: str, seconds: float, cmd_id: str | None = None):
    await asyncio.sleep(seconds)
    inc = incidents.get(inc_id)
    if not inc:
        return
    value = await asyncio.get_running_loop().run_in_executor(None, latest_tag, inc.asset, inc.recovery[0]) if name == "reobs" and inc.recovery else None
    machine.on_timer(inc, name, now(), value, Fx(inc), time_scale=TIME_SCALE, cmd_id=cmd_id)
    _after(inc)
    if inc.state == 'RESOLVED':
        rt = instance_mode.current()
        owned = await asyncio.get_running_loop().run_in_executor(None, rt.repo.incident_is_process_owned, inc.id) if rt else False
        if not owned:
            await asyncio.get_running_loop().run_in_executor(None, _complete_legacy_work_order, inc)


def latest_tag(asset: str, tag: str = "TS1") -> float | None:
    """Latest 1 s value of one tag (the incident's recovery tag: TS1 · PS1 · VS1) from TimescaleDB."""
    try:
        with psycopg.connect(PG_DSN, autocommit=True, connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("SELECT value FROM tag_1s WHERE asset=%s AND name=%s ORDER BY time DESC LIMIT 1", (asset, tag))
            row = cur.fetchone()
            return float(row[0]) if row else None
    except Exception as e:  # noqa: BLE001
        log.warning("latest_tag %s failed: %s", tag, e)
        return None


def latest_ts1(asset: str) -> float | None:
    return latest_tag(asset, "TS1")


def _after(inc: machine.Incident):
    """Runs on the event loop or on a worker thread (instance-mode hooks), so it schedules through the global loop."""
    persist()
    if inc.state in definition.TERMINAL:
        c_inc.inc(state=inc.state)
        if inc.state == "CLOSED" and loop is not None:
            loop.run_in_executor(None, record_incident, inc)
    g_open.set(sum(1 for i in list(incidents.values()) if i.state not in definition.TERMINAL))
    instance_mode.on_incident_update(inc)


def _wake_case_projection():
    if loop is not None and case_projection_event is not None and not loop.is_closed():
        loop.call_soon_threadsafe(case_projection_event.set)


def record_incident(inc: machine.Incident) -> None:
    # Only wake delivery; the mutable caller snapshot is never graph authority.
    _wake_case_projection()


def _incident_projected(incident_id):
    rt = instance_mode.current()
    if rt is not None:
        rt.repo.enqueue_incident_projections(rt.tenant_id, incident_id)


def _ddl_sync_once():
    """A087: compare physical InputData bindings with the live business catalog (see ddl_sync)."""
    import psycopg
    from . import ddl_sync
    from .procdb import SUPABASE_DSN
    report = ddl_sync.sync(_q, lambda: psycopg.connect(SUPABASE_DSN, connect_timeout=5))
    if report.get('changed'):
        _audit("-", "process", "DDL_SOURCE_DRIFT", {"changes": report["changes"][:50]})
    return report


def _scm_sync_once():
    """A089: SCM master data (supplier AVL, quotes of the parts ent holds) → graph (see scm_sync)."""
    import psycopg
    from . import scm_sync
    from .procdb import SUPABASE_DSN
    report = scm_sync.sync(_q, lambda: psycopg.connect(SUPABASE_DSN, connect_timeout=5))
    if report.get('changed'):
        _audit("-", "process", "SCM_SOURCE_SYNCED", {k: report[k] for k in ("set_suppliers", "set_quotes", "delete_quotes")})
    return report


def _lease_sweep_once():
    """A097: a worker run whose lease expired three times is marked FAILED so a person can close it (A082)."""
    from . import procdb
    rt = instance_mode.current()
    n = rt.repo.expire_worker_leases() if rt is not None else 0
    if n:
        log.warning("worker lease sweep: %d run(s) marked FAILED after %d expired claims", n, procdb.MAX_CLAIMS)
    return {"failed": n}


async def _ddl_sync_loop():
    interval = float(os.getenv("DDL_SYNC_INTERVAL_S", "60"))
    while True:
        for name, once in (("DDL source", _ddl_sync_once), ("SCM source", _scm_sync_once), ("worker lease", _lease_sweep_once)):
            try:
                await asyncio.to_thread(once)
            except Exception:  # noqa: BLE001
                log.exception("%s sync failed; the graph keeps its last synced state", name)
        await asyncio.sleep(interval)


async def _case_projection_loop():
    while True:
        try:
            await asyncio.wait_for(case_projection_event.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
        case_projection_event.clear()
        try:
            if knowledge_reconciler is not None:
                await asyncio.to_thread(knowledge_reconciler.poll)
            await asyncio.to_thread(case_projector.drain)
        except Exception:
            log.exception('case graph recovery loop failed; durable jobs remain pending')




async def _alert_policy_retrying(pattern):
    """A108: classifying a RAISE needs the DB; a transient failure there must not end the consumer for good. Observed
    2026-10-07 08:01:10 right after a container restart (libpq fell to the unreachable IPv6 host.docker.internal):
    `consumer task ended: OperationalError`, /healthz 503, every later alert ignored until a manual restart. Now the lookup
    retries with backoff; the offset is not committed meanwhile (durable path) and /healthz shows source_policy_error."""
    delay = 1.0
    while True:
        try:
            policy = await asyncio.to_thread(instance_mode.current().alert_policy, pattern)
            state.pop('source_policy_error', None)
            return policy
        except Exception as exc:  # noqa: BLE001 — psycopg OperationalError/InterfaceError, DNS, pool exhaustion
            state['source_policy_error'] = f"{type(exc).__name__}: {str(exc)[:200]}"
            log.exception('alert policy lookup failed; retrying in %.0fs', delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)


async def _receive_retrying(pairs):
    """A120: the receipt itself opens a DB connection; right after a container restart libpq may pick the unreachable IPv6
    host.docker.internal (2026-10-07 13:37:45: `consumer task ended: OperationalError` raised from source_inbox.receive_many
    → /healthz 503 and every later alert, pump·fan included, ignored until a manual restart — A108 had covered only the
    policy lookup). Same contract as _alert_policy_retrying: retry with backoff, nothing committed meanwhile, /healthz shows
    source_receive_error until the receipt succeeds."""
    delay = 1.0
    while True:
        try:
            out = await asyncio.to_thread(source_inbox.receive_many, pairs)
            state.pop('source_receive_error', None)
            return out
        except Exception as exc:  # noqa: BLE001 — psycopg OperationalError/InterfaceError, DNS, pool exhaustion
            state['source_receive_error'] = f"{type(exc).__name__}: {str(exc)[:200]}"
            log.exception('source receipt unavailable; retrying in %.0fs', delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)


async def consume():
    global producer
    producer = await make_producer()
    durable=source_inbox is not None
    cons = await make_consumer([topics.K_STATUS, topics.K_ALERTS], group="process", from_latest=not durable,
                               auto_commit=not durable,raw_values=durable)
    state["kafka"] = True
    log.info("consuming plant.status (ACK) and alerts (CLEAR)")
    from aiokafka import TopicPartition
    while True:
      batches = await cons.getmany(timeout_ms=250, max_records=SOURCE_BATCH_MAX)
      if not batches:
          continue
      for tp, recs in batches.items():
        if durable:
            # A080: receive the whole fetched batch on one DB connection (one committed transaction per receipt, as
            # before) and commit the offset once per batch. On a receipt failure the failed delivery and everything after
            # it stay unacknowledged and are retried; nothing is committed past a missing event.
            items=[]
            for rec in recs:
                record=kafka_record(rec)
                policy=None
                if record['kind']=='RAISE':
                    policy=await _alert_policy_retrying(record['payload'].get('pattern'))
                items.append((rec,record,policy))
            start=0
            while start<len(items):
                rows,error,states=await _receive_retrying([(r,p) for _,r,p in items[start:]])
                done=start+len(rows)
                if states:
                    plant_status.update(states)
                if done>start:
                    last=items[done-1][0]
                    try:
                        await cons.commit({TopicPartition(last.topic,last.partition):last.offset+1})
                    except Exception:
                        # Rebalance/network failure may redeliver an already committed
                        # receipt. Every later offset also passes receive() first.
                        log.exception('durable source will tolerate offset redelivery: %s/%s/%s',last.topic,last.partition,last.offset)
                if error is None:
                    state.pop('source_receive_error',None)
                    break
                failed=items[done][0]
                state['source_receive_error']=str(error)
                log.error('source receipt failed: %s/%s/%s: %s',failed.topic,failed.partition,failed.offset,error)
                start=done
                await asyncio.sleep(1)
            continue
        for rec in recs:
          try:
              _legacy_record(rec)
          except Exception:  # noqa: BLE001 — A108: one failed receipt must not end the consumer (legacy auto-commit path)
              log.exception('legacy record handling failed on %s/%s', rec.topic, rec.offset)


def _legacy_record(rec):
        v = rec.value
        if not isinstance(v, dict) or "_raw" in v:
            log.warning("ignoring malformed record on %s", rec.topic)
            return
        if rec.topic == topics.K_STATUS and v.get("asset"):
            plant_status[v["asset"]] = v
        if rec.topic == topics.K_ALERTS and v.get("state") == "RAISE":
            instance_mode.on_alert_raise(v)      # message start event (ev:alert): one RAISE opens one process instance
            if instance_mode.current() is None and definition.recovery_for(v.get('pattern')) is None:
                if not any(i.alert_id==v.get('alertId') for i in list(incidents.values())):
                    inc=machine.Incident.from_card(machine.new_incident_id(),{'alert':v,'recommended':[]})
                    machine.on_card(inc);incidents[inc.id]=inc;state['incidents']=len(incidents)
                    _audit(inc.asset,'process','UNSUPPORTED_ALERT_PATTERN',{'alert':v},incident=inc.id)
                    _after(inc)
        for inc in list(incidents.values()):
            if inc.state in definition.TERMINAL:
                if (rec.topic == topics.K_ALERTS and inc.reason == 'UNSUPPORTED_ALERT_PATTERN'
                        and v.get('alertId') == inc.alert_id and v.get('state') == 'CLEAR' and not inc.cleared):
                    machine.on_alert(inc,v,Fx(inc))
                    _after(inc)  # Source CLEAR is recorded; ESCALATED remains human review.
                continue  # next incident
            try:
                if rec.topic == topics.K_STATUS and v.get("asset") == inc.asset:
                    machine.on_status(inc, v, now(), Fx(inc), time_scale=TIME_SCALE)
                elif rec.topic == topics.K_ALERTS:
                    machine.on_alert(inc, v, Fx(inc))
                _after(inc)
            except Exception as e:  # noqa: BLE001
                log.warning("record on %s failed for %s: %s", rec.topic, inc.id, e)


def _apply_source_event(receipt):
    value=receipt['payload'];rt=instance_mode.current()
    if receipt['kind']=='CLEAR':
        inc=next((i for i in list(incidents.values()) if i.alert_id==value['alertId']),None)
    else:
        inc=next((i for i in list(incidents.values()) if i.cmd_id==value['cmdId']),None)
    if inc is None:raise SourcePending('연결할 원천 사건/명령이 아직 없습니다')
    if value['asset']!=inc.asset or (receipt['kind']=='CLEAR' and 'pattern' in value and value['pattern']!=inc.pattern):
        raise ValueError('원천 해제/응답의 설비 또는 경보 패턴이 사건과 다릅니다')
    inst=rt.instance_of_incident(inc.id)
    # Use the same instance lock as approval/task transitions. Source receipt
    # fencing alone cannot prevent a previously running handler from finishing.
    with rt._transition(inst['proc_inst_id']) if inst else nullcontext():
        if receipt['kind']=='CLEAR' and not inc.cleared:
            machine.on_alert(inc,value,Fx(inc))
        elif receipt['kind']=='ACK':
            machine.on_status(inc,value,now(),Fx(inc),time_scale=TIME_SCALE)
        persist()
        rt.on_incident_update(inc.state,inc.id,inc.cleared)
        return {'incident':inc.id,'state':inc.state,'cleared':inc.cleared,'cmdId':inc.cmd_id,
                'ack':inc.ack,'disposition':'correlated source observed; recovery is not inferred'}


async def _source_loop():
    while producer is None:await asyncio.sleep(.1)
    while True:
        try:
            result=await source_delivery.run_once()
            state.pop('source_handler_error',None)
            if result is None:await asyncio.sleep(.2)
        except Exception as exc:
            state['source_handler_error']=str(exc)
            log.exception('source handler unavailable')
            await asyncio.sleep(1)


app = make_app("process (L9: mini-BPMN — approval, action.cmd, ACK, re-observation, work order)", reg,
               lambda: {**state, "ok": state["kafka"] and not any(state.get(k) for k in
                    ('consumer_dead','source_receive_error','source_handler_error','source_policy_error'))})
instance_mode.mount(app, PROCESS_MODE)      # /api/instances · /api/todolist · … (409 unless PROCESS_MODE=instance)

from . import memdebug
if memdebug.enabled():                      # A131: GET /debug/memory only with PROCESS_MEMDEBUG=1 (OOM diagnosis, dev only)
    def _snapshot_bytes():
        if store is None:
            return None
        with store._lock:
            row = store.db.execute("select length(body) from snapshot where id=1").fetchone()
        return row[0] if row else 0

    memdebug.register(app, {
        "incidents": lambda: len(incidents), "book": lambda: len(book), "audit_log": lambda: len(audit_log),
        "plant_status": lambda: len(plant_status), "state_keys": lambda: sorted(state),
        "metrics_series": lambda: {n: len(s) for n, s in list(reg._counters.items()) + list(reg._gauges.items())},
        "sse_stream_clients": lambda: instance_mode.stream_clients,
        "snapshot_json_bytes": _snapshot_bytes,
        "case_projection_pending": lambda: store.case_projection_status(limit=1)["pending"] if store else None,
        "runtime": lambda: (lambda rt: None if rt is None else {
            "repo": type(rt.repo).__name__, "repo_local": sorted(vars(rt.repo._local)) if hasattr(rt.repo, "_local") else None,
            "runtime_local": sorted(vars(rt._local)), "memory_repo_sizes": {k: len(v) for k, v in vars(rt.repo).items()
                                                                           if isinstance(v, (dict, list))} if type(rt.repo).__name__ == "MemoryRepo" else None,
        })(instance_mode.current()),
    }, get_loop=lambda: loop)


def _approve_incident(inc: machine.Incident, by: str, commands: list[dict]) -> dict:
    rt = instance_mode.current()
    inst = rt.instance_of_incident(inc.id) if rt else None
    current_id = engine.variables(inst).get('decision_id') if inst else None
    choices = [d for d in book.values() if (d.get('origin') or {}).get('incident') == inc.id
               and (not inst or d.get('id') == current_id)
               and d.get('chosen') and d.get('state') in ('APPROVED', 'PARTIAL', 'EXECUTED')]
    if len(choices) != 1:
        raise ValueError('명령 발행에 필요한 단일 승인 판단을 확인할 수 없습니다')
    d = choices[0]
    _check_current_approval(d, d['chosen'], d['approvedRole'])
    from .approval_hooks import require_reviewed_commands
    require_reviewed_commands(next(o for o in d['options'] if o['id'] == d['chosen']), commands)
    cmd = machine.on_approve(inc, by, commands, now(), Fx(inc), time_scale=TIME_SCALE)
    _after(inc)
    return cmd


def _check_current_approval(d, option, role):
    report = current_approval.check(d, option, role)
    _audit(d.get('asset') or '-', 'process', 'APPROVAL_CURRENT_CHECK', report,
           incident=(d.get('origin') or {}).get('incident'))
    return current_approval.require(lambda *_: report, d, option, role)


def _instance_context() -> instance_mode.ProcessContext:
    return instance_mode.ProcessContext(incidents=incidents, book=book, state=state, time_scale=TIME_SCALE, persist=persist, audit=_audit,
                                        cypher=_q, exec_skill=exec_skill, record_decision=record_decision, approve_incident=_approve_incident,
                                        get_loop=lambda: loop, check_approval=_check_current_approval, after_incident=_after,
                                        reviews=_review_service, record_incident=record_incident, approval_receipts=_approval_receipts,
                                        accept_evaluation=_publish_legacy_evaluation, exec_compensation=_exec_compensation)


def _exec_compensation(body: dict) -> dict:
    """POST one compensation skill (A072) to the enterprise systems; the enterprise keeps it idempotent per decision/skill/ref."""
    req = urllib.request.Request(ENTERPRISE_URL + "/api/exec", data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ValueError(f"enterprise refused the compensation: {e.code} {e.read().decode(errors='replace')[:200]}")


def _approval_receipts(decision_id):
    from urllib.parse import urlencode
    with urllib.request.urlopen(ENTERPRISE_URL + '/api/transactions?' + urlencode({'decision': decision_id}), timeout=10) as response:
        return json.loads(response.read())


def _review_service():
    from .decision_reviews import DecisionReviews
    if store is None:
        raise ValueError('검토본 저장소가 준비되지 않았습니다')
    return DecisionReviews(store,book,incidents,current_approval.preview)


def _watch(task):
    """If the consume loop ever exits, /healthz reports it (503) instead of looking healthy while doing nothing."""
    state["consumer_dead"] = True
    state["consumer_error"] = repr(task.exception()) if not task.cancelled() and task.exception() else "exited"
    log.error("consumer task ended: %s", state["consumer_error"])


@app.on_event("startup")
async def _startup():
    global loop, store, source_inbox, source_delivery, case_projector, case_projection_event, case_projection_task, knowledge_reconciler
    loop = asyncio.get_running_loop()
    store = Store(os.getenv("PROCESS_STATE_PATH", "/data/process.sqlite3"))
    saved_incidents, saved_book, saved_audit = store.restore()
    incidents.update(saved_incidents)
    # decisions made on the v1 ontology (Scenario / Option) cannot be shown or executed any more
    book.update({k: d for k, d in saved_book.items() if d.get("schema") == "v2"})
    audit_log[:] = saved_audit
    state["incidents"] = len(incidents)
    persist()
    if PROCESS_MODE == "instance":
        rt=instance_mode.start(_instance_context())
        source_inbox=PgSourceInbox(rt.repo,rt.tenant_id)
        plant_status.update(await asyncio.to_thread(source_inbox.latest_states))
        source_delivery=SourceDelivery(source_inbox,rt,_apply_source_event,owner=rt.consumer+'-source')
        asyncio.create_task(_source_loop()).add_done_callback(_watch)
    case_projector = CaseProjector(store, _q, _incident_projected)
    active_runtime=instance_mode.current()
    knowledge_reconciler=KnowledgeReconciler(store,_q,os.getenv('TENANT_ID','hyd'),active_runtime.repo if active_runtime else None)
    case_projection_event = asyncio.Event()
    case_projection_event.set()
    case_projection_task = asyncio.create_task(_case_projection_loop())
    asyncio.create_task(_ddl_sync_loop())
    asyncio.create_task(consume()).add_done_callback(_watch)


@app.get('/api/graph-projections')
async def graph_projection_status():
    if store is None:
        raise HTTPException(503, '사건 저장소가 준비되지 않았습니다')
    result = await asyncio.to_thread(store.case_projection_status)
    knowledge=await asyncio.to_thread(knowledge_reconciler.status) if knowledge_reconciler else None
    return result | {'worker_running': case_projection_task is not None and not case_projection_task.done(),'knowledge':knowledge}


class ApproveReq(BaseModel):
    approvedBy: str = "OP-17"
    actions: list[dict]


class RejectReq(BaseModel):
    by: str = "OP-17"
    reason: str = ""


class SourceRetryReq(BaseModel):
    by: str
    reason: str


@app.get('/api/source-events')
async def source_events(after_id: int=0,limit: int=100,status: str|None=None):
    if source_inbox is None:raise HTTPException(409,'원천 접수는 instance 모드에서 사용할 수 있습니다')
    try:return await asyncio.to_thread(source_inbox.list,after_id=after_id,limit=limit,status=status)
    except ValueError as exc:raise HTTPException(400,str(exc))


@app.get('/api/source-events/{receipt_id}')
async def source_event(receipt_id: int):
    if source_inbox is None:raise HTTPException(409,'원천 접수 저장소가 준비되지 않았습니다')
    row=await asyncio.to_thread(source_inbox.get,receipt_id)
    if row is None:raise HTTPException(404,'접수 기록이 없습니다')
    return row


@app.post('/api/source-events/{receipt_id}/retry')
async def retry_source_event(receipt_id: int,req: SourceRetryReq):
    if source_inbox is None:raise HTTPException(409,'원천 접수 저장소가 준비되지 않았습니다')
    try:row=await asyncio.to_thread(source_inbox.retry_failed,receipt_id,by=req.by,reason=req.reason)
    except ValueError as exc:raise HTTPException(400,str(exc))
    if row is None:raise HTTPException(409,'재시도할 FAILED 원천 접수가 아닙니다')
    return row


@app.post("/api/incidents")
async def create_incident(card: dict):   # async: mutates incidents on the loop thread, like consume()
    if not card.get("alert") or not card.get("recommended"):
        raise HTTPException(400, "card needs alert and recommended actions")
    alert_id = card["alert"].get("alertId")
    if not alert_id or not card['alert'].get('asset'):
        raise HTTPException(400,'alert에는 alertId와 asset이 필요합니다')
    rt=instance_mode.current()
    if rt is not None:
        try:
            if source_delivery is not None:
                record=source_record(topics.K_ALERTS,None,None,card['alert'],source='http')
                if record['kind']!='RAISE':raise ValueError('가이드에는 원천 RAISE 경보가 필요합니다')
                policy=await asyncio.to_thread(rt.alert_policy,record['payload'].get('pattern'))
                receipt=await asyncio.to_thread(source_inbox.receive,record,policy)
                await source_delivery.wait_for(receipt)
            else:
                await asyncio.get_running_loop().run_in_executor(None,rt.on_alert_raise,card['alert'])
        except (ValueError,LookupError) as exc:
            raise HTTPException(409,str(exc))
        except TimeoutError as exc:
            raise HTTPException(503,str(exc))
    for inc in list(incidents.values()):
        if inc.alert_id == alert_id:
            if (inc.asset,inc.pattern)!=(card['alert'].get('asset'),card['alert'].get('pattern')):
                raise HTTPException(409,'같은 경보 ID의 설비/패턴이 다릅니다')
            if rt is not None and inc.state=='AWAITING_APPROVAL' and not inc.card.get("recommended"):
                # instance mode: the incident was opened by the instance; the agent's card fills it in
                inc.card = dict(card, incident=inc.id, alert=inc.card['alert'])
                persist()
                return {"id": inc.id, "state": inc.state, "duplicate": True, "cardUpdated": True}
            return {"id": inc.id, "state": inc.state, "duplicate": True}
    inc = machine.Incident.from_card(machine.new_incident_id(), card)
    machine.on_card(inc)
    incidents[inc.id] = inc
    state["incidents"] += 1
    Fx(inc).emit_audit({"t": inc.created, "incident": inc.id, "asset": inc.asset, "actor": "agent", "event": "GUIDE_SUBMITTED",
                        "detail": {"alertId": alert_id, "topCause": card.get("topCause"), "citations": len(card.get("citations") or [])}})
    _after(inc)
    log.info("incident %s created for %s", inc.id, alert_id)
    return {"id": inc.id, "state": inc.state}


@app.get('/api/alerts/policy')
async def alert_execution_policy(pattern: str = ''):
    rt=instance_mode.current()
    if rt is not None:
        return await asyncio.get_running_loop().run_in_executor(None,rt.alert_policy,pattern)
    criterion=definition.recovery_for(pattern)
    return {'pattern':pattern,'route':'response' if criterion else 'triage','criterion':criterion,
            'definition':'legacy-incident','version':'explicit-patterns-v1'}


@app.get("/api/incidents")
def list_incidents():
    return [i.to_dict() | {"card": None} for i in sorted(incidents.values(), key=lambda i: i.created, reverse=True)]


@app.get("/api/incidents/{inc_id}")
def get_incident(inc_id: str):
    inc = incidents.get(inc_id)
    if not inc:
        raise HTTPException(404, "no such incident")
    rt=instance_mode.current()
    return inc.to_dict() | {'processOwned':bool(rt and rt.repo.incident_is_process_owned(inc_id))}


async def _require_legacy_incident(inc_id):
    rt = instance_mode.current()
    if rt and inc_id and await asyncio.get_running_loop().run_in_executor(None, rt.repo.incident_is_process_owned, inc_id):
        raise HTTPException(409, '프로세스 인스턴스의 사람 작업에서 승인·복구하세요')


async def _require_legacy_decision(d):
    if d.get('process_approval_id'):
        raise HTTPException(409, '이미 접수된 프로세스 승인입니다. 해당 작업에서 전달 상태를 확인하세요')
    await _require_legacy_incident((d.get('origin') or {}).get('incident'))


@app.post("/api/incidents/{inc_id}/approve")
async def approve(inc_id: str, req: ApproveReq):
    inc = incidents.get(inc_id)
    if not inc:
        raise HTTPException(404, "no such incident")
    await _require_legacy_incident(inc_id)
    raise HTTPException(409, '원자 명령만으로 승인할 수 없습니다. 조치 카드에서 SOP와 승인 역할을 선택하세요')


@app.post('/api/incidents/{inc_id}/work-order-retry')
async def retry_legacy_work_order(inc_id: str):
    inc = incidents.get(inc_id)
    if inc is None:
        raise HTTPException(404, 'no such incident')
    await _require_legacy_incident(inc_id)
    if inc.state not in ('RESOLVED', 'AWAITING_APPROVAL') or not inc.work_order_request:
        raise HTTPException(409, '재전달할 승인된 작업지시가 없습니다')
    if inc.state == 'AWAITING_APPROVAL' and not inc.work_order_request['work_order_only']:
        raise HTTPException(409, '설비 재관측이 끝나지 않았습니다')
    result = await asyncio.get_running_loop().run_in_executor(None, _complete_legacy_work_order, inc)
    if result.get('ok') is not True:
        raise HTTPException(502, result)
    return {'incident':inc.to_dict(), 'work_order':result}


@app.post("/api/incidents/{inc_id}/reject")
async def reject(inc_id: str, req: RejectReq):
    inc = incidents.get(inc_id)
    if not inc:
        raise HTTPException(404, "no such incident")
    await _require_legacy_incident(inc_id)
    try:
        machine.on_reject(inc, req.by, req.reason, Fx(inc))
    except ValueError as e:
        raise HTTPException(400, str(e))
    _after(inc)
    return {"id": inc.id, "state": inc.state}


@app.get("/api/audit")
def get_audit():
    return audit_log[:100]


@app.get("/api/plant/{asset}/status")
def get_plant_status(asset: str):
    """Latest plant.status (PLC mode · state · last ACK) — the agent's source for the DMN facts plc_mode / plc_state."""
    st = plant_status.get(asset)
    if not st:
        raise HTTPException(404, f"no plant.status seen for {asset} yet")
    return st


@app.get("/api/definition")
def get_definition():
    return definition.as_json() | {"time_scale": TIME_SCALE}


@app.get("/api/summary")
def summary():
    return {"open": [i.to_dict() | {"card": None} for i in list(incidents.values()) if i.state not in definition.TERMINAL],
            "total": len(incidents), "time_scale": TIME_SCALE}


# ---------------------------------------------------------------- enterprise decisions (L7 -> L8 -> L9)
class DecisionApproveReq(BaseModel):
    option: str
    by: str = "승인자"
    role: str
    reason: str = ""


class DecisionRejectReq(BaseModel):
    by: str = "승인자"
    reason: str = ""


def _audit(asset: str, actor: str, event: str, detail: dict, incident: str | None = None):
    evt = {"t": now_iso(), "incident": incident, "asset": asset, "actor": actor, "event": event, "detail": detail}
    audit_log.insert(0, evt)
    del audit_log[500:]
    persist()
    if producer is not None and loop is not None:   # callable from worker threads too (instance-mode hooks)
        asyncio.run_coroutine_threadsafe(producer.send(topics.K_AUDIT, key=topics.asset_key(asset if asset in ("HYD-01", "HYD-02", "HYD-03") else "HYD-01"), value=evt), loop)


# atomic system transactions of an SOP skill -> the enterprise-sim job that performs them
TX_JOBS = {"WO_CREATE": "skill:schedule-maintenance", "PR_CREATE": "skill:procure-part"}


def exec_skill(d: dict, item: dict) -> dict:
    """POST one approved system transaction (CMMS work order, ERP purchase request) of the chosen SOP skill."""
    opt = next(o for o in d["options"] if o["id"] == d["chosen"])
    job = TX_JOBS.get(item.get("code"))
    out = {"skill": item["skill"], "code": item.get("code"), "system": item.get("system")}
    if not job:
        return out | {"ok": False, "error": f"실행할 수 없는 트랜잭션 {item.get('code')}"}
    if item["code"] == "WO_CREATE":
        params = {"task": f"{item.get('sop') or opt.get('sopId')} {opt.get('name')} → 작업지시 {item.get('value')}",
                  "window": "야간 정비창" if "night" in opt["id"] else "즉시"}
    else:
        params = {"supplier": item.get("value") or "sup:b", "part": opt.get("name")}
    body = {"decision": d["id"], "option": opt["id"], "skill": job, "system": item.get("system"), "asset": d.get("asset"),
            "by": d.get("approvedBy"), "params": params}
    try:
        req = urllib.request.Request(ENTERPRISE_URL + "/api/exec", data=json.dumps(body, ensure_ascii=False).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            tx = json.loads(r.read())
        if not isinstance(tx.get('ref'), str) or not tx['ref'].strip():
            raise ValueError('enterprise response has no actual transaction reference')
        return out | {"ok": True, "ref": tx.get("ref"), "detail": tx.get("detail")}
    except Exception as e:  # noqa: BLE001
        return out | {"ok": False, "error": str(e)[:200]}


def _work_order_context():
    from types import SimpleNamespace
    return SimpleNamespace(incidents=incidents, persist=persist, audit=_audit, after_incident=_after)


def _freeze_legacy_work_order(inc, by):
    action = next((a for a in inc.card.get('recommended', []) if a.get('kind')=='work_order'), None)
    if action is None:
        raise ValueError('승인 가이드에 후속 작업지시가 없습니다. 정비 계획 검토가 필요합니다')
    option = {'id':action.get('skillId') or action.get('actionId') or action['code'],
              'sopId':(action.get('sop') or {}).get('id'),
              'name':(action.get('sop') or {}).get('name') or action.get('name'),
              'actions':[{'kind':'command'}]}
    item = {'skill':option['id'], 'sop':option['sopId'], 'code':'WO_CREATE',
            'name':option['name'], 'system':'sys:cmms', 'value':action.get('value'),
            'param':action.get('param'), 'source':'approved-legacy-guide'}
    d = {'id':inc.id, 'chosen':option['id'], 'approvedBy':by, 'options':[option],
         'asset':inc.asset, 'origin':{'incident':inc.id}}
    work_orders.prepare(_work_order_context(), d, item, allow_before_recovery=True)


def _complete_legacy_work_order(inc):
    """Legacy guide approval still requires a real, idempotent CMMS receipt."""
    item = {}
    try:
        saved = inc.work_order_request
        if saved:
            item = copy.deepcopy(saved['item'])
            option = {'id':saved['option'], 'sopId':item.get('sop'), 'name':saved['option_name'],
                      'actions':[{'kind':'command'}] if not saved['work_order_only'] else []}
            d = {'id':saved['decision'], 'chosen':saved['option'], 'approvedBy':saved['by'],
                 'options':[option], 'asset':inc.asset, 'origin':{'incident':inc.id}}
        else:
            raise ValueError('승인 당시의 작업지시 요청이 없습니다. 정비 계획 검토가 필요합니다')
        ctx = _work_order_context()
        work_orders.prepare(ctx, d, item)
        result = exec_skill(d, item)
        if result.get('ok') is not True:
            raise RuntimeError(result.get('error') or 'CMMS failed')
        work_orders.confirm(ctx, inc, item, result)
        decision = book.get(saved['decision'])
        if decision is not None:
            from .approval_hooks import record_execution
            record_execution(decision, result)
            persist()
        return result
    except Exception as exc:
        _audit(inc.asset, 'process', 'WORK_ORDER_FAILED', {'error':str(exc), 'retryable':inc.state=='RESOLVED'}, incident=inc.id)
        return {'ok':False, 'code':'WO_CREATE', 'error':str(exc),
                'skill':item.get('skill'), 'system':item.get('system', 'sys:cmms')}


def record_decision(d: dict) -> None:
    """The persisted source and queue own delivery, including retries/restart."""
    _wake_case_projection()


@app.post("/api/decisions")
async def create_decision(payload: dict):
    return await asyncio.get_running_loop().run_in_executor(None, _create_decision, payload)


def _create_decision(payload: dict):
    """Serialize acceptance with rework so a late producer cannot bind to a new generation."""
    if not payload.get("id") or not payload.get("options"):
        raise HTTPException(400, "decision needs id and options")
    origin = payload.get('origin') or {}
    rt = instance_mode.current()
    inst = rt.instance_of_incident(origin.get('incident')) if rt and origin.get('incident') else None
    with rt._transition(inst['proc_inst_id']) if inst else nullcontext():
        if inst:
            inst = rt.repo.get_instance(inst['proc_inst_id'])
            legacy=origin.get('legacy_attempt')
            if legacy is not None:
                if not isinstance(legacy,dict):raise HTTPException(409,'invalid legacy attempt')
                wi=rt.repo.get_workitem(legacy.get('workitem'))
                if (not wi or wi['proc_inst_id']!=inst['proc_inst_id'] or wi['status']!='IN_PROGRESS'
                        or wi.get('draft_status')!='STARTED' or wi.get('consumer')!=legacy.get('owner')):
                    raise HTTPException(409,'legacy assessment no longer owns the task')
            scope = origin.get('process_scope')
            if int(inst.get('rework_generation') or 0) > 0 or scope is not None:
                from .decision_scope import validate_submission
                try:
                    import uuid
                    wid = str(uuid.UUID(scope.get('workitem', ''))) if isinstance(scope, dict) else None
                    workitem = rt.repo.get_workitem(wid) if wid else None
                    validate_submission(inst, rt.definition_for(inst), workitem, scope)
                except (ValueError, TypeError, AttributeError) as error:
                    raise HTTPException(409, str(error))
        elif origin.get('process_scope') is not None:
            raise HTTPException(409, '판단의 활성 프로세스 인스턴스를 찾을 수 없습니다')
        elif (rt and origin.get('incident') and payload['id'] not in book
              and rt.repo.incident_is_process_owned(origin['incident'])):
            raise HTTPException(409, '종료된 프로세스 사건에 새 판단을 접수할 수 없습니다')
        return _store_decision(payload)


def _store_decision(payload):
    if payload["id"] in book:
        d = book[payload["id"]]
        if any((payload.get('origin') or {}).get(key) != (d.get('origin') or {}).get(key)
               for key in ('process_scope','legacy_attempt')):
            raise HTTPException(409, '같은 판단 ID를 다른 작업/세대에서 재사용할 수 없습니다')
        return {"id": d["id"], "state": d["state"], "duplicate": True}
    origin=payload.get('origin') or {}
    if origin.get('incident'):
        inc=incidents.get(origin['incident'])
        if not inc or inc.asset!=payload.get('asset') or (origin.get('pattern') is not None and origin['pattern']!=inc.pattern):
            raise HTTPException(409,'결정의 원천 사건/설비/패턴이 일치하지 않습니다')
        if inc.state!='AWAITING_APPROVAL' or inc.recovery is None:
            raise HTTPException(409,'이 사건은 조치 카드 접수 대상이 아닙니다. 현장 검토 상태를 확인하세요')
    d = declib.new(payload)
    book[d["id"]] = d
    _audit(d.get("asset") or "-", "agent", "DECISION_SUBMITTED",
           {"decision": d["id"], "cards": [o.get("sopId") for o in d.get("options", [])], "recommended": d.get("recommended")},
           incident=(d.get("origin") or {}).get("incident"))
    instance_mode.bridge_legacy_agent(d)
    return {"id": d["id"], "state": d["state"]}


def _publish_legacy_evaluation(payload,card):
    rt=instance_mode.current()
    if rt is None:raise ValueError('instance runtime required')
    rt.hooks.update_incident_card(payload['origin']['incident'],card)
    _create_decision(payload)
    return book[payload['id']]


@app.get("/api/decisions")
def list_decisions():
    return [{k: d.get(k) for k in ("id", "created", "scenario", "asset", "state", "recommended", "chosen", "approvedBy", "approvedRole",
                                    "override", "origin", "applicable")} for d in sorted(book.values(), key=lambda d: d["created"], reverse=True)]


@app.get("/api/decisions/{did}")
def get_decision(did: str):
    d = book.get(did)
    if not d:
        raise HTTPException(404, "no such decision")
    return d


@app.post("/api/decisions/{did}/approve")
async def approve_decision(did: str, req: DecisionApproveReq):
    d = book.get(did)
    if not d:
        raise HTTPException(404, "no such decision")
    await _require_legacy_decision(d)
    try:
        await asyncio.get_running_loop().run_in_executor(None, _check_current_approval, d, req.option, req.role)
        plan = declib.approve(d, req.option, req.by, req.role, req.reason)
    except PermissionError as e:
        _audit(d.get("asset") or "-", req.by, "DECISION_DENIED", {"decision": did, "option": req.option, "role": req.role, "reason": str(e)})
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    _audit(d.get("asset") or "-", req.by, "DECISION_APPROVED",
           {"decision": did, "option": req.option, "role": req.role, "override": d["override"], "reason": req.reason}, incident=(d.get("origin") or {}).get("incident"))
    loop_ = asyncio.get_running_loop()
    results = [await loop_.run_in_executor(None, exec_skill, d, item) for item in plan["enterprise"]]
    declib.record_execution(d, results, plan)
    persist()
    for r in results:
        _audit(d.get("asset") or "-", "process", "SKILL_EXECUTED" if r["ok"] else "SKILL_FAILED",
               {"decision": did, "skill": r["skill"], "code": r.get("code"), "system": r["system"], "ref": r.get("ref"), "detail": r.get("detail") or r.get("error")})
    loop_.run_in_executor(None, record_decision, d)
    return {"id": did, "state": d["state"], "executions": d["executions"]}


@app.post("/api/decisions/{did}/reject")
async def reject_decision(did: str, req: DecisionRejectReq):
    d = book.get(did)
    if not d:
        raise HTTPException(404, "no such decision")
    await _require_legacy_decision(d)
    try:
        declib.reject(d, req.by, req.reason)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _audit(d.get("asset") or "-", req.by, "DECISION_REJECTED", {"decision": did, "reason": req.reason})
    asyncio.get_running_loop().run_in_executor(None, record_decision, d)
    return {"id": did, "state": d["state"]}


# ---------------------------------------------------------------- knowledge administration (humans edit the ontology through L9)
def _kg():
    from neo4j import GraphDatabase
    user, pwd = os.getenv("NEO4J_AUTH", "neo4j/hydpass123").split("/", 1)
    return GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://neo4j:7687"), auth=(user, pwd))


def _q(cypher: str, **params) -> list[dict]:
    # managed write transaction: the driver retries a dropped connection and transient errors
    drv = _kg()
    try:
        with drv.session() as s:
            return s.execute_write(lambda tx: [r.data() for r in tx.run(cypher, **params)])
    finally:
        drv.close()


SKILL_Q = """
MATCH (k:Skill) WHERE $id IS NULL OR k.id = $id
OPTIONAL MATCH (k)-[:APPROVED_BY]->(r:Role)
RETURN k.id AS id, k.sopId AS sopId, k.name AS name, k.description AS description, k.kind AS kind, k._manual_document AS source_document, k.source_id AS source_id,
       CASE WHEN r IS NULL THEN null ELSE {id: r.id, name: r.name, level:r.level} END AS approver,
       COLLECT { MATCH (fm:FailureMode)-[m:MITIGATED_BY|REMEDIED_BY]->(k) RETURN {id: fm.id, name: fm.name, relation: type(m)} } AS failureModes,
       COLLECT { MATCH (k)-[:ADDRESSES]->(c:Cause) RETURN {id: c.id, name: c.name} } AS causes,
       COLLECT { MATCH (k)-[co:CONSISTS_OF]->(a:Action) RETURN {code: a.code, name: a.name, kind: a.kind, value: co.value} ORDER BY co.seq } AS actions,
       COLLECT { MATCH (k)-[:HAS_STEP]->(st:Step) OPTIONAL MATCH (st)-[:REFERS_TO]->(m:ManualSection)
                 RETURN {order: st.order, text: st.text, manual: m.ref} ORDER BY st.order } AS steps,
       COLLECT { MATCH (ru:Rule)-[:OUTPUTS|APPLIES_TO]->(k) RETURN {id: ru.id, effect: ru.effect, annotation: ru.annotation} } AS rules,
       COLLECT { MATCH (k)-[af:AFFECTS]->(x) RETURN {name: x.name, sign: af.sign} } AS affects,
       COLLECT { MATCH (sy)-[:HAS_SKILL]->(k) RETURN coalesce(sy.name, sy.id) } AS performers
ORDER BY sopId
"""


@app.get("/api/kg/skills")
async def kg_skills():
    return await asyncio.get_running_loop().run_in_executor(None, lambda: skill_graph.stamp(_q(SKILL_Q, id=None)))


@app.get("/api/kg/catalog")
async def kg_catalog():
    """Choices for the skill editor and the manual upload: roles, failure modes (조치 방법은 고장 유형에 매칭된다)."""
    def run():
        return {"roles": _q("MATCH (r:Role) RETURN r.id AS id, r.name AS name, r.level AS level ORDER BY r.level DESC, r.id"),
                "failureModes": _q("MATCH (f:FailureMode) RETURN f.id AS id, f.name AS name ORDER BY f.id"),
                "manualSections": _q("MATCH (m:ManualSection) RETURN m.id AS id, m.title AS name ORDER BY m.id")}
    return await asyncio.get_running_loop().run_in_executor(None, run)


def _author_skill(sid, values, body, create=False):
    driver = _kg()
    try:
        with driver.session() as session:
            return skill_graph.write(session, SKILL_Q, sid, values, create=create,
                expected_revision=body.get('revision'), request_id=body.get('request_id'),
                by=str(body.get('by') or '지식 관리자'))
    finally:
        driver.close()


@app.put("/api/kg/skills/{sid}")
async def kg_update_skill(sid: str, body: dict):
    try:
        values = kgadmin.validate_skill(body)
        out = await asyncio.get_running_loop().run_in_executor(None, lambda: _author_skill(sid, values, body))
    except KeyError:
        raise HTTPException(404, 'no such skill')
    except skill_graph.Conflict as error:
        raise HTTPException(409, str(error))
    except ValueError as error:
        raise HTTPException(400, str(error))
    _audit('-', str(body.get('by') or '지식 관리자'), 'SKILL_EDITED', {'skill': sid, 'name': values['name']})
    return out


@app.post("/api/kg/skills")
async def kg_create_skill(body: dict):
    try:
        values = kgadmin.validate_skill(body, create=True)
        sid = kgadmin.skill_id(values['sopId'])
        out = await asyncio.get_running_loop().run_in_executor(None, lambda: _author_skill(sid, values, body, create=True))
    except skill_graph.Conflict as error:
        raise HTTPException(409, str(error))
    except ValueError as error:
        raise HTTPException(400, str(error))
    _audit('-', str(body.get('by') or '지식 관리자'), 'SKILL_CREATED', {'skill': sid, 'sop': values['sopId']})
    return out


# Document originals are durable; source review and graph commit have distinct states.
from pathlib import Path
from .manual_sources import ManualSources
from . import manual_api
manual_api.register(app,
    archive_factory=lambda: ManualSources(Path(os.getenv("PROCESS_STATE_PATH", "/data/process.sqlite3")).with_name("manuals.sqlite3")),
    driver_factory=_kg, tenant=os.getenv("TENANT_ID", "hyd"), audit=_audit,
    runtime_factory=instance_mode.current)


# ---------------------------------------------------------------- 인제스천 (회의 2번 · 6번): 회사 DB 의 DDL → System · InputData, 되돌리기, 규칙 → SQL
@app.post("/api/kg/ddl/preview")
async def kg_ddl_preview(body: dict):
    """body = {filename, data(base64) | text}. Parses CREATE TABLE statements and proposes the ontology plan
    (System per source system, InputData per selected column with provenance). Nothing is written."""
    name = str(body.get("filename") or "schema.sql")
    loop_ = asyncio.get_running_loop()
    try:
        text = body.get("text") if isinstance(body.get("text"), str) and body.get("text") else await loop_.run_in_executor(None, lambda: _extract_text(name, body.get("data", "")))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"파일을 읽을 수 없다: {e}")
    try:
        tables = ingest.parse_ddl(text)
        plan = ingest.plan(tables, filename=name, batch=ingest.new_batch_id("ddl"),
                           selection=body.get("selection"), systems=body.get("systems"),
                           datasource=body.get("datasource", "hyd-enterprise"), catalog=body.get("catalog", "postgres"))
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    if not tables:
        raise HTTPException(400, "CREATE TABLE 문을 찾지 못했다")
    systems = await loop_.run_in_executor(None, lambda: _q("MATCH (s:System) RETURN s.id AS id, s.name AS name, s.zone AS zone ORDER BY s.id"))
    plan["existingSystems"] = systems
    plan["chars"] = len(text)
    return plan


@app.post("/api/kg/ddl/sync")
async def kg_ddl_sync():
    """A087: poll the live business catalog now; physical inputs whose column vanished or changed type are marked."""
    try:
        return await asyncio.get_running_loop().run_in_executor(None, _ddl_sync_once)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"원천 카탈로그 동기화 실패: {str(e)[:200]}")


@app.post("/api/kg/scm/sync")
async def kg_scm_sync():
    """A089: apply the business database's supplier master data to the graph now."""
    try:
        return await asyncio.get_running_loop().run_in_executor(None, _scm_sync_once)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"SCM 원천 동기화 실패: {str(e)[:200]}")


@app.post("/api/kg/ddl/commit")
async def kg_ddl_commit(body: dict):
    """body = the preview plan (possibly edited: selection/systems) + {by}. Applies the ownership journal and nodes in one transaction."""
    if not body.get("inputs") and not body.get("systems"):
        raise HTTPException(400, "적재할 시스템 · 입력 데이터가 없다")
    by = str(body.get("by") or "지식 관리자")
    plan = {"batch": body.get("batch") or ingest.new_batch_id("ddl"), "filename": body.get("filename", "schema.sql"),
            "systems": body.get("systems") or [], "inputs": body.get("inputs") or []}

    try:
        ingest.validate_plan(plan)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(400, str(e))

    def run():
        with _kg() as drv, drv.session() as session:
            return graph_ingest.commit(session, plan)
    try:
        out = await asyncio.get_running_loop().run_in_executor(None, run)
    except graph_ingest.Conflict as e:
        raise HTTPException(409, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"온톨로지 적재 실패: {str(e)[:200]}")
    out.update(by=by, t=now_iso(), kind="ddl")
    try:   # A087: a re-ingested binding reports its live state at once, not after the next poll
        out["sourceSync"] = await asyncio.get_running_loop().run_in_executor(None, _ddl_sync_once)
    except Exception as e:  # noqa: BLE001
        out["sourceSync"] = {"error": str(e)[:200]}
    # Ingestion history is the durable graph journal read by /api/kg/ingests.
    # The old manual-upload list no longer exists; do not fail after commit.
    _audit("-", by, "DDL_INGESTED", {k: out[k] for k in ("batch", "filename", "systems", "inputs")})
    return out


@app.get("/api/kg/ingests")
async def kg_ingests():
    """Active batch claims by label; shared nodes may be retained or restored on clear."""
    return await asyncio.get_running_loop().run_in_executor(None, lambda: _q(graph_ingest.BATCHES_Q))


@app.delete("/api/kg/ingests/{batch}")
async def kg_ingest_clear(batch: str, by: str = "지식 관리자"):
    """Release one batch's claims and restore the latest remaining revision atomically."""
    def run():
        with _kg() as drv, drv.session() as session:
            return graph_ingest.clear(session, batch)
    try:
        out = await asyncio.get_running_loop().run_in_executor(None, run)
    except graph_ingest.Conflict as e:
        raise HTTPException(409, str(e))
    except KeyError:
        raise HTTPException(404, "배치를 찾을 수 없습니다")
    except Exception as e:
        raise HTTPException(502, f"되돌리기 실패: {str(e)[:200]}")
    _audit("-", by, "INGEST_CLEARED", out)
    return out


@app.post("/api/kg/rules/sql")
async def kg_rule_sql(body: dict):
    """회의 6번: a rule's threshold tests → the SQL that checks them against the ingested tables.
    body = {rule: 'rule:…'} (TESTS read from the ontology) or {tests: [{variable, operator, value}]}."""
    loop_ = asyncio.get_running_loop()
    tests = body.get("tests")
    if not tests and body.get("rule"):
        tests = await loop_.run_in_executor(None, lambda: _q(
            "MATCH (r:Rule {id: $id})-[t:TESTS]->(i:InputData) RETURN i.variable AS variable, t.operator AS operator, t.value AS value", id=body["rule"]))
    if not tests:
        raise HTTPException(400, "tests 또는 rule 이 필요하다")
    inputs = await loop_.run_in_executor(None, lambda: _q(
        "MATCH (i:InputData) WHERE i.table IS NOT NULL RETURN i.variable AS variable, i.datasource AS datasource, "
        "i.catalog AS catalog, i.schema AS schema, i.table AS table, i.column AS column, i.assetColumn AS assetColumn, i.derive AS derive"))
    mapped = {}
    used = {t.get("variable") for t in tests}
    for item in inputs:
        if item["variable"] not in used:
            continue
        if item["variable"] in mapped and mapped[item["variable"]] != item:
            raise HTTPException(409, "같은 변수가 여러 원천을 가리킵니다. 원천 정보를 다시 적재하세요")
        mapped[item["variable"]] = item
    try:
        return ingest.tests_to_sql(tests, mapped)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(400, str(e))


@app.get('/api/kg/ranking-policy/{rule}')
async def kg_ranking_policy(rule: str):
    def run():
        with _kg() as driver, driver.session() as session:
            return ranking_policy.read(session, rule)
    try:
        return await asyncio.get_running_loop().run_in_executor(None, run)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except skill_graph.Conflict as exc:
        raise HTTPException(409, str(exc))


@app.get('/api/kg/bsc/conditions')
async def kg_bsc_conditions():
    def run():
        with _kg() as driver, driver.session() as session:
            return bsc_conditions.read(session)
    return await asyncio.get_running_loop().run_in_executor(None, run)


@app.put('/api/kg/bsc/conditions/{edge}')
async def kg_bsc_condition_write(edge: str, body: dict):
    def run():
        with _kg() as driver, driver.session() as session:
            return bsc_conditions.write(session, edge, body)
    try:
        return await asyncio.get_running_loop().run_in_executor(None, run)
    except skill_graph.Conflict as exc:
        raise HTTPException(409, str(exc))
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc))


@app.put('/api/kg/ranking-policy/{rule}')
async def kg_ranking_policy_write(rule: str, body: dict):
    def run():
        with _kg() as driver, driver.session() as session:
            return ranking_policy.write(session, rule, body)
    try:
        return await asyncio.get_running_loop().run_in_executor(None, run)
    except skill_graph.Conflict as exc:
        raise HTTPException(409, str(exc))
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc))


# ---------------------------------------------------------------- HITL: one human decision for an equipment anomaly
class HitlDecideReq(BaseModel):
    decision: str
    option: str
    by: str = "승인자"
    role: str
    reason: str = ""
    fan_pct: float | None = None
    load_pct: float | None = None
    review_id: str | None = None


def _commands_of(opt: dict, req: HitlDecideReq) -> list[dict]:
    """The chosen SOP skill's PLC commands as action.cmd items. A person may adjust fan / load inside the ontology range."""
    out = []
    for a in opt.get("actions") or []:
        if a.get("kind") != "command":
            continue
        item = {"code": a["code"]}
        if a.get("param"):
            v = a.get("value")
            if a["param"] == "fan_pct" and req.fan_pct is not None:
                v = req.fan_pct
            if a["param"] == "load_pct" and req.load_pct is not None:
                v = req.load_pct
            item[a["param"]] = v
        out.append(item)
    return out


@app.post('/api/incidents/{inc_id}/decision-preview')
async def legacy_decision_preview(inc_id: str, req: instance_mode.ReviewReq):
    await _require_legacy_incident(inc_id)
    d = book.get(req.decision)
    if not d or (d.get('origin') or {}).get('incident') != inc_id:
        raise HTTPException(404,'no such incident decision')
    await _require_legacy_decision(d)
    try:
        return await asyncio.get_running_loop().run_in_executor(None,lambda:
            _review_service().create(req.decision,req.option,req.parameters,{'kind':'legacy','incident':inc_id}))
    except ValueError as exc:
        raise HTTPException(409,str(exc))


@app.post("/api/incidents/{inc_id}/decide")
async def hitl_decide(inc_id: str, req: HitlDecideReq):
    """The operator picks one ranked action card (= one SOP skill of the failure mode). Its PLC commands go out through the
    incident (action.cmd -> gateway -> PLC); a card without commands closes the incident as 'no immediate command'. Its system
    transactions (CMMS work order, ERP purchase request) run in the enterprise systems. The choice is written back to the
    ontology as a DecisionCase and becomes a precedent for the next decision of the same failure mode."""
    inc = incidents.get(inc_id)
    d = book.get(req.decision)
    if not inc or not d:
        raise HTTPException(404, "no such incident or decision")
    await _require_legacy_incident(inc_id)
    await _require_legacy_decision(d)
    if inc.state != "AWAITING_APPROVAL":
        raise HTTPException(409, f"incident is {inc.state}")
    if (d.get("origin") or {}).get("incident") != inc_id or d.get("asset") != inc.asset:
        raise HTTPException(400, "decision does not belong to this incident")
    opt = next((o for o in d.get("options", []) if o["id"] == req.option), None)
    if opt is None:
        raise HTTPException(400, "unknown option")
    try:
        scope = {'kind':'legacy','incident':inc_id}
        candidate = (_review_service().snapshot(req.review_id,req.decision,req.option,scope)
                     if req.review_id else copy.deepcopy(d))
        opt = next(o for o in candidate['options'] if o['id']==req.option)
        commands = _commands_of(opt, req)
        plan = declib.approve(candidate, req.option, req.by, req.role, req.reason)
        if commands:                          # validate the command before consuming the human decision
            machine._validate_actions(inc, commands)
        from .approval_hooks import require_reviewed_commands
        require_reviewed_commands(opt, commands)
        await asyncio.get_running_loop().run_in_executor(None, _check_current_approval, candidate, req.option, req.role)
        # The read yields to other requests; check whether another choice won.
        if inc.state != 'AWAITING_APPROVAL':
            raise ValueError(f'incident is {inc.state}')
        candidate = (_review_service().snapshot(req.review_id,req.decision,req.option,scope)
                     if req.review_id else copy.deepcopy(d))
        plan = declib.approve(candidate, req.option, req.by, req.role, req.reason)
    except PermissionError as e:
        _audit(inc.asset, req.by, "DECISION_DENIED", {"decision": d["id"], "option": req.option, "role": req.role, "reason": str(e)}, incident=inc_id)
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    before = copy.deepcopy(d)
    d.update(candidate)
    try:
        work_orders.prepare(_work_order_context(), d, work_orders.request_for_option(opt), allow_before_recovery=True)
    except Exception as e:
        d.clear()
        d.update(before)
        raise HTTPException(400, str(e))
    _audit(inc.asset, req.by, "DECISION_APPROVED", {"decision": d["id"], "option": req.option, "sop": opt.get("sopId"), "role": req.role,
                                                     "override": d["override"], "reason": req.reason, "via": "HITL 조치 카드 선택"}, incident=inc_id)
    cmd = None
    try:
        if commands:
            cmd = machine.on_approve(inc, req.by, commands, now(), Fx(inc), time_scale=TIME_SCALE)
            for item in plan.get('ot', []):
                d['executions'].append({'skill':item['skill'], 'code':item.get('code'),
                    'status':'VIA_HITL', 'system':item.get('system'), 't':now_iso(),
                    'detail':f"PLC 명령 {item.get('code')}={item.get('value')} — Incident의 ACK/재관측 결과를 확인하세요"})
        else:
            inc.approved_by = req.by
    except ValueError as e:
        raise HTTPException(400, str(e))
    _after(inc)
    loop_ = asyncio.get_running_loop()
    results = [await loop_.run_in_executor(None, exec_skill, d, item)
               for item in plan["enterprise"] if item.get('code') != 'WO_CREATE']
    from .approval_hooks import record_execution
    for result in results:
        record_execution(d, result)
    if not commands and all(r.get('ok') for r in results):
        results.append(await loop_.run_in_executor(None, _complete_legacy_work_order, inc))
    persist()
    for r in results:
        _audit(inc.asset, "process", "SKILL_EXECUTED" if r["ok"] else "SKILL_FAILED",
               {"decision": d["id"], "skill": r["skill"], "code": r.get("code"), "system": r["system"], "ref": r.get("ref"),
                "detail": r.get("detail") or r.get("error")}, incident=inc_id)
    loop_.run_in_executor(None, record_decision, d)
    return {"incident": inc.to_dict() | {"card": None}, "decision": {"id": d["id"], "state": d["state"], "executions": d["executions"]}, "cmd": cmd}
