"""A086 (R05, meeting L75~79) — business times move on their own; consent follows the business record, not the clock.

    .venv314/Scripts/python scripts/probe_time_anchors.py .evidence/reaudit/a086-time-<n>

Real stack (enterprise-sim on Supabase, agent HTTP, Neo4j rules). Nothing is submitted.
1. The MES due date (due_at) stays put while due_in_h falls with the clock, and due_in_h = (due_at - as_of) / 3600.
2. A decision preview (/api/agent/decide) records the due date as the provenance anchor of order_due_h.
3. The approval check after time has passed (hours differ) raises no order_due_h reason.
4. MES moves the due date (+30 h) → the same approval check refuses with an order_due_h reason. The due date is restored.
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


def http(url, body=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def psql(sql):
    r = subprocess.run(['docker', 'exec', 'supabase_db_hyd-iot-edu', 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-c', sql],
                       capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def ts(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
    report = {'scope': __doc__, 'checks': {}}
    def save(name, v): (out / f'{name}.json').write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def check(name, ok, detail=None):
        report['checks'][name] = {'passed': bool(ok), 'detail': detail}; save('result', report)
        print(('PASS ' if ok else 'FAIL ') + name + ('' if detail is None else '  ' + json.dumps(detail, ensure_ascii=False, default=str)[:300]), flush=True)
    due_reason = lambda reasons: [r for r in reasons if 'order_due_h' in r]

    _, m1 = http('http://127.0.0.1:8095/mes/orders?asset=HYD-01'); save('1-mes-first', m1)
    f1 = m1['facts']
    computed = (ts(f1['due_at']) - ts(m1['as_of'])).total_seconds() / 3600
    check('due_in_h_is_computed_from_the_stored_due_date', abs(f1['due_in_h'] - computed) <= 0.01, dict(due_at=f1['due_at'], as_of=m1['as_of'], due_in_h=f1['due_in_h'], computed=round(computed, 4)))

    code, d = http('http://127.0.0.1:8091/api/agent/decide', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}); save('2-decision', d)
    prov = {p['variable']: p for p in d.get('provenance') or []}
    check('decision_records_the_due_date_as_the_anchor', code == 200 and prov.get('order_due_h', {}).get('anchor') == f1['due_at'],
          dict(http=code, row={k: prov.get('order_due_h', {}).get(k) for k in ('value', 'anchor', 'how')}))
    d = dict(d, options=(d.get('result') or {}).get('options') or d.get('options') or [])   # the preview keeps cards under result
    option = (d.get('result') or {}).get('recommended') or d.get('recommended') or (d['options'] or [{}])[0].get('id')

    time.sleep(45)
    _, m2 = http('http://127.0.0.1:8095/mes/orders?asset=HYD-01'); save('3-mes-later', m2)
    check('the_clock_moves_the_hours_not_the_due_date', m2['facts']['due_at'] == f1['due_at'] and m2['facts']['due_in_h'] < f1['due_in_h'],
          dict(before=f1['due_in_h'], after=m2['facts']['due_in_h'], due_at=m2['facts']['due_at']))
    code, a1 = http('http://127.0.0.1:8091/api/agent/approval-check', {'decision': d, 'option': option, 'role': 'role:prod-mgr'}); save('4-approval-after-time', a1)
    check('elapsed_time_alone_raises_no_due_reason', code == 200 and a1.get('facts', {}).get('order_due_h') != d['facts'].get('order_due_h') and not due_reason(a1['reasons']),
          dict(http=code, decided=d['facts'].get('order_due_h'), now=a1.get('facts', {}).get('order_due_h'), reasons=a1.get('reasons')))
    order = f1['order_id']; original = psql(f"select due_at from ent.production_orders where order_id='{order}'")
    try:
        psql(f"update ent.production_orders set due_at = due_at + interval '30 hours' where order_id='{order}'")
        code, a2 = http('http://127.0.0.1:8091/api/agent/approval-check', {'decision': d, 'option': option, 'role': 'role:prod-mgr'}); save('5-approval-after-due-moved', a2)
        check('a_moved_due_date_is_refused', code == 200 and not a2.get('allowed') and bool(due_reason(a2['reasons'])),
              dict(http=code, now=a2.get('facts', {}).get('order_due_h'), reasons=due_reason(a2.get('reasons') or [])))
    finally:
        psql(f"update ent.production_orders set due_at = '{original}' where order_id='{order}'")
        report['restored_due_at'] = psql(f"select due_at from ent.production_orders where order_id='{order}'")
    check('due_date_restored', report['restored_due_at'] == original, dict(original=original, now=report['restored_due_at']))
    save('result', report)
    failed = [k for k, v in report['checks'].items() if not v['passed']]
    print('ALL PASS' if not failed else f'FAILED: {failed}', flush=True)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
