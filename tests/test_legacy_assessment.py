from copy import deepcopy
from datetime import timedelta

import pytest

from procsvc import engine,instance_mode,task_deferral
from procsvc.legacy_assessment import LegacyAssessment
from test_instance_mode import world,ALERT,NOW,_decision_payload,GUIDE_CARD_ACTIONS


HELD={'id':'fixture','status':'WITHHELD','error':'2분 근거 불일치',
      'card':{'evidence_status':{'status':'UNSUPPORTED'}},'steps':[{'name':'evidence','output':{'value':180,'passed':False}}]}


def setup(world,evaluate):
    rt,ctx=world['rt'],world['ctx']
    inst=rt.on_alert_raise(ALERT,now=NOW)
    pid=inst['proc_inst_id'];inc=engine.variables(inst)['incident']
    wi=next(w for w in rt.repo.list_workitems(proc_inst_id=pid) if w['activity_id']=='task:diagnose')
    publications=[]
    def publish(payload,card):
        publications.append(deepcopy(payload));ctx.book[payload['id']]=deepcopy(payload)
        rt.hooks.update_incident_card(inc,card)
        return payload
    worker=LegacyAssessment(rt,evaluate,publish,instance_mode._bridge_legacy_agent,lease_seconds=2)
    return rt,inst,wi,worker,publications


def supported(inst):
    payload=_decision_payload(engine.variables(inst)['incident'])
    return {'status':'EVALUATED','evaluation':payload,'card':{'alert':ALERT,'recommended':GUIDE_CARD_ACTIONS,
                                                            'cause':'cause:cooler-fin-fouling'}}


def test_withheld_is_pending_and_explicit_retry_reads_new_source(world):
    calls=[]
    rt,inst,wi,worker,published=setup(world,lambda a:calls.append(a) or deepcopy(HELD))
    assert worker.tick(NOW)==1
    pending=rt.repo.get_workitem(wi['id'])
    assert pending['status']=='PENDING' and not published
    assert pending['draft']['_deferral']['assessment']['status']=='UNSUPPORTED'
    assert worker.tick(NOW+timedelta(seconds=3))==0
    task_deferral.reassess(rt.repo,'hyd',wi['id'],deferral_id=pending['draft']['_deferral']['id'],
                          request_id='new-observation',by='tester',reason='new measurements')
    worker.evaluate=lambda a:calls.append(a) or supported(inst)
    assert worker.tick(NOW+timedelta(seconds=4))==1
    rows={w['activity_id']:w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])}
    assert len(calls)==2 and len(published)==1
    assert all(rows[k]['status']=='DONE' for k in ('task:diagnose','task:candidates','task:compliance','task:rank'))
    assert rows['task:select']['status']=='IN_PROGRESS'
    assert not world['executed']  # enterprise effects are still absent


def test_committed_bundle_survives_worker_recreation_without_requery(world):
    rt,inst,wi,worker,published=setup(world,lambda _:pytest.fail('should use saved result'))
    row=worker.claim(wi['id'],NOW);worker.save_reply(row,supported(inst))
    fresh=LegacyAssessment(rt,lambda _:pytest.fail('must not read again'),worker.publish,worker.bridge)
    assert fresh.tick(NOW)==1 and len(published)==1
    assert fresh.tick(NOW)==0


def test_expired_attempt_is_replaced_and_old_response_cannot_publish(world):
    rt,inst,wi,worker,published=setup(world,lambda _:supported(inst))
    old=worker.claim(wi['id'],NOW)
    assert worker.claim(wi['id'],NOW+timedelta(seconds=1)) is None
    fresh=worker.claim(wi['id'],NOW+timedelta(seconds=3))
    assert fresh['consumer']!=old['consumer']
    assert not worker.save_reply(old,supported(inst)) and not worker.apply_reply(old)
    assert worker.save_reply(fresh,supported(inst)) and worker.apply_reply(fresh)
    assert len(published)==1


def test_cancel_during_evaluation_does_not_publish(world):
    rt,inst,wi,worker,published=setup(world,lambda _:None)
    def evaluate(_):
        current=rt.repo.get_workitem(wi['id']);current['status']='CANCELLED';rt.repo.update_workitem(current)
        return supported(inst)
    worker.evaluate=evaluate
    assert worker.tick(NOW)==1 and not published
    assert rt.repo.get_workitem(wi['id'])['status']=='CANCELLED'


def test_foreign_cli_claim_is_not_taken_over(world):
    rt,inst,wi,worker,published=setup(world,lambda _:pytest.fail('foreign task'))
    rt.repo.fetch_pending_task('cliagents','actual-codex-claim',tenant_id='hyd')
    assert worker.tick(NOW)==0


@pytest.mark.parametrize('reply',[None,{}, {'status':'EVALUATED','evaluation':{},'card':{}}])
def test_invalid_source_response_defers_instead_of_looping_or_advancing(world,reply):
    rt,inst,wi,worker,published=setup(world,lambda _:reply)
    assert worker.tick(NOW)==1 and not published
    assert rt.repo.get_workitem(wi['id'])['draft']['_deferral']['assessment']['status']=='UNKNOWN'


