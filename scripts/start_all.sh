#!/usr/bin/env bash
# 실습 스택을 한 번에 켠다(학생 PC · 강사 PC 공통). setup 폴더의 시작.bat(Windows, Git Bash) · 시작.command(Mac)가 부른다.
# 하는 일: Docker 확인 → .env · 이 PC 값 준비(키 확인 → AI 단계 방식, 프로젝트 이름 · 포트) → 업무 DB(Supabase, 새 마이그레이션 적용)
#          → 시스템 · AI 워커 빌드 · 기동 → 서비스 확인 → 수업 흐름(A · B · C) 배포 → 수업용 기본 지식 → AI 단계 확인.
# 학생이 .env에 채우는 것은 LLM_API_KEY 한 줄(강의 중계 키)뿐이다. 키가 있으면 AI 단계는 실제 AI(live), 없으면 강사가 미리 진행해
# 저장소에 올린 응답(it/agent-worker/replay/)을 재생한다(replay). 이 PC 값은 git 밖(.env · .hyd-runtime/ · it/supabase/.env)에만 쓴다.
# 강사 AI 응답 저장: bash scripts/start_all.sh --record (키 필요, AI_MODE=record) — 보통은 강사용 저장 도구가 부른다.
set -euo pipefail
RECORD=''
case "${1:-}" in --record) RECORD=1;; "") ;; *) printf '[멈춤] 알 수 없는 인자: %s (쓸 수 있는 것: --record)\n' "$1" >&2; exit 1;; esac
# The distributed launcher must work independently of the Windows account's
# console/code-page defaults, including Python subprocesses printing Korean.
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
cd "$(dirname "$0")/.."

say() { printf '\n== %s\n' "$*"; }
die() { printf '\n[멈춤] %s\n' "$*" >&2; exit 1; }

. scripts/windows_paths.sh
. scripts/macos_paths.sh
. scripts/versions.txt
INSTALL_ENTRY='설치.bat'; START_ENTRY='시작.bat'; STOP_ENTRY='끄기.bat'
if [ "$(uname -s)" = Darwin ]; then INSTALL_ENTRY='설치.command'; START_ENTRY='시작.command'; STOP_ENTRY='끄기.command'; fi

# 창이 늦게 떠 두 번 누르면 두 시작이 같은 .env · 업무 DB 를 동시에 고친다 — 하나만 돌게 한다(끝나지 못한 앞 시작의 표시는 넘겨받는다)
LOCK=.hyd-runtime/start.lock
mkdir -p .hyd-runtime
if ! mkdir "$LOCK" 2>/dev/null; then
  other=$(cat "$LOCK/pid" 2>/dev/null || true)
  if [ -n "$other" ] && kill -0 "$other" 2>/dev/null; then die "다른 창에서 시작이 이미 진행 중입니다. 그 창이 끝난 뒤 필요하면 다시 실행하세요."; fi
  rm -rf "$LOCK"; mkdir "$LOCK"
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

say "1/8 Docker 확인"
if [ "$(uname -s)" = Darwin ] && ! docker info >/dev/null 2>&1; then
  echo 'Docker Desktop을 엽니다. 초기 설정·약관 동의를 완료하세요(최대 3분 대기).'
  open -a Docker || die "Docker Desktop을 열지 못했습니다. $INSTALL_ENTRY 로 설치를 확인하세요."
  for i in $(seq 1 36); do docker info >/dev/null 2>&1 && break; sleep 5; done
fi
if ! docker info >/dev/null 2>&1 && [ -n "${DD_EXE:-}" ] && [ -f "$DD_EXE" ]; then   # Windows(Git Bash): 꺼져 있으면 켜고 엔진이 뜰 때까지 기다린다
  echo "Docker Desktop을 켭니다. 엔진이 준비될 때까지 최대 3분 기다립니다."
  HYD_DOCKER_DESKTOP_EXE="$(cygpath -w "$DD_EXE")" powershell.exe -NoProfile -Command 'Start-Process -WindowStyle Hidden -FilePath $env:HYD_DOCKER_DESKTOP_EXE' >/dev/null 2>&1
  for i in $(seq 1 36); do docker info >/dev/null 2>&1 && break; sleep 5; done
fi
command -v docker >/dev/null 2>&1 || die "docker 명령이 없습니다. $INSTALL_ENTRY 으로 Docker Desktop 설치를 확인하세요."
docker info >/dev/null 2>&1 || die "Docker가 응답하지 않습니다. Docker Desktop을 열어 약관 동의 창이 있으면 동의하고, 'Engine running'이 된 뒤 다시 실행하세요."
docker compose version >/dev/null 2>&1 || die "docker compose가 없습니다. Docker Desktop을 최신으로 설치하세요."
# 이 시스템의 이미지는 모두 Linux 컨테이너다. Windows 컨테이너 모드에서는 이미지 받기가 뜻 모를 오류(no matching manifest)로 멈춘다
[ "$(docker info --format '{{.OSType}}' 2>/dev/null)" = linux ] || die "Docker Desktop이 Windows 컨테이너 모드입니다. 작업 표시줄의 Docker 아이콘을 오른쪽 클릭해 'Switch to Linux containers...'를 누르고, 바뀐 뒤 다시 실행하세요."
echo "ok"

