# F3·F12 최종 원문·모델·운영 근거 감사

이번 작업은 Sol 6.1의 읽기 감사다. 제품·NOW·교재·lecture-deck를 수정하지 않았고 reviewed=true나 사람 검토 기록을 만들지 않았다. 실제 추출 제안과 원문, 현행 코드, 실패 로그를 읽어 완주 준비에 필요한 변경과 사람이 검토할 내용을 구분했다. 기준은 신규2.4 PR-07 추출 완료 이후 코드다. 메인의 후속 모델/검증 수정은 해당 증거로 별도 갱신해야 한다.

핵심 결과는 세 가지다. **B의 causes=[]는 필수 예방 지식이 아직 적재되지 않은 상태**, **PM-02에는 원문보다 넓은 command 제안**, **PR-07은 구매 절차를 추출해도 현행 Skill 모델의 FM 필수 조건 때문에 적재할 수 없는 제품 도메인 불일치**다. 이를 한 가지 원인이나 단순 seed 누락으로 합치면 안 된다. 사람 검토를 대신하거나 빈칸에 고장 유형·승인자·가중치를 지어 넣어 해결하지 않는다.

## 1. 실제 B의 빈 causes가 생기는 정확한 경로

실제 `worker-codex-skills.log`의 처리 건 `c3_pm.d99ee952-f943-42fd-ba53-745b569522f7`은 정비 상태·정비 시간·생산 오더와 hyd-dmn/business_causes를 정상 호출했다. 이어 실제 Neo4j에 PREVENTED_BY 관계를 조회한 반환도[]였다. MCP 시작 실패나 권한 거절을 정상 빈 목록으로 바꾼 결과가 아니다. 해당 로그와 보존된 실제 B 처리 건 원문을 근거로 한다.

[dmn tools.py](../../../../it/dmn-mcp/dmn_mcp/tools.py)의 BUSINESS_CAUSES.PM_DUE(35행)는 다음 경로를 요구한다.

```cypher
MATCH (fm:FailureMode)-[:PREVENTED_BY]->(:Skill)
WITH DISTINCT fm
MATCH (c:Cause)-[:CAUSES]->(fm)
RETURN c.id AS causeId, fm.id AS failureModeId
```

business_causes(189행)는 이 실제 조회 결과에서 top_cause/failure_mode를 만든다. 후속 evaluate_cards/submit_decision의 `_checked_cause`는 같은 업무 근거에 속하지 않는 원인을 거절한다. PM_DUE는 운전시간 업무 경보라 센서 증상 T1 진단으로 우회하는 계약이 아니다. [t2_skills.cypher](../../../../it/neo4j/templates/t2_skills.cypher)는 예방 스킬을 일반 고장 경보 후보에서도 제외한다.

[test_seed_editions.py](../../../../tests/test_seed_editions.py)104~113행은 이를 **의도적으로 문서에서 채우는 계약**으로 고정한다. 시드는 PM_DUE 패턴·1,950h 조건·판단 입력·부품 자리만 두고 모든 seed 파일에서 SOP-PM-/rule:cand-pm/PREVENTED_BY가 없음을 단언한다. full edition도 예외가 아니다. 따라서 seed 재실행이나 구조판→전체판 교체만으로 B를 완주시키는 근거는 없다.

[test_c1_scenario_b.py](../../../../tests/test_c1_scenario_b.py)74~97행의 문서 적재 계약은 PM-02의7개 시행 방식/패키지 SOP를 fm:volumetric-loss의 PREVENTED_BY로 만들고 Cause→CAUSES 및 부품 근거를 둔다. **이는 단위 고정본의 기대 계약이며 실제 사람 검토/적재가 이미 끝났다는 증명은 아니다.** 실제 PM-02 제안의 전체 commit이 아직 막혀 있어 B의 예방 경로도 생성되지 않았다.

