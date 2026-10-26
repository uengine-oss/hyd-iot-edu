"""Delegate a student task without executing a local model or teacher-side tools."""
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor,TimeoutError as FutureTimeout
import json
import os
import time

from fastapi.encoders import jsonable_encoder
from procsvc import classroom_agents,handover,manual_extraction
from procsvc.agents_store import agent_settings,activity_capabilities
from procsvc.classroom_read_tools import TaskRouter
from procsvc.instances import InstanceRuntime
from . import outcome


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
    run=wait(client.start_agent,task,binding['reference'],inputs,approval['revision'])
    runner._event(row,job_id,'task_started',{'name':'승인된 관리 에이전트 실행','managed_run':run},crew_type='agent')
    deadline=min(deadline,time.monotonic()+binding['max_seconds'])
    try:
        while True:
            check()
            router.claim()
            value=wait(client.agent_result,task,run)
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
        try:client.cancel_agent(task,run)
        except Exception:
            runner._event(row,job_id,'task_working',{'type':'notice','content':'관리 실행 중단 응답을 확인하지 못했습니다. 서버 시간·예산 한도는 유지됩니다.'},crew_type='agent')
        raise
