# 실제 identity 기반 가져오기 준비 완료

루트가 정식API로 만든 `agent:u-24c67f1e`와 `회의 주관자`(`role:google-meeting-organizer`)를 실제 refreshed GET catalog에서 확인했다. 모델은 빈 설정으로 실행기 기본 상속이며 개발용 Sol6.1 선택과 다르다. GPU 실제 접속/실행을 확인한 것은 아니다. agent tools는없고 역할members도없다.

`prepared/flow.bpmn`, `prepared/mapping.json`, `prepared/preconditions.json`을 기존helper로 새로 생성했다. `prepared-bundle-proof.json`은3파일bytes/SHA·원본recursiveSHA불변·실제catalog를쓴production importer check의ok=true/문제0을 남긴다. unknownagent 변경은거절했고 같은출력폴더 재실행도거절했다. 원래7문제/identitymissing2 negative증거는초기시점기록으로유지한다. 전체27개시험은다시실행하지않았다.

포털에서 사용할 준비 동선은 흐름→가져오기에서prepared/flow.bpmn선택→prepared/mapping.json의부품/역할/입력설정을적용→검사다. 현재우리가라이브POST/흐름등록을한것은아니다. 사본이명시한Google서버이름은`google-meeting-calendar`/`google-meeting-drive`이며아직실제미등록이다. 구조검사는외부MCP연결검사/Google권한/업무값진실성을보증하지않는다.

실행전에실제서버등록/읽기도구체크와agent연결,실제주관자회원배정,동일요청의실제typed시작값/calendar/참석자/문서/회의실이필요하다. 이를준비값이나임의수락으로채우지않는다. 생성된preconditions의registration_verified/google_read_verified/execution_ready는모두false다. mapping에사용자idempotency_key를넣지않고실제runtimecall_effect가주입한다. 일정쓰기와실제초대는주관자승인뒤systemtask에서만가능하다.

복사본생성에사용한명령과offlinecheck전체결과는proof에남겼다. 이미존재하는prepared폴더는덮지않으므로사용자가재실행할필요가없다. 아직Google조회/초대/응답확인/K3완료를주장하지않는다.