완주 전 확인은 관계 숫자 하나만 만들기가 아니다. 검토된 PM 절차·출처·승인·후보 규칙이 실제 적재된 뒤 business_causes의 원인/FM, 후보가 반환하는 예방 SOP, evaluate_cards의 입력/규칙 근거와 submit_decision을 함께 대조해야 한다. 열린 incident 때문에 close409인 현재 B는 억지로 기술 종료하거나 성공으로 바꾸지 않는다.

## 2. 세 문서의 제안과 모델 문제

원문은 [HM-8](../../../samples/HM-8_cooler-fan-manual.md)·[PM-02](../../../samples/PM-02_powerpack-pm-checklist.md)·[PR-07](../../../samples/PR-07_spare-parts-standard.md)다. 실제 제안은 활성 작업 트리 `.evidence/a161-c3/proposal-HM-8.json`, proposal-PM-02.json, proposal-PR-07.json이며 최초 PR2.3 절차0은 proposal-PR-07-v2.3.json에 따로 보존했다. 세부 원문/경고 표는 [manual-review-packet.md](manual-review-packet.md)를 따른다.

| 문서 | 원문과 실제 제안 | 현재 막는 원인·구분 |
|---|---|---|
| HM-8 | 절8·절차8·단계27. 원문 COOL-11~15와 기존 COOL-01~05, 운전원과 기존 생산관리자 승인 역할이 다름 | `existing_skill_id`가 있어도 manual_graph는 절차id로 새 Skill을 생성한다. 동일성·개정/별도 등록·승인 역할은 의미 검토 대상이다. evidence4개와 제한 규칙의 설정 부족도 자동 추정하지 않는다 |
| PM-02 | 절10·절차8·단계33. PM-12는 생산/설비를 정지하고 정비 오더·공지·출고를 수행하라는 현장/업무 절차 | `kind=work_order`에 action:controlled-stop command(value=null)를 제안했다. 그래프 검증은 command를 control에만 허용해 거절한다. 원문은 PLC 실행 승인이나 명령 인자를 주지 않았으므로 kind만 control로 바꿔 통과시키면 안 된다 |
| PR-07 신규2.4 | 실제 Sol COMPLETED, 절7·절차6·단계21. PUR-11~13 각5단계와 추가 정책/검증3절차. 고장 연결은 원문에 없어6개 FM/relation이null | 추출 범위 결함은 해결됐지만 현행 새 Skill의 FM 필수 조건과 충돌한다. 사람에게 존재하지 않는 고장 유형을 고르라고 넘길 문제가 아니라 제품의 구매 절차 도메인 지원 문제다. 별도의 사람 원문 검토 단계는 여전히 필요하다 |

### PM의 잘못된 command를 사람 검토 전에 드러내는 검증

[manual_extraction.validate_proposal](../../../../it/process/procsvc/manual_extraction.py)87/137행은 원문 anchor·절차/단계 순서·형식과 link 값의 스칼라를 검증한다. require_failure_mode=False라 미상 연결을 남기는 제안은 허용한다. **READY는 원문/형식 검증 상태이지 적재 가능한 의미 모델이라는 보장이 아니다.**

실제 Action 종류/값·Rule 입력 검사는 [manual_knowledge.check_graph](../../../../it/process/procsvc/manual_knowledge.py)354~388행에 있다. 현행 [manual_api.py](../../../../it/process/procsvc/manual_api.py)124~145행은 POST commit에서 사람 검토를 검증한 다음에야 이 검사를 호출한다. 전용 읽기 dry-run/validate API는 현재 없다. 그래서 PM-12의 work_order/command 충돌은 추출 READY에는 남고 commit 시점에 드러난다.

안전한 제품 후보는 **기존 GET extraction-result/preview에 읽기 전용 preflight 결과를 추가**하는 것이다. Action/공급사/SOP/Rule 검사를 쓰기와 분리한 공용 validator로 만들고 실제/고정 catalog를 읽어 다음 정도의 계약을 반환한다.

```json
{"validation":{"checked":true,"can_commit":false,"issues":[
  {"sop":"SOP-PM-12","field":"link.actions","code":"COMMAND_IN_WORK_ORDER"}
]}}
```

