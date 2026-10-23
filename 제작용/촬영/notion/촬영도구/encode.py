"""구간 합성·측정. 구간별 원본 시간 유지(배속·중간 컷 없음), 구간 경계만 이어 붙인다.
사용: python encode.py <출력이름> <구간[:여기까지 쓸 ms]> ...   (구간 = config.json work 아래 폴더)
예: python encode.py Notion_합본 take-25d:185585 take-25u take-26 …  — 실패 조각은 이어 찍은 큐 시작 시각에서 자른다."""
import json, os, re, subprocess, sys, wave
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
from common import WORK as base, AUDIO as audio, ffmpeg
ff = ffmpeg()
name, specs = sys.argv[1], sys.argv[2:]
dest = base / name
dest.mkdir(exist_ok=True)
SR = 44100
lines, cues, motions, clicks, segs = [], [], [], [], []
offset = 0.0
for spec in specs:
    seg, _, cut = spec.partition(':')
    t = json.loads((base / seg / 'timing.json').read_text(encoding='utf-8'))
    end_ms = float(cut) if cut else t['duration']
    if t['error'] and not cut:
        raise RuntimeError(f'{seg}: errored take needs an explicit cut point: {t["error"][:120]}')
    for a in t['actions']:
        if a['time'] < end_ms and a['time'] + a['duration'] > end_ms:
            raise RuntimeError(f'{seg}: cut {end_ms} splits speech {a["id"]}')
    fr = sorted(t['frames'], key=lambda f: f['sourceTimestamp'])
    times = [max(0.0, f['sourceTimestamp'] * 1000 - t['start']) for f in fr]
    keep = [(f, x) for f, x in zip(fr, times) if x < end_ms]
    for i, (f, x) in enumerate(keep):
        nxt = keep[i + 1][1] if i + 1 < len(keep) else end_ms
        lines += [f"file '{(base / seg / f['file']).as_posix()}'", 'option framerate 1000', f'duration {max(0.001, (nxt - x) / 1000):.6f}']
    for a in t['actions']:
        if a['time'] < end_ms:
            cues.append({**a, 'segment': seg, 'g': offset + a['time']})
    for m in t['motions']:
        if m['end'] <= end_ms:
            v = [x for x in times if m['start'] <= x <= m['end']]
            g = [b - a for a, b in zip([m['start']] + v, v + [m['end']])]
            motions.append({'segment': seg, 'start_ms': round(offset + m['start']), 'duration_ms': m['end'] - m['start'], 'planned_ms': m.get('planned_ms'), 'frames': len(v), 'max_gap_ms': round(max(g))})
    st = json.loads((base / seg / 'end-state.json').read_text(encoding='utf-8'))
    segs.append({'segment': seg, 'used_ms': end_ms, 'recorded_ms': t['duration'], 'error': t['error'], 'end_url': st['url']})
    offset += end_ms
for c in st['clicks']:
    clicks.append({'x': c['x'], 'y': c['y'], 'dx': round(c['px'] - c['x'], 2), 'dy': round(c['py'] - c['y'], 2), 'gliding': c.get('gliding')})
