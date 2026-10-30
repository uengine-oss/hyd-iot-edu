#!/usr/bin/env bash
# 시작 · 점검이 쓸 Python(scripts/versions.txt 의 PYTHON_MIN 이상)을 찾아 PYTHON 배열에 둔다(없으면 빈 배열).
# scripts/windows_paths.sh · macos_paths.sh · versions.txt 를 먼저 불러 둔 뒤 `. scripts/find_python.sh` 로 쓴다(macOS 기본 Bash 3.2 호환).
hyd_python_ok() { "$@" -c "import sys; sys.exit(0 if sys.version_info >= tuple(map(int, '$PYTHON_MIN'.split('.'))) else 1)" >/dev/null 2>&1; }
PYTHON=()
for hyd_candidate in python python3 /opt/homebrew/opt/python@3.14/bin/python3.14 /usr/local/opt/python@3.14/bin/python3.14 \
  /Library/Frameworks/Python.framework/Versions/*/bin/python3 \
  "${local_apps:-/nonexistent}"/Programs/Python/Python*/python.exe "${program_files:-/nonexistent}"/Python*/python.exe; do
  command -v "$hyd_candidate" >/dev/null 2>&1 || continue
  # Mac: 개발자 도구가 없으면 /usr/bin/python3 은 실행하는 순간 설치 창을 띄우는 자리표시 — 건너뛴다(git 과 같은 판정)
  if [ "$(command -v "$hyd_candidate")" = /usr/bin/python3 ] && [ "$(uname -s)" = Darwin ] && ! xcode-select -p >/dev/null 2>&1; then continue; fi
  if hyd_python_ok "$hyd_candidate"; then PYTHON=("$hyd_candidate"); break; fi
done
if [ "${#PYTHON[@]}" -eq 0 ] && command -v py >/dev/null 2>&1 && hyd_python_ok py -3; then PYTHON=(py -3); fi
unset hyd_candidate
