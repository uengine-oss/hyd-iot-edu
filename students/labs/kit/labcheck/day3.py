"""3일차 확인: 결정표와 평가 함수(3-1) · 경계값과 겹침(3-2) · 조치가 지표에 주는 영향(3-3)."""
from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

from labcheck import graphstate
from labcheck.core import Report, ids, need_file, read_json, run_json, run_script, work_path
from labcheck.facts import read_csv, read_kit_json
from labcheck.schemafile import check_classes, check_constraints, check_relationships, load_schema
from labkit.graph import graph_session
from labkit.settings import KIT_ROOT

RESULTS = {"허용", "경고", "제외"}
PREPARED_INPUTS = {"정상값": "normal.json", "임계값 바로 위": "just_above.json", "두 조건 겹침": "overlap.json"}
UNKNOWN_ACTION_ID = "ACT-NONE"
ESTIMATE_MARKS = ("15 %", "15 ℃")


def expected_decisions() -> dict:
    return read_kit_json("labcheck/expected/decision.json")


def evaluate_values(report: Report, values: dict) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        json.dump(values, handle, ensure_ascii=False)
    try:
        return run_json(report, work_path("evaluate.py"), "--input", handle.name)
    finally:
        Path(handle.name).unlink()


def summary(result: dict) -> dict:
    return {action: outcome.get("result") for action, outcome in result.get("actions", {}).items()}


def lab3_1(report: Report) -> None:
    expected = expected_decisions()
    table = read_json(report, work_path("decision_table.json"), "결정표")
    need_file(report, work_path("evaluate.py"), "평가 프로그램")
    rules = {rule.get("id"): rule for rule in table.get("rules", [])} if isinstance(table, dict) else {}
    report.equal("결정표에 판단 기준의 규칙이 모두 있다", set(rules), set(expected["rules"]))
    for rule_id, (action, result) in expected["rules"].items():
        rule = rules.get(rule_id, {})
        report.check(f"규칙 {rule_id} 의 조치와 결과가 판단 기준과 같다",
                     rule.get("action") == action and rule.get("result") == result and bool(rule.get("when")),
                     f"결정표: 조치 {rule.get('action')}, 결과 {rule.get('result')}, 조건 {rule.get('when')} / 기준: {action}, {result}")
    normal = str(KIT_ROOT / "day3" / "inputs" / "normal.json")
    first = run_json(report, work_path("evaluate.py"), "--input", normal)
    report.equal("조치 세 가지의 결과가 모두 나온다", set(first.get("actions", {})), set(expected["actions"]))
    complete = all(outcome.get("result") in RESULTS and outcome.get("applied_rule") and isinstance(outcome.get("matched_rules"), list)
                   for outcome in first.get("actions", {}).values())
    report.check("조치마다 result(허용·경고·제외) · applied_rule · matched_rules 가 있다", complete, f"나온 값 {first.get('actions')}")
    report.equal("같은 입력을 두 번 넣으면 같은 결과가 나온다", run_json(report, work_path("evaluate.py"), "--input", normal), first)


def lab3_2(report: Report) -> None:
    expected = expected_decisions()
    need_file(report, work_path("evaluate.py"), "평가 프로그램")
    cases = {case["name"]: case for case in expected["cases"]}
    for label, filename in PREPARED_INPUTS.items():
        values = read_kit_json(f"day3/inputs/{filename}")
        case = cases[filename]
        result = evaluate_values(report, values)
        report.equal(f"준비된 입력 '{label}' 의 결과가 판단 기준과 같다", summary(result), case["results"])
        applied = {action: outcome.get("applied_rule") for action, outcome in result.get("actions", {}).items()}
        report.equal(f"준비된 입력 '{label}' 에 적용된 규칙이 맞다", applied, case["applied"])
    overlap = evaluate_values(report, read_kit_json("day3/inputs/overlap.json"))
    matched = set(overlap.get("actions", {}).get("ACT-FIN-CLEAN", {}).get("matched_rules", []))
    report.check("겹침 입력에서 핀 세척에 맞은 규칙 두 개(C1 · C2)가 모두 보인다", matched == {"C1", "C2"}, f"matched_rules: {sorted(matched)}")
    wrong = []
    for case in expected["boundaries"]:
        got = summary(evaluate_values(report, case["input"]))
        if got != case["results"]:
            wrong.append({"입력": case["input"], "나온 값": got, "기대": case["results"]})
    report.check(f"경계값 {len(expected['boundaries'])}가지(45 · 60 ℃, 30 · 80 % 의 바로 아래·위)가 모두 맞다", not wrong,
                 f"틀린 경우 {len(wrong)}개. 첫 번째: {wrong[:1]}")
    for label, values in expected["invalid_inputs"].items():
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
            json.dump(values, handle, ensure_ascii=False)
        done = run_script(work_path("evaluate.py"), "--input", handle.name)
        Path(handle.name).unlink()
        report.check(f"기준에 없는 입력({label})은 결과를 지어내지 않고 오류로 끝난다", done.returncode != 0,
                     f"종료 코드 0 으로 결과를 냈습니다: {done.stdout.strip()[:200]}")


