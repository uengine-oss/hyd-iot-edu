"""Real managed reservation + engine lifecycle; no paid model execution."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from procsvc.classroom_api import create_app
from procsvc.classroom_authority import Denied
from test_classroom_agents import approved
from test_classroom_authority_pg import authority, DSN, KEY, POLICY  # noqa: F401
from test_instances import rt  # noqa: F401

pytestmark=pytest.mark.skipif(not DSN,reason='requires disposable classroom authority PostgreSQL')


@pytest.fixture
def setup(authority,rt):
    auth,connect=authority;runtime,_=rt
    approval=approved(runtime)
    policy=deepcopy(POLICY)
    policy['agents']={'handover.draft':approval}
    policy['actions']['agent_run']=dict(max_seconds=60,max_calls=3,max_input_bytes=1000,max_output_tokens=300)
    with connect() as db:db.execute("UPDATE hyd_classroom_grants SET policy=%s,subject='hyd'",(Jsonb(policy),))
    app=create_app(auth,source_loader=None,catalog_factory=None,runtime_factory=lambda subject:runtime,agent_enabled=True)
    return TestClient(app),runtime,auth,connect,approval


def test_approved_agent_api_joins_duplicates_and_returns_only_reviewable_proposal(setup):
    client,runtime,auth,connect,approval=setup
    headers={'Authorization':'Bearer '+KEY};body={'reference':'handover.draft','inputs':{'memo':'실제 상태 확인 필요'}}
    first=client.post('/v1/classroom/agents',headers=headers,json=body)
    assert first.status_code==200,first.text
    run=first.json()['run_id']
    repeat=client.post('/v1/classroom/agents',headers=headers,json=body).json()
    assert repeat['run_id']==run and repeat['reused']
    assert len(runtime.repo.instances)==1
    url=f'/v1/classroom/agents/runs/{run}/result'
    assert client.get(url,headers=headers).json()=={'status':'PENDING','output':None}
    wi=runtime.repo.fetch_pending_task('cliagents','test-agent')[0]
    runtime.repo.save_task_result(wi['id'],{'answer':'확인 필요'},final=True);runtime.poll_once()
    result=client.get(url,headers=headers)
    assert result.status_code==200,result.text
    assert result.json()=={'status':'DONE','output':{'answer':'확인 필요'},'historical_proposal':True,'requires_local_review':True}
    assert client.get(url,headers=headers).json()==result.json()
    assert client.post('/v1/classroom/agents',headers=headers,json=body).status_code==409
    with connect() as db:
        assert db.execute('SELECT calls FROM hyd_classroom_grants').fetchone()['calls']==0
        assert db.execute('SELECT count(*) AS n FROM hyd_classroom_runs').fetchone()['n']==1


def test_request_id_prompt_revision_and_unknown_agent_cannot_bypass_approval(setup):
    client,runtime,auth,_,approval=setup
    headers={'Authorization':'Bearer '+KEY};body={'reference':'handover.draft','inputs':{'memo':'x'}}
    for field in ('request_id','prompt','model','revision'):
        assert client.post('/v1/classroom/agents',headers=headers,json=dict(body,**{field:'new'})).status_code==422
    assert client.post('/v1/classroom/agents',headers=headers,json=dict(body,reference='free-topic')).status_code==403
    assert client.post('/v1/classroom/agents',headers=headers,json=dict(body,inputs={'memo':'x','prompt':'new'})).status_code==403
    with pytest.raises(Denied):auth.reserve(KEY,'agent_run',{'reference':'handover.draft','revision':'changed','inputs':{'memo':'x'}})
    assert not runtime.repo.instances


def test_pending_failure_is_not_success_and_default_route_stays_disabled(setup):
    client,runtime,auth,_,_=setup
    headers={'Authorization':'Bearer '+KEY};body={'reference':'handover.draft','inputs':{'memo':'x'}}
    disabled=TestClient(create_app(auth,source_loader=None,catalog_factory=None,runtime_factory=lambda subject:runtime))
    assert disabled.post('/v1/classroom/agents',headers=headers,json=body).status_code==503
    run=client.post('/v1/classroom/agents',headers=headers,json=body).json()['run_id']
    wi=runtime.repo.fetch_pending_task('cliagents','failed-agent')[0]
    wi['draft_status']='FAILED';runtime.repo.update_workitem(wi)
    assert client.get(f'/v1/classroom/agents/runs/{run}/result',headers=headers).json()=={'status':'FAILED','output':None}
    assert auth.read_run(KEY,run)['state']=='FAILED'


def test_real_agent_snapshot_is_rechecked_before_model_permission(setup,tmp_path,monkeypatch):
    from procsvc import classroom_model
    from fastapi import HTTPException
    client,runtime,auth,_,_=setup
    secret='private-model-binding-test-'*3
    path=tmp_path/'runtime.key';path.write_text(secret,encoding='utf8')
    monkeypatch.setenv('HYD_WORKER_RUNTIME_KEY_FILE',str(path))
    run=client.post('/v1/classroom/agents',headers={'Authorization':'Bearer '+KEY},
                    json={'reference':'handover.draft','inputs':{'memo':'확인 필요'}}).json()['run_id']
    wi=runtime.repo.fetch_pending_task('cliagents','actual-claim')[0]
    body={'tenant_id':runtime.tenant_id,'todo_id':wi['id'],'consumer':wi['consumer']}
    permit=classroom_model.issue(runtime,auth,body,'Bearer '+secret)
    assert classroom_model.authorize(runtime,auth,permit['token'])['run_id']==run
    user=runtime.repo.list_users(['agent:class-test'],runtime.tenant_id)[0]
    runtime.repo.upsert_user(dict(user,persona='수업과 무관한 변경'))
    with pytest.raises(HTTPException):classroom_model.authorize(runtime,auth,permit['token'])


def test_managed_mcp_to_student_exchange_keeps_name_schema_and_scoped_result(setup,tmp_path,monkeypatch):
    import asyncio,json,httpx
    from pathlib import Path
    from fastmcp import Client as McpClient
    from worker import managed_tools
    from procsvc.classroom_client import Client as Student
    from test_worker_managed_tools import META
    _,runtime,auth,connect,_=setup
    secret='private-end-to-end-tool-test-'*3
    keyfile=tmp_path/'runtime.key';keyfile.write_text(secret,encoding='utf8')
    monkeypatch.setenv('HYD_WORKER_RUNTIME_KEY_FILE',str(keyfile))
    with connect() as db:
        db.execute((Path(__file__).parents[1]/'it/supabase/migrations/20261027000067_classroom_tool_io.sql').read_text(encoding='utf8'))
        policy=db.execute('SELECT policy FROM hyd_classroom_grants').fetchone()['policy']
        policy['tool_io']=dict(tools=['enterprise/spare_stock'],max_calls=3,max_input_bytes=200,
            max_result_bytes=40000,total_result_bytes=50000,catalog={'enterprise/spare_stock':{
                'description':META['description'],'inputSchema':META['inputSchema'],'annotations':{'readOnlyHint':True}}})
        db.execute('UPDATE hyd_classroom_grants SET policy=%s',(Jsonb(policy),))
    client=TestClient(create_app(auth,source_loader=None,catalog_factory=None,runtime_factory=lambda subject:runtime,
                                upstream_factory=lambda:{},agent_enabled=True))
    run=client.post('/v1/classroom/agents',headers={'Authorization':'Bearer '+KEY},
                    json={'reference':'handover.draft','inputs':{'memo':'확인 필요'}}).json()['run_id']
    wi=runtime.repo.fetch_pending_task('cliagents','managed-worker')[0]
    permit=client.post('/internal/worker/model-runtime',headers={'Authorization':'Bearer '+secret},
        json={'tenant_id':runtime.tenant_id,'todo_id':wi['id'],'consumer':wi['consumer']}).json()
    local_reads=[];exchanges=[]
    def read(tool,args):
        local_reads.append((tool,args))
        return {'is_error':False,'result':{'available':7,'source':'student-local'}}
    def bridge(request):
        try:response=client.request(request.method,request.url.path,headers=dict(request.headers),content=request.content)
        except Exception as exc:
            exchanges.append(('request-error',request.url.path,type(exc).__name__,str(exc)))
            raise
        exchanges.append((request.url.path,response.status_code))
        if request.url.path=='/internal/worker/tool-request' and response.status_code==200:
            try:assert student.exchange_tool(run,read)['status']=='DONE'
            except Exception as exc:
                exchanges.append(('student-error',type(exc).__name__,str(exc)))
                raise
        return httpx.Response(response.status_code,content=response.content)
    network=httpx.MockTransport(bridge)
    student=Student('https://teacher.example',lambda:KEY,tmp_path/'student.sqlite3',transport=network)
    transport=managed_tools.Transport('https://teacher.example',permit['token'],transport=network)
    catalog=transport.request('catalog',{})['tools']
    assert catalog==[META]
    async def exercise():
        async with McpClient(managed_tools.server('enterprise',catalog,transport)) as mcp:
            result=await mcp.call_tool('spare_stock',{'part':'P-PMP-SEAL'})
            assert json.loads(result.content[0].text)=={'available':7,'source':'student-local'}
    try:asyncio.run(exercise())
    except Exception:pytest.fail(str(exchanges))
    assert local_reads==[('enterprise/spare_stock',{'part':'P-PMP-SEAL'})]
    assert auth.read_run(KEY,run)['calls']==0
    with pytest.raises(Exception):transport.request('request',{'call_id':'bad','tool':'enterprise/spare_stock','arguments':{'part':9}})
