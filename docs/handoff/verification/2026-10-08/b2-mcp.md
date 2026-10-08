# B2 — MCP 서버 직접 등록 + 연결 검사 게이트 (확정 TODO B2, DECISIONS 110 ①, 2026-10-08 밤)

범위: `TODO.md` 확정 TODO B 의 **B2** — MCP 서버 등록 · 고치기 · 지우기(`tenants.mcp`), 연결 검사를 통과한 서버만 도구로 선택,
에이전트에는 읽기 표시 도구만. 완료 기준: 잘못된 서버는 사유와 함께 거절, 정상 서버는 도구 목록, 쓰기 도구는 선택 불가.
U3(`u3-mcp.md`)의 "포털은 읽기 전용" 결정은 DECISIONS 110 ①로 대체됐다. U3 의 읽기 경로(도구 지도 · 써 보기 · 호출 기록)는 그대로 두고 쓰기 경로를 새 모듈에 더했다.

## 한 줄 비유와 스스로 판정할 질문
- 비유: **출입증 발급 창구**. 서버를 등록하면 그 자리에서 실제로 전화를 걸어(연결 검사) 받는지 확인하고, 받으면 "읽기만 하는 도구" 목록을 적은 출입증(도장)을 붙인다.
  워커는 출입증에 적힌 도구만 들여보내고, 설정이 바뀌면 출입증은 무효다. 기본 제공 세 서버는 원래 직원이라 출입증 창구에서 고치거나 내보낼 수 없다.
- 체크 질문: ① 일부러 틀린 주소를 넣었을 때 "왜 안 되는지"가 한 줄로 보이는가? ② 등록한 서버의 쓰기 도구가 "에이전트에 붙일 수 없음 — 사유"로 보이는가?
  ③ 기준 서버(업무 DB · 판단 엔진 · 지식 그래프)에는 고치기 · 지우기 버튼이 없는가? ④ "기준으로 되돌리기" 뒤 서버가 세 개로 돌아오는가?

## 원본 대조 (원본 파일:줄 → HYD)
| 원본 | 무엇 | HYD | 차이 · 판단 |
|---|---|---|---|
| process-gpt-vue3 `src/components/pages/account-settings/MCPServer.vue:64` · `:367-375` `isDefaultServer`(`is_default === true`) | 기본 서버는 연필 대신 눈(보기만) | `mcp_registry.BASE_SERVERS = ("neo4j","enterprise","hyd-dmn")` → 목록 `origin=seed`, `editable=false`, 상세에 고치기 · 지우기 버튼 없음 | 원본은 설정 칸 표시, HYD 시드에는 표시 칸이 없어 **이름**으로 정한다. 시드 `seed.sql:57-63` · 워커 `DEFAULT_ALLOWED_TOOLS` 와 세 곳이 같은지 시험이 대조(차이 있음, 유지) |
| 같은 파일 `:589-596` · `:661-668` | 기본 서버 저장 · 삭제를 화면에서 막음(`console.warn`) | API 에서 **403 사유**(`PUT/DELETE /api/mcp/servers/{기준}`), 이름 충돌 409 | 원본은 화면만 막음 → HYD 는 서버가 거절(포털 밖 호출도 막힘) |
| 같은 파일 `:520-536` `autoValidateServer`(저장 **뒤** 비동기 검사) · `:713-` `saveNewMCP` | 저장 → 검사 결과는 화면 상태에만 | 등록 · 고치기 = 형식 검사 → **연결 검사 통과해야 저장**(실패 422 + 사유 + 검사 결과), 결과는 `mcp_server_checks` 에 저장 | 원본은 실패해도 저장된다. HYD 완료 기준 "잘못된 서버는 사유와 함께 거절"에 맞춰 앞에서 막는다. 검사만 하고 저장 안 하는 `POST /api/mcp/check`(등록 전 검사)도 둔다 |
| `MCPEnvSecret.vue:38-54 · 356-385` | 비밀값을 별도 비밀 저장소로 | env · headers 값은 `tenants.mcp` 에 그대로 저장, 화면 · 응답은 U3 `mcp_check.masked`(`********`), 고칠 때 `********` 를 그대로 보내면 옛 값 유지(인자 안 주소 비밀번호 포함) | 비밀 저장소 분리는 TODO "넣지 않음"(비밀값 분리). 가림만 |
| process-gpt-mcp-validator@cf220bf `src/mcp_validator/validator.py:24-44` `_ALLOWED_CONNECTION_KEYS`(설명 같은 남는 칸을 버리고 연결) | 설정 정리 | `mcp_check.normalize` 가 command · args · env · cwd / url · headers 만 읽고 나머지(`description`, HYD 표시 `hyd`)는 무시 | 같음 |
| 같은 파일 `:94-189`(세션 → initialize → load_mcp_tools → `wait_for(timeout)` → 실패 사유: 명령 없음 · Connection closed · TaskGroup) | 검사 절차 | U3 `mcp_check.check` 재사용(stdio · streamable_http · sse, 사유 분류 11종) | 같음. 원본 Dockerfile 은 Node 를 넣어 `npx` 를 검사하지만 HYD process 이미지(python:3.12-slim)에는 Node · uv 가 없다 → 명령형은 아래 "실행 위치" 참고 |
| — (원본에 없음) | 도구별 읽기/쓰기 판정 · 에이전트 선택 제한 | U3 `read_only_verdict`(readOnlyHint=true + 쓰기 이름 아님)로 도구마다 판정 → 선택 가능 목록 · 워커 허용/차단 목록 | HYD 추가(CLAUDE.md §4 "승인 전 에이전트는 조회 · 계산 · 보고서만") |

