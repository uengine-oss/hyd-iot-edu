"""Inspect and explicitly requeue derived graphs from a reviewed current source.

Repair retains its source/graph comparison and intent in a durable journal. It
never rewinds a business record, issues a command, resets a graph fence, or marks
a delivery complete. The ordinary projector must still return an exact receipt.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from types import SimpleNamespace
import uuid
from .projection_receipt import digest


def graph_state(query,kind,sid):
    if kind not in ('Incident','DecisionCase','Execution'):raise ValueError('unknown projection kind')
    fence='ExecutionProjection' if kind=='Execution' else 'CaseProjection'
    label='ProcessInstance' if kind=='Execution' else kind
    key=sid if kind=='Execution' else kind+':'+sid
    gid='case:'+sid if kind=='DecisionCase' else sid
    rows=query(f'''OPTIONAL MATCH (f:{fence} {{id:$key}})
        RETURN f.revision AS revision,f.payload_hash AS payload_hash''',key=key)
    nodes=query(f'''MATCH (n:{label} {{id:$id}})
        RETURN n{{.*}} AS node,COLLECT {{ MATCH (n)-[r]->(m)
        RETURN {{type:type(r),properties:properties(r),target:m.id}} ORDER BY type(r),m.id }} AS edges''',id=gid)
    items=query('''MATCH (w:WorkItem)-[:IN_INSTANCE]->(:ProcessInstance {id:$id})
        RETURN w{.*} AS node,COLLECT { MATCH (w)-[r]->(m)
        RETURN {type:type(r),properties:properties(r),target:m.id} ORDER BY type(r),m.id } AS edges ORDER BY w.id''',id=gid) if kind=='Execution' else []
    # Neo4j temporal values must survive the JSON inspection file and journal
    # with exactly the same representation used for plan comparison.
    return json.loads(json.dumps(dict(fence=rows[0] if rows else dict(revision=None,payload_hash=None),nodes=nodes,items=items),default=str))


def case_source(store,kind,sid):
    row=store.db.execute('select body from snapshot where id=1').fetchone()
    body=json.loads(row[0]) if row else {}
    source=next((i for i in body.get('incidents',[]) if i['id']==sid),None) if kind=='Incident' else body.get('book',{}).get(sid)
    if source is None and not store.db.execute('select 1 from case_projection_source where kind=? and source_id=?',(kind,sid)).fetchone():
        raise KeyError('no known source or deletion tombstone')
    return source


def dependent_cases(store,kind,sid):
    if kind!='Incident':return {}
    row=store.db.execute('select body from snapshot where id=1').fetchone()
    book=json.loads(row[0]).get('book',{}) if row else {}
    return {key:value for key,value in book.items() if (value.get('origin') or {}).get('incident')==sid}


def inspect_case(store,query,kind,sid):
    if kind not in ('Incident','DecisionCase'):raise ValueError('invalid case kind')
    with store._lock:
        source=case_source(store,kind,sid)
        dependencies=dependent_cases(store,kind,sid)
        pending=[dict(zip(('id','attempts','last_error'),r)) for r in store.db.execute('select id,attempts,last_error from case_projection_outbox where kind=? and source_id=? and processed_at is null order by id',(kind,sid))]
    dependents=[dict(kind='DecisionCase',id=key,source=value,source_hash=digest(value),graph=graph_state(query,'DecisionCase',key)) for key,value in sorted(dependencies.items())]
    return dict(kind=kind,id=sid,source=source,source_hash=digest(source),pending=pending,graph=graph_state(query,kind,sid),dependents=dependents)


def execution_source(repo,connection,tenant,pid):
    repo._local.connection=connection
    try:
        inst=repo.get_instance(pid)
        if inst and inst['tenant_id']!=tenant:raise KeyError('foreign tenant')
        if inst is None and not connection.execute('select 1 from execution_projection_outbox where tenant_id=%s and proc_inst_id=%s limit 1',(tenant,pid)).fetchone():
            raise KeyError('no known instance or deletion tombstone')
        definition=repo.get_proc_def(inst['proc_def_id'],tenant,version=inst['proc_def_version']) if inst and not inst.get('is_deleted') else None
        if inst and not inst.get('is_deleted') and definition is None:raise ValueError('pinned definition source is missing')
        return dict(instance=inst,definition=definition,items=sorted(repo.list_workitems(proc_inst_id=pid,limit=None),key=lambda i:i['id']))
    finally:del repo._local.connection


#: ProcessInstance / WorkItem properties the projection copies verbatim from the source (instances.py INSTANCE_Q params);
#: a graph-only change to one of them is drift the fence hash cannot see (the fence hashes the *payload the projector sent*,
#: not what the graph holds now). A148 (sweep 57): inspect reports it, so a tampered or stale node is found without a repair.
INSTANCE_DRIFT_FIELDS=(('status','status'),('end_event','end_event'),('proc_def_version','version'),('rework_generation','rework_generation'),
                       ('proc_def_id','definition_id'))
ITEM_DRIFT_FIELDS=(('status','status'),('draft_status','draft_status'),('activity_id','activity_id'),('generation','generation'))


def execution_drift(source,graph):
    """[{where,field,source,graph}] for every projected field whose graph value differs from the source row; [] when the
    projection matches. A missing node/item counts as drift too (deleted or never projected) unless the source is deleted."""
    out=[];inst=source.get('instance') or {}
    nodes=[n.get('node') or {} for n in graph.get('nodes') or []]
    if inst and not inst.get('is_deleted'):
        if not nodes:return [dict(where='ProcessInstance',field='*',source='present',graph='missing')]
        node=nodes[0]
        for src,dst in INSTANCE_DRIFT_FIELDS:
            s,g=inst.get(src),node.get(dst)
            if src=='rework_generation':s=int(s or 0);g=int(g or 0)
            if (s or None)!=(g or None):out.append(dict(where='ProcessInstance',field=dst,source=s,graph=g))
        items={i.get('node',{}).get('id'):i.get('node') or {} for i in graph.get('items') or []}
        for row in source.get('items') or []:
            g=items.get(row['id'])
            if g is None:out.append(dict(where='WorkItem:'+row['id'],field='*',source='present',graph='missing'));continue
            for src,dst in ITEM_DRIFT_FIELDS:
                s,gv=row.get(src),g.get(dst)
                if src=='generation':s=int(s or 0);gv=int(gv or 0)
                if (s or None)!=(gv or None):out.append(dict(where='WorkItem:'+row['id'],field=dst,source=s,graph=gv))
    elif nodes:
        out.append(dict(where='ProcessInstance',field='*',source='deleted',graph='present'))
    return out


def inspect_execution(repo,query,tenant,pid):
    if getattr(repo._local,'connection',None) is not None:raise RuntimeError('inspect projection outside business transactions')
    with repo._conn() as c:
        c.execute('set transaction isolation level repeatable read')
        source=execution_source(repo,c,tenant,pid)
        pending=c.execute('select id,revision,attempts,last_error from execution_projection_outbox where tenant_id=%s and proc_inst_id=%s and processed_at is null order by id',(tenant,pid)).fetchall()
    source=json.loads(json.dumps(source,default=str))
    graph=graph_state(query,'Execution',pid)
    return dict(kind='Execution',tenant=tenant,id=pid,source=source,source_hash=digest(source),pending=pending,graph=graph,drift=execution_drift(source,graph))


def intent(plan,by,reason,request_id):
    if not isinstance(by,str) or not by.strip() or not isinstance(reason,str) or not reason.strip():raise ValueError('repair actor and reason are required')
    if digest(plan['source'])!=plan['source_hash']:raise ValueError('inspection source integrity mismatch')
    if any(digest(d['source'])!=d['source_hash'] for d in plan.get('dependents',[])):raise ValueError('dependent source integrity mismatch')
    rid=str(uuid.UUID(request_id)) if request_id else str(uuid.uuid4())
    return rid,digest(dict(plan=plan,by=by,reason=reason))


def repair_case(store,query,kind,sid,*,by,reason,plan=None,request_id=None):
    plan=plan or inspect_case(store,query,kind,sid)
    if plan['kind']!=kind or plan['id']!=sid:raise ValueError('repair target differs from reviewed plan')
    rid,fingerprint=intent(plan,by,reason,request_id)
    # A replay returns its durable receipt even if graph delivery has since run.
    with store._lock:
        receipt=store.db.execute('select fingerprint,result from projection_repairs where request_id=?',(rid,)).fetchone()
    if receipt:
        if receipt[0]!=fingerprint:raise ValueError('repair request ID reused with a different intent')
        return json.loads(receipt[1])
    observed=graph_state(query,kind,sid)
    if digest(observed)!=digest(plan['graph']):raise ValueError('graph changed since inspection; inspect again')
    dependents=plan.get('dependents',[])
    for item in dependents:
        if item['kind']!='DecisionCase' or kind!='Incident':raise ValueError('invalid dependent repair target')
        if digest(graph_state(query,'DecisionCase',item['id']))!=digest(item['graph']):raise ValueError('dependent graph changed since inspection; inspect again')
    with store._lock,store.db:
        store.db.execute('BEGIN IMMEDIATE')
        source=case_source(store,kind,sid)
        if digest(source)!=plan['source_hash']:raise ValueError('source changed since inspection; inspect again')
        actual_dependencies=dependent_cases(store,kind,sid)
        if {key:digest(value) for key,value in actual_dependencies.items()}!={d['id']:d['source_hash'] for d in dependents}:
            raise ValueError('dependent sources changed since inspection; inspect again')
        existing=store.db.execute('select fingerprint,result from projection_repairs where request_id=?',(rid,)).fetchone()
        if existing:
            if existing[0]!=fingerprint:raise ValueError('repair request ID reused with a different intent')
            return json.loads(existing[1])
        row=store.db.execute("select seq from sqlite_sequence where name='case_projection_outbox'").fetchone()
        floor=max([row[0] if row else 0,observed['fence']['revision'] or 0]+[d['graph']['fence']['revision'] or 0 for d in dependents])
        if row:store.db.execute("update sqlite_sequence set seq=? where name='case_projection_outbox'",(floor,))
        else:store.db.execute("insert into sqlite_sequence(name,seq) values('case_projection_outbox',?)",(floor,))
        jobs=[]
        for target in [dict(kind=kind,id=sid,source=source)]+dependents:
            store.db.execute('update case_projection_outbox set last_error=null,retry_at=0 where kind=? and source_id=? and processed_at is null',(target['kind'],target['id']))
            cursor=store.db.execute('insert into case_projection_outbox(kind,source_id,body,created_at) values(?,?,?,?)',(target['kind'],target['id'],json.dumps(target['source'],ensure_ascii=False),time.time()))
            jobs.append(dict(kind=target['kind'],id=target['id'],revision=cursor.lastrowid))
        result=dict(request_id=rid,status='QUEUED',by=by,reason=reason,plan=plan,revision=jobs[0]['revision'],jobs=jobs,queued_at=time.time())
        store.db.execute('insert into projection_repairs values(?,?,?)',(rid,fingerprint,json.dumps(result,ensure_ascii=False)))
        return result


def repair_execution(repo,query,tenant,pid,*,by,reason,plan=None,request_id=None):
    if getattr(repo._local,'connection',None) is not None:raise RuntimeError('repair projection outside business transactions')
    plan=plan or inspect_execution(repo,query,tenant,pid)
    if plan['kind']!='Execution' or plan['id']!=pid or plan['tenant']!=tenant:raise ValueError('repair target differs from reviewed plan')
    rid,fingerprint=intent(plan,by,reason,request_id)
    with repo._conn() as c:
        receipt=c.execute('select fingerprint,result from projection_repairs where request_id=%s',(rid,)).fetchone()
    if receipt:
        if receipt['fingerprint']!=fingerprint:raise ValueError('repair request ID reused with a different intent')
        return receipt['result']
    observed=graph_state(query,'Execution',pid)
    if digest(observed)!=digest(plan['graph']):raise ValueError('graph changed since inspection; inspect again')
    with repo._psycopg.connect(repo.dsn,autocommit=True,connect_timeout=5,row_factory=repo._dict_row) as c:
        key='execution-projection:'+tenant+':'+pid
        if not c.execute('select pg_try_advisory_lock(hashtextextended(%s,0)) as ok',(key,)).fetchone()['ok']:
            raise ValueError('projection delivery is active; inspect again after it settles')
        try:
            with c.transaction():
                c.execute('set transaction isolation level repeatable read')
                receipt=c.execute('select fingerprint,result from projection_repairs where request_id=%s',(rid,)).fetchone()
                if receipt:
                    if receipt['fingerprint']!=fingerprint:raise ValueError('repair request ID reused with a different intent')
                    return receipt['result']
                source=execution_source(repo,c,tenant,pid)
                if digest(source)!=plan['source_hash']:raise ValueError('source changed since inspection; inspect again')
                c.execute("select pg_advisory_xact_lock(hashtextextended('hyd-projection-revision',0))")
                sequence=c.execute('select last_value from hyd_projection_revision').fetchone()['last_value']
                floor=max(sequence,observed['fence']['revision'] or 0)
                # Sequence jumps are nontransactional; a rolled-back repair may
                # leave a harmless gap, never reuse a lower allocated revision.
                c.execute("select setval('hyd_projection_revision',%s,true)",(max(1,floor),))
                c.execute('update execution_projection_outbox set last_error=null,retry_at=now() where tenant_id=%s and proc_inst_id=%s and processed_at is null',(tenant,pid))
                job=c.execute('insert into execution_projection_outbox(tenant_id,proc_inst_id) values(%s,%s) returning id',(tenant,pid)).fetchone()['id']
                result=dict(request_id=rid,status='QUEUED',by=by,reason=reason,plan=plan,revision_floor=floor,job_id=job,queued_at=time.time())
                c.execute('insert into projection_repairs(request_id,tenant_id,proc_inst_id,fingerprint,result) values(%s,%s,%s,%s,%s)',(rid,tenant,pid,fingerprint,repo._Jsonb(result)))
                return result
        finally:c.execute('select pg_advisory_unlock(hashtextextended(%s,0))',(key,))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode',choices=['inspect','apply']);ap.add_argument('--kind',choices=['Incident','DecisionCase','Execution'])
    ap.add_argument('--id');ap.add_argument('--tenant',default=os.getenv('TENANT_ID','hyd'))
    ap.add_argument('--file',type=Path,required=True);ap.add_argument('--by');ap.add_argument('--reason');ap.add_argument('--request-id')
    args=ap.parse_args()
    from .main import _kg
    from .procdb import PgRepo
    from .store import Store
    with _kg() as driver:
        def q(query,**params):
            with driver.session() as session:return session.execute_write(lambda tx:tx.run(query,**params).data())
        plan=json.loads(args.file.read_text(encoding='utf8')) if args.mode=='apply' else None
        kind=plan['kind'] if plan else args.kind;sid=plan['id'] if plan else args.id
        if not kind or not sid:ap.error('inspect requires --kind and --id')
        if args.mode=='apply' and (not args.by or not args.reason or not args.request_id):ap.error('apply requires --by --reason --request-id')
        if kind=='Execution':
            repo=PgRepo(os.environ['SUPABASE_DSN']);tenant=plan['tenant'] if plan else args.tenant
            result=inspect_execution(repo,q,tenant,sid) if plan is None else repair_execution(repo,q,tenant,sid,by=args.by,reason=args.reason,request_id=args.request_id,plan=plan)
        else:
            path=Path(os.getenv('PROCESS_STATE_PATH','/data/process.sqlite3'))
            store=SimpleNamespace(db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True),_lock=threading.Lock()) if plan is None else Store(path)
            try:result=inspect_case(store,q,kind,sid) if plan is None else repair_case(store,q,kind,sid,by=args.by,reason=args.reason,request_id=args.request_id,plan=plan)
            finally:store.db.close()
        destination=args.file if plan is None else args.file.with_name(args.file.stem+'.result.json')
        if destination.exists() and plan is not None:
            if json.loads(destination.read_text(encoding='utf8'))!=result:raise ValueError('result file belongs to a different repair; preserve it and choose another plan file')
        else:
            with destination.open('x',encoding='utf8') as target:target.write(json.dumps(result,ensure_ascii=False,indent=2,default=str))
        print(json.dumps(dict(file=str(destination),status='INSPECTED' if plan is None else 'QUEUED')))


if __name__=='__main__':main()
