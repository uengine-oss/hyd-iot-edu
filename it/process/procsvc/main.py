"""process (L9): 처리 건 엔진. 경보 원천 접수 → 처리 건(에이전트 · 사람 · 시스템 단계) → 사람 승인 → action.cmd → ACK → 재관측 → 작업지시 → 닫힘.

Only this service may write action.cmd (the agent has no command authority). 사람 승인은 POST /api/todolist/{id}/select 하나다.
시한은 메모리 타이머가 아니라 작업 행의 마감(due_date)이다 — ACK 마감 · 재관측 창 · 경계 타이머 모두 폴링이 판정한다(instances).
재관측 판정은 사건의 회복 기준 태그 최신값을 TimescaleDB(tag_1s)에서 읽는다.
"""
import asyncio
import copy
import json
from datetime import datetime, timezone
import logging
import os
import threading
import urllib.error
import urllib.request
from contextlib import nullcontext

import psycopg
from fastapi import HTTPException
from pydantic import BaseModel

from hydcommon import graphdb, schemas, topics
from hydcommon.kafka import consumer as make_consumer, producer as make_producer
from hydcommon.metrics import Registry
from hydcommon.service import make_app
from hydcommon.timeutil import now, now_iso
from . import decisions as declib, definition, ingest, graph_ingest, instance_mode, kgadmin, machine, current_approval, engine, reobs_series
from .store import Store
from . import skill_graph
from .inbox import actor_or_400
from .knowledge_projection import KnowledgeReconciler
from .case_projection import CaseProjector
from .source_inbox import PgSourceInbox, kafka_record, source_record
from .source_delivery import SourceDelivery, SourcePending

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("process")
TIME_SCALE = float(os.getenv("TIME_SCALE", "20"))
PG_DSN = os.getenv("PG_DSN", "postgresql://hyd:hyd@timescaledb:5432/hyd")
ENTERPRISE_URL = os.getenv("ENTERPRISE_URL", "http://enterprise-sim:8095")
KAFKA_SEND_TIMEOUT_S = 10.0          # 승인 원장 · 명령 송신 확인을 기다리는 한도

reg = Registry()
c_inc = reg.counter("process_incidents_total", "incidents by terminal state")
g_open = reg.gauge("process_open_incidents", "incidents not in a terminal state")
state: dict = {}                     # 처리 오류 · 시작 표시(/healthz 가 읽는 칸만 — _health_state)
incidents: dict[str, machine.Incident] = {}
book: dict[str, dict] = {}          # action-card decisions (L9, ontology v2)
audit_log: list[dict] = []
SOURCE_BATCH_MAX = int(os.getenv('SOURCE_BATCH_MAX', '50'))   # A080: deliveries received per DB connection and per offset commit (~6 s at 20x)
plant_status: dict[str, dict] = {}   # latest plant.status per asset (PLC mode / state for the agent's DMN facts)
producer = None
consumer_client = None
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


def _send(topic: str, key, value) -> "asyncio.Future":
    """Kafka 송신 하나를 이벤트 루프에 맡긴다(어느 스레드에서든). 돌려준 future 는 브로커가 받았다고 답할 때 끝난다."""
    if producer is None or loop is None or loop.is_closed():
        raise RuntimeError('Kafka 송신기가 아직 준비되지 않았습니다')

    async def delivered():
        return await (await producer.send(topic, key=key, value=value))
    return asyncio.run_coroutine_threadsafe(delivered(), loop)


def _send_logged(topic: str, key, value, what: str) -> None:
    """기다리지 않는 송신(감사 기록). 실패는 조용히 버리지 않고 로그에 남긴다(A-07)."""
    def done(fut):
        if fut.cancelled():
            log.error('%s not sent to %s: cancelled', what, topic)
        elif fut.exception() is not None:
            log.error('%s not sent to %s: %s', what, topic, fut.exception())
    try:
        _send(topic, key, value).add_done_callback(done)
    except RuntimeError as exc:
        log.error('%s not sent to %s: %s', what, topic, exc)


def _send_and_wait(topic: str, key, value) -> None:
    """브로커가 받았다고 답할 때까지 기다린다 — 승인 원장 · 명령. 이벤트 루프 스레드에서는 부르지 않는다(스스로를 기다리게 됨)."""
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is not None and running is loop:
        raise RuntimeError('명령 송신 확인은 이벤트 루프 밖에서 기다려야 합니다')
    _send(topic, key, value).result(timeout=KAFKA_SEND_TIMEOUT_S)


class Fx(machine.Effects):
    """Effects for one incident: keep an audit copy and publish it to Kafka (fire-and-forget, failures logged)."""

    def __init__(self, inc: machine.Incident):
        self.inc = inc

    def emit_audit(self, evt: dict) -> None:
        audit_log.insert(0, evt)
        del audit_log[AUDIT_PAGE_MAX:]
        _send_logged(topics.K_AUDIT, topics.asset_key(self.inc.asset), evt, f"audit {evt.get('event')}")


class TagReadError(RuntimeError):
    """시계열(tag_1s)을 읽지 못했다 — 「값이 아직 없다」(None)와 다르다. 판정하는 쪽이 까닭을 판정 기록에 남긴다(P5-05)."""


