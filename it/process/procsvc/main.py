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
book: dict[str, dict] = {}          # action-card decisions (L9, ontology v2)
audit_log: list[dict] = []
plant_status: dict[str, dict] = {}   # latest plant.status per asset (PLC mode / state for the agent's DMN facts)
uploads: list[dict] = []             # manual ingestion history (this process run)
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


INCIDENT_Q = """
MERGE (i:Incident {id: $id}) SET i.alertId = $alert, i.openedAt = datetime($created)
WITH i OPTIONAL MATCH (a:Asset {code: $asset}) FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (i)-[:ON_ASSET]->(a))
WITH i OPTIONAL MATCH (p:AnomalyPattern {code: $pattern}) FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (i)-[:RAISED_BY]->(p))
WITH i OPTIONAL MATCH (c:Cause {id: $cause}) FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END | MERGE (i)-[:DIAGNOSED_AS]->(c))
"""


def _incident_params(inc: machine.Incident) -> dict:
    card = inc.card or {}
    return {"id": inc.id, "alert": inc.alert_id, "created": inc.created, "asset": inc.asset,
            "pattern": (card.get("alert") or {}).get("pattern"), "cause": card.get("topCause")}


def record_incident(inc: machine.Incident) -> None:
    """Write the case back into the ontology v2 (Incident -ON_ASSET-> Asset, -RAISED_BY-> AnomalyPattern, -DIAGNOSED_AS-> Cause)."""
    try:
        _q(INCIDENT_Q, **_incident_params(inc))
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
        if rec.topic == topics.K_STATUS and v.get("asset"):
            plant_status[v["asset"]] = v
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
    # decisions made on the v1 ontology (Scenario / Option) cannot be shown or executed any more
    book.update({k: d for k, d in saved_book.items() if d.get("schema") == "v2"})
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


@app.get("/api/plant/{asset}/status")
def get_plant_status(asset: str):
    """Latest plant.status (PLC mode · state · last ACK) — the agent's source for the DMN facts plc_mode / plc_state."""
    st = plant_status.get(asset)
    if not st:
        raise HTTPException(404, f"no plant.status seen for {asset} yet")
    return st


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


# atomic system transactions of an SOP skill -> the enterprise-sim job that performs them
TX_JOBS = {"WO_CREATE": "skill:schedule-maintenance", "PR_CREATE": "skill:procure-part"}


