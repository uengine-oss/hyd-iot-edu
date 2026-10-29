#!/bin/bash
# 구간을 차례로 이어 찍는다(run.sh rec). 앞 구간 끝 화면 · 포인터에서 시작하고, 녹화 오류가 나면 그 구간에서 멈춘다(뒤 구간은 시작하지 않음).
#   ./chain.sh <앞 구간 이름> <이름:모듈> ...   예: ./chain.sh readme-s1 readme-s2:readme-2.mjs readme-s3:readme-3.mjs
set -u
cd "$(dirname "$0")"
prev=$1; shift
for spec in "$@"; do
  name="${spec%%:*}"; mod="${spec#*:}"
  out=$(TMO=${TMO:-900} ./run.sh rec "$name" "$mod" "$prev" | tail -1)
  echo "$out"
  ok=$(echo "$out" | python3 -c "import json,sys;r=json.loads(sys.stdin.read());print('ok' if not r['error'] else 'stop')" 2>/dev/null || echo stop)
  [ "$ok" = ok ] || { echo "STOPPED at $name"; exit 1; }
  prev="$name"
done
echo "CHAIN DONE"
