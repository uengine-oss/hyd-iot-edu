"""5일차 에이전트 답의 기대 출력 예를 만든다.

AI 를 부르지 않는다. 학생 폴더의 도구(work/agent/tools.py)를 실제로 불러 받은 반환값으로 답의 각 칸을 조립한다.
에이전트가 낸 답이 이 모양이면 자동 확인을 통과한다는 것을 보이는 용도다.
"""
from __future__ import annotations

import json
from typing import Callable

ToolCaller = Callable[[str, dict], dict]


def document(source: dict) -> dict:
    return {"kind": "문서", **{key: source[key] for key in ("doc", "section", "line", "quote")}}


def finish(question: dict, calls: list[dict], **fields) -> dict:
    base = {"question_id": question["id"], "question": question["question"], "causes": [], "actions": [],
            "evidence": [], "missing": [], "control": "없음", "tool_calls": calls}
    return {**base, **fields}


def record(call: ToolCaller, name: str, arguments: dict) -> dict:
    return {"name": name, "input": arguments, "output": call(name, arguments)}


def draft(question: dict) -> dict:
    return finish(question, [], status="보류", answer="조회 도구가 없어 근거를 확인하지 못했습니다.", missing=["조회 도구가 연결되지 않음"])


def causes_answer(question: dict, call: ToolCaller) -> dict:
    step = record(call, "get_failure_knowledge", {"asset_id": question["asset_id"], "failure_name": "과열"})
    causes = step["output"]["causes"]
    names = [cause["name"] for cause in causes]
    return finish(question, [step], status="답변", answer=f"매뉴얼에 따르면 과열의 원인은 {', '.join(names)} 입니다.",
                  causes=names, evidence=[document(cause["source"]) for cause in causes])


def current_answer(question: dict, call: ToolCaller) -> dict:
    step = record(call, "get_current_value", {"asset_id": question["asset_id"], "kind": "출구 온도"})
    current, match = step["output"]["current"], step["output"]["matches"][0]
    evidence = [{"kind": "현재 값", **{key: current[key] for key in ("sensor_id", "value", "unit", "measured_at")}},
                document(match["source"]), *[document(action["source"]) for action in match["actions"]]]
    actions = [action["name"] for action in match["actions"]]
    return finish(question, [step], status="답변", actions=actions, evidence=evidence,
                  answer=f"지금 출구 온도는 {current['value']} {current['unit']} 로 '{match['symptom']}' 기준에 해당합니다. 할 수 있는 조치는 {', '.join(actions)} 입니다.")


def hold_answer(question: dict, call: ToolCaller, name: str, arguments: dict, missing: str | None = None) -> dict:
    step = record(call, name, arguments)
    reason = missing or step["output"]["reason"]
    return finish(question, [step], status="보류", answer=f"근거가 부족해 답을 보류합니다. {reason}", missing=[reason])


def build(questions: dict[str, dict], call: ToolCaller, question_id: str) -> dict:
    question = questions[question_id]
    asset_id = question["asset_id"]
    if question_id == "q1":
        return causes_answer(question, call)
    if question_id == "q2":
        return current_answer(question, call)
    if question_id == "q3":
        return hold_answer(question, call, "get_related", {"asset_id": asset_id}, f"설비 {asset_id} 의 부품 목록에 압축기가 없습니다.")
    if question_id == "q4":
        return hold_answer(question, call, "get_current_value", {"asset_id": asset_id, "kind": "팬 회전수"})
    if question_id == "q5":
        return hold_answer(question, call, "get_failure_knowledge", {"asset_id": asset_id, "failure_name": "과열"})
    raise KeyError(question_id)


def dump(answer: dict) -> str:
    return json.dumps(answer, ensure_ascii=False, indent=2) + "\n"
