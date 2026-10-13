# 5조 메타데이터 — 레포 4개 (+ 맞는 원본 1개 보조 확인)

HEAD: robo-data-catalog cf41148d 2026-09-22 · neo4j-text2sql 25ab12a8 2026-05-13 · process-gpt-glossary 6a29cd98 2026-04-23 · process-gpt-strategy 1db85d3b 2026-07-26 (`references-latest/heads.tsv`).
네 레포 모두 이전 스냅샷과 **같은 SHA**다(`references/robo-data-catalog`·`references/neo4j-text2sql`·`references/a066/process-gpt-glossary`의 `git rev-parse HEAD` 일치, strategy는 r13-group6이 같은 1db85d3를 읽음). 그래서 "스냅샷 이후 바뀐 것"은 없다. 차이는 전부 **읽는 깊이**에서 나왔다.
보조 확인: DDL→그래프 투영의 실제 원본인 robo-data-analyzer는 `D:\work\robo\project\robo-data-analyzer` 49b7734 2026-09-08 로컬 체크아웃만 봤다. 최신 HEAD 수집본이 아니다.

## 결론 먼저

1. **DDL→그래프 투영에 "맞는 레포"는 robo-data-catalog가 아니다.** Catalog README:3-11은 "Analyzer가 TABLE·COLUMN을 생성하고 Catalog는 조회·설명 보완만 한다"고 적고 있다. 투영 원본은 robo-data-analyzer(`pipeline/stages/ddl/parse_ddl_step.py`, `graph/product_writer.py`)다. HYD의 `graph_ingest`·`ingest.plan`은 둘 중 어느 쪽도 따르지 않은 **HYD 자체 설계**다. 열 1개를 InputData 1개로 만들고 TABLE/COLUMN/FK 노드는 없다. 다만 지금 범위에서는 HYD 쪽이 낫다(아래 출처 판정 B).
2. **SQL 생성은 neo4j-text2sql 방식을 따르지 않았다.** 따른 것은 SQL 검사(guard) 하나다. 메타데이터 검색·후보 생성·평가·수정 루프는 Claude Code/Codex가 그때그때 알아서 한다. 이 방식은 사용자 결정이다(HANDOFF.md:50 "DDL을 프롬프트에 넣어 Claude Code가 직접 SQL 생성… 교육용 테이블 몇 개 규모. 사용자 추천 수용"). 그런데 레포 프롬프트가 지키는 **SQL 작성 규칙**이 작업자 상시 지시에는 없다. 그 규칙은 표·열 지어내지 않기, 수정 횟수 제한, 실패를 0으로 바꾸지 않기 같은 것이다. 지금은 시험 스크립트 지시문에만 들어 있다(`scripts/probe_codex_sql_repair.py:24-28`). 이 한 가지는 레포 쪽이 낫다.
3. **BSC 상충 계산은 process-gpt-strategy를 따르지 않았다. 따를 대상이 없었다.** strategy에는 sign·strength·condition으로 경로를 곱하는 상충 계산이 없다. A070이 근거로 든 `age_adapter.py:262-347`은 일반 link/unlink/relationships CRUD다. HYD `hydcommon/bsc.py`는 HYD 자체 고안이다.

## robo-data-catalog (cf41148d 2026-09-22, 스냅샷 대비: 동일)

