# 원천 이벤트 접수와 재시작 복구

상태 갱신 2026-10-04 16:19 KST

A034 실제 Codex 경로는 **42/42, exit 0**이다. 네 작업 321초, MCP 시작/종료 25쌍, 명시 오류 0을 확인했고 사람 승인→PLC ACK→재관측→CMMS→종결/그래프까지 이어졌다. 원본 실패 A032 26/27은 별도 보존했다. 워커 종료 PowerShell 0과 개인 config 해시 불변도 확인했다(a034-codex/, a034-worker-stop.json).

A033은 public migration00007과 수신/처리/API를 배포했다. 전체563검사, 실제PG/SQLite+ASGI12/12, 실제Kafka·process 강제종료/재시작22/22(a033-kafka-recovery-retry/)를 확인했다. 접수 직후·claim 중·Incident만 저장된 경계를 검사했고, 중복/충돌/지연 CLEAR와 동일 사건 재연결을 확인했다. 첫 검사기의 상세조회 오류는 a033-kafka-recovery/에 보존한다.

배포 후 펌프·팬·경보 가림은20배속 legacy bridge에서 **37/37**이다(a033-pump-fan/checks.json, stdout.log). PowerShell에서 검사 프로세스와 워커가 남아 있지 않음을 확인했다. CMMS standby_ready는 원래 NULL로 복원됐다. Codex를 쓴 A034 경로와 새 A033 수신기를 쓴 이 회귀는 서로 다른 실행 증거다.

쿨러는5배속/instance/legacy에서 **42/42, exit0**(a033-cooler/)이다. 승인DELIVERED1회→CMD-1004-0001-2be1/ACK→재관측181초→CMMS WO-1004-F54F→ev:closed/그래프를 확인했다. 추가로 PG 인스턴스 저장 후 접수완료 쓰기를 막고 실제process를kill/start한 **10/10**(a033-kafka-after-instance/)도 통과했다. 같은 접수·사건·인스턴스로 복구됐고 추가PLC명령은없었다.

포털은 agent-browser 실제클릭으로 충돌3건 조회, FAILED의 담당자/이유 필수입력, 같은접수503/562재시도→HANDLED, 원문/정의/hash유지와실제triage생성을 확인했다(a033-source-ui/). 이 UI 시험의 실패는 명시 주입이며 실제DB장애가 아니다. 재시도후목록에옛실패표시가남는결함을수정하고 선택접수새로고침·모바일입력배치를 재검증했다. 390폭가로넘침없음/1280상세화면을직접봤다. 시험사건두건은원문보존후사람검토API로종결, PLC명령0. 브라우저종료확인. 세션중 errors 명령의 빈 오류 출력은 원인확인되지않았으므로 브라우저콘솔오류0이라고 주장하지않는다.

교재 정본은 D:/work/study/시스템교재/13_확장_ProcessGPT.html이다(docs/src/master_body.html 아님). source-receipt-contract 절에 접수/업무/회복구분·상태표·화면재시도·장애실험판단을추가했다. 구조검사0문제, 변경절1280/390렌더 직접확인/넘침없음(a033-book-check,book-render/a033-*). 전체교재직접검수나학생리허설완료가아니다.

최종runtime20배속/instance/legacy·health ok, PowerShell 워커/시나리오/복구검사프로세스0(a033-runtime-after-ui.json,a033-process-stop-check.json). 소스수정은문법검사와실제브라우저로검증했다. git diff --check는 기존 tests/test_guardrail.py:114, test_stability.py:157의 EOF빈줄을보고한다. 이번영향파일외기존WIP는고치지않았다.

남은 A033 경계: ACK/CLEAR 처리 중 hard kill, Kafka 접수 전 DB 실패, 새 수신기에서 실제 Codex 완주. 전체 강의 검수·일반 재작업·일반문서 AI 추출·전체 그래프 outbox 등 전체 Goal 미결은 계속 유지한다. 최신 권한은 danger-full-access/never이며 사용자 부재 중 일반 명령 승인을 요청하지 않는다. 새 결제·push·개인 설정 기존내용 변경은 별도 계약이다.