def lab3_3(report: Report) -> None:
    schema = load_schema(report)
    check_classes(report, schema, {"Action": ["id", "name"], "Measure": ["id", "name"]})
    check_relationships(report, schema, [("AFFECTS", "Action", "Measure")])
    effects = read_csv("day3/data/action_effects.csv")
    expected = sorted((row["action_id"], row["measure_id"], row["effect"]) for row in effects)
    with graph_session() as session:
        check_constraints(report, schema, graphstate.unique_constraints(session), ["Action", "Measure"])
        action_ids = ids(graphstate.nodes(session, "Action"))
        report.check("조치 노드가 모두 있다", {row["action_id"] for row in read_csv("day3/data/actions.csv")} <= action_ids, f"그래프의 조치: {sorted(action_ids)}")
        report.equal("성과 지표 노드가 CSV 와 같다", ids(graphstate.nodes(session, "Measure")),
                     {row["measure_id"] for row in read_csv("day3/data/measures.csv")})
        found = graphstate.relations(session, "AFFECTS")
    triples = sorted((row["from_id"], row["to_id"], row["props"].get("effect")) for row in found)
    repeated = [pair for pair, count in Counter(graphstate.pairs(found)).items() if count > 1]
    report.check("AFFECTS 관계가 같은 쌍에 두 번 없다", not repeated, f"겹친 관계: {repeated}")
    report.equal("조치 → 지표 관계와 방향(긍정·부정)이 CSV 와 같다", sorted(set(triples)), expected)
    report.check("관계마다 이유(basis)가 적혀 있다", all(row["props"].get("basis") for row in found), "basis 가 빈 관계가 있습니다.")
    guessed = [(row["from_id"], row["to_id"], key) for row in found for key, value in row["props"].items()
               if isinstance(value, (int, float)) and not isinstance(value, bool)
               or isinstance(value, str) and any(mark in value for mark in ESTIMATE_MARKS)]
    report.check("계산하지 않은 추정 숫자를 관계에 사실처럼 저장하지 않았다", not guessed,
                 f"추정 숫자가 들어간 곳(조치, 지표, 속성): {guessed}. note 칸의 숫자는 확정값이 아닙니다.")
    finder = work_path("action_effects.py")
    need_file(report, finder, "영향 조회 프로그램")
    for action_id in sorted({row["action_id"] for row in effects}):
        result = run_json(report, finder, "--action-id", action_id)
        for side, effect in (("positive", "긍정"), ("negative", "부정")):
            report.equal(f"{action_id}: {effect} 영향을 받는 지표가 함께 나온다", ids(result.get(side, []), "measure_id"),
                         {row["measure_id"] for row in effects if row["action_id"] == action_id and row["effect"] == effect})
    unknown = run_json(report, finder, "--action-id", UNKNOWN_ACTION_ID)
    report.check("없는 조치를 물으면 found 가 false 이고 빈 결과다",
                 unknown.get("found") is False and not unknown.get("positive") and not unknown.get("negative"), f"나온 값 {unknown}")


LABS = {
    "3-1": ("조치를 허용·경고·제외하는 결정표 만들기", lab3_1),
    "3-2": ("조건을 바꿔 규칙 결과가 달라지는지 확인하기", lab3_2),
    "3-3": ("조치가 지표에 미치는 영향 관계 만들기", lab3_3),
}
