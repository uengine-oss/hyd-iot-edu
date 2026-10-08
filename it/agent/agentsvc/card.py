"""Guide-card assembly (L8, pure logic): rank causes by prior × evidence, then attach actions/SOP/manual with citations."""
from typing import Any
import math

NO_EVIDENCE_DISCOUNT = 0.3   # a cause with no evidence rule at all keeps only 30 % of its prior


def passes(expect: str, value: Any, threshold: float) -> bool:
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(v) or not math.isfinite(threshold):
        return False
    return {"lt": v < threshold, "lte": v <= threshold, "gt": v > threshold, "gte": v >= threshold,
            "eq": v == threshold}.get(expect, False)


HUMAN_SOURCE = "human_input"
HUMAN_FIELDS = ("source", "enteredBy", "item", "measured", "unit", "memo", "t")


def human_evidence(alert: dict | None) -> dict | None:
    """B7: a person's entered analysis (process `human_alert` — e.g. an oil analysis out of spec) is the observation behind a
    human-input alert. It plays the role a sensor Evidence SQL plays for a detector alert: one PASS evidence row, cited by
    its alert id, carrying who entered it. Anything else (a detector alert, an in-spec reading) gives None."""
    if not isinstance(alert, dict) or alert.get("source") != HUMAN_SOURCE or not alert.get("alertId"):
        return None
    ev = alert.get("evidence") if isinstance(alert.get("evidence"), dict) else {}
    if ev.get("out_of_spec") is not True:
        return None
    by = alert.get("enteredBy") if isinstance(alert.get("enteredBy"), dict) else {}
    who = by.get("name") or by.get("id") or "입력자 미상"
    return {"id": f"human:{alert['alertId']}", "name": f"사람 입력 분석 결과: {ev.get('item_name') or ev.get('item')} 기준 이탈 ({who})",
            "weight": 1.0, "expect": "eq", "threshold": 1.0, "source": HUMAN_SOURCE, "enteredBy": by, "item": ev.get("item"),
            "measured": ev.get("value"), "unit": ev.get("unit"), "memo": ev.get("memo"), "t": alert.get("t")}


def with_human_evidence(t1_rows: list[dict], alert: dict | None) -> tuple[list[dict], dict[str, dict]]:
    """Causes the knowledge gives no sensor Evidence rule (a pattern with no real-time sensor, such as OIL_ANALYSIS) get the
    person's entered analysis as their evidence. Causes with their own Evidence keep only that (a detector reading is never
    replaced). Returns (rows, results for rank_causes). The ranking among such causes stays prior × 1 — the knowledge's order."""
    ev = human_evidence(alert)
    if ev is None:
        return t1_rows, {}
    rows = [r if r.get("evidence") else dict(r, evidence=[dict(ev)]) for r in t1_rows]
    if all(r is t for r, t in zip(rows, t1_rows)):
        return t1_rows, {}
    return rows, {ev["id"]: {"value": 1.0, "passed": True, "status": "PASS", "source": HUMAN_SOURCE}}


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
            raw = r.get('value')
            known = (type(r.get('passed')) is bool and isinstance(raw, (float, int))
                     and not isinstance(raw, bool) and math.isfinite(raw)
                     and r.get('status') != 'UNKNOWN' and not r.get('error'))
            ok = r['passed'] if known else None
            wsum += w
            wpass += w if ok else 0.0
            evs.append({"id": e["id"], "name": e.get("name"), "weight": w, "expect": e.get("expect"),
                        "threshold": e.get("threshold"), "value": raw, "passed": ok,
                        "status": ('PASS' if ok else 'FAIL') if known else 'UNKNOWN',
                        **{k: r[k] for k in ('error', 'error_kind', 'reason', 'sql', 'coverage') if k in r},
                        **{k: e[k] for k in HUMAN_FIELDS if k in e}})
        prior = float(row.get("prior") or 0)
        score = prior * (wpass / wsum) if wsum > 0 else prior * NO_EVIDENCE_DISCOUNT
        out.append({"id": row["causeId"], "name": row.get("cause"), "description": row.get("description"),
                    "failureModeId": row.get("failureModeId"), "failureMode": row.get("failureMode"),
                    "component": row.get("component"), "symptoms": row.get("symptoms") or [],
                    "prior": prior, "score": None if any(e['status'] == 'UNKNOWN' for e in evs) else round(score, 4), "evidence": evs})
    # evidence-backed causes always rank above causes that have no confirmed evidence
    out.sort(key=lambda c: (c['score'] is not None, any(e["passed"] is True for e in c["evidence"]), c["score"] or 0), reverse=True)
    return out


def evidence_status(causes: list[dict]) -> dict:
    """An unknown alternative cannot be silently ranked below a known candidate."""
    unknown = sorted({e['id'] for c in causes for e in c.get('evidence', [])
                      if e.get('passed') is None or e.get('status') == 'UNKNOWN'})
    supported = any(e.get('passed') is True for c in causes for e in c.get('evidence', []))
    status = 'UNKNOWN' if unknown else 'SUPPORTED' if supported else 'UNSUPPORTED'
    return dict(status=status, unknown=unknown, withheld=status != 'SUPPORTED',
                reason='근거 조회가 불완전하여 원인 순위와 조치를 보류합니다.' if unknown else
                '현재 관측 근거로 뒷받침되는 원인이 없어 조치를 보류합니다.' if not supported else None)


