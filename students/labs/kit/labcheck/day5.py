"""5일차 확인: 에이전트의 역할·입력·출력(5-1) · 조회 도구 연결(5-2) · 근거 부족이면 보류(5-3).

에이전트(AI)를 직접 돌리지는 않는다. 도구는 실제로 불러 보고, 에이전트가 저장한 답 파일이 도구 결과에 근거하는지 대조한다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from labcheck.core import CLI_TIMEOUT_SECONDS, Report, need_file, read_json, run_json, work_path
from labcheck.day4 import graph_knowledge, latest_reading, names
from labcheck.facts import read_kit_json
from labkit.settings import KIT_ROOT

STATUSES = {"답변", "보류"}
ANSWER_KEYS = ("status", "answer", "causes", "actions", "evidence", "missing", "control", "tool_calls")
REQUIRED_TOOLS = {"get_related", "get_current_value", "get_failure_knowledge"}
GROUNDED_QUESTIONS = ("q1", "q2")
HOLD_QUESTIONS = ("q3", "q4", "q5")
MIN_PROMPT_CHARS = 200
EVIDENCE_IGNORED_KEYS = {"kind"}
LOG_NAME = "tool_calls.jsonl"


def agent_path(relative: str):
    return work_path(f"agent/{relative}")


def drive(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": f"{KIT_ROOT}{os.pathsep}{work_path('')}", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "labcheck.tool_driver", str(agent_path("")), *args],
                          cwd=KIT_ROOT, env=env, capture_output=True, text=True, timeout=CLI_TIMEOUT_SECONDS)


def call_tool(report: Report, name: str, arguments: dict) -> dict:
    done = drive("call", name, json.dumps(arguments, ensure_ascii=False))
    report.require(f"도구 호출이 예외 없이 끝난다: {name} {json.dumps(arguments, ensure_ascii=False)}", done.returncode == 0,
                   f"오류 출력: {done.stderr.strip()[-600:]}")
    return json.loads(done.stdout)


def walk(value: Any):
    """중첩된 결과 안의 모든 사전을 차례로 낸다."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def grounded(evidence: dict, outputs: list[dict]) -> bool:
    """근거 하나가 도구 반환값 어딘가에 같은 값으로 들어 있는가."""
    wanted = {key: value for key, value in evidence.items() if key not in EVIDENCE_IGNORED_KEYS and value is not None}
    return bool(wanted) and any(all(found.get(key) == value for key, value in wanted.items()) for output in outputs for found in walk(output))


def names_in(outputs: list[dict]) -> set[str]:
    return {found["name"] for output in outputs for found in walk(output) if isinstance(found.get("name"), str)}


def load_answer(report: Report, filename: str) -> dict:
    answer = read_json(report, agent_path(f"answers/{filename}"), f"답({filename})")
    missing = [key for key in ANSWER_KEYS if key not in answer] if isinstance(answer, dict) else list(ANSWER_KEYS)
    report.require(f"{filename}: 출력 항목이 모두 있다", not missing, f"없는 항목: {missing}")
    report.check(f"{filename}: status 가 답변 · 보류 가운데 하나다", answer["status"] in STATUSES, f"나온 값 {answer['status']!r}")
    report.check(f"{filename}: 제어를 하지 않았다(control 이 '없음')", answer["control"] == "없음", f"나온 값 {answer['control']!r}")
    return answer


def check_grounding(report: Report, question_id: str, answer: dict) -> list[dict]:
    calls = answer["tool_calls"]
    report.require(f"{question_id}: 도구를 한 번 이상 불렀다", isinstance(calls, list) and bool(calls), "tool_calls 가 비어 있습니다. 도구 없이 답했습니다.")
    replayed = [call_tool(report, call.get("name"), call.get("input") or {}) for call in calls]
    report.check(f"{question_id}: 기록된 도구 반환값이 실제로 도구를 다시 불러 나온 값과 같다",
                 [call.get("output") for call in calls] == replayed, "기록과 실제 반환값이 다릅니다. 반환값을 고쳐 적지 않습니다.")
    loose = [item for item in answer["evidence"] if not grounded(item, replayed)]
    report.check(f"{question_id}: 근거가 모두 도구 반환값에 있다", not loose, f"도구 결과에 없는 근거: {loose}")
    invented = sorted((set(answer["causes"]) | set(answer["actions"])) - names_in(replayed))
    report.check(f"{question_id}: 도구 결과에 없는 원인 · 조치를 답에 쓰지 않았다", not invented, f"지어낸 이름: {invented}")
    return replayed


def lab5_1(report: Report) -> None:
    prompt = agent_path("system_prompt.md")
    need_file(report, prompt, "에이전트 지침")
    text = prompt.read_text(encoding="utf-8")
    report.check(f"지침에 목표 · 입력 · 도구 사용 조건 · 출력 항목을 적었다({MIN_PROMPT_CHARS}자 이상)", len(text) >= MIN_PROMPT_CHARS, f"지금 {len(text)}자입니다.")
    absent = [key for key in ANSWER_KEYS[:-1] if key not in text]
    report.check("지침에 출력 항목 이름이 모두 나온다", not absent, f"지침에 없는 항목: {absent}")
    need_file(report, agent_path("agent.py"), "에이전트 프로그램")
    draft = load_answer(report, "draft_q1.json")
    report.check("초안은 도구 없이 낸 답이다(tool_calls 가 비어 있다)", draft["tool_calls"] == [], "초안 단계에서는 도구를 연결하지 않습니다.")


