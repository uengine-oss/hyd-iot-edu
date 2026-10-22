import html,re,sys
from pathlib import Path
# sync.py(제작용/온라인/labs/online/revision20261019) 44행과 같은 형식으로 가이드.html을 만든다.
repo_lab=Path(sys.argv[1]); prop_lab=Path(sys.argv[2]); script=Path(sys.argv[3])
names=set()
for base in (repo_lab,prop_lab):
    for f in base.rglob('*'):
        if f.is_file() and f.suffix not in ['.html','.pdf','.zip'] and f.name!='강사대본.md' and '__pycache__' not in f.parts and f.suffix!='.pyc':
            names.add(f.relative_to(base).as_posix())
links=''.join('<li><a href="'+html.escape(n,quote=True)+'">'+html.escape(n)+'</a></li>' for n in sorted(names))
text=script.read_text('utf8');blocks=[]
for para in text.strip().split('\n\n'):
    tag='h1' if para.startswith('# ') else 'h2' if para.startswith('## ') else 'aside' if para.startswith('>') else 'p'
    blocks.append('<'+tag+'>'+html.escape(re.sub(r'^(?:#{1,2} |> ?)', '',para))+'</'+tag+'>')
out='<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+html.escape(repo_lab.name)+'</title><style>body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:980px;margin:40px auto;padding:0 24px;color:#22303e}h1{font-size:28px}h2{margin-top:32px;font-size:23px}aside{background:#f0f4f7;padding:14px}p,aside{white-space:pre-wrap}</style><p>제작 참고용 · 학생 가이드 제공 전제 없음 · 실제 실행 및 이미지 촬영 미수행</p><details><summary>작업 자료</summary><ul>'+links+'</ul></details>'+''.join(blocks)+'</html>'
(prop_lab/'가이드.html').write_text(out,'utf8')
