#!/usr/bin/env bash
# 실습 스택 점검 — setup 폴더의 점검.bat(Windows, Git Bash) · 점검.command(Mac)가 부른다. 시작이 「완료」된 뒤에 쓴다.
# 서비스 응답 → 쿨러 사건 한 바퀴(경보 → AI 판단 → 승인 → 냉각 명령 → 재관측 → 작업지시) → 강의 중계(키 있는 PC만)를 scripts/check_stack.py 가 본다.
set -euo pipefail
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
cd "$(dirname "$0")/.."
. scripts/windows_paths.sh
. scripts/macos_paths.sh
. scripts/versions.txt
. scripts/find_python.sh
[ "${#PYTHON[@]}" -gt 0 ] || { echo "[멈춤] Python $PYTHON_MIN 이상이 없습니다. 설치 파일을 먼저 실행하세요." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo '[멈춤] Docker가 응답하지 않습니다. Docker Desktop을 열고 시작 파일을 먼저 끝까지 실행하세요.' >&2; exit 1; }
"${PYTHON[@]}" scripts/check_stack.py all
