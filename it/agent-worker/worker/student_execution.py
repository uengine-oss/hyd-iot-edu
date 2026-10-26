"""Delegate a student task without executing a local model or teacher-side tools."""
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor,TimeoutError as FutureTimeout
import json
import os
import time

from fastapi.encoders import jsonable_encoder
from procsvc import classroom_agents,handover,manual_extraction
from procsvc import task_deferral
from procsvc.classroom_authority import digest
from procsvc.agents_store import agent_settings,activity_capabilities
from procsvc.classroom_read_tools import TaskRouter
from procsvc.instances import InstanceRuntime
from . import outcome,workspace


class LocalRuntime:
    # Reuse read-only version/snapshot resolution; constructing InstanceRuntime
    # would deploy a definition as a side effect of worker startup.
    definition_for=InstanceRuntime.definition_for
    definition_for_workitem=InstanceRuntime.definition_for_workitem
    workitem_view=InstanceRuntime.workitem_view

    def __init__(self,repo,tenant):
        self.repo,self.tenant_id=repo,tenant


def configured(settings):
    from procsvc.classroom_client import Client
    url=os.getenv('HYD_CLASSROOM_URL')
    if not url:return None
    return Client(url,lambda:os.getenv('LLM_API_KEY',''),settings.workspace_root/'classroom.sqlite3')


