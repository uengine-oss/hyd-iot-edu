"""Human questions must survive filesystem loss and partial persistence failure."""
import json
import pytest

from test_worker import _repo, _settings, _fake_exec
from worker import hitl, workspace
from worker.runner import Runner


def diagnose(repo, inst):
    return next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='task:diagnose')


def test_pending_file_failure_does_not_lose_question(tmp_path,monkeypatch):
    repo,inst=_repo()
    def fail(*a):raise OSError('injected disk error')
    monkeypatch.setattr(hitl,'remember',fail)
    Runner(_settings(tmp_path),repo,exec_fn=_fake_exec('',permission_refusal='담당자 확인')).poll_once()
    wi=diagnose(repo,inst)
    questions=[e for e in repo.list_events(todo_id=wi['id']) if e['event_type']=='human_asked']
    assert wi['draft_status']=='HUMAN_ASKED' and len(questions)==1
    assert wi['draft']['cliagents_session_id']=='sess-A'
    assert len(repo.notifications)==1


def test_question_event_failure_does_not_leave_unanswerable_state(tmp_path,monkeypatch):
    repo,inst=_repo();record=repo.record_events
    def fail(rows):
        if any(e['event_type']=='human_asked' for e in rows):raise RuntimeError('injected event failure')
        return record(rows)
    monkeypatch.setattr(repo,'record_events',fail)
    Runner(_settings(tmp_path),repo,exec_fn=_fake_exec('',permission_refusal='담당자 확인')).poll_once()
    wi=diagnose(repo,inst)
    assert wi['draft_status']=='FAILED' and wi['consumer'] is None
    assert not repo.notifications
    assert any(e['event_type']=='error' for e in repo.list_events(todo_id=wi['id']))


def test_resume_uses_durable_session_when_pending_file_is_missing(tmp_path):
    repo,inst=_repo();requests=[]
    r=Runner(_settings(tmp_path),repo,exec_fn=_fake_exec('',permission_refusal='담당자 확인',requests=requests))
    r.poll_once();wi=diagnose(repo,inst)
    question=next(e for e in repo.list_events(todo_id=wi['id']) if e['event_type']=='human_asked')
    hitl.clear(workspace.for_run(tmp_path,wi['id'],tenant_id='hyd').path)
    repo.update_workitem(wi|dict(feedback={'human_answer':'MCP만 사용','job_id':question['job_id']},draft_status='FB_REQUESTED'))
    r.exec_fn=_fake_exec(json.dumps(dict(cause='c',failure_mode='f',guide_card={'ok':True})),requests=requests)
    r.poll_once()
    assert requests[-1][0].resume_session=='sess-A'
    assert diagnose(repo,inst)['status']=='SUBMITTED'


def test_business_question_pauses_without_faking_form_output(tmp_path):
    repo,inst=_repo()
    control={'__human_input__':{'question':'어느 설비를 확인할까요?','options':['HYD-01','HYD-02']}}
    Runner(_settings(tmp_path),repo,exec_fn=_fake_exec(json.dumps(control))).poll_once()
    wi=diagnose(repo,inst)
    assert wi['draft_status']=='HUMAN_ASKED' and wi['status']=='IN_PROGRESS' and not wi['output']
    question=next(e for e in repo.list_events(todo_id=wi['id']) if e['event_type']=='human_asked')
    assert question['data']['options']==['HYD-01','HYD-02']


@pytest.mark.parametrize('value',[
    {'__human_input__':{'question':''}},
    {'__human_input__':{'question':'ask','permission':'write'}},
    {'__human_input__':{'question':'ask','options':[1]}},
    {'__human_input__':{'question':'ask'},'cause':'invented'},
])
def test_invalid_question_control_is_not_silently_accepted(value):
    with pytest.raises(ValueError):hitl.business_question(json.dumps(value))
