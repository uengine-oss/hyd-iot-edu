"""Real migrated process storage, not only the separate authority database."""
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from procsvc import classroom_agents,classroom_responses
from worker import student_execution,context
from worker.runner import Runner
from test_backend_pg_contracts import pg,DSN
from test_classroom_agents import approved
from test_instances import rt
from test_worker import _settings

pytestmark=pytest.mark.skipif(not DSN,reason='requires disposable fully migrated process PostgreSQL')


def test_authored_candidate_exports_identically_from_real_pg(pg,rt):
    from procsvc import classroom_manifest
    from test_classroom_manifest import candidate
    _,runtime,_=pg;memory,_=rt
    memory.tenant_id=runtime.tenant_id
    value=candidate(memory)
    runtime.register_definition(value['definition'])
    for skill in value['skills']:
        runtime.repo.write_skill(dict(skill,tenant_id=runtime.tenant_id,origin='user'),create=True)
    runtime.repo.write_agent(dict(value['profile'],tenant_id=runtime.tenant_id,origin='user'),value['agent_skills'],create=True)
    runtime.repo.put_agent_map(dict(tenant_id=runtime.tenant_id,proc_def_id=value['approval']['definition'],
        activity_id=value['approval']['activity'],agent_id=value['assignment']))
    exported=classroom_manifest.export_candidate(runtime,value['approval'])
    assert exported==value
    assert classroom_manifest.review_candidate(exported)['permission_granted'] is False


@pytest.mark.parametrize('kind',['human_answer','reassessment'])
def test_process_pg_control_roundtrip_has_one_storage_transaction(pg,rt,tmp_path,kind):
    parsed=urlsplit(DSN)
    assert parsed.hostname=='127.0.0.1' and parsed.port==55757 and parsed.path=='/hyd_system_progress_test'
    _,runtime,_=pg;memory,_=rt
    approval=approved(memory)
    profile=memory.repo.list_users(['agent:class-test'],memory.tenant_id)[0]
    runtime.repo.write_agent(dict(profile,tenant_id=runtime.tenant_id),[],create=True)
    source=memory.repo.get_proc_def(approval['definition'],memory.tenant_id,version='1')['definition']
    source['version']='2'
    source['activities']=source['activities'][:1]
    source['sequences']=[{'id':'s1','source':'s','target':'draft'},{'id':'s2','source':'draft','target':'e'}]
    memory.register_definition(source)
    approval['version']='2';approval['revision']=classroom_agents.revision(memory,approval)
    runtime.register_definition(source)
    # PG adds null fields/timestamps; execution semantics must remain identical.
    assert classroom_agents.revision(runtime,approval)==approval['revision']
    inst=runtime.start_definition(approval['definition'],approval['version'],'local',values={'memo':'실재고 확인'})
    state={'responded':False}
    def result(*args):
        if state['responded']:return {'status':'DONE','output':{'answer':'사람 확인 완료'}}
        if kind=='human_answer':return {'status':'NEEDS_INPUT','request_id':'remote-question','question':'재고 확인?'}
        return {'status':'DEFERRED','request_id':'remote-deferral','assessment':{'status':'UNKNOWN','reason':'재고 확인 필요','evidence':{}}}
    def respond(*args):state['responded']=True;return {'status':'QUEUED'}
    client=SimpleNamespace(agent_contract=lambda *a:{'approval':approval,'reference':'lesson','max_seconds':60,'tools':[]},
        start_agent=lambda *a:'same-remote-run',agent_result=result,respond_agent=respond,
        cancel_agent=lambda *a:state.update(cancelled=True),
        cancel_start=lambda *a:state.update(cancelled=True))
    runner=Runner(_settings(tmp_path),runtime.repo,schema_prompt='s')
    runner.s=__import__('dataclasses').replace(runner.s,tenant_id=runtime.tenant_id)
    row=runtime.repo.fetch_pending_task('cliagents','student-1',tenant_id=runtime.tenant_id)[0]
    student_execution.execute(runner,row,context.prepare(runtime.repo,row,runtime.tenant_id),'first',client)
    paused=runtime.repo.get_workitem(row['id'])
    control=classroom_responses.control(paused)
    assert control['status']==('NEEDS_INPUT' if kind=='human_answer' else 'DEFERRED')
    policy={kind:{'max_count':1,'schema':{'type':'string','enum':['확인했습니다']}}}
    assert classroom_responses.respond(runtime,inst,policy,kind,control['request_id'],'확인했습니다')['status']=='QUEUED'
    again=runtime.repo.fetch_pending_task('cliagents','student-2',tenant_id=runtime.tenant_id)[0]
    student_execution.execute(runner,again,context.prepare(runtime.repo,again,runtime.tenant_id),'second',client)
    assert runtime.repo.get_workitem(row['id'])['status']=='SUBMITTED'
    assert not state.get('cancelled')
