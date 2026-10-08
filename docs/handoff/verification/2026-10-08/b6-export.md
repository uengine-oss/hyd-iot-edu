# B6 — 구성 내보내기 · 가져오기 = 막별 "출발본" + 하나의 "기준으로 되돌리기" (확정 TODO B6, DECISIONS 110 ⑤)

2026-10-08 밤. 브랜치 `worktree-b6-export`(기준 7cf6fd6 — B1~B5 합친 뒤). 마이그레이션 없음(`…46` 은 쓰지 않았다 — B1~B4 표만 읽고 쓴다).

## 1. 한 줄 요약

- `GET /api/config/export` → 학생이 만든 것만 담은 JSON 한 파일(형식 이름 `hyd-config-bundle` · 판수 1 · 만든 시각 · 내용 7칸). 기준(seed) 것과 MCP 비밀값은 들어가지 않는다.
- `POST /api/config/import` → **검증(아무것도 안 바꿈) → 진행 중 처리 건 확인 → 지금 구성 보관 → 되돌리기 → MCP → 스킬 → 에이전트 → 업무분장 → 흐름 등록(B3 사전 검사) → 단계 배정 → 배포 → 다시 내보내 파일과 대조**. 하나라도 실패하면 어느 단계 · 무엇이 들어갔고 무엇이 안 들어갔는지 + 보관본으로 적용 전 상태를 다시 세운다(`rolled_back`). 같은 파일을 두 번 가져와도 같은 결과.
- `POST /api/config/reset` → 하나의 "기준으로 되돌리기": B4 deploy-reset → B3 flows reset → B1 agents reset → B2 mcp reset → B5 ask reset. **먼저 409 조건을 모두 점검**하고 하나라도 있으면 아무것도 지우지 않는다.
- 포털 **관리 → "출발본 내보내기 · 불러오기 · 기준으로 되돌리기"** 접이식 패널에 카드 3개(파일 받기 · 파일 올리기(비밀값 입력 칸이 필요할 때만 나타남) · 기준으로 되돌리기).
- 비유: 출발본은 **실습실 "세이브 파일"**이다. 내가 꾸민 책상(내 에이전트 · 스킬 · 흐름 …)만 사진 찍듯 담고, 학교 비품(기준)은 담지 않으며, 사물함 비밀번호(MCP 토큰)는 빈칸으로 남긴다. 불러오기는 "책상을 비우고 → 사진대로 다시 놓고 → 사진과 대조"이고, 대조가 틀리면 원래 책상으로 되돌려 놓는다.

## 2. 파일 형식

```json
{"format": "hyd-config-bundle", "format_version": 1, "created_at": "2026-10-08T15:26:25.030Z", "tenant": "hyd",
 "base": {"definition": "anomaly_response", "version": "2.2", "parts_from": {"id": "anomaly_response", "version": "2.2"}},
 "note": "…", "summary": {"mcp_servers": 2, "skills": 1, "agents": 2, "role_members": 1, "flows": 2, "flow_versions": 2,
                          "assignments": 2, "deployments": 1, "secrets_needed": 2},
 "not_included": [{"what": "…", "reason": "…"}],
 "content": {
   "mcp_servers": [{"name": "my-http", "origin": "user", "transport": "streamable_http", "url": "http://…/mcp",
                    "headers": {"Authorization": "${HYD_SECRET:headers.Authorization}", "X-Team": "a"},
                    "secrets": [{"slot": "headers.Authorization", "label": "접속 헤더 Authorization"}]}],
   "skills": [{"skill_name": "cooler-check", "description": "…", "content": "---\nname: cooler-check …"}],
   "agents": [{"id": "agent:u-0c5031c6", "name": "쿨러 점검 에이전트", "role": "…", "goal": "…", "persona": "…", "model": "claude-haiku-4-5",
               "tools": ["enterprise", "my-fake", "my-http"], "skills": ["fan-vibration-check", "cooler-check"]}],
   "role_members": [{"role_id": "role:maint-mgr", "user_id": "user:kim-op", "role_name": "정비관리자", "user_name": "김운전"}],
   "flows": [{"definition_id": "my_cooler",
              "versions": [{"version": "1", "file_name": "redraw.bpmn", "bpmn": "<?xml …", "mapping": {…}, "definition_sha256": "…"}],
              "draft": {"file_name": "…", "bpmn": "…", "mapping": {…}}}],
   "assignments": [{"definition_id": "my_cooler", "activity_id": "Activity_0diag4n", "agent_id": "agent:u-0c5031c6"}],
   "deployments": {"flows": [{"definition_id": "my_cooler", "version": "2", "patterns": ["PUMP_LEAKAGE"]}], "reference": null}}}
```

