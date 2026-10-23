"""L8 action-card decision (IO side of cards.py), traced step by step like the guide-card run.

ontology (T3 DMN rules) -> inputs (InputData -SOURCED_FROM-> System | Sensor) -> facts (TSDB · process · MES) ->
candidates (dec:action-candidates) -> compliance (dec:compliance) -> forecasts · BSC trade-offs · precedents ->
rank (dec:rank-actions) -> guardrail -> submit (POST process /api/decisions — the agent's only write *of action cards*;
the legacy pipeline in main.py has already posted the guide card to /api/incidents before calling decide()).
"""
from __future__ import annotations

import json
import logging
import math
import os
import secrets
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import cards, guardrail
from .tools import mcp_ent
from .tools.physical import binding, is_physical, read_physical, read_physical_fact

log = logging.getLogger("agent.decide")
PROCESS_URL = os.getenv("PROCESS_URL", "http://process:8080")
# C2 (확정 2026-10-09): 업무 경보 시나리오의 판단 입력 — 온톨로지 InputData 의 변수 이름(scenario_structure.cypher) 그대로.
#   B 정기 정비: CMMS 정기 정비 계획 · 운전시간 계수기 한 행(GET /cmms/pm_status — ent.pm_status)
#   C 예비품 구매: ERP 예비품 재고(GET /erp/spare_stock) — 재주문점 아래인 부품(없으면 정비 키트 부품)의 한 행
CMMS_PM_FACTS = ("hours_since_pm", "hours_at_next_window", "hours_at_following_window", "pm_crew_available", "spare_available")
ERP_SPARE_FACTS = ("spare_gap", "need_qty", "need_by_days")
SENSOR_TAGS = {"ts1": "TS1", "ce": "CE", "ps1": "PS1", "fs1": "FS1", "vs1": "VS1", "load": "LoadSP"}
MAX_APPROVAL_FACT_AGE_S = float(os.getenv('APPROVAL_FACT_MAX_AGE_S', '15'))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


ID_KINDS = ("DEC", "EVAL")
#: Which service minted a decision id. The agent service (main.py) and dmn-mcp (DmnTools) each keep their own registry and
#: post to the same process decision book, so the id says which one it came from.
ID_SERVICES = ("agent", "mcp")


class DecisionRegistry:
    def __init__(self, service: str = "agent"):
        if service not in ID_SERVICES:
            raise ValueError(f"판단 id 를 만드는 서비스는 {', '.join(ID_SERVICES)} 중 하나입니다 (받은 값: {service!r})")
        self.service = service
        self._lock = threading.Lock()
        self._items: dict[str, dict] = {}
        self._seq = 0

    def new_id(self, kind: str) -> str:
        """kind: DEC = process 에 제출해 저장되는 판단(GET /api/decisions/{id}), EVAL = 제출하지 않는 읽기 평가(evaluate_cards · 가정 실험).
        라이브 3차: 읽기 평가도 DEC- id 를 받아 처리 기록에 '저장되지 않은 판단 id'(GET 404)가 판단처럼 보였다.
        2026-10-23 검수: `{kind}-MMDD-{seq}-{2바이트}` 는 서비스 · 재시작마다 seq 가 1부터 다시 시작하고, process 판단 장부(book)는
        재시작 뒤에도 남는다. 같은 날 같은 seq 면 4자리 16진수(65,536가지)로만 갈려, 새 판단이 409(다른 작업 · 세대) 또는
        legacy 경로의 duplicate 응답(옛 판단을 돌려주고 새 카드는 저장 안 됨)이 됐다. 서비스 이름과 12자리 16진수(48비트)를 붙인다."""
        if kind not in ID_KINDS:
            raise ValueError(f"판단 기록 id 종류는 {', '.join(ID_KINDS)} 중 하나입니다 (받은 값: {kind!r})")
        with self._lock:
            self._seq += 1
            return f"{kind}-{datetime.now():%m%d}-{self.service}-{self._seq:03d}-{secrets.token_hex(6)}"

    def put(self, d: dict) -> None:
        with self._lock:
            self._items[d["id"]] = d
            if len(self._items) > 200:
                self._items.pop(next(iter(self._items)))

    def get(self, did: str) -> dict | None:
        return self._items.get(did)

    def submitted(self, record: dict, decision_id: str) -> None:
        """Only a confirmed process submission earns a persisted-decision id."""
        with self._lock:
            self._items.pop(record["id"], None)
            record["id"] = decision_id
            self._items[decision_id] = record

    def all(self) -> list[dict]:
        return sorted(self._items.values(), key=lambda d: d["created"], reverse=True)


