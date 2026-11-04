"""3 · 4회차 온라인 · 오프라인 덱 원고(화면 · 노트) · 대본 낭독의 식별자가 지금 코드 · 시드 · 수업 문서 · 떠 있는 그래프에 있는지 잰다. 이름 존재만 판정한다. 인자: 출력 json [그래프덤프.json]"""
import re, subprocess, json, sys
from pathlib import Path
W=Path('workspace/강의제작')
def d(c,n): 
    cp={'통합반':'integrated','실전반':'practical'}[c]
    return W/f'제작도구/온라인/decks/{cp}/day{n}/{c}_{n}일차.md'
def o(c,n):
    cp={'통합반':'integrated','실전반':'practical'}[c]
    return W/f'제작도구/오프라인/decks/{cp}/off{n}/{c}_오프라인_{n}회차.md'
SRC={'온3통합':[d('통합반','03'),*sorted((W/'산출물/통합반/이론/03회차/대본').glob('*.md'))],
 '온3실전':[d('실전반','03'),*sorted((W/'산출물/실전반/이론/03회차/대본').glob('*.md'))],
 '온4통합':[d('통합반','04'),*sorted((W/'산출물/통합반/이론/04회차/대본').glob('*.md'))],
 '온4실전':[d('실전반','04'),*sorted((W/'산출물/실전반/이론/04회차/대본').glob('*.md'))],
 '오3통합':[o('통합반','03')],'오4통합':[o('통합반','04')],'오3실전':[o('실전반','03')],'오4실전':[o('실전반','04')],'오5실전':[o('실전반','05')]}
PAT=re.compile(r"\b(?:rule|fm|sym|cause|comp|cmp|asset|sen|sv|pattern|msr|dt|dec|ks|skill|part|kpi|act|step|sec|ms|task|proc|doc|cand)[:\-][a-z0-9][a-z0-9_\-:]*|\bSOP-[A-Z]+-\d+\b|\bP-[A-Z]{2,}-[A-Z0-9\-]+\b|\bHM-\d+(?:\.\d+)?\b|\b[A-Z]+_[A-Z_]{3,}\b|\b[A-Z][a-zA-Z]+(?=\s*\{)|\b[a-z]+_[a-z0-9_]{2,}\b")
tree=subprocess.run(['git','ls-files','it','ot','dmz','common'],capture_output=True,text=True,encoding='utf8').stdout.split('\n')
corpus=''
for f in tree:
    p=Path(f)
    if p.suffix in('.cypher','.json','.py','.md','.yaml','.yml','.js','.html','.ttl','.sql','.mjs','.txt'):
        try:
            if p.stat().st_size<3_000_000: corpus+=p.read_text('utf8',errors='ignore')+'\n'
        except OSError: pass
if len(sys.argv)>2: corpus+=Path(sys.argv[2]).read_text('utf8')
def spoken(path):
    t=path.read_text('utf8')
    if path.parent.name=='대본': return t.split('# 촬영 본문 끝')[0]
    return '\n'.join(re.findall(r'### 화면 내용\n(.*?)(?=\n### |\n## |\Z)',t,flags=re.S))
out={}
for k,fs in SRC.items():
    seen={}
    for f in fs:
        t=spoken(f)
        cur=None
        for line in t.split('\n'):
            m=re.match(r'## \[?SLIDE (\d+)',line)
            if m: cur=m[1]
            for x in PAT.finditer(line): seen.setdefault(x[0],set()).add(f.name[:14]+(':'+cur if cur else ''))
    miss={a:sorted(b)[:8] for a,b in seen.items() if a not in corpus}
    out[k]=miss; print(k,'식별자',len(seen),'코드 · 그래프에 없음',len(miss))
    for a,b in sorted(miss.items())[:80]: print('   ',a,b[:4])
json.dump(out,open(sys.argv[1],'w',encoding='utf8'),ensure_ascii=False,indent=1)
