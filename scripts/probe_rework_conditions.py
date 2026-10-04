"""Real HTTP/PG rework condition review, restart and boundary-timer generations.

Creates owned definitions/instances and preserves them as evidence. No PLC/Codex.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
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
    report={'scope':'actual HTTP/PG/restart/timer/Neo4j; no Codex or PLC','checks':{},'instances':[]}
    def save(name,value):
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,value):
        report['checks'][name]=bool(value); save('result',report)
        print(('PASS ' if value else 'FAIL ')+name,flush=True); assert value,name
    def req(path,data=None):
        status,value=http(path,data); assert status in (200,201),(status,value); return value
    def until(fn,timeout=50):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            value=fn()
            if value: return value
            time.sleep(.3)
        raise TimeoutError('condition did not become true')
    def health():
        try: return http('/healthz')[0]==200
        except OSError: return False
    def start(suffix,timer):
        raw=json.loads((ROOT/'docs/examples/condition-recheck-v1.json').read_text(encoding='utf8'))
        raw['processDefinitionId']+='-'+suffix+'-'+uuid.uuid4().hex[:8]
        raw['events'][-1]['timer']=timer
        req('/api/process/definitions',dict(definition=raw)); save(suffix+'-definition',raw)
        inst=req('/api/instances/start',dict(definition_id=raw['processDefinitionId'],version='1',event_id=str(uuid.uuid4())))
        report['instances'].append(inst['proc_inst_id']); save('result',report)
        return inst['proc_inst_id']
    def view(pid): return req('/api/instances/'+pid)
    def latest(pid):
        return {w['activity_id']:w for w in sorted(view(pid)['workitems'],key=lambda w:(w.get('generation') or 0,w.get('start_date') or ''))}
    def submit(row,output): return req('/api/todolist/'+row['id']+'/submit',dict(output=output,by='A071 probe'))
    def rework(pid,row,label):
        plan=req('/api/instances/'+pid+'/rework-preview?workitem_id='+row['id']); save(label+'-preview',plan)
        check(label+'_plan_includes_prior_review',plan['execution_available'] and 'b' in plan['affected_nodes'])
        body=dict(workitem_id=row['id'],request_id=str(uuid.uuid4()),snapshot_token=plan['snapshot_token'],by='A071 probe',role='role:operator',reason='new producer value changes separate branch condition')
        result=req('/api/instances/'+pid+'/rework',body); save(label+'-receipt',result)
        return body,result
    def graph_matches(pid,label):
        source=view(pid); graph=req('/api/instances/'+pid+'/graph'); save(label+'-source',source); save(label+'-graph',graph)
        check(label+'_graph_matches_current_rows',graph['graph']['instance']['status']==source['instance']['status'] and
              {w['id']:w['status'] for w in graph['graph']['workitems']}=={w['id']:w['status'] for w in source['workitems']})
    until(health)
    pid=start('gateway','PT20M'); old=latest(pid)
    submit(old['a'],{'x':'old'}); submit(old['b'],{'review':'old decision'})
    original_b=latest(pid)['b']; check('original_condition_takes_old_branch',latest(pid)['c']['status']=='IN_PROGRESS')
    body,receipt=rework(pid,old['a'],'first'); fresh=latest(pid)
    check('new_review_and_all_branches_wait_for_producer',fresh['b']['status']==fresh['c']['status']==fresh['d']['status']=='TODO')
    status,error=http('/api/todolist/'+fresh['b']['id']+'/submit',dict(output={'review':'premature'},by='A071 probe'))
    check('unreached_review_cannot_be_submitted',status==400 and 'not reached' in error.get('detail',''))
    waiting=view(pid); save('waiting',waiting)
    with psycopg.connect(DSN) as db:
        state=db.execute('select flow_state from bpm_proc_inst where proc_inst_id=%s',(pid,)).fetchone()[0]
    check('exact_condition_producer_and_arrival_durable_in_pg',state==waiting['instance']['flow_state'] and
          state['dependency_schedule'][fresh['b']['id']]['requires'][0]['workitem']==fresh['a']['id'] and
          state['dependency_schedule'][fresh['b']['id']]['requires'][0]['condition_variables']==['x'])
    subprocess.run(['docker','kill','hyd-iot-edu-process-1'],check=True,capture_output=True)
    subprocess.run(['docker','start','hyd-iot-edu-process-1'],check=True,capture_output=True); until(health)
    check('process_restart_preserves_waiting_condition_identity',view(pid)['instance']['flow_state']==state)
    check('request_replay_is_original_receipt',req('/api/instances/'+pid+'/rework',body)==receipt)
    _,second=rework(pid,fresh['a'],'second'); current=latest(pid)
    status,error=http('/api/todolist/'+fresh['a']['id']+'/submit',dict(output={'x':'stale'},by='A071 probe'))
    check('older_producer_cannot_release_new_review',status==400 and latest(pid)['b']['status']=='TODO')
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(submit,current['a'],{'x':'new'}),pool.submit(submit,old['hold'],{'hold':'finished'})]
        [f.result() for f in futures]
    opened=latest(pid); save('new-review',view(pid))
    check('fresh_condition_snapshot_and_reference_reach_review',opened['b']['status']=='IN_PROGRESS' and opened['b']['generation']==2 and
          opened['b']['reference_ids']==[current['a']['id']] and '[ConditionData]' in opened['b']['query'] and 'new' in opened['b']['query'])
    snapshot=view(pid)['instance']['flow_state']['condition_snapshots'][opened['b']['id']]
    check('condition_snapshot_preserves_exact_value_and_source',snapshot['inputs']=={'x':'new'} and snapshot['sources']['x']['id']==current['a']['id'])
    submit(opened['b'],{'review':'new review'}); branch=latest(pid)
    check('new_review_reevaluates_gateway_and_cancels_new_timer',branch['d']['status']=='IN_PROGRESS' and branch['c']['status']=='TODO' and branch['deadline']['status']=='CANCELLED')
    check('original_done_review_and_gateway_record_preserved',next(w for w in view(pid)['workitems'] if w['id']==old['b']['id'])==original_b)
    submit(branch['d'],{'new_result':'verified new branch'})
    check('new_branch_closes_after_all_admitted_work',view(pid)['instance']['status']=='COMPLETED')
    graph_matches(pid,'gateway')

    pid=start('boundary','PT5M'); old=latest(pid); submit(old['a'],{'x':'old'})
    until(lambda:latest(pid).get('late',{}).get('status')=='IN_PROGRESS')
    expired=latest(pid); save('old-expired-boundary',view(pid))
    check('original_timer_fires_and_cancels_review',expired['deadline']['status']=='DONE' and expired['b']['status']=='CANCELLED')
    _,_=rework(pid,old['a'],'expired-boundary')
    waiting=latest(pid)
    check('expired_review_is_not_reopened_before_fresh_producer',waiting['b']['status']=='TODO' and latest(pid)['deadline']['id']==expired['deadline']['id'])
    submit(waiting['a'],{'x':'new'}); reopened=latest(pid); timer=reopened['deadline']
    start_at=datetime.fromisoformat(timer['start_date'].replace('Z','+00:00'))
    due_at=datetime.fromisoformat(timer['due_date'].replace('Z','+00:00'))
    check('new_timer_starts_at_new_review_with_same_time_scale',reopened['b']['status']=='IN_PROGRESS' and timer['generation']==1 and
          timer['supersedes_id']==expired['deadline']['id'] and (due_at-start_at).total_seconds()==15)
    check('previous_timeout_branch_waits_for_new_timer_arrival',reopened['late']['status']=='TODO')
    submit(old['hold'],{'hold':'done'})
    until(lambda:latest(pid).get('late',{}).get('status')=='IN_PROGRESS')
    fired=latest(pid); save('new-expired-boundary',view(pid))
    check('only_new_boundary_wins_in_new_generation',fired['deadline']['status']=='DONE' and fired['b']['status']=='CANCELLED' and fired['late']['generation']==1 and fired['d']['status']=='TODO')
    status,error=http('/api/todolist/'+reopened['b']['id']+'/submit',dict(output={'review':'too late'},by='A071 probe'))
    check('late_review_cannot_override_fired_boundary',status==400 and fired['b']['status']=='CANCELLED')
    submit(fired['late'],{'late_result':'timeout handled'})
    check('boundary_generation_finishes_without_losing_old_timer',view(pid)['instance']['status']=='COMPLETED' and next(w for w in view(pid)['workitems'] if w['id']==expired['deadline']['id'])['status']=='DONE')
    graph_matches(pid,'boundary')
    report['exit_code']=0; save('result',report)


if __name__=='__main__': main()
