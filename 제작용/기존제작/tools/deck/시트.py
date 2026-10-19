"""렌더한 장 PNG를 묶음 그림으로 만든다(한눈에 보기·검토용).

사용: python 시트.py <렌더 폴더> <출력 접두어> [--cols 4] [--per 24]
  <렌더 폴더>의 `*-NN.png`(deck2pptx --render 결과)를 장 번호 순으로 --per장씩 묶어 `<출력 접두어>_1.png`, `_2.png`…로 저장한다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image

GAP = 10


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("render_dir")
    ap.add_argument("out_prefix")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--per", type=int, default=24)
    a = ap.parse_args()
    files = sorted((f for f in Path(a.render_dir).glob("*.png") if re.search(r"-\d+\.png$", f.name)),
                   key=lambda f: int(re.search(r"-(\d+)\.png$", f.name).group(1)))
    if not files:
        print(f"[실패] 장 그림이 없음: {a.render_dir}", file=sys.stderr)
        return 1
    ims = [Image.open(f) for f in files]
    w, h = ims[0].size
    out = Path(a.out_prefix)
    out.parent.mkdir(parents=True, exist_ok=True)
    for n, k in enumerate(range(0, len(ims), a.per), 1):
        grp = ims[k:k + a.per]
        rows = -(-len(grp) // a.cols)
        sheet = Image.new("RGB", (a.cols * w + (a.cols + 1) * GAP, rows * h + (rows + 1) * GAP), (120, 120, 120))
        for i, im in enumerate(grp):
            sheet.paste(im, (GAP + (i % a.cols) * (w + GAP), GAP + (i // a.cols) * (h + GAP)))
        path = out.with_name(f"{out.name}_{n}.png")
        sheet.save(path)
        print(f"{path} — {k + 1}~{k + len(grp)}장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
