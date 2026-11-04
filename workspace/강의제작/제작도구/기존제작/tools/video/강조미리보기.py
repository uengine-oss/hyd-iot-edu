"""강조 설정을 장 그림 위에 다 그린 모습(그리기가 끝난 순간)으로 미리 본다 — 강조표시.py의 그리기 함수를 그대로 쓴다.
언제: 강조 설정을 쓰거나 고친 뒤, 영상을 굽기 전. 영상 없이 좌표 · 모양을 본다(비용 0).
명령: <py> workspace/강의제작/제작도구/기존제작/tools/video/강조미리보기.py <장그림 폴더(s-NN.png)> <강조.json> <출력 폴더> [--장 5,8]

- 장마다 그 장의 모든 표시를 번호(설정 순서, 1부터)와 함께 그린 `s-NN.png`를 출력 폴더에 쓴다. 영상과 같은 1920×1080으로 줄여 그린다.
- 좌표 · 필수 칸 검사는 하지 않는다(그건 강조표시.py가 영상에서 한다). 모르는 모양이면 멈춘다.
"""
import importlib.util, json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("emph", Path(__file__).resolve().parent / "강조표시.py")
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)

src, cfg, out = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), Path(sys.argv[3])
only = None
if "--장" in sys.argv: only = {int(x) for x in sys.argv[sys.argv.index("--장") + 1].split(",")}
out.mkdir(parents=True, exist_ok=True)
by = {}
for i, m in enumerate(cfg["표시"], 1):
    if m["모양"] not in E.SHAPES: sys.exit(f"표시 {i}: 모르는 모양 {m['모양']}")
    by.setdefault(int(m["장"]), []).append(dict(m, seed=i))
try: font = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
except OSError: font = None
for s, ms in sorted(by.items()):
    if only and s not in only: continue
    base = Image.open(src / f"s-{s:02d}.png").convert("RGBA").resize((E.W, E.H), Image.LANCZOS)
    layer = Image.new("RGBA", (E.W * E.SS, E.H * E.SS), (0, 0, 0, 0))
    for m in ms:
        m["_path"] = E.path(m)
        if m["모양"] == "글씨" and not E.FONT.exists(): continue
        E.draw_mark(layer, m, 1.0, 255)
    img = Image.alpha_composite(base, layer.resize((E.W, E.H), Image.LANCZOS))
    d = ImageDraw.Draw(img)
    for m in ms:   # 번호: 표시의 왼쪽 위
        x, y = (m.get("상자") or m.get("시작") or [m["중심"][0] - m.get("반지름", [0, 0])[0], m["중심"][1] - m.get("반지름", [0, 0])[1]])[:2]
        d.text((max(0, x - 8), max(0, y - 34)), str(m["seed"]), fill=(0, 90, 200, 255), font=font)
    img.convert("RGB").save(out / f"s-{s:02d}.png")
print(f"{len(by) if not only else len(only & set(by))}장 그림 → {out}")
