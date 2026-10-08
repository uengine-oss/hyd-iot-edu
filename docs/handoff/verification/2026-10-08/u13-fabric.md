# U13 데이터 패브릭 미니 (확정 TODO A11, 2026-10-08 밤)

범위: 메인 `TODO.md` 확정 TODO §0(전제·원칙), §1 **A11**("데이터 패브릭 미니(읽기 전용): 업무 DB·시계열 DB 소스·표/열/샘플, 클래스 ↔ 표·열 연결, 두 DB를 한 질문으로" · 완료 기준 "교차 조회 값·출처, 쓰기 거부, 연결 실패 사유" · 실라버스 41행), §2 **L11**(DDL에서 데이터 위치 연결)·**L15**(진동 MCP 서버 + 업무 DB MCP) 행.

> **HANDOFF §2와의 관계.** HANDOFF §2 확정 방향 표의 "데이터 패브릭은 **구현하지 않고** 후반 설명만"(근거 회의 L63~67 "패브릭까지 안 가더라도", L447 확장 시나리오)을, 사용자 확정 TODO(10-08 밤 "전체 다 구현, 할 일을 TODO 파일로", `mini-processgpt-plan.md` 갱신 절 "U13 데이터 패브릭 미니(9 — HANDOFF §2 '후반 설명만'을 사용자 'todo 다 구현'으로 변경)")에 따라 **가볍게** 구현했다. 새 서비스(MindsDB 등)·새 DB·새 의존성 없음. 이미 있는 두 전용 읽기 계정과 이미 있는 SQL 가드만 쓴다. 설명용 확장 서사(제품으로 가는 길)는 아래 4절에 그대로 남긴다 — 미니는 원리를 손으로 만져 보는 재료이고, 제품(ProcessGPT·ontologic data-fabric)은 마지막에 "전부 갖춘 것"으로 등장한다.

## 1. 만든 것 (비유 한 줄 + 스스로 판정할 체크 질문)

| 덩어리 | 무엇 | 비유 | 체크 질문 |
|---|---|---|---|
| ① 원천 | 업무 DB(Supabase `ent`)·시계열 DB(TimescaleDB `tag_1s`·`feat_1s`·`tag_1m`)의 연결 상태 · 접속 계정 · 읽기 전용 확인 · 표 · 열(형식 · 기본키 · 외래키 · 주석) · 최신 샘플 | 두 창고의 출입 대장과 선반 목록 | 업무 DB를 끄면 "연결됨"이 사람이 읽을 사유로 바뀌는가? 표 이름에 `; drop`을 넣으면 거절되는가? |
| ② 클래스 ↔ 표·열 | 온톨로지 클래스의 식별 키(설비 `code`·센서 `tag`·구동기 `resource`·부품 `partNo`·공급사 `id`)가 원천의 어느 열과 같은 것을 가리키는지 + 판단 입력(InputData)의 원천 링크(`SOURCED_FROM`, DDL 적재로 생긴 물리 바인딩)를 **살아 있는 카탈로그에 대어** OK · 원천에 없음 · 원천 연결 실패 · 표·열 미연결 · DB 밖 값으로 판정 | 지도(온톨로지)의 지명이 실제 창고 선반 번호와 맞는지 대조표 | 그래프의 부품 3개 중 업무 DB `parts`에 실제로 있는 것은 몇 개인가? "긴급 오더 남은 시간"은 왜 "표·열 미연결"인가(→ L11 DDL 적재로 연결)? |
| ③ 두 DB 묶어 보기 | 설비 하나 → 업무 DB의 `assets.code`를 외래키로 가리키는 표들의 행 + DDL 바인딩된 판단 입력 값 + 시계열의 태그별 최신값을, 값마다 출처(원천 · 표 · 열 · 조건 · 실행 SQL · 관측 시각)와 함께 합침. 정의된 교차 조회 3개(납기 ↔ 지금 유온·부하, QMS 고온 로트 ↔ 실제 유온 초과 분, 정비 이력 ↔ 진동 추세). 원천별 SELECT 직접 쓰기(가드). 에이전트 도구 `fabric_query` | 두 창고 장부를 같은 설비 번호로 펼쳐 한 장에 옮겨 적되, 칸마다 어느 장부 몇 쪽인지 적어 둠 | 업무 DB의 납기 오더 번호가 직접 SQL로 읽은 값과 같은가? 시계열을 끄면 업무 DB 값은 그대로 나오고 유온 칸만 사유와 함께 비는가? `delete`를 넣으면 DB에 닿기 전에 거절되는가? |
| ④ 화면 | 포털 "데이터 패브릭"(`fabric.js`, `window.hydFabric.mount(el)`): 요약 카드 4장(두 원천 · 클래스 연결 · 쓰기 없음) → 탭(두 DB 묶어 보기 · 원천과 표 · 클래스 ↔ 표·열). 결과는 답 표가 먼저 보이고 실행 SQL · 행은 접힘 | — | 학생이 10초 안에 "설비 고르고 묶어 보기"를 찾는가? 일부 원천 실패가 숨지 않는가? |

