# 4조 온톨로지 구축·문서 인제스천·출처 — 레포 4개 (HEAD: ontology-studio 6a229be 2026-07-09 · ontologic e72adf1 2026-08-13 · process-gpt-bpmn-extractor c7992ce 2026-08-04 · process-gpt-memento 659ab9f 2026-10-01)

읽기 전용. 프로젝트 파일은 고치지 않았다. 실험 스크립트·결과는 scratchpad `r14/g4exp/`에 있다(`studio_pattern_a.py`·`.json`·`_iter2.py`; studio 기능 브랜치 사본 `studio-branch/`).

**결론부터.** HYD 매뉴얼 인제스천은 "맞는 레포(ontology-studio)"를 따르지 않았다. 구간 분할은 bpmn-extractor에서 **이름만** 빌렸고(40,000자·`#` 제목·병렬 독립 구간·첫 제안 유지는 bpmn-extractor에도 없음), 나머지는 HYD가 따로 만들었다. 다만 적대적으로 대조해 보면 **추출 주체(LLM 대 파서 코드) 자체는 승부가 갈리지 않는다.** 실물 EHU40에서 정규식 파서는 절 구조는 LLM과 같게 뽑지만 절차는 8/37만 찾았다. 분할을 부른 실제 원인은 다른 데 있다. **결과를 마지막 메시지 토큰으로 돌려주는 HYD의 출력 경로**다. studio는 결과를 파일로 쓰고 `batch_ingest(파일 경로)`로 적재해서 이 문제가 처음부터 없다. 맞출 1순위는 이 출력 경로다.

---

## ontology-studio (6a229be 2026-07-09, 스냅샷 대비: 동일 — 10-03 사본과 같은 커밋(HANDOFF A112). 원격에 `feat/graph-store-strategy` e0dc888(07-29)이 있다. 구축 프롬프트는 main과 바이트 동일(diff 0)이고 `ontology/tools.py`만 다르다(그래프 저장소 Strategy·Apache AGE))

### 이 레포가 하는 방식 (흐름 순서, 파일:줄)
1. **진입**: `generate_sse`(agent_session/service.py:1327) → 빌드 모드는 `_compose_build_prompt`(480-526)가 [구축 의도]·[Golden Question]·[이전 결과 검토 피드백(verdict·feedback)]·[완료 기준]을 붙인다. 재개 시에는 `_compose_continuation_prompt`(597-666)가 이전 세션 요약·산출물 목록·graph_stats·`_search_hints.json`(앞 1,000자)을 붙인다.
2. **알고리즘 = 시스템 프롬프트** `ONTOLOGY_BUILD_SYSTEM_PROMPT`(80-275).
   - 패턴 A 구조→노드(정규식, 2-pass), 패턴 B 내용→엔티티·관계(기술문서, "문장/단락 단위 NLP식 추출" 94-96), 패턴 C 표→노드.
   - Phase 1: 골든 퀘스천에서 클래스·관계를 도출하고 `_schema_design.json`에 저장한다.
   - Phase 2: 모든 파일을 샘플링한다(PDF는 5~10쪽 177). 에이전트가 `_parser_<소스>.py`를 써서 실행하면 `_parsed_<소스>.json`이 나오고, `batch_ingest`는 이 **파일 경로**를 받는다("컨텍스트 절약을 위해 파일 경로 전달을 권장" 171).
   - 파서 규칙: 모든 노드에 content(2,000자) 필수, `name`·`number` 분리, 목차 건너뛰기, 표는 `extract_tables`, 관계에 `source_page`(228), 원문에 없는 개념 금지(229). 자체 검증은 content 커버리지가 80% 미만이면 수정(234-241). "대규모 문서는 페이지/행 범위를 나눠서 처리"(252) — 나누는 주체는 에이전트다.
   - Phase 3: graph_stats → 골든 퀘스천별로 실제 Cypher를 실행해 PASS/FAIL을 판정한다. 스키마 갭이면 Phase 1, 데이터 갭이면 Phase 2로 돌아가며 **최대 3회**(138)다. 끝나면 `_search_hints.json`을 쓰고 `ontology_build_report{question,answer,status,confidence}`를 반드시 낸다(254-274).
   - 실제 추적(tests/eval_build_trace.json): pdfplumber 시도 → "found 0" 실패 몇 번 → 파서 재작성 → 노드 601·관계 631 파싱 → batch_ingest.
3. **스키마 그룹·클래스**(ontology/tools.py)
   - 클래스 원본은 SQLite다(201-241). 다른 그룹에 같은 클래스가 있으면 `merge_warning`만 내고 병합한다.
   - 클래스 `properties`는 저장만 하고 적재 때 강제하지 않는다. `batch_ingest`는 쓰인 클래스를 그룹에 자동 등록한다(640-650).
   - 클래스를 삭제하면 엔티티도 DETACH DELETE된다(282-304).
