# A9 옛 DB 뜻 복원 (2026-10-08 밤, worktree `a9-legacydb`)

범위: `TODO.md` 확정 TODO §0 원칙, §1 **A9**("코드 이름 열 → AI 의미 후보·근거·확신도 → 사람이 승인한 것만 반영", 완료 기준 "승인 전 반영 0, 승인한 것만 반영·감사"), §2 **L11**(DDL에서 데이터 위치 연결 ↔ 지식 관리 업무 데이터 연결 · A9 · A11). 실라버스 v6 24행.

비유 한 줄: 라벨이 떨어진 약병 선반에서, 조수(AI)가 병 모양·내용물·옆 병과의 관계를 보고 "이건 아마 소독약" 쪽지를 붙여 두면, 약사(사람)가 쪽지마다 맞다·고친다·틀렸다를 판정하고 **약사가 맞다고 한 라벨만** 장부(온톨로지)에 옮겨 적는다.

## 1. 결론
1. 열 이름이 코드인 옛 DB 덤프(DDL + INSERT)를 올리면, 서버가 열마다 **관찰**(이름 조각 · 주석 · 샘플 값 분포 · 키 관계 — 선언과 추론을 구별)을 만들고, 그 관찰과 온톨로지 목록(상태 변수 · 성과 지표 · 설비 태그)을 고정 입력으로 **에이전트 작업 한 건**(HYD 워커 경로, 제품 모양 userTask + agentMode)을 연다. AI 경로가 없으면(instance 모드 아님 503 · 워커 연결 안 됨 503 · 그래프 못 읽음 502) 작업을 열지 않고 사유를 돌려준다.
2. AI 후보(뜻 · 단위 · 연결 · 근거 · 확신도)는 서버가 **관찰에 근거가 있는지** 검사한다. 샘플이 없는 열의 "샘플" 근거, 목록에 없는 연결 대상, 설비 태그와 하나도 안 겹치는 "설비 식별 열", 근거 없음인데 뜻을 채운 후보는 거부되어 같은 세션의 에이전트에게 정정 요청으로 돌아간다(A077 정정 고리 재사용). "근거 없음"은 정상 답이다.
3. 사람은 후보마다 **승인 · 고치기 · 거부**(또는 보류)한다. 검토는 고칠 수 없는 기록으로 저장되고 결정마다 감사 기록(`DDL_MEANING_APPROVED/EDITED/REJECTED` + `DDL_MEANING_REVIEWED`, 전/후 값 포함)을 남긴다. 같은 후보를 다르게 검토한 기록을 나란히 두고 "이 검토로 미리보기"로 반영 결과를 비교한다.
4. DDL 미리보기는 `meaning_review`로 고른 검토의 **승인 · 고치기만** 반영한다: 입력 데이터 이름(= 승인한 뜻 + 단위, 기존 `input_name` 규칙), 온톨로지 연결(`InputData -REPRESENTS-> StateVariable|Measure`, 스키마에 이미 있는 관계), 설비 식별 열(`assetColumn` → 규칙 → SQL의 `where "EQP_CD" = %(asset)s`). 거부 · 보류 열은 그대로 "표 열" 이름, 연결 없음. 적재(commit)는 검토가 승인하지 않은 이름 · 연결 · 식별 열을 400으로 거부한다.
5. 회사 DB 원본은 바꾸지 않는다. 승인한 뜻은 DB 담당자에게 줄 `COMMENT ON COLUMN` SQL로만 보여 준다(실행 안 함). 정답 매핑은 코드 · 시드 · 예시 파일 어디에도 없다.

## 2. 데이터 리니지
| 단계 | 무엇이 | 어디에 | 실패 · 분기 |
|---|---|---|---|
| 출생 | 옛 DB 덤프(DDL + INSERT) | 포털 업로드 → `POST /api/kg/ddl/preview` | CREATE TABLE 없음 400, INSERT 구문 오류는 미리보기에 사유로(`legacy.error`), COPY · INSERT…SELECT는 "읽지 않음" 안내 |
| 변환 1 (관찰) | 열별 이름 조각 · 형 · 샘플 분포 · 선언 키 · 추론 키(값 겹침 ≥ 0.8) · 설비 태그 겹침 | `legacy_meaning.profile()` | 주석 있는 열은 대상 아님, 대상 0이면 400 "뜻을 복원할 열이 없습니다" |
| 변환 2 (제안) | 열별 후보 | 에이전트 작업 `legacy_column_meaning`/`task:legacy-meaning`의 출력 `meanings` | 근거 없는 후보 → 정정 요청(같은 작업), 워커 미연결 503, instance 모드 아님 503 |
| 저장 | 사람 검토(결정 · 전/후 · 메모) | `legacy_meanings.sqlite3`(프로세스 상태 옆, 불변 행) + 감사 로그(`_audit`, Kafka audit) | 승인 불가(근거 없음 후보) 400, 후보 전 검토 400 |
| 변환 3 (반영) | 승인 · 고치기만 → 열 주석 → InputData 이름 · REPRESENTS · assetColumn | `apply_comments` → `ingest.plan` → `apply_links` | 다른 DDL의 검토 400 |
| 소비 | 그래프 적재 | `graph_ingest.commit` — REPRESENTS도 소유 이력(journal)에 들어가 "되돌리기"로 함께 지워짐 | 검토 밖 이름 · 연결 400, 연결 대상 노드 없음 409 |