읽기 전용 4중: ① 전용 읽기 계정만 허용(`hyd_enterprise_reader`는 `hydcommon.enterprise.reader_connection`, `hyd_timeseries_reader`는 새 `fabric.timeseries_reader` — 슈퍼유저·생성 권한·RLS 우회 계정이면 연결 직후 거절) ② 모든 조회는 `set transaction read only` + `statement_timeout 5s` + `lock_timeout 1s` ③ 사람이 쓴 SQL·정의된 교차 조회 모두 `hydcommon.sql_read.guard`(SELECT 한 문장, 원천별 허용 스키마·표, 허용 함수, 바깥 LIMIT) ④ 행 제한은 호출자 값이 아니라 바인더가 `min(요청, 200)`으로 붙임(샘플 20). 쓰기 버튼 없음.

정답 미내장: 교차 조회는 원천 값을 그대로 옮길 뿐 판정하지 않는다. 고온 기준(55 ℃)도 코드 상수가 아니라 질의 시점에 지식 그래프의 `(:AnomalyPattern)-[:TESTS]->(:InputData {variable:'ts1'})`에서 읽는다(없으면 사유와 함께 실패). 클래스 ↔ 열 대응(`CLASS_KEYS`)은 "어느 열이 같은 것을 가리키나"라는 구조만 적고, 맞는지는 매번 실제 값으로 대조한다.

## 2. 원본 대조 (파일:줄) · HYD 차이

조사 기준: `scratchpad/refs-A11/` — ontology-studio@20afcde(2026-10-08), ontologic@e72adf1(2026-08-13, `data-fabric`은 서브모듈 `jinyoung/robo-data-fabric`, `.gitmodules:4-6`).

