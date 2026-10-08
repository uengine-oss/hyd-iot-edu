# U3 — 도구(MCP) 지도 · 도구 써 보기 · 호출 기록 (확정 TODO A2 MCP 부분, 2026-10-08 밤)

범위: 메인 `TODO.md` 확정 TODO §0 · §1 **A2**(MCP 부분) · §2 L14·L15 행. **읽기 전용** — 포털에서 서버를 추가 · 수정 · 삭제하는 경로는 없다
(TODO §4 D "포털에서 에이전트·MCP 만들기·등록·연결 검사"는 ProcessGPT 쪽 기능). 서버 추가는 랩업(Claude Code)에서 하고, 같은 설정 원천
`public.tenants.mcp`를 읽으므로 추가한 서버가 화면에 그대로 나타난다.

이전 미커밋 작업(등록 · 수정 · 삭제 · 검사 결과 저장 · 마이그레이션 `…27_mcp_server_checks`)은 이 범위에 맞춰 정리했다:
쓰기 라우트 5개(`POST/PUT/DELETE /api/mcp/servers…`, `POST …/check`, `POST /api/mcp/check`)와 `mcp_store.py` · 마이그레이션 `…27`을 지웠다
(연결 상태는 저장하지 않고 화면을 열 때마다 시간 제한 안에서 확인). 마이그레이션 번호 `…27`은 쓰지 않는다.

## 원본 대조 (원본 파일:줄 → HYD)
| 원본 | 무엇 | HYD | 차이 · 판단 |
|---|---|---|---|
| process-gpt-vue3@867e8cf `src/components/pages/account-settings/MCPServer.vue:23-84` | 서버 목록 + 검사 요약(도구 n개 / 실패) + 펼치면 `McpValidationResult` | `mcp.js` 서버 카드(상태 칩 · 종류 · 도구 수 · 주소 또는 실패 사유 · 쓰는 에이전트) → 아래 상세 | 같은 구조. 원본은 편집(연필)·켜기 스위치(`:63-77`)가 있고 기본 서버는 보기만(`:64` `mdi-eye`, `:455` readOnly) — HYD는 **모든 서버가 보기만**(사용자 10-08 "읽기 전용") |
| 같은 파일 `:520-536` `autoValidateServer`, `src/services/McpValidatorService.js:23-38`(`timeout=10`) | 저장 뒤 자동 검사, 서버마다 시간 제한 | 화면을 열면 서버마다 `GET /api/mcp/servers/{name}/tools?timeout=4` 를 동시에 부름 | 원본 10초 → HYD 4초(포털 GET 8초 제한 안). 결과는 저장하지 않음(원본도 저장 안 함) |
| `McpValidationResult.vue:8-24` | 도구 이름 · 설명 목록, 선택 체크 | 도구 줄: 이름(아는 도구는 한국어 이름) · 설명 · 읽기 전용 칩 · 입력 형식 접기 · 행동 1개 "써 보기" | 체크(에이전트에 도구 고르기)는 없음 — 설정 변경이므로 랩업으로 |
| process-gpt-mcp-validator@cf220bf `src/mcp_validator/validator.py:94-189` | 세션 → `initialize` → `load_mcp_tools` → `asyncio.wait_for(timeout)` → 실패 사유(명령 없음 · Connection closed · TaskGroup) | `procsvc/mcp_check.py` `_with_session` · `_initialize` · `_list_tools` · `check` | 같은 절차를 표준 라이브러리로(process 이미지 requirements 불변). 실패 분류를 더 나눔(config · exec · refused · unreachable · timeout · auth · not_mcp · protocol · server · closed · too_large) |
| `models.py:60-64` `MCPToolInfo{name, description, parameters}` | 도구의 입력 형식 | `input_schema`(tools/list `inputSchema` 그대로) + `annotations` + `callable` · `refuse_reason` | 입력 형식에서 폼을 만들어 **실제 호출**까지(원본 validator·vue3 에는 도구 호출 화면이 없다 — HYD 추가, A2 "도구 하나를 직접 호출해 결과 보기") |
| vue3 `views/markdown/AgentMonitor.vue:862-877`(screens-vue3.md S2) | 단계별 `tool_usage_started/finished` 구독 | `GET /api/mcp/calls` — events 의 같은 두 종류를 **도구 기준**으로 모음 → 처리 건 · task · 입력 · 결과 요약 · 시각 · `#/instances/<id>/task/<taskId>` | 원본은 단계 기준만, HYD는 "이 도구가 어느 task에서 불렸나"(A2) |

