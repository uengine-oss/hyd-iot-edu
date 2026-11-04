"""네 온라인 덱의 판본 연결을 잰다(DoD 6 · 7): 원고 · PPTX 장 수, 노트 일치, 대본 [SLIDE] 덮음, 구성.json slide_count · pptx_sha256, 대본 머리 장 범위. 인자: 덱키들(없으면 넷)"""
import hashlib, json, posixpath, re, sys, zipfile
from pathlib import Path
from lxml import etree as E
W=Path('workspace/강의제작')
D={'통합3':('통합반','03','integrated'),'실전3':('실전반','03','practical'),'통합4':('통합반','04','integrated'),'실전4':('실전반','04','practical')}
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
def order(z):
    pres=E.fromstring(z.read('ppt/presentation.xml'))
    rels={r.get('Id'):r.get('Target') for r in E.fromstring(z.read('ppt/_rels/presentation.xml.rels'))}
    return [posixpath.normpath('ppt/'+rels[s.get('{%s}id'%NS['r'])].lstrip('/').replace('ppt/','')) for s in pres.find('p:sldIdLst',NS)]
def note(z,part):
    rp=posixpath.dirname(part)+'/_rels/'+posixpath.basename(part)+'.rels'
    for r in E.fromstring(z.read(rp)):
        if r.get('Type').endswith('/notesSlide'):
            x=E.fromstring(z.read(posixpath.normpath(posixpath.join(posixpath.dirname(part),r.get('Target')))))
            b=x.xpath('.//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]/p:txBody',namespaces=NS)
            return ' '.join(''.join(p.xpath('.//a:t/text()',namespaces=NS)) for p in b[0].findall('a:p',NS)) if b else ''
    return ''
def norm(s): return re.sub(r'\s+',' ',s.replace(' / ',' ').replace('\x0b',' ')).strip()
ok=True
for k in (sys.argv[1:] or D):
    c,n,cp=D[k]
    md=W/f'제작도구/온라인/decks/{cp}/day{n}/{c}_{n}일차.md'; px=W/f'산출물/{c}/이론/{n}회차/{c}_{n}일차.pptx'; sd=W/f'산출물/{c}/이론/{n}회차/대본'; cj=W/f'제작도구/구성/{c}/{n}회차/구성.json'
    t=md.read_text('utf8'); blocks=re.split(r'(?m)^## SLIDE (\d+) — .*$',t); nums=[int(x) for x in blocks[1::2]]
    notes={int(blocks[i]):(re.search(r'(?m)^- 노트: (.*)$',blocks[i+1]) or [0,''])[1] for i in range(1,len(blocks),2)}
    z=zipfile.ZipFile(px); o=order(z); diff=[i+1 for i,p in enumerate(o) if norm(note(z,p))!=norm(notes.get(i+1,''))]
    cover=[]
    heads=[]
    for f in sorted(sd.glob('*.md')):
        s=f.read_text('utf8'); 
        for m in re.finditer(r'(?m)^## \[SLIDE (\d+)(?:~(\d+))?\]',s): cover+=list(range(int(m[1]),int(m[2] or m[1])+1))
        h=re.search(r'\.pptx\)\s*(\d+)\s*[~–-]\s*(\d+)\s*장',s); heads.append((f.name[:2],h[1],h[2]) if h else (f.name[:2],None))
    cfg=json.loads(cj.read_text('utf8')); sha=hashlib.sha256(px.read_bytes()).hexdigest()
    res=dict(원고장=len(nums),번호연속=nums==list(range(1,len(nums)+1)),PPTX장=len(o),노트다른장=diff,대본덮음=cover==list(range(1,len(nums)+1)),구성장수=cfg.get('slide_count'),구성해시일치=cfg.get('pptx_sha256')==sha,대본머리=heads,sha=sha[:12])
    print(k,res)
    ok&=res['원고장']==res['PPTX장']==res['구성장수'] and not diff and res['대본덮음'] and res['구성해시일치'] and res['번호연속']
print('전부 일치' if ok else '어긋남 있음'); sys.exit(0 if ok else 1)
