"""쉼_제안.json의 파일마다 문장과 그 사이 초안 값을 찍는다(초안: 문단 사이 · 물음 뒤 2, 「다음 시간에는」 앞 3, 나머지 1).
   python3 쉼보기.py <편 키> → scratchpad/보기_<편>.txt , 초안은 scratchpad/초안.json 에 모은다
"""
import json, re, sys
from pathlib import Path
ROOT = Path("/home/user/hyd-iot-edu"); HERE = Path(__file__).parent
m = json.loads((HERE / "쉼_제안.json").read_text(encoding="utf-8"))
norm = lambda s: re.sub(r"\s+", "", s)
key = sys.argv[1]
n, part = key.split("_")
script = sorted((ROOT / f"workspace/강의제작/산출물/실전반/이론/{n}/대본").glob(f"{part}_*.md"))[0]
raw = script.read_text(encoding="utf-8")
parts = re.split(r"^## \[SLIDE ([0-9~]+)\].*$", raw, flags=re.M)
bodies = {parts[i]: re.split(r"^#{1,2} ", parts[i + 1], flags=re.M)[0] for i in range(1, len(parts), 2)}
draftf = HERE / "초안.json"
draft = json.loads(draftf.read_text(encoding="utf-8")) if draftf.exists() else {}
out = []
for name, d in sorted(m.items(), key=lambda kv: int(kv[1]["장"].split("~")[0])):
    if d["편"] != key: continue
    body = re.sub(r"^---\s*$|^>.*$|^\|.*$", "", bodies[d["장"]], flags=re.M).replace("**", "")
    flat = re.sub(r"\n\s*\n", "¶", body.strip()); flat = re.sub(r"\s+", "", flat)
    S = d["문장"]; pos = []; p = 0
    for s in S:
        j = flat.find(norm(s), p); pos.append(j); p = j + len(norm(s)) if j >= 0 else p
    v = []
    for i in range(len(S) - 1):
        gap = flat[pos[i] + len(norm(S[i])):pos[i + 1]] if pos[i] >= 0 and pos[i + 1] >= 0 else ""
        if d["쉼"][i] is not None: x = d["쉼"][i]
        elif S[i + 1].startswith("다음 시간에는"): x = 3
        elif re.match(r"(답은|정답은) .{0,8}(번|입니다)", S[i + 1]) and not S[i].startswith(("답은", "정답은")): x = 3
        elif "¶" in gap or S[i].rstrip("’”」").endswith("?") or (re.search(r"(까요|는가|을까|일까|할까|될까|볼까)\.$", S[i]) and not S[i].endswith("니까요.")): x = 2
        elif re.search(r"(니까요|거든요)\.$", S[i + 1]) and len(S[i + 1]) < 45: x = 0
        else: x = 1
        v.append(x)
    draft[name] = v
    out.append(f"### {name} 장{d['장']}")
    for i, s in enumerate(S):
        out.append(f"{i:>2} {s}")
        if i < len(v): out.append(f"      ‹{v[i]}›{'¶' if '¶' in (flat[pos[i] + len(norm(S[i])):pos[i + 1]] if pos[i] >= 0 and pos[i+1] >= 0 else '') else ''}")
draftf.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
(HERE / f"보기_{key}.txt").write_text("\n".join(out), encoding="utf-8")
print(len(out), "줄")