## 만든 것 · 바꾼 파일
| 파일 | 내용 |
|---|---|
| `it/process/procsvc/mcp_registry.py` (새) | 등록 · 고치기 · 지우기 · 연결 검사(기록) · 등록 전 검사 · 선택 가능 목록 · 되돌리기 API, `MemoryMcpStore` / `PgMcpStore`(서버 한 칸만 `jsonb_set` / `#-`), 설정 해시 `fingerprint`, 실행기 허용(npx · uvx · uv · node · python · deno · bunx · bun · pipx), 셸 거절, 감사 `MCP_SERVER_REGISTERED/UPDATED/DELETED/REJECTED`, `MCP_RESET` |
| `it/supabase/migrations/20261008000042_mcp_server_checks.sql` (새) | `public.mcp_server_checks`(테넌트 · 서버마다 마지막 검사 1줄: fingerprint · status · error · error_kind · tools · server_info · checked_at), RLS 는 000040 과 같은 교육 정책 |
| `it/process/procsvc/mcp_api.py` (+6줄) | 도구 지도 목록에 `origin · origin_text · mine · editable · check · selectable · description` 칸을 더함(읽기 경로 그대로) |
| `it/process/procsvc/main.py` (+3줄) | `mcp_registry.mount(app, …)` |
| `it/agent-worker/worker/bridge.py` | `config_fingerprint`(포털과 같은 계산), `gate_servers`(기준 아닌 서버는 지금 설정과 맞는 도장이 있을 때만 연결), Codex `enabled_tools` 에 도장의 읽기 도구만, SSE 서버는 Claude Code `type: "sse"` |
| `it/agent-worker/worker/settings.py` | `run_allowed_tools`: 학생 서버에 `mcp__<서버>__*` 대신 도장의 읽기 도구만, `run_disallowed_tools`: 도장의 쓰기 · 표시 없음 도구 |
| `it/agent-worker/worker/runner.py` | `select_servers` 뒤 `gate_servers` → 빠진 서버는 task 기록에 "연결 검사 게이트로 연결하지 않은 도구 서버: 이름(사유)" 알림, `--allowedTools`(읽기만) · `--disallowedTools`(쓰기) |
| `it/portal/www/mcp.js` | "서버 등록" · "기준으로 되돌리기" 버튼, 등록 · 고치기 폼(이름 · 전송 방식 · 명령/인자/환경변수 또는 주소/접속 헤더 · 설명, "연결 검사만" / "검사 후 등록"), 카드에 출처 칩(기준 / 내가 등록 / 포털 밖에서 추가) · "에이전트 도구로 고를 수 있음/없음 — 사유", 상세에 "연결 검사"(기록) · 고치기 · 지우기(학생 서버만), 순수 함수 `window.hydMcp.register.bodyFrom` |
| `tests/test_b2_mcp_registry.py` (새) · `tests/test_u2_agents_skills.py`(3곳) | 아래 시험. U2 시험의 학생 서버 `fan-vib` 에 도장을 붙이고 기대값을 `mcp__fan-vib__*` → 도장의 읽기 도구로 바꿈(계약 변경) |

