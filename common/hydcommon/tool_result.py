"""Bound the actual serialized agent response, including nested aggregate cells."""
import json

MAX_CHARS = 20000


def checked(value):
    size = len(json.dumps(value, ensure_ascii=False, default=str))
    if size > MAX_CHARS:
        raise ValueError(
            f'조회 결과 {size}자가 응답 한도 {MAX_CHARS}자를 넘었습니다. '
            '일부를 전체 결과로 반환하지 않습니다. 필요한 열·조건·시간 범위를 좁히거나 '
            'DB에서 COUNT/MIN/MAX 등으로 집계하세요. 시계열은 step을 늘리세요.')
    return value


#: 도구 응답 봉투 {"result": "error", "error_kind": …} 의 종류 하나 — 쓸 값을 원천에서 아직 받지 못했다(아무것도 쓰지 않았고, 같은 인자로
#: 잠시 뒤 다시 부르면 된다). 주는 곳: 판단 도구 서버(dmn_mcp/tools.py), 다시 부르는 곳: 재생 워커(worker/ai_replay.py).
UNAVAILABLE = 'UNAVAILABLE'
