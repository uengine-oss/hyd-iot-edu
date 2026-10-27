"""Disposable real PG: cached results are never visible as billable jobs."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from procsvc import instances, procdb, manual_cache
from procsvc.manual_approved_cache import ApprovedExtractions
from procsvc.manual_sources import ManualSources
from test_backend_pg_contracts import pg, DSN
from test_manual_approved_cache import ORIGINALS

pytestmark = pytest.mark.skipif(not DSN, reason='requires disposable fully migrated PostgreSQL')


def source_for(cache, archive, runtime, index):
    entry = list(cache.payload['documents'].values())[index]
    return archive.get(runtime.tenant_id, archive.save(runtime.tenant_id, entry['filename'],
                       (ORIGINALS/entry['filename']).read_bytes())['source_id'])


def test_postgres_cache_commit_visibility_duplicate_join_and_restart(pg, tmp_path, monkeypatch):
    _, runtime, _ = pg
    cache = ApprovedExtractions()
    archive = ManualSources(tmp_path/'sources.sqlite3')
    source = source_for(cache, archive, runtime, 0)
    original_insert = runtime.repo.insert_workitems
    observer = procdb.PgRepo(DSN)
    checked = []
    def insert(items):
        # Separate connection, while the creation transaction is still open.
        with ThreadPoolExecutor(max_workers=1) as pool:
            seen = pool.submit(observer.fetch_pending_task, 'cliagents', 'observer', 10, runtime.tenant_id).result()
        assert not seen
        assert all(i['status'] == 'SUBMITTED' for i in items)
        checked.append(True)
        return original_insert(items)
    monkeypatch.setattr(runtime.repo, 'insert_workitems', insert)
    with ThreadPoolExecutor(max_workers=6) as pool:
        runs = list(pool.map(lambda _:cache.start(runtime, source, str(uuid4()), {}), range(6)))
    assert len(checked) == 1 and len({r['instance'] for r in runs}) == 1
    assert not observer.fetch_pending_task('cliagents','observer',10,runtime.tenant_id)
    restored = instances.InstanceRuntime(procdb.PgRepo(DSN), runtime.defn, runtime.hooks, tenant_id=runtime.tenant_id)
    assert restored.poll_once() == 1
    result = manual_cache.result(restored, archive, source, runs[0]['instance'], None)
    assert result['status'] == 'DONE' and result['cache']['validated']
    assert result['preview']['extraction']['session_id'] is None


def test_postgres_failed_cache_creation_rolls_back_and_recovers(pg, tmp_path, monkeypatch):
    _, runtime, _ = pg
    cache = ApprovedExtractions()
    archive = ManualSources(tmp_path/'sources.sqlite3')
    source = source_for(cache, archive, runtime, -1)
    original_insert = runtime.repo.insert_workitems
    def fail(items):raise RuntimeError('write interrupted')
    monkeypatch.setattr(runtime.repo, 'insert_workitems', fail)
    with pytest.raises(RuntimeError,match='write interrupted'):
        cache.start(runtime,source,str(uuid4()),{})
    assert not runtime.repo.list_instances(tenant_id=runtime.tenant_id)
    assert not runtime.repo.fetch_pending_task('cliagents','observer',10,runtime.tenant_id)
    monkeypatch.setattr(runtime.repo,'insert_workitems',original_insert)
    run = cache.start(runtime,source,str(uuid4()),{})
    assert runtime.poll_once() == 1
    assert manual_cache.result(runtime,archive,source,run['instance'],None)['status'] == 'DONE'
