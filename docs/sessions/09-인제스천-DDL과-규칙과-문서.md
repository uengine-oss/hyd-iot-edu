# 9. 인제스천: DDL → 입력 데이터, 규칙 → SQL, 문서 → 정비 절차 (2부, 180분: 설명 50 / 실습 100 / 정리 30)

## 이번에 할 것 / 끝나면 보이는 것
회사 DB의 테이블 정의(DDL)를 올려 "어느 표의 어느 열"을 지식 그래프에 넣고(값은 넣지 않는다), 되돌린다. 규칙의 조건을 그 DB에 대한 SQL로 바꿔 실행하고, 매뉴얼 문서에서 정비 절차(SOP)를 만든다.
끝나면 DDL 배치 1건 적재·되돌리기 기록, 규칙에서 만든 SQL과 결과 행, SOP 1개가 남는다.

## 준비
- 포털 **온톨로지 지식 지도** 탭 아래 두 절: **업무 DB 의 DDL 로 입력 데이터 만들기**, **매뉴얼에서 정비 절차 만들기**. Neo4j Browser.
- 입력 파일: `it/supabase/migrations/20261003000002_enterprise.sql`(DDL), `it/portal/www/samples/HM-8_cooler-fan-manual.md`(화면의 "예시 매뉴얼 받기"), `tests/fixtures/manuals/HM-9_oil-degradation-manual.md`.
- API(터미널로 할 때): `POST /api/kg/ddl/preview`, `POST /api/kg/ddl/commit`, `POST /api/kg/ddl/sync`, `GET /api/kg/ingests`, 되돌리기 `DELETE /api/kg/ingests/{batch}?by=…`, `POST /api/kg/rules/sql` (`{"rule":"rule:…"}` 또는 `{"tests":[…]}`), `POST /api/kg/manuals/preview`·`/commit` (`it/process/procsvc/main.py` 974~1090행). 운영 계약: `docs/enterprise-catalog.md`, `docs/handoff/MANUAL_INGESTION.md`.

