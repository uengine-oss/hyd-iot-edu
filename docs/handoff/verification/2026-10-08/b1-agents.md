# B1 — 에이전트 · 스킬 직접 만들기 + 역할 · 단계 배정 + 되돌리기 (확정 TODO B1, DECISIONS 110 ①)

2026-10-08 밤. 브랜치 `worktree-b1-agents`. U2(읽기 전용, `u2-agents-skills.md`)와 U5(업무분장 읽기, `u5-inbox.md`) 위에 쓰기를 더했다.

## 1. 한 줄 요약

- 포털 "AI 에이전트" 화면에서 **에이전트 만들기 · 고치기 · 복제 · 지우기**(이름 · 역할 · 목표 · 성격 · 모델 · 쓸 도구 · 스킬), **스킬(SKILL.md) 쓰기 · 고치기 · 지우기 · 붙이기 · 떼기**, **담당 배정** 탭(단계 → 에이전트, 역할 → 사람), **기준으로 되돌리기** 단추.
- **기본(시드) 보호**: 기본 에이전트 · 시스템 수행자 · 기본 스킬 · 기본 업무분장은 고치기 · 지우기 · 스킬 붙이기를 403 + 사유로 거절하고, 에이전트는 "복제해서 고치기"만 된다. 포털에서 만든 행은 `origin='user'`("내가 만든" 표시).
- **단계 → 에이전트**는 정의(BPMN) 원본을 바꾸지 않는다. 배정 표 `activity_agent_map`이 있고, 흐름이 그 단계에 닿는 순간 작업 행의 담당(`todolist.user_id`)을 배정 에이전트로 쓴다. 워커는 작업 행 담당으로 프로필 · 스킬 · 모델 · 도구를 읽으므로 **배정 = 실제 실행 담당**이다. 배정을 지우면 다음에 열리는 단계부터 기본 담당(`sys:agent`)으로 돌아간다.
- `POST /api/agents/reset`: 내가 만든 에이전트 · 스킬 · 단계 배정 · 넣은 업무분장만 지운다. 아직 집히지 않은 열린 단계는 기본 담당으로 되돌리고, 실행 중인 작업이 있으면 아무것도 지우지 않고 409로 거절한다.
- 비유: 기본 에이전트는 **회사 표준 직무기술서**(아무도 고쳐 쓰지 못함 — 복사본을 만들어 고친다), 단계 배정은 **근무표**(직무기술서는 그대로 두고 오늘 이 업무를 누가 맡는지만 적는다), 되돌리기는 **내가 붙인 포스트잇만 떼기**다.

## 2. 저장 위치 (migration `20261008000041_agent_authoring.sql`)

| 무엇 | 원천 | 더한 것 |
|---|---|---|
| 에이전트 | `public.users`(is_agent) | `origin text default 'seed'`('seed' 보호 / 'user' 포털에서 만든 것) · `updated_at` |
| 스킬 | `public.tenant_skills` | `origin` |
| 에이전트 ↔ 스킬 | `public.agent_skills` | — (내가 만든 에이전트 · 스킬을 지우면 FK cascade 로 함께) |
| 역할 → 사람 | `public.role_members` | `origin` |
| 단계 → 에이전트 | **새 표 `public.activity_agent_map`**(tenant_id, proc_def_id, activity_id) → agent_id(FK users, on delete cascade) · by_user | 모든 행이 포털에서 만든 것 |
| 배정 적용 기록 | `public.task_assignments` | `kind` 허용값에 `'agent_map'` 추가 |

seed.sql 은 마이그레이션 뒤에 들어가 기본값 `'seed'`로 표시된다(seed 변경 없음). **랩업 SQL 로 넣은 행도 origin 을 적지 않으면 'seed'(보호)**다 — 포털에서 고치고 되돌리기로 지우게 하려면 `origin='user'`로 넣는다.

## 3. 실행 경로 (배정이 실제 실행에 반영되는 길)

