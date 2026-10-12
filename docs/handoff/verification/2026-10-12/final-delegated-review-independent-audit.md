# 적재 직전 사용자 위임 검토본 독립 감사

Codex Sol 6.1이 실제 GET source 스냅샷·저장소 sample 원문과 최종 review/body/plan/changes/preflight를 읽기 대조했다. 공유 제품 소스, 실제 그래프, 검토 JSON은 수정하지 않았다. 원문 대조에 fake SQLite source나 새 source UUID를 사용하지 않았다. 자료 루트는 `D:/work/study/hyd-iot-edu/.evidence/delegated-review-20261012/`다.

## 원문 대조 결과

| 문서 | 실제 source SHA와 sample bytes | body 인용 | review 인용 | 절/SOP/단계 |
|---|---|---:|---:|---|
| HM-8 | 6a1a66a6… 일치 | 46개 정확 | 24개 정확·각 원문에서 유일 | 8/8/28 |
| PM-02 | 2a757bd4… 일치 | 61개 정확 | 11개 정확·각 원문에서 유일 | 10/8/33 |
| PR-07 | 7cb1c01d… 일치 | 41개 정확 | 6개 정확·각 원문에서 유일 | 7/6/21 |

모든 source_id/document_id/sha256이 실제 source와 연결되어 있고, body의 148개 anchor는 원문 page의 start:end와 quote가 정확히 같다. 모든 단계 text는 해당 원문 quote에 그대로 있다. 전체 22개 절차·82개 단계가 body와 checked plan에서 동일하게 보존된다. 검토 신원은 `사용자 위임 Codex`이며 사람 신원이나 승인 역할을 사칭하지 않는다. `method=manual-source-proposal-v1`과 `review_method=user-delegated-ai-review`가 분리되어 있고 실제 추출의 instance/workitem/session/generation 연결은 body에 유지된다. manual API가 method 표식을 바꿔도 extraction이 있으면 원세대 binding을 확인하는 수정과 `pytest-binding-final.log`의 97 통과·13 건너뜀·경고 1, 4.29초를 읽어 확인했다. 이 감사가 실제 적재/API binding 재실행을 수행한 것은 아니다.

HM의 FAN-11/12는 기존 동일 SOP·4단계로 정확 재참조하고 전체 실행 계약 pin을 갖는다. 미상 source 승인·cooling FM 제안을 기존 maint-mgr·bearing 계약으로 인수하지 않으며, 등록 설명 1.2와 source 0.9도 그대로 구별한다. COOL-11~15의 추정 alias를 지우고 reference/false로 보존하여 번호·Role·WO target이 다른 기존 01~05 실행 조치를 중복 활성화하지 않는다. HM-8.6의 누락됐던 첫 성공 조건을 복원해 15분·TS1<55·경보 해제 유지/예측 실패 비교/미달 보고의 3문장을 보존한다. 기존 seed FM/Cause 정의와 source-only 실행 규칙 두 개를 명시 제외한 결정에는 새 중대한 원문 왜곡을 발견하지 않았다.

PM의 PLC STOP·LOAD_SET 제외와 현장 패키지/시운전 4절차 reference 보관은 원문을 원격 명령 권한으로 바꾸지 않는 결정이다. PM-13의 명시 WO_RESCHEDULE은 “기존 정비 오더의 시행 시간을 그다음 창으로 옮긴다”에 근거하며 실제 기존 오더/창/회차가 없으면 실행할 수 없는 현재 검사와 맞는다. 필터 막힘→걸러지지 않은 입자의 펌프 마모라는 명시 원인 기전을 별도로 명명해 prior 0.3을 보존한 추가는, seed의 일반 입자 유입→oil-degradation/prior 0.25를 덮는 변경이 아니다. 동일 ID 회피만을 이유로 이름을 바꾼 추가가 아니며 원문 기전·고장 문맥과 검토 사유를 명시했다. 80만원 Rule도 생산 중/납기≤24h/즉시 시행의 원문 조건에 맞고, 이번 비교의 단일 손실을 그대로 보존해 월 반복 빈도를 추정하지 않았다.

PR은 원문의 세 중요 부품 범위를 유지하고 실제 견적에 적용할 oem/lowest_approved/fastest_quote 정책을 명시한다. 특정 공급사로 source를 고정하지 않으며, 최단 견적을 먼저 고른 뒤 AVL이 아니면 절차를 제외하는 순서도 유지한다. 원문 구매 담당 한 번 승인·7개 Rule·정책/입고 확인 reference 분리에 새 중대한 권한 추정이나 원문 밖 변경은 발견하지 않았다.

