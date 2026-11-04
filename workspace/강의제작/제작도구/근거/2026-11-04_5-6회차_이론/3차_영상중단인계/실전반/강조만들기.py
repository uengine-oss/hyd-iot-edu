"""실전반 5 · 6회차 강조 설정을 만든다(좌표는 덱에서 재고, 문장은 자막 문장 그대로 찾는다). 저장소 루트에서:
    python3 작업/2026-11-04_5-6회차-렌더-음성/영상/실전반/강조만들기.py
- 표시 하나 = (편, 장, 문장 조각, 낱말, 끝문장 조각 또는 None, 모양, 좌표 식, 대상). 조각은 그 장 자막 문장 하나에만 맞아야 한다(둘 이상이면 멈춤).
- 좌표 식: L("글") 그 글이 든 글줄 상자, W("글") 그 글을 덮는 낱말 상자, S("글") 그 글로 시작하는 도형 상자, U(a, b) 두 상자를 합친 상자,
  C(상자) 동그라미(상자 둘레), A(시작, 끝) 화살표. 상자 좌표는 1920×1080 프레임.
- 출력: workspace/강의제작/제작도구/구성/실전반/<NN>회차/강조_<영상 이름>.json
"""
import html, json, re, subprocess, zipfile
from pathlib import Path
ROOT = Path("/home/user/hyd-iot-edu")
V = ROOT / "workspace/강의제작/제작도구/기존제작/tools/video"
K = 1920 / 12191695
norm = lambda s: re.sub(r"\s+", "", s)

# ---- 덱 좌표
_cache = {}
def deck(n):
    if n in _cache: return _cache[n]
    pptx = ROOT / f"workspace/강의제작/산출물/실전반/이론/{n}회차/실전반_{n}일차.pptx"
    pdf = V / f"슬라이드/실전반_{n}일차/실전반_{n}일차.pdf"
    _cache[n] = (zipfile.ZipFile(pptx), pdf, {})
    return _cache[n]

def page(n, s):
    z, pdf, pages = deck(n)
    if s not in pages:
        out = subprocess.run(["pdftotext", "-f", str(s), "-l", str(s), "-bbox-layout", str(pdf), "-"], capture_output=True, text=True).stdout
        lines = []
        for attrs, body in re.findall(r"<line (.*?)>(.*?)</line>", out, re.S):
            ws = [([float(v) * 2 for v in re.findall(r'"([\d.]+)"', a)], html.unescape(t)) for a, t in re.findall(r"<word (.*?)>([^<]*)</word>", body)]
            lines.append(ws)
        x = z.read(f"ppt/slides/slide{s}.xml").decode(); shapes = []
        for sp in re.findall(r"<p:(?:sp|cxnSp|pic)>.*?</p:(?:sp|cxnSp|pic)>", x, re.S):
            m = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"/><a:ext cx="(\d+)" cy="(\d+)"/>', sp)
            if not m: continue
            a, b, w, h = map(int, m.groups())
            t = " / ".join(html.unescape("".join(re.findall(r"<a:t>(.*?)</a:t>", p))) for p in re.findall(r"<a:p>.*?</a:p>", sp, re.S)).strip(" /")
            geo = (re.search(r'prst="(\w+)"', sp) or [None, "?"])[1]
            shapes.append(([a * K, b * K, (a + w) * K, (b + h) * K], t, geo))
        pages[s] = (lines, shapes)
    return pages[s]

CUR = {}
def _span(text):
    lines, _ = page(CUR["n"], CUR["s"]); hits = []
    for ws in lines:
        joined = "".join(t for _, t in ws)
        i = joined.find(norm(text))
        if i < 0: continue
        pos, sel = 0, []
        for box, t in ws:
            if pos + len(t) > i and pos < i + len(norm(text)): sel.append(box)
            pos += len(t)
        hits.append((ws, sel))
    if len(hits) != 1: raise SystemExit(f"장 {CUR['s']}: 글 「{text}」 글줄 {len(hits)}곳")
    return hits[0]

def L(text, px=8, py=0):
    ws, _ = _span(text); b = [min(w[0][0] for w in ws), min(w[0][1] for w in ws), max(w[0][2] for w in ws), max(w[0][3] for w in ws)]
    return [round(b[0] - px), round(b[1] - py), round(b[2] + px), round(b[3] + py)]

def W(text, px=2, py=0):
    _, sel = _span(text)
    return [round(min(b[0] for b in sel) - px), round(min(b[1] for b in sel) - py), round(max(b[2] for b in sel) + px), round(max(b[3] for b in sel) + py)]

