# C1 지식 — 시드 두 판 · 문서 적재 확장 · 시나리오 문서 (확정 TODO C1)

작성 2026-10-09. 근거: `TODO.md` 확정 TODO C(원칙 · 결정 1 · 2 · 6 · 7), `scenario-research.md` §2.1 · §2.2 · §5 · §10.1(K1~K7).
증거: `.evidence/a161-c1/` (명령 `COMMANDS.txt`). HANDOFF · TODO · DECISIONS는 고치지 않았다(메인 세션이 합친다).

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
| 문서 | A: `HM-8_cooler-fan-manual.md` 보강(HM-8.1 · 8.2 그대로 + 8.3 판정 기준 · 8.4 고장 · 원인 · 증거 · 8.5 즉시 완화 SOP-COOL-11~13 · 8.6 회복 · 8.7 근본 SOP-COOL-14 · 15 · 8.8 금지). C: `PR-07_spare-parts-standard.md`(중요 예비품 · 재주문점/목표 재고 · AVL · 공급사 비교(총비용 · 리드타임 · 불량률) · 금액 전결 300만 원 · 발주 SOP-PUR-11~13 · 입고 확인). **B 문서는 코디네이터 지시로 보류**(B 재정의 대기) | `docs/samples/` |
| 포털(최소) | 처리 과정 패널에 `ontology_catalog` 한국어 이름 · 종류별 개수, 추출 제안 요약에 지식 개수. 이것 없이는 영문 변수명이 보여 기존 시험(`test_u1_task_detail`)이 실패 | `it/portal/www/taskDetail.js` |
| 회귀 스크립트 | HM-8 보강으로 미리보기 기대값 2절 · 8단계 → 8절 · 7 SOP · 25단계, 모든 SOP 번호를 시험용으로 치환 | `scripts/scenario_test.py` |

시드 SOP 번호와 겹치지 않게 문서 A는 SOP-COOL-11~15를 쓴다(전체판 SOP-COOL-01~05).

## 2. 시드 판 바꾸는 법

- 강의(기본): `SEED_EDITION=structure` → `docker compose --profile knowledge up kg-seed`. 로그 `seed edition: structure`, `read-back: 16 checks, 0 failed`.
- 회귀 · 통합 시험: `.env`에 `SEED_EDITION=full`, **새 neo4j 볼륨**에서 kg-seed. 로그 `read-back: 17 checks, 0 failed`.
- kg-seed는 MERGE만 하므로 지식이 든 볼륨을 structure로 다시 돌려도 지워지지 않는다(주 스택에 영향 없음). 호스트: `scripts/ontology_v2.py load --edition structure|full`.

## 3. 검토 화면용 API · 데이터 모양 (U 담당에게)

1. `GET /api/kg/manuals/catalog` (새) — 고르기 목록: `components` · `symptoms`(patterns) · `patterns` · `parts`(suppliers: price · failRate · leadDays · avl) · `suppliers` · `state_variables` · `measures` · `actions`(code · kind · param · min · max · target) · `roles`(level) · `decision_tables`(decision · inputs[id · variable · typeRef]) · `failure_modes` · `causes` · `skills` · `evidence_tags` · `rule_tables`(표별 허용 effect).
2. `POST /api/kg/manuals/sources/{id}/extractions` — 그대로. 서버가 catalog를 실행 입력 `ontology_catalog`로 고정한다.
3. `GET …/extractions/{instance}` → `preview`에 기존 필드 + `knowledge` + 절차마다 `link`(제안) + `knowledge_conflicts`([{id, label, owner: 'seed'|문서 id, kind}] — 같은 문서 재적재는 제외).
4. `POST /api/kg/manuals/commit` 본문 = 미리보기 + `links` + `knowledge` + `by` + `reviewed:true`(+ 에이전트 추출이면 `method`, `extraction`).
   - `links[SOP] = {failureMode, relation: MITIGATED_BY|REMEDIED_BY, kind: control|work_order, approver: role:…, affects:[{target, sign, note}], actions:[{action: action:…, value}], addresses:[cause:…]}` — 화면은 `preview.procedures[i].link`로 미리 채우고 사람이 고친다.
   - `knowledge = {failure_modes:[{id fm:…, name, component comp:…, symptoms[sym:…], leads_to[fm:…], section, anchor}], causes:[{id cause:…, name, aliases[], prior 0~1, failure_mode, parts[part:…], disturbs[{target sv:…, sign}], section, anchor}], evidence:[{id evd:…, cause, name, tag, aggregate avg|max|min|range, window_seconds 1~3600, expect lt|gt|gte, threshold, weight 0~1, section, anchor}], rules:[{id rule:…, table dt:diagnose-cause|dt:action-candidates|dt:compliance, effect, tests[{input in:…, operator, value, unit}], outputs[cause:…|SOP-…|skill:…], applies_to[SOP-…|skill:…], penalty, penalizes msr:…, order?, annotation, section, anchor}]}`. 이미 있는 id(충돌 목록)는 항목을 빼고 그 id를 참조한다.
   - 실패는 400(모양 · 그래프 검사, 이유 전부 ` / `로 연결) · 409(소유 충돌 · 판본 변경). 영수증에 `knowledge`(종류별 id) · `actions` 수가 붙는다.