### 이 레포가 하는 방식
- 책임 경계: TABLE/COLUMN/RULE은 Analyzer가 만든다. Catalog는 조회, 사람 설명 수정, 그리고 자기 소유 FK·READS·WRITES·DATA_FLOWS_TO 생성만 한다(README:5-11). 소유는 노드·관계의 `_owner` 속성(`analyzer`/`catalog`)으로 가른다. 모든 조회는 `_owner='analyzer'` 술어를 붙인다(`graph/scope.py:6-14`, `graph/schema_queries.py:57-60`).
- 노드 계약: TABLE `_id, datasource, database, schema, name, qualified_name, logical_name, description, summary`. description(사람)과 summary(분석)를 섞지 않는다(README:17-36).
- 원천 발견: `GET /robo/tables/discovery` → Data Fabric 테이블 목록 전체를 정렬·중복 검사한 뒤 불변 스냅샷으로 봉인한다. 신원 키는 (catalog, schema, name)이다. 따옴표가 없는 식별자는 casefold로 비교하고 따옴표 식별자는 원문 그대로 둔다. 페이지 커서는 서버가 만든 토큰이다(`samples/discovery.py:34-35, 101-143, 157-256, 310-370`).
- 이름 연결: Analyzer가 코드에서 찾은 객체명을 (schema, object, dblink, case 정책, 열 목록) 신원으로 묶어 Fabric에 정확 해석한다(`samples/object_resolver.py:29-43`). 퍼지 매칭(rapidfuzz 85)은 따로 있다(`samples/resolver.py:27-56`).
- 설명 보강: description이 빈 TABLE만 고른다(`schema_queries.py:30-47`). 샘플 10행과 DDL 주석을 LLM에 준다. 주석이 없는 열은 반드시 "[추정]"으로 시작하고 근거·대안·확인 행동을 3~5줄로 쓰게 한다(`enrichment/description.py:117-195`). 저장은 비어 있을 때만 한다(같은 파일 197-254).
- FK 추론: 원천 DB 함수 `public.infer_fk_candidates` 결과에 이름 유사도·겹침 비율·고유값 수를 섞어 신뢰도 0.85 이상만 `FK {_owner:'catalog'}`로 MERGE한다(`enrichment/foreign_keys.py:19-37, 122-148`).
- 의미 검색: 설명 200개를 요청 때마다 임베딩해 코사인 유사도 0.3 이상을 반환한다. 저장 벡터는 없다(`search/semantic.py:18-78`).
- 드리프트: Catalog에는 없다. Analyzer가 다시 실행되면 analyzer 소유 관계 전부와 TABLE/COLUMN을 뺀 노드를 지운다. TABLE/COLUMN은 `_id`로 MERGE하되 저장돼 있던 description·logical_name을 보존한다(analyzer `graph/product_writer.py:77-106`). DDL에서 사라진 TABLE은 지워지지 않고 상태 표시도 없이 남는다(같은 파일 87-93이 TABLE/COLUMN을 삭제 대상에서 뺌).
- Analyzer의 DDL 투영(보조 확인): sqlglot 다중 방언 파싱을 쓴다. 권위 있는 description은 정식 `COMMENT ON`만이다. `--`·`/* */` 주석은 comment에 보존할 뿐 description으로 올리지 않는다(`ddl_parser.py:1-14`). 파일 사이에 같은 테이블이 다시 정의되면 즉시 실패한다(`parse_ddl_step.py:24-37, 82-85`). id는 `db.catalog.schema.table(.column)`이고 따옴표 여부를 반영한다(`graph/schema/node_ids.py:157-193`).

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 투영 단위 | TABLE·COLUMN·HAS_COLUMN·FK (analyzer) | 선택한 열 → InputData, 테이블 → System. FK·TABLE 노드 없음(`ingest.py:173-216`, `graph_ingest.py:15-17`) | 다름 | HYD 목적은 DMN 규칙 입력 바인딩이다. 조인 탐색은 그래프가 아니라 live `describe_catalog`로 한다 | 아니오(현 규모) |
| 신원 키 | (db, catalog, schema, table[, column]) + 따옴표 | (datasource, catalog, schema, table, column). 따옴표 없는 식별자는 소문자로 바꾼다(`ddl.py:15-16`, `ingest.py:155-160`) | 같음(PG 기준) | — | 아니오 |
| 소유 | `_owner` 속성 2값 | 노드별 `_ingest_history` 저널, 복원·충돌 거절(`graph_ingest.py:77-199`) | 다름 | HYD가 더 강하다(되돌리기 가능) | 아니오 |
| 설명 권위 | `COMMENT ON`만 권위 | `COMMENT ON` 우선. 없으면 `--` 인라인 주석이 InputData 이름이 되고(`ingest.py:121, 206`), 테이블 머리 `--`는 System 힌트가 된다(`ingest.py:70-76`) | 부분 다름 | 정상 경로는 live DB의 `describe_schema`(COMMENT ON)라 영향이 작다. 업로드 DDL에서는 낡은 메모가 이름으로 올라갈 수 있다 | 사용자 결정(작음) |
| 설명 보강 | LLM "[추정]" 표시 저장 | 하지 않음(`enterprise-catalog.md:3`) | 다름 | 주석 없는 열은 에이전트가 표시 없이 추측한다 | 아니오(ent 표 주석 있음) |
| 드리프트 | 감지 없음. 낡은 TABLE은 남음 | 바인딩된 열만 폴링해 OK/MISSING/TYPE_CHANGED를 표시한다. 삭제하지 않고 판단에서 뺀다(`ddl_sync.py:17-64`, `main.py:147-156`, `decide.py:96-98`) | 다름 | HYD가 낫다 | 아니오 |

