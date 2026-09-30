"""agent (L8): alert -> data-trust check -> T1 causes -> evidence SQL -> T2 actions -> guide card -> guardrail -> process API.

The LangGraph/MCP/LiteLLM stack of the full architecture is collapsed into one process, but the discipline is kept:
tools are read-only, the only write is POST {PROCESS_URL}/api/incidents, and every step is recorded in the run trace.
"""
import asyncio
import json
import logging
import os
import urllib.request

from fastapi import HTTPException
from pydantic import BaseModel

from hydcommon import topics
from hydcommon.kafka import consumer as make_consumer
from hydcommon.metrics import Registry
from hydcommon.service import make_app
from . import card as cardlib, enterprise, guardrail, llm
from .runs import RunRegistry
from .tools import mcp_kg, mcp_prom, mcp_tsdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("agent")
PROCESS_URL = os.getenv("PROCESS_URL", "http://process:8080")

reg = Registry()
c_runs = reg.counter("agent_runs_total", "agent runs by status")
runs = RunRegistry()
state = {"kafka": False, "neo4j": False, "runs": 0, "llm": llm.available(), "llm_model": llm.MODEL}
kg: mcp_kg.KnowledgeGraph | None = None
tsdb = mcp_tsdb.TimeSeriesDB()
decisions = enterprise.DecisionRegistry()


