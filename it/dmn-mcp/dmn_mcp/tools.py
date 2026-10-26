"""The deterministic L8 engine (it/agent/agentsvc: card · cards · decide · tools) as callable tools.

ProcessGPT's principle "repeated judgments become DMN rules; the LLM gathers and explains" (process-gpt README,
Deterministic Regularization). Claude Code calls these to get rule results it must not re-derive by itself.
Nothing here writes to a plant or an enterprise system; `submit_decision` posts the ranked cards to the process
service, which is the agent's only write (same as the legacy agent service).
"""
from __future__ import annotations

import psycopg

from agentsvc import card as cardlib, decide as decidelib, llm
from agentsvc.tools import mcp_ent, mcp_kg, mcp_prom, mcp_tsdb
from agentsvc.tools.prometheus import Prometheus
from hydcommon.fabric import CROSS_QUERIES, ENT, TS, Fabric


#: Recorded in a decision's origin: where the cause argument of evaluate_cards/submit_decision was checked against.
CAUSE_BASIS = "ontology T1 (pattern → symptom → failure mode ← cause), same query as diagnose"
#: C2: 업무 경보(재고 · 운전시간)에는 증상(T1)이 없다. 원인은 업무 근거로 이어진 것만 받는다(business_causes 와 같은 질의).
BUSINESS_CAUSE_BASIS = {
    "SPARE_BELOW_MIN": "ontology: cause -INVOLVES_PART-> part (ERP 재주문점 아래 부품), cause -CAUSES-> failure mode",
    "PM_DUE": "ontology: failure mode -PREVENTED_BY-> skill (정기 정비가 막는 고장), cause -CAUSES-> failure mode",
}
#: 원인 근거의 종류(판단 origin.cause_route) — 화면이 원인을 '진단'으로 읽을지, '이 부품이 고치는 원인' · '정비로 막는 원인'으로 읽을지 정한다.
#: 라이브 3차: 업무 경보도 cause_basis 에 T1(증상) 문장이 적혀 C 발주가 고장 진단처럼 보였다.
DIAGNOSIS_ROUTE = "diagnosis"
BUSINESS_CAUSE_ROUTE = {"SPARE_BELOW_MIN": "part", "PM_DUE": "prevention"}
BUSINESS_CAUSES = {
    # 재고가 모자란 부품을 쓰는 원인(그 부품을 교체해 고치는 고장) — 구매 SOP 가 ADDRESSES 로 그 원인을 가리킨다
    "SPARE_BELOW_MIN": "MATCH (c:Cause)-[:INVOLVES_PART]->(p:Part) WHERE p.partNo IN $parts MATCH (c)-[:CAUSES]->(fm:FailureMode) "
                       "RETURN c.id AS causeId, c.name AS cause, fm.id AS failureModeId, fm.name AS failureMode, p.partNo AS partNo, "
                       "c.prior AS prior ORDER BY c.prior DESC",
    # 정기 정비가 막는 고장과 그 원인
    "PM_DUE": "MATCH (fm:FailureMode)-[:PREVENTED_BY]->(:Skill) WITH DISTINCT fm MATCH (c:Cause)-[:CAUSES]->(fm) "
              "RETURN c.id AS causeId, c.name AS cause, fm.id AS failureModeId, fm.name AS failureMode, null AS partNo, "
              "c.prior AS prior ORDER BY c.prior DESC",
}


def ok(document) -> dict:
    """The result envelope the WMS sample's MCP uses: {"result": "ok", "document": …}."""
    return {"result": "ok", "document": document}


def error(kind: str, message: str) -> dict:
    """kind: INVALID (bad input) | UNKNOWN (engine / graph / network)."""
    return {"result": "error", "error_kind": kind, "message": message}


class NotRegistered(RuntimeError):
    """A decision the tool did not store (refused · failed · nothing to submit). `kind` is the envelope's error_kind; the
    message keeps the process reason whole (decide.SubmitRefused is up to 600 characters)."""
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


BUSINESS_ERRORS = ('BUSINESS_CANDIDATES_MISSING', 'BUSINESS_FACTS_MISSING', 'PURCHASE_MODEL_INVALID')


