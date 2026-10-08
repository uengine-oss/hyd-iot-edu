"""A159 live B7 (real worker: AGENT_BRIDGE=off + one host worker; or deterministic: AGENT_BRIDGE=legacy, workers stopped):

    .venv/bin/python scripts/probe_b7_oil_live.py .evidence/a159/live/b7/run.json

 oil analysis (human input) → student flow my_oil → real worker diagnosis → 정비관리자 approval → work order (no plant command)
→ recheck 비정상 → new judgment/approval/work order → recheck 정상 → COMPLETED."""
import json, sys, time, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'common'),str(ROOT/'it/process')]
import urllib.request
PROC='http://127.0.0.1:8080'
def call(m,u,d=None,raw=False):
    r=urllib.request.Request(PROC+u,method=m,data=json.dumps(d).encode() if d is not None else None,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(r,timeout=120) as x:
            body=x.read(); return x.status, (body.decode() if raw else (json.loads(body) if body else {}))
    except urllib.error.HTTPError as e:
        b=e.read()
        try: return e.code, json.loads(b)
        except Exception: return e.code, b.decode()[:500]
def show(tag,st,r,n=600): print(f'[{tag}] {st}', json.dumps(r,ensure_ascii=False)[:n] if not isinstance(r,str) else r[:n], flush=True)

import test_b7_oil as T
from procsvc import bpmn_import as B
OUT=sys.argv[1]; out={'steps':[]}
def step(k,v): out['steps'].append({k:v}); print(k,json.dumps(v,ensure_ascii=False)[:500],flush=True); json.dump(out,open(OUT,'w'),ensure_ascii=False,indent=1)
def sql(q): return subprocess.run(['docker','exec','supabase_db_hyd-iot-edu','psql','-U','postgres','-At','-c',q],capture_output=True,text=True).stdout.strip()
t0=time.time()
wo_before=sql("select count(*) from ent.work_orders"); since=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); cmd_before='logs since '+since
step('baseline',{'work_orders':wo_before,'cmd_published':cmd_before})
# 1 import → mapping → register → deploy (bpmn.io drawing tests/fixtures/bpmn/oil_maintenance_student.bpmn as flow my_oil)
st,r=call('POST','/api/flows/import',{'xml':T.OIL_BPMN,'file_name':'oil_maintenance_student.bpmn','definition_id':'my_oil'}); step('import',{'st':st,'next_version':r.get('next_version'),'ok':(r.get('check') or {}).get('ok')})
parsed=B.parse_bpmn(T.OIL_BPMN); m=T.oil_mapping(parsed,B.catalog(T.BASE,[T.MAINT]))
st,r=call('PUT','/api/flows/my_oil/mapping',{'mapping':m}); step('mapping',{'st':st,'ok':(r.get('check') or {}).get('ok'),'problems':[p.get('reason') for p in (r.get('check') or {}).get('problems',[])][:5]})
st,r=call('POST','/api/flows/my_oil/register',{}); ver=r.get('version'); step('register',{'st':st,'version':ver,'err':None if st<300 else r})
st,r=call('POST','/api/process/definitions/my_oil/deploy',{'version':ver,'by':'김정비','reason':'[회귀 검사] A159 B7 작동유 흐름'}); step('deploy',{'st':st,'applies_to':r.get('applies_to'),'err':None if st<300 else r})
# 2 in-spec → nothing; out-of-spec → alert
st,r=call('POST','/api/human-alerts',{'pattern':'OIL_ANALYSIS','asset':'HYD-01','item':'water','value':150,'out_of_spec':False,'by':'김정비'}); step('in_spec',{'st':st,**r})
st,r=call('POST','/api/human-alerts',{'pattern':'OIL_ANALYSIS','asset':'HYD-01','item':'water','value':620,'out_of_spec':True,'memo':'[회귀 검사] 정기 분석 — 수분 증가','by':'김정비'}); step('out_of_spec',{'st':st,**{k:r.get(k) for k in r if k!='alert'}})
pid=None
while time.time()-t0<300 and not pid:
    st,lst=call('GET','/api/instances?limit=10')
    pid=next((i['proc_inst_id'] for i in lst if i['proc_def_id']=='my_oil' and i['status']=='RUNNING'),None); time.sleep(3)
