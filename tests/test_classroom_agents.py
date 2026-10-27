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


def test_managed_diagnosis_cannot_write_instructor_incident_card(rt):
    runtime,hooks=rt;approval=approved(runtime)
    source=deepcopy(runtime.repo.get_proc_def(approval['definition'],runtime.tenant_id,version='1')['definition'])
    source['version']='2'
    source['data'] += [{'name':'incident','type':'String'},{'name':'guide_card','type':'Object'}]
    source['forms']['answer']['fields_json'].append({'key':'guide_card','type':'object'})
    source['activities'][0]['inputData'].append('incident')
    source['activities'][0]['outputData'].append('guide_card')
    source['activities'][1]['outputData'].append('guide_card')
    runtime.register_definition(source)
    approval['version']='2'
    approval['input_schema']['properties']['incident']={'type':'string'}
    approval['revision']=agents.revision(runtime,approval)
    inst=agents.start(runtime,approval,{'memo':'확인','incident':'student-incident'},str(uuid4()),'diagnosis')
    row=runtime.repo.fetch_pending_task('cliagents','managed-test')[0]
    runtime.repo.save_task_result(row['id'],{'answer':'제안','guide_card':{'recommended':[]}},final=True)
    runtime.poll_once()
    assert runtime.repo.get_instance(inst['proc_inst_id'])['status']=='COMPLETED'
    assert not hooks.cards and not hooks.calls


def test_internal_input_exception_cannot_authorize_a_normal_definition(rt):
    runtime,_=rt;approval=approved(runtime)
    with pytest.raises(ValueError):
        runtime.start_definition(approval['definition'],'1','ordinary',values={'memo':'x','incident':'student'},
                                 _classroom_approval=approval)
    with pytest.raises(ValueError):
        runtime.start_definition(approval['definition'],'1','ordinary',values={'memo':'x','incident':'student'})


def test_managed_marker_cannot_hide_changed_execution_definition(rt):
    from types import SimpleNamespace
    runtime,_=rt;approval=approved(runtime)
    definition=agents.isolated_definition(runtime,approval)
    definition['activities'][0]['instruction']='different instructions'
    wrapped=SimpleNamespace(repo=runtime.repo,tenant_id=runtime.tenant_id,
                            definition_for=lambda _:SimpleNamespace(raw=definition))
    with pytest.raises(Denied):agents.verify_instance(wrapped,{})


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


def test_portal_assignment_is_pinned_and_runs_the_selected_agent(rt):
    runtime,_=rt;approval=approved(runtime)
    original=deepcopy(runtime.repo.get_proc_def(approval['definition'],runtime.tenant_id,version='1'))
    runtime.repo.upsert_user({'id':'agent:selected','tenant_id':runtime.tenant_id,'username':'학생 작성',
                              'is_agent':True,'agent_type':'agent','goal':'학생이 작성한 지시','tools':'enterprise'})
    mapping=dict(tenant_id=runtime.tenant_id,proc_def_id=approval['definition'],activity_id='draft',
                 agent_id='agent:selected')
    runtime.repo.put_agent_map(mapping)
    with pytest.raises(Denied,match='판본'):agents.checked(runtime,approval)
    approval['revision']=agents.revision(runtime,approval)
    inst=agents.start(runtime,approval,{'memo':'확인 필요'},str(uuid4()),'handover.draft')
    row=runtime.repo.fetch_pending_task('cliagents','test-worker')[0]
    assert row['user_id']=='agent:selected'
    assert runtime.definition_for(inst).raw['roles'][0]['endpoint']=='agent:selected'
    assert runtime.repo.get_proc_def(approval['definition'],runtime.tenant_id,version='1')==original
    runtime.repo.put_agent_map(dict(mapping,by_user='another-editor',updated_at='metadata-only'))
    agents.verify_instance(runtime,inst)
    runtime.repo.drop_agent_map(runtime.tenant_id,approval['definition'],'draft')
    with pytest.raises(Denied,match='판본'):agents.verify_instance(runtime,inst)


@pytest.mark.parametrize('endpoint',[None,'missing-agent','human'])
def test_invalid_portal_assignment_cannot_fall_back_to_definition(rt,endpoint):
    runtime,_=rt;approval=approved(runtime)
    runtime.repo.upsert_user({'id':'human','tenant_id':runtime.tenant_id,'username':'사람','is_agent':False})
    runtime.repo.put_agent_map(dict(tenant_id=runtime.tenant_id,proc_def_id=approval['definition'],
                                    activity_id='draft',agent_id=endpoint))
    with pytest.raises(Denied):agents.revision(runtime,approval)


