# 사용자 위임 후 남은 기능 진행

현재 포털8088은 후속 runtime 판본이다. 큰 묶음 전체2673개 통과·배포·3문서 적재 뒤 구매 경제 정책을 공식 개정하고 **실제 C의 교육용 ERP 업무 COMPLETED**를 확인했다. 실제 Sol B1회는 원인 연결 뒤 부품/기한 조건으로 PENDING이다. 실행별 도구 키 수정 뒤 최신 B의 같은run 공개/도구 PNG를 평가 보류 전에 확인했다. **원본 C 도구 PNG 무효 정정은 유지한다.** 첫 최종GET캡처에서 B보류진단/제목 계약의 화면 결함을 발견해 수정 중이며 전체 UIUX·외부 인증 완료는 아니다. 이전 스냅숏/준비 단계는 이력이고 맨 아래 최신 실행/잔여 기록이 우선한다.

사용자가 원문 대조·검토·적재를 맡겼다. 실제 검토 신원은 **사용자 위임 Codex**이며 특정 사람의 신원이나 사람이 직접 검토했다는 기록을 만들지 않는다. 기존 승인 단계의 권한은 바꾸지 않는다.

## 실제 운영 상태

사용자 열람 주소 `http://127.0.0.1:8088/`는 현재 stream 포함 runtime manifest 판본이다. 과거 별도 정적 `stable-portal` 스냅숏 고정은 당시 운영 이력이며 현재 live 판본으로 소개하지 않는다. root 소유 마운트/스냅숏 자료를 임의로 삭제하지 않는다. 제품 스택은 유지하며 실제 C 제안1회 뒤 워커8097은 다시 종료 상태다. 원본 볼륨·처리 건·교재 폴더는 보존한다.

루트가11:02 KST부터 `LIVE_LOCK`을 소유한다. 후속 배포·적재·실제 워커 검증은 검사기/워커 중복 없이 순차 진행한다. 먼저 검증한 A는 미달 경로 COMPLETED, B/C는 지식 부족 PENDING으로 보존돼 있다.

## 원문·기존 지식 대조

세 문서의 보관 원본 바이트와 `docs/samples` 원본이 일치한다. 추출 인용153개·경고55개를 대조했다. 기존 고장 지식6개는 문서 journal 소유가 없는 seed다. 기존 팬 점검·벨트 교체8단계는 최신 원문의 내용과 일치하지만 옛 점검 절 발췌의 진동 조건은1.2이며 최신은0.9다. 기존 노드·조건을 덮거나 SOP 번호를 바꿔 충돌을 피하지 않는다. 정확 재참조·개정 출처·참고 절차를 보존할 모델을 검토한다.

실제 구매 원천은 `part_quotes/quote_rows`다. 펌프 씰 견적3개와 Part의 SUPPLIED_BY를 확인했다. 레거시 `scm_suppliers`의0건은 별도 등록 자료 범위이며 견적 부재가 아니다. 원문 구매 기준은 순정·저가 승인·전체 최단 후 AVL 검사다. 현재 공급사 하나로 원문을 고정하거나 최단 미승인 대안을 숨기지 않는다.

원문 근거 없이 붙은 PM 정지·부하 설정 명령2개는 검토에서 제외한다. 현장 정비·시운전 원문과 측정 조건은 남긴다. 원문에 없는 승인자·고장 유형·증거 가중치·공급 관계는 만들지 않는다.

## 구현·시험

- 구매 Part 영역의 기본 모델304개 통과. 동적 공급사 정책, 실행 시 실제 견적 연결, 구매 도구3개와 일반인 한국어 처리 기록을 함께 보완 중이다.
- 워커는 구매 판단에 `purchase_context/evaluate_purchase/submit_purchase`를 사용하고 현재 생산 작업 범위를 그대로 전달한다. 조회 전용 시험의 `submit_purchase`는 차단한다. 관련77개 통과(`pytest-worker-purchase.log`).
- 기존 MCP30개와 기존 유일 판단 등록 쓰기 도구 검사는 그대로 보존한다. 추가된 구매3개는 별도로 정확한 이름과 READ/READ/WRITE를 요구한다. 도구 수를 낮추거나 표시·쓰기 경계 검사를 제거하지 않았다.
- `c3_ingest.py`의409 뒤 자동 지식 제거·재시도 우회를 제거했다. 충돌과 검토 본문을 보존하며 새 명시 검토 없이는 바꾸지 않는다. 관련18개 통과(`pytest-no-conflict-fallback-approved.log`). 최초 실행의 임시 디렉터리 권한 오류 로그도 보존한다.
- 새 설치용 구매 등록 스킬과 보호 seed 본문만 업그레이드하는 추가 migration53을 준비했다. 예상 본문과 다른 seed는 실패하며 사용자 스킬·과거 실행 스냅숏은 덮지 않는다. 실제 적용은 아직 안 했다.
- Google 실제 API 기반 Calendar/Drive MCP·브라우저 OAuth 절차를 준비했다. 관련61개 및 실제 로컬 무인증 검사8개 통과. 계정 로그인·자료 읽기·일정 생성은 아직 안 했다. [연결 준비](google-meeting-connection-preparation.md)에 필요한 사용자 조작과 실제 한계를 기록했다.

