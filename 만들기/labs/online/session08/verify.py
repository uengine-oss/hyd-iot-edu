"""문서와 자료의 정적 검증. 학생 코드와 테스트 모듈은 import/실행하지 않는다."""
from helpers import *
import ast,posixpath,csv
from PIL import ImageChops
def theory(folder):return [b for f in sorted(folder.glob('*_이론_*.md')) for b in re.split(r'(?=^## \[SLIDE )',f.read_text('utf8'),flags=re.M)[1:]]
def say(b):return ' '.join(l.strip().replace('**','') for l in b.splitlines()[1:] if l.strip() and not l.startswith(('>','#','---')))
def estimate(t):
 t=re.sub(r'^#.*$|^>.*$|\*\*','',t,flags=re.M);t=re.sub(r'[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)',r'\1',t)
 return (len(re.findall('[가-힣]',t))+1.6*len(re.findall(r'\d',t))+.6*len(re.findall('[A-Za-z]',t)))/275
report={'lab_execution':False,'student_code_or_tests_run':False,'ai_demo':False,'HYD_DB_browser_capture':False,'pptx':[],'pdf':json.loads((EV/'pdf-check.json').read_text('utf8')),'labs':[]};timing={}
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def screen(b):
 b=b.split('### 화면 구성')[0];b=re.sub(r'^- 노트:.*$','',b,flags=re.M);return b.replace('figures/day11/','figures/').strip()
for root,folder,course,day,count,labcount,allocation in [(C,I,'통합반',8,61,4,70),(D,P,'실전반',11,64,6,60)]:
 before=theory(EV/f'before/산출물/교재/대본/통합반_온라인/{day:02}회차');now=theory(folder)
 assert len(before)==len(now);assert [b.split(']')[0] for b in before]==[b.split(']')[0] for b in now]
 a=sum(estimate(say(b)) for b in before);b=sum(estimate(say(b)) for b in now)
 timing[course]=dict(slides_before=count,slides_after=count,blocks=len(now),changed_speech_blocks=[x.splitlines()[0] for x,y in zip(before,now) if say(x)!=say(y)],before_minutes=a,after_minutes=b,delta_seconds=(b-a)*60,syllabus_theory_minutes=allocation,wait_seconds=sum(int(n) for f in folder.glob('*_이론_*.md') for n in re.findall(r'\[대기 (\d+)초\]',f.read_text('utf8'))),practice=[dict(file=f.name,spoken_minutes=estimate(f.read_text('utf8'))) for f in sorted(folder.glob('*_실습_*.md'))])
 path=root/f'산출물/교재/PPTX/{course}_온라인/{course}_08일차.pptx';notes=theory_notes(folder)
 assert sorted(notes)==list(range(1,count+1))
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  assert len([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)])==count
  for name in z.namelist():
   if name.endswith('.rels'):
    parent=posixpath.dirname(posixpath.dirname(name))
    for r in E.fromstring(z.read(name)):
     if r.get('TargetMode')=='External':continue
     t=r.get('Target');resolved=posixpath.normpath(posixpath.join(parent,t)) if not t.startswith('/') else t[1:];assert resolved in z.namelist(),(name,resolved)
  for n in range(1,count+1):
   rel=E.fromstring(z.read(f'ppt/slides/_rels/slide{n}.xml.rels'));target=next(r.get('Target') for r in rel if r.get('Type').endswith('/notesSlide'));nr=E.fromstring(z.read(posixpath.normpath(posixpath.join('ppt/slides',target))))
   text=''.join(nr.xpath('//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]//a:t/text()',namespaces=ns));assert text==notes[n],(course,n,'notes')
  with zipfile.ZipFile(EV/f'before/산출물/교재/PPTX/통합반_온라인/통합반_{day:02}일차.pptx') as old:
   changed_parts=[]
   for name in old.namelist():
    if re.fullmatch(r'ppt/slides/slide\d+\.xml',name) or name.startswith(('ppt/media/','ppt/theme/','ppt/slideLayouts/','ppt/slideMasters/')):
     if old.read(name)!=z.read(name):changed_parts.append(name)
   assert changed_parts==([] if course=='통합반' else ['ppt/slides/slide1.xml']),changed_parts
 src=EV/f'before/만들기/decks/integrated/day{day:02}/통합반_{day:02}일차.md'
 dst=root/('만들기/decks/integrated/day08/통합반_08일차.md' if course=='통합반' else '만들기/decks/practical/day08/실전반_08일차.md')
 sb=re.split(r'(?=^## SLIDE )',src.read_text('utf8'),flags=re.M)[1:];db=re.split(r'(?=^## SLIDE )',dst.read_text('utf8'),flags=re.M)[1:]
 assert len(sb)==len(db)==count
 for n,(x,y) in enumerate(zip(sb,db),1):
  if not(course=='실전반' and n==1):assert screen(x)==screen(y),(course,n,'screen source')
 cfg=json.loads((folder/'구성.json').read_text('utf8'));assert cfg['pptx_sha256']==sha(path)
 report['pptx'].append(dict(course=course,slides=count,notes_exact=True,internal_relationships_valid=True,visible_changed_parts=changed_parts,source_coverage='all slides, in order, no omissions'))
 labs=sorted(p for p in (root/f'산출물/실습/{course}_온라인').glob('08일차_실습*') if p.is_dir());assert len(labs)==labcount
 for lab in labs:
  files=[f for f in lab.rglob('*') if f.is_file()]
  with zipfile.ZipFile(lab.with_suffix('.zip')) as z:
   assert z.testzip() is None;assert set(z.namelist())=={f.relative_to(lab).as_posix() for f in files}
   for f in files:assert z.read(f.relative_to(lab).as_posix())==f.read_bytes()
  refs=re.findall(r'href="([^"]+)"',(lab/'안내.html').read_text('utf8'))
  for ref in refs:assert (lab/html.unescape(ref)).exists(),ref
  for f in lab.rglob('*.json'):json.loads(f.read_text('utf-8-sig'))
  for f in lab.rglob('*.py'):ast.parse(f.read_text('utf-8-sig'))
  for f in lab.rglob('*.csv'):
   rows=list(csv.reader(f.read_text('utf-8-sig').splitlines()));assert rows and all(len(r)==len(rows[0]) for r in rows)
  report['labs'].append(dict(path=str(lab),files=len(files),zip_byte_match=True,local_links=len(refs),static_json_python_csv=True))
 # 모든 현재 회차 구성표와 실습 안내의 로컬 링크 확인
 for f in [folder/'구성표.md',root/f'산출물/실습/{course}_온라인/08회차_실습_안내.md']:
  for target in re.findall(r'\]\(([^)]+)\)',f.read_text('utf8')):assert (f.parent/target).exists(),(f,target)