| 원본 | 원본 근거 | HYD 미니 | 차이 판정(① 결함? ② 계약 미충족?) |
|---|---|---|---|
| 원천 카탈로그 = data-fabric(MindsDB) REST :8004 | ontology-studio `openspec/changes/add-datasource-backed-virtual-classes/design.md:80-92`(카탈로그 data-fabric, 실행 text2sql `/direct-sql`), `backend/src/modules/ontology/datasource_api.py:50-110`(datasources · schemas · tables · columns · sample), ontologic `installation.md:116-121`(MindsDB 기동), `docs/catalog-schema.md:116,138` | 원천 2개라 각 DB 시스템 카탈로그(`pg_class`·`pg_attribute`·`pg_constraint`)를 전용 읽기 계정으로 직접 읽음(`common/hydcommon/fabric.py` `CATALOG_SQL`) | 차이 있음, 유지 — 새 서비스 금지(TODO §0 "가볍게"), 원천이 둘이면 연합 엔진 불필요. 확장 서사(4절)에서 "원천이 수십 종이 되면 이 칸이 MindsDB/data-fabric" |
| 가상 클래스 = 인스턴스 0건, 질의 시점 인출 | `design.md:3-25`("결정: 0건") | 그래프에 값을 복사하지 않음. 클래스는 식별 키만, 값은 질의 시점에 원천에서 | 같음 |
| 바인딩 = 클래스 → (datasource, schema, table) + 열 매핑 | `proposal.md:16-18`, `datasource_api.py:142-180`(binding get/put/validate) | 판단 입력(InputData)의 물리 바인딩(`datasource·schema·table·column·assetColumn`, 기존 DDL 적재 `procsvc/ingest.py:186-228`)과 `CLASS_KEYS`(식별 키 ↔ 열). 바인딩 편집은 기존 지식 관리 "업무 데이터 연결"(DDL 미리보기 → 승인 적재)이 유일한 쓰기 경로 | 차이 있음, 유지 — 포털은 읽기 전용(사용자 10-08 화면 원칙). 바인딩 유효성은 `validate`처럼 살아 있는 카탈로그에 대어 OK/MISSING(ddl_sync A087과 같은 판정어) |
| 행위(behavior) = Golden Question당 파라미터화 SQL 템플릿, NL→SQL은 폴백 | `design.md:27-36` | 정의된 교차 조회 3개(`CROSS_QUERIES`, `%(asset)s`·`%(ts1_limit)s` 파라미터) + 원천별 직접 SELECT(`query='sql'`, 에이전트가 씀) | 같은 구조(결정적 경로 우선). NL→SQL은 에이전트(Claude Code)가 SQL을 쓰고 가드가 검사 |
| 보안 3중(타입 바인더 · SQLGuard · row cap) | `design.md:38-78`("LIMIT은 호출자가 절대 정할 수 없다" :74) | 4중(전용 읽기 계정 확인 · 읽기 전용 트랜잭션 · 같은 `sql_read.guard` · 바인더 LIMIT). 값은 psycopg 파라미터로만 | 같거나 강함 |
| 실행 = text2sql `/direct-sql`(SQLGuard) | `design.md:90` | `hydcommon.sql_read.guard`(이미 neo4j-text2sql SQLGuard를 이식한 것, `sql_read.py:1-5`)를 원천별로 | 같음 |
| ProcessGPT F11 | `processgpt-flows.md:26`("데이터 패브릭·What-if 권장, ProcessGPT 본체 의존 아님") | ProcessGPT 본체와 무관한 HYD 자체 기능 | 같음 |

원본 쪽 주의(따라 하지 않음): data-fabric `/api/query`는 인증·SELECT 검증·row limit이 없는 raw 실행이라 원본도 실행을 text2sql로 돌렸다(`design.md:90`). HYD는 처음부터 가드 경로 하나만 둔다.

## 3. 바꾼 파일

| 파일 | 내용 |
|---|---|
| `common/hydcommon/fabric.py` (새) | 원천 · 카탈로그 · 샘플 · 클래스 링크 · 묶어 보기 · 교차 조회 · 실패 사유(`failure_reason`) · `timeseries_reader`. 연결 · 그래프는 주입 |
| `it/process/procsvc/fabric_api.py` (새) | `GET /api/fabric/sources` · `/sources/{s}/tables` · `/sources/{s}/tables/{t}/sample` · `/links` · `/queries`, `POST /api/fabric/query`. 400(입력·거절 SQL) · 503(필요한 원천 전부 실패, 사유) · 200 partial |
| `it/process/procsvc/main.py` (+3줄) | `fabric_api.register(app, driver_factory=_kg)` |
| `compose.yaml` (process +3줄) | `ENTERPRISE_READ_DSN` · `TSDB_READ_DSN`(전용 읽기 계정). process의 쓰기 연결(`SUPABASE_DSN`·`PG_DSN`)은 패브릭이 쓰지 않음 |
| `it/dmn-mcp/dmn_mcp/tools.py` · `server.py` | MCP 도구 `fabric_query(asset, query, limit, sql)` — 포털과 같은 함수. dmn-mcp는 두 읽기 DSN과 Neo4j를 이미 가짐. 워커 허용 목록 `mcp__hyd-dmn__*`에 이미 포함(`agent-worker/worker/settings.py:21`) |
| `it/portal/www/fabric.js` (새) · `index.html`(+메뉴 1 · 화면 1 · script 1) | `window.hydFabric.mount(el)`. 셸이 `#view-fabric`을 열면 스스로 mount(U7 셸이 직접 불러도 됨) |
| `tests/test_fabric.py` (새, 25개) | 아래 5절 |
| `scripts/probe_fabric.py` (새) | 실제 두 원천 라이브 검사(13항목) |

