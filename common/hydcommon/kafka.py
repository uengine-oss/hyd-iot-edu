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


#: How long the whole probe may take (every partition: its end offset, then its next record or the decode error) before it
#: gives up loudly. A fetch can be slow without anything being wrong: one broker serves one fetch request of a consumer at a
#: time, the request in flight for an idle partition waits fetch_max_wait_ms (500 ms) for data, and an overloaded PC adds seconds.
PROBE_S = 30.0


class PoisonProbeError(RuntimeError):
    """Within the probe time the broker did not answer whether a partition's next record can be read."""


async def step_over_poison(cons, probe_s: float | None = None) -> list[tuple]:
    """After a consume loop ended on a fetch that cannot be decoded (unsupported codec, corrupt batch — the error does not
    name its partition): fetch each assigned partition on its own. Only a partition that fails again is moved one record past
    its position and that position is committed; a partition that reads is put back where it was, so the loop reads the
    probed record again and no healthy partition loses one (before, every assigned partition was stepped by one: a poison
    record on `alerts` dropped an unrelated command). → [(partition, skipped offset, error text)] of the stepped ones.

    Whether a partition holds the bad record is decided from what the broker answers, never from a timer: a partition with
    no record at its position (position = end offset) cannot hold it; one with a record is fetched until the record or its
    error comes back. Before, an answer that took longer than one 500 ms fetch counted as «reads fine» — nothing was stepped
    and the loop met the same record again on its next start. No answer within probe_s (default PROBE_S) raises
    PoisonProbeError naming the partition and offset it was waiting for (that partition is put back where it was)."""
    probe_s = PROBE_S if probe_s is None else probe_s
    stepped, waiting = [], None
    try:
        async with asyncio.timeout(probe_s):
            for tp in sorted(cons.assignment()):
                waiting = (tp, None, None)
                position = await cons.position(tp)
                waiting = (tp, position, None)
                end = (await cons.end_offsets([tp]))[tp]
                waiting = (tp, position, end)
                if position >= end:
                    continue                  # nothing waits on this partition — the record that cannot be read is not here
                while True:
                    try:
                        got = await cons.getmany(tp, timeout_ms=500, max_records=1)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:  # noqa: BLE001 — this partition's next record is the one that cannot be read
                        cons.seek(tp, position + 1)
                        await cons.commit({tp: position + 1})
                        stepped.append((tp, position, repr(exc)[:200]))
                        log.error("%s/%s: record at %s cannot be decoded (%s); stepping past it", tp.topic, tp.partition, position, exc)
                        break
                    if got:
                        cons.seek(tp, position)   # it reads — put it back so the loop handles that record
                        break
                waiting = None
    except TimeoutError:
        tp, position, end = waiting
        if position is not None:
            cons.seek(tp, position)
        raise PoisonProbeError(f"{tp.topic}/{tp.partition}: the broker did not answer within {probe_s:g} s whether the record at "
                               f"{position} (end {end}) can be read") from None
    return stepped


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
