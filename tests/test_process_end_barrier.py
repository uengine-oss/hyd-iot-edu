"""An end arrival consumes one path; other admitted work must finish first."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import uuid
import pytest

from procsvc import engine, instances, procdb, definition_registry
from test_engine import NOW


def definition():
    return {
        'processDefinitionId': 'independent-reviews', 'processDefinitionName': 'Independent reviews', 'version': '1',
        'roles': [{'name': 'Reviewer', 'endpoint': 'role:operator'}],
        'data': [{'name': 'a', 'type': 'Text'}, {'name': 'b', 'type': 'Text'}],
        'forms': {key: {'fields_json': [{'key': key, 'type': 'text', 'text': key}]}
                  for key in ('a', 'b')},
        'activities': [{'id': key, 'type': 'userTask', 'role': 'Reviewer',
                        'tool': 'formHandler:' + key, 'outputData': [key]}
                       for key in ('a', 'b')],
        'events': [{'id': 'start', 'type': 'startEvent'},
                   {'id': 'end-a', 'type': 'endEvent'}, {'id': 'end-b', 'type': 'endEvent'}],
        'gateways': [],
        'sequences': [{'id': 's-' + key, 'source': 'start', 'target': key} for key in ('a', 'b')]
                     + [{'id': key + '-e', 'source': key, 'target': 'end-' + key} for key in ('a', 'b')],
    }


def setup(raw=None):
    raw = raw or definition()
    d = definition_registry.validate_definition(raw)
    repo = procdb.MemoryRepo()
    rt = instances.InstanceRuntime(repo, d, instances.Hooks())
    inst = rt.start_definition(d.id, '1', str(uuid.uuid4()), now=NOW)
    rows = {w['activity_id']: w for w in repo.list_workitems(proc_inst_id=inst['proc_inst_id'], limit=None)}
    return rt, inst['proc_inst_id'], rows


def test_one_end_does_not_close_another_live_path():
    rt, pid, rows = setup()
    rt.submit(rows['a']['id'], {'a': 'first'}, now=NOW)
    inst = rt.repo.get_instance(pid)
    assert inst['status'] == 'RUNNING' and inst['end_event'] is None
    assert inst['current_activity_ids'] == ['b']
    assert rt.repo.get_workitem(rows['b']['id'])['status'] == 'IN_PROGRESS'
    assert inst['flow_state']['end_arrivals'][0]['workitem'] == rows['a']['id']
    assert inst['flow_state']['end_arrivals'][0]['event'] == 'end-a'


def test_waiting_end_survives_new_runtime_then_both_paths_complete():
    rt, pid, rows = setup()
    rt.submit(rows['a']['id'], {'a': 'first'}, now=NOW)
    saved = deepcopy(rt.repo.get_instance(pid)['flow_state'])
    resumed = instances.InstanceRuntime(rt.repo, rt.defn, instances.Hooks())
    resumed.submit(rows['b']['id'], {'b': 'second'}, now=NOW)
    inst = resumed.repo.get_instance(pid)
    assert inst['status'] == 'COMPLETED' and inst['end_event'] == 'end-b'
    assert len(inst['flow_state']['end_arrivals']) == 2
    assert saved['end_arrivals'][0] == inst['flow_state']['end_arrivals'][0]
    assert all(w['status'] == 'DONE' for w in resumed.repo.list_workitems(proc_inst_id=pid, limit=None))


def test_concurrent_path_completion_keeps_both_results_and_end_arrivals():
    rt, pid, rows = setup()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda key: rt.submit(rows[key]['id'], {key: key}, now=NOW), ('a', 'b')))
    inst = rt.repo.get_instance(pid)
    assert inst['status'] == 'COMPLETED'
    assert engine.variables(inst) == {'a': 'a', 'b': 'b'}
    assert {a['workitem'] for a in inst['flow_state']['end_arrivals']} == {r['id'] for r in rows.values()}


@pytest.mark.parametrize('status', ['PENDING', 'SUBMITTED'])
def test_pending_or_submitted_other_path_is_not_silently_finished(status):
    rt, pid, rows = setup()
    row = rt.repo.get_workitem(rows['b']['id'])
    row['status'] = status
    rt.repo.update_workitem(row)
    rt.submit(rows['a']['id'], {'a': 'first'}, now=NOW)
    assert rt.repo.get_instance(pid)['status'] == 'RUNNING'
    assert rt.repo.get_workitem(row['id'])['status'] == status


def test_rework_retires_only_affected_end_arrival_and_preserves_its_evidence():
    rt, pid, rows = setup()
    rt.submit(rows['a']['id'], {'a': 'first'}, now=NOW)
    prior = deepcopy(rt.repo.get_instance(pid)['flow_state']['end_arrivals'])
    preview = rt.preview_rework(pid, rows['a']['id'])
    rid = str(uuid.uuid4())
    result = rt.request_rework(pid, rows['a']['id'], rid, preview['snapshot_token'],
                              'reviewer', 'role:operator', 'changed measurement', now=NOW)
    state = rt.repo.get_instance(pid)['flow_state']
    assert state['end_arrivals'] == []
    assert state['superseded_end_arrivals'] == [{'request_id': rid, 'arrivals': prior}]
    rt.submit(rows['b']['id'], {'b': 'second'}, now=NOW)
    assert rt.repo.get_instance(pid)['status'] == 'RUNNING'
    rt.submit(result['start_workitem'], {'a': 'new'}, now=NOW)
    inst = rt.repo.get_instance(pid)
    assert inst['status'] == 'COMPLETED'
    assert {a['event']: a['generation'] for a in inst['flow_state']['end_arrivals']} == {'end-a': 1, 'end-b': 0}
    assert rt.repo.get_workitem(rows['a']['id'])['output'] == {'a': 'first'}


def test_failure_to_persist_instance_rolls_back_task_and_end_arrival(monkeypatch):
    rt, pid, rows = setup()
    before = deepcopy((rt.repo.instances, rt.repo.workitems, rt.repo.events))
    def failure(*args): raise OSError('storage failed')
    monkeypatch.setattr(rt.repo, 'update_instance', failure)
    with pytest.raises(OSError): rt.submit(rows['a']['id'], {'a': 'first'}, now=NOW)
    assert (rt.repo.instances, rt.repo.workitems, rt.repo.events) == before


def test_reworking_one_path_preserves_other_arrival_at_the_same_end():
    raw = definition()
    raw['sequences'][-1]['target'] = 'end-a'
    rt, pid, rows = setup(raw)
    rt.submit(rows['b']['id'], {'b': 'retained'}, now=NOW)
    before = deepcopy(rt.repo.get_instance(pid)['flow_state']['end_arrivals'])
    preview = rt.preview_rework(pid, rows['a']['id'])
    result = rt.request_rework(pid, rows['a']['id'], str(uuid.uuid4()), preview['snapshot_token'],
                              'reviewer', 'role:operator', 'new first path', now=NOW)
    assert rt.repo.get_instance(pid)['flow_state']['end_arrivals'] == before
    rt.submit(result['start_workitem'], {'a': 'new'}, now=NOW)
    arrivals = rt.repo.get_instance(pid)['flow_state']['end_arrivals']
    assert len(arrivals) == 2 and {a['event'] for a in arrivals} == {'end-a'}
