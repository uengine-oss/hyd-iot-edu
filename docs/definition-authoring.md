# 정의와 폼을 변경하여 실제 실행하기

이 실습은 같은 입력이 다른 버전에서 다른 분기로 끝나고, 기존 실행의 정의·폼·그래프 참조가 유지되는지 확인한다. 샘플의 5점/10점은 구조 검증용 임의 기준이며 실제 공정 품질 기준이 아니다. 기본 설비 경보 정의와 별도의 프로세스다.

## 입력과 확인할 결과

| 버전 | 폼 | 분기 조건 | 점수 7의 결과 |
|---|---|---|---|
| 1 | score: number | score >= 5 | accepted |
| 2 | score: number, note: text | score >= 10 | rejected |

1. 포털 `http://127.0.0.1:8088` → 프로세스 인스턴스 → **프로세스 정의 등록 · 버전 선택 · 실행**을 연다.
2. `docs/examples/inspection-review-v1.json`을 파일로 읽고 등록한다. 등록만으로 실행되지는 않는다.
3. `inspection_review @ 1`을 선택하고 시작 이벤트 ID를 새 값으로 입력한다. 시작 변수는 `{}`, 경보는 비운다. 실행 버튼을 누른다.
4. 선택된 인스턴스의 폼에 점수7을 제출한다. 종료 이벤트 accepted, 변수 score7, 해당 버전의 실행 노드를 확인한다.
5. v2 파일을 등록해 새 이벤트 ID로 시작한다. 같은 점수7만 입력하면 메모 누락으로 제출이 거절된다. 메모를 채우면 rejected로 종료된다.
6. v1 실행을 다시 선택한다. 화면의 정의 버전1·점수 폼·분기 결과가 유지되어야 한다. Execution 표의 노드 ID도 v1/v2가 다르다.
7. 같은 ID/버전에서 조건만 고쳐 등록하면409, 없는 버전 조회는404, 이미 처리한 이벤트 ID 재시작은409다. 새 버전 또는 새 이벤트를 명시해야 한다.

## 작성 계약

`processDefinitionId`, `processDefinitionName`, `version`, `activities`, `events`, `gateways`, `sequences`, `roles`, `data`, `forms`를 사용한다. 폼은 `forms.<폼ID>.fields_json`에 넣고 활동의 `tool`을 `formHandler:<폼ID>`로 지정한다. 폼의 key와 활동의 outputData가 일치해야 한다. 지원 필드는 text/textarea/number/integer/boolean/select/object/array이며 required 기본값은true다. object/array는 화면에서 JSON으로 입력한다. 동적 HTML은 실행하지 않는다.

현재 공개 등록은 사람 작업(userTask/manualTask), CLI 에이전트(ProcessGPT와 같은 모양: userTask + agentMode DRAFT 또는 COMPLETE, orchestration cliagents — 생략하면 cliagents; 이전 모양 businessRuleTask + agentMode는 등록 때 이 모양으로 바뀐다), 등록된 서비스 도구, 배타 게이트웨이, 시작/종료/경계 타이머를 검사한다. 서비스 도구는 incident:command, incident:reobserve, enterprise:WO_CREATE이며 실제 연결·필요 입력이 있어야 실행된다. 반복·병렬 합류·subProcess/callActivity는 공개 경로 통합 검증 전이므로 등록을 거절한다. 모든 BPMN을 지원한다는 뜻이 아니다.

활동의 `agentConfig.permission`은 `workspace_write`(기본)·`command_exec`·`read_only`다. `read_only`는 Claude Code에서 plan 모드가 되어 MCP 도구 호출이 전부 거절되므로(14회차 1차 실패), 워커는 Claude Code일 때 `read_only`를 `workspace_write`로 바꾸고 경고 로그를 남긴다(A129). 조회만 시키려면 권한이 아니라 도구 목록(`tools`)으로 제한한다.

새 정의의 폼은 정의 원문과 함께 버전별 불변 저장된다. 기존 anomaly_response1.0은 당시 폼 snapshot이 없어 현재 form_def를 읽는 `legacy-live`로 표시한다. 기본 신규 설비 실행은 2.0으로 전환하여 6개 폼을 정의 안에 보존한다. 상급자 확인은 note를 필수로 제출하고 그 값을 실행 변수에 남긴다. 1.0 과거 폼을 자동 복원했다는 뜻은 아니다. MCP 서버 설정도 정의 원문 밖에 있으므로 폼 고정만으로 모든 실행 환경이 고정됐다고 하지 않는다.

## 실제 API

### 여러 경로의 종료

