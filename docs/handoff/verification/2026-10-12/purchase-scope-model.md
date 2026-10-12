# 원문 기반 구매 SOP 영역 모델 — 2026-10-12

후속 기준5747907(기존2381pass/24skip 검증 커밋 이후). 사용자 위임 검토의 실제 기록과 적재는 루트 소유다. 이 구현은 원문/제안/seed를 수정하거나 실제 graph에 쓰지 않는다.

기존 Skill/Step/Part/Action/System/Role와 관계를 유지한다. `Skill.scope=purchase`를 명시할 때만 FM 없는 원문 구매 절차를 수용한다. `parts`는 기존Part id의 명시 범위이고 Skill→INVOLVES_PART→Part를 만든다. `executable`은 Boolean을 명시한다. false는 참고 보관이며 runtime 후보가 아니다. true는 PR_CREATE-only·구매 승인 역할·실제 공급사와 해당Part의 SUPPLIED_BY를 검증한다. 시스템은 sys:erp로 고정한다. 원문/단계/인용은 필수이고 일반 관리자 직접 생성 경로에는 예외를 주지 않는다.

scope 없는 기존 고장 조치는 FM 필수와 기존 물리/정비 계약을 유지한다. 구매에 고장 연결/명령/정비 작업지시/대상원인을 붙이지 않는다. 구매 후보 Rule 출력은 실행 가능한 구매SOP이고 SPARE_BELOW_MIN을 명시해야 한다. 참고SOP를 실행Rule 출력으로 가리키면 issue다.

읽기/실행 계약은 신규 명시 `evaluate_purchase(asset,part_no)`와 `submit_purchase(asset,part_no,incident,...)`로 분리한다. 실제 ERP 부족부품과 Part 범위가 근거이며 Cause/FM을 지어내거나 기존 evaluate_cards의 필수 원인 계약을 nullable로 바꾸지 않는다. 공급사 자료는 실제 part_quotes/quote_rows와 graph SUPPLIED_BY를 사용하며 레거시 scm_suppliers의0을 전체견적 부재로 오판하지 않는다.

보관 기계검사 `technical_ready`와 절차별 실행 상태 `execution`/`executable_ready`를 구분한다. 원문에 없는 공급사·Part·Role·Action은 추정하지 않고 issues로 남긴다. 사람이름 사칭/가짜 검토기록은 만들지 않는다. PR13을 참고 절차로 숨기거나 원문 세 부품을 현재 C의 펌프 씰 하나로 축소하지 않는다.

`link.supplier_policy`는 `oem`/`lowest_approved`/`fastest_quote` 중 명시 선택한다. 정책형 PR_CREATE의 value는 null이며 고정 공급사 값과 동시 입력을 거부한다. 정책 없는 기존 fixed Supplier 경로는 유지한다. 실행 불가능한 참고 절차는 정책과 실행 Action을 갖지 않는다.

oem은 기존 SCM 원천의 정확한 정본 라벨 `B-OEM (순정)`을 사용한다. 새 제조사 분류나 가짜 필드를 만들지 않는다. lowest_approved는 비순정·AVL 승인 견적 중 최저가, fastest_quote는 전체 견적 중 최단 납기를 먼저 선택하고 이후 AVL 규정을 검사한다. 동률·견적 누락·잘못된 수치·없는 공급 관계는 오류이며 원문에 없는 선택 순서를 추정하지 않는다. 고정 Supplier가 아닌 정책을 모든 원문 Part에 보관하고, 실제 요청 Part의 견적과 SUPPLIED_BY 관계에서 실행값을 계산한다.

계산 결과의 `resolvedSupplier`는 실제 supplier id, 원문 정책, Part/partNo, 선택 견적, 전체 견적집합, 원본 분류 라벨을 보존한다. 결과 Action.value에 선택 supplier를 바인딩하지만 저장 SOP는 변경하지 않는다. preview/final assess는 실제 Part와 ERP 사실을 다시 읽어 같은 pure 정책을 실행한다. 정책·선택 공급사·견적 근거 변경은 새 검토를 요구한다. 실제 ERP 발주 값 확정도 카드의 Part/공급사/전체 견적집합과 현재 견적 일치를 검증한다. 이 계산은 승인 또는 발주 성공을 뜻하지 않는다.

기본 범위 묶음 `purchase-model-stable.log`: 304 passed, 5 warnings, 37.85초. 정책 최초 시험 `purchase-policy-first.log`: 신규 시험이 null인 graph property의 생략을 KeyError로 처리하여 1 failed/39 passed. 실제 Neo4j null 속성 생략 계약에 맞춰 시험의 `.get('value')`로 교정했으며 생산 코드 검증을 완화하지 않았다. `purchase-policy-second.log`: 92 passed, 4 warnings. 정책·동률·AVL·견적 변경·Part3개·실제 preview/assess 경로·old reference 카드 거절 추가 후 `purchase-policy-approval.log`: 18 passed. 큰 묶음 최종 결과는 후속 기록한다.

기본+동적 모델 큰 묶음 `purchase-policy-wide.log`: 326 passed, 5 warnings, 46.97초. 기존 고장/DMN/실행/원문 검토/스키마와 새 구매 UI를 함께 검사했다. 실제 서비스 배포·원문 위임 검토·실제 적재·새 실행의 증거는 루트가 별도로 기록한다. 이 시험 결과를 실제 구매 완료로 표시하지 않는다.

승인·예측·가드레일·검토 회귀 추가 묶음 `purchase-policy-approval-regression.log`: 143 passed, 91.71초. 기존 승인 기대·golden을 바꾸지 않았다. `git diff --check` 오류 없음.
