"""L9 지식 관리(순수 함수): 조치 방법(스킬 = SOP) 고치기 · 새로 만들기의 검사와, 문서 넣기가 같이 쓰는 SOP 번호 · 영향 연결 규칙.

사람이 process 서비스로 지식 지도(온톨로지 v2)를 고친다(에이전트는 읽기만):
  - 조치 방법 고치기(이름 · 설명 · 승인 역할 · 영향) 또는 고장 유형에 맞춘 새 SOP 조치 방법 만들기(validate_skill).
검사 문장은 학생에게 그대로 보인다(합니다체, 화면 말).
"""
from __future__ import annotations

import re

SOP_ID_RE = re.compile(r"^SOP-[A-Z0-9]+(?:-[A-Z0-9]+)*$")


AFFECTS_MAX = 12
AFFECTS_TARGET = re.compile(r"^(sv|msr):[a-z0-9]+(?:-[a-z0-9]+)*$")
AFFECTS_LABELS = {"sv": "StateVariable", "msr": "Measure"}
SIGNS = {"+": 1, "-": -1, 1: 1, -1: -1, "1": 1, "-1": -1}


def validate_affects(value, owner: str = "") -> list:
    """조치 방법의 영향 연결(Skill -[:AFFECTS {sign}]-> StateVariable | Measure) 한 곳 — 관리 화면의 조치 방법 고치기(A098)와 문서 검토
    (A079)가 같이 쓴다. [{target, sign(+/-), note?}] → [{target, label, sign(±1), note}]. 대상이 그래프에 있는지는 쓸 때 확인한다.
    owner = 문장 앞에 붙일 SOP 번호. None = 영향 없음([])."""
    where = f"{owner}: " if owner else ""
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > AFFECTS_MAX:
        raise ValueError(f"{where}영향 연결은 최대 {AFFECTS_MAX}개의 목록입니다")
    out, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{where}영향 연결 항목은 대상 · 방향이 있는 객체여야 합니다")
        target = str(item.get("target") or "").strip()
        if not AFFECTS_TARGET.fullmatch(target):
            raise ValueError(f"{where}영향 대상은 상태 변수(sv:…) 또는 성과 지표(msr:…) id입니다(소문자 · 숫자 · '-'): {target!r}")
        if target in seen:
            raise ValueError(f"{where}같은 영향 대상이 두 번 있습니다: {target}")
        sign = SIGNS.get(item.get("sign"))
        if sign is None:
            raise ValueError(f"{where}영향 방향은 + 또는 - 입니다")
        seen.add(target)
        out.append({"target": target, "label": AFFECTS_LABELS[target.split(":")[0]], "sign": sign,
                    "note": str(item.get("note") or "").strip()[:300]})
    return out


# 고장 유형 ↔ 스킬(SOP) 관계: 즉시 완화 · 근본 조치 · 예방 조치(정기 정비, 2026-10-09 확정 추가 — schema.json PREVENTED_BY).
# 관계 이름은 이 한 곳에서만 정한다(manual_knowledge · skill_graph가 가져다 쓴다).
FAILURE_RELATIONS = ("MITIGATED_BY", "REMEDIED_BY", "PREVENTED_BY")
FAILURE_RELATION_HELP = "고장 유형과의 관계는 MITIGATED_BY(즉시 완화) · REMEDIED_BY(근본 조치) · PREVENTED_BY(예방 조치 = 정기 정비)"
CORRECTIVE_RELATIONS = ("MITIGATED_BY", "REMEDIED_BY")      # 경보(고장) 대응 후보 규칙에 자동으로 합류하는 관계

