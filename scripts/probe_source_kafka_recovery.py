"""Actual Kafka receipts + process SIGKILL/restart, preserving every test record."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import psycopg
from psycopg.rows import dict_row
from probe_alert_triage import publish
from scenario_instance_test import get,post,PROCESS,variables


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True)
    ap.add_argument('--stages',nargs='+',choices=['receipt','claimed','incident','instance'],default=['receipt','claimed','incident','instance'])
    args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False);checks=[];ids=[]
    dsn=os.environ['SUPABASE_DSN']
    def save(name,x):(out/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    def check(name,ok,detail=None):
        checks.append({'name':name,'passed':bool(ok),'detail':detail});save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    def until(fn,seconds=90):
        end=time.monotonic()+seconds;error=None
        while time.monotonic()<end:
            try:
                v=fn()
                if v:return v
            except Exception as e:error=str(e)
            time.sleep(.5)
        raise TimeoutError(str(error or 'condition not observed'))
    def rows(aid):
        with psycopg.connect(dsn,row_factory=dict_row) as c:
            return c.execute("select * from process_source_inbox where tenant_id='hyd' and payload->>'alertId'=%s order by id",(aid,)).fetchall()
    def instance(aid):
        with psycopg.connect(dsn,row_factory=dict_row) as c:
            return c.execute("select * from bpm_proc_inst where tenant_id='hyd' and start_event_id=%s",(aid,)).fetchall()
    def stopped():
        r=subprocess.run(['docker','kill','hyd-iot-edu-process-1'],capture_output=True,text=True,timeout=30,check=True)
        return {'command':'docker kill process','stdout':r.stdout,'exit_code':r.returncode}
    def started():
        subprocess.run(['docker','start','hyd-iot-edu-process-1'],capture_output=True,text=True,timeout=30,check=True)
        return until(lambda:get(PROCESS+'/healthz').get('ok'),90)
    def reviewed(aid):
        inst,=instance(aid);view=get(PROCESS+'/api/instances/'+inst['proc_inst_id'])
        task=next(w for w in view['workitems'] if w['status']=='IN_PROGRESS')
        assert task['activity_id']=='task:triage'
        answer=post(PROCESS+'/api/todolist/'+task['id']+'/submit',{'by':'A033 Kafka 복구 검증',
            'output':{'note':'시험 Kafka 원문/재시작/중복/충돌 확인. 실제 설비 조치나 회복 승인 아님.'}})
        check(aid+': human review accepted',not answer.get('error'))
        return get(PROCESS+'/api/instances/'+inst['proc_inst_id'])
    try:
        until(lambda:get(PROCESS+'/healthz').get('ok'))
        mode=get(PROCESS+'/api/process/mode');save('mode',mode)
        check('instance20x legacy baseline',mode['mode']=='instance' and mode['time_scale']==20 and mode['agent_bridge']=='legacy')
        for stage in args.stages:
            aid='A033-'+stage+'-'+uuid.uuid4().hex[:10];ids.append(aid)
            alert={'asset':'HYD-02','alertId':aid,'state':'RAISE','pattern':'UNSUPPORTED_A033',
                   't':datetime.now(timezone.utc).isoformat(),'evidence':{'test_stage':stage,'original':[1,2,3]}}
            lock=psycopg.connect(dsn,autocommit=False);receipt_lock=None
            try:
                if stage=='receipt':
                    key=json.dumps(['source-scheduler','hyd'])
                    lock.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',(key,))
                elif stage=='claimed':
                    key=json.dumps(['hyd','alert_triage',aid])
                    lock.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',(key,))
                else:lock.execute('lock table bpm_proc_inst in share mode')
                save(stage+'-publish',publish(alert))
                receipt=until(lambda:next((r for r in rows(aid) if r['parent_id'] is None),None))
                if stage=='receipt':check(stage+': committed before handling',receipt['status']=='PENDING' and not instance(aid))
                else:
                    receipt=until(lambda:next((r for r in rows(aid) if r['status']=='CLAIMED'),None))
                    check(stage+': durable claim observed',bool(receipt['claim_token']) and receipt['attempts']==1)
                if stage in ('incident','instance'):
                    inc=until(lambda:next((i for i in get(PROCESS+'/api/incidents') if i['alertId']==aid),None))
                    save(stage+'-partial-incident',inc)
                    check('Incident exists before blocked PG instance insertion',not instance(aid) and not inc['cmdId'])
                if stage=='instance':
                    # Keep this receipt's completion update blocked, then let
                    # the real instance transaction commit before SIGKILL.
                    receipt_lock=psycopg.connect(dsn,autocommit=False)
                    receipt_lock.execute('select id from process_source_inbox where id=%s for update',(receipt['id'],))
                    lock.rollback()
                    saved=until(lambda:instance(aid))
                    still=rows(aid)
                    save('instance-before-kill',saved)
                    check('PG instance committed before blocked receipt completion',len(saved)==1
                          and still[0]['status']=='CLAIMED' and still[0]['result'] is None)
                save(stage+'-before',rows(aid));save(stage+'-kill',stopped())
            finally:
                lock.rollback();lock.close()
                if receipt_lock is not None:receipt_lock.rollback();receipt_lock.close()
            started()
            handled=until(lambda:next((r for r in rows(aid) if r['status']=='HANDLED'),None),130)
            save(stage+'-after',rows(aid));insts=instance(aid)
            check(stage+': same receipt recovered to exactly one instance',handled['id']==receipt['id'] and len(insts)==1
                  and handled['payload']==alert and handled['policy']['target']=={'definition':'alert_triage','version':'1.0'})
            if stage!='receipt':check(stage+': expired owner recorded and token replaced',handled['attempts']==2 and handled['failures']==1
                and any(h['event']=='lease_expired' for h in handled['history']))
            incs=[i for i in get(PROCESS+'/api/incidents') if i['alertId']==aid]
            incs=[get(PROCESS+'/api/incidents/'+i['id']) for i in incs]
            check(stage+': one original incident with no physical action',len(incs)==1 and incs[0]['cmdId'] is None
                  and incs[0]['card']['alert']==alert)
            publish(alert);publish(dict(alert,evidence={'test_stage':'conflicting payload'}))
            until(lambda:len(rows(aid))==3)
            check(stage+': Kafka duplicate and conflict remain separate receipts',[r['status'] for r in rows(aid)]==['HANDLED','DUPLICATE','CONFLICT'])
            publish(dict(alert,state='CLEAR'))
            until(lambda:any(r['kind']=='CLEAR' and r['status']=='HANDLED' for r in rows(aid)))
            check(stage+': CLEAR correlates without changing unsupported recovery',get(PROCESS+'/api/incidents/'+incs[0]['id'])['state']=='ESCALATED')
            save(stage+'-final',reviewed(aid));save(stage+'-receipts',rows(aid))
        save('health',get(PROCESS+'/healthz'))
    finally:
        save('result',{'checks':checks,'alert_ids':ids,'scope':'actual Kafka, PostgreSQL, SQLite, process SIGKILL/restart and HTTP; no Codex, no physical command'})
    print(f'{len(checks)}/{len(checks)} passed',flush=True)


if __name__=='__main__':main()
