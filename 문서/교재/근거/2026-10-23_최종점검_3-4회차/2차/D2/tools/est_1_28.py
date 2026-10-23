import sys,re
def spoken(path):
    t=open(path,encoding='utf-8').read()
    t=t[:t.index('## [SLIDE 29]')]
    out=[]
    for l in t.split('\n'):
        s=l.strip()
        if not s or s.startswith('>') or s.startswith('#') or s.startswith('---') or s.startswith('|'): continue
        out.append(s)
    t=' '.join(out)
    h=len(re.findall(r'[가-힣]',t)); d=len(re.findall(r'[0-9]',t)); e=len(re.findall(r'[A-Za-z]',t))
    return h,d,e,(h+d*1.6+e*0.6)/275
for name,p in zip(('원본','제안본','손질본'),sys.argv[1:]):
    print('%s SLIDE 1~28: 한글 %d 숫자 %d 영문 %d -> %.2f분'%((name,)+spoken(p)))
