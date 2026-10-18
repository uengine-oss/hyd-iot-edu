"""4회차 원문 보존 조립. 실습·학생 코드 실행 없음."""
from helpers import *
B=EV/'before/산출물/교재/대본/통합반_온라인'
def blocks(folder):
 out={}
 for f in sorted(folder.glob('*_이론_*.md')):
  for b in re.split(r'(?=^## \[SLIDE )',f.read_text('utf8'),flags=re.M)[1:]:
   m=re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]',b);out[int(m[1])]=(int(m[2] or m[1]),b.rstrip().removesuffix('---').rstrip())
 return out
for f in sorted((B/'04회차').glob('*_이론_*.md')):
 t=f.read_text('utf8')
 for a,b in {'견주어 보세요':'견주어 보겠습니다','여러분이 직접 쓰는':'제가 직접 쓰는','꼭 넣으세요':'함께 넣겠습니다','다음 시간에는 첫 번째 활동':'이제 첫 번째 활동'}.items():t=t.replace(a,b)
 t=re.sub(r'^> \[제작:? 중단.*$', '> [제작 진행 — 낭독하지 않음] 44장 뒤 실습 03·04·05를 진행한다. 실제 확인 결과와 남은 미확인을 기록하고 45장부터 전체 흐름을 정리한다.',t,flags=re.M)
 write(I/f.name,t)
