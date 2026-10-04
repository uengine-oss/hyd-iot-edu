# 변경 조치의 예측 검토와 사람 승인 (A031)

2026-10-04. 현재 전체 Goal의 일부다. 회의 원천 입력/업무조건 비교 요구(회의 원문 386~404행), `FORECAST_MODEL.md`, `CURRENT_APPROVAL.md`를 잇는다. 완료된 에이전트 작업을 다시 수행하는 일반 ProcessGPT 재작업과 구분한다.

## 계약과 구현

팬·부하를 바꾸면 기존 기본값 예측을 그대로 승인할 수 없다. 현재 그래프의 해당 SOP에 정확히 하나 있는 파라미터 조치와 명시된 min/max 범위 안에서만 변경을 받는다. bool/NaN/범위 밖 값, facts·운전 모드·펌프 등 다른 키는 거부한다. 요청이 원천 사실이나 기본 SOP를 바꾸지 않는다.

`agentsvc.approval.current_options`가 현재 규칙, 역할, 업무 원천, 설비 상태와 명시 모델을 다시 읽는다. `preview`와 실제 승인 검사는 같은 평가 함수를 사용한다. 변경된 effective actions, 원래 SOP 이름/기본 actions, 기본 정책 SHA, 예측 입력/시각/모델/계수/규칙 출처를 함께 반환한다. 권고는 전체 후보의 현재 비교 결과이며, 사용자가 검토한 옵션을 임의로 권고로 만들지 않는다. 선택한 실행 가능 SOP의 역할·절차·후보 근거가 불완전하면 새 검토로 이를 덮을 수 없다. 제외된 변경안은 제외 이유를 보여 주되 실행할 수 없다.

프로세스는 브라우저가 보낸 카드 내용 자체를 승인하지 않는다. 서버의 `DecisionReviews`가 원래 PENDING_APPROVAL 결정과 AWAITING_APPROVAL 사건을 확인하고 새 평가를 받아 `Store.decision_reviews`에 UUID·JSON·SHA256으로 먼저 저장한다. 동일 ID의 다른 내용 덮어쓰기는 금지한다. 원래 결정은 계속 보존되며 미리보기만으로 할일 제출/승인/outbox/설비 명령은 생성되지 않는다.

검토본은 tenant/instance/workitem/decision/option/asset/incident에 묶인다. 조회 시 저장 SHA, 현재 원본 SHA와 소유 범위를 다시 확인한다. 원본이 달라지면 재사용하지 못한다. 사람의 선택 요청은 `review_id`만으로 서버 저장본을 지정한다. 그 복사본이 기존 역할/현재조건/정확명령 검사를 거쳐 PostgreSQL 승인 outbox와 할일 제출의 같은 트랜잭션에 들어간다. 전달 재시도는 커밋된 승인 스냅샷을 사용한다. 최종 PLC 발행 시에도 같은 조치값과 현재 조건을 확인한다.

검토본 생성 전후와 선택 전후에 실제 작업 기한을 확인한다. 느린 원천 조회가 끝난 뒤 기한을 지난 요청이 새 동의를 만드는 것은 허용하지 않는다. 검토본 자체의 별도 TTL은 없으며 활성 작업·사건 상태와 현재 승인 조건이 유효성을 제한한다. 완료된 작업에 같은 검토본을 다시 제출할 수 없다.

## API와 화면

| 위치 | 동작 |
|---|---|
| Agent `POST /api/agent/choice-preview` | 현재 모델로 읽기 평가. 결정/옵션/parameters를 받으며 영속 승인이나 명령은 하지 않음 |
| Process `POST /api/todolist/{id}/decision-preview` | 작업 소유/기한 검사 후 불변 검토본 저장 |
| Process `POST /api/todolist/{id}/select` | 선택적인 review_id로 저장본을 명시 승인. fan/load를 함께 보내면 검토값과 정확히 같아야 함 |
| Legacy `POST /api/incidents/{id}/decision-preview`, `/decide` | 같은 검토 저장소·현재 검사 사용. 프로세스 소유 사건에는 기존 legacy 우회 차단 적용 |
| 포털 인스턴스/HITL | 변경값→새 예측 검토→기본 SOP와 이번 조치값 비교→검토한 조치로 결정. 값을 다시 바꾸면 검토 유효 표시와 승인 버튼 해제 |

역할과 사실의 진위는 별도다. 현재 데모의 역할 문자열 선택은 사용자 인증 시스템을 의미하지 않는다. UI 선택 상태도 승인 권한을 만들지 않으며 서버 검사를 통과해야 한다.

## 실행 기록

