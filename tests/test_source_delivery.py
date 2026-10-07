"""Receipt commit precedes Kafka offset, pinned input precedes runtime dispatch."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
import pytest
from procsvc import main,engine
from procsvc.source_delivery import SourcePending
from test_instance_mode import world,ALERT,NoFx


def test_receipt_replay_uses_original_definition_after_default_changes(world):
    rt=world['rt'];policy=rt.alert_policy(ALERT['pattern'])
    changed=deepcopy(rt.defn.raw);changed['version']='later-default'
    changed['alertPolicy']['patterns']['COOLER_DEGRADATION']['limit']=40
    rt.register_definition(changed);rt.defn=engine.Definition.from_dict(changed)
    result=rt.receive_alert(ALERT,policy)
    stored=rt.repo.get_instance(result['instance'])
    assert stored['proc_def_version']==policy['version']
    assert world['incidents'][result['incident']].recovery[2]==55
    assert rt.receive_alert(ALERT,policy)==result and len(world['incidents'])==1


def test_incident_only_partial_write_rejoins_one_original_event(world,monkeypatch):
    rt=world['rt'];policy=rt.alert_policy(ALERT['pattern']);original=rt.repo.insert_instance
    def fail(_):raise OSError('fixture PG create failure')
    monkeypatch.setattr(rt.repo,'insert_instance',fail)
    with pytest.raises(OSError):rt.receive_alert(ALERT,policy)
    assert len(world['incidents'])==1 and not rt.repo.list_instances()
    inc_id=next(iter(world['incidents']))
    monkeypatch.setattr(rt.repo,'insert_instance',original)
    assert rt.receive_alert(ALERT,policy)['incident']==inc_id and len(world['incidents'])==1


def test_policy_tampering_is_not_a_new_recovery_criterion(world):
    rt=world['rt'];policy=rt.alert_policy(ALERT['pattern']);policy['criterion']=['TS1','<',200]
    with pytest.raises(ValueError):rt.receive_alert(ALERT,policy)
    assert not world['incidents']


def source_context(world,monkeypatch):
    monkeypatch.setattr(main,'incidents',world['incidents'])
    monkeypatch.setattr(main,'persist',world['ctx'].persist)
    monkeypatch.setattr(main,'Fx',lambda inc:NoFx())


def test_clear_waits_for_raise_then_preserves_raw_alarm(world,monkeypatch):
    source_context(world,monkeypatch);clear=dict(ALERT,state='CLEAR')
    row={'kind':'CLEAR','payload':clear}
    with pytest.raises(SourcePending):main._apply_source_event(row)
    result=world['rt'].receive_alert(ALERT,world['rt'].alert_policy(ALERT['pattern']))
    observed=main._apply_source_event(row);inc=world['incidents'][result['incident']]
    assert observed['cleared'] and inc.card['alert']==ALERT and inc.cmd_id is None
    assert main._apply_source_event(row)==observed


def test_late_ack_cannot_override_restart_review(world,monkeypatch):
    source_context(world,monkeypatch);rt=world['rt'];rt.on_alert_raise(ALERT)
    inc=next(iter(world['incidents'].values()));inc.cmd_id='old-cmd';inc.state='ESCALATED';inc.reason='PROCESS_RESTART_REVIEW'
    observed=main._apply_source_event({'kind':'ACK','payload':{'asset':inc.asset,'cmdId':'old-cmd','result':'DONE'}})
    assert observed['state']=='ESCALATED' and inc.ack is None and inc.reason=='PROCESS_RESTART_REVIEW'


@pytest.mark.parametrize('fail_attempt,commit_error',[(1,False),(2,False),(None,True)])
def test_offset_never_precedes_receipt_and_redelivery_is_safe(monkeypatch,fail_attempt,commit_error):
    """A033 contract under the A080 batched path: a batch is received on one connection, the offset is committed once per
    batch and only up to the last *received* delivery; a failed receipt (first or second of the batch) is retried and
    nothing is ever committed past it; a commit failure is tolerated (redelivery passes receive() again)."""
    events=[];attempts=0
    class Inbox:
        def receive_many(self,items):
            nonlocal attempts
            rows=[]
            for i,(record,policy) in enumerate(items):
                attempts+=1
                if fail_attempt and attempts==fail_attempt:
                    events.append('receipt-failed-'+str(record['offset_no']));return rows,OSError('fixture DB unavailable'),({} if rows else None)
                events.append('saved-'+str(record['offset_no']));rows.append(record)
            return rows,None,{}
        def latest_states(self):return {}
    class Consumer:
        calls=0
        async def getmany(self,timeout_ms,max_records):
            self.calls+=1
            if self.calls==1:
                return {('alerts',0):[SimpleNamespace(topic='alerts',partition=0,offset=n,value=json.dumps(dict(ALERT,alertId=str(n))).encode()) for n in (1,2)]}
            raise asyncio.CancelledError   # the fixture stream ends
        async def commit(self,offsets):
            target=next(iter(offsets.values()));events.append('commit-'+str(target))
            assert 'saved-'+str(target-1) in events                    # never past a missing receipt
            if commit_error and target==3:raise OSError('fixture rebalance')
    async def producer():return object()
    async def consumer(*a,**kw):
        assert kw['auto_commit'] is False and kw['raw_values'] is True
        return Consumer()
    async def no_wait(*_):pass
    monkeypatch.setattr(main,'source_inbox',Inbox());monkeypatch.setattr(main,'make_consumer',consumer)
    monkeypatch.setattr(main,'make_producer',producer);monkeypatch.setattr(main.asyncio,'sleep',no_wait)
    monkeypatch.setattr(main.instance_mode,'current',lambda:SimpleNamespace(alert_policy=lambda p:{'pattern':p}))
    with pytest.raises(asyncio.CancelledError):asyncio.run(main.consume())
    assert events[-2:]==['saved-2','commit-3']
    if fail_attempt==1: assert events[:2]==['receipt-failed-1','saved-1'] and 'commit-2' not in events
    if fail_attempt==2: assert events[:3]==['saved-1','receipt-failed-2','commit-2']        # committed up to the received one only
    if commit_error: assert main.state.get('source_receive_error') is None
