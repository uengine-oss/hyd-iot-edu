#!/bin/bash
# Finder의 시스템 Git stub보다 Homebrew를 먼저 찾되 앞쪽의 사용자 PATH는 유지한다.
if [ "$(uname -s)" = Darwin ]; then
  hyd_brew_paths=''
  for hyd_bin in /opt/homebrew/bin /usr/local/bin; do
    [ ! -d "$hyd_bin" ] || hyd_brew_paths="$hyd_brew_paths$hyd_bin:"
  done
  case ":$PATH:" in
    *:/usr/bin:*) PATH="${PATH/\/usr\/bin/$hyd_brew_paths/usr/bin}" ;;
    *) PATH="$PATH:$hyd_brew_paths" ;;
  esac
  for hyd_bin in "$HOME/.docker/bin" \
    /Applications/Docker.app/Contents/Resources/bin \
    "$HOME/Applications/Docker.app/Contents/Resources/bin"; do
    [ ! -d "$hyd_bin" ] || PATH="$PATH:$hyd_bin"
  done
  export PATH
  unset hyd_bin hyd_brew_paths
fi
