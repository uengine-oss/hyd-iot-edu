#!/usr/bin/env bash
# 강사 녹화 — 온라인(키 없는) 학생이 받을 AI 단계 결과를 한 번에 만든다. 저장소 루트에서(Windows는 녹화.bat):
#   bash scripts/record_replay.sh [강사 해제 코드 파일]
# 하는 일: 시작(--record: 실제 AI로 진행하며 응답 저장) → 포털 실습 01~13 · 90을 학생 한 명이 누르는 그대로 한 바퀴(class_round.py)
#          → 저장 목록 → 평소 시작(live)으로 되돌림 → 커밋할 명령 안내.
# 필요한 것: .env의 LLM_API_KEY(강의 중계 키), 13 교대 실습을 여는 강사 해제 코드 파일(기본 work/course-access-private/unlock-code.txt),
#           Playwright가 든 Python. 수업 시작 상태(처리 건 0)의 새 폴더에서 돌린다 — 학생 PC도 그 상태에서 시작한다.
# 결과: it/agent-worker/replay/*.json.gz (문서/시스템/참조/재생모드.md). 커밋 · 푸시는 안내만 하고 하지 않는다.
set -euo pipefail
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
cd "$(dirname "$0")/.."
die() { printf '\n[멈춤] %s\n' "$*" >&2; exit 1; }

CODE_FILE="${1:-work/course-access-private/unlock-code.txt}"
[ -s "$CODE_FILE" ] || die "강사 해제 코드 파일이 없습니다: $CODE_FILE (13 교대 실습을 녹화하려면 필요합니다. 경로를 인자로 주세요)"
PY=""
for candidate in .venv314/Scripts/python.exe .venv/bin/python .venv/Scripts/python.exe python python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import playwright' >/dev/null 2>&1; then PY="$candidate"; break; fi
done
[ -n "$PY" ] || die "Playwright가 든 Python이 없습니다. 'python -m pip install playwright' 와 'python -m playwright install chromium' 뒤 다시 실행하세요."

old=$( { ls it/agent-worker/replay/*.json.gz 2>/dev/null || true; } | wc -l | tr -d ' ')
if [ "$old" -gt 0 ]; then   # 한 바퀴 녹화가 저장분 전체가 되게 한다(옛 저장분은 git 이력에 남는다)
  rm -f it/agent-worker/replay/*.json.gz
  echo "옛 저장분 ${old}개를 지우고 새로 녹화합니다(git 이력에는 남아 있습니다)."
fi

bash scripts/start_all.sh --record || die "녹화 모드로 켜지 못했습니다(위 [멈춤] 메시지)."

OUT=".evidence/record-replay/$(date +%Y%m%d-%H%M%S)"
echo
echo "== 녹화: 포털 실습 01~13 · 90 한 바퀴 (실제 AI, 30분 안팎) — 결과 $OUT"
set +e
"$PY" scripts/class_round.py --only 01,02,03,04,05,05c,06,07,08,09,10,11,12,13,90 --ai-runs 1 \
  --unlock-code-file "$CODE_FILE" --out "$OUT"
rc=$?
set -e

echo
echo "== 저장된 AI 응답"
# 폴더 인자를 주지 않는다: Git Bash 가 /srv/replay 를 C:/Program Files/Git/srv/replay 로 바꿔 「업무 0개」로 보였다(2026-10-28 실측) — 컨테이너의 AI_REPLAY_DIR 을 쓴다
docker compose exec -T agent-worker python -m worker.ai_replay || true

echo
echo "== 평소 시작(실제 AI)으로 되돌림"
bash scripts/start_all.sh || die "평소 시작으로 되돌리지 못했습니다. 시작.bat을 다시 실행하세요."

[ "$rc" = 0 ] || die "한 바퀴에 실패한 판정이 있습니다($OUT/summary.md). 실패한 실습의 저장분은 학생에게 줄 수 없으니 원인을 고친 뒤 다시 녹화하세요."
cat <<'EOF'

녹화 완료. 저장분만 커밋 · 푸시합니다(다른 파일은 넣지 않습니다):
  git add it/agent-worker/replay/
  git commit -m "replay: 강사 녹화(포털 실습 01~13 · 90)"
  git show --stat HEAD
  git push origin main
EOF
