"""Real PG/Neo4j projection recovery; isolated retained tenant, no agent/PLC."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/process'), str(ROOT/'common')]
import psycopg
from neo4j import GraphDatabase
from procsvc import engine, instances, procdb

DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True); ap.add_argument('--crash',action='store_true')
    args=ap.parse_args(); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    env=dict(v.split('=',1) for v in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    driver=GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1)))
    def query(q,**params):
        with driver.session() as s:
            return s.execute_write(lambda tx:[r.data() for r in tx.run(q,**params)])
    def save(name,value):
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    if args.crash:
        meta=json.loads((out/'fixture.json').read_text(encoding='utf8'))
        def after_graph(q,**params):
            query(q,**params)
            os._exit(73)
        rt=instances.InstanceRuntime(procdb.PgRepo(DSN),engine.Definition.from_dict(meta['definition']),
            instances.Hooks(record_cypher=after_graph),tenant_id=meta['tenant'])
        rt._project({'proc_inst_id':meta['pid']})
        raise AssertionError('crash point was not reached')
    checks=[]
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)}); save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True); assert ok,name
    tenant='projection-'+uuid.uuid4().hex[:10]
    raw=json.loads((ROOT/'docs/examples/rework-inspection-v1.json').read_text(encoding='utf8'))
    with psycopg.connect(DSN) as c:c.execute('insert into tenants(id,name) values(%s,%s)',(tenant,'A043 retained projection fixture'))
    captured=[]
    def writer(q,**params):
        captured.append((q,deepcopy(params)))
        return query(q,**params)
    def make(hook=writer):
        return instances.InstanceRuntime(procdb.PgRepo(DSN),engine.Definition.from_dict(raw),
            instances.Hooks(record_cypher=hook,query_cypher=query),tenant_id=tenant)
    # A real refused Bolt connection, without taking shared Neo4j down.
    offline=GraphDatabase.driver('bolt://127.0.0.1:1',connection_timeout=1,max_transaction_retry_time=0)
    def unavailable(q,**params):
        with offline.session() as s:s.run(q,**params).consume()
    rt=make(unavailable)
    inst=rt.start_definition(raw['processDefinitionId'],'1',str(uuid.uuid4()),{'score':2}); pid=inst['proc_inst_id']
    meta={'tenant':tenant,'definition':raw,'pid':pid};save('fixture',meta)
    status=rt.repo.projection_status(tenant,pid);save('outage',status)
    check('real connection failure leaves committed source and durable error',status['pending']>0 and status['last_error'] and rt.repo.get_instance(pid)['status']=='RUNNING')
    rt=make();rt._project(inst)
    view=rt.execution_view(pid);save('recovered',view)
    check('fresh repository recovers source into actual graph',view['graph']['instance']['status']=='RUNNING' and view['projection']['pending']==0)
    obsolete=captured[-1]
    try:
        with rt.repo.instance_transaction(tenant,pid):
            changed=rt.repo.get_instance(pid);changed['status']='COMPLETED';rt.repo.update_instance(changed)
            raise RuntimeError('planned rollback')
    except RuntimeError:pass
    check('rollback leaves source and outbox unchanged',rt.repo.get_instance(pid)['status']=='RUNNING' and rt.repo.projection_status(tenant,pid)['pending']==0)
    # No runtime hook: triggers catch direct DB/worker writes too.
    with psycopg.connect(DSN) as c:c.execute("update todolist set draft_status='STARTED' where proc_inst_id=%s and activity_id='measure'",(pid,))
    rt.reconcile_projections()
    check('direct SQL child mutation reaches graph through poller',any(w['activity_id']=='measure' and w['draft_status']=='STARTED' for w in rt.execution_view(pid)['graph']['workitems']))
    # Freeze snapshot, commit another source update, then acknowledge only the
    # visible events. Later changes must remain pending and get their own pass.
    with psycopg.connect(DSN) as c:c.execute('update bpm_proc_inst set proc_inst_name=%s where proc_inst_id=%s',('snapshot-before',pid))
    with rt.repo.projection_snapshot(tenant,pid) as snap:
        with psycopg.connect(DSN) as c:c.execute('update bpm_proc_inst set proc_inst_name=%s where proc_inst_id=%s',('snapshot-after',pid))
        rt._write_projection(pid,snap);rt.repo.finish_projection(snap)
    check('concurrent source commit remains queued',rt.repo.projection_status(tenant,pid)['pending']>0)
    rt.reconcile_projections()
    check('next pass reflects concurrent source commit',rt.execution_view(pid)['graph']['instance']['name']=='snapshot-after')
    # An older sequence number can commit later. Ack must not use <= max(id).
    early=psycopg.connect(DSN)
    early.execute('insert into execution_projection_outbox(tenant_id,proc_inst_id) values(%s,%s)',(tenant,pid))
    with psycopg.connect(DSN) as c:c.execute('insert into execution_projection_outbox(tenant_id,proc_inst_id) values(%s,%s)',(tenant,pid))
    with rt.repo.projection_snapshot(tenant,pid) as snap:
        early.commit(); early.close()
        rt._write_projection(pid,snap);rt.repo.finish_projection(snap)
    check('late-committed lower sequence is not lost',rt.repo.projection_status(tenant,pid)['pending']==1)
    rt.reconcile_projections()
    before=rt.execution_view(pid)['graph']['instance']
    query(obsolete[0],**obsolete[1])
    check('delayed obsolete write cannot regress graph',rt.execution_view(pid)['graph']['instance']==before)
    with psycopg.connect(DSN) as c:c.execute('update bpm_proc_inst set proc_inst_name=%s where proc_inst_id=%s',('crash-after-graph',pid))
    child=subprocess.run([sys.executable,__file__,'--out',str(out),'--crash'],capture_output=True,text=True)
    save('crash',{'returncode':child.returncode,'stdout':child.stdout,'stderr':child.stderr})
    check('process dies after graph commit before queue acknowledgement',child.returncode==73 and rt.repo.projection_status(tenant,pid)['pending']>0)
    rt=make();rt.reconcile_projections()
    view=rt.execution_view(pid);save('after-crash-recovery',view)
    check('new process state recovers idempotently after crash',view['projection']['pending']==0 and view['graph']['instance']['name']=='crash-after-graph' and len(view['graph']['workitems'])==len(rt.repo.list_workitems(proc_inst_id=pid,limit=None)))
    with psycopg.connect(DSN) as c:c.execute('update bpm_proc_inst set is_deleted=true where proc_inst_id=%s',(pid,))
    rt.reconcile_projections();check('source soft deletion removes execution graph',rt.execution_view(pid)['graph'] is None)
    query(obsolete[0],**obsolete[1]);check('old write cannot resurrect deleted graph',rt.execution_view(pid)['graph'] is None)
    with psycopg.connect(DSN) as c:c.execute('update bpm_proc_inst set is_deleted=false where proc_inst_id=%s',(pid,))
    rt.reconcile_projections();check('source restoration produces current graph',rt.execution_view(pid)['graph']['instance']['name']=='crash-after-graph')
    # Keep a closed fixture; no human or physical action is claimed.
    with psycopg.connect(DSN) as c:
        c.execute("update todolist set status='CANCELLED' where proc_inst_id=%s",(pid,))
        c.execute("update bpm_proc_inst set status='COMPLETED',current_activity_ids='{}',end_date=now() where proc_inst_id=%s",(pid,))
    rt.reconcile_projections();save('final',rt.execution_view(pid))
    check('fixture graph has no duplicate workitems',query('MATCH (w:WorkItem)-[:IN_INSTANCE]->(:ProcessInstance {id:$id}) RETURN count(w) AS n',id=pid)[0]['n']==len(rt.repo.list_workitems(proc_inst_id=pid,limit=None)))
    offline.close();driver.close()


if __name__=='__main__':main()
