"""구간 합성·측정. 구간별 원본 시간 유지(배속·중간 컷 없음), 구간 경계만 이어 붙인다.
사용: python encode.py <출력이름> <구간[@빼낼시작ms-끝ms …][:여기까지 쓸 ms]> ...   (구간 = config.json work 아래 폴더)
   @a-b: 그 구간 안 [a, b) ms를 화면 · 소리 함께 들어낸다(이미 찍은 구간에서 문장을 뺄 때). 그 사이에 조작 · 커서 이동이 있으면 멈춘다.
         큐의 끝 문장을 들어낸 큐도 음성 교체를 받는다(새 음성이 남긴 앞부분을 대신한다 — 그 큐 글은 남긴 앞부분이어야 한다). 큐 가운데를 들어낸 큐는 교체하면 멈춘다.
   ~x: 앞 구간 끝 화면에서 이 구간 화면으로 0.4초 교차 전환하고, 0.4초에 이 구간 화면 원본을 둔다(다른 실행에서 이어 찍어 스크롤 · 사이드바가 달라진 이음새). 소리는 그대로.
   ~hold=ms: 이 구간 머리 ms까지는 앞 구간 끝 화면을 멈춰 보여 준다(그 동안의 말이 앞 화면을 설명할 때 — 27b 머리의 압축 파일 설명).
음성 교체(자동): 녹화한 큐 글과 지금 음성(audio_play)의 글이 다르면 지금 음성을 쓴다. 새 음성이 길면 그 큐가 시작하는 자리의 화면을 그만큼 멈춰
늘리고(뒤 화면 · 말 · 조작이 함께 밀린다), 짧으면 앞에 무음을 둬 큐 끝(조작 자리)을 지킨다. 바꾼 큐는 verification.json의 replaced에 남는다.
예: python encode.py Notion_합본 take-25d:185585 take-25u take-26 …  — 실패 조각은 이어 찍은 큐 시작 시각에서 자른다.
--무음: 음성 없이 같은 합성 · 인코딩 경로로 화면만 만든다(리허설 화면 녹화를 게시본과 같은 조건으로 잴 때 — 소리 자리는 무음)."""
import json, os, re, subprocess, sys, wave
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
from common import WORK as base, PLAY_AUDIO as audio, ffmpeg
ff = ffmpeg()
SILENT = '--무음' in sys.argv
args = [a for a in sys.argv[1:] if a != '--무음']
name, specs = args[0], args[1:]
dest = base / name
dest.mkdir(exist_ok=True)
SR = 44100
lines, cues, motions, clicks, segs = [], [], [], [], []
offset = 0.0
for spec in specs:
    seg, _, cut = spec.partition(':')
    import re as _re
    parts = _re.split(r'([~@])', seg); seg = parts[0]
    opts = [v for k, v in zip(parts[1::2], parts[2::2]) if k == '~']
    outs = [v for k, v in zip(parts[1::2], parts[2::2]) if k == '@']   # ~x와 @a-b는 어느 차례로 적어도 된다(v12b: ~x@… 에서 @를 놓쳤다)
    R = sorted(tuple(float(v) for v in o.split('-')) for o in outs)
    xfade = 'x' in opts
    hold = next((float(o[5:]) for o in opts if o.startswith('hold=')), 0.0)
    if (xfade or hold) and not lines:
        raise RuntimeError(f'{seg}: ~x / ~hold needs a previous segment')
    t = json.loads((base / seg / 'timing.json').read_text(encoding='utf-8'))
    end_ms = float(cut) if cut else t['duration']
    for r0, r1 in R:
        if not (0 <= r0 < r1 <= end_ms):
            raise RuntimeError(f'{seg}: bad removal {r0}-{r1}')
        for a in t['actions']:
            if a.get('actionStart') is not None and a.get('actionEnd') is not None and a['actionStart'] < r1 and a['actionEnd'] > r0:
                raise RuntimeError(f'{seg}: removal {r0}-{r1} overlaps action of {a["id"]}')
        for m in t['motions']:
            if m['start'] < r1 and m['end'] > r0:
                raise RuntimeError(f'{seg}: removal {r0}-{r1} overlaps a pointer motion at {m["start"]}')
    cutout = lambda x: any(r0 <= x < r1 for r0, r1 in R)
    # 음성 교체: 지금 음성 글이 녹화한 글과 다르면 그 큐를 새 음성으로 바꾼다. 늘어난 몫은 큐 시작에 화면을 멈춰 넣는다(INS).
    # 큐의 끝을 들어냈으면(@a-b가 큐 안에서 시작해 큐 끝 너머까지) 그 큐가 실제로 말하는 길이는 남긴 앞부분이다.
    kept_ms = lambda a: next((r0 - a['time'] for r0, r1 in R if a['time'] < r0 < a['time'] + a['duration'] <= r1), a['duration'])
    INS, NEWV = [], {}
    for a in t['actions']:
        jv = json.loads((audio / (a['id'] + '.json')).read_text(encoding='utf-8'))
        if jv['text'] != a['text']:
            NEWV[a['id']] = jv
            if jv['duration_ms'] > kept_ms(a):
                INS.append((a['time'], jv['duration_ms'] - kept_ms(a)))
    removed = lambda x: sum(max(0.0, min(x, r1) - r0) for r0, r1 in R if x > r0)
    pre = lambda x: x - removed(x) + sum(d for t0, d in INS if t0 < x)     # 그 자리에서 멈추기 전 시각
    shift = lambda x: x - removed(x) + sum(d for t0, d in INS if t0 <= x)  # 멈춘 뒤 시각
    if t['error'] and not cut:
        raise RuntimeError(f'{seg}: errored take needs an explicit cut point: {t["error"][:120]}')
    for a in t['actions']:
        if a['time'] < end_ms and a['time'] + a['duration'] > end_ms:
            raise RuntimeError(f'{seg}: cut {end_ms} splits speech {a["id"]}')
    fr = sorted(t['frames'], key=lambda f: f['sourceTimestamp'])
    times = [max(0.0, f['sourceTimestamp'] * 1000 - t['start']) for f in fr]
    keep = [(f, shift(x)) for f, x in zip(fr, times) if x < end_ms and not cutout(x)]
    prev_last = Path(lines[-3][6:-1]) if lines else None   # 앞 구간 마지막 프레임 파일
    if hold:
        if hold >= end_ms:
            raise RuntimeError(f'{seg}: hold {hold} longer than the segment')
        later = [(f, x) for f, x in keep if x >= hold]
        keep = [({'file': str(prev_last)}, 0.0)] + later
    for t0, d in INS:   # 멈춤: 큐가 시작하는 자리의 화면을 d ms 더 보여 준다
        act = [f for f, x in zip(fr, times) if x <= t0 and not cutout(x)]
        keep.append(({'file': (act[-1] if act else fr[0])['file']}, pre(t0)))
    keep.sort(key=lambda k: k[1])
    if xfade:
        from PIL import Image
        xd = dest / 'xfade'; xd.mkdir(exist_ok=True)
        a_img = Image.open(prev_last).convert('RGB'); xs = []
        for k in range(12):   # 0.4초 · 30fps
            tk = k * 1000 / 30
            cur = [f for f, x in keep if x <= tk]
            b_file = cur[-1]['file'] if cur else keep[0][0]['file']
            b_img = Image.open(b_file if Path(b_file).is_absolute() else base / seg / b_file).convert('RGB')
            out = xd / f'{seg}_{k:02}.jpg'; Image.blend(a_img, b_img, (k + 1) / 13).save(out, quality=90); xs.append(({'file': str(out)}, tk))
        # 섞은 마지막 장에도 앞 화면이 8% 남는다. 녹화는 화면이 바뀔 때만 프레임을 남기므로, 0.4초에 뒤 화면 원본을 두지 않으면
        # 정적인 화면에서는 그 잔상이 다음 프레임까지 이어진다(v12d 10:06에서 10초, 25:22에서 1.9초 동안 글자가 두 겹).
        tail = [(f, x) for f, x in keep if x >= 400]
        if not tail or tail[0][1] > 400:
            cur = [f for f, x in keep if x <= 400]
            tail.insert(0, (cur[-1] if cur else keep[0][0], 400.0))
        keep = xs + tail
    # 들어낸 자리 바로 뒤 첫 프레임이 없으면 들어내기 직전 화면이 이어진다(화면이 바뀌지 않은 때). 그 위치는 shift로 맞춘다.
    for i, (f, x) in enumerate(keep):
        nxt = keep[i + 1][1] if i + 1 < len(keep) else shift(end_ms)
        fp_ = Path(f['file']); fp_ = fp_ if fp_.is_absolute() else base / seg / f['file']
        lines += [f"file '{fp_.as_posix()}'", 'option framerate 1000', f'duration {max(0.001, (nxt - x) / 1000):.6f}']
    for a in t['actions']:
        if a['time'] < end_ms:
            sp = [(max(r0, a['time']) - a['time'], min(r1, a['time'] + a['duration']) - a['time']) for r0, r1 in R if r0 < a['time'] + a['duration'] and r1 > a['time']]
            if sp and sp[0][0] <= 0 and sp[-1][1] >= a['duration']:
                continue   # 큐 전체를 들어냈다
            nv = NEWV.get(a['id'])
            rec = a['duration']
            if nv and sp:   # 끝을 들어낸 큐만 바꿀 수 있다: 새 음성은 남긴 앞부분을 대신한다(그 큐의 글은 남긴 앞부분이어야 한다)
                if kept_ms(a) >= a['duration']:
                    raise RuntimeError(f"{seg}: {a['id']} is replaced and cut in the middle (only a cut tail can be replaced)")
                rec, sp = kept_ms(a), []
            cues.append({**a, 'segment': seg, 'g': offset + pre(a['time']), 'drop': sp, 'duration': rec - sum(b - x for x, b in sp),
                         'new_voice': nv, 'rec_duration': rec, 'o_act': offset + shift(a['time'] + 1) - (a['time'] + 1)})
    for m in t['motions']:
        if m['end'] <= end_ms:
            m = {**m, 'start': shift(m['start']), 'end': shift(m['end'])}
            v = [x for x in times if m['start'] <= x <= m['end']]
            g = [b - a for a, b in zip([m['start']] + v, v + [m['end']])]
            motions.append({'segment': seg, 'start_ms': round(offset + m['start']), 'duration_ms': m['end'] - m['start'], 'planned_ms': m.get('planned_ms'), 'frames': len(v), 'max_gap_ms': round(max(g))})
    st = json.loads((base / seg / 'end-state.json').read_text(encoding='utf-8'))
    segs.append({'segment': seg, 'used_ms': shift(end_ms), 'removed': R, 'held': INS, 'replaced': sorted(NEWV), 'recorded_ms': t['duration'], 'error': t['error'], 'end_url': st['url']})
    offset += shift(end_ms)
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
        if a.get('new_voice'):   # 음성 교체: 짧으면 오른쪽(큐 끝)에 맞춘다, 길면 화면을 이미 멈춰 늘려 두었다
            nd = a['new_voice']['duration_ms']; s += max(0, round((a['rec_duration'] - nd) / 1000 * SR)); a['text'] = a['new_voice']['text']; a['duration'] = max(nd, a['rec_duration']); a['replaced'] = True
        if SILENT:
            continue
        if s < cursor:
            raise RuntimeError('Overlapping speech ' + a['id'])
        w.writeframesraw(b'\0\0' * (s - cursor))
        if pcm is None:
            pcm = subprocess.check_output([ff, '-v', 'error', '-i', str(src), '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'])
        for x, b in reversed(a.get('drop') or []):   # 들어낸 말 조각(큐 안 ms)을 소리에서도 뺀다
            i0, i1 = round(x / 1000 * SR) * 2, round(b / 1000 * SR) * 2
            pcm = pcm[:i0] + pcm[i1:]
        w.writeframesraw(pcm); cursor = s + len(pcm) // 2
    if len(used) != len(ov):
        raise RuntimeError('Unmatched voice overrides: ' + json.dumps([o for i, o in enumerate(ov) if i not in used], ensure_ascii=False))
    w.writeframesraw(b'\0\0' * max(0, round(total * SR) - cursor))
