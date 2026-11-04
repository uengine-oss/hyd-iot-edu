import re,sys
W=sys.argv[1]
def rows(p):
    out={}
    for l in open(p,encoding='utf8'):
        c=[x.strip() for x in l.strip().strip('|').split('|')]
        if len(c)>=5 and c[0].startswith(('이론','실습','도입','마무리','[')) : out[c[1] if len(c)>1 else c[0]]=c
    return out
for c,n in [('통합반','01'),('통합반','02'),('통합반','03'),('통합반','04'),('실전반','01'),('실전반','02'),('실전반','03'),('실전반','04')]:
    a=rows(f'{W}/기준/구성표_{c}_{n}.md'); b=rows(f'workspace/강의제작/제작도구/구성/{c}/{n}회차/구성표.md')
    print('==',c,n,'행',len(a),len(b))
    for k,x in a.items():
        y=b.get(k)
        if y is None: print(' 없음',k[:50]); continue
        f=lambda s:(re.search(r'[\d.]+',s) or [None])[0]
        print(' ',k[:34].ljust(34),'|'.join(x[2:6]),'→','|'.join(y[2:6]))
