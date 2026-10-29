"""여러 영상을 한 편으로 잇는다(예: README 설명 → 설치부터 실행까지 → 포털 소개). 사용:
  python3 join.py <출력.mp4> <조각1.mp4>:<조각1.srt>[:<장 이름>] <조각2.mp4>:<조각2.srt>[:<장 이름>] ...
  1. 조각마다 소리 크기를 잰다(loudnorm 1차). 다른 세션 · 다른 도구로 만든 조각은 크기가 다르다(2026-10-23: −22.0 · −16.3 · −21.5 LUFS).
  2. 모두 −16 LUFS · 최고점 −1.5 dB로 맞춰 48 kHz 한 채널로 잇고, 영상은 1920×1080 30 fps libx264 crf 18로 다시 만든다(시간 기준이 조각마다 달라 그냥 붙이지 않는다).
  3. 자막은 앞 조각들의 길이만큼 시간을 밀어 하나로 합친다(<출력>.srt).
  4. 장(chapter): 조각에 장이 있으면 앞 조각 길이만큼 밀어 옮기고, 없으면 <장 이름>을 준 조각에 장 하나를 단다.
     ffmpeg 기본값은 첫 장 있는 조각의 장을 시간 그대로 옮긴다 — 2026-10-23 합본이 그래서 README 구간에 「Python」 장이 붙었다.
  5. 이음매마다 앞 0.7초 · 뒤 0.4초 장면을 <출력>_이음매.jpg로 남긴다 — 눈으로 이어짐을 확인한다.
GitHub 파일 한도는 100 MiB다. 넘으면 실패한다(crf를 올려 다시 만든다). 끝나면 verify.py로 검증한다."""
import json, re, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding='utf-8')
from common import ffmpeg, chapters, write_chapters

ff = ffmpeg()
out = Path(sys.argv[1]); parts = [(a.split(':') + [None, None])[:3] for a in sys.argv[2:]]   # 조각, 자막, 장 이름
if len(parts) < 2: sys.exit('조각이 둘 이상 필요하다')
CRF = int(__import__('os').environ.get('CRF', '18'))


def dur(f):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode())


meas, durs = [], []
for v, _, _ in parts:
    e = subprocess.run([ff, '-nostats', '-i', v, '-map', '0:a', '-af', 'aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = json.loads(e[e.rindex('{'):e.rindex('}') + 1]); meas.append(m); durs.append(dur(v))
    print(f'{Path(v).name}: {durs[-1]:.2f}s · {m["input_i"]} LUFS · 최고점 {m["input_tp"]}')
fc = []
for i, m in enumerate(meas):
    fc.append(f"[{i}:a]aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
              f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000,aformat=channel_layouts=mono[a{i}]")
    fc.append(f'[{i}:v]setpts=PTS-STARTPTS,scale=1920:1080,fps=30,format=yuv420p[v{i}]')
fc.append(''.join(f'[v{i}][a{i}]' for i in range(len(parts))) + f'concat=n={len(parts)}:v=1:a=1[v][a]')
chs, off = [], 0.0
for (v, _, title), d in zip(parts, durs):
    own = chapters(v)
    chs += [(off + a, off + min(z, d), t) for a, z, t in own] if own else ([(off, off + d, title)] if title else [])
    off += d
meta = out.with_name(out.stem + '_장.txt'); write_chapters(meta, chs)
cmd = [ff, '-y', '-nostats']
for v, _, _ in parts: cmd += ['-i', v]
cmd += ['-i', str(meta), '-map_chapters', str(len(parts))]   # -map_metadata -1 은 장 이름까지 지운다
cmd += ['-filter_complex', ';'.join(fc), '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', str(CRF), '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-movflags', '+faststart', str(out)]
subprocess.run(cmd, check=True, capture_output=True)
size = out.stat().st_size
if size >= 100 * 1024 * 1024: sys.exit(f'{size/2**20:.1f} MiB ≥ 100 MiB(GitHub 한도): CRF=20 등으로 다시 만든다')

# 자막 합치기
def ms(t):
    h, m, s = t.split(':'); s, f = s.split(','); return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(f)
def fmt(x):
    x = int(round(x)); h, x = divmod(x, 3600000); m, x = divmod(x, 60000); s, f = divmod(x, 1000); return f'{h:02d}:{m:02d}:{s:02d},{f:03d}'
blocks, off, n = [], 0.0, 0
for (v, srt, _), d in zip(parts, durs):
    if srt:
        for b in Path(srt).read_text(encoding='utf-8-sig').strip().split('\n\n'):
            l = b.strip().split('\n')
            if len(l) < 3: continue   # 빈 자막 파일 · 빈 블록(말 없는 조각)
            a, z = l[1].split(' --> '); n += 1
            blocks.append(f'{n}\n{fmt(ms(a) + off * 1000)} --> {fmt(ms(z) + off * 1000)}\n' + '\n'.join(l[2:]))
    off += d
out.with_suffix('.srt').write_text('\n\n'.join(blocks) + '\n', encoding='utf-8')

# 이음매 장면
seams, t = [], 0.0
for d in durs[:-1]:
    t += d; seams.append(t)
s = Image.new('RGB', (1280, 360 * len(seams)), 'white'); dr = ImageDraw.Draw(s)
for k, t in enumerate(seams):
    for j, dt in enumerate((-0.7, 0.4)):
        f = out.with_name(f'_seam{k}{j}.jpg')
        subprocess.run([ff, '-v', 'error', '-y', '-ss', f'{t + dt:.2f}', '-i', str(out), '-frames:v', '1', '-vf', 'scale=640:-1', str(f)], check=True)
        s.paste(Image.open(f), (j * 640, k * 360)); dr.text((j * 640 + 4, k * 360 + 4), f'{t + dt:.1f}s', fill='red'); f.unlink()
s.save(out.with_name(out.stem + '_이음매.jpg'), quality=85)
total = dur(str(out))
print(json.dumps({'output': str(out), 'duration_s': round(total, 2), 'parts_sum_s': round(sum(durs), 2), 'size_mib': round(size / 2**20, 1),
                  'subtitles': n, 'chapters': len(chs), 'seams_s': [round(x, 2) for x in seams]}, ensure_ascii=False))
if abs(total - sum(durs)) > 0.3: sys.exit('합본 길이가 조각 합과 0.3초 넘게 다르다')
