"""구간 녹화 실측: 이동별 최대 프레임 공백(원본 sourceTimestamp), 클릭 좌표 오차, 발화·행동 겹침, 조작 없는 그림 전체 변화. 사용: python measure.py <take>
조작 없는 그림 전체 변화(unexplained_jumps): 이웃한 두 프레임 사이에 그림 영역 화소가 8 % 넘게 바뀌었는데 그 앞 1.5초 · 뒤 0.3초 안에 클릭 · 입력 · 키(commit)가 없는 자리.
arrows가 그림 맞춤을 다시 해 화면이 한 번에 줄며 옮겨 간 튐(옛 08 10:32 · 10:40)이 여기 걸린다. 하나라도 있으면 그 take를 쓰지 않고 원인을 고친다."""
import json, sys
import numpy as np
from PIL import Image
from common import WORK
take = WORK / sys.argv[1]
t = json.loads((take / 'timing.json').read_text(encoding='utf-8'))
st = json.loads((take / 'end-state.json').read_text(encoding='utf-8'))
times = sorted(f['sourceTimestamp'] * 1000 - t['start'] for f in t['frames'])
gaps = []
for m in t['motions']:
    v = [x for x in times if m['start'] <= x <= m['end']]
    g = [b - a for a, b in zip([m['start']] + v, v + [m['end']])]
    gaps.append(round(max(g)))
rs = json.loads((take / 'recording-start.json').read_text(encoding='utf-8'))
clicks = st['clicks'][rs.get('clicksBefore', len(st['clicks']) - int(sys.argv[2]) if len(sys.argv) > 2 else 0):]
off = [round(max(abs(c['px'] - c['x']), abs(c['py'] - c['y'])), 2) for c in clicks]
late = [a['id'] for a in t['actions'] if a.get('commit') and a['commit'] > a['time'] + a['duration'] + 50]
commits = [a['commit'] for a in t['actions'] if a.get('commit') is not None]
jumps, prev = [], None
for f in sorted(t['frames'], key=lambda f: f['sourceTimestamp']):
    tm = f['sourceTimestamp'] * 1000 - t['start']
    cur = np.asarray(Image.open(take / f['file']).convert('L').crop((0, 60, 1380, 1040)).resize((345, 245))).astype(int)
    if prev is not None:
        ch = float((np.abs(cur - prev) > 40).mean()) * 100
        if ch > 8 and not any(-1500 <= tm - c <= 300 for c in commits):
            jumps.append([round(tm), round(ch, 1)])
    prev = cur
print(json.dumps({'take': sys.argv[1], 'duration_s': round(t['duration'] / 1000, 1), 'frames': len(t['frames']), 'error': (t['error'] or '')[:120],
                  'motions': len(gaps), 'max_gap_ms': max(gaps) if gaps else None, 'over_100ms': sum(g >= 100 for g in gaps), 'over_500ms': sum(g > 500 for g in gaps),
                  'click_offset_max_px': max(off) if off else None, 'clicks': len(off), 'commit_after_speech_end': late,
                  'unexplained_jumps': jumps}, ensure_ascii=False))
