from helpers import *
import posixpath,ast,subprocess
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
def estimate(s):
 s=re.sub(r'^#.*$|^>.*$|\*\*','',s,flags=re.M);s=re.sub(r'[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)',r'\1',s)
 return (len(re.findall('[가-힣]',s))+1.6*len(re.findall(r'\d',s))+.6*len(re.findall('[A-Za-z]',s)))/275
def blocks(folder):return [b for f in sorted(folder.glob('*_이론_*.md')) for b in re.split(r'(?=^## \[SLIDE )',f.read_text('utf8'),flags=re.M)[1:]]
def say(s):return ' '.join(l.strip().replace('**','') for l in s.splitlines()[1:] if l.strip() and not l.startswith(('#','>','---')))
results=[];edits=json.loads((EV/'finish11-edits.json').read_text('utf8'))
for root,course,kind,day in [(C,'통합반','integrated',11),(D,'실전반','practical',8)]:
 folder=root/f'산출물/교재/대본/{course}_온라인/{day:02}회차';old=EV/'before'/kind/folder.relative_to(root);before=blocks(old);after=blocks(folder)
 assert len(before)==len(after)==59
 changes=[]
 for a,b in zip(before,after):
  expected=say(a)
  for e in edits:
   if str(folder) in e['path'] and '_이론_' in e['path']:expected=expected.replace(e['before'],e['after'])
  assert expected==say(b),a.splitlines()[0]
  if say(a)!=say(b):changes.append(b.splitlines()[0])
 notes=theory_notes(folder);assert len(notes)==64
 ppt=root/f'산출물/교재/PPTX/{course}_온라인/{course}_{day:02}일차.pptx'
 assert json.loads((folder/'구성.json').read_text('utf8'))['pptx_sha256']==sha(ppt)
 with zipfile.ZipFile(ppt) as z,zipfile.ZipFile(EV/'before'/kind/ppt.relative_to(root)) as prev:
  screen=[]
  for name in prev.namelist():
   if name.startswith(('ppt/slides/','ppt/media/','ppt/theme/','ppt/slideLayouts/','ppt/slideMasters/')) and prev.read(name)!=z.read(name):
    if name.startswith('ppt/slides/_rels/'):
     a=E.fromstring(prev.read(name));b=E.fromstring(z.read(name))
     for tree in [a,b]:
      for r in list(tree):
       if r.get('Type').endswith('/notesSlide'):tree.remove(r)
     assert E.tostring(a)==E.tostring(b),name
    else:screen.append(name)
  assert screen==['ppt/slides/slide48.xml'],screen
  for n in range(1,65):
   rel=E.fromstring(z.read(f'ppt/slides/_rels/slide{n}.xml.rels'));target=next(r.get('Target') for r in rel if r.get('Type').endswith('/notesSlide'));nr=E.fromstring(z.read(posixpath.normpath(posixpath.join('ppt/slides',target))))
   assert ''.join(nr.xpath('//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]//a:t/text()',namespaces=ns))==notes[n]
  for name in z.namelist():
   if name.endswith('.rels'):
    rel=E.fromstring(z.read(name));base=posixpath.dirname(posixpath.dirname(name))
    for r in rel:
     if r.get('TargetMode')!='External':assert posixpath.normpath(posixpath.join(base,r.get('Target'))).lstrip('/') in z.namelist(),(name,r.get('Target'))
 labs=[]
 for src in sorted(folder.glob('*_실습_*.md')):
  name=src.stem.split('_실습_')[1];lab=next(p for p in (root/f'산출물/실습/{course}_온라인').glob(f'{day:02}일차_실습*_'+name) if p.is_dir());assert src.read_bytes()==(lab/'강사대본.md').read_bytes()
  files=[f for f in lab.rglob('*') if f.is_file()]
  with zipfile.ZipFile(lab.with_suffix('.zip')) as z:
   assert z.testzip() is None and set(z.namelist())=={f.relative_to(lab).as_posix() for f in files}
   for f in files:assert z.read(f.relative_to(lab).as_posix())==f.read_bytes()
  for link in re.findall('href="([^"]+)"',(lab/'안내.html').read_text('utf8')):assert (lab/html.unescape(link)).exists()
  for f in files:
   if f.suffix=='.py':ast.parse(f.read_text('utf8'))
   if f.suffix=='.json':json.loads(f.read_text('utf8'))
   if f.suffix=='.bpmn':
    tree=E.parse(str(f));ids=tree.xpath('//@id');assert len(ids)==len(set(ids));ids=set(ids)
    for e in tree.iter():
     for attr in ['sourceRef','targetRef','attachedToRef']:
      if e.get(attr):assert e.get(attr) in ids
    mapping=json.loads((f.parent/'mapping.json').read_text('utf8'))
    for key in ['tasks','timers','flows']:assert set(mapping[key])<=ids
  ref=lab/'reference/example_meeting'
  if ref.exists():
   schema=json.loads((ref/'schema.json').read_text('utf8'));graph=json.loads((ref/'graph.json').read_text('utf8'));ids=[n['props']['id'] for n in graph['nodes']];assert len(ids)==len(set(ids))
   assert schema['ns']==graph['ns']
   for n in graph['nodes']:assert n['props']['ns']==graph['ns'] and n['props']['id'].startswith(graph['ns']+':')
   for r in graph['rels']:assert r['a'] in ids or r['b'] in ids
   # 참조 예제의 실제 연결 미정 자리와 사전 수집 결과를 제거하지 않는다.
   mapping=(ref/'mapping.json').read_text('utf8');assert '<내 에이전트 id>' in mapping and '<일정 만들기 결과' in mapping
   assert '완성' in src.read_text('utf8') or '참조' in src.read_text('utf8') or 'reference' in src.read_text('utf8')
  labs.append(dict(file=src.name,before_minutes=estimate((old/src.name).read_text('utf8')),after_minutes=estimate(src.read_text('utf8')),zip_files=len(files)))
 out=EV/f'final-render/{kind}{day:02}';out.mkdir(parents=True,exist_ok=True)
 if '--keep-pdf' not in sys.argv:
  r=subprocess.run(['C:/Program Files/LibreOffice/program/soffice.exe','-env:UserInstallation='+(EV/f'lo-profile-{kind}{day}').as_uri(),'--headless','--convert-to','pdf','--outdir',str(out),str(ppt)],capture_output=True,timeout=120);assert r.returncode==0,(r.stdout,r.stderr)
 pf=out/(ppt.stem+'.pdf');assert len(PdfReader(pf).pages)==64;shutil.copy2(pf,root/f'산출물/교재/PDF/{course}_온라인/{ppt.stem}.pdf');render(pf,out)
 # PDF의 화면 원문은 공백과 줄바꿈을 제외하고 모든 텍스트를 대조한다.
 textchecks=[]
 with zipfile.ZipFile(ppt) as z:
  for n,page in enumerate(PdfReader(pf).pages,1):
   screen=E.fromstring(z.read(f'ppt/slides/slide{n}.xml')).xpath('//a:t/text()',namespaces=ns);actual=re.sub(r'\s+','',page.extract_text());missing=[s for s in screen if re.sub(r'\s+','',s) not in actual];assert not missing,(n,missing)
   textchecks.append(n)
 results.append(dict(course=course,day=day,slides_before=64,slides_after=64,blocks=59,changed_blocks=changes,before_minutes=sum(estimate(say(b)) for b in before),after_minutes=sum(estimate(say(b)) for b in after),labs=labs,deck_pdf_text_pages=textchecks,actual_execution=False))
for c in json.loads((EV/'finish11-copies.json').read_text('utf8')):assert sha(Path(c['source']))==sha(Path(c['destination']))==c['sha256']
for p in Path(__file__).parent.glob('*.py'):ast.parse(p.read_text('utf8'))
write(EV/'finish11-check.json',json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results,ensure_ascii=False))
