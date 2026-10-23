"""구간 합성 · 측정(Notion encode.py를 옮기고 화살표 합성을 더함). 구간별 원본 시간 유지(배속 · 중간 컷 없음), 구간 경계만 이어 붙인다.
사용: python3 encode.py <출력이름> <구간[:여기까지 쓸 ms]> ... [--silent]
  --silent: 음성 없는 시험 구간(큐 길이만 있고 음성 파일이 없음)을 영상만 합성한다.
config.json pointer=overlay면 페이지 화살표는 투명하게 녹화됐으므로, 기록된 이동(motions: 출발 · 도착 · 시작 시각 · 계획 길이)으로
30fps마다 화살표를 그린다(안내 1절 「커서 표시 보정」: 기록된 위치 · 시각 그대로, 화면 · 조작 · 음성은 원본, 두 화살표 없음).
화면 내용은 그 시각까지 받은 마지막 원본 프레임이다 — 원본에 없는 화면을 만들지 않는다."""
import json, subprocess, sys, wave
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding='utf-8')
from common import CFG, WORK as base, AUDIO as audio, ffmpeg
ff = ffmpeg()
args = [a for a in sys.argv[1:] if not a.startswith('--')]
silent = '--silent' in sys.argv
name, specs = args[0], args[1:]
dest = base / name
dest.mkdir(exist_ok=True)
SR, FPS = 44100, 30
DSF = CFG['viewport']['deviceScaleFactor']
W, H = round(CFG['viewport']['width'] * DSF), round(CFG['viewport']['height'] * DSF)
OVERLAY = CFG.get('pointer') == 'overlay'


