# B 공식 초기 ERP 보완 명세 — B-ERP-20261012-v1

2026-10-12 사용자 답변으로 외부 실제 재고 자료가 없다는 점을 확인했다. 이 저장소의 `it/supabase/seed.sql`과 `entsim/data.py`는 처음부터 교육용 가상 기업의 공식 실습 데이터를 정의한다. 필터 결손을 외부 현실 자료 제공 조건으로 분류한 앞선 보고는 정정한다. 실제 운영 저장 행을 고치거나 보류 사례를 성공 사례로 바꾸는 작업이 아니라, 공식 **초기 실습 데이터**의 빠진 품목을 두 백엔드에 동일하게 보완한다.

## 결함과 배선

원문 PM-02 §2.2는 2,000h 패키지에 씰 키트1 + 리턴 필터1을 요구하고, 4,000h는 같은 부품 범위를 상속한다. `maintenance_policy.service`는 HYD-02 total=11,950/since=1,950에서 다음12,000h/SOP-PM-22/4,000h를 선택한다. `scope`는 패키지의 정확한 part_no와 ERP 재고를 대조하며 없으면 unknown으로 거절한다. 현재 공식 seed는 씰·베어링·쿨러만 공급하고 필터를 빠뜨렸다. 그래프의 `Part.partNo=P-RTN-FLT` 연결은 ERP 재고 초기화가 아니다.

Memory: `data.SPARE_BASE` → 새 `EnterpriseState`의 `_c2_defaults` → `spare_stock` → `decide.pm_context` → `maintenance_policy.scope` → 평가·승인 재확인·실행.

Supabase: `seed.sql` / 신규 057 migration의 없는 master·stock 행 삽입 → `ent.spare_stock_read(NULL)` → enterprise 전체 GET → 같은 `pm_context/scope` 소비자.

## 공식 교육용 설계값

아래 값의 출처는 이 명세 **B-ERP-20261012-v1**이다. 현실 창고 재고, 제조사 원문, 가격 견적이라고 주장하지 않는다. 금액 단위는 기존 데이터와 같은 만 원이다. 기존 A/C 설계값은 변경하지 않는다.

| 필드 | 설계값 | 선택 근거 |
|---|---|---|
| part_no / name | P-RTN-FLT / 리턴 필터 엘리먼트 | 이미 원문 검토 정책·공식 그래프에서 사용하는 연결 |
| std_price | 12 | 공식 가상 필터 단가. 기존 씰50·베어링25·쿨러250과 구별되는 교육용 비용; 시장/원문 가격 아님 |
| on_hand / reserved / on_order | 2 / 0 / 0 | 필터1개 단독안 후1개가 남는 최소 두 단위 재고. 예약·발주로 가용을 부풀리지 않음 |
| reorder_point / target_stock | 1 / 2 | 초기available2는 경보를 만들지 않음. 단독예약 후1은 기준과 같고, 추가 소모 시 부족 상태를 드러냄 |
| base_on_hand / base_reserved | 2 / 0 | 새 실습/명시적 수업 초기화의 같은 기준값 |
| reserved_for | HYD-02 | B의 기본 실습 대상. reserved=0이므로 실제 선예약으로 해석하지 않음 |
| need_by_days / below_since | null / null | 새로운 납기·결품 경과 사실을 발명하지 않음 |

기존 C 씰 초기 실물3/예약2/가용1/기준2/목표7은 그대로 둔다. C 구매 공급사·견적·기존 재고·발주·예약·입고 이력도 바꾸지 않는다. 새 필터는 초기 below_reorder=false이고 C의 초기 씰 부족 시나리오를 대신하지 않는다. 필터 구매 견적은 추가하지 않는다.

## 변경과 충돌 보호

소유 파일은 data.py, seed.sql, 신규 `20261012000057_b_return_filter_fixture.sql`, 이 명세와 별도 증거뿐이다. `_STD_PRICE`와 `SPARE_BASE`에 품목을 추가한다. seed와 migration은 같은 master/stock 행에 `ON CONFLICT (part_no) DO NOTHING`을 사용한다. 기존 표/함수/운영 행을 UPDATE하지 않는다. 기존 master가 있으면 그 이름·가격을 유지하며 stock이 있으면 실물·예약·발주·기준·시간을 모두 유지한다. 반복 적용으로 변하지 않는다.

Memory의 새 상태와 명시적인 reset은 SPARE_BASE를 사용한다. root가 state.py의 초기화 위치 소유권을 추가 허용했다. 저장된 spare_stock dict에서도 품목별 `setdefault`로 없는 초기 행만 추가하여 SQL migration과 동등하게 만들고, 존재하는 행·예약·발주·카운터는 덮어쓰지 않는다. 현재 살아 있는 사례/서비스의 저장 상태를 직접 수정하지 않는다.

## 수용 기준과 남는 비해피 분기

수정 전 공식 초기 data/seed에서 필터 결손을 독립 증거로 재현한다. 다른 에이전트가 새 검증 테스트를 소유하며 기존 기대값을 약화시키지 않는다. Memory/Supabase 초기 품목·재고 값은 일치하고, 신규 migration 두 번 적용/기존 필터 행 보유 시 충돌 보호를 검사한다.

