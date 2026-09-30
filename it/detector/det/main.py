"""detector (L4): Flink stand-in. plant.tag/plant.wave/plant.status -> feat.1s + alerts (RAISE/CLEAR).

Per asset: 60-sim-second TS1 slope, z-score anomaly score (autoencoder slot), CEP state machine, trip watcher.
Simulated time = (event time - first event time) * TIME_SCALE, so hold windows are in simulated seconds.
"""
import asyncio
import logging
import os
from dataclasses import dataclass, field

from hydcommon import topics
from hydcommon.kafka import consumer as make_consumer, producer as make_producer
from hydcommon.metrics import Registry
from hydcommon.service import make_app
from hydcommon.timeutil import parse_iso
from . import cep, features

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("detector")
TIME_SCALE = float(os.getenv("TIME_SCALE", "20"))

reg = Registry()
c_alerts = reg.counter("detector_alerts_total", "alerts emitted by pattern/state")
g_score = reg.gauge("detector_anomaly_score", "anomaly score by asset")
g_ts1 = reg.gauge("detector_ts1", "latest TS1 by asset")

# fixed "trained" baseline of the healthy operating point (restart-safe; see features.Baseline for the learned variant)
NORMAL = {"TS1": (48.0, 1.0), "CE": (84.0, 3.0), "VS1": (0.6, 0.05)}


@dataclass
class AssetState:
    asset: str
    latest: dict = field(default_factory=dict)
    slope: features.SlopeWindow = field(default_factory=lambda: features.SlopeWindow(window_s=60.0))
    cep_state: cep.CepState = field(default_factory=cep.CepState)
    trip_state: cep.TripState = field(default_factory=cep.TripState)
    last_sim_t: float = 0.0
    score: float = 0.0
    plc_state: str = "RUN"


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


async def on_tag(prod, v: dict):
    a = get(v["asset"])
    name, val, t_iso = v["name"], v.get("v"), v.get("t")
    if val is None or t_iso is None:
        return
    a.latest[name] = val
    if name != "TS1":
        return
    t_sim = sim_time(t_iso)
    a.last_sim_t = t_sim
    a.slope.push(t_sim, val)
    slope = a.slope.slope()
    z = (baseline.z("TS1", val), baseline.z("CE", a.latest.get("CE", 84.0)), baseline.z("VS1", a.latest.get("VS1", 0.6)))
    a.score = features.anomaly_score(*z)
    g_score.set(a.score, asset=a.asset)
    g_ts1.set(val, asset=a.asset)
    key = topics.asset_key(a.asset)
    await prod.send(topics.K_FEAT, key=key, value={"asset": a.asset, "t": t_iso, "sensor": "TS1", "mean": val,
                                                   "rms": None, "slope": round(slope, 5), "score": a.score})
    ev = cep.evaluate(a.cep_state, a.asset, t_sim, val, a.latest.get("CE", 100.0), slope, t_iso=t_iso, score=a.score)
    if ev:
        await emit_alert(prod, ev)


async def on_wave(prod, v: dict):
    f = features.wave_features(v.get("v") or [])
    await prod.send(topics.K_FEAT, key=topics.asset_key(v["asset"]), value={
        "asset": v["asset"], "t": v.get("t0"), "sensor": v["sensor"], "mean": f["mean"], "rms": f["rms"], "slope": f["slope"], "score": None})


async def on_status(prod, v: dict):
    a = get(v.get("asset", "HYD-00"))
    a.plc_state = v.get("state", "RUN")
    ev = cep.trip_alert(a.trip_state, a.asset, tripped=(a.plc_state == "TRIP"), t_iso=v.get("t"), reason=v.get("trip"))
    if ev:
        await emit_alert(prod, ev)


async def emit_alert(prod, ev: dict):
    await prod.send(topics.K_ALERTS, key=topics.asset_key(ev["asset"]), value=ev)
    c_alerts.inc(pattern=ev["pattern"], state=ev["state"])
    state["alerts"] += 1
    log.info("ALERT %s %s %s evidence=%s", ev["state"], ev["pattern"], ev["alertId"], ev.get("evidence"))


async def run():
    prod = await make_producer()
    cons = await make_consumer([topics.K_TAG, topics.K_WAVE, topics.K_STATUS], group="detector", from_latest=True)
    state["kafka"] = True
    log.info("consuming plant.tag/plant.wave/plant.status (TIME_SCALE=%s)", TIME_SCALE)
    async for rec in cons:
        try:
            if not isinstance(rec.value, dict) or "_raw" in rec.value:
                continue
            if rec.topic == topics.K_TAG:
                state["tags"] += 1
                await on_tag(prod, rec.value)
            elif rec.topic == topics.K_WAVE:
                state["waves"] += 1
                await on_wave(prod, rec.value)
            elif rec.topic == topics.K_STATUS:
                await on_status(prod, rec.value)
        except Exception as e:  # noqa: BLE001
            log.warning("record failed on %s: %s", rec.topic, e)


app = make_app("detector (L4: 1 s features + anomaly score + CEP)", reg,
               lambda: {**{k: v for k, v in state.items() if k != "t0"}, "ok": state["kafka"] and not state.get("consumer_dead", False)})


def _watch(task):
    """If the consume loop ever exits, /healthz reports it (503) instead of looking healthy while doing nothing."""
    state["consumer_dead"] = True
    state["consumer_error"] = repr(task.exception()) if not task.cancelled() and task.exception() else "exited"
    log.error("consumer task ended: %s", state["consumer_error"])


@app.on_event("startup")
async def _startup():
    asyncio.create_task(run()).add_done_callback(_watch)


@app.get("/api/detector/state")
def detector_state():
    return {"time_scale": TIME_SCALE, **{k: v for k, v in state.items() if k != "t0"},
            "assets": {a.asset: {"phase": a.cep_state.phase, "alert_id": a.cep_state.alert_id, "since": a.cep_state.since,
                                 "sim_t": round(a.last_sim_t, 1), "ts1": a.latest.get("TS1"), "ce": a.latest.get("CE"),
                                 "slope": round(a.slope.slope(), 5), "score": a.score, "plc_state": a.plc_state,
                                 "tripped": a.trip_state.tripped} for a in assets.values()}}
