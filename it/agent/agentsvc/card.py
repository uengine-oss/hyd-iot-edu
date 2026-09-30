"""Guide-card assembly (L8, pure logic): rank causes by prior × evidence, then attach actions/SOP/manual with citations."""
from typing import Any

NO_EVIDENCE_DISCOUNT = 0.3   # a cause with no evidence rule at all keeps only 30 % of its prior


def passes(expect: str, value: Any, threshold: float) -> bool:
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return {"lt": v < threshold, "lte": v <= threshold, "gt": v > threshold, "gte": v >= threshold,
            "eq": v == threshold}.get(expect, False)


def rank_causes(t1_rows: list[dict], results: dict[str, dict]) -> list[dict]:
    """t1_rows: T1 template rows. results: evidence id -> {"value", "passed"}.
    score = prior × (Σ weight of passed evidence / Σ weight)."""
    out = []
    for row in t1_rows:
        evs = []
        wsum = wpass = 0.0
        for e in row.get("evidence") or []:
            r = results.get(e["id"], {})
            w = float(e.get("weight") or 0)
            ok = bool(r.get("passed"))
            wsum += w
            wpass += w if ok else 0.0
            evs.append({"id": e["id"], "name": e.get("name"), "weight": w, "expect": e.get("expect"),
                        "threshold": e.get("threshold"), "value": r.get("value"), "passed": ok})
        prior = float(row.get("prior") or 0)
        score = prior * (wpass / wsum) if wsum > 0 else prior * NO_EVIDENCE_DISCOUNT
        out.append({"id": row["causeId"], "name": row.get("cause"), "description": row.get("description"),
                    "failureModeId": row.get("failureModeId"), "failureMode": row.get("failureMode"),
                    "component": row.get("component"), "symptoms": row.get("symptoms") or [],
                    "prior": prior, "score": round(score, 4), "evidence": evs})
    # evidence-backed causes always rank above causes that have no confirmed evidence
    out.sort(key=lambda c: (any(e["passed"] for e in c["evidence"]), c["score"]), reverse=True)
    return out


def _actions_for(cause_id: str, t2_by_cause: dict[str, list[dict]]) -> list[dict]:
    rows = sorted(t2_by_cause.get(cause_id) or [], key=lambda r: (r.get("priority") or 99, r.get("code") or ""))
    acts = []
    for r in rows:
        steps = sorted([s for s in (r.get("steps") or []) if s.get("id")], key=lambda s: s.get("order") or 0)
        rng = [r["min"], r["max"]] if r.get("min") is not None and r.get("max") is not None else None
        acts.append({"code": r["code"], "actionId": r["actionId"], "name": r.get("name"), "kind": r.get("kind"),
                     "relation": r.get("relation"), "description": r.get("description"),
                     "param": r.get("param"), "value": r.get("default"), "paramRange": rng,
                     "actuatorId": r.get("actuatorId"), "resource": r.get("resource"),
                     "constraints": r.get("constraints") or [],
                     "sop": {"id": (r.get("procedure") or {}).get("id"), "name": (r.get("procedure") or {}).get("name"),
                             "steps": [{"id": s["id"], "order": s.get("order"), "text": s.get("text"),
                                        "manual": s.get("manual")} for s in steps]}})
    return acts


def _citations(causes: list[dict], actions: list[dict]) -> list[str]:
    ids: list[str] = []
    for c in causes:
        ids += [c["id"], c.get("failureModeId")] + [e["id"] for e in c["evidence"]]
    for a in actions:
        ids += [a["actionId"], a["sop"].get("id"), a.get("actuatorId")] + [k.get("id") for k in a["constraints"]]
        for s in a["sop"]["steps"]:
            ids.append(s["id"])
            if s.get("manual"):
                ids.append(s["manual"].get("ref") or s["manual"].get("id"))
    seen, out = set(), []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def template_summary(alert: dict, causes: list[dict], actions: list[dict]) -> str:
    top = causes[0] if causes else None
    cmds = [a for a in actions if a["kind"] == "command"]
    wos = [a for a in actions if a["kind"] == "work_order"]
    parts = [f"{alert.get('asset')}에서 {alert.get('pattern')} 경보가 발생했습니다"
             + (f" (TS1 {alert['evidence'].get('ts1')} ℃, CE {alert['evidence'].get('ce')} %)." if alert.get("evidence") else ".")]
    if top:
        passed = [e["name"] for e in top["evidence"] if e["passed"]]
        parts.append(f"가장 유력한 원인은 '{top['name']}'(점수 {top['score']:.2f})이며 근거는 {', '.join(passed) if passed else '없음'}입니다.")
    if cmds:
        parts.append("권장 즉시 조치: " + ", ".join(f"{a['name']}({a['param']}={a['value']})" for a in cmds)
                     + (f"; 완화 후 {wos[0]['name']}를 발행합니다." if wos else "."))
    return " ".join(parts)


def build_card(incident_id: str, alert: dict, causes: list[dict], t2_by_cause: dict[str, list[dict]],
               freshness: dict, summary: str | None = None) -> dict:
    top = causes[0]["id"] if causes else None
    actions = _actions_for(top, t2_by_cause) if top else []
    card = {"incident": incident_id, "alert": alert, "freshness": freshness,
            "causes": causes, "topCause": top, "recommended": actions,
            "citations": _citations(causes, actions),
            "summary": summary or template_summary(alert, causes, actions)}
    return card