1. 흐름이 단계에 닿음 → 엔진의 다섯 자리(`instances.start_definition` · `process_workitem` · `_fire_timeout` · `_abort_before_action` · `rework_runtime`)가 저장 전에 `inbox.apply_advance(rt, inst, adv)`를 부른다(U5 훅).
2. `apply_advance` 첫 줄이 `agent_authoring.apply_agent_map`을 부른다: IN_PROGRESS 가 된 에이전트 단계(agent_mode + `cliagents`)마다 `activity_agent_map`을 보고, 있으면 `user_id`·`username`을 그 에이전트로, `assignees`에 `{kind:'agent', via:이전, resolution:'agent-map'}`, `task_assignments(kind='agent_map')` 한 줄. 같은 트랜잭션.
3. 워커 `fetch_pending_task`는 `agent_orch`로 집으므로(담당과 무관) 그대로 집는다 → `context.prepare`가 `row.user_id`로 users 를 읽어 `Context.profile` → `runner`가 `agents_store.agent_settings(profile, activity)`로 모델 · MCP 서버 · 스킬 · 지시문을 정한다(U2 경로 그대로).
4. 배정이 없으면 2는 아무것도 하지 않는다 → 정의의 역할 담당(`new_workitem`이 쓴 `sys:agent`)이 실행.

`AGENT_BRIDGE=legacy`(수업 기본 결정론 경로)에서는 2까지는 같고(담당 표시 · 기록), 판단은 내장 경로가 한다. 담당 배정 탭에 이 사실을 경고로 띄운다(`bridge_note`).

## 4. API (`procsvc/agent_authoring_api.py`, 로직 `procsvc/agent_authoring.py`)

| 요청 | 내용 | 거절 |
|---|---|---|
| `GET /api/agent-authoring/options` | 폼 선택지: 등록된 도구 서버(tenants.mcp, 검사 상태 `check`가 있으면 함께) · 스킬(origin) · 모델 예시 | |
| `POST /api/agents` | `{name, role, goal, persona, model, tools[], skills[]}` → `agent:u-<hex>`, origin=user | 이름 · 목표 빈칸 422, 같은 이름 409, 등록 안 된 도구 서버 422(등록된 목록 함께), 없는 스킬 422, 모델 이름 모양 422 |
| `PUT /api/agents/{id}` | 전체 바꾸기(스킬 목록도 교체 — 제품 replaceAgentSkills 와 같음) | 기본 · 시스템 수행자 403("복제해서 고치기") |
| `DELETE /api/agents/{id}` | 지우기 + 배정 · 붙이기 cascade, 열린 단계는 기본 담당으로 | 기본 403, 실행 중 작업 409 |
| `POST /api/agents/{id}/clone` | 사본(origin=user, 이름 "… 사본", 겹치면 "… 사본 2") | 시스템 수행자 403 |
| `POST /api/agents/{id}/skills` · `DELETE …/skills/{name}` | 붙이기 · 떼기 | 기본 403, 이미 붙음 409, 없음 404 |
| `POST /api/skills` · `PUT` · `DELETE /api/skills/{name}` | SKILL.md 쓰기 | 빈 본문 422, 폴더 이름 모양 422, 문서 머리 name 불일치 422, 설명 없음 422, 이름 중복 409, 기본 스킬 고치기 · 지우기 403 |
| `GET /api/agent-assignments` | 단계(기본 담당 · 지금 배정) · 고를 수 있는 에이전트 · 역할별 구성원(origin) · 사람 · `bridge_note` | |
| `PUT /api/agent-assignments` | `{definition_id, activity_id, agent_id}` | 사람 · 시스템 단계 404, 시스템 수행자 422, 기본 담당과 같음 422 |
| `DELETE /api/agent-assignments/{def}/{activity}` | 배정 지우기 | 없음 404 |
| `POST /api/role-members` · `DELETE /api/role-members?role_id=&user_id=` | 역할에 사람 넣기 · 빼기 | 없는 역할 · 사람 아님 404, 이미 409, 기본 업무분장 빼기 403 |
| `POST /api/agents/reset` | 되돌리기 → `{agents, skills, attachments, assignments, role_members, returned_tasks}` | 실행 중 409(아무것도 안 지움) |

읽기 API(`agents_api.py`)는 카드에 `origin`·`editable`, 단계에 `assigned`를 더했고, "맡은 단계"는 배정을 따른다(배정한 단계는 기본 에이전트 목록에서 빠지고 배정 에이전트에 붙는다 — 엔진과 같은 규칙).

## 5. 원본 대조 (원본 파일:줄 · HYD 차이)

