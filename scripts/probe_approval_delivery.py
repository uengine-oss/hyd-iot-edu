"""Real PgRepo + SQLite + HTTP enterprise; PLC/graph effects remain test doubles.

The crash case exits a separate Python process after the real enterprise commit.
Cleanup is restricted to the exact fixture tenants and decision identifiers.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'it/process'), str(ROOT/'common'), str(ROOT/'tests')]
import psycopg
from procsvc import decisions, engine, instance_mode, instances, machine, procdb, main as process_main
from procsvc.store import Store
from test_instance_mode import ALERT, GUIDE_CARD_ACTIONS, _decision_payload

DSN = 'postgresql://postgres:postgres@127.0.0.1:54322/postgres'
OUT = ROOT/'.evidence/reaudit/approval-delivery-pg'
DEFINITION = ROOT/'it/process/definitions/anomaly_response_v2.json'
FIXTURES = []
process_main.ENTERPRISE_URL = 'http://127.0.0.1:8095'


def context(store_path, commands):
    store = Store(store_path)
    incidents, book, audit = store.restore()
    def persist():
        store.save(incidents, book, audit)
    def approve(inc, by, actions):
        class Fx(machine.Effects):
            def emit_cmd(self, cmd): commands.append(deepcopy(cmd))
            def emit_audit(self, event): audit.append(event)
            def set_timer(self, name, seconds): pass
        result = machine.on_approve(inc, by, actions, datetime.now(timezone.utc), Fx())
        persist()
        return result
    ctx = instance_mode.ProcessContext(incidents=incidents, book=book, state={}, time_scale=20,
        persist=persist, audit=lambda *a, **k: None, cypher=lambda *a, **k: [],
        exec_skill=process_main.exec_skill, record_decision=lambda _: None,
        approve_incident=approve, get_loop=lambda: None,
        check_approval=lambda *args: {'allowed': True, 'scope': 'approval-delivery-probe-source-double'})
    return ctx, store


def fixture(purchase=False):
    tenant = 'approval-'+uuid.uuid4().hex[:10]
    folder = OUT/tenant
    folder.mkdir(parents=True)
    with psycopg.connect(DSN) as c:
        c.execute('insert into tenants(id,name) values(%s,%s)', (tenant, tenant))
    meta = {'tenant':tenant, 'store':str(folder/'snapshot.sqlite'), 'commands':[]}
    FIXTURES.append(meta)
    ctx, store = context(meta['store'], meta['commands'])
    rt = instances.InstanceRuntime(procdb.PgRepo(DSN), engine.Definition.load(DEFINITION),
                                    instance_mode._hooks(ctx), tenant_id=tenant)
    inst = rt.on_alert_raise(dict(ALERT, alertId=tenant))
    inc = next(iter(ctx.incidents.values()))
    inc.card = dict(inc.card, recommended=GUIDE_CARD_ACTIONS)
    d = decisions.new(dict(_decision_payload(inc.id), id='DEC-'+tenant))
    if purchase:
        d['options'][0]['actions'].append({'code':'PR_CREATE', 'kind':'transaction',
            'value':'sup:b', 'target':'sys:erp'})
    ctx.book[d['id']] = d
    ctx.persist()
    for aid, output in instance_mode._legacy_outputs(d, inc).items():
        row, = rt.repo.fetch_pending_task('cliagents', tenant, tenant_id=tenant)
        assert row['activity_id'] == aid
        assert rt.repo.save_task_result(row['id'], output, True, expected_consumer=tenant)
        rt.poll_once()
    wi = next(w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='task:select')
    meta.update(pid=inst['proc_inst_id'], wid=wi['id'], decision=d['id'])
    return rt, ctx, store, meta


def choose(rt, meta):
    return rt.select(meta['wid'], meta['decision'], 'skill:fan-max-derate', '[회귀 검사] 승인 검사기', 'role:prod-mgr')


def new_runtime(meta):
    ctx, store = context(meta['store'], meta['commands'])
    rt = instances.InstanceRuntime(procdb.PgRepo(DSN), engine.Definition.load(DEFINITION),
                                    instance_mode._hooks(ctx), tenant_id=meta['tenant'])
    return rt, ctx, store


def rollback_before_commit():
    rt, ctx, store, meta = fixture()
    before = deepcopy(ctx.book)
    def fail(_): raise RuntimeError('injected SQL transition failure')
    rt.repo.update_instance = fail
    try: choose(rt, meta)
    except RuntimeError: pass
    else: raise AssertionError('injection not reached')
    assert ctx.book == before and store.restore()[1] == before
    assert rt.repo.get_workitem(meta['wid'])['status']=='IN_PROGRESS'
    assert rt.repo.get_approval(meta['wid'], meta['tenant']) is None and not meta['commands']
    store.db.close()
    return {'book_unchanged':True, 'approval_absent':True, 'commands':0}


def lost_dispatch_and_competing_recovery():
    rt, ctx, store, meta = fixture()
    rt._after_commit = lambda *a, **k: None
    choose(rt, meta)
    assert rt.repo.get_approval(meta['wid'], meta['tenant'])['status']=='PENDING'
    # All dispatchers share the restored process context, like concurrent engine threads.
    peers = [instances.InstanceRuntime(procdb.PgRepo(DSN), rt.defn, instance_mode._hooks(ctx),
                                      tenant_id=rt.tenant_id, consumer=f'peer-{n}') for n in range(8)]
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda r: r.deliver_approval(meta['wid']), peers))
    row = rt.repo.get_approval(meta['wid'], meta['tenant'])
    assert row['status']=='DELIVERED' and row['attempts']==1 and len(meta['commands'])==1
    assert rt.repo.get_workitem(meta['wid'])['status']=='DONE'
    store.db.close()
    return {'connections':8, 'attempts':row['attempts'], 'commands':len(meta['commands'])}


def sqlite_failure_and_manual_retry():
    rt, ctx, store, meta = fixture()
    persist = ctx.persist
    def fail(): raise OSError('injected SQLite write failure')
    ctx.persist = fail
    choose(rt, meta)
    row = rt.repo.get_approval(meta['wid'], meta['tenant'])
    assert row['status']=='FAILED' and not meta['commands']
    ctx.persist = persist
    try: rt.retry_approval(meta['wid'], 'operator', role='role:operator')
    except PermissionError: pass
    else: raise AssertionError('lower role could retry')
    row = rt.retry_approval(meta['wid'], 'manager', role='role:prod-mgr')
    assert row['status']=='DELIVERED' and row['attempts']==2 and len(meta['commands'])==1
    store.db.close()
    return {'failed_delivery_blocks_commands':True, 'lower_role_rejected':True, 'retry_attempts':2}


def crash_child(path):
    meta = json.loads(Path(path).read_text(encoding='utf-8'))
    rt, ctx, store = new_runtime(meta)
    def crash_after_commit(d, item):
        result = process_main.exec_skill(d, item)
        if result.get('ok') is not True:
            raise RuntimeError(str(result))
        (Path(path).parent/'external-before-exit.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        os._exit(73)
    ctx.exec_skill = crash_after_commit
    rt.deliver_approval(meta['wid'])
    raise AssertionError('crash hook did not run')


def process_death_after_enterprise_commit():
    rt, ctx, store, meta = fixture(purchase=True)
    rt._after_commit = lambda *a, **k: None
    choose(rt, meta)
    store.db.close()
    config = Path(meta['store']).parent/'fixture.json'
    config.write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    child = subprocess.run([sys.executable, __file__, '--crash-child', str(config)], capture_output=True, timeout=45)
    (config.parent/'child.log').write_bytes(child.stdout+child.stderr)
    assert child.returncode==73, child.stderr.decode(errors='replace')
    assert rt.repo.get_approval(meta['wid'], meta['tenant'])['status']=='PENDING'
    with psycopg.connect(DSN) as c:
        before = c.execute('select id from ent.purchase_requests where decision_id=%s', (meta['decision'],)).fetchall()
    assert len(before)==1
    restarted, restored, store2 = new_runtime(meta)
    restarted.poll_once()
    row = restarted.repo.get_approval(meta['wid'], meta['tenant'])
    with psycopg.connect(DSN) as c:
        after = c.execute('select id from ent.purchase_requests where decision_id=%s', (meta['decision'],)).fetchall()
    assert before==after and row['status']=='DELIVERED' and len(meta['commands'])==1
    assert row['results'][0]['ref']==before[0][0]
    assert len(restored.book[meta['decision']]['executions'])==1
    store2.db.close()
    return {'child_exit':child.returncode, 'before_purchase_ids':before, 'after_purchase_ids':after,
            'delivery_status':row['status'], 'commands':len(meta['commands'])}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'scope':'real PostgreSQL + SQLite + HTTP enterprise; fake PLC commands/graph; actual child os._exit fault', 'checks':[]}
    try:
        for case in [rollback_before_commit, lost_dispatch_and_competing_recovery,
                     sqlite_failure_and_manual_retry, process_death_after_enterprise_commit]:
            try:
                detail = case()
                report['checks'].append({'name':case.__name__, 'ok':True, 'detail':detail})
                print(case.__name__+': PASS', flush=True)
            except Exception:
                error = traceback.format_exc()
                report['checks'].append({'name':case.__name__, 'ok':False, 'error':error})
                print(case.__name__+': FAIL\n'+error, flush=True)
    finally:
        tenants = [m['tenant'] for m in FIXTURES]
        dids = [m['decision'] for m in FIXTURES if 'decision' in m]
        with psycopg.connect(DSN) as c:
            pids = [r[0] for r in c.execute('select proc_inst_id from bpm_proc_inst where tenant_id=any(%s)', (tenants,)).fetchall()]
            c.execute('delete from ent.transactions where decision_id=any(%s)', (dids,))
            c.execute('delete from ent.purchase_requests where decision_id=any(%s)', (dids,))
            c.execute('delete from events where proc_inst_id=any(%s)', (pids,))
            c.execute('delete from bpm_proc_inst where tenant_id=any(%s)', (tenants,))
            c.execute('delete from proc_def_version where tenant_id=any(%s)', (tenants,))
            c.execute('delete from proc_def where tenant_id=any(%s)', (tenants,))
            c.execute('delete from tenants where id=any(%s)', (tenants,))
            report['remaining_instances'] = c.execute('select count(*) from bpm_proc_inst where tenant_id=any(%s)', (tenants,)).fetchone()[0]
            report['remaining_events'] = c.execute('select count(*) from events where proc_inst_id=any(%s)', (pids,)).fetchone()[0]
            report['remaining_approvals'] = c.execute('select count(*) from process_approval_outbox where tenant_id=any(%s)', (tenants,)).fetchone()[0]
        report['fixtures'] = FIXTURES
        report['passed'] = sum(x['ok'] for x in report['checks'])
        report['total'] = len(report['checks'])
        (OUT/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"{report['passed']}/{report['total']}")
    return int(report['passed'] != report['total'])


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--crash-child':
        crash_child(sys.argv[2])
    else:
        sys.exit(main())
