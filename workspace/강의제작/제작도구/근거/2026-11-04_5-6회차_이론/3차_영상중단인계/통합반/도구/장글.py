"""장 그림의 글줄(PDF 글자 층)과 칸(PPTX 도형)을 1920×1080 영상 좌표로 찍는다 — 강조 좌표를 고르는 재료.
    python3 장글.py <과정_NN일차> <장 번호 …>        예: 통합반_05일차 5 6 7
L번호 = 글줄 [x1 y1 x2 y2] 글, S번호 = 그림이 아닌 도형(칸 · 카드) [x1 y1 x2 y2] 안의 글. 함수 lines() · shapes()는 강조만들기.py가 쓴다."""
import re, subprocess, sys, html
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
SL = ROOT / "workspace/강의제작/제작도구/기존제작/tools/video/슬라이드"
PPTX = {"통합반_05일차": "workspace/강의제작/산출물/통합반/이론/05회차/통합반_05일차.pptx",
        "통합반_06일차": "workspace/강의제작/산출물/통합반/이론/06회차/통합반_06일차.pptx"}
_cache = {}

def lines(deck, n):
    k = (deck, n)
    if k in _cache: return _cache[k]
    x = subprocess.run(["pdftotext", "-f", str(n), "-l", str(n), "-bbox-layout", str(SL / deck / f"{deck}.pdf"), "-"], capture_output=True, text=True).stdout
    pw = float(re.search(r'<page width="([\d.]+)"', x)[1]); f = 1920 / pw
    out = []
    for m in re.finditer(r"<line ([^>]*)>(.*?)</line>", x, re.S):
        words = [(tuple(float(v) * f for v in re.findall(r'"([\d.]+)"', w[1])), html.unescape(w[2])) for w in re.finditer(r"<word ([^>]*)>(.*?)</word>", m[2])]
        b = [round(float(v) * f) for v in re.findall(r'"([\d.]+)"', m[1])]
        out.append({"상자": b, "글": " ".join(t for _, t in words), "낱말": words})
    _cache[k] = out
    return out

def shapes(deck, n):
    from pptx import Presentation
    p = Presentation(str(ROOT / PPTX[deck])); W, H = p.slide_width, p.slide_height; out = []
    def walk(ss, ox=0, oy=0):
        for s in ss:
            if s.shape_type == 6: walk(s.shapes); continue
            if s.shape_type not in (1,) or not s.width or not s.height: continue
            b = [round(s.left * 1920 / W), round(s.top * 1080 / H), round((s.left + s.width) * 1920 / W), round((s.top + s.height) * 1080 / H)]
            if b[2] - b[0] < 20 or b[3] - b[1] < 20: continue   # 선 · 띠 장식
            out.append({"상자": b, "글": s.text_frame.text.replace("\n", " / ") if s.has_text_frame else ""})
    walk(p.slides[n - 1].shapes)
    return out

def find(deck, n, phrase, nth=1):
    """글줄 안에서 phrase(띄어쓰기 무시)가 걸친 낱말들의 상자. 여러 번 나오면 nth번째."""
    key = re.sub(r"\s+", "", phrase); hits = []
    for L in lines(deck, n):
        ws = L["낱말"]; joined = "".join(t for _, t in ws)
        st = 0
        while True:
            i = joined.find(key, st)
            if i < 0: break
            pos, sel = 0, []
            for b, t in ws:
                if pos + len(t) > i and pos < i + len(key): sel.append(b)
                pos += len(t)
            hits.append([round(min(b[0] for b in sel)), round(min(b[1] for b in sel)), round(max(b[2] for b in sel)), round(max(b[3] for b in sel))])
            st = i + 1
    if len(hits) < nth: sys.exit(f"{deck} {n}장: 「{phrase}」를 글줄에서 찾지 못함({len(hits)}곳)")
    return hits[nth - 1], len(hits)

if __name__ == "__main__":
    deck = sys.argv[1]
    for n in map(int, sys.argv[2:]):
        print(f"== {n}장")
        for i, s in enumerate(shapes(deck, n)): print(f" S{i} {s['상자']} {s['글'][:70]}")
        for i, L in enumerate(lines(deck, n)): print(f" L{i} {L['상자']} {L['글'][:90]}")
