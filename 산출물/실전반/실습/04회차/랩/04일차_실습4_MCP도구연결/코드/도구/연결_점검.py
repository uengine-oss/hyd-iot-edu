"""`.vscode/mcp.json`에 적힌 서버를 하나씩 직접 띄워 연결해 보고, 서버가 내주는 도구 목록을 그대로 보여 준다.

    python 코드/도구/연결_점검.py                          적힌 서버 모두: 연결(initialize) → 도구 목록(tools/list)
    python 코드/도구/연결_점검.py time                     그 서버만
    python 코드/도구/연결_점검.py --호출 time get_current_time timezone=Asia/Seoul
                                                           도구 하나를 직접 부르고(tools/call) 주고받은 메시지를 그대로 보여 준다
    python 코드/도구/연결_점검.py --호출 git git_status    인수가 없는 도구

설정 파일은 랩 폴더(START.md가 있는 폴더, VS Code로 연 폴더)의 `.vscode/mcp.json`이다. `${workspaceFolder}`는 그 랩 폴더로 푼다.
stdio 서버만 띄운다. http 서버(예: Notion)는 「확인 안 함」으로 적고 연결 성공으로도 실패로도 세지 않는다.
그 서버는 VS Code 채팅의 도구 목록과 호출 기록으로 확인한다.

AI를 거치지 않는다. 채팅에서 본 것이 서버가 실제로 돌려준 것과 같은지 견줄 때 쓴다.
인수는 `이름=값`으로 적는다. 값이 숫자이면 숫자로 넘긴다.
"""
from __future__ import annotations

import json
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path

작업_폴더 = Path(__file__).resolve().parents[2]  # 랩 폴더(코드/도구/연결_점검.py의 두 단계 위)
설정_파일 = 작업_폴더 / ".vscode" / "mcp.json"
기다림 = 15  # 초


class 연결_실패(Exception):
    pass


