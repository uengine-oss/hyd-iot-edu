# B actual stock lineage — read-only evidence, 2026-10-12

현재 B의 시행안이 막히는 이유는 기존 ERP 사실을 놓친 조회가 아니라 **원문 패키지에 필요한 ERP 품목·재고 데이터의 부재**다. 현재 부품 마스터와 재고 표 모두 세 품목뿐이다. `P-RTN-FLT`는 그래프의 Part/정책 연결에는 있으나 실제 ERP master와 stock에는 없다. 작동유에 해당하는 다른 품목 이름·번호도 없다. 미등록을 재고 0이나 가용으로 바꾸지 않았다.

## 실제 읽기와 경계

`read_actual.py`, `read_catalog.py`, `project_lineage.py`는 소스를 먼저 확인한 기존 GET 경로만 사용했다. 각 실제 응답은 이 디렉터리에 원문 바이트로 보관했고 URL/시간/status/SHA는 세 manifest에 남겼다. 첫 Fabric 호출은 limit=100으로 기존 1~20 제한을 초과해 400을 받았다. `common/hydcommon/fabric.py:SAMPLE_MAX=20`에 맞춰 limit=20으로 읽었으며 세 표 모두 반환 행 수가 제한보다 작아 미표시 추가 행이 없다. 업무 변경·초기화·MCP 호출·모델 실행·재평가·DB 직접 연결은 하지 않았다.

| 실제 원천 | 전체 관찰 |
|---|---|
| `/erp/spare_stock` | P-CLR-CORE, P-FAN-BRG, P-PMP-SEAL 세 행 |
| Fabric `ent.parts` | 같은 세 품목, row_count=3 < row_limit=20 |
| Fabric `ent.spare_stock` | 같은 세 품목, row_count=3 < row_limit=20 |
| 씰 키트 | on_hand=9, reserved=2, on_order=0, available=7 |
| 리턴 필터 | master 행 없음, stock 행 없음; 수량은 unknown |
| 작동유 | master/stock에 해당 품목·대체 별칭 없음 |
| Fabric `ent.task_standards` | 쿨러 두 절차, 씰 교체, 베어링 교체만 있음; 필터·작동유 연결 없음 |

`actual-B-case.json`은 기존 B instance RUNNING/current agent PENDING과 마지막 보류 영수증을 그대로 보존한다. `actual-B-package-lineage.json`은 그 마지막 실제 평가의 네 카드와 진단을 투영했으며 재평가 결과가 아니다. 과거 보류의 `WO_RESCHEDULE` 예측 오류는 역사적 기록이다. 이미 수정된 예측 경로를 다시 실행하지 않았다.

## 원문 → 실제 차례 → 필요 자재

실제 원문 GET의 source id는 `manual:6c306bfa-7ac2-46a0-b48c-3402a995ab57:2a757bd43772774a3b85c99779b3acef501f8d4dbc2cdbf9f851394ba841ae4a`이고 filename은 PM-02_powerpack-pm-checklist.md다. `PM-02-original-source-GET.json`에 실제 페이지 텍스트가 남아 있다.

PM-2.2는 기본 패키지에 씰 키트 1개와 리턴 필터 1개를 요구한다. 4,000h는 두 부품을 그대로 상속하고 작동유 **샘플 분석**을 추가한다. 8,000h는 작동유 **교환**을 추가하지만 원문은 작동유의 실제 ERP 번호와 교환 수량을 명시하지 않는다. 샘플 분석을 교환/추가 출고로 바꿀 근거가 없다.

| 실제 설비 | 마지막 정비 후/누적 | 실제 다음 차례 | 이번 필요 부품 |
|---|---|---|---|
| HYD-02 | 1,950 / 11,950h | 마지막 누적10,000, 다음12,000, 차례6, SOP-PM-22/4,000h | 씰1 + 필터1; 오일 교환 없음 |
| HYD-03 | 1,880 / 7,880h | 마지막 누적6,000, 다음8,000, 차례4, SOP-PM-23/8,000h | 씰1 + 필터1 + 작동유(번호·양 unknown) |

단독 예정/즉시안은 필터 미확인으로 제외된다. 묶음안은 필터 두 개 합계와 작동유 연결·수량이 모두 필요하다. 씰 두 개는 현재 available=7로 충족한다. 묶음 인력은 4명 요구/현재2명이며 원문은 비용 감점·인력 조정을 요구한다. 단독 실행을 위해 묶음의 작동유 요건을 충족할 필요는 없다.

