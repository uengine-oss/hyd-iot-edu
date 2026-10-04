"""Hold parent, let a writer start, then lock child: reproduces trigger deadlocks.

--baseline loads the preserved A021 PgRepo before the lock-order fix. Run that
before applying migration 000004. External effects are FakeHooks only.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import time
import uuid

from probe_instance_recovery import fixture,task,TENANTS,DSN,ROOT
import psycopg
from procsvc import procdb


def main(baseline):
    repo_class=procdb.PgRepo
    if baseline:
        spec=importlib.util.spec_from_file_location('a021_old_procdb',ROOT/'.evidence/reaudit/a021-source/procdb.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);repo_class=mod.PgRepo
    checks=[]
    try:
        for kind in ('save','draft','release','update','worker_claim','engine_claim','rpc_save'):
            rt,hooks,inst,now=fixture(False);wi=task(rt,inst,'task:diagnose');tag='lockprobe-'+uuid.uuid4().hex[:8]
            repo=repo_class(DSN+'?application_name='+tag)
            with psycopg.connect(DSN) as c:
                if kind=='engine_claim':c.execute("update todolist set status='SUBMITTED',consumer=null where id=%s",(wi['id'],))
                elif kind!='worker_claim':c.execute("update todolist set draft_status='STARTED',consumer='fixture' where id=%s",(wi['id'],))
            def action():
                if kind=='save':return repo.save_task_result(wi['id'],{'test':True},True,expected_consumer='fixture')
                if kind=='draft':return repo.set_draft_status(wi['id'],'FAILED',expected_consumer='fixture')
                if kind=='release':return repo.release_worker_claim(wi['id'],'fixture')
                if kind=='update':return repo.update_workitem(repo.get_workitem(wi['id'])|{'log':'lock probe'})
                if kind=='worker_claim':return repo.fetch_pending_task('cliagents','fixture',tenant_id=rt.tenant_id)
                if kind=='engine_claim':return repo.claim_submitted('fixture',tenant_id=rt.tenant_id)
                with psycopg.connect(DSN+'?application_name='+tag) as c:
                    c.execute('select save_task_result(%s,%s,true)',(wi['id'],psycopg.types.json.Jsonb({'test':True})))
                return True
            errors=[];waited=False;result=None
            with ThreadPoolExecutor(1) as pool:
                try:
                    with psycopg.connect(DSN) as c:
                        c.execute("set local statement_timeout='5s'")
                        c.execute('select proc_inst_id from bpm_proc_inst where proc_inst_id=%s for update',(inst['proc_inst_id'],))
                        future=pool.submit(action)
                        until=time.monotonic()+3
                        with psycopg.connect(DSN,autocommit=True) as monitor:
                            while not future.done() and time.monotonic()<until:
                                waited=bool(monitor.execute("select 1 from pg_stat_activity where application_name=%s and wait_event_type='Lock'",(tag,)).fetchone())
                                if waited:break
                                time.sleep(.02)
                        c.execute('select id from todolist where proc_inst_id=%s order by id for update',(inst['proc_inst_id'],)).fetchall()
                except Exception as e:errors.append(type(e).__name__+': '+str(e))
                try:result=future.result(timeout=8)
                except Exception as e:errors.append(type(e).__name__+': '+str(e))
            if not baseline and not errors and kind in ('worker_claim','engine_claim'):
                assert result==[],result
                result=action();assert len(result)==1,result
            ok=bool(errors) if baseline else not errors
            checks.append(dict(kind=kind,ok=ok,waited=waited,errors=errors,result_rows=len(result) if isinstance(result,list) else result))
            print(kind, 'REPRODUCED' if baseline and ok else 'PASS' if ok else 'FAIL',flush=True)
    finally:
        with psycopg.connect(DSN) as c:
            pids=[r[0] for r in c.execute('select proc_inst_id from bpm_proc_inst where tenant_id=any(%s)',(TENANTS,)).fetchall()]
            c.execute('delete from events where proc_inst_id=any(%s)',(pids,))
            c.execute('delete from bpm_proc_inst where tenant_id=any(%s)',(TENANTS,))
            c.execute('delete from proc_def_version where tenant_id=any(%s)',(TENANTS,))
            c.execute('delete from proc_def where tenant_id=any(%s)',(TENANTS,))
            c.execute('delete from tenants where id=any(%s)',(TENANTS,))
        report=dict(baseline=baseline,checks=checks,passed=sum(x['ok'] for x in checks),total=len(checks),fixture_instances=pids)
        path=ROOT/'.evidence/reaudit'/('process-lock-order-baseline.json' if baseline else 'process-lock-order.json')
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(f"{report['passed']}/{report['total']}")
    return 0 if report['passed']==report['total'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',action='store_true');args=p.parse_args()
    raise SystemExit(main(args.baseline))
