from concurrent.futures import ThreadPoolExecutor
from psycopg.types.json import Jsonb
import pytest

from procsvc import task_deferral
from worker.runner import Runner
from worker import workspace
from test_worker import _settings
from test_classroom_agent_api_pg import setup
from test_classroom_authority_pg import authority,DSN,KEY
from test_instances import rt

pytestmark=pytest.mark.skipif(not DSN,reason='requires disposable classroom authority PostgreSQL')


@pytest.fixture
def pending(setup,tmp_path):
    client,runtime,auth,connect,_=setup
    with connect() as db:
        policy=db.execute('SELECT policy FROM hyd_classroom_grants').fetchone()['policy']
        policy['responses']={'handover.draft':{kind:{'max_count':1,'schema':{'type':'string','enum':['실재고 확인']}}
                              for kind in ('human_answer','reassessment')}}
        db.execute('UPDATE hyd_classroom_grants SET policy=%s',(Jsonb(policy),))
    headers={'Authorization':'Bearer '+KEY}
    run=client.post('/v1/classroom/agents',headers=headers,json={
        'reference':'handover.draft','inputs':{'memo':'확인'}}).json()['run_id']
    runner=Runner(_settings(tmp_path),runtime.repo,schema_prompt='s')
    def pause():
        row=runtime.repo.fetch_pending_task('cliagents','teacher')[0]
        runner._pause(row,workspace.for_run(tmp_path,row['id'],tenant_id=runtime.tenant_id),
                      'claude-code','teacher-session','실재고를 확인했나요?','run-test',options=['실재고 확인','확인 전'])
        return runtime.repo.get_workitem(row['id'])
    return client,runtime,auth,connect,run,headers,pause


def test_answer_is_schema_bounded_idempotent_and_does_not_refresh_budget(pending):
    client,runtime,auth,connect,run,headers,pause=pending
    row=pause();base=f'/v1/classroom/agents/runs/{run}'
    value=client.get(base+'/result',headers=headers).json()
    assert value['status']=='NEEDS_INPUT' and value['question']=='실재고를 확인했나요?'
    assert value['options']==['실재고 확인','확인 전']
    before=auth.read_run(KEY,run)
    body={'kind':'human_answer','request_id':value['request_id'],'text':'실재고 확인'}
    assert client.post(base+'/respond',headers=headers,json=dict(body,text='임의 명령')).status_code==403
    assert client.post(base+'/respond',headers=headers,json=dict(body,request_id='wrong')).status_code==403
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:client.post(base+'/respond',headers=headers,json=body),range(2)))
    assert all(r.status_code==200 for r in results)
    assert sorted(r.json()['reused'] for r in results)==[False,True]
    after=auth.read_run(KEY,run)
    assert after['deadline']==before['deadline'] and after['calls']==before['calls']==0
    assert runtime.repo.get_workitem(row['id'])['draft_status']=='FB_REQUESTED'
    pause()
    newer=client.get(base+'/result',headers=headers).json()
    assert client.post(base+'/respond',headers=headers,json=dict(body,request_id=newer['request_id'])).status_code==403
    with connect() as db:db.execute("UPDATE hyd_classroom_runs SET deadline=now()-interval '1 second'")
    assert client.post(base+'/respond',headers=headers,json=body).status_code==409


def test_deferral_is_not_failed_or_success_and_reassessment_keeps_same_run(pending):
    client,runtime,auth,_,run,headers,_=pending
    row=runtime.repo.fetch_pending_task('cliagents','teacher')[0]
    assessment={'status':'UNKNOWN','reason':'실재고 확인 필요','evidence':{}}
    task_deferral.defer(runtime.repo,runtime.tenant_id,row['id'],expected_consumer=row['consumer'],request_id='deferred-1',assessment=assessment)
    base=f'/v1/classroom/agents/runs/{run}'
    value=client.get(base+'/result',headers=headers).json()
    assert value=={'status':'DEFERRED','request_id':'deferred-1','assessment':assessment,'output':None}
    assert auth.read_run(KEY,run)['state'] in ('RESERVED','RUNNING')
    response=client.post(base+'/respond',headers=headers,json={
        'kind':'reassessment','request_id':'deferred-1','text':'실재고 확인'})
    assert response.status_code==200
    current=runtime.repo.get_workitem(row['id'])
    assert current['status']=='IN_PROGRESS' and current['feedback']['reassessment']['reason']=='실재고 확인'
