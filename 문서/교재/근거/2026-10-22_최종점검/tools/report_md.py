"""전 · 후를 MD 한 장으로. 바뀐 장마다 대본 전체를 싣고, 지운 말은 ~~취소선~~, 넣은 말은 **굵게**.

    python3 report_md.py <저장소 루트> <결과 폴더> <회차 01 · 02> <출력 md>
"""
import difflib
import re
import sys
from pathlib import Path

ROOT, F2, NN, OUT = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
AGENTS = {"02": {("통합반", "01"): "A", ("통합반", "02"): "B", ("통합반", "03"): "C",
                  ("실전반", "01"): "A", ("실전반", "03"): "C", ("실전반", "04"): "D"},
          "01": {("통합반", "01"): "E", ("통합반", "02"): "F", ("통합반", "03"): "G"}}[NN]
HEAD = re.compile(r"^## \[SLIDE ([0-9~]+)\](.*)$", re.M)
TOK = re.compile(r"\s+|[가-힣A-Za-z0-9_]+|.", re.S)


def norm(lab): return "~".join(str(int(x)) for x in lab.split("~"))


def sections(text):
    out = []
    for m in HEAD.finditer(text):
        nxt = re.compile(r"^#{1,2} ", re.M).search(text, m.end())
        out.append((norm(m.group(1)), m.group(2).strip(), text[m.end():nxt.start() if nxt else len(text)].strip("\n")))
    return out


def esc(s): return re.sub(r"([~*_])", r"\\\1", s)


def inline(a, b):
    ta, tb = TOK.findall(a), TOK.findall(b)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        x, y = "".join(ta[i1:i2]), "".join(tb[j1:j2])
        if op == "equal": out.append(esc(x)); continue
        for s, mark in ((x, "~~"), (y, "**")):
            core = s.strip()
            if not core: out.append(s); continue
            if "\n" in core:   # 문단 단위로 지우거나 넣은 것
                core = "\n\n".join(f"{mark}{esc(p.strip())}{mark}" for p in re.split(r"\n\s*\n", core) if p.strip())
                out.append(core)
            else:
                lead, trail = s[:len(s) - len(s.lstrip())], s[len(s.rstrip()):]
                out.append(f"{lead}{mark}{esc(core)}{mark}{trail}")
    return "".join(out)


def rows_of(path):
    rows = []
    if not path.exists(): return rows
    for line in path.read_text("utf-8").splitlines():
        if not line.startswith("|") or re.match(r"^\|[\s\-:|]+\|?$", line): continue
        c = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(c) >= 7 and c[0] not in ("번호", "#"): rows.append(c)
    return rows


def nums(s): return {int(x) for x in re.findall(r"\d+", s)}


OWN = rows_of(F2 / "통합" / "변경목록.md")
md = [f"# {int(NN)}회차 이론 대본 최종 점검 — 전과 후", "",
      "지운 말은 ~~취소선~~, 넣은 말은 **굵게**. `>` 줄은 낭독하지 않는 제작 표시. 아직 저장소에 반영하지 않은 제안이다.", ""]
if (F2 / "통합" / "요약.md").exists(): md += [(F2 / "통합" / "요약.md").read_text("utf-8"), ""]
if (F2 / "통합" / "덱_정리.md").exists(): md += [(F2 / "통합" / "덱_정리.md").read_text("utf-8").replace("# ", "## ", 1), ""]

jobs = []
for course in ("통합반", "실전반"):
    for f in sorted((ROOT / f"산출물/{course}/이론/{NN}회차/대본").glob("*.md")):
        jobs.append((course, f, F2 / "proposed" / course / f.name, AGENTS.get((course, f.name[:2]))))
x3 = F2 / "proposed" / "통합반_03회차"
if NN == "02" and x3.exists():
    for f in sorted(x3.glob("*.md")):
        jobs.append(("통합반 3회차(같은 문장 맞춤)", ROOT / "산출물/통합반/이론/03회차/대본" / f.name, f, None))

md.append("# 대본 전 · 후")
for course, src, prop, k in jobs:
    old, new = src.read_text("utf-8"), prop.read_text("utf-8")
    so, sn = {l: (t, b) for l, t, b in sections(old)}, {l: (t, b) for l, t, b in sections(new)}
    shared = set()
    tsrc = ROOT / f"산출물/통합반/이론/{NN}회차/대본" / src.name
    if course == "실전반" and tsrc.exists():
        to = {l: b for l, _, b in sections(tsrc.read_text("utf-8"))}
        shared = {l for l in so if l in to and so[l][1] == to[l]}
    rows = [r for r in rows_of(F2 / k / "변경목록.md")
            if ("실전반" in r[1]) == (course == "실전반" or (k == "D" and "통합반" not in r[1]))] if k else []
    rows += [r for r in OWN if r[1].endswith(src.name) and (course.startswith("통합반 3회차") == r[1].startswith("통합반_03회차"))
             and (course == "실전반") == r[1].startswith("실전반/")]
    changed = [l for l in so if so[l][1] != sn.get(l, ("", ""))[1]]
    h_old, h_new = old.split("## [SLIDE", 1)[0], new.split("## [SLIDE", 1)[0]
    if not changed and h_old == h_new: continue
    md += ["", f"## {course} · {src.stem}", ""]
    same = [l for l in changed if l in shared]
    if same: md.append(f"_통합반과 같은 장 {len(same)}곳({', '.join(same)})은 통합반과 똑같이 바뀐다 — 여기서는 생략._\n")
    if h_old != h_new:
        md += ["### 머리(제작 표시)", "", inline(h_old.strip(), h_new.strip()), ""]
    for l in [x for x in changed if x not in shared]:
        rng = set(range(int(l.split("~")[0]), int(l.split("~")[-1]) + 1))
        why = [r for r in rows if nums(r[2]) & rng]
        md += [f"### SLIDE {l} — {so[l][0]}", ""]
        md += [f"- {r[3]}: {r[6]}" for r in why] + ([""] if why else [])
        md += [inline(so[l][1], sn[l][1]), ""]
OUT.write_text("\n".join(md) + "\n", "utf-8")
print(OUT, sum(1 for x in md if x.startswith("### SLIDE")), "장")
