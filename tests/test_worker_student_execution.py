from copy import deepcopy
from dataclasses import replace
import time
from uuid import uuid4

import pytest
from worker import student_execution,context
from worker.runner import Runner,RunFailed,Cancelled,LeaseLost
from procsvc import mcp_check,mcp_registry,mcp_secrets,ask
from test_classroom_agents import approved
from test_instances import rt
from test_worker import _settings


@pytest.fixture
def local(rt,tmp_path,monkeypatch):
    runtime,hooks=rt;approval=approved(runtime)
    inst=runtime.start_definition(approval['definition'],'1','student-task',values={'memo':'실제 상태 확인'})
    monkeypatch.setattr(mcp_registry,'store_for',lambda _:type('Store',(),{'servers':lambda _,tenant:{
        'enterprise':{'url':'http://student-enterprise/mcp','type':'streamable_http'}}})())
    monkeypatch.setattr(mcp_secrets,'runtime_spec',lambda *a:(a[-1],[]))
    monkeypatch.setattr(mcp_check,'call',lambda *a,**kw:{'status':'ok','result':{
        'text':'{"available":7}','json':True,'is_error':False}})
    class Client:
        def __init__(self):self.starts=[];self.cancelled=[];self.results=0;self.reads=[];self.run=str(uuid4());self.responses=[]
        def agent_contract(self,*args):
            return {'approval':deepcopy(approval),'reference':'lesson.draft','max_seconds':60,
                    'tools':[{'server':'enterprise','name':'spare_stock'}]}
        def start_agent(self,*args):self.starts.append(args);return self.run
        def respond_agent(self,*args):self.responses.append(args);return {'status':'QUEUED'}
        def agent_result(self,*args):
            self.results+=1
            return {'status':'PENDING'} if self.results==1 else {'status':'DONE','output':{'answer':'확인 필요'}}
        def exchange_tool(self,run,router):
            self.reads.append(router('enterprise/spare_stock',{'part':'SEAL'}))
            return {'status':'DONE'}
        def cancel_agent(self,*args):self.cancelled.append(args)
        def flush_cancellations(self):return {'state':'IDLE'}
        def reconcile_cancellations(self,*a):return {'state':'IDLE'}
        def cancel_start(self,*args):self.cancelled.append(args);return {'state':'CONFIRMED'}
    client=Client()
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=lambda *a:pytest.fail('local model must not run'),schema_prompt='s')
    return runtime,hooks,inst,approval,client,runner


def claim(local):
    runtime,*_=local
    row=runtime.repo.fetch_pending_task('cliagents','student-worker')[0]
    return row,context.prepare(runtime.repo,row,runtime.tenant_id)


def test_managed_student_worker_submits_locally_and_preserves_actual_trace(local,monkeypatch):
    runtime,hooks,inst,approval,client,runner=local
    monkeypatch.setattr(student_execution,'configured',lambda _:client)
    assert runner.poll_once()==1
    row=runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    assert row['status']=='SUBMITTED' and row['output']['answer']=='확인 필요'
    assert client.starts[0][2]=={'memo':'실제 상태 확인'} and client.starts[0][3]==approval['revision']
    assert client.reads==[{'result':{'available':7},'is_error':False}]
    calls=ask.tool_calls(runtime.repo.list_events(todo_id=row['id']))
    assert len(calls)==1 and '7' in str(calls[0])
    assert not hooks.calls and not client.cancelled


def test_changed_student_profile_is_rejected_before_paid_start(local):
    runtime,_,_,_,client,runner=local
    user=runtime.repo.list_users(['agent:class-test'],runtime.tenant_id)[0]
    runtime.repo.upsert_user(dict(user,goal='different'))
    row,ctx=claim(local)
    with pytest.raises(Exception):student_execution.execute(runner,row,ctx,'test',client,sleep=lambda _:None)
    assert not client.starts


