"""옛 72장 ↔ 새 78장: 장마다 화면 · 노트 · 대본 낭독이 바뀌었는지. python3 …/근거/장별변경.py > …/근거/장별변경.out"""
import re, sys
sys.path.insert(0, '작업/2026-11-04_5-6회차-이론/통합6/근거')
from 재편_내용 import ORDER
W = '작업/2026-11-04_5-6회차-이론/통합6'
def deck(p):
    t = open(p, encoding='utf-8').read(); out = {}
    for m in re.finditer(r'^## SLIDE (\d+) — (.*?)\n### 화면 내용\n(.*?)### 화면 구성', t, re.M | re.S):
        sc = re.sub(r'^- 노트:.*$', '', m.group(3), flags=re.M).strip(); no = re.search(r'^- 노트:(.*)$', m.group(3), re.M)
        out[int(m.group(1))] = (m.group(2), sc, no.group(1) if no else '')
    return out
def scr(files):
    out = {}
    for f in files:
        t = open(f, encoding='utf-8').read() + '\n---\n'
        for m in re.finditer(r'^## \[SLIDE (\d+)(?:~\d+)?\][^\n]*\n(.*?)(?=^---$|^# )', t, re.M | re.S):
            out[int(m.group(1))] = re.sub(r'^>.*$', '', m.group(2), flags=re.M).split()
    return out
F = ['01_이론_재사용가능한업무지침.md', '02_이론_외부도구연결원리.md', '03_이론_연결안전과실습안내.md']
od, nd = deck(W + '/변경전/통합반_06일차.md'), deck('workspace/강의제작/제작도구/온라인/decks/integrated/day06/통합반_06일차.md')
os_, ns = scr([W + '/변경전/' + f for f in F]), scr(['workspace/강의제작/산출물/통합반/이론/06회차/대본/' + f for f in F])
print('| 새 | 옛 | 화면 | 노트 | 대본 낭독 |'); print('|---:|---:|---|---|---|')
for i, (k, key) in enumerate(ORDER, 1):
    if k == 'new':
        print(f'| {i} | 새 장({key}) | 새 | 새 | {"새" if i in ns else "실습 묶음(앞 장에 포함)"} |'); continue
    a, b = od[key], nd[i]
    s = '같음' if (a[0], a[1]) == (b[0], b[1]) else '바뀜'
    n = '같음' if a[2] == b[2] else '바뀜'
    na = '같음' if os_.get(key) == ns.get(i) else '바뀜'
    print(f'| {i} | {key} | {s} | {n} | {na} |')
