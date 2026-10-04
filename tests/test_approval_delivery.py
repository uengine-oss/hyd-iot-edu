"""Approval commit and external delivery are separate, recoverable boundaries."""
from copy import deepcopy
from datetime import timedelta

import pytest

from procsvc import decisions, engine, instance_mode, instances
from test_instance_mode import world, ALERT, NOW, GUIDE_CARD_ACTIONS, _decision_payload, _row


def ready(world, purchase=False):
    rt = world['rt']
    inst = rt.on_alert_raise(ALERT, now=NOW)
    inc = next(iter(world['incidents'].values()))
    inc.card = dict(inc.card, recommended=GUIDE_CARD_ACTIONS)
    d = decisions.new(_decision_payload(inc.id))
    if purchase:
        d['options'][0]['actions'].append({'code':'PR_CREATE', 'kind':'transaction',
            'value':'sup:b', 'target':'sys:erp'})
    world['book'][d['id']] = d
    instance_mode._bridge_legacy_agent(d)
    return rt, inst, inc, d, _row(rt, inst, 'task:select')


def choose(rt, d, wi):
    return rt.select(wi['id'], d['id'], d['options'][0]['id'], 'manager',
                     'role:prod-mgr', now=NOW)


def test_current_conditions_reject_before_commit_and_leave_choice_open(world):
    rt, inst, inc, d, wi = ready(world)
    world['ctx'].check_approval = lambda *args: {'allowed': False, 'reasons': ['PLC is now manual']}
    with pytest.raises(ValueError, match='PLC is now manual'):
        choose(rt, d, wi)
    assert d['state'] == 'PENDING_APPROVAL' and inc.cmd_id is None
    assert rt.repo.get_workitem(wi['id'])['status'] == 'IN_PROGRESS'
    assert rt.repo.get_approval(wi['id'], rt.tenant_id) is None
    assert not world['executed']


def test_adjusted_value_cannot_reuse_default_card_prediction(world):
    rt, inst, inc, d, wi = ready(world)
    with pytest.raises(ValueError, match='실행 조치값'):
        rt.select(wi['id'],d['id'],d['options'][0]['id'],'manager','role:prod-mgr',fan_pct=90,now=NOW)
    assert inc.cmd_id is None and d['state']=='PENDING_APPROVAL'
    assert rt.repo.get_workitem(wi['id'])['status']=='IN_PROGRESS'
    assert rt.repo.get_approval(wi['id'],rt.tenant_id) is None


def test_saved_review_authorizes_exact_changed_actions_after_store_reopen(world,tmp_path):
    from procsvc.store import Store
    from procsvc.decision_reviews import DecisionReviews
    rt,inst,inc,d,wi=ready(world)
    store=Store(tmp_path/'reviews.sqlite3')
    def evaluate(source,option,parameters):
        fresh=deepcopy(source)
        card=next(o for o in fresh['options'] if o['id']==option)
        card['actions'][0]['value']=parameters['fan_pct']
        card['reviewed_choice']={'parameters':parameters,'scope':'unit test evaluator'}
        fresh['options']=[card]
        return fresh
    world['ctx'].reviews=lambda:DecisionReviews(store,world['book'],world['incidents'],evaluate)
    review=rt.preview_choice(wi['id'],d['id'],d['options'][0]['id'],{'fan_pct':95},now=NOW)
    assert inc.cmd_id is None and d['options'][0]['actions'][0]['value']==100
    assert rt.repo.get_approval(wi['id'],rt.tenant_id) is None
    store.db.close();store=Store(tmp_path/'reviews.sqlite3')
    with pytest.raises(ValueError,match='실행 조치값'):
        rt.select(wi['id'],d['id'],d['options'][0]['id'],'manager','role:prod-mgr',fan_pct=94,
                  review_id=review['id'],now=NOW)
    assert inc.cmd_id is None and rt.repo.get_workitem(wi['id'])['status']=='IN_PROGRESS'
    rt.select(wi['id'],d['id'],d['options'][0]['id'],'manager','role:prod-mgr',fan_pct=95,
              review_id=review['id'],now=NOW)
    assert inc.actions[0]['fan_pct']==95 and inc.cmd_id
    row=rt.repo.get_approval(wi['id'],rt.tenant_id)
    assert row['payload']['plan']['_snapshot']['review_id']==review['id']
    assert row['payload']['plan']['_snapshot']['original_decision']['options'][0]['actions'][0]['value']==100
    assert d['review_id']==review['id'] and d['options'][0]['actions'][0]['value']==95
    store.db.close()


