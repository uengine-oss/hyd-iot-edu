import sys
lst, orig, new = sys.argv[1:4]
O=open(orig,encoding='utf-8').read(); N=open(new,encoding='utf-8').read()
rows=[l for l in open(lst,encoding='utf-8') if l.startswith('| ') and l.split('|')[1].strip().isdigit()]
bad=0
for r in rows:
    c=[x.strip() for x in r.strip().strip('|').split('|')]
    no,before,after=c[0],c[4],c[5]
    if c[1]!='실전반 01': continue
    okb = before.startswith('(') or before in O
    oka = after.startswith('(') or after in N
    goneb = before.startswith('(') or (before not in N) or (after in before) or before in after
    print(no, 'before_in_orig' if okb else 'BEFORE_MISSING', 'after_in_new' if oka else 'AFTER_MISSING', '' if goneb else 'BEFORE_STILL_IN_NEW')
    bad += (not okb) + (not oka)
print('rows',len(rows),'bad',bad)
