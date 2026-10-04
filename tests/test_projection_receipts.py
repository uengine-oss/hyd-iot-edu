import pytest
from procsvc.projection_receipt import ProjectionConflict,require
from procsvc.case_projection import CaseProjector
from procsvc.store import Store
from procsvc.projection_repair import inspect_case,repair_case
import sqlite3
import uuid
from test_case_projection import incident
from test_projection_recovery import runtime


@pytest.mark.parametrize('rows',[None,[],[None],[{}],[{'projection_key':'wrong','projection_revision':5,'projection_hash':'hash'}],
                                [{'projection_key':'key','projection_revision':4,'projection_hash':'hash'}],
                                [{'projection_key':'key','projection_revision':5,'projection_hash':'other'}]])
def test_only_an_exact_receipt_can_acknowledge_delivery(rows):
    with pytest.raises(ProjectionConflict):require(rows,'key',5,'hash')


def test_missing_case_receipt_blocks_new_events_and_survives_restart(tmp_path):
    path=tmp_path/'cases.db';store=Store(path);inc=incident();store.save({inc.id:inc},{},[])
    assert CaseProjector(store,lambda *a,**kw:[]).drain()==0
    assert store.case_projection_status()['items'][0]['last_error'].startswith('ProjectionConflict:')
    inc.reason='new event';store.save({inc.id:inc},{},[]);store.db.close();store=Store(path)
    assert store.case_projection_status()['pending']==2
    assert store.case_projection_batch()==[]


def test_execution_conflict_cannot_count_retries_past_graph_revision():
    rt,hooks=runtime();hooks.record_cypher=lambda *a,**kw:[]
    from test_instances import ALERT,NOW
    inst=rt.on_alert_raise(ALERT,now=NOW)
    pid=inst['proc_inst_id'];before=rt.repo._projection_sequence
    assert rt.repo.projection_status(rt.tenant_id,pid)['last_error'].startswith('ProjectionConflict:')
    for i in range(3):
        rt._project(inst)
    assert rt.repo._projection_sequence==before
    inst['proc_inst_name']='new source event';rt.repo.update_instance(inst)
    assert not rt.repo.pending_projections(rt.tenant_id)
    rt._project(inst)
    assert rt.repo.projection_status(rt.tenant_id,pid)['pending']>0


def test_repair_journal_failure_rolls_back_queue_and_quarantine_release(tmp_path):
    store=Store(tmp_path/'cases.db');inc=incident();store.save({inc.id:inc},{},[])
    CaseProjector(store,lambda *a,**kw:[]).drain()
    before=store.case_projection_status()
    store.db.execute("create trigger reject_repair before insert on projection_repairs begin select raise(abort,'journal offline'); end")
    with pytest.raises(sqlite3.IntegrityError,match='journal offline'):
        repair_case(store,lambda *a,**kw:[],'Incident',inc.id,by='operator',reason='repair test')
    assert store.case_projection_status()==before and store.case_projection_batch()==[]


def test_repair_receipt_survives_reopen_and_rejects_different_actor(tmp_path):
    path=tmp_path/'cases.db';store=Store(path);inc=incident();store.save({inc.id:inc},{},[])
    q=lambda *a,**kw:[];plan=inspect_case(store,q,'Incident',inc.id);rid=str(uuid.uuid4())
    result=repair_case(store,q,'Incident',inc.id,by='operator',reason='test',plan=plan,request_id=rid)
    store.db.close();store=Store(path)
    assert repair_case(store,q,'Incident',inc.id,by='operator',reason='test',plan=plan,request_id=rid)==result
    with pytest.raises(ValueError,match='different intent'):
        repair_case(store,q,'Incident',inc.id,by='different operator',reason='test',plan=plan,request_id=rid)


def test_modified_inspection_source_is_not_accepted_as_a_review(tmp_path):
    store=Store(tmp_path/'cases.db');inc=incident();store.save({inc.id:inc},{},[])
    q=lambda *a,**kw:[];plan=inspect_case(store,q,'Incident',inc.id);plan['source']['reason']='changed file'
    with pytest.raises(ValueError,match='integrity'):
        repair_case(store,q,'Incident',inc.id,by='operator',reason='test',plan=plan)


def test_new_dependent_judgment_invalidates_incident_repair_review(tmp_path):
    store=Store(tmp_path/'cases.db');inc=incident();store.save({inc.id:inc},{},[])
    q=lambda *a,**kw:[];plan=inspect_case(store,q,'Incident',inc.id)
    store.save({inc.id:inc},{'new':{'id':'new','origin':{'incident':inc.id}}},[])
    with pytest.raises(ValueError,match='dependent sources changed'):
        repair_case(store,q,'Incident',inc.id,by='operator',reason='test',plan=plan)