## 실제 실행 전에 남은 중대한 조건

### 1. “이번 차례 패키지” 선택이 고정 2,000h 상태와 충돌

PM-2.2는 **누적 12,000h 차례에 4,000h 패키지**를 시행한다고 명시한다. `PM-business-facts-read.json`의 실제 HYD-02는 total 11,950h/since-PM 1,950h인데 package 값은 2,000h다. `entsim.data.pm_row`는 `PM_PACKAGE`를 고정 반환하고 SQL `ent.pm_status`도 `st.package`를 읽는다. 새 `maintenance_plan.plan`의 WO_CREATE는 window만 확인해 돌려주므로 누적 차례와 올바른 package의 일치를 검증하지 않는다.

검토본의 “이번 차례 패키지” 단계 자체는 정확히 보존됐지만, 이 데이터로 단순 오더 발행을 “원문 패키지 실행 완료”로 보고하면 원문과 다르다. 실제 누적 회차에 따른 package 선택·패키지 내용/부품 범위 검증을 연결하거나, 해당 실행의 미구현을 명시하고 보류해야 한다. source-only 패키지 21~23을 보관한 것만으로 그 실제 패키지가 수행됐다는 증거는 생기지 않는다. root에 즉시 전달했다.

### 2. PM-14 묶음의 peer 조건과 실제 두 설비 범위가 실행 계약에 없음

원문 SOP-PM-14의 첫 단계는 **같은 기종의 다른 설비도 마지막 PM 뒤 운전시간 하한 이상**인지 확인하라고 한다. 두 번째 단계는 **두 대를 같은 이번 정비 창으로 묶어** 오더를 발행한다. 현재 reviewed Rule은 crew·재고·현재 설비의 정비창 상한만 다루고 peer/model/peer-hours와 실제 두 설비 범위를 확인하지 않는다. `maintenance_plan.plan(WO_CREATE)`는 window만 반환하며 cards·work_orders의 PM 생성 계약에도 묶음 대상이 없다. CMMS schedule-maintenance 경로는 단일 asset 오더를 생성한다.

실제 PM facts에 bundle_peer가 있다는 사실만으로 필수 선택 조건이 검증되는 것은 아니다. 현재 실제 재고 1개로는 PM-14가 재고 Rule에서 제외되지만, 재고 2개 이상이면 이 누락이 드러날 수 있다. source를 실행 가능한 PM-14로 등록하려면 peer 동종/운전시간·공통 창과 두 설비 범위를 확인하는 계약이 필요하다. 그 지원 전에는 reference로 보존하거나 실행을 명시적으로 거절해야 한다. root에 즉시 전달했다. 이 문제는 source anchor 불일치가 아니라 **원문 실행 예외/범위의 미구현**이다.

## 지금 preflight를 통과한 범위

현재 준비 파일에서 HM은 technical_ready=true/issue 0, PR도 true/issue 0다. PM은 false이며 ACTION_NOT_FOUND(action:reschedule-work-order), PM_ORDER_EFFECT_REQUIRED, RULE_INPUT_NOT_DECLARED(in:production-running) 3개를 그대로 반환한다. root가 준비한 정본 capability/InputData를 실제 graph에 적용한 후 새 카탈로그로 다시 확인해야 하며, 기존 false 결과를 무시하거나 성공으로 바꿔 적재하면 안 된다. 새 Action이 source 문서에서 임의 생성되는 것도 허용하지 않는다.

원본 GET 스냅샷 adapter는 고정 hyd/source_id를 확인하고 실제 source의 좌표를 검사한다. 검토 body의 source UUID를 시험 SQLite에서 새로 생성하거나 재등록하는 경로는 사용하지 않았다. 기존 `review-local-source.sqlite` 파일 이름만을 새 검토본의 근거로 해석하지 않았다.

권고는 원문/출처가 검증된 보관과 실제 실행 가능성을 구분하는 것이다. 위 두 PM 조건과 실제 graph preflight 3개를 해결하지 않은 채 “전체 매뉴얼의 모든 실행이 완주했다”고 보고할 수는 없다. root가 수행할 실제 적재·배포·A/B/C 실행은 이 읽기 감사와 별도 증거다. ProcessGPT의 실행 결과/오류 기록 원칙과 ontology-studio의 실제 읽은 source ID 기반 출처 회수 경계로 대조했다. 제품 소스 변경과 실제 graph 쓰기는 0이다.

