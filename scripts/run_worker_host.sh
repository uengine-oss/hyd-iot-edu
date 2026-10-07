#!/usr/bin/env bash
# Run the cliagents agent worker on this PC with the lecturer's own (logged-in) Claude Code CLI, while Supabase · Neo4j ·
# enterprise-mcp · dmn-mcp run in compose. The tenant's MCP entries use container hostnames; MCP_HOST_REWRITE maps them.
#   bash scripts/run_worker_host.sh            (from the repo root; .venv314 or any Python 3.12+ with psycopg + cliagents)
set -euo pipefail
cd "$(dirname "$0")/.."
# Git Bash on Windows: Python wants ';' between PYTHONPATH entries and Windows-style paths (pwd -W), not /d/work/…
case "${OSTYPE:-}" in msys*|cygwin*) SEP=";"; HERE="$(pwd -W)";; *) SEP=":"; HERE="$PWD";; esac
export PYTHONPATH="it/agent-worker${SEP}it/process${SEP}common"
export SUPABASE_DSN="${SUPABASE_DSN:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"
export MCP_HOST_REWRITE="${MCP_HOST_REWRITE:-neo4j:7687=127.0.0.1:7687,enterprise-mcp:8199=127.0.0.1:8199,dmn-mcp:8198=127.0.0.1:8198}"
export CLIAGENTS_WORKSPACE_ROOT="${CLIAGENTS_WORKSPACE_ROOT:-$HERE/.evidence/workspace}"
export SCHEMA_PROMPT="${SCHEMA_PROMPT:-$HERE/it/neo4j/v2/schema_prompt.md}"
export CONSUMER_ID="${CONSUMER_ID:-agent-worker:host}"
# The worker is Claude Code on Opus (user 2026-10-06: "Opus, not a toy"); pin it instead of relying on the personal default model.
export CLI_MODEL="${CLI_MODEL:-opus}"
export HEALTH_PORT="${HEALTH_PORT:-8097}"
PY="${PYTHON:-.venv314/Scripts/python.exe}"
[ -x "$PY" ] || PY=python
exec "$PY" -m worker.main
