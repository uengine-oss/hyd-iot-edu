# 포털 · Neo4j 녹화 실행기(run.sh · take.sh · neo4j/촬영도구/rec.sh)가 source하는 셸 환경 한 곳. 리눅스(클라우드)와 Windows Git Bash(이 PC)가 다른 것은 여기에만 둔다.
# 정하는 것:
#   linux        true | false
#   HYD_ENV      cloud | pc | ego — 주지 않으면 리눅스는 cloud, Windows는 pc. node 쪽은 env.mjs가 같은 값을 읽는다. ego는 take.sh만 쓴다(이 PC ego 브라우저 안에서 돌리는 옛 길)
#   PY           파이썬. 리눅스 python3, Windows는 환경변수 PY 또는 저장소의 .venv314(없으면 멈춘다). Windows는 PYTHONUTF8=1을 함께 건다
#   pre          node에 넘길 파일 주소의 머리(리눅스 file://, Windows file:///)
#   pwdw         node · 파이썬에 넘길 꼴의 현재 폴더(Windows는 D:/… — Git Bash의 /d/… 는 Windows 프로그램이 못 읽는다)
#   tools        이 폴더(포털 촬영도구)
#   cdp_port <config.json>             그 도구의 CDP 포트
#   browser_up <config.json> <work>    녹화 브라우저(browser.mjs)를 그 config로 띄운다. 이미 떠 있으면 그대로. PID는 browser.mjs가 찍은 값을 <work>/browser.pid에 남긴다
#   browser_down <config.json> <work>  그 PID로 끄고(Windows는 자식 Chromium까지 taskkill) 포트가 내려갔는지 확인한다. 한글 경로는 pkill -f가 못 찾는다
#   busy <정규식>                       명령줄이 그 정규식에 맞는 node 프로세스가 돌고 있으면 참
linux=false; [ "$(uname -s)" = Linux ] && linux=true
HYD_ENV=${HYD_ENV:-$($linux && echo cloud || echo pc)}
case "$HYD_ENV" in cloud|pc|ego) ;; *) echo "HYD_ENV=$HYD_ENV: cloud | pc | ego 가운데 하나 (env.sh)"; exit 2;; esac
export HYD_ENV
if $linux; then pwdw(){ pwd; }; pre="file://"; PY=python3
else pwdw(){ pwd -W; }; pre="file:///"; export PYTHONUTF8=1; fi
tools="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwdw)"
if ! $linux; then PY=${PY:-$tools/../../../../../../.venv314/Scripts/python.exe}; [ -x "$PY" ] || { echo "파이썬 없음: $PY — 환경변수 PY에 python.exe 경로를 준다 (env.sh)"; exit 2; }; fi
cdp_port(){ "$PY" -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['cdp'])" "$1"; }
_alive(){ curl -s -m 2 "http://127.0.0.1:$1/json/version" >/dev/null; }
browser_up(){
  local cfg=$1 work=$2 port; port=$(cdp_port "$cfg") || return 2
  _alive "$port" && { echo "already up :$port"; return 0; }
  mkdir -p "$work"
  (HYD_BROWSER_CONFIG="$cfg" nohup node "$tools/browser.mjs" > "$work/browser.log" 2>&1 < /dev/null &)
  for i in $(seq 1 30); do
    _alive "$port" && grep -q '"ready":true' "$work/browser.log" && { grep -o '"pid":[0-9]*' "$work/browser.log" | tail -1 | cut -d: -f2 > "$work/browser.pid"; tail -1 "$work/browser.log"; return 0; }
    sleep 1
  done
  echo "browser did not start"; cat "$work/browser.log"; return 1
}
browser_down(){
  local cfg=$1 work=$2 port; port=$(cdp_port "$cfg") || return 2
  if [ -f "$work/browser.pid" ]; then if $linux; then kill "$(cat "$work/browser.pid")" 2>/dev/null; else taskkill //PID "$(cat "$work/browser.pid")" //T //F >/dev/null 2>&1; fi; fi
  sleep 2
  _alive "$port" && { echo "STILL UP :$port"; return 1; }
  echo "down"
}
busy(){
  if $linux; then ps -eo args | grep -E "^node " | grep -qE "$1"
  else [ "$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | ? { \$_.CommandLine -match '$1' }).Count" | tr -dc 0-9)" != "0" ]; fi
}
