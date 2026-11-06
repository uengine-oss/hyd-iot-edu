"""렌더 PDF에서 같은 글상자의 마지막 줄이 낱말 하나뿐인 곳의 후보를 찾는다(판정은 렌더를 눈으로 본다). 읽기만 한다.
언제: 덱을 렌더한 뒤, 화면 검토 전에 「낱말 하나만 떨어진 줄」 후보를 모을 때. 이 도구를 고치면 --자가시험을 돌린다.
명령: <py> workspace/강의제작/제작도구/검사/낱말줄찾기.py <렌더 폴더(PDF가 든)> · --자가시험
"""
import sys, tempfile, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import fitz  # noqa: E402


def text(l):
    return "".join(s["text"] for s in l["spans"]).strip()


def candidates(pdf):
    """[(쪽, 윗줄, 떨어진 낱말)]"""
    out = []
    for n, page in enumerate(fitz.open(pdf), 1):
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
                out.append((n, p, t))
    return out


def selftest():
    """가운데 정렬 두 줄(블록이 갈림) · 왼쪽 정렬 글상자 · 낱말 둘인 끝줄 · 글자 크기가 다른 아래 줄을 그린 PDF로 후보가 정확히 나오는지 본다."""
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "시험.pdf"
        doc = fitz.open()
        page = doc.new_page(width=720, height=405)
        w = 400
        for y, s in ((60, "Centered headline text goes here"), (82, "alone")):         # 1쪽 후보: 가운데 정렬 끝줄 낱말 하나
            x = (720 - fitz.get_text_length(s, fontsize=16)) / 2
            page.insert_text((x, y), s, fontsize=16)
        page.insert_textbox(fitz.Rect(40, 150, 40 + w, 260), "Left aligned box line that wraps\nword", fontsize=16)   # 한 블록 안 끝줄 낱말 하나
        for y, s in ((300, "This box line is followed by"), (322, "two words")):         # 끝줄이 두 낱말 — 후보 아님
            page.insert_text((40, y), s, fontsize=16)
        page.insert_text((400, 300), "A title line in large font", fontsize=16)
        page.insert_text((400, 318), "caption", fontsize=10)                              # 크기가 달라 같은 글이 아님 — 후보 아님
        doc.save(pdf)
        if len(sys.argv) > 2:   # --자가시험 <폴더>: 시험 PDF를 남겨 옛 판 도구와 견줄 때
            doc.save(Path(sys.argv[2]) / "시험.pdf")
        got = candidates(pdf)
    words = sorted(t for _, _, t in got)
    cases = [("가운데 정렬 끝줄 낱말 하나를 잡는다(블록이 줄마다 갈려도)", "alone" in words, got),
             ("왼쪽 정렬 글상자 끝줄 낱말 하나를 잡는다", "word" in words, got),
             ("끝줄이 두 낱말이면 후보가 아니다", "two" not in " ".join(words), got),
             ("글자 크기가 다른 아래 줄은 같은 글로 잇지 않는다", "caption" not in words, got)]
    for name, ok, detail in cases:
        print(f"{'통과' if ok else '실패'}: {name}" + ("" if ok else f" — {detail}"))
    bad = sum(not c[1] for c in cases)
    print(f"자가시험 {len(cases)}건 · 실패 {bad}")
    return bad == 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["--자가시험"]:
        sys.exit(0 if selftest() else 1)
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for n, p, t in candidates(next(Path(sys.argv[1]).glob("*.pdf"))):
        print(n, "|", p[:48], "/", t)
