"""Guardrail policy (v3 L8 '가드레일 정책'): no command authority, every claim cites a node id, parameters inside range.

check() returns a list of violations; an empty list means the card may be submitted to the process engine.
"""
FORBIDDEN_KEYS = {"writes", "cmdId", "expiresAt", "mqtt", "topic"}


def check(card: dict) -> list[str]:
    v: list[str] = []
    cites = set(card.get("citations") or [])
    if not cites:
        v.append("citations list is empty")
    if not card.get("causes"):
        v.append("no cause candidates")
    fresh = card.get("freshness") or {}
    if not fresh.get("ok", False):
        v.append(f"data freshness not ok (age {fresh.get('age_s')} s) — reasoning withheld")

    # command authority: the agent must never emit command-shaped fields
    for k in FORBIDDEN_KEYS & set(card.keys()):
        v.append(f"command field '{k}' present on card (agent has no command authority)")

    for c in card.get("causes") or []:
        if not c.get("id"):
            v.append(f"cause '{c.get('name')}' has no node id")
        elif c["id"] not in cites:
            v.append(f"cause {c['id']} not in citations")
        for e in c.get("evidence") or []:
            if e.get("id") and e["id"] not in cites:
                v.append(f"evidence {e['id']} not in citations")

    for a in card.get("recommended") or []:
        for k in FORBIDDEN_KEYS & set(a.keys()):
            v.append(f"command field '{k}' present on action {a.get('code')} (agent has no command authority)")
        if not a.get("actionId"):
            v.append(f"action {a.get('code')} has no node id")
        elif a["actionId"] not in cites:
            v.append(f"action {a['actionId']} not in citations")
        rng, val = a.get("paramRange"), a.get("value")
        if rng and val is not None and not (rng[0] <= val <= rng[1]):
            v.append(f"action {a.get('code')} value {val} outside paramRange {rng}")
        if a.get("kind") == "command" and (not rng or val is None):
            v.append(f"command action {a.get('code')} lacks paramRange/value")
    return v


def check_decision(result: dict, ctx: dict) -> list[str]:
    """Enterprise decision guardrail: every impact cites a KPI node, the recommendation is feasible (no HARD policy
    violated, no missing fact) and names the approving Role from the ontology."""
    v: list[str] = []
    kpis = {k["id"] for k in ctx.get("kpis", [])}
    for o in result.get("options", []):
        for k in o.get("impacts", {}):
            if k not in kpis:
                v.append(f"{o['id']}: 온톨로지에 없는 KPI {k} 인용")
    rec = next((o for o in result.get("options", []) if o["id"] == result.get("recommended")), None)
    if rec:
        if rec.get("violations") or rec.get("errors"):
            v.append(f"권고안 {rec['id']}가 규정 위반 또는 데이터 부족")
        if not (rec.get("approver") or {}).get("id"):
            v.append(f"권고안 {rec['id']}에 승인 역할(Option -APPROVED_BY-> Role)이 없다")
    return v
