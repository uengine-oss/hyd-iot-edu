"""문서·자료를 정적으로 검사한다. 학생 코드와 테스트를 실행하지 않는다."""
from helpers import *
import ast,posixpath,subprocess
from PIL import ImageChops
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def blocks(folder):return [b for f in sorted(folder.glob('*_이론_*.md')) for b in re.split(r'(?=^## \[SLIDE )',f.read_text('utf8'),flags=re.M)[1:]]
def say(b):return ' '.join(l.strip().replace('**','') for l in b.splitlines()[1:] if l.strip() and not l.startswith(('>','#','---')))
def estimate(t):
 t=re.sub(r'^#.*$|^>.*$|\*\*','',t,flags=re.M);t=re.sub(r'[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)',r'\1',t)
 return (len(re.findall('[가-힣]',t))+1.6*len(re.findall(r'\d',t))+.6*len(re.findall('[A-Za-z]',t)))/275
old=blocks(EV/'before/산출물/교재/대본/통합반_온라인/09회차');now=blocks(I)
assert len(old)==len(now)==70
assert [b.split(']')[0] for b in old]==[b.split(']')[0] for b in now]
edits=json.loads((EV/'speech-edits.json').read_text('utf8'));changed=[]
for a,b in zip(old,now):
 expected=say(a)
 for x in edits:expected=expected.replace(x['before'],x['after'])
 assert expected==say(b),a.splitlines()[0]
 if say(a)!=say(b):changed.append(b.splitlines()[0])
assert len(changed)==5
timing=dict(slides_before=74,slides_after=74,blocks=70,changed_speech_blocks=changed,before_minutes=sum(estimate(say(b)) for b in old),after_minutes=sum(estimate(say(b)) for b in now),wait_seconds=90,syllabus_theory_minutes=85,practice=[dict(file=f.name,before_minutes=0,after_minutes=estimate(f.read_text('utf8'))) for f in sorted(I.glob('*_실습_*.md'))])
timing['delta_seconds']=(timing['after_minutes']-timing['before_minutes'])*60
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
p=C/'산출물/교재/PPTX/통합반_온라인/통합반_09일차.pptx';notes=theory_notes(I);assert sorted(notes)==list(range(1,75))
with zipfile.ZipFile(p) as z,zipfile.ZipFile(EV/'before/산출물/교재/PPTX/통합반_온라인/통합반_09일차.pptx') as oldz:
 assert z.testzip() is None
 assert len([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)])==74
 different=[]
 for name in oldz.namelist():
  if re.fullmatch(r'ppt/slides/slide\d+\.xml',name) or name.startswith(('ppt/media/','ppt/theme/','ppt/slideMasters/','ppt/slideLayouts/')):
   if oldz.read(name)!=z.read(name):different.append(name)
 assert different==['ppt/slides/slide45.xml'],different
 for name in z.namelist():
  if name.endswith('.rels'):
   parent=posixpath.dirname(posixpath.dirname(name))
   for r in E.fromstring(z.read(name)):
    if r.get('TargetMode')=='External':continue
    t=r.get('Target');assert (posixpath.normpath(posixpath.join(parent,t)) if not t.startswith('/') else t[1:]) in z.namelist(),(name,t)
 for n in range(1,75):
  rel=E.fromstring(z.read(f'ppt/slides/_rels/slide{n}.xml.rels'));target=next(r.get('Target') for r in rel if r.get('Type').endswith('/notesSlide'));nr=E.fromstring(z.read(posixpath.normpath(posixpath.join('ppt/slides',target))))
  assert ''.join(nr.xpath('//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]//a:t/text()',namespaces=ns))==notes[n]
assert json.loads((I/'구성.json').read_text('utf8'))['pptx_sha256']==sha(p)
screen=lambda s:re.sub(r'^- 노트:.*$','',s.split('### 화면 구성')[0],flags=re.M).strip()
oldmd=re.split(r'(?=^## SLIDE )',(EV/'before/만들기/decks/integrated/day09/통합반_09일차.md').read_text('utf8'),flags=re.M)[1:]
newmd=re.split(r'(?=^## SLIDE )',(C/'만들기/decks/integrated/day09/통합반_09일차.md').read_text('utf8'),flags=re.M)[1:]
assert len(oldmd)==len(newmd)==74
assert [i for i,(a,b) in enumerate(zip(oldmd,newmd),1) if screen(a)!=screen(b)]==[45]
for ref in re.findall(r'^- 그림: (.+)$',(C/'만들기/decks/integrated/day09/통합반_09일차.md').read_text('utf8'),flags=re.M):assert (C/'만들기/decks/integrated/day09'/ref.strip()).exists()
labs=[];base=C/'산출물/실습/통합반_온라인'
for lab in sorted(base.glob('09일차_실습*')):
 if not lab.is_dir():continue
 files=[f for f in lab.rglob('*') if f.is_file()]
 with zipfile.ZipFile(lab.with_suffix('.zip')) as z:
  assert z.testzip() is None;assert set(z.namelist())=={f.relative_to(lab).as_posix() for f in files}
  for f in files:assert z.read(f.relative_to(lab).as_posix())==f.read_bytes()
 links=re.findall(r'href="([^"]+)"',(lab/'안내.html').read_text('utf8'))
 for link in links:assert (lab/html.unescape(link)).exists(),link
 for f in lab.rglob('*.json'):json.loads(f.read_text('utf-8-sig'))
 if (lab/'reference/cooling-emergency.bpmn').exists():
  xml=E.parse(str(lab/'reference/cooling-emergency.bpmn'));ids=[e.get('id') for e in xml.iter() if e.get('id')];assert len(ids)==len(set(ids))
  for e in xml.iter():
   for k in ['sourceRef','targetRef','attachedToRef','bpmnElement','processRef','default']:
    if e.get(k):assert e.get(k) in ids,(e.tag,k,e.get(k))
   if e.tag.endswith('flowNodeRef'):assert e.text in ids
  mapping=json.loads((lab/'reference/mapping.json').read_text('utf8'))
  for k in ['tasks','flows','timers','lanes']:assert set(mapping[k])<=set(ids)
  timer=next(e for e in xml.iter() if e.get('id')=='B_overdue');assert timer.get('cancelActivity')=='false';assert timer.get('attachedToRef')=='T_approve';assert mapping['timers']['B_overdue']=='PT10M'
 labs.append(dict(path=str(lab),files=len(files),links=len(links),zip_byte_match=True))
