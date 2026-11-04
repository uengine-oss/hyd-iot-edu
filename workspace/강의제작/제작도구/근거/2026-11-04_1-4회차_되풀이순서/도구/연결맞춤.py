"""심각 항목 적용 뒤 연결 산출물: 화면 구성 줄 · PPTX 노트 · 첫 편 구성 표 · 오프라인 덱."""
import glob
import io
import os
import re
import subprocess
import sys
import warnings
import zipfile
from pathlib import Path

from pptx import Presentation

BASE = "7e85bdd4"
W = Path("작업/2026-11-04_1-4회차-이론-되풀이-순서")
env = dict(os.environ, PYTHONUTF8="1")
ALL = [("통합반", "01"), ("통합반", "02"), ("통합반", "03"), ("통합반", "04"), ("실전반", "01"), ("실전반", "02"), ("실전반", "03"), ("실전반", "04")]


def run(*a):
    r = subprocess.run(a, capture_output=True, env=env)
    return r.returncode, (r.stdout + r.stderr).decode("utf8", "replace")


# 화면 구성 줄(화면에 나가지 않는 칸): P3-08 · P3-34가 살아 있고 노트가 바뀐 장만
D3 = "workspace/강의제작/제작도구/온라인/decks/practical/day03/실전반_03일차.md"
t = open(D3, "rb").read().decode("utf8")
for n in (11, 47):
    m = re.search(rf"^## SLIDE {n} — .*?(?=^## SLIDE )", t, re.M | re.S)
    b = m.group(0)
    nt = re.search(r"^- 노트: \[짚을 곳\] (.*?)(?: / |\r?$)", b, re.M).group(1).strip()
    lay = re.search(r"^### 화면 구성\r?\n(.*?)\r?$", b, re.M)
    t = t[: m.start()] + b[: lay.start(1)] + nt + "." + b[lay.end(1):] + t[m.end():]
open(D3, "wb").write(t.encode("utf8"))

# PPTX 노트
for c, n in ALL:
    code, out = run(sys.executable, str(W / "도구/노트주입.py"), c, n, "--실행")
    print(out.strip().replace("\n", " ")[:170], "" if code == 0 else "실패")

# 구성 표
for c, n in ALL:
    table = {}
    for l in open(f"workspace/강의제작/제작도구/구성/{c}/{n}회차/구성표.md", encoding="utf8"):
        x = [y.strip() for y in l.strip().strip("|").split("|")]
        if len(x) == 5 and x[4].endswith("분"):
            table[x[1]] = x[4]
    f = sorted(glob.glob(f"workspace/강의제작/산출물/{c}/이론/{n}회차/대본/*.md"))[0]
    L = open(f, "rb").read().decode("utf8").split("\n")
    ct = 0
    for i, l in enumerate(L):
        x = l.rstrip("\r").strip().strip("|").split("|")
        if l.startswith("|") and len(x) >= 5 and x[1].strip() in table and re.fullmatch(r"[\d.]+분", x[4].strip()) and x[4].strip() != table[x[1].strip()]:
            x[4] = f" {table[x[1].strip()]} "
            L[i] = "|" + "|".join(x) + "|" + ("\r" if l.endswith("\r") else "")
            ct += 1
    open(f, "wb").write("\n".join(L).encode("utf8"))
    print(c, n, "구성 표 칸", ct)

# 오프라인: 조립 → MD가 커밋본과 다르면 다시 만든다. 실전 off02는 커밋본 + 노트만
O = "workspace/강의제작/제작도구/오프라인/decks"
for k, n in [("integrated", x) for x in ("01", "02", "03", "04")] + [("practical", x) for x in ("01", "02", "03", "04", "05")]:
    name = {"integrated": "통합반", "practical": "실전반"}[k]
    md = f"{O}/{k}/off{n}/{name}_오프라인_{n}회차.md"
    pp = f"workspace/강의제작/산출물/{name}/이론_오프라인/{n}회차/{name}_오프라인_{n}회차.pptx"
    run(sys.executable, f"{O}/조립.py", f"{O}/{k}/off{n}")
    base = subprocess.run(["git", "show", f"{BASE}:{md}"], capture_output=True).stdout.replace(b"\r\n", b"\n")
    if open(md, "rb").read().replace(b"\r\n", b"\n") == base:
        print(k, n, "노트 변화 없음 — 그대로")
        restore = subprocess.run(["git", "show", f"{BASE}:{md}"], capture_output=True).stdout
        open(md, "wb").write(restore)
        continue
    if (k, n) == ("practical", "02"):
        data = subprocess.run(["git", "show", f"{BASE}:{pp}"], capture_output=True, check=True).stdout
        open(pp, "wb").write(data)
        notes = {}
        for b in re.split(r"(?=^## SLIDE )", open(md, encoding="utf8").read(), flags=re.M)[1:]:
            s = int(re.match(r"## SLIDE (\d+)", b).group(1))
            x = re.search(r"^- 노트:\s*(.*)$", b, re.M)
            notes[s] = (x.group(1).strip() if x else "").replace(" / ", "\n")
        prs = Presentation(pp)
        norm = lambda v: re.sub(r"\s+", " ", v.replace("\x0b", "\n")).strip()
        changed = {}
        for i, sl in enumerate(prs.slides, 1):
            if norm(sl.notes_slide.notes_text_frame.text) != norm(notes[i]):
                sl.notes_slide.notes_text_frame.text = notes[i]
                changed[str(sl.notes_slide.part.partname).lstrip("/")] = i
        tmp = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            prs.save(tmp)
        with zipfile.ZipFile(tmp) as z:
            new = {a: z.read(a) for a in changed}
        out = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as zi, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
            for info in zi.infolist():
                zo.writestr(info, new.get(info.filename, zi.read(info)))
        open(pp, "wb").write(out.getvalue())
        r1 = run(sys.executable, f"{O}/대조.py", md, pp)[1].strip().split("\n")[-1]
        r2 = run(sys.executable, f"{O}/노트점검.py", md, pp)[1].strip().split("\n")[-1]
        print(k, n, "노트만", sorted(changed.values()), r1[:40], r2[:30])
        continue
    print(k, n, "만들기는 Git Bash에서"); continue
    L = out.strip().split("\n")
    print(k, n, "다시 만듦", L[-2][:40], L[-1][:30], "" if code == 0 else "실패")
