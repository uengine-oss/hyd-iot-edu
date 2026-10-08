"""Actual Neo4j transaction/race checks; only the named test fixtures are removed.

The interrupted transaction is an explicit injected OSError, not a network outage.
No agent, process execution, or physical control result is asserted here.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/process'),str(ROOT/'common')]
from neo4j import GraphDatabase
from procsvc import main, skill_graph, kgadmin


def run():
    tag='A047-'+uuid.uuid4().hex[:10].upper()
    dest=ROOT/'.evidence/reaudit/a047-skill-atomic'/tag
    dest.mkdir(parents=True,exist_ok=False)
    env=dict(v.split('=',1) for v in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    driver=GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1)))
    checks=[]; ids=[]; requests=[]
    def save(name,data):(dest/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    def q(query,**params):
        with driver.session() as session:return session.execute_write(lambda tx:tx.run(query,**params).data())
    def check(name,condition,detail=None):
        checks.append(dict(name=name,passed=bool(condition),detail=detail));save('checks',checks)
        print(('PASS ' if condition else 'FAIL ')+name,flush=True)
        assert condition,name
    def receipt_count(rid):return q('MATCH (r:KnowledgeEdit {id:$id}) RETURN count(r) AS n',id=rid)[0]['n']
    def current(sid):return skill_graph.stamp(q(main.SKILL_Q,id=sid))[0]
    def snapshot():
        return dict(nodes=q('MATCH (n) WHERE n.id IN $ids RETURN labels(n) AS labels,properties(n) AS props ORDER BY n.id',ids=ids),
                    edges=q('MATCH (a)-[r]->(b) WHERE a.id IN $ids OR b.id IN $ids RETURN a.id AS a,type(r) AS type,properties(r) AS props,b.id AS b ORDER BY a,type,b',ids=ids))
    def invoke(sid,values,*,create=False,revision=None,rid=None,fault=False):
        rid=rid or str(uuid.uuid4()); requests.append(rid)
        with driver.session() as session:
            class Tx:
                def __init__(self,tx):self.tx=tx
                def run(self,query,**params):
                    if 'CREATE (k)-[:APPROVED_BY]' in query:raise OSError('explicit A047 transaction interruption')
                    return self.tx.run(query,**params)
            class Session:
                def run(self,*args,**kwargs):return session.run(*args,**kwargs)
                def execute_write(self,fn):return session.execute_write(lambda tx:fn(Tx(tx)))
            return skill_graph.write(Session() if fault else session,main.SKILL_Q,sid,values,create=create,expected_revision=revision,request_id=rid,by='[회귀 검사] A047 격리 인수 시험')
    def rejected(fn,kind):
        try:fn()
        except kind:return True
        return False
    roles=['role:'+tag+'-1','role:'+tag+'-2'];ids.extend(roles)
    q('UNWIND $ids AS id CREATE (:Role {id:id,name:id,level:2,_acceptance_fixture:true})',ids=roles)
    fm=q('MATCH (f:FailureMode) RETURN f.id AS id ORDER BY id LIMIT 1')[0]['id']
    values=kgadmin.validate_skill(dict(name=tag,description='[회귀 검사] 격리 인수 시험 자료',approver=roles[0],sopId='SOP-'+tag,steps=['first step','second step'],failureMode=fm),create=True)
    sid=kgadmin.skill_id(values['sopId']);ids.extend([sid,sid+'/step/1',sid+'/step/2'])
    try:
        rid=str(uuid.uuid4());created=invoke(sid,values,create=True,rid=rid)
        check('new SOP properties, ordered steps, failure-mode, role and performer commit together',
              created['id']==sid and [s['text'] for s in created['steps']]==values['steps'] and created['approver']['id']==roles[0]
              and len(created['failureModes'])==1 and len(created['performers'])==1 and receipt_count(rid)==1)
        before=snapshot();save('created',before)
        check('same creation request returns original receipt without duplicates',invoke(sid,values,create=True,rid=rid)==created and snapshot()==before)
        reversed_values=dict(values,steps=list(reversed(values['steps'])))
        check('same request with reversed SOP step order is rejected',rejected(lambda:invoke(sid,reversed_values,create=True,rid=rid),skill_graph.Conflict) and snapshot()==before)
        check('another creation request cannot overwrite the existing SOP',rejected(lambda:invoke(sid,dict(values,name='replacement'),create=True),skill_graph.Conflict) and snapshot()==before)
        edit=dict(name='valid edit',description='[회귀 검사] 설명 수정',approver=roles[1])
        rid_bad=str(uuid.uuid4())
        check('unknown approval role rejects every change',rejected(lambda:invoke(sid,dict(edit,approver='role:missing-'+tag),revision=created['revision'],rid=rid_bad),ValueError) and snapshot()==before and receipt_count(rid_bad)==0)
        rid_fault=str(uuid.uuid4())
        check('injected interruption rolls back properties, removed approval and receipt',rejected(lambda:invoke(sid,edit,revision=created['revision'],rid=rid_fault,fault=True),OSError) and snapshot()==before and receipt_count(rid_fault)==0)
        check('missing review revision cannot edit',rejected(lambda:invoke(sid,edit),ValueError) and snapshot()==before)
        def racing(name):
            try:return dict(result=invoke(sid,dict(edit,name=name),revision=created['revision']))
            except skill_graph.Conflict as error:return dict(conflict=str(error))
        with ThreadPoolExecutor(max_workers=2) as pool:race=list(pool.map(racing,['racer one','racer two']))
        save('race',race)
        check('two real concurrent writers yield one commit and one stale-review conflict',sum('result' in r for r in race)==1 and sum('conflict' in r for r in race)==1 and current(sid)['approver']['id']==roles[1])
        now=current(sid);rid_edit=str(uuid.uuid4())
        updated=invoke(sid,edit,revision=now['revision'],rid=rid_edit)
        # A new driver/session models a fresh client after losing its response.
        with GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1))) as fresh:
            with fresh.session() as session:replay=skill_graph.write(session,main.SKILL_Q,sid,edit,expected_revision=now['revision'],request_id=rid_edit,by='[회귀 검사] A047 격리 인수 시험')
        check('fresh client replays committed request despite its now-old revision',replay==updated and receipt_count(rid_edit)==1)
        before=snapshot()
        check('stale edit cannot overwrite the newer revision',rejected(lambda:invoke(sid,dict(edit,name='stale'),revision=created['revision']),skill_graph.Conflict) and snapshot()==before)
        q('MATCH (k:Skill {id:$id}) SET k._manual_document=$document',id=sid,document='isolated:'+tag)
        before=snapshot()
        check('source-owned skill requires source revision review',rejected(lambda:invoke(sid,edit,revision=current(sid)['revision']),skill_graph.Conflict) and snapshot()==before)
        q('MATCH (k:Skill {id:$id}) REMOVE k._manual_document',id=sid)
        for suffix,change in [('MISSING-FM',{'failureMode':'fm:missing-'+tag}),('STEP-COLLISION',{})]:
            other=dict(values,sopId='SOP-'+tag+'-'+suffix,**change);other_id=kgadmin.skill_id(other['sopId'])
            ids.extend([other_id,other_id+'/step/1',other_id+'/step/2'])
            if suffix=='STEP-COLLISION':q('CREATE (:Step {id:$id,text:"foreign existing step",_acceptance_fixture:true})',id=other_id+'/step/1')
            before=snapshot()
            check(suffix+' leaves no partial skill or replacement',rejected(lambda:invoke(other_id,other,create=True),ValueError) and snapshot()==before)
    finally:
        save('before-cleanup',snapshot());save('requests',requests)
        # Exact IDs created by this run; refuse deleting any unexpected edge.
        allowed={'HAS_STEP','APPROVED_BY','HAS_SKILL','REMEDIED_BY'}
        edges=q('MATCH (a)-[r]->(b) WHERE a.id IN $ids OR b.id IN $ids RETURN type(r) AS type,a.id AS a,b.id AS b',ids=ids)
        if any(e['type'] not in allowed for e in edges):raise RuntimeError('unexpected reference: retained test fixtures')
        q('MATCH (a)-[r]->(b) WHERE a.id IN $ids OR b.id IN $ids DELETE r',ids=ids)
        q('MATCH (n) WHERE n.id IN $ids DELETE n',ids=ids)
        q('MATCH (r:KnowledgeEdit) WHERE r.id IN $ids DELETE r',ids=requests)
        check('all exact test nodes and request receipts removed',not snapshot()['nodes'] and not q('MATCH (r:KnowledgeEdit) WHERE r.id IN $ids RETURN r.id AS id',ids=requests))
        driver.close()
    print(json.dumps(dict(evidence=str(dest),passed=len(checks)),ensure_ascii=False))


if __name__=='__main__':run()
