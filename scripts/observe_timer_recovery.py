"""Observe A021 with real PostgreSQL and fake external effects, isolated tenant.

This records defects, not a passing recovery test. It never touches a real PLC.
"""
from datetime import datetime, timedelta, timezone
import json
import sys
import uuid

from probe_definition_registry import ROOT, DSN
import psycopg
from procsvc import engine, instances, procdb

sys.path.insert(0, str(ROOT/'tests'))
from test_instances import FakeHooks, AGENT_OUTPUTS, ALERT, DEF_PATH


def main():
    tenant = 'timer-observe-' + uuid.uuid4().hex[:8]
    out = ROOT/'.evidence/reaudit'/f'{tenant}.json'
    report = {'tenant':tenant, 'scope':'real PostgreSQL; FakeHooks for Incident/PLC/CMMS; observation only'}
    repo = procdb.PgRepo(DSN)
    now = datetime.now(timezone.utc)
    hooks = FakeHooks()
    try:
        with psycopg.connect(DSN) as c:
            c.execute('insert into tenants(id,name) values(%s,%s)',(tenant,tenant))
        d = engine.Definition.load(DEF_PATH)
        rt = instances.InstanceRuntime(repo,d,hooks,tenant_id=tenant)
        inst = rt.on_alert_raise(dict(ALERT,alertId=tenant),now=now)
        for _ in range(4):
            wi, = repo.fetch_pending_task('cliagents',tenant,tenant_id=tenant)
            repo.save_task_result(wi['id'],AGENT_OUTPUTS[wi['activity_id']],True,expected_consumer=tenant)
            assert rt.poll_once(now=now)==1
        rows = repo.list_workitems(proc_inst_id=inst['proc_inst_id'])
        timer = next(x for x in rows if x['activity_id']=='ev:select-timeout')
        selection = next(x for x in rows if x['activity_id']=='task:select')
        # Valid independent one-task executions occupy the normal display page.
        raw = {'processDefinitionId':tenant,'processDefinitionName':'older human work','version':'1',
               'roles':[{'name':'operator','endpoint':'role:operator'}], 'data':[],
               'activities':[{'id':'review','type':'userTask','role':'operator','name':'review'}],
               'events':[{'id':'start','type':'startEvent'},{'id':'end','type':'endEvent'}],
               'gateways':[], 'sequences':[{'id':'s1','source':'start','target':'review'},{'id':'s2','source':'review','target':'end'}]}
        noise = engine.Definition.from_dict(raw)
        repo.upsert_proc_def(raw,tenant)
        for n in range(205):
            i = engine.new_instance(noise,{},tenant_id=tenant,now=now-timedelta(days=1,seconds=n))
            a = engine.start(noise,i,now=now-timedelta(days=1,seconds=n))
            repo.insert_instance(i); repo.insert_workitems(a.created); repo.update_instance(i)
        due = now+timedelta(minutes=1)
        page = repo.list_workitems(status='IN_PROGRESS',tenant_id=tenant)
        fired = [len(rt.fire_timeouts(now=due)) for _ in range(3)]
        report['timer'] = {'page_rows':len(page),'timer_in_page':timer['id'] in {x['id'] for x in page},
                           'due_date':timer['due_date'],'evaluated_at':due.isoformat(),'three_fired_counts':fired,
                           'saved_status':repo.get_workitem(timer['id'])['status']}
        assert fired==[0,0,0] and report['timer']['saved_status']=='IN_PROGRESS', 'baseline changed; review observation'
        rt.select(selection['id'],'DEC-1003-001','skill:fan-max-derate',by='fixture',role='role:prod-mgr',now=now)
        hooks.inc_state = 'RESOLVED'  # deliberately suppress the callback
        restarted = instances.InstanceRuntime(repo,d,hooks,tenant_id=tenant,consumer=tenant+'-restarted')
        polls = [restarted.poll_once(now=due) for _ in range(3)]
        command = next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='task:command')
        report['callback'] = {'incident_state':hooks.inc_state,'recreated_runtime':True,'three_claim_counts':polls,
                              'command_status':command['status'],'consumer':command['consumer'],
                              'instance_status':repo.get_instance(inst['proc_inst_id'])['status'],
                              'fake_command_calls':sum(x[0]=='approve_commands' for x in hooks.calls)}
        assert polls==[0,0,0] and command['status']=='SUBMITTED', 'baseline changed; review observation'
    finally:
        with psycopg.connect(DSN) as c:
            c.execute('delete from bpm_proc_inst where tenant_id=%s',(tenant,))
            c.execute('delete from proc_def_version where tenant_id=%s',(tenant,))
            c.execute('delete from proc_def where tenant_id=%s',(tenant,))
            c.execute('delete from tenants where id=%s',(tenant,))
            report['remaining_instances'] = c.execute('select count(*) from bpm_proc_inst where tenant_id=%s',(tenant,)).fetchone()[0]
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
