# C1 지식 — 시드 두 판 · 문서 적재 확장 · 시나리오 문서 (확정 TODO C1)

작성 2026-10-09(B 추가 같은 날). 근거: `TODO.md` 확정 TODO C(원칙 · 결정 1 · 2 · 6 · 7), `scenario-research.md` §2.1 · §2.2 · §5 · §10.1(K1~K7),
`docs/보고서/2026-10-09_HYD_시나리오_3개.md`(A · B · C 확정본), `scenario-selection.md` §4.B, 사용자 결정 2026-10-09(PREVENTED_BY 추가 · B 정기 정비 확정 · 승인 1회).
증거: `.evidence/a161-c1/`(A · C), `.evidence/c1-b/`(B · 관계 추가, 명령 `COMMANDS.txt`). HANDOFF · TODO · DECISIONS는 고치지 않았다(메인 세션이 합친다).

## 0. B 추가분 요약 (2026-10-09 후반)

| 일 | 무엇 | 파일 |
|---|---|---|
| 관계 하나 추가 (별도 커밋) | `(:FailureMode)-[:PREVENTED_BY {_manual_document}]->(:Skill)` N:M, "예방 조치 — 고장 유형을 미리 막는 정기 정비"(준용 EN 13306 · ISO 14224). 스킬 필수 조건을 `MITIGATED_BY\|REMEDIED_BY\|PREVENTED_BY`로 넓힘. 이름 바꾸기 · 지우기 없음. schema 2.6.0 | `schema.json`, 생성 파일(`schema_prompt.md` · `ontology-schema.ttl` · `ontology-classes.svg`), `seed_checks.cypher`, `schema-v2.md`, `queries.cypher`, `t3_skills.cypher`, `seed.sh` 요약 줄 |
| 관계 목록 한 곳 | `kgadmin.FAILURE_RELATIONS`(세 관계) · `CORRECTIVE_RELATIONS`(경보 대응 두 관계). 검토 · 적재 · 스킬 편집 · 추출 계약이 따른다. 예방 조치 스킬은 경보 대응 후보 규칙(A075 자동 연결 · t2 템플릿)에 들어가지 않는다 | `kgadmin.py`, `manual_knowledge.py`, `manual_graph.py`, `skill_graph.py`, `manual_extraction.py`, `main.py`, 포털 `enterprise.js`(관계 이름표 1줄 · 지도 따라가기 1줄) |
| B 구조(두 판 공통, 추가만) | 감시 규칙 `pattern:pm-due`(PM_DUE, TESTS `in:hours-since-pm >= 1950 h`, 출처 sys:cmms, 증상 없음), 판단 입력 `in:hours-since-pm`(후보) · `in:next-scheduled-time`(이번 예정된 정비 시간의 운전시간) · `in:hours-if-deferred`(그다음 정비 시간의 운전시간) · `in:pm-crew` · `in:spare-available`(CMMS 자재 키트) + 기존 `in:order-due`(규정 검토에 선언), 부품 `part:return-filter`, 출처 `ks:pm-plan` | `scenario_structure.cypher` |
| B 문서 | `PM-02_powerpack-pm-checklist.md` — OEM 형식 정기 점검표: 2,000 · 4,000 · 8,000 h 패키지 표, 허용 오차 ±10 %(1,800~2,200 h, 회사 설정), 도래 알림 1,950 h, 시행 방식 SOP-PM-11~14(이번 정비 시간 단독 · 지금 정지 · 미루기 · 두 대 묶기), 패키지 SOP-PM-21~23(LOTO · 잔압 해제 · 0 bar 확인 · 씰 키트 · 리턴 필터), 시운전 기준(PS1 ≥ 178 · FS1 ≥ 8.8 · VS1 < 1.2, 15분), 막는 고장(체적 효율 저하 · 씰 마모 0.7 · 작동유 오염 0.3) | `docs/samples/` |
| B 적재 결과 | 고장 유형 1 · 원인 2 · 증거 2 · 규칙 9(진단 1 · 후보 1 · 규정 7), 스킬 7개 모두 PREVENTED_BY. 주기 · 허용 오차 · 생산 · 인원 · 부품 기준은 모두 TESTS 관계 | 시험 대역 `tests/c1_fixtures.py` B_KNOWLEDGE · B_LINKS |
| 경쟁(해피패스 아님) | 판단 엔진(`agentsvc.cards.evaluate` + 시드 순위 정책 `rule:rank-value`)으로 순위 확인. 아래 4절 표 | `tests/test_c1_scenario_b.py`, `scripts/probe_c1_knowledge.py` |
| 승인 1회 · 단어 정리 | HM-8: SOP-COOL-12 · 13 승인을 운전원으로(시나리오 A 승인자), "회복하지 않으면 생산관리자가 확인" → "결과 보고에 미달로 적는다", "정비창" → "예정된 정비 시간". PR-07: 300만 원 초과는 "구매팀장 추가 승인" → "발주안에 전결 기준 초과 표시 · 결과 보고를 구매팀장에게도 보냄, 승인은 구매 담당 한 번" | `docs/samples/HM-8_*.md`, `PR-07_*.md` |
| C 경쟁 보강 | PR-7.4 총비용에 불량 1건 손실 250만 원(교육용) — 계산하면 B-OEM 360 < A정밀 390 < C트레이딩 570. 엔진이 공급사별 총비용을 아직 못 받으므로 문서의 "불량률 10 % 초과 공급사 → 전수 검사 비용 20만 원" 규칙(`rule:pur-inspection`, PENALTY)으로 A정밀이 실제로 진다 | `PR-07_*.md`, `c1_fixtures.py` |
| 구조판 결함 수정 | 회사 규정 `rule:avl`의 적용 대상(`skill:wo-pump-seal`)이 구조판에 없어 "모든 후보에 적용"으로 번졌고, 공급사가 없는 냉각 · 정비 카드가 전부 "승인 여부 모름 → 제외"됐다(라이브 판단에서 발견). 구조판 전용 문장 하나로 같은 규칙에 `skill_code == 'PR_CREATE'` 검사를 더해 구매 스킬에만 걸리게 함. 전체판은 그대로 | `scenario_structure.cypher` 끝(`// @edition structure`) |