def failure(rec: dict, what: str) -> NotRegistered:
    """The error for a FAILED decision record. 2026-10-23 audit: submit_decision returned result=ok with an unsaved EVAL- id
    and ranked cards when the process refused the decision (HTTP 409) or could not be reached; the worker then reported
    that id and the process said '판단 원문을 찾을 수 없습니다' — the real reason was lost."""
    code, reason = rec.get('error_code'), rec.get('error') or '원인 미상'
    if code == 'SUBMIT_REFUSED':
        status = rec.get('submit_status')
        return NotRegistered('INVALID' if isinstance(status, int) and 400 <= status < 500 else 'UNKNOWN',
                             f'판단을 등록하지 못했습니다 — {reason}')
    if code == 'SUBMIT_FAILED':
        return NotRegistered('UNKNOWN', f'판단을 등록하지 못했습니다 — process 에 연결하거나 응답을 읽지 못했습니다: {reason}')
    return NotRegistered('INVALID' if code in BUSINESS_ERRORS else 'UNKNOWN', f'{what}을(를) 완료하지 못했습니다 — {reason}')


def registered(rec: dict, what: str) -> dict:
    """A write tool succeeds only when the process stored the cards (status SUBMITTED — decide sets it after the process
    accepted the POST and the record took its DEC- id)."""
    if rec.get('status') == 'SUBMITTED':
        return rec
    if rec.get('status') == 'FAILED':
        raise failure(rec, what)
    if rec.get('status') == 'REJECTED_BY_GUARDRAIL':
        steps = [x for x in rec.get('steps') or [] if x.get('name') == 'guardrail']
        found = '; '.join((steps[-1].get('output') or {}).get('violations') or []) if steps else ''
        raise NotRegistered('UNKNOWN', f'가드레일이 카드 묶음을 거절해 판단을 등록하지 않았습니다 — {found or "위반 내용 미상"}')
    if not (rec.get('result') or {}).get('options'):
        raise NotRegistered('INVALID', '현재 사실·규칙으로 선택된 조치 후보가 0개라 판단을 등록하지 않았습니다 — '
                            + str(rec.get('explanation') or '후보 선택 규칙과 지식을 확인하세요'))
    raise NotRegistered('UNKNOWN', f'판단을 등록하지 못했습니다 — 판단 상태 {rec.get("status")}')


def read_outcome(rec: dict, what: str, detail_option: str | None = None) -> dict:
    """A read-only evaluation: a failure is an error envelope; zero candidates or a guardrail refusal is stated in the
    result (`outcome`, `notice`) so it is not read as a ranked set. Its EVAL- id is never stored by the process."""
    if rec.get('status') == 'FAILED':
        raise failure(rec, what)
    options = (rec.get('result') or {}).get('options') or []
    if rec.get('status') == 'REJECTED_BY_GUARDRAIL':
        outcome, notice = 'guardrail_rejected', '가드레일이 이 카드 묶음을 거절했습니다. 제출해도 등록되지 않습니다'
    elif not options:
        outcome, notice = 'no_candidates', '조치 후보 0개 — ' + str(rec.get('explanation') or '후보 선택 규칙이 맞지 않음')
    elif not rec.get('recommended'):
        outcome, notice = 'no_feasible_option', '후보 ' + str(len(options)) + '장 모두 규정상 제외됐습니다'
    else:
        outcome, notice = 'ranked', '후보 ' + str(len(options)) + '장 순위 계산'
    return dict(agent_view(rec, detail_option), outcome=outcome, notice=notice + ' (읽기 평가 — 저장되지 않은 ' + str(rec.get('id')) + ', decision_id 로 쓰지 않습니다)')


#: 에이전트가 카드 비교에 쓰는 칸만. 2026-10-26 수업 한 바퀴(final6): evaluate_cards 가 판단 기록 전체(약 15만 5천 자 — 카드마다 순위 근거 ·
#: 득실 평가 · 단계 본문 · 예측 맥락, 원천 기록)를 돌려 실행기 한도를 넘었고(「exceeds maximum allowed tokens」 → 파일 저장), 에이전트가 그 파일을
#: Bash 로 조각조각 읽느라 A 판단이 152~411초 · 도구 11~34회로 갈렸다. 전체 근거는 제출된 판단 기록(처리 건 화면)에 그대로 남는다.
def _rule_lines(rows):
    return [{k: r.get(k) for k in ('rule', 'effect', 'annotation', 'penalty') if r.get(k) is not None} for r in rows or [] if isinstance(r, dict)]


def _bsc(rows):
    return [{k: g.get(k) for k in ('name', 'owner', 'conditional') if g.get(k) is not None} for g in rows or [] if isinstance(g, dict)]


