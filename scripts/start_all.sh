#!/usr/bin/env bash
# 실습 스택을 한 번에 켠다(학생 PC · 강사 PC 공통, Windows는 Git Bash). 저장소 루트에서:
#   bash scripts/start_all.sh
# 하는 일: Docker 확인 → .env 준비(강의 배포본 값) → 업무 DB(Supabase) → 시스템 빌드 · 기동 → 에이전트용 MCP 둘 → 상태 확인.
# 이 스택은 LLM 키 없이 끝까지 돈다(강의 배포본 instance 모드는 경보 처리에 LLM을 부르지 않는다).
# 중계 접속 설정은 루트 .env에 넣는다. 점검.bat은 이 설정을 우선 사용한다. 개별 실습은 해당 실습의 설정 안내를 따른다.
# 끌 때: bash scripts/stop_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\n== %s\n' "$*"; }
die() { printf '\n[멈춤] %s\n' "$*" >&2; exit 1; }

say "1/6 Docker 확인"
DD_EXE="/c/Program Files/Docker/Docker/Docker Desktop.exe"
DD_BIN="/c/Program Files/Docker/Docker/resources/bin"
[ -d "$DD_BIN" ] && PATH="$PATH:$DD_BIN"   # 설치 직후 PATH에 아직 없을 때
. scripts/windows_paths.sh
if ! docker info >/dev/null 2>&1 && [ -f "$DD_EXE" ]; then   # Windows(Git Bash): 꺼져 있으면 켜고 엔진이 뜰 때까지 기다린다
  echo "Docker Desktop을 켭니다. 엔진이 준비될 때까지 최대 3분 기다립니다."
  HYD_DOCKER_DESKTOP_EXE="$(cygpath -w "$DD_EXE")" powershell.exe -NoProfile -Command 'Start-Process -WindowStyle Hidden -FilePath $env:HYD_DOCKER_DESKTOP_EXE' >/dev/null 2>&1
  for i in $(seq 1 36); do docker info >/dev/null 2>&1 && break; sleep 5; done
fi
command -v docker >/dev/null 2>&1 || die "docker 명령이 없습니다. 설치.bat으로 Docker Desktop을 설치하고 PC를 다시 시작한 뒤 실행하세요."
docker info >/dev/null 2>&1 || die "Docker가 응답하지 않습니다. Docker Desktop을 열어 약관 동의 창이 있으면 동의하고, 'Engine running'이 된 뒤 다시 실행하세요."
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

# Compose · 업무 DB · 포털 · 점검이 같은 포트 표를 사용한다.
# 실행 중인 이 프로젝트의 포트만 재사용하고, 다른 앱/컨테이너와 겹치면 빈 포트로 옮긴다.
if command -v python >/dev/null 2>&1 && python -c 'import sys; assert sys.version_info >= (3, 10)' >/dev/null 2>&1; then
  PYTHON=(python)
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; assert sys.version_info >= (3, 10)' >/dev/null 2>&1; then
  PYTHON=(python3)
elif command -v py >/dev/null 2>&1; then
  PYTHON=(py -3)
else
  die "Python 3.10 이상이 필요합니다. 설치.bat을 먼저 실행하세요."
fi
"${PYTHON[@]}" scripts/prepare_ports.py || die "포트를 준비하지 못했습니다. Docker 상태와 폴더 쓰기 권한을 확인하세요."

say "3/6 업무 DB(Supabase) 켜기"
if command -v supabase >/dev/null 2>&1; then SUPA=(supabase); else SUPA=(npx -y supabase); echo "supabase CLI가 없어 npx로 실행합니다(설치: npm install -g supabase@2.119.0)."; fi
( cd it/supabase && "${SUPA[@]}" start >/dev/null ) || die "Supabase가 켜지지 않았습니다. 'cd it/supabase && supabase stop' 뒤 다시 실행하세요(위 포트 배정 결과와 오류 확인)."

say "4/6 시스템 빌드 · 기동 (처음은 이미지 받기 · 빌드로 10분 넘게 걸릴 수 있습니다)"
docker compose up -d --build || die "docker compose up이 실패했습니다. 위 오류의 서비스 이름을 보고 'docker compose logs <서비스>'로 원인을 확인하세요."

say "5/6 에이전트용 MCP 서버 둘"
# 4단계에서 의존 서비스와 kg-seed는 준비됐다. 다시 의존성을 시작하면
# 종료된 일회성 kg-seed가 재실행되므로 MCP 둘만 최신 코드로 빌드·기동한다.
docker compose up -d --build --no-deps enterprise-mcp dmn-mcp || die "enterprise-mcp · dmn-mcp가 올라오지 않았습니다."

say "6/6 상태 확인 (최대 3분 기다립니다)"
PORTS="8000 8093 8090 8094 8092 8091 8080 8095 8199 8198"
hp() { local m; m=$(awk -F= -v k="HYD_PORT_$1" '$1==k {print $2; exit}' .env); echo "${m:-$1}"; }   # 옮긴 포트가 있으면 그 포트
for i in $(seq 1 36); do
  bad=""; for p in $PORTS; do curl -fsS -m 3 "http://127.0.0.1:$(hp "$p")/healthz" >/dev/null 2>&1 || bad="$bad $p"; done
  [ -z "$bad" ] && break; sleep 5
done
for p in $PORTS; do printf '%s ' "$(hp "$p")"; curl -fsS -m 3 "http://127.0.0.1:$(hp "$p")/healthz" | head -c 120 || printf '응답 없음'; echo; done
echo "실행 중 컨테이너: 시스템 $(docker ps --format '{{.Names}}' | grep -c '^hyd-iot-edu-') · 업무 DB $(docker ps --format '{{.Names}}' | grep -c '^supabase_')"
broken=$(docker ps -a --format '{{.Names}} {{.Status}}' | grep '^hyd-iot-edu-' | grep -E 'Restarting|Exited \([1-9]' || true)
[ -z "$broken" ] || { echo "멈췄거나 계속 재시작하는 컨테이너:"; echo "$broken"; }
[ -z "$bad" ] || die "응답하지 않는 포트:$bad — 'docker compose ps'와 'docker compose logs <서비스>'로 확인하세요."
curl -fsS -m 5 "http://127.0.0.1:$(hp 8088)/" >/dev/null || die "포털이 응답하지 않습니다. docker compose logs portal 로 확인하세요."
printf '\n완료. 포털: http://127.0.0.1:%s  (홈의 상태 점이 모두 초록이면 됩니다)\n' "$(hp 8088)"
echo "포트 설정 저장: .hyd-runtime/ports.json (점검.bat이 자동으로 읽습니다)"
