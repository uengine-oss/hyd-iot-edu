"""A131 — process memory: the diagnostics endpoint, the SSE subscriber counter and the persist() path that no longer re-parses
the whole snapshot. Background: the process container was OOM-killed twice on 2026-10-07 (.evidence/a131)."""
import asyncio
import json

import pytest

from procsvc import instance_mode, memdebug, procdb
from procsvc.machine import Incident
from procsvc.store import Store


# ---------------------------------------------------------------- persist(): same outbox content without the json.loads round trip
def _incident(i):
    inc = Incident.from_card(f'a131-{i}', {'alert': {'alertId': f'alert-{i}', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'},
                                           'topCause': 'cause:x', 'tags': ('a', 'b')})          # a tuple: JSON turns it into a list
    return inc


def _outbox(store):
    return store.db.execute('select kind,source_id,body from case_projection_outbox order by id').fetchall()


def _sources(store):
    return store.db.execute('select kind,source_id,digest from case_projection_source order by kind,source_id').fetchall()


def test_save_enqueues_identical_outbox_without_reparsing_snapshot(tmp_path, monkeypatch):
    incidents = {inc.id: inc for inc in (_incident(1), _incident(2))}
    book = {'dec-1': {'id': 'dec-1', 'schema': 'v2', 'state': 'APPROVED', 'chosen': 'skill:x', 'created': '2026-10-07T00:00:00+00:00',
                      'history': [{'state': 'APPROVED', 't': '2026-10-07T00:00:01+00:00'}], 'origin': {'incident': 'a131-1'}, 'nested': {1: 'int key'}}}
    audit = [{'event': 'X'}]
    # reference: the old path (json.loads of the saved body)
    ref = Store(tmp_path / 'ref.db')
    with ref._lock, ref.db:
        body = json.dumps({'incidents': [__import__('dataclasses').asdict(i) for i in incidents.values()], 'book': dict(book), 'audit': audit}, ensure_ascii=False)
        ref.db.execute('INSERT OR REPLACE INTO snapshot VALUES (1, ?)', (body,))
        ref._enqueue_case_snapshot(json.loads(body))
    # new path
    loads_calls = []
    real_loads = json.loads
    monkeypatch.setattr('procsvc.store.json.loads', lambda s, *a, **k: (loads_calls.append(len(s)), real_loads(s, *a, **k))[1])
    new = Store(tmp_path / 'new.db')
    new.save(incidents, book, audit)
    assert not loads_calls, 'persist() must not re-parse the snapshot JSON'
    assert _outbox(new) == _outbox(ref)
    assert _sources(new) == _sources(ref)
    assert new.db.execute('select body from snapshot where id=1').fetchone()[0] == body
    # a second identical save enqueues nothing new (digests unchanged)
    new.save(incidents, book, audit)
    assert len(_outbox(new)) == len(_outbox(ref))


def test_save_falls_back_when_keys_cannot_be_sorted(tmp_path):
    """A dict mixing str and non-str keys makes sort_keys raise; the JSON round trip (all-str keys) must then still work."""
    store = Store(tmp_path / 'mixed.db')
    book = {'dec-m': {'id': 'dec-m', 'schema': 'v2', 'state': 'APPROVED', 'chosen': 'skill:x', 'created': '2026-10-07T00:00:00+00:00',
                      'history': [], 'origin': {}, 'mixed': {1: 'a', 'b': 2}}}
    store.save({}, book, [])
    rows = _outbox(store)
    assert [r[1] for r in rows] == ['dec-m'] and json.loads(rows[0][2])['mixed'] == {'1': 'a', 'b': 2}


# ---------------------------------------------------------------- /api/events/stream subscriber count returns to zero
def test_stream_clients_counter_returns_to_zero_after_disconnect():
    repo = procdb.MemoryRepo()
    seen = []

    async def run():
        calls = {'n': 0}
        async def disconnected():
            calls['n'] += 1
            return calls['n'] > 2
        async for _ in instance_mode.event_stream(repo, None, disconnected, interval=0.001, keepalive_s=0.001):
            seen.append(instance_mode.stream_clients)
    assert instance_mode.stream_clients == 0
    asyncio.run(run())
    assert instance_mode.stream_clients == 0
    assert seen and all(n == 1 for n in seen)


def test_stream_clients_counter_decrements_when_consumer_abandons_generator():
    repo = procdb.MemoryRepo()
    repo.record_events([{'id': 'e1', 'job_id': 'j', 'event_type': 'task_started', 'data': {}, 'timestamp': '2026-10-07T01:00:00+00:00'}])

    async def run():
        async def never():
            return False
        gen = instance_mode.event_stream(repo, None, never, interval=0.001, keepalive_s=0.001)
        await gen.__anext__()
        assert instance_mode.stream_clients == 1
        await gen.aclose()                      # what Starlette does when the client drops the connection
    asyncio.run(run())
    assert instance_mode.stream_clients == 0


# ---------------------------------------------------------------- /debug/memory
def test_memdebug_snapshot_reports_rss_containers_and_tracemalloc():
    import tracemalloc
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start(1)
    try:
        snap = memdebug.snapshot({'incidents': lambda: 3, 'broken': lambda: 1 / 0})
    finally:
        if not was_tracing:
            tracemalloc.stop()
    assert snap['containers']['incidents'] == 3 and snap['containers']['broken'].startswith('error:')
    assert set(snap['objects']['tracked']) >= {'psycopg.Connection', 'neo4j.Driver', 'sqlite3.Connection', 'threading.Lock'}
    assert snap['tracemalloc']['tracing'] is True and len(snap['tracemalloc']['top_by_line']) <= memdebug.TOP
    assert all({'size_kb', 'count', 'where'} <= set(r) for r in snap['tracemalloc']['top_by_traceback'])
    assert snap['threads'] >= 1 and 'gc_objects' in snap['objects']
    cheap = memdebug.snapshot({}, trace=False)
    assert cheap['tracemalloc'].get('skipped') is True


def test_memdebug_is_off_unless_flag_set(monkeypatch):
    monkeypatch.delenv('PROCESS_MEMDEBUG', raising=False)
    assert memdebug.enabled() is False
    monkeypatch.setenv('PROCESS_MEMDEBUG', '1')
    assert memdebug.enabled() is True


def test_memdebug_route_mounts_only_with_flag():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    memdebug.register(app, {'n': lambda: 1})
    with TestClient(app) as client:
        body = client.get('/debug/memory?trace=0').json()
    assert body['containers'] == {'n': 1} and body['tracemalloc'].get('skipped') is True
