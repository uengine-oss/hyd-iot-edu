"""Actual initial/rework input contract; fixture outputs, not an actual CLI run."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
from probe_definition_registry import http, ROOT, DSN
from procsvc.procdb import PgRepo
from worker.context import prepare


def main():
    out=Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=False)
    checks=[]; repo=PgRepo(DSN)
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
        raise TimeoutError('health')
    health()
    raw=json.loads((ROOT/'docs/examples/bound-input-review-v1.json').read_text(encoding='utf8'))
    raw['processDefinitionId']+='-'+uuid.uuid4().hex[:10]
    raw['activities'][1].update(type='businessRuleTask',agentMode='COMPLETE',orchestration='cliagents')
    raw['activities'][3].update(outputData=['x'],tool='formHandler:x')
    for label,change in [('unreachable',lambda bad:bad.update(sequences=[s for s in bad['sequences'] if s['id']!='s-a'])),
                         ('cycle',lambda bad:bad['activities'][0].update(inputData=['y'],inputBindings={'y':{'activity':'b'}}))]:
        bad=deepcopy(raw); bad['processDefinitionId']+='-'+label; change(bad)
        code,value=http('/api/process/definitions',dict(definition=bad))
        check(label+'_input_binding_rejected_before_start',code==400 and 'inputBindings' in value.get('detail',''))
    req('/api/process/definitions',dict(definition=raw)); save('definition',raw)
    inst=req('/api/instances/start',dict(definition_id=raw['processDefinitionId'],version='1',event_id=str(uuid.uuid4())))
    pid=inst['proc_inst_id']
    def view(): return req('/api/instances/'+pid)
    def latest():
        return {w['activity_id']:w for w in sorted(view()['workitems'],key=lambda w:(w.get('generation') or 0,w.get('start_date') or ''))}
    def submit(row,key,value): return req('/api/todolist/'+row['id']+'/submit',dict(output={key:value},by='A064 fixture'))
    def claim(): return repo.fetch_pending_task('cliagents','a064-fixture',tenant_id='hyd',proc_inst_id=pid)
    rows=latest()
    check('initial_producer_live_consumer_waiting',rows['a']['status']=='IN_PROGRESS' and rows['b']['status']=='TODO')
    check('worker_cannot_claim_before_bound_input',claim()==[])
    before=repo.get_instance(pid)['flow_state']; save('waiting-pg',before)
    subprocess.run(['docker','kill','hyd-iot-edu-process-1'],capture_output=True,check=True)
    subprocess.run(['docker','start','hyd-iot-edu-process-1'],capture_output=True,check=True); health()
    check('restart_preserves_bound_workitem_identity',repo.get_instance(pid)['flow_state']==before and latest()['b']['id']==rows['b']['id'])
    submit(rows['a'],'x','measurement A')
    claimed=claim(); check('exact_consumer_claimable_after_producer',len(claimed)==1 and claimed[0]['id']==rows['b']['id'])
    context=prepare(repo,claimed[0],'hyd')
    check('worker_context_contains_captured_input_and_producer','measurement A' in context.row['query'] and context.row['reference_ids']==[rows['a']['id']])
    submit(rows['hold'],'x','measurement from other task')
    bv=req('/api/todolist/'+rows['b']['id']); save('bound-view',bv)
    check('other_writer_does_not_change_captured_input',bv['inputs']=={'x':'measurement A'} and bv['input_sources']['x']['id']==rows['a']['id'])
    check('fixture_result_saved_only_by_claim_owner',repo.save_task_result(rows['b']['id'],{'y':'fixture review'},True,expected_consumer='a064-fixture'))
    for _ in range(40):
        if latest()['b']['status']=='DONE': break
        time.sleep(.5)
    check('engine_poll_releases_bound_successor',latest()['b']['status']=='DONE' and latest()['c']['status']=='IN_PROGRESS')
    preview=req('/api/instances/'+pid+'/rework-preview?workitem_id='+rows['a']['id']); save('preview',preview)
    reworked=req('/api/instances/'+pid+'/rework',dict(workitem_id=rows['a']['id'],request_id=str(uuid.uuid4()),
        snapshot_token=preview['snapshot_token'],by='A064 fixture',role='role:operator',reason='new measurement'))
    current=latest(); check('rework_consumer_waits_and_cannot_be_claimed',current['b']['status']=='TODO' and claim()==[])
    submit(current['a'],'x','revised measurement')
    claimed=claim(); check('new_generation_claims_exact_new_producer',len(claimed)==1 and claimed[0]['id']==current['b']['id']
        and claimed[0]['reference_ids']==[current['a']['id']] and 'revised measurement' in claimed[0]['query'])
    old=req('/api/todolist/'+rows['b']['id']); new=req('/api/todolist/'+current['b']['id'])
    check('old_and_new_input_snapshots_remain_distinct',old['inputs']=={'x':'measurement A'} and new['inputs']=={'x':'revised measurement'})
    assert repo.save_task_result(current['b']['id'],{'y':'fixture revised review'},True,expected_consumer='a064-fixture')
    for _ in range(40):
        if latest()['c']['status']=='IN_PROGRESS': break
        time.sleep(.5)
    submit(latest()['c'],'z','verified'); final=view(); save('final',final)
    check('bound_workflow_completes',final['instance']['status']=='COMPLETED')
    graph=req('/api/instances/'+pid+'/graph'); save('graph',graph)
    check('graph_matches_exact_workitem_generations',graph['graph']['instance']['status']==final['instance']['status']
          and {w['id']:w['status'] for w in graph['graph']['workitems']}=={w['id']:w['status'] for w in final['workitems']})
    save('scope',dict(actual_cli=False,fixture_outputs=True,actual_postgresql_claim=True,instance=pid))
    print(out,flush=True)


if __name__=='__main__': main()
