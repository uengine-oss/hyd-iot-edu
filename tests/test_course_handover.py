from copy import deepcopy
import json
from pathlib import Path

import pytest
from hydcommon import course_access as rules, course_handover as flow
from test_course_access import instructor, setup
from test_bpmn_import import api


def test_shipped_handover_contract_matches_its_source():
    root=Path(__file__).parents[1]/'it/process/definitions'
    assert flow.CONTENT['xml']==(root/'shift_handover.bpmn').read_text(encoding='utf8')
    assert flow.CONTENT['mapping']==json.loads((root/'shift_handover.mapping.json').read_text(encoding='utf8'))


def test_only_shipped_topology_and_mapping_are_editable(tmp_path,instructor):
    _,client,_,sign,_=setup(tmp_path,instructor)
    imported={'definition_id':'ShiftHandover','xml':flow.CONTENT['xml'],'file_name':'shift_handover.bpmn'}
    assert client.post('/api/flows/import',json=imported).status_code==403
    client.post('/api/course-access/unlock',json={'code':sign()})
    assert client.post('/api/flows/import',json=imported).status_code==200
    # The portal sends null when the student leaves "흐름 id" empty (live 2026-10-28 refusal).
    for empty in (dict(imported,definition_id=None),{k:v for k,v in imported.items() if k!='definition_id'}):
        reply=client.post('/api/flows/import',json=empty)
        assert reply.status_code==200, reply.text
    mapping=deepcopy(flow.CONTENT['mapping']);mapping['name']='내 교대 인수인계'
    for task in flow.DRAFTS:mapping['tasks'][task]['agent']='agent:u-student'
    for method,action in [('put','mapping'),('post','check'),('post','register')]:
        assert getattr(client,method)('/api/flows/ShiftHandover/'+action,json={'mapping':mapping}).status_code==200
    for body in [dict(imported,definition_id='c3_cooling'),dict(imported,class_flow=True),
                 dict(imported,xml=imported['xml'].replace('targetRef="task_sender"','targetRef="ev_confirmed"')),
                 dict(imported,xml=imported['xml'].replace('bpmn:userTask','bpmn:serviceTask'))]:
        assert client.post('/api/flows/import',json=body).status_code==403
    for changed in [dict(mapping,start={'kind':'alert'}),dict(mapping,tasks=[]),dict(mapping,timers={'evil':{}})]:
        assert client.post('/api/flows/ShiftHandover/register',json={'mapping':changed}).status_code==403
        assert client.put('/api/flows/ShiftHandover/mapping',json={'mapping':changed}).status_code==403
    # A half-filled mapping can be previewed while the student connects rows (live 2026-10-28:
    # every preview was 403, so branch conditions had no values to pick), never registered.
    partial=deepcopy(mapping);partial['flows']={};partial['tasks']={'task_sender':mapping['tasks']['task_sender']}
    assert client.post('/api/flows/ShiftHandover/check',json={'mapping':partial}).status_code==200
    assert client.post('/api/flows/ShiftHandover/register',json={'mapping':partial}).status_code==403
    assert client.post('/api/flows/ShiftHandover/check',json={'mapping':partial,'class_flow':True}).status_code==403
    assert client.post('/api/flows/c3_cooling/check',json={'mapping':partial}).status_code==403
    mapping['tasks']['task_sender']={'part':'generic:task:system'}
    assert client.post('/api/flows/ShiftHandover/register',json={'mapping':mapping}).status_code==403
    for path in ['/api/flows/reset','/api/flows/c3_cooling/register','/api/process/definitions/ShiftHandover/deploy']:
        assert client.post(path,json={}).status_code==403


