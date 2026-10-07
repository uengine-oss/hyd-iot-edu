# ontology-studio 최신 HEAD(6a229be, 2026-07-09)의 문서 인제스천 — HYD와의 대조 (2026-10-07 20:10, 읽기 전용)

사용자 질문: "온톨로지 스튜디오는 엄청 큰 문서를 어떻게 처리하나? 우리가 bpmn-extractor를 쓴 게 문제 아닌가?" → 최신 레포를 clone해 코드로 확인.

## ontology-studio가 하는 방식(코드 근거)

| 단계 | 내용 | 근거 |
|---|---|---|
| 골든 퀘스천 → 스키마 | 인텐트·골든 퀘스천에서 클래스·관계를 도출해 `schema_create_class`/`schema_create_relationship_type`, 질문별 그래프 경로를 `_schema_design.json`에 저장 | `backend/src/modules/agent_session/service.py` ONTOLOGY_BUILD_SYSTEM_PROMPT Phase 1 |
| 소스별 파서 생성·실행 | 업로드 파일을 `ls → execute`로 5~10쪽 샘플 탐색 → 패턴 판별(A 문서 구조→노드 / B 내용 추출→엔티티·관계 / C 구조화 데이터→노드) → **에이전트가 `/workspace/output/_parser_<소스>.py`를 써서 샌드박스에서 실행** → `_parsed_<소스>.json`(nodes·relationships) | 같은 프롬프트 Phase 2, "PDF: pdfplumber. 먼저 5-10페이지 샘플로 구조 파악 후 전체 파싱", 2-pass(전체 텍스트 합치기 → 정규식으로 구조 단위 분할, 모든 노드에 content 필수) |
| 일괄 적재 | `batch_ingest(nodes_json)` — 파일 경로를 받아 노드는 `MERGE (n:_Entity:<class> {_source_id})`, 속성 문자열은 2,000자에서 자름, 관계는 from/to id로 | `backend/src/modules/ontology/tools.py:520~` |
| 검증 루프 | `graph_stats` → 골든 퀘스천마다 실제 Cypher 실행 → PASS/FAIL → 스키마 갭은 Phase 1, 데이터 갭은 Phase 2로, **최대 3회** → `_search_hints.json` 생성 | Phase 3 |
| 문서 청크 색인(별도) | PDF OCR(페이지) 또는 텍스트를 4,000자 가상 페이지로 → `_split_text`가 tiktoken으로 **1,000토큰 청크(EMBEDDING_CHUNK_MAX_TOKENS), 겹침 1/8** → 임베딩 → Neo4j Document/Chunk + 전문·벡터 인덱스. `hybrid_search_chunks` 도구는 있으나 **6a229be의 빌드·답변 도구 목록에 연결돼 있지 않다**(`agent_session/service.py`에 호출 0건; A113 4조 확인 — 처음 판본의 "에이전트가 근거를 꺼냄"은 오류) | `document_indexing/service.py:347~`, `settings.py:108`, `document_indexing/tools.py` |

요점: **큰 문서를 LLM 답변 한 번에 실어 받지 않는다.** LLM은 파서 코드를 만들고 결과를 **파일**로 쓰며, `batch_ingest(파일 경로)`가 적재한다. 다만 빌드 전체는 여전히 에이전트가 수행하므로 **빠르지도 결정적이지도 않다**: ontologic 실측(specs/004 spec.md:195-197) 도로교통법 PDF 403 KB 빌드 Claude Code 2,493노드·991초, Codex 1,559노드·361초 — 에이전트마다 결과가 다르다. "수 초·동일 결과"는 생성된 파서를 **다시 돌릴 때만** 맞다(처음 판본의 오류, A113 4조 지적).

## HYD(현재)와의 차이

