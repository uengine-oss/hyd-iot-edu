"""detector (L4): Flink stand-in. plant.tag/plant.wave/plant.status -> feat.1s + alerts (RAISE/CLEAR).

Per asset: one observation store (pattern_runtime) feeds the Neo4j TESTS/clearRule/hold definitions on each TS1 tick, the
features (TS1 slope, z-score anomaly score — the autoencoder slot) and the authoritative PLC trip watch. Active alerts pin
their definition; SQLite checkpoints and an outbox preserve alert identity across restart.
Clocks: pattern hold/clear windows and slopes are measured in simulated seconds = event epoch seconds * TIME_SCALE; sample
validity (missing · stale · future) is wall seconds (observations).
Records: each one is checked against its contract (hydcommon.schemas — Kafka is reachable from the host, so the ingest's
check is not the only gate). A record outside it is counted and logged with its coordinates; for a known asset · tag it
also invalidates that observation (the hold is interrupted, it is never filled in). A record whose processing still raises
is counted the same way and /healthz is 503 for a minute — one record never stops detection.
Checkpoint: written at once when an alert is emitted (with its outbox entry) and otherwise every CHECKPOINT_S together with
the Kafka commit; a restart replays at most that much, which the stored offsets and the restored runtime absorb.
"""
import asyncio
import logging
import os
import time
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass, field

from aiokafka.structs import TopicPartition
from fastapi import HTTPException

from hydcommon import graphdb, schemas, topics
from hydcommon.daq_contract import OBSERVATION_GRACE_S, TAGS, profile_from_env
from hydcommon.kafka import Delivery, consumer as make_consumer, producer as make_producer, replay_verdict
from hydcommon.metrics import Registry
from hydcommon.service import make_app
from hydcommon.timeutil import parse_iso, time_scale
from . import cep, features
from .pattern_runtime import PatternRuntime
from .pattern_source import read_patterns
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("detector")
TIME_SCALE = time_scale()
DAQ_PROFILE = profile_from_env()
STATE_PATH = os.getenv('DETECTOR_STATE_PATH', '/data/detector.sqlite3')
CHECKPOINT_S = 5.0
ERROR_WINDOW_S = 60.0
runtime = PatternRuntime(None, DAQ_PROFILE, TIME_SCALE, OBSERVATION_GRACE_S)
store = None
pending_alerts = []
catalog_status = {'ready': False, 'error': 'NOT_LOADED', 'checked_at': None, 'applied_at': None}
mutation_lock = asyncio.Lock()
refresh_lock = asyncio.Lock()

reg = Registry()
c_alerts = reg.counter("detector_alerts_total", "alerts emitted by pattern/state")
g_score = reg.gauge("detector_anomaly_score", "anomaly score by asset")
g_ts1 = reg.gauge("detector_ts1", "latest TS1 by asset")
g_event_time = reg.gauge('detector_input_event_timestamp_seconds', 'last accepted source event timestamp by asset/tag')
g_valid = reg.gauge('detector_pattern_inputs_valid', 'required inputs valid at last TS1 evaluation; inspect source event timestamps for current age')


@dataclass
class AssetState:
    asset: str
    trip_state: cep.TripState = field(default_factory=cep.TripState)
    score: float | None = None
    plc_state: str = "UNKNOWN"


state = {"kafka": False, "tags": 0, "waves": 0, "statuses": 0, "alerts": 0, "rejected": 0, "last_rejected": None,
         "record_errors": 0, "last_record_error": None, "last_record_error_at": None, "offset_resets": 0}
delivery = Delivery()
assets: dict[str, AssetState] = {}


def get(asset: str) -> AssetState:
    if asset not in topics.ASSETS:
        raise schemas.RecordError(f"asset {asset!r} is not one of {list(topics.ASSETS)}")
    if asset not in assets:
        assets[asset] = AssetState(asset)
    return assets[asset]


def samples(asset: str) -> dict:
    return runtime.asset(asset).observations.samples


def value(asset: str, tag: str):
    sample = samples(asset).get(tag)
    return sample['value'] if sample and sample.get('valid') else None


def sync_quality_gauges(asset: str):
    for code, run in runtime.asset(asset).runs.items():
        g_valid.set(int(run.quality.get('status') == 'VALID'), asset=asset, pattern=code)


