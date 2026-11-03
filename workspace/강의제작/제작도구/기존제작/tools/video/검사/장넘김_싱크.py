# 화면이 바뀐 시각과 시간표의 장 시작 시각(묶음 구획은 넘김 시각까지)을 대조한다
# 시간표의 시작 시각은 초 아래를 버린 값이라, 화면이 그 시각부터 1초 안에 바뀌면 맞은 것으로 본다
# 장 조각은 장마다 따로 인코딩해 잇는다(강의영상.py) — 장 시작은 키프레임이라 키프레임끼리의 바뀜부터 잰다
# 키프레임 점수는 못 맞춤만 낳으므로(거짓 통과 없음), 거기서 못 맞춘 장 시작과 조각 안의 묶음 넘김은 둘레 2.4초를 다 풀어 확인한다
import sys,re,subprocess
v,t=sys.argv[1],sys.argv[2]
def scene(*a):
    o=subprocess.run(['ffmpeg',*a,'-an','-vf',"select='gt(scene,0.02)',showinfo",'-f','null','-'],capture_output=True,text=True).stderr
    return [float(x) for x in re.findall(r'pts_time:([\d.]+)',o)]
def hit(e,got): return any(-0.2<g-e<1.05 for g in got)
starts,inner=[],[]
for line in open(t,encoding='utf-8'):
    m=re.match(r'\| [\d~]+ \| (\d+):(\d+)(?: \(SLIDE \d+부터 (\d+):([\d.]+)\))? \|',line)
    if m:
        starts.append(int(m[1])*60+int(m[2]))
        if m[3]: inner.append(int(m[3])*60+float(m[4]))
starts=starts[1:]
key=scene('-skip_frame','nokey','-i',v)
look=[e for e in starts if not hit(e,key)]+inner
win=[]
for e in look:
    a=max(0,e-1)
    win+=[a+g for g in scene('-ss',f'{a:.3f}','-i',v,'-t','2.4')]
miss=[e for e in starts+inner if not hit(e,key+win)]
print(f'장 넘김 기대 {len(starts)+len(inner)} · 둘레를 다 푼 곳 {len(look)} · 못 맞춘 기대 {len(miss)} {miss[:10]}')