## 3. 원본 대조와 HYD 차이
원본: ontologic `e72adf1`(2026-08-13) `specs/008-legacy-metadata-to-ontology/spec.md`, robo-data-catalog `cf41148`(2026-09-22, `scratchpad/refs-A9/robo-data-catalog`).

| 원본 (파일:줄) | 원본이 하는 것 | HYD | 판정 |
|---|---|---|---|
| spec 008 `spec.md:246-253` FR-001~005 | 코드 이름 · FK 없음 · 주석 없음 · 값은 원본 그대로인 예제 | `it/portal/www/samples/legacy-plant-db.sql`: 표 3 · 열 23(전부 뜻 없음), FK · 주석 없음, INSERT 24행 | 같음 |
| spec 008 `spec.md:254-259` FR-006~007 | 원본 + 이름 매핑으로 난독화본 생성, 매핑 = 정답지(자동 채점) | 매핑 파일 없음 | 차이 있음, 유지 — 사용자 지시 "정답 매핑 넣지 않음"(정답은 강사가 수업에서 유도). ① 결함 아님 ② 계약은 오히려 매핑 금지 |
| spec 008 `spec.md:266-272` FR-009~015 | 프로시저 코드 · 샘플로 설명 생성, 근거 기록, 근거 없으면 "근거 없음", 재실행이 이전 결과 훼손 안 함 | 샘플 · 이름 · 키 관찰로 후보, 근거 kind별 서버 검사, `no_evidence` 정식 답, 검토는 불변 행(재실행 · 재검토가 이전 기록을 덮지 않음) | 같음(프로시저 코드 근거는 없음 — 실습 덤프에 프로시저 없음, 차이 있음, 유지) |
| spec 008 `spec.md:268-269` FR-011~012 | 조인에서 관계 추론, 선언 FK와 구별 | 같은 이름 열 · 값 겹침을 `keys.inferred[].kind='추론'`, 선언은 `keys.declared` | 같음 |
| spec 008 `spec.md:279-282` FR-018~020 | 후보에 근거, 확신 부족이면 자동 바인딩 안 함 | 자동 반영 자체가 없음 — 모든 반영이 사람 결정 | 더 엄격, 유지 |
| robo-data-catalog `enrichment/description.py:46-87` | 샘플 10행 + 열 정보 → LLM JSON | 관찰 요약(분포 · 키) + 온톨로지 목록 → 에이전트 작업(LLM 직접 호출 아님) | 차이 있음, 유지 — HYD의 AI 경로는 워커(A116 제품 모양), 처리 과정이 처리 건으로 남는다(A1 블랙박스 0) |
| robo-data-catalog `enrichment/description.py:151-178` | 주석 없는 열은 "[추정]" + 근거 · 대안 · 확인 행동 | `evidence[]` · `alternatives[]` · `confidence`, 확인 행동은 사람 검토 단계 | 같음(형식만 구조화) |
| robo-data-catalog `enrichment/description.py:89-115, 206, 236` | 생성한 설명을 **바로** 카탈로그에 씀(빈 설명만) | 승인 전 반영 0 — 검토의 승인 · 고치기만 계획에 들어가고 적재 때 다시 검사 | 차이 있음, 유지 — A9 완료 기준이 "승인한 것만 반영" |
| robo-data-catalog `enrichment/foreign_keys.py:39-62` | 값 겹침(≥0.8) · 이름 유사도 · 고유값 수로 FK 추론, 확신도 ≥0.85면 FK 관계 저장 | 같은 0.8 겹침을 **근거로만** 보여 줌, FK 관계는 만들지 않음 | 차이 있음, 유지 — 온톨로지 스키마 고정(새 관계 종류 금지) |

