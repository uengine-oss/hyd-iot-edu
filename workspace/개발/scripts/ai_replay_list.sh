#!/usr/bin/env bash
# 저장된 AI 응답 목록 — 촬영(AI_MODE=record) 뒤 업무마다 저장됐는지 확인한다. workspace/개발/문서/재생모드.md 5절.
#   bash workspace/개발/scripts/ai_replay_list.sh            (기본 폴더 it/agent-worker/replay/, 다른 폴더는 인자로)
set -euo pipefail
cd "$(dirname "$0")/../../.."
case "${OSTYPE:-}" in msys*|cygwin*) SEP=";";; *) SEP=":";; esac
export PYTHONPATH="it/agent-worker${SEP}it/process${SEP}common" PYTHONUTF8=1
PY="${PYTHON:-}"
if [ -z "$PY" ]; then for c in .venv314/Scripts/python.exe .venv/bin/python; do [ -x "$c" ] && { PY="$c"; break; }; done; fi
[ -n "$PY" ] || { echo "ai_replay_list.sh: no .venv314 or .venv python (set PYTHON=...)" >&2; exit 1; }
exec "$PY" -m worker.ai_replay "$@"
