"""온라인 덱의 장마다 유형 · 레이아웃 · 메시지 · 그림 · 대본 어림 낭독 시간을 JSON으로 내고, 대본이 덮지 못한 장 · 2분 넘는 장 · 유형 분포를 찍는다.
언제: 덱 재편 전후, 장별 점검 · 시간 배분을 판단할 때. 읽기만 하고 음성을 부르지 않는다.
명령: <py> workspace/강의제작/제작도구/검사/덱측정.py <출력.json> <덱키 …(통합3 실전4)>
"""
import json, re, sys
from pathlib import Path

W = Path(__file__).resolve().parents[2]   # workspace/강의제작
sys.dont_write_bytecode = True
sys.path.insert(0, str(W / "제작도구/촬영"))
from 시간계산 import load_coef, script_slides, slide_seconds  # noqa: E402

COURSE = {"통합": ("통합반", "integrated"), "실전": ("실전반", "practical")}
if len(sys.argv) < 3:
    sys.exit(__doc__)
k = load_coef(); out = {}
for name in sys.argv[2:]:
    m = re.fullmatch(r"(통합|실전)(\d+)", name)
    if not m:
        sys.exit(f"{name}: 덱키는 통합3 · 실전10 꼴이다")
    c, dk = COURSE[m[1]]; nn = f"{int(m[2]):02d}"
    md, sd = W / f"제작도구/온라인/decks/{dk}/day{nn}/{c}_{nn}일차.md", W / f"산출물/{c}/이론/{nn}회차/대본"
    parts = re.split(r"(?m)^## SLIDE (\d+) — (.*)$", md.read_text(encoding="utf-8"))
    slides = {}
    for i in range(1, len(parts), 3):
        n = int(parts[i]); title = parts[i + 1].strip(); body = parts[i + 2]
        ty = re.search(r"(?m)^- 유형:\s*(.+)$", body); lay = re.search(r"(?m)^레이아웃:\s*(.+)$", body); msg = re.search(r"(?m)^- 메시지:\s*(.+)$", body); fig = re.search(r"(?m)^- 그림:\s*(.+)$", body)
        slides[n] = dict(title=title, type=ty.group(1).strip() if ty else "", layout=lay.group(1).strip() if lay else "", msg=msg.group(1).strip() if msg else "", fig=fig.group(1).strip() if fig else "", sec=None, file="")
    cover = set()
    for f in sorted(sd.glob("*.md")):
        for n, (text, share, title) in script_slides(f.read_text(encoding="utf-8")).items():
            s = slide_seconds(text, k) / share if share > 1 else slide_seconds(text, k)
            if n in slides:
                slides[n]["sec"] = round(s, 1); slides[n]["file"] = f.name[:2]
            cover.add(n)
    out[name] = slides
    miss = [n for n in slides if n not in cover]; extra = [n for n in cover if n not in slides]
    tot = sum(v["sec"] or 0 for v in slides.values())
    print(name, len(slides), "장", round(tot / 60, 1), "분 대본미덮음", miss, "덱에없음", extra)
    print("  2분초과", [(n, v["sec"]) for n, v in slides.items() if (v["sec"] or 0) >= 120])
    print("  유형분포", {ty: sum(1 for v in slides.values() if v["type"] == ty) for ty in sorted({v["type"] for v in slides.values()})})
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