## 만든 것 · 바꾼 파일
| 파일 | 내용 |
|---|---|
| `it/process/procsvc/mcp_check.py` (새) | 설정 정규화(시드 형태 3종 + `type: sse/http` 별칭), 비밀값 가림(`masked` 설정 · `mask_value`/`mask_text` 입력·결과), MCP 클라이언트(stdio · streamable_http JSON/SSE · 구형 sse), `check`(도구 목록 + 읽기 전용 판정), `call`(같은 세션에서 tools/list 를 다시 받아 판정 → tools/call), `shape_result`(2만 자 상한 · `truncated` · 원래 크기), 서버 응답 하나 2 MB 상한(`too_large`) |
| `it/process/procsvc/mcp_calls.py` (새) | 도구 호출 기록: Claude Code `mcp__<서버>__<도구>` · Codex `<서버>/<도구>`(cliagents `providers/codex.py:459`, `-`↔`_` 같은 서버) 해석, 시작·끝 이벤트를 `tool_use_id`로 한 줄, 입력·결과 비밀값 가림, 최근 도구 이벤트 3000개까지 훑음(PgRepo 한 번의 SQL — events ⟕ todolist ⟕ bpm_proc_inst) |
| `it/process/procsvc/mcp_api.py` (새) | 아래 API 4개, legacy 모드 503, 시도마다 감사 `MCP_TOOL_TRIED{server, tool, status, error, arguments(가림)}` |
| `it/process/procsvc/main.py` (+4줄) | `mcp_api.register(app, runtime_factory=instance_mode.current, audit=_audit)` |
| `it/dmn-mcp/dmn_mcp/server.py`, `it/enterprise-mcp/enterprise_mcp/server.py` (데코레이터만) | 도구마다 MCP ToolAnnotations: 읽기 13+10개 `READ={"readOnlyHint": True, "destructiveHint": False}`, `submit_decision` 만 `WRITE={"readOnlyHint": False, …}` (서버 docstring "submit_decision is the only write"와 같음). **두 이미지 재빌드 필요** |
| `it/portal/www/mcp.js` · `mcp.css` (새), `index.html`(메뉴 1줄 · `<section id="view-mcp"><div id="mcpView">` · link/script), `ui.js`(`nav.mcp` 용어 · `tools` 아이콘) | `window.hydMcp.mount(el)` — 셸(U7)이 `#mcpView`에 붙인다. 지금 셸에서는 메뉴 "도구(MCP)"를 처음 누를 때 스스로 mount. 순수 함수 `window.hydMcp.form.{fieldsOf, coerce, argsFrom}` |
| `tests/test_mcp_check.py`, `tests/fixtures/mcp_fake_server.py` | 아래 시험 |
| `tests/test_a144_mcp_worker.py:69` (1줄) | enterprise 도구 10개 세기를 표시 붙은 데코레이터로 |
| 지움 | `it/process/procsvc/mcp_store.py`, `it/supabase/migrations/20261008000027_mcp_server_checks.sql` (커밋된 적 없음) |

## API (모두 읽기 · 설정 저장 없음)
- `GET /api/mcp/servers` → `{tenant, source:"tenants.mcp", servers:[{name, transport, url|command, args, env(가림), headers(가림), config_error, agents:[{id,name,goal}], tasks:[{definition, definition_name, version, activity_id, activity_name, agent, declared}]}]}` — 네트워크 연결 없음.
  - agents: `users.is_agent` 이고 `agent_type='agent'`(시스템 SCADA·CMMS 제외)인 사람 중 `tools` 칸에 이 서버 이름이 있는 것.
  - tasks: 정의마다 가장 새 판본의 단계 중 역할 endpoint 가 그 에이전트인 것. 단계가 `tools`를 적었으면 그 서버만, 안 적었으면 테넌트 서버 전부(`declared=false`) — 워커 `bridge.select_servers`(A095)와 같은 규칙. 지금 정의는 모두 미지정이라 네 단계(원인 진단 · 조치 후보 조회 · 규정 검토 · 우선순위·카드 작성)가 모든 서버에 붙는다.
  - 손편집으로 깨진 칸은 `config_error`("설정 오류 — …")로 줄이 남는다.
