"""aiokafka helpers with retry-until-broker-ready (students start containers in any order)."""
import asyncio
import json
import os
import logging
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

log = logging.getLogger("hydcommon.kafka")


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
        except Exception as e:  # broker not ready yet
            await p.stop()
            log.warning("kafka producer not ready (%s), retrying", e)
            await asyncio.sleep(2)


async def consumer(topics: list[str], group: str, from_latest: bool = True, auto_commit: bool = True) -> AIOKafkaConsumer:
    while True:
        c = AIOKafkaConsumer(*topics, bootstrap_servers=bootstrap(), group_id=group,
                             auto_offset_reset="latest" if from_latest else "earliest",
                             enable_auto_commit=auto_commit,
                             value_deserializer=decode_value,
                             key_deserializer=lambda b: b.decode(errors="replace") if b else None)
        try:
            await c.start()
            return c
        except Exception as e:
            await c.stop()
            log.warning("kafka consumer not ready (%s), retrying", e)
            await asyncio.sleep(2)
