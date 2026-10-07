"""detector (L4): Flink stand-in. plant.tag/plant.wave/plant.status -> feat.1s + alerts (RAISE/CLEAR).

Per asset: feature slopes and z-score anomaly score (autoencoder slot), plus
Neo4j TESTS/clearRule/hold definitions evaluated on each TS1 tick. Active alerts
pin their definition; SQLite checkpoints and an outbox preserve alert identity
across restart. Authoritative PLC trips are watched separately.
Clocks: pattern hold/clear windows are measured in simulated seconds = event epoch seconds * TIME_SCALE
(pattern_runtime.observe -> cep._step). sim_time() below, (event time - first event time) * TIME_SCALE, is used only
for the TS1/VS1 slope windows shown on the portal; it is not the clock the patterns hold on.
"""
import asyncio
import logging
import os
import re
import time
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass, field

from fastapi import HTTPException

from hydcommon import topics
from hydcommon.kafka import consumer as make_consumer, producer as make_producer
from hydcommon.metrics import Registry
from hydcommon.service import make_app
from hydcommon.timeutil import parse_iso
from . import cep, features
from .observations import Observations
from .pattern_runtime import PatternRuntime
from .pattern_source import read_patterns
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("detector")
TIME_SCALE = float(os.getenv("TIME_SCALE", "20"))
DAQ_PROFILE = os.getenv('DAQ_PROFILE', 'lite')
OBSERVATION_GRACE_S = float(os.getenv('OBSERVATION_GRACE_S', '2'))
# Legacy display aliases only; these names do not select executable predicates.
DISPLAY_STATES = {'COOLER_DEGRADATION': 'cep_state', 'PUMP_LEAKAGE': 'pump_state', 'FAN_VIBRATION': 'fan_state'}
runtime = None
store = None
pending_alerts = []
catalog_status = {'ready': False, 'error': 'NOT_LOADED', 'checked_at': None, 'applied_at': None}
mutation_lock = asyncio.Lock()
refresh_lock = asyncio.Lock()
PATTERN_SCOPE = os.getenv('DETECTOR_PATTERN_SCOPE', 'production')
TOPIC_PREFIX = os.getenv('DETECTOR_TOPIC_PREFIX', '')
if TOPIC_PREFIX:
    if not re.fullmatch('[a-zA-Z0-9_-]{1,120}', TOPIC_PREFIX):raise ValueError('invalid detector topic prefix')
    for key, suffix in [('K_TAG','tag'),('K_WAVE','wave'),('K_STATUS','status'),('K_FEAT','feat'),('K_ALERTS','alerts')]:
        setattr(topics, key, f'{TOPIC_PREFIX}.{suffix}')

reg = Registry()
c_alerts = reg.counter("detector_alerts_total", "alerts emitted by pattern/state")
g_score = reg.gauge("detector_anomaly_score", "anomaly score by asset")
g_ts1 = reg.gauge("detector_ts1", "latest TS1 by asset")
g_event_time = reg.gauge('detector_input_event_timestamp_seconds', 'last accepted source event timestamp by asset/tag')
g_valid = reg.gauge('detector_pattern_inputs_valid', 'required inputs valid at last TS1 evaluation; inspect source event timestamps for current age')

# fixed "trained" baseline of the healthy operating point (restart-safe; see features.Baseline for the learned variant)
NORMAL = {"TS1": (48.0, 1.0), "CE": (84.0, 3.0), "VS1": (0.6, 0.05)}


@dataclass
class AssetState:
    asset: str
    latest: dict = field(default_factory=dict)
    slope: features.SlopeWindow = field(default_factory=lambda: features.SlopeWindow(window_s=60.0))
    vs1_slope: features.SlopeWindow = field(default_factory=lambda: features.SlopeWindow(window_s=60.0))
    cep_state: cep.CepState = field(default_factory=cep.CepState)
    pump_state: cep.CepState = field(default_factory=cep.CepState)
    fan_state: cep.CepState = field(default_factory=cep.CepState)
    trip_state: cep.TripState = field(default_factory=cep.TripState)
    last_sim_t: float = 0.0
    score: float | None = None
    plc_state: str = "UNKNOWN"
    observations: Observations = field(default_factory=lambda: Observations(DAQ_PROFILE, OBSERVATION_GRACE_S))
    data_quality: dict = field(default_factory=dict)


