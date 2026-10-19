"""현재 산출물·기존 기록·링크·Git 상태의 읽기 전용 최종 대조."""
from helpers import *
import subprocess,ast
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
counts={}
# 현재 분할 이론과 합본·낭독본의 실제 발화 전량 비교.
spoken=lambda s:' '.join(l.strip().replace('**','') for l in s.splitlines() if l.strip() and not l.startswith(('#','>','---')))
extract=lambda s:[spoken(b.split('\n',1)[1]) for b in re.split(r'(?=^## \[SLIDE )',s.split('# 촬영 본문 끝')[0],flags=re.M)[1:]]
theory=[b for p in sorted(I.glob('*_이론_*.md')) for b in extract(p.read_text('utf8'))]
for p in [I.parent/'통합반_09일차_대본.md',I.parent/'낭독본/통합반_09일차_낭독본.md']:
 assert extract(p.read_text('utf8'))==theory,p
for p in sorted(I.glob('*_이론_*.md')):
 assert extract(p.read_text('utf8'))==extract((I/'낭독본'/p.name).read_text('utf8'))
for session in ['session08','session09']:
 items=json.loads((D/'.evidence'/session/'artifact-manifest.json').read_text('utf8'))
 for x in items:
  p=Path(x['path']);assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256'],p
 counts[session]=len(items)
meta=json.loads((EV/'meta-preservation.json').read_text('utf8'))
linkcount=0
def links(p,s):
 global linkcount
 for ref in re.findall(r'\]\(([^)]+)\)',s):
  if ref.startswith(('https:','http:','#')):continue
  target=Path(ref) if re.match(r'^[A-Z]:[/\\]',ref,re.I) else p.parent/ref
  assert target.exists(),(p,ref)
  linkcount+=1
for x in meta:
 p=Path(x['path']);content=p.read_bytes()
 assert hashlib.sha256(content[x['prefix_bytes']:]).hexdigest()==x['old_sha256'],p
 links(p,content[:x['prefix_bytes']].decode('utf8'))
for root in [C,D]:
 p=root/'문서/교재/근거/2026-10-19_9회차_점검결과.md';links(p,p.read_text('utf8'))
p=I.parent/'통합반_09일차_대본.md';links(p,p.read_text('utf8'))
git={}
for root,kind in [(C,'integrated'),(D,'practical')]:
 run=lambda *args:subprocess.check_output(['git','-C',str(root),'-c','core.quotepath=false',*args]).decode('utf8').strip()
 start=json.loads((EV/f'git-start-{kind}.json').read_text('utf8'))
 state=dict(branch=run('branch','--show-current'),head=run('rev-parse','HEAD'),status=run('status','--short'))
 assert state['head']==start['head'] and state['branch']==start['branch']
 write(EV/f'git-final-{kind}.json',json.dumps(state,ensure_ascii=False,indent=2))
 git[kind]={k:v for k,v in state.items() if k!='status'}
 git[kind]['dirty_entries']=len(state['status'].splitlines())
 for name in [f'before-{kind}.json',f'git-start-{kind}.json']:
  assert (root/'.evidence/session09'/name).read_bytes()==(EV/name).read_bytes()
for f in Path(__file__).parent.glob('*.py'):ast.parse(f.read_text('utf8'))
pres=json.loads((EV/'final-check.json').read_text('utf8'))['preservation']
assert all(not v['missing'] and not v['unexpected'] for v in pres.values())
result=dict(artifact_hashes=counts,metadata_original_tails_preserved=len(meta),current_links=linkcount,git=git,no_commit=True,no_push=True,actual_lab_execution=False,scope='기존8회차 보존 및 작성 중이던 통합반9 마감. 실전반 신규9와 통합반10~11 작업 없음.')
write(EV/'closeout-check.json',json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
