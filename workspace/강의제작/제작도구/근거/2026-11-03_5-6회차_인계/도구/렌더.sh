#!/usr/bin/env bash
# 정본 PPTX를 다시 빌드하지 않고 렌더만 한다. 인자: 렌더 묶음 이름, 대상(온3통합 ...; 없으면 전부). soffice는 한 번에 하나 — 다른 세션이 돌리면 기다린다.
T=작업/2026-11-03_3-4회차-이론영상-갱신; G=workspace/강의제작; OUT=$T/렌더/$1; shift
L=$(cygpath -u "$LOCALAPPDATA")/Microsoft/WinGet/Packages
export PATH="/c/Program Files/LibreOffice/program:$(ls -d $L/oschwartz10612.Poppler_*/poppler-*/Library/bin | head -1):$PATH"
declare -A P=([온3통합]=$G/산출물/통합반/이론/03회차/통합반_03일차.pptx [온3실전]=$G/산출물/실전반/이론/03회차/실전반_03일차.pptx [온4통합]=$G/산출물/통합반/이론/04회차/통합반_04일차.pptx [온4실전]=$G/산출물/실전반/이론/04회차/실전반_04일차.pptx [오3통합]=$G/산출물/통합반/이론_오프라인/03회차/통합반_오프라인_03회차.pptx [오4통합]=$G/산출물/통합반/이론_오프라인/04회차/통합반_오프라인_04회차.pptx [오3실전]=$G/산출물/실전반/이론_오프라인/03회차/실전반_오프라인_03회차.pptx [오4실전]=$G/산출물/실전반/이론_오프라인/04회차/실전반_오프라인_04회차.pptx [오5실전]=$G/산출물/실전반/이론_오프라인/05회차/실전반_오프라인_05회차.pptx)
L2=${@:-온3통합 온3실전 온4통합 온4실전 오3통합 오4통합 오3실전 오4실전 오5실전}
for k in $L2; do d=$OUT/$k; mkdir -p $d
  while tasklist 2>/dev/null | grep -qi soffice; do sleep 20; done
  soffice --headless --convert-to pdf --outdir $d "${P[$k]}" >/dev/null 2>&1
  pdf=$(ls $d/*.pdf); pdftoppm -r 80 -png "$pdf" $d/s
  PYTHONUTF8=1 .venv314/Scripts/python.exe $G/제작도구/기존제작/tools/deck/글겹침.py "$pdf" > $d/글겹침.txt 2>&1; rc=$?
  echo "$k $(ls $d/s-*.png | wc -l)장 글겹침종료=$rc $(tail -1 $d/글겹침.txt | cut -c1-120)"
done
echo 렌더끝
