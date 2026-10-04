import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from procsvc import task_deferral as deferred
from test_worker import _repo, _settings, _fake_exec
from worker.runner import Runner


ASSESSMENT = {'status':'UNSUPPORTED', 'reason':'현재 2분 평균이 진단 조건을 만족하지 않습니다.',
              'evidence':{'evd:ps1-low':{'status':'FAIL','value':180.3,'threshold':165}}}


def claimed():
    repo, inst = _repo()
    row = repo.fetch_pending_task('cliagents','owner:old',tenant_id='hyd')[0]
    return repo, inst, row


def hold(repo, row, **kw):
    return deferred.defer(repo,'hyd',row['id'],expected_consumer='owner:old',
                          request_id='attempt-1',assessment=ASSESSMENT,**kw)


def retry(repo, row, **kw):
    args=dict(deferral_id='attempt-1',request_id='retry-1',by='운전원',reason='센서 구간을 다시 관측합니다')
    return deferred.reassess(repo,'hyd',row['id'],**(args|kw))


def test_deferral_persists_reason_without_business_output_or_next_tasks():
    repo, inst, row = claimed();receipt=hold(repo,row)
    wi=repo.get_workitem(row['id'])
    assert wi['status']=='PENDING' and wi['consumer'] is None and wi['output'] is None
    assert wi['draft']['_deferral']['assessment']==ASSESSMENT
    assert not repo.fetch_pending_task('cliagents','other',tenant_id='hyd')
    assert not repo.claim_submitted('engine',tenant_id='hyd')
    assert receipt['id']=='attempt-1'
    assert len([e for e in repo.list_events(todo_id=row['id']) if e['event_type']=='task_deferred'])==1


def test_atomic_deferral_rolls_back_when_event_persistence_fails(monkeypatch):
    repo, inst, row=claimed()
    monkeypatch.setattr(repo,'record_events',lambda *_: (_ for _ in ()).throw(OSError('disk')))
    with pytest.raises(OSError):hold(repo,row)
    assert repo.get_workitem(row['id'])==row


def test_duplicate_receipt_and_conflicting_reuse_are_distinct():
    repo, inst, row=claimed();first=hold(repo,row)
    assert hold(repo,row)==first
    with pytest.raises(ValueError,match='different'):
        deferred.defer(repo,'hyd',row['id'],expected_consumer='owner:old',request_id='attempt-1',
                       assessment=ASSESSMENT|{'reason':'different'})
    assert len(repo.list_events(todo_id=row['id']))==1


def test_reassessment_is_durable_new_claim_and_fences_late_old_output():
    repo, inst, row=claimed();hold(repo,row)
    first=retry(repo,row)
    assert retry(repo,row)==first
    wi=repo.get_workitem(row['id'])
    assert wi['status']=='IN_PROGRESS' and wi['draft'] is None and wi['draft_status'] is None
    assert wi['feedback']['reassessment']['deferral_id']=='attempt-1'
    new=repo.fetch_pending_task('cliagents','owner:new',tenant_id='hyd')[0]
    assert not repo.save_task_result(row['id'],{'cause':'stale'},True,expected_consumer='owner:old')
    assert repo.save_task_result(new['id'],{'cause':'fresh'},True,expected_consumer='owner:new')
    assert repo.get_workitem(row['id'])['output']=={'cause':'fresh'}
    assert len(repo.list_events(todo_id=row['id']))==2


def test_reassessment_double_click_never_queues_two_attempts():
    repo, inst, row=claimed();hold(repo,row)
    def one(n):
        try:return retry(repo,row,request_id='request-'+str(n))
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(one,[1,2]))
    assert sum(r is not None for r in results)==1
    assert len(repo.fetch_pending_task('cliagents','owner:new',limit=2,tenant_id='hyd'))==1


def test_reassessment_event_failure_keeps_pending_evidence(monkeypatch):
    repo,inst,row=claimed();hold(repo,row);before=repo.get_workitem(row['id'])
    monkeypatch.setattr(repo,'record_events',lambda *_: (_ for _ in ()).throw(OSError('disk')))
    with pytest.raises(OSError):retry(repo,row)
    assert repo.get_workitem(row['id'])==before
    assert len(repo.list_events(todo_id=row['id']))==1