state = {"kafka": False, "t0": None, "tags": 0, "waves": 0, "alerts": 0}
assets: dict[str, AssetState] = {}
baseline = features.Baseline()
baseline.stats.update(NORMAL)


def get(asset: str) -> AssetState:
    if asset not in assets:
        assets[asset] = AssetState(asset)
    return assets[asset]


def sim_time(t_iso: str) -> float:
    t = parse_iso(t_iso)
    if state["t0"] is None:
        state["t0"] = t
    return (t - state["t0"]).total_seconds() * TIME_SCALE


def interrupt_input(a, name, reason):
    if name == 'TS1':
        a.slope.pts.clear()
    elif name == 'VS1':
        a.vs1_slope.pts.clear()


def sync_pattern_view(a):
    if runtime is None or a.asset not in runtime.assets:
        return
    runs = runtime.assets[a.asset].runs
    a.data_quality = {code: run.quality for code, run in runs.items()}
    for code, run in runs.items():
        if code in DISPLAY_STATES:setattr(a, DISPLAY_STATES[code], run.state)
        g_valid.set(int(run.quality.get('status') == 'VALID'), asset=a.asset, pattern=code)


def pattern_observe(a, name, value, timestamp, quality='good'):
    if runtime is None:return []
    try:
        at = parse_iso(timestamp).timestamp()
    except (AttributeError, TypeError, ValueError):
        runtime.invalidate(a.asset, name, 'INVALID_TIMESTAMP')
        sync_pattern_view(a)
        return []
    events = runtime.observe(a.asset, name, value, at, quality, now=time.time())
    sync_pattern_view(a)
    return events


def observe(a, name, value, timestamp, quality='good'):
    try:
        at = parse_iso(timestamp).timestamp()
    except (AttributeError, TypeError, ValueError):
        a.observations.invalidate(name, 'INVALID_TIMESTAMP')
        a.latest.pop(name, None)
        interrupt_input(a, name, 'INVALID_TIMESTAMP')
        return None
    old = a.observations.samples.get(name)
    if old and old['time'] is not None and at < old['time']:
        return None  # a delayed record must not overwrite the newer source state
    if at > time.time() + OBSERVATION_GRACE_S:
        a.observations.invalidate(name, 'FUTURE_TIMESTAMP')
        a.latest.pop(name, None)
        interrupt_input(a, name, 'FUTURE_TIMESTAMP')
        return None  # do not advance the watermark into the future
    status, gap = a.observations.record(name, at, value, quality)
    if status == 'ignored':
        return None
    if status == 'invalid' or gap:
        interrupt_input(a, name, 'INVALID_VALUE_OR_QUALITY' if status == 'invalid' else 'OBSERVATION_GAP')
    if status == 'invalid':
        a.latest.pop(name, None)
        return None
    a.latest[name] = value
    g_event_time.set(at, asset=a.asset, tag=name)
    return at


async def on_tag(prod, v: dict):
    a = get(v["asset"])
    name, val, t_iso = v["name"], v.get("v"), v.get("t")
    events = pattern_observe(a, name, val, t_iso, v.get('q', 'good'))
    at = observe(a, name, val, t_iso, v.get('q', 'good'))
    if at is None:
        return
    if name == "VS1":
        a.vs1_slope.push(sim_time(t_iso), val)
    if name != "TS1":
        return
    t_sim = sim_time(t_iso)
    a.last_sim_t = t_sim
    a.slope.push(t_sim, val)
    a.vs1_slope.trim(t_sim)
    slope = a.slope.slope()
    now = time.time()
    score_problems = a.observations.problems(('TS1', 'CE', 'VS1'), at, now)
    a.score = None if score_problems else features.anomaly_score(*(baseline.z(tag, a.latest[tag]) for tag in ('TS1', 'CE', 'VS1')))
    if a.score is not None:
        g_score.set(a.score, asset=a.asset)
    g_ts1.set(val, asset=a.asset)
    key = topics.asset_key(a.asset)
    await prod.send(topics.K_FEAT, key=key, value={"asset": a.asset, "t": t_iso, "sensor": "TS1", "mean": val,
                                                   "rms": None, "slope": round(slope, 5), "score": a.score})
    for ev in events:
        # Preserve existing consumers' evidence field names alongside full definition provenance.
        ev['evidence'].update(ts1=a.latest.get('TS1'), ce=a.latest.get('CE'), ps1=a.latest.get('PS1'),
                              fs1=a.latest.get('FS1'), load=a.latest.get('LoadSP'), vs1=a.latest.get('VS1'),
                              ts1_slope=slope, vs1_slope=a.vs1_slope.slope(), score=a.score)
        await emit_alert(prod, ev)


