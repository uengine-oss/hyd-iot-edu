import re,sys
t=open(sys.argv[1],encoding='utf-8').read()
s={}
for m in re.finditer(r'^\| (\d+)(?:~\d+)? \| (\d+) \|',t,re.M): s[int(m.group(1))]=int(m.group(2))
def r(a,b): return round(sum(v for k,v in s.items() if a<=k<=b)/60,2)
rows=[('도입',1,3),('59행',4,25),('60행',26,45),('61행',46,61),('실습62~66',62,71),('마무리',72,78)] if max(s)>72 else [('도입',1,3),('59행',4,23),('60행',24,43),('61행',44,57),('실습',58,65),('마무리',66,72)]
for n,a,b in rows: print(n,f'{a}~{b}',r(a,b))
print('장 수',len(s))