mp4 = dest / f'{name}_안치윤_1080p.mp4'
subprocess.run([ff, '-y', '-v', 'warning', '-f', 'concat', '-safe', '0', '-i', str(dest / 'frames.concat'), '-i', str(dest / 'narration.wav'),
                '-r', '30', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', str(mp4)], check=True)
subprocess.run([ff, '-v', 'error', '-i', str(mp4), '-f', 'null', '-'], check=True)
# 끝까지 디코드된다고 길이가 맞는 것은 아니다(v10 · v11 첫 합성이 끝인사를 잘라 먹고도 통과). 영상 · 음성 각각 끝 시각을 재서 구간 합계와 비교한다.
# 끝 시각은 실제로 든 것을 센다: 영상은 디코드한 프레임 수 ÷ 30, 소리는 디코드한 표본 수 ÷ 표본율. 예전에는 -c copy 로그의 time=(마지막 패킷의
# 시작 시각)로 재서, 마지막 프레임 길이와 B프레임 재정렬 몫(약 2프레임)이 빠져 여러 구간을 이은 무음 합성이 0.10초 짧다고 잘못 멈췄다(2026-11-12).
fp = str(Path(ff).with_name('ffprobe' + Path(ff).suffix))
def probe(stream, entry):
    out = subprocess.run([fp, '-v', 'error', '-select_streams', f'{stream}:0', '-count_frames', '-show_entries', f'stream={entry}', '-of', 'csv=p=0', str(mp4)],
                         capture_output=True, text=True, encoding='utf-8', errors='replace').stdout.strip().split(',')
    return out
v_frames = int(probe('v', 'nb_read_frames')[0])
a_rate, a_frames = probe('a', 'sample_rate,nb_read_frames')
a_samples = subprocess.run([ff, '-v', 'error', '-i', str(mp4), '-map', '0:a', '-f', 's16le', '-ac', '1', '-ar', a_rate, '-'], capture_output=True).stdout
for stream, got in (('v', v_frames / 30), ('a', len(a_samples) / 2 / int(a_rate))):
    if abs(got - offset / 1000) > 0.1:
        raise RuntimeError(f'{mp4.name}: {stream} stream {got:.3f}s != segments {offset / 1000:.3f}s')
def stamp(ms):
    ms = round(ms); m, s = divmod(ms, 60000); return f'{m:02}:{s // 1000:02}.{s % 1000:03}'
(dest / '자막.srt').write_text('\n\n'.join(f"{i+1}\n00:{stamp(a['g']).replace('.', ',')} --> 00:{stamp(a['g']+a['duration']).replace('.', ',')}\n{a['text']}" for i, a in enumerate(cues)) + '\n', encoding='utf-8')
rows = []
for i, a in enumerate(cues):
    r = {'id': a['id'], 'speech': [stamp(a['g']), stamp(a['g'] + a['duration'])]}
    if a.get('actionStart') is not None:
        o = a.get('o_act', a['g'] - a['time'])   # 조작 시각: 멈춰 늘린 몫 · 들어낸 몫을 반영한 자리
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
          'motions': motions, 'decode': 'passed', 'voice': '무음(--무음 — 화면 비교용)' if SILENT else '안치윤 (기존 캐시 재사용, 신규 생성 0)',
          'not_verified': ['직접 청취(도구 없음)', '스크롤 조작(이 구간에 없음)', '사용자 재생 확인']}
(dest / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: report[k] for k in ['duration_s', 'speech_cues', 'motion_summary', 'segments']}, ensure_ascii=False, indent=1))
print(json.dumps(clicks))
