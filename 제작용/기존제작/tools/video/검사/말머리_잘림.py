# 넣은 쉼(완전 무음 0) 바로 앞 20ms에 말소리가 있는지 = 말머리가 잘린 자리
import sys,subprocess,array,math
v=sys.argv[1]
raw=subprocess.run(['ffmpeg','-v','error','-i',v,'-ac','1','-ar','44100','-f','s16le','-'],capture_output=True).stdout
d=array.array('h',raw); fr=44100; n=len(d); i=0; bad=[]; tot=0
while i<n:
    if d[i]==0:
        j=i
        while j<n and d[j]==0: j+=1
        if (j-i)/fr>=0.1:
            tot+=1; w=d[max(0,i-882):i]; r=math.sqrt(sum(x*x for x in w)/max(1,len(w)))
            if r>1000: bad.append((round(i/fr,2),int(r)))
        i=j
    else: i+=1
print('넣은 쉼',tot,'곳 · 앞이 말소리인 자리',len(bad)); print(bad[:40])
