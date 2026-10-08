"""Follow one live anomaly_response instance whose agent tasks a real cliagents worker performs, and finish the human part.

    .venv314/Scripts/python scripts/probe_worker_follow.py <proc_inst_id> <out_dir>

Used when the cooler regression harness died after the alert had already opened the instance (A072 run 4: a process
container restart delayed the instance past the harness's 31 s wait). It does not create anything new: it waits for the
four agent tasks to be DONE by the worker (consumer recorded on each row, events carry the CLI session), approves the
recommended card through the fresh decision review as the production manager, then waits for PLC ACK, re-observation,
the real CMMS work order and ev:closed. Every state is saved; nothing is forced.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

PROCESS = "http://127.0.0.1:8080"
AGENT_TASKS = ("task:diagnose", "task:candidates", "task:compliance", "task:rank")


def http(path, data=None):
    req = urllib.request.Request(PROCESS + path, data=None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"raw": body.decode(errors="replace")[:300]}


def main():
    pid, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    report = {"instance": pid, "started": datetime.now(timezone.utc).isoformat(), "checks": {}, "scope": __doc__}
    def save(name, value): (out / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf8")
    def check(name, ok, detail=None):
        report["checks"][name] = {"passed": bool(ok), "detail": detail}; save("follow-result", report)
        print(("PASS " if ok else "FAIL ") + name + ("" if detail is None else "  " + json.dumps(detail, ensure_ascii=False, default=str)[:260]), flush=True)
        assert ok, name
    def ok(path, data=None):
        s, v = http(path, data); assert s in (200, 201), (path, s, v); return v
    def until(fn, timeout, every=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            v = fn()
            if v:
                return v
            time.sleep(every)
        raise TimeoutError(f"not reached in {timeout}s")
    view = lambda: ok("/api/instances/" + pid)
    items = lambda: {w["activity_id"]: w for w in view()["workitems"]}
    variables = lambda inst: {v["key"]: v.get("value") for v in inst.get("variables_data") or []}
    mode = ok("/api/process/mode"); save("mode", mode)
    check("worker_mode_bridge_off", mode["agent_bridge"] == "off", {"time_scale": mode["time_scale"]})
    inc_id = variables(view()["instance"])["incident"]
    t0 = time.monotonic()
    tl = until(lambda: (lambda w: w if w.get("task:select", {}).get("status") == "IN_PROGRESS" else None)(items()), 2400, 10)
    agent_rows = {a: tl[a] for a in AGENT_TASKS}; save("agent-rows", agent_rows)
    # a DONE row no longer carries its consumer (the claim is released on completion); the worker identity is in the events
    check("four_agent_tasks_done", all(r["status"] == "DONE" for r in agent_rows.values()),
          {"minutes_waited_here": round((time.monotonic() - t0) / 60, 1), "outputs": {a: sorted((r.get("output") or {}).keys())[:6] for a, r in agent_rows.items()}})
    events = ok(f"/api/events?proc_inst_id={pid}&limit=500"); save("events", events)
    rows = events if isinstance(events, list) else events.get("items") or events.get("events") or []
    kinds = sorted({str(e.get("event_type")) for e in rows})
    tool_events = [e for e in rows if "tool" in str(e.get("event_type"))]
    crews = sorted({str(e.get("crew_type")) for e in rows})
    check("worker_events_carry_tool_usage", bool(tool_events) and any("cliagents" in c or "claude" in c for c in crews), {"event_types": kinds[:12], "tool_events": len(tool_events), "crews": crews})
    sel = tl["task:select"]; dec_id = variables(view()["instance"])["decision_id"]
    decision = ok("/api/decisions/" + dec_id); save("decision", decision)
    check("decision_from_worker_run_has_cards", decision.get("recommended") and len(decision.get("options") or []) >= 2, {"recommended": decision.get("recommended")})
    option = decision["recommended"]
    reviewed = ok(f"/api/todolist/{sel['id']}/decision-preview", {"decision": dec_id, "option": option, "parameters": {}}); save("review", reviewed)
    assert reviewed.get("id"), reviewed
    r = ok(f"/api/todolist/{sel['id']}/select", {"decision": dec_id, "option": option, "by": "이생산", "role": "role:prod-mgr",
                                                  "reason": "[회귀 검사] A072 4회차(1배속, 실제 Claude Code 워커): 새로 검토한 뒤 추천 카드 승인", "review_id": reviewed["id"]})
    save("select", r); check("human_approval_accepted", "instance" in r, {"approval_status": r.get("approval_status")})
    inc = until(lambda: (lambda i: i if i.get("cmdId") and (i.get("ack") or {}).get("result") == "DONE" else None)(ok("/api/incidents/" + inc_id)), 120)
    save("incident-acked", inc); check("plc_ack_done", inc["state"] in ("ACKED", "RE_OBSERVING"), {"cmd": inc["cmdId"], "state": inc["state"]})
    fin = until(lambda: (lambda v: v if v["instance"]["status"] == "COMPLETED" else None)(view()), 2400, 10); save("final-view", fin)
    inc = ok("/api/incidents/" + inc_id); save("incident-final", inc)
    wo = (inc.get("workOrder") or {}); check("closed_with_real_cmms_work_order", fin["instance"]["end_event"] == "ev:closed" and inc["state"] == "CLOSED" and bool(wo.get("ref") or wo.get("id")),
                                            {"end": fin["instance"]["end_event"], "incident": inc["state"], "wo": wo.get("ref") or wo.get("id")})
    graph = until(lambda: (lambda g: g if {w["id"]: w["status"] for w in g["graph"]["workitems"]} == {w["id"]: w["status"] for w in fin["workitems"]} else None)(ok(f"/api/instances/{pid}/graph")), 90, 2)
    save("graph", graph); check("graph_matches_rows", True)
    report["finished"] = datetime.now(timezone.utc).isoformat(); save("follow-result", report)
    print(f"ALL PASS: {len(report['checks'])} checks", flush=True)


if __name__ == "__main__":
    main()
