"""네 온라인 덱의 장 유형 · 대본 어림 낭독 시간 · 본문 장 수를 낸다(이론영상_갱신/측정.py 본보기). 인자: 출력 json"""
import json, re, sys
from pathlib import Path
R = Path('.').resolve()
sys.path.insert(0, str(R/'workspace/강의제작/제작도구/촬영'))
from 시간계산 import load_coef, script_slides, slide_seconds
W = R/'workspace/강의제작'
DECKS = {
 '통합3': (W/'제작도구/온라인/decks/integrated/day03/통합반_03일차.md', W/'산출물/통합반/이론/03회차/대본'),
 '실전3': (W/'제작도구/온라인/decks/practical/day03/실전반_03일차.md', W/'산출물/실전반/이론/03회차/대본'),
 '통합4': (W/'제작도구/온라인/decks/integrated/day04/통합반_04일차.md', W/'산출물/통합반/이론/04회차/대본'),
 '실전4': (W/'제작도구/온라인/decks/practical/day04/실전반_04일차.md', W/'산출물/실전반/이론/04회차/대본'),
}
EXCL=('표지','목차','간지')
k = load_coef(); out = {}
for name,(md,sd) in DECKS.items():
    t = md.read_text(encoding='utf-8')
    parts = re.split(r'(?m)^## SLIDE (\d+) — (.*)$', t)
    slides = {}
    for i in range(1,len(parts),3):
        n=int(parts[i]); title=parts[i+1].strip(); body=parts[i+2]
        m=re.search(r'(?m)^- 유형:\s*(.+)$',body); ty=m.group(1).strip() if m else ''
        lay=re.search(r'(?m)^레이아웃:\s*(.+)$',body); msg=re.search(r'(?m)^- 메시지:\s*(.+)$',body); fig=re.search(r'(?m)^- 그림:\s*(.+)$',body)
        slides[n]=dict(title=title,type=ty,layout=lay.group(1).strip() if lay else '',msg=msg.group(1).strip() if msg else '',fig=fig.group(1).strip() if fig else '',sec=None,file='')
    cover=set()
    for f in sorted(sd.glob('*.md')):
        for n,(text,share,title) in script_slides(f.read_text(encoding='utf-8')).items():
            s=slide_seconds(text,k)/share if share>1 else slide_seconds(text,k)
            if n in slides: slides[n]['sec']=round(s,1); slides[n]['file']=f.name[:2]
            cover.add(n)
    out[name]=slides
    miss=[n for n in slides if n not in cover]; extra=[n for n in cover if n not in slides]
    tot=sum(v['sec'] or 0 for v in slides.values())
    print(name,len(slides),'장',round(tot/60,1),'분 대본미덮음',miss,'덱에없음',extra)
    print('  2분초과',[(n,v['sec']) for n,v in slides.items() if (v['sec'] or 0)>=120])
    print('  유형분포',{ty:sum(1 for v in slides.values() if v['type']==ty) for ty in sorted({v['type'] for v in slides.values()})})
json.dump(out,open(sys.argv[1],'w',encoding='utf-8'),ensure_ascii=False,indent=0)
