"""과정 사이 같은 문단 대응표: 대상 파일의 장마다, 다른 파일들의 어느 장과 문단이 같은지."""
import re, sys
from pathlib import Path
R = Path("/Users/uengine/agent-provider/안치윤/hyd-develop/산출물")
def slides(f):
    out, cur = {}, None
    for ln in f.read_text("utf-8").split("\n"):
        m = re.match(r"## \[SLIDE ([0-9~]+)\]", ln)
        if m: cur = m.group(1); out[cur] = []; continue
        if cur is None or not ln.strip() or ln.startswith((">", "#", "---", "|")): continue
        out[cur].append(ln.strip())
    return out
def files(globs): return [f for g in globs for f in sorted(R.glob(g))]
targets = files(sys.argv[1].split(","))
pool = files(sys.argv[2].split(","))
idx = {}
for f in pool:
    for s, ps in slides(f).items():
        for p in ps: idx.setdefault(p, []).append(f"{f.parent.parent.parent.name[:1]}{f.parent.parent.name[:2]}/{f.name[:2]}:{s}")
for f in targets:
    print(f"\n## {f.relative_to(R)}")
    for s, ps in slides(f).items():
        hits = {}
        for p in ps:
            for h in idx.get(p, []): hits[h] = hits.get(h, 0) + 1
        best = sorted(hits.items(), key=lambda x: -x[1])[:2]
        print(f"{s}: {len(ps)}문단, 같음 " + (", ".join(f"{h}={n}" for h, n in best) if best else "-"))
