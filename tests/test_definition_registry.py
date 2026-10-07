from copy import deepcopy
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from procsvc import engine, instances, instance_mode, procdb
from worker.context import prepare


def definition(did='review', version='1', threshold=5):
    return {'processDefinitionId':did,'processDefinitionName':'검토','version':version,
            'roles':[{'name':'검토자','endpoint':'role:operator'}],
            'data':[{'name':'score','type':'Number'}],
            'forms':{'review':{'fields_json':[{'key':'score','type':'number','text':'측정 점수'}]}},
            'activities':[{'id':'task:review','name':'점수 검토','type':'userTask','role':'검토자',
                           'tool':'formHandler:review','outputData':['score']}],
            'events':[{'id':'start','type':'startEvent'},{'id':'accepted','type':'endEvent'},
                      {'id':'rejected','type':'endEvent'}],
            'gateways':[{'id':'choice','type':'exclusiveGateway'}],
            'sequences':[{'id':'s1','source':'start','target':'task:review'},
                         {'id':'s2','source':'task:review','target':'choice'},
                         {'id':'s3','source':'choice','target':'accepted','condition':f'score >= {threshold}'},
                         {'id':'s4','source':'choice','target':'rejected','properties':{'default':True}}]}


def test_hyd_v2_pins_forms_and_requires_escalation_note_without_rewriting_v1():
    import json
    from procsvc.definition_registry import validate_definition
    defs=Path(__file__).resolve().parents[1]/'it/process/definitions'
    old=json.loads((defs/'anomaly_response.json').read_text(encoding='utf-8'))
    new=json.loads((defs/'anomaly_response_v2.json').read_text(encoding='utf-8'))
    assert old['version']=='1.0' and 'forms' not in old
    repo=procdb.MemoryRepo()
    legacy=instances.InstanceRuntime(repo,engine.Definition.from_dict(old),instances.Hooks())
    prior=legacy.on_alert_raise({'alertId':'prior','asset':'HYD-01','pattern':'COOLER_DEGRADATION','state':'RAISE'})
    rt=instances.InstanceRuntime(repo,validate_definition(new),instances.Hooks())
    assert rt.definition_for(prior).raw==old
    inst=rt.on_alert_raise({'alertId':'new','asset':'HYD-01','pattern':'COOLER_DEGRADATION','state':'RAISE'})
    assert inst['proc_def_version']=='2.0'
    rows=repo.list_workitems(proc_inst_id=inst['proc_inst_id'])
    wi=next(w for w in rows if w['activity_id']=='task:diagnose')
    repo.upsert_form({'id':'diagnose','fields_json':[{'key':'wrong','type':'text'}]})
    assert [f['key'] for f in prepare(repo,wi,'hyd').form_fields]==['cause','failure_mode','guide_card']
    # Reach escalation through the real timer path. Forcing it IN_PROGRESS
    # while diagnosis was still live relied on the old premature-end defect.
    from test_engine import AGENT_OUTPUTS
    from datetime import datetime, timedelta
    for aid, output in AGENT_OUTPUTS.items():
        item=next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']==aid)
        rt.submit(item['id'],output)
    timer=next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='ev:select-timeout')
    rt.fire_timeouts(now=datetime.fromisoformat(timer['due_date'].replace('Z','+00:00'))+timedelta(seconds=1))
    esc=next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id']=='task:escalate')
    assert esc['status']=='IN_PROGRESS'
    with pytest.raises(ValueError,match='note'):
        rt.submit(esc['id'],{})
    rt.submit(esc['id'],{'note':'현장 확인 및 후속 정비 요청'})
    saved=repo.get_instance(inst['proc_inst_id'])
    assert saved['end_event']=='ev:escalated'
    assert engine.variables(saved)['note']=='현장 확인 및 후속 정비 요청'


@pytest.fixture
def app_world(monkeypatch):
    repo = procdb.MemoryRepo()
    rt = instances.InstanceRuntime(repo,engine.Definition.from_dict(definition()),instances.Hooks())
    monkeypatch.setattr(instance_mode,'_runtime',rt)
    app=FastAPI(); instance_mode.mount(app,'instance')
    return TestClient(app),rt,repo