HYD 쪽 기존 경로 재사용: 문서 추출 제안 `it/process/procsvc/manual_extraction.py:176-202`(작업 열기) · `:260-276`(결과 읽기) · 정정 고리 `instances.py:311-320`, 골든 퀘스천 `manual_golden.py:36-48 · 92-97`. 업무 데이터 연결 화면 `it/portal/www/hitl.js:545-608`, DDL 엔드포인트 `it/process/procsvc/main.py`(`/api/kg/ddl/preview` · `commit`). enterprise-mcp `describe_catalog`(`it/enterprise-mcp/enterprise_mcp/tools.py:83-89`)는 **라이브 DB의 실제 열 주석**을 그대로 읽는 도구라 바꾸지 않았다 — 승인한 뜻은 그래프(InputData 이름 · REPRESENTS)에 들어가고, 라이브 DB 주석은 DB 담당자가 `COMMENT ON` SQL을 실행했을 때만 바뀐다("원본은 지키고").

## 4. 바꾼 파일
| 파일 | 내용 |
|---|---|
| `it/process/procsvc/legacy_meaning.py` (새) | INSERT 샘플 읽기, 열 관찰, 에이전트 작업 정의 · 시작 · 결과, 후보 근거 검사, 검토 검사, 반영(`reflection` · `apply_comments` · `apply_links` · `expected_input`), `COMMENT ON` SQL |
| `it/process/procsvc/legacy_meaning_store.py` (새) | 검토 불변 기록(SQLite, `legacy_meanings.sqlite3`) — 마이그레이션 불필요 |
| `it/process/procsvc/legacy_meaning_api.py` (새) | `POST /api/kg/ddl/meanings` · `GET …/{instance}` · `POST …/{instance}/reviews`, 감사, 적재 검사(`Bridge.check_commit`) |
| `it/process/procsvc/main.py` | 등록 7줄, 미리보기 `legacy` 요약 + `meaning_review` 반영 6줄, 적재 검사 1줄 |
| `it/process/procsvc/ingest.py` | `validate_plan`이 `represents` · `meaningReview` 허용(값 검사) |
| `it/process/procsvc/graph_ingest.py` | 소유 이력이 `REPRESENTS`도 관리(읽기 · 복원 · 되돌리기), 대상 노드 확인. A9 이전 이력(`rel` 키 없음 = SOURCED_FROM)과 같게 비교 |
| `it/process/procsvc/manual_extraction.py` | 결과 검사 분기에 A9 계약 추가, 정정 가능 계약에 추가(2줄) |
| `it/portal/www/legacyMeaning.js` (새) | 지식 관리 › 업무 데이터 연결 안 접기 섹션 "옛 DB 뜻 복원": 요약 칩(뜻 없는 열 · 샘플 행 · 후보 상태) → 후보 받기 카드 → 진행 표시(`live-dot`, 정정 횟수 · 사유) → 근거 있는 후보 표(뜻 · 연결 · 확신도 · 근거 요지는 펼친 채, 관찰은 접기) + "근거 없음" 열은 접기 → 열별 결정 → "검토 저장 · 미리보기에 반영"(행동 하나) → 반영 카드(검토자 · 반영 입력 · 주석 SQL 접기 · "원래대로") → 검토 기록(다른 검토로 미리보기) |
| `it/portal/www/hitl.js` | DDL 미리보기에 컨테이너 1줄 + `hydLegacy.mount` 호출 3줄, "선택 반영"이 반영 중 검토 유지 |
| `it/portal/www/index.html` | 스크립트 1줄, 파일 안내에 "옛 설비 DB 예시" 내려받기 |
| `it/portal/www/samples/legacy-plant-db.sql` (새) | 실습용 옛 DB(정답 매핑 없음, 근거 없는 열 `C_PRS_B` 전부 NULL · 모호한 `ST_CD` · 설비 태그 밖 `HYD-00` 포함) |
| `tests/test_legacy_meaning.py` (새) | 37개 |

