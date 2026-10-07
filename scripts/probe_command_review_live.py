"""Live MES change between consent delivery and command; actual PLC/CMMS path.

The alert and first three agent outputs are explicit fixtures. Rank uses real
DMN MCP. No fresh Codex execution is claimed. Proxy forwards real assessments.
"""
import json
import argparse
from pathlib import Path
import subprocess
import sys
import time
import uuid
from urllib.error import HTTPError
import probe_incident_rework_ui as base

ROOT=base.ROOT
OUT=ROOT/'.evidence/reaudit/a046-command-live'
DEPLOY=ROOT/'.evidence/reaudit/a046-deploy'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    DEPLOY.mkdir(exist_ok=args.resume);checks=[];proxy_started=False;overridden=False
    logs=DEPLOY/('resume-'+uuid.uuid4().hex[:8]) if args.resume else DEPLOY
    logs.mkdir(exist_ok=True)
    def save(name,x):(OUT/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def read(name):return json.loads((OUT/(name+'.json')).read_text(encoding='utf8'))
    def run(command,label,timeout=180):
        result=subprocess.run(command,capture_output=True,cwd=ROOT,timeout=timeout)
        (logs/(label+'.log')).write_bytes(result.stdout+result.stderr)
        print(label,'exit',result.returncode,flush=True)
        if result.returncode:raise RuntimeError(label+' failed; see retained log')
    def phase(name,*args):run([sys.executable,str(ROOT/'scripts/probe_incident_rework_ui.py'),name,'--out',str(OUT),'--label','A046',*args],name)
    def until(fn,seconds=55):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            value=fn()
            if value:return value
            time.sleep(.5)
        raise TimeoutError('Expected real state was not reached')
    def ready():
        try:return base.request(base.PROCESS+'/healthz').get('ok')
        except (OSError,ValueError):return False
    def check(name,ok):
        checks.append(dict(name=name,passed=bool(ok)));save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    backup="import sqlite3,os; s=sqlite3.connect(os.environ.get('PROCESS_STATE_PATH','/data/process.sqlite3')); t=sqlite3.connect('/tmp/a046-before.sqlite3'); s.backup(t);t.close();s.close()"
    if not args.resume:
        run(['docker','exec','hyd-iot-edu-process-1','python','-c',backup],'backup')
        run(['docker','cp','hyd-iot-edu-process-1:/tmp/a046-before.sqlite3',str(DEPLOY/'before.sqlite3')],'copy-backup')
        run(['docker','compose','build','process'],'build')
        run(['docker','compose','up','-d','--no-deps','process'],'base-up')
    until(ready)
    try:
        if not args.resume:phase('prepare')
        state=read('state');pid=state['pid'];path=base.PROCESS+'/api/instances/'+pid
        def view():return base.request(path)
        def task(aid):return max((w for w in view()['workitems'] if w['activity_id']==aid),key=lambda w:w.get('generation') or 0)
        if args.resume:
            current=view();save('resume-observed-source',current)
            assert not current['approvals'] and task('task:rank')['status']=='DONE' and task('task:select')['status']=='IN_PROGRESS', 'Resume supports this saved pre-consent stage only'
            did=task('task:rank')['output']['decision_id']
            save('g0-decision',base.request(base.PROCESS+'/api/decisions/'+did));save('g0-view',current)
        decision=read('g0-decision');did=decision['id'];selection=task('task:select')
        with base.psycopg.connect(base.DSN) as conn:
            rows=conn.execute("select order_id,ent.hours_from_now(due_at) as due_in_h from ent.production_orders where asset='HYD-01'").fetchall()
        assert len(rows)==1 and rows[0][1] is not None
        order,due=rows[0];changed=36.0 if float(due)<24 else 2.0
        save('source-before',dict(order_id=order,due=float(due),changed_due=changed))
        save('proxy-arm',dict(decision=did))
        overlay=DEPLOY/'proxy.compose.yaml'
        overlay.write_text('''services:
  process:
    environment:
      AGENT_URL: http://a046-check-proxy:8091
  a046-check-proxy:
    image: hyd-iot-edu-process
    command: [python, /probe.py]
    networks: [it-net]
    extra_hosts: ["host.docker.internal:host-gateway"]
    volumes:
      - "'''+(ROOT/'scripts/approval_source_change_proxy.py').as_posix()+''':/probe.py:ro"
      - "'''+OUT.as_posix()+''':/evidence"
''',encoding='utf8')
        compose=['docker','compose','-f','compose.yaml','-f',str(overlay)]
        proxy_started=True;run(compose+['up','-d','--no-deps','a046-check-proxy'],'proxy-up')
        overridden=True;run(compose+['up','-d','--no-deps','process'],'process-proxy-up');until(ready)
        def consent(d,wi,label):
            options=[o for o in d['options'] if o['feasible'] and any(a.get('kind')=='command' for a in o['actions'])]
            option=next((o for o in options if o['id']==d['recommended']),options[0])
            response=base.request(base.PROCESS+'/api/todolist/'+wi['id']+'/select',dict(decision=d['id'],option=option['id'],by='A046 integration reviewer',role='role:prod-mgr'))
            save(label+'-consent',response)
            return option
        original_option=consent(decision,selection,'g0')
        stopped=until(lambda:(v if (v:=task('task:command'))['status']=='PENDING' else None));before=view();save('g0-stopped',before)
        inc=base.request(base.PROCESS+'/api/incidents/'+state['incident']);save('g0-stopped-incident',inc)
        reports=[read('proxy-check-'+str(n))['report'] for n in (1,2,3)]
        check('actual agent allowed consent and delivery then refused changed MES',reports[0]['allowed'] and reports[1]['allowed'] and not reports[2]['allowed'] and reports[2]['facts']['order_due_h']==changed)
        check('command stops once with structured original assessment',stopped['retry']==1 and any(e['job_id']=='TASK_REVIEW_REQUIRED' and e['data']['assessment']==reports[2] for e in before['events']))
        check('delivered consent has no PLC or enterprise effect',before['approvals'][0]['status']=='DELIVERED' and not inc['cmdId'] and not inc['actions'] and not inc['ack'])
        old=base.request(base.PROCESS+'/api/decisions/'+did);save('g0-approved-original',old)
        rank=task('task:rank');preview=base.request(path+'/rework-preview?workitem_id='+rank['id']);save('rework-preview',preview)
        check('real complete ledgers permit fresh judgment and consent',preview['execution_available'] and bool(preview['unissued_commands']))
        body=dict(workitem_id=rank['id'],request_id=str(uuid.uuid4()),snapshot_token=preview['snapshot_token'],by='A046 integration reviewer',role='role:prod-mgr',reason='MES changed after delivered consent; recompute judgment and request fresh consent')
        result=base.request(path+'/rework',body);save('rework-receipt',result)
        phase('rank')
        fresh=read('g1-decision');save('g1-before-consent',view())
        check('fresh DMN judgment reads changed source and sends no command',fresh['id']!=did and fresh['facts']['order_due_h']==changed and not base.request(base.PROCESS+'/api/incidents/'+state['incident'])['cmdId'])
        check('original approved decision remains unchanged',base.request(base.PROCESS+'/api/decisions/'+did)==old)
        consent(fresh,task('task:select'),'g1')
        phase('finish','--clear-after-ack')
        final=read('completed');finished=read('incident-completed')
        check('fresh approval reaches real PLC ACK CMMS and process closure',final['instance']['end_event']=='ev:closed' and finished['ack']['result']=='DONE' and bool(finished['workOrder']))
        check('old approval retired and new generation explicitly approved',len(final['approvals'])==2 and {a['status'] for a in final['approvals']}=={'DISCARDED','DELIVERED'} and final['instance']['rework_generation']==1)
    finally:
        cleanup_errors=[]
        if (OUT/'state.json').exists():
            try:phase('restore')
            except Exception as e:cleanup_errors.append(str(e));save('cleanup-source-error',{'error':str(e)})
        if overridden:
            try:run(['docker','compose','up','-d','--no-deps','process'],'restore-base-process');until(ready)
            except Exception as e:cleanup_errors.append(str(e))
        if proxy_started:
            try:run(compose+['stop','a046-check-proxy'],'stop-proxy')
            except Exception as e:cleanup_errors.append(str(e))
        if OUT.exists():save('result',{'scope':__doc__,'checks':checks,'cleanup_errors':cleanup_errors})
        if cleanup_errors:raise RuntimeError('Cleanup requires followup: '+str(cleanup_errors))
    print(str(len(checks))+' live checks passed; source restored; proxy stopped',flush=True)


if __name__=='__main__':main()
