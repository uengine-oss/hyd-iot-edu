#!/bin/bash
# Neo4j Browser 녹화 실행기(클라우드 리눅스 · 이 PC Windows Git Bash — 다른 것은 포털 촬영도구 env.sh에만 있다). 상주 브라우저는 포털 browser.mjs를 이 폴더 config.json으로 띄운다(구간 사이 상태 유지).
#   bash rec.sh up                       상주 브라우저 띄우기(이미 떠 있으면 그대로)
#   bash rec.sh down                     끄기(끈 뒤 포트가 내려갔는지 확인)
#   bash rec.sh prep <명령> [인자 …]      녹화 밖에서 탭 열기 · 맞추기(prep.mjs 머리말)
#   bash rec.sh rec <설정.json>          녹화 한 번(설정 = record_graph_lesson.mjs 머리말의 값) → measure.py
# 실행 전 node --check, 시간 초과(TMO초, 기본 1800) 때 그 녹화만 끊는다(브라우저는 유지).
set -u
export PYTHONDONTWRITEBYTECODE=1   # 공용 포털 촬영도구 폴더에 캐시를 남기지 않는다
. "$(dirname "$0")/../../포털/촬영도구/env.sh"
here="$(cd "$(dirname "$0")" && pwdw)"; n4="$(dirname "$here")"; portal="$tools"
work="$(cd "$portal" && "$PY" -c "from common import tool;print(tool('neo4j').work.as_posix())")"
cmd=${1:-}; shift || true
case "$cmd" in
  up) browser_up "$here/config.json" "$work"; exit $?;;
  down) browser_down "$here/config.json" "$work"; exit $?;;
  prep) node "$here/prep.mjs" "$@";;
  rec)
    conf="$(cd "$(dirname "$1")" && pwdw)/$(basename "$1")"
    for f in record_graph_lesson.mjs graph_targets.mjs readable_graph.mjs record_from_config.mjs; do node --check "$n4/$f" || { echo "SYNTAX ERROR in $f"; exit 2; }; done
    busy 'globalThis\.HYD_CONFIG_PATH' && { echo "BUSY: 다른 녹화 실행 중"; exit 3; }
    take=$("$PY" -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['take'])" "$conf")
    mkdir -p "$work"
    timeout "${TMO:-1800}" node -e "globalThis.HYD_CONFIG_PATH='$conf';await import('$pre$n4/record_from_config.mjs');process.exit(0)" < /dev/null > "$work/$take.log" 2>&1; rc=$?
    [ $rc -eq 124 ] && echo "TIMEOUT: 녹화만 끊음(브라우저 유지)"
    grep -v "^    at" "$work/$take.log" | tail -3 | cut -c1-900
    (cd "$portal" && "$PY" measure.py --도구 neo4j "$take");;
  *) sed -n 2,7p "$0"; exit 2;;
esac
