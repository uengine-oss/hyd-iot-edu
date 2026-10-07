"""A097 — orphan recovery measured live: a worker dies mid-run, its lease expires, another worker reclaims the row.

    .venv314/Scripts/python scripts/probe_worker_lease.py .evidence/reaudit/a097-lease-<n>

Preconditions: process (instance mode) on :8080, two host workers (8097 agent-worker:host, 8098 agent-worker:host2),
the Claude Code CLI logged in. The probe uploads the small HM-9 manual, starts the real extraction, waits until a worker
has claimed it (draft STARTED + consumer), kills that worker's python process (the way a crash would), then records what
the DB does: lease_until passes, the other worker reclaims (claim_count 2, log "[Lease expired: reclaimed by …]"), the
run completes and the result is accepted. Expectations are written before the run; failing one is a measured defect.
"""
import base64
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

import psycopg

PROCESS = "http://127.0.0.1:8080"
DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/manuals/HM-9_oil-degradation-manual.md"


def http(path, data=None):
    req = urllib.request.Request(PROCESS + path, data=None if data is None else json.dumps(data).encode(), headers={"Content-Type": "application/json"},
                                 method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def row(cur, pid):
    cur.execute("select id, consumer, draft_status, status, lease_until, claim_count, log from todolist where proc_inst_id=%s and activity_id='task:extract-manual' order by start_date desc limit 1", (pid,))
    r = cur.fetchone()
    return dict(id=str(r[0]), consumer=r[1], draft_status=r[2], status=r[3], lease_until=r[4].isoformat() if r[4] else None, claim_count=r[5], log=r[6]) if r else None


def worker_pids():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*worker.main*' } | ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId)\" }"],
                         capture_output=True, text=True).stdout.split()
    pairs = [tuple(map(int, out[i:i + 2])) for i in range(0, len(out) - 1, 2)]
    return pairs


def consumer_port(consumer):
    return 8098 if consumer.startswith("agent-worker:host2") else 8097


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
    report = {"started": datetime.now(timezone.utc).isoformat(), "steps": [], "checks": []}
    def step(name, **kw):
        kw["t"] = datetime.now().strftime("%H:%M:%S"); report["steps"].append({"step": name, **kw}); print(name, json.dumps(kw, ensure_ascii=False, default=str)[:300], flush=True)
    def check(name, ok, detail=None):
        report["checks"].append({"name": name, "passed": bool(ok), "detail": detail}); print(("PASS " if ok else "FAIL ") + name, json.dumps(detail, ensure_ascii=False, default=str)[:200] if detail is not None else "", flush=True)
    up = http("/api/kg/manuals/preview", {"filename": FIXTURE.name, "data": base64.b64encode(FIXTURE.read_bytes()).decode()})
    sid = up["source_id"]; root = "/api/kg/manuals/sources/" + sid
    inst = http(root + "/extractions", {"request_id": str(uuid.uuid4())}); pid = inst["instance"]
    step("started", instance=pid)
    with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
        t0 = time.monotonic(); r = None
        while time.monotonic() - t0 < 120:
            r = row(cur, pid)
            if r and r["draft_status"] == "STARTED" and r["consumer"]:
                break
            time.sleep(1)
        check("a_worker_claimed_the_task_with_a_lease", bool(r and r["draft_status"] == "STARTED" and r["lease_until"] and r["claim_count"] == 1), r)
        victim = r["consumer"]; port = consumer_port(victim)
        time.sleep(20)                                                           # let the CLI really start (events flowing)
        r_before = row(cur, pid)
        # kill the claiming worker's python processes (parent wrapper + child), the way a crash or power loss would
        killed = []
        try:
            health = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5).read())
        except Exception as e:  # noqa: BLE001
            health = {"error": str(e)}
        # the consumer name maps to a health port (run_worker_host.sh); the process listening there and its wrapper are the victim
        ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                             f"(Get-NetTCPConnection -LocalPort {port} -State Listen | Select-Object -First 1).OwningProcess"], capture_output=True, text=True).stdout.strip()
        if ps:
            owner = int(ps)
            tree = [owner] + [p for p, parent in worker_pids() if parent == owner] + [parent for p, parent in worker_pids() if p == owner]
            for p in sorted(set(tree)):
                res = subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True, text=True, encoding="cp949", errors="replace")   # Korean console output
                killed.append((p, res.returncode))
        step("killed_victim_worker", consumer=victim, port=port, killed=killed, health_before=health, row=r_before)
        time.sleep(3)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3); alive = True
        except Exception:  # noqa: BLE001
            alive = False
        check("victim_worker_is_really_dead", not alive, {"port": port})
        r_dead = row(cur, pid)
        check("row_still_claimed_by_the_dead_worker_until_the_lease_expires", r_dead["consumer"] == victim and r_dead["draft_status"] == "STARTED", r_dead)
        # wait for the other worker to reclaim (lease 120 s + poll interval)
        t1 = time.monotonic(); r2 = None
        while time.monotonic() - t1 < 240:
            r2 = row(cur, pid)
            if r2["claim_count"] >= 2 or r2["draft_status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(3)
        waited = round(time.monotonic() - t1, 1)
        check("other_worker_reclaimed_after_lease_expiry", r2["claim_count"] == 2 and r2["consumer"] and r2["consumer"] != victim and "[Lease expired: reclaimed by" in (r2["log"] or ""),
              {"waited_s": waited, "row": r2})
        # wait for completion
        t2 = time.monotonic(); res = None
        while time.monotonic() - t2 < 900:
            res = http(root + "/extractions/" + pid)
            if res["status"] in ("DONE", "FAILED", "CANCELLED", "PENDING") and (res.get("preview") or res["status"] != "DONE"):
                break
            time.sleep(5)
        final = row(cur, pid)
        check("reclaimed_run_completed_and_result_accepted", res["status"] == "DONE" and bool(res.get("preview")) and final["draft_status"] == "COMPLETED", {"status": res["status"], "elapsed_s": round(time.monotonic() - t2, 1), "row": final})
        check("no_duplicate_result_or_late_submission_from_the_dead_worker", final["claim_count"] == 2 and final["consumer"] is None, final)
    report["finished"] = datetime.now(timezone.utc).isoformat()
    (out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf8")
    print("checks passed", sum(c["passed"] for c in report["checks"]), "/", len(report["checks"]), flush=True)


if __name__ == "__main__":
    main()
