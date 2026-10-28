"""점검 메모 조회 MCP 서버의 골격 — 도구 함수의 본문은 직접 구현합니다.

실행 방법
    python 점검메모_서버.py --folder <점검 메모 폴더>

    --folder <점검 메모 폴더>   이 서버가 읽을 폴더(예: 코드/업무자료/점검). 꼭 적습니다.
                                도구는 이 폴더 안의 글 파일만 읽습니다. 다른 폴더는 호출로 고를 수 없습니다.

이 서버의 도구는 읽기만 합니다. 파일을 고치거나 만드는 도구를 두지 않습니다.
요청과 응답의 처리(initialize · tools/list · tools/call)는 mcp_기본.py가 합니다. 여기서는 도구만 정합니다.

지금 상태
    서버는 뜨고 tools/list에 도구 하나가 보입니다. 그 도구를 부르면 「아직 구현하지 않은 도구」 오류를 돌려줍니다.
    도구의 이름 · 설명 · 입력 스키마는 바꿔도 됩니다. 바꾸면 무엇을 왜 바꿨는지 기록합니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

from mcp_기본 import 기록, 도구_오류, 서버

인수들 = sys.argv[1:]
if "--folder" not in 인수들 or 인수들.index("--folder") + 1 >= len(인수들):
    기록("시작하지 못함: --folder <점검 메모 폴더> 를 적어야 한다.")
    sys.exit(2)
폴더 = Path(인수들[인수들.index("--folder") + 1]).expanduser().resolve()
if not 폴더.is_dir():
    기록(f"시작하지 못함: 점검 메모 폴더가 없다 — {폴더}")
    sys.exit(2)

s = 서버("inspection-notes", "0.1.0")


@s.도구(
    "find_inspection_notes",
    "점검 메모와 점검 기록에서 설비 하나에 관한 내용을 찾아 근거(파일 · 줄)와 함께 돌려준다.",
    {
        "equipment": {"type": "string", "description": "찾을 설비. 메모에 적힌 이름 그대로(예: 3호기)"},
        "keyword": {"type": "string", "description": "함께 찾을 낱말. 없으면 설비만으로 찾는다"},
    },
    필수=("equipment",),
)
def find_inspection_notes(equipment: str, keyword: str | None = None) -> str:
    """폴더 안의 점검 메모 · 점검 기록에서 equipment(와 keyword)에 관한 내용을 찾아 글로 돌려준다.

    직접 정할 것: 무엇을 찾아 어떤 모양으로 돌려줄지(줄 · 표의 행 · 「남은 일」 같은 절),
    결과마다 붙일 근거(파일 이름 · 줄 번호), 찾은 것이 없을 때와 읽지 못했을 때를 서로 다른 결과로 돌려주는 방법.
    읽지 못했을 때는 도구_오류를 내서 호출한 쪽이 실패로 받게 한다. 실패를 빈 결과로 바꾸지 않는다.
    """
    raise 도구_오류("아직 구현하지 않은 도구입니다: find_inspection_notes")


if __name__ == "__main__":
    기록(f"읽을 폴더: {폴더}")
    s.실행()