### 이전 주장 판정
- REFERENCE_ADOPTION:5 (A067) "지도 밖 catalog의 원천/소유/설명 계약을 읽고 … 구현" → **불완전.** Catalog는 투영하지 않는다(README:5-11). 원천 DDL 투영의 원본(analyzer)은 대조하지 않았다. HYD는 `_owner`도 description/summary 분리도 채택하지 않고 자체 저널을 만들었다. "따랐다"가 아니라 "참고 후 자체 설계"가 맞다.
- AUDIT.md:100·109 "object_resolution 명시 datasource/schema/reference key, 물리 식별을 datasource/catalog/schema/table/column으로 분리" → **맞음**(`contracts/object_resolution.py:9-29`, `ingest.py:155-160`).
- `docs/enterprise-catalog.md:37`의 근거 문구 → **맞음(부분)**. 인용한 세 파일은 조회 계약이다. DDL 파싱·주석 권위 규칙의 원본(analyzer `ddl_parser.py`)은 근거에 없다.
- 레포 자체 결함(채택 시 주의):
  - `orchestrator.py:113-114`는 `fk_to_column` 키를 읽는다. 그런데 이벤트는 `fk`로 낸다(`foreign_keys.py:102`). 그래서 fk_persisted 집계가 늘 0이다.
  - `fetch_table_references`가 schema를 버리고(`schema_queries.py:139`) `_id ENDS WITH`로 매칭한다(103, 146). 스키마가 다르고 이름이 같은 표끼리 섞인다.
  - FK 후보 SQL에 schema를 f-string으로 넣는다(`foreign_keys.py:109-112`).

### 읽지 않은 것
`api/lineage.py`·`lineage/sql_extract.py` 본문(정규식 계보, 40행 이후), `integrations/data_fabric.py` 본문, `samples/context.py`, `graph/queries.py`, specs 001~014 본문. analyzer는 DDL 파서 앞 60행, parse 단계, product_writer 75-200만 읽었다.

## neo4j-text2sql (25ab12a8 2026-05-13, 스냅샷 대비: 동일)

