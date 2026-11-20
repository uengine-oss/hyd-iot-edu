"""구간 녹화 실측(화살표를 합성 때 그리는 overlay 녹화). 사용: python measure.py <take>
- 끌기 프레임 공백(drags · max_gap_ms · over_100ms · over_500ms): 끌기(path가 있는 이동) 동안 원본 프레임(sourceTimestamp) 사이의 가장 긴 공백. 끌리는 원이 끊겨 보이는 자리다.
  끌기가 아닌 이동은 화살표를 합성 때 그리고 그동안 화면이 그대로라 원본 프레임이 오지 않으므로 재지 않는다.
- 화살표 이어짐(pointer_teleports · motion_overlaps): 이동의 출발 자리가 앞 이동의 도착 자리(첫 이동은 pointer-start.json)와 다르거나, 앞 이동이 끝나기 5ms 넘게 전에
  다음 이동이 시작하면 합성 화살표가 그 자리에서 튄다. [이동 번호(1부터), 큐 id, 값]으로 적는다. 하나라도 있으면 그 take를 쓰지 않는다.
- 클릭 좌표 오차(click_offset_max_px): 페이지가 받은 mousedown 좌표와 그때 합성기가 그리는 화살표 자리의 차이. clicks_not_received = 페이지가 받은 기록이 없는 누르기의 큐 id
  (쪽을 옮기는 누르기는 받은 기록이 쪽과 함께 사라진다 — 그 밖의 큐가 있으면 그 장면을 본다).
- 발화 · 행동 겹침(commit_after_speech_end), 강조(highlights: 모양별 수 · highlights_open: 끝이 없는 강조 — 0이어야 한다).
- 조작 없는 그림 전체 변화(unexplained_jumps): 이웃한 두 프레임 사이에 그림 영역 화소가 8 % 넘게 바뀌었는데 그 앞 1.5초 · 뒤 0.3초 안에 클릭 · 입력 · 키(commit)가 없는 자리.
  arrows가 그림 맞춤을 다시 해 화면이 한 번에 줄며 옮겨 간 튐(옛 08 10:32 · 10:40)이 여기 걸린다. 하나라도 있으면 그 take를 쓰지 않고 원인을 고친다.
무음 리허설(timing.json mode rehearse)은 프레임이 없어 프레임 항목을 재지 않는다."""
import json, math, sys
from collections import Counter
import numpy as np
from PIL import Image
from common import WORK
take = WORK / sys.argv[1]
t = json.loads((take / 'timing.json').read_text(encoding='utf-8'))
st = json.loads((take / 'end-state.json').read_text(encoding='utf-8'))
ps = json.loads((take / 'pointer-start.json').read_text(encoding='utf-8')) if (take / 'pointer-start.json').exists() else {}
if ps.get('mode') != 'overlay':
    raise SystemExit(f'{sys.argv[1]}: pointer-start.json mode가 overlay가 아니다({ps.get("mode")}) — 화살표를 페이지에 그려 찍은 옛 녹화는 이 실측으로 재지 않는다 (촬영도구/measure.py)')
rehearse = t.get('mode') == 'rehearse'
times = sorted(f['sourceTimestamp'] * 1000 - t['start'] for f in t['frames'])
gaps = []
for m in t['motions']:
    if not m.get('path'):
        continue
    v = [x for x in times if m['start'] <= x <= m['end']]
    gaps.append(round(max(b - a for a, b in zip([m['start']] + v, v + [m['end']]))))
teleports, overlaps, at, free = [], [], (ps['x'], ps['y']), -math.inf
for i, m in enumerate(t['motions'], 1):
    d = math.hypot(m['from']['x'] - at[0], m['from']['y'] - at[1])
    if d > 0.5:
        teleports.append([i, m.get('cue'), round(d, 1)])
    if m['glide'] < free - 5:
        overlaps.append([i, m.get('cue'), round(free - m['glide'])])
    at, free = (m['x'], m['y']), (m['path'][-1][0] if m.get('path') else m['glide'] + m['planned_ms'])
clicks = st['clicks']
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
hs = t.get('highlights') or []
print(json.dumps({'take': sys.argv[1], 'mode': t.get('mode', 'record'), 'pointer_mode': ps['mode'], 'scale': ps.get('scale'), 'duration_s': round(t['duration'] / 1000, 1), 'frames': len(t['frames']),
                  'error': (t['error'] or '')[:160], 'cues': len(t['actions']), 'estimated_voice': [a['id'] for a in t['actions'] if a.get('voice') == 'estimate'],
                  'motions': len(t['motions']), 'drags': len(gaps), 'max_gap_ms': None if rehearse else max(gaps, default=None),
                  'over_100ms': None if rehearse else sum(g >= 100 for g in gaps), 'over_500ms': None if rehearse else sum(g > 500 for g in gaps),
                  'pointer_teleports': teleports, 'motion_overlaps': overlaps,
                  'click_offset_max_px': max(off) if off else None, 'clicks': len(off), 'clicks_not_received': [c.get('cue') for c in clicks if not c.get('received')],
                  'commit_after_speech_end': late, 'highlights': dict(Counter(h['shape'] for h in hs)), 'highlights_open': sum(h.get('end') is None for h in hs),
                  'unexplained_jumps': None if rehearse else jumps}, ensure_ascii=False))
