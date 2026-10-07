"""Reading the agent's last message as a business result (process-gpt-cli-agent/core/outcome.py).

The contract asked for a JSON object when the process defined a form. This module decides whether it got one — and
refuses to pretend otherwise: a form field filled with a shrug is indistinguishable downstream from one a person filled in.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .prompt import field_keys
from .workspace import RESULT_FILE
from hydcommon.process_contracts import validate_output

_FENCE = re.compile(r"```(?:json)?\s*(?P<body>\{.*?\})\s*```", re.DOTALL)
DEFAULT_MAX_FILE_BYTES = 16 * 1024 * 1024


@dataclass
class Outcome:
    raw_text: str
    outputs: dict[str, Any] = field(default_factory=dict)
    contract_met: bool = True
    mismatch_reason: str = ""
    missing_fields: list[str] = field(default_factory=list)
    source: str = "message"          # A119: "file" when the result came from the workspace result file

    @property
    def payload(self) -> dict[str, Any]:
        """What gets stored on the work item: the form holds the answer, the text holds the reasoning."""
        body: dict[str, Any] = {"text": self.raw_text}
        if self.outputs:
            body.update(self.outputs)
        return body


def interpret(final_text: str, form_fields: Any, *, versioned: bool = False, result_file: Path | None = None,
              max_file_bytes: int = DEFAULT_MAX_FILE_BYTES) -> Outcome:
    """A119 (r14 B1): when the run wrote `output/result.json`, that file is the result and the last message is only a
    note (studio writes `_parsed_*.json` and ingests the path — the output-token ceiling never applies). A file that is
    there but unreadable is a contract defect of the file (sent back for correction), never silently replaced by the
    message; no file means the message route as before."""
    text = (final_text or "").strip()
    keys = field_keys(form_fields)
    if not keys or keys == ["freeform"]:
        return Outcome(raw_text=text)
    if result_file is not None and result_file.is_file():
        parsed, defect = _read_result_file(result_file, max_file_bytes)
        if defect:
            return Outcome(raw_text=text, contract_met=False, mismatch_reason=defect, missing_fields=keys, source="file")
        return _against_form(text, parsed, keys, form_fields, versioned, source="file")
    if not text:
        return Outcome(raw_text=text, contract_met=False, mismatch_reason="에이전트가 결과를 반환하지 않았습니다.", missing_fields=keys)
    parsed = _extract_object(text)
    if parsed is None:
        return Outcome(raw_text=text, contract_met=False, mismatch_reason="결과가 JSON 객체가 아닙니다. 폼 필드에 채울 값을 판별할 수 없습니다.", missing_fields=keys)
    return _against_form(text, parsed, keys, form_fields, versioned, source="message")


def _against_form(text: str, parsed: dict, keys: list[str], form_fields: Any, versioned: bool, *, source: str) -> Outcome:
    if versioned:
        try:
            validate_output({'fields_json':form_fields},parsed)
        except ValueError as e:
            return Outcome(raw_text=text,contract_met=False,mismatch_reason=str(e),source=source)
        return Outcome(raw_text=text,outputs={k:parsed[k] for k in keys if k in parsed},source=source)
    missing = [k for k in keys if k not in parsed or _is_blank(parsed.get(k))]
    outputs = {k: parsed[k] for k in keys if k in parsed}
    if missing:
        return Outcome(raw_text=text, outputs=outputs, contract_met=False, mismatch_reason=f"필수 폼 필드가 비어 있습니다: {', '.join(missing)}", missing_fields=missing, source=source)
    return Outcome(raw_text=text, outputs=outputs, source=source)


def _read_result_file(path: Path, max_file_bytes: int) -> tuple[dict | None, str]:
    """(object, "") or (None, defect). Size cap before reading, UTF-8 (BOM tolerated), one JSON object."""
    try:
        size = path.stat().st_size
    except OSError as e:
        return None, f"결과 파일 `{RESULT_FILE}`을 읽을 수 없습니다: {e}"
    if size > max_file_bytes:
        return None, f"결과 파일 `{RESULT_FILE}`이 너무 큽니다({size:,} B > 상한 {max_file_bytes:,} B). 결과를 줄일 수 없으면 담당자에게 알리세요."
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        return None, f"결과 파일 `{RESULT_FILE}`을 UTF-8 텍스트로 읽을 수 없습니다: {e}"
    try:
        value = json.loads(raw)
    except ValueError as e:
        return None, f"결과 파일 `{RESULT_FILE}`이 올바른 JSON이 아닙니다: {e}. 파일을 다시 쓰세요(메시지에 JSON을 넣지 말고)."
    if not isinstance(value, dict):
        return None, f"결과 파일 `{RESULT_FILE}`의 최상위가 JSON 객체가 아닙니다({type(value).__name__})."
    return value, ""


def _extract_object(text: str) -> dict[str, Any] | None:
    """The whole message, a fenced block, then the last balanced {…} — last because an answer after an explanation is at the end."""
    direct = _load(text)
    if direct is not None:
        return direct
    for candidate in reversed(_FENCE.findall(text)):
        parsed = _load(candidate)
        if parsed is not None:
            return parsed
    for candidate in reversed(_balanced_objects(text)):
        parsed = _load(candidate)
        if parsed is not None:
            return parsed
    return None


def _load(candidate: str) -> dict[str, Any] | None:
    try:
        value = json.loads(candidate.strip())
    except (json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _balanced_objects(text: str) -> list[str]:
    found, depth, start, in_string, escaped = [], 0, -1, False, False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start >= 0:
                found.append(text[start:i + 1])
    return found


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False
