"""process (L9): mini-BPMN engine. Guide card in -> human approval -> action.cmd -> ACK -> re-observe -> work order -> close.

Only this service may write action.cmd (the agent has no command authority). Timers are asyncio tasks;
the latest TS1 for the re-observation verdict comes from TimescaleDB.
"""
import asyncio
import copy
import json
import logging
import os
import urllib.request

import psycopg
from fastapi import HTTPException
from pydantic import BaseModel

from hydcommon import topics
from hydcommon.kafka import consumer as make_consumer, producer as make_producer
from hydcommon.metrics import Registry
from hydcommon.service import make_app
from hydcommon.timeutil import now, now_iso
from . import decisions as declib, definition, kgadmin, machine
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("process")
TIME_SCALE = float(os.getenv("TIME_SCALE", "20"))
PG_DSN = os.getenv("PG_DSN", "postgresql://hyd:hyd@timescaledb:5432/hyd")
ENTERPRISE_URL = os.getenv("ENTERPRISE_URL", "http://enterprise-sim:8095")

reg = Registry()
c_inc = reg.counter("process_incidents_total", "incidents by terminal state")
g_open = reg.gauge("process_open_incidents", "incidents not in a terminal state")
state = {"kafka": False, "incidents": 0}
incidents: dict[str, machine.Incident] = {}
book: dict[str, dict] = {}          # enterprise decisions (L9)
audit_log: list[dict] = []
producer = None
loop: asyncio.AbstractEventLoop | None = None
store = None


def persist():
    if store is not None:
        store.save(incidents, book, audit_log)


class Fx(machine.Effects):
    """Effects for one incident: publish to Kafka, keep an audit copy, schedule timers."""

    def __init__(self, inc: machine.Incident):
        self.inc = inc

    def emit_cmd(self, cmd: dict) -> None:
        persist()  # durable CMD_ISSUED before any external side effect
        asyncio.run_coroutine_threadsafe(producer.send(topics.K_CMD, key=topics.asset_key(cmd["asset"]), value=cmd), loop)

    def emit_audit(self, evt: dict) -> None:
        audit_log.insert(0, evt)
        del audit_log[500:]
        asyncio.run_coroutine_threadsafe(producer.send(topics.K_AUDIT, key=topics.asset_key(self.inc.asset), value=evt), loop)

    def set_timer(self, name: str, seconds: float) -> None:
        loop.call_soon_threadsafe(lambda: asyncio.create_task(fire_timer(self.inc.id, name, seconds)))


async def fire_timer(inc_id: str, name: str, seconds: float):
    await asyncio.sleep(seconds)
    inc = incidents.get(inc_id)
    if not inc:
        return
    ts1 = await asyncio.get_running_loop().run_in_executor(None, latest_ts1, inc.asset) if name == "reobs" else None
    machine.on_timer(inc, name, now(), ts1, Fx(inc), time_scale=TIME_SCALE)
    _after(inc)