- `GET /api/mcp/servers/{name}/tools?timeout=0.5~6(기본 4)` → `{status: ok|failed, tools:[{name, title, description, input_schema, annotations, callable, refuse_reason}], error, error_kind, server_info, elapsed_ms, checked_at, timeout_s}`. 없는 서버 404, 깨진 설정 422.
- `POST /api/mcp/servers/{name}/tools/{tool}/call {arguments:{…}, timeout?: 0.5~25(기본 15)}` → 200 `{result:{is_error, text, json, size_chars, truncated, limit_chars}, arguments(가림), elapsed_ms}` · **403** 쓰기·표시 없음(사유) · 404 없는 도구 · 400 입력이 객체가 아님 · 502 연결 실패(사유).
- `GET /api/mcp/calls?server=&tool=&limit=1~200(기본 50)` → `{calls:[{server, tool, raw_tool, proc_inst_id, instance_name, todo_id, activity_id, task_name, at, state: done|error|running, duration_ms, input_summary, output_summary, input, output, link}], scanned, scan_limit}`.

## 읽기 전용 판정 (코드에 정답을 넣지 않은 범용 규칙)
`mcp_check.read_only_verdict`: **서버가 도구에 `readOnlyHint=true`를 붙였고, 이름이 쓰기·실행(write · submit · create · delete · set · run · command …, camelCase 포함)을 뜻하지 않을 때만** 써 보기를 허용한다.
- `destructiveHint=true` / `readOnlyHint=false` → "쓰기 도구로 표시했습니다 — 처리 건 안에서 사람 승인 뒤에만 쓰입니다".
- 표시 없음 → "서버가 이 도구를 읽기 전용(readOnlyHint)으로 표시하지 않았습니다 — 서버 코드에서 표시를 붙이면 써 볼 수 있습니다"(기본 닫힘).
- 표시는 읽기인데 이름이 쓰기 → 거부("표시했더라도 포털에서는 부르지 않습니다").
- 판정은 호출 직전 **같은 세션에서 서버 목록을 다시 받아** 한다(클라이언트 판정을 믿지 않음). 거부된 도구는 서버의 `tools/call`에 닿지 않는다(시험).
- 결과: 서버 응답 하나 2 MB 넘으면 끊음(`too_large`), 화면 결과 2만 자 상한(`truncated`, 원래 글자 수 표시). 도구가 오류를 돌려주면 `is_error`로 그대로 보인다(숨기지 않음).
- 랩업 L15에서 학생이 만든 서버: FastMCP 면 `@mcp.tool(annotations={"readOnlyHint": True})` 를 붙여야 포털에서 써 볼 수 있다. 붙이지 않아도 도구 지도 · 호출 기록에는 나타난다.

## 비밀값 가림
- 설정: env · headers 이름에 pass · pwd · secret · token · key · auth · dsn · credential · cookie · signature → `********`, 주소의 비밀번호 → `http://u:********@h`.
- 도구 입력 · 결과 · 호출 기록 · 감사: 칸 이름이 password · secret · token · api_key · access_key · private_key · authorization · dsn · credential · cookie · signature 이면 값 통째로, 문자열 안의 `scheme://u:비번@` · `password=…` · `Bearer …` 도 가림. 업무 값 `key`(공급사 a·b·c) · `primary_key` 는 가리지 않는다(시험).