def submit_card(card: dict) -> dict:
    req = urllib.request.Request(f"{PROCESS_URL}/api/incidents", data=json.dumps(card, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def pipeline(run) -> None:
    """Synchronous reasoning pipeline (runs in a worker thread)."""
    alert, asset = run.alert, run.asset
    try:
        # 1. data trust (mcp-prom)
        fresh = mcp_prom.freshness(tsdb, asset)
        run.step("freshness", fresh, note="mcp-prom: 데이터 신선도·수집 상태")
        if not fresh["ok"]:
            run.card = {"incident": None, "alert": alert, "freshness": fresh, "causes": [], "recommended": [], "citations": [],
                        "summary": f"데이터 신뢰 불가: {fresh['reason']}. 추론을 보류합니다."}
            run.finish("WITHHELD")
            c_runs.inc(status="WITHHELD")
            return
        # 2. T1 cause candidates (mcp-kg)
        t1 = kg.t1_causes(alert.get("pattern", ""), asset)
        run.step("t1_causes", [{k: r.get(k) for k in ("causeId", "cause", "prior", "failureMode")} | {"evidence": [e["id"] for e in r.get("evidence") or []]} for r in t1],
                 note="mcp-kg T1: 경보 패턴 → 증상 → 고장모드 → 원인 후보 + 증거 규칙")
        # 3. evidence (mcp-tsdb)
        evidence = [e for r in t1 for e in (r.get("evidence") or [])]
        results = tsdb.evaluate(evidence, asset)
        run.step("evidence", results, note="mcp-tsdb: Evidence SQL 템플릿 실행 (tag_1s)")
        causes = cardlib.rank_causes(t1, results)
        run.step("rank", [{"id": c["id"], "name": c["name"], "score": c["score"], "prior": c["prior"]} for c in causes],
                 note="원인 점수 = 사전확률 × 통과 증거 가중치 비율")
        # 4. T2 actions for the top cause (mcp-kg)
        t2 = {causes[0]["id"]: kg.t2_actions(causes[0]["id"], asset)} if causes else {}
        run.step("t2_actions", [{k: r.get(k) for k in ("code", "name", "kind", "min", "max", "default", "relation")}
                                | {"sop": (r.get("procedure") or {}).get("id"), "steps": len(r.get("steps") or [])} for r in next(iter(t2.values()), [])],
                 note="mcp-kg T2: 원인 → 조치(파라미터 범위) → SOP 단계 → 매뉴얼 절")
        # 5. card (+ optional LLM narrative)
        card = cardlib.build_card(None, alert, causes, t2, fresh)
        summary, source = llm.summarize(card, card["summary"])
        card["summary"], card["summarySource"] = summary, source
        run.step("card", {"summary": summary, "source": source, "citations": card["citations"]}, note="가이드 카드 조립 (근거 노드 ID 인용)")
        # 6. guardrail
        violations = guardrail.check(card)
        run.step("guardrail", {"violations": violations}, status="DONE" if not violations else "FAILED",
                 note="가드레일: 인용 누락·범위 밖 파라미터·명령 필드 금지")
        run.card = card
        if violations:
            run.finish("REJECTED_BY_GUARDRAIL", "; ".join(violations))
            c_runs.inc(status="REJECTED_BY_GUARDRAIL")
            log.warning("run %s rejected by guardrail: %s", run.id, violations)
            return
        # 7. submit (the agent's only write)
        res = submit_card(card)
        run.incident_id = res.get("id")
        card["incident"] = run.incident_id
        run.step("submit", res, note="process API에 카드 제출 (에이전트의 유일한 쓰기)")
        # 8. enterprise decisions (L7 -> L8 -> L9): scenarios the ontology links to this cause / pattern
        linked = []
        try:
            ids = [c for c in [card.get("topCause"), "pattern:" + str(alert.get("pattern", "")).lower().replace("_", "-")] if c]
            for trig in kg.triggers(ids):
                d = enterprise.decide(kg, decisions, trig["id"], asset,
                                      origin={"kind": "alert", "alertId": alert.get("alertId"), "incident": run.incident_id, "trigger": trig["trigger"]})
                linked.append({"decision": d["id"], "scenario": trig["name"], "status": d["status"], "applicable": d.get("applicable"),
                               "recommended": next((o["name"] for o in (d.get("result") or {}).get("options", []) if o["id"] == d.get("recommended")), None)})
        except Exception as e:  # noqa: BLE001
            log.warning("enterprise decisions skipped: %s", e)
        run.step("enterprise", linked, note="온톨로지가 이 원인·경보에 연결한 전사 판단 시나리오 (ERP·MES·CMMS·QMS 조회 → KPI 트레이드오프)")
        run.finish("SUBMITTED")
        c_runs.inc(status="SUBMITTED")
        log.info("run %s submitted as incident %s", run.id, run.incident_id)
    except Exception as e:  # noqa: BLE001
        log.exception("run %s failed", run.id)
        run.step("error", {"error": str(e)}, status="FAILED")
        run.finish("FAILED", str(e))
        c_runs.inc(status="FAILED")


async def consume():
    global kg
    kg = mcp_kg.KnowledgeGraph()
    state["neo4j"] = kg.ping()
    cons = await make_consumer([topics.K_ALERTS], group="agent", from_latest=True)
    state["kafka"] = True
    log.info("consuming alerts (RAISE only)")
    async for rec in cons:
        alert = rec.value
        if not isinstance(alert, dict) or alert.get("state") != "RAISE" or not alert.get("alertId"):
            continue
        run = runs.create_if_new(alert)
        if run is None:
            log.info("duplicate RAISE for %s ignored", alert.get("alertId"))
            continue
        state["runs"] += 1
        asyncio.get_running_loop().run_in_executor(None, pipeline, run)


app = make_app("agent (L8: ontology-grounded guide cards, read-only tools)", reg,
               lambda: {**state, "ok": state["kafka"] and not state.get("consumer_dead", False)})


def _watch(task):
    """If the consume loop ever exits, /healthz reports it (503) instead of looking healthy while doing nothing."""
    state["consumer_dead"] = True
    state["consumer_error"] = repr(task.exception()) if not task.cancelled() and task.exception() else "exited"
    log.error("consumer task ended: %s", state["consumer_error"])


@app.on_event("startup")
async def _startup():
    asyncio.create_task(consume()).add_done_callback(_watch)


@app.get("/api/agent/runs")
def list_runs():
    return [r.to_dict() | {"card": None, "steps": [{"name": s["name"], "status": s["status"], "t": s["t"]} for s in r.steps]} for r in runs.all()]


@app.get("/api/agent/runs/{run_id}")
def get_run(run_id: str):
    r = runs.get(run_id)
    if not r:
        raise HTTPException(404, "no such run")
    return r.to_dict()


@app.post("/api/agent/replay/{alert_id}")
async def replay(alert_id: str):
    """Lecture helper: re-run the pipeline for an alert that was already processed."""
    prev = runs.by_alert(alert_id)
    if not prev:
        raise HTTPException(404, "unknown alert")
    run = runs.force_new(prev.alert)
    asyncio.get_running_loop().run_in_executor(None, pipeline, run)
    return {"run": run.id}


# ---------------------------------------------------------------- L7/L8 endpoints for the portal
class DecideReq(BaseModel):
    scenario: str
    asset: str | None = None


def _kg():
    if kg is None:
        raise HTTPException(503, "knowledge graph not connected yet")
    return kg


@app.get("/api/ontology/graph")
def ontology_graph(asset: str = "HYD-01"):
    return _kg().graph(asset)


@app.get("/api/ontology/template/{name}")
def ontology_template(name: str):
    if not name.replace("_", "").isalnum() or not name.startswith(("t0", "t1", "t2", "t3")):
        raise HTTPException(404, "no such template")
    try:
        return {"name": name, "text": _kg().template_text(name)}
    except FileNotFoundError:
        raise HTTPException(404, "no such template")


@app.get("/api/ontology/roles")
def ontology_roles():
    return _kg().roles()


@app.get("/api/agent/scenarios")
def list_scenarios():
    return _kg().scenarios()


@app.post("/api/agent/decide")
async def decide(req: DecideReq):
    k = _kg()
    return await asyncio.get_running_loop().run_in_executor(None, lambda: enterprise.decide(k, decisions, req.scenario, req.asset))


@app.get("/api/agent/decisions")
def list_decisions():
    return [{k: d.get(k) for k in ("id", "created", "scenario", "asset", "status", "recommended", "applicable", "origin")} for d in decisions.all()]


@app.get("/api/agent/decisions/{did}")
def get_decision(did: str):
    d = decisions.get(did)
    if not d:
        raise HTTPException(404, "no such decision")
    return d