새 전체 회귀·실제 적재·B/C 재실행·최신 화면 캡처는 이 묶음의 구현 안정화 뒤 별도로 기록한다. 이전 판본의 통과를 새 미완료 소스의 검증으로 대신하지 않는다.

## 후속 모델 안정화와 실제 독립 검증

구매 정책 큰 묶음326개·승인/예측143개가 통과했다. 참고 원문은 `kind=reference/executable=false`로 보관하며, 정확 동일 SOP·단계 재참조만 기존 Skill 계약을 pin한다. 실제 독립 Neo4j에서 reference·개정·rollback·HISTORY·HTTP 회귀 **51 passed/0skip/21.67초**를 확인했다. 운영 graph 쓰기는0이다. 초기 임시 DB 기동 실패는 보존했고 자원에 맞는 로그 회전 크기를 적용했으며 트랜잭션 로그·사전 할당·검증 조건은 유지했다.

PM13의 기존 오더 일정 변경은 명시 WO_RESCHEDULE과 실제 계획 오더·회차·목표 창·기한·승인 스냅숏으로 처리한다. 새 오더/기본 창으로 바꾸는 우회는 제거한다. 관련361개 통과에 더해 독립 PostgreSQL55322의 실제 일정 변경·멱등·원자성 **6 passed/1.00초**를 확인했다. 현재 운영 데이터에는 변경할 PM 계획 오더가 없고 다음 창은 기한을 넘으므로 불가 대안으로 유지한다. Source-only 승인·물리/업무 실행과 공급사 기본값 우회 방지의 기존 확대 회귀107개도 통과했다.

실제 원문 검토 기록을 세 문서 각각 준비했다. HM은 기존 팬8단계의 정확 재참조와 번호/역할이 다른 조치의 비실행 출처 보관, 빠진 회복 판정 문장 복원을 명시했다. PM은 잘못 붙은 PLC 명령을 제외하고 현장 패키지·시운전을 참고로 남기며, 일정 변경·생산 중 오더 손실80만원의 실제 입력 연결을 검토했다. PR은 세 Part와 동적 정책3개·원문 규칙7개를 보존한다. PR 준비 검사 통과, PM은 아직 운영 graph에 새 capability가 없어 연결 오류가 표시되는 것이 현재 정상이다. 실제 적재는 아직 안 했다.

검토 뒤 제거한 지식 정의에 옛 extraction 충돌 표시가 남는 문제를 실제 준비 과정에서 발견했다. 명시·유효한 현재 knowledge 본문을 기준으로 검사하도록 제품을 수정했다. knowledge가 없거나 잘못된 경우 기존 경고를 유지하며 기존 실패 기대를 바꾸지 않았다. 원문 단계의 반복 문장도 기존의 정확 좌표를 검증해 보존하고, 새 인용이 모호하면 거절한다. 관련38개 통과; 최초 실패 로그를 보존했다.

## 최종 원문 검토와 추가 정비 결함

검토 방식은 `review_method=user-delegated-ai-review`에 따로 기록하고, 원래 추출 방식 `method=manual-source-proposal-v1`과 실제 추출 세대 연결을 보존한다. 추출 연결을 가진 요청은 방식 문자열이 바뀌어도 실제 완료된 추출과 대조하도록 수정했다. 관련97개 통과. 독립 최종 감사에서 검토본의 원문 좌표148개·검토 인용41개·22절차82단계가 일치했고, 새 권한 추정이나 원문 왜곡은 발견하지 않았다. [독립 감사](final-delegated-review-independent-audit.md)가 적용 전 근거다.

독립 감사가 두 실행 누락을 발견했다. 실제 HYD-02의 누적11950h·정비 뒤1950h이면 다음12000h 차례는4000h 패키지인데 기존 CMMS는 고정2000h였다. 또한 PM14가 요구한 동종 peer의1800h 이상·공통 정비 시간·실제 두 설비 정비 오더 범위가 강제되지 않았다. 후속 큰 묶음에서 원문 기반 패키지 선택과 두 설비의 승인·원자적 업무 처리 구현을 완료했다. 현재는 전체 회귀에서 발견한 기존 계약과의 호환 결함을 해결하는 단계다. 누락된 재고나 이력을 성공용 값으로 만들지 않는다.

