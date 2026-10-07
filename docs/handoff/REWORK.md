# 재작업 — 새 판단과 실패 승인 폐기 (A035~A042)

2026-10-04. **실패 승인 폐기/종료 인스턴스 정리는 실제 검증했다. A036에서 새 인스턴스의 시작 입력/변수 출처를 실제 연결했다. A038에서 일반 정의의 새 세대·접수/복구·출처 재구성을 실제 검증했다. A040에서 효과 없는 활성 사건의 승인 폐기/새 세대 판단을 실제PG13/13·가동HTTP/MCP/그래프18/18로 검증했다. 새 세대 Codex→승인→PLC 전체와 효과 보상·의존 작업 스케줄링은 남아 있다.** A033 원천 접수 복구를 완료 태스크 재작업으로 해석하지 않는다.

## 왜 필요한가

회의의 규칙·현재 업무 데이터·대안 판단과 사용자의 시나리오 변경 요구는 처음 받은 정답만 순서대로 실행하는 것으로 충족되지 않는다. 이미 만들어진 판단이 현재 조건에서 거절되면, 사람이 그 이유와 영향 범위를 보고 새 원천 조회·진단·대안을 요청할 수 있어야 한다. 이전 판단·승인·효과는 이력으로 남는다. 같은 승인 재전달과 새 판단은 서로 다른 작업이다.

근거는 GOAL 현재 인수조건3~5, AUDIT R04/R09~R11, CURRENT_APPROVAL의 미결2다. 회의가 특정 재작업 API나 모든 BPMN 보상을 직접 지정했다고 주장하지 않는다.

## A035 최초 조사 당시 막힌 사례 — 현재 결과는 아래 후속 기록

`.evidence/reaudit/a035-rework-baseline/`은 읽기만 수행한 현재 API·PG 스냅샷이다.

- instance `anomaly_response.d6a2392c-f5b2-4772-9593-b7b104c8a493`는 RUNNING.
- 승인 작업 `6e50dcef-082b-48eb-a243-2d9b8ce82448`은 승인 전달 FAILED, 1시도. 사유는 현재 TS1 예측 악화 또는 미확인으로 새 검토 필요.
- Incident `INC-1004-07-b30f`는 이미 RESOLVED_WITHOUT_ACTION, cmdId 없음. 이 사실만으로 모든 기업 시스템 효과가 없다고 증명한 것은 아니다.
- 현재 OpenAPI에는 approval-retry/work-order-retry/source-events retry가 있고 일반 rework/discard는 없다. 기존 승인 재시도는 동일 불변 snapshot을 재전달하므로 새 판단 생성 경로가 아니다.

이 사건을 다시 AWAITING_APPROVAL로 강제 변경해 시험을 통과시키지 않는다. 원천 CLEAR/종료와 실패 승인/남은 인스턴스의 명시 정리 경로부터 필요하다. 활성 사건의 새 판단 재작업은 별도 실제 사례로 검증한다.

## ProcessGPT 원본과 HYD 차이

completion 고정 HEAD `b272c9ab458f3ca3e18fe286e4e770d291b99e89`, `process_engine.py`791~1040을 다시 읽었다. 실제 HEAD/파일 변경 상태/SHA/열람 범위는 위 baseline의 reference.json과 발췌본에 있다. 원본 서비스 실행 증거는 아니다.

- 818~848: 새 UUID의 workitem, output 초기화, rework_count 증가.
- 850 이후: 고정 정의의 inputData 참조 또는 후행 활동을 찾아 완료 작업을 선택.
- rework endpoint: 선택한 활동마다 새 행과 보상 계획을 만들며 원래 행을 그대로 초기화하지 않는다.
- 앞서 읽은 compensation_handler/compensation 본문과 SHA는 `a031-reference-review/`다. 외부 효과별 역순 처리는 참고하되 SQL 역변환/파일 삭제를 PLC 효과 취소에 대입하지 않는다.

A035 최초 조사 당시 HYD의 engine은 반복 진입 시 새 작업 행을 만들 수 있었지만 명시 재작업 API/거래/승인 폐기 계약은 없었다. `_by_activity`와 timeline은 start_date로 최신 작업을 정했다. 이후 A038에서 명시 세대·접수 receipt·새 UUID/유효 선행 참조를 연결했다. 최초 발견과 후속 구현/실측 범위를 구분한다.

A035 최초 조사 시 variables_data만 실행 중 누적 결과였고 start_definition은 시작 입력의 별도 불변 snapshot을 저장하지 않았다. A036 후속은 아래를 따른다. 일부 결과만 삭제하고 나머지를 새 입력으로 간주하면 오래된 진단/선택/commands를 재사용할 수 있다. 시작 입력·출력 소유 작업·재작업 세대의 출처부터 보존한다.

## 구현할 계약과 순서

