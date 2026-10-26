import asyncio
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastmcp import Client

from worker import managed_tools,managed_model
from worker.runtime_credentials import RuntimeConnectionError
from worker.runner import Runner
from procsvc import classroom_agents
from test_classroom_agents import approved
from test_instances import rt  # noqa: F401
from test_worker import _settings,_fake_exec


META={'server':'enterprise','name':'spare_stock','description':'학생 현재 재고',
      'inputSchema':{'type':'object','properties':{'part':{'type':'string'}},'required':['part'],'additionalProperties':False}}
MANAGED={'url':'https://teacher.example','token':'HydModel test-permit','model':'class-model',
         'env':{'ANTHROPIC_API_KEY':'HydModel test-permit'},'secrets':['HydModel test-permit']}


def test_original_mcp_name_schema_json_and_error_are_preserved():
    calls=[]
    class Transport:
        def call(self,tool,args):
            calls.append((tool,args))
            return {'state':'FAILED','result':{'error':'조회 실패'}} if args['part']=='missing' else {'state':'DONE','result':[{'available':7}]}
    async def run():
        async with Client(managed_tools.server('enterprise',[META],Transport())) as client:
            tools=await client.list_tools()
            assert [tool.name for tool in tools]==['spare_stock'] and tools[0].inputSchema==META['inputSchema']
            result=await client.call_tool('spare_stock',{'part':'P-PMP-SEAL'})
            assert json.loads(result.content[0].text)==[{'available':7}]
            with pytest.raises(Exception):await client.call_tool('spare_stock',{'part':9})
            assert len(calls)==1
            with pytest.raises(Exception):await client.call_tool('spare_stock',{'part':'missing'})
    asyncio.run(run())
    assert calls==[('enterprise/spare_stock',{'part':'P-PMP-SEAL'}),('enterprise/spare_stock',{'part':'missing'})]


def test_transport_never_accepts_redirects_or_arbitrary_student_key():
    with pytest.raises(RuntimeConnectionError):managed_tools.Transport('http://external.example','HydModel x')
    with pytest.raises(RuntimeConnectionError):managed_tools.Transport('https://teacher.example','student-key')
    client=managed_tools.Transport(MANAGED['url'],MANAGED['token'],transport=httpx.MockTransport(
        lambda req:httpx.Response(302,headers={'location':'https://other.example'})))
    with pytest.raises(RuntimeConnectionError):client.request('catalog',{})


def test_transport_cancels_a_stalled_stream_at_absolute_deadline():
    closed=[]
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{'
            await asyncio.sleep(10)
        async def aclose(self):closed.append(True)
    client=managed_tools.Transport(MANAGED['url'],MANAGED['token'],timeout=0.02,
        transport=httpx.MockTransport(lambda req:httpx.Response(200,stream=Stream())))
    started=time.monotonic()
    with pytest.raises(RuntimeConnectionError):client.request('catalog',{})
    assert closed and time.monotonic()-started<1


def test_worker_replaces_teacher_mcp_before_cli_and_never_uses_teacher_credentials(rt,tmp_path,monkeypatch):
    runtime,_=rt;approval=approved(runtime)
    runtime.repo.upsert_tenant({'id':runtime.tenant_id,'mcp':{'mcpServers':{'enterprise':{'url':'https://instructor-only.example/mcp'}}}})
    classroom_agents.start(runtime,approval,{'memo':'상태 확인'},str(uuid4()),'handover.draft')
    permits=[]
    monkeypatch.setattr(managed_model,'attach',lambda *a:(permits.append(1) or MANAGED))
    monkeypatch.setattr(managed_tools.Transport,'request',lambda self,*a,**kw:{'tools':[META]})
    monkeypatch.setattr('worker.runtime_credentials.attach',lambda *a:pytest.fail('must not resolve instructor MCP credentials'))
    requests=[]
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=_fake_exec('{"answer":"확인 필요"}',requests=requests),
                  schema_prompt='# schema',resolve_provider=lambda _:object())
    assert runner.poll_once()==1 and len(requests)==1 and permits==[1]
    request=requests[0][0];root=Path(request.workdir)
    config=json.loads((root/'.mcp.json').read_text(encoding='utf8'))
    assert MANAGED['token'] not in (root/'.mcp.json').read_text(encoding='utf8')
    assert set(config['mcpServers'])=={'enterprise'}
    assert config['mcpServers']['enterprise']['args'][:2]==['-m','worker.managed_tools']
    context=(root/'context/input.json').read_text(encoding='utf8')
    assert 'instructor-only' not in context and 'HydModel' not in context
    assert request.model=='class-model'


def test_missing_managed_permission_cannot_fall_back_to_local_model(rt,tmp_path,monkeypatch):
    runtime,_=rt;approval=approved(runtime)
    classroom_agents.start(runtime,approval,{'memo':'확인'},str(uuid4()),'handover.draft')
    monkeypatch.setattr(managed_model,'attach',lambda *a:None)
    requests=[]
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=_fake_exec('{"answer":"x"}',requests=requests),
                  schema_prompt='# schema',resolve_provider=lambda _:object())
    runner.poll_once()
    assert not requests


@pytest.mark.parametrize('change',['missing','write','schema','unlisted'])
def test_instructor_catalog_must_match_read_only_schema_contract(change):
    from copy import deepcopy
    from procsvc.classroom_tool_io import catalog
    from procsvc.classroom_authority import Denied
    contract={'tools':['enterprise/spare_stock'],'catalog':{'enterprise/spare_stock':{
        'description':META['description'],'inputSchema':deepcopy(META['inputSchema']),'annotations':{'readOnlyHint':True}}}}
    if change=='missing':contract.pop('catalog')
    if change=='write':contract['catalog']['enterprise/spare_stock']['annotations']['readOnlyHint']=False
    if change=='schema':contract['catalog']['enterprise/spare_stock']['inputSchema']['type']='not-a-type'
    if change=='unlisted':contract['tools'].append('enterprise/PR_CREATE')
    with pytest.raises(Denied):catalog(contract)
