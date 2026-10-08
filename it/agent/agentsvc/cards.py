"""L8 조치 카드 판단 (pure logic): 온톨로지 v2의 DMN 결정표 · 예측 · BSC 상충 · 선례로 조치 가이드 카드(스킬 = SOP)를 고르고 순위를 매긴다.

  1. 후보 선택  dec:action-candidates 규칙(SELECT)의 임계값 검사(TESTS)를 사실에 대어 맞으면 OUTPUTS 스킬이 후보가 된다 (COLLECT).
                원인 한정 스킬(ADDRESSES)은 그 원인일 때만 남긴다.
  2. 규정 판정  dec:compliance 규칙을 후보마다 그 후보의 사실(예측 유온 · 스킬 종류 · 명령 코드 · 공급사 승인)에 대어
                EXCLUDE(제외) · PENALTY(감점) · WARN(경고)을 정한다. APPLIES_TO가 없는 규칙은 모든 후보에 적용된다.
  3. 순위       dec:rank-actions 규칙의 `rankingPolicy`(검토된 명시 식, A069)로 계산한다. 기본 정책은 BSC 득실 + 예측 유온 여유
                − 경고 − 감점 + 선례 + 납기 긴급도 × 생산 영향 − 품질 클레임 위험이며(회의 2026-10-01 L385~404), 납기·품질·계약·재고 같은
                업무 조건은 이 코드가 아니라 정책 데이터(입력 별칭 + 식)가 담는다 — 새 조건은 DDL 인제스천 + 정책 변경만으로 늘어난다(A078).
LLM 없이 결정론적이다. 같은 그래프 · 같은 사실이면 같은 카드와 순위가 나온다.
"""
from __future__ import annotations
import hashlib
import json
from hydcommon import ranking, bsc

STRENGTH_NOTE = "강도 high 1 · medium 0.6 · low 0.3 (경로의 곱), 조건부 경로는 절반"
WARN_COST = 0.5
PENALTY_SCALE = 20.0
PRECEDENT_WEIGHT = 1.5
FORECAST_REF, FORECAST_SPAN, FORECAST_CAP = 55.0, 3.0, 2.0
STOP_MEASURES, REDUCE_MEASURES = {"msr:availability"}, {"msr:throughput", "msr:tp"}
LOAD_DESIGN = 90.0                                                      # 정상 운전 부하 (thermal.py 설계점): 이보다 낮게 설정하면 감산


def _num(v):
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def test_ok(test: dict, facts: dict) -> bool | None:
    """One DMN input entry. None = the fact is unknown (the rule cannot fire)."""
    var, op, want = test.get("variable"), test.get("operator"), test.get("value")
    if var not in facts or facts[var] is None:
        return None
    have = facts[var]
    if isinstance(have, (list, tuple, set)):                       # e.g. skill_code: any command code of the skill
        hit = want in have
        return hit if op == "==" else (not hit) if op == "!=" else None
    if isinstance(want, bool) or isinstance(have, bool):
        return (bool(have) == bool(want)) if op == "==" else (bool(have) != bool(want)) if op == "!=" else None
    a, b = _num(have), _num(want)
    if a is not None and b is not None:
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b, "!=": a != b}.get(op)
    return (str(have) == str(want)) if op == "==" else (str(have) != str(want)) if op == "!=" else None


def rule_fires(rule: dict, facts: dict) -> tuple[bool, list[str]]:
    """A decision-table row fires when every test is true (AND). Returns (fired, unknown variables)."""
    unknown, ok = [], True
    for t in rule.get("tests") or []:
        r = test_ok(t, facts)
        if r is None:
            unknown.append(t.get("variable"))
            ok = False
        elif not r:
            ok = False
    return ok and bool(rule.get("tests")), unknown


# A115 (r14 A11, DMN hit policy): how this code evaluates each table it executes. The graph declares the policy on the
# DecisionTable (instances.cypher); a declaration that differs from the evaluation is refused instead of silently ignored.
# dt:diagnose-cause is not evaluated here: the cause ranking is prior x evidence weight (card.rank_causes).
EXECUTED_HIT_POLICIES = {"dec:action-candidates": "COLLECT", "dec:compliance": "COLLECT", "dec:rank-actions": "UNIQUE"}


def check_hit_policy(rows: list[dict]) -> None:
    for r in rows:
        expected = EXECUTED_HIT_POLICIES.get(r.get("decision"))
        if expected and r.get("hitPolicy") is not None and r["hitPolicy"] != expected:
            raise ValueError(f"{r['decision']} 결정표의 hitPolicy {r['hitPolicy']}는 이 엔진의 평가 방식({expected})과 다릅니다")