- **학생 것만**: MCP = `mcp_registry.origin_of` 가 seed 아닌 서버(포털 등록 · 랩업 SQL), 스킬 · 에이전트 · 업무분장 = `origin='user'`, 흐름 = B3 `origin='user'` 판본 · 초안, 배정 = `activity_agent_map` 전부, 배포 = B4 `routes().flows`(배포 API로 올린 학생 흐름, 배포한 순서) + 기준 흐름의 운영 판본이 기준 판본이 아닐 때만 그 판본.
- **비밀값**: env · headers 중 이름이 비밀(`mcp_check.is_secret_key`: pass · token · key · auth · secret …)이거나 값에 Bearer · password= 꼴이 있는 것, 주소의 비밀번호, 비밀이 든 명령 인자 → `${HYD_SECRET:<칸>}` 자리표시 + `secrets` 목록. 화면 가림(B2)과 같은 판정이다.
- **에이전트 id 를 그대로** 담는다 — 단계 배정이 같은 에이전트를 가리키고, 두 번 가져와도 같은 id.
- **흐름**은 판본마다 `.bpmn` 원본 + 매핑 + 정의 해시(`definition_sha256`, 정렬 JSON 의 SHA-256). 불러올 때 B3 사전 검사로 다시 만든 정의가 이 해시와 같아야 한다(기준 정의 파일(부품)이나 에이전트 목록이 다른 환경이면 사유와 함께 거절).
- `not_included`: 담지 못한 것과 사유(예: 관리 화면 JSON 으로 등록해 그림이 없는 배포 흐름). 조용히 빠지는 것 없음.

## 3. 불러오기 검증 · 적용 · 대조 (`procsvc/config_bundle.py`)

검증에서 거절(422 `{reason, problems:[{where, reason}]}`, 아무것도 바꾸지 않음):
형식 이름 · 판수 · content 칸 모양 / MCP 이름 형식 · 기준 이름 · 중복 · 설정 형식(B2 `entry_from_body`) / 스킬 이름 · 기본 스킬과 같은 이름 · 빈 본문 · name 불일치(B1 `_skill_fields`) /
에이전트 id 모양(`agent:u-…`) · 기본 사용자 id 와 겹침 · 기본 에이전트 이름 · 빈 이름/목표 · 모델 모양 · **참조 없는 도구 서버 · 참조 없는 스킬** / 업무분장 없는 역할 · 사람 · 기본과 중복 /
흐름 id 형식 · 기준 흐름 id · 판본 번호가 1, 2, 3 … 으로 이어지는지 · 그림 읽기 · **B3 사전 검사(적용 뒤의 에이전트 목록으로 미리)** · 정의 해시 /
단계 배정: 흐름 없음 · 에이전트 단계 아님 · **참조 없는 에이전트** · 기본 담당 / 배포: 파일에 없는 흐름 판본 · 이 환경에 없는 기준 흐름 판본.

비밀값: 자리표시가 있는데 값을 안 주면 422 `{needs_secrets:[{server, slots:[{slot, label}]}]}`(아무것도 안 바꿈). `skip_missing_secrets: true` 면 그 서버만 건너뛰고 그 서버를 적은 에이전트 도구에서 빼며 `skipped` 에 사유를 남긴다.

적용(B1~B4 함수 재사용): MCP `mcp_registry.register`(실제 연결 검사 통과해야) → 스킬 `agent_authoring.create_skill` → 에이전트 `_agent_fields`(B2 게이트 포함) + `write_agent`(파일 id) + `link_skill`(붙인 순서대로) → 업무분장 `add_member` → 흐름 `FlowStore.save_draft` + `bpmn_import.check` + `FlowStore.register`(판본 번호 · 해시 대조) → 마지막 초안 → 배정 `set_assignment` → 배포 `rt.deploy_definition`(배포 순서대로 — 같은 패턴은 나중 배포가 이김).