def test_connection_error_is_persisted_with_no_publication(world):
    def unavailable(_):raise OSError('agent unavailable')
    rt,inst,wi,worker,published=setup(world,unavailable)
    worker.tick(NOW)
    assert 'agent unavailable' in rt.repo.get_workitem(wi['id'])['log'] and not published


def test_saved_response_is_immutable(world):
    rt,inst,wi,worker,published=setup(world,lambda _:None)
    row=worker.claim(wi['id'],NOW);worker.save_reply(row,HELD)
    with pytest.raises(ValueError,match='immutable'):worker.save_reply(row,supported(inst))


def test_large_trace_is_explicitly_truncated_and_does_not_strand_claim(world):
    held=deepcopy(HELD);held['steps']=[{'output':'근거'*80_000}];held['error']='사유'*3000
    rt,inst,wi,worker,published=setup(world,lambda _:held)
    worker.tick(NOW)
    row=rt.repo.get_workitem(wi['id']);assessment=row['draft']['_deferral']['assessment']
    assert row['status']=='PENDING' and not published
    assert assessment['evidence']['trace_truncated'] and len(assessment['evidence']['trace_sha256'])==64
    assert len(assessment['reason'])==4000


def test_publication_failure_reuses_saved_bundle_and_stable_id(world):
    calls=[]
    rt,inst,wi,worker,published=setup(world,lambda _:calls.append(1) or supported(inst))
    real_publish=worker.publish;attempts=[]
    def fail_after_publication(payload,card):
        attempts.append(payload['id']);real_publish(payload,card)
        raise OSError('publication acknowledgement lost')
    worker.publish=fail_after_publication
    assert worker.tick(NOW)==1
    assert rt.repo.get_workitem(wi['id'])['status']=='IN_PROGRESS'
    assert worker.tick(NOW+timedelta(seconds=1))==0  # do not monopolize the queue
    assert 'publication acknowledgement lost' in rt.repo.get_workitem(wi['id'])['log']
    worker.publish=lambda payload,card:attempts.append(payload['id']) or real_publish(payload,card)
    worker.tick(NOW+timedelta(seconds=3))
    assert len(calls)==1 and attempts[0]==attempts[1]
    assert rt.repo.get_workitem(wi['id'])['status']=='DONE'


def test_old_decision_cannot_satisfy_queued_reassessment(world):
    rt,inst,wi,worker,published=setup(world,lambda _:deepcopy(HELD))
    worker.tick(NOW)
    row=rt.repo.get_workitem(wi['id'])
    task_deferral.reassess(rt.repo,'hyd',wi['id'],deferral_id=row['draft']['_deferral']['id'],
                          request_id='fresh',by='tester',reason='new source')
    instance_mode._bridge_legacy_agent(_decision_payload(engine.variables(inst)['incident']))
    current=rt.repo.get_workitem(wi['id'])
    assert current['status']=='IN_PROGRESS' and current.get('output') is None and current.get('consumer') is None


def test_failed_publication_does_not_starve_another_instance(world):
    rt,inst,wi,worker,published=setup(world,lambda _:None)
    claim=worker.claim(wi['id'],NOW);worker.save_reply(claim,supported(inst))
    worker.publish=lambda *_:(_ for _ in ()).throw(OSError('publication down'))
    worker.tick(NOW)
    second=rt.on_alert_raise(ALERT|{'alertId':'independent-alert','asset':'HYD-03'},now=NOW)
    worker.evaluate=lambda _:deepcopy(HELD)
    assert worker.tick(NOW+timedelta(seconds=1))==1
    other=next(w for w in rt.repo.list_workitems(proc_inst_id=second['proc_inst_id']) if w['activity_id']=='task:diagnose')
    assert other['status']=='PENDING' and rt.repo.get_workitem(wi['id'])['status']=='IN_PROGRESS'


def test_legacy_claim_leaves_no_worker_lease_to_reclaim(world, monkeypatch):
    """A115 (r14 A8, infra-docker init.sql:2559-2564): the legacy claim keeps its own expiry and never renews the worker
    lease, so it clears it. Before, the shared claim's now+120 s stayed on the row and a cliagents worker reclaimed it
    after 120 s (a delivery retry can wait longer), running the same diagnosis twice."""
    rt,inst,wi,worker,published=setup(world,lambda _:pytest.fail('not evaluated here'))
    row=worker.claim(wi['id'],NOW)
    assert row and rt.repo.get_workitem(wi['id'])['lease_until'] is None
    from procsvc import procdb
    later=procdb.time.time()+procdb.LEASE_SECONDS+60
    monkeypatch.setattr(procdb.time,'time',lambda:later)
    assert rt.repo.fetch_pending_task('cliagents','agent-worker:other',tenant_id='hyd')==[]
    assert rt.repo.expire_worker_leases()==0
    assert rt.repo.get_workitem(wi['id'])['consumer']==row['consumer']
