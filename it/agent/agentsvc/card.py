"""Guide-card assembly (L8, pure logic): rank causes by prior × evidence and the document's diagnosis rules, then list the failure
mode's SOP skills with citations.

가이드 카드는 원인 · 근거와 그 고장 유형의 조치 방법(SOP 스킬) 목록까지다. 무엇을 할지(조치 카드 한 장 = SOP 하나)는 판단 카드(cards.evaluate)가
고르고 순위를 매긴다 — 가이드 카드가 SOP 들의 조치를 한 목록으로 섞어 「권장 조치」라 부르면 어느 절차에도 없는 조합이 되고 판단 카드와 갈린다(검진 G1-04).
"""
from typing import Any
import math

from hydcommon.maintenance_policy import PM_PATTERN
from hydcommon.skill_scope import PURCHASE_PATTERN
from hydcommon.words import josa

from . import cards as cardslib

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


#: 문서의 진단 규칙이 사는 판단(결정표 dt:diagnose-cause, 적중 정책 PRIORITY — instances.cypher). 「경보 X에서 값이 …이면 원인 Y를 1순위로 둔다」
DIAGNOSIS = "dec:diagnose-cause"


def _rule_status(rule: dict, facts: dict) -> tuple[str, list[str]]:
    """진단 규칙 한 행 → (FIRED · NOT_FIRED · UNKNOWN, 값을 모르는 입력의 이름). 검사는 모두 AND 다 — 하나라도 거짓이면 값을 모르는 검사가 있어도
    발화하지 않는다(cards.test_ok 와 같은 비교)."""
    tests = rule.get("tests") or []
    got = [cardslib.test_ok(t, facts) for t in tests]
    if not tests or any(r is False for r in got):
        return "NOT_FIRED", []
    unknown = [str(t.get("name") or t.get("variable")) for t, r in zip(tests, got) if r is None]
    return ("UNKNOWN", unknown) if unknown else ("FIRED", [])


def rank_causes(t1_rows: list[dict], results: dict[str, dict], rules: list[dict] = (), facts: dict | None = None) -> list[dict]:
    """t1_rows: T1 template rows. results: evidence id -> {"value", "passed"}.
    score = prior × (Σ weight of passed evidence / Σ weight).
    rules · facts: 문서의 진단 규칙 가운데 이 원인 후보를 고르는 것과 그 규칙이 시험하는 사실(decide.diagnosis_rules). 발화한 규칙이 고른
    원인을 맨 앞에 둔다(문서의 「…이면 Y를 1순위 원인으로 둔다」). 규칙마다 판정을 그 원인의 rules 에 남기고, 규칙이 있는데 하나도 발화하지
    않았거나 규칙이 보는 값을 모르면 evidence_status 가 보류한다 — 전에는 이 규칙을 평가하지 않아, 학생이 문서에서 진단 규칙을 빼도 판단이
    같았고 냉각 효율이 정상인 설비도 사전 확률로 핀 오염이 골라졌다(2026-11-22 탐사 C1)."""
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
                    "prior": prior, "score": None if any(e['status'] == 'UNKNOWN' for e in evs) else round(score, 4), "evidence": evs,
                    "rules": []})
    by_id = {c["id"]: c for c in out}
    for rule in rules:
        status, unknown = _rule_status(rule, facts or {})
        for cid in rule.get("outputs") or []:
            if cid in by_id:
                by_id[cid]["rules"].append({"id": rule.get("rule"), "annotation": rule.get("annotation"), "status": status, "unknown": unknown})
    # the document's fired diagnosis rule puts its cause first; then evidence-backed causes rank above causes that have no confirmed evidence
    out.sort(key=lambda c: (any(r["status"] == "FIRED" for r in c["rules"]), c['score'] is not None,
                            any(e["passed"] is True for e in c["evidence"]), c["score"] or 0), reverse=True)
    return out


#: 설비 센서가 아니라 업무 표 감시가 내는 경보(it/neo4j/v2/scenario_structure.cypher — detectionMode · Symptom 없음). 원인 진단 대상이 아니다
BUSINESS_PATTERNS = frozenset({PM_PATTERN, PURCHASE_PATTERN})


