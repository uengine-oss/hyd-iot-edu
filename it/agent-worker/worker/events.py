"""cliagents ExecEvent → the events ProcessGPT's screens already know (process-gpt-cli-agent/core/events.py).

Two rules: an event with nothing to show produces nothing; an event we do not recognise still produces something
(agent_log) so a new CLI event type is visible rather than absent. Each UI event is also stored as an `events` row
(record_events_bulk) under the product's event_type_enum so the portal and the Execution layer see the same trace.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from cliagents import ExecEvent, ExecEventKind

PREVIEW_MAX = 4_000
CONSOLE_MAX = 120
NOTE_MAX = 1_500           #: U1: one assistant note (the agent's own words between tool calls) is stored up to this many characters

#: UI event type → events.event_type (enum). UI events without a row type are streamed only.
#: permission_request is streamed only: the pause (runner._pause) records the one human_asked row with its job id and signature.
ROW_TYPE = {"run_start": "task_working", "tool_start": "tool_usage_started", "tool_end": "tool_usage_finished",
            "error": "error", "usage": "task_working", "file_artifact": "task_working", "assistant_note": "task_working",
            "skills_provided": "task_working", "skill_used": "task_working"}


@dataclass(frozen=True)
class UiEvent:
    type: str
    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.data}


def translate(event: ExecEvent) -> list[UiEvent]:
    kind = event.kind
    if kind is ExecEventKind.ASSISTANT_TEXT:
        return [UiEvent("text", {"content": event.text})] if event.text else []
    if kind is ExecEventKind.THINKING:
        return [UiEvent("thinking", {"content": event.text})] if event.text else []
    if kind is ExecEventKind.TOOL_START:
        return [UiEvent("tool_start", {"tool": event.tool or "tool", "tool_use_id": event.tool_use_id, "input": _truncate(event.tool_input)})]
    if kind is ExecEventKind.TOOL_END:
        return [UiEvent("tool_end", {"tool": event.tool or "tool", "tool_use_id": event.tool_use_id, "output": _truncate(event.text or event.tool_output), "is_error": event.is_error})]
    if kind is ExecEventKind.PLAN:
        return [UiEvent("plan_update", {"items": event.tool_output or []})]
    if kind is ExecEventKind.FILE_CHANGE:
        return [UiEvent("file_artifact", {"path": event.path, "operation": event.change or "modified", "content": _truncate(event.text)})]
    if kind is ExecEventKind.PERMISSION_REQUEST:
        return [UiEvent("permission_request", {"tool": event.tool or "", "detail": event.text, "tool_use_id": event.tool_use_id})]
    if kind is ExecEventKind.USAGE:
        return [UiEvent("usage", {"usage": event.usage or {}})]
    if kind is ExecEventKind.ERROR:
        return [UiEvent("error", {"content": event.text, "error": event.text})]
    if kind is ExecEventKind.RUN_START:
        return [UiEvent("run_start", {"session_id": event.session_id, "model": event.text})]
    if kind is ExecEventKind.RESULT:
        return []
    if event.text:
        return [UiEvent("agent_log", {"content": event.text})]
    if event.raw:
        return [UiEvent("agent_log", {"raw": _truncate(event.raw)})]
    return []


def row_of(ui: UiEvent, *, job_id: str, todo_id: str, proc_inst_id: str | None, crew_type: str) -> dict | None:
    """The events row for a UI event, or None for stream-only events (text, thinking, plan, agent_log)."""
    event_type = ROW_TYPE.get(ui.type)
    if event_type is None:
        return None
    return {"job_id": job_id, "todo_id": todo_id, "proc_inst_id": proc_inst_id, "crew_type": crew_type, "event_type": event_type,
            "data": ui.as_dict()}


def task_started(row: dict, provider_name: str) -> dict:
    """The card the work-item panel opens first (the product's executor._started)."""
    return {"goal": (row.get("activity_name") or "").strip() or "업무 수행", "name": provider_name, "role": "CLI 코딩 에이전트",
            "task_description": (row.get("query") or "").strip()[:500]}


def short_tool(name: Any) -> str:
    """mcp__neo4j__read_neo4j_cypher → neo4j/read_neo4j_cypher; built-in tools keep their name."""
    raw = str(name or "tool")
    return raw[5:].replace("__", "/") if raw.startswith("mcp__") else raw


def console_summary(value: Any, limit: int = CONSOLE_MAX) -> str:
    """One line of a tool input/result for the terminal: whitespace collapsed, JSON for structures, cut at `limit`."""
    if value is None:
        return "없음"
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


class ConsoleLog:
    """U1 (TODO 7): one terminal line per tool call start/end (plus run start and errors) so whoever watches the worker's
    console sees what the agent is doing — the logger adds the time; the line carries instance · step · tool · summary · ms."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._starts: dict[str, float] = {}

    def line(self, ui: UiEvent, row: dict) -> str | None:
        d = ui.data
        where = f"{row.get('proc_inst_id') or '-'} · {row.get('activity_name') or row.get('activity_id') or '-'}"
        if ui.type == "run_start":
            return f"[실행 시작] {where} · 모델 {d.get('model') or '-'} · 세션 {d.get('session_id') or '-'}"
        if ui.type == "tool_start":
            self._starts[str(d.get("tool_use_id") or "")] = self._clock()
            return f"[도구 시작] {where} · {short_tool(d.get('tool'))} · 입력 {console_summary(d.get('input'))}"
        if ui.type == "tool_end":
            started = self._starts.pop(str(d.get("tool_use_id") or ""), None)
            elapsed = f"{(self._clock() - started) * 1000:.0f} ms" if started is not None else "시간 미상"
            label = "오류" if d.get("is_error") else "결과"
            return f"[도구 끝] {where} · {short_tool(d.get('tool'))} · {label} {console_summary(d.get('output'))} · {elapsed}"
        if ui.type == "error":
            return f"[오류] {where} · {console_summary(d.get('content'))}"
        if ui.type == "assistant_note":
            return f"[판단] {where} · {console_summary(d.get('content'))}"
        if ui.type == "skill_used":
            return f"[스킬 읽음] {where} · {d.get('skill')} · {d.get('file')} · {d.get('via')}"
        return None


class NoteBuffer:
    """U1 (블랙박스 0): Claude Code streams its prose as text deltas, which are stream-only — so the reason the agent gave
    between two tool calls ("TS1 이 55 ℃ 를 넘었으니 쿨러 오염부터 확인한다") never reached the events table. The deltas are
    collected here and stored as ONE task_working row (type text) at the next boundary (tool start/end, error, result, end of
    stream), cut at NOTE_MAX. The final answer is not stored twice: the run's result text (task_completed carries it) is cut
    off the end of the last note, so only the words before it remain."""

    def __init__(self, limit: int = NOTE_MAX):
        self._limit = limit
        self._parts: list[str] = []

    def add(self, text: str | None) -> None:
        if text:
            self._parts.append(text)

    def flush(self, final_text: str | None = None) -> UiEvent | None:
        text, self._parts = "".join(self._parts).strip(), []
        final = (final_text or "").strip()
        if final and text.endswith(final):
            text = text[:-len(final)].strip()                 # keep only the words before the answer
        if not text:
            return None
        cut = len(text) > self._limit
        return UiEvent("assistant_note", {"type": "text", "content": text[:self._limit] + ("… (생략됨)" if cut else ""),
                                          "chars": len(text), "truncated": cut})


#: ExecEvent kinds that close the agent's current paragraph (the note is recorded before them, so the order is kept)
NOTE_BOUNDARY = frozenset({ExecEventKind.TOOL_START, ExecEventKind.TOOL_END, ExecEventKind.ERROR, ExecEventKind.RESULT,
                           ExecEventKind.PERMISSION_REQUEST, ExecEventKind.FILE_CHANGE, ExecEventKind.PLAN})


# ---------------------------------------------------------------- A161-G1: which skills the run had, and which it read
#: a skill file named anywhere in a tool's input: Claude Code `Read .claude/skills/<name>/SKILL.md`, Codex `cat .agents/skills/…`
SKILL_PATH = re.compile(r"(?:\.claude|\.agents)[/\\]+skills[/\\]+(?P<name>[a-z0-9][a-z0-9-]{0,63})[/\\]+(?P<file>[^\s\"'`,;|&<>]+)")
#: Claude Code's Skill tool (the CLI loads the skill itself; the input names it)
SKILL_TOOLS = frozenset({"Skill"})


def skill_entry(skill: dict, *, text: str, path: str, source: str) -> dict:
    """One provided skill as the run had it: the hash is of the SKILL.md written into the workspace, so the record says which
    text the run saw even after the skill row is edited (tenant_skills keeps no versions)."""
    return {"name": skill["skill_name"], "path": path, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "version": hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], "chars": len(text),
            "description": str(skill.get("description") or ""), "source": source, "updated_at": _iso(skill.get("updated_at"))}


def skills_provided(entries: list[dict], *, cli: str, missing: list[str]) -> UiEvent:
    names = ", ".join(e["name"] for e in entries)
    content = (f"배정된 스킬 {len(entries)}개를 작업 폴더에 넣고 실행합니다: {names}" if entries else "배정된 스킬 없이 실행합니다")
    if missing:
        content += f" (본문이 없어 넣지 못함: {', '.join(missing)})"
    return UiEvent("skills_provided", {"content": content, "cli": cli, "skills": entries, "missing": list(missing)})


class SkillReads:
    """Emits one skill_used event the first time the agent reads a given file of a skill (Read / Bash / Grep naming a path
    under the skill folders, or Claude Code's Skill tool). Paths outside the provided set are still reported (known=false)."""

    def __init__(self, provided: list[dict] | None = None):
        self._by_name = {e["name"]: e for e in provided or []}
        self._seen: set[tuple[str, str]] = set()

    def on_tool_start(self, event: ExecEvent) -> list[UiEvent]:
        found: list[tuple[str, str]] = []
        if (event.tool or "") in SKILL_TOOLS:
            data = event.tool_input if isinstance(event.tool_input, dict) else {}
            name = str(data.get("skill") or data.get("command") or data.get("name") or "").strip().lstrip("/")
            if name:
                found.append((name, "SKILL.md"))
        text = event.tool_input if isinstance(event.tool_input, str) else json.dumps(event.tool_input, ensure_ascii=False, default=str)
        for m in SKILL_PATH.finditer(text or ""):
            found.append((m.group("name"), re.sub(r"[\\/]+", "/", m.group("file")).rstrip("/")))
        out = []
        for name, file in found:
            if (name, file) in self._seen:
                continue
            self._seen.add((name, file))
            known = self._by_name.get(name)
            data = {"content": f"스킬 \u2018{name}\u2019의 {file} 을(를) 읽었습니다", "skill": name, "file": file, "via": event.tool or "tool",
                    "tool_use_id": event.tool_use_id, "known": known is not None}
            if known:
                data.update(sha256=known["sha256"], version=known["version"], source=known["source"])
            out.append(UiEvent("skill_used", data))
        return out


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def preview_cut(value: Any) -> bool:
    """True when _truncate would shorten this tool output (the row then holds a preview only)."""
    if isinstance(value, str):
        return len(value) > PREVIEW_MAX
    if isinstance(value, (dict, list)):
        return len(repr(value)) > PREVIEW_MAX
    return False


def _truncate(value: Any) -> Any:
    if isinstance(value, str) and len(value) > PREVIEW_MAX:
        return value[:PREVIEW_MAX] + "\n… (생략됨)"
    if isinstance(value, (dict, list)):
        text = repr(value)
        return value if len(text) <= PREVIEW_MAX else text[:PREVIEW_MAX] + "… (생략됨)"
    return value
