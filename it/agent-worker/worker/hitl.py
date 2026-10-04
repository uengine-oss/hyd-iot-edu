"""Pausing for a human, and picking up where the pause happened (process-gpt-cli-agent/core/hitl.py).

A CLI agent has no graph to suspend: the process ends. What survives is the pair (session id, workspace) — enough for
the CLI to resume its own conversation. So a pause is written down in the workspace, not held in memory; the answer that
arrives tomorrow still lands in the run that asked.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

_STATE_FILENAME = ".processgpt-pending.json"


def business_question(text: str) -> dict | None:
    """Explicit business input request, separate from CLI permission escalation."""
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(value, dict) or '__human_input__' not in value:
        return None
    request = value['__human_input__']
    if set(value) != {'__human_input__'} or not isinstance(request, dict):
        raise ValueError('사람 질문과 완료 결과를 함께 제출할 수 없습니다')
    if set(request) - {'question', 'options'}:
        raise ValueError('사람 질문은 question/options만 허용합니다')
    question, options = request.get('question'), request.get('options', [])
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError('사람 질문은 1~4000자의 문자열이어야 합니다')
    if (not isinstance(options, list) or len(options) > 8
            or any(not isinstance(o, str) or not o.strip() or len(o) > 500 for o in options)):
        raise ValueError('선택지는 비어 있지 않은 문자열 최대8개입니다')
    return {'question': question.strip(), 'options': options}


def durable_resume(row: dict) -> ResumePlan | None:
    """The DB request/job is authoritative; workspace files are only a cache."""
    draft, feedback = row.get('draft'), row.get('feedback')
    if not isinstance(draft, dict) or not isinstance(feedback, dict):
        return None
    request = draft.get('_human_request')
    if not isinstance(request, dict) or request.get('job_id') != feedback.get('job_id'):
        return None
    session = request.get('session_id')
    return ResumePlan(session_id=session) if isinstance(session, str) and session else None


@dataclass
class PendingRequest:
    run_id: str
    agent_id: str
    session_id: str
    question: str
    tool: str = ""
    job_id: str = ""
    asked_at: float = field(default_factory=time.time)
    fingerprint: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def fingerprint(tool: str, question: str) -> str:
    """Tool plus the first line: the tail of a permission message often carries a retry count or a timestamp."""
    head = (question or "").strip().splitlines()
    return f"{tool}::{head[0][:200] if head else ''}"


def state_path(workspace_path: Path) -> Path:
    return workspace_path / _STATE_FILENAME


def remember(workspace_path: Path, request: PendingRequest) -> bool:
    """Record a pause. False when this question is already pending (duplicate suppression)."""
    existing = recall(workspace_path)
    if existing and existing.fingerprint == request.fingerprint:
        return False
    path = state_path(workspace_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(request.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def recall(workspace_path: Path) -> PendingRequest | None:
    path = state_path(workspace_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return PendingRequest(**data) if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def clear(workspace_path: Path) -> None:
    try:
        state_path(workspace_path).unlink()
    except OSError:
        pass


@dataclass
class ResumePlan:
    session_id: str
    restarted: bool = False
    reason: str = ""


def plan_resume(workspace_path: Path, *, workspace_exists: bool) -> ResumePlan:
    """Resume the paused session when it is still there; otherwise say so (silently starting over is the failure this guards)."""
    pending = recall(workspace_path) if workspace_exists else None
    if pending and pending.session_id:
        return ResumePlan(session_id=pending.session_id)
    reason = "이전 작업 공간이 정리되어 이어갈 수 없습니다." if not workspace_exists else "이전 세션 정보를 찾을 수 없어 이어갈 수 없습니다."
    return ResumePlan(session_id="", restarted=True, reason=reason)