## 후속 감사: 원문 PM 정책과 실제 B 완료 경계

앞의 패키지 선택·묶음 범위 결함은 **정책 추가 전 감사 이력**이다. 후속 `prepare-hm-pm-source-policy-first.log`와 최신 준비 파일을 독립적으로 다시 읽었다. 기존 자료는 `review-before-pm-policy/`에 보존돼 있다. 이번 감사는 builder를 실행하거나 검토 JSON·제품 소스·실제 graph를 쓰지 않았다. 아래 판정은 준비 자료와 읽은 코드의 계약이며 운영 배포·실제 B 성공의 증거가 아니다.

### 최신 원문 대조와 추출 연결

| 문서 | 최신 body anchor | 최신 review 인용 | 정책 전 body/review |
|---|---:|---:|---:|
| HM-8 | 46 | 24 | 46/24 |
| PM-02 | 69 | 13 | 61/11 |
| PR-07 | 41 | 6 | 41/6 |
| 합계 | 156 | 43 | 148/41 |

156개 anchor 모두 실제 GET source의 page `start:end`와 quote가 정확히 같고 source_id도 일치했다. 43개 최상위 review 인용은 각 원문에서 유일하다. sample bytes SHA 일치와 body/checked plan의 22절차·82단계도 재확인했다. PM 증가분은 PM-11~14의 정책에 각각 붙은 적용 범위·패키지 anchor 2개씩과, 새 PM-11/14 검토 항목의 원문 인용 2개다. 기존 PM-12 조치 수정·PM-13 일정 변경 인용을 패키지 인용으로 바꾸지 않았다.

HM/PM의 추출 instance/workitem/session/generation과 `method=manual-source-proposal-v1`, `review_method=user-delegated-ai-review`는 정책 전 사본과 동일하다. review의 extraction 문자열은 body의 extraction.instance에 대응한다. 문자열과 상세 객체 전체를 직접 비교해 불일치로 판단하면 안 된다. 기존 HM 추출은 모델 전환 이전 자료이며 현재 Sol 검토를 원추출의 모델 이력으로 바꾸지 않는다.

### 정책의 원문 범위

PM-11/12/13은 single, PM-14는 bundle이다. 정책의 HYD-01/02/03 목록은 PM-2.1의 같은 모델 1~3호기와 실제 assets의 호기 명칭을 연결한다. 별도 물리 장비 모델 인증을 수행했다는 뜻은 아니다. 간격 2,000h·허용 오차 10%·SOP-PM-21/22/23과 패키지 순서는 원문과 맞는다.

- 2,000h: 씰 키트 1개와 리턴 필터 엘리먼트 1개.
- 4,000h: 동일한 두 부품과 수량을 상속한다. 작동유 **샘플 분석**을 작동유 교환이나 추가 오일 출고로 바꾸지 않는다.
- 8,000h: 위 두 부품을 상속하고 작동유 교환을 포함한다. 작동유의 실제 part_no와 수량은 모두 null이며 연결 미상 사유를 보존한다.

`P-RTN-FLT`는 정책에서 명시한 필터 연결 식별자이며 실제 ERP master/재고에 존재한다는 증거가 아니다. 정책이 원문 부품을 명시하는 것과 업무 시스템이 그 부품을 보유·예약할 수 있다는 사실은 구별한다. 현재 4,000h 차례는 오일 교환이 아니므로 작동유 번호·교환 수량 미상이 이번 HYD-02 실행의 직접 차단 사유는 아니다.

`maintenance_policy.service`는 경보 cycle=1을 패키지 차례로 쓰지 않는다. 실제 total=11,950/since=1,950에서 마지막 정비 누적 10,000·다음 12,000·정비 차례 6·4,000h/SOP-PM-22를 산출한다. 조기·지연 정비로 마지막 누적 시간이 간격에 맞지 않으면 검증된 service_position 이력 없이 위상을 추정하지 않고 거절한다. `scope`는 실제 전체 CMMS 행·ERP 재고, 동일 모델 목록, 두 설비의 하한·목표 상한·공통 창, 패키지별 전체 부품 합계를 검사한다. `decide.pm_context`의 두 GET은 asset 필터가 없는 주소이며 실제 전체 행을 읽는 계약이다. 승인 때 재조회하고 실행 때 `maintenance_plan.recheck`로 승인 계획과 다시 대조한다. 앞서 발견한 고정 패키지/단일 설비 구현을 그대로 성공 처리하는 계약은 유지하지 않는다.

