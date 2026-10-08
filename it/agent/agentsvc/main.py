"""agent (L8): alert -> data-trust check -> T1 causes -> evidence SQL -> T2 actions -> guide card -> guardrail -> process API.

The LangGraph/MCP/LiteLLM stack of the full architecture is collapsed into one process (the `tools.mcp_*` modules are
in-process functions, not MCP servers), but the discipline is kept: tools are read-only and every step is recorded in the
run trace. The legacy pipeline writes to the process service twice and nowhere else: POST /api/incidents (the guide card,
step 7 below) and then POST /api/decisions (the ranked action cards, decide.submit). PROCESS_MODE=instance hands the
action-card step to the process instance's agent task instead (see /api/agent/decide and dmn-mcp).
"""
import asyncio
import json
import logging
import os
import urllib.request
from urllib.parse import quote

from fastapi import HTTPException
from pydantic import BaseModel

from hydcommon import topics
from hydcommon.kafka import consumer as make_consumer
from hydcommon.metrics import Registry
from hydcommon.service import make_app
from . import card as cardlib, decide as decidelib, guardrail, llm, whatif
from .runs import RunRegistry
from .tools import mcp_ent, mcp_kg, mcp_prom, mcp_tsdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("agent")
PROCESS_URL = os.getenv("PROCESS_URL", "http://process:8080")
AUTOMATIC_PIPELINE = os.getenv("PROCESS_MODE", "legacy") != "instance"

reg = Registry()
c_runs = reg.counter("agent_runs_total", "agent runs by status")
runs = RunRegistry()
state = {"kafka": False, "neo4j": False, "runs": 0, "llm": llm.available(), "llm_model": llm.MODEL}
kg: mcp_kg.KnowledgeGraph | None = None
tsdb = mcp_tsdb.TimeSeriesDB()
decisions = decidelib.DecisionRegistry()
whatifs = whatif.Sessions()