마이그레이션: 필요 없음(`20261008000038` 미사용). 두 읽기 계정 · 권한은 기존 `20261004000003_enterprise_reader.sql`, `it/timescaledb/reader.sql` 그대로.

## 4. 확장 서사 — 현장 DB 수십 종 → 제품

1. **미니(지금)**: 원천 2개(업무 PostgreSQL · 시계열 TimescaleDB). 카탈로그는 각 DB가 스스로 아는 것(`pg_catalog`)을 읽고, 클래스 ↔ 열 대응은 식별 키 6줄과 DDL 적재 바인딩. 교차는 "같은 설비 코드"로 묶어 파이썬에서 나란히 놓는다(원천 간 SQL 조인 없음).
2. **현장**: ERP(Oracle) · MES(MS-SQL) · CMMS(SAP) · Historian(PI · InfluxDB) · QMS · 엑셀이 수십 종. 그때 필요한 것이 이 미니의 각 칸을 키운 것 —
   - 카탈로그 칸 → **연합 질의 엔진**(ontologic data-fabric = MindsDB: 원천을 "데이터베이스"로 등록해 한 SQL 방언으로, `installation.md:116-121`),
   - 클래스 ↔ 열 칸 → **가상 클래스 바인딩 + 행위**(ontology-studio, `design.md:1-36`), 열 의미 복원(A9 옛 DB 뜻 복원과 연결),
   - 가드 칸 → **text2sql SQLGuard + 원천별 권한 · PII**(`design.md:38-78`),
   - 교차 칸 → 원천 간 조인 · 신선도 관리 · 캐시.
3. **제품(실라버스 55행, 회의 L437~449)**: 데이터 패브릭이 원천을 묶고, 온톨로지가 뜻을 주고, ProcessGPT가 그 위에서 사건 한 건 = 처리 건 하나로 판단 · 승인 · 실행을 돌린다. 학생은 미니에서 "읽기 전용 · 출처 · 실패 사유 · 정답 미내장"이 왜 필요한지 손으로 확인한 뒤, 제품이 같은 원칙을 규모로 푼 것임을 본다.

## 5. 시험 결과

