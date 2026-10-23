"""완성 영상 검증 — 게시 전에 한 번 돌린다. 사용: python3 verify.py <영상.mp4> <자막.srt> [<결과 폴더>]
사람이 귀로 듣는 확인을 대신하지 않는다(발음 · 억양은 사용자 재생 확인). 기계로 잴 수 있는 것만 잰다.
  1. 길이: 영상 · 음성 길이 차이 0.2초 이내, 마지막 자막이 영상 안에서 끝남
  2. 자막: 시간이 거꾸로 가거나 겹치지 않음
  3. 소리: 통합 크기(LUFS) · 최고점, 자막이 있는 구간이 무음이 아님(말 잘림 · 빠진 음성), 자막 사이 무음이 너무 길지 않음(기본 8초)
  4. 화면: 검은 화면 0.5초 이상 없음, 문장마다 한 장면(문장 3/4 지점)을 뽑아 모음 그림으로 남김 — 화면 · 화살표 · 말이 맞는지는 이 그림을 눈으로 대조한다
결과: <결과 폴더>/검증.json · 장면_NN.jpg. 하나라도 실패하면 종료 코드 1."""
import json, re, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding='utf-8')
from common import ffmpeg

ff = ffmpeg()
mp4, srt = Path(sys.argv[1]), Path(sys.argv[2])
out = Path(sys.argv[3]) if len(sys.argv) > 3 else mp4.parent / (mp4.stem + '_검증')
out.mkdir(parents=True, exist_ok=True)
GAP_MAX = 8.0


def probe(stream):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', stream, '-show_entries', 'stream=duration', '-of', 'csv=p=0', str(mp4)], capture_output=True, text=True)
    return float(r.stdout.strip().splitlines()[0])


def ms(t):
    h, m, s = t.split(':'); s, f = s.split(','); return ((int(h) * 60 + int(m)) * 60 + int(s)) + int(f) / 1000


cues = []
for b in srt.read_text(encoding='utf-8-sig').strip().split('\n\n'):
    l = b.strip().split('\n'); a, z = l[1].split(' --> '); cues.append((ms(a), ms(z), ' '.join(l[2:])))
v, a = probe('v:0'), probe('a:0')
fails, report = [], {'video': str(mp4), 'subtitles': len(cues), 'video_s': round(v, 3), 'audio_s': round(a, 3)}
if abs(v - a) > 0.2: fails.append(f'영상 {v:.2f}s · 음성 {a:.2f}s 차이')
if cues[-1][1] > v + 0.05: fails.append(f'마지막 자막 {cues[-1][1]:.2f}s가 영상 {v:.2f}s 뒤에서 끝남')
for i in range(1, len(cues)):
    if cues[i][0] < cues[i - 1][1] - 0.02: fails.append(f'자막 {i}·{i+1} 겹침({cues[i-1][1]:.2f} > {cues[i][0]:.2f})')

# 소리: 크기 · 최고점, 무음 구간
e = subprocess.run([ff, '-nostats', '-i', str(mp4), '-map', '0:a', '-af', 'ebur128=peak=true,silencedetect=n=-45dB:d=0.6', '-f', 'null', '-'], capture_output=True, text=True).stderr
lufs = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', e)[-1]); peak = float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS', e)[-1])
sil = [(float(s), float(t)) for s, t in zip(re.findall(r'silence_start: (-?[\d.]+)', e), re.findall(r'silence_end: ([\d.]+)', e))]
report.update(lufs=lufs, true_peak_dbfs=peak, silences=len(sil))
if peak > -0.5: fails.append(f'최고점 {peak} dBFS(찌그러짐 위험)')
# 자막(말) 구간 안의 긴 무음 = 말이 빠졌거나 잘림. 문장 사이 쉼(0.6초 남짓)은 자막 경계에 걸쳐 있으므로, 자막 안쪽에 1.2초 넘게 들어간 무음만 본다
for s, t in sil:
    for c0, c1, txt in cues:
        inside = min(t, c1) - max(s, c0)
        if inside > 1.2: fails.append(f'자막 안 무음 {inside:.1f}s @ {max(s, c0):.1f}s 「{txt[:20]}」')
gaps = [(cues[i][0] - cues[i - 1][1], cues[i - 1][1]) for i in range(1, len(cues))]
long_gaps = [(round(g, 1), round(at, 1)) for g, at in gaps if g > GAP_MAX]
report['longest_gap_s'] = round(max([g for g, _ in gaps] or [0]), 1)
report['gaps_over_limit'] = long_gaps   # 실패로 치지 않음: 기다리는 화면(로딩 등)일 수 있어 장면 그림으로 판단

# 화면: 검은 화면
b = subprocess.run([ff, '-nostats', '-i', str(mp4), '-map', '0:v', '-vf', 'blackdetect=d=0.5:pix_th=0.08', '-f', 'null', '-'], capture_output=True, text=True).stderr
blacks = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', b)
report['black'] = blacks
if blacks: fails.append(f'검은 화면 {len(blacks)}곳: {blacks[:3]}')

# 문장마다 한 장면 → 9장씩 모음
shots = []
for i, (c0, c1, txt) in enumerate(cues):
    t = c0 + (c1 - c0) * 0.75; f = out / f'_{i:03d}.jpg'
    subprocess.run([ff, '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', str(mp4), '-frames:v', '1', '-vf', 'scale=640:-1', str(f)], check=True)
    shots.append((f, i + 1, t, txt))
for k in range(0, len(shots), 9):
    s = Image.new('RGB', (1920, 1080), 'white'); d = ImageDraw.Draw(s)
    for j, (f, n, t, txt) in enumerate(shots[k:k + 9]):
        s.paste(Image.open(f), ((j % 3) * 640, (j // 3) * 360)); d.rectangle(((j % 3) * 640, (j // 3) * 360, (j % 3) * 640 + 70, (j // 3) * 360 + 14), fill='black')
        d.text(((j % 3) * 640 + 3, (j // 3) * 360 + 1), f'{n} {int(t // 60)}:{t % 60:04.1f}', fill='yellow')
    s.save(out / f'장면_{k // 9 + 1:02d}.jpg', quality=82)
for f, *_ in shots: f.unlink()
report['scene_sheets'] = sorted(p.name for p in out.glob('장면_*.jpg'))
report['fails'] = fails
(out / '검증.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps({k: report[k] for k in ['video_s', 'audio_s', 'subtitles', 'lufs', 'true_peak_dbfs', 'longest_gap_s', 'gaps_over_limit', 'fails']}, ensure_ascii=False))
sys.exit(1 if fails else 0)
