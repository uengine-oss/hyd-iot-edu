"""학생의 work/agent/tools.py 를 따로 띄운 파이썬에서 불러 도구 하나를 실행한다(확인용).

    python -m labcheck.tool_driver <agent 폴더> specs
    python -m labcheck.tool_driver <agent 폴더> call <도구 이름> '<입력 JSON>'

도구가 콘솔에 찍는 글은 표준 오류로 돌리고, 표준 출력에는 결과 JSON 한 줄만 낸다.
"""
from __future__ import annotations

import contextlib
import importlib
import json
import sys


def main() -> None:
    agent_dir, command, *rest = sys.argv[1:]
    sys.path.insert(0, agent_dir)
    with contextlib.redirect_stdout(sys.stderr):
        tools = importlib.import_module("tools")
        result = tools.TOOLS if command == "specs" else tools.call_tool(rest[0], json.loads(rest[1]))
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
