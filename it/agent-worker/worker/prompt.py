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
    sections: list[str] = ["당신은 ProcessGPT 업무 프로세스의 담당 에이전트입니다. 아래 업무를 끝까지 수행하고, 마지막에 결과를 제시하세요. "
                           "진행 중에 남기는 설명과 마지막 메시지는 한국어로 쓰세요 — 포털 처리 과정에 그대로 보입니다(A158). "
                           "설명 문장에는 노드 id(예: skill:fan-max) 대신 이름(예: 팬 최대)을 쓰세요. 결과 필드의 id 값은 형식대로 둡니다."]
    activity = (row.get("activity_name") or "").strip()
    query = (row.get("query") or "").strip()
    if activity:
        sections.append(f"## 업무\n{activity}")
    if query:
        sections.append(f"## 지시사항\n{query}")
    if extras.get("agent_instructions"):     # U2: the assigned agent's profile and skills (agents_store.AgentSettings.instructions)
        sections.append(str(extras["agent_instructions"]))
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
    sections.append(FILE_READ_RULE)
    sections.append(output_contract(extras.get("form_fields")))
    from procsvc.result_correction import instructions
    contract_note = instructions(extras.get('form_contract'))
    if contract_note:
        sections.append('## 폼 계약 상세\n' + contract_note)
    if any(field.get('key') == 'decision_id' for field in field_list(extras.get('form_fields'))):
        sections.append('## 판단 등록의 생산 작업\n설비 고장·정비 판단은 submit_decision, 예비품 구매 판단은 submit_purchase를 사용합니다. '
                        '구매는 실제 ERP 부족부품 번호로 purchase_context와 evaluate_purchase를 조회하며 고장 원인·고장 유형을 만들어 넣지 마세요. '
                        '어느 판단 등록 도구든 호출 시 process_scope에 아래 객체를 그대로 전달하세요. '
                        '두 도구는 승인 대기 카드 등록만 하며 설비 명령·발주·입고를 실행하지 않습니다. '
                        '이 작업의 새 판단 ID만 출력하며 이전 작업/세대의 판단을 재사용하지 마세요.\n'
                        + json.dumps(extras.get('process_scope') or {}, ensure_ascii=False))
    sections.append("## 담당자에게 업무 정보 질문\n"
                    "필수 업무 정보가 없고 연결된 조회 도구로도 확인할 수 없으면 값을 지어내지 마세요. "
                    "작업을 완료하는 대신 마지막 메시지에 다음 JSON 객체 하나만 내고 기다리세요: "
                    '{"__human_input__":{"question":"담당자가 답할 구체적인 질문","options":[]}}. '
                    "options에는 필요할 때 선택지 문자열을 넣습니다. 이 응답은 완료 결과가 아닙니다. "
                    "도구 접근 거절이나 설비 조치 승인 우회에는 쓰지 마세요. 답변은 실행 권한을 바꾸지 않습니다.")
    sections.append(LANGUAGE_RULE)
    return "\n\n".join(s for s in sections if s.strip())


# C3 (U1 남은 것 1): the agent's narration between tool calls streamed in English ("Next I'll look up …"). The rule now closes
# the prompt too, where the model reads it last, and names the narration explicitly.
LANGUAGE_RULE = ("## 언어\n도구 호출 사이의 진행 설명, 판단 이유, 마지막 메시지까지 모든 자연어 문장을 한국어로 쓰세요. "
                 "\"Next I'll …\", \"Let me …\" 같은 영어 문장을 쓰지 마세요. 코드 · 식별자 · SQL · 원문 인용만 원문 그대로 둡니다.")

FILE_READ_RULE = ("## 작업 파일 읽기\n작업 파일과 등록 스킬은 BOM 없는 UTF-8 원문입니다. "
                  "Windows PowerShell에서 읽을 때는 기본 인코딩을 쓰지 말고 "
                  "`Get-Content -Raw -Encoding UTF8 -LiteralPath 'context/task.json'`처럼 UTF8을 명시하세요. "
                  "Python에서는 `Path(...).read_text(encoding='utf-8')`를 사용하세요. "
                  "깨진 문자열을 추측해 복원하거나 원본 파일에 BOM을 붙여 고치지 마세요.")


