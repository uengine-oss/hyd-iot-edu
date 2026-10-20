#!/usr/bin/env bash
# Git Bash: support per-user installations and apps opened before PATH changed.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    local_apps=$(cygpath -u "${LOCALAPPDATA:-C:/Users/Default/AppData/Local}")
    program_files=$(cygpath -u "${ProgramFiles:-C:/Program Files}")
    for desktop in "$program_files/Docker/Docker/Docker Desktop.exe" \
                   "$local_apps/Programs/DockerDesktop/Docker Desktop.exe" \
                   "$local_apps/Docker/Docker Desktop.exe"; do
      if [ -f "$desktop" ]; then
        DD_EXE="$desktop"
        PATH="$(dirname "$desktop")/resources/bin:$PATH"
        break
      fi
    done
    for bin in "$local_apps/Programs/Python/Launcher" \
               "$local_apps"/Programs/Python/Python3* "$program_files"/Python3* \
               "$program_files/nodejs"; do
      [ ! -d "$bin" ] || PATH="$PATH:$bin"
    done
    export PATH
    ;;
esac