index.html · ui.js · seed.sql 은 바꾸지 않았다.

## API (B1 에이전트 폼이 쓰는 모양 포함)
모두 `PROCESS_MODE=instance` 필요(아니면 503). 실패는 `{"detail": "사유"}` 또는 연결 검사 실패면 `{"detail": {"reason": "사유", "check": {검사 결과}}}`(포털 `requestJ` 가 `detail.reason` 을 보여 준다).

- `POST /api/mcp/check` 등록 전 검사(저장 없음). 본문 = 아래 등록 본문(이름 없어도 됨) → `{check, config(가림), gate|null}`.
- `POST /api/mcp/servers` 등록 → **201** `{name, check, gate}` · 409 기준 이름 · 같은 이름 · 422 형식/검사 실패(저장 안 함).
  본문: `{name, transport: "streamable_http"|"sse"|"stdio", url?, headers?{}, command?, args?[]|"공백 문자열", env?{}, description?, timeout?: 0.5~20(기본 8), by?}`.
  이름 `^[a-z0-9](?:[a-z0-9]|-(?!-)){0,39}$`(밑줄 없음 — 도구 이름 `mcp__<서버>__<도구>` 가 갈라지지 않게).
- `PUT /api/mcp/servers/{name}` 고치기 → 200 `{name, check, gate}` · **403 기준 서버** · 404 · 422(옛 설정 유지). `********` 값은 옛 값 유지.
- `DELETE /api/mcp/servers/{name}?force=false&by=` → 200 `{name, deleted, agents_still_naming_it}` · **403 기준 서버** · 404 · 409 에이전트가 쓰는 중(`force=true` 면 지움).
- `POST /api/mcp/servers/{name}/check {timeout?, by?}` 등록된 서버(기준 포함) 검사 → `{name, check, state}`. 기록을 남기고, 학생 서버면 워커 도장(`hyd.gate`)을 새로 쓰거나(통과) 지운다(실패). 기준 서버 설정은 바꾸지 않는다.
- `POST /api/mcp/reset` 기준으로 되돌리기 → `{removed_servers, removed_checks, kept}` — 기준이 아닌 서버(포털 등록 · 랩업 SQL)와 **모든** 검사 기록을 지운다. 기준 세 서버 설정은 그대로.
- **`GET /api/mcp/selectable`** (B1 용):
```json
{"tenant": "hyd",
 "rule": "연결 검사를 통과했고 그 뒤 설정이 바뀌지 않은 서버의, 서버가 읽기 전용(readOnlyHint=true)으로 표시한 도구만 …",
 "servers": [{"name": "my-folder", "origin": "seed|user|external", "origin_text": "기준(기본 제공)|내가 등록|포털 밖에서 추가(랩업 SQL 등)",
              "mine": true, "editable": true, "transport": "streamable_http",
              "check": {"status": "ok|failed|stale|never", "checked_at": "…Z", "error": "사유|null", "error_kind": "refused|exec|…|null",
                        "elapsed_ms": 12, "server_info": {"name": "…", "version": "…"}, "tool_count": 6},
              "selectable": true, "reason": null, "agent_value": "my-folder",
              "tools": [{"name": "read_file", "title": null, "description": "…", "read_only": true, "selectable": true, "reason": null, "tool_id": "mcp__my-folder__read_file"},
                        {"name": "write_file", "read_only": false, "selectable": false, "reason": "에이전트에는 읽기 전용 도구만 붙입니다 — 서버가 이 도구를 쓰기 도구(readOnlyHint=false)로 표시했습니다 …", "tool_id": "mcp__my-folder__write_file"}]}],
 "selectable_tools": [{"server": "my-folder", "tool": "read_file", "tool_id": "mcp__my-folder__read_file"}]}
```
  - 에이전트(`users.tools`)에는 지금처럼 **서버 이름**(`agent_value`)을 적는다. 서버를 붙이면 실행 때 워커가 그 서버의 읽기 도구만 허용한다(도구 단위 선택 칸은 만들지 않았다 — 워커 계약이 서버 단위).
  - 저장 전 검사용 파이썬 함수: `mcp_registry.refuse_reasons(mcp_registry.store_for(repo), tenant, ["my-folder", …]) -> ["이름: 사유", …]`(빈 목록 = 모두 붙일 수 있음).
  - 기준 서버도 **검사 전(never)이면 selectable=false** 다(게이트는 모두에게 같다). 학생이 B1 폼을 열기 전에 도구(MCP) 화면에서 "연결 검사"를 누르거나 B1 이 `POST …/{name}/check` 를 부른다.
