# 검토 · 보강 — scripts · 캡스톤 키트 · 온톨로지 · 문서 (merge-preview)

> 2026-10-09 · 범위: `git diff 7fa5664..HEAD`의 scripts/**, students/**, it/neo4j/**, docs/**(RUNBOOK) 와 시험 3개(G4 · G5 · G8)
> 점검표: review-checklist.md(헌법 §2·§3, 프로젝트 CLAUDE.md §4, 클린코드). 대조 설계: 본 레포 c2f2188 `docs/handoff/verification/2026-10-09/capstone-lab.md`
> 형식: 발견 → 분류(결함 / 의도된 차이 / 오해 / 근거 부족) → 조치(파일:줄) → 검증(검증됨 / 실패 / 미검증 / 해당 없음)
> 규칙: docker · 컨테이너 · DB 쓰기 · 워커 없음. 커밋 안 함(작업 트리에만).

## 0. 진행 상태
- [x] 점검표 · 헌법 · 프로젝트 CLAUDE.md · capstone-lab.md 통독
- [x] 범위 diff 통독(scripts/ontology_v2.py · project_student_flow.py, students/_template 3개, it/neo4j/templates t0_* 3개, RUNBOOK 1줄, 시험 3개)
- [x] 시작 시점 시험: 3개 파일 23 passed (수정 전 기준선)

## 1. 확정 스키마 v2 변경 0 · 비밀값 · RUNBOOK

| 발견 | 분류 | 조치 | 검증 |
|---|---|---|---|
| `git diff 7fa5664..HEAD -- it/neo4j/v2/` 줄 수 0, 작업 트리 변경도 0 | 해당 없음(정상) | 없음 | 검증됨 |
| `hydpass123`(ontology_v2 · project_student_flow 기본 암호), DDL `change-me` | 의도된 차이 — compose.yaml 257 · 287행 등 레포에 이미 있는 로컬 개발 기본값, DDL 은 자리표시자. 새 비밀값 없음 | 서버(T4)는 자리표시자 암호로 뜨지 않게 고침(3절) | 검증됨(grep) |
| RUNBOOK 95행 `PLANT_SIM_URL` 행: 기본 `http://plant-sim:8000`, process 가 ot-net 에도 붙음, 로그 문구 `설비 시뮬레이터 복구 요청 실패` | 주장 = 실물 일치: compose.yaml 389행 기본값 · process `networks: [it-net, ot-net]` · `.env.example` 39행 · instance_mode.py 53 · 534행 | 없음 | 검증됨(정적 대조, 실제 Linux 서버 완주는 미검증) |

## 2. G4 이름 공간 검사기 (`scripts/ontology_v2.py`) · 지식 지도 템플릿

| # | 발견 | 분류 | 조치(파일:줄 — 수정 뒤 기준) | 검증 |
|---|---|---|---|---|
| G4-1 | `load_extra` 가 ns 칸이 없으면 폴더 이름으로 몰래 채움. 더 나쁜 경우: 출발본을 `students/s07/` 로 복사하고 ns `"s00"` 을 안 바꾸면 그대로 s00 으로 검사(조용히 남의 이름 공간) | 결함(조용한 폴백) | ns 필수, `students/<폴더>/` 면 ns = 폴더 이름 강제(`_` 로 시작하는 출발본 폴더 제외), 깨진 JSON · 객체 아님도 파일 좌표 있는 ValueError. CLI 는 추적 대신 한 줄 + 종료 1 — `scripts/ontology_v2.py:43-59`, `cmd_check_extra` · `cmd_validate_ns` 742-768 | 검증됨(시험 `test_the_namespace_comes_from_the_file_and_must_match_the_student_folder`) |
| G4-2 | `check_extra` 가 속성 항목을 안 봄 — `type` 없는 속성 · 없는 자료형("text") · values 없는 enum 이 통과, `from: "Meeting"`(글자) 이면 글자 단위로 끝점 오류가 쏟아짐, cardinality 값 미검사 | 결함(검사 구멍) | `_prop_types` · `_check_props`(v2 가 쓰는 자료형만, enum 은 values 필수), from/to 는 이름 목록, cardinality 는 v2 값(1:1 · 1:N · N:1 · N:M) — `scripts/ontology_v2.py:62-154` | 검증됨(형식 시험에 5문구 추가) |
| G4-3 | `validate(cross=False)` 가 `integrity()` 결과를 **오류 글 앞머리 "input "** 으로 걸러 냄 — 문구가 바뀌면 조용히 깨지고, 학생 자기 InputData 의 출처 없음도 같이 숨김 | 결함(깨지기 쉬운 우회 · 검사 누락) | `cross` 제거, `integrity(..., input_scope=)` 로 "출처 검사는 내 입력에만"을 구조로 표현 — `scripts/ontology_v2.py:557` validate · `:629` integrity · `:190` validate_ns | 검증됨(`test_input_source_rule_still_applies_to_my_inputs_but_not_to_base_inputs`: 내 입력은 잡고 v2 입력은 안 잡음) |
| G4-4 | 이름 공간 노드가 0개여도 `validate --extra` 가 PASS(빈 성공). 특히 G8 이 7687 에 적재하고 검사기 기본 접속은 7688 이라 그대로 따라 치면 빈 그래프 PASS | 결함(빈 성공) | `validate_ns` 가 0개면 "적재했는가, --uri 가 적재한 그래프인가" 로 실패, 출력에 `@ <uri>` — `scripts/ontology_v2.py` validate_ns · cmd_validate_ns. G8 안내 문구도 `--uri` 포함(4절) | 검증됨(`test_an_empty_namespace_fails_instead_of_passing`) |
| G4-5 | 다른 이름 공간 노드가 내 클래스 레이블을 쓰면 같은 결함이 3줄(ns 틀림 · 접두어 틀림 · 다른 이름 공간) | 결함(경미, 보고 중복) | `ns_rules` 가 다른 ns 노드는 한 줄로만 — `scripts/ontology_v2.py` ns_rules | 검증됨(한 줄 단언) |
| G4-6 | `_graph_rows` 와 `cmd_validate` 가 같은 Neo4j 읽기 질의를 두 벌, PASS/FAIL 출력도 세 벌 | 클린코드(중복) | `cmd_validate` 가 `_graph_rows` 재사용, `_report` 하나로 | 검증됨(기존 시험 통과) |
| G4-7 | 지식 지도 관계 템플릿: 학생 모드에서 한쪽이 다른 학생 노드인 관계도 내보냄 → 노드 목록에 없는 끝(매달린 선) | 결함(경미, 노드 · 관계 조건 불일치) | `it/neo4j/templates/t0_graph_edges.cypher:12-15` 다른 끝은 같은 학생 또는 ns 없음만 | 검증됨: Neo4j 5.26.31(라이브, **읽기 세션**)에서 식 의미 실측 — s01 모드 (s01,null)=참 (s01,s01)=참 (null,null)=null(제외) (s01,s02)=거짓 |
| G4-8 | t0_* 3개 템플릿 문법 · 기본 보기 회귀 | — | 없음 | 검증됨: 5.26.31 읽기 세션에서 실행 — 기본 보기(`$ns=''`) 노드 411 · 관계 918 이 7fa5664 판 템플릿과 같은 순간 같은 수(라이브 그래프가 408→411 로 자라는 중이라 같은 시점 쌍으로 비교). 학생 모드 실제 데이터 표시는 미검증(그래프에 ns 노드 0개, 쓰기 금지) |
| G4-9 | 공용 Neo4j 에 두 학생이 같은 클래스 이름(Meeting)을 쓰면 서로 "다른 이름 공간 노드가 내 클래스를 쓴다"로 실패 | 의도된 차이 — 설계 G6 이 노트북마다 스택 하나를 권장. 공용 서버면 클래스 이름 충돌이 실제 문제라 시끄럽게 실패하는 편이 맞음 | 없음 | 해당 없음 |
| G4-10 | ProcessGPT ontology-studio 는 스키마 id 로 가름, 여기는 노드 ns 로 가름 | 의도된 차이(머리말에 "차이 있음, 유지" 기록됨) | 없음 | 해당 없음 |

## 3. G5 학생 업무 표 읽기 MCP 출발본 (`students/_template/mcp_table_reader/server.py`) · DDL(`table.sql`)

| # | 발견 | 분류 | 조치 | 검증 |
|---|---|---|---|---|
| G5-1 | `STUDENT_DSN` · `STUDENT_SCHEMA` 가 없으면 모듈 기본값(`stu_s00` · 암호 `change-me`)으로 조용히 뜸 — 학생이 환경 변수를 빠뜨려도 남의 스키마 · 자리표시자 암호로 붙으려 함 | 결함(조용한 폴백) | 기본값 삭제, `config_from_env()` 가 빠진 키 이름 · 예시를 말하며 SystemExit, DSN 암호가 `change-me` 그대로면 거절. `TableReader(schema)` 는 필수 인자 — server.py `config_from_env` · `__main__` | 검증됨(`test_the_server_does_not_start_without_its_contract_settings`) |
| G5-2 | `limit=0` 을 몰래 최대(200)로 바꿈, `limit="5"` 는 `int()` 의 ValueError 가 봉투 밖으로 샘, `True` 는 1 로 통과 | 결함(조용한 변환 · 실패 경로 누락) | `_limit()`: None 만 기본값, 정수(불 제외) 1~200 아니면 INVALID | 검증됨(파라미터 시험 3개 추가) |
| G5-3 | `columns="name"`(글자)이면 글자 단위 칸 오류, 같은 칸 두 번이면 dict 로 접혀 칸 목록과 행이 어긋남 | 결함(경미) | columns 는 글자 목록만, 중복 제거(`dict.fromkeys`) | 검증됨 |
| G5-4 | 칸 조회가 `to_regclass(f'"{schema}"."{table}"')` 로 이름을 **문장 글자에 이어 붙임**(앞에서 목록 대조를 하니 주입은 막히지만, 따옴표가 든 표 이름이면 깨짐) | 결함(경미, 주입 불가 원칙과 어긋남) | `pg_attribute ⋈ pg_class ⋈ pg_namespace` 에 `nspname = %s and relname = %s` 값 바인딩 | 검증됨(시험 + **실제 Supabase PG(54322) 읽기 전용 트랜잭션에서 실행**: ent 스키마 표 27개 · 칸 목록 정상) |
| G5-5 | 매직 넘버 `connect_timeout=5` · `[:200]` · `[:120]` · 포트 `8311` | 클린코드 | `CONNECT_TIMEOUT_S` · `ERROR_TEXT_MAX` · `DEFAULT_PORT` · `PLACEHOLDER_PASSWORD`, 오류 첫 줄 자르기 `_first_line` 하나로 | 검증됨 |
| G5-6 | 실패 경로 시험 없음: 권한 있는 계정 거절, DB 오류 → UNKNOWN, 연결 실패 | 시험 구멍 | `test_a_privileged_account_is_refused_and_its_connection_closed`, `test_database_failures_come_back_as_unknown_with_the_reason` 추가 | 검증됨 |
| G5-7 | 읽기 전용 · 시간 제한이 실제 PG 에서 먹는가 | — | 없음 | 검증됨(실측, 쓰기 없음): `set transaction read only` 뒤 `show transaction_read_only`=on, `create table` → `ReadOnlySqlTransaction` 거절, `statement_timeout=10ms` 에서 `pg_sleep(0.5)` → `QueryCanceled`. where 값 바인딩 · 없는 칸 `code; drop` → INVALID · 잘림(truncated) 실측 |
| G5-8 | 예시 행에 비해피 가지: 고객 회의 좌석 4(<6, 좌석 미달) · 필수 참석자 `none`(무응답) · 비필수 거절 | 정상 | 시험으로 고정(`test_ddl_example_rows_walk_the_unhappy_branches`), DDL 머리말에 "change-me 면 서버가 안 뜸" 한 줄 | 검증됨(정적) |
| G5-9 | 서버가 `0.0.0.0` 에 열림 — 같은 망에서 학생 표 읽기가 가능 | 근거 부족 — 포털 컨테이너가 `host.docker.internal` 로 닿아야 하고(Linux 는 docker0 주소) 127.0.0.1 로 묶으면 Linux 에서 안 닿음. 수업 망 정책이 정해지면 `MCP_HOST` 로 좁힐 일 | 없음 | 미검증 |
| G5-10 | 실제 `stu_<ID>` 스키마 · 읽기 계정을 만들어 DDL 을 돌린 적 없음, FastMCP HTTP 기동 · 포털 연결 검사 통과 | — | 없음(DB 쓰기 · 서비스 기동 금지 범위) | **미검증**(도구 표시 · 읽기 판정은 `mcp_check.read_only_verdict` 로 단위 검증) |

## 4. G8 흐름 투영 (`scripts/project_student_flow.py`)

| # | 발견 | 분류 | 조치 | 검증 |
|---|---|---|---|---|
| G8-1 | 다시 돌리면 `Process` 를 DETACH DELETE — 출발본 스키마의 다리 관계 `Meeting -PREPARED_BY_PROCESS-> Process`(학생이 단 것)가 재투영마다 조용히 사라짐(멱등이 아님) | 결함 | Process 는 지우지 않고 MERGE, 지우기는 이 정의의 FlowNode 만(`WIPE`). 흐름 노드에 손으로 단 관계는 적재 전에 `!` 줄로 목록을 알림(`FOREIGN`) | 검증됨(시험: 지우기 문장에 Process 없음 · 이후 문장에 DELETE 없음). 실제 그래프 재투영은 미검증 |
| G8-2 | 모르는 task 종류 → 조용히 `user`, 모르는 eventDefinition(예 signal) → 조용히 `none`, 타이머 이벤트에 기간 없음 · 경계 이벤트에 attachedTo 없음 → 그냥 적재 | 결함(조용한 폴백) | 모두 문제로 보고하고 쓰지 않음. 단 **정의 칸이 아예 없는** 이벤트는 BPMN 의미상 none 이벤트라 none(기준 정의 alert_triage · ask_agent 가 이렇게 씀 — 처음엔 이것도 막았다가 실제 기준 정의 3개로 돌려 보고 되돌림) | 검증됨(시험 + 기준 정의 4개 `--check` PASS) |
| G8-3 | id 없는 요소 → KeyError 추적(좌표 없음), 정의가 JSON 배열 · 깨진 JSON → AttributeError 추적, 노드 0개 정의 → Process 하나만 PASS | 결함(좌표 없는 실패 · 빈 성공) | `activities[6]: id 가 없다` 꼴 좌표, 파일 경로가 든 ValueError → `FAIL` 한 줄 · 종료 1, 노드 0개는 문제 | 검증됨 |
| G8-4 | 흐름 가져오기의 '그 밖의 경우' 선(`properties.default`)을 버림 — v2 `SEQUENCE_FLOW.isDefault` 가 있는데 투영 그래프에서 미달 가지가 조건 없는 선으로 보임 | 결함(정보 손실) | `isDefault: true` 로 옮김 | 검증됨 |
| G8-5 | 시스템 수행자(sys:*)가 그래프에 없으면 `MATCH` 가 조용히 0건, endpoint 가 `role:` · `sys:` 둘 다 아니면 시스템으로 분류돼 사라짐 | 결함(조용한 누락) | 적재 전에 그래프의 기준 Role · System id 를 읽어(`BASES`) 실제 끝으로 검사, 없는 System 은 FAIL. 모르는 endpoint 접두어는 문제. 적재 뒤 흐름 노드 수 · 수행자 관계 수를 투영과 대조해 다르면 FAIL | 검증됨(단위). 실제 적재 대조는 미검증 |
| G8-6 | `--extra` 파일의 ns 가 `--ns` 와 달라도 check 가 몰래 `--ns` 로 덮어씀 | 결함(조용한 덮어쓰기) | 다르면 문제 | 검증됨 |
| G8-7 | 적재 뒤 안내가 `ontology_v2.py validate --extra …` — 그 검사기 기본 접속은 7688, 투영 기본은 7687(포털 지식 지도가 읽는 그래프, compose.yaml 285행) → 그대로 따라 치면 다른 그래프를 검사 | 결함(문서 · 출력 주장 불일치) | 안내에 `--uri <적재한 곳>` 포함 + 검사기 쪽 0개 노드 FAIL(G4-4) | 검증됨(정적) |
| G8-8 | 투영 · 검사 문장의 Cypher 문법 | — | 없음 | 검증됨: Neo4j 5.26.31 에 `EXPLAIN`(계획만, 실행 · 쓰기 없음) 11문장 모두 통과, 읽기 질의 `BASES` 는 실행해 `role:operator` · `sys:agent` 실존 확인 |
| G8-9 | 실제 흐름 가져오기 출력으로 투영되는가 | — | 없음 | 검증됨: `bpmn_import.check` 로 만든 정의 2개(사람 시작 + 일반 부품 `oil_check`, 기준 흐름 다시 그리기 `redraw`) `--check` PASS |
| G8-10 | 학생 Role 은 정의를 바꿔도 남음(다른 정의와 함께 쓸 수 있어 지우지 않음) | 의도된 차이 — 지우면 다른 흐름 · 학생 온톨로지가 쓰는 Role 이 사라짐 | 없음 | 해당 없음 |

## 5. 키트 ↔ 설계(capstone-lab.md, c2f2188) 대조

| 설계 | 키트 | 분류 |
|---|---|---|
| T1 스키마 틀: 같은 형식 · "다리 관계 예 3개" | `students/_template/schema.json` — 형식 같음, 다리 관계 3개(ORGANIZED_BY→Role, RAISED_IN→KnowledgeSource, PREPARED_BY_PROCESS→Process), `check-extra` PASS | 일치 |
| T1 "빈 칸 + v2 상위 클래스 목록" | 3절 예시가 채워진 틀, v2 목록은 넣지 않고 `check-extra` 명령을 가리킴 | 의도된 차이 — v2 목록을 복사하면 한 사실 두 곳(헌법 §8). 검사기가 v2 이름 재정의를 막으므로 목록 없이도 틀린 정의가 걸림 |
| 3.3 학생 클래스 Meeting · Customer · Attendee · AgendaItem · Document, Meeting 속성 `title!` | Meeting · AgendaItem · Material, 속성 `name` | 의도된 차이(예시 축약) — 검사기가 id · name 을 요구하므로 `title` 대신 `name`. Customer · Attendee 는 표(attendee)로만. 근거 부족 표시: 설계 3.3 표가 키트와 이름이 달라 강사 시연 때 혼동 가능 — 설계 문서 쪽 정리는 이 검토 범위 밖(main 레포 문서) |
| 3.4 표 `meeting_request` · `attendee` · `room` | `stu_s00.meeting` · `attendee`(좌석은 meeting.room_seats) | 의도된 차이(축약). 비해피 가지(좌석 미달 · 필수 무응답)는 있음 — 검증됨 |
| T3 DDL: 스키마 · 읽기 전용 계정 · 예시 행 | 있음, 계정 nosuperuser · nocreaterole · nocreatedb · nobypassrls · default_transaction_read_only, SELECT 만 | 일치 |
| T4 서버: readOnlyHint=true, 스키마 이름만 바꾸면 됨 | 있음(이번에 계약 환경 변수 필수로 강화) | 일치 |
| T2 적재 · 되돌리기 스크립트(MERGE 적재 ns · id 강제, **ns 단위 삭제**, 꼭 답할 질문 자동 검사) | 흐름 투영(G8)만 있음. 학생 지식 적재 · ns 단위 삭제 · 질문 자동 검사 스크립트는 없음 | 근거 부족(미구현) — 이번 병합 범위(G4 · G5 · G8) 밖. 6.2 "마친 뒤 정리"의 Neo4j ns 단위 삭제가 아직 손 질의 |
| T0 · T5 · T6 · T7 · T8 | 없음 | 근거 부족(미구현, 범위 밖) |
| 확정 스키마 변경 0 | 0줄 | 검증됨 |

## 6. 뮤테이션 확인 (일부러 깨뜨려 시험이 잡는가)

스크립트: 스크래치 `mutate.py`(파일 하나 고침 → 해당 시험 파일 실행 → 원문 복구). 19개 모두 **잡힘**, 놓침 0.

| 영역 | 뮤테이션 | 결과 |
|---|---|---|
| G4 | 폴더-ns 대조 끔 · v2 클래스 재정의 허용 · enum values 검사 끔 · id 접두어 규칙 끔 · 출처 검사를 옛 방식(전부 건너뜀) · 빈 이름 공간 PASS · 관계 템플릿 옛 조건 | 7/7 잡힘 |
| G5 | 읽기 전용 트랜잭션 빼기 · limit 0 을 최대로 · 없는 칸 거절 끔 · 권한 계정 허용 · 자리표시자 암호 허용 · 표 이름을 문장에 붙임 | 6/6 잡힘 |
| G8 | 모르는 task 종류를 user 로 · 기본 선 표시 버림 · Process 도 지우고 다시 · 시스템 수행자 확인 끔 · --extra ns 불일치 허용 · 빈 정의 통과 | 6/6 잡힘 |

주의: G4-7(관계 템플릿)의 시험은 문장 문자열 대조다 — 식의 의미는 위 2절처럼 라이브 Neo4j 읽기 세션에서 따로 실측했다.

## 7. 미검증으로 남긴 것

- 학생 모드 지식 지도가 실제 학생 노드를 그리는 모습(그래프에 ns 노드 0개, 쓰기 금지) — 식 의미와 기본 보기 회귀만 실측.
- G8 실제 적재 · 재적재 멱등(Neo4j 쓰기 금지) — 문장 문법(EXPLAIN)과 단위 시험만.
- T3 DDL 실제 실행 · T4 서버 HTTP 기동 · 포털 MCP 등록 연결 검사 · 에이전트 호출(DB 쓰기 · 서비스 기동 금지) — 카탈로그 SQL · 읽기 전용 · 시간 제한은 실제 PG 에서 실측.
- `validate --extra` CLI 를 실제 그래프에 붙여 돌리기(학생 노드 없음).

## 8. 바꾼 파일 (커밋 안 함)

- `scripts/ontology_v2.py` — G4-1~6
- `scripts/project_student_flow.py` — G8-1~7
- `students/_template/mcp_table_reader/server.py` — G5-1~5
- `students/_template/table.sql` — 머리말 한 줄(자리표시자 암호)
- `it/neo4j/templates/t0_graph_edges.cypher` — G4-7
- `tests/test_capstone_g4_namespace.py` · `tests/test_capstone_g5_table_reader.py` · `tests/test_capstone_g8_flow_projection.py` — 실패 경로 시험 추가 · 폴백을 고정하던 시험 교체
- 이 파일

최종 시험: 아래 9절.

## 9. 최종 시험 (수정 뒤, 한 번)

- `pytest tests/test_capstone_g4_namespace.py tests/test_capstone_g5_table_reader.py tests/test_capstone_g8_flow_projection.py` → **39 passed**(기준선 23 → 실패 경로 16개 추가)
- 영향 범위 회귀: `tests/test_ontology_schema.py tests/test_ontology_kpi_role.py tests/test_seed_editions.py tests/test_engine.py tests/test_bpmn_import.py` → 81 passed, 1 skipped
- `ruff check --select F`(바꾼 6개 파일) → 통과(쓰지 않는 import · 이름 없음)
- `python scripts/ontology_v2.py check-extra --extra students/_template/schema.json` → PASS