def test_retry_id_conflict_and_ordinary_pending_are_not_accepted():
    repo,inst,row=claimed();hold(repo,row);retry(repo,row)
    with pytest.raises(ValueError,match='different'):retry(repo,row,reason='changed request')
    row=repo.get_workitem(row['id']);row.update(status='PENDING',draft=None);repo.update_workitem(row)
    with pytest.raises(ValueError,match='not waiting'):retry(repo,row,request_id='new')


def test_late_deferral_cannot_replace_new_waiting_reason():
    repo, inst, row=claimed();hold(repo,row);retry(repo,row)
    repo.fetch_pending_task('cliagents','owner:new',tenant_id='hyd')
    deferred.defer(repo,'hyd',row['id'],expected_consumer='owner:new',request_id='attempt-2',assessment=ASSESSMENT)
    assert hold(repo,row)['id']=='attempt-1'  # acknowledgement only, no mutation
    assert repo.get_workitem(row['id'])['draft']['_deferral']['id']=='attempt-2'
    with pytest.raises(ValueError):retry(repo,row,request_id='retry-new')


@pytest.mark.parametrize('mode',['tenant','cancel','generation','consumer'])
def test_stale_or_foreign_work_cannot_be_deferred(mode):
    repo,inst,row=claimed()
    if mode=='tenant':row['tenant_id']='other';repo.update_workitem(row)
    elif mode=='cancel':row['status']='CANCELLED';repo.update_workitem(row)
    elif mode=='generation':inst['rework_generation']=1;repo.update_instance(inst)
    else:row['consumer']='someone-else';repo.update_workitem(row)
    with pytest.raises((ValueError,KeyError)):hold(repo,row)
    assert not repo.list_events(todo_id=row['id'])


@pytest.mark.parametrize('assessment',[
    {'status':'SUPPORTED','reason':'ok','evidence':{}},
    {'status':'UNKNOWN','reason':'','evidence':{}},
    {'status':'UNKNOWN','reason':'x','evidence':{'value':float('nan')}},
    {'status':'UNKNOWN','reason':'x','evidence':{},'cause':'invented'},
])
def test_invalid_deferral_is_not_a_completed_form(assessment):
    with pytest.raises(ValueError):deferred.validate(assessment)


def test_worker_defers_then_reassesses_in_a_fresh_execution(tmp_path):
    repo,inst=_repo();requests=[]
    runner=Runner(_settings(tmp_path),repo,exec_fn=_fake_exec(json.dumps({'__deferred__':ASSESSMENT}),requests=requests))
    runner.poll_once()
    wi=next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='task:diagnose')
    assert wi['status']=='PENDING' and not wi['output']
    receipt=wi['draft']['_deferral']
    deferred.reassess(repo,'hyd',wi['id'],deferral_id=receipt['id'],request_id='retry',by='운전원',reason='새 관측 확인')
    runner.exec_fn=_fake_exec(json.dumps({'cause':'c','failure_mode':'f','guide_card':{'ok':True}}),requests=requests)
    runner.poll_once()
    assert requests[-1][0].resume_session is None
    assert '새 관측 확인' in requests[-1][0].prompt
    assert repo.get_workitem(wi['id'])['status']=='SUBMITTED'
    assert not any(e['event_type']=='task_completed' for e in repo.list_events(todo_id=wi['id'])[:-1])


def test_deferral_control_cannot_mix_an_answer():
    with pytest.raises(ValueError):deferred.control(json.dumps({'__deferred__':ASSESSMENT,'cause':'invented'}))


def test_http_reassessment_returns_receipt_and_rejects_stale_request(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from procsvc import engine, instances, instance_mode
    from test_worker import DEF_PATH
    repo,inst,row=claimed();hold(repo,row)
    rt=instances.InstanceRuntime(repo,engine.Definition.load(DEF_PATH),instances.Hooks())
    monkeypatch.setattr(instance_mode,'_runtime',rt)
    app=FastAPI();instance_mode.mount(app,'instance');client=TestClient(app)
    payload=dict(deferral_id='attempt-1',request_id='http-retry',by='운전원',reason='새 관측')
    response=client.post(f"/api/todolist/{row['id']}/reassess",json=payload)
    assert response.status_code==200 and response.json()['status']=='QUEUED'
    assert client.post(f"/api/todolist/{row['id']}/reassess",json=payload).json()==response.json()
    assert client.post(f"/api/todolist/{row['id']}/reassess",json=payload|{'request_id':'another'}).status_code==409
    assert client.post('/api/todolist/unknown/reassess',json=payload).status_code==404
