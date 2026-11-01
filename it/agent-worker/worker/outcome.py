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
NO_RESULT = "에이전트가 결과를 반환하지 않았습니다."
FREEFORM_KEY = "freeform"          # 폼이 없는 단계의 칸 하나(worker/context.FREEFORM_FIELDS)


def _no_constant(value):
    raise ValueError(f"JSON 은 {value} 같은 비표준 숫자 상수를 받지 않습니다")


def strict_loads(text: str):
    """결과 JSON 읽기 한 곳(결과 해석 · 결과 검사 도구 worker/result_check 가 같이 쓴다): NaN · Infinity 를 받지 않는다 — 받아들이면 업무 DB
    (jsonb) 저장에서 일반 실패가 되고, 결과 검사 도구는 같은 파일을 거절해 두 판정이 갈렸다(검진 G1-19)."""
    return json.loads(text, parse_constant=_no_constant)


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
    message; no file means the message route as before. 폼이 없는 단계(자유형식 칸 하나)도 같은 규칙이다 — 예전에는 파일을 보기 전에
    메시지로 끝내 파일에 쓴 답을 버리고 「파일을 썼습니다」 한 줄을 결과로 저장했다(검진 G1-01)."""
    text = (final_text or "").strip()
    keys = field_keys(form_fields)
    if keys and result_file is not None and result_file.is_file():
        parsed, defect = _read_result_file(result_file, max_file_bytes)
        if defect:
            return Outcome(raw_text=text, contract_met=False, mismatch_reason=defect, missing_fields=keys, source="file")
        return _against_form(text, parsed, keys, form_fields, versioned, source="file")
    if not text:
        return Outcome(raw_text=text, contract_met=False, mismatch_reason=NO_RESULT, missing_fields=keys)
    if not keys:
        return Outcome(raw_text=text)
    parsed = _extract_object(text)
    if keys == [FREEFORM_KEY] and (parsed is None or FREEFORM_KEY not in parsed):
        # W4 (2026-10-23 검수): a step without a form (a student's bpmn.io agent task) — the answer may be plain text
        return Outcome(raw_text=text)
    if parsed is None:
        return Outcome(raw_text=text, contract_met=False, mismatch_reason="결과가 JSON 객체가 아닙니다. 폼 필드에 채울 값을 판별할 수 없습니다.", missing_fields=keys)
    return _against_form(text, parsed, keys, form_fields, versioned, source="message")


def deferral_in_result_file(result_file: Path | None, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES) -> str | None:
    """A151 (A148 item 55, 2026-10-08): the prompt asks for the result in `output/result.json`, so an agent that cannot
    assess writes its `{"__deferred__": …}` there too — the runner only looked at the last message, sent the file back for
    "form correction" twice and failed the run. Returns the file's JSON text when its top-level object carries
    `__deferred__` (task_deferral.control validates it exactly like the message route), otherwise None."""
    if result_file is None or not result_file.is_file():
        return None
    parsed, defect = _read_result_file(result_file, max_file_bytes)
    if defect or "__deferred__" not in parsed:
        return None
    return json.dumps(parsed, ensure_ascii=False)


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
        value = strict_loads(raw)
    except json.JSONDecodeError as e:
        return None, (f"결과 파일 `{RESULT_FILE}`이 올바른 JSON이 아닙니다: {e}. "
                      + _json_syntax_hint(raw, e)
                      + " 파일의 내용을 유지하며 표시된 문법을 고치세요(메시지에 JSON을 되풀이하지 말고).")
    except ValueError as e:
        return None, f"결과 파일 `{RESULT_FILE}`이 올바른 JSON이 아닙니다: {e}. 파일을 다시 쓰세요(메시지에 JSON을 넣지 말고)."
    if not isinstance(value, dict):
        return None, f"결과 파일 `{RESULT_FILE}`의 최상위가 JSON 객체가 아닙니다({type(value).__name__})."
    return value, ""


def _json_syntax_hint(raw: str, error: json.JSONDecodeError) -> str:
    """Bounded diagnostics only: never repair or silently accept a model's result."""
    before = raw[max(0, error.pos - 100):error.pos]
    after = raw[error.pos:error.pos + 100]
    hint = '오류 주변(일부 발췌): ' + json.dumps(before + ' ⟦오류 위치⟧ ' + after, ensure_ascii=False)
    stack, mismatches = [], []
    quoted = escaped = False
    line, column = 1, 0
    for char in raw:
        column += 1
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '{[':
            stack.append('}' if char == '{' else ']')
        elif char in '}]':
            if stack and stack[-1] == char:
                stack.pop()
            else:
                expected = stack[-1] if stack else '문서 끝'
                mismatches.append(f'{line}행 {column}열: {char} (열린 괄호에 맞는 기호는 {expected})')
                if len(mismatches) == 6:
                    break
        if char == '\n':
            line, column = line + 1, 0
    if mismatches:
        hint += ' 구분 기호 불일치 후보: ' + '; '.join(mismatches) + '. 문자열 안의 괄호는 제외했습니다.'
    return hint


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
        value = strict_loads(candidate.strip())
    except ValueError:                     # JSONDecodeError 도 ValueError — 비표준 상수가 든 글은 결과가 아니다
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