## 랩업에서 추가한 서버가 나타나는 곳 (L14 · L15)
설정 원천 하나: `public.tenants.mcp` 의 `mcpServers.<이름>` (워커 `it/agent-worker/worker/bridge.py`가 실행마다 읽는 제품 형태).
```sql
-- 예: L15 진동 MCP 서버(HTTP)를 추가 — Supabase Studio SQL 또는 psql (로컬 54322)
update public.tenants
   set mcp = jsonb_set(mcp, '{mcpServers,my-vibration}', '{"type":"url","url":"http://host.docker.internal:8301/mcp","transport":"streamable_http"}')
 where id = 'hyd';
-- 에이전트가 쓰는 서버로 적기(도구 지도의 '쓰는 에이전트')
update public.users set tools = tools || ',my-vibration' where id = 'sys:agent';
```
- 명령형(stdio) 서버 `{"command": "...", "args": [...], "env": {...}}`도 같은 칸. 단, 도구 지도의 연결 확인은 **process 컨테이너 안**에서 하므로 그 명령이 컨테이너에 없으면 "명령 없음" 사유가 정직하게 나온다(시드 `neo4j`의 `uvx` — python:3.12-slim 에 없음. 워커 PC 에서는 돈다). 호출 기록은 events 에서 오므로 연결과 무관하게 보인다.
- HTTP 서버 주소는 process 컨테이너에서 닿아야 한다(같은 compose 망의 서비스 이름, 또는 호스트의 서버면 `host.docker.internal`).
- `supabase db reset`은 `seed.sql`로 되돌리므로 수업 동안 유지하려면 랩업 문서에서 시드가 아니라 위 SQL 을 다시 실행하게 한다(시드 · BPMN 은 고정).

## 화면 (포털 "관리 › 도구(MCP)")
1. 머리말 한 줄 + 서버 카드 격자: 상태 칩(연결 확인 중 · 연결됨 · 명령 없음/연결 거부/시간 초과 …) · 종류 칩 · 도구 n개 · 주소 또는 실패 사유(빨강) · "쓰는 에이전트 · 맡은 task n개". 카드 행동 1개 "도구 보기".
2. 상세(카드 아래): 상태 줄(서버 이름 · 판 · ms · 확인 시각 또는 사유), **쓰는 에이전트 · 맡은 task 는 접지 않음**, 설정(가린 값)은 접기, 탭 "도구 n" / "호출 기록".
3. 도구 탭: 줄마다 이름 · 칩(읽기 전용 / 써 보기 불가) · 설명 · 불가 사유 · 입력 형식 접기 · 행동 1개 "써 보기"(불가면 비활성 + 사유). 써 보기 → 입력 형식에서 만든 폼(글 · 숫자 · 정수 · 예/아니요 · 목록 · JSON, 필수 *, 설명은 라벨, 입력 이름은 도움말) → "호출" → 결과(가린 JSON, 크기 · 잘림 · 보낸 입력).
4. 호출 기록 탭: 도구 고르기(전체/도구) → 시각 · 상태 · 도구 · 걸린 시간 / 처리 건 · task · "처리 건에서 보기"(`#/instances/<id>/task/<taskId>` — U7 셸 라우팅) / 입력 · 결과 요약, 전체는 접기.

## 시험 (근거 `.evidence/u3-mcp/`)
- `pytest -q tests/test_mcp_check.py` → **31 passed** (`pytest-mcp.txt`):
  - 가짜 서버 도구 목록: stdio(두 페이지 커서) · streamable_http JSON · SSE(세션 id 되돌림) · 구형 sse, 입력 형식 · 표시 · 판정까지.
  - 실패 사유: 연결 거부(host:port) · 모르는 호스트 · 401 · HTML · 0.5초 시간 초과 · 없는 명령(process 컨테이너 · 워커) · 조기 종료(종료 코드 · stderr) · websocket/주소 형식.
  - 호출: 읽기 전용 `add` 실제 결과 `{"sum": 5.5}`, 도구 오류 `is_error`, **쓰기(`readOnlyHint=false`) · 표시 없음 · 이름이 쓰기(`delete_rows`) 3종 거부 + 서버 `tools/call`에 닿지 않음(CALLS == [])**, 없는 도구 · 객체 아닌 입력, 5만 자 결과 1000자에서 잘림, 결과 비밀값 가림(dsn · password · URL 비번 · Bearer)과 업무 값 `key` 유지.
  - 저장소 서버 표시: dmn-mcp · enterprise-mcp 24개 도구 모두 표시, 쓰기는 `submit_decision` 하나(표시를 빼면 실패).
  - API: 목록(가림 · 에이전트 · 실제 정의 v22 의 네 task · 깨진 칸), 도구 목록(정상 · 명령 없음 · 404 · 422 · timeout 400), 써 보기(200 · 403 · 404 · 400 · 502, 감사 4건), **쓰기 라우트 5개 404/405 · tenants.mcp 불변**, 호출 기록(시작·끝 짝 · 1250 ms · 새것 먼저 · Codex 이름 · MCP 아닌 도구 제외 · 비밀값 가림 · 링크), legacy 503.
  - 포털 폼(node vm): 입력 형식 6종 → 칸, 좋은 입력 → 값, 나쁜 입력 4종 → 한국어 사유.
  - **일부러 깨뜨리기**: 거부 판정(`if not meta["callable"]`)을 끄고 문자열 가림을 빼면 6개 시험이 실패함을 확인한 뒤 되돌림.
