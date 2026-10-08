"""HTTP authoring contract with retained UI fixture; explicit prepare/check/cleanup."""
import argparse
import json
from pathlib import Path
import subprocess
import uuid
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from neo4j import GraphDatabase

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.evidence/reaudit/a047-skill-http'
BASE='http://127.0.0.1:8080/api/kg/skills'


def request(url,body=None,method=None):
    req=Request(url,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'},method=method)
    try:
        with urlopen(req,timeout=30) as r:return r.status,json.load(r)
    except HTTPError as e:return e.code,json.load(e)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','check','cleanup']);args=parser.parse_args()
    def save(name,data):(OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    if args.phase=='prepare':
        OUT.mkdir(exist_ok=False);checks=[]
        def check(name,ok):
            checks.append(dict(name=name,passed=bool(ok)));save('checks',checks)
            print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
        status,catalog=request('http://127.0.0.1:8080/api/kg/catalog');assert status==200
        sop='SOP-A047UI-'+uuid.uuid4().hex[:8].upper()
        body=dict(name='[회귀 검사] A047 화면 저장 확인',description='[회귀 검사] 격리 시험 자료',sopId=sop,steps=['격리된 시험 단계'],failureMode=catalog['failureModes'][0]['id'],approver='role:maint-mgr',request_id=str(uuid.uuid4()),by='[회귀 검사] A047 HTTP 인수 시험')
        status,created=request(BASE,body,'POST');save('created',created)
        check('HTTP create returns reviewed revision',status==200 and bool(created.get('revision')))
        save('state',dict(sid=created['id'],sop=sop,body=body,original=created))
        check('same HTTP create request is idempotent',request(BASE,body,'POST')==(200,created))
        status,response=request(BASE,dict(body,request_id=str(uuid.uuid4())),'POST')
        check('another request for same SOP is conflict',status==409)
        invalid=dict(name='invalid edit',approver='role:missing-'+uuid.uuid4().hex,revision=created['revision'],request_id=str(uuid.uuid4()))
        status,response=request(BASE+'/'+created['id'],invalid,'PUT');save('missing-role',dict(status=status,response=response))
        _,rows=request(BASE);now=next(k for k in rows if k['id']==created['id'])
        check('missing role returns 400 with unchanged skill',status==400 and now==created)
        status,_=request(BASE+'/'+created['id'],dict(name='unreviewed'),'PUT')
        check('unreviewed edit returns 400',status==400)
        status,_=request(BASE+'/'+created['id'],dict(name='stale',revision='stale',request_id=str(uuid.uuid4())),'PUT')
        check('stale review returns 409',status==409)
        print(json.dumps(dict(sid=created['id'],sop=sop),ensure_ascii=False))
    else:
        state=json.loads((OUT/'state.json').read_text(encoding='utf8'));sid=state['sid']
        env=dict(v.split('=',1) for v in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
        with GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1))) as driver:
            with driver.session() as session:
                def q(query,**params):return session.execute_write(lambda tx:tx.run(query,**params).data())
                receipts=q('MATCH (r:KnowledgeEdit {skill:$sid}) RETURN r.id AS id,r.result AS result ORDER BY r.created_at',sid=sid)
                if args.phase=='check':
                    status,rows=request(BASE);skill=next(k for k in rows if k['id']==sid)
                    save('after-ui',dict(skill=skill,receipts=receipts))
                    assert status==200 and skill['description']=='[회귀 검사] A047 응답 유실 뒤 저장' and len(receipts)==3
                    print('PASS actual UI edit and response-loss retry create exactly two edit receipts')
                else:
                    ids=[sid,sid+'/step/1'];edges=q('MATCH (a)-[r]->(b) WHERE a.id IN $ids OR b.id IN $ids RETURN a.id AS a,type(r) AS type,b.id AS b',ids=ids)
                    save('cleanup-before',dict(edges=edges,receipts=receipts))
                    assert all(e['type'] in {'HAS_STEP','APPROVED_BY','HAS_SKILL','REMEDIED_BY'} for e in edges)
                    q('MATCH (a)-[r]->(b) WHERE a.id IN $ids OR b.id IN $ids DELETE r',ids=ids)
                    q('MATCH (n) WHERE n.id IN $ids DELETE n',ids=ids)
                    q('MATCH (r:KnowledgeEdit {skill:$sid}) DELETE r',sid=sid)
                    assert not q('MATCH (n) WHERE n.id IN $ids RETURN n.id',ids=ids)
                    save('cleanup',dict(removed_exact_ids=ids));print('PASS exact HTTP/UI fixtures removed')


if __name__=='__main__':main()