1. **사람이 영향 범위를 먼저 본다.** 서버가 고정 정의의 제어 흐름, input/output 의존성, 타이머와 실행 중 작업으로 재작업 범위를 계산한다. 클라이언트가 보낸 활동 목록을 그대로 신뢰하지 않는다. 시작 작업·사유·담당자·역할, 이전/새 작업 관계, 무효가 되는 변수, 기존 승인과 실제 효과를 반환한다. 미리보기는 상태를 변경하지 않는다.
2. **이전 결과를 보존하는 세대를 만든다.** 재작업 요청 자체에 UUID/멱등 키와 관측한 세대·작업 ID를 고정한다. 같은 인스턴스 전이 잠금에서 현재 상태를 재검사하고, 새 작업 UUID·rework_count와 불변 이전 행/출력/이벤트를 연결한다. 이전 실행 중 작업과 타이머를 취소·fence하여 늦은 워커 결과/승인이 새 세대에 들어오지 못하게 한다. 동시 요청 하나만 반영하고 재전달은 같은 결과를 돌려준다.
3. **새 입력의 출처를 재구성한다.** 새 인스턴스는 불변 시작 입력과 변수 생산 작업을 저장한다. 영향받지 않은 유효 선행 결과만 재사용하며, 무효화된 결과·approval/commands/chosen_option은 가져오지 않는다. 기존 인스턴스는 실제 원천/저장 작업/승인에서 복원 가능한 범위를 명시하고, 출처가 모호한 변수를 추측으로 채우지 않는다. 정의 판본은 유지한다. 정의 변경은 재작업과 별도 이행 계약이다.
4. **승인 폐기와 효과를 처리한다.** FAILED 승인 snapshot/history를 지우거나 PENDING으로 덮지 않고 별도 폐기 상태·요청자·사유·대체 요청을 남긴다. PENDING/DELIVERED/동시 전달은 같은 잠금에서 구분한다. cmdId가 없다는 이유만으로 기업 효과도 없다고 판단하지 않는다. 기업 실행 receipt/결정 executions/서비스 상태를 대조한다. 효과가 있거나 결과가 불명확하면 실제 보상 계약/확인 작업을 거쳐야 하며, 물리 명령을 자동 역명령으로 보상하지 않는다. 종료 사건의 남은 실패 인스턴스는 명시 종료 경로로 정리하고 종료를 정상 회복이나 새 제어 승인으로 쓰지 않는다.
5. **새 실행을 동일 경로에 연결한다.** 재작업은 실제 worker claim→Codex/MCP→새 decision→새 human selection/review→새 approval 경로로 진행한다. 선택 화면만 다시 열거나 기존 decision_id를 복사하는 것으로 대체하지 않는다. 포털은 과거/현재 세대·폐기 승인·효과 확인 사유를 구분하고 Execution 그래프는 workitem UUID별 이력을 유지한다. 시스템 사용 문서는 변경 이유/무효 범위/추가 승인 필요성을 설명한다. 교재 제작은 현재 범위 밖이다.

이 순서는 부분 기능을 최종 범위로 축소하기 위한 것이 아니다. 각 단계는 실제 경로 연결 전후를 기록하고 최종 판정은 아래 전체 수용 기준을 따른다.

## 필요한 증거

| 상황 | 확인할 결과 |
|---|---|
| 실제 잔여 FAILED 승인 + 종료 Incident | 효과 조회 근거와 명시 폐기/종료, 원문 보존, 재전달 차단, 새 PLC 명령0 |
| 활성 사건의 업무조건/지식 변경 | 새 원천 조회와 진단 작업, 새 판단 ID·사람 검토, 변경 결과와 이력 비교 |
| HYD와 다른 새 일반 정의 | 시나리오 이름 분기 없이 입력/의존성에 따라 새 작업 세대 실행 |
| 같은 요청 재전달/동시 요청 | 같은 재작업 결과 또는 명시 충돌, 새 작업 중복 없음 |
| 취소 직전 claim과 늦은 결과/승인 | 옛 세대 불변, 새 세대 출력·명령에 침투하지 않음 |
| 접수/세대 저장 전후 종료·DB 실패 | 같은 재작업 receipt로 복구, 부분 세대/이중 효과 없음 |
| 기업 효과 완료/불명확 + 물리 명령 발행 | 실제 효과 계약에 따른 확인/보상, 허위 무효화·자동 역제어 없음 |
| 타이머·분기·같은 시각 작업 행 | 최신 세대 선택과 유효 선행 참조가 일관됨 |
| UI·교재 | 원천 API 상태와 클릭 동선 대조, 변경 부분 렌더, 학생 판단/실행 검증 구분 |

Codex 도구 차단은 이 설계·독립 구현을 막지 않지만 실제 새 Codex 재작업 완주까지 통과한 것으로 세지 않는다. 전체 그래프 outbox·일반 문서 AI 추출·전체 강의 검수는 별도 미결로 유지한다.

### A035 실패 승인 폐기 — 실제 연결·검증, 일반 재작업은 미완료

승인 snapshot/error/history를 보존한 `DISCARDED`와 성공 완료와 구분되는 인스턴스 `CANCELLED`를 migration00008에 추가했다. 폐기 미리보기/실행은 동일 인스턴스 잠금에서 tenant·원래 승인 역할·FAILED/SUBMITTED·다른 승인/서비스 상태를 확인한다. 종료 사건이라도 명령/작업지시/기업 실행 또는 불명확한 기록이 있으면 거절한다. 요청자/역할/사유/요청 ID/효과 조회를 이력과 PG 이벤트로 함께 저장한다. 같은 요청은 같은 결과, 다른 요청은 충돌이며 폐기 후 재전달은 불가하다. 이전 DONE 작업과 원래 Incident/decision은 덮지 않는다. 이 로컬 역할 입력을 운영 신원 인증 구현으로 설명하지 않는다.

효과 조회에 최근300건 거래 목록을 쓰면 오래된 거래를 놓칠 수 있어 enterprise API에 결정 ID별 전체 원장 조회를 연결했다. PG는 decision_id 조건을 쓰고 목록 한도를 적용하지 않으며, 메모리 backend는 영속 멱등 원장을 읽는다. 조회 오류/잘못된 응답은 빈 결과로 바꾸지 않는다. 실제 기존 효과를 보상하는 기능은 아직 추가하지 않았고 해당 사례는 명시 보류한다.

신규검사 최초10실패→관련42passed→전체580passed/경고2. `a035-discard-red/unit/full` 로그/XML. 실제 PG/SQLite/기업HTTP **9/9**에서 마지막 쓰기 실패 rollback, 네 dispatcher 동시 요청 한 번 반영, 저장소 재개/멱등 응답과 명령0을 확인했다(`a035-discard-pg/`). 이 별도 tenant의 종료 사건/PLC/그래프는 명시 시험 대역이며 실제 HYD 실행으로 확대하지 않는다. fixture tenant와 원문은 보존했다.

