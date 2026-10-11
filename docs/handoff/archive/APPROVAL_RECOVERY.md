# A025 승인 저장과 외부 실행 복구 설계

2026-10-04 08:12 KST. **구현·배포 및 단계 검증 완료, 새 실제 Codex 전체 경로 검사 중이다.** 단위348, 실제Pg/SQLite/업무HTTP4/4, Pg기존복구11/11, 레거시다리 실제설비36/36을 확인했다. 포털 직접클릭은 미검수다. 아래 첫 관찰은 수정 전 반례이며 현행 구현 상태와 구분한다.

## 확인한 문제

`InstanceRuntime.select` → `instance_mode._hooks.approve_decision`은 SQLite book을 먼저 APPROVED로 바꾸고, 이후 PgRepo에 인스턴스·작업을 저장한다. 뒤의 SQL 저장이 실패하면 사람 작업은 IN_PROGRESS, book은 APPROVED여서 재선택이 막힌다. 외부 구매 요청도 SQL 트랜잭션 안에서 수행한다. `approval-atomicity-observation.json`과 `a025-red.xml/log`는 MemoryRepo/실제 결정 규칙/가짜 외부 IO 재현이다. 새로운 검사 7개 중 일부는 아직 없는 복구 인터페이스를 수용 조건으로 요구한다. 실제 PostgreSQL/SQLite 강제중단 검증을 대체하지 않는다.

## 적용한 계약

1. 승인 검증은 결정의 복사본에서 수행한다. 이 시점에는 book의 승인 상태·업무 시스템·PLC를 변경하지 않는다. A027 현재조건 평가 감사는 승인 접수와 구분해 남긴다. 인스턴스의 decision_id, asset, incident와 결정의 소속을 대조한다.
2. 승인한 결정/조치/입력의 스냅샷과 사람 작업 SUBMITTED를 **같은 PostgreSQL 트랜잭션**에 저장한다. `process_approval_outbox`는 작업당 한 승인과 tenant/decision당 한 소유자를 보장한다. 기존 PgRepo 부모→자식 잠금 순서를 유지한다.
3. 커밋 뒤 전달자는 스냅샷을 book에 반영하고 승인 직후 필요한 업무 조치를 수행한다. 모든 조치는 승인 시 저장한 입력과 같은 멱등 키를 사용한다. 후속 PLC/작업으로 넘어가는 것은 전달 완료 이후다.
4. 커밋 뒤 전달 전에 종료되면 PENDING 기록에서 다시 시작한다. 외부 실행 뒤 응답을 잃으면 같은 입력으로 재조회/재실행해 같은 참조를 받는다. 멱등성을 제공하지 않는 외부 실행을 자동 재시도 대상으로 확대하지 않는다.
5. 알려진 실패는 FAILED로 남기고 에러/시도/재요청자를 표시한다. 사용자가 복구를 요청하면 **이미 승인한 같은 내용**을 재전달한다. 실패를 DONE으로 바꾸거나 새 공급업체·값을 대신 선택하지 않는다. 중복 재시도와 다른 tenant 요청을 거절한다.
6. API/포털에는 승인 접수, 전달 중, 전달 실패, 전달 완료를 구분한다. 기존 legacy 결정 승인 API로 인스턴스 소유 결정을 우회할 수 없게 한다.

## 별도로 남는 경계

이 승인 전달 기록은 모든 Neo4j 투영/감사 알림을 위한 범용 outbox가 아니다. 현재 PLC/업무조건 재검증은 A027 CURRENT_APPROVAL.md의 범위에서 연결·검증했다. 변경된 판단의 재작업, 지연 중 TRIP과 복합 경보 처리, 일반 엔진 claim의 빠른 복구는 별도 후속이다. Incident의 재시작은 현재처럼 불확실한 진행 상태를 사람 검토로 돌린다. 분산 시스템 전체 exactly-once를 주장하지 않는다.

## 반례와 검증 범위

