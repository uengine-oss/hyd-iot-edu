#!/usr/bin/env bash
# 실습 스택을 끈다(데이터는 지우지 않는다). setup 폴더의 끄기.bat(Windows) · 끄기.command(Mac)가 부른다.
# 이 폴더의 compose 서비스(AI 워커 · 선택 도구 monitor · tools 까지 — 프로필 "*")를 멈추고(컨테이너는 남긴다), 업무 DB(Supabase)를 끈 뒤
# 둘 다 켜진 컨테이너가 0개인지 센다(업무 DB 이름 · 포트는 시작이 쓴 it/supabase/.env 를 CLI 가 스스로 읽는다. 그 파일이 없으면 — 이 폴더에서 지금
# 판의 시작을 한 번도 하지 않았으면 — CLI 는 커밋된 기본 이름(it/supabase/config.toml 의 project_id)의 업무 DB 를 끈다: 그 이름으로 세고 그렇게 말한다).
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/windows_paths.sh
. scripts/macos_paths.sh
. scripts/versions.txt
die() { printf '[멈춤] %s\n' "$*" >&2; exit 1; }
docker info >/dev/null 2>&1 || die 'Docker가 응답하지 않습니다. Docker Desktop을 연 뒤 다시 실행하세요(Docker가 꺼져 있으면 실습 스택도 이미 꺼져 있습니다).'
unset COMPOSE_PROFILES
# stop 은 시작이 정하는 값(AI_MODE · 호출자 토큰 · 지문 키)을 쓰지 않지만 compose 는 파일 전체를 읽는다 — 새 판을 받고 아직 시작하지 않은
# .env(그 값이 없음)에서도 끌 수 있게 이 명령에만 자리 값을 준다(켜는 명령에는 주지 않는다)
compose() { AI_MODE=stop PROCESS_CALLER_TOKEN=stop CMD_FINGERPRINT_KEY=stop docker compose "$@"; }
compose --profile '*' stop || die '시스템 컨테이너를 멈추지 못했습니다. 위 오류를 보고 Docker Desktop이 켜져 있는지 확인한 뒤 다시 실행하세요.'
( cd it/supabase && npx -y "supabase@$SUPABASE_CLI" stop ) || die '업무 DB(Supabase)를 끄지 못했습니다. 도움을 요청할 때 위 오류를 그대로 전해 주세요(쌓인 데이터는 그대로 있습니다). Docker Desktop의 Containers 화면에서 supabase_ 로 시작하는 컨테이너를 멈춰도 됩니다.'
running=$(compose ps --status running -q | grep -c . || true)
supa=$(sed -n 's/^SUPABASE_PROJECT_ID=//p' it/supabase/.env 2>/dev/null | tail -1)
supa_note=''
if [ -z "$supa" ]; then
  supa=$(sed -n 's/^project_id *= *"\(.*\)"/\1/p' it/supabase/config.toml | head -1)
  supa_note=" 이 폴더의 업무 DB 이름 기록(it/supabase/.env)이 없어 기본 이름(${supa})의 업무 DB를 껐습니다."
fi
supa_running=0
[ -z "$supa" ] || supa_running=$(docker ps -q --filter "label=com.supabase.cli.project=$supa" | grep -c . || true)
[ "$running" -eq 0 ] || die "이 폴더의 시스템 컨테이너 ${running}개가 아직 켜져 있습니다. 'docker compose ps'로 확인하세요."
[ "$supa_running" -eq 0 ] || die "업무 DB(Supabase, ${supa}) 컨테이너 ${supa_running}개가 아직 켜져 있습니다. 끄기를 한 번 더 실행하고, 그래도 남으면 이 메시지를 그대로 전해 도움을 요청하세요."
echo "꺼짐: 이 폴더의 시스템과 업무 DB(쌓인 데이터는 그대로 남습니다).${supa_note}"
