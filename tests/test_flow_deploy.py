"""B4 (확정 TODO B4): 경보 패턴 → 지금 배포된 흐름. 학생이 자기 흐름을 배포하면 다음 같은 패턴 경보부터 그 흐름, 열린 처리 건은
자기 판본, "기준 흐름으로 되돌리기"는 운영 포인터만 기준으로, 기준 비교는 바뀐 단계 목록. 일부러 깨뜨린 라우팅(U4처럼 기준 흐름만
보는 것)이 잡히는지도 확인한다."""
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import alert_policy, flow_deploy, instance_mode, instances
from test_instance_mode import world, ALERT  # noqa: F401 — fixture

PUMP = {"alertId": "HYD-02-PUMP_LEAKAGE-1", "asset": "HYD-02", "pattern": "PUMP_LEAKAGE", "state": "RAISE"}


def _student_flow(rt, def_id='student_pump', version='1.0', patterns=('PUMP_LEAKAGE',), step_name='내 원인 진단'):
    raw = deepcopy(rt.deployed_definition().raw)
    raw['processDefinitionId'], raw['processDefinitionName'], raw['version'] = def_id, '내 펌프 흐름', version
    raw['alertPolicy']['patterns'] = {p: raw['alertPolicy']['patterns'][p] for p in patterns}
    next(a for a in raw['activities'] if a['id'] == 'task:diagnose')['name'] = step_name
    return raw


def _alert(base, n):
    return dict(base, alertId=f"{base['alertId']}-{n}")


def _deploy_student_and_check(rt):
    """The B4 contract in one place (also run against a deliberately broken router below)."""
    before = rt.on_alert_raise(_alert(PUMP, 'before'))
    assert (before['proc_def_id'], before['proc_def_version']) == ('anomaly_response', '2.2')
    rt.register_definition(_student_flow(rt))
    assert rt.on_alert_raise(_alert(PUMP, 'registered'))['proc_def_id'] == 'anomaly_response'   # registering is not deploying
    out = rt.deploy_definition('student_pump', '1.0', by='학생1', reason='내 흐름 시험')
    assert out['applies_to'] == '다음 경보부터(PUMP_LEAKAGE)' and out['patterns'] == ['PUMP_LEAKAGE']
    after = rt.on_alert_raise(_alert(PUMP, 'after'))
    assert (after['proc_def_id'], after['proc_def_version']) == ('student_pump', '1.0')
    diagnose = next(w for w in rt.repo.list_workitems(proc_inst_id=after['proc_inst_id']) if w['activity_id'] == 'task:diagnose')
    assert diagnose['activity_name'] == '내 원인 진단'
    # another pattern is still opened by the reference flow
    assert rt.on_alert_raise(_alert(ALERT, 'cooler'))['proc_def_id'] == 'anomaly_response'
    # the instance opened before the deployment keeps its own flow and version
    kept = rt.repo.get_instance(before['proc_inst_id'])
    assert (kept['proc_def_id'], kept['proc_def_version']) == ('anomaly_response', '2.2')
    assert all(w['proc_def_id'] == 'anomaly_response' and w['version'] == '2.2'
               for w in rt.repo.list_workitems(proc_inst_id=before['proc_inst_id']))
    return before, after


def test_a_deployed_student_flow_opens_the_next_alert_of_its_pattern(world):
    rt = world['rt']
    _deploy_student_and_check(rt)
    policy = rt.alert_policy('PUMP_LEAKAGE')
    assert policy['route'] == 'response' and policy['target'] == {'definition': 'student_pump', 'version': '1.0'}
    assert rt.alert_policy('UNKNOWN')['target'] == {'definition': 'alert_triage', 'version': '1.0'}   # unsupported → human review
    table = flow_deploy.routes(rt)
    by_pattern = {r['pattern']: r for r in table['routes']}
    assert by_pattern['PUMP_LEAKAGE']['definition'] == 'student_pump' and by_pattern['PUMP_LEAKAGE']['source'] == '내가 배포한 흐름'
    assert by_pattern['COOLER_DEGRADATION']['reference'] and by_pattern['FAN_VIBRATION']['reference']
    assert not table['at_reference'] and table['flows'][0]['opens'] == ['PUMP_LEAKAGE']