가동 enterprise/process를 배포하고 과거 실제 실패 인스턴스 d6a2392c…를 포털에서 선택했다. 담당자/역할/사유 누락 안내→생산관리자 조회→기업 원장0건/종료 사건/남은5작업 확인→명시 폐기를 실제 클릭했다. 사전API **4/4**, 사후API **8/8**: 원래 승인·오류·Incident 원문 불변, CANCELLED/DISCARDED, 남은 작업 종료, 같은 요청 replay, 재전달409, 폐기 이벤트1건, Neo4j 취소/작업 상태 일치. `a035-discard-live/`에 전후와 실제 화면을 보존했다. 그래프에는 기존 사건 원천 누락 경고 `incident source not projected: INC-1004-07-b30f`가 남아 있어 전체 그래프 정합 완료는 아니다.

포털 폐기 상태의 실제 데스크톱/390 화면을 직접 확인했고 390 가로 넘침은 false였다. 앞 element 캡처는 고정 헤더에 일부 가려져 viewport 캡처 screenshot-1791101939468/9811을 최종 화면 근거로 쓴다. 브라우저 종료 확인. 교재13 `approval-discard-contract`에 필요성·원장 전체 조회·담당자 판단·동작과 재작업의 구분을 반영했다. 구조0문제, 변경절1280/390 렌더 직접확인/넘침없음(`a035-book-check`, `book-render/a035-*`). 전체 학생 리허설은 아니다.

process 실제 restart 뒤에도 CANCELLED/DISCARDED가 유지됐고 health ok,20배속/instance/legacy,PowerShell 워커/검사 프로세스0,개인 config SHA 불변이다(`a035-restart-final.json`). 최초 build 명령은 PowerShell stderr 취급으로 NativeCommandError/종료1이었지만 로그에는 두 이미지 Built가 있었고 그 이미지의 실제 recreate/API/재시작으로 배포를 확인했다. 실패 출력은 지우지 않았다.

다음은 REWORK 계약의 활성 사건/새 일반 정의에서 새 작업 UUID·세대·시작 입력/출력 출처·변경 원천 조회·새 판단/승인으로 이어가는 구현이다. 이번 명시 취소 기능을 일반 재작업 완료로 축소하지 않는다. 새 A033 이후 Codex 전체 실행은 기존 도구 정책 차단으로 미검증이며 우회 시도하지 않았다. 일반 문서 AI 추출·전체 그래프 outbox·전체 강의 검수도 남는다.

### A036 시작 입력 보존과 변수 생산 작업 — 실제 기반 연결

재작업에서 누적 결과를 최초 입력으로 오인하지 않도록 `initial_variables`와 `variable_sources`를 연결했다. engine.new_instance가 전달받은 시작 입력을 깊은 복사로 보존한다. 업무 결과가 변수를 만들면 실제 workitem UUID/활동/정의 판본을 출처로 저장하고, 별도 서버 갱신은 runtime으로 구분한다. migration00009의 DB trigger와 MemoryRepo는 저장된 시작 입력의 교체/제거를 거절한다. 기존 인스턴스는 NULL로 남기며 누적 결과로 시작 입력을 추측하지 않는다. 이는 현재 값의 마지막 기록 출처이며 모든 외부 사실의 진실성/전체 변수 변경 이력까지 증명하지 않는다.

신규4검사 red 재현→관련51passed→전체584passed/경고2. 최초 red 중 World.items 검사기 오타를 World.rows로 수정한 뒤 기능4실패를 다시 확인했고 두 원본을 보존했다. 이미지 build/deploy는 subprocess에서 종료0을 확인했다. 실제 새 비HYD 정의를 HTTP로 등록/시작/제출한 **8/8**에서 입력score2→업무결과7→accepted, 시작2 보존, 생산 작업9d47b2bd… 연결, 실제PG 입력 변조/제거 거절, 기존 사건 입력NULL을 확인했다. 증거 `a036-provenance-live/`, `a036-provenance-unit/full`, `a036-migration.json`이다. 인스턴스 `provenance_a463e4c7a1.92497170-0dee-42ba-b072-a159463c50ce`를 보존했다. Codex/PLC를 수행한 검사는 아니다.

포털에 시작 입력 펼쳐보기와 현재 변수의 출처를 연결했다. 실제 클릭으로 score2/현재7/작업ID를 확인하고1280·390 화면을 직접 봤다.390 가로 넘침false. 최종 화면 screenshot-1791102680901/1791102664456이며 이전 인스턴스의 원문 없음 안내는 old-input-panel.txt로 기록했다. 브라우저 종료 확인. `docs/definition-authoring.md`도 같은 계약으로 갱신했다. 전체 교재/학생 리허설 검증을 뜻하지 않는다.

현재20배속/instance/legacy·health ok,PowerShell 워커/검사 프로세스0/개인 config 불변(`a036-runtime-final.json`). 이번 단계는 일반 재작업의 입력 기반이며 재작업 요청 API/새 작업 세대/재진단/새 승인까지 구현한 것은 아니다. 다음은 고정 정의의 흐름·input/output 의존성으로 영향 범위를 계산하고, 이 snapshot/생산 작업 ID에 근거해 재사용·무효화할 변수를 결정하는 계획기와 원자적 재작업 접수/세대 전이를 연결한다. 이전 입력이 없는 인스턴스에는 임의 seed를 채우지 않는다. A035 실패승인 폐기와 효과 확인 계약을 재사용하되 활성 사건을 CANCELLED로 끝내는 것으로 재작업을 대체하지 않는다.

### A037 재작업 영향 계산 — 실제 HTTP/PG 미리보기 검증

