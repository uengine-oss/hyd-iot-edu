"""Actual PG transactions/RPCs and local HTTP ASGI; fixture results, no AI/PLC actions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/process'),str(ROOT/'common')]
import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from procsvc import engine,instances,instance_mode,procdb,task_deferral

DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'
ASSESSMENT={'status':'UNKNOWN','reason':'[회귀 검사] 명시 시험: 원천에 관측값 없음',
            'evidence':{'fixture-source':{'status':'UNKNOWN','value':None}}}


def runtime(meta):
    return instances.InstanceRuntime(procdb.PgRepo(DSN),engine.Definition.from_dict(meta['definition']),
                                     instances.Hooks(),tenant_id=meta['tenant'],time_scale=1)


def defer(rt,meta):
    return task_deferral.defer(rt.repo,meta['tenant'],meta['wid'],expected_consumer='fixture:old',
                              request_id='attempt-1',assessment=ASSESSMENT)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--crash');args=ap.parse_args()
    out=Path(args.out)
    if args.crash:
        meta=json.loads((out/'fixture.json').read_text(encoding='utf8'));rt=runtime(meta)
        if args.crash=='before-commit':
            original=rt.repo.record_events
            def terminate(rows):original(rows);os._exit(73)
            rt.repo.record_events=terminate
        defer(rt,meta);os._exit(74)
    out.mkdir(parents=True,exist_ok=False);checks=[]
    def save(name,value):(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)});save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    raw=json.loads((ROOT/'docs/examples/rework-inspection-v1.json').read_text(encoding='utf8'))
    raw['roles'].append({'name':'Agent','endpoint':'sys:agent'})
    raw['activities'][0].update(type='userTask',role='Agent',agentMode='COMPLETE',orchestration='cliagents')
    tenant='defer-'+uuid.uuid4().hex[:10]
    with psycopg.connect(DSN,connect_timeout=5) as c:
        c.execute('insert into tenants(id,name) values(%s,%s)',(tenant,'[회귀 검사] A058 보존 격리 시험'))
    meta=dict(tenant=tenant,definition=raw);rt=runtime(meta)
    inst=rt.start_definition(raw['processDefinitionId'],'1',str(uuid.uuid4()),{'score':2})
    row=rt.repo.fetch_pending_task('cliagents','fixture:old',tenant_id=tenant,proc_inst_id=inst['proc_inst_id'])[0]
    meta.update(pid=inst['proc_inst_id'],wid=row['id']);save('fixture',meta);save('before',row)
    for phase,code in [('before-commit',73),('after-commit',74)]:
        child=subprocess.run([sys.executable,__file__,'--out',str(out),'--crash',phase],capture_output=True,timeout=40)
        save(phase,dict(exit=child.returncode,stderr=child.stderr.decode('utf8',errors='replace')))
        fresh=rt.repo.get_workitem(row['id'])
        if phase=='before-commit':
            check('actual child exit before commit rolls back state and event',child.returncode==code and fresh==row
                  and rt.repo.find_task_event(row['id'],'deferral:attempt-1','task_deferred') is None)
        else:check('actual child exit after commit leaves durable PENDING evidence',child.returncode==code
                   and fresh['status']=='PENDING' and fresh['draft']['_deferral']['assessment']==ASSESSMENT)
    restarted=runtime(meta)
    check('new PG runtime reads and acknowledges exact committed deferral',defer(restarted,meta)==rt.repo.get_workitem(row['id'])['draft']['_deferral'])
    check('pending assessment is not claimable or submitted for completion',
          not rt.repo.fetch_pending_task('cliagents','wrong',tenant_id=tenant,proc_inst_id=meta['pid'])
          and not rt.repo.claim_submitted('engine',tenant_id=tenant))
    payload=dict(deferral_id='attempt-1',request_id='explicit-retry',by='[회귀 검사] PG 시험 검토자',reason='[회귀 검사] 원천 결과를 새로 읽기')
    def repeat(_):
        own=runtime(meta)
        return task_deferral.reassess(own.repo,tenant,row['id'],**payload)
    with ThreadPoolExecutor(max_workers=4) as pool:receipts=list(pool.map(repeat,range(4)))
    save('reassessment',receipts[0])
    check('four concurrent requests queue one fresh assessment',all(r==receipts[0] for r in receipts)
          and len([e for e in rt.repo.list_events(todo_id=row['id']) if e['event_type']=='task_reassessment_requested'])==1)
    instance_mode._runtime=runtime(meta);app=FastAPI();instance_mode.mount(app,'instance');client=TestClient(app)
    response=client.post(f"/api/todolist/{row['id']}/reassess",json=payload)
    check('HTTP API replays durable receipt after reconnect',response.status_code==200 and response.json()==receipts[0])
    check('HTTP new request cannot duplicate an active reassessment',client.post(f"/api/todolist/{row['id']}/reassess",json=payload|{'request_id':'other'}).status_code==409)
    fresh=rt.repo.fetch_pending_task('cliagents','fixture:new',tenant_id=tenant,proc_inst_id=meta['pid'])[0]
    check('late old worker result cannot overwrite new attempt',not rt.repo.save_task_result(row['id'],{'score':999},True,expected_consumer='fixture:old'))
    check('late duplicate deferral is only acknowledged',defer(runtime(meta),meta)['id']=='attempt-1'
          and rt.repo.get_workitem(row['id'])['consumer']=='fixture:new')
    check('fresh worker RPC submits labelled fixture result',rt.repo.save_task_result(row['id'],{'score':7},True,expected_consumer='fixture:new'))
    rt.poll_once()
    current=engine._by_activity(rt.repo.list_workitems(proc_inst_id=meta['pid'],limit=None))
    check('only fresh result advances dependent work',current['check']['status']=='IN_PROGRESS'
          and current['check']['reference_ids']==[row['id']]
          and engine.variables(rt.repo.get_instance(meta['pid']))['score']==7)
    rt.submit(current['check']['id'],{'score':8},by='[회귀 검사] PG 시험 검토자')
    current=engine._by_activity(rt.repo.list_workitems(proc_inst_id=meta['pid'],limit=None))
    rt.submit(current['finish']['id'],{'note':'[회귀 검사] 보류와 재평가 시험 완료'},by='[회귀 검사] PG 시험 검토자')
    final=rt.instance_view(meta['pid']);save('final',final)
    check('retained isolated fixture completes with both assessment receipts',final['instance']['status']=='COMPLETED'
          and rt.repo.find_task_event(row['id'],'deferral:attempt-1','task_deferred') is not None
          and rt.repo.find_task_event(row['id'],'reassessment:explicit-retry','task_reassessment_requested') is not None)
    save('result',dict(scope=__doc__,fixture=meta,checks=checks));print(f'{len(checks)}/{len(checks)} passed',flush=True)


if __name__=='__main__':main()
