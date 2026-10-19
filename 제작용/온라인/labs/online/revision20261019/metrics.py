from pathlib import Path
import json,re,difflib,hashlib,subprocess,ast
from lxml import etree
D=Path('D:/work/study/hyd-portal-latest-20261014');C=Path('D:/work/study/hyd-integrated-recovered-20261018');EV=D/'.evidence/online-revision-20261019'
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def speech(t):return re.sub(r'^#.*$|^>.*$|\*\*','',t,flags=re.M)
def minutes(t):
 t=re.sub(r'[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)',r'\1',speech(t))
 return (len(re.findall('[가-힣]',t))+1.6*len(re.findall('[0-9]',t))+.6*len(re.findall('[A-Za-z]',t)))/275
def paras(t):return [p.strip() for p in speech(t).split('\n\n') if p.strip() and p.strip()!='---']
sync=json.loads((EV/'sync.json').read_text('utf8'));rows=[];preserve=[];syntax=[];fail=[];matrix=json.loads((EV/'review-matrix.json').read_text('utf8'))
for root,course,total in [(C,'통합반',11),(D,'실전반',8)]:
 base=root/'.evidence/online-revision-20261019';before=json.loads((base/'before.json').read_text('utf8'));start=json.loads((base/'git-start.json').read_text('utf8'));outside=[];changed=[];missing=[]
 for rel,h in before.items():
  p=root/rel
  if not p.exists():missing.append(rel)
  elif hashlib.sha256(p.read_bytes()).hexdigest()!=h:
   changed.append(rel)
   if not rel.startswith(('산출물/교재/','산출물/실습/','문서/교재/','만들기/decks/','만들기/labs/online/')):outside.append(rel)
 preserve.append(dict(root=str(root),baseline_files=len(before),changed=len(changed),missing=missing,outside_changes=outside,head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),branch=subprocess.check_output(['git','-C',str(root),'branch','--show-current'],text=True).strip()))
 for day in range(1,total+1):
  folder=root/f'산출물/교재/대본/{course}_온라인/{day:02}회차';cfg=json.loads((folder/'구성.json').read_text('utf8'));a=b=0;oldchanged=newchanged=0;details=[]
  for u in cfg['units']:
   if u['kind']!='practice':continue
   p=folder/u['file'];old=(base/'before'/p.relative_to(root)).read_text('utf8');new=p.read_text('utf8');a+=minutes(old);b+=minutes(new)
   oc=nc=0
   for tag,i,j,k,l in difflib.SequenceMatcher(None,paras(old),paras(new),autojunk=False).get_opcodes():
    if tag!='equal':oc+=j-i;nc+=l-k
   oldchanged+=oc;newchanged+=nc;details.append(dict(file=str(p),before=minutes(old),after=minutes(new),old_changed_paragraphs=oc,new_changed_paragraphs=nc))
   if not any(Path(x['path'])==p for x in matrix):matrix.append(dict(course=course,day=day,lab=p.stem.split('_실습_')[-1],purpose=paras(new)[0],exploration='첫 코딩 탐색' if day==1 else '제조 정비 계획의 자료·조건·후속 변경을 연결',path=str(p)))
  rows.append(dict(course=course,day=day,slides=cfg['slide_count'],labs=len(details),before=a,after=b,old_changed_paragraphs=oldchanged,new_changed_paragraphs=newchanged,details=details))
 for pair in sync['pairs']:
  lab=Path(pair['lab'])
  if not lab.is_relative_to(root):continue
  for p in lab.rglob('*'):
   if p.suffix not in ['.py','.json','.bpmn','.xml'] or not p.is_file():continue
   try:
    if p.suffix=='.py':ast.parse(p.read_text('utf-8-sig'))
    elif p.suffix=='.json':json.loads(p.read_text('utf-8-sig'))
    else:etree.parse(str(p))
    syntax.append(str(p))
   except Exception as e:fail.append([str(p),str(e)])
save(EV/'metrics.json',rows);save(EV/'preservation.json',preserve);save(EV/'syntax.json',dict(parsed=len(syntax),failures=fail));save(EV/'review-matrix.json',matrix)
print(json.dumps(dict(sessions=len(rows),matrix=len(matrix),syntax=len(syntax),failures=fail,preservation=preserve,totals={c:[round(sum(x[k] for x in rows if x['course']==c),1) for k in ['before','after','old_changed_paragraphs','new_changed_paragraphs']] for c in ['통합반','실전반']}),ensure_ascii=False))
