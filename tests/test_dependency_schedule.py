"""Rework follows fresh producer evidence and actual control arrivals together."""
from copy import deepcopy
import uuid
import pytest
from procsvc import engine, instances
from test_process_end_barrier import setup as setup_definition
from test_rework_runtime import latest, request
from test_engine import NOW


def definition():
    return {
        'processDefinitionId': 'dependency-review', 'processDefinitionName': 'Dependency review', 'version': '1',
        'roles': [{'name': 'Reviewer', 'endpoint': 'role:operator'}],
        'data': [{'name': k, 'type': 'Text'} for k in ('x', 'y', 'z', 'hold')],
        'forms': {k: {'fields_json': [{'key': k, 'type': 'text', 'text': k}]} for k in ('x', 'y', 'z', 'hold')},
        'activities': [dict(id=a, type='userTask', role='Reviewer', tool='formHandler:'+output,
                            inputData=inputs, outputData=[output])
                       for a, inputs, output in [('a', [], 'x'), ('b', ['x'], 'y'), ('c', ['y'], 'z'), ('hold', [], 'hold')]],
        'events': [{'id': 's', 'type': 'startEvent'}, {'id': 'e', 'type': 'endEvent'}],
        'sequences': [dict(id=f'{src}-{tgt}', source=src, target=tgt)
                      for src, tgt in [('s','a'), ('s','b'), ('s','hold'), ('a','e'), ('b','c'), ('c','e'), ('hold','e')]],
    }


def setup(raw=None):
    rt, pid, rows = setup_definition(raw or definition())
    rt.submit(rows['a']['id'], {'x': 'old x'}, now=NOW)
    rt.submit(rows['b']['id'], {'y': 'old y'}, now=NOW)
    return rt, pid, rows


def test_fresh_dependency_chain_waits_then_rebuilds_queries_and_references():
    rt, pid, old = setup()
    result = request(rt, pid, old['a']['id'])
    a, b, c = [latest(rt, pid, k) for k in ('a','b','c')]
    assert [r['status'] for r in (a,b,c)] == ['IN_PROGRESS','TODO','TODO']
    rt.submit(old['hold']['id'], {'hold': 'finished'}, now=NOW)
    assert rt.repo.get_instance(pid)['status'] == 'RUNNING'
    rt = instances.InstanceRuntime(rt.repo, rt.defn, instances.Hooks())
    rt.submit(a['id'], {'x': 'new x'}, now=NOW)
    b = latest(rt, pid, 'b')
    assert b['status'] == 'IN_PROGRESS' and 'new x' in b['query'] and 'old x' not in b['query']
    assert b['reference_ids'] == [a['id']]
    assert latest(rt, pid, 'c')['status'] == 'TODO'
    rt.submit(b['id'], {'y': 'new y'}, now=NOW)
    c = latest(rt, pid, 'c')
    assert c['status'] == 'IN_PROGRESS' and c['reference_ids'] == [b['id']] and 'new y' in c['query']
    rt.submit(c['id'], {'z': 'verified'}, now=NOW)
    assert rt.repo.get_instance(pid)['status'] == 'COMPLETED'
    assert rt.repo.get_workitem(old['b']['id'])['output'] == {'y':'old y'}


def test_second_rework_retargets_waiting_dependencies_and_fences_old_result():
    rt, pid, old = setup()
    request(rt, pid, old['a']['id'])
    previous = latest(rt, pid, 'a')
    request(rt, pid, previous['id'])
    current = latest(rt, pid, 'a')
    with pytest.raises(ValueError): rt.submit(previous['id'], {'x':'stale'}, now=NOW)
    rt.submit(current['id'], {'x':'generation two'}, now=NOW)
    b = latest(rt, pid, 'b')
    assert b['generation'] == 2 and b['status'] == 'IN_PROGRESS'
    assert b['reference_ids'] == [current['id']]


def test_waiting_schedule_survives_transaction_failure(monkeypatch):
    rt, pid, old = setup()
    request(rt, pid, old['a']['id'])
    before = deepcopy((rt.repo.instances,rt.repo.workitems,rt.repo.events))
    def fail(*args): raise OSError('disk failed')
    monkeypatch.setattr(rt.repo, 'update_instance', fail)
    with pytest.raises(OSError): rt.submit(latest(rt,pid,'a')['id'], {'x':'new'}, now=NOW)
    assert (rt.repo.instances,rt.repo.workitems,rt.repo.events) == before


@pytest.mark.parametrize('status', ['PENDING','CANCELLED'])
def test_failed_or_cancelled_producer_never_releases_consumer(status):
    rt, pid, old = setup()
    request(rt,pid,old['a']['id'])
    row=latest(rt,pid,'a'); row['status']=status; rt.repo.update_workitem(row)
    rt.submit(old['hold']['id'], {'hold':'done'}, now=NOW)
    assert latest(rt,pid,'b')['status']=='TODO'
    assert rt.repo.get_instance(pid)['status']=='RUNNING'
    spec=rt.repo.get_instance(pid)['flow_state']['dependency_schedule'][latest(rt,pid,'b')['id']]
    assert spec['waiting_for'][0]['reason']=='producer_not_done_or_superseded'


