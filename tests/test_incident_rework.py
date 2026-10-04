from copy import deepcopy
import uuid

import pytest
from procsvc import engine, decisions, decision_scope, main
from worker.context import process_scope
from test_instance_mode import world, NOW
from test_approval_delivery import ready, choose


def fixture(world, monkeypatch, failed=False):
    rt, inst, inc, decision, selection = ready(world)
    world['ctx'].approval_receipts = lambda did: []
    if failed:
        with monkeypatch.context() as patch:
            patch.setattr(rt.hooks, 'deliver_approval', lambda _: (_ for _ in ()).throw(ValueError('source changed')))
            choose(rt, decision, selection)
    pid = inst['proc_inst_id']
    rank = engine._by_activity(rt.repo.list_workitems(proc_inst_id=pid))['task:rank']
    return rt, pid, inc, decision, selection, rank


def rerun(rt, pid, rank, role='role:prod-mgr', token=None, request_id=None):
    return rt.request_rework(pid, rank['id'], request_id or str(uuid.uuid4()),
        token or rt.preview_rework(pid, rank['id'])['snapshot_token'], 'rework reviewer', role,
        'New source evidence requires new judgment', now=NOW)


def produce(world, rt, pid, original):
    row, = rt.repo.fetch_pending_task('cliagents', 'new-worker', tenant_id=rt.tenant_id, proc_inst_id=pid)
    scope = process_scope(row); inst = rt.repo.get_instance(pid)
    decision_scope.validate_submission(inst, rt.definition_for(inst), row, scope)
    decision = decisions.new(deepcopy(original))
    decision.pop('process_approval_id', None)  # a fresh worker result carries no old consent owner
    decision.update(id='D-new-'+uuid.uuid4().hex, state='PENDING_APPROVAL', chosen=None)
    decision['origin']['process_scope'] = scope
    world['book'][decision['id']] = decision
    result = {'decision': {'recommended': decision['recommended']}, 'decision_id': decision['id']}
    assert rt.repo.save_task_result(row['id'], result, True, expected_consumer='new-worker')
    rt.poll_once(now=NOW)
    return decision, row


def test_active_incident_rework_preserves_original_and_requires_new_decision_and_consent(world, monkeypatch):
    rt, pid, inc, old, selection, rank = fixture(world, monkeypatch)
    original = deepcopy((old, inc.to_dict(), rank))
    preview = rt.preview_rework(pid, rank['id'])
    assert preview['execution_available'] and preview['retired_decisions'] == [old['id']]
    result = rerun(rt, pid, rank)
    assert result['generation'] == 1 and engine.variables(rt.repo.get_instance(pid)).get('decision_id') is None
    assert (old, inc.to_dict(), rt.repo.get_workitem(rank['id'])) == original
    assert rt.repo.get_workitem(selection['id'])['status'] == 'CANCELLED'
    with pytest.raises(ValueError): choose(rt, old, selection)
    decision, produced = produce(world, rt, pid, old)
    current = engine._by_activity(rt.repo.list_workitems(proc_inst_id=pid))['task:select']
    assert current['status'] == 'IN_PROGRESS' and inc.cmd_id is None and world['executed'] == []
    with pytest.raises(ValueError): choose(rt, old, current)
    choose(rt, decision, current)
    assert inc.cmd_id and rt.repo.get_approval(current['id'], rt.tenant_id)['decision_id'] == decision['id']
    assert rt.repo.get_workitem(produced['id'])['status'] == 'DONE'
    assert old == original[0]


def test_failed_consent_is_retired_atomically_without_changing_its_payload_or_incident(world, monkeypatch):
    rt, pid, inc, old, selection, rank = fixture(world, monkeypatch, failed=True)
    prior = rt.repo.get_approval(selection['id'],rt.tenant_id); card = deepcopy(old); incident = deepcopy(inc.to_dict())
    token = rt.preview_rework(pid,rank['id'])['snapshot_token']
    rid = str(uuid.uuid4()); result = rerun(rt,pid,rank,token=token,request_id=rid)
    retired = rt.repo.get_approval(selection['id'],rt.tenant_id)
    assert retired['status']=='DISCARDED' and retired['payload']==prior['payload'] and retired['error']==prior['error']
    assert retired['history'][:-1]==prior['history'] and retired['history'][-1]['via']=='rework'
    assert old==card and inc.to_dict()==incident
    assert not set(engine.variables(rt.repo.get_instance(pid))) & {'decision_id','commands','chosen_option','approved_by','approved_role'}
    assert rerun(rt,pid,rank,token=token,request_id=rid)==result
    with pytest.raises(ValueError): rt.retry_approval(selection['id'],'manager','role:prod-mgr',now=NOW)
    assert inc.cmd_id is None and world['executed']==[]