def validate_skill(body: dict, create: bool = False, *, source_backed: bool = False) -> dict:
    """Skill edit (name, description, approver). A new skill (create=True) is an SOP matched to a failure mode
    (ontology v2: Skill.sopId, Skill -HAS_STEP-> Step ≥ 1, FailureMode -MITIGATED_BY|REMEDIED_BY|PREVENTED_BY-> Skill ≥ 1)."""
    name = str(body.get("name") or "").strip()
    if body.get('scope') not in (None, 'fault', 'purchase'):
        raise ValueError('조치 방법의 업무 범위는 고장 조치 또는 구매(purchase)입니다')
    if body.get('scope') != 'purchase' and (body.get('executable') is not None or body.get('parts') is not None or body.get('supplier_policy') is not None):
        raise ValueError('실행 여부 · 구매 부품 · 공급사 정책은 구매(purchase) 절차에서만 씁니다')
    if body.get('scope') == 'purchase':
        from hydcommon.skill_scope import purchase_shape
        scope_fields = purchase_shape(body, source_backed=source_backed)
    if not name:
        raise ValueError("조치 방법 이름이 비어 있습니다")
    if len(name) > 80:
        raise ValueError("조치 방법 이름은 80자 이내로 적습니다")
    out = {"name": name, "description": str(body.get("description") or "").strip()[:500]}
    if body.get('purchase_comparison_policy') is not None:
        if not source_backed or not create or body.get('scope') != 'purchase' or body.get('executable') is not True:
            raise ValueError('구매 비용 정책은 원문 검토의 실행 구매 생성 경로에서만 연결합니다')
        from hydcommon.purchase_comparison import policy
        out['purchase_comparison_policy']=policy(body['purchase_comparison_policy'])
    if body.get('maintenance_policy') is not None:
        if not source_backed or body.get('scope') == 'purchase' or not create:
            raise ValueError('원문 PM 적용 정책은 매뉴얼 검토 생성 경로에서만 연결합니다')
        from hydcommon.maintenance_policy import policy
        out['maintenance_policy']=policy(body['maintenance_policy'])
    if body.get("approver"):
        out["approver"] = str(body["approver"])
    if body.get("affects") is not None:
        out["affects"] = validate_affects(body["affects"])
    if not create:
        if body.get('scope') == 'purchase':
            raise ValueError('원문 구매 SOP는 매뉴얼 개정·검토 경로에서 변경하세요')
        # A075: a reviewer may (re)link an existing skill to a failure mode; the candidate rules of that failure mode then
        # offer the skill (meeting L253~302: ingested knowledge must reach the runtime judgment).
        if body.get("failureMode"):
            relation = body.get("relation") or "REMEDIED_BY"
            if relation not in FAILURE_RELATIONS:
                raise ValueError(FAILURE_RELATION_HELP)
            out.update(failureMode=str(body["failureMode"]).strip(), relation=relation)
        return out
    sop = str(body.get("sopId") or "").strip().upper()
    if not SOP_ID_RE.match(sop):
        raise ValueError("SOP 번호는 SOP-FAN-05처럼 SOP-로 시작하고 대문자 · 숫자를 '-'로 잇습니다")
    steps = body.get("steps") or []
    if isinstance(steps, str):
        steps = steps.splitlines()
    steps = [str(s).strip() for s in steps if str(s).strip()]
    if not steps:
        raise ValueError("절차 단계가 하나 이상 있어야 합니다(한 줄에 한 단계)")
    if body.get('scope') == 'purchase':
        out.update(sopId=sop, steps=steps[:30], **scope_fields)
        return out
    if not str(body.get("failureMode") or "").strip():
        raise ValueError("조치 방법을 고장 유형에 연결하세요 — 검토 화면의 고장 유형 칸에서 고릅니다(구매 · 참고 절차는 업무 범위를 바꿉니다)")
    kind = body.get("kind") or "work_order"
    if kind not in ("control", "work_order"):
        raise ValueError("조치 방법 종류는 설비 명령(control) 또는 작업지시(work_order)입니다")
    relation = body.get("relation") or "REMEDIED_BY"
    if relation not in FAILURE_RELATIONS:
        raise ValueError(FAILURE_RELATION_HELP)
    out.update(sopId=sop, steps=steps[:30], failureMode=str(body["failureMode"]).strip(), kind=kind, relation=relation)
    return out


def skill_id(sop_id: str) -> str:
    """One skill per SOP: the id follows the SOP number (skill:sop-fan-05)."""
    return "skill:" + re.sub(r"[^a-z0-9-]+", "-", sop_id.lower()).strip("-")
