from helpers import *
source_manifest=[]
def copy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);source_manifest.append(dict(source=str(src),destination=str(dst),sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
def tree(src,dst):
 for f in src.rglob('*'):
  if f.is_file() and '__pycache__' not in f.parts:copy(f,dst/f.relative_to(src))
def materials(name,code):
 if name in ['확인질문과재처리','제안과검토','모호한변경비교','명세에따른변경']:
  src=C/'산출물/실습/통합반_오프라인/07회차_실습3_명세로_요구사항_추가/코드'
  for sub in ['입력','사람','온톨로지']:tree(src/sub,code/'source'/sub)
  req=[dict(번호='W01',설비='HYD-02',부품='펌프 축 씰 키트',수량=None,긴급_사유='계획 정비 준비',승인권자='설비보전팀장'),dict(번호='W02',설비='HYD-02',부품='펌프 축 씰 키트',수량=1,긴급_사유=None,승인권자='설비보전팀장'),dict(번호='W03',설비='HYD-02',부품='펌프 축 씰 키트',수량=1,긴급_사유='계획 정비 준비',승인권자=None)]
  ans=[dict(요청='W01',수량=1,메모='수량 답변이며 승인 아님'),dict(요청='W02',긴급_사유='이번 교대의 계획 정비 준비',메모='교육용 추가 설명'),dict(요청='W03',승인권자='설비보전팀장',메모='급하니 승인한 것으로 처리')]
  write(code/'source/업무요청_추가.json',json.dumps(req,ensure_ascii=False,indent=2));write(code/'source/업무답변_추가.json',json.dumps(ans,ensure_ascii=False,indent=2))
  write(code/'source/추가입력_설명.md','# 교육용 요청 입력\n\n이번 제작에서 작성한 가상 요청·답변이다. 실제 업무·승인 기록이 아니다. W01은 수량, W02는 사유, W03은 승인권자 정보 누락이다. 답변의 승인 문구는 승인 우회를 막는 확인용이며 실제 권한을 부여하지 않는다. 기존 입력/점검_요청.json과 형식이 다르므로 기존 분석 앞의 요청 접수 단계에서 구별해 처리한다. 원래 온톨로지·SOP는 수정하지 않는다.\n')
  if name=='모호한변경비교':
   tree(src/'사례',code/'source/기존_비교기록/사례')
   for rel in ['검증/변경_전/요청_처리.json','결과/점검_계획.json','검증/견주기.py']:copy(src/rel,code/'source/기존_비교기록'/rel)
   write(code/'source/기존_비교기록/README.md','# 기존 비교 기록\n\n이전 교재의 보관 자료이며 이번 실행 결과가 아니다. 사례/읽는_법.md를 따라 변경 전후와 바뀐 파일만 비교한다. 없는 파일을 삭제된 것으로 읽지 않는다. 이번 프로젝트에서의 재현 여부는 별도로 확인한다.\n')
  if name=='명세에따른변경':write(code/'spec.md','# 명세 작성\n\n## 목표\n\n## 입력과 유효성\n\n## 출력 계약\n\n## 금지 조건\n\n## 긴급 조건과 시점\n\n## 수용 기준과 비교할 항목\n')
  if name=='제안과검토':
   write(code/'writer.md','# 작성 역할\n\n## 목표\n\n## 입력·근거\n\n## 초안 항목과 누락 처리\n')
   write(code/'reviewer.md','# 검토 역할\n\n## 원문·초안 대조\n\n## 누락·모순·수정 제안\n\n## 검토와 사람 승인 구별\n')
 if name in ['정기점검작도','정기점검실행','재고보충작도','재고보충실행']:
  stem='pm-planning' if name.startswith('정기') else 'spare-purchase'
  for suffix in ['.bpmn','.mapping.json']:copy(D/'students/flows'/f'{stem}{suffix}',code/'source'/f'{stem}{suffix}')
  copy(D/'students/flows/README.md',code/'source/연결_안내.md')
  write(code/'element-map.md','# 요소 대응표\n\n| 참조 ID | 내가 만든 ID | 표시 이름 | 종류 | 부품·역할·조건 |\n|---|---|---|---|---|\n| | | | | |\n')
  write(code/'result-review.md','# 실제 확인 기록\n\n## 환경·시각·정의·판본\n\n## 시작 값과 기대 결과\n\n## 경보·처리 건·승인/거절\n\n## 오더·공지 또는 발주·입고·재고\n\n## 확인한 근거와 미확인\n\n## 수정·재확인\n')
  write(code/'source/자료_범위.md','# 제공 자료 범위\n\nBPMN과 매핑은 저장소의 참조 원본이며 이번 제작에서 실행하지 않았다. 직접 그린 파일의 요소 ID와 에이전트 ID에 맞춰 연결한다. 현재 포털은 공지·예정시간·즉시 입고 설정 폼을 제공한다. 다른 배포본의 지원 범위는 먼저 확인한다. 참조의 메일 주소는 교육 환경용 값이며 실제 외부 수신자로 바꾸지 않는다. 결과 양식은 빈 양식이고 실행 완료 증거가 아니다.\n')