def resume_prompt(answer: str, *, previous_summary: str = "", restarted: bool = False, process_scope: dict | None = None) -> str:
    """How to continue after a person answered (the product's hitl.plan_resume prompts).
    The answer puts the task back in the queue; the worker that picks it up claims it under a new consumer id, so the process_scope the
    session read in its first prompt is no longer the claim — a write tool (submit_decision) sent with it is refused with 409 '현재 판단
    작업의 유효한 worker claim이 필요합니다' (2026-10-23 검수 · 라이브 B). The resumed text carries this run's scope."""
    scope = ("\n\n## 이번 실행의 process_scope (앞서 읽은 값은 무효)\n작업을 다시 잡아 담당 표시(consumer)가 바뀌었습니다. 판단 등록 같은 쓰기 "
             "도구에는 앞 대화에서 읽은 process_scope 대신 아래 값을 그대로 넘기세요(context/task.json 에도 같은 값이 있습니다).\n"
             + json.dumps(process_scope, ensure_ascii=False)) if process_scope else ""
    if not restarted:
        return (f"담당자 응답: {answer}\n\n이 응답을 반영해 중단된 지점부터 작업을 계속하세요. 이미 완료한 작업은 다시 하지 마세요.{scope}"
                f"\n\n{FILE_READ_RULE}\n\n{LANGUAGE_RULE}")
    text = f"담당자 응답: {answer}\n"
    if previous_summary:
        text += f"\n## 이전 진행 요약\n{previous_summary}\n"
    return text + "\n위 맥락을 참고해 작업을 새로 진행하세요.\n\n" + FILE_READ_RULE + "\n\n" + LANGUAGE_RULE


def format_correction(reason: str, form_fields: Any, *, form_contract=None) -> str:
    """A086: the result had the right content but not the contract's shape (e.g. an array sent as a JSON string). Same session,
    the exact defect, no new queries — the product's validate → correct → recheck loop (bpmn-extractor process_validator)."""
    from procsvc.result_correction import instructions
    return (f"방금 제출한 결과가 출력 형식 검사에서 거절됐습니다: {reason}\n"
            "조회나 분석을 다시 하지 말고, 같은 내용을 아래 형식에 맞춰 다시 제출하세요. 배열 필드는 JSON 배열 그대로(문자열로 감싸지 않음), "
            "숫자는 숫자로 쓰세요. 결과를 `output/result.json` 파일로 냈다면 그 파일을 고쳐 다시 쓰고 마지막 메시지에는 확인만 적으세요.\n\n"
            + output_contract(form_fields) + "\n\n" + instructions(form_contract) + "\n\n" + FILE_READ_RULE + "\n\n" + LANGUAGE_RULE)


#: 보류 판정 규칙(2026-10-25 수업 한 바퀴: 같은 진단 결과에 status 가 UNSUPPORTED · UNKNOWN 으로 갈리고, 학생 화면의 보류 사유에
#: diagnose · withheld=true · submit_decision 같은 도구 · 필드 이름이 그대로 나왔다). status 는 판단 엔진이 낸 값을 따르고, reason 은 사람 글로 쓴다.
DEFERRAL_RULE = ("status: 판단 엔진(진단 도구)이 근거 판정(evidence_status.status)을 냈으면 그 값을 그대로 씁니다. 그런 판정이 없을 때만 "
                 "조회 실패 · 결측은 UNKNOWN, 조회한 근거가 모두 조건에 맞지 않으면 UNSUPPORTED로 씁니다. "
                 "reason: 처리 건 화면에서 현장 담당자가 읽는 한국어 한두 문장입니다. 무엇이 없어서(예: 원인을 뒷받침하는 지식 · 센서 근거) 멈췄는지와 "
                 "담당자가 할 수 있는 일(예: 매뉴얼 지식을 적재한 뒤 다시 평가)을 씁니다. 도구 · 함수 · 필드 이름(diagnose, withheld, top_cause, "
                 "submit_decision 등)과 영문 상수 · JSON 값은 쓰지 않습니다. 실제 조회 결과는 evidence에 보존합니다.")


def output_contract(form_fields: Any) -> str:
    fields = field_list(form_fields)
    if not fields:
        return "## 결과 제출 형식\n작업을 마치면 마지막 메시지에 최종 결과 본문을 그대로 작성하세요."
    described = "\n".join(_describe(f) for f in fields)
    skeleton = json.dumps({f["key"]: "" for f in fields}, ensure_ascii=False, indent=2)
    lines = ["## 결과 제출 형식", "근거 부족으로 완료할 수 없으면 완료 폼 대신 보류 객체 하나를 제출하세요: "
             '{"__deferred__":{"status":"UNKNOWN 또는 UNSUPPORTED","reason":"현장 담당자가 읽을 보류 이유","evidence":{}}}. ' + DEFERRAL_RULE,
             "작업을 마치면 아래 JSON 객체 하나를 다음 두 방법 중 하나로 제출하세요. "
             "(a) 작업 디렉터리의 `output/result.json` 파일에 UTF-8 JSON으로 쓰고(스크립트로 써도 됨), 마지막 메시지에는 "
             "파일을 썼다는 짧은 확인 한 줄만 적습니다(결과 JSON을 메시지에 되풀이하지 않음). 결과가 길면 반드시 이 방법을 씁니다. "
             "(b) 파일을 쓰지 않았다면 **마지막 메시지에 그 JSON 객체 하나만** 출력합니다. 설명 문장이나 코드펜스 밖 텍스트를 함께 쓰지 마세요. "
             "파일이 있으면 파일이 결과이고 메시지는 읽지 않습니다.",
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
