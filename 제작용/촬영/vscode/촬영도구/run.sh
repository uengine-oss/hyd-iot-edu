#!/bin/bash
# VS Code 웹 ego 실행기(Git Bash). Notion 실행기 복사본. 저장소의 촬영도구를 ego 안에서 불러 돌린다.
#   ./run.sh rec <이름> <구간 파일(segs/ 기준)> [앞 구간 이름 | '{x:..,y:..}']   구간 하나 녹화 → 실측. 앞 구간 끝(또는 자른 시점) 포인터에서 시작
#   ./run.sh restore <cut25|noteTail|reload|state>                    녹화 밖 상태 맞춤(실행 취소 없이) · 읽기 전용 상태 보기
#   SPACE=<ego 작업 공간> VP='{width:1536,height:864,dsf:1.5}' ./run.sh rec …  VS Code 밖 화면(포털). 앞 구간 URL로 되돌아가지 않는다
#   ./run.sh measure <이름>                                     녹화 하나 다시 실측
# 다른 ego 명령(ego-browser.exe)이 떠 있으면 시작하지 않는다(상태 파일 EPERM). 실행 전 node --check(ego는 문법 오류에 조용히 멈춘다),
# stdin을 닫는다(-e가 입력을 기다린다). 시간 초과(TMO초, 기본 900) 시 ego의 NodeService(스크립트 실행기)만 정리한다.
set -u
here="$(cd "$(dirname "$0")" && pwd -W)"
work="$(cd "$here" && PYTHONUTF8=1 python -c "from common import WORK;print(WORK.as_posix())")"
cmd=${1:-}; shift || true
if [ "$cmd" = measure ]; then cd "$here" && PYTHONUTF8=1 python measure.py "$1"; exit; fi
for f in ctrl.mjs ui.mjs segs/*.mjs; do node --check "$here/$f" || { echo "SYNTAX ERROR in $f: ego로 보내지 않음"; exit 2; }; done
busy=$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='ego-browser.exe'\").Count")
[ "${busy//[^0-9]/}" = "0" ] || { echo "BUSY: 다른 ego 명령이 실행 중($busy) — 끝난 뒤 다시"; exit 3; }
# PC 부하: 화상회의가 돌면 녹화하지 않는다(Zoom으로 1~2초 정지가 반복된 사례). 여유 메모리 3GB 미만은 경고만 하고 measure.py의 프레임 간격으로 판정한다(수치만으로 중단하지 않음).
if [ "$cmd" = rec ]; then
  load=$(powershell -NoProfile -Command "\$z=@(Get-Process -Name Zoom,Teams,ms-teams -ErrorAction SilentlyContinue).Count; \$f=[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024); \"\$z \$f\"")
  set -- "$@"; z=${load%% *}; free=${load##* }; free=${free//[^0-9]/}
  if [ "${z//[^0-9]/}" != "0" ]; then echo "LOAD: 화상회의 ${z}개 — 녹화하지 않음"; exit 4; fi
  [ "${free:-0}" -lt 3000 ] && echo "WARN: 여유 메모리 ${free}MB — 녹화 뒤 measure.py 프레임 간격(최대 0.8초 이하)을 꼭 본다"
fi
stamp=$(date +%s)
mkdir -p "$work"
case "$cmd" in
  rec)
    n=$1; seg=$2; prev=${3:-}
    ptr=null
    if [ "${prev:0:1}" = "{" ]; then ptr=$prev
    # 앞 구간을 <이름>:<자른ms>로 주면 그 시각의 화살표 위치에서 잇는다(실패 조각의 마지막 위치를 쓰면 이음매에서 화살표가 튐, 2026-10-23 v11 5:24.7).
    elif [ -n "$prev" ]; then ptr=$(PYTHONUTF8=1 python -c "import json;n,_,c=r'$prev'.partition(':');ms=json.load(open(r'$work/'+n+'/timing.json',encoding='utf8'))['motions'];ms=[m for m in ms if not c or m['start']<float(c)];m=ms[-1];print('{x:%.1f,y:%.1f}'%(m['x'],m['y']))") || exit 2; fi
    rurl=null; [ -n "$prev" ] && [ "${prev:0:1}" != "{" ] && [ -z "${SPACE:-}" ] && rurl=$(PYTHONUTF8=1 python -c "import json;print(json.dumps(json.load(open(r'$work/${prev%%:*}/end-state.json',encoding='utf8'))['url']))")
    sp=null; [ -n "${SPACE:-}" ] && sp="\"$SPACE\""
    js="const {run}=await import('file:///$here/ctrl.mjs?$stamp');console.log(JSON.stringify(await run({name:'$n',module:'$seg',pointer:$ptr,resumeUrl:$rurl,space:$sp,viewport:${VP:-null}})));"
    log="$work/$n.log";;
  *) sed -n 2,5p "$0"; exit 2;;
esac
runner="$work/run-$cmd-$stamp.mjs"
printf '%s\n' "$js" > "$runner"
node --check "$runner" || { echo "SYNTAX ERROR in $runner"; exit 2; }
timeout ${TMO:-900} ego-browser nodejs -e "await import('file:///$runner')" < /dev/null > "$log" 2>&1
rc=$?
if [ $rc -eq 124 ]; then powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='ego.exe'\" | ? { \$_.CommandLine -match 'ego.mojom.NodeService' } | % { Stop-Process -Id \$_.ProcessId -Force }"; echo "TIMEOUT: NodeService만 정리함 — 끊긴 명령이 실제로 실행됐을 수 있으니 restore state로 확인"; fi
grep -v "^    at" "$log" | tail -3 | cut -c1-600
[ "$cmd" = rec ] && (cd "$here" && PYTHONUTF8=1 python measure.py "$n")
exit 0
