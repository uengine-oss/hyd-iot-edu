"""게시한 영상에서 말 없는 구간을 잘라 낸다(예: 합본 안 설치 영상의 바탕화면 · 광고 알림 4초). 사용:
  python3 cut.py <입력.mp4> <입력.srt> <출력.mp4> <시작초>-<끝초> [<시작초>-<끝초> ...]
  1. 자를 구간에 걸친 자막이 있으면 멈춘다(말을 자르지 않는다). 남는 자막은 앞에서 잘린 길이만큼 당긴다(<출력>.srt).
  2. 영상은 남는 조각마다 따로 libx264 crf 18로 만들고 다시 만들지 않고 잇는다(concat demuxer -c copy).
     한 filter graph에서 같은 입력을 trim 두 갈래로 나누면 처리되지 않은 프레임이 쌓여 27분 1080p에서 12 GB를 넘겨 커널이 ffmpeg를 죽였다(2026-10-23, 두 번).
  3. 소리는 원본에서 한 번에 atrim · concat해 다시 붙인다. 조각마다 AAC로 만들어 이으면 조각 앞 1024샘플(21 ms)만큼 소리가 늦어진다(같은 날 실측).
  4. 장(chapter)도 잘린 만큼 당기고, 자른 구간 안에 든 장 경계는 자른 자리로 옮긴다.
끝나면 verify.py로 검증하고 자른 자리 앞뒤를 scenes.py로 본다. GitHub 한도 100 MiB를 넘으면 실패한다."""
import json, subprocess, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
from common import ffmpeg, chapters, write_chapters

ff = ffmpeg()
if len(sys.argv) < 5: sys.exit(__doc__)
src, srt, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
cuts = sorted(tuple(map(float, a.split('-'))) for a in sys.argv[4:])
dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(src)]).decode())
for a, z in cuts:
    if not 0 <= a < z <= dur: sys.exit(f'구간 {a}-{z}가 영상 길이 {dur:.2f}초 밖이다')
keep, t = [], 0.0
for a, z in cuts:
    if a > t: keep.append((t, a))
    t = z
if t < dur: keep.append((t, dur))


def shift(x):
    """원본 시각 → 자른 뒤 시각. 자른 구간 안이면 자른 자리."""
    d = 0.0
    for a, z in cuts:
        if x >= z: d += z - a
        elif x > a: return a - d
    return x - d


# 자막
def ms(s):
    h, m, s = s.split(':'); s, f = s.split(','); return ((int(h) * 60 + int(m)) * 60 + int(s)) + int(f) / 1000
def fmt(x):
    x = int(round(x * 1000)); h, x = divmod(x, 3600000); m, x = divmod(x, 60000); s, f = divmod(x, 1000); return f'{h:02d}:{m:02d}:{s:02d},{f:03d}'
blocks = []
for b in srt.read_text(encoding='utf-8-sig').strip().split('\n\n'):
    l = b.strip().split('\n')
    if len(l) < 3: continue
    s0, s1 = map(ms, l[1].split(' --> '))
    for a, z in cuts:
        if s0 < z and s1 > a: sys.exit(f'자막 {l[0]}({l[1]})이 자를 구간 {a}-{z}에 걸친다 — 말을 자르게 된다')
    blocks.append(f'{len(blocks) + 1}\n{fmt(shift(s0))} --> {fmt(shift(s1))}\n' + '\n'.join(l[2:]))
out.with_suffix('.srt').write_text('\n\n'.join(blocks) + '\n', encoding='utf-8')

# 영상: 조각마다 따로
tmp = out.with_name(out.stem + '_조각'); tmp.mkdir(exist_ok=True)
names = []
for i, (a, z) in enumerate(keep):
    f = tmp / f'v{i}.mp4'; names.append(f)
    subprocess.run([ff, '-y', '-nostats', '-v', 'error', '-ss', f'{a:.3f}', '-i', str(src), '-t', f'{z - a:.3f}', '-an',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', '30', str(f)], check=True)
lst = tmp / 'list.txt'; lst.write_text(''.join(f"file '{f.name}'\n" for f in names), encoding='utf-8')
video = tmp / 'video.mp4'
subprocess.run([ff, '-y', '-nostats', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(video)], check=True)

# 소리: 원본에서 한 번에 · 장
fc = ';'.join(f'[1:a]atrim={a:.3f}:{z:.3f},asetpts=PTS-STARTPTS[a{i}]' for i, (a, z) in enumerate(keep))
fc += ';' + ''.join(f'[a{i}]' for i in range(len(keep))) + f'concat=n={len(keep)}:v=0:a=1[a]'
chs = [(shift(a), shift(z), t) for a, z, t in chapters(src)]
chs = [c for c in chs if c[1] > c[0]]
meta = tmp / '장.txt'; write_chapters(meta, chs)
subprocess.run([ff, '-y', '-nostats', '-v', 'error', '-i', str(video), '-i', str(src), '-i', str(meta), '-filter_complex', fc,
                '-map', '0:v', '-map', '[a]', '-map_chapters', '2', '-c:v', 'copy',
                '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '1', '-movflags', '+faststart', str(out)], check=True)
size = out.stat().st_size
new = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(out)]).decode())
want = dur - sum(z - a for a, z in cuts)
print(json.dumps({'output': str(out), 'duration_s': round(new, 2), 'expected_s': round(want, 2), 'size_mib': round(size / 2**20, 1),
                  'subtitles': len(blocks), 'chapters': len(chs), 'cut_at_s': [round(shift(z), 2) for a, z in cuts]}, ensure_ascii=False))
if size >= 100 * 1024 * 1024: sys.exit(f'{size / 2**20:.1f} MiB ≥ 100 MiB(GitHub 한도)')
if abs(new - want) > 0.1: sys.exit(f'길이 {new:.2f}초가 기대 {want:.2f}초와 다르다')
