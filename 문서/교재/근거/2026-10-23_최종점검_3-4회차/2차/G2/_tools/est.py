import re, sys
def est(path, lo, hi):
    lines = open(path, encoding='utf-8').read().split('\n')
    cur = None; total = 0.0
    for l in lines:
        m = re.match(r'^## \[SLIDE ([0-9]+)', l)
        if m: cur = int(m.group(1)); continue
        if cur is None or not (lo <= cur <= hi): continue
        if l.startswith('#') or l.startswith('>') or l.strip() == '---' or l.startswith('|'): continue
        h = len(re.findall(r'[가-힣]', l)); d = len(re.findall(r'[0-9]', l)); e = len(re.findall(r'[A-Za-z]', l))
        total += h + d*1.6 + e*0.6
    return total
for p in sys.argv[1:]:
    t = est(p, 102, 132); print(f'{t:.0f} weighted syllables, {t/275:.2f} min  {p[-40:]}')
