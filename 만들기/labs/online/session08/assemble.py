"""통합반8 검토 반영 및 통합반11 전체를 실전반8로 조립한다."""
from helpers import *
B=EV/'before/산출물/교재/대본/통합반_온라인'
edits=[]
changesI={30:[('다시 실행하세요.','다시 실행하겠습니다.')],31:[('점검해 주세요.','점검하겠습니다.'),('함께 남겨 주세요.','함께 남기겠습니다.')],33:[('적어 주세요.','적겠습니다.'),('구별하세요.','구별하겠습니다.')],35:[('가려 주세요.','가려 보겠습니다.'),('기록하세요.','기록하겠습니다.')],37:[('붙이세요.','붙이겠습니다.'),('다음 시간에는 시나리오 작성부터','이제 시나리오 작성부터')]}
changesP={1:[('같은 구조를 각자의 작은 업무로 직접 만들어 봅니다.','같은 구조를 강사가 고른 작은 업무로 직접 만들어 봅니다.')],2:[('각자에게 친숙한 작은 업무 하나를 골라서','친숙한 작은 업무 하나를 제가 골라서')],21:[('다음 시간에는 이 추천안이','이어서 이 추천안이')],41:[('이번엔 쿨러가 아니라 각자의 업무 위에서요.','이번엔 쿨러가 아니라 강사가 고른 회의 준비 업무 위에서요.'),('먼저 각자에게 친숙한 작은 업무 하나를 고르게 돼요.','먼저 강사가 친숙한 작은 업무 하나를 고릅니다.'),('뒤의 실습에서는 이 명세부터 적습니다.','실제 실습에서는 이 명세부터 적겠습니다.')],58:[('실습과 시연을 마친 뒤 다시 모였습니다.','실습과 시연에서 남긴 기록으로 돌아왔습니다.'),('학습 노트에는 완성한 결과뿐 아니라 아직 확인하지 못한 것도 구분해 두세요.','학습 노트에는 완성한 결과와 아직 확인하지 못한 것을 구분해 두겠습니다.')]}
def prepare(day,folder,changes,course):
 for f in (B/f'{day:02}회차').glob('*_이론_*.md'):
  t=f.read_text('utf8').replace(f'통합반 {day}회차',f'{course} 8회차').replace('실제 실습은 별도 빈 파일이다.','실습 진행 대본은 별도로 관리한다.').replace('실습 파일은 0바이트이다.','실습 대본의 진행 순서와 확인 기록을 따른다.').replace('실제 외부 화면 실습03~08은 별도 빈 파일이며','실제 외부 화면 실습03~08은 별도 진행 대본이며')
  if course=='실전반':t=t.replace('에이전트의 결과가 업무 완료로 이어지는 전체 구조 복습하기','에이전트가 사람과 시스템을 통해 업무를 완료하는 구조 복습하기')
  blocks=re.split(r'(?=^## \[SLIDE )',t,flags=re.M)
  for j in range(1,len(blocks)):
   n=int(re.match(r'## \[SLIDE (\d+)',blocks[j])[1])
   for a,b in changes.get(n,[]):
    assert a in blocks[j],(course,n,a)
    blocks[j]=blocks[j].replace(a,b);edits.append(dict(course=course,slide=n,before=a,after=b,reason='강사 단독 진행 주체와 촬영 구간 연결 정정; 본론·조건·예외 보존'))
  write(folder/f.name,''.join(blocks))
 cfg=json.loads((B/f'{day:02}회차/구성.json').read_text('utf8'));cfg['day']=8
 for u in cfg['units']:
  if u['kind']=='empty_practice':u.update(kind='practice',status='문서 작성·실행 및 캡처 미검증')
 write(folder/'구성.json',json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
prepare(8,I,changesI,'통합반');prepare(11,P,changesP,'실전반')
out=D/'만들기/decks/practical/day08';out.mkdir(parents=True,exist_ok=True)
t=(EV/'before/만들기/decks/integrated/day11/통합반_11일차.md').read_text('utf8');notes=theory_notes(P)
blocks=re.split(r'(?=^## SLIDE )',t,flags=re.M)
for n in range(1,65):
 blocks[n]=re.sub(r'^- 노트:.*\n?','',blocks[n],flags=re.M).replace('### 화면 구성','- 노트: '+notes[n]+'\n### 화면 구성',1).replace('figures/','figures/day11/')
 if n==1:blocks[n]=blocks[n].replace('- 과정: 온톨로지 · 에이전트 · 프로세스를 내 주제에 적용하고 마무리하기','- 과정: 실전반 8회차 · 내 주제에 적용하고 지식 자산으로 마무리하기')
write(out/'실전반_08일차.md',''.join(blocks));shutil.copytree(EV/'before/만들기/decks/integrated/day11/figures',out/'figures/day11',dirs_exist_ok=True)
write(P/'원본대응.json',json.dumps(dict(source_root=str(C),source_day=11,source_count=64,final_count=64,slides=[dict(destination=n,source_day=11,source_slide=n) for n in range(1,65)],coverage='64장 전체 같은 순서. 본론·실습/시연6개·복습·용어·퀴즈3개·정답 보존. 삭제·압축 없음.',screen_changes=[1],syllabus_rows=list(range(89,97))),ensure_ascii=False,indent=2)+'\n')
write(EV/'speech-edits.json',json.dumps(edits,ensure_ascii=False,indent=2))
print('assembled 61 / 64 slides, complete source coverage')
