"""덱 MD의 노트를 PPTX 노트 칸에 넣는다 — 노트가 다른 장의 notesSlide XML 항목만 바꾸고 나머지 ZIP 항목은 바이트 그대로다.
언제: 낭독 · 노트만 고쳐 PPTX를 다시 빌드하지 않을 때(온라인 · 오프라인 덱 모두). --실행 없으면 다른 장만 센다.
명령: <py> workspace/강의제작/제작도구/검사/노트주입.py <덱.md> <덱.pptx> --기준 <커밋|파일> [--실행] [--화면허용 slideN.xml …]

끝에 기준본과 항목별 바이트를 비교해 노트 밖 차이가 있으면 실패한다(--화면허용으로 일부러 고친 화면 항목만 허용). 기준은 고치기 전 커밋(PPTX의 저장소 경로로 찾음) 또는 파일.
"""
import argparse, io, os, re, subprocess, sys, zipfile
from pathlib import Path

from pptx import Presentation


def base_bytes(ref, pptx):
    if Path(ref).is_file():
        return Path(ref).read_bytes()
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, cwd=pptx.resolve().parent, check=True).stdout.strip()
    rel = pptx.resolve().relative_to(Path(top).resolve()).as_posix()
    r = subprocess.run(["git", "show", f"{ref}:{rel}"], capture_output=True, cwd=top)
    if r.returncode:
        sys.exit(f"기준 {ref}에 {rel}이 없다")
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md"); ap.add_argument("pptx")
    ap.add_argument("--기준", dest="base", required=True)
    ap.add_argument("--실행", dest="run", action="store_true")
    ap.add_argument("--화면허용", dest="allow", action="append", default=[])
    a = ap.parse_args()
    md, pptx = Path(a.md), Path(a.pptx)
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
    print(pptx.name, "노트 다른 장", sorted(changed.values()))
    if not a.run:
        return
    if changed:
        tmp = io.BytesIO()
        prs.save(tmp)
        with zipfile.ZipFile(tmp) as z:
            new = {n: z.read(n) for n in changed}
        out = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(pptx.read_bytes())) as zi, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
            for info in zi.infolist():
                zo.writestr(info, new.get(info.filename, zi.read(info.filename)))
        pptx.write_bytes(out.getvalue())
    with zipfile.ZipFile(io.BytesIO(base_bytes(a.base, pptx))) as b, zipfile.ZipFile(pptx) as c:
        if b.namelist() != c.namelist():
            sys.exit("ZIP 항목 목록이 달라졌다")
        diff = [n for n in b.namelist() if b.read(n) != c.read(n)]
    outside = [n for n in diff if not re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n) and os.path.basename(n) not in a.allow]
    print(" 기준본과 다른 항목", len(diff), "노트 밖", outside)
    if outside:
        sys.exit(1)


if __name__ == "__main__":
    main()