def S(text, pad=0, nth=0):
    _, shapes = page(CUR["n"], CUR["s"])
    hits = [b for b, t, g in shapes if t.startswith(text)]
    if len(hits) <= nth: raise SystemExit(f"장 {CUR['s']}: 도형 「{text}」 없음")
    b = hits[nth]
    return [round(b[0] - pad), round(b[1] - pad), round(b[2] + pad), round(b[3] + pad)]

def R(text, py=2):
    """그 글이 든 표 행의 바탕(글 없는 넓은 둥근 사각형) 상자."""
    ws, _ = _span(text); cy = (min(w[0][1] for w in ws) + max(w[0][3] for w in ws)) / 2
    _, shapes = page(CUR["n"], CUR["s"])
    rows = [b for b, t, g in shapes if g == "roundRect" and not t and b[2] - b[0] > 1000 and b[1] <= cy <= b[3]]
    if not rows: raise SystemExit(f"장 {CUR['s']}: 「{text}」의 행 바탕 없음")
    b = min(rows, key=lambda b: b[3] - b[1])
    return [round(b[0]), round(b[1] + py), round(b[2]), round(b[3] - py)]

def U(*bs): return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
def P(b, px, py=None): py = px if py is None else py; return [b[0] - px, b[1] - py, b[2] + px, b[3] + py]

# ---- 자막 문장
def sentences(script):
    import sys; sys.argv = ["x", "_", "_"]
    import importlib.util
    spec = importlib.util.spec_from_file_location("lv", V / "강의영상.py"); M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
    files = [json.loads(f.read_text(encoding="utf-8"))["문장"] for f in (V / "쉼_저장").glob("*.json")]
    out = {}
    for a, b, t in M.slides_text(script):
        nt = norm(t); cand = [S for S in files if all(norm(x) in nt for x in S) and len("".join(map(norm, S))) == len(nt)]
        out[a] = cand[0] if cand else [t.strip()]
    return out

def find(sents, piece, where):
    hit = [x for x in sents if norm(piece) in norm(x)]
    if len(hit) != 1: raise SystemExit(f"{where}: 문장 조각 「{piece}」 {len(hit)}곳")
    return hit[0]

def build(n, part, marks):
    script = sorted((ROOT / f"workspace/강의제작/산출물/실전반/이론/{n}회차/대본").glob(f"{part}_*.md"))[0]
    name = f"실전반_{n}회차_{script.stem}"
    sents = sentences(script); out = []
    for s, sen, word, end, shape, geo, what in marks:
        CUR.update(n=n, s=s)
        first = max(k for k in sents if k <= s)
        S_ = sents[first]; full = find(S_, sen, f"{name} 장 {s}")
        if norm(word) not in norm(full): raise SystemExit(f"{name} 장 {s}: 낱말 「{word}」이 문장에 없다")
        m = {"장": s, "문장": full, "낱말": word}
        if end:
            e = find(S_, end, f"{name} 장 {s} 끝문장")
            if S_.index(e) <= S_.index(full): raise SystemExit(f"{name} 장 {s}: 끝문장이 문장보다 앞")
            m["끝문장"] = e
        m["모양"] = shape
        g = geo() if callable(geo) else geo
        if shape == "동그라미": m["중심"] = [round((g[0] + g[2]) / 2), round((g[1] + g[3]) / 2)]; m["반지름"] = [round((g[2] - g[0]) / 2), round((g[3] - g[1]) / 2)]
        elif shape == "화살표": m["시작"], m["끝"] = g
        else: m["상자"] = g
        m["대상"] = what; out.append(m)
    # 같은 때 셋 이상 금지 검사(문장 차례로)
    for s in {m["장"] for m in out}:
        first = max(k for k in sents if k <= s); S_ = sents[first]
        iv = [(S_.index(m["문장"]), S_.index(m["끝문장"]) if "끝문장" in m else len(S_)) for m in out if m["장"] == s]
        for i in range(len(S_)):
            if sum(a <= i < b for a, b in iv) > 2: raise SystemExit(f"{name} 장 {s}: 문장 {i}에서 셋 이상")
    f = ROOT / f"workspace/강의제작/제작도구/구성/실전반/{n}회차/강조_{name}.json"
    f.write_text(json.dumps({"표시": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{f.name}: {len(out)}개")

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    import 강조만들기 as M
    from 강조계획 import PLAN
    only = sys.argv[1:]
    for (n, part), marks in PLAN.items():
        if not only or f"{n}_{part}" in only: M.build(n, part, marks)
