#!/bin/bash
# ego 실행기. 저장소의 촬영도구를 ego 안에서 불러 돌린다(Git Bash).
#   ./run.sh rec <이름> <구간> [시작큐] [이전 구간 이름] [relax]   구간 하나 녹화(relax: 그림 주소가 바뀐 뒤 첫 구간)
#   ./run.sh restore <이전 구간 이름> [출발원 도착원]               녹화 밖 상태 복원(가져오기 + 원 크기 + 마지막 화살표 선택)
#   ./run.sh coords                                                  사용자가 배치한 그림들의 저장 좌표 읽기(읽기 전용)
# 실행 전 node --check로 문법 오류를 막고(ego는 문법 오류에 조용히 멈춘다), stdin을 닫는다(-e가 입력을 기다린다).
# 시간 초과(TMO초, 기본 600) 시 ego의 NodeService(스크립트 실행기)만 정리한다. 브라우저 창 · 탭은 건드리지 않는다.
set -u
here="$(cd "$(dirname "$0")" && pwd -W)"
work="$(PYTHONUTF8=1 python -c "import sys;sys.path.insert(0,r'$here');from common import WORK;print(WORK.as_posix())")"
for f in ctrl.mjs ui.mjs restore.mjs; do node --check "$here/$f" || { echo "SYNTAX ERROR in $f: ego로 보내지 않음"; exit 2; }; done
cmd=$1; shift
stamp=$(date +%s)
case "$cmd" in
  rec)
    n=$1; seg=$2; from=${3:-}; st=${4:-}; relax=false; [ -n "${5:-}" ] && relax=true
    mkdir -p "$work"
    js="const {run}=await import('file:///$here/ctrl.mjs?$n');console.log(JSON.stringify(await run({name:'$n',segment:$seg,from:'$from',startState:'$st',expectUrl:'arrows.app',to:'${TO:-}',relaxUrl:$relax})));"
    log="$work/$n.log";;
  restore)
    take=$1; e1=${2:-}; e2=${3:-}
    edge=$([ -n "$e1" ] && echo "['$e1','$e2']" || echo "null")
    js="const {restore}=await import('file:///$here/restore.mjs?$stamp');console.log(JSON.stringify(await restore({take:'$take',edge:$edge})));"
    log="$work/restore-$stamp.log";;
  coords)
    js="const {coords}=await import('file:///$here/restore.mjs?$stamp');console.log(JSON.stringify(await coords()));"
    log="$work/coords-$stamp.log";;
  *) sed -n 2,5p "$0"; exit 2;;
esac
runner="$work/run-$cmd-$stamp.mjs"
printf '%s\n' "$js" > "$runner"
node --check "$runner" || { echo "SYNTAX ERROR in $runner"; exit 2; }
timeout ${TMO:-600} ego-browser nodejs -e "await import('file:///$runner')" < /dev/null > "$log" 2>&1
rc=$?
if [ $rc -eq 124 ]; then powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='ego.exe'\" | ? { \$_.CommandLine -match 'ego.mojom.NodeService' } | % { Stop-Process -Id \$_.ProcessId -Force }"; echo "TIMEOUT: NodeService만 정리함 — 끊긴 명령이 실제로 실행됐을 수 있으니 저장 데이터로 상태를 확인"; fi
grep -v "^    at" "$log" | tail -3 | cut -c1-600
