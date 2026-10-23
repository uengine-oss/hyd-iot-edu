#!/bin/bash
# 구간을 차례로 이어 찍는다(run.sh rec). 앞 구간 끝 페이지 · 포인터에서 시작하고, 녹화 오류나 서비스 오류 문구가
# 나오면 그 구간에서 멈춘다(사소한 움직임 · 프레임 차이로는 멈추지 않는다 — 사용자 기준). 녹화 중에는 같은 PC에서 무거운 작업을 하지 않는다.
#   ./chain.sh <앞 구간 이름> <번호 또는 이름:모듈> ...   예: ./chain.sh take-37 37b:seg-37b.mjs 38 39
# 앞 구간이 실패하면 뒤 구간은 시작하지 않는다(take-38이 잘못된 화면에서 돈 사고 — 2026-10-23).
set -u
cd "$(dirname "$0")"
prev=$1; shift
for n in "$@"; do
  case "$n" in *:*) name="take-${n%%:*}"; mod="${n#*:}";; *) name="take-$n"; mod="seg-$n.mjs";; esac
  out=$(TMO=900 ./run.sh rec "$name" "$mod" "$prev" | tail -1)
  echo "$out"
  ok=$(echo "$out" | PYTHONUTF8=1 python -c "import json,sys;r=json.loads(sys.stdin.read());print('ok' if not r['error'] and not r['banner_frames'] else 'stop')" 2>/dev/null || echo stop)
  [ "$ok" = ok ] || { echo "STOPPED at $n"; exit 1; }
  prev="$name"
done
echo "CHAIN DONE"
