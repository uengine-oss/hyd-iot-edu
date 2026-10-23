"""대본 문단마다 다른 과정의 어느 파일 · 장과 같은지 표시한 공유표를 만든다."""
import re, sys
from pathlib import Path
R = Path("/Users/uengine/agent-provider/안치윤/hyd-develop/산출물")
def slides(f):
    out, cur = [], None
    for ln in f.read_text("utf-8").split("\n"):
        m = re.match(r"## \[SLIDE ([0-9~]+)\]", ln)
        if m: cur = m.group(1); continue
        if cur and ln.strip() and not ln.startswith((">", "#", "---", "|")): out.append((cur, ln.strip()))
    return out
def tag(f): return f"{f.parents[3].name} {int(f.parents[1].name[:2])}회차 {f.name[:2]}"
targets = [f for g in sys.argv[1].split(",") for f in sorted(R.glob(g))]
pool = [f for g in sys.argv[2].split(",") for f in sorted(R.glob(g))]
idx = {}
for f in pool:
    for s, p in slides(f): idx.setdefault(p, []).append(f"{tag(f)} SLIDE {s}")
for f in targets:
    print(f"\n## {f.relative_to(R)}\n")
    last = None
    for s, p in slides(f):
        if s != last: print(f"\n### SLIDE {s}"); last = s
        hit = idx.get(p)
        print(f"- [{'같음: ' + '; '.join(hit) if hit else '이 파일에만'}] {p[:70]}…")