def exec_skill(d: dict, item: dict) -> dict:
    """POST one approved system transaction (CMMS work order, ERP purchase request) of the chosen SOP skill."""
    opt = next(o for o in d["options"] if o["id"] == d["chosen"])
    job = TX_JOBS.get(item.get("code"))
    out = {"skill": item["skill"], "code": item.get("code"), "system": item.get("system")}
    if not job:
        return out | {"ok": False, "error": f"실행할 수 없는 트랜잭션 {item.get('code')}"}
    if item["code"] == "WO_CREATE":
        params = {"task": f"{opt.get('sopId')} {opt.get('name')} → 작업지시 {item.get('value')}",
                  "window": "야간 정비창" if "night" in opt["id"] else "즉시"}
    else:
        params = {"supplier": item.get("value") or "sup:b", "part": opt.get("name")}
    body = {"decision": d["id"], "option": opt["id"], "skill": job, "system": item.get("system"), "asset": d.get("asset"),
            "by": d.get("approvedBy"), "params": params}
    try:
        req = urllib.request.Request(ENTERPRISE_URL + "/api/exec", data=json.dumps(body, ensure_ascii=False).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            tx = json.loads(r.read())
        return out | {"ok": True, "ref": tx.get("ref"), "detail": tx.get("detail")}
    except Exception as e:  # noqa: BLE001
        return out | {"ok": False, "error": str(e)[:200]}


DECISION_CASE_Q = """
MERGE (x:DecisionCase {id: $id}) SET x.decidedAt = datetime($at), x.reason = $reason, x.followedRecommendation = $followed
WITH x MATCH (d:Decision {id: 'dec:rank-actions'}) MERGE (x)-[:INSTANCE_OF]->(d)
WITH x OPTIONAL MATCH (s:Skill {id: $skill}) FOREACH (_ IN CASE WHEN s IS NULL THEN [] ELSE [1] END | MERGE (x)-[:CHOSE]->(s))
WITH x OPTIONAL MATCH (r:Role {id: $role}) FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (x)-[:DECIDED_BY]->(r))
WITH x OPTIONAL MATCH (i:Incident {id: $incident}) FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END | MERGE (x)-[:FOR_INCIDENT]->(i))
"""


def record_decision(d: dict) -> None:
    """Case memory in the ontology v2: DecisionCase -INSTANCE_OF-> Decision(dec:rank-actions), -CHOSE-> Skill, -DECIDED_BY-> Role,
    -FOR_INCIDENT-> Incident. The agent reads it back as a precedent of the same failure mode (T3-e)."""
    if d.get("state") not in ("APPROVED", "EXECUTED", "PARTIAL") or not d.get("chosen"):
        return
    try:
        inc = incidents.get((d.get("origin") or {}).get("incident") or "")
        if inc:
            _q(INCIDENT_Q, **_incident_params(inc))
        at = next((h["t"] for h in reversed(d.get("history") or []) if h.get("state") == "APPROVED"), d["created"])
        _q(DECISION_CASE_Q, id="case:" + d["id"], at=at, reason=d.get("reason") or "", followed=not d.get("override"),
           skill=d["chosen"], role=d.get("approvedRole"), incident=inc.id if inc else None)
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
           {"decision": d["id"], "cards": [o.get("sopId") for o in d.get("options", [])], "recommended": d.get("recommended")},
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
               {"decision": did, "skill": r["skill"], "code": r.get("code"), "system": r["system"], "ref": r.get("ref"), "detail": r.get("detail") or r.get("error")})
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
    # managed write transaction: the driver retries a dropped connection and transient errors
    drv = _kg()
    try:
        with drv.session() as s:
            return s.execute_write(lambda tx: [r.data() for r in tx.run(cypher, **params)])
    finally:
        drv.close()


SKILL_Q = """
MATCH (k:Skill) WHERE $id IS NULL OR k.id = $id
OPTIONAL MATCH (k)-[:APPROVED_BY]->(r:Role)
RETURN k.id AS id, k.sopId AS sopId, k.name AS name, k.description AS description, k.kind AS kind,
       CASE WHEN r IS NULL THEN null ELSE {id: r.id, name: r.name} END AS approver,
       COLLECT { MATCH (fm:FailureMode)-[m:MITIGATED_BY|REMEDIED_BY]->(k) RETURN {id: fm.id, name: fm.name, relation: type(m)} } AS failureModes,
       COLLECT { MATCH (k)-[:ADDRESSES]->(c:Cause) RETURN {id: c.id, name: c.name} } AS causes,
       COLLECT { MATCH (k)-[co:CONSISTS_OF]->(a:Action) RETURN {code: a.code, name: a.name, kind: a.kind, value: co.value} ORDER BY co.seq } AS actions,
       COLLECT { MATCH (k)-[:HAS_STEP]->(st:Step) OPTIONAL MATCH (st)-[:REFERS_TO]->(m:ManualSection)
                 RETURN {order: st.order, text: st.text, manual: m.ref} ORDER BY st.order } AS steps,
       COLLECT { MATCH (ru:Rule)-[:OUTPUTS|APPLIES_TO]->(k) RETURN {id: ru.id, effect: ru.effect, annotation: ru.annotation} } AS rules,
       COLLECT { MATCH (k)-[af:AFFECTS]->(x) RETURN {name: x.name, sign: af.sign} } AS affects,
       COLLECT { MATCH (sy)-[:HAS_SKILL]->(k) RETURN coalesce(sy.name, sy.id) } AS performers
ORDER BY sopId
"""


@app.get("/api/kg/skills")
async def kg_skills():
    return await asyncio.get_running_loop().run_in_executor(None, lambda: _q(SKILL_Q, id=None))


