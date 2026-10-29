"""실전반 덱 장마다, 비교할 통합반 덱에서 가장 닮은 화면과의 글 닮음(0~1)을 잰다.

    python3 workspace/강의제작/제작도구/기존제작/tools/deck/닮음.py <덱.md> --ref <통합반 덱.md> [<통합반 덱.md> ...] [--slides 2 7 11]

- 화면 글은 `### 화면 내용`에서 `- 노트:` 줄을 뺀 것이다. difflib 닮음 비율이며 0.6 미만을 「통과」로 적는다.
"""
import argparse, re
from difflib import SequenceMatcher


def screens(p):
    t = open(p, encoding='utf-8').read()
    res = {}
    for blk in re.split(r'(?m)^(?=## SLIDE )', t):
        m = re.match(r'## SLIDE (\d+) — (.*)', blk)
        if not m:
            continue
        k = blk.find('### 화면 구성')
        sc = blk[:k] if k > 0 else blk
        sc = '\n'.join(l for l in sc.splitlines() if not l.startswith('- 노트') and not l.startswith('### '))
        res[int(m.group(1))] = re.sub(r'\s+', ' ', sc.split('\n', 1)[1] if '\n' in sc else '').strip()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('deck')
    ap.add_argument('--ref', nargs='+', required=True)
    ap.add_argument('--slides', nargs='*', type=int)
    a = ap.parse_args()
    ref = [v for p in a.ref for v in screens(p).values()]
    new = screens(a.deck)
    want = set(a.slides) if a.slides else set(new)
    for n in sorted(want & set(new)):
        r = max(SequenceMatcher(None, new[n], w, autojunk=False).ratio() for w in ref)
        print(n, f'{r:.2f}', '통과' if r < 0.6 else '닮음')


if __name__ == '__main__':
    main()