대조: 적용 뒤 다시 내보낸 내용(비밀값 포함, 안에서만) == 파일 내용(건너뛴 서버 · 도구는 빼고, 자리표시는 넣은 값으로). 다르면 `failed_step: "verify"` + 다른 칸(한국어 이름) → 적용 전 상태로.

실패 응답(422): `{reason, failed_step, failed_label, applied:[{step,label,count,items}], partially_applied:[…], not_applied:[{step,label}], rolled_back, rollback_error}`. 실패 사유는 B1 · B2 · B3 의 사람이 읽는 사유를 그대로 올린다(예: `'MCP 서버' 단계에서 실패했습니다 — 연결 검사 실패로 등록하지 않았습니다 — 연결 거부 …`).

## 4. 원본 대조 (원본 파일:줄 · HYD 차이)

| 원본 (process-gpt-vue3@867e8cf) | 무엇 | HYD | 판정 |
|---|---|---|---|
| `src/components/ProcessDefinitionChatHeader.vue:128-137` | 정의 하나에 BPMN 파일 가져오기 메뉴(`accept=".bpmn,.jsonold,.csv"`) | 흐름은 B3 경로 그대로 쓰고, 출발본이 여러 흐름 · 판본의 `.bpmn` + 매핑을 한 파일로 묶는다 | 제품은 정의 단위, HYD 는 수업 출발본(구성 전체) — 회의 · 계약 요구(DECISIONS 110 ⑤), 차이 있음 유지 |
| `src/components/ProcessDefinitionModule.vue:66-68` | 모델러 `saveXML` 로 정의 그림 내보내기 | 판본마다 저장된 `.bpmn` 원본(B3 `proc_def_version.snapshot`)을 그대로 담음 | 같음(그림 원본 왕복) |
| `src/components/pages/account-settings/MCPEnvSecret.vue:38-54` | MCP 비밀값을 별도 비밀 저장소로 | 파일에는 자리표시만, 불러올 때 입력 · 건너뛰기 | 제품은 저장소 분리, HYD 는 "파일에 비밀값 0"(TODO "넣지 않음": 비밀 저장소) |
| `src/stores/adminConsole.ts:9-121` | 관리 콘솔: 삭제 기록 · 데이터 동결 등 — 구성 묶음 내보내기 없음 | 관리 화면에 출발본 패널 | 제품에 없는 기능(수업 운영용), 추가 |

## 5. 바꾼 파일

| 파일 | 내용 |
|---|---|
| `it/process/procsvc/config_bundle.py` (새) | 내보내기 · 검증 · 적용 · 대조 · 적용 전 상태 복원 · 하나의 되돌리기(사전 409 점검) · HTTP 3개 |
| `it/process/procsvc/main.py` (+3줄) | `config_bundle.register(app, runtime_factory=instance_mode.current, audit=_audit)` |
| `it/process/procsvc/bpmn_store.py` (+13줄) | `FlowStore.running()` — 되돌리기 전 확인용(학생 판본을 쓰는 진행 중 처리 건, 아무것도 안 바꿈). `reset` 은 그대로 |
| `it/process/procsvc/procdb.py` (+4줄) | **B3×B4 메모리 저장소 결함 수정**: B3 로 등록한 흐름은 메모리에 `proc_def` 머리가 없어 `record_deployment` 가 "등록되지 않은 정의 판본"으로 배포를 거절했다(PG 는 B3 등록이 머리를 넣으므로 정상). 판본이 등록돼 있으면 첫 배포 때 머리(prod_version NULL)를 만든다 — 등록 안 된 판본 거절은 그대로(`test_definition_deploy` 통과) |
| `it/portal/www/configBundle.js` (새) | `window.hydConfig.mount(el)` — 카드 3개, 파일 받기(Blob 다운로드), 파일 올리기 → 확인 → 비밀값 입력 칸(필요할 때만) · "비밀값이 없는 서버만 건너뛰고 불러오기", 결과(적용 · 건너뜀) · 실패(고칠 곳 · 막은 것 · 멈춘 단계 · 적용된/안 된 단계 · 되돌림 여부), 되돌리기(확인 대화상자, 단계별 한국어 결과) |
| `it/portal/www/index.html` (+2줄) | 관리 화면 패널 한 줄 · 스크립트 한 줄 |
| `tests/test_b6_config_bundle.py` (새, 30개) | 아래 §6 |

