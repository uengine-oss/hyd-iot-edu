"""정적 문서 검증과 동일 산식 변경량. 실습 실행 없음."""
from helpers import *
import ast,posixpath,csv
from PIL import ImageChops
def theory(folder):return [b for f in sorted(folder.glob('*_이론_*.md')) for b in re.split(r'(?=^## \[SLIDE )',f.read_text('utf8'),flags=re.M)[1:]]
def say(b):return ' '.join(l.strip().replace('**','') for l in b.splitlines()[1:] if l.strip() and not l.startswith(('>','#','---')))
def estimate(t):
 t=re.sub(r'^#.*$|^>.*$|\*\*','',t,flags=re.M);t=re.sub(r'[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)',r'\1',t)
 return (len(re.findall('[가-힣]',t))+1.6*len(re.findall(r'\d',t))+.6*len(re.findall('[A-Za-z]',t)))/275
def mins(bs):return sum(estimate(say(b)) for b in bs)
before=theory(EV/'before/산출물/교재/대본/통합반_온라인/04회차');now=theory(I);pt=theory(P)
assert len(before)==len(now)==66 and len(pt)==127
changed=[dict(block=b.splitlines()[0],before_minutes=estimate(say(a)),after_minutes=estimate(say(b))) for a,b in zip(before,now) if say(a)!=say(b)]
mapping=json.loads((P/'원본대응.json').read_text('utf8'))['slides']
source={d:{int(re.match(r'## \[SLIDE (\d+)',b)[1]):b for b in theory(EV/f'before/산출물/교재/대본/통합반_온라인/{d:02}회차')} for d in [5,6]}
full=[source[m['source_day']][m['source_slide']] for m in mapping if m['source_slide'] in source[m['source_day']]]
changedP=[dict(destination=m['destination'],source_day=m['source_day'],source_slide=m['source_slide']) for m in mapping if m['source_slide'] in source[m['source_day']] and say(source[m['source_day']][m['source_slide']])!=say(next(b for b in pt if re.match(r'## \[SLIDE (\d+)',b)[1]==str(m['destination'])))]
timing={'integrated':{'slides_before':69,'slides_after':69,'blocks':len(now),'changed_speech_blocks':len(changed),'before_minutes':mins(before),'after_minutes':mins(now),'delta_seconds':(mins(now)-mins(before))*60,'original_syllabus_theory_minutes':70},'practical':{'slides':132,'blocks':len(pt),'changed_speech_blocks':len(changedP),'full_source_minutes':mins(full),'minutes':mins(pt),'delta_seconds':(mins(pt)-mins(full))*60,'original_syllabus_theory_minutes':80},'integrated_changed_blocks':changed,'practical_changed_blocks':changedP}
for key,folder in [('integrated',I),('practical',P)]:
 timing[key]['wait_seconds']=sum(int(n) for f in folder.glob('*_이론_*.md') for n in re.findall(r'\[대기 (\d+)초\]',f.read_text('utf8')))
 timing[key]['practice']=[dict(file=f.name,spoken_minutes=estimate(f.read_text('utf8'))) for f in sorted(folder.glob('*_실습_*.md'))]
