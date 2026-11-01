"""hyd-effects 쓰기 도구의 본체(FastMCP 없이 시험할 수 있게 분리). 사람 승인 뒤 process 의 'mcp:call' 부품만 부른다.

  send_mail           SMTP 로 메일 한 통. 수업 기본은 Supabase 로컬의 Inbucket(SMTP 54325, 웹 54324) — 실제 발송 없음.

일정 · 기록 같은 업무 쓰기는 여기 두지 않는다 — 기존 enterprise-sim 거래(작업지시 · 구매요청 등, /api/exec)를 process 가 직접 쓴다
(2026-10-09 지시: 이미 있는 CMMS · ERP 부품을 다시 만들지 않는다).

멱등: idempotency_key 를 받는다(process 가 '처리 건:작업' 으로 넣는다). 같은 키 · 같은 내용의 두 번째 호출은 첫 결과를 그대로 돌려준다
(replayed=true) — 재시도해도 메일이 두 번 가지 않는다. 같은 키에 다른 내용이면 거절한다(업무 DB 거래의 멱등 충돌과 같은 규칙). 확인 · 발송 ·
기록은 한 번에 하나씩 한다 — 같은 키가 동시에 두 번 와도 한 통이다. 키 기록은 SQLite(EFFECTS_STATE_PATH)에 남는다.
받는 주소는 수업 도메인(@hyd.local)만 받는다 — SMTP 주소 설정이 바뀌어도 수업 밖으로 메일이 나가지 않게(2026-10-30 검진 G2-17).
결과는 {"result": "ok" | "error", "document" | "message"} 봉투(enterprise-mcp 와 같은 모양).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
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
CLASS_DOMAIN = "hyd.local"                     # 수업 메일 주소의 도메인(seed 사용자 · 흐름의 공급사 · 생산팀 주소)
MAX_SUBJECT_CHARS = 200
MAX_BODY_CHARS = 100_000
_ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@" + re.escape(CLASS_DOMAIN))


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
                if not _ADDRESS.fullmatch(addr):
                    raise ValueError(f"받는 주소 '{addr}' 가 수업 메일 주소(이름@{CLASS_DOMAIN})가 아닙니다")
                out.append(addr)
    if not out:
        raise ValueError("받는 사람(to)이 없습니다")
    if len(out) > MAX_RECIPIENTS:
        raise ValueError(f"받는 사람은 {MAX_RECIPIENTS}명까지입니다")
    return out


def _request_fingerprint(tool: str, request: dict) -> str:
    return hashlib.sha256(json.dumps([tool, request], ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class EffectTools:
    def __init__(self, ledger: Ledger, smtp_factory=None):
        self.ledger = ledger
        self._smtp = smtp_factory or (lambda: smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10))
        self._once_lock = threading.Lock()     # 확인 → 발송 → 기록을 한 번에 하나씩(같은 키의 동시 재시도가 두 통이 되지 않게)

    def _once(self, tool: str, key: str | None, request: dict, work) -> dict:
        fingerprint = _request_fingerprint(tool, request)
        with self._once_lock:
            if key:
                prior = self.ledger.get(key)
                if prior is not None:
                    if prior.get("tool") != tool:
                        return error("INVALID", f"멱등 키 {key} 는 이미 다른 도구({prior.get('tool')})에 쓰였습니다")
                    if "request" not in prior:
                        # 지문을 남기기 전 판(2026-10-30 전)이 쓴 기록 — 같은 메일인지 가릴 수 없다. 다시 보내면 두 통이 될 수 있어 보내지 않는다
                        return error("INVALID", f"멱등 키 {key} 는 이전 판이 이미 썼고 그 기록에는 보낸 내용이 남아 있지 않아 같은 메일인지 "
                                                "확인할 수 없습니다 — 다시 보내지 않습니다(이미 한 통이 갔을 수 있으니 메일함을 확인하세요)")
                    if prior.get("request") != fingerprint:
                        return error("INVALID", f"멱등 키 {key} 는 이미 다른 내용의 메일에 쓰였습니다 — 같은 키로 다른 메일을 보내지 않습니다")
                    return ok(dict(prior["document"], replayed=True))
            try:
                doc = work()
            except ValueError as e:
                return error("INVALID", str(e))
            except (OSError, smtplib.SMTPException, urllib.error.URLError, RuntimeError) as e:
                return error("UNKNOWN", f"메일 서버에 보내지 못했습니다({SMTP_HOST}:{SMTP_PORT}) — {type(e).__name__}: {str(e)[:200]}")
            if key:
                self.ledger.put(key, tool, {"tool": tool, "request": fingerprint, "document": doc})
            return ok(dict(doc, replayed=False))

    def send_mail(self, to, subject: str, body: str, cc=None, idempotency_key: str | None = None) -> dict:
        request = {"to": to, "cc": cc, "subject": subject, "body": body}

        def work():
            rcpt = _recipients(to)
            copy = _recipients(cc) if cc else []
            title = str(subject or "").strip()
            if not title:
                raise ValueError("제목(subject)이 비었습니다")
            if len(title) > MAX_SUBJECT_CHARS:
                raise ValueError(f"제목은 {MAX_SUBJECT_CHARS}자까지입니다(지금 {len(title)}자)")
            text = str(body or "")
            if len(text) > MAX_BODY_CHARS:
                raise ValueError(f"본문은 {MAX_BODY_CHARS:,}자까지입니다(지금 {len(text):,}자)")
            msg = EmailMessage()
            msg["From"] = formataddr(("HYD 프로세스", MAIL_FROM))
            msg["To"] = ", ".join(rcpt)
            if copy:
                msg["Cc"] = ", ".join(copy)
            msg["Subject"] = title
            msg["Message-ID"] = make_msgid(domain=CLASS_DOMAIN)
            if idempotency_key:
                msg["X-HYD-Idempotency-Key"] = idempotency_key
            msg.set_content(text)
            with self._smtp() as smtp:
                smtp.send_message(msg)
            return {"message_id": msg["Message-ID"], "to": rcpt, "cc": copy, "subject": msg["Subject"], "sent_at": _now(),
                    "smtp": f"{SMTP_HOST}:{SMTP_PORT}"}
        return self._once("send_mail", idempotency_key, request, work)

    def smtp_ready(self) -> dict:
        """건강 검사: 메일 서버(수업 메일함)가 연결 · NOOP 에 답하는가."""
        try:
            with self._smtp() as smtp:
                code = smtp.noop()[0]
        except (OSError, smtplib.SMTPException) as e:
            return {"ok": False, "smtp": f"{SMTP_HOST}:{SMTP_PORT}", "error": f"{type(e).__name__}: {str(e)[:200]}"}
        return {"ok": code == 250, "smtp": f"{SMTP_HOST}:{SMTP_PORT}"}
