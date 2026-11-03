"""구간 하나 실측(합성 없이) — 포털 실측과 합성기(encode.py)가 이 정의(이동 공백 · 클릭 오차 · 늦은 조작)를 써서 합성기록에 같은 값을 쓰고,
--도구로 다른 도구 take도 잰다. VS Code · Notion · ARROWS의 measure.py 사본과 neo4j lesson_pipeline.py는 아직 자기 정의를 쓴다.
사용: python3 measure.py [--도구 <이름>] <take> [끝 클릭 수]   (기본 도구 = 포털, take = 그 도구 config.json의 work 아래 폴더)
      python3 measure.py --자가시험
  끝 클릭 수: recording-start.json에 clicksBefore(녹화 전에 누른 수)가 없을 때 끝에서 그만큼만 센다(ARROWS 옛 녹화).
  config에 "banner": "notion"이 있으면 Notion 오류 문구 · 업데이트 막대 프레임을 센다(PIL 필요).
출력 키(chain.sh · full.sh가 error · banner_frames · gaps_over_100을 읽는다): segment, pointer_mode, error, duration_s, frames, avg_fps, cues, moves,
  start_delay_max_ms, max_gap_ms, gaps_over_100, click_offset_max_px, clicks, pointer, late_commits, banner_frames, update_banner_frames, end_tab, last_motion, last_frame."""
import json, sys
from pathlib import Path


def frame_times(t):
    """원본 프레임 시각(ms, 녹화 시작 기준) — 받은 순서가 아니라 화면이 만들어진 시각(sourceTimestamp)."""
    st = t.get('start') or 0
    return sorted(f['sourceTimestamp'] * 1000 - st for f in t['frames'])


def motion_gaps(m, times):
    """이동 하나의 (출발 지연 ms | None, 이동 중 최대 프레임 공백 ms). 이동 시작은 화살표가 실제로 출발한 시각(glide, 없으면 start).
    출발 지연 = 시작부터 첫 프레임까지 — 화살표 애니메이션이 출발하기 전이라 화면 변화가 없다(2026-10-23 take-27: 100ms 넘는 공백 7개가 모두 출발 직전).
    끊김 판정은 첫 프레임 이후 이동 끝까지의 프레임 간격으로 한다. 프레임이 하나도 없으면 이동 전체 길이가 공백이다."""
    s, e = m.get('glide', m['start']), m['end']
    v = [x for x in times if s <= x <= e]
    if not v:
        return None, round(e - s)
    return round(v[0] - s), round(max(b - a for a, b in zip(v, v[1:] + [e])))


def click_offsets(clicks):
    """클릭 좌표 오차(px): 보낸 좌표와 페이지 화살표 끝의 차이."""
    return [round(max(abs(c['px'] - c['x']), abs(c['py'] - c['y'])), 1) for c in clicks]


def late_commits(actions):
    """문장이 끝나고 50ms 넘게 지나서 실행된 조작(큐 id)."""
    return [a['id'] for a in actions if a.get('commit') and a['commit'] > a['time'] + a['duration'] + 50]


def recorded_clicks(d, state, last=None):
    """녹화 중 클릭만 — 녹화 전에 누른 것(recording-start.json clicksBefore)은 뺀다."""
    clicks = state.get('clicks', [])
    rs = d / 'recording-start.json'
    before = json.loads(rs.read_text(encoding='utf-8')).get('clicksBefore') if rs.exists() else None
    if before is None:
        before = len(clicks) - last if last is not None else 0
    return clicks[before:]


def banner_frames(d, frames):
    """Notion 화면 막대: 오류 문구(위 오른쪽 빨간 글자 「문제가 발생했습니다 … 다시 시도」)와, 새 버전 배포 뒤 위쪽(y 83~165)에 화면 폭 전체로
    깔리는 연파랑 「최신 버전으로 업데이트」 막대(본문 칸 밖 x 60 · 1850까지 같은 색). 3장마다 하나씩 본다."""
    from PIL import Image
    error = update = 0
    for f in frames[::3]:
        im = Image.open(d / f['file']).convert('RGB')
        small = im.crop((950, 15, 1600, 65)).resize((130, 10))
        error += sum(1 for r, g, b in small.get_flattened_data() if r > 180 and g < 120 and b < 120) >= 3
        update += all(abs(r - 229) < 8 and abs(g - 242) < 8 and abs(b - 251) < 6 for r, g, b in (im.getpixel((x, y)) for x in (60, 1850) for y in (100, 150)))
    return error, update