아래 설계/부분 구현 기록은 해당 단계의 근거다. 현재 consumer는 commit 후 offset 확인 경로이며 과거 auto_commit 설명은 변경 전이다.

## 현재 근거

- `common/hydcommon/kafka.py::consumer`는 기본 auto_commit=true다.
- `procsvc.main.consume`은 RAISE를 `instance_mode.on_alert_raise`로 넘긴 뒤 원천 수신 루프를 계속한다.
- `instance_mode._schedule`은 executor future를 저장하지 않는다. A032 로그에 실제 `Future exception was never retrieved`가 남았다.
- `InstanceRuntime.start_definition`은 PG event_transaction 안에서 Incident hook을 먼저 호출한다. hook의 SQLite 저장과 뒤의 PG instance/workitem 저장은 한 트랜잭션이 아니다.
- `procdb.event_transaction`/인스턴스 거래와 이벤트 ID 중복 조회는 동시 생성의 일부를 방지한다. 원천 이벤트의 접수 기록·완료 기록·재시도 큐는 아니다.
- 실제 실패: INC-1004-01-973f, LOW_PRESSURE_TRIP. SQLite 사건이 있었지만 PG 인스턴스가 없었다. `a032-failed-fixtures-before.json`을 보존한 뒤 같은 원문을 명시 재접수하여 사람 검토로 종결했다. 이 수동 복구는 자동 복구의 증거가 아니다.

## 구현 방향

1. **원문부터 내구성 있게 접수한다.** tenant·원천 topic/partition/offset·event ID·원문·hash·접수시각을 저장한다. Kafka offset은 접수 저장 뒤에만 확인한다. DB 장애 때 저장 안 된 사건을 소비 완료로 넘기지 않는다. 접수 성공과 업무 처리 완료를 분리한다.
2. **접수 당시 정의를 고정한다.** RAISE를 처리할 정의/버전/경보 기준을 기록한다. 재시작 사이 기본 정의가 바뀌어도 같은 이벤트가 다른 경로로 재시도되지 않게 한다. 같은 ID에 다른 원문이 오면 덮지 말고 충돌을 표시한다.
3. **처리 결과와 재시도를 저장한다.** pending/claimed/handled/failed, 시도 횟수·오류·재시도 시각·실제 instance/incident ID를 갖는다. 여러 처리기가 같은 이벤트를 동시에 실행하지 않게 기존 PG 잠금/claim 구조와 맞춘다. 종료된 처리기의 claim 회수도 검증한다.
4. **부분 완료를 식별자로 재연결한다.** Incident만 저장된 경우와 instance까지 저장된 경우를 구분한다. 같은 사건/동일 정의로 이어 가며 새 사건을 복제하지 않는다. 승인 outbox/이미 전달된 PLC 명령을 재실행하는 복구와 섞지 않는다.
5. **CLEAR와 ACK의 순서·유실도 다룬다.** RAISE만 내구화하고 해제/ACK는 버리는 것으로 전체 복구를 완료했다고 말하지 않는다. 일반 상태 갱신과 사건의 상태를 바꾸는 이벤트의 기록 범위, 지연/중복/순서 뒤집힘 정책을 코드 변경 전에 명시한다. 원천 상태의 최신 시각과 사건 ACK의 명령 ID를 유지한다.
6. **오류를 사람이 볼 수 있게 한다.** 재시도 횟수를 넘긴 원문/오류/현재 부분 결과를 API와 담당자 검토에서 확인하고, 명시 재접수는 같은 식별자를 사용한다. 영원히 빈 큐처럼 보이는 상태나 조용한 손실을 허용하지 않는다.