async def on_tag(prod, v: dict):
    a = get(v["asset"])
    name, val, t_iso = v["name"], v["v"], v["t"]
    at = parse_iso(t_iso).timestamp()
    status, events = runtime.observe(a.asset, name, val, at, v['q'], now=time.time())
    sync_quality_gauges(a.asset)
    if status != 'valid':
        return
    g_event_time.set(at, asset=a.asset, tag=name)
    if name != "TS1":
        return
    observations = runtime.asset(a.asset).observations
    problems = observations.problems(tuple(features.NORMAL), at, time.time())
    a.score = None if problems else features.anomaly_score({sig: value(a.asset, sig) for sig in features.NORMAL})
    if a.score is not None:
        g_score.set(a.score, asset=a.asset)
    g_ts1.set(val, asset=a.asset)
    ts1_slope, vs1_slope = runtime.slope(a.asset, 'TS1'), runtime.slope(a.asset, 'VS1')
    await delivery.send(prod, topics.K_FEAT, key=topics.asset_key(a.asset), value={
        "asset": a.asset, "t": t_iso, "sensor": "TS1", "mean": val, "rms": None,
        "slope": None if ts1_slope is None else round(ts1_slope, 5), "score": a.score})
    for ev in events:
        # Keep the consumers' evidence field names (InputData.variable ts1 · ts1_slope …) next to the definition's own values.
        ev['evidence'].update(ts1=value(a.asset, 'TS1'), ce=value(a.asset, 'CE'), ps1=value(a.asset, 'PS1'),
                              fs1=value(a.asset, 'FS1'), load=value(a.asset, 'LoadSP'), vs1=value(a.asset, 'VS1'),
                              ts1_slope=ts1_slope, vs1_slope=vs1_slope, score=a.score)
        emit_alert(ev)


async def on_wave(prod, v: dict):
    get(v["asset"])
    f = features.wave_features(v["v"])
    await delivery.send(prod, topics.K_FEAT, key=topics.asset_key(v["asset"]), value={
        "asset": v["asset"], "t": v["t0"], "sensor": v["sensor"], "mean": f["mean"], "rms": f["rms"], "slope": f["slope"], "score": None})


def on_status(v: dict):
    a = get(v["asset"])
    at = parse_iso(v['t']).timestamp()
    now = time.time()
    status, _ = runtime.observe(a.asset, 'PLC_STATE', v['state'], at, now=now)
    if status == 'ignored':
        return
    observations = runtime.asset(a.asset).observations
    if status != 'valid' or observations.problems(('PLC_STATE',), at, now):
        a.plc_state = 'UNKNOWN'
        return
    a.plc_state = v['state']
    ev = cep.trip_alert(a.trip_state, a.asset, tripped=(a.plc_state == "TRIP"), t_iso=v["t"], reason=v.get("trip"),
                        names=runtime.names)
    if ev:
        emit_alert(ev)


def emit_alert(ev: dict):
    pending_alerts.append(ev)
    c_alerts.inc(pattern=ev["pattern"], state=ev["state"])
    state["alerts"] += 1
    log.info("ALERT %s %s %s evidence=%s", ev["state"], ev["pattern"], ev["alertId"], ev.get("evidence"))


def checkpoint(offsets=None):
    store.save(dict(runtime=runtime.snapshot(), trips={a.asset: asdict(a.trip_state) for a in assets.values()}),
               offsets, pending_alerts)
    pending_alerts.clear()


def fetch_catalog():
    with graphdb.connect(connection_timeout=3, connection_acquisition_timeout=5, max_transaction_retry_time=0) as driver:
        return read_patterns(driver)


async def refresh_catalog():
    async with refresh_lock:
        return await _refresh_catalog()


async def _refresh_catalog():
    try:
        rows, names = await asyncio.to_thread(fetch_catalog)
        async with mutation_lock:
            runtime.replace(rows, names)
            catalog_status.update(ready=True, error=None, checked_at=time.time(), applied_at=time.time())
            if store is not None:
                checkpoint()
        return True
    except Exception as exc:  # noqa: BLE001 — shown in /healthz (patterns.error, 503) and the log; held alerts stay pinned
        async with mutation_lock:
            runtime.source_failed()
            catalog_status.update(ready=False, error=f'{type(exc).__name__}: {exc}', checked_at=time.time())
        log.warning('pattern source unavailable/rejected: %s', catalog_status['error'])
        return False


