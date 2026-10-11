# A028 실제 작업지시와 종결

2026-10-04 09:23 구현·배포 및 실제 legacy/인스턴스 검증. 새 Codex 워커 시작은 자동 승인 심사 거절로 미실행이다. 전체 Goal 완료 문서가 아니다.

## 발견한 실제 실패

A025 Codex 38검사는 통과했지만, Incident가 23:31:15.085Z에 임시 WO-INC 번호로 작업지시 생성/종결을 기록했고 실제 CMMS 저장은15.557632Z/WO-1003-4CBB였다. 원본 `a028-work-order-observation.json`, 실제 비교 `a028-closure-first.json`2/4 exit1. 기존 성공 검사는 실제 작업지시 존재와 인스턴스 완료까지만 확인했다.

## 변경한 경계

- 재관측 성공은 RESOLVED다. 실제 CMMS의 성공 응답과 비어 있지 않은 ref를 받은 뒤에만 Incident에 작업지시를 기록하고 CLOSED로 전이한다. 임시 번호는 만들지 않는다.
- 선택 변수에 승인 옵션 전체를 보존한다. 기존에는 id/name/kind만 남겨 명시된 WO_CREATE.value를 잃었다. 명시된 작업지시 값은 그대로 쓴다. 명시된 WO가 없는 제어 옵션은 프로세스 정의에 존재하는 정비 서비스의 후속 점검 요청이며, 임의의 다른 대안 SOP나 정비 절차를 선택하지 않는다. 화면에서 승인 전에 그 내용을 안내한다.
- CMMS 요청은 결정/옵션/승인자/옵션명/입력으로 SQLite에 먼저 저장한다. 요청이 달라지는 재시도는 거절한다. Incident/태스크/감사는 같은 실제 CMMS 참조를 사용한다. 발행 완료는 실제 정비 완료를 뜻하지 않는다.
- 작업지시만 선택한 경우 PLC를 거치지 않으며, 실제 접수 뒤 Incident와 인스턴스를 닫는다. 레거시 API도 이를 '운전원 거부'로 기록하지 않는다.
- SQLite 영수증 저장 실패 때 메모리 Incident를 종결 상태로 남기지 않는다. 실제 CMMS 뒤 SQL 완료 저장이 실패하면 실제 발행 사실은 보존하고 같은 요청의 응답을 다시 받아 태스크를 완료한다.
- RESOLVED와 저장된 CMMS 요청이 함께 있으면 재시작 뒤 그 요청을 회수할 수 있다. 이는 PLC 명령 재실행이 아니다. 불확실한 PLC 진행 상태는 기존 PROCESS_RESTART_REVIEW 계약을 유지한다.
- 점유 후 service 표식을 커밋하기 전에 죽는 경로도 조회한다. 지원하는 멱등 Incident/CMMS 서비스만 대상으로 하며, 인스턴스 잠금과 최신 행 재확인으로 동시 회수를 직렬화한다. 일반 에이전트 claim 전체의 30분 stale 정책을 바꾼 것은 아니다.
- CMMS 자동 시도3회 후 PENDING이면 기존 승인 역할 이상의 담당자가 같은 요청을 재전달할 수 있다. 이전 오류 이벤트는 보존하고 rework_count를 올린다. 프로세스 소유 Incident는 레거시 재전달 API로 우회하지 못한다.

## 확인한 결과

- 신규7검사 수정 전 실패(`a028-red.xml`), 최초 수정6/7에서 승인 변수의 actions 유실을 추가 발견하고 수정.
- 최신 전체382 passed/기존경고2(`a028-final-tests.xml`), 포털 JS2파일 문법 검사 통과. 직접 클릭 검수는 아직 못 했다.
- 실제 PgRepo/SQLite/HTTP CMMS 첫4/5. 자식프로세스가 HTTP 저장 뒤 os._exit(73)로 죽으면 일반 consumer가 남아 회수되지 않았다. 조회 수정 뒤5/5, 자동시도소진/역할검사/8개경쟁회수 추가 뒤 **6/6** (`work-order-recovery-pg/report.json`, `a028-pg-six.log`). 실패 report-first.json과중간report-five-pass.json도 보존했다.
- 실제 CMMS1건/동일ref, 재시작 후 PLC 대역명령 추가0, 8경쟁자 HTTP호출1회. fixture tenant/decision만 정리해 instances/events/work_orders0. 이 검사의 PLC와 그래프는 대역이며 실제 설비 장애 검증으로 확대하지 않는다.
- 배포 뒤 `scenario_instance_test.py` **40/40 exit0** (`a028-legacy-instance.log`). instance148e3b71-17ce-43a9-948a-eca411653cbe/INC-1004-01-1e8e/WO-1004-F744. CMMS00:09:04.823064Z 뒤 Incident종결00:09:04.850Z, 독립 비교4/4(`a028-instance/receipt-check.json`). 이 실행의 에이전트는 legacy bridge다.
- 직접legacy `scenario_test.py --quick` **48/48 exit0**, 173초(`a028-direct-legacy-receipt.log`). 추가한 번호/시간 검사는 enterprise reset 전에 실제응답을 `legacy-receipts/INC-1004-02-d4aa.json`에 보존한다. 첫46/46로그도 별도로 남겼다.
- 교재13장 실제접수/종결/재시도 설명을 추가하고 1280/390 정적HTML렌더를 직접 확인했다(`book-render/a028-receipt-*.png`, overflowfalse, 구조검사0문제). 이는 포털 실제버튼 검수가 아니다.
- 새 Codex40검사를 위해2×/bridge off로 전환했으나 `Start-Process ... run_worker_host.ps1 -Provider codex`가 자동 승인 심사에서 `blocked by policy`로 거절됐다. 우회 실행하지 않았다. 기본 instance/20×/legacy로 복구했고 PowerShell CIM worker0, 개인config SHA불변(`a028-restored.json`). 따라서 A025의38/38을 새 코드의 Codex 검증으로 재사용하지 않는다.

## 남는 경계

인스턴스 CMMS 서비스는 재시작 뒤 자동 회수한다. 직접 legacy 경로는 저장된 요청을 수동 재시도 API로 회수하며 별도의 자동 복구 루프는 없다.

모든 감사/Neo4j 투영을 아우르는 outbox는 아니다. 승인 당시의 조치와 현재 설비/규칙 재검증(A027), SOP 인제스천(A026), 실제 UI 검수·전체 강의 완주가 남는다. CMMS 응답 자체의 업무 의미/정비 수행 완료는 별도 계약이다. 새 코드가 과거의 잘못된 Incident/감사 데이터를 사후 성공 데이터로 고치지 않는다.