4. **중복 처리**
   - `entity_search`(378-427): 클래스+속성 일치 검색. name만 주면 CONTAINS, LIMIT 10.
   - `entity_create`(430-475): `match_keys` 속성으로 `MERGE (n:_Entity:Class {keys})`.
   - `batch_ingest`(520-662): 노드는 `MERGE (n:_Entity:<class> {_source_id})`이고 **모든 문자열 속성**을 2,000자에서 자른다(562-565).
   - parent는 `CONTAINS`로 연결하고, 관계는 `_source_id`로 **클래스 구분 없이** 매칭한다(620-623). 오류는 20건까지만 보고한다(659).
5. **출처**: `_source_id`·`_parent_source_id` 노드 속성(567-569)과 관계 `source_page`(프롬프트 규칙)뿐이다. 문자 좌표는 없다.
6. **임베딩**: `batch_ingest` 끝에 `_embed_entity_nodes`가 돈다(665-721).
   - 임베딩이 없는 `_Entity`를 호출당 **최대 500개**, name+title+content 1,500자로 묶는다.
   - 모델은 OpenAI text-embedding-3-small 1536 또는 Ollama qwen3-embedding 4096이다(embedding.py:46,90-91). 1,000토큰으로 자르고 5개씩 묶어 보낸다(embedding.py:105-130).
   - 코사인 벡터 인덱스는 `entity_embedding_vector`다.
7. **질의응답 모드**: `ONTOLOGY_ANSWER_SYSTEM_PROMPT`(277-305)
   - `vector_search`(HyDE: minor 모델로 가상 답변 3~5문장 → 질문+답변 임베딩, embedding.py:133-181) 1회 → 부족하면 `CONTAINS` 보완. 도구 호출은 2~3회 이내, 근거 노드 번호를 명시한다.
   - 도구 6종(337-344): schema_get·entity_search·neo4j_cypher_readonly·graph_stats·vector_search·sandbox_read.
   - **`_search_hints.json`은 답변 에이전트가 읽지 않는다.** 주입 지점은 빌드 재개 프롬프트(649-654)뿐이다. 답변 프롬프트는 "질의 응답 에이전트가 자동으로 결정"한다고 적혀 있지만(140-146) 배선이 없다.
8. **읽기 MCP 4도구**(ontology_mcp/server.py:15-20)
   - `ontology_query`: 답변 에이전트를 SSE로 그대로 돌리고, 진행 상황을 MCP 로그로 보내며, `sources[]`를 돌려준다(adapters.py:93-).
   - `ontology_list_entities`(semantic_query·class_name+criteria·schema_name), `ontology_list_schemas`, `ontology_get_schema`.
   - 이 목록 자체가 보안 경계다(14-15 주석).
9. **문서 청크 색인**(document_indexing): 4,000자 가상 페이지(service.py:186,252) → tiktoken 1,000토큰·겹침 1/8(382-417) → BM25+벡터 RRF. **6a229be에서는 미연결이다.** 어느 라우트도, 어느 에이전트 도구 목록도 이것을 부르지 않는다(openspec/specs/document-indexing/spec.md:49-56, service.py:319-344).

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 추출 주체 | 에이전트가 파서 코드 작성·실행(패턴 A/C), 기술문서는 패턴 B | Claude Code 워커가 LLM으로 직접 추출(manual_extraction.py:16-41). 구조화 파서 결과를 정답으로 쓰지 말라고 명시(19) | 다름 | 실험(아래 출처 판정)에서는 구조=파서 동등, 절차=LLM 우위 | 사용자 결정(혼합 권고) |
| 결과 전달 경로 | 파일 → `batch_ingest(경로)`(171, tools.py:528-541) | 마지막 메시지의 JSON(`{"proposal":…}` 41, worker/outcome.py:1-5) | **다름** | HYD는 출력 토큰 상한 때문에 구간 분할(A093)이 필요했다. studio에는 이 제약이 없다 | **예** |
| 스키마 결정 | 골든 퀘스천 톱다운, SQLite, 런타임 생성·속성 미강제 | schema.json 2.5.0(46·72) 고정, validate가 미선언 속성까지 거부(ontology_v2.py:330-393) | 다름 | 회의 요구로 정한 HYD 선택 | 아니오(사용자 결정 유지) |
| 중복/MERGE 키 | `_source_id`(파서가 정한 id), 관계는 클래스 무시 매칭 | `manual:<doc>:<sha>:section:<hash>` 결정적 id, `Skill.sopId` 유일 제약, 타 원천 소유 시 Conflict(manual_graph.py:25-33,112-132) | 다름 | HYD 쪽이 강하다. studio는 다른 소스의 같은 id가 덮어쓰기·오연결될 수 있음(tools.py:571,620-623) | 아니오 |
| 출처 | `_source_id`·`source_page`·content 2,000자 | `{source_id,page,start,end,quote}` 문자 단위 정확 일치(manual_extraction.py:69-79, manual_sources.py:210-222) | 다름 | HYD 쪽이 정확. 대신 LLM이 좌표를 계산해야 해서 교정 회차가 생김 → memento 절 참조 | 부분(memento) |
| 검증 | 문서 빌드마다 골든 퀘스천 Cypher를 실행해 PASS/FAIL·status·confidence 보고 → 사람 verdict → 다음 회차 | ① 제안 계약 검증+교정 3회(instances.py:372) ② 사람 검토 WRONG/MISSING/OK(manual_extraction.py:123-146) ③ 그래프 전역 연결 감사 Q01~Q22(probe_semantic_links.py:1-12, 40-) | 다름 | HYD에는 "이 문서를 넣은 뒤 이 질문에 답할 수 있나"라는 문서별 검사·보고가 없다. Q01~Q22는 전역 무결성 감사, queries.cypher는 few-shot 예시(1-2행) | **예**(보고 형식) |
| 사람 검토 | 질문별 verdict/feedback이 다음 빌드에 재주입 | `reviewed=true`+`by` 필수, 검토 피드백 재주입(A077) | 같음(빌려 옴) | — | 아니오 |
| 읽기 경로 | MCP 4도구, 자유 질문 → 에이전트 → sources | 화이트리스트 Cypher 템플릿(agent/agentsvc/tools/mcp_kg.py:1-5), 카드 인용·guardrail(card.py:98, guardrail.py:12-42) | 다름 | HYD 판단 재현성 우선 설계 | 아니오 |
| 벡터/검색 | 엔티티 HyDE 벡터, 청크 RRF(미연결) | 벡터 0. 전문 인덱스 `ont_names`는 Measure·Component·StateVariable·Symptom·Cause·ExternalVariable만이고 ManualSection·Step은 없음(constraints.cypher:48) | 다름 | 매뉴얼 본문 검색 불가 | 사용자 결정 |

