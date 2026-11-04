"""고치며 생긴 찌꺼기만 정리: 낭독 줄의 겹공백 · 줄끝 공백 · 3줄 이상 빈 줄 · 뒤에 낭독 없는 빈 표시(> [핵심|풀이|보충]). 원래 판에 없던 것만 건드린다."""
import re,subprocess,sys,glob,os
base='7e85bdd4'
for c,n in [('실전반','01'),('통합반','01'),('통합반','02'),('통합반','03'),('통합반','04'),('실전반','02'),('실전반','03'),('실전반','04')]:
    for p in sorted(glob.glob(f'workspace/강의제작/산출물/{c}/이론/{n}회차/대본/*.md')):
        raw=open(p,'rb').read().decode('utf8'); nl='\r\n' if '\r\n' in raw else '\n'
        old=subprocess.run(['git','show',f'{base}:{p}'],capture_output=True).stdout.decode('utf8')
        if old==raw: continue
        t=raw.replace('\r\n','\n'); o=old.replace('\r\n','\n'); o_lines=set(o.split('\n'))
        L=[]
        for line in t.split('\n'):
            if line not in o_lines and not line.startswith(('>','#','|')):
                line=re.sub(r'(?<=\S)  +(?=\S)',' ',line).strip()
            L.append(line)
        t='\n'.join(L)
        before=t
        # 뒤에 낭독 없이 다음 표시/구분/제목이 오는 빈 표시
        t=re.sub(r'^> \[(?:핵심|풀이|보충)\]\n+(?=(?:> \[(?:핵심|풀이|보충)\]|---|#))','',t,flags=re.M)
        if not re.search(r'\n{3,}',o): t=re.sub(r'\n{3,}','\n\n',t)
        new=t.replace('\n',nl)
        if new!=raw:
            open(p,'wb').write(new.encode('utf8')); print('정리',p.split('/')[-4],n,os.path.basename(p),'글자',len(new)-len(raw))