첫 최종 전체 시험은2116통과·41건너뜀·453setup오류·실패0으로 끝났다. 모든 setup오류는 사용자 지정 임시 경로의 부모 `D:/work/study/.test-temp`가 없었기 때문이다. pytest는 명시한 basetemp의 부모를 만들지 않는다. 원문 [로그](D:/work/study/hyd-iot-edu/.evidence/delegated-review-20261012/pytest-whole-missing-temp-parent.log)와 [XML](D:/work/study/hyd-iot-edu/.evidence/delegated-review-20261012/pytest-whole-missing-temp-parent.xml)은 해당 이름으로 옮겨 보존했다. 부모를 명시적으로 준비했고 제품 코드·기대값은 바꾸지 않았다. 새 자식 임시 경로에서 전체 시험을 다시 수행 중이며, 현재 `pytest-whole-final.*`은 이 후속 실행 자료다.

## 실제 원천으로 확인한 패키지와 미등록 부품

세 설비의 실제 CMMS 상태·정비 창·ERP 재고9조회가 모두200이다. 읽기 전용 SQL로 설비3개·부품3개·재고3개·운전 계수기3개·정비 창 규칙9개와 운영 migration52를 확인했다. ERP에는 씰 키트·팬 베어링·쿨러 코어만 있고 리턴 필터 부품/재고는 없다. graph에 있는 리턴 필터의 부품 번호는 재고의 존재를 뜻하지 않는다. 증거 `PM-full-business-source-read.json`의 persistentWrites=0이다.

원문의 모델 적용 범위와2천/4천/8천 시간 패키지·포함 부품을 명시 `maintenance_policy`로 검토본에 추가했다. 부품 번호·수량이 미상인 작동유는 null과 근거 사유를 보존한다. 실제 읽은 자료로 새 pure 경로를 확인한 결과 HYD-02의 이번 차례는4000시간·다음 기준 누적12000시간이며, 리턴 필터 재고 확인 불가로 executionReady=false다. 실패해도 정확한 패키지·필요 부품과 미등록 사유를 diagnostics에 보존한다. `PM-actual-policy-scope-validation.json`이 실제 원천 계산 근거이며 실제 오더를 발행한 증거는 아니다.

기존 승인 검토 기록이나 추출 세대가 나중의 실행 본문 변경으로 달라지지 않도록 본문·nested 변경과 변경 기록을 복사해 분리했다. 기존 검사와 새 원본 보존 회귀23개 통과(0.84초). PM capability 정본 두 문장은 실제 graph의 기존 System/Decision/Task를 대상으로 transaction 안에서 연결 검사 뒤 전체 rollback했고 영구 쓰기0이다. 실제 capability 적용·문서 적재·SQL56·그룹 업무 실행은 최종 전체 검증 후 수행한다.

후속 독립 감사의 최신 수량은 원문 좌표156개·검토 인용43개·22절차82단계다. 148/41은 정책 추가 전 기록으로 구분한다. 최신 PM graph-issues 파일에도 capability 미적용에 따른3개 오류가 그대로 있다. [문서별 검토 JSON](reviews/README.md)을 검증 기록 안에 보존했고, 원래 추출 연결과 실제 검토 주체 **사용자 위임 Codex**를 유지한다.

정비 정책 필드 추가 뒤 실제 독립 Neo4j의 참고/개정/판단 이력51개를 다시 검사해51통과·0skip·28.32초를 확인했다. 새 SQL56의 첫 실제 PG 검사는 IF 안 CASE 표현식 문법 오류로6통과·10setup오류였다. SQL 표현식을 고쳐 당시 동일 검사16개가 실제 PostgreSQL55322에서 모두 통과(3.47초)했다. 이16개 결과와 첫 실패 로그/XML은 이력으로 보존한다. 두 오더·예약·계획 연결·멱등·중간 두 번째 오더 실패·전체 취소·변경된 peer의 전체 취소 거부가 검증 대상이다. 기대값은 바꾸지 않았고 각 변경은 시험 transaction에서 rollback했다.

## 최신 검증과 전체 회귀 진행 상태

독립 PostgreSQL에서 `test_pm_scoped_pg`와 `test_pm_reschedule_pg`를 함께 실행해 **20개 통과·3.69초**를 확인했다. 근거는 `delegated-review-20261012/pytest-pm-scoped-pg-final2.log/xml`이며 운영 writes=0이다. 예약·실물 출고·기존 오더 할당 유지의 경계를 구분하고 이전16개 결과를 최신20개와 중복 합산하지 않는다.