S={d:blocks(B/f'{d:02}회차') for d in [5,6]}
G={d:re.split(r'(?=^## SLIDE )',(C/f'만들기/decks/integrated/day{d:02}/통합반_{d:02}일차.md').read_text('utf8'),flags=re.M)[1:] for d in [5,6]}
mapping=[(5,n) for n in range(1,60)]+[(6,n) for n in range(4,24)]+[(6,62),(6,63)]+[(6,n) for n in range(24,62)]+[(5,64),(6,66),(5,65),(6,67),(5,66)]+[(5,n) for n in range(67,70)]+[(6,n) for n in range(69,72)]+[(5,70),(6,72)]
assert len(mapping)==132
out=D/'만들기/decks/practical/day04';out.mkdir(parents=True,exist_ok=True);P.mkdir(parents=True,exist_ok=True)
decks=[];scripts={};changes=[]
for dest,(day,n) in enumerate(mapping,1):
 g=G[day][n-1];g=re.sub(r'^## SLIDE \d+',f'## SLIDE {dest:02}',g).replace('figures/',f'figures/day{day:02}/')
 if day==6:g=re.sub(r'(?m)^- 번호: (\d+)',lambda m:f'- 번호: {int(m[1])+7:02}',g)
 if day==6 and n>=69:g=re.sub(r'Quiz ([123])',lambda m:'Quiz '+str(int(m[1])+3),g)
 # Only the portal lab's assignment changes: internal registered read tools.
 if day==6 and n==59:
  g=g.replace('기준 서버의 도구를 확인하고 등록한 서버를 연결 검사로 통과시켜, 읽기 도구의 호출 기록을 에이전트까지 잇는다.','등록된 업무 서버의 읽기 도구를 확인하고, 연결 검사와 호출 기록을 에이전트까지 잇는다.').replace('등록한 서버를 연결 검사하고','등록된 서버를 연결 검사하고')
  g=g.replace('기존 서버의 도구를 확인하고 등록할 새 서버를 연결 검사로 통과시켜, 읽기 도구의 호출 기록을 에이전트까지 잇는다.','등록된 업무 서버의 읽기 도구를 확인하고, 연결 검사와 호출 기록을 에이전트까지 잇는다.')
  g=g.replace('실습용으로 제공하는 읽기 전용 서버 하나','교육 환경의 서버 연결 상태').replace('등록할 서버를 연결 검사하고 읽기 도구를 호출한다','등록된 서버를 연결 검사하고 읽기 도구를 호출한다')
 if day==6 and n==61:g=g.replace('HYD 포털은 연결 검사를 통과한 서버만 에이전트에 붙인다 / 로컬 코딩 도구의 서버 설정과 실행 권한도 확인한다','HYD는 연결 검사 통과 후 에이전트에 붙인다 / 로컬은 서버 설정·실행 권한을 확인한다')
 if n in S[day]:
  end,b=S[day][n];original=b
  if day==5:
   b=b.replace('다음 시간에는','이어서')
   if n==29:b=b.replace('앞 시간에는','앞에서').replace('이번 시간에는','이어서').replace('네 실습','두 에이전트 실습')
   if n==48:b=b.replace('마지막 이론 단원','에이전트 원리를 마무리하는 단원')
   if n==56:
    b=b.replace('네 실습','두 에이전트 실습').replace('네 가지 실습','두 가지 에이전트 실습').replace('뒤의 세 활동','다음 원인 추론 활동').replace('뒤 세 활동','다음 원인 추론 활동')
   if n==58:b+='\n\n> [진행 — 낭독하지 않음] 59장 뒤 실습 1·2를 진행하고 60장 스킬부터 재개한다.'
   if n==64:b=b.replace('네 실습','에이전트 구성과 원인 추론 실습')
   if n==66:b=b.replace('세 문제','여섯 문제').replace('세 문항','여섯 문항')
   if n==69:b=b.replace('마지막 문제입니다','세 번째 문제입니다')
   if n==70:
    b=b.split('다음 회차에서는')[0].rstrip()+'\n\n이어서 스킬과 도구 연결에 관한 나머지 세 문제의 판단 기준을 확인하겠습니다.'
    b=b.replace('세 문제를 다 골랐으면','여섯 문제를 다 골랐으면')
  else:
   ren={'첫 번째 단원':'여덟 번째 단원','두 번째 단원':'아홉 번째 단원','세 번째 단원':'열 번째 단원','네 번째 단원':'열한 번째 단원','다섯 번째 단원':'열두 번째 단원','여섯 번째 단원':'열세 번째 단원','일곱 번째 단원':'열네 번째 단원'}
   b=re.sub('|'.join(ren),lambda m:ren[m[0]],b)
   b=b.replace('앞 회차','앞부분').replace('지난 회차','앞부분').replace('앞 시간에는','앞에서').replace('다음 시간에는','이어서')
   if n==23:b+='\n\n이제 회의록을 작업 목록으로 바꾸는 스킬을 직접 작성하겠습니다. 그 뒤에는 이 지침이 부르는 도구의 연결을 살펴보겠습니다.'
   if n==44:b=b.replace('네 실습','마지막 도구 연결 실습').replace('네 가지 실습','마지막 도구 연결 실습')
   if n==58:
    b=b.replace('첫 번째 실습','마지막 실습의 포털 단계').replace('첫 실습','마지막 실습의 포털 단계')
    b=b.replace('등록할 새 서버','등록된 업무 서버').replace('새 서버를 등록','등록 상태를 확인')
   if n==60:
    b=b.replace('두 번째 실습','같은 실습의 로컬 단계').replace('둘째 실습','같은 실습의 로컬 단계')
    b+='\n\n> [진행 — 낭독하지 않음] 119장 뒤 실습 4의 포털·로컬 두 단계를 진행하고 120장부터 복습한다.'
   if n==62:
    b=b.replace('앞의 두 활동','앞에서 배운 원리').replace('앞 두 활동','앞에서 배운 원리')
    b+='\n\n> [진행 — 낭독하지 않음] 81장 뒤 실습 3을 진행하고 82장 MCP부터 재개한다.'
   if n>=69:
    b=re.sub(r'Quiz ([123])',lambda m:'Quiz '+str(int(m[1])+3),b)
    for a,c in {'첫 번째 문제':'네 번째 문제','두 번째 문제':'다섯 번째 문제','세 번째 문제':'여섯 번째 문제','첫 문항':'네 번째 문항','둘째 문항':'다섯 번째 문항','셋째 문항':'여섯 번째 문항','첫 번째 문항':'네 번째 문항','두 번째 문항':'다섯 번째 문항','세 번째 문항':'여섯 번째 문항'}.items():b=b.replace(a,c)
  if day==6 and n==4:b=b.replace('이번 시간에는 그 가운데 위의 두 줄, 에이전트 스킬을 다룹니다.','앞에서 구성한 에이전트가 반복해서 따를 수행 방법을 에이전트 스킬로 정리하겠습니다.')
  if day==6 and n==23:b=b.replace('이어서 스킬이 부르는 도구 쪽으로 넘어갑니다. 절차에 이름만 적힌 그 도구가 실제로 어디에 있고, 에이전트가 어떤 표준으로 그 도구를 부르는지 보겠습니다.','')
  if day==6 and n==62:b=b.replace('앞에서 배운 원리이 도구 연결을 확인하는 실습이라면, 세 번째 실습에서는 이번 회차의 다른 한 축인 스킬로 돌아가서,','앞에서 배운 스킬의 작성 기준을 적용해,')
  if day==6 and n==58:
   b=b.replace('그다음 실습용으로 제공하는 읽기 전용 서버를 등록하고, 연결 검사를 거쳐서 읽기 도구 하나를 호출합니다.','그다음 등록된 업무 서버의 연결 검사를 확인하고, 허용된 읽기 도구 하나를 호출합니다.')
   b=b.replace('이어서 나머지 실습도 살펴본 뒤','이어서 같은 실습의 로컬 단계도 살펴본 뒤')
  if day==6 and n==60:b=b.replace('단계은','단계는').replace('첫 실습에서 확인할','앞 단계에서 확인할').replace('견줘 보세요','견줘 보겠습니다').replace('남겨 주세요','남기겠습니다')
  if day==6 and n==66:b=b.replace('실습에서 남긴 결과를 바탕으로 이번 회차를 마무리하겠습니다. 복습, 용어 정리, 퀴즈 순서로 갈게요. 네 실습에서 도구를 직접 연결해 불러 보고, 스킬도 직접 써 봤죠. 먼저 복습으로,','에이전트의 실행 흐름에 이어, 스킬과 도구 연결을 돌아보겠습니다. 실습에서 실제로 확인한 기록과 남은 미확인을 바탕으로,')
  if day==6 and n==67:b=b.replace('상황에 적용해 봤으니, 이번에는 이번 회차에 나온 용어의 뜻을 정리하겠습니다.','에이전트 용어에 이어, 스킬과 도구 연결의 용어를 정리하겠습니다.')
  b=b.replace('이어질 실습 네 개에서','이어질 두 에이전트 실습에서').replace('여러분이 직접','제가 직접').replace('직접 만들어 보세요','제가 직접 만들어 보겠습니다').replace('앞 시간에','앞에서')
  b=re.sub(r'^> \[제작:? (?:중단|재개).*$', '> [제작 진행 — 낭독하지 않음] 구성.json의 회차 진행 순서를 따른다. 실습 결과를 미리 단정하지 않는다.',b,flags=re.M)
  if b!=original:changes.append(dict(source_day=day,source_slide=n,destination=dest))
  b=re.sub(r'^## \[SLIDE \d+(?:~\d+)?\]',f'## [SLIDE {dest}'+(f'~{dest+end-n}' if end>n else '')+']',b);scripts[dest]=b
 decks.append(g)
