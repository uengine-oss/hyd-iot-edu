import base64
import json
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from hydcommon import course_access as rules
from procsvc.course_access import AccessStore, mount


@pytest.fixture
def instructor(monkeypatch):
    key = Ed25519PrivateKey.generate()
    public = base64.urlsafe_b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    original = rules.verify
    verify = lambda code: original(code, public_key=public)
    monkeypatch.setattr(rules, 'verify', verify)
    def sign(payload=None):
        raw = rules.canonical(payload or {'aud':rules.AUDIENCE,'phase':'handover','version':1})
        b64 = lambda x: base64.urlsafe_b64encode(x).rstrip(b'=').decode()
        return 'HYD1.'+b64(raw)+'.'+b64(key.sign(raw))
    return sign, verify


def setup(tmp_path, instructor):
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
    calls = []
    @app.api_route('/api/{rest:path}', methods=['POST','PUT','DELETE','PATCH'])
    async def echo(rest:str, request:Request):
        body = await request.json()
        calls.append((request.method,request.url.path,body))
        return {'received':body}
    # Register the real unlock before the catch-all route.
    app.router.routes.pop()
    sign, verify = instructor
    store = AccessStore(tmp_path/'course-access.json', verify=verify)
    archive = type('Archive', (), {'get': lambda self, tenant, sid: {'sha256':sid.rsplit(':',1)[-1]}})()
    mount(app, path=store.path, archive_factory=lambda:archive, tenant='hyd', store=store)
    app.add_api_route('/api/{rest:path}',echo,methods=['POST','PUT','DELETE','PATCH'])
    return app,TestClient(app),store,sign,calls


def test_signed_code_only_persists_and_never_leaks_through_status_or_errors(tmp_path,instructor):
    app,client,store,sign,calls = setup(tmp_path,instructor)
    code = sign()
    assert client.get('/api/course-access').json()['unlocked'] is False
    for body in ({'unlocked':True},{'code':code,'phase':'handover'},{'code':code+'x'*1000}):
        response=client.post('/api/course-access/unlock',json=body)
        assert response.status_code==422 and code not in response.text
    assert client.patch('/api/course-access',json={'unlocked':True}).status_code==403
    assert client.post('/api/course-access/unlock',json={'code':'not-a-code'}).status_code==403
    assert client.post('/api/course-access/unlock',json={'code':code}).json()['unlocked'] is True
    assert code not in client.get('/api/course-access').text
    assert AccessStore(store.path,verify=instructor[1]).status()['unlocked'] is True
    store.path.write_text(json.dumps({'unlocked':True,'phase':'handover'}),encoding='utf8')
    assert store.status()['unlocked'] is False
    store.path.write_text(json.dumps({'grant':code[:-1]+'!'}),encoding='utf8')
    assert store.status()['unlocked'] is False


def test_even_a_valid_signature_cannot_open_another_audience_or_phase(instructor):
    sign,verify = instructor
    for payload in ({'aud':'other','phase':'handover','version':1},
                    {'aud':rules.AUDIENCE,'phase':'admin','version':1},
                    {'aud':rules.AUDIENCE,'phase':'handover','version':1,'all':True}):
        with pytest.raises(ValueError):verify(sign(payload))


def test_lock_rejects_direct_api_and_preserves_basic_actions_and_cors(tmp_path,instructor):
    _,client,store,sign,calls = setup(tmp_path,instructor)
    for path,method,body in [('/api/agents','post',{'model':'other'}),('/api/agents','post',{'tools':['other']}),
          ('/api/agent-assignments','put',{'definition_id':'shift_handover'}),('/api/agents/reset','post',{}),
          ('/api/ask','post',{'question':'arbitrary'}),('/api/config/import','post',{}),
          ('/api/flows/import','post',{}),('/api/mcp/servers','post',{}),
          ('/api/instances/start','post',{'definition_id':'ask_agent'}),
          ('/api/instances/start','post',{'definition_id':['c3_cooling']})]:
        response=getattr(client,method)(path,json=body,headers={'Origin':'http://localhost:8088'})
        assert response.status_code==403 and response.headers['access-control-allow-origin']=='*'
    assert not calls
    for path,body in [('/api/scenario/A/degrade',{}),('/api/todolist/w/select',{'selected':'x'}),
                      ('/api/instances/start',{'definition_id':'c3_cooling'})]:
        assert client.post(path,json=body).status_code==200
    assert len(calls)==3
    assert calls[-1][2]=={'definition_id':'c3_cooling'}  # middleware didn't consume the downstream body


def test_guided_course_can_author_agents_and_skills_without_opening_handover(tmp_path, instructor):
    _, client, store, _, calls = setup(tmp_path, instructor)
    status = client.get('/api/course-access').json()
    assert status['unlocked'] is False and status['capabilities']['agent_authoring'] is True
    for path, method, body in [
        ('/api/agents', 'post', {'name':'냉각 점검', 'goal':'근거를 조사', 'tools':['neo4j','hyd-dmn']}),
        ('/api/agents/a', 'put', {'name':'새 이름', 'goal':'다른 설명', 'model':'coding'}),
        ('/api/skills', 'post', {'skill_name':'cooler', 'content':'점검'}),
        ('/api/agents/a/skills', 'post', {'skill_name':'cooler'}),
    ]:
        assert getattr(client, method)(path, json=body).status_code == 200
    for path, method, body in [
        ('/api/agents', 'post', {'model':'other'}),
        ('/api/agents/a', 'put', {'tools':['enterprise-purchase']}),
        ('/api/agent-assignments', 'put', {'definition_id':'ShiftHandover'}),
        ('/api/instances/start', 'post', {'definition_id':'ShiftHandover'}),
        ('/api/mcp/servers', 'post', {}), ('/api/agents/reset', 'post', {})]:
        assert getattr(client, method)(path, json=body).status_code == 403


