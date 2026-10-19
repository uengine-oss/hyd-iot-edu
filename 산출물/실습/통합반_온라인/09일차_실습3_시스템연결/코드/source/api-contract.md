# 실행 연결 계약과 확인 순서

이 문서는 저장소 it/process/procsvc/flows_api.py와 it/portal/www/flows.js를 정적으로 대조한 수업용 절차다. 이번 제작에서 API를 호출하지 않았다. 준비된 교육 환경의 주소·인증을 사용하고 화면에서 같은 항목을 입력할 수 있으면 API를 별도로 호출할 필요가 없다.

1. POST /api/flows/import: xml은 작성한 BPMN의 XML 문자열, file_name은 파일명, definition_id는 자신의 정의 ID, start_patterns는 ["COOLER_DEGRADATION"]이다. 기존 기준 정의를 덮어쓰지 않는다.
2. GET /api/flows/catalog로 부품·역할·에이전트 목록을 확인하고 GET /api/flows/{id}로 동일 초안의 parsed와 mapping을 읽는다. {id}는 실제 정의 ID로 바꾼다.
3. 참조 mapping의 tasks·flows·timers 키를 내 요소 ID에 대응시켜 output/mapping.json을 작성한다. agent는 실제 기존 에이전트 ID, role은 준비된 승인 역할과 대조한다. start.kind는 alert, start.patterns는 위 경보 배열이다.
4. PUT /api/flows/{id}/mapping의 본문은 {"mapping": <실제 JSON 객체>}이다. 꺾쇠 표기는 설명이며 그대로 전송하지 않는다. 파일 경로 문자열로 대신하지 않는다. GET으로 저장된 매핑을 다시 읽어 작성 파일과 대조한다.
5. POST /api/flows/{id}/check에 같은 mapping 객체를 보낸다. check.ok와 check.problems의 where·field·reason을 읽고 발견한 원인을 수정해 재검사한다. 이 검사 요청 자체는 매핑을 저장하지 않는다. 억지 오류 시연을 위해 정상 부품·조건을 삭제하지 않는다.
6. POST /api/flows/{id}/register에 같은 mapping 객체를 보내거나 이미 저장된 매핑을 사용한다. 반환된 definition_id·version과 deployed:false를 기록한다. 등록과 배포는 별개다. 포털에서 판본을 선택해 배포하고 경보 경로를 다시 읽는다. 실행·권한·실제 호출 성공은 후속 실습의 기록으로 확인한다.

매핑의 제공 예: 승인 조건 approval == "승인", 회복 조건 recovered == true, 반대편은 default:true, 승인 지연 타이머 PT10M. 보고의 {work_order.ref} 등은 결과 변수 참조다. 입력 누락이나 미실행을 성공 값으로 채우지 않는다. 공용 환경은 배정된 배포 범위를 확인하며 전체 사용자 배포를 초기화하는 기능을 이 절차에 포함하지 않는다.
