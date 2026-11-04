"""통합반 6회차 덱 MD 재편: 변경전/ 원고에서 새 원고를 만든다(옛 72장 → 새 78장).
python3 작업/2026-11-04_5-6회차-이론/통합6/근거/재편_덱.py
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
W = ROOT / '작업/2026-11-04_5-6회차-이론/통합6'
OUT = ROOT / 'workspace/강의제작/제작도구/온라인/decks/integrated/day06/통합반_06일차.md'
sys.path.insert(0, str(W / '근거'))
from 재편_내용 import ORDER, SCREEN_EDITS, TITLE_EDITS, NEW_SLIDES, BASIS, LAYOUT_EDITS, NEW_SCREEN  # noqa: E402

src = (W / '변경전/통합반_06일차.md').read_text(encoding='utf-8')
parts = re.split(r'^(## SLIDE (\d+) — .*)$', src, flags=re.M)
old = {}
for i in range(1, len(parts), 3):
    head, num, body = parts[i], int(parts[i + 1]), parts[i + 2]
    title = head.split(' — ', 1)[1]
    m = re.search(r'### 화면 내용\n(.*?)### 화면 구성\n(.*?)### 제작 기준\n', body, re.S)
    old[num] = dict(title=title, screen=m.group(1), layout=m.group(2))
assert len(old) == 72, len(old)


def rep(text, pairs, where):
    for a, b in pairs:
        n = text.count(a)
        if n != 1:
            raise SystemExit(f'{where}: 「{a[:60]}」 {n}번')
        text = text.replace(a, b)
    return text


out = ['# 업무 지침의 재사용과 외부 시스템 연결\n']
for new_no, (kind, key) in enumerate(ORDER, 1):
    if kind == 'old':
        s = old[key]
        title = TITLE_EDITS.get(key, s['title'])
        screen = NEW_SCREEN[key] if key in NEW_SCREEN else rep(s['screen'], SCREEN_EDITS.get(key, []), f'옛 {key} 화면')
        layout = LAYOUT_EDITS.get(key, s['layout'])
    else:
        n = NEW_SLIDES[key]
        title, screen, layout = n['title'], n['screen'].strip('\n') + '\n', n['layout'].strip('\n') + '\n'
    basis = BASIS[new_no].strip()
    out.append(f'## SLIDE {new_no:02d} — {title}\n### 화면 내용\n{screen.rstrip()}\n### 화면 구성\n{layout.strip()}\n### 제작 기준\n{basis}\n')
OUT.write_text('\n'.join(out), encoding='utf-8')
print(f'{OUT.relative_to(ROOT)} — {len(ORDER)}장')