## 6. 시험

`tests/test_b6_config_bundle.py` 30개(PG 1개는 `HYD_B6_PG_DSN` 있을 때). 가짜 MCP 서버(U3/B2 시험의 stdio · HTTP)에 실제로 연결 검사를 한다.
- **같은 상태 · 두 번**: 학생 구성 한 벌(MCP 2 — stdio 비밀 환경변수 · HTTP 비밀 헤더, 스킬 1, 에이전트 2 — 새로 · 기본 복제, 업무분장 1, 흐름 2 — 판본 2개 + 초안만, 배정 2 — 학생 흐름 · 기준 흐름, 학생 흐름 배포) → 내보내기 → 하나의 되돌리기(5단계 순서, 기준만 남음, 기본 에이전트 실행 설정 불변) → 가져오기 → **에이전트 실행 설정(agent_settings 기본 + 단계 4개: summary · 지시문 · Codex 지시문 · 프로필) · 스킬 · MCP 설정과 게이트 · 업무분장 · 흐름 정의 · 그림 · 초안 · 배정 · 배포 표가 내보내기 전과 같음** → 한 번 더 가져와도 같음 → 두 번째 내보내기 = 첫 내보내기(만든 시각만 다름) · 감사 `CONFIG_RESET · CONFIG_IMPORTED ×2`.
- **기준 · 비밀값 없음**: 파일에 토큰 · Bearer 값 없음, 자리표시와 `secrets` 칸, 기준 서버 · 기본 스킬 · 기본 에이전트 · 기본 업무분장 · 기준 흐름 없음, 배포 칸 모양.
- **잘못된 파일 17가지 → 422 사유 + 상태 그대로**(검증에서 거절이라 되돌리기도 안 함): 형식 이름 · 판수 · 내용 없음 · 참조 없는 스킬 · 참조 없는 도구 서버 · 참조 없는 에이전트 · 없는 판본 배포 · 기본 에이전트 이름 · 기본 스킬 이름 · 기준 서버 이름 · 기준 흐름 id · 빈 스킬 · 판본 번호 건너뜀 · 부품 빠짐(B3 사전 검사) · 정의 해시 다름 · 사람 단계 배정 · 없는 역할.
- **비밀값**: 하나 빠지면 422 `needs_secrets`(칸 이름 · 한국어 설명) · 아무것도 안 바뀜 → 건너뛰기 → 그 서버만 빠지고 에이전트 도구에서 빠짐 · `skipped` 사유 · 다른 서버는 넣은 값으로 등록.
- **적용 중 실패 → 복원**: 형식은 맞고 연결만 안 되는 주소 → `failed_step=mcp`, 사유에 "연결 검사 실패", 멈춘 단계에서 들어간 것(my-fake) · 적용 안 한 6단계 · `rolled_back=true` · 상태 = 불러오기 전 · 감사 `CONFIG_IMPORT_FAILED`.
- **진행 중 처리 건**: 학생 흐름(반복 흐름)으로 진행 중 → reset 409 `blocking=[flows_reset]`(처리 건 id) · 배포 포함 아무것도 안 바뀜 · import 도 409 · 끝낸 뒤 reset 성공 / 학생 에이전트가 워커에 집힌(STARTED) 작업 → reset 409 `blocking=[agents_reset]` · 아무것도 안 바뀜.
- 빈 출발본(학생 것 없음) 불러오기 = 기준으로 되돌리기, 파일 본문 그대로 보내도 됨 · instance 모드 아니면 503 · `node --check configBundle.js`.
- **일부러 깨뜨려 잡힘**(시험 안에 둠): ① 업무분장 적용을 몰래 건너뛰게 하면 → "적용한 뒤 다시 읽은 구성이 파일과 다릅니다 — 업무분장 (개수 1 ≠ 0)"으로 실패, 복원도 같은 깨진 함수라 `rolled_back=false` + 사유(숨기지 않음) ② 비밀값 판정을 끄면 파일에 토큰 · Bearer 가 나온다(비밀값 시험이 공허하지 않음) ③ 사전 409 점검을 끄면 B4 배포 되돌리기가 먼저 일어난 뒤 B3 에서 409 → 반쯤 지운 상태(`done=[deploy_reset]`, 배포가 이미 기준) — 그래서 점검이 먼저다.
- **PostgreSQL**: docker · Supabase CLI 없이 버릴 로컬 PostgreSQL 16(포트 55446)에 마이그레이션 **36개 전부** + `seed.sql` 적용(오류 0) → `HYD_B6_PG_DSN=… pytest tests/test_b6_config_bundle.py` **30 passed**: PgRepo 로 학생 구성 → 내보내기(비밀값 없음) → 되돌리기 뒤 `users`(id · origin) · `tenants.mcp` 가 seed 와 같고 학생 판본 0 → 가져오기 ×2 → 상태 동일(jsonb 왕복 뒤에도 정의 해시 같음), `proc_def` 학생 머리 `prod_version=2 · origin=user · bpmn=원본`. 시험 끝에 되돌리기, 클러스터 정지 · 삭제.
- 관련 묶음(B6 · B3 · B4 · U4 · B1 · B2 · B5) **129 passed, 2 skipped**. 전체 `pytest -q` **1664 passed, 4 skipped**(5분 1초, `.evidence/b6/pytest-full.log`).
- 화면(Playwright, MemoryRepo API(학생 구성 미리 만듦) + 정적 포털, 8080 요청은 시험 서버로 · 나머지 서비스 차단 — 실제 스택 미접촉, `.evidence/b6/`): 관리 → 패널 카드 3개 → 파일 받기(`hyd-starter-….json`, 비밀값 없음, 요약 "에이전트 2 …") → 기준으로 되돌리기(확인 대화상자) → 파일 올리기 → 불러오기 → 비밀값 입력 칸 2개 → 값 넣고 불러오기 → "출발본을 불러왔습니다 — 11건 적용"(단계별 이름 목록) → 화면에 영문 칸 이름 0 · 페이지 오류 0 (9/9, `b6-ui-smoke.json` · `b6-secrets.png` · `b6-imported.png`).

