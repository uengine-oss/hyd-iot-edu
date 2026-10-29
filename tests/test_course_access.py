"""Classroom boundary (2026-10-29): course actions are open from the first lesson, everything outside the course is
refused — by the process API and again by the worker right before an AI run. There is no unlock step."""
import base64
import json
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from hydcommon import course_access as rules
from procsvc.course_access import CourseState, mount


def setup(tmp_path=None):
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
    calls = []
    async def echo(rest:str, request:Request):
        body = await request.json()
        calls.append((request.method,request.url.path,body))
        return {'received':body}
    store = CourseState()
    archive = type('Archive', (), {'get': lambda self, tenant, sid: {'sha256':sid.rsplit(':',1)[-1]}})()
    mount(app, archive_factory=lambda:archive, tenant='hyd', store=store)
    app.add_api_route('/api/{rest:path}',echo,methods=['POST','PUT','DELETE','PATCH'])
    return app,TestClient(app),store,calls


def test_status_has_no_unlock_and_course_actions_are_open():
    _,client,store,_ = setup()
    status = client.get('/api/course-access').json()
    assert status['phase'] == 'course' and 'unlocked' not in status
    caps = status['capabilities']
    assert caps['handover'] and caps['provided_manuals'] and caps['handover_flow'] and caps['agent_authoring']
    assert caps['model_settings'] is False and caps['tool_settings'] is False
    for path in ('/api/course-access/unlock', '/api/course-access'):
        assert client.post(path, json={'code':'HYD1.anything', 'unlocked':True}).status_code == 403


def test_outside_the_course_is_refused_and_cors_and_bodies_are_kept():
    _,client,store,calls = setup()
    for path,method,body in [('/api/agents','post',{'model':'other'}),('/api/agents','post',{'tools':['other']}),
          ('/api/agent-assignments','put',{'definition_id':'c3_cooling'}),('/api/agents/reset','post',{}),
          ('/api/ask','post',{'question':'arbitrary'}),('/api/config/import','post',{}),
          ('/api/flows/import','post',{}),('/api/mcp/servers','post',{}),('/api/process/definitions','post',{}),
          ('/api/instances/start','post',{'definition_id':'ask_agent'}),
          ('/api/instances/start','post',{'definition_id':['c3_cooling']})]:
        response=getattr(client,method)(path,json=body,headers={'Origin':'http://localhost:8088'})
        assert response.status_code==403 and response.headers['access-control-allow-origin']=='*', path
        assert 'course_locked' not in response.json() and '해제 코드' not in response.json()['detail']
    assert not calls
    for path,body in [('/api/scenario/A/degrade',{}),('/api/todolist/w/select',{'selected':'x'}),
                      ('/api/instances/start',{'definition_id':'c3_cooling'})]:
        assert client.post(path,json=body).status_code==200
    assert len(calls)==3
    assert calls[-1][2]=={'definition_id':'c3_cooling'}  # middleware didn't consume the downstream body


def test_course_actions_work_from_the_first_lesson_without_any_code():
    _,client,store,calls = setup()
    for path,method,body in [
        ('/api/agents','post',{'name':'냉각 점검','goal':'근거를 조사','tools':['neo4j','hyd-dmn']}),
        ('/api/agents/a','put',{'name':'새 이름','goal':'다른 설명','model':'coding'}),
        ('/api/skills','post',{'skill_name':'cooler','content':'점검'}),
        ('/api/agents/a/skills','post',{'skill_name':'cooler'}),
        ('/api/agent-assignments','put',{'definition_id':'ShiftHandover'}),
        ('/api/agent-assignments','put',{'definition_id':'shift_handover'}),
        ('/api/instances/start','post',{'definition_id':'ShiftHandover'}),
        ('/api/instances/start','post',{'definition_id':'c3_pm'}),
        ('/api/instances/start','post',{'definition_id':'c3_spare'})]:
        assert getattr(client,method)(path,json=body).status_code==200, path


def test_provided_documents_can_be_extracted_reviewed_committed_and_rolled_back_others_cannot():
    _,client,store,calls = setup()
    root=Path(__file__).parents[1]
    for sha in rules.CONTENT['document_hashes']:
        assert client.post('/api/kg/manuals/sources/manual:x:'+sha+'/extractions',json={}).status_code==200
        assert client.post('/api/kg/manuals/commit',json={'source_id':'manual:x:'+sha,'reviewed':True}).status_code==200
        assert client.post('/api/kg/manuals/changes',json={'source_id':'manual:x:'+sha}).status_code==200
    seed=json.loads((root/'it/neo4j/class-knowledge/HM-8.json').read_text(encoding='utf8'))
    raw=(root/'문서/시스템/참조/수업_문서_원문'/seed['filename']).read_bytes()
    assert client.post('/api/kg/manuals/preview',json={'data':base64.b64encode(raw).decode()}).status_code==200
    assert client.post('/api/kg/manuals/batches/b1/rollback',json={'by':'학생'}).status_code==200
    other='manual:other:'+'0'*64
    assert client.post(f'/api/kg/manuals/sources/{other}/extractions',json={}).status_code==403
    assert client.post('/api/kg/manuals/commit',json={'source_id':other}).status_code==403
    assert client.post('/api/kg/manuals/preview',json={'data':base64.b64encode(b'arbitrary big data').decode()}).status_code==403
    # 캐시 없는 AI 실행(골든 질문 평가)은 수업 밖
    assert client.post('/api/kg/manuals/batches/b1/golden-questions',json={'questions':['q']}).status_code==403
    sha=rules.CONTENT['document_hashes'][0]
    assert client.post('/api/kg/manuals/commit',json={'source_id':'manual:x:'+sha,'golden_questions':['q']}).status_code==403


