"""Durable process snapshot. Uncertain in-flight execution needs review, never replay.

save() is called from the event-loop thread (legacy Incident path) and from executor threads
(instance runtime hooks), so the connection is shared across threads behind a lock.
"""
import json
import hashlib
import sqlite3
import threading
from dataclasses import asdict
from pathlib import Path

from hydcommon.timeutil import now_iso
from .machine import Incident
from .definition import TERMINAL
from .case_projection_store import CaseProjectionStore


class Store(CaseProjectionStore):
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
        self.db.execute('CREATE TABLE IF NOT EXISTS decision_reviews (id TEXT PRIMARY KEY, body TEXT NOT NULL, sha256 TEXT NOT NULL)')
        self._init_case_projection()

    def put_review(self, review):
        body = json.dumps(review,ensure_ascii=False,sort_keys=True,separators=(',', ':'),allow_nan=False)
        digest = hashlib.sha256(body.encode()).hexdigest()
        with self._lock, self.db:
            old = self.db.execute('SELECT body,sha256 FROM decision_reviews WHERE id=?',(review['id'],)).fetchone()
            if old:
                if old != (body,digest):
                    raise ValueError('검토본은 덮어쓸 수 없습니다')
                return
            self.db.execute('INSERT INTO decision_reviews VALUES (?,?,?)',(review['id'],body,digest))

    def get_review(self, review_id):
        with self._lock:
            row = self.db.execute('SELECT body,sha256 FROM decision_reviews WHERE id=?',(review_id,)).fetchone()
        if row is None:
            raise ValueError('저장된 검토본이 없습니다. 다시 예측을 확인하세요')
        body, digest = row
        if hashlib.sha256(body.encode()).hexdigest() != digest:
            raise ValueError('검토본 무결성을 확인할 수 없습니다')
        return json.loads(body)

    def save(self, incidents, book, audit):
        with self._lock, self.db:
            # Capture and write in the same serialization order. Alarm handlers
            # may add incidents on other executor threads while asdict walks an
            # existing incident, so freeze collection membership first.
            members = list(incidents.values())
            body = json.dumps({"incidents": [asdict(i) for i in members],
                               "book": dict(book), "audit": list(audit)}, ensure_ascii=False)
            self.db.execute("INSERT OR REPLACE INTO snapshot VALUES (1, ?)", (body,))
            self._enqueue_case_snapshot(json.loads(body))

    def restore(self):
        with self._lock:
            row = self.db.execute("SELECT body FROM snapshot WHERE id=1").fetchone()
        data = json.loads(row[0]) if row else {}
        incidents = {v["id"]: Incident(**v) for v in data.get("incidents", [])}
        for inc in incidents.values():
            # Recovery was observed and the exact CMMS request was durably saved.
            # Replaying that idempotent request does not replay a PLC command.
            cmms_pending = inc.state == 'RESOLVED' and inc.work_order_request is not None
            if inc.state not in TERMINAL | {"AWAITING_APPROVAL"} and not cmms_pending:
                inc.state, inc.reason = "ESCALATED", "PROCESS_RESTART_REVIEW"
                inc.history.append({"state": inc.state, "t": now_iso(), "note": inc.reason})
        book = data.get("book", {})
        for d in book.values():
            if d["state"] == "APPROVED" and not d.get('process_approval_id'):
                d.update(state="PARTIAL", reason="PROCESS_RESTART_REVIEW")
                d["history"].append({"state": "PARTIAL", "t": now_iso(), "reason": "PROCESS_RESTART_REVIEW"})
        return incidents, book, data.get("audit", [])
