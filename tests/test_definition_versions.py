"""A running instance and its worker must keep the definition they started with."""
from copy import deepcopy
from pathlib import Path

import pytest

from procsvc import engine, instances, procdb
from worker.context import prepare, activity_capabilities

SOURCE = Path(__file__).resolve().parents[1] / 'it/process/definitions/anomaly_response.json'


def definitions():
    first = deepcopy(engine.Definition.load(SOURCE).raw)
    first['activities'][0]['agentConfig'] = {'model': 'model-v1'}
    second = deepcopy(first)
    second['version'] = '2.0'
    second['ontologyRef'] = 'proc:version-two'
    second['activities'][0]['agentConfig'] = {'model': 'model-v2'}
    return first, second


def test_versions_are_immutable_and_explicit_missing_version_never_falls_back():
    repo = procdb.MemoryRepo()
    first, second = definitions()
    repo.upsert_proc_def(first)
    repo.upsert_proc_def(second)
    assert repo.get_proc_def(first['processDefinitionId'], version='1.0')['definition'] == first
    assert repo.get_proc_def(first['processDefinitionId'])['definition'] == second
    changed = deepcopy(first); changed['description'] = 'silently changed'
    with pytest.raises(ValueError, match='version|버전'):
        repo.upsert_proc_def(changed)
    assert repo.get_proc_def(first['processDefinitionId'], version='missing') is None


def test_new_runtime_processes_old_instance_using_its_own_version():
    repo = procdb.MemoryRepo()
    first, second = definitions()
    receipt=lambda q,**p:[dict(projection_key=p['id'],projection_revision=p['revision'],projection_hash=p['payload_hash'])]
    rt1 = instances.InstanceRuntime(repo, engine.Definition.from_dict(first), instances.Hooks(record_cypher=receipt))
    inst = rt1.on_alert_raise({'alertId': 'old', 'asset': 'HYD-01', 'pattern':'COOLER_DEGRADATION'})
    old_task = next(w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['status'] == 'IN_PROGRESS')
    old_id = old_task['activity_id']
    for a in second['activities']:
        if a['id'] == old_id:
            a['id'] = 'new-diagnosis'
    for seq in second['sequences']:
        for end in ('source', 'target'):
            if seq[end] == old_id:
                seq[end] = 'new-diagnosis'
    projected = []
    rt2 = instances.InstanceRuntime(repo, engine.Definition.from_dict(second),
                                    instances.Hooks(record_cypher=lambda q, **p: projected.append(p) or receipt(q,**p)))
    out = rt2.submit(old_task['id'], {'cause': 'cause:test', 'failure_mode': 'fm:test', 'guide_card': {}})
    assert out['workitem']['status'] == 'DONE'
    assert projected[-1]['process'] == first['ontologyRef']
    assert rt2.instance_view(inst['proc_inst_id'])['timeline'][0]['activity_id'] == old_id
    new = rt2.on_alert_raise({'alertId': 'new', 'asset': 'HYD-01', 'pattern':'COOLER_DEGRADATION'})
    assert new['proc_def_version'] == '2.0'
    assert any(w['activity_id'] == 'new-diagnosis' for w in repo.list_workitems(proc_inst_id=new['proc_inst_id']))


def test_worker_capabilities_resolve_the_workitems_version():
    repo = procdb.MemoryRepo()
    first, second = definitions()
    repo.upsert_proc_def(first)
    repo.upsert_proc_def(second)
    row = {'id': 'w', 'proc_def_id': first['processDefinitionId'], 'version': '1.0', 'activity_id': first['activities'][0]['id']}
    ctx = prepare(repo, row, 'hyd')
    assert activity_capabilities(ctx.definition, row['activity_id'])['agent_config']['model'] == 'model-v1'


def test_missing_pinned_definition_blocks_runtime():
    repo = procdb.MemoryRepo()
    first, _ = definitions()
    rt = instances.InstanceRuntime(repo, engine.Definition.from_dict(first), instances.Hooks())
    inst = rt.on_alert_raise({'alertId': 'missing', 'asset': 'HYD-01', 'pattern':'COOLER_DEGRADATION'})
    inst['proc_def_version'] = 'unknown'
    repo.update_instance(inst)
    with pytest.raises(LookupError, match='definition|정의'):
        rt.instance_view(inst['proc_inst_id'])
