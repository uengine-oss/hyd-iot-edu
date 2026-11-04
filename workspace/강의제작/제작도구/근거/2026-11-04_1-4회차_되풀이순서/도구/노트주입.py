"""덱 MD 노트를 커밋본 PPTX 노트 칸에 넣는다 — 노트가 다른 장의 notesSlide XML 항목만 바꾸고 나머지 ZIP 항목은 바이트 그대로다.

python 노트주입.py <과정> <NN> [--실행]   (없으면 다른 장만 센다)
끝에 커밋본과 항목별 바이트를 비교해 노트 밖 차이가 있으면 실패한다(--화면허용 slideN.xml 로 일부러 고친 화면 항목만 허용).
"""
import argparse
import io
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from pptx import Presentation

ap = argparse.ArgumentParser()
ap.add_argument("과정")
ap.add_argument("회차")
ap.add_argument("--실행", action="store_true")
ap.add_argument("--기준", default="7e85bdd4")
ap.add_argument("--화면허용", action="append", default=[])
a = ap.parse_args()
DECK = {"통합반": "integrated", "실전반": "practical"}
md = Path(f"workspace/강의제작/제작도구/온라인/decks/{DECK[a.과정]}/day{a.회차}/{a.과정}_{a.회차}일차.md")
pptx = Path(f"workspace/강의제작/산출물/{a.과정}/이론/{a.회차}회차/{a.과정}_{a.회차}일차.pptx")
notes = {}
for block in re.split(r"(?=^## SLIDE )", md.read_text("utf8"), flags=re.M)[1:]:
    n = int(re.match(r"## SLIDE (\d+)", block).group(1))
    m = re.search(r"^- 노트:\s*(.*)$", block, re.M)
    notes[n] = (m.group(1).strip() if m else "").replace(" / ", "\n")
prs = Presentation(str(pptx))
if len(prs.slides) != len(notes):
    sys.exit(f"{pptx}: 장 수 {len(prs.slides)} ≠ 덱 MD {len(notes)}")
norm = lambda s: re.sub(r"\s+", " ", s.replace("\x0b", "\n")).strip()
changed = {}
for i, sl in enumerate(prs.slides, 1):
    if not sl.has_notes_slide:
        sys.exit(f"{pptx}: 장 {i}에 노트 칸이 없다")
    if norm(sl.notes_slide.notes_text_frame.text) != norm(notes[i]):
        sl.notes_slide.notes_text_frame.text = notes[i]
        changed[str(sl.notes_slide.part.partname).lstrip("/")] = i
print(a.과정, a.회차, "노트 다른 장", sorted(changed.values()))
if not a.실행:
    sys.exit(0)
if changed:
    tmp = io.BytesIO()
    prs.save(tmp)
    with zipfile.ZipFile(tmp) as z:
        new = {n: z.read(n) for n in changed}
    src = pptx.read_bytes()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src)) as zi, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for info in zi.infolist():
            zo.writestr(info, new.get(info.filename, zi.read(info.filename)))
    pptx.write_bytes(out.getvalue())
# 항목별 바이트 대조
base = subprocess.run(["git", "show", f"{a.기준}:{pptx.as_posix()}"], capture_output=True, check=True).stdout
with zipfile.ZipFile(io.BytesIO(base)) as b, zipfile.ZipFile(pptx) as c:
    if b.namelist() != c.namelist():
        sys.exit("ZIP 항목 목록이 달라졌다")
    diff = [n for n in b.namelist() if b.read(n) != c.read(n)]
outside = [n for n in diff if not re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n) and os.path.basename(n) not in a.화면허용]
print(" 커밋본과 다른 항목", len(diff), "노트 밖", outside)
if outside:
    sys.exit(1)