def test_pending_undelivered_consent_can_be_retired_under_same_transition(world, monkeypatch):
    rt,pid,inc,old,selection,rank=fixture(world,monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(rt,'_after_commit',lambda *a,**k:None)
        choose(rt,old,selection)
    assert rt.repo.get_approval(selection['id'],rt.tenant_id)['status']=='PENDING'
    rerun(rt,pid,rank)
    rt.reconcile_approvals(now=NOW)
    assert rt.repo.get_approval(selection['id'],rt.tenant_id)['status']=='DISCARDED' and inc.cmd_id is None


@pytest.mark.parametrize('defect', ['cleared','ended','command','actions','ack','work_order','request','local','enterprise','untracked_runtime','untracked_consent'])
def test_effects_and_unknown_provenance_prevent_rework(world,monkeypatch,defect):
    rt,pid,inc,old,selection,rank=fixture(world,monkeypatch)
    if defect=='cleared': inc.cleared=True
    if defect=='ended': inc.state='ESCALATED'
    if defect=='command': inc.cmd_id='CMD-existing'
    if defect=='actions': inc.actions=[{'code':'FAN_SET','fan_pct':100}]
    if defect=='ack': inc.ack={'result':'DONE'}
    if defect=='work_order': inc.work_order={'id':'WO-existing'}
    if defect=='request': inc.work_order_request={'key':'existing'}
    if defect=='local': old['executions']=[{'status':'FAILED','ref':None}]
    if defect=='enterprise': world['ctx'].approval_receipts=lambda did:[{'decision':did,'ref':'PR-existing'}]
    if defect=='untracked_consent': decisions.approve(old,old['options'][0]['id'],'unknown manager','role:prod-mgr')
    if defect=='untracked_runtime':
        inst=rt.repo.get_instance(pid);engine.set_variables(rt.definition_for(inst),inst,{'approved_by':'untracked'})
        rt.repo.update_instance(inst)
    before=rt.instance_view(pid)
    assert not rt.preview_rework(pid,rank['id'])['execution_available']
    with pytest.raises(ValueError): rerun(rt,pid,rank)
    assert rt.instance_view(pid)==before


def test_unknown_or_changed_effect_source_does_not_mutate_rework(world,monkeypatch):
    rt,pid,inc,old,selection,rank=fixture(world,monkeypatch)
    preview=rt.preview_rework(pid,rank['id']);before=rt.instance_view(pid)
    world['ctx'].approval_receipts=lambda did:(_ for _ in ()).throw(OSError('ledger offline'))
    with pytest.raises(OSError): rerun(rt,pid,rank,token=preview['snapshot_token'])
    assert rt.instance_view(pid)==before
    world['ctx'].approval_receipts=lambda did:[{'decision':did,'ref':'late receipt'}]
    with pytest.raises(ValueError,match='바뀌었습니다'): rerun(rt,pid,rank,token=preview['snapshot_token'])
    assert rt.instance_view(pid)==before


def test_lower_role_cannot_retire_failed_higher_role_consent(world,monkeypatch):
    rt,pid,inc,old,selection,rank=fixture(world,monkeypatch,failed=True)
    before=rt.instance_view(pid)
    with pytest.raises(PermissionError): rerun(rt,pid,rank,role='role:operator')
    assert rt.instance_view(pid)==before


def test_last_write_failure_rolls_back_approval_retirement_and_generation(world,monkeypatch):
    rt,pid,inc,old,selection,rank=fixture(world,monkeypatch,failed=True)
    before=deepcopy((rt.repo.instances,rt.repo.workitems,rt.repo.approvals,rt.repo.reworks,rt.repo.events,world['book'],inc.to_dict()))
    monkeypatch.setattr(rt.repo,'record_events',lambda _:(_ for _ in ()).throw(OSError('commit boundary')))
    with pytest.raises(OSError): rerun(rt,pid,rank)
    assert (rt.repo.instances,rt.repo.workitems,rt.repo.approvals,rt.repo.reworks,rt.repo.events,world['book'],inc.to_dict())==before


def test_selection_only_rework_cannot_reuse_old_judgment(world,monkeypatch):
    rt,pid,inc,old,selection,rank=fixture(world,monkeypatch)
    p=rt.preview_rework(pid,selection['id'])
    assert not p['execution_available'] and 'rework_requires_new_decision' in {b['code'] for b in p['blockers']}


def test_second_rework_distinguishes_proven_cancelled_todo_from_effect_log(world,monkeypatch):
    rt,pid,inc,old,selection,rank=fixture(world,monkeypatch)
    rerun(rt,pid,rank)
    newrank=engine._by_activity(rt.repo.list_workitems(proc_inst_id=pid))['task:rank']
    p=rt.preview_rework(pid,newrank['id'])
    assert p['execution_available'] and p['started_services']==[]
    result=rerun(rt,pid,newrank)
    assert result['generation']==2
    suspicious=next(w for w in rt.repo.list_workitems(proc_inst_id=pid) if w['tool']=='incident:command' and w['status']=='CANCELLED')
    suspicious['log'] += 'external call attempted; '
    rt.repo.update_workitem(suspicious)
    current=engine._by_activity(rt.repo.list_workitems(proc_inst_id=pid))['task:rank']
    assert not rt.preview_rework(pid,current['id'])['execution_available']


def test_retired_original_approved_decision_does_not_ambiguate_new_command(world,monkeypatch):
    rt,pid,inc,old,selection,rank=fixture(world,monkeypatch)
    rerun(rt,pid,rank);new,_=produce(world,rt,pid,old)
    # Stored original may have been materialized by an interrupted delivery.
    decisions.approve(old,old['options'][0]['id'],'old manager','role:prod-mgr')
    decisions.approve(new,new['options'][0]['id'],'new manager','role:prod-mgr')
    monkeypatch.setattr(main,'book',world['book'])
    seen=[];monkeypatch.setattr(main,'_check_current_approval',lambda d,*a:seen.append(d['id']))
    monkeypatch.setattr(main.machine,'on_approve',lambda *a,**k:{'cmdId':'fixture'})
    monkeypatch.setattr(main,'_after',lambda *a:None)
    commands=[{'code':'FAN_SET','fan_pct':100},{'code':'LOAD_SET','load_pct':80}]
    main._approve_incident(inc,'new manager',commands)
    assert seen==[new['id']]
