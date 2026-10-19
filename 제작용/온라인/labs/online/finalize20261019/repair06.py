"""현재6회차의 불일치만 수정. 역사적 근거와 시작 원본은 쓰지 않는다."""
from helpers import *

IP=C/'산출물/교재/대본/통합반_온라인/06회차';PP=D/'산출물/교재/대본/실전반_온라인/06회차'
edits=[]
def replace(p,a,b,reason):
 s=p.read_text('utf8')
 if b in s and a not in s:return
 assert a in s,(p,a)
 write(p,s.replace(a,b));edits.append(dict(path=str(p),before=a,after=b,reason=reason))
replacements=[
('통합반','07_실습_학습코치.md','이어서 다음 문항에 일부러 근거와 다른 답을 넣어 오답 피드백을 확인합니다. 정답을 맞힌 경우와 틀린 경우 모두 출처만 붙이는 데 그치지 않고 그 문장이 판단을 뒷받침하는지 확인하겠습니다. 근거가 없는 내용을 물으면 판단을 보류하는지도 보겠습니다.','이어지는 문항도 현재 이해한 내용으로 직접 답하겠습니다. 맞거나 틀렸다는 판정은 실제 답변과 원문으로 확인하고, 출처 문장이 그 판단을 뒷받침하는지 보겠습니다. 틀린 답이나 근거 부족이 실제로 확인되면 교정 또는 판단 보류의 이유를 읽습니다. 이번에 나오지 않은 경우는 미확인으로 남기고, 오답 장면을 만들기 위해 답을 바꾸지 않겠습니다.','실제 답변의 근거 판정을 유지하고 오답 연출 제거'),
('실전반','06_실습_설비이상대응작도.md','앞 실습의 승인 구조를 참고해 편집기에서 새 흐름을 만들겠습니다.','앞 실습의 approval.bpmn을 input에 복사하고 편집기에서 열겠습니다. 원본을 보존하고 cooling-draft.bpmn으로 따로 저장한 뒤 기존 승인 구조에 역할과 작업을 보태겠습니다.','앞 실습의 실제 결과 이어 쓰기'),
('실전반','08_실습_에이전트와실행연결.md','참조 파일의 ID가 내 그림에 존재하는지와 필요한 연결이 빠지지 않았는지 확인한 뒤 검사 단계로 넘어가겠습니다.','참조 파일의 ID가 내 그림에 존재하는지와 필요한 연결이 빠지지 않았는지 확인하겠습니다. BPMN·조건 계획·내 매핑을 저장한 뒤 VS Code와 포털에서 다시 열어 같은 ID와 설정인지 대조하고 검사 단계로 넘어가겠습니다.','저장·재열기 확인 보완'),
('실전반','09_실습_사전검사와배포.md','오류 사례는 배포하지 않은 별도 연습 초안에서 확인합니다.','지금 작성한 초안을 검사하며 실제로 발견한 문제만 수정하겠습니다.','오류 만들기 제거'),
('실전반','09_실습_사전검사와배포.md','먼저 연습 초안에서 냉각 명령 작업의 부품 선택을 비우고 사전 검사를 요청하겠습니다. 검사 결과에서 해당 작업과 part 항목, 부품을 고르라는 사유가 잡히는지 보겠습니다. 실제로 표시된 문구를 review.md에 적고 PLC 명령 부품을 복원해 다시 검사합니다. 예상한 오류가 나오지 않으면 성공한 실패 시연으로 처리하지 않고 현재 설정과 검사의 범위를 확인합니다.','사전 검사를 요청하고 반환된 작업·선의 위치와 field, reason을 현재 BPMN과 매핑에 대조하겠습니다. 부품 관련 문제가 실제로 있으면 그 작업의 ID와 part 값, 교육 환경의 부품 목록을 확인합니다. 냉각 명령 작업에는 PLC 명령 부품이 맞는지 보고 잘못된 연결이나 누락을 고친 뒤 저장하고 다시 검사합니다. 실제 문구와 수정 이유는 review.md에 적겠습니다.','부품 검사 개념은 보존하고 실제 문제에 따른 수정으로 변경'),
('실전반','09_실습_사전검사와배포.md','다음에는 승인 분기의 조건을 비우고 기본 경로 표시도 없는 상태로 검사하겠습니다. 해당 선의 condition 누락 사유를 확인하고 승인 결과가 승인과 같다는 조건을 복원합니다. 선의 표시 이름을 ‘승인’으로 쓴 것만으로 조건이 생기지 않는다는 점을 여기서 확인합니다. 한 항목씩 바꾸고 복원해야 어떤 수정으로 문제가 사라졌는지 알 수 있습니다.','분기 조건에 관한 문제가 있으면 해당 선의 condition과 기본 경로 표시를 읽겠습니다. 승인 선은 승인 결과가 승인과 같다는 조건인지, 반대 선은 기본 경로인지 확인합니다. 선의 표시 이름을 ‘승인’으로 쓴 것만으로 조건이 생기지는 않습니다. 실제로 잘못된 항목을 하나씩 고쳐 재검사하고 어느 수정으로 문제가 해소됐는지 기록하겠습니다.','조건 검사 설명 보존, 조건 삭제로 실패 만드는 단계 제거'),
('실전반','09_실습_사전검사와배포.md','정상 초안으로 돌아와 모든 작업·조건·타이머와 담당을 검사하겠습니다. 경고나 오류가 남으면 위치와 사유를 읽고 고칩니다.','현재 초안의 모든 작업·조건·타이머와 담당을 검사하겠습니다. 경고나 오류가 남으면 위치와 사유를 읽고 고칩니다. 문제가 없으면 정상 설정을 비우지 않고 확인한 검사 범위와 응답을 남깁니다.' ,'정상 초안 훼손 금지'),
('실전반','09_실습_사전검사와배포.md','내보낸 BPMN·매핑, 검사 결과와 배포 기록을 저장합니다.','내보낸 BPMN·매핑, 검사 결과와 배포 기록을 저장하고 VS Code와 포털에서 다시 열어 정의 ID와 판본·경보 경로를 대조하겠습니다.','저장·재열기 명시'),
('실전반','10_실습_이벤트와처리결과.md','승인 권한이 있는 교육용 계정으로 추천안과 현재 조건을 검토하고 조치를 승인하겠습니다.','승인 권한이 있는 교육용 계정으로 추천안과 현재 조건을 검토하겠습니다. 근거와 조건이 충족된 경우에 조치를 선택해 승인하고, 부족하면 보류와 이유를 남깁니다. 승인한 경우에는 다음 기록을 확인하겠습니다.','승인·성공을 미리 확정하지 않음'),
('실전반','10_실습_이벤트와처리결과.md','review.md에 사건·처리 건·정의·판본, 승인 대기와 종료 시각, 명령·재관측·보고의 실제 근거를 적겠습니다.','기대한 흐름과 다르면 사건 입력, 매핑, 실제 호출·승인 기록 중 어디에서 달라졌는지 보겠습니다. 원인을 확인해 고칠 때는 이전 정의 판본과 결과를 보존하고 새 판본의 재검사를 거쳐 별도 사건으로 재확인합니다. 다시 실행하지 못한 범위는 미확인으로 남깁니다. review.md에 사건·처리 건·정의·판본, 실제 확인한 승인 대기와 종료 시각, 명령·재관측·보고의 근거를 적겠습니다.','실제 차이에 따른 수정·재확인 경로 보완')]
for course,name,a,b,reason in replacements:
 replace((IP if course=='통합반' else PP)/name,a,b,reason)
 replace(D/'만들기/labs/online/session06/labs.py',a,b,'재생성 원본 동기화: '+reason)
