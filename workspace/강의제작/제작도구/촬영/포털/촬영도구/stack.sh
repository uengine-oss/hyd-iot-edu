#!/bin/bash
# 클라우드 세션의 포털 스택 점검 · 복구(촬영 전 · 세션 컨테이너가 다시 시작된 뒤). 데이터는 지우지 않는다.
#   ./stack.sh check   상태만 본다(아무것도 켜지 않음)
#   ./stack.sh up      꺼진 것만 순서대로 켠다: dockerd → /etc/hosts → Supabase → compose(+MCP) → 호스트 워커 → 녹화 브라우저
#   ./stack.sh up --build   main을 새로 병합한 뒤: 앱 이미지를 다시 빌드하고 바뀐 컨테이너를 다시 만든다(+ 업무 DB 새 마이그레이션 적용, 데이터 유지)
# 세션 컨테이너가 다시 시작되면(uptime이 짧음) dockerd · /etc/hosts 줄 · 워커 · 녹화 브라우저가 모두 사라진다. 볼륨 · 이미지는 남는다.
# compose는 저장소 루트(main 체크아웃)에서 띄운다. 체크아웃이 origin/main보다 뒤면 옛 코드로 뜨므로 멈춘다.
set -u
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../../../../../.." && pwd)"
ev="$root/작업/촬영/포털/stack-$(date +%Y%m%d)"; mkdir -p "$ev"
mode=${1:-check}; build=${2:-}
ok(){ printf '  ✓ %s\n' "$*"; }; bad(){ printf '  ✗ %s\n' "$*"; }
wait_for(){ for i in $(seq 1 "$2"); do eval "$1" >/dev/null 2>&1 && return 0; sleep 2; done; return 1; }

echo "[세션] $(uptime -p) · 저장소 $root"
# 1 Docker
if docker info >/dev/null 2>&1; then ok "dockerd"
elif [ "$mode" = up ]; then (setsid nohup dockerd >/tmp/dockerd.log 2>&1 < /dev/null &); wait_for "docker info" 40 && ok "dockerd 켬" || { bad "dockerd 안 켜짐(/tmp/dockerd.log)"; exit 1; }
else bad "dockerd 꺼짐"; fi
# 2 워커가 업무 DB(host.docker.internal)에 붙으려면 필요한 줄(세션 재시작 때 사라짐)
if grep -q "host.docker.internal" /etc/hosts; then ok "/etc/hosts host.docker.internal"
elif [ "$mode" = up ]; then echo "127.0.0.1 host.docker.internal" >> /etc/hosts && ok "/etc/hosts 줄 넣음"
else bad "/etc/hosts 줄 없음"; fi
docker info >/dev/null 2>&1 || exit 1
# 3 코드 판본: 체크아웃이 origin/main을 포함하는지
git -C "$root" fetch -q origin main 2>/dev/null
if git -C "$root" merge-base --is-ancestor origin/main HEAD 2>/dev/null; then ok "체크아웃이 origin/main 포함($(git -C "$root" rev-parse --short origin/main))"
else bad "체크아웃이 origin/main보다 뒤 — git pull 뒤 이미지를 다시 빌드하고 띄운다(docker compose build)"; [ "$mode" = up ] && exit 1; fi
# 4 Supabase(업무 DB)
if docker ps --format '{{.Names}}' | grep -q '^supabase_db_'; then ok "Supabase"
elif [ "$mode" = up ]; then (cd "$root/it/supabase" && npx -y supabase@2.119.0 start > "$ev/supabase-start.log" 2>&1) && ok "Supabase 켬" || { bad "Supabase 실패($ev/supabase-start.log, ghcr 403이면 다시 실행)"; exit 1; }
else bad "Supabase 꺼짐"; fi
# 4-1 main을 새로 병합했으면: 새 마이그레이션(함수 · 제약 교체, 데이터 유지)과 앱 이미지 다시 빌드. 빌드 안 pip는 프록시 CA를 넣은 베이스 이미지가 필요(CLAUDE.md 5절)
if [ "$mode" = up ] && [ "$build" = --build ]; then
  (cd "$root/it/supabase" && npx -y supabase@2.119.0 migration up > "$ev/migration-up.log" 2>&1) && ok "업무 DB 마이그레이션 적용" || { bad "마이그레이션 실패($ev/migration-up.log)"; exit 1; }
  (cd "$root" && docker compose -p hyd-iot-edu build agent enterprise-sim process && docker compose -p hyd-iot-edu build dmn-mcp enterprise-mcp) > "$ev/build.log" 2>&1 && ok "이미지 다시 빌드" || { bad "빌드 실패($ev/build.log, CERTIFICATE_VERIFY_FAILED면 프록시 CA 베이스 이미지)"; exit 1; }
  force=1