def arrow():
    """ui.mjs의 화살표(SVG viewBox 25x34 → CSS 20x27)를 배율대로 8배 크게 그려 줄인다(후광 없음, 흰 채움 · 얇은 검은 테두리)."""
    k = 8; sx, sy = 20 / 25 * DSF * k, 27 / 34 * DSF * k
    pts = [(1, 1), (1, 25), (7, 20), (12, 31), (17, 29), (12, 18), (22, 18)]
    im = Image.new('RGBA', (round(25 * sx / 1) + 4, round(34 * sy) + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon([(x * sx, y * sy) for x, y in pts], fill=(255, 255, 255, 255), outline=(17, 17, 17, 255), width=round(1.7 * sx))
    return im.resize((round(im.width / k), round(im.height / k)), Image.LANCZOS)


ARROW = arrow()


def smooth(t):
    return t * t * (3 - 2 * t)


def pointer_at(ms, motions, start):
    """그 시각의 화살표 위치(CSS px). 이동 중이면 기록된 시작 시각 · 계획 길이로 페이지 애니메이션과 같은 곡선을 따른다."""
    pos = start
    for m in motions:
        g = m.get('glide', m['start'])
        if ms < g:
            break
        u = min(1.0, (ms - g) / m['planned_ms'])
        a = m['from']
        pos = (a['x'] + (m['x'] - a['x']) * smooth(u), a['y'] + (m['y'] - a['y']) * smooth(u))
    return pos


lines, cues, motions, segs, clicks = [], [], [], [], []
plan = []   # 합성할 (구간, 원본 프레임 목록, 사용 ms, 이동, 화살표 시작)
offset = 0.0
for spec in specs:
    seg, _, cut = spec.partition(':')
    t = json.loads((base / seg / 'timing.json').read_text(encoding='utf-8'))
    end_ms = float(cut) if cut else t['duration']
    if t['error'] and not cut:
        raise RuntimeError(f'{seg}: errored take needs an explicit cut point: {t["error"][:120]}')
    for a in t['actions']:
        if a['time'] < end_ms < a['time'] + a['duration']:
            raise RuntimeError(f'{seg}: cut {end_ms} splits speech {a["id"]}')
    fr = sorted(t['frames'], key=lambda f: f['sourceTimestamp'])
    times = [max(0.0, f['sourceTimestamp'] * 1000 - t['start']) for f in fr]
    keep = [(f, x) for f, x in zip(fr, times) if x < end_ms]
    ps = json.loads((base / seg / 'pointer-start.json').read_text(encoding='utf-8')) if (base / seg / 'pointer-start.json').exists() else None
    if OVERLAY and (not ps or ps.get('mode') != 'overlay'):
        raise RuntimeError(f'{seg}: pointer=overlay인데 페이지 화살표를 그대로 녹화한 구간이다(두 화살표가 보인다). config.json pointer를 page로 하거나 다시 녹화한다')
    plan.append((seg, keep, end_ms, t['motions'], (ps['x'], ps['y']) if ps else None))
    for a in t['actions']:
        if a['time'] < end_ms:
            cues.append({**a, 'segment': seg, 'g': offset + a['time']})
    for m in t['motions']:
        if m['end'] <= end_ms:
            v = [x for x in times if m['start'] <= x <= m['end']]
            g = [b - a for a, b in zip([m['start']] + v, v + [m['end']])]
            motions.append({'segment': seg, 'start_ms': round(offset + m['start']), 'duration_ms': m['end'] - m['start'], 'planned_ms': m.get('planned_ms'),
                            'source_frames': len(v), 'source_max_gap_ms': round(max(g))})
    st = json.loads((base / seg / 'end-state.json').read_text(encoding='utf-8'))
    for c in st.get('clicks', []):
        clicks.append({'segment': seg, 'x': c['x'], 'y': c['y'], 'dx': round(c['px'] - c['x'], 2), 'dy': round(c['py'] - c['y'], 2), 'gliding': c.get('gliding')})
    segs.append({'segment': seg, 'used_ms': end_ms, 'recorded_ms': t['duration'], 'error': t['error'], 'end_tab': st.get('tab')})
    offset += end_ms
total = offset / 1000

# 영상: 30fps마다 그 시각의 마지막 원본 프레임 + (overlay면) 기록된 경로의 화살표
video = dest / 'video.mp4'
enc = subprocess.Popen([ff, '-y', '-v', 'warning', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', str(video)], stdin=subprocess.PIPE)
cache = {}
for seg, keep, end_ms, mots, pstart in plan:
    n = int(end_ms / 1000 * FPS)
    j = 0
    for k in range(n):
        ms = k * 1000 / FPS
        while j + 1 < len(keep) and keep[j + 1][1] <= ms:
            j += 1
        f = keep[j][0]['file']
        if f not in cache:
            cache.clear(); cache[f] = Image.open(base / seg / f).convert('RGB')
        im = cache[f]
        if OVERLAY:
            im = im.copy(); x, y = pointer_at(ms, mots, pstart)
            im.paste(ARROW, (round(x * DSF), round(y * DSF)), ARROW)
        enc.stdin.write(im.tobytes())
enc.stdin.close()
if enc.wait():
    raise RuntimeError('ffmpeg video encode failed')

mp4 = dest / f'{name}_1080p.mp4'
if silent:
    video.replace(mp4)
else:
    cursor = 0
    with wave.open(str(dest / 'narration.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        for a in cues:
            s = round(a['g'] / 1000 * SR)
            if s < cursor:
                raise RuntimeError('Overlapping speech ' + a['id'])
            w.writeframesraw(b'\0\0' * (s - cursor))
            pcm = subprocess.check_output([ff, '-v', 'error', '-i', str(audio / (a['id'] + '.mp3')), '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'])
            w.writeframesraw(pcm); cursor = s + len(pcm) // 2
        w.writeframesraw(b'\0\0' * max(0, round(total * SR) - cursor))
    subprocess.run([ff, '-y', '-v', 'warning', '-i', str(video), '-i', str(dest / 'narration.wav'), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', str(mp4)], check=True)
    video.unlink()
subprocess.run([ff, '-v', 'error', '-i', str(mp4), '-f', 'null', '-'], check=True)


def stamp(ms):
    ms = round(ms); m, s = divmod(ms, 60000); return f'{m:02}:{s // 1000:02}.{s % 1000:03}'


if not silent:
    (dest / '자막.srt').write_text('\n\n'.join(f"{i+1}\n00:{stamp(a['g']).replace('.', ',')} --> 00:{stamp(a['g']+a['duration']).replace('.', ',')}\n{a['text']}" for i, a in enumerate(cues)) + '\n', encoding='utf-8')
rows = []
for i, a in enumerate(cues):
    r = {'id': a['id'], 'speech': [stamp(a['g']), stamp(a['g'] + a['duration'])]}
    if a.get('actionStart') is not None:
        o = a['g'] - a['time']
        r['action'] = [stamp(o + a['actionStart']), stamp(o + a['actionEnd']) if a.get('actionEnd') is not None else None]
        r['commit'] = stamp(o + a['commit']) if a.get('commit') else None
    rows.append(r)
gaps = [m['source_max_gap_ms'] for m in motions]
report = {'output': mp4.name, 'duration_s': round(total, 3), 'source': f'{W}x{H} JPEG screencast, UI 150%', 'output_fps': FPS,
          'pointer': '기록 경로로 합성(보정판, 페이지 화살표는 투명 녹화)' if OVERLAY else '페이지 화살표 원본',
          'segments': segs, 'speech_cues': len(cues), 'cue_timeline': rows, 'clicks': clicks,
          'motion_summary': {'count': len(motions), 'source_max_gap_ms_max': max(gaps) if gaps else None, 'source_over_100ms': sum(g >= 100 for g in gaps)},
          'motions': motions, 'decode': 'passed', 'voice': '없음(시험)' if silent else '안치윤',
          'not_verified': ['직접 청취', '사용자 재생 확인']}
(dest / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: report[k] for k in ['output', 'duration_s', 'pointer', 'speech_cues', 'motion_summary']}, ensure_ascii=False))