def no_cause_message(k, pattern: str) -> str:
    """원인 후보가 없을 때 학생이 읽는 문장 — 지식 지도의 패턴 목록(agent /api/ontology/patterns) · 수동 판단 · 판단 등록 도구(dmn-mcp)가 이 한 곳을 쓴다(2026-10-25 수업 한 바퀴: 「no cause candidates for pattern …」가 판단 규칙 · 손익 화면에 그대로 보였다).
    고장 유형이 없는 패턴(정기 정비 도래 · 재고 기준 이탈)은 원인 진단 대상이 아니라 업무 흐름의 에이전트가 판단한다."""
    meta = next((p for p in k.patterns() if p.get("code") == pattern), {})
    name = meta.get("name") or pattern
    if pattern in BUSINESS_PATTERNS:
        quoted = f"'{name}'"
        return f"{josa(quoted, '은')} 고장 원인을 진단하는 이상 패턴이 아닙니다 — 업무 흐름(정기 정비 · 예비품 구매)의 에이전트가 판단합니다. 설비 센서 값으로 감지하는 이상 패턴을 고르세요"
    return f"'{name}'의 원인 지식이 아직 없습니다 — 지식 › 문서 등록에서 이 고장을 다루는 매뉴얼을 적재한 뒤 다시 실행하세요"


#: 업무 경보가 판단에 쓰는 지식(조치 방법 · 후보 규칙)이 무엇이고 어떤 문서가 그것을 넣는가 — business_knowledge_missing 의 낱말
BUSINESS_KNOWLEDGE = {PM_PATTERN: ("예방 정비 지식(예방 조치 방법과 그 후보 규칙, 그것이 막는 고장의 원인)", "예방 정비 절차"),
                      PURCHASE_PATTERN: ("구매 지식(구매 요청 조치 방법과 그 후보 규칙)", "예비품 구매 절차")}


def business_knowledge_missing(k, pattern: str) -> str:
    """업무 경보(정기 정비 도래 · 재고 기준 이탈)의 판단 지식이 지식 지도에 없을 때 학생이 읽는 문장 — 판단 엔진(decide)과 판단 등록 도구
    (dmn-mcp)가 이 한 곳을 쓴다. 문서를 넣기 전이나 비운 뒤에 이 경보가 나면, 고칠 것은 도구 인자가 아니라 지식이다."""
    name = next((p.get("name") for p in k.patterns() if p.get("code") == pattern), None) or pattern
    what, procedure = BUSINESS_KNOWLEDGE[pattern]
    return (f"'{name}' 경보를 판단할 {what}이 지식 지도에 없어 판단하지 않았습니다 — 「지식 › 문서 등록」에서 {procedure}가 담긴 매뉴얼을 "
            "적재한 뒤 이 단계를 다시 수행하세요")