### 이전 주장 판정 (REFERENCE_ADOPTION O01 행)
- "스키마 관리·적재·검증은 같은 역할" → **불완전.** 적재 키·출처 강도·스키마 강제가 반대 방향이다(위 표). 검증도 대상이 다르다.
- "골든 퀘스천 루프 = HYD 감사기·queries.cypher"(ontology-studio-latest-ingestion.md:31 "추가 구현 불필요") → **틀림.** studio 루프는 문서 빌드마다 사용자 질문에 답할 수 있는지를 본다. HYD 감사기는 그래프 전체 연결성을 보고, queries.cypher는 Cypher 작성 예시다.
- "추출 주체가 다름 — 파서 생성 vs LLM 구간 추출(40,000자)" → **맞음.**
- ingestion 문서 "studio는 수 초·동일 결과" → **틀림.** 수 초는 파서 재실행만이다. ontologic이 같은 studio로 잰 문서 빌드는 Claude Code **991 s**(도로교통법 PDF 403 KB, 2,493 노드), Codex 361 s·**1,559 노드**였다(ontologic specs/004-pluggable-agent-backend/spec.md:195-197). 같은 문서에서 에이전트마다 결과가 다르다.
- ingestion 문서 "에이전트는 `hybrid_search_chunks`로 근거만 꺼냄" → **틀림**(6a229be 기준 미연결). r13-group5의 "제품에서도 미연결"이 맞다.
- r13-group5 "HYD grep embedding/vector 0건" → **맞음**(현재도 it/·scripts/ 제품 코드 0. UI 스크립트 3개의 일치는 무관).

### 읽지 않은 것
`agent_session/service.py` 1-79·700-1326·1400-1786(SSE·이력 압축), `session_store.py` 본문, `ocr_service.py` 574, `ontology/api.py` 대부분, frontend, `feat/graph-store-strategy`의 tools.py 차이 본문, openspec ontology/agent-session spec 본문.

---

## ontologic (e72adf1 2026-08-13, 스냅샷 대비: 동일 — `references/ontologic`과 diff 차이는 `.codegraph`뿐)

### 하위 레포와 HYD 부품의 겹침 (`.gitmodules` 15개. gitlink 14 + `data-platform-olap`은 tree. 전부 미체크아웃)
| 하위 레포(pin) | 겹치는 HYD 부품 | 이유 |
|---|---|---|
| ontology-studio (6a229be) | manual_*·kgadmin·schema.json·mcp_kg | 문서→온톨로지 구축·읽기 MCP의 정식 레포(O01) |
| process-gpt-bpmn-extractor (**8156f77**, 최신 c7992ce와 다르고 얕은 사본이라 관계 미확인) | manual_segments·manual_extraction | 문서→프로세스/SOP 추출(T02) |
| robo-data-catalog (96ba7d3) | graph_ingest·ddl_sync·enterprise-catalog.md | DDL/메타데이터→그래프(A067에서 대조함) |
| neo4j-text2sql (33401a6) | R06 자연어→SQL·`hydcommon/sql_read` | 메타데이터 그래프 기반 Text2SQL |
| data-secure-guard (a3b7707) | enterprise-mcp `sql_guard.py` | SQL 안전 가드 |
| domain-layer (2e88db1) | FORECAST_MODEL·bsc-conditions(INFLUENCES) | what-if·Granger 인과 발견(spec 003 전략 2 근거 `causal_analysis.py:325-353`) |
| robo-data-glossary (b6fac84) | T06 용어 저장 | 용어집 |
| agent-scheduler / node-local-agent-scheduler | agent-worker claim·lease | 에이전트 작업 배정(추측: 이름 기준, 본문 미확인) |
| data-fabric · infra · robo-data-frontend · robo-data-analyzer · antlr-code-parser · data-platform-olap | 직접 겹침 약함 | 데이터 연결·배포·UI·레거시 코드 분석·OLAP. analyzer는 원리 참고만(메모리 기록) |

