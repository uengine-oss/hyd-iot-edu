"""The managed catalog and actual CLI must expose the same handover reads."""
import json
from uuid import uuid4

import httpx
import pytest

from procsvc import classroom_agents as agents
from procsvc.classroom_authority import Denied
from worker import managed_tools, managed_model
from worker.runner import Runner
from worker.settings import handover_allowed_tools, DEFAULT_ALLOWED_TOOLS
from test_inbox import rt
from test_handover import begin, unknown_draft
from test_worker import _settings, _fake_exec
from test_worker_managed_tools import MANAGED


def test_managed_handover_catalog_call_gate_and_cli_are_identical(rt,tmp_path,monkeypatch):
    runtime,_=rt
    source=runtime.definition_for(begin(runtime)).raw
    props={name:{'type':'string'} for name in source['activities'][0]['inputData']}
    for name in ('sender_notes','receiver_notes'):props[name]={'type':['string','null']}
    approval=dict(definition=source['processDefinitionId'],version=source['version'],activity='task:draft',revision='pending',
        input_schema={'type':'object','properties':props,'additionalProperties':False})
    approval['revision']=agents.revision(runtime,approval)
    inst=agents.start(runtime,approval,dict(asset='HYD-01',shift_label='next',as_of='2026-10-27T00:00:00Z',
        work_notes='check',sender_notes=None,receiver_notes=None),str(uuid4()),'shift.draft')
    # Remove only the ordinary fixture task from the poll queue.
    for row in runtime.repo.list_workitems(limit=None):
        if row['proc_inst_id']!=inst['proc_inst_id']:runtime.repo.update_workitem(dict(row,status='DONE'))
    rows=[dict(server=s,name=n,description=n,inputSchema={'type':'object'}) for s,n in
        [('hyd-dmn','inputs'),('hyd-dmn','timeseries_query'),('enterprise','query'),
         ('hyd-dmn','evaluate_cards'),('enterprise','PR_CREATE')]]
    rows += [dict(server='hyd-dmn',name=n,description=n,inputSchema={'type':'object'},kind='proposal')
             for n in ('submit_decision','submit_purchase')]
    filtered=agents.filter_tools(runtime,inst,rows)
    expected={'hyd-dmn/inputs','hyd-dmn/timeseries_query','enterprise/query'}
    assert {t['server']+'/'+t['name'] for t in filtered}==expected
    for t in rows:
        name=t['server']+'/'+t['name']
        if name in expected:agents.verify_tool(runtime,inst,name)
        else:
            with pytest.raises(Denied):agents.verify_tool(runtime,inst,name)
    monkeypatch.setattr(managed_model,'attach',lambda *a:MANAGED)
    # A stale/wider server catalog must also be narrowed before tools/list.
    monkeypatch.setattr(managed_tools.Transport,'request',lambda *a,**kw:{'tools':rows})
    requests=[]
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=_fake_exec(json.dumps(unknown_draft()),requests=requests),
                  schema_prompt='# schema',resolve_provider=lambda _:object())
    assert runner.poll_once()==1
    request=requests[0][0]
    from pathlib import Path
    stored=json.loads((Path(request.workdir)/'managed-tool-catalog.json').read_text(encoding='utf8'))
    allowed=request.extra_args[request.extra_args.index('--allowedTools')+1].split(',')
    assert {x for x in allowed if x.startswith('mcp__')}=={'mcp__'+x.replace('/','__') for x in expected}
    assert {t['server']+'/'+t['name'] for t in stored}==expected
    assert not any('*' in x for x in allowed)


def test_handover_does_not_authorize_reads_absent_from_managed_catalog():
    allowed=handover_allowed_tools(DEFAULT_ALLOWED_TOOLS.split(','),['hyd-dmn'],{'hyd-dmn':['inputs']})
    assert [x for x in allowed if x.startswith('mcp__')]==['mcp__hyd-dmn__inputs']
