#!/bin/bash
# Neo4j Browser 녹화 실행기(클라우드 리눅스). 상주 브라우저는 포털 browser.mjs를 이 폴더 config.json으로 띄운다(구간 사이 상태 유지).
#   bash rec.sh up                       상주 브라우저 띄우기(이미 떠 있으면 그대로)
#   bash rec.sh down                     끄기(끈 뒤 포트가 내려갔는지 확인)
#   bash rec.sh prep <명령> [인자 …]      녹화 밖에서 탭 열기 · 맞추기(prep.mjs 머리말)
#   bash rec.sh rec <설정.json>          녹화 한 번(설정 = record_graph_lesson.mjs 머리말의 값) → measure.py
# 실행 전 node --check, 시간 초과(TMO초, 기본 1800) 때 그 녹화만 끊는다(브라우저는 유지).
set -u
export PYTHONDONTWRITEBYTECODE=1   # 공용 포털 촬영도구 폴더에 캐시를 남기지 않는다
here="$(cd "$(dirname "$0")" && pwd)"; n4="$(dirname "$here")"; portal="$n4/../포털/촬영도구"
work="$(cd "$portal" && python3 -c "from common import tool;print(tool('neo4j').work.as_posix())")"
port=$(python3 -c "import json;print(json.load(open('$here/config.json'))['cdp'])")
cmd=${1:-}; shift || true
case "$cmd" in
  up)
    curl -s -m 2 "http://127.0.0.1:$port/json/version" >/dev/null && { echo "already up :$port"; exit 0; }
    mkdir -p "$work"; HYD_BROWSER_CONFIG="$here/config.json" nohup node "$portal/browser.mjs" > "$work/browser.log" 2>&1 & echo $! > "$work/browser.pid"
    for i in $(seq 1 30); do curl -s -m 2 "http://127.0.0.1:$port/json/version" >/dev/null && { tail -1 "$work/browser.log"; exit 0; }; sleep 1; done
    echo "browser did not start"; cat "$work/browser.log"; exit 1;;
  down)
    [ -f "$work/browser.pid" ] && kill "$(cat "$work/browser.pid")" 2>/dev/null; sleep 2
    curl -s -m 2 "http://127.0.0.1:$port/json/version" >/dev/null && { echo "STILL UP :$port"; exit 1; } || echo "down";;
  prep) node "$here/prep.mjs" "$@";;
  rec)
    conf="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
    for f in record_graph_lesson.mjs graph_targets.mjs readable_graph.mjs record_from_config.mjs; do node --check "$n4/$f" || { echo "SYNTAX ERROR in $f"; exit 2; }; done
    ps -eo args | grep -q "^node -e globalThis.HYD_CONFIG_PATH" && { echo "BUSY: 다른 녹화 실행 중"; exit 3; }
    take=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['take'])" "$conf")
    mkdir -p "$work"
    timeout "${TMO:-1800}" node -e "globalThis.HYD_CONFIG_PATH='$conf';await import('file://$n4/record_from_config.mjs');process.exit(0)" < /dev/null > "$work/$take.log" 2>&1; rc=$?
    [ $rc -eq 124 ] && echo "TIMEOUT: 녹화만 끊음(브라우저 유지)"
    grep -v "^    at" "$work/$take.log" | tail -3 | cut -c1-900
    (cd "$portal" && python3 measure.py --도구 neo4j "$take");;
  *) sed -n 2,7p "$0"; exit 2;;
esac