세부 저장소/스키마는 기존 PG/SQLite 계약과 실제 원본의 이벤트 처리/claim 코드를 대조한 뒤 결정한다. 두 DB의 전체 상태를 원자화했다고 설명하거나, 메모리 목록 복사를 사건 내부 모든 전이의 일관성 보장으로 설명하지 않는다. 일반 태스크 재작업보다 먼저 이번 실제 유실 경계를 닫는다.

## 필요한 실행 증거

| 중단 지점 | 재시작 후 확인 |
|---|---|
| 접수 저장 후 인스턴스 생성 전 | 원문으로 한 사건/한 인스턴스 생성 |
| Incident 저장 후 PG 거래 완료 전 | 기존 사건 재연결, 중복 없음 |
| PG 생성 완료 후 접수 완료 표시 전 | 동일 인스턴스를 찾아 완료 처리 |
| Kafka 재전달 / 같은 ID 다른 원문 | 동일 입력은 멱등, 다른 원문은 명시 충돌 |
| CLEAR 또는 해당 명령 ACK 전달 중 종료 | 관측/명령 ID 보존, 회복 성공을 추측하지 않음 |
| 여러 설비 동시 이벤트와 DB 접속 실패 | 누락/복제 없이 재시도하거나 명시 실패 상태 |
| 새 기본 정의 배포 후 재시도 | 접수 당시 정의/회복 기준 유지 |

단위 대역뿐 아니라 실제 PG·SQLite·Kafka·process 강제 종료로 검증한다. 새 Codex가 실행되지 않은 범위는 계속 구분한다.


## A033 사전 원본 대조 (아직 구현 전)

completion b272c9ab458f3ca3e18fe286e4e770d291b99e89의 process_start_api.py 전문, polling_service/polling_service.py 전문, polling_service/database.py 909~1048행을 재대조했다. 앞 두 파일은 현재 Git 수정 없음도 확인했다. 증거와 SHA/줄수는 `.evidence/reaudit/a033-reference/`이다.

start-activity API는 고정 버전의 시작 이벤트/활동을 엔진에서 계산하는 조회이며 Kafka 원문을 내구화하는 접수 큐가 아니다. polling은 저장된 SUBMITTED/PENDING 업무를 처리하고 조건부 consumer 할당·해제 및 30분 stale 회수를 사용한다. 오류 3회 뒤 DONE 처리도 원본에 있으므로 그대로 가져와 실패 성공 판정으로 쓰지 않는다. 이 열람 범위가 원본 저장소 전체의 inbox 부재를 증명하는 것은 아니다. HYD의 source receipt/offset 확인과 Incident-PG 부분완료 복구는 별도 계약/검증이 필요하다.

## A033 접수 저장 검증 (2026-10-04 14:54)

`source_inbox.py`와 migration00007은 원문과 Kafka좌표를 먼저 저장한다. 원문 hash/업무 의미 hash를 분리하여 PLC의 반복 ACK heartbeat는 중복, 결과가 바뀐 ACK는 충돌로 남긴다. 동일 이벤트에 변경된 설비/원문이 오면 첫 입력과 접수 당시 정책을 덮지 않는다. tenant별 읽기와 식별자를 분리한다. 바깥 PG 거래에 붙어 아직 commit하지 않은 상태로 접수 성공을 반환하는 호출도 거부한다.

단위12passed; 실제 PostgreSQL14/14 exit0. `scripts/probe_source_inbox.py`가 만든 독립 schema `a033_receipts_f706f0943c8b`에 증거를 남겼고 운영 public 스키마/가동 프로세스는 바꾸지 않았다. 증거 `.evidence/reaudit/a033-source-unit.xml`, `a033-receipts-live/result.json` 및 원문 rows. 8개 동시 서로 다른 offset은 한 canonical+7중복, 같은 offset 동시8개는 같은 receipt ID를 반환했다. 이 검증에는 강제종료·Kafka offset·처리 claim·물리 업무 복구가 포함되지 않는다.

