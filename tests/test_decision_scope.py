import asyncio
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import HTTPException
from procsvc import engine, decision_scope, main, instance_mode
from worker import context, prompt
from dmn_mcp import tools as dmn
from test_instance_mode import world, ALERT, _decision_payload


def fixture():
    definition = engine.Definition.load(Path(__file__).resolve().parents[1]/'it/process/definitions/anomaly_response_v21.json')
    inst = engine.new_instance(definition, {'asset': 'HYD-01', 'incident': 'INC-fixture'})
    inst['rework_generation'] = 1
    row = engine.new_workitem(definition, inst, definition.activities['task:rank'], status='IN_PROGRESS')
    row.update(draft_status='STARTED', consumer='scope-worker')
    scope = context.process_scope(row)
    decision = {'id': 'D-new', 'asset': 'HYD-01', 'state': 'PENDING_APPROVAL',
                'origin': {'incident': 'INC-fixture', 'process_scope': scope}}
    return definition, inst, row, scope, decision


def test_current_claimed_producer_and_accepted_output_match():
    d, inst, row, scope, decision = fixture()
    decision_scope.validate_submission(inst, d, row, scope)
    decision_scope.validate_output(inst, row, decision)


@pytest.mark.parametrize('field,value', [('tenant', 'other'), ('instance', 'other'), ('workitem', 'other'),
                                        ('generation', 0), ('generation', True), ('version', 'other'), ('consumer', 'old')])
def test_mismatched_scope_cannot_submit(field, value):
    d, inst, row, scope, _ = fixture(); scope[field] = value
    with pytest.raises(ValueError): decision_scope.validate_submission(inst, d, row, scope)


@pytest.mark.parametrize('status', ['CANCELLED', 'DONE', 'TODO', 'SUBMITTED'])
def test_non_live_claim_cannot_submit(status):
    d, inst, row, scope, _ = fixture(); row['status'] = status
    with pytest.raises(ValueError): decision_scope.validate_submission(inst, d, row, scope)


def test_old_generation_even_if_still_claimed_and_wrong_output_task_are_rejected():
    d, inst, row, scope, _ = fixture(); inst['rework_generation'] = 2
    with pytest.raises(ValueError, match='이전 세대'): decision_scope.validate_submission(inst, d, row, scope)
    inst['rework_generation'] = 1; row['activity_id'] = 'task:diagnose'
    with pytest.raises(ValueError, match='판단 ID'): decision_scope.validate_submission(inst, d, row, scope)


@pytest.mark.parametrize('defect', ['unknown', 'old_workitem', 'old_generation', 'processed', 'wrong_incident'])
def test_rank_output_cannot_reuse_unrelated_or_old_decision(defect):
    _, inst, row, _, decision = fixture()
    if defect == 'unknown': decision = None
    if defect == 'old_workitem': decision['origin']['process_scope']['workitem'] = 'old'
    if defect == 'old_generation': decision['origin']['process_scope']['generation'] = 0
    if defect == 'processed': decision['state'] = 'APPROVED'
    if defect == 'wrong_incident': decision['origin']['incident'] = 'other'
    with pytest.raises(ValueError): decision_scope.validate_output(inst, row, decision)


def test_worker_prompt_and_mcp_pass_exact_producer_scope(monkeypatch):
    _, _, row, scope, _ = fixture()
    ctx = context.Context(row, 'rank', [{'key': 'decision_id', 'type': 'text'}])
    text = prompt.build(row, ctx.extras, workdir='workspace')
    assert 'process_scope' in text and row['id'] in text and row['consumer'] in text
    seen = []
    def decide(*args, **kwargs):
        seen.append(kwargs)
        return {'id': 'D', 'status': 'SUBMITTED'}
    monkeypatch.setattr(dmn.decidelib, 'decide', decide)
    tool = dmn.DmnTools(kg=object(), tsdb=object())
    tool.submit_decision('HYD-01', 'COOLER_DEGRADATION', 'cause', 'failure', 'INC-fixture', process_scope=scope)
    assert seen[0]['origin']['process_scope'] == scope and seen[0]['do_submit'] is True


def test_legacy_replay_does_not_claim_new_generation(world):
    rt = world['rt']; inst = rt.on_alert_raise(ALERT); inst['rework_generation'] = 1; rt.repo.update_instance(inst)
    before = deepcopy(rt.repo.workitems)
    decision = _decision_payload(next(iter(world['incidents'])))
    world['book'][decision['id']] = decision
    instance_mode._bridge_legacy_agent(decision); instance_mode.reconcile_legacy_decisions()
    assert rt.repo.workitems == before


def test_legacy_bridge_claim_fences_result_after_rework_cancellation(world, monkeypatch):
    rt = world['rt']; rt.on_alert_raise(ALERT); original = instance_mode._event
    def cancel_before_save(job, row, inst, kind, data):
        original(job, row, inst, kind, data)
        if kind == 'task_started':
            cancelled = rt.repo.get_workitem(row['id']); cancelled.update(status='CANCELLED', consumer=None)
            rt.repo.update_workitem(cancelled)
    monkeypatch.setattr(instance_mode, '_event', cancel_before_save)
    instance_mode._bridge_legacy_agent(_decision_payload(next(iter(world['incidents']))))
    row = next(w for w in rt.repo.workitems.values() if w['activity_id'] == 'task:diagnose')
    assert row['status'] == 'CANCELLED' and row['output'] is None


def test_decision_endpoint_refuses_missing_new_generation_scope_before_storage(world, monkeypatch):
    rt = world['rt']; inst = rt.on_alert_raise(ALERT); inst['rework_generation'] = 1; rt.repo.update_instance(inst)
    monkeypatch.setattr(main, 'book', world['book']); monkeypatch.setattr(main, 'incidents', world['incidents'])
    payload = _decision_payload(next(iter(world['incidents'])))
    with pytest.raises(HTTPException) as error: asyncio.run(main.create_decision(payload))
    assert error.value.status_code == 409 and payload['id'] not in world['book']


def test_ended_process_cannot_accept_a_new_unscoped_decision(world, monkeypatch):
    rt = world['rt']; inst = rt.on_alert_raise(ALERT)
    inst['status'] = 'CANCELLED'; rt.repo.update_instance(inst)
    monkeypatch.setattr(main, 'book', world['book']); monkeypatch.setattr(main, 'incidents', world['incidents'])
    payload = _decision_payload(next(iter(world['incidents'])))
    with pytest.raises(HTTPException) as error: asyncio.run(main.create_decision(payload))
    assert error.value.status_code == 409 and payload['id'] not in world['book']


def test_ended_process_duplicate_preserves_existing_decision(world, monkeypatch):
    rt = world['rt']; inst = rt.on_alert_raise(ALERT)
    inst['status'] = 'CANCELLED'; rt.repo.update_instance(inst)
    monkeypatch.setattr(main, 'book', world['book']); monkeypatch.setattr(main, 'incidents', world['incidents'])
    payload = _decision_payload(next(iter(world['incidents'])))
    payload['state'] = 'REJECTED'
    world['book'][payload['id']] = deepcopy(payload)
    result = asyncio.run(main.create_decision(payload))
    assert result['duplicate'] and world['book'][payload['id']] == payload
