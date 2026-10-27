import asyncio
import json
from pathlib import Path
import httpx
import pytest
from fastmcp import Client
from worker import question_tools, managed_tools
from worker.runtime_credentials import RuntimeConnectionError
from test_instance_mode import world  # noqa: F401


def test_question_proxy_discovery_and_execution_allow_reads_only(tmp_path):
    calls=[]
    tools=[{'name':'inputs','description':'입력','input_schema':{'type':'object','properties':{}},'callable':True},
           {'name':'evaluate_cards','description':'평가','input_schema':{'type':'object','properties':{}},'callable':True},
           {'name':'submit_decision','description':'쓰기','input_schema':{'type':'object','properties':{}},'callable':True}]
    def handle(req):
        calls.append((req.method,req.url.path))
        if req.method=='GET':return httpx.Response(200,json={'status':'ok','tools':tools})
        return httpx.Response(200,json={'result':{'is_error':False,'truncated':False,'json':True,'text':json.dumps({'result':'ok','document':[1]})}})
    transport=httpx.MockTransport(handle)
    config,names=question_tools.attach({'mcpServers':{'hyd-dmn':{'url':'http://ignored'}}},tmp_path,'http://process:8080',transport=transport)
    assert set(names['hyd-dmn'])=={'inputs','evaluate_cards'}
    rows=json.loads((tmp_path/'question-tool-catalog.json').read_text(encoding='utf8'))
    assert [x['name'] for x in rows]==['inputs','evaluate_cards']
    assert set(config['mcpServers'])=={'hyd-dmn'}
    async def run():
        proxy=managed_tools.server('hyd-dmn',rows,question_tools.Transport('http://process:8080',transport=transport))
        async with Client(proxy) as c:
            listed=await c.list_tools()
            assert {t.name for t in listed}=={'inputs','evaluate_cards'}
            result=await c.call_tool('inputs',{})
            assert json.loads(result.content[0].text)=={'result':'ok','document':[1]}
            with pytest.raises(Exception):await c.call_tool('submit_decision',{})
    asyncio.run(run())
    assert calls==[('GET','/api/mcp/servers/hyd-dmn/tools'),('POST','/api/mcp/servers/hyd-dmn/tools/inputs/call')]


def test_question_proxy_fails_closed_on_truncation_and_disallowed_server(tmp_path):
    with pytest.raises(RuntimeConnectionError):question_tools.attach({'mcpServers':{'untrusted':{}}},tmp_path,'http://process:8080')
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'result':{'is_error':False,'truncated':True,'text':'partial'}}))
    client=question_tools.Transport('http://process:8080',transport=transport)
    with pytest.raises(RuntimeConnectionError):client.call('hyd-dmn/inputs',{})
    with pytest.raises(RuntimeConnectionError):client.call('hyd-dmn/submit_decision',{})


def test_actual_question_runner_uses_proxy_and_exact_read_permissions(world, tmp_path, monkeypatch):
    from test_b5_ask import _people, _ask, _cli, ANSWER
    from test_worker import _settings
    from worker.runner import Runner
    from worker import managed_model
    runtime=world['rt'];_people(runtime);_ask(runtime)
    monkeypatch.setenv('HYD_MANAGED_MODEL_URL','http://process:8080')
    monkeypatch.setattr(managed_model,'attach',lambda *args:None)
    def attach(config,workdir,url):
        assert set(config['mcpServers'])=={'neo4j','enterprise','hyd-dmn'}
        return {'mcpServers':{'hyd-dmn':{'command':'python','args':['-m','worker.question_tools']}}}, {'hyd-dmn':['inputs','evaluate_cards']}
    monkeypatch.setattr(question_tools,'attach',attach)
    requests=[]
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=_cli(ANSWER,requests=requests),
                  schema_prompt='# schema',resolve_provider=lambda _:object(),course_access=lambda *args:None)
    assert runner.poll_once()==1 and len(requests)==1
    request=requests[0]
    args=request.extra_args
    allowed=args[args.index('--allowedTools')+1].split(',')
    assert {x for x in allowed if x.startswith('mcp__')}=={'mcp__hyd-dmn__inputs','mcp__hyd-dmn__evaluate_cards'}
    assert not any('*' in x or 'submit_' in x for x in allowed)
    config=json.loads((Path(request.workdir)/'.mcp.json').read_text(encoding='utf8'))
    assert set(config['mcpServers'])=={'hyd-dmn'}


def test_question_with_no_selected_tools_does_not_inherit_every_server(world, tmp_path, monkeypatch):
    from test_b5_ask import _people, _ask, _cli, ANSWER
    from test_worker import _settings
    from worker.runner import Runner
    from worker import managed_model
    runtime=world['rt'];_people(runtime)
    source=runtime.repo.list_users(['sys:agent'],'hyd')[0]
    runtime.repo.upsert_user({**source,'tools':''})
    _ask(runtime)
    monkeypatch.setenv('HYD_MANAGED_MODEL_URL','http://process:8080')
    monkeypatch.setattr(managed_model,'attach',lambda *args:None)
    def attach(config,workdir,url):
        assert config['mcpServers']=={}
        return {'mcpServers':{}}, {}
    monkeypatch.setattr(question_tools,'attach',attach)
    requests=[]
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=_cli(ANSWER,requests=requests),
                  schema_prompt='# schema',resolve_provider=lambda _:object(),course_access=lambda *args:None)
    assert runner.poll_once()==1 and len(requests)==1
    allowed=requests[0].extra_args[requests[0].extra_args.index('--allowedTools')+1].split(',')
    assert not any(x.startswith('mcp__') for x in allowed)