이 예시는 제안 API 계약이며 실행 결과를 지어낸 로그가 아니다. reviewed/by를 만들지 않고 원제안·인용·경고는 보존한다. issues가 비어도 사람 검토가 끝났거나 적재 권한을 얻었다는 뜻은 아니다. FM 미상·필수 입력 부족도 별도 issue로 남겨 원문 절차를 삭제하거나 고장 유형을 자동 생성하지 않는다. commit에서는 최신 그래프를 다시 검증해 추출 때 고정한 catalog 이후의 변경도 잡아야 한다. 수정 제안은 원문 feedback을 준 새 추출/교정으로 별도 보관하고 실제 사람 검토 전에는 적용/적재하지 않는다.

### PR의 FM 조건은 검증 한 줄만 풀 수 없다

다음 계층이 모두 같은 고장 조치 전제를 갖는다.

| 계층 | 실제 강제 |
|---|---|
| manual_review.validate(188행)→kgadmin.validate_skill(create=True,148행) | 새 SOP에 failureMode 필수. 승인자 공백도 maint-mgr로 대체할 수 있어 미상 역할 보존과 별도 검토가 필요 |
| manual_api commit(141행) | 모든 procedures의 failureMode로 후보 규칙을 조회 |
| manual_graph.desired(192~208행) | 모든 Skill에 FM→관계 edge를 무조건 만들고 kind가control이면SCADA, 그 밖에는CMMS의 HAS_SKILL을 생성 |
| schema-v2 Skill 및 schema_prompt.md72행 | Skill은 FM의 MITIGATED_BY/REMEDIED_BY/PREVENTED_BY incoming≥1 필수 |
| v2/seed_checks.cypher18행 및 ontology validator 시험 | 고장 유형에 매칭되지 않은 Skill을 오류로 판정 |

따라서 optionalFM만 kgadmin에서 푸는 것은 dangling/부정확한 graph edge, 후보 연결, 시스템 담당 및 스키마 되읽기와 불일치한다. 구매/업무 절차 지원은 **기존 고장 조치의 필수 연결을 보존하면서 업무 근거·적용 범위·출처·승인·시스템 실행 연결을 명시하는 일관된 모델**로 검토해야 한다. 원문과 실제 domain이 없는 FM나 CMMS 연결을 임의로 채우지 않는다. 스키마v2 동결/가산 원칙과 런타임/적재/조회/검증 전체를 함께 검토하는 root의 제품 과제다.

## 3. 자동 준비와 사람이 결정할 목록 — 짧은 최종표

| 항목 | 지금 안전하게 자동 준비할 수 있는 것 | 사람이 확인하거나 제품 모델에서 해결할 것 |
|---|---|---|
| 원문/동일 문서 | 바이트·hash·anchor·단계/ID 순서·완료 판본 검증, 정확히 하나인 current document_id 재사용 | 기존 Skill 동일성·별도 새 번호와 개정의 의미, 다른 문서/판정 이력 소유권 |
| PM command | 실제 Action catalog와 비교해 원문에 없는 PLC 연결/종류 충돌을 preflight issue로 표시; 원문 feedback으로 새 수정 제안 준비 | 원문에 없는 PLC 실행 권한/인자는 만들지 않음. 현장 정지와 업무 오더 연결의 실제 의미 및 제안 변경 검토 |
| PR 구매 절차 | 원문 명시3개/15단계와 신규6개/21단계의 출처 보존·검증 | FM 없는 업무 절차는 제품 도메인 모델 수정 과제. 단일 검증 완화나 임의 FM 연결로 대체하지 않음 |
| 누락 지식/규칙 | 30/60/120초 관측 조건·명시 임계값·수량/기간/금액의 원문과 미등록 사유를 모음 | 미명시 evidence 가중치·감점 지표/월 집계·고정 공급사·승인 역할·개정 동일성은 추정하지 않음 |
| 실제 적재/완주 | 검증할 Cypher/API·예상 원문 경로·판정/승인/업무 효과 점검 준비 | 실제 사람의 추출 instance와 연결된 검토 기록 뒤 적재. B의 예방 지식 경로와 신규 PR 기반 C는 아래 필수 조건 전에는 완료로 보고하지 않음 |

