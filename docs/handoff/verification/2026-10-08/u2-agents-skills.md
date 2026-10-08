# U2 — 에이전트 · 스킬 보기(읽기 전용) + 워커 반영 (TODO A2의 에이전트·스킬 부분, 랩업 L16)

2026-10-08 밤. 범위: 메인 `TODO.md` 확정 TODO §0(포털은 보기만), §1 A2 중 에이전트·스킬, §2 L16("팬 진동 점검 스킬 → 에이전트 화면에 나타남").
MCP 도구 지도·도구 써 보기·호출 기록(A2의 나머지)은 U3 몫이라 여기서 다루지 않는다.

## 1. 한 줄 요약

- 포털 사이드바 **"AI 에이전트"**: 에이전트 카드 → 상세(요약 먼저: 역할·목표·성격·모델·쓰는 도구·스킬·맡은 단계, 펼치면 단계별 실제 실행 설정과 지시문에 더해지는 글). **스킬** 탭: 스킬 목록 → 본문(SKILL.md)·붙은 에이전트·선언한 단계. 쓰기 버튼·쓰기 API 없음.
- **워커가 배정된 에이전트의 설정을 실제 실행에 쓴다**: 지시문에 프로필(이름·역할·목표·성격), 작업 폴더에 스킬 파일(`.claude/skills/<이름>/SKILL.md`, Codex는 `.agents/skills/…`), 모델, 그 에이전트의 MCP 서버만 연결(+그 서버 도구 허용).
- 비유: 에이전트 프로필은 **직원 인사카드**, 스킬은 그 직원 책상에 꽂아 주는 **업무 매뉴얼 한 권**, 워커는 출근할 때마다 인사카드와 매뉴얼을 새로 받아 일하는 **사람**이다. 포털은 인사카드 열람실(고치는 창구가 아님), 고치는 곳은 랩업이다.

## 2. 저장 위치 — 하나로 정함

| 무엇 | 원천(하나) | 누가 읽나 |
|---|---|---|
| 에이전트 프로필 | `public.users` (is_agent=true): username · role · goal · persona · model · tools(콤마로 MCP 서버 이름) | 포털 `GET /api/agents*`, 워커 `context.prepare` |
| 스킬 본문 | `public.tenant_skills` (tenant_id, skill_name, description, content = **SKILL.md 원문**) — migration `20261008000026_agents_skills.sql` | 포털 `GET /api/skills*`, 워커 |
| 에이전트에 스킬 붙이기 | `public.agent_skills` (user_id, tenant_id, skill_name) — 없는 스킬은 외래 키로 거부 | 포털, 워커 |
| 단계가 선언한 도구·스킬·모델 | 흐름 정의 activity의 `tools`·`skills`·`agentConfig` (BPMN 고정 — 지금 정의에는 선언 0건) | 워커, 포털(단계별 실행 설정) |

**랩업에서 여기에 추가하면 포털에 나타난다.** 포털은 캐시 없이 요청마다 읽고("다시 읽기"), 워커도 실행마다 읽는다 — 다음 실행부터 반영된다. 시드에는 스킬을 넣지 않았다(정답은 수업에서 유도, 코드·시드에 정답 없음). 그래서 처음 화면의 스킬 탭은 "아직 스킬이 없습니다"이다.

### 랩업 L16 — 스킬 추가 예(형식만, 내용은 수업에서)

Supabase 로컬(`postgresql://postgres:postgres@127.0.0.1:54322/postgres`)에 `psql -f my_skill.sql` 또는 Claude Code에게 "이 SKILL.md를 tenant_skills에 넣고 에이전트에 붙여줘"로 실행한다.

```sql
-- 1) 스킬 저장: SKILL.md 원문을 그대로 content 에 ($md$ 따옴표로 감싸면 본문의 따옴표를 바꿀 필요가 없다)
insert into public.tenant_skills (tenant_id, skill_name, description, content) values
  ('hyd', 'fan-vibration-check', '팬 진동으로 원인을 좁히는 점검 순서', $md$---
name: fan-vibration-check
description: 팬 진동으로 원인을 좁히는 점검 순서
---
# 팬 진동 점검
1. (먼저 조회할 값과 도구)
2. (판정 기준)
3. (모를 때 적는 법)
$md$)
on conflict (tenant_id, skill_name) do update set description = excluded.description, content = excluded.content, updated_at = now();

-- 2) 에이전트에 붙이기. 처리 건의 에이전트 단계 4개(원인 진단·조치 후보·규정 검토·우선순위)는 기본 에이전트 sys:agent 가 맡는다
insert into public.agent_skills (user_id, tenant_id, skill_name) values ('sys:agent', 'hyd', 'fan-vibration-check')
on conflict do nothing;

-- 되돌리기(원래대로)
delete from public.agent_skills where user_id = 'sys:agent' and skill_name = 'fan-vibration-check';
```

