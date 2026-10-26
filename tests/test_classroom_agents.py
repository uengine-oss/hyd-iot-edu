from copy import deepcopy
from uuid import uuid4

import pytest

from procsvc import classroom_agents as agents, engine
from procsvc.classroom_authority import Denied
from test_instances import rt  # noqa: F401


def approved(runtime):
    source=dict(processDefinitionId='approved_lesson',processDefinitionName='승인 수업',version='1',
        roles=[{'name':'AI','endpoint':'agent:class-test'}],data=[{'name':'memo','type':'String'},{'name':'answer','type':'String'}],
        forms={'answer':{'fields_json':[{'key':'answer','type':'textarea','required':True}]}},
        activities=[dict(id='draft',type='userTask',name='인계 초안',role='AI',agentMode='COMPLETE',orchestration='cliagents',
            tool='formHandler:answer',inputData=['memo'],outputData=['answer'],instruction='승인 자료만 대조한다'),
            dict(id='later',type='userTask',name='뒤 단계',role='AI',agentMode='COMPLETE',orchestration='cliagents',
            tool='formHandler:answer',inputData=['answer'],outputData=['answer'],instruction='이 단계는 관리 실행하지 않는다')],
        gateways=[],events=[{'id':'s','type':'startEvent'},{'id':'e','type':'endEvent'}],
        sequences=[{'id':'s1','source':'s','target':'draft'},{'id':'s2','source':'draft','target':'later'},
                   {'id':'s3','source':'later','target':'e'}])
    runtime.repo.upsert_user({'id':'agent:class-test','tenant_id':runtime.tenant_id,'username':'수업 에이전트',
                              'is_agent':True,'agent_type':'agent','goal':'교대 메모와 실제 상태를 대조','tools':'enterprise'})
    runtime.register_definition(source)
    approval=dict(definition='approved_lesson',version='1',activity='draft',revision='pending',
                  input_schema={'type':'object','properties':{'memo':{'type':'string','maxLength':100}},
                                'required':['memo'],'additionalProperties':False})
    approval['revision']=agents.revision(runtime,approval)
    return approval


def test_only_approved_activity_runs_and_duplicate_server_run_joins(rt):
    runtime,_=rt;approval=approved(runtime);run=str(uuid4())
    inst=agents.start(runtime,approval,{'memo':'실제 상태 확인 필요'},run,'handover.draft')
    assert agents.start(runtime,approval,{'memo':'실제 상태 확인 필요'},run,'handover.draft')['proc_inst_id']==inst['proc_inst_id']
    with pytest.raises(Denied):agents.start(runtime,approval,{'memo':'다른 입력'},run,'handover.draft')
    definition=runtime.definition_for(inst)
    assert list(definition.activities)==['draft']
    assert engine.variables(inst)['classroom_execution']=={'run_id':run}
    assert agents.verify_instance(runtime,inst)==approval
    agents.verify_tool(runtime,inst,'enterprise/spare_stock')
    with pytest.raises(Denied):agents.verify_tool(runtime,inst,'hyd-dmn/evaluate_cards')
    wi=runtime.repo.fetch_pending_task('cliagents','test-worker')[0]
    runtime.repo.save_task_result(wi['id'],{'answer':'확인 필요'},final=True)
    runtime.poll_once()
    assert runtime.repo.get_instance(inst['proc_inst_id'])['status']=='COMPLETED'
    assert len(runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id']))==1


def test_profile_change_revokes_pinned_execution(rt):
    runtime,_=rt;approval=approved(runtime)
    inst=agents.start(runtime,approval,{'memo':'확인 필요'},str(uuid4()),'handover.draft')
    user=runtime.repo.list_users(['agent:class-test'],runtime.tenant_id)[0]
    runtime.repo.upsert_user(dict(user,goal='허용되지 않은 다른 작업'))
    with pytest.raises(Denied,match='판본'):agents.verify_instance(runtime,inst)
    with pytest.raises(Denied):agents.start(runtime,approval,{'memo':'확인 필요'},str(uuid4()),'handover.draft')


def test_skill_body_change_also_revokes_approval(rt):
    runtime,_=rt;approval=approved(runtime)
    runtime.repo.put_skill({'tenant_id':runtime.tenant_id,'skill_name':'handover-check','content':'원문과 실제 상태를 비교한다'})
    runtime.repo.attach_skill('agent:class-test','handover-check',runtime.tenant_id)
    approval['revision']=agents.revision(runtime,approval)
    agents.checked(runtime,approval)
    runtime.repo.put_skill({'tenant_id':runtime.tenant_id,'skill_name':'handover-check','content':'다른 지시로 바뀜'})
    with pytest.raises(Denied):agents.checked(runtime,approval)


@pytest.mark.parametrize('values',[{'memo':'x','prompt':'arbitrary'}, {'memo':'x'*101},
                                   {'memo':7}, {'classroom_execution':{'run_id':str(uuid4())}}, {'memo':'한'*3000}])
def test_unapproved_input_cannot_create_a_task(rt,values):
    runtime,_=rt;approval=approved(runtime)
    with pytest.raises(Denied):agents.start(runtime,approval,values,str(uuid4()),'handover.draft')
    assert not runtime.repo.instances


def test_missing_or_wrong_source_revision_is_denied(rt):
    runtime,_=rt;approval=approved(runtime)
    with pytest.raises(Denied):agents.checked(runtime,dict(approval,revision='0'*64))
    with pytest.raises(Denied):agents.checked(runtime,dict(approval,version='missing'))
    invalid=deepcopy(approval);invalid['input_schema']['additionalProperties']=True
    with pytest.raises(Denied):agents.revision(runtime,invalid)
