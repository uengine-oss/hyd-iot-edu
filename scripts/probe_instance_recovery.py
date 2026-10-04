"""A021 real PostgreSQL transactions and recovery; external effects are fakes.

Each case has its own tenant. Separate runtimes/connections contend on the same
instance. Only exact test tenants are removed, even after assertion failure.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import sys
import time
import traceback
import uuid

from probe_definition_registry import ROOT, DSN, review_definition
import psycopg
from procsvc import engine, instances, procdb

sys.path.insert(0, str(ROOT/'tests'))
from test_instances import FakeHooks, AGENT_OUTPUTS, ALERT, DEF_PATH

OUT=ROOT/'.evidence/reaudit/instance-recovery-pg.json'
TENANTS=[]
REPORT={'scope':'actual PostgreSQL, separate runtime connections; FakeHooks for PLC/Incident/CMMS', 'checks':[]}


def fixture(agents=True):
    tenant='recovery-'+uuid.uuid4().hex[:10];TENANTS.append(tenant)
    with psycopg.connect(DSN) as c:c.execute('insert into tenants(id,name) values(%s,%s)',(tenant,tenant))
    hooks=FakeHooks();now=datetime.now(timezone.utc)
    rt=instances.InstanceRuntime(procdb.PgRepo(DSN),engine.Definition.load(DEF_PATH),hooks,
                                 tenant_id=tenant,consumer=tenant+'-engine')
    inst=rt.on_alert_raise(dict(ALERT,alertId=tenant),now=now)
    if agents:
        for _ in range(4):
            wi,=rt.repo.fetch_pending_task('cliagents',tenant,tenant_id=tenant)
            assert rt.repo.save_task_result(wi['id'],AGENT_OUTPUTS[wi['activity_id']],True,expected_consumer=tenant)
            assert rt.poll_once(now=now)==1
    return rt,hooks,inst,now


def task(rt,inst,aid):
    return next(w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'],limit=None) if w['activity_id']==aid)


def another(rt):
    return instances.InstanceRuntime(procdb.PgRepo(DSN),rt.defn,rt.hooks,tenant_id=rt.tenant_id,
                                     consumer=rt.tenant_id+'-'+uuid.uuid4().hex[:6])


def choose(rt,inst,now):
    return rt.select(task(rt,inst,'task:select')['id'],'DEC-1003-001','skill:fan-max-derate',
                     'fixture','role:prod-mgr',now=now)


def timer_beyond_page():
    rt,hooks,inst,now=fixture()
    raw=review_definition(rt.tenant_id+'-noise');noise=engine.Definition.from_dict(raw)
    rt.repo.upsert_proc_def(raw,rt.tenant_id)
    with rt.repo.event_transaction(rt.tenant_id+'-noise'):
        for n in range(205):
            old=now-timedelta(days=1,seconds=n)
            i=engine.new_instance(noise,{},tenant_id=rt.tenant_id,now=old)
            a=engine.start(noise,i,now=old)
            rt.repo.insert_instance(i);rt.repo.insert_workitems(a.created);rt.repo.update_instance(i)
    timer=task(rt,inst,'ev:select-timeout')
    page=rt.repo.list_workitems(status='IN_PROGRESS',tenant_id=rt.tenant_id)
    assert len(page)==200 and timer['id'] not in {w['id'] for w in page}
    fired=rt.fire_timeouts(now+timedelta(seconds=31))
    assert len(fired)==1 and fired[0]['status']=='DONE'
    assert task(rt,inst,'task:select')['status']=='CANCELLED'
    assert task(rt,inst,'task:escalate')['status']=='IN_PROGRESS'
    assert rt.fire_timeouts(now+timedelta(seconds=32))==[]
    return {'older_rows':205,'display_rows':len(page),'fired':len(fired)}


def competing_timers():
    rt,hooks,inst,now=fixture();runtimes=[another(rt) for _ in range(8)]
    with ThreadPoolExecutor(8) as pool:
        results=list(pool.map(lambda r:r.fire_timeouts(now+timedelta(seconds=31)),runtimes))
    assert sum(map(len,results))==1 and hooks.audits.count('SELECT_TIMEOUT')==1
    return {'connections':8,'fired':sum(map(len,results))}


def competing_approvals():
    rt,hooks,inst,now=fixture();runtimes=[another(rt) for _ in range(8)]
    original=hooks.approve_decision
    def slow(*a):time.sleep(.05);return original(*a)
    hooks.approve_decision=slow
    def attempt(r):
        try:choose(r,inst,now);return 'approved'
        except ValueError:return 'rejected'
    with ThreadPoolExecutor(8) as pool:results=list(pool.map(attempt,runtimes))
    assert results.count('approved')==1
    assert sum(c[0]=='approve_decision' for c in hooks.calls)==1
    assert sum(c[0]=='approve_commands' for c in hooks.calls)==1
    return {'connections':8,'results':results,'command_calls':1}


def expired_approval_vs_timer():
    rt,hooks,inst,now=fixture();runtimes=[another(rt) for _ in range(8)];due=now+timedelta(seconds=31)
    def attempt(pair):
        n,r=pair
        if n%2:return len(r.fire_timeouts(due))
        try:choose(r,inst,due);return 'approved'
        except ValueError:return 'rejected'
    with ThreadPoolExecutor(8) as pool:results=list(pool.map(attempt,enumerate(runtimes)))
    assert 'approved' not in results and not hooks.calls
    assert sum(x for x in results if isinstance(x,int))==1
    return {'results':results,'external_calls':len(hooks.calls)}


def rollback():
    rt,hooks,inst,now=fixture(False);before=rt.instance_view(inst['proc_inst_id'])
    def fail(_):raise RuntimeError('injected final write failure')
    rt.repo.update_instance=fail
    try:rt.submit(task(rt,inst,'task:diagnose')['id'],AGENT_OUTPUTS['task:diagnose'],now=now)
    except RuntimeError as e:assert 'injected' in str(e)
    else:raise AssertionError('failure was swallowed')
    after=another(rt).instance_view(inst['proc_inst_id'])
    assert after==before and 'TASK_COMPLETED' not in hooks.audits
    return {'instance_workitems_events_unchanged':True,'completion_audits':0}


def missed_callback():
    rt,hooks,inst,now=fixture();choose(rt,inst,now)
    assert task(rt,inst,'task:command')['status']=='SUBMITTED'
    hooks.inc_state='RESOLVED'
    restarted=another(rt);restarted.poll_once(now+timedelta(seconds=20))
    final=rt.repo.get_instance(inst['proc_inst_id'])
    assert final['end_event']=='ev:closed' and final['status']=='COMPLETED'
    assert sum(c[0]=='approve_commands' for c in hooks.calls)==1
    assert restarted.poll_once(now+timedelta(seconds=21))==0
    return {'new_runtime':True,'final':final['status'],'end':final['end_event'],'command_calls':1}


def competing_callbacks():
    rt,hooks,inst,now=fixture();choose(rt,inst,now);hooks.inc_state='RESOLVED'
    calls=[];original=hooks.exec_enterprise
    def slow(*a):calls.append(a);time.sleep(.03);return original(*a)
    hooks.exec_enterprise=slow
    runtimes=[another(rt) for _ in range(8)]
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda r:r.on_incident_update('RESOLVED','INC-1003-01',True,now),runtimes))
    assert rt.repo.get_instance(inst['proc_inst_id'])['end_event']=='ev:closed'
    assert len(calls)==1
    return {'callbacks':8,'work_order_calls':len(calls)}


def stale_callback_uses_current_incident():
    rt,hooks,inst,now=fixture();choose(rt,inst,now)
    hooks.incident_snapshot=lambda _:dict(state='ESCALATED',cleared=False)
    rt.on_incident_update('RESOLVED','INC-1003-01',True,now)
    final=rt.repo.get_instance(inst['proc_inst_id'])
    assert final['status']=='RUNNING' and engine.variables(final)['recovered'] is False
    assert task(rt,inst,'task:escalate')['status']=='IN_PROGRESS'
    assert task(rt,inst,'task:work-order')['status']=='TODO'
    return {'callback':'RESOLVED','current':'ESCALATED','human_escalation':'IN_PROGRESS','recovered':False}


def late_claim_error():
    rt,hooks,inst,now=fixture(False)
    wi,=rt.repo.fetch_pending_task('cliagents',rt.tenant_id,tenant_id=rt.tenant_id)
    rt.repo.save_task_result(wi['id'],AGENT_OUTPUTS['task:diagnose'],True,expected_consumer=rt.tenant_id)
    claimed,=rt.repo.claim_submitted(rt.consumer,tenant_id=rt.tenant_id)
    rt.process_workitem(claimed,now);before=rt.instance_view(inst['proc_inst_id'])
    another(rt).process_workitem(claimed,now);another(rt)._fail(claimed,RuntimeError('late'),now)
    assert rt.instance_view(inst['proc_inst_id'])==before
    return {'replay_and_late_error_unchanged':True}


def command_effect_before_sql_failure():
    rt,hooks,inst,now=fixture();write=rt.repo.update_workitem
    def fail_after_issue(wi):
        if wi['activity_id']=='task:command' and 'waiting ACK' in (wi.get('log') or ''):
            raise RuntimeError('injected SQL failure after external command')
        return write(wi)
    rt.repo.update_workitem=fail_after_issue
    choose(rt,inst,now)
    pending=task(rt,inst,'task:command')
    assert pending['status']=='SUBMITTED' and pending['retry']==1 and pending['consumer'] is None
    assert hooks.inc_state=='AWAITING_ACK'
    hooks.inc_state='RESOLVED'
    another(rt).poll_once(now+timedelta(seconds=20))
    assert rt.repo.get_instance(inst['proc_inst_id'])['end_event']=='ev:closed'
    assert sum(c[0]=='approve_commands' for c in hooks.calls)==1
    return {'failure_after_command':True,'durable_retry':pending['retry'],'command_calls':1,'end':'ev:closed'}


def service_queue_beyond_first_page():
    rt,hooks,inst,now=fixture();choose(rt,inst,now)
    template=rt.repo.get_instance(inst['proc_inst_id'])
    children=rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'],limit=None)
    # Valid copies of the waiting snapshot, each with separate instance/task IDs.
    # Low UUIDs ensure these 105 still-waiting commands precede the target.
    with rt.repo.event_transaction(rt.tenant_id+'-queue'):
        for n in range(105):
            copy=deepcopy(template);copy['proc_inst_id']='queue.'+str(uuid.uuid4());copy['root_proc_inst_id']=copy['proc_inst_id']
            engine.set_variables(rt.defn,copy,{'incident':f'WAIT-{n}'})
            copy['start_event_id']=f'queue-{n}'
            rt.repo.insert_instance(copy)
            for row in children:
                child=deepcopy(row);child.update(id=str(uuid.UUID(int=n+1)) if row['activity_id']=='task:command' else str(uuid.uuid4()),
                                                proc_inst_id=copy['proc_inst_id'],root_proc_inst_id=copy['proc_inst_id'])
                rt.repo.insert_workitems([child])
    hooks.incident_state=lambda inc:'RESOLVED' if inc=='INC-1003-01' else 'AWAITING_ACK'
    first=rt.repo.waiting_services(rt.tenant_id)
    assert len(first)==100 and task(rt,inst,'task:command')['id'] not in {x['id'] for x in first}
    another(rt).poll_once(now+timedelta(seconds=20))
    assert rt.repo.get_instance(inst['proc_inst_id'])['end_event']=='ev:closed'
    with psycopg.connect(DSN) as c:
        waiting=c.execute("select count(*) from todolist where tenant_id=%s and status='SUBMITTED'",(rt.tenant_id,)).fetchone()[0]
    assert waiting==105 and sum(c[0]=='approve_commands' for c in hooks.calls)==1
    return {'waiting_ahead':105,'first_page':len(first),'remaining_waiting':waiting,'target_end':'ev:closed','command_calls':1}


def main():
    try:
        for case in [timer_beyond_page,competing_timers,competing_approvals,expired_approval_vs_timer,
                     rollback,missed_callback,competing_callbacks,stale_callback_uses_current_incident,late_claim_error,
                     command_effect_before_sql_failure,service_queue_beyond_first_page]:
            try:
                detail=case();REPORT['checks'].append(dict(name=case.__name__,ok=True,detail=detail))
                print(case.__name__+': PASS',flush=True)
            except Exception:
                REPORT['checks'].append(dict(name=case.__name__,ok=False,error=traceback.format_exc()))
                print(case.__name__+': FAIL\n'+traceback.format_exc(),flush=True)
    finally:
        with psycopg.connect(DSN) as c:
            pids=[r[0] for r in c.execute('select proc_inst_id from bpm_proc_inst where tenant_id=any(%s)',(TENANTS,)).fetchall()]
            REPORT['fixture_instances']=pids
            c.execute('delete from events where proc_inst_id=any(%s)',(pids,))
            for tenant in TENANTS:
                c.execute('delete from bpm_proc_inst where tenant_id=%s',(tenant,))
                c.execute('delete from proc_def_version where tenant_id=%s',(tenant,))
                c.execute('delete from proc_def where tenant_id=%s',(tenant,))
                c.execute('delete from tenants where id=%s',(tenant,))
            REPORT['remaining_instances']=c.execute('select count(*) from bpm_proc_inst where tenant_id=any(%s)',(TENANTS,)).fetchone()[0]
            REPORT['remaining_events']=c.execute('select count(*) from events where proc_inst_id=any(%s)',(pids,)).fetchone()[0]
        REPORT['passed']=sum(c['ok'] for c in REPORT['checks']);REPORT['total']=len(REPORT['checks'])
        OUT.write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"{REPORT['passed']}/{REPORT['total']}; remaining={REPORT['remaining_instances']}")
    return 0 if REPORT['passed']==REPORT['total'] else 1


if __name__=='__main__':sys.exit(main())
