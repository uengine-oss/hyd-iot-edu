"""완료 후 메타 원문·산출물 해시·Git 기준을 재확인한다."""
from helpers import *
import subprocess
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
meta=json.loads((EV/'meta-preservation.json').read_text('utf8'))
for x in meta:assert hashlib.sha256(Path(x['path']).read_bytes()[x['prefix_bytes']:]).hexdigest()==x['old_sha256']
artifacts=json.loads((EV/'artifact-manifest.json').read_text('utf8'))
for x in artifacts:assert sha(Path(x['path']))==x['sha256']
links=0
for root in [C,D]:
 report=root/'문서/교재/근거/2026-10-18_8회차_점검결과.md'
 for target in re.findall(r'\]\(([^)]+)\)',report.read_text('utf8')):
  if target.startswith('https:'):continue
  assert Path(target).exists(),target;links+=1
 for name in ['인계_통합반_회차별_점검.md','3_현황.md','6_남은_일.md','4_만드는_법.md']:
  p=root/'문서/교재'/name;first=p.read_text('utf8').split('\n---\n')[0]
  for target in re.findall(r'\]\(([^)]+)\)',first):assert (p.parent/target).exists();links+=1
states={}
for root,kind in [(C,'integrated'),(D,'practical')]:
 def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false','-C',str(root),*args]).decode('utf8')
 start=json.loads((EV/f'git-{kind}.txt').read_text('utf8'))
 current=dict(root=str(root),branch=git('branch','--show-current').strip(),head=git('rev-parse','HEAD').strip(),status=git('status','--porcelain=v1'))
 assert start['head']==current['head'] and start['branch']==current['branch']
 write(root/f'.evidence/session08/git-final-{kind}.json',json.dumps(current,ensure_ascii=False,indent=2))
 states[kind]=dict(branch=current['branch'],head=current['head'],initial_dirty_entries=len(start['status'].splitlines()),final_dirty_entries=len(current['status'].splitlines()))
result=dict(artifact_hashes=len(artifacts),metadata_original_tails_preserved=len(meta),report_and_current_meta_links=links,git=states,no_commit=True,no_push=True)
write(EV/'closeout-check.json',json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