[scripts/c3_ingest.py](../../../../scripts/c3_ingest.py)74~120행의 apply_review는 doc/by/extraction/warnings_read, 변경/추가/제외의 원문 quote와 reason을 요구한다. 알고리즘이 적용 가능한 형식/구조 검증과 이 사람 검토 기록은 구분한다. 담당자 이름이나 reviewed를 자동 만들어 실제 사람 승인이라고 기록하지 않는다.

차단 범위도 구분한다. **B는 현재 예방 지식/후보 규칙의 실제 검토·적재 전에는 완주할 수 없고, 신규 PR을 쓰는 C는 업무 절차 모델과 사람 검토/적재를 모두 해결해야 한다.** 기존에 적재된 A 지식이 충분한 기준 A 검증까지 새 HM-8 검토와 한 덩어리로 막을 이유는 없다. 기존 A 경로의 실제 검증과 새 HM-8 반영 성공은 별도 결과로 기록하면 된다. 어느 경로든 실제 충분한 지식 여부를 먼저 읽고 없는 지식을 만들어 통과시키지 않는다.

## 4. F12 원기록 대조 — 현재 장애와 과거 이력

| 항목 | 원기록 | 현재 판정 |
|---|---|---|
| kg-seed16분 | [live-final.md](../2026-10-10/live-final.md)58/92행: compose run이 컨테이너를 띄우기까지09:21→09:37, 원인 미확인. seed 자체는 수십 초 | 현재 메인 실측59.719291초와 kg-seed.log의full exit0·read-back17/0을 확인. 동일16분 현상은 재현하지 못했다. Docker 기동 대기와 seed 내용 실행을 분리하며 원인이 해결됐다고 단정하지 않음 |
| b7379c5e… 고아 원천 | 같은 문서/sha인데 예전 c3_ingest가document_id를 안 줘 새 문서 생성→다른 소유의SOP 덮기409. 원천/추출만 보존되고 그래프 적재 없음(live-final35~42/60행) | 현재 loaded_document→preview document_id로 이미 근본 수정됨. 동일 파일의current가 여러개면 자동 선택하지 않고 거절한다. 해당 옛 원천의현재 존재/상태는 root 실제 조회로 확인할 예정이며 감사자가 삭제하지 않음 |
| ui_regression 전체판 | [c3-assembly.md](../2026-10-09/c3-assembly.md)147행: 줄 파서HM-8 적재에fm:cooling-loss가 필요해 구조판에서 막힐 수 있음 | 특정 옛 UI 쓰기 검사기의 전제다. 수업 구조판이 잘못됐다는 근거나 모든 현재 검증의필수 전체판 조건이 아님. 사람검토/문서적재를 생략하는 우회로 사용하지 않음 |

[c3_ingest.py](../../../../scripts/c3_ingest.py)124~146행은 현재 `GET /api/kg/manuals`의 같은filename/current 문서id를 재사용한다. current가둘 이상이면 어느 판을 개정할지 모호하므로 거절한다. [manual_sources.save](../../../../it/process/procsvc/manual_sources.py)135행은 document_id와sha가 같으면 원래 원천을 돌려주고, 새UUID는 document_id가 없을 때만 만든다. 과거 고아 원천은 실행 판단 그래프와 별개인 보관 자료라 삭제를 현재 완주 조건으로 추론하지 않는다.

root의 현재 조회 준비는 `GET /api/kg/manuals/sources`를 페이지 끝까지 읽고 b7379c5e 접두어의document_id/source_id/sha/filename을 확인한 다음 `GET /api/kg/manuals`의current/배치 소유와 비교하는 것이다. 원문/추출 이력 보존과 DB의KnowledgeSource/ManualIngestionDocument/_manual_document 연결을 함께 확인한다. 본문이나 운영 키값을 불필요하게 출력하지 않는다. 이름만 같은 원천을 삭제하거나 다른 문서의SOP 소유권을 바꾸지 않는다.

