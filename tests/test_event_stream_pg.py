import os
from uuid import uuid4
from urllib.parse import urlsplit

import psycopg
import pytest
from procsvc.procdb import PgRepo


def test_publication_follows_commit_order_not_event_timestamp_or_insert_order():
    dsn = os.getenv('HYD_SYSTEM_PROGRESS_PG_DSN')
    if not dsn:
        pytest.skip('requires disposable PostgreSQL')
    target = urlsplit(dsn)
    assert target.hostname == '127.0.0.1' and target.port == 55757 and target.path == '/hyd_system_progress_test'
    repo = PgRepo(dsn)
    late, early = str(uuid4()), str(uuid4())
    try:
        with psycopg.connect(dsn) as slow:
            slow.execute("insert into events(id,job_id,event_type,data,timestamp) values(%s,'stream-test','task_working','{}','2026-10-26T00:00:00Z')", (late,))
            with psycopg.connect(dsn) as fast:
                fast.execute("insert into events(id,job_id,event_type,data,timestamp) values(%s,'stream-test','task_working','{}','2026-10-26T00:01:00Z')", (early,))
            published = repo.list_stream_events(None, 300)
            assert late not in {e['id'] for e in published}
            cursor = next(e['stream_cursor'] for e in published if e['id'] == early)
            # slow transaction commits only on leaving this block.
        after = repo.list_stream_events(cursor, 300)
        assert [e['id'] for e in after] == [early, late]
        assert after[0]['stream_cursor'] < after[1]['stream_cursor']
        assert repo.list_stream_events(after[1]['stream_cursor'], 300)[0]['id'] == late
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute('delete from events where id=any(%s)', ([late, early],))
