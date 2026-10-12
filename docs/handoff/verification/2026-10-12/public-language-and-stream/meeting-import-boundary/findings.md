# 회의 가져오기: 초안·구조검사·등록·실행 경계

결론: 현재 prepared3파일의 offline structural ok는 유효하다. Google 인증 없이 정식API로 **초안을 저장하고 구조검사**하는 것은 가능하다. 그러나 **안전한 비실행 등록**이라는 모드는 현재 제품에 없다. register응답의deployed=false는 경보 운영배포가 아니라는 뜻이며 직접시작을 차단하지 않는다. 사용자에게 연결미완료가 확실히 표시되는 disabled상태도 없어, 현재 실제등록을 추가할 이유가 없다. 이 조사에서는 라이브POST/등록/Google조회/모델/코드변경0이다.

| 우선순위 | 범위 | 가능한 사실과 제약 | 권고 |
|---|---|---|---|
|1|기존파일+offline검사|실제생성agent/역할을쓴prepared mapping과productioncheck ok; 서버인증/agent읽기도구/rolemember미완료|기존증거를사용하고반복검증안함|
|2|정식초안저장|POST/api/flows/import는DB초안쓰기다. 그후mapping PUT/구조check는가능. 초안은등록판본이없어직접시작버튼대상이아님|사용자보이는초안이필요할때만루트가별도잠금하에결정; 이번read-only작업은실행안함|
|3|판본register|구조check만통과하면없는Google서버참조도저장될수있음. deployed=false로반환하지만직접시작가능|현재추가하지않음. '연결완료/실행가능'표시금지|
|4|외부연결/실행|읽기도구선택·Googlegrant·주관자회원·실제업무입력확인필요|우리가연결환경준비; 사용자에게서버URI조사요구안함|

## 소스의 정확한 의미

- `it/process/procsvc/flows_api.py:90` import는parse→catalog→merge_mapping→`save_draft`(111행)를수행한다. ImportReq는xml/file_name/definition_id/start_patterns이며mapping은동시에받지않는다. 따라서preparedBPMN을import한뒤168행mappingPUT으로preparedmapping을적용하는2단계다. import가그자체로Google매핑/연결을설치했다고말하면안된다.
- `flows_api.py:179` check는초안이이미있어야하며요청mapping또는저장mapping으로view→`bpmn_import.check`를호출한다. check는매핑을저장하지않는다.171~176행PUT은매핑을저장한다. 현재offline진입점도동일parse/check함수다.
- `flows_api.py:189` register는구조check결과가ok면`FlowStore.register`를호출하고216행deployed=false를반환한다. optionalmapping을보내면197~199행에서먼저저장한다. 등록거절이라도mapping쓰기와동일한순수검사로취급하지않는다.
- `it/process/procsvc/bpmn_store.py:126` 등록은immutable판본을저장하고운영head prod_version은움직이지않는다(144~149행memory,155~164행PG). **deployed=false는disabled=false와다른개념**이다. 별도MCPreadiness/disabled필드는이경로에없다.
- `it/portal/www/flows.js:403` 등록판본목록은405행에서무조건'직접시작'버튼을만든다.432행폼/453행은`POST /api/instances/start`에명시definition_id/version을전달한다. '등록한판본없음'과'매핑초안있음'표시(406행)는지원하지만Google연결미완료칩이나실행잠금은이경로에없다.
- `it/process/procsvc/instance_mode.py:1023`은명시판본을`rt.start_definition`으로전달한다. `it/process/procsvc/instances.py:230`은명시version을`definition_for`로읽으며운영배포포인터를필수로확인하지않는다. 따라서미배포만으로비실행보장을할수없다.
- `it/process/procsvc/effect_parts.py:171`부터MCP설정의server/tool문자열/arguments/extract/effect형식을검사하지만실제tenantregistry/OAuth를연결검사하지않는다. `bpmn_import.check`의catalog도parts/roles/agents중심이다. 실제runtime `service_parts.py:100`의MCP호출까지가서연결/권한오류가날수있다. 나중실패가난다는것은안전한비실행등록을뜻하지않는다.

현재제품에새단계/우회/fallback을넣자는제안이아니다. 서버/역할/초안등록을모두'완료'로묶지않고,외부준비전에는파일준비상태를명확히유지하는것이현재최소안이다. root가별도초안저장을선택할수있지만실제등록을추가할근거는현재없다.

## 회의 원본의 반려·지연·ordinary end semantics

`students/_template/example_meeting/flow.bpmn:90`의4시간경계타이머는`cancelActivity=false`로주관자승인Activity_approve에붙어있다. 102~103행은지연보고→EndEvent_delay,100~101행은반려보고→EndEvent_reject다. 둘다ordinary end event이며지연가지를종료한다고프로세스전체를강제종료하는terminate end가아니다. 원본mapping38행PT4H/Activity_report_delay·reject설정은준비사본에도보존된다. 다음참석응답대기P1D(Activity_wait)는승인경계지연과별개다.

`bpmn_import.py:195`는cancelActivity를interrupting으로읽고748~751행의정의에false를유지한다. `engine.py:538`~553은non-interruptingtimer가승인작업을계속기다리게하고두번째token가지를만든다. `engine.py:596`은ordinaryend도달을flow_state.end_arrivals에기록한다.625~629행은다른liveIN_PROGRESS/SUBMITTED/PENDING이나dependencywaiting이없는경우에만인스턴스를COMPLETED로닫는다. 따라서회의지연알림이끝에닿아도주관자승인이열려있으면회의전체는자동완료되지않는다. 반려도승인결과분기뒤반려보고로끝나며기존승인지연가지를고정공장정책으로바꾸지않는다.

고정A/B/C는자기정의의타이머/에스컬레이션/보류정책을쓴다. 예로`anomaly_response_v22.json:132`~140의선택PT10M경계는cancelActivity=false가없어interrupting기본이며운전원선택을생산관리자에게넘기는정책이다. 회의PT4H비중단알림을공장3시나리오정책으로통일할근거는없다. 원본회의의반려·지연이각끝으로가는도면은그대로이며현재engine의다중경로ordinaryend규칙으로해석한다.

## 결과와 남은 작업

preparedflow의실제라이브등록0·실제Google읽기/초대0·구조offlineok를구분한다. 모델API나포털기본모델은변경하지않았다. 원본/준비파일/기존negative증거를재생성하지않았으며기존27시험도반복하지않았다. 다음구체작업은우리가Google연결준비를진행한뒤실제registry/schema/read-only도구연결·주관자실제회원배정·사용자승인을확인하는것이다. 사용자에게기술서버주소나Credential설정을조사해오라고요구하지않는다.
