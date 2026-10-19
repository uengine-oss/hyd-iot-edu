"""업무자료 폴더를 만들고 Git 이력을 쌓는다. 실습을 시작할 때 한 번 실행한다.

    python 도구/자료_준비.py          업무자료 폴더를 만든다(이미 있으면 그대로 두고 멈춘다)
    python 도구/자료_준비.py --다시    업무자료 폴더를 지우고 처음 상태로 다시 만든다

만들어지는 것: 설비보전팀 공유 폴더 `업무자료/`. 커밋 다섯 건의 이력이 있고,
마지막 커밋 뒤에 고친 파일 하나와 새로 생긴 파일 하나가 커밋되지 않은 채 남아 있다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

여기 = Path(__file__).resolve().parent
폴더 = 여기.parent / "업무자료"
이력 = 여기 / "이력"

커밋들 = [  # (단계 폴더, 쓴 사람, 날짜, 메시지)
    ("1", "강도현", "2026-09-08T09:10:00+09:00", "설비보전팀 공유 폴더를 만들고 기준 문서 세 건을 올린다"),
    ("2", "문태오", "2026-10-06T16:05:00+09:00", "10월 정기 회의록을 올린다"),
    ("3", "오민재", "2026-10-08T11:20:00+09:00", "10월 2주차 주간 협의 메모를 올린다"),
    ("4", "한서윤", "2026-10-08T15:40:00+09:00", "쿨러 점검 메모를 만든다: 청소 주기 변경과 호기별 핀 점검"),
    ("5", "문태오", "2026-10-13T08:50:00+09:00", "쿨러 점검 메모에 3호기 점검 완료와 1호기 필터 망 시험 설치를 적는다"),
]


def 덮어_놓기(단계: str):
    for f in sorted((이력 / 단계).rglob("*")):
        if f.is_file():
            자리 = 폴더 / f.relative_to(이력 / 단계)
            자리.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, 자리)


def git(*명령: str, 환경: dict | None = None) -> str:
    r = subprocess.run(["git", "-C", str(폴더), "-c", "core.autocrlf=false", "-c", "core.quotepath=false", *명령],
                       capture_output=True, env={**os.environ, **(환경 or {})})
    if r.returncode != 0:
        sys.exit("git 오류: " + r.stderr.decode("utf-8", "replace").strip())
    return r.stdout.decode("utf-8", "replace").strip()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if shutil.which("git") is None:
        print("git 을 찾지 못했다. Git 을 설치한 뒤 다시 실행한다.")
        return 1
    if 폴더.exists():
        if "--다시" not in sys.argv:
            print("업무자료 폴더가 이미 있다. 그대로 두었다. 처음 상태로 되돌리려면: python 도구/자료_준비.py --다시")
            return 0
        shutil.rmtree(폴더, onerror=lambda 함수, 경로, _: (os.chmod(경로, 0o700), 함수(경로)))
    폴더.mkdir()
    git("init", "--quiet", "--initial-branch=main")
    for 단계, 사람, 날짜, 메시지 in 커밋들:
        덮어_놓기(단계)
        git("add", "--all")
        git("commit", "--quiet", "-m", 메시지, 환경={
            "GIT_AUTHOR_NAME": 사람, "GIT_AUTHOR_EMAIL": "", "GIT_AUTHOR_DATE": 날짜,
            "GIT_COMMITTER_NAME": 사람, "GIT_COMMITTER_EMAIL": "", "GIT_COMMITTER_DATE": 날짜})
    덮어_놓기("작업중")
    print("업무자료 폴더를 만들었다.")
    print("커밋 " + git("rev-list", "--count", "HEAD") + "건:")
    print("\n".join("  " + 줄 for 줄 in git("log", "--date=short", "--format=%h | %ad | %an | %s").splitlines()))
    print("커밋하지 않은 변경:")
    print("\n".join("  " + 줄 for 줄 in git("status", "--short").splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
