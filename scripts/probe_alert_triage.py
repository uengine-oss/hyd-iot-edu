"""A032 actual Kafka/PLC/PG/SQLite path. No Codex worker or inferred recovery.

Injects one unknown Kafka alarm and three simulator faults, records raw inputs,
completes only human triage work, then restores the plant fixture.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
import traceback
import uuid

from scenario_instance_test import get, post, wait_for, variables, PROCESS, PLANT, DETECTOR

AGENT='http://127.0.0.1:8091'
CHECKS=[]
OUT=None


def save(name,value):
    (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def check(name,condition,detail=None):
    CHECKS.append({'name':name,'passed':bool(condition),'detail':detail})
    print(('PASS ' if condition else 'FAIL ')+name,flush=True)
    save('checks',CHECKS)
    if not condition:raise AssertionError(name)


def until(fn,timeout=45):
    result,_=wait_for(fn,timeout,every=.5)
    if not result:raise TimeoutError('condition was not observed')
    return result


def publish(alert):
    code="""import asyncio,json,sys
from hydcommon.kafka import producer
from hydcommon import topics
async def main():
    event=json.load(sys.stdin);p=await producer()
    try:
        receipt=await p.send_and_wait(topics.K_ALERTS,key=topics.asset_key(event['asset']),value=event)
        print(json.dumps({'topic':receipt.topic,'partition':receipt.partition,'offset':receipt.offset}))
    finally:await p.stop()