def test_missing_fresh_output_never_falls_back_to_old_value_or_initial_seed():
    raw=definition(); raw['forms']['x']['fields_json'][0]['required']=False
    rt,pid,old=setup(raw)
    request(rt,pid,old['a']['id'])
    # A legitimate optional output can be absent, even though the consumer names it.
    rt.submit(latest(rt,pid,'a')['id'], {}, now=NOW)
    rt.submit(old['hold']['id'], {'hold':'done'}, now=NOW)
    assert latest(rt,pid,'b')['status']=='TODO'
    inst=rt.repo.get_instance(pid)
    assert inst['status']=='RUNNING' and 'x' not in engine.variables(inst)
    assert inst['flow_state']['dependency_schedule'][latest(rt,pid,'b')['id']]['waiting_for'][0]['reason']=='fresh_output_unavailable'


def test_duplicate_completion_does_not_reopen_or_duplicate_consumers():
    rt,pid,old=setup(); request(rt,pid,old['a']['id'])
    a=latest(rt,pid,'a'); rt.submit(a['id'], {'x':'new'}, now=NOW)
    before=deepcopy((rt.repo.instances,rt.repo.workitems))
    with pytest.raises(ValueError): rt.submit(a['id'], {'x':'duplicate'}, now=NOW)
    assert (rt.repo.instances,rt.repo.workitems)==before


@pytest.mark.parametrize('activity,output', [('b',{'y':'premature'}),('c',{'z':'premature'})])
def test_direct_submission_cannot_skip_dependency_or_flow_wait(activity,output):
    rt,pid,old=setup(); request(rt,pid,old['a']['id'])
    before=deepcopy((rt.repo.instances,rt.repo.workitems,rt.repo.events))
    with pytest.raises(ValueError,match='not reached'):
        rt.submit(latest(rt,pid,activity)['id'],output,now=NOW)
    assert (rt.repo.instances,rt.repo.workitems,rt.repo.events)==before


def test_runtime_reference_without_input_data_is_remapped_to_new_producer():
    raw=definition(); raw['activities'][1]['inputData']=[]
    rt,pid,old=setup(raw)
    b=rt.repo.get_workitem(old['b']['id']); b['reference_ids']=[old['a']['id']]; rt.repo.update_workitem(b)
    request(rt,pid,old['a']['id'])
    a=latest(rt,pid,'a'); rt.submit(a['id'], {'x':'new'}, now=NOW)
    assert latest(rt,pid,'b')['reference_ids']==[a['id']]


def test_unreached_control_branch_is_not_opened_by_data_dependency():
    raw=definition()
    raw['sequences']=[s for s in raw['sequences'] if s['id']!='s-b']
    raw['sequences'].append(dict(id='hold-b',source='hold',target='b'))
    rt,pid,old=setup_definition(raw)
    rt.submit(old['a']['id'], {'x':'old'},now=NOW)
    request(rt,pid,old['a']['id'])
    rt.submit(latest(rt,pid,'a')['id'], {'x':'new'},now=NOW)
    assert latest(rt,pid,'b')['status']=='TODO'
    rt.submit(old['hold']['id'], {'hold':'done'},now=NOW)
    assert latest(rt,pid,'b')['status']=='IN_PROGRESS'


def test_ambiguous_producers_and_dependency_cycles_are_explicitly_blocked():
    rt,pid,old=setup()
    raw=deepcopy(rt.defn.raw)
    raw['activities'][2]['outputData']=['x']
    # a ->data b ->flow c ->data b cannot be resolved by task-name guessing.
    from procsvc import rework
    d=engine.Definition.from_dict(raw)
    result=rework.plan(d,rt.repo.get_instance(pid),rt.repo.list_workitems(proc_inst_id=pid,limit=None),old['a']['id'])
    assert 'ambiguous_dependency_producer' in {b['code'] for b in result['blockers']}


def test_direct_condition_replay_waits_for_exact_fresh_input_producer():
    rt,pid,old=setup()
    from procsvc import rework
    d=engine.Definition.from_dict(deepcopy(rt.defn.raw))
    d.sequences[-2]['condition']='x == "new"'
    result=rework.plan(d,rt.repo.get_instance(pid),rt.repo.list_workitems(proc_inst_id=pid,limit=None),old['a']['id'])
    assert not result['blockers']
    assert result['dependency_schedule']['c']['requires']['a']==['x']
    assert result['dependency_schedule']['c']['condition_names']==['x']


def test_mutual_dependencies_do_not_get_released_by_submitted_results():
    rt,pid,old=setup()
    from procsvc import rework
    raw=deepcopy(rt.defn.raw); raw['activities'][0]['inputData']=['y']
    result=rework.plan(engine.Definition.from_dict(raw),rt.repo.get_instance(pid),
                       rt.repo.list_workitems(proc_inst_id=pid,limit=None),old['a']['id'])
    assert {'rework_root_dependency_requires_review','dependency_cycle_requires_review'} <= {b['code'] for b in result['blockers']}


def test_unaffected_runtime_reference_is_preserved_with_its_original_generation():
    rt,pid,old=setup()
    # Keep c open while hold finishes, then record b's actual external reference.
    rt.submit(old['hold']['id'], {'hold':'kept evidence'},now=NOW)
    b=rt.repo.get_workitem(old['b']['id']); b['reference_ids']=[old['hold']['id']]; rt.repo.update_workitem(b)
    request(rt,pid,old['a']['id'])
    a=latest(rt,pid,'a'); rt.submit(a['id'], {'x':'new'},now=NOW)
    assert set(latest(rt,pid,'b')['reference_ids'])=={a['id'],old['hold']['id']}