say "2/8 .env · 이 PC 값 준비"
[ -f .env ] || { cp .env.example .env; echo ".env.example을 복사해 .env를 만들었습니다."; }
. scripts/find_python.sh
[ "${#PYTHON[@]}" -gt 0 ] || die "Python $PYTHON_MIN 이상이 필요합니다. $INSTALL_ENTRY 을 실행하세요."
# 키 유무는 .env 해석기 한 벌(scripts/hyd_env.py — Docker Compose 와 같은 규칙)로만 본다. 키 값은 화면에 내지 않는다
AI_MODE_WANT=$("${PYTHON[@]}" scripts/hyd_env.py ai-mode ${RECORD:+--record}) || die "AI 단계 방식을 정하지 못했습니다. 바로 위의 안내대로 .env를 고친 뒤 다시 실행하세요."
case "$AI_MODE_WANT" in
  record) echo "AI 단계: 응답 저장(실제 AI로 진행하며 응답을 it/agent-worker/replay/ 에 저장)";;
  live) echo "AI 단계: 실제 AI(강의 중계)";;
  replay) echo "AI 단계: AI 키가 없어 준비된 응답을 재생합니다. 키를 받았다면 .env의 LLM_API_KEY= 뒤에 넣고 $START_ENTRY 을 다시 실행하세요.";;
esac
# 프로젝트 이름 · 포트: 같은 폴더면 그대로, 옮긴 폴더면 이어받고, 다른 폴더가 쓰는 이름 · 다른 프로그램이 쓰는 포트는 피한다(까닭은 위에 출력)
"${PYTHON[@]}" scripts/prepare_ports.py || die "이 PC의 프로젝트 이름 · 포트를 준비하지 못했습니다. 바로 위의 까닭대로 고친 뒤 다시 실행하세요."
# 기본 포트 → 이 PC의 바깥 포트(.hyd-runtime/ports.json — 방금 정한 표. 6 · 7 · 8단계 스크립트도 이 표에서 process 주소를 찾는다)
PORTAL="http://127.0.0.1:$("${PYTHON[@]}" scripts/prepare_ports.py port 8088)"

say "3/8 업무 DB(Supabase) 켜기 · 업데이트"
command -v npx >/dev/null 2>&1 || die "npx(Node.js)가 없습니다. $INSTALL_ENTRY 을 실행하세요."
SUPA=(npx -y "supabase@$SUPABASE_CLI")   # it/supabase/.env(2단계가 씀)의 이 PC 업무 DB 이름 · 포트를 CLI 가 스스로 읽는다
( cd it/supabase && "${SUPA[@]}" start >/dev/null ) || die "업무 DB(Supabase)가 켜지지 않았습니다. 위 오류에 포트가 겹친다는 내용(port is already allocated)이 있으면 $STOP_ENTRY 로 끈 뒤 다시 실행하세요. 이미지를 받다가 멈췄으면(timeout · connection · TLS) 인터넷 연결을 확인하고 다시 실행하세요 — 받은 데까지는 이어서 받습니다. 그래도 같으면 위 오류를 강사에게 알려 주세요."
# supabase start는 이미 만든 DB에 새 판의 마이그레이션을 적용하지 않는다. 새 판의 업무 시스템이 그 표를 기다리다 멈추지 않게 여기서 적용한다
( cd it/supabase && "${SUPA[@]}" migration up --local ) || die "업무 DB 업데이트(마이그레이션)가 실패했습니다. 도움을 요청할 때 위 오류의 파일 이름을 그대로 전해 주세요."