`procsvc/rework.py`와 `GET /api/instances/{id}/rework-preview?workitem_id=...`를 연결했다. 서버는 고정 정의의 모든 후행 가지, input/output 의존성, 분기 조건의 변수, boundary timer와 실제 reference_ids를 닫힌 범위가 될 때까지 추적한다. HYD 활동 이름을 고정하지 않는다. 같은 인스턴스 잠금에서 정의·작업·변수·승인을 읽고 상태를 바꾸지 않는다. 시작 snapshot과 비영향 DONE 생산자의 실제 UUID/판본/출력값을 대조해 재사용 후보를 만들며, 무효 출력과 같은 이름의 시작 입력이 있으면 그 원문을 복원 후보로 표시한다. 출처 불명·옛 입력 NULL·종료 인스턴스·동시각 최신 행 모호·기존 승인·시작된 서비스는 사유로 남는다. `snapshot_token`은 로컬 계획 근거의 해시이며 외부 효과가 없다는 증명이나 승인 토큰이 아니다.

ProcessGPT completion의 새 UUID·입출력 참조 코드(고정 HEAD b272c9ab…/process_engine.py818~927)를 다시 읽었다. 원문 열람을 원본 서비스 실행으로 쓰지 않는다. HYD의 `rework_count`는 `retry_work_order`에서 동일 CMMS 요청 재전달에도 증가하므로 새 세대 순서로 사용하지 않았다. 새 세대 식별자/접수 receipt/옛 작업 fencing은 다음 구현이며 현재 미리보기는 `execution_available=false`다. 권한 승인, 실제 효과 조회·보상, 새 Codex 실행, UI 버튼은 이 단계에서 수행하지 않았다.

신규16passed→전체600passed/기존 경고2(`a037-planner-unit/full.log/xml`). 전이 의존성, 분기조건만 참조하는 변수, 정의 밖 실제 reference, 잘못된 생산자/판본/값/상태, tenant/인스턴스 혼입, 타이머, 승인/서비스 기록, 같은 시각 행과 읽기 전후 불변을 검사했다. build/deploy 모두 종료0(`a037-build/deploy.log`). 실제 HTTP/PG **10/10 exit0**(`a037-planner-live/`)에서 새2단계 일반 정의를 등록하고 score2→사람 결과7→다음 작업의 입력을 확인했다. 미리보기는 원래2/무효화7/취소 대상인 현재 후행 작업을 구분하고 이전 DONE 결과·이벤트·변수를 변경하지 않았다. 외부 작업 ID는409, 기존 취소 사건은 원문없음/종료 상태를 유지했다. 일반 진행으로 score8을 제출해 accepted/COMPLETED로 끝냈으며 시험용 인스턴스 `rework_plan_b8b09342f5.3a79f1f1-884f-4b2c-9350-63ede5e960c5`와 원문을 보존했다. 새 세대 재실행 증거는 아니다.

최종20배속/instance/legacy,healthz ok/PG·Kafka 연결,PowerShell 워커/검사 프로세스0,개인config SHA 불변(`a037-runtime-final.json`). 최초 상태 확인 명령은 잘못된 `/health`로404였고 실제 계약 `/healthz`로 재확인했다. 서비스 장애나 기능검사 실패로 해석하지 않는다.

다음: 재작업 receipt와 명시 generation을 저장하고 동일 인스턴스 거래에서 관측 token/작업 ID를 재검사한다. 완료된 옛 행/출력은 보존하고 살아 있는 영향 작업·타이머는 fence하며 새 UUID와 유효 선행 참조를 연결한다. 기존 승인/runtime 변수는 원래 효과·권한 계약을 다시 확인한 뒤 폐기/새 판단에 연결해야 한다. 활성 사건의 실제 Codex/MCP→새 결정→새 사람 승인까지 미완료이며 이전 도구 정책 거부 경로는 우회하지 않았다. 일반문서 AI 추출·전체 그래프 outbox·전체 강의/학생 리허설도 계속 남는다.

### A038 일반 정의의 새 작업 세대 — 실제 PG/HTTP/그래프 검증

migration00010은 인스턴스의 rework_generation/현재 요청 UUID, 작업의 generation/rework_request_id/supersedes_id, 불변 process_rework_receipt를 추가했다. 요청 UUID·미리보기 token·담당자/정의의 사람 역할/사유를 확인하고 같은 인스턴스 거래에서 재검사한다. 완료된 옛 행·출력은 보존하며 영향받는 live/TODO 행·타이머는 CANCELLED로 남기고 새 UUID와 세대를 만든다. 새 입력·query·선행 참조를 재구성하고 옛 claim/제출은 취소 상태로 차단한다. 세대 식별 정보와 요청 원문은 DB trigger로 변경을 거절한다. 같은 요청 재전달은 같은 접수 결과, 다른 내용 재사용/관측 후 상태변화는409, 정의 밖 역할은403이다. 역할 문자열 검사는 운영 신원 인증을 의미하지 않는다.

중간 작업이 같은 변수 이름을 덮어쓰는 반례도 처리했다. seed2→측정7→검토9에서 검토를 다시 하면 유효 선행 결과7을 복원한다. seed2를 항상 쓰거나 현재9를 재사용하면 잘못된다. 여러 선행 생산자가 순서상 비교되지 않으면 추측하지 않고 명시 검토로 남긴다. engine/rework planner/timeline/포털 단계는 generation 우선이며 rework_count는 기존 CMMS 동일요청 재전달 횟수와 혼동하지 않는다. 새 타이머도 요청과 세대를 이어받는다. Execution 투영은 모든 작업 UUID의 세대/이전작업/요청 ID를 보존한다.

관련24passed→전체608passed/기존경고2, 최종 그래프·타이머 보강 후 전체608 재확인(`a038-generation-first/full/final.log/xml`). migration00010 적용 및 process build/deploy 종료0(`a038-migration`, `a038-build/deploy.log`). 원문/기존 인스턴스는 삭제하지 않았다.

