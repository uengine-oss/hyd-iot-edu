"""Real HTTP/PG/PLC/CMMS probe of A072: effects of a retired generation, review receipt, Incident reopen, new generation.

    .venv314/Scripts/python scripts/probe_effect_compensation.py .evidence/reaudit/a072-live-<n>

Case A: real cooler fault -> legacy bridge fills generation 0 -> human approval of the fan-only card (forecast steady
TS1 55.4 C, above the 55 C recovery limit) -> real PLC ACK -> RE_OBSERVING ->
effects API lists the command as an irreversible pending effect -> rework blocked -> review receipt -> rework admitted
with reopen -> Incident AWAITING_APPROVAL with the old command in `superseded`, approval DISCARDED -> generation 1.
Generation 1 agent tasks are filled the way A040/A042 live probes did: a labelled stand-in worker claims them through the
real PG RPC (fetch_pending_task / save_task_result), replays this case's own generation-0 outputs for the first three and
asks the real DMN MCP for a new decision with the claimed process scope (generation 1 starts at task:rank, the reworked
node; the diagnosis stays). Then a new human approval of fan-max-derate -> second PLC ACK ->
closure with a real CMMS work order. Case B: on the Supabase enterprise backend the closed case's work order is cancelled
by its exact inverse once, replayed idempotently, refused once the record moved on, and the ledger carries `compensates`.
No Codex run; no PLC counter-command. Instances are kept as evidence.

`--worker` (A156, A148 item 55): process AGENT_BRIDGE=off with host workers running (scripts/run_worker_host.sh). Both
generations' agent tasks are done by the real cliagents worker (Claude Code) instead of the legacy bridge / stand-in; the probe
checks that generation 1 task:rank carries the worker's own tool-usage events. Everything else is identical.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "it/process"), str(ROOT / "it/agent-worker"), str(ROOT / "common")]
from procsvc import procdb  # noqa: E402
from worker.context import process_scope  # noqa: E402

PROCESS, PLANT, DETECTOR, ENT = "http://127.0.0.1:8080", "http://127.0.0.1:8000", "http://127.0.0.1:8092", "http://127.0.0.1:8095"
DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
AGENT_TASKS = ("task:diagnose", "task:candidates", "task:compliance")


def http(base, path, data=None, method=None):
    req = urllib.request.Request(base + path, data=None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method=method or ("POST" if data is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"raw": body.decode(errors="replace")[:300]}


def mcp_submit(arguments):
    code = '''import asyncio,json,sys
from fastmcp import Client
async def run():
    args=json.load(sys.stdin)
    async with Client('http://127.0.0.1:8198/mcp',timeout=60) as client:
        result=await client.call_tool('submit_decision',args)
        print(next(c.text for c in result.content if c.type=='text'))
asyncio.run(run())'''
    result = subprocess.run(["docker", "exec", "-i", "hyd-iot-edu-dmn-mcp-1", "python", "-c", code],
                            input=json.dumps(arguments).encode(), capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr.decode("utf8", errors="replace")[-800:]
    return json.loads(result.stdout)


def main():
    worker = "--worker" in sys.argv[2:]
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
    consumer = "a072-standin-" + uuid.uuid4().hex[:8]
    report = {"scope": __doc__, "consumer": consumer, "worker_mode": worker, "new_codex_execution": False, "checks": {}, "instances": [],
              "started": datetime.now(timezone.utc).isoformat()}
    def save(name, value):
        (out / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf8")
    def check(name, ok, detail=None):
        report["checks"][name] = {"passed": bool(ok), "detail": detail}; save("result", report)
        print(("PASS " if ok else "FAIL ") + name + ("" if detail is None else "  " + json.dumps(detail, ensure_ascii=False, default=str)[:240]), flush=True)
        assert ok, name
    def ok(base, path, data=None, method=None):
        status, value = http(base, path, data, method); assert status in (200, 201), (path, status, value); return value
    def until(fn, timeout=240, every=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = fn()
            if value:
                return value
            time.sleep(every)
        raise TimeoutError("condition did not become true in %ss" % timeout)
    variables = lambda inst: {v["key"]: v.get("value") for v in inst.get("variables_data") or []}
    def view(pid): return ok(PROCESS, "/api/instances/" + pid)
    def latest(pid):
        rows = sorted(view(pid)["workitems"], key=lambda w: (w.get("generation") or 0, w.get("start_date") or ""))
        return {w["activity_id"]: w for w in rows}
    def incident(iid): return ok(PROCESS, "/api/incidents/" + iid)
    repo = procdb.PgRepo(DSN)
    def approve(wid, decision, option, reason, tag):
        reviewed = ok(PROCESS, f"/api/todolist/{wid}/decision-preview", {"decision": decision, "option": option, "parameters": {}})
        save(tag + "-review", reviewed)
        assert reviewed.get("id") and reviewed.get("snapshot", {}).get("options", [{}])[0].get("feasible") is True, reviewed
        return ok(PROCESS, f"/api/todolist/{wid}/select", {"decision": decision, "option": option, "by": "이생산", "role": "role:prod-mgr", "reason": reason, "review_id": reviewed["id"]})

    mode = ok(PROCESS, "/api/process/mode"); save("mode", mode)
    check("process_instance_mode_" + ("worker_bridge_off" if worker else "legacy_bridge"),
          mode["mode"] == "instance" and mode["agent_bridge"] == ("off" if worker else "legacy"), mode)
    agent_wait = 900 if worker else 180   # four real Claude Code tasks take minutes (A146: about 6 min end to end)
    ok(PLANT, "/api/reset", {}); ok(ENT, "/api/reset", {})
    det = lambda: ok(DETECTOR, "/api/detector/state")["assets"].get("HYD-01", {})
    stale = det().get("alert_id")          # an earlier case's alert may still be RAISED; this probe must attach to its own alert only
    until(lambda: det().get("phase") != "RAISED", 120); time.sleep(3)

    # ---------------------------------------------------------------- Case A
    # --worker: four real Claude Code tasks take minutes; plant-sim's default (high, health 0.43) trips ~90 s after injection and
    # the incident closes RESOLVED_WITHOUT_ACTION before any approval (first A156 run). moderate (0.55) keeps the alarm without
    # the trip — the same choice as scenario_instance_test.py (A146).
    ok(PLANT, "/api/fault", {"asset": "HYD-01", "type": "cooler_degradation", **({"severity": "moderate"} if worker else {})})
    raised = until(lambda: (lambda a: a if a.get("phase") == "RAISED" and a.get("alert_id") and a.get("alert_id") != stale else None)(det()), 200)
    alert_id = raised["alert_id"]
    inst = until(lambda: next((i for i in ok(PROCESS, "/api/instances?limit=30") if variables(i).get("alert_id") == alert_id), None), 60)
    pid = inst["proc_inst_id"]; report["instances"].append(pid); save("result", report)
    inc_id = variables(inst)["incident"]
    until(lambda: latest(pid).get("task:select", {}).get("status") == "IN_PROGRESS", agent_wait)
    g0 = latest(pid); sel = g0["task:select"]; dec_id = variables(view(pid)["instance"])["decision_id"]
    save("a-g0-view", view(pid)); save("a-decision-first", ok(PROCESS, "/api/decisions/" + dec_id))
    r = approve(sel["id"], dec_id, "skill:fan-max", "[회귀 검사] A072 첫 판단: 팬만 올림(OEM 오더는 전부하 유지)", "a-g0")
    check("a_first_approval_accepted", "instance" in r)
    inc = until(lambda: (lambda i: i if i["state"] == "RE_OBSERVING" else None)(incident(inc_id)), 90)
    first_cmd = inc["cmdId"]; save("a-incident-after-ack", inc)
    check("a_plc_ack_and_reobserving", (inc.get("ack") or {}).get("result") == "DONE" and bool(first_cmd), {"cmd": first_cmd})
    effects = ok(PROCESS, f"/api/instances/{pid}/effects"); save("a-effects-before", effects)
    plc = next((e for e in effects["effects"] if e["kind"] == "plc"), None)
    check("a_effects_show_plc_command_irreversible_pending",
          plc is not None and plc["cmdId"] == first_cmd and not plc["reversible"] and effects["resolution"]["pending"] == [plc["id"]] and effects["reopen_required"],
          {"effects": [e["id"] for e in effects["effects"]], "pending": effects["resolution"]["pending"]})
    rank = g0["task:rank"]
    preview = ok(PROCESS, f"/api/instances/{pid}/rework-preview?workitem_id={rank['id']}"); save("a-preview-blocked", preview)
    check("a_rework_blocked_until_effects_reviewed", not preview["execution_available"] and any(b["code"] == "effects_require_compensation_or_review" for b in preview["blockers"]),
          [b["code"] for b in preview["blockers"]])
    status, body = http(PROCESS, f"/api/instances/{pid}/effects/review", {"request_id": str(uuid.uuid4()), "by": "김운전", "role": "role:operator", "reason": "x", "effects": [plc["id"]]})
    check("a_review_below_approving_role_refused_403", status == 403, body)
    status, body = http(PROCESS, f"/api/instances/{pid}/effects/compensate", {"request_id": str(uuid.uuid4()), "by": "이생산", "role": "role:prod-mgr", "reason": "x"})
    check("a_nothing_reversible_to_compensate_409", status == 409, body)
    review_body = {"request_id": str(uuid.uuid4()), "by": "이생산", "role": "role:prod-mgr",
                   "reason": "[회귀 검사] 현장에서 팬 100% 확인, 유온이 아직 56 ℃ 근처 — 팬만으로는 부족해 새 판단 필요", "effects": [plc["id"]]}
    receipt = ok(PROCESS, f"/api/instances/{pid}/effects/review", review_body); save("a-review-receipt", receipt)
    replay = ok(PROCESS, f"/api/instances/{pid}/effects/review", review_body)
    check("a_review_recorded_and_replayed_identically", receipt["status"] == "RECORDED" and replay == receipt and receipt["history"][0]["incident"]["cmdId"] == first_cmd)
    effects = ok(PROCESS, f"/api/instances/{pid}/effects"); save("a-effects-after-review", effects)
    check("a_effects_resolved_after_review", effects["resolution"]["pending"] == [] and effects["resolution"]["acknowledged"] == [plc["id"]])
    preview = ok(PROCESS, f"/api/instances/{pid}/rework-preview?workitem_id={rank['id']}"); save("a-preview-admitted", preview)
    check("a_rework_admitted_with_reopen", preview["execution_available"] and preview.get("reopen_incident") is True and sel["id"] in preview["retire_approvals"],
          {"blockers": preview["blockers"], "retire": preview["retire_approvals"]})
    rw = {"workitem_id": rank["id"], "request_id": str(uuid.uuid4()), "snapshot_token": preview["snapshot_token"], "by": "이생산", "role": "role:prod-mgr",
          "reason": "[회귀 검사] A072 설비 상태 확인 뒤 새 판단"}
    result = ok(PROCESS, f"/api/instances/{pid}/rework", rw); save("a-rework-receipt", result)
    inc = incident(inc_id); save("a-incident-reopened", inc)
    approval = next(a for a in view(pid)["approvals"] if a["todo_id"] == sel["id"])
    check("a_incident_reopened_old_command_superseded_approval_discarded",
          result["generation"] == 1 and inc["state"] == "AWAITING_APPROVAL" and inc["cmdId"] is None and inc["superseded"][-1]["cmdId"] == first_cmd
          and inc["superseded"][-1]["state_before"] == "RE_OBSERVING" and approval["status"] == "DISCARDED" and approval["history"][-1]["via"] == "rework",
          {"generation": result["generation"], "state": inc["state"], "superseded": inc["superseded"][-1]["cmdId"]})
    # generation 1 agent tasks: stand-in worker over the real PG RPC; legacy bridge must not touch them
    check("a_generation1_starts_at_rank_diagnosis_kept", all(latest(pid)[aid]["status"] == "DONE" and (latest(pid)[aid].get("generation") or 0) == 0 for aid in AGENT_TASKS))
    until(lambda: (lambda w: w.get("status") == "IN_PROGRESS" and (w.get("generation") or 0) == 1)(latest(pid).get("task:rank", {})), 120)
    def cleared_branch():
        # --worker, moderate fault: generation 0's fan command is still on the plant, so the alarm can clear while the real
        # worker is still judging generation 1 — before or after task:select opens. That ending is a contract, not a skip
        # (A156 fix in instances._command_never_issued): the reopened Incident is RESOLVED_WITHOUT_ACTION and the instance
        # follows it — generation 1's open tasks cancelled, task:escalate reached by abort — while the retired command and the
        # effect review stay on record.
            snap = incident(inc_id); save("a-incident-cleared", snap)
            def g1(): return {w["activity_id"]: w for w in view(pid)["workitems"] if (w.get("generation") or 0) == 1}
            rows1 = until(lambda: (lambda r: r if "reached by abort" in (r.get("task:escalate", {}).get("log") or "") else None)(g1()), 120, 2)
            save("a-g1-cleared-view", view(pid))
            effects = ok(PROCESS, f"/api/instances/{pid}/effects"); save("a-effects-cleared", effects)
            check("a_cleared_branch_instance_follows_incident_abort",
                  rows1["task:select"]["status"] == "CANCELLED" and "before any action" in (rows1["task:select"].get("log") or "")
                  and not any(w["status"] == "IN_PROGRESS" and k != "task:escalate" for k, w in rows1.items())
                  and rows1.get("task:command", {}).get("status") == "CANCELLED",
                  {k: (w["status"], (w.get("log") or "")[:60]) for k, w in rows1.items()})
            check("a_cleared_branch_history_kept", snap["superseded"][-1]["cmdId"] == first_cmd and snap.get("cmdId") is None
                  and any(r.get("kind") == "review" and plc["id"] in json.dumps(r) for r in view(pid).get("effects", [])),
                  {"superseded": [x["cmdId"] for x in snap["superseded"]], "view_effects": [r.get("kind") for r in view(pid).get("effects", [])]})
            # /effects lists what is still outstanding for the current generation (the retired command left it, by design);
            # the review receipt itself is kept on the instance record — the same place the approval path checks (kinds == ["review"]).
            report["branch"] = "alarm cleared during generation 1 (moderate fault); case B (work-order inverse) not exercised"
            report["finished"] = datetime.now(timezone.utc).isoformat(); save("result", report)
            print(f"ALL PASS: {len(report['checks'])} checks — {report['branch']}", flush=True)
            return True
    if worker:
        reached = until(lambda: ("select" if (lambda w: w.get("status") == "IN_PROGRESS" and (w.get("generation") or 0) == 1)(latest(pid).get("task:select", {}))
                                 else "cleared" if incident(inc_id)["state"] == "RESOLVED_WITHOUT_ACTION" else None), agent_wait, 3)
        if reached == "cleared":
            return cleared_branch()
        rank1 = latest(pid)["task:rank"]
        with repo._conn() as c:
            ev = c.execute("select event_type, crew_type, count(*) as n from events where todo_id = %s group by 1, 2", (str(rank1["id"]),)).fetchall()
        save("a-g1-rank-events", ev)
        tool_runs = sum(r["n"] for r in ev if r["event_type"] == "tool_usage_started" and str(r["crew_type"]).startswith("cliagents:"))
        doc = {"id": (rank1.get("output") or {}).get("decision_id")}
        check("a_g1_rank_done_by_real_worker_with_tool_calls", rank1["status"] == "DONE" and (rank1.get("generation") or 0) == 1
              and tool_runs > 0 and doc["id"] and doc["id"] != dec_id, {"tool_usage_started": tool_runs, "decision": doc["id"]})
    else:
        row, = repo.fetch_pending_task("cliagents", consumer, tenant_id="hyd", proc_inst_id=pid)
        assert row["activity_id"] == "task:rank" and row["generation"] == 1, row
        values = variables(view(pid)["instance"])
        arguments = {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "cause": values["cause"], "failure_mode": values["failure_mode"],
                     "incident": inc_id, "alert_id": alert_id, "process_scope": process_scope(row)}
        save("a-g1-claim-rank", row); save("a-g1-mcp-request", arguments)
        mcp = mcp_submit(arguments); save("a-g1-mcp-response", mcp)
        check("a_g1_real_dmn_mcp_new_decision", mcp["result"] == "ok" and mcp["document"]["status"] == "SUBMITTED" and mcp["document"]["id"] != dec_id, {"decision": mcp["document"]["id"]})
        doc = mcp["document"]
        output = {"decision_id": doc["id"], "decision": {"recommended": doc["recommended"], "explanation": doc["explanation"], "order": doc["cards"]}}
        assert repo.save_task_result(row["id"], output, True, expected_consumer=consumer)
        until(lambda: (lambda w: w.get("status") == "IN_PROGRESS" and (w.get("generation") or 0) == 1)(latest(pid).get("task:select", {})), 120)
    sel2 = latest(pid)["task:select"]; dec2 = variables(view(pid)["instance"])["decision_id"]
    save("a-g1-view", view(pid)); save("a-decision-second", ok(PROCESS, "/api/decisions/" + dec2))
    check("a_new_generation_reached_new_selection_with_new_decision", sel2["id"] != sel["id"] and dec2 == doc["id"] and dec2 != dec_id, {"decision": dec2})
    status, body = http(PROCESS, f"/api/todolist/{sel2['id']}/select", {"decision": dec_id, "option": "skill:fan-max-derate", "by": "이생산", "role": "role:prod-mgr", "reason": "[회귀 검사] 지난 판단으로 승인 시도"})
    check("a_old_decision_refused_for_new_generation", status in (400, 409), body)
    try:
        approve(sel2["id"], dec2, "skill:fan-max-derate", "[회귀 검사] A072 두 번째 판단: 팬 최대와 부하 저감", "a-g1")
    except AssertionError:
        if not (worker and incident(inc_id)["state"] == "RESOLVED_WITHOUT_ACTION"):
            raise
        return cleared_branch()
    report["branch"] = "generation 1 approved and executed"
    inc = until(lambda: (lambda i: i if i.get("cmdId") and (i.get("ack") or {}).get("result") == "DONE" else None)(incident(inc_id)), 90)
    check("a_second_command_issued_and_acknowledged", inc["cmdId"] != first_cmd and inc["state"] in ("ACKED", "RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED", "CLOSED"), {"cmd": inc["cmdId"], "state": inc["state"]})
    fin = until(lambda: (lambda v: v if v["instance"]["status"] == "COMPLETED" else None)(view(pid)), 480); save("a-final-view", fin)
    inc = incident(inc_id); save("a-incident-final", inc)
    wo = inc.get("workOrder") or {}; wo_ref = wo.get("ref") or wo.get("id")
    check("a_closed_with_real_cmms_work_order_and_one_superseded_command",
          fin["instance"]["end_event"] == "ev:closed" and fin["instance"]["rework_generation"] == 1 and inc["state"] == "CLOSED" and bool(wo_ref)
          and len(inc["superseded"]) == 1 and [r["kind"] for r in fin.get("effects", [])] == ["review"],
          {"wo": wo_ref, "end": fin["instance"]["end_event"]})
    rows = {w["id"]: w["status"] for w in fin["workitems"]}
    graph = until(lambda: (lambda g: g if {w["id"]: w["status"] for w in g["graph"]["workitems"]} == rows else None)(ok(PROCESS, f"/api/instances/{pid}/graph")), 90, 2)
    save("a-graph", graph)   # the Execution projection is applied by the outbox after the rows commit; wait for convergence, do not read once
    check("a_graph_matches_rows", {w["id"]: w["status"] for w in graph["graph"]["workitems"]} == rows)
    effects = ok(PROCESS, f"/api/instances/{pid}/effects"); save("a-effects-final", effects)

    # ---------------------------------------------------------------- Case B: exact inverse on the real enterprise backend
    ledger = ok(ENT, "/api/transactions"); save("b-ledger-before", ledger)
    wo_tx = next((t for t in ledger if t.get("ref") == wo_ref and t.get("skill") == "skill:schedule-maintenance"), None)
    check("b_work_order_in_enterprise_ledger", wo_tx is not None, {"ledger": [(t.get("skill"), t.get("ref")) for t in ledger[:6]]})
    undo_req = {"decision": wo_tx["decision"], "skill": "skill:cancel-work-order", "asset": "HYD-01", "by": "이생산", "params": {"ref": wo_ref}, "compensates": wo_tx["id"]}
    undo = ok(ENT, "/api/exec", undo_req); save("b-undo", undo)
    again = ok(ENT, "/api/exec", undo_req)
    state = ok(ENT, "/api/state"); save("b-state", state)
    row = next((w for w in state["cmms"]["work_orders"] if w["id"] == wo_ref), None)
    check("b_cancel_is_exact_and_idempotent", undo["ref"] == wo_ref and undo.get("compensates") == wo_tx["id"] and again["id"] == undo["id"]
          and row is not None and row["status"] == "취소", {"row": row})
    status, body = http(ENT, "/api/exec", dict(undo_req, decision=str(wo_tx["decision"]) + "-other"))
    check("b_second_cancel_refused_record_moved_on", status in (400, 409) and "cannot be cancelled" in json.dumps(body, ensure_ascii=False), body)
    ledger = ok(ENT, "/api/transactions"); save("b-ledger-after", ledger)
    check("b_ledger_carries_compensates", any(t.get("compensates") == wo_tx["id"] and t.get("skill") == "skill:cancel-work-order" for t in ledger))
    report["finished"] = datetime.now(timezone.utc).isoformat(); save("result", report)
    print(f"ALL PASS: {len(report['checks'])} checks", flush=True)


if __name__ == "__main__":
    main()