| 항목 | ontology-studio | HYD | 판단 |
|---|---|---|---|
| 추출 주체 | 에이전트가 생성한 파서 코드(파서 재실행은 결정적; 빌드 전체는 에이전트라 비결정적) | Claude Code 워커가 구간(제목 경계 40,000자·페이지 범위)마다 LLM으로 직접 추출 | **다름.** 소요는 비슷하다(studio 403 KB PDF 361~991초, HYD 80쪽 약 900초). A113 4조 실험: studio 패턴 A 방식 정규식 파서는 실물 EHU40에서 장·절 구조는 LLM과 일치했으나 절차는 37개 중 8개만 찾음 → 구조는 코드, 절차 의미는 LLM이 낫다 |
| 스키마 결정 | 골든 퀘스천에서 톱다운 | 회의 요구로 고정한 schema.json(46 클래스·72 관계) | 같은 역할(둘 다 질문이 스키마를 정함). HYD는 질문 22개가 감사기(`probe_semantic_links`)·정답 Cypher(`queries.cypher`) |
| 검증 | 골든 퀘스천 Cypher 실행, 3회 반복 | 감사 22항목·validate·왕복 7/7·교정 루프(앵커 불일치 시 재추출) | 역할 같음. HYD의 앵커(원문 글자 위치) 정확 일치 검증은 studio에 없음(studio는 content·chunk_ref·source_page 속성으로 출처 보존) |
| 긴 문서 분할 | 추출엔 분할 없음(코드가 전체 처리); 검색용 청크 1,000토큰 | 추출용 구간 40,000자(bpmn-extractor의 청크→추출→병합 구조) | 목적이 다름. bpmn-extractor는 ontologic 플랫폼의 정식 하위 레포(.gitmodules)이므로 출처는 문제 없음 |
| 패턴 | A 구조→노드 / B 내용→엔티티·관계 / C 구조화 데이터 | 매뉴얼은 B에 가깝게 LLM 추출, DDL은 C(graph_ingest) | 제조사 매뉴얼(장-절-소절-절차 번호)은 studio 기준으로는 **패턴 A+B 혼합** — 구조는 정규식 파서, 절차 의미는 LLM |

## 새 세션의 결정 과제(사용자에게 올릴 것)

1. **맞출 것인가**: 매뉴얼 인제스천을 studio 방식(에이전트가 파서 코드 생성 → 코드가 전체 파싱 → batch 적재 → 골든 퀘스천 검증 루프)으로 바꾸고, HYD의 앵커 검증·검토 피드백은 유지한다. 장점: 속도(분→초)·비용·재현성. 비용: 파서 생성 단계 구현 1~2일, 실물 PDF로 재실측.
2. **유지할 것인가**: 지금 방식(LLM 구간 추출)을 두고, 차이를 교재에서 "두 방식"으로 설명한다. 수업 재현성은 지금도 확보(10/10).
3. ~~어느 쪽이든 골든 퀘스천 루프는 이미 HYD 감사기·정답 Cypher로 같은 역할을 하므로 추가 구현 불필요.~~ **정정(A113 4조):** 목적이 다르다. HYD Q01~Q22는 그래프 전체 연결 감사이고, studio의 골든 퀘스천은 "이 문서를 넣은 뒤 이 질문에 답할 수 있나"를 문서별로 본다. 문서별 골든 퀘스천 보고가 필요하다.
4. **A113 4조 판정(우선):** 분할이 필요했던 진짜 원인은 결과를 LLM 마지막 메시지 JSON으로 받는 출력 경로다(A092 160 KB). studio처럼 에이전트가 작업공간에 결과 파일을 쓰고 서버가 그 파일을 검증·적재하게 바꾸면 분할은 병렬 처리용 선택 사항이 된다(`worker/outcome.py`·`workspace.py`·`manual_extraction.py`, 1~2일 + 재실측). 원문 인용 위치는 서버가 찾는다(memento `citations.py:203-248`, 0.5일). 상세는 `r14-g4-ontology.md`.

원칙(사용자 10-07): 다르면 레포 쪽으로 맞추는 것이 기본. 단 수업용 안전선을 깨지 않는 범위에서.
