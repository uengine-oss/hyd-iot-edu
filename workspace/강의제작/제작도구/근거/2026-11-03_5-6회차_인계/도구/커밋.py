"""이 작업 경로만 --만으로 커밋한다. 파일이 많아 명령 줄 길이를 넘으므로 동기화.py의 commit을 파이썬 안에서 부르고 git rm에도 경로를 파일로 넘긴다. 인자: 메시지 파일"""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
G='workspace/강의제작/'
T=Path('작업/2026-11-03_3-4회차-이론영상-갱신')
roots=[G+'제작도구/온라인/decks/integrated/day03',G+'제작도구/온라인/decks/integrated/day04',G+'제작도구/온라인/decks/practical/day03',G+'제작도구/온라인/decks/practical/day04',G+'산출물/통합반/이론/03회차',G+'산출물/통합반/이론/04회차',G+'산출물/실전반/이론/03회차',G+'산출물/실전반/이론/04회차',G+'제작도구/구성/통합반/03회차',G+'제작도구/구성/통합반/04회차',G+'제작도구/구성/실전반/03회차',G+'제작도구/구성/실전반/04회차']
V=G+'제작도구/기존제작/tools/video/'
off=json.loads((T/'실측/커밋대상.json').read_text('utf8'))['off']
voice=[V+f'음성_저장/{h}.{e}' for h in off for e in ('mp3','json')]
br=[]
for S in ['작업/2026-11-03_3회차-음성-노션게시/개정판/미디어/합성대기/도구/쉼_저장','작업/2026-11-03_4회차-이론/합성대기/도구/쉼_저장']:
    br+=[V+'쉼_저장/'+p.name for p in Path(S).glob('*.json')]
paths=roots+voice+sorted(set(br))
print('경로',len(paths))
spec=importlib.util.spec_from_file_location('동기화','workspace/동기화.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
NUL=chr(0)
def only(tp, ps, files):
    fs=set(files); add=[]; remote=m.git('ls-tree','-r','--name-only','-z',tp).split(NUL); rs=set(remote)
    for x in ps:
        here=[x] if x in fs else [f for f in files if f.startswith(x+'/')]
        if not here and x not in rs and not any(f.startswith(x+'/') for f in remote): sys.exit(f'--만 {x}: 로컬에도 브랜치에도 없다')
        add+=here
    with tempfile.TemporaryDirectory() as d:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(d)/'index'))
        m.git('read-tree',tp,env=env)
        pl=Path(d)/'rm'; pl.write_text(chr(10).join(ps)+chr(10),encoding='utf-8')
        m.git('rm','-r','-q','-f','--cached','--ignore-unmatch',f'--pathspec-from-file={pl}',env=env)
        al=Path(d)/'list'; al.write_text(chr(10).join(add)+chr(10),encoding='utf-8')
        m.git('-c','core.autocrlf=false','add','-f',f'--pathspec-from-file={al}',env=env)
        return m.git('write-tree',env=env).strip()
m.build_tree_only=only
m.commit(Path(sys.argv[1]).read_text('utf8'),['--만',*paths])