def _by_decision(dmn: list[dict]) -> dict[str, list[dict]]:
    check_hit_policy(dmn)
    out: dict[str, list[dict]] = {}
    for r in sorted(dmn, key=lambda r: (r["decision"], r.get("ord") or 0)):
        out.setdefault(r["decision"], []).append(r)
    return out


def _cite(rule: dict) -> dict:
    return {"rule": rule["rule"], "effect": rule["effect"], "when": rule.get("when"), "annotation": rule.get("annotation"),
            "penalty": rule.get("penalty"), "measure": (rule.get("penalizes") or [None])[0], "sources": rule.get("sources") or []}


def candidate_facts(base: dict, skill: dict, forecasts: dict, suppliers: dict) -> dict:
    f = dict(base)
    fc = forecasts.get(skill["skillId"]) or {}
    f["forecast_ts1"] = fc["sv:ts1"]["value"] if fc.get("sv:ts1") else None      # DMN 온도 규칙
    f["forecast_ps1"] = fc["sv:ps1"]["value"] if fc.get("sv:ps1") else None      # DMN 압력 규칙
    f["skill_kind"] = skill.get("kind")
    f["skill_code"] = [a["code"] for a in skill.get("actions") or [] if a.get("code")]
    sup = next((a.get("value") for a in skill.get("actions") or [] if a.get("code") == "PR_CREATE"), None)
    f["supplier_avl"] = suppliers.get(sup, {}).get("avl") if sup else None
    return f


def production_effect(o: dict) -> str:
    """What the card does to production, read from its PLC commands: a STOP command = stop, a load set-point under the
    design load = reduce, any other command = keep. A card without commands (work order only) falls back to its BSC losses
    (availability loss = stop, throughput loss = reduce). Live check 2026-10-04: judging every card by BSC losses marked all
    three cooler cards 'stop' because each lists 생산량·가동률 ↓ in its trade-offs."""
    commands = {a.get("code"): a.get("value") for a in o.get("actions") or [] if a.get("code") and a.get("kind", "command") == "command"}
    if commands:
        if "STOP" in commands:
            return "stop"
        load = _num(commands.get("LOAD_SET"))
        if load is not None and load < LOAD_DESIGN:
            return "reduce"
        return "keep"
    measures = {l.get("measure") for l in o.get("losses") or []}
    if measures & STOP_MEASURES:
        return "stop"
    if measures & REDUCE_MEASURES:
        return "reduce"
    return "keep"


def score_option(o: dict, facts: dict, policy: dict) -> dict:
    facts = facts or {}
    ts1 = next((x["value"] for x in o["forecast"] if x["variable"] == "sv:ts1"), None)
    features = {'bsc_gain':sum(x['weight'] for x in o['gains'] if not x['conditional']),
        'bsc_conditional_gain':sum(x['weight'] for x in o['gains'] if x['conditional']),
        'bsc_loss':sum(x['weight'] for x in o['losses'] if not x['conditional']),
        'bsc_conditional_loss':sum(x['weight'] for x in o['losses'] if x['conditional']),
        'forecast_ts1':ts1, 'warning_count':len(o['warnings']),
        'penalty_total':sum(ranking.number(p.get('penalty') or 0) for p in o['penalties']),
        'precedent_share':o['precedent']['share'] if o['precedent'] else 0,
        'production':o.get('production') or production_effect(o)}
    return ranking.score(policy, features, facts)


def rank_policy(rules, facts):
    check_hit_policy(rules)
    matches = []
    for rule in rules:
        if rule['effect'] != 'RANK':
            raise ValueError('ranking table contains a non-RANK rule')
        fired, unknown = rule_fires(rule, facts) if rule.get('tests') else (True, [])
        if unknown and not any(test_ok(t, facts) is False for t in rule['tests']):
            raise ValueError('ranking rule input is unknown: ' + ', '.join(unknown))
        if fired:
            matches.append(rule)
    if len(matches) != 1:
        # UNIQUE (EXECUTED_HIT_POLICIES): two applicable ranking policies are a table error, not a choice
        raise ValueError('exactly one applicable executable ranking rule is required')
    return matches[0], ranking.validate(matches[0].get('rankingPolicy'))


def ranking_variables(rules):
    return {variable for rule in rules if rule['decision']=='dec:rank-actions'
            for variable in ranking.validate(rule.get('rankingPolicy'))['inputs'].values()}


def policy_digest(dmn, skill):
    sid = skill['skillId']
    applicable = [r for r in dmn if r['decision'] == 'dec:rank-actions'
        or (r['decision'] == 'dec:action-candidates' and sid in (r.get('outputs') or []))
        or (r['decision'] == 'dec:compliance' and (not r.get('applies') or sid in r['applies']))]
    return hashlib.sha256(json.dumps({'skill':skill, 'rules':applicable},
        ensure_ascii=False,sort_keys=True,separators=(',', ':')).encode()).hexdigest()


