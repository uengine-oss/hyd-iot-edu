"""Real Neo4j and HYD endpoint/function; only isolated, unreferenced skills mutate."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import uuid
from urllib.request import Request,urlopen
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/process'),str(ROOT/'common')]
from neo4j import GraphDatabase
from procsvc import main


def run():
    out=ROOT/'.evidence/reaudit/a047-skill-baseline';out.mkdir(exist_ok=False)
    env=dict(v.split('=',1) for v in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    driver=GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1)))
    prefix='a047-atomic-'+uuid.uuid4().hex[:10];sid='skill:'+prefix;role='role:'+prefix
    def q(query,**params):
        with driver.session() as s:return s.execute_write(lambda tx:tx.run(query,**params).data())
    def save(name,value):(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    def snapshot():return q('MATCH (s:Skill {id:$sid}) OPTIONAL MATCH (s)-[a:APPROVED_BY]->(r) RETURN properties(s) AS skill, collect(r.id) AS approvers',sid=sid)
    def restore():
        q('MATCH (s:Skill {id:$sid}) OPTIONAL MATCH (s)-[a:APPROVED_BY]->() DELETE a SET s.name=$name,s.description=$description WITH s MATCH (r:Role {id:$role}) MERGE (s)-[:APPROVED_BY]->(r)',sid=sid,role=role,name=prefix,description='isolated acceptance fixture')
    q('CREATE (r:Role {id:$role,name:$name,level:2,_acceptance_fixture:true}), (s:Skill {id:$sid,name:$name,description:$description,sopId:$sop,kind:"work_order",_acceptance_fixture:true}) CREATE (s)-[:APPROVED_BY]->(r)',sid=sid,role=role,name=prefix,description='isolated acceptance fixture',sop='SOP-'+prefix.upper())
    before=snapshot();save('before',before);checks=[]
    try:
        request=Request('http://127.0.0.1:8080/api/kg/skills/'+sid,data=json.dumps({'name':'changed name','approver':'role:a047-missing-'+uuid.uuid4().hex,'by':'A047 isolated acceptance'}).encode(),headers={'Content-Type':'application/json'},method='PUT')
        try:
            with urlopen(request,timeout=25) as response:result=dict(status=response.status,body=json.load(response))
        except HTTPError as error:result=dict(status=error.code,body=error.read().decode())
        after=snapshot();save('unknown-role-response',result);save('after-unknown-role',after)
        checks.append(dict(name='unknown role leaves the original skill and approval relationship intact',passed=before==after))
        restore()
        def interrupted(query,**params):
            if 'MERGE (k)-[:APPROVED_BY]' in query:raise OSError('explicit test fault before new role write')
            return q(query,**params)
        old_query=main._q;old_audit=main._audit
        main._q=interrupted;main._audit=lambda *args,**kwargs:None
        try:asyncio.run(main.kg_update_skill(sid,{'name':'interrupted change','approver':role}))
        except OSError as error:save('injected-failure',dict(type=type(error).__name__,message=str(error)))
        finally:main._q=old_query;main._audit=old_audit
        after=snapshot();save('after-interruption',after)
        checks.append(dict(name='interrupted approval replacement rolls back metadata and relationship',passed=after==before))
    finally:
        restore();save('restored',snapshot());save('checks',checks);save('fixture',dict(skill=sid,role=role,scope=__doc__))
        driver.close()
    print(json.dumps(checks,ensure_ascii=False));assert all(c['passed'] for c in checks)


if __name__=='__main__':run()