def test_changed_conditions_after_commit_block_delivery_and_plc(world, monkeypatch):
    rt, inst, inc, d, wi = ready(world, purchase=True)
    with monkeypatch.context() as patch:
        patch.setattr(rt, '_after_commit', lambda *args, **kwargs: None)
        choose(rt, d, wi)
    world['ctx'].check_approval = lambda *args: {'allowed': False, 'reasons': ['source changed after consent']}
    rt.poll_once(now=NOW)
    row = rt.repo.get_approval(wi['id'], rt.tenant_id)
    assert row['status'] == 'FAILED' and 'source changed' in row['error']
    assert inc.cmd_id is None and not world['executed']
    assert rt.repo.get_workitem(wi['id'])['status'] == 'SUBMITTED'
    assert row['payload']['current_check']['allowed'] is True  # original consent evidence is immutable


def test_raw_legacy_commands_cannot_skip_sop_and_role(world, monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from procsvc import main
    rt, inst, inc, d, wi = ready(world)
    monkeypatch.setattr(main, 'incidents', world['incidents'])
    monkeypatch.setattr(instance_mode, '_runtime', None)
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.approve(inc.id, main.ApproveReq(actions=[{'code':'FAN_SET','fan_pct':100}])))
    assert error.value.status_code == 409 and inc.cmd_id is None


def test_final_command_boundary_rechecks_conditions(world, monkeypatch):
    from procsvc import main
    rt, inst, inc, d, wi = ready(world)
    decisions.approve(d, d['options'][0]['id'], 'manager', 'role:prod-mgr')
    monkeypatch.setattr(main, 'book', world['book'])
    monkeypatch.setattr(main, '_audit', lambda *args, **kwargs: None)
    monkeypatch.setattr(main.current_approval, 'check', lambda *args: {'allowed': False, 'reasons':['late change']})
    with pytest.raises(ValueError, match='late change'):
        main._approve_incident(inc, 'manager', [{'code':'FAN_SET','fan_pct':100}])
    assert inc.cmd_id is None


def test_sql_rollback_does_not_leave_approved_decision(world, monkeypatch):
    rt, inst, inc, d, wi = ready(world)
    before = deepcopy(d)
    def fail(_):
        raise RuntimeError('injected instance save failure')
    monkeypatch.setattr(rt.repo, 'update_instance', fail)
    with pytest.raises(RuntimeError, match='injected'):
        choose(rt, d, wi)
    assert world['book'][d['id']] == before
    assert rt.repo.get_workitem(wi['id'])['status'] == 'IN_PROGRESS'
    assert world['executed'] == [] and inc.cmd_id is None
    assert rt.repo.get_approval(wi['id'], rt.tenant_id) is None


def test_committed_intent_recovers_after_dispatch_is_lost(world, monkeypatch):
    rt, inst, inc, d, wi = ready(world)
    with monkeypatch.context() as patch:
        patch.setattr(rt, '_after_commit', lambda *a, **k: None)
        choose(rt, d, wi)
    assert d['state'] == 'PENDING_APPROVAL' and inc.cmd_id is None
    assert rt.repo.get_workitem(wi['id'])['status'] == 'SUBMITTED'
    assert rt.repo.get_approval(wi['id'], rt.tenant_id)['status'] == 'PENDING'
    restarted = instances.InstanceRuntime(rt.repo, rt.defn, rt.hooks, consumer='restarted')
    restarted.poll_once(now=NOW)
    assert rt.repo.get_workitem(wi['id'])['status'] == 'DONE'
    assert inc.cmd_id and rt.repo.get_approval(wi['id'], rt.tenant_id)['status'] == 'DELIVERED'
    assert world['book'][d['id']]['chosen'] == d['options'][0]['id']


def test_snapshot_failure_leaves_recoverable_approval_and_blocks_plc(world, monkeypatch):
    rt, inst, inc, d, wi = ready(world)
    def fail():
        raise OSError('injected snapshot unavailable')
    with monkeypatch.context() as patch:
        patch.setattr(world['ctx'], 'persist', fail)
        choose(rt, d, wi)
    row = rt.repo.get_approval(wi['id'], rt.tenant_id)
    assert row['status'] == 'FAILED' and 'snapshot unavailable' in row['error']
    assert inc.cmd_id is None and rt.repo.get_workitem(wi['id'])['status'] == 'SUBMITTED'
    rt.retry_approval(wi['id'], 'recovery-manager', role='role:prod-mgr', now=NOW)
    assert rt.repo.get_approval(wi['id'], rt.tenant_id)['status'] == 'DELIVERED'
    assert inc.cmd_id and rt.repo.get_workitem(wi['id'])['status'] == 'DONE'


