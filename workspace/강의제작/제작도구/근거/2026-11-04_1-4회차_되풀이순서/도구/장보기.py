import glob,re,sys
DK={'통합반':'integrated','실전반':'practical'}
def show(c,n,s,lim=330):
    t=open(f'workspace/강의제작/제작도구/온라인/decks/{DK[c]}/day{n}/{c}_{n}일차.md',encoding='utf8').read()
    b=re.search(rf'^## SLIDE 0*{s} — .*?(?=^## SLIDE |\Z)',t,re.M|re.S).group(0)
    print(f'[{c} {n} 장{s}]',b.split('\n')[0][9:60]); print(' 요소:',' / '.join(x.strip()[:42] for x in re.findall(r'^\s+\d+\. .*$',b,re.M))[:300])
    print(' 짚을곳:',(re.search(r'\[짚을 곳\] (.*?) / ',b) or [0,''])[1][:150])
    for p in sorted(glob.glob(f'workspace/강의제작/산출물/{c}/이론/{n}회차/대본/*.md')):
        x=open(p,encoding='utf8').read(); m=re.search(rf'^## \[SLIDE 0*{s}(?:~\d+)?\].*?(?=^#|\Z)',x,re.M|re.S)
        if m:
            for l in m.group(0).split('\n')[1:]:
                if l.strip() and not l.startswith(('>','-')): print('  ',l.strip()[:lim])
for a in sys.argv[1:]:
    c,n,s=a.split(':'); show(c,n,int(s))
