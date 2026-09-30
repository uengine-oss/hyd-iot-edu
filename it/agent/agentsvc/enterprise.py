"""L8 enterprise decision pipeline (IO side of decision.py), traced step by step like the guide-card run.

ontology_context (T3) -> info_routing (InfoType -> System -> endpoint) -> fetch (mcp-ent GET) -> impacts ->
policies -> perspectives -> recommend -> guardrail -> submit (POST process /api/decisions — the agent's only write).
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import urllib.request
from datetime import datetime, timezone

from . import decision, guardrail
from .tools import mcp_ent

log = logging.getLogger("agent.enterprise")
PROCESS_URL = os.getenv("PROCESS_URL", "http://process:8080")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class DecisionRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._items: dict[str, dict] = {}
        self._seq = 0

    def new_id(self) -> str:
        with self._lock:
            self._seq += 1
            return f"DEC-{datetime.now():%m%d}-{self._seq:03d}-{secrets.token_hex(2)}"

    def put(self, d: dict) -> None:
        with self._lock:
            self._items[d["id"]] = d
            if len(self._items) > 200:
                self._items.pop(next(iter(self._items)))

    def get(self, did: str) -> dict | None:
        return self._items.get(did)

    def all(self) -> list[dict]:
        return sorted(self._items.values(), key=lambda d: d["created"], reverse=True)


def submit(payload: dict) -> dict:
    req = urllib.request.Request(f"{PROCESS_URL}/api/decisions", data=json.dumps(payload, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def decide(kg, registry: DecisionRegistry, scenario_id: str, asset: str | None = None, origin: dict | None = None,
           do_submit: bool = True) -> dict:
    steps: list[dict] = []

    def step(name, output, note, status="DONE"):
        steps.append({"name": name, "status": status, "t": _now(), "note": note, "output": output})

    rec = {"id": registry.new_id(), "created": _now(), "scenario": {"id": scenario_id}, "asset": asset, "origin": origin or {"kind": "manual"},
           "status": "RUNNING", "steps": steps}
    registry.put(rec)
    try:
        raw = kg.scenario_context(scenario_id)
        ctx = decision.build_context(raw["scenario"], raw["options"], raw["kpis"], raw["policies"], raw.get("precedents"))
        scn = ctx["scenario"]
        asset = asset or (scn.get("asset") if scn.get("asset") not in (None, "ALL") else "HYD-01")
        rec.update(scenario=scn, asset=asset)
        step("ontology_context", {"scenario": scn.get("name"), "triggers": ctx["triggers"],
                                  "options": [{"id": o["id"], "name": o["name"], "skills": [s["id"] for s in o["skills"]],
                                               "kpis": [i["kpi"] for i in o["impacts"]], "approver": (o.get("approver") or {}).get("name")} for o in ctx["options"]],
                                  "kpis": [{"id": k["id"], "name": k["name"], "owner": k["ownerName"]} for k in ctx["kpis"]],
                                  "policies": [{"id": p["id"], "name": p["name"], "kind": p["kind"], "scope": p["scope"], "skills": p["skills"]}
                                               for p in ctx["policies"] if p["scope"] == "scenario" or set(p["skills"]) & {s["id"] for o in ctx["options"] for s in o["skills"]}]},
             "mcp-kg T3: 시나리오 → 대안 → 스킬 → KPI(소유 부서) · 규정 · 필요 정보")
        step("precedents", ctx["precedents"] or "선례 없음",
             "T3-g: 같은 판단에서 사람이 승인한 대안(Decision -DECIDED-> Option) — 현장 판단 선례 KPI로 반영")
        step("info_routing", [{"info": i["id"], "name": i["name"], "system": i["systemName"], "endpoint": i["endpoint"].replace("{asset}", asset)} for i in ctx["infos"]],
             "InfoType -HELD_IN-> System: 어떤 사실을 어느 시스템에서 가져올지 온톨로지가 알려 준다")
        responses = {}
        for i in ctx["infos"]:
            try:
                responses[i["id"]] = mcp_ent.fetch(i["endpoint"], asset)
            except Exception as e:  # noqa: BLE001
                log.warning("fetch %s failed: %s", i["endpoint"], e)
        facts, prov = decision.assemble_facts(ctx["infos"], responses, asset)
        step("fetch", prov, "mcp-ent: ERP · MES · CMMS · QMS · SCM · EMS 조회 (읽기 전용)",
             status="DONE" if all(not p.get("error") for p in prov) else "FAILED")
        cond = scn.get("condition")
        applicable = True
        if cond:
            try:
                applicable = bool(decision.safe_eval(cond, facts))
            except KeyError:
                applicable = False
        result = decision.evaluate(ctx, facts)
        step("impacts", [{"option": o["name"], "impacts": o["impacts"], "notes": o["notes"], "errors": o["errors"]} for o in result["options"]],
             "Option -IMPACTS{식}-> KPI: 사실 × 대안 파라미터로 KPI별 금액 영향(만원) 계산")
        step("policies", [{"option": o["name"], "violations": o["violations"], "soft": o["softPenalties"]} for o in result["options"]],
             "Policy -GOVERNS-> Skill|Scenario: HARD는 대안 제외, SOFT는 해당 KPI에 페널티")
        step("perspectives", {"departments": result["departments"], "winners": result["winners"], "naiveWinners": result["naiveWinners"]},
             "관점별 1위: 부서는 자기 KPI만, 전사는 Goal(전사 영업이익) 가중합")
        step("recommend", {"recommended": result["recommended"], "runnerUp": result["runnerUp"], "drivers": result["drivers"],
                           "explanation": result["explanation"], "approver": result["approver"]},
             "권고안 + 근거 (차이를 만든 KPI) + 승인 역할")
        violations = guardrail.check_decision(result, ctx)
        step("guardrail", {"violations": violations}, "가드레일: KPI 인용 · 규정 위반 · 승인 역할 확인",
             status="DONE" if not violations else "FAILED")
        roles = {r["id"]: {"name": r["name"], "level": r["level"], "dept": r["deptName"]} for r in kg.roles()}
        rec.update(result=result, provenance=prov, facts=facts, applicable=applicable, condition=cond, roles=roles,
                   kpis=ctx["kpis"], recommended=result["recommended"], explanation=result["explanation"])
        if violations:
            rec["status"] = "REJECTED_BY_GUARDRAIL"
            return rec
        if not result["recommended"]:
            rec["status"] = "NO_FEASIBLE_OPTION"
        if do_submit and (applicable or (origin or {}).get("kind") == "manual"):
            payload = {"id": rec["id"], "scenario": scn, "asset": asset, "origin": rec["origin"], "recommended": result["recommended"],
                       "explanation": result["explanation"], "options": result["options"], "winners": result["winners"],
                       "naiveWinners": result["naiveWinners"], "departments": result["departments"], "drivers": result["drivers"],
                       "roles": roles, "kpis": ctx["kpis"], "provenance": [{k: p[k] for k in ("info", "name", "system", "systemName", "endpoint")} for p in prov],
                       "applicable": applicable}
            res = submit(payload)
            step("submit", res, "process API에 판단 제출 (에이전트의 유일한 쓰기) — 실행은 승인 후 L9가 한다")
            rec["status"] = "SUBMITTED"
        elif rec["status"] == "RUNNING":
            rec["status"] = "NOT_APPLICABLE" if not applicable else "EVALUATED"
        return rec
    except Exception as e:  # noqa: BLE001
        log.exception("decision %s failed", rec["id"])
        step("error", {"error": str(e)}, "실패", status="FAILED")
        rec["status"] = "FAILED"
        rec["error"] = str(e)
        return rec
