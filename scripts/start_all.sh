#!/usr/bin/env bash
# 실습 스택을 한 번에 켠다(학생 PC · 강사 PC 공통, Windows는 Git Bash). 저장소 루트에서:
#   bash scripts/start_all.sh
# 하는 일: Docker 확인 → .env 준비(강의 배포본 값) → 업무 DB(Supabase) → 시스템 빌드 · 기동 → 에이전트용 MCP 둘 → 상태 확인.
# 이 스택은 LLM 키 없이 끝까지 돈다(강의 배포본 instance 모드는 경보 처리에 LLM을 부르지 않는다).
# LiteLLM 중계 키는 모델을 직접 부르는 실습 폴더의 .env에만 넣는다(실습 가이드의 「LLM 서버 접속 정보」 단계).
# 끌 때: bash scripts/stop_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\n== %s\n' "$*"; }
die() { printf '\n[멈춤] %s\n' "$*" >&2; exit 1; }

say "1/6 Docker 확인"
docker info >/dev/null 2>&1 || die "Docker가 응답하지 않습니다. Docker Desktop을 켜고 'Engine running'이 된 뒤 다시 실행하세요."
docker compose version >/dev/null 2>&1 || die "docker compose가 없습니다. Docker Desktop을 최신으로 설치하세요."
echo "ok"

say "2/6 .env 준비"
[ -f .env ] || { cp .env.example .env; echo ".env.example을 복사해 .env를 만들었습니다."; }
set_env() {   # KEY VALUE — 줄이 있으면 바꾸고 없으면 붙인다(값의 특수 문자를 그대로 두려고 sed 대신 awk + ENVIRON)
  K="$1" V="$2" awk 'BEGIN{k=ENVIRON["K"]; v=ENVIRON["V"]; done=0}
    index($0, k "=")==1 {print k "=" v; done=1; next} {print}
    END{if(!done) print k "=" v}' .env > .env.tmp && mv .env.tmp .env
}
set_env PROCESS_MODE instance          # 강의 배포본(RUNBOOK §0). 예시 파일 기본값 legacy는 회귀 시험용
set_env ENTERPRISE_BACKEND supabase    # memory면 업무 값이 재기동 때 사라진다
echo "ok (PROCESS_MODE=instance, ENTERPRISE_BACKEND=supabase)"

say "3/6 업무 DB(Supabase) 켜기"
if command -v supabase >/dev/null 2>&1; then SUPA=(supabase); else SUPA=(npx -y supabase); echo "supabase CLI가 없어 npx로 실행합니다(설치: npm install -g supabase@2.119.0)."; fi
( cd it/supabase && "${SUPA[@]}" start ) || die "Supabase가 켜지지 않았습니다. 'cd it/supabase && supabase stop' 뒤 다시 실행하세요(포트 54321~54329 충돌 확인)."

say "4/6 시스템 빌드 · 기동 (처음은 이미지 받기 · 빌드로 10분 넘게 걸릴 수 있습니다)"
docker compose up -d --build || die "docker compose up이 실패했습니다. 위 오류의 서비스 이름을 보고 'docker compose logs <서비스>'로 원인을 확인하세요."

say "5/6 에이전트용 MCP 서버 둘"
docker compose up -d enterprise-mcp dmn-mcp || die "enterprise-mcp · dmn-mcp가 올라오지 않았습니다."

say "6/6 상태 확인 (최대 3분 기다립니다)"
PORTS="8000 8093 8090 8094 8092 8091 8080 8095 8199 8198"
for i in $(seq 1 36); do
  bad=""; for p in $PORTS; do curl -s -m 3 "http://127.0.0.1:$p/healthz" >/dev/null 2>&1 || bad="$bad $p"; done
  [ -z "$bad" ] && break; sleep 5
done
for p in $PORTS; do printf '%s ' "$p"; curl -s -m 3 "http://127.0.0.1:$p/healthz" | head -c 120 || printf '응답 없음'; echo; done
echo "실행 중 컨테이너: 시스템 $(docker ps --format '{{.Names}}' | grep -c '^hyd-iot-edu-') · 업무 DB $(docker ps --format '{{.Names}}' | grep -c '^supabase_')"
broken=$(docker ps -a --format '{{.Names}} {{.Status}}' | grep '^hyd-iot-edu-' | grep -E 'Restarting|Exited \([1-9]' || true)
[ -z "$broken" ] || { echo "멈췄거나 계속 재시작하는 컨테이너:"; echo "$broken"; }
[ -z "$bad" ] || die "응답하지 않는 포트:$bad — 'docker compose ps'와 'docker compose logs <서비스>'로 확인하세요."
printf '\n완료. 포털: http://127.0.0.1:8088  (홈의 상태 점이 모두 초록이면 됩니다)\n'