PM 패키지·범위·오더 영수증·승인·기존 UI 묶음은 **49개 통과·건너뜀0·26.79초**다. 근거는 `final-completion-20261012/pytest-pm-package-ui-final-approved.log`와 [화면 검증 기록](ui-final-remaining.md)이다. 독립 메모리/브라우저 fixture 검증이며 실제 ERP에 필터를 등록하거나 운영 승인·오더 발행을 수행한 결과가 아니다.

부모 경로 문제를 해결한 첫 전체 시험은 **2,624개 통과·10개 실패·16개 건너뜀·경고21·1,559초**로 끝났다. C1 시나리오 B와 enterprise-sim inverse 호환 실패를 포함하며 `pytest-whole-first-complete.log/xml`에 원문을 보존한다. 앞서81%에서 실패를 발견했다고 기록한 실행의 최종 결과가 이 자료다. 현재 `pytest-whole-final.log`과 혼동하지 않는다.

후속 근본 mode 경계 수정 묶음은 **357개 통과·건너뜀1·125.52초**, 별도 경계 검사는 **87개 통과·2.34초**, 구매 preflight는 **37개 통과·1.80초**다. 근거는 각각 `pytest-pm-mode-wide-final.log`, `pytest-pm-mode-final-boundary.log`, `pytest-purchase-structural-meta.log`다. 기존 실행 mode와 원문 정책 실행 mode의 경계를 확인했으며 각 묶음이 겹칠 수 있으므로 통과 수를 전체 결과로 합산하지 않는다.

넓은 UI 회귀는 **84개 통과·2개 실패·179.06초**였다(`pytest-evaluation-ui-final.log`). 두 제품 호환 결함을 수정한 뒤 관련 재검사는 **34개 통과·건너뜀0·61.09초**다(`pytest-evaluation-ui-compat.log`). 84+34를 전체 UI 통과 수로 보고하지 않으며 앞선 실패 로그는 보존한다. CSS는 검증 판본5747907 대비 차이0이고 기존 A golden을 유지한다. 앞선 PM49개 통과도 해당 당시 묶음의 검증 범위다.

최종 전체 회귀는 **2673개 통과·16개 건너뜀·21경고·1455.58초**로 끝났다. `pytest-whole-final.log/xml`이 확정 결과이며 앞선77% 실패 없음은 중간 관찰 이력이다. source manifest792개 파일/변경110개를 고정했고 `whole-final-source-manifest-verification.json`의 sourceChangedAfterVerification=[]·passed=true로 검증 중 변경0을 확인했다. 이 판본의 같은 전체 검증을 반복하지 않는다.

전체 회귀 뒤 배포·공식 적재를 수행했고, 최초 C 제안에서는 경제 추천 결함 때문에 승인/효과0으로 중단했다. 이 실패를 보존한 뒤 공식 정책 개정·현재본 비교·명시 위임 선택으로 실제 C 업무를 완료했다. 실제 B1회는 원인 연결 후 부품/기한 조건으로 PENDING이다. 운영 ERP 필터 부재를 성공용 값으로 바꾸지 않는다. 초기 중단과 후속 C 완료를 서로 덮어 쓰지 않는다.

사용자는 ChatGPT Google MCP를 다른 계정으로 연결했다고 알렸다. 해당 연결의 Drive 파일명 검색은 성공했으나 일치0·본문읽기0·쓰기0이다. 이 결과는 HYD 워커 OAuth나 실제 회의 실행의 증거가 아니다. 계정 변경 질문에 GCP client 준비를 안내했던 혼동을 정정했고, ChatGPT 계정 변경에 GCP 준비를 요구하지 않는다. 별도 로컬 HYD 인증 절차와 상태는 [Google 연결 기록](google-meeting-connection-preparation.md)에 구분한다.

## 전체 검증 뒤 실제 배포·공식 적재

root가 검증 판본의 서비스7개를 빌드·배포했다. `build-verified-services.log`, `deploy-verified-services.log`, `verified-service-state.txt`가 근거다. 최초5747907 정적 열람 화면은 이력이며 현재8088은 후속runtime 판본이다. CSS/색상과 A golden을 유지하며 최종 UIUX 판정은 별도다. 루트 LIVE_LOCK을 유지하고 actual B1회 뒤 owned 워커28980 tree를 정지했다. `worker-final-B-stopped.json`의 최종 확인은17:12:12 KST·listeners=[]다.