def start(client,did='review',version='1',event='e'):
    res=client.post('/api/instances/start',json={'definition_id':did,'version':version,'event_id':event})
    assert res.status_code==200,res.text
    pid=res.json()['proc_inst_id']
    view=client.get('/api/instances/'+pid).json()
    return pid,next(w for w in view['workitems'] if w['status']=='IN_PROGRESS')


def test_api_keeps_old_definition_and_form_while_new_version_changes_result(app_world):
    c,rt,repo=app_world
    old,w1=start(c)
    v2=definition(version='2',threshold=10)
    v2['forms']['review']['fields_json'].append({'key':'note','type':'text'})
    v2['activities'][0]['outputData'].append('note')
    assert c.post('/api/process/definitions',json={'definition':v2}).status_code==201
    new,w2=start(c,version='2',event='next')
    # Even the mutable form table changes, both tasks keep their version-owned contract.
    repo.upsert_form({'id':'review','fields_json':[{'key':'wrong','type':'text'}]})
    assert [f['key'] for f in c.get('/api/todolist/'+w1['id']).json()['form']['fields_json']]==['score']
    assert [f['key'] for f in prepare(repo,w1,'hyd').form_fields]==['score']
    assert c.post('/api/todolist/'+w2['id']+'/submit',json={'output':{'score':7}}).status_code==400
    for w,output in [(w1,{'score':7}),(w2,{'score':7,'note':'검토함'})]:
        r=c.post('/api/todolist/'+w['id']+'/submit',json={'output':output})
        assert r.status_code==200,r.text
    assert c.get('/api/instances/'+old).json()['instance']['end_event']=='accepted'
    v=c.get('/api/instances/'+new).json()
    assert v['instance']['end_event']=='rejected' and v['definition']==v2


def test_api_rejects_version_overwrite_missing_version_and_replay(app_world):
    c,rt,repo=app_world
    changed=definition(threshold=100)
    assert c.post('/api/process/definitions',json={'definition':changed}).status_code==409
    assert c.get('/api/process/definitions/review?version=missing').status_code==404
    assert c.post('/api/instances/start',json={'definition_id':'review','event_id':'no-version'}).status_code==400
    pid,w=start(c)
    assert c.post('/api/instances/start',json={'definition_id':'review','version':'1','event_id':'e'}).status_code==409
    assert len(repo.list_instances())==1


@pytest.mark.parametrize('change',[
    lambda d:d['activities'].append(deepcopy(d['activities'][0])),
    lambda d:d['forms'].clear(),
    lambda d:d['sequences'].append({'id':'loop','source':'choice','target':'task:review'}),
    lambda d:d['activities'][0].update(type='callActivity'),
    lambda d:d['activities'][0].update(outputData='score'),
    lambda d:d['forms']['review']['fields_json'][0].update(type='select',items=123),
    lambda d:d['gateways'][0].pop('type'),
    # A096 static connectivity (bpmn-extractor process_validator._static_check · bpmn-process-generation-skill)
    lambda d:d['activities'].append({'id':'task:orphan','name':'고아','type':'userTask','role':'검토자','tool':'formHandler:review','outputData':['score']}),   # unreachable
    lambda d:(d['activities'].append({'id':'task:dead','name':'막힘','type':'userTask','role':'검토자','tool':'formHandler:review','outputData':['score']}),
              d['sequences'].append({'id':'s5','source':'choice','target':'task:dead','condition':'score < 0'})),                           # reaches no end
    lambda d:d['events'].append({'id':'lonely','type':'endEvent'}),                                                                           # never entered
    # A098 condition variables (bpmn-process-generation-skill reference-info): declared and produced by some activity
    lambda d:d['sequences'][2].update(condition='scoer >= 5'),                                                                                 # typo: not declared
    lambda d:(d['data'].append({'name':'ghost','type':'Number'}), d['sequences'][2].update(condition='ghost >= 5')),                            # declared, nobody writes it
])
def test_invalid_definition_does_not_publish(app_world,change):
    c,rt,repo=app_world
    d=definition(did='invalid'); change(d)
    assert c.post('/api/process/definitions',json={'definition':d}).status_code==400
    assert repo.get_proc_def('invalid') is None


