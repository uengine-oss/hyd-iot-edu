"""connect-sink (L5): Kafka -> TimescaleDB (the JDBC Sink role of the full architecture, in one Python process).

  plant.tag    -> tag_1s   (batched plain INSERT — no unique key; duplicates are prevented by the sink_offsets checkpoint)
  feat.1s      -> feat_1s  (same: plain INSERT + checkpoint)
  alerts       -> alerts   (by alert_id: RAISE inserts, CLEAR updates; the pattern's display name kept in `name`)
  audit        -> audit    (plain INSERT + checkpoint), and cmd-gateway's CMD_FORWARDED -> actions: the commands that
                  passed the gateway's checks (approval ledger · fingerprint · mode). The first record of a cmd_id is kept;
                  a later one never rewrites it (the audit table has every event).
  plant.status -> actions  (ACK of an automatic command: cmdId/result -> ack_result/ack_reason/ack_at, first ACK wins;
                  FUXA / panel writes are not approved actions and stay out of it)
Every record is checked against its contract (hydcommon.schemas) before it becomes a row: a record outside it is counted
(/healthz rejected · last_rejected) and skipped, its offset still advances — one record never stops the sink. The times
written are the records' own; a record without a valid time is refused, never re-dated.
Rows and the Kafka offsets they came from are committed in one DB transaction (store_records), so a restart or a rebalance
replays records the checkpoint already covers without writing them twice; sink_offsets also keeps the newest record
timestamp so a recreated topic is noticed (hydcommon.kafka.replay_verdict) instead of being skipped.
`sink_batch_age_seconds` is the age of the oldest record in the batch just stored (how far behind the sink is).
"""
import asyncio
import logging
import os
import time

import psycopg
from aiokafka.errors import CommitFailedError
from psycopg.types.json import Jsonb

from hydcommon import schemas, topics
from hydcommon.kafka import consumer as make_consumer, replay_verdict
from hydcommon.metrics import Registry
from hydcommon.service import make_app, stop_after_loop_end
from hydcommon.timeutil import parse_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("connect-sink")
PG_DSN = os.getenv("PG_DSN", "postgresql://hyd:hyd@timescaledb:5432/hyd")

reg = Registry()
c_rows = reg.counter("sink_rows_total", "rows written by table")
g_lag = reg.gauge("sink_batch_age_seconds", "age of oldest row in current batch")
state = {"db": False, "kafka": False, "rows": 0, "last_write": None, "errors": 0, "rejected": 0, "last_rejected": None,
         "offset_resets": 0, "fetch_errors": 0}

TOPICS = [topics.K_TAG, topics.K_FEAT, topics.K_ALERTS, topics.K_STATUS, topics.K_AUDIT]
# Schema this process needs on top of it/timescaledb/init.sql (applied once at initdb): run on every connect so a database
# created by an earlier version gets it too (each statement is idempotent). The action.cmd checkpoint row is from when
# commands were read from that topic. Pruning: alerts · actions · audit are plain tables (no hypertable retention), so one
# TimescaleDB job deletes what is older than 30 days every hour — the same horizon as tag_1m; Kafka keeps the full ledger.
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS sink_offsets (topic TEXT NOT NULL, partition_id INTEGER NOT NULL, next_offset BIGINT NOT NULL, "
    "max_ts BIGINT, PRIMARY KEY(topic, partition_id))",
    "ALTER TABLE sink_offsets ADD COLUMN IF NOT EXISTS max_ts BIGINT",
    "UPDATE sink_offsets SET max_ts = (extract(epoch from now()) * 1000)::bigint WHERE max_ts IS NULL",
    "DELETE FROM sink_offsets WHERE topic = 'action.cmd'",
    "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS name TEXT",
    """CREATE OR REPLACE PROCEDURE hyd_prune_events(job_id int, config jsonb) LANGUAGE SQL AS $$
         DELETE FROM alerts WHERE cleared_at < now() - interval '30 days';
         DELETE FROM actions WHERE coalesce(ack_at, issued_at) < now() - interval '30 days';
         DELETE FROM audit WHERE time < now() - interval '30 days';
       $$""",
    "SELECT add_job('hyd_prune_events', '1 hour') WHERE NOT EXISTS "
    "(SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'hyd_prune_events')",
)


