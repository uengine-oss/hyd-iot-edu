"""Incident routing lookup is independent of list-page size and tenant collisions."""
import json
import uuid
from datetime import datetime,timedelta,timezone

from probe_definition_registry import ROOT,DSN
from probe_registered_codex import definition
import psycopg
from procsvc import engine,instances,procdb


def main():
    tenant='lookup-'+uuid.uuid4().hex[:8];foreign=tenant+'-foreign';repo=procdb.PgRepo(DSN)
    out=ROOT/'.evidence/reaudit/incident-lookup-live.json';report={'fixture':tenant,'checks':{}}
    def check(name,ok):
        report['checks'][name]=bool(ok);print(name,'PASS' if ok else 'FAIL',flush=True)
        out.write_text(json.dumps(report,indent=2),encoding='utf-8');assert ok,name
    try:
        with psycopg.connect(DSN,autocommit=True) as c:
            for t in (tenant,foreign):c.execute('insert into tenants(id,name) values(%s,%s)',(t,t))
        d=engine.Definition.from_dict(definition(tenant,'1'))
        rt=instances.InstanceRuntime(repo,d,instances.Hooks(),tenant_id=tenant)
        now=datetime.now(timezone.utc)
        target=engine.new_instance(d,{'incident':'shared'},tenant_id=tenant,now=now)
        repo.insert_instance(target)
        for n in range(105):
            repo.insert_instance(engine.new_instance(d,{'incident':f'noise-{n}'},tenant_id=tenant,now=now+timedelta(seconds=n+1)))
        other=engine.new_instance(d,{'incident':'shared'},tenant_id=foreign,now=now+timedelta(seconds=106));repo.insert_instance(other)
        check('target_is_outside_normal_first_page',target['proc_inst_id'] not in {i['proc_inst_id']for i in repo.list_instances(tenant_id=tenant)})
        check('lookup_filters_incident_and_tenant_before_limit',rt.instance_of_incident('shared')['proc_inst_id']==target['proc_inst_id'])
        check('foreign_tenant_can_only_find_its_own',repo.list_instances(status='RUNNING',tenant_id=foreign,incident_id='shared',limit=1)[0]['proc_inst_id']==other['proc_inst_id'])
        target['status']='COMPLETED';repo.update_instance(target)
        check('closed_target_does_not_fall_back_to_foreign',rt.instance_of_incident('shared') is None)
        check('unknown_incident_is_not_first_row',rt.instance_of_incident('missing') is None)
    finally:
        with psycopg.connect(DSN,autocommit=True) as c:
            c.execute('delete from bpm_proc_inst where tenant_id=any(%s)',([tenant,foreign],))
            c.execute('delete from proc_def_version where tenant_id=%s',(tenant,))
            c.execute('delete from proc_def where tenant_id=%s',(tenant,))
            c.execute('delete from tenants where id=any(%s)',([tenant,foreign],))
            report['remaining_instances']=c.execute('select count(*) from bpm_proc_inst where tenant_id=any(%s)',([tenant,foreign],)).fetchone()[0]
        out.write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