## 7. 메인이 합친 뒤 라이브로 확인할 것 (배포 → 검사 순서, 검사기 도는 중 compose 금지)

0. 마이그레이션 없음. process 이미지 재빌드(새 `config_bundle.py`, `main.py` · `bpmn_store.py` · `procdb.py`), 포털 정적 파일 갱신. `PROCESS_MODE=instance`, `ENTERPRISE_BACKEND=supabase`.
1. 깨끗한 상태: `curl :8080/api/config/export | jq .summary` → 모두 0, `not_included` 빈 목록.
2. 학생 구성 만들기(B1~B4 화면): 도구(MCP) → 서버 등록(예 `my-dmn` = `http://dmn-mcp:8198/mcp`, 접속 헤더 `Authorization=Bearer test-123456`) → AI 에이전트 → 새 스킬 · 새 에이전트(도구 `my-dmn` · `enterprise`) · 담당 배정(원인 진단 → 새 에이전트) · 역할에 사람 → 판단 → 흐름 가져오기(`tests/fixtures/bpmn/anomaly_response_redraw.bpmn`, id `my_cooler`, 시작 패턴 펌프만) → 판본 등록 → 관리 → 흐름 판본 배포.
3. 관리 → **출발본 내보내기 → 파일 받기** → 파일에 `test-123456` 이 없고 `${HYD_SECRET:headers.Authorization}` 가 있는지, `sys:agent` · `anomaly_response` 정의가 없는지.
4. 내보내기 직전 값 적어 두기: `GET /api/flows/deployments`(routes) · `GET /api/agents/<새 id>`(실행 설정) · `select id, version, md5(definition::text) from proc_def_version where origin='user'`.
5. **기준으로 되돌리기** → `select id, origin from users where origin='user'` 0행, `select mcp from tenants` = seed, `GET /api/flows/deployments` `at_reference: true`.
6. **출발본 불러오기**(3의 파일) → 비밀값 칸에 `Bearer test-123456` → "출발본을 불러왔습니다" → 4의 값이 모두 같은지(md5 포함). 같은 파일을 한 번 더 → 같은 값.
7. 진행 중 처리 건: 펌프 결함 주입 1건(학생 흐름으로 열림) → 되돌리기 → "진행 중인 처리 건 … 아무것도 바꾸지 않았습니다" 409 · 배포 표 그대로 → 처리 건을 닫은 뒤 다시.
8. (선택) 실제 워커 1개 · 쿨러 1건: 불러온 뒤 원인 진단 담당이 파일의 에이전트 id 로 실행되는지(B1 §8 4번과 같은 확인).