이 읽기 범위에서 최신 정책 준비본에 추가 중대한 원문 왜곡을 발견하지 않았다. 현재 준비 preflight는 HM technical_ready=true/issue 0, PM false/기존 정본 Action·InputData 관련 3개다. 실제 `PM-02-reviewed-graph-issues.json`도 같은 3개를 보존하며 HM/PR 해당 파일은 issue 0이다. 이 파일의 PM 결과를 graph 검사 전체 0으로 보고하면 안 된다. 실제 정본 적용 후 다시 받은 preflight와 운영 실행 결과를 이 파일의 준비 단계 결과로 대신할 수 없다.

### 실제 B가 기다리는 사실과 완료 기준

최종 실라버스 XLSX의 **통합반 온라인 44H 102행을 read_only로 직접 읽었다**. 요구는 승인 후 오더·생산 공지·종료이며, `DECISIONS.md` 결정 112와 `NOW.md`의 고정 흐름도 같다. 물리 정비·시운전·계수기 초기화를 B 완료 조건으로 추가할 근거는 없다. 다만 선택한 원문 업무 절차의 부품 의무를 없애는 근거도 아니다.

| 선택 | 원문 업무 의무와 실제 상태 | 현 자료의 판정 |
|---|---|---|
| PM-11 | 이번 차례 오더·생산 공지·씰/필터 출고 예약. HYD-02의 4,000h 차례도 필터 1개 포함 | 실제 필터 master/가용 재고 미상으로 원문 준수 실행 불가 |
| PM-12 | 이번 차례 오더·즉시 정지 공지·씰/필터 출고. 현장 정지를 임의 PLC 권한으로 바꿀 수 없음 | 같은 필터 부족으로 대안이 되지 않음. 예약과 실제 출고도 동일한 완료 사실이 아님 |
| PM-13 | 이미 있는 PM 오더를 그다음 허용 창으로 이동 | plannedWO=null이며 다음 창 2,226.18h로 2,200h 상한 초과. 새 오더/이번 창으로 대체 불가 |
| PM-14 | 같은 모델·하한 이상인 두 설비에 이번 창 오더, 인력 4명과 씰 2개 확보. 기본 패키지 필터 범위도 상속 | 실제 씰 가용 1개로 제외되며 필터도 미상. 묶음 문장에 필터가 다시 적히지 않았다고 패키지 부품을 제거할 수 없음 |

`PM-full-business-source-read.json`의 실제 SQL parts/stock과 ERP GET에는 씰·팬 베어링·쿨러 코어 3종만 있다. 필터 master/재고 행과 오일 mapping은 없다. `PM-actual-policy-scope-validation.json`은 persistentWrites=0, 다음 12,000h/4,000h를 정확히 반환하면서 필터 available=null/verified=false, executionReady=false와 구체적인 차단 사유를 보존한다. 검사 실패를 해소됐다고 표시하지 않는다.

필터를 미예약한 4,000h 오더만 만드는 것은 **부분 작업 또는 보류 상태**로 기록할 수 있지만, 고정 B를 원문 준수 성공으로 종결한 증거가 될 수 없다. 원문에는 필터 없이 성공 종결하는 별도 업무 종료가 없다. 현재 source와 실제 snapshot을 유지한다면 B는 필요한 사실을 기다려야 한다. 이 판정은 인위적으로 성공 데이터를 넣거나 물리 정비 흐름을 추가하라는 제안이 아니다.

이번 단독 시행에 실제로 필요한 추가 사실은 리턴 필터 엘리먼트의 ERP 정본 부품 연결과 가용 재고·예약 가능 상태다. 원문이 이미 수량 1개를 제공하므로 그 수량을 새로 추정하거나 사용자에게 다시 정하게 할 필요가 없다. 8,000h 차례의 작동유 번호·수량, 묶음 시행의 두 설비 부품·인력 확보는 해당 대안을 실제로 실행할 때 별도로 확인할 사항이다. 사실이 확보되면 실제 승인→올바른 차례의 오더 및 선택 절차의 부품 효과→생산 공지→자동 확인→결과 보고·종료를 검증해야 한다. 물리 정비 완료나 예약 미실행을 성공으로 보고해서는 안 된다.
