"""이어 찍은 자리의 화면이 같은지 잰다. 사용: python 이음새검수.py <이어 찍은 take 이름>
앞 take의 잘린 지점 마지막 프레임과 이어 찍은 take의 첫 프레임을 화소로 비교한다(녹화 프레임에는 커서가 없다). 나란히 그림을 남긴다.
통과 = 두 프레임이 같은 화면이다(값이 12 넘게 바뀐 화소 0.5 % 이하). 실패면 그 큐보다 앞에서 다시 잇거나 그 구간을 다시 찍는다.
행동이 잘렸는지는 앞 take가 말이 없는 큐 경계에서 끝나는 것으로 막고(take.mjs), 이 도구는 화면 상태만 판정한다."""
import json, sys
from PIL import Image, ImageChops
sys.stdout.reconfigure(encoding='utf-8')
from common import WORK

name = sys.argv[1]
s = json.loads((WORK / name / '이음.json').read_text(encoding='utf-8'))
prev = json.loads((WORK / s['prev'] / 'timing.json').read_text(encoding='utf-8'))
cur = json.loads((WORK / name / 'timing.json').read_text(encoding='utf-8'))
fr = sorted(prev['frames'], key=lambda f: f['sourceTimestamp'])
before = [f for f in fr if f['sourceTimestamp'] * 1000 - prev['start'] < s['cut_ms']]
if not before:
    raise SystemExit(f"{s['prev']}: 잘린 지점 앞 프레임 없음")
after = min(cur['frames'], key=lambda f: f['sourceTimestamp'])
a = Image.open(WORK / s['prev'] / before[-1]['file']).convert('RGB')
b = Image.open(WORK / name / after['file']).convert('RGB')
diff = ImageChops.difference(a, b).convert('L').point(lambda v: 255 if v > 12 else 0)
changed = diff.histogram()[255] / (diff.width * diff.height) * 100
sheet = Image.new('RGB', (1920, 540), 'white')
sheet.paste(a.resize((960, 540)), (0, 0))
sheet.paste(b.resize((960, 540)), (960, 0))
sheet.save(WORK / name / '이음새.jpg', quality=88)
report = {'앞take': s['prev'], '잘린ms': s['cut_ms'], '이어찍은큐': s['fromCue'], '바뀐화소퍼센트': round(changed, 3), '바뀐영역': diff.getbbox(), '판정': '같은 화면' if changed <= 0.5 else '다른 화면'}
(WORK / name / '이음새.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
print(f"합성: python encode.py <출력> {s['prev']}:{s['cut_ms']} {name}")
sys.exit(0 if changed <= 0.5 else 1)