공식 Supabase CLI `migration up --local`로53(purchase_part_skill)·54(pm_reschedule)·56(pm_scoped_schedule)를 적용했다. `migrations-official-applied.log`의 Migrations applied와 세 파일 목록을 확인했다. 정본 `pm_capabilities.cypher`의 두 문장도 실제 적용했고 `pm-capabilities-applied.json`에서 WO_RESCHEDULE transaction Action과 production_running boolean InputData의 after/readback을 확인했다. 앞선 rollback 검사는 당시 영구쓰기0의 검증 이력이며 이 후속 실제 적용을 대신하지 않는다.

공식 `c3_ingest` 경로로 세 문서를 각각 HTTP200 적재했다. 검토 신원은 모두 **사용자 위임 Codex**, review_method는user-delegated-ai-review이고 원추출 연결을 유지한다.

| 문서 | 공식 accepted marker | 실제 batch |
|---|---|---|
| HM-8 | `HM-8-official-ingest-accepted.json` | `21acf8f9-9e9d-4360-8ab7-9bdbf6a3a119` |
| PM-02 | `PM-02-official-ingest-accepted.json` | `dff3825b-01ef-4b7a-9488-d3cdcc1aa371` |
| PR-07 | `PR-07-official-ingest-accepted.json` | `0729247c-f26f-449c-8a90-324f4e1532c7` |

`official-ingest-all.log`의 status200과 `manual-history-after-official-ingest.json`의 batch·검토자·원추출·출처/참조 이력이 실제 적재 근거다. 최신 공식 preflight의 구조 issues는 세 문서 모두0이며, 이전 PM capability 미적용3개는 준비 단계 이력이다. PM의 실제 counters/order/window/stock/staff 검사는 structural 단계에서 execution_checked=false로 남기고 실행 전 다시 확인한다. PR의 structural ready도 실제 견적·재고·공급사 검사나 실행 성공을 뜻하지 않는다. 일반 preflight의 needs_human_review/can_commit 표시를 위임 검토 기록을 통한 공식 commit 결과와 혼동하지 않는다.

## 후속 실시간 결함과 남은 검증

사용자는 도구 호출·결과·공개 진행 설명 전체가 실시간으로 누락 없이 보여야 한다고 다시 강조했다. 원 경로의 **공개 assistant 문장 경계 버퍼링**과 **원문1500자 절단**을 근본 수정했다. worker→DB/SSE→portal 공개 출력/도구 결과가 대상이며 비공개 내부 추론을 노출한다는 뜻은 아니다.

이 수정은 전체2673개 통과 판본 이후 변경이다. 집중 회귀 `pytest-public-stream-final3.log`는 **87개 통과·8.21초**, 긴 도구 입력/출력 검사 `pytest-tool-verbatim-first.log`는 **25개 통과·2.48초**다. `runtime-source-delta-from-whole.json`은 delta9파일(제품7+새 시험2)과 verified=true를 기록한다. runtime manifest를 따로 보존했고 불필요한 전체 재실행은0이다.

원본 `watch-C-live/result.json`의 passed=true·freshFrames26·캡처2개·before_actual_completion=true는 그대로 보존한다. **root의 후속 PNG/native_row_text 대조에서 캡처 선택 결함을 발견했으므로 이 passed를 두 PNG 모두의 새 실행 증명으로 해석하지 않는다.** `C-public-before-completion-1.png`는 최신16:34:51 공개 문장의 유효한 완료 전 화면 증거다. freshFrames26과 최신16:34 도구 SSE 수신도 유효하지만, `C-tool-before-completion-2.png`는 과거10:13 실행의 행을 잡았다. 따라서 새 실행의 도구 DOM/PNG는 미입증이며 해당 도구 캡처를 무효로 정정한다.

원인은 tool_use_id=`item_1`이 실행마다 재사용되는데 trace/taskDetail/caseRecord의 map·DOM key가 실행job 없이 그 ID만 사용하고 watcher가 `.first`로 과거 행을 선택한 것이다. 후속 `[case, task, job, toolid]` 키·교차run 부정 시험과 checker의 최신job DOM 선택을 강화했다. 최신 실제 B watcher에서 같은run의 두 행을 평가 보류 전에 다시 확인한 근거는 아래에 있다. 이 후속 검증이 원본 C 도구 PNG를 유효하게 바꾸지는 않는다. U16/U20/F13와 전체 시각 판정은 열린 상태다.

원본 consoleErrors/pageErrors는0이지만 health 주소 ERR_ABORTED는 보존하므로 모든 네트워크 요청 성공이라고 확대하지 않는다. 이번 최신 공개 문장 증거도 모든 옛 trace의 한국어 표시·원문 해독·전체 UIUX 검증을 뜻하지 않는다. 집중 시험 결과와 원본 watcher 파일은 수정하거나 삭제하지 않았다.

