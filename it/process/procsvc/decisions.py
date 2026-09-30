"""L9 enterprise decisions (pure): PENDING_APPROVAL -> APPROVED -> EXECUTED | PARTIAL, or REJECTED.

Who may approve comes from the ontology: Option -APPROVED_BY-> Role, Role.level. The same role or a higher level may
approve. Enterprise skills are executed in ERP/MES/CMMS/QMS/EMS by the process service; OT skills (SCADA/PLC) are
never sent from here — they go through the HITL incident and the command gateway, as before.
"""
from __future__ import annotations

from datetime import datetime, timezone

OT_SYSTEMS = {"sys:scada"}


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
        why = "; ".join(v["name"] for v in opt.get("violations") or []) or "infeasible"
        raise ValueError(f"'{opt['name']}'은(는) 승인할 수 없다: {why}")
    need = (opt.get("approver") or {}).get("id")
    need_level = int((opt.get("approver") or {}).get("level") or _level(d, need or ""))
    if need and role != need and _level(d, role) <= need_level:
        raise PermissionError(f"승인 권한 없음: '{opt['name']}'은(는) {(opt.get('approver') or {}).get('name', need)} 이상이 승인해야 한다")
    d.update(state="APPROVED", chosen=option_id, approvedBy=by, approvedRole=role, override=option_id != d.get("recommended"), reason=reason)
    d["history"].append({"state": "APPROVED", "t": _now(), "by": by, "role": role, "option": option_id, "reason": reason})
    skills = opt.get("skills") or []
    return {"option": opt, "enterprise": [{"skill": s["id"], "system": s.get("system")} for s in skills if s.get("system") not in OT_SYSTEMS],
            "ot": [{"skill": s["id"], "system": s.get("system")} for s in skills if s.get("system") in OT_SYSTEMS]}


def reject(d: dict, by: str, reason: str) -> None:
    if d["state"] != "PENDING_APPROVAL":
        raise ValueError(f"decision is {d['state']}")
    d.update(state="REJECTED", approvedBy=by)
    d["history"].append({"state": "REJECTED", "t": _now(), "by": by, "reason": reason})


def record_execution(d: dict, results: list[dict], plan: dict) -> None:
    for r in results:
        d["executions"].append({"skill": r["skill"], "status": "DONE" if r.get("ok") else "FAILED", "ref": r.get("ref"),
                                "system": r.get("system"), "detail": r.get("detail") or r.get("error"), "t": _now()})
    for s in plan.get("ot", []):
        d["executions"].append({"skill": s["skill"], "status": "VIA_HITL", "system": s["system"], "t": _now(),
                                "detail": "즉시 제어는 인시던트 승인 → action.cmd → cmd-gateway 경로로만 실행된다"})
    d["state"] = "EXECUTED" if all(r.get("ok") for r in results) else "PARTIAL"
    d["history"].append({"state": d["state"], "t": _now()})