- 기존 `GET /api/mcp/servers` 목록의 서버마다 `origin · origin_text · mine · editable · check · selectable · description` 이 더 붙는다.

## 안전 — 워커 실제 실행에서도 읽기 표시 도구만 (확인 결과와 최소 변경)
확인: 바꾸기 전 워커는 기본 허용 목록에 없는 서버(학생 서버)에 `mcp__<서버>__*` 를 붙여 **쓰기 도구까지 미리 허용**했다(`settings.run_allowed_tools`, U2). 즉 제한이 적용되지 않았다.
최소 변경(`bridge.gate_servers` + `settings.run_allowed_tools/run_disallowed_tools` + runner 6줄):
1. 기준 서버(허용 목록이 이름을 적은 neo4j · enterprise · hyd-dmn)는 그대로 — 기본 에이전트 실행 설정 불변(시험).
2. 그 밖의 서버는 `hyd.gate.fingerprint == config_fingerprint(지금 설정)` 일 때만 `.mcp.json` / Codex 설정에 들어간다. 도장 없음 · 설정 바뀜 · 읽기 도구 0개면 빠지고 task 기록에 사유 알림.
3. Claude Code: `--allowedTools` 에 `mcp__<서버>__<읽기 도구>` 만, `--disallowedTools` 에 도장의 쓰기 · 표시 없음 도구. 검사 뒤 서버에 새로 생긴 도구는 어느 쪽에도 없어 헤드리스 실행에서 권한 요청 → 사람 질문(HITL)으로 간다(자동 실행 안 됨).
4. Codex: 서버 항목에 `enabled_tools = [읽기 도구]`.
5. `hyd` 키는 `.mcp.json` · Codex 설정에 쓰지 않는다(bridge 는 command · args · env · url 만 읽음, 시험).

## 학생 PC 에서 붙일 예시 (문서로만 — 실제 외부 연결 시험은 하지 않음, 코드 경로로 판단)
**실행 위치가 둘이다**: 연결 검사(등록 · "연결 검사")는 **process 컨테이너 안**(`mcp_check`), 실제 사용은 **워커**(강의 기본: 호스트 PC `scripts/run_worker_host.sh`, Claude Code 가 서버를 띄움).

### 로컬 폴더 읽기 MCP (`@modelcontextprotocol/server-filesystem`, Node · stdio)
- 명령형으로 등록(`command: npx`, `args: -y @modelcontextprotocol/server-filesystem C:/hyd/docs`) → process 이미지(python:3.12-slim)에 Node 가 없어 검사가
  "명령 없음 — 'npx' 를 process 컨테이너에서 찾을 수 없습니다"(`error_kind=exec`)로 **거절**된다. 폴더 경로도 컨테이너 안에는 없다. 이 거절은 정직한 결과이고 저장되지 않는다.
