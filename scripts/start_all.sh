#!/usr/bin/env bash
# 실습 스택을 한 번에 켠다(학생 PC · 강사 PC 공통, Windows는 Git Bash). 저장소 루트에서:
#   bash scripts/start_all.sh
# 하는 일: Docker 확인 → .env 준비(강의 배포본 값 + 키 확인) → 업무 DB(Supabase, 새 마이그레이션 적용) → 시스템 · AI 워커 빌드 · 기동
#          → 상태 확인 → 수업 흐름(A · B · C) 배포 → 수업용 기본 지식(검토한 수업 문서 셋) → 강의 중계 키 확인.
# 학생이 채우는 것은 .env의 LLM_API_KEY 한 줄이다(강의 중계 키). 포털의 AI 단계(판단 · 제안, 에이전트에게 질문, 매뉴얼 추출)는
# AI 워커 컨테이너가 이 키로 강의 중계를 부른다. 키가 비어 있으면 2단계에서 멈춘다.
# 끌 때: bash scripts/stop_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\n== %s\n' "$*"; }
die() { printf '\n[멈춤] %s\n' "$*" >&2; exit 1; }

say "1/8 Docker 확인"
DD_EXE="/c/Program Files/Docker/Docker/Docker Desktop.exe"
DD_BIN="/c/Program Files/Docker/Docker/resources/bin"
[ -d "$DD_BIN" ] && PATH="$PATH:$DD_BIN"   # 설치 직후 PATH에 아직 없을 때
. scripts/windows_paths.sh
. scripts/macos_paths.sh
INSTALL_ENTRY='설치.bat'
if [ "$(uname -s)" = Darwin ]; then
  INSTALL_ENTRY='설치.command'
  if ! docker info >/dev/null 2>&1; then
    echo 'Docker Desktop을 엽니다. 초기 설정·약관 동의를 완료하세요(최대 3분 대기).'
    open -a Docker || die 'Docker Desktop을 열지 못했습니다. 설치.command로 설치를 확인하세요.'
    for i in $(seq 1 36); do docker info >/dev/null 2>&1 && break; sleep 5; done
  fi
fi
if ! docker info >/dev/null 2>&1 && [ -f "$DD_EXE" ]; then   # Windows(Git Bash): 꺼져 있으면 켜고 엔진이 뜰 때까지 기다린다
  echo "Docker Desktop을 켭니다. 엔진이 준비될 때까지 최대 3분 기다립니다."
  HYD_DOCKER_DESKTOP_EXE="$(cygpath -w "$DD_EXE")" powershell.exe -NoProfile -Command 'Start-Process -WindowStyle Hidden -FilePath $env:HYD_DOCKER_DESKTOP_EXE' >/dev/null 2>&1
  for i in $(seq 1 36); do docker info >/dev/null 2>&1 && break; sleep 5; done
fi
command -v docker >/dev/null 2>&1 || die "docker 명령이 없습니다. $INSTALL_ENTRY 으로 Docker Desktop 설치를 확인하세요."
docker info >/dev/null 2>&1 || die "Docker가 응답하지 않습니다. Docker Desktop을 열어 약관 동의 창이 있으면 동의하고, 'Engine running'이 된 뒤 다시 실행하세요."
docker compose version >/dev/null 2>&1 || die "docker compose가 없습니다. Docker Desktop을 최신으로 설치하세요."
echo "ok"