실제PG **10/10 exit0**(`a038-generation-pg/`): 자식 프로세스가 마지막 쓰기 후 commit 전에 os._exit(73)하면 작업/receipt/event 전체 rollback, commit 직후 os._exit(74)하면 새runtime에서 같은 결과 재개. 네 PG runtime의 replay가 한 receipt/이벤트를 반환했고 실제 old-worker RPC 결과는 거절됐다. 새 claim UUID→명시 시험 출력→다음 작업 참조→종결, SQL 세대/요청 변조 거절도 확인했다. 별도 retained tenant의 명시 시험 payload이며 Codex/PLC/그래프 대역 실행을 실제 에이전트 판단으로 쓰지 않는다.

가동HTTP/PG/Neo4j **11/11 exit0**(`a038-generation-http/`): 새3작업 정의 등록,2→7→9,검토부터 재작업입력7,옛DONE/선행작업 원문 보존,새timer/UUID,취소된옛사람제출400,잘못된역할403,요청ID다른내용409,동일요청4개 동시접수1회/같은결과,서로다른요청2개 동시접수200+409,process 실제restart뒤 전체행/receipt 동일,세대2에서11제출→COMPLETED. Neo4j에서 모든 UUID의 상태/세대/이전 작업 ID와 인스턴스 세대2를 실제 조회했다. 인스턴스 `rework_inspection_5ebe5c93.17f3683e-663e-42a9-a373-4012347095a8`은 보존됐다. 이는 Codex/활성 Incident 재작업 완주가 아니다.

포털에 현재 세대·작업별 세대/이전 작업 ID·재작업 요청 이력을 표시했다. 실제 인스턴스 탭→요청 연결 펼치기→1280×900/390×844 화면을 직접 확인했다(`screenshot-1791104272841.png`, `screenshot-1791104282402.png`).390 가로 넘침false,브라우저 종료. 첫 inline geometry 평가가 셸 quoting으로 실패해 base64 평가로 실제390/390을 다시 확인했다. 포털 요청 버튼은 아직 없으며 API로 요청한다. 예제정의/definition-authoring/교재13 `rework-generation-contract` 동기화,구조검사0문제,변경절1280/390 렌더 직접확인·넘침false(`a038-book-check`, `book-render/a038-*`). 전체 학생 리허설이 아니다.

남은 연결: 활성 Incident의 원래 효과/종료 여부, 이전 승인 snapshot과 runtime 명령 변수 무효화, 새 decision 생성·기존 decision 재사용 차단·새 사람 승인, 실제 Codex/MCP, 포털 재작업 요청 동선. 현재 Incident/기존 승인·효과가 있거나 시작점의 제어 흐름 밖 의존 활동이 필요한 계획은 명시 보류한다. 이 제한을 최종 범위 축소로 확정하지 않으며 실제 효과 확인/보상 계약과 의존 작업 스케줄러를 이어 구현한다. 전체 그래프 outbox·일반문서 AI 추출·전체 강의/리허설도 미결이다. 이전 Codex 실제 시나리오 도구 정책 거부를 우회하지 않았다.


### A039 판단 생산 작업 연결 — 가동 HTTP/PG/MCP 확인

종료된 프로세스의 Incident가 AWAITING_APPROVAL로 남은 경우 무scope 새 판단을 받는 반례를 추가 재현했다(1failed/23passed, a039-ended-red). 새 판단은409로 막고 기존 판단 ID의 중복 재전달은 원문/상태를 보존한다. 최종 전체 **632passed/기존 경고2, exit0**(a039-final-full.log/xml). process/dmn-mcp build 및 deploy 종료0이다. 최초 --profile cliagents 지정이 기본 프로필을 대체해 process 의존성 누락으로 build1이었고, .env 기본 프로필에 cliagents를 더한 환경으로 수정했다. 원래 실패 로그 a039-build.log는 보존했다.

가동 검사 a039-scope-live: MCP tools/list에 process_scope 노출, tenant/instance/generation/consumer/version/생산 작업 불일치6종409·저장없음, 실제 DMN MCP의 현재 원천 평가→새 판단 제출→정확한 scope 저장, 같은 live claim 중복 원문 보존, 다른 claim 중복 거절, legacy bridge 미개입, 실제 PG save_task_result→사람 선택 대기, 완료 claim의 늦은 새 판단 거절을 확인했다. 앞3작업은 A034 기록 출력의 명시 시험 재사용이다. 새 Codex 실행이나 활성 Incident 재작업 검증이 아니다. 실제 접수는 generation0이며 generation>0은 단위검사 범위다.

첫 검사 실행은 호스트 fastmcp 미설치로 인스턴스 생성 전에 종료1이었다. 서버 이미지의 설치된 fastmcp Client로 실제 HTTP MCP endpoint를 호출하도록 바꿨다. 다음 실행은9검사 통과 후 사람 폼에 허용되지 않는 escalated 필드를 넣어400/종료1이었다. note만 허용하는 정의 계약을 유지하고 검사기를 수정했다. 같은 보존 인스턴스에서 note만 제출한 후속 종료0으로 남은2검사를 확인했다. **합계11/11은 원래9검사+수정 후 동일 사례2검사의 합산이며 전체 검사기 단일 exit0 재실행을 뜻하지 않는다.** 실패 로그/전후 응답/수정 후 result-with-corrected-finish.json을 모두 보존했다.

instance anomaly_response.e3dfb2bb-e2ef-410d-b8c0-120e18bc9d36, Incident INC-1004-01-fe3d. 명시 시험 CLEAR가 실제 Kafka 접수 경로로 반영됐고 정의의 선택 시간초과→사람 검토 제출로 COMPLETED가 됐다. 명령/작업지시 없음, 종료 인스턴스의 새 무scope 판단409를 확인했다. 시험 원문은 삭제하지 않았다. 다음은 활성 Incident의 실제 효과·기존 승인 snapshot·새 판단/새 사람 승인을 재작업 세대에 연결하는 일이다. 의존 작업 스케줄링·전체 그래프 outbox·일반문서 AI 추출·남은 시스템 UI 검증도 남는다. 교재·시수·강의 리허설은 최신 사용자 지시로 범위 밖이다.