@pytest.mark.parametrize('mapped',[False,True])
def test_activity_agent_and_portal_map_use_engine_precedence(rt,mapped):
    runtime,_=rt;approval=approved(runtime)
    for agent in ('agent:authored','agent:mapped'):
        runtime.repo.upsert_user(dict(id=agent,tenant_id=runtime.tenant_id,username=agent,is_agent=True,
                                     goal='instructions for '+agent,tools='enterprise'))
    source=deepcopy(runtime.repo.get_proc_def(approval['definition'],runtime.tenant_id,version='1')['definition'])
    source['version']='2';source['activities'][0]['agent']='agent:authored'
    runtime.register_definition(source);approval['version']='2'
    if mapped:
        runtime.repo.put_agent_map(dict(tenant_id=runtime.tenant_id,proc_def_id=approval['definition'],
                                       activity_id='draft',agent_id='agent:mapped'))
    selected='agent:mapped' if mapped else 'agent:authored'
    approval['revision']=agents.revision(runtime,approval)
    assert agents.snapshot(runtime,approval)[3]['agent']['agent_id']==selected
    inst=agents.start(runtime,approval,{'memo':'확인'},str(uuid4()),'lesson')
    assert runtime.repo.fetch_pending_task('cliagents','worker')[0]['user_id']==selected
    agents.verify_instance(runtime,inst)
    assert runtime.repo.get_proc_def(approval['definition'],runtime.tenant_id,version='2')['definition']==source


def test_database_metadata_does_not_change_execution_approval(rt):
    runtime,_=rt;approval=approved(runtime)
    runtime.repo.put_skill({'tenant_id':runtime.tenant_id,'skill_name':'handover-check','content':'원문 확인'})
    runtime.repo.attach_skill('agent:class-test','handover-check',runtime.tenant_id)
    approval['revision']=agents.revision(runtime,approval)
    profile=runtime.repo.list_users(['agent:class-test'],runtime.tenant_id)[0]
    runtime.repo.upsert_user(dict(profile,updated_at='different-machine',email='unrelated@example.invalid',avatar='new'))
    runtime.repo.put_skill({'tenant_id':runtime.tenant_id,'skill_name':'handover-check','content':'원문 확인',
                            'id':'different-row-id','created_at':'new','owner_id':'different-owner'})
    agents.checked(runtime,approval)


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


def test_handover_approval_accepts_first_draft_null_notes_without_dropping_reviews(rt):
    from test_handover import begin
    runtime,_=rt;inst=begin(runtime)
    source=runtime.definition_for(inst).raw
    props={name:{'type':'string'} for name in source['activities'][0]['inputData']}
    for name in ('sender_notes','receiver_notes'):props[name]={'type':['string','null'],'maxLength':2000}
    approval=dict(definition=source['processDefinitionId'],version=source['version'],activity='task:draft',revision='pending',
        input_schema={'type':'object','properties':props,'required':['asset','shift_label','as_of','work_notes'],'additionalProperties':False})
    approval['revision']=agents.revision(runtime,approval)
    row=next(w for w in runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='task:draft')
    inputs=runtime.workitem_view(row['id'])['inputs']
    assert inputs['sender_notes'] is None and inputs['receiver_notes'] is None
    agents.validate_input(approval,inputs)
    agents.validate_input(approval,dict(inputs,sender_notes='작업지시를 다시 확인하세요'))
    # Exercise the actual engine start, not only the input-schema helper.
    for notes in (None,'작업지시를 다시 확인하세요'):
        managed_inputs=dict(inputs,sender_notes=notes)
        started=agents.start(runtime,approval,managed_inputs,str(uuid4()),'handover.draft')
        managed_row=runtime.repo.list_workitems(proc_inst_id=started['proc_inst_id'])[0]
        assert runtime.workitem_view(managed_row['id'])['inputs']['sender_notes']==notes
        assert agents.verify_instance(runtime,started)==approval
    with pytest.raises(ValueError,match='시간대'):
        agents.start(runtime,approval,dict(inputs,as_of='2026-10-27T18:00:00'),str(uuid4()),'handover.draft')
    with pytest.raises(Denied):
        agents.start(runtime,approval,dict(inputs,sender_decision='approve'),str(uuid4()),'handover.draft')
    with pytest.raises(ValueError,match='시작에는'):
        runtime.start_definition(source['processDefinitionId'],source['version'],str(uuid4()),values=inputs)
    bad=deepcopy(approval);bad['input_schema']['properties']['sender_notes']['type']='string'
    with pytest.raises(Denied,match='검토 전 null'):agents.revision(runtime,bad)
    del bad['input_schema']['properties']['sender_notes']
    with pytest.raises(Denied,match='검토 전 null'):agents.revision(runtime,bad)
