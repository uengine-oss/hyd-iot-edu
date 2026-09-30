"""connect-ingest (L3, DMZ): one-way replication OT MQTT -> Kafka.

  plant/{a}/tag/{name}   -> plant.tag     {"asset","name","t","v","q"}
  plant/{a}/wave/{sensor}-> plant.wave    {"asset","sensor","t0","hz","v":[...]}
  plant/{a}/status       -> plant.status  (payload as-is, asset guaranteed)
Kafka key = asset key (hyd01) so per-asset order is preserved (v3 5.4).
Nothing flows back: this container never publishes to MQTT.
"""
import asyncio
import json
import logging
import os
import time

from hydcommon import topics
from hydcommon.kafka import producer as make_producer
from hydcommon.metrics import Registry
from hydcommon.mqtt import make_client
from hydcommon.service import make_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("connect-ingest")

reg = Registry()
c_msgs = reg.counter("ingest_messages_total", "messages replicated OT->IT by kafka topic")
g_age = reg.gauge("ingest_last_event_age_seconds", "seconds since last MQTT message")
g_queue = reg.gauge("ingest_queue_depth", "messages waiting for Kafka")

state = {"mqtt": False, "kafka": False, "last_ts": 0.0, "count": 0}
queue: asyncio.Queue = asyncio.Queue(maxsize=20000)
loop: asyncio.AbstractEventLoop | None = None


def to_kafka(topic: str, payload: bytes):
    parsed = topics.parse_mqtt(topic)
    if not parsed:
        return None
    key, kind, rest = parsed
    asset = topics.asset_id(key)
    try:
        body = json.loads(payload.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if kind == "tag" and rest:
        return topics.K_TAG, key, {"asset": asset, "name": rest, "t": body.get("t"), "v": body.get("v"), "q": body.get("q", "good")}
    if kind == "wave" and rest:
        return topics.K_WAVE, key, {"asset": asset, "sensor": rest, "t0": body.get("t0"), "hz": body.get("hz"), "v": body.get("v", [])}
    if kind == "status":
        body.setdefault("asset", asset)
        return topics.K_STATUS, key, body
    return None


def _on_connect(client, userdata, flags, rc, properties=None):
    state["mqtt"] = True
    client.subscribe([("plant/+/tag/+", 0), ("plant/+/wave/+", 0), ("plant/+/status", 1)])
    log.info("subscribed to OT topics (rc=%s)", rc)


def _on_message(client, userdata, msg):
    item = to_kafka(msg.topic, msg.payload)
    if not item or loop is None:
        return
    state["last_ts"] = time.time()
    loop.call_soon_threadsafe(_enqueue, item)


def _enqueue(item):
    """Runs on the loop thread; drop (and count) instead of raising when Kafka falls behind."""
    if queue.full():
        state["dropped"] = state.get("dropped", 0) + 1
        return
    queue.put_nowait(item)


async def pump():
    prod = await make_producer()
    state["kafka"] = True
    log.info("kafka producer ready")
    while True:
        ktopic, key, value = await queue.get()
        try:
            await prod.send(ktopic, value=value, key=key)
            c_msgs.inc(topic=ktopic)
            state["count"] += 1
        except Exception as e:  # noqa: BLE001
            log.warning("send failed: %s", e)
            await asyncio.sleep(0.5)


async def age_updater():
    while True:
        g_age.set(round(time.time() - state["last_ts"], 1) if state["last_ts"] else -1)
        g_queue.set(queue.qsize())
        await asyncio.sleep(1)


app = make_app("connect-ingest (L3 DMZ: OT MQTT -> Kafka)", reg,
               lambda: {"mqtt": state["mqtt"], "kafka": state["kafka"], "replicated": state["count"],
                        "last_event_age_s": round(time.time() - state["last_ts"], 1) if state["last_ts"] else None})


@app.on_event("startup")
async def _startup():
    global loop
    loop = asyncio.get_running_loop()
    client = make_client("connect-ingest")
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.loop_start()
    asyncio.create_task(pump())
    asyncio.create_task(age_updater())


@app.get("/api/ingest/stats")
def stats():
    return {**state, "queue": queue.qsize()}
