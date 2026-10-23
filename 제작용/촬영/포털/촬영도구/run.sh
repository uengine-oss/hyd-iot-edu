#!/bin/bash
# 포털 녹화 실행기(리눅스 클라우드). 녹화 브라우저는 browser.mjs가 상주하며 구간 사이 상태를 유지한다.
#   ./run.sh up                                    녹화 브라우저 띄우기(이미 떠 있으면 그대로)
#   ./run.sh down                                  녹화 브라우저 끄기(끈 뒤 포트가 내려갔는지 확인)
#   ./run.sh rec <이름> <구간 파일(segs/ 기준)> [앞 구간 이름]   구간 하나 녹화 → 실측. 앞 구간 끝 탭 · 포인터에서 시작
#   ./run.sh measure <이름>                        녹화 하나 다시 실측
# 실행 전 node --check, 시간 초과(TMO초, 기본 900) 시 그 녹화만 끊는다(브라우저는 유지).
set -u
here="$(cd "$(dirname "$0")" && pwd)"
work="$(cd "$here" && python3 -c "from common import WORK;print(WORK.as_posix())")"
port=$(python3 -c "import json;print(json.load(open('$here/config.json'))['cdp'])")
cmd=${1:-}; shift || true
case "$cmd" in
  up)
    curl -s -m 2 "http://127.0.0.1:$port/json/version" >/dev/null && { echo "already up :$port"; exit 0; }
    mkdir -p "$work"; nohup node "$here/browser.mjs" > "$work/browser.log" 2>&1 & echo $! > "$work/browser.pid"
    for i in $(seq 1 30); do curl -s -m 2 "http://127.0.0.1:$port/json/version" >/dev/null && { tail -1 "$work/browser.log"; exit 0; }; sleep 1; done
    echo "browser did not start"; cat "$work/browser.log"; exit 1;;
  down)
    # 한글 경로는 pkill -f가 못 찾으므로 띄울 때 남긴 PID로 끈다(자식 Chromium도 함께 끝남).
    [ -f "$work/browser.pid" ] && kill "$(cat "$work/browser.pid")" 2>/dev/null; sleep 2
    curl -s -m 2 "http://127.0.0.1:$port/json/version" >/dev/null && { echo "STILL UP :$port"; exit 1; } || echo "down";;
  measure) cd "$here" && python3 measure.py "$1";;
  rec)
    n=$1; seg=$2; prev=${3:-}
    for f in ctrl.mjs ui.mjs "segs/$seg"; do node --check "$here/$f" || { echo "SYNTAX ERROR in $f"; exit 2; }; done
    ptr=null; resume=null
    if [ -n "$prev" ]; then
      ptr=$(python3 -c "import json;m=json.load(open('$work/$prev/timing.json'))['motions'];print(json.dumps({'x':m[-1]['x'],'y':m[-1]['y']}) if m else 'null')") || exit 2
      resume=$(cat "$work/$prev/end-state.json")
    fi
    mkdir -p "$work"; runner="$work/run-$n.mjs"
    printf "import {run} from 'file://%s/ctrl.mjs';\nconst r=await run({name:%s,module:%s,pointer:%s,resume:%s});\nconsole.log(JSON.stringify(r));process.exit(0);\n" \
      "$here" "$(python3 -c "import json,sys;print(json.dumps(sys.argv[1]))" "$n")" "$(python3 -c "import json,sys;print(json.dumps(sys.argv[1]))" "$seg")" "$ptr" "$resume" > "$runner"
    timeout ${TMO:-900} node "$runner" < /dev/null > "$work/$n.log" 2>&1; rc=$?
    [ $rc -eq 124 ] && echo "TIMEOUT: 녹화만 끊음(브라우저 유지)"
    grep -v "^    at" "$work/$n.log" | tail -2 | cut -c1-600
    (cd "$here" && python3 measure.py "$n");;
  *) sed -n 2,6p "$0"; exit 2;;
esac
