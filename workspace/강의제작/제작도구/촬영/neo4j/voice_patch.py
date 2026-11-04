"""Neo4j 2회차 04 — 바꾼 큐 자리만 새 음성으로 바꾼다(화면 영상은 복사). 원래 소리는 음성 캐시를 자막 시각에 놓은 것과 같다(큐별 상관 1.0, 0.3 ms 안).
새 음성은 원래 시작 자리에(조작이 그대로라), 이득은 그 큐의 옛 음성과 원래 소리로 맞춘다. 다음 말과 겹치면 멈춘다.
사용: python3 patch.py <옛.mp4> <옛.srt> <새 큐.json> <옛 음성 폴더> <새 음성 폴더> <출력.mp4> <출력.srt> <큐 id,…>"""
import json,sys,subprocess,numpy as np
mp4,srt,cuef,oldd,newd,out,outsrt,ids=sys.argv[1:9]; ids=ids.split(','); SR=44100
dec=lambda p:np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',p,'-map','0:a:0','-f','s16le','-ac','1','-ar',str(SR),'-']),np.int16).astype(np.float32)
def t(x):h,m,r=x.split(':');s,ms=r.split(',');return int(h)*3600+int(m)*60+int(s)+int(ms)/1000
def f(v):h=int(v//3600);m=int(v%3600//60);s=v%60;return f"{h:02}:{m:02}:{int(s):02},{int(round((s-int(s))*1000)):03}"
o=dec(mp4); y=o.copy(); cues=json.load(open(cuef))['cues']; S=open(srt,encoding='utf-8').read().strip().split('\n\n')
prev_end=0
T=[[t(x) for x in b.split('\n')[1].split(' --> ')] for b in S]; outS=[]
for k,(c,b) in enumerate(zip(cues,S)):
    a,e=T[k]
    if c['id'] not in ids: outS.append(b); prev_end=int(round(e*SR)); continue
    ov=dec(f"{oldd}/{c['id']}.mp3"); nv=dec(f"{newd}/{c['id']}.mp3"); s0=int(round(a*SR))
    best=max(range(-40,41),key=lambda L:float(np.dot(o[s0+L:s0+L+len(ov)],ov)))
    seg=o[s0+best:s0+best+len(ov)]; g=float(np.dot(seg,ov)/np.dot(ov,ov)); corr=float(np.dot(seg,ov)/(np.linalg.norm(seg)*np.linalg.norm(ov)))
    nxt=int(round(T[k+1][0]*SR)) if k+1<len(T) else len(o); prv=prev_end+int(0.15*SR)
    st=s0+best
    if st+len(nv)>nxt-int(0.15*SR): st=nxt-int(0.15*SR)-len(nv)          # 길어진 음성은 앞의 빈 시간으로 당긴다
    if st<prv: raise SystemExit(f"{c['id']}: 새 음성이 앞뒤 말 사이에 들어가지 않음")
    y[s0+best:s0+best+len(ov)]-=g*ov; y[st:st+len(nv)]+=g*nv; prev_end=st+len(nv)
    a=st/SR; ne=a+len(nv)/SR; L=b.split('\n'); outS.append('\n'.join([L[0],f"{f(a)} --> {f(ne)}",c['text']]))
    print(c['id'],'corr',round(corr,4),'gain',round(g,3),'lag',best,'old',round(e-a,2),'new',round(len(nv)/SR,2))
pk=np.max(np.abs(y)); assert pk<32767,'clip'
subprocess.run(['ffmpeg','-v','error','-y','-i',mp4,'-f','s16le','-ar',str(SR),'-ac','1','-i','-','-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k',out],input=y.astype(np.int16).tobytes(),check=True)
open(outsrt,'w',encoding='utf-8').write('\n\n'.join(outS)+'\n'); print('ok peak',int(pk))
