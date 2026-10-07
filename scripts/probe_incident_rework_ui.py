"""Phased live UI fixture: recorded diagnosis + real DMN/MES/PG/PLC, never Codex.

prepare -> change-source -> portal rework -> rank -> portal consent -> finish.
restore is available independently; every mutation has a prior-value journal.
Only an explicitly synthetic alert is used, without injecting a physical fault.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'it/process'), str(ROOT/'it/agent-worker'), str(ROOT/'common')]
import psycopg
from procsvc import procdb, engine
from worker.context import process_scope
from probe_alert_triage import publish

PROCESS = 'http://127.0.0.1:8080'
PLANT = 'http://127.0.0.1:8000'
DSN = 'postgresql://postgres:postgres@127.0.0.1:54322/postgres'


def request(url, data=None):
    req = Request(url, data=json.dumps(data).encode() if data is not None else None,
                  headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=40) as response:
        return json.load(response)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=['prepare', 'change-source', 'resume-source', 'rank', 'finish', 'restore'])
    ap.add_argument('--out', required=True)
    ap.add_argument('--label', default='A042', help='Evidence label, not a production behavior change')
    ap.add_argument('--due', type=float, help='Explicit synthetic MES due time for change-source')
    ap.add_argument('--clear-after-ack', action='store_true', help='Publish this synthetic alert CLEAR after actual PLC ACK')
    args = ap.parse_args()
    assert args.label.isalnum(), 'Evidence label must be alphanumeric'
    out = Path(args.out)
    if args.phase == 'prepare':
        out.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        (out/(name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def read(name):
        return json.loads((out/(name+'.json')).read_text(encoding='utf8'))
    def until(fn, seconds=65):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:result = fn()
            except HTTPError as error:
                if error.code < 500:raise
                print('Transient read failed; observing the same saved operation:',error,flush=True)
                result=None
            except (URLError,TimeoutError) as error:
                print('Read unavailable; observing the same saved operation:',error,flush=True)
                result=None
            if result:
                return result
            time.sleep(.5)
        raise TimeoutError('Expected live state not reached')
    def mcp(arguments):
        code = '''import asyncio,json,sys
from fastmcp import Client
async def run():
    args=json.load(sys.stdin)
    async with Client('http://127.0.0.1:8198/mcp',timeout=60) as client:
        result=await client.call_tool('submit_decision',args)
        print(next(c.text for c in result.content if c.type=='text'))
asyncio.run(run())'''
        result = subprocess.run(['docker', 'exec', '-i', 'hyd-iot-edu-dmn-mcp-1', 'python', '-c', code],
                                input=json.dumps(arguments).encode(), capture_output=True, timeout=90)
        assert result.returncode == 0, result.stderr.decode('utf8', errors='replace')
        return json.loads(result.stdout)

    if args.phase == 'prepare':
        plant = request(PLANT+'/api/state'); save('plant-before', plant)
        status = plant['units']['HYD-01']['status']
        assert status['mode'] == 'REMOTE_AUTO' and status['state'] == 'RUN' and not status['trip']
        assert not plant['units']['HYD-01']['faults']
        raw = request(PROCESS+'/api/process/definition'); save('source-definition', raw)
        raw['processDefinitionId'] = 'incident_rework_ui_'+uuid.uuid4().hex[:8]
        raw['processDefinitionName'] = args.label+' 업무 조건 변경 후 사건 재작업'
        raw['version'] = '1'
        raw['ontologyRef'] = 'proc:'+raw['processDefinitionId']
        for event in raw['events']:
            if event['id'] == 'ev:select-timeout':
                event['timer'] = 'PT24H'
                event['description'] = args.label+' UI 검토용 기한; 기본 정의의 10분 기한은 변경하지 않음'
        save('definition', raw)
        request(PROCESS+'/api/process/definitions', {'definition': raw})
        alert = {'alertId': args.label+'-synthetic-'+uuid.uuid4().hex, 'asset': 'HYD-01',
                 'pattern': 'COOLER_DEGRADATION', 'state': 'RAISE',
                 'evidence': {'fixture': 'No physical fault; recorded first three agent outputs; real DMN and current MES'}}
        inst = request(PROCESS+'/api/instances/start', {'definition_id': raw['processDefinitionId'],
                       'version': raw['version'], 'event_id': alert['alertId'], 'alert': alert})
        state = {'pid': inst['proc_inst_id'], 'incident': engine.variables(inst)['incident'], 'alert': alert,
                 'consumer': args.label.lower()+'-labelled-fixture-'+uuid.uuid4().hex[:8], 'new_codex_execution': False}
        save('state', state)
    else:
        state = read('state')
    path = PROCESS+'/api/instances/'+state['pid']
    repo = procdb.PgRepo(DSN)
    def task(aid):
        return max((w for w in request(path)['workitems'] if w['activity_id'] == aid),
                   key=lambda w: (w.get('generation') or 0, w['start_date']))
    def claim(aid):
        until(lambda: task(aid)['status'] == 'IN_PROGRESS')
        row, = repo.fetch_pending_task('cliagents', state['consumer'], tenant_id='hyd', proc_inst_id=state['pid'])
        assert row['activity_id'] == aid
        return row
    def rank():
        row = claim('task:rank')
        values = engine.variables(request(path)['instance'])
        arguments = {'asset': 'HYD-01', 'pattern': state['alert']['pattern'], 'cause': values['cause'],
                     'failure_mode': values['failure_mode'], 'incident': state['incident'],
                     'alert_id': state['alert']['alertId'], 'process_scope': process_scope(row)}
        generation = row.get('generation') or 0
        save(f'g{generation}-mcp-request', arguments)
        result = mcp(arguments); save(f'g{generation}-mcp-response', result)
        assert result['result'] == 'ok' and result['document']['status'] == 'SUBMITTED'
        document = result['document']
        output = {'decision_id': document['id'], 'decision': {'recommended': document['recommended'],
                  'explanation': document['explanation'], 'order': document['cards']}}
        assert repo.save_task_result(row['id'], output, True, expected_consumer=state['consumer'])
        until(lambda: task('task:select')['status'] == 'IN_PROGRESS')
        save(f'g{generation}-decision', request(PROCESS+'/api/decisions/'+document['id']))
        save(f'g{generation}-view', request(path))
        print(json.dumps({'generation': generation, 'decision': document['id'], 'instance': state['pid']}, ensure_ascii=False), flush=True)

    def restore():
        if (out/'source-before.json').exists():
            before = read('source-before')
            with psycopg.connect(DSN, autocommit=True) as conn:
                current = conn.execute('select ent.hours_from_now(due_at) as due_in_h from ent.production_orders where order_id=%s', (before['order_id'],)).fetchone()[0]
                assert float(current) in (before['due'], before['changed_due']), 'Another writer changed MES; review before overwriting'
                conn.execute('update ent.production_orders set due_at=now()+make_interval(secs=>%s*3600) where order_id=%s', (before['due'], before['order_id']))
                actual = conn.execute('select ent.hours_from_now(due_at) as due_in_h from ent.production_orders where order_id=%s', (before['order_id'],)).fetchone()[0]
                assert float(actual) == before['due']
                save('source-restored', {'order_id': before['order_id'], 'due': actual})
        current = request(PLANT+'/api/state')['units']['HYD-01']['status']
        prior = read('plant-before')['units']['HYD-01']['status']
        if (current['fan_pct'], current['load_pct']) != (prior['fan_pct'], prior['load_pct']):
            inc = request(PROCESS+'/api/incidents/'+state['incident'])
            assert current['cmdId'] == inc['cmdId'], 'Another command changed the plant; review before restoring'
            request(PLANT+'/api/mode', {'asset': 'HYD-01', 'mode': 'REMOTE_MANUAL'})
            result = request(PLANT+'/api/manual', {'asset': 'HYD-01', 'writes': {'FanSpeedSP': prior['fan_pct'], 'LoadSP': prior['load_pct']}})
            assert result['result'] == 'DONE', result
            request(PLANT+'/api/mode', {'asset': 'HYD-01', 'mode': prior['mode']})
        actual = request(PLANT+'/api/state'); save('plant-restored', actual)
        assert all(actual['units']['HYD-01']['status'][key] == prior[key] for key in ('fan_pct', 'load_pct', 'pump', 'mode'))
        print('Source and HYD-01 setpoints restored; event history retained', flush=True)

    if args.phase == 'prepare':
        recorded = json.loads((ROOT/'.evidence/reaudit/a034-codex/traces/instance.json').read_text(encoding='utf8'))
        for aid in ('task:diagnose', 'task:candidates', 'task:compliance'):
            row = claim(aid)
            value = deepcopy(next(w['output'] for w in recorded['workitems'] if w['activity_id'] == aid))
            if isinstance(value.get('guide_card'), dict):
                value['guide_card'].update(alert=state['alert'], incident=state['incident'])
            save(aid.replace(':', '-')+'-recorded-fixture', {'claim': row, 'output': value})
            assert repo.save_task_result(row['id'], value, True, expected_consumer=state['consumer'])
            until(lambda: task(aid)['status'] == 'DONE')
        rank()
    elif args.phase == 'change-source':
        assert not (out/'source-before.json').exists(), 'Already changed; use existing journal'
        with psycopg.connect(DSN, autocommit=True) as conn:
            rows = conn.execute("select order_id,ent.hours_from_now(due_at) as due_in_h from ent.production_orders where asset='HYD-01'").fetchall()
            assert len(rows) == 1 and rows[0][1] is not None
            order_id, due = rows[0]
            changed = args.due if args.due is not None else (36.0 if float(due) < 24 else 2.0)
            assert changed >= 0 and changed != float(due)
            save('source-before', {'order_id': order_id, 'due': float(due), 'changed_due': changed})
            conn.execute('update ent.production_orders set due_at=now()+make_interval(secs=>%s*3600) where order_id=%s', (changed, order_id))
            assert float(conn.execute('select ent.hours_from_now(due_at) as due_in_h from ent.production_orders where order_id=%s', (order_id,)).fetchone()[0]) == changed
        save('after-source-change-view', request(path))
        print(f'MES due {due} -> {changed}; prior decision intentionally preserved', flush=True)
    elif args.phase == 'rank':
        assert task('task:rank')['generation'] == 1, 'Portal must request generation 1 first'
        rank()
    elif args.phase == 'resume-source':
        before = read('source-before')
        with psycopg.connect(DSN, autocommit=True) as conn:
            current = conn.execute('select ent.hours_from_now(due_at) as due_in_h from ent.production_orders where order_id=%s', (before['order_id'],)).fetchone()[0]
            assert float(current) == before['due'], 'Resume only the exact restored fixture'
            conn.execute('update ent.production_orders set due_at=now()+make_interval(secs=>%s*3600) where order_id=%s', (before['changed_due'], before['order_id']))
            actual = conn.execute('select ent.hours_from_now(due_at) as due_in_h from ent.production_orders where order_id=%s', (before['order_id'],)).fetchone()[0]
            assert float(actual) == before['changed_due']
            save('source-resumed', {'order_id': before['order_id'], 'due': actual})
        print('Restored fixture resumed from exact source journal; approval unchanged', flush=True)
    elif args.phase == 'finish':
        try:
            if args.clear_after_ack:
                inc = until(lambda: (v if ((v := request(PROCESS+'/api/incidents/'+state['incident'])).get('ack') or {}).get('result') == 'DONE' else None))
                assert inc['state'] in ('ACKED', 'RE_OBSERVING'), 'Do not turn an ended failure into synthetic success'
                save('ack-before-clear', inc)
                save('synthetic-clear-publication', publish(dict(state['alert'], state='CLEAR')))
                until(lambda: request(PROCESS+'/api/incidents/'+state['incident'])['cleared'])
            def completed():
                view = request(path)
                incident = request(PROCESS+'/api/incidents/'+state['incident'])
                if incident['state'] == 'ESCALATED':
                    save('unexpected-escalation', incident)
                    raise RuntimeError('Source recovery contract failed; finish human review, do not force ev:closed')
                return view if view['instance']['status'] == 'COMPLETED' else None
            final = until(completed, seconds=150)
            inc = request(PROCESS+'/api/incidents/'+state['incident'])
            save('completed', final); save('incident-completed', inc)
            save('plant-after', request(PLANT+'/api/state')); save('graph', request(path+'/graph'))
            assert inc['ack']['result'] == 'DONE', inc
            assert final['instance']['end_event'] == 'ev:closed'
            assert final['instance']['rework_generation'] == 1
            assert task('task:work-order')['output']['work_order']['ok'] is True
            save('generation1-approved-decision', request(PROCESS+'/api/decisions/'+engine.variables(final['instance'])['decision_id']))
            print('Generation 1 approved -> real PLC ACK -> reobservation -> CMMS -> ev:closed', flush=True)
        finally:
            save('last-view', request(path))
            restore()
    elif args.phase == 'restore':
        restore()


if __name__ == '__main__':
    main()
