"""U4 (TODO 4): the deployed version — an alert opens the deployed version, open instances finish on theirs, only a version
that passes validate_definition can be deployed, rollback returns to the previously deployed version, and a restart keeps
the deployment instead of re-seeding from the file."""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import instance_mode, instances, procdb
from procsvc.definition_diff import compare
from test_engine import AGENT_OUTPUTS
from test_instance_mode import world, ALERT  # noqa: F401 — fixture


def _version_b(rt, version='2.3-test'):
    raw = deepcopy(rt.deployed_definition().raw)
    raw['version'] = version
    raw['description'] = 'B: 원인 진단 이름을 바꾸고 선택 시간제한을 줄인 판본'
    next(a for a in raw['activities'] if a['id'] == 'task:diagnose')['name'] = '원인 진단 (B)'
    next(e for e in raw['events'] if e['id'] == 'ev:select-timeout')['timer'] = 'PT5M'
    return raw


def _finish_by_escalation(rt, inst):
    """Agent outputs → select timeout → escalation note → ev:escalated (the shortest complete path without PLC/CMMS)."""
    for aid, output in AGENT_OUTPUTS.items():
        item = next(w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id'] == aid)
        rt.submit(item['id'], output)
    timer = next(w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id'] == 'ev:select-timeout')
    rt.fire_timeouts(now=datetime.fromisoformat(timer['due_date'].replace('Z', '+00:00')) + timedelta(seconds=1))
    esc = next(w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id'] == 'task:escalate')
    rt.submit(esc['id'], {'note': '현장 확인'})
    return rt.repo.get_instance(inst['proc_inst_id'])


def test_seed_deploys_the_file_once_and_registration_does_not_move_the_pointer(world):
    rt = world['rt']
    assert rt.repo.deployed_version('anomaly_response') == '2.2'
    history = rt.repo.list_deployments('anomaly_response')
    assert [h['action'] for h in history] == ['seed'] and history[0]['previous_version'] is None
    rt.register_definition(_version_b(rt))
    assert rt.repo.deployed_version('anomaly_response') == '2.2'          # registering is not deploying
    assert rt.repo.get_proc_def('anomaly_response')['prod_version'] == '2.2'
    status = rt.definition_status('anomaly_response')
    assert [v['version'] for v in status['versions']] == ['2.2', '2.3-test']
    assert [v['deployed'] for v in status['versions']] == [True, False] and all(v['deployable'] for v in status['versions'])
    assert status['alert_entry'] and status['rollback_version'] is None


def test_new_alert_opens_the_deployed_version_while_an_open_instance_finishes_on_its_own(world):
    rt = world['rt']
    opened_on_a = rt.on_alert_raise(dict(ALERT, alertId='A-1'))
    assert opened_on_a['proc_def_version'] == '2.2'
    rt.register_definition(_version_b(rt))
    out = rt.deploy_definition('anomaly_response', '2.3-test', by='강사', reason='선택 시간제한 5분 실습')
    assert out['previous_version'] == '2.2' and out['applies_to'] == '다음 경보부터'
    assert 'DEFINITION_DEPLOYED' in world['audits']
    opened_on_b = rt.on_alert_raise(dict(ALERT, alertId='B-1'))
    assert opened_on_b['proc_def_version'] == '2.3-test'
    diagnose_b = next(w for w in rt.repo.list_workitems(proc_inst_id=opened_on_b['proc_inst_id']) if w['activity_id'] == 'task:diagnose')
    assert diagnose_b['activity_name'] == '원인 진단 (B)' and diagnose_b['version'] == '2.3-test'
    # the instance opened on A keeps A's definition (name, 10-minute timer) to the end
    assert rt.definition_for(rt.repo.get_instance(opened_on_a['proc_inst_id'])).raw['version'] == '2.2'
    diagnose_a = next(w for w in rt.repo.list_workitems(proc_inst_id=opened_on_a['proc_inst_id']) if w['activity_id'] == 'task:diagnose')
    assert diagnose_a['activity_name'] == '원인 진단' and diagnose_a['version'] == '2.2'
    saved = _finish_by_escalation(rt, opened_on_a)
    assert saved['status'] == 'COMPLETED' and saved['end_event'] == 'ev:escalated' and saved['proc_def_version'] == '2.2'
    assert all(w['version'] == '2.2' for w in rt.repo.list_workitems(proc_inst_id=opened_on_a['proc_inst_id']))
    # and the B instance also runs to the end on B
    saved_b = _finish_by_escalation(rt, opened_on_b)
    assert saved_b['status'] == 'COMPLETED' and saved_b['proc_def_version'] == '2.3-test'
    assert rt.deployed_definition().raw['version'] == '2.3-test'


def test_a_version_that_fails_validation_cannot_be_deployed(world):
    rt = world['rt']
    broken = _version_b(rt, version='broken')
    broken.pop('forms')                        # validate_definition: forms are required
    rt.repo.upsert_proc_def(broken)            # stored without the API check (like the legacy 1.0 backfill)
    status = rt.definition_status('anomaly_response')
    bad = next(v for v in status['versions'] if v['version'] == 'broken')
    assert not bad['deployable'] and 'forms' in bad['problem']
    with pytest.raises(ValueError, match='검사를 통과하지 못한'):
        rt.deploy_definition('anomaly_response', 'broken', by='강사', reason='시험')
    assert rt.repo.deployed_version('anomaly_response') == '2.2'
    with pytest.raises(LookupError):
        rt.deploy_definition('anomaly_response', 'nope', by='강사', reason='시험')
    with pytest.raises(ValueError, match='이미 운영 판본'):
        rt.deploy_definition('anomaly_response', '2.2', by='강사', reason='시험')
    with pytest.raises(ValueError, match='사유'):
        rt.deploy_definition('anomaly_response', '2.2', by='강사', reason=' ')


def test_rollback_returns_to_the_previously_deployed_version(world):
    rt = world['rt']
    with pytest.raises(ValueError, match='되돌릴 이전'):
        rt.rollback_definition('anomaly_response', by='강사', reason='없음')
    rt.register_definition(_version_b(rt))
    rt.deploy_definition('anomaly_response', '2.3-test', by='강사', reason='실습')
    assert rt.on_alert_raise(dict(ALERT, alertId='on-b'))['proc_def_version'] == '2.3-test'
    out = rt.rollback_definition('anomaly_response', by='강사', reason='타이머가 너무 짧음')
    assert out['version'] == '2.2' and out['previous_version'] == '2.3-test' and out['action'] == 'rollback'
    assert rt.on_alert_raise(dict(ALERT, alertId='back-on-a'))['proc_def_version'] == '2.2'
    history = rt.repo.list_deployments('anomaly_response')
    assert [(h['action'], h['version'], h['previous_version']) for h in history] == \
        [('rollback', '2.2', '2.3-test'), ('deploy', '2.3-test', '2.2'), ('seed', '2.2', None)]
    assert history[0]['actor'] == '강사' and history[0]['reason'] == '타이머가 너무 짧음'
    assert rt.definition_status('anomaly_response')['rollback_version'] == '2.3-test'   # rolling back again goes forward to B


def test_restart_loads_the_deployed_version_not_the_seed_file(world):
    rt = world['rt']
    rt.register_definition(_version_b(rt))
    rt.deploy_definition('anomaly_response', '2.3-test', by='강사', reason='실습')
    booted = instance_mode._bootstrap_definition(rt.repo, 'hyd')           # same file env, DB says 2.3-test
    assert booted.raw['version'] == '2.3-test'
    restarted = instances.InstanceRuntime(rt.repo, booted, rt.hooks, consumer='restarted')
    assert [h['action'] for h in rt.repo.list_deployments('anomaly_response')] == ['deploy', 'seed']   # no second seed
    assert restarted.on_alert_raise(dict(ALERT, alertId='after-restart'))['proc_def_version'] == '2.3-test'
    assert rt.repo.deployed_version('anomaly_response') == '2.3-test'


def test_compare_lists_added_removed_and_changed_elements_for_people():
    a = {'processDefinitionId': 'p', 'processDefinitionName': '검토', 'version': '1',
         'activities': [{'id': 't1', 'name': '점수 검토', 'type': 'userTask', 'role': '검토자', 'tool': 'formHandler:f', 'outputData': ['score']}],
         'events': [{'id': 's', 'type': 'startEvent'}, {'id': 'ok', 'type': 'endEvent'}],
         'gateways': [{'id': 'g', 'type': 'exclusiveGateway'}],
         'sequences': [{'id': 's1', 'source': 's', 'target': 't1'}, {'id': 's2', 'source': 't1', 'target': 'g'},
                       {'id': 's3', 'source': 'g', 'target': 'ok', 'condition': 'score >= 5'}],
         'data': [{'name': 'score', 'type': 'Number'}], 'roles': [{'name': '검토자', 'endpoint': 'role:operator'}],
         'forms': {'f': {'fields_json': [{'key': 'score', 'type': 'number', 'text': '점수'}]}}}
    b = deepcopy(a); b['version'] = '2'
    b['activities'][0]['name'] = '점수 재검토'
    b['activities'].append({'id': 't2', 'name': '메모', 'type': 'userTask', 'role': '검토자', 'tool': 'formHandler:f2', 'outputData': ['note']})
    b['sequences'][2]['condition'] = 'score >= 10'
    del b['sequences'][1]
    b['sequences'] += [{'id': 's4', 'source': 't1', 'target': 't2'}, {'id': 's5', 'source': 't2', 'target': 'g'}]
    b['forms']['f2'] = {'fields_json': [{'key': 'note', 'type': 'text', 'text': '메모'}]}
    b['data'].append({'name': 'note', 'type': 'Text'})
    diff = compare(a, b)
    assert diff['from']['version'] == '1' and diff['to']['version'] == '2' and not diff['same']
    assert diff['counts'] == {'추가': 5, '삭제': 1, '변경': 2}
    texts = [c['text'] for c in diff['changes']]
    assert '단계 "점수 재검토"(t1) 변경: 이름' in texts
    assert '단계 "메모"(t2) 추가' in texts
    assert '연결 점수 재검토 → g (s2) 삭제' in texts or '연결 점수 검토 → g (s2) 삭제' in texts
    assert '연결 g → ok (s3) 변경: 분기 조건' in texts
    assert '폼 f2 추가' in texts and '변수 note 추가' in texts
    cond = next(c for c in diff['changes'] if c['id'] == 's3')
    assert cond['fields'] == [{'label': '분기 조건', 'key': 'condition', 'before': 'score >= 5', 'after': 'score >= 10'}]
    assert cond['flow'] == {'from': 'g', 'to': 'ok'}
    assert compare(a, a)['same'] and compare(a, a)['changes'] == []


def test_http_versions_compare_deploy_and_rollback(world, monkeypatch):
    rt = world['rt']
    monkeypatch.setattr(instance_mode, '_runtime', rt)
    app = FastAPI(); instance_mode.mount(app, 'instance'); client = TestClient(app)
    assert client.get('/api/process/mode').json()['deployed_version'] == '2.2'
    assert client.get('/api/process/definition').json()['version'] == '2.2'
    assert client.post('/api/process/definitions', json={'definition': _version_b(rt)}).status_code == 201
    rows = client.get('/api/process/definitions').json()
    assert {(r['version'], r['deployed']) for r in rows if r['id'] == 'anomaly_response'} == {('2.2', True), ('2.3-test', False)}
    status = client.get('/api/process/definitions/anomaly_response/versions').json()
    assert status['deployed_version'] == '2.2' and len(status['versions']) == 2 and status['history'][0]['action'] == 'seed'
    assert client.get('/api/process/definitions/missing/versions').status_code == 404
    diff = client.get('/api/process/definitions/anomaly_response/compare', params={'from_version': '2.2', 'to_version': '2.3-test'}).json()
    assert diff['counts']['변경'] == 3 and {c['id'] for c in diff['changes']} == {'description', 'task:diagnose', 'ev:select-timeout'}
    assert client.get('/api/process/definitions/anomaly_response/compare', params={'from_version': '2.2', 'to_version': 'x'}).status_code == 404
    assert client.post('/api/process/definitions/anomaly_response/deploy', json={'version': '2.3-test', 'by': '강사', 'reason': ''}).status_code == 422
    assert client.post('/api/process/definitions/anomaly_response/deploy', json={'version': 'x', 'by': '강사', 'reason': '시험'}).status_code == 404
    assert client.post('/api/process/definitions/anomaly_response/deploy', json={'version': '2.2', 'by': '강사', 'reason': '시험'}).status_code == 409
    res = client.post('/api/process/definitions/anomaly_response/deploy', json={'version': '2.3-test', 'by': '강사', 'reason': '실습'})
    assert res.status_code == 200 and res.json()['version'] == '2.3-test'
    assert client.get('/api/process/definition').json()['version'] == '2.3-test'
    assert client.post('/api/instances/start', json={'alert': dict(ALERT, alertId='via-http')}).json()['proc_def_version'] == '2.3-test'
    res = client.post('/api/process/definitions/anomaly_response/rollback', json={'by': '강사', 'reason': '되돌림'})
    assert res.status_code == 200 and res.json()['version'] == '2.2'
    assert client.post('/api/process/definitions/anomaly_response/rollback', json={'by': '강사', 'reason': '또'}).json()['version'] == '2.3-test'
    assert len(client.get('/api/process/definitions/anomaly_response/versions').json()['history']) == 4


def test_memory_repo_deployment_rejects_unknown_versions():
    repo = procdb.MemoryRepo()
    with pytest.raises(LookupError):
        repo.record_deployment('p', '1', 'hyd', action='deploy', actor='x', reason='y')
    repo.upsert_proc_def({'processDefinitionId': 'p', 'processDefinitionName': 'p', 'version': '1'})
    assert repo.deployed_version('p') is None
    with pytest.raises(LookupError):
        repo.record_deployment('p', '2', 'hyd', action='deploy', actor='x', reason='y')
    row = repo.record_deployment('p', '1', 'hyd', action='deploy', actor='x', reason='y')
    assert row['previous_version'] is None and repo.deployed_version('p') == '1' and repo.deployed_version('p', 'other') is None
