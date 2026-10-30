#!/usr/bin/env bash
# 실습 스택을 끈다(데이터는 지우지 않는다). setup 폴더의 끄기.bat(Windows)이 부르고, Mac은 프로젝트 폴더에서 bash scripts/stop_all.sh.
# 이 폴더의 compose 서비스(AI 워커 · 선택 도구 monitor · tools 까지 — 프로필 "*")를 멈추고(컨테이너는 남긴다), 업무 DB(Supabase)를 끈다
# (업무 DB 이름 · 포트는 시작이 쓴 it/supabase/.env 를 CLI 가 스스로 읽는다).
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/windows_paths.sh
. scripts/macos_paths.sh
. scripts/versions.txt
docker info >/dev/null 2>&1 || { echo '[멈춤] Docker가 응답하지 않습니다. Docker Desktop을 연 뒤 다시 실행하세요(Docker가 꺼져 있으면 실습 스택도 이미 꺼져 있습니다).' >&2; exit 1; }
unset COMPOSE_PROFILES
# stop 은 시작이 정하는 값(AI_MODE · 호출자 토큰 · 지문 키)을 쓰지 않지만 compose 는 파일 전체를 읽는다 — 새 판을 받고 아직 시작하지 않은
# .env(그 값이 없음)에서도 끌 수 있게 이 명령에만 자리 값을 준다(켜는 명령에는 주지 않는다)
AI_MODE=stop PROCESS_CALLER_TOKEN=stop CMD_FINGERPRINT_KEY=stop docker compose --profile '*' stop
( cd it/supabase && npx -y "supabase@$SUPABASE_CLI" stop )
running=$(AI_MODE=stop PROCESS_CALLER_TOKEN=stop CMD_FINGERPRINT_KEY=stop docker compose ps --status running -q | grep -c . || true)
[ "$running" -eq 0 ] || { echo "[멈춤] 이 폴더의 시스템 컨테이너 ${running}개가 아직 켜져 있습니다. 'docker compose ps'로 확인하세요." >&2; exit 1; }
echo "꺼짐: 이 폴더의 시스템과 업무 DB(실습 데이터는 그대로 남습니다)."
