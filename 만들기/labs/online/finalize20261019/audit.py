"""Read-only whole online document audit. Never runs student programs."""
from helpers import *
import posixpath,subprocess,urllib.parse
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
norm=lambda s:re.sub(r'\s+','',s)
results=[];issues=[];pdfs=[];manifest={}
def issue(*a):issues.append(list(map(str,a)))
for root,course,kind,total in [(C,'통합반','integrated',11),(D,'실전반','practical',8)]:
 for day in range(1,total+1):
  folder=root/f'산출물/교재/대본/{course}_온라인/{day:02}회차';cfg=json.loads((folder/'구성.json').read_text('utf8'));notes=theory_notes(folder);count=cfg['slide_count'];coverage=[];labs=[]
  merged=(folder.parent/f'{course}_{day:02}일차_대본.md').read_text('utf8');reading=(folder.parent/f'낭독본/{course}_{day:02}일차_낭독본.md').read_text('utf8')
  for u in cfg['units']:
   f=folder/u['file'];s=f.read_text('utf8')
   if not s.strip():issue('empty',f)
   if u['kind']=='pptx':
    coverage.extend(range(u['slides'][0],u['slides'][1]+1))
    for b in re.split(r'(?=^## \[SLIDE )',s,flags=re.M)[1:]:
     if b.strip() not in merged:issue('merged',f,b.splitlines()[0])
     spoken=norm(' '.join(l.strip().replace('**','') for l in b.splitlines()[1:] if l.strip() and not l.startswith(('#','>','---'))))
     if spoken not in norm(reading):issue('reading',f,b.splitlines()[0])
   elif u['kind']=='practice':labs.append(f)
   else:issue('unfinished_kind',f,u['kind'])
  if coverage!=list(range(1,count+1)) or len(notes)!=count:issue('coverage',folder)
  ppt=root/f'산출물/교재/PPTX/{course}_온라인/{course}_{day:02}일차.pptx';pf=root/f'산출물/교재/PDF/{course}_온라인/{course}_{day:02}일차.pdf'
  if cfg.get('pptx_sha256') and cfg['pptx_sha256']!=sha(ppt):issue('pptx_hash',folder)
  if not pf.exists() and ppt.with_suffix('.pdf').exists():pf=ppt.with_suffix('.pdf')
  reader=PdfReader(pf) if pf.exists() else None
  if reader is None:issue('deck_pdf_missing',pf)
  elif len(reader.pages)!=count:issue('deck_pages',pf)
  with zipfile.ZipFile(ppt) as z:
   for n in range(1,count+1):
    rp=f'ppt/slides/_rels/slide{n}.xml.rels';rels=E.fromstring(z.read(rp));targets=[r.get('Target') for r in rels if r.get('Type').endswith('/notesSlide')]
    if not targets:issue('missing_note',ppt,n);continue
    nr=E.fromstring(z.read(posixpath.normpath(posixpath.join('ppt/slides',targets[0]))));actual=''.join(nr.xpath('//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]//a:t/text()',namespaces=ns))
    if norm(actual)!=norm(notes[n]):issue('note',ppt,n)
    if reader is None:continue
    screen=E.fromstring(z.read(f'ppt/slides/slide{n}.xml')).xpath('//a:t/text()',namespaces=ns);text=norm(reader.pages[n-1].extract_text())
    missing=[s for s in screen if norm(s) not in text]
    if missing:issue('deck_pdf_text',pf,n,missing)
  labbase=root/f'산출물/실습/{course}_온라인'
  guide=(labbase/f'{day:02}회차_실습_안내.md').read_text('utf8')
  labdirs=[p for p in labbase.glob(f'{day:02}일차_실습*') if p.is_dir() and p.name in guide]
  if len(labdirs)!=len(labs):issue('lab_count',folder,len(labs),len(labdirs))
  zfiles=0;links=0
  for lab in labdirs:
   fs={f.relative_to(lab).as_posix():f for f in lab.rglob('*') if f.is_file()};zp=lab.with_suffix('.zip')
   if not zp.exists():zp=labbase/'다운로드'/(lab.name+'.zip')
   if not zp.exists():issue('zip_missing',lab);continue
   with zipfile.ZipFile(zp) as z:
    entries={n for n in z.namelist() if not n.endswith('/')}
    # Early ZIPs put the lab folder itself at the root.
    prefix=lab.name+'/' if entries and all(n.startswith(lab.name+'/') for n in entries) else ''
    logical={n[len(prefix):]:n for n in entries}
    if set(logical)!=set(fs):issue('zip_list',zp,sorted(set(logical)^set(fs)))
    for name in set(logical)&set(fs):
     if z.read(logical[name])!=fs[name].read_bytes():issue('zip_bytes',zp,name)
    zfiles+=len(entries)
   for h in lab.glob('*.html'):
    for link in re.findall(r'(?:href|src)=[\"\x27]([^\"\x27]+)',h.read_text('utf8')):
     link=html.unescape(link)
     if link.startswith(('#','http:','https:','data:','mailto:','javascript:')):continue
     target=(h.parent/urllib.parse.unquote(link.split('#')[0].split('?')[0]))
     if not target.exists():issue('html_link',h,link)
     links+=1
   if (lab/'강사대본.md').exists():
    matches=[f for f in labs if f.stem.split('_실습_')[-1]==lab.name.split('_',2)[-1]]
    if matches and matches[0].read_text('utf8')!=(lab/'강사대본.md').read_text('utf8'):issue('lab_script',lab)
  paths=list(folder.rglob('*'))+list((root/f'만들기/decks/{kind}/day{day:02}').rglob('*'))+[ppt,pf]+list(folder.parent.glob(f'{course}_{day:02}일차*'))+list((folder.parent/'낭독본').glob(f'{course}_{day:02}일차*'))
  paths+=[labbase/f'{day:02}회차_실습_안내.md']+list((folder.parent/'PDF').glob(f'{course}_{day:02}일차*'))
  for lab in labdirs:paths+=list(lab.rglob('*'))+[lab.with_suffix('.zip'),labbase/'다운로드'/(lab.name+'.zip')]
  for p in paths:
   if p.is_file():
    manifest[str(p)]=sha(p)
    if p.suffix=='.pdf' and str(p) not in {x['file'] for x in pdfs}:pdfs.append(dict(file=str(p),pages=len(PdfReader(p).pages),sha256=sha(p)))
  results.append(dict(course=course,day=day,slides=count,labs=len(labs),zip_files=zfiles,html_links=links))
  print(course,day,'checked',flush=True)
write(EV/'whole-audit.json',json.dumps(dict(sessions=results,issues=issues,pdfs=pdfs),ensure_ascii=False,indent=2));write(EV/'whole-artifacts.json',json.dumps(manifest,ensure_ascii=False,indent=2))
print(json.dumps(dict(sessions=len(results),slides=sum(r['slides'] for r in results),labs=sum(r['labs'] for r in results),artifacts=len(manifest),pdfs=len(pdfs),pages=sum(x['pages'] for x in pdfs),issues=issues),ensure_ascii=False))
