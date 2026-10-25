#!/usr/bin/env bash
# 실습 스택을 끈다(데이터는 지우지 않는다). 저장소 루트에서: bash scripts/stop_all.sh
# AI 워커 · 에이전트용 MCP(프로필 cliagents)와 선택 프로필(monitor · tools)까지 모두 끈다 — 프로필 "*" 는 compose 의 모든 프로필.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/windows_paths.sh
. scripts/macos_paths.sh
unset COMPOSE_PROFILES
docker compose --profile '*' stop
SUPA=(npx -y supabase@2.119.0)
( cd it/supabase && "${SUPA[@]}" stop )
echo "실행 중 컨테이너: $(docker ps -q | wc -l | tr -d ' ')개 (0이면 모두 꺼짐)"
