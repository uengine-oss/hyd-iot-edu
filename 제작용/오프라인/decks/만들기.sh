#!/usr/bin/env bash
# 오프라인 이론 덱 하나를 조립 → 빌드 → 원 PPTX 대조(위치 옮김 포함) → 노트 점검 → 렌더 → 글겹침까지 돌린다.
# bash 제작용/오프라인/decks/만들기.sh integrated 01 [렌더 폴더]
set -euo pipefail
cd "$(dirname "$0")/../../.."
course=$1; n=$2; out=${3:-}
case $course in integrated) name=통합반;; practical) name=실전반;; *) echo "과정은 integrated/practical"; exit 1;; esac
dir=제작용/오프라인/decks/$course/off$n
md=$dir/${name}_오프라인_${n}회차.md
pptx=산출물/$name/이론_오프라인/${n}회차/${name}_오프라인_${n}회차.pptx
mkdir -p "$(dirname "$pptx")"
python3 제작용/오프라인/decks/조립.py "$dir"
python3 .claude/skills/lecture-deck/scripts/deck2pptx.py "$md" "$pptx" | tail -1
python3 제작용/오프라인/decks/대조.py "$md" "$pptx" --fix | tail -3
python3 제작용/오프라인/decks/대조.py "$md" "$pptx" | tail -1
python3 제작용/오프라인/decks/노트점검.py "$md" "$pptx"
if [ -n "$out" ]; then
  rm -rf "$out"; mkdir -p "$out"
  timeout 300 soffice --headless --convert-to pdf --outdir "$out" "$pptx" >/dev/null 2>&1
  python3 제작용/기존제작/tools/deck/글겹침.py "$out/$(basename "${pptx%.pptx}").pdf" | tail -3 || true
  pdftoppm -r 50 -png "$out/$(basename "${pptx%.pptx}").pdf" "$out/p"
fi