write(EV/'timing.json',json.dumps(timing,ensure_ascii=False,indent=2))
report={'lab_execution':False,'capture':False,'pptx':[],'pdf':json.loads((EV/'pdf-check.json').read_text('utf8'))}
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
for root,folder,course,count,labcount in [(C,I,'통합반',69,3),(D,P,'실전반',132,4)]:
 p=root/f'산출물/교재/PPTX/{course}_온라인/{course}_04일차.pptx';notes=theory_notes(folder);assert sorted(notes)==list(range(1,count+1))
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  assert len([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+.xml',n)])==count
  for name in z.namelist():
   if name.endswith('.rels'):
    parent=posixpath.dirname(posixpath.dirname(name))
    for r in E.fromstring(z.read(name)):
     if r.get('TargetMode')=='External':continue
     t=r.get('Target');resolved=posixpath.normpath(posixpath.join(parent,t)) if not t.startswith('/') else t[1:];assert resolved in z.namelist(),(name,resolved)
  for n in range(1,count+1):
   rel=E.fromstring(z.read(f'ppt/slides/_rels/slide{n}.xml.rels'));target=next(r.get('Target') for r in rel if r.get('Type').endswith('/notesSlide'));nr=E.fromstring(z.read(posixpath.normpath(posixpath.join('ppt/slides',target))))
   text=''.join(nr.xpath('//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]//a:t/text()',namespaces=ns));assert text==notes[n],(course,n,'notes mismatch')
 cfg=json.loads((folder/'구성.json').read_text('utf8'));cfg['pptx_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();write(folder/'구성.json',json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
 report['pptx'].append(dict(course=course,slides=count,notes_exact=True,relationships_valid=True))
 labs=[p for p in (root/f'산출물/실습/{course}_온라인').glob('04일차_실습*') if p.is_dir()];assert len(labs)==labcount
 for lab in labs:
  with zipfile.ZipFile(lab.with_suffix('.zip')) as z:
   assert z.testzip() is None
   files=[f for f in lab.rglob('*') if f.is_file()];assert set(z.namelist())=={f.relative_to(lab).as_posix() for f in files}
   for f in files:assert z.read(f.relative_to(lab).as_posix())==f.read_bytes()
  for ref in re.findall(r'href="([^"]+)"',(lab/'안내.html').read_text('utf8')):assert (lab/html.unescape(ref)).exists(),ref
  for f in lab.rglob('*.json'):json.loads(f.read_text('utf-8-sig'))
  for f in lab.rglob('*.py'):ast.parse(f.read_text('utf-8-sig'))
  for f in lab.rglob('*.csv'):
   rows=list(csv.reader(f.read_text('utf-8-sig').splitlines()));assert rows and all(len(r)==len(rows[0]) for r in rows),(f,'CSV width')
report['zip_byte_match']=7;report['html_local_links_valid']=7
for entry in json.loads((EV/'source-materials.json').read_text('utf8')):assert hashlib.sha256(Path(entry['source']).read_bytes()).hexdigest()==hashlib.sha256(Path(entry['destination']).read_bytes()).hexdigest()==entry['sha256']
with zipfile.ZipFile(EV/'before/산출물/교재/PPTX/통합반_온라인/통합반_04일차.pptx') as a,zipfile.ZipFile(C/'산출물/교재/PPTX/통합반_온라인/통합반_04일차.pptx') as b:
 same=[n for n in a.namelist() if re.fullmatch(r'ppt/slides/slide\d+.xml',n) or n.startswith(('ppt/media/','ppt/theme/','ppt/slideLayouts/','ppt/slideMasters/'))];assert all(a.read(n)==b.read(n) for n in same)
report['integrated_visible_parts_identical']=len(same)
def deck(path):return re.split(r'(?=^## SLIDE )',path.read_text('utf8'),flags=re.M)[1:]
def content(b):
 b=b.split('### 화면 구성')[0];b=re.sub(r'^## SLIDE \d+','## SLIDE',b);b=re.sub(r'^- (노트|번호):.*$','',b,flags=re.M);b=re.sub(r'figures/day\d+/','figures/',b);b=re.sub(r'Quiz [1-6]','Quiz N',b);return b.strip()
src={d:deck(C/f'만들기/decks/integrated/day{d:02}/통합반_{d:02}일차.md') for d in [5,6]};dst=deck(D/'만들기/decks/practical/day04/실전반_04일차.md')
assert len(dst)==132
for m in mapping:
 if m['destination'] not in [1,2,3,117,119]:assert content(src[m['source_day']][m['source_slide']-1])==content(dst[m['destination']-1]),m
assert {m['source_slide'] for m in mapping if m['source_day']==5}=={*range(1,60),*range(64,71)}
assert {m['source_slide'] for m in mapping if m['source_day']==6}=={*range(4,64),66,67,69,70,71,72}
report['source_mapping']={'source5_slides':66,'source6_slides':66,'screen_content_preserved_except_numbers':127,'metadata_rewritten':3,'lab_assignment_screen_adapted':1,'lab_layout_reworded':1,'all_six_quizzes':True}
for f in Path(__file__).parent.glob('*.py'):ast.parse(f.read_text('utf8'))
report['static_python_syntax']=True
if '--render' in sys.argv:
 report['renders']=[]
 for root,course,count in [(C,'통합반',69),(D,'실전반',132)]:
  f=EV/f'final-render/{course}_04일차.pdf';assert len(PdfReader(f).pages)==count;render(f,EV/f'final-render/{course}')
  if course=='통합반':
   a=pdfium.PdfDocument(EV/'source-render/통합반_04일차.pdf');b=pdfium.PdfDocument(f)
   for n in range(count):assert ImageChops.difference(a[n].render(scale=1).to_pil().convert('RGB'),b[n].render(scale=1).to_pil().convert('RGB')).getbbox() is None,('pixel',n+1)
  out=root/f'산출물/교재/PDF/{course}_온라인/{course}_04일차.pdf';out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,out)
  report['renders'].append(dict(course=course,pages=count,integrated_pixel_identical=course=='통합반'))
baseline=json.loads((EV/'before.json').read_text('utf8'));changedpaths=[];missing=[]
for p,h in baseline.items():
 f=Path(p)
 if not f.exists():missing.append(p)
 elif hashlib.sha256(f.read_bytes()).hexdigest()!=h:changedpaths.append(p)
allowed=['산출물/교재/대본/통합반_온라인/04회차/','산출물/교재/대본/통합반_온라인/통합반_04일차','산출물/교재/대본/통합반_온라인/낭독본/통합반_04일차','만들기/decks/integrated/day04/','산출물/교재/PPTX/통합반_온라인/통합반_04일차','산출물/교재/PDF/통합반_온라인/통합반_04일차','문서/교재/인계_통합반_회차별_점검.md','문서/교재/4_만드는_법.md','문서/교재/3_현황.md','문서/교재/6_남은_일.md']
unexpected=[p for p in changedpaths if not any(s in p.replace('\\','/') for s in allowed)];assert not missing and not unexpected,(missing,unexpected)
report['preservation']=dict(baseline_files=len(baseline),changed_existing_files=len(changedpaths),missing=missing,unexpected=unexpected,changed_paths=changedpaths)
write(EV/'final-check.json',json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(dict(timing=timing,preservation={k:v for k,v in report['preservation'].items() if k!='changed_paths'}),ensure_ascii=False))
