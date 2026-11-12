# 확정 대본(06_전체과정관찰_다시찍을판.md §2)을 ▸ · ‖ · [기다림]에서 잘라 큐 JSON을 만든다. 글은 대본 그대로, 조작은 아래 표.
import re,json,sys
SRC='/home/user/hyd-iot-edu/workspace/강의제작/제작도구/근거/2026-11-12_통합1-06-포털-다시찍기/06_전체과정관찰_다시찍을판.md'
OUT='/home/user/hyd-iot-edu/workspace/강의제작/제작도구/촬영/포털/전체과정관찰_다시찍기_큐.json'
src=open(SRC,encoding='utf-8').read()
body=src[src.index('## 2. 새 대본 전문'):src.index('# 촬영 본문 끝')]
st=re.split(r'\n### (\d+)\. [^\n]*\n',body)[1:]
raw=[]
for i in range(0,len(st),2):
    s=int(st[i]);txt=st[i+1].strip().replace('\n',' ')
    toks=re.split(r'\s*(▸|‖|\[기다림\])\s*',txt);n=0;cur=''
    for t in toks:
        if t in('▸','‖','[기다림]'):
            if cur.strip():n+=1;raw.append({'stage':s,'n':n,'text':cur.strip(),'after':t})
            else: raw[-1]['after']+='+'+t
            cur=''
        else: cur+=t
    if cur.strip():n+=1;raw.append({'stage':s,'n':n,'text':cur.strip(),'after':'끝'})
SEG={1:1,2:1,3:1,4:2,5:3,6:4,7:4,8:5,9:5,10:6,11:6,12:7,13:7,14:7,15:7}
H='#units [data-asset="HYD-01"]'
def t(css,anchor='after',**k): return dict(css=css,anchor=anchor,**k)
def tx(text,**k): k.setdefault('anchor','after'); return dict(text=text,**k)
A=lambda s:{'at':s}
def P(tg,at=None): return ['point',tg]+([A(at)] if at else [0])
def mid(tg):
    # 누르는 조작은 대상 안쪽을 누른다(글 끝 오른쪽 · 아래 여백을 누르면 맨 위 요소가 대상이 아니다).
    if isinstance(tg,dict) and tg.get('anchor') in ('after','below','margin','right'): tg={**tg,'anchor':'center'}
    return tg
