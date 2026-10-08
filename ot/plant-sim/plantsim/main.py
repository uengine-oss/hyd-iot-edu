"""plant-sim HTTP API (L1). Fault injection is a lecture tool, not part of the OT command path."""
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from hydcommon.metrics import Registry
from . import thermal
from .plant import Plant
from .edge import Edge

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

TIME_SCALE = float(os.getenv("TIME_SCALE", "20"))
plant = Plant(time_scale=TIME_SCALE)
edge = Edge(plant, publish_wave=None if os.getenv("PUBLISH_WAVE") is None else os.getenv("PUBLISH_WAVE") == "1")   # DAQ_PROFILE lite|full decides by default
reg = Registry()
g_ts1 = reg.gauge("plant_ts1_celsius", "oil temperature")
g_health = reg.gauge("plant_cooler_health", "cooler health 0..1")
g_leak = reg.gauge("plant_pump_leak", "pump A internal leakage fraction")
g_wear = reg.gauge("plant_fan_bearing_wear", "fan bearing wear 0..1")
g_pub = reg.gauge("plant_mqtt_published_total", "messages published")

app = FastAPI(title="plant-sim (L1 hydraulic units + soft-PLC)", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class FaultReq(BaseModel):
    asset: str = "HYD-01"
    type: str = "cooler_degradation"     # cooler_degradation | pump_leakage | fan_vibration | restore
    target: float | None = None          # ramp target of the fault's disturbance variable (default per kind)
    target_health: float | None = None   # legacy name for cooler_degradation
    severity: str | None = None          # named strength when no target is given: "high" (default, trips) | "moderate" (cooler only, alarm without trip)
    ramp_sim_s: float | None = None     # None = the kind's default ramp (plant.DEFAULT_RAMP_S)


class ModeReq(BaseModel):
    asset: str
    mode: str


class ScaleReq(BaseModel):
    scale: float


class ManualReq(BaseModel):
    asset: str
    writes: dict            # {"FanSpeedSP": 80, "LoadSP": 70, "Reset": 1}


@app.on_event("startup")
def _startup():
    edge.start()


@app.on_event("shutdown")
def _shutdown():
    edge.stop()


@app.get("/healthz")
def healthz():
    return {"ok": True, "mqtt": edge.connected, "sim_t": plant.sim_t, "daq": edge.daq.profile, "waves": edge.publish_wave}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    for a, u in plant.units.items():
        g_ts1.set(u.state.ts1, asset=a)
        g_health.set(u.state.cooler_health, asset=a)
        g_leak.set(u.state.leak, asset=a)
        g_wear.set(u.state.bearing_wear, asset=a)
    g_pub.set(edge.published)
    return reg.render()


@app.get("/api/state")
def state():
    return plant.snapshot()


@app.post("/api/fault")
def fault(req: FaultReq):
    if req.asset not in plant.units:
        raise HTTPException(404, "unknown asset")
    target = req.target if req.target is not None else (req.target_health if req.type == "cooler_degradation" else None)
    try:
        return plant.inject(req.asset, req.type, target, req.ramp_sim_s, severity=req.severity)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/mode")
def mode(req: ModeReq):
    """Local panel: the only other place besides FUXA allowed to switch operating mode."""
    if req.asset not in plant.units:
        raise HTTPException(404, "unknown asset")
    if not plant.set_mode(req.asset, req.mode, requester="LOCAL"):
        raise HTTPException(400, "invalid mode")
    edge._publish_status(req.asset)
    return plant.status(req.asset)


@app.post("/api/manual")
def manual(req: ManualReq):
    """Local panel write (same rules as FUXA cmd/manual)."""
    if req.asset not in plant.units:
        raise HTTPException(404, "unknown asset")
    from . import plc
    r = plant.command(req.asset, plc.normalize_manual(req.writes), source="FUXA")
    edge._publish_status(req.asset)
    return {"cmdId": r.cmd_id, "result": r.result, "reason": r.reason, "applied": r.writes_applied}


@app.post("/api/time_scale")
def time_scale(req: ScaleReq):
    if not (1 <= req.scale <= 200):
        raise HTTPException(400, "scale must be 1..200")
    with plant.lock:
        plant.time_scale = float(req.scale)
    return {"time_scale": plant.time_scale}


@app.post("/api/reset")
def reset():
    """Lecture helper: put every unit back to the healthy operating point (REMOTE_AUTO, fan 60, load 90, pump A, no faults)."""
    with plant.lock:
        for a, u in plant.units.items():
            u.faults.clear()
            u.state.cooler_health, u.state.leak, u.state.bearing_wear, u.state.pump = 1.0, 0.0, 0.0, "A"
            u.state.fan_pct, u.state.load_pct = 60.0, 90.0
            u.state.ts1 = 48.0
            u.ctrl.mode, u.ctrl.state, u.ctrl.trip = "REMOTE_AUTO", "RUN", None
            u.ctrl.last_cmd_id = u.ctrl.last_result = u.ctrl.last_reason = None
            u.dirty_status = True
    for a in plant.units:
        edge._publish_status(a)
    return plant.snapshot()
