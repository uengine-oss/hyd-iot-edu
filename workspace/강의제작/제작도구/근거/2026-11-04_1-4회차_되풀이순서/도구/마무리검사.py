"""off02 항목 보존 재주입 · 첫 편 구성 표 낭독 칸 맞추기 · 목록대로 고쳐졌는지 대조 · 고친 범위 대조."""
import glob
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

from pptx import Presentation

W = Path("작업/2026-11-04_1-4회차-이론-되풀이-순서")
BASE = "7e85bdd4"

# 1. off02: 커밋본 항목을 하나하나 그대로(중복 항목 포함) 두고 노트만 바꾼다
md = Path("workspace/강의제작/제작도구/오프라인/decks/practical/off02/실전반_오프라인_02회차.md")
pp = Path("workspace/강의제작/산출물/실전반/이론_오프라인/02회차/실전반_오프라인_02회차.pptx")
base = subprocess.run(["git", "show", f"{BASE}:{pp.as_posix()}"], capture_output=True, check=True).stdout
with zipfile.ZipFile(io.BytesIO(base)) as z:
    names = z.namelist()
dups = sorted({n for n in names if names.count(n) > 1})
print("off02 커밋본 중복 항목", len(dups))
pp.write_bytes(base)
notes = {}
for b in re.split(r"(?=^## SLIDE )", md.read_text("utf8"), flags=re.M)[1:]:
    n = int(re.match(r"## SLIDE (\d+)", b).group(1))
    x = re.search(r"^- 노트:\s*(.*)$", b, re.M)
    notes[n] = (x.group(1).strip() if x else "").replace(" / ", "\n")
prs = Presentation(str(pp))
norm = lambda s: re.sub(r"\s+", " ", s.replace("\x0b", "\n")).strip()
changed = {}
for i, sl in enumerate(prs.slides, 1):
    if norm(sl.notes_slide.notes_text_frame.text) != norm(notes[i]):
        sl.notes_slide.notes_text_frame.text = notes[i]
        changed[str(sl.notes_slide.part.partname).lstrip("/")] = i
tmp = io.BytesIO()
prs.save(tmp)
with zipfile.ZipFile(tmp) as z:
    new = {n: z.read(n) for n in changed}
out = io.BytesIO()
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    with zipfile.ZipFile(io.BytesIO(base)) as zi, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for info in zi.infolist():
            zo.writestr(info, new.get(info.filename, zi.read(info)))
pp.write_bytes(out.getvalue())
print("off02 노트", sorted(changed.values()))

# 2. 회차 첫 편의 「이 회차의 구성」 표 낭독 칸을 구성표 값으로
DECKS = [("통합반", "01"), ("통합반", "02"), ("통합반", "03"), ("통합반", "04"), ("실전반", "01"), ("실전반", "02"), ("실전반", "03"), ("실전반", "04")]
for c, n in DECKS:
    table = {}
    for l in open(f"workspace/강의제작/제작도구/구성/{c}/{n}회차/구성표.md", encoding="utf8"):
        cells = [x.strip() for x in l.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[4].endswith("분"):
            table[cells[1]] = cells[4]
    first = sorted(glob.glob(f"workspace/강의제작/산출물/{c}/이론/{n}회차/대본/*.md"))[0]
    t = open(first, "rb").read().decode("utf8")
    lines, ct = t.split("\n"), 0
    for i, l in enumerate(lines):
        cells = l.rstrip("\r").strip().strip("|").split("|")
        if l.startswith("|") and len(cells) >= 6 and cells[1].strip() in table:
            old = cells[4].strip()
            if old != table[cells[1].strip()] and re.fullmatch(r"[\d.]+분", old):
                cells[4] = f" {table[cells[1].strip()]} "
                lines[i] = "|" + "|".join(cells) + "|" + ("\r" if l.endswith("\r") else "")
                ct += 1
    open(first, "wb").write("\n".join(lines).encode("utf8"))
    print(c, n, "구성 표 고친 칸", ct)

# 3. 목록대로: 적용 항목의 후가 현재 파일에 있고 지운 전이 없는가
sp = lambda s: re.sub(r"\s+", " ", s or "").strip()
bad = total = 0
for p in sorted(glob.glob(str(W / "점검/*.json"))):
    name = Path(p).stem
    c, n = name.split("_")
    v = json.load(open(W / "판정" / f"{name}.json", encoding="utf8"))["판정"]
    text = sp(" ".join(open(f, encoding="utf8", newline="").read() for f in glob.glob(f"workspace/강의제작/산출물/{c}/이론/{n}회차/대본/*.md")))
    for it in json.load(open(p, encoding="utf8"))["고칠것"]:
        x = v[it["번호"]]
        if x["처리"] not in ("적용", "수정") or not it.get("전"):
            continue
        total += 1
        after = sp(x.get("후", it.get("후")))
        for old, new_ in (("맨 아래 줄은", "마지막 줄은"), ("마지막 줄 ORDER BY는", "마지막 줄의 ORDER BY는")):
            after = after.replace(old, new_)
        if after and after not in text:
            # 뒤 항목이 앞 항목 후의 일부를 다시 고친 경우가 있다 — 문장 단위로 다시 본다
            miss = [s for s in re.split(r"(?<=[.?!])\s+", after) if s and s not in text]
            print(" 후 없음", it["번호"], len(miss), (miss[0][:70] if miss else ""))
            bad += bool(miss)
        before = sp(it["전"])
        if not after and text.count(before):
            print(" 전 남음", it["번호"], before[:70], text.count(before))
            bad += 1
print("목록 대조 항목", total, "어긋남", bad)

# 4. 고친 범위: 낭독이 바뀐 구획 수와 항목이 없는데 바뀐 구획
for c, n in DECKS:
    name = f"{c}_{n}" if (c, n) != ("실전반", "01") else "통합반_01"
    items = json.load(open(W / "점검" / f"{name}.json", encoding="utf8"))["고칠것"]
    slides = {it["장"] for it in items}
    add = json.load(open(W / "판정" / f"{name}.json", encoding="utf8"))
    changed, stray = 0, []
    for f in sorted(glob.glob(f"workspace/강의제작/산출물/{c}/이론/{n}회차/대본/*.md")):
        old = subprocess.run(["git", "show", f"{BASE}:{f.replace(chr(92), '/')}"], capture_output=True).stdout.decode("utf8").replace("\r\n", "\n")
        cur = open(f, encoding="utf8", newline="").read().replace("\r\n", "\n")
        blk = lambda t: {int(m.group(1)): sp(" ".join(l for l in m.group(3).split("\n") if l.strip() and not l.startswith((">", "|", "---")))) for m in re.finditer(r"^## \[SLIDE (\d+)(~\d+)?\][^\n]*\n(.*?)(?=^#|\Z)", t, re.M | re.S)}
        a, b = blk(old), blk(cur)
        for s in b:
            if a.get(s) != b[s]:
                changed += 1
                if s not in slides and not (name == "통합반_02" and s == 21):
                    stray.append(s)
    print(c, n, "낭독 바뀐 구획", changed, "항목 없이 바뀐 구획", stray)