a='작업 부품과 분기 조건을 빠뜨린 별도 초안에서 검사 사유를 읽고 원래 연결로 고치겠습니다. 정상 초안을 다시 검사해 판본으로 등록하고 배포합니다.'
b='앞 실습에서 작성한 초안을 검사하고 실제 문제의 위치와 사유를 읽겠습니다. 부품과 분기 조건 등에서 잘못된 항목이 있으면 고치고 다시 검사해 판본으로 등록하고 배포합니다. 문제가 없으면 검사 범위를 남기고 정상 설정을 비우지 않습니다.'
replace(PP/'03_이론_프로세스오케스트레이션.md',a,b,'실습70~71 소개에서 강제 실패 제거')
replace(D/'만들기/labs/online/session06/assemble.py',a,b,'재생성 소개문 동기화')
fix=json.loads((D/'.evidence/session09/speech-edits.json').read_text('utf8'))[-1]
replace(PP/'03_이론_프로세스오케스트레이션.md',fix['before'],fix['after'],'통합반9 68장↔실전반6 74장 강사 진행·미확인 표현 일치')
api_old='오류 사례는 별도 미배포 초안에서만 검사한다.'
api_new='현재 작성한 미배포 초안에서 실제 문제만 검사·수정하며 정상 설정을 일부러 지우지 않는다.'
record_old='## 부품 누락: 실제 위치·사유·복원·재검사\n\n## 조건 누락: 실제 위치·사유·복원·재검사'
record_new='## 실제 검사 응답·확인 범위\n\n## 발견한 문제 위치·사유(없으면 없음)\n\n## 수정·저장·재검사(수정 없으면 해당 없음)'
replace(D/'만들기/labs/online/session06/materials.py',api_old,api_new,'API 절차의 강제 오류 전제 제거')
replace(D/'만들기/labs/online/session06/materials.py',record_old.replace('\n','\\n'),record_new.replace('\n','\\n'),'빈 배포 기록 양식 동기화')
for lab in (D/'산출물/실습/실전반_온라인').glob('06일차_실습*'):
 if not lab.is_dir():continue
 api=lab/'코드/API_연결절차.md'
 if api.exists():replace(api,api_old,api_new,'현재 배포 입력자료 정정')
 record=lab/'코드/deployment-record.md'
 if record.exists():replace(record,record_old,record_new,'검사 실패를 전제하지 않는 기록 양식')
