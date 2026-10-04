"""Dependency/provenance counterexamples; planning is never execution approval."""
from copy import deepcopy
import pytest

from procsvc import engine, rework, instances, procdb
from test_engine import NOW, World, defn


def arbitrary():
    raw = {
        'processDefinitionId': 'unrelated-business', 'version': 'v8',
        'events': [{'id': 's', 'type': 'startEvent'}, {'id': 'e', 'type': 'endEvent'},
                   {'id': 'late', 'type': 'boundaryEvent', 'attachedTo': 'b', 'eventDefinition': 'timer', 'timer': 'PT5M'}],
        'activities': [
            {'id': 'a', 'type': 'userTask', 'inputData': ['seed'], 'outputData': ['x']},
            {'id': 'b', 'type': 'userTask', 'inputData': ['x'], 'outputData': ['y']},
            {'id': 'c', 'type': 'userTask', 'inputData': ['y'], 'outputData': []},
            {'id': 'other', 'type': 'userTask', 'outputData': ['keep']},
        ],
        'gateways': [{'id': 'g', 'type': 'exclusiveGateway'}],
        'sequences': [{'id': 'sa', 'source': 's', 'target': 'a'},
                      {'id': 'ae', 'source': 'a', 'target': 'e'},
                      {'id': 'le', 'source': 'late', 'target': 'e'}],
    }
    d = engine.Definition.from_dict(raw)
    i = engine.new_instance(d, {'seed': {'value': 4}, 'x': 1}, now=NOW)
    rows = [engine.new_workitem(d, i, a, NOW, 'DONE') for a in d.activities.values()]
    for w in rows:
        output = {'a': {'x': 8}, 'b': {'y': 9}, 'other': {'keep': 17}}.get(w['activity_id'], {})
        w['output'] = output
        engine.set_variables(d, i, output, source={'kind': 'workitem', 'id': w['id'],
                             'activity': w['activity_id'], 'version': w['version']})
    rows.append(engine.new_event_workitem(d, i, d.events['late'], NOW))
    return d, i, rows


def test_transitive_data_and_boundary_paths_keep_unaffected_evidence():
    d, i, rows = arbitrary(); before = deepcopy((d.raw, i, rows))
    result = rework.plan(d, i, rows, rows[0]['id'])
    assert set(result['affected_nodes']) == {'a', 'b', 'c', 'late', 'e'}
    assert result['candidate_variables'] == {'seed': {'value': 4}, 'x': 1, 'keep': 17}
    assert result['restored_input_variables'] == ['x']
    assert result['invalidated_variables'] == ['x', 'y']
    assert result['cancel_workitems'] == [rows[-1]['id']]
    # A DONE row without any incoming control path is not arrival evidence.
    assert {b['code'] for b in result['blockers']} == {'dependency_control_arrival_unavailable'}
    assert result['execution_available'] is False
    assert (d.raw, i, rows) == before
    result['candidate_variables']['seed']['value'] = 99
    assert i['initial_variables']['seed']['value'] == 4


def test_condition_dependency_without_input_data_reaches_all_branches():
    d, i, rows = arbitrary()
    d.sequences += [{'id': 'gc', 'source': 'g', 'target': 'c', 'condition': 'x > 5'},
                    {'id': 'go', 'source': 'g', 'target': 'other'}]
    result = rework.plan(d, i, rows, rows[0]['id'])
    assert 'g' in result['affected_nodes'] and 'other' in result['affected_nodes']
    assert 'keep' not in result['candidate_variables']


def test_runtime_reference_adds_a_dependency_absent_from_the_definition():
    d, i, rows = arbitrary(); rows[3]['reference_ids'] = [rows[0]['id']]
    result = rework.plan(d, i, rows, rows[0]['id'])
    assert 'other' in result['affected_nodes'] and 'keep' not in result['candidate_variables']