다음 구현은 owner/lease/token 조건부 claim과 재시도·명시 실패, 접수 당시 정책으로 InstanceRuntime 재진입, CLEAR/ACK 지연 연결 및 최신 상태 시각 보존이다. 원문 commit 이후에만 Kafka partition offset을 확인하도록 수신루프를 바꾸고, API 경유 사건 시작도 같은 정책을 거쳐야 한다. 이전 WAITING CLEAR가 뒤의 RAISE를 막는 순서 교착과 여러 처리기의 동일 설비 동시 실행을 함께 검증한다. 재시작 확인 상태를 늦은 ACK로 자동 해제하지 않는다. 가동 연결 전에 이 처리 계약/수용조건을 구체화한다.

### 수신 경로 연결 전 추가 확인점

현재 receipt의 payload는 디코딩된 JSON 객체이며 byte 단위 Kafka 원문 보존을 증명하지 않는다. 기존 `decode_value`는 잘못된 UTF-8을 replacement 문자로 바꾼다. 실제 연결에서는 역직렬화 전 bytes와 원문 hash를 함께 보존하거나, 원문 보존의 범위를 명시적으로 좁혀야 한다. malformed 메시지를 로그만 남기고 버리는 현재 경로는 그대로 둘 수 없다.

읽은 연결 지점: main.consume은 상태 메모리 갱신 뒤 모든 Incident를 순회하고, 개별 예외를 로그에 남긴다. on_alert_raise는 future를 추적하지 않는다. InstanceRuntime.start_definition은 고정 정의의 PG event_transaction 안에서 SQLite Incident hook을 먼저 수행한다. 따라서 receipt HANDLED 조건은 함수를 예약했다는 사실이 아니라 동일 event_id/정의/Incident의 실제 저장을 재조회한 결과여야 한다. 재접수 시 start_definition의 중복 반환 None도 기존 instance를 조회하여 명시 ID로 기록해야 한다.

## A033 처리 소유권·재시도 부분 구현

claim/renew/finish/defer/fail/retry_failed를 추가했다. 짧은 tenant 스케줄링 거래로 같은 설비에 살아 있는 claim 하나만 허용하고, owner와 매 시도 UUID token·lease를 모두 대조한다. 만료는 실패 횟수에 기록하며 한도 뒤 FAILED를 유지한다. 명시 재시도는 원문·정책·이력을 유지하고 담당자/이유를 남긴다. unmatched CLEAR/ACK의 WAITING은 실패 횟수와 분리하고 뒤의 RAISE를 막지 않는다.

실제 독립 PostgreSQL28/28 exit0(a033-claims-live). 8경쟁자/여러설비, 만료 이전 소유자의 늦은완료·갱신 거절, 같은 owner의 다른token 거절, 실패한도·명시재시도·다른tenant·완료중복을 포함한다. 시험을 위해 해당 독립 schema의 lease/due만 과거로 지정했으며 실제 프로세스 강제종료 검사는 아니다. 운영 migration/consumer/runtime/API 미연결 상태다. token 검사는 DB 완료 쓰기를 막을 뿐 이미 실행 중인 외부효과를 중단시키지 않는다. 실제 연결에서 사건 식별자의 멱등성과 기존 인스턴스 잠금, 최신 상태 시각 대조가 필요하다.

## 운영 연결 코드 작성 (아직 미배포)

원본 바이트·tombstone을 보존하는 raw Kafka 수신을 추가했다. HTTP 경보는 source=http로 저장하고 Kafka 좌표를 만들지 않는다. 두 출처는 같은 업무 identity/원문으로 중복을 판정하고 첫 정책을 유지한다. plant.status는 별도 최신 상태 표에 원천 시각을 비교해 저장하며, 늦은 관측이나 시각이 잘못된 관측으로 최신 상태를 덮지 않는다. 중복 ACK heartbeat도 최신 관측은 반영하되 명령 응답 처리는 중복 실행하지 않는다.