| 원본 (process-gpt-vue3@867e8cf) | 무엇 | HYD | 판정 |
|---|---|---|---|
| `src/components/ui/field/AgentField.vue:64-170` | 에이전트 폼: 이름 · 역할 · 목표 · 성격 · 도구(등록 MCP 서버 콤보 + 서버별 검사 결과) · 스킬 · 공급자/모델 | 같은 칸, 도구는 tenants.mcp 서버 체크박스 + 검사 상태 표시만(검사는 B2) · 모델은 자유 입력 + 예시 | 공급자 고르기 · 서버별 도구 거르기(tool_filters) 없음 — 회의 · 계약 요구 아님, 차이 있음 유지 |
| `src/components/api/ProcessGPTBackend.ts:4250-4306` | putAgent(users 칸 upsert → replaceAgentSkills) · deleteAgent | `write_agent`(users + agent_skills 교체) · `remove_agent` | 제품에는 기본 보호가 없다 → HYD 는 origin 으로 기본 보호(DECISIONS 110 ①) |
| 같은 파일 `:4393-4441` | replaceAgentSkills · deleteAgentSkill · deleteAgentSkillsBySkill | `link_skill` · 스킬 삭제 시 FK cascade | 같음 |
| `src/components/SkillsManagement.vue:995-1058` | 스킬 업로드(파일 · URL) · 삭제 | 포털 textarea 로 SKILL.md 쓰기 · 고치기 · 지우기 | 업로드 · Git 없음(본문은 tenant_skills.content — U2 결정), 유지 |
| `src/components/ui/field/AgentSelectField.vue:6-16,61-62` | 단계의 orchestration · 담당 에이전트를 **정의 activity 에 직접** 씀 | 정의는 그대로, `activity_agent_map` → 단계가 열릴 때 작업 행 담당으로 | 기준 BPMN 보호(공통 브리프) 때문에 다름 — 의도, 유지 |
| `src/router/MainRoutes.ts:507-508` `/work-assignment`(WorkAssignment.vue) | 역할별 담당자 편집 | 담당 배정 탭 "역할 → 사람" | 기본 업무분장 빼기는 거절(되돌리기가 기본을 복원할 필요가 없게), 차이 있음 유지 |
| process-gpt-cli-agent@a4fd1a2 `core/subagents.py:38-55` | 에이전트 role · goal · persona · skills · tools 로 실행 구성 | U2 `agent_settings` 그대로 — 배정 에이전트가 들어갈 뿐 | 같음 |

## 6. 바꾼 파일

| 파일 | 내용 |
|---|---|
| `it/supabase/migrations/20261008000041_agent_authoring.sql` (새) | origin 칸 3개 · users.updated_at · activity_agent_map · task_assignments kind 'agent_map' · RLS |
| `it/process/procsvc/agent_authoring.py` (새) | 검사 · 보호 · 복제 · 배정 · `apply_agent_map` · 되돌리기, Memory/Pg 저장소 믹스인 |
| `it/process/procsvc/agent_authoring_api.py` (새) | 위 §4 라우트 |
| `it/process/procsvc/agents_api.py` | 카드 origin · editable, 단계 배정 반영(assigned · default_performers), 스킬 origin, 문서 주석 |
| `it/process/procsvc/inbox.py` | `apply_advance` 첫머리에 `apply_agent_map` 한 줄 |
| `it/process/procsvc/procdb.py` | MemoryRepo/PgRepo 에 믹스인 추가(가져오기 한 줄 + 클래스 줄) |
| `it/process/procsvc/main.py` | `agent_authoring_api.mount(app)` 두 줄 |
| `it/agent-worker/Dockerfile` | `agent_authoring.py` 복사 한 줄(procdb 가 가져옴 — 이 이미지는 지금 쓰지 않음, §9) |
| `it/portal/www/agents.js` | 새 에이전트 · 스킬 폼, 고치기 · 복제 · 지우기, 스킬 붙이기 · 떼기, 담당 배정 탭, 기준으로 되돌리기, 에이전트 이름을 포털 전체 "누가" 표시에 등록 |
| `it/portal/www/index.html` | agents.js 캐시 버전 문자열만 |
| `tests/test_b1_agent_authoring.py` (새) | §7 |
| `tests/test_u2_agents_skills.py` | 읽기 전용 단언의 주석만(agents_api 자체는 여전히 읽기만) |

## 7. 시험