| 사용자 요구 | 현재 확인한 근거 | 남은 판정 |
|---|---|---|
| bpmn.io 등록부터 실제 실행 | 기존 A/B/C 왕복/등록/배포·학생 흐름DONE·A미달 종결. 후속 C현재정책 선택→교육용ERP발주/입고/재고·COMPLETED | B1회는원인 연결 뒤 부품/기한으로PENDING. 전체 최신화면·외부 실습 가능 판정은 별도 |
| 최종 실라버스 전체 실습 가능 | 최종 XLSX 네 시트 대조·핵심 포털 행별 검증표, source/PG/UI 자동 검증 | 외부 MCP 계정/권한·실제 회의·학생별 환경 등 미확인 항목을 전체 가능으로 합치지 않음 |
| 실시간 누락 없는 진행/도구/결과 | 집중87개·긴 입출력25개와 B freshFrames23/private0·같은run 공개/도구 PNG의 평가 보류 전 표시 | 원본 C도구PNG 무효 유지. B업무 완료 증거가 아니며 최종 보류진단 UI·전체 시각 판정은 아직 |
| ProcessGPT 최신·Dify·ontology 참고와 실물 증거 | 이 요구는 이전부터 알고 있던 기준이다. `REPO_GAP.md`·`REPOSITORY_REVIEW.md`의 판본/열람 기록, ProcessGPT 실제 컴포넌트 비교와 Dify 공식 화면/실제 HYD 나란한 캡처를 보존 | 참고 이름을 안다는 사실만으로 최신판 전체 이식·새 화면 일치·UIUX 최종 승인을 주장하지 않음 |
| 학생이 인증한 MCP를 포털에 등록 | 기존T5의 URL/stdio·headers/env·`${SECRET:KEY}`와 실제 학생 등록/읽기 호출 검증 | ChatGPT Google 앱 연결은 별도. 로컬 HYD OAuth·외부 쓰기·실제 회의 완주는 미확인 |

작업 원칙은 `C:/Users/roede/.claude/CLAUDE.md`에서 연결된 `D:/work/claude-skills/CLAUDE.md`와 debug/e2e-verify를 읽어 적용했다. 원칙 파일·교재·lecture-deck를 수정하지 않았다. 코드 반영 해시와 원격 commit/push 결과는 git log와 root 최종 보고로 확인한다.

## 실제 C 제안 뒤 발견한 구매 경제 결함(F26)의 이력

공식 재평가와 실제 `gpt-6.1-sol` 워커1회로 C 처리 건 `c3_spare.01a60b8d-284d-422b-96db-113dda3dd43f`의 T_agent가 DONE, T_approve가 IN_PROGRESS가 됐다. `C-actual-approval-inspection.json`의 승인/효과는0이고 입고·발주 작업은 아직TODO다. 실제 stream 캡처와 이 업무 실행 상태를 구분한다. `worker-first-live-stopped.json`에서16:34:29 KST 시작·16:39:39 KST 정지를 확인했고 root가8097 없음도 확인했다. 승인하지 않고 C를 WAIT로 보존했다.

승인 전 `C-actual-decision-before-approval.json`을 **PR-7.4 원문**에 대조했다. 판단 DEC-1012-003-0869는 대체 승인 공급사A(SOP-PUR-12)를 추천했으며 OEM(SOP-PUR-11)과 점수2.83으로 동점이다. 두 후보의 scoreParts에는 물리 forecast2.0과 MES delivery1.33이 들어가지만 원문은 구매 수량·단가·불량률·불량1건 손실250만원과 조건부 전수검사20만원으로 총비용을 비교하라고 한다.

| 실제 후보 | 원문 적용 계산(만원) | 총비용 |
|---|---|---:|
| A정밀·수량6·단가35·불량률12% | 6×35 + 6×0.12×250 + 전수검사20 | 410 |
| B-OEM·수량6·단가55·불량률2% | 6×55 + 6×0.02×250 | 360 |

이는 적재 HTTP200 실패가 아니라 **실제 추천의 원문 경제 의미 검증 실패**다. 공급사 선택 정책과 실제 견적 연결을 구현한 것만으로 총비용 순위까지 완성됐다고 볼 수 없다. OEM 발주금액330만원의 보고 경고는 PR-7.5에 따른 표시이며 구매 담당 승인1회를 다른 권한으로 바꾸거나 임의 비용 감점으로 바꿀 근거가 아니다. 전체 최단 C 공급사는 AVL=false로 제외된 원문 경계를 유지한다.

