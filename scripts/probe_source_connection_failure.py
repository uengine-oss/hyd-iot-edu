"""Interrupt only process -> PostgreSQL TCP traffic, retaining live Kafka.

A task-owned, unpublished Docker TCP proxy forwards the original DB address.
Stopping it breaks real connections; restarting it must recover without an
application restart. Finally restore the original process environment and
remove only the labelled proxy. No shared DB or personal settings are changed.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import traceback
import uuid
from urllib.error import HTTPError
from urllib.request import urlopen

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from probe_alert_triage import publish
from scenario_instance_test import PROCESS, get, post

PROXY = '''import asyncio,os
async def pipe(reader,writer):
    try:
        while data:=await reader.read(65536):
            writer.write(data);await writer.drain()
    finally:writer.close()
async def client(reader,writer):
    try:
        upstream,output=await asyncio.open_connection(os.environ['DB_HOST'],int(os.environ['DB_PORT']))
        await asyncio.gather(pipe(reader,output),pipe(upstream,writer))
    except Exception:writer.close()
async def main():
    server=await asyncio.start_server(client,'0.0.0.0',5432)
    print('READY',flush=True)
    async with server:await server.serve_forever()
asyncio.run(main())
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    suffix = uuid.uuid4().hex[:10]
    proxy = 'hyd-a033-db-proxy-' + suffix
    checks = []
    dsn = os.environ['SUPABASE_DSN']
    proxy_created = process_changed = False
    failure = None

    def save(name, value):
        (out / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf8')

    def run(*cmd, **kwargs):
        return subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=90, check=True, **kwargs)

    def check(name, value, detail=None):
        checks.append({'name': name, 'passed': bool(value), 'detail': detail})
        save('checks', checks)
        print(('PASS ' if value else 'FAIL ') + name, flush=True)
        assert value, name

    def until(fn, timeout=100):
        end = time.monotonic() + timeout
        last = None
        while time.monotonic() < end:
            try:
                result = fn()
                if result:
                    return result
            except Exception as exc:
                last = str(exc)
            time.sleep(.5)
        raise TimeoutError(last or 'condition not observed')

    def health():
        try:
            response = urlopen(PROCESS + '/healthz', timeout=10)
        except HTTPError as exc:
            response = exc
        return json.loads(response.read())

    def inspect(name):
        return json.loads(run('docker', 'inspect', name).stdout)[0]

    def recreate(override):
        run('docker', 'compose', '-f', str(root / 'compose.yaml'), '-f', str(override),
            'up', '-d', '--no-deps', 'process')

    def rows():
        with psycopg.connect(dsn, row_factory=dict_row) as connection:
            return connection.execute("select * from process_source_inbox where tenant_id='hyd' and payload->>'alertId'=any(%s) order by id", (aids,)).fetchall()

    def offsets(positions):
        code = '''import asyncio,json,sys
from aiokafka import AIOKafkaConsumer,TopicPartition
from hydcommon.kafka import bootstrap
async def main():
    positions=json.load(sys.stdin);c=AIOKafkaConsumer(bootstrap_servers=bootstrap(),group_id='process',enable_auto_commit=False)
    await c.start()
    try:
        print(json.dumps([dict(p,committed=await c.committed(TopicPartition(p['topic'],p['partition']))) for p in positions]))
    finally:await c.stop()
asyncio.run(main())'''
        return json.loads(run('docker', 'exec', '-i', 'hyd-iot-edu-agent-1', 'python', '-c', code,
                              input=json.dumps(positions)).stdout)

    original = inspect('hyd-iot-edu-process-1')
    original_env = dict(item.split('=', 1) for item in original['Config']['Env'])
    config = conninfo_to_dict(original_env['SUPABASE_DSN'])
    # Restrict this probe to a single, ordinary TCP endpoint.
    assert ',' not in config.get('host', '') and config.get('host') and not config.get('hostaddr')
    assert original_env['PROCESS_MODE'] == 'instance'
    original_mode = get(PROCESS + '/api/process/mode')
    save('baseline', {'mode': original_mode, 'health': health(), 'process_id': original['Id'],
                      'proxy': proxy, 'scope': 'process DB transport only; DB server and Kafka remain running'})
    restore = out / 'compose.restore.json'
    override = out / 'compose.proxy.json'
    restore.write_text(json.dumps({'services': {'process': {'environment': original_env}}}), encoding='utf8')
    proxy_env = dict(original_env, SUPABASE_DSN=make_conninfo(original_env['SUPABASE_DSN'], host=proxy, port='5432'))
    override.write_text(json.dumps({'services': {'process': {'environment': proxy_env}}}), encoding='utf8')
    (out / 'tcp_proxy.py').write_text(PROXY, encoding='utf8')
    aids = ['A033-connect-' + suffix + '-' + str(index) for index in range(1, 4)]
    alerts = [{'asset': 'HYD-0' + str(index), 'alertId': aid, 'pattern': 'UNSUPPORTED_A033', 'state': 'RAISE',
               't': datetime.now(timezone.utc).isoformat(), 'evidence': {'fixture': 'isolated DB transport outage'}}
              for index, aid in enumerate(aids, 1)]
    save('alerts', alerts)
    try:
        check('healthy instance baseline', health()['ok'])
        network = next(iter(original['NetworkSettings']['Networks']))
        run('docker', 'run', '-d', '--name', proxy, '--label', 'hyd.probe=' + suffix,
            '--network', network, '--add-host', 'host.docker.internal:host-gateway',
            '--mount', 'type=bind,source=' + str(out / 'tcp_proxy.py') + ',target=/probe.py,readonly',
            '-e', 'DB_HOST=' + config['host'], '-e', 'DB_PORT=' + config.get('port', '5432'),
            original['Config']['Image'], 'python', '/probe.py')
        proxy_created = True
        until(lambda: 'READY' in run('docker', 'logs', proxy).stdout)
        process_changed = True
        recreate(override)
        until(lambda: health().get('ok'))
        process_id = inspect('hyd-iot-edu-process-1')['Id']
        save('proxied-baseline', {'health': health(), 'process_id': process_id})
        check('process operates through isolated proxy',
              dict(item.split('=', 1) for item in inspect('hyd-iot-edu-process-1')['Config']['Env'])['SUPABASE_DSN'] == proxy_env['SUPABASE_DSN'])
        run('docker', 'stop', '-t', '2', proxy)
        check('proxy stopped while shared DB stays reachable', not inspect(proxy)['State']['Running'] and rows() == [])
        positions = [publish(alert) for alert in alerts]
        positions.append(publish(alerts[0]))
        save('published', positions)
        observed = until(lambda: (value if value.get('source_receive_error') else None) if (value := health()) else None)
        save('health-outage', observed)
        check('DB connection outage is exposed as unhealthy', not observed['ok'] and observed['kafka'])
        first = offsets(positions)
        time.sleep(2)
        second = offsets(positions)
        save('offsets-outage', {'first': first, 'second': second})
        check('unpersisted multi-asset events do not advance Kafka commits',
              all(a['committed'] == b['committed'] and (b['committed'] is None or b['committed'] <= b['offset'])
                  for a, b in zip(first, second)))
        check('no receipts or incidents fabricated during outage', not rows() and
              not any(incident['alertId'] in aids for incident in get(PROCESS + '/api/incidents')))
        run('docker', 'start', proxy)
        until(lambda: health().get('ok'), 150)
        recovered = until(lambda: (value if len(value) == 4 and sum(r['status'] == 'HANDLED' for r in value) == 3
                                   and sum(r['status'] == 'DUPLICATE' for r in value) == 1 else None) if (value := rows()) else None, 150)
        save('recovered-receipts', recovered)
        canonical = [row for row in recovered if row['status'] == 'HANDLED']
        check('three original events recover with one canonical per asset',
              sorted([row['payload'] for row in canonical], key=lambda item: item['alertId']) == sorted(alerts, key=lambda item: item['alertId']) and
              len({row['result']['instance'] for row in canonical}) == 3)
        check('recovery uses same running process', inspect('hyd-iot-edu-process-1')['Id'] == process_id and
              'consumer_dead' not in health())
        committed = until(lambda: (value if all(row['committed'] is not None and row['committed'] > row['offset'] for row in value) else None)
                          if (value := offsets(positions)) else None)
        save('offsets-recovered', committed)
        check('every published coordinate preserved before commit', all(any(r['topic'] == p['topic'] and r['partition_no'] == p['partition']
              and r['offset_no'] == p['offset'] for r in recovered) for p in positions))
        for row in canonical:
            pid, iid = row['result']['instance'], row['result']['incident']
            view = get(PROCESS + '/api/instances/' + pid)
            incident = get(PROCESS + '/api/incidents/' + iid)
            check(row['asset'] + ': human triage without PLC command', incident['cmdId'] is None and incident['state'] == 'ESCALATED')
            task = next(w for w in view['workitems'] if w['activity_id'] == 'task:triage' and w['status'] == 'IN_PROGRESS')
            reply = post(PROCESS + '/api/todolist/' + task['id'] + '/submit', {'by': 'A033 DB connection probe',
                         'output': {'note': 'Transport outage recovered; original alert retained. No physical fault or recovery was inferred.'}})
            check(row['asset'] + ': human review recorded', not reply.get('error'))
            save('instance-' + row['asset'], get(PROCESS + '/api/instances/' + pid))
    except BaseException:
        failure = traceback.format_exc()
        save('failure', {'traceback': failure})
        raise
    finally:
        if proxy_created:
            run('docker', 'start', proxy)
        if process_changed:
            recreate(restore)
            until(lambda: health().get('ok'), 150)
        if proxy_created:
            owned = inspect(proxy)
            assert owned['Config']['Labels'].get('hyd.probe') == suffix
            run('docker', 'rm', '-f', proxy)
        final = inspect('hyd-iot-edu-process-1')
        save('restored', {'health': health(), 'mode': get(PROCESS + '/api/process/mode'),
                         'original_environment_restored': dict(item.split('=', 1) for item in final['Config']['Env']) == original_env,
                         'remaining_proxy_ids': run('docker', 'ps', '-aq', '--filter', 'label=hyd.probe=' + suffix).stdout.strip()})
        save('result', {'checks': checks, 'failure': failure, 'alert_ids': aids,
                       'scope': 'real process-only DB connection outage, three assets plus duplicate; no DB server outage or Codex'})
    print(f'{len(checks)}/{len(checks)} passed', flush=True)


if __name__ == '__main__':
    main()