def _get_json(url: str, timeout: float = 5.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


class SubmitRefused(RuntimeError):
    """The process service refused the decision — carries its status and reason (FastAPI `detail`)."""


def submit(payload: dict) -> dict:
    req = urllib.request.Request(f"{PROCESS_URL}/api/decisions", data=json.dumps(payload, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        # 2026-10-23 live: only "HTTP Error 409: Conflict" reached the agent and the case record — the reason the process gave was dropped.
        body = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(body).get("detail", body)
        except ValueError:
            detail = body
        refused = SubmitRefused(f"process 가 판단 등록을 거절했습니다 (HTTP {e.code}): {detail}"[:600])
        refused.status = e.code
        raise refused from e
    # 2026-10-23 검수: process 는 이미 장부에 있는 id 를 받으면(작업 · 세대가 같을 때) 새 카드를 저장하지 않고 옛 판단을
    # `duplicate: true` 로 돌려준다. 이 판단의 id 는 방금 새로 만든 것이라 같은 id 가 있으면 다른 판단과 충돌한 것이다.
    if not isinstance(res, dict) or res.get('id') != payload['id'] or res.get('duplicate'):
        refused = SubmitRefused('process 가 이 판단을 새로 저장하지 않았습니다: 같은 판단 id 의 다른 판단이 장부에 이미 있습니다 '
                                f"({payload['id']}, 응답 {json.dumps(res, ensure_ascii=False)[:200]})"[:600])
        refused.status = 409
        raise refused
    return res


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
    plant = erp = qms = pm = spare = None
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
                from .forecasting import stack_time_scale
                scale = stack_time_scale()
                facts[var] = tsdb.fan100_hours(asset, time_scale=scale)
                row.update(value=facts[var], time_scale=scale,
                           how=f"TimescaleDB FanSpeedSP ≥ 99 % 현재 연속 운전 시간, 설비 시간(실제 시간 × 배율 {scale:g}) "
                               "(HM-8.5 · 8.8; 관측 없으면 미확인)")
            elif src == "sys:mes" and var == "order_due_h":
                mes = mcp_ent.fetch("/mes/orders?asset={asset}", asset)
                facts[var] = (mes.get("facts") or {}).get("due_in_h")
                # A086: the hours are computed from the MES due date at read time; the due date itself is the business record
                row.update(value=facts[var], how="MES 생산오더 납기까지 남은 시간 (납기 일시 기준, 조회 시각에 계산)",
                           anchor=(mes.get("facts") or {}).get("due_at"), **source_time(mes, asset))
            elif src == 'sys:mes' and var == 'production_running':
                mes = mcp_ent.fetch('/mes/orders?asset={asset}', asset)
                rows = mes.get('records')
                if not isinstance(rows,list) or any(not isinstance(r,dict) or not isinstance(r.get('status'),str) for r in rows):
                    raise ValueError('MES 생산 오더의 실제 상태 목록을 확인할 수 없습니다')
                facts[var] = any(r.get('asset') == asset and r['status'] == 'RUNNING' for r in rows)
                row.update(value=facts[var],how='MES 현재 설비 생산 오더의 실제 RUNNING 상태',**source_time(mes,asset))
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
            elif src == "sys:cmms" and var in CMMS_PM_FACTS:
                if pm is None:
                    pm = mcp_ent.fetch('/cmms/pm_status?asset={asset}', asset)
                    facts.setdefault("windows_by_variable", pm_windows(pm.get('facts') or {}))
                    pmfacts = pm.get('facts') or {}
                    facts.update(existing_pm_order=pmfacts.get('existing_pm_order'),
                                 pm_planned_wo=pmfacts.get('pm_planned_wo'),pm_cycle=pmfacts.get('pm_cycle'),
                                 pm_limit_hours=(pmfacts.get('pm_interval_h') * (1 + pmfacts.get('pm_tolerance_pct') / 100)
                                     if type(pmfacts.get('pm_interval_h')) in (int,float) and type(pmfacts.get('pm_tolerance_pct')) in (int,float) else None))
                facts[var] = (pm.get('facts') or {}).get(var)
                row.update(value=facts[var], how='CMMS 정기 정비 계획 · 운전시간 계수기 (예정된 정비 시간까지의 운전시간 · 인원 · 정비 키트 재고)',
                           **source_time(pm, asset))
            elif src == "sys:erp" and var in ERP_SPARE_FACTS:
                if spare is None:
                    spare = spare_facts(asset, known['purchase_part_no']) if known.get('purchase_part_no') else spare_facts(asset)
                    facts.update({k: spare.get(k) for k in ("spare_part_no", "spare_quotes", "need_qty", "need_by_days") if k not in facts})
                facts[var] = spare.get(var)
                row.update(value=facts[var], how=f"ERP 예비품 재고 {spare.get('spare_part_no')} (가용 = 실물 − 예약 + 입고 예정, 재주문점 · 목표 · 필요일)",
                           observed_at=_now())
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


def pm_windows(row: dict) -> dict:
    """C3: 정기 정비 판단 변수 → 그 변수가 가리키는 예정된 정비 시간(CMMS ent.pm_status 한 행). 카드가 고른 시점을 작업지시에 싣는 데 쓴다
    (cards.option_window). 창 id 가 없으면 빼서, 모르는 창을 지어내지 않는다."""
    out = {}
    for var, key, name in (("hours_at_next_window", "night_window", "이번 예정된 정비 시간"),
                           ("hours_at_following_window", "following_window", "그다음 예정된 정비 시간")):
        if row.get(f"{key}_id"):
            out[var] = {"id": row[f"{key}_id"], "starts_at": row.get(f"{key}_at"), "name": name}
    return out


def pm_context(asset):
    """Actual all-asset counters and all-part availability; no master values inferred."""
    response=mcp_ent.fetch('/cmms/pm_status',asset)
    stock=mcp_ent.fetch('/erp/spare_stock',asset)
    rows=response.get('records');parts=stock.get('records')
    if not isinstance(rows,list) or not isinstance(parts,list):
        raise ValueError('실제 CMMS 전체 설비 상태와 ERP 전체 재고 응답이 없습니다')
    return dict(asset=asset,records=rows,parts=parts,source='CMMS/ERP',
                observed_at=_now(),source_as_of=response.get('as_of'))


def spare_facts(asset: str, part_no: str | None = None) -> dict:
    """C 판단의 재고 사실: 재주문점 아래인 중요 예비품(여럿이면 차이가 큰 것), 없으면 정기 정비 키트 부품. 그 부품의 공급사 견적도 함께
    (spare_quotes: 공급사 → 단가 · 리드타임 · 불량률 · AVL — 카드마다 발주 금액 · 납기 여유를 계산하는 데 쓴다, cards.candidate_facts)."""
    stock = mcp_ent.fetch('/erp/spare_stock', asset)
    rows = [r for r in stock.get('records') or [] if isinstance(r, dict)]
    below = sorted((r for r in rows if r.get('below_reorder_point')), key=lambda r: r.get('spare_gap') or 0)
    if part_no is not None:
        matches = [r for r in rows if r.get('part_no') == part_no and r.get('below_reorder_point')]
        if len(matches) != 1:
            raise ValueError('요청한 구매 부품의 실제 재주문점 이탈 행을 확인할 수 없습니다')
        row = matches[0]
    else:
        row = below[0] if below else next((r for r in rows if r.get('part_no') == 'P-PMP-SEAL'), rows[0] if rows else {})
    part = row.get('part_no')
    quotes = {}
    if part:
        for q in (mcp_ent.fetch(f'/scm/quotes?part={part}', asset).get('records') or []):
            quotes[q['supplier']] = {k: q.get(k) for k in ('price', 'lead_d', 'fail_rate', 'avl', 'name')}
    return {'spare_part_no': part, 'spare_gap': row.get('spare_gap'), 'need_qty': row.get('need_qty'),
            'need_by_days': row.get('need_by_days'), 'spare_quotes': quotes}


def decide(kg, registry: DecisionRegistry, tsdb, asset: str, pattern: str, cause: dict, origin: dict | None = None,
           overrides: dict | None = None, do_submit: bool = True, capture: dict | None = None,
           purchase_part: dict | None = None) -> dict:
    """cause: the top ranked cause of the guide card ({id, name, failureModeId, failureMode}). overrides: facts set by a person
    (portal 'what if' — e.g. plc_mode REMOTE_MANUAL) to watch the DMN rules react. capture: A7 what-if — receives the exact
    inputs cards.evaluate used, so trials re-rank the same snapshot (read-only)."""
    if overrides and do_submit:
        raise ValueError('가정 facts는 읽기 전용 evaluate_cards에서만 사용할 수 있습니다')
    from . import forecasting
    steps: list[dict] = []

    def step(name, output, note, status="DONE"):
        steps.append({"name": name, "status": status, "t": _now(), "note": note, "output": output})

    rec = {"id": registry.new_id("EVAL"), "created": _now(), "schema": "v2", "asset": asset, "origin": origin or {"kind": "manual"},
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
        if purchase_part is not None:
            if pattern != 'SPARE_BELOW_MIN':
                raise ValueError('명시 구매 Part 경로는 SPARE_BELOW_MIN에서만 사용합니다')
            known.update(purchase_part=purchase_part['id'], purchase_part_no=purchase_part['partNo'],
                         purchase_part_name=purchase_part.get('name'))
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
        skills = cards.scoped_skills(pattern, skills, purchase_part['id'] if purchase_part else None)
        if pattern == 'PM_DUE':
            try:
                facts['pm_context']=pm_context(asset)
            except Exception as exc:
                facts['pm_context']=dict(asset=asset,error=str(exc))
        if pattern == 'PM_DUE' and not skills:
            rec['error_code'] = 'BUSINESS_CANDIDATES_MISSING'
            raise ValueError('PM_DUE 예방 정비 후보 지식이 없습니다: PREVENTED_BY 스킬과 후보 규칙을 확인하세요. 고장 대응 카드로 대체하지 않습니다')
        if pattern == 'SPARE_BELOW_MIN' and not skills:
            rec['error_code'] = 'BUSINESS_CANDIDATES_MISSING'
            raise ValueError('SPARE_BELOW_MIN 구매 후보 지식이 없습니다: PR_CREATE만 수행하는 work_order 스킬과 후보 규칙을 확인하세요. 운전·정비 카드로 대체하지 않습니다')
        if pattern == 'SPARE_BELOW_MIN':
            if purchase_part is not None and facts.get('spare_part_no') != purchase_part['partNo']:
                rec['error_code'] = 'BUSINESS_FACTS_MISSING'
                raise ValueError('요청한 구매 Part와 실제 ERP 부족부품 사실이 다릅니다. 다른 부품의 견적으로 판단하지 않습니다')
            missing = [key for key in ERP_SPARE_FACTS if type(facts.get(key)) not in (int, float)
                       or not math.isfinite(facts[key])]
            if missing or facts['need_qty'] <= 0:
                rec['error_code'] = 'BUSINESS_FACTS_MISSING'
                raise ValueError('SPARE_BELOW_MIN 구매 판단의 실제 업무 사실을 확인할 수 없습니다: ' + ', '.join(missing or ['need_qty']))
        cand_ids = [sid for sid in cand_ids if sid in skills]
        forecasts, forecast_contexts = ({}, None) if purchase_part is not None else forecasting.candidates(kg, asset, skills)
        step('forecast', forecast_contexts, '구매는 물리 예측을 사용하지 않고 검토된 원문 총비용과 실제 부품 견적을 비교한다' if purchase_part is not None else '설비별 명시 모델과 동일 시점 원천으로 조치별 예측; 고정 설계점으로 대체하지 않음')
        tradeoffs = kg.tradeoffs(cand_ids)
        precedents = kg.precedents(cause.get("failureModeId") or "")
        suppliers = kg.suppliers()
        if purchase_part is not None:
            for skill in skills.values():
                if skill.get('supplier_policy'):
                    from hydcommon.skill_scope import SupplierUnresolved, resolve_supplier
                    try:
                        resolve_supplier(skill, facts)
                    except SupplierUnresolved:
                        pass        # that card alone is impossible; cards.evaluate records why
                    continue
                supplier = skill['actions'][0].get('value')
                quote = (facts.get('spare_quotes') or {}).get(supplier)
                if not isinstance(quote, dict) or type(quote.get('avl')) is not bool or any(
                        type(quote.get(key)) not in (int, float) or not math.isfinite(quote[key])
                        for key in ('price', 'lead_d', 'fail_rate')):
                    rec['error_code'] = 'BUSINESS_FACTS_MISSING'
                    raise ValueError(f'구매 범위 부품의 실제 공급사 견적·AVL을 확인할 수 없습니다: {supplier}')
                if quote['price'] < 0 or quote['lead_d'] < 0 or not 0 <= quote['fail_rate'] <= 1:
                    rec['error_code'] = 'BUSINESS_FACTS_MISSING'
                    raise ValueError(f'실제 공급사 견적의 수치 범위를 확인하세요: {supplier}')
        result = cards.evaluate(dmn, skills, facts, forecasts, tradeoffs, precedents, suppliers, forecast_contexts, evaluation_mode='execution')
        if pattern == 'SPARE_BELOW_MIN' and not result['options']:
            rec['error_code'] = 'BUSINESS_CANDIDATES_MISSING'
            step('candidates', result['trace'], '현재 업무 사실·원인으로 선택된 구매 후보 없음', status='FAILED')
            raise ValueError('SPARE_BELOW_MIN의 현재 업무 사실·원인에 맞게 발화한 구매 후보가 없습니다. 후보 규칙과 구매 지식을 확인하세요')
        if capture is not None:
            capture.update(dmn=dmn, skills=skills, facts=dict(facts), forecasts=forecasts, tradeoffs=tradeoffs, precedents=precedents,
                           suppliers=suppliers, forecast_contexts=forecast_contexts)
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
            decision_id = registry.new_id("DEC")
            payload = {"id": decision_id, "schema": "v2", "scenario": scenario, "asset": asset, "origin": rec["origin"],
                       "recommended": result["recommended"], "explanation": result["explanation"], "options": result["options"],
                       "rankRule": result.get("rankRule"), "roles": roles, "facts": facts,
                       "evaluation_mode": result['evaluation_mode'], "execution_checked": result['execution_checked'],
                       "provenance": prov, "applicable": True}
            try:
                res = submit(payload)
            except SubmitRefused as exc:
                # the process looked at the cards and said no (scope · state · duplicate id): its reason is the failure
                rec['error_code'], rec['submit_status'] = 'SUBMIT_REFUSED', getattr(exc, 'status', None)
                raise
            except Exception:
                rec['error_code'] = 'SUBMIT_FAILED'      # unreachable process, timeout, unreadable reply
                raise
            registry.submitted(rec, decision_id)
            step("submit", res, "process API에 조치 카드 제출 (에이전트의 유일한 쓰기) — 실행은 사람이 고른 뒤 L9가 한다")
            rec["status"] = "SUBMITTED"
        elif rec["status"] == "RUNNING":
            rec["status"] = "EVALUATED"
        return rec
    except Exception as e:  # noqa: BLE001
        if purchase_part is not None and isinstance(e, ValueError) and not rec.get('error_code'):
            rec['error_code'] = 'PURCHASE_MODEL_INVALID'
        log.exception("decision %s failed", rec["id"])
        step("error", {"error": str(e)}, "실패", status="FAILED")
        rec["status"] = "FAILED"
        rec["error"] = str(e)
        return rec
