"""connect-sink (L5): Kafka -> TimescaleDB (the JDBC Sink role, upsert mode).

  plant.tag    -> tag_1s   (batched inserts)
  feat.1s      -> feat_1s
  alerts       -> alerts   (RAISE insert / CLEAR update by alert_id)
  action.cmd   -> actions  (insert)
  plant.status -> actions  (ACK: cmdId/result -> ack_result/ack_reason/ack_at)
  audit        -> audit
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone

import psycopg
from aiokafka.errors import CommitFailedError
from psycopg.types.json import Jsonb

from hydcommon import topics
from hydcommon.kafka import consumer as make_consumer
from hydcommon.metrics import Registry
from hydcommon.service import make_app
from hydcommon.timeutil import parse_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("connect-sink")
PG_DSN = os.getenv("PG_DSN", "postgresql://hyd:hyd@timescaledb:5432/hyd")

reg = Registry()
c_rows = reg.counter("sink_rows_total", "rows written by table")
g_lag = reg.gauge("sink_batch_age_seconds", "age of oldest row in current batch")
state = {"db": False, "kafka": False, "rows": 0, "last_write": None, "errors": 0}

TOPICS = [topics.K_TAG, topics.K_FEAT, topics.K_ALERTS, topics.K_CMD, topics.K_STATUS, topics.K_AUDIT]


def ts(s, fallback_ms=None) -> datetime:
    if s:
        try:
            return parse_iso(s)
        except ValueError:
            pass
    if fallback_ms:
        return datetime.fromtimestamp(fallback_ms / 1000, tz=timezone.utc)
    return datetime.now(timezone.utc)


async def connect_db():
    while True:
        try:
            conn = await psycopg.AsyncConnection.connect(PG_DSN, autocommit=True, connect_timeout=5)
            await conn.execute("""CREATE TABLE IF NOT EXISTS sink_offsets (
                topic TEXT NOT NULL, partition_id INTEGER NOT NULL, next_offset BIGINT NOT NULL,
                PRIMARY KEY(topic, partition_id))""")
            state["db"] = True
            return conn
        except Exception as e:  # noqa: BLE001
            state["db"] = False
            log.warning("db not ready (%s), retrying", e)
            await asyncio.sleep(2)


async def write_batch(conn, tag_rows, feat_rows):
    if tag_rows:
        async with conn.cursor() as cur:
            await cur.executemany("INSERT INTO tag_1s (time, asset, name, value) VALUES (%s, %s, %s, %s)", tag_rows)
        c_rows.inc(len(tag_rows), table="tag_1s")
    if feat_rows:
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO feat_1s (time, asset, sensor, mean, rms, slope, score) VALUES (%s, %s, %s, %s, %s, %s, %s)", feat_rows)
        c_rows.inc(len(feat_rows), table="feat_1s")
    state["rows"] += len(tag_rows) + len(feat_rows)


async def handle_event(conn, topic, v, rec_ms):
    async with conn.cursor() as cur:
        if topic == topics.K_ALERTS:
            t = ts(v.get("t"), rec_ms)
            if v.get("state") == "RAISE":
                await cur.execute(
                    """INSERT INTO alerts (alert_id, asset, pattern, severity, state, raised_at, evidence)
                       VALUES (%s, %s, %s, %s, 'RAISE', %s, %s)
                       ON CONFLICT (alert_id) DO UPDATE SET state='RAISE', raised_at=EXCLUDED.raised_at, evidence=EXCLUDED.evidence""",
                    (v["alertId"], v.get("asset"), v.get("pattern"), v.get("severity"), t, Jsonb(v.get("evidence") or {})))
            else:
                await cur.execute(
                    """INSERT INTO alerts (alert_id, asset, pattern, severity, state, cleared_at, evidence)
                       VALUES (%s, %s, %s, %s, 'CLEAR', %s, %s)
                       ON CONFLICT (alert_id) DO UPDATE SET state='CLEAR', cleared_at=EXCLUDED.cleared_at""",
                    (v["alertId"], v.get("asset"), v.get("pattern"), v.get("severity"), t, Jsonb(v.get("evidence") or {})))
            c_rows.inc(table="alerts")
        elif topic == topics.K_CMD:
            await cur.execute(
                """INSERT INTO actions (cmd_id, incident, asset, actions, approved_by, issued_at, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (cmd_id) DO UPDATE SET incident=EXCLUDED.incident, asset=EXCLUDED.asset,
                       actions=EXCLUDED.actions, approved_by=EXCLUDED.approved_by,
                       issued_at=EXCLUDED.issued_at, expires_at=EXCLUDED.expires_at""",
                (v["cmdId"], v.get("incident"), v.get("asset"), Jsonb(v.get("actions") or []), v.get("approvedBy"),
                 ts(v.get("issuedAt"), rec_ms), ts(v.get("expiresAt"), rec_ms)))
            c_rows.inc(table="actions")
        elif topic == topics.K_STATUS:
            if v.get("cmdId") and v.get("result"):
                await cur.execute(
                    """INSERT INTO actions (cmd_id, ack_result, ack_reason, ack_at) VALUES (%s,%s,%s,%s)
                       ON CONFLICT (cmd_id) DO UPDATE SET ack_result=EXCLUDED.ack_result,
                       ack_reason=EXCLUDED.ack_reason, ack_at=EXCLUDED.ack_at WHERE actions.ack_result IS NULL""",
                    (v["cmdId"], v["result"], v.get("reason"), ts(v.get("t"), rec_ms)))
        elif topic == topics.K_AUDIT:
            await cur.execute(
                "INSERT INTO audit (time, incident, actor, event, detail) VALUES (%s, %s, %s, %s, %s)",
                (ts(v.get("t"), rec_ms), v.get("incident"), v.get("actor"), v.get("event"), Jsonb(v.get("detail") or {})))
            c_rows.inc(table="audit")
    state["rows"] += 1


async def store_records(conn, batches):
    """Rows and source offsets share one DB transaction, including restart/rebalance replay."""
    async with conn.transaction():
        for tp, records in batches.items():
            if not records:
                continue
            cur = await conn.execute("SELECT next_offset FROM sink_offsets WHERE topic=%s AND partition_id=%s",
                                     (tp.topic, tp.partition))
            row = await cur.fetchone()
            next_offset = row[0] if row else -1
            tags, feats = [], []
            for r in records:
                if r.offset < next_offset:
                    continue
                v = r.value
                try:
                    if not isinstance(v, dict) or "_raw" in v:
                        raise ValueError("malformed record")
                    if tp.topic == topics.K_TAG:
                        tags.append((ts(v.get("t"), r.timestamp), v["asset"], v["name"], float(v["v"])))
                    elif tp.topic == topics.K_FEAT:
                        values = [float(v[k]) if v.get(k) is not None else None for k in ("mean", "rms", "slope", "score")]
                        feats.append((ts(v.get("t"), r.timestamp), v["asset"], v["sensor"], *values))
                    else:
                        # A bad event rolls back only its savepoint, not valid neighbours.
                        async with conn.transaction():
                            await handle_event(conn, tp.topic, v, r.timestamp)
                except (ValueError, TypeError, KeyError, psycopg.DataError, psycopg.IntegrityError) as exc:
                    state["errors"] += 1
                    log.warning("invalid record %s/%s/%s (%s)", tp.topic, tp.partition, r.offset, type(exc).__name__)
            await write_batch(conn, tags, feats)
            await conn.execute("""INSERT INTO sink_offsets VALUES (%s,%s,%s)
                ON CONFLICT (topic,partition_id) DO UPDATE SET next_offset=GREATEST(sink_offsets.next_offset,EXCLUDED.next_offset)""",
                (tp.topic, tp.partition, records[-1].offset + 1))


async def run():
    conn = await connect_db()
    cons = await make_consumer(TOPICS, group="connect-sink", from_latest=False, auto_commit=False)
    state["kafka"] = True
    try:
        while True:
            batches = await cons.getmany(timeout_ms=500, max_records=2000)
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
    """If the consume loop ever exits, /healthz reports it (503) instead of looking healthy while doing nothing."""
    state["consumer_dead"] = True
    state["consumer_error"] = repr(task.exception()) if not task.cancelled() and task.exception() else "exited"
    log.error("consumer task ended: %s", state["consumer_error"])


@app.on_event("startup")
async def _startup():
    asyncio.create_task(run()).add_done_callback(_watch)


@app.get("/api/sink/stats")
def stats():
    return dict(state)
