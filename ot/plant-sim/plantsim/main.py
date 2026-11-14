"""plant-sim HTTP API (L1). Fault injection is a lecture tool, not part of the OT command path.

POST /api/mode and /api/manual are the panel at the machine (source LOCAL — see plc.WRITERS); the portal's 결함 시뮬레이션
screen stands in for it. Everything else that changes the plant comes over MQTT (edge).
"""
import logging

from fastapi import HTTPException
from pydantic import BaseModel

from hydcommon.daq_contract import profile_from_env
from hydcommon.metrics import Registry
from hydcommon.service import make_app
from hydcommon.timeutil import now_iso, time_scale
from . import plc, thermal
from .edge import Edge
from .plant import Plant

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

TIME_SCALE = time_scale()
plant = Plant(time_scale=TIME_SCALE)
edge = Edge(plant, daq_profile=profile_from_env())
reg = Registry()
g_ts1 = reg.gauge("plant_ts1_celsius", "oil temperature")
g_health = reg.gauge("plant_cooler_health", "cooler health 0..1")
g_leak = reg.gauge("plant_pump_leak", "pump A internal leakage fraction")
g_wear = reg.gauge("plant_fan_bearing_wear", "fan bearing wear 0..1")
g_pub = reg.gauge("plant_mqtt_published_total", "messages published")


def refresh_gauges():
    for a, u in plant.units.items():
        g_ts1.set(u.state.ts1, asset=a)
        g_health.set(u.state.cooler_health, asset=a)
        g_leak.set(u.state.leak, asset=a)
        g_wear.set(u.state.bearing_wear, asset=a)
    g_pub.set(edge.published)


app = make_app("plant-sim (L1 hydraulic units + soft-PLC)", reg, lambda: {**edge.health(), "sim_t": plant.sim_t}, refresh_gauges)


class FaultReq(BaseModel):
    asset: str                           # 어느 설비에 무엇을 넣는지는 부르는 쪽이 정한다 — 빠지면 HYD-01 쿨러 열화로 대신 넣지 않고 422
    type: str                            # cooler_degradation | pump_leakage | fan_vibration | restore
    target: float | None = None          # ramp target of the fault's disturbance variable (default per kind; domain plant.DOMAIN)
    severity: str | None = None          # named strength when no target is given: "high" (default, trips) | "moderate" (cooler only, alarm without trip)
    ramp_sim_s: float | None = None     # None = the kind's default ramp (plant.DEFAULT_RAMP_S)
    component: str | None = None        # C2 restore only: cooler | pump | fan (or comp:* id) — None restores every disturbance
    origin: dict | None = None          # C3: the button press behind this request {id, by, user_id, roles} — kept as the unit's injection
    operating_point: bool = False       # restore only: also put FanSpeedSP · LoadSP back to the normal operating point (ends a mitigation)


class ModeReq(BaseModel):
    asset: str
    mode: str


class ManualReq(BaseModel):
    asset: str
    writes: dict            # {"FanSpeedSP": 80, "LoadSP": 70, "Reset": 1}


@app.on_event("startup")
def _startup():
    edge.start()


@app.on_event("shutdown")
def _shutdown():
    edge.stop()


@app.get("/api/state")
def state():
    return plant.snapshot()


@app.post("/api/fault")
def fault(req: FaultReq):
    if req.asset not in plant.units:
        raise HTTPException(404, "unknown asset")
    try:
        if req.origin is not None and not str(req.origin.get("id") or "").strip():
            raise ValueError("origin needs an id (the press that asked for this injection)")
        return plant.inject(req.asset, req.type, req.target, req.ramp_sim_s, severity=req.severity, component=req.component,
                            origin=req.origin, operating_point=req.operating_point)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/mode")
def mode(req: ModeReq):
    """The panel at the machine: the only other place besides FUXA allowed to switch operating mode."""
    if req.asset not in plant.units:
        raise HTTPException(404, "unknown asset")
    if not plant.set_mode(req.asset, req.mode, requester="LOCAL"):
        raise HTTPException(400, "invalid mode")
    edge.publish_status(req.asset, now_iso())
    return plant.status(req.asset)


@app.post("/api/manual")
def manual(req: ManualReq):
    """The panel at the machine writes (source LOCAL: allowed in every mode; in REMOTE_AUTO it switches to REMOTE_MANUAL)."""
    if req.asset not in plant.units:
        raise HTTPException(404, "unknown asset")
    r = plant.command(req.asset, plc.normalize_manual(req.writes, "LOCAL"), source="LOCAL")
    edge.publish_status(req.asset, now_iso())
    return {"cmdId": r.cmd_id, "result": r.result, "reason": r.reason, "reason_text": plc.TEXT.get(r.reason) if r.reason else None,
            "applied": r.writes_applied}


@app.post("/api/reset")
def reset():
    """Lecture helper: put every unit back to the healthy operating point (REMOTE_AUTO, fan 60, load 90, pump A, no faults)."""
    plant.reset()
    t = now_iso()
    for a in plant.units:
        edge.publish_status(a, t)
    return plant.snapshot()