async def poll_catalog():
    while True:
        await asyncio.sleep(15)
        await refresh_catalog()


async def drain_alerts(prod):
    for seq, event in store.pending():
        await prod.send_and_wait(topics.K_ALERTS, key=topics.asset_key(event['asset']), value=event)
        store.delivered(seq)  # a crash before this can resend the same alertId/state


async def _stop_refresh(task):
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def restore(saved: dict) -> None:
    """Runtime (raised alerts with their definitions) and trip states from the last checkpoint. A checkpoint written under
    another TIME_SCALE / DAQ profile / grace is refused: its holds were measured on another clock (RUNBOOK: a separate
    DETECTOR_STATE_PATH per time scale)."""
    global runtime
    if saved.get('runtime'):
        restored = PatternRuntime.restore(saved['runtime'])
        if (restored.profile, restored.time_scale, restored.grace_s) != (DAQ_PROFILE, TIME_SCALE, OBSERVATION_GRACE_S):
            raise RuntimeError('persisted detector clock/reporting contract differs from environment; explicit state migration required')
        runtime = restored
    for asset, trip in saved.get('trips', {}).items():
        get(asset).trip_state = cep.TripState(**trip)


def _reject(rec, reason: str, asset=None, name=None):
    state["rejected"] += 1
    state["last_rejected"] = f"{rec.topic}/{rec.partition}/{rec.offset}: {reason}"[:200]
    log.warning("rejected record %s", state["last_rejected"])
    if asset in topics.ASSETS and (name in TAGS or name == 'PLC_STATE'):
        runtime.invalidate(asset, name, 'INVALID_RECORD')


async def process(prod, rec) -> None:
    """One Kafka record: check it, then let the runtime see it."""
    v = rec.value
    raw = v if isinstance(v, dict) else {}
    try:
        if rec.topic == topics.K_TAG:
            v = schemas.tag_record(raw.get('asset'), raw.get('name'), v)
            state['tags'] += 1
            await on_tag(prod, v)
        elif rec.topic == topics.K_WAVE:
            v = schemas.wave_record(raw.get('asset'), raw.get('sensor'), v)
            state['waves'] += 1
            await on_wave(prod, v)
        elif rec.topic == topics.K_STATUS:
            v = schemas.status_record(raw.get('asset'), v)
            state['statuses'] += 1
            on_status(v)
    except schemas.RecordError as exc:
        _reject(rec, str(exc), raw.get('asset'), 'PLC_STATE' if rec.topic == topics.K_STATUS else raw.get('name'))
    except Exception as exc:  # noqa: BLE001 — module docstring: counted, logged with traceback, /healthz 503 for a minute
        state["record_errors"] += 1
        state["last_record_error"] = f"{rec.topic}/{rec.partition}/{rec.offset}: {type(exc).__name__}: {exc}"[:300]
        state["last_record_error_at"] = time.time()
        log.exception("record %s/%s/%s failed", rec.topic, rec.partition, rec.offset)
        asset = raw.get('asset')
        name = 'PLC_STATE' if rec.topic == topics.K_STATUS else raw.get('name')
        if asset in topics.ASSETS and (name in TAGS or name == 'PLC_STATE'):
            runtime.invalidate(asset, name, 'RECORD_FAILED')