- 권장: 학생 PC 에서 HTTP 로 띄워 주소로 등록. 예) stdio 서버를 HTTP 로 감싸는 게이트웨이(예: `npx -y supergateway --stdio "npx -y @modelcontextprotocol/server-filesystem C:/hyd/docs" --outputTransport streamableHttp --port 8301`, 주소 경로는 게이트웨이 출력대로 — 확인 안 함).
  - 등록 주소: `http://host.docker.internal:8301/mcp`(process 컨테이너는 compose `extra_hosts: host.docker.internal:host-gateway` 로 호스트에 닿는다 — `compose.yaml` process 서비스). Linux 엔진이면 서버가 `127.0.0.1` 이 아니라 `0.0.0.0`(또는 docker0)에서 들어야 한다. Docker Desktop 은 호스트의 127.0.0.1 에도 닿는다.
  - 워커(호스트)에서는 `host.docker.internal` 이 호스트 LAN 주소로 풀리거나(Windows Docker Desktop 의 hosts 항목) 아예 안 풀린다(Linux). **`MCP_HOST_REWRITE` 에 `host.docker.internal:8301=127.0.0.1:8301` 을 더한다** — `run_worker_host.sh:11` 기본값 뒤에 쉼표로 이어 붙이거나 실행 전 `export`.
    재작성은 워커의 설치 단계(`bridge.install`)에서만 일어나고 도장 해시는 tenants.mcp 원래 설정으로 계산하므로, 재작성해도 게이트는 깨지지 않는다(시험 `test_host_rewrite_happens_after_the_gate_so_the_stamp_still_matches`).
  - 도구 판정: 읽기 도구(`read_file` · `read_text_file` · `list_directory` · `directory_tree` · `search_files` · `get_file_info` …)는 서버가 `readOnlyHint=true` 를 붙인 판일 때만 "붙일 수 있음". 표시가 없는 판이면 **전부 붙일 수 없음**(기본 닫힘)으로 나온다.
    `write_file` · `create_directory` 는 이름 규칙으로도 막히지만 `edit_file` · `move_file` 은 이름 규칙(`_WRITE_WORDS`)에 없어 **서버 표시에만 의존**한다(남은 위험).
- 명령형 서버를 워커 PC 에서만 돌리고 싶어도 등록은 컨테이너 검사를 통과해야 하므로 지금 구조에서는 안 된다(워커 쪽 검사 경로 없음 — 남은 판단).

### Notion MCP
- 공식 원격 서버(`https://mcp.notion.com/mcp`)는 OAuth 로그인 흐름이라 고정 헤더로 붙일 수 없다 → 검사가 "인증 실패"(401, `auth`) 또는 연결 실패로 거절할 것으로 본다(코드 경로: `mcp_check._http_error` 401 → auth). 확인 안 함.
- 로컬 서버(`@notionhq/notion-mcp-server`, Node): 명령형이면 위와 같이 컨테이너에 Node 가 없어 거절. HTTP 모드(`--transport http --port 8302`, 인증 토큰을 켜면 `Authorization: Bearer <토큰>`)로 띄우고
  `http://host.docker.internal:8302/mcp` + 접속 헤더 `Authorization=Bearer …` 로 등록(헤더는 저장되고 화면 · 응답 · 감사에는 `********`). Notion API 토큰(NOTION_TOKEN)은 호스트 환경변수에만 둔다. 워커는 `MCP_HOST_REWRITE` 에 `host.docker.internal:8302=127.0.0.1:8302`.
- 도구 판정: Notion 서버는 OpenAPI 에서 도구를 만든다(`API-post-search` · `API-retrieve-a-page` · `API-patch-page` · `API-post-page` …). readOnlyHint 를 붙이는지는 확인 못 했다 — 붙이지 않으면 **전부 붙일 수 없음**.
  `API-patch-page` 는 이름(patch)으로도 막히지만 `API-post-page`(페이지 생성)는 이름 규칙에 `post` 가 없어 표시에만 의존한다(`post` 를 넣으면 읽기인 `API-post-search` 도 막힌다 — 넣지 않음).
  표시가 없으면 랩업에서 "읽기 도구만 표시한 작은 Notion 래퍼 MCP"를 만들어 붙이는 것이 수업 흐름에 맞다(작동유 시나리오 "Notion 보고서"는 쓰기이므로 에이전트 도구가 아니라 사람 승인 뒤 process 쪽 일이다).

