"""Turning a work item into something worth handing an agent (process-gpt-cli-agent/core/prompt.py).

A CLI agent gets one prompt and whatever is on disk. Everything the product's orchestration would have injected as
context — who asked, what the form wants back, what the reviewer objected to — has to be said. The output contract gets
the most attention because it fails silently: an essay where the form wanted three fields is wrong in a way no exception
reports.
"""
from __future__ import annotations

import json
from typing import Any

def build(row: dict[str, Any], extras: dict[str, Any], *, workdir: str) -> str:
    """The prompt for one work item: 업무 · 지시사항 · 참여자 · 입력 데이터 · 피드백 · 참고 자료 · 작업 공간 · 결과 제출 형식."""
    sections: list[str] = ["당신은 ProcessGPT 업무 프로세스의 담당 에이전트입니다. 아래 업무를 끝까지 수행하고, 마지막에 결과를 제시하세요."]
    activity = (row.get("activity_name") or "").strip()
    query = (row.get("query") or "").strip()
    if activity:
        sections.append(f"## 업무\n{activity}")
    if query:
        sections.append(f"## 지시사항\n{query}")
    participants = _participants(extras)
    if participants:
        sections.append(f"## 참여자\n{participants}")
    inputs = _inputs(row, extras)
    if inputs:
        sections.append(f"## 입력 데이터\n{inputs}")
    feedback = (extras.get("summarized_feedback") or "").strip()
    if feedback:
        sections.append("## 이전 결과에 대한 피드백\n" f"{feedback}\n\n" "이 피드백을 반영해 결과를 수정하세요. 같은 결과를 반복하지 마세요.")
    sources = _sources(extras)
    if sources:
        sections.append(f"## 참고 자료\n{sources}")
    sections.append("## 작업 공간\n" f"작업 디렉터리는 `{workdir}` 입니다. 산출 파일은 이 디렉터리 안에 만드세요. 이 디렉터리 밖에는 쓰지 마세요. "
                    "온톨로지 스키마 설명은 `context/schema_prompt.md` 에 있습니다.")
    sections.append(output_contract(extras.get("form_fields")))
    if any(field.get('key') == 'decision_id' for field in field_list(extras.get('form_fields'))):
        sections.append('## 판단 등록의 생산 작업\nsubmit_decision 호출 시 process_scope에 아래 객체를 그대로 전달하세요. '
                        '이 작업의 새 판단 ID만 출력하며 이전 작업/세대의 판단을 재사용하지 마세요.\n'
                        + json.dumps(extras.get('process_scope') or {}, ensure_ascii=False))
    sections.append("## 담당자에게 업무 정보 질문\n"
                    "필수 업무 정보가 없고 연결된 조회 도구로도 확인할 수 없으면 값을 지어내지 마세요. "
                    "작업을 완료하는 대신 마지막 메시지에 다음 JSON 객체 하나만 내고 기다리세요: "
                    '{"__human_input__":{"question":"담당자가 답할 구체적인 질문","options":[]}}. '
                    "options에는 필요할 때 선택지 문자열을 넣습니다. 이 응답은 완료 결과가 아닙니다. "
                    "도구 접근 거절이나 설비 조치 승인 우회에는 쓰지 마세요. 답변은 실행 권한을 바꾸지 않습니다.")
    return "\n\n".join(s for s in sections if s.strip())


def resume_prompt(answer: str, *, previous_summary: str = "", restarted: bool = False) -> str:
    """How to continue after a person answered (the product's hitl.plan_resume prompts)."""
    if not restarted:
        return f"담당자 응답: {answer}\n\n이 응답을 반영해 중단된 지점부터 작업을 계속하세요. 이미 완료한 작업은 다시 하지 마세요."
    text = f"담당자 응답: {answer}\n"
    if previous_summary:
        text += f"\n## 이전 진행 요약\n{previous_summary}\n"
    return text + "\n위 맥락을 참고해 작업을 새로 진행하세요."