async def on_wave(prod, v: dict):
    f = features.wave_features(v.get("v") or [])
    await prod.send(topics.K_FEAT, key=topics.asset_key(v["asset"]), value={
        "asset": v["asset"], "t": v.get("t0"), "sensor": v["sensor"], "mean": f["mean"], "rms": f["rms"], "slope": f["slope"], "score": None})


async def on_status(prod, v: dict):
    a = get(v.get("asset", "HYD-00"))
    pattern_observe(a, 'PLC_STATE', v.get('state'), v.get('t'))
    at = observe(a, 'PLC_STATE', v.get('state'), v.get('t'))
    if at is None:
        if not (a.observations.samples.get('PLC_STATE') or {}).get('valid'):
            a.plc_state = 'UNKNOWN'
        return
    a.plc_state = v['state']
    if a.observations.problems(('PLC_STATE',), at, time.time()):
        interrupt_input(a, 'PLC_STATE', 'STALE')
        return
    ev = cep.trip_alert(a.trip_state, a.asset, tripped=(a.plc_state == "TRIP"), t_iso=v.get("t"), reason=v.get("trip"))
    if ev:
        await emit_alert(prod, ev)


async def emit_alert(prod, ev: dict):
    if store is not None:
        pending_alerts.append(ev)
    else:
        await prod.send(topics.K_ALERTS, key=topics.asset_key(ev["asset"]), value=ev)
    c_alerts.inc(pattern=ev["pattern"], state=ev["state"])
    state["alerts"] += 1
    log.info("ALERT %s %s %s evidence=%s", ev["state"], ev["pattern"], ev["alertId"], ev.get("evidence"))


def checkpoint(record=None):
    if store is not None:
        store.save(dict(scope=PATTERN_SCOPE, runtime=runtime.snapshot() if runtime else None,
                        trips={a.asset: asdict(a.trip_state) for a in assets.values()}), record, pending_alerts)
        pending_alerts.clear()


def fetch_catalog():
    from neo4j import GraphDatabase
    user, password = os.getenv('NEO4J_AUTH', 'neo4j/hydpass123').split('/', 1)
    with GraphDatabase.driver(os.getenv('NEO4J_URI', 'bolt://neo4j:7687'), auth=(user,password),
                              connection_timeout=3, connection_acquisition_timeout=5,
                              max_transaction_retry_time=0) as driver:
        return read_patterns(driver, scope=PATTERN_SCOPE)


async def refresh_catalog():
    async with refresh_lock:
        return await _refresh_catalog()


async def _refresh_catalog():
    global runtime
    try:
        rows = await asyncio.to_thread(fetch_catalog)
        async with mutation_lock:
            if runtime is None:runtime = PatternRuntime(rows, DAQ_PROFILE, TIME_SCALE, OBSERVATION_GRACE_S)
            else:runtime.replace(rows)
            catalog_status.update(ready=True, error=None, checked_at=time.time(), applied_at=time.time())
            checkpoint()
        return True
    except Exception as exc:
        async with mutation_lock:
            if runtime is not None:runtime.source_failed()
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


