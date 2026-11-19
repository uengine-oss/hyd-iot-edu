# 대본 표에서 큐를 읽어 말 길이 · 쉼 · 조작 시간을 어림한다(시간계수.json의 계수). 큐 JSON이 생기면 시간계산.py estimate가 정본이다.
import re,sys,json,collections
K=json.load(open('workspace/강의제작/제작도구/촬영/시간계수.json',encoding='utf-8'))
SY,DG,EN,PU=K['speech']; CH,CL,DR,KY,C0=K['overflow']
def speech(t):
    t=t.replace('&lt;','<').replace('&gt;','>')
    return (len(re.findall(r'[가-힣]',t))*SY+len(re.findall(r'[0-9]',t))*DG+len(re.findall(r'[A-Za-z]',t))*EN+len(re.findall(r'[.,?!]',t))*PU)
for f in sys.argv[1:]:
    body=open(f,encoding='utf-8').read().split('# 촬영 본문 끝')[0]
    sec=None;rows=[];tot=collections.OrderedDict()
    for line in body.splitlines():
        if line.startswith('## '):sec=line[3:].strip();tot[sec]=[0,0,0,0];continue
        m=re.match(r'\| ([gk]\d{4}) \| (.*?) \| (.*) \|$',line)
        if not m:continue
        cid,say,op=m.groups()
        sp=speech(say)+0.6*max(0,len(re.findall(r'[.?!](?= )',say)))   # 큐 안 문장 사이 0.6초
        pm=re.search(r'쉼: (잇기|큐|결과 뒤|구간) ([0-9.]+)',op); pause=float(pm.group(2)) if pm else 2.0
        opt=op.count('[복사]')*(4*CL+KY+C0)+(len(re.findall(r'누른다|누르고|고른다',op))-op.count('[복사]')*0)*CL+len(''.join(re.findall(r'`([^`]*)`를 넣',op)))*CH
        nsent=len(re.findall(r'[.?!](?= |$)',say))
        rows.append((cid,sp,nsent,len(say)));t=tot[sec];t[0]+=sp;t[1]+=pause;t[2]+=opt;t[3]+=1
    S=sum(v[0] for v in tot.values());P=sum(v[1] for v in tot.values());O=sum(v[2] for v in tot.values());N=sum(v[3] for v in tot.values())
    print(f'\n== {f}\n큐 {N}개 · 말 {S/60:.1f}분 · 쉼 {P/60:.1f}분 · 조작 {O/60:.1f}분 · 합 {(S+P+O)/60:.1f}분')
    for k,v in tot.items():print(f'  {k}: 큐 {v[3]} · {(v[0]+v[1]+v[2])/60:.1f}분')
    long=[(c,round(s,1),n) for c,s,n,_ in rows if s>30 or n>4]
    print('  30초 넘거나 다섯 문장 이상인 큐(읽을 곳):',long)
