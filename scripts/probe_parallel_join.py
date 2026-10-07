"""A100 — parallel gateway live: register a definition with a parallel split/join through the real API, start an instance,
submit the two branches as a person, and record that the join waits for the last branch before the next task starts.

    .venv314/Scripts/python scripts/probe_parallel_join.py .evidence/reaudit/a100-parallel-<n>
"""
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request

PROCESS = "http://127.0.0.1:8080"


def http(path, data=None, method=None):
    req = urllib.request.Request(PROCESS + path, data=None if data is None else json.dumps(data, ensure_ascii=False).encode(), headers={"Content-Type": "application/json"},
                                 method=method or ("POST" if data is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


def definition(did):
    form = lambda key: {'fields_json': [{'key': key, 'type': 'text', 'text': key}]}
    return {'processDefinitionId': did, 'processDefinitionName': '병렬 합류 실측', 'version': '1',
            'roles': [{'name': '운전원', 'endpoint': 'role:operator'}],
            'data': [{'name': 'a_out', 'type': 'Text'}, {'name': 'b_out', 'type': 'Text'}, {'name': 'c_out', 'type': 'Text'}],
            'forms': {'fa': form('a_out'), 'fb': form('b_out'), 'fc': form('c_out')},
            'activities': [{'id': 'a', 'name': '작업지시 발행', 'type': 'userTask', 'role': '운전원', 'tool': 'formHandler:fa', 'outputData': ['a_out']},
                           {'id': 'b', 'name': '제어 명령', 'type': 'userTask', 'role': '운전원', 'tool': 'formHandler:fb', 'outputData': ['b_out']},
                           {'id': 'c', 'name': '결과 확인', 'type': 'userTask', 'role': '운전원', 'tool': 'formHandler:fc', 'outputData': ['c_out']}],
            'events': [{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}],
            'gateways': [{'id': 'split', 'type': 'parallelGateway'}, {'id': 'join', 'type': 'parallelGateway'}],
            'sequences': [{'id': 's0', 'source': 'start', 'target': 'split'},
                          {'id': 's1', 'source': 'split', 'target': 'a'}, {'id': 's2', 'source': 'split', 'target': 'b'},
                          {'id': 's3', 'source': 'a', 'target': 'join'}, {'id': 's4', 'source': 'b', 'target': 'join'},
                          {'id': 's5', 'source': 'join', 'target': 'c'}, {'id': 's6', 'source': 'c', 'target': 'end'}]}


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
    report = {"started": datetime.now(timezone.utc).isoformat(), "checks": []}
    def check(name, ok, detail=None):
        report["checks"].append({"name": name, "passed": bool(ok), "detail": detail}); print(("PASS " if ok else "FAIL ") + name, json.dumps(detail, ensure_ascii=False, default=str)[:220] if detail is not None else "", flush=True)
    did = "parallel_probe_" + uuid.uuid4().hex[:8]
    s, reg = http("/api/process/definitions", {"definition": definition(did)})
    check("registry_accepts_a_parallel_split_join_definition", s in (200, 201), {"status": s, "body": str(reg)[:200]})
    bad = definition(did + "_bad"); bad["sequences"][1]["condition"] = "a_out == 'x'"
    s, _ = http("/api/process/definitions", {"definition": bad})
    check("registry_refuses_a_conditioned_parallel_split", s == 400, {"status": s})
    s, inst = http("/api/instances/start", {"definition_id": did, "version": "1", "event_id": "probe-" + uuid.uuid4().hex[:6]})
    pid = inst.get("instance") or inst.get("proc_inst_id"); check("instance_started", s in (200, 201) and pid, {"status": s, "pid": pid})
    def view():
        s, v = http("/api/instances/" + pid); return v
    def rows():
        return {w["activity_id"]: w for w in view()["workitems"]}
    r = rows(); check("both_branches_start_at_once_and_the_joined_task_waits", r["a"]["status"] == "IN_PROGRESS" and r["b"]["status"] == "IN_PROGRESS" and r["c"]["status"] == "TODO", {k: v["status"] for k, v in r.items()})
    s, _ = http(f"/api/todolist/{r['a']['id']}/submit", {"output": {"a_out": "WO-1"}, "by": "운전원"})
    r = rows(); check("first_branch_done_join_still_waits", s == 200 and r["a"]["status"] == "DONE" and r["c"]["status"] == "TODO" and view()["instance"]["status"] == "RUNNING", {k: v["status"] for k, v in r.items()})
    s, _ = http(f"/api/todolist/{r['b']['id']}/submit", {"output": {"b_out": "CMD-1"}, "by": "운전원"})
    r = rows(); check("last_branch_fires_the_join_and_starts_the_next_task", s == 200 and r["b"]["status"] == "DONE" and r["c"]["status"] == "IN_PROGRESS", {k: v["status"] for k, v in r.items()})
    s, _ = http(f"/api/todolist/{r['c']['id']}/submit", {"output": {"c_out": "ok"}, "by": "운전원"})
    v = view(); check("instance_completes_through_the_end_event_with_both_outputs", v["instance"]["status"] == "COMPLETED" and v["instance"].get("end_event") == "end"
          and {x["key"]: x["value"] for x in v["instance"]["variables_data"]}.get("a_out") == "WO-1", {"status": v["instance"]["status"], "end": v["instance"].get("end_event")})
    report["finished"] = datetime.now(timezone.utc).isoformat(); report["definition"] = did; report["instance"] = pid
    (out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf8")
    print("checks passed", sum(c["passed"] for c in report["checks"]), "/", len(report["checks"]), flush=True)


if __name__ == "__main__":
    main()