title='일하는 AI와 업무 지침·도구의 연결'
def screen(n,title,body):return f'## SLIDE {n:02} — {title}\n### 화면 내용\n{body}\n### 화면 구성\n기존 교재 유형과 배치를 따른다.\n### 제작 기준\n실전반 4회차 실라버스와 원본 대응표.\n\n'
decks[0]=screen(1,title.replace('AI와 업무','AI와 / 업무'),'- 유형: 표지\n- 기관: 경남대학교 피지컬AI 사관학교\n- 과정: 실전반 4회차 · 에이전트 · 스킬 · MCP\n- 부제: 도구의 근거로 판단하고, 수행 지침을 재사용하며 외부 시스템을 연결한다\n- 아이콘: robot, file-check, network')
decks[1]=screen(2,'학습목표','- 유형: 카드\n- 메시지: 판단의 근거·수행 방법·도구 연결을 구별하고 실행 기록으로 확인한다.\n- 요소:\n  1. 에이전트 | LLM · RAG · 도구의 역할을 구별한다 / 호출 결과로 다음 행동을 정한다 | 실행 고리\n  2. 원인과 근거 | 가설과 확인한 사실을 나눈다 / 누락과 실패를 기록한다 | 판단 보류\n  3. 재사용 지침 | SKILL.md에 절차와 예외를 적는다 / 결과를 원문과 대조한다 | 에이전트 스킬\n  4. 도구 연결 | 호스트 · 서버 · 도구를 구별한다 / 권한과 호출 기록을 확인한다 | MCP')
decks[2]=screen(3,'목차','- 유형: 목차\n- 요소:\n  1. LLM · RAG · 에이전트 | 이론\n  2. 실행 고리 · 근거 · 기록 | 이론\n  3. 업무 에이전트 · 원인 추론 | 실습 1~2\n  4. SKILL.md · SOP · 재사용 | 이론\n  5. 회의록 스킬 작성과 검토 | 실습 3\n  6. MCP · 권한 · 연결과 실패 | 이론\n  7. 포털 조회 · 로컬 서버 조합 | 실습 4\n  8. 복습 · 용어 · 퀴즈 | 마무리')
scripts[1]='## [SLIDE 1] '+title+'\n\n지난 회차까지 판단에 쓸 구조와 지식을 정리했습니다. 이번에는 에이전트가 그 지식과 도구를 어떻게 사용하는지 보겠습니다. 목표에 따라 조회하고 결과를 읽어 다음 행동을 정하는 흐름부터, 그 수행 방법을 스킬로 남기고 도구를 MCP로 연결하는 과정까지 이어갑니다.'
scripts[2]='## [SLIDE 2] 학습목표\n\nLLM과 RAG, 에이전트가 맡는 역할을 구별하겠습니다. 원인을 추론할 때는 가설과 확인된 사실을 나누고, 근거가 없으면 어떤 판단을 보류할지 정합니다. 수행 방법은 SKILL.md에 절차와 예외로 남기겠습니다. 마지막에는 MCP의 구성과 권한을 이해하고, 연결됐다는 사실뿐 아니라 실제 호출의 입력과 결과를 확인하겠습니다.'
scripts[3]='## [SLIDE 3] 목차\n\n에이전트의 원리와 실행 기록을 먼저 배우고, 포털에서 업무 에이전트를 구성한 뒤 원인 추론 기능을 직접 만들겠습니다. 이어서 스킬을 배우고 회의록을 작업 목록으로 바꾸는 지침을 작성합니다. MCP와 연결의 안전 기준을 배운 뒤에는 포털의 업무 도구와 로컬의 파일·Git·시간 서버를 확인하겠습니다. 마지막에 두 묶음의 복습과 용어, 여섯 퀴즈를 함께 정리합니다.'
units=[]
for name,a,b in [('01_이론_에이전트와근거.md',1,59),('02_이론_재사용가능한업무지침.md',60,81),('03_이론_도구연결과전체정리.md',82,132)]:
 write(P/name,'# 실전반 4회차\n\n'+'\n\n---\n\n'.join(scripts[n] for n in sorted(scripts) if a<=n<=b)+'\n');units.append(dict(file=name,kind='pptx',slides=[a,b]))
