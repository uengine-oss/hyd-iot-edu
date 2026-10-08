"""A102 — one command runs the live regression probes in the right mode and writes one results table.

    .venv314/Scripts/python scripts/run_regression.py --group core   --out .evidence/reaudit/reg-<tag> [--kill-workers] [--restart-workers 2]
    .venv314/Scripts/python scripts/run_regression.py --group worker --out .evidence/reaudit/reg-<tag>
    .venv314/Scripts/python scripts/run_regression.py --group all    --out .evidence/reaudit/reg-<tag> --kill-workers --restart-workers 2

Groups (each probe keeps its own evidence folder under --out):
  core   — real stack at TIME_SCALE=20 with the legacy agent bridge; **host workers must be stopped** (they would claim the
           bridge's agent tasks — A085/A090 incident). cooler 42 · effect compensation · work-order-only · DDL drift · SCM ·
           time anchors · evidence coverage · knowledge→judgment · expert answers · parallel join · semantic audit · schema validate.
  worker — probes that need the host workers (Claude Code): rule/business/time-series questions, manual ingestion (HM-9),
           worker lease (needs 2 workers), running-task cancel.
The runner only checks and reports preconditions; with --kill-workers it stops the host workers before `core` and with
--restart-workers N it starts N of them afterwards (run_worker_host.sh). A probe is PASS only when its own pass line says
every check passed and it exited 0 — nothing is inferred.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Windows lecturer PC: .venv314 (CLAUDE.md §5); Linux (cloud): .venv; PYTHON overrides both.
WINDOWS = os.name == "nt"
PY = os.environ.get("PYTHON") or str(ROOT / (".venv314/Scripts/python.exe" if WINDOWS else ".venv/bin/python"))
NEO4J = "bolt://127.0.0.1:7687"
PASS_PATTERNS = [r"ALL PASS[^\d\n]*(\d+)\s*/\s*(\d+)", r"ALL PASS:\s*(\d+) checks", r"checks passed\s*(\d+)\s*/\s*(\d+)",
                 r"golden questions passed\s*(\d+)/(\d+)", r"^ALL PASS\s*$", r"^PASS$"]
FAIL_PATTERNS = [r"^FAILED:", r"^FAIL ", r"\[FAIL\]", r"Traceback \(most recent call last\)"]

PROBES = {
    "core": [
        ("cooler-42", "scripts/run_scenario_evidence.py", ["--fresh-review", "--out", "{out}"], 1800, "scenario.log"),
        ("pump-fan", "scripts/run_scenario_pump_fan_evidence.py", ["--out", "{out}"], 1500, None),   # A120: pump · fan instances end to end
        ("effect-compensation", "scripts/probe_effect_compensation.py", ["{out}"], 1500, None),
        ("work-order-only", "scripts/probe_work_order_only_card.py", ["--out", "{out}"], 900, None),
        ("ddl-drift", "scripts/probe_ddl_drift.py", ["--out", "{out}"], 300, None),
        ("scm-sync", "scripts/probe_scm_sync.py", ["--out", "{out}"], 300, None),
        ("time-anchors", "scripts/probe_time_anchors.py", ["{out}"], 300, None),
        ("evidence-coverage", "scripts/probe_evidence_coverage.py", ["{out}"], 600, None),
        ("knowledge-to-judgment", "scripts/probe_knowledge_to_judgment.py", ["{out}"], 600, None),
        ("parallel-join", "scripts/probe_parallel_join.py", ["{out}"], 300, None),
        ("schema-validate", "scripts/ontology_v2.py", ["validate", "--uri", NEO4J], 300, None),
    ],
    "worker": [
        ("rule-questions", "scripts/probe_rule_questions.py", ["--out", "{out}"], 1800, None),
        ("business-questions", "scripts/probe_business_questions.py", ["--out", "{out}"], 1800, None),
        ("timeseries-questions", "scripts/probe_timeseries_questions.py", ["--out", "{out}"], 1800, None),
        # A157: the HM-9 extraction is an agent task only a host worker picks up (core runs with the workers stopped — it timed out there)
        ("expert-answers", "scripts/probe_expert_answers_a098.py", ["{out}"], 900, None),
        ("ingest-hm9", "scripts/probe_ingest_quality.py", ["{out}", "tests/fixtures/manuals/HM-9_oil-degradation-manual.md"], 1800, None),
        # A157: Q03 needs fm:oil-degradation remedied, which only the HM-9 ingestion above commits (seed alone leaves it open)
        ("semantic-audit", "scripts/probe_semantic_links.py", ["--out", "{out}", "--uri", NEO4J], 300, None),
        ("worker-lease", "scripts/probe_worker_lease.py", ["{out}"], 1200, None),
        ("cancel-running", "scripts/probe_cancel_running_task.py", ["{out}"], 900, None),
    ],
}


def health(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as r:
            return json.loads(r.read())
    except Exception:  # noqa: BLE001
        return None


def worker_pids():
    if not WINDOWS:
        out = subprocess.run(["pgrep", "-f", r"python.* -m worker\.main"], capture_output=True, text=True).stdout.split()
        return [int(p) for p in out if p.strip().isdigit()]
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*worker.main*' } | ForEach-Object { $_.ProcessId }"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split()
    return [int(p) for p in out if p.strip().isdigit()]


def kill_workers():
    for pid in worker_pids():
        if not WINDOWS:
            os.kill(pid, 15)
            continue
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True, encoding="cp949", errors="replace")
    for _ in range(20):
        if not any(health(p) for p in (8097, 8098)):
            return True
        time.sleep(1)
    return False


def _git_bash():
    """The worker script is bash (set -o pipefail); from a Python parent a plain `bash` may resolve to WSL/sh on Windows."""
    import shutil
    git = shutil.which("git")                       # <Git>/cmd/git.exe or <Git>/bin/git.exe → <Git>/bin/bash.exe
    roots = ([Path(git).resolve().parents[1]] if git else []) + [Path("D:/dev/Git"), Path("C:/Program Files/Git")]
    for root in roots:
        for p in (root / "bin/bash.exe", root / "usr/bin/bash.exe"):
            if p.exists():
                return str(p)
    return "bash"


def _host_path():
    """A105 — same as scripts/host_libpq.sh: a signed libpq.dll on PATH so psycopg's pure-Python wrapper works while Smart App
    Control blocks the unsigned DLLs inside psycopg_binary."""
    libpq = Path(os.environ.get("LIBPQ_DIR") or "C:/Program Files/LibreOffice/program")
    path = os.environ.get("PATH", "")
    return f"{libpq}{os.pathsep}{path}" if (libpq / "libpq.dll").exists() and str(libpq) not in path else path


def start_workers(n):
    for i in range(n):
        env = dict(os.environ, PATH=_host_path(), PYTHON=PY)
        if i:
            env.update(CONSUMER_ID=f"agent-worker:host{i + 1}", HEALTH_PORT=str(8097 + i))
        log = open(ROOT / ".evidence/worker" / f"host-worker{i + 1 if i else ''}-regression.log", "a", encoding="utf-8")
        subprocess.Popen([_git_bash(), "scripts/run_worker_host.sh"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    for _ in range(30):
        if all(health(8097 + i) for i in range(n)):
            return True
        time.sleep(1)
    return False


def parse_pass(text):
    failed = any(re.search(p, text, re.M) for p in FAIL_PATTERNS)
    for pat in PASS_PATTERNS:
        m = re.search(pat, text, re.M)
        if m:
            g = [x for x in m.groups() if x]
            if not g:
                return (0, 1) if failed else (1, 1)
            total = int(g[1]) if len(g) > 1 else int(g[0])
            return (int(g[0]) if not failed or len(g) > 1 else 0), total
    return (0, 1) if failed else (None, None)


def run_one(name, script, args, timeout, log_name, out_root):
    out = out_root / name
    argv = [PY, "-u", script] + [a.replace("{out}", str(out)) for a in args]
    t0 = time.monotonic()
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PATH=_host_path())
    try:
        res = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
        rc, text = res.returncode, (res.stdout or "") + "\n" + (res.stderr or "")
    except subprocess.TimeoutExpired as e:
        # TimeoutExpired carries bytes even with text=True (A157: the runner died here and skipped the rest of the group)
        partial = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        rc, text = -1, partial + "\nTIMEOUT"
    if log_name and (out / log_name).exists():
        text += "\n" + (out / log_name).read_text(encoding="utf-8", errors="replace")
    passed, total = parse_pass(text)
    (out_root / f"{name}.log").write_text(text, encoding="utf-8")
    return {"probe": name, "script": script, "exit": rc, "passed": passed, "total": total, "seconds": round(time.monotonic() - t0, 1),
            "verdict": "PASS" if rc == 0 and passed is not None and passed == total else ("FAIL" if passed is not None or rc != 0 else "UNKNOWN"),
            "out": str(out)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--group", choices=["core", "worker", "all"], required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--kill-workers", action="store_true"); ap.add_argument("--restart-workers", type=int, default=0); ap.add_argument("--only", help="comma-separated probe names")
    a = ap.parse_args()
    out_root = Path(a.out); out_root.mkdir(parents=True, exist_ok=False)
    groups = ["core", "worker"] if a.group == "all" else [a.group]
    report = {"started": datetime.now(timezone.utc).isoformat(), "groups": groups, "preconditions": {}, "results": []}
    def save():
        (out_root / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        rows = ["| probe | group | verdict | passed | exit | s |", "|---|---|---|---:|---:|---:|"] + \
               [f"| {r['probe']} | {r['group']} | {r['verdict']} | {r['passed']}/{r['total']} | {r['exit']} | {r['seconds']} |" for r in report["results"]]
        (out_root / "results.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    proc = health(8080) is not None or urllib.request.urlopen("http://127.0.0.1:8080/api/process/definitions", timeout=5) is not None
    report["preconditions"]["process"] = bool(proc)
    for g in groups:
        workers_up = [p for p in (8097, 8098) if health(p)]
        if g == "core" and workers_up:
            if a.kill_workers:
                report["preconditions"]["workers_killed"] = kill_workers(); print("host workers stopped:", report["preconditions"]["workers_killed"], flush=True)
            else:
                print(f"core group needs the host workers stopped (up on {workers_up}); re-run with --kill-workers", flush=True); report["preconditions"]["core_skipped"] = True; continue
        if g == "worker" and not workers_up:
            if a.restart_workers:
                report["preconditions"]["workers_started"] = start_workers(a.restart_workers); print("host workers started:", report["preconditions"]["workers_started"], flush=True)
            else:
                print("worker group needs a host worker on 8097 (and 8098 for the lease probe); re-run with --restart-workers 2", flush=True); report["preconditions"]["worker_skipped"] = True; continue
        for name, script, args, timeout, log_name in PROBES[g]:
            if a.only and name not in a.only.split(","):
                continue
            print(f"== {g} · {name} …", flush=True)
            r = run_one(name, script, args, timeout, log_name, out_root); r["group"] = g
            report["results"].append(r); save()
            print(f"   {r['verdict']} {r['passed']}/{r['total']} exit {r['exit']} {r['seconds']}s", flush=True)
    if a.restart_workers and "core" in groups and not any(health(p) for p in (8097, 8098)):
        report["preconditions"]["workers_restarted"] = start_workers(a.restart_workers); print("host workers restarted:", report["preconditions"]["workers_restarted"], flush=True)
    report["finished"] = datetime.now(timezone.utc).isoformat(); save()
    verdicts = [r["verdict"] for r in report["results"]]
    print("REGRESSION", f"{verdicts.count('PASS')}/{len(verdicts)} PASS", {v: verdicts.count(v) for v in set(verdicts)}, flush=True)
    sys.exit(0 if verdicts and all(v == "PASS" for v in verdicts) else 1)


if __name__ == "__main__":
    main()