def measure(d, cfg=None, last=None):
    cfg = cfg or {}
    t = json.loads((d / 'timing.json').read_text(encoding='utf-8'))
    times = frame_times(t)
    pairs = [motion_gaps(m, times) for m in t['motions']]
    starts, gaps = [s for s, _ in pairs if s is not None], [g for _, g in pairs]
    es = json.loads((d / 'end-state.json').read_text(encoding='utf-8')) if (d / 'end-state.json').exists() else {}
    off = click_offsets(recorded_clicks(d, es, last))
    error, update = banner_frames(d, t['frames']) if cfg.get('banner') == 'notion' else (0, 0)
    # pointer=overlay 녹화는 페이지 화살표가 투명이라 이동 중 화면 변화가 없어 원본 프레임이 오지 않는다 — 이때 이동 공백은 화살표 끊김이 아니다(합성 때 그림).
    ps = json.loads((d / 'pointer-start.json').read_text(encoding='utf-8')) if (d / 'pointer-start.json').exists() else {}
    return {'segment': d.name, 'pointer_mode': ps.get('mode', 'page'), 'error': (t['error'] or '')[:300], 'duration_s': round(t['duration'] / 1000, 1),
            'frames': len(times), 'avg_fps': round(len(times) / (t['duration'] / 1000), 1) if t['duration'] else None, 'cues': len(t['actions']), 'moves': len(gaps),
            'start_delay_max_ms': max(starts, default=None), 'max_gap_ms': max(gaps, default=None), 'gaps_over_100': [g for g in gaps if g >= 100],
            'click_offset_max_px': max(off, default=None), 'clicks': len(off), 'pointer': es.get('pointer'), 'late_commits': late_commits(t['actions']),
            'banner_frames': error + update, 'update_banner_frames': update, 'end_tab': es.get('tab'),
            'last_motion': {'x': round(t['motions'][-1]['x'], 1), 'y': round(t['motions'][-1]['y'], 1)} if t['motions'] else None,
            'last_frame': t['frames'][-1]['file'] if t['frames'] else None}


def self_test():
    """합성 timing: 출발 지연 300ms · 이동 중 공백 80ms → max_gap_ms 80, start_delay_max_ms 300. 옛 정의(출발 지연을 공백에 넣음)면 300이 나온다."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / 'take-시험'
        d.mkdir()
        st = 1_000_000.0
        frames = [{'file': f'frames/{i:06}.jpg', 'sourceTimestamp': (st + x) / 1000} for i, x in enumerate([0, 1300, 1380, 1460, 1540, 1620, 1700, 1780, 1860, 1940])]
        motion = {'start': 1000, 'end': 1940, 'x': 10, 'y': 20, 'from': {'x': 0, 'y': 0}, 'planned_ms': 900}
        (d / 'timing.json').write_text(json.dumps({'start': st, 'frames': frames, 'actions': [{'id': 'c1', 'time': 900, 'duration': 1200, 'commit': 2000}],
                                                   'motions': [motion], 'duration': 2500, 'error': None}), encoding='utf-8')
        (d / 'end-state.json').write_text(json.dumps({'clicks': [{'x': 5, 'y': 5, 'px': 5, 'py': 5}, {'x': 10, 'y': 20, 'px': 10.4, 'py': 20}]}), encoding='utf-8')
        (d / 'recording-start.json').write_text(json.dumps({'clicksBefore': 1}), encoding='utf-8')
        r = measure(d)
        want = {'max_gap_ms': 80, 'start_delay_max_ms': 300, 'gaps_over_100': [], 'clicks': 1, 'click_offset_max_px': 0.4, 'late_commits': [], 'banner_frames': 0}
        bad = {k: (r[k], v) for k, v in want.items() if r[k] != v}
        glide = motion_gaps({**motion, 'glide': 1300}, frame_times(json.loads((d / 'timing.json').read_text(encoding='utf-8'))))
        if glide != (0, 80):
            bad['glide'] = (glide, (0, 80))
        # Notion 막대 검사: 빨간 오류 글자 한 장, 연파랑 업데이트 막대 한 장, 깨끗한 화면 한 장 → 2 · 업데이트 1
        from PIL import Image, ImageDraw
        (d / 'frames').mkdir()
        for i in range(10):
            im = Image.new('RGB', (1920, 1080), 'white')
            if i == 0:
                ImageDraw.Draw(im).rectangle((1000, 30, 1100, 50), fill=(220, 40, 40))
            if i == 3:
                ImageDraw.Draw(im).rectangle((0, 83, 1919, 165), fill=(229, 242, 251))
            im.save(d / f'frames/{i:06}.jpg', quality=95)
        r = measure(d, {'banner': 'notion'})
        if (r['banner_frames'], r['update_banner_frames']) != (2, 1):
            bad['banner'] = ((r['banner_frames'], r['update_banner_frames']), (2, 1))
    print(json.dumps({'자가시험': '통과' if not bad else '실패', '어긋남': bad}, ensure_ascii=False))
    return not bad


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--자가시험' in sys.argv:
        sys.exit(0 if self_test() else 1)
    from common import tool
    args = sys.argv[1:]
    name = '포털'
    if '--도구' in args:
        i = args.index('--도구'); name = args[i + 1]; del args[i:i + 2]
    T = tool(name)
    print(json.dumps(measure(T.work / args[0], T.cfg, int(args[1]) if len(args) > 1 else None), ensure_ascii=False))