`docs/examples/independent-reviews-v1.json`은 두 검토 작업을 함께 열고 각 결과를 받는 정의다. 한 작업이 종료 지점에 도달해도 다른 작업이 IN_PROGRESS/SUBMITTED/PENDING이면 인스턴스는 RUNNING을 유지한다. 남은 작업까지 끝나면 전체 COMPLETED가 된다. 일부 경로가 끝난 상태에서 서버가 재시작돼도 남은 작업을 계속 제출할 수 있다. 이는 병렬 게이트웨이 합류나 모든 BPMN 패턴의 지원을 뜻하지 않는다.

원천 PostgreSQL의 `flow_state.end_arrivals`는 종료 지점, 생산 작업, 작업 세대를 보존한다. 재작업은 영향받은 생산 경로의 기록만 `superseded_end_arrivals`로 옮긴다. 여러 경로가 같은 종료 지점을 써도 다른 경로의 기록을 지우지 않는다. 두 결과를 동시에 제출해도 작업 결과와 종료 도달 기록은 같은 인스턴스 트랜잭션으로 저장한다.

운영 갱신에는 `20261005000014_flow_state.sql`을 먼저 적용하고 process 이미지를 배포한다. 이전 인스턴스의 빈 `flow_state`는 과거 도달 기록이 없다는 뜻이며 과거의 잘못된 완료 상태를 자동 재구성하거나 재개하지 않는다. 직접 화면 검증 여부는 HANDOFF A062를 따른다.

### 처음 실행할 때부터 특정 입력 출처를 기다리기

기존 `inputData`는 읽을 값의 목록이며 그 자체로 모든 값의 필수 준비를 뜻하지 않는다. 특정 생산 결과가 반드시 필요한 정의는 `inputBindings`에 입력 출처를 명시한다. 예를 들어 b의 `inputData: ["x"]`와 `inputBindings: {"x": {"activity": "a"}}`는 a의 이번 작업 결과 x를 기다린다. `{"seed": {"initial": true}}`는 최초 시작 입력의 seed를 사용한다. 이는 참고 제품의 inputData 필수 의미를 추정한 것이 아니라 HYD가 추가한 명시 계약이다.

`docs/examples/bound-input-review-v1.json`은 a→입력x→b→입력y→c를 사용한다. 시작하면 b는 TODO로 대기하고, a의 결과가 확정된 뒤 b를 연다. 이미 전달한 x는 작업별 입력/출처 snapshot과 워커 query에 보존한다. 다른 작업이 같은 변수명을 덮어써도 이 작업의 입력은 바뀌지 않는다. 재작업에서는 새 생산 작업의 UUID·세대로 다시 연결하고 이전 작업의 입력을 보존한다. 실제 흐름이 해당 작업에 도달해야 시작한다는 조건도 유지한다.

출처는 `activity` 또는 `initial:true` 중 하나다. 지정 활동이 해당 변수를 outputData로 선언해야 하며, 없는 생산자·자기 자신·도달 불가능한 생산자·제어흐름과 결합한 순환은 등록 단계에서 거절한다. 시작 입력이 없거나 지정 작업의 출력이 없으면 다른 출처의 현재 값으로 대신하지 않고 대기 사유를 표시한다. 시작 입력은 실행 중 덮어쓸 수 없으므로 누락이면 입력을 갖춰 새 실행을 시작한다. 0·false·null은 키가 존재하는 실제 입력값으로 보존한다. 선택되지 않은 분기의 결과를 필수로 연결하면 해당 결과가 생기지 않아 대기할 수 있으므로 정의의 흐름과 출처를 함께 검토해야 한다.

### 다른 경로의 결과를 사용하는 재작업

`docs/examples/dependency-review-v1.json`에서 a가 x를 만들고, 다른 경로의 b가 x를 읽어 y를 만들며, c가 y를 검토한다. a와 b를 완료하고 c는 열어 둔 상태에서 a부터 재작업하면 새 a만 시작한다. 이미 도달했던 b는 새 a의 완료를 기다리고, c는 새 b에서 흐름이 도달할 때까지 기다린다. 새 a의 결과가 확정되면 b의 입력과 참조 작업이 새 세대로 바뀐다. 원래 결과와 작업은 이력에 남는다.

대기 중인 TODO에 직접 제출해도400으로 거절한다. 생산 작업이 PENDING/취소이거나 필요한 출력이 없으면 소비 작업을 열지 않는다. 이때 일부 경로가 종료됐더라도 전체 실행을 완료로 표시하지 않는다. 같은 작업의 중복 제출과 이전 세대의 늦은 제출도400이다. 서버 재시작 후에도 PostgreSQL의 `flow_state.dependency_schedule`에서 정확한 생산 작업 UUID·세대·흐름 도달 상태를 복원한다. 다른 경로가 아직 해당 작업에 도달하지 않았으면 데이터가 준비됐다는 이유만으로 시작하지 않는다.

