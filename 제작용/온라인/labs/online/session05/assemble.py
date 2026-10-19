"""5회차 원본 보존 조립. 문서만 생성한다."""
from helpers import *
B=EV/'before/산출물/교재/대본/통합반_온라인'
def blocks(folder):
 out={}
 for f in sorted(folder.glob('*_이론_*.md')):
  for b in re.split(r'(?=^## \[SLIDE )',f.read_text('utf8'),flags=re.M)[1:]:
   m=re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]',b);out[int(m[1])]=(int(m[2] or m[1]),b.rstrip().removesuffix('---').rstrip())
 return out
for f in (B/'05회차').glob('*_이론_*.md'):
 t=f.read_text('utf8').replace('견줘 보세요','견줘 보겠습니다').replace('출력 점검을 꼭 하세요','출력도 점검하겠습니다').replace('다음 시간에는 첫 활동','이제 첫 활동')
 t=re.sub(r'^> \[제작:? (?:중단|재개).*$', '> [제작 진행 — 낭독하지 않음] 63장 뒤 실습 03~06을 진행하고, 실제 확인 기록과 남은 미확인을 바탕으로 64장부터 정리한다.',t,flags=re.M)
 write(I/f.name,t)
S={d:blocks(B/f'{d:02}회차') for d in [7,8]}
G={d:re.split(r'(?=^## SLIDE )',(C/f'만들기/decks/integrated/day{d:02}/통합반_{d:02}일차.md').read_text('utf8'),flags=re.M)[1:] for d in [7,8]}
mapping=[(7,n) for n in range(1,24)]+[(7,n) for n in range(26,50)]+[(7,52),(7,53)]+[(8,n) for n in range(4,31)]+[(8,35),(8,36)]+[(8,n) for n in range(39,56)]+[(7,54),(7,55),(8,56),(7,56)]+[(7,n) for n in range(57,60)]+[(8,n) for n in range(58,61)]+[(7,60),(8,61)]
assert len(mapping)==107
out=D/'만들기/decks/practical/day05';out.mkdir(parents=True,exist_ok=True);P.mkdir(parents=True,exist_ok=True)
scripts={};decks=[];changes=[]
for dest,(day,n) in enumerate(mapping,1):
 g=re.sub(r'^## SLIDE \d+',f'## SLIDE {dest:02}',G[day][n-1]).replace('figures/',f'figures/day{day:02}/')
 if day==7 and n in [22,23]:g=g.replace('부품 수량 · 긴급 사유 · 승인권자','설비 · 경보 패턴 · 사례 정보').replace('부품 수량이나 긴급 사유, 승인권자','설비나 경보 패턴, 사례 정보')
 if day==8:g=re.sub(r'(?m)^- 번호: (\d+)',lambda m:f'- 번호: {int(m[1])+6 if int(m[1])<4 else 10:02}',g)
 if day==8 and n>=58:g=re.sub(r'Quiz ([123])',lambda m:'Quiz '+str(int(m[1])+3),g)
 if n in S[day]:
  end,b=S[day][n];original=b
  b=b.replace('5회차','지난 회차').replace('6회차','지난 회차').replace('여러분이 고칠','직접 고칠').replace('견줘 보세요','견줘 보겠습니다').replace('다시 실행하세요','다시 실행하겠습니다')
  if day==7:
   if n==20:b=b.replace('다음 실습은 정보를 묻는 일과 AI끼리 검토하는 일을 나누어 확인합니다.','다음 실습에서는 정보가 빠졌을 때 질문하고 다시 처리하는 흐름을 만들겠습니다.').replace('이어지는 두 실습','다음 실습').replace('정보를 채우는 질문과 AI끼리의 검토','정보를 채우는 질문')
   if n==22:b=b.replace('이 활동에 사용할 기존 업무 요청 에이전트를 재사용해','지난 회차에 만든 에이전트에 요청 확인 단계를 더해').replace('부품 수량이나 긴급 사유, 승인권자','설비나 경보 패턴, 사례 정보').replace('줘 보세요','넣겠습니다').replace('남기세요','남기겠습니다');b+='\n\n> [진행 — 낭독하지 않음] 23장 뒤 승인·거절과 확인 질문 실습을 진행하고 24장부터 재개한다.'
   if n==26:b=b.replace('목차의 아래 네 단원','변경 요청·명세·계약·검증의 네 단원').replace('이번 회차 처음의 두 번째 물음','변경할 때 확인할 물음').replace('앞의 세 실습','앞의 두 실습').replace('승인 기록과 질문 전후 상태, 검토 의견','승인 기록과 질문 전후 상태')
   if n==33:b=b.replace('이번 회차 마지막 실습','이어질 명세 실습')
   if n==45:b=b.replace('마지막 이론 단원','명세 부분의 마지막 단원')
   if n==49:b=b.replace('다음 회차에는','이어서')
   if n==52:b='''## [SLIDE 52~53] 실습: 명세에 따라 기존 기능을 유지하며 요구사항 추가

앞에서 만든 에이전트에 긴급 조건을 추가하겠습니다. 먼저 제공된 모호한 변경 요청의 기존 비교 기록을 읽고, 출력 항목과 승인 조건 중 무엇이 달라졌는지 확인합니다. 이 기록은 이번 실행의 결과가 아닙니다. 모호한 요청이 반드시 실패한다는 뜻도 아니며, 차이가 없으면 없는 그대로 기록합니다.

같은 프로젝트의 변경 전 판본과 입력을 보존한 뒤 spec.md를 먼저 작성하겠습니다. 기존 일반 요청의 처리, 긴급 기준, 필수 값이 없을 때의 보류, 승인 없이 확정하지 않는 조건, 결과 형식과 수용 기준을 적습니다. 그 명세에 맞춰 필요한 기능만 더하고 일반 요청과 긴급 요청을 같은 조건으로 비교합니다.

수용 기준마다 기대와 실제를 나누어 확인하고 입력과 기대 결과, 조회 자료와 판본을 함께 저장하겠습니다. 실행마다 달라지는 번호와 시각은 별도 규칙으로 비교합니다. 이어질 검증 실습에서는 이 자료를 그대로 시나리오와 회귀 확인에 사용합니다.

> [진행 — 낭독하지 않음] 49장 뒤 실습 3을 진행하고 50장부터 BDD를 설명한다.'''
   if n==54:b=b.replace('실습에서 남긴 변경 전후 기록과 명세를 바탕으로 이번 회차를 마무리하겠습니다. 복습과 용어 정리, 퀴즈로 배운 것을 되짚어 볼게요. 먼저 복습입니다.','전체 흐름에 이어, 변경 전후 기록과 명세를 바탕으로 사람의 결정과 변경 조건을 돌아보겠습니다.')
   if n==56:b=b.replace('세 문제','여섯 문제').replace('세 문항','여섯 문항')
   if n==59:b=b.replace('마지막 문제예요','세 번째 문제예요')
   if n==60:b=b.split('여기까지가 이번 회차입니다.')[0].rstrip()+'\n\n이어서 검증에 관한 나머지 세 문제의 판단 기준을 확인하겠습니다.'
  else:
   ren={'첫 번째 단원':'일곱 번째 단원','두 번째 단원':'여덟 번째 단원','세 번째 단원':'아홉 번째 단원','다섯 번째 단원':'열 번째 단원'}
   b=re.sub('|'.join(ren),lambda m:ren[m[0]],b).replace('앞 회차','앞부분').replace('지난 회차에서 정한 명세','앞에서 정한 명세')
   if n==35:b='''## [SLIDE 35~36] 실습: 기존 기능과 추가 기능을 함께 검증하기

앞 실습의 프로젝트와 spec.md, 저장한 입력과 기대 결과를 그대로 열겠습니다. 일반 요청, 긴급 요청, 필수 값 누락, 승인 거절을 Given·When·Then으로 적고, 긴급 기준 바로 아래와 정확히 경계인 값도 확인합니다. 기대값은 실행 전에 명세에서 정합니다.

각 시나리오를 실행 가능한 검사로 연결하고 같은 입력과 조건으로 반복해 결과를 비교하겠습니다. 설명의 표현 차이와 출력 계약 위반을 나눠 보고, 실패가 있으면 입력·조회·판단·출력 중 어느 단계에서 달라졌는지 기록으로 좁힙니다. 발견한 원인을 수정한 뒤에는 추가 기능뿐 아니라 기존 시나리오도 모두 다시 확인합니다.

통과 여부, 실제 결과, 수정 사항과 남은 미확인을 저장하겠습니다. 실패가 없으면 일부러 만들지 않습니다. 이 검증이 확인한 조건의 범위도 함께 남기고 전체 제작 흐름을 정리하겠습니다.

> [진행 — 낭독하지 않음] 78장 뒤 실습 4를 진행하고 79장부터 전체 과정을 정리한다.'''
   if n==39:b=b.replace('네 실습에서 남긴 시나리오와 실행 기록, 수정 내역과 인수인계서','승인·질문 기록과 명세, 시나리오와 실행 기록, 수정 내역')
   if n==45:b=b.replace('앞 실습','앞 이론')
   if n==50:
    b=b.replace('에이전트를 만들어 본 실습들에서 나온 산출물 다섯','여러 업무에 에이전트를 적용할 때의 산출물 예 다섯').replace('표시했습니다','표시합니다').replace('냈고요','냅니다').replace('단정하지 않았어요','단정하지 않습니다').replace('미정으로 적었고','미정으로 적고').replace('되짚어 줬죠','되짚어 줍니다').replace('실습에서 만든 인수인계서도 같은 방식이었죠','인수인계서에도 같은 방식을 적용합니다').replace('읽지 못했다고 적었습니다','읽지 못했다고 적습니다')
   if n==52:b=b.replace('연습이었어요','예입니다').replace('구별한 겁니다','구별합니다').replace('가운데 아래 인수인계서는','별도 응용 예인 가운데 아래 인수인계서는')
   if n==56:b=b.replace('이번 실습은 그중','앞에서 살펴본 인수인계 예는 그중')
   if n>=58:
    b=re.sub(r'Quiz ([123])',lambda m:'Quiz '+str(int(m[1])+3),b)
    for a,c in {'첫 번째 문제':'네 번째 문제','두 번째 문제':'다섯 번째 문제','세 번째 문제':'여섯 번째 문제','세 문제 모두':'여섯 문제 모두'}.items():b=b.replace(a,c)
  b=re.sub(r'^> \[제작:? (?:중단|재개).*$', '> [제작 진행 — 낭독하지 않음] 구성.json의 진행 순서를 따른다. 실제 결과를 미리 단정하지 않는다.',b,flags=re.M)
  if b!=original:changes.append(dict(source_day=day,source_slide=n,destination=dest))
  b=re.sub(r'^## \[SLIDE \d+(?:~\d+)?\]',f'## [SLIDE {dest}'+(f'~{dest+end-n}' if end>n else '')+']',b);scripts[dest]=b
 decks.append(g)