**비유 한 줄**: 시드는 "빈 공장 도면 + 회사 규정집"만 주고, 고장 대처 지식은 학생이 매뉴얼을 읽혀서(적재) 채운다. 전체판은 "다 채워진 시험용 공장"이다.

## 1. 바뀐 것

| 일 | 무엇 | 파일 |
|---|---|---|
| 시드 두 판 | 시드 문장에 `// @edition full` 표시. 표시 문장은 전체판에서만 실행. 구조판 = 설비 구조 · 역할/조직/시스템 · BSC · 감시 패턴 · 회사 규정(`rule:ts1-hard` SR-04, `rule:avl` PR-07) · 순위 정책(`rule:rank-value`). 고장 유형 · 원인 · 증거 · 스킬/단계 · 매뉴얼 절(HM-*) · 매뉴얼 규칙 · 예측 · 선례 · 사건은 구조판에 없다 | `it/neo4j/v2/instances.cypher`(표시 18, 규칙 문장을 회사 규정 3 / 매뉴얼 규칙 18로 나눔), `knowledge_a098.cypher`(표시 9, 오일 증상 문장에서 INDICATES 분리), `it/neo4j/edition.sh`(bash 필터), `scripts/ontology_v2.py`(`edition_filter` · `edition_checks` · `load --edition`) |
| 판 고르기 | `SEED_EDITION=structure`(기본, 강의) / `full`(회귀). compose kg-seed 환경변수, `.env.example`, `docs/RUNBOOK.md` §0 | `it/neo4j/seed.sh`, `compose.yaml`, `.env.example`, `docs/RUNBOOK.md` |
| 되읽기 단언 | 판별 줄 표시. 결정 1(가): "pattern not linked to a failure mode"는 held · plc-trip 이거나 증상을 잇는 패턴에만 적용(재고 패턴 SPARE_BELOW_MIN 제외). 구조판은 "설비 패턴 → 증상" 단언 · 구조 레이블 목록. 선례 단언은 전체판만 | `it/neo4j/v2/seed_checks.cypher` |
| 시나리오 구조(두 판 공통, 추가만) | 구매 담당 `role:purchasing`(L1), 판단 입력 `in:spare-gap`(ERP) · `in:po-amount`(에이전트, REPRESENTS msr:part-cost) · `in:lead-slack-days`, `dec:compliance`가 `in:pattern` · `in:po-amount` · `in:lead-slack-days`를 REQUIRES_INPUT(+ task READS), 감시 패턴 `pattern:spare-below-min`(SPARE_BELOW_MIN, TESTS in:spare-gap < 0, detectionMode 없음 → 탐지기는 읽지 않음, ks:pr-07 근거) | `it/neo4j/v2/scenario_structure.cypher` |
| 추출 계약 2.0 | 제안에 선택 항목 `knowledge`(고장 유형 · 원인 · 증거 · 규칙)와 SOP별 `link`(고장 유형 · 관계 · 종류 · 승인 · 원자 조치 값 · 대상 원인 · 영향) 추가. 실행 입력에 `ontology_catalog`(기존 id 목록)를 고정해 넘김. 구간 추출 병합 · 인용 범위 · 좌표 이동 · 인용 범위율에 knowledge 포함 | `it/process/procsvc/manual_extraction.py`, `manual_segments.py` |
| 검토 → 적재 | 검토 본문에 `knowledge`, `links[SOP].actions` · `addresses`. 모양 · 범위 · 열거값 · 문서 안 참조 검사(`manual_knowledge.validate`), 적재 직전 그래프 검사(`check_graph`: Action 존재 · 명령 값 min~max · 명령은 control 스킬에만 · PR_CREATE 값=공급사 · WO_CREATE 값=SOP · 규칙 입력이 그 결정의 REQUIRES_INPUT · 입력 변수로 `when` 생성). 증거 SQL은 서버 틀 | `manual_knowledge.py`(새), `manual_review.py`, `manual_api.py` |
| 그래프 적재 | FailureMode · Cause · Evidence · Rule 노드와 OCCURS_IN · INDICATES · LEADS_TO · CAUSES · INVOLVES_PART · DISTURBS · EVIDENCED_BY · ADDRESSES · CONSISTS_OF · HAS_RULE · TESTS · OUTPUTS · APPLIES_TO · PENALIZES · DERIVED_FROM. **스키마 v2 무변경**: 새 레이블 · 관계에는 `_manual_document`를 붙이지 않고, 문서 소유를 적재 기록(ManualIngestionDocument.snapshot)으로 정한다. 옛 4레이블은 그대로 표시. 문서가 자기 후보 규칙을 냈으면 A075 자동 후보 연결을 하지 않음 | `manual_graph.py`, `manual_golden.py`(문서 지식 id를 적재 기록에서 읽음) |
| 문서 | A: `HM-8_cooler-fan-manual.md` 보강(HM-8.1 · 8.2 그대로 + 8.3 판정 기준 · 8.4 고장 · 원인 · 증거 · 8.5 즉시 완화 SOP-COOL-11~13 · 8.6 회복 · 8.7 근본 SOP-COOL-14 · 15 · 8.8 금지). B: `PM-02_powerpack-pm-checklist.md`(0절). C: `PR-07_spare-parts-standard.md`(중요 예비품 · 재주문점/목표 재고 · AVL · 공급사 비교(총비용 · 리드타임 · 불량률) · 금액 전결 300만 원 · 발주 SOP-PUR-11~13 · 입고 확인) | `docs/samples/` |
| 포털(최소) | 처리 과정 패널에 `ontology_catalog` 한국어 이름 · 종류별 개수, 추출 제안 요약에 지식 개수. 이것 없이는 영문 변수명이 보여 기존 시험(`test_u1_task_detail`)이 실패 | `it/portal/www/taskDetail.js` |
| 회귀 스크립트 | HM-8 보강으로 미리보기 기대값 2절 · 8단계 → 8절 · 7 SOP · 25단계, 모든 SOP 번호를 시험용으로 치환 | `scripts/scenario_test.py` |

