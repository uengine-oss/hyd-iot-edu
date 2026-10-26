import json
import time
from types import SimpleNamespace

import pytest

from procsvc import classroom_proposals,engine,mcp_registry,mcp_secrets,procdb
from procsvc.classroom_read_tools import TaskRouter
from test_decision_scope import fixture


@pytest.fixture
def task(monkeypatch):
    definition,inst,row,scope,_=fixture()
    inst['variables_data'].append({'key':'pattern','value':'COOLER_DEGRADATION'})
    row['lease_until']=time.time()+60
    repo=procdb.MemoryRepo()
    repo.instances[inst['proc_inst_id']]=inst
    repo.workitems[row['id']]=row
    runtime=SimpleNamespace(repo=repo,tenant_id=inst['tenant_id'],definition_for=lambda _:definition)
    entry={'url':'http://student-dmn/mcp','type':'streamable_http'}
    monkeypatch.setattr(mcp_registry,'store_for',lambda _:SimpleNamespace(servers=lambda _: {'hyd-dmn':entry}))
    monkeypatch.setattr(mcp_secrets,'runtime_spec',lambda *args:(args[-1],[]))
    calls=[]
    def submit(spec,tool,args):
        calls.append((spec,tool,args))
        return {'status':'ok','result':{'text':'{"id":"DEC-local"}','json':True,'is_error':False}}
    monkeypatch.setattr(classroom_proposals,'call',submit)
    router=TaskRouter(runtime,row['id'],row['consumer'],classroom_proposals.TOOLS)
    args={'asset':'HYD-01','incident':'INC-fixture','pattern':'COOLER_DEGRADATION',
          'process_scope':{'instance':'teacher-instance'}}
    return router,args,calls,repo,inst,row


def test_local_scope_and_duplicate_receipt(task):
    router,args,calls,repo,inst,row=task
    first=router('hyd-dmn/submit_decision',args)
    assert first=={'is_error':False,'result':{'id':'DEC-local'}}
    assert router('hyd-dmn/submit_decision',args)==first and len(calls)==1
    scope=calls[0][2]['process_scope']
    assert scope['instance']==inst['proc_inst_id'] and scope['workitem']==row['id']
    assert json.loads(calls[0][0]['headers']['X-HYD-Process-Scope'])==scope
    events=repo.list_events(todo_id=row['id'])
    assert len(events)==2 and events[0]['data']['tool']=='mcp__hyd-dmn__submit_decision'
    assert events[0]['data']['tool_use_id']==events[1]['data']['tool_use_id']


@pytest.mark.parametrize('change',['asset','incident','pattern','expired','owner','wrong_activity','generation'])
def test_local_authority_and_event_binding_cannot_be_bypassed(task,change):
    router,args,calls,repo,inst,row=task
    if change in args:args[change]='other'
    if change=='expired':row['lease_until']=time.time()-1
    if change=='owner':row['consumer']='other-worker'
    if change=='wrong_activity':row['activity_id']='task:diagnose'
    if change=='generation':inst['rework_generation']=2
    assert router('hyd-dmn/submit_decision',args)['is_error']
    assert not calls and not repo.events


def test_unknown_registration_never_retries(task,monkeypatch):
    router,args,calls,repo,_,_=task
    def interrupted(*a):
        calls.append(a)
        raise TimeoutError('response lost after registration')
    monkeypatch.setattr(classroom_proposals,'call',interrupted)
    assert router('hyd-dmn/submit_decision',args)['is_error']
    assert router('hyd-dmn/submit_decision',args)['is_error'] and len(calls)==1
    assert repo.events[-1]['data']['outcome_unknown']


def test_changed_proposal_cannot_register_again(task):
    router,args,calls,*_=task
    assert not router('hyd-dmn/submit_decision',args)['is_error']
    assert router('hyd-dmn/submit_decision',dict(args,cause='different'))['is_error']
    assert len(calls)==1


def test_purchase_must_match_current_part(task):
    router,args,calls,repo,inst,row=task
    inst['variables_data'].append({'key':'alert','value':{'evidence':{'part_no':'SEAL'}}})
    args.pop('pattern')
    assert router('hyd-dmn/submit_purchase',dict(args,part_no='OTHER'))['is_error']
    assert not calls
    assert not router('hyd-dmn/submit_purchase',dict(args,part_no='SEAL'))['is_error']


def test_adapter_has_no_generic_write_entry():
    with pytest.raises(ValueError):classroom_proposals.call({},'enterprise/PR_CREATE',{})
