"""Real stack changed-action review, denial boundaries and PLC/CMMS outcome.

Runs through the configured legacy agent bridge, never claims a Codex run.
Only this run's simulator fault and human work item are changed. Evidence is
written before cleanup; plant restoration still runs if evidence capture fails.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import scenario_instance_test as s


def main(destination,restart_after_review=False):
    out=Path(destination);out.mkdir(parents=True,exist_ok=False)
    report={'checks':[],'agent_path':'legacy bridge'};pid=None
    def save(name,value):
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    def check(name,ok,detail=None):
        report['checks'].append(dict(name=name,passed=bool(ok),detail=detail));save('report',report)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    def require(name,ok,detail=None):
        check(name,ok,detail)
        if not ok:raise RuntimeError(name)
    try:
        mode=s.get(s.PROCESS+'/api/process/mode');save('mode',mode)
        require('instance / legacy bridge is explicit',mode['mode']=='instance' and mode['agent_bridge']=='legacy')
        s.post(s.PLANT+'/api/reset');time.sleep(2)
        s.post(s.PLANT+'/api/fault',{'asset':'HYD-01','type':'cooler_degradation'})
        report['time_scale']=mode['time_scale'];factor=20/max(float(mode['time_scale']),1)
        raised,_=s.wait_for(lambda:(v if (v:=s.get(s.DETECTOR+'/api/detector/state')['assets'].get('HYD-01',{})).get('phase')=='RAISED' else None),200*factor)
        require('real cooler alert raised',bool(raised))
        inst,_=s.wait_for(lambda:s.instance_for(raised['alert_id']),30);require('instance created',bool(inst))
        pid=inst['proc_inst_id'];report['instance']=pid
        rows,_=s.wait_for(lambda:(v if (v:=s.items(pid)).get('task:select',{}).get('status')=='IN_PROGRESS' else None),120)
        require('four agent tasks reach human choice',rows and all(rows[a]['status']=='DONE' for a in s.AGENT_TASKS))
        before=s.view(pid);values=s.variables(before['instance']);inc=values['incident'];did=values['decision_id']
        report.update(incident=inc,decision=did);save('before-instance',before)
        original=s.get(s.PROCESS+'/api/decisions/'+did);save('original-decision',original)
        wid=rows['task:select']['id'];option='skill:fan-max-derate';base=s.PROCESS+'/api/todolist/'+wid
        params={'fan_pct':95,'load_pct':78}
        request={'decision':did,'option':option,'parameters':params}
        selection={'decision':did,'option':option,'by':'[회귀 검사] A031 검토 검사기','role':'role:prod-mgr',
                   'reason':'[회귀 검사] 현재 입력으로 팬 95% / 부하 78% 변경안을 검토함',**params}
        review=s.post(base+'/decision-preview',request,timeout=30);save('review-first',review)
        require('preview saved and grants no execution',review.get('id','').startswith('REV-') and review.get('execution_authorized') is False,review.get('error'))
        opt=review['snapshot']['options'][0]
        check('review contains original decision and exact changed actions',review['snapshot']['original_decision']==original
              and {a['param']:a['value'] for a in opt['actions'] if a.get('param') in params}==params)
        check('review source is current model with changed actions',opt['forecastContext']['actions']==opt['actions'] and bool(opt['forecastContext'].get('model_id')))
        check('preview leaves original decision, work item and command unchanged',s.get(s.PROCESS+'/api/decisions/'+did)==original
              and s.items(pid)['task:select']['status']=='IN_PROGRESS' and s.get(s.PROCESS+'/api/incidents/'+inc).get('cmdId') is None)
        invalid=s.post(base+'/decision-preview',dict(request,parameters={'plc_mode':'REMOTE_AUTO'}));save('invalid-fact-override',invalid)
        check('fact override cannot enter parameter review',invalid.get('error')==409,invalid)
        wrong=s.post(base+'/select',dict(selection,review_id=review['id'],fan_pct=94));save('wrong-value',wrong)
        check('review 95 cannot authorize 94',wrong.get('error') in (400,409),wrong)
        lower=s.post(base+'/select',dict(selection,review_id=review['id'],role='role:operator'));save('wrong-role',lower)
        check('saved review grants no role elevation',lower.get('error')==403,lower)
        other=s.post(base+'/decision-preview',dict(request,parameters={'fan_pct':70,'load_pct':90}),timeout=30);save('review-other-values',other)
        require('second changed input produces a distinct saved prediction',other.get('id')!=review['id'] and other.get('snapshot',{}).get('options',[{}])[0].get('forecast')!=opt['forecast'],other.get('error'))
        s.post(s.PLANT+'/api/mode',{'asset':'HYD-01','mode':'REMOTE_MANUAL'})
        visible,_=s.wait_for(lambda:(v if (v:=s.get(s.PROCESS+'/api/plant/HYD-01/status')).get('mode')=='REMOTE_MANUAL' else None),15)
        require('changed current mode reaches process',bool(visible))
        stale=s.post(base+'/select',dict(selection,review_id=review['id']),timeout=35);save('stale-mode',stale)
        check('old review denied under changed current conditions',stale.get('error') in (400,409),stale)
        check('all denied attempts leave selection open and no command',s.items(pid)['task:select']['status']=='IN_PROGRESS'
              and s.get(s.PROCESS+'/api/incidents/'+inc).get('cmdId') is None)
        s.post(s.PLANT+'/api/mode',{'asset':'HYD-01','mode':'REMOTE_AUTO'})
        visible,_=s.wait_for(lambda:(v if (v:=s.get(s.PROCESS+'/api/plant/HYD-01/status')).get('mode')=='REMOTE_AUTO' else None),15)
        require('remote mode restored before new review',bool(visible))
        fresh=s.post(base+'/decision-preview',request,timeout=30);save('review-current',fresh)
        require('new current review is feasible',fresh.get('snapshot',{}).get('options',[{}])[0].get('feasible') is True,fresh.get('error'))
        if restart_after_review:
            env=dict(os.environ,COMPOSE_PROFILES='ot,backbone,detect,knowledge,agent,enterprise,process,cliagents')
            for action in (['kill','-s','SIGKILL'],['start']):
                stopped=subprocess.run(['docker','compose',*action,'process'],env=env,capture_output=True,text=True,encoding='utf-8')
                (out/('process-'+action[0]+'.log')).write_text(stopped.stdout+stopped.stderr,encoding='utf-8')
                require('process '+action[0]+' exits successfully',stopped.returncode==0)
            healthy,_=s.wait_for(lambda:s.get(s.PROCESS+'/healthz'),45)
            require('process restarts without granting consent',healthy and s.items(pid)['task:select']['status']=='IN_PROGRESS'
                    and s.get(s.PROCESS+'/api/incidents/'+inc).get('cmdId') is None)
            report['review_survived_process_sigkill']=fresh['id']
        result=s.post(base+'/select',dict(selection,review_id=fresh['id']),timeout=30);save('approval-result',result)
        require('human explicitly approves current saved review',result.get('accepted') is True,result)
        ack,_=s.wait_for(lambda:(v if (v:=s.get(s.PROCESS+'/api/incidents/'+inc)).get('ack',{}).get('result')=='DONE' else None),60)
        save('ack-incident',ack)
        require('PLC acknowledges reviewed fan 95 and load 78',ack and {a.get('code'):(a.get('fan_pct') if a.get('code')=='FAN_SET' else a.get('load_pct')) for a in ack.get('actions',[])}=={'FAN_SET':95,'LOAD_SET':78},ack and ack.get('actions'))
        plant=s.get(s.PLANT+'/api/state');save('plant-after-ack',plant)
        actual=plant['units']['HYD-01']['status']
        check('physical setpoints match review after PLC ACK',actual['fan_pct']==95 and actual['load_pct']==78
              and actual['source']=='HITL',actual)
        final,_=s.wait_for(lambda:(v if (v:=s.view(pid))['instance']['status']=='COMPLETED' else None),300*factor)
        save('completed-instance',final)
        require('changed input reaches ev:closed through reobservation',final and final['instance'].get('end_event')=='ev:closed')
        approved=s.get(s.PROCESS+'/api/decisions/'+did);save('approved-decision',approved)
        check('approved decision retains review identity and original source',approved.get('review_id')==fresh['id'] and approved.get('original_decision')==original)
        snapshot=final['approvals'][0]['payload']['plan']['_snapshot']
        check('durable approval outbox uses exact reviewed snapshot',snapshot.get('review_id')==fresh['id'] and snapshot['options'][0]['actions']==fresh['snapshot']['options'][0]['actions'])
        work=next(w for w in final['workitems'] if w['activity_id']=='task:work-order')['output']['work_order']
        tx=s.get(s.ENT+'/api/transactions');save('enterprise-transactions',tx)
        check('actual CMMS receipt matches process result',work.get('ok') is True and bool(work.get('ref')) and any(t.get('ref')==work['ref'] for t in tx),work)
        reuse=s.post(base+'/select',dict(selection,review_id=fresh['id']));save('duplicate-select',reuse)
        check('completed choice cannot reuse review',reuse.get('error') in (400,409),reuse)
    finally:
        try:
            if pid:save('final-observed-instance',s.view(pid))
            save('audit',s.get(s.PROCESS+'/api/audit'))
        finally:
            save('plant-reset',s.post(s.PLANT+'/api/reset'));save('report',report)
    return 0 if report['checks'] and all(c['passed'] for c in report['checks']) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True)
    parser.add_argument('--restart-after-review',action='store_true')
    args=parser.parse_args()
    raise SystemExit(main(args.out,args.restart_after_review))