async def run():
    global store, runtime
    try:
        async with AsyncExitStack() as resources:
            store = Store(os.getenv('DETECTOR_STATE_PATH', '/data/detector.sqlite3'))
            resources.callback(store.close)
            saved = store.load()
            if saved:
                if saved.get('scope') != PATTERN_SCOPE:raise RuntimeError('persisted detector source scope differs from environment')
                if saved.get('runtime'):
                    runtime = PatternRuntime.restore(saved['runtime'])
                    if (runtime.profile, runtime.time_scale, runtime.grace_s) != (DAQ_PROFILE,TIME_SCALE,OBSERVATION_GRACE_S):
                        raise RuntimeError('persisted detector clock/reporting contract differs from environment; explicit state migration required')
                for asset, trip in saved.get('trips', {}).items():get(asset).trip_state = cep.TripState(**trip)
                if runtime:
                    for asset in runtime.assets:sync_pattern_view(get(asset))
            await refresh_catalog()
            refresh = asyncio.create_task(poll_catalog())
            resources.push_async_callback(_stop_refresh, refresh)
            prod = await make_producer()
            resources.push_async_callback(prod.stop)
            cons = await make_consumer([topics.K_TAG, topics.K_WAVE, topics.K_STATUS], group=TOPIC_PREFIX or 'detector',
                                       from_latest=True, auto_commit=False)
            resources.push_async_callback(cons.stop)
            while not cons.assignment():
                await asyncio.sleep(.05)
            for partition in cons.assignment():
                await cons.position(partition)
            state['kafka'] = True
            await drain_alerts(prod)
            from aiokafka.structs import TopicPartition
            async for rec in cons:
                key = (rec.topic, rec.partition, rec.offset)
                if not store.seen(*key):
                    async with mutation_lock:
                        if isinstance(rec.value, dict) and '_raw' not in rec.value:
                            if rec.topic == topics.K_TAG and all(k in rec.value for k in ('asset','name')):
                                state['tags'] += 1
                                await on_tag(prod, rec.value)
                            elif rec.topic == topics.K_WAVE and all(k in rec.value for k in ('asset','sensor')):
                                state['waves'] += 1
                                await on_wave(prod, rec.value)
                            elif rec.topic == topics.K_STATUS:
                                await on_status(prod, rec.value)
                        checkpoint(key)
                await drain_alerts(prod)
                await cons.commit({TopicPartition(rec.topic, rec.partition): rec.offset+1})
    finally:
        state['kafka'] = False
        store = None


app = make_app("detector (L4: 1 s features + anomaly score + CEP)", reg,
               lambda: {**{k: v for k, v in state.items() if k != "t0"}, 'patterns': catalog_status,
                        "ok": state["kafka"] and catalog_status['ready'] and not state.get("consumer_dead", False)})


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
    return dict(source=catalog_status, applied=runtime.describe() if runtime else None,
                pending_alerts=len(store.pending()) if store else None)


@app.post('/api/detector/patterns/reload')
async def reload_patterns():
    if not await refresh_catalog():raise HTTPException(503, detail=catalog_status)
    return pattern_catalog()


@app.get('/api/detector/state')
async def get_detector_state():
    return detector_state()


def detector_state():
    return {"time_scale": TIME_SCALE, 'daq_profile': DAQ_PROFILE, 'observation_grace_wall_s': OBSERVATION_GRACE_S,
            **{k: v for k, v in state.items() if k != "t0"},
            "assets": {a.asset: {"phase": a.cep_state.phase, "alert_id": a.cep_state.alert_id, "since": a.cep_state.since,
                                 "patterns": (runtime.describe()['assets'].get(a.asset, {}) if runtime else {}),
                                 "sim_t": round(a.last_sim_t, 1), "ts1": a.latest.get("TS1"), "ce": a.latest.get("CE"),
                                 "ps1": a.latest.get("PS1"), "fs1": a.latest.get("FS1"), "vs1": a.latest.get("VS1"),
                                 "slope": round(a.slope.slope(), 5), "vs1_slope": round(a.vs1_slope.slope(), 5), "score": a.score,
                                 "plc_state": a.plc_state, "tripped": a.trip_state.tripped,
                                 'data_quality_at_last_tick': a.data_quality,
                                 'observations': a.observations.view(time.time())} for a in assets.values()}}