### 이 레포가 하는 방식
- 진입: `/react` → `_stream_run_controller_with_progress` → `run_controller`(`routers/react.py:1188-1286`, `react/controller.py:1687`). 이름은 ReAct지만 실제로는 **고정 controller 파이프라인**이다.
- 메타데이터: `build_sql_context`가 질문을 임베딩한다. 이어서 HyDE·유사 질의·값 매핑을 병렬로 모으고, 테이블 벡터 검색과 rerank, FK 사전 조회, 테이블별 열 검색, 스키마 XML, 열 값 힌트(enum 캐시), FK XML, 값 해석, 제안을 거친다. 마지막에 가벼운 모호성 해소 질의를 실제로 실행한다(`build_sql_context_parts/orchestrator.py:104-344`).
- 그래프 계약: `:Table` NODE KEY(db, schema, name), `:Column` fqn UNIQUE, 벡터 인덱스(`core/neo4j_bootstrap.py:85-140`, `scripts/init_schema.py`). FK는 `Column-[:FK_TO_COLUMN]->Column`이다(`build_sql_context_parts/neo4j.py:301`). 이 레포는 그래프를 **읽기만** 하고 DDL에서 만들지 않는다.
- 생성: 후보 3개(온도 0.3). 프롬프트 규칙은 SELECT만, 주석·세미콜론 금지, "context XML에 있는 표·열만", 값 힌트의 정확한 값 우선, LIMIT 부여다(`prompts/controller_sql_candidates_prompt.md`). 요구사항은 LLM으로 미리 뽑는다(`controller.py:1720-1735`).
- 검사(`tools/validate_sql.py`): ① SQLGuard(파싱, SELECT만, 금지 키워드, join·서브쿼리 깊이. LIMIT은 바꾸지 않음. `core/sql_guard.py:40-90`). 실패하면 LLM 수정을 한 번 하고 guard를 다시 돈다(143-167). ② PostgreSQL `EXPLAIN`(analyze=False) 계획을 LLM이 판정한다. 오류가 나면 규칙 수정, 그다음 LLM 수정, 다시 guard 순서다(302-340). 예상 시간이 상한을 넘으면 FAIL과 suggested_fixes(375-395). ③ preview 실행.
- 판정·수정 루프: PASS여도 preview 0행·전부 NULL이면 hard reject한다. 이어서 LLM rubric으로 MUST 요구 충족을 채점한다(`controller.py:1797-1836, 1839-1935`). 실패한 검사만 고치는 repair는 온도 0.0, 후보당 최대 4회, 정체 2회면 다른 후보로 바꾼다(`controller.py:1354-1366`, `prompts/controller_repair_prompt.md`). 그래도 실패하면 triage가 ask_user/context_refresh/give_best_effort 중 하나를 고른다(`controller.py:1400-1416, 1531`).
- 용어/값 매핑: `ValueMapping {natural_value, column_fqn} → code_value`(`routers/cache.py:266-289`)와 enum 캐시다.

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 메타데이터 공급 | 그래프 + 벡터 검색으로 고른 부분 스키마 | 전체 live 카탈로그 JSON/DDL(`enterprise_mcp/tools.py:57-67`, `catalog.py`), 시계열은 information_schema + 최근 5분 태그(`agentsvc/tools/mcp_tsdb.py:48-62`) | 다름 | 표 16개 규모라 검색이 필요 없다(사용자 결정 HANDOFF.md:50) | 아니오 |
| SQL 검사 | SQLGuard. allowlist는 이름만 비교하고 ReAct 경로에선 넘기지 않음(`validate_sql.py:145`) | scope 기반 ent/public 표만 허용, 함수 허용목록, 바깥 LIMIT ≤200 강제, 읽기 전용 트랜잭션 + 5초 timeout(`hydcommon/sql_read.py:37-80`, `tools.py:40-43`) | 다름(HYD 강화) | HYD가 안전하다 | 아니오 |
| 비용 검사 | EXPLAIN + LLM 판정 | statement_timeout 5초만 | 다름 | 작은 표라 timeout으로 충분하다 | 아니오 |
| 오류 반환 | FAIL·fail_reason·suggested_fixes·selected_sql | `error_kind INVALID/UNKNOWN`, message, statement(`enterprise_mcp/server.py:94-97`). sqlstate 42xxx는 INVALID(`dmn_mcp/tools.py:34-38`) | 비슷 | — | 아니오 |
| 수정 루프 | 결정론 controller, 횟수 제한, rubric | 에이전트 자율. 상시 지시(`agent-worker/worker/workspace.py:19-44`)에 SQL 규칙·횟수 제한 없음. 시험 지시문에만 "최대 두 번"(`probe_codex_sql_repair.py:24-28`) | 다름 | 표·열 지어내기, 무한 재시도, 실패를 0으로 바꾸는 일을 상시 규칙이 막지 않는다 | **예(규칙 몇 줄만)** |
| 0행 처리 | hard reject | 규칙 조회에서는 0행이 정상(DECISIONS.md:169) | 의도된 차이 | — | 아니오 |
| 값→코드 매핑 | ValueMapping·enum 캐시 | 없음 | 다름 | ent의 코드 값이 적어 지금은 영향이 작다 | 사용자 결정 |

### 이전 주장 판정
- HANDOFF.md:94 "robo-data-text2sql: Neo4j에 Table/Column/FK 그래프 + ReAct SQL 생성(큰 서비스)" → **불완전·일부 틀림.** 그래프는 이 레포가 만들지 않고 읽는다. "ReAct"는 고정 controller다. 그래프 계약(`:Table`/`FK_TO_COLUMN`, (db, schema, name) 키)은 현재 catalog/analyzer 계약(`:TABLE`/`:COLUMN`, `FK` 관계 + `from_column`/`to_column`, `_id`/`_owner`. catalog README:17-33, analyzer `product_writer.py:100-136`)과 **맞지 않는다**. 같은 그래프를 그대로 공유할 수 없다.
- REBUILD.md:39 "README만 읽은 현재 상태" → **낡음.** AUDIT.md:226(A022)에서 validate_sql·repair 프롬프트를 이미 읽었다.
- AUDIT.md:226 "SQLGuard→EXPLAIN→preview, FAIL/selected_sql/suggested_fixes, 규칙수정 후 LLM수정을 다시 guard에" → **맞음**(`validate_sql.py:143-167, 302-340`).
- DECISIONS.md:119 "bare table 이름만 비교하는 allowlist" → **맞음**(`sql_guard.py:132-146`). 덧붙일 점: ReAct 경로는 allowlist를 아예 넘기지 않는다(`validate_sql.py:145`). `parse_one` + `exp.Select` 검사 때문에 UNION도 거절된다(`sql_guard.py:63-70`).
- `ddl.py:3` "SQLGlot at the version pinned by neo4j-text2sql" → **맞음**(uv.lock 1436-1437의 27.24.2 = `it/process/requirements.txt:8`).
- REPOSITORY_REVIEW.md:69 "robo-data-text2sql과 같은 HEAD" → 미검증(이번에 robo-data-text2sql을 보지 않음).

