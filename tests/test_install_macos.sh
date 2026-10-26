#!/bin/bash
# 실제 설치 없이 정책·설치 실패·설치 후 재확인을 검사한다.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/install_macos.sh
passed=0
check() {
  if "$@"; then passed=$((passed+1)); else echo "FAIL: $*"; exit 1; fi
}
reject() { if "$@"; then return 1; else return 0; fi; }
check version_ge 4.87.0 4.87.0
check version_ge 4.100.0 4.87.0
check reject version_ge 4.9.0 4.87.0
check version_ge 25.0.0 24.22.1
check version_ge 2.54 2.54.0
check reject version_ge unknown 2.54.0
check reject version_ge 2.54.0-beta 2.54.0

run_case() (
  local initial="$1" installed="$2" install_code="$3" expected_calls="$4" expected_result="$5"
  local calls=0 result=0 state="$initial"
  detect_version() { echo "$state"; }
  install_package() { calls=$((calls+1)); state="$installed"; return "$install_code"; }
  ensure_package node 24.22.1 formula >/dev/null || result=$?
  [ "$calls" -eq "$expected_calls" ] && [ "$result" -eq "$expected_result" ]
)
check run_case 24.22.1 unused 0 0 0
check run_case 25.0.0 unused 0 0 0
check run_case 24.9.0 24.22.1 0 1 0
check run_case missing 25.0.0 0 1 0
check run_case unknown unused 0 0 1
check run_case missing unknown 0 1 1
check run_case 24.9.0 24.10.0 0 1 1
check run_case missing 24.22.1 1 1 1

# 패키지 선택/명령은 mock으로 확인한다. 실제 brew를 실행하지 않는다.
brew_case() (
  local kind="$1" managed="$2" expected="$3" calls=''
  ensure_brew() { :; }
  brew() {
    if [ "$1" = list ]; then return "$managed"; fi
    calls="$*"
  }
  install_package test-package "$kind"
  [ "$calls" = "$expected" ]
)
check brew_case formula 1 'install --formula test-package'
check brew_case formula 0 'upgrade --formula test-package'
check brew_case cask 1 'install --cask --force --appdir=/Applications test-package'
check brew_case cask 0 'upgrade --cask --greedy --appdir=/Applications test-package'
echo "PASS: $passed cases (no real installation)"
