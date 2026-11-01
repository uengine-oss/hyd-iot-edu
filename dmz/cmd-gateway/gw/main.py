"""cmd-gateway (L3, DMZ): the only path from IT down to OT — and, with the broker rules (ot/emqx/acl.conf: only this
service may publish plant/+/cmd/auto), the only one that can be.

  Kafka action.cmd --validate (7 checks)--> MQTT plant/{a}/cmd/auto   (retain=false)
  Kafka alerts     --alert board (display only)--> MQTT plant/{a}/alert (retain=true: the active alerts of that unit)
  Kafka audit      --process approval ledger records (A148) remembered for check ⑤ (own consumer task, group cmd-gateway-ledger)
  MQTT plant/{a}/status --> remembered so check ⑥ knows the PLC mode (asset from the topic)
  MQTT plant/{a}/alert  --> the retained board, read once after a restart so the active alerts are not forgotten
Every decision is written to Kafka audit: CMD_FORWARDED (with the command, for the actions table) or CMD_REJECTED (check ·
reason · reason_text — process reads its own cmdId's rejection and ends the case with that reason instead of waiting for an
ACK that cannot come). A command whose ledger record has not arrived yet waits up to APPROVAL_GRACE_S in its own task (the
record is published first, but two topics give no cross-topic order) — other commands and alerts are not held up; after
that it is rejected as APPROVAL like any forged command.
"""
import asyncio
import json
import logging
import time
from collections import deque

from hydcommon import schemas, topics
from hydcommon.kafka import Delivery, consumer as make_consumer, producer as make_producer
from hydcommon.metrics import Registry
from hydcommon.mqtt import Link
from hydcommon.service import make_app
from hydcommon.timeutil import now, now_iso
from . import validate as gw

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("cmd-gateway")

schemas.fingerprint_key()          # no key, no gateway: it could not verify a single approval
APPROVAL_GRACE_S = 3.0
reg = Registry()
c_dec = reg.counter("gateway_decisions_total", "command decisions by result/check")
c_alerts = reg.counter("gateway_alerts_relayed_total", "alerts relayed to OT")
state = {"kafka": False, "forwarded": 0, "rejected": 0, "alerts_relayed": 0, "alert_relay_failed": 0, "approvals_recorded": 0, "approval_conflicts": 0,
         "malformed": 0, "last_malformed": None}
gstate = gw.GatewayState()
board = gw.AlertBoard()
delivery = Delivery()
decisions: deque = deque(maxlen=200)


def _malformed(where: str, reason) -> None:
    state["malformed"] += 1
    state["last_malformed"] = f"{where}: {reason}"[:200]
    log.warning("malformed %s", state["last_malformed"])


def _on_connect(client):
    client.subscribe([("plant/+/status", 1), ("plant/+/alert", 1)])


