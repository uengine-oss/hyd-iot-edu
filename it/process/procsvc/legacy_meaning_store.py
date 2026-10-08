"""A9: immutable record of each person's review of one candidate run (who decided what, before → after).

A review is never edited; deciding again makes a new review, so two reviews of the same candidates can be compared
(TODO A9 "같은 옛 DB를 넣고 후보를 승인·거부해 반영 결과 비교"). Same SQLite-next-to-the-process-state pattern as manual_sources.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class LegacyMeaningStore:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ':memory:':
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(':memory:', check_same_thread=False) if self.path == ':memory:' else None
        with self._db() as db:
            db.execute('create table if not exists legacy_meaning_reviews(id text primary key, tenant text not null, '
                       'instance text not null, workitem text not null, sha256 text not null, filename text not null, '
                       'by text not null, review text not null, created_at text not null)')
            db.execute('create index if not exists legacy_meaning_reviews_instance on legacy_meaning_reviews(tenant, instance)')

    @contextmanager
    def _db(self):
        db = self._memory or sqlite3.connect(self.path)
        try:
            yield db
            db.commit()
        finally:
            if self._memory is None:
                db.close()

    def add(self, tenant, instance, workitem, source, review) -> dict:
        row = {'id': 'review:' + uuid4().hex, 'tenant': tenant, 'instance': instance, 'workitem': workitem,
               'sha256': source['sha256'], 'filename': source['filename'], 'by': review['by'],
               'review': review, 'created_at': datetime.now(timezone.utc).isoformat()}
        with self._db() as db:
            db.execute('insert into legacy_meaning_reviews values (?,?,?,?,?,?,?,?,?)',
                       (row['id'], tenant, instance, workitem, row['sha256'], row['filename'], row['by'],
                        json.dumps(review, ensure_ascii=False), row['created_at']))
        return row

    def _row(self, r):
        keys = ('id', 'tenant', 'instance', 'workitem', 'sha256', 'filename', 'by', 'review', 'created_at')
        out = dict(zip(keys, r))
        out['review'] = json.loads(out['review'])
        return out

    def get(self, tenant, review_id) -> dict:
        with self._db() as db:
            r = db.execute('select * from legacy_meaning_reviews where tenant=? and id=?', (tenant, review_id)).fetchone()
        if r is None:
            raise KeyError(review_id)
        return self._row(r)

    def list(self, tenant, instance) -> list[dict]:
        with self._db() as db:
            rows = db.execute('select * from legacy_meaning_reviews where tenant=? and instance=? order by created_at desc',
                              (tenant, instance)).fetchall()
        return [self._row(r) for r in rows]
