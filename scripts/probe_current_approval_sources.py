"""Deployed assessment API + real Supabase source changes; no PLC execution.

Exact prior values are restored in finally. This deliberately changes teaching
fixture CMMS readiness/MES due time; run only without another scenario in flight.
"""
import json
import argparse
from pathlib import Path
import urllib.request
import psycopg

OUT = Path('.evidence/reaudit/a027-live-sources')
BASE = 'http://127.0.0.1:8091'
DSN = 'postgresql://postgres:postgres@127.0.0.1:54322/postgres'


def post(path, value):
    req = urllib.request.Request(BASE + path, data=json.dumps(value).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'scope': 'real Pg and deployed HTTP assessment; no approval/execution', 'checks': []}

    def save(name, value):
        (OUT / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf8')

    def check(name, ok, detail=None):
        report['checks'].append({'name': name, 'passed': bool(ok), 'detail': detail})
        save('report', report)
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    def preview(pattern):
        result = post('/api/agent/decide', {'asset': 'HYD-01', 'pattern': pattern})
        save('preview-' + pattern, result)
        assert result['status'] in ('EVALUATED', 'NO_FEASIBLE_OPTION'), result.get('status')
        return dict(result, options=result['result']['options'])

    def assess(d, option):
        card = next(o for o in d['options'] if o['id'] == option)
        return post('/api/agent/approval-check', {'decision': d, 'option': option, 'role': card['approver']['id']})

    with psycopg.connect(DSN, autocommit=True) as conn:
        readiness = conn.execute("select standby_ready from ent.maintenance_profiles where asset='HYD-01'").fetchone()[0]
        orders = conn.execute("select order_id,ent.hours_from_now(due_at) as due_in_h from ent.production_orders where asset='HYD-01'").fetchall()
        assert len(orders) == 1, 'fixture expects exactly one source order'
        order_id, due = orders[0]
        save('prior-values', {'standby_ready': readiness, 'order': orders})
        try:
            cooler = preview('COOLER_DEGRADATION')
            save('cooler-decision', cooler)
            good = assess(cooler, 'skill:fan-max-derate')
            save('cooler-baseline', good)
            check('unchanged source data is allowed', good.get('allowed') is True, good.get('reasons'))
            conn.execute('update ent.production_orders set due_at=now()+make_interval(secs=>%s*3600) where order_id=%s', (float(due) + 7, order_id))
            changed = assess(cooler, 'skill:fan-max-derate')
            save('changed-order', changed)
            check('actual MES due change rejects the old consent context', changed.get('allowed') is False
                  and any('order_due_h' in r for r in changed.get('reasons', [])), changed.get('reasons'))
            conn.execute('update ent.production_orders set due_at=now()+make_interval(secs=>%s*3600) where order_id=%s', (due, order_id))
            conn.execute("update ent.maintenance_profiles set standby_ready=true where asset='HYD-01'")
            pump = preview('PUMP_LEAKAGE')
            save('pump-decision', pump)
            good = assess(pump, 'skill:switch-standby-pump')
            save('pump-ready', good)
            check('CMMS explicit ready is read without inventing a standby exclusion',
                  good['facts']['standby_ready'] is True and not any(v['rule']=='rule:standby' for v in good['current_option']['violations']))
            check('explicit current model supplies pump temperature and permits a ready healthy standby',
                  good.get('allowed') is True and good['current_option']['forecastContext']['model_revision']=='1.0'
                  and not any('forecast_ts1' in row['variables'] for row in good['unknown']), good.get('reasons'))
            for name, value in [('not-ready', False), ('unknown', None)]:
                conn.execute("update ent.maintenance_profiles set standby_ready=%s where asset='HYD-01'", (value,))
                changed = assess(pump, 'skill:switch-standby-pump')
                save('pump-' + name, changed)
                check('CMMS ' + name + ' blocks the old ready card', changed.get('allowed') is False
                      and changed['facts']['standby_ready'] is value
                      and any(v['rule']=='rule:standby' for v in changed['current_option']['violations']), changed.get('reasons'))
        finally:
            conn.execute('update ent.production_orders set due_at=now()+make_interval(secs=>%s*3600) where order_id=%s', (due, order_id))
            conn.execute("update ent.maintenance_profiles set standby_ready=%s where asset='HYD-01'", (readiness,))
            actual_ready = conn.execute("select standby_ready from ent.maintenance_profiles where asset='HYD-01'").fetchone()[0]
            actual_due = conn.execute('select ent.hours_from_now(due_at) as due_in_h from ent.production_orders where order_id=%s', (order_id,)).fetchone()[0]
            check('source fixture values restored exactly', actual_ready is readiness and actual_due == due)
    raise SystemExit(0 if all(c['passed'] for c in report['checks']) else 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(OUT))
    OUT = Path(parser.parse_args().out)
    main()
