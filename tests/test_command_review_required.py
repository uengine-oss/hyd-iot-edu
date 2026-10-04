"""An explicit current-condition refusal needs fresh consent, not blind retry."""
from copy import deepcopy
import pytest
from procsvc import current_approval, engine
from test_instance_mode import world, NOW
from test_approval_delivery import ready, choose


def test_command_refusal_stops_once_and_preserves_structured_review_evidence(world,monkeypatch):
    rt,inst,inc,d,selection=ready(world)
    report={'allowed':False,'decision':d['id'],'option':d['options'][0]['id'],
            'reasons':['order_due_h changed'],'checked_at':'2026-10-04T11:00:00Z',
            'current_facts':{'order_due_h':36}}
    calls=[]
    def refuse(*args):
        calls.append(args)
        return current_approval.require(lambda *_:report,d,d['options'][0]['id'],'role:prod-mgr')
    monkeypatch.setattr(rt.hooks,'approve_commands',refuse)
    choose(rt,d,selection)
    command=engine._by_activity(rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']))['task:command']
    assert command['status']=='PENDING' and command['retry']==1
    assert rt.repo.get_approval(selection['id'],rt.tenant_id)['status']=='DELIVERED'
    events=rt.repo.list_events(proc_inst_id=inst['proc_inst_id'])
    event=next(e for e in events if e['job_id']=='TASK_REVIEW_REQUIRED')
    assert event['data']['assessment']==report
    assert event['data']['recovery']=='new_judgment_and_consent'
    saved=deepcopy(event)
    report['current_facts']['order_due_h']=999
    rt.poll_once(now=NOW);rt.poll_once(now=NOW)
    assert len(calls)==1 and inc.cmd_id is None
    assert next(e for e in rt.repo.list_events(proc_inst_id=inst['proc_inst_id']) if e['job_id']=='TASK_REVIEW_REQUIRED')==saved


@pytest.mark.parametrize('response',[None,{}, {'allowed':None}, {'allowed':'false'}])
def test_unavailable_or_malformed_result_is_not_explicit_current_condition_refusal(response):
    with pytest.raises(ValueError) as error:current_approval.require(lambda *_:response,{'id':'D'},'O','role:R')
    assert type(error.value).__name__!='ApprovalReviewRequired'


def test_network_failure_keeps_bounded_retry_instead_of_fabricating_review_assessment(world,monkeypatch):
    rt,inst,inc,d,selection=ready(world)
    monkeypatch.setattr(rt.hooks,'approve_commands',lambda *a:(_ for _ in ()).throw(OSError('source unavailable')))
    choose(rt,d,selection)
    command=engine._by_activity(rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']))['task:command']
    assert command['status']=='SUBMITTED' and command['retry']==1
    assert not any(e['job_id']=='TASK_REVIEW_REQUIRED' for e in rt.repo.list_events(proc_inst_id=inst['proc_inst_id']))
    rt.poll_once(now=NOW);rt.poll_once(now=NOW)
    command=rt.repo.get_workitem(command['id'])
    assert command['status']=='PENDING' and command['retry']==3 and inc.cmd_id is None
