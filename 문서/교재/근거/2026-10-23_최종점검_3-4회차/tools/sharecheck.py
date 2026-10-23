"""두 과정이 같이 쓰던 문단이 제안본에서도 같은지 본다.
    python3 sharecheck.py <원본 A 폴더들,> <원본 B 폴더들,> <제안 A 폴더들,> <제안 B 폴더들,>
원본에서 A와 B에 똑같이 있던 문단마다, 제안본 A에서 바뀌었는데 B에 같은 새 문단이 없으면(또는 그 반대) 보고한다.
"""
import re, sys
from pathlib import Path
def paras(dirs):
    out = {}
    for d in dirs.split(","):
        for f in sorted(Path(d).glob("*.md")):
            cur = None
            for i, l in enumerate(f.read_text("utf-8").split("\n")):
                m = re.match(r"## \[SLIDE ([0-9~]+)", l)
                if m: cur = m.group(1); continue
                if cur and l.strip() and not l.startswith((">", "#", "---", "|")): out.setdefault(l.strip(), []).append(f"{f.parent.parent.name}/{f.name[:2]}:{cur}")
    return out
oa, ob, na, nb = (paras(x) for x in sys.argv[1:5])
shared = [p for p in oa if p in ob]
lost_a = [p for p in shared if p not in na]   # A에서 바뀜
lost_b = [p for p in shared if p not in nb]
for p in lost_a:
    if p in nb: print(f"A만 바뀜  {oa[p][0]} ↔ {ob[p][0]} | {p[:70]}")
for p in lost_b:
    if p in na: print(f"B만 바뀜  {oa[p][0]} ↔ {ob[p][0]} | {p[:70]}")
print(f"같이 쓰던 문단 {len(shared)} · A에서 바뀜 {len(lost_a)} · B에서 바뀜 {len(lost_b)}")
