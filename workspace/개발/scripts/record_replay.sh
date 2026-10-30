#!/usr/bin/env bash
# 강사 AI 응답 저장(영상 녹화 아님) — 온라인(키 없는) 학생이 받을 AI 단계 결과를 한 번에 만든다. 저장소 루트에서(Windows는 Git Bash):
#   bash workspace/개발/scripts/record_replay.sh
# 하는 일: 시작(--record: 실제 AI로 진행하며 응답 저장) → 포털 실습 01~13 · 90을 학생 한 명이 누르는 그대로 한 바퀴(class_round.py)
#          → 녹화 목록(수업 AI 자리마다 있는지 — 빠진 자리가 있으면 실패) → 평소 시작(live)으로 되돌림 → 커밋할 명령 안내.
# 녹화는 점유가 저장된 결과(제출 · 사람 질문 · 보류)로 끝난 실행만 남고 같은 자리의 옛 녹화를 그때 바꾼다 — 실패한 실행은 좋은 녹화를 덮지 않는다
# (worker/ai_replay.py Claim.keep). 그래서 시작할 때 옛 녹화를 지우지 않는다.
# 필요한 것: .env의 LLM_API_KEY(강의 중계 키), Playwright가 든 Python. 수업 시작 상태(처리 건 0)의 새 폴더에서 돌린다 — 학생 PC도 그 상태에서 시작한다.
# 결과: it/agent-worker/replay/*.json.gz (workspace/개발/문서/재생모드.md). 커밋 · 푸시는 안내만 하고 하지 않는다.
set -euo pipefail
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
cd "$(dirname "$0")/../../.."
die() { printf '\n[멈춤] %s\n' "$*" >&2; exit 1; }

PY=""
for candidate in .venv314/Scripts/python.exe .venv/bin/python .venv/Scripts/python.exe python python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import playwright' >/dev/null 2>&1; then PY="$candidate"; break; fi
done
[ -n "$PY" ] || die "Playwright가 든 Python이 없습니다. 'python -m pip install playwright' 와 'python -m playwright install chromium' 뒤 다시 실행하세요."

bash scripts/start_all.sh --record || die "AI 응답 저장 모드로 켜지 못했습니다(위 [멈춤] 메시지)."

OUT="작업/record-replay/$(date +%Y%m%d-%H%M%S)"
echo
echo "== AI 응답 저장: 포털 실습 01~13 · 90 한 바퀴 (실제 AI, 30분 안팎) — 결과 $OUT"
set +e
"$PY" workspace/개발/scripts/class_round.py --only 01,02,03,04,05,05c,06,07,08,09,10,11,12,13,90 --ai-runs 1 --out "$OUT"
rc=$?
set -e

echo
echo "== 수업 녹화 목록"
# 폴더 인자를 주지 않는다: Git Bash 가 /srv/replay 를 C:/Program Files/Git/srv/replay 로 바꿔 「0개」로 보였다(2026-10-28 실측) — 컨테이너의 AI_REPLAY_DIR 을 쓴다
set +e
docker compose exec -T agent-worker python -m worker.ai_replay
listed=$?
set -e

echo
echo "== 평소 시작(실제 AI)으로 되돌림"
bash scripts/start_all.sh || die "평소 시작으로 되돌리지 못했습니다. 시작.bat을 다시 실행하세요."

[ "$rc" = 0 ] || die "한 바퀴에 실패한 판정이 있습니다($OUT/summary.md). 실패한 실습의 녹화는 남지 않았습니다 — 원인을 고친 뒤 그 실습만 다시 하세요."
[ "$listed" = 0 ] || die "녹화가 없는 수업 AI 자리가 있습니다(위 목록의 [녹화 없음]). 그 단계를 실제 AI로 한 번 진행한 뒤 다시 확인하세요."
cat <<'EOF'

AI 응답 저장 완료. 저장분만 커밋 · 푸시합니다(다른 파일은 넣지 않습니다):
  git add it/agent-worker/replay/
  git commit -m "replay: 강사 AI 응답 저장(포털 실습 01~13 · 90)"
  git show --stat HEAD
  git push origin main
EOF