### 새 에이전트 추가 예

```sql
insert into public.users (id, username, role, is_agent, agent_type, goal, persona, model, tools, tenant_id) values
  ('agent:fan-check', '팬 진동 점검 에이전트', '팬 진동으로 원인을 좁힌다', true, 'agent',
   '(목표 한 문장)', '(성격·말투)', null, 'neo4j,hyd-dmn', 'hyd')
on conflict (id) do update set username = excluded.username, role = excluded.role, goal = excluded.goal,
  persona = excluded.persona, model = excluded.model, tools = excluded.tools;
insert into public.agent_skills (user_id, tenant_id, skill_name) values ('agent:fan-check', 'hyd', 'fan-vibration-check') on conflict do nothing;
```

- `tools`는 `tenants.mcp`에 등록된 서버 이름(콤마). 등록 안 된 이름은 화면에 빨간 "등록 안 됨"으로, 실행 때는 알림 이벤트로 보인다.
- `model`이 비어 있으면 실행기 기본 모델. 단계의 `agentConfig.model`이 있으면 그것이 이긴다.
- **새 에이전트는 처리 건 단계를 스스로 맡지 않는다**(BPMN 고정: 단계 담당자는 정의의 역할 담당자 `sys:agent`). 화면에 "맡은 단계가 없습니다"로 보인다. 새 에이전트로 결과 차이를 보는 것은 A10 시험 실행이 아래 함수로 한다.

## 3. A10이 쓸 함수 — `procsvc.agents_store.agent_settings`

```python
agent_settings(repo, tenant_id, agent, *, activity=None) -> AgentSettings
# agent: users.id 문자열 | users 행 | None,  activity: agents_store.activity_capabilities(definition, activity_id) | None
# AgentSettings: agent_id · profile · model · model_source · tools(None=전부, []=없음) · tools_source · skills(행) · missing_skills
#   .instructions(skill_root=".claude/skills") → 지시문에 더할 글,  .summary() → 이름만 담은 JSON
# 없는 id · 사람 id → LookupError("그런 에이전트가 없습니다: …")
```

규칙(코드 `it/process/procsvc/agents_store.py`):
- 모델: 단계 `agentConfig`(agent_model·agentModel·model) > 에이전트 `users.model` > None(실행기 기본).
- 도구: 에이전트 서버와 단계 선언이 둘 다 있으면 교집합(겹치지 않으면 `[]` = 서버 없음, 워커가 알림), 하나만 있으면 그것, 둘 다 없으면 None(테넌트 서버 전부 — U2 전과 같음).
- 스킬: 단계 선언 ∪ `agent_skills` 행. 본문 없는 이름은 `missing_skills`(워커가 "넣지 못한 스킬" 알림 이벤트).
- 워커 `runner.run`, 포털 `GET /api/agents/{id}`의 `run.steps[].settings`, A10 시험 실행이 **같은 함수**를 부른다 → 화면에 보이는 설정 = 실제 실행 설정.

## 4. 원본 대조 (원본 파일:줄 · HYD 차이)