시드 SOP 번호와 겹치지 않게 문서 A는 SOP-COOL-11~15를 쓴다(전체판 SOP-COOL-01~05).

## 2. 시드 판 바꾸는 법

- 강의(기본): `SEED_EDITION=structure` → `docker compose --profile knowledge up kg-seed`. 로그 `seed edition: structure`, `read-back: 16 checks, 0 failed`.
- 문서 적재 순서(구조판): **A(HM-8) → B(PM-02) → C(PR-07)**. C의 구매 SOP가 B가 만든 `fm:volumetric-loss` · `cause:pump-seal-wear`를 가리키므로 B 없이 C를 넣으면 409("대상이 없거나…"). A와 B는 서로 기대지 않는다.
- 회귀 · 통합 시험: `.env`에 `SEED_EDITION=full`, **새 neo4j 볼륨**에서 kg-seed. 로그 `read-back: 17 checks, 0 failed`.
- kg-seed는 MERGE만 하므로 지식이 든 볼륨을 structure로 다시 돌려도 지워지지 않는다(주 스택에 영향 없음). 호스트: `scripts/ontology_v2.py load --edition structure|full`.

## 3. 검토 화면용 API · 데이터 모양 (U 담당에게)

1. `GET /api/kg/manuals/catalog` (새) — 고르기 목록: `components` · `symptoms`(patterns) · `patterns` · `parts`(suppliers: price · failRate · leadDays · avl) · `suppliers` · `state_variables` · `measures` · `actions`(code · kind · param · min · max · target) · `roles`(level) · `decision_tables`(decision · inputs[id · variable · typeRef]) · `failure_modes` · `causes` · `skills` · `evidence_tags` · `rule_tables`(표별 허용 effect).
2. `POST /api/kg/manuals/sources/{id}/extractions` — 그대로. 서버가 catalog를 실행 입력 `ontology_catalog`로 고정한다.
3. `GET …/extractions/{instance}` → `preview`에 기존 필드 + `knowledge` + 절차마다 `link`(제안) + `knowledge_conflicts`([{id, label, owner: 'seed'|문서 id, kind}] — 같은 문서 재적재는 제외).
4. `POST /api/kg/manuals/commit` 본문 = 미리보기 + `links` + `knowledge` + `by` + `reviewed:true`(+ 에이전트 추출이면 `method`, `extraction`).
   - `links[SOP] = {failureMode, relation: MITIGATED_BY|REMEDIED_BY|PREVENTED_BY, kind: control|work_order, approver: role:…, affects:[{target, sign, note}], actions:[{action: action:…, value}], addresses:[cause:…]}` — 화면은 `preview.procedures[i].link`로 미리 채우고 사람이 고친다.
   - `knowledge = {failure_modes:[{id fm:…, name, component comp:…, symptoms[sym:…], leads_to[fm:…], section, anchor}], causes:[{id cause:…, name, aliases[], prior 0~1, failure_mode, parts[part:…], disturbs[{target sv:…, sign}], section, anchor}], evidence:[{id evd:…, cause, name, tag, aggregate avg|max|min|range, window_seconds 1~3600, expect lt|gt|gte, threshold, weight 0~1, section, anchor}], rules:[{id rule:…, table dt:diagnose-cause|dt:action-candidates|dt:compliance, effect, tests[{input in:…, operator, value, unit}], outputs[cause:…|SOP-…|skill:…], applies_to[SOP-…|skill:…], penalty, penalizes msr:…, order?, annotation, section, anchor}]}`. 이미 있는 id(충돌 목록)는 항목을 빼고 그 id를 참조한다.
   - 실패는 400(모양 · 그래프 검사, 이유 전부 ` / `로 연결) · 409(소유 충돌 · 판본 변경). 영수증에 `knowledge`(종류별 id) · `actions` 수가 붙는다.