- 승인 뒤 인스턴스 저장 실패: book/작업/전달 기록 모두 이전 상태.
- SQL 커밋 뒤 전달 유실: 새 runtime이 PENDING을 회수해 한 번 진행.
- SQLite 저장 실패: 승인 의도는 남고 PLC는 미발행, 실패 사유 표시 후 재개.
- 업무 시스템 적용 뒤 응답 유실: 같은 멱등 요청으로 같은 PR 참조, 추가 PR 없음.
- 동시 재전달/다른 tenant/다른 인스턴스의 결정: 중복 실행·소유권 침범 없음.
- 승인 뒤 메모리 카드 수정: 저장된 승인 스냅샷의 입력만 사용.
- 실제 PgRepo+SQLite+HTTP enterprise에서 실패 주입 및 재시작, 실제 HYD 경로 재검증.

## 참고 범위

HYD `Store.save/restore`, `decisions.approve`, `instances.select`, `main.exec_skill`, `entsim.state.execute`를 읽었다. 기존 enterprise는 decision/skill과 입력 fingerprint로 멱등 재요청을 처리한다. process-gpt-completion의 현지 `polling_service/*.py`에서 outbox/idempotency 검색으로 이 승인 전달 패턴을 찾지는 못했다. 이 제한된 검색을 제품 전체에 해당 기능이 없다는 근거로 쓰지 않는다. 이번 구조는 HYD의 PostgreSQL/SQLite/HTTP 경계에서 확인한 결함을 해결하기 위한 설계다.

08:12 구현: `approval_store.py`, `approval_delivery.py`, `approval_hooks.py`를 기존runtime/Repo에 연결했다. migration00005 적용/등록 SHA256 `0fe75b52b3099d5aec9c1569df02c30d9379cfb31d1b0b89f59ff8041201bf6c`. 사람 응답 기한은 승인 접수와 함께 취소하고, FAILED 전달은 역할 검사 후 같은 내용으로만 재시도한다. 인스턴스 소유 Incident/결정은 legacy 승인·거부·decide API로 우회할 수 없다(삭제된 인스턴스 포함). SQL 오류를 주입하기 전 검사11개는 실패했고 수정후 API 포함14개·전체348이 통과했다. 첫 구현검사의 now_iso 인자 오류도 수정 전 로그로 남겼다.

`approval-delivery-pg/report.json`: 실제Pg+SQLite+HTTP업무4/4. 별도Python이 실제PR저장후 `os._exit(73)`로 종료했고, PostgreSQL전달상태는PENDING/SQLite승인정보는보존됐다. 새Runtime/SQLite재개로 PR-1003-17EC 한건·같은참조·한번의후속명령을확인했다. PLC/graph효과는이검사에서대역이며실제PLC장애시험이아니다. 8개연결동시전달은시도1회/후속명령1회, SQLite실패는PLC미진행/하위역할403/상위역할재개다. 정확한fixture tenant/decision만정리해instances/events/approvals0을확인했다.

`a025-legacy-scenario.log`: 배포컨테이너/실제PLC경로36/36 exit0. e8e0dff5-fa85-4d9b-8485-b8b78acc98f6/INC-1003-01-8800/CMD-1003-0001-6734/WO-1003-0CC5, 승인DELIVERED/attempts1을별도API조회로보존했다. `a025-codex-scenario.log`의2×/bridge off 실제Codex 실행은08:31에38/38 exit0으로끝났다. 승인DELIVERED1회, 네작업269초, MCP20시작/20종료, 재관측601초후51.49/CLEARtrue, 실제WO-1003-4CBB와ev:closed를확인했다. raw명시오류0/4세션을보존했다. 다만추가대조로A028 Incident임시WO/실제CMMS불일치를발견했으므로38검사를전체업무상태정합성완료로확대하지않는다. worker/자식0·20×/legacy·3설비RUN복구완료다. 교재13장에승인접수/전달실패/전달완료/설비회복의차이를반영했고1280/390렌더직접확인·넘침없음·check_book0문제다.

### A035 실패 승인 폐기 — 실제 연결·검증, 일반 재작업은 미완료

