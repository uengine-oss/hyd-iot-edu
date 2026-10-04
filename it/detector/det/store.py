"""Atomic detector checkpoint, consumed offsets and alert outbox (at-least-once delivery)."""
import json
from pathlib import Path
import sqlite3


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS offsets(topic TEXT, partition INTEGER, position INTEGER NOT NULL,
                                               PRIMARY KEY(topic,partition));
            CREATE TABLE IF NOT EXISTS outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL);
        ''')

    def load(self):
        row = self.db.execute('SELECT body FROM checkpoint WHERE id=1').fetchone()
        return json.loads(row[0]) if row else None

    def seen(self, topic, partition, offset):
        row = self.db.execute('SELECT position FROM offsets WHERE topic=? AND partition=?',(topic,partition)).fetchone()
        return row is not None and offset <= row[0]

    def save(self, body, record=None, events=()):
        serialized = json.dumps(body, allow_nan=False)
        messages = [json.dumps(event, allow_nan=False) for event in events]
        with self.db:
            self.db.execute('INSERT INTO checkpoint VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',(serialized,))
            if record:
                self.db.execute('INSERT INTO offsets VALUES(?,?,?) ON CONFLICT(topic,partition) DO UPDATE SET position=excluded.position',record)
            self.db.executemany('INSERT INTO outbox(body) VALUES(?)',[(message,) for message in messages])

    def pending(self):
        return [(seq,json.loads(body)) for seq,body in self.db.execute('SELECT seq,body FROM outbox ORDER BY seq')]

    def delivered(self, seq):
        with self.db:self.db.execute('DELETE FROM outbox WHERE seq=?',(seq,))

    def close(self):
        self.db.close()
