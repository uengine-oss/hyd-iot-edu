import json,glob,os,collections,re,sys
W=sys.argv[1]
tot=collections.Counter()
for p in sorted(glob.glob(W+'/점검/*.json')):
    d=json.load(open(p,encoding='utf-8')); n=os.path.basename(p)[:-5]; L=d['고칠것']
    c=collections.Counter(x['종류'] for x in L); g=collections.Counter(x.get('고침') for x in L)
    note=sum(1 for x in L if x.get('노트전') or x.get('노트후')); noteonly=sum(1 for x in L if not x.get('전') and (x.get('노트전') or x.get('노트후')))
    print(n,'고칠',len(L),dict(c),'|고침',dict(g),'|노트',note,'노트만',noteonly,'|글자',sum(x.get('글자증감',0) or 0 for x in L),'|장',len({x['장'] for x in L}),'|남김',len(d['남김']),'|딴',len(d['딴문제']))
    tot.update(c); tot['합']+=len(L)
    for x in L:
        if x.get('고침')=='요소순서' or ('요소' in str(x.get('고침'))): print('  요소:',x['번호'],x['장'],x['어긋남'][:140])
    for x in d['딴문제']: print('  딴:',x.get('장'),str(x.get('내용'))[:170])
    for x in d.get('못본것',[]): print('  못:',str(x)[:110])
    for x in L:
        s=json.dumps(x,ensure_ascii=False)
        if re.search(r'먼저 적용|한 번에|함께 처리|보다 먼저|함께 적용',s): print('  선후:',x['번호'],[k for k in x if k not in('번호','종류','파일','장','줄','어긋남','근거','고침','전','후','노트전','노트후','글자증감')], (x.get('비고') or x.get('메모') or '')[:100])
print(dict(tot))
