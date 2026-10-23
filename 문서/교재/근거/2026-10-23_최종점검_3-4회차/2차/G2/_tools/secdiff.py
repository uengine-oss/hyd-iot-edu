import sys, re, difflib
def sections(path):
    txt = open(path, encoding='utf-8').read().split('\n')
    secs = {}; order=[]; cur='HEAD'; secs[cur]=[]; order.append(cur)
    for line in txt:
        m = re.match(r'^## \[SLIDE ([0-9~]+)\]', line)
        if m:
            cur = m.group(1); secs[cur]=[]; order.append(cur)
        secs[cur].append(line)
    return secs, order
a, ao = sections(sys.argv[1]); b, bo = sections(sys.argv[2])
lo = int(sys.argv[3]) if len(sys.argv)>3 else 0
hi = int(sys.argv[4]) if len(sys.argv)>4 else 9999
def num(k):
    try: return int(k.split('~')[0])
    except: return -1
for k in bo:
    if not (lo <= num(k) <= hi): continue
    if k not in a:
        print(f'=== SLIDE {k}: NEW SECTION'); continue
    if a[k] == b[k]:
        print(f'=== SLIDE {k}: same'); continue
    print(f'=== SLIDE {k}: CHANGED')
    sm = difflib.SequenceMatcher(None, a[k], b[k])
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal': continue
        for l in a[k][i1:i2]: print('  - ' + l)
        for l in b[k][j1:j2]: print('  + ' + l)
for k in ao:
    if lo <= num(k) <= hi and k not in b: print(f'=== SLIDE {k}: REMOVED')
