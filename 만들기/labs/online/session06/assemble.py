"""6회차 원본 대응 조립. 실습 실행 없음."""
from helpers import *
B=EV/'before/산출물/교재/대본/통합반_온라인'
def blocks(folder):
 out={}
 for f in sorted(folder.glob('*_이론_*.md')):
  for b in re.split(r'(?=^## \[SLIDE )',f.read_text('utf8'),flags=re.M)[1:]:
   m=re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]',b);out[int(m[1])]=(int(m[2] or m[1]),b.rstrip().removesuffix('---').rstrip())
 return out
for f in (B/'06회차').glob('*_이론_*.md'):
 t=f.read_text('utf8').replace('실제 실습은 빈 파일로 별도 관리한다.','실습 진행 대본은 별도 파일로 관리한다.')
 for a,b in [('견줘 보세요. 그리고 파일을','견줘 보겠습니다. 그리고 파일을'),('호출 기록으로 남겨 주세요.','호출 기록으로 남기겠습니다.'),('절차와 결과 항목의 이름을 정하세요.','절차와 결과 항목의 이름을 정하겠습니다.'),('작업 목록을 만드는 것과 실제 담당자에게 업무를 발송하는 것도 구분하세요.','작업 목록을 만드는 것과 실제 담당자에게 업무를 발송하는 것도 구분하겠습니다.'),('다음 시간에는 안내한 순서대로','이제 안내한 순서대로')]:t=t.replace(a,b)
 t=t.replace('현재 실제 실습 파일은 비어 있다.','실습 대본에 따라 실제 확인한 결과와 미확인을 기록한다.')
 write(I/f.name,t)
S=blocks(B/'09회차');G=re.split(r'(?=^## SLIDE )',(EV/'before/만들기/decks/integrated/day09/통합반_09일차.md').read_text('utf8'),flags=re.M)[1:]
out=D/'만들기/decks/practical/day06';out.mkdir(parents=True,exist_ok=True);P.mkdir(parents=True,exist_ok=True)
decks=[];scripts={};mapping=[];changes=[]
def screen(n,title,body):return f'## SLIDE {n:02} — {title}\n### 화면 내용\n{body}\n### 화면 구성\n기존 교재 유형과 배치를 따른다.\n### 제작 기준\n실전반 6회차 실라버스와 통합반9 원본 대응표.\n\n'
for n in list(range(1,60))+list(range(68,75)):
 dest=n if n<60 else n+6
 g=re.sub(r'^## SLIDE \d+',f'## SLIDE {dest:02}',G[n-1]).replace('figures/','figures/day09/')
 end,b=S[n];original=b
 if n==1:b=b.replace('그런데 추천안이 나왔다고 설비가 바로 좋아질까요? 아니죠.','추천안이 나와도 승인과 실행은 아직 남아 있습니다.').replace('그럼 이 일들은 누가, 어떤 순서로 이어 가야 할까요?','각 일을 맡는 주체와 진행 순서가 필요합니다.')
 if n==3:b=b.replace('네 가지가 이어집니다. 작은 승인 절차를 그리는 데서 시작해서, 긴급 대응 프로세스를 그리고, 그걸 실제 시스템에 연결한 다음, 쿨러 경보로 실행까지 해 보겠습니다.','일곱 활동이 이어집니다. 편집기 기본 조작과 작은 승인 절차부터 긴급 대응 작도, 승인·예외 설계, 시스템 연결, 사전 검사와 배포, 쿨러 경보의 처리 결과 확인까지 진행하겠습니다.')
 if n==18:b=b.replace('셋째 실습','사전 검사 실습')
 if n==32:b=b.replace('셋째 실습','다섯째 실습')
 if n==33:b=b.replace('표준에는 조건부 시퀀스 흐름도 있으므로 모든 갈림에 마름모가 필수인 것은 아닙니다. 승인과 거절이 동시에 일어나는 그림이 되어 버리는 거죠.','그러면 승인과 거절이 동시에 일어나는 그림이 되어 버리는 거죠. 표준에는 조건부 시퀀스 흐름도 있으므로 모든 갈림에 마름모가 필수인 것은 아닙니다.')
 if n==40:b=b.replace('셋째 실습','네 번째 실습')
 if n==45:b=b.replace('경보로 열린 처리 건을 이 엔진이 정의의 조건에 따라 진행을 관리합니다.','이 엔진이 정의의 조건에 따라 경보로 열린 처리 건의 진행을 관리합니다.')
 if n==58:b=b.replace('셋째 실습','여섯째 실습')
 if n==68:b=b.replace('실제 실습04~07','실제 실습04~10')
 b=re.sub(r'^## \[SLIDE \d+(?:~\d+)?\]',f'## [SLIDE {dest}]',b)
 if b.replace(f'[SLIDE {dest}]',f'[SLIDE {n:02}]')!=original.replace(f'[SLIDE {n}]',f'[SLIDE {n:02}]'):changes.append({'source_day':9,'source_slide':n,'destination':dest})
 scripts[dest]=b;decks.append((dest,g));mapping.append(dict(destination=dest,source_day=9,source_slide=n))
