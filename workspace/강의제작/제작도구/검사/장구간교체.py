"""언제: 확정 덱의 한 구간(편)을 장 수가 다른 새 장들로 바꿀 때 — 덱 원고의 그 구간을 초안의 장으로 바꾸고 뒤 장 번호를 당기거나 민다. 대본 [SLIDE] 머리와 구성.json 장 번호도 옮긴다(구성의 행 범위는 실행 뒤 눈으로 확인한다).
명령: <py> workspace/강의제작/제작도구/검사/장구간교체.py <덱.md> <초안.md 또는 -> <a> <b> --대본 <대본 …> --구성 <구성.json>
"""
import argparse, json, re
from pathlib import Path
H = re.compile(r"^## SLIDE (\d+) — ", re.M)
ap = argparse.ArgumentParser(); ap.add_argument("deck"); ap.add_argument("draft"); ap.add_argument("a", type=int); ap.add_argument("b", type=int)
ap.add_argument("--대본", nargs="*", default=[]); ap.add_argument("--구성")
o = ap.parse_args()
def blocks(text):
    ms = list(H.finditer(text)); head = text[:ms[0].start()] if ms else text
    return head, [(int(m.group(1)), text[m.start():(ms[i + 1].start() if i + 1 < len(ms) else len(text))]) for i, m in enumerate(ms)]
deck = Path(o.deck).read_text(encoding="utf-8"); head, bl = blocks(deck)
new = [] if o.draft == "-" else blocks(Path(o.draft).read_text(encoding="utf-8"))[1]
before = [t for n, t in bl if n < o.a]; after = [(n, t) for n, t in bl if n > o.b]
delta = len(new) - (o.b - o.a + 1)
out, k = [], o.a
for _, t in new: out.append(H.sub(f"## SLIDE {k:02d} — ", t, count=1)); k += 1
for n, t in after: out.append(H.sub(f"## SLIDE {n + delta:02d} — ", t, count=1))
res = head + "".join(before) + "".join(out)
if not res.endswith("\n"): res += "\n"
Path(o.deck).write_text(res, encoding="utf-8")
print(f"덱: {o.a}~{o.b}({o.b - o.a + 1}장) → {len(new)}장, 뒤 장 {delta:+d}, 전체 {len(before) + len(out)}장")
def sh(n): return n + delta if n > o.b else n
for f in o.대본:
    p = Path(f); s = p.read_text(encoding="utf-8")
    s2 = re.sub(r"\[SLIDE (\d+)(~(\d+))?\]", lambda m: f"[SLIDE {sh(int(m.group(1))):02d}" + (f"~{sh(int(m.group(3))):02d}" if m.group(3) else "") + "]", s)
    p.write_text(s2, encoding="utf-8"); print("대본 옮김:", p.name)
if o.구성:
    p = Path(o.구성); j = json.loads(p.read_text(encoding="utf-8"))
    j["slide_count"] = j["slide_count"] + delta
    for u in j["units"]:
        if "slides" in u: u["slides"] = [sh(x) if x != o.b else x + delta for x in u["slides"]] if False else [u["slides"][0] if u["slides"][0] <= o.b else sh(u["slides"][0]), sh(u["slides"][1]) if u["slides"][1] > o.b else u["slides"][1] + (delta if u["slides"][0] <= o.a <= u["slides"][1] else 0)]
    for r in j["rows"]:
        a, b = r["slides"]
        r["slides"] = [sh(a) if a > o.b else a, (b + delta) if (a <= o.a and b >= o.b) else sh(b)]
    p.write_text(json.dumps(j, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print("구성 옮김, slide_count", j["slide_count"])
