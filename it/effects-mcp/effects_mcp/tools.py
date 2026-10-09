"""hyd-effects 쓰기 도구의 본체(FastMCP 없이 시험할 수 있게 분리). 사람 승인 뒤 process 의 'mcp:call' 부품만 부른다.

  send_mail           SMTP 로 메일 한 통. 수업 기본은 Supabase 로컬의 Inbucket(SMTP 54325, 웹 54324) — 실제 발송 없음.
  add_calendar_entry  CMMS 일정 등록 → enterprise-sim POST /api/exec skill:calendar-entry (ent.cmms_calendar)
  record_case         처리 건 기록 한 장 → enterprise-sim POST /api/exec skill:record-case (ent.case_records)

멱등: 모든 도구가 idempotency_key 를 받는다(process 가 '처리 건:작업' 으로 넣는다). 같은 키의 두 번째 호출은 첫 결과를 그대로 돌려준다
(replayed=true) — 재시도해도 메일이 두 번 가지 않는다. 키 기록은 SQLite(EFFECTS_STATE_PATH)에, 업무 기록은 업무 DB 의 멱등 키
(decision = 'MCP:<키>')에도 남는다. 결과는 {"result": "ok" | "error", "document" | "message"} 봉투(enterprise-mcp 와 같은 모양).
"""
from __future__ import annotations

import json
import os
import smtplib
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

SMTP_HOST = os.getenv("SMTP_HOST", "host.docker.internal")
SMTP_PORT = int(os.getenv("SMTP_PORT", "54325"))
MAIL_FROM = os.getenv("EFFECTS_MAIL_FROM", "hyd-process@hyd.local")
ENTERPRISE_URL = os.getenv("ENTERPRISE_URL", "http://enterprise-sim:8095")
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
    def __init__(self, ledger: Ledger, smtp_factory=None, post=None):
        self.ledger = ledger
        self._smtp = smtp_factory or (lambda: smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10))
        self._post = post or _post_json

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

    def _exec(self, tool: str, skill: str, asset: str | None, params: dict, key: str | None) -> dict:
        def work():
            req = {"skill": skill, "asset": asset or "HYD-01", "by": "effects-mcp", "params": params,
                   "decision": f"MCP:{key}" if key else None}
            tx = self._post(ENTERPRISE_URL + "/api/exec", req)
            if not isinstance(tx, dict) or not tx.get("ref"):
                raise RuntimeError(f"업무 시스템 응답에 기록 번호가 없습니다: {str(tx)[:200]}")
            return {"ref": tx["ref"], "detail": tx.get("detail"), "transaction": tx.get("id"), "system": tx.get("system")}
        return self._once(tool, key, work)

    def add_calendar_entry(self, asset: str, title: str, starts_at: str | None = None, duration_h: float | None = None,
                           wo_ref: str | None = None, note: str | None = None, idempotency_key: str | None = None) -> dict:
        params = {k: v for k, v in {"title": title, "starts_at": starts_at, "duration_h": duration_h, "wo_ref": wo_ref, "note": note}.items()
                  if v not in (None, "")}
        return self._exec("add_calendar_entry", "skill:calendar-entry", asset, params, idempotency_key)

    def record_case(self, title: str, body: str, asset: str | None = None, proc_inst_id: str | None = None,
                    idempotency_key: str | None = None) -> dict:
        params = {k: v for k, v in {"title": title, "body": body, "proc_inst_id": proc_inst_id}.items() if v not in (None, "")}
        return self._exec("record_case", "skill:record-case", asset, params, idempotency_key)


def _post_json(url: str, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode(), headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        if e.code in (400, 409):
            raise ValueError(f"업무 시스템이 거절했습니다({e.code}): {detail}") from e
        raise RuntimeError(f"업무 시스템 오류({e.code}): {detail}") from e
