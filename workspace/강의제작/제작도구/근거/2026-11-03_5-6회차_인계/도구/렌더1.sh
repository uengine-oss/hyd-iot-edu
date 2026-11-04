#!/usr/bin/env bash
# PPTX 하나를 렌더한다(다시 빌드하지 않음). 사용: bash 렌더1.sh <pptx> <새 폴더>. 잠금으로 이 작업 안에서 한 번에 하나, 다른 세션의 soffice도 끝나길 기다린다.
T=작업/2026-11-03_3-4회차-이론영상-갱신; G=workspace/강의제작; X=$1; d=$2; mkdir -p "$d"
L=$(cygpath -u "$LOCALAPPDATA")/Microsoft/WinGet/Packages
export PATH="/c/Program Files/LibreOffice/program:$(ls -d $L/oschwartz10612.Poppler_*/poppler-*/Library/bin | head -1):$PATH"
until mkdir "$T/렌더잠금" 2>/dev/null; do sleep 10; done
trap 'rmdir "$T/렌더잠금"' EXIT
while tasklist 2>/dev/null | grep -qi soffice; do sleep 10; done
soffice --headless --convert-to pdf --outdir "$d" "$X" >/dev/null 2>&1
pdf=$(ls "$d"/*.pdf | head -1); pdftoppm -r 80 -png "$pdf" "$d/s"
PYTHONUTF8=1 .venv314/Scripts/python.exe $G/제작도구/기존제작/tools/deck/글겹침.py "$pdf" > "$d/글겹침.txt" 2>&1; rc=$?
echo "$(ls "$d"/s-*.png | wc -l)장 글겹침종료=$rc $(tail -1 "$d/글겹침.txt" | cut -c1-120)"
