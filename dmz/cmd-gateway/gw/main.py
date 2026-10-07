"""cmd-gateway (L3, DMZ): the ONLY path from IT down to OT.

  Kafka action.cmd --validate (5 checks)--> MQTT plant/{a}/cmd/auto   (retain=false)
  Kafka alerts     --relay (display only)--> MQTT plant/{a}/alert     (retain=true)
  MQTT plant/{a}/status --> remembered so check ⑤ knows the PLC mode
  MQTT plant/{a}/alert  --> retained legacy display records are re-published with display_text (no new alarm event)
Rejected commands are dropped and written to Kafka audit with the failing check (one of validate.CHECKS).
"""
import asyncio
import json
import logging
import time
from collections import deque

from hydcommon import topics
from hydcommon.kafka import consumer as make_consumer, producer as make_producer
from hydcommon.metrics import Registry
from hydcommon.mqtt import make_client
from hydcommon.service import make_app
from hydcommon.timeutil import now, now_iso
from . import validate as gw

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("cmd-gateway")

reg = Registry()
c_dec = reg.counter("gateway_decisions_total", "command decisions by result/check")
c_alerts = reg.counter("gateway_alerts_relayed_total", "alerts relayed to OT")
state = {"mqtt": False, "kafka": False, "forwarded": 0, "rejected": 0, "alerts_relayed": 0}
gstate = gw.GatewayState()
decisions: deque = deque(maxlen=200)
mqtt = make_client("cmd-gateway")


def _on_connect(client, userdata, flags, rc, properties=None):
    state["mqtt"] = True
    client.subscribe("plant/+/status", qos=1)
    client.subscribe("plant/+/alert", qos=1)
    log.info("mqtt connected, watching plant/+/status and retained plant/+/alert")


def _on_message(client, userdata, msg):
    parsed = topics.parse_mqtt(msg.topic)
    if parsed and parsed[1] == "alert" and msg.retain:
        try:
            upgraded = gw.upgrade_retained_alert(json.loads(msg.payload.decode()))
            if upgraded:
                client.publish(msg.topic, json.dumps(upgraded), qos=1, retain=True)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    if parsed and parsed[1] == "status":
        try:
            st = json.loads(msg.payload.decode())
            gstate.last_status[st.get("asset") or topics.asset_id(parsed[0])] = st
        except json.JSONDecodeError:
            pass


async def run():
    prod = await make_producer()
    cons = await make_consumer([topics.K_CMD, topics.K_ALERTS], group="cmd-gateway", from_latest=True)
    state["kafka"] = True
    log.info("consuming action.cmd and alerts")
    async for rec in cons:
        try:
            await handle(prod, rec)
        except Exception as e:  # noqa: BLE001
            log.warning("record on %s failed: %s", rec.topic, e)


async def handle(prod, rec):
    v = rec.value if isinstance(rec.value, dict) else {"_raw": str(rec.value)}
    if rec.topic == topics.K_ALERTS:
        if "_raw" in v or not v.get("asset"):
            log.warning("ignoring malformed alert: %s", str(v)[:120])
            return
        key = topics.asset_key(v.get("asset", "hyd00"))
        ot = gw.alert_to_ot(v)
        mqtt.publish(topics.mqtt_alert(key), json.dumps(ot), qos=1, retain=True)
        c_alerts.inc(state=v.get("state", "?"))
        state["alerts_relayed"] += 1
        log.info("alert relayed -> %s %s %s", topics.mqtt_alert(key), v.get("state"), v.get("alertId"))
        return

    d = gw.validate(v, gstate, now())
    entry = {"t": now_iso(), "cmdId": v.get("cmdId") if isinstance(v, dict) else None,
             "asset": v.get("asset") if isinstance(v, dict) else None, "incident": v.get("incident") if isinstance(v, dict) else None,
             "ok": d.ok, "check": d.check, "reason": d.reason}
    decisions.appendleft(entry)
    c_dec.inc(result="PASS" if d.ok else "REJECT", check=d.check)
    if d.ok:
        key = topics.asset_key(v["asset"])
        mqtt.publish(topics.mqtt_cmd_auto(key), json.dumps(d.mqtt_payload), qos=1, retain=False)
        state["forwarded"] += 1
        log.info("cmd %s -> %s PASS %s", v["cmdId"], topics.mqtt_cmd_auto(key), d.mqtt_payload["writes"])
        await prod.send(topics.K_AUDIT, key=key, value={
            "t": now_iso(), "incident": v.get("incident"), "actor": "cmd-gateway", "event": "CMD_FORWARDED",
            "detail": {"cmdId": v["cmdId"], "writes": d.mqtt_payload["writes"], "checks": list(gw.CHECKS)}})
    else:
        state["rejected"] += 1
        log.warning("cmd %s REJECTED at %s: %s", entry["cmdId"], d.check, d.reason)
        await prod.send(topics.K_AUDIT, key=topics.asset_key(entry["asset"] or "hyd00"), value={
            "t": now_iso(), "incident": entry["incident"], "actor": "cmd-gateway", "event": "CMD_REJECTED",
            "detail": {"cmdId": entry["cmdId"], "check": d.check, "reason": d.reason}})


app = make_app("cmd-gateway (L3 DMZ: validated downlink IT -> OT)", reg,
               lambda: {**state, "ok": state["kafka"] and not state.get("consumer_dead", False)})


def _watch(task):
    """If the consume loop ever exits, /healthz reports it (503) instead of looking healthy while doing nothing."""
    state["consumer_dead"] = True
    state["consumer_error"] = repr(task.exception()) if not task.cancelled() and task.exception() else "exited"
    log.error("consumer task ended: %s", state["consumer_error"])


@app.on_event("startup")
async def _startup():
    mqtt.on_connect = _on_connect
    mqtt.on_message = _on_message
    mqtt.loop_start()
    asyncio.create_task(run()).add_done_callback(_watch)


@app.get("/api/gateway/log")
def get_log():
    return list(decisions)


@app.get("/api/gateway/status")
def get_status():
    return {"plc_status": gstate.last_status, "seen_cmd_ids": list(gstate.seen_cmd_ids)[-10:], **state}