def test_all_three_imported_handover_drafts_require_the_signed_grant(instructor):
    grant=instructor[0]()
    for task in flow.DRAFTS:
        with pytest.raises(ValueError):rules.authorize_task(None,{'processDefinitionId':'ShiftHandover'},task,{})
        rules.authorize_task(grant,{'processDefinitionId':'ShiftHandover'},task,{})
    with pytest.raises(ValueError):rules.authorize_task(grant,{'processDefinitionId':'ShiftHandover'},'task_evil',{})


def test_registration_rechecks_persisted_xml_and_preserves_the_class_flows(api):
    from procsvc.bpmn_store import FlowStore
    client,runtime,repo,_=api
    client.app.state.course_access=object()
    repo.upsert_user(dict(id='agent:handover',username='인계 에이전트',is_agent=True,agent_type='agent',
                          tools='neo4j,enterprise,hyd-dmn',tenant_id='hyd'))
    store=FlowStore(repo,runtime.tenant_id)
    xml=flow.CONTENT['xml'];mapping=deepcopy(flow.CONTENT['mapping'])
    store.save_draft(flow.DEFINITION,xml.replace('bpmn:userTask','bpmn:serviceTask'),'shift.bpmn',mapping)
    response=client.post('/api/flows/ShiftHandover/register',json={'mapping':mapping})
    assert response.status_code==403 and not store.versions(flow.DEFINITION)
    store.save_draft(flow.DEFINITION,xml,'shift.bpmn',mapping)
    response=client.post('/api/flows/ShiftHandover/register',json={'mapping':mapping})
    assert response.status_code==201,response.text
    assert len(store.versions(flow.DEFINITION))==1


def test_imported_flow_worker_runs_revision_drafts_under_course_gate(api,tmp_path,instructor):
    import httpx
    from worker.runner import Runner
    from worker.course_access import CourseAccess
    from test_worker import _settings,_fake_exec,TENANT_MCP
    from test_handover import unknown_draft
    from test_inbox import KIM,CHOI
    client,runtime,repo,_=api
    for uid in (KIM,CHOI):repo.upsert_user(dict(id=uid,username=uid,is_agent=False,tenant_id='hyd'))
    repo.upsert_user(dict(id='agent:handover',username='인계 에이전트',is_agent=True,agent_type='agent',
        tools='neo4j,enterprise,hyd-dmn',work_rules='hyd-handover',tenant_id='hyd'))
    repo.upsert_tenant(dict(id='hyd',name='hyd',mcp=TENANT_MCP))
    client.post('/api/flows/import',json={'xml':flow.CONTENT['xml'],'definition_id':flow.DEFINITION})
    registered=client.post('/api/flows/ShiftHandover/register',json={'mapping':flow.CONTENT['mapping']})
    assert registered.status_code==201,registered.text
    inst=runtime.start_definition(flow.DEFINITION,registered.json()['version'],'course-revision',values=dict(
        asset='HYD-01',shift_label='다음 교대',as_of='2026-10-27T18:00:00+09:00',work_notes='완료 주장 확인 필요'))
    requests=[]
    gate=CourseAccess(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'grant':instructor[0]()})))
    runner=Runner(_settings(tmp_path),repo,exec_fn=_fake_exec(json.dumps(unknown_draft()),requests=requests),
                  resolve_provider=lambda _:object(),course_access=gate)
    for index in range(3):
        assert runner.poll_once()==1
        assert runtime.poll_once()==1
        suffix='' if index==0 else f'_r{index+1}'
        def ready(activity):
            return next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id'])
                        if w['activity_id']==activity and w['status']=='IN_PROGRESS')
        runtime.submit_human(ready('task_sender'+suffix)['id'],dict(sender_decision='approve',sender_notes='미확인 전달'),KIM)
        runtime.submit_human(ready('task_receiver'+suffix)['id'],dict(receiver_decision='revise' if index<2 else 'confirm',
            receiver_notes='열린 정비 확인 필요',communication_only=index==2),CHOI)
    assert len(requests)==3
    assert repo.get_instance(inst['proc_inst_id'])['status']=='COMPLETED'
