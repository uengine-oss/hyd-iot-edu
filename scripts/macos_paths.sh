#!/bin/bash
# Finder 로 연 창은 셸 설정을 읽지 않아 Homebrew · Docker 명령이 PATH 에 없다. Homebrew(/opt/homebrew/bin · /usr/local/bin)를
# 시스템 /usr/bin(개발자 도구가 없으면 설치 창을 띄우는 git · python3 자리표시가 있다) 바로 앞에 끼우고, 그보다 앞쪽의 사용자 PATH 는 그대로 둔다.
# PATH 를 「:」로 나눈 항목 단위로 다룬다 — 글자 치환은 /System/Cryptexes/App/usr/bin 안의 /usr/bin 에 걸려 항목을 깨뜨렸다(macOS 13+).

# hyd_brew_first PATH 끼울_항목들(끝이 「:」) → /usr/bin 항목 바로 앞에 끼운 PATH(/usr/bin 이 없으면 끝에 붙인다)
hyd_brew_first() {
  local out='' placed='' entry old_ifs=$IFS
  set -f
  IFS=':'
  for entry in $1; do
    if [ -z "$placed" ] && [ "$entry" = /usr/bin ]; then out="$out$2"; placed=1; fi
    out="$out$entry:"
  done
  IFS=$old_ifs
  set +f
  [ -n "$placed" ] || out="$out$2"
  printf '%s' "${out%:}"
}

if [ "$(uname -s)" = Darwin ]; then
  hyd_brew_paths=''
  for hyd_bin in /opt/homebrew/bin /usr/local/bin; do
    [ ! -d "$hyd_bin" ] || hyd_brew_paths="$hyd_brew_paths$hyd_bin:"
  done
  PATH=$(hyd_brew_first "$PATH" "$hyd_brew_paths")
  for hyd_bin in "$HOME/.docker/bin" \
    /Applications/Docker.app/Contents/Resources/bin \
    "$HOME/Applications/Docker.app/Contents/Resources/bin"; do
    [ ! -d "$hyd_bin" ] || PATH="$PATH:$hyd_bin"
  done
  export PATH
  unset hyd_bin hyd_brew_paths
fi
