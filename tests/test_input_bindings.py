"""Explicit mandatory producer bindings; inputData alone remains a read list."""
from copy import deepcopy
import pytest
from procsvc import engine, definition_registry, instances
from test_dependency_schedule import definition
from test_process_end_barrier import setup
from test_rework_runtime import latest, request
from test_engine import NOW


def bound_definition():
    raw=definition()
    raw['processDefinitionId']='bound-dependency-review'
    raw['activities'][1]['inputBindings']={'x':{'activity':'a'}}
    raw['activities'][2]['inputBindings']={'y':{'activity':'b'}}
    return raw


def test_first_run_waits_for_bound_producer_and_survives_new_runtime():
    rt,pid,rows=setup(bound_definition())
    assert rows['a']['status']=='IN_PROGRESS' and rows['b']['status']=='TODO'
    rt=instances.InstanceRuntime(rt.repo,rt.defn,instances.Hooks())
    rt.submit(rows['a']['id'],{'x':'measured'},now=NOW)
    b=latest(rt,pid,'b')
    assert b['status']=='IN_PROGRESS' and b['reference_ids']==[rows['a']['id']]
    assert rt.workitem_view(b['id'])['inputs']=={'x':'measured'}


def test_missing_bound_output_blocks_without_completing_instance():
    raw=bound_definition(); raw['forms']['x']['fields_json'][0]['required']=False
    rt,pid,rows=setup(raw)
    rt.submit(rows['a']['id'],{},now=NOW)
    rt.submit(rows['hold']['id'],{'hold':'done'},now=NOW)
    assert latest(rt,pid,'b')['status']=='TODO'
    assert rt.repo.get_instance(pid)['status']=='RUNNING'


def test_bound_input_snapshot_is_not_replaced_by_later_global_variable():
    raw=bound_definition(); raw['activities'][3]['outputData']=['x']; raw['activities'][3]['tool']='formHandler:x'
    rt,pid,rows=setup(raw)
    rt.submit(rows['a']['id'],{'x':'first measurement'},now=NOW)
    rt.submit(rows['hold']['id'],{'x':'other measurement'},now=NOW)
    assert engine.variables(rt.repo.get_instance(pid))['x']=='other measurement'
    assert rt.workitem_view(rows['b']['id'])['inputs']=={'x':'first measurement'}
    assert 'first measurement' in latest(rt,pid,'b')['query']


def test_initial_binding_preserves_zero_false_and_null_and_blocks_missing():
    raw=bound_definition(); raw['activities'][0]['inputData']=['seed']; raw['activities'][0]['inputBindings']={'seed':{'initial':True}}
    rt,pid,rows=setup(raw)
    assert rows['a']['status']=='TODO'
    for value in (0,False,None):
        inst=rt.start_definition(rt.defn.id,'1',str(value),{'seed':value},now=NOW)
        row=latest(rt,inst['proc_inst_id'],'a')
        assert row['status']=='IN_PROGRESS' and rt.workitem_view(row['id'])['inputs']=={'seed':value}


def test_rework_uses_new_bound_producer_and_keeps_previous_snapshot():
    rt,pid,rows=setup(bound_definition())
    rt.submit(rows['a']['id'],{'x':'old'},now=NOW)
    rt.submit(rows['b']['id'],{'y':'old y'},now=NOW)
    request(rt,pid,rows['a']['id'])
    a=latest(rt,pid,'a'); b=latest(rt,pid,'b')
    assert b['status']=='TODO'
    rt.submit(a['id'],{'x':'new'},now=NOW)
    assert rt.workitem_view(b['id'])['inputs']=={'x':'new'}
    assert rt.workitem_view(rows['b']['id'])['inputs']=={'x':'old'}


@pytest.mark.parametrize('binding', [[], {'q':{'activity':'a'}}, {'x':{'activity':'missing'}},
    {'x':{'activity':'b'}}, {'x':{'initial':False}}, {'x':{'activity':'a','initial':True}}, {'x':{'activity':'c'}}])
def test_invalid_binding_contract_rejected_at_registration(binding):
    raw=bound_definition(); raw['activities'][1]['inputBindings']=binding
    with pytest.raises(ValueError,match='inputBindings'): definition_registry.validate_definition(raw)


def test_binding_control_dependency_cycle_is_rejected():
    raw=bound_definition(); raw['activities'][0]['inputData']=['y']; raw['activities'][0]['inputBindings']={'y':{'activity':'b'}}
    with pytest.raises(ValueError,match='inputBindings'): definition_registry.validate_definition(raw)


def test_unreachable_bound_producer_is_rejected_before_instance_side_effects():
    raw=bound_definition(); raw['sequences']=[s for s in raw['sequences'] if s['id']!='s-a']
    with pytest.raises(ValueError,match='inputBindings'): definition_registry.validate_definition(raw)


def test_unbound_read_list_does_not_impose_new_mandatory_inputs():
    rt,pid,rows=setup(definition())
    assert rows['b']['status']=='IN_PROGRESS'


def test_reworking_other_writer_does_not_invalidate_explicit_bound_consumer():
    raw=bound_definition(); raw['activities'][3]['outputData']=['x']; raw['activities'][3]['tool']='formHandler:x'
    rt,pid,rows=setup(raw)
    rt.submit(rows['a']['id'],{'x':'bound'},now=NOW)
    preview=rt.preview_rework(pid,rows['hold']['id'])
    assert 'b' not in preview['affected_nodes'] and 'c' not in preview['affected_nodes']


def test_waiting_view_does_not_present_unrelated_current_value_as_bound_input():
    raw=bound_definition(); raw['activities'][3]['outputData']=['x']; raw['activities'][3]['tool']='formHandler:x'
    rt,pid,rows=setup(raw)
    rt.submit(rows['hold']['id'],{'x':'wrong source'},now=NOW)
    assert rt.workitem_view(rows['b']['id'])['inputs']=={}
    assert rt.workitem_view(rows['b']['id'])['input_state']=='waiting'


def test_rework_can_wait_for_existing_unaffected_bound_producer():
    raw=bound_definition()
    # Open b once with the named producer. A later rework of b must retain a's exact output.
    rt,pid,rows=setup(raw)
    rt.submit(rows['a']['id'],{'x':'kept'},now=NOW)
    request(rt,pid,rows['b']['id'])
    current=latest(rt,pid,'b')
    assert current['status']=='IN_PROGRESS' and current['reference_ids']==[rows['a']['id']]
    assert rt.workitem_view(current['id'])['inputs']=={'x':'kept'}