def test_other_tenant_cannot_be_read_submitted_or_claimed(app_world):
    c,rt,repo=app_world
    other=instances.InstanceRuntime(repo,engine.Definition.from_dict(definition()),instances.Hooks(),tenant_id='other')
    inst=other.start_definition('review','1','other-event')
    w=repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    assert c.get('/api/instances/'+inst['proc_inst_id']).status_code==404
    assert c.get('/api/instances/'+inst['proc_inst_id']+'/graph').status_code==404
    assert c.get('/api/todolist/'+w['id']).status_code==404
    assert c.post('/api/todolist/'+w['id']+'/submit',json={'output':{'score':7}}).status_code==404
    assert c.get('/api/todolist').json()==[] and c.get('/api/instances').json()==[]
    assert c.get('/api/events?proc_inst_id='+inst['proc_inst_id']).status_code==404
    w.update(agent_mode='COMPLETE',agent_orch='cliagents');repo.update_workitem(w)
    assert repo.fetch_pending_task('cliagents','hyd-worker',tenant_id='hyd')==[]
    assert len(repo.fetch_pending_task('cliagents','other-worker',tenant_id='other'))==1
    w.update(status='SUBMITTED',consumer=None);repo.update_workitem(w)
    assert repo.claim_submitted('hyd-engine',tenant_id='hyd')==[]
    assert len(repo.claim_submitted('other-engine',tenant_id='other'))==1


def test_form_type_and_task_version_checked_before_mutation(app_world):
    c,rt,repo=app_world
    pid,w=start(c)
    assert c.post('/api/todolist/'+w['id']+'/submit',json={'output':{'score':'seven'}}).status_code==400
    assert repo.get_workitem(w['id'])['status']=='IN_PROGRESS'
    w['version']='other';repo.update_workitem(w)
    assert c.post('/api/todolist/'+w['id']+'/submit',json={'output':{'score':7}}).status_code==400
    assert repo.get_instance(pid)['status']=='RUNNING'


def test_generic_submit_cannot_bypass_card_approval(app_world):
    c,rt,repo=app_world
    d=definition(did='approval');d['forms']['select_card']=d['forms'].pop('review')
    d['activities'][0]['tool']='formHandler:select_card'
    assert c.post('/api/process/definitions',json={'definition':d}).status_code==201
    pid,w=start(c,did='approval')
    assert c.post('/api/todolist/'+w['id']+'/submit',json={'output':{'score':7}}).status_code==403
    assert repo.get_workitem(w['id'])['status']=='IN_PROGRESS'


def test_start_and_published_output_cannot_inject_approval_state(app_world):
    c,rt,repo=app_world
    assert c.post('/api/instances/start',json={'definition_id':'review','version':'1','event_id':'inject',
        'variables':{'commands':[{'code':'STOP'}],'incident':'some-existing-incident'}}).status_code==400
    assert repo.list_instances()==[]
    d=definition(did='inject');d['activities'][0]['outputData']=['approved_by']
    d['forms']['review']['fields_json']=[{'key':'approved_by','type':'text'}]
    assert c.post('/api/process/definitions',json={'definition':d}).status_code==400


def test_human_response_cannot_requeue_a_completed_task(app_world):
    c,rt,repo=app_world
    pid,w=start(c)
    assert c.post('/api/todolist/'+w['id']+'/submit',json={'output':{'score':7}}).status_code==200
    assert c.post('/api/todolist/'+w['id']+'/human-response',json={'job_id':'invented','answer':'resume'}).status_code==409
    saved=repo.get_workitem(w['id'])
    assert saved['status']=='DONE' and saved.get('draft_status') is None