def execute(runner,row,ctx,job_id,client,*,sleep=time.sleep):
    from .runner import Cancelled,LeaseLost,RunFailed
    runtime=LocalRuntime(runner.repo,runner.s.tenant_id)
    deadline=time.monotonic()+runner.s.run_timeout_s
    renewed=0.0
    def check():
        nonlocal renewed
        if runner._reclaimed(row):raise LeaseLost()
        if runner._cancelled(row):raise Cancelled()
        if time.monotonic()>deadline:raise RunFailed('관리 에이전트 실행 제한 시간을 초과했습니다')
        if time.monotonic()-renewed>=min(15,runner.s.lease_renew_every_s):
            if not runner.repo.renew_task_lease(row['id'],row['consumer']):raise LeaseLost()
            renewed=time.monotonic()
    def wait(fn,*args):
        # Network/MCP waits must not starve lease renewal or cancellation.
        pool=ThreadPoolExecutor(max_workers=1)
        try:
            check()
            future=pool.submit(fn,*args)
            while True:
                check()
                try:return future.result(timeout=0.25)
                except FutureTimeout:
                    if future.done():raise
        finally:pool.shutdown(wait=False,cancel_futures=True)
    binding=wait(client.agent_contract,row['proc_def_id'],row['version'],row['activity_id'])
    approval=binding['approval']
    if (approval['definition'],approval['version'],approval['activity'])!=(row['proc_def_id'],row['version'],row['activity_id']):
        raise RunFailed('관리 서버의 승인 작업이 현재 학생 작업과 다릅니다')
    classroom_agents.checked(runtime,approval)
    bundle=classroom_agents.snapshot(runtime,approval)[3]
    actual=agent_settings(runner.repo,runner.s.tenant_id,ctx.profile,
                          activity=activity_capabilities(ctx.definition,row['activity_id']))
    if jsonable_encoder(asdict(actual))!=bundle['agent']:
        raise RunFailed('현재 배정된 학생 에이전트가 강사 승인 판본과 다릅니다')
    inputs=runtime.workitem_view(row['id'])['inputs']
    inputs={key:inputs[key] for key in approval['input_schema']['properties'] if key in inputs}
    classroom_agents.validate_input(approval,inputs)
    tools=[item['server']+'/'+item['name'] for item in binding['tools']]
    router=TaskRouter(runtime,row['id'],row['consumer'],tools)
    router.claim()
    task=runner.s.tenant_id+':'+row['id']
    try:
        run=wait(client.start_agent,task,binding['reference'],inputs,approval['revision'])
    except LeaseLost:
        raise
    except Exception as exc:
        from fastapi import HTTPException
        if runner._reclaimed(row):raise LeaseLost() from None
        if isinstance(exc,HTTPException) and exc.status_code!=502:raise
        try:
            cancelled=client.cancel_start(task,binding['reference'],inputs,approval['revision'])
            if cancelled.get('state')!='CONFIRMED':
                runner._event(row,job_id,'task_working',{'type':'notice','content':'시작 요청의 취소를 보관했습니다. 관리 서버 확인은 제한된 재전송으로 이어갑니다.'},crew_type='agent')
        except Exception:
            runner._event(row,job_id,'task_working',{'type':'notice','content':'시작 요청의 취소 보관에 실패했습니다. 강사 실행 상태 확인이 필요합니다.'},crew_type='agent')
        raise
    runner._event(row,job_id,'task_started',{'name':'승인된 관리 에이전트 실행','managed_run':run},crew_type='agent')
    deadline=min(deadline,time.monotonic()+binding['max_seconds'])
    try:
        feedback=row.get('feedback') or {}
        request_id=feedback.get('job_id') if ctx.human_answer else (feedback.get('reassessment') or {}).get('deferral_id')
        if request_id:
            mappings=[e['data'] for e in runner.repo.list_events(todo_id=row['id'],limit=None)
                      if e['job_id']=='CLASSROOM_CONTROL' and e['data'].get('local_request_id')==request_id]
            if len(mappings)!=1 or mappings[0]['run_id']!=run:
                raise RunFailed('학생 보완 답변과 원격 질문의 연결을 확인할 수 없습니다')
            link=mappings[0]
            text=ctx.human_answer or feedback['reassessment']['reason']
            wait(client.respond_agent,task,run,link['kind'],link['request_id'],text)
        while True:
            check()
            router.claim()
            value=wait(client.agent_result,task,run)
            if value['status'] in ('NEEDS_INPUT','DEFERRED'):
                with runner.repo.instance_transaction(runtime.tenant_id,row['proc_inst_id']):
                    router.claim()
                    if value['status']=='NEEDS_INPUT':
                        runner._pause(row,workspace.for_run(runner.s.workspace_root,row['id'],tenant_id=runtime.tenant_id),
                                      'managed-classroom','',value['question'],job_id,options=value.get('options') or [])
                        local_id=runner.repo.get_workitem(row['id'])['draft']['_human_request']['job_id']
                        kind='human_answer'
                    else:
                        local_id='managed:'+digest([run,value['request_id']])
                        task_deferral.defer(runner.repo,runtime.tenant_id,row['id'],expected_consumer=row['consumer'],
                            request_id=local_id,assessment=value['assessment'])
                        kind='reassessment'
                    runner.repo.record_events([{'job_id':'CLASSROOM_CONTROL','todo_id':row['id'],
                        'proc_inst_id':row['proc_inst_id'],'crew_type':'agent','event_type':'classroom_control',
                        'data':{'run_id':run,'request_id':value['request_id'],'local_request_id':local_id,'kind':kind}}])
                return
            if value['status']=='DONE':
                result=outcome.interpret(json.dumps(value['output'],ensure_ascii=False),ctx.form_fields,versioned=True)
                if not result.contract_met:raise RunFailed(result.mismatch_reason)
                form={'fields_json':ctx.form_fields,'contract':ctx.form_contract}
                current,inst=router.claim()
                current_inputs=runtime.workitem_view(row['id'])['inputs']
                current_inputs={key:current_inputs[key] for key in approval['input_schema']['properties'] if key in current_inputs}
                if current_inputs!=inputs or current.get('user_id')!=row.get('user_id'):
                    raise RunFailed('관리 실행 중 학생 작업 입력·배정이 바뀌었습니다. 현재 조건으로 다시 검토하세요')
                manual_extraction.validate_result(form,inst,result.payload)
                handover.validate_trace(runner.repo,row,form,result.payload)
                classroom_agents.checked(runtime,approval)
                if not runner.repo.save_task_result(row['id'],result.payload,final=True,expected_consumer=row['consumer']):
                    raise LeaseLost()
                runner._event(row,job_id,'task_completed',{'managed_run':run,'output_keys':sorted(result.outputs),
                              'requires_local_review':True},crew_type='result')
                return
            if value['status']!='PENDING':raise RunFailed('관리 에이전트가 성공 결과를 만들지 못했습니다')
            wait(client.exchange_tool,run,router)
            sleep(0.5)
    except LeaseLost:
        # A new local claimant may resume the same remote run. Never cancel it
        # merely because this worker lost ownership.
        raise
    except Exception:
        try:
            cancelled=client.cancel_agent(task,run)
            if cancelled and cancelled.get('state') in ('PENDING','REVIEW_REQUIRED'):
                runner._event(row,job_id,'task_working',{'type':'notice','content':'관리 실행 취소를 보관했습니다. 확인 전에는 완료로 처리하지 않습니다.'},crew_type='agent')
        except Exception:
            runner._event(row,job_id,'task_working',{'type':'notice','content':'관리 실행 중단 응답을 확인하지 못했습니다. 서버 시간·예산 한도는 유지됩니다.'},crew_type='agent')
        raise