def evaluate(dmn: list[dict], skills: dict[str, dict], base_facts: dict, forecasts: dict[str, dict], tradeoffs: list[dict],
             precedents: list[dict], suppliers: dict[str, dict], forecast_contexts: dict | None = None) -> dict:
    """dmn: t3_dmn rows. skills: id -> t2/t3 skill row. forecasts: skill -> {variable -> row}. tradeoffs: t3_tradeoffs rows.
    precedents: t3_precedents rows. suppliers: id -> {avl}. Returns options ranked + recommendation + rule trace."""
    tables = _by_decision(dmn)
    trace = []
    cand_ids: list[str] = []
    selected_by: dict[str, list[dict]] = {}
    for r in tables.get("dec:action-candidates", []):
        fired, unknown = rule_fires(r, base_facts)
        trace.append({"decision": "dec:action-candidates", "rule": r["rule"], "when": r.get("when"), "fired": fired, "unknown": unknown})
        if fired and r["effect"] == "SELECT":
            for sid in r.get("outputs") or []:
                if sid not in cand_ids:
                    cand_ids.append(sid)
                selected_by.setdefault(sid, []).append(_cite(r))
    cause = base_facts.get("cause")
    cand_ids = [s for s in cand_ids if s in skills and (not skills[s].get("addresses") or cause in skills[s]["addresses"])]

    # precedents = t3_precedents 행 — 교육용 고정(DECISIONS 110 ④): 그 템플릿이 시드 선례(seeded=true)만 센다. 점수식은 그대로.
    total_prec = sum(p["n"] for p in precedents) or 0
    prec_by = {p["skill"]: p for p in precedents}
    options = []
    for sid in cand_ids:
        k = skills[sid]
        cf = candidate_facts(base_facts, k, forecasts, suppliers)
        violations, penalties, warnings = [], [], []
        forecast_context = (forecast_contexts or {}).get(sid)
        if forecast_contexts is not None:
            if not forecast_context or forecast_context.get('error'):
                violations.append({'rule':'forecast:model-unavailable', 'effect':'EXCLUDE',
                    'annotation':'현재 조치 예측을 확인할 수 없습니다: ' + str((forecast_context or {}).get('error', 'missing forecast')),
                    'sources':['forecast:model-binding']})
            elif forecast_context.get('predicted_interlocks'):
                violations.append({'rule':'forecast:predicted-interlock', 'effect':'EXCLUDE',
                    'annotation':'예측 구간의 PLC 인터록: ' + ', '.join(forecast_context['predicted_interlocks']),
                    'sources':[forecast_context['model_id']]})
        for r in tables.get("dec:compliance", []):
            if r.get("applies") and sid not in r["applies"]:
                continue
            fired, unknown = rule_fires(r, cf)
            trace.append({"decision": "dec:compliance", "rule": r["rule"], "skill": sid, "when": r.get("when"), "fired": fired, "unknown": unknown})
            if not fired:
                # Missing evidence is not a satisfied rule. WARN remains advisory,
                # but the human must see its uncertainty before choosing a card.
                # A known-false AND term makes the remaining unknown irrelevant.
                if unknown and not any(test_ok(t, cf) is False for t in r.get('tests') or []):
                    pending = dict(_cite(r), unknown=unknown,
                                   annotation='확인되지 않은 조건 (' + ', '.join(unknown) + '): ' + (r.get('annotation') or r['rule']))
                    (warnings if r['effect'] == 'WARN' else violations).append(pending)
                continue
            {"EXCLUDE": violations, "PENALTY": penalties, "WARN": warnings}.get(r["effect"], []).append(_cite(r))
        tos = [t for t in tradeoffs if t["skill"] == sid]
        effects, paths = bsc.evaluate_paths(tos, base_facts, forecasts.get(sid) or {})
        p = prec_by.get(sid)
        o = {"id": sid, "sopId": k.get("sopId"), "name": k.get("name"), "kind": k.get("kind"), "description": k.get("description"),
             "relation": k.get("relation"), "approver": k.get("approver"), "actions": k.get("actions") or [], "steps": k.get("steps") or [],
             "forecast": [{"variable": v, "name": x["variableName"], "value": x["value"], "unit": x["unit"], "method": x["method"], "id": x["id"]}
                          for v, x in (forecasts.get(sid) or {}).items()],
             "gains": [t for t in effects if t["good"]], "losses": [t for t in effects if not t["good"]],
             "tradeoffEvaluation":paths,
             "violations": violations, "penalties": penalties, "warnings": warnings, "feasible": not violations,
             "selectedBy": selected_by.get(sid, []),
             "precedent": {"n": p["n"], "share": round(p["n"] / total_prec, 2), "reasons": p.get("reasons") or []} if p and total_prec else None,
             "facts": {k2: cf[k2] for k2 in ("forecast_ts1", "forecast_ps1", "skill_kind", "skill_code", "supplier_avl")}}
        o["production"] = production_effect(o)
        if forecast_contexts is not None:
            o['forecastContext'] = forecast_context
        o['policy_sha256'] = policy_digest(dmn, k)
        rank_rule, policy = rank_policy(tables.get('dec:rank-actions', []), cf)
        o['rankingEvidence'] = {'rule':rank_rule['rule'], 'policy':policy, 'policy_sha256':ranking.fingerprint(policy),
            'gains':o['gains'], 'losses':o['losses'],
            'paths':bsc.consent_paths(paths),
            'conditionMode':'명시 조건 TRUE만 확정 반영; FALSE 제외; UNKNOWN의 추가 가능 영향은 순위 정책에 따른 추정'}
        o.update(score_option(o, base_facts, policy))
        options.append(o)
    lvl = lambda o: (o.get("approver") or {}).get("level") or 9
    options.sort(key=lambda o: (not o["feasible"], -o["score"], lvl(o)))
    for i, o in enumerate(options):
        o["rank"] = i + 1
    rec = next((o for o in options if o["feasible"]), None)
    rank_rule = next((r for r in tables.get('dec:rank-actions', []) if rec and r['rule']==rec['rankingEvidence']['rule']), None)
    if rank_rule is None and options:
        rank_rule = next((r for r in tables.get('dec:rank-actions', []) if r['rule']==options[0]['rankingEvidence']['rule']), None)
    return {"options": options, "recommended": rec["id"] if rec else None, "trace": trace,
            "rankRule": dict(_cite(rank_rule), rankingPolicy=ranking.validate(rank_rule['rankingPolicy'])) if rank_rule else None,
            "explanation": explain(options, rec, base_facts)}


