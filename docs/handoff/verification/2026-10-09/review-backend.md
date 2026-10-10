# 백엔드 검토·보강 (merge-preview, 2026-10-09)

범위: `git diff 7fa5664..HEAD` 중 it/process/**, it/agent-worker/**, it/agent/**, it/supabase/migrations/**, compose.yaml, .env.example, 관련 tests/.
형식: 발견 → 분류(결함 / 의도된 차이 / 오해 / 근거 부족) → 조치(파일:줄) → 검증.
라이브 스택·컨테이너·DB는 건드리지 않음(단위 시험만). 커밋하지 않음.

## 1. MCP 비밀 값(mcp_secrets) · 자리표시자

| # | 발견 | 분류 | 조치(파일:줄) | 검증 |
|---|---|---|---|---|
| 1-1 | `PgSecretStore` 가 표(마이그레이션 050)가 없으면 `values()`→`{}`, `delete()`→False(→404 "없습니다"), `delete_all()`→0 을 돌려줬다. 강사는 "값을 넣으라"는 엉뚱한 안내만 받고, 되돌리기는 0건 성공으로 보였다(조용한 폴백 · 호환 shim). | 결함 | `it/process/procsvc/mcp_secrets.py:168-209` `_require` 가 모든 동작에서 503 + 마이그레이션 파일 좌표로 실패 | 검증됨 — `test_a_missing_secret_table_stops_every_operation_with_the_migration_named`, 뮤테이션 M1 잡힘 |
| 1-2 | 그 대신 표가 없을 때 **비밀이 없는 서버**까지 검사가 막히지 않게: 등록 · 고치기 · 검사 · 등록 전 검사가 설정에 자리표시자가 있을 때만 표를 읽는다. 전에는 모든 검사가 표를 읽었다. | 결함(1-1 의 연쇄) | `mcp_registry.py:449-456` `secrets_of(store, tenant, entry)`, `:464` `dry_check(store, tenant, body)` | 검증됨 — `test_servers_without_placeholders_do_not_need_the_secret_table`, M12 잡힘 |
| 1-3 | 레지스트리 HTTP 가 `SecretError` 를 잡지 않아 표 읽기 실패가 500 으로 나갔다. | 결함 | `mcp_registry.py:645-646` 503 사유로 | 검증됨 — 같은 시험, M14 잡힘 |
| 1-4 | 채운 토큰이 응답 · 검사 기록 · 감사로 샐 수 있는 길: 서버가 오류 본문 · 에코 도구로 토큰을 되돌리거나, stdio 서버가 stderr 에 환경 변수를 찍으면(검사기는 stderr 꼬리를 오류 문구에 넣는다 — `mcp_check.py:394`) 그대로 `mcp_server_checks` · `/tools` 응답 · `MCP_TOOL_TRIED` 감사 · 승인 뒤 영수증에 실렸다. | 결함 | `mcp_secrets.py:225-262` `runtime_spec` 이 (설정, 채운 값) 을 돌려주고 `redact()` 추가(4자 미만 값은 가리지 않음 — 응답 전체 훼손 방지). 적용: `mcp_registry.py:168`(검사 기록), `mcp_api.py:168-185`(도구 목록 · 써 보기 → 응답 · 감사), `instance_mode.py:478-486`(승인 뒤 시스템 task) | 검증됨 — `test_a_token_echoed_by_the_server_never_reaches_the_record_the_answer_or_the_audit`, `test_the_system_task_after_approval_redacts_an_echoed_token`, `test_redact_skips_values_too_short_to_be_secrets`; M2 · M3 · M3b 잡힘 |
| 1-5 | 승인 뒤 시스템 task 에서 실행 서비스가 없으면 `repo=None` 으로 환경 변수만 읽는 조용한 대체. | 결함(경계) | `instance_mode.py:478-480` 사유와 함께 failed | 검증됨 — 같은 시험 끝 줄 |
| 1-6 | 되돌리기가 서버를 먼저 지우고 비밀 값을 나중에 지웠다 — 비밀 지우기가 실패하면 반만 되돌린 상태. | 결함 | `mcp_registry.py:595-605` 비밀 값 먼저 | 검증됨 — `test_reset_stops_before_removing_servers_when_secrets_cannot_be_deleted`, M11 잡힘 |
| 1-7 | 워커 `context.with_secrets` 가 표 조회 예외를 삼키고 환경 변수만으로 진행 → 게이트가 "비밀 값 X 이(가) 없는 서버"라고만 말해 원인(표를 못 읽음)이 숨었다. | 결함(조용한 폴백) | `it/agent-worker/worker/context.py:97-107`(실패 사유를 설정과 함께 넘김, claim 은 실패시키지 않음 — 다른 서버는 그대로 실행), `bridge.py:34-37,118-123`(`SECRETS_ERROR_KEY`, 탈락 사유에 "비밀 값 표를 읽지 못함: …"), `without_secrets` 가 두 키 모두 제거 | 검증됨 — `test_a_failed_secret_lookup_in_the_worker_is_named_on_the_drop_reason`, M4 잡힘. 러너는 이미 `gate.dropped` 를 처리 건 notice 로 남긴다(`runner.py:146-149`) |
| 1-8 | `with_secrets` 조건식이 `mcpServers` 가 dict 가 아니면 `.values()` 에서 AttributeError(필터보다 먼저 평가). | 결함(경계) | `context.py:97-98` | 검증됨(기존 시험 통과, 코드 읽기) |
| 1-9 | 로그 · 감사에 값: `PUT /api/mcp/secrets` 감사는 키만, 워커 로그는 사유 문자열만. `.mcp.json` 은 실행 뒤 `cleanup` 이 headers · env 를 지움. | 문제 없음 | — | 기존 시험 + 코드 읽기 |

## 2. 강사 "읽기로 확인"(read-confirm) API

| # | 발견 | 분류 | 조치 | 검증 |
|---|---|---|---|---|
| 2-1 | `on` 을 `is not False` 로 읽어 `"false"`(글자) · `0` 이 **확인(on)** 으로 처리됐다. | 결함 | `mcp_registry.py:714-717` bool 이 아니면 422 | 검증됨 — `test_read_confirm_rejects_a_non_boolean_on_and_revokes_even_on_a_stale_check`, M10b 잡힘(처음 쓴 시험은 reason 이 없어 다른 422 로 우연히 통과 → 시험을 고쳐 다시 잡힘 확인) |
| 2-2 | 취소(off)도 "지금 설정으로 통과한 검사"를 요구해, 설정이 바뀐 뒤에는 강사가 믿음을 거둘 수 없었다. | 결함 | `mcp_registry.py:551-593` off 는 검사 없이 받고, 통과 검사가 없으면 도장(gate)을 내린다 — 다음 검사가 확인 목록으로 다시 계산 | 검증됨 — 같은 시험, M10 잡힘 |

## 3. 도구 결과 원문(event_payloads) 저장 · API

| # | 발견 | 분류 | 조치 | 검증 |
|---|---|---|---|---|
| 3-1 | 행 id = 원문 sha256 하나(전역) + `on conflict do nothing`. 두 처리 건(또는 두 테넌트)이 같은 결과(예: 같은 큰 KG 조회)를 받으면 둘째 처리 건의 참조가 **첫 처리 건의 행**(todo · job · tool_use id)을 보이고, 첫 처리 건이 지워지거나 다른 테넌트면 404 — `stored=true` 인데 못 읽는다. | 결함(테넌트 · 처리 건 격리) | `it/agent-worker/worker/payloads.py:1-24,131-147` id = sha256(처리 건 id + 원문 sha256), 원문 해시는 `meta.content_sha256` · 참조의 `sha256`. 마이그레이션 주석만 갱신(`20261009000048_event_payloads.sql:5-6,9`, 실행문 변화 없음 — 적용된 DB 와 어긋나지 않음) | 검증됨 — `test_the_same_result_in_two_cases_is_kept_per_case_and_read_only_through_its_own_case`, M5 잡힘 |
| 3-2 | GET `/api/event-payloads/{id}` 가 `proc_inst_id` 가 없는 행은 테넌트 검사 없이 누구에게나 줬다(fail open). 또 검사에 `instance_view`(작업 · 이벤트 1,500건 · 승인 등 전부)를 덩어리마다 불렀다. | 결함 + 효율 | `instance_mode.py:1205-1222` `get_instance` 로 테넌트 · 지움 확인, 처리 건 없는 행은 404 | 검증됨 — 같은 시험, M6 잡힘 |
| 3-3 | 워커가 처리 건 없는 작업의 원문도 저장하려 함 → 읽을 수 없는 행. | 결함(3-2 연쇄) | `runner.py:343-347` 저장하지 않고 `stored=false` + 사유 | 검증됨 — `test_a_work_item_without_a_case_does_not_store_and_says_so`, M13 잡힘 |
| 3-4 | 저장 실패는 이미 행에 `stored=false` · `error` 로 남고 실행은 계속(기존 시험 있음). 크기 상한 `MAX_CHARS` · 잘림 `meta.cut`, 덩어리 상한 200,000자. | 문제 없음 | — | 기존 시험 |
| 3-5 | `saved_path` 는 어느 위치든 `tool-results` 이름의 폴더 아래 파일이면 읽는다 — 도구 출력이 CLI 문구를 흉내 내면 그 폴더의 다른 파일을 읽어 표(anon 읽기 허용)에 올릴 수 있다. 실행별 CLI 설정 폴더로 좁히려면 비격리 모드의 경로를 알아야 해 이번에 고치지 않음. | 근거 부족(잔여 위험) | — | 미검증 |
| 3-6 | `procdb.py` 프로토콜 주석의 마이그레이션 번호 000047 → 000048. | 결함(주석) | `procdb.py:135` | 코드 읽기 |

## 4. 재관측 값 흐름(reobs series)

| # | 발견 | 분류 | 조치 | 검증 |
|---|---|---|---|---|
| 4-1 | `main.tag_series` 가 TimescaleDB 읽기 실패를 `[]` 로 바꿔 `samples 0` 시계열을 만들었다 — "창 안에 값이 없었다"와 "못 읽었다"가 같은 모양(조용한 폴백). 창 시작을 못 찾으면 `None` 으로 조용히 빠짐. | 결함 | `reobs_series.py:12-14,63-66` `unavailable()`(같은 모양 + `error`), `main.py:119-150` `tag_series` 는 실패를 올리고 `window_series` 가 사유와 함께 기록, `machine.py:326-331` 감사 요약에 `error` | 검증됨 — `test_the_command_path_records_why_a_window_could_not_be_read`, M7 · M7c 잡힘 |
| 4-2 | 작업지시 재관측(`recovery_reading`)도 예외 시 `series=None` 으로 흔적 없이 빠졌다(기존 시험이 `reobs_series is None` 을 기대 — 해피 쪽으로 굳힌 시험). | 결함 | `instance_mode.py:457-469` 사유가 든 시계열을 판정 기록 · 사건에 남김(판정은 기다리지 않음) | 검증됨 — 시험을 `test_a_failing_series_read_does_not_stop_the_verdict_and_the_gap_is_recorded` 로 바꿈, M7b 잡힘 |
| 4-3 | `MAX_ROWS`(7,200행)로 자를 때 잘림 표시가 없다. 20배속 창은 45초(행 45개), 1배속도 900초+연장이라 상한에 닿지 않음. | 의도된 상한 | — | 코드 읽기 |
| 4-4 | 포털이 `reobsSeries.error` 를 보여 주는지는 포털 검토 범위. | 해당 없음(타 범위) | 포털 검토자에게 전달 필요 | 미검증 |

## 5. 이벤트 쪽 넘기기(events paging)

| # | 발견 | 분류 | 조치 | 검증 |
|---|---|---|---|---|
| 5-1 | 모르는 커서(`before=없는 id`)가 빈 쪽 + `has_more=0` 으로 답해 "더 오래된 행 없음"과 구별되지 않았다(기존 시험이 `== []` 를 기대). Pg 는 다른 처리 건의 이벤트 id 도 커서로 받아 그 시각 기준으로 잘랐다. | 결함 | `procdb.py:129-131`(계약), `:511-516`(Memory), `:946-958`(Pg: 같은 필터 안에서 커서를 먼저 찾고 없으면 LookupError, 찾은 (timestamp, id) 로 비교), `instance_mode.py:1191-1196` 404 | Memory 검증됨 — `test_events_pages_backwards_without_gaps_or_repeats`(모르는 커서 · 다른 처리 건 커서 404), M8 잡힘. **Pg 경로는 DB 없이 미검증** |

## 6. 역할 만들기 · 지우기(G10)

| # | 발견 | 분류 | 조치 | 검증 |
|---|---|---|---|---|
| 6-1 | 지우기가 `IN_PROGRESS` 작업만 막았다 — 기다림(TODO) · 제출 뒤 대기(SUBMITTED) · 보류(PENDING) 작업의 담당 역할도 지워져 작업이 갈 곳을 잃는다. 또 담당이 쉼표 목록(`role:a,role:b`)이면 `user_id == role_id` 비교로 놓쳤다. 시험에 이 가지가 아예 없었다. | 결함 | `agent_authoring.py:449-456` `OPEN_STATUSES` · `role_open_rows`(csv), `:497-499` | 검증됨 — `test_a_role_with_unfinished_work_is_kept_whatever_the_status`, M9 · M9b 잡힘 |
| 6-2 | 이름 중복 검사는 앱에서만(동시 요청 경합 가능), 지우기 감사는 로그만 — 다른 저작 API 와 같은 수준. | 의도된 차이(교육 환경) | — | 코드 읽기 |

## 7. 워커 스킬 이벤트(A161-G1)

| # | 발견 | 분류 | 조치 | 검증 |
|---|---|---|---|---|
| 7-1 | `_provided_skills` 가 작업 폴더에 SKILL.md 가 없으면 저장된 본문으로 해시를 만들어 "이 실행이 가진 스킬"로 기록했다 — 에이전트가 읽을 수 없었던 스킬을 가졌다고 말하는 조용한 대체. | 결함 | `runner.py:445-466` 목록에는 남기되 `written=false` · `error`, 경고 로그. `events.py:181-183` 요약 문구에 "작업 폴더에 파일이 없어 읽을 수 없었음" | 검증됨 — `test_a_skill_file_missing_from_the_workspace_is_not_recorded_as_had`, M15 · M16 잡힘 |
| 7-2 | `SkillReads` 는 같은 파일 반복 읽기 1회, 제공 밖 경로도 `known=false` 로 남김(기존 시험). | 문제 없음 | — | 기존 시험 |

## 8. compose · 네트워크

| # | 발견 | 분류 | 조치 | 검증 |
|---|---|---|---|---|
| 8-1 | plant-sim 을 부르려고 **process 를 ot-net 에 붙였다**. compose 의 망 구조는 OT(ot-net) · IT(it-net)를 DMZ 두 서비스(connect-ingest · cmd-gateway = "유일한 하향 통로")만 넘게 짜여 있는데, 이 변경으로 IT 서비스(process)가 emqx(OT MQTT)에 직접 닿게 됐다 — 수업이 가르치는 IT/OT/DMZ 경계를 깬다. | 결함(설계 경계) | `compose.yaml:16-19` 시뮬레이터 API 전용 `sim-net` 추가, `:56` plant-sim `[ot-net, sim-net]`, `:363-364` process `[it-net, sim-net]`, `:389` 주석. `.env.example:37` 주석. `PLANT_SIM_URL=http://plant-sim:8000` 은 그대로 동작(같은 sim-net). 재발 방지: `tests/test_compose_contract.py` 에 "ot-net 과 it-net 을 함께 가진 서비스는 DMZ 둘뿐" 불변식 + 변형 시험 | 정적 검증됨 — `docker compose --profile '*' config` 파싱 통과(process: it-net · sim-net), 계약 시험 4개 통과, M17(process 를 다시 ot-net 에) 잡힘. **라이브 미검증**(지시대로 up 하지 않음). 반영하려면 `docker compose up -d plant-sim process` 로 두 컨테이너를 다시 만들어야 한다(plant-sim 상태 초기화 — 검사 전에). `docs/RUNBOOK.md:95` 의 "process는 ot-net에도 붙어" 문구는 문서 검토 범위라 고치지 않음 → 문서 담당이 sim-net 으로 고쳐야 함 |

## 9. 그 밖에 읽은 것(문제 없음)
- `it/agent/agentsvc/main.py` ns 검증(정규식 422) · `mcp_kg.py` ns 전달 · `/api/ontology/namespaces` — 템플릿 쪽은 neo4j 검토 범위.
- `instances.py` `events_page`(EVENTS_WINDOW+1 로 더 있음 판정) — 기존 시험 있음.
- `agent-worker/Dockerfile` 에 mcp_secrets.py 복사 — 워커 import 경로와 일치.
- `mcp_check.confirmable` · 써 보기의 확인 도구 재판정(그 자리에서 다시 받은 목록 기준) — 기존 시험 있음.

## 10. 검증 요약
- 전체 단위 시험: `pytest -q -p no:cacheprovider` → **1916 passed, 4 skipped, 0 failed**(188 s). 기준선은 1886 passed + macOS 불안정 1건. 늘어난 수에는 같은 작업 트리의 다른 검토자 시험도 들어 있다. 이번 실행에서는 `test_mcp_check.py::test_html_page_is_not_an_mcp_endpoint` 도 통과했다.
- 뮤테이션 18종(M1~M16, M3b·M7b·M7c·M9b·M10b 포함) + compose M17: **모두 잡힘**, 놓친 것 0. 스크립트는 `scratchpad/review-backend/mutate_backend.py`, 기록은 `mutate.log`. 파일은 finally 에서 원래대로 되돌렸다.
- 미검증: Pg `list_events` 커서 경로와 `PgSecretStore`(실 DB 없이 가짜 연결로만 확인), compose `sim-net` 라이브 반영(up 금지), 포털의 `reobsSeries.error` · `skills[].written` 표시(포털 범위).
- 다른 검토자에게 넘길 것: `docs/RUNBOOK.md:95` ot-net → sim-net 문구, 포털 처리 기록 화면의 `reobsSeries.error` · `full_output`(id 가 처리 건 범위로 바뀌었고 `sha256` 은 여전히 원문 해시) · `skills_provided` 의 `written=false` 표시.
