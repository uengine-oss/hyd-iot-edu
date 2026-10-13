"""Git MCP 서버 — 저장소 하나의 변경 이력을 읽는 도구를 내준다.

실행 방법
    python 깃_서버.py --repository <저장소 폴더>

    --repository <저장소 폴더>   이 서버가 들여다볼 Git 저장소(안에 .git 이 있는 폴더). 꼭 적는다.
                                 도구는 이 저장소만 본다. 호출할 때 다른 저장소를 고를 수 없다.

이 서버의 도구는 모두 읽기만 한다. 커밋하거나 되돌리는 도구는 없다.
이 PC에 git 이 깔려 있어야 한다.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from mcp_기본 import 기록, 도구_오류, 서버

인수들 = sys.argv[1:]
if "--repository" not in 인수들 or 인수들.index("--repository") + 1 >= len(인수들):
    기록("시작하지 못함: --repository <저장소 폴더> 를 적어야 한다.")
    sys.exit(2)
저장소 = Path(인수들[인수들.index("--repository") + 1]).expanduser().resolve()
if not 저장소.is_dir():
    기록(f"시작하지 못함: 저장소 폴더가 없다 — {저장소}")
    sys.exit(2)

s = 서버("git", "1.0.0")


def git(*명령: str) -> str:
    if not (저장소 / ".git").exists():
        raise 도구_오류(f"Git 저장소가 아니다: {저장소.name} 폴더에 .git 이 없다. 서버의 --repository 설정을 확인한다.")
    try:
        r = subprocess.run(["git", "-C", str(저장소), "-c", "core.quotepath=false", "--no-pager", *명령],
                           capture_output=True, timeout=20)
    except FileNotFoundError:
        raise 도구_오류("git 을 실행하지 못했다. 이 PC에 git 이 깔려 있는지 확인한다.")
    except subprocess.TimeoutExpired:
        raise 도구_오류("git 이 20초 안에 답하지 않았다.")
    if r.returncode != 0:
        raise 도구_오류("git 오류: " + r.stderr.decode("utf-8", "replace").strip())
    return r.stdout.decode("utf-8", "replace").rstrip()


def 안전한_이름(값: str, 무엇: str) -> str:
    if not re.fullmatch(r"[0-9A-Za-z가-힣_./~^@-]+", 값) or 값.startswith("-"):
        raise 도구_오류(f"입력 오류: {무엇}에 쓸 수 없는 글자가 있다 — {값}")
    return 값


@s.도구("git_status", "작업 폴더의 지금 상태를 돌려준다: 마지막 커밋 뒤에 고친 파일, 새로 생긴 파일, 지워진 파일.")
def git_status():
    return git("status", "--short", "--branch") or "(바뀐 것 없음)"


@s.도구("git_log", "커밋 이력을 최근 것부터 돌려준다. 한 건마다 커밋 번호, 날짜, 쓴 사람, 메시지, 바뀐 파일이 나온다.",
        {"max_count": {"type": "integer", "description": "돌려줄 커밋의 수(없으면 10)"},
         "path": {"type": "string", "description": "이 파일이나 폴더를 건드린 커밋만 본다(저장소 기준 상대경로)"}})
def git_log(max_count=10, path=None):
    명령 = ["log", f"--max-count={int(max_count)}", "--date=short", "--name-status", "--format=커밋 %h | %ad | %an | %s"]
    if path:
        명령 += ["--", 안전한_이름(path, "path")]
    return git(*명령) or "(커밋 없음)"


@s.도구("git_diff", "마지막 커밋 뒤에 작업 폴더에서 고친 내용을 줄 단위로 돌려준다(아직 커밋하지 않은 변경). 새로 생긴 파일은 git_status에만 나온다.",
        {"path": {"type": "string", "description": "이 파일이나 폴더의 변경만 본다(저장소 기준 상대경로)"}})
def git_diff(path=None):
    명령 = ["diff", "HEAD"]
    if path:
        명령 += ["--", 안전한_이름(path, "path")]
    return git(*명령) or "(커밋하지 않은 변경 없음)"


@s.도구("git_show", "커밋 하나의 내용을 돌려준다: 쓴 사람, 날짜, 메시지, 그 커밋에서 바뀐 줄.",
        {"revision": {"type": "string", "description": "커밋 번호(예: git_log가 돌려준 일곱 글자) 또는 HEAD, HEAD~1"}}, 필수=("revision",))
def git_show(revision):
    return git("show", "--date=short", "--format=커밋 %h | %ad | %an | %s", 안전한_이름(revision, "revision"))


if __name__ == "__main__":
    기록(f"저장소: {저장소}")
    s.실행()
