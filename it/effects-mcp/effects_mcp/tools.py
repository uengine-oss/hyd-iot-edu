"""hyd-effects 쓰기 도구의 본체(FastMCP 없이 시험할 수 있게 분리). 사람 승인 뒤 process 의 'mcp:call' 부품만 부른다.

  send_mail           SMTP 로 메일 한 통. 수업 기본은 Supabase 로컬의 Inbucket(SMTP 54325, 웹 54324) — 실제 발송 없음.

일정 · 기록 같은 업무 쓰기는 여기 두지 않는다 — 기존 enterprise-sim 거래(작업지시 · 구매요청 등, /api/exec)를 process 가 직접 쓴다
(2026-10-09 지시: 이미 있는 CMMS · ERP 부품을 다시 만들지 않는다).

멱등: idempotency_key 를 받는다(process 가 '처리 건:작업' 으로 넣는다). 같은 키의 두 번째 호출은 첫 결과를 그대로 돌려준다
(replayed=true) — 재시도해도 메일이 두 번 가지 않는다. 키 기록은 SQLite(EFFECTS_STATE_PATH)에 남는다.
결과는 {"result": "ok" | "error", "document" | "message"} 봉투(enterprise-mcp 와 같은 모양).
"""
from __future__ import annotations

import json
import os
import smtplib
import sqlite3
import threading
import urllib.error
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

SMTP_HOST = os.getenv("SMTP_HOST", "host.docker.internal")
SMTP_PORT = int(os.getenv("SMTP_PORT", "54325"))
MAIL_FROM = os.getenv("EFFECTS_MAIL_FROM", "hyd-process@hyd.local")
MAX_RECIPIENTS = 20


def ok(document) -> dict:
    return {"result": "ok", "document": document}


def error(kind: str, message: str) -> dict:
    return {"result": "error", "error_kind": kind, "message": message}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class Ledger:
    """idempotency_key → 첫 결과. 프로세스가 재시작해도 남는다(경로가 없으면 메모리)."""

    def __init__(self, path: str | None = None):
        self._lock = threading.Lock()
        self._mem: dict[str, dict] = {}
        self._db = None
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(path, check_same_thread=False)
            self._db.execute("CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, tool TEXT NOT NULL, body TEXT NOT NULL)")

    def get(self, key: str) -> dict | None:
        with self._lock:
            if self._db is not None:
                row = self._db.execute("SELECT body FROM calls WHERE key=?", (key,)).fetchone()
                return json.loads(row[0]) if row else None
            return self._mem.get(key)

    def put(self, key: str, tool: str, body: dict) -> None:
        with self._lock:
            if self._db is not None:
                with self._db:
                    self._db.execute("INSERT OR IGNORE INTO calls VALUES (?,?,?)", (key, tool, json.dumps(body, ensure_ascii=False)))
            else:
                self._mem.setdefault(key, body)


def _recipients(to) -> list[str]:
    items = [to] if isinstance(to, str) else list(to or [])
    out = []
    for item in items:
        for addr in str(item).replace(";", ",").split(","):
            addr = addr.strip()
            if addr:
                if "@" not in addr or any(c in addr for c in "\r\n<> "):
                    raise ValueError(f"받는 주소 '{addr}' 가 올바르지 않습니다")
                out.append(addr)
    if not out:
        raise ValueError("받는 사람(to)이 없습니다")
    if len(out) > MAX_RECIPIENTS:
        raise ValueError(f"받는 사람은 {MAX_RECIPIENTS}명까지입니다")
    return out


class EffectTools:
    def __init__(self, ledger: Ledger, smtp_factory=None):
        self.ledger = ledger
        self._smtp = smtp_factory or (lambda: smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10))

    def _once(self, tool: str, key: str | None, work) -> dict:
        if key:
            prior = self.ledger.get(key)
            if prior is not None:
                if prior.get("tool") != tool:
                    return error("INVALID", f"idempotency_key {key} 는 이미 다른 도구({prior.get('tool')})에 쓰였습니다")
                return ok(dict(prior["document"], replayed=True))
        try:
            doc = work()
        except ValueError as e:
            return error("INVALID", str(e))
        except (OSError, smtplib.SMTPException, urllib.error.URLError, RuntimeError) as e:
            return error("UNKNOWN", f"{type(e).__name__}: {str(e)[:200]}")
        if key:
            self.ledger.put(key, tool, {"tool": tool, "document": doc})
        return ok(dict(doc, replayed=False))

    def send_mail(self, to, subject: str, body: str, cc=None, idempotency_key: str | None = None) -> dict:
        def work():
            rcpt = _recipients(to)
            copy = _recipients(cc) if cc else []
            if not str(subject or "").strip():
                raise ValueError("제목(subject)이 비었습니다")
            msg = EmailMessage()
            msg["From"] = formataddr(("HYD 프로세스", MAIL_FROM))
            msg["To"] = ", ".join(rcpt)
            if copy:
                msg["Cc"] = ", ".join(copy)
            msg["Subject"] = str(subject).strip()
            msg["Message-ID"] = make_msgid(domain="hyd.local")
            if idempotency_key:
                msg["X-HYD-Idempotency-Key"] = idempotency_key
            msg.set_content(str(body or ""))
            with self._smtp() as smtp:
                smtp.send_message(msg)
            return {"message_id": msg["Message-ID"], "to": rcpt, "cc": copy, "subject": msg["Subject"], "sent_at": _now(),
                    "smtp": f"{SMTP_HOST}:{SMTP_PORT}"}
        return self._once("send_mail", idempotency_key, work)
