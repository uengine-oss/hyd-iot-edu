"""고친 자리 앞뒤만 본다. 사용: python 앞뒤보기.py <영상.mp4> <초> [앞뒤 초, 기본 3]
그 시각 앞뒤를 0.5초 간격으로 뽑아 <영상>_앞뒤_<초>.jpg 한 장으로 남긴다. 이어짐은 이 그림을 눈으로 판정한다. 확정된 구간은 다시 보지 않는다."""
import subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw
from common import ffmpeg
sys.stdout.reconfigure(encoding='utf-8')
ff, mp4, at = ffmpeg(), Path(sys.argv[1]), float(sys.argv[2])
span = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
times = [at + i * 0.5 for i in range(int(-span * 2), int(span * 2) + 1)]
cols, w, h = 4, 480, 270
sheet = Image.new('RGB', (cols * w, ((len(times) + cols - 1) // cols) * h), 'white')
draw = ImageDraw.Draw(sheet)
for k, t in enumerate(times):
    raw = subprocess.check_output([ff, '-v', 'error', '-ss', f'{max(0, t):.3f}', '-i', str(mp4), '-frames:v', '1', '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    x, y = (k % cols) * w, (k // cols) * h
    sheet.paste(Image.frombytes('RGB', (w, h), raw), (x, y))
    draw.rectangle((x, y, x + 70, y + 14), fill='black')
    draw.text((x + 3, y + 1), f'{t:.1f}', fill='yellow')
out = mp4.with_name(f'{mp4.stem}_앞뒤_{at:.1f}.jpg')
sheet.save(out, quality=85)
print(out)