- 첫 Linux 전체 단위검사: **503 passed**, 경고3 (`a031-container-all-second.xml/log`). 명시 대역을 포함하므로 실제 Codex/설비 실행 증거가 아니다.
- Windows 최초 검사는 기존 psycopg DLL이 앱 제어에 차단돼 수집 exit2 (`a031-initial-unit`). 보안 설정을 바꾸지 않았다. 표준 Linux 테스트 이미지의 첫 시도는 httpx 누락으로 수집 실패 (`a031-container-all-first`); 설치된 호스트와 같은 httpx0.28.1을 고정한 다음 통과했다. 소스 읽기 전용·네트워크 none·개인 인증 미마운트다.
- 첫 실제20배속 통합 (`a031-review-instance/`)은 **exit1**. 저장/원본 보존/다른 값400/낮은 역할403/facts override409/다른 파라미터의 다른 예측은 확인했다. 검사기가 모델 키를 model로 오기한 1건과 20초 클라이언트 timeout을 보존했다. 서버 감사에는 실제 REMOTE_MANUAL/예측 악화 allowed=false, 승인/outbox 없음이 남았다. 그 동안 30초 사람 기한을 넘었고 추가 TRIP 사건도 열렸다. 이를 완주로 세지 않는다.
- 후속5배속 검사는 plant/detector/process를 같은 속도로 맞춰 사람 기한120초에서 **24/24 exit0** (`a031-review-scale5/`). 95/78 검토의 평형48.792℃/900초뒤51.141℃와70/90 검토의 평형65.182℃/900초뒤61.563℃가 달랐고 후자는 실제 rule:ts1-hard로 제외됐다. 수동 모드 이전 검토 거절→자동 복원→새 검토의 명시 승인→PLC ACK→재관측→CMMS **WO-1004-19B2**→ev:closed. 인스턴스 `anomaly_response.a1dac0de-62c4-4cf2-80cd-969ecd74637b`. 원천 규칙·물리 인터록·예측 재검토 허용차는 변경하지 않았다.
- 검토 저장 뒤 **실제 process SIGKILL/start 28/28 exit0** (`a031-review-restart/`). 검토 `REV-2247f9f8-bd14-4552-8200-4c485d10f0c2`는 재시작 뒤 그대로 명시 승인됐고 재시작만으로 명령은 발행되지 않았다. 실제팬95/부하78/HITL 출처→재관측→CMMS **WO-1004-400F**→ev:closed. 인스턴스 `anomaly_response.9cde5522-1793-41b7-a993-f6c53f4fc9f3`. 승인/outbox의 original_decision과 review ID/actions도 비교했다.
- 추가 가드레일을 포함한 전체 **505 passed**, 경고3 (`a031-container-all-final.xml/log`). 실제 응답을 입력으로 쓰는 JS 순수 컴포넌트 **10/10** (`a031-review-component.json`). 문법 검사 통과. 교재13의 현재승인/예측/변경안3절을1280/390 정적렌더6개로 직접 확인했고 가로 넘침 없음/교재구조0문제다. 이것은 실제 포털 클릭 검증이 아니다.
- legacy HITL 경로도 **17/17 exit0** (`a031-legacy-review-ready/`)다. INC-1004-01-3c56 / DEC-1004-003-5d04에서 같은95/78 검토 저장/다른값 거절/역할 검사/실제PLC/재관측/CMMS **WO-1004-70CE**/CLOSED를 확인했다. 첫 시험은 compose 재생성 직후 준비 전 요청으로 연결종료(exit1, a031-legacy-review)였고, 건강 상태를 기다린 후 다른 증거 폴더로 재실행했다. 서버/물리 정책을 바꾸지 않았다.

## 아직 남은 경계

실제 새 Codex 워커 기동은 이전 자동심사 거절 이후 실행하지 않았다. 포털 실제 브라우저 클릭도 미검증이며 문법/컴포넌트 검사를 직접 클릭 증거로 쓰지 않는다. 검토 저장 뒤 process SIGKILL 복구는 위28/28 범위에서 확인했다. 이 결과가 모든 서비스/DB/네트워크 장애의 복구를 보장하지는 않는다.

새 SOP가 후보에 추가되거나 원인이 달라지면 이 기능으로 원래 진단을 갱신하지 않는다. 네 에이전트 작업의 재실행, 승인 완료 후 변경 요청/보상, 참조중 SOP 병행 판본은 일반 재작업 설계로 이어간다. 원본 completion의 새 workitem UUID/rework_count와 보상 흐름을 HYD의 불변 승인/명령 이력에 맞춰 검토해야 한다. 그 기능을 A031의 활성 선택 작업 미리보기로 대체하지 않는다.


## 복원과 재개

12:51 `a031-runtime-final.json`: instance/20배속/legacy bridge, 설비3RUN/REMOTE_AUTO/열화없음, PowerShell CIM의host worker.main0, 개인Codex config SHA변경없음. `.env`와개인설정은수정하지않았다. 첫실패의두인스턴스만원시상태보존뒤관리자확인으로ev:escalated 종료했다(`a031-fixture-cleanup.json`); 정상회복으로바꿔표시하지않았다. 단위/실제검사프로세스는모두종료했다.

다음은미지원경보의회복계약과일반완료태스크재작업이다. 코드열람에서원본은새UUID/output초기화/rework_count+1과효과별보상을구분한다. 관련구현의실제범위·판단은CURRENT_APPROVAL의A031절을따른다. A031을전체Goal완료로세지않는다.
