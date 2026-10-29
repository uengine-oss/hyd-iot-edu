# 화면이 바뀐 시각과 시간표의 장 시작 시각(묶음 구획은 넘김 시각까지)을 대조한다
# 시간표의 시작 시각은 초 아래를 버린 값이라, 화면이 그 시각부터 1초 안에 바뀌면 맞은 것으로 본다
import sys,re,subprocess
v,t=sys.argv[1],sys.argv[2]
o=subprocess.run(['ffmpeg','-i',v,'-vf',"select='gt(scene,0.02)',showinfo",'-f','null','-'],capture_output=True,text=True).stderr
got=[float(x) for x in re.findall(r'pts_time:([\d.]+)',o)]
exp=[]
for line in open(t,encoding='utf-8'):
    m=re.match(r'\| [\d~]+ \| (\d+):(\d+)(?: \(SLIDE \d+부터 (\d+):([\d.]+)\))? \|',line)
    if m:
        exp.append(int(m[1])*60+int(m[2]))
        if m[3]: exp.append(int(m[3])*60+float(m[4]))
exp=exp[1:]
miss=[e for e in exp if not any(-0.2<g-e<1.05 for g in got)]
extra=[g for g in got if not any(-0.2<g-e<1.05 for e in exp)]
print(f'장 넘김 기대 {len(exp)} · 화면 바뀜 {len(got)} · 못 맞춘 기대 {len(miss)} {miss[:10]} · 기대 밖 바뀜 {len(extra)} {[round(x,1) for x in extra[:10]]}')