5. 되돌리기 `POST /api/kg/manuals/batches/{batch}/rollback` 그대로. 다른 문서가 참조 중이면 409.

## 4. 시험 · 검증

- **B 추가 뒤(2026-10-09 후반)**: 전체 `pytest -q` **1754 passed, 4 skipped, 0 failed**(`.evidence/c1-b/pytest-full.txt`, 앞의 test_mcp_check 실패도 이번에는 통과). C1 묶음 72(`test_c1_scenario_b` 10 · `test_c1_knowledge` 36 · `test_seed_editions` 11 · `test_ontology_schema` 15). 라이브(버림 컨테이너 `c1kg-b-neo4j`, 17689, 검증 뒤 삭제) `probe_c1_knowledge.py` **37/37 PASS** — A → B → C 적재, B 판단 순위 · 인원 4명 뒤집힘, C 순위, 전체판 위 B 적재 거절 포함. `seed.sh`를 neo4j 이미지 안에서 구조판 2회 · 전체판 1회 exit 0(읽기 단언 16 · 17, 0 실패).
- **B 경쟁 결과**(사실: 운전시간 1,950 h, 이번 정비 시간 1,959 h, 그다음 2,230 h, 오더 납기 20 h · 지연 보상 50만 원/h, 정비 인원 2명, 씰 키트 가용 2개. 실제 그래프 템플릿 + 판단 엔진, 단위 시험과 라이브가 같은 값):

  | 순위 | 시행 방식 | 점수 | 지는 이유 / 붙는 것 |
  |---|---|---|---|
  | 1 | SOP-PM-11 이번 예정된 정비 시간에 단독 | 1.62 | 경고: 씰 키트 출고 뒤 재주문점 아래 → 구매 경보 예정(C 예고) |
  | 2 | SOP-PM-14 두 대 묶기 | −0.38 | 성과 지표 득실은 가장 좋다(정지 한 번 줄어듦, +1)지만 정비 인원 2명 < 4명 → 60만 원 감점(`rule:pm-bundle-crew`) |
  | 3 | SOP-PM-12 지금 바로 정지 | −4.62 | 가동률 · 생산량 손실(−2), 납기 24 h 안 오더 → 오더 손실 80만 원 감점(`rule:pm-stop-order`), 생산 영향 '정지' |
  | 제외 | SOP-PM-13 그다음 정비 시간으로 미루기 | — | 미루면 2,230 h > 2,200 h → 보증 기록 요건 위반(`rule:pm-defer-limit`, EXCLUDE) |

  값이 바뀌면 답이 바뀐다: 인원 4명 → 묶기 1위, 씰 키트 1개 → 묶기 제외(`rule:pm-bundle-spare`), 0개 → 지금 하는 안 모두 제외 · 미루기도 위반 → 추천 없음(비해피 가지), 이번 정비 시간이 2,210 h → 기다리는 안 제외 · 지금 정지만 남음.