현재 이 재개 계약은 생산자가 명확한 비순환 데이터/참조 의존 경로다. 제어흐름 밖의 게이트웨이·조건·경계이벤트 재판정, 모호한 여러 생산자, 순환 의존은 미리보기에서 구체적인 보류 사유를 반환한다. 실제 외부 효과가 있는 작업의 보상은 별도 검토 대상이다. 이를 전체 BPMN 또는 모든 재작업의 지원으로 해석하지 않는다. A063 실제HTTP/PG 검증과 새Codex·직접UI 검증의 경계는 HANDOFF에 기록한다.

### 조회와 제출

- `POST /api/process/definitions` — `{ "definition": <정의 JSON> }` 등록
- `GET /api/process/definitions` — 현재 서비스 tenant의 버전 목록
- `GET /api/process/definitions/inspection_review?version=1` — 정확한 버전 원문
- `POST /api/instances/start` — `{ "definition_id":"inspection_review", "version":"1", "event_id":"inspection-001", "variables":{} }`
- `GET /api/instances/<id>` — 인스턴스와 그 실행의 정의 원문
- `GET /api/instances/<id>/rework-preview?workitem_id=<작업UUID>` — 고정 정의·변수 출처에 따른 재작업 영향 미리보기
- `POST /api/instances/<id>/rework` — 관측 token·작업UUID·새 요청UUID·담당자·역할·사유를 확인하고 새 세대 접수
- `GET /api/todolist/<id>` — 버전에 고정된 폼
- `POST /api/todolist/<id>/submit` — `{ "output":{"score":7}, "by":"검토자" }`

메시지 시작 정의는 경보 입력을 필요로 한다. 시작 변수나 일반 폼으로 서버의 Incident/승인 명령 상태를 주입할 수 없다. select_card 작업은 역할 검사를 하는 `/select` 경로로만 제출한다. API/작업 점유는 서비스 tenant로 제한하지만 로그인 사용자 인증/RLS 전체를 구현한 상태는 아니다.

## 검증 범위

새 인스턴스는 `initial_variables`에 시작 입력을 보존하고, `variables_data`에는 실행 중 값을 저장한다. 작업 결과로 바뀐 변수의 `variable_sources`에는 workitem UUID·활동·정의 판본이 남는다. 서버가 별도로 갱신한 값은 `runtime`, 시작 값은 `input`으로 구분한다. 포털의 **시작 입력과 현재 결과**에서 둘을 비교할 수 있다. 예를 들어 시작 점수2에 대해 사람 작업이7을 제출하면 원래2는 보존되고 현재7에는 제출한 작업 ID가 연결된다.

시작 입력은 DB에서도 변경/제거할 수 없다. 이전 인스턴스의 `initial_variables=null`은 별도 원문을 저장하지 않았다는 뜻이며 누적 변수로 자동 복원하지 않는다. 새 작업 세대는 포털 또는 아래 API로 접수한다. 효과 없는 활성 Incident의 새 판단·별도 승인 계약도 연결돼 있으며 실제 효과가 있는 사례의 보상은 후속 작업이다.

재작업 미리보기는 어느 후행 작업·변수·타이머가 영향을 받는지와 그 이유를 반환한다. 흐름 외에도 변수와 분기 조건의 의존성, 실제 작업 참조를 추적한다. `candidate_variables`는 검토할 재구성 후보이며, `blockers`에 원문 없음·출처 불명·승인/효과 검토 등을 표시한다. `snapshot_token`은 조회한 로컬 상태의 해시다. 외부 효과 조회나 실행 권한을 대신하지 않는다. 미리보기 자체는 상태를 바꾸지 않으며 `execution_available`이 참이어도 별도 요청과 역할·현재 상태 검사를 통과해야 실행한다.

### 완료 결과를 보존하며 다시 수행하기

예제 `docs/examples/rework-inspection-v1.json`은 측정→재검토→확인 순서다. 시작score2, 측정score7, 재검토score9를 제출하고 확인 작업은 열어 둔다. 재검토부터 다시 수행하면 최초2 대신 유효한 선행 측정값7을 입력으로 복원한다. 측정부터 다시 수행하면 시작2를 쓴다. 임의의 다른 점수를 새 결과로 제출해 비교한다. 예제의 점수는 실제 공정 품질 기준이 아니다.