say "2/8 .env 준비"
[ -f .env ] || { cp .env.example .env; echo ".env.example을 복사해 .env를 만들었습니다."; }
env_get() { awk -F= -v k="$1" 'index($0, k "=")==1 {sub(/^[^=]*=/, ""); v=$0} END{print v}' "${2:-.env}" | tr -d '\r'; }
llm_key() { env_get LLM_API_KEY | tr -d "[:space:]\"'"; }   # 앞뒤 공백 · 따옴표를 뺀 키(화면에 내지 않는다)
set_env() {   # KEY VALUE — 줄이 있으면 바꾸고 없으면 붙인다(값의 특수 문자를 그대로 두려고 sed 대신 awk + ENVIRON)
  K="$1" V="$2" awk 'BEGIN{k=ENVIRON["K"]; v=ENVIRON["V"]; done=0}
    index($0, k "=")==1 {print k "=" v; done=1; next} {print}
    END{if(!done) print k "=" v}' .env > .env.tmp && mv .env.tmp .env
}
# 앞 판의 .env(키 말고 옛 값)를 가진 PC도 같은 구성이 되게 강의 배포본 값을 보장한다(RUNBOOK §0). 값은 .env.example 한 곳에서 읽는다
for k in PROCESS_MODE ENTERPRISE_BACKEND AGENT_BRIDGE WORKER_URL COMPOSE_PROFILES; do set_env "$k" "$(env_get "$k" .env.example)"; done
# 중계 주소 · 모델: 비었거나 옛 기본값(api.openai.com)이면 예시 값으로. 강사가 다른 중계를 적어 둔 것은 그대로 둔다
case "$(env_get OPENAI_BASE_URL)" in ""|*api.openai.com*) set_env OPENAI_BASE_URL "$(env_get OPENAI_BASE_URL .env.example)";; esac
[ -n "$(env_get LLM_RELAY_URL)" ] || set_env LLM_RELAY_URL "$(env_get LLM_RELAY_URL .env.example)"
[ -n "$(env_get LLM_MODEL)" ] || set_env LLM_MODEL "$(env_get LLM_MODEL .env.example)"
echo "ok (PROCESS_MODE=instance, ENTERPRISE_BACKEND=supabase, AGENT_BRIDGE=off, AI 워커 포함)"
# 키는 이름만 본다(값을 화면에 내지 않는다)
[ -n "$(llm_key)" ] || die ".env의 LLM_API_KEY가 비어 있습니다. 수업에서 받은 강의 중계 키를 .env의 LLM_API_KEY= 뒤에 붙여 넣고 저장한 뒤 시작.bat을 다시 실행하세요."

# Compose · 업무 DB · 포털 · 점검이 같은 포트 표를 사용한다.
# 실행 중인 이 프로젝트의 포트만 재사용하고, 다른 앱/컨테이너와 겹치면 빈 포트로 옮긴다.
PYTHON=()
for candidate in python python3 /opt/homebrew/opt/python@3.14/bin/python3.14 /usr/local/opt/python@3.14/bin/python3.14 \
  /Library/Frameworks/Python.framework/Versions/*/bin/python3 \
  "${local_apps:-/nonexistent}"/Programs/Python/Python*/python.exe "${program_files:-/nonexistent}"/Python*/python.exe; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert sys.version_info >= (3, 14, 7)' >/dev/null 2>&1; then
    PYTHON=("$candidate"); break
  fi
done
if [ "${#PYTHON[@]}" -eq 0 ] && command -v py >/dev/null 2>&1 && py -3 -c 'import sys; assert sys.version_info >= (3, 14, 7)' >/dev/null 2>&1; then PYTHON=(py -3); fi
[ "${#PYTHON[@]}" -gt 0 ] || die "Python 3.14.7 이상이 필요합니다. $INSTALL_ENTRY 을 실행하세요."
"${PYTHON[@]}" scripts/prepare_ports.py || die "포트를 준비하지 못했습니다. Docker 상태와 폴더 쓰기 권한을 확인하세요."

say "3/8 업무 DB(Supabase) 켜기 · 업데이트"
SUPA=(npx -y supabase@2.119.0)
( cd it/supabase && "${SUPA[@]}" start >/dev/null ) || die "Supabase가 켜지지 않았습니다. 'cd it/supabase && supabase stop' 뒤 다시 실행하세요(위 포트 배정 결과와 오류 확인)."
# supabase start는 이미 만든 DB에 git pull로 새로 받은 마이그레이션을 적용하지 않는다. 새 판의 업무 시스템이 그 표를 기다리다 멈추지 않게 여기서 적용한다
( cd it/supabase && "${SUPA[@]}" migration up --local ) || die "업무 DB 업데이트(마이그레이션)가 실패했습니다. 위 오류의 파일 이름을 강사에게 알려 주세요."

