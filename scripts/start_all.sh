#!/usr/bin/env bash
# 실습 스택을 한 번에 켠다(학생 PC · 강사 PC 공통, Windows는 Git Bash). 저장소 루트에서:
#   bash scripts/start_all.sh
# 하는 일: Docker 확인 → .env 준비(강의 배포본 값) → 업무 DB(Supabase) → 시스템 빌드 · 기동 → 에이전트용 MCP 둘 → 상태 확인.
# LLM은 .env의 OPENAI_BASE_URL · LLM_API_KEY · LLM_MODEL 세 줄(LiteLLM 중계)로 붙는다. 비어 있어도 시나리오는 끝까지 돈다.
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
for k in OPENAI_BASE_URL LLM_API_KEY LLM_MODEL LLM_PROVIDER LLM_EXTRA_BODY; do
  if [ -n "${!k:-}" ]; then echo "주의: 이 창에 환경변수 $k 가 잡혀 있어 .env 값보다 먼저 쓰입니다. 의도한 것이 아니면 'unset $k' 뒤 다시 실행하세요."; fi
done
# LiteLLM 중계 값이 비어 있으면 처음 한 번만 묻는다(엔터만 치면 건너뛴다). 키는 화면에 보이지 않게 받는다.
if ! grep -q "^LLM_API_KEY=." .env && [ -t 0 ]; then
  echo "수업에서 받은 LiteLLM 주소와 키를 넣습니다. 없으면 엔터만 누르세요(나중에 다시 실행하면 또 묻습니다)."
  read -r -p "  LiteLLM 주소(예: https://litellm.example.com): " url || url=""
  if [ -n "$url" ]; then
    read -r -s -p "  키(입력해도 화면에 보이지 않습니다): " key || key=""; echo
    url="${url%/}"; case "$url" in */v1) ;; *) url="$url/v1";; esac
    read -r -p "  모델 이름 [gpt-6-luna]: " model || model=""
    set_env OPENAI_BASE_URL "$url"; set_env LLM_API_KEY "$key"; set_env LLM_MODEL "${model:-gpt-6-luna}"
    set_env LLM_PROVIDER openai; set_env LLM_EXTRA_BODY ""
    if curl -s -m 10 -o /dev/null -w '%{http_code}' "$url/models" -H "Authorization: Bearer $key" | grep -q '^200$'; then
      echo "  LiteLLM 연결 확인: 주소와 키가 맞습니다."
    else
      echo "  주의: $url/models 가 200을 돌려주지 않았습니다. 주소 · 키를 확인하세요(.env를 고치거나 이 줄들을 지우고 다시 실행)."
    fi
  fi
fi
if grep -q "^LLM_API_KEY=." .env && grep -q "^LLM_MODEL=." .env; then
  echo "LLM: .env에 주소 · 키 · 모델이 있습니다(마지막 단계에서 연결을 확인합니다)."
else
  echo "LLM: .env의 LLM_API_KEY 또는 LLM_MODEL이 비어 있습니다. 시나리오는 돌지만 에이전트 요약문은 정해진 문장으로 나옵니다."
fi

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
llm=$(curl -s -m 3 http://127.0.0.1:8091/healthz || true)
case "$llm" in
  *'"llm": true'*|*'"llm":true'*) echo "LLM: 에이전트가 .env의 LLM을 쓸 수 있는 상태입니다($(printf '%s' "$llm" | grep -o '"llm_model": *"[^"]*"'))." ;;
  *) echo "LLM: 에이전트가 LLM 없이 돕니다(키 · 모델을 넣었다면 .env를 확인하고 'docker compose up -d agent')." ;;
esac
[ -z "$bad" ] || die "응답하지 않는 포트:$bad — 'docker compose ps'와 'docker compose logs <서비스>'로 확인하세요."
printf '\n완료. 포털: http://127.0.0.1:8088  (홈의 상태 점이 모두 초록이면 됩니다)\n'
