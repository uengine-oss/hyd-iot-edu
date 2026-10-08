"""Actual HTTP/PG generation dependencies, restart, concurrency and projection."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
import psycopg
from probe_definition_registry import http, ROOT, DSN


def main():
    out=Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=False)
    checks=[]
    def save(name,value):
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,value):
        checks.append(dict(name=name,passed=bool(value))); save('checks',checks)
        print(('PASS ' if value else 'FAIL ')+name,flush=True); assert value,name
    def req(path,data=None):
        code,value=http(path,data); assert code in (200,201),(code,value); return value
    def health():
        for _ in range(120):
            try:
                if http('/healthz')[0]==200: return
            except OSError: pass
            time.sleep(.5)
        raise TimeoutError('process health')
    health()
    raw=json.loads((ROOT/'docs/examples/dependency-review-v1.json').read_text(encoding='utf8'))
    raw['processDefinitionId']+='-'+uuid.uuid4().hex[:10]
    req('/api/process/definitions',dict(definition=raw)); save('definition',raw)
    inst=req('/api/instances/start',dict(definition_id=raw['processDefinitionId'],version='1',event_id=str(uuid.uuid4())))
    pid=inst['proc_inst_id']
    def view(): return req('/api/instances/'+pid)
    def latest():
        return {w['activity_id']:w for w in sorted(view()['workitems'],key=lambda w:(w.get('generation') or 0,w.get('start_date') or ''))}
    def submit(row,key,value): return req('/api/todolist/'+row['id']+'/submit',dict(output={key:value},by='[회귀 검사] A063 검사기'))
    def rework(row):
        preview=req('/api/instances/'+pid+'/rework-preview?workitem_id='+row['id']); save('preview-'+str(row['generation']),preview)
        check('generation_'+str(row['generation'])+'_plan_available',preview['execution_available'])
        return req('/api/instances/'+pid+'/rework',dict(workitem_id=row['id'],request_id=str(uuid.uuid4()),
            snapshot_token=preview['snapshot_token'],by='[회귀 검사] A063 검사기',role='role:operator',reason='[회귀 검사] 앞 단계 결과 변경'))
    old=latest(); submit(old['a'],'x','old x'); submit(old['b'],'y','old y')
    first=rework(old['a']); save('first-rework',first)
    current=latest(); waiting=view(); save('waiting',waiting)
    check('only_root_open_consumers_wait', [current[a]['status'] for a in ('a','b','c')]==['IN_PROGRESS','TODO','TODO'])
    for activity,key in [('b','y'),('c','z')]:
        status,body=http('/api/todolist/'+current[activity]['id']+'/submit',dict(output={key:'premature'},by='[회귀 검사] A063 검사기'))
        check(activity+'_direct_submit_cannot_bypass_wait',status==400 and 'not reached' in body.get('detail','')
              and latest()[activity]['status']=='TODO' and latest()[activity]['output'] is None)
    with psycopg.connect(DSN) as conn:
        state=conn.execute('select flow_state from bpm_proc_inst where proc_inst_id=%s',(pid,)).fetchone()[0]
    check('schedule_is_durable_postgresql',state==waiting['instance']['flow_state'] and state['dependency_schedule'][current['b']['id']]['requires'][0]['workitem']==current['a']['id'])
    subprocess.run(['docker','kill','hyd-iot-edu-process-1'],capture_output=True,check=True)
    subprocess.run(['docker','start','hyd-iot-edu-process-1'],capture_output=True,check=True); health()
    check('kill_restart_preserves_wait_and_identity',view()['instance']['flow_state']==state)
    second=rework(current['a']); save('second-rework',second)
    newer=latest()
    stale_status,stale=http('/api/todolist/'+current['a']['id']+'/submit',dict(output={'x':'stale'},by='[회귀 검사] A063 검사기'))
    save('stale-submit',dict(status=stale_status,response=stale))
    check('superseded_submission_rejected',stale_status==400 and 'CANCELLED' in stale.get('detail','')
          and latest()['a']['output'] is None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(submit,newer['a'],'x','fresh x'),pool.submit(submit,old['hold'],'hold','finished')]
        [f.result() for f in futures]
    opened=latest(); save('producer-finished',view())
    check('fresh_result_opens_exact_consumer_once',opened['b']['status']=='IN_PROGRESS' and opened['b']['generation']==2
          and opened['b']['reference_ids']==[newer['a']['id']] and 'fresh x' in opened['b']['query'] and 'old x' not in opened['b']['query'])
    check('flow_successor_waits_despite_data_plan',opened['c']['status']=='TODO' and view()['instance']['status']=='RUNNING')
    code,duplicate=http('/api/todolist/'+newer['a']['id']+'/submit',dict(output={'x':'duplicate'},by='[회귀 검사] A063 검사기'))
    check('duplicate_producer_rejected',code==400 and 'DONE' in duplicate.get('detail','')
          and latest()['b']['id']==opened['b']['id'] and latest()['a']['output']=={'x':'fresh x'})
    submit(opened['b'],'y','fresh y'); c=latest()['c']
    check('consumer_output_reaches_next_with_new_reference',c['status']=='IN_PROGRESS' and c['reference_ids']==[opened['b']['id']] and 'fresh y' in c['query'])
    submit(c,'z','verified'); final=view(); save('final',final)
    check('all_admitted_paths_complete',final['instance']['status']=='COMPLETED')
    check('historical_outputs_and_waiting_generations_preserved',next(w for w in final['workitems'] if w['id']==old['b']['id'])['output']=={'y':'old y'}
          and len(final['instance']['flow_state']['superseded_dependency_schedules'])==1)
    graph=req('/api/instances/'+pid+'/graph'); save('graph',graph)
    check('execution_projection_matches_exact_source_rows',graph['graph']['instance']['status']==final['instance']['status']
          and {w['id']:w['status'] for w in graph['graph']['workitems']}=={w['id']:w['status'] for w in final['workitems']})
    print(out,flush=True)


if __name__=='__main__': main()
