"""Durable process snapshot. Uncertain in-flight execution needs review, never replay."""
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from hydcommon.timeutil import now_iso
from .machine import Incident
from .definition import TERMINAL


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")

    def save(self, incidents, book, audit):
        body = json.dumps({"incidents": [asdict(i) for i in incidents.values()], "book": book, "audit": audit}, ensure_ascii=False)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO snapshot VALUES (1, ?)", (body,))

    def restore(self):
        row = self.db.execute("SELECT body FROM snapshot WHERE id=1").fetchone()
        data = json.loads(row[0]) if row else {}
        incidents = {v["id"]: Incident(**v) for v in data.get("incidents", [])}
        for inc in incidents.values():
            if inc.state not in TERMINAL | {"AWAITING_APPROVAL"}:
                inc.state, inc.reason = "ESCALATED", "PROCESS_RESTART_REVIEW"
                inc.history.append({"state": inc.state, "t": now_iso(), "note": inc.reason})
        book = data.get("book", {})
        for d in book.values():
            if d["state"] == "APPROVED":
                d.update(state="PARTIAL", reason="PROCESS_RESTART_REVIEW")
                d["history"].append({"state": "PARTIAL", "t": now_iso(), "reason": "PROCESS_RESTART_REVIEW"})
        return incidents, book, data.get("audit", [])
