"""결정표(decision_table.json)로 조치마다 허용·경고·제외를 판정한다.

    python work/evaluate.py --input day3/inputs/normal.json
"""
from __future__ import annotations

import argparse
import json
import operator
import sys
from pathlib import Path

TABLE_FILE = Path(__file__).with_name("decision_table.json")
OPERATORS = {"==": operator.eq, ">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


class DecisionError(ValueError):
    pass


def check_inputs(table: dict, values: dict) -> None:
    for name, spec in table["inputs"].items():
        if values.get(name) is None:
            raise DecisionError(f"입력 '{name}'({spec['label']}) 이 없습니다.")
        value = values[name]
        if spec["type"] == "enum":
            if value not in spec["values"]:
                raise DecisionError(f"'{name}' 의 값 '{value}' 는 기준에 없습니다. 쓸 수 있는 값: {spec['values']}")
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DecisionError(f"'{name}' 은 숫자여야 합니다(받은 값 {value!r}).")
        elif not spec.get("min", value) <= value <= spec.get("max", value):
            raise DecisionError(f"'{name}' 의 값 {value} 가 범위를 벗어났습니다.")


def evaluate(table: dict, values: dict) -> dict:
    check_inputs(table, values)
    order = table["priority"]
    actions = {}
    for action, name in table["actions"].items():
        matched = [
            rule for rule in table["rules"]
            if rule["action"] == action
            and all(OPERATORS[test["op"]](values[test["input"]], test["value"]) for test in rule["when"])
        ]
        if not matched:
            raise DecisionError(f"조치 '{action}' 에 맞는 규칙이 없습니다(입력 {values}).")
        applied = min(matched, key=lambda rule: order.index(rule["result"]))
        actions[action] = {
            "name": name,
            "result": applied["result"],
            "applied_rule": applied["id"],
            "matched_rules": [rule["id"] for rule in matched],
            "reason": applied["reason"],
        }
    return {"input": {name: values[name] for name in table["inputs"]}, "actions": actions}


def main() -> None:
    parser = argparse.ArgumentParser(description="결정표 평가")
    parser.add_argument("--input", required=True, help="temp_c · fan_state · load_pct 가 든 JSON 파일")
    args = parser.parse_args()
    table = json.loads(TABLE_FILE.read_text(encoding="utf-8"))
    values = json.loads(Path(args.input).read_text(encoding="utf-8"))
    try:
        result = evaluate(table, values)
    except DecisionError as error:
        print(f"판정할 수 없습니다: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