#: 카드 상세(detail_option)로 줄 때도 한 칸이 이 글자 수를 넘으면 자르고 표시한다 — ontology-studio document_indexing 의 [truncated] 표시와 같은 뜻
DETAIL_FIELD_MAX_CHARS = 6000
DETAIL_FIELDS = ('rankingEvidence', 'tradeoffEvaluation', 'steps', 'forecastContext', 'facts', 'precedent', 'selectedBy')


def _capped(value):
    import json
    text = json.dumps(value, ensure_ascii=False, default=str)
    return value if len(text) <= DETAIL_FIELD_MAX_CHARS else text[:DETAIL_FIELD_MAX_CHARS] + '…[truncated]'


def agent_view(rec: dict, detail_option: str | None = None) -> dict:
    """카드 목록은 비교에 쓰는 칸만(ProcessGPT get_process_list 의 select=id,name 처럼), 카드 하나의 전체 근거는 detail_option 으로
    따로(get_process_detail 처럼). 뺀 칸과 받는 법을 omitted 로 알린다 — 잘린 줄 모르고 판단하지 않게."""
    r = rec.get('result') or {}
    provenance = rec.get('provenance') or []
    source_errors = [{k: row.get(k) for k in ('variable', 'source', 'error', 'how') if row.get(k) is not None}
                     for row in provenance if isinstance(row, dict) and row.get('error')]
    facts = dict(rec.get('facts') or {})
    facts_omitted = ['pm_context'] if 'pm_context' in facts else []
    # Full all-asset CMMS/all-part ERP rows repeat the selected plans below.
    # Keep comparison facts and plans; raw rows remain in the frozen evidence.
    facts.pop('pm_context', None)
    options = []
    for o in r.get('options') or []:
        options.append({k: v for k, v in {
            'rank': o.get('rank'), 'id': o.get('id'), 'sopId': o.get('sopId'), 'name': o.get('name'), 'kind': o.get('kind'),
            'feasible': o.get('feasible'), 'score': o.get('score'), 'scoreParts': o.get('scoreParts'),
            'approver': (o.get('approver') or {}).get('name'),
            'actions': [{k: a.get(k) for k in ('code', 'name', 'value', 'targetName')} for a in o.get('actions') or []],
            'forecast': {f.get('name'): f"{f.get('value')} {f.get('unit') or ''}".strip() for f in o.get('forecast') or [] if isinstance(f, dict)},
            'gains': _bsc(o.get('gains')), 'losses': _bsc(o.get('losses')),
            'violations': _rule_lines(o.get('violations')), 'penalties': _rule_lines(o.get('penalties')), 'warnings': _rule_lines(o.get('warnings')),
            'production': o.get('production'), 'window': o.get('window'), 'resolvedSupplier': o.get('resolvedSupplier'),
            'maintenancePlan': o.get('maintenancePlan'), 'economicComparison': o.get('economicComparison'),
        }.items() if v not in (None, [], {})})
        if detail_option and detail_option in (o.get('id'), o.get('sopId')):
            options[-1]['detail'] = {k: _capped(o[k]) for k in DETAIL_FIELDS if o.get(k) not in (None, [], {})}
    return {k: v for k, v in {
        'id': rec.get('id'), 'status': rec.get('status'), 'asset': rec.get('asset'), 'scenario': rec.get('scenario'),
        'part': (rec.get('origin') or {}).get('part'),
        'recommended': rec.get('recommended'), 'explanation': rec.get('explanation') or r.get('explanation'),
        'facts': facts, 'facts_omitted': facts_omitted,
        'facts_detail': '전체 평가 사실(전체 설비/부품 원천 행 포함)은 read_evaluation_evidence에서 field=facts, option=null로 이어 읽습니다.' if facts_omitted else None,
        'rankRule': (r.get('rankRule') or rec.get('rankRule') or {}).get('annotation'),
        'options': options, 'error': rec.get('error'), 'source_errors': source_errors,
        'provenance': _capped(provenance) if detail_option else None,
        'omitted': f"카드마다 {', '.join(DETAIL_FIELDS)} 와 provenance 는 뺐습니다. 한 카드의 전체 근거가 필요하면 같은 인자에 "
                   "detail_option=<카드 id 또는 SOP ID> 를 더하면 현재 상태로 재계산한 상세 미리보기를 받습니다(칸마다 6000자 상한). "
                   "같은 평가의 잘리지 않은 근거는 evidence_ref로 read_evaluation_evidence를 호출하고 next_offset을 따라 읽으세요. 제출한 판단 기록에는 전부 남습니다",
    }.items() if v not in (None, [], {})}


