"""8회차 시작 기준. 기존 근거를 덮어쓰지 않으며 한 번만 실행한다."""
from pathlib import Path
import hashlib,json,shutil,subprocess
D=Path(__file__).resolve().parents[4]
C=Path('D:/work/study/hyd-integrated-recovered-20261018')
E=D/'.evidence/session08'
E.mkdir(parents=True,exist_ok=False)
h={}; states={}
for label,root in [('integrated',C),('practical',D)]:
 def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false','-C',str(root),*args]).decode('utf8')
 states[label]={'root':str(root),'branch':git('branch','--show-current').strip(),'head':git('rev-parse','HEAD').strip(),'status':git('status','--porcelain=v1')}
 (E/f'git-{label}.txt').write_text(json.dumps(states[label],ensure_ascii=False,indent=2),encoding='utf8')
 paths=set(git('ls-files','-z').split('\0')) | set(git('ls-files','--others','--exclude-standard','-z').split('\0'))
 for rel in paths:
  f=root/rel
  if rel and f.is_file() and f.name!='.env' and '__pycache__' not in f.parts:h[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
 for rel in ['문서/교재','만들기/decks','만들기/labs','산출물/교재','산출물/실습']:
  for f in (root/rel).rglob('*'):
   if f.is_file() and '__pycache__' not in f.parts:h[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
(E/'before.json').write_text(json.dumps(h,ensure_ascii=False,indent=2),encoding='utf8')
for day in [8,11]:
 for rel in [f'산출물/교재/대본/통합반_온라인/{day:02}회차',f'만들기/decks/integrated/day{day:02}',f'산출물/교재/PPTX/통합반_온라인/통합반_{day:02}일차.pptx']:
  src=C/rel;dst=E/'before'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
  if src.is_dir():shutil.copytree(src,dst)
  else:shutil.copy2(src,dst)
print(json.dumps({'baseline_files':len(h),'git':{k:{'branch':v['branch'],'head':v['head'],'modified_entries':len(v['status'].splitlines())} for k,v in states.items()}},ensure_ascii=False))
