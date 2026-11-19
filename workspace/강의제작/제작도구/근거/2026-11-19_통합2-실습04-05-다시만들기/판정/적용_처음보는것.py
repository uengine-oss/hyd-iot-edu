"""처음보는것_NN.json의 전 → 후, 조작전 → 조작후를 그 큐 줄 안에서만 바꾼다(한 번씩 있어야 한다). 쓰는 법: 적용_처음보는것.py <대본.md> <json> [번호=새 후 …]"""
import json,sys
md,js=sys.argv[1],sys.argv[2]; over=dict(a.split('=',1) for a in sys.argv[3:])
lines=open(md,encoding='utf-8',newline='').read().split('\n'); d=json.load(open(js,encoding='utf-8'))
for x in d['고칠것']:
    i=[k for k,l in enumerate(lines) if l.startswith(f"| {x['큐']} |")]
    if len(i)!=1: raise SystemExit(f"{x['번호']}: 큐 줄 {len(i)}개")
    l=lines[i[0]]; 후=over.get(x['번호'],x['후'])
    for a,b in [(x['전'],후),(x.get('조작전') or '',x.get('조작후') or '')]:
        if not a: continue
        if l.count(a)!=1: raise SystemExit(f"{x['번호']}: 「{a[:30]}」 {l.count(a)}번")
        l=l.replace(a,b)
    lines[i[0]]=l; print('적용',x['번호'],x['큐'])
open(md,'w',encoding='utf-8',newline='').write('\n'.join(lines))