### A040 활성 사건의 효과 확인·승인 폐기·새 세대 판단

회의의 현재 데이터에 따른 새 판단/사람 책임 요구와 사용자 시나리오 변경 지시를 A038 새 세대 및 A039 생산 작업 계약에 연결했다. ProcessGPT completion의 새 UUID/후행 입출력 영향 계산 참고 위치는 이 문서의 고정 커밋/열람 기록과 같다. HYD 고유의 PG 승인 outbox·SQLite Incident·기업 원장을 원본 제품 기능으로 주장하지 않는다.

`rework_effects.collect`가 같은 인스턴스 전이 잠금 아래 사건 전체 원문, 관련 판단 전체와 결정별 기업 원장 전체를 조회한다. cmdId뿐 아니라 actions/ACK/작업지시/요청/local executions/기업 영수증/전달 결과·서비스 상태를 본다. 조회 실패는 빈 결과로 바꾸지 않는다. 원래 사건이 승인 대기·미해제·명시 회복 기준을 갖고 실제 효과가 없을 때, 새 decision_id를 생산하는 활동을 포함한 재작업만 접수한다. 효과와 로컬 snapshot을 함께 token에 묶고 요청 때 다시 조회한다. 외부 시스템 전체의 분산 거래/운영 신원 인증을 구현한 것은 아니다.

기존 PENDING/FAILED 승인은 원래 snapshot의 역할 권한을 재검사한 뒤 같은 PG 거래에서 DISCARDED로 남긴다. 원래 payload/error/history는 보존한다. 승인으로 생성됐다고 값과 출처가 일치하는 commands/chosen_option/approved_by/approved_role만 제거한다. SQLite의 기존 사건/카드/판단을 먼저 바꾸지 않으므로 PG rollback 뒤 외부 원문만 폐기되는 중간 상태가 없다. 새 receipt에 원래 판단/효과 snapshot을 보존한다. DELIVERED나 실제/불명확한 효과는 계속 검토 대상이며 자동 역제어하지 않는다.

새 세대의 사람 선택/미리보기는 그 세대에서 DONE 된 판단 생산 작업의 원문과 ID를 요구한다. 현재 decision_id가 없거나 옛 카드를 고르면 거절한다. 명령 발행은 같은 Incident에 남은 모든 승인 카드를 추측해 고르지 않고 현재 인스턴스의 decision_id를 사용한다. legacy bridge는 새 세대에 들어가지 않는다. 이전 guide/decision은 이력으로 남고 새 진단이 완료되면 검증된 새 guide를 저장한다.

첫 관련42passed→전체651passed/경고2. 실제PG 첫 실행은9검사 통과 뒤 두 번째 재작업이 service_effects_require_review로 실패했다. 새 세대가 시작 전 TODO 서비스를 취소하며 남긴 행정 로그를 실제 서비스 시작으로 오인했다. 불변 receipt에 원래 TODO/취소된 UUID가 있고 현재 로그도 그 요청의 취소 기록과 정확히 일치하는 경우만 제외하도록 수정했다. 임의 로그/시작됐던 서비스는 보류한다. 추가 검사 후 관련28passed, 최종 전체 **652passed/기존경고2·exit0**(`a040-final-tests.log/xml`). process build/deploy 모두0이다.

실제PG/SQLite/기업HTTP 원장 조회 **13/13 exit0**(`a040-incident-pg-retry/`): commit 전 자식 os._exit73은 승인 폐기/새 행/receipt/event 전체 rollback, commit 후 os._exit74는 새runtime에서 동일 결과 유지;4개 PG peer 같은 접수 재전달1회; 원래 승인/실패/SQLite 원문 보존;옛 worker 결과 거절;실제 엔진이 옛 decision_id 출력을 거절하고 사람 작업을 열지 않음;명시 세대2에서 새 scoped 판단→새 승인;효과 뒤 재작업 보류. PLC/현재조건/그래프는 명시 대역이며 생성된 명령1건은 fixture의 메모리 수집이다. 실제 PLC나 Codex 실행이 아니다. 첫 실패 tenant/로그도 보존했다.

가동HTTP/PG/DMN MCP/Neo4j **18/18 exit0**(`a040-incident-live/`): 명시 시험 경보로 생성한 `anomaly_response.7824da59-f681-46ba-923b-166215586da3` / `INC-1004-01-1ce6`에서 세대0 판단→실제효과 미리보기→재작업접수→세대1 MCP 현재 원천 평가/새 판단 ID→새 사람 선택 대기를 확인했다. 옛 사람 작업/옛 카드를 새 작업에 제출하면400, 새 세대의 무scope 판단409,Neo4j 세대/이전 UUID 연결을 확인했다. 실제 Kafka CLEAR→정상 선택 시간초과→사람 note 제출로 COMPLETED,명령/작업지시 없음. 앞3작업은 A034 기록 출력을 명시적으로 재사용했고 최신 판단2건은 실제 DMN MCP다. 새 Codex 또는 새 세대 승인→실제PLC 완주를 검증했다고 하지 않는다.

남은 시스템 작업: 포털 재작업 요청/영향·효과 검토 동선, 새 원천/지식 변경 후 진단부터의 실제 Codex·새 승인·PLC 연결, 효과가 있는 경우의 명시 확인/보상, 제어 흐름 밖 의존 작업 스케줄러. 일반 문서 AI 추출·전체 그래프 outbox 및 다른 회의 시스템 요구도 유지한다. 교재/강의 리허설은 C17에 따라 범위 밖이다.


### A041 포털 재작업 — 가동 브라우저와 HTTP 상태 대조

