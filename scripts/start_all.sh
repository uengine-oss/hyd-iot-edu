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
DD_EXE="/c/Program Files/Docker/Docker/Docker Desktop.exe"
DD_BIN="/c/Program Files/Docker/Docker/resources/bin"
[ -d "$DD_BIN" ] && PATH="$PATH:$DD_BIN"   # 설치 직후 PATH에 아직 없을 때
if ! docker info >/dev/null 2>&1 && [ -f "$DD_EXE" ]; then   # Windows(Git Bash): 꺼져 있으면 켜고 엔진이 뜰 때까지 기다린다
  echo "Docker Desktop을 켭니다. 엔진이 준비될 때까지 최대 3분 기다립니다."
  cmd.exe //c start "" "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"
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

# 바깥 포트(모두 127.0.0.1 — 이 PC 안에서만). 다른 프로그램이 이미 쓰고 있으면 그 서비스만 비어 있는 다른 포트로 옮긴다.
# 옮긴 표는 .env의 HYD_PORT_<원래 포트>=<새 포트>(compose가 읽음)와 HYD_PORTS(포털 화면이 읽음)에 적는다. Docker가 잡은 포트(이미 켜진
# 실습 스택)는 겹친 것이 아니다. 업무 DB(Supabase) 포트는 옮기지 않고, 겹치면 멈춘다.
SERVICE_PORTS="1881 1883 3000 5432 7474 7687 8000 8080 8083 8088 8090 8091 8092 8093 8094 8095 8197 8198 8199 9644 18083 19092"
DB_PORTS="54321 54322 54323 54324 54325 54326"
listen_table() {   # LISTEN 중인 "포트 프로그램" 줄. Windows(Git Bash)는 PowerShell Get-NetTCPConnection(언어와 무관), 그 밖은 ss · lsof
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      powershell.exe -NoProfile -Command "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | ForEach-Object { '' + \$_.LocalPort + ' ' + (Get-Process -Id \$_.OwningProcess -ErrorAction SilentlyContinue).ProcessName } | Sort-Object -Unique" 2>/dev/null | tr -d '\r' ;;
    *)
      if command -v ss >/dev/null 2>&1; then ss -ltnpH 2>/dev/null | awk '{n=$4; sub(/.*:/, "", n); u=$0; if (match(u, /users:\(\("[^"]*"/)) u=substr(u, RSTART+9, RLENGTH-10); else u="?"; print n, u}'
      else lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk 'NR>1{n=$9; sub(/.*:/, "", n); print n, $1}'; fi ;;
  esac
}
LISTEN=$(listen_table)
owner() { echo "$LISTEN" | awk -v p="$1" '$1==p {print $2; exit}'; }
foreign() { local o; o=$(owner "$1"); [ -n "$o" ] && ! echo "$o" | grep -qiE 'docker|com\.docker|wslrelay|vpnkit'; }
for p in $DB_PORTS; do
  foreign "$p" && die "업무 DB 포트 $p 를 다른 프로그램($(owner "$p"))이 쓰고 있습니다. 그 프로그램을 끄고 다시 실행하세요(끌 수 없으면 학교 관리자에게 알리세요)."
done
K="HYD_PORT_" awk 'index($0, ENVIRON["K"])!=1 && index($0, "HYD_PORTS=")!=1' .env > .env.tmp && mv .env.tmp .env
moved=""; taken=" $SERVICE_PORTS $DB_PORTS "
for p in $SERVICE_PORTS; do
  foreign "$p" || continue
  q=$((p + 10000)); [ "$q" -gt 65000 ] && q=$((p + 1))
  while [ "$q" -le 65535 ] && { case "$taken" in *" $q "*) true ;; *) false ;; esac || foreign "$q"; }; do q=$((q + 1)); done
  [ "$q" -le 65535 ] || die "포트 $p 를 다른 프로그램($(owner "$p"))이 쓰고 있는데 옮길 빈 포트를 찾지 못했습니다."
  echo "포트 $p 는 다른 프로그램($(owner "$p"))이 쓰고 있어 $q 로 옮깁니다."
  echo "HYD_PORT_$p=$q" >> .env; moved="$moved $p=$q"; taken="$taken$q "
done
[ -z "$moved" ] || echo "HYD_PORTS=\"${moved# }\"" >> .env

say "3/6 업무 DB(Supabase) 켜기"
if command -v supabase >/dev/null 2>&1; then SUPA=(supabase); else SUPA=(npx -y supabase); echo "supabase CLI가 없어 npx로 실행합니다(설치: npm install -g supabase@2.119.0)."; fi
( cd it/supabase && "${SUPA[@]}" start ) || die "Supabase가 켜지지 않았습니다. 'cd it/supabase && supabase stop' 뒤 다시 실행하세요(포트 54321~54329 충돌 확인)."

say "4/6 시스템 빌드 · 기동 (처음은 이미지 받기 · 빌드로 10분 넘게 걸릴 수 있습니다)"
docker compose up -d --build || die "docker compose up이 실패했습니다. 위 오류의 서비스 이름을 보고 'docker compose logs <서비스>'로 원인을 확인하세요."

say "5/6 에이전트용 MCP 서버 둘"
docker compose up -d enterprise-mcp dmn-mcp || die "enterprise-mcp · dmn-mcp가 올라오지 않았습니다."

say "6/6 상태 확인 (최대 3분 기다립니다)"
PORTS="8000 8093 8090 8094 8092 8091 8080 8095 8199 8198"
hp() { local m; m=$(awk -F= -v k="HYD_PORT_$1" '$1==k {print $2; exit}' .env); echo "${m:-$1}"; }   # 옮긴 포트가 있으면 그 포트
for i in $(seq 1 36); do
  bad=""; for p in $PORTS; do curl -s -m 3 "http://127.0.0.1:$(hp "$p")/healthz" >/dev/null 2>&1 || bad="$bad $p"; done
  [ -z "$bad" ] && break; sleep 5
done
for p in $PORTS; do printf '%s ' "$(hp "$p")"; curl -s -m 3 "http://127.0.0.1:$(hp "$p")/healthz" | head -c 120 || printf '응답 없음'; echo; done
echo "실행 중 컨테이너: 시스템 $(docker ps --format '{{.Names}}' | grep -c '^hyd-iot-edu-') · 업무 DB $(docker ps --format '{{.Names}}' | grep -c '^supabase_')"
broken=$(docker ps -a --format '{{.Names}} {{.Status}}' | grep '^hyd-iot-edu-' | grep -E 'Restarting|Exited \([1-9]' || true)
[ -z "$broken" ] || { echo "멈췄거나 계속 재시작하는 컨테이너:"; echo "$broken"; }
[ -z "$bad" ] || die "응답하지 않는 포트:$bad — 'docker compose ps'와 'docker compose logs <서비스>'로 확인하세요."
printf '\n완료. 포털: http://127.0.0.1:%s  (홈의 상태 점이 모두 초록이면 됩니다)\n' "$(hp 8088)"
[ -z "$moved" ] || printf '이 PC에서 옮긴 포트:%s\n' "$moved"
