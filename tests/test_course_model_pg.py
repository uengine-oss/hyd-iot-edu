"""Real claim/authority tables; model requests are charged, never sent upstream."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest

from fastapi import HTTPException
from procsvc import ask, classroom_model, course_model
from procsvc.classroom_authority import Denied
from test_backend_pg_contracts import pg, DSN

pytestmark = pytest.mark.skipif(not DSN, reason='requires disposable fully migrated PostgreSQL')
DEFINITIONS = Path(__file__).resolve().parents[1]/'it/process/definitions'


@pytest.fixture
def bounded(pg, tmp_path, monkeypatch):
    _, runtime, _ = pg
    key_file = tmp_path/'runtime.key';key_file.write_text('private-test-runtime-'+'x'*40)
    monkeypatch.setenv('HYD_WORKER_RUNTIME_KEY_FILE',str(key_file))
    policy = deepcopy(course_model.POLICY)
    policy['total_calls'] = 2
    policy['actions']['class_check']['max_calls'] = 1
    monkeypatch.setattr(course_model,'POLICY',policy)
    authority = course_model.CourseAuthority(lambda:psycopg.connect(DSN,row_factory=dict_row),
                                             SimpleNamespace(grant=lambda:None))
    with runtime.repo._conn() as db:
        db.execute("insert into users(id,username,is_agent,agent_type,tenant_id,model) values (%s,%s,true,'agent',%s,'coding')",
                   ('agent:'+runtime.tenant_id,'다른 이름·설명의 에이전트',runtime.tenant_id))
    runtime.register_definition(ask.definition(DEFINITIONS))
    def claimed(question='원문에서 HI-01의 조회 절차를 설명해줘'):
        inst = runtime.start_definition(ask.DEFINITION_ID,ask.VERSION,'ask:'+str(uuid4()),
                    values={'question':question,'asked_by':'수강생'}, role_endpoints={ask.ROLE:'agent:'+runtime.tenant_id})
        rows = runtime.repo.fetch_pending_task('cliagents','bounded-test',tenant_id=runtime.tenant_id)
        assert len(rows) == 1
        row = rows[0]
        body = dict(tenant_id=runtime.tenant_id,todo_id=row['id'],consumer=row['consumer'])
        return inst,row,body
    def complete(row):
        runtime.repo.save_task_result(row['id'],{'status':'cannot_answer','reason':'유료 호출 없는 경계 시험'},True,
                                     expected_consumer=row['consumer'])
        assert runtime.poll_once() == 1
    yield runtime,authority,claimed,complete,key_file.read_text()
    with runtime.repo._conn() as db:
        db.execute('delete from hyd_classroom_runs where key_hash in (select key_hash from hyd_classroom_grants where subject=%s)',
                   (runtime.tenant_id,))
        db.execute('delete from hyd_classroom_grants where subject=%s',(runtime.tenant_id,))


def payload():
    return json.dumps({'model':'coding','max_tokens':32,'messages':[{'role':'user','content':'수업 질문'}]}).encode()


def test_local_permit_rejoins_same_run_and_limits_survive_authority_recreation(bounded):
    runtime,authority,claimed,complete,key = bounded
    _,row,body = claimed()
    permit = classroom_model.issue(runtime,authority,body,'Bearer '+key)
    same = classroom_model.issue(runtime,authority,body,'Bearer '+key)
    binding = classroom_model.verify_token(permit['token'])
    assert binding['run_id'] == classroom_model.verify_token(same['token'])['run_id']
    assert 0 < permit['expires']-__import__('time').time() <= 600
    classroom_model.prepare(runtime,authority,permit['token'],payload())
    # A new service object and repeated permit issuance cannot reset usage.
    authority = course_model.CourseAuthority(authority.connect,authority.access_store)
    again = classroom_model.issue(runtime,authority,body,'Bearer '+key)
    with pytest.raises(HTTPException) as caught:
        classroom_model.prepare(runtime,authority,again['token'],payload())
    assert caught.value.status_code == 429
    complete(row)
    assert authority.usage(runtime)['executions']=={'DONE':1}
    assert authority.usage(runtime)['used']['model_requests']==1
    _,second,body = claimed('설명과 표현을 자유롭게 바꾼 다른 질문')
    permit = classroom_model.issue(runtime,authority,body,'Bearer '+key)
    classroom_model.prepare(runtime,authority,permit['token'],payload())
    complete(second)
    _,third,body = claimed('세 번째 질문')
    permit = classroom_model.issue(runtime,authority,body,'Bearer '+key)
    with pytest.raises(HTTPException) as caught:
        classroom_model.prepare(runtime,authority,permit['token'],payload())
    assert caught.value.status_code == 429
    with authority.connect() as db:
        row = db.execute('select calls from hyd_classroom_grants where subject=%s',(runtime.tenant_id,)).fetchone()
        assert row['calls'] == 2


def test_concurrency_model_override_and_disabled_account_never_charge(bounded):
    runtime,authority,claimed,complete,key = bounded
    _,row,body = claimed()
    permit = classroom_model.issue(runtime,authority,body,'Bearer '+key)
    _,other,other_body = claimed('동시에 들어온 별도 질문')
    with pytest.raises(HTTPException) as caught:
        classroom_model.issue(runtime,authority,other_body,'Bearer '+key)
    assert caught.value.status_code == 403
    with pytest.raises(HTTPException):
        classroom_model.prepare(runtime,authority,permit['token'],payload().replace(b'coding',b'other'))
    with authority.connect() as db:
        db.execute('update hyd_classroom_grants set enabled=false where subject=%s',(runtime.tenant_id,))
    with pytest.raises(HTTPException):classroom_model.issue(runtime,authority,body,'Bearer '+key)
    with authority.connect() as db:
        grant=db.execute('select calls,enabled from hyd_classroom_grants where subject=%s',(runtime.tenant_id,)).fetchone()
        assert grant['calls']==0 and grant['enabled'] is False


def test_real_postgres_question_aliases_join_and_persist_after_completion(bounded):
    from concurrent.futures import ThreadPoolExecutor
    runtime,authority,_,complete,_ = bounded
    ids = [str(uuid4()) for _ in range(6)]
    def start(rid):
        return ask.start(runtime,'사용자가 자유롭게 적은 같은 수업 질문','agent:'+runtime.tenant_id,
                         request_id=rid,definitions_dir=DEFINITIONS,worker_probe=lambda:{'reachable':True},bridge='off')
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(start,ids))
    cases=[runtime.repo.find_event_instance(runtime.tenant_id,ask.DEFINITION_ID,'ask:'+rid) for rid in ids]
    assert len({v['proc_inst_id'] for v in cases})==1
    row=runtime.repo.fetch_pending_task('cliagents','bounded-test',tenant_id=runtime.tenant_id)[0]
    complete(row)
    for rid in ids:start(rid)
    assert len(runtime.repo.list_instances(tenant_id=runtime.tenant_id))==1
    fresh=str(uuid4());start(fresh)
    assert runtime.repo.find_event_instance(runtime.tenant_id,ask.DEFINITION_ID,'ask:'+fresh)['proc_inst_id']!=cases[0]['proc_inst_id']


def test_transient_failure_can_resume_same_authorization_without_resetting_usage(bounded,monkeypatch):
    runtime,authority,claimed,complete,key=bounded
    policy=deepcopy(course_model.POLICY);policy['actions']['class_check']['max_calls']=2
    monkeypatch.setattr(course_model,'POLICY',policy)
    inst,row,body=claimed()
    permit=classroom_model.issue(runtime,authority,body,'Bearer '+key)
    original=classroom_model.verify_token(permit['token'])['run_id']
    classroom_model.prepare(runtime,authority,permit['token'],payload())
    runtime.repo.update_task_error(row['id'],expected_consumer=row['consumer'])
    status=authority.usage(runtime)
    assert status['paused_executions']==1 and status['used']['model_requests']==1
    ask.retry(runtime,inst['proc_inst_id'],str(uuid4()),'수강생','기존 조회와 같은 대화로 재개')
    resumed=runtime.repo.fetch_pending_task('cliagents','resume-worker',tenant_id=runtime.tenant_id)[0]
    body=dict(tenant_id=runtime.tenant_id,todo_id=resumed['id'],consumer=resumed['consumer'])
    permit=classroom_model.issue(runtime,authority,body,'Bearer '+key)
    assert classroom_model.verify_token(permit['token'])['run_id']==original
    classroom_model.prepare(runtime,authority,permit['token'],payload())
    complete(resumed)
    status=authority.usage(runtime)
    assert status['used']['model_requests']==2 and status['executions']=={'DONE':1} and status['paused_executions']==0


def test_changed_agent_during_recovery_preserves_same_run_and_budget(bounded, monkeypatch, tmp_path):
    from test_b5_ask import _cli
    from worker.runner import Runner
    from worker.settings import Settings
    runtime, authority, _, complete, key = bounded
    policy = deepcopy(course_model.POLICY)
    policy['actions']['class_check']['max_calls'] = 2
    monkeypatch.setattr(course_model, 'POLICY', policy)
    agent_id = 'agent:' + runtime.tenant_id
    started = ask.start(runtime, '수업 상태를 알려 주세요', agent_id, '수강생', str(uuid4()),
                        definitions_dir=DEFINITIONS, worker_probe=lambda:{'reachable':True}, bridge='off')
    row = runtime.repo.fetch_pending_task('cliagents', 'first-claim', tenant_id=runtime.tenant_id)[0]
    body = dict(tenant_id=runtime.tenant_id, todo_id=row['id'], consumer=row['consumer'])
    permit = classroom_model.issue(runtime, authority, body, 'Bearer '+key)
    original_run = classroom_model.verify_token(permit['token'])['run_id']
    classroom_model.prepare(runtime, authority, permit['token'], payload())
    runtime.repo.update_task_error(row['id'], expected_consumer=row['consumer'])
    with runtime.repo._conn() as db:
        db.execute('update users set goal=%s where id=%s', ('바뀐 목표',agent_id))
    ask.retry(runtime, started['id'], str(uuid4()), '수강생', '다시 확인')
    requests = []
    runner = Runner(Settings(workspace_root=tmp_path, tenant_id=runtime.tenant_id,
                             consumer='changed-agent', cancel_check_every_s=0),
                    runtime.repo, exec_fn=_cli({'status':'cannot_answer','reason':'fixture'}, requests=requests),
                    schema_prompt='# fixture', resolve_provider=lambda _:object())
    assert runner.poll_once() == 1 and not requests
    assert runtime.repo.get_workitem(row['id'])['draft_status'] == 'FAILED'
    status = authority.usage(runtime)
    assert status['paused_executions'] == 1 and status['used']['model_requests'] == 1
    with runtime.repo._conn() as db:
        db.execute('update users set goal=null where id=%s', (agent_id,))
    ask.retry(runtime, started['id'], str(uuid4()), '수강생', '기존 설정 복구')
    resumed = runtime.repo.fetch_pending_task('cliagents', 'restored-claim', tenant_id=runtime.tenant_id)[0]
    body = dict(tenant_id=runtime.tenant_id, todo_id=resumed['id'], consumer=resumed['consumer'])
    resumed_permit = classroom_model.issue(runtime, authority, body, 'Bearer '+key)
    assert classroom_model.verify_token(resumed_permit['token'])['run_id'] == original_run
    classroom_model.prepare(runtime, authority, resumed_permit['token'], payload())
    complete(resumed)
    status = authority.usage(runtime)
    assert status['used']['model_requests'] == 2 and status['executions'] == {'DONE':1}