def test_lost_enterprise_reply_retries_same_intent_without_duplicate_operation(world):
    rt, inst, inc, d, wi = ready(world, purchase=True)
    ledger, requests = {}, []
    def execute(snapshot, item):
        key = (snapshot['id'], item['code'])
        requests.append(key)
        if key not in ledger:
            ledger[key] = dict(ok=True, ref='PR-stable', skill=item['skill'],
                               code=item['code'], system=item['system'])
            raise OSError('reply lost after enterprise commit')
        return ledger[key]
    world['ctx'].exec_skill = execute
    choose(rt, d, wi)
    assert inc.cmd_id is None
    assert rt.repo.get_approval(wi['id'], rt.tenant_id)['status'] == 'FAILED'
    restarted = instances.InstanceRuntime(rt.repo, rt.defn, rt.hooks, consumer='new-engine')
    restarted.retry_approval(wi['id'], 'recovery-manager', role='role:prod-mgr', now=NOW)
    assert len(ledger) == 1 and len(requests) == 2 and inc.cmd_id
    delivered = rt.repo.get_approval(wi['id'], rt.tenant_id)
    assert delivered['status'] == 'DELIVERED' and delivered['results'][0]['ref'] == 'PR-stable'
    assert len(world['book'][d['id']]['executions']) == 1
    with pytest.raises(ValueError):
        restarted.retry_approval(wi['id'], 'recovery-manager', role='role:prod-mgr', now=NOW)
    assert len(requests) == 2


def test_wrong_incident_decision_cannot_be_approved(world):
    rt, inst, inc, d, wi = ready(world)
    d['origin']['incident'] = 'another-incident'
    with pytest.raises(ValueError, match='incident|인시던트'):
        choose(rt, d, wi)
    assert d['state'] == 'PENDING_APPROVAL' and inc.cmd_id is None


def test_delivery_uses_committed_snapshot_not_later_card_edits(world, monkeypatch):
    rt, inst, inc, d, wi = ready(world, purchase=True)
    with monkeypatch.context() as patch:
        patch.setattr(rt, '_after_commit', lambda *a, **k: None)
        choose(rt, d, wi)
    d['options'][0]['actions'][-1]['value'] = 'unapproved-supplier'
    observed = []
    def execute(snapshot, item):
        observed.append((snapshot['options'][0]['actions'][-1]['value'], item['value']))
        return dict(ok=True, ref='PR-fixed', skill=item['skill'], code=item['code'], system=item['system'])
    world['ctx'].exec_skill = execute
    rt.poll_once(now=NOW)
    assert observed == [('sup:b', 'sup:b')]
    assert inc.cmd_id


def test_other_tenant_cannot_retry_approval(world, monkeypatch):
    rt, inst, inc, d, wi = ready(world)
    with monkeypatch.context() as patch:
        patch.setattr(rt, '_after_commit', lambda *a, **k: None)
        choose(rt, d, wi)
    other = instances.InstanceRuntime(rt.repo, rt.defn, rt.hooks, tenant_id='other')
    with pytest.raises(KeyError):
        other.retry_approval(wi['id'], 'outsider', now=NOW)
    assert inc.cmd_id is None


def test_accepted_approval_ends_human_deadline_even_while_delivery_waits(world, monkeypatch):
    rt, inst, inc, d, wi = ready(world)
    with monkeypatch.context() as patch:
        patch.setattr(rt, '_after_commit', lambda *a, **k: None)
        choose(rt, d, wi)
    assert rt.fire_timeouts(now=NOW+timedelta(days=2)) == []
    assert rt.repo.get_workitem(wi['id'])['status'] == 'SUBMITTED'
    assert _row(rt, inst, 'task:escalate')['status'] == 'TODO'