@app.get("/api/kg/catalog")
async def kg_catalog():
    """Choices for the skill editor and the manual upload: roles, failure modes (조치 방법은 고장 유형에 매칭된다)."""
    def run():
        return {"roles": _q("MATCH (r:Role) RETURN r.id AS id, r.name AS name, r.level AS level ORDER BY r.level DESC, r.id"),
                "failureModes": _q("MATCH (f:FailureMode) RETURN f.id AS id, f.name AS name ORDER BY f.id"),
                "manualSections": _q("MATCH (m:ManualSection) RETURN m.id AS id, m.title AS name ORDER BY m.id")}
    return await asyncio.get_running_loop().run_in_executor(None, run)


def _set_approver(sid: str, role: str | None) -> None:
    if role:
        _q("MATCH (k:Skill {id: $id}) OPTIONAL MATCH (k)-[old:APPROVED_BY]->() DELETE old", id=sid)
        _q("MATCH (k:Skill {id: $id}), (r:Role {id: $role}) MERGE (k)-[:APPROVED_BY]->(r)", id=sid, role=role)


def _write_sop_skill(sid: str, v: dict, steps: list[dict], performer: str) -> None:
    """Create / replace one SOP skill: Skill {sopId, kind} -HAS_STEP-> Step (-REFERS_TO-> ManualSection), matched to its failure mode.
    One SOP number belongs to one skill: a number another skill already uses is refused (its Step nodes would be shared)."""
    taken = _q("MATCH (k:Skill {sopId: $sop}) WHERE k.id <> $id RETURN k.id AS id, k.name AS name", sop=v["sopId"], id=sid)
    if taken:
        raise ValueError(f"SOP 번호 {v['sopId']}는 이미 '{taken[0]['name']}'({taken[0]['id']})의 것이다 — 다른 번호를 쓰세요")
    _q("""MERGE (k:Skill {id: $id}) SET k.sopId = $sop, k.name = $name, k.description = $description, k.kind = $kind""",
       id=sid, sop=v["sopId"], name=v["name"], description=v["description"] or f"{v['sopId']} 절차", kind=v["kind"])
    _q("MATCH (k:Skill {id: $id})-[:HAS_STEP]->(s:Step) DETACH DELETE s", id=sid)
    for st in steps:
        _q("""MATCH (k:Skill {id: $id}) MERGE (s:Step {id: $sid}) SET s.order = $order, s.text = $text MERGE (k)-[:HAS_STEP]->(s)
              WITH s OPTIONAL MATCH (m:ManualSection {id: $manual}) FOREACH (_ IN CASE WHEN m IS NULL THEN [] ELSE [1] END | MERGE (s)-[:REFERS_TO]->(m))""",
           id=sid, sid=f"{v['sopId']}/{st['order']}", order=st["order"], text=st["text"], manual=st.get("manual"))
    rel = "MITIGATED_BY" if v["relation"] == "MITIGATED_BY" else "REMEDIED_BY"
    _q(f"MATCH (f:FailureMode {{id: $fm}}), (k:Skill {{id: $id}}) MERGE (f)-[:{rel}]->(k)", fm=v["failureMode"], id=sid)
    _q("MATCH (s {id: $sys}), (k:Skill {id: $id}) WHERE s:System OR s:Role MERGE (s)-[:HAS_SKILL]->(k)", sys=performer, id=sid)
    _set_approver(sid, v.get("approver") or "role:maint-mgr")


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

    def run():
        _q("MATCH (k:Skill {id: $id}) SET k.name = $name, k.description = $description", id=sid, name=v["name"], description=v["description"])
        _set_approver(sid, v.get("approver"))
        return _q(SKILL_Q, id=sid)[0]
    out = await loop_.run_in_executor(None, run)
    _audit("-", by, "SKILL_EDITED", {"skill": sid, "name": v["name"]})
    return out


