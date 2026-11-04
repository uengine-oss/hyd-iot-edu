import json,glob,re,subprocess
W='작업/2026-11-04_1-4회차-이론-되풀이-순서'
sp=lambda s:re.sub(r'\s+',' ',s or '').strip()
Q={'실전반_03':['P3-34'],'실전반_04':['P4-03','P4-28'],'통합반_01':['T1-03','T1-18','T1-19','T1-51'],'통합반_02':['T2-03','T2-34','T2-44','T2-47']}
for name,ids in Q.items():
    c,n=name.split('_'); L=json.load(open(f'{W}/점검/{name}.json',encoding='utf8'))['고칠것']; V=json.load(open(f'{W}/판정/{name}.json',encoding='utf8'))['판정']
    afters={x['번호']:sp(V[x['번호']].get('후',x.get('후'))) for x in L}
    cur={}
    for f in glob.glob(f'workspace/강의제작/산출물/{c}/이론/{n}회차/대본/*.md'):
        t=open(f,encoding='utf8',newline='').read().replace('\r\n','\n')
        for m in re.finditer(r'^## \[SLIDE (\d+)(?:~\d+)?\][^\n]*\n(.*?)(?=^#|\Z)',t,re.M|re.S): cur[int(m.group(1))]=sp(m.group(2))
    for it in L:
        if it['번호'] not in ids: continue
        s=sp(it['전']); where=[k for k,b in cur.items() if s in b]
        host=[k for k,a in afters.items() if k!=it['번호'] and s and s in a]
        print(it['번호'],it['종류'],it['고침'],'장',it['장'],'→지금 장',where,'다른항목 후에 포함',host,'|처리',V[it['번호']]['처리'],'|후 글자',len(afters[it['번호']]))
        if not host: print('   전:',s[:150]); print('   후:',afters[it['번호']][:150])
