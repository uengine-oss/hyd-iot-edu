from copy import deepcopy
import pytest
from procsvc import engine, procdb
from test_engine import defn, NOW, World, AGENT_OUTPUTS


def test_start_input_is_independent_of_later_caller_and_runtime_changes(defn):
    supplied={'asset':'HYD-01','request':{'limit':12}}
    inst=engine.new_instance(defn,supplied,now=NOW)
    supplied['request']['limit']=90
    engine.set_variables(defn,inst,{'asset':'HYD-02'})
    assert inst['initial_variables']=={'asset':'HYD-01','request':{'limit':12}}
    assert inst['variable_sources']['request']=={'kind':'input'}
    assert inst['variable_sources']['asset']=={'kind':'runtime'}


def test_completed_agent_output_names_producing_work_item(defn):
    world=World(defn,values={'asset':'HYD-01'})
    wi=next(w for w in world.rows if w['activity_id']=='task:diagnose')
    engine.submit(defn,world.inst,wi,AGENT_OUTPUTS['task:diagnose'],now=NOW)
    engine.process_submitted(defn,world.inst,wi,world.rows,now=NOW)
    source=world.inst['variable_sources']['cause']
    assert source=={'kind':'workitem','id':wi['id'],'activity':'task:diagnose','version':wi['version']}
    assert 'cause' not in world.inst['initial_variables']


def test_memory_store_rejects_start_input_replacement_and_removal(defn):
    repo=procdb.MemoryRepo();inst=engine.new_instance(defn,{'asset':'HYD-01'},now=NOW);repo.insert_instance(inst)
    for value in ({'asset':'wrong'},None):
        changed=deepcopy(inst);changed['initial_variables']=value
        with pytest.raises(ValueError,match='시작 입력'):
            repo.update_instance(changed)
    assert repo.get_instance(inst['proc_inst_id'])['initial_variables']=={'asset':'HYD-01'}


def test_old_instance_has_no_invented_input_provenance(defn):
    inst=engine.new_instance(defn,{'asset':'HYD-01'},now=NOW)
    inst.pop('initial_variables',None);inst.pop('variable_sources',None)
    engine.set_variables(defn,inst,{'note':'operator annotation'})
    assert 'initial_variables' not in inst
    assert inst['variable_sources']=={'note':{'kind':'runtime'}}