@app.post("/api/kg/skills")
async def kg_create_skill(body: dict):
    """New SOP skill (ontology v2): sopId + steps + the failure mode it treats (MITIGATED_BY | REMEDIED_BY)."""
    try:
        v = kgadmin.validate_skill(body, create=True)
    except ValueError as e:
        raise HTTPException(400, str(e))
    sid = kgadmin.skill_id(v["sopId"])
    by = str(body.get("by") or "지식 관리자")
    loop_ = asyncio.get_running_loop()
    if not await loop_.run_in_executor(None, lambda: _q("MATCH (f:FailureMode {id: $id}) RETURN f.id AS id", id=v["failureMode"])):
        raise HTTPException(400, f"unknown failure mode {v['failureMode']}")
    steps = [{"order": i + 1, "text": s} for i, s in enumerate(v["steps"])]
    performer = "sys:scada" if v["kind"] == "control" else "sys:cmms"
    try:
        out = await loop_.run_in_executor(None, lambda: (_write_sop_skill(sid, v, steps, performer), _q(SKILL_Q, id=sid)[0])[1])
    except ValueError as e:
        raise HTTPException(409, str(e))
    _audit("-", by, "SKILL_CREATED", {"skill": sid, "sop": v["sopId"], "failureMode": v["failureMode"]})
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
    # suggest the failure mode each SOP treats (the skill must be matched to one)
    fms = await loop_.run_in_executor(None, lambda: _q("MATCH (f:FailureMode) OPTIONAL MATCH (f)-[:OCCURS_IN]->(c:Component) "
                                                       "RETURN f.id AS id, f.name + ' ' + coalesce(c.name, '') AS name"))
    r = kgadmin.parse_manual(text, name, fms)
    for p in r["procedures"]:
        p["suggestedFailureMode"] = p.pop("suggestedAction", None)
    r["chars"] = len(text)
    return r


@app.post("/api/kg/manuals/commit")
async def kg_manual_commit(body: dict):
    """body = parse result (possibly edited in the UI) + {by, links: {procedureId: {failureMode, relation, kind}}}.
    Each procedure becomes one Skill (= SOP) with its steps, matched to the chosen failure mode; sections become ManualSection nodes."""
    secs, procs = body.get("sections") or [], body.get("procedures") or []
    if not secs and not procs:
        raise HTTPException(400, "적재할 절 · 절차가 없다")
    by, links = str(body.get("by") or "지식 관리자"), body.get("links") or {}
    for p_ in procs:
        ln = links.get(p_["id"]) or {}
        if not (ln.get("failureMode") or p_.get("suggestedFailureMode")):
            raise HTTPException(400, f"{p_['id']}: 조치 방법(SOP)은 고장 유형에 매칭되어야 한다 — 고장 유형을 고르세요")

    def run():
        for p_ in procs:                       # all-or-nothing: refuse before writing anything
            sop = str(p_["id"]).upper()
            taken = _q("MATCH (k:Skill {sopId: $sop}) WHERE k.id <> $id RETURN k.name AS name", sop=sop, id=kgadmin.skill_id(sop))
            if taken:
                raise ValueError(f"SOP 번호 {sop}는 이미 '{taken[0]['name']}'의 것이다 — 매뉴얼의 SOP 번호를 바꾸세요")
        for s_ in secs:
            _q("""MERGE (m:ManualSection {id: $ref}) SET m.ref = $ref, m.title = $title, m.excerpt = $excerpt
                  WITH m MATCH (k:KnowledgeSource {id: 'ks:manual-hm'}) MERGE (m)-[:PART_OF]->(k)""",
               ref=s_["ref"], title=s_["title"], excerpt=s_.get("excerpt", ""))
        made = {}
        for p_ in procs:
            ln = links.get(p_["id"]) or {}
            v = kgadmin.validate_skill({"name": p_["name"], "description": f"매뉴얼 {body.get('filename', '')}에서 등록한 SOP",
                                        "sopId": p_["id"], "steps": [s["text"] for s in p_.get("steps", [])],
                                        "failureMode": ln.get("failureMode") or p_.get("suggestedFailureMode"),
                                        "relation": ln.get("relation") or "REMEDIED_BY", "kind": ln.get("kind") or "work_order",
                                        "approver": "role:maint-mgr"}, create=True)
            sid = kgadmin.skill_id(v["sopId"])
            _write_sop_skill(sid, v, [{"order": s["order"], "text": s["text"], "manual": s.get("manual")} for s in p_.get("steps", [])],
                             "sys:scada" if v["kind"] == "control" else "sys:cmms")
            made[p_["id"]] = {"skill": sid, "failureMode": v["failureMode"], "relation": v["relation"]}
        return {"sections": len(secs), "procedures": len(procs), "steps": sum(len(p_.get("steps", [])) for p_ in procs), "skills": made}
    try:
        out = await asyncio.get_running_loop().run_in_executor(None, run)
    except ValueError as e:
        raise HTTPException(400, str(e))
    out.update(filename=body.get("filename", "manual"), by=by, t=now_iso())
    uploads.insert(0, out)
    del uploads[20:]
    _audit("-", by, "MANUAL_INGESTED", {k: out[k] for k in ("filename", "sections", "procedures", "steps")} | {"skills": list(out["skills"].values())})
    return out


