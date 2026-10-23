import sys,re
def spoken(path,a,b):
    L=open(path,encoding='utf-8').read().split('\n')[a-1:b]
    out=[]
    for l in L:
        s=l.strip()
        if not s or s.startswith('>') or s.startswith('#') or s.startswith('---') or s.startswith('|'): continue
        out.append(s)
    t=' '.join(out)
    h=len(re.findall(r'[가-힣]',t)); d=len(re.findall(r'[0-9]',t)); e=len(re.findall(r'[A-Za-z]',t))
    return h,d,e,(h+d*1.6+e*0.6)/275
o=spoken(sys.argv[1],481,986); n=spoken(sys.argv[2],481,990)
print('orig 29~59: hangul %d digits %d latin %d  -> %.2f min'%o)
print('new  29~59: hangul %d digits %d latin %d  -> %.2f min'%n)
print('delta %.2f min (%+d hangul)'%(n[3]-o[3], n[0]-o[0]))