def C(tg,at=None): return ['click',mid(tg)]+([A(at)] if at else [0])
def PH(s,at=None): return ['phrase',s]+([A(at)] if at else [0])
MAP=lambda s:{'text':s,'tag':'text','anchor':'below'}
REC=lambda n,part,anchor='after':t(f'#instRecord [data-cr-steps] > li:nth-child({n}) {part}',anchor)
mproc=lambda sop:f'.mproc:has([data-rel="{sop}"]) > details:first-of-type'
ev=lambda g:f'.mknow .msec:has([data-know-drop="{g}"])'
OPS={
 '01-01':[P(MAP('관제 · 데이터'),'이 그림')],
 '01-02':[P(MAP('현장 설비'))],
 '01-03':[P(MAP('지식 지도 · 에이전트 조치'))],
 '01-04':[P(MAP('승인된 조치 → 검증 → 설비'))],
 '02-01':[C('tab:knowledge','지식 관리 누르'),['waitjs',"[...(document.querySelector('#manualDocumentId')?.options||[])].some(o=>o.textContent.includes('HM-8_cooler-fan-manual.md'))",30]],
 '02-02':[P(t('#manualUpload label.file-picker .btn')),P(t('#providedDocs a[href*="HM-8_cooler-fan"]'),'여기 제공 문서'),['download',t('#providedDocs a[href*="HM-8_cooler-fan"]','center'),'HM-8_cooler-fan-manual.md',A('이름을 누르')]],
 '02-03':[P(t('#manualUpload label.file-picker .btn'),'파일 선택 누르'),['file',t('#manualUpload label.file-picker .btn','center'),'HM-8_cooler-fan-manual.md',A('받은 파일 고르')]],
 '02-04':[P(t('#manualFilename','below'))],
 '02-05':[P(t('#manualBy','below'))],
 '02-06':[P(t('#manualHistory h2.sec'))],
 '02-07':[P(t('#manualHistory .manual-doc .card-title a',contains='HM-8'))],
 '02-08':[P(t('#manualDocumentId','below'),'오른쪽 등록할'),['selectwith',t('#manualDocumentId','below'),['HM-8_cooler-fan-manual.md','문서 개정'],A('골라 주세요')]],
 '02-10':[C(t('#manualPreview','center'),'미리보기 누르'),['wait',t('#manualFullSource'),30]],
 '03-01':[P(t('.mprev > div.muted','below'),'맨 위 줄')],
 '03-03':[P(t('.mprev section.card .chip',contains='수정할 항목'))],
 '03-04':[P(t('.mprev section.card .card-body > ul > li','margin',nth=0),'절차마다')],
 '03-05':[P(t('.mprev section.card .card-body > ul > li','margin',nth=7),'이 절차를')],
 '04-01':[C(t('#manualFullSource','center'),'추출 원문 전체 보기 누르'),['wait',t('#manualSourceText details > summary'),15]],
 '04-02':[C(t('#manualSourceText details > summary','left'),'펼쳐')],
 '04-03':[PH('## HM-8.1'),PH('## HM-8.2','갈아 끼우는')],
 '04-04':[PH('1. 설비를 정지하고 현장 패널에서 LOCAL로 전환한다.'),PH('1. LOCAL 전환과 잠금','현장 제어는')],
 '04-05':[PH('## HM-8.3')],
 '04-06':[PH('| 유온 TS1','하나는 기름'),PH('| 냉각 효율 CE','또 하나는')],
 '04-07':[PH('유온이 55 ℃를 넘고','유온이 오십오 도를 넘고')],
 '04-08':[PH('## HM-8.4')],
 '04-09':[PH('- 쿨러 핀 오염','첫째는')],
 '04-10':[PH('(사전 확률 0.6)')],
 '04-11':[PH('- 주변 온도 상승')],
 '04-12':[PH('- 팬 구동 불량')],
 '04-13':[PH('최근 2분 팬 진동 VS1 평균이 0.9 mm/s 미만','핀 오염이면'),PH('VS1 평균이 0.9 mm/s 이상','팬 구동 불량이면')],
 '04-14':[PH('## HM-8.5')],
 '04-15':[PH('원격 조치는 PLC 운전 모드가 REMOTE_AUTO일 때만 한다.','멀리서 명령으로')],
 '04-16':[PH('승인: 운전원. 생산은 그대로 유지된다.')],
 '04-17':[PH('## HM-8.6')],
 '04-18':[PH('조치 뒤 15분 동안 TS1이 55 ℃ 미만','유온이 오십오')],
 '04-19':[PH('## HM-8.7')],
 '04-20':[PH('### SOP-COOL-14 쿨러 핀 세척','급한 불은')],
 '04-21':[PH('## HM-8.8')],
 '05-01':[C(t('#manualAgentExtract','center'),'추출 제안 준비 누르'),['waittext','진행 · 결과 확인을 누르세요',60]],
 '05-02':[P(t('#manualAgentStatus')),['clickuntil',t('#manualAgentResult','center'),"document.querySelectorAll('.mproc').length>0",A('결과 확인 누르')]],
 '05-03':[P(t('.mprev > div.muted','below'))],
 '05-04':[P(t('.mprev > details:first-of-type > summary'))],
 '05-05':[['open',t('.mprev > details:first-of-type > summary','left'),0]],
 '05-06':[P(t('.mprev > details:first-of-type li','margin',nth=0),'하나는')],
 '05-07':[P(t('.mprev > details:first-of-type li','margin',nth=1))],
 '05-08':[P(t('.mprev > details:first-of-type li','margin',nth=2))],
 '05-09':[P(t('.mprev section.card .card-body > ul > li','margin',contains='벨트 교체'),'검사 칸을')],
 '06-01':[P(tx('매뉴얼 절',tag='h3'),'아래 왼쪽은'),P(tx('등록할 조치 방법',tag='h3'),'오른쪽 등록할')],
 '06-02':[P(t('[data-manual-name="SOP-FAN-11"]','right')),P(t('[data-manual-name="SOP-FAN-12"]','right'),'벨트 교체')],
 '06-03':[P(t('[data-rel="SOP-FAN-12"]','below'),'관계는'),P(t('[data-kind="SOP-FAN-12"]','below'),'종류는')],
 '06-04':[P(t('[data-manual-name="SOP-COOL-11"]','right'))],
 '06-05':[P(t('[data-fm="SOP-COOL-11"]','below'))],
 '06-06':[P(t('[data-rel="SOP-COOL-11"]','below')),P(t('[data-kind="SOP-COOL-11"]','below'),'종류는')],
 '06-07':[['open',t(mproc('SOP-COOL-11')+' > summary','left'),A('원문 인용 눌러')]],
 '06-08':[P(t(mproc('SOP-COOL-11')+' pre','left')),P(t('[data-manual-step="SOP-COOL-11"][data-order="1"]','right'),'밑의 작업 순서')],
 '06-10':[P(t('[data-rel="SOP-COOL-12"]','below')),P(t('[data-rel="SOP-COOL-13"]','below'),'즉시 완화로')],
 '06-11':[P(t('[data-manual-name="SOP-COOL-14"]','right'))],
 '06-12':[P(t('[data-rel="SOP-COOL-14"]','below')),P(t('[data-kind="SOP-COOL-14"]','below'),'종류가')],
 '06-13':[P(t('[data-manual-step="SOP-COOL-14"][data-order="1"]','right'))],
 '06-14':[P(t('[data-rel="SOP-COOL-15"]','below'),'환기 보강')],
 '07-01':[P(tx('추출한 지식 후보',tag='h3'))],
 '07-02':[P(t('.mknow h4',contains='고장 유형'))],
 '07-03':[P(t('.mknow h4',contains='원인'))],
 '07-04':[['open',t(ev('causes')+' > details > summary','left',nth=0),A('원문 인용을 눌러')]],
 '07-05':[P(t(ev('causes')+' > details pre','left',nth=0))],
 '07-06':[P(t('.mknow h4',contains='확인 증거'))],
 '07-07':[P(t(ev('evidence')+' > div.muted',nth=0))],
 '07-08':[P(t(ev('evidence')+' > div.muted',nth=1))],
 '07-09':[P(t(ev('evidence')+' > div.muted',nth=3),'두 줄도')],
 '07-10':[P(t('.mknow h4',contains='규칙')),P(t(ev('rules')+' > div.muted',nth=0),'여기 쿨러 성능 저하')],
 '07-11':[P(t(ev('rules')+' > b',nth=0))],
 '07-12':[P(t(ev('rules')+' > b',nth=1))],
 '07-13':[P(t(ev('rules')+' > b',nth=3),'원인마다'),P(t(ev('rules')+' > b',nth=5),'원격 자동이 아니면')],
 '07-14':[P(t(ev('rules')+' label.check',nth=0),'제외 칸은')],
 '08-01':[C(t('#manualReviewed','center'),'체크해')],
 '08-02':[C(t('#manualCommit','center'),'적재 누르'),['waitjs',"/적재 완료/.test(document.querySelector('#manualMsg')?.textContent||'')",90]],
 '08-03':[P(t('#manualMsg','below'))],
 '08-05':[P(t('#manualHistory .manual-doc .card-title a',nth=0),'맨 위에'),P(t('#manualHistory .manual-doc .card-chips .chip',nth=0),'현재 판본으로')],
 '09-01':[C('tab:ontology','지식 지도 누르'),['wait',t('#ontoSearch'),30]],
 '09-02':[C(t('#ontoSearch','center'),'검색 칸에'),['type','쿨러',A('쿨러라고')]],
 '09-03':[['wait',t('[data-id="fm:cooler-cooling-loss"]','center'),15],C(t('[data-id="fm:cooler-cooling-loss"]','center'),'쿨러 냉각 성능 상실 누르')],
 '09-04':[P(t('#ontoNode h3'))],
 '09-05':[P(t('#ontoNode h4',nth=1),'아래 들어오는 쪽부터')],
 '09-06':[P(t('#ontoNode a[data-go]',contains='핀 오염')),P(t('#ontoNode a[data-go]',contains='팬 구동 불량'),'팬 구동 불량이')],
 '09-07':[P(t('#ontoNode a[data-go]',contains='유온 상승')),P(t('#ontoNode a[data-go]',contains='냉각 효율 저하'),'냉각 효율 저하가')],
 '09-08':[P(t('#ontoNode h4',nth=0)),P(tx('팬 최대 운전',tag='a',within='#ontoNode'),'팬 최대 운전,'),P(tx('쿨러 핀 세척',tag='a',within='#ontoNode'),'쿨러 핀 세척 같은'),P(t('#ontoNode a[data-go]',contains='오일 쿨러'),'오일 쿨러도')],
 '09-09':[P(t('#ontoNode a[data-go]',contains='유온 상승'),'증상에서 출발'),P(t('#ontoNode h3'),'이 고장을 찾고'),P(t('#ontoNode a[data-go]',contains='핀 오염'),'원인을 찾고'),P(tx('팬 최대 운전',tag='a',within='#ontoNode'),'조치를 꺼내')],
 '10-01':[C('tab:scenario','결함 시뮬레이션 누르'),['wait',t(H),20]],
 '10-02':[P(t(H+' .big.num'),'유온은')],
 '10-03':[P(t(H+' .kv em.ce'))],
 '10-04':[P(t(H+' .kv em.vs1'))],
 '10-05':[P(t(H+' header .mode','below'))],
 '10-06':[C(t(H+' button[data-act="degrade"]','center'),'쿨러 열화 주입을'),['scroll',t(H+' header','left',top=96),A('눌러 주세요')]],
 '10-07':[P(t(H+' .kv em.health'))],
 '10-08':[P(t(H+' .kv em.ce'),'위의 냉각 효율'),['waitjs',f"parseFloat(document.querySelector('{H} .kv em.ce')?.textContent)<70",60]],
 '10-10':[P(t(H+' .kv em.vs1'))],
 '10-11':[P(t(H+' .big.num'),'맨 위 유온')],
 '10-12':[P(t(H+' .bar','below')),['waitjs',f"/이상 징후|경보 발생/.test(document.querySelector('{H} .kv em.phase')?.textContent||'')",180]],
 '10-13':[P(t(H+' .kv em.phase'),'아래 경보 칸')],
 '10-14':[['waitjs',f"(document.querySelector('{H} .kv em.phase')?.textContent||'').includes('경보 발생')",60]],
 '11-01':[C('tab:instances','처리 건 누르'),['wait',t('#todoList .item strong',nth=0),60]],
 '11-02':[P(t('#todoList .item strong',nth=0))],
 '11-03':[P(t('#todoPanel h3',nth=0))],
 '11-04':[P(t('#instList [data-inst^="c3_cooling."] strong',nth=0)),P(t('#instList [data-inst] strong',nth=1),'그 밑의 건은')],
 '11-05':[P(t('#instDetail .td-now'))],
 '11-06':[P(MAP('쿨러 과열 경보'))],
 '11-07':[P(dict(text='원인 진단',tag='text',within='#instDetail',anchor='below'),'원인 진단'),P(dict(text='냉각 조치 제안',tag='text',within='#instDetail',anchor='below'),'냉각 조치 제안이')],
 '11-08':[P(dict(text='운전원 승인',tag='text',within='#instDetail',anchor='below',nth=0),'운전원 승인에서'),P(t('#instDetail .td-now'),'위에도')],
 '12-01':[P(t('#todoPanel h3',nth=0))],
 '12-02':[P(t('#todoPanel [data-approval-until]'),'지연 알림')],
 '12-03':[P(t('#todoPanel .ap-title'),'맨 위에')],
 '12-04':[P(t('#todoPanel .ap-reasons li',nth=0))],
 '12-05':[P(t('#todoPanel .ap-reasons li',nth=1),'좋아지는 건'),P(t('#todoPanel .ap-reasons li',nth=2),'감수할 건')],
 '12-06':[P(t('#todoPanel .ap-do .ap-label'))],
 '12-07':[P(t('#todoPanel .ap-evidence .ap-row .ap-label',nth=1))],
 '12-08':[['open',t('#todoPanel .ap-card > details:has(.ap-lost-list) > summary','left'),A('펼쳐 보면')]],
 '12-09':[P(t('#todoPanel .ap-lost-head b',nth=0)),P(t('#todoPanel .ap-lost-head b',nth=1),'생산이 줄어서')],
 '12-10':[P(t('#todoPanel .ap-lost-head b',nth=2))],
 '12-11':[P(t('#todoPanel .ap-switch',nth=0),'이 안으로 바꾸기')],
 '12-12':[P(t('#tdGo','center'),'승인 버튼')],
 '12-13':[P(t('#todoPanel .field-hint',contains='먼저 나를')),C('tab:inbox','내 작업함 누르')],
 '12-14':[['select',t('select[data-inbox-me]','right'),'user:choi-op',A('최운전')]],
 '12-15':[['wait',t('[data-inbox-link]',nth=0),60],P(t('[data-inbox-link]',nth=0)),C('tab:instances','처리 건으로')],
 '12-16':[['wait',t('#todoPanel .field.ro .ro-value',contains='최운전'),60],P(t('#todoPanel .field.ro .ro-value',contains='최운전'))],
 '12-17':[P(t('#tdGo','center')),P(t('#todoPanel textarea','left'),'사유는'),C(t('#tdGo','center'),'승인 누르')],
 '13-01':[['stepmark','운전원 승인',A('아래 처리 과정')]],
 '13-02':[['stepmark','운전원 승인',0],['stepmark','승인 지연',A('지연 알림은')]],
 '13-03':[['stepmark','냉각 명령',0]],
 '13-04':[['stepmark','재관측',0]],
 '13-05':[P(t('#instDetail .td-now'),'남은 시간이'),['waitjs',"(document.querySelector('#instDetail .td-now')?.textContent||'').trim()==='끝'",240]],
 '13-06':[P(t('#instDetail .td-now'))],
 '14-01':[C(t('[data-inst-tab=record]','center'),'처리 기록 탭 누르'),['wait',REC(1,'.cr-title'),30]],
 '14-03':[P(REC(1,'.cr-title'))],
 '14-04':[P(REC(1,'.cr-chips','left'))],
 '14-05':[P(REC(2,'.cr-title'))],
 '14-06':[P(REC(2,'.cr-sentence','margin')),C(tx('모두 펼치기',tag='button',within='#instRecord',anchor='center'),'모두 펼치기 누르')],
 '14-07':[P(t('#instRecord .cr-sec > summary, #instRecord .cr-sec-body > h6',contains='지식 경로'),'지식 경로를')],
 '14-09':[P(t('#instRecord .cr-sec > summary, #instRecord .cr-sec-body > h6',contains='원인 후보와 증거')),P(t('#instRecord .cr-sec-body:has(> h6) tr','margin',contains='쿨러 핀 오염'),'핀 오염 줄은')],
 '14-10':[P(t('#instRecord .cr-sec-body:has(> h6) tr','margin',contains='주변 온도'))],
 '14-12':[P(t('#instRecord .cr-sec > summary, #instRecord .cr-sec-body > h6',contains='추천안에 이른 길'))],
 '14-14':[P(REC(3,'.cr-title'))],
 '14-15':[P(REC(3,'.cr-sentence','margin'))],
 '14-16':[P(REC(3,'.cr-sec-body > ul.cr-list > li','margin')|{'contains':'쿨러 팬 속도'})],
 '14-17':[P(REC(4,'.cr-title'))],
 '14-18':[P(REC(4,'.cr-sentence','margin'))],
 '14-19':[P(REC(5,'.cr-title'))],
 '14-20':[P(REC(5,'.cr-sentence','margin'))],
 '14-21':[P(REC(6,'.cr-title'))],
 '14-22':[P(REC(6,'.cr-sentence','margin'))],
 '14-23':[P(REC(7,'.cr-title'))],
 '14-24':[P(REC(7,'.cr-sentence','margin')),P('top:알림','알림 종')],
 '15-01':[C(t('[data-inst-tab="result"]','center'),'결과 탭 누르'),['wait',t('[data-open-record]'),30]],
 '15-02':[P(t('#instDetail .rr-badge')),P(t('#instDetail .rr-val',nth=0),'유온이'),P(t('#instDetail .rr-val',nth=1),'경보 해제')],
 '15-03':[P(t('#instDetail .rr-who .ap-label')),P(t('#instDetail .rr-steps-wrap .ap-label'),'시스템이 한 일')],
}
# 앞 큐 끝 표시에 따른 쉼(영상 V-14 1회차 값): ▸ 잇기 0.5초, ‖ 큐 1.0초, 조작 결과 뒤(▸+‖) 1.5초, 기다림 뒤 1.5초
def gap(prev):
    if prev is None: return 1000
    a=prev['after']
    if '[기다림]' in a: return 1500
    if '▸' in a and '‖' in a: return 1500
    if '‖' in a or a=='끝': return 1000
    return 500