title='설비 이상 대응을 안전하게 실행하는 프로세스'
decks[0]=(1,screen(1,'설비 이상 대응의 / 프로세스 설계와 실행','- 유형: 표지\n- 기관: 경남대학교 피지컬AI 사관학교\n- 과정: 실전반 6회차 · BPM · BPMN · 오케스트레이션\n- 부제: 에이전트의 제안을 사람의 승인과 시스템 실행으로 연결한다\n- 아이콘: git-fork, user-check, shield'))
# 원본 목차의 실습 묶음 수를 실제 배정에 맞춘다.
decks[2]=(3,re.sub(r'9\. .*', '9. 작도 · 승인과 예외 · 연결 · 배포 · 실행 | 실습 1~7',decks[2][1],count=1))
labs=[
('업무설계도구기본','BPMN 편집기의 기본 조작','새 다이어그램 | 시작·작업·끝을 배치한다 | 입력','배치와 연결 | 요소 이름과 종류를 고친다 | 범위','저장 파일 | basics.bpmn | 산출물','다시 열기 | 요소·선·이름이 유지된다 | 판정','첫 실습에서는 BPMN 편집기에서 시작과 작업, 끝을 배치하고 연결하겠습니다. 이름과 종류, 연결된 선을 확인하고 파일로 저장한 뒤 다시 엽니다. 저장 전후 그림이 같은지 확인한 다음 승인 업무로 확장하겠습니다.'),
('승인업무작도','간단한 승인 업무 작도','정비 요청 | 요청 확인과 승인 판단 | 입력','두 경로 | 승인 종료 · 반려 종료 | 범위','승인 흐름 | approval.bpmn | 산출물','경로 확인 | 각 갈래가 끝에 닿는다 | 판정','작은 정비 요청을 받아 확인하고 승인 여부에 따라 승인 종료와 반려 종료로 나누겠습니다. 사람이 결정하는 작업과 결과를 읽는 게이트웨이를 구별합니다. 두 갈래를 각각 따라가며 끊긴 선이 없는지 확인하고 저장하겠습니다.'),
('설비이상대응작도','설비 이상 대응 프로세스 작도','쿨러 경보 | 앞 회차의 진단·제안 에이전트 | 입력','역할과 순서 | 에이전트 · 담당자 · 시스템 | 범위','기본 흐름 | cooling-draft.bpmn | 산출물','책임 확인 | 제안 · 승인 · 명령 · 재관측 · 보고 | 판정','풀 하나를 에이전트, 담당자, 시스템의 세 레인으로 나누겠습니다. 쿨러 경보, 진단과 제안, 운전원 승인, 냉각 명령, 재관측과 보고를 연결합니다. 회복 뒤의 핀 세척 작업지시도 남깁니다. 레인은 책임을 보여 주는 칸이며 실제 실행 담당은 연결 실습에서 지정합니다.'),
('승인조건과예외','승인 조건과 비중단형 알림','기본 흐름 | 승인 · 회복 여부의 갈림 | 입력','예외 처리 | 거절 종결 · 승인 지연 알림 | 범위','조건을 갖춘 흐름 | cooling.bpmn | 산출물','경계 확인 | 거절에 명령 없음 · 알림 뒤 승인 대기 | 판정','앞에서 그린 흐름에 승인과 거절, 회복과 미달 경로를 넣겠습니다. 승인 작업에는 비중단형 경계 타이머를 붙여 지연 알림을 보낸 뒤에도 사람의 결정을 기다리게 합니다. 거절 경로가 명령으로 이어지지 않는지, 알림 갈래의 끝과 처리 건 전체의 끝을 혼동하지 않았는지 그림과 설정으로 확인하겠습니다.'),
('에이전트와실행연결','BPMN과 실행 기능 연결','작성한 BPMN | 연결 값 참조 자료 | 입력','실행 연결 | 경보 · 에이전트 · 역할 · 시스템 | 범위','매핑 초안 | 내 요소 ID에 맞춘 mapping.json | 산출물','대응 확인 | 그림의 모든 작업에 올바른 연결 | 판정','작성한 BPMN을 가져와 쿨러 경보 시작 조건과 기존 에이전트, 운전원 역할을 연결하겠습니다. 냉각 명령, 재관측, 작업지시와 결과 보고도 각 작업에 맞춥니다. 제공된 연결 값은 직접 그린 요소 ID에 대응시켜 사용합니다. 포털에서 제공하는 설정을 확인하고, 없는 항목은 제공된 API 절차의 적용 가능 범위를 확인한 뒤 보완하겠습니다.'),
('사전검사와배포','연결 오류 점검과 판본 배포','매핑 초안 | 작업 부품과 분기 조건 | 입력','검사와 수정 | 누락 위치 · 사유 · 재검사 | 범위','등록과 배포 | 정의 ID · 판본 · 경보 경로 | 산출물','배포 확인 | 검사 통과와 실행 성공을 구별 | 판정','앞 실습에서 작성한 초안을 검사하고 실제 문제의 위치와 사유를 읽겠습니다. 부품과 분기 조건 등에서 잘못된 항목이 있으면 고치고 다시 검사해 판본으로 등록하고 배포합니다. 문제가 없으면 검사 범위를 남기고 정상 설정을 비우지 않습니다. 등록과 배포는 서로 다른 단계이며, 실행 결과는 다음 실습에서 확인합니다. 공용 환경에서는 마지막 배포가 경보 경로를 바꾸므로 내 환경과 현재 배포 대상을 먼저 확인하겠습니다.'),
('이벤트와처리결과','설비 이벤트와 처리 결과 확인','배포한 판본 | 교육 환경의 쿨러 열화 이벤트 | 입력','처리 경로 | 제안 · 승인 · 명령 · 재관측 · 보고 | 범위','처리 기록 | 사건 · 인스턴스 · 판본 · 결과 | 산출물','결과 판정 | 승인 대기 · 정상 · 거절 · 미달 구별 | 판정','마지막에는 쿨러 열화 이벤트로 자신의 정의와 판본에 처리 건이 열리는지 확인하겠습니다. 승인 대기 상태를 먼저 읽고, 승인 뒤에는 명령 처리와 회복 여부를 따로 확인합니다. 기준 흐름의 여러 에이전트 단계와 중단형 타이머도 수업 흐름과 비교합니다. 아직 얻지 못한 결과는 미확인으로 남기고, 저장한 실제 기록을 바탕으로 복습으로 돌아오겠습니다.')]
for j,(name,label,*v) in enumerate(labs):
 n=60+j*2;cards=v[:4];talk=v[4]
 decks.extend([(n,screen(n,'실습: '+label,'- 유형: 간지\n- 구분: 실습')),(n+1,screen(n+1,label+'의 결과물','- 유형: 카드\n- 메시지: '+{'업무설계도구기본':'저장한 그림을 다시 열어 작업 내용을 확인한다.','승인업무작도':'승인과 반려의 경로를 구분해 표현한다.'}.get(name,'앞 단계의 결과를 이어 받아 흐름과 근거를 확인한다.')+'\n- 요소:\n'+''.join(f'  {k}. {c}\n' for k,c in enumerate(cards,1))))])
 scripts[n]=f'## [SLIDE {n}~{n+1}] 실습: {label}\n\n'+talk
 if j==6:scripts[n]+='\n\n> [진행 — 낭독하지 않음] 73장 뒤 실제 실습04~10 진행. 74장부터 복습 재개.'