### 읽지 않은 것
`build_sql_context_parts/*` 각 흐름 본문(table_search 508줄, column_search 475줄, neo4j.py 907줄), `rubric_judge.py`, `sql_autorepair.py`, controller 1990-2476(탐색·전환 루프 본문), `routers/react.py` 나머지, 이벤트·CEP·캐시 후처리.

## process-gpt-glossary (6a29cd98 2026-04-23, 스냅샷 대비: 동일)

### 이 레포가 하는 방식
- 저장은 PostgreSQL `terms(name, description, status DEFAULT 'Draft', synonyms text[], batch_id)`와 owners/reviewers 링크 테이블이다(`supabase/init/10-app-schema.sql:45-74`).
- 검색은 name·description·synonyms를 동시에 LIKE로 찾는다. 공백 제거와 토큰 폴백이 있다(`glossary_manage_service.py:619-640`).
- 상태 변경은 권한 검사 없이 UPDATE한다(`glossary_manage_service.py:802-830`).
- **용어↔물리 컬럼 연결 테이블이 없다.** 테이블 목록은 glossaries/domains/owners/tags/terms/term_*/business_calendar*뿐이다(`10-app-schema.sql:11-105`). `confirmed_mapping`은 업로드한 엑셀의 "어느 칸이 용어명인가" 매핑이다(`glossary_router.py:108-114`). DB 컬럼 의미 매핑이 아니다.

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 업무 이름 | 용어 + 동의어 배열 | InputData.name = COMMENT 원문 1개(`ingest.py:206`), Measure.aliases만 있음(schema.json Measure) | 다름 | 질문 표현이 흔들리면 에이전트가 직접 메운다 | 사용자 결정(T06 권고 그대로) |
| 용어→컬럼 | 없음 | 물리 5요소로 직접 연결 | 다름 | 이 기능의 맞는 원본은 glossary가 아니라 text2sql ValueMapping·catalog description이다 | — |
| 상태·롤백 | 무권한 status, batch DELETE | 저널 복원·참조 시 거절 | 다름 | HYD가 강하다 | 아니오 |

### 이전 주장 판정
- REFERENCE_ADOPTION:45 T06 행 → **맞음**(위 줄 번호와 일치). 덧붙일 점 두 가지. (1) glossary에는 용어↔컬럼 연결이 없다. (2) 채택 후보 "InputData 동의어 배열"은 아직 구현되지 않았다(`graph_ingest.py:15-16` INPUT_FIELDS에 synonyms 없음).

### 읽지 않은 것
`frontend/*`, `glossary_bulk_service.py` 330-1100·1160-1330, LLM 클라이언트, 업무 달력.

## process-gpt-strategy (1db85d3b 2026-07-26, 스냅샷 대비: 동일)

