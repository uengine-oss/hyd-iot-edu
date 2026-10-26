"""Real PG reverse RPC: student-specific current facts, no public call enqueue."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
import pytest

from procsvc.classroom_authority import Denied, key_hash
from procsvc.classroom_tool_io import ToolIO
from procsvc.classroom_api import create_app
from test_classroom_authority_pg import authority, DSN, KEY, POLICY  # noqa: F401

pytestmark = pytest.mark.skipif(not DSN, reason='requires disposable classroom authority PostgreSQL')


@pytest.fixture
def channel(authority):
    auth, connect = authority
    policy = deepcopy(POLICY)
    policy['actions']['agent_run'] = dict(max_seconds=60,max_calls=3,max_input_bytes=1000,max_output_tokens=300)
    policy['tool_io'] = dict(tools=['hyd-dmn/evaluate_cards','enterprise/spare_stock'],max_calls=2,
                             max_input_bytes=200,max_result_bytes=40000,total_result_bytes=50000)
    policy['tool_io']['catalog']={tool:{'inputSchema':{'type':'object'},'annotations':{'readOnlyHint':True}}
                                 for tool in policy['tool_io']['tools']}
    policy['agents']={'test-tools':{'revision':'a'*64,'input_schema':{'type':'object','properties':{},'additionalProperties':False}}}
    with connect() as db:
        db.execute((Path(__file__).parents[1]/'it/supabase/migrations/20261027000067_classroom_tool_io.sql').read_text(encoding='utf8'))
        db.execute('UPDATE hyd_classroom_grants SET policy=%s',(Jsonb(policy),))
    run=auth.reserve(KEY,'agent_run',{'reference':'test-tools','revision':'a'*64,'inputs':{}})
    return ToolIO(auth),str(run['id']),connect,policy


def test_concurrent_duplicate_call_and_result_are_joined(channel):
    io,run,_,_=channel
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids=list(pool.map(lambda _:io.enqueue(run,'tool-call-1','enterprise/spare_stock',{'part':'P-PMP-SEAL'}),range(4)))
    assert len(set(ids))==1
    assert io.pending(KEY,run)==[dict(id=ids[0],tool='enterprise/spare_stock',arguments={'part':'P-PMP-SEAL'})]
    response={'on_hand':10,'reserved':3,'available':7}
    assert io.complete(KEY,run,ids[0],result=response,is_error=False)=={'status':'DONE','reused':False}
    assert io.complete(KEY,run,ids[0],result=response,is_error=False)['reused']
    assert io.result(run,ids[0])=={'state':'DONE','result':response}
    assert io.pending(KEY,run)==[]
    with pytest.raises(Denied):io.complete(KEY,run,ids[0],result={'available':99},is_error=False)
    with pytest.raises(Denied):io.enqueue(run,'tool-call-1','enterprise/spare_stock',{'part':'other'})


def test_errors_limits_and_missing_data_are_not_success(channel):
    io,run,_,_=channel
    with pytest.raises(Denied):io.enqueue(run,'x','enterprise/PR_CREATE',{})
    with pytest.raises(Denied):io.enqueue(run,'x','hyd-dmn/evaluate_cards',{'x':'a'*201})
    first=io.enqueue(run,'1','hyd-dmn/evaluate_cards',{})
    assert io.result(run,first)=={'state':'WAITING','result':None}
    io.complete(KEY,run,first,result={'error':'student database unavailable'},is_error=True)
    assert io.result(run,first)['state']=='FAILED'
    second=io.enqueue(run,'2','hyd-dmn/evaluate_cards',{})
    with pytest.raises(Denied):io.enqueue(run,'3','hyd-dmn/evaluate_cards',{})
    with pytest.raises(Denied):io.complete(KEY,run,second,result='a'*40001,is_error=False)
    with pytest.raises(Denied):io.complete(KEY,run,str(uuid4()),result={},is_error=False)
    assert io.result(run,second)['state']=='WAITING'


@pytest.mark.parametrize('change',["UPDATE hyd_classroom_grants SET enabled=false",
    "UPDATE hyd_classroom_runs SET deadline=now()-interval '1 second'",
    "UPDATE hyd_classroom_runs SET state='DONE'",
    "UPDATE hyd_classroom_grants SET scope='changed'"])
def test_revoked_changed_expired_and_completed_runs_cannot_exchange_results(channel,change):
    io,run,connect,_=channel
    request=io.enqueue(run,'1','hyd-dmn/evaluate_cards',{})
    with connect() as db:db.execute(change)
    with pytest.raises(Denied):io.pending(KEY,run)
    with pytest.raises(Denied):io.complete(KEY,run,request,result={},is_error=False)
    with pytest.raises(Denied):io.result(run,request)


def test_public_api_ownership_body_limit_and_no_enqueue(channel):
    io,run,connect,policy=channel
    other='another-student-key-'+'y'*32
    with connect() as db:
        db.execute("INSERT INTO hyd_classroom_grants(key_hash,subject,scope,policy,expires_at) VALUES (%s,'student-2','class-1',%s,now()+interval '1 day')",
                   (key_hash(other),Jsonb(policy)))
    request=io.enqueue(run,'1','hyd-dmn/evaluate_cards',{})
    app=create_app(io.authority,source_loader=None,runtime_factory=None,catalog_factory=None)
    client=TestClient(app);headers={'Authorization':'Bearer '+KEY}
    endpoint=f'/v1/classroom/runs/{run}/tool-requests'
    assert client.get(endpoint,headers={'Authorization':'Bearer '+other}).status_code==403
    assert client.get(endpoint,headers=headers).json()['requests'][0]['id']==request
    assert client.post(endpoint,headers=headers,json={'tool':'evil'}).status_code==405
    payload=dict(run_id=run,request_id=request,result={'text':'한'*10000},is_error=False)
    assert client.post('/v1/classroom/tool-results',headers={'Authorization':'Bearer '+other},json=payload).status_code==403
    assert client.post('/v1/classroom/tool-results',headers=headers,json=payload).json()['status']=='DONE'
    assert client.post('/v1/classroom/tool-results',headers=headers,content=b'x'*192001).status_code==413
    assert client.post('/v1/classroom/tool-results',headers=headers,json=dict(payload,model='other')).status_code==422


def test_student_current_observation_is_durable_for_retry_not_cached_for_new_call(channel,tmp_path):
    import httpx
    from fastapi import HTTPException
    from procsvc.classroom_client import Client
    io,run,_,_=channel
    app=TestClient(create_app(io.authority,source_loader=None,runtime_factory=None,catalog_factory=None))
    fail=[True];observed=[]
    def bridge(request):
        if request.method=='POST' and fail[0]:
            fail[0]=False
            raise httpx.ReadTimeout('lost connection')
        r=app.request(request.method,request.url.path,headers=dict(request.headers),content=request.content)
        return httpx.Response(r.status_code,content=r.content)
    student=Client('https://class.example',lambda:KEY,tmp_path/'client.sqlite3',transport=httpx.MockTransport(bridge))
    def execute(tool,args):
        observed.append((tool,args))
        return {'is_error':False,'result':{'available':len(observed)}}
    first=io.enqueue(run,'1','enterprise/spare_stock',{})
    with pytest.raises(HTTPException):student.exchange_tool(run,execute)
    assert student.exchange_tool(run,execute)['status']=='DONE'
    assert len(observed)==1 and io.result(run,first)['result']['available']==1
    second=io.enqueue(run,'2','enterprise/spare_stock',{})
    student.exchange_tool(run,execute)
    assert len(observed)==2 and io.result(run,second)['result']['available']==2
    assert student.exchange_tool(run,execute)['status']=='IDLE'


def test_total_response_budget_cannot_be_bypassed_by_new_call_id(channel):
    io,run,_,_=channel
    first=io.enqueue(run,'1','hyd-dmn/evaluate_cards',{})
    io.complete(KEY,run,first,result='x'*30000,is_error=False)
    second=io.enqueue(run,'2','hyd-dmn/evaluate_cards',{})
    with pytest.raises(Denied):io.complete(KEY,run,second,result='x'*30000,is_error=False)
    assert io.result(run,second)['state']=='WAITING'


def test_worker_claim_to_student_result_is_bound_to_one_authorized_run(channel,tmp_path,monkeypatch):
    import time
    from types import SimpleNamespace
    io,run,_,_=channel
    monkeypatch.setattr('procsvc.classroom_agents.verify_instance',lambda runtime,inst:None)
    monkeypatch.setattr('procsvc.classroom_agents.verify_tool',lambda runtime,inst,tool:None)
    secret='private-test-worker-key-'*3
    path=tmp_path/'runtime.key';path.write_text(secret,encoding='utf8')
    monkeypatch.setenv('HYD_WORKER_RUNTIME_KEY_FILE',str(path))
    io.authority.bind_work(KEY,run,'managed-task-1')
    row=dict(id='todo-1',tenant_id='student-1',consumer='worker:claim-1',proc_inst_id='managed-task-1',
             status='IN_PROGRESS',draft_status='STARTED',lease_until=time.time()+120)
    inst={'variables_data':[{'key':'classroom_execution','value':{'run_id':run}}]}
    runtime=SimpleNamespace(tenant_id='student-1',repo=SimpleNamespace(
        get_instance=lambda pid:inst if pid=='managed-task-1' else None,
        get_workitem=lambda wid:row if wid=='todo-1' else None))
    client=TestClient(create_app(io.authority,source_loader=None,catalog_factory=None,
        runtime_factory=lambda subject:runtime,upstream_factory=lambda:{}))
    auth={'Authorization':'Bearer '+KEY}
    body={'tenant_id':'student-1','todo_id':'todo-1','consumer':'worker:claim-1'}
    assert client.post('/internal/worker/model-runtime',headers=auth,json=body).status_code==403
    permit=client.post('/internal/worker/model-runtime',headers={'Authorization':'Bearer '+secret},json=body)
    assert permit.status_code==200,permit.text
    worker={'Authorization':'Bearer '+permit.json()['token']}
    call={'call_id':'call-1','tool':'enterprise/spare_stock','arguments':{'part':'P-PMP-SEAL'}}
    assert client.post('/internal/worker/tool-request',headers=auth,json=call).status_code==403
    assert client.post('/internal/worker/tool-request',headers=worker,json=dict(call,run_id='other')).status_code==422
    response=client.post('/internal/worker/tool-request',headers=worker,json=call)
    assert response.status_code==200,response.text
    request=response.json()['request_id']
    assert client.post('/internal/worker/tool-result',headers=worker,json={'request_id':request}).json()['state']=='WAITING'
    assert client.get(f'/v1/classroom/runs/{run}/tool-requests',headers=auth).json()['requests'][0]['id']==request
    assert client.post('/v1/classroom/tool-results',headers=auth,json={
        'run_id':run,'request_id':request,'result':{'available':7},'is_error':False}).status_code==200
    assert client.post('/internal/worker/tool-result',headers=worker,json={'request_id':request}).json()=={
        'state':'DONE','result':{'available':7}}
    row['consumer']='worker:new-claim'
    assert client.post('/internal/worker/tool-result',headers=worker,json={'request_id':request}).status_code==409
