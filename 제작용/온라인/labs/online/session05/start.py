from pathlib import Path
import hashlib,json,shutil,subprocess
D=Path(__file__).resolve().parents[4];C=Path('C:/Users/roede/.codex/worktrees/hyd-script-flow/hyd-portal-latest-20261014');E=D/'.evidence/session05';E.mkdir(parents=True,exist_ok=True)
assert not (E/'before.json').exists(),'baseline already exists'
h={}
for root in [C,D]:
 for rel in ['문서/교재','만들기/decks','만들기/labs','산출물/교재','산출물/실습']:
  for f in (root/rel).rglob('*'):
   if f.is_file() and '__pycache__' not in f.parts:h[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
 (E/f'git-{root.drive[0]}.txt').write_bytes(subprocess.check_output(['git','-C',str(root),'status','--porcelain=v1']))
(E/'before.json').write_text(json.dumps(h,ensure_ascii=False,indent=2),encoding='utf8')
for day in [5,7,8]:
 for rel in [f'산출물/교재/대본/통합반_온라인/{day:02}회차',f'만들기/decks/integrated/day{day:02}',f'산출물/교재/PPTX/통합반_온라인/통합반_{day:02}일차.pptx']:
  src=C/rel;dst=E/'before'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
  if src.is_dir():shutil.copytree(src,dst)
  else:shutil.copy2(src,dst)
print('baseline',len(h))
