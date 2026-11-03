#!/bin/bash
# 끊지 않는 한 번 녹화 실행기(Git Bash · 로컬 ego). take.mjs 머리말 참고.
#   ./take.sh rehearse <이름> <큐 파일> <모듈> <구간 번호,…> [--silent]
#   ./take.sh record   <이름> <큐 파일> <모듈> <구간 번호,…> [--silent]
#   RESUME=<앞 take>:<큐 id> ./take.sh record …   실패한 페이지 그대로 그 큐부터 이어 찍는다(FAIL_AT=<큐 id>는 복구 시험용)
# 다른 ego 명령이 떠 있으면 시작하지 않는다. 시간 초과(TMO초, 기본 3600) 때 ego NodeService만 정리한다.
set -u
here="$(cd "$(dirname "$0")" && pwd -W)"
mode=$1; name=$2; cues=$(cd "$(dirname "$3")" && pwd -W)/$(basename "$3"); module=$4; segs=$5; silent=false; [ "${6:-}" = "--silent" ] && silent=true
space=${SPACE:-portal rec 20261028}
for f in take.mjs ui.mjs "segs/$module"; do node --check "$here/$f" || { echo "SYNTAX ERROR in $f"; exit 2; }; done
busy=$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='ego-browser.exe'\").Count"); [ "${busy//[^0-9]/}" = "0" ] || { echo "BUSY: 다른 ego 명령 실행 중"; exit 3; }
work="$(cd "$here" && PYTHONUTF8=1 python -c "from common import WORK;print(WORK.as_posix())")"; mkdir -p "$work"
runner="$work/run-$name-$mode.mjs"
extra=""; [ -n "${RESUME:-}" ] && extra="$extra,resume:{prev:'${RESUME%%:*}',fromCue:'${RESUME##*:}'}"; [ -n "${FAIL_AT:-}" ] && extra="$extra,failAt:'$FAIL_AT'"
printf "const {take}=await import('file:///%s/take.mjs?%s');\nawait take({mode:'%s',name:'%s',cueFile:'%s',module:'%s',segments:[%s],space:'%s',silent:%s%s});\n" "$here" "$(date +%s)" "$mode" "$name" "$cues" "$module" "$segs" "$space" "$silent" "$extra" > "$runner"
timeout "${TMO:-3600}" ego-browser nodejs -e "await import('file:///$runner')" < /dev/null > "$work/$name-$mode.log" 2>&1; rc=$?
[ $rc -eq 124 ] && powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='ego.exe'\" | ? { \$_.CommandLine -match 'ego.mojom.NodeService' } | % { Stop-Process -Id \$_.ProcessId -Force }"
grep -v "^    at" "$work/$name-$mode.log" | tail -4 | cut -c1-900
[ $rc -eq 0 ] && ! grep -q '"error":null' "$work/$name-$mode.log" && { echo "FAILED: $name $mode"; exit 1; }
exit $rc
