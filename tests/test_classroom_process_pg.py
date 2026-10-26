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


def test_instructor_import_reviews_changes_and_preserves_unrelated_data(pg,rt):
    from procsvc import classroom_manifest as m
    from test_classroom_manifest import candidate
    _,runtime,_=pg;memory,_=rt;memory.tenant_id=runtime.tenant_id
    value=candidate(memory)
    runtime.repo.write_skill(dict(tenant_id=runtime.tenant_id,skill_name='unrelated',description='',content='keep',origin='user'),create=True)
    review=m.review_target(runtime,value)
    assert set(review['changes'])=={'definition','agent','skill:student-check','assignment'}
    result=m.apply_candidate(runtime,value,fingerprint=review['fingerprint'],target_fingerprint=review['target_fingerprint'])
    assert result['permission_granted'] is False
    assert m.export_candidate(runtime,value['approval'])==value
    assert runtime.repo.get_skill(runtime.tenant_id,'unrelated')['content']=='keep'
    repeat=m.review_target(runtime,value)
    assert repeat['changes']==[]
    assert m.apply_candidate(runtime,value,fingerprint=repeat['fingerprint'],target_fingerprint=repeat['target_fingerprint'])['changes']==[]
    profile=memory.repo.list_users(['agent:student'],memory.tenant_id)[0]
    memory.repo.write_agent(dict(profile,goal='새 인계 지시'),['student-check'],create=False)
    updated=m.export_candidate(memory,value['approval'])
    review=m.review_target(runtime,updated)
    assert review['changes']==['agent']
    m.apply_candidate(runtime,updated,fingerprint=review['fingerprint'],target_fingerprint=review['target_fingerprint'])
    assert runtime.repo.list_users(['agent:student'],runtime.tenant_id)[0]['goal']=='새 인계 지시'


def test_instructor_grant_checks_imported_revision_and_keeps_usage(pg,rt):
    from copy import deepcopy
    from datetime import datetime,timedelta,timezone
    from uuid import uuid4
    import psycopg
    from psycopg.rows import dict_row
    from procsvc import classroom_admin,classroom_manifest as m
    from procsvc.classroom_authority import Authority,Denied,key_hash
    from test_classroom_authority_pg import POLICY
    from test_classroom_manifest import candidate
    _,runtime,_=pg;memory,_=rt;memory.tenant_id=runtime.tenant_id
    value=candidate(memory);review=m.review_target(runtime,value)
    m.apply_candidate(runtime,value,fingerprint=review['fingerprint'],target_fingerprint=review['target_fingerprint'])
    auth=Authority(lambda:psycopg.connect(DSN,row_factory=dict_row))
    key='instructor-import-'+uuid4().hex
    policy=deepcopy(POLICY);policy['documents']={}
    policy['actions']['agent_run']=policy['actions'].pop('manual_extract')
    policy['agents']={'student-draft':value['approval']}
    args=dict(key=key,subject=runtime.tenant_id,scope='lesson-v1',policy=policy,
              expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
    try:
        with pytest.raises(Denied,match='저장소'):
            classroom_admin.approve(auth,None,**args)
        first=classroom_admin.approve(auth,None,runtime=runtime,**args)
        assert first['calls']==0
        with auth.connect() as db:
            db.execute('update hyd_classroom_grants set calls=1,input_bytes=17,output_tokens=9 where key_hash=%s',(key_hash(key),))
        updated=classroom_admin.approve(auth,None,runtime=runtime,**dict(args,scope='lesson-v2'))
        assert (updated['calls'],updated['input_bytes'],updated['output_tokens'])==(1,17,9)
        runtime.repo.write_agent(dict(value['profile'],goal='unapproved',tenant_id=runtime.tenant_id),value['agent_skills'],create=False)
        with pytest.raises(Denied,match='판본'):
            classroom_admin.approve(auth,None,runtime=runtime,**dict(args,scope='lesson-v3'))
        with auth.connect() as db:
            assert db.execute('select scope from hyd_classroom_grants where key_hash=%s',(key_hash(key),)).fetchone()['scope']=='lesson-v2'
    finally:
        with auth.connect() as db:
            db.execute('delete from hyd_classroom_grants where key_hash=%s',(key_hash(key),))


def test_instructor_import_rejects_stale_review_live_work_and_rolls_back(pg,rt,monkeypatch):
    from procsvc import classroom_manifest as m
    from procsvc.classroom_authority import Denied
    from test_classroom_manifest import candidate
    _,runtime,_=pg;memory,_=rt;memory.tenant_id=runtime.tenant_id
    value=candidate(memory);review=m.review_target(runtime,value)
    with pytest.raises(Denied,match='후보'):
        m.apply_candidate(runtime,value,fingerprint='wrong',target_fingerprint=review['target_fingerprint'])
    original=runtime.repo.upsert_proc_def
    def fail(*args,**kwargs):raise RuntimeError('injected import failure after profile and skills')
    monkeypatch.setattr(runtime.repo,'upsert_proc_def',fail)
    with pytest.raises(RuntimeError,match='injected'):
        m.apply_candidate(runtime,value,fingerprint=review['fingerprint'],target_fingerprint=review['target_fingerprint'])
    assert not runtime.repo.list_users(['agent:student'],runtime.tenant_id)
    assert runtime.repo.get_skill(runtime.tenant_id,'student-check') is None
    monkeypatch.setattr(runtime.repo,'upsert_proc_def',original)
    runtime.repo.write_skill(dict(value['skills'][0],tenant_id=runtime.tenant_id,origin='user'),create=True)
    with pytest.raises(Denied,match='대상 내용'):
        m.apply_candidate(runtime,value,fingerprint=review['fingerprint'],target_fingerprint=review['target_fingerprint'])
    review=m.review_target(runtime,value)
    m.apply_candidate(runtime,value,fingerprint=review['fingerprint'],target_fingerprint=review['target_fingerprint'])
    runtime.start_definition(value['approval']['definition'],'1','live-import-guard',values={'memo':'진행'})
    profile=memory.repo.list_users(['agent:student'],memory.tenant_id)[0]
    memory.repo.write_agent(dict(profile,goal='실행 중 변경'),['student-check'],create=False)
    changed=m.export_candidate(memory,value['approval']);review=m.review_target(runtime,changed)
    assert review['live_work'] and not review['applicable']
    with pytest.raises(Denied,match='진행 중'):
        m.apply_candidate(runtime,changed,fingerprint=review['fingerprint'],target_fingerprint=review['target_fingerprint'])
    assert runtime.repo.list_users(['agent:student'],runtime.tenant_id)[0]['goal']==value['profile']['goal']


def test_import_boundary_excludes_ordinary_authoring_writers(pg):
    import psycopg
    _,runtime,_=pg
    # A separate portal/worker connection does not take the import advisory lock.
    # Its normal SQL must still be excluded from the review/apply transaction.
    with runtime.repo.classroom_authoring_transaction(runtime.tenant_id):
        with psycopg.connect(DSN) as other:
            other.execute("set local lock_timeout='100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                other.execute('update users set goal=goal where tenant_id=%s',(runtime.tenant_id,))
            other.rollback()


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
