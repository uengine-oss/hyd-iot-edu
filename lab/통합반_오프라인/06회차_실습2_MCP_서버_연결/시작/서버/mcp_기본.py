"""세 서버가 함께 쓰는 MCP 서버의 뼈대(stdio).

호스트(VS Code)가 이 프로그램을 하위 프로세스로 띄우고, 표준 입력으로 요청을 한 줄에 하나씩 보낸다.
서버는 표준 출력으로 응답을 한 줄에 하나씩 돌려준다. 메시지의 형식은 JSON-RPC 2.0이다.

다루는 요청은 넷이다.
  initialize   연결을 열고 규약의 판과 서버 이름을 알린다
  tools/list   도구의 이름, 설명, 입력 스키마, 읽기 전용 표시를 알린다
  tools/call   도구 하나를 실행하고 결과를 돌려준다
  ping         살아 있는지 답한다

표준 출력은 응답만 지나가는 길이다. 사람이 볼 기록은 표준 오류로 낸다(VS Code의 서버 출력 창에 보인다).
"""
from __future__ import annotations

import json
import sys

규약의_판 = ("2025-06-18", "2025-03-26", "2024-11-05")


class 도구_오류(Exception):
    """도구가 일을 하지 못했을 때 낸다. 호출한 쪽에는 isError가 true인 결과로 돌아간다."""


class 서버:
    def __init__(self, 이름: str, 판: str):
        self.이름, self.판, self.도구들 = 이름, 판, {}

    def 도구(self, 이름: str, 설명: str, 인수: dict | None = None, 필수: tuple = (), 읽기_전용: bool = True):
        """도구 하나를 등록한다. 인수는 {이름: {"type": …, "description": …}} 꼴이다."""
        def 등록(함수):
            self.도구들[이름] = {
                "함수": 함수,
                "정의": {
                    "name": 이름,
                    "description": 설명,
                    "inputSchema": {"type": "object", "properties": 인수 or {}, "required": list(필수)},
                    "annotations": {"readOnlyHint": 읽기_전용},
                },
            }
            return 함수
        return 등록

    # ── 요청 하나를 처리한다
    def _처리(self, 요청: dict):
        방법, 값 = 요청.get("method"), 요청.get("params") or {}
        if 방법 == "initialize":
            판 = 값.get("protocolVersion")
            return {"protocolVersion": 판 if 판 in 규약의_판 else 규약의_판[0],
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.이름, "version": self.판}}
        if 방법 == "ping":
            return {}
        if 방법 == "tools/list":
            return {"tools": [d["정의"] for d in self.도구들.values()]}
        if 방법 == "tools/call":
            return self._호출(값.get("name"), 값.get("arguments") or {})
        raise LookupError(f"Method not found: {방법}")

    def _호출(self, 이름, 인수: dict):
        def 결과(글: str, 실패: bool):
            기록(f"호출 {이름} {json.dumps(인수, ensure_ascii=False)} → {'실패' if 실패 else '성공'}")
            return {"content": [{"type": "text", "text": 글}], "isError": 실패}
        if 이름 not in self.도구들:
            return 결과(f"이 서버({self.이름})에는 {이름} 이라는 도구가 없다. 있는 도구: {', '.join(self.도구들)}", True)
        d = self.도구들[이름]
        스키마 = d["정의"]["inputSchema"]
        빠진_것 = [k for k in 스키마["required"] if k not in 인수 or 인수[k] in (None, "")]
        if 빠진_것:
            return 결과(f"입력 오류: 필수 인수가 없다 — {', '.join(빠진_것)}", True)
        모르는_것 = [k for k in 인수 if k not in 스키마["properties"]]
        if 모르는_것:
            return 결과(f"입력 오류: 이 도구가 받지 않는 인수다 — {', '.join(모르는_것)}. 받는 인수: {', '.join(스키마['properties']) or '없음'}", True)
        try:
            return 결과(str(d["함수"](**인수)), False)
        except 도구_오류 as e:
            return 결과(str(e), True)
        except Exception as e:  # 도구 안에서 생긴 예상 밖의 오류도 실패로 돌려준다
            return 결과(f"도구 실행 중 오류: {type(e).__name__}: {e}", True)

    # ── 표준 입력을 한 줄씩 읽어 답한다
    def 실행(self):
        기록(f"서버 {self.이름} {self.판} 시작. 도구 {len(self.도구들)}개: {', '.join(self.도구들)}")
        for 줄 in sys.stdin.buffer:
            줄 = 줄.strip()
            if not 줄:
                continue
            try:
                요청 = json.loads(줄.decode("utf-8"))
            except ValueError:
                self._보내기({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
                continue
            if "id" not in 요청:          # 알림(notifications/initialized 등)에는 답하지 않는다
                continue
            try:
                self._보내기({"jsonrpc": "2.0", "id": 요청["id"], "result": self._처리(요청)})
            except LookupError as e:
                self._보내기({"jsonrpc": "2.0", "id": 요청["id"], "error": {"code": -32601, "message": str(e)}})
            except Exception as e:
                self._보내기({"jsonrpc": "2.0", "id": 요청["id"], "error": {"code": -32603, "message": f"{type(e).__name__}: {e}"}})

    @staticmethod
    def _보내기(응답: dict):
        sys.stdout.buffer.write(json.dumps(응답, ensure_ascii=False).encode("utf-8") + b"\n")
        sys.stdout.buffer.flush()


def 기록(글: str):
    sys.stderr.buffer.write((글 + "\n").encode("utf-8"))
    sys.stderr.buffer.flush()
