"""L8 조치 카드 판단 (pure logic): 온톨로지 v2의 DMN 결정표 · 예측 · BSC 상충 · 선례로 조치 가이드 카드(스킬 = SOP)를 고르고 순위를 매긴다.

  1. 후보 선택  dec:action-candidates 규칙(SELECT)의 임계값 검사(TESTS)를 사실에 대어 맞으면 OUTPUTS 스킬이 후보가 된다 (COLLECT).
                원인 한정 스킬(ADDRESSES)은 그 원인일 때만 남긴다.
  2. 규정 판정  dec:compliance 규칙을 후보마다 그 후보의 사실(예측 유온 · 스킬 종류 · 명령 코드 · 공급사 승인)에 대어
                EXCLUDE(제외) · PENALTY(감점) · WARN(경고)을 정한다. APPLIES_TO가 없는 규칙은 모든 후보에 적용된다.
  3. 순위       dec:rank-actions 규칙의 식: BSC 득실 + 예측 유온 여유 − 경고 − 감점 + 선례.
LLM 없이 결정론적이다. 같은 그래프 · 같은 사실이면 같은 카드와 순위가 나온다.
"""
from __future__ import annotations

STRENGTH_NOTE = "강도 high 1 · medium 0.6 · low 0.3 (경로의 곱), 조건부 경로는 절반"
WARN_COST = 0.5
PENALTY_SCALE = 20.0
PRECEDENT_WEIGHT = 1.5
FORECAST_REF, FORECAST_SPAN, FORECAST_CAP = 55.0, 3.0, 2.0


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


def _by_decision(dmn: list[dict]) -> dict[str, list[dict]]:
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


def score_option(o: dict) -> dict:
    value = sum(g["weight"] * (0.5 if g["conditional"] else 1.0) for g in o["gains"]) - \
            sum(l["weight"] * (0.5 if l["conditional"] else 1.0) for l in o["losses"])
    ts1 = next((x["value"] for x in o["forecast"] if x["variable"] == "sv:ts1"), None)
    fc = 0.0 if ts1 is None else max(-FORECAST_CAP, min(FORECAST_CAP, (FORECAST_REF - float(ts1)) / FORECAST_SPAN))
    warn = -WARN_COST * len(o["warnings"])
    pen = -sum(float(p.get("penalty") or 0) for p in o["penalties"]) / PENALTY_SCALE
    prec = PRECEDENT_WEIGHT * (o["precedent"]["share"] if o["precedent"] else 0.0)
    parts = {"bsc": round(value, 2), "forecast": round(fc, 2), "warn": round(warn, 2), "penalty": round(pen, 2), "precedent": round(prec, 2)}
    return {"score": round(sum(parts.values()), 2), "scoreParts": parts}


def evaluate(dmn: list[dict], skills: dict[str, dict], base_facts: dict, forecasts: dict[str, dict], tradeoffs: list[dict],
             precedents: list[dict], suppliers: dict[str, dict]) -> dict:
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

    total_prec = sum(p["n"] for p in precedents) or 0
    prec_by = {p["skill"]: p for p in precedents}
    options = []
    for sid in cand_ids:
        k = skills[sid]
        cf = candidate_facts(base_facts, k, forecasts, suppliers)
        violations, penalties, warnings = [], [], []
        for r in tables.get("dec:compliance", []):
            if r.get("applies") and sid not in r["applies"]:
                continue
            fired, unknown = rule_fires(r, cf)
            trace.append({"decision": "dec:compliance", "rule": r["rule"], "skill": sid, "when": r.get("when"), "fired": fired, "unknown": unknown})
            if not fired:
                continue
            {"EXCLUDE": violations, "PENALTY": penalties, "WARN": warnings}.get(r["effect"], []).append(_cite(r))
        tos = [t for t in tradeoffs if t["skill"] == sid]
        eff = lambda t: {"measure": t["measure"], "name": t["name"], "owner": t.get("owner"), "dir": t["dir"], "weight": round(float(t["weight"]), 2),
                         "conditional": bool(t.get("conditional")), "conds": t.get("conds") or []}
        p = prec_by.get(sid)
        o = {"id": sid, "sopId": k.get("sopId"), "name": k.get("name"), "kind": k.get("kind"), "description": k.get("description"),
             "relation": k.get("relation"), "approver": k.get("approver"), "actions": k.get("actions") or [], "steps": k.get("steps") or [],
             "forecast": [{"variable": v, "name": x["variableName"], "value": x["value"], "unit": x["unit"], "method": x["method"], "id": x["id"]}
                          for v, x in (forecasts.get(sid) or {}).items()],
             "gains": [eff(t) for t in tos if t["good"]], "losses": [eff(t) for t in tos if not t["good"]],
             "violations": violations, "penalties": penalties, "warnings": warnings, "feasible": not violations,
             "selectedBy": selected_by.get(sid, []),
             "precedent": {"n": p["n"], "share": round(p["n"] / total_prec, 2), "reasons": p.get("reasons") or []} if p and total_prec else None,
             "facts": {k2: cf[k2] for k2 in ("forecast_ts1", "forecast_ps1", "skill_kind", "skill_code", "supplier_avl")}}
        o.update(score_option(o))
        options.append(o)
    lvl = lambda o: (o.get("approver") or {}).get("level") or 9
    options.sort(key=lambda o: (not o["feasible"], -o["score"], lvl(o)))
    for i, o in enumerate(options):
        o["rank"] = i + 1
    rec = next((o for o in options if o["feasible"]), None)
    rank_rule = next(iter(tables.get("dec:rank-actions", [])), None)
    return {"options": options, "recommended": rec["id"] if rec else None, "trace": trace,
            "rankRule": _cite(rank_rule) if rank_rule else None, "explanation": explain(options, rec, base_facts)}


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
    return " ".join(parts)
