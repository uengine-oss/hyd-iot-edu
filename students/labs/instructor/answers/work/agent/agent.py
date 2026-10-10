"""냉각장치 질문 에이전트. 질문을 받아 조회 도구를 부르고, 도구 결과를 근거로 답을 낸다.

    python work/agent/agent.py --question-id q1             # 도구를 써서 답한다
    python work/agent/agent.py --question-id q1 --no-tools  # 도구 없이 초안만(비교용)

답은 work/agent/answers/ 에 JSON 으로 저장한다. 설비를 제어하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import anthropic

AGENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENT_DIR))

from labkit.settings import KIT_ROOT, setting, setting_or  # noqa: E402
from tools import TOOLS, call_tool  # noqa: E402

QUESTIONS_FILE = KIT_ROOT / "day5" / "questions.json"
ANSWERS_DIR = AGENT_DIR / "answers"
SYSTEM_PROMPT = (AGENT_DIR / "system_prompt.md").read_text(encoding="utf-8")
DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
MAX_TURNS = 8
SUBMIT_TOOL = "submit_answer"

EVIDENCE_ITEM = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["문서", "현재 값"]},
        "doc": {"type": ["string", "null"]}, "section": {"type": ["string", "null"]},
        "line": {"type": ["integer", "null"]}, "quote": {"type": ["string", "null"]},
        "sensor_id": {"type": ["string", "null"]}, "value": {"type": ["number", "null"]},
        "unit": {"type": ["string", "null"]}, "measured_at": {"type": ["string", "null"]},
    },
    "required": ["kind", "doc", "section", "line", "quote", "sensor_id", "value", "unit", "measured_at"],
    "additionalProperties": False,
}
SUBMIT_SPEC = {
    "name": SUBMIT_TOOL,
    "description": "최종 답을 낸다. 조회가 끝난 뒤 한 번만 부른다.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["답변", "보류"]},
            "answer": {"type": "string"},
            "causes": {"type": "array", "items": {"type": "string"}},
            "actions": {"type": "array", "items": {"type": "string"}},
            "evidence": {"type": "array", "items": EVIDENCE_ITEM},
            "missing": {"type": "array", "items": {"type": "string"}},
            "control": {"type": "string", "enum": ["없음"]},
        },
        "required": ["status", "answer", "causes", "actions", "evidence", "missing", "control"],
        "additionalProperties": False,
    },
}


def load_question(question_id: str) -> dict:
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]
    for question in questions:
        if question["id"] == question_id:
            return question
    raise SystemExit(f"{QUESTIONS_FILE} 에 질문 {question_id} 가 없습니다. 있는 질문: {[q['id'] for q in questions]}")


def drop_empty(evidence: list[dict]) -> list[dict]:
    return [{key: value for key, value in item.items() if value is not None} for item in evidence]


def ask(question: dict, use_tools: bool) -> dict:
    """도구 호출이 끝나고 submit_answer 가 올 때까지 대화를 이어 간다."""
    client = anthropic.Anthropic(api_key=setting("ANTHROPIC_API_KEY"))
    model = setting_or("LAB_AGENT_MODEL", DEFAULT_MODEL)
    tools = ([*TOOLS] if use_tools else []) + [SUBMIT_SPEC]
    messages = [{"role": "user", "content": f"설비 번호: {question['asset_id']}\n질문: {question['question']}"}]
    tool_calls: list[dict] = []
    for _ in range(MAX_TURNS):
        response = client.messages.create(model=model, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT, tools=tools, messages=messages)
        if response.stop_reason != "tool_use":
            raise RuntimeError(f"에이전트가 답을 내지 않고 멈췄습니다(stop_reason={response.stop_reason}).")
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == SUBMIT_TOOL:
                return {**block.input, "evidence": drop_empty(block.input["evidence"]), "tool_calls": tool_calls}
            output = call_tool(block.name, block.input)
            tool_calls.append({"name": block.name, "input": block.input, "output": output})
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": json.dumps(output, ensure_ascii=False), "is_error": not output["ok"]})
        messages.append({"role": "user", "content": results})
    raise RuntimeError(f"{MAX_TURNS}번 안에 답을 내지 못했습니다.")


def main() -> None:
    parser = argparse.ArgumentParser(description="냉각장치 질문 에이전트")
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--no-tools", action="store_true", help="조회 도구 없이 초안만 낸다")
    args = parser.parse_args()
    question = load_question(args.question_id)
    answer = {"question_id": question["id"], "question": question["question"], **ask(question, not args.no_tools)}
    ANSWERS_DIR.mkdir(exist_ok=True)
    name = f"draft_{question['id']}.json" if args.no_tools else f"{question['id']}.json"
    (ANSWERS_DIR / name).write_text(json.dumps(answer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[최종 답] {answer['status']}: {answer['answer']}")
    print(f"저장: {ANSWERS_DIR / name}")


if __name__ == "__main__":
    main()
