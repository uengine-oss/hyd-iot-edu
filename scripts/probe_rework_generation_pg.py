"""Real PostgreSQL commit/crash/claim tests; external effects and graph are absent fixture hooks. No Codex/PLC."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'it/process'), str(ROOT/'common')]
import psycopg
from procsvc import engine, instances, procdb

DSN = 'postgresql://postgres:postgres@127.0.0.1:54322/postgres'


def runtime(meta):
    return instances.InstanceRuntime(procdb.PgRepo(DSN), engine.Definition.from_dict(meta['definition']),
                                     instances.Hooks(), tenant_id=meta['tenant'], time_scale=1)


def invoke(rt, meta):
    return rt.request_rework(meta['pid'], **meta['request'])


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); parser.add_argument('--crash'); args = parser.parse_args()
    out = Path(args.out)
    if args.crash:
        meta = json.loads((out/'fixture.json').read_text(encoding='utf8')); rt = runtime(meta)
        if args.crash == 'before-commit':
            original = rt.repo.record_events
            def terminate(events):
                original(events)
                os._exit(73)
            rt.repo.record_events = terminate
        invoke(rt, meta)
        os._exit(74)
    out.mkdir(parents=True, exist_ok=False); checks = []
    def save(name, value):
        (out/(name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)}); save('checks', checks)
        print(('PASS ' if passed else 'FAIL ') + name, flush=True); assert passed, name
    raw = json.loads((ROOT/'docs/examples/rework-inspection-v1.json').read_text(encoding='utf8'))
    # An actual claimed agent row is needed for the stale-result fence. Its
    # accepted value below is a labelled test payload, not an AI inference.
    raw['roles'].append({'name': 'Agent', 'endpoint': 'sys:agent'})
    raw['activities'][0].update(type='userTask', role='Agent', agentMode='COMPLETE', orchestration='cliagents')
    tenant = 'rework-' + uuid.uuid4().hex[:10]
    with psycopg.connect(DSN) as c:
        c.execute('insert into tenants(id,name) values(%s,%s)', (tenant, 'A038 retained fixture'))
    meta = {'tenant': tenant, 'definition': raw}; rt = runtime(meta)
    inst = rt.start_definition(raw['processDefinitionId'], '1', str(uuid.uuid4()), {'score': 2}); pid = inst['proc_inst_id']
    claimed = rt.repo.fetch_pending_task('cliagents', 'old-worker', tenant_id=tenant, proc_inst_id=pid)[0]
    meta.update(pid=pid, request=dict(workitem_id=claimed['id'], request_id=str(uuid.uuid4()),
                snapshot_token=rt.preview_rework(pid, claimed['id'])['snapshot_token'], by='PG rework tester',
                role='role:operator', reason='Change request after original claim'))
    save('fixture', meta); before = rt.instance_view(pid); save('before', before)
    process = subprocess.run([sys.executable, __file__, '--out', str(out), '--crash', 'before-commit'], capture_output=True)
    save('before-commit-child', {'exit': process.returncode, 'stderr': process.stderr.decode('utf8', errors='replace')})
    check('actual child crash before commit rolls back all rows receipt and events', process.returncode == 73 and rt.instance_view(pid) == before)
    process = subprocess.run([sys.executable, __file__, '--out', str(out), '--crash', 'after-commit'], capture_output=True)
    save('after-commit-child', {'exit': process.returncode, 'stderr': process.stderr.decode('utf8', errors='replace')})
    check('actual child exits after durable commit', process.returncode == 74 and rt.repo.get_instance(pid)['rework_generation'] == 1)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: invoke(runtime(meta), meta), range(4)))
    result = results[0]; save('result-receipt', result)
    check('four fresh PG runtimes replay exactly one committed generation', all(r == result for r in results) and len(rt.repo.list_reworks(tenant, pid)) == 1)
    check('one generation event and old claim cancelled',
          sum(e['job_id'] == 'PROCESS_REWORK' for e in rt.repo.list_events(proc_inst_id=pid)) == 1
          and rt.repo.get_workitem(claimed['id'])['status'] == 'CANCELLED')
    check('late actual worker RPC cannot overwrite cancelled row', not rt.repo.save_task_result(claimed['id'], {'score': 999}, True, expected_consumer='old-worker'))
    fresh = rt.repo.fetch_pending_task('cliagents', 'new-worker', tenant_id=tenant, proc_inst_id=pid)[0]
    check('fresh claim points to replacement UUID and generation', fresh['id'] == result['start_workitem'] and fresh['generation'] == 1 and fresh['supersedes_id'] == claimed['id'])
    rt.repo.save_task_result(fresh['id'], {'score': 7}, True, expected_consumer='new-worker'); rt.poll_once()
    current = engine._by_activity(rt.repo.list_workitems(proc_inst_id=pid, limit=None))
    check('new result opens next task with only valid predecessor', current['check']['status'] == 'IN_PROGRESS' and current['check']['reference_ids'] == [fresh['id']])
    try:
        with psycopg.connect(DSN) as c: c.execute('update todolist set generation=99 where id=%s', (fresh['id'],))
    except psycopg.Error as error:
        check('DB rejects generation identity mutation', 'immutable' in str(error))
    else: check('DB rejects generation identity mutation', False)
    try:
        with psycopg.connect(DSN) as c: c.execute("update process_rework_receipt set request='{}' where request_id=%s", (result['request_id'],))
    except psycopg.Error as error:
        check('DB rejects immutable request replacement', 'immutable' in str(error))
    else: check('DB rejects immutable request replacement', False)
    rt.submit(current['check']['id'], {'score': 8}, by='PG reviewer')
    current = engine._by_activity(rt.repo.list_workitems(proc_inst_id=pid, limit=None))
    rt.submit(current['finish']['id'], {'note': 'Actual generation checked'}, by='PG reviewer')
    final = rt.instance_view(pid); save('final', final)
    check('retained fixture ends normally and original input survives', final['instance']['status'] == 'COMPLETED' and final['instance']['initial_variables'] == {'score': 2})
    save('result', {'scope': __doc__, 'fixture': meta, 'checks': checks})
    print(f'{len(checks)}/{len(checks)} passed', flush=True)


if __name__ == '__main__': main()