async def run():
    global store
    try:
        async with AsyncExitStack() as resources:
            store = Store(STATE_PATH)
            resources.callback(store.close)
            saved = store.load()
            if saved:
                restore(saved)
            await refresh_catalog()
            refresh = asyncio.create_task(poll_catalog())
            resources.push_async_callback(_stop_refresh, refresh)
            prod = await make_producer()
            resources.push_async_callback(prod.stop)
            cons = await make_consumer([topics.K_TAG, topics.K_WAVE, topics.K_STATUS], group='detector',
                                       from_latest=True, auto_commit=False)
            resources.push_async_callback(cons.stop)
            while not cons.assignment():
                await asyncio.sleep(.05)
            for partition in cons.assignment():
                await cons.position(partition)
            state['kafka'] = True
            await drain_alerts(prod)
            done, last_checkpoint = {}, time.monotonic()
            async for rec in cons:
                position, max_ts = store.position(rec.topic, rec.partition)
                verdict = replay_verdict(rec.offset, rec.timestamp, position, max_ts)
                if verdict == 'recreated':
                    store.forget(rec.topic, rec.partition)
                    state['offset_resets'] += 1
                    log.error('%s/%s: offset %s is below the checkpoint (%s) but newer than every processed record — the topic '
                              'was recreated; its checkpoint is dropped and records are processed again', rec.topic,
                              rec.partition, rec.offset, position)
                    verdict = 'new'
                if verdict == 'new':
                    async with mutation_lock:
                        await process(prod, rec)
                        key = (rec.topic, rec.partition)
                        done[key] = (rec.offset, max(rec.timestamp, done.get(key, (0, 0))[1]))
                        emitted = bool(pending_alerts)
                        if emitted:
                            checkpoint(done)       # the transition and its outbox entry are durable before they are sent
                    if emitted:
                        await drain_alerts(prod)
                if time.monotonic() - last_checkpoint >= CHECKPOINT_S:
                    if done:
                        async with mutation_lock:
                            checkpoint(done)
                        await cons.commit({TopicPartition(t, p): o + 1 for (t, p), (o, _) in done.items()})
                        done = {}
                    last_checkpoint = time.monotonic()
    finally:
        state['kafka'] = False
        store = None


def health() -> dict:
    recent_error = state["last_record_error_at"] is not None and time.time() - state["last_record_error_at"] < ERROR_WINDOW_S
    return {**{k: v for k, v in state.items() if k != "last_record_error_at"}, **delivery.health(), 'patterns': catalog_status,
            "ok": state["kafka"] and catalog_status['ready'] and delivery.healthy() and not recent_error
                  and not state.get("consumer_dead", False)}


app = make_app("detector (L4: 1 s features + anomaly score + CEP)", reg, health)


def _watch(task):
    """If the consume loop ever exits, /healthz reports it (503) instead of looking healthy while doing nothing."""
    state["consumer_dead"] = True
    state["consumer_error"] = repr(task.exception()) if not task.cancelled() and task.exception() else "exited"
    log.error("consumer task ended: %s", state["consumer_error"])


@app.on_event("startup")
async def _startup():
    asyncio.create_task(run()).add_done_callback(_watch)


@app.get('/api/detector/patterns')
async def get_pattern_catalog():
    return pattern_catalog()


def pattern_catalog():
    return dict(source=catalog_status, applied=runtime.describe(), pending_alerts=len(store.pending()) if store else None)


@app.post('/api/detector/patterns/reload')
async def reload_patterns():
    if not await refresh_catalog():
        raise HTTPException(503, detail=catalog_status)
    return pattern_catalog()


@app.get('/api/detector/state')
async def get_detector_state():
    return detector_state()


def detector_state():
    now = time.time()
    described = runtime.describe()['assets']
    view = {}
    for asset in topics.ASSETS:
        a = assets.get(asset) or AssetState(asset)
        observations = runtime.asset(asset).observations
        ts1_slope, vs1_slope = runtime.slope(asset, 'TS1'), runtime.slope(asset, 'VS1')
        view[asset] = {"patterns": described.get(asset, {}), "ts1": value(asset, "TS1"), "ce": value(asset, "CE"),
                       "ps1": value(asset, "PS1"), "fs1": value(asset, "FS1"), "vs1": value(asset, "VS1"),
                       "slope": None if ts1_slope is None else round(ts1_slope, 5),
                       "vs1_slope": None if vs1_slope is None else round(vs1_slope, 5), "score": a.score,
                       "plc_state": a.plc_state, "tripped": a.trip_state.tripped, 'observations': observations.view(now)}
    return {"time_scale": TIME_SCALE, 'daq_profile': DAQ_PROFILE, 'observation_grace_wall_s': OBSERVATION_GRACE_S,
            "slope_unit": "per simulated second", **{k: v for k, v in state.items() if k != "last_record_error_at"},
            "assets": view}
