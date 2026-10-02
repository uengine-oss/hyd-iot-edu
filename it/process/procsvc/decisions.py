"""L9 action-card decisions (pure, ontology v2): PENDING_APPROVAL -> APPROVED -> EXECUTED | PARTIAL, or REJECTED.

An option is one SOP skill (조치 방법 = Skill = SOP) with its atomic actions. Who may approve comes from the ontology:
Skill -APPROVED_BY-> Role, Role.level — the same role or a higher level may approve. System transactions (CMMS work
order, ERP purchase request) are executed by the process service; PLC commands are never sent from here — they go
through the HITL incident and the command gateway.
"""
from __future__ import annotations

from datetime import datetime, timezone

OT_SYSTEMS = {"sys:scada"}   # where PLC commands go — never executed from a decision, only via the HITL incident


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new(payload: dict) -> dict:
    d = dict(payload)
    d.update(state="PENDING_APPROVAL", created=d.get("created") or _now(), chosen=None, approvedBy=None, approvedRole=None,
             override=False, executions=[], history=[{"state": "PENDING_APPROVAL", "t": _now()}])
    return d


def _level(d: dict, role: str) -> int:
    r = (d.get("roles") or {}).get(role)
    return int(r["level"]) if r else 0


def approve(d: dict, option_id: str, by: str, role: str, reason: str = "") -> dict:
    if d["state"] != "PENDING_APPROVAL":
        raise ValueError(f"decision is {d['state']}")
    opt = next((o for o in d.get("options", []) if o["id"] == option_id), None)
    if opt is None:
        raise ValueError(f"unknown option {option_id}")
    if not opt.get("feasible", False):
        why = "; ".join(v.get("annotation") or v.get("name") or v.get("rule", "") for v in opt.get("violations") or []) or "infeasible"
        raise ValueError(f"'{opt['name']}'은(는) 규정상 고를 수 없다: {why}")
    need = (opt.get("approver") or {}).get("id")
    need_level = int((opt.get("approver") or {}).get("level") or _level(d, need or ""))
    if need and role != need and _level(d, role) <= need_level:
        raise PermissionError(f"승인 권한 없음: '{opt['name']}'은(는) {(opt.get('approver') or {}).get('name', need)} 이상이 승인해야 한다")
    d.update(state="APPROVED", chosen=option_id, approvedBy=by, approvedRole=role, override=option_id != d.get("recommended"), reason=reason)
    d["history"].append({"state": "APPROVED", "t": _now(), "by": by, "role": role, "option": option_id, "reason": reason})
    item = lambda a: {"skill": opt["id"], "sop": opt.get("sopId"), "code": a.get("code"), "name": a.get("name"),
                      "system": a.get("target"), "value": a.get("value"), "param": a.get("param")}
    acts = opt.get("actions") or []
    return {"option": opt, "enterprise": [item(a) for a in acts if a.get("kind") != "command"],
            "ot": [item(a) for a in acts if a.get("kind") == "command"]}


def reject(d: dict, by: str, reason: str) -> None:
    if d["state"] != "PENDING_APPROVAL":
        raise ValueError(f"decision is {d['state']}")
    d.update(state="REJECTED", approvedBy=by)
    d["history"].append({"state": "REJECTED", "t": _now(), "by": by, "reason": reason})


def record_execution(d: dict, results: list[dict], plan: dict) -> None:
    for r in results:
        d["executions"].append({"skill": r["skill"], "code": r.get("code"), "status": "DONE" if r.get("ok") else "FAILED", "ref": r.get("ref"),
                                "system": r.get("system"), "detail": r.get("detail") or r.get("error"), "t": _now()})
    for s in plan.get("ot", []):
        d["executions"].append({"skill": s["skill"], "code": s.get("code"), "status": "VIA_HITL", "system": s.get("system"), "t": _now(),
                                "detail": f"PLC 명령 {s.get('code')}={s.get('value')} — 인시던트 승인 → action.cmd → cmd-gateway 경로로만 실행된다"})
    d["state"] = "EXECUTED" if all(r.get("ok") for r in results) else "PARTIAL"
    d["history"].append({"state": d["state"], "t": _now()})
