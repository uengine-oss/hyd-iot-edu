import sys, re
from pathlib import Path
from pptx import Presentation
def read(p):
    out=[]
    for s in Presentation(p).slides:
        items=sorted((sh.left or 0,sh.top or 0,sh.width or 0,sh.height or 0,sh.text_frame.text if sh.has_text_frame else '') for sh in s.shapes)
        out.append(items)
    return out
T=Path('작업/2026-11-02_1회차-학생가이드-현행화/이론영상_갱신/오프라인/전_사본')
for c in ['통합반/이론_오프라인/01회차','실전반/이론_오프라인/01회차','통합반/이론_오프라인/02회차','실전반/이론_오프라인/02회차']:
    old=next((T/c).glob('*.pptx')); new=next(Path('workspace/강의제작/산출물',c).glob('*.pptx'))
    a=read(old); b=read(new); 
    def key(items): return tuple((i[4]) for i in items if i[4] and not re.fullmatch(r'\d+',i[4].strip()))
    ka=[key(x) for x in a]; kb=[key(x) for x in b]
    sa=set(ka)
    print(c,len(a),'→',len(b))
    print('  옛 판에만 있는 글(장):',[i+1 for i,k in enumerate(ka) if k not in set(kb)])
    print('  새 판에만 있는 글(장):',[i+1 for i,k in enumerate(kb) if k not in sa])
    pos=0
    for i,k in enumerate(kb):
        if k in sa:
            j=ka.index(k)
            pa=[x[:4] for x in a[j] if x[4]]; pb=[x[:4] for x in b[i] if x[4]]
            if sorted(pa)!=sorted(pb): pos+=1; print('  위치 다름: 새',i+1,'옛',j+1)
    print('  위치 다른 장 수',pos)