def screen(n,title,body):return f'## SLIDE {n:02} — {title}\n### 화면 내용\n{body}\n### 화면 구성\n기존 교재 유형과 배치를 따른다.\n### 제작 기준\n실전반 5회차 실라버스와 원본 대응표.\n\n'
title='사람과 협업하고 변경된 기능까지 검증하기'
decks[0]=screen(1,'사람과 협업하고 / 변경된 기능까지 검증하기','- 유형: 표지\n- 기관: 경남대학교 피지컬AI 사관학교\n- 과정: 실전반 5회차 · HITL · SDD · BDD\n- 부제: 사람의 결정과 명세를 기준으로 기존 기능과 새 기능을 함께 확인한다\n- 아이콘: user-check, file-check, shield')
decks[1]=screen(2,'학습목표','- 유형: 카드\n- 메시지: 사람의 결정·변경 기준·행동 검증을 하나의 흐름으로 연결한다.\n- 요소:\n  1. 사람의 개입 | 승인과 정보 확인을 구별한다 / 결정과 권한의 기록을 읽는다 | HITL\n  2. 변경의 기준 | 계약·금지 조건을 지킨다 / 수용 기준을 적는다 | SDD\n  3. 행동 검증 | 전제 · 행동 · 기대 결과를 정한다 / 새 기능과 기존 기능을 확인한다 | BDD\n  4. 전체 흐름 | 제작과 검증의 산출물을 연결한다 / 확인한 범위와 미확인을 남긴다 | 정리')
decks[2]=screen(3,'목차','- 유형: 목차\n- 요소:\n  1. 사람의 결정 · 질문 · 역할 | 이론\n  2. 승인·거절 · 확인 질문 | 실습 1~2\n  3. 변경 요청 · 명세 · 계약 | 이론\n  4. 기존 기능을 유지하며 확장 | 실습 3\n  5. 시나리오 · 반복 · 회귀 | 이론\n  6. 기존·추가 기능 함께 검증 | 실습 4\n  7. 제작부터 검증까지 연결 | 전체 정리\n  8. 복습 · 용어 · 퀴즈 | 마무리')
scripts[1]='## [SLIDE 1] '+title+'\n\n앞 회차에서 만든 에이전트가 사람과 협업하고, 요구가 바뀐 뒤에도 지켜야 할 기준을 유지하도록 만들겠습니다. 사람의 승인과 확인 질문부터 명세에 따른 기능 추가, 시나리오와 회귀 검증까지 연결합니다.'
scripts[2]='## [SLIDE 2] 학습목표\n\n사람의 결정과 정보 확인, AI의 검토 의견을 구별하겠습니다. 변경할 때는 기존 입출력 계약과 금지 조건을 보존하고 수용 기준을 먼저 적습니다. 그 기준을 시나리오로 옮겨 새 기능과 기존 기능을 함께 확인하겠습니다. 마지막에는 제작과 검증의 산출물이 다음 작업에 어떻게 이어지는지 정리합니다.'
scripts[3]='## [SLIDE 3] 목차\n\n사람이 결정하는 자리와 질문으로 정보를 채우는 방법을 배우고 두 실습으로 확인합니다. 이어서 명세와 계약을 배우고 기존 에이전트에 요구사항을 더합니다. 다음은 행동 시나리오와 반복·회귀 검증입니다. 같은 프로젝트를 검증한 뒤 전체 과정을 연결하고 복습과 용어, 여섯 퀴즈를 정리하겠습니다.'
for n,title_,lines in [(48,'실습: 명세에 따라 요구사항 추가','기존 비교 기록에서 출력·승인 조건의 차이를 읽는다 / spec.md에 지킬 것과 바꿀 것을 적는다 / 같은 입력으로 일반·긴급 요청을 확인한다'),(49,'실습: 입력과 수용 기준','일반 · 긴급 · 누락 입력과 기대값을 남긴다 / 기존 결과 항목과 승인 조건을 보존한다 / 판본·조회 자료·미확인을 함께 저장한다'),(77,'실습: 기존·추가 기능 함께 검증','일반 · 긴급 · 누락 · 거절을 시나리오로 적는다 / 같은 조건으로 반복하고 계약 위반을 구별한다 / 실제 실패를 고친 뒤 기존 검사도 다시 실행한다'),(78,'실습: 검증 결과와 남은 범위','명세에서 Given · When · Then을 정한다 / 경계값과 승인 조건도 함께 확인한다 / 실제 결과 · 수정 · 재확인 · 미확인을 저장한다')]:
 decks[n-1]=screen(n,title_,'- 유형: 카드\n- 메시지: 앞 단계의 프로젝트와 근거를 이어 사용한다.\n- 요소:\n'+''.join(f'  {j}. {s} | 작업과 근거를 기록한다 | 직접 확인\n' for j,s in enumerate(lines.split(' / '),1)))
