"""구간 하나 실측(합성 없이): 이동별 최대 프레임 공백, 출발 지연, 클릭 오차, 문장보다 늦은 조작, 막아 낸 늦은 입력 수.
사용: python3 measure.py <구간 이름>   (config.json의 work 아래 폴더)"""
import json, sys
from common import WORK

d = WORK / sys.argv[1]
t = json.loads((d / 'timing.json').read_text(encoding='utf-8')); st = t['start'] or 0
src = sorted(f['sourceTimestamp'] * 1000 - st for f in t['frames'])
# 이동 시작부터 첫 프레임까지는 화살표 애니메이션 출발 전이라 화면 변화가 없다(출발 지연). 끊김 판정은 첫 프레임 이후 이동 중 공백으로 한다.
gaps, starts = [], []
for m in t['motions']:
    v = [x for x in src if m['start'] <= x <= m['end']]
    if not v:
        gaps.append(round(m['end'] - m['start'])); starts.append(None); continue
    starts.append(round(v[0] - m['start']))
    g = [b - a for a, b in zip(v, v[1:] + [m['end']])]
    gaps.append(round(max(g)))
es = json.loads((d / 'end-state.json').read_text(encoding='utf-8')); clicks = es.get('clicks', [])
off = [round(max(abs(c['px'] - c['x']), abs(c['py'] - c['y'])), 1) for c in clicks]
late = [a['id'] for a in t['actions'] if a.get('commit') and a['commit'] > a['time'] + a['duration'] + 50]
fps = round(len(src) / (t['duration'] / 1000), 1) if t['duration'] else None
print(json.dumps({'segment': sys.argv[1], 'error': (t['error'] or '')[:300], 'duration_s': round(t['duration'] / 1000, 1), 'frames': len(src), 'avg_fps': fps,
                  'cues': len(t['actions']), 'moves': len(gaps), 'start_delay_max_ms': max([x for x in starts if x is not None], default=None),
                  'max_gap_ms': max(gaps) if gaps else None, 'gaps_over_100': [g for g in gaps if g >= 100],
                  'click_offset_max_px': max(off) if off else None, 'pointer': es.get('pointer'), 'late_commits': late, 'banner_frames': 0,
                  'end_tab': es.get('tab'), 'last_motion': {'x': round(t['motions'][-1]['x'], 1), 'y': round(t['motions'][-1]['y'], 1)} if t['motions'] else None,
                  'last_frame': t['frames'][-1]['file'] if t['frames'] else None}, ensure_ascii=False))
