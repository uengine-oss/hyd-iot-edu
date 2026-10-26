import json
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from procsvc import classroom_model as model
from procsvc.classroom_authority import Denied
from worker import managed_model

PRIVATE = 'private-runtime-test-'*3
UPSTREAM = 'upstream-test-secret'


@pytest.fixture
def setup(monkeypatch, tmp_path):
    path = tmp_path/'runtime.key'; path.write_text(PRIVATE, encoding='utf8')
    monkeypatch.setenv('HYD_WORKER_RUNTIME_KEY_FILE', str(path))
    row = dict(id='todo-1', tenant_id='class-1', consumer='worker:claim-1', proc_inst_id='instance-1',
               status='IN_PROGRESS', draft_status='STARTED', lease_until=time.time()+120)
    inst = {'variables_data': [{'key': 'extraction_cache', 'value': {'key': 'cache-1'}}]}
    rt = SimpleNamespace(tenant_id='class-1', repo=SimpleNamespace(
        get_workitem=lambda wid: row if wid==row['id'] else None, get_instance=lambda pid: inst))
    class Authority:
        calls = 0
        def execution_context(self, subject, work, cache_key=None, *, execution_run_id=None):
            assert (subject, work, cache_key) == ('class-1', 'instance-1', 'cache-1')
            return dict(run_id='run-1', model='class-model', deadline=time.time()+1200)
        def charge_execution(self, run_id, **kw):
            assert run_id == 'run-1'
            if self.calls>=2: raise Denied('수업 호출 한도 초과')
            self.calls += 1
    authority = Authority()
    body = dict(tenant_id='class-1', todo_id='todo-1', consumer='worker:claim-1')
    return rt, row, authority, body


@pytest.mark.parametrize('change', ['student-key', 'wrong-worker', 'closed', 'expired-lease'])
def test_only_current_managed_worker_can_mint_a_model_permit(setup, change):
    rt, row, authority, body = setup
    authorization = 'Bearer '+PRIVATE
    if change=='student-key': authorization='Bearer student-class-key'
    if change=='wrong-worker': body['consumer']='different-worker'
    if change=='closed': row['status']='DONE'
    if change=='expired-lease': row['lease_until']=time.time()-1
    with pytest.raises(HTTPException): model.issue(rt, authority, body, authorization)
    assert authority.calls == 0


def test_permit_tampering_model_override_and_lost_lease_never_charge(setup):
    rt, row, authority, body = setup
    permit = model.issue(rt, authority, body, 'Bearer '+PRIVATE)
    payload = json.dumps(dict(model='class-model', max_tokens=50, messages=[{'role':'user','content':'approved'}])).encode()
    with pytest.raises(HTTPException): model.prepare(rt, authority, permit['token']+'bad', payload)
    with pytest.raises(HTTPException): model.prepare(rt, authority, permit['token'], payload.replace(b'class-model', b'other-model'))
    row['consumer']='new-owner'
    with pytest.raises(HTTPException): model.prepare(rt, authority, permit['token'], payload)
    assert authority.calls == 0


def test_http_forwarder_charges_each_retry_and_does_not_forward_student_credentials(setup, monkeypatch):
    rt, _, authority, body = setup
    sent=[]
    def upstream(request):
        sent.append(request)
        assert request.headers['x-api-key']==UPSTREAM
        assert 'HydModel' not in str(request.headers)
        return httpx.Response(200, text='data: {"type":"message_stop"}\n\n', headers={'content-type':'text/event-stream'})
    client_class=httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: client_class(transport=httpx.MockTransport(upstream), **kw))
    app=FastAPI()
    model.mount(app, authority, lambda tenant:rt, lambda:dict(url='https://upstream.example', key=UPSTREAM))
    client=TestClient(app)
    assert client.post('/internal/worker/model-runtime', headers={'Authorization':'Bearer student-key'}, json=body).status_code==403
    permit=client.post('/internal/worker/model-runtime', headers={'Authorization':'Bearer '+PRIVATE}, json=body).json()
    request=dict(model='class-model', max_tokens=50, messages=[{'role':'user','content':'approved'}], stream=True)
    assert client.post('/internal/model/v1/messages', headers={'x-api-key':'student-key'}, json=request).status_code==403
    for _ in range(2):
        response=client.post('/internal/model/v1/messages', headers={'x-api-key':permit['token']}, json=request)
        assert response.status_code==200 and 'message_stop' in response.text
    assert client.post('/internal/model/v1/messages', headers={'x-api-key':permit['token']}, json=request).status_code==429
    assert len(sent)==2 and authority.calls==2


def test_upstream_errors_do_not_leak_keys_or_retry_automatically(setup, monkeypatch):
    rt, _, authority, body=setup
    client_class=httpx.AsyncClient
    calls=[]
    def failed(request):
        calls.append(1)
        return httpx.Response(500, text=UPSTREAM)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: client_class(transport=httpx.MockTransport(failed), **kw))
    app=FastAPI(); model.mount(app,authority,lambda _:rt,lambda:dict(url='https://upstream.example',key=UPSTREAM))
    permit=model.issue(rt,authority,body,'Bearer '+PRIVATE)
    response=TestClient(app).post('/internal/model/v1/messages',headers={'x-api-key':permit['token']},
              json=dict(model='class-model',max_tokens=50,messages=[{'role':'user','content':'approved'}]))
    assert response.status_code==502 and UPSTREAM not in response.text and len(calls)==1


def test_worker_environment_has_only_claim_bound_model_key(setup, monkeypatch):
    import io
    rt, row, authority, body=setup
    reply=model.issue(rt,authority,body,'Bearer '+PRIVATE)
    monkeypatch.setenv('HYD_MANAGED_MODEL_URL','https://managed.example')
    class Opener:
        def open(self, request, timeout):
            assert request.full_url=='https://managed.example/internal/worker/model-runtime'
            assert request.headers['Authorization']=='Bearer '+PRIVATE
            return io.BytesIO(json.dumps(reply).encode())
    monkeypatch.setattr(managed_model.urllib.request,'build_opener',lambda *a:Opener())
    result=managed_model.attach(row,'class-1','claude-code')
    assert result['env']['ANTHROPIC_API_KEY']==reply['token']
    assert result['env']['LLM_API_KEY']==result['env']['OPENAI_API_KEY']==''
    assert result['env']['ANTHROPIC_BASE_URL']=='https://managed.example/internal/model'
    assert result['secrets']==[reply['token']]


def test_required_managed_mode_cannot_silently_fall_back(monkeypatch):
    monkeypatch.delenv('HYD_MANAGED_MODEL_URL',raising=False)
    monkeypatch.setenv('HYD_MANAGED_MODEL_REQUIRED','1')
    with pytest.raises(managed_model.RuntimeConnectionError): managed_model.attach({},'class-1','claude-code')
