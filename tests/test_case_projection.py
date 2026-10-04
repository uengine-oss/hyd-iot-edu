from procsvc.machine import Incident
from procsvc.store import Store
from procsvc.case_projection import CaseProjector
import json
import sqlite3
import pytest


def incident():
    return Incident.from_card('case-outbox-test', {'alert': {'alertId':'test-alert','asset':'HYD-01','pattern':'COOLER_DEGRADATION'}})


def receipt(*args,**params):
    return [dict(projection_key=params['key'],projection_revision=params['revision'],projection_hash=params['payload_hash'])]


def test_source_commit_also_contains_pending_graph_work(tmp_path):
    store=Store(tmp_path/'state.db');inc=incident();store.save({inc.id:inc},{},[])
    tables={r[0] for r in store.db.execute("select name from sqlite_master where type='table'")}
    assert 'case_projection_outbox' in tables
    assert store.db.execute('select count(*) from case_projection_outbox where processed_at is null').fetchone()[0]==1


def test_case_graph_work_survives_new_store(tmp_path):
    path=tmp_path/'state.db';store=Store(path);inc=incident();store.save({inc.id:inc},{},[]);store.db.close()
    restored=Store(path)
    assert hasattr(restored,'case_projection_batch'), 'no durable graph recovery interface'
    assert restored.case_projection_batch()[0]['source_id']==inc.id


def test_queue_failure_rolls_back_source_commit(tmp_path):
    store=Store(tmp_path/'state.db');inc=incident();store.save({inc.id:inc},{},[])
    before=store.db.execute('select body from snapshot').fetchone()[0]
    store.db.execute("create trigger fail_case_job before insert on case_projection_outbox begin select raise(abort,'planned outbox failure'); end")
    inc.reason='changed'
    with pytest.raises(sqlite3.IntegrityError,match='planned outbox'):
        store.save({inc.id:inc},{},[])
    assert store.db.execute('select body from snapshot').fetchone()[0]==before
    assert store.case_projection_status()['pending']==1


def test_audit_only_save_does_not_duplicate_graph_jobs(tmp_path):
    store=Store(tmp_path/'state.db');inc=incident();store.save({inc.id:inc},{},[])
    store.save({inc.id:inc},{},[{'event':'unrelated audit'}])
    assert store.case_projection_status()['pending']==1


def test_graph_error_persisted_and_retried_after_reopen(tmp_path):
    path=tmp_path/'state.db';store=Store(path);inc=incident();store.save({inc.id:inc},{},[])
    def offline(*a,**kw):raise ConnectionError('offline')
    assert CaseProjector(store,offline).drain()==0
    assert 'offline' in store.case_projection_status()['items'][0]['last_error']
    store.db.close();store=Store(path)
    store.db.execute('update case_projection_outbox set retry_at=0');store.db.commit()
    assert CaseProjector(store,receipt).drain()==1
    assert store.case_projection_status()['pending']==0


def test_change_during_graph_write_remains_pending(tmp_path):
    store=Store(tmp_path/'state.db');inc=incident();store.save({inc.id:inc},{},[])
    def write(*a,**kw):
        inc.reason='concurrent source change';store.save({inc.id:inc},{},[])
        return receipt(**kw)
    assert CaseProjector(store,write).drain()==1
    assert store.case_projection_status()['pending']==1
    assert store.case_projection_batch()[0]['body']['reason']=='concurrent source change'


def test_dependency_failure_keeps_job_after_graph_write(tmp_path):
    store=Store(tmp_path/'state.db');inc=incident()
    d={'id':'D','created':inc.created,'state':'APPROVED','chosen':'skill:x','origin':{'incident':inc.id}}
    store.save({}, {'D':d}, [])
    worker=CaseProjector(store,lambda *a,**kw:[{'dependency_pending':True}])
    assert worker.drain()==0 and store.case_projection_status()['pending']==1


def test_incident_removal_enqueues_case_relationship_repair(tmp_path):
    store=Store(tmp_path/'state.db');inc=incident()
    d={'id':'D','created':inc.created,'state':'APPROVED','chosen':'skill:x','origin':{'incident':inc.id}}
    store.save({inc.id:inc},{'D':d},[]);CaseProjector(store,receipt).drain()
    store.save({}, {'D':d}, [])
    jobs=store.case_projection_batch()
    assert len(jobs)==2
    assert next(j for j in jobs if j['kind']=='Incident')['body'] is None
    assert next(j for j in jobs if j['kind']=='DecisionCase')['body']==d


def test_pg_notification_failure_keeps_durable_case_job(tmp_path):
    store=Store(tmp_path/'state.db');inc=incident();store.save({inc.id:inc},{},[])
    def unavailable(_):raise ConnectionError('PG unavailable')
    assert CaseProjector(store,receipt,unavailable).drain()==0
    assert 'PG unavailable' in store.case_projection_status()['items'][0]['last_error']