| 원본 | 무엇 | HYD | 차이 판정 |
|---|---|---|---|
| process-gpt-vue3@867e8cf `src/components/AgentChatInfo.vue:85,105,126,209,223` | 상세 순서 목표→성격→도구→스킬→모델, 긴 글 50자 펼치기 | `agents.js` 요약 카드(역할·목표·성격·모델·도구·스킬·맡은 단계), 80자 펼치기 | 편집(연필·삭제·도구 우선순위) 버튼 없음 — §0 보기 전용, 유지 |
| 같은 레포 `src/components/SkillDetail.vue:250-266` | 스킬의 "사용 중 에이전트" | 스킬 상세 "붙은 에이전트"(누르면 그 에이전트로) | 업로드·트리·Git 탭 없음 — 랩업 SQL로, 유지 |
| 같은 레포 `src/components/api/ProcessGPTBackend.ts:4250-4297`(putAgent → replaceAgentSkills), `:4315-4370`(agent_skills) | 프로필 = users 칸, 붙이기 = agent_skills | 같은 칸·같은 표 | 제품은 users.skills 콤마 사본도 둔다 → HYD는 agent_skills 하나만(원천 하나) |
| process-gpt-deepagents@faedeaa `core/skills/tools.py:644-716` | tenant_skills에 이름 등록, 본문은 skills 디렉터리·Git | tenant_skills.content에 SKILL.md 원문 | 포털(process 컨테이너)과 워커가 같은 행을 읽게 하려는 차이, 유지 |
| process-gpt-cli-agent@a4fd1a2 `core/subagents.py:38-55` | 에이전트의 role·goal·persona를 지시문으로, skills·tools(서버 이름 ∩ 테넌트 서버)로 실행 구성 | `AgentSettings.instructions()`·`tools` 규칙 | 제품은 하위 에이전트로 나누고 HYD는 한 에이전트 지시문 절로 — 같은 칸을 같은 목적에 씀 |
| 같은 레포 `executor.py:148-180`(skills.build_bundle → provision, 실패 목록) | 스킬을 작업 폴더에 쓰고 실패를 알림 | `workspace.provision(skills=…)`, `missing_skills` 알림 이벤트 | 같음 |

## 5. 이전 미커밋 변경에서 바꾼 것 (읽기 전용으로)

이전 작업(생성 모델)의 미커밋 변경을 읽고 범위에 맞게 정리했다.
- **제거**: `procsvc/agent_draft.py`(말로 초안 — LLM), `procsvc/agent_bindings.py` + `instances.py` 런타임 단계 배정 표(`activity_agent_bindings`) 적용, `agents_api.py`의 POST·PUT·DELETE(에이전트·스킬·배정·초안), `compose.yaml`의 process LLM 환경변수, `seed.sql`의 기본 스킬·성격 시드(정답 금지·기본 에이전트 회귀 영향), migration의 `users.skills/description/updated_at` 칸과 바인딩 표, `agents_store`의 쓰기 메서드(Pg).
- **유지·보완**: migration 000026(tenant_skills·agent_skills), 워커 Dockerfile의 `agents_store.py` 복사, `settings.py` 허용 도구 `Skill`, 워커의 프로필·스킬 반영(아래 §6로 재구성).

## 6. 바꾼 파일

| 파일 | 내용 |
|---|---|
| `it/supabase/migrations/20261008000026_agents_skills.sql` | tenant_skills · agent_skills(외래 키 · 이름 모양 검사 · RLS 읽기 전체) |
| `it/process/procsvc/agents_store.py` (새) | `agent_settings`·`AgentSettings`·`activity_capabilities`(워커에서 옮김)·`skill_markdown`·`skill_title`·읽기 저장소(Memory/Pg; Memory만 시험용 `put_skill`·`attach_skill`) |
| `it/process/procsvc/agents_api.py` (새) | `GET /api/agents` · `/api/agents/{id}` · `/api/skills` · `/api/skills/{name}` (읽기 전용) |
| `it/process/procsvc/main.py` · `procdb.py` | 라우트 연결 · Memory/PgRepo에 읽기 믹스인 |
| `it/agent-worker/worker/runner.py` | `agent_settings`로 모델·서버·스킬·지시문 결정, 스킬 없는 이름·등록 안 된 서버·겹치지 않는 도구를 알림 이벤트로, 선택된 서버의 도구 허용 |
| `it/agent-worker/worker/context.py` | `Context.profile`(배정 에이전트, 시스템 수행자 제외), `activity_capabilities`는 공용 함수로 위임 |
| `it/agent-worker/worker/prompt.py` | 지시사항 다음에 "에이전트 프로필 · 배정된 스킬" 절 |
| `it/agent-worker/worker/workspace.py` | `provision(skills=…)`: 이전 시도 스킬 폴더 지우고 이번 실행 스킬만 씀, 쓴 경로 반환 |
| `it/agent-worker/worker/bridge.py` | `select_servers`: None=전부, []=없음(구분) |
| `it/agent-worker/worker/settings.py` | 허용 도구 `Skill`, `run_allowed_tools`(기본 목록에 없는 등록 서버만 `mcp__<서버>__*` 추가 — neo4j는 읽기 도구만 유지) |
| `it/agent-worker/Dockerfile` | `agents_store.py` 복사(procdb가 가져옴) |
| `it/portal/www/agents.js` (새) · `index.html` | `window.hydAgents.mount(el)`, 사이드바 "AI 에이전트" + `#agentsView` 컨테이너, 화면이 열릴 때마다 다시 읽기 |
| `tests/test_u2_agents_skills.py` (새) | 아래 §7 |

