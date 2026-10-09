"""A091 — the live event stream: every recorded event reaches the client once, in order, across polls; batches that share a
timestamp are neither lost nor repeated; the stream ends when the client disconnects."""
import asyncio
import json

from procsvc import instance_mode, procdb


def _frames(chunks):
    out = []
    for c in chunks:
        if c.startswith(':'):
            continue
        out.append((c.split('\n')[0].replace('event: ', '') if c.startswith('event:') else 'data', json.loads(c.split('data: ', 1)[1].strip())))
    return out


async def _collect(repo, since, script, interval=0.001):
    """script: list of callables run between polls (None = just poll); returns frames and disconnects after the script."""
    chunks, step = [], {'i': 0}
    async def disconnected():
        if step['i'] < len(script):
            fn = script[step['i']]; step['i'] += 1
            if fn: fn()
            return False
        return True
    async for chunk in instance_mode.event_stream(repo, since, disconnected, interval=interval, keepalive_s=0.002):
        chunks.append(chunk)
    return _frames(chunks)


def test_history_then_new_events_once_each_in_order():
    repo = procdb.MemoryRepo()
    repo.record_events([{'id': 'e1', 'job_id': 'j', 'event_type': 'task_started', 'data': {}, 'timestamp': '2026-10-07T01:00:00+00:00'}])
    def more():
        repo.record_events([{'id': 'e2', 'job_id': 'j', 'event_type': 'tool_usage_started', 'data': {'tool': 'x'}, 'timestamp': '2026-10-07T01:00:01+00:00'},
                            {'id': 'e3', 'job_id': 'j', 'event_type': 'tool_usage_finished', 'data': {'tool': 'x'}, 'timestamp': '2026-10-07T01:00:01+00:00'}])  # same timestamp
    def later():
        repo.record_events([{'id': 'e4', 'job_id': 'j', 'event_type': 'task_completed', 'data': {}, 'timestamp': '2026-10-07T01:00:01+00:00'}])          # still that timestamp
    frames = asyncio.run(_collect(repo, None, [None, more, None, later, None, None]))
    assert [(k, f['id']) for k, f in frames] == [('history', 'e1'), ('data', 'e2'), ('data', 'e3'), ('data', 'e4')]


def test_cursor_resumes_without_replaying_older_events():
    repo = procdb.MemoryRepo()
    for i in range(3):
        repo.record_events([{'id': f'o{i}', 'job_id': 'j', 'event_type': 'task_working', 'data': {}, 'timestamp': f'2026-10-07T00:00:0{i}+00:00'}])
    def new():
        repo.record_events([{'id': 'n1', 'job_id': 'j', 'event_type': 'task_completed', 'data': {}, 'timestamp': '2026-10-07T00:00:05+00:00'}])
    frames = asyncio.run(_collect(repo, '2026-10-07T00:00:02+00:00', [None, new, None]))
    assert [f['id'] for _, f in frames] == ['o2', 'n1']           # the cursor event itself is sent (>=), nothing older


def test_memory_repo_since_filter_is_inclusive_and_ordered():
    repo = procdb.MemoryRepo()
    repo.record_events([{'id': 'b', 'job_id': 'j', 'event_type': 'error', 'data': {}, 'timestamp': '2026-10-07T00:00:01+00:00'},
                        {'id': 'a', 'job_id': 'j', 'event_type': 'error', 'data': {}, 'timestamp': '2026-10-07T00:00:00+00:00'}])
    assert [e['id'] for e in repo.list_events_since('2026-10-07T00:00:00+00:00')] == ['a', 'b']
    assert [e['id'] for e in repo.list_events_since('2026-10-07T00:00:01+00:00')] == ['b']


def _raw(repo, since, script, interval=0.001):
    chunks, step = [], {'i': 0}
    async def disconnected():
        if step['i'] < len(script):
            fn = script[step['i']]; step['i'] += 1
            if fn: fn()
            return False
        return True
    async def run():
        async for chunk in instance_mode.event_stream(repo, since, disconnected, interval=interval, keepalive_s=0.002):
            chunks.append(chunk)
    asyncio.run(run())
    return [c for c in chunks if not c.startswith(':')]


def test_a161_every_frame_carries_its_timestamp_as_the_sse_id():
    """A161-U1: the browser keeps the last id and sends it back as Last-Event-ID when it reconnects by itself."""
    repo = procdb.MemoryRepo()
    repo.record_events([{'id': 'h1', 'job_id': 'j', 'event_type': 'task_started', 'data': {}, 'timestamp': '2026-10-09T01:00:00+00:00'}])
    def more():
        repo.record_events([{'id': 'n1', 'job_id': 'j', 'event_type': 'tool_usage_started', 'data': {}, 'timestamp': '2026-10-09T01:00:02+00:00'}])
    raw = _raw(repo, None, [None, more, None])
    assert raw[0].startswith('event: history\nid: 2026-10-09T01:00:00+00:00\ndata: ')
    assert raw[1].startswith('id: 2026-10-09T01:00:02+00:00\ndata: ')


def test_a161_reconnect_from_last_id_delivers_what_was_written_while_disconnected():
    """Events recorded while the connection was down arrive after the reconnect (resume at the last id, >=); the client
    drops the one it already had by id. Without the id the stream replays only the last 60 rows and a burst is lost."""
    repo = procdb.MemoryRepo()
    repo.record_events([{'id': 'seen', 'job_id': 'j', 'event_type': 'task_started', 'data': {}, 'timestamp': '2026-10-09T01:00:00+00:00'}])
    for i in range(80):                                      # a burst bigger than the 60-row history, written while offline
        repo.record_events([{'id': f'b{i:02d}', 'job_id': 'j', 'event_type': 'task_working', 'data': {}, 'timestamp': f'2026-10-09T01:00:{1 + i // 60:02d}.{i:03d}000+00:00'}])
    frames = asyncio.run(_collect(repo, '2026-10-09T01:00:00+00:00', [None]))
    ids = [f['id'] for _, f in frames]
    assert ids[0] == 'seen' and all(f'b{i:02d}' in ids for i in range(80)) and len(ids) == len(set(ids))


def test_a161_memory_repo_list_events_keeps_the_newest_rows():
    """The instance view reads the newest rows (a long run must not freeze the screen on its oldest 500 events)."""
    repo = procdb.MemoryRepo()
    for i in range(10):
        repo.record_events([{'id': f'e{i}', 'job_id': 'j', 'proc_inst_id': 'p', 'event_type': 'task_working', 'data': {}, 'timestamp': f'2026-10-09T01:00:0{i}+00:00'}])
    assert [e['id'] for e in repo.list_events(proc_inst_id='p', limit=3)] == ['e7', 'e8', 'e9']
