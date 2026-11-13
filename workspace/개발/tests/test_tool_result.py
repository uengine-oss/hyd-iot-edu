"""도구 응답 한도(common/hydcommon/tool_result.py) — 직렬화한 응답이 20,000자를 넘으면 잘라서 성공처럼 주지 않고 까닭과 함께 거절한다.

글자 수는 실제로 에이전트에게 가는 JSON(한국어는 그대로 — ensure_ascii=False) 기준이다. 시계열 · 업무 MCP · dmn-mcp 도구가 같은 함수를 쓴다.
"""
import json
from datetime import datetime, timezone

import pytest

from hydcommon.tool_result import MAX_CHARS, checked


def _text(n, ch='a'):
    """JSON 으로 n 자가 되는 문자열 하나(따옴표 2자 포함)."""
    return ch * (n - 2)


@pytest.mark.parametrize('value', [
    {'rows': [[1, 'HYD-01', 48.2]], 'row_count': 1},
    _text(MAX_CHARS),                     # 경계: 딱 한도
    _text(MAX_CHARS, '가'),               # 한국어 한 글자는 한 자(\uXXXX 여섯 자가 아니다)
    [],
], ids=['보통 결과', '딱 한도', '한국어 딱 한도', '빈 목록'])
def test_한도_안의_응답은_같은_값을_그대로_돌려준다(value):
    assert len(json.dumps(value, ensure_ascii=False)) <= MAX_CHARS
    assert checked(value) is value


@pytest.mark.parametrize('value, size', [
    (_text(MAX_CHARS + 1), MAX_CHARS + 1),
    (_text(MAX_CHARS + 1, '유'), MAX_CHARS + 1),
    ({'cells': [{'note': _text(1000)} for _ in range(25)]}, None),       # 안쪽 칸이 모여 넘는 경우(집계 칸 포함)
], ids=['한 자 넘음', '한국어 한 자 넘음', '안쪽 칸이 모여 넘음'])
def test_한도를_넘는_응답은_크기와_줄일_방법을_말하며_거절한다(value, size):
    actual = len(json.dumps(value, ensure_ascii=False))
    assert actual > MAX_CHARS and (size is None or actual == size)
    with pytest.raises(ValueError) as caught:
        checked(value)
    message = str(caught.value)
    assert f'{actual}자' in message and f'{MAX_CHARS}자' in message and '좁히거나' in message


def test_JSON_이_아닌_값은_글로_바꿔_센다():
    """DB 시각 · 소수 같은 값도 실제로 나갈 글(str)의 길이로 잰다 — 못 세서 통과시키지 않는다."""
    at = datetime(2026, 10, 30, 5, 0, tzinfo=timezone.utc)
    assert checked({'at': at}) == {'at': at}
    big = [at] * 1000                    # '"2026-10-30 05:00:00+00:00"' 27자 × 1000 + 쉼표 · 괄호
    with pytest.raises(ValueError, match='응답 한도'):
        checked(big)
