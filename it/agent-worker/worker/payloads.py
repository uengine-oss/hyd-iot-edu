"""A161-G2: a tool result too large for an events row is kept whole, and the row points at it.

Two ways a result used to disappear from the trace:
  * Claude Code itself replaces an MCP result over ~150,000 characters with
    "Error: result (N characters) exceeds maximum allowed tokens. Output has been saved to <file>" — the agent never sees it,
    and the original stays only in that temp file on the worker PC (hyd evaluate_cards, live 2026-10-09);
  * the worker cuts every tool output at PREVIEW_MAX (events._truncate) before it becomes an events row.

Both now store the full text once in public.event_payloads (migration 20261009000048), content-addressed by sha256 like the
product's run journal snapshots (process-gpt cli-agent core/journal.py:187-201), and the tool_end row carries
`full_output` = {ref, chars, sha256, source, content_type, summary, …}. The row id is the hash of the case id and the content
(payload_id): the same text in one case is one row, but two cases (or two tenants) that got the same tool result each keep
their own row — a bare content hash let the first case own the row, so the second case's reference read another case's
row (its todo · job · tool_use ids) or, across tenants or after the first case was removed, nothing. `sha256` stays the
content hash. The product keeps only the preview
(cli-agent core/events.py _truncate_value → file_preview_max_bytes); HYD keeps the original too because the case record has to
show what the agent was handed (차이 있음: 제품에 없는 저장, 처리 기록 블랙박스 요구).

Only a path inside a `tool-results` directory named by that CLI message is read — a tool's own output cannot make the worker
read an arbitrary file.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

#: the CLI's own message for a result it moved to a file (UI side: it/portal/www/ui.js trace.truncated uses the same pattern)
TOO_LARGE = re.compile(r"exceeds maximum allowed tokens|result \(\d[\d,]*\s*characters\) exceeds", re.I)
SAVED_TO = re.compile(r"(?:saved|written) to:?\s+[`'\"]?(?P<path>.+?\.(?:txt|json|jsonl|md|log))(?=[`'\"]?(?:[\s.,;)]|$))", re.I)
SAVED_DIR = "tool-results"
MAX_FILE_BYTES = 16 * 1024 * 1024        #: a saved result larger than this is not read
MAX_CHARS = 4_000_000                    #: stored content is cut here (meta.cut says so)
SUMMARY_MAX = 1_200                      #: the readable summary the event row carries


def oversized(text: Any) -> bool:
    return isinstance(text, str) and bool(TOO_LARGE.search(text))


def saved_path(text: str) -> Path | None:
    """The temp file the CLI named, only when it lies under a `tool-results` folder and is a regular file."""
    m = SAVED_TO.search(text or "")
    if not m:
        return None
    path = Path(m.group("path").strip())
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if SAVED_DIR not in resolved.parts[:-1] or not resolved.is_file():
        return None
    return resolved


def read_saved(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None


def unwrap(text: str) -> tuple[str, bool]:
    """Claude Code saves an MCP result as its content-block list ([{"type":"text","text":"…"}]); the text inside is what the
    tool returned. Anything else is kept as is."""
    stripped = text.lstrip()
    if not stripped.startswith("["):
        return text, False
    try:
        blocks = json.loads(stripped)
    except ValueError:
        return text, False
    if isinstance(blocks, list) and blocks and all(isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str) for b in blocks):
        return "\n".join(b["text"] for b in blocks), True
    return text, False


def summarize(text: str, limit: int = SUMMARY_MAX) -> tuple[str, str]:
    """(content_type, one readable paragraph): the JSON shape when it parses (keys, list sizes), then the start of the text."""
    shape = ""
    content_type = "text"
    try:
        value = json.loads(text)
    except ValueError:
        value = None
    else:
        content_type = "json"
        shape = _shape(value)
    head = " ".join(text[:limit * 2].split())
    head = head if len(head) <= limit else head[:limit] + "…"
    lead = f"{len(text):,}자" + (f" · {shape}" if shape else "")
    return content_type, f"{lead}\n{head}"


def _shape(value: Any) -> str:
    if isinstance(value, dict):
        parts = []
        for k, v in list(value.items())[:12]:
            parts.append(f"{k}[{len(v)}]" if isinstance(v, (list, dict)) else str(k))
        more = f" 외 {len(value) - 12}개" if len(value) > 12 else ""
        return f"JSON 객체 · 키 {len(value)}개: " + ", ".join(parts) + more
    if isinstance(value, list):
        first = value[0] if value else None
        keys = f" · 첫 항목 키: {', '.join(list(first)[:8])}" if isinstance(first, dict) else ""
        return f"JSON 배열 · {len(value)}개 항목{keys}"
    return "JSON 값"


def capture(output: Any, *, preview_cut: bool) -> dict | None:
    """What should be kept whole for one tool result, or None when the row already holds all of it.
    Returns {content, source, meta, unread?} — `unread` (with no content) when the CLI's file could not be read."""
    if oversized(output):
        path = saved_path(output)
        raw = read_saved(path) if path else None
        if raw is None:
            return {"content": None, "source": "cli_saved_file", "meta": {"cli_message": output[:500]},
                    "unread": "CLI 가 결과를 옮긴 임시 파일을 찾지 못했거나 읽을 수 없습니다"}
        content, unwrapped = unwrap(raw)
        return {"content": content, "source": "cli_saved_file",
                "meta": {"cli_path": str(path), "cli_message": output[:500], "unwrapped": unwrapped, "file_chars": len(raw)}}
    if preview_cut:
        text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, default=str)
        return {"content": text, "source": "event_text", "meta": {}}
    return None


def payload_id(proc_inst_id: str | None, content_sha256: str) -> str:
    """The event_payloads row id: one row per (case, content) — see the module note."""
    return hashlib.sha256(f"{proc_inst_id or ''}\n{content_sha256}".encode("utf-8")).hexdigest()


def payload_row(captured: dict, *, tool: str, tool_use_id: str | None, job_id: str, todo_id: str, proc_inst_id: str | None) -> tuple[dict, str]:
    """(event_payloads row, readable summary) for captured content."""
    content = captured["content"].replace("\x00", "")          # PostgreSQL text holds no NUL
    original_chars, cut = len(content), len(content) > MAX_CHARS
    content = content[:MAX_CHARS]
    content_type, summary = summarize(content)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    row = {"id": payload_id(proc_inst_id, digest), "content": content, "chars": len(content),
           "content_type": content_type, "source": captured["source"], "tool": tool, "tool_use_id": tool_use_id, "job_id": job_id,
           "todo_id": todo_id, "proc_inst_id": proc_inst_id,
           "meta": dict(captured.get("meta") or {}, original_chars=original_chars, cut=cut, content_sha256=digest)}
    return row, summary


def reference(row: dict, summary: str, *, stored: bool, error: str | None = None) -> dict:
    """The `full_output` field of the tool_end event (what the portal reads)."""
    ref = {"ref": row["id"] if stored else None, "sha256": row["meta"]["content_sha256"], "chars": row["chars"], "original_chars": row["meta"]["original_chars"],
           "cut": row["meta"]["cut"], "source": row["source"], "content_type": row["content_type"], "summary": summary, "stored": stored}
    if error:
        ref["error"] = error
    return ref


def unread_reference(captured: dict) -> dict:
    """`full_output` when the CLI's temp file could not be read: said out loud instead of left blank."""
    return {"ref": None, "stored": False, "source": captured["source"], "error": captured["unread"]}
