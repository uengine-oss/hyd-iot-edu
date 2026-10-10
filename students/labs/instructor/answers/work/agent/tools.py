"""에이전트가 쓰는 조회 도구. 2일차·4일차에 만든 조회 기능을 도구로 감싼다.

도구를 부를 때마다 이름·입력·반환값을 콘솔에 찍고 tool_calls.jsonl 에 한 줄씩 남긴다.
도구는 읽기만 한다. 실패해도 예외를 밖으로 던지지 않고 {"ok": false, "error": ...} 를 돌려준다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

WORK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK_DIR))

from find_related import find_related  # noqa: E402
from lookup import current_status, failure_knowledge  # noqa: E402

CALL_LOG = Path(__file__).with_name("tool_calls.jsonl")


def tool_spec(name: str, description: str, properties: dict[str, dict], required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
    }


ASSET_ID = {"type": "string", "description": "설비 번호. 예: CL-01"}

TOOLS = [
    tool_spec("get_related", "설비 번호로 그 설비에 붙은 센서와 부품 목록을 찾는다. 어떤 부품이 있는지 확인할 때 쓴다.",
              {"asset_id": ASSET_ID}, ["asset_id"]),
    tool_spec("get_current_value", "연습용 DB 에서 설비의 현재 측정값을 읽고, 그 값이 넘긴 판정 기준과 이어진 원인·조치를 출처와 함께 돌려준다.",
              {"asset_id": ASSET_ID, "kind": {"type": "string", "description": "재는 것. 예: 출구 온도, 유량, 팬 회전수"}},
              ["asset_id", "kind"]),
    tool_spec("get_failure_knowledge", "설비에 등록된 고장 하나의 증상·원인·조치를 매뉴얼 출처와 함께 돌려준다.",
              {"asset_id": ASSET_ID, "failure_name": {"type": "string", "description": "고장 이름. 예: 과열, 누수"}},
              ["asset_id", "failure_name"]),
]

HANDLERS: dict[str, Callable[..., dict]] = {
    "get_related": lambda asset_id: find_related(asset_id=asset_id),
    "get_current_value": lambda asset_id, kind: current_status(asset_id, kind),
    "get_failure_knowledge": lambda asset_id, failure_name: failure_knowledge(asset_id, failure_name),
}
SPECS_BY_NAME = {spec["name"]: spec for spec in TOOLS}


def run_tool(name: str, arguments: dict[str, Any]) -> dict:
    if name not in HANDLERS:
        return {"ok": False, "error": f"없는 도구입니다: {name}. 쓸 수 있는 도구: {list(HANDLERS)}"}
    schema = SPECS_BY_NAME[name]["input_schema"]
    missing = [key for key in schema["required"] if not arguments.get(key)]
    unknown = [key for key in arguments if key not in schema["properties"]]
    if missing or unknown:
        return {"ok": False, "error": f"도구 {name} 의 입력이 맞지 않습니다. 빠진 값: {missing}, 모르는 값: {unknown}"}
    try:
        return {"ok": True, **HANDLERS[name](**arguments)}
    except Exception as error:  # 도구 실패는 에이전트가 읽을 수 있는 결과로 돌려준다
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


def call_tool(name: str, arguments: dict[str, Any]) -> dict:
    result = run_tool(name, arguments)
    record = {"name": name, "input": arguments, "output": result}
    print(f"[도구 호출] {name} 입력={json.dumps(arguments, ensure_ascii=False)}")
    print(f"[도구 반환] {json.dumps(result, ensure_ascii=False)}")
    with CALL_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return result
