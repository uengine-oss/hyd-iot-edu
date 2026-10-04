"""Actual PG/child-exit durability; isolated tenant, explicit fixture evaluation, no AI/PLC."""
import argparse
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/process'),str(ROOT/'common')]
import psycopg
from procsvc import engine,instances,procdb,task_deferral
from procsvc.legacy_assessment import LegacyAssessment

DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'
HELD={'id':'explicit-fixture','status':'WITHHELD','error':'Fixture source unavailable','steps':[]}


def runtime(meta):
    raw=json.loads((ROOT/'it/process/definitions/anomaly_response_v21.json').read_text(encoding='utf8'))
    hooks=instances.Hooks(new_incident=lambda alert,recovery_policy=None:{'id':'fixture-incident'})
    return instances.InstanceRuntime(procdb.PgRepo(DSN),engine.Definition.from_dict(raw),hooks,tenant_id=meta['tenant'])


def worker(rt):
    def forbidden(*_):raise AssertionError('unexpected source evaluation or publication')
    return LegacyAssessment(rt,forbidden,forbidden,forbidden,lease_seconds=2)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--child');args=ap.parse_args()
    out=Path(args.out)
    if args.child:
        meta=json.loads((out/'fixture.json').read_text(encoding='utf8'));rt=runtime(meta);w=worker(rt)
        if args.child=='claim':w.claim(meta['wid']);os._exit(81)
        row=rt.repo.get_workitem(meta['wid']);w.save_reply(row,HELD);os._exit(82)
    out.mkdir(parents=True,exist_ok=False);checks=[]
    def save(name,value):(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)});save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    meta={'tenant':'legacy-'+uuid.uuid4().hex[:10]}
    with psycopg.connect(DSN,connect_timeout=5) as c:
        c.execute('insert into tenants(id,name) values(%s,%s)',(meta['tenant'],'A059 retained isolated fixture'))
    rt=runtime(meta)
    alert={'alertId':'fixture-'+uuid.uuid4().hex,'asset':'HYD-02','pattern':'PUMP_LEAKAGE','state':'RAISE'}
    inst=rt.on_alert_raise(alert);meta['pid']=inst['proc_inst_id']
    row=next(w for w in rt.repo.list_workitems(proc_inst_id=meta['pid']) if w['activity_id']=='task:diagnose')
    meta['wid']=row['id'];save('fixture',meta)
    for phase,code in [('claim',81),('reply',82)]:
        child=subprocess.run([sys.executable,__file__,'--out',str(out),'--child',phase],capture_output=True,timeout=40)
        save(phase,{'exit':child.returncode,'stderr':child.stderr.decode('utf8',errors='replace')})
        current=rt.repo.get_workitem(row['id'])
        check('child exit retains '+phase,child.returncode==code and current.get('consumer','').startswith('legacy-eval:'))
        if phase=='claim':
            old=current;fresh=worker(runtime(meta)).claim(row['id'],datetime.now(timezone.utc)+timedelta(seconds=3))
            check('new runtime replaces expired claim',fresh is not None and fresh['consumer']!=old['consumer'])
            check('late old reply cannot overwrite new claim',not worker(rt).save_reply(old,HELD))
    check('new runtime consumes saved reply without source access',worker(runtime(meta)).tick()==1)
    pending=rt.repo.get_workitem(row['id']);save('pending',pending)
    check('committed reply becomes durable PENDING',pending['status']=='PENDING' and pending['draft']['_deferral']['assessment']['reason']==HELD['error'])
    receipt=task_deferral.reassess(rt.repo,meta['tenant'],row['id'],deferral_id=pending['draft']['_deferral']['id'],
                                  request_id='fixture-fresh',by='fixture',reason='new source requested')
    fresh=worker(runtime(meta)).claim(row['id'])
    check('reassessment claims new owner without saved reply',fresh is not None and fresh['consumer']!=current['consumer']
          and 'result' not in fresh['draft']['_legacy_attempt'])
    worker(rt).save_reply(fresh,HELD);worker(rt).apply_reply(fresh)
    save('final',rt.instance_view(meta['pid']));save('receipt',receipt)
    print(f'{len(checks)}/{len(checks)} passed; retained fixture is PENDING',flush=True)


if __name__=='__main__':main()