- 단위: `tests/test_fabric.py` 25 통과 — 교차 조회 값 · 출처 · 읽기 전용 순서(`set transaction read only`가 첫 문장, 끝은 ROLLBACK) · 바인더 LIMIT, 임계값은 그래프에서(없으면 연결 0회로 실패), 설비 묶어 보기(외래키 표만 · 클래스 없는 태그 표시 · 열 사라진 바인딩 MISSING · 없는 설비 거절), **쓰기 거부 8종**(delete · update · 다중 문장 · CTE 안 delete · 다른 스키마 · 시계열 insert · 허용 밖 표 · pg_sleep → 연결 0회), 샘플 표 이름 주입 거절, **연결 실패 사유 7종**(포트 닫힘 · 비밀번호 · 계정 없음 · 호스트 이름 · 시간 초과 · 쓰기 가능 계정 · 읽기 전용 트랜잭션), 설정 없음, 한 원천 실패 = partial + 사유 · 둘 다 실패 = 오류(503 · MCP UNKNOWN), 클래스 링크 상태, 포털 API 상태 코드, dmn-mcp 봉투(INVALID · UNKNOWN).
- 전체: `.venv/bin/python -m pytest -q` **1309 passed**(worktree, 2026-10-08).
- 라이브(실제 PostgreSQL 16, docker 없이 임시 클러스터): 저장소의 Supabase 마이그레이션 27개 + `seed.sql` 그대로 적용한 `postgres` DB, `it/timescaledb/init.sql`(TimescaleDB 전용 구문만 대역: `time_bucket` = `date_bin` 함수, `tag_1m` = 보통 뷰) + `reader.sql`의 `hyd` DB, 시험용 tag_1s 2시간(설비 3 × 태그 7, 값은 시험 대역). 그래프는 Neo4j가 없어 `instances.cypher` 시드에서 뽑은 고정본(+ DDL 적재 바인딩 1개). `scripts/probe_fabric.py` **13/13 통과**: 두 원천 연결 · 읽기 전용, 샘플, 클래스 링크(구동기 `PumpSelect`는 시계열에 기록 없음, 부품 `P-PMP-SEAL`·`P-FAN-BRG`는 업무 DB `parts`에 없음 — 실제 불일치를 그대로 보임), 교차 조회 값 = 같은 계정 직접 읽기 값(`MO-0930-0412`, TS1), 모든 답에 출처, **쓰기 SQL 연결 전 거절 + 가드를 건너뛴 INSERT도 DB가 25006으로 거절**, 시계열만 꺼짐 = partial + "DB 서버에 연결할 수 없습니다", 틀린 비밀번호 = "읽기 전용 계정 인증에 실패", 쓰기 가능 계정(`postgres`) = "전용 읽기 계정이 아닌 계정으로 연결돼 거부", 설정 없음 = 환경변수 이름. 증거 `.evidence/A11/`(probe-scratch.json · .log · .cmd, other-assets.log, 그래프 고정본 · 생성 스크립트, 화면 shots/1~8).
- 비해피 확인(HYD-02 · 03): HYD-02는 고온 로트 없음(0), HYD-03은 QMS 고온 5분 기록이 있으나 시계열 최근 60분 초과 0분 — 두 원천이 서로 다른 이야기를 하는 경우가 그대로 보인다.
- 화면: 정적 포털 + 같은 `fabric_api`를 띄운 임시 API에서 Playwright로 1360px · 390px 캡처(`shots/`), 페이지 오류 0, 시계열을 끈 상태(`8-ts-down.png`)에서 요약 카드 · 결과 경고 · 칸별 사유 확인.

## 6. 합친 뒤 메인이 할 일 (라이브 확인 경로)

1. 배포 전: `docker compose up -d process`(이 단위가 process에 읽기 DSN 2개 추가). dmn-mcp는 `--profile cliagents` 재빌드.
2. 포털 `http://localhost:8088` → 관리 › **데이터 패브릭** → HYD-01 "묶어 보기", 질문 3개 각각, 원천과 표 › `production_orders`, 클래스 ↔ 표·열.
3. API: `curl localhost:8080/api/fabric/sources`, `curl -XPOST localhost:8080/api/fabric/query -d '{"asset":"HYD-01","query":"due-vs-temp"}' -H 'content-type: application/json'`.
4. 라이브 검사(실제 Neo4j): `ENTERPRISE_READ_DSN=postgresql://hyd_enterprise_reader:hyd-enterprise-read-local@localhost:54322/postgres TSDB_READ_DSN=postgresql://hyd_timeseries_reader:hyd-timeseries-read-local@localhost:5432/hyd NEO4J_URI=bolt://localhost:7687 python scripts/probe_fabric.py --writer-dsn postgresql://postgres:postgres@localhost:54322/postgres --out .evidence/A11/probe-live.json` (시계열 포트는 compose 공개 포트에 맞춘다).
5. 에이전트: 워커 시험에서 `mcp__hyd-dmn__fabric_query` 호출이 콘솔 로그에 보이는지(정답 유도는 강사 몫, 지시문 · 스킬에 넣지 않음).
6. 메인 몫(이 단위가 건드리지 않은 공유 파일): HANDOFF §2 "후반 설명만" 행에 "A11로 미니 구현(이 문서)" 표시 · §9 기록, `docs/sessions/24-…데이터-패브릭.md:9,16`의 "구현하지 않고 설명만" 문구, `docs/src/arch_build.py:252` dmn 도구 14개 → 15개(`fabric_query`), 실라버스 41행 "개발 예정" 지우기.