미리보기 결과를 확인한 뒤 다음 필드로 재작업을 요청한다: `workitem_id`(시작 작업), `request_id`(새 UUID), `snapshot_token`(조회 결과), `by`(담당자), `role`(정의의 사람 역할 endpoint), `reason`(변경 이유). 동일 요청 UUID의 같은 내용은 저장된 결과를 돌려주고, 다른 내용은409로 거절한다. 미리보기 뒤 작업이 바뀌어도409이므로 다시 검토한다. 다른 역할은403이다. 역할 문자열은 운영 사용자 인증을 대신하지 않는다.

원래 DONE 행·출력은 보존한다. 영향받는 진행 중/예정 행은 CANCELLED로 남고 새 UUID·generation·supersedes_id로 다음 세대를 만든다. DB가 요청 원문과 세대의 식별 정보 변경을 거절한다. 기존 `rework_count`는 동일 CMMS 재전달 횟수에도 사용되므로 세대 순서는 `generation`을 따른다. 인스턴스 상세의 `reworks`에는 원래 요청과 접수 당시 결과가 있으며 포털에는 세대·이전 작업·요청 이력이 표시된다.

포털 **프로세스 인스턴스 → 대상 실행 → 작업 다시 수행**에서 시작 작업을 선택하고 **영향 범위·실행 효과 확인**을 누른다. 무효화/복원/재사용 값, 사건의 명령·기업 원장·이전 승인 처리와 보류 사유를 확인한다. 요청자·담당 역할·변경 사유를 입력하고 확인란을 선택한 뒤 요청한다. 작업 상태가 바뀌면 미리보기를 다시 확인해야 한다. 통신 오류로 결과가 불명확하면 **같은 요청 결과 다시 확인**을 사용한다. 같은 탭의 새로고침에도 미확인 요청을 보존하며, 접수 기록이 확인되면 재전송 없이 성공 표시를 복구한다. 종료된 실행에는 새 요청 폼이 나오지 않는다. 브라우저 저장소를 사용하지 못하는 환경에서는 새로고침 전 현재 페이지의 메모리에만 미확인 요청이 남는다.

Incident 재작업 미리보기는 현재 사건·관련 판단과 기업 전체 원장을 조회한다. 승인 대기·미해제·효과 없음이 확인되고 새 decision_id 생산 작업을 포함한 경우에 접수할 수 있다. PENDING/FAILED 이전 승인은 원래 역할 권한을 재검사해 이력으로 폐기하며 원문은 남긴다. 새 판단을 만들었다고 새 명령이 나가는 것은 아니다. 새 세대에서 완료된 생산 작업의 판단을 다시 사람이 검토·선택해야 한다. 미리보기 뒤 원장/작업이 바뀌면 새 token으로 다시 확인한다. 조회 실패는503 또는 명시 오류이며 빈 원장으로 취급하지 않는다.

이미 명령/작업지시/기업 효과가 있거나 결과가 불명확한 사건, DELIVERED 승인은 보상 검토가 필요하다. 제어흐름 밖 의존 작업은 위의 생산자·도달 계약을 만족하는 경우에 재개하며 조건/경계 재판정 등은 여전히 보류한다. 임의 seed나 오래된 decision_id로 보류 사유를 우회하지 않는다. 실제 검증 범위와 새 세대 Codex·직접UI 미결은 최신 HANDOFF/AUDIT를 따른다.

실제 서비스/PostgreSQL에서 등록·구/신 버전 분기·폼 변경 보존·동시 등록·tenant 조회/claim을 실행했다. 원시 결과는 `.evidence/reaudit/definition-registry-live.json`, 포털의 파일 등록/버전 선택/제출 결과는 별도 UI 증거다. 이 검사는 CLI 에이전트가 새 정의를 실제 수행했다는 증거와 구분한다. 기본 실제 설비 legacy 경로35/35 회귀와 F의 Codex 실행도 서로 별도 실행이다.


별도 실제 Codex 검사도 수행했다. `scripts/probe_registered_codex.py`는 두 버전을 등록한 뒤 업무 DB 스키마를 읽고, 모델이 작성한 SELECT를 enterprise MCP로 실행한다. 전체 HYD 설비 조회는3/multiple, HYD-01만 조회한 새 버전은1/single 및 추가 note 필드를 제출했다. 실제 실행 증거는 `.evidence/reaudit/codex-registry-df9b60d2/report.json`이다. 재실행에는 호스트 Codex 로그인·worker.main·enterprise MCP가 필요하고 조회 데이터가 달라지면 기대값도 현재 DB에서 다시 계산한다. 설비 조치 없이 정의/폼/질의 변경을 관찰하는 확장 실습이다. 전체 질의 오류수정·PromQL이나 설비2.0 네 에이전트 작업 완주 검증을 대신하지 않는다.