InstanceRuntime.receive_alert는 접수 정책을 원래 정의 버전과 다시 대조하고, Incident/PG 부분 완료 또는 이미 만든 인스턴스를 실제 ID로 재연결한다. SourceDelivery는 owner/token/lease를 유지하면서 처리하고, CLEAR/ACK는 같은 인스턴스 잠금 안에서 원천 사건/명령에 연결한다. 늦은 ACK가 PROCESS_RESTART_REVIEW를 해제하지 않는다. main.consume은 원문 접수 commit 뒤 Kafka offset을 확인하며 DB 장애 동안 같은 메시지를 재시도한다. Kafka 재균형의 offset commit 실패는 이미 저장한 원문을 다시 받는 것으로 처리한다.

접수 당시 정책을 버리는 별도 시작 경로가 생기지 않도록 가이드 HTTP 접수도 같은 receipt를 기다린다. GET /api/source-events 및 /{id}, POST /{id}/retry로 원문/실패/이력과 명시 재시도를 제공한다. FAILED 외 상태를 임의 초기화하지 않으며 actor/reason을 기록한다. 이 로컬 강의 API를 운영 SSO/ACL 구현이라고 설명하지 않는다. 포털 담당자 화면 연결은 남아 있다.

검증: 19단위(a033-wire-unit), 실제PG34/34(a033-wire-live), 연결단위26(a033-delivery-unit), 실제PG/SQLite7/7(a033-delivery-live). 마지막 검사는 저장 예외/저장소 재연결/정의 변경/지연 CLEAR·ACK를 다루며 실제 Kafka/운영 HTTP/프로세스 강제종료가 아니다. ASGI API 추가 검사와 전체회귀는 실행 중이다. 운영 public migration00007 미적용, 컨테이너 미배포이므로 전체 유실 복구 완료로 세지 않는다. A034 Codex 검사 종료 뒤 migration/배포/실제 Kafka·프로세스 강제종료를 진행한다.

### A033 저장 실패와 CLEAR·ACK 완료 경계 — 실제 검증

`probe_source_persistence_failure.py` 재검사 **10/10**: 시험 경보 한 건에만 PG INSERT 예외를 주입했다. 원문이 저장되지 않은 동안 실제 Kafka process 그룹의 committed offset이 경보를 넘어가지 않았고, 오류 제거 뒤 동일 좌표·원문으로 처리됐다. health에도 실패/회복이 나타났다. CLEAR 반영 후 접수 완료 SQL이 대기 중임을 확인하고 process SIGKILL과 해당 DB 연결 종료를 수행했다. 원래 접수가 2시도로 이어졌고 사건은 ESCALATED를 유지했다. 증거 `a033-persistence-failure-retry/`. 이것은 DB 전체 접속 장애가 아닌 범위를 한정한 실제 쓰기 오류다.

첫 `a033-persistence-failure/`는 7통과 뒤 2시도를 기대한 검사 1개가 실패했다. 앱을 죽인 뒤에도 DB가 이미 받은 완료 쓰기를 끝내 1시도 HANDLED가 됐다. 원본 실패/관측값은 보존했고 시험 사건은 명시 검토로 종료했다. 앱 종료가 DB 거래 중단과 같다는 가정을 폐기했다. 재검사는 대기 중인 정확한 완료 SQL/backend를 기록하고 그 연결까지 종료한 범위를 명시한다.

`probe_source_ack_recovery.py` **9/9** 및 설정 단계4/4: 실제 HYD-03 팬 결함→legacy 에이전트→사람 승인→팬40/부하80→PLC ACK 뒤 같은 완료 경계를 끊었다. 재시작 후 같은 ACK/명령 ID를 재처리했고 PROCESS_RESTART_REVIEW를 유지했다. Kafka action.cmd에서 CMD-1004-0001-28bd는 partition0/offset43의 **1회 발행**으로 확인했다. 사람 검토→ev:escalated, CMMS 가지 CANCELLED. instance39edd9a3…, Incident INC-1004-01-32e7. `a033-ack-recovery/`에 실제 command 메시지·접수·사건·결과를 보존했다. Codex를 쓴 검사는 아니다.

