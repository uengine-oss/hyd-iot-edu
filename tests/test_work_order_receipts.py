"""The actual CMMS receipt, not a generated label, closes an Incident."""
from copy import deepcopy

import pytest

from procsvc import instance_mode, machine
from test_instance_mode import world, NOW, NoFx, _row
from test_approval_delivery import ready, choose


def recover(world):
    rt, inst, inc, d, wi = ready(world)
    choose(rt, d, wi)
    machine.on_status(inc, {'cmdId':inc.cmd_id,'result':'DONE'}, NOW, NoFx())
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    machine.on_alert(inc, {'alertId':inc.alert_id,'state':'CLEAR'}, NoFx())
    machine.on_timer(inc, 'reobs', NOW, 50.0, NoFx())
    return rt, inst, inc, d


def test_reobservation_does_not_invent_a_work_order_or_close_incident(world):
    _, _, inc, _ = recover(world)
    assert inc.state == 'RESOLVED' and inc.work_order is None and inc.closed is None
    assert not any(h['state']=='WORK_ORDER_CREATED' for h in inc.history)


def test_actual_receipt_is_shared_by_incident_task_and_enterprise(world):
    rt, inst, inc, _ = recover(world)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    result = _row(rt, inst, 'task:work-order')['output']['work_order']
    assert inc.state == 'CLOSED' and inc.work_order['id'] == result['ref'] == 'WO-1003-AB12'
    assert inc.work_order['sop'] == 'SOP-COOL-02'


def test_cmms_failure_keeps_incident_and_instance_open(world):
    rt, inst, inc, _ = recover(world)
    world['ctx'].exec_skill = lambda d,item: {'ok':False,'code':'WO_CREATE','error':'CMMS offline','skill':item['skill']}
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    assert inc.state == 'RESOLVED' and inc.work_order is None and inc.closed is None
    assert rt.repo.get_instance(inst['proc_inst_id'])['status'] == 'RUNNING'


def test_work_order_only_path_closes_incident_after_real_receipt(world):
    rt, inst, inc, d, wi = ready(world)
    opt = d['options'][0]
    opt['kind'] = 'work_order'
    opt['actions'] = [a for a in opt['actions'] if a['code']=='WO_CREATE']
    choose(rt, d, wi)
    assert inc.cmd_id is None
    assert inc.state == 'CLOSED' and inc.work_order['id'] == 'WO-1003-AB12'
    assert rt.repo.get_instance(inst['proc_inst_id'])['status'] == 'COMPLETED'


def test_approved_work_order_value_is_not_replaced_with_control_option_name(world):
    captured=[]
    real = world['ctx'].exec_skill
    world['ctx'].exec_skill = lambda d,item: (captured.append(deepcopy(item)), real(d,item))[1]
    rt, inst, inc, _ = recover(world)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    assert captured[0]['value'] == '쿨러 세척'


def test_invalid_success_without_actual_reference_does_not_close(world):
    rt, inst, inc, _ = recover(world)
    world['ctx'].exec_skill = lambda d,item: {'ok':True,'ref':None,'code':'WO_CREATE','skill':item['skill']}
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    assert inc.state == 'RESOLVED' and inc.work_order is None
    assert _row(rt, inst, 'task:work-order')['status'] != 'DONE'


def test_receipt_replay_is_idempotent_and_conflicting_receipt_is_refused(world):
    _, _, inc, _ = recover(world)
    result={'ok':True,'ref':'WO-real','code':'WO_CREATE','sop':'SOP-COOL-02'}
    machine.on_work_order(inc, result, NoFx())
    before=deepcopy(inc.to_dict())
    machine.on_work_order(inc, result, NoFx())
    assert inc.to_dict()==before
    with pytest.raises(ValueError, match='conflict'):
        machine.on_work_order(inc, result | {'ref':'WO-other'}, NoFx())