def submit_card(card: dict) -> dict:
    req = urllib.request.Request(f"{PROCESS_URL}/api/incidents", data=json.dumps(card, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def pipeline(run, *, do_submit=True) -> None:
    """Synchronous reasoning pipeline (runs in a worker thread)."""
    alert, asset = run.alert, run.asset
    try:
        policy=decidelib._get_json(f"{PROCESS_URL}/api/alerts/policy?pattern={quote(str(alert.get('pattern') or ''),safe='')}")
        run.step('alert_policy',policy,note='프로세스 정의의 경보 지원 범위/사람 검토 경로')
        if policy.get('route')!='response':
            run.finish('WITHHELD','이 경보는 명시된 사람 검토 경로에서 확인합니다')
            c_runs.inc(status='WITHHELD')
            return
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
        t1, human = cardlib.with_human_evidence(t1, alert)       # B7: 사람 입력 경보(오일 분석)는 입력한 결과가 증거
        run.step("t1_causes", [{k: r.get(k) for k in ("causeId", "cause", "prior", "failureMode")} | {"evidence": [e["id"] for e in r.get("evidence") or []]} for r in t1],
                 note="mcp-kg T1: 경보 패턴 → 증상 → 고장모드 → 원인 후보 + 증거 규칙"
                      + (" (센서 증거 규칙이 없는 원인은 사람이 입력한 분석 결과를 증거로)" if human else ""))
        # 3. evidence (mcp-tsdb)
        evidence = [e for r in t1 for e in (r.get("evidence") or []) if e["id"] not in human]
        results = {**tsdb.evaluate(evidence, asset), **human}
        run.step("evidence", results, note="mcp-tsdb: Evidence SQL 템플릿 실행 (tag_1s)")
        causes = cardlib.rank_causes(t1, results)
        assessment = cardlib.evidence_status(causes)
        if assessment['withheld']:
            run.card = cardlib.build_card(None, alert, causes, {}, fresh)
            run.step('evidence_assessment', assessment, note=assessment['reason'])
            run.finish('WITHHELD', assessment['reason'])
            c_runs.inc(status='WITHHELD')
            return
        run.step("rank", [{"id": c["id"], "name": c["name"], "score": c["score"], "prior": c["prior"]} for c in causes],
                 note="원인 점수 = 사전확률 × 통과 증거 가중치 비율")
        # 4. T2: the failure mode's SOP skills for the top cause (mcp-kg)
        t2 = {causes[0]["id"]: kg.t2_skills(causes[0]["id"])} if causes else {}
        run.step("t2_skills", [{"sop": r.get("sopId"), "skill": r.get("name"), "relation": r.get("relation"), "kind": r.get("kind"),
                                "actions": [f"{a['code']}={a.get('value')}" for a in r.get("actions") or []], "steps": len(r.get("steps") or [])}
                               for r in next(iter(t2.values()), [])],
                 note="mcp-kg T2: 원인 → 고장 유형 → 조치 방법(스킬 = SOP) → 원자 조치 · 단계 · 매뉴얼 절")
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
        if not do_submit:
            d = decidelib.decide(kg, decisions, tsdb, asset, alert.get('pattern',''), causes[0], do_submit=False,
                                origin={'kind':'alert','alertId':alert['alertId'],'pattern':alert['pattern'],
                                        'cause':causes[0]['id'],'failureMode':causes[0].get('failureModeId')})
            if d.get('status') != 'EVALUATED' or not (d.get('result') or {}).get('options'):
                run.step('cards',d,status='FAILED')
                run.finish('WITHHELD',d.get('error') or d.get('explanation') or '검증된 조치 대안을 만들지 못했습니다')
                return
            run.evaluation = {k:d.get(k) for k in ('id','schema','scenario','asset','origin','recommended','explanation',
                                                    'rankRule','roles','facts','provenance','applicable')}
            run.evaluation.update(options=d['result']['options'],rankRule=d['result'].get('rankRule'))
            run.step('cards',d,note='읽기 평가 결과: 프로세스 점유 확인 후 접수하며 여기서는 제출/실행하지 않습니다')
            run.finish('EVALUATED')
            return
        # 7. submit (the agent's only write)
        res = submit_card(card)
        run.incident_id = res.get("id")
        card["incident"] = run.incident_id
        run.step("submit", res, note="process API에 카드 제출 (에이전트의 유일한 쓰기)")
        if res.get('state')!='AWAITING_APPROVAL':
            run.finish('WITHHELD','사건이 조치 선택 상태가 아니므로 카드 제출을 중단합니다')
            c_runs.inc(status='WITHHELD')
            return
        # 8. action cards (L7 -> L8 -> L9): DMN rules + forecasts + BSC trade-offs + precedents -> ranked SOP skills for the human
        linked = {}
        try:
            d = decidelib.decide(kg, decisions, tsdb, asset, alert.get("pattern", ""), causes[0],
                                 origin={"kind": "alert", "alertId": alert.get("alertId"), "incident": run.incident_id,
                                         "pattern": alert.get("pattern"), "cause": causes[0]["id"], "failureMode": causes[0].get("failureModeId")})
            res = d.get("result") or {}
            linked = {"decision": d["id"], "status": d["status"], "recommended": d.get("recommended"),
                      "cards": [f"{o['rank']}. {o['sopId']} {o['name']}" + ("" if o["feasible"] else " (제외)") for o in res.get("options", [])],
                      "explanation": d.get("explanation")}
        except Exception as e:  # noqa: BLE001
            log.warning("action-card decision skipped: %s", e)
            linked = {"error": str(e)}
        run.step("cards", linked, status="DONE" if linked.get("status") == "SUBMITTED" else "FAILED",
                 note="조치 카드: DMN 후보 · 규정 규칙 → 예측 · BSC 상충 · 선례로 순위 → 사람이 고를 카드 2~3장 제출")
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
        if not AUTOMATIC_PIPELINE:
            log.info("RAISE %s is owned by the instance worker; legacy pipeline skipped", alert["alertId"])
            continue
        run = runs.create_if_new(alert)
        if run is None:
            log.info("duplicate RAISE for %s ignored", alert.get("alertId"))
            continue
        state["runs"] += 1
        asyncio.get_running_loop().run_in_executor(None, pipeline, run)


app = make_app("agent (L8: ontology-grounded guide cards, read-only tools)", reg,
               lambda: {**state, "ok": state["kafka"] and not state.get("consumer_dead", False)})


class EvaluationReq(BaseModel):
    alert: dict


@app.post('/api/agent/evaluate')
def evaluate_without_submission(req: EvaluationReq):
    if (req.alert.get('state')!='RAISE' or any(not isinstance(req.alert.get(k),str) or not req.alert[k]
                                             for k in ('alertId','asset','pattern'))):
        raise HTTPException(400,'원천 RAISE 경보의 ID/설비/패턴이 필요합니다')
    run = runs.force_new(req.alert)
    state['runs'] += 1
    pipeline(run,do_submit=False)
    return run.to_dict()


class TrialReq(BaseModel):
    """A10 시험 실행: scenario {asset, pattern} · agent 설정 · 입력 스냅숏 항목(같은 입력 재사용) · 테넌트 MCP 서버 이름."""
    scenario: dict
    agent: dict
    entries: dict = {}
    tenant_servers: list[str] | None = None


@app.post('/api/agent/trial')
def agent_trial(req: TrialReq):
    """Read-only judgment for one agent setting; no incident, decision, work item or command (trial.py)."""
    from . import trial as triallib
    if not all(isinstance(req.scenario.get(k), str) and req.scenario[k] for k in ('asset', 'pattern')):
        raise HTTPException(400, '시나리오의 설비와 이상 패턴이 필요합니다')
    snap = triallib.Snapshot(req.entries)
    out = triallib.run_trial(req.scenario, req.agent, triallib.LiveWorld(kg, tsdb), snap, req.tenant_servers)
    return {'trial': out, 'added': snap.added}


def _watch(task):
    """If the consume loop ever exits, /healthz reports it (503) instead of looking healthy while doing nothing."""
    state["consumer_dead"] = True
    state["consumer_error"] = repr(task.exception()) if not task.cancelled() and task.exception() else "exited"
    log.error("consumer task ended: %s", state["consumer_error"])


@app.on_event("startup")
async def _startup():
    llm.announce()
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
    """Manual run of the action-card decision (portal '조치 판단 규칙' view). facts: what-if values a person sets."""
    asset: str = "HYD-01"
    pattern: str = "COOLER_DEGRADATION"
    facts: dict | None = None


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


@app.get("/api/ontology/patterns")
def ontology_patterns():
    return _kg().patterns()


def _manual_decide(k, req: DecideReq, capture: dict | None = None) -> dict:
    """Same pipeline as an alert, without submitting: T1 causes → evidence → top cause → action cards."""
    t1 = k.t1_causes(req.pattern, req.asset)
    if not t1:
        raise HTTPException(404, f"no cause candidates for pattern {req.pattern}")
    try:
        results = tsdb.evaluate([e for r in t1 for e in (r.get("evidence") or [])], req.asset)
    except Exception as e:  # noqa: BLE001
        log.warning("evidence source unavailable: %s", e)
        raise HTTPException(503, '근거 원천 조회 실패로 판단을 보류합니다') from e
    causes = cardlib.rank_causes(t1, results)
    assessment = cardlib.evidence_status(causes)
    if assessment['withheld']:
        raise HTTPException(409, {'reason': assessment['reason'], 'evidence_status': assessment, 'causes': causes})
    if req.facts and req.facts.get("cause"):
        causes.sort(key=lambda c: c["id"] != req.facts["cause"])
    d = decidelib.decide(k, decisions, tsdb, req.asset, req.pattern, causes[0], origin={"kind": "manual", "pattern": req.pattern},
                         overrides={x: v for x, v in (req.facts or {}).items() if x != "cause"}, do_submit=False, capture=capture)
    d["causes"] = [{"id": c["id"], "name": c["name"], "score": c["score"], "failureMode": c.get("failureMode"),
                    "evidence": c["evidence"]} for c in causes]
    return d


def _with_money(d: dict) -> dict:
    """A7: each card of a manual decision gets its 손익(원) from the business DB (read-only GET). A failed read is a reason, not a 0."""
    options = (d.get("result") or {}).get("options") or []
    if options:
        try:
            mf = whatif.load_money_facts(mcp_ent.fetch, d["asset"])
            for o in options:
                o["money"] = whatif.card_money(o, mf)
        except ValueError as e:
            d["moneyError"] = str(e)
    return d


@app.post("/api/agent/decide")
async def decide(req: DecideReq):
    k = _kg()
    return await asyncio.get_running_loop().run_in_executor(None, lambda: _with_money(_manual_decide(k, req)))


# ---------------------------------------------------------------- A7 손익 · What-if · 규칙 바꿔 보기 (시험 실행만)
class WhatifStartReq(BaseModel):
    asset: str = "HYD-01"
    pattern: str = "COOLER_DEGRADATION"


class WhatifTryReq(BaseModel):
    values: dict | None = None          # 시험값 {variable: number}
    policy: dict | None = None          # {weights: {component: k}, penalties: {rule: value}}


class WhatifWeeksReq(BaseModel):
    card: str
    weeks: int = 4
    change: dict | None = None          # 값 하나 {variable: number}
    policy: dict | None = None


def _whatif_session(sid: str) -> dict:
    s = whatifs.get(sid)
    if not s:
        raise HTTPException(404, "시험 기준 판단이 없습니다(에이전트가 다시 시작됐거나 오래됨). 다시 불러오세요")
    return s


def _whatif_view(s: dict, sid: str, trial=None, policy=None) -> dict:
    ev = whatif.evaluate(s["bundle"], s["mf"], trial, policy)
    unchanged = whatif.original_fingerprint(s["bundle"], s["mf"]) == s["fingerprint"]
    if not unchanged:
        raise HTTPException(500, "시험 실행 중 기준 판단 묶음이 바뀌었습니다 — 결과를 쓰지 않습니다")
    return {"id": sid, "asset": s["asset"], "pattern": s["pattern"], "cause": s["cause"], "created": s["created"],
            "decisionId": s["decisionId"], "variables": whatif.variable_list(s["mf"], trial), "policy": whatif.policy_view(s["bundle"]["dmn"]),
            "perspectives": whatif.perspective_view(s["bundle"]),
            "policyTrial": policy or {"weights": {}, "penalties": {}}, "trial": trial or {}, **ev,
            "baseTop": s["baseTop"], "summary": whatif.summary(ev, s["baseTop"] if (trial or (policy and any(policy.values()))) else None),
            "original": {"unchanged": unchanged, "fingerprint": s["fingerprint"][:12],
                         "note": "업무 DB · 지식 그래프 · 순위 정책은 읽기만 했고, 시험값은 이 계산의 사본에만 적용됐습니다"}}


def _whatif_start(k, req: WhatifStartReq) -> dict:
    bundle: dict = {}
    d = _manual_decide(k, DecideReq(asset=req.asset, pattern=req.pattern), capture=bundle)
    if d.get("status") == "FAILED" or not bundle:
        raise HTTPException(409, "판단을 끝까지 계산하지 못해 시험 기준을 만들 수 없습니다: " + str(d.get("error") or d.get("status")))
    try:
        mf = whatif.load_money_facts(mcp_ent.fetch, req.asset)
    except ValueError as e:
        raise HTTPException(503, str(e)) from e
    try:                                   # B5 관점 중요도: 관점 이름 · 지표 소속은 그래프에서 (못 읽으면 그 기능만 사유와 함께 꺼짐)
        bundle["perspectives"] = whatif.load_perspectives(k.perspectives())
    except Exception as e:  # noqa: BLE001
        bundle["perspectives"] = {"error": f"지식 그래프에서 BSC 관점을 읽지 못했습니다: {type(e).__name__}: {str(e)[:160]}"}
    s = {"asset": req.asset, "pattern": req.pattern, "cause": {c: (d.get("causes") or [{}])[0].get(c) for c in ("id", "name", "failureMode")},
         "created": d["created"], "decisionId": d["id"], "bundle": bundle, "mf": mf}
    s["fingerprint"] = whatif.original_fingerprint(bundle, mf)
    s["baseTop"] = whatif.evaluate(bundle, mf)["top"]
    sid = whatifs.put(s)
    return _whatif_view(s, sid)


@app.post("/api/agent/whatif")
async def whatif_start(req: WhatifStartReq):
    """Read-only snapshot of one manual decision + business DB values; every later trial re-computes against it."""
    k = _kg()
    return await asyncio.get_running_loop().run_in_executor(None, lambda: _whatif_start(k, req))


def _checked(s, values=None, policy=None):
    try:
        return whatif.check_trial(values), whatif.check_policy(s["bundle"]["dmn"], policy, whatif.perspective_view(s["bundle"]))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/agent/whatif/{sid}/try")
async def whatif_try(sid: str, req: WhatifTryReq):
    s = _whatif_session(sid)
    trial, policy = _checked(s, req.values, req.policy)
    return await asyncio.get_running_loop().run_in_executor(None, lambda: _whatif_view(s, sid, trial, policy))


@app.post("/api/agent/whatif/{sid}/boundaries")
async def whatif_boundaries(sid: str, req: WhatifTryReq):
    s = _whatif_session(sid)
    _, policy = _checked(s, None, req.policy)
    out = await asyncio.get_running_loop().run_in_executor(None, lambda: whatif.find_boundaries(s["bundle"], s["mf"], policy=policy))
    return {"id": sid, "boundaries": out}


@app.post("/api/agent/whatif/{sid}/weeks")
async def whatif_weeks(sid: str, req: WhatifWeeksReq):
    s = _whatif_session(sid)
    _, policy = _checked(s, None, req.policy)
    try:
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: whatif.weeks(s["bundle"], s["mf"], req.card, req.weeks, req.change, policy))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class ApprovalCheckReq(BaseModel):
    decision: dict
    option: str
    role: str


class ForecastReq(BaseModel):
    asset: str
    actions: list[dict]
    horizon_s: float = 900


class ChoicePreviewReq(BaseModel):
    decision: dict
    option: str
    parameters: dict


@app.post('/api/agent/choice-preview')
def choice_preview(req: ChoicePreviewReq):
    from .approval import preview
    try:
        return preview(_kg(), tsdb, req.decision, req.option, req.parameters)
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post('/api/agent/forecast')
def forecast_actions(req: ForecastReq):
    """Read-only counterfactual; cannot submit a decision or send a command."""
    from .forecasting import current
    try:
        return current(_kg(), req.asset, req.actions, req.horizon_s)
    except ValueError as e:
        raise HTTPException(409, str(e))
    except OSError as e:
        raise HTTPException(503, 'forecast source unavailable') from e


@app.post('/api/agent/approval-check')
def approval_check(req: ApprovalCheckReq):
    """Read-only policy/source assessment; this endpoint cannot authorize effects."""
    from .approval import assess
    try:
        return assess(_kg(), tsdb, req.decision, req.option, req.role)
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/api/agent/decisions")
def list_decisions():
    return [{k: d.get(k) for k in ("id", "created", "scenario", "asset", "status", "recommended", "applicable", "origin")} for d in decisions.all()]


@app.get("/api/agent/decisions/{did}")
def get_decision(did: str):
    d = decisions.get(did)
    if not d:
        raise HTTPException(404, "no such decision")
    return d
