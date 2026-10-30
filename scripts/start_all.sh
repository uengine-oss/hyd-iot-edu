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
if [ "$(uname -s)" = Darwin ]; then INSTALL_ENTRY='설치.command'; START_ENTRY='시작.command'; STOP_ENTRY='bash scripts/stop_all.sh'; fi

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
  replay) echo "AI 단계: 키가 없어 강사가 미리 진행한 결과를 재생합니다(온라인 수업). 오프라인 수업에서 키를 받았다면 .env의 LLM_API_KEY= 뒤에 넣고 $START_ENTRY 을 다시 실행하세요.";;
esac
# 프로젝트 이름 · 포트: 같은 폴더면 그대로, 옮긴 폴더면 이어받고, 다른 폴더가 쓰는 이름 · 다른 프로그램이 쓰는 포트는 피한다(까닭은 위에 출력)
"${PYTHON[@]}" scripts/prepare_ports.py || die "이 PC의 프로젝트 이름 · 포트를 준비하지 못했습니다. 바로 위의 까닭대로 고친 뒤 다시 실행하세요."
# 기본 포트 → 이 PC의 바깥 포트(.hyd-runtime/ports.json — 방금 정한 표)
PROCESS_URL="http://127.0.0.1:$("${PYTHON[@]}" scripts/prepare_ports.py port 8080)"
PORTAL="http://127.0.0.1:$("${PYTHON[@]}" scripts/prepare_ports.py port 8088)"
export PROCESS_URL

say "3/8 업무 DB(Supabase) 켜기 · 업데이트"
command -v npx >/dev/null 2>&1 || die "npx(Node.js)가 없습니다. $INSTALL_ENTRY 을 실행하세요."
SUPA=(npx -y "supabase@$SUPABASE_CLI")   # it/supabase/.env(2단계가 씀)의 이 PC 업무 DB 이름 · 포트를 CLI 가 스스로 읽는다
( cd it/supabase && "${SUPA[@]}" start >/dev/null ) || die "업무 DB(Supabase)가 켜지지 않았습니다. 위 오류에 포트가 겹친다는 내용이 있으면 $STOP_ENTRY 로 끈 뒤 다시 실행하고, 그래도 같으면 위 오류를 강사에게 알려 주세요."
# supabase start는 이미 만든 DB에 새 판의 마이그레이션을 적용하지 않는다. 새 판의 업무 시스템이 그 표를 기다리다 멈추지 않게 여기서 적용한다
( cd it/supabase && "${SUPA[@]}" migration up --local ) || die "업무 DB 업데이트(마이그레이션)가 실패했습니다. 위 오류의 파일 이름을 강사에게 알려 주세요."

say "4/8 시스템 · AI 워커 빌드 · 기동 (처음은 이미지 받기 · 빌드로 10분 넘게 걸릴 수 있습니다)"
# .env 의 AI_MODE · 포트를 쓴다. 이 창에 다른 값이 남아 있으면 그것이 이기므로 비운다
unset COMPOSE_PROFILES AI_MODE
docker compose up -d --build || die "시스템을 켜지 못했습니다. 위 오류의 서비스 이름을 보고 'docker compose logs <서비스>'로 원인을 확인하세요."

say "5/8 서비스 확인 (최대 3분 기다립니다)"
"${PYTHON[@]}" scripts/check_stack.py services --wait 180 || die "응답하지 않거나 멈춘 서비스가 있습니다(바로 위 줄). 고친 뒤 $START_ENTRY 을 다시 실행하세요."

say "6/8 수업 흐름(A 냉각 · B 정기 정비 · C 예비품 구매) 배포"
# 이미 수업 흐름으로 배포돼 있으면 건너뛴다(두 번째 실행은 아무것도 바꾸지 않는다)
"${PYTHON[@]}" scripts/c3_flows.py ensure || die "수업 흐름을 배포하지 못했습니다. 위 메시지를 강사에게 알려 주세요."

say "7/8 수업용 기본 지식(쿨러 · 정기 정비 · 구매 매뉴얼) 넣기"
# 검토를 마친 HM-8 · PM-02 · PR-07 지식을 처음 한 번 넣는다(AI를 부르지 않음, 이미 있으면 건너뜀). 4회차 인제스천은 같은 문서를 다시 올리는 과정 실습이다
"${PYTHON[@]}" scripts/class_knowledge.py ensure || die "수업용 기본 지식을 넣지 못했습니다. 위 메시지를 강사에게 알려 주세요."

say "8/8 AI 단계 확인"
# 워커가 2단계에서 정한 방식으로 켜졌는지, 키 없음이면 저장된 응답이 있는지, 키 있음이면 process 가 받은 중계 주소 · 키로 강의 중계에 닿는지
if "${PYTHON[@]}" scripts/check_stack.py ai; then
  printf '\n완료. 포털: %s  (홈의 상태 점이 모두 초록이면 됩니다)\n' "$PORTAL"
else
  printf '\n포털은 열 수 있습니다: %s\nAI 단계(판단 · 제안, 에이전트에게 질문)만 위 「실패」의 까닭을 고친 뒤 %s 을 다시 실행하면 됩니다.\n' "$PORTAL" "$START_ENTRY"
  exit 1
fi
