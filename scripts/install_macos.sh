#!/bin/bash
# macOS 기본 Bash 3.2 호환. 기준 판은 scripts/versions.txt 하나(Windows 설치 · 시작과 같은 파일).
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/versions.txt"
PYTHON_FORMULA="python@${PYTHON_NEW%.*}"   # 예: 3.14.7 → python@3.14 (없거나 기준보다 낮을 때 새로 넣는 판)

version_valid() { [[ "$1" =~ ^[0-9]+(\.[0-9]+){1,3}$ ]]; }
version_ge() {
  version_valid "$1" && version_valid "$2" || return 2
  awk -v current="$1" -v minimum="$2" 'BEGIN {
    split(current,a,"."); split(minimum,b,".");
    for(i=1;i<=4;i++) { if(a[i]+0>b[i]+0) exit 0; if(a[i]+0<b[i]+0) exit 1 }
    exit 0
  }'
}

# missing과 unknown을 구별한다. 읽을 수 없는 기존 앱은 덮어쓰지 않는다.
detect_version() {
  local app='' candidate='' found='' output=''
  if [ "$1" = "$PYTHON_FORMULA" ]; then
    local best='' v='' line="${PYTHON_NEW%.*}"
    for candidate in python3 "/opt/homebrew/opt/$PYTHON_FORMULA/bin/python$line" "/usr/local/opt/$PYTHON_FORMULA/bin/python$line" /Library/Frameworks/Python.framework/Versions/*/bin/python3; do
      command -v "$candidate" >/dev/null 2>&1 || continue
      # 개발자 도구가 없으면 /usr/bin/python3 은 실행하는 순간 설치 창을 띄우는 자리표시 — 건너뛴다(git 과 같은 판정)
      if [ "$(command -v "$candidate")" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; then continue; fi
      v=$("$candidate" --version 2>/dev/null) || continue
      v=${v#Python }
      version_valid "$v" || continue
      if [ -z "$best" ] || version_ge "$v" "$best"; then best="$v"; fi
    done
    echo "${best:-missing}"
    return
  fi
  case "$1" in
    docker-desktop) app='Docker.app' ;;
    visual-studio-code) app='Visual Studio Code.app' ;;
  esac
  if [ -n "$app" ]; then
    for candidate in "/Applications/$app" "$HOME/Applications/$app"; do
      if [ -d "$candidate" ]; then
        [ -z "$found" ] || { echo unknown; return; }
        found="$candidate"
      fi
    done
    [ -n "$found" ] || { echo missing; return; }
    output=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$found/Contents/Info.plist" 2>/dev/null) || output=''
  else
    command -v "$1" >/dev/null 2>&1 || { echo missing; return; }
    # /usr/bin/git은 CLT가 없으면 설치 대화상자를 띄우는 stub이다.
    if [ "$1" = git ] && [ "$(command -v git)" = /usr/bin/git ] && ! xcode-select -p >/dev/null 2>&1; then
      echo missing; return
    fi
    output=$("$1" --version 2>/dev/null) || { echo unknown; return; }
    case "$1" in
      node) output=${output#v} ;;
      git) output=${output#git version }; output=${output%% *} ;;
    esac
  fi
  if version_valid "$output"; then echo "$output"; else echo unknown; fi
}

ensure_brew() {
  if ! command -v brew >/dev/null 2>&1; then
    echo 'Homebrew를 준비합니다. 설치 내용과 관리자 암호 요청을 터미널에서 확인하세요.'
    local installer
    installer=$(mktemp -t hyd-homebrew) || return 1
    if ! curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$installer"; then
      rm -f "$installer"; return 1
    fi
    /bin/bash "$installer"
    local code=$?
    rm -f "$installer"
    [ "$code" -eq 0 ] || return "$code"
    . "$(dirname "${BASH_SOURCE[0]}")/macos_paths.sh"
  fi
  command -v brew >/dev/null 2>&1
}

install_package() {
  local package="$1" kind="$2" appdir=/Applications
  ensure_brew || return 1
  # 전체 upgrade를 실행하지 않으며, 자동 정리와 다른 설치 항목 점검도 제외한다.
  export HOMEBREW_NO_INSTALL_CLEANUP=1 HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1
  if [ "$kind" = cask ]; then
    case "$package" in
      docker-desktop) [ ! -d "$HOME/Applications/Docker.app" ] || appdir="$HOME/Applications" ;;
      visual-studio-code) [ ! -d "$HOME/Applications/Visual Studio Code.app" ] || appdir="$HOME/Applications" ;;
    esac
    if brew list --cask "$package" >/dev/null 2>&1; then
      brew upgrade --cask --greedy --appdir="$appdir" "$package"
    else
      # 이 함수는 없거나 낮은 버전만 호출한다. 수동 설치 앱도 같은 위치에서 갱신한다.
      brew install --cask --force --appdir="$appdir" "$package"
    fi
  else
    if brew list --formula "$package" >/dev/null 2>&1; then
      brew upgrade --formula "$package"
    else
      brew install --formula "$package"
    fi
  fi
}

ensure_package() {
  local package="$1" minimum="$2" kind="$3" before after
  before=$(detect_version "$package")
  if [ "$before" = unknown ]; then
    echo "[실패] $package: 기존 버전을 확인할 수 없습니다. 중복 설치·앱 위치·PATH를 확인하세요."
    return 1
  fi
  if [ "$before" != missing ] && version_ge "$before" "$minimum"; then
    echo "[유지] $package $before (기준 $minimum)"
    return 0
  fi
  echo "[설치/업데이트] $package: $before → 최소 $minimum"
  install_package "$package" "$kind" || { echo "[실패] $package 설치 명령 실패"; return 1; }
  . "$(dirname "${BASH_SOURCE[0]}")/macos_paths.sh"
  hash -r
  after=$(detect_version "$package")
  if ! version_ge "$after" "$minimum"; then
    echo "[실패] $package: 설치 후 $after, 기준 $minimum 미충족. 배포 버전·앱 위치·PATH를 확인하세요."
    return 1
  fi
  echo "[완료] $package $after"
}

main() {
  [ "$(uname -s)" = Darwin ] || { echo 'Mac 전용 설치 도구입니다.'; return 1; }
  [ "$(id -u)" -ne 0 ] || { echo 'sudo로 전체 스크립트를 실행하지 마세요. 일반 계정에서 설치.command를 여세요.'; return 1; }
  . "$(dirname "${BASH_SOURCE[0]}")/macos_paths.sh"
  local failed=0
  ensure_package docker-desktop "$DOCKER_DESKTOP_MIN" cask || failed=1
  ensure_package visual-studio-code "$VSCODE_MIN" cask || failed=1
  ensure_package node "$NODE_MIN" formula || failed=1
  ensure_package git "$GIT_MIN" formula || failed=1
  ensure_package "$PYTHON_FORMULA" "$PYTHON_MIN" formula || failed=1   # 기준 이상 Python 이 있으면 그대로(Windows 와 같게)
  echo 'Supabase CLI 실행 파일을 준비합니다(시스템 데이터는 시작 파일에서 받습니다).'
  local supabase_version
  supabase_version=$(npx -y "supabase@$SUPABASE_CLI" --version) || failed=1
  version_ge "$supabase_version" "$SUPABASE_CLI" || failed=1
  echo 'Mac에는 WSL이 필요 없습니다.'
  if [ "$failed" -eq 0 ]; then
    echo '도구가 기준을 만족합니다. Docker Desktop의 초기 설정을 완료한 뒤 시작.command를 실행하세요.'
  else
    echo '실패 항목을 해결한 뒤 다시 실행하세요. 기준 이상인 항목은 유지합니다.'
  fi
  return "$failed"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then main "$@"; fi