# 마지막 프레임의 duration은 다음 항목이 있어야 지켜진다. 끝에 같은 그림을 한 번 더 넣되 option framerate가 빠지면 ffmpeg가 무시해
# 마지막 정지 화면만큼 영상이 잘린다(v10 14.7초 · v11 6.6초, 끝인사 동안 화면이 멈춰 프레임이 없음).
lines += [lines[-3], 'option framerate 1000']
(dest / 'frames.concat').write_text('\n'.join(lines) + '\n', encoding='utf-8')
total = offset / 1000
cursor = 0
with wave.open(str(dest / 'narration.wav'), 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    # 음성 교체(환경변수 VOICE_OVERRIDES = JSON [{segment, time, file}]): 녹화한 문장 자리에 고친 문장을 넣는다.
    # 고친 문장이 원래 문장이 끝나던 시점에 끝나도록 오른쪽에 맞춘다(조작이 말 직후에 그대로 온다). 원래보다 길면 멈춘다.
    ovp = os.environ.get('VOICE_OVERRIDES')
    ov = json.loads(Path(ovp).read_text(encoding='utf-8')) if ovp else []
    used = set()
    for a in cues:
        src, s, pcm = audio / (a['id'] + '.mp3'), round(a['g'] / 1000 * SR), None
        hit = [i for i, o in enumerate(ov) if o['segment'] == a['segment'] and abs(o['time'] - a['time']) < 5]
        if hit:
            o = ov[hit[0]]; used.add(hit[0])
            src = (Path(ovp).parent / o['file']).resolve()
            pcm = subprocess.check_output([ff, '-v', 'error', '-i', str(src), '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'])
            n, orig = len(pcm) // 2, round(a['duration'] / 1000 * SR)
            if n > orig + SR // 10:
                raise RuntimeError(f"Override longer than recorded speech: {a['segment']} {a['id']} {n / SR:.2f}s > {orig / SR:.2f}s")
            s += max(0, orig - n); a['override'] = o['file']
        if s < cursor:
            raise RuntimeError('Overlapping speech ' + a['id'])
        w.writeframesraw(b'\0\0' * (s - cursor))
        if pcm is None:
            pcm = subprocess.check_output([ff, '-v', 'error', '-i', str(src), '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'])
        w.writeframesraw(pcm); cursor = s + len(pcm) // 2
    if len(used) != len(ov):
        raise RuntimeError('Unmatched voice overrides: ' + json.dumps([o for i, o in enumerate(ov) if i not in used], ensure_ascii=False))
    w.writeframesraw(b'\0\0' * max(0, round(total * SR) - cursor))
mp4 = dest / f'{name}_안치윤_1080p.mp4'
subprocess.run([ff, '-y', '-v', 'warning', '-f', 'concat', '-safe', '0', '-i', str(dest / 'frames.concat'), '-i', str(dest / 'narration.wav'),
                '-r', '30', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', str(mp4)], check=True)
subprocess.run([ff, '-v', 'error', '-i', str(mp4), '-f', 'null', '-'], check=True)
# 끝까지 디코드된다고 길이가 맞는 것은 아니다(v10 · v11 첫 합성이 끝인사를 잘라 먹고도 통과). 영상 · 음성 각각 끝 시각을 재서 구간 합계와 비교한다.
for stream in ('v', 'a'):
    log = subprocess.run([ff, '-hide_banner', '-i', str(mp4), '-map', f'0:{stream}', '-c', 'copy', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
    h, m, s = re.findall(r'time=(\d+):(\d+):([\d.]+)', log)[-1]
    got = int(h) * 3600 + int(m) * 60 + float(s)
    if abs(got - offset / 1000) > 0.1:
        raise RuntimeError(f'{mp4.name}: {stream} stream {got:.2f}s != segments {offset / 1000:.2f}s')
def stamp(ms):
    ms = round(ms); m, s = divmod(ms, 60000); return f'{m:02}:{s // 1000:02}.{s % 1000:03}'
(dest / '자막.srt').write_text('\n\n'.join(f"{i+1}\n00:{stamp(a['g']).replace('.', ',')} --> 00:{stamp(a['g']+a['duration']).replace('.', ',')}\n{a['text']}" for i, a in enumerate(cues)) + '\n', encoding='utf-8')
rows = []
for i, a in enumerate(cues):
    r = {'id': a['id'], 'speech': [stamp(a['g']), stamp(a['g'] + a['duration'])]}
    if a.get('actionStart') is not None:
        o = a['g'] - a['time']
        r['action'] = [stamp(o + a['actionStart']), stamp(o + a['actionEnd']) if a.get('actionEnd') is not None else None]
        r['commit'] = stamp(o + a['commit']) if a.get('commit') else None
        r['commit_before_speech_end_ms'] = round(a['g'] + a['duration'] - (o + a['commit'])) if a.get('commit') else None
        nxt = cues[i + 1] if i + 1 < len(cues) else None
        if nxt and a.get('actionEnd') is not None:
            r['next_speech_after_action_ms'] = round(nxt['g'] - (o + a['actionEnd']))
    rows.append(r)
gaps = [m['max_gap_ms'] for m in motions]
report = {'output': mp4.name, 'duration_s': round(total, 3), 'source': '1920x1080 JPEG85 screencast, UI 150%', 'output_fps': 30,
          'segments': segs, 'speech_cues': len(cues), 'cue_timeline': rows, 'clicks': clicks,
          'motion_summary': {'count': len(motions), 'max_gap_ms_max': max(gaps), 'over_100ms': [m for m in motions if m['max_gap_ms'] >= 100]},
          'motions': motions, 'decode': 'passed', 'voice': '안치윤 (기존 캐시 재사용, 신규 생성 0)',
          'not_verified': ['직접 청취(도구 없음)', '스크롤 조작(이 구간에 없음)', '사용자 재생 확인']}
(dest / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: report[k] for k in ['duration_s', 'speech_cues', 'motion_summary', 'segments']}, ensure_ascii=False, indent=1))
print(json.dumps(clicks))
