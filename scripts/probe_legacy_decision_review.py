"""Actual legacy HITL changed-value review; separate from instance/Codex claims."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import time
import scenario_instance_test as s


def main(destination):
    out=Path(destination);out.mkdir(parents=True,exist_ok=False)
    report={'checks':[]};inc_id=None
    def save(name,value):
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    def check(name,ok,detail=None):
        report['checks'].append(dict(name=name,passed=bool(ok),detail=detail));save('report',report)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    def require(name,ok,detail=None):
        check(name,ok,detail)
        if not ok:raise RuntimeError(name)
    try:
        healthy,_=s.wait_for(lambda:s.get(s.PROCESS+'/healthz'),45)
        require('process ready before legacy requests',bool(healthy))
        mode=s.get(s.PROCESS+'/api/process/mode');save('mode',mode)
        require('legacy mode is explicit',mode['mode']=='legacy')
        # The legacy mode endpoint has no InstanceRuntime clock. Read only the
        # named public process settings, never dump the container environment.
        configured=subprocess.run(['docker','exec','hyd-iot-edu-process-1','python','-c',
          'import json,os;print(json.dumps({k:os.getenv(k) for k in ("TIME_SCALE","PROCESS_MODE")}))'],capture_output=True,text=True,check=True)
        clock=json.loads(configured.stdout);save('process-clock',clock)
        scale=float(clock['TIME_SCALE']);report['time_scale']=scale
        require('plant and process clocks match',s.get(s.PLANT+'/api/state')['time_scale']==scale)
        factor=20/max(scale,1)
        s.post(s.PLANT+'/api/reset');time.sleep(2)
        s.post(s.PLANT+'/api/fault',{'asset':'HYD-01','type':'cooler_degradation'})
        raised,_=s.wait_for(lambda:(v if (v:=s.get(s.DETECTOR+'/api/detector/state')['assets'].get('HYD-01',{})).get('phase')=='RAISED' else None),200*factor)
        require('actual cooler alert raised',bool(raised))
        inc,_=s.wait_for(lambda:next((i for i in s.get(s.PROCESS+'/api/incidents') if i.get('alertId')==raised['alert_id']),None),90)
        require('legacy incident created',bool(inc));inc_id=inc['id'];report['incident']=inc_id
        d,_=s.wait_for(lambda:next((d for d in s.get(s.PROCESS+'/api/decisions') if d.get('origin',{}).get('incident')==inc_id),None),60)
        require('legacy agent supplies pending cards',d and d['state']=='PENDING_APPROVAL')
        original=s.get(s.PROCESS+'/api/decisions/'+d['id']);save('original-decision',original);report['decision']=d['id']
        base=s.PROCESS+'/api/incidents/'+inc_id;option='skill:fan-max-derate';params={'fan_pct':95,'load_pct':78}
        review=s.post(base+'/decision-preview',{'decision':d['id'],'option':option,'parameters':params},timeout=30);save('review',review)
        require('legacy review stored with incident scope',review.get('scope',{}).get('kind')=='legacy' and review['scope']['incident']==inc_id,review.get('error'))
        check('preview preserves original and issues no command',s.get(s.PROCESS+'/api/decisions/'+d['id'])==original and s.get(base).get('cmdId') is None)
        body={'decision':d['id'],'option':option,'review_id':review['id'],'by':'A031-legacy-probe','role':'role:prod-mgr','reason':'새 예측의 변경값 검토',**params}
        wrong=s.post(base+'/decide',dict(body,fan_pct=94),timeout=35);save('wrong-value',wrong)
        check('legacy rejects a value different from saved review',wrong.get('error')==400,wrong)
        lower=s.post(base+'/decide',dict(body,role='role:operator'),timeout=35);save('wrong-role',lower)
        check('legacy review preserves required approver role',lower.get('error')==403,lower)
        result=s.post(base+'/decide',body,timeout=35);save('approval',result)
        require('legacy explicitly approves saved review',bool(result.get('cmd',{}).get('cmdId')),result.get('error'))
        ack,_=s.wait_for(lambda:(v if (v:=s.get(base)).get('ack',{}).get('result')=='DONE' else None),60);save('ack',ack)
        require('legacy changed command gets real PLC ACK',bool(ack))
        plant=s.get(s.PLANT+'/api/state');save('plant-after-ack',plant);actual=plant['units']['HYD-01']['status']
        check('actual setpoints are fan95 load78 from HITL',actual['fan_pct']==95 and actual['load_pct']==78 and actual['source']=='HITL',actual)
        final,_=s.wait_for(lambda:(v if (v:=s.get(base)).get('terminal') else None),300*factor);save('final-incident',final)
        require('legacy changed action closes after reobservation',final and final['state']=='CLOSED',final and final.get('reason'))
        approved=s.get(s.PROCESS+'/api/decisions/'+d['id']);save('approved-decision',approved)
        check('legacy preserves reviewed and original decision',approved.get('review_id')==review['id'] and approved.get('original_decision')==original)
        tx=s.get(s.ENT+'/api/transactions');save('transactions',tx)
        receipt=next((t for t in tx if t.get('decision')==d['id'] and t.get('ref')==(final.get('workOrder') or {}).get('id')),None)
        check('actual CMMS receipt matches and precedes closure',bool(receipt) and datetime.fromisoformat(final['closed'].replace('Z','+00:00'))>=datetime.fromisoformat(receipt['t'].replace('Z','+00:00')),receipt)
        repeat=s.post(base+'/decide',body,timeout=35);save('repeat',repeat)
        check('closed legacy choice cannot reuse review',repeat.get('error')==409,repeat)
    finally:
        try:
            if inc_id:save('final-observed-incident',s.get(s.PROCESS+'/api/incidents/'+inc_id))
            save('audit',s.get(s.PROCESS+'/api/audit'))
        finally:
            save('reset',s.post(s.PLANT+'/api/reset'));save('report',report)
    return 0 if report['checks'] and all(c['passed'] for c in report['checks']) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True)
    raise SystemExit(main(parser.parse_args().out))
