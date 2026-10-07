from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import uuid

import pytest
from procsvc import engine, instances, procdb
from test_engine import NOW


def definition(agent=False):
    activities = [{'id': 'measure', 'name': 'Measure', 'type': 'userTask', 'role': 'Reviewer',
                   'tool': 'formHandler:score', 'outputData': ['score']},
                  {'id': 'check', 'name': 'Check', 'type': 'userTask', 'role': 'Reviewer',
                   'tool': 'formHandler:score', 'inputData': ['score'], 'outputData': ['score'], 'attachedEvents': ['deadline']},
                  {'id': 'finish', 'name': 'Finish', 'type': 'userTask', 'role': 'Reviewer',
                   'tool': 'formHandler:note', 'inputData': ['score'], 'outputData': ['note']}]
    if agent:
        activities[0].update(type='userTask', role='Agent', agentMode='COMPLETE', orchestration='cliagents')   # A116 product shape
    return engine.Definition.from_dict({
        'processDefinitionId': 'repeatable-inspection', 'processDefinitionName': 'Repeatable inspection', 'version': '1',
        'roles': [{'name': 'Reviewer', 'endpoint': 'role:operator'}, {'name': 'Agent', 'endpoint': 'sys:agent'}],
        'forms': {'score': {'fields_json': [{'key': 'score', 'type': 'number', 'text': 'Score'}]},
                  'note': {'fields_json': [{'key': 'note', 'type': 'text', 'text': 'Note'}]}},
        'activities': activities,
        'events': [{'id': 's', 'type': 'startEvent'}, {'id': 'e', 'type': 'endEvent'},
                   {'id': 'deadline', 'type': 'boundaryEvent', 'attachedTo': 'check', 'eventDefinition': 'timer', 'timer': 'PT10M'}],
        'sequences': [{'id': 's-m', 'source': 's', 'target': 'measure'}, {'id': 'm-c', 'source': 'measure', 'target': 'check'},
                      {'id': 'c-f', 'source': 'check', 'target': 'finish'}, {'id': 'f-e', 'source': 'finish', 'target': 'e'},
                      {'id': 't-e', 'source': 'deadline', 'target': 'e'}],
    })


def setup(agent=False):
    d = definition(agent); repo = procdb.MemoryRepo(); rt = instances.InstanceRuntime(repo, d, instances.Hooks(), time_scale=1)
    inst = rt.start_definition(d.id, '1', str(uuid.uuid4()), {'score': 2})
    return rt, inst['proc_inst_id']


def latest(rt, pid, aid):
    return engine._by_activity(rt.repo.list_workitems(proc_inst_id=pid, limit=None))[aid]


def request(rt, pid, wid, *, now=NOW, request_id=None, token=None, role='role:operator', reason='Changed inspection'):
    return rt.request_rework(pid, wid, request_id or str(uuid.uuid4()), token or rt.preview_rework(pid, wid)['snapshot_token'],
                             'Reviewer 1', role, reason, now=now)


def test_new_generation_preserves_old_outputs_and_fences_human_timer_and_references():
    rt, pid = setup(); first = latest(rt, pid, 'measure')
    rt.submit(first['id'], {'score': 7}, now=NOW)
    old_done = rt.repo.get_workitem(first['id']); old_check = latest(rt, pid, 'check'); old_timer = latest(rt, pid, 'deadline')
    result = request(rt, pid, first['id'])
    assert result['generation'] == 1
    assert rt.repo.get_workitem(first['id']) == old_done
    assert rt.repo.get_workitem(old_check['id'])['status'] == 'CANCELLED'
    assert rt.repo.get_workitem(old_timer['id'])['status'] == 'CANCELLED'
    new_first = latest(rt, pid, 'measure')
    assert new_first['id'] != first['id'] and new_first['supersedes_id'] == first['id'] and new_first['generation'] == 1
    assert engine.variables(rt.repo.get_instance(pid)) == {'score': 2}
    with pytest.raises(ValueError): rt.submit(old_check['id'], {'score': 99}, now=NOW)
    rt.submit(new_first['id'], {'score': 8}, now=NOW)
    current = latest(rt, pid, 'check'); timer = latest(rt, pid, 'deadline')
    assert current['reference_ids'] == [new_first['id']] and first['id'] not in current['reference_ids']
    assert timer['generation'] == 1 and timer['rework_request_id'] == result['request_id']
    assert rt.instance_view(pid)['timeline'][0]['workitem'] == new_first['id']
    rt.submit(current['id'], {'score': 9}, now=NOW)
    rt.submit(latest(rt, pid, 'finish')['id'], {'note': 'new result checked'}, now=NOW)
    assert rt.repo.get_instance(pid)['status'] == 'COMPLETED'
    assert rt.repo.get_workitem(first['id'])['output'] == {'score': 7}