### 이 레포가 하는 방식 (BSC 부분, r13-group6이 안 읽은 범위)
- 그래프 스키마: Strategy·KPI·Initiative·Process·Task·User·Agent·Team·Skill·Canvas. 관계는 HAS_SUB_STRATEGY·HAS_KPI·IMPACTS_KPI·PERFORMS·USES_SKILL 등이다(`app/graph/schema.py`). **sign·strength·condition을 가진 지표 간 영향 관계가 없다.**
- KPI 달성률: (현재-기준)/(목표-기준). decrease 방향이면 뒤집고 0~150%로 자른다(`impact_analysis.py:77-96`).
- 영향 분석: KPI → IMPACTS_KPI → Process → Task → PERFORMS 평균 처리시간으로 병목 후보를 정한다. 정렬은 결정론이고 LLM 서술은 보조다(`impact_analysis.py:1-24, 219-404`).
- 기여도: KPI 안에서 0~1로 정규화한 share에 전략 importance(기본 3)를 곱해 합산한다(`contribution.py:1-20, 247-271`, `strategy_ops.py:57`).
- A070이 인용한 `age_adapter.py:262-347`은 `link`(속성이 있으면 unlink 후 CREATE)·`unlink`·`relationships` CRUD다. BSC 계산이 아니다.
- 보조 관찰(5조 범위 밖): ontologic `what-if-simulator/simulation_engine.py`에 CAUSES polarity/lag 전파가 있다. 하지만 기준값과 주요 경로가 하드코딩된 데모다(318-333, 457-468).

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 상충 계산 | 없음 | Skill-AFFECTS→INFLUENCES≤4→Measure 경로. sign을 곱하고 strength high 1/medium 0.6/low 0.3을 곱한다. TRUE/FALSE/UNKNOWN 조건, 미확인 증가분(`hydcommon/bsc.py:11, 66-120`, `docs/bsc-conditions.md:7-21`) | 해당 없음 | 원본 없이 HYD가 고안. 가중치는 HYD 가정이라고 문서에 이미 적혀 있다(bsc-conditions.md:17, 21) | 아니오 |
| 지표 달성 | 기준·목표·방향 달성률 | Measure 목표·경고·위험 임계값 + 방향(schema.json Measure) | 다름 | 목적이 다르다(조치 순위 vs 성과 대시보드) | 아니오 |
| 원천 동기화 | ontology_sync 폴링 MERGE | `ddl_sync`·`scm_sync`가 이 방식을 빌림(docstring) | 빌림 | r13-group6 판정과 같다 | 아니오 |

### 이전 주장 판정
- REFERENCE_ADOPTION:50 P03 행 → **맞음**(r13-group6 정정을 반영함).
- REFERENCE_ADOPTION:82 (A070)·`bsc-conditions.md:56` "P03 age_adapter 262~347의 관계 양 끝·종류·속성 보존을 HYD BSC 경로 근거에 반영" → **불완전(출처 과대).** 인용 코드는 일반 그래프 CRUD다. strategy에는 상충 계산 자체가 없다. bsc-conditions.md:56이 "BSC 조건 실행 엔진이 아니며"라고 덧붙였지만, "출처: HYD 자체 고안, 참고 레포 없음"으로 적어야 정확하다.

### 읽지 않은 것
`measurement.py`·`strategy_ops.py`·`chat.py`·`ontology_agent/` 본문, `contribution.py` 50-245.

## 출처 판정

| HYD 기능(파일:줄) | 출처 | 맞는 레포의 방식(파일:줄) |
|---|---|---|
| A. DDL 파싱 `procsvc/ddl.py:1-94`, `ingest.py:80-137` | 다른 레포 빌림: neo4j-text2sql의 SQLGlot 버전·AST 방식 + 자체 | robo-data-analyzer `pipeline/stages/ddl/ddl_parser.py:1-14`(COMMENT ON만 권위), `parse_ddl_step.py:24-85` |
| B. DDL→그래프 투영 `ingest.py:173-216`, `graph_ingest.py:84-139` | HYD 자체 고안(`ingest.py:11-14`가 직접 밝힘) | analyzer `graph/product_writer.py:77-136`(TABLE/COLUMN MERGE by `_id`, 전체 교체). catalog는 투영 안 함(README:5-11) |
| C. 신원 키 `ingest.py:155-160` | 맞는 레포 따름 | analyzer `node_ids.py:157-193`, catalog `samples/discovery.py:34-35, 111-117` |
| D. 소유·되돌리기 `graph_ingest.py:77-199` | HYD 자체 고안 | catalog/analyzer `_owner` 속성 + 전체 교체(`scope.py:6-14`, `product_writer.py:77-93`) |
| E. 드리프트 `ddl_sync.py:1-64` | 다른 레포 빌림(process-gpt-strategy ontology_sync) | 맞는 레포에는 드리프트 감지가 없다. 낡은 TABLE이 남는다(`product_writer.py:87-93`) |
| F. SQL 검사 `hydcommon/sql_read.py:37-80` | 맞는 레포 따름(강화) | neo4j-text2sql `core/sql_guard.py:40-146`, `tools/validate_sql.py:143-395` |
| G. SQL 생성 메타데이터 `enterprise_mcp/tools.py:57-67`, `mcp_tsdb.py:48-62` | HYD 자체(사용자 결정 HANDOFF.md:50) | text2sql `build_sql_context_parts/orchestrator.py:104-344` |
| H. SQL 오류 수정 루프(에이전트 자율, `worker/workspace.py:19-44`) | HYD 자체(규칙 없음) | text2sql `controller.py:1354-1366, 1839-1935`, `prompts/controller_repair_prompt.md` |
| I. 규칙→SQL `ingest.py:269-317` (`/api/kg/rules/sql`) | HYD 자체 고안 | 해당 원본 없음(text2sql은 자연어→SQL) |
| J. 업무 용어 `ingest.py:206`(COMMENT=이름) | HYD 자체 | glossary 동의어(`glossary_manage_service.py:619-640`), text2sql ValueMapping(`routers/cache.py:266-289`) |
| K. BSC 상충 `hydcommon/bsc.py:11-120`, `procsvc/bsc_conditions.py` | HYD 자체 고안 | strategy에 없음. 달성률·기여도뿐(`impact_analysis.py:77-96`, `contribution.py:247-271`) |

