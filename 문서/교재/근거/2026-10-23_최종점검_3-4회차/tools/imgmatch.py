"""대상 덱의 장마다 후보 덱들에서 가장 비슷한 장 그림을 찾는다(전체 해상도 픽셀 차이)."""
import sys
from pathlib import Path
from PIL import Image, ImageChops
C = Path(sys.argv[1]); tgt = sys.argv[2]; cands = sys.argv[3].split(",")
def load(p, size=(160, 90)): return Image.open(p).convert("L").resize(size)
def num(p): return int(p.stem.split("-")[1])
pool = [(d, num(p), p, load(p)) for d in cands for p in (C / d).glob("s-*.png")]
for p in sorted((C / tgt).glob("s-*.png"), key=num):
    a = load(p)
    best = min(pool, key=lambda x: sum(ImageChops.difference(a, x[3]).getdata()))
    full = ImageChops.difference(Image.open(p).convert("L"), Image.open(best[2]).convert("L").resize(Image.open(p).size))
    px = sum(1 for v in full.getdata() if v > 40)
    print(f"{num(p)}\t{best[0]}:{best[1]}\t다른픽셀 {px}")