def test_receipt_snapshot_failure_does_not_leave_in_memory_closed(world):
    rt, inst, inc, _ = recover(world)
    persist = world['ctx'].persist
    def fail_closed():
        if inc.state == 'CLOSED':
            raise OSError('receipt SQLite failure')
        persist()
    world['ctx'].persist = fail_closed
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    assert inc.state == 'RESOLVED' and inc.work_order is None and inc.closed is None
    assert _row(rt, inst, 'task:work-order')['status'] != 'DONE'
    world['ctx'].persist = persist
    rt.poll_once(now=NOW)
    assert inc.state == 'CLOSED' and inc.work_order['id'] == 'WO-1003-AB12'
    assert len(world['book'][inc.work_order['decision']]['executions']) == 1


def test_cmms_request_survives_snapshot_restart_without_replaying_plc(world, tmp_path):
    from procsvc.store import Store
    rt, inst, inc, _ = recover(world)
    world['ctx'].exec_skill = lambda d,item: {'ok':False,'code':'WO_CREATE','error':'offline','skill':item['skill']}
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    store=Store(tmp_path/'snapshot.sqlite')
    store.save(world['incidents'], world['book'], [])
    restored, _, _ = store.restore()
    store.db.close()
    assert restored[inc.id].state == 'RESOLVED'
    assert restored[inc.id].work_order_request == inc.work_order_request


def test_mutated_request_is_refused_before_external_retry(world):
    from procsvc import work_orders
    rt, inst, inc, d = recover(world)
    world['ctx'].exec_skill = lambda d,item: {'ok':False,'code':'WO_CREATE','error':'offline','skill':item['skill']}
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    request=deepcopy(inc.work_order_request['item'])
    with pytest.raises(ValueError, match='conflicts'):
        work_orders.prepare(world['ctx'], d, request | {'value':'different maintenance'})


def test_recovery_finds_cmms_claim_before_service_marker_commits(world):
    rt, inst, inc, _ = recover(world)
    real=world['ctx'].exec_skill
    world['ctx'].exec_skill=lambda d,item: {'ok':False,'error':'offline','skill':item['skill'],'code':'WO_CREATE'}
    rt.on_incident_update(inc.state,inc.id,inc.cleared,now=NOW)
    wi=_row(rt,inst,'task:work-order')
    wi['consumer']='dead-engine-before-service-marker'
    rt.repo.update_workitem(wi)
    world['ctx'].exec_skill=real
    rt.poll_once(now=NOW)
    assert _row(rt,inst,'task:work-order')['status']=='DONE' and inc.work_order['id']=='WO-1003-AB12'


