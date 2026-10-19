"""통합반7 점검과 통합반10 전체를 실전반7로 조립. 실습 실행 없음."""
from helpers import *
B=EV/'before/산출물/교재/대본/통합반_온라인'
replacementsI={
'승인 역할을 먼저 확인하세요.':'승인 역할을 먼저 확인하겠습니다.',
'어떻게 바뀌었는지 읽어 보세요.':'어떻게 바뀌었는지 읽어 보겠습니다.',
'받아들여지지 않는지 확인하세요.':'받아들여지지 않는지 확인하겠습니다.',
'요청을 에이전트에 줘 보세요.':'요청을 에이전트에 넣어 보겠습니다.',
'상태를 기록으로 남기세요.':'상태를 기록으로 남기겠습니다.',
'원래 근거와 대조하세요.':'원래 근거와 대조하겠습니다.',
'다음 시간에는 승인과 질문, 제안과 검토를':'이제 승인과 질문, 제안과 검토를',
'비교의 기준으로 남겨 두세요.':'비교의 기준으로 남겨 두겠습니다.',
'두 버전에 똑같이 넣어 보세요.':'두 버전에 똑같이 넣어 보겠습니다.',
'실패를 일부러 만들지 마세요.':'실패를 일부러 만들지는 않겠습니다.',
'나누어 기록하세요.':'나누어 기록하겠습니다.',
'요청을 다시 실행하세요.':'요청을 다시 실행하겠습니다.',
'기대 결과를 저장해 두세요.':'기대 결과를 저장하겠습니다.',
'다음 시간에는 모호한 변경의 비교부터':'이제 모호한 변경의 비교부터',
}
for f in (B/'07회차').glob('*_이론_*.md'):
 t=f.read_text('utf8')
 for a,b in replacementsI.items():t=t.replace(a,b)
 t=t.replace('실제 실습은 별도 빈 파일이다.','실습 진행 대본은 별도로 관리한다.').replace('현재 실습 파일은 비어 있다.','실습 대본의 진행 순서와 확인 기록을 따른다.')
 write(I/f.name,t)
P.mkdir(parents=True,exist_ok=True)
changes={
1:[('이런 업무마다 프로세스를 처음부터 새로 만들어야 할까요? 긴급 대응에서 그대로 가져다 쓸 수 있는 건 뭐고, 바꿔야 하는 건 뭘까요?','긴급 대응에서 다시 쓸 구조와 업무마다 바꿔야 할 조건을 가르면, 새 업무도 기존 설계를 바탕으로 만들 수 있습니다.'),('이번 회차는 이 물음에서 출발합니다.','이번 회차는 이 구분에서 출발합니다.')],
32:[('구별하세요.','구별하겠습니다.'),('이 실습을 마치면 정기 점검의 처리 건 하나가 끝까지 간 기록으로 남고,','이 실습에서는 정기 점검의 승인·거절 처리 기록을 남기고,')],
36:[('가용 재고가 1개에서 7개로 올라가고, 결과 보고가 입고 완료로 남아야 해요.','제시된 시작 조건과 6개 발주안을 그대로 사용했다면 가용 재고가 1개에서 7개로 올라가고, 결과 보고가 입고 완료로 남아야 해요. 시작 재고나 승인 수량이 달랐다면 그 값으로 기대 재고를 계산해 실제 입고 기록과 대조합니다.'),('직접 그린 두 프로세스가 모두 처리 건을 끝까지 보낸 셈이고,','직접 그린 두 프로세스의 진행 결과와 미확인이 기록으로 남고,'),('다음 시간부터 정기 점검 작도와 실행,','이제 정기 점검 작도와 실행,')],
38:[('여러분이 보낸 것과 같은 모양으로','강사가 확인한 기록과 비교할 수 있도록'),('여러분의 처리 건과 다른 건 그래서예요.','실습의 처리 건과 다른 건 그래서예요.')],
51:[('3회차에서 조치 절차로 적어 둔','앞서 조치 절차로 적어 둔')],
}
for f in (B/'10회차').glob('*_이론_*.md'):
 t=f.read_text('utf8').replace('통합반 10회차','실전반 7회차').replace('실제 실습은 별도 빈 파일이다.','실습 진행 대본은 별도로 관리한다.').replace('별도 빈 실습 파일','별도 실습 대본')
 t=t.replace('다양한 업무를 하나의 프로세스 설계 원리로 관리하기','여러 업무의 시작 조건과 실행 결과를 일관되게 관리하기').replace('AI와 사람이 함께 수행하는 전체 업무 흐름 정리하기 — Wrap-up','프로세스 설계·실행·검증 과정 정리하기 — Wrap-up')
 chunks=re.split(r'(?=^## \[SLIDE )',t,flags=re.M)
 for j in range(1,len(chunks)):
  n=int(re.match(r'## \[SLIDE (\d+)',chunks[j])[1])
  for a,b in changes.get(n,[]):
   assert a in chunks[j],(n,a);chunks[j]=chunks[j].replace(a,b)
 write(P/f.name,''.join(chunks))
cfg=json.loads((B/'10회차/구성.json').read_text('utf8'));cfg['day']=7;cfg['playback']='1~37장 → 실습02~05 → 38~61장 전체 흐름·복습·용어·퀴즈.'
for u in cfg['units']:
 if u['kind']=='empty_practice':u['kind']='practice';u['status']='문서 작성·실행 및 캡처 미검증'
write(P/'구성.json',json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
out=D/'만들기/decks/practical/day07';out.mkdir(parents=True,exist_ok=True)
t=(EV/'before/만들기/decks/integrated/day10/통합반_10일차.md').read_text('utf8')
notes=theory_notes(P);chunks=re.split(r'(?=^## SLIDE )',t,flags=re.M)
for n in range(1,62):
 chunks[n]=re.sub(r'^- 노트:.*\n?','',chunks[n],flags=re.M).replace('### 화면 구성','- 노트: '+notes[n]+'\n### 화면 구성',1).replace('figures/','figures/day10/')
 if n==1:chunks[n]=chunks[n].replace('- 과정: 설비 대응을 넘어 정비와 구매 업무까지 자동으로 연결하기','- 과정: 실전반 7회차 · 정비와 구매 업무의 설계·실행·검증')
 if n==37:chunks[n]=chunks[n].replace('가용 재고가 / 1개에서 7개로, / 결과 보고: 입고 완료','시작 값·승인 수량으로 대조 / 예: 가용 재고 1→7개 / 결과 보고: 입고 완료')
write(out/'실전반_07일차.md',''.join(chunks));shutil.copytree(EV/'before/만들기/decks/integrated/day10/figures',out/'figures/day10',dirs_exist_ok=True)
write(P/'원본대응.json',json.dumps(dict(source_day=10,source_count=61,final_count=61,slides=[dict(destination=n,source_day=10,source_slide=n) for n in range(1,62)],coverage='통합반10 61장 전체 보존. 본론·실습4쌍·복습·용어·퀴즈3개·정답 모두 동일 순서.',speech_edit_candidates=list(changes)),ensure_ascii=False,indent=2)+'\n')
print('assembled integrated60/practical61; no core deletions')