`tests/test_b1_agent_authoring.py` 14개(PG 1개는 `HYD_B1_PG_DSN` 있을 때):
- 기본 보호: 기본 에이전트 · 시스템 수행자 고치기 · 지우기 · 스킬 붙이기 · 떼기 → 403 + "보호" 사유, "복제해서 고치기" 안내, 랩업 스킬(origin 없음)도 403, 복제는 같은 모델 · 도구 · 스킬 · 목표, 이름 겹침 "사본 2".
- **불변**: 스킬 · 에이전트 · 복제 · 단계 배정 · 업무분장 · 고치기를 다 한 뒤 기본 에이전트의 `agent_settings`(단계 선언 없음 + 에이전트 단계 4개, summary · 지시문(Claude · Codex) · 프로필) JSON 이 한 글자도 같음, API `run.instructions/settings` 도 같음. **깨뜨림**: 저장소에 직접 기본 에이전트에 스킬을 붙이면 같은 비교가 다르다고 잡는다.
- 입력 거절 13가지(이름 · 목표 빈칸, 등록 안 된 서버, 없는 스킬, 모델 모양, 같은 이름, 빈 스킬 2종, 폴더 이름 모양 · 빈칸, name 불일치, 설명 없음, 스킬 중복).
- 스킬 고치기 → 다음 실행이 읽는 같은 행이 바뀜, 붙이기 · 떼기 · 지우기(붙은 에이전트에서 cascade), MCP 검사 상태가 있으면 선택지에 붙음.
- **실제 워커 실행**(MemoryRepo + 가짜 CLI): 원인 진단을 새 에이전트에 배정 → 작업 행 담당 = 새 에이전트, task_assignments `agent_map`(바꾼 사람 포함), 정의 원본 불변, 요청 모델 = 새 에이전트 모델, 지시문에 이름 · 목표 · 성격, 작업 폴더 `.claude/skills/cooler-check/SKILL.md` = 저장 원문, `.mcp.json` = 새 에이전트 서버만, task.json agent id. 배정 안 한 단계는 기본 에이전트로 실행.
- **배정 → 실행 담당 변경 → 지우기 · 되돌리기 후 원복**: 배정 지우기 → 다음 단계 기본, 열린 단계는 되돌리기로 sys:agent 로 돌아감(기록 남음), 되돌리기 뒤 새 처리 건은 기본.
- 지우기: 실행 중(STARTED) 409(지우기 · 되돌리기 모두, 아무것도 안 지움), 풀린 뒤 지우면 열린 단계 기본 담당으로.
- 역할 → 사람: 넣기(한 명 → 역할 공용으로 바뀜), 중복 409, 기본 빼기 403, 넣은 사람 빼기, 되돌리기가 넣은 것만 지움.
- 되돌리기: 기본 users · 스킬 그대로, 내가 만든 것 0, 두 번 눌러도 기본 그대로.
- legacy 모드 409.
- **일부러 깨뜨려 확인(변형 시험, 되돌림)**: `apply_agent_map` 호출을 빼면 3개 실패 · 기본 보호(`_protect`)를 끄면 1개 실패 · 되돌리기가 기본 스킬까지 지우게 하면 1개 실패.
- **PostgreSQL**: docker · Supabase CLI 없이 버릴 로컬 PostgreSQL 16 에 마이그레이션 전부(000041 포함) + seed.sql 적용 → seed 행 origin 전부 'seed' 확인, `HYD_B1_PG_DSN` 으로 PgRepo 시험(보호 403 · 이름 중복 409 · 고치기 · 배정 · 실제 워커 경로(PgRepo claim) 모델 · 스킬 파일 · `.mcp.json` · 되돌리기 · 열린 단계 원복 · 기본 users 그대로) 통과, 시험 처리 건 정리 · DB 삭제.

결과: `pytest -q` 전체 **1521 passed, 2 skipped**(PG 시험은 DSN 없으면 건너뜀). PG 포함 B1 · U2 · U5 묶음 34 passed. `node --check it/portal/www/agents.js` 통과.
화면: MemoryRepo 시험 서버(8180) + 정적 포털을 Playwright 로 — 8080 요청은 시험 서버로 돌리고 나머지 서비스 요청은 차단(실제 스택 미접촉). 스킬 만들기 → 중복 사유 표시 → 빈 에이전트 사유 → 에이전트 만들기(도구 · 스킬 체크) → 담당 배정 → 역할에 사람 넣기 → 기본 에이전트 복제 → 되돌리기 토스트("에이전트 2 · 스킬 1 · 단계 배정 1 · 업무분장 1"), 콘솔 오류 0, 화면에 영문 id 0. 증거 `.evidence/b1/`(git 밖).

## 8. 메인이 합친 뒤 라이브로 확인할 것

