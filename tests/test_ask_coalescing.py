from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from procsvc import ask
from test_instances import rt
from test_b5_ask import _ask, _people


def test_new_request_ids_join_only_the_current_question_and_keep_aliases_after_completion(rt):
    runtime, _ = rt
    _people(runtime)
    ids = [str(uuid4()) for _ in range(6)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda rid:_ask(runtime,rid=rid),ids))
    cases = [runtime.repo.find_event_instance('hyd',ask.DEFINITION_ID,'ask:'+rid) for rid in ids]
    assert len({i['proc_inst_id'] for i in cases}) == 1
    assert len(runtime.repo.list_workitems(proc_inst_id=cases[0]['proc_inst_id'])) == 1
    row = runtime.repo.fetch_pending_task('cliagents','one-question')[0]
    runtime.repo.save_task_result(row['id'],{'status':'cannot_answer','reason':'무과금 시험'},True)
    runtime.poll_once()
    for rid in ids:_ask(runtime,rid=rid)
    assert len(runtime.repo.list_instances(tenant_id='hyd')) == 1
    # A new question after completion reads current facts; it is not a replay.
    rid = str(uuid4());_ask(runtime,rid=rid)
    assert runtime.repo.find_event_instance('hyd',ask.DEFINITION_ID,'ask:'+rid)['proc_inst_id'] != cases[0]['proc_inst_id']


def test_display_name_is_flexible_but_changed_instructions_and_reused_id_are_distinct(rt):
    runtime, _ = rt
    _people(runtime)
    first = str(uuid4());_ask(runtime,rid=first)
    original = runtime.repo.find_event_instance('hyd',ask.DEFINITION_ID,'ask:'+first)
    user = runtime.repo.list_users(['sys:agent'],'hyd')[0]
    runtime.repo.upsert_user(dict(user,username='완전히 다른 표시 이름'))
    alias = str(uuid4());_ask(runtime,rid=alias)
    assert runtime.repo.find_event_instance('hyd',ask.DEFINITION_ID,'ask:'+alias)['proc_inst_id'] == original['proc_inst_id']
    runtime.repo.upsert_user(dict(user,goal='다른 설명과 새로운 정리 방식'))
    changed = str(uuid4());_ask(runtime,rid=changed)
    assert runtime.repo.find_event_instance('hyd',ask.DEFINITION_ID,'ask:'+changed)['proc_inst_id'] != original['proc_inst_id']
    with pytest.raises(ValueError,match='다른 질문'):_ask(runtime,q='바뀐 질문',rid=first)


def test_coalescing_metadata_cannot_be_injected_as_start_input(rt):
    from test_b5_ask import DEFS
    runtime, _ = rt
    ask.register_definition(runtime,DEFS)
    with pytest.raises(ValueError):
        runtime.start_definition(ask.DEFINITION_ID,ask.VERSION,'forged',
                    values={'question':'x','_runtime_coalescing':{'events':['ask:other']}})


def test_reused_request_id_rejects_changed_agent_instructions(rt):
    runtime, _ = rt
    _people(runtime)
    rid = str(uuid4())
    first = _ask(runtime, rid=rid)
    agent = runtime.repo.list_users(['sys:agent'], 'hyd')[0]
    runtime.repo.upsert_user(dict(agent, username='새 표시 이름'))
    assert _ask(runtime, rid=rid)['id'] == first['id']
    runtime.repo.upsert_user(dict(agent, goal='내용이 다른 새 업무 목표'))
    with pytest.raises(ValueError, match='다른.*조건'):
        _ask(runtime, rid=rid)


def test_existing_legacy_request_is_readable_but_not_reused_without_settings_binding(rt):
    from test_b5_ask import DEFS
    runtime, _ = rt
    _people(runtime)
    ask.register_definition(runtime, DEFS)
    rid = str(uuid4())
    inst = runtime.start_definition(ask.DEFINITION_ID, ask.VERSION, 'ask:'+rid,
                                    values={'question':'완제품 재고가 가장 적은 설비와 그 수량은?'},
                                    role_endpoints={ask.ROLE:'sys:agent'})
    with pytest.raises(ValueError, match='기존 조건을 확인'):
        _ask(runtime, rid=rid)
    assert ask.view(runtime, inst['proc_inst_id'])['id'] == inst['proc_inst_id']


def test_ask_api_reports_reused_id_with_changed_settings_without_creating_a_task(rt):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from test_b5_ask import DEFS, UP
    runtime, _ = rt
    _people(runtime)
    rid = str(uuid4())
    first = _ask(runtime, rid=rid)
    agent = runtime.repo.list_users(['sys:agent'], 'hyd')[0]
    runtime.repo.upsert_user(dict(agent, goal='수정된 목표'))
    app = FastAPI()
    ask.register(app, runtime_factory=lambda:runtime, definitions_dir=DEFS, worker_probe=UP, bridge=lambda:'off')
    response = TestClient(app).post('/api/ask', json={'question':'완제품 재고가 가장 적은 설비와 그 수량은?', 'request_id':rid})
    assert response.status_code == 400 and '다른 에이전트 조건' in response.json()['detail']
    assert len(runtime.repo.list_workitems(proc_inst_id=first['id'])) == 1