def rows_of(topic: str, v) -> tuple:
    """(kind, row) for one record — kind 'tag' | 'feat' | 'event' (inserted one by one) | None (nothing to store).
    Raises schemas.RecordError for a record outside its contract."""
    raw = v if isinstance(v, dict) else {}
    if topic == topics.K_TAG:
        r = schemas.tag_record(raw.get("asset"), raw.get("name"), v)
        return "tag", (parse_iso(r["t"]), r["asset"], r["name"], r["v"])
    if topic == topics.K_FEAT:
        r = schemas.feat_record(v)
        return "feat", (parse_iso(r["t"]), r["asset"], r["sensor"], r["mean"], r["rms"], r["slope"], r["score"])
    if topic == topics.K_ALERTS:
        return "event", ("alert", schemas.alert_record(v))
    if topic == topics.K_AUDIT:
        r = schemas.audit_record(v)
        if r["actor"] == "cmd-gateway" and r["event"] == "CMD_FORWARDED":
            command = r["detail"].get("command")
            if not isinstance(command, dict) or schemas.validate_action_cmd(command):
                raise schemas.RecordError("CMD_FORWARDED detail.command is not a well-formed action.cmd")
        return "event", ("audit", r)
    if topic == topics.K_STATUS:
        r = schemas.status_record(raw.get("asset"), v)
        if r.get("source") == "HITL" and r.get("cmdId") and r.get("result"):
            return "event", ("ack", r)
        return None, None
    raise schemas.RecordError(f"topic {topic} is not stored")


async def store_event(conn, kind: str, v: dict) -> None:
    async with conn.cursor() as cur:
        if kind == "alert":
            t = parse_iso(v["t"])
            if v["state"] == "RAISE":
                await cur.execute(
                    """INSERT INTO alerts (alert_id, asset, pattern, name, severity, state, raised_at, evidence)
                       VALUES (%s, %s, %s, %s, %s, 'RAISE', %s, %s)
                       ON CONFLICT (alert_id) DO UPDATE SET state='RAISE', raised_at=EXCLUDED.raised_at, evidence=EXCLUDED.evidence,
                           name=EXCLUDED.name""",
                    (v["alertId"], v["asset"], v["pattern"], v.get("name"), v["severity"], t, Jsonb(v.get("evidence") or {})))
            else:
                await cur.execute(
                    """INSERT INTO alerts (alert_id, asset, pattern, name, severity, state, cleared_at, evidence)
                       VALUES (%s, %s, %s, %s, %s, 'CLEAR', %s, %s)
                       ON CONFLICT (alert_id) DO UPDATE SET state='CLEAR', cleared_at=EXCLUDED.cleared_at""",
                    (v["alertId"], v["asset"], v["pattern"], v.get("name"), v["severity"], t, Jsonb(v.get("evidence") or {})))
            c_rows.inc(table="alerts")
        elif kind == "audit":
            await cur.execute("INSERT INTO audit (time, incident, actor, event, detail) VALUES (%s, %s, %s, %s, %s)",
                              (parse_iso(v["t"]), v.get("incident"), v["actor"], v["event"], Jsonb(v.get("detail") or {})))
            c_rows.inc(table="audit")
            if v["actor"] == "cmd-gateway" and v["event"] == "CMD_FORWARDED":
                c = v["detail"]["command"]
                await cur.execute(
                    """INSERT INTO actions (cmd_id, incident, asset, actions, approved_by, issued_at, expires_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (cmd_id) DO UPDATE SET incident=EXCLUDED.incident, asset=EXCLUDED.asset, actions=EXCLUDED.actions,
                           approved_by=EXCLUDED.approved_by, issued_at=EXCLUDED.issued_at, expires_at=EXCLUDED.expires_at
                       WHERE actions.issued_at IS NULL""",
                    (c["cmdId"], c["incident"], c["asset"], Jsonb(c["actions"]), c["approvedBy"],
                     parse_iso(v["t"]), parse_iso(c["expiresAt"])))
                c_rows.inc(table="actions")
        elif kind == "ack":
            await cur.execute(
                """INSERT INTO actions (cmd_id, asset, ack_result, ack_reason, ack_at) VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (cmd_id) DO UPDATE SET ack_result=EXCLUDED.ack_result,
                   ack_reason=EXCLUDED.ack_reason, ack_at=EXCLUDED.ack_at WHERE actions.ack_result IS NULL""",
                (v["cmdId"], v["asset"], v["result"], v.get("reason"), parse_iso(v["t"])))
    state["rows"] += 1


async def connect_db():
    while True:
        try:
            conn = await psycopg.AsyncConnection.connect(PG_DSN, autocommit=True, connect_timeout=5)
            for statement in SCHEMA:
                await conn.execute(statement)
            state["db"] = True
            return conn
        except psycopg.OperationalError as e:
            state["db"] = False
            log.warning("db not ready (%s), retrying", e)
            await asyncio.sleep(2)


TAG_SQL = "INSERT INTO tag_1s (time, asset, name, value) VALUES (%s, %s, %s, %s)"
FEAT_SQL = "INSERT INTO feat_1s (time, asset, sensor, mean, rms, slope, score) VALUES (%s, %s, %s, %s, %s, %s, %s)"


async def write_batch(conn, sql: str, table: str, rows: list) -> None:
    """Batched insert of checked rows."""
    if rows:
        async with conn.cursor() as cur:
            await cur.executemany(sql, rows)
        c_rows.inc(len(rows), table=table)
        state["rows"] += len(rows)