이 단계의 승인0·효과0과 원DEC의 A추천은 당시 실패 증거로 보존한다. 이후 source-backed purchase comparison policy와 scope별 경제 순위를 근본 수정하고 아래 공식 개정·현재 비교·C업무 효과를 검증했다. 추천 이름만 바꾸거나 과거 DEC를 덮지 않았다. F26은 구현/정책/C효과 범위에서 해소됐으며 U16/U20/F13·전체 UIUX는 열린 상태다.

## 구매 정책 공식 개정과 실제 C 업무 완료

첫 정책 개정 시도는 기존 batch 재사용을409로 거절했다. `first-failed-PR-comparison-official-*` 원문을 보존했고 검사/기대값을 바꾸지 않았다. 공식 reopen에서 원제안의 필드·추출 연결이 불변임을 검토한 뒤 새batch와 직전head를 연결해 개정을 승인했다. `PR-comparison-official-accepted.json`의 batch는 **1b45ca6f-6d68-4f8d-bcdc-2722ce3f91c1**이며 공식HTTP200 결과와 `manual-history-after-comparison-revision.json`에 사용자 위임 Codex·원추출 세대를 보존한다.

실제 읽기 전용 MCP `C-current-economic-mcp-response.json`은 OEM의 구매330+기대불량30+전수0=총360만원, A의410만원을 비교해 OEM을 추천하고 미AVL 최단공급사를 제외했다. 원DEC의 잘못된 A추천을 변경하지 않고 현재 정책과 현재본 최종비교를 검토했다. `C-economic-choice-accepted.json`은 **명시 사용자 위임 OEM 선택 DELIVERED**와 review REV-b26557f1-61b9-4c04-a29a-61dc7dc00f71을 기록한다. 사람의 직접 선택이라고 꾸미지 않는다.

`C-business-completion-proof.json`과 실제API 대조로 다음 교육용 ERP 결과를 확인했다.

| 항목 | 실제 결과 |
|---|---|
| 처리 건 | COMPLETED |
| 공급사·수량·발주 금액 | sup:b(순정)·6개·330만원. 비교 총비용360만원과 발주금액을 구분 |
| 발주·입고 번호 | PR-1012-FE8A / GR-1012-C42C |
| 입고 로트·검사 | LOT-261012-654 / 합격 |
| 실제 재고 | on_hand9·reserved2·available7·below_reorder_point=false |

실제 발주 참조는 **T_po.output.purchase_order.ref**다. 처음 단발 readback driver가 존재하지 않는 variables_data.po_no를 가정해 assert가 실패한 원문은 보존했다. proof의 rejected_read_driver_assumption에 원인과 정정 참조를 남겼으며 제품/시험 계약을 변경하지 않았다. 이 업무 완료는 교육용 enterprise-sim의 실제효과이며 외부 실공급사 주문이나 물리 정비 완료가 아니다.

## 실제 B 보류·최신 스트림과 최종 화면 잔여

실제 Sol B1회에서 현재 원인 연결을 확인하고 정비 카드를 평가했으나 필터·작동유 실제 재고를 확인할 수 없고 연기안은 허용상한을 넘어서 PENDING을 유지했다. 필터/작동유 부재를 같은 패키지의 교환 의무로 일괄 해석하지 않고 각 원문 패키지 범위를 구분한다. 오일 교환 미상은8k 범위이며 HYD-02의4k 차례에 임의 오일출고를 추가하지 않는다. 성공을 위해 재고를 만들지 않았다.

`watch-B-final-live/result.json`은 passed=true·freshFrames23·privateEvents=[]·business_completion_claimed=false다. root가 최신 공개17:09:59·도구17:10:04 PNG를 직접 확인했고 둘의job은run-6c2ddc9c-1b6c1170ce5849f5837537e125699a0a로 같다. 두 캡처는 **17:11:17 평가 보류 이전(before_agent_assessment_end)**이다. 업무 완료 전 증거라고 이름을 바꾸거나 B업무 완료로 주장하지 않는다. 원본 C도구PNG 무효 정정과 후속 B검증을 구분한다.

WO_RESCHEDULE이 신규 예측 목록에서 빠진 1파일 결함을 근본 수정했고 `pytest-pm-reschedule-forecast.log`의73개 통과를 확인했다. 후속 3서비스 배포와 아래 실제 MCP 읽기 평가를 완료했으며 추가 LLM 실행은0이다. phase1의 제품797개/delta32와 후속 묶음(기존87/25·backend130+신규16·schema16·UI78+15·forecast73)을 구분하며 중첩 합산하거나 전체2673개 판본의 결과로 바꾸지 않는다. `pytest-purchase-total-final.log`의1실패/130통과와 final2의경로오류는 원본 그대로 보존하며 이를 backend 전체 통과 로그로 소개하지 않는다. purchase 신규16·schema16·UI78+15·forecast73의 통과는 각 집중 로그 범위다. forecast1파일·후속 UI 수정 이후 새 phase2 snapshot/최종 캡처는 아직 대기다. 전체 재실행0이다.

