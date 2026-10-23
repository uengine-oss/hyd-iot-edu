"""완성 영상을 일정 간격으로 끝까지 잘라 모음 그림으로 만든다 — 장면 사이의 튐 · 로딩 · 오류 창 · 엉뚱한 화면을 눈으로 찾는다.
사용: python3 scenes.py <영상.mp4> [간격 초(기본 2)] [<결과 폴더>]
문장마다 한 장면(verify.py)은 문장 사이를 못 본다. 게시 전에 이 그림을 처음부터 끝까지 모두 본다(8분 영상 2초 간격 = 12장, 27분 3초 간격 = 28장).
그림 한 장 = 20장면(5×4), 왼쪽 위에 영상 시각. 의심 구간은 ffmpeg -ss 로 0.5초 간격을 다시 뽑아 확대해 본다."""
import os, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw
from common import ffmpeg

mp4 = Path(sys.argv[1]); step = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
out = Path(sys.argv[3]) if len(sys.argv) > 3 else mp4.parent / (mp4.stem + '_장면')
out.mkdir(parents=True, exist_ok=True)
tmp = out / '_f'; tmp.mkdir(exist_ok=True)
subprocess.run([ffmpeg(), '-v', 'error', '-y', '-i', str(mp4), '-vf', f'fps=1/{step},scale=384:216', str(tmp / 'f_%04d.jpg')], check=True)
fs = sorted(tmp.glob('f_*.jpg'))
for k in range(0, len(fs), 20):
    s = Image.new('RGB', (1920, 864), 'white'); d = ImageDraw.Draw(s)
    for j, f in enumerate(fs[k:k + 20]):
        t = (k + j) * step; x, y = (j % 5) * 384, (j // 5) * 216
        s.paste(Image.open(f), (x, y)); d.rectangle((x, y, x + 44, y + 12), fill='black'); d.text((x + 2, y), f'{int(t // 60)}:{int(t % 60):02d}', fill='yellow')
    s.save(out / f'장면_{k // 20 + 1:02d}.jpg', quality=80)
for f in fs: f.unlink()
tmp.rmdir()
print(f'{len(fs)}장면 · 그림 {(len(fs) + 19) // 20}장 · {out}')
