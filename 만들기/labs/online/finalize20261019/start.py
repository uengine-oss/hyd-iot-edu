"""두 과정 전체 마감 재개 불변 시작 기준. 기존 근거를 재생성하지 않는다."""
from pathlib import Path
import hashlib,json,subprocess,shutil
D=Path(__file__).resolve().parents[4];C=Path('D:/work/study/hyd-integrated-recovered-20261018');E=D/'.evidence/finalize20261019'
E.mkdir(parents=True,exist_ok=False)
for kind,root in [('integrated',C),('practical',D)]:
 def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false','-C',str(root),*args]).decode('utf8')
 state=dict(root=str(root),branch=git('branch','--show-current').strip(),head=git('rev-parse','HEAD').strip(),status=git('status','--porcelain=v1'))
 paths=set(git('ls-files','-z').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').split('\0'));files={root/x for x in paths if x and (root/x).is_file()}
 for rel in ['문서/교재','만들기/decks','만들기/labs','산출물/교재','산출물/실습']:
  files.update(f for f in (root/rel).rglob('*') if f.is_file())
 files.update(f for f in (root/'.evidence').rglob('*') if f.is_file() and f.suffix in ['.json','.md','.txt'] and 'finalize20261019' not in f.parts)
 hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files) if f.name!='.env' and '__pycache__' not in f.parts}
 for p in [E,root/'.evidence/finalize20261019']:
  p.mkdir(parents=True,exist_ok=True)
  (p/f'git-start-{kind}.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
  (p/f'before-{kind}.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
 print(kind,len(hashes),len(state['status'].splitlines()),state['branch'],state['head'])
