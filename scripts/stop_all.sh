#!/usr/bin/env bash
# 실습 스택을 끈다(데이터는 지우지 않는다). 저장소 루트에서: bash scripts/stop_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/windows_paths.sh
docker compose stop enterprise-mcp dmn-mcp
docker compose stop
if command -v supabase >/dev/null 2>&1; then SUPA=(supabase); else SUPA=(npx -y supabase); fi
( cd it/supabase && "${SUPA[@]}" stop )
echo "실행 중 컨테이너: $(docker ps -q | wc -l | tr -d ' ')개 (0이면 모두 꺼짐)"