def _names(xs: list[dict], n: int = 3) -> str:
    return ", ".join(f"{x['name']} {'↑' if x['dir'] == 1 else '↓'}" + (f" [{x['owner']}]" if x.get("owner") else "") for x in xs[:n])


def explain(options: list[dict], rec: dict | None, facts: dict) -> str:
    if not options:
        return "이 고장 유형에 맞는 조치 후보가 없다 (후보 선택 규칙이 맞지 않음)."
    head = f"{facts.get('failure_mode_name') or facts.get('failure_mode')} — 후보 {len(options)}장"
    if not rec:
        return head + " 모두 규정상 제외됐다: " + "; ".join(f"{o['sopId']} {o['name']} ({o['violations'][0]['annotation']})" for o in options)
    fc = next((x for x in rec["forecast"] if x["variable"] == "sv:ts1"), None)
    parts = [f"{head} 중 '{rec['sopId']} {rec['name']}'을(를) 권한다 (점수 {rec['score']})."]
    if fc:
        parts.append(f"예측 유온 {fc['value']} {fc['unit']}.")
    if rec["gains"]:
        parts.append("득: " + _names(sorted(rec["gains"], key=lambda g: -g["weight"])) + ".")
    if rec["losses"]:
        parts.append("실: " + _names(sorted(rec["losses"], key=lambda g: -g["weight"])) + ".")
    out = [o for o in options if not o["feasible"]]
    if out:
        parts.append("제외: " + "; ".join(f"'{o['name']}' — {o['violations'][0]['annotation']}" for o in out) + ".")
    if rec["precedent"]:
        parts.append(f"같은 고장 유형에서 사람이 이 안을 고른 선례 {rec['precedent']['n']}건 ({int(rec['precedent']['share'] * 100)} %).")
    delivery = rec['scoreParts'].get('delivery', 0)
    if delivery:
        tier = f"{facts['order_customer_tier']} " if facts.get("order_customer_tier") else ""
        parts.append(f"납기: {tier}오더 납기까지 {facts.get('order_due_h')} h, 지연 시 {facts.get('order_penalty_per_h')}만원/h — "
                     f"생산을 {'유지' if rec.get('production') == 'keep' else '감산' if rec.get('production') == 'reduce' else '정지'}하는 카드"
                     f"의 실행 순위 식 결과 {delivery:+g}점.")
    risky = [o for o in options if (o["scoreParts"].get("quality") or 0) < 0]
    if risky:
        parts.append(f"품질: 출하 대기 로트 {facts.get('hot_lot_qty')}개(클레임 {facts.get('hot_lot_claim')}만원) — 실행 순위 식에 따라 "
                     + ", ".join(f"'{o['name']}'" for o in risky) + " 감산.")
    return " ".join(parts)