for idx,name in enumerate(['업무에이전트구성','원인추론과점검계획','회의록스킬작성','MCP도구연결'],4):units.append(dict(file=f'{idx:02}_실습_{name}.md',kind='practice',status='문서 작성·실행 및 캡처 미검증'))
write(P/'구성.json',json.dumps(dict(version=1,day=4,slide_count=132,units=units,playback='1~59장 → 실습 1·2 → 60~81장 → 실습 3 → 82~119장 → 실습 4 → 120~132장 복습·용어·퀴즈.'),ensure_ascii=False,indent=2)+'\n')
notes=theory_notes(P)
for n,g in enumerate(decks,1):decks[n-1]=re.sub(r'^- 노트:.*\n?','',g,flags=re.M).replace('### 화면 구성','- 노트: '+notes[n]+'\n### 화면 구성',1)
write(out/'실전반_04일차.md','# '+title+'\n\n'+''.join(decks))
for day in [5,6]:shutil.copytree(C/f'만들기/decks/integrated/day{day:02}/figures',out/f'figures/day{day:02}',dirs_exist_ok=True)
write(P/'원본대응.json',json.dumps(dict(slides=[dict(destination=i,source_day=d,source_slide=n) for i,(d,n) in enumerate(mapping,1)],speech_edits=changes,metadata_rewritten=[1,2,3],lab_screen_adapted=[117],layout_reworded=[119],omissions='통합반5 품질대응·센서시각화 실습 소개60~63, 통합반6 학습코치 소개64~65는 이번 실전반4 미배정 활동. 통합반6 메타정보1~3과 퀴즈간지68은 공통 안내로 통합. 핵심 이론5:4~55 및6:4~57 전체 보존. 복습·용어·퀴즈6문제 전체 보존.'),ensure_ascii=False,indent=2)+'\n')
print('assembled',len(decks),'slides',len(scripts),'blocks')
