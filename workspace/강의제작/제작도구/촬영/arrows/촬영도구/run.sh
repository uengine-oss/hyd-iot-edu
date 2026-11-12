#!/bin/bash
# ARROWS 녹화 실행기. 이 PC(Git Bash)는 ego 안에서, 클라우드(리눅스)는 browser.mjs가 띄운 헤드리스 Chromium에 붙어 같은 촬영도구를 돈다.
#   ./run.sh up | down                                              클라우드만: 녹화 브라우저 띄우기 · 끄기(구간 사이 그림 · 저장소 유지)
#   ./run.sh open                                                   클라우드만: 녹화 탭을 https://arrows.app 첫 화면으로(녹화 밖)
#   ./run.sh rec <이름> <구간> [시작큐] [이전 구간 이름] [relax]   구간 하나 녹화(relax: 그림 주소가 바뀐 뒤 첫 구간. VIEW={"scale":…,"dx":…,"dy":…}이면 녹화 전 보기를 그 값으로)
#   ./run.sh restore <이전 구간 이름> [출발원 도착원]               녹화 밖 상태 복원(가져오기 + 원 크기 + 마지막 화살표 선택)
#   ./run.sh coords                                                  사용자가 배치한 그림들의 저장 좌표 읽기(읽기 전용)
# 실행 전 node --check로 문법 오류를 막고(ego는 문법 오류에 조용히 멈춘다), stdin을 닫는다(-e가 입력을 기다린다).
# 시간 초과(TMO초, 기본 600): ego는 NodeService(스크립트 실행기)만 정리하고, 클라우드는 그 녹화만 끊는다. 브라우저 창 · 탭은 건드리지 않는다.
set -u
linux=false; [ "$(uname -s)" = Linux ] && linux=true
if $linux; then here="$(cd "$(dirname "$0")" && pwd)"; PY=python3; pre="file://"; else here="$(cd "$(dirname "$0")" && pwd -W)"; PY=python; pre="file:///"; fi
work="$(PYTHONUTF8=1 $PY -c "import sys;sys.path.insert(0,r'$here');from common import WORK;print(WORK.as_posix())")"
port=$($PY -c "import json;print(json.load(open(r'$here/config.json',encoding='utf-8'))['cloud']['cdp'])")
for f in ctrl.mjs ui.mjs restore.mjs pw.mjs browser.mjs; do node --check "$here/$f" || { echo "SYNTAX ERROR in $f: 보내지 않음"; exit 2; }; done
cmd=${1:-}; shift || true
stamp=$(date +%s)
case "$cmd" in
  up)
    $linux || { echo "up은 클라우드 전용"; exit 2; }
    curl -s -m 2 "http://127.0.0.1:$port/json/version" >/dev/null && { echo "already up :$port"; exit 0; }
    mkdir -p "$work"; (setsid nohup node "$here/browser.mjs" > "$work/browser.log" 2>&1 < /dev/null & echo $! > "$work/browser.pid")
    for i in $(seq 1 30); do curl -s -m 2 "http://127.0.0.1:$port/json/version" >/dev/null && { tail -1 "$work/browser.log"; exit 0; }; sleep 1; done
    echo "browser did not start"; cat "$work/browser.log"; exit 1;;
  down)
    # 한글 경로는 pkill -f가 못 찾으므로 띄울 때 남긴 PID로 끈다(자식 Chromium도 함께 끝남).
    [ -f "$work/browser.pid" ] && kill "$(cat "$work/browser.pid")" 2>/dev/null; sleep 2
    curl -s -m 2 "http://127.0.0.1:$port/json/version" >/dev/null && { echo "STILL UP :$port"; exit 1; } || echo "down"; exit 0;;
  open)
    js="const {taskSpace}=await import('$pre$here/pw.mjs?$stamp');const p=(await taskSpace()).page();await p.goto('https://arrows.app',{waitUntil:'networkidle',timeout:60000});await p.waitForSelector('canvas');await p.waitForTimeout(1500);console.log(JSON.stringify({url:p.url(),text:(await p.evaluate(()=>document.body.innerText)).slice(0,80)}));"
    log="$work/open-$stamp.log";;
  rec)
    n=$1; seg=$2; from=${3:-}; st=${4:-}; relax=false; [ -n "${5:-}" ] && relax=true
    mkdir -p "$work"
    js="const {run}=await import('$pre$here/ctrl.mjs?$n');console.log(JSON.stringify(await run({name:'$n',segment:$seg,from:'$from',startState:'$st',expectUrl:'arrows.app',to:'${TO:-}',relaxUrl:$relax,view:${VIEW:-null}})));"
    log="$work/$n.log";;
  restore)
    take=$1; e1=${2:-}; e2=${3:-}
    edge=$([ -n "$e1" ] && echo "['$e1','$e2']" || echo "null")
    js="const {restore}=await import('$pre$here/restore.mjs?$stamp');console.log(JSON.stringify(await restore({take:'$take',edge:$edge})));"
    log="$work/restore-$stamp.log";;
  coords)
    js="const {coords}=await import('$pre$here/restore.mjs?$stamp');console.log(JSON.stringify(await coords()));"
    log="$work/coords-$stamp.log";;
  *) sed -n 2,7p "$0"; exit 2;;
esac
mkdir -p "$work"; runner="$work/run-$cmd-$stamp.mjs"
if $linux; then printf '%s\nconst {closeTaskSpace}=await import("%s%s/pw.mjs");await closeTaskSpace();process.exit(0);\n' "$js" "$pre" "$here" > "$runner"; else printf '%s\n' "$js" > "$runner"; fi
node --check "$runner" || { echo "SYNTAX ERROR in $runner"; exit 2; }
if $linux; then timeout ${TMO:-600} node "$runner" < /dev/null > "$log" 2>&1; rc=$?
  [ $rc -eq 124 ] && echo "TIMEOUT: 녹화만 끊음(브라우저 유지) — 끊긴 명령이 상태를 바꿨을 수 있으니 저장 데이터로 확인"
else timeout ${TMO:-600} ego-browser nodejs -e "await import('file:///$runner')" < /dev/null > "$log" 2>&1; rc=$?
  if [ $rc -eq 124 ]; then powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='ego.exe'\" | ? { \$_.CommandLine -match 'ego.mojom.NodeService' } | % { Stop-Process -Id \$_.ProcessId -Force }"; echo "TIMEOUT: NodeService만 정리함 — 끊긴 명령이 실제로 실행됐을 수 있으니 저장 데이터로 상태를 확인"; fi; fi
grep -v "^    at" "$log" | tail -3 | cut -c1-600
