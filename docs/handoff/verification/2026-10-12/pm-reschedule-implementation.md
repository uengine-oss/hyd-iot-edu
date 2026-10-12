# 원문 PM 일정 변경 capability — 2026-10-12

원문 PM13의 기존 오더 시간 이동을 빈 Action→새 WO_CREATE로 대체하던 경계를 수정했다. 원문·제안·기존 seed/golden은 바꾸지 않는다. 실제 원안 교정과 위임 검토 기록은 루트 소유다.

정본 `it/neo4j/v2/pm_capabilities.cypher`는 기존 Action/System/InputData 클래스에 WO_RESCHEDULE와 MES production_running 입력 자리만 추가한다. 실제 정비 오더·생산 사실·규칙은 생성하지 않는다. seed.sh와 ontology_v2 공식 적재 목록에 포함한다. 기존 운영 그래프에는 이 정본 capability 파일만 별도 공식 적용할 수 있으며 임시 raw 지식 패치나 과거 seed 재적재는 필요하지 않다.

추가 migration54는 pm_status_read에 이번 회차의 실제 existing_pm_order/pm_cycle를 부착한다. 기존 facts/records/log/settings/as_of 봉투는 유지한다. 일정 변경은 pm_counters.plan_wo에 연결된 기존 오더만 사용하고, 동일 asset·cycle·배정 상태·완료 미발생·승인 당시 전체 오더 스냅샷을 확인한다. 실제 그다음 창과 운전시간 허용 상한을 다시 읽고 row lock 및 멱등 키로 갱신한다. 새 오더를 발행하지 않는다. 오류는 SQL transaction으로 롤백된다. 메모리 어댑터도 같은 의미이며 저장 실패 시 새 효과·멱등 기록·감사 거래를 되돌린다. 이미 완료된 일정 변경의 무조건 역실행을 제공한다고 주장하지 않는다. 운영 정정은 기존 오더 상태와 기한을 다시 검토한 새 일정 변경이다.

source-backed PM 후보는 maintenancePlan에 실제 효과와 목표 창을 보관한다. 기존 오더·그다음 창·기한이 미상/초과하면 execution:pm-plan EXCLUDE로 해당 대안을 불가로 남긴다. 빈 Action을 새 오더로 바꾸지 않는다. 명시 STOP+WO_CREATE인 즉시 정비는 control 종류를 유지하며 즉시 창을 명시한다. 원문 참고 절차는 별도 reference 모델로 실행에서 제외한다. A의 기존 process-definition-followup 계약은 보존한다.

승인 preview/final assess는 같은 pure 경로를 다시 계산하고 maintenancePlan 변경을 검토 변경으로 거부한다. 승인 전달에서 WO_RESCHEDULE은 실제 흐름의 CMMS 단계까지 지연한다. 실행은 승인한 기존 ref/스냅샷/목표 창에서만 인자를 만들고 SQL이 실제 상태와 기한을 다시 검증한다. 기존 B의 Task stage와 승인 횟수는 추가하지 않는다.

생산 감점 입력 production_running은 실제 MES records의 현재 asset/RUNNING 상태를 읽는다. missing/malformed 상태를 거짓으로 바꾸지 않는다. 기존 order_due_h와 함께 원문 PM2.5의 납기24시간·생산 중·즉시 정지 감점80 규칙을 명시적으로 연결할 수 있다. 실제 규칙의 원문 anchor와 감점 지표에 대한 위임 판단은 루트 검토 기록에 남겨야 한다. 입력 자리 추가만으로 누락 규칙이 자동 적용되었다고 주장하지 않는다.

실제 원천 증거 `D:/work/study/hyd-iot-edu/.evidence/delegated-review-20261012/PM-business-facts-read.json`: 이번 PM 계획의 pm_planned_wo/window/at는 null이다. 기존 즉시 펌프 씰 오더를 대신 재사용하지 않는다. 실제 following 창은 존재하지만 그때 운전시간은 허용 상한을 넘는다. 현재 MES 생산 오더는 RUNNING이고 납기는24시간 이내다. 따라서 현재 원천에서 일정 변경 대안은 불가로 남으며 생산 조건의 원문 감점은 실제 입력 근거가 있다.

첫 회귀는 신규 capability의 정정 사유가 process effect_compensation에 빠져 기존 일치 시험1개가 실패했다. 생산 코드 양쪽의 같은 사유를 연결했고 기대를 완화하지 않았다. 후속158 passed/7 skipped. 다음 신규 입력 시험6개는 sourceKind/name/sourceName을 빠뜨린 fixture 계약 오류였으며 실제 InputData DTO로 fixture를 고쳐 기존 요구를 보존했다. 최종 큰 묶음·실제 독립 PG 결과는 후속 기록한다.

tests/test_pm_reschedule_pg.py는 HYD_PM_PG_DSN이 명시된 독립 seeded 데이터베이스에서만 실행한다. 각 시험은 migration/임시 fixture/거래를 전체 rollback한다. 실제 운영 DSN 연결·DB 쓰기·배포는 루트만 수행한다. 파이프 입력이 필요한 경우 OutputEncoding=UTF-8 및 PYTHONUTF8=1을 함께 사용하며 문서 한글을 UTF-8로 확인했다.

최종 큰 묶음 `pm-contract-wide.log`: 361 passed, 19 skipped, 5 warnings, 27.15초. 이 중 실제 독립 PG 일정 변경 시험6개는 명시 DSN이 없어 skip했다. 메모리 계약·source-backed 후보·기존 DMN/정비/구매·원문/API·스키마 회귀는 통과했다. 실제 PG·배포·현재 처리 건 실행 결과는 루트의 별도 증거로 확정한다.

루트 후속 실제 PostgreSQL 검증: 독립55322 DB에서 `tests/test_pm_reschedule_pg.py` **6 passed, 1.00초, exit0**. 로그/XML은 `delegated-review-20261012/pytest-pm-pg.log/xml`이다. 정상 기존 오더 갱신·같은 요청 멱등·오더 미상·이전 스냅숏 불일치·기한 초과·창 불일치·회차 불일치의 원자성을 확인했고 각 시험 변경은 모두 rollback했다. 운영54322에는 이 시험을 연결하지 않았다. 앞선 6skip은 당시 기록으로 유지한다.