- **C 경쟁 결과**(라이브): SOP-PUR-11 B-OEM 1.5 추천 > SOP-PUR-12 A정밀 0.5(전수 검사 비용 감점) > SOP-PUR-13 C트레이딩 제외(AVL). 세 안 모두 300만 원 초과 경고(승인은 구매 담당 1회).
- (A · C 때 기록) 단위: `tests/test_seed_editions.py` 9, `tests/test_c1_knowledge.py` 34 (A · C 문서 인용 · 지식 · 규칙 · 원자 조치 값 · 잘못된 입력 21종 거절 · 구간 병합 · 카탈로그 고정). 전체 `pytest -q`: **1739 passed, 4 skipped, 1 failed** — 실패는 `test_mcp_check.py::test_html_page_is_not_an_mcp_endpoint`로 작업 전 기준선에서도 같은 실패(이 macOS 환경의 로컬 HTTP 응답 'closed', C1과 무관).
- 라이브(버림 컨테이너 `c1kg-a161-neo4j`, 17688, 검증 뒤 삭제): `scripts/probe_c1_knowledge.py` **28/28 PASS**
  - 새 전체판 그래프 = 옛 시드 그래프 + scenario_structure 추가 5노드(빠지거나 바뀐 노드 · 관계 0), 전체판 되읽기 · `ontology_v2 validate` 통과.
  - 구조판: 되읽기 통과, 지식 레이블 0, 규칙 3(회사 규정 · 순위), 쿨러 경보 원인 후보 0, validate 통과.
  - 구조판 + 대역 펌프 지식 + 문서 A + 문서 C 적재 → t1 원인 템플릿이 핀 오염(0.6) 1순위와 증거를 읽음, 후보 규칙이 SOP 7개, t3 카드가 FAN_SET 100 · LOAD_SET 80, 재고 경보 후보 규칙 → 구매 SOP 3 · 공급사 sup:b/a/c, 금액 · AVL · 납기 규정 규칙, 스키마 검사 통과, 시드 재실행이 문서 소유를 건드리지 않음, 참조 중 문서 되돌리기 거절, 재적재 · 되돌리기 4건 → 구조판 복귀.
  - 전체판 위 문서 A는 미리보기에서 시드 소유 충돌을 알리고 적재는 거절.
