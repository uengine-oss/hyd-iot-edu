import sys, re
from pptx import Presentation
def read(p):
    out=[]
    for s in Presentation(p).slides:
        items=sorted((sh.left or 0,sh.top or 0,sh.width or 0,sh.height or 0,sh.text_frame.text if sh.has_text_frame else '') for sh in s.shapes)
        out.append(items)
    return out
old,new=sys.argv[1],sys.argv[2]
a=read(old); b=read(new)
def key(items): return tuple(i[4] for i in items if i[4] and not re.fullmatch(r'\d+',i[4].strip()))
def title(items): 
    t=[i[4] for i in items if i[4]]; return t[0][:30] if t else ''
ka=[key(x) for x in a]; kb=[key(x) for x in b]
print(len(a),'→',len(b))
print('옛 판에만 있는 화면(장):',[(i+1,title(a[i])) for i,k in enumerate(ka) if k not in set(kb)])
print('새 판에만 있는 화면(장):',[i+1 for i,k in enumerate(kb) if k not in set(ka)])
for i,k in enumerate(kb):
    if k in set(ka):
        j=ka.index(k)
        pa=sorted(x[:4] for x in a[j] if x[4] and not re.fullmatch(r'\d+',x[4].strip())); pb=sorted(x[:4] for x in b[i] if x[4] and not re.fullmatch(r'\d+',x[4].strip()))
        print(f'  같은 화면: 새 {i+1} = 옛 {j+1}', '위치 같음' if pa==pb else '위치 다름')