첫 최종 GET 캡처 `portal-final-delegated-live/result.json`은 **passed=false**다. B의 정식 deferred evidence에서 진단 DTO를 소비하지 않아 실제4,000/12,000 근거가 화면에 없었고, 없는 `.cr-title`을 찾던 driver도 시간초과했다. ui_sol이 deferred evidence→DTO와 shell alias의 실제 source 누락을 수정 중이다. 원본 실패를 덮거나 검사를 완화하지 않는다. 아래 B 현재 읽기 평가와 최종 UI 캡처는 서로 다른 검증이다. 재캡처 성공·전체 UIUX 완료는 아직 확인하지 않았으며 자료 인증·외부 회의 등의 잔여도 유지한다.

후속 예측 수정 배포 뒤 **08:34Z 실제 MCP 읽기 1회**의 [원응답](D:/work/study/hyd-iot-edu/.evidence/delegated-review-20261012/B-current-after-forecast-mcp-response.json)과 [읽기 검증 근거](D:/work/study/hyd-iot-edu/.evidence/delegated-review-20261012/B-current-after-forecast-proof.json)를 확인했다. 모델 오류는0이며 추천은 null이다. 네 후보 모두 실제 재고 또는 기한 조건으로 제외되므로 B 업무 성공을 뜻하지 않는다. HYD02의 실제 차례는 총11,950h·다음12,000h·6회차·4,000h 패키지다. 리턴 필터의 실제 재고는 미상으로 유지하며, HYD03을 포함하는 묶음에서 작동유가 추가로 미확인인 조건을 HYD02의4,000h 패키지 조건과 구분한다.

| 현재 후보 | 실제 제외 사유 |
|---|---|
| PM11 예약 | 리턴 필터 엘리먼트의 실제 수량·가용 재고 미확인 |
| PM12 출고 | 리턴 필터 엘리먼트의 실제 수량·가용 재고 미확인 |
| PM13 연기 | 다음 정비 시점이 허용 상한을 초과하거나 실제 목표 시점 미상 |
| PM14 묶음 | 두 설비 패키지의 리턴 필터와 묶음 대상 작동유의 실제 수량·가용 재고 미확인 |

최초 읽기 driver는 `document.options`를 가정해 KeyError가 났고 그 로그를 보존했다. 실제 producer 계약인 `document.result.options`를 확인한 뒤 `--verify-saved-response`로 저장 응답만 검증해 **추가 MCP 호출0**이다. `portal-final-delegated-live/cases-before.json`의 B와 현재 DB를 대조해 저장된 처리 건과 보류가 불변임을 확인했다. 추가 워커 실행0·현재 읽기 평가의 쓰기0이다. 따라서 새 예측 결함 항목을 만들지 않으며 F25의 구현/배포 범위와 실제 재고·기한 때문에 열린 B 완료 조건을 구분한다. U16은 최종 UI 캡처, U20/F13은 B 업무 완료·외부 동선·전체 수업 운영·시각 판정, K3는 인증된 외부 회의 MCP의 실제 동선 검증 때문에 열린 상태를 유지한다.


## 최종 phase2 부분 확인 완료

집중 보류 UI46개(136.90초)와 실제 B/C/지식 GET 캡처203항목을 통과했다. phase2 source800개·전체 이후delta36이며 원본 전체/phase1 SHA를 덮지 않았다. 새 화면은4,000/12,000·필터 미확인과 실제C입고·가용7 및 사용자 위임 검토 이력을 표시한다. 사례/작업/승인/효과·검토 원장 불변, pageerrors/consoleErrors/blockedWrites0을 확인했다. health 및 이동 request abort는 원본에 보존한다. 첫 실패 캡처·fixture DOM 준비 오류·옛C도구PNG 무효를 지우지 않았다. 이 절은 앞선 대기 상태의 후속 결과이며 전체 시각 인수·외부회의·B 업무 성공으로 확대하지 않는다.

[최종 화면·실제 영수증·참고 비교와 한계](final-delegated/README.md), [203항목 원본](final-delegated/result.json), [phase2 검증 범위](final-delegated/final-runtime-phase2-verification-coverage.json)를 원격 보관한다. 전체 재실행0, 추가LLM0이다. 서비스는8088에서 유지하고 owned 워커8097은 종료했다.
