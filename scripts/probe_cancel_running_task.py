"""A097 — a person cancels a RUNNING agent task; the worker stops within its check interval and releases the claim.

    .venv314/Scripts/python scripts/probe_cancel_running_task.py .evidence/reaudit/a097-cancel-<n>

Live: process :8080, at least one host worker, Claude Code logged in. Uploads HM-9, starts the real extraction, posts
/api/todolist/{id}/cancel, and records how long until the worker gives the claim back (consumer null, task_cancelled event
from the agent side), that a late result is impossible, and that the person can then close the row.

Two legitimate paths (A134): the first cancel is sent the moment the instance exists, before any sleep. If the worker has
not claimed yet the engine must refuse it (409) and the probe then waits for the claim and cancels a second time (200). If
the worker already claimed in that window the first cancel *is* the 200 path, and the "refused before a claim" check is
recorded as skipped (not a failure) — the worker is never paused or slowed to force one path.
"""
import base64
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request

import psycopg

PROCESS = "http://127.0.0.1:8080"
DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/manuals/HM-9_oil-degradation-manual.md"


def http(path, data=None):
    req = urllib.request.Request(PROCESS + path, data=None if data is None else json.dumps(data, ensure_ascii=False).encode(), headers={"Content-Type": "application/json"},
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def row(cur, wid):
    cur.execute("select consumer, draft_status, status, claim_count, log from todolist where id=%s", (wid,))
    r = cur.fetchone(); return dict(consumer=r[0], draft_status=r[1], status=r[2], claim_count=r[3], log=r[4])


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
    report = {"started": datetime.now(timezone.utc).isoformat(), "checks": []}
    def check(name, ok, detail=None):
        report["checks"].append({"name": name, "status": "passed" if ok else "failed", "passed": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name, json.dumps(detail, ensure_ascii=False, default=str)[:220] if detail is not None else "", flush=True)
    def skip(name, reason, detail=None):
        report["checks"].append({"name": name, "status": "skipped", "passed": None, "reason": reason, "detail": detail})
        print("SKIP " + name, reason, json.dumps(detail, ensure_ascii=False, default=str)[:220] if detail is not None else "", flush=True)
    _, up = http("/api/kg/manuals/preview", {"filename": FIXTURE.name, "data": base64.b64encode(FIXTURE.read_bytes()).decode()})
    root = "/api/kg/manuals/sources/" + up["source_id"]
    with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
        _, inst = http(root + "/extractions", {"request_id": str(uuid.uuid4())}); pid = inst["instance"]
        # one round trip: the row id and its state, then the cancel goes out at once (no sleep — the worker may still win)
        cur.execute("select id, consumer, draft_status from todolist where proc_inst_id=%s and activity_id='task:extract-manual'", (pid,))
        wid, c0, d0 = cur.fetchone(); wid = str(wid)
        before_claim = d0 != "STARTED" and c0 is None
        s, first = http(f"/api/todolist/{wid}/cancel", {"by": "운전원", "reason": "[회귀 검사] 아직 시작 전"})
        report["first_cancel"] = {"row_before": {"consumer": c0, "draft_status": d0}, "status": s, "body": first}
        if s == 409:
            report["path"] = "before_claim"
            check("cancel_before_a_worker_claims_is_refused_409", True, {"status": s, "body": first, "row_before": {"consumer": c0, "draft_status": d0}})
            t0 = time.monotonic()
            while time.monotonic() - t0 < 120 and row(cur, wid)["draft_status"] != "STARTED":
                time.sleep(1)
            r = row(cur, wid); check("worker_claimed", r["draft_status"] == "STARTED" and r["consumer"], r)
            time.sleep(15)                                                       # the CLI is really running
            t1 = time.monotonic(); s, res = http(f"/api/todolist/{wid}/cancel", {"by": "운전원", "reason": "[회귀 검사] 잘못된 문서를 올렸다"})
        elif s == 200:
            report["path"] = "after_claim"
            skip("cancel_before_a_worker_claims_is_refused_409",
                 "worker claimed the row between instance creation and the first cancel; the 200 is the legitimate running-task path"
                 if before_claim else "worker had already claimed the row when its state was read; no pre-claim window existed",
                 {"status": s, "body": first, "row_before": {"consumer": c0, "draft_status": d0}})
            # the engine only answers 200 when draft_status was STARTED with a consumer; the body carries that consumer
            check("worker_claimed", bool(first.get("consumer")) and first.get("draft_status") == "CANCELLED", first)
            t1 = time.monotonic(); res = first
        else:
            report["path"] = "unexpected"
            check("cancel_before_a_worker_claims_is_refused_409", False, {"status": s, "body": first, "row_before": {"consumer": c0, "draft_status": d0}})
            r = row(cur, wid); check("worker_claimed", r["draft_status"] == "STARTED" and r["consumer"], r)
            t1 = time.monotonic(); res = first
        check("cancel_accepted_200_with_cancelled_mark", s == 200 and res.get("draft_status") == "CANCELLED", {"status": s, "body": res})
        while time.monotonic() - t1 < 60 and row(cur, wid)["consumer"] is not None:
            time.sleep(0.5)
        released = round(time.monotonic() - t1, 1); r2 = row(cur, wid)
        check("worker_released_the_claim_within_its_check_interval", r2["consumer"] is None and r2["draft_status"] == "CANCELLED", {"released_after_s": released, "row": r2})
        cur.execute("select job_id, crew_type, event_type from events where todo_id=%s order by timestamp", (wid,))
        ev = [list(x) for x in cur.fetchall()]
        check("both_the_persons_request_and_the_workers_stop_are_recorded", any(e[0] == "TASK_CANCEL_REQUESTED" for e in ev) and any(e[2] == "task_cancelled" and e[1] != "human" for e in ev), ev[-6:])
        s, again = http(f"/api/todolist/{wid}/cancel", {"by": "운전원", "reason": "[회귀 검사] 다시"})
        check("second_cancel_is_refused", s == 409, {"status": s})
        s, nothing = http(root + "/extractions/" + pid)
        check("extraction_result_reports_the_cancelled_run_without_a_preview", s == 200 and nothing.get("preview") is None and nothing["status"] == "IN_PROGRESS", {"status": nothing.get("status")})
        s, closed = http(f"/api/todolist/{wid}/close", {"by": "운전원", "reason": "[회귀 검사] 취소 뒤 닫음"})
        check("person_closes_the_cancelled_row", s == 200 and closed.get("status") == "CANCELLED", {"status": s, "body": closed})
    report["finished"] = datetime.now(timezone.utc).isoformat()
    executed = [c for c in report["checks"] if c["status"] != "skipped"]
    report["summary"] = {"path": report.get("path"), "executed": len(executed), "passed": sum(c["passed"] for c in executed),
                         "skipped": [c["name"] for c in report["checks"] if c["status"] == "skipped"], "all_executed_passed": all(c["passed"] for c in executed)}
    (out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf8")
    if report["summary"]["skipped"]:
        print("checks skipped", len(report["summary"]["skipped"]), report["summary"]["skipped"], flush=True)
    print("checks passed", report["summary"]["passed"], "/", len(executed), flush=True)
    sys.exit(0 if report["summary"]["all_executed_passed"] else 1)


if __name__ == "__main__":
    main()