def test_exhausted_cmms_retries_need_approved_role_and_preserve_request(world, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    rt,inst,inc,_=recover(world)
    real=world['ctx'].exec_skill
    world['ctx'].exec_skill=lambda d,item: {'ok':False,'error':'offline','skill':item['skill'],'code':'WO_CREATE'}
    rt.on_incident_update(inc.state,inc.id,inc.cleared,now=NOW)
    rt.poll_once(now=NOW);rt.poll_once(now=NOW)
    wi=_row(rt,inst,'task:work-order');before=deepcopy(inc.work_order_request)
    assert wi['status']=='PENDING' and wi['retry']==3
    monkeypatch.setattr(instance_mode,'_runtime',rt)
    app=FastAPI();instance_mode.mount(app,'instance');client=TestClient(app)
    url=f"/api/todolist/{wi['id']}/work-order-retry"
    assert client.post(url,json={'by':'operator','role':'role:operator'}).status_code==403
    assert _row(rt,inst,'task:work-order')['retry']==3
    world['ctx'].exec_skill=real
    response=client.post(url,json={'by':'manager','role':'role:prod-mgr'})
    assert response.status_code==200 and response.json()['status']=='DONE'
    assert inc.state=='CLOSED' and inc.work_order_request==before
    assert _row(rt,inst,'task:work-order')['rework_count']==1
    assert client.post(url,json={'by':'manager','role':'role:prod-mgr'}).status_code==409


def test_legacy_frozen_guide_failure_retry_and_real_receipt(monkeypatch):
    from procsvc import main
    from test_machine import new_incident
    inc=new_incident()
    audits=[]; calls=[]
    monkeypatch.setattr(main,'incidents',{inc.id:inc})
    monkeypatch.setattr(main,'persist',lambda:None)
    monkeypatch.setattr(main,'_after',lambda _:None)
    monkeypatch.setattr(main,'_audit',lambda *a,**kw:audits.append(a))
    main._freeze_legacy_work_order(inc,'manager')
    from procsvc import work_orders
    request=inc.work_order_request
    d={'id':request['decision'],'asset':inc.asset,'origin':{'incident':inc.id},
       'chosen':request['option'],'approvedBy':request['by'],
       'options':[{'id':request['option'],'name':request['option_name'],'actions':[{'kind':'command'}]}]}
    with pytest.raises(ValueError, match='plant recovery'):
        work_orders.prepare(main._work_order_context(), d, request['item'])
    inc.state='RESOLVED'
    inc.card={'recommended':[]}  # A retry must use the approval snapshot.
    def execute(d,item):
        calls.append((deepcopy(d),deepcopy(item)))
        return {'ok':False,'error':'offline'} if len(calls)==1 else {'ok':True,'ref':'WO-real-legacy','code':'WO_CREATE'}
    monkeypatch.setattr(main,'exec_skill',execute)
    assert main._complete_legacy_work_order(inc)['ok'] is False and inc.state=='RESOLVED'
    assert main._complete_legacy_work_order(inc)['ok'] is True and inc.state=='CLOSED'
    assert inc.work_order['id']=='WO-real-legacy' and calls[0]==calls[1]


@pytest.mark.parametrize('first_fails', [False, True])
def test_legacy_work_order_only_api_closes_on_receipt_and_can_retry(monkeypatch, first_fails):
    from fastapi.testclient import TestClient
    from procsvc import main, decisions
    from test_instance_mode import _decision_payload, GUIDE_CARD_ACTIONS
    from test_machine import new_incident
    inc=new_incident(); inc.card['recommended']=deepcopy(GUIDE_CARD_ACTIONS)
    d=decisions.new(_decision_payload(inc.id))
    opt=d['options'][0];opt['kind']='work_order'
    opt['actions']=[a for a in opt['actions'] if a['code']=='WO_CREATE']
    monkeypatch.setattr(main,'incidents',{inc.id:inc});monkeypatch.setattr(main,'book',{d['id']:d})
    monkeypatch.setattr(main,'persist',lambda:None);monkeypatch.setattr(main,'_after',lambda _:None)
    monkeypatch.setattr(main,'_audit',lambda *a,**kw:None);monkeypatch.setattr(main,'record_decision',lambda _:None)
    monkeypatch.setattr(main.current_approval,'check',lambda *args:{'allowed':True,'scope':'receipt-test-source-double'})
    monkeypatch.setattr(instance_mode,'current',lambda:None)
    calls=[]
    def execute(decision,item):
        calls.append(deepcopy(item))
        result={'skill':item['skill'],'system':item['system'],'code':'WO_CREATE'}
        return result | ({'ok':False,'error':'offline'} if first_fails and len(calls)==1 else {'ok':True,'ref':'WO-api-real'})
    monkeypatch.setattr(main,'exec_skill',execute)
    client=TestClient(main.app)
    response=client.post(f'/api/incidents/{inc.id}/decide',json={'decision':d['id'],'option':opt['id'],'role':'role:prod-mgr','by':'manager'})
    assert response.status_code==200, response.text
    if first_fails:
        assert inc.state=='AWAITING_APPROVAL' and inc.work_order is None
        response=client.post(f'/api/incidents/{inc.id}/work-order-retry')
        assert response.status_code==200,response.text
        assert calls[0]==calls[1]
    assert inc.state=='CLOSED' and inc.cmd_id is None and inc.work_order['id']=='WO-api-real'
    assert 'REJECTED_BY_OPERATOR' not in {h['state'] for h in inc.history}
