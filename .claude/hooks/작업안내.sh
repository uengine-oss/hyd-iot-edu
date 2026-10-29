#!/usr/bin/env bash
# 세션이 열릴 때(시작 · 이어하기 · 비우기) 구조 지도와 열린 작업 폴더를 보여 준다. 무엇부터 할지 사용자에게 묻지 않게 한다.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
echo "[hyd 작업 안내]"
echo "- 구조: main = 학생이 clone해 실행하는 것만 · workspace/ = 작업 자료 전부(workspace 브랜치) · 작업/ = 진행 중 작업(이 PC 전용)"
echo "- 요청을 받으면 스킬 hyd-task 순서대로 한다: 작업 폴더 → workspace/README.md 색인에서 문서 하나 → 만들기 · 검사 → 제자리 → 동기화 → 정리"
open=0
for d in 작업/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*/; do
  [ -d "$d" ] || continue
  st=$(grep -m1 -o '상태: *[^ ]*' "$d/스펙.md" 2>/dev/null | sed 's/상태: *//')
  echo "- 열린 작업: ${d%/} (상태 ${st:-스펙 없음}) — 이어서 하면 그 폴더의 스펙.md · 기록.md부터 읽는다"
  open=$((open+1))
done
[ "$open" -eq 0 ] && echo "- 열린 작업 폴더 없음"
exit 0
