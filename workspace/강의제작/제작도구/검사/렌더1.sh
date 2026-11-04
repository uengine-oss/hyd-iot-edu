#!/usr/bin/env bash
# 무엇: PPTX 하나를 다시 빌드하지 않고 PDF · 80dpi 장 그림(s-NN.png)으로 렌더하고 글겹침을 잰다. 끝 줄에 장 수 · 글겹침 종료 코드.
# 언제: PPTX를 국소 수정한 뒤 화면을 볼 때. soffice는 한 번에 하나만 돌아, 잠금으로 줄을 서고 다른 세션의 soffice도 끝나길 기다린다.
# 명령: bash workspace/강의제작/제작도구/검사/렌더1.sh <pptx> <새 폴더>   (저장소 어디서든. 클라우드는 앞에 PATH=/usr/local/lo268/bin:$PATH)
set -u
[ $# -eq 2 ] || { sed -n 2,4p "$0"; exit 2; }
X=$1; d=$2
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(git -C "$HERE" rev-parse --show-toplevel)
[ -f "$X" ] || { echo "$X: PPTX가 없다" >&2; exit 2; }
mkdir -p "$d"
if command -v cygpath >/dev/null 2>&1; then   # 이 PC: CLAUDE.md 6절 「렌더 · 영상 도구」
  L=$(cygpath -u "$LOCALAPPDATA")/Microsoft/WinGet/Packages
  export PATH="/c/Program Files/LibreOffice/program:$(ls -d "$L"/oschwartz10612.Poppler_*/poppler-*/Library/bin | head -1):$PATH"
fi
for t in soffice pdftoppm; do command -v $t >/dev/null 2>&1 || { echo "$t이 PATH에 없다" >&2; exit 2; }; done
PY="$ROOT/.venv314/Scripts/python.exe"; [ -x "$PY" ] || PY=python3
LOCK="${TMPDIR:-/tmp}/hyd_렌더잠금"
until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
trap 'rmdir "$LOCK"' EXIT
if command -v tasklist >/dev/null 2>&1; then
  while tasklist 2>/dev/null | grep -qi soffice; do sleep 10; done
else
  while pgrep -x soffice.bin >/dev/null 2>&1; do sleep 10; done
fi
soffice --headless --convert-to pdf --outdir "$d" "$X" >/dev/null 2>&1
pdf="$d/$(basename "${X%.*}").pdf"
[ -f "$pdf" ] || { echo "$X: soffice가 PDF를 만들지 못했다" >&2; exit 1; }
pdftoppm -r 80 -png "$pdf" "$d/s"
PYTHONUTF8=1 "$PY" "$HERE/../기존제작/tools/deck/글겹침.py" "$pdf" > "$d/글겹침.txt" 2>&1; rc=$?
echo "$(ls "$d"/s-*.png | wc -l)장 글겹침종료=$rc $(tail -1 "$d/글겹침.txt" | cut -c1-120)"
exit $rc
