import sys
lst, tong = sys.argv[1:3]
T=open(tong,encoding='utf-8').read()
rows=[l for l in open(lst,encoding='utf-8') if l.startswith('| ') and l.split('|')[1].strip().isdigit()]
for r in rows:
    c=[x.strip() for x in r.strip().strip('|').split('|')]
    no,before,basis=c[0],c[4],c[6]
    shared = not basis.startswith('[실전반 전용]')
    cnt = 0 if before.startswith('(') else T.count(before)
    print(no, 'shared' if shared else '실전반전용', 'count_in_통합반=%d'%cnt)