def test_course_allows_only_fixed_mcp_reads_without_opening_configuration():
    _,client,store,calls = setup()
    assert client.get('/api/course-access').json()['capabilities']['tool_inspection'] is True
    for server, tool in [('hyd-dmn','inputs'),('hyd-dmn','timeseries_query'),
                         ('enterprise','describe_catalog'),('neo4j','read_neo4j_cypher')]:
        assert client.post(f'/api/mcp/servers/{server}/tools/{tool}/call',json={'arguments':{}}).status_code == 200
    for path in ('/api/mcp/servers/hyd-dmn/tools/submit_decision/call',
                 '/api/mcp/servers/hyd-dmn/tools/submit_purchase/call',
                 '/api/mcp/servers/custom/tools/inputs/call', '/api/mcp/servers',
                 '/api/mcp/servers/hyd-dmn/check', '/api/mcp/reset'):
        assert client.post(path,json={}).status_code == 403


def test_free_questions_follow_the_course_model_switch():
    _,client,store,calls = setup()
    assert client.post('/api/ask',json={'question':'냉각 경보 원인은?'}).status_code==403
    store.questions_enabled = True
    assert client.get('/api/course-access').json()['capabilities']['free_questions'] is True
    assert client.post('/api/ask',json={'question':'냉각 경보 원인은?'}).status_code==200


def test_worker_allows_every_course_step_and_refuses_unknown_work():
    from worker.course_access import CourseAccess
    check=CourseAccess()
    for did, activity in [('c3_cooling','T_agent'),('c3_pm','T_agent'),('c3_spare','T_agent'),
                          ('shift_handover','task:draft'),('ShiftHandover','task_draft'),('ShiftHandover','task_draft_r3')]:
        check({'processDefinitionId':did},activity,{})
    check({'processDefinitionId':'ask_agent'},'task:answer',{'question':'냉각 경보 원인은?'})
    with pytest.raises(ValueError):check({'processDefinitionId':'ask_agent'},'task:answer',{'question':'x'*1001})
    with pytest.raises(ValueError):check({'processDefinitionId':'ask_agent'},'task:ask',{})
    with pytest.raises(ValueError):check({'processDefinitionId':'manual_source_extraction'},'task:extract',{'manual_source':{'sha256':'0'*64}})
    with pytest.raises(ValueError):check({'processDefinitionId':'student_flow'},'task:anything',{})


def test_actual_runner_refuses_work_outside_the_course_before_calling_cli(rt,tmp_path,monkeypatch):
    from test_handover import begin,unknown_draft
    from test_worker import _settings,_fake_exec
    from worker.runner import Runner
    from worker.course_access import CourseAccess
    runtime,_=rt;inst=begin(runtime);requests=[]
    monkeypatch.setattr(rules,'COURSE_RUNS',{k:v for k,v in rules.COURSE_RUNS.items() if k not in rules.HANDOVER_DEFINITIONS})
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=_fake_exec(json.dumps(unknown_draft()),requests=requests),
                  resolve_provider=lambda _:object(),course_access=CourseAccess())
    assert runner.poll_once()==1 and not requests
    wi=next(w for w in runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='task:draft')
    assert wi['draft_status']=='FAILED'


def test_course_runner_runs_handover_and_forces_course_model(rt,tmp_path):
    from test_handover import begin,unknown_draft
    from test_worker import _settings,_fake_exec
    from worker.runner import Runner
    from worker.course_access import CourseAccess
    runtime,_=rt;begin(runtime);requests=[]
    agent=runtime.repo.list_users(['agent:handover'],'hyd')[0]
    runtime.repo.upsert_user(dict(agent,model='unapproved-model'))
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=_fake_exec(json.dumps(unknown_draft()),requests=requests),
                  resolve_provider=lambda _:object(),course_access=CourseAccess())
    assert runner.poll_once()==1 and len(requests)==1
    assert requests[0][0].model=='coding'
    assert requests[0][1]['ENABLE_TOOL_SEARCH']=='false'


from test_inbox import rt
