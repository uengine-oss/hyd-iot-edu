"""connect-ingest (L3, DMZ): one-way replication OT MQTT -> Kafka.

  plant/{a}/tag/{name}   -> plant.tag     {"asset","name","t","v","q"}
  plant/{a}/wave/{sensor}-> plant.wave    {"asset","sensor","t0","hz","v":[...]}
  plant/{a}/status       -> plant.status  (payload, asset from the topic)
Kafka key = asset key (hyd01) so per-asset order is preserved (v3 5.4).
Every message is checked against its contract (hydcommon.schemas *_record — the same check the detector and connect-sink
apply on the Kafka side): only known assets, DAQ tags, ISO times with a zone and finite numbers go on; anything else is
counted as malformed with its reason (/healthz `malformed`, `last_malformed`) and dropped here.
Nothing flows back: this container never publishes to MQTT (the broker rules let it subscribe only).
"""
import asyncio
import json
import logging
import time

from hydcommon import schemas, topics
from hydcommon.kafka import Delivery, producer as make_producer
from hydcommon.metrics import Registry
from hydcommon.mqtt import Link
from hydcommon.service import make_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("connect-ingest")

reg = Registry()
c_msgs = reg.counter("ingest_messages_total", "messages replicated OT->IT by kafka topic")
g_age = reg.gauge("ingest_last_event_age_seconds", "seconds since last accepted MQTT message (-1: none yet)")
g_queue = reg.gauge("ingest_queue_depth", "messages waiting for Kafka")

QUEUE_MAX = 20000
state = {"last_ts": 0.0, "count": 0, "dropped": 0, "malformed": 0, "last_malformed": None, "kafka": False}
delivery = Delivery()
queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
loop: asyncio.AbstractEventLoop | None = None


def to_kafka(topic: str, payload: bytes):
    """(kafka topic, key, record) for one OT message; raises schemas.RecordError for a message outside its contract."""
    parsed = topics.parse_mqtt(topic)
    if not parsed:
        raise schemas.RecordError(f"topic {topic!r} is not plant/<known asset>/…")
    asset, kind, rest = parsed
    try:
        body = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise schemas.RecordError("payload is not UTF-8 JSON") from None
    key = topics.asset_key(asset)
    if kind == "tag" and rest:
        return topics.K_TAG, key, schemas.tag_record(asset, rest, body)
    if kind == "wave" and rest:
        return topics.K_WAVE, key, schemas.wave_record(asset, rest, body)
    if kind == "status" and rest is None:
        return topics.K_STATUS, key, schemas.status_record(asset, body)
    raise schemas.RecordError(f"topic {topic!r} is not a replicated kind (tag · wave · status)")


def _on_connect(client):
    client.subscribe([("plant/+/tag/+", 0), ("plant/+/wave/+", 0), ("plant/+/status", 1)])


def _on_message(client, msg):
    try:
        item = to_kafka(msg.topic, msg.payload)
    except schemas.RecordError as exc:
        state["malformed"] += 1
        state["last_malformed"] = f"{msg.topic}: {exc}"[:200]
        return
    state["last_ts"] = time.time()
    loop.call_soon_threadsafe(_enqueue, item)


link = Link("connect-ingest", _on_message, on_connect=_on_connect)


def _enqueue(item):
    """Runs on the loop thread; drop (and count) instead of raising when Kafka falls behind."""
    if queue.full():
        state["dropped"] += 1
        return
    queue.put_nowait(item)


async def pump(prod):
    """Send queued records in order; what the broker did with each is counted by `delivery` (health)."""
    while True:
        ktopic, key, value = await queue.get()
        try:
            await delivery.send(prod, ktopic, value=value, key=key)
            c_msgs.inc(topic=ktopic)
            state["count"] += 1
        except Exception:  # noqa: BLE001 — refused before queueing; delivery counted it and its reason (health)
            await asyncio.sleep(0.5)


async def run():
    prod = await make_producer()
    state["kafka"] = True
    log.info("kafka producer ready")
    await pump(prod)


async def age_updater():
    while True:
        g_age.set(round(time.time() - state["last_ts"], 1) if state["last_ts"] else -1)
        g_queue.set(queue.qsize())
        await asyncio.sleep(1)


def health() -> dict:
    """/healthz body. `ok` (-> 200/503 in hydcommon.service) holds only while the MQTT link is up without a recent handler
    failure, the Kafka producer runs, the broker accepted the recent records and the pump task is alive — the agent's
    data-trust check (mcp_prom.freshness) and the compose healthcheck both read this, so a broken leg must not look healthy."""
    return {"ok": link.healthy() and state["kafka"] and delivery.healthy() and not state.get("pump_dead", False),
            **link.health(), **delivery.health(), "kafka": state["kafka"],
            "pump_dead": state.get("pump_dead", False), "pump_error": state.get("pump_error"), "replicated": state["count"],
            "dropped": state["dropped"], "malformed": state["malformed"], "last_malformed": state["last_malformed"],
            "queue": queue.qsize(), "last_event_age_s": round(time.time() - state["last_ts"], 1) if state["last_ts"] else None}


app = make_app("connect-ingest (L3 DMZ: OT MQTT -> Kafka)", reg, health)


def _watch(task):
    """If the Kafka pump ever exits, /healthz reports it (503) instead of looking healthy while replicating nothing."""
    state["pump_dead"] = True
    state["kafka"] = False
    state["pump_error"] = repr(task.exception()) if not task.cancelled() and task.exception() else "exited"
    log.error("kafka pump task ended: %s", state["pump_error"])


@app.on_event("startup")
async def _startup():
    global loop
    loop = asyncio.get_running_loop()
    link.start()
    asyncio.create_task(run()).add_done_callback(_watch)
    asyncio.create_task(age_updater())


@app.get("/api/ingest/stats")
def stats():
    return health()
