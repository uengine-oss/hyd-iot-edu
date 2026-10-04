"""Read-only/in-memory counterexamples for the requirements audit; no plant/DB writes.

These probes record observations, not integration-test completion. Run with the same
project Python as pytest. The JSON explicitly distinguishes expected and observed.
"""
from __future__ import annotations

import configparser
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config = configparser.ConfigParser()
config.read(ROOT / "pytest.ini")
for path in config["pytest"]["pythonpath"].split():
    sys.path.insert(0, str(ROOT / path))

from procsvc import engine, ingest, instances, procdb  # noqa: E402


def service_case(activity_id: str, *, success: bool = True) -> dict:
    definition = engine.Definition.from_dict({
        "processDefinitionId": "audit_work_order", "processDefinitionName": "Audit work order",
        "ontologyRef": "proc:audit-work-order", "data": [{"name": "work_order", "type": "Object"}],
        "activities": [{"id": activity_id, "name": "Work order", "type": "serviceTask",
                        "orchestration": "hyd-process", "tool": "enterprise:WO_CREATE", "outputData": ["work_order"]}],
        "events": [{"id": "start", "type": "startEvent"}, {"id": "end", "type": "endEvent"}],
        "sequences": [{"id": "s1", "source": "start", "target": activity_id}, {"id": "s2", "source": activity_id, "target": "end"}],
    })
    calls, projections = [], []

    def execute(decision_id, item):
        calls.append(item)
        return {"ok": success, "ref": "AUDIT-WO" if success else None, "error": None if success else "database unavailable"}

    repo = procdb.MemoryRepo()
    runtime = instances.InstanceRuntime(repo, definition, instances.Hooks(
        exec_enterprise=execute, record_cypher=lambda q, **kw: projections.append(kw)))
    alert = {"alertId": "audit-alert", "asset": "AUDIT-01", "pattern": "AUDIT"}
    instance = runtime.on_alert_raise(alert)
    polls = [runtime.poll_once() for _ in range(3)]
    final = repo.get_instance(instance["proc_inst_id"])
    item = repo.list_workitems(proc_inst_id=instance["proc_inst_id"])[0]
    duplicate = runtime.on_alert_raise(alert) if final["status"] == "COMPLETED" else None
    return {"activity_id": activity_id, "tool": "enterprise:WO_CREATE", "hook_success": success,
            "calls": len(calls), "polls": polls, "instance_status": final["status"], "workitem_status": item["status"],
            "consumer": item.get("consumer"), "output": item.get("output"),
            "projected_process": projections[0]["process"], "expected_process": definition.raw["ontologyRef"],
            "duplicate_after_completion_created": duplicate is not None}


def main():
    ddl = "CREATE TABLE plant_a.readings (asset text, value numeric); CREATE TABLE plant_b.readings (asset text, value numeric);"
    plan = ingest.plan(ingest.parse_ddl(ddl), filename="two-plants.sql", batch="audit")
    inputs = plan["inputs"]
    reference = service_case("task:work-order")
    renamed = service_case("task:maintenance-order")
    failed = service_case("task:work-order", success=False)
    findings = [
        {"id": "A004", "requirement": "R02", "expected": "Distinct schema/table/column identities",
         "observed": inputs, "pass": len({i["id"] for i in inputs}) == len(inputs)},
        {"id": "A005", "requirement": "R11", "expected": "Same supported service tool works after activity ID rename",
         "observed": {"reference": reference, "renamed": renamed}, "pass": renamed["calls"] == 1 and renamed["instance_status"] == "COMPLETED"},
        {"id": "A006", "requirement": "R12", "expected": "Execution projection uses definition ontologyRef",
         "observed": {"expected": reference["expected_process"], "actual": reference["projected_process"]},
         "pass": reference["expected_process"] == reference["projected_process"]},
        {"id": "A007", "requirement": "R11", "expected": "Duplicate event after completion does not repeat the work",
         "observed": reference["duplicate_after_completion_created"], "pass": not reference["duplicate_after_completion_created"]},
        {"id": "A008", "requirement": "R10,R11", "expected": "A failed work-order action is not a successful completed instance",
         "observed": failed, "pass": failed["instance_status"] != "COMPLETED"},
    ]
    result = {"scope": "actual HYD functions with MemoryRepo and explicit fake enterprise hook; no DB/PLC/UI integration",
              "findings": findings, "passed": sum(x["pass"] for x in findings), "total": len(findings)}
    output = ROOT / ".evidence/reaudit/2026-10-04-baseline/behavior-probes.json"
    if output.exists():
        raise RuntimeError("Baseline evidence already exists; use a new evidence path for post-fix verification")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