## 실행 장면
1. [화면] DDL 절 → **DDL 파일 선택** `20261003000002_enterprise.sql`, 원천 연결 `hyd-enterprise`, 데이터베이스 `postgres` → **미리보기** → [관찰] 테이블별 출처 시스템(MES · ERP · CMMS …) 후보와 열 목록 → [확인] `mes_orders`의 납기 열 등 입력으로 쓸 열 3~5개를 고른다.
2. [화면] 적재(검토자 이름 입력) → [관찰] 배치 ID와 적재 결과 → [확인] 적재 이력(`ddlHistory`)에 배치 1건.
3. [화면] Neo4j Browser → `MATCH (i:InputData)-[:SOURCED_FROM]->(s:System) WHERE i.table IS NOT NULL RETURN i.variable, i.schema, i.table, i.column, s.id LIMIT 20` → [확인] 그래프에 값이 아니라 표·열 이름만 있다(값 열이 없음을 눈으로).
4. [명령] `curl -s -X POST 127.0.0.1:8080/api/kg/rules/sql -H 'Content-Type: application/json' -d '{"rule":"rule:standby"}'` (규칙 id는 8회차 2단계 목록에서; 이 API는 2단계에서 적재돼 `table`이 붙은 InputData만 SQL로 바꾼다) → [관찰] 응답 `{"queries":[…], "unmapped":[…]}` — TESTS가 SQL로 바뀐 문장은 `queries`에, 아직 표에 묶이지 않은 변수는 `unmapped`에 온다(적재 전에는 `queries`가 비고 `unmapped`에 `standby_ready`가 남는다 — 이것이 2단계가 필요한 이유) → `queries`의 SQL을 Supabase Studio(http://127.0.0.1:54323) SQL 편집기 또는 `docker exec -it supabase_db_hyd-iot-edu psql -U postgres`에서 실행 → [확인] 결과 행이 규칙 조건과 맞는다(0행도 결과다 — 실패와 구분).
5. [화면] 같은 DDL 절의 이력 표 "인제스천 배치"에서 해당 배치의 **되돌리기**(확인 창 → `DELETE /api/kg/ingests/{batch}`) → [확인] 3단계 질의를 다시 돌리면 그 배치의 InputData가 사라진다(다른 배치·시드는 남는다).
6. [화면] 매뉴얼 절 → **매뉴얼 파일 선택** `HM-8_cooler-fan-manual.md` → **미리보기** → [관찰] 절 제목(`HM-8.1 …`)과 번호 매긴 단계가 SOP 후보로 → 검토자 이름, 고장 유형 연결 선택 → 등록 → [확인] **에이전트 스킬** 탭에 새 SOP 1개, 단계 목록. (이 등록은 조치 후보 활성화와 별개 — 규칙을 자동으로 바꾸지 않는다, 화면 안내문.)
7. [선택, 호스트 워커 필요] 같은 절의 **에이전트 추출 요청** → [관찰] "이 문서의 추출 작업"에 작업 1건, 워커가 집으면 진행 → [확인] 제안 결과를 사람이 검토한 뒤 등록. 적재 직후 "이 문서로 답할 수 있는 질문" 보고(`GET /api/kg/manuals/batches/{배치}/golden-report`).

## 막혔을 때
- 미리보기가 400: DDL에 `CREATE TABLE … ;`가 있어야 한다. 열 주석·타입이 실제 DB와 다르면 적재 뒤 `TYPE_CHANGED · MISSING · COMMENT_CHANGED`로 표시되고 판단에 읽히지 않는다(`probe_ddl_drift.py` 머리말).
- `rules/sql`이 400 "tests 또는 rule 이 필요하다": 규칙 id 오타(그 규칙에 TESTS가 없음). 규칙 목록은 8회차 2단계. `queries`가 비고 `unmapped`만 있으면 DDL 적재(2단계)가 안 된 것이다.
- 매뉴얼 등록이 400: 검토자와 `reviewed=true`가 없다(MANUAL_INGESTION.md).
- 추출 요청이 IN_PROGRESS로 멈춤: 호스트 워커가 없다(RUNBOOK §1 ⑤).
- curl로 한글 JSON을 보내면 Git Bash 코드페이지 때문에 깨질 수 있다 → 파이썬 `urllib`로 보낸다(HANDOFF A118).

## 증거
- `.evidence/sessions/09/`(2026-10-07 제작자, `run.py`·`commands.md`): 1 DDL 미리보기(`POST /api/kg/ddl/preview`, 표 16개 · 시스템 후보 MES·ERP·CMMS… · 입력 후보, 아무것도 쓰지 않음) · 2 적재 이력 조회(현재 0건) · 3 `InputData -SOURCED_FROM-> System` 시스템별 집계(표에 묶인 InputData 0) · 4 `rules/sql` 응답 모양(`queries`/`unmapped`) · 6 매뉴얼 미리보기(`POST /api/kg/manuals/preview`, HM-8 절 2개) · 7 매뉴얼 배치 21건·골든 리포트 GET(`answerable`/`partially_answerable`/`not_yet_answerable`) — **검증됨**. **2단계 적재(commit) · 3단계 적재 뒤 질의 · 4단계 SQL 실행 결과 · 5단계 되돌리기 · 6단계 등록(commit) · 7단계 에이전트 추출**은 공유 그래프를 바꾸거나 호스트 워커가 필요해 이번 실행에서 하지 않음 — **미검증**.
- 제작자 증거: DDL 드리프트 8/8 `.evidence/a115/ddl-drift-4/`(`probe_ddl_drift.py`), 업무 DB 메타데이터 `probe_enterprise_catalog.py`, 적재 지식이 판단에 닿음 9/9 `.evidence/reaudit/reg-a115/knowledge-to-judgment/`(`probe_knowledge_to_judgment.py`), 실제 에이전트 추출 `.evidence/reaudit/a077-ingest-3b/`(HM-9)·`a094-ingest-real-ehu40-2/`(실물 80쪽), 골든 퀘스천 `.evidence/a118/golden_report.json`. 학생 완주 증거 아님.
