"""Atomic detector checkpoint, consumed offsets and alert outbox (at-least-once delivery).

offsets: per (topic, partition) the last processed offset and the newest record timestamp processed (ms) — the pair
hydcommon.kafka.replay_verdict needs to tell a replay from a recreated topic. A database from before max_ts existed gets
the column once, filled with the time of that upgrade (every record it covered was produced before it).
"""
import json
from pathlib import Path
import sqlite3
import time


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS offsets(topic TEXT, partition INTEGER, position INTEGER NOT NULL, max_ts INTEGER,
                                               PRIMARY KEY(topic,partition));
            CREATE TABLE IF NOT EXISTS outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL);
        ''')
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(offsets)')}
        if 'max_ts' not in columns:
            with self.db:
                self.db.execute('ALTER TABLE offsets ADD COLUMN max_ts INTEGER')
                self.db.execute('UPDATE offsets SET max_ts=? WHERE max_ts IS NULL', (int(time.time() * 1000),))

    def load(self):
        row = self.db.execute('SELECT body FROM checkpoint WHERE id=1').fetchone()
        return json.loads(row[0]) if row else None

    def position(self, topic, partition):
        """(next offset to process, newest processed timestamp ms) or (None, None) for a partition never processed."""
        row = self.db.execute('SELECT position, max_ts FROM offsets WHERE topic=? AND partition=?', (topic, partition)).fetchone()
        return (row[0] + 1, row[1]) if row else (None, None)

    def forget(self, topic, partition):
        with self.db:
            self.db.execute('DELETE FROM offsets WHERE topic=? AND partition=?', (topic, partition))

    def save(self, body, offsets=None, events=()):
        """One transaction: the checkpoint body, {(topic, partition): (last offset, max timestamp ms)} and new alerts."""
        serialized = json.dumps(body, allow_nan=False)
        messages = [json.dumps(event, allow_nan=False) for event in events]
        with self.db:
            self.db.execute('INSERT INTO checkpoint VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body', (serialized,))
            for (topic, partition), (offset, max_ts) in (offsets or {}).items():
                self.db.execute('INSERT INTO offsets VALUES(?,?,?,?) ON CONFLICT(topic,partition) DO UPDATE SET '
                                'position=excluded.position, max_ts=max(coalesce(offsets.max_ts, 0), excluded.max_ts)',
                                (topic, partition, offset, max_ts))
            self.db.executemany('INSERT INTO outbox(body) VALUES(?)', [(message,) for message in messages])

    def pending(self):
        return [(seq, json.loads(body)) for seq, body in self.db.execute('SELECT seq,body FROM outbox ORDER BY seq')]

    def delivered(self, seq):
        with self.db:
            self.db.execute('DELETE FROM outbox WHERE seq=?', (seq,))

    def close(self):
        self.db.close()