def test_unlock_opens_only_handover_and_provided_documents(tmp_path,instructor):
    _,client,store,sign,calls = setup(tmp_path,instructor)
    code=sign();assert client.post('/api/course-access/unlock',json={'code':code}).status_code==200
    for path,method,body in [('/api/agents','post',{'name':'handover','model':'coding','tools':['neo4j','enterprise']}),
          ('/api/agent-assignments','put',{'definition_id':'shift_handover'}),
          ('/api/instances/start','post',{'definition_id':'ShiftHandover'})]:
        assert getattr(client,method)(path,json=body).status_code==200
    for path,method,body in [('/api/agent-assignments','put',{'definition_id':'c3_cooling'}),
          ('/api/agents','post',{'model':'other-model'}),('/api/agents','post',{'tools':['Bash']}),
          ('/api/ask','post',{'question':'anything'}),('/api/config/reset','post',{}),
          ('/api/mcp/servers','post',{}),('/api/process/definitions','post',{}),
          ('/api/instances/start','post',{'definition_id':'ask_agent'})]:
        assert getattr(client,method)(path,json=body).status_code==403
    sha=rules.CONTENT['document_hashes'][-1]
    assert client.post('/api/kg/manuals/sources/manual:hi:'+sha+'/extractions',json={}).status_code==200
    assert client.post('/api/kg/manuals/sources/manual:other:'+'0'*64+'/extractions',json={}).status_code==403
    assert client.post('/api/kg/manuals/preview',json={'data':base64.b64encode(b'arbitrary').decode()}).status_code==403


def test_shipped_knowledge_bootstrap_still_works_without_unlock_but_edits_do_not(tmp_path,instructor):
    _,client,store,sign,calls = setup(tmp_path,instructor)
    root=Path(__file__).parents[1]
    seed=json.loads((root/'it/neo4j/class-knowledge/HM-8.json').read_text(encoding='utf8'))
    raw=(root/'문서/시스템/참조/수업_문서_원문'/seed['filename']).read_bytes()
    assert client.post('/api/kg/manuals/preview',json={'data':base64.b64encode(raw).decode()}).status_code==200
    body={k:seed[k] for k in ('sections','procedures','links','knowledge')}
    body.update(source_id='manual:local:'+seed['sha256'],reviewed=True)
    assert client.post('/api/kg/manuals/commit',json=body).status_code==200
    body['procedures'][0]['name']='modified'
    assert client.post('/api/kg/manuals/commit',json=body).status_code==403
    assert client.post('/api/kg/manuals/sources/manual:local:'+seed['sha256']+'/extractions',json={}).status_code==403


def test_invalid_code_attempts_are_bounded(tmp_path,instructor):
    _,client,store,sign,calls = setup(tmp_path,instructor)
    for _ in range(5):assert client.post('/api/course-access/unlock',json={'code':'wrong'}).status_code==403
    assert client.post('/api/course-access/unlock',json={'code':sign()}).status_code==429
    assert store.status()['unlocked'] is False


def test_worker_does_not_trust_a_status_boolean_or_allow_unknown_work(instructor):
    from worker.course_access import CourseAccess
    def client(proof):return CourseAccess(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=proof)))
    locked=client({'grant':None})
    locked({'processDefinitionId':'c3_cooling'},'T_agent',{})
    with pytest.raises(ValueError):locked({'processDefinitionId':'shift_handover'},'task:draft',{})
    with pytest.raises(ValueError):client({'unlocked':True,'grant':None})({'processDefinitionId':'shift_handover'},'task:draft',{})
    opened=client({'grant':instructor[0]()})
    opened({'processDefinitionId':'shift_handover'},'task:draft',{})
    with pytest.raises(ValueError):opened({'processDefinitionId':'ask_agent'},'task:ask',{})
    with pytest.raises(ValueError):opened({'processDefinitionId':'manual_source_extraction'},'task:extract',{'manual_source':{'sha256':'0'*64}})


def test_actual_runner_checks_access_before_calling_cli(rt,tmp_path,instructor):
    from test_handover import begin,unknown_draft
    from test_worker import _settings,_fake_exec
    from worker.runner import Runner
    from worker.course_access import CourseAccess
    runtime,_=rt;inst=begin(runtime);requests=[]
    locked=CourseAccess(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'grant':None})))
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=_fake_exec(json.dumps(unknown_draft()),requests=requests),
                  resolve_provider=lambda _:object(),course_access=locked)
    assert runner.poll_once()==1 and not requests
    wi=next(w for w in runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='task:draft')
    assert wi['draft_status']=='FAILED'


def test_unlocked_runner_uses_same_handover_and_forces_course_model(rt,tmp_path,instructor):
    from test_handover import begin,unknown_draft
    from test_worker import _settings,_fake_exec
    from worker.runner import Runner
    from worker.course_access import CourseAccess
    runtime,_=rt;begin(runtime);requests=[]
    agent=runtime.repo.list_users(['agent:handover'],'hyd')[0]
    runtime.repo.upsert_user(dict(agent,model='unapproved-model'))
    opened=CourseAccess(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'grant':instructor[0]()})))
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=_fake_exec(json.dumps(unknown_draft()),requests=requests),
                  resolve_provider=lambda _:object(),course_access=opened)
    assert runner.poll_once()==1 and len(requests)==1
    assert requests[0][0].model=='coding'
    assert requests[0][1]['ENABLE_TOOL_SEARCH']=='false'


from test_inbox import rt
