"""3회차 이론 조립. 기존 원본의 본문 단위를 보존한다. 실습 실행 없음."""
from helpers import *
B=EV/'before/산출물/교재/대본/통합반_온라인'
def blocks(folder):
 out={}
 for f in sorted(folder.glob('*_이론_*.md')):
  for b in re.split(r'(?=^## \[SLIDE )',f.read_text('utf8'),flags=re.M)[1:]:
   m=re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]',b);out[int(m[1])]=(int(m[2] or m[1]),b.rstrip().removesuffix('---').rstrip())
 return out
edits=[]
for f in sorted((B/'03회차').glob('*_이론_*.md')):
 t=f.read_text('utf8');old=t
 replacements={
 '이번 시간에는 이번 회차의 세 번째 물음,':'이제 세 번째 물음,',
 '앞 시간에는 지금 해도 되는 조치를 결정표로 가렸죠. 이번 시간에는':'앞에서 지금 해도 되는 조치를 결정표로 가렸죠. 이어서',
 '앞에서 말한 순위 정책':'이 시스템의 순위 정책',
 '다음 시간에는 두 번째 물음':'이어서 두 번째 물음',
 '다음 시간에는 세 번째 물음':'이어서 세 번째 물음',
 '생성된 자료를 실행해 보면서':'생성된 구조를 원문과 대조하면서',
 '직접 만들어 보세요':'제가 직접 만들어 보겠습니다',
 '여러분이 직접':'제가 직접',
 '다음 시간에는 첫 번째 활동':'이제 첫 번째 활동',
 '다음 시간에는 첫 활동':'이제 첫 활동',
 }
 for a,b in replacements.items():t=t.replace(a,b)
 t=re.sub(r'^> \[제작 중단.*$', '> [제작 진행 — 낭독하지 않음] 60장 뒤 04·05·06 실습 대본을 진행한다. 실제 확인 결과에 맞게 말하고 61장부터 복습을 재개한다.',t,flags=re.M)
 write(I/f.name,t)
 if old!=t:edits.append(f.name)
