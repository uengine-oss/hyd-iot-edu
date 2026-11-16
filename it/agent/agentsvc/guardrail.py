"""Guardrail policy (v3 L8 '가드레일 정책'): no command authority, every claim cites a node id.

check() 는 가이드 카드(원인 · 근거 · 조치 방법 목록)를, check_cards() 는 조치 카드 묶음을 본다. 둘 다 위반 문장 목록을 돌려주고, 빈 목록이면
그 카드 묶음을 판단으로 쓸 수 있다(이 서비스는 제출하지 않는다 — 판단 등록은 dmn-mcp 의 submit_decision · submit_purchase).
문장은 처리 기록 · 판단 채점 화면에 그대로 보인다 — 학생이 읽는 한국어로 쓴다(검진 G1-10).
"""
from hydcommon.words import particle
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
        v.append(f"카드에 설비 명령 칸 '{k}'{particle(k, '이')} 있습니다 — 에이전트는 명령 권한이 없습니다")

    for c in card.get("causes") or []:
        if not c.get("id"):
            v.append(f"원인 '{c.get('name')}'에 지식 노드 id 가 없습니다")
        elif c["id"] not in cites:
            v.append(f"원인 {c['id']}{particle(c['id'], '을')} 인용하지 않았습니다")
        for e in c.get("evidence") or []:
            if e.get('status') == 'UNKNOWN' or e.get('error') or ('passed' in e and e['passed'] is None):
                v.append(f"근거 {e.get('id')}의 판정이 미확인입니다")
            if e.get("id") and e["id"] not in cites:
                v.append(f"근거 {e['id']}{particle(e['id'], '을')} 인용하지 않았습니다")
    for k in card.get("skills") or []:
        if k.get("id") and k["id"] not in cites:
            v.append(f"조치 방법 {k['id']}{particle(k['id'], '을')} 인용하지 않았습니다")
    return v


def check_cards(result: dict) -> list[str]:
    """Action-card guardrail (ontology v2): every card was selected by a DMN rule of the ontology, and the recommended
    card is not excluded by a rule, names its approving Role and carries its SOP steps.
    문장은 학생이 화면에서 읽는다(승인 보류 409 · 미리 보기 거절 · 모의 판단의 거절 사유) — 화면 용어(조치 후보 · 규칙 · 승인 역할 · 단계)로, 「…니다」로 끝낸다.
    무엇이 어느 관계인지는 이 함수의 조건이 말한다: 후보로 고른 규칙 = Rule -OUTPUTS-> Skill, 제외 규칙 = 효과가 EXCLUDE 인 규칙(violations) 또는 실행 불가(feasible=False),
    승인 역할 = Skill -APPROVED_BY-> Role, 단계 = Skill -HAS_STEP-> Step. 승인 때는 사람이 고른 후보 하나를 recommended 로 넣어 부른다(approval.py).
    후보 id 바로 뒤에는 받침에 따라 갈리지 않는 조사(의 · 에)만 붙인다 — 화면이 id 를 이름으로 바꿔 보이므로(ui.js ID_RE) id 에 맞춘 은/는 · 이/가는 이름과 어긋나고,
    쌍점(:)을 붙이면 id 의 일부로 읽혀 이름으로 바뀌지 않는다."""
    v: list[str] = []
    for o in result.get("options", []):
        if o.get('kind') == 'reference' or o.get('executable') is False:
            v.append(f"조치 후보 {o['id']}의 종류가 원문 참고 절차라서 실행할 조치로 낼 수 없습니다")
        if not o.get("selectedBy"):
            v.append(f"조치 후보 {o['id']}의 근거가 되는(이 조치를 후보로 고른) 규칙이 지식에 없습니다")
    rec = next((o for o in result.get("options", []) if o["id"] == result.get("recommended")), None)
    if rec:
        if rec.get("violations") or not rec.get("feasible", True):
            v.append(f"조치 후보 {rec['id']}에 제외 규칙이 걸려 지금 조건에서는 실행할 수 없습니다")
        if not (rec.get("approver") or {}).get("id"):
            v.append(f"조치 후보 {rec['id']}에 승인 역할이 정해져 있지 않습니다")
        if not rec.get("steps"):
            v.append(f"조치 후보 {rec['id']}에 조치 단계가 없습니다")
    return v
