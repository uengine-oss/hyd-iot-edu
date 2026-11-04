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
for n, page in enumerate(doc, 1):
    for b in page.get_text("dict")["blocks"]:
        ls = [l for l in b.get("lines", []) if "".join(s["text"] for s in l["spans"]).strip()]
        if len(ls) < 2:
            continue
        for k in range(1, len(ls)):
            t = "".join(s["text"] for s in ls[k]["spans"]).strip()
            prev = "".join(s["text"] for s in ls[k - 1]["spans"]).strip()
            size = ls[k]["spans"][0]["size"]
            same_size = abs(size - ls[k - 1]["spans"][0]["size"]) < .6
            near = 0 < ls[k]["bbox"][1] - ls[k - 1]["bbox"][1] < size * 1.7
            last = k == len(ls) - 1 or abs(ls[k + 1]["bbox"][1] - ls[k]["bbox"][1]) > size * 1.7
            if same_size and near and last and len(t.split()) == 1 and (len(prev) >= 8 or prev.startswith("•")):
                print(n, "|", prev[:48], "/", t)