**새로 확인한 사실(이전 기록에 없음).**
- ontologic의 `.mcp.json`은 `…/mcp/agent-bridge/build/`·`/answer/`를 가리킨다.
- `.claude/skills/ontology-build`·`ontology-answer`는 `../../ontology-studio/skills/...`를 가리키는 심볼릭 링크다.
- specs 004(Implemented 2026-08-01)·005가 기술하는 `agent_bridge_mcp/router.py`, 프롬프트 파일 `backend/src/modules/agent_session/skills/ontology_build.md 22.0K`, 참조 자료 `ingestion-patterns.md`(**패턴 A~D, D-1**)·`parser-rules.md`는 **pin된 6a229be에도, 원격의 다른 브랜치 e0dc888에도 없다**(ls-remote 브랜치 2개 전부 확인).
- 즉 플랫폼 문서가 공개 코드보다 앞서 있다. "최신 HEAD 6a229be"는 공개 main 기준으로만 참이다.
- 그 비공개 판에서도 문서 빌드 방식은 "파서 작성→적재→Cypher 검증"이다(004 spec.md:60-61,185; 005 spec.md:322). 004 plan.md:105에는 "전환 전 에이전트가 파서를 짜서 7번 실패, 전환 후 0번"이라는 기록이 있다. 또 spec 003 research.md:44-60은 문서 출처 위치로 `chunk_ref`·`source_page`를 쓴다고 적었다.

### 이전 주장 판정 (O02)
- "gitlink 14+tree 1, 서브모듈 미체크아웃" → **맞음.**
- "연결 추적 유지" → **불완전.** 위의 "pin된 커밋에 없는 agent-bridge·skills 참조"가 빠져 있다. 4조 범위에서 맞출 대상이 공개 코드인지 플랫폼 스펙인지 사용자가 알아야 한다.

### 읽지 않은 것
specs 001·002·006~009 본문, 003·004·005의 plan/tasks 대부분, constitution 80행 이후, installation.md.

---

## process-gpt-bpmn-extractor (c7992ce 2026-08-04, 스냅샷 대비: 동일 — r13-group6이 같은 커밋을 읽음)

### 이 레포가 하는 방식 (흐름 순서, 파일:줄)
1. **진입**: 실행기 `pdf2bpmn_agent_executor.py:9283-9292` → `workflow.extract_candidates_with_progress`. 앞 단계는 `ingest_pdf`(workflow/graph.py:148-172) → `PDFExtractor.extract_document`(extractors/pdf_extractor.py:45-136).
2. **원문**: pdfplumber 페이지 텍스트. 이미지가 있는 쪽은 OCR을 **항상** 함께 돈다(기본 tesseract, vision/synap 선택, 50쪽까지, config.py:76-88, pdf_extractor.py:66-90).
3. **분할(추출 단위 = 섹션)**
   - ① LLM SOP 경계 판정: **처음 30쪽만** 보여 준다(config.py:93, pdf_extractor.py:299-300). 돌려받은 `{title,page_from,page_to}`로 섹션을 만든다(491-510, temperature 0). SOP 결과가 있으면 그것을 그대로 쓴다(253-271).
   - ② 결과가 비면 제목 정규식 9종(`#`·`##`·`제N장`·`제N절`·`1.`·`1.1`·`1.1.1`·로마자·`A.` 633-709)으로 자른다.
   - **섹션 크기 상한은 없다.**
   - 읽은 코드로 보면, 30쪽을 넘는 문서는 LLM이 30쪽 안의 경계만 돌려줄 수 있어 31쪽 이후가 어느 섹션에도 들어가지 않는다(추측: page_to를 30 너머로 줄 수는 있으나 원문을 보지 못함. 미실측).
4. **청크**: 1,000자·겹침 200(config.py:66-67, `_create_chunks` 711-754). **임베딩·근거 연결용**(segment_sections 174-195)이고 추출 입력이 아니다.
5. **추출**: 섹션을 page_from 순으로 **순차** 돈다. LLM 호출마다 **이미 뽑힌 프로세스·역할·태스크 목록을 문맥으로 넘긴다**(graph.py:557-600, entity_extractor.py:393-436, temperature 0 291).
6. **병합**: 이름+내용 유사도로 프로세스 병합(SIMILARITY_MERGE 0.90), 태스크 cosine 0.85/0.92·명사 Jaccard 0.6, 역할 0.92(config.py:61-118), 전역 순서 재할당(graph.py:233-364).
7. **검증·교정**: `process_validator`는 BPMN **정의**의 정적 검사와 실제 엔진 실행 추적을 한다. LLM 교정은 기본 **max_iters 5**(process_validator.py:121,257-415)다. 원문 대비 인용 검증은 없다.

