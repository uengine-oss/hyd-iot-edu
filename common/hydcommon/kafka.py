"""aiokafka helpers with retry-until-broker-ready (students start containers in any order)."""
import asyncio
import json
import os
import logging
import time
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

log = logging.getLogger("hydcommon.kafka")
ERROR_WINDOW_S = 60.0


class Delivery:
    """What the broker did with the records a service sent — the producer's send() only queues a record and returns a
    future the broker answers later, so a refused or timed-out record is visible only here. Every service that sends
    through this counts the same way and shows `health()` in /healthz; `healthy()` is false for ERROR_WINDOW_S after a
    failure (a broken Kafka leg must not look healthy)."""

    def __init__(self):
        self.delivered = 0
        self.failed = 0
        self.last_error: str | None = None
        self.last_error_at: float | None = None

    async def send(self, producer, topic: str, value, key=None) -> None:
        try:
            future = await producer.send(topic, value=value, key=key)
        except Exception as exc:  # noqa: BLE001 — refused before queueing (size, serialisation, buffer): counted, then raised
            self._failed(topic, exc)
            raise
        future.add_done_callback(lambda f: self._done(topic, f))

    def _done(self, topic, future) -> None:
        if future.cancelled():
            self._failed(topic, asyncio.CancelledError("send cancelled"))
        elif future.exception() is not None:
            self._failed(topic, future.exception())
        else:
            self.delivered += 1

    def _failed(self, topic, exc) -> None:
        self.failed += 1
        self.last_error = f"{topic}: {type(exc).__name__}: {exc}"[:300]
        self.last_error_at = time.time()
        log.warning("kafka record to %s not delivered: %s", topic, self.last_error)

    def healthy(self, now: float | None = None) -> bool:
        return self.last_error_at is None or (time.time() if now is None else now) - self.last_error_at >= ERROR_WINDOW_S

    def health(self) -> dict:
        return {"kafka_delivered": self.delivered, "kafka_failed": self.failed, "kafka_last_error": self.last_error}


def decode_value(b):
    """Never raise on a bad record: a malformed or non-object value becomes {"_raw": text} so the consumer
    can reject it (schema check) instead of dying inside `async for`."""
    if b is None:
        return {}
    text = b.decode("utf-8", errors="replace")
    try:
        v = json.loads(text)
    except json.JSONDecodeError:
        return {"_raw": text}
    return v if isinstance(v, dict) else {"_raw": text}


def replay_verdict(offset: int, timestamp_ms: int, position: int | None, max_timestamp_ms: int | None) -> str:
    """Is a record new, already processed, or from a topic that was recreated? A consumer that keeps its own checkpoint
    (detector SQLite, connect-sink sink_offsets) stores, per partition, the next offset to process and the newest record
    timestamp it processed. A record below that offset is a replay — unless it is newer than everything processed before:
    then the offsets restarted (the topic was deleted and created again, e.g. a reset Redpanda volume or the console), and
    skipping it would silently drop every new record. 'new' | 'seen' | 'recreated'."""
    if position is None or offset >= position:
        return 'new'
    if max_timestamp_ms is not None and timestamp_ms > max_timestamp_ms:
        return 'recreated'
    return 'seen'


def bootstrap() -> str:
    return os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")


async def producer() -> AIOKafkaProducer:
    while True:
        p = AIOKafkaProducer(bootstrap_servers=bootstrap(),
                             value_serializer=lambda v: json.dumps(v).encode(),
                             key_serializer=lambda k: k.encode() if isinstance(k, str) else k)
        try:
            await p.start()
            return p
        except asyncio.CancelledError:
            await p.stop()
            raise
        except Exception as e:  # broker not ready yet
            await p.stop()
            log.warning("kafka producer not ready (%s), retrying", e)
            await asyncio.sleep(2)


async def consumer(topics: list[str], group: str, from_latest: bool = True, auto_commit: bool = True,
                   raw_values: bool = False) -> AIOKafkaConsumer:
    while True:
        c = AIOKafkaConsumer(*topics, bootstrap_servers=bootstrap(), group_id=group,
                             auto_offset_reset="latest" if from_latest else "earliest",
                             enable_auto_commit=auto_commit,
                             value_deserializer=None if raw_values else decode_value,
                             key_deserializer=lambda b: b.decode(errors="replace") if b else None)
        try:
            await c.start()
            return c
        except asyncio.CancelledError:
            await c.stop()
            raise
        except Exception as e:
            await c.stop()
            log.warning("kafka consumer not ready (%s), retrying", e)
            await asyncio.sleep(2)
