#!/usr/bin/env bash
# Run the cliagents agent worker on this PC with the lecturer's own (logged-in) Claude Code CLI, while Supabase · Neo4j ·
# enterprise-mcp · dmn-mcp run in compose. The tenant's MCP entries use container hostnames; MCP_HOST_REWRITE maps them.
#   bash scripts/run_worker_host.sh            (from the repo root; .venv314 or any Python 3.12+ with psycopg + cliagents)
set -euo pipefail
cd "$(dirname "$0")/.."
# Git Bash on Windows: Python wants ';' between PYTHONPATH entries and Windows-style paths (pwd -W), not /d/work/…
case "${OSTYPE:-}" in msys*|cygwin*) SEP=";"; HERE="$(pwd -W)";; *) SEP=":"; HERE="$PWD";; esac
export PYTHONPATH="it/agent-worker${SEP}it/process${SEP}common"
# host.docker.internal=127.0.0.1: 학생이 자기 PC 에서 띄워 포털에 등록한 MCP 서버(주소 http://host.docker.internal:<포트>/mcp — process 컨테이너가
# 닿는 이름)는 이 호스트 워커에게는 자기 자신이다. 이 줄이 없으면 macOS · Linux 호스트에서 그 이름을 풀지 못해 에이전트만 그 도구를 못 쓴다.
export SUPABASE_DSN="${SUPABASE_DSN:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"
export MCP_HOST_REWRITE="${MCP_HOST_REWRITE:-neo4j:7687=127.0.0.1:7687,enterprise-mcp:8199=127.0.0.1:8199,dmn-mcp:8198=127.0.0.1:8198,enterprise-mcp-maint:8196=127.0.0.1:8196,enterprise-mcp-purchase:8195=127.0.0.1:8195,host.docker.internal=127.0.0.1}"
export CLIAGENTS_WORKSPACE_ROOT="${CLIAGENTS_WORKSPACE_ROOT:-$HERE/.evidence/workspace}"
export SCHEMA_PROMPT="${SCHEMA_PROMPT:-$HERE/it/neo4j/v2/schema_prompt.md}"
export CONSUMER_ID="${CONSUMER_ID:-agent-worker:host}"
# The worker is Claude Code on Opus (user 2026-10-06: "Opus, not a toy"); pin it instead of relying on the personal default model.
export CLI_MODEL="${CLI_MODEL:-opus}"
export HEALTH_PORT="${HEALTH_PORT:-8097}"
# A105: Smart App Control blocks psycopg_binary's unsigned libpq; load a signed one for the pure-Python wrapper instead.
. scripts/host_libpq.sh
# Windows: .venv314 (CLAUDE.md §5); Linux (cloud): .venv; PYTHON overrides. A missing interpreter fails loudly below.
PY="${PYTHON:-}"
if [ -z "$PY" ]; then for c in .venv314/Scripts/python.exe .venv/bin/python; do [ -x "$c" ] && { PY="$c"; break; }; done; fi
[ -n "$PY" ] || { echo "run_worker_host.sh: no .venv314 or .venv python (set PYTHON=...)" >&2; exit 1; }
exec "$PY" -m worker.main
