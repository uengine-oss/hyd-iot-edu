"""2회차 문서 조립. 실습·시스템 실행 없음. 통합반 원본 경로를 인자로 받는다."""
from pathlib import Path
import re,json,shutil,sys
D=Path(__file__).resolve().parents[4]; C=Path(sys.argv[1])
I=C/'산출물/교재/대본/통합반_온라인/02회차'
P=D/'산출물/교재/대본/실전반_온라인/02회차';P.mkdir(parents=True,exist_ok=True)
OUT=D/'만들기/decks/practical/day02';OUT.mkdir(parents=True,exist_ok=True)
def blocks(t,pattern):return re.split(pattern,t,flags=re.M)[1:]
def speechblocks(folder):
 out={}
 for f in sorted(folder.glob('*_이론_*.md')):
  for b in blocks(f.read_text('utf8'),r'(?=^## \[SLIDE )'):
   m=re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]',b);out[int(m[1])]=(int(m[2] or m[1]),b.rstrip().removesuffix('---').rstrip())
 return out
S2=speechblocks(I);S3=speechblocks(C/'산출물/교재/대본/통합반_온라인/03회차')
def loaddeck(day):return blocks((C/f'만들기/decks/integrated/day{day:02}/통합반_{day:02}일차.md').read_text('utf8'),r'(?=^## SLIDE )')
G2=loaddeck(2);G3=loaddeck(3)
mapping=[(2,n) for n in range(1,66)]+[(3,n) for n in range(4,34)]+[(0,96),(0,97),(2,66),(2,67),(0,100),(2,68),(2,69),(2,70),(2,71),(0,105),(2,72),(0,107)]
assert len(mapping)==107
new={
96:('실습: 조치 허용·제외 조건표','- 유형: 간지\n- 구분: 실습\n- 부제: 원문 조건을 표로 옮기고 경계값과 겹치는 조건을 대조한다','그래프의 대상과 관계를 설계한 데 이어, 이제 조치를 판단하는 조건을 만들어 보겠습니다. 작업 기준 자료를 내려받고 폴더를 연 뒤, 조건표와 사례별 판단 기록을 직접 작성하겠습니다.'),
97:('조건표와 판단 근거 확인','- 유형: 카드\n- 메시지: 작업 순서는 보존하고, 판단 조건과 적용 결과를 별도로 남긴다.\n- 요소:\n  1. 원문에서 조건 찾기 | 온도 · 압력 · 운전 모드 · 설비 상태 / 단위와 비교 범위를 함께 기록 | 근거\n  2. 조건표 작성 | 입력 · 연산자 · 기준 · 적용 조치 · 출력 / 허용 · 제외 · 보류를 구별 | 결과물\n  3. 경계와 중첩 확인 | 기준값 바로 아래 · 같은 값 · 바로 위 / 여러 제외 사유와 입력 누락을 함께 검사 | 검토\n  4. **절차와 연결** | 조건을 통과해도 승인과 작업 단계는 남는다 / 원문 절과 검토 기록을 저장하고 다시 연다 | 마무리','먼저 자료의 작업 순서와 판단 조건을 구별하겠습니다. 조건은 입력, 비교 연산자, 기준값과 단위, 적용할 조치, 결과로 나누어 적습니다. 온도와 압력의 경계값을 대입하고, 운전 모드와 설비 상태가 동시에 걸리는 경우도 확인하겠습니다. 입력이 없으면 허용으로 넘기지 않고 보류합니다. 결과만 적지 않고 어느 원문 조건 때문에 제외했는지 남기겠습니다.\n\n> [제작: 실습 5 삽입] 09_실습_조치조건표.md를 진행한 뒤 98장부터 재개. 실제 확인한 결과만 발화한다.'),
100:('절차와 판단의 핵심 용어','- 유형: 표\n- 메시지: 작업 순서, 판단 규칙, 실행 기록의 역할을 구별한다.\n- 머리: 용어 | 정식 명칭 · 풀이\n- 요소:\n  1. SOP | Standard Operating Procedure / 작업 순서와 수행 기준을 정한 표준 작업 절차\n  2. DMN | Decision Model and Notation / 업무의 의사결정을 표현하는 모델과 표기 표준\n  3. 결정표 | Decision Table / 입력 조건에 따른 출력을 행으로 나타낸 표\n  4. Hit Policy | 여러 행이 맞을 때 결과를 처리하는 정책\n  5. Step · Action | 사람이 수행하는 작업 단계 · 시스템이 실행하는 명령 또는 업무 처리','절차와 판단에서 사용한 용어도 정리하겠습니다. SOP는 작업 순서와 수행 기준을 정하고, DMN은 업무의 의사결정을 표현하는 표준입니다. 결정표는 입력 조건과 출력을 행으로 적은 것이고, 여러 행이 맞으면 Hit Policy에 따라 처리합니다. HYD는 표준 엔진 전체를 쓰는 것이 아니라 앞에서 본 비교 검사와 평가 함수를 사용합니다. 작업 단계인 Step과 실제 명령이나 업무 처리인 Action도 구별해야 합니다. 조건 통과, 승인, 명령 처리, 현장 정비 완료는 각각 확인할 기록이 다릅니다.'),
105:('Quiz 4. 조건 통과와 작업 수행','- 유형: 문답\n- 메시지: 추천 시점에는 원격 자동 · 운전 중 조건을 통과했다. 승인 직전에 현장 모드가 수동으로 바뀌었다.\n- 문장: 절차와 판단의 관계에 맞는 처리는?\n- 요소:\n  1. 추천 때 통과했으므로 그대로 명령을 보낸다\n  2. 현재 조건을 다시 확인해 원격 조치를 제외하고 근거를 남긴다\n  3. 결정표가 있으므로 SOP의 확인 단계를 지운다\n  4. 제외됐으므로 현장 정비까지 완료로 기록한다','네 번째 문제입니다. 추천 때는 원격 자동이고 운전 중이었지만, 승인 직전에 현장 모드가 수동으로 바뀌었습니다. 첫째, 추천 때 통과했으니 명령을 보냅니다. 둘째, 현재 조건을 다시 확인해 원격 조치를 제외하고 근거를 남깁니다. 셋째, 결정표가 있으니 SOP의 확인 단계를 지웁니다. 넷째, 제외됐으니 현장 정비도 완료로 적습니다. 어떤 처리가 절차와 판단의 역할에 맞는지 골라 보세요.\n\n> [대기 20초] 판단 시점과 작업 단계의 관계를 확인한다.'),
107:('조건 판단의 정답과 회차 마무리','- 유형: 표\n- 메시지: 조건표의 판단은 해당 시점의 입력에 대한 결과이며 작업 완료를 대신하지 않는다.\n- 머리: 문항 | 판단 기준 | 정답\n- 요소:\n  1. Quiz 4 | 승인 직전의 모드와 상태를 다시 검사한다. 수동이면 원격 조치를 제외하고 근거를 남긴다. | 2번\n  2. 절차와 기록 | SOP의 확인 · 승인 · 현장 작업은 조건표와 별도로 수행하고 기록한다. | 역할 구별','네 번째 정답은 2번입니다. 추천할 때 확인한 값이 승인할 때도 같다고 보장할 수는 없습니다. 현재 모드가 수동이면 원격 조치를 제외하고, 어떤 조건이 맞았는지 기록합니다. 결정표가 생겨도 현장에서 확인하는 단계는 남습니다. 제외는 그 조치를 실행하지 않는다는 판단이지 정비가 끝났다는 뜻이 아닙니다.\n\n이번 회차에서는 현장 정보를 구조로 정의하고 저장한 뒤, 그 지식에 작업 절차와 판단 조건을 연결했습니다. 다음 회차에서는 조건을 통과한 후보들의 효과와 비용을 비교할 기준으로 이어가겠습니다. 수고 많으셨습니다.')}
new[105]=(new[105][0],new[105][1].replace('조건을 통과했다. 승인 직전에','조건을 통과했지만 승인 직전에'),new[105][2])
new[97]=(new[97][0],new[97][1].replace('허용 · 제외 · 보류를 구별','경고 · 감점 · 제외와 보류를 구별'),new[97][2].replace('허용하거나','허용하거나').replace('온도와 압력의 경계값을 대입하고,','경고·감점·제외를 구별하며 온도와 압력의 경계값을 대입하고,'))
decks=[];scripts={};edits=[]
for dest,(day,n) in enumerate(mapping,1):
 if day:
  g=(G2 if day==2 else G3)[n-1];ss=S2 if day==2 else S3
  g=re.sub(r'^## SLIDE \d+',f'## SLIDE {dest:02}',g)
  g=g.replace('figures/',f'figures/day{day:02}/')
  if day==3:g=re.sub(r'(?m)^- 번호: (\d+)',lambda m:f'- 번호: {int(m[1])+8:02}',g)
  if n in ss:
   end,b=ss[n];b=re.sub(r'^## \[SLIDE \d+(?:~\d+)?\]',f'## [SLIDE {dest}'+(f'~{dest+end-n}' if end!=n else '')+']',b)
   original=b
   if day==3:
    b=b.replace('다음 시간에는 두 번째 물음','이어서 두 번째 물음').replace('앞 회차','앞부분').replace('첫 번째 단원','아홉 번째 단원').replace('두 번째 단원','열 번째 단원').replace('세 번째 단원','열한 번째 단원').replace('네 번째 단원','열두 번째 단원').replace('다섯 번째 단원','열세 번째 단원')
    if n==16:b=b.replace('이번 시간에는 이번 회차의 두 번째 물음','이제 두 번째 물음').replace('앞 시간에는','앞에서').replace('이번 시간에는 매뉴얼','이어서 매뉴얼')
    if n==4:b=b.replace('첫 단원은 작업 절차와 수행 조건입니다.','지식을 구조로 만들었으니, 아홉 번째 단원에서는 작업 절차와 수행 조건을 연결하겠습니다.').replace('팬을 올리기 전에는 뭘 확인해야 할까요? 올린 뒤에는 뭘 보고 작업이 끝났다고 판단할까요? 그리고 같은 조치를 지금 해도 되는지는 뭐가 정할까요?','팬을 올리기 전의 확인 조건, 조치 뒤 완료 판단, 지금 수행해도 되는지를 가르는 기준을 구별하겠습니다.')
    if n==33:b=b.replace('다음 시간에는 세 번째 물음, 규칙을 통과한 후보 가운데 무엇이 더 나은지를 다룹니다. 성과를 여러 관점에서 보는 BSC와 그 목표를 재는 KPI로, 후보를 견줄 기준부터 세웁니다.','이제 작업 기준에서 조건을 찾아 표로 옮겨 보겠습니다. 규칙을 통과한 후보들의 성과를 비교하는 BSC와 KPI는 다음 회차에 이어집니다.')
   if day==2 and n==66:b=b.replace('설계한 지식을 그래프에 넣고, 원자료와 조회 결과를 대조하는 실습을 마쳤습니다.','그래프 설계와 조회, 절차와 조건표까지 살펴봤습니다.')
   if day==2 and n==68:b=b.replace('세 문제','네 문제')
   if day==2 and n==71:b=b.replace('마지막 문제입니다.','세 번째 문제입니다.')
   if day==2 and n==72:b=b[:b.index('이번 회차에서는 질문에 필요한 지식')].rstrip()
   if original!=b:edits.append({'source':f'{day:02}/{n}','destination':dest,'reason':'합친 회차의 연결·단원 번호·마무리 조정'})
   scripts[dest]=b
 else:
  title,screen,speech=new[n];g=f'## SLIDE {dest:02} — {title}\n### 화면 내용\n{screen}\n### 화면 구성\n기존 유형의 기본 배치를 따른다.\n### 제작 기준\n실전반 2회차 조립: 실라버스 24·25행의 적용과 회차 말미 정리.\n\n';scripts[dest]=f'## [SLIDE {dest}] {title}\n\n{speech}'
 decks.append(g)