[ui_regression.py](../../../../scripts/ui_regression.py)171~186행은 HM-8 줄 파서preview 후 적재 버튼을 실제 클릭한다. 이는 읽기 캡처 전용이 아니며 옛 DOM/fixture와 graph 전제를 가진 쓰기 검사기다. 이 코드가 존재한다는 것만으로 현재 실제 사람 검토를 대신할 권한이 생기지 않는다. 현재 지식관리/학생 UI의독립 브라우저 계약과 실제target 캡처 범위를 이 옛 검사기와 구분한다.

## 5. 참고 제품과 안전한 실제 검증 순서

ProcessGPT 모노레포의 로컬 README39/41/150행은 반복 판단의DMN/Python 규칙화, 실제 단계 감사, HITL의승인/수정/거절을 설명한다. ontology-studio의 로컬 `backend/src/modules/quality/parser_screen.py`는 batch_ingest를 본쓰기와 분리해 ID/관계 끝점/선언된domain-range 오류를 선별한다. `ontology/api.py`299/333행은 target_schema를 입력에 명시한다. 이를 **원문 제안·구조/도메인 preflight·사람 검토·실제 적재 분리**의 참고로 읽었다. HYD와같은 PM/구매 모델이나 보호 구현을 upstream이 제공한다는 주장은 하지 않는다.

실제 완주 준비는 다음 순서로 가능하다.

1. 원문/제안은 보존하고 PM의command 오류 및 PR 모델 미지원 상태를 읽기preflight로 드러낸다. 모델 수정 시 기존 고장/판정이력/소유권/Rule/시스템 계약의 부정사례까지 같이 검증한다.
2. 적재 가능한 제안이 준비돼도 실제 사람 검토 기록을 별도로 받아 추출instance·경고·근거있는 변경을 연결한다. 이 감사 문서는 검토 승인을 대신하지 않는다.
3. root가 잠금 아래 문서preview/commit을 실행할 때409/부분쓰기 없음·원문/판정 이력 보존을 확인한다. 이미있는seed/admin 노드와 새 문서 충돌을 무조건 drop하지 않는다.
4. B는 PREVENTED_BY→FM←CAUSES 및 후보규칙을 실제 business_causes/evaluate_cards에서 확인한다. C는 ERP 부족부품→INVOLVES_PART→Cause의업무 근거와 실제 공급사/발주 입력을 확인한다. 이 결과 없이 빈 원인이나 없는 규칙을fallback으로 채우지 않는다.
5. 준비가 끝난 실제 A/B/C는 한 번에 한 처리 건·워커1개·20배속으로 진행하고 사람 승인/거절·업무 효과·결과 보고를 원문 증거로 확인한다. 기존 B의 열린 incident 보호를 유지한다.

F12의 과거16분 지연·미적재 고아 원천·옛 검사기 전제를 사람이 승인해야 하는 새 정책 질문으로 만들지 않는다. 현재 실행 가능성을 막는 것은 위F3의 검증/모델/실제 사람 검토 단계이며 각 원인을 따로 보고한다.

## 6. 후속 읽기 전용 preflight 구현

루트가 Sol 6.1에 `manual_knowledge.py` 의미검사 공용화와 `manual_api.py` preview/extraction-result의 additive 검사를 승인했다. 1~5절은 구현 전 감사이며 이 절이 후속 변경을 구분한다. 현재 Action/Rule 검사 pure helper는 원제안을 깊은 복사로 보존하고 commit은 최신 그래프 재검사를 유지한다. 새 `manual_preflight.py`는 사람 review/by를 생성하거나 validate(commit)를 우회하지 않는다.

응답은 `validation={checked,technical_ready,needs_human_review:true,can_commit:false,issues}`다. issue는 `code/sop/field/message`이며 한국어 사유를 보여준다. extraction 결과에서는 `preview.validation`, 구조화 preview에서는 응답의 `validation`에 붙는다. graph catalog 실패는503으로 명시하고 checked 성공/빈 목록으로 바꾸지 않는다. 기계검사 통과가 사람 검토·원문 의미 검증·실제 적재 성공을 뜻하지 않는다.

