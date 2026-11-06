"""렌더 PDF에서 같은 글상자의 마지막 줄이 낱말 하나뿐인 곳의 후보를 찾는다(판정은 렌더를 눈으로 본다). 읽기만 한다.
언제: 덱을 렌더한 뒤, 화면 검토 전에 「낱말 하나만 떨어진 줄」 후보를 모을 때.
명령: <py> workspace/강의제작/제작도구/검사/낱말줄찾기.py <렌더 폴더(PDF가 든)>
"""
import sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import fitz  # noqa: E402

if len(sys.argv) != 2:
    sys.exit(__doc__)
doc = fitz.open(next(Path(sys.argv[1]).glob("*.pdf")))


def text(l):
    return "".join(s["text"] for s in l["spans"]).strip()


for n, page in enumerate(doc, 1):
    # 가운데 정렬 글은 줄마다 다른 블록으로 나오므로, 블록을 가리지 않고 쪽의 모든 줄을 위치로 잇는다
    ls = [l for b in page.get_text("dict")["blocks"] for l in b.get("lines", []) if text(l)]

    def above(l):  # 바로 위에서 같은 크기 · 가로가 겹치는 줄
        size = l["spans"][0]["size"]
        c = [m for m in ls if m is not l and abs(m["spans"][0]["size"] - size) < .6
             and 0 < l["bbox"][1] - m["bbox"][1] < size * 1.7
             and m["bbox"][0] < l["bbox"][2] and l["bbox"][0] < m["bbox"][2]]
        return max(c, key=lambda m: m["bbox"][1]) if c else None

    for l in ls:
        t, prev = text(l), above(l)
        if prev is None or len(t.split()) != 1:
            continue
        if any(above(m) is l for m in ls):  # 아래에 같은 글의 줄이 더 있으면 마지막 줄이 아니다
            continue
        p = text(prev)
        if len(p) >= 8 or p.startswith("•"):
            print(n, "|", p[:48], "/", t)
