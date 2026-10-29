#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
if [ "$(uname -s)" != Darwin ]; then
  echo 'Mac 전용입니다. Windows에서는 시작.bat을 실행하세요.'
  exit 1
fi
/bin/bash scripts/start_all.sh
result=$?
if [ -t 0 ]; then read -r -p '창을 닫으려면 Enter: ' _; fi
exit "$result"