def test_engine_cannot_advance_failed_delivery_after_claim_is_released(world, monkeypatch):
    rt, inst, inc, d, wi = ready(world)
    def fail(): raise OSError('snapshot failed')
    with monkeypatch.context() as patch:
        patch.setattr(world['ctx'], 'persist', fail)
        choose(rt, d, wi)
    row = rt.repo.get_workitem(wi['id'])
    row['consumer'] = None
    rt.repo.update_workitem(row)
    rt.poll_once(now=NOW)
    assert rt.repo.get_approval(wi['id'], rt.tenant_id)['status'] == 'FAILED'
    assert rt.repo.get_workitem(wi['id'])['status'] == 'SUBMITTED'
    assert _row(rt, inst, 'task:command')['status'] == 'TODO' and inc.cmd_id is None


def test_invalid_command_does_not_consume_approval(world):
    rt, inst, inc, d, wi = ready(world)
    with pytest.raises(ValueError, match='paramRange'):
        rt.select(wi['id'], d['id'], d['options'][0]['id'], 'manager',
                  'role:prod-mgr', fan_pct=999, now=NOW)
    assert d['state'] == 'PENDING_APPROVAL'
    assert rt.repo.get_approval(wi['id'], rt.tenant_id) is None
    assert rt.repo.get_workitem(wi['id'])['status'] == 'IN_PROGRESS'


def test_closed_incident_cannot_consume_approval(world):
    rt, inst, inc, d, wi = ready(world)
    inc.state = 'RESOLVED_WITHOUT_ACTION'
    with pytest.raises(ValueError, match='incident|인시던트'):
        choose(rt, d, wi)
    assert d['state'] == 'PENDING_APPROVAL' and inc.cmd_id is None


@pytest.mark.parametrize('deleted', [False, True])
def test_legacy_http_routes_cannot_bypass_instance_approval(world, monkeypatch, deleted):
    from fastapi.testclient import TestClient
    from procsvc import main
    rt, inst, inc, d, wi = ready(world)
    monkeypatch.setattr(main, 'incidents', world['incidents'])
    monkeypatch.setattr(main, 'book', world['book'])
    monkeypatch.setattr(instance_mode, '_runtime', rt)
    if deleted:
        rt.repo.instances[inst['proc_inst_id']]['is_deleted'] = True
    client = TestClient(main.app)
    decision_body = {'option':d['options'][0]['id'], 'role':'role:prod-mgr', 'by':'manager'}
    attempts = [
        (f'/api/incidents/{inc.id}/approve', {'approvedBy':'manager','actions':[{'code':'FAN_SET','fan_pct':100}]}),
        (f'/api/incidents/{inc.id}/reject', {'by':'manager'}),
        (f'/api/incidents/{inc.id}/work-order-retry', {}),
        (f'/api/incidents/{inc.id}/decide', dict(decision_body, decision=d['id'])),
        (f'/api/incidents/{inc.id}/decision-preview', {'decision':d['id'],'option':d['options'][0]['id'],'parameters':{'fan_pct':95}}),
        (f"/api/decisions/{d['id']}/approve", decision_body),
        (f"/api/decisions/{d['id']}/reject", {'by':'manager'}),
    ]
    for url, body in attempts:
        assert client.post(url, json=body).status_code == 409, url
    assert d['state']=='PENDING_APPROVAL' and inc.cmd_id is None


def test_approval_http_reports_failure_then_authorized_recovery(world, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    rt, inst, inc, d, wi = ready(world)
    monkeypatch.setattr(instance_mode, '_runtime', rt)
    app = FastAPI()
    instance_mode.mount(app, 'instance')
    client = TestClient(app)
    def fail(): raise OSError('snapshot unavailable')
    with monkeypatch.context() as patch:
        patch.setattr(world['ctx'], 'persist', fail)
        result = client.post(f"/api/todolist/{wi['id']}/select", json={'decision':d['id'],
            'option':d['options'][0]['id'], 'by':'manager','role':'role:prod-mgr'})
    assert result.status_code==200 and result.json()['accepted'] is True
    assert result.json()['approval_status']=='FAILED' and inc.cmd_id is None
    view = client.get(f"/api/instances/{inst['proc_inst_id']}").json()
    assert view['approvals'][0]['status']=='FAILED'
    url = f"/api/todolist/{wi['id']}/approval-retry"
    assert client.post(url, json={'by':'operator','role':'role:operator'}).status_code==403
    response = client.post(url, json={'by':'manager','role':'role:prod-mgr'})
    assert response.status_code==200 and response.json()['status']=='DELIVERED' and inc.cmd_id
    assert client.post(url, json={'by':'manager','role':'role:prod-mgr'}).status_code==409
