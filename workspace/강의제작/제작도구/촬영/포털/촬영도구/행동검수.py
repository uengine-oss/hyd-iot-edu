"""행동별 프레임 검수 — 전편을 재생하지 않고 촬영 기록의 행동 시각에서만 화면을 뽑는다. take.mjs 녹화와 encode.py 합성본에 쓴다.
사용: python 행동검수.py <take 이름[:여기까지 쓸 ms]> <영상.mp4>
  이어 찍은 take(이음.json 있음)는 합본(encode.py <출력> <앞>:<잘린ms> <이 take> …)의 시각으로 장면을 뽑는다 — 이음.json을 거슬러 앞 조각 길이를 더한다.
  뒤에 이어 찍은 take가 있어 이 take를 중간에서 잘라 썼으면 encode.py처럼 :<ms>로 쓴 끝을 준다(그 뒤 행동은 보지 않는다).
  클릭: 직전 · 누른 순간 · 결과 세 장. 가리키기: 도착한 순간 한 장. 모음 그림을 눈으로 본다.
  기계 판정(통과 = 그 사실이 확정): 녹화 시작 1회 · 오류 없음 · 커서 경로 연속 · 재조준 수 · 페이지가 받은 클릭 좌표와 커서 도착 좌표 차이.
  화면과 말의 일치 · 가독성 · 자연스러움은 이 도구가 판정하지 않는다. 그림을 보고 사람이 판정한다."""
import json, os, subprocess, sys, time
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding='utf-8')
from common import WORK, ffmpeg

ff = ffmpeg()
T0 = time.time()
name, _, used = sys.argv[1].partition(':')
mp4 = sys.argv[2]
d = WORK / name
t = json.loads((d / 'timing.json').read_text(encoding='utf-8'))
out = d / '행동검수'
seam = json.loads((d / '이음.json').read_text(encoding='utf-8')) if (d / '이음.json').exists() else None


def start_in_join(n):
    """합본에서 그 take가 시작하는 시각(ms) = 이음.json을 거슬러 올라가며 앞 조각을 쓴 길이의 합."""
    f = WORK / n / '이음.json'
    if not f.exists():
        return 0
    s = json.loads(f.read_text(encoding='utf-8'))
    return start_in_join(s['prev']) + s['cut_ms']


OFF = start_in_join(name)
END = float(used) if used else float('inf')   # 이 take에서 합본에 쓴 끝(ms)
t['clicks'] = [c for c in t['clicks'] if c['time'] < END]
t['motions'] = [m for m in t['motions'] if m['start'] < END]
out.mkdir(exist_ok=True)
# 한글 글꼴: Windows는 맑은 고딕, 리눅스는 fontconfig가 고른 한글 글꼴
FONT = 'C:/Windows/Fonts/malgun.ttf' if os.path.exists('C:/Windows/Fonts/malgun.ttf') else subprocess.check_output(['fc-match', '-f', '%{file}', 'Malgun Gothic:lang=ko']).decode()
font = ImageFont.truetype(FONT, 15)
fails = []
if t.get('captures') != 1: fails.append(f"녹화 시작 {t.get('captures')}회")
if t.get('error'): fails.append(f"촬영 오류: {t['error'][:200]}")
motions = t['motions']
for a, b in zip(motions, motions[1:]):
    if abs(a['x'] - b['from']['x']) > 1 or abs(a['y'] - b['from']['y']) > 1:
        fails.append(f"{a['cue']}→{b['cue']}: 커서 순간이동 ({a['x']:.0f},{a['y']:.0f})→({b['from']['x']:.0f},{b['from']['y']:.0f})")
    if b['glide'] < a['glide'] + a['planned_ms'] - 1:
        fails.append(f"{a['cue']}→{b['cue']}: 앞 이동이 끝나기 전에 다음 이동 시작")
offsets = []
for c in t['clicks']:
    if 'page_x' not in c:
        fails.append(f"{c['cue']}: 페이지가 받은 클릭 기록 없음")
        continue
    last = max((m for m in motions if m['start'] <= c['time']), key=lambda m: m['start'], default=None)
    off = max(abs(c['page_x'] - last['x']), abs(c['page_y'] - last['y']))
    offsets.append(round(off, 2))
    if off > 1: fails.append(f"{c['cue']}: 클릭과 커서 차이 {off:.1f}px")
shots = []
for c in t['clicks']:
    for label, dt in (('직전', -400), ('누름', 60), ('결과', 1200)):
        shots.append((c['time'] + dt, f"{c['cue']} 클릭 {label}"))
clicked = {c['time'] for c in t['clicks']}
for m in motions:
    if not any(m['end'] - 100 <= x <= m['end'] + 1500 for x in clicked):
        shots.append((m['end'] + 120, f"{m['cue']} 가리킴"))
shots.sort()
for k in range(0, len(shots), 9):
    sheet = Image.new('RGB', (1920, 1080), 'white')
    draw = ImageDraw.Draw(sheet)
    for j, (ms, cap) in enumerate(shots[k:k + 9]):
        ms += OFF
        raw = subprocess.check_output([ff, '-v', 'error', '-ss', f'{max(0, ms) / 1000:.3f}', '-i', mp4, '-frames:v', '1', '-vf', 'scale=640:360', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        x, y = (j % 3) * 640, (j // 3) * 360
        sheet.paste(Image.frombytes('RGB', (640, 360), raw), (x, y))
        draw.rectangle((x, y, x + 300, y + 20), fill='black')
        draw.text((x + 4, y), f'{int(ms // 60000)}:{ms % 60000 / 1000:05.2f} {cap}', fill='yellow', font=font)
    sheet.save(out / f'행동_{k // 9 + 1:02d}.jpg', quality=85)
report = {'영상초': round(t['duration'] / 1000, 1), '녹화시작': t.get('captures'), '이음새': (1 if seam else 0) if t.get('captures') == 1 else None, '행동장면': len(shots), '모음그림': (len(shots) + 8) // 9,
          '클릭': len(t['clicks']), '클릭차이px최대': max(offsets, default=None), '재조준': len(t.get('retargets', [])), '걸린초': round(time.time() - T0, 1), '실패': fails}
(out / '판정.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
sys.exit(1 if fails else 0)