def batch_age_seconds(batches, now_s=None) -> float | None:
    """Age (s) of the oldest record in the batch by its Kafka record timestamp (ms); None for an empty batch."""
    stamps = [r.timestamp for records in batches.values() for r in records if r.timestamp]
    if not stamps:
        return None
    return round(max(0.0, (time.time() if now_s is None else now_s) - min(stamps) / 1000.0), 3)


def _rejected(tp, offset, reason) -> None:
    state["rejected"] += 1
    state["last_rejected"] = f"{tp.topic}/{tp.partition}/{offset}: {reason}"[:200]
    log.warning("rejected record %s", state["last_rejected"])


async def store_records(conn, batches):
    """Rows and source offsets share one DB transaction, including restart/rebalance replay."""
    age = batch_age_seconds(batches)
    if age is not None:
        g_lag.set(age)
    async with conn.transaction():
        for tp, records in batches.items():
            if not records:
                continue
            cur = await conn.execute("SELECT next_offset, max_ts FROM sink_offsets WHERE topic=%s AND partition_id=%s",
                                     (tp.topic, tp.partition))
            row = await cur.fetchone()
            position, max_ts = row if row else (None, None)
            tags, feats = [], []
            for r in records:
                verdict = replay_verdict(r.offset, r.timestamp, position, max_ts)
                if verdict == "recreated":
                    state["offset_resets"] += 1
                    log.error("%s/%s: offset %s is below the checkpoint (%s) but newer than every stored record — the topic "
                              "was recreated; storing its records again from here", tp.topic, tp.partition, r.offset, position)
                    position, max_ts = None, None
                elif verdict == "seen":
                    continue
                try:
                    kind, row = rows_of(tp.topic, r.value)
                except schemas.RecordError as exc:
                    _rejected(tp, r.offset, exc)
                    continue
                if kind == "tag":
                    tags.append(row)
                elif kind == "feat":
                    feats.append(row)
                elif kind == "event":
                    try:
                        async with conn.transaction():     # a savepoint: a refused row rolls back alone
                            await store_event(conn, *row)
                    except (psycopg.DataError, psycopg.IntegrityError) as exc:
                        _rejected(tp, r.offset, f"{type(exc).__name__}: {exc}")
            await write_batch(conn, TAG_SQL, "tag_1s", tags)
            await write_batch(conn, FEAT_SQL, "feat_1s", feats)
            newest = max(r.timestamp for r in records)
            await conn.execute("""INSERT INTO sink_offsets VALUES (%s,%s,%s,%s)
                ON CONFLICT (topic,partition_id) DO UPDATE SET next_offset=EXCLUDED.next_offset,
                    max_ts=GREATEST(coalesce(sink_offsets.max_ts, 0), EXCLUDED.max_ts)""",
                (tp.topic, tp.partition, records[-1].offset + 1, newest))


async def _fetch(cons):
    """One getmany. A fetch that cannot be decoded (unsupported codec, corrupt batch) raises without naming its partition:
    each assigned partition is then fetched on its own, the good ones' records are returned, and only the partition that
    fails again is moved one record past its position (counted in fetch_errors) — no other partition loses a record."""
    try:
        return await cons.getmany(timeout_ms=500, max_records=2000)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 — see docstring
        state["fetch_errors"] += 1
        state["fetch_last_error"] = repr(exc)[:200]
        log.error("fetch failed (%s); probing each partition", exc)
    batches = {}
    for tp in sorted(cons.assignment()):
        try:
            batches.update(await cons.getmany(tp, timeout_ms=500, max_records=2000))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            position = await cons.position(tp)
            cons.seek(tp, position + 1)
            state["fetch_last_error"] = f"{tp.topic}/{tp.partition}/{position}: {exc!r}"[:200]
            log.error("%s/%s: record at %s cannot be decoded (%s); stepping past it", tp.topic, tp.partition, position, exc)
    return batches


async def run():
    conn = await connect_db()
    cons = await make_consumer(TOPICS, group="connect-sink", from_latest=False, auto_commit=False)
    state["kafka"] = True
    try:
        while True:
            batches = await _fetch(cons)
            if not batches:
                continue
            while True:
                try:
                    await store_records(conn, batches)
                    state["db"] = True
                    state["last_write"] = time.time()
                    break
                except (psycopg.OperationalError, psycopg.InterfaceError):
                    state["db"] = False
                    state["errors"] += 1
                    await conn.close()
                    conn = await connect_db()
            try:
                await cons.commit({tp: records[-1].offset + 1 for tp, records in batches.items() if records})
            except CommitFailedError:
                # DB offsets suppress duplicates after Kafka partition reassignment.
                log.warning("rebalance before offset commit; DB checkpoint retained")
    finally:
        state.update(db=False, kafka=False)
        await cons.stop()
        await conn.close()


app = make_app("connect-sink (L5: Kafka -> TimescaleDB)", reg,
               lambda: {**state, "ok": state["kafka"] and state["db"] and not state.get("consumer_dead", False)})


def _watch(task):
    stop_after_loop_end(task, state, log)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(run()).add_done_callback(_watch)


@app.get("/api/sink/stats")
def stats():
    return dict(state)