기존 POST reopen과 upload preview를 유지했고 같은 읽기 동작의 `GET /api/kg/manuals/sources/{source_id}/preview`를 추가했다. 현행 FM 필수 모델·승인 역할/대상 참조·Action 범위/공급사/SOP·Rule 입력·신규 지식의 외부 참조·이미 전달된 소유권 충돌을 표시한다. 현재 모델의 기본 kind/승인 역할은 검사에만 반영하며 원제안에 값을 채우지 않는다. PM/PR 도메인 제약을 완화하지 않았다. 적재 시 최신 catalog 재검사·원문 검토·atomic graph/배치·판정 이력 보호는 그대로다.

첫 검사 명령은 없는 `test_c1_knowledge_ingestion.py` 경로 때문에 **시험0개/exit1**이었다(`manual-preflight-first.log`); 실제 파일명으로 고쳤다. 관련 첫 회귀는 **121 passed, 10.75초**(`manual-preflight-tests.log`). GET preview와 commit 재조회 회귀를 추가한 마지막 범위는 **189 passed·5 skipped,10.28초,exit0**(`manual-preflight-final.log`). 명령은 `pytest tests/test_manual_preflight.py tests/test_manual_extraction.py tests/test_manual_review.py tests/test_c1_knowledge.py tests/test_c1_scenario_b.py tests/test_manual_revision_history.py tests/test_manual_sources.py tests/test_manual_locate.py tests/test_manual_segments.py tests/test_manual_golden.py -q --tb=short`다. `HYD_MANUAL_NEO4J_URI`는 미설정이며 실제 Neo4j 이력5개는 건너뜀이다. main DB에 접속하거나 이를 실제 이력 시험 완료로 주장하지 않았다. 로그 루트는 `D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/`다.

실제 DB·live 적재와 현재 제안의 실제 catalog preflight는 루트 소유이며 이 작업에서는 실행하지 않는다.

### 실제 추출 연결 계약 수정

앞선189개 통과는 실제 제안의 `procedures[].link`를 입력하는 검증이 빠져 있었다. 루트가 실제 PM/PR 제안으로 확인한 결과, preflight가 최상위 `links`만 읽어 PM의 정상 FM을 없다고 오판하고 PM12 command/work_order 충돌을 놓쳤다. 기존 통과 수치는 이 실제 계약 결함 해결의 증거가 아니며 보존한다.

수정은 최상위 `links`에 해당 SOP key가 있으면 그 값을 명시 override로 사용하고, key가 없을 때만 `procedures[].link`를 읽는다. 빈 객체 override는 명시 해제이며 원래 연결로 되돌리지 않는다. 과거 구조화 preview의 연결 없음도 유지한다. 원제안/anchors/단계/경고를 변경하지 않는다. 실제 `.evidence/a161-c3/proposal-PM-02.json`과 PR-07의 preview를 그대로 읽는 로컬 회귀와 독립 inline/빈 override/교체 회귀를 추가했다. 실제 evidence가 없는 다른 환경에서는 해당2개가 명시 skip이며 합성 시험으로 실제 추출 검증을 대체하지 않는다.

같은 범위 재실행은 **193 passed·5 skipped,13.45초,exit0**(`manual-preflight-inline-links.log`)이다. 이번 로컬 실행에서 실제 제안2개 회귀는 모두 통과했고5개 skip은 앞선 Neo4j 이력 시험이다. PM12의 `COMMAND_IN_WORK_ORDER`를 검출하고 PM의 정상 FM을 누락으로 오판하지 않으며 PR6개 FM 공란의 모델 제약을 각각 표시했다. 원제안 깊은 비교와 diff 검사가 통과했다. 이 검사의 catalog는 명시한 seed 계약 fixture이며 현재 live graph 조회 증거는 루트가 별도로 확인한다.
