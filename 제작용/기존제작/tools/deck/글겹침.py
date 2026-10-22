"""덱 PDF(LibreOffice 렌더)에서 서로 다른 글상자의 글줄이 겹치는 장을 찾는다.

    python3 제작용/기존제작/tools/deck/글겹침.py <덱.pdf> [<덱.pdf> …]

PDF 추출은 가까운 글상자를 한 묶음으로 합치므로 묶음을 믿지 않고 모든 글줄 쌍을 본다. 가로로 겹치고 세로로 낮은 줄 높이의 25 % 넘게 겹치면 겹침이다(정상 줄 간격은 1 % 미만으로 닿는다).
장 밖으로 나간 글줄과, 작은 칠한 칸(배지 · 꼬리표, 높이 40pt 미만)에 걸친 글줄이 그 칸 밖으로 2pt 넘게 나간 것도 찾는다. 그림 안의 글(삽화)은 PDF에서 글이 아니므로 보지 않는다.
겹침이 하나라도 있으면 종료 코드 1이다.
"""
import sys

import pymupdf


def lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            text = "".join(s["text"] for s in ln["spans"]).strip()
            if text:
                out.append((b["number"], pymupdf.Rect(ln["bbox"]), text))
    return out


def check(pdf):
    found = []
    doc = pymupdf.open(pdf)
    for pno, page in enumerate(doc, 1):
        L = lines(page)
        for i in range(len(L)):
            _, ri, ti = L[i]
            if not page.rect.contains(ri):
                found.append((pno, f"장 밖으로 나감: {ti[:30]}"))
            for j in range(i + 1, len(L)):
                _, rj, tj = L[j]
                w = min(ri.x1, rj.x1) - max(ri.x0, rj.x0)
                h = min(ri.y1, rj.y1) - max(ri.y0, rj.y0)
                if w > 1 and h > 0.25 * min(ri.height, rj.height):
                    found.append((pno, f"「{ti[:24]}」 ↔ 「{tj[:24]}」"))
        badges = [d["rect"] for d in page.get_drawings() if d.get("fill") and d["rect"].height < 40 and d["rect"].width < 400]
        for _, r, t in L:
            for b in badges:
                inter = r & b
                if inter.is_empty or inter.get_area() < 0.3 * r.get_area():
                    continue
                if not (b + (-2, -2, 2, 2)).contains(r):
                    found.append((pno, f"칸 밖으로 나감: 「{t[:24]}」"))
    return found


bad = 0
for pdf in sys.argv[1:]:
    f = check(pdf)
    bad += len(f)
    print(f"{pdf}: 겹침 {len(f)}곳")
    for pno, msg in f:
        print(f"  {pno}장 {msg}")
sys.exit(1 if bad else 0)