write(EV/'repair06-edits.json',json.dumps(edits,ensure_ascii=False,indent=2))
# 통합반9에서 바로잡은 화면45 문법도 함께 반영한다.
deck=D/'만들기/decks/practical/day06/실전반_06일차.md';a='HYD에서는 경보로 열린 처리 건을 이 엔진이 정의의 조건에 따라 진행을 관리한다.';b='HYD에서는 이 엔진이 정의의 조건에 따라 경보로 열린 처리 건의 진행을 관리한다.'
if a in deck.read_text('utf8'):
 replace(deck,a,b,'통합반9↔실전반6 화면45 문법 동기화')
 path=D/'산출물/교재/PPTX/실전반_온라인/실전반_06일차.pptx';out=io.BytesIO()
 with zipfile.ZipFile(path) as z:
  r=E.fromstring(z.read('ppt/slides/slide45.xml'));found=0
  for e in r.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
   if e.text and a in e.text:e.text=e.text.replace(a,b);found+=1
  assert found==1
  with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as w:
   for item in z.infolist():w.writestr(item,E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True) if item.filename=='ppt/slides/slide45.xml' else z.read(item.filename))
 path.write_bytes(out.getvalue())
write(EV/'repair06-edits.json',json.dumps(edits,ensure_ascii=False,indent=2))
# 화면은 변경하지 않고 발표자 노트·덱 원본 노트만 갱신한다.
patch_notes(PP,80,D/'만들기/decks/practical/day06/실전반_06일차.md',D/'산출물/교재/PPTX/실전반_온라인/실전반_06일차.pptx')
for root,course,folder,practical in [(C,'통합반',IP,False),(D,'실전반',PP,True)]:
 # 모든 현재 실습 원본으로 대본 파생물을 동기화하되 입력 자료는 재생성하지 않는다.
 for src in sorted(folder.glob('*_실습_*.md')):
  name=src.stem.split('_실습_',1)[1];lab=next(p for p in (root/f'산출물/실습/{course}_온라인').glob('06일차_실습*_'+name) if p.is_dir())
  text=src.read_text('utf8');changed=(lab/'강사대본.md').read_text('utf8')!=text
  if changed:
   write(lab/'강사대본.md',text);pdf(speech(text),lab/'강사대본.pdf')
   oldhtml=(lab/'안내.html').read_text('utf8');start=oldhtml.index('<h1>');segments=[]
   for para in text.strip().split('\n\n'):
    tag='h1' if para.startswith('# ') else 'h2' if para.startswith('## ') else 'aside' if para.startswith('>') else 'p'
    segments.append('<'+tag+'>'+html.escape(re.sub(r'^(?:#{1,2} |> ?)', '',para))+'</'+tag+'>')
   write(lab/'안내.html',oldhtml[:start]+''.join(segments)+'</html>')
  # 양식 변경도 반영. ZIP의 모든 파일은 현재 풀린 배포본과 일치한다.
  if changed or (lab/'코드/API_연결절차.md').exists():
   with zipfile.ZipFile(lab.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(lab.rglob('*')):
     if f.is_file():z.write(f,f.relative_to(lab).as_posix())
 merge(root,folder,practical)
 merged=folder.parent/f'{course}_06일차_대본.md';write(merged,re.sub(r'\]\((\d{2}_[^/)]+\.md)\)',r'](06회차/\1)',merged.read_text('utf8')))
 if practical:pdf((folder.parent/f'낭독본/{course}_06일차_낭독본.md').read_text('utf8'),folder.parent/f'{course}_06일차_대본.pdf')
 alltext='\n\n'.join(speech(f.read_text('utf8')) for f in sorted(folder.glob('*_실습_*.md')));write(folder/'실습_낭독합본.md',alltext);pdf(alltext,folder/f'{course}_06일차_실습대본.pdf')
write(EV/'repair06-pdf-check.json',json.dumps(checks,ensure_ascii=False,indent=2))
print('6회차 정정과 파생 문서 동기화 완료. 실제 실행 없음.')