2026-10-04 19:05. `instanceRework.js`는 서버 미리보기의 영향 작업/무효화/복원/유효 선행 값과 Incident 효과/보류 사유를 표시한다. 요청자·정의 역할·변경 사유·명시 확인 후 새 세대를 요청한다. 통신/5xx로 결과가 불명확하면 최초 request_id/본문을 보존하고 입력을 잠근다. sessionStorage로 같은 탭 새로고침을 넘기며 서버 reworks receipt가 확인되면 성공 표시를 복구한다. 실제4xx 거절은 대기 요청을 지우고 재검토를 요구한다. 상태가 바뀐 미리보기는 자동 무효화한다. DISCARDED 승인의 via=rework는 인스턴스 종료와 구분하며 새 판단/별도 승인을 안내한다.

브라우저에서 기존 app.js의 `approve` 미정의 export가 hydApp 초기화를 중단하고 뒤3개 모듈에도 오류를 만드는 것을 발견했다. 실제 사용처가 없는 export만 제거하고 app/instances CSS의 캐시 키를 갱신했다. 역할 선택의 change 이벤트가 input만 구독한 상태에 반영되지 않는 문제도 실제 클릭으로 발견해 두 이벤트를 처리했다. 초기 브라우저 오류4건과 수정 뒤 같은 세션의 누적 오류 목록을 보존했으며 새 오류는 없었다.

`.evidence/reaudit/verify_a041_ui.py` **13/13 exit0**, 원시 증거는 `a041-ui/`:

- 일반 정의 `portal_rework_a29789df`의 첫 인스턴스 `2c8d7f31-8c9f-44c4-8838-0ba4469003b6`: 원래2→측정7→검토9에서 check 재작업. 전송 전 fetch 실패를 명시 주입한 뒤 새로고침/같은본문 재시도. receipt/세대 각1개, 유효 선행7 복원, 옛 DONE 전체행/최초 입력 보존. 포털 사람 폼으로 새8/확인 내용을 제출해 COMPLETED. 완료 상태 변화는 기존 미리보기와 요청 폼을 제거했다.
- 같은 정의 두 번째 인스턴스 `dc4fed69-bebb-4283-9a03-08ececbd756d`: 원래3에서 measure 재작업. 실제 POST가 접수한 뒤 응답 전달만 주입 오류로 끊었다. POST1회/receipt1개/세대1, 조회한 receipt로 대기 저장소를 비우고 성공 표시. 다음 요청에서는 실제 사람 제출200을 먼저 실행하는 동시 변경을 주입해 옛 token 요청409를 확인했다. 재시도 버튼/미리보기/대기 저장은 사라지고 제출 비활성. 남은 사람 check10/finish는 정상 API로 완료했다. 두 fixture/원문은 삭제하지 않았다.
- 화면1440×1100과390×844를 PNG로 직접 확인했다. 390의 document.scrollWidth=390, 확인 후 제출 활성. 캡처 `screenshot-1791107835741.png`, `screenshot-1791107925323.png`. 최초 selector 캡처는 화면 일부여서 전체 검증 근거로 쓰지 않는다.

실패 보존: 두 번째 응답 유실의 첫 주입기는 기존 전역 fetch 래퍼를 다시 참조해 재귀 오류를 냈다(`injection-harness-recursion-failure.json`). 실제 접수 전/세대0였으며 제품 성공으로 세지 않았다. 페이지를 다시 열고 원래 fetch를 closure에 고정한 수정 주입기로 같은 미확인 요청을 처리한 결과만 최종 증거로 썼다. CLI의 reload 직후 stale ref/잘못된 wait 인수/고정 헤더에 가려진 클릭도 성공으로 세지 않았으며 새 snapshot과 실제 스크롤 뒤 조작했다.

JS app/instances/instanceRework 구문 검사 exit0. Python/서버를 변경하지 않아 A040 전체652를 반복하지 않았다. 19:05 runtime-final.json: healthz/Kafka/Supabase ok,20배속/instance/legacy,PowerShell 워커·시나리오·검사 프로세스0,개인config SHA836330D5…불변. 전용브라우저 종료.

범위: 일반 정의의 실제 포털 접수/복구/동시 상태 변화다. Incident의 보류/이전 승인 폐기/새 판단 대기를 실제 포털에서 완주한 증거, 새 원천/지식의 Codex→새 승인→PLC 증거는 아직 아니다. 기존 효과의 확인/보상·제어 흐름 밖 의존 작업·AI문서추출·graph outbox도 계속 남는다. 강의자료/리허설은 제외한다.


### A042 MES 변경·Incident 포털 재작업·새 세대 승인/효과

2026-10-04 19:27. 회의 R04/R09/R10의 현재 업무 데이터·상충 대안·사람 선택을 가동 PG/MCP/포털/시뮬레이터에서 연결했다. 별도 정의는 기본2.1의 계약을 복사하고 UI 검토 타이머만PT24H로 명시 연장했다. 기본 정의·운영 시간배율은 바꾸지 않았다. **합성 경보, 앞3개 에이전트 작업은 A034 기록출력 재사용, 순위 작업은 실제 DMN MCP다. 새 Codex 진단이나 실제 고장 회복 증거가 아니다.**

첫 실행 `.evidence/reaudit/a042-incident-ui/`: 정의 incident_rework_ui_84e67e36/1, instance e71cc4d0-83bf-408b-8e33-fcd93f7d6d1d, INC-1004-02-0604. MES MO-0930-0412의 납기를6→36h로 변경하자 옛 카드 승인400(order_due_h)이고 동의 원장/명령이 만들어지지 않았다. 포털에서 사람 선택만 재작업하면 새 판단 필요로 보류; rank부터 명시 검토/요청하면 세대1. DMN 판단 DEC-1004-004-d0b3→DEC-1004-005-f730, 권고점수3.85→3.40/납기기여0.45→0. 옛 판단 원문 보존. 운전원 동의403,생산관리자 동의200 후 실제PLC ACK DONE. 이후 효과 있는 재작업은 포털에서 보류됐다.