for entry in json.loads((EV/'source-materials.json').read_text('utf8')):assert sha(Path(entry['source']))==sha(Path(entry['destination']))==entry['sha256']
report['copied_materials']=len(json.loads((EV/'source-materials.json').read_text('utf8')))
# 참조 예제의 구조만 읽는다. 자리값은 미완료 연결로 보고하며 실행하지 않는다.
ref=D/'students/_template/example_meeting';xml=E.parse(str(ref/'flow.bpmn'));ids=[e.get('id') for e in xml.iter() if e.get('id')];assert len(ids)==len(set(ids))
for e in xml.iter():
 for key in ['sourceRef','targetRef','attachedToRef','bpmnElement']:
  if e.get(key):assert e.get(key) in ids,(key,e.get(key))
mapping=json.loads((ref/'mapping.json').read_text('utf8'))
for key in ['tasks','timers','flows','lanes']:assert set(mapping[key])<=set(ids)
g=json.loads((ref/'graph.json').read_text('utf8'));nodes={n['props']['id'] for n in g['nodes']};assert len(nodes)==len(g['nodes'])
assert all(n['props']['ns']==g['ns'] and n['props']['id'].startswith(g['ns']+':') for n in g['nodes'])
external=sorted({r[k] for r in g['rels'] for k in ['a','b'] if r[k] not in nodes})
report['reference_static']=dict(bpmn_ids=len(ids),mapping_references_valid=True,graph_nodes=len(nodes),external_graph_references=external,unfilled_agent_or_tool_paths='reference README에 명시된 자리값 유지; 실제 연결·실행 미확인')
for f in Path(__file__).parent.glob('*.py'):ast.parse(f.read_text('utf8'))
if '--render' in sys.argv:
 report['renders']=[]
 for root,course,day,count in [(C,'통합반',8,61),(D,'실전반',11,64)]:
  f=EV/f'final-render/{course}_08일차.pdf';assert len(PdfReader(f).pages)==count;render(f,EV/f'final-render/{course}')
  old=pdfium.PdfDocument(EV/f'source-render/통합반_{day:02}일차.pdf');new=pdfium.PdfDocument(f);different=[]
  for n in range(count):
   if ImageChops.difference(old[n].render(scale=1).to_pil().convert('RGB'),new[n].render(scale=1).to_pil().convert('RGB')).getbbox() is not None:different.append(n+1)
  assert different==([] if course=='통합반' else [1]),(course,different)
  out=root/f'산출물/교재/PDF/{course}_온라인/{course}_08일차.pdf';out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,out)
  report['renders'].append(dict(course=course,pages=count,pixel_different_slides=different))
baseline=json.loads((EV/'before.json').read_text('utf8'));changed=[];missing=[]
for p,h in baseline.items():
 f=Path(p)
 if not f.exists():missing.append(p)
 elif sha(f)!=h:changed.append(p)
def allowed(p):
 f=Path(p);root=C if f.is_relative_to(C) else D;rel=f.relative_to(root).as_posix()
 if rel in ['문서/교재/인계_통합반_회차별_점검.md','문서/교재/3_현황.md','문서/교재/4_만드는_법.md','문서/교재/6_남은_일.md']:return True
 course='통합반' if root==C else '실전반';kind='integrated' if root==C else 'practical'
 return any(rel.startswith(x) for x in [f'산출물/교재/대본/{course}_온라인/08회차/',f'산출물/교재/대본/{course}_온라인/{course}_08일차',f'산출물/교재/대본/{course}_온라인/낭독본/{course}_08일차',f'만들기/decks/{kind}/day08/',f'산출물/교재/PPTX/{course}_온라인/{course}_08일차',f'산출물/교재/PDF/{course}_온라인/{course}_08일차',f'산출물/실습/{course}_온라인/08'])
unexpected=[p for p in changed if not allowed(p)];assert not missing and not unexpected,(missing,unexpected)
report['preservation']=dict(baseline_files=len(baseline),changed_existing_files=len(changed),missing=missing,unexpected=unexpected,changed_paths=changed,all_unrelated_work_preserved=True)
write(EV/'timing.json',json.dumps(timing,ensure_ascii=False,indent=2));write(EV/'final-check.json',json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(dict(timing=timing,preservation={k:v for k,v in report['preservation'].items() if k!='changed_paths'},labs=len(report['labs']),copied=report['copied_materials']),ensure_ascii=False))
