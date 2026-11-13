#!/bin/bash
# ARROWS 녹화 실행기. 환경은 셋이다: cloud(리눅스, browser.mjs가 띄운 헤드리스 Chromium에 Playwright로 붙음) · pc(이 PC Windows, 같은 길) · ego(이 PC ego 브라우저 안).
# 환경은 ARROWS_ENV=cloud|pc|ego로 고르고, 주지 않으면 리눅스는 cloud, Windows(Git Bash)는 pc다. 환경마다 다른 값은 config.json의 그 환경 칸에만 둔다(env.mjs가 읽는다).
#   ./run.sh up | down                                              cloud · pc: 녹화 브라우저 띄우기 · 끄기(구간 사이 그림 · 저장소 유지)
#   ./run.sh open [주소]                                            cloud · pc: 녹화 탭을 그 주소로(기본 https://arrows.app 첫 화면, 녹화 밖). 검색 화면에서 시작하는 구간은 검색 사이트 주소를 준다
#   ./run.sh rec <이름> <구간> [시작큐] [이전 구간 이름] [relax]   구간 하나 녹화(relax: 그림 주소가 바뀐 뒤 첫 구간. VIEW={"scale":…,"dx":…,"dy":…}이면 녹화 전 보기를 그 값으로. EXPECT=<주소 조각>이면 시작 주소를 그 값으로 검사 — 기본 arrows.app)
#   ./run.sh restore <이전 구간 이름> [출발원 도착원]               녹화 밖 상태 복원(가져오기 + 원 크기 + 마지막 화살표 선택)
#   ./run.sh coords                                                  사용자가 배치한 그림들의 저장 좌표 읽기(읽기 전용)
# 실행 전 node --check로 문법 오류를 막고(ego는 문법 오류에 조용히 멈춘다), stdin을 닫는다(-e가 입력을 기다린다).
# 시간 초과(TMO초, 기본 600): ego는 NodeService(스크립트 실행기)만 정리하고, cloud · pc는 그 녹화만 끊는다. 브라우저 창 · 탭은 건드리지 않는다.
set -u
linux=false; [ "$(uname -s)" = Linux ] && linux=true
env=${ARROWS_ENV:-$($linux && echo cloud || echo pc)}
case "$env" in cloud|pc|ego) ;; *) echo "ARROWS_ENV=$env: cloud | pc | ego 가운데 하나"; exit 2;; esac
export ARROWS_ENV=$env
pw=true; [ "$env" = ego ] && pw=false   # pw = Playwright 길(cloud · pc)
if $linux; then here="$(cd "$(dirname "$0")" && pwd)"; PY=python3; pre="file://"; else here="$(cd "$(dirname "$0")" && pwd -W)"; PY=${PY:-python}; pre="file:///"; fi
work="$(PYTHONUTF8=1 $PY -c "import sys;sys.path.insert(0,r'$here');from common import WORK;print(WORK.as_posix())")"
port=$($PY -c "import json;print(json.load(open(r'$here/config.json',encoding='utf-8')).get('$env',{}).get('cdp',''))")
for f in ctrl.mjs ui.mjs restore.mjs env.mjs pw.mjs browser.mjs; do node --check "$here/$f" || { echo "SYNTAX ERROR in $f: 보내지 않음"; exit 2; }; done
cmd=${1:-}; shift || true
stamp=$(date +%s)
alive(){ curl -s -m 2 "http://127.0.0.1:$port/json/version" >/dev/null; }
case "$cmd" in
  up)
    $pw || { echo "up은 cloud · pc 전용(ego는 ego 창을 쓴다)"; exit 2; }
    alive && { echo "already up :$port"; exit 0; }
    mkdir -p "$work"
    # 리눅스는 setsid로 떼어 띄우고 그 PID를 남긴다. Windows(Git Bash)에는 setsid가 없고 $!가 MSYS 번호라, browser.mjs가 찍은 Windows PID를 로그에서 읽어 남긴다.
    if $linux; then (setsid nohup node "$here/browser.mjs" > "$work/browser.log" 2>&1 < /dev/null & echo $! > "$work/browser.pid")
    else (nohup node "$here/browser.mjs" > "$work/browser.log" 2>&1 < /dev/null &); fi
    for i in $(seq 1 30); do alive && grep -q '"ready":true' "$work/browser.log" && { $linux || grep -o '"pid":[0-9]*' "$work/browser.log" | tail -1 | cut -d: -f2 > "$work/browser.pid"; tail -1 "$work/browser.log"; exit 0; }; sleep 1; done
    echo "browser did not start"; cat "$work/browser.log"; exit 1;;
  down)
    $pw || { echo "down은 cloud · pc 전용"; exit 2; }
    # 한글 경로는 pkill -f가 못 찾으므로 띄울 때 남긴 PID로 끈다(자식 Chromium도 함께 끝남). Windows는 taskkill로 자식까지 끈다.
    if [ -f "$work/browser.pid" ]; then if $linux; then kill "$(cat "$work/browser.pid")" 2>/dev/null; else taskkill //PID "$(cat "$work/browser.pid")" //T //F >/dev/null 2>&1; fi; fi; sleep 2
    alive && { echo "STILL UP :$port"; exit 1; } || echo "down"; exit 0;;
  open)
    $pw || { echo "open은 cloud · pc 전용"; exit 2; }
    url=${1:-https://arrows.app}
    js="const {taskSpace}=await import('$pre$here/pw.mjs?$stamp');const p=(await taskSpace()).page();await p.goto('$url',{waitUntil:'load',timeout:60000});if((await p.url()).includes('arrows.app'))await p.waitForSelector('canvas');await p.waitForTimeout(1500);console.log(JSON.stringify({url:await p.url(),text:(await p.evaluate(()=>document.body.innerText)).slice(0,80)}));"
    log="$work/open-$stamp.log";;
  rec)
    n=$1; seg=$2; from=${3:-}; st=${4:-}; relax=false; [ -n "${5:-}" ] && relax=true
    mkdir -p "$work"
    js="const {run}=await import('$pre$here/ctrl.mjs?$n');console.log(JSON.stringify(await run({name:'$n',segment:$seg,from:'$from',startState:'$st',expectUrl:'${EXPECT:-arrows.app}',to:'${TO:-}',relaxUrl:$relax,view:${VIEW:-null}})));"
    log="$work/$n.log";;
  restore)
    take=$1; e1=${2:-}; e2=${3:-}
    edge=$([ -n "$e1" ] && echo "['$e1','$e2']" || echo "null")
    js="const {restore}=await import('$pre$here/restore.mjs?$stamp');console.log(JSON.stringify(await restore({take:'$take',edge:$edge})));"
    log="$work/restore-$stamp.log";;
  coords)
    js="const {coords}=await import('$pre$here/restore.mjs?$stamp');console.log(JSON.stringify(await coords()));"
    log="$work/coords-$stamp.log";;
  *) sed -n 2,8p "$0"; exit 2;;
