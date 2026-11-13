#!/usr/bin/env bash
# 수업 녹화 목록 — 녹화(AI_MODE=record) 뒤 수업 AI 자리마다 녹화가 있는지 확인한다(녹화해야 하는 자리가 빠졌으면 종료 코드 1,
# 녹화하지 않기로 한 자리는 따로 한 줄). 자리 목록은 떠 있는 process 의 GET /api/course-access 에서 읽는다. workspace/개발/문서/재생모드.md
#   bash workspace/개발/scripts/ai_replay_list.sh            (기본 폴더 it/agent-worker/replay/, 다른 폴더는 인자로)
set -euo pipefail
cd "$(dirname "$0")/../../.."
case "${OSTYPE:-}" in msys*|cygwin*) SEP=";";; *) SEP=":";; esac
export PYTHONPATH="it/agent-worker${SEP}it/process${SEP}common" PYTHONUTF8=1 PYTHONIOENCODING=utf-8
PY="${PYTHON:-}"
if [ -z "$PY" ]; then for c in .venv314/Scripts/python.exe .venv/bin/python; do [ -x "$c" ] && { PY="$c"; break; }; done; fi
[ -n "$PY" ] || { echo "ai_replay_list.sh: .venv314 · .venv 파이썬이 없습니다(PYTHON=... 으로 지정)" >&2; exit 1; }
[ -f .hyd-runtime/ports.json ] || { echo "ai_replay_list.sh: .hyd-runtime/ports.json 이 없습니다 — 시작.bat 으로 스택을 먼저 켜세요(자리 목록은 process 에서 읽는다)" >&2; exit 1; }
export PROCESS_URL="${PROCESS_URL:-http://127.0.0.1:$("$PY" -c 'import json; print(json.load(open(".hyd-runtime/ports.json"))["8080"])')}"
exec "$PY" -m worker.ai_replay "${@:-it/agent-worker/replay}"
