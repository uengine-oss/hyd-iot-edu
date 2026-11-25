#!/bin/bash
# 웹 VS Code 녹화 실행기(Git Bash). 녹화 브라우저는 포털 촬영도구 browser.mjs를 이 폴더 config.json으로 띄운 헤드리스 Chromium이고(파이썬 · 경로 꼴 · 띄우고 끄기는 포털 촬영도구 env.sh),
# 구간 사이에도 떠 있어 같은 페이지 · 폴더 · 터미널 · Codex 대화가 남는다. 페이지에 붙는 곳은 page.mjs 하나다.
#   ./run.sh up | down                                     녹화 브라우저 띄우기(이미 떠 있으면 그대로) · 끄기(포트가 내려갔는지 확인)
#   ./run.sh prep [랩 폴더 절대 경로]                        녹화 브라우저의 웹 VS Code 사용자 설정을 config.json settings로 맞추고 화면을 잰다(prep.mjs)
#   ./run.sh reset <되돌리기 모듈(segs/ 기준)>                녹화 밖 상태 맞춤(segs/<편>-reset.mjs)
#   ./run.sh dry <이름> <구간 모듈(segs/ 기준)>               리허설: 녹화 · 프레임 저장 · 음성 대기 없이 조작만 실제로 해 보고 큐마다 검사(dry.json). 실패면 종료 코드 1
#   ./run.sh rec <이름> <구간 모듈> [앞 구간 이름[:자른 ms] | '{x:..,y:..}']   구간 하나 녹화 → 실측. 앞 구간 끝(또는 자른 시점)의 포인터에서 시작한다
#   ./run.sh measure <이름>                                 녹화 하나 다시 실측
#   PAGE=1 ./run.sh rec|dry …                               녹화 브라우저의 둘째 페이지(랩 결과 화면)에서 돈다. 앞 구간 주소로 되돌아가지 않는다
#   VP='{width:..,height:..,dsf:..}' ./run.sh rec|dry …      config.json viewport와 다른 화면 값으로 돈다
#   HYD_AUDIO=<음성 캐시 폴더> ./run.sh rec …                 다른 음성 캐시(common.py). 앞 구간 이름은 구간 모듈에 ctx.prev(앞 take의 timing.json result)로도 넘어간다
# 같은 녹화 브라우저에 붙는 다른 실행(run-*.mjs)이 돌고 있으면 시작하지 않는다. 실행 전에 돌릴 파일의 문법을 node --check로 본다. 시간 초과(TMO초, 기본 900)에는 그 실행만 끊고 브라우저는 둔다.
set -u
. "$(dirname "$0")/../../포털/촬영도구/env.sh"
here="$(cd "$(dirname "$0")" && pwdw)"
work="$(cd "$here" && "$PY" -c "from common import WORK;print(WORK.as_posix())")" || exit 2
audio="$(cd "$here" && "$PY" -c "from common import AUDIO;print(AUDIO.as_posix())")" || exit 2
cmd=${1:-}; shift || true
case "$cmd" in
  up) browser_up "$here/config.json" "$work"; exit $?;;
  down) browser_down "$here/config.json" "$work"; exit $?;;
  measure) cd "$here" && "$PY" measure.py "$1"; exit $?;;
  prep|reset|dry|rec) ;;
  *) sed -n 2,13p "$0"; exit 2;;
