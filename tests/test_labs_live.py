"""랩용 실행 환경(연습용 그래프 · DB · 판단 MCP)을 실제로 쓰는 시험. LAB_LIVE=1 일 때만 돈다.

    cd students/labs/kit && docker compose up -d --wait      # .env 필요(kit/README.md)
    LAB_LIVE=1 pytest tests/test_labs_live.py

연습용 그래프를 비우고 시작한다. HYD 스택은 쓰지 않는다.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from test_labs_support import INSTRUCTOR, LABS

pytestmark = pytest.mark.skipif(os.environ.get("LAB_LIVE") != "1", reason="랩용 실행 환경이 필요하다(LAB_LIVE=1)")
LIVE_TIMEOUT_SECONDS = 900


def run_tool(name: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(INSTRUCTOR / name)], cwd=LABS, capture_output=True, text=True, timeout=LIVE_TIMEOUT_SECONDS)


def test_answers_complete_every_lab_from_an_empty_graph():
    done = run_tool("run_all.py")
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    assert "완주 결과: 21/21 랩 통과" in done.stdout


def test_every_deliberately_wrong_result_is_caught_and_the_graph_is_restored():
    done = run_tool("wrong_results.py")
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    assert "놓침" not in done.stdout and "되돌린 뒤 전체 확인: 모두 통과" in done.stdout
