"""A156 (A148 item 70-A) — process restarted while the business DB is unreachable comes back on its own, without a container
restart and without touching instance state.

    .venv/bin/python scripts/probe_db_outage_restart.py --out .evidence/<A>/db-outage [--outage-s 20]

Live stack, PROCESS_MODE=instance. Run nothing else against the stack meanwhile (it restarts process — CLAUDE.md §3).
Steps: snapshot instances → `docker pause` the Supabase DB → `docker restart` process → hold the outage → `docker unpause` →
poll /healthz. A148 measured the old failure (startup died on the first psycopg.OperationalError, RestartCount 0→1);
A151 added instance_mode.retry_startup (bounded backoff, /healthz not ready meanwhile).
"""
import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

PROCESS, DB = 'hyd-iot-edu-process-1', 'supabase_db_hyd-iot-edu'
HEALTH = 'http://127.0.0.1:8080/healthz'


def sh(*argv):
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout.strip()


def healthz():
    try:
        with urllib.request.urlopen(HEALTH, timeout=3) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')
    except Exception as e:  # noqa: BLE001 — connection refused while uvicorn is still in startup
        return None, {'error': type(e).__name__}


def instances():
    out = sh('docker', 'exec', DB, 'psql', '-U', 'postgres', '-At', '-F', '|', '-c',
             'select proc_inst_id, status from bpm_proc_inst where coalesce(is_deleted,false)=false order by 1')
    return dict(line.split('|', 1) for line in out.splitlines() if line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--outage-s', type=float, default=20)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    checks, timeline = [], []

    def check(name, ok, detail=None):
        checks.append(dict(name=name, passed=bool(ok), detail=detail))
        print(('[PASS] ' if ok else '[FAIL] ') + name, json.dumps(detail, ensure_ascii=False, default=str))

    def mark(event, **kw):
        timeline.append(dict(t=round(time.monotonic() - t0, 1), event=event, **kw))

    t0 = time.monotonic()
    code, body = healthz()
    check('precondition: process healthy in instance mode with Supabase', code == 200 and body.get('mode') == 'instance'
          and body.get('supabase') is True, body)
    before_restarts = int(sh('docker', 'inspect', PROCESS, '--format', '{{.RestartCount}}'))
    before = instances()
    mark('snapshot', instances=len(before), restart_count=before_restarts)
    sh('docker', 'pause', DB)
    mark('db paused')
    try:
        sh('docker', 'restart', '-t', '10', PROCESS)
        mark('process restarted')
        seen_down = []
        end = time.monotonic() + args.outage_s
        while time.monotonic() < end:
            seen_down.append(healthz()[0])
            time.sleep(2)
        mark('outage held', health_codes=sorted({str(c) for c in seen_down}))
        check('process is not reported healthy while the DB is unreachable', 200 not in seen_down, seen_down)
    finally:
        sh('docker', 'unpause', DB)
        mark('db resumed')
    resumed = time.monotonic()
    code, body = None, {}
    while time.monotonic() - resumed < 120:
        code, body = healthz()
        if code == 200 and body.get('ok'):
            break
        time.sleep(1)
    mark('healthy', after_resume_s=round(time.monotonic() - resumed, 1), body=body)
    check('process becomes healthy on its own after the DB returns (≤120 s)', code == 200 and body.get('ok')
          and body.get('supabase') is True and 'startup_db_error' not in body, dict(code=code, body=body))
    restarts = int(sh('docker', 'inspect', PROCESS, '--format', '{{.RestartCount}}'))
    check('no container restart by the restart policy (startup retried in-process)', restarts == before_restarts,
          dict(before=before_restarts, after=restarts))
    logs = subprocess.run(['docker', 'logs', '--since', '5m', PROCESS], capture_output=True, text=True).stderr
    (out / 'process.log').write_text(logs, encoding='utf-8')
    check('startup logged the bounded DB retry', 'DB unreachable' in logs and 'retrying in' in logs,
          [ln for ln in logs.splitlines() if 'DB unreachable' in ln][:3])
    after = instances()
    lost = sorted(set(before) - set(after))
    check('every instance from before the outage is still there', not lost, lost)
    order = ['RUNNING', 'COMPLETED']
    regressed = {k: (before[k], after[k]) for k in before if k in after and before[k] != after[k]
                 and not (before[k] in order and after[k] in order and order.index(after[k]) > order.index(before[k]))}
    check('no instance status went backwards across the restart', not regressed, regressed)
    passed = sum(c['passed'] for c in checks)
    (out / 'summary.json').write_text(json.dumps(dict(checks=checks, timeline=timeline), ensure_ascii=False, indent=2,
                                                 default=str), encoding='utf-8')
    if passed == len(checks):
        print(f'ALL PASS {passed}/{len(checks)}')
    else:
        print(f'FAIL {passed}/{len(checks)}')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