@pytest.mark.parametrize('status',['FAILED','broken-output','cancel','reclaimed','changed-input'])
def test_failure_cancel_and_reclaim_never_submit_success(local,status):
    runtime,_,_,_,client,runner=local;row,ctx=claim(local)
    def result(*args):
        if status=='changed-input':
            inst=runtime.repo.get_instance(row['proc_inst_id'])
            next(v for v in inst['variables_data'] if v['key']=='memo')['value']='다른 입력'
            runtime.repo.update_instance(inst)
            return {'status':'DONE','output':{'answer':'과거 입력의 답'}}
        if status in ('cancel','reclaimed'):
            fresh=runtime.repo.get_workitem(row['id'])
            if status=='cancel':fresh['draft_status']='CANCELLED'
            else:fresh['consumer']='another-worker'
            runtime.repo.update_workitem(fresh)
            return {'status':'PENDING'}
        return {'status':'DONE','output':{'answer':None}} if status=='broken-output' else {'status':'FAILED'}
    client.agent_result=result
    with pytest.raises(Exception):student_execution.execute(runner,row,ctx,'test',client,sleep=lambda _:None)
    assert runtime.repo.get_workitem(row['id'])['status']=='IN_PROGRESS'
    assert bool(client.cancelled)==(status!='reclaimed')


def test_lease_is_renewed_during_slow_network(local):
    runtime,_,_,_,client,runner=local;row,ctx=claim(local)
    runner.s=replace(runner.s,lease_renew_every_s=0.01)
    original=runtime.repo.renew_task_lease;renewals=[]
    def renew(*a):renewals.append(time.monotonic());return original(*a)
    runtime.repo.renew_task_lease=renew
    def result(*args):time.sleep(0.6);return {'status':'DONE','output':{'answer':'확인 필요'}}
    client.agent_result=result
    student_execution.execute(runner,row,ctx,'test',client,sleep=lambda _:None)
    assert len(renewals)>=3


def test_deadline_stops_waiting_and_requests_remote_cancel(local):
    _,_,_,_,client,runner=local;row,ctx=claim(local)
    runner.s=replace(runner.s,run_timeout_s=0.1)
    def result(*args):time.sleep(0.4);return {'status':'PENDING'}
    client.agent_result=result
    with pytest.raises(RunFailed):student_execution.execute(runner,row,ctx,'test',client,sleep=lambda _:None)
    assert len(client.starts)==1 and len(client.cancelled)==1


@pytest.mark.parametrize('kind',['human_answer','reassessment'])
def test_question_or_deferral_returns_to_student_and_resumes_same_run(local,monkeypatch,kind):
    from procsvc import task_deferral
    runtime,_,inst,_,client,runner=local
    monkeypatch.setattr(student_execution,'configured',lambda _:client)
    def result(*args):
        if client.responses:return {'status':'DONE','output':{'answer':'보완 확인'}}
        if kind=='human_answer':return {'status':'NEEDS_INPUT','request_id':'teacher-question','question':'실재고를 확인했나요?'}
        return {'status':'DEFERRED','request_id':'teacher-deferral','assessment':{
            'status':'UNKNOWN','reason':'실재고 확인 필요','evidence':{}}}
    client.agent_result=result
    assert runner.poll_once()==1
    row=runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    assert not row.get('output') and not client.cancelled
    if kind=='human_answer':
        assert row['draft_status']=='HUMAN_ASKED'
        runtime.human_response(row['id'],row['draft']['_human_request']['job_id'],'실재고 확인','student')
    else:
        assert row['status']=='PENDING'
        task_deferral.reassess(runtime.repo,runtime.tenant_id,row['id'],deferral_id=row['draft']['_deferral']['id'],
            request_id='local-recheck',by='student',reason='실재고 확인')
    assert runner.poll_once()==1
    assert runtime.repo.get_workitem(row['id'])['status']=='SUBMITTED'
    assert client.responses==[(runtime.tenant_id+':'+row['id'],client.run,kind,
                              'teacher-question' if kind=='human_answer' else 'teacher-deferral','실재고 확인')]
    assert not client.cancelled


@pytest.mark.parametrize('failure',['network','other-task','reclaimed'])
def test_start_uncertainty_cancels_only_the_owned_attempt(local,failure):
    from fastapi import HTTPException
    runtime,_,_,_,client,runner=local;row,ctx=claim(local)
    def start(*args):
        if failure=='reclaimed':
            fresh=runtime.repo.get_workitem(row['id']);fresh['consumer']='new-worker'
            runtime.repo.update_workitem(fresh)
        raise HTTPException(409 if failure=='other-task' else 502,'start not confirmed')
    client.start_agent=start
    with pytest.raises(Exception):student_execution.execute(runner,row,ctx,'test',client)
    assert bool(client.cancelled)==(failure=='network')