첫 finish는 **exit1**이다. 합성 경보 CLEAR를 빠뜨려 실제 유온36.91℃인데도 cleared=false로 MITIGATION_FAILED/ESCALATED가 됐다. 작업지시는 없고 포털 사람 note로 ev:escalated/COMPLETED를 기록했다. 성공 종결로 바꾸지 않았다. MES/대상 설비 설정은 finally에서 복원했다. 원래의 종료150초 대기는 실패를 늦게 발견하므로 검사기에 ESCALATED 조기 탐지와 명시 --clear-after-ack를 추가했다.

두 번째 실행 `.evidence/reaudit/a042-incident-clear/`: 정의 incident_rework_ui_e81c128a/1, instance ecdd457e-b23f-4ae8-ab3e-4eded37f76e8. 납기6→0h 변경, 같은 포털 재작업/실제MCP 경로에서 DEC-1004-006-6d61→DEC-1004-007-49d9. 권고가 팬100+부하80에서 **팬만100(4.02) > 팬100+부하80(4.00)**으로 바뀌었다. 운영자가 새 카드를 명시 선택했다. 최초 finish는 nullable ACK를 dict로 가정한 검사기 결함으로exit1/조기 source복원을 냈다. process는 변경된 납기를 다시 확인해 승인 전달을FAILED로 막고 명령을 내지 않았다. ACK 대기를 수정하고 정확한 source journal로0h를 재적용한 뒤 포털 **같은 승인 내용 재전달**을 실행했다. 원래 payload 동일·시도2·동의1행/DELIVERED를 확인했다.

수정 뒤 동일 두 번째 사례의 finish --clear-after-ack는 **exit0**: 실제PLC 팬100/부하90 유지/ACK DONE→같은 합성 경보의 CLEAR를 실제Kafka로 발행→재관측→실제CMMS 접수→ev:closed/COMPLETED. Neo4j에 세대1·이전 작업 연결도 조회했다. 전체를 첫 실행부터 무실패 단일 완주라고 쓰지 않는다. 새로운 물리 고장/새 Codex 전체 검증과 별개다.

화면 결함: 카드 총점에는 있던 납기·품질 기여가 세부 내역에서 빠져 있었다. enterprise.js 공용 cardHtml에7개 항목을 모두 표시하고 없는 값은0으로 만들지 않고 '미확인'으로 표시했다. 실제 새 카드의 납기+1.50/품질0.00을 DOM과1440×1100 이미지 screenshot-1791109363460.png로 직접 확인했다. 앞선 잘못된 .hscore 선택자 캡처는 카드 렌더 근거로 쓰지 않았다.

`.evidence/reaudit/verify_a042.py` 최종 **17/17 exit0**는 두 실행의 실제 원문/화면/현재API·PG/기업원장을 대조한 결과다. 위 finish 실패2건을 지우지 않는다. 첫 대조기는 UI 로딩 중 view=null 스냅샷을 잘못 가정해 실패했고, 별도 저장한 동의 전 g1-view 원문으로 수정했다. 최종 상태 확인의 inline PowerShell Python quoting 오류도 상태 변경 없이 종료했으며 실제 파일 검사기로 다시 읽었다. JS구문/해당diff공백 검사0, Python 서버 변경이 없어 A040 전체652를 반복하지 않았다. 19:27 health/Kafka/Supabase ok,20×/instance/legacy,PowerShell worker/scenario/probe0,개인config SHA836330D5…불변,전용브라우저 종료. 마지막 실제PG 납기6 및HYD-01 fan60/load90/pumpA/REMOTE_AUTO를 다시 확인했다. 다른 설비는 reset하지 않았다.

남음: 변경 원천/새 지식을 진단부터 다시 읽는 **새 Codex**·실제고장 경로, 이미FAILED 동의를 새 세대에서 폐기하는 포털 직접 검증, 효과 확인/보상 계약, 제어흐름 밖 의존 작업, 일반문서AI추출, 전체graph outbox/회복 및 요구표의 다른 미검증. A042는 현재 MES 납기 비교/기존 원인과 규칙 범위이며 모든 업무/온톨로지 변경을 일반화해 검증한 것이 아니다.


### A071 조건 재검토·경계 도달 후속

별도 흐름의 변경 조건은 실제 선행 검토 작업을 새 세대에 포함하고 정확한 생산 완료를 기다린다. 새 타이머는 새 검토 도달부터 시작하며 이전 timeout 후속의 도달을 재사용하지 않는다. API·예제·출처·보류 경계는 [현재 운영 계약](../rework-conditions.md), 실패/복구와 전체982·실제24의 근거는 HANDOFF §9 A071을 따른다. 과거 이 문서의 의존스케줄러 전체 미구현 설명은 당시 기록이다. 실제 효과 보상/시작gateway 재평가·미확인과거도달은 남는다.


### A072 실제효과 보상·확인·Incident 재개

재작업 전 기존 세대의 외부 효과를 전부 영수증으로 해결한다. 기업 역거래 4종은 보상 영수증(PENDING→DELIVERED|FAILED, 같은 request_id 재전달이 남은 항목부터 이어감), 되돌릴 수 없는 거래·PLC 명령·원장 미확인 기록은 사람 확인 영수증(RECORDED)이다. 해결되면 미리보기에 `reopen_incident`가 표시되고 새 세대 요청이 같은 거래에서 Incident를 승인 대기로 재개하며 이전 명령·ACK·작업지시는 `superseded`, 이전 승인은 DISCARDED(via rework)다. 실제 실행에서 찾은 결함(영수증 첫 응답 시각 누락, 폐기 명령의 재관측 타이머가 새 창 판정)과 수정·증거는 HANDOFF §9 A072, 운영 계약은 [effect-compensation.md](../effect-compensation.md). 세대1 에이전트 작업은 대역 워커이며 새 Codex/Claude Code 완주는 별도 미결이다.
