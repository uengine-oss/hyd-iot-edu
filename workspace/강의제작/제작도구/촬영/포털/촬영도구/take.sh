#!/bin/bash
# 끊지 않는 한 번 녹화 실행기. take.mjs 머리말 참고. 환경은 HYD_ENV로 고른다(env.sh): cloud(클라우드 리눅스 Playwright) · pc(이 PC Windows Playwright, Git Bash) — 둘 다 먼저 ./run.sh up —
# · ego(이 PC ego 브라우저 안에서 돌리는 옛 길, HYD_ENV=ego를 줘야 한다). 주지 않으면 리눅스는 cloud, Windows는 pc다.
#   ./take.sh rehearse <이름> <큐 파일> <모듈> <구간 번호,…> [--silent]
#   ./take.sh record   <이름> <큐 파일> <모듈> <구간 번호,…> [--silent]
#   RESUME=<앞 take>:<큐 id> ./take.sh record …   실패한 페이지 그대로 그 큐부터 이어 찍는다(FAIL_AT=<큐 id>는 복구 시험용)
#   AFTER=<앞 구간 take> ./take.sh record …      구간으로 나눠 찍을 때 앞 구간 끝 화면 · 마지막 커서 자리에서 시작한다(영상 길 16)
# cloud · pc: 다른 take가 돌면 시작하지 않는다. 시간 초과(TMO초, 기본 3600) 때 그 녹화만 끊는다. ego: 다른 ego 명령이 떠 있으면 시작하지 않고, 시간 초과 때 ego NodeService만 정리한다.
set -u
. "$(dirname "$0")/env.sh"
here="$tools"
mode=$1; name=$2; cues=$(cd "$(dirname "$3")" && pwdw)/$(basename "$3"); module=$4; segs=$5; silent=false; [ "${6:-}" = "--silent" ] && silent=true
space=${SPACE:-portal rec 20261028}
for f in take.mjs ui.mjs env.mjs hl.mjs "segs/$module"; do node --check "$here/$f" || { echo "SYNTAX ERROR in $f"; exit 2; }; done
if [ "$HYD_ENV" = ego ]; then busy=$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='ego-browser.exe'\").Count"); [ "${busy//[^0-9]/}" = "0" ] || { echo "BUSY: 다른 ego 명령 실행 중"; exit 3; }
else busy '/run-[^/ ]*\.mjs' && { echo "BUSY: 다른 take 실행 중"; exit 3; }; fi
work="$(cd "$here" && "$PY" -c "from common import WORK;print(WORK.as_posix())")"; mkdir -p "$work"
runner="$work/run-$name-$mode.mjs"
extra=""; [ -n "${RESUME:-}" ] && extra="$extra,resume:{prev:'${RESUME%%:*}',fromCue:'${RESUME##*:}'}"; [ -n "${FAIL_AT:-}" ] && extra="$extra,failAt:'$FAIL_AT'"; [ -n "${AFTER:-}" ] && extra="$extra,after:'$AFTER'"
printf "const {take}=await import('%s%s/take.mjs?%s');\nawait take({mode:'%s',name:'%s',cueFile:'%s',module:'%s',segments:[%s],space:'%s',silent:%s%s});\n" "$pre" "$here" "$(date +%s)" "$mode" "$name" "$cues" "$module" "$segs" "$space" "$silent" "$extra" > "$runner"
if [ "$HYD_ENV" = ego ]; then timeout "${TMO:-3600}" ego-browser nodejs -e "await import('file:///$runner')" < /dev/null > "$work/$name-$mode.log" 2>&1; rc=$?
  [ $rc -eq 124 ] && powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='ego.exe'\" | ? { \$_.CommandLine -match 'ego.mojom.NodeService' } | % { Stop-Process -Id \$_.ProcessId -Force }"
else echo "process.exit(0);" >> "$runner"; timeout "${TMO:-3600}" node "$runner" < /dev/null > "$work/$name-$mode.log" 2>&1; rc=$?
  [ $rc -eq 124 ] && echo "TIMEOUT: 녹화만 끊음(브라우저 유지)"; fi
grep -v "^    at" "$work/$name-$mode.log" | tail -4 | cut -c1-900
[ $rc -eq 0 ] && ! grep -q '"error":null' "$work/$name-$mode.log" && { echo "FAILED: $name $mode"; exit 1; }
exit $rc
