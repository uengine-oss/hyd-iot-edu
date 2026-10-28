"""오프라인 덱의 이론 시간을 강사 템포 실측으로 예측한다.

python3 제작용/오프라인/decks/시간.py 제작용/오프라인/decks/*/off0*/*_오프라인_*.md

- 재사용 장: 그 장의 온라인 대본 음절(대본시간.py 산식)을 장 시간 = 1.3초 + 0.1987초 × 음절에 넣는다.
  계수는 other-pc 브랜치의 온라인 이론 영상 시간표(통합 · 실전 1 · 2회차, 강사 복제 음성, 쉼 포함)
  292장의 장별 화면 시간과 현재 대본 음절의 회귀다(분당 약 297음절, 장당 잔차 표준편차 2.5초, 2026-10-28).
- 새로 쓴 장(대본 없음): 노트 음절 × k를 같은 식에 넣는다. k는 재사용 장의 대본 음절 ÷ 노트 음절의 중앙값.
- 강사가 교실에서 실제로 진행한 시간은 아니다(실측과 구분).
"""
import re, sys, glob, statistics
sys.path.insert(0, '제작용/기존제작/tools/deck')
from 대본시간 import syllables
A, B = 1.3, 0.1987
cache = {}
def script(course, day):
    if (course, day) not in cache:
        d = {}
        for f in sorted(glob.glob(f'산출물/{course}/이론/{day:02d}회차/대본/*.md')):
            body = re.split(r"^# (여기까지 작성|촬영 본문 끝)|^## 제작 확인용", open(f, encoding='utf8').read(), flags=re.M)[0]
            p = re.split(r"^## \[SLIDE ([0-9~]+)\](.*)$", body, flags=re.M)
            for i in range(1, len(p), 3):
                a = p[i].split('~'); r = range(int(a[0]), int(a[-1]) + 1)
                for n in r: d[n] = d.get(n, 0) + syllables(p[i + 2]) / len(r)
        cache[(course, day)] = d
    return cache[(course, day)]
def note(b):
    m = re.search(r'^- 노트: (.*)$', b, re.M); return syllables(m.group(1)) if m else 0
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
print(f'대본/노트 음절 비 중앙값 k = {K:.2f} (재사용 장 {len(ratios)}개)')
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
