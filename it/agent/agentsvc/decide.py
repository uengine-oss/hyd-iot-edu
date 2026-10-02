"""L8 action-card decision (IO side of cards.py), traced step by step like the guide-card run.

ontology (T3 DMN rules) -> inputs (InputData -SOURCED_FROM-> System | Sensor) -> facts (TSDB · process · MES) ->
candidates (dec:action-candidates) -> compliance (dec:compliance) -> forecasts · BSC trade-offs · precedents ->
rank (dec:rank-actions) -> guardrail -> submit (POST process /api/decisions — the agent's only write).
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import urllib.request
from datetime import datetime, timezone

from . import cards, guardrail
from .tools import mcp_ent

log = logging.getLogger("agent.decide")
PROCESS_URL = os.getenv("PROCESS_URL", "http://process:8080")
SENSOR_TAGS = {"ts1": "TS1", "ce": "CE", "ps1": "PS1", "fs1": "FS1", "vs1": "VS1", "load": "LoadSP"}


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


def _get_json(url: str, timeout: float = 5.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def submit(payload: dict) -> dict:
    req = urllib.request.Request(f"{PROCESS_URL}/api/decisions", data=json.dumps(payload, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def gather_facts(inputs: list[dict], asset: str, known: dict, tsdb) -> tuple[dict, list[dict]]:
    """Fetch every InputData the DMN rules may test, from the source the ontology names for it.
    known: facts the pipeline already has (pattern, cause, failure_mode, alert evidence). Returns (facts, provenance)."""
    facts, prov = dict(known), []
    plant = None
    for i in inputs:
        var, src, kind = i["variable"], i["source"], i["sourceKind"]
        row = {"variable": var, "name": i["name"], "source": src, "sourceName": i["sourceName"], "represents": i.get("representsName")}
        try:
            if var in facts and facts[var] is not None:
                row.update(value=facts[var], how="파이프라인이 이미 가진 값")
            elif kind == "Sensor" or var in SENSOR_TAGS and src in ("sys:scada",):
                tag = i.get("tag") or SENSOR_TAGS.get(var)
                v, age = tsdb.latest(asset, tag)
                facts[var] = None if v is None else round(v, 3)
                row.update(value=facts[var], how=f"TimescaleDB tag_1s {tag} 최신값 ({age:.0f} s 전)" if v is not None else f"TimescaleDB {tag} 값 없음")
            elif src == "sys:scada" and var in ("plc_mode", "plc_state"):
                if plant is None:
                    plant = _get_json(f"{PROCESS_URL}/api/plant/{asset}/status")
                facts[var] = plant.get("mode" if var == "plc_mode" else "state")
                row.update(value=facts[var], how="plant.status 최신 메시지 (process 서비스가 구독)")
            elif src == "sys:historian" and var == "fan100_hours":
                facts[var] = tsdb.fan100_hours(asset)
                row.update(value=facts[var], how="TimescaleDB FanSpeedSP ≥ 99 % 누적 (최근 48 h)")
            elif src == "sys:mes" and var == "order_due_h":
                mes = mcp_ent.fetch("/mes/orders?asset={asset}", asset)
                facts[var] = (mes.get("facts") or {}).get("due_in_h")
                row.update(value=facts[var], how="MES 생산오더 납기까지 남은 시간")
            elif src == "sys:cmms" and var == "standby_ready":
                facts[var] = True
                row.update(value=True, how="CMMS 목업에 예비 펌프 정비 항목이 없어 기본값 true")
            elif src in ("sys:agent", "sys:scm", "sys:process", "sys:cep"):
                row.update(value=facts.get(var), how="후보마다 계산하거나 경보 · 결정 시점에 정해진다")
            else:
                row.update(value=None, how="출처 조회 방법 없음")
        except Exception as e:  # noqa: BLE001
            facts.setdefault(var, None)
            row.update(value=None, error=str(e)[:160])
        prov.append(row)
    return facts, prov


def decide(kg, registry: DecisionRegistry, tsdb, asset: str, pattern: str, cause: dict, origin: dict | None = None,
           overrides: dict | None = None, do_submit: bool = True) -> dict:
    """cause: the top ranked cause of the guide card ({id, name, failureModeId, failureMode}). overrides: facts set by a person
    (portal 'what if' — e.g. plc_mode REMOTE_MANUAL) to watch the DMN rules react."""
    steps: list[dict] = []

    def step(name, output, note, status="DONE"):
        steps.append({"name": name, "status": status, "t": _now(), "note": note, "output": output})

    rec = {"id": registry.new_id(), "created": _now(), "schema": "v2", "asset": asset, "origin": origin or {"kind": "manual"},
           "status": "RUNNING", "steps": steps}
    registry.put(rec)
    try:
        dmn = kg.dmn()
        step("ontology", {"decisions": sorted({r["decision"] for r in dmn}), "rules": len(dmn),
                          "candidateRules": [r["rule"] for r in dmn if r["decision"] == "dec:action-candidates"]},
             "mcp-kg T3-b: DMN 판단 → 결정표 → 규칙(임계값 TESTS · OUTPUTS · APPLIES_TO · 근거)")
        inputs = kg.inputs()
        known = {"pattern": pattern, "cause": cause["id"], "failure_mode": cause.get("failureModeId"),
                 "failure_mode_name": cause.get("failureMode")}
        facts, prov = gather_facts(inputs, asset, known, tsdb)
        if overrides:
            facts.update(overrides)
            for p in prov:
                if p["variable"] in overrides:
                    p.update(value=overrides[p["variable"]], how="사람이 바꿔 넣은 값 (가정 실험)")
        step("facts", prov, "T3-h: InputData -SOURCED_FROM-> 시스템 · 센서 — 규칙이 검사할 사실을 온톨로지가 정한 출처에서 가져온다",
             status="DONE" if not any(p.get("error") for p in prov) else "FAILED")
        cand_ids = sorted({sid for r in dmn if r["decision"] == "dec:action-candidates" for sid in r.get("outputs") or []})
        skills = {r["skillId"]: r for r in kg.skills(cand_ids)}
        forecasts = kg.forecasts(cause["id"])
        tradeoffs = kg.tradeoffs(cand_ids)
        precedents = kg.precedents(cause.get("failureModeId") or "")
        result = cards.evaluate(dmn, skills, facts, forecasts, tradeoffs, precedents, kg.suppliers())
        step("candidates", [{"rule": t["rule"], "when": t["when"], "fired": t["fired"], "unknown": t["unknown"]}
                            for t in result["trace"] if t["decision"] == "dec:action-candidates"],
             "dec:action-candidates: 고장 유형 · PLC 상태 규칙 → 후보 SOP 스킬 (원인 한정 스킬은 원인으로 거름)")
        step("compliance", [{"skill": o["sopId"] + " " + o["name"], "excluded": [v["annotation"] for v in o["violations"]],
                             "penalty": [p["annotation"] for p in o["penalties"]], "warn": [w["annotation"] for w in o["warnings"]]}
                            for o in result["options"]],
             "dec:compliance: 후보마다 예측 유온 · 스킬 종류 · 명령 코드 · 공급사 승인을 규칙 임계값에 대어 제외 · 감점 · 경고")
        step("tradeoffs", [{"skill": o["sopId"], "forecast": [f"{f['name']} {f['value']}{f['unit']}" for f in o["forecast"]],
                            "gains": [g["name"] for g in o["gains"]], "losses": [l["name"] for l in o["losses"]],
                            "precedent": o["precedent"]} for o in result["options"]],
             "T3-c/d/e: BSC 상충(스킬 → 성과 지표, 소유 부서) · 조치별 예측 · 같은 고장 유형의 선례")
        step("rank", {"recommended": result["recommended"], "order": [f"{o['rank']}. {o['sopId']} ({o['score']})" for o in result["options"]],
                      "rule": (result.get("rankRule") or {}).get("annotation"), "explanation": result["explanation"]},
             "dec:rank-actions: 온톨로지 순위 규칙의 식으로 점수 · 순위")
        violations = guardrail.check_cards(result)
        step("guardrail", {"violations": violations}, "가드레일: 규칙 인용 · 권고 카드의 규정 · 승인 역할 · SOP 단계",
             status="DONE" if not violations else "FAILED")
        roles = {r["id"]: {"name": r["name"], "level": r["level"], "dept": r["deptName"]} for r in kg.roles()}
        scenario = {"id": "dec:rank-actions", "name": f"{cause.get('failureMode') or ''} 조치 판단", "pattern": pattern,
                    "cause": cause.get("name"), "failureMode": cause.get("failureMode")}
        rec.update(scenario=scenario, result=result, facts=facts, provenance=prov, roles=roles,
                   recommended=result["recommended"], explanation=result["explanation"], applicable=bool(result["options"]))
        if violations:
            rec["status"] = "REJECTED_BY_GUARDRAIL"
            return rec
        if not result["recommended"]:
            rec["status"] = "NO_FEASIBLE_OPTION"
        if do_submit and result["options"]:
            payload = {"id": rec["id"], "schema": "v2", "scenario": scenario, "asset": asset, "origin": rec["origin"],
                       "recommended": result["recommended"], "explanation": result["explanation"], "options": result["options"],
                       "rankRule": result.get("rankRule"), "roles": roles, "facts": facts,
                       "provenance": prov, "applicable": True}
            res = submit(payload)
            step("submit", res, "process API에 조치 카드 제출 (에이전트의 유일한 쓰기) — 실행은 사람이 고른 뒤 L9가 한다")
            rec["status"] = "SUBMITTED"
        elif rec["status"] == "RUNNING":
            rec["status"] = "EVALUATED"
        return rec
    except Exception as e:  # noqa: BLE001
        log.exception("decision %s failed", rec["id"])
        step("error", {"error": str(e)}, "실패", status="FAILED")
        rec["status"] = "FAILED"
        rec["error"] = str(e)
        return rec
