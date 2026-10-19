from helpers import *
import posixpath,ast
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
timing={};labchecks=[]
def estimate(s):
 s=re.sub(r'^#.*$|^>.*$|\*\*','',s,flags=re.M);s=re.sub(r'[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)',r'\1',s)
 return (len(re.findall('[가-힣]',s))+1.6*len(re.findall(r'\d',s))+.6*len(re.findall('[A-Za-z]',s)))/275
def blocks(folder):
 return [b for f in sorted(folder.glob('*_이론_*.md')) for b in re.split(r'(?=^## \[SLIDE )',f.read_text('utf8'),flags=re.M)[1:]]
def say(s):return ' '.join(l.strip().replace('**','') for l in s.splitlines()[1:] if l.strip() and not l.startswith(('#','>','---')))
edits=json.loads((EV/'repair06-edits.json').read_text('utf8'))
for root,course,kind,count in [(C,'통합반','integrated',72),(D,'실전반','practical',80)]:
 folder=root/f'산출물/교재/대본/{course}_온라인/06회차';old=EV/'before'/kind/folder.relative_to(root)
 before=blocks(old);after=blocks(folder);assert len(before)==len(after)
 changed=[]
 for a,b in zip(before,after):
  expected=say(a)
  for x in edits:expected=expected.replace(x['before'],x['after'])
  assert expected==say(b),a.splitlines()[0]
  if say(a)!=say(b):changed.append(b.splitlines()[0])
 notes=theory_notes(folder);assert len(notes)==count
 p=root/f'산출물/교재/PPTX/{course}_온라인/{course}_06일차.pptx'
 assert json.loads((folder/'구성.json').read_text('utf8'))['pptx_sha256']==sha(p)
 with zipfile.ZipFile(p) as z:
  for n in range(1,count+1):
   rel=E.fromstring(z.read(f'ppt/slides/_rels/slide{n}.xml.rels'));target=next(r.get('Target') for r in rel if r.get('Type').endswith('/notesSlide'));nr=E.fromstring(z.read(posixpath.normpath(posixpath.join('ppt/slides',target))))
   assert ''.join(nr.xpath('//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]//a:t/text()',namespaces=ns))==notes[n]
  if course=='실전반':
   with zipfile.ZipFile(EV/'before/practical'/p.relative_to(root)) as a:
    changed_screen=[]
    for f in a.namelist():
     if f.startswith(('ppt/slides/','ppt/media/','ppt/theme/','ppt/slideLayouts/','ppt/slideMasters/')) and a.read(f)!=z.read(f):changed_screen.append(f)
    assert changed_screen==['ppt/slides/slide45.xml'],changed_screen
 changedlabs=[]
 for src in sorted(folder.glob('*_실습_*.md')):
  a=(old/src.name).read_text('utf8');b=src.read_text('utf8')
  if a!=b:changedlabs.append(dict(file=src.name,before_minutes=estimate(a),after_minutes=estimate(b)))
  lab=next(p for p in (root/f'산출물/실습/{course}_온라인').glob('06일차_실습*_'+src.stem.split('_실습_')[1]) if p.is_dir())
  assert src.read_bytes()==(lab/'강사대본.md').read_bytes()
  files=[f for f in lab.rglob('*') if f.is_file()]
  with zipfile.ZipFile(lab.with_suffix('.zip')) as z:
   assert z.testzip() is None and set(z.namelist())=={f.relative_to(lab).as_posix() for f in files}
   for f in files:assert z.read(f.relative_to(lab).as_posix())==f.read_bytes()
  for link in re.findall('href="([^"]+)"',(lab/'안내.html').read_text('utf8')):assert (lab/html.unescape(link)).exists()
  labchecks.append(dict(course=course,lab=lab.name,zip_files=len(files)))
 timing[course]=dict(slides=count,blocks=len(after),changed_blocks=changed,before_minutes=sum(estimate(say(b)) for b in before),after_minutes=sum(estimate(say(b)) for b in after),changed_labs=changedlabs)
for p in Path(__file__).parent.glob('*.py'):ast.parse(p.read_text('utf8'))
write(EV/'repair06-check.json',json.dumps(dict(timing=timing,labs=labchecks,practical_changed_screen=[45],actual_execution=False),ensure_ascii=False,indent=2))
print(json.dumps(timing,ensure_ascii=False))