강사가 설명할 실행 신뢰성: 화면에 보이는 최근 목록은 실행 엔진의 전체 작업 큐가 아니다. 이 차이를 놓치면 실행 수가 늘어났을 때만 멈추는 문제가 생긴다. HYD의 브리지는 이제 해당 인스턴스만 DB에서 원자적으로 점유하고, Incident 통지도 tenant와 Incident를 먼저 검색한다. 실제 검증은14개 작업의 점유와107개 실행의 검색으로 수행했다. 학생은 단일 정상 실행과 여러 실행·재개 요청이 함께 있는 상태를 나누어 확인한다. 이 검사만으로 동시 전이와 장애 복구 전체가 검증되는 것은 아니다.


워커 중단 관찰: CLI가 조용한 상태에서도 실행 시간제한·DB 취소·점유 변경을 감시한다. 결과 저장 시에도 같은 실행 시도의 소유권을 검사하므로 취소된 작업의 늦은 출력을 정상 제출로 만들지 않는다. A020에서 실제 PostgreSQL/Windows 자식 트리와 서로 다른 정의의 실제 Codex 정상 완료를 검사했다. 추가로 실제 Codex에 DB 취소 신호를 주입해 1.027초 안에 점유 반환과 자식 MCP를 포함한 프로세스 7개 종료를 확인했다. 사용자 취소 UI·전체 인스턴스 취소·실제 질문/답변 재개와 엔진 복구는 아직 미완료다.


후속 실측(A020~A023): 기본설비2.0에서 실제Codex4작업→사람승인→PLC ACK→재관측→작업지시→종결까지 실행됐다. 검사기의 폼 id 메타데이터 비교오류로 원본35/36, 수정 후 같은폼계약과4변조검사5/5이며 전체36개재실행은아직이다. `probe_codex_sql_repair.py`에서는 옛asset_code 조회가실패한뒤 모델이현재스키마를읽어code로수정하고실제1건을반환했다. 조회범위권한과CLI이력의남은결함은 AUDIT A022/A023에명시한다. 정상결과만따라실습완료로판정하지않는다.
## 업무 SQL의 실행 계약

입력 변경 뒤 별도 분기의 검토 작업과 경계 타이머를 새 세대로 연결하는 방법은 [재작업 조건 운영 계약](rework-conditions.md)을 따른다. 새 입력이 준비되고 실제 검토가 열린 시점에 시간제한을 시작한다.

조치 순위 식의 명시 입력·계산·수정 충돌·승인 재검사와 되돌리기는 [순위 정책 운영 계약](ranking-policy.md)을 따른다. 설명문만 바꾸는 것은 실행 식 변경이 아니다.

BSC의 개별 영향 경로·원문 조건·현재 사실/후보 예측 연결과 조건 해석의 변경은 [BSC 조건 운영 계약](bsc-conditions.md)을 따른다. 검토되지 않은 자연어 조건은 미확인으로 남긴다.

현재 메타데이터/원문 주석/DDL 변경·적재·되돌리기 계약은 [업무 원천 카탈로그](enterprise-catalog.md)를 따른다. `describe_catalog`는 구조화된 실제 타입·주석·키 관계와 table/view 구분을 제공하며, `describe_schema`는 같은 원천의 인용 DDL을 제공한다.

enterprise MCP의 `query`는 ent 스키마의 단일 SELECT/CTE/집합 조회를 받는다. 실제 테이블은 ent로 한정하며 허용 함수만 실행하고 결과는 최대200행이다. `describe_schema`에서 현재 표와 열을 확인한 뒤 조회한다. 결과가 0행인 경우도 성공일 수 있다. `result:error`는 조회 실패이므로 0으로 바꾸지 않는다.

MCP는 `hyd_enterprise_reader` 계정만 사용한다. 마이그레이션 `20261004000003_enterprise_reader.sql`을 적용한 뒤 enterprise-mcp를 재빌드한다. `/healthz`의 role/read_only를 확인한다. `ENTERPRISE_READ_DSN`은 전용 계정 연결용이며 관리 계정을 넣으면 실패한다. 추가 테이블/함수는 SELECT/RLS 정책과 SQL 허용 범위를 검토해 확장한다. 이 교육 공장의 업무 조회 계약은 여러 고객의 인증/행 격리를 대신하지 않는다.