def _kind(action: dict) -> str:
    """Card action kind: PLC command, CMMS work order or ERP purchase request (the process service treats each differently)."""
    if action.get("kind") == "command":
        return "command"
    return "work_order" if action.get("code") == "WO_CREATE" else "purchase"


def _skills_for(cause_id: str, t2_by_cause: dict[str, list[dict]]) -> list[dict]:
    """t2_skills rows (the failure mode's SOP skills): immediate mitigations first, then remedies, by SOP id."""
    return sorted(t2_by_cause.get(cause_id) or [], key=lambda r: (r.get("relation") != "MITIGATED_BY", r.get("sopId") or ""))


def _actions_for(cause_id: str, t2_by_cause: dict[str, list[dict]]) -> list[dict]:
    """Flatten the SOP skills into one entry per action code (the first skill that uses the code supplies value and SOP).
    The process service validates approved commands against these entries (code, parameter, range)."""
    acts, seen = [], set()
    for k in _skills_for(cause_id, t2_by_cause):
        steps = sorted([s for s in (k.get("steps") or []) if s.get("id")], key=lambda s: s.get("order") or 0)
        for a in sorted(k.get("actions") or [], key=lambda a: a.get("seq") or 0):
            if not a.get("code") or a["code"] in seen:
                continue
            seen.add(a["code"])
            rng = [a["min"], a["max"]] if a.get("min") is not None and a.get("max") is not None else None
            acts.append({"code": a["code"], "actionId": a["id"], "name": a.get("name"), "kind": _kind(a),
                         "relation": k.get("relation"), "description": k.get("description"),
                         "param": a.get("param"), "value": a.get("value"), "paramRange": rng,
                         "actuatorId": a.get("target"), "resource": a.get("targetName"), "constraints": [],
                         "skillId": k["skillId"],
                         "sop": {"id": k.get("sopId"), "name": k.get("name"),
                                 "steps": [{"id": s["id"], "order": s.get("order"), "text": s.get("text"),
                                            "manual": s.get("manual")} for s in steps]}})
    return acts


def _citations(causes: list[dict], actions: list[dict], skills: list[dict] | None = None) -> list[str]:
    ids: list[str] = []
    for c in causes:
        ids += [c["id"], c.get("failureModeId")] + [e["id"] for e in c["evidence"]]
    for k in skills or []:
        ids += [k.get("skillId"), k.get("sopId")]
    for a in actions:
        ids += [a["actionId"], a.get("skillId"), a["sop"].get("id"), a.get("actuatorId")] + [k.get("id") for k in a["constraints"]]
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


PATTERN_KO = {"COOLER_DEGRADATION": "쿨러 성능 저하", "PUMP_LEAKAGE": "펌프 내부 누설", "FAN_VIBRATION": "팬 진동 상승", "OVERHEAT_TRIP": "과열 보호 정지",
              "OIL_ANALYSIS": "오일 분석 기준 이탈(사람 입력)"}


def template_summary(alert: dict, causes: list[dict], actions: list[dict]) -> str:
    top = causes[0] if causes else None
    cmds = [a for a in actions if a["kind"] == "command"]
    wos = [a for a in actions if a["kind"] == "work_order"]
    ev = alert.get("evidence") or {}
    shown = {"ts1": ("TS1", "℃"), "ce": ("CE", "%"), "ps1": ("PS1", "bar"), "fs1": ("FS1", "l/min"), "vs1": ("VS1", "mm/s"), "load": ("LoadSP", "%")}
    reading = ", ".join(f"{tag} {ev[k]} {unit}" for k, (tag, unit) in shown.items() if ev.get(k) is not None)
    parts = [f"{alert.get('asset')}에서 {PATTERN_KO.get(alert.get('pattern'), alert.get('pattern'))} 경보가 발생했습니다"
             + (f" ({reading})." if reading else ".")]
    if top:
        passed = [e["name"] for e in top["evidence"] if e["passed"]]
        parts.append(f"가장 유력한 원인은 '{top['name']}'(점수 {top['score']:.2f})이며 근거는 {', '.join(passed) if passed else '없음'}입니다.")
    if cmds:
        parts.append("권장 즉시 조치: " + ", ".join(f"{a['name']}({a['param']}={a['value']})" for a in cmds)
                     + (f"; 완화 후 {wos[0]['name']}를 발행합니다." if wos else "."))
    return " ".join(parts)


def build_card(incident_id: str, alert: dict, causes: list[dict], t2_by_cause: dict[str, list[dict]],
               freshness: dict, summary: str | None = None) -> dict:
    assessment = evidence_status(causes)
    top = causes[0]["id"] if causes and not assessment['withheld'] else None
    actions = _actions_for(top, t2_by_cause) if top else []
    skills = _skills_for(top, t2_by_cause) if top else []
    card = {"incident": incident_id, "alert": alert, "freshness": freshness,
            "causes": causes, "topCause": top, "failureMode": causes[0].get("failureModeId") if top else None,
            "withheld": assessment['withheld'], "evidence_status": assessment,
            "recommended": actions,
            "skills": [{"id": k["skillId"], "sopId": k.get("sopId"), "name": k.get("name"), "kind": k.get("kind"), "relation": k.get("relation"),
                        "approver": k.get("approver"), "actions": [f"{a['code']}={a.get('value')}" for a in k.get("actions") or []]} for k in skills],
            "citations": _citations(causes, actions, skills),
            "summary": assessment['reason'] if assessment['withheld'] else summary or template_summary(alert, causes, actions)}
    return card