def test_the_check_catches_a_router_that_ignores_deployed_student_flows(world, monkeypatch):
    """일부러 깨뜨리기: U4처럼 기준 흐름만 보는 라우터로 바꾸면 위 계약이 깨져야 한다."""
    rt = world['rt']
    monkeypatch.setattr(instances.InstanceRuntime, 'alert_policy',
                        lambda self, pattern: alert_policy.for_definition(self.deployed_definition().raw, pattern))
    with pytest.raises(AssertionError):
        _deploy_student_and_check(rt)


def test_deploy_reset_puts_the_pointers_back_to_the_reference_flow(world):
    rt = world['rt']
    _before, after = _deploy_student_and_check(rt)
    # a student version of the reference id deployed as well
    raw = deepcopy(rt.deployed_definition().raw); raw['version'] = '2.3-user'
    next(a for a in raw['activities'] if a['id'] == 'task:diagnose')['name'] = '원인 진단 (내 판본)'
    rt.register_definition(raw)
    rt.deploy_definition('anomaly_response', '2.3-user', by='학생1', reason='기준 흐름 고쳐 보기')
    assert rt.on_alert_raise(_alert(ALERT, 'user'))['proc_def_version'] == '2.3-user'
    with pytest.raises(ValueError, match='되돌린 사람'):
        flow_deploy.deploy_reset(rt, ' ')
    out = flow_deploy.deploy_reset(rt, '학생1')
    assert [(c['definition'], c['action'], c['from'], c['to']) for c in out['changes']] == \
        [('student_pump', 'withdraw', '1.0', None), ('anomaly_response', 'reset', '2.3-user', '2.2')]
    assert out['routes']['at_reference'] and 'DEFINITION_WITHDRAWN' in world['audits'] and 'DEFINITION_RESET' in world['audits']
    pump = rt.on_alert_raise(_alert(PUMP, 'reset'))
    assert (pump['proc_def_id'], pump['proc_def_version']) == ('anomaly_response', '2.2')
    assert rt.on_alert_raise(_alert(ALERT, 'reset'))['proc_def_version'] == '2.2'
    # the student's registered versions stay (deleting them is B3's /api/flows/reset), the open student instance keeps its flow
    assert rt.repo.get_proc_def('student_pump', version='1.0') and rt.repo.get_proc_def('anomaly_response', version='2.3-user')
    assert rt.repo.get_instance(after['proc_inst_id'])['proc_def_id'] == 'student_pump'
    assert flow_deploy.deploy_reset(rt, '학생1')['already_reference']
    # restart after a reset boots the reference file (no extra seed), the history keeps who did what
    assert instance_mode._bootstrap_definition(rt.repo, 'hyd').raw['version'] == '2.2'
    assert [h['action'] for h in rt.repo.list_deployments('student_pump')] == ['withdraw', 'deploy']
    assert rt.repo.list_deployments('anomaly_response')[0]['action'] == 'reset'


def test_only_flows_a_person_deployed_take_alert_patterns(world):
    """A seed (boot or the migration backfill of the old "last registered" pointer) never takes an alert pattern."""
    rt = world['rt']
    rt.register_definition(_student_flow(rt, def_id='old_probe_flow'))
    rt.repo.record_deployment('old_probe_flow', '1.0', 'hyd', action='seed', actor='migration', reason='backfill')
    assert rt.alert_policy('PUMP_LEAKAGE')['target']['definition'] == 'anomaly_response'
    assert flow_deploy.routes(rt)['flows'] == []
    # …and a reference id whose newest record is a seed boots from the file even if the pointer says otherwise
    raw = deepcopy(rt.deployed_definition().raw); raw['version'] = '2.9-registered'
    rt.register_definition(raw)
    rt.repo.record_deployment('anomaly_response', '2.9-registered', 'hyd', action='seed', actor='migration', reason='backfill')
    assert instance_mode._bootstrap_definition(rt.repo, 'hyd').raw['version'] == '2.2'