# 표지·목표·목차는 합친 범위에 맞춘다. 본문 4~65, SOP/DMN 4~33은 그대로 유지.
decks[0]=decks[0].replace('지식 구조의 설계와 그래프 조회','지식 구조와 작업 판단의 설계').replace('설비와 데이터의 관계를 체계화해 필요한 정보 찾기','실전반 2회차 · 지식 구조와 절차·조건 연결').replace('현장 정보를 클래스와 관계로 나누어 스키마로 정의하고, 그래프에 저장해 관계를 따라 찾는다','현장 지식을 설계하고 그래프에서 찾으며, 작업 절차와 판단 조건으로 연결한다')
decks[1]=decks[1].replace('그래프 DB에 저장해 관계를 따라 조회한다.','그래프 DB에서 조회하고, 작업 절차와 판단 조건으로 연결한다.').replace('**설계와 구현의 검증** | 설비 자료에서 스키마와 예시 인스턴스를 설계한다 / 그래프 DB에 넣고 조회 결과를 설계와 대조한다 | 결과물 검증','**구현과 작업 판단** | 직접 설계한 그래프를 조회해 검증한다 / SOP의 순서와 DMN의 조건을 구별하고 조건표를 작성한다 | 결과물 검증')
decks[2]=re.sub(r'- 요소:.*?(?=### 화면 구성)', '- 요소:\n  1. 클래스 · 인스턴스와 관계 | 이론 01~03\n  2. 스키마 · 식별자 · 제약 | 이론 04~06\n  3. 그래프 DB와 Cypher 조회 · 생성 | 이론 07~08\n  4. 관계 조회 · 기준 지식 탐색 | 실습 1~2\n  5. 온톨로지 설계 · 그래프 구현 | 실습 3~4\n  6. 작업 절차와 수행 기준 | 이론 09~10\n  7. 결정표와 판단의 연결 | 이론 11~13\n  8. 조치 허용·제외 조건표 | 실습 5\n  9. 핵심 용어 · 복습 · 퀴즈 | 정리\n',decks[2],flags=re.S)
scripts[1]='## [SLIDE 1] 지식 구조와 작업 판단의 설계\n\n이번 회차에서는 설비 자료를 지식 구조로 만들고, 필요한 정보를 그래프에서 찾겠습니다. 이어서 작업 절차와 판단 조건을 구별하고, 어떤 조치를 할 수 있는지 근거를 담은 표로 정리하겠습니다. 먼저 대상을 어떻게 나누고 연결하는지부터 보겠습니다.'
scripts[2]='## [SLIDE 2] 학습목표\n\n현장의 대상과 값, 관계를 나누고 스키마로 정의하는 것이 출발점입니다. 식별자와 제약으로 일관성을 지키고, 그래프에 저장한 지식을 조회해 설계와 맞는지 확인하겠습니다. 그다음 작업 절차와 판단 조건을 구별합니다. 직접 만든 그래프와 조치 조건표를 원자료에 대어 확인하는 데까지 이어갑니다.'
scripts[3]='## [SLIDE 3] 목차\n\n앞부분은 클래스와 관계, 스키마, 그래프 저장과 조회 순서입니다. 관계를 조회하고 기준 지식을 탐색한 뒤, 설비 자료에서 지식 구조를 직접 만들어 검증하겠습니다. 이어 작업 절차를 읽고 판단 조건을 결정표로 옮기는 방법을 배웁니다. 마지막 실습에서는 허용과 제외의 근거를 표로 남기고, 회차 끝에서 핵심 용어와 퀴즈를 정리하겠습니다.'
scripts[66]=scripts[66].replace('이번 회차','이 부분')
# 실습 1~4는 65장 다음에 진행, SOP는 그 뒤에 재개.
scripts[64]=re.sub(r'^> \[제작 중단.*$', '> [제작 중단 — 낭독하지 않음] 65장 설명 뒤 05·06·07·08 실습 대본으로 실습 1~4를 진행한다. 실제 확인 결과에 맞게 발화하고, 끝나면 66장 SOP에서 재개한다.',scripts[64],flags=re.M)
units=[]
for name,a,b in [('01_이론_클래스와인스턴스.md',1,21),('02_이론_스키마설계.md',22,37),('03_이론_그래프저장과조회.md',38,65),('04_이론_작업절차와판단조건.md',66,107)]:
 (P/name).write_text('# 실전반 2회차 — '+name[6:-3]+'\n\n'+'\n\n---\n\n'.join(scripts[n] for n in sorted(scripts) if a<=n<=b)+'\n',encoding='utf8');units.append(dict(file=name,kind='pptx',slides=[a,b]))
