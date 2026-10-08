"""A156 (A148 item 61, docs/sessions/14 step 2) — the guardrail experiment: break the card's citations, watch the guardrail
refuse the card, restore and watch it pass again.

    .venv/bin/python scripts/probe_guardrail_experiment.py --out .evidence/<A>/guardrail

The session's step 2 edits `card.py` `_citations()`, rebuilds `agent` and injects a cooler fault. A148 tried that with host
workers running: the alert's instance tasks went to Claude Code, the in-server agent was never called (`run: null`). This
probe drives the same in-server pipeline directly through `POST /api/agent/evaluate` (agent/agentsvc/main.py — alert →
causes → T2 skills → card → **guardrail** → stop before any submission), so it does not depend on AGENT_BRIDGE or workers and
writes nothing to the process. The repository file is never edited: the patched `card.py` is copied into the running agent
container only, and the original bytes are copied back and verified by hash in `finally`.
Run nothing else that needs the agent meanwhile (the agent container restarts twice).
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

AGENT, CARD = 'hyd-iot-edu-agent-1', '/srv/agentsvc/card.py'
BASE = 'http://127.0.0.1:8091'
ORIGINAL = '        ids += [a["actionId"], a.get("skillId"), a["sop"].get("id"), a.get("actuatorId")] + [k.get("id") for k in a["constraints"]]\n'
BROKEN = '        ids += [a.get("skillId"), a["sop"].get("id"), a.get("actuatorId")] + [k.get("id") for k in a["constraints"]]   # A156 experiment: action ids dropped\n'


def sh(*argv):
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout


def wait_healthy(timeout=120):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(BASE + '/healthz', timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001 — restarting
            pass
        time.sleep(2)
    return False


def evaluate():
    alert = {'alertId': 'ALT-A156-' + uuid.uuid4().hex[:8], 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'state': 'RAISE',
             'severity': 'HIGH'}
    req = urllib.request.Request(BASE + '/api/agent/evaluate', data=json.dumps({'alert': alert}).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=180) as r:
        run = json.loads(r.read())
    guard = next((s for s in run.get('steps') or [] if s.get('name') == 'guardrail'), None)
    return run, guard


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(name, ok, detail=None):
        checks.append(dict(name=name, passed=bool(ok), detail=detail))
        print(('[PASS] ' if ok else '[FAIL] ') + name, json.dumps(detail, ensure_ascii=False, default=str)[:300])

    tmp = Path(tempfile.mkdtemp(prefix='a156-guardrail-'))
    sh('docker', 'cp', f'{AGENT}:{CARD}', str(tmp / 'card.orig.py'))
    original = (tmp / 'card.orig.py').read_bytes()
    text = original.decode('utf-8')
    check('precondition: the citation line the session edits is in the running card.py', text.count(ORIGINAL) == 1)
    run, guard = evaluate()
    (out / '1-baseline.json').write_text(json.dumps(run, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    check('baseline: guardrail passes (no violations) and the run is not rejected',
          guard and guard.get('status') == 'DONE' and run.get('status') != 'REJECTED_BY_GUARDRAIL',
          dict(status=run.get('status'), guardrail=guard and guard.get('output')))
    try:
        (tmp / 'card.py').write_text(text.replace(ORIGINAL, BROKEN), encoding='utf-8')
        sh('docker', 'cp', str(tmp / 'card.py'), f'{AGENT}:{CARD}')
        sh('docker', 'restart', '-t', '5', AGENT)
        check('patched agent restarted healthy', wait_healthy())
        run, guard = evaluate()
        (out / '2-broken.json').write_text(json.dumps(run, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        violations = ((guard or {}).get('output') or {}).get('violations') or []
        check('broken citations: guardrail FAILED, run REJECTED_BY_GUARDRAIL, violations name the uncited actions',
              guard and guard.get('status') == 'FAILED' and run.get('status') == 'REJECTED_BY_GUARDRAIL'
              and violations and all('not in citations' in v for v in violations),
              dict(status=run.get('status'), error=run.get('error'), violations=violations))
        check('nothing was submitted while rejected (no submit step)', not any(s.get('name') == 'submit' for s in run.get('steps') or []),
              [s.get('name') for s in run.get('steps') or []])
    finally:
        sh('docker', 'cp', str(tmp / 'card.orig.py'), f'{AGENT}:{CARD}')
        sh('docker', 'restart', '-t', '5', AGENT)
        healthy = wait_healthy()
        sh('docker', 'cp', f'{AGENT}:{CARD}', str(tmp / 'card.after.py'))
        restored = hashlib.sha256((tmp / 'card.after.py').read_bytes()).hexdigest() == hashlib.sha256(original).hexdigest()
        check('restored: original card.py bytes back in the container and agent healthy', healthy and restored)
    run, guard = evaluate()
    (out / '3-restored.json').write_text(json.dumps(run, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    check('after restore: guardrail passes again', guard and guard.get('status') == 'DONE' and run.get('status') != 'REJECTED_BY_GUARDRAIL',
          dict(status=run.get('status')))
    passed = sum(c['passed'] for c in checks)
    (out / 'summary.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(f'ALL PASS {passed}/{len(checks)}' if passed == len(checks) else f'FAIL {passed}/{len(checks)}')
    raise SystemExit(0 if passed == len(checks) else 1)


if __name__ == '__main__':
    main()