- 실제 FastMCP 2.13.0.2(dmn-mcp · enterprise-mcp 와 같은 판, 별도 venv): stdio · streamable HTTP 서버에서 `annotations` 가 tools/list 로 나오고 읽기 호출 · 쓰기/표시 없음 거부가 같은 결과(`fastmcp-real.txt`, 서버 `fastmcp-srv.py`). 저장소 서버를 그대로 import 해 목록을 뽑으면 dmn 14개 중 13개 readOnlyHint=true(남은 것 submit_decision) · enterprise 10/10(`repo-servers-annotations.txt`).
- 포털 스모크(Playwright, 실제 `mcp_api` + MemoryRepo + 가짜 MCP HTTP, `portal-smoke.py`): 지도(연결됨 · 명령 없음 사유) → 쓰기 · 표시 없음 버튼 비활성 → lookup 호출 결과(가림) → 필수 빈칸 사유 → 호출 기록(task · 처리 건 · 링크 · 가림) — `portal/1-map.png`·`2-try.png`·`3-calls.png`·`4-failed.png`, 페이지 오류 0.
- 전체 `pytest -q` → **1315 passed** (`pytest-full.txt`, 2분 23초). 첫 실행에서 `tests/test_a144_mcp_worker.py:69`(enterprise 서버의 `@mcp.tool\n` 10개 세기)가 표시 추가로 0개가 되어 실패 → 같은 계약을 `@mcp.tool(annotations=READ)\n` 10개로 고침.
- `node --check` mcp.js · ui.js 통과.

## 메인이 라이브로 확인할 것 (합친 뒤 1회)
1. dmn-mcp · enterprise-mcp 이미지 재빌드(데코레이터 표시) + process 재기동(`PROCESS_MODE=instance`). 검사기 도는 중 금지(CLAUDE.md §3).
2. `docker compose --profile cliagents up -d enterprise-mcp dmn-mcp` 뒤 포털 "도구(MCP)": enterprise 연결됨 · 도구 10(모두 읽기 전용) / hyd-dmn 연결됨 · 도구 14(submit_decision 만 써 보기 불가) / neo4j "명령 없음"(process 이미지에 uvx 없음 — 사실). 
3. hyd-dmn `dmn_rules` 써 보기(입력 비움) → 결과 JSON, `submit_decision` 버튼 비활성 · 사유.
4. 쿨러 처리 건 1건 뒤 enterprise "호출 기록" → 원인 진단 등 task 와 "처리 건에서 보기" 링크(U7 라우팅).
5. dmn-mcp 를 끄고 "연결 다시 확인" → "주소를 찾을 수 없습니다 — 'dmn-mcp'" 또는 연결 거부.
6. 위 SQL 로 서버 하나 추가 → "다시 읽기"에 카드가 나타남(랩업 L15 경로).

## 남은 판단 (메인)
- neo4j(stdio)는 process 컨테이너에 `uv` 가 없어 지도에서 늘 "명령 없음"이다. ① process 이미지에 uv 추가(빌드 변경) ② 그대로(정직한 사유, 호출 기록은 보임) — 코드는 ①이 되면 그대로 연결된다. 지금은 ②.
- legacy 경로(`AGENT_BRIDGE=legacy`, agentsvc)는 도구 호출을 events 에 남기지 않으므로 호출 기록에 나오지 않는다(instance 모드 · 워커 경로만).