@app.get("/api/kg/manuals")
async def kg_manuals():
    return uploads


# ---------------------------------------------------------------- HITL: one human decision for an equipment anomaly
class HitlDecideReq(BaseModel):
    decision: str
    option: str
    by: str = "승인자"
    role: str
    reason: str = ""
    fan_pct: float | None = None
    load_pct: float | None = None


def _commands_of(opt: dict, req: HitlDecideReq) -> list[dict]:
    """The chosen SOP skill's PLC commands as action.cmd items. A person may adjust fan / load inside the ontology range."""
    out = []
    for a in opt.get("actions") or []:
        if a.get("kind") != "command":
            continue
        item = {"code": a["code"]}
        if a.get("param"):
            v = a.get("value")
            if a["param"] == "fan_pct" and req.fan_pct is not None:
                v = req.fan_pct
            if a["param"] == "load_pct" and req.load_pct is not None:
                v = req.load_pct
            item[a["param"]] = v
        out.append(item)
    return out


@app.post("/api/incidents/{inc_id}/decide")
async def hitl_decide(inc_id: str, req: HitlDecideReq):
    """The operator picks one ranked action card (= one SOP skill of the failure mode). Its PLC commands go out through the
    incident (action.cmd -> gateway -> PLC); a card without commands closes the incident as 'no immediate command'. Its system
    transactions (CMMS work order, ERP purchase request) run in the enterprise systems. The choice is written back to the
    ontology as a DecisionCase and becomes a precedent for the next decision of the same failure mode."""
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
    commands = _commands_of(opt, req)
    try:
        candidate = copy.deepcopy(d)
        plan = declib.approve(candidate, req.option, req.by, req.role, req.reason)
        if commands:                          # validate the command before consuming the human decision
            machine._validate_actions(inc, commands)
    except PermissionError as e:
        _audit(inc.asset, req.by, "DECISION_DENIED", {"decision": d["id"], "option": req.option, "role": req.role, "reason": str(e)}, incident=inc_id)
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    d.update(candidate)
    _audit(inc.asset, req.by, "DECISION_APPROVED", {"decision": d["id"], "option": req.option, "sop": opt.get("sopId"), "role": req.role,
                                                     "override": d["override"], "reason": req.reason, "via": "HITL 조치 카드 선택"}, incident=inc_id)
    cmd = None
    try:
        if commands:
            cmd = machine.on_approve(inc, req.by, commands, now(), Fx(inc), time_scale=TIME_SCALE)
        else:
            machine.on_reject(inc, req.by, f"HITL 판단: '{opt.get('sopId')} {opt['name']}' 선택 — 즉시 제어 없음", Fx(inc))
    except ValueError as e:
        raise HTTPException(400, str(e))
    _after(inc)
    loop_ = asyncio.get_running_loop()
    results = [await loop_.run_in_executor(None, exec_skill, d, item) for item in plan["enterprise"]]
    declib.record_execution(d, results, plan)
    persist()
    for r in results:
        _audit(inc.asset, "process", "SKILL_EXECUTED" if r["ok"] else "SKILL_FAILED",
               {"decision": d["id"], "skill": r["skill"], "code": r.get("code"), "system": r["system"], "ref": r.get("ref"),
                "detail": r.get("detail") or r.get("error")}, incident=inc_id)
    loop_.run_in_executor(None, record_decision, d)
    return {"incident": inc.to_dict() | {"card": None}, "decision": {"id": d["id"], "state": d["state"], "executions": d["executions"]}, "cmd": cmd}