- `seed.sh`를 neo4j 이미지 안에서 실제 실행: 구조판 2회(멱등) · 전체판 1회 모두 exit 0.

## 5. 참고 레포 대응 (ProcessGPT `/Users/uengine/process-gpt`, origin uengine-oss/process-gpt, HEAD 7c678c47 2026-08-10)

BX = `services/bpmn-extractor/src/pdf2bpmn`, OS = `services/ontology-studio/backend/src/modules`.

| 설계 선택 | 따른 곳 |
|---|---|
| 추출 입력에 기존 온톨로지 목록을 주고 "있는 것은 같은 id로, 없는 것은 지어내지 말 것" | BX `extractors/entity_extractor.py:49`(existing_context 자리) · `:228-275`(기존 이름 그대로 쓰기 규칙) · `:348-392` `_build_context`, OS `agent_session/service.py:158-160`(target_schema의 클래스만). 참고는 이름만 넘기고 HYD는 id까지 넘긴다(HYD 자체: 그래프 id로 바로 잇기 위해) |
| 항목마다 원문 근거(인용) | BX `entity_extractor.py:69-74`(evidence 원문 구간) · `graph/neo4j_client.py:781-815`(SUPPORTED_BY). HYD는 이미 채택한 A117 인용 위치 찾기(REFERENCE_ADOPTION T01) 재사용. 참고의 confidence 칸은 두지 않음(사람이 검토) |
| 결정 규칙(조건 → 결과) 추출 · 결정표 행으로 적재 | BX `entity_extractor.py:57-58,158-168`(조건-결과 쌍) · `models/entities.py:163-178`(DMNRule) · `graph/neo4j_client.py:702-760`(HAS_RULE). 규칙을 기존 DMN 결정표 · TESTS 관계로 쓰는 것은 HYD 자체(X07, 스키마 v2의 규칙 모양) |
| 사람 검토 뒤에만 그래프 쓰기 | BX `hitl.py:1-28,413-445`(멈춤 · 재개 계약) · `models/entities.py:55-56`. HYD는 기존 검토 → 커밋 경로(A092) 그대로 |
| 구간별 제안 병합 · 같은 id는 첫 제안 유지 + 경고 | BX `workflow/graph.py:716-882` · `models/state.py:21-30`(id로 중복 제거), OS `ontology/tools.py:218-226`(merge_warning). HYD 기존 A093 병합에 지식 항목만 더함 |
| 적재 전 기존 노드 충돌 알림 | OS `ontology/tools.py:218-226`(이름 충돌 경고, 클래스만) · BX `graph/vector_search.py:115-170`(유사 기존 개체). id 기준 충돌 목록은 HYD 자체(A077 sop_conflicts를 지식으로 넓힘) |
| 문서 단위 소유 · 재적재 · 되돌리기 | OS `ontology/tools.py:562-566`(`_source_id`) · `document_indexing/service.py:492-590`(문서 단위 갱신, 청크만). 원자적 배치 되돌리기 · 적재 기록 기반 소유는 HYD 자체(참고에 없음, 스키마 v2를 바꾸지 않으려고 속성 대신 기록) |
| 관계 끝점 · 값 검사(Action min~max, 결정 입력 선언) | 참고에 없음(OS `tools.py:473-512,602-626`은 검사하지 않음) — HYD 자체(스키마 · 안전: 승인 앞 명령 값이 허용 범위 안이어야 함) |
| 증거 SQL을 서버 틀로 | HYD 자체(에이전트가 SQL을 쓰지 않게 — A083 tag · windowSeconds 계약) |
| 적재 뒤 골든 퀘스천 | OS `agent_session/service.py:243-274,480-520`, HYD 기존 A118. 지식 id도 답 근거로 셀 수 있게 적재 기록에서 읽도록만 바꿈 |
| 시드 두 판 · 문장 표시 필터 | HYD 자체(결정 6, 참고에 해당 없음) |
| (B) 관계 타입 하나를 스키마 원본 한 곳에 이름 · 끝점 · 설명 · 속성으로 더하고 나머지는 생성 | OS `ontology/tools.py:239-274` `schema_create_relationship_type`(관계 타입 = 이름 · from · to · 설명 · 속성, 저장소가 원본). HYD는 `schema.json`이 원본, `ontology_v2.py gen`이 프롬프트 · OWL · 그림을 만든다(기존 v2 방식) |
| (B) 관계 이름 PREVENTED_BY와 뜻 | 표준 준용: EN 13306(preventive maintenance) · ISO 14224(PM). 참고 레포에 정비 온톨로지 없음 — HYD 자체(사용자 확정 2026-10-09) |
| (B) 주기 · 허용 오차 · 인원 · 부품 기준을 결정표 행(TESTS 관계)으로 | BX `extractors/entity_extractor.py:57-58,158-168`(조건-결과 쌍) · `models/entities.py:163-178`(DMNRule). 임계값을 관계로 두는 것은 스키마 v2 규칙(`conventions.threshold`) |
| (B) 시행 방식(언제 · 얼마나)을 SOP 넷으로 두고 같은 판단 엔진에서 경쟁 | HYD 자체(기존 A115 결정표 평가 · rule:rank-value 그대로). 참고 레포는 대안 순위를 매기지 않음 |
| (B) 정기 정비 도래를 증상 없는 감시 규칙(AnomalyPattern, detectionMode 없음)으로 | HYD 자체(결정 1, C의 SPARE_BELOW_MIN과 같은 모양). SAP · Maximo 운전시간 계수기 계획은 조사 문서 출처(scenario-selection §9) |
| (B) 구조판 전용 규칙 범위 좁히기(rule:avl) | HYD 자체(시드 두 판에서 생긴 결함 수정, 참고에 해당 없음) |

