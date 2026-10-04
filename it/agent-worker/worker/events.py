"""cliagents ExecEvent → the events ProcessGPT's screens already know (process-gpt-cli-agent/core/events.py).

Two rules: an event with nothing to show produces nothing; an event we do not recognise still produces something
(agent_log) so a new CLI event type is visible rather than absent. Each UI event is also stored as an `events` row
(record_events_bulk) under the product's event_type_enum so the portal and the Execution layer see the same trace.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cliagents import ExecEvent, ExecEventKind

PREVIEW_MAX = 4_000

#: UI event type → events.event_type (enum). UI events without a row type are streamed only.
#: permission_request is streamed only: the pause (runner._pause) records the one human_asked row with its job id and signature.
ROW_TYPE = {"run_start": "task_working", "tool_start": "tool_usage_started", "tool_end": "tool_usage_finished",
            "error": "error", "usage": "task_working", "file_artifact": "task_working"}


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


def _truncate(value: Any) -> Any:
    if isinstance(value, str) and len(value) > PREVIEW_MAX:
        return value[:PREVIEW_MAX] + "\n… (생략됨)"
    if isinstance(value, (dict, list)):
        text = repr(value)
        return value if len(text) <= PREVIEW_MAX else text[:PREVIEW_MAX] + "… (생략됨)"
    return value
