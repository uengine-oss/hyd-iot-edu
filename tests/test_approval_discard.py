"""Explicitly retire failed consent; never infer that missing replies undo effects."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from procsvc import instance_mode, instances
from test_approval_delivery import ready, choose
from test_instance_mode import world, NOW


def failed(world, monkeypatch, purchase=False):
    rt, inst, inc, decision, wi = ready(world, purchase=purchase)
    with monkeypatch.context() as patch:
        patch.setattr(rt.hooks, 'deliver_approval', lambda row: (_ for _ in ()).throw(ValueError('conditions changed')))
        choose(rt, decision, wi)
    inc.state = 'RESOLVED_WITHOUT_ACTION'
    world['ctx'].approval_receipts = lambda did: []
    return rt, inst, inc, decision, wi


def discard(rt, wi, request='request-1', role='role:prod-mgr'):
    return rt.discard_approval(wi['id'], 'reviewer', role, 'Source ended; retire failed consent', request, now=NOW)


def test_discard_preserves_consent_and_completed_work_and_is_idempotent(world, monkeypatch):
    rt, inst, inc, decision, wi = failed(world, monkeypatch)
    before = rt.repo.get_approval(wi['id'], rt.tenant_id)
    completed = [w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['status']=='DONE']
    result = discard(rt, wi)
    assert result['status']=='DISCARDED' and result['payload']==before['payload']
    assert result['error']==before['error'] and result['history'][:-1]==before['history']
    assert result['history'][-1]['effects']['enterprise_receipts']==[]
    assert rt.repo.get_instance(inst['proc_inst_id'])['status']=='CANCELLED'
    assert not rt.repo.get_instance(inst['proc_inst_id'])['current_activity_ids']
    for work in completed:
        assert rt.repo.get_workitem(work['id'])==work
    assert all(w['status'] in {'DONE','CANCELLED'} for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']))
    assert discard(rt, wi)==result
    with pytest.raises(ValueError, match='다른'):
        discard(rt, wi, request='different')
    with pytest.raises(ValueError):
        rt.retry_approval(wi['id'], 'reviewer', role='role:prod-mgr', now=NOW)
    rt.poll_once(now=NOW)
    assert inc.cmd_id is None and world['executed']==[]
    assert inc.state=='RESOLVED_WITHOUT_ACTION'


@pytest.mark.parametrize('mode', ['live', 'command', 'receipt', 'unknown', 'local-effect'])
def test_discard_refuses_live_or_effectful_or_unknown_work(world, monkeypatch, mode):
    rt, inst, inc, decision, wi = failed(world, monkeypatch, purchase=True)
    if mode=='live': inc.state='AWAITING_APPROVAL'
    if mode=='command': inc.cmd_id='CMD-already-sent'
    if mode=='receipt': world['ctx'].approval_receipts=lambda did:[{'decision':did,'ref':'PR-real'}]
    if mode=='unknown': world['ctx'].approval_receipts=lambda did:(_ for _ in ()).throw(OSError('DB unavailable'))
    if mode=='local-effect': decision['executions']=[{'status':'DONE','ref':'PR-real'}]
    before=deepcopy(rt.repo.get_approval(wi['id'],rt.tenant_id))
    with pytest.raises((ValueError,OSError)):
        discard(rt,wi)
    assert rt.repo.get_approval(wi['id'],rt.tenant_id)==before
    assert rt.repo.get_instance(inst['proc_inst_id'])['status']=='RUNNING'


def test_role_and_tenant_are_checked_before_discard_or_replay(world, monkeypatch):
    rt,inst,inc,d,wi=failed(world,monkeypatch)
    with pytest.raises(PermissionError): discard(rt,wi,role='role:operator')
    other=instances.InstanceRuntime(rt.repo,rt.defn,rt.hooks,tenant_id='other')
    with pytest.raises(KeyError): discard(other,wi)
    discard(rt,wi)
    with pytest.raises(PermissionError): discard(rt,wi,role='role:operator')


def test_discard_rollback_preserves_failed_approval_and_running_tasks(world, monkeypatch):
    rt,inst,inc,d,wi=failed(world,monkeypatch)
    before=rt.repo.get_approval(wi['id'],rt.tenant_id)
    with monkeypatch.context() as patch:
        patch.setattr(rt.repo,'update_instance',lambda _:(_ for _ in ()).throw(OSError('write failed')))
        with pytest.raises(OSError): discard(rt,wi)
    assert rt.repo.get_approval(wi['id'],rt.tenant_id)==before
    assert rt.repo.get_workitem(wi['id'])['status']=='SUBMITTED'
    assert rt.repo.get_instance(inst['proc_inst_id'])['status']=='RUNNING'


def test_two_discard_requests_have_one_committed_winner(world, monkeypatch):
    rt,inst,inc,d,wi=failed(world,monkeypatch)
    def attempt(request):
        try: return discard(rt,wi,request=request)['status']
        except ValueError:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,['one','two']))==['DISCARDED','conflict']
    row=rt.repo.get_approval(wi['id'],rt.tenant_id)
    assert sum(h['status']=='DISCARDED' for h in row['history'])==1


def test_discard_preview_has_no_mutation(world, monkeypatch):
    rt,inst,inc,d,wi=failed(world,monkeypatch)
    before=rt.repo.get_approval(wi['id'],rt.tenant_id)
    preview=rt.preview_approval_discard(wi['id'],'reviewer','role:prod-mgr')
    assert preview['can_discard'] and preview['incident']['state']=='RESOLVED_WITHOUT_ACTION'
    assert rt.repo.get_approval(wi['id'],rt.tenant_id)==before
    assert rt.repo.get_instance(inst['proc_inst_id'])['status']=='RUNNING'


@pytest.mark.parametrize('receipts',[None,{},[{'decision':'different','ref':'PR-1'}]])
def test_invalid_ledger_response_is_not_evidence_of_absence(world,monkeypatch,receipts):
    rt,inst,inc,d,wi=failed(world,monkeypatch)
    world['ctx'].approval_receipts=lambda _:receipts
    with pytest.raises(ValueError,match='응답 계약'):
        discard(rt,wi)
    assert rt.repo.get_approval(wi['id'],rt.tenant_id)['status']=='FAILED'


def test_another_started_service_prevents_discard_even_without_local_receipt(world,monkeypatch):
    rt,inst,inc,d,wi=failed(world,monkeypatch)
    command=next(w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['tool']=='incident:command')
    command['status']='SUBMITTED';rt.repo.update_workitem(command)
    with pytest.raises(ValueError,match='서비스'):
        discard(rt,wi)


def test_pending_consent_is_not_silently_discarded(world,monkeypatch):
    rt,inst,inc,d,wi=failed(world,monkeypatch)
    row=rt.repo.get_approval(wi['id'],rt.tenant_id);row['status']='PENDING';rt.repo.update_approval(row)
    with pytest.raises(ValueError,match='전달 실패'):
        discard(rt,wi)
