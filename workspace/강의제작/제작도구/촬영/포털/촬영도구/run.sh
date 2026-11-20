#!/bin/bash
# 포털 녹화 실행기(클라우드 리눅스 · 이 PC Windows Git Bash — 다른 것은 env.sh에만 있다). 녹화 브라우저는 browser.mjs가 상주하며 구간 사이 상태를 유지한다.
#   ./run.sh up                                    녹화 브라우저 띄우기(이미 떠 있으면 그대로)
#   ./run.sh down                                  녹화 브라우저 끄기(끈 뒤 포트가 내려갔는지 확인)
#   ./run.sh rec <이름> <구간 파일(segs/ 기준)> [앞 구간 이름]   구간 하나 녹화 → 실측. 앞 구간 끝 탭 · 포인터에서 시작
#   ./run.sh measure <이름>                        녹화 하나 다시 실측
# 실행 전 node --check, 시간 초과(TMO초, 기본 900) 시 그 녹화만 끊는다(브라우저는 유지).
set -u
. "$(dirname "$0")/env.sh"
here="$tools"
work="$(cd "$here" && "$PY" -c "from common import WORK;print(WORK.as_posix())")"
cmd=${1:-}; shift || true
case "$cmd" in
  up) browser_up "$here/config.json" "$work"; exit $?;;
  down) browser_down "$here/config.json" "$work"; exit $?;;
  measure) cd "$here" && "$PY" measure.py "$1";;
  rec)
    n=$1; seg=$2; prev=${3:-}
    for f in ctrl.mjs ui.mjs env.mjs "segs/$seg"; do node --check "$here/$f" || { echo "SYNTAX ERROR in $f"; exit 2; }; done
    ptr=null; resume=null
    if [ -n "$prev" ]; then
      ptr=$("$PY" -c "import json,sys;m=json.load(open(sys.argv[1],encoding='utf-8'))['motions'];print(json.dumps({'x':m[-1]['x'],'y':m[-1]['y']}) if m else 'null')" "$work/$prev/timing.json") || exit 2
      resume=$(cat "$work/$prev/end-state.json")
    fi
    mkdir -p "$work"; runner="$work/run-$n.mjs"
    printf "import {run} from '%s%s/ctrl.mjs';\nconst r=await run({name:%s,module:%s,pointer:%s,resume:%s});\nconsole.log(JSON.stringify(r));process.exit(0);\n" \
      "$pre" "$here" "$("$PY" -c "import json,sys;print(json.dumps(sys.argv[1]))" "$n")" "$("$PY" -c "import json,sys;print(json.dumps(sys.argv[1]))" "$seg")" "$ptr" "$resume" > "$runner"
    timeout ${TMO:-900} node "$runner" < /dev/null > "$work/$n.log" 2>&1; rc=$?
    [ $rc -eq 124 ] && echo "TIMEOUT: 녹화만 끊음(브라우저 유지)"
    grep -v "^    at" "$work/$n.log" | tail -2 | cut -c1-600
    (cd "$here" && "$PY" measure.py "$n");;
  *) sed -n 2,6p "$0"; exit 2;;
esac
