"""agent (L8): 읽기 전용 판단 서비스 — alert -> data-trust check -> T1 causes -> evidence SQL -> T2 actions -> guide card -> guardrail
-> 조치 카드 평가(제출하지 않음).

The LangGraph/MCP/LiteLLM stack of the full architecture is collapsed into one process (the `tools.mcp_*` modules are
in-process functions, not MCP servers), but the discipline is kept: tools are read-only and every step is recorded in the
run trace. 경보마다 스스로 돌던 옛 자동 파이프라인(가이드 카드 · 판단 제출)은 지웠다(2026-10-30) — 판단 제출은 처리 건의 에이전트
단계(AI 워커 → dmn-mcp submit_decision) 하나뿐이다. 여기 남은 것은 읽기 평가(/api/agent/evaluate — 판단 채점) · 규칙 판단 · 예측 ·
승인 현재 조건 검사 · 가정 실험이다.
"""
import asyncio
import logging
import os
import re
from urllib.parse import quote

from fastapi import HTTPException
from pydantic import BaseModel

from hydcommon.maintenance_policy import PM_PATTERN
from hydcommon.metrics import Registry
from hydcommon.skill_scope import PURCHASE_PATTERN
from hydcommon.service import make_app
from . import card as cardlib, decide as decidelib, guardrail, whatif
from .runs import Run
from .tools import mcp_ent, mcp_kg, mcp_prom, mcp_tsdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("agent")
PROCESS_URL = decidelib.PROCESS_URL

reg = Registry()
state = {"runs": 0}
kg: mcp_kg.KnowledgeGraph | None = None
tsdb = mcp_tsdb.TimeSeriesDB()
decisions = decidelib.DecisionRegistry("agent")
whatifs = whatif.Sessions()


def pipeline(run) -> None:
    """Synchronous read-only reasoning pipeline (runs in a worker thread). 제출 · 쓰기는 없다 — 끝에 조치 카드를 평가만 한다."""
    alert, asset = run.alert, run.asset
    try:
        policy=decidelib._get_json(f"{PROCESS_URL}/api/alerts/policy?pattern={quote(str(alert.get('pattern') or ''),safe='')}")
        run.step('alert_policy',policy,note='프로세스 정의의 경보 지원 범위/사람 검토 경로')
        if policy.get('route')!='response':
            run.finish('WITHHELD','이 경보는 명시된 사람 검토 경로에서 확인합니다')
            return
        # 1. data trust (mcp-prom)
        fresh = mcp_prom.freshness(tsdb, asset)
        run.step("freshness", fresh, note="mcp-prom: 데이터 신선도·수집 상태")
        if not fresh["ok"]:
            run.card = {"incident": None, "alert": alert, "freshness": fresh, "causes": [], "citations": [],
                        "summary": f"데이터 신뢰 불가: {fresh['reason']}. 추론을 보류합니다."}
            run.finish("WITHHELD")
            return
        # 2. T1 cause candidates (mcp-kg)
        t1 = kg.t1_causes(alert.get("pattern", ""))
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
            return
        run.step("rank", [{"id": c["id"], "name": c["name"], "score": c["score"], "prior": c["prior"]} for c in causes],
                 note="원인 점수 = 사전확률 × 통과 증거 가중치 비율")
        # 4. T2: the failure mode's SOP skills for the top cause (mcp-kg)
        t2 = {causes[0]["id"]: kg.t2_skills(causes[0]["id"])} if causes else {}
        run.step("t2_skills", [{"sop": r.get("sopId"), "skill": r.get("name"), "relation": r.get("relation"), "kind": r.get("kind"),
                                "actions": [f"{a['code']}={a.get('value')}" for a in r.get("actions") or []], "steps": len(r.get("steps") or [])}
                               for r in next(iter(t2.values()), [])],
                 note="mcp-kg T2: 원인 → 고장 유형 → 조치 방법(스킬 = SOP) → 원자 조치 · 단계 · 매뉴얼 절")
        # 5. card — 원인 · 근거 · 조치 방법 목록(문장은 엔진 틀 — 모델을 부르지 않는다)
        card = cardlib.build_card(None, alert, causes, t2, fresh)
        run.step("card", {"summary": card["summary"], "citations": card["citations"]}, note="가이드 카드 조립 (근거 노드 ID 인용)")
        # 6. guardrail
        violations = guardrail.check(card)
        run.step("guardrail", {"violations": violations}, status="DONE" if not violations else "FAILED",
                 note="가드레일: 인용 누락 · 미확인 근거 · 명령 칸 금지")
        run.card = card
        if violations:
            run.finish("REJECTED_BY_GUARDRAIL", "; ".join(violations))
            log.warning("run %s rejected by guardrail: %s", run.id, violations)
            return
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
        run.step('cards',d,note='읽기 평가 결과: 제출 · 실행하지 않습니다(판단 제출은 처리 건의 에이전트 단계만)')
        run.finish('EVALUATED')
    except Exception as e:  # noqa: BLE001
        log.exception("run %s failed", run.id)
        run.step("error", {"error": str(e)}, status="FAILED")
        run.finish("FAILED", str(e))


