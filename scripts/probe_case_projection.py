"""Real SQLite/PG/Neo4j case recovery, isolated retained sources, no agent or PLC."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/process'),str(ROOT/'common')]
import psycopg
from neo4j import GraphDatabase
from procsvc import engine,instances,procdb,machine
from procsvc.store import Store
from procsvc.case_projection import CaseProjector

DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--crash',action='store_true')
    args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    env=dict(v.split('=',1) for v in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    driver=GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1)))
    def query(q,**p):
        with driver.session() as s:return s.execute_write(lambda tx:[r.data() for r in tx.run(q,**p)])
    query('CREATE CONSTRAINT case_projection_id IF NOT EXISTS FOR (n:CaseProjection) REQUIRE n.id IS UNIQUE')
    store=Store(out/'cases.sqlite3')
    if args.crash:
        def after_write(q,**p):
            query(q,**p);os._exit(73)
        CaseProjector(store,after_write).drain()
        raise AssertionError('crash point not reached')
    def save(name,v):(out/(name+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    checks=[]
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)});save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    unique=uuid.uuid4().hex[:10];tenant='case-projection-'+unique
    inc=machine.Incident.from_card('INC-A044-'+unique,{'alert':{'alertId':'A044-'+unique,'asset':'HYD-01','pattern':'COOLER_DEGRADATION'},'topCause':'cause:cooler-fin-fouling'})
    inc.state='AWAITING_APPROVAL';sources={inc.id:inc}
    d={'id':'DEC-A044-'+unique,'created':inc.created,'state':'APPROVED','chosen':'skill:fan-max',
       'approvedRole':'role:operator','origin':{'incident':inc.id},'history':[{'state':'APPROVED','t':inc.created}]}
    book={d['id']:d};store.save(sources,book,[])
    # PG execution exists before its Incident graph source, reproducing the old
    # dangling HANDLES edge. Its source and decision are labelled fixtures.
    with psycopg.connect(DSN) as c:c.execute('insert into tenants(id,name) values(%s,%s)',(tenant,'[회귀 검사] A044 보존 사례 시험'))
    repo=procdb.PgRepo(DSN)
    definition=engine.Definition.load(ROOT/'it/process/definitions/anomaly_response.json')
    rt=instances.InstanceRuntime(repo,definition,instances.Hooks(new_incident=lambda alert:{'id':inc.id},record_cypher=query,query_cypher=query),tenant_id=tenant)
    inst=rt.on_alert_raise(inc.card['alert']);pid=inst['proc_inst_id']
    save('fixture',{'tenant':tenant,'pid':pid,'incident':inc.id,'decision':d['id']})
    check('execution reports missing real incident source',rt.execution_view(pid)['graph']['incident'] is None)
    bad=GraphDatabase.driver('bolt://127.0.0.1:1',connection_timeout=1,max_transaction_retry_time=0)
    def unavailable(q,**p):
        with bad.session() as s:s.run(q,**p).consume()
    check('actual graph connection failure retains both source jobs',CaseProjector(store,unavailable).drain()==0 and store.case_projection_status()['pending']==2)
    save('offline',store.case_projection_status());store.db.close();store=Store(out/'cases.sqlite3')
    captured=[]
    def writer(q,**p):captured.append((q,deepcopy(p)));return query(q,**p)
    def notify(sid):repo.enqueue_incident_projections(tenant,sid)
    worker=CaseProjector(store,writer,notify)
    until=time.monotonic()+12
    while store.case_projection_status()['pending'] and time.monotonic()<until:
        worker.drain();time.sleep(.2)
    check('reopened SQLite restores Incident and DecisionCase to actual graph',store.case_projection_status()['pending']==0)
    old_incident=next((q,p) for q,p in captured if p.get('id')==inc.id)
    rt.reconcile_projections();view=rt.execution_view(pid);save('repaired-execution',view)
    check('incident delivery repairs original PG HANDLES relationship',view['graph']['incident']==inc.id and not any('incident source' in w for w in view['graph']['warnings']))
    case=query('MATCH (c:DecisionCase {id:$id})-[:FOR_INCIDENT]->(i:Incident) RETURN c{.*} AS c,i.id AS incident',id='case:'+d['id'])
    check('decision has actual incident and approved source state',case[0]['incident']==inc.id and case[0]['c']['status']=='APPROVED')
    before=store.db.execute('select count(*) from case_projection_outbox').fetchone()[0]
    store.save(sources,book,[{'event':'unrelated audit'}])
    check('audit-only snapshot does not enqueue duplicate projections',store.db.execute('select count(*) from case_projection_outbox').fetchone()[0]==before)
    inc.state='ESCALATED';inc.reason='[회귀 검사] 시험 검토';inc.card['topCause']=None;store.save(sources,book,[]);worker.drain()
    row=query('MATCH (i:Incident {id:$id}) OPTIONAL MATCH (i)-[:DIAGNOSED_AS]->(c) RETURN i.status AS status,count(c) AS causes',id=inc.id)[0]
    check('current state and removed diagnosis replace obsolete graph facts',row=={'status':'ESCALATED','causes':0})
    query(old_incident[0],**old_incident[1])
    check('delayed old case payload cannot restore former state',query('MATCH (i:Incident {id:$id}) RETURN i.status AS status',id=inc.id)[0]['status']=='ESCALATED')
    inc.reason='crash after graph commit';store.save(sources,book,[])
    child=subprocess.run([sys.executable,__file__,'--out',str(out),'--crash'],capture_output=True,text=True)
    save('crash',{'returncode':child.returncode,'stdout':child.stdout,'stderr':child.stderr})
    check('real process death after graph commit keeps SQLite job pending',child.returncode==73 and store.case_projection_status()['pending']>0)
    store.db.close();store=Store(out/'cases.sqlite3');worker=CaseProjector(store,writer,notify);worker.drain();rt.reconcile_projections()
    check('restart replay acknowledges committed graph idempotently',store.case_projection_status()['pending']==0 and query('MATCH (i:Incident {id:$id}) RETURN count(i) AS n',id=inc.id)[0]['n']==1)
    # A decision's source exists before its referenced Incident source. Do not
    # fabricate an Incident or claim that the missing relationship is complete.
    other=machine.Incident.from_card('INC-A044-LATE-'+unique,inc.card);other.state='AWAITING_APPROVAL'
    later=dict(d,id='DEC-A044-LATE-'+unique,origin={'incident':other.id});book[later['id']]=later
    store.save(sources,book,[]);worker.drain();save('dependency-pending',store.case_projection_status())
    check('missing incident keeps decision relationship retryable',store.case_projection_status()['pending']==1 and query('MATCH (i:Incident {id:$id}) RETURN count(i) AS n',id=other.id)[0]['n']==0)
    sources[other.id]=other;store.save(sources,book,[]);worker.drain()
    check('later source arrival repairs pending decision relation',store.case_projection_status()['pending']==0 and len(query('MATCH (:DecisionCase {id:$id})-[:FOR_INCIDENT]->(:Incident {id:$inc}) RETURN 1 AS ok',id='case:'+later['id'],inc=other.id))==1)
    sources.pop(inc.id);store.save(sources,book,[]);worker.drain();rt.reconcile_projections()
    check('source removal deletes Incident and leaves dependent case pending',query('MATCH (i:Incident {id:$id}) RETURN count(i) AS n',id=inc.id)[0]['n']==0 and store.case_projection_status()['pending']==1 and rt.execution_view(pid)['graph']['incident'] is None)
    query(old_incident[0],**old_incident[1])
    check('pre-delete delayed graph write cannot resurrect source',query('MATCH (i:Incident {id:$id}) RETURN count(i) AS n',id=inc.id)[0]['n']==0)
    sources[inc.id]=inc;store.save(sources,book,[]);worker.drain();rt.reconcile_projections()
    check('restored source repairs both graph dependencies',store.case_projection_status()['pending']==0 and rt.execution_view(pid)['graph']['incident']==inc.id)
    with psycopg.connect(DSN) as c:
        c.execute("update todolist set status='CANCELLED' where proc_inst_id=%s",(pid,))
        c.execute("update bpm_proc_inst set status='COMPLETED',current_activity_ids='{}',end_date=now() where proc_inst_id=%s",(pid,))
    other.state='ESCALATED';other.reason='[회귀 검사] 시험 검토';store.save(sources,book,[]);worker.drain();rt.reconcile_projections()
    save('final-queue',store.case_projection_status());save('final-execution',rt.execution_view(pid))
    save('final-cases',query('MATCH (n) WHERE n.id IN $ids RETURN labels(n) AS labels,n{.*} AS properties',ids=[inc.id,other.id,'case:'+d['id'],'case:'+later['id']]))
    check('retained fixture leaves both queues settled',store.case_projection_status()['pending']==0 and repo.projection_status(tenant,pid)['pending']==0)
    store.db.close();bad.close();driver.close()


if __name__=='__main__':main()
