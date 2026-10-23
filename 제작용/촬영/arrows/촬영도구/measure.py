"""구간 녹화 실측: 이동별 최대 프레임 공백(원본 sourceTimestamp), 클릭 좌표 오차, 발화·행동 겹침. 사용: python measure.py <take>"""
import json, sys
from pathlib import Path
from common import WORK
t = json.loads((WORK / sys.argv[1] / 'timing.json').read_text(encoding='utf-8'))
st = json.loads((WORK / sys.argv[1] / 'end-state.json').read_text(encoding='utf-8'))
times = sorted(f['sourceTimestamp'] * 1000 - t['start'] for f in t['frames'])
gaps = []
for m in t['motions']:
    v = [x for x in times if m['start'] <= x <= m['end']]
    g = [b - a for a, b in zip([m['start']] + v, v + [m['end']])]
    gaps.append(round(max(g)))
rs = json.loads((WORK / sys.argv[1] / 'recording-start.json').read_text(encoding='utf-8'))
clicks = st['clicks'][rs.get('clicksBefore', len(st['clicks']) - int(sys.argv[2]) if len(sys.argv) > 2 else 0):]
off = [round(max(abs(c['px'] - c['x']), abs(c['py'] - c['y'])), 2) for c in clicks]
late = [a['id'] for a in t['actions'] if a.get('commit') and a['commit'] > a['time'] + a['duration'] + 50]
print(json.dumps({'take': sys.argv[1], 'duration_s': round(t['duration'] / 1000, 1), 'frames': len(t['frames']), 'error': (t['error'] or '')[:120],
                  'motions': len(gaps), 'max_gap_ms': max(gaps) if gaps else None, 'over_100ms': sum(g >= 100 for g in gaps),
                  'click_offset_max_px': max(off) if off else None, 'clicks': len(off), 'commit_after_speech_end': late}, ensure_ascii=False))
