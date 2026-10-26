"""Pin one instructor-approved agent activity, without its business effects.

Definitions, profiles and skill bodies are read on the instructor server. The
student supplies only the approved reference and schema-checked input values.
The ordinary engine/worker retains form validation and bounded correction.
"""
from copy import deepcopy
from dataclasses import asdict
from fastapi.encoders import jsonable_encoder

from hydcommon.process_contracts import pinned_form
from . import agents_store, engine, mcp_check
from .classroom_authority import Denied, digest
from .classroom_tool_io import encoded, identifier


def snapshot(runtime, approval):
    required={'definition','version','activity','revision','input_schema'}
    if not isinstance(approval,dict) or set(approval)!=required:
        raise Denied('강사 에이전트 승인 명세가 올바르지 않습니다')
    saved=runtime.repo.get_proc_def(approval['definition'],runtime.tenant_id,version=approval['version'])
    source=(saved or {}).get('definition')
    if not source:
        raise Denied('강사 서버에 승인할 정의 판본이 없습니다')
    activity=next((a for a in source.get('activities',[]) if a.get('id')==approval['activity']),None)
    if (not activity or activity.get('type')!='userTask' or activity.get('agentMode')!='COMPLETE'
            or activity.get('orchestration')!='cliagents'):
        raise Denied('관리 실행 대상은 에이전트 작업 한 단계여야 합니다')
    role=next((r for r in source.get('roles',[]) if r.get('name')==activity.get('role')),None)
    endpoint=(role or {}).get('endpoint')
    if not endpoint:
        raise Denied('승인 에이전트 담당 연결이 없습니다')
    profile=None
    if endpoint!='sys:agent':
        users=runtime.repo.list_users([endpoint],runtime.tenant_id)
        if len(users)!=1 or not users[0].get('is_agent'):
            raise Denied('사람 역할이나 미등록 에이전트는 관리 실행할 수 없습니다')
        profile=users[0]
    caps=agents_store.activity_capabilities(source,activity['id'])
    settings=agents_store.agent_settings(runtime.repo,runtime.tenant_id,profile,activity=caps)
    if settings.missing_skills:
        raise Denied('승인 에이전트의 스킬 본문이 없습니다')
    form=pinned_form(source,activity.get('tool',''))
    if not form:
        raise Denied('정의 판본에 고정된 출력 폼이 필요합니다')
    schema=approval['input_schema']
    if not isinstance(schema,dict) or schema.get('type')!='object' or schema.get('additionalProperties') is not False:
        raise Denied('승인 입력은 추가 필드를 막는 객체 스키마여야 합니다')
    properties=set(schema.get('properties') or {})
    if not properties.issubset(set(activity.get('inputData') or [])) or 'classroom_execution' in properties:
        raise Denied('입력 스키마는 해당 작업의 입력만 허용해야 합니다')
    bundle=jsonable_encoder({'source_definition':source,'activity':activity,'agent':asdict(settings),'input_schema':schema})
    return source,activity,role,bundle


def revision(runtime,approval):
    return digest(snapshot(runtime,approval)[3])


def checked(runtime,approval):
    source,activity,role,bundle=snapshot(runtime,approval)
    if digest(bundle)!=approval['revision']:
        raise Denied('에이전트·정의·스킬이 강사 승인 판본과 다릅니다')
    return source,activity,role


def validate_input(approval,values):
    if not isinstance(values,dict) or len(encoded(values))>8000:
        raise Denied('승인 수업 입력 크기 한도 초과')
    problem=mcp_check._argument_problem({'input_schema':approval['input_schema']},values)
    if problem:
        raise Denied('수업 입력이 강사 승인 스키마와 다릅니다')


def start(runtime,approval,values,run_id,reference):
    run_id=identifier(run_id)
    source,activity,role=checked(runtime,approval)
    validate_input(approval,values)
    did='classroom_agent_'+approval['revision'][:24]
    definition=dict(processDefinitionId=did,processDefinitionName=activity.get('name') or '승인 에이전트 실행',version='1',
        roles=[deepcopy(role)],data=deepcopy(source.get('data') or []),forms=deepcopy(source['forms']),
        activities=[deepcopy(activity)],gateways=[],
        events=[{'id':'managed_start','type':'startEvent','name':'승인 실행'},
                {'id':'managed_end','type':'endEvent','name':'검토할 제안 생성'}],
        sequences=[{'id':'managed_in','source':'managed_start','target':activity['id']},
                   {'id':'managed_out','source':activity['id'],'target':'managed_end'}],
        classroom_agent=deepcopy(approval))
    runtime.register_definition(definition)
    event='classroom-agent:'+run_id
    inputs=dict(deepcopy(values),classroom_execution={'run_id':run_id},classroom_agent_reference=reference)
    inst=runtime.start_definition(did,'1',event,values=inputs,name=definition['processDefinitionName'])
    inst=inst or runtime.repo.find_event_instance(runtime.tenant_id,did,event)
    saved=engine.variables(inst)
    if any(saved.get(k)!=v for k,v in inputs.items()):
        raise Denied('기존 실행 ID에 다른 입력을 연결할 수 없습니다')
    return inst


def verify_instance(runtime,instance):
    definition=runtime.definition_for(instance).raw
    approval=definition.get('classroom_agent')
    checked(runtime,approval)
    return approval


def verify_tool(runtime,instance,qualified):
    approval=verify_instance(runtime,instance)
    bundle=snapshot(runtime,approval)[3]
    servers=bundle['agent']['tools']
    if (not isinstance(qualified,str) or qualified.count('/')!=1
            or servers is not None and qualified.split('/')[0] not in servers):
        raise Denied('승인 에이전트 단계가 사용하는 도구 서버가 아닙니다')


def filter_tools(runtime,instance,tools):
    approval=verify_instance(runtime,instance)
    servers=snapshot(runtime,approval)[3]['agent']['tools']
    return [tool for tool in tools if servers is None or tool['server'] in servers]