범위를 한정한 DB trigger/function은 모두 제거됐고, `a033-worker-preflight.json`에서 잔여 시험 함수0/기존 워커 대상 작업0을 확인했다. 첫 실패 원문을 성공으로 덮지 않는다. 이 단계는 수신 완료 거래의 재시도를 검증하며 Kafka의 모든 장애 유형이나 모든 외부 효과의 원자성을 증명하지 않는다.

### 최신 Codex 경로 — 실행 도구 차단으로 미실행

2배속/off로 바꾸고 Codex 워커 PID1916은 실제 기동됐다. 그러나 상태조회와 `run_scenario_evidence.py --worker --fresh-review --out .evidence/reaudit/a033-codex` 시작을 포함한 명령이 실행 도구의 `blocked by policy`로 거절됐다. 구체적인 사유는 제공되지 않았다. 현재 danger-full-access/never여도 이 거절이 발생했으며 사용자 승인 요청이나 우회 실행을 하지 않았다. `a033-codex` 결과 폴더도 생성되지 않았다. A03442/42를 새 A033 Codex 성공으로 재사용하지 않는다.

켜진 워커1916과 확인된 자식23512/21896을 종료했고 PowerShell로 remainingWorkers0/remainingTree0을 확인했다(`a033-worker-stop.json`). 개인 config SHA는836330D5…불변. process/plant/detector를20배속/instance/legacy로 복원했다. 다음은 독립적인 DB 접속 실패 검사 준비, 남은 일반 재작업/문서 추출/강의 요구 대조다. 같은 차단된 Codex 시작 명령은 정책 변화나 허용 확인 없이 반복하지 않는다. 전체 Goal은 active이며 이 차단 하나가 독립 작업 전체를 막지는 않는다.

### A033 DB 연결 중단과 여러 설비의 접수 복구 — 15/15

`probe_source_connection_failure.py`를 실제 실행했다. process에만 시험 전용 TCP 중계기 DSN을 적용하고 중계기를 중지했다. 공유 PostgreSQL/Kafka는 계속 가동했다. handler에서 실제 Connection refused, receiver에서 DNS 접속 오류가 관측됐고 health ok=false였다. 세 설비의 서로 다른 경보와 동일 경보 중복 한 건이 Kafka에 발행됐으나 접수/사건은 생기지 않았으며, 두 시점의 process 그룹 committed offset은 네 원문을 넘어가지 않았다.

중계기를 다시 켜자 **process 컨테이너 재시작 없이** 세 원문 HANDLED/세 고유 인스턴스와 중복 한 건 DUPLICATE로 처리됐다. 네 Kafka 좌표가 보존된 뒤 offset이 전진했다. 세 사건은 원래 미지원 경보의 사람검토 경로로 갔으며 PLC 명령은 없었다. 명시 검토 결과까지 저장했다. 총15/15 exit0. 증거 `.evidence/reaudit/a033-connection-failure/`의 result/health-outage/offsets-outage/recovered-receipts/offsets-recovered 및 설비별 instance 원문이다.

finally에서 process의 원래 환경변수 전체가 같음을 확인하고 20배속/instance/legacy·health ok로 복원했다. 시험 label을 대조한 중계기는 제거했고 잔여0이다. PowerShell 워커/시나리오/검사 프로세스0와 개인 config SHA 불변은 `a033-connection-process-check.json`에 기록했다. 공유 DB 서버 자체의 장애·모든 네트워크 분할 유형·새 Codex 실행을 증명하지 않는다. 최신 A033 Codex 시작은 기존 정책 차단으로 계속 미검증이다.

다음은 CURRENT_APPROVAL의 완료 태스크 재작업 및 실패 승인 폐기/새 판단 경로를 ProcessGPT 원본과 대조해 설계·구현하는 것이다. 원천 접수 장애 검사만으로 전체 Goal을 완료하지 않는다.