class 연결:
    """서버 하나를 하위 프로세스로 띄우고 표준 입출력으로 메시지를 주고받는다."""

    def __init__(self, 이름: str, 항목: dict):
        if 항목.get("type", "stdio") != "stdio":
            raise 연결_실패(f"type 이 stdio 가 아니다({항목.get('type')}). 이 프로그램은 stdio 서버만 띄운다.")
        if not 항목.get("command"):
            raise 연결_실패("command 가 없다.")
        풀기 = lambda 글: str(글).replace("${workspaceFolder}", str(작업_폴더))
        명령 = 풀기(항목["command"])
        if shutil.which(명령) is None:
            if 명령 in ("python", "python3", "py"):
                명령 = sys.executable       # 이 프로그램을 실행한 파이썬으로 대신 띄운다
            else:
                raise 연결_실패(f"실행할 프로그램을 찾지 못했다: {명령}")
        self.명령줄 = [명령] + [풀기(a) for a in 항목.get("args", [])]
        try:
            self.p = subprocess.Popen(self.명령줄, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      cwd=풀기(항목.get("cwd", "${workspaceFolder}")))
        except OSError as e:
            raise 연결_실패(f"서버를 띄우지 못했다: {e}")
        self.받은_것, self.서버_기록, self.번호 = queue.Queue(), [], 0
        threading.Thread(target=lambda: [self.받은_것.put(줄) for 줄 in self.p.stdout], daemon=True).start()
        self.기록_읽기 = threading.Thread(target=lambda: [self.서버_기록.append(줄.decode("utf-8", "replace").rstrip()) for 줄 in self.p.stderr], daemon=True)
        self.기록_읽기.start()

    def 요청(self, 방법: str, 값: dict | None = None) -> tuple[dict, dict]:
        self.번호 += 1
        보낸_것 = {"jsonrpc": "2.0", "id": self.번호, "method": 방법, "params": 값 or {}}
        self._쓰기(보낸_것)
        try:
            return 보낸_것, json.loads(self.받은_것.get(timeout=기다림).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise 연결_실패("서버 응답을 JSON으로 읽지 못했다: " + str(e))
        except queue.Empty:
            끝 = self.p.poll()
            if 끝 is not None:
                self.기록_읽기.join(timeout=2)  # 꺼진 서버가 남긴 말을 마저 읽는다
            까닭 = f"서버가 꺼졌다(종료 코드 {끝})" if 끝 is not None else f"{기다림}초 안에 답이 없다"
            raise 연결_실패(까닭 + ("\n      서버가 남긴 말: " + " / ".join(self.서버_기록[-3:]) if self.서버_기록 else ""))

    def 알림(self, 방법: str):
        self._쓰기({"jsonrpc": "2.0", "method": 방법})

    def _쓰기(self, 메시지: dict):
        try:
            self.p.stdin.write(json.dumps(메시지, ensure_ascii=False).encode("utf-8") + b"\n")
            self.p.stdin.flush()
        except OSError:
            pass  # 서버가 이미 꺼졌다. 요청() 이 까닭을 알린다.

    def 열기(self) -> dict:
        _, 답 = self.요청("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                       "clientInfo": {"name": "연결_점검", "version": "1.0.0"}})
        if "error" in 답 or not isinstance(답.get("result"), dict):
            raise 연결_실패("초기화 오류: " + json.dumps(답, ensure_ascii=False))
        if 답["result"].get("protocolVersion") != "2025-06-18":
            raise 연결_실패("지원하지 않는 규약 판: " + str(답["result"].get("protocolVersion")))
        self.알림("notifications/initialized")
        return 답["result"]

    def 닫기(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=3)
        except Exception:
            self.p.kill()


def 설정_읽기() -> dict:
    if not 설정_파일.is_file():
        sys.exit(f"설정 파일이 없다: .vscode/mcp.json")
    try:
        return json.loads(설정_파일.read_text(encoding="utf-8")).get("servers", {})
    except ValueError as e:
        sys.exit(f".vscode/mcp.json 을 읽지 못했다(JSON 문법 오류): {e}")


def 보이기(명령줄: list) -> str:
    return " ".join(str(a).replace(str(작업_폴더), "${workspaceFolder}") for a in 명령줄[1:])


def 목록(서버들: dict, 고른_것: list) -> int:
    if not 서버들:
        print("연결된 서버가 없다. .vscode/mcp.json 의 servers 가 비어 있다.")
        return 1
    실패 = 0
    for 이름, 항목 in 서버들.items():
        if 고른_것 and 이름 not in 고른_것:
            continue
        print(f"\n■ {이름}")
        if 항목.get("type") == "http":
            print(f"  확인 안 함: http 서버({항목.get('url')})는 이 프로그램이 띄우지 않는다. VS Code 채팅의 도구 목록과 호출 기록으로 확인한다.")
            continue
        c = None
        try:
            c = 연결(이름, 항목)
            print(f"  실행: {항목.get('command')} {보이기(c.명령줄)}")
            정보 = c.열기()
            _, 답 = c.요청("tools/list")
            if "error" in 답 or not isinstance(답.get("result", {}).get("tools"), list):
                raise 연결_실패("도구 목록 오류: " + json.dumps(답, ensure_ascii=False))
            도구들 = 답["result"]["tools"]
        except 연결_실패 as e:
            실패 += 1
            print(f"  연결 실패: {e}")
            continue
        finally:
            if c is not None:
                c.닫기()
        print(f"  연결됨: 서버 이름 {정보['serverInfo']['name']} · 판 {정보['serverInfo']['version']} · 규약의 판 {정보['protocolVersion']}")
        print(f"  도구 {len(도구들)}개")
        print(f"    {'도구':<26}{'읽기 전용':<10}필수 인수 (선택 인수)")
        for t in 도구들:
            스키마 = t.get("inputSchema", {})
            필수 = 스키마.get("required", [])
            선택 = [k for k in 스키마.get("properties", {}) if k not in 필수]
            읽기 = t.get("annotations", {}).get("readOnlyHint")
            print(f"    {t['name']:<26}{'true' if 읽기 else 'false':<13}{', '.join(필수) or '없음'}" + (f" ({', '.join(선택)})" if 선택 else ""))
    return 1 if 실패 else 0


def 호출(서버들: dict, 이름: str, 도구: str, 인수_글: list) -> int:
    if 이름 not in 서버들:
        print(f"서버 미연결: .vscode/mcp.json 에 {이름} 이라는 서버가 없다. 적혀 있는 서버: {', '.join(서버들) or '없음'}")
        return 1
    인수 = {}
    for 글 in 인수_글:
        if "=" not in 글:
            sys.exit(f"인수는 이름=값 으로 적는다: {글}")
        k, v = 글.split("=", 1)
        인수[k] = int(v) if v.lstrip("-").isdigit() else v
    c = None
    try:
        c = 연결(이름, 서버들[이름])
        c.열기()
        보낸_것, 답 = c.요청("tools/call", {"name": 도구, "arguments": 인수})
    except 연결_실패 as e:
        print(f"연결 실패: {e}")
        return 1
    finally:
        if c is not None:
            c.닫기()
    print("보낸 요청 (tools/call)")
    print(json.dumps(보낸_것, ensure_ascii=False, indent=2))
    print("\n받은 응답")
    print(json.dumps(답, ensure_ascii=False, indent=2))
    결과 = 답.get("result", {})
    if "content" in 결과:
        print(f"\n결과의 글 (isError: {str(결과.get('isError', False)).lower()})")
        print("\n".join(c.get("text", "") for c in 결과["content"]))
    return 1 if "error" in 답 or 결과.get("isError", False) else 0


def main() -> int:
    for 길 in (sys.stdout, sys.stderr):
        if hasattr(길, "reconfigure"):
            길.reconfigure(encoding="utf-8")
    인수들 = sys.argv[1:]
    서버들 = 설정_읽기()
    if 인수들 and 인수들[0] == "--호출":
        if len(인수들) < 3:
            sys.exit("쓰는 법: python 코드/도구/연결_점검.py --호출 <서버> <도구> [이름=값 …]")
        return 호출(서버들, 인수들[1], 인수들[2], 인수들[3:])
    return 목록(서버들, 인수들)


if __name__ == "__main__":
    sys.exit(main())