def evidence_status(causes: list[dict]) -> dict:
    """An unknown alternative cannot be silently ranked below a known candidate. When every unknown is a window whose record
    is arriving now but does not yet reach back over the whole window (coverage.ready_in_s — mcp_tsdb.observation_coverage),
    the reason says so and when to reassess, so the person does not read a just-started stack as a sensor fault."""
    rows = {e['id']: e for c in causes for e in c.get('evidence', []) if e.get('passed') is None or e.get('status') == 'UNKNOWN'}
    unknown = sorted(rows)
    # 문서의 진단 규칙(rank_causes 의 rules): 있으면 원인은 그 규칙이 고른다 — 하나도 발화하지 않았으면 원인을 정하지 않고, 값을 모르면 근거 미확인이다
    rules = {r['id']: r for c in causes for r in c.get('rules') or []}
    fired = any(r['status'] == 'FIRED' for r in rules.values())
    rule_unknown = list(dict.fromkeys(n for r in rules.values() if r['status'] == 'UNKNOWN' for n in r['unknown']))
    supported = fired or any(e.get('passed') is True for c in causes for e in c.get('evidence', []))
    status = ('UNKNOWN' if unknown or rule_unknown else 'UNSUPPORTED' if rules and not fired
              else 'SUPPORTED' if supported else 'UNSUPPORTED')
    # 보류의 까닭은 무엇이 없었는지를 말한다: 원인 지식이 아예 없을 때(문서를 넣기 전 · 비운 뒤)와 원인은 있는데 확인할 근거 규칙이 없을 때를
    # 「관측 근거로 뒷받침되는 원인이 없다」(센서를 봤더니 아니었다)로 말하면 학생은 설비가 정상이라고 읽는다
    said = ', '.join(f"「{r.get('annotation') or r['id']}」" for r in rules.values())
    reason = ('근거 조회가 불완전하여 원인 순위와 조치를 보류합니다.' if unknown else
              f"문서의 진단 규칙이 보는 값({', '.join(rule_unknown)})을 지금 읽지 못해 원인 순위와 조치를 보류합니다." if rule_unknown else
              f"문서의 진단 규칙 {josa(said, '이')} 지금 설비 값에 맞지 않아 원인을 정하지 않고 조치를 보류합니다." if rules and not fired else
              None if supported else
              '이 경보의 원인 지식이 지식 지도에 없어 조치를 보류합니다 — 「지식 › 문서 등록」에서 이 고장을 다루는 매뉴얼을 적재한 뒤 다시 평가하세요.'
              if not causes else
              f'원인 후보 {len(causes)}개에 설비 값으로 확인할 근거가 지식에 없어 조치를 보류합니다 — 어떤 센서 값이 어떠면 그 원인인지가 적힌 '
              '매뉴얼을 「지식 › 문서 등록」에서 적재한 뒤 다시 평가하세요.'
              if not any(c.get('evidence') for c in causes) else
              '현재 관측 근거로 뒷받침되는 원인이 없어 조치를 보류합니다.')
    filling = [e['coverage'] for e in rows.values() if e.get('reason') == 'OBSERVATION_GAP' and isinstance(e.get('coverage'), dict)
               and all(isinstance(e['coverage'].get(k), (int, float)) for k in ('ready_in_s', 'window_s'))]
    if unknown and len(filling) == len(rows):
        reason += (f" 설비 기록이 이어진 지 얼마 되지 않아(시스템을 막 켰거나 수집이 잠시 끊겼다 다시 이어진 경우) 판단에 쓰는 최근 "
                   f"{max(float(c['window_s']) for c in filling):g}초 기록이 아직 다 차지 않았습니다. 지금 값은 들어오고 있으니 약 "
                   f"{math.ceil(max(c['ready_in_s'] for c in filling))}초 뒤 다시 평가하세요.")
    return dict(status=status, unknown=unknown, withheld=status != 'SUPPORTED', reason=reason)


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
    # 잰 값은 원인마다의 근거(evidence — 이름 · 값 · 기준)가 싣는다. 전에는 경보 근거에서 수업 설비의 여섯 태그(TS1 · CE · PS1 · FS1 · VS1 · LoadSP)를
    # 골라 이 문장에 붙이는 구절이 있었는데, 진단하는 곳(판단 서비스 · 읽기 평가 · 판단 실험) 어디도 경보 근거를 넘기지 않아 쓰이지 않았다(전수검사 02-8)
    top = causes[0] if causes else None
    what = f"「{top['failureMode']}」 경보" if top and top.get("failureMode") else "경보"
    parts = [f"{alert.get('asset')}에서 {what}가 발생했습니다."]
    if top:
        passed = [e["name"] for e in top["evidence"] if e["passed"]]
        fired = [r.get("annotation") or r["id"] for r in top.get("rules") or [] if r["status"] == "FIRED"]
        parts.append(f"가장 유력한 원인은 '{top['name']}'(점수 {top['score']:.2f})이며 근거는 {', '.join(passed) if passed else '없음'}입니다."
                     + (f" 문서의 진단 규칙 「{'」 · 「'.join(fired)}」에 맞아 1순위로 둡니다." if fired else ""))
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