def test_restart_overwriter_restores_valid_predecessor_not_initial_seed():
    rt, pid = setup(); rt.submit(latest(rt, pid, 'measure')['id'], {'score': 7}, now=NOW)
    checked = latest(rt, pid, 'check'); rt.submit(checked['id'], {'score': 9}, now=NOW)
    preview = rt.preview_rework(pid, checked['id'])
    assert preview['candidate_variables']['score'] == 7
    result = request(rt, pid, checked['id'])
    current = latest(rt, pid, 'check')
    assert current['id'] == result['start_workitem'] and '7' in current['query']
    assert engine.variables(rt.repo.get_instance(pid))['score'] == 7
    assert rt.repo.get_instance(pid)['initial_variables']['score'] == 2


def test_late_worker_result_cannot_write_into_new_generation():
    rt, pid = setup(agent=True)
    claimed = rt.repo.fetch_pending_task('cliagents', 'old-worker', tenant_id='hyd', proc_inst_id=pid)[0]
    result = request(rt, pid, claimed['id'])
    assert not rt.repo.save_task_result(claimed['id'], {'score': 999}, True, expected_consumer='old-worker')
    assert not rt.repo.update_task_error(claimed['id'], expected_consumer='old-worker')
    assert rt.repo.get_workitem(result['start_workitem'])['output'] is None
    new_claim = rt.repo.fetch_pending_task('cliagents', 'new-worker', tenant_id='hyd', proc_inst_id=pid)[0]
    assert new_claim['id'] == result['start_workitem']
    assert rt.repo.save_task_result(new_claim['id'], {'score': 6}, True, expected_consumer='new-worker')
    rt.poll_once(now=NOW)
    assert latest(rt, pid, 'check')['status'] == 'IN_PROGRESS'


def test_duplicate_and_concurrent_request_returns_one_committed_generation():
    rt, pid = setup(); wid = latest(rt, pid, 'measure')['id']; token = rt.preview_rework(pid, wid)['snapshot_token']; rid = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: request(rt, pid, wid, request_id=rid, token=token), range(4)))
    assert all(r == results[0] for r in results)
    assert len(rt.repo.list_reworks('hyd', pid)) == 1 and rt.repo.get_instance(pid)['rework_generation'] == 1
    assert len([e for e in rt.repo.list_events(proc_inst_id=pid) if e['job_id'] == 'PROCESS_REWORK']) == 1
    with pytest.raises(ValueError, match='다른 재작업'): request(rt, pid, wid, request_id=rid, token=token, reason='different')


def test_stale_preview_and_wrong_role_leave_no_generation():
    rt, pid = setup(); wid = latest(rt, pid, 'measure')['id']; token = rt.preview_rework(pid, wid)['snapshot_token']
    with pytest.raises(PermissionError): request(rt, pid, wid, token=token, role='outsider')
    rt.submit(wid, {'score': 7}, now=NOW)
    with pytest.raises(ValueError, match='바뀌었습니다'): request(rt, pid, wid, token=token)
    assert rt.repo.list_reworks('hyd', pid) == []


def test_last_write_failure_rolls_back_every_row_receipt_and_event(monkeypatch):
    rt, pid = setup(); wid = latest(rt, pid, 'measure')['id']
    before = deepcopy((rt.repo.instances, rt.repo.workitems, rt.repo.reworks, rt.repo.events))
    monkeypatch.setattr(rt.repo, 'record_events', lambda _: (_ for _ in ()).throw(OSError('final write failed')))
    with pytest.raises(OSError): request(rt, pid, wid)
    assert (rt.repo.instances, rt.repo.workitems, rt.repo.reworks, rt.repo.events) == before


def test_second_generation_uses_generation_not_time_or_retry_count():
    rt, pid = setup(); wid = latest(rt, pid, 'measure')['id']; request(rt, pid, wid, now=NOW + timedelta(days=10))
    prior = latest(rt, pid, 'measure'); result = request(rt, pid, prior['id'], now=NOW)
    assert latest(rt, pid, 'measure')['id'] == result['start_workitem'] and result['generation'] == 2
    assert rt.instance_view(pid)['timeline'][0]['generation'] == 2


def test_workitem_generation_metadata_is_immutable():
    rt, pid = setup(); row = latest(rt, pid, 'measure'); row['generation'] = 8
    with pytest.raises(ValueError, match='immutable'): rt.repo.update_workitem(row)