def health() -> dict:
    """지식 그래프에 지금 닿는지 물을 때마다 잰다 — 켜질 때 한 번만 재면 Neo4j보다 먼저 뜬 날(PC · Docker 재시작) 영영 503이다."""
    up = kg is not None and kg.ping()
    return {**state, "neo4j": up, "ok": up, **({} if up else {"neo4j_error": kg.ping_error if kg is not None else "아직 켜지는 중"})}


app = make_app("agent (L8: ontology-grounded guide cards, read-only tools)", reg, health)


class EvaluationReq(BaseModel):
    alert: dict


@app.post('/api/agent/evaluate')
def evaluate_without_submission(req: EvaluationReq):
    if (req.alert.get('state')!='RAISE' or any(not isinstance(req.alert.get(k),str) or not req.alert[k]
                                             for k in ('alertId','asset','pattern'))):
        raise HTTPException(400,'원천 RAISE 경보의 ID/설비/패턴이 필요합니다')
    run = Run.new(req.alert)
    state['runs'] += 1
    pipeline(run)
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


@app.on_event("startup")
async def _startup():
    global kg
    kg = mcp_kg.KnowledgeGraph()


# ---------------------------------------------------------------- L7/L8 endpoints for the portal
class DecideReq(BaseModel):
    """Manual run of the action-card decision (portal '조치 판단 규칙' view). facts: what-if values a person sets."""
    asset: str = "HYD-01"
    pattern: str = "COOLER_DEGRADATION"
    facts: dict | None = None


def _kg():
    if kg is None:
        raise HTTPException(503, "agent 가 아직 켜지는 중이라 지식 그래프에 연결하지 않았습니다 — 잠시 뒤 다시 시도하세요")
    return kg


_NS_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


@app.get("/api/ontology/graph")
def ontology_graph(asset: str = "HYD-01", ns: str = ""):
    """ns (G4 전체 과정 랩업): 학생 이름 공간. 비면 수업 기준 — 학생 노드는 섞이지 않는다."""
    if ns and not _NS_RE.match(ns):
        raise HTTPException(422, "ns: 소문자로 시작하는 소문자 · 숫자 · 하이픈 32자 이내")
    return _kg().graph(asset, ns)


@app.get("/api/ontology/namespaces")
def ontology_namespaces():
    """G4: 그래프에 있는 학생 이름 공간(ns)과 노드 수 — 지식 지도의 '이름 공간' 고르기."""
    return _kg().namespaces()


@app.get("/api/ontology/template/{name}")
def ontology_template(name: str):
    if not name.replace("_", "").isalnum() or not name.startswith(("t0", "t1", "t2", "t3")):
        raise HTTPException(404, "no such template")
    try:
        return {"name": name, "text": _kg().template_text(name)}
    except FileNotFoundError:
        raise HTTPException(404, "no such template")


@app.get("/api/ontology/patterns")
def ontology_patterns():
    return _kg().patterns()


#: 설비 센서가 아니라 업무 표 감시가 내는 경보(it/neo4j/v2/scenario_structure.cypher — detectionMode · Symptom 없음). 원인 진단 대상이 아니다
BUSINESS_PATTERNS = frozenset({PM_PATTERN, PURCHASE_PATTERN})