def _on_message(client, msg):
    parsed = topics.parse_mqtt(msg.topic)
    if not parsed:
        return
    asset, kind, _ = parsed
    try:
        body = json.loads(msg.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _malformed(msg.topic, "payload is not UTF-8 JSON")
        return
    if kind == "status":
        try:
            gstate.last_status[asset] = schemas.status_record(asset, body)
        except schemas.RecordError as exc:
            _malformed(msg.topic, exc)
    elif kind == "alert" and msg.retain:
        board.restore(asset, body)


link = Link("cmd-gateway", _on_message, on_connect=_on_connect)


async def run(prod):
    while True:
        cons = await make_consumer([topics.K_CMD, topics.K_ALERTS], group="cmd-gateway", from_latest=True)
        log.info("consuming action.cmd and alerts")
        try:
            async for rec in cons:
                if rec.topic == topics.K_ALERTS:
                    await relay_alert(rec.value)
                else:
                    asyncio.create_task(handle_command(prod, rec.value)).add_done_callback(_command_done)
        except Exception as e:  # noqa: BLE001 — A148: a fetch that cannot be decoded (unsupported codec, broken batch)
            # used to end this task for good (healthz 503 until a restart). The record is dropped (commands expire in
            # 120 s anyway), the error is counted for /healthz, and the loop resumes behind the poison record.
            state["consumer_errors"] = state.get("consumer_errors", 0) + 1
            state["consumer_last_error"] = repr(e)[:200]
            log.error("consume loop failed (%s); dropping the record and resuming", e)
            await _skip_poison(cons)
        finally:
            await cons.stop()
        await asyncio.sleep(1)


def _command_done(task) -> None:
    """A command task that raised (e.g. the audit record could not be queued) is counted and logged, never lost silently."""
    if task.cancelled() or task.exception() is None:
        return
    state["command_errors"] = state.get("command_errors", 0) + 1
    state["command_last_error"] = repr(task.exception())[:200]
    state["command_last_error_at"] = time.time()
    log.error("command handling failed: %s", state["command_last_error"], exc_info=task.exception())


async def _skip_poison(cons) -> None:
    """Commit one past the position of every assigned partition so the undecodable record is left behind."""
    try:
        for tp in cons.assignment():
            pos = await cons.position(tp)
            await cons.commit({tp: pos + 1})
    except Exception as e:  # noqa: BLE001 — logged; the loop resumes from the committed position either way
        log.warning("could not step over the poison record: %s", e)


async def run_ledger():
    """A148: process's approval records (audit topic) feed check ⑤. Its own consumer so a command waiting for its record
    never blocks the record it is waiting for."""
    cons = await make_consumer([topics.K_AUDIT], group="cmd-gateway-ledger", from_latest=True)
    log.info("consuming audit for approval ledger records")
    async for rec in cons:
        result = gw.record_approval(gstate, rec.value)
        if result == "kept":
            state["approvals_recorded"] += 1
        elif result == "conflict":
            state["approval_conflicts"] += 1
            log.warning("approval record for %s differs from the one already kept; the first stays",
                        (rec.value.get("detail") or {}).get("cmdId"))


async def relay_alert(value) -> None:
    try:
        alert = schemas.alert_record(value)
    except schemas.RecordError as exc:
        _malformed("alerts", exc)
        return
    display = board.apply(alert)
    if not link.publish(topics.mqtt_alert(topics.asset_key(alert["asset"])), json.dumps(display, ensure_ascii=False), qos=1, retain=True):
        state["alert_relay_failed"] += 1     # 건강(/healthz)에 보인다 — 끊긴 MQTT 는 link 가 503
        log.error("alert %s %s %s was not published to the plant board: mqtt not connected", alert["asset"], alert["state"], alert["alertId"])
        return
    c_alerts.inc(state=alert["state"])
    state["alerts_relayed"] += 1
    log.info("alert %s %s %s -> %s", alert["asset"], alert["state"], alert["alertId"], display["display_text"])


async def _await_ledger(cmd_id: str) -> None:
    deadline = time.monotonic() + APPROVAL_GRACE_S
    while cmd_id not in gstate.approvals and time.monotonic() < deadline:
        await asyncio.sleep(0.1)


async def handle_command(prod, v) -> gw.Decision:
    if isinstance(v, dict) and isinstance(v.get("cmdId"), str) and v["cmdId"] not in gstate.approvals:
        await _await_ledger(v["cmdId"])       # the record is published first; this only covers cross-topic reordering
    d = gw.validate(v, gstate, now())
    cmd = v if isinstance(v, dict) else {}
    asset = cmd.get("asset") if cmd.get("asset") in topics.ASSETS else None
    entry = {"t": now_iso(), "cmdId": cmd.get("cmdId"), "asset": asset, "incident": cmd.get("incident"),
             "ok": d.ok, "check": d.check, "reason": d.reason}
    key = topics.asset_key(asset) if asset else None
    if d.ok and not link.publish(topics.mqtt_cmd_auto(key), json.dumps(d.mqtt_payload), qos=1):
        d = gw.Decision(False, gw.PUBLISH_CHECK, "mqtt broker did not take the command (not connected)", None)
        entry.update(ok=False, check=d.check, reason=d.reason)
    decisions.appendleft(entry)
    c_dec.inc(result="PASS" if d.ok else "REJECT", check=d.check)
    if d.ok:
        state["forwarded"] += 1
        log.info("cmd %s -> %s PASS %s", cmd["cmdId"], topics.mqtt_cmd_auto(key), d.mqtt_payload["writes"])
        await delivery.send(prod, topics.K_AUDIT, key=key, value={
            "t": now_iso(), "incident": cmd.get("incident"), "asset": asset, "actor": "cmd-gateway", "event": "CMD_FORWARDED",
            "detail": {"cmdId": cmd["cmdId"], "writes": d.mqtt_payload["writes"], "checks": list(gw.CHECKS), "command": cmd}})
    else:
        state["rejected"] += 1
        log.warning("cmd %s REJECTED at %s: %s", entry["cmdId"], d.check, d.reason)
        await delivery.send(prod, topics.K_AUDIT, key=key, value={
            "t": now_iso(), "incident": entry["incident"] if isinstance(entry["incident"], str) else None, "asset": asset,
            "actor": "cmd-gateway", "event": "CMD_REJECTED",
            "detail": {"cmdId": entry["cmdId"] if isinstance(entry["cmdId"], str) else None, "check": d.check,
                       "reason": d.reason, "reason_text": gw.CHECK_TEXT[d.check]}})
    return d


def health() -> dict:
    recent = time.time() - state.get("command_last_error_at", 0) < 60
    return {**{k: v for k, v in state.items() if k != "command_last_error_at"}, **link.health(), **delivery.health(),
            "ok": link.healthy() and state["kafka"] and delivery.healthy() and not recent and not state.get("consumer_dead", False)}


app = make_app("cmd-gateway (L3 DMZ: validated downlink IT -> OT)", reg, health)


def _watch(task):
    """If a consume loop ever exits, /healthz reports it (503) instead of looking healthy while doing nothing."""
    state["consumer_dead"] = True
    state["consumer_error"] = repr(task.exception()) if not task.cancelled() and task.exception() else "exited"
    log.error("consumer task ended: %s", state["consumer_error"])


async def _main():
    prod = await make_producer()
    state["kafka"] = True
    await asyncio.gather(run(prod), run_ledger())


@app.on_event("startup")
async def _startup():
    link.start()
    asyncio.create_task(_main()).add_done_callback(_watch)


@app.get("/api/gateway/log")
def get_log():
    return list(decisions)


@app.get("/api/gateway/status")
def get_status():
    return {"plc_status": gstate.last_status, "seen_cmd_ids": list(gstate.seen_cmd_ids)[-10:],
            "approvals_known": list(gstate.approvals)[-10:], "alerts_active": board.active, **health()}