### 빌림·자체 고안 줄의 비교

| 줄 | 정확성 | 재현성 | 속도·비용 | 실패 시 복구 | 수업 설명·재현 | 판정 |
|---|---|---|---|---|---|---|
| A 파싱 | 레포는 `--` 주석을 권위로 올리지 않는다. HYD는 COMMENT ON이 없으면 `--`를 이름으로 쓴다 | 같음(둘 다 결정론) | 같음 | 같음 | HYD는 PostgreSQL 하나라 쉽다 | **비슷하다(차이 작음).** 정상 경로가 live COMMENT ON이다. 업로드 DDL만 해당 |
| B 투영 | HYD는 규칙 입력에 필요한 열만 다뤄 정확하다. 조인 경로를 그래프에서 못 찾는다 | 같음 | HYD가 가볍다 | HYD는 배치 단위로 되돌린다. 레포는 다시 실행해 교체한다 | HYD가 쉽다(열→판단 입력이 바로 보임) | **HYD 쪽이 낫다**(현 16표). 표가 수십 개 이상이거나 그래프 조인 탐색이 필요해지면 레포 방식이 필요하다. 그 시점은 사용자 결정 |
| D 소유 | HYD는 남의 수정과 충돌하면 거절한다. 레포는 `_owner`만 본다 | 같음 | 레포가 단순하다 | HYD가 이전 상태로 복원한다 | 레포가 설명하기 쉽다 | **HYD 쪽이 낫다**(되돌리기 요구 원문2 L253~293) |
| E 드리프트 | HYD는 사라진 열·바뀐 형식을 판단에서 뺀다. 레포는 감지하지 못한다 | 같음 | 폴링 1회는 information_schema 1질의 | HYD는 노드를 지우지 않는다 | HYD가 시연 가능하다(`probe_ddl_drift.py`) | **HYD 쪽이 낫다** |
| G 메타데이터 | 작은 스키마에선 전체 공급이 누락이 없다. 레포는 검색에서 빠뜨릴 수 있다 | HYD는 live라 매번 같다 | HYD는 임베딩·벡터 DB가 없다 | — | HYD가 쉽다 | **HYD 쪽이 낫다**(현 규모) |
| H 수정 루프 | 레포: rubric으로 의미까지 확인한다. HYD: 상시 규칙이 없다 | 레포가 높다(온도·횟수 고정) | 레포는 질문당 LLM 호출이 여러 번(요구 추출, 후보, EXPLAIN 판정, rubric, repair) | 레포는 횟수 제한·triage가 있다. HYD는 작업 timeout뿐 | HYD가 단순하다 | **레포 쪽이 낫다(규칙 부분만).** controller·rubric은 가져오지 않는다 |
| I 규칙→SQL | 매개변수 SELECT, 실행 안 함, 미매핑 보고 | 결정론 | 0비용 | — | 쉽다 | **HYD 쪽이 낫다**(원본 없음) |
| J 용어 | 동의어·값 매핑이 없어 표현이 흔들리면 에이전트 추측에 기댄다 | 레포가 높다 | 레포는 저장·검색이 필요 | — | 비슷 | **레포 쪽이 낫다(부분)**, 다만 현 질문 3종 규모에선 영향이 작다 → 사용자 결정 |
| K BSC | 원본이 없다. HYD 가중치는 정성 가정이다(문서에 명시) | 결정론 | 0비용 | 원문이 바뀌면 UNKNOWN | 쉽다 | **HYD 쪽이 낫다**(비교 대상 없음). 출처 표기만 고친다 |

