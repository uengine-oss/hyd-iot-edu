"""Actual SQLite backup and PG/Neo4j fence disagreement, isolated fixtures."""
import argparse
import json
import logging
from pathlib import Path
import sqlite3
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


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',action='store_true');args=ap.parse_args()
    tag='a049-'+uuid.uuid4().hex[:10];out=ROOT/'.evidence/reaudit'/('a049-red' if args.baseline else 'a049-live')/tag;out.mkdir(parents=True)
    logging.getLogger('neo4j.notifications').setLevel(logging.ERROR)
    env=dict(v.split('=',1) for v in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    driver=GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1)))
    def q(query,**p):
        with driver.session() as s:return s.execute_write(lambda tx:tx.run(query,**p).data())
    def save(name,x):(out/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    checks=[]
    def check(name,ok):
        checks.append(dict(name=name,passed=bool(ok)));save('checks',checks);print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if not args.baseline:assert ok,name
    inc=machine.Incident.from_card('INC-'+tag,{'alert':{'alertId':tag,'asset':'HYD-01','pattern':'COOLER_DEGRADATION'}});inc.state='AWAITING_APPROVAL'
    store=Store(out/'source.sqlite3');store.save({inc.id:inc},{},[])
    with sqlite3.connect(out/'backup.sqlite3') as backup:store.db.backup(backup)
    worker=CaseProjector(store,q);old_case_job=store.case_projection_batch()[0];worker.drain()
    for reason in ['newer-one','newer-two']:
        inc.reason=reason;store.save({inc.id:inc},{},[]);worker.drain()
    store.db.close();store=Store(out/'backup.sqlite3')
    restored,_,_=store.restore();restored[inc.id].reason='restored-change';store.save(restored,{},[])
    worker=CaseProjector(store,q);worker.drain();save('sqlite-stale-status',store.case_projection_status())
    check('restored SQLite source cannot report success for rejected older revision',store.case_projection_status()['pending']>0)
    restored[inc.id].reason='colliding-restored-revision';store.save(restored,{},[]);worker.drain()
    row=q('MATCH (i:Incident {id:$id}) RETURN i.reason AS reason',id=inc.id)[0]
    check('new events after restore cannot silently overwrite equal graph revision',row['reason']=='newer-two')
    dsn='postgresql://postgres:postgres@127.0.0.1:54322/postgres'
    with psycopg.connect(dsn) as c:c.execute('insert into tenants(id,name) values(%s,%s)',(tag,'A049 fence fixture'))
    repo=procdb.PgRepo(dsn);raw=json.loads((ROOT/'docs/examples/rework-inspection-v1.json').read_text(encoding='utf8'))
    rt=instances.InstanceRuntime(repo,engine.Definition.from_dict(raw),instances.Hooks(record_cypher=q,query_cypher=q),tenant_id=tag)
    inst=rt.start_definition(raw['processDefinitionId'],'1',tag,{'score':2});pid=inst['proc_inst_id']
    # Scope the higher graph revision to this fixture. Never rewind the shared
    # production PG sequence to simulate an old source database.
    q('MATCH (f:ExecutionProjection {id:$id}) SET f.revision=f.revision+100000',id=pid)
    inst['proc_inst_name']='a049 changed current source';repo.update_instance(inst);rt.reconcile_projections()
    save('pg-stale-status',repo.projection_status(tag,pid))
    check('PG source cannot acknowledge a graph write refused by the fence',repo.projection_status(tag,pid)['pending']>0)
    save('fixture',dict(tenant=tag,pid=pid,incident=inc.id,definition=raw,sqlite=str(out/'backup.sqlite3')))
    if not args.baseline:
        # The reviewed repair API is exercised here once implemented.
        from procsvc.projection_repair import repair_case,repair_execution,inspect_case,inspect_execution
        case_plan=inspect_case(store,q,'Incident',inc.id);case_rid=str(uuid.uuid4())
        case_result=repair_case(store,q,'Incident',inc.id,by='A049 acceptance',reason='isolated restored SQLite comparison',plan=case_plan,request_id=case_rid)
        save('case-repair',case_result);worker.drain()
        check('explicit restored-source repair delivers the current source',store.case_projection_status()['pending']==0 and q('MATCH (i:Incident {id:$id}) RETURN i.reason AS reason',id=inc.id)[0]['reason']=='colliding-restored-revision')
        check('same SQLite repair request replays its journal after delivery',repair_case(store,q,'Incident',inc.id,by='A049 acceptance',reason='isolated restored SQLite comparison',plan=case_plan,request_id=case_rid)==case_result)
        pg_plan=inspect_execution(repo,q,tag,pid);pg_rid=str(uuid.uuid4())
        pg_result=repair_execution(repo,q,tag,pid,by='A049 acceptance',reason='isolated graph ahead comparison',plan=pg_plan,request_id=pg_rid)
        save('pg-repair',pg_result);rt.reconcile_projections()
        check('explicit execution repair requeues above the observed fence',repo.projection_status(tag,pid)['pending']==0 and rt.execution_view(pid)['graph']['instance']['name']=='a049 changed current source')
        check('same PG repair request replays its journal after delivery',repair_execution(repo,q,tag,pid,by='A049 acceptance',reason='isolated graph ahead comparison',plan=pg_plan,request_id=pg_rid)==pg_result)
        decision=dict(id='DEC-'+tag,created=inc.created,state='APPROVED',chosen='skill:fan-max',approvedRole='role:operator',origin={'incident':inc.id})
        store.save(restored,{decision['id']:decision},[]);worker.drain()
        q('MATCH (i:Incident {id:$id}) DETACH DELETE i',id=inc.id)
        repair_case(store,q,'Incident',inc.id,by='A049 acceptance',reason='isolated relationship damage');worker.drain()
        check('explicit repair restores a projection-only damaged relationship',q('MATCH (:Incident {id:$id})-[:ON_ASSET]->(a) RETURN a.code AS code',id=inc.id)==[dict(code='HYD-01')])
        check('incident recreation also restores reviewed incoming decision links',q('MATCH (:DecisionCase {id:$id})-[:FOR_INCIDENT]->(i) RETURN i.id AS id',id='case:'+decision['id'])==[dict(id=inc.id)])
        stale=inspect_case(store,q,'Incident',inc.id);restored[inc.id].reason='source changed after review';store.save(restored,{},[])
        try:repair_case(store,q,'Incident',inc.id,by='A049 acceptance',reason='must reject stale inspection',plan=stale)
        except ValueError:rejected=True
        else:rejected=False
        check('stale inspected source is rejected before repair',rejected)
        worker.drain();store.save({}, {},[]);worker.drain()
        worker.deliver(old_case_job)
        check('deletion tombstone still rejects a delayed pre-repair source',not q('MATCH (i:Incident {id:$id}) RETURN i.id AS id',id=inc.id))
    save('final-checks',checks);store.db.close();driver.close()
    print(json.dumps(dict(evidence=str(out)),ensure_ascii=False));assert all(c['passed'] for c in checks)


if __name__=='__main__':main()