step('instance',{'pid':pid,'after_s':round(time.time()-t0)})
if not pid: sys.exit(1)
def wait_live(aid,n_done=None,limit=1500):
    while time.time()-t0<limit*4:
        st,v=call('GET','/api/instances/'+pid)
        w=next((x for x in v['workitems'] if x['activity_id']==aid and x['status']=='IN_PROGRESS'),None)
        if w and (n_done is None or sum(1 for x in v['workitems'] if x['activity_id']==T.DIAG and x['status']=='DONE')>=n_done): return v,w
        if v['instance']['status']!='RUNNING': return v,None
        bad=[x for x in v['workitems'] if x['status']=='PENDING' or x.get('draft_status')=='FAILED']
        if bad: return v,None
        time.sleep(8)
    return v,None
for rnd,result in ((1,'비정상'),(2,'정상')):
    v,sel=wait_live(T.SELECT,rnd)
    diag=[x for x in v['workitems'] if x['activity_id']==T.DIAG]
    step(f'r{rnd}_diagnose',{'statuses':[(x['status'],x.get('draft_status'),x.get('user_id')) for x in diag],'after_s':round(time.time()-t0),
                             'blocked':[(x['activity_name'],x['status'],x.get('log')) for x in v['workitems'] if x['status']=='PENDING' or x.get('draft_status')=='FAILED']})
    if not sel: break
    vars_=v['instance'].get('variables_data') or v['instance'].get('variables') or {}
    dec_id=(vars_.get('decision_id') if isinstance(vars_,dict) else None) or next(((x.get('output') or {}).get('decision_id') for x in v['workitems'] if isinstance(x.get('output'),dict) and (x.get('output') or {}).get('decision_id')),None)
    st,dec=call('GET','/api/decisions/'+str(dec_id)); rec=dec.get('recommended')
    ev=(dec.get('causes') or [{}])[0].get('evidence') if isinstance(dec.get('causes'),list) else None
    step(f'r{rnd}_decision',{'id':dec_id,'recommended':rec,'options':[o['id'] for o in dec.get('options',[])],'cause':(dec.get('causes') or [{}])[0].get('id') if isinstance(dec.get('causes'),list) else None,'evidence':ev})
    st,bad=call('POST',f"/api/todolist/{sel['id']}/select",{'decision':dec_id,'option':rec,'by':'김운전','role':'role:operator','reason':'[회귀 검사] 권한 확인'})
    step(f'r{rnd}_operator_refused',{'st':st,'detail':str(bad)[:200]})
    _,rv=call('POST',f"/api/todolist/{sel['id']}/decision-preview",{'decision':dec_id,'option':rec,'parameters':{}})
    st,r=call('POST',f"/api/todolist/{sel['id']}/select",{'decision':dec_id,'option':rec,'by':'박정비','role':'role:maint-mgr','review_id':rv.get('id'),'reason':f'[회귀 검사] A159 B7 {rnd}회차'})
    step(f'r{rnd}_select',{'st':st,'err':None if st<300 else r})
    v,chk=wait_live(T.RECHECK,limit=400)
    wo=[(x['status'],(x.get('output') or {}).get('work_order',{}).get('ref') if isinstance((x.get('output') or {}).get('work_order'),dict) else None) for x in v['workitems'] if x['activity_id']==T.WO]
    step(f'r{rnd}_work_order',{'wo_tasks':wo,'recheck_open':bool(chk),'work_orders_db':sql("select count(*) from ent.work_orders")})
    if not chk: break
    st,r=call('POST',f"/api/todolist/{chk['id']}/submit",{'output':{'recheck_result':result,'recheck_note':f'[회귀 검사] {result}'},'by':'박정비'})
    step(f'r{rnd}_recheck_{result}',{'st':st,'err':None if st<300 else r})
time.sleep(10)
st,v=call('GET','/api/instances/'+pid)
step('end',{'status':v['instance']['status'],'end_event':v['instance'].get('end_event'),'tasks':[(x['activity_name'],x['status']) for x in v['workitems']],
            'work_orders_db':sql("select count(*) from ent.work_orders"),'after_s':round(time.time()-t0)})
gw=subprocess.run(['docker','logs','--since',since,'hyd-iot-edu-cmd-gateway-1'],capture_output=True,text=True)
step('cmd_gateway_logs_since_start',[l for l in (gw.stdout+gw.stderr).splitlines() if 'HYD-01' in l or 'cmd' in l.lower()][:20])