S={3:blocks(I),4:blocks(C/'산출물/교재/대본/통합반_온라인/04회차')}
G={d:re.split(r'(?=^## SLIDE )',(C/f'만들기/decks/integrated/day{d:02}/통합반_{d:02}일차.md').read_text('utf8'),flags=re.M)[1:] for d in [3,4]}
mapping=[(3,n) for n in [1,2,3]+list(range(34,57))+[59,60]]+[(4,n) for n in range(4,63)]+[(3,61),(4,63),(3,62),(4,64),(3,63)]+[(3,n) for n in range(64,67)]+[(4,n) for n in range(66,69)]+[(3,67),(4,69)]
assert len(mapping)==100
out=D/'만들기/decks/practical/day03';out.mkdir(parents=True,exist_ok=True);P.mkdir(parents=True,exist_ok=True)
decks=[];scripts={};changes=[]
for dest,(day,n) in enumerate(mapping,1):
 g=G[day][n-1];g=re.sub(r'^## SLIDE \d+',f'## SLIDE {dest:02}',g).replace('figures/',f'figures/day{day:02}/')
 if day==3:g=re.sub(r'(?m)^- 번호: (\d+)',lambda m:f'- 번호: {int(m[1])-5:02}',g)
 else:g=re.sub(r'(?m)^- 번호: (\d+)',lambda m:f'- 번호: {int(m[1])+3:02}',g)
 if day==4 and n in [66,67,68,69]:g=re.sub(r'Quiz ([123])',lambda m:'Quiz '+str(int(m[1])+3),g)
 if n in S[day]:
  end,b=S[day][n];original=b
  if day==3:
   b=b.replace('여섯 번째 단원','첫 번째 단원').replace('일곱 번째 단원','두 번째 단원').replace('여덟 번째 단원','세 번째 단원')
   if n==34:b=b.replace('이제 세 번째 물음,','이번 회차에서는').replace('앞에서 지금 해도 되는 조치를 결정표로 가렸죠.','지난 회차에 지금 해도 되는 조치를 결정표로 가렸죠.').replace('세 실습','두 실습')
   if n==45:b=b.replace('마지막 이론 단원','세 번째 이론 단원')
   if n==55:b=b.replace('이어지는 두 실습','이어지는 판단 기능 실습')
   if n==59:
    b=b.replace('마지막 실습에서는 두 번째 실습에서 만들 결정표','두 번째 실습에서는 지난 회차에 만든 결정표')
    b=b.replace('세 실습은 판단 결과를 비교하는 데서 시작해서, 그 판단의 기준을 만들고, 기준대로 동작하는지 시험하는 순서입니다.','두 실습은 판단 결과를 비교한 뒤, 지난 회차의 조건표를 읽는 기능을 만들고 기준대로 동작하는지 시험하는 순서입니다.')
    b=b.replace('세 번째 실습','두 번째 실습').replace('앞 실습에서 만든','지난 회차에 만든').replace('둘째 실습에서 만든','지난 회차에 만든').replace('두 번째 실습에서 만든','지난 회차에 만든')
    b=re.sub(r'^> \[제작 진행.*$', '> [제작 진행 — 낭독하지 않음] 28장 뒤 실습 1·2를 진행하고 29장 인제스천부터 재개한다.',b,flags=re.M)
   if n==63:b=b.replace('세 문제','여섯 문제')
   if n==66:b=b.replace('마지막 문제예요','세 번째 문제예요')
   if n==67:b=b[:b.index('이번 회차에서는 조치의 절차')].rstrip()+'\n\n이어서 문서와 출처에 관한 세 문제의 근거도 확인하겠습니다.'
  else:
   ren={'첫 번째 단원':'네 번째 단원','두 번째 단원':'다섯 번째 단원','세 번째 단원':'여섯 번째 단원','네 번째 단원':'일곱 번째 단원','다섯 번째 단원':'여덟 번째 단원'}
   b=re.sub('|'.join(ren),lambda m:ren[m[0]],b)
   b=b.replace('3회차에서','앞에서').replace('3회차에','앞에서').replace('2회차와 3회차가','지난 회차와 이번 회차 앞부분이')
   b=b.replace('네 회차에 걸쳐','세 회차에 걸쳐').replace('1회차부터 4회차까지','1회차부터 이번 회차까지')
   if n==4:b=b.replace('이번 회차의 첫 물음','이어서 다룰 물음').replace('첫 단원은','네 번째 단원은').replace('그럼 첫 단원,','이어서 네 번째 단원,')
   if n==15:b=b.replace('둘째 실습','네 번째 실습')
   if n==34:b=b.replace('3회차에서','지난 회차에서')
   if n in [39,41,43]:
    b=b.replace('세 번째 실습','다섯 번째 실습').replace('두 번째 실습','네 번째 실습').replace('첫 번째 실습','세 번째 실습').replace('첫 실습','세 번째 실습').replace('두 번째는','두 번째는')
    b=b.replace('사용하게 될 추출 과정','확인한 추출 과정').replace('여러분이 직접 쓰는','제가 직접 쓰는').replace('꼭 넣으세요','함께 넣겠습니다')
    b=b.replace('3회차의 조치와 규칙 구조','지난 회차의 조치와 규칙 구조')
    b=b.replace('다음 시간에는 첫 번째 활동인','이제 세 번째 실습인')
    b=re.sub(r'^> \[제작 중단.*$', '> [제작 진행 — 낭독하지 않음] 69장 뒤 실습 3·4·5를 진행하고 70장 전체 정리부터 재개한다.',b,flags=re.M)
   if n==46:b=b.replace('각 회차의 주제','학습 단계의 주제').replace('3회차에는 조치 방법과 판단 규칙과 성과 지표가','지난 회차와 이번 회차 앞부분에는 조치 방법과 판단 규칙과 성과 지표가').replace('그 회차에','그 단계에서')
   if n==49:b=b.replace('3회차의 입력은','지난 회차 조건표의 입력은')
   if n==50:b=b.replace('3회차의 결과물이','이번 회차 앞부분의 결과물이')
   if n==57:b=b.replace('앞에서 자세히 봤어요','앞부분에서 자세히 봤어요')
   if n in [66,67,68,69]:
    b=re.sub(r'Quiz ([123])',lambda m:'Quiz '+str(int(m[1])+3),b)
    b=b.replace('첫 번째 문제','네 번째 문제').replace('두 번째는','다섯 번째는').replace('첫 문제의 정답','네 번째 문제의 정답').replace('두 번째 문제의 정답','다섯 번째 문제의 정답').replace('세 번째 문제의 정답','여섯 번째 문제의 정답')
  if b!=original:changes.append(dict(source_day=day,source_slide=n,destination=dest))
  b=re.sub(r'^## \[SLIDE \d+(?:~\d+)?\]',f'## [SLIDE {dest}'+(f'~{dest+end-n}' if end>n else '')+']',b)
  scripts[dest]=b
 decks.append(g)