cues=[];used=set();prev=None
for c in raw:
    k=f"{c['stage']:02d}-{c['n']:02d}";used.add(k)
    ops=OPS.get(k,[])
    for o in ops:
        v=o[-1]
        if isinstance(v,dict) and 'at' in v and v['at'] not in c['text']: sys.exit(f'{k}: 대사에 없는 구절 {v["at"]}')
    cues.append({'id':'o'+k.replace('-',''),'segment':SEG[c['stage']],'gap':gap(prev),'mark':c['after'],'text':c['text'],'ops':ops})
    prev=c
bad=set(OPS)-used
if bad: sys.exit('없는 큐: '+str(sorted(bad)))
d={'note':'1회차 실습 06 전체과정관찰 다시 찍는 판. 글은 확정 대본(06_전체과정관찰_다시찍을판.md, 커밋 c382d773) §2를 ▸ · ‖ · [기다림]에서 자른 것 그대로다. 조작 형식은 촬영도구/segs/one06.mjs 머리말. gap은 앞 큐와의 쉼(ms, 영상 V-14 1회차 값), mark는 대본의 끝 표시.','voice_id':'1PdAOcPlPTz12RwMyFVp','model_id':'eleven_v4','cues':cues}
open(OUT,'w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False,indent=1)+'\n')
print(len(cues),'큐 · 구간별',{s:sum(1 for c in cues if c['segment']==s) for s in range(1,8)},'· 글자',sum(len(c['text']) for c in cues))
