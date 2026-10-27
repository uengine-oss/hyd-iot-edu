import importlib.util
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from procsvc import course_bootstrap,course_access


def test_locked_bootstrap_installs_only_shipped_flows_and_reuses_them(tmp_path):
    app=FastAPI();present=set();writes=[]
    @app.get('/api/flows/deployments')
    def deployments():return {'flows':[{'definition':d,'class_flow':True} for d in present]}
    @app.post('/api/flows/import')
    async def imported(request:Request):
        body=await request.json();did=body['definition_id']
        assert body['xml']==course_bootstrap.FLOWS[did][1]
        writes.append('import');return {}
    @app.post('/api/flows/{did}/check')
    async def check(did:str,request:Request):
        assert (await request.json())['mapping']==course_bootstrap.FLOWS[did][2]
        writes.append('check');return {'check':{'problems':[]}}
    @app.post('/api/flows/{did}/register')
    async def register(did:str,request:Request):
        assert (await request.json())['mapping']==course_bootstrap.FLOWS[did][2]
        writes.append('register');return {'version':'1'}
    @app.post('/api/process/definitions/{did}/deploy')
    async def deploy(did:str,request:Request):
        assert (await request.json())['class_flow'] is True
        present.add(did);writes.append('deploy');return {}
    course_access.mount(app,path=tmp_path/'access.json',archive_factory=lambda:None,tenant='hyd')
    course_bootstrap.mount(app)
    client=TestClient(app)
    assert client.post('/api/flows/import',json={'definition_id':'c3_cooling'},
        headers={'X-Course-Bootstrap':'true','X-HYD-Bootstrap':'true'}).status_code==403
    assert client.post('/api/course-bootstrap',json={'unlocked':True}).status_code==422
    assert not writes
    response=client.post('/api/course-bootstrap',json={})
    assert response.status_code==200 and len(writes)==12
    assert all(not r['reused'] for r in response.json()['flows'])
    assert all(r['reused'] for r in client.post('/api/course-bootstrap',json={}).json()['flows'])
    assert len(writes)==12 and client.get('/api/course-access').json()['unlocked'] is False


def test_packaged_flows_match_existing_assembly_source():
    path=Path(__file__).parents[1]/'scripts/c3_flows.py'
    spec=importlib.util.spec_from_file_location('course_flow_source',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert course_bootstrap.FLOWS==json.loads(json.dumps(module.FLOWS))