### HYD 대응 부품과 대조 (A093 "나누고 합치는 구조를 가져왔다")
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 분할 기준 | LLM SOP 경계(30쪽까지) 우선, 없으면 제목 정규식 9종 | `^#{1,3} ` 제목만 + 40,000자 예산 + 문단 경계 절단 + 페이지 묶음(manual_segments.py:11-60) | **다름** | PDF에는 `#`이 없어 HYD 구간 경계는 사실상 **쪽 경계**다(EHU40 1~22·23~49·50~73·74~80쪽, HANDOFF A094④). 장 중간에서 끊긴다 | 아니오(레포 쪽이 더 나쁨. 아래) |
| 크기 | 상한 없음 | 40,000자(12), 최소 2,000(13) | 다름 | 40,000은 HYD가 정한 수치(출력 상한 회피) | — |
| 겹침 | 추출 섹션 겹침 없음(청크만 200자) | 없음 | 같음 | — | — |
| 처리 순서·문맥 | 순차, 앞 섹션의 엔티티 목록 전달 | 구간마다 독립 인스턴스(병렬 가능), 문맥 전달 없음(manual_extraction.py:172-181) | 다름 | HYD는 구간 사이 중복·잘린 절차를 경고로만 처리(INSTRUCTION 38-40) | 사용자 결정 |
| 병합 | 의미 유사도 병합 | 같은 ref/SOP id면 첫 제안 유지+경고, 구간 밖 인용 거부(manual_segments.py:68-104) | 다름 | HYD는 결정적이고 검토자가 판단 | 아니오 |
| 검증·교정 | 정의 정적·실행 검사, LLM 교정 5회 | 원문 인용 계약 검증 → 같은 세션 교정 **3회**(instances.py:372 주석은 "product process_validator"를 출처로 적지만 제품 기본값은 5이고 대상도 다르다) | 다름 | 숫자와 출처 표기 불일치(무해) | 아니오(주석만 정정) |
| OCR | 이미지 쪽 항상 OCR | 텍스트 없는 쪽은 `OCR_REQUIRED`로 막고 OCR 없음(manual_sources.py:63-67) | 다름 | 스캔·그림 매뉴얼에서 HYD가 약하다 | 사용자 결정 |

### 이전 주장 판정 (T02)
- "A093/A094의 manual_segments가 제품 청크→병합에 대응(주장 참)" → **불완전.** 가져온 것은 "섹션 단위로 추출하고 합친다"는 개념뿐이다. 분할 기준·크기·순서·문맥·병합 규칙은 모두 다르다. "청크→추출"이라는 표현은 틀렸다: 레포의 청크(1,000/200)는 추출 입력이 아니다.
- manual_segments.py:1-2 docstring "process-gpt-bpmn-extractor: section boundary → per-section extraction → merge" → 출처 표기가 과장됐다.

### 읽지 않은 것
entity_extractor.py 1-280·437-1271(추출 프롬프트 전문), graph.py 716-2773 대부분, neo4j_client.py, executor 나머지 1만 줄, `_create_semantic_chunks`.

---

## process-gpt-memento (659ab9f 2026-10-01, 스냅샷 대비: 동일 — r13-group7이 같은 커밋)

### 이 레포가 하는 방식
- **원본 → 블록**: `document_blocks`(문단·표·그림 설명, 쪽 번호·bbox, sql/document_blocks.sql:9-18), `parser_version`으로 재색인 대상 선택(21).
- **섹션**: `document_sections`가 블록 범위로 문서 전체를 빈틈없이 덮는다. 제목은 **LLM이 고르거나(source=llm)** 크기 상한 때문에 블록 경계에서 자른다(split)(document_sections.sql:1-17).
- **검색**: 섹션 키워드 BM25 모양 점수(같은 파일 40-) + 섹션 벡터 RRF(section_search.py, r13). 청커 기본은 recursive 800자·겹침 100(app/plugins/chunkers/config.py:17-23).
- **인용 위치**: `/document/locate`(app/api/citations.py:203-248)가 **인용문(quote)만 받아** 서버가 원문에서 찾는다. 글자·숫자만 비교하고(`_squash` 182), 생략 표시 사이 400자·다단 PDF 낱말 사이 40자를 허용한 느슨한 재탐색(188-200)을 거쳐 블록·쪽·섹션을 돌려준다.

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 원본 보관 | 블록 테이블+파서 버전 | SQLite 원본 BLOB+쪽 텍스트 sha256+추출기 버전(`pypdf:5.1.0:text-v2`)(manual_sources.py:97-173) | 같은 역할 | HYD는 해시 무결성까지 검사 | 아니오 |
| 인용 좌표 | **quote → 서버가 위치 계산** | **LLM이 start/end를 계산**하고 quote와 정확히 일치해야 함, 아니면 교정(manual_extraction.py:25-26,69-79) | **다름** | EHU40 1차 교정 2회의 원인이 이것이었다(보이지 않는 글리프, HANDOFF A094⑤⑥). text-v2 정규화는 그 경우만 막는다 | **예**(좌표 계산만) |
| 섹션 | LLM 또는 크기 분할, 전체 덮음 | ManualSection은 추출 결과에만 있고 문서 전체를 덮지 않음(page_reviews로 대신) | 다름 | 목적이 다름(검색 vs SOP) | 아니오 |
| 검색 | 키워드+벡터 RRF | 매뉴얼 본문 검색 없음 | 다름 | — | 사용자 결정 |