say "4/8 시스템 · AI 워커 빌드 · 기동 (처음은 이미지 받기 · 빌드로 10분 넘게 걸릴 수 있습니다)"
# .env 의 AI_MODE · 포트를 쓴다. 이 창에 다른 값이 남아 있으면 그것이 이기므로 비운다
unset COMPOSE_PROFILES AI_MODE
if ! docker compose up -d --build; then
  # 지식 지도 준비(kg-seed)가 내용 검사에서 멈췄으면 그 까닭과 되돌리는 길을 말한다 — AI 판단 서비스(agent · dmn-mcp)는 이 준비가 끝나야 켜진다.
  # 검사는 기본 제공 지식과 적재한 문서 지식이 서로 이어져 있는지를 본다: 지식 지도를 Neo4j Browser 등으로 직접 고치면(관계 · 항목 지우기) 걸린다
  seed_log=$(docker compose logs --no-log-prefix --tail 60 kg-seed 2>/dev/null || true)
  if printf '%s\n' "$seed_log" | grep -q 'kg-seed FAILED read-back'; then
    printf '\n지식 지도 내용 검사가 짚은 곳:\n' >&2
    printf '%s\n' "$seed_log" | grep -E '^CHECK (FAILED|ERROR)' | sed 's/^/  /' >&2 || true
    kg_volume=$(docker volume ls -q --filter label=com.docker.compose.volume=neo4j-data --filter "label=com.docker.compose.project=$(docker compose config --format json 2>/dev/null | "${PYTHON[@]}" -c 'import json,sys; print(json.load(sys.stdin)["name"])' 2>/dev/null)" | head -1 || true)
    die "지식 지도의 내용 검사가 실패해 AI 판단 서비스(agent · dmn-mcp)를 켜지 않았습니다. 위 줄이 짚은 항목은 서로 이어져 있어야 하는 지식(고장 유형 · 원인 · 조치 방법 등)인데 이어진 선이나 항목이 빠져 있습니다 — 지식 지도를 Neo4j Browser 등에서 직접 고쳤다면 그 변경이 까닭입니다. 되돌리는 길 (1) 지운 것을 Neo4j Browser에서 다시 만든 뒤 $START_ENTRY 을 다시 실행합니다. (2) 다시 만들 수 없으면 지식 지도를 비우고 처음부터 채웁니다: $STOP_ENTRY 실행 → 터미널에서 'docker compose down' 과 'docker volume rm ${kg_volume:-<프로젝트 이름>_neo4j-data}' → $START_ENTRY 실행. 기본 제공 지식은 다시 들어가고, 직접 적재한 문서 · 표 정의 · 화면에서 만든 조치 방법은 다시 넣어야 합니다(업무 DB의 처리 건 기록은 그대로입니다)."
  fi
  die "시스템을 켜지 못했습니다. 위 오류가 무엇인지에 따라: 이미지 받기 · 빌드 중 네트워크 오류(pull · pip · timeout · TLS)면 인터넷 연결을 확인하고 다시 실행하세요(받은 데까지는 이어집니다). 'port is already allocated'면 $STOP_ENTRY 로 끈 뒤 다시 실행하세요. 어떤 서비스가 unhealthy · exited 로 나오면 'docker compose logs <그 서비스 이름>'의 마지막 줄이 까닭입니다."
fi
# 새 판이 compose 에서 뺀 볼륨은 down -v 도 지우지 않는다 — 옛 컨테이너가 새 판으로 바뀐 지금 지운다(지울 이름은 prepare_ports.py 의 표 하나)
"${PYTHON[@]}" scripts/prepare_ports.py retire || die "지금 판이 쓰지 않는 옛 볼륨을 정리하지 못했습니다. 도움을 요청할 때 바로 위의 까닭을 그대로 전해 주세요."

say "5/8 서비스 확인 (최대 3분 기다립니다)"
"${PYTHON[@]}" scripts/check_stack.py services --wait 180 || die "응답하지 않거나 멈춘 서비스가 있습니다(바로 위 줄). 고친 뒤 $START_ENTRY 을 다시 실행하세요."

say "6/8 기본 제공 흐름(A 냉각 · B 정기 정비 · C 예비품 구매) 배포"
# 이미 수업 흐름으로 배포돼 있으면 건너뛴다(두 번째 실행은 아무것도 바꾸지 않는다)
"${PYTHON[@]}" scripts/c3_flows.py ensure || die "기본 제공 흐름을 배포하지 못했습니다. 도움을 요청할 때 위 메시지를 그대로 전해 주세요."

say "7/8 기본 지식(쿨러 · 정기 정비 · 구매 매뉴얼) 넣기"
# 검토를 마친 HM-8 · PM-02 · PR-07 지식을 처음 한 번 넣는다(AI를 부르지 않음, 이미 있으면 건너뜀). 4회차 인제스천은 같은 문서를 다시 올리는 과정 실습이다
"${PYTHON[@]}" scripts/class_knowledge.py ensure || die "기본 지식을 넣지 못했습니다. 도움을 요청할 때 위 메시지를 그대로 전해 주세요."

say "8/8 AI 단계 확인"
# 워커가 2단계에서 정한 방식으로 켜졌는지, 키 없음이면 저장된 응답이 있는지, 키 있음이면 process 가 받은 중계 주소 · 키로 강의 중계에 닿는지
if "${PYTHON[@]}" scripts/check_stack.py ai; then
  printf '\n완료. 포털: %s  (왼쪽 메뉴 맨 아래 「서비스 상태」 점이 초록이면 됩니다)\n' "$PORTAL"
else
  printf '\n포털은 열 수 있습니다: %s\nAI 단계(판단 · 제안, 에이전트에게 질문)만 위 「실패」의 까닭을 고친 뒤 %s 을 다시 실행하면 됩니다.\n' "$PORTAL" "$START_ENTRY"
  exit 1
fi