# Metadata states the actual assembled curriculum. Core source content is retained.
title='조치 비교와 문서 지식의 검증'
def screen(n,title,body):return f'## SLIDE {n:02} — {title}\n### 화면 내용\n{body}\n### 화면 구성\n기존 교재 유형과 배치를 따른다.\n### 제작 기준\n실전반 3회차 실라버스의 배정과 원본 대응표.\n\n'
decks[0]=screen(1,title,'- 유형: 표지\n- 기관: 경남대학교 피지컬AI 사관학교\n- 과정: 실전반 3회차 · 성과 평가와 인제스천\n- 부제: 가능한 조치의 득실을 비교하고, 문서에서 온 지식의 근거를 검증한다\n- 아이콘: scale, file-check, network')
decks[1]=screen(2,'학습목표','- 유형: 카드\n- 메시지: 성과 기준으로 조치를 비교하고, 검토한 지식을 출처와 함께 연결한다.\n- 요소:\n  1. 성과 비교 | 목표와 KPI를 구별한다 / 후보의 득실과 가정을 비교한다 | BSC · KPI\n  2. 판단 기능 | 지난 회차의 조건표를 읽는다 / 경계값과 적용 대상을 검증한다 | 조건과 근거\n  3. 문서 지식 | 원문에서 후보를 추출한다 / 검토한 내용만 그래프에 반영한다 | 인제스천\n  4. 전체 연결 | 스키마 · 지식 · 값을 구별한다 / 추천의 경로와 출처를 설명한다 | 판단 근거')
decks[2]=screen(3,'목차','- 유형: 목차\n- 요소:\n  1. BSC · KPI · 전략맵 | 이론\n  2. 조치 비교와 What-if | 이론\n  3. 결과 비교 · 판단 기능 만들기 | 실습 1~2\n  4. 원문 보관 · 추출 · 매핑 · 검토 | 이론\n  5. 승인 적재 · 개정 · 지식과 값 | 이론\n  6. 매뉴얼 검토 · 지식 추출 · 그래프 반영 | 실습 3~5\n  7. 온톨로지 설계에서 판단 근거까지 | 전체 정리\n  8. 복습 · 용어 · 퀴즈 | 마무리')
scripts[1]=f'## [SLIDE 1] {title}\n\n지난 회차에는 작업 절차와 판단 조건을 정리했습니다. 이번 회차에서는 조건을 통과한 조치들의 효과와 비용을 비교하겠습니다. 이어서 그 판단에 쓸 지식을 문서에서 추출하고, 원문과 대조한 뒤 출처와 함께 그래프에 연결하겠습니다.'
scripts[2]='## [SLIDE 2] 학습목표\n\n성과 목표와 KPI를 구별하고, 한 조치가 생산과 안전, 에너지에 주는 영향을 함께 보겠습니다. 지난 회차의 조건표는 판단 기능의 입력으로 이어집니다. 문서를 다룰 때는 추출 결과를 바로 사실로 쓰지 않고, 원문과 대조해 검토한 것만 반영하겠습니다. 마지막에는 스키마와 지식, 값이 추천의 근거로 이어지는 전체 흐름을 정리합니다.'
scripts[3]='## [SLIDE 3] 목차\n\n먼저 BSC와 KPI, 전략맵으로 조치의 득실을 비교합니다. 결과 비교와 판단 기능 만들기를 마친 뒤에는 문서에서 지식을 들여오는 과정을 배웁니다. 포털에서 매뉴얼을 검토하고, 추출 기능과 그래프 반영 기능을 차례로 만들겠습니다. 마지막에 지금까지의 결과물을 연결하고, 용어와 여섯 퀴즈를 정리합니다.'
# Theory files follow teaching breaks; practice files are authored separately.
units=[]
for name,a,b in [('01_이론_성과평가와조치비교.md',1,28),('02_이론_문서에서검증된지식으로.md',29,69),('03_이론_판단근거와전체정리.md',70,100)]:
 write(P/name,'# 실전반 3회차\n\n'+'\n\n---\n\n'.join(scripts[n] for n in sorted(scripts) if a<=n<=b)+'\n');units.append(dict(file=name,kind='pptx',slides=[a,b]))
for i,name in enumerate(['조치결과비교','판단기능만들기','매뉴얼검토','지식추출','그래프반영'],4):units.append(dict(file=f'{i:02}_실습_{name}.md',kind='practice',status='문서 작성·실행 및 캡처 미검증'))
write(P/'구성.json',json.dumps(dict(version=1,day=3,slide_count=100,units=units,playback='1~28장 → 실습 1·2 → 29~69장 → 실습 3·4·5 → 70~100장 전체 정리·복습·용어·퀴즈.'),ensure_ascii=False,indent=2)+'\n')
notes=theory_notes(P)
for n,g in enumerate(decks,1):decks[n-1]=re.sub(r'^- 노트:.*\n?','',g,flags=re.M).replace('### 화면 구성','- 노트: '+notes[n]+'\n### 화면 구성',1)
write(out/'실전반_03일차.md','# '+title+'\n\n'+''.join(decks))
for day in [3,4]:shutil.copytree(C/f'만들기/decks/integrated/day{day:02}/figures',out/f'figures/day{day:02}',dirs_exist_ok=True)
write(P/'원본대응.json',json.dumps(dict(slides=[dict(destination=i,source_day=d,source_slide=n) for i,(d,n) in enumerate(mapping,1)],speech_edits=changes,metadata_rewritten=[1,2,3],source3_BSC_34_to_54_complete=True,source4_content_4_to_64_complete=True,quiz6_complete=True,omissions='통합반3 SOP·DMN 4~33은 실전반2에서 전체 사용. 조치기준 만들기 소개57~58은 실전반2 조건표로 대체된 실습 배정. 통합반4 표지·목표·목차1~3과 중복 퀴즈 간지65는 공통 메타정보로 통합. 본문 삭제 없음.'),ensure_ascii=False,indent=2)+'\n')
print('assembled 100 slides',len(scripts),'speech blocks')
