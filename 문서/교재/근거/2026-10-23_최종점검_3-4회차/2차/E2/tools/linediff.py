import sys, difflib
a = open(sys.argv[1], encoding='utf-8').read().split('\n')
b = open(sys.argv[2], encoding='utf-8').read().split('\n')
lo = int(sys.argv[3]) if len(sys.argv) > 3 else 1
sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == 'equal':
        continue
    if j2 < lo and i2 < lo:
        continue
    print(f'=== {tag} A{i1+1}-{i2} B{j1+1}-{j2}')
    for k in range(i1, i2):
        print(f'- A{k+1}: {a[k]}')
    for k in range(j1, j2):
        print(f'+ B{k+1}: {b[k]}')
    print()