## 시험 (근거 `.evidence/b2-mcp/`)
- `pytest -q tests/test_b2_mcp_registry.py` → **26 passed**:
  - 기준 = 시드 = 워커 허용 목록(세 곳 대조), 포털 · 워커 해시 같음.
  - 정상 가짜 서버(U3 `tests/fixtures/mcp_fake_server.py`) stdio · HTTP 등록 → 도구 6개, 도장 읽기 `add · lookup · big_dump` / 막을 `greet · submit_note · delete_rows`, 저장은 원래 값 · 응답 · 목록은 가림.
  - 거절(사유): ftp 주소 · 주소 없음 · websocket · 셸 `bash` · 실행기 아닌 `rm` · 이름 형식 · 기준 이름(409) · 닫힌 포트(연결 거부 host:port) · 조기 종료 프로세스 · 컨테이너에 없는 명령(exec) — 모두 저장 안 됨, 감사 `MCP_SERVER_REJECTED`.
  - 선택 가능: 쓰기 · 표시 없음 · 쓰기 이름 도구 `selectable=false`+사유, 읽기 3개만 `selectable_tools`, 기준 서버도 검사 전엔 불가, `refuse_reasons`, SQL 로 넣은 서버(never) · 검사 뒤 SQL 로 바꾼 서버(stale) 불가 → 다시 검사하면 도장 갱신.
  - 기준 서버 PUT · DELETE(force 포함) 403, 기준 서버 검사는 기록만 남기고 `tenants.mcp` 불변.
  - 고치기: `********` 헤더 · 인자 속 주소 비밀번호 유지, 검사 실패 고치기는 옛 설정 유지, 지우기: 에이전트가 쓰면 409 · force 로 지움 · 검사 기록도 지움.
  - 되돌리기: 포털 등록 + SQL 추가 서버와 검사 기록 2건 지움, 기준 세 서버 그대로, 두 번째는 0건.
  - **새 서버 등록이 기본 에이전트 실행 설정을 바꾸지 않음**: 등록 전 · 후 기본 에이전트 실제 워커 실행의 `.mcp.json` 서버 · `--allowedTools` · `--disallowedTools` · `agent_settings().tools` 동일.
  - 워커: 도장 있는 학생 서버만 연결, `--allowedTools` 에 읽기 3개만(`mcp__my-fake__*` 없음), `--disallowedTools` 에 3개, 도장 없음 · 설정 바뀜 서버는 빠지고 사유 알림, Codex `enabled_tools` 읽기만, `MCP_HOST_REWRITE` 는 게이트 뒤에 적용(도장 유지), SSE 는 `type: sse`.
  - 포털 폼(node vm): 입력 → 요청 본문(인자 공백 나눔 · 환경변수/헤더 `이름=값` 줄), 빈 이름 · 명령 · 주소 · `=` 없는 줄 → 한국어 사유.
- **일부러 깨뜨리기**(`mutations.txt`, 9건 모두 잡힘): 검사 실패해도 등록 · 기준 서버 고치기 허용 · 쓰기 도구 선택 가능 · stale 끔 · 되돌리기가 기준까지 지움 · `********` 그대로 저장 · 워커 게이트 끔 · 워커 `mcp__x__*` 허용 · 워커 쓰기 차단 끔.
- PostgreSQL 실제 SQL(`pg-store.txt`): 임시 로컬 PostgreSQL 16(포트 55442, 시험 뒤 정지 · 삭제)에 최소 `tenants · users · proc_def_version` + 마이그레이션 `…42` 적용 → 등록 201 · 중복 409 · 거절 422 · 선택 가능 · 기준 검사 뒤 기준 칸 불변 · 기준 PUT/DELETE 403 · `********` 유지 · 검사 기록 행 · 지우기 · 되돌리기 뒤 `tenants.mcp == 시드` · 검사 기록 0행. (Supabase · docker 는 쓰지 않음)
- 포털 스모크(Playwright, 실제 `mcp_api` + `mcp_registry` + MemoryRepo + 가짜 MCP HTTP, `portal-smoke.txt` · `portal/1-list.png ~ 6-reset.png`): 기준 카드 "기준 · 고를 수 없음 — 연결 검사 전" → 닫힌 포트 등록 → 사유 → "연결 검사만" 도구 6개(붙일 수 있음 3 · 없음 3 사유) → "검사 후 등록" → 상세 "에이전트 도구로 고를 수 있음" · 비밀값 화면에 없음 → 고치기 폼 헤더 `Authorization=********` → 저장 뒤 원래 비밀값 유지 → 기준 서버 고치기 · 지우기 버튼 0 → 연결 검사 → 되돌리기 뒤 기준 두 서버만, 페이지 오류 0.
- 관련 묶음 `test_b2 · test_u2 · test_mcp_check · test_worker` → **112 passed**(`pytest-b2.txt`), 전체 `pytest -q` → **1534 passed, 1 skipped**(`pytest-full.txt`, 3분 51초), `node --check mcp.js` 통과.

