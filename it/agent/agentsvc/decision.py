"""L8 enterprise decision engine (pure, no IO) — "ontology as a knowledge map for trade-off decisions".

The ontology (L7) supplies, for one decision scenario:
  options   : alternatives, each a bundle of agent Skills with parameters (o_*),
  impacts   : Option -IMPACTS{expr}-> KPI   — a formula in 만원 (KRW 10k) over facts and option parameters,
  kpis      : KPI -OWNED_BY-> Department, KPI -CONTRIBUTES_TO{weight}-> Goal (the enterprise view),
  policies  : Policy -GOVERNS-> Skill, HARD (option excluded) or SOFT (penalty charged to a KPI).
Enterprise systems (ERP/MES/CMMS/QMS/SCM/EMS, reached through InfoType nodes) supply the facts (prefix_name).

The engine scores every option from each department's point of view (only the KPIs it owns) and from the
enterprise point of view (all KPIs, goal-weighted), removes HARD violations, and explains why the enterprise
optimum differs from a department optimum. No LLM is involved; the same inputs always give the same answer.
"""
from __future__ import annotations

import ast
import operator

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Mod: operator.mod}
_CMP = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}
_FUNCS = {"min": min, "max": max, "abs": abs, "round": round}


def safe_eval(expr: str, variables: dict):
    """Evaluate a formula stored in the ontology. Only numbers, names, + - * / %, comparisons, and/or/not,
    `a if c else b` and min/max/abs/round are allowed; anything else raises ValueError. Unknown names raise KeyError."""
    try:
        tree = ast.parse(str(expr), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"bad formula {expr!r}: {e.msg}") from None

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, bool, str)):
            return n.value
        if isinstance(n, ast.Name):
            if n.id not in variables:
                raise KeyError(n.id)
            return variables[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            return _BIN[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            return not ev(n.operand)
        if isinstance(n, ast.BoolOp):
            vals = [ev(v) for v in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if isinstance(n, ast.Compare):
            left = ev(n.left)
            for op, right in zip(n.ops, n.comparators):
                if type(op) not in _CMP:
                    raise ValueError(f"operator not allowed in {expr!r}")
                r = ev(right)
                if not _CMP[type(op)](left, r):
                    return False
                left = r
            return True
        if isinstance(n, ast.IfExp):
            return ev(n.body) if ev(n.test) else ev(n.orelse)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
            return _FUNCS[n.func.id](*[ev(a) for a in n.args])
        raise ValueError(f"not allowed in formula {expr!r}: {type(n).__name__}")

    return ev(tree)


def _num(x) -> float:
    return round(float(x), 2)


def evaluate(ctx: dict, facts: dict) -> dict:
    kpis = {k["id"]: k for k in ctx.get("kpis", [])}
    all_skills = {s["id"] for o in ctx.get("options", []) for s in o.get("skills", [])}
    used = {i["kpi"] for o in ctx.get("options", []) for i in o.get("impacts", [])} | ({"kpi:precedent"} if ctx.get("precedents") else set()) | {
        p.get("kpi") for p in ctx.get("policies", []) if p.get("kpi") and (p.get("scope") == "scenario" or set(p.get("skills", [])) & all_skills)}
    depts = sorted({k["owner"] for k in kpis.values() if k.get("owner") and k["id"] in used})   # only departments this scenario touches
    dept_name = {k["owner"]: k.get("ownerName", k["owner"]) for k in kpis.values() if k.get("owner")}
    policies = ctx.get("policies", [])
    errors: list[str] = []
    out = []
    for o in ctx.get("options", []):
        vars_ = dict(facts) | {f"o_{k}": v for k, v in (o.get("params") or {}).items()}
        skill_ids = {s["id"] for s in o.get("skills", [])}
        res = {"id": o["id"], "name": o["name"], "description": o.get("description", ""), "params": o.get("params") or {},
               "skills": o.get("skills", []), "approver": o.get("approver"), "impacts": {}, "notes": {},
               "violations": [], "softPenalties": [], "feasible": True, "errors": []}
        for imp in o.get("impacts", []):
            try:
                res["impacts"][imp["kpi"]] = _num(safe_eval(imp["expr"], vars_))
                if imp.get("note"):
                    res["notes"][imp["kpi"]] = imp["note"]
            except KeyError as e:
                res["errors"].append(f"{o['id']}: 사실 '{e.args[0]}' 없음 ({imp['kpi']})")
            except (ValueError, ZeroDivisionError, TypeError) as e:
                res["errors"].append(f"{o['id']}: {imp['kpi']} 식 오류 {e}")
        for p in policies:
            if p.get("scope") != "scenario" and not (set(p.get("skills", [])) & skill_ids):
                continue
            try:
                violated = bool(safe_eval(p["expr"], vars_))
            except KeyError as e:
                res["errors"].append(f"{o['id']}: 규정 {p['id']} 판단에 필요한 '{e.args[0]}' 없음")
                continue
            if not violated:
                continue
            v = {"policy": p["id"], "name": p["name"], "kind": p.get("kind", "HARD"), "source": p.get("source", "")}
            if v["kind"] == "HARD":
                res["violations"].append(v)
            else:
                pen = _num(safe_eval(p.get("penalty", "0"), vars_))
                v["penalty"] = pen
                res["softPenalties"].append(v)
                kpi = p.get("kpi")
                if kpi:
                    res["impacts"][kpi] = _num(res["impacts"].get(kpi, 0) + pen)
        # HITL feedback: what people chose before in this scenario becomes a (bounded) KPI of its own
        prec = ctx.get("precedents") or {}
        total_prec = sum(int(v.get("n", 0)) for v in prec.values())
        if total_prec and "kpi:precedent" in kpis:
            mine = prec.get(o["id"], {})
            share = round(int(mine.get("n", 0)) / total_prec, 4)
            res["impacts"]["kpi:precedent"] = _num(float(kpis["kpi:precedent"].get("value_per_share") or 60) * share)
            res["notes"]["kpi:precedent"] = f"과거 같은 판단 {total_prec}건 중 {mine.get('n', 0)}건이 이 안을 승인"
            res["precedent"] = {"n": int(mine.get("n", 0)), "share": share, "reasons": list(mine.get("reasons") or [])[:3]}
        if res["errors"]:
            res["feasible"] = False
            errors.extend(res["errors"])
        if res["violations"]:
            res["feasible"] = False
        res["perspectives"] = {d: _num(sum(v for k, v in res["impacts"].items() if kpis.get(k, {}).get("owner") == d)) for d in depts}
        res["total"] = _num(sum(v * float(kpis.get(k, {}).get("weight", 1.0)) for k, v in res["impacts"].items()))
        res["perspectives"]["enterprise"] = res["total"]
        out.append(res)

    def best(key, pool):
        pool = [o for o in pool if not o["errors"]]
        # ties inside one department's view are broken by the enterprise total (the least harmful to everyone else)
        return max(pool, key=lambda o: (o["perspectives"].get(key, 0), o["total"]))["id"] if pool else None

    feasible = [o for o in out if o["feasible"]]
    winners = {k: best(k, feasible) for k in depts + ["enterprise"]}
    naive = {k: best(k, out) for k in depts + ["enterprise"]}
    ranked = sorted(feasible, key=lambda o: o["total"], reverse=True)
    rec = ranked[0] if ranked else None
    runner = ranked[1] if len(ranked) > 1 else None
    drivers = []
    if rec and runner:
        for k in set(rec["impacts"]) | set(runner["impacts"]):
            d = _num(rec["impacts"].get(k, 0) - runner["impacts"].get(k, 0))
            if d:
                drivers.append({"kpi": k, "name": kpis.get(k, {}).get("name", k), "delta": d})
        drivers.sort(key=lambda d: d["delta"], reverse=True)
    for o in out:
        o["rank"] = next((i + 1 for i, r in enumerate(ranked) if r["id"] == o["id"]), None)
    return {"scenario": ctx.get("scenario"), "options": out, "winners": winners, "naiveWinners": naive,
            "departments": [{"id": d, "name": dept_name[d]} for d in depts],
            "recommended": rec["id"] if rec else None, "runnerUp": runner["id"] if runner else None,
            "approver": rec.get("approver") if rec else None, "drivers": drivers, "errors": errors,
            "explanation": explain(out, rec, runner, winners, naive, dept_name, drivers)}


def _score(out, oid, key):
    return next(o["perspectives"].get(key, 0) for o in out if o["id"] == oid)


def explain(out, rec, runner, winners, naive, dept_name, drivers) -> str:
    if not rec:
        return "실행 가능한 대안이 없습니다. 규정 위반이나 데이터 부족으로 모든 대안이 제외됐습니다. 사람의 판단이 필요합니다."
    name = {o["id"]: o["name"] for o in out}
    parts = [f"전사 관점 권고는 '{rec['name']}'입니다 (전사 합계 {rec['total']:+,.0f}만원)."]
    if rec.get("precedent"):
        p = rec["precedent"]
        parts.append(f"현장 판단 선례: 지난 같은 판단에서 {p['n']}건({p['share'] * 100:.0f} %)이 이 안을 골랐고, 그만큼 점수에 반영했습니다.")
    if runner:
        top = drivers[0] if drivers else None
        why = f" 가장 큰 차이는 {top['name']} {top['delta']:+,.0f}만원입니다." if top else ""
        parts.append(f"차선 '{runner['name']}'보다 {rec['total'] - runner['total']:+,.0f}만원 유리합니다.{why}")
    for d, w in winners.items():
        if d == "enterprise" or not w or w == rec["id"]:
            continue
        parts.append(f"{dept_name.get(d, d)} 관점만 보면 '{name[w]}'가 1위지만, 다른 부서 KPI 손실까지 합치면 전사 이익이 줄어듭니다.")
    for d, w in naive.items():
        if d == "enterprise" or not w or w == winners.get(d):
            continue
        if winners.get(d) and _score(out, w, d) <= _score(out, winners[d], d):
            continue                                   # not actually better for this department, only a tie
        o = next(x for x in out if x["id"] == w)
        if o["violations"]:
            parts.append(f"{dept_name.get(d, d)}에 가장 유리한 '{name[w]}'는 규정 '{o['violations'][0]['name']}' 위반으로 처음부터 제외됐습니다.")
    return " ".join(parts)


def build_context(scn_row: dict, option_rows: list[dict], kpi_rows: list[dict], policy_rows: list[dict], precedents: dict | None = None) -> dict:
    """Turn the T3 template results into the engine's input."""
    import json
    options = []
    for o in option_rows:
        params = o.get("params") or {}
        if isinstance(params, str):
            params = json.loads(params or "{}")
        options.append({**o, "params": params, "skills": o.get("skills") or [], "impacts": o.get("impacts") or []})
    policies = [{**p, "scope": "scenario" if p.get("scenarioScope") else "skill", "skills": p.get("skills") or []} for p in policy_rows]
    return {"scenario": scn_row.get("scenario"), "infos": [i for i in scn_row.get("infos") or [] if i],
            "triggers": [t for t in scn_row.get("triggers") or [] if t], "options": options, "kpis": kpi_rows, "policies": policies,
            "precedents": precedents or {}}


def assemble_facts(infos: list[dict], responses: dict, asset: str) -> tuple[dict, list[dict]]:
    """responses: {info_id: {"system", "facts", "records"}} fetched from the endpoints the ontology named.
    Facts are namespaced with the InfoType prefix from the ontology, so a formula says where its number came from."""
    facts: dict = {}
    prov = []
    for i in infos:
        resp = responses.get(i["id"])
        if not resp:
            prov.append({"info": i["id"], "name": i.get("name"), "system": i.get("system"), "systemName": i.get("systemName"),
                         "endpoint": str(i.get("endpoint", "")).replace("{asset}", asset), "error": "no response", "facts": {}, "records": []})
            continue
        f = {f"{i['prefix']}_{k}": v for k, v in (resp.get("facts") or {}).items()}
        facts |= f
        prov.append({"info": i["id"], "name": i.get("name"), "system": i.get("system"), "systemName": i.get("systemName"),
                     "endpoint": str(i.get("endpoint", "")).replace("{asset}", asset), "facts": f, "records": resp.get("records", [])})
    return facts, prov
