"""강조 좌표를 덱에서 잰다(1920×1080 프레임 기준). 저장소 루트에서:
    python3 강조도우미.py <05|06> <장 …>   — 장마다 도형(PPTX 상자 · 채움색 · 글)과 글줄(렌더 PDF의 줄 상자)을 찍는다
도형 좌표는 PPTX의 a:off · a:ext(EMU → ×1920/12191695), 글줄은 슬라이드 폴더의 LO 26.8 렌더 PDF를 pdftotext -bbox-layout(pt → ×2)으로 읽는다.
"""
import re, subprocess, sys, zipfile, html
from pathlib import Path
ROOT = Path("/home/user/hyd-iot-edu")
n = sys.argv[1]
pptx = ROOT / f"workspace/강의제작/산출물/실전반/이론/{n}회차/실전반_{n}일차.pptx"
pdf = ROOT / f"workspace/강의제작/제작도구/기존제작/tools/video/슬라이드/실전반_{n}일차/실전반_{n}일차.pdf"
K = 1920 / 12191695
z = zipfile.ZipFile(pptx)
for s in map(int, sys.argv[2:]):
    x = z.read(f"ppt/slides/slide{s}.xml").decode()
    print(f"=== 장 {s} 도형")
    for sp in re.findall(r"<p:(?:sp|cxnSp|pic)>.*?</p:(?:sp|cxnSp|pic)>", x, re.S):
        m = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"/><a:ext cx="(\d+)" cy="(\d+)"/>', sp)
        if not m: continue
        a, b, w, h = map(int, m.groups())
        geo = (re.search(r'prst="(\w+)"', sp) or [None, "?"])[1]
        fill = (re.search(r"<p:spPr>.*?<a:solidFill><a:srgbClr val=\"(\w+)\"", sp, re.S) or [None, ""])[1]
        t = " / ".join(html.unescape("".join(re.findall(r"<a:t>(.*?)</a:t>", p))) for p in re.findall(r"<a:p>.*?</a:p>", sp, re.S))
        t = t.strip(" /")
        if not t and w * K < 40 and h * K < 40 and geo not in ("ellipse",): continue
        print(f"  [{round(a*K)},{round(b*K)},{round((a+w)*K)},{round((b+h)*K)}] {geo} {fill} {t[:70]}")
    out = subprocess.run(["pdftotext", "-f", str(s), "-l", str(s), "-bbox-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    print(f"--- 장 {s} 글줄")
    for ln in re.findall(r"<line (.*?)>(.*?)</line>", out, re.S):
        c = [float(v) for v in re.findall(r'"([\d.]+)"', ln[0])]
        words = re.findall(r">([^<]*)</word>", ln[1])
        print(f"  [{round(c[0]*2)},{round(c[1]*2)},{round(c[2]*2)},{round(c[3]*2)}] {html.unescape(' '.join(words))}")