def _no_cause_message(k, pattern: str) -> str:
    """원인 후보가 없을 때 학생이 읽는 문장(2026-10-25 수업 한 바퀴: 「no cause candidates for pattern …」가 판단 규칙 · 손익 화면에 그대로 보였다).
    고장 유형이 없는 패턴(정기 정비 도래 · 재고 기준 이탈)은 원인 진단 대상이 아니라 업무 흐름의 에이전트가 판단한다."""
    meta = next((p for p in k.patterns() if p.get("code") == pattern), {})
    name = meta.get("name") or pattern
    if pattern in BUSINESS_PATTERNS:
        return f"'{name}'은(는) 고장 원인을 진단하는 이상 패턴이 아닙니다 — 업무 흐름(정기 정비 · 예비품 구매)의 에이전트가 판단합니다. 쿨러 성능 저하 같은 설비 이상 패턴을 고르세요"
    return f"'{name}'의 원인 지식이 아직 없습니다 — [지식 관리]에서 이 고장을 다루는 매뉴얼을 적재한 뒤 다시 실행하세요"


def _manual_decide(k, req: DecideReq, capture: dict | None = None) -> dict:
    """Same pipeline as an alert, without submitting: T1 causes → evidence → top cause → action cards."""
    t1 = k.t1_causes(req.pattern)
    if not t1:
        raise HTTPException(404, _no_cause_message(k, req.pattern))
    try:
        results = tsdb.evaluate([e for r in t1 for e in (r.get("evidence") or [])], req.asset)
    except Exception as e:  # noqa: BLE001 — 근거 조회 실패는 그 까닭과 함께 보류(값 없음으로 판단하지 않는다)
        log.warning("evidence source unavailable: %s", e)
        raise HTTPException(503, f'설비 근거(시계열 DB)를 읽지 못해 판단을 보류합니다 — {type(e).__name__}: {str(e)[:200]}') from e
    causes = cardlib.rank_causes(t1, results)
    assessment = cardlib.evidence_status(causes)
    if assessment['withheld']:
        raise HTTPException(409, {'reason': assessment['reason'], 'evidence_status': assessment, 'causes': causes})
    if req.facts and req.facts.get("cause"):
        causes.sort(key=lambda c: c["id"] != req.facts["cause"])
    d = decidelib.decide(k, decisions, tsdb, req.asset, req.pattern, causes[0], origin={"kind": "manual", "pattern": req.pattern},
                         overrides={x: v for x, v in (req.facts or {}).items() if x != "cause"}, do_submit=False, capture=capture)
    if d.get("error_code") == "INVALID_FACT":
        # 사람이 바꿔 넣은 사실(음수 시간 · 형식이 다른 값 · 없는 변수)은 판단 실패가 아니라 입력 거절이다 — 4xx 와 그 문장(한바퀴3)
        raise HTTPException(422, d["error"])
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
            "policyTrial": policy or {"weights": {}, "penalties": {}}, "trial": trial or {}, "limits": whatif.LIMITS, **ev,
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
    consented_at: str | None = None      # 사람이 승인한 시각 — 예측 나이를 이 시각으로 잰다(process 가 승인 때 기록)


class ChoicePreviewReq(BaseModel):
    decision: dict
    option: str
    parameters: dict


def _source_failure(e: Exception) -> HTTPException:
    """원천(업무 시스템 · 설비 상태)을 읽지 못한 것은 이 승인을 거절한 것이 아니라 검사를 못 한 것이다 — 503 과 그 자리의 까닭(H-8)."""
    return HTTPException(503, str(e))


@app.post('/api/agent/choice-preview')
def choice_preview(req: ChoicePreviewReq):
    from .approval import preview
    try:
        return preview(_kg(), tsdb, req.decision, req.option, req.parameters)
    except (decidelib.FactUnavailable, mcp_ent.SourceUnavailable) as e:
        raise _source_failure(e) from e
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post('/api/agent/approval-check')
def approval_check(req: ApprovalCheckReq):
    """Read-only policy/source assessment; this endpoint cannot authorize effects."""
    from .approval import assess
    try:
        return assess(_kg(), tsdb, req.decision, req.option, req.role, consented_at=req.consented_at)
    except (decidelib.FactUnavailable, mcp_ent.SourceUnavailable) as e:
        raise _source_failure(e) from e
    except ValueError as e:
        raise HTTPException(409, str(e))
