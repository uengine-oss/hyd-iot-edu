"""L8 action-card decision (IO side of cards.py), traced step by step like the guide-card run.

ontology (T3 DMN rules) -> inputs (InputData -SOURCED_FROM-> System | Sensor) -> facts (TSDB · process · MES) ->
candidates (dec:action-candidates) -> compliance (dec:compliance) -> forecasts · BSC trade-offs · precedents ->
rank (dec:rank-actions) -> guardrail -> submit (POST process /api/decisions — the agent's only write *of action cards*;
the legacy pipeline in main.py has already posted the guide card to /api/incidents before calling decide()).
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
from .tools.physical import binding, is_physical, read_physical, read_physical_fact

log = logging.getLogger("agent.decide")
PROCESS_URL = os.getenv("PROCESS_URL", "http://process:8080")
SENSOR_TAGS = {"ts1": "TS1", "ce": "CE", "ps1": "PS1", "fs1": "FS1", "vs1": "VS1", "load": "LoadSP"}
MAX_APPROVAL_FACT_AGE_S = float(os.getenv('APPROVAL_FACT_MAX_AGE_S', '15'))


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


def source_time(response: dict, asset: str) -> dict:
    """A085 (R05, meeting L75~79): when a business fact was read, and the source's own time for the asset's row when the
    source gives one (records[].updated_at). A source without row times is recorded as such — never filled in."""
    stamps = sorted(str(r['updated_at']) for r in response.get('records') or []
                    if isinstance(r, dict) and r.get('asset') in (asset, None) and r.get('updated_at'))
    return {'observed_at': _now(), 'source_as_of': stamps[-1] if stamps else None,
            'source_time': 'record updated_at' if stamps else '원천이 행 시점을 주지 않음'}


def gather_facts(inputs: list[dict], asset: str, known: dict, tsdb, *, strict: bool = False) -> tuple[dict, list[dict]]:
    """Fetch every InputData the DMN rules may test, from the source the ontology names for it.
    known: facts the pipeline already has (pattern, cause, failure_mode, alert evidence). Returns (facts, provenance)."""
    facts, prov = dict(known), []
    plant = erp = qms = None
    identities = {}
    for item in inputs:
        identities.setdefault(item['variable'], set()).add(json.dumps(binding(item), sort_keys=True))
    for i in inputs:
        var, src, kind = i["variable"], i["source"], i["sourceKind"]
        row = {"variable": var, "name": i["name"], "source": src, "sourceName": i["sourceName"], "represents": i.get("representsName")}
        physical = is_physical(i)
        if physical:
            row['binding'] = binding(i)
        try:
            if len(identities[var]) != 1:
                raise ValueError('ambiguous InputData bindings for variable')
            if physical:
                if not src:
                    raise ValueError('physical InputData has no declared source')
                if i.get('sourceState') not in (None, 'OK'):
                    # A087: the business DDL changed under this binding (column gone or meaning changed) — never read it
                    raise ValueError(f"원천 열이 DDL 동기화에서 {i['sourceState']}로 확인돼 판단에 쓰지 않습니다"
                                     f" (선언 {i.get('sqlType')}, 현재 {i.get('sourceLiveType') or '없음'}). 지식 작성자가 DDL을 다시 적재·검토해야 합니다")
                facts[var], anchor = read_physical_fact(i, asset) if i.get('derive') else (read_physical(i, asset), None)
                row.update(value=facts[var], how='명시된 업무 DB 물리 출처의 설비별 단일 행' + (' (시각 열을 지금부터 h로 환산)' if i.get('derive') else ''),
                           observed_at=_now(), **({'anchor': anchor} if i.get('derive') else {}))
            elif var in facts and facts[var] is not None:
                row.update(value=facts[var], how="파이프라인이 이미 가진 값")
            elif kind == "Sensor" or var in SENSOR_TAGS and src in ("sys:scada",):
                tag = i.get("tag") or SENSOR_TAGS.get(var)
                v, age = tsdb.latest(asset, tag)
                row['age_seconds'] = age
                if strict and (age is None or not -2 <= age <= MAX_APPROVAL_FACT_AGE_S):
                    raise ValueError(f'{tag} 최신값 시각을 신뢰할 수 없습니다 (age={age})')
                facts[var] = None if v is None else round(v, 3)
                row.update(value=facts[var], how=f"TimescaleDB tag_1s {tag} 최신값 ({age:.0f} s 전)" if v is not None else f"TimescaleDB {tag} 값 없음")
            elif src == "sys:scada" and var in ("plc_mode", "plc_state"):
                if plant is None:
                    plant = _get_json(f"{PROCESS_URL}/api/plant/{asset}/status")
                if strict:
                    observed = datetime.fromisoformat(str(plant.get('t') or '').replace('Z', '+00:00'))
                    if observed.tzinfo is None:
                        raise ValueError('PLC 상태 시각에 시간대가 없습니다')
                    age = (datetime.now(timezone.utc) - observed).total_seconds()
                    row.update(age_seconds=age, observed_at=plant['t'])
                    if not -2 <= age <= MAX_APPROVAL_FACT_AGE_S:
                        raise ValueError(f'PLC 상태가 오래됐거나 미래 시각입니다 (age={age})')
                facts[var] = plant.get("mode" if var == "plc_mode" else "state")
                row.update(value=facts[var], how="plant.status 최신 메시지 (process 서비스가 구독)")
            elif src == "sys:historian" and var == "fan100_hours":
                if strict:
                    _, age = tsdb.latest(asset, 'FanSpeedSP')
                    row['age_seconds'] = age
                    if age is None or not -2 <= age <= MAX_APPROVAL_FACT_AGE_S:
                        raise ValueError('팬 운전 이력의 최신 수집을 확인할 수 없습니다')
                facts[var] = tsdb.fan100_hours(asset)
                row.update(value=facts[var], how="TimescaleDB FanSpeedSP ≥ 99 % 현재 연속 운전 시간 (HM-7.3; 관측 없으면 미확인)")
            elif src == "sys:mes" and var == "order_due_h":
                mes = mcp_ent.fetch("/mes/orders?asset={asset}", asset)
                facts[var] = (mes.get("facts") or {}).get("due_in_h")
                # A086: the hours are computed from the MES due date at read time; the due date itself is the business record
                row.update(value=facts[var], how="MES 생산오더 납기까지 남은 시간 (납기 일시 기준, 조회 시각에 계산)",
                           anchor=(mes.get("facts") or {}).get("due_at"), **source_time(mes, asset))
            elif src == "sys:erp" and var in ("order_penalty_per_h", "order_customer_tier"):
                # 회의 L385~404: 납기 상충은 설비 상태만이 아니라 계약(지연 보상 · 고객 등급)을 같이 봐야 판단된다
                if erp is None:
                    erp = mcp_ent.fetch("/erp/contract?asset={asset}", asset)
                facts[var] = (erp.get("facts") or {}).get("penalty_per_h" if var == "order_penalty_per_h" else "customer_tier")
                row.update(value=facts[var], how="ERP 계약 조건 (지연 시 시간당 보상 · 고객 등급)", **source_time(erp, asset))
            elif src == "sys:qms" and var in ("hot_lot_claim", "hot_lot_qty"):
                if qms is None:
                    qms = mcp_ent.fetch("/qms/lots?asset={asset}", asset)
                lots = qms.get("facts") or {}
                qty = lots.get("auto_qty")
                if not isinstance(qty, (float, int)) or isinstance(qty, bool) or qty < 0:
                    facts[var] = None
                else:
                    facts[var] = qty if var == "hot_lot_qty" else (lots.get("auto_claim") if qty > 0 else 0)
                row.update(value=facts[var], how="QMS 고온 구간 출하 대기 로트 (OEM 클레임 위험)", **source_time(qms, asset))
            elif src == "sys:cmms" and var == "standby_ready":
                cmms = mcp_ent.fetch('/cmms/history?asset={asset}', asset)
                value = (cmms.get('facts') or {}).get('standby_ready')
                facts[var] = value if type(value) is bool else None
                row.update(value=facts[var], how='CMMS 설비별 예비 펌프 준비 상태 (값이 없으면 미확인)', **source_time(cmms, asset))
            elif src in ("sys:agent", "sys:scm", "sys:process", "sys:cep"):
                row.update(value=facts.get(var), how="후보마다 계산하거나 경보 · 결정 시점에 정해진다")
            else:
                facts[var] = None
                row.update(value=None, how="출처 조회 방법 없음")
        except Exception as e:  # noqa: BLE001
            facts[var] = None
            row.update(value=None, error=str(e)[:160])
        prov.append(row)
    return facts, prov


def decide(kg, registry: DecisionRegistry, tsdb, asset: str, pattern: str, cause: dict, origin: dict | None = None,
           overrides: dict | None = None, do_submit: bool = True) -> dict:
    """cause: the top ranked cause of the guide card ({id, name, failureModeId, failureMode}). overrides: facts set by a person
    (portal 'what if' — e.g. plc_mode REMOTE_MANUAL) to watch the DMN rules react."""
    if overrides and do_submit:
        raise ValueError('가정 facts는 읽기 전용 evaluate_cards에서만 사용할 수 있습니다')
    from . import forecasting
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
        forecasts, forecast_contexts = forecasting.candidates(kg, asset, skills)
        step('forecast', forecast_contexts, '설비별 명시 모델과 동일 시점 원천으로 조치별 예측; 고정 설계점으로 대체하지 않음')
        tradeoffs = kg.tradeoffs(cand_ids)
        precedents = kg.precedents(cause.get("failureModeId") or "")
        result = cards.evaluate(dmn, skills, facts, forecasts, tradeoffs, precedents, kg.suppliers(), forecast_contexts)
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