"레포 쪽이 낫다"의 바꾸는 범위:
- H: `it/agent-worker/worker/workspace.py` CONSTITUTION에 SQL 절 5~6줄을 넣는다. 내용은 "describe_catalog로 표·열을 확인한 뒤 SELECT", "결과에 없는 표·열을 쓰지 않음", "오류는 보존하고 같은 의도로 최대 2회 수정", "조회 실패를 0·없음으로 바꾸지 않음", "규칙 조회의 0행은 정상일 수 있음"이다. 또는 enterprise·hyd-dmn `query` 도구 설명에 같은 문장을 넣는다. 공수는 0.5일 안쪽이다. 확인은 `scripts/probe_business_questions.py`·`probe_codex_sql_repair.py` 재실행인데, 실제 LLM을 호출하므로 비용이 든다. 실행 전에 확인이 필요하다.
- J(선택): `graph_ingest.INPUT_FIELDS`에 `synonyms`를 넣고, ingest preview에 입력 칸을 만들고, `describe_catalog`/`inputs` 응답에 싣는다. 1~1.5일이다. 사용자 결정 사항이다.

## HYD 쪽에서 새로 본 결함 (적대적 검토)
1. **DB 주석(설명) 변경을 감지하지 않는다.** InputData.name은 COMMENT 원문이다(`ingest.py:206`). 승인 재검사는 설명이 바뀌면 새 검토를 요구한다(`enterprise-catalog.md:27`). 그런데 `ddl_sync`는 열 존재와 형식만 본다(`ddl_sync.py:22-23`, `col_description` 없음). 그래서 DB에서 주석만 고치면 재적재 전까지 그래프에 옛 의미가 남는다. 수정 범위는 `ddl_sync.py`에 COMMENT_CHANGED 상태 추가와 `probe_ddl_drift.py` 사례 1개, 약 0.5일이다. 맞는 레포(analyzer)도 저장된 description을 보존하므로(`product_writer.py:103-104`) 레포에서 가져올 방식은 아니다.
2. 형식 매핑이 부분 문자열이다. `'int' in 'interval'`이라 interval이 number가 된다(`ingest.py:30, 51-55`). `ddl_sync.family`도 같은 표를 쓴다(`ddl_sync.py:27-32`). 그래서 integer→interval 변경을 TYPE_CHANGED로 잡지 못한다. 작음.
3. `ddl_sync`는 `SUPABASE_DSN`으로 information_schema를 읽는다(`main.py:152`). 판단은 `hyd_enterprise_reader`로 읽는다. 권한이 다르면 동기화는 OK인데 실제 조회는 실패할 수 있다(**추측**, 실측 안 함).

## 조 요약
| 레포 | 핵심 차이 | 맞춰야 할 것 | 이전 기록 오류 |
|---|---|---|---|
| robo-data-catalog | 투영하지 않음. 투영은 analyzer. HYD는 자체 InputData 투영·저널 | 없음(HYD가 낫다). 단 투영 원본을 analyzer로 바로 적을 것 | A067 "catalog 계약 구현"은 불완전(맞는 원본 analyzer 미대조) |
| neo4j-text2sql | 검사만 따랐다. 생성·수정은 에이전트 자율 | **작업자 상시 지시에 SQL 규칙·수정 2회 제한 넣기** | HANDOFF:94 "그래프 보유·ReAct" 불완전. 그래프 계약이 catalog와 불일치. REBUILD:39 낡음 |
| process-gpt-glossary | 동의어는 있으나 용어↔컬럼 연결 없음 | 동의어(선택, 사용자 결정) | T06 맞음. 권고 미구현 상태를 표에 적을 것 |
| process-gpt-strategy | 상충 계산 없음 | 없음 | A070·bsc-conditions:56 출처 과대(age_adapter는 CRUD) |

## 읽지 않은 것 (조 전체)
위 각 절에 적은 범위 밖 전부. 실행 검증은 하지 않았다(읽기 전용). robo-data-analyzer는 최신 HEAD 수집본이 아닌 로컬 체크아웃 49b7734다. HYD는 `catalog.py`(enterprise-mcp)·`scm_sync.py`·`probe_scm_sync.py`·`decide.py` 본문 대부분·`hydcommon/bsc.py` 본문 전체를 열지 않았다(bsc.py는 grep으로 핵심 줄만 봤다).
