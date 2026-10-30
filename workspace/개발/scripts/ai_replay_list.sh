#!/usr/bin/env bash
# 수업 녹화 목록 — 녹화(AI_MODE=record) 뒤 수업 AI 자리마다 녹화가 있는지 확인한다(빠진 자리가 있으면 종료 코드 1). workspace/개발/문서/재생모드.md
#   bash workspace/개발/scripts/ai_replay_list.sh            (기본 폴더 it/agent-worker/replay/, 다른 폴더는 인자로)
set -euo pipefail
cd "$(dirname "$0")/../../.."
case "${OSTYPE:-}" in msys*|cygwin*) SEP=";";; *) SEP=":";; esac
export PYTHONPATH="it/agent-worker${SEP}it/process${SEP}common" PYTHONUTF8=1
PY="${PYTHON:-}"
if [ -z "$PY" ]; then for c in .venv314/Scripts/python.exe .venv/bin/python; do [ -x "$c" ] && { PY="$c"; break; }; done; fi
[ -n "$PY" ] || { echo "ai_replay_list.sh: no .venv314 or .venv python (set PYTHON=...)" >&2; exit 1; }
exec "$PY" -m worker.ai_replay "$@"
