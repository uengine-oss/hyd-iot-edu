"""Guide-card assembly (L8, pure logic): rank causes by prior × evidence, then list the failure mode's SOP skills with citations.

가이드 카드는 원인 · 근거와 그 고장 유형의 조치 방법(SOP 스킬) 목록까지다. 무엇을 할지(조치 카드 한 장 = SOP 하나)는 판단 카드(cards.evaluate)가
고르고 순위를 매긴다 — 가이드 카드가 SOP 들의 조치를 한 목록으로 섞어 「권장 조치」라 부르면 어느 절차에도 없는 조합이 되고 판단 카드와 갈린다(검진 G1-04).
"""
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
            evs.append({"id": e["id"], "name": e.get("name"), "tag": e.get("tag"), "weight": w, "expect": e.get("expect"),
                        "threshold": e.get("threshold"), "value": raw, "passed": ok,
                        "status": ('PASS' if ok else 'FAIL') if known else 'UNKNOWN',
                        **{k: r[k] for k in ('error', 'error_kind', 'reason', 'sql', 'coverage') if k in r},
                        **{k: e[k] for k in HUMAN_FIELDS if k in e}})
        prior = float(row.get("prior") or 0)
        score = prior * (wpass / wsum) if wsum > 0 else prior * NO_EVIDENCE_DISCOUNT
        out.append({"id": row["causeId"], "name": row.get("cause"),
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


def _skills_for(cause_id: str, t2_by_cause: dict[str, list[dict]]) -> list[dict]:
    """t2_skills rows (the failure mode's SOP skills): immediate mitigations first, then remedies, by SOP id."""
    return sorted(t2_by_cause.get(cause_id) or [], key=lambda r: (r.get("relation") != "MITIGATED_BY", r.get("sopId") or ""))


def _citations(causes: list[dict], skills: list[dict]) -> list[str]:
    """인용: 원인 · 고장 유형 · 근거, 그리고 SOP 스킬마다 스킬 · 절차 번호 · 원자 조치 · 대상 · 단계 · 매뉴얼 절."""
    ids: list[str] = []
    for c in causes:
        ids += [c["id"], c.get("failureModeId")] + [e["id"] for e in c["evidence"]]
    for k in skills:
        ids += [k.get("skillId"), k.get("sopId")]
        ids += [x for a in k.get("actions") or [] for x in (a.get("id"), a.get("target"))]
        for s in k.get("steps") or []:
            ids.append(s.get("id"))
            if s.get("manual"):
                ids.append(s["manual"].get("ref") or s["manual"].get("id"))
    seen, out = set(), []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _action_text(a: dict) -> str:
    """원자 조치 한 줄: 이름과 값(팬 속도 설정 100 % · 정비 작업지시 발행 SOP-COOL-14) — 영문 칸 이름(fan_pct=100)을 쓰지 않는다."""
    value = a.get("value")
    if value is None:
        return str(a.get("name") or a.get("code"))
    unit = " %" if str(a.get("param") or "").endswith("_pct") else ""
    return f"{a.get('name') or a.get('code')} {value}{unit}"


def template_summary(alert: dict, causes: list[dict], skills: list[dict]) -> str:
    top = causes[0] if causes else None
    ev = alert.get("evidence") or {}
    shown = {"ts1": ("TS1", "℃"), "ce": ("CE", "%"), "ps1": ("PS1", "bar"), "fs1": ("FS1", "l/min"), "vs1": ("VS1", "mm/s"), "load": ("LoadSP", "%")}
    reading = ", ".join(f"{tag} {ev[k]} {unit}" for k, (tag, unit) in shown.items() if ev.get(k) is not None)
    what = f"「{top['failureMode']}」 경보" if top and top.get("failureMode") else "경보"
    parts = [f"{alert.get('asset')}에서 {what}가 발생했습니다" + (f" ({reading})." if reading else ".")]
    if top:
        passed = [e["name"] for e in top["evidence"] if e["passed"]]
        parts.append(f"가장 유력한 원인은 '{top['name']}'(점수 {top['score']:.2f})이며 근거는 {', '.join(passed) if passed else '없음'}입니다.")
    if skills:
        listed = "; ".join(f"{k.get('sopId')} {k.get('name')}(" + (", ".join(_action_text(a) for a in k.get('actions') or []) or "조치 없음") + ")"
                           for k in skills)
        parts.append(f"이 고장 유형의 조치 방법: {listed}. 어느 절차를 고를지는 조치 판단(규정 · 예측 · 순위)이 절차마다 비교합니다.")
    return " ".join(parts)


def build_card(incident_id: str, alert: dict, causes: list[dict], t2_by_cause: dict[str, list[dict]],
               freshness: dict, summary: str | None = None) -> dict:
    assessment = evidence_status(causes)
    top = causes[0]["id"] if causes and not assessment['withheld'] else None
    skills = _skills_for(top, t2_by_cause) if top else []
    card = {"incident": incident_id, "alert": alert, "freshness": freshness,
            "causes": causes, "topCause": top, "failureMode": causes[0].get("failureModeId") if top else None,
            "withheld": assessment['withheld'], "evidence_status": assessment,
            "skills": [{"id": k["skillId"], "sopId": k.get("sopId"), "name": k.get("name"), "kind": k.get("kind"), "relation": k.get("relation"),
                        "approver": k.get("approver"), "actions": [_action_text(a) for a in sorted(k.get("actions") or [], key=lambda a: a.get("seq") or 0)]}
                       for k in skills],
            "citations": _citations(causes, skills),
            "summary": assessment['reason'] if assessment['withheld'] else summary or template_summary(alert, causes, skills)}
    return card
