"""Real SQLite/PG/Neo4j knowledge join changes; isolated tenant, no agent/PLC."""
import argparse
from copy import deepcopy
import json
import logging
from pathlib import Path
import subprocess
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/process'),str(ROOT/'common')]
import psycopg
from neo4j import GraphDatabase
from procsvc import engine,instances,procdb,machine
from procsvc.store import Store
from procsvc.case_projection import CaseProjector

DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'


def run():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',action='store_true');args=ap.parse_args()
    tag='a048-'+uuid.uuid4().hex[:10];tenant=tag;out=ROOT/'.evidence/reaudit'/('a048-red' if args.baseline else 'a048-live')/tag
    out.mkdir(parents=True);checks=[]
    logging.getLogger('neo4j.notifications').setLevel(logging.ERROR)
    env=dict(v.split('=',1) for v in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    driver=GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1)))
    def q(query,**params):
        with driver.session() as session:return session.execute_write(lambda tx:tx.run(query,**params).data())
    def save(name,value):(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,ok):
        checks.append(dict(name=name,passed=bool(ok)));save('checks',checks);print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if not args.baseline:assert ok,name
    store=Store(out/'source.sqlite3');repo=procdb.PgRepo(DSN)
    raw=json.loads((ROOT/'docs/examples/rework-inspection-v1.json').read_text(encoding='utf8'))
    raw['ontologyRef']='proc:'+tag;raw['roles'][0]['endpoint']='role:'+tag
    for item in raw['activities']+raw['events']:item['ontologyRef']='semantic:'+tag+':'+item['id']
    with psycopg.connect(DSN) as conn:conn.execute('insert into tenants(id,name) values(%s,%s)',(tenant,'[회귀 검사] A048 격리 투영 인수 시험'))
    owned=['proc:'+tag,'role:'+tag]+[r['ontologyRef'] for r in raw['activities']+raw['events']]+['skill:'+tag]
    q('CREATE (:Role {id:$role,name:$name}),(:Process {id:$process,name:$name})',role='role:'+tag,process=raw['ontologyRef'],name=tag)
    for item in raw['activities']+raw['events']:
        q('MATCH (p:Process {id:$process}) CREATE (n:FlowNode {id:$id,name:$name}) CREATE (p)-[:HAS_NODE]->(n)',process=raw['ontologyRef'],id=item['ontologyRef'],name=item['id'])
    rt=instances.InstanceRuntime(repo,engine.Definition.from_dict(raw),instances.Hooks(record_cypher=q,query_cypher=q),tenant_id=tenant)
    inst=rt.start_definition(raw['processDefinitionId'],'1',str(uuid.uuid4()),{'score':2});pid=inst['proc_inst_id']
    inc=machine.Incident.from_card('INC-'+tag,{'alert':{'alertId':tag,'asset':'HYD-01','pattern':'COOLER_DEGRADATION'}})
    inc.state='AWAITING_APPROVAL'
    decision=dict(id='DEC-'+tag,created=inc.created,state='APPROVED',chosen='skill:'+tag,approvedRole='role:'+tag,origin={'incident':inc.id},history=[dict(state='APPROVED',t=inc.created)])
    store.save({inc.id:inc},{decision['id']:decision},[])
    worker=CaseProjector(store,q,lambda sid:repo.enqueue_incident_projections(tenant,sid))
    worker.drain();before_source=store.db.execute('select body from snapshot where id=1').fetchone()[0];before_pg=deepcopy(repo.get_instance(pid))
    before_items=deepcopy(repo.list_workitems(proc_inst_id=pid,limit=None))
    save('fixture',dict(tenant=tenant,pid=pid,incident=inc.id,decision=decision,definition=raw))
    if not args.baseline:
        from procsvc.knowledge_projection import KnowledgeReconciler
        watcher=KnowledgeReconciler(store,q,tenant,repo)
        watcher.scan();worker.drain();rt.reconcile_projections()
    def cycle():
        if not args.baseline:watcher.scan()
        worker.drain();rt.reconcile_projections()
    def chosen():return q('MATCH (:DecisionCase {id:$id})-[:CHOSE]->(s) RETURN s.id AS id',id='case:'+decision['id'])
    def mapped():return q('MATCH (:ProcessVersion {tenant_id:$tenant})-[:HAS_NODE]->(n)-[:MAPS_TO]->(s {id:$id}) RETURN n.id AS id',tenant=tenant,id=raw['activities'][0]['ontologyRef'])
    try:
        check('fixture execution and original semantic link actually exist',len(mapped())==1 and rt.execution_view(pid)['graph'] is not None)
        q('CREATE (:Skill {id:$id,name:$id})',id='skill:'+tag)
        cycle()
        check('knowledge created after case delivery repairs missing chosen relation',chosen()==[dict(id='skill:'+tag)])
        q('MATCH (p:Process {id:$process})-[r:HAS_NODE]->(n {id:$id}) DELETE r',process=raw['ontologyRef'],id=raw['activities'][0]['ontologyRef'])
        # Even explicit source re-projection could not remove stale MAPS_TO.
        if args.baseline:repo.update_instance(repo.get_instance(pid))
        cycle()
        check('removed semantic membership removes obsolete MAPS_TO',not mapped())
        if not args.baseline:
            warnings=rt.execution_view(pid)['graph']['warnings']
            check('missing semantic mapping remains visible as a warning',any('measure' in w for w in warnings))
            q('MATCH (p:Process {id:$process}),(n:FlowNode {id:$id}) CREATE (p)-[:HAS_NODE]->(n)',process=raw['ontologyRef'],id=raw['activities'][0]['ontologyRef'])
            cycle();check('restored membership reconnects and clears warning',len(mapped())==1 and not any('measure' in w for w in rt.execution_view(pid)['graph']['warnings']))
            # Replace the node with identical logical properties: element identity
            # must detect the detached historical edge too.
            q('MATCH (s:Skill {id:$id}) DETACH DELETE s',id='skill:'+tag)
            q('CREATE (:Skill {id:$id,name:$id})',id='skill:'+tag)
            cycle();check('same-id replacement repairs severed case relation',len(chosen())==1)
            count=store.db.execute('select count(*) from case_projection_outbox').fetchone()[0]
            watcher.scan();worker.drain();rt.reconcile_projections()
            check('unchanged graph does not recursively requeue its own projections',store.db.execute('select count(*) from case_projection_outbox').fetchone()[0]==count)
            prior=watcher.status()['queued']
            q('MATCH (r:Role {id:$id}) SET r.code=$code',id='role:'+tag,code=tag)
            child_code='''
import json,os,subprocess,sys
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'it/process'),str(Path.cwd()/'common')]
from neo4j import GraphDatabase
from procsvc.store import Store
from procsvc.procdb import PgRepo
from procsvc.knowledge_projection import KnowledgeReconciler
env=dict(v.split('=',1) for v in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
driver=GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1)))
def q(query):
    with driver.session() as session:return session.run(query).data()
store=Store(sys.argv[1])
store.enqueue_knowledge_cases=lambda *args:os._exit(73)
KnowledgeReconciler(store,q,sys.argv[2],PgRepo(sys.argv[3])).scan()
'''
            child=subprocess.run([sys.executable,'-c',child_code,str(out/'source.sqlite3'),tenant,DSN],capture_output=True,cwd=ROOT)
            save('crash-after-pg',dict(exit=child.returncode,stderr=child.stderr.decode(errors='replace')))
            check('actual process death between stores leaves checkpoint unchanged and PG job pending',child.returncode==73 and store.knowledge_projection_checkpoint(watcher.key)==prior and repo.projection_status(tenant,pid)['pending']>0)
            store.db.close();store=Store(out/'source.sqlite3')
            watcher=KnowledgeReconciler(store,q,tenant,repo)
            worker=CaseProjector(store,q,lambda sid:repo.enqueue_incident_projections(tenant,sid))
            cycle()
            check('new reconciler resumes both stores after the interrupted enqueue',store.case_projection_status()['pending']==0 and repo.projection_status(tenant,pid)['pending']==0 and watcher.status()['queued']['digest']==watcher.observed)
            check('knowledge reconciliation never changes saved judgment, consent or task state',store.db.execute('select body from snapshot where id=1').fetchone()[0]==before_source and repo.get_instance(pid)==before_pg and repo.list_workitems(proc_inst_id=pid,limit=None)==before_items)
    finally:
        save('case',q('MATCH (n:DecisionCase {id:$id}) RETURN n{.*} AS source',id='case:'+decision['id']))
        save('execution',rt.execution_view(pid));save('status',store.case_projection_status())
        # Own disposable Neo4j fixtures only; the dedicated SQL tenant and source
        # file remain as evidence. They are not processed by the hyd worker.
        q('MATCH (n) WHERE n.id IN $ids OR n.tenant_id=$tenant DETACH DELETE n',ids=owned+[inc.id,'case:'+decision['id'],'Incident:'+inc.id,'DecisionCase:'+decision['id']],tenant=tenant)
        driver.close();store.db.close()
    print(json.dumps(dict(out=str(out),checks=checks),ensure_ascii=False))
    assert all(c['passed'] for c in checks)


if __name__=='__main__':run()