### 이전 주장 판정 (T01)
- "문서 검색/메모리 스냅샷, 인용 위치 복구는 후보" → 맞음.
- r13-group7 "실측 EHU40 10/10이 교정 0이라 지금 결함은 아님" → **불완전.** 같은 문서 **1차** 실측에서 이 원인으로 교정 2회가 실제로 났다. 2차 0회는 글리프 한 종류를 정규화한 결과이고, 좌표 계약의 취약성 자체는 남아 있다.

### 읽지 않은 것
ingest/pipeline.py 80-400, knowledge_files 1,395, parsers, doc_cards, section_search 전문(r13 재사용).

---

## 출처 판정

HYD 기능마다 출처를 판정했다. 근거 실험은 scratchpad `r14/g4exp/studio_pattern_a.py`(+`_iter2.py`)다. studio 프롬프트의 패턴 A대로 "5~10쪽 샘플을 보고 쓴 정규식 2-pass 파서"를 한 번 써서, HYD의 고정 파서 `manual_review.proposal`과 함께 같은 입력에 돌렸다. 에이전트가 생성한 파서가 아니라 사람이 쓴 대역이다. 실물 EHU40 결과는 개수와 ID만 적는다.

| 문서 | studio형 파서 1회차 | 2회차(단계 표지 `(n)`·`•` 추가) | HYD 고정 파서 | HYD LLM 실측 |
|---|---|---|---|---|
| HM-9 (2.3 KB) | 절 4·SOP 1·단계 6, 0.0 s | — | 절 4·SOP 2(폐지된 SOP-OIL-20 포함) | — |
| HM-FULL (156 KB) | 절 66·SOP 62·단계 335, 0.005 s | — | 같음 66/62/335 | A093: 절 66·SOP 61, 24분(구간 3) |
| HM-FULL3 (466 KB) | 절 198·SOP 194·단계 1,055, 0.016 s | — | 같음 | A093: 절 198·SOP 193, 82분(구간 7) |
| EHU40 실물 80쪽 | 절 92(13장 21, LLM 13장 20 전부 포함)·**절차 8·단계 38**, 0.037 s, 재실행 동일, 앵커 불일치 0 | 절차 45·단계 376(과다: 경고 불릿까지 단계화), LLM과 ID 겹침 19/37, 단계 수 일치 6 | **절 0·절차 0** | A094-2: 절 56·절차 37·단계 140, 15분(워커 2), 교정 0 |

- 정규식은 HM 시험 문서(HYD가 정규식에 맞게 만든 가상 문서)를 0.02초에 LLM과 같은 개수로 뽑는다. 다만 폐지 절차(SOP-OLD-01·SOP-OIL-20)도 절차로 낸다. LLM은 이것을 제외했다.
- 실물 매뉴얼에서 정규식은 13장 절 구조는 맞히지만, 산문·불릿으로 쓴 절차(13.5.2~13.7.3, 5~11장)를 놓치거나 과다 포함한다.