def lab5_2(report: Report) -> None:
    need_file(report, agent_path("tools.py"), "도구")
    done = drive("specs")
    report.require("도구 목록(TOOLS)을 읽을 수 있다", done.returncode == 0, done.stderr.strip()[-600:])
    specs = {spec.get("name"): spec for spec in json.loads(done.stdout)}
    report.require("도구 세 개가 등록돼 있다", REQUIRED_TOOLS <= set(specs), f"없는 도구: {sorted(REQUIRED_TOOLS - set(specs))}")
    complete = all(specs[name].get("description") and specs[name].get("input_schema", {}).get("required") for name in REQUIRED_TOOLS)
    report.check("도구마다 설명과 필수 입력이 적혀 있다", complete, "description 또는 input_schema.required 가 빈 도구가 있습니다.")
    log = agent_path(LOG_NAME)
    before = len(log.read_text(encoding="utf-8").splitlines()) if log.is_file() else 0
    related = call_tool(report, "get_related", {"asset_id": "CL-01"})
    direct = run_json(report, work_path("find_related.py"), "--id", "CL-01")
    report.check("get_related 가 2일차 조회 기능과 같은 센서 · 부품을 돌려준다",
                 related.get("ok") is True and related.get("sensors") == direct.get("sensors") and related.get("components") == direct.get("components"),
                 f"도구 반환값 {related}")
    current = call_tool(report, "get_current_value", {"asset_id": "CL-01", "kind": "출구 온도"})
    sensor = next(node for node in graph_knowledge("CL-01")["sensors"].values() if node.get("kind") == "출구 온도")
    db_value = float(latest_reading(sensor["tag"])["value"])
    report.check("get_current_value 가 연습용 DB 의 현재 값을 돌려준다", (current.get("current") or {}).get("value") == db_value, f"도구 반환값 {current.get('current')}")
    knowledge = call_tool(report, "get_failure_knowledge", {"asset_id": "CL-01", "failure_name": "과열"})
    expected = graph_knowledge("CL-01")["failures"]["과열"]
    report.check("get_failure_knowledge 가 그래프에 등록된 원인 · 조치를 돌려준다",
                 names(knowledge.get("causes", [])) == names(expected["CAUSES"]) and names(knowledge.get("actions", [])) == names(expected["REMEDIED_BY"]),
                 f"도구 반환값 {knowledge}")
    after = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
    logged = [json.loads(line) for line in after[before:]]
    report.check("도구를 부를 때마다 이름 · 입력 · 반환값이 기록(tool_calls.jsonl)에 남는다",
                 [entry.get("name") for entry in logged] == ["get_related", "get_current_value", "get_failure_knowledge"]
                 and all("input" in entry and "output" in entry for entry in logged), f"새로 남은 기록 {len(logged)}줄")
    for question_id in GROUNDED_QUESTIONS:
        answer = load_answer(report, f"{question_id}.json")
        check_grounding(report, question_id, answer)
        report.check(f"{question_id}: 근거가 있어 답했다(status 가 '답변', 근거 1개 이상)", answer["status"] == "답변" and bool(answer["evidence"]),
                     f"status={answer['status']!r}, 근거 {len(answer['evidence'])}개")
    q1 = load_answer(report, "q1.json")
    report.check("q1: 답의 원인이 그래프에 등록된 과열 원인이다", bool(q1["causes"]) and set(q1["causes"]) <= names(expected["CAUSES"]), f"답의 원인 {q1['causes']}")
    q2 = load_answer(report, "q2.json")
    report.check("q2: 현재 값 근거가 연습용 DB 의 값과 같다", any(item.get("value") == db_value for item in q2["evidence"]),
                 f"DB 값 {db_value} / 답의 근거 {q2['evidence']}")


def lab5_3(report: Report) -> None:
    need_file(report, agent_path("tools.py"), "도구")
    unknown = call_tool(report, "no_such_tool", {})
    report.check("없는 도구를 부르면 ok 가 false 이고 이유가 온다", unknown.get("ok") is False and bool(unknown.get("error")), f"반환값 {unknown}")
    incomplete = call_tool(report, "get_current_value", {})
    report.check("필수 입력(설비 번호)을 빼고 부르면 ok 가 false 이고 이유가 온다", incomplete.get("ok") is False and bool(incomplete.get("error")), f"반환값 {incomplete}")
    absent = call_tool(report, "get_current_value", {"asset_id": "CL-02", "kind": "팬 회전수"})
    report.check("측정값이 없으면 도구가 found=false 와 부족한 정보를 돌려준다", absent.get("found") is False and bool(absent.get("missing")), f"반환값 {absent}")
    questions = {question["id"]: question for question in read_kit_json("day5/questions.json")["questions"]}
    for question_id in HOLD_QUESTIONS:
        answer = load_answer(report, f"{question_id}.json")
        check_grounding(report, question_id, answer)
        report.check(f"{question_id}: 근거가 부족해 보류했다(status 가 '보류')", answer["status"] == "보류",
                     f"질문: {questions[question_id]['question']} / status={answer['status']!r}")
        report.check(f"{question_id}: 부족한 정보(missing)를 적었다", bool(answer["missing"]), "무엇이 없어서 보류했는지 적어 주세요.")
        report.check(f"{question_id}: 근거 없이 원인 · 조치를 추천하지 않았다", not answer["causes"] and not answer["actions"],
                     f"원인 {answer['causes']} / 조치 {answer['actions']}")


LABS = {
    "5-1": ("작은 에이전트의 역할·입력·출력 정의하기", lab5_1),
    "5-2": ("조회 도구를 연결해 근거로 답하는 에이전트 만들기", lab5_2),
    "5-3": ("근거가 부족한 질문은 보류하게 만들기", lab5_3),
}
