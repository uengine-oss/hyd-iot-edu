from copy import deepcopy
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import engine, instance_mode, instances, procdb
from test_inbox import _people, KIM, PARK
from test_instances import DEF_PATH, FakeHooks, ALERT, NOW


def setup(monkeypatch):
    repo = procdb.MemoryRepo()
    _people(repo)
    rt = instances.InstanceRuntime(repo, engine.Definition.load(DEF_PATH), FakeHooks())
    monkeypatch.setattr(instance_mode, '_runtime', rt)
    app = FastAPI()
    instance_mode.mount(app, 'instance')
    return rt, TestClient(app)


def test_incident_lookup_ignores_recent_list_cutoff_and_omits_large_values(monkeypatch):
    rt, client = setup(monkeypatch)
    inst = rt.on_alert_raise(dict(ALERT, document='x' * 150000), now=NOW)
    inst['variables_data'].extend([{'key': 'huge_proposal', 'value': 'x' * 150000},
                                  {'key': 'result_report', 'value': {'outcome': '미달', 'level': 'fail', 'values': ['x'] * 50000}}])
    inst['variable_sources'] = {'document': {'provenance': ['x'] * 50000}}
    inst['flow_state'] = {'activity_arrivals': {str(i): {} for i in range(2000)}}
    rt.repo.update_instance(inst)
    for i in range(65):
        row = dict(deepcopy(inst), proc_inst_id=f'new-{i}', start_date=f'2026-10-26T12:00:{i:02d}Z', variables_data=[])
        rt.repo.insert_instance(row)
    rows = client.get('/api/instances', params={'incident': 'INC-1003-01', 'limit': 1}).json()
    assert len(rows) == 1 and rows[0]['proc_inst_id'] == inst['proc_inst_id']
    assert len(json.dumps(rows)) < 6000
    values = engine.variables(rows[0])
    assert values['result_report'] == {'outcome': '미달', 'level': 'fail'}
    assert engine.variables(rt.repo.get_instance(inst['proc_inst_id']))['huge_proposal']
    detail = client.get('/api/instances/' + inst['proc_inst_id']).json()['instance']
    assert detail['initial_variables']['alert']['document'] == 'x' * 150000


def test_human_question_requires_registered_instance_participant(monkeypatch):
    rt, client = setup(monkeypatch)
    inst = rt.on_alert_raise(ALERT, now=NOW)
    inst['role_bindings'] = [{'endpoint': 'role:operator'}]
    inst['participants'] = []
    rt.repo.update_instance(inst)
    wi = next(w for w in rt.repo.list_workitems(inst['proc_inst_id']) if w['status'] == 'IN_PROGRESS')
    wi.update(draft_status='HUMAN_ASKED', draft={'_human_request': {'job_id': 'question'}})
    rt.repo.update_workitem(wi)
    rt.repo.record_events([{'id': 'q', 'todo_id': wi['id'], 'proc_inst_id': inst['proc_inst_id'],
                           'job_id': 'question', 'event_type': 'human_asked', 'data': {}}])
    url = f"/api/todolist/{wi['id']}/human-response"
    for actor in ('담당자', 'user:missing', PARK):
        assert client.post(url, json={'job_id': 'question', 'answer': 'yes', 'by': actor}).status_code == 403
    assert client.post(url, json={'job_id': 'question', 'answer': 'yes', 'by': KIM}).status_code == 200


def test_human_form_checks_current_assignment(monkeypatch):
    rt, client = setup(monkeypatch)
    inst = rt.on_alert_raise(ALERT, now=NOW)
    wi = engine.new_workitem(rt.defn, inst, rt.defn.activities['task:escalate'], status='IN_PROGRESS')
    wi['user_id'] = KIM
    rt.repo.insert_workitems([wi])
    url = f"/api/todolist/{wi['id']}/submit"
    for actor in ('담당자', PARK):
        assert client.post(url, json={'output': {}, 'by': actor}).status_code == 403
    result = client.post(url, json={'output': {}, 'by': KIM})
    assert result.status_code == 200, result.text


def test_system_only_cycle_stops_without_recursion_error():
    definition = engine.Definition.from_dict({
        'processDefinitionId': 'loop-test', 'version': '1',
        'events': [{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}],
        'activities': [{'id': 'report', 'type': 'serviceTask', 'tool': 'process:report',
                        'service': {'outcome': '알림', 'title': '반복'}, 'outputData': ['result_report']}],
        'gateways': [{'id': 'gate', 'type': 'exclusiveGateway'}],
        'sequences': [{'id': 's1', 'source': 'start', 'target': 'report'},
                      {'id': 's2', 'source': 'report', 'target': 'gate'},
                      {'id': 's3', 'source': 'gate', 'target': 'report', 'condition': 'again == True'},
                      {'id': 's4', 'source': 'gate', 'target': 'end', 'condition': 'again != True'}]})
    rt = instances.InstanceRuntime(procdb.MemoryRepo(), definition, FakeHooks())
    inst = engine.new_instance(definition, {'again': True})
    rt.repo.insert_instance(inst)
    wi = engine.new_workitem(definition, inst, definition.activities['report'], status='SUBMITTED')
    wi.update(agent_orch='hyd-process', consumer=rt.consumer)
    rt.repo.insert_workitems([wi])
    rt._run_service(inst, wi, NOW)
    rows = rt.repo.list_workitems(inst['proc_inst_id'], limit=None)
    pending = [w for w in rows if w['status'] == 'PENDING']
    assert len(pending) == 1 and '100회' in pending[0]['log']
    assert len([w for w in rows if w['status'] == 'DONE' and w['activity_id'] == 'report']) == 101
    assert 'RecursionError' not in str(rows)
