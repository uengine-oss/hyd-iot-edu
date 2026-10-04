"""A delivered consent does not prove that its later PLC command was issued."""
from copy import deepcopy
import uuid
import pytest
from procsvc import engine
from test_instance_mode import world,NOW
from test_approval_delivery import ready,choose
from test_incident_rework import produce,rerun


def blocked_command(world,monkeypatch):
    rt,inst,inc,decision,selection=ready(world)
    world['ctx'].approval_receipts=lambda did:[]
    def blocked(*args):raise ValueError('current forecast worsened before command')
    with monkeypatch.context() as patch:
        patch.setattr(rt.hooks,'approve_commands',blocked)
        choose(rt,decision,selection)
        rt.poll_once(now=NOW);rt.poll_once(now=NOW)
    work=engine._by_activity(rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']))
    assert work['task:command']['status']=='PENDING' and inc.cmd_id is None
    assert rt.repo.get_approval(selection['id'],rt.tenant_id)['status']=='DELIVERED'
    return rt,inst,inc,decision,selection,work


def test_delivered_but_unissued_command_allows_fresh_judgment_and_consent(world,monkeypatch):
    rt,inst,inc,old,selection,work=blocked_command(world,monkeypatch)
    original=deepcopy(old);approval=rt.repo.get_approval(selection['id'],rt.tenant_id)
    preview=rt.preview_rework(inst['proc_inst_id'],work['task:rank']['id'])
    assert preview['execution_available'],preview['blockers']
    rerun(rt,inst['proc_inst_id'],work['task:rank'])
    retired=rt.repo.get_approval(selection['id'],rt.tenant_id)
    assert retired['status']=='DISCARDED' and retired['payload']==approval['payload']
    assert retired['history'][:-1]==approval['history']
    assert rt.repo.get_workitem(work['task:command']['id'])['status']=='CANCELLED'
    assert old==original and inc.cmd_id is None
    fresh,_=produce(world,rt,inst['proc_inst_id'],old)
    new_selection=engine._by_activity(rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']))['task:select']
    assert inc.cmd_id is None
    choose(rt,fresh,new_selection)
    assert inc.cmd_id is not None and old==original


def test_cleared_case_can_be_reviewed_and_cancelled_without_false_success(world,monkeypatch):
    rt,inst,inc,old,selection,work=blocked_command(world,monkeypatch)
    inc.state='RESOLVED_WITHOUT_ACTION';inc.cleared=True
    before=deepcopy(inc.to_dict());original=deepcopy(old)
    preview=rt.preview_approval_discard(selection['id'],'reviewer','role:prod-mgr')
    assert preview['can_discard']
    request=str(uuid.uuid4())
    result=rt.discard_approval(selection['id'],'reviewer','role:prod-mgr','Alarm cleared before command',request,now=NOW)
    assert result['status']=='DISCARDED'
    assert rt.repo.get_instance(inst['proc_inst_id'])['status']=='CANCELLED'
    assert inc.to_dict()==before and old==original and not world['executed']
    assert rt.discard_approval(selection['id'],'reviewer','role:prod-mgr','Alarm cleared before command',request,now=NOW)==result


@pytest.mark.parametrize('effect',['cmd','actions','ack','receipt','local','delivery','unknown_service','issued_log'])
def test_post_delivery_rework_stays_blocked_for_actual_or_uncertain_effects(world,monkeypatch,effect):
    rt,inst,inc,old,selection,work=blocked_command(world,monkeypatch)
    if effect=='cmd':inc.cmd_id='CMD-known'
    if effect=='actions':inc.actions=[{'code':'FAN_SET','fan_pct':100}]
    if effect=='ack':inc.ack={'result':'DONE'}
    if effect=='receipt':world['ctx'].approval_receipts=lambda did:[{'decision':did,'ref':'WO-known'}]
    if effect=='local':old['executions']=[{'status':'FAILED','code':'PR_CREATE'}]
    if effect=='delivery':
        row=rt.repo.get_approval(selection['id'],rt.tenant_id);row['results']=[{'ok':False}];rt.repo.update_approval(row)
    if effect=='unknown_service':
        row=work['task:work-order'];row['status']='PENDING';rt.repo.update_workitem(row)
    if effect=='issued_log':
        row=work['task:command'];row['log']+='action.cmd CMD-missing issued; waiting ACK; ';rt.repo.update_workitem(row)
    assert not rt.preview_rework(inst['proc_inst_id'],work['task:rank']['id'])['execution_available']
    inc.state='RESOLVED_WITHOUT_ACTION';inc.cleared=True
    with pytest.raises(ValueError):rt.preview_approval_discard(selection['id'],'reviewer','role:prod-mgr')


@pytest.mark.parametrize('defect',['inflight','owner','generation','commands','runtime','other_ledger'])
def test_delivered_consent_requires_exact_ownership_and_stopped_command(world,monkeypatch,defect):
    rt,inst,inc,old,selection,work=blocked_command(world,monkeypatch)
    if defect in {'inflight','generation'}:
        row=work['task:command']
        if defect=='inflight':row.update(status='SUBMITTED',consumer='live-service')
        else:
            # Corrupt source fixture: normal repository updates prohibit this.
            rt.repo.workitems[row['id']]['generation']=12
        if defect=='inflight':rt.repo.update_workitem(row)
    if defect=='owner':old['process_approval_id']='other-approval'
    if defect=='commands':
        saved=rt.repo.get_instance(inst['proc_inst_id']);engine.set_variables(rt.definition_for(saved),saved,{'commands':[]});rt.repo.update_instance(saved)
    if defect=='runtime':
        saved=rt.repo.get_instance(inst['proc_inst_id']);engine.set_variables(rt.definition_for(saved),saved,{'approved_by':'other'});rt.repo.update_instance(saved)
    if defect=='other_ledger':
        sibling=deepcopy(old);sibling['id']='another-decision';world['book'][sibling['id']]=sibling
        world['ctx'].approval_receipts=lambda did:[] if did==old['id'] else [{'decision':did,'ref':'unknown-effect'}]
    assert not rt.preview_rework(inst['proc_inst_id'],work['task:rank']['id'])['execution_available']
    inc.state='RESOLVED_WITHOUT_ACTION';inc.cleared=True
    with pytest.raises(ValueError):rt.preview_approval_discard(selection['id'],'reviewer','role:prod-mgr')


def test_delivered_rework_checks_role_and_rolls_back_before_commit(world,monkeypatch):
    rt,inst,inc,old,selection,work=blocked_command(world,monkeypatch)
    before=rt.instance_view(inst['proc_inst_id']);card=deepcopy(old)
    with pytest.raises(PermissionError):rerun(rt,inst['proc_inst_id'],work['task:rank'],role='role:operator')
    assert rt.instance_view(inst['proc_inst_id'])==before
    with monkeypatch.context() as patch:
        patch.setattr(rt.repo,'record_events',lambda _:(_ for _ in ()).throw(OSError('commit failure')))
        with pytest.raises(OSError):rerun(rt,inst['proc_inst_id'],work['task:rank'])
    assert rt.instance_view(inst['proc_inst_id'])==before and old==card
    inc.state='RESOLVED_WITHOUT_ACTION';inc.cleared=True
    with pytest.raises(PermissionError):rt.preview_approval_discard(selection['id'],'reviewer','role:operator')
    with monkeypatch.context() as patch:
        patch.setattr(rt.repo,'update_instance',lambda _:(_ for _ in ()).throw(OSError('commit failure')))
        with pytest.raises(OSError):rt.discard_approval(selection['id'],'reviewer','role:prod-mgr','ended',str(uuid.uuid4()))
    assert rt.instance_view(inst['proc_inst_id'])==before and old==card


def test_repeat_rework_accepts_only_receipt_proven_unissued_cancellation(world,monkeypatch):
    rt,inst,inc,old,selection,work=blocked_command(world,monkeypatch)
    rerun(rt,inst['proc_inst_id'],work['task:rank'])
    current=engine._by_activity(rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']))['task:rank']
    assert rt.preview_rework(inst['proc_inst_id'],current['id'])['execution_available']
    rerun(rt,inst['proc_inst_id'],current)
    cancelled=rt.repo.get_workitem(work['task:command']['id']);cancelled['log']+='unknown effect; ';rt.repo.update_workitem(cancelled)
    current=engine._by_activity(rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']))['task:rank']
    assert not rt.preview_rework(inst['proc_inst_id'],current['id'])['execution_available']


def test_late_effect_and_unavailable_ledger_cannot_use_old_discard_preview(world,monkeypatch):
    rt,inst,inc,old,selection,work=blocked_command(world,monkeypatch)
    inc.state='RESOLVED_WITHOUT_ACTION';inc.cleared=True
    rt.preview_approval_discard(selection['id'],'reviewer','role:prod-mgr')
    before=rt.instance_view(inst['proc_inst_id'])
    world['ctx'].approval_receipts=lambda _:(_ for _ in ()).throw(OSError('ledger offline'))
    with pytest.raises(OSError):rt.discard_approval(selection['id'],'reviewer','role:prod-mgr','ended',str(uuid.uuid4()))
    world['ctx'].approval_receipts=lambda did:[{'decision':did,'ref':'late-effect'}]
    with pytest.raises(ValueError):rt.discard_approval(selection['id'],'reviewer','role:prod-mgr','ended',str(uuid.uuid4()))
    assert rt.instance_view(inst['proc_inst_id'])==before