def enveloped(fn):
    """Wrap a tool so the agent always gets the same envelope and never a stack trace."""
    def run(*a, **kw):
        try:
            return ok(fn(*a, **kw))
        except NotRegistered as e:
            return error(e.kind, str(e)[:800])
        except (KeyError, ValueError, TypeError) as e:
            return error("INVALID", f"{type(e).__name__}: {str(e)[:300]}")
        except psycopg.Error as e:
            # Invalid generated SQL can be repaired from the current metadata;
            # unavailable source/timeouts must not become a normal empty result.
            return error('INVALID' if (e.sqlstate or '').startswith('42') else 'UNKNOWN',
                         f"{type(e).__name__}: {str(e)[:300]}")
        except Exception as e:  # noqa: BLE001
            return error("UNKNOWN", f"{type(e).__name__}: {str(e)[:300]}")
    run.__name__, run.__doc__ = fn.__name__, fn.__doc__
    return run


class DmnTools:
    def __init__(self, kg: mcp_kg.KnowledgeGraph | None = None, tsdb: mcp_tsdb.TimeSeriesDB | None = None, fabric: Fabric | None = None):
        self.kg = kg or mcp_kg.KnowledgeGraph()
        self.tsdb = tsdb or mcp_tsdb.TimeSeriesDB()
        self.registry = decidelib.DecisionRegistry("mcp")
        self.prometheus = Prometheus()
        self._fabric = fabric
        from collections import OrderedDict
        from threading import Lock
        self._evidence = OrderedDict()
        self._evidence_lock = Lock()

    def _evaluation_view(self, rec, detail_option=None, *, submitted=False, what='조치 카드 평가'):
        """Short-lived read capabilities preserve the evaluated facts, never execution permission."""
        from copy import deepcopy
        import json
        import secrets
        import time
        from hydcommon.tool_result import checked
        result = agent_view(rec) if submitted else read_outcome(rec, what, detail_option)
        snapshot = {k: rec.get(k) for k in ('id', 'created', 'provenance', 'facts')}
        snapshot['result'] = {'options': [{k: o[k] for k in ('id', 'sopId', *DETAIL_FIELDS) if k in o}
                                           for o in (rec.get('result') or {}).get('options') or []]}
        size = len(json.dumps(snapshot, ensure_ascii=False, default=str).encode())
        if size > 16_000_000:
            raise ValueError('평가 근거가 보관 한도 16MB를 넘었습니다. 조회 범위를 줄이세요')
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._evidence_lock:
            for key, (created, _, _) in list(self._evidence.items()):
                if now - created >= 600:
                    del self._evidence[key]
            while self._evidence and (len(self._evidence) >= 64 or sum(v[2] for v in self._evidence.values()) + size > 16_000_000):
                self._evidence.popitem(last=False)
            self._evidence[token] = (now, deepcopy(snapshot), size)
        result['evidence_ref'] = token
        result['evidence_note'] = '평가 시점의 근거, 최대10분/64건/16MB 보관. 현재 상태의 판단·승인·실행에는 재사용하지 않습니다.'
        return checked(result)

    def read_evaluation_evidence(self, evidence_ref: str, option: str | None, field: str, offset: int = 0):
        """Read one JSON field from the exact snapshot, with explicit continuation.

        The unguessable capability is issued only with its evaluation response;
        knowing a decision ID or another student's option ID is insufficient.
        No registry fallback or re-evaluation occurs on expiry/restart.
        """
        import hashlib
        import json
        import time
        from hydcommon.tool_result import checked
        if type(offset) is not int or offset < 0:
            raise ValueError('offset은 0 이상의 정수여야 합니다')
        if field not in (*DETAIL_FIELDS, 'provenance'):
            raise ValueError('조회 가능한 근거 칸: ' + ', '.join((*DETAIL_FIELDS, 'provenance')))
        with self._evidence_lock:
            entry = self._evidence.get(evidence_ref)
            if entry is None or time.monotonic() - entry[0] >= 600:
                self._evidence.pop(evidence_ref, None)
                raise ValueError('평가 근거 참조가 없거나 만료됐습니다. 새 평가가 필요합니다')
            rec = entry[1]
        if field == 'provenance' or (field == 'facts' and option is None):
            value = rec.get(field, [])
        else:
            matches = [o for o in (rec.get('result') or {}).get('options') or [] if option and option in (o.get('id'), o.get('sopId'))]
            if len(matches) != 1:
                raise ValueError('이 평가에 있는 카드 id를 하나 지정하세요')
            if field not in matches[0]:
                raise ValueError('이 카드에는 요청한 근거 칸이 없습니다')
            value = matches[0][field]
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        if offset > len(serialized):
            raise ValueError('offset이 근거 길이를 넘었습니다')
        end = min(offset + 4000, len(serialized))
        return checked(dict(evaluation_id=rec['id'], evaluated_at=rec.get('created'), field=field,
                            encoding='json', offset=offset, next_offset=end if end < len(serialized) else None,
                            total_chars=len(serialized), sha256=hashlib.sha256(serialized.encode()).hexdigest(),
                            content=serialized[offset:end], snapshot=True))

    # ---- A11 데이터 패브릭: 업무 DB + 시계열 DB 를 한 질문으로 (portal /api/fabric/query 와 같은 함수, 읽기 전용)
    def _graph(self, cypher: str, **params) -> list[dict]:
        from neo4j import unit_of_work

        @unit_of_work(timeout=5.0)
        def read(tx):
            return [r.data() for r in tx.run(cypher, **params)]
        with self.kg.driver.session() as s:
            return s.execute_read(read)

    @property
    def fabric(self) -> Fabric:
        if self._fabric is None:
            self._fabric = Fabric(graph=self._graph)
        return self._fabric

    def fabric_query(self, asset: str, query: str = 'asset', limit: int = 50, sql: dict | None = None) -> dict:
        from hydcommon.tool_result import checked
        return checked(self.fabric.query(asset, query, limit, sql))

    # ---- task:diagnose
    def human_alert(self, asset: str, pattern: str, alert_id: str | None = None) -> dict | None:
        """B7: the person's entered analysis behind a human-input alert, read from the process (server truth, never from the
        caller's arguments). None when no such alert is being handled for this asset and pattern."""
        import urllib.error
        from urllib.parse import urlencode
        q = {"asset": asset, "pattern": pattern, **({"alert_id": alert_id} if alert_id else {})}
        try:
            return decidelib._get_json(f"{decidelib.PROCESS_URL}/api/human-alerts/current?{urlencode(q)}").get("alert")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def diagnose(self, asset: str, pattern: str, alert_id: str | None = None) -> dict:
        """Data trust → T1 cause candidates → evidence SQL → ranked causes → T2 SOP skills → guide card (with citations).
        B7: causes with no sensor Evidence rule (a pattern people enter, such as OIL_ANALYSIS) take the entered analysis of the
        alert being handled as their evidence (card.with_human_evidence)."""
        fresh = mcp_prom.freshness(self.tsdb, asset)
        alert = {"asset": asset, "pattern": pattern}
        if not fresh["ok"]:
            return {"withheld": True, "freshness": fresh, "card": None, "reason": f"데이터 신뢰 불가: {fresh['reason']}"}
        t1 = self.kg.t1_causes(pattern, asset)
        human = {}
        if any(not r.get("evidence") for r in t1):
            t1, human = cardlib.with_human_evidence(t1, self.human_alert(asset, pattern, alert_id))
        evidence = [e for r in t1 for e in (r.get("evidence") or []) if e["id"] not in human]
        results = {**self.tsdb.evaluate(evidence, asset), **human}
        causes = cardlib.rank_causes(t1, results)
        assessment = cardlib.evidence_status(causes)
        if assessment['withheld']:
            return dict(withheld=True, freshness=fresh, top_cause=None, failure_mode=None,
                        card=None, causes=causes, evidence_status=assessment, reason=assessment['reason'])
        t2 = {causes[0]["id"]: self.kg.t2_skills(causes[0]["id"])} if causes else {}
        card = cardlib.build_card(None, alert, causes, t2, fresh)
        return {"withheld": False, "freshness": fresh, "evidence_status": assessment, "top_cause": causes[0]["id"] if causes else None,
                "failure_mode": causes[0].get("failureModeId") if causes else None,
                "causes": [{"id": c["id"], "name": c["name"], "score": c["score"], "prior": c["prior"],
                            "evidence": c["evidence"]} for c in causes],
                "card": card}

    # ---- rules and facts (task:candidates · task:compliance)
    def dmn_rules(self, decision: str | None = None) -> list[dict]:
        rows = self.kg.dmn()
        result = [r for r in rows if decision is None or r["decision"] == decision]
        if decision and not result:
            self._require_knowledge('Decision', [decision])
        return result

    def _require_knowledge(self, label, ids):
        if label not in {'Decision', 'FailureMode', 'Skill'}:
            raise ValueError('지원하지 않는 지식 종류')
        rows = self._graph(f'MATCH (n:{label}) WHERE n.id IN $ids RETURN n.id AS id', ids=ids)
        missing = sorted(set(ids) - {r['id'] for r in rows})
        if missing:
            raise ValueError(f'등록되지 않은 {label} id: ' + ', '.join(missing)[:500])

    def inputs(self) -> list[dict]:
        return self.kg.inputs()

    def timeseries_schema(self):
        return self.tsdb.describe_schema()

    def timeseries_query(self, sql):
        return self.tsdb.query(sql)

    def forecast_actions(self, asset: str, actions: list[dict], horizon_s: float = 900) -> dict:
        """Read current model inputs and forecast supplied actions; no execution."""
        from agentsvc.forecasting import current
        return current(self.kg, asset, actions, horizon_s)

    def gather_facts(self, asset: str, pattern: str, cause: str, failure_mode: str) -> dict:
        known = {"pattern": pattern, "cause": cause, "failure_mode": failure_mode}
        facts, provenance = decidelib.gather_facts(self.kg.inputs(), asset, known, self.tsdb)
        return {"facts": facts, "provenance": provenance}

    # ---- task:rank
    def evaluate_cards(self, asset: str, pattern: str, cause: str, failure_mode: str, overrides: dict | None = None,
                       detail_option: str | None = None) -> dict:
        """Run dec:action-candidates → dec:compliance → dec:rank-actions with forecasts, BSC trade-offs and precedents. No submission.
        The (cause, failure_mode) pair must be one the diagnosis knowledge (T1) lists for this pattern and asset; an
        argument with no diagnosis basis is refused (INVALID) instead of silently filtering candidates by a made-up cause."""
        c, basis = self._diagnosed_cause(asset, pattern, cause, failure_mode)
        rec = decidelib.decide(self.kg, self.registry, self.tsdb, asset, pattern, c,
                                origin={"kind": "mcp", "pattern": pattern, "cause": cause, "failureMode": failure_mode, **basis},
                                overrides=overrides or None, do_submit=False)
        if rec.get('error_code') in ('BUSINESS_CANDIDATES_MISSING', 'BUSINESS_FACTS_MISSING'):
            raise ValueError(rec['error'])
        return self._evaluation_view(rec, detail_option)

    def submit_decision(self, asset: str, pattern: str, cause: str, failure_mode: str, incident: str, alert_id: str | None = None,
                        overrides: dict | None = None, process_scope: dict | None = None) -> dict:
        """Same evaluation, then POST the ranked cards to the process service (the agent's only write). Returns id · status · recommended."""
        if overrides:
            # the same guard decide() applies, raised here before any graph/DB IO: what-if facts never reach a live submission
            raise ValueError('가정 facts는 읽기 전용 evaluate_cards에서만 사용할 수 있습니다')
        c, basis = self._diagnosed_cause(asset, pattern, cause, failure_mode)
        origin = {"kind": "alert", "alertId": alert_id, "incident": incident, "pattern": pattern, "cause": cause, "failureMode": failure_mode,
                  **basis}
        if process_scope is not None:
            origin['process_scope'] = dict(process_scope)
        rec = decidelib.decide(self.kg, self.registry, self.tsdb, asset, pattern, c, origin=origin, overrides=overrides or None, do_submit=True)
        if rec.get('error_code') in ('BUSINESS_CANDIDATES_MISSING', 'BUSINESS_FACTS_MISSING'):
            raise ValueError(rec['error'])
        registered(rec, '조치 카드 판단')
        res = rec.get("result") or {}
        return {"id": rec["id"], "status": rec["status"], "recommended": rec.get("recommended"), "explanation": rec.get("explanation"),
                "cards": [{"rank": o["rank"], "id": o["id"], "sopId": o["sopId"], "name": o["name"], "feasible": o["feasible"], "score": o["score"],
                           "approver": (o.get("approver") or {}).get("name")} for o in res.get("options", [])],
                "error": rec.get("error")}

    def _purchase_part(self, asset: str, part_no: str) -> dict:
        if not isinstance(part_no, str) or not part_no or len(part_no) > 120:
            raise ValueError('실제 ERP 부족부품 번호(part_no)를 명시하세요')
        rows = mcp_ent.fetch('/erp/spare_stock', asset).get('records') or []
        eligible = [r for r in rows if r.get('part_no') == part_no and r.get('below_reorder_point')]
        if len(eligible) != 1:
            raise ValueError('요청한 부품의 재주문점 이탈을 실제 ERP에서 확인할 수 없습니다')
        parts = self._graph('MATCH (p:Part {partNo:$part}) RETURN p.id AS id,p.name AS name,p.partNo AS partNo', part=part_no)
        if len(parts) != 1:
            raise ValueError('ERP 부족부품에 대응하는 Part 지식이 없거나 중복되어 구매 범위를 확정할 수 없습니다')
        return parts[0]

    def purchase_context(self, asset: str, part_no: str) -> dict:
        """Explicit Part-scoped purchase procedures; no inferred Cause/FailureMode."""
        part = self._purchase_part(asset, part_no)
        procedures = self._graph("MATCH (:System {id:'sys:erp'})-[:HAS_SKILL]->(s:Skill {scope:'purchase'})-[:INVOLVES_PART]->(:Part {id:$part}) "
                                 'RETURN s.id AS id,s.sopId AS sopId,s.name AS name,s.executable AS executable,s.source_id AS source_id', part=part['id'])
        return dict(pattern='SPARE_BELOW_MIN', route='purchase-part', part=part, procedures=procedures,
                    basis='실제 ERP 재주문점 이탈 부품 → Part ← INVOLVES_PART ← 원문 구매 Skill ← ERP')

    def _purchase_decision(self, asset, part_no, *, incident=None, alert_id=None, overrides=None, process_scope=None, submit=False,
                           detail_option=None):
        if submit and overrides:
            raise ValueError('가정 구매 facts는 읽기 전용 evaluate_purchase에서만 사용합니다')
        part = self._purchase_part(asset, part_no)
        origin = dict(kind='alert' if submit else 'mcp', pattern='SPARE_BELOW_MIN', cause_route='purchase-part',
                      part=part, cause_basis='실제 ERP 부족부품 → Part ← 원문 구매 Skill',
                      **(dict(incident=incident, alertId=alert_id) if submit else {}))
        if process_scope is not None:
            origin['process_scope'] = dict(process_scope)
        rec = decidelib.decide(self.kg, self.registry, self.tsdb, asset, 'SPARE_BELOW_MIN',
                              dict(id=None, name=None, failureModeId=None, failureMode=None), origin=origin,
                              overrides=overrides, do_submit=submit, purchase_part=part)
        if rec.get('status') == 'FAILED':
            if rec.get('error_code') in BUSINESS_ERRORS:
                raise ValueError(rec['error'])
            raise failure(rec, '원문 구매 후보 계산')
        return self._evaluation_view(registered(rec, '원문 구매 판단') if submit else rec, detail_option,
                                     submitted=submit, what='원문 구매 후보 계산')

    def evaluate_purchase(self, asset: str, part_no: str, overrides: dict | None = None,
                          detail_option: str | None = None) -> dict:
        return self._purchase_decision(asset, part_no, overrides=overrides, detail_option=detail_option)

    def submit_purchase(self, asset: str, part_no: str, incident: str, alert_id: str | None = None,
                        process_scope: dict | None = None) -> dict:
        if not isinstance(incident, str) or not incident.strip():
            raise ValueError('구매 처리 건의 실제 incident id가 필요합니다')
        return self._purchase_decision(asset, part_no, incident=incident, alert_id=alert_id,
                                       process_scope=process_scope, submit=True)

    def business_causes(self, asset: str, pattern: str) -> dict:
        """C2: 업무 경보(SPARE_BELOW_MIN · PM_DUE)의 원인 후보 — 센서 증상이 없으므로 진단(diagnose) 대신 업무 근거로 그래프에서 읽는다.
        재고: ERP 에서 재주문점 아래인 부품 → 그 부품을 쓰는 원인. 정기 정비: 정비가 막는(PREVENTED_BY) 고장의 원인.
        돌려준 cause · failure_mode 를 evaluate_cards · submit_decision 에 그대로 넘긴다(원인 한정 SOP 가 후보에서 빠지지 않게)."""
        if pattern not in BUSINESS_CAUSES:
            raise ValueError(f"{pattern} 은(는) 업무 경보가 아닙니다 — 센서 경보는 diagnose 를 쓰세요")
        parts = []
        if pattern == "SPARE_BELOW_MIN":
            rows = (mcp_ent.fetch("/erp/spare_stock", asset).get("records") or [])
            parts = [r["part_no"] for r in rows if r.get("below_reorder_point")]
        causes = self._graph(BUSINESS_CAUSES[pattern], parts=parts)
        return {"pattern": pattern, "basis": BUSINESS_CAUSE_BASIS[pattern], "parts_below_reorder_point": parts, "causes": causes,
                "top_cause": causes[0]["causeId"] if causes else None, "failure_mode": causes[0]["failureModeId"] if causes else None}

    def precedents(self, failure_mode: str) -> list[dict]:
        rows = self.kg.precedents(failure_mode)
        if not rows:
            self._require_knowledge('FailureMode', [failure_mode])
        return rows

    def tradeoffs(self, skill_ids: list[str]) -> list[dict]:
        from hydcommon.tool_result import checked
        rows = checked(self.kg.tradeoffs(skill_ids))
        missing = set(skill_ids) - {r.get('skill') for r in rows}
        if missing:
            self._require_knowledge('Skill', sorted(missing))
        return rows

    @staticmethod
    def _cause(cause: str, failure_mode: str) -> dict:
        """The shape decide.decide() expects for the top cause. Names are only used in explanation text, so ids suffice here."""
        return {"id": cause, "name": cause, "failureModeId": failure_mode, "failureMode": failure_mode}

    def _diagnosed_cause(self, asset: str, pattern: str, cause: str, failure_mode: str) -> tuple[dict, dict]:
        """A144 (A053 open end): evaluate_cards/submit_decision take the cause as an argument, so nothing used to tie it to a
        diagnosis. The same T1 query diagnose() ranks (pattern → symptom → failure mode ← cause) is the diagnosis basis: the
        pair must appear there, and the real names are carried into the explanation. Anything else is a ValueError
        (→ INVALID envelope): the caller must diagnose first, or fix its arguments.
        Returns (cause, basis): basis = {cause_basis, cause_route} — the query that actually admitted the pair (T1 diagnosis, or the
        business path of a business alarm), recorded in the decision origin."""
        if not isinstance(cause, str) or not cause or not isinstance(failure_mode, str) or not failure_mode:
            raise ValueError("cause와 failure_mode는 비어 있지 않은 노드 id여야 합니다")
        basis = {"cause_basis": CAUSE_BASIS, "cause_route": DIAGNOSIS_ROUTE}
        if pattern in BUSINESS_CAUSES:
            basis = {"cause_basis": BUSINESS_CAUSE_BASIS[pattern], "cause_route": BUSINESS_CAUSE_ROUTE[pattern]}
            # C2: 업무 경보는 업무 근거로 이어진 원인만 받는다(business_causes 와 같은 질의)
            listed = [r for r in self.business_causes(asset, pattern)["causes"] if r.get("causeId") == cause]
            if not listed:
                raise ValueError(f"{cause}는 {pattern}의 업무 근거({BUSINESS_CAUSE_BASIS[pattern]})에 없는 원인입니다. business_causes 결과를 쓰세요")
        else:
            t1 = self.kg.t1_causes(pattern, asset)
            listed = [r for r in t1 if r.get("causeId") == cause]
        if not listed:
            raise ValueError(f"{cause}는 {pattern}의 진단 지식(T1)에 없는 원인입니다. diagnose 결과의 원인 id를 쓰세요")
        match = [r for r in listed if r.get("failureModeId") == failure_mode]
        if not match:
            known = sorted({r.get("failureModeId") for r in listed if r.get("failureModeId")})
            raise ValueError(f"{cause}는 고장 유형 {failure_mode}의 원인이 아닙니다 (진단 지식: {', '.join(known) or '없음'})")
        r = match[0]
        return ({"id": cause, "name": r.get("cause") or cause, "failureModeId": failure_mode, "failureMode": r.get("failureMode") or failure_mode},
                basis)

    def health(self) -> dict:
        return {"neo4j": self.kg.ping(), "llm": llm.available()}