## 메인이 라이브로 확인할 것 (합친 뒤 1회 — 검사기 도는 중 compose 금지)
1. 마이그레이션 `20261008000042_mcp_server_checks.sql` 적용(Supabase 로컬). 없으면 도구 지도 목록이 503 "검사 기록 표(mcp_server_checks)가 없습니다 — 마이그레이션 …42" 로 정직하게 실패한다.
2. process 재기동(`PROCESS_MODE=instance`). 워커 코드가 바뀌었으므로 호스트 워커 재시작(컨테이너 워커면 agent-worker 이미지 재빌드).
3. 포털 "도구(MCP)": 기준 카드 3개 "기준" 칩, 고치기 · 지우기 없음. enterprise · hyd-dmn "연결 검사" → "에이전트 도구로 고를 수 있음"(hyd-dmn 은 `submit_decision` 만 붙일 수 없음), neo4j → "명령 없음"(uvx 없음 — 아래 위험).
4. "서버 등록": 주소 `http://127.0.0.1:1/mcp` → 사유와 함께 거절. 주소 `http://dmn-mcp:8198/mcp` · 이름 `my-dmn` → 등록 → 도구 14 중 13 붙일 수 있음.
5. `GET http://localhost:8080/api/mcp/selectable` → 위 모양. `POST /api/mcp/reset` → `my-dmn` 사라짐, 기준 그대로(`select mcp from tenants` 가 seed 와 같음).
6. (실제 워커) 에이전트 하나의 `users.tools` 에 `my-dmn` 을 적고 처리 건 1건 → 워커 로그의 `--allowedTools` 에 `mcp__my-dmn__…` 읽기 도구만, `--disallowedTools mcp__my-dmn__submit_decision`. 도장을 지운 뒤(SQL 로 설정 한 글자 변경) 다시 → task 기록 "연결 검사 게이트로 연결하지 않은 도구 서버: my-dmn(검사한 뒤 설정이 바뀐 서버…)".

## 남은 위험 · 판단 (메인)
- **neo4j(기준, stdio `uvx`)는 process 컨테이너에서 검사가 늘 "명령 없음"** → `selectable` 이 false 라 B1 이 새 에이전트에 neo4j 를 붙이지 못한다(기본 에이전트 실행은 영향 없음 — 기준 서버는 워커 허용 목록으로 돈다). ① process 이미지에 uv 추가 ② 기준 서버는 검사 없이 선택 허용 ③ 그대로 — 메인 결정. 코드는 ①이면 그대로 통과한다.
- 기준 서버 hyd-dmn 의 `submit_decision`(쓰기)은 선택 가능 목록에서는 "붙일 수 없음"이지만, 워커는 기준 서버를 기존 허용 목록(`mcp__hyd-dmn__*`)으로 돌린다. B1 의 새 에이전트가 서버 `hyd-dmn` 을 통째로 붙이면 카드 제출(사람 승인 앞 단계, 설비 명령 아님)은 할 수 있다 — 기준 흐름의 "우선순위 · 카드 작성" 단계를 복제 에이전트가 맡으려면 필요하므로 유지했다. 막으려면 워커가 에이전트 출신(B1 `origin`)을 보고 기준 서버도 읽기만 허용해야 한다.
- stdio 등록은 웹 폼 입력을 process 컨테이너 안 명령으로 실행한다. 실행기만 받고 셸은 거절하지만 `python -c …` · `node -e …` 같은 인자는 막지 않는다(학생 PC 단독 스택 전제 — DECISIONS 110 경위). 공유 서버로 쓰게 되면 stdio 등록을 끄는 것이 맞다.
- 쓰기 이름 규칙에 `edit` · `move` · `post` 가 없어 서버 표시가 틀리면 그런 도구가 "붙일 수 있음"이 될 수 있다(위 Notion · 폴더 예).
- 검사 뒤 서버에 새로 생긴 도구는 허용 · 차단 어느 목록에도 없어 실행 중 권한 요청 → 사람 질문으로 간다(자동 실행은 안 됨). 다시 검사하면 판정된다.
- 검사 기록은 서버마다 마지막 1줄만 남긴다(이력 없음). 화면을 열 때의 자동 연결 확인(U3 GET …/tools)은 여전히 저장하지 않는다 — 게이트는 "연결 검사" 버튼 · 등록 · 고치기 때만 바뀐다.
- HANDOFF §9 체크박스는 단위 worktree 에서 고치지 않았다(공유 파일 충돌 방지) — 메인이 합칠 때 기록.
