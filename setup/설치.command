#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
/bin/bash scripts/install_macos.sh
result=$?
if [ -t 0 ]; then read -r -p '창을 닫으려면 Enter: ' _; fi
exit "$result"