for name,a,z in [('01_이론_비즈니스프로세스.md',1,25),('02_이론_BPMN표현.md',26,42),('03_이론_프로세스오케스트레이션.md',43,80)]:write(P/name,'# 실전반 6회차\n\n'+'\n\n---\n\n'.join(scripts[n] for n in sorted(scripts) if a<=n<=z)+'\n')
units=[dict(file=name,kind='pptx',slides=[a,z]) for name,a,z in [('01_이론_비즈니스프로세스.md',1,25),('02_이론_BPMN표현.md',26,42),('03_이론_프로세스오케스트레이션.md',43,80)]]
units += [dict(file=f'{j+4:02}_실습_{lab[0]}.md',kind='practice',status='문서 작성·실행 및 캡처 미검증') for j,lab in enumerate(labs)]
write(P/'구성.json',json.dumps(dict(version=1,day=6,slide_count=80,units=units,playback='1~73장 → 실습04~10 → 74~80장 복습·용어·퀴즈.'),ensure_ascii=False,indent=2)+'\n')
notes=theory_notes(P)
decktext=[]
for n,g in sorted(decks):decktext.append(re.sub(r'^- 노트:.*\n?','',g,flags=re.M).replace('### 화면 구성','- 노트: '+notes[n]+'\n### 화면 구성',1))
write(out/'실전반_06일차.md','# '+title+'\n\n'+''.join(decktext));shutil.copytree(C/'만들기/decks/integrated/day09/figures',out/'figures/day09',dirs_exist_ok=True)
write(P/'원본대응.json',json.dumps(dict(slides=mapping,speech_edits=changes,source_count=74,final_count=80,lab_pairs=[dict(start=60+j*2,name=l[0]) for j,l in enumerate(labs)],coverage='통합반9 1~59 및68~74의66장 모두 보존. 60~67의4개 실습 소개를 실전반 배정7개 소개14장으로 재구성(+6). 통합반10은 실전반7 배정이므로 이번 원본에 포함하지 않음.'),ensure_ascii=False,indent=2)+'\n')
print('assembled',len(decks),'slides',len(scripts),'speech blocks')

