"""A083 (R05, meeting L51~79) — a real observation gap makes window evidence UNKNOWN, and the gap closing restores it.

    .venv314/Scripts/python scripts/probe_evidence_coverage.py .evidence/reaudit/a083-coverage-<n> [--pause 20]

Real stack: the hyd-dmn MCP `diagnose` tool (the one the agents call) on HYD-01 / COOLER_DEGRADATION.
1. Baseline: every declared window evidence carries a coverage record and is judged (PASS/FAIL).
2. The TimescaleDB sink (connect-sink) is paused for --pause seconds — shorter than the asset freshness limit (60 s), so
   diagnosis is not withheld for staleness, but longer than the 1 Hz contract (3 s). The same call must report
   OBSERVATION_GAP for the windows whose tail is unobserved, never PASS/FAIL from the partial aggregate.
3. The sink is resumed (always, in finally); Kafka keeps the samples, so the sink backfills the gap with their own
   timestamps. The same call must judge the windows again. Detector and process read Kafka directly and are not touched.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SINK = 'hyd-iot-edu-connect-sink-1'


def diagnose():
    code = ("import asyncio,json\nfrom fastmcp import Client\nasync def run():\n"
            "    async with Client('http://127.0.0.1:8198/mcp',timeout=120) as c:\n"
            "        r=await c.call_tool('diagnose',{'asset':'HYD-01','pattern':'COOLER_DEGRADATION'})\n"
            "        print(next(x.text for x in r.content if x.type=='text'))\nasyncio.run(run())")
    r = subprocess.run(['docker', 'exec', 'hyd-iot-edu-dmn-mcp-1', 'python', '-c', code], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=180)
    d = json.loads(r.stdout.strip().splitlines()[-1])
    return d.get('document') or d.get('result') or d


def evidence(doc):
    return {e['id']: e for c in doc.get('causes') or [] for e in c.get('evidence') or []}


def tsdb(sql):
    r = subprocess.run(['docker', 'exec', 'hyd-iot-edu-timescaledb-1', 'psql', '-U', 'hyd', '-d', 'hyd', '-At', '-c', sql],
                       capture_output=True, text=True, timeout=30)
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--pause', type=float, default=20.0)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=False)
    report = {'scope': __doc__, 'checks': {}}
    def save(name, v): (out / f'{name}.json').write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def check(name, ok, detail=None):
        report['checks'][name] = {'passed': bool(ok), 'detail': detail}; save('result', report)
        print(('PASS ' if ok else 'FAIL ') + name + ('' if detail is None else '  ' + json.dumps(detail, ensure_ascii=False, default=str)[:300]), flush=True)
    windowed = lambda ev: {k: v for k, v in ev.items() if v.get('coverage')}

    base = diagnose(); save('1-baseline', base); ev = windowed(evidence(base))
    check('baseline_every_window_evidence_is_covered_and_judged',
          ev and all(v['coverage']['covered'] and v['status'] in ('PASS', 'FAIL') for v in ev.values()),
          {k: (v['status'], v['coverage']['samples'], v['coverage']['max_gap_s'], v['coverage']['limit_s']) for k, v in ev.items()})
    try:
        subprocess.run(['docker', 'pause', SINK], check=True, capture_output=True)
        paused_at = time.time(); time.sleep(a.pause)
        gap = diagnose(); save('2-during-gap', gap); ev = windowed(evidence(gap))
        report['ts1_age_during_gap'] = (gap.get('freshness') or {}).get('age_s')
        check('freshness_not_the_reason_diagnosis_reached_evidence', (gap.get('freshness') or {}).get('ok') is True, gap.get('freshness'))
        gapped = {k: v for k, v in ev.items() if v.get('reason') == 'OBSERVATION_GAP'}
        check('gapped_windows_are_unknown_not_judged_from_partial_aggregate',
              gapped and all(v['status'] == 'UNKNOWN' and v['passed'] is None and v['coverage']['max_gap_s'] > v['coverage']['limit_s'] for v in gapped.values())
              and all(v['status'] != 'PASS' or v['coverage']['covered'] for v in ev.values()),
              {k: (v['status'], v.get('reason'), v['coverage']['max_gap_s'], v.get('value')) for k, v in ev.items()})
        check('ce_30s_window_is_gapped', 'evd:ce-low' in gapped, ev.get('evd:ce-low', {}).get('coverage'))
    finally:
        subprocess.run(['docker', 'unpause', SINK], capture_output=True)
        report['paused_seconds'] = round(time.time() - paused_at, 1) if 'paused_at' in locals() else None
    # wait until the sink has backfilled the paused span (Kafka keeps the samples; their own timestamps are written)
    until = time.time() + 120
    while time.time() < until:
        n = tsdb("select count(*) from tag_1s where asset='HYD-01' and name='CE' and time > now() - interval '45 seconds'")
        if n.isdigit() and int(n) >= 44:
            break
        time.sleep(3)
    report['ce_rows_last_45s_after_resume'] = n
    after = diagnose(); save('3-after-resume', after); ev = windowed(evidence(after))
    check('after_backfill_windows_are_covered_and_judged_again',
          ev and all(v['coverage']['covered'] and v['status'] in ('PASS', 'FAIL') for v in ev.values()),
          {k: (v['status'], v['coverage']['samples'], v['coverage']['max_gap_s']) for k, v in ev.items()})
    save('result', report)
    failed = [k for k, v in report['checks'].items() if not v['passed']]
    print('ALL PASS' if not failed else f'FAILED: {failed}', flush=True)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