## 6. 남은 것 · 결정 필요

1. **B 판단의 실행 쪽(C2 · C3 몫)**: 판단 엔진은 지금 후보마다 `forecast_ts1 · skill_kind · skill_code · supplier_avl`만 따로 계산한다. B 사실(`hours_since_pm` · `hours_at_next_window` · `hours_at_following_window` · `pm_crew_available` · `spare_available` · `order_due_h`)은 처리 건 단위 사실로 주면 되도록 규칙을 짰다(시행 방식별 차이는 APPLIES_TO가 가른다). 이 값을 CMMS · MES에서 읽어 오는 도구(`cmms_pm_plans` · `cmms_counters` 등)와 PM_DUE 경보 발행은 C2.
2. **설비 명령이 없는 카드의 예측**: 회사 규정 `rule:ts1-hard`(예측 유온 ≥ 65 → 제외)는 모든 후보에 걸린다. 예측이 없으면 "모름 → 제외"가 된다. 시험 · 라이브 검증은 정비 · 구매 카드에 지금 운전점 그대로의 예측(48 ℃)을 주고 돌렸다. 실제 에이전트가 B · C 카드에도 예측(또는 공칭값)을 붙이는지 C3에서 확인 필요.
3. **C 재고 경보의 원인 사실**: 구매 SOP는 원인 한정(ADDRESSES `cause:pump-seal-wear`)이라, 재고 경보에 원인이 없으면 엔진이 후보에서 거른다. 라이브 검증은 "부족한 부품을 쓰는 원인"(`Cause -INVOLVES_PART-> part:pump-seal`)을 그래프에서 읽어 사실로 줬다. C 에이전트가 같은 조회를 해야 한다(C2/C3). 대안: 구매 SOP에서 ADDRESSES를 빼는 것(그러면 C는 B의 원인 id에 기대지 않고 고장 유형만 가리킨다).
4. **C 공급사별 총비용**: 문서는 총비용(단가 × 수량 + 수량 × 불량률 × 250만 원)을 정했지만 엔진은 공급사별 값을 사실로 받지 못한다. 지금은 문서의 전수 검사 비용 규칙(20만 원 감점)으로 A정밀이 진다. 엔진에 공급사별 불량률 · 총비용 사실을 더하면 더 정확해진다(C2/C3 판단).
5. **B 결과 확인 · 미달 가지**: 시운전 기준(PS1 · FS1 · VS1, 15분)은 문서 PM-2.9에 있고 지식에는 절(ManualSection)로 남는다. 시운전 확인 · 계수기 리셋 · 미달 결과 보고는 실행 쪽(C2).
6. **구조판에서 비는 주제**: 팬 진동 · 작동유(HM-9/B7) · 과열/저압/고진동 트립은 A · B · C 문서에 없어 구조판에서는 "조치 없음"이다. 펌프 누설 경보(PUMP_LEAKAGE)는 B 적재 뒤 원인 진단까지는 되지만 시정 조치 SOP는 없다(B는 예방 조치만).
7. **실제 LLM 추출 미검증**: 계약 · 지시문은 PREVENTED_BY까지 받게 바꿨지만 실제 워커로 A · B · C를 추출한 라이브 검증은 하지 않았다(주 스택은 다른 에이전트 소유). C3에서 `POST …/extractions` → 검토 → 커밋 확인 필요.
8. **users 행**: 구매 담당 · 구매팀장 Supabase users 행(`it/supabase/seed.sql`)은 넣지 않았다(C3).
9. 포털 샘플 사본 `it/portal/www/samples/HM-8_cooler-fan-manual.md`는 옛 판 그대로(포털 담당이 맞추거나 PM-02 · PR-07 추가 결정). `scripts/ui_regression.py`가 그 사본을 쓴다. 포털 스킬 편집 화면(`hitl.js`)의 관계 고르기에는 PREVENTED_BY 선택지를 넣지 않았다(API는 받는다, 화면은 U 담당).
10. 문서끼리 참조(C → B의 고장 유형 · 원인)가 있으면 B는 C를 되돌리기 전까지 개정 · 되돌리기가 막힌다(의도된 보호, 사유와 함께 409).
11. 업무 MCP 둘로 나누기(보전용 · 구매용)는 C2 몫이라 C1에서는 건드리지 않았다. 문서 · 지식에는 도구 이름을 쓰지 않았다.

### 스스로 판정할 체크 질문

- 구조판으로 띄운 직후 쿨러 경보의 원인 후보가 0이고, HM-8을 적재한 뒤에만 핀 오염 · 팬 최대 카드가 나오는가?
- B를 적재한 뒤 정기 정비 SOP 7개가 모두 "예방 조치"로 이어지고, 펌프 누설 경보의 대응 후보에는 섞이지 않는가?
- B 판단에서 "지금 정지 · 미루기 · 두 대 묶기"가 각각 오더 손실 · 허용 오차 위반 · 인력 부족이라는 서로 다른 이유로 지고, 정비 인원을 4명으로 바꾸면 묶기가 이기는가?
- 문서 C를 적재한 뒤 재고 경보의 후보가 구매 SOP 3개뿐이고, 쿨러 · 펌프 경보 후보에는 구매 SOP가 섞이지 않는가?
- 문서가 없는 Action 코드나 범위 밖 명령 값(팬 140 %)을 내면 적재가 사유와 함께 거절되는가?
- 전체판으로 돌린 회귀 스크립트가 이전과 같은 시드 스킬 · 규칙을 보는가(`probe_c1_knowledge` 1번 비교)?