초기 B HYD-02 단독4,000h의 씰1·필터1 범위는 기존 초기 씰available1과 새 필터available2로 확인 가능해야 한다. 부족·예약으로 가용을 소진하거나 필터 행을 제거하면 계속 불가해야 한다. staff, 허용시간, 운전시간 위상, 실행 전 재확인은 그대로다. 이것은 데이터 배선 수용이며 실제 승인·WO·공지·종료 성공을 대신하지 않는다.

묶음의 HYD-03은 total7,880/since1,880 → 다음8,000h/SOP-PM-23다. 작동유 번호·양·단위는 원문에서 미상이고 이번 작업에서 채우지 않는다. 묶음의 인원4/가용2, 씰 초기available1<합계2, 허용 상한 밖 연기 등 기존 비해피 조건도 유지한다.

실제 DB/서비스에 적용, LIVE 쓰기, 워커/모델 실행, 기존 실제 B 사례 수정, 커밋/스테이징은 이 작업의 범위 밖이다.

## 독립 검증 결과

별도 에이전트가 신규 `tests/test_education_pm_inventory_fixture.py`를 작성·실행했다. 관련 12개가 0.89초에 통과했다. 새 Memory 초기 상태와 기존 저장 상태 재개, 초기 C 씰 부족 유지, 단독4,000h의 실제 production planner, 필터 없음·부족·기존 예약, 묶음8,000h 작동유 미상, 상한 밖 연기를 검사했다. 기존 기대값은 수정하지 않았다.

root가 제공한 폐기 가능한 PostgreSQL15에서 실제 ent 마이그레이션17개와 enterprise seed를 bootstrap한 뒤, 동일한 production 소비·예약·멱등 실행 및 신규057 두 번 적용/기존 행 전체 보존도 확인했다. 별도 SQLite SQL 검사만으로 PostgreSQL 확인을 대신하지 않았다. 모든 테스트 업무 변경 트랜잭션은 rollback했고 공유/운영 DB에는 적용하지 않았다. 가까운 기존 PostgreSQL 통합 검사1개도 0.46초에 통과했다.

필터 행을 의도적으로 제거한 변이는 원래 단독4,000h 정상 수용 검사를 `ScopeError`로 실패시켰다(예상 실패1개, 0.15초). unknown을 0/성공으로 바꿔 검사를 통과시키지 않았다. 실제 원문 정책 SHA와 네 제품 파일 SHA는 검사 전후 같았다.

독립 원문 로그·bootstrap·SHA·결과: `.evidence/education-fixture-correction-20261012/b-verification/`. 구현 전 결손과 기존 A/C 값 보존 증거: 같은 갈래 `b-data/before.json`, `b-data/result.json`. 운영 B의 실제 승인/WO/공지/종료 검증과 운영 DB 적용은 아직 수행하지 않았으며 데이터·소비 배선 검증으로 완료를 주장하지 않는다. 일회용 PostgreSQL의 정리는 root 소유다.

## 직접 검토한 참고 구현

- 최신 캐시 ProcessGPT `6ad9db604898efa2c16fa2e364d7317a93a3ee87`의 `docs/en/architecture.md`를 직접 읽었다. 영속 업무 프로세스/작업과 도구 호출은 별도 고리다. 이번 수정도 업무 초기 행을 공급하며 에이전트의 성공 응답이나 완료 이벤트를 조작하지 않는다.
- 최신 캐시 ontology-studio `6a229be8dcce2aeb533ecdba360b5b4564ffb777`의 `frontend/src/features/files/FilePanel.vue`를 직접 읽었다. uploadedFiles와 outputFiles를 구분하고 파일 이름/크기/다운로드를 보존한다. 이번 데이터 보완을 업로드 원문이나 실제 출력 파일로 사칭하지 않는다. 아래 제조 예제는 이전 설치본 캐시에서 직접 검토한 별도 참고이며 최신 캐시에 같은 tutorial이 있다고 주장하지 않는다.
- ProcessGPT 모노레포 cached `process-gpt/README.md`의 업무 프로세스별 작업·에이전트 계약을 직접 검토했다. Vue `supabase/seed.sql`은 현재 비어 있는 placeholder임을 확인했으며 이를 ERP 초기값의 출처로 사용하지 않는다. HYD 가상 ERP의 seed 보완은 자체 도메인 계약이며 ProcessGPT의 프로세스 런타임 변경을 요구하지 않는다.
- ontology-studio `desktop/resources/tutorial/manufacturing/README.md`는 사용자가 자료를 준비하지 않아도 실습할 수 있도록 설치본에 공식 교육 예제를 배포한다. `procedures/FN_CHECK_BOM_SHORTAGE.sql`은 BOM 요구량과 실제 가용을 구분하는 참고다. 공식 실습 자료 공급과 원문/현실 사실의 구분을 유지한다.
- ontology-studio `backend/src/shared/kernel/mcp_client.py:_unwrap`의 structured/text MCP 봉투 소비도 직접 확인했다. 이 수정은 이미 정상인 조회·봉투·unknown 소비자 대신 초기 데이터의 결손 고리를 고친다.
