#!/usr/bin/env bash
# 개발용 호스트 워커 — 이 PC의 Claude Code CLI 로 AI 단계를 돌린다. 나머지(process · Supabase · Neo4j · 도구 서버)는 compose 스택이다.
#   bash workspace/개발/scripts/run_worker_host.sh            (저장소 루트에서, Git Bash · macOS · Linux)
#   AI_MODE=record bash workspace/개발/scripts/run_worker_host.sh   (강사 녹화 — workspace/개발/문서/재생모드.md)
# 컨테이너 워커와 같은 경로로 돈다: 수업 판정 · 실행 토큰은 process(로컬 중계 관문)에서 받고, CLI 는 그 토큰으로만 모델을 부른다(개인 로그인 · 모델
# 고르기 없음 — 모델은 관문 정책). 워커 인증 파일은 process 컨테이너의 것을 이 PC의 .hyd-runtime/ 에 잠시 복사해 쓰고, 워커가 끝나면 지운다.
# 워커는 하나만 — 컨테이너 워커가 켜져 있으면 멈춘다. 포털 「에이전트 현황」이 이 워커를 보게 하려면 RUNBOOK §5.
# 멈추기: Windows workspace/개발/scripts/stop_worker_host.ps1, 그 밖은 Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")/../../.."
die() { printf '[멈춤] %s\n' "$*" >&2; exit 1; }
# 로그를 UTF-8 하나로(Windows 로캘 cp949와 섞이지 않게)
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
# Git Bash on Windows: Python wants ';' between PYTHONPATH entries and Windows-style paths (pwd -W), not /d/work/…
case "${OSTYPE:-}" in msys*|cygwin*) SEP=";"; HERE="$(pwd -W)";; *) SEP=":"; HERE="$PWD";; esac
export PYTHONPATH="it/agent-worker${SEP}it/process${SEP}common"
# Windows Smart App Control 이 psycopg_binary 의 서명 없는 libpq 를 막는 PC — 서명된 libpq 를 먼저 쓴다(그 파일 머리)
. workspace/개발/scripts/host_libpq.sh
# Windows: .venv314 (CLAUDE.md §6); Linux (cloud): .venv; PYTHON overrides. A missing interpreter fails loudly below.
PY="${PYTHON:-}"
if [ -z "$PY" ]; then for c in .venv314/Scripts/python.exe .venv/bin/python; do [ -x "$c" ] && { PY="$c"; break; }; done; fi
[ -n "$PY" ] || die "no .venv314 or .venv python (set PYTHON=...)"
[ -f .hyd-runtime/ports.json ] || die ".hyd-runtime/ports.json 이 없습니다 — 먼저 시작.bat(scripts/start_all.sh)으로 스택을 켜세요"
[ -z "$(docker compose ps -q --status running agent-worker 2>/dev/null)" ] || die "컨테이너 AI 워커가 켜져 있습니다(워커는 하나만). docker compose stop agent-worker 뒤 다시 실행하세요"
# 이 PC의 호스트 포트(시작 스크립트가 옮긴 포트 포함): 컨테이너 포트 → 호스트 포트
port() { "$PY" -c 'import json,sys; print(json.load(open(".hyd-runtime/ports.json"))[sys.argv[1]])' "$1"; }
KEY=.hyd-runtime/worker-runtime.key
trap 'rm -f "$KEY" "$KEY.tmp"' EXIT
docker compose exec -T process sh -c 'cat "$HYD_WORKER_RUNTIME_KEY_FILE"' > "$KEY.tmp" || die "process 컨테이너에서 워커 인증 파일을 읽지 못했습니다(스택이 켜져 있는지 확인)"
chmod 600 "$KEY.tmp" && mv "$KEY.tmp" "$KEY"
export PROCESS_URL="http://127.0.0.1:$(port 8080)"
export HYD_WORKER_RUNTIME_KEY_FILE="$HERE/$KEY"
export SUPABASE_DSN="${SUPABASE_DSN:-postgresql://postgres:postgres@127.0.0.1:$(port 54322)/postgres}"
# 처리 건의 도구 서버 주소는 컨테이너 이름이다 — 이 워커가 닿는 호스트 포트로 바꾼다. host.docker.internal 은 학생이 이 PC에서 띄운 서버.
export MCP_HOST_REWRITE="${MCP_HOST_REWRITE:-neo4j:7687=127.0.0.1:$(port 7687),enterprise-mcp:8199=127.0.0.1:$(port 8199),dmn-mcp:8198=127.0.0.1:$(port 8198),enterprise-mcp-maint:8196=127.0.0.1:$(port 8196),enterprise-mcp-purchase:8195=127.0.0.1:$(port 8195),host.docker.internal=127.0.0.1}"
# 작업 공간은 이 PC 전용 자리(.hyd-runtime/ — git 밖, 작업 폴더 규칙 밖에 쌓이지 않게)
export CLIAGENTS_WORKSPACE_ROOT="${CLIAGENTS_WORKSPACE_ROOT:-$HERE/.hyd-runtime/worker-workspace}"
export SCHEMA_PROMPT="${SCHEMA_PROMPT:-$HERE/it/neo4j/v2/schema_prompt.md}"
export AI_REPLAY_DIR="${AI_REPLAY_DIR:-$HERE/it/agent-worker/replay}"
export CONSUMER_ID="${CONSUMER_ID:-agent-worker:host}"
export AI_MODE="${AI_MODE:-live}"
export HEALTH_PORT="${HEALTH_PORT:-$(port 8097)}"
# exec 하지 않는다 — 워커가 끝나면(Ctrl+C · stop_worker_host.ps1) 위 trap 이 인증 파일 사본을 지운다
"$PY" -m worker.main