5. 되돌리기 `POST /api/kg/manuals/batches/{batch}/rollback` 그대로. 다른 문서가 참조 중이면 409.

## 4. 시험 · 검증

- 단위: `tests/test_seed_editions.py` 9, `tests/test_c1_knowledge.py` 34 (A · C 문서 인용 · 지식 · 규칙 · 원자 조치 값 · 잘못된 입력 21종 거절 · 구간 병합 · 카탈로그 고정). 전체 `pytest -q`: **1739 passed, 4 skipped, 1 failed** — 실패는 `test_mcp_check.py::test_html_page_is_not_an_mcp_endpoint`로 작업 전 기준선에서도 같은 실패(이 macOS 환경의 로컬 HTTP 응답 'closed', C1과 무관).
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

## 6. 남은 것 · 결정 필요

1. **B 문서 · B 구조 보류**: 코디네이터 지시(B를 "정기 정비" — 가동 시간/달력 도래 시작, 점검만/씰 교체/펌프 교체 판단)로 B 문서를 쓰지 않았고 조기 열화 패턴(PUMP_DEGRADATION_EARLY)도 넣지 않았다. 추출 · 적재는 일반형이라 B 문서가 오면 그대로 들어간다. B용 판단 입력(가동 시간 · 정비 주기 · 정비창 · 재고 등)은 B 확정 뒤 `scenario_structure.cypher`에 더한다(결정표 REQUIRES_INPUT 포함).
2. **C가 기대는 펌프 고장 지식**: 구매 SOP는 `fm:volumetric-loss`(REMEDIED_BY) · `cause:pump-seal-wear`(ADDRESSES)를 가리킨다. 구조판에서는 이 노드를 B 문서가 만들어야 C가 적재된다(없으면 409 "대상이 없거나…"). 시험은 대역 문서(`tests/c1_fixtures.py PUMP_STANDIN`)로 확인. B 문서가 다른 id를 쓰면 C 링크도 그 id로.
3. **구조판에서 비는 주제**: 팬 진동 · 작동유(HM-9/B7) · 과열/저압/고진동 트립은 이번 A · C 문서에 없어 구조판에서는 "조치 없음"이다. B7 작동유 시나리오는 전체판에서만 그대로 돈다(HM-9 적재는 fm:oil-degradation이 시드에 있어야 함).
4. **실제 LLM 추출 미검증**: 계약 · 지시문은 바꿨지만 실제 워커(Claude Code)로 A · C를 추출한 라이브 검증은 하지 않았다(주 스택은 다른 에이전트 소유). C3에서 `POST …/extractions` → 검토 → 커밋으로 확인 필요.
5. **결정 1 적용 범위**: 되읽기 단언을 "held · plc-trip 또는 증상을 잇는 패턴"으로 좁혔다. 재고 패턴은 Symptom 없이 TESTS만 갖는다.
6. **users 행**: 구매 담당 · 구매팀장 Supabase users 행(`it/supabase/seed.sql`)은 넣지 않았다(C3).
7. 포털 샘플 사본 `it/portal/www/samples/HM-8_cooler-fan-manual.md`는 옛 판 그대로(포털 담당이 맞추거나 PR-07 추가 결정). `scripts/ui_regression.py`가 그 사본을 쓴다.
8. 문서끼리 참조(C → B의 고장 유형)가 있으면 B는 C를 되돌리기 전까지 개정 · 되돌리기가 막힌다(의도된 보호, 사유와 함께 409).

### 스스로 판정할 체크 질문

- 구조판으로 띄운 직후 쿨러 경보의 원인 후보가 0이고, HM-8을 적재한 뒤에만 핀 오염 · 팬 최대 카드가 나오는가?
- 문서 C를 적재한 뒤 재고 경보의 후보가 구매 SOP 3개뿐이고, 쿨러 · 펌프 경보 후보에는 구매 SOP가 섞이지 않는가?
- 문서가 없는 Action 코드나 범위 밖 명령 값(팬 140 %)을 내면 적재가 사유와 함께 거절되는가?
- 전체판으로 돌린 회귀 스크립트가 이전과 같은 시드 스킬 · 규칙을 보는가(`probe_c1_knowledge` 1번 비교)?
