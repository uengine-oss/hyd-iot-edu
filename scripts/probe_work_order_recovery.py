"""Real PostgreSQL/SQLite/CMMS, with fake PLC and graph; scoped fixture cleanup."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

import probe_approval_delivery as fixture
from procsvc import machine

OUT=fixture.ROOT/'.evidence/reaudit/work-order-recovery-pg'
fixture.OUT=OUT


class Fx(machine.Effects):
    def emit_audit(self, event): pass
    def set_timer(self, name, seconds): pass


def ready(work_order_only=False):
    rt,ctx,store,meta=fixture.fixture()
    inc=next(iter(ctx.incidents.values()))
    if work_order_only:
        opt=ctx.book[meta['decision']]['options'][0]
        opt['actions']=[a for a in opt['actions'] if a['code']=='WO_CREATE']
        opt['kind']='work_order'
    fixture.choose(rt,meta)
    if not work_order_only:
        now=datetime.now(timezone.utc)
        machine.on_status(inc,{'cmdId':inc.cmd_id,'result':'DONE'},now,Fx())
        rt.on_incident_update(inc.state,inc.id,inc.cleared)
        machine.on_alert(inc,{'alertId':inc.alert_id,'state':'CLEAR'},Fx())
        machine.on_timer(inc,'reobs',now,50.0,Fx())
        ctx.persist()
    return rt,ctx,store,meta,inc


def workitem(rt,meta):
    return next(w for w in rt.repo.list_workitems(proc_inst_id=meta['pid']) if w['activity_id']=='task:work-order')


def receipt(rt,ctx,meta):
    wi=workitem(rt,meta);inc=next(iter(ctx.incidents.values()))
    with fixture.psycopg.connect(fixture.DSN) as c:
        rows=c.execute('select id,task from ent.work_orders where decision_id=%s',(meta['decision'],)).fetchall()
    assert len(rows)==1 and wi['status']=='DONE' and inc.state=='CLOSED', {
        'rows':rows,'workitem':wi['status'],'consumer':wi.get('consumer'),
        'retry':wi.get('retry'),'incident_state':inc.state,'work_order':inc.work_order}
    assert rows[0][0]==wi['output']['work_order']['ref']==inc.work_order['id']
    assert rt.repo.get_instance(meta['pid'])['status']=='COMPLETED'
    return {'ref':rows[0][0],'task':rows[0][1],'rows':len(rows),'commands':len(meta['commands']),
            'incident_state':inc.state,'work_item_status':wi['status']}


def confirmed_recovery_and_receipt():
    rt,ctx,store,meta,inc=ready()
    assert inc.state=='RESOLVED' and inc.work_order is None
    rt.on_incident_update(inc.state,inc.id,inc.cleared)
    result=receipt(rt,ctx,meta);store.db.close();return result


def work_order_without_plc():
    rt,ctx,store,meta,inc=ready(True)
    result=receipt(rt,ctx,meta)
    assert not meta['commands'] and inc.cmd_id is None
    store.db.close();return result


def offline_then_retry():
    rt,ctx,store,meta,inc=ready()
    real=ctx.exec_skill;calls=[]
    def execute(d,item):
        calls.append(deepcopy(item))
        return {'ok':False,'error':'injected CMMS offline','skill':item['skill'],'code':'WO_CREATE'} if len(calls)==1 else real(d,item)
    ctx.exec_skill=execute
    rt.on_incident_update(inc.state,inc.id,inc.cleared)
    assert inc.state=='RESOLVED' and inc.work_order is None and workitem(rt,meta)['retry']==1
    rt.poll_once()
    assert calls[0]==calls[1]
    result=receipt(rt,ctx,meta)|{'same_input':True};store.db.close();return result


def exhausted_retries_and_competing_recovery():
    rt,ctx,store,meta,inc=ready()
    real=ctx.exec_skill
    ctx.exec_skill=lambda d,item:{'ok':False,'error':'offline','code':'WO_CREATE','skill':item['skill']}
    rt.on_incident_update(inc.state,inc.id,inc.cleared)
    rt.poll_once();rt.poll_once()
    wi=workitem(rt,meta)
    assert wi['status']=='PENDING' and wi['retry']==3
    try:rt.retry_work_order(wi['id'],'operator','role:operator')
    except PermissionError:pass
    else:raise AssertionError('lower role could retry')
    # Preserve the accepted human retry, simulate its dispatcher dying before it runs.
    after=rt._after_commit;rt._after_commit=lambda *a,**k:None
    rt.retry_work_order(wi['id'],'manager','role:prod-mgr')
    rt._after_commit=after
    wi=workitem(rt,meta);wi['consumer']='dead-engine';rt.repo.update_workitem(wi)
    calls=[]
    ctx.exec_skill=lambda d,item:(calls.append(deepcopy(item)),real(d,item))[1]
    peers=[fixture.instances.InstanceRuntime(fixture.procdb.PgRepo(fixture.DSN),rt.defn,
           fixture.instance_mode._hooks(ctx),tenant_id=rt.tenant_id,consumer=f'peer-{i}') for i in range(8)]
    with ThreadPoolExecutor(8) as pool:list(pool.map(lambda peer:peer.poll_once(),peers))
    result=receipt(rt,ctx,meta)
    assert len(calls)==1 and workitem(rt,meta)['rework_count']==1
    store.db.close();return result|{'peers':8,'http_calls':len(calls),'manual_retry_cycle':1}


def sql_failure_after_actual_receipt():
    rt,ctx,store,meta,inc=ready()
    update=rt.repo.update_workitem
    def fail(wi):
        if wi['activity_id']=='task:work-order' and wi['status']=='DONE':
            raise RuntimeError('injected work-item SQL completion failure')
        return update(wi)
    rt.repo.update_workitem=fail
    rt.on_incident_update(inc.state,inc.id,inc.cleared)
    assert inc.state=='CLOSED' and inc.work_order['id']
    assert workitem(rt,meta)['status']=='SUBMITTED'
    before=inc.work_order['id'];store.db.close()
    restarted,restored,store2=fixture.new_runtime(meta)
    restarted.poll_once()
    result=receipt(restarted,restored,meta)
    assert result['ref']==before
    store2.db.close();return result|{'replayed_after_sql_failure':True}


def child_crash(path):
    meta=json.loads(Path(path).read_text(encoding='utf-8'))
    rt,ctx,store=fixture.new_runtime(meta)
    def crash(d,item):
        result=fixture.process_main.exec_skill(d,item)
        assert result.get('ok'),result
        (Path(path).parent/'before-exit.json').write_text(json.dumps(result),encoding='utf-8')
        os._exit(73)
    ctx.exec_skill=crash
    rt.poll_once()
    raise AssertionError('crash point not reached')


def process_death_after_cmms_commit():
    rt,ctx,store,meta,inc=ready()
    ctx.exec_skill=lambda d,item: (_ for _ in ()).throw(RuntimeError('pause before CMMS'))
    rt.on_incident_update(inc.state,inc.id,inc.cleared)
    assert inc.work_order_request and inc.state=='RESOLVED'
    store.db.close()
    path=Path(meta['store']).parent/'fixture.json';path.write_text(json.dumps(meta),encoding='utf-8')
    child=subprocess.run([sys.executable,__file__,'--child',str(path)],capture_output=True,timeout=45)
    (path.parent/'child.log').write_bytes(child.stdout+child.stderr)
    assert child.returncode==73,child.stderr.decode(errors='replace')
    before=json.loads((path.parent/'before-exit.json').read_text(encoding='utf-8'))
    restarted,restored,store2=fixture.new_runtime(meta)
    pending=next(iter(restored.incidents.values()))
    assert pending.state=='RESOLVED' and pending.work_order is None
    restarted.poll_once()
    result=receipt(restarted,restored,meta)
    assert before['ref']==result['ref'] and len(meta['commands'])==1
    store2.db.close();return result|{'child_exit':73,'reused_actual_reference':True}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={'scope':'real PgRepo + SQLite + HTTP CMMS; fake PLC/graph; real child process termination','checks':[]}
    try:
        for case in [confirmed_recovery_and_receipt,work_order_without_plc,offline_then_retry,exhausted_retries_and_competing_recovery,
                     sql_failure_after_actual_receipt,process_death_after_cmms_commit]:
            try:
                detail=case();report['checks'].append({'name':case.__name__,'ok':True,'detail':detail})
                print(case.__name__+': PASS',flush=True)
            except Exception:
                err=traceback.format_exc();report['checks'].append({'name':case.__name__,'ok':False,'error':err})
                print(case.__name__+': FAIL\n'+err,flush=True)
    finally:
        tenants=[m['tenant'] for m in fixture.FIXTURES]
        dids=[m['decision'] for m in fixture.FIXTURES if 'decision' in m]
        with fixture.psycopg.connect(fixture.DSN) as c:
            pids=[r[0] for r in c.execute('select proc_inst_id from bpm_proc_inst where tenant_id=any(%s)',(tenants,)).fetchall()]
            for table in ('transactions','work_orders'):
                c.execute(f'delete from ent.{table} where decision_id=any(%s)',(dids,))
            c.execute('delete from events where proc_inst_id=any(%s)',(pids,))
            for table in ('bpm_proc_inst','proc_def_version','proc_def'):
                c.execute(f'delete from {table} where tenant_id=any(%s)',(tenants,))
            c.execute('delete from tenants where id=any(%s)',(tenants,))
            report['remaining_instances']=c.execute('select count(*) from bpm_proc_inst where tenant_id=any(%s)',(tenants,)).fetchone()[0]
            report['remaining_events']=c.execute('select count(*) from events where proc_inst_id=any(%s)',(pids,)).fetchone()[0]
            report['remaining_work_orders']=c.execute('select count(*) from ent.work_orders where decision_id=any(%s)',(dids,)).fetchone()[0]
        report['fixtures']=fixture.FIXTURES
        report['passed']=sum(c['ok'] for c in report['checks']);report['total']=len(report['checks'])
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"{report['passed']}/{report['total']}")
    return int(report['passed']!=report['total'])


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':
        child_crash(sys.argv[2])
    else:
        raise SystemExit(main())