esac
mkdir -p "$work"; runner="$work/run-$cmd-$stamp.mjs"
if $pw; then printf '%s\nconst {closeTaskSpace}=await import("%s%s/pw.mjs");await closeTaskSpace();process.exit(0);\n' "$js" "$pre" "$here" > "$runner"; else printf '%s\n' "$js" > "$runner"; fi
node --check "$runner" || { echo "SYNTAX ERROR in $runner"; exit 2; }
if $pw; then timeout ${TMO:-600} node "$runner" < /dev/null > "$log" 2>&1; rc=$?
  [ $rc -eq 124 ] && echo "TIMEOUT: 녹화만 끊음(브라우저 유지) — 끊긴 명령이 상태를 바꿨을 수 있으니 저장 데이터로 확인"
else timeout ${TMO:-600} ego-browser nodejs -e "await import('file:///$runner')" < /dev/null > "$log" 2>&1; rc=$?
  if [ $rc -eq 124 ]; then powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='ego.exe'\" | ? { \$_.CommandLine -match 'ego.mojom.NodeService' } | % { Stop-Process -Id \$_.ProcessId -Force }"; echo "TIMEOUT: NodeService만 정리함 — 끊긴 명령이 실제로 실행됐을 수 있으니 저장 데이터로 상태를 확인"; fi; fi
grep -v "^    at" "$log" | tail -3 | cut -c1-600