for i,f in enumerate(sorted(I.glob('*_실습_*.md')),5):
 name=f'{i:02}'+f.name[2:];(P/name).write_text(f.read_text('utf8').replace('통합반 2회차','실전반 2회차'),encoding='utf8');units.append(dict(file=name,kind='practice',status='문서 작성·실행 및 캡처 미검증'))
name='09_실습_조치조건표.md';shutil.copy2(Path(__file__).parent/name,P/name);units.append(dict(file=name,kind='practice',status='문서 작성·실행 및 캡처 미검증'))
(P/'구성.json').write_text(json.dumps(dict(version=1,day=2,slide_count=107,units=units,playback='1~65장 → 실습 1~4 → 66~97장 → 실습 5 → 98~107장 복습·용어·퀴즈. 실습은 강사 단독 진행.'),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for day in [2,3]:shutil.copytree(C/f'만들기/decks/integrated/day{day:02}/figures',OUT/f'figures/day{day:02}',dirs_exist_ok=True)
# 덱 노트는 최종 분할대본에서만 파생.
notes={}
for n,b in scripts.items():
 m=re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]',b);end=int(m[2] or m[1]);s=' '.join(l.strip().replace('**','') for l in b.splitlines()[1:] if l.strip() and not l.startswith(('>','#','---')))
 for k in range(n,end+1):notes[k]=s if k==n else f'{n}~{end}장 통합 발화는 {n}장 발표자 노트를 따른다.'
for n,g in enumerate(decks,1):
 g=re.sub(r'^- 노트:.*\n?', '',g,flags=re.M);g=g.replace('### 화면 구성','- 노트: '+notes[n]+'\n### 화면 구성',1);decks[n-1]=g
(OUT/'실전반_02일차.md').write_text('# 지식 구조와 작업 판단의 설계\n\n통합반 2회차 전체와 3회차 SOP·DMN 본문 전체를 조립한다. 실습 실행·캡처 미수행.\n\n'+''.join(decks),encoding='utf8')
(P/'원본대응.json').write_text(json.dumps(dict(slides=[dict(destination=i,source_course='통합반' if d else '실전반 추가',source_day=d,source_slide=n) for i,(d,n) in enumerate(mapping,1)],speech_edits=edits,metadata_rewritten=[1,2,3],source_2_all_72=True,source_3_content_4_to_33_all=True),ensure_ascii=False,indent=2),encoding='utf8')
print('assembled',len(decks),'slides',len(scripts),'speech blocks')