## 8. 남은 위험

- **불러오기 = 되돌리기 → 적용**이라 B3 되돌리기 규칙대로 학생 판본으로 **끝난** 처리 건은 목록에서 숨겨진다(`is_deleted`, 정의가 지워지므로). 불러온 뒤 같은 id · 판본으로 다시 등록돼도 숨김은 풀리지 않는다. 질문 기록(B5)은 구성이 아니라 불러오기에서는 지우지 않는다(하나의 되돌리기에서만 지움).
- **MCP 는 불러올 때 다시 연결 검사**를 한다(B2 게이트를 지키려고 — 도장을 파일에서 믿지 않음). 학생 PC 에서 그 서버가 떠 있지 않으면 MCP 단계에서 실패하고 적용 전 상태로 돌아간다. 비밀값이 없는 서버만 "건너뛰기"가 있고, "연결 안 되는 서버만 건너뛰기"는 없다(필요하면 추가).
- **정의 해시가 출발본을 기준 정의 파일(부품)에 묶는다**: `PROCESS_DEFINITION_FILE` 이나 `anomaly_response_v22.json` 이 바뀌면 그 전 출발본의 흐름은 "다시 만든 정의가 내보낼 때와 다릅니다"로 거절된다(조용히 다른 흐름이 되지 않게 — 의도). 기준을 바꾸면 강사가 출발본을 다시 만든다.
- **비밀값 판정은 이름 · 값 모양 휴리스틱**(B2 화면 가림과 같음): 비밀 이름이 아닌 칸(예: `X-Notion: ntn_…`, `NOTION=…`)에 넣은 토큰은 파일에 남는다. 강사는 받은 파일을 한 번 훑어볼 것. 모든 헤더 값을 비밀로 보는 쪽으로 바꿀지는 결정 필요.
- 랩업 SQL 로 넣은 MCP 서버(origin external)는 담기지만 불러오면 포털 등록(origin user)이 된다(B2 기준으로 둘 다 "학생 것"이라 되돌리기 동작은 같음). 랩업 SQL 로 넣은 에이전트 · 스킬은 origin 이 없으면 기준(seed)으로 보아 담지 않는다(B1 남은 위험과 같음).
- 에이전트 id 를 파일 그대로 쓰므로, 다른 환경에 같은 id 의 기본 사용자가 있으면 거절된다(사유 표시).
- 복원(rolled_back)도 같은 적용 경로라, 복원 중 MCP 연결이 안 되면 `rolled_back=false` + 사유로 끝난다(숨기지 않음). 그때 상태는 "되돌린 뒤 일부만 다시 세운" 상태 — 출발본을 다시 불러오면 된다.
- 배포 이력(`proc_def_deployment`)에는 불러올 때마다 withdraw · deploy 기록이 쌓인다(지우지 않음 — 감사 기록).
- 동시 실행 막기는 process 한 프로세스 안의 잠금이다(uvicorn 워커 1개 전제 — 지금 compose 와 같음).
- `procdb.MemoryRepo.record_deployment` 수정은 메모리 저장소(시험 · `PROCESS_REPO=memory`)만 바꾼다. PG 경로는 그대로.
- HANDOFF §9 · TODO B6 줄 · 작업보고는 합칠 때 메인이 갱신(공유 파일 충돌을 피해 이 단위에서는 고치지 않음).

## 9. 사용자가 스스로 판정할 체크 질문

- 받은 출발본 파일을 메모장으로 열었을 때, 내가 넣은 MCP 토큰 값이 어디에도 없고 `${HYD_SECRET:…}` 자리표시만 있는가?
- 출발본을 불러온 뒤 "AI 에이전트"의 내 에이전트 실행 설정 · "흐름 판본 배포"의 경보 → 흐름 표가 받기 전과 똑같은가? 한 번 더 불러와도 똑같은가?
- 일부러 스킬 이름 하나를 지운 파일을 올렸을 때 "참조 없는 스킬"처럼 **어디가 왜** 틀렸는지 보이고, 내 구성은 그대로 남는가?
- 내 흐름으로 처리 건이 돌고 있을 때 "기준으로 되돌리기"를 누르면 아무것도 지우지 않고 그 처리 건 때문이라고 말하는가?