## 5. 시험 (`.evidence/A9/`)
- `tests/test_legacy_meaning.py` 37 통과. 일부러 깨뜨려 잡히는지: 근거 없는 후보 12가지 거부 · 에이전트 정정 요청 1, 잘못된 검토 8가지 거부, 적재 변조 5가지(거부한 연결 끼워 넣기 · 승인 안 한 열에 검토 표시 · 이름 바꾸기 · 연결 바꾸기 · 없는 검토) 거부, 다른 DDL의 검토 거부, 그래프에 없는 연결 대상 409.
- 완료 기준 대응: **승인 전 반영 0** `test_before_approval_nothing_of_the_ai_reaches_the_plan` · `test_ddl_preview_and_commit_routes_reflect_only_the_review`(검토 없는 미리보기에 `represents` 0), **승인한 것만 반영** `test_after_review_only_approved_meanings_and_links_are_in_the_plan` · `test_graph_journal_writes_represents_only_for_the_approved_input_and_clear_removes_it`(그래프 REPRESENTS = 승인한 1건), **거부 반영 0** 같은 시험의 거부 열(`C_TMP_O`) 이름 · 연결 그대로, **감사** `test_http_flow_request_read_review_and_audit`(요청 · 결정별 · 요약 4건, 거부의 전/후 · 메모), **AI 경로 없음 = 명확한 오류** `test_no_ai_path_is_a_clear_error_not_an_empty_success`(503 · 503 · 502, 작업 0건).
- 전체 `pytest -q`: 1321 통과(기준선 1284 + 37) — `.evidence/A9/pytest-full.txt`. JS `node --check legacyMeaning.js hitl.js` 통과, 포털 모듈을 node vm에서 후보 · 반영 카드 상태로 그려 영문 id 노출 0 확인(`scratchpad/a9/render.js`).
- 한계(정직하게): Neo4j는 단위 시험에 없어 `graph_ingest`의 REPRESENTS는 문장 단위 가짜 그래프(`FakeGraph`)로만 검증했다. 합친 뒤 라이브 검증에서 실제 Neo4j로 적재 → REPRESENTS 1건 → 되돌리기로 0건을 한 번 확인해야 한다. 실제 워커(Claude Code)가 이 계약으로 후보를 내는지도 라이브에서 확인(정정 고리는 단위 시험).

## 6. 라이브 확인 경로 (합친 뒤, instance 모드 + 워커)
1. 포털 지식 관리 › 업무 데이터 연결 › "옛 설비 DB 예시" 내려받기 → 파일 선택, 원천 연결 `legacy-plant` → 미리보기. 입력 데이터 표에 `T_EQP01 C_PRS_A` 같은 코드 이름, 접기 "옛 DB 뜻 복원 — 뜻이 없는 열 23개 · 덤프 샘플 행 24개".
2. "AI에게 뜻 후보 묻기" → 진행 표시 → 후보 표. 워커를 끈 상태면 "AI 일꾼(워커)에 연결할 수 없어…" 오류.
3. 몇 개 승인 · 하나 고치기 · 하나 거부 → "검토 저장 · 미리보기에 반영" → 입력 데이터 이름이 승인한 뜻으로, 거부한 열은 그대로. 감사 기록에 결정별 행.
4. 다른 담당자 이름으로 다르게 검토 → 검토 기록에서 "이 검토로 미리보기"로 반영 결과 비교, "검토 빼고 미리보기"로 원래대로.
5. 적재 → Neo4j Browser `MATCH (i:InputData)-[:REPRESENTS]->(v) WHERE i.datasource='legacy-plant' RETURN i.name, v.name` = 승인한 연결만. 연결 배치 "되돌리기" → 0건.

## 7. 사용자가 스스로 판정할 체크 질문
- 후보를 하나도 결정하지 않고 적재하면, 그래프의 입력 이름에 AI가 쓴 말이 하나라도 들어가는가? (들어가면 실패)
- 거부한 열의 이름 · 연결이 미리보기나 그래프에 남는가? (남으면 실패)
- 감사 기록만 보고 "누가 · 언제 · 어느 열을 · AI는 뭐라 했고 · 사람은 무엇으로 바꿨는지"를 말할 수 있는가?
- 샘플이 전부 비어 있는 `C_PRS_B`에 AI가 "샘플 근거"를 대면 화면에 후보로 나오는가? (나오면 실패 — 정정 요청으로 돌아가야 한다)
- 워커를 끄고 후보를 요청하면 "성공"처럼 보이는 빈 표가 나오는가, 사유가 나오는가?

## 8. 인계 메모
- HANDOFF §9 · DECISIONS는 병렬 단위 충돌을 피하려고 이 worktree에서 고치지 않았다. 메인이 합칠 때 §9에 "A9 옛 DB 뜻 복원" 체크와 이 문서 링크, §2에 "AI 후보는 반영 전 사람 검토 — 승인 · 고치기만 계획 · 그래프로"를 넣는다.
- 마이그레이션 `20261008000039`는 쓰지 않았다(검토 저장은 프로세스 상태 옆 SQLite).
