import glob,os,re
def body(p):
    t=open(p,encoding='utf8',newline='').read().replace('\r\n','\n')
    t=t[t.index('## [SLIDE'):t.index('# 촬영 본문 끝')]
    return [l for l in t.split('\n') if l.strip() and not l.startswith(('#','>')) and l.strip()!='---']
for a in sorted(glob.glob('workspace/강의제작/산출물/통합반/이론/01회차/대본/*.md')):
    b=a.replace('통합반','실전반'); x,y=body(a),body(b)
    print(os.path.basename(a),'낭독 같음' if x==y else f'낭독 다름 {len(x)} {len(y)}')
    if x!=y:
        for i,(l,m) in enumerate(zip(x,y)):
            if l!=m: print(' ',i,l[:90],'|',m[:90]); break