def latest_tag(asset: str, tag: str) -> float | None:
    """One tag's latest 1 s value (the incident's recovery tag: TS1 · PS1 · VS1) from TimescaleDB. None = no row yet;
    a read failure raises TagReadError with its reason (never the same None)."""
    try:
        with psycopg.connect(PG_DSN, autocommit=True, connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("SELECT value FROM tag_1s WHERE asset=%s AND name=%s ORDER BY time DESC LIMIT 1", (asset, tag))
            row = cur.fetchone()
    except psycopg.Error as e:
        raise TagReadError(f"시계열(tag_1s)에서 {asset} {tag} 최신값을 읽지 못했습니다: {type(e).__name__}: {str(e).strip()[:200]}") from e
    return None if row is None or row[0] is None else float(row[0])


def tag_series(asset: str, tag: str, since: str, until: str | None = None) -> list[tuple[str, float]]:
    """A161-G3: the 1 s rows of one tag from `since` (ISO) to `until` (default now), oldest first, at most reobs_series.MAX_ROWS
    (the newest ones when the window is longer). A read failure raises — window_series records it as the window's error."""
    with psycopg.connect(PG_DSN, autocommit=True, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT time, value FROM tag_1s WHERE asset=%s AND name=%s AND time >= %s::timestamptz"
                    " AND (%s::timestamptz IS NULL OR time <= %s::timestamptz) ORDER BY time DESC LIMIT %s",
                    (asset, tag, since, until, until, reobs_series.MAX_ROWS))
        rows = cur.fetchall()
    return [(t.isoformat() if hasattr(t, "isoformat") else str(t), float(v)) for t, v in reversed(rows) if v is not None]


def window_series(inc: machine.Incident, after: str, since: str | None = None) -> dict | None:
    """A161-G3: the Incident's recovery tag over its re-observation window (since: the window start; default the last
    RE_OBSERVING entry), sampled for the Incident record. A window that cannot be read is recorded with its reason
    (reobs_series.unavailable) instead of disappearing — the verdict itself never waits for the trend."""
    if inc.recovery is None:
        return None
    tag, op, limit = inc.recovery
    until = now_iso()
    since = since or reobs_series.window_start(inc.history)
    where = dict(tag=tag, op=op, limit=limit, since=since, until=until, after=after, extensions=inc.reobs_extensions)
    if not since:
        return reobs_series.unavailable("재관측 시작 시각(RE_OBSERVING 기록)을 찾지 못해 창의 값을 읽지 않았습니다", **where)
    try:
        rows = tag_series(inc.asset, tag, since, until)
    except Exception as e:  # noqa: BLE001 — TimescaleDB down: said on the record, the verdict goes on
        log.warning("re-observation series %s %s failed: %s", inc.id, tag, e)
        return reobs_series.unavailable(f"시계열(tag_1s)을 읽지 못했습니다: {type(e).__name__}: {str(e)[:200]}", **where)
    return reobs_series.build(rows, **where)


def _after(inc: machine.Incident, *, advance: bool = True):
    """Runs on the event loop or on a worker thread (instance-mode hooks), so it schedules through the global loop.
    advance=False: 사건만 저장하고 처리 건 진행은 예약하지 않는다 — 지금 그 처리 건의 단계 안에서 실패를 올릴 때(그 단계의 실패 기록이
    먼저 남고, 다음 폴링이 사건 상태로 진행한다. 예약하면 다른 스레드의 진행과 실패 기록의 앞뒤가 그때그때 갈린다)"""
    persist()                      # 저장이 사건 그래프 반영도 깨운다(_wake_case_projection)
    if inc.state in definition.TERMINAL:
        c_inc.inc(state=inc.state)
    g_open.set(sum(1 for i in list(incidents.values()) if i.state not in definition.TERMINAL))
    if advance:
        instance_mode.on_incident_update(inc)


def _wake_case_projection():
    if loop is not None and case_projection_event is not None and not loop.is_closed():
        loop.call_soon_threadsafe(case_projection_event.set)


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


async def _ddl_sync_loop():
    interval = float(os.getenv("DDL_SYNC_INTERVAL_S", "60"))
    while True:
        for name, once in (("DDL source", _ddl_sync_once), ("SCM source", _scm_sync_once)):
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


async def receive_records(recs, commit=None) -> None:
    """Kafka 에서 받은 원천 레코드 한 묶음(한 파티션, 받은 차례)을 원천 접수에 넣는다 — 경보(RAISE)의 흐름 정책 고르기 → 한 DB 연결의 접수
    (source_inbox.receive_many) → 설비 최신 상태(plant_status) 갱신. consume() 과 테스트가 이 함수 하나를 부른다(G5b-03 · 06).
    A080: 접수는 레코드마다 커밋되고, 접수된 앞부분마다 commit(마지막으로 접수한 레코드)를 부른다(offset 은 부르는 쪽 — Kafka).
    접수에 실패한 레코드부터는 1초 뒤 다시(빠진 사건 뒤로는 commit 하지 않는다). 돌아오면 묶음 전체가 접수된 것이다."""
    items = []
    for rec in recs:
        record = kafka_record(rec)
        policy = await _alert_policy_retrying(record['payload'].get('pattern')) if record['kind'] == 'RAISE' else None
        items.append((rec, record, policy))
    start = 0
    while start < len(items):
        rows, error, states = await _receive_retrying([(r, p) for _, r, p in items[start:]])
        done = start + len(rows)
        if states:
            plant_status.update(states)
        if done > start and commit is not None:
            await commit(items[done - 1][0])
        if error is None:
            state.pop('source_receive_error', None)
            return
        failed = items[done][0]
        state['source_receive_error'] = str(error)
        log.error('source receipt failed: %s/%s/%s: %s', failed.topic, failed.partition, failed.offset, error)
        start = done
        await asyncio.sleep(1)


#: process 가 원천 접수로 받는 Kafka 토픽 — 설비 상태(명령 응답 ACK) · 경보(RAISE · CLEAR) · 감사(명령 관문 거절 REJECT, G3b-9:
#: 받지 않으면 관문이 거절한 명령을 30초 응답 없음으로만 알았다). 어떤 레코드가 원천 사건인지는 source_inbox.source_record 가 정한다.
SOURCE_TOPICS = (topics.K_STATUS, topics.K_ALERTS, topics.K_AUDIT)


async def consume():
    global producer, consumer_client
    producer = await make_producer()
    cons = consumer_client = await make_consumer(list(SOURCE_TOPICS), group="process", from_latest=False,
                                                 auto_commit=False, raw_values=True)
    state["consumer_started"] = True
    log.info("consuming plant.status (ACK) · alerts (RAISE · CLEAR) · audit (cmd-gateway REJECT) into the durable source receipts")
    from aiokafka import TopicPartition

    async def commit(last):
        try:
            await cons.commit({TopicPartition(last.topic, last.partition): last.offset + 1})
        except Exception:
            # Rebalance/network failure may redeliver an already committed receipt. Every later offset also passes receive() first.
            log.exception('durable source will tolerate offset redelivery: %s/%s/%s', last.topic, last.partition, last.offset)
    while True:
        batches = await cons.getmany(timeout_ms=250, max_records=SOURCE_BATCH_MAX)
        if not batches:
            continue
        state["last_record_at"] = now_iso()
        for _tp, recs in batches.items():
            await receive_records(recs, commit)


def _apply_source_event(receipt):
    value=receipt['payload'];rt=instance_mode.current()
    if receipt['kind']=='CLEAR':
        inc=next((i for i in list(incidents.values()) if i.alert_id==value['alertId']),None)
    else:
        inc=next((i for i in list(incidents.values()) if i.cmd_id==value['cmdId']),None)
        if inc is None:
            # process 는 사건에 명령 id 를 먼저 저장한 뒤에 명령을 보낸다(_approve_incident) — 어느 사건에도 없는 명령 id 의 응답은 process 가
            # 낸 명령이 아니다(FUXA 수동 조작 · 다음 명령에 밀린 옛 응답). 기다릴 짝이 없으므로 대기로 두지 않고 끝낸다(P2-01: 5초마다 영원히 다시 처리)
            return {'cmdId':value['cmdId'],'asset':value.get('asset'),'disposition':'process 가 낸 명령의 응답이 아님 — 할 일 없음'}
    if inc is None:raise SourcePending('연결할 원천 사건이 아직 없습니다')
    if value['asset']!=inc.asset or (receipt['kind']=='CLEAR' and 'pattern' in value and value['pattern']!=inc.pattern):
        raise ValueError('원천 해제 · 명령 응답의 설비 또는 경보 패턴이 사건과 다릅니다')
    inst=rt.instance_of_incident(inc.id)
    # Use the same instance lock as approval/task transitions. Source receipt
    # fencing alone cannot prevent a previously running handler from finishing.
    with rt._transition(inst['proc_inst_id']) if inst else nullcontext():
        if receipt['kind']=='CLEAR' and not inc.cleared:
            machine.on_alert(inc,value,Fx(inc),trip=machine.active_trip(inc.asset,list(incidents.values()),since=inc.created))
        elif receipt['kind']=='ACK':
            machine.on_status(inc,value,now(),Fx(inc))
        elif receipt['kind']=='REJECT':      # G3b-9: 명령 관문이 이 명령을 설비로 넘기지 않음 — 30초 응답 없음을 기다리지 않고 그 까닭으로
            machine.on_gateway_rejected(inc,value['cmdId'],value.get('check'),value.get('reason_text'),Fx(inc))
        persist()
        rt.on_incident_update(inc.state,inc.id,inc.cleared)
        return {'incident':inc.id,'state':inc.state,'cleared':inc.cleared,'cmdId':inc.cmd_id,
                'ack':inc.ack,'disposition':'correlated source observed; recovery is not inferred'}


async def source_loop():
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


HEALTH_ERRORS = ('source_receive_error', 'source_handler_error', 'source_policy_error', 'startup_db_error')


def _health_state():
    """지금 처리할 수 있는가 — DB 를 새로 열지 않고 메모리에서 잰 것만(P5-16: 시작 때 한 번 정한 값은 싣지 않는다).
    ok = Kafka 소비를 시작했고 · 멈춘 반복이 없고 · 원천 접수/처리 오류가 없고 · 처리 엔진 폴링이 돈다(runtime — DB 상태는 여기서 드러난다).
    kafka.last_record_at = 마지막으로 받은 원천 레코드 시각(설비 상태가 1초마다 오므로 오래 멈춰 있으면 브로커 · 설비 쪽을 본다).
    그래프 반영 대기는 GET /api/graph-projections(DB 를 읽는다)."""
    runtime = instance_mode.runtime_readiness()
    errors = {k: state[k] for k in HEALTH_ERRORS if state.get(k)}
    stopped = dict(state.get("stopped_loops") or {})
    ready = state.get("consumer_started") and not errors and not stopped and runtime['ready']
    return {"ok": bool(ready), "runtime": runtime, "errors": errors, "stopped_loops": stopped,
            "kafka": {"consumer_started": bool(state.get("consumer_started")), "last_record_at": state.get("last_record_at")},
            "incidents": len(incidents)}


app = make_app("process — 처리 건 엔진(원천 접수 · 사람 승인 · 설비 명령 · ACK · 재관측 · 작업지시)", reg, _health_state)
# /api/instances · /api/todolist · … — 경보로 처리 건을 여는 길은 원천 접수 하나(_admit_alert, 아래)
instance_mode.mount(app, admit_alert=lambda alert: _admit_alert(alert))
from . import agents_api
agents_api.mount(app)                       # U2: /api/agents · /api/skills · /api/agent-bindings (instance mode)
from . import inbox_api
inbox_api.mount(app)                        # U5: /api/inbox/* (나 · 내 작업함 · 알림 · 업무분장 읽기)
from . import agent_authoring_api
agent_authoring_api.mount(app)              # B1: 에이전트 · 스킬 쓰기 · 단계/역할 배정 · POST /api/agents/reset

def _approve_incident(inc: machine.Incident, by: str, commands: list[dict], at: datetime | None = None) -> dict:
    """승인한 명령을 낸다: 사건에 CMD_ISSUED 를 먼저 저장하고, 승인 원장 송신이 확인된 뒤 명령을 보낸다(A148 · A-07). 둘 중 하나라도
    브로커가 받지 않으면 다시 보내지 않고 사건을 사람 검토(CMD_SEND_FAILED)로 넘긴 뒤 실패를 알린다 — 조용히 ACK 시간 초과로 보이지 않게."""
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
    option = next(o for o in d['options'] if o['id'] == d['chosen'])
    require_reviewed_commands(option, commands)
    at = at or now()
    fx = Fx(inc)
    cmd = machine.on_approve(inc, by, option, commands, at, fx)
    persist()                      # durable CMD_ISSUED before any external side effect
    ledger = {"t": now_iso(), "incident": inc.id, "asset": inc.asset, "actor": "process",
              "event": schemas.CMD_APPROVAL_LEDGER_EVENT, "detail": schemas.approval_ledger_record(cmd)}
    try:
        _send_and_wait(topics.K_AUDIT, topics.asset_key(inc.asset), ledger)
        audit_log.insert(0, ledger)
        _send_and_wait(topics.K_CMD, topics.asset_key(cmd["asset"]), cmd)
    except Exception as exc:  # noqa: BLE001 — 송신 실패는 사건 사유로 남기고 이 단계를 실패시킨다(재전송하지 않음)
        error = f"{type(exc).__name__}: {str(exc)[:300]}"
        machine.on_command_send_failed(inc, cmd["cmdId"], error, fx)
        _after(inc, advance=False)
        raise ValueError(f"설비 명령을 명령 통로에 싣지 못했습니다({error}) — 명령은 다시 보내지 않고 이 처리 건을 사람 검토(미달)로 넘깁니다") from exc
    machine.on_command_sent(inc, cmd["cmdId"], at, fx)
    _after(inc)
    return cmd


def _check_current_approval(d, option, role, consented_at=None):
    report = current_approval.check(d, option, role, *([consented_at] if consented_at else []))
    _audit(d.get('asset') or '-', 'process', 'APPROVAL_CURRENT_CHECK', report,
           incident=(d.get('origin') or {}).get('incident'))
    return current_approval.require(lambda *_: report, d, option, role)


def instance_context() -> instance_mode.ProcessContext:
    return instance_mode.ProcessContext(incidents=incidents, book=book, state=state, time_scale=TIME_SCALE, persist=persist, audit=_audit,
                                        cypher=_q, exec_skill=exec_skill, approve_incident=_approve_incident,
                                        get_loop=lambda: loop, check_approval=_check_current_approval, after_incident=_after,
                                        reviews=_review_service, approval_receipts=_approval_receipts,
                                        exec_compensation=_exec_compensation, latest_tag=latest_tag, tag_read_error=TagReadError,
                                        window_series=window_series)


class ServiceRefused(ValueError):
    """바깥 서비스(업무 시스템 · 설비 시뮬레이터)가 요청을 거절했거나 닿지 않았다. 메시지 = 사람이 읽는 사유(그 서비스가 준 detail 그대로 포함),
    status = 그 서비스의 HTTP 상태(닿지 않았으면 None)."""
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _service_json(base: str, label: str, path: str, body: dict | None = None, *, headers: dict | None = None, timeout: float = 10) -> dict:
    """바깥 서비스 HTTP 한 번(body 가 있으면 POST, 없으면 GET) → JSON. 거절 · 닿지 않음은 ServiceRefused — FastAPI 의 detail(거절 까닭)을
    버리지 않는다(P5-04: 「HTTP Error 400: Bad Request」만 남아 학생 · 강사가 정비 창 · 공급사 거절 까닭을 못 봤다). 업무 시스템 · 설비
    시뮬레이터를 부르는 길은 모두 이것 하나다."""
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            detail = json.loads(raw).get("detail", raw)
        except (ValueError, AttributeError):
            detail = raw
        if not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
        raise ServiceRefused(f"{label}이(가) 요청을 거절했습니다(HTTP {e.code}, {path.split('?')[0]}): {detail[:300]}", e.code) from None
    except OSError as e:
        raise ServiceRefused(f"{label}에 닿지 못했습니다({path.split('?')[0]}): {type(e).__name__}: {str(e)[:200]}") from None


def _enterprise(path: str, body: dict | None = None) -> dict:
    """업무 시스템(enterprise-sim) — 쓰기는 process 만 아는 실행 호출 값을 싣는다(하-05)."""
    return _service_json(ENTERPRISE_URL, "업무 시스템(enterprise-sim)", path, body,
                         headers=instance_mode.caller_headers() if body is not None else None)


def _exec_compensation(body: dict) -> dict:
    """POST one compensation skill (A072) to the enterprise systems; the enterprise keeps it idempotent per decision/skill/ref.
    업무 시스템이 역거래를 거절하면(4xx — 다시 보내도 같은 답) CompensationRefused(그 효과는 사람 확인으로 정리 — P4-11), 연결 실패 · 5xx 는
    ServiceRefused 그대로(다시 시도할 수 있는 실패)."""
    from .effect_compensation import CompensationRefused
    try:
        return _enterprise("/api/exec", body)
    except ServiceRefused as e:
        if e.status is not None and 400 <= e.status < 500:
            raise CompensationRefused(str(e)) from None
        raise


def _approval_receipts(decision_id):
    from urllib.parse import urlencode
    return _enterprise('/api/transactions?' + urlencode({'decision': decision_id}))


def _review_service():
    from .decision_reviews import DecisionReviews
    if store is None:
        raise ValueError('검토본 저장소가 준비되지 않았습니다')
    return DecisionReviews(store,book,incidents,current_approval.preview)


_tasks: dict[str, asyncio.Task] = {}      # 이름 → 백그라운드 반복(끄기가 모두 멈춘다)
_stopping = False


def background(coro, name: str) -> asyncio.Task:
    """백그라운드 반복 하나를 띄운다. 끄기가 아닌데 끝나면(예외든 그냥 끝이든) /healthz 가 그 이름과 까닭으로 503 을 낸다 — 아무 일도 안 하면서
    건강해 보이지 않게(원천 처리 · Kafka 소비뿐 아니라 그래프 반영 · 원천 카탈로그 동기화 반복도)."""
    task = asyncio.create_task(coro, name=name)
    _tasks[name] = task
    task.add_done_callback(_watch)
    return task


def _watch(task: asyncio.Task):
    if _tasks.get(task.get_name()) is task:
        del _tasks[task.get_name()]       # 끝난 반복은 끄기가 기다릴 일이 아니다(끝난 까닭은 아래 stopped_loops 에 남는다)
    if _stopping:
        return
    error = task.exception() if not task.cancelled() else None
    reason = f"{type(error).__name__}: {str(error)[:300]}" if error else ("취소됨" if task.cancelled() else "반복이 끝남")
    state.setdefault("stopped_loops", {})[task.get_name()] = reason
    log.error("background loop %s ended: %s", task.get_name(), reason)


@app.on_event("shutdown")
async def _shutdown():
    """끄기(P5-17): 반복을 멈추고, Kafka 소비 그룹을 떠나고(다시 켤 때 파티션을 바로 받게), 송신기가 쥔 감사 기록을 다 보낸 뒤 닫고,
    작업 스레드의 처리 건 갱신이 끝나기를 기다린 뒤 사건 저장소를 닫는다."""
    global _stopping, producer, consumer_client, _graph
    _stopping = True
    for task in list(_tasks.values()):
        task.cancel()
    await asyncio.gather(*_tasks.values(), return_exceptions=True)
    if consumer_client is not None:
        await consumer_client.stop()
        consumer_client = None
    if producer is not None:
        await producer.stop()          # aiokafka: 쌓인 송신을 다 보낸(flush) 뒤 닫는다
        producer = None
    await instance_mode.stop_loops()
    await drain_scheduled_updates()
    if _graph is not None:
        _graph.close()
        _graph = None                  # 다음 쓰임(같은 프로세스에서 다시 켬)이 닫힌 드라이버를 받지 않게 — _shared_graph 가 새로 잇는다
    if store is not None:
        store.db.close()


async def drain_scheduled_updates() -> None:
    """이 루프의 작업 스레드에 맡긴 처리 건 갱신(instance_mode._schedule — 사건이 바뀔 때마다)이 다 끝날 때까지 기다린다. 끄기 · 테스트의
    world 닫기가 사건 저장소를 닫기 전에 부른다 — 전에는 기다리지 않아 끄는 순간 돌던 갱신이 닫힌 저장소에 부딪히거나(FA2 검증 P5-17)
    테스트에서는 다음 world 의 준비 중에 앞 world 의 갱신이 돌았다(FA1 검증 §4-6). 기본 실행기를 닫으므로 그 뒤 새 갱신은 받지 않는다."""
    await asyncio.get_running_loop().shutdown_default_executor()


async def restore_and_build(ctx: instance_mode.ProcessContext, *, state_path: str | None = None, repo=None, clock=None):
    """process 한 번의 기동에서 백그라운드 반복을 뺀 전부 — `_startup`과 테스트가 이 함수 하나를 부른다(G5b-03).
      ① 실행 호출 값 확인(없으면 뜨지 않는다) ② 사건 저장 파일 복원(사건 · 판단 · 감사 — 메모리에 있던 앞 값은 버린다)
      ③ 처리 엔진 런타임 구성(DB 가 잠깐 멈춰 있으면 제한된 재시도, A151) ④ 원천 접수 · 원천 처리기 · 설비 최신 상태 · 사건 그래프 반영기 · 지식 정리기.
    ctx = instance_context()(테스트는 바깥 자리만 바꾼 사본 — 그래프 질의는 ctx.cypher 하나를 모두가 쓴다), state_path = 사건 저장 파일
    (기본 PROCESS_STATE_PATH), repo · clock = instance_mode.build 에 그대로. 이벤트 루프(main.loop) · Kafka 송신기는 부르는 쪽이 정한다.
    돌려줌 = 처리 엔진 런타임(instance_mode.current() 와 같은 것)."""
    global store, source_inbox, source_delivery, case_projector, knowledge_reconciler, _stopping
    _stopping = False                         # 새 기동은 끄는 중이 아니다(끈 뒤 같은 프로세스에서 다시 켜면 멈춘 반복을 다시 알린다)
    instance_mode.caller_headers()            # 하-04 · 하-05: process 만 아는 실행 호출 값이 없으면 뜨지 않는다(조용히 쓰기 실패로 돌지 않게)
    schemas.fingerprint_key()                 # G3b-30: 승인 장부 지문 키가 없으면 첫 승인에서가 아니라 켜질 때 멈춘다
    store = Store(state_path or os.getenv("PROCESS_STATE_PATH", "/data/process.sqlite3"))
    saved_incidents, saved_book, saved_audit = store.restore()
    incidents.clear()
    incidents.update(saved_incidents)
    book.clear()
    book.update(saved_book)
    audit_log[:] = saved_audit
    persist()
    rt = await instance_mode.retry_startup(lambda: instance_mode.build(ctx, repo=repo, clock=clock), 'instance runtime', state)
    rt.hooks.case_started = _link_injection     # C3: 수업 버튼의 설비 주입 → 그 주입이 연 처리 건 (누름 id 로 연결)
    source_inbox = PgSourceInbox(rt.repo, rt.tenant_id)
    states = await instance_mode.retry_startup(lambda: asyncio.to_thread(source_inbox.latest_states), 'plant status', state)
    plant_status.clear()
    plant_status.update(states)
    source_delivery = SourceDelivery(source_inbox, rt, _apply_source_event, owner=rt.consumer + '-source')
    case_projector = CaseProjector(store, ctx.cypher, _incident_projected)
    knowledge_reconciler = KnowledgeReconciler(store, ctx.cypher, os.getenv('TENANT_ID', 'hyd'), rt.repo)
    return rt


@app.on_event("startup")
async def _startup():
    global loop, case_projection_event, case_projection_task
    loop = asyncio.get_running_loop()
    ctx = instance_context()
    rt = await restore_and_build(ctx)
    instance_mode.start_loops(rt, ctx)
    background(source_loop(), 'source handler')
    case_projection_event = asyncio.Event()
    case_projection_event.set()
    case_projection_task = background(_case_projection_loop(), 'graph projection')
    background(_ddl_sync_loop(), 'source catalog sync')
    background(consume(), 'kafka consumer')


@app.get('/api/graph-projections')
async def graph_projection_status():
    """그래프 반영 대기 현황 한 곳(P5-07, RUNBOOK §6 이 가리킨다): 사건 · 판단(pending · items — 이 PC 의 사건 저장 파일),
    처리 건 실행(execution — 업무 DB 대기열, 충돌 수 · 가장 오래된 대기 포함), 반영 반복이 도는지, 지식 변경 확인."""
    if store is None:
        raise HTTPException(503, '사건 저장소가 준비되지 않았습니다')
    rt = _runtime_or_503()
    result = await asyncio.to_thread(store.case_projection_status)
    execution = await asyncio.to_thread(rt.repo.projection_backlog, rt.tenant_id)
    knowledge = await asyncio.to_thread(knowledge_reconciler.status) if knowledge_reconciler else None
    return result | {'execution': execution, 'knowledge': knowledge, 'definition_cleanup': rt.graph_cleanup_status(),
                     'worker_running': case_projection_task is not None and not case_projection_task.done()}


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


def _runtime_or_503():
    rt = instance_mode.current()
    if rt is None:
        raise HTTPException(503, instance_mode.instances.NOT_READY)
    return rt


@app.get('/api/alerts/policy')
async def alert_execution_policy(pattern: str = ''):
    """경보 패턴 → 그 패턴을 받는 배포 흐름과 회복 기준(agent 의 읽기 평가가 먼저 묻는다)."""
    rt = _runtime_or_503()
    return await asyncio.get_running_loop().run_in_executor(None, rt.alert_policy, pattern)


@app.get("/api/incidents")
def list_incidents():
    return [i.to_dict() | {"card": None} for i in sorted(incidents.values(), key=lambda i: i.created, reverse=True)]


@app.get("/api/incidents/{inc_id}")
def get_incident(inc_id: str):
    inc = incidents.get(inc_id)
    if not inc:
        raise HTTPException(404, f"사건 {inc_id} 이(가) 없습니다")
    rt=instance_mode.current()
    return inc.to_dict() | {'processOwned':bool(rt and rt.repo.incident_is_process_owned(inc_id))}


AUDIT_PAGE_MAX = 500          # 메모리 · 저장 파일이 쥔 감사 기록 줄 수(_audit) — 한 번에 그보다 많이 줄 것이 없다


@app.get("/api/audit")
def get_audit(incident: str | None = None, limit: int = 100):
    """최근 감사 기록(새것 먼저). incident 를 주면 그 사건의 기록만 거른 뒤 자른다(W2-06: 전체의 최근 100줄에서 거르면 지난 사건의 기록이 「없음」으로
    보였다). 메모리에는 최근 AUDIT_PAGE_MAX 줄만 있다 — 그보다 오래된 기록은 Kafka 감사 토픽(시계열 DB)에 있다."""
    if not 1 <= limit <= AUDIT_PAGE_MAX:
        raise HTTPException(400, f"limit 은 1~{AUDIT_PAGE_MAX} 사이여야 합니다")
    rows = [e for e in list(audit_log) if incident is None or e.get("incident") == incident]
    return rows[:limit]


@app.get("/api/plant/{asset}/status")
def get_plant_status(asset: str):
    """Latest plant.status (PLC mode · state · last ACK) — the agent's source for the DMN facts plc_mode / plc_state."""
    st = plant_status.get(asset)
    if not st:
        raise HTTPException(404, f"{asset} 의 설비 상태(plant.status)를 아직 받지 못했습니다")
    return st


@app.get("/api/time-scale")
def get_time_scale():
    """배속(TIME_SCALE, compose 한 곳) — agent · dmn-mcp 가 읽는다(CLAUDE.md 4절). 사람이 읽고 고르는 시한은 벽시계라 여기 없다."""
    return {"time_scale": TIME_SCALE}


# ---------------------------------------------------------------- enterprise decisions (L7 -> L8 -> L9)
def _audit(asset: str, actor: str, event: str, detail: dict, incident: str | None = None):
    evt = {"t": now_iso(), "incident": incident, "asset": asset, "actor": actor, "event": event, "detail": detail}
    audit_log.insert(0, evt)
    del audit_log[AUDIT_PAGE_MAX:]
    persist()
    # callable from worker threads too (instance hooks); a send failure is logged, never silent (A-07)
    _send_logged(topics.K_AUDIT, topics.asset_key(asset if asset in ("HYD-01", "HYD-02", "HYD-03") else "HYD-01"), evt, f"audit {event}")


# atomic system transactions of an SOP skill -> the enterprise-sim job that performs them
TX_JOBS = {"WO_CREATE": "skill:schedule-maintenance", "PR_CREATE": "skill:procure-part",
           "WO_RESCHEDULE": "skill:reschedule-maintenance",
           # C2 승인 뒤 실행 부품: 입고 확인 · 정비 수행 모사(작업지시 완료)
           "GR_CONFIRM": "skill:receive-goods", "WO_COMPLETE": "skill:complete-maintenance",
           # 시운전 통과 뒤 운전시간 계수기 리셋 · 다음 기한 기록 (시나리오 B)
           "PM_RESET": "skill:pm-reset"}


def _window_params(window, opt: dict) -> dict:
    """C2: 승인된 정비 시점 → CMMS window 인자. 예정된 정비 시간 id('MW-…') · {id|window_id, label, starts_at} · 글 라벨을 받는다."""
    if isinstance(window, dict):
        out = {}
        if window.get("id") or window.get("window_id"):
            out["window_id"] = window.get("id") or window.get("window_id")
        if window.get("label"):
            out["window"] = str(window["label"])
        if window.get("starts_at") and "window_id" not in out:
            out["window_starts_at"] = window["starts_at"]
        return out or {"window": "즉시"}
    if isinstance(window, str) and window.strip():
        return {"window_id": window.strip()} if window.strip().startswith("MW-") else {"window": window.strip()}
    # 카드 · 흐름이 정비 시점을 싣지 않은 작업지시(센서 경보 조치)는 즉시다 — 카드 id 글자로 시점을 짐작하지 않는다(G2-09)
    return {"window": "즉시"}


def exec_skill(d: dict, item: dict) -> dict:
    """POST one approved system transaction (CMMS work order, ERP purchase request) of the chosen SOP skill."""
    opt = next(o for o in d["options"] if o["id"] == d["chosen"])
    from hydcommon.execution_scope import require_decision_option
    require_decision_option(d, opt)
    job = TX_JOBS.get(item.get("code"))
    out = {"skill": item["skill"], "code": item.get("code"), "system": item.get("system")}
    if not job:
        return out | {"ok": False, "error": f"실행할 수 없는 트랜잭션 {item.get('code')}"}
    if item["code"] == "WO_CREATE":
        params = {"task": f"{item.get('sop') or opt.get('sopId')} {opt.get('name')} → 작업지시 {item.get('value')}",
                  **_window_params(item.get("window"), opt)}
        if opt.get('maintenancePlan'):
            if item.get('schedule_plan') != opt['maintenancePlan']:
                return out | {'ok':False,'error':'승인한 원문 정비 범위 계획과 실행 인자가 다릅니다'}
            job='skill:schedule-maintenance-scoped'
            params={'task':params['task'],'plan':copy.deepcopy(opt['maintenancePlan'])}
    elif item['code'] == 'WO_RESCHEDULE':
        plan = opt.get('maintenancePlan') or {}
        if plan.get('code') != 'WO_RESCHEDULE' or item.get('ref') != plan.get('ref') or item.get('expected_order') != plan.get('expected_order'):
            return out | {'ok':False,'error':'승인한 PM 기존 오더의 일정 변경 계획과 실행 인자가 다릅니다'}
        params = {'ref':plan['ref'],'expected_order':plan['expected_order'],'cycle':plan.get('cycle'),'plan':copy.deepcopy(plan),
                  'window_id':(plan.get('window') or {}).get('id')}
        if not params['window_id']:
            return out | {'ok':False,'error':'실제 목표 정비 창이 없습니다'}
    elif item["code"] == "PR_CREATE":
        if not isinstance(item.get('value'), str) or not item['value'].strip():
            return out | {'ok': False, 'error': '승인한 실제 공급사가 없습니다 — 기본 공급사로 대신 발주하지 않습니다'}
        params = {"supplier": item['value'], "part": opt.get("name")}
        if item.get("part_no"):          # C2: 승인 경로가 확정한 부품 · 수량 · 금액 (ERP 가 견적 · AVL · 금액을 다시 확인)
            params.update(part_no=item["part_no"], qty=item["qty"], amount=item["amount"])
    else:                                # C2: GR_CONFIRM(입고) · WO_COMPLETE(작업지시 완료) · PM_RESET(계수기 리셋) — 대상 기록 번호
        params = {"ref": item.get("ref")}
        if item.get("sop"):
            params["sop"] = item["sop"]
        if item.get("basis"):            # H-11: 입고 확인의 시간 근거(수업 즉시 입고 · 시간 압축 — service_parts.receipt_basis)를 거래 기록에
            params["basis"] = item["basis"]
    body = {"decision": d["id"], "option": opt["id"], "skill": job, "system": item.get("system"), "asset": d.get("asset"),
            "by": d.get("approvedBy"), "params": params}
    try:
        tx = _enterprise("/api/exec", body)
    except ServiceRefused as e:
        return out | {"ok": False, "error": str(e)}
    if not isinstance(tx, dict) or not isinstance(tx.get('ref'), str) or not tx['ref'].strip():
        return out | {"ok": False, "error": f"업무 시스템 응답에 실제 거래 번호(ref)가 없습니다: {json.dumps(tx, ensure_ascii=False)[:200]}"}
    return out | {"ok": True, "ref": tx.get("ref"), "detail": tx.get("detail"), "after": tx.get("after")}


@app.post("/api/decisions")
async def create_decision(payload: dict):
    return await asyncio.get_running_loop().run_in_executor(None, _create_decision, payload)


DECISION_ID_MAX = 200


def _decision_problems(payload) -> list[dict]:
    """판단 접수 본문의 모양(판단 엔진 dmn-mcp 가 보내는 계약) — 틀린 칸마다 {field, reason}. 모양이 맞아야 장부에 쓴다(P5-01)."""
    if not isinstance(payload, dict):
        return [{"field": "", "reason": "판단 본문이 객체가 아닙니다"}]
    out = []

    def text(value, limit=DECISION_ID_MAX):
        return isinstance(value, str) and value.strip() != "" and len(value) <= limit
    if not text(payload.get("id")):
        out.append({"field": "id", "reason": f"판단 id 가 없습니다(글, {DECISION_ID_MAX}자 이하)"})
    if not text(payload.get("asset")):
        out.append({"field": "asset", "reason": "설비 id 가 없습니다"})
    options = payload.get("options")
    if not isinstance(options, list) or not options:
        out.append({"field": "options", "reason": "조치 카드 목록이 비었거나 목록이 아닙니다"})
    else:
        ids = []
        for n, o in enumerate(options):
            if not isinstance(o, dict) or not text(o.get("id")):
                out.append({"field": f"options[{n}]", "reason": "조치 카드는 id(글)가 있는 객체여야 합니다"})
            else:
                ids.append(o["id"])
        twice = sorted({i for i in ids if ids.count(i) > 1})
        if twice:
            out.append({"field": "options", "reason": f"조치 카드 id {', '.join(twice)} 가 두 번 이상 있습니다"})
        rec = payload.get("recommended")
        if rec is not None and rec not in ids:
            out.append({"field": "recommended", "reason": "추천 카드 id 가 조치 카드 목록에 없습니다"})
    origin = payload.get("origin")
    if not isinstance(origin, dict):
        out.append({"field": "origin", "reason": "판단의 출처(사건 · 처리 건 작업)가 객체로 없습니다"})
    return out


def _create_decision(payload: dict):
    """판단 하나를 접수한다 — 판단은 경보로 열린 처리 건의 에이전트 단계 안에서만 생긴다(W3-05 · P1-20). 그 처리 건의 사건(origin.incident)과
    지금 점유된 생산 작업(origin.process_scope — 작업 행 · 세대 · 판본 · 점유한 워커)이 맞을 때만 받는다: 승인할 길이 없는 판단(사건 없음)이
    장부에 영원히 「승인 대기」로 남지 않고, 그 작업을 점유한 워커 말고는(다른 웹 페이지 · 손 요청) 판단을 쓸 수 없다(P5-08).
    승인과 겹치지 않게 처리 건 잠금 안에서 판정 → 쓴다."""
    problems = _decision_problems(payload)
    if problems:
        raise HTTPException(400, {"reason": "판단 형식이 맞지 않아 접수하지 않았습니다 — " + " · ".join(f"{p['field']}: {p['reason']}" for p in problems),
                                  "problems": problems})
    origin = payload['origin']
    if not isinstance(origin.get('incident'), str) or not origin['incident'].strip() or not isinstance(origin.get('process_scope'), dict):
        raise HTTPException(409, '판단은 경보로 열린 처리 건의 에이전트 단계 안에서만 접수합니다 — 처리 건의 사건(incident)과 '
                                 '생산 작업(process_scope)이 없는 판단은 승인할 길이 없습니다')
    rt = _runtime_or_503()
    inst = rt.instance_of_incident(origin['incident'])
    if inst is None:
        raise HTTPException(409, f"사건 {origin['incident']} 을(를) 맡은 처리 건이 없습니다 — 판단을 접수하지 않았습니다")
    with rt._transition(inst['proc_inst_id']):
        inst = rt.repo.get_instance(inst['proc_inst_id'])
        scope = origin['process_scope']
        from .decision_scope import validate_submission
        try:
            import uuid
            workitem = rt.repo.get_workitem(str(uuid.UUID(str(scope.get('workitem') or ''))))
        except ValueError:
            raise HTTPException(409, '판단의 생산 작업(process_scope.workitem)이 작업 id 꼴이 아닙니다') from None
        try:
            validate_submission(inst, rt.definition_for(inst), workitem, scope)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        return _store_decision(payload)


@machine._transition
def _store_decision(payload):
    if payload["id"] in book:
        d = book[payload["id"]]
        if (payload.get('origin') or {}).get('process_scope') != (d.get('origin') or {}).get('process_scope'):
            raise HTTPException(409, '같은 판단 ID를 다른 작업/세대에서 재사용할 수 없습니다')
        return {"id": d["id"], "state": d["state"], "duplicate": True}
    origin=payload.get('origin') or {}
    scope = declib.submission_scope(payload)
    if scope is not None:
        existing = next((d for d in book.values() if declib.submission_scope(d) == scope), None)
        if existing:
            keys = ('asset', 'scenario', 'recommended', 'options', 'facts', 'evaluation_mode', 'execution_checked')
            if any(payload.get(k) != existing.get(k) for k in keys):
                raise HTTPException(409, f"이 작업은 이미 판단 {existing['id']}을 제출했습니다. 기존 판단을 확인하세요. 변경은 새 판단 단계에서 제출해야 합니다")
            return {'id': existing['id'], 'state': existing['state'], 'duplicate': True}
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
    return {"id": d["id"], "state": d["state"]}


@app.get("/api/decisions")
def list_decisions():
    return [{k: d.get(k) for k in ("id", "created", "scenario", "asset", "state", "recommended", "chosen", "approvedBy", "approvedRole",
                                    "override", "origin", "applicable")} for d in sorted(book.values(), key=lambda d: d["created"], reverse=True)]


@app.get("/api/decisions/{did}")
def get_decision(did: str):
    d = book.get(did)
    if not d:
        raise HTTPException(404, f"판단 {did} 이(가) 없습니다")
    out = copy.deepcopy(d)              # 응답 사본에만 싣는다 — 장부 원본은 바꾸지 않는다
    for opt in out.get("options") or []:
        opt["approvable_roles"] = declib.approver_roles(d, opt)   # 그 안을 승인할 수 있는 역할(판정 정본 decisions.holds_approver_role — 화면 사본 없이 단추를 켜고 끔)
    return out


# ---------------------------------------------------------------- knowledge administration (humans edit the ontology through L9)
def _kg():
    """새 Neo4j 드라이버 하나 — 받은 쪽이 닫는다(`with _kg() as driver`). 설정 · 알림 · 풀 확인은 hydcommon.graphdb 한 곳(결정 2)."""
    return graphdb.connect()


_graph = None
_graph_lock = threading.Lock()


def _shared_graph():
    """_q 가 함께 쓰는 드라이버 하나(처음 질의 때 연다). 투영 · 정리 주기가 질의마다 드라이버 · 연결 풀을 새로 만들지 않게 — 드라이버는 여러
    스레드가 함께 써도 되고 세션은 질의마다 따로다. 끄기(_shutdown)가 닫는다."""
    global _graph
    with _graph_lock:
        if _graph is None:
            _graph = graphdb.connect()
        return _graph


def _q(cypher: str, **params) -> list[dict]:
    # managed write transaction: the driver retries a dropped connection and transient errors
    with _shared_graph().session() as s:
        return s.execute_write(lambda tx: [r.data() for r in tx.run(cypher, **params)])


SKILL_Q = """
MATCH (k:Skill) WHERE $id IS NULL OR k.id = $id
OPTIONAL MATCH (k)-[:APPROVED_BY]->(r:Role)
RETURN k.id AS id, k.sopId AS sopId, k.name AS name, k.description AS description, k.kind AS kind, k._manual_document AS source_document, k.source_id AS source_id,
       k.scope AS scope, k.executable AS executable,k.supplier_policy AS supplier_policy,k.maintenance_policy AS maintenance_policy,k.purchase_comparison_policy AS purchase_comparison_policy,
       COLLECT { MATCH (k)-[:INVOLVES_PART]->(p:Part) RETURN {id:p.id,name:p.name,partNo:p.partNo} ORDER BY p.id } AS parts,
       CASE WHEN r IS NULL THEN null ELSE {id: r.id, name: r.name, level:r.level} END AS approver,
       COLLECT { MATCH (fm:FailureMode)-[m:MITIGATED_BY|REMEDIED_BY|PREVENTED_BY]->(k) RETURN {id: fm.id, name: fm.name, relation: type(m)} } AS failureModes,
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
    with _shared_graph().session() as session:
        return skill_graph.write(session, SKILL_Q, sid, values, create=create,
            expected_revision=body.get('revision'), request_id=body.get('request_id'),
            by=actor_or_400(body.get('by')))


@app.put("/api/kg/skills/{sid}")
async def kg_update_skill(sid: str, body: dict):
    try:
        values = kgadmin.validate_skill(body)
        out = await asyncio.get_running_loop().run_in_executor(None, lambda: _author_skill(sid, values, body))
    except KeyError:
        raise HTTPException(404, f'조치 방법(스킬) {sid} 이(가) 지식 그래프에 없습니다') from None
    except skill_graph.Conflict as error:
        raise HTTPException(409, str(error))
    except ValueError as error:
        raise HTTPException(400, str(error))
    _audit('-', actor_or_400(body.get('by')), 'SKILL_EDITED', {'skill': sid, 'name': values['name']})
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
    _audit('-', actor_or_400(body.get('by')), 'SKILL_CREATED', {'skill': sid, 'sop': values['sopId']})
    return out


# Document originals are durable; source review and graph commit have distinct states.
from pathlib import Path
from .manual_sources import ManualSources
from . import manual_api
from .manual_approved_cache import ApprovedExtractions
from . import course_policy, course_bootstrap
course_bootstrap.mount(app)
_course = course_policy.mount(app, runtime_factory=instance_mode.current)   # 수업 경계 정본(단계 선언이 깨졌으면 여기서 멈춘다)
from . import course_model
course_model.mount(app, policy=_course, runtime_factory=instance_mode.current, settings=os.environ)
manual_api.register(app,
    archive_factory=lambda: ManualSources(Path(os.getenv("PROCESS_STATE_PATH", "/data/process.sqlite3")).with_name("manuals.sqlite3")),
    driver_factory=_kg, tenant=os.getenv("TENANT_ID", "hyd"), audit=_audit,
    runtime_factory=instance_mode.current, approved_cache=ApprovedExtractions())
# A9 옛 DB 뜻 복원: AI candidates (agent task) → a person's review → only approved meanings reach the DDL plan
from . import legacy_meaning, legacy_meaning_api
from .legacy_meaning_store import LegacyMeaningStore
_legacy_store = lambda: LegacyMeaningStore(Path(os.getenv("PROCESS_STATE_PATH", "/data/process.sqlite3")).with_name("legacy_meanings.sqlite3"))
_legacy = legacy_meaning_api.Bridge(_legacy_store, os.getenv("TENANT_ID", "hyd"))
legacy_meaning_api.register(app, driver_factory=_kg, tenant=os.getenv("TENANT_ID", "hyd"), audit=_audit,
    runtime_factory=instance_mode.current, store_factory=_legacy_store, worker_probe=lambda: instance_mode.worker_status())

# A4 (U6): AI 판단 채점 — 화면에서 적은 정답표 대비 점수 · 반복 흔들림 · 지식 고치기 전·후 비교 (procsvc/eval_api.py · judgment_eval.py)
from . import eval_api, judgment_eval, procdb as _procdb
eval_api.register(app, driver_factory=_kg, book=book, incidents=incidents, runtime_factory=instance_mode.current, audit=_audit,
    agent_url=os.getenv('AGENT_URL', 'http://agent:8091'),
    store_factory=lambda: judgment_eval.PgEvalStore(_procdb.SUPABASE_DSN, os.getenv("TENANT_ID", "hyd")))
# U3 (A2 MCP): 도구 지도 · 읽기 전용 도구 써 보기 · 호출 기록 — tenants.mcp 와 events 를 읽기만 한다 (procsvc/mcp_api.py)
from . import mcp_api
mcp_api.register(app, runtime_factory=instance_mode.current, audit=_audit)
# B2: MCP 서버 등록 · 고치기 · 지우기 · 연결 검사 게이트 · 되돌리기 (procsvc/mcp_registry.py)
from . import mcp_registry
mcp_registry.mount(app, runtime_factory=instance_mode.current, audit=_audit)
# G2 (전체 과정 랩업): MCP 설정의 ${SECRET:KEY} 값 — 쓰기만 하고 돌려주지 않는다 (procsvc/mcp_secrets.py)
from . import mcp_secrets
mcp_secrets.mount(app, runtime_factory=instance_mode.current, audit=_audit)

# A11 데이터 패브릭 미니: 업무 DB · 시계열 DB 읽기 전용 묶어 보기 (전용 읽기 계정만, fabric_api.py)
from . import fabric_api
fabric_api.register(app, driver_factory=_kg)

# A8 (U11): KPI 실적 · 역추적 — 시계열 · 업무 DB · 처리 기록에서 지표 실적, 미달 지표 → 원인 처리 건 (읽기 전용)
from . import kpi
from .procdb import SUPABASE_DSN as _KPI_BIZ_DSN
kpi.register(app, ts_dsn=PG_DSN, biz_dsn=_KPI_BIZ_DSN, driver_factory=_kg, time_scale=TIME_SCALE, tenant=os.getenv("TENANT_ID", "hyd"))

# A10 에이전트 시험 실행 · 비교 (읽기 전용 판단, 처리 건 · 명령 없음)
from . import agent_trials
agent_trials.register(app, runtime_factory=instance_mode.current)

# B5 에이전트에게 질문하기: 질문 하나 = 처리 건 하나(정식 정의 ask_agent), 답할 에이전트 선택, 근거 대조 (procsvc/ask.py)
from . import ask
ask.register(app, runtime_factory=instance_mode.current, definitions_dir=instance_mode.DEFINITIONS_DIR,
             worker_probe=lambda: instance_mode.worker_status())
# B3 bpmn.io 그림 가져오기: task 별 부품 · 담당 매핑 → 사전 검사 → 판본 등록(그림 원본 함께), 기준으로 되돌리기 (flows_api.py)
from . import flows_api
flows_api.register(app, runtime_factory=instance_mode.current, audit=_audit)
# B6 출발본: 학생 구성 내보내기 · 가져오기(되돌리기 → 순서대로 적용 → 대조) · 하나의 기준으로 되돌리기 (config_bundle.py)
from . import config_bundle
config_bundle.register(app, runtime_factory=instance_mode.current, audit=_audit)


# 경보로 처리 건을 여는 길은 원천 접수 하나다(B-10): Kafka 경보 · 사람 입력 경보(B7, human_alert.py) · 업무 감시 · 수업 버튼 ·
# 강의 도우미(/api/instances/start alert) 모두 같은 접수 → 같은 처리기(rt.receive_alert)로 간다. 같은 경보는 같은 처리 건이다.
async def _admit_alert(alert: dict) -> dict:
    """경보 하나를 원천 접수하고 처리될 때까지 기다린다. 돌려줌 = 접수 결과 {instance, incident, definition, duplicate}."""
    rt = _runtime_or_503()
    if source_delivery is None or source_inbox is None:
        raise TimeoutError('원천 접수가 아직 준비되지 않았습니다 — 잠시 뒤 다시 시도하세요')
    record = source_record(topics.K_ALERTS, None, None, alert, source='http')
    if record['kind'] != 'RAISE':
        raise ValueError(record.get('error') or '경보는 asset · alertId · state RAISE 를 가진 원천 형식이어야 합니다')
    policy = await asyncio.to_thread(rt.alert_policy, record['payload'].get('pattern'))
    receipt = await asyncio.to_thread(source_inbox.receive, record, policy)
    # 새 접수는 PENDING 으로 생긴다. 같은 배달이면 처음 접수 행이(처리됨 등), 같은 경보의 다른 배달이면 DUPLICATE 행이 돌아온다
    duplicate = receipt['status'] != 'PENDING'
    handled = await source_delivery.wait_for(receipt)
    return dict(handled.get('result') or {}, duplicate=duplicate)


# C3 B · C 단순화: 포털 '결함 실험'의 버튼 (scenario_buttons.py). [정기 점검] · [재고 보충]은 업무 감시와 같은 계약의 경보를 만들어 같은
# 원천 접수 경로로 보낸다 — 배포된 B · C 흐름이 처리 건을 연다. [쿨러 열화 주입] · [쿨러 복구]는 plant-sim 에 누름 id 를 실어 보내고, 그 주입이
# 일으킨 경보로 열린 처리 건에 같은 id 로 연결한다(case_started). 누름은 모두 감사 기록 SCENARIO_BUTTON(누가 · 언제 · 무엇)에 남는다.
from . import business_monitor, scenario_buttons


def _scenario_route(pattern: str) -> str | None:
    from . import flow_deploy
    rt = instance_mode.current()
    defn = flow_deploy.route_definition(rt, pattern)
    return defn.id if defn is not None and defn.id != rt.defn.id else None


def _press_audit(asset: str, person: dict, button: str, scenario: str, at: str, **detail) -> None:
    _audit(asset, person["by"], "SCENARIO_BUTTON", {"scenario": scenario, "button": button, "at": at, **person, **detail})


def _last_press(asset: str) -> dict | None:
    """그 설비의 마지막 수업 버튼(감사 기록) — 처리 건이 없는 [초기화]도 화면 버튼 옆에 보인다."""
    e = next((e for e in audit_log if e.get("asset") == asset and e.get("event") == "SCENARIO_BUTTON"), None)
    return {k: e["detail"].get(k) for k in ("button", "by", "at", "instance")} if e else None


def _scenario_rt():
    return _runtime_or_503()


async def _reanchor_if_idle(rt, button: str | None = None) -> dict:
    """시나리오 시각 기준점을 지금으로. 설비 처리 건이 진행 중이면 옮기지 않는다 — 예정된 정비 시간 id 가 기준점 시각을 품어, 옮기면 진행 중인
    처리 건이 승인 뒤 낼 작업지시의 창이 사라진다(scenario_buttons.reanchor_blockers). 승인 지연을 선언하고 사람만 기다리는 처리 건은 붙잡지
    않는다(P12) — 옮겼으면 그 처리 건 기록에 남긴다. 돌려줌 {moved, blocked_by[], overdue[]}(응답 'reanchor' · 감사 기록에 남긴다 — 막았으면
    어느 처리 건이 막았는지 이름으로)."""
    found = await asyncio.to_thread(scenario_buttons.reanchor_blockers, rt)
    if found["blocked_by"]:
        return dict(found, moved=False)
    await asyncio.to_thread(_entsim_post, "/api/reanchor", {})
    if found["overdue"]:
        at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        await asyncio.to_thread(rt.repo.record_events, [scenario_buttons.reanchor_event(o["instance"], at, button) for o in found["overdue"]])
    return dict(found, moved=True)


def _reanchor_audit(r: dict) -> dict:
    """감사 기록 칸: 옮겼는지 + 막은 · 붙잡지 않은 처리 건 id."""
    return {"reanchored": r["moved"], "reanchor_blocked_by": [b["instance"] for b in r["blocked_by"]],
            "reanchor_overdue": [o["instance"] for o in r["overdue"]]}


_SCENARIO_LOCKS: dict[str, tuple] = {}


def _scenario_lock(key: str) -> asyncio.Lock:
    """P6 (audit2): 시나리오마다 하나 — '진행 중' 검사(prepare)부터 경보 접수 · 처리 건 확인까지를 묶는다. 경보 id 가 누른 시각(초)이라 1초 넘게
    떨어진 두 요청(두 탭 · 두 학생)은 원천 중복 제거에 걸리지 않아 처리 건이 둘 열렸다. 이벤트 루프마다 새로 만든다(시험 클라이언트는 루프가 바뀐다)."""
    loop = asyncio.get_running_loop()
    held = _SCENARIO_LOCKS.get(key)
    if held is None or held[0] is not loop:
        held = _SCENARIO_LOCKS[key] = (loop, asyncio.Lock())
    return held[1]


@app.get("/api/scenario/status")
async def scenario_status():
    """시나리오 B · C 의 화면 표시(정기 점검 도래 · 재고 보충 필요) · 근거 값 · 진행 중 · 마지막 처리 건, 설비마다 마지막 수업 버튼."""
    return await asyncio.to_thread(scenario_buttons.status, instance_mode.enterprise_read, _scenario_rt(), _last_press)


@app.post("/api/scenario/{key}/start")
async def scenario_start(key: str, body: dict | None = None):
    """[정기 점검](B) · [재고 보충](C): (설비 처리 건이 진행 중이 아니면) 시나리오 시각 기준점을 지금으로 맞추고, 지금 업무 값으로 경보를 만들어
    배포된 흐름의 처리 건을 연다. 기준점은 업무 값을 읽기 전에 옮긴다 — 경보 근거의 예정된 정비 시간이 새 기준점의 것이어야 한다.
    시나리오마다 한 번에 하나(_scenario_lock) — 겹친 두 번째 요청은 첫 처리 건을 보고 '이미 진행 중'(409)으로 거절된다."""
    rt = _scenario_rt()
    key = key.upper()
    if key not in scenario_buttons.SCENARIOS:
        raise HTTPException(404, f"모르는 시나리오 {key}")
    person = scenario_buttons.who(body)
    button = scenario_buttons.SCENARIOS[key]["button"]
    spec = scenario_buttons.SCENARIOS[key]
    async with _scenario_lock(key):
        # 거절 검사를 기준점보다 먼저(P5-18 · P4-24) — 거절된 누름은 업무 시각을 바꾸지 않고, 감사 기록에 그 까닭으로 남는다
        try:
            await asyncio.to_thread(scenario_buttons.refusal, key, instance_mode.enterprise_read, rt, _scenario_route)
        except scenario_buttons.Refused as e:
            _press_audit(spec["asset"], person, button, key, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         instance=None, error=str(e), refused=True, reanchored=False)
            raise HTTPException(409, str(e)) from None
        reanchor = await _reanchor_if_idle(rt, button)
        try:
            prep = await asyncio.to_thread(scenario_buttons.prepare, key, instance_mode.enterprise_read, rt, _scenario_route, person)
        except scenario_buttons.Refused as e:          # 기준점을 옮긴 뒤의 업무 값이 거절 조건에 들었다(드묾) — 옮긴 것까지 남긴다
            _press_audit(spec["asset"], person, button, key, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         instance=None, error=str(e), refused=True, **_reanchor_audit(reanchor))
            raise HTTPException(409, str(e)) from None
        alert = prep["alert"]
        try:
            await _admit_alert(alert)
        except (ValueError, LookupError) as e:       # P8 (audit2): /api/human-alerts 와 같은 사유 · 같은 코드, 누름 기록은 error 칸에
            _press_audit(alert["asset"], person, button, key, alert["evidence"]["requested_at"], instance=None, alertId=alert["alertId"],
                         error=f"경보를 접수하지 못했습니다: {e}")
            raise HTTPException(409, f"경보를 접수하지 못했습니다: {e}") from e
        except TimeoutError as e:
            _press_audit(alert["asset"], person, button, key, alert["evidence"]["requested_at"], instance=None, alertId=alert["alertId"],
                         error=f"경보 접수 확인 시간이 지났습니다: {e}")
            raise HTTPException(503, f"경보 접수 확인 시간이 지났습니다: {e}") from e
        try:
            out = await asyncio.to_thread(scenario_buttons.started, rt, key, alert, _scenario_route(alert["pattern"]), person)
        except scenario_buttons.NotStarted as e:       # 접수와 확인 사이에 배포가 바뀐 상태 충돌 — 서버 고장(500)이 아니다
            _press_audit(alert["asset"], person, button, key, alert["evidence"]["requested_at"],
                         instance=None, alertId=alert["alertId"], error=str(e))
            raise HTTPException(409, str(e)) from e
    _press_audit(alert["asset"], person, button, key, alert["evidence"]["requested_at"],
                 instance=out["instance"], alertId=alert["alertId"], **_reanchor_audit(reanchor))
    return dict(out, reanchored=reanchor["moved"], reanchor=reanchor)


@app.post("/api/scenario/{key}/reset")
async def scenario_reset(key: str, body: dict | None = None):
    """[초기화]: B = 운전시간 계수기 세 대(묶음 후보 HYD-03 포함) · 이번 회차 오더 표시, C = 씰 키트 재고를 수업 시작값으로, 시나리오 시각
    기준점을 지금으로. 끝난 처리 건 기록은 남는다. 누름은 감사 기록과(있으면) 그 시나리오 마지막 처리 건 기록에 남는다."""
    rt = _scenario_rt()
    key = key.upper()
    if key not in scenario_buttons.SCENARIOS:
        raise HTTPException(404, f"모르는 시나리오 {key}")
    spec = scenario_buttons.SCENARIOS[key]
    person = scenario_buttons.who(body)
    async with _scenario_lock(key):          # [정기 점검] · [재고 보충]의 검사~접수 도중에 업무 값을 바꾸지 않게
        try:
            await asyncio.to_thread(scenario_buttons.reset_refusal, rt, key)
        except scenario_buttons.Refused as e:
            _press_audit(spec["asset"], person, "초기화", key, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         instance=None, error=str(e), refused=True, reanchored=False)
            raise HTTPException(409, str(e)) from None
        await asyncio.to_thread(_entsim_post, *spec["reset"])
        reanchor = await _reanchor_if_idle(rt, "초기화")
        at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        last = await asyncio.to_thread(scenario_buttons.last_instance, rt, key)
        if last:
            await asyncio.to_thread(rt.repo.record_events, [scenario_buttons.press_event(
                last["proc_inst_id"], "초기화", spec["asset"], person, at, {"effect": f"{spec['label']} 표시를 수업 시작 상태로 되돌림"})])
    _press_audit(spec["asset"], person, "초기화", key, at, instance=last["proc_inst_id"] if last else None, **_reanchor_audit(reanchor))
    return dict(await asyncio.to_thread(scenario_buttons.status, instance_mode.enterprise_read, rt, _last_press),
                reanchored=reanchor["moved"], reanchor=reanchor)


@app.post("/api/scenario/A/{act}")
async def scenario_a_button(act: str, body: dict | None = None):
    """[쿨러 열화 주입] · [쿨러 복구] (HYD-01). 누름 id(origin)를 plant-sim 주입에 실어 보낸다 — 설비 상태(plant.status injection)에 남고, 그
    주입이 일으킨 경보로 열린 처리 건에 case_started 가 같은 id 로 기록을 붙인다. 복구는 지금 주입 id 로 연결된 처리 건에 기록한다.
    복구는 팬 · 부하 지령도 평소 운전점으로 되돌린다 — 바뀐 값(setpoints 전 · 후)을 그 기록과 감사 기록에 남긴다."""
    rt = _scenario_rt()
    if act not in scenario_buttons.A_BUTTONS:
        raise HTTPException(404, f"모르는 A 버튼 {act}")
    spec = scenario_buttons.A_BUTTONS[act]
    asset = scenario_buttons.A_ASSET
    person = scenario_buttons.who(body)
    reanchor = await _reanchor_if_idle(rt, spec["button"]) if act == "degrade" else {"moved": False, "blocked_by": [], "overdue": []}
    caused_by = (plant_status.get(asset) or {}).get("injection")
    origin = scenario_buttons.injection_origin(spec["button"], person)
    res = await asyncio.to_thread(_plant_post, "/api/fault", dict(spec["fault"], asset=asset, origin=origin))
    linked = None
    if act == "restore" and caused_by and caused_by.get("kind") != "restore":
        linked = await asyncio.to_thread(scenario_buttons.case_of_injection, rt, asset, caused_by)
        if linked:
            await asyncio.to_thread(rt.repo.record_events, [scenario_buttons.press_event(
                linked, spec["button"], asset, person, origin["at"],
                {"injection_id": origin["id"], "restores": caused_by["id"], "setpoints": res.get("setpoints")})])
    _press_audit(asset, person, spec["button"], "A", origin["at"], injection_id=origin["id"], instance=linked, **_reanchor_audit(reanchor),
                 setpoints=res.get("setpoints"))
    return {"ok": True, "button": spec["button"], "asset": asset, "at": origin["at"], "injection_id": origin["id"], "instance": linked,
            "plant": res, "reanchored": reanchor["moved"], "reanchor": reanchor}


def _route_error(e: ServiceRefused) -> HTTPException:
    """수업 버튼 라우트의 바깥 서비스 실패 → 그 서비스의 거절(400 · 404 · 409)은 같은 코드, 그 밖(닿지 않음 · 5xx)은 502 — 사유는 그대로."""
    return HTTPException(e.status if e.status in (400, 404, 409) else 502, str(e))


def _plant_post(path: str, body: dict) -> dict:
    try:
        return _service_json(instance_mode.PLANT_SIM_URL, "설비 시뮬레이터(plant-sim)", path, body)
    except ServiceRefused as e:
        raise _route_error(e) from None


def _link_injection(inst: dict) -> None:
    """case_started 훅: 센서 경보로 열린 처리 건이면, 그 설비의 지금 주입(누름 id 가 실린 것)을 처리 건 기록에 붙인다."""
    v = engine.variables(inst)
    alert = v.get("alert") or {}
    if not alert or business_monitor.is_business_alert(alert):
        return
    inj = (plant_status.get(v.get("asset")) or {}).get("injection")
    if inj and inj.get("kind") != "restore":
        instance_mode.current().repo.record_events([scenario_buttons.press_event(
            inst["proc_inst_id"], inj["button"], v["asset"], inj, inj["at"], {"injection_id": inj["id"], "alertId": alert.get("alertId")})])


def _entsim_post(path: str, body: dict) -> dict:
    try:
        return _enterprise(path, body)
    except ServiceRefused as e:
        raise _route_error(e) from None


from . import human_alert
human_alert.register(app, runtime_factory=instance_mode.current, admit=_admit_alert, audit=_audit,
                     open_alerts=lambda: [(i.card.get('alert') or {}, i.state) for i in list(incidents.values())
                                          if i.state not in definition.TERMINAL])


# ---------------------------------------------------------------- 인제스천 (회의 2번 · 6번): 회사 DB 의 DDL → System · InputData, 되돌리기, 규칙 → SQL
from hydcommon.fabric import DDL_SOURCES as _fabric_ddl_sources, SOURCES as _fabric_sources


def _ddl_preview(body: dict) -> dict:
    """미리보기 한 번(쓰지 않음): CREATE TABLE 해석 → 출처 시스템 · 입력 데이터 계획 + 옛 DB 뜻 요약 + 지금 그래프의 시스템 목록.
    해석은 큰 DDL 에서 몇 초가 걸리므로 이벤트 루프가 아니라 이 함수(작업 스레드)에서 돈다(P5-03)."""
    name = str(body.get("filename") or "schema.sql")
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(400, "DDL 파일 내용이 비어 있습니다 — CREATE TABLE 문이 든 .sql 파일을 다시 고르세요")
    try:
        course_policy.within_text_max(text, 'DDL 파일')
    except course_policy.AccessDenied as e:
        raise HTTPException(400, f"{e} 가져올 표의 CREATE TABLE 문만 남긴 .sql 파일로 다시 고르세요") from None
    try:
        from . import ddl_sync
        from .procdb import SUPABASE_DSN
        tables, datasource, where = ddl_sync.place(text, body.get("datasource"),
                                                   lambda: psycopg.connect(SUPABASE_DSN, connect_timeout=5))
        legacy = legacy_meaning.summary(tables, text)          # A9: columns without a meaning and the dump's sample rows
        review = _legacy.review_for(body.get("meaning_review"), text)
        refl = legacy_meaning.apply_comments(tables, review["review"]) if review else None
        plan = ingest.plan(tables, filename=name, batch=ingest.new_batch_id("ddl"),
                           selection=body.get("selection"), systems=body.get("systems"),
                           datasource=datasource, catalog=body.get("catalog", "postgres"))
        plan["legacy"] = legacy
        plan["sourceNotes"] = where
        plan["sourceOptions"] = [{"id": d, "label": _fabric_sources[d]["label"], "schema": _fabric_sources[d]["schema"]}
                                 for d in _fabric_ddl_sources]
        if review:
            plan["meaningReview"] = _legacy.applied(plan, review, refl)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e)) from None
    if not tables:
        raise HTTPException(400, "CREATE TABLE 문을 찾지 못했습니다 — 표 정의(CREATE TABLE)가 든 .sql 파일인지 확인하세요")
    plan["existingSystems"] = _q("MATCH (s:System) RETURN s.id AS id, s.name AS name, s.zone AS zone ORDER BY s.id")
    plan["chars"] = len(text)
    return plan


@app.post("/api/kg/ddl/preview")
async def kg_ddl_preview(body: dict):
    """body = {filename, text}. Parses CREATE TABLE statements and proposes the ontology plan
    (System per source system, InputData per selected column with provenance). Nothing is written.
    포털은 파일 내용을 글(text)로 읽어 보낸다 — 예전 base64(data) 갈래는 읽는 함수가 없어 부르면 내부 오류가 났다(지움)."""
    return await asyncio.get_running_loop().run_in_executor(None, _ddl_preview, body)


@app.post("/api/kg/ddl/commit")
async def kg_ddl_commit(body: dict):
    """body = the preview plan (possibly edited: selection/systems) + {by}. Applies the ownership journal and nodes in one transaction."""
    if not body.get("inputs") and not body.get("systems"):
        raise HTTPException(400, "적재할 시스템 · 입력 데이터가 없습니다 — 미리보기에서 표 · 열을 하나 이상 고르세요")
    by = actor_or_400(body.get("by"))
    plan = {"batch": body.get("batch") or ingest.new_batch_id("ddl"), "filename": body.get("filename", "schema.sql"),
            "systems": body.get("systems") or [], "inputs": body.get("inputs") or []}

    try:
        ingest.validate_plan(plan)
        _legacy.check_commit(plan)             # A9: no meaning/REPRESENTS a person did not approve
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(400, str(e))

    def run():
        with _shared_graph().session() as session:
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


@app.post("/api/kg/scm-sync")
async def scm_sync_now():
    """업무 DB 의 공급사 · 견적을 지금 한 번 그래프로(60초 주기 반복과 같은 _scm_sync_once) — 수업 지식 적재(scripts/class_knowledge.py)가
    매뉴얼을 넣기 전에 부른다(G3a-25 순서). 돌려줌 = 동기화 보고 그대로: missing_part(그래프에 없는 부품의 견적 '부품/공급사')가 남으면
    부른 쪽이 그 좌표로 멈춘다. 업무 DB · 그래프를 못 읽으면 503 과 까닭."""
    try:
        return await asyncio.to_thread(_scm_sync_once)
    except Exception as e:  # noqa: BLE001 — 까닭을 그대로 돌려 부른 쪽이 멈추게 한다(조용히 넘기지 않음)
        log.exception("SCM source sync on request failed")
        raise HTTPException(503, f"공급사 · 견적을 그래프로 옮기지 못했습니다({type(e).__name__}): {str(e)[:300]}") from None


@app.get("/api/kg/ingests")
async def kg_ingests():
    """Active batch claims by label; shared nodes may be retained or restored on clear."""
    return await asyncio.get_running_loop().run_in_executor(None, lambda: _q(graph_ingest.BATCHES_Q))


@app.delete("/api/kg/ingests/{batch}")
async def kg_ingest_clear(batch: str, by: str = ""):
    """Release one batch's claims and restore the latest remaining revision atomically."""
    by = actor_or_400(by)
    def run():
        with _shared_graph().session() as session:
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
