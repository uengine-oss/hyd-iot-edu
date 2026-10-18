# 화면에 없는 매핑 항목을 보완하는 API 계약

수업에서 제공한 포털 주소·로그인·인증 방식을 사용한다. 아래는 저장소의 요청 모델과 경로를 정적으로 대조한 절차이며 이번 제작에서 API를 호출하지 않았다. UI에서 모든 항목을 입력할 수 있으면 API는 필요하지 않다. 시스템이 이 계약과 다르면 응답을 확인하기 전 성공으로 간주하지 않는다.

1. 포털에서 내 BPMN을 가져와 정의 ID를 확인한다. API를 쓸 경우 POST /api/flows/import 본문은 xml(파일의 XML 문자열), file_name, definition_id, start_patterns 배열이다. 경보 값은 COOLER_DEGRADATION이다.
2. GET /api/flows/catalog로 현재 부품·역할·에이전트 목록을 확인한다. GET /api/flows/{id}로 같은 초안의 parsed와 mapping을 읽는다.
3. source/reference/mapping.json을 복사한 뒤 tasks·flows·timers의 키를 내 그림 ID와 맞춘다. start.kind는 alert, start.patterns는 쿨러 경보 배열이다. 에이전트는 내가 앞에서 만든 실제 ID로 바꾼다. 역할과 작업 부품은 현재 목록과 대조한다.
4. PUT /api/flows/{id}/mapping 본문을 {"mapping": 실제매핑객체}로 보내 저장한다. 파일 경로 문자열을 mapping 값으로 보내지 않는다. 반환된 check와 GET으로 다시 읽은 mapping을 확인한다.
5. POST /api/flows/{id}/check에 {"mapping": 실제매핑객체}를 보낸다. 이 요청은 검사만 하며 매핑을 저장하지 않는다. 응답 check.ok와 check.problems의 where·field·reason을 확인한다.
6. 정상 매핑으로 POST /api/flows/{id}/register를 요청한다. 반환된 definition_id·version과 deployed:false를 확인한다. 등록은 배포가 아니다. 배포는 포털 업무 프로세스에서 그 판본을 선택한다.

중괄호의 실제매핑객체는 JSON 객체로 치환할 설명용 표기다. 그대로 실행할 요청 파일이 아니다. 오류 사례는 별도 미배포 초안에서만 검사한다. 근거: it/process/procsvc/flows_api.py의 ImportReq·MappingReq와 각 경로, it/portal/www/flows.js의 설정 폼.
