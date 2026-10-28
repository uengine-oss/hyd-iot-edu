"""오프라인 덱의 이론 시간을 강사 템포 실측으로 예측한다.

python3 제작용/오프라인/decks/시간.py 제작용/오프라인/decks/*/off0*/*_오프라인_*.md

- 재사용 장: 그 장의 온라인 대본 말 길이를 장 시간 = scale · 말 길이 + per_slide에 넣는다.
  계수는 제작용/촬영/시간계수.json 하나다(실제 강사 복제 음성으로 맞춤 — 시간계산.py calibrate · calibrate-lecture).
- 새로 쓴 장(대본 없음): 노트 말 길이 × k를 같은 식에 넣는다. k는 재사용 장의 대본 말 길이 ÷ 노트 말 길이의 중앙값.
- 강사가 교실에서 실제로 진행한 시간은 아니다(실측과 구분).
"""
import re, sys, glob, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '촬영'))
from 시간계산 import load_coef, speech_seconds
COEF = load_coef()
if 'lecture' not in COEF:
    raise SystemExit('시간계수.json에 이론 장 계수(lecture)가 없다. 시간계산.py calibrate-lecture를 먼저 실행한다.')
A, B = COEF['lecture']['per_slide'], COEF['lecture']['scale']
def 말길이(text):  # 초
    return speech_seconds(text, COEF)
cache = {}
def script(course, day):
    if (course, day) not in cache:
        d = {}
        for f in sorted(glob.glob(f'산출물/{course}/이론/{day:02d}회차/대본/*.md')):
            body = re.split(r"^# (여기까지 작성|촬영 본문 끝)|^## 제작 확인용", open(f, encoding='utf8').read(), flags=re.M)[0]
            p = re.split(r"^## \[SLIDE ([0-9~]+)\](.*)$", body, flags=re.M)
            for i in range(1, len(p), 3):
                a = p[i].split('~'); r = range(int(a[0]), int(a[-1]) + 1)
                for n in r: d[n] = d.get(n, 0) + 말길이(p[i + 2]) / len(r)
        cache[(course, day)] = d
    return cache[(course, day)]
def note(b):
    m = re.search(r'^- 노트: (.*)$', b, re.M); return 말길이(m.group(1)) if m else 0
def slides(md):
    out = []
    for b in re.split(r'(?=^## SLIDE )', open(md, encoding='utf8').read(), flags=re.M)[1:]:
        m = re.search(r'\[출처\] 온라인 (\S+) (\d+)회차 (\d+)장', b)
        t = re.match(r'## SLIDE (\d+) — (.*)', b)
        out.append((int(t.group(1)), t.group(2), (m.group(1), int(m.group(2)), int(m.group(3))) if m else None, note(b)))
    return out
mds = [m for m in sys.argv[1:] if not m.endswith('새장.md')]
ratios = []
# k는 덱 하나만 재도 같은 값이 되도록 오프라인 덱 전체의 재사용 장으로 정한다.
ALL = sorted(glob.glob(str(__import__('pathlib').Path(__file__).resolve().parent / '*/off*/*_오프라인_*회차.md')))
for md in ALL:
    for n, t, src, ns in slides(md):
        if src and ns:
            d = script(src[0], src[1]).get(src[2])
            if d: ratios.append(d / ns)
K = statistics.median(ratios)
print(f'대본/노트 말 길이 비 중앙값 k = {K:.2f} (재사용 장 {len(ratios)}개)')
for md in mds:
    tot = new = 0
    for n, t, src, ns in slides(md):
        if src:
            s = script(src[0], src[1]).get(src[2])
            sec = A + B * s if s is not None else A + B * ns * K
        else:
            sec = A + B * ns * K; new += sec
        tot += sec
    print(f'{md.split("/")[-1]}: {tot/60:.1f}분 (새 장 {new/60:.1f}분)')
