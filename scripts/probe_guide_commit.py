"""Real PG + SQLite guide persistence; no live agent, PLC or CMMS effects."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/process'),str(ROOT/'common')]
from procsvc import engine, instances, instance_mode, procdb
from procsvc.store import Store


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--recorded-instance',required=True);args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    recorded=json.loads(Path(args.recorded_instance).read_text(encoding='utf-8'))
    source=next(w['output'] for w in recorded['workitems'] if w['activity_id']=='task:diagnose')
    source=deepcopy(source)
    tenant='a034-guide-'+uuid.uuid4().hex[:10];repo=procdb.PgRepo(os.environ['SUPABASE_DSN'])
    with repo._conn() as c:c.execute('insert into tenants(id,name) values(%s,%s)',(tenant,tenant))
    store=Store(out/'incident.sqlite3');incidents={};book={};audit=[];checks=[]
    def check(name,passed):
        checks.append({'name':name,'passed':bool(passed)});print(('PASS ' if passed else 'FAIL ')+name,flush=True)
        assert passed,name
    def persist():store.save(incidents,book,audit)
    def unexpected(*a,**k):raise AssertionError('no physical or enterprise effect belongs in this probe')
    ctx=instance_mode.ProcessContext(incidents,book,{},20,persist,
        lambda *a,**k:audit.append(str(a)),lambda *a,**k:[],unexpected,unexpected,unexpected,
        lambda:None,unexpected)
    defn=engine.Definition.load(ROOT/'it/process/definitions/anomaly_response_v21.json')
    rt=instances.InstanceRuntime(repo,defn,instance_mode._hooks(ctx),tenant_id=tenant,consumer=tenant+'-engine')
    alert={'alertId':tenant,'asset':'HYD-01','pattern':'COOLER_DEGRADATION','state':'RAISE','evidence':{'fixture':'guide durability'}}
    inst=rt.on_alert_raise(alert);pid=inst['proc_inst_id']
    def task(activity):return next(w for w in repo.list_workitems(proc_inst_id=pid,limit=None) if w['activity_id']==activity)
    def save(name):
        x={'instance':repo.get_instance(pid),'workitems':repo.list_workitems(proc_inst_id=pid,limit=None),
           'sqlite_cards':{key:value.card for key,value in store.restore()[0].items()}}
        (out/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        wi,=repo.fetch_pending_task('cliagents',tenant,tenant_id=tenant)
        assert repo.save_task_result(wi['id'],source,True,expected_consumer=tenant)
        def fail_sqlite():raise OSError('fixture SQLite write unavailable')
        ctx.persist=fail_sqlite
        rt.poll_once()
        save('sqlite-failure')
        check('SQLite failure keeps PG result submitted and next task unopened',task('task:diagnose')['status']=='SUBMITTED'
              and task('task:diagnose')['retry']==1 and task('task:candidates')['status']=='TODO')
        disk=store.restore()[0]
        check('failed SQLite write did not persist the new guide',all(not i.card.get('recommended') for i in disk.values()))
        ctx.persist=persist
        original_update=repo.update_instance
        def fail_pg(_):raise OSError('fixture PG instance write unavailable')
        repo.update_instance=fail_pg
        rt.poll_once()
        repo.update_instance=original_update
        save('pg-failure')
        check('PG failure rolls back DONE after successful SQLite guide save',task('task:diagnose')['status']=='SUBMITTED'
              and task('task:diagnose')['retry']==2 and task('task:candidates')['status']=='TODO')
        disk=store.restore()[0]
        check('SQLite guide survives PG failure with full original alert',len(disk)==1 and next(iter(disk.values())).card['alert']==alert
              and any(a['code']=='FAN_SET' for a in next(iter(disk.values())).card['recommended']))
        store.db.close();store=Store(out/'incident.sqlite3')
        incidents.clear();incidents.update(store.restore()[0])
        restarted=instances.InstanceRuntime(procdb.PgRepo(repo.dsn),defn,instance_mode._hooks(ctx),tenant_id=tenant,consumer=tenant+'-restarted')
        restarted.poll_once()
        save('restarted')
        check('new runtime and reopened stores complete the same recorded output',task('task:diagnose')['status']=='DONE'
              and task('task:diagnose')['output']==source and task('task:candidates')['status']=='IN_PROGRESS')
        check('replay keeps one incident one instance and sends no command',len(incidents)==1
              and len(repo.list_instances(tenant_id=tenant))==1 and next(iter(incidents.values())).cmd_id is None)
        check('completed replay is not claimed a second time',restarted.poll_once()==0)
    finally:
        (out/'result.json').write_text(json.dumps({'tenant':tenant,'instance':pid,'checks':checks,
            'scope':'actual PostgreSQL and SQLite; recorded Codex output replay; storage exceptions and new runtime; no live agent/physical effects'},ensure_ascii=False,indent=2),encoding='utf-8')
        store.db.close()
    print(f'{len(checks)}/{len(checks)} passed; isolated tenant retained {tenant}',flush=True)


if __name__=='__main__':main()