def test_the_newest_deployment_wins_a_pattern_and_the_other_is_reported_as_shadowed(world):
    rt = world['rt']
    rt.register_definition(_student_flow(rt, def_id='flow_a', patterns=('PUMP_LEAKAGE', 'FAN_VIBRATION')))
    rt.register_definition(_student_flow(rt, def_id='flow_b', patterns=('PUMP_LEAKAGE',)))
    rt.deploy_definition('flow_a', '1.0', by='학생1', reason='a')
    rt.deploy_definition('flow_b', '1.0', by='학생1', reason='b')
    assert rt.on_alert_raise(_alert(PUMP, 'x'))['proc_def_id'] == 'flow_b'
    assert rt.on_alert_raise(dict(PUMP, alertId='HYD-03-FAN-1', asset='HYD-03', pattern='FAN_VIBRATION'))['proc_def_id'] == 'flow_a'
    flows = {f['definition']: f for f in flow_deploy.routes(rt)['flows']}
    assert flows['flow_b']['opens'] == ['PUMP_LEAKAGE'] and flows['flow_a']['opens'] == ['FAN_VIBRATION']
    assert flows['flow_a']['shadowed'] == ['PUMP_LEAKAGE']


def test_compare_with_reference_lists_the_changed_steps(world):
    rt = world['rt']
    rt.register_definition(_student_flow(rt))
    diff = flow_deploy.compare_with_reference(rt, 'student_pump', '1.0')
    assert diff['reference'] == {'definition': 'anomaly_response', 'version': '2.2'}
    assert '단계 "내 원인 진단"(task:diagnose) 변경: 이름' in diff['steps']
    assert any(c['id'] == 'alertPolicy' for c in diff['changes']) and diff['summary'].startswith('기준 대비')
    same = flow_deploy.compare_with_reference(rt, 'anomaly_response', '2.2')
    assert same['same'] and same['summary'] == '기준 흐름과 같습니다'
    with pytest.raises(LookupError, match='배포된 판본이 없는'):
        flow_deploy.compare_with_reference(rt, 'student_pump')


def test_http_deployments_reset_and_compare(world, monkeypatch):
    rt = world['rt']
    monkeypatch.setattr(instance_mode, '_runtime', rt)
    app = FastAPI(); instance_mode.mount(app, 'instance'); client = TestClient(app)
    assert client.get('/api/flows/deployments').json()['at_reference']
    assert client.post('/api/process/definitions', json={'definition': _student_flow(rt)}).status_code == 201
    assert client.post('/api/process/definitions/student_pump/deploy', json={'version': '1.0', 'by': '학생1', 'reason': '시험'}).status_code == 200
    table = client.get('/api/flows/deployments').json()
    assert {r['pattern']: r['definition'] for r in table['routes']}['PUMP_LEAKAGE'] == 'student_pump'
    status = client.get('/api/process/definitions/student_pump/versions').json()
    assert status['alert_entry'] and status['alert_patterns'] == ['PUMP_LEAKAGE'] and not status['reference']
    diff = client.get('/api/flows/deploy-compare', params={'definition': 'student_pump'}).json()
    assert diff['target'] == {'definition': 'student_pump', 'version': '1.0'} and diff['steps']
    assert client.get('/api/flows/deploy-compare', params={'definition': 'nope', 'version': '1'}).status_code == 404
    assert client.post('/api/flows/deploy-reset', json={}).status_code == 422
    res = client.post('/api/flows/deploy-reset', json={'by': '학생1'})
    assert res.status_code == 200 and res.json()['routes']['at_reference'] and len(res.json()['changes']) == 1
    assert client.post('/api/instances/start', json={'alert': _alert(PUMP, 'http')}).json()['proc_def_id'] == 'anomaly_response'