@pytest.mark.parametrize('defect', ['missing', 'runtime', 'bad_id', 'bad_version', 'bad_value', 'cancelled'])
def test_unproven_current_output_is_not_reused(defect):
    d, i, rows = arbitrary()
    if defect == 'missing': i['variable_sources'].pop('keep')
    if defect == 'runtime': i['variable_sources']['keep'] = {'kind': 'runtime'}
    if defect == 'bad_id': i['variable_sources']['keep']['id'] = 'unavailable'
    if defect == 'bad_version': i['variable_sources']['keep']['version'] = 'different'
    if defect == 'bad_value': rows[3]['output']['keep'] = 999
    if defect == 'cancelled': rows[3]['status'] = 'CANCELLED'
    result = rework.plan(d, i, rows, rows[0]['id'])
    assert 'keep' not in result['candidate_variables']
    assert any(b['code'] == 'variable_provenance_requires_review' and b['variable'] == 'keep' for b in result['blockers'])


def test_legacy_inputs_remain_unknown_and_finished_instance_is_not_reopened():
    d, i, rows = arbitrary(); i['initial_variables'] = None; i['status'] = 'COMPLETED'
    result = rework.plan(d, i, rows, rows[0]['id'])
    assert {'initial_inputs_unavailable', 'instance_not_running'} <= {b['code'] for b in result['blockers']}
    assert 'seed' not in result['candidate_variables'] and 'x' not in result['candidate_variables']


def test_same_timestamp_needs_explicit_generation_not_cmms_retry_count():
    d, i, rows = arbitrary(); old = deepcopy(rows[0]); old['id'] = 'old'; old['rework_count'] = 999
    rows.append(old)
    result = rework.plan(d, i, rows, rows[0]['id'])
    assert {'code': 'ambiguous_workitem_order', 'activity': 'a'} in result['blockers']


@pytest.mark.parametrize('field,value', [('tenant_id', 'other'), ('version', 'v9'), ('proc_inst_id', 'other')])
def test_cross_scope_rows_rejected(field, value):
    d, i, rows = arbitrary(); rows[1][field] = value
    with pytest.raises(ValueError, match='섞였습니다'): rework.plan(d, i, rows, rows[0]['id'])


def test_hyd_flow_includes_timer_and_side_effect_review(defn):
    world = World(defn); world.agent_tasks()
    command = world.row('task:command'); command['status'] = 'CANCELLED'; command['log'] = 'issued once'
    approval = {'todo_id': world.row('task:select')['id'], 'proc_inst_id': world.inst['proc_inst_id'],
                'tenant_id': 'hyd', 'decision_id': 'D', 'status': 'FAILED'}
    result = rework.plan(defn, world.inst, world.rows, world.row('task:diagnose')['id'], [approval])
    assert set(defn.activities) <= set(result['affected_nodes']) and 'ev:select-timeout' in result['affected_nodes']
    assert 'decision_id' not in result['candidate_variables']
    assert {'approval_requires_review', 'service_effects_require_review'} <= {b['code'] for b in result['blockers']}


def test_runtime_preview_is_read_only_pinned_and_snapshot_changes_with_claim():
    d, i, rows = arbitrary(); repo = procdb.MemoryRepo()
    rt = instances.InstanceRuntime(repo, d, instances.Hooks())
    repo.insert_instance(i); repo.insert_workitems(rows)
    before = deepcopy((repo.instances, repo.workitems, repo.events))
    result = rt.preview_rework(i['proc_inst_id'], rows[0]['id'])
    assert (repo.instances, repo.workitems, repo.events) == before
    assert result == rt.preview_rework(i['proc_inst_id'], rows[0]['id'])
    row = repo.get_workitem(rows[0]['id']); row['consumer'] = 'claimed'; repo.update_workitem(row)
    assert result['snapshot_token'] != rt.preview_rework(i['proc_inst_id'], rows[0]['id'])['snapshot_token']
    other = instances.InstanceRuntime(repo, d, instances.Hooks(), tenant_id='other')
    with pytest.raises(KeyError): other.preview_rework(i['proc_inst_id'], rows[0]['id'])