say "4/8 시스템 · AI 워커 빌드 · 기동 (처음은 이미지 받기 · 빌드로 10분 넘게 걸릴 수 있습니다)"
# .env의 COMPOSE_PROFILES(cliagents 포함)를 쓴다. 이 창에 다른 값이 남아 있으면 그것이 이기므로 비운다
unset COMPOSE_PROFILES
docker compose up -d --build || die "docker compose up이 실패했습니다. 위 오류의 서비스 이름을 보고 'docker compose logs <서비스>'로 원인을 확인하세요."

say "5/8 상태 확인 (최대 3분 기다립니다)"
PORTS="8000 8093 8090 8094 8092 8091 8080 8095 8199 8198 8196 8195 8097"
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

say "6/8 수업 흐름(A 냉각 · B 정기 정비 · C 예비품 구매) 배포"
# 이미 수업 흐름으로 배포돼 있으면 건너뛴다(두 번째 실행은 아무것도 바꾸지 않는다)
PROCESS_URL="http://127.0.0.1:$(hp 8080)" "${PYTHON[@]}" scripts/c3_flows.py ensure || die "수업 흐름을 배포하지 못했습니다. 위 메시지를 강사에게 알려 주세요."

say "7/8 수업용 기본 지식(쿨러 · 정기 정비 · 구매 매뉴얼) 넣기"
# 검토를 마친 HM-8 · PM-02 · PR-07 지식을 처음 한 번 넣는다(AI를 부르지 않음, 이미 있으면 건너뜀). 4회차 인제스천은 같은 문서를 다시 올리는 과정 실습이다
PROCESS_URL="http://127.0.0.1:$(hp 8080)" "${PYTHON[@]}" scripts/class_knowledge.py ensure || die "수업용 기본 지식을 넣지 못했습니다. 위 메시지를 강사에게 알려 주세요."

say "8/8 강의 중계 키 확인"
if [ -n "$(env_get HYD_CLASSROOM_URL)" ]; then
  printf '%s' "$(llm_key)" | "${PYTHON[@]}" scripts/check_classroom.py "$(env_get HYD_CLASSROOM_URL)" || die "관리 서버 수업 접속을 확인하지 못했습니다. 직접 모델 중계로 우회하지 않습니다."
else
# 키는 명령줄에 싣지 않고 표준 입력으로 헤더를 넘긴다(작업 관리자 · 로그에 남지 않게).
# 중계가 한동안 쉬었다 깨어날 때는 첫 연결이 수십 초 멈출 수 있어(2026-10-25 실측) 세 번까지 다시 묻는다
for attempt in 1 2 3; do
  code=$(printf 'Authorization: Bearer %s\n' "$(llm_key)" |
    curl -s -o /dev/null -w '%{http_code}' -m 30 -H @- "$(env_get OPENAI_BASE_URL | sed 's:/*$::')/models" || true)
  case "$code" in 200|401|403) break;; esac
  [ "$attempt" = 3 ] || { echo "중계 응답 ${code:-없음} — 다시 묻습니다($attempt/3)"; sleep 5; }
done
case "$code" in
  200) echo "ok (강의 중계 연결됨 · 모델 $(env_get LLM_MODEL))";;
  401|403) die "강의 중계가 키를 받지 않습니다($code). .env의 LLM_API_KEY가 수업에서 받은 키와 같은지(앞뒤 공백 · 따옴표 없이) 확인하고 시작.bat을 다시 실행하세요. 다른 실습은 포털에서 그대로 할 수 있습니다.";;
  *) die "강의 중계에 닿지 않습니다(응답 ${code:-없음}). 인터넷 연결을 확인하고 시작.bat을 다시 실행하세요. 포털의 AI 단계(판단 · 제안, 질문, 매뉴얼 추출)만 막히고 나머지는 동작합니다.";;
esac
fi
printf '\n완료. 포털: http://127.0.0.1:%s  (홈의 상태 점이 모두 초록이면 됩니다)\n' "$(hp 8088)"
echo "포트 설정 저장: .hyd-runtime/ports.json (점검.bat이 자동으로 읽습니다)"