## 7. 시험

`tests/test_u2_agents_skills.py` 10개 — 일부러 깨뜨린 경우 포함:
- 설정 읽기: 모델 우선순위, 도구 교집합·겹침 없음(`[]`)·선언 없음(None), 본문 없는 스킬 이름, 없는 id·사람 id → LookupError.
- 실제 워커 실행(MemoryRepo + 가짜 CLI): 요청 모델 = 프로필 모델, 지시문에 프로필·스킬 경로, 작업 폴더 `.claude/skills/fan-vibration-check/SKILL.md` = 저장 원문, `.mcp.json`에 에이전트 서버만, `--allowedTools`에 학생 서버 `mcp__fan-vib__*` 추가·neo4j 쓰기 도구 없음, task.json 에이전트 요약. Codex는 `.agents/skills/…`.
- 이전 시도 스킬이 작업 폴더에 남지 않음, 단계가 선언한 스킬이 저장 안 됐으면 알림 이벤트.
- 포털 API: 랩업이 넣은 에이전트·스킬이 다음 요청에 나타남, 새 에이전트는 맡은 단계 0, 등록 안 된 서버 표시, 쓰기 메서드 전부 404/405, legacy 모드는 409.
- 변형 확인: 워커에 스킬을 넘기지 않게 바꾸면 2개 시험이 실패함을 확인하고 되돌림.

결과: 전체 `pytest -q` **1294 passed**(U2 전 1284 + 새 10). `node --check it/portal/www/agents.js` 통과. 화면은 MemoryRepo API(:8080)와 정적 포털로 Playwright 렌더 확인(콘솔 오류 0, 캡처는 세션 스크래치패드 — 저장소에 넣지 않음).

## 8. 미검증 · 합친 뒤 확인할 것 (라이브 확인 경로)

docker·Supabase를 쓰지 않는 단위라 아래는 메인이 합친 뒤 한 번에:
1. `supabase db reset` 또는 migration 000026 적용 → `select * from tenant_skills` 0행 확인.
2. 포털 "AI 에이전트": 기본 에이전트 1 · 시스템 수행자 3, 기본 에이전트 맡은 단계 4(원인 진단·조치 후보 조회·규정 검토·우선순위·카드 작성), 스킬 탭 빈 상태.
3. §2 SQL로 스킬 하나를 `sys:agent`에 붙이고 "다시 읽기" → 스킬 탭·에이전트 상세에 나타남.
4. 쿨러 경보 1건(워커 1개, 20배속) → 워커 작업 폴더 `<WORKSPACE_ROOT>/hyd/<작업 id>/.claude/skills/<이름>/SKILL.md` 존재, 워커 로그 `skills in the workspace: …`, 처리 건 에이전트 활동에 스킬 파일을 읽는 도구 호출(Read/Skill)이 보이는지.
5. 되돌리기 SQL 뒤 다음 실행 작업 폴더에 스킬 폴더 없음.
6. 기본 에이전트의 지시문에 "에이전트 프로필" 절(이름·역할·목표)이 새로 들어간다 — worker 회귀에서 결과 형식이 그대로인지 확인.

## 9. 사용자가 스스로 판정할 체크 질문

- 랩업에서 SQL 한 번 넣고 "다시 읽기"만 눌렀을 때, 그 스킬과 붙은 에이전트가 화면에 그대로 보이는가? (안 보이면 원천이 둘이다)
- 에이전트 상세의 "단계별 실제 실행 설정"과 워커 작업 폴더의 `task.json` `agent` 칸이 같은 모델·도구·스킬을 말하는가?
- 붙인 스킬을 떼고 다음 경보를 돌렸을 때 작업 폴더에서 그 스킬이 사라지는가?
- 포털 어디에도 에이전트·스킬을 고치거나 지우는 버튼이 없는가?