esac
# 문법은 이번에 돌릴 파일만 본다(구간 모듈 70여 개를 모두 보면 2분이 걸린다). 그 파일이 불러오는 다른 파일의 문법 오류는 node가 파일 · 줄을 대며 멈춘다.
case "$cmd" in prep) chk="prep.mjs";; reset) chk="segs/$1";; *) chk="ctrl.mjs segs/$2";; esac
for f in $chk; do [ -f "$here/$f" ] || { echo "파일 없음: $here/$f"; exit 2; }; node --check "$here/$f" || { echo "SYNTAX ERROR in $f: 돌리지 않음"; exit 2; }; done
busy 'vscode/run-[^/ ]*\.mjs' && { echo "BUSY: 이 녹화 브라우저에 붙은 다른 실행이 돌고 있음 — 끝난 뒤 다시"; exit 3; }
# PC 부하: 화상회의가 돌면 녹화하지 않는다(Zoom으로 1~2초 정지가 반복된 사례). 여유 메모리 3GB 미만은 경고만 하고 measure.py의 이동 중 공백으로 판정한다(수치만으로 중단하지 않음).
if [ "$cmd" = rec ]; then
  load=$(powershell -NoProfile -Command "\$z=@(Get-Process -Name Zoom,Teams,ms-teams -ErrorAction SilentlyContinue).Count; \$f=[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024); \"\$z \$f\"")
  z=${load%% *}; free=${load##* }; free=${free//[^0-9]/}
  if [ "${z//[^0-9]/}" != "0" ]; then echo "LOAD: 화상회의 ${z}개 — 녹화하지 않음"; exit 4; fi
  [ "${free:-0}" -lt 3000 ] && echo "WARN: 여유 메모리 ${free}MB — 녹화 뒤 measure.py의 이동 중 공백(gaps_over_100)을 꼭 본다"
fi
stamp=$(date +%s)
mkdir -p "$work"
page=${PAGE:-0}
case "$cmd" in
  prep)
    js="const {prep}=await import('$pre$here/prep.mjs');console.log(JSON.stringify(await prep('${1:-}')));"
    log="$work/prep-$stamp.log";;
  reset)
    js="await import('$pre$here/segs/$1');"
    log="$work/reset-$stamp.log";;
  rec)
    n=$1; seg=$2; prev=${3:-}
    ptr=null
    if [ "${prev:0:1}" = "{" ]; then ptr=$prev
    # 앞 구간을 <이름>:<자른ms>로 주면 그 시각의 화살표 위치에서 잇는다(실패 조각의 마지막 위치를 쓰면 이음매에서 화살표가 튄다).
    elif [ -n "$prev" ]; then ptr=$("$PY" -c "import json;n,_,c=r'$prev'.partition(':');ms=json.load(open(r'$work/'+n+'/timing.json',encoding='utf8'))['motions'];ms=[m for m in ms if not c or m['start']<float(c)];m=ms[-1];print('{x:%.1f,y:%.1f}'%(m['x'],m['y']))") || exit 2; fi
    rurl=null; [ -n "$prev" ] && [ "${prev:0:1}" != "{" ] && [ "$page" = 0 ] && rurl=$("$PY" -c "import json;print(json.dumps(json.load(open(r'$work/${prev%%:*}/end-state.json',encoding='utf8'))['url']))")
    pv=null; [ -n "$prev" ] && [ "${prev:0:1}" != "{" ] && pv="'${prev%%:*}'"
    js="const {run}=await import('$pre$here/ctrl.mjs');console.log(JSON.stringify(await run({name:'$n',module:'$seg',pointer:$ptr,resumeUrl:$rurl,pageIndex:$page,viewport:${VP:-null},audio:'$audio',prev:$pv})));"
    log="$work/$n.log";;
  dry)
    n=$1; seg=$2
    js="const {run}=await import('$pre$here/ctrl.mjs');console.log(JSON.stringify(await run({name:'$n',module:'$seg',pageIndex:$page,viewport:${VP:-null},audio:'$audio',dry:true})));"
    log="$work/$n.log";;
esac
runner="$work/run-$cmd-$stamp.mjs"
printf '%s\nprocess.exit(0);\n' "$js" > "$runner"
node --check "$runner" || { echo "SYNTAX ERROR in $runner"; exit 2; }
timeout ${TMO:-900} node "$runner" < /dev/null > "$log" 2>&1
rc=$?
[ $rc -eq 124 ] && echo "TIMEOUT: 그 실행만 끊음(녹화 브라우저 유지) — 끊긴 조작이 화면 상태를 바꿨을 수 있으니 화면을 확인한다"
rm -f "$runner"
grep -v "^    at" "$log" | tail -3 | cut -c1-600
[ "$cmd" = rec ] && (cd "$here" && "$PY" measure.py "$n")
if [ "$cmd" = dry ]; then grep '^{"dry"' "$log" | tail -1 | "$PY" -c "import json,sys;r=json.loads(sys.stdin.read());sys.exit(0 if r.get('ok') else 1)" 2>/dev/null || { echo "DRY FAIL: $n"; exit 1; }; echo "DRY OK: $n"; fi
[ "$cmd" = prep ] || [ "$cmd" = reset ] && exit $rc
exit 0