def latest_ts1(asset: str) -> float | None:
    try:
        with psycopg.connect(PG_DSN, autocommit=True, connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("SELECT value FROM tag_1s WHERE asset=%s AND name='TS1' ORDER BY time DESC LIMIT 1", (asset,))
            row = cur.fetchone()
            return float(row[0]) if row else None
    except Exception as e:  # noqa: BLE001
        log.warning("latest_ts1 failed: %s", e)
        return None


def _after(inc: machine.Incident):
    persist()
    if inc.state in definition.TERMINAL:
        c_inc.inc(state=inc.state)
        if inc.state == "CLOSED":
            asyncio.get_running_loop().run_in_executor(None, record_incident, inc)
    g_open.set(sum(1 for i in incidents.values() if i.state not in definition.TERMINAL))


def record_incident(inc: machine.Incident) -> None:
    """Write the case back into the ontology (Incident -TRIGGERED_BY-> Alert, -DIAGNOSED_AS-> Cause, -RESOLVED_BY-> Action)."""
    try:
        from neo4j import GraphDatabase
        user, pwd = os.getenv("NEO4J_AUTH", "neo4j/hydpass123").split("/", 1)
        drv = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://neo4j:7687"), auth=(user, pwd))
        card = inc.card
        with drv.session() as s:
            s.run("""
                MERGE (i:Incident {id: $id}) SET i.asset=$asset, i.state=$state, i.created=$created, i.closed=$closed, i.approvedBy=$by
                MERGE (al:Alert {id: $alert}) SET al.pattern=$pattern
                MERGE (i)-[:TRIGGERED_BY]->(al)
                WITH i, al
                OPTIONAL MATCH (p:AnomalyPattern {code: $pattern}) FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (al)-[:INSTANCE_OF]->(p))
                WITH i
                OPTIONAL MATCH (c:Cause {id: $cause}) FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END | MERGE (i)-[:DIAGNOSED_AS]->(c))
                WITH i
                UNWIND $actions AS aid
                OPTIONAL MATCH (a:Action {id: aid}) FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (i)-[:RESOLVED_BY]->(a))
                """, id=inc.id, asset=inc.asset, state=inc.state, created=inc.created, closed=inc.closed, by=inc.approved_by,
                  alert=inc.alert_id, pattern=(card.get("alert") or {}).get("pattern"), cause=card.get("topCause"),
                  actions=[a.get("actionId") for a in card.get("recommended") or [] if a.get("actionId")])
        drv.close()
        log.info("incident %s recorded in ontology", inc.id)
    except Exception as e:  # noqa: BLE001
        log.warning("ontology record skipped: %s", e)


async def consume():
    global producer
    producer = await make_producer()
    cons = await make_consumer([topics.K_STATUS, topics.K_ALERTS], group="process", from_latest=True)
    state["kafka"] = True
    log.info("consuming plant.status (ACK) and alerts (CLEAR)")
    async for rec in cons:
        v = rec.value
        if not isinstance(v, dict) or "_raw" in v:
            log.warning("ignoring malformed record on %s", rec.topic)
            continue
        for inc in list(incidents.values()):
            if inc.state in definition.TERMINAL:
                continue
            try:
                if rec.topic == topics.K_STATUS and v.get("asset") == inc.asset:
                    machine.on_status(inc, v, now(), Fx(inc), time_scale=TIME_SCALE)
                elif rec.topic == topics.K_ALERTS:
                    machine.on_alert(inc, v, Fx(inc))
                _after(inc)
            except Exception as e:  # noqa: BLE001
                log.warning("record on %s failed for %s: %s", rec.topic, inc.id, e)


app = make_app("process (L9: mini-BPMN — approval, action.cmd, ACK, re-observation, work order)", reg,
               lambda: {**state, "ok": state["kafka"] and not state.get("consumer_dead", False)})


def _watch(task):
    """If the consume loop ever exits, /healthz reports it (503) instead of looking healthy while doing nothing."""
    state["consumer_dead"] = True
    state["consumer_error"] = repr(task.exception()) if not task.cancelled() and task.exception() else "exited"
    log.error("consumer task ended: %s", state["consumer_error"])


@app.on_event("startup")
async def _startup():
    global loop, store
    loop = asyncio.get_running_loop()
    store = Store(os.getenv("PROCESS_STATE_PATH", "/data/process.sqlite3"))
    saved_incidents, saved_book, saved_audit = store.restore()
    incidents.update(saved_incidents)
    book.update(saved_book)
    audit_log[:] = saved_audit
    state["incidents"] = len(incidents)
    persist()
    asyncio.create_task(consume()).add_done_callback(_watch)


class ApproveReq(BaseModel):
    approvedBy: str = "OP-17"
    actions: list[dict]


class RejectReq(BaseModel):
    by: str = "OP-17"
    reason: str = ""


@app.post("/api/incidents")
async def create_incident(card: dict):   # async: mutates incidents on the loop thread, like consume()
    if not card.get("alert") or not card.get("recommended"):
        raise HTTPException(400, "card needs alert and recommended actions")
    alert_id = card["alert"].get("alertId")
    for inc in incidents.values():
        if inc.alert_id == alert_id and inc.state not in definition.TERMINAL:
            return {"id": inc.id, "state": inc.state, "duplicate": True}
    inc = machine.Incident.from_card(machine.new_incident_id(), card)
    machine.on_card(inc)
    incidents[inc.id] = inc
    state["incidents"] += 1
    Fx(inc).emit_audit({"t": inc.created, "incident": inc.id, "asset": inc.asset, "actor": "agent", "event": "GUIDE_SUBMITTED",
                        "detail": {"alertId": alert_id, "topCause": card.get("topCause"), "citations": len(card.get("citations") or [])}})
    _after(inc)
    log.info("incident %s created for %s", inc.id, alert_id)
    return {"id": inc.id, "state": inc.state}


@app.get("/api/incidents")
def list_incidents():
    return [i.to_dict() | {"card": None} for i in sorted(incidents.values(), key=lambda i: i.created, reverse=True)]


@app.get("/api/incidents/{inc_id}")
def get_incident(inc_id: str):
    inc = incidents.get(inc_id)
    if not inc:
        raise HTTPException(404, "no such incident")
    return inc.to_dict()


@app.post("/api/incidents/{inc_id}/approve")
async def approve(inc_id: str, req: ApproveReq):
    inc = incidents.get(inc_id)
    if not inc:
        raise HTTPException(404, "no such incident")
    try:
        cmd = machine.on_approve(inc, req.approvedBy, req.actions, now(), Fx(inc), time_scale=TIME_SCALE)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _after(inc)
    return {"id": inc.id, "state": inc.state, "cmd": cmd}


@app.post("/api/incidents/{inc_id}/reject")
async def reject(inc_id: str, req: RejectReq):
    inc = incidents.get(inc_id)
    if not inc:
        raise HTTPException(404, "no such incident")
    try:
        machine.on_reject(inc, req.by, req.reason, Fx(inc))
    except ValueError as e:
        raise HTTPException(400, str(e))
    _after(inc)
    return {"id": inc.id, "state": inc.state}


@app.get("/api/audit")
def get_audit():
    return audit_log[:100]


@app.get("/api/definition")
def get_definition():
    return definition.as_json() | {"time_scale": TIME_SCALE}


@app.get("/api/summary")
def summary():
    return {"open": [i.to_dict() | {"card": None} for i in incidents.values() if i.state not in definition.TERMINAL],
            "total": len(incidents), "time_scale": TIME_SCALE}


# ---------------------------------------------------------------- enterprise decisions (L7 -> L8 -> L9)
class DecisionApproveReq(BaseModel):
    option: str
    by: str = "승인자"
    role: str
    reason: str = ""


class DecisionRejectReq(BaseModel):
    by: str = "승인자"
    reason: str = ""


def _audit(asset: str, actor: str, event: str, detail: dict, incident: str | None = None):
    evt = {"t": now_iso(), "incident": incident, "asset": asset, "actor": actor, "event": event, "detail": detail}
    audit_log.insert(0, evt)
    del audit_log[500:]
    persist()
    if producer is not None:
        asyncio.get_running_loop().create_task(producer.send(topics.K_AUDIT, key=topics.asset_key(asset if asset in ("HYD-01", "HYD-02", "HYD-03") else "HYD-01"), value=evt))


def exec_skill(d: dict, item: dict) -> dict:
    """POST one approved enterprise skill to the system that runs it (ERP/MES/CMMS/QMS/EMS)."""
    opt = next(o for o in d["options"] if o["id"] == d["chosen"])
    params = dict(opt.get("params") or {})
    if item["skill"] == "skill:procure-part":
        params["supplier"] = {"opt:sc2-a": "sup:a", "opt:sc2-b": "sup:b", "opt:sc2-c": "sup:c"}.get(opt["id"], "sup:b")
    body = {"decision": d["id"], "option": opt["id"], "skill": item["skill"], "system": item["system"], "asset": d.get("asset"),
            "by": d.get("approvedBy"), "params": params}
    try:
        req = urllib.request.Request(ENTERPRISE_URL + "/api/exec", data=json.dumps(body, ensure_ascii=False).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            tx = json.loads(r.read())
        return {"skill": item["skill"], "system": item["system"], "ok": True, "ref": tx.get("ref"), "detail": tx.get("detail")}
    except Exception as e:  # noqa: BLE001
        return {"skill": item["skill"], "system": item["system"], "ok": False, "error": str(e)[:200]}


def record_decision(d: dict) -> None:
    """Case memory in the ontology: Decision -ABOUT-> Scenario, -DECIDED-> Option, -APPROVED_BY-> Role, -FOR-> Incident."""
    try:
        from neo4j import GraphDatabase
        user, pwd = os.getenv("NEO4J_AUTH", "neo4j/hydpass123").split("/", 1)
        drv = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://neo4j:7687"), auth=(user, pwd))
        with drv.session() as s:
            s.run("""
                MERGE (x:Decision {id: $id}) SET x.state=$state, x.asset=$asset, x.created=$created, x.approvedBy=$by, x.override=$override,
                    x.recommended=$rec, x.name = $name, x.reason = $reason
                WITH x MATCH (sc:Scenario {id: $scenario}) MERGE (x)-[:ABOUT]->(sc)
                WITH x OPTIONAL MATCH (o:Option {id: $option}) FOREACH (_ IN CASE WHEN o IS NULL THEN [] ELSE [1] END | MERGE (x)-[:DECIDED]->(o))
                WITH x OPTIONAL MATCH (r:Role {id: $role}) FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (x)-[:APPROVED_BY]->(r))
                WITH x OPTIONAL MATCH (i:Incident {id: $incident}) FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END | MERGE (x)-[:FOR]->(i))
                """, id=d["id"], state=d["state"], asset=d.get("asset"), created=d["created"], by=d.get("approvedBy"), override=d.get("override"),
                  rec=d.get("recommended"), name=f"판단 {d['id']}", reason=d.get("reason") or "", scenario=(d.get("scenario") or {}).get("id"), option=d.get("chosen"),
                  role=d.get("approvedRole"), incident=(d.get("origin") or {}).get("incident"))
        drv.close()
    except Exception as e:  # noqa: BLE001
        log.warning("decision record skipped: %s", e)


@app.post("/api/decisions")
async def create_decision(payload: dict):
    if not payload.get("id") or not payload.get("options"):
        raise HTTPException(400, "decision needs id and options")
    if payload["id"] in book:
        d = book[payload["id"]]
        return {"id": d["id"], "state": d["state"], "duplicate": True}
    d = declib.new(payload)
    book[d["id"]] = d
    _audit(d.get("asset") or "-", "agent", "DECISION_SUBMITTED",
           {"decision": d["id"], "scenario": (d.get("scenario") or {}).get("id"), "recommended": d.get("recommended")},
           incident=(d.get("origin") or {}).get("incident"))
    return {"id": d["id"], "state": d["state"]}


@app.get("/api/decisions")
def list_decisions():
    return [{k: d.get(k) for k in ("id", "created", "scenario", "asset", "state", "recommended", "chosen", "approvedBy", "approvedRole",
                                    "override", "origin", "applicable")} for d in sorted(book.values(), key=lambda d: d["created"], reverse=True)]


@app.get("/api/decisions/{did}")
def get_decision(did: str):
    d = book.get(did)
    if not d:
        raise HTTPException(404, "no such decision")
    return d


@app.post("/api/decisions/{did}/approve")
async def approve_decision(did: str, req: DecisionApproveReq):
    d = book.get(did)
    if not d:
        raise HTTPException(404, "no such decision")
    try:
        plan = declib.approve(d, req.option, req.by, req.role, req.reason)
    except PermissionError as e:
        _audit(d.get("asset") or "-", req.by, "DECISION_DENIED", {"decision": did, "option": req.option, "role": req.role, "reason": str(e)})
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    _audit(d.get("asset") or "-", req.by, "DECISION_APPROVED",
           {"decision": did, "option": req.option, "role": req.role, "override": d["override"], "reason": req.reason}, incident=(d.get("origin") or {}).get("incident"))
    loop_ = asyncio.get_running_loop()
    results = [await loop_.run_in_executor(None, exec_skill, d, item) for item in plan["enterprise"]]
    declib.record_execution(d, results, plan)
    persist()
    for r in results:
        _audit(d.get("asset") or "-", "process", "SKILL_EXECUTED" if r["ok"] else "SKILL_FAILED",
               {"decision": did, "skill": r["skill"], "system": r["system"], "ref": r.get("ref"), "detail": r.get("detail") or r.get("error")})
    loop_.run_in_executor(None, record_decision, d)
    return {"id": did, "state": d["state"], "executions": d["executions"]}


@app.post("/api/decisions/{did}/reject")
async def reject_decision(did: str, req: DecisionRejectReq):
    d = book.get(did)
    if not d:
        raise HTTPException(404, "no such decision")
    try:
        declib.reject(d, req.by, req.reason)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _audit(d.get("asset") or "-", req.by, "DECISION_REJECTED", {"decision": did, "reason": req.reason})
    asyncio.get_running_loop().run_in_executor(None, record_decision, d)
    return {"id": did, "state": d["state"]}


# ---------------------------------------------------------------- knowledge administration (humans edit the ontology through L9)
def _kg():
    from neo4j import GraphDatabase
    user, pwd = os.getenv("NEO4J_AUTH", "neo4j/hydpass123").split("/", 1)
    return GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://neo4j:7687"), auth=(user, pwd))


def _q(cypher: str, **params) -> list[dict]:
    drv = _kg()
    try:
        with drv.session() as s:
            return [r.data() for r in s.run(cypher, **params)]
    finally:
        drv.close()


SKILL_Q = """
MATCH (k:Skill) WHERE $id IS NULL OR k.id = $id
OPTIONAL MATCH (k)-[:EXECUTED_VIA]->(sy:System)
OPTIONAL MATCH (k)-[:EXECUTED_IN]->(bp:BusinessProcess)
OPTIONAL MATCH (k)-[:APPROVED_BY]->(r:Role)
RETURN k.id AS id, k.name AS name, k.description AS description, k.detail AS detail, k.category AS category, coalesce(k.edited, false) AS edited,
       k.updatedBy AS updatedBy, k.updatedAt AS updatedAt,
       CASE WHEN sy IS NULL THEN null ELSE {id: sy.id, name: sy.name} END AS system,
       CASE WHEN bp IS NULL THEN null ELSE {id: bp.id, name: bp.name} END AS process,
       CASE WHEN r IS NULL THEN null ELSE {id: r.id, name: r.name} END AS approver,
       COLLECT { MATCH (p:Policy)-[:GOVERNS]->(k) RETURN {id: p.id, name: p.name, kind: p.kind} } AS policies,
       COLLECT { MATCH (k)-[:REQUIRES_INFO]->(i:InfoType)-[:HELD_IN]->(s2:System) RETURN {id: i.id, name: i.name, system: s2.name} } AS infos,
       COLLECT { MATCH (k)-[:IMPLEMENTS]->(a:Action) RETURN {id: a.id, name: a.name} } AS actions,
       COLLECT { MATCH (o:Option)-[:USES_SKILL]->(k) MATCH (sc:Scenario)-[:HAS_OPTION]->(o) RETURN {option: o.name, scenario: sc.name} } AS usedBy
ORDER BY id
"""


@app.get("/api/kg/skills")
async def kg_skills():
    return await asyncio.get_running_loop().run_in_executor(None, lambda: _q(SKILL_Q, id=None))


@app.get("/api/kg/catalog")
async def kg_catalog():
    """Choices for the skill editor: systems, business processes, roles, actions."""
    def run():
        return {"systems": _q("MATCH (s:System) RETURN s.id AS id, s.name AS name ORDER BY s.id"),
                "processes": _q("MATCH (p:BusinessProcess) RETURN p.id AS id, p.name AS name ORDER BY p.id"),
                "roles": _q("MATCH (r:Role) RETURN r.id AS id, r.name AS name, r.level AS level ORDER BY r.level DESC, r.id"),
                "actions": _q("MATCH (a:Action) RETURN a.id AS id, a.name AS name ORDER BY a.id")}
    return await asyncio.get_running_loop().run_in_executor(None, run)


def _save_skill(sid: str, v: dict, by: str) -> dict:
    _q("""MERGE (k:Skill {id: $id})
          SET k.name = $name, k.description = $description, k.detail = $detail, k.edited = true, k.updatedBy = $by, k.updatedAt = $t,
              k.category = coalesce(k.category, '사용자 추가')""", id=sid, by=by, t=now_iso(), name=v["name"], description=v["description"], detail=v["detail"])
    for rel, label, key in (("EXECUTED_VIA", "System", "system"), ("EXECUTED_IN", "BusinessProcess", "process"), ("APPROVED_BY", "Role", "approver")):
        if v.get(key):
            _q(f"MATCH (k:Skill {{id: $id}}) OPTIONAL MATCH (k)-[old:{rel}]->() DELETE old", id=sid)
            _q(f"MATCH (k:Skill {{id: $id}}), (x:{label} {{id: $to}}) MERGE (k)-[:{rel}]->(x)", id=sid, to=v[key])
    return _q(SKILL_Q, id=sid)[0]


@app.put("/api/kg/skills/{sid}")
async def kg_update_skill(sid: str, body: dict):
    try:
        v = kgadmin.validate_skill(body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    loop_ = asyncio.get_running_loop()
    if not await loop_.run_in_executor(None, lambda: _q("MATCH (k:Skill {id: $id}) RETURN k.id AS id", id=sid)):
        raise HTTPException(404, "no such skill")
    by = str(body.get("by") or "지식 관리자")
    out = await loop_.run_in_executor(None, lambda: _save_skill(sid, v, by))
    _audit("-", by, "SKILL_EDITED", {"skill": sid, "name": v["name"]})
    return out


@app.post("/api/kg/skills")
async def kg_create_skill(body: dict):
    try:
        v = kgadmin.validate_skill(body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    sid = kgadmin.skill_id(v["name"])
    by = str(body.get("by") or "지식 관리자")
    out = await asyncio.get_running_loop().run_in_executor(None, lambda: _save_skill(sid, v, by))
    _audit("-", by, "SKILL_CREATED", {"skill": sid, "name": v["name"]})
    return out


def _extract_text(filename: str, data_b64: str) -> str:
    import base64
    import io
    raw = base64.b64decode(data_b64 or "")
    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


@app.post("/api/kg/manuals/preview")
async def kg_manual_preview(body: dict):
    name = str(body.get("filename") or "manual.md")
    loop_ = asyncio.get_running_loop()
    try:
        text = await loop_.run_in_executor(None, lambda: _extract_text(name, body.get("data", "")))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"파일을 읽을 수 없다: {e}")
    actions = await loop_.run_in_executor(None, lambda: _q("MATCH (a:Action) RETURN a.id AS id, a.name AS name, a.kind AS kind"))
    r = kgadmin.parse_manual(text, name, actions)
    r["chars"] = len(text)
    return r


@app.post("/api/kg/manuals/commit")
async def kg_manual_commit(body: dict):
    """body = parse result (possibly edited in the UI) + {by, links: {procedureId: actionId}}"""
    secs, procs = body.get("sections") or [], body.get("procedures") or []
    if not secs and not procs:
        raise HTTPException(400, "적재할 절 · 절차가 없다")
    by, links = str(body.get("by") or "지식 관리자"), body.get("links") or {}
    uid = "UP-" + now_iso()[:19].replace(":", "").replace("-", "")

    def run():
        _q("MERGE (u:ManualUpload {id: $id}) SET u.name = $name, u.filename = $name, u.by = $by, u.t = $t", id=uid, name=body.get("filename", "manual"), by=by, t=now_iso())
        for s_ in secs:
            _q("""MERGE (m:ManualSection {id: $ref}) SET m.ref = $ref, m.title = $title, m.excerpt = $excerpt, m.source = $src
                  WITH m MATCH (u:ManualUpload {id: $uid}) MERGE (u)-[:INGESTED]->(m)""", ref=s_["ref"], title=s_["title"], excerpt=s_.get("excerpt", ""), src=body.get("filename"), uid=uid)
        for p_ in procs:
            _q("""MERGE (pr:Procedure {id: $id}) SET pr.name = $name, pr.source = $src
                  WITH pr MATCH (u:ManualUpload {id: $uid}) MERGE (u)-[:INGESTED]->(pr)""", id=p_["id"], name=p_["name"], src=body.get("filename"), uid=uid)
            for st in p_.get("steps", []):
                _q("""MATCH (pr:Procedure {id: $pid}) MERGE (s:Step {id: $sid}) SET s.order = $order, s.text = $text, s.manual = $manual
                      MERGE (pr)-[:HAS_STEP]->(s)
                      WITH s OPTIONAL MATCH (m:ManualSection {id: $manual}) FOREACH (_ IN CASE WHEN m IS NULL THEN [] ELSE [1] END | MERGE (s)-[:REFERS_TO]->(m))""",
                   pid=p_["id"], sid=f"{p_['id']}/{st['order']}", order=st["order"], text=st["text"], manual=st.get("manual"))
            act = links.get(p_["id"]) or p_.get("suggestedAction")
            if act:
                _q("MATCH (a:Action {id: $a}), (pr:Procedure {id: $p}) MERGE (a)-[:FOLLOWS]->(pr)", a=act, p=p_["id"])
        return {"upload": uid, "sections": len(secs), "procedures": len(procs), "steps": sum(len(p_.get("steps", [])) for p_ in procs),
                "links": {p_["id"]: links.get(p_["id"]) or p_.get("suggestedAction") for p_ in procs}}
    out = await asyncio.get_running_loop().run_in_executor(None, run)
    _audit("-", by, "MANUAL_INGESTED", out)
    return out


@app.get("/api/kg/manuals")
async def kg_manuals():
    return await asyncio.get_running_loop().run_in_executor(None, lambda: _q(
        "MATCH (u:ManualUpload) RETURN u.id AS id, u.filename AS filename, u.by AS by, u.t AS t, "
        "COUNT { (u)-[:INGESTED]->(:ManualSection) } AS sections, COUNT { (u)-[:INGESTED]->(:Procedure) } AS procedures ORDER BY t DESC LIMIT 20"))


# ---------------------------------------------------------------- HITL: one human decision for an equipment anomaly
class HitlDecideReq(BaseModel):
    decision: str
    option: str
    by: str = "승인자"
    role: str
    reason: str = ""
    fan_pct: float | None = None
    load_pct: float | None = None


@app.post("/api/incidents/{inc_id}/decide")
async def hitl_decide(inc_id: str, req: HitlDecideReq):
    """The operator picks one ranked option. Its enterprise skills run in ERP/MES/CMMS/…; if it contains the immediate
    cooling skill the incident is approved (action.cmd -> gateway -> PLC), otherwise the incident is closed as
    'no immediate command' with the chosen option as the reason. The choice is written back to the ontology."""
    inc = incidents.get(inc_id)
    d = book.get(req.decision)
    if not inc or not d:
        raise HTTPException(404, "no such incident or decision")
    if inc.state != "AWAITING_APPROVAL":
        raise HTTPException(409, f"incident is {inc.state}")
    if (d.get("origin") or {}).get("incident") != inc_id or d.get("asset") != inc.asset:
        raise HTTPException(400, "decision does not belong to this incident")
    opt = next((o for o in d.get("options", []) if o["id"] == req.option), None)
    if opt is None:
        raise HTTPException(400, "unknown option")
    cooling = any(s["id"] == "skill:cooling-adjust" for s in opt.get("skills") or [])
    try:
        candidate = copy.deepcopy(d)
        plan = declib.approve(candidate, req.option, req.by, req.role, req.reason)
        # Validate the command before consuming the human decision.
        if cooling:
            proposed = []
            for action in (inc.card or {}).get("recommended") or []:
                if action.get("code") == "FAN_BOOST":
                    proposed.append({"code": "FAN_BOOST", "fan_pct": req.fan_pct if req.fan_pct is not None else action.get("value", 100)})
                elif action.get("code") == "REDUCE_LOAD":
                    proposed.append({"code": "REDUCE_LOAD", "load_pct": req.load_pct if req.load_pct is not None else action.get("value", 80)})
            machine._validate_actions(inc, proposed)
    except PermissionError as e:
        _audit(inc.asset, req.by, "DECISION_DENIED", {"decision": d["id"], "option": req.option, "role": req.role, "reason": str(e)}, incident=inc_id)
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    d.update(candidate)
    _audit(inc.asset, req.by, "DECISION_APPROVED", {"decision": d["id"], "option": req.option, "role": req.role, "override": d["override"],
                                                     "reason": req.reason, "via": "HITL 조치 의사결정"}, incident=inc_id)
    cmd = None
    if inc.state == "AWAITING_APPROVAL":
        try:
            if cooling:
                acts = []
                for a in (inc.card or {}).get("recommended") or []:
                    if a.get("code") == "FAN_BOOST":
                        acts.append({"code": "FAN_BOOST", "fan_pct": req.fan_pct if req.fan_pct is not None else a.get("value", 100)})
                    elif a.get("code") == "REDUCE_LOAD":
                        acts.append({"code": "REDUCE_LOAD", "load_pct": req.load_pct if req.load_pct is not None else a.get("value", 80)})
                cmd = machine.on_approve(inc, req.by, acts, now(), Fx(inc), time_scale=TIME_SCALE)
            else:
                machine.on_reject(inc, req.by, f"HITL 판단: '{opt['name']}' 선택 — 즉시 제어 없음", Fx(inc))
        except ValueError as e:
            raise HTTPException(400, str(e))
        _after(inc)
    loop_ = asyncio.get_running_loop()
    results = [await loop_.run_in_executor(None, exec_skill, d, item) for item in plan["enterprise"]]
    declib.record_execution(d, results, plan)
    persist()
    for r in results:
        _audit(inc.asset, "process", "SKILL_EXECUTED" if r["ok"] else "SKILL_FAILED",
               {"decision": d["id"], "skill": r["skill"], "system": r["system"], "ref": r.get("ref"), "detail": r.get("detail") or r.get("error")}, incident=inc_id)
    loop_.run_in_executor(None, record_decision, d)
    return {"incident": inc.to_dict() | {"card": None}, "decision": {"id": d["id"], "state": d["state"], "executions": d["executions"]}, "cmd": cmd}