def output_contract(form_fields: Any) -> str:
    fields = field_list(form_fields)
    if not fields:
        return "## 결과 제출 형식\n작업을 마치면 마지막 메시지에 최종 결과 본문을 그대로 작성하세요."
    described = "\n".join(_describe(f) for f in fields)
    skeleton = json.dumps({f["key"]: "" for f in fields}, ensure_ascii=False, indent=2)
    lines = ["## 결과 제출 형식", "근거 부족으로 완료할 수 없으면 완료 폼 대신 보류 객체 하나를 제출하세요: "
             '{"__deferred__":{"status":"UNKNOWN","reason":"실제 보류 이유","evidence":{}}}. '
             "조회 실패/결측은 UNKNOWN, 조회한 모든 근거가 불일치하면 UNSUPPORTED입니다. 실제 근거를 evidence에 보존합니다.",
             "작업을 마치면 **마지막 메시지에 아래 JSON 객체 하나만** 출력하세요. 설명 문장이나 코드펜스 밖 텍스트를 함께 쓰지 마세요.",
             "", f"필드:\n{described}"]
    if any(f.get("choices") for f in fields):
        lines.append("선택지가 있는 필드는 **허용값 중 하나를 그대로** 쓰세요. 뜻이 같아 보이는 다른 표현('예', 'Y', 'true' 등)으로 바꾸지 마세요.")
    lines.append(f"\n형태:\n```json\n{skeleton}\n```")
    return "\n".join(lines)


def _describe(field: dict[str, Any]) -> str:
    line = f"- `{field['key']}`: {field.get('label') or field['key']}"
    if field.get("type"):
        line += f" (형식: {field['type']})"
    choices = field.get("choices") or []
    if choices:
        allowed = ", ".join(f"`{value}`" + (f"({label})" if label and label != value else "") for value, label in choices)
        line += f"\n  허용값(이 중 하나를 그대로): {allowed}"
    return line


def _choices(raw: Any) -> list[tuple[str, str]]:
    """select/radio fields list their allowed values as [{"<value>": "<label>"}] (form_def.fields_json), [{value,label}] or strings."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw.replace("'", '"'))
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    out: list[tuple[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            out.append((item, item))
        elif isinstance(item, dict):
            if "value" in item or "key" in item:
                value = item.get("value") or item.get("key")
                label = item.get("label") or item.get("text") or item.get("title") or ""
                if value is not None:
                    out.append((str(value), str(label)))
            else:
                out.extend((str(v), str(l)) for v, l in item.items())
    return [(v, l) for v, l in out if v]


def field_list(form_fields: Any) -> list[dict[str, Any]]:
    """Normalise the form definition, which arrives in more than one shape."""
    if isinstance(form_fields, str):
        try:
            form_fields = json.loads(form_fields)
        except json.JSONDecodeError:
            return []
    if isinstance(form_fields, dict):
        form_fields = form_fields.get("fields") or form_fields.get("properties") or []
    if not isinstance(form_fields, list):
        return []
    out = []
    for f in form_fields:
        if not isinstance(f, dict):
            continue
        key = f.get("key") or f.get("name") or f.get("id")
        if not key:
            continue
        out.append({"key": str(key), "label": f.get("label") or f.get("text") or f.get("title") or "", "type": f.get("type") or "",
                    "choices": _choices(f.get("items") or f.get("options"))})
    return out


def field_keys(form_fields: Any) -> list[str]:
    return [f["key"] for f in field_list(form_fields)]


def _participants(extras: dict[str, Any]) -> str:
    lines = []
    for user in extras.get("users") or []:
        name = user.get("name") or user.get("username") or ""
        if name:
            lines.append(f"- 담당자: {name}")
    for agent in extras.get("agents") or []:
        name = agent.get("name") or agent.get("username") or ""
        role = agent.get("role") or agent.get("goal") or ""
        if name:
            lines.append(f"- 에이전트: {name}{f' ({role})' if role else ''}")
    return "\n".join(lines)


def _inputs(row: dict[str, Any], extras: dict[str, Any]) -> str:
    payload = row.get("output") or row.get("draft") or extras.get("sensitive_data")
    if not payload:
        return ""
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def _sources(extras: dict[str, Any]) -> str:
    lines = []
    for s in extras.get("sources") or []:
        if isinstance(s, dict) and (s.get("file_name") or s.get("file_path")):
            lines.append(f"- {s.get('file_name') or ''} {f'({s.get('file_path')})' if s.get('file_path') else ''}".strip())
    return "\n".join(lines)
