import sqlite3
import pytest
from procsvc.knowledge_projection import KnowledgeReconciler
from procsvc.store import Store
from procsvc.procdb import MemoryRepo
from test_case_projection import incident


def setup(tmp_path):
    store=Store(tmp_path/'cases.db');inc=incident();store.save({inc.id:inc},{},[])
    for job in store.case_projection_batch():store.finish_case_projection(job)
    repo=MemoryRepo();repo.instances['one']={'proc_inst_id':'one','tenant_id':'hyd'}
    return store,repo


def test_graph_query_failure_does_not_advance_checkpoint_or_enqueue(tmp_path):
    store,repo=setup(tmp_path)
    def unavailable(q):raise ConnectionError('offline')
    scanner=KnowledgeReconciler(store,unavailable,'hyd',repo)
    assert scanner.scan() is False
    assert 'offline' in scanner.status()['last_error']
    assert scanner.status()['queued'] is None and not repo.projection_jobs


def test_pg_failure_cannot_ack_sqlite_knowledge_scan(tmp_path):
    store,repo=setup(tmp_path)
    def fail(tenant):raise ConnectionError('PG down')
    repo.enqueue_knowledge_projections=fail
    scanner=KnowledgeReconciler(store,lambda q:[],'hyd',repo)
    assert not scanner.scan()
    assert store.case_projection_status()['pending']==0
    assert scanner.status()['queued'] is None


@pytest.mark.parametrize('table',['case_projection_outbox','knowledge_projection_checkpoint'])
def test_sqlite_failure_rolls_back_case_jobs_and_checkpoint_then_recovers(tmp_path,table):
    store,repo=setup(tmp_path)
    store.db.execute(f"create trigger fail_write before insert on {table} begin select raise(abort,'planned write failure'); end")
    scan=KnowledgeReconciler(store,lambda q:[],'hyd',repo)
    assert not scan.scan() and repo.pending_projections('hyd')==['one']
    assert store.case_projection_status()['pending']==0 and scan.status()['queued'] is None
    store.db.execute('drop trigger fail_write');store.db.close()
    restored=Store(tmp_path/'cases.db');scan=KnowledgeReconciler(restored,lambda q:[],'hyd',repo)
    assert scan.scan()
    assert restored.case_projection_status()['pending']==1
    assert len(repo.projection_jobs)==2  # PG delivery repeats safely, never lost.
    assert not scan.scan()


def test_requeue_uses_latest_source_and_preserves_deleted_tombstone(tmp_path):
    store,repo=setup(tmp_path)
    store.save({}, {},[])
    for job in store.case_projection_batch():store.finish_case_projection(job)
    before=store.db.execute('select body from snapshot').fetchone()[0]
    scan=KnowledgeReconciler(store,lambda q:[],'hyd',repo);assert scan.scan()
    assert all(j['body'] is None for j in store.case_projection_batch())
    assert store.db.execute('select body from snapshot').fetchone()[0]==before


def test_mode_change_cannot_skip_instance_queue_with_legacy_checkpoint(tmp_path):
    store,repo=setup(tmp_path)
    assert KnowledgeReconciler(store,lambda q:[],'hyd').scan()
    assert KnowledgeReconciler(store,lambda q:[],'hyd',repo).scan()
    assert repo.pending_projections('hyd')==['one']


def test_memory_requeues_known_deleted_identity_and_isolates_tenant(tmp_path):
    _,repo=setup(tmp_path)
    repo._enqueue_projection({'proc_inst_id':'deleted','tenant_id':'hyd'})
    repo.instances['other']={'proc_inst_id':'other','tenant_id':'other'}
    repo.enqueue_knowledge_projections('hyd')
    assert set(repo.pending_projections('hyd'))=={'one','deleted'}
    assert not repo.pending_projections('other')