assert len(labs)==4
for f in [I/'구성표.md',base/'09회차_실습_안내.md']:
 for ref in re.findall(r'\]\(([^)]+)\)',f.read_text('utf8')):assert (f.parent/ref).exists(),(f,ref)
source=json.loads((EV/'source-materials.json').read_text('utf8'))
for x in source:assert sha(Path(x['source']))==sha(Path(x['destination']))==x['sha256']
for f in Path(__file__).parent.glob('*.py'):ast.parse(f.read_text('utf8'))
oldpdf=EV/'source-render/통합반_09일차.pdf';newpdf=EV/'final-render/통합반_09일차.pdf';a=pdfium.PdfDocument(oldpdf);b=pdfium.PdfDocument(newpdf);assert len(a)==len(b)==74
pixelchanges=[]
for n in range(74):
 if ImageChops.difference(a[n].render(scale=1).to_pil().convert('RGB'),b[n].render(scale=1).to_pil().convert('RGB')).getbbox():pixelchanges.append(n+1)
assert pixelchanges==[45],pixelchanges
aa=PdfReader(oldpdf);bb=PdfReader(newpdf);textchanges=[i for i,(x,y) in enumerate(zip(aa.pages,bb.pages),1) if re.sub(r'\s+','',x.extract_text())!=re.sub(r'\s+','',y.extract_text())];assert textchanges==[45]
preservation={}
for root,kind in [(C,'integrated'),(D,'practical')]:
 hashes=json.loads((EV/f'before-{kind}.json').read_text('utf8'));changed=[];missing=[]
 for path,h in hashes.items():
  f=Path(path)
  if not f.exists():missing.append(path)
  elif sha(f)!=h:changed.append(path)
 def allowed(path):
  rel=Path(path).relative_to(root).as_posix()
  if rel in ['문서/교재/인계_통합반_회차별_점검.md','문서/교재/3_현황.md','문서/교재/4_만드는_법.md','문서/교재/6_남은_일.md']:return True
  if kind=='practical':return rel.startswith('만들기/labs/online/session09/')
  return any(rel.startswith(x) for x in ['산출물/교재/대본/통합반_온라인/09회차/','산출물/교재/대본/통합반_온라인/통합반_09일차','산출물/교재/대본/통합반_온라인/낭독본/통합반_09일차','산출물/교재/PPTX/통합반_온라인/통합반_09일차','산출물/교재/PDF/통합반_온라인/통합반_09일차','산출물/실습/통합반_온라인/09','만들기/decks/integrated/day09/'])
 unexpected=[p for p in changed if not allowed(p)];assert not missing and not unexpected,(missing,unexpected)
 start=json.loads((EV/f'git-start-{kind}.json').read_text('utf8'));head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip();assert head==start['head']
 preservation[kind]=dict(baseline_files=len(hashes),changed_existing_files=len(changed),missing=missing,unexpected=unexpected,changed_paths=changed,head=head)
report=dict(slides=74,blocks=70,notes_exact=74,source_coverage='all 74 slides, all 70 speech blocks, no omissions',changed_screen_slides=[45],unchanged_screen_pixel_pages=73,pdf=json.loads((EV/'pdf-check.json').read_text('utf8')),deck_pdf_pages=74,labs=labs,copied_materials=len(source),preservation=preservation,actual_lab_execution=False,student_code_or_tests_run=False,AI_HYD_DB_browser_capture=False)
write(EV/'timing.json',json.dumps(timing,ensure_ascii=False,indent=2));write(EV/'final-check.json',json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(dict(timing=timing,labs=4,copied=len(source),preservation={k:{a:b for a,b in v.items() if a!='changed_paths'} for k,v in preservation.items()}),ensure_ascii=False))