승인 snapshot/error/history를 보존한 `DISCARDED`와 성공 완료와 구분되는 인스턴스 `CANCELLED`를 migration00008에 추가했다. 폐기 미리보기/실행은 동일 인스턴스 잠금에서 tenant·원래 승인 역할·FAILED/SUBMITTED·다른 승인/서비스 상태를 확인한다. 종료 사건이라도 명령/작업지시/기업 실행 또는 불명확한 기록이 있으면 거절한다. 요청자/역할/사유/요청 ID/효과 조회를 이력과 PG 이벤트로 함께 저장한다. 같은 요청은 같은 결과, 다른 요청은 충돌이며 폐기 후 재전달은 불가하다. 이전 DONE 작업과 원래 Incident/decision은 덮지 않는다. 이 로컬 역할 입력을 운영 신원 인증 구현으로 설명하지 않는다.

효과 조회에 최근300건 거래 목록을 쓰면 오래된 거래를 놓칠 수 있어 enterprise API에 결정 ID별 전체 원장 조회를 연결했다. PG는 decision_id 조건을 쓰고 목록 한도를 적용하지 않으며, 메모리 backend는 영속 멱등 원장을 읽는다. 조회 오류/잘못된 응답은 빈 결과로 바꾸지 않는다. 실제 기존 효과를 보상하는 기능은 아직 추가하지 않았고 해당 사례는 명시 보류한다.

신규검사 최초10실패→관련42passed→전체580passed/경고2. `a035-discard-red/unit/full` 로그/XML. 실제 PG/SQLite/기업HTTP **9/9**에서 마지막 쓰기 실패 rollback, 네 dispatcher 동시 요청 한 번 반영, 저장소 재개/멱등 응답과 명령0을 확인했다(`a035-discard-pg/`). 이 별도 tenant의 종료 사건/PLC/그래프는 명시 시험 대역이며 실제 HYD 실행으로 확대하지 않는다. fixture tenant와 원문은 보존했다.

가동 enterprise/process를 배포하고 과거 실제 실패 인스턴스 d6a2392c…를 포털에서 선택했다. 담당자/역할/사유 누락 안내→생산관리자 조회→기업 원장0건/종료 사건/남은5작업 확인→명시 폐기를 실제 클릭했다. 사전API **4/4**, 사후API **8/8**: 원래 승인·오류·Incident 원문 불변, CANCELLED/DISCARDED, 남은 작업 종료, 같은 요청 replay, 재전달409, 폐기 이벤트1건, Neo4j 취소/작업 상태 일치. `a035-discard-live/`에 전후와 실제 화면을 보존했다. 그래프에는 기존 사건 원천 누락 경고 `incident source not projected: INC-1004-07-b30f`가 남아 있어 전체 그래프 정합 완료는 아니다.

포털 폐기 상태의 실제 데스크톱/390 화면을 직접 확인했고 390 가로 넘침은 false였다. 앞 element 캡처는 고정 헤더에 일부 가려져 viewport 캡처 screenshot-1791101939468/9811을 최종 화면 근거로 쓴다. 브라우저 종료 확인. 교재13 `approval-discard-contract`에 필요성·원장 전체 조회·담당자 판단·동작과 재작업의 구분을 반영했다. 구조0문제, 변경절1280/390 렌더 직접확인/넘침없음(`a035-book-check`, `book-render/a035-*`). 전체 학생 리허설은 아니다.

process 실제 restart 뒤에도 CANCELLED/DISCARDED가 유지됐고 health ok,20배속/instance/legacy,PowerShell 워커/검사 프로세스0,개인 config SHA 불변이다(`a035-restart-final.json`). 최초 build 명령은 PowerShell stderr 취급으로 NativeCommandError/종료1이었지만 로그에는 두 이미지 Built가 있었고 그 이미지의 실제 recreate/API/재시작으로 배포를 확인했다. 실패 출력은 지우지 않았다.

다음은 REWORK 계약의 활성 사건/새 일반 정의에서 새 작업 UUID·세대·시작 입력/출력 출처·변경 원천 조회·새 판단/승인으로 이어가는 구현이다. 이번 명시 취소 기능을 일반 재작업 완료로 축소하지 않는다. 새 A033 이후 Codex 전체 실행은 기존 도구 정책 차단으로 미검증이며 우회 시도하지 않았다. 일반 문서 AI 추출·전체 그래프 outbox·전체 강의 검수도 남는다.
