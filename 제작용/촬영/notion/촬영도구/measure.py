"""구간 하나 실측(합성 없이): 이동별 최대 프레임 공백, 클릭 오차, 문장보다 늦은 조작, Notion 오류 문구 프레임.
사용: python measure.py <구간 이름>   (config.json의 work 아래 폴더)"""
import json, sys
from PIL import Image
from common import WORK

d = WORK / sys.argv[1]
t = json.loads((d / 'timing.json').read_text(encoding='utf-8')); st = t['start'] or 0
src = sorted(f['sourceTimestamp'] * 1000 - st for f in t['frames'])
# 이동 시작(m.start)부터 첫 프레임까지는 화살표 애니메이션이 출발하기 전이라 화면 변화가 없다(출발 지연). 끊김 판정은
# 첫 프레임 이후 이동 중 공백으로 하고, 출발 지연은 따로 기록한다(2026-10-23 take-27: 100ms 넘는 공백 7개가 모두 출발 직전).
gaps, starts = [], []
for m in t['motions']:
    v = [x for x in src if m['start'] <= x <= m['end']]
    if not v:
        gaps.append(round(m['end'] - m['start'])); starts.append(None); continue
    starts.append(round(v[0] - m['start']))
    g = [b - a for a, b in zip(v, v[1:] + [m['end']])]
    gaps.append(round(max(g)))
es = json.loads((d / 'end-state.json').read_text(encoding='utf-8')); clicks = es['clicks']
# pointer.applied: 녹화 중 실제 입력이 화살표를 옮긴 횟수(이동은 모두 애니메이션이므로 0이어야 함). heldAfterFinish: 막아 낸 늦은 입력 수.
off = [round(max(abs(c['px'] - c['x']), abs(c['py'] - c['y'])), 1) for c in clicks]
late = [a['id'] for a in t['actions'] if a.get('commit') and a['commit'] > a['time'] + a['duration'] + 50]
# Notion 오류 문구("문제가 발생했습니다 … 다시 시도")는 화면 위 오른쪽의 빨간 글자로 나온다.
banner = 0
for f in t['frames'][::3]:
    im = Image.open(d / f['file']).crop((950, 15, 1600, 65)).convert('RGB').resize((130, 10))
    banner += sum(1 for r, g, b in im.get_flattened_data() if r > 180 and g < 120 and b < 120) >= 3
print(json.dumps({'segment': sys.argv[1], 'error': (t['error'] or '')[:300], 'duration_s': round(t['duration'] / 1000, 1), 'cues': len(t['actions']),
                  'moves': len(gaps), 'start_delay_max_ms': max([x for x in starts if x is not None], default=None), 'max_gap_ms': max(gaps) if gaps else None, 'gaps_over_100': [g for g in gaps if g >= 100],
                  'click_offset_max_px': max(off) if off else None, 'pointer': es.get('pointer'), 'late_commits': late, 'banner_frames': banner,
                  'last_motion': {'x': round(t['motions'][-1]['x'], 1), 'y': round(t['motions'][-1]['y'], 1)} if t['motions'] else None,
                  'last_frame': t['frames'][-1]['file'] if t['frames'] else None}, ensure_ascii=False))
