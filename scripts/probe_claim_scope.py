"""Actual PostgreSQL targeted bridge claim and competing consumers; scoped cleanup."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import uuid

from probe_definition_registry import DSN, ROOT
from probe_registered_codex import definition
import psycopg
from procsvc import engine,instances,instance_mode,procdb


def main():
    prefix='claim-'+uuid.uuid4().hex[:8]
    tenant=prefix; other=prefix+'-other'
    repo=procdb.PgRepo(DSN)
    report={'fixture':prefix,'checks':{}}
    out=ROOT/'.evidence/reaudit/claim-scope-live.json'
    def check(name,ok,detail=None):
        report['checks'][name]={'passed':bool(ok),'detail':detail}
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,'PASS' if ok else 'FAIL',flush=True);assert ok,name
    try:
        with psycopg.connect(DSN,autocommit=True) as c:
            for t in (tenant,other):c.execute('insert into tenants(id,name) values(%s,%s)',(t,t))
        rt=instances.InstanceRuntime(repo,engine.Definition.from_dict(definition(prefix,'1')),instances.Hooks(),tenant_id=tenant)
        instance_mode._runtime=rt
        runs=[rt.start_definition(prefix,'1',f'e-{i}') for i in range(14)]
        rows=[repo.list_workitems(proc_inst_id=i['proc_inst_id'])[0] for i in runs]
        rows[1].update(draft_status='FB_REQUESTED',draft={'text':'previous attempt'})
        repo.update_workitem(rows[1])
        before={w['id']:repo.get_workitem(w['id']) for w in rows}
        got=instance_mode._claim_own(runs[0]['proc_inst_id'])
        check('first_target_does_not_claim_rest_of_batch',got['id']==rows[0]['id'] and
              all(repo.get_workitem(k)==v for k,v in before.items() if k!=got['id']))
        got=instance_mode._claim_own(runs[11]['proc_inst_id'])
        check('target_beyond_first_ten_is_claimed',got is not None and got['id']==rows[11]['id'])
        check('feedback_request_is_unchanged',repo.get_workitem(rows[1]['id'])==before[rows[1]['id']])
        target=runs[12]['proc_inst_id']
        check('wrong_tenant_cannot_claim_named_instance',repo.fetch_pending_task('cliagents','foreign',tenant_id=other,proc_inst_id=target)==[])
        def compete(n):return repo.fetch_pending_task('cliagents',f'consumer-{n}',tenant_id=tenant,proc_inst_id=target)
        with ThreadPoolExecutor(max_workers=8) as pool:claims=list(pool.map(compete,range(8)))
        check('eight_consumers_only_one_wins_same_target',sum(len(c)for c in claims)==1,[len(c)for c in claims])
        check('already_claimed_target_not_reissued',instance_mode._claim_own(target) is None)
        remaining=repo.fetch_pending_task('cliagents','normal-worker',limit=20,tenant_id=tenant)
        check('ordinary_worker_still_receives_remaining_queue',len(remaining)==11 and
              rows[1]['id'] in {x['id']for x in remaining},len(remaining))
    finally:
        with psycopg.connect(DSN,autocommit=True) as c:
            for table in ('events','todolist','bpm_proc_inst'):
                if table=='events':c.execute('delete from events where proc_inst_id in(select proc_inst_id from bpm_proc_inst where tenant_id=%s)',(tenant,))
                else:c.execute(f'delete from {table} where tenant_id=%s',(tenant,))
            c.execute('delete from proc_def_version where tenant_id=%s',(tenant,))
            c.execute('delete from proc_def where tenant_id=%s',(tenant,))
            c.execute('delete from tenants where id=any(%s)',([tenant,other],))
            report['remaining_instances']=c.execute('select count(*) from bpm_proc_inst where tenant_id=%s',(tenant,)).fetchone()[0]
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