@pytest.mark.parametrize('change', [{'goal':'새 목표'}, {'tools':'hyd-dmn'}])
def test_queued_question_does_not_run_after_agent_execution_settings_change(rt, tmp_path, change):
    from test_b5_ask import _cli, _work
    runtime, _ = rt
    _people(runtime)
    started = _ask(runtime, rid=str(uuid4()))
    agent = runtime.repo.list_users(['sys:agent'], 'hyd')[0]
    runtime.repo.upsert_user(dict(agent, **change))
    requests = []
    _work(runtime, tmp_path, _cli({'status':'cannot_answer','reason':'fixture'}, requests=requests))
    row = runtime.repo.get_workitem(started['workitem'])
    assert not requests and row['draft_status'] == 'FAILED' and row['output'] is None
    errors = runtime.repo.list_events(todo_id=row['id'])
    assert any('에이전트 설정이 바뀌었습니다' in str(e.get('data',{})) for e in errors)


def test_queued_question_allows_display_name_change(rt, tmp_path):
    from test_b5_ask import _cli, _work
    runtime, _ = rt
    _people(runtime)
    started = _ask(runtime, rid=str(uuid4()))
    agent = runtime.repo.list_users(['sys:agent'], 'hyd')[0]
    runtime.repo.upsert_user(dict(agent, username='새 표시 이름'))
    requests = []
    _work(runtime, tmp_path, _cli({'status':'cannot_answer','reason':'fixture'}, requests=requests))
    assert len(requests) == 1 and ask.view(runtime, started['id'])['state'] == 'done'


def test_queued_question_keeps_its_original_definition_version(rt, tmp_path, monkeypatch):
    from test_b5_ask import _cli, _work
    runtime, _ = rt
    _people(runtime)
    started = _ask(runtime, rid=str(uuid4()))
    monkeypatch.setattr(ask, 'VERSION', 'future-version')
    requests = []
    _work(runtime, tmp_path, _cli({'status':'cannot_answer','reason':'fixture'}, requests=requests))
    assert len(requests) == 1 and ask.view(runtime, started['id'])['state'] == 'done'


def test_queued_question_stops_if_attached_skill_content_changes(rt, tmp_path):
    from test_b5_ask import _cli, _work
    runtime, _ = rt
    _people(runtime)
    skill = {'skill_name':'cooler-check', 'description':'점검', 'content':'원래 점검 방법'}
    runtime.repo.put_skill(skill)
    runtime.repo.attach_skill('sys:agent', 'cooler-check')
    started = _ask(runtime, rid=str(uuid4()))
    runtime.repo.put_skill(dict(skill, content='바뀐 점검 방법'))
    requests = []
    _work(runtime, tmp_path, _cli({'status':'cannot_answer','reason':'fixture'}, requests=requests))
    row = runtime.repo.get_workitem(started['workitem'])
    assert not requests and row['draft_status'] == 'FAILED' and row['output'] is None


def test_failed_question_retry_preserves_work_generation_trace_and_is_bounded(rt):
    runtime, _ = rt
    _people(runtime)
    rid=str(uuid4());_ask(runtime,rid=rid)
    inst=runtime.repo.find_event_instance('hyd',ask.DEFINITION_ID,'ask:'+rid)
    row=runtime.repo.fetch_pending_task('cliagents','failed-run')[0]
    runtime.repo.record_events([dict(job_id='original-failure',todo_id=row['id'],proc_inst_id=inst['proc_inst_id'],
                                   crew_type='agent',event_type='error',data={'reason':'connection error'})])
    runtime.repo.update_task_error(row['id'],expected_consumer=row['consumer'])
    request=str(uuid4())
    with pytest.raises(PermissionError):ask.retry(runtime,inst['proc_inst_id'],request,'다른 사람','연결 수정')
    ask.retry(runtime,inst['proc_inst_id'],request,'수강생','연결 수정')
    ask.retry(runtime,inst['proc_inst_id'],request,'수강생','연결 수정')
    events=runtime.repo.list_events(todo_id=row['id'])
    assert len([e for e in events if e['data'].get('ask_retry_id')])==1
    assert any(e['job_id']=='original-failure' for e in events)
    resumed=runtime.repo.fetch_pending_task('cliagents','restored-run')[0]
    assert resumed['id']==row['id'] and resumed.get('generation',0)==row.get('generation',0)
    runtime.repo.update_task_error(row['id'],expected_consumer=resumed['consumer'])
    ask.retry(runtime,inst['proc_inst_id'],str(uuid4()),'수강생','두 번째 확인')
    resumed=runtime.repo.fetch_pending_task('cliagents','restored-run')[0]
    runtime.repo.update_task_error(row['id'],expected_consumer=resumed['consumer'])
    with pytest.raises(ValueError,match='2회'):ask.retry(runtime,inst['proc_inst_id'],str(uuid4()),'수강생','세 번째 요청')


def test_real_retry_http_contract_rejects_wrong_requester_and_extra_input(rt):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from test_b5_ask import DEFS,UP
    runtime, _=rt;_people(runtime)
    rid=str(uuid4());_ask(runtime,rid=rid)
    inst=runtime.repo.find_event_instance('hyd',ask.DEFINITION_ID,'ask:'+rid)
    row=runtime.repo.fetch_pending_task('cliagents','failed-run')[0]
    runtime.repo.update_task_error(row['id'],expected_consumer=row['consumer'])
    app=FastAPI();ask.register(app,runtime_factory=lambda:runtime,definitions_dir=DEFS,worker_probe=UP,bridge=lambda:'off')
    client=TestClient(app);path='/api/ask/'+inst['proc_inst_id']+'/retry'
    body=dict(request_id=str(uuid4()),by='수강생',reason='연결 수정')
    assert client.post(path,json=dict(body,question='다른 질문')).status_code==422
    assert client.post(path,json=dict(body,by='다른 사람')).status_code==403
    assert client.post(path,json=body).status_code==200
