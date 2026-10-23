import sys
lst, orig, new = sys.argv[1:4]
O=open(orig,encoding='utf-8').read(); N=open(new,encoding='utf-8').read()
rows=[l for l in open(lst,encoding='utf-8') if l.startswith('| ') and l.split('|')[1].strip().isdigit()]
T=O
for r in rows:
    c=[x.strip() for x in r.strip().strip('|').split('|')]
    no,before,after=c[0],c[4],c[5]
    if after=='(문단 삭제)':
        assert T.count('\n\n'+before)==1, no; T=T.replace('\n\n'+before,'',1); continue
    if before.startswith('('):
        anchor='점검 계획에 원인 이름만 쓰는 것이 아니라, 왜 그 점검이 필요한지까지 남기는 활동입니다.'
        assert T.count(anchor)==1; T=T.replace(anchor, anchor+'\n\n'+after,1); continue
    assert T.count(before)==1, (no, T.count(before)); T=T.replace(before,after,1)
print('identical' if T==N else 'DIFFERENT')