현재 전체 CMMS GET에서 HYD-02의 following 시점 운전시간은 2,226.47h로 2,200h 상한보다 높다. 예측 도구가 읽기에 성공해도 현재 연기 시간 자체가 원문 허용 범위 밖인 사실은 남는다. 이것은 현재 GET 값의 비교이며 새 카드 평가/승인 결과가 아니다.

## 조회·소비 계약의 연결

- `it/agent/agentsvc/decide.py:pm_context`: CMMS 전체 행과 ERP 전체 재고 두 GET, asset query를 붙이지 않음.
- `it/agent/agentsvc/tools/mcp_ent.py:fetch`: endpoint의 literal `{asset}`만 치환. `/erp/spare_stock`에 HYD-02 같은 부품 필터를 잘못 붙이지 않음.
- `it/enterprise-sim/entsim/main.py` → `supabase_backend.py` → `ent.spare_stock_read(p_part)`: part 미지정은 null이고 `where part_no=p_part or p_part is null`로 모든 재고 행을 반환.
- `common/hydcommon/maintenance_policy.py:service/scope`: 실제 카운터로 패키지를 정하고 required.part_no의 정확한 ERP 행을 찾음. 행 없음/번호·수량 미상은 `verified=false`, availability null로 보존. 이름 유사성으로 다른 부품을 대체하지 않음.
- `it/neo4j/v2/scenario_structure.cypher`는 필터 Part/partNo 연결만 만든다. ERP master/stock을 보유했다는 증거가 아니다. SQL seed/migrations의 parts·spare_stock 삽입은 실제 관찰한 세 품목만 준비한다. 조사 범위에서 필터나 작동유 공급 seed를 발견하지 못했다.

따라서 변경 제안의 대상은 조회 fallback이나 소비자의 unknown→0 변환이 아니라 검증 가능한 업무 데이터 준비다. 제품 소스는 수정하지 않았다.

## 기존 학생 화면에서 확인할 위치와 최소 후속 준비

`데이터 패브릭 → 원천과 표 → 업무 DB → parts / spare_stock / task_standards`에서 같은 실제 DB의 마스터·수량을 읽을 수 있다. Fabric 화면·API는 전용 reader이고 **업무 행을 쓰는 버튼이 없다**. `원문 읽기`에서 PM-02 원문/검토된 적용 정책과 부품 미상을 확인할 수 있다. DDL/원문 적재는 지식 연결을 적재하며 ERP 실물 수량을 자동 공급하지 않는다.

기존 C의 구매→입고는 기존 `ent.spare_stock` 행을 UPDATE한다. 신규 필터 master/stock 행을 만들어 주는 경로가 아니므로 C 재고 초기화나 씰 구매를 반복해도 필터가 생기지 않는다. `reset_spare_stock`도 기존 행의 base 값을 복원할 뿐 신규 행을 공급하지 않는다.

가장 작은 다음 준비는 HYD-02 단독 4,000h 안의 필터 근거를 확보하는 것이다: 검증한 ERP 품목 번호/이름(현재 정책 연결 P-RTN-FLT와 일치하는지), 실제 실물·예약·입고 예정 수량, 가용 수량, ERP 필수 재주문점/목표/기준값 및 표준단가의 업무 출처가 필요하다. 예정안은 최소 필터1개 가용 예약, 즉시안은 최소 실물−예약1개 출고를 충족해야 한다. **최소 요구량은 실제 보유량을 입력해도 된다는 근거가 아니다.** 임의로 수량1이나 가격을 만들어 넣는 SQL은 준비하지 않았다.

묶음까지 실행하려면 필터 합계2개와 추가 작동유의 실제 품목 번호·교환량·단위·가용 수량을 원문 보완/업무 BOM에 근거해 연결하고 인력 조정을 확인해야 한다. 현재 단독안에 이 추가 요구를 얹지 않는다. 원문 정책과 업무 사실이 준비된 후에만 실제 기존 B 재평가→사람 승인→정비 오더/생산 공지→종료의 별도 운영 검증이 가능하다. 현재 PENDING을 완료로 보고하지 않는다.