asyncio.run(main())
"""
    result=subprocess.run(['docker','exec','-i','hyd-iot-edu-agent-1','python','-c',code],
        input=json.dumps(alert),text=True,capture_output=True,timeout=30,check=True)
    return json.loads(result.stdout)


def incidents():return get(PROCESS+'/api/incidents')


def find_instance(alert_id):
    return next((i for i in get(PROCESS+'/api/instances?limit=500') if variables(i).get('alert_id')==alert_id),None)


def inspect_case(label,inc,raw=None):
    inc=get(PROCESS+'/api/incidents/'+inc['id'])
    aid=inc['alertId'];inst=until(lambda:find_instance(aid));pid=inst['proc_inst_id']
    view=get(PROCESS+'/api/instances/'+pid);save(label+'-instance',view);save(label+'-incident',inc)
    check(label+': pinned human review',inst['proc_def_id']=='alert_triage' and inst['proc_def_version']=='1.0',pid)
    check(label+': no assumed recovery',inc['state']=='ESCALATED' and inc['reason']=='UNSUPPORTED_ALERT_PATTERN'
          and inc['recoveryPolicy']['criterion'] is None and not inc['cmdId'] and not inc['workOrder'])
    task=next(w for w in view['workitems'] if w['status']=='IN_PROGRESS')
    check(label+': human task only',task['activity_id']=='task:triage' and not task.get('agent_mode')
          and not task.get('agent_orch') and not view['events'])
    form=get(PROCESS+'/api/todolist/'+task['id']);save(label+'-form',form)
    check(label+': source event presented unchanged',form['inputs']['alert']==(raw or inc['card']['alert']))
    run=until(lambda:next((r for r in get(AGENT+'/api/agent/runs') if r['alertId']==aid and r['status']!='RUNNING'),None))
    full=get(AGENT+'/api/agent/runs/'+run['id']);save(label+'-agent',full)
    check(label+': legacy agent withheld before inference',run['status']=='WITHHELD'
          and [s['name'] for s in full['steps']]==['alert_policy'] and full['card'] is None)
    return inst,task


def complete_review(label,inst,task,inc):
    response=post(PROCESS+'/api/todolist/'+task['id']+'/submit',
        {'by':'A032 현장검토 시험','output':{'note':'원천 경보와 PLC 사유 확인. 시험 주입 복구. 이 기록은 실제 회복 승인/설비 명령이 아님.'}})
    check(label+': human review accepted',not response.get('error'),response.get('error'))
    final=get(PROCESS+'/api/instances/'+inst['proc_inst_id']);saved=get(PROCESS+'/api/incidents/'+inc['id'])
    save(label+'-final',final);save(label+'-final-incident',saved)
    check(label+': review end is not physical recovery',final['instance']['end_event']=='ev:review-recorded'
          and final['instance']['status']=='COMPLETED' and saved['state']=='ESCALATED'
          and not saved['cmdId'] and not saved['workOrder'] and variables(final['instance']).get('recovered') is not True)
    projection=get(PROCESS+'/api/instances/'+inst['proc_inst_id']+'/graph');save(label+'-graph',projection)
    graph=projection.get('graph') or {}
    check(label+': graph links actual process incident asset and completed task',
          graph.get('process',{}).get('id')=='proc:alert-triage' and graph.get('incident')==inc['id']
          and graph.get('asset')==saved['asset'] and not graph.get('warnings')
          and graph.get('instance',{}).get('end_event')=='ev:review-recorded'
          and len(graph.get('workitems',[]))==1 and graph['workitems'][0]['status']=='DONE')


def main():
    global OUT
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    OUT=Path(args.out);OUT.mkdir(parents=True,exist_ok=False)
    save('scope',{'started':datetime.now(timezone.utc).isoformat(),
        'scope':'actual local Kafka, simulator PLC, detector, process PG/SQLite, legacy agent and human form HTTP; no Codex/no browser'})
    existing={i['id'] for i in incidents()};save('before-plant',get(PLANT+'/api/state'))
    try:
        for base in (PROCESS,AGENT,DETECTOR,PLANT):until(lambda:get(base+'/healthz'),60)
        mode=get(PROCESS+'/api/process/mode');save('mode',mode)
        check('instance mode / legacy bridge',mode['mode']=='instance' and mode['agent_bridge']=='legacy',mode)
        raw={'alertId':'A032-UNKNOWN-'+uuid.uuid4().hex[:12],'asset':'HYD-01','pattern':'UNRECOGNIZED_SOURCE_ALARM',
             'state':'RAISE','severity':'CRITICAL','t':datetime.now(timezone.utc).isoformat(),
             'evidence':{'trip':'UNRECOGNIZED_SOURCE_CAUSE','source_note':'A032 Kafka fixture, preserved verbatim'}}
        save('unknown-source',raw);save('unknown-kafka',publish(raw))
        inc=until(lambda:next((i for i in incidents() if i['alertId']==raw['alertId']),None))
        inst,task=inspect_case('unknown',inc,raw)
        save('duplicate-kafka',publish(raw));time.sleep(2)
        check('duplicate RAISE has one incident/instance',len([i for i in incidents() if i['alertId']==raw['alertId']])==1
              and len([i for i in get(PROCESS+'/api/instances?limit=500') if variables(i).get('alert_id')==raw['alertId']])==1)
        card=post(PROCESS+'/api/incidents',{'alert':raw,'recommended':[{'code':'RESET','kind':'command'}]})
        check('late guide cannot upgrade review',card.get('duplicate') and card.get('state')=='ESCALATED',card)
        decision=post(PROCESS+'/api/decisions',{'id':raw['alertId'],'asset':raw['asset'],
            'origin':{'incident':inc['id']},'options':[{'id':'reset','actions':[{'code':'RESET'}]}]})
        check('late decision rejected',decision.get('error')==409,decision)
        subprocess.run(['docker','kill','hyd-iot-edu-process-1'],check=True,timeout=30,capture_output=True)
        subprocess.run(['docker','start','hyd-iot-edu-process-1'],check=True,timeout=30,capture_output=True)
        until(lambda:get(PROCESS+'/healthz'),60)
        restored=get(PROCESS+'/api/incidents/'+inc['id']);save('unknown-restored',restored)
        check('restart preserves review identity and no recovery criterion',restored['recoveryPolicy']==inc['recoveryPolicy']
              and restored['state']=='ESCALATED' and find_instance(raw['alertId'])['proc_inst_id']==inst['proc_inst_id'])
        complete_review('unknown',inst,task,restored)

        post(PLANT+'/api/reset');time.sleep(2)
        # Physical sources: pressure loss, fan bearing wear at full fan, and heat loss.
        post(PLANT+'/api/manual',{'asset':'HYD-03','writes':{'FanSpeedSP':100}})
        for asset,kind,target in [('HYD-01','cooler_degradation',0),('HYD-02','pump_leakage',.8),('HYD-03','fan_vibration',.8)]:
            result=post(PLANT+'/api/fault',{'asset':asset,'type':kind,'target':target,'ramp_sim_s':1})
            check(asset+': physical fault injected',not result.get('error'),result)
        cases=[]
        for asset,pattern,reason in [('HYD-02','LOW_PRESSURE_TRIP','LOW_PRESSURE'),('HYD-03','HIGH_VIBRATION_TRIP','HIGH_VIBRATION'),('HYD-01','OVERHEAT_TRIP','OVERTEMP')]:
            inc=until(lambda:next((i for i in incidents() if i['id'] not in existing and i['asset']==asset
                      and (i.get('recoveryPolicy') or {}).get('pattern')==pattern),None),90)
            inc=get(PROCESS+'/api/incidents/'+inc['id'])
            plant=get(PLANT+'/api/state');save(pattern+'-plant',plant)
            check(pattern+': actual PLC cause preserved',inc['card']['alert']['evidence']['trip']==reason
                and plant['units'][asset]['status']['trip']==reason,inc['card']['alert'])
            inst,task=inspect_case(pattern,inc);cases.append((pattern,inc,inst,task))
        save('detector-trip',get(DETECTOR+'/api/detector/state'))
        post(PLANT+'/api/reset')
        for label,inc,inst,task in cases:
            cleared=until(lambda:(lambda row:row if row['cleared'] else None)(get(PROCESS+'/api/incidents/'+inc['id'])))
            check(label+': source CLEAR does not mean recovered',cleared['state']=='ESCALATED' and not cleared['cmdId'])
            log=subprocess.run(['docker','logs','--since','10m','hyd-iot-edu-detector-1'],
                 capture_output=True,text=True,timeout=20,check=True)
            lines=log.stdout+log.stderr
            (OUT/'detector.log').write_text(lines,encoding='utf-8')
            check(label+': CLEAR preserves source pattern and ID',f"ALERT CLEAR {label} {inc['alertId']}" in lines)
            complete_review(label,inst,task,cleared)
        save('detector-restored',get(DETECTOR+'/api/detector/state'))
    except Exception:
        save('error',{'traceback':traceback.format_exc()});raise
    finally:
        save('all-new-incidents',[i for i in incidents() if i['id'] not in existing])
        save('plant-restored',post(PLANT+'/api/reset'))
        save('checks',CHECKS)
    print(f'{sum(c["passed"] for c in CHECKS)}/{len(CHECKS)} checks passed',flush=True)


if __name__=='__main__':main()
