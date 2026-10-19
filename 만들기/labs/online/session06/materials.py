from helpers import *
source_manifest=[]
def copy(src,dest):
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);source_manifest.append(dict(source=str(src),destination=str(dest),sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
def copytree(src,dest):
 for f in src.rglob('*'):
  if f.is_file() and '__pycache__' not in f.parts:copy(f,dest/f.relative_to(src))
def materials(name,code):
 raw=C/'산출물/실습/통합반_오프라인'
 if name=='업무도구연결호출':write(code/'connection-record.md','# 연결과 호출 기록\n\n| 서버 | 연결 방식 | 검사 시각·결과 | 허용 도구 | 입력 | 반환 행·기준 시각 | 에이전트 연결 |\n|---|---|---|---|---|---|---|\n| | | | | | | |\n')
 if name=='MCP서버조합':
  src=raw/'06회차_실습2_MCP_서버_연결/코드'
  for sub in ['서버','도구','구매팀_자료']:copytree(src/sub,code/sub)
  src=D/'산출물/실습/실전반_온라인/04일차_실습4_MCP도구연결/코드'
  for f in ['config-notes.md','설정_작성.md']:copy(src/f,code/f)
 if name=='회의록스킬작성':copytree(raw/'06회차_실습3_회의록_스킬/코드/회의록',code/'source')
 if name=='학습코치':
  write(code/'source/학습자료.md','''# 도구 호출 결과를 읽는 법

이 파일은 수업용 학습 입력이다. 실제 호출 결과나 이번 실습의 수행 기록이 아니다.

## 1. 연결 검사와 호출

연결 검사로 목록을 읽었다는 사실과 업무 입력으로 도구를 호출해 성공했다는 사실은 다르다. 도구를 호출할 때 이름과 입력 스키마를 확인하고 실제 대상과 반환 자료를 대조한다.

## 2. 값 없음과 실패

정상 조회에서 0행이면 그 조건에 맞는 행을 찾지 못한 것이다. 수량이 0이라는 뜻은 아니다. 호출 실패나 시간 초과는 값을 확인하지 못한 것이므로 0으로 바꾸어 적지 않는다.

## 3. 시각과 근거

관측 시각은 값이 관측된 때이고 조회 시각은 그 값을 가져온 때다. 두 시각이 다를 수 있다. 결과에 출처 이름이 붙어 있어도 그 자료가 결론을 뒷받침하는지 확인해야 한다.

## 4. 지침과 권한

스킬은 재사용할 수행 방법을 적은 지침이다. 스킬에 어떤 행동을 적었다는 사실만으로 실행 권한이 생기지 않는다. 도구의 연결과 권한, 입력과 결과는 따로 확인한다.
''')
  write(code/'source/출처.md','학습자료.md는 통합반6 이론 32·45~50·56~57장의 구분을 학습 입력으로 정리한 제작 자료다. 모델 출력이나 실제 실행 기록이 아니다.\n')
  write(code/'dialogue-review.md','# 대화 검토\n\n| 문항 | 확인용 답변 | 판정 | 정답·이유 | 원문 절·근거 | 다음 문항 | 수정 |\n|---|---|---|---|---|---|---|\n| | | | | | | |\n')
 if name in ['설비이상대응작도','승인조건과예외','에이전트와실행연결','사전검사와배포','이벤트와처리결과']:
  copy(D/'students/flows/cooling-emergency.bpmn',code/'source/reference/cooling-emergency.bpmn')
  copy(D/'students/flows/cooling-emergency.mapping.json',code/'source/reference/mapping.json')
  write(code/'source/reference/README.md','# 참조 흐름\n\n저장소 students/flows의 제공 참조다. 이번 제작에서 실행하지 않았다. 직접 만든 결과는 output에 저장한다. 참조 mapping의 ID를 직접 그린 BPMN 요소 ID와 대응시킨 후 사용한다. agent:cooling은 기본 예이므로 기존에 만든 에이전트의 실제 ID로 연결한다.\n')
  write(code/'element-map.md','# 요소 대응\n\n| 참조 ID | 내 그림 ID | 이름 | 레인 | 부품 | 담당·설정 |\n|---|---|---|---|---|---|\n| | | | | | |\n')
 if name=='승인조건과예외':write(code/'condition-plan.md','# 조건 계획\n\n| 내 요소 ID | 구분 | 변수·연산·값 또는 기본 | 확인 근거 |\n|---|---|---|---|\n| | 승인 분기 | | |\n| | 회복 분기 | | |\n| | 승인 지연 타이머 | | |\n')
 if name in ['에이전트와실행연결','사전검사와배포']:
  write(code/'API_연결절차.md','''# 화면에 없는 매핑 항목을 보완하는 API 계약

수업에서 제공한 포털 주소·로그인·인증 방식을 사용한다. 아래는 저장소의 요청 모델과 경로를 정적으로 대조한 절차이며 이번 제작에서 API를 호출하지 않았다. UI에서 모든 항목을 입력할 수 있으면 API는 필요하지 않다. 시스템이 이 계약과 다르면 응답을 확인하기 전 성공으로 간주하지 않는다.

1. 포털에서 내 BPMN을 가져와 정의 ID를 확인한다. API를 쓸 경우 POST /api/flows/import 본문은 xml(파일의 XML 문자열), file_name, definition_id, start_patterns 배열이다. 경보 값은 COOLER_DEGRADATION이다.
2. GET /api/flows/catalog로 현재 부품·역할·에이전트 목록을 확인한다. GET /api/flows/{id}로 같은 초안의 parsed와 mapping을 읽는다.
3. source/reference/mapping.json을 복사한 뒤 tasks·flows·timers의 키를 내 그림 ID와 맞춘다. start.kind는 alert, start.patterns는 쿨러 경보 배열이다. 에이전트는 내가 앞에서 만든 실제 ID로 바꾼다. 역할과 작업 부품은 현재 목록과 대조한다.
4. PUT /api/flows/{id}/mapping 본문을 {"mapping": 실제매핑객체}로 보내 저장한다. 파일 경로 문자열을 mapping 값으로 보내지 않는다. 반환된 check와 GET으로 다시 읽은 mapping을 확인한다.
5. POST /api/flows/{id}/check에 {"mapping": 실제매핑객체}를 보낸다. 이 요청은 검사만 하며 매핑을 저장하지 않는다. 응답 check.ok와 check.problems의 where·field·reason을 확인한다.
6. 정상 매핑으로 POST /api/flows/{id}/register를 요청한다. 반환된 definition_id·version과 deployed:false를 확인한다. 등록은 배포가 아니다. 배포는 포털 업무 프로세스에서 그 판본을 선택한다.

중괄호의 실제매핑객체는 JSON 객체로 치환할 설명용 표기다. 그대로 실행할 요청 파일이 아니다. 현재 작성한 미배포 초안에서 실제 문제만 검사·수정하며 정상 설정을 일부러 지우지 않는다. 근거: it/process/procsvc/flows_api.py의 ImportReq·MappingReq와 각 경로, it/portal/www/flows.js의 설정 폼.
''')
 if name=='사전검사와배포':write(code/'deployment-record.md','# 검사·배포 기록\n\n## 정상 초안 위치와 해시\n\n## 실제 검사 응답·확인 범위\n\n## 발견한 문제 위치·사유(없으면 없음)\n\n## 수정·저장·재검사(수정 없으면 해당 없음)\n\n## 정의 ID·등록 판본\n\n## 배포 시각·환경·경보 경로\n\n## 남은 실행 확인\n')
 if name=='이벤트와처리결과':write(code/'source/기준흐름_비교.md','# 구조 비교 자료\n\n통합반9 이론66~67의 기준 흐름 설명: 기준 흐름은 에이전트 단계 넷과 중단형 타이머, 수업 참조 흐름은 에이전트 단계 하나와 비중단형 지연 알림을 사용한다. 둘은 과거와 미래 버전이 아니다. 실제 배포 환경의 정의가 이 설명과 같은지는 수업에서 판본과 구조를 확인한다. 이번 제작의 실행 결과가 아니다.\n')