| HYD 기능(파일:줄) | 출처 | 맞는 레포의 방식(파일:줄) | 비교(정확성 / 재현성 / 속도·비용 80쪽 / 실패 복구 / 불규칙 문서 / 수업) | 판정 |
|---|---|---|---|---|
| **결과를 메시지 JSON으로 돌려줌**(manual_extraction.py:41, worker/outcome.py:1-5) | HYD 자체 고안 | studio: 파서가 `_parsed_*.json`을 쓰고 `batch_ingest(경로)`로 적재(service.py:150-152,171; tools.py:528-541) | 정확성 동일 / 재현성 동일 / HYD는 A092에서 결과 160 KB를 한 메시지로 토큰 출력(약 4분)했고 2~3배 문서는 출력 상한에서 깨진다(HANDOFF A092·A093). 파일 경로는 크기와 무관 / 파일은 서버가 다시 읽어 같은 `validate_proposal`을 돌리면 됨 / 무관 / "AI가 파일을 만들고 서버가 검사"가 설명하기 쉬움 | **레포 쪽이 낫다** |
| **구간 분할 40,000자·`#` 제목·쪽 묶음**(manual_segments.py:11-60) | bpmn-extractor에서 개념만 빌림 + 수치·규칙은 HYD 자체 | studio: 추출용 분할 없음, 에이전트가 필요하면 쪽 범위로 나눔(service.py:252). bpmn: LLM SOP 경계(30쪽)·제목 정규식 9종·상한 없음(pdf_extractor.py:293-709) | 정확성: HYD 실측 10/10(EHU40), bpmn은 30쪽 너머 누락 가능(읽은 코드 기준) / 재현성: HYD 분할은 결정적, bpmn SOP 경계는 LLM / 속도: 분할 자체가 통문서보다 22% 느림(A093) / 구간별 실패 격리는 HYD 장점 / PDF에서는 장 중간이 쪽 경계로 끊김 / 보통 | **bpmn보다 HYD가 낫다. studio(파일 출력)와 비교하면 분할의 존재 이유가 사라진다** — 출력 경로를 바꾸면 분할은 병렬화용 선택 사항이 된다 |
| **LLM 직접 추출(구조+절차 모두)**(INSTRUCTION 16-41, "구조화 파서 결과를 정답으로 사용하지 마세요" 19) | HYD 자체 고안 | studio: 패턴 A(구조)는 파서 코드, 패턴 B(기술문서 내용)는 "문장/단락 단위 추출"(94-96). 패턴 B를 누가 수행하는지(에이전트 직접 vs 파서 안 호출)는 프롬프트에 명시되지 않음(추측: 에이전트 직접) | 정확성: 실물 절 구조는 파서=LLM, 절차는 LLM 37 vs 파서 8~19 겹침, 폐지 판단은 LLM만 / 재현성: 파서는 재실행 동일(실측 True). LLM은 같은 입력 반복 실측이 없음(**미검증**. 1차·2차는 지시문이 달라 비교 불가). studio 빌드 전체도 에이전트마다 2,493 vs 1,559 노드 / 속도: 파서 0.04 s지만 studio 빌드 전체는 991 s(403 KB), HYD 900 s(80쪽) — **비슷** / 복구: HYD 교정 3회+사람 검토 / 표: studio는 `extract_tables` 규칙, HYD는 pypdf 텍스트 / 수업: studio가 시각적 | **비슷하다**(구조는 레포, 절차 의미는 HYD). 개선 여지: 구조·앵커는 코드, 절차는 LLM인 A+B 혼합 |
| **고정 정규식 미리보기** `manual_review.proposal`(manual_review.py:15-76, kgadmin.py:18-19) | HYD 자체 고안(패턴 A와 같은 발상, 문서별 생성이 아니라 고정) | studio: 문서마다 에이전트가 파서 생성(150-152) | EHU40 0/0, HM 문서 66/62. 고정 파서는 HYD 가상 번호(`HM-9.2`·`SOP-…`)에만 맞음 / 결정적 / 즉시 | **레포 쪽이 낫다**(범용성). 영향은 작다: 미리보기용 보조 경로 |
| **문자 좌표 앵커를 LLM이 계산**(manual_extraction.py:25-26,69-79) | HYD 자체 고안 | memento: quote → 서버 locate(citations.py:203-248). studio: `source_page`·`_source_id` | 정확성: HYD가 가장 엄격(정확 일치), 유지 / 재현성: 좌표를 서버가 계산하면 결정적 / 교정 회차 비용 감소(EHU40 1차 2회) / 다단·글리프에 memento가 강건 | **레포(memento) 쪽이 낫다**(좌표 계산만 서버로. 정확 일치 검증은 유지) |
| **구간 병합: 첫 제안 유지+경고**(manual_segments.py:68-104) | HYD 자체 고안 | bpmn: 순차 문맥 전달+의미 유사도 병합(graph.py:557-600, config.py:61-118). studio: `_source_id` MERGE | 정확성: HYD는 잘린 절차가 두 부분 SOP가 될 수 있음(미실측) / 결정성은 HYD 우위 / 검토자 계약 유지 | **비슷하다**(차이 무해, 경계 절차 한계는 기록) |
| **스키마 고정 schema.json+validate**(ontology_v2.py:330-393, manual_graph.py:21-22) | HYD 자체(사용자·회의 결정) | studio: 골든 퀘스천에서 런타임 생성, 속성 미강제(tools.py:201-241,640-650) | 정확성·재현성 HYD 우위 / 새 도메인 확장은 studio 우위 | 해당 없음(사용자 결정 유지) |
| **결정적 id·소유·Conflict·되돌리기**(manual_graph.py:25-234) | HYD 자체 고안 | studio: `_source_id` MERGE, 관계 클래스 무시 매칭, 버전 없음(tools.py:567-623) | HYD가 덮어쓰기·오연결을 막음 | **HYD 쪽이 낫다** |
| **검토 피드백 WRONG/MISSING/OK 재주입**(manual_extraction.py:120-146) | 맞는 레포 따름(studio review_feedback, A077) | service.py:456-526 | 같음 | 비슷하다 |
| **merge_warning식 SOP 충돌 사전 경고**(manual_api.py:52-55) | 맞는 레포 따름(studio merge_warning) | tools.py:223-231 | HYD는 경고만 따르지 않고 commit 때 Conflict로 강제 | HYD 쪽이 낫다 |
| **검증: 계약+교정 3회, 전역 감사 Q01~Q22**(instances.py:372, probe_semantic_links.py) | HYD 자체(이름만 "golden questions") | studio: 문서 빌드마다 골든 퀘스천 Cypher 실행 PASS/FAIL·status/confidence 보고, 3회(138,254-274) | HYD에는 문서별 "답할 수 있나" 판정이 없다. 실측 검사(`probe_ingest_quality`)는 개발자가 미리 적은 시험이지 제품 흐름이 아니다 | **레포 쪽이 낫다**(보고 형식과 문서별 질문 검증) |
| **OCR 없음, 텍스트 없는 쪽은 차단**(manual_sources.py:63-67) | HYD 자체 | bpmn: 이미지 쪽 항상 OCR(pdf_extractor.py:66-90). studio OCR은 미연결 | 스캔 매뉴얼에서 HYD는 진행 불가(정직하게 막음) | **레포(bpmn) 쪽이 낫다**(스캔 문서). 요구 여부는 사용자 결정 |
| **읽기: 화이트리스트 템플릿·카드 인용**(mcp_kg.py:1-5, guardrail.py) | HYD 자체 | studio MCP 4도구·HyDE 벡터 | 판단 재현성 HYD 우위, 자유 질문·매뉴얼 본문 검색은 studio 우위 | 비슷하다(목적이 다름) |

