import sys,re
lst=open(sys.argv[1],encoding='utf-8').read()
prop=open(sys.argv[2],encoding='utf-8').read()
new=open(sys.argv[3],encoding='utf-8').read()
tong=open(sys.argv[4],encoding='utf-8').read()
rows=[l for l in lst.split('\n') if re.match(r'^\| \d+ \| 실전반 01 \|',l)]
ok=True
for r in rows:
    c=[x.strip() for x in r.strip('|').split(' | ')]
    no,_,sl,kind,before,after=c[:6]
    nb=prop.count(before); nn=new.count(before)
    if after.startswith('(문단 삭제'):
        good = nb==1 and nn==0
        print(no,sl,kind,'삭제', '제안본',nb,'손질본',nn, 'OK' if good else 'NG')
    else:
        na=new.count(after); nt=tong.count(before)
        good = nb==1 and nn==0 and na==1
        print(no,sl,kind,'제안본(전)',nb,'손질본(전)',nn,'손질본(후)',na,'통합반(전)',nt,'OK' if good else 'NG')
    ok&=good
print('ALL OK' if ok else 'FAIL', len(rows),'rows')
