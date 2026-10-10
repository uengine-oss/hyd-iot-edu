"""판단 MCP 서버. 결정표로 조치를 허용·경고·제외로 판정한다. 설비를 바꾸지 않는다(읽기 전용).

호출이 올 때마다 무엇을 받아 무엇을 돌려줬는지 콘솔에 한 줄씩 남긴다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from engine import DecisionError, evaluate, load_table

TABLE_FILE = Path(__file__).with_name("decision_table.json")
HOST = os.environ.get("JUDGE_MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("JUDGE_MCP_PORT", "18198"))

mcp = FastMCP("cooler-judge")
TABLE = load_table(TABLE_FILE)


def log_call(tool: str, received: Any, returned: Any) -> None:
    print(json.dumps({"tool": tool, "input": received, "output": returned}, ensure_ascii=False), flush=True)


@mcp.tool(annotations={"readOnlyHint": True})
def describe_decision_table() -> dict:
    """결정표가 받는 입력(이름·단위·쓸 수 있는 값), 판정하는 조치, 규칙 전체를 돌려준다. evaluate_actions 를 부르기 전에 입력 이름을 확인할 때 쓴다."""
    log_call("describe_decision_table", {}, {"rules": len(TABLE["rules"])})
    return TABLE


@mcp.tool(annotations={"readOnlyHint": True})
def evaluate_actions(
    temp_c: Annotated[float, Field(description="출구 온도(℃)")],
    fan_state: Annotated[str, Field(description="팬 상태: 정상 · 약함 · 정지 가운데 하나")],
    load_pct: Annotated[float, Field(description="부하(%), 0~100")],
    action_ids: Annotated[list[str] | None, Field(description="판정할 조치 번호 목록(예: ACT-FAN-UP). 비우면 결정표의 모든 조치")] = None,
) -> dict:
    """운전 조건 세 값으로 조치마다 허용 · 경고 · 제외를 판정한다. 적용된 규칙과 이유를 함께 준다. 결정표에 없는 조치나 값이면 오류를 낸다."""
    received = {"temp_c": temp_c, "fan_state": fan_state, "load_pct": load_pct, "action_ids": action_ids}
    try:
        result = evaluate(TABLE, received, action_ids)
    except DecisionError as error:
        log_call("evaluate_actions", received, {"error": str(error)})
        raise ToolError(str(error)) from error
    log_call("evaluate_actions", received, result)
    return result


if __name__ == "__main__":
    mcp.run(transport="http", host=HOST, port=PORT)
