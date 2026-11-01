"""L9 action-card decisions (pure, ontology v2): PENDING_APPROVAL -> APPROVED | REJECTED | CLOSED_UNAPPROVED(승인 없이 처리 건이 끝남). 승인 뒤 실행 결과(EXECUTED · PARTIAL)는
approval_hooks.record_execution 이 같은 판단에 적는다(판단 상태 표의 나머지 반쪽 — 이 파일은 승인 · 거절까지).

An option is one SOP skill (조치 방법 = Skill = SOP) with its atomic actions. Who may approve comes from the ontology:
Skill -APPROVED_BY-> Role, Role.level — the same role or a higher level may approve. System transactions (CMMS work
order, ERP purchase request) are executed by the process service; PLC commands are never sent from here — they go
through the HITL incident and the command gateway.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .machine import _transition   # A143: decision mutations share the Incident state lock (see machine.STATE_LOCK)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new(payload: dict) -> dict:
    d = dict(payload)
    d.update(state="PENDING_APPROVAL", created=d.get("created") or _now(), chosen=None, approvedBy=None, approvedRole=None,
             override=False, executions=[], history=[{"state": "PENDING_APPROVAL", "t": _now()}])
    return d


def submission_scope(payload):
    """A producer task/generation owns one decision, independent of retries and leases."""
    origin = payload.get('origin') or {}
    scope = origin.get('process_scope')
    if isinstance(scope, dict) and scope.get('workitem'):
        return tuple(scope.get(k) for k in ('tenant', 'instance', 'workitem', 'generation', 'version'))
    return None


def _level(d: dict, role: str) -> int:
    r = (d.get("roles") or {}).get(role)
    return int(r["level"]) if r else 0


def may_approve(d: dict, opt: dict, role: str) -> bool:
    """The option's approver role itself, or any role ranked above it (ontology Skill -APPROVED_BY-> Role and role levels)."""
    from hydcommon.execution_scope import require_decision_option
    try:
        require_decision_option(d, opt)
    except ValueError:
        return False
    return holds_approver_role(d, opt, role)


def holds_approver_role(d: dict, opt: dict, role: str) -> bool:
    """Role only: the option's approver role or a higher one. Execution readiness is not checked — rejection uses this, so a decision whose
    options were all excluded (stock · rules) can still be closed by the role that would have approved it (2026-10-23 live: B stuck at approval)."""
    need = (opt.get("approver") or {}).get("id")
    need_level = int((opt.get("approver") or {}).get("level") or _level(d, need or ""))
    return not need or role == need or _level(d, role) > need_level


def approver_roles(d: dict, opt: dict) -> list[str]:
    """이 안을 승인할 수 있는 역할 id 들(holds_approver_role 이 참인 판단의 역할 표 전부, 등급 낮은 순) — 화면이 역할 규칙 사본 없이 단추를 켜고
    끄게 응답에 싣는 값(W1-11 · W1-25). 승인 역할이 없는 안은 역할 표 전부. 접수는 서버가 holds_approver_role 로 다시 판정한다."""
    roles = d.get("roles") or {}
    return [r for r in sorted(roles, key=lambda r: (_level(d, r), r)) if holds_approver_role(d, opt, r)]


STATE_WORDS = {"APPROVED": "이미 승인됐습니다", "REJECTED": "이미 거절됐습니다", "CLOSED_UNAPPROVED": "승인 없이 처리 건이 끝났습니다", "EXECUTED": "이미 실행됐습니다", "PARTIAL": "이미 일부 실행됐습니다"}


def _pending(d: dict) -> None:
    if d["state"] != "PENDING_APPROVAL":
        raise ValueError(f"판단 {d.get('id')}은(는) {STATE_WORDS.get(d['state'], d['state'])} — 다시 승인 · 거절하지 않습니다")


@_transition
def approve(d: dict, option_id: str, by: str, role: str, reason: str = "") -> dict:
    _pending(d)
    opt = next((o for o in d.get("options", []) if o["id"] == option_id), None)
    if opt is None:
        raise ValueError(f"판단 {d.get('id')}에 카드 {option_id}이(가) 없습니다")
    from hydcommon.execution_scope import require_decision_option
    require_decision_option(d, opt)
    if not opt.get("feasible", False):
        why = "; ".join(v.get("annotation") or v.get("name") or v.get("rule", "") for v in opt.get("violations") or []) or "infeasible"
        raise ValueError(f"'{opt['name']}'은(는) 규정상 고를 수 없다: {why}")
    if not may_approve(d, opt, role):
        need = (opt.get("approver") or {}).get("id")
        raise PermissionError(f"승인 권한 없음: '{opt['name']}'은(는) {(opt.get('approver') or {}).get('name', need)} 이상이 승인해야 한다")
    d.update(state="APPROVED", chosen=option_id, approvedBy=by, approvedRole=role, override=option_id != d.get("recommended"), reason=reason)
    d["history"].append({"state": "APPROVED", "t": _now(), "by": by, "role": role, "option": option_id, "reason": reason})
    item = lambda a: {"skill": opt["id"], "sop": opt.get("sopId"), "code": a.get("code"), "name": a.get("name"),
                      "system": a.get("target"), "value": a.get("value"), "param": a.get("param")}
    acts = opt.get("actions") or []
    return {"option": opt, "enterprise": [item(a) for a in acts if a.get("kind") != "command"],
            "ot": [item(a) for a in acts if a.get("kind") == "command"]}


@_transition
def reject(d: dict, by: str, reason: str) -> None:
    _pending(d)
    d.update(state="REJECTED", approvedBy=by, reason=reason)
    d["history"].append({"state": "REJECTED", "t": _now(), "by": by, "reason": reason})


@_transition
def close_unapproved(d: dict, reason: str) -> None:
    """승인을 기다리던 판단의 처리 건이 승인 없이 끝났다(조치 전 해소 · 사람이 닫음 · 시한 초과 등) — 판단도 끝낸다(전에는 「승인 대기」로
    남아 화면이 끝난 처리 건의 판단을 승인할 것처럼 보였다). reason = 처리 건이 끝난 곳."""
    _pending(d)
    d.update(state="CLOSED_UNAPPROVED", reason=reason)
    d["history"].append({"state": "CLOSED_UNAPPROVED", "t": _now(), "by": "sys:process", "reason": reason})