### "레포 쪽이 낫다"의 바꾸는 범위 (대략 공수, 제작자 추정)
1. **출력 경로를 파일로**: 에이전트가 작업공간에 `proposal.json`을 쓰고 최종 메시지에는 경로만 낸다. 서버는 그 파일을 읽어 기존 `validate_proposal`·`coverage`를 그대로 적용한다.
   - 대상: `worker/outcome.py`(파일 참조 형식 해석), `worker/workspace.py`(파일 수거, 이미 `files()` 있음), `manual_extraction.py` INSTRUCTION 41행·`result()`, `manual_segments`는 병렬용 선택으로 남긴다.
   - 공수 1~2일 + 실측 재확인(HM-FULL3 1회 약 80분, EHU40 약 15분).
2. **앵커 좌표 서버 계산**: 에이전트는 `{page, quote}`만 낸다. 서버가 `text.find(quote)`로 정확 일치 위치를 찾고, 여러 곳이면 거부·교정, 없으면 교정을 요청한다.
   - 대상: `manual_extraction.validate_proposal` anchor()·INSTRUCTION 25-26, `manual_segments.within`.
   - 공수 0.5일(시험 포함).
3. **문서별 골든 퀘스천 보고**: 추출 요청에 질문 목록(예: "13.5 쿨러 정비 절차의 단계는?")을 받는다. 미리보기 단계에서 제안에 대해 답할 수 있는지 `{question, status, confidence, 근거 절}`로 보고하고, 검토자 verdict를 다음 회차에 넣는다(기존 review_feedback 경로 재사용).
   - 공수 0.5~1일.
4. (선택, 사용자 결정) **패턴 A+B 혼합**: 절 구조·앵커는 에이전트가 쓴 파서 코드로 뽑고 LLM은 절차 의미만 채운다. 공수 2~3일 + 실물 재실측. 위 1~3 없이 이것만 하면 이득이 불분명하다.

---

## 조 요약
| 레포 | 핵심 차이 | 맞춰야 할 것 | 이전 기록 오류 |
|---|---|---|---|
| ontology-studio | 결과를 파일→`batch_ingest(경로)`로 넘겨 분할이 필요 없다. 문서마다 파서 코드를 생성하고 빌드마다 골든 퀘스천을 검증·보고한다 | 출력 경로 파일화, 문서별 골든 퀘스천 보고 | "수 초·동일 결과"(실제 빌드 991 s, 에이전트마다 노드 수 다름) · "hybrid_search_chunks로 근거"(미연결) · "골든 퀘스천 = 감사기, 추가 구현 불필요"(목적이 다름) · `_search_hints`는 답변 모드에 미연결 |
| ontologic | pin한 studio 커밋에 없는 agent-bridge·skills·패턴 A~D 스펙이 있다(비공개 판) | 맞출 기준(공개 코드 vs 스펙)을 사용자에게 알림 | O02 "연결 추적 유지"에 이 불일치 누락. bpmn-extractor pin 8156f77 ≠ 대조한 c7992ce |
| bpmn-extractor | 추출 단위는 크기 상한 없는 SOP/제목 섹션, 순차·문맥 전달, 의미 병합, OCR 기본, 청크 1,000/200은 임베딩용 | 없음(HYD 분할이 30쪽 한계보다 낫다). 주석 출처 정정만 | T02 "청크→병합 대응(참)" → 개념만 같고 세부 전부 다름. instances.py:372 "product process_validator" 3회 ≠ 제품 기본 5회 |
| memento | 인용은 quote만 받고 서버가 위치를 찾는다(느슨한 재탐색) | 앵커 좌표 서버 계산 | r13 T01 "교정 0이라 결함 아님" → 같은 문서 1차 실측에서 교정 2회 발생 |
