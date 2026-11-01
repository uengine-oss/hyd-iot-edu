"""Guardrail policy (v3 L8 '가드레일 정책'): no command authority, every claim cites a node id.

check() 는 가이드 카드(원인 · 근거 · 조치 방법 목록)를, check_cards() 는 조치 카드 묶음을 본다. 둘 다 위반 문장 목록을 돌려주고, 빈 목록이면
그 카드 묶음을 판단으로 쓸 수 있다(이 서비스는 제출하지 않는다 — 판단 등록은 dmn-mcp 의 submit_decision · submit_purchase).
문장은 처리 기록 · 판단 채점 화면에 그대로 보인다 — 학생이 읽는 한국어로 쓴다(검진 G1-10).
"""
FORBIDDEN_KEYS = {"writes", "cmdId", "expiresAt", "mqtt", "topic"}


def check(card: dict) -> list[str]:
    v: list[str] = []
    if card.get('withheld') or (card.get('evidence_status') or {}).get('withheld'):
        v.append('근거 판정이 보류라 조치를 낼 수 없습니다')
    cites = set(card.get("citations") or [])
    if not cites:
        v.append("인용한 지식 노드가 하나도 없습니다")
    if not card.get("causes"):
        v.append("원인 후보가 없습니다")
    fresh = card.get("freshness") or {}
    if not fresh.get("ok", False):
        v.append(f"설비 데이터가 신선하지 않아(나이 {fresh.get('age_s')}초) 추론을 보류합니다")

    # command authority: the agent must never emit command-shaped fields
    for k in sorted(FORBIDDEN_KEYS & set(card.keys())):
        v.append(f"카드에 설비 명령 칸 '{k}'이(가) 있습니다 — 에이전트는 명령 권한이 없습니다")

    for c in card.get("causes") or []:
        if not c.get("id"):
            v.append(f"원인 '{c.get('name')}'에 지식 노드 id 가 없습니다")
        elif c["id"] not in cites:
            v.append(f"원인 {c['id']}을(를) 인용하지 않았습니다")
        for e in c.get("evidence") or []:
            if e.get('status') == 'UNKNOWN' or e.get('error') or ('passed' in e and e['passed'] is None):
                v.append(f"근거 {e.get('id')}의 판정이 미확인입니다")
            if e.get("id") and e["id"] not in cites:
                v.append(f"근거 {e['id']}을(를) 인용하지 않았습니다")
    for k in card.get("skills") or []:
        if k.get("id") and k["id"] not in cites:
            v.append(f"조치 방법 {k['id']}을(를) 인용하지 않았습니다")
    return v


def check_cards(result: dict) -> list[str]:
    """Action-card guardrail (ontology v2): every card was selected by a DMN rule of the ontology, and the recommended
    card is not excluded by a rule, names its approving Role and carries its SOP steps."""
    v: list[str] = []
    for o in result.get("options", []):
        if o.get('kind') == 'reference' or o.get('executable') is False:
            v.append(f"{o['id']}: 원문 참고 절차는 실행 카드로 제출할 수 없다")
        if not o.get("selectedBy"):
            v.append(f"{o['id']}: 후보 선택 규칙(Rule -OUTPUTS-> Skill) 인용이 없다")
    rec = next((o for o in result.get("options", []) if o["id"] == result.get("recommended")), None)
    if rec:
        if rec.get("violations") or not rec.get("feasible", True):
            v.append(f"권고 카드 {rec['id']}가 규정(EXCLUDE 규칙)에 걸려 있다")
        if not (rec.get("approver") or {}).get("id"):
            v.append(f"권고 카드 {rec['id']}에 승인 역할(Skill -APPROVED_BY-> Role)이 없다")
        if not rec.get("steps"):
            v.append(f"권고 카드 {rec['id']}에 SOP 단계(Skill -HAS_STEP-> Step)가 없다")
    return v