units=[]
for name,a,b in [('01_이론_사람의판단과승인.md',1,23),('04_이론_명세와요구사항확장.md',24,49),('06_이론_행동시나리오와검증.md',50,78),('08_이론_제작과검증전체정리.md',79,107)]:
 write(P/name,'# 실전반 5회차\n\n'+'\n\n---\n\n'.join(scripts[n] for n in sorted(scripts) if a<=n<=b)+'\n');units.append(dict(file=name,kind='pptx',slides=[a,b]))
for idx,name in [(2,'승인과거절'),(3,'확인질문과재처리'),(5,'명세에따른요구사항추가'),(7,'기존기능과추가기능검증')]:units.append(dict(file=f'{idx:02}_실습_{name}.md',kind='practice',status='문서 작성·실행 및 캡처 미검증'))
units.sort(key=lambda u:u['file'])
write(P/'구성.json',json.dumps(dict(version=1,day=5,slide_count=107,units=units,playback='1~23장 → 실습1·2 → 24~49장 → 실습3 → 50~78장 → 실습4 → 79~107장 전체 정리·복습·용어·퀴즈.'),ensure_ascii=False,indent=2)+'\n')
notes=theory_notes(P)
for n,g in enumerate(decks,1):decks[n-1]=re.sub(r'^- 노트:.*\n?','',g,flags=re.M).replace('### 화면 구성','- 노트: '+notes[n]+'\n### 화면 구성',1)
write(out/'실전반_05일차.md','# '+title+'\n\n'+''.join(decks))
for d in [7,8]:shutil.copytree(C/f'만들기/decks/integrated/day{d:02}/figures',out/f'figures/day{d:02}',dirs_exist_ok=True)
write(P/'원본대응.json',json.dumps(dict(slides=[dict(destination=i,source_day=d,source_slide=n) for i,(d,n) in enumerate(mapping,1)],speech_edits=changes,metadata_rewritten=[1,2,3],lab_screen_adapted=[22,23,48,49,77,78],omissions='원본121장→107장. 통합반7의24~25 다른AI 검토 실습과 통합반8의37~38 인수인계 실습은 미배정. 7의50~53 변경 비교·명세 실습은48~49로 통합, 8의31~36 시나리오·반복·회귀 실습은77~78로 통합. 8의1~3 메타정보와57 퀴즈 안내는 공통 안내로 통합. 핵심 이론7:4~19,26~49 및8:4~30,39~55와 복습·용어·퀴즈6문제 전부 보존.'),ensure_ascii=False,indent=2)+'\n')
print('assembled',len(decks),'slides',len(scripts),'blocks')
