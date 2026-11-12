#!/bin/bash
# Notion ego 실행기(Git Bash). 저장소의 촬영도구를 ego 안에서 불러 돌린다.
#   ./run.sh rec <이름> <구간 파일(segs/ 기준)> [앞 구간 이름 | '{x:..,y:..}']   구간 하나 녹화 → 실측. 앞 구간 끝(또는 자른 시점) 포인터에서 시작
#   ./run.sh chain12 <접두어> [시작 구간(v12-NN)] [앞 구간 take]    v12 구간 전부(또는 그 구간부터)를 한 ego 실행 안에서 차례로 녹화 → 구간마다 실측.
#                                                                 take 이름은 take-<접두어>-v12-NN, 결과 줄은 <work>/chain-<접두어>.jsonl. 녹화 전에 node preflight12.mjs --음성
#   ./run.sh rehearse12 <접두어> [시작 구간] [앞 리허설 이름]        같은 차례를 녹화 · 음성 없이 조작만 돌린다(큐 길이는 시간계수 어림 × 0.5). 홈 제목은
#                                                                 「내 학습 노트 리허설」, 이름은 rehearsal-<접두어>-v12-NN, 결과 줄은 <work>/rehearsal-<접두어>.jsonl.
#                                                                 CAPTURE=v12-02,v12-12 를 주면 그 구간만 화면을 녹화한다(음성 없이 화질 · 움직임을 잴 때, encode.py --무음)
#                                                                 UNTIL=v12-NN 을 주면 chain12 · rehearse12가 그 구간까지만 돈다(고친 구간 하나만 확인할 때)
#   ./run.sh restore <cut25|noteTail|reload|state>                    녹화 밖 상태 맞춤(실행 취소 없이) · 읽기 전용 상태 보기
#   ./run.sh measure <이름>                                     녹화 하나 다시 실측
# 다른 ego 명령(ego-browser.exe)이 떠 있으면 시작하지 않는다(상태 파일 EPERM). 실행 전 node --check(ego는 문법 오류에 조용히 멈춘다),
# stdin을 닫는다(-e가 입력을 기다린다). 시간 초과(TMO초, 기본 900) 시 ego의 NodeService(스크립트 실행기)만 정리한다.
set -u
here="$(cd "$(dirname "$0")" && pwd -W)"
# measure.py는 PIL이 필요하다 — 이 PC의 개발 파이썬(.venv314)을 쓴다(CLAUDE.md 6절). 시스템 python에는 PIL이 없어 k2 실측이 돌지 않았다.
PY="$here/../../../../../../.venv314/Scripts/python.exe"; [ -x "$PY" ] || { echo "개발 파이썬 없음: $PY (run.sh)"; exit 2; }
work="$(cd "$here" && PYTHONUTF8=1 python -c "from common import WORK;print(WORK.as_posix())")"
cmd=${1:-}; shift || true
if [ "$cmd" = measure ]; then cd "$here" && PYTHONUTF8=1 "$PY" measure.py "$1"; exit; fi
for f in ctrl.mjs ui.mjs restore.mjs preflight12.mjs lib/*.mjs segs/*.mjs; do node --check "$here/$f" || { echo "SYNTAX ERROR in $f: ego로 보내지 않음"; exit 2; }; done
busy=$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='ego-browser.exe'\").Count")
[ "${busy//[^0-9]/}" = "0" ] || { echo "BUSY: 다른 ego 명령이 실행 중($busy) — 끝난 뒤 다시"; exit 3; }
# PC 부하: 화상회의가 돌거나 여유 메모리가 3GB 미만이면 녹화하지 않는다(Zoom · 메모리 부족으로 1~2초 정지가 반복된 사례)
# v12: 큐 · 모듈 · 음성 · config 대조가 0건이 아니면 ego로 보내지 않는다(녹화 전에 멈춤).
if [ "$cmd" = rehearse12 ]; then (cd "$here" && node preflight12.mjs) || { echo "PREFLIGHT: 위 목록을 고친 뒤 다시"; exit 2; }; fi
if [ "$cmd" = chain12 ]; then (cd "$here" && node preflight12.mjs --음성) || { echo "PREFLIGHT: 위 목록을 고친 뒤 다시"; exit 2; }; fi
if [ "$cmd" = rec ] || [ "$cmd" = chain12 ]; then
  load=$(powershell -NoProfile -Command "\$z=@(Get-Process -Name Zoom,Teams,ms-teams -ErrorAction SilentlyContinue).Count; \$f=[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024); \"\$z \$f\"")
  set -- "$@"; z=${load%% *}; free=${load##* }; free=${free//[^0-9]/}
  if [ "${z//[^0-9]/}" != "0" ] || [ "${free:-0}" -lt 3000 ]; then echo "LOAD: 화상회의 ${z}개, 여유 메모리 ${free}MB — 녹화하지 않음"; exit 4; fi
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
    rurl=null; [ -n "$prev" ] && [ "${prev:0:1}" != "{" ] && rurl=$(PYTHONUTF8=1 python -c "import json;print(json.dumps(json.load(open(r'$work/${prev%%:*}/end-state.json',encoding='utf8'))['url']))")
    js="const {run}=await import('file:///$here/ctrl.mjs?$stamp');console.log(JSON.stringify(await run({name:'$n',module:'$seg',pointer:$ptr,resumeUrl:$rurl})));"
    log="$work/$n.log";;
  chain12)
    p=$1; from=${2:-}; prev=${3:-}
    fj=null; [ -n "$from" ] && fj="'$from'"; pj=null; [ -n "$prev" ] && pj="'$prev'"
    uj=null; [ -n "${UNTIL:-}" ] && uj="'$UNTIL'"
    rj=$(PYTHONUTF8=1 python -c "import json,sys;print(json.dumps([x for x in sys.argv[1].split(',') if x]))" "${RETAKE:-}")
    wj=$(PYTHONUTF8=1 python -c "import json,sys;print(json.dumps(sys.argv[1]))" "${RETAKE_WHY:-}")
    js="const {chain}=await import('file:///$here/ctrl.mjs?$stamp');console.log(JSON.stringify(await chain({prefix:'$p',from:$fj,prev:$pj,until:$uj,retake:$rj,why:$wj})));"
    log="$work/chain-$p-$stamp.log"; TMO=${TMO:-7200};;
  rehearse12)
    p=$1; from=${2:-}; prev=${3:-}
    fj=null; [ -n "$from" ] && fj="'$from'"; pj=null; [ -n "$prev" ] && pj="'$prev'"
    cj=$(PYTHONUTF8=1 python -c "import json,sys;print(json.dumps([x for x in sys.argv[1].split(',') if x]))" "${CAPTURE:-}")
    uj=null; [ -n "${UNTIL:-}" ] && uj="'$UNTIL'"
    js="const {chain}=await import('file:///$here/ctrl.mjs?$stamp');console.log(JSON.stringify(await chain({prefix:'$p',from:$fj,prev:$pj,rehearsal:true,capture:$cj,until:$uj})));"
    log="$work/rehearsal-$p-$stamp.log"; TMO=${TMO:-5400};;
  restore)
    js="const {restore}=await import('file:///$here/restore.mjs?$stamp');console.log(JSON.stringify(await restore('$1')));"
    log="$work/restore-$stamp.log";;
  *) sed -n 2,9p "$0"; exit 2;;
esac
runner="$work/run-$cmd-$stamp.mjs"
printf '%s\n' "$js" > "$runner"
node --check "$runner" || { echo "SYNTAX ERROR in $runner"; exit 2; }
timeout ${TMO:-900} ego-browser nodejs -e "await import('file:///$runner')" < /dev/null > "$log" 2>&1
rc=$?
if [ $rc -eq 124 ]; then powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='ego.exe'\" | ? { \$_.CommandLine -match 'ego.mojom.NodeService' } | % { Stop-Process -Id \$_.ProcessId -Force }"; echo "TIMEOUT: NodeService만 정리함 — 끊긴 명령이 실제로 실행됐을 수 있으니 restore state로 확인"; fi
grep -v "^    at" "$log" | tail -3 | cut -c1-600
[ "$cmd" = rec ] && (cd "$here" && PYTHONUTF8=1 "$PY" measure.py "$n")
# chain12: 녹화가 끝난 뒤(녹화 중에는 무거운 검사를 하지 않는다) 찍힌 구간마다 프레임 실측(오류 · 업데이트 막대 픽셀 포함)을 돌린다.
if [ "$cmd" = chain12 ]; then
  for t in $(PYTHONUTF8=1 python -c "import json,sys;l=[x for x in open(sys.argv[1],encoding='utf8') if x.startswith('{')];[print(r['name']) for r in json.loads(l[-1])['takes']] if l else sys.exit('no chain result in log')" "$log"); do
    (cd "$here" && PYTHONUTF8=1 "$PY" measure.py "$t")
  done
fi
exit 0
