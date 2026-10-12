"""Non-business SYSTEM invocation journal, independently committed from transitions."""
from __future__ import annotations
import hashlib


def owner_hash(owner):
    return hashlib.sha256(str(owner).encode()).hexdigest()


def validate_rows(rows, pid, todo):
    if not rows:
        raise ValueError("system progress is empty")
    for row in rows:
        data = row.get("data") or {}
        if row.get("proc_inst_id") != pid or row.get("todo_id") != todo or not row.get("id"):
            raise ValueError("system progress case mismatch")
        if not data.get("system_observation") or not data.get("attempt_id"):
            raise ValueError("system progress correlation missing")
        closure = row.get("job_id") in ("SYSTEM_ATTEMPT_COMMITTED", "SYSTEM_ATTEMPT_ROLLED_BACK")
        if row.get("event_type") not in ("tool_usage_started", "tool_usage_finished") and not (closure and row.get("event_type") == "task_working"):
            raise ValueError("only observational system tool progress is allowed")


def require_owner(instance, workitem, tenant, pid, todo, consumer):
    if not instance or not workitem or instance.get("tenant_id") != tenant or workitem.get("tenant_id") != tenant:
        raise PermissionError("system progress tenant mismatch")
    if instance.get("proc_inst_id") != pid or workitem.get("proc_inst_id") != pid or str(workitem.get("id")) != str(todo):
        raise PermissionError("system progress case mismatch")
    # Service rows retain the lane's role binding (engine._make_workitem); the
    # executor is agent_orch=hyd-process, not a fabricated sys:process user id.
    if instance.get("status") != "RUNNING" or instance.get("is_deleted") or workitem.get("status") != "SUBMITTED" or workitem.get("agent_orch") != "hyd-process" or not consumer or workitem.get("consumer") != consumer:
        raise PermissionError("system progress requires the committed SYSTEM claim")


def require_closure(instance, workitem, start, tenant, pid, todo, consumer, row):
    if not instance or not workitem or instance.get("tenant_id") != tenant or workitem.get("tenant_id") != tenant or workitem.get("proc_inst_id") != pid:
        raise PermissionError("system progress closure tenant/case mismatch")
    data = (start or {}).get("data") or {}
    if not start or data.get("attempt_id") != row["data"]["attempt_id"] or data.get("owner_claim_hash") != owner_hash(consumer):
        raise PermissionError("system progress closure has no owned invocation")
