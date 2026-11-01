#!/usr/bin/env bash
# 강사 AI 응답 저장(영상 녹화 아님) — 키 없는 학생 PC가 받을 AI 단계 결과를 한 번에 만든다. 저장소 루트에서(Windows는 Git Bash):
#   bash workspace/개발/scripts/record_replay.sh 작업/<날짜>_<제목>/실행/녹화        (한 바퀴 결과 폴더 — 열린 작업 폴더 아래)
# 하는 일: 시작(--record: 실제 AI로 진행하며 응답 저장) → 실라버스 포털 실습 전부(01~17) · 메뉴 순회(90)를 학생 한 명이 누르는 그대로 한 바퀴
#          (class_round.py --ai-runs 1) → 녹화 목록(수업 AI 자리마다 있는지 — 녹화하지 않기로 한 자리는 빠짐으로 세지 않는다) → 평소 시작(live)으로 되돌림
#          → 커밋할 명령 안내.
# 녹화는 화면 판정과 상관없이 워커 실행이 저장된 결과(제출 · 사람 질문 · 보류)로 끝나면 그 자리의 옛 녹화를 바꾼다(worker/ai_replay.py Claim.keep)
# — 그래서 시작할 때 옛 녹화를 지우지 않고, 끝에 git diff 로 바뀐 녹화를 본다.
# 필요한 것: .env의 LLM_API_KEY(강의 중계 키), Playwright가 든 Python. 수업 시작 상태(처리 건 0)의 새 폴더에서 돌린다 — 학생 PC도 그 상태에서 시작한다.
# 결과: it/agent-worker/replay/*.json.gz (workspace/개발/문서/재생모드.md). 커밋 · 푸시는 안내만 하고 하지 않는다.
set -euo pipefail
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
cd "$(dirname "$0")/../../.."
die() { printf '\n[멈춤] %s\n' "$*" >&2; exit 1; }
OUT="${1:-}"
[ -n "$OUT" ] || die "결과 폴더를 주세요: bash workspace/개발/scripts/record_replay.sh 작업/<날짜>_<제목>/실행/녹화"

PY=""
for candidate in .venv314/Scripts/python.exe .venv/bin/python .venv/Scripts/python.exe python python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import playwright, openpyxl' >/dev/null 2>&1; then PY="$candidate"; break; fi
done
[ -n "$PY" ] || die "Playwright · openpyxl 이 든 Python이 없습니다. '.venv314/Scripts/python.exe -m pip install -r workspace/requirements-dev.txt' 와 'python -m playwright install chromium' 뒤 다시 실행하세요."

bash scripts/start_all.sh --record || die "AI 응답 저장 모드로 켜지 못했습니다(위 [멈춤] 메시지)."

echo
echo "== AI 응답 저장: 실라버스 포털 실습 01~17 · 90 한 바퀴 (실제 AI) — 결과 $OUT"
set +e
"$PY" workspace/개발/scripts/class_round.py --only 01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,90 --ai-runs 1 --out "$OUT"
rc=$?
set -e

echo
echo "== 수업 녹화 목록(저장소 it/agent-worker/replay/ — 워커 컨테이너와 같은 폴더)"
set +e
bash workspace/개발/scripts/ai_replay_list.sh
listed=$?
set -e

echo
echo "== 평소 시작(실제 AI)으로 되돌림"
bash scripts/start_all.sh || die "평소 시작으로 되돌리지 못했습니다. 시작.bat을 다시 실행하세요."

echo
echo "== 바뀐 녹화"
git status --short -- it/agent-worker/replay/
[ "$rc" = 0 ] || die "한 바퀴에 실패한 판정이 있습니다($OUT/summary.md). 녹화는 워커 실행 결과로 정해져 이번 실행으로 이미 바뀌었을 수 있습니다 — 위 「바뀐 녹화」와 목록을 확인하고, 원인을 고친 뒤 그 실습만(--only) 다시 녹화하세요."
[ "$listed" = 0 ] || die "녹화가 없는 수업 AI 자리가 있습니다(위 목록의 [녹화 없음]). 그 단계를 실제 AI로 한 번 진행한 뒤 다시 확인하세요."
cat <<'MSG'

AI 응답 저장 완료. 저장분만 두 브랜치 동기화 도구로 커밋 · 푸시합니다(키 검사를 거친다 — CLAUDE.md 2절):
  PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/동기화.py commit "replay: 강사 AI 응답 저장(실라버스 포털 실습)" it/agent-worker/replay/
  PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/동기화.py push
MSG
