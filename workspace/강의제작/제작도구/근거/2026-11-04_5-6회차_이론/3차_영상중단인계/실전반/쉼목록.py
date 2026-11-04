"""실전반 5 · 6회차 대본에 속한 빈 쉼 파일을 찾고, 옛 판의 같은 두 문장 이음 쉼을 옮긴 제안을 낸다(파일은 쓰지 않는다 — --쓰기일 때만).
   python3 쉼목록.py [--쓰기 결정.json]
출력: scratchpad/쉼_제안.json — {파일: {"편":…, "장":…, "문장":[…], "쉼":[값 또는 null]}}
"""
import json, re, sys, glob
from pathlib import Path
ROOT = Path("/home/user/hyd-iot-edu")
BDIR = ROOT / "workspace/강의제작/제작도구/기존제작/tools/video/쉼_저장"
OUT = Path(__file__).parent / "쉼_제안.json"
scripts = sorted(glob.glob(str(ROOT / "workspace/강의제작/산출물/실전반/이론/0[56]회차/대본/*.md")))
norm = lambda s: re.sub(r"\s+", "", s)
texts = {}
for s in scripts:
    t = Path(s).read_text(encoding="utf-8")
    parts = re.split(r"^## \[SLIDE ([0-9~]+)\].*$", t, flags=re.M)
    key = f"{Path(s).parent.parent.name}_{Path(s).stem[:2]}"
    for i in range(1, len(parts), 2):
        body = re.split(r"^#{1,2} ", parts[i + 1], flags=re.M)[0]
        texts[(key, parts[i])] = norm(body.replace("**", ""))

pair, full = {}, {}
mine = {}
for f in sorted(BDIR.glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8")); S = d["문장"]; v = d.get("쉼")
    if isinstance(v, list) and len(v) == len(S) - 1:
        for i in range(len(v)): pair.setdefault((norm(S[i]), norm(S[i + 1])), []).append(v[i])
        continue
    hit = [k for k, body in texts.items() if all(norm(x) in body for x in S)]
    if hit: mine[f.name] = {"편": hit[0][0], "장": hit[0][1], "문장": S}

if len(sys.argv) > 2 and sys.argv[1] == "--쓰기":
    dec = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    n = 0
    for name, v in dec.items():
        f = BDIR / name; d = json.loads(f.read_text(encoding="utf-8"))
        assert d["쉼"] is None and len(v) == len(d["문장"]) - 1 and all(x in (0, 1, 2, 3) for x in v), name
        assert sum(x == 3 for x in v) <= 2, (name, "크게 셋 이상")
        d["쉼"] = v; f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8"); n += 1
    print("쓴 파일", n); sys.exit()

moved = new = 0
for name, m in mine.items():
    S = m["문장"]; sug = []
    for i in range(len(S) - 1):
        c = pair.get((norm(S[i]), norm(S[i + 1])))
        if c: sug.append(max(set(c), key=c.count)); moved += 1
        else: sug.append(None); new += 1
    m["쉼"] = sug
OUT.write_text(json.dumps(mine, ensure_ascii=False, indent=1), encoding="utf-8")
from collections import Counter
print("내 빈 파일", len(mine), Counter(m["편"] for m in mine.values()), "옛 이음 옮김", moved, "새 자리", new)