1. 마이그레이션 000041 적용 → `select id, origin from users` 전부 seed, `\d activity_agent_map`.
2. 포털 "AI 에이전트": 기본 에이전트 카드 "기본", 상세에 "복제해서 고치기"만. `curl -X PUT :8080/api/agents/sys:agent -d '{"name":"x","goal":"y"}'` → 403 사유.
3. 스킬 탭 "새 스킬"(예: cooler-check) → 에이전트 탭 "새 에이전트"(도구 업무 DB, 스킬 체크) → 담당 배정 탭 "원인 진단" → 새 에이전트.
4. 실제 워커(AGENT_BRIDGE=off, 워커 1개, 20배속, 쿨러 1건): `todolist` 원인 진단 행 `user_id` = `agent:u-…`, `task_assignments.kind='agent_map'`, 워커 작업 폴더 `<WORKSPACE_ROOT>/hyd/<작업 id>/.claude/skills/cooler-check/SKILL.md`, `.mcp.json` 서버 = enterprise 만, `context/task.json` agent.id = 새 에이전트, 처리 건 화면 담당 이름 = 새 에이전트 이름. 나머지 세 단계는 sys:agent.
5. 기본 에이전트 상세의 "실행 지시문에 더해지는 내용" · 단계별 실행 설정이 3 전과 같음(맡은 단계 목록만 3개로 줄어듦).
6. "기준으로 되돌리기" → 토스트 개수, 다음 경보의 원인 진단 담당 = sys:agent, 기본 users · 업무분장 그대로.
7. AGENT_BRIDGE=legacy(수업 기본)에서는 담당 배정 탭에 경고 문구가 보이고, 배정한 단계 담당 이름은 바뀌지만 판단은 내장 경로(이벤트 이름 "legacy agent").

## 9. 남은 위험

- **legacy 경로**: 수업 기본(AGENT_BRIDGE=legacy)에서는 배정이 기록 · 표시만 되고 판단은 내장 결정론 경로다. 학생 에이전트의 차이를 보려면 워커 경로 또는 A10 시험 실행. 화면이 경고로 알린다.
- **도구 지도(U3 `mcp_api.usage`)는 배정을 모른다**: "이 서버를 어느 단계에서 누가 쓰나"가 여전히 정의의 역할 담당(sys:agent) 기준. B2 와 합칠 때 `agents_api.agent_steps(…, maps)`를 쓰면 맞춰진다.
- **랩업 SQL 행은 origin 'seed'**: U2 문서의 SQL 예시에는 origin 이 없어 랩업에서 넣은 에이전트 · 스킬은 보호되고 되돌리기로 지워지지 않는다. 랩업 재료를 쓸 때 `origin='user'`를 넣을지 정해야 한다(실라버스 단계).
- **지운 에이전트의 지난 기록**: 끝난(DONE) 작업 행의 담당 id 는 그대로 남아, 그 에이전트를 지운 뒤에는 이름 대신 id 가 보일 수 있다.
- **실행 중 409**: 워커가 죽어 STARTED 로 남은 행이 있으면 임대 만료 · 회수 전까지 지우기 · 되돌리기가 거절된다(사유에 건수).
- **배정은 정의 id 단위**(판본 무관). B3/B4 로 새 판본 · 새 정의가 들어오면 에이전트 단계는 배정 표에 자동으로 나타나고, 단계 id 가 바뀐 옛 배정은 `orphans`로 응답에 남는다(화면 표시 없음).
- **MCP 검사 상태(B2)**: 합칠 자리는 `repo.mcp_check_status(tenant) → {서버: {ok|status|error}}` 또는 서버 설정의 `check` 칸. 지금은 표시만, 선택을 막지 않는다(B2 범위).
- **워커 Docker 이미지**: Dockerfile 에 한 줄 추가했지만 이 이미지는 procdb 가 가져오는 다른 모듈(approval_store 등)도 원래 복사하지 않아 지금 쓰지 않는 상태(호스트 워커 사용). 범위 밖.
- 로그인이 없어 누구나 되돌리기를 누를 수 있다(기존 포털 권한 수준과 같음, 학생별 자기 PC 전제 — DECISIONS 110 경위).

## 10. 사용자가 스스로 판정할 체크 질문

- 기본 에이전트를 고치려 할 때 거절 사유가 "왜 안 되고 무엇을 하면 되는지"(복제해서 고치기)를 말하는가?
- 원인 진단을 내 에이전트에 맡긴 뒤 경보 하나를 돌렸을 때, 처리 건 화면의 그 단계 담당 이름과 워커 작업 폴더 `task.json`의 agent 가 같은 에이전트인가?
- 내 에이전트 · 스킬을 아무리 만들어도 기본 에이전트 상세의 "실행 지시문에 더해지는 내용"이 그대로인가?
- "기준으로 되돌리기" 뒤 다음 경보가 처음과 똑같이 기본 에이전트로 돌아가는가?