fi
# 5 compose(+ 프로필 cliagents의 MCP 두 개). 세션 환경변수가 .env보다 우선하므로 WORKER_URL은 명령 앞에 둔다
n=$(docker ps --filter "label=com.docker.compose.project=hyd-iot-edu" --format '{{.Names}}' | wc -l)
if [ "$n" -ge 18 ] && [ -z "${force:-}" ]; then ok "compose 컨테이너 $n개"
elif [ "$mode" = up ]; then (cd "$root" && WORKER_URL=http://host.docker.internal:8097 docker compose -p hyd-iot-edu up -d && WORKER_URL=http://host.docker.internal:8097 docker compose -p hyd-iot-edu up -d --no-deps enterprise-mcp dmn-mcp) > "$ev/up.log" 2>&1 \
  && ok "compose 켬($(docker ps --filter label=com.docker.compose.project=hyd-iot-edu -q | wc -l)개)" || { bad "compose 실패($ev/up.log)"; exit 1; }
else bad "compose 컨테이너 $n개"; fi
[ "$mode" = up ] && wait_for "curl -sf -m3 http://127.0.0.1:8080/healthz" 60
for s in "8080 process" "8091 agent" "8092 detector" "8090 gateway" "8000 plant"; do set -- $s
  curl -sf -m3 "http://127.0.0.1:$1/healthz" >/dev/null && ok "$2 healthz" || bad "$2 healthz($1) 응답 없음"; done
curl -sf -m3 -o /dev/null http://127.0.0.1:8088/ && ok "포털 :8088" || bad "포털 :8088 응답 없음"
# 6 호스트 워커(에이전트 추출 · 판단을 실제로 하는 쪽). 강의 배포본도 호스트 워커 1개(RUNBOOK ⑤)
if curl -sf -m3 http://127.0.0.1:8097/healthz >/dev/null; then ok "워커 :8097"
elif [ "$mode" = up ]; then (cd "$root" && setsid nohup bash workspace/개발/scripts/run_worker_host.sh > "$ev/worker-8097.log" 2>&1 < /dev/null &); wait_for "curl -sf -m3 http://127.0.0.1:8097/healthz" 30 && ok "워커 켬(로그 $ev/worker-8097.log)" || bad "워커 안 켜짐($ev/worker-8097.log)"
else bad "워커 꺼짐"; fi
# 7 녹화 브라우저
port=$(python3 -c "import json;print(json.load(open('$here/config.json'))['cdp'])")
if curl -sf -m2 "http://127.0.0.1:$port/json/version" >/dev/null; then ok "녹화 브라우저 :$port"
elif [ "$mode" = up ]; then "$here/run.sh" up >/dev/null && ok "녹화 브라우저 켬" || bad "녹화 브라우저 실패"
else bad "녹화 브라우저 꺼짐"; fi
# 8 데이터 상태(촬영 시작 전 깨끗한지): 처리 건 · 보관 원문 · 열린 사건
python3 - <<'PY'
import json, urllib.request
def get(u):
    try: return json.load(urllib.request.urlopen(u, timeout=5))
    except Exception as e: return {'error': str(e)}
i = get('http://127.0.0.1:8080/api/instances?limit=50'); s = get('http://127.0.0.1:8080/api/kg/manuals/sources')
items = i.get('items', i) if isinstance(i, dict) else i
src = s.get('items', s) if isinstance(s, dict) else s
print(f"[데이터] 처리 건 {len(items) if isinstance(items, list) else items} · 보관 원문 {len(src) if isinstance(src, list) else src}"
      " (둘 다 0이어야 처음부터 찍을 수 있다. 아니면 촬영준비.md 1절 2번 「데이터 초기화」)")
PY
