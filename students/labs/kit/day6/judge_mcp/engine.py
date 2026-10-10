"""결정표 평가. 표(JSON)와 입력 세 값을 받아 조치마다 허용·경고·제외를 낸다."""
from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Any

OPERATORS = {"==": operator.eq, ">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


class DecisionError(ValueError):
    """입력이 결정표의 약속과 다르거나, 맞는 규칙이 하나도 없을 때."""


def load_table(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_inputs(table: dict[str, Any], values: dict[str, Any]) -> None:
    for name, spec in table["inputs"].items():
        if name not in values or values[name] is None:
            raise DecisionError(f"입력 '{name}'({spec['label']}) 이 없습니다.")
        value = values[name]
        if spec["type"] == "enum":
            if value not in spec["values"]:
                raise DecisionError(f"입력 '{name}' 의 값 '{value}' 는 결정표에 없습니다. 쓸 수 있는 값: {spec['values']}")
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DecisionError(f"입력 '{name}' 은 숫자여야 합니다(받은 값 {value!r}).")
        if "min" in spec and value < spec["min"] or "max" in spec and value > spec["max"]:
            raise DecisionError(f"입력 '{name}' 의 값 {value} 가 범위({spec.get('min')}~{spec.get('max')})를 벗어났습니다.")


def rule_matches(rule: dict[str, Any], values: dict[str, Any]) -> bool:
    return all(OPERATORS[test["op"]](values[test["input"]], test["value"]) for test in rule["when"])


def evaluate(table: dict[str, Any], values: dict[str, Any], action_ids: list[str] | None = None) -> dict[str, Any]:
    validate_inputs(table, values)
    wanted = list(table["actions"]) if action_ids is None else action_ids
    unknown = [action for action in wanted if action not in table["actions"]]
    if unknown:
        raise DecisionError(f"결정표에 없는 조치입니다: {unknown}. 있는 조치: {list(table['actions'])}")
    priority = table["priority"]
    results: dict[str, Any] = {}
    for action in wanted:
        matched = [rule for rule in table["rules"] if rule["action"] == action and rule_matches(rule, values)]
        if not matched:
            raise DecisionError(f"조치 '{action}' 에 맞는 규칙이 없습니다(입력 {values}). 결정표에 빠진 조건이 있습니다.")
        applied = min(matched, key=lambda rule: priority.index(rule["result"]))
        results[action] = {
            "name": table["actions"][action],
            "result": applied["result"],
            "applied_rule": applied["id"],
            "matched_rules": [rule["id"] for rule in matched],
            "reason": applied["reason"],
        }
    return {"input": {name: values[name] for name in table["inputs"]}, "actions": results}
