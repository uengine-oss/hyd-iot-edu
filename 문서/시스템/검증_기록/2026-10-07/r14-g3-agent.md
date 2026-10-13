# 3조 에이전트 실행 — 레포 6개 + 의존 SDK (HEAD: cli-agent 89cae91 10-06 · cliagents 7c7a392 08-25 · codex b505f0a 10-06 · deepagents 9676662 10-06 · mcp-validator cf220bf 08-10 · llm-factory a32e57e 2025-09-18 · 참고: agent-sdk e4728a2 0.10.1 10-06)

읽기 전용 조사. 경로 약어: `CA`=references-latest/process-gpt-cli-agent, `SDK`=references-latest/process-gpt-agent-sdk/processgpt_agent_sdk, `DA`=references-latest/process-gpt-deepagents, `W`=HYD it/agent-worker/worker. 줄 번호는 `cat -n` 기준.

## 결론 먼저

1. **설계 화면의 CLI 선택 키가 HYD와 다르다(실제 결함).** 제품 화면은 `agentConfig.agent_cli`를 쓴다(vue3 `AgentSelectField.vue:327,610`, CA `core/selection.py:30`, CA `tests/test_core_logic.py:378`). HYD는 `cli`/`agent`만 읽는다(W `runner.py:81`). 그래서 제품 화면에서 Codex로 지정한 정의가 HYD에서는 알림 없이 Claude Code로 실행된다. `cli` 키는 HYD가 따로 정한 것이고 HYD 스크립트·테스트끼리만 맞는다(`scripts/probe_*`, `tests/test_worker.py:305`).
2. **lease의 claim_count를 세는 방식이 SDK 0.10과 다르다.** SDK는 만료된 행을 다시 가져갈 때만 +1 하고, 새 작업이나 FB_REQUESTED 재실행이면 1로 되돌린다(SDK `function.sql:99-105`, 주석은 "피드백 몇 번 주고받은 작업이 멀쩡한데도 FAILED"를 막으려는 것). HYD는 워커가 가져갈 때마다 +1 한다(`it/supabase/migrations/20261007000018_worker_lease.sql:51`). 그래서 사람 질문·답이 두 번 오간 작업은 그 뒤 워커가 한 번만 죽어도 다시 가져가지지 않고 FAILED가 된다. 갱신 중 DB 예외가 나면 SDK는 다음 주기에 다시 시도하지만(SDK `lease.py:163-170`), HYD는 그대로 실행 실패로 끝난다(W `runner.py:181` → `handle` 68-69 `_fail`).
3. **Codex 경로에서는 테넌트 MCP 비밀이 정리되지 않는다.** A096 `bridge.cleanup`은 `.mcp.json`만 정리한다(W `bridge.py:28-44`). Codex 경로는 `codex-mcp.toml`에 서버 env를 평문으로 쓰고(118-120) argv `-c mcp_servers=`에도 그대로 싣는다(122-123). seed의 neo4j env에는 `NEO4J_PASSWORD`가 있어(`it/supabase/seed.sql:60`) 이 파일이 72 h 남는다.
4. **스냅샷 이후 cli-agent·codex의 코드 변경은 없다.** 바뀐 것은 의존성 pin 하나다(`pyproject.toml`·`requirements.txt`: agent-sdk 0.4.23→0.10.0, codex 0.7.2/0.8.1→0.10.0). 실제로 바뀐 동작은 SDK 쪽에 있고(lease·HUMAN_ASKED·FB_REQUESTED 재개), HYD는 SDK를 쓰지 않고 따로 구현했다. deepagents는 크게 바뀌었다. env 화이트리스트가 없어지고 TENANT_ID만 넘기며, 마운트를 테넌트별로 나누고, 워크아이템 HITL 규칙을 함수로 꺼냈다.

---

## process-gpt-cli-agent (89cae91 2026-10-06, 스냅샷 4475bf7 대비: 코드 동일 · pyproject/requirements의 agent-sdk 0.4.23→0.10.0만 변경)

### 이 레포가 하는 방식
- **claim·폴링·취소·lease**: 레포 자체에는 없다. `ProcessGPTAgentServer(...).run()`에 맡긴다(CA `server.py:86,103`). 0.10에서 SDK가 하는 일:
  - 폴링: 고정 consumer(`CONSUMER_ID` 또는 host:pid, SDK `database.py:124-130`)로 RPC `fetch_pending_task`에 `p_lease_seconds`·`p_max_claims`를 넘긴다(155-173). 일이 없으면 10 s를 쉰다(framework 327).
  - lease 유지: 별도 OS 스레드 `LeaseKeeper`가 120 s lease를 30 s마다 연장한다(SDK `lease.py:56-58,161-198`, framework 410-412). `not_owner`면 실행을 취소하고 FAILED로 표시하지 않는다(framework 404-408, 448-466). `not_started`면 연장만 멈춘다(lease 192-198). 일시적 예외는 다음 주기에 다시 시도한다(163-170).
  - 취소: `draft_status=CANCELLED`를 2 s마다 확인하고 `executor.cancel` 후 task를 취소한다(framework 343-371).
  - 끝날 때: `release_task_lease`(524-533).
- **컨텍스트**: 정의에서 activity를 읽는다(`core/activity.py:94-134`, 버전 고정 없이 proc_def id만 사용). 행·extras 값이 정의보다 우선한다(executor 124). 키는 `agent_cli/agentCli/cli_agent/cliAgent`, `agent_model/model`, `agent_permission/permission`이다(`selection.py:30-32,107-126`).
- **MCP 연결**: 테넌트 `mcpServers` 중 stdio만 고른다(`bridge.py:132-161`, url 서버는 149에서 버림). 이 서버들은 **네이티브 서브에이전트에만** 붙는다. `subagents.prepare`(23-70)가 activity `tools`로 서버를 고르고, `provision_definitions`가 `.agent-home/claude-code/agents/<name>.md`에 기록한다(83-119). 부모 프롬프트에는 "부모는 직접 MCP를 사용하지 않습니다"가 들어간다(122-126, executor 138-139). `bridge.install`(.mcp.json 경로, 67-94)은 **호출하는 곳이 없다**(codegraph callers 0건, executor grep으로도 확인).
- **비밀·설정 격리**: Claude Code는 항상 `CLAUDE_CONFIG_DIR=<ws>/.agent-home/claude-code`를 쓰고(bridge 123-129), Codex는 `CODEX_HOME`을 옮긴다(97-120). 실행이 끝나면 `RuntimeLease.restore()`가 서브에이전트 정의 파일(자격증명 포함 가능)을 원래대로 되돌린다(executor 99-103, `runtime.py:24-40`).
- **프롬프트**: 작업마다 CLAUDE.md 지시문을 만든다(executor 545-571, 활동명·테넌트·산출물 경로). 본문은 `prompt.build`가 만들고(`prompt.py:65-110`), 입력은 **8,000자에서 잘라낸다**(247-258). 주석 19-20에는 "workspace에 쓰고 참조한다"고 적혀 있어 코드와 주석이 다르다. 스킬은 작업공간에 배치한다(executor 155-174).
- **HITL**: 권한 거부(PERMISSION_REQUEST)만 멈춤 사유로 본다(executor 319-322, 237-250). `remember()`가 False면 알림 chunk를 내지 않는다(450-456). INPUT_REQUIRED 상태가 오면 SDK가 HUMAN_ASKED를 기록한다(SDK `event_queue_process.py:88-93,113-116`, `database.py:474-499`). 재개할 때는 `human_answer/feedback_answer/user_answer` 행 키를 읽는다(executor 594-600). 그런데 제품 화면은 답을 `feedback` 배열에 붙이고 FB_REQUESTED로 돌린다(vue3 `shared/hitlFeedback/index.js:127-144`). 즉 **cli-agent 안에서 화면 답변과 재개 경로가 맞지 않는다**(추측: 답은 SDK가 요약한 feedback으로만 프롬프트에 들어가 세션 재개가 아니라 새 실행이 됨, 실측 없음).
- **결과**: 폼 키가 있고 비어 있지 않은지만 본다(`outcome.py:51-80`). 맞지 않으면 바로 FAILED다(executor 267-278). 성공하면 payload에 `cliagents_session_id`를 넣고, 범위 밖 변경이 있으면 `replay_limited`를 붙인다(397-403).

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| CLI 선택 키 | `agent_cli` 등(selection 30) | `cli`/`agent`(runner 81) | 다름 | 제품 화면 정의를 HYD에 넣으면 기본 CLI로 바꿔 실행됨(무경고) | **예** — 두 키 다 읽기 |
| 행 수준 덮어쓰기 | row·extras > 정의(executor 124) | 정의만 | 다름 | HYD는 정의 버전 고정이 정본이라 의도된 차이 | 아니오 |
| claim | SDK RPC + 고정 consumer | `claim_process_workitems`(procdb 645-649) + claim마다 uuid consumer(runner 52) + 인스턴스 잠금 | 다름(HYD 확장) | 펜싱은 HYD가 더 엄격 | 아니오 |
| lease 연장 | 별도 스레드·예외 시 재시도·사유 구분 | 출력 펌프 루프의 check_stop 안(runner 177-181)·bool·예외 시 실패 | 다름 | DB가 잠깐 흔들려도 살아 있는 실행이 FAILED가 됨 | **예** — 예외는 넘기고 다음 주기에 재시도 |
| claim_count | 재회수만 +1 | 모든 claim +1 | 다름 | HITL 2회 뒤 워커가 한 번 죽으면 회수 없이 FAILED | **예** |
| MCP 붙이는 곳 | 서브에이전트만(subagents 83-126) | 부모 `.mcp.json`(bridge 124-141) | 다름 | HYD가 따르는 것은 제품에서 호출되지 않는 `bridge.install` | 사용자 결정(아래 출처 판정) |
| 설정 디렉터리 격리 | 항상 | API 키일 때만(settings 62) | 다름 | 구독 로그인을 유지하려는 결정(DECISIONS 12) | 아니오 |
| 실행 뒤 비밀 정리 | RuntimeLease restore | `.mcp.json` env 제거만(bridge 28-44) | 부분 | Codex용 `codex-mcp.toml`(평문)은 남음 | **예** |
| 입력 길이 | 8,000자에서 잘림 | 자르지 않고 16,000자를 넘으면 프롬프트 전체를 파일로(runner 278-289) | 다름 | HYD는 손실 없음 | 아니오 |
| 스킬 배치 | 작업공간에 배치 | activity `skills`는 읽기만 하고 쓰지 않음(context 89, runner에서 사용 0) | 다름 | HYD 스킬은 온톨로지 노드. 정의 화면의 스킬 지정은 무시됨 | 사용자 결정 |
| 업무 질문 HITL | 없음(권한 거부만) | `__human_input__` JSON(hitl 17-37, prompt 41-46) | 다름 | 아래 출처 판정 | 아니오 |
| 재개 | 행 키 human_answer | `feedback={human_answer, job_id}`(instances 625) + `draft._human_request`(runner 245) | 다름 | 제품은 화면과 맞지 않음. HYD는 job_id까지 맞춤. 다만 feedback을 **덮어써** 이전 검토 의견 이력이 사라짐 | 아니오(기록) |
| 결과 계약 | 키 존재만, 실패 즉시 | 버전 폼 `validate_output` + 같은 세션 교정 2회 | 다름 | HYD가 더 강함 | 아니오 |
| 중복 알림 억제 | remember 반환값 사용 | 반환값 버림(runner 254), 매번 새 ask_job·알림 | 다름 | 같은 질문이 반복되면 알림 중복(미실측) | 예(작음) |
| 취소 사유 문구 | — | lease를 잃어도 "담당자가 실행을 취소했습니다"(runner 64-67) | — | 운영자 오해 | 예(작음) |

### 이전 주장 판정 (REFERENCE_ADOPTION A05)
- "주장 참(CLI pump/on_start/timeout/HITL → runner/hitl)" → **맞음**. 코드가 같다(`core/runner.py:33-106`, `core/hitl.py`).
- "RuntimeLease 대응으로 A096 `bridge.cleanup`" → **불완전**. Claude 경로만 정리하고 Codex `codex-mcp.toml`·argv의 비밀은 남는다(W bridge 112-123).
- "보류: `_pause`가 remember() 반환값을 버림(runner 244)" → **맞음**. 지금은 254행이다.
- r13 group6 "서브에이전트 네이티브 정의 생성(subagents 83-119) → 해당 없음(HYD는 서브에이전트 요구 없음)" → **틀림(분류 오류)**. 이 경로는 서브에이전트 기능이 아니라 제품의 **유일한 MCP 연결 경로**다. HYD가 인용한 `core/bridge.py` 방식(.mcp.json)은 제품 실행 경로에서 호출되지 않는다.
- r13 group6은 `selection.py`를 읽은 범위에 넣지 않아 `agent_cli` 키 불일치를 놓쳤다(누락).

### 읽지 않은 것
`core/skills.py` 본문(271줄, 함수 목록만), `core/journal.py`·`stream_registry.py`(r13에서 읽음, 코드 동일), `api/*`, `system-skills/*`, `tests/` 중 378행 외, `e2e/`, `demo/`. SDK `processgpt_agent_framework.py` 1-300·560-881, `chat_*`·`steering.py`.

---

## cliagents (7c7a392 2026-08-25, 스냅샷 대비: 동일 — r13이 읽은 사본과 같은 커밋, HYD도 같은 커밋 pin `it/agent-worker/requirements.txt:2`)

### 이 레포가 하는 방식
`stream_exec`가 자식 프로세스를 띄운다. stderr는 별도 스레드가 받아 두었다가(`execution.py:238-249`) 끝난 뒤 `_LAST_RUN.stderr`(286-287)로만 내준다. env는 `dict(os.environ)`을 복사한 뒤 덮어쓴다(`provider.py:165-169`). 권한 매핑: Claude는 `plan/acceptEdits/bypassPermissions`(`claude_code.py:69-73`), Codex는 `--sandbox read-only/workspace-write/danger-full-access`(`codex.py:73-77`). 권한 거부는 Claude의 문자열 4종 부분일치로만 알아본다(`claude_code.py:29-34`). Codex resume은 `exec resume <id>` 뒤에 플래그를 붙인다(`codex.py:82-99`).

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 실행·파서 | stream_exec·parser | 그대로 사용(runner 21, events 31-59) | 같음 | — | 아니오 |
| 종료코드·stderr | `_LAST_RUN`에만 기록 | 0이 아니면 실패, 0이어도 stderr가 있으면 로그(process_control 108-113) | HYD 확장 | — | 아니오 |
| 프로세스 트리 종료 | terminate | Windows Job·killpg(process_control 15-82) | HYD 확장 | — | 아니오 |
| Codex resume 순서 | resume 뒤 플래그 | 플래그 뒤 resume(codex_provider 12-16) | 다름 | Codex 0.151 실측 대응 | 아니오 |
| env 상속 | os.environ 전체 | env_guard 블록리스트로 덜어냄(env_guard 10-33) | 다름 | 아래 deepagents 절 | 예(작음) |

### 이전 주장 판정 (A06)
- "주장 참·Codex 플래그 순서·exec_env os.environ 복사·권한 마커 4종" → **맞음**. 줄 번호도 다시 확인했다(위).
- "A096: exit 0인데 stderr가 있으면 워커 로그에 꼬리 기록" → **맞음**(process_control 110-113).

### 읽지 않은 것
registry.py·detection.py·artifacts.py 본문, terminal.py.

---

## process-gpt-codex (b505f0a 2026-10-06, 스냅샷 75784ee 대비: 코드 동일 · agent-sdk pin만 0.7.2/0.8.1→0.10.0)

### 이 레포가 하는 방식
문서 제작용 Codex **App Server** 런타임이다. `config.py:554-627`이 CODEX_HOME마다 `config.toml`을 쓴다. 내용: `approval_policy="never"`, `sandbox_mode="workspace-write"`, 읽기 제한 프로필(`":root"="deny"`, 542-551/561-562), 사용자 모델 서버 표(`name/base_url/env_key/wire_api="responses"/request_max_retries=0/stream_max_retries=0/requires_openai_auth=false`, 569-586), 자체 지식 MCP 하나(600-605)와 프로젝트 사전 신뢰(608-609). **테넌트 `mcpServers`는 쓰지 않는다**(app 전체 grep 결과 MCP는 `processgpt_knowledge`뿐).

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 실행 방식 | App Server JSON-RPC | `codex exec`(cliagents) | 다름 | 작업 단위 CLI는 cli-agent 계열이 맞는 기준 | 아니오 |
| 모델 서버 | config.toml 표 | 실행마다 `-c model_providers.hydgpu={name,base_url,env_key,wire_api}`(runner 112-117) | 거의 같음 | `requires_openai_auth=false`·재시도 0 없음(실측 PONG은 통과) | 아니오(기록) |
| 읽기 제한 | `:root` deny | 없음(Codex read-only도 디스크 전체를 읽을 수 있음, Claude는 Read/Glob/Grep 허용) | 다름 | 작업 디렉터리 밖 읽기 금지는 CONSTITUTION 문장으로만(workspace 25) | 사용자 결정 |
| 테넌트 MCP | 해당 기능 없음 | inline `-c mcp_servers=`(bridge 107-123) | — | HYD 자체(아래) | — |

### 이전 주장 판정 (A04)
- "채팅/프로세스 분기·이전 산출물 암묵 주입·폼 계약(게이트 뒤 별도 턴·1회 재요청)" → **맞음**(코드 동일, r13 group7 근거 그대로).
- 기록에 없는 점: HYD Codex 모델 서버 설정(A073)은 이 레포의 `config.py:569-586`을 가져온 것이다. 채택표에 출처로 남아 있지 않다(**불완전**).

### 읽지 않은 것
`app/runtime/service.py`·`workspace/bridge.py`·`session_archive.py` 본문, knowledge/*, documents/*, tests.

---

## process-gpt-deepagents (9676662 2026-10-06, 스냅샷 1bf79e0 대비: **변경 큼**)

### 바뀐 것 (이 조 영역만)
- **샌드박스 env**: 옛 화이트리스트(LLM 키만 전달)를 없앴다. 지금은 `_build_container_env`가 `{"TENANT_ID"}`만 넘긴다(`core/sandbox/docker_sandbox.py:216-218`). 사유는 210-215 주석에 있다: "모델 API 키도 넘기지 않는다. 사용자가 채팅으로 env를 시키면 그대로 출력돼 실제로 노출됐다".
- **마운트**: 볼륨 전체 대신 `{root}/{tenant}`만 `/workspace`로 마운트한다(docker_sandbox 7-9, 264; `tenant_workspace.py:26-36`, 테넌트 id는 치환하지 않고 거부).
- **워크아이템 HITL**: 질문 도구는 채팅이거나 COMPLETE 모드일 때만 준다. DRAFT에는 주지 않는다(`core/chat/hitl.py:173-187`, `agent.py:246`). 답은 feedback 마지막 항목으로 오며 대기 중인 interrupt의 답으로 쓴다(hitl 189-211). 워크아이템에서는 human_answered 이벤트를 내지 않는다(enum 문제, 213-220). 재시도 미들웨어는 HITL interrupt를 삼키지 않는다(`core/agents/tool_retry.py:20-48`).
- **도구 선택**: activity `tools`의 MCP 서버만 루트에 붙이고(agent.py 298-313), 프로필 `tool_filters`로 서버별 도구 허용 목록을 둔다(320-339, `core/llm/mcp.py:46-88`). 워크아이템에서는 `execute_process`를 빼고(248-250) 스킬 평가 도구도 주지 않는다(270-271).
- **보상**: 관측된 작업 이력에서 LLM 없이 되돌리기 단계를 만들고, 되돌릴 수 없으면 그렇다고 말한다(`core/deterministic/compensation.py` 머리말, `sql_undo.py`·`work_history.py` 신규).

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 자식 env | TENANT_ID만 | 블록리스트(`*_DSN/_PASSWORD/_SECRET/_SERVICE_KEY` + 이름 8개, env_guard 10-12) | 다름 | `*_TOKEN`·`*_API_KEY`(예: GH_TOKEN, OPENAI_API_KEY, LLM_API_KEY)는 남음. 호스트 실행은 사용자 셸 env 전체를 상속(run_worker_host.sh) | **예(작음)** — 접미사 추가 또는 허용 목록 방식 |
| 테넌트 격리 마운트 | 테넌트 디렉터리만 | 작업공간 폴더만, OS 경계 아님(workspace 3-5) | 다름 | HYD는 단일 테넌트·호스트 실행 | 아니오 |
| 질문 도구 노출 | COMPLETE/채팅만 | 프롬프트에 항상(prompt 41-46) | 다름 | DRAFT 작업에서도 질문할 수 있음 | 사용자 결정 |
| activity 도구 선택 | activity tools + tool_filters | activity tools(select_servers, bridge 47-59) + 전역 `--allowedTools`(settings 57-59) | 거의 같음 | 서버별 허용 목록은 settings 상수와 Codex neo4j 하드코딩(bridge 116-117) | 아니오 |

### 이전 주장 판정 (A01)
- "샌드박스 env 화이트리스트(docker_sandbox.py L52-66)를 env_guard로 반영(A095)" → **불완전(낡음)**. 스냅샷 시점에는 맞았지만 최신 HEAD에는 화이트리스트가 없고 TENANT_ID만 넘긴다. HYD env_guard는 화이트리스트도 아닌 **블록리스트**라 처음부터 같은 강도가 아니었다.
- "HITL 체크포인터는 HYD가 DB 저장으로 대체" → **맞음**.
- "프레임워크 교체 근거 없음" → **맞음**.

### 읽지 않은 것
`executor.py` 2,549줄 중 함수 목록과 `workitem_resume_answer` 호출 위치만 봄. `core/skills/*`, `steering.py`, `chat/*` 신규 파일, `compensation.py` 본문(머리말만).

---

## process-gpt-mcp-validator (cf220bf 2026-08-10, 스냅샷 95647ed 대비: 변경 — 전송별 허용 키만 넘기는 `_build_connection_config`(validator.py 21-44), 실행 파일이 없을 때 안내 문구(172-180), Dockerfile에 Node.js)

### 이 레포가 하는 방식
`POST /validate`(api.py 85)에서 서버마다 따로 `initialize`→`load_mcp_tools`를 timeout(기본 10 s) 안에 돌려 success/timeout/error를 내고, 전체는 success/partial/failed로 묶는다(validator 51-92, 101-163). **호출하는 곳은 화면이다.** 계정 설정의 MCP 서버 화면과 에이전트 필드에서 부른다(vue3 `account-settings/MCPServer.vue`, `ui/field/AgentField.vue`, `services/McpValidatorService.js:12,24`). 즉 **설정 저장 시점에 하는 검사**이고, 워커가 실행 전에 하는 검사가 아니다.

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 검증 시점 | 설정할 때(UI) | 설정 UI 없음, seed + probe 스크립트 | 다름 | 테넌트 MCP를 바꾸는 화면이 없어 해당 경로가 없음 | 아니오 |
| 실행 시 서버 다운 | — | Codex: `required=True, startup_timeout_sec=60`으로 기동 실패(bridge 115). Claude: 도구 없이 진행 | — | Claude 경로는 도구 실패가 권한/오류 공지로만 보임 | 사용자 결정 |

### 이전 주장 판정 (T04)
- "validator.py 서버별 initialize+list_tools+timeout→success/partial/failed" → **맞음**.
- "격차: 워커는 bridge.install 뒤 점검 없이 CLI 기동 → 실행 전 MCP 초기화 점검 후보" → **불완전**. 제품도 실행 전에 점검하지 않는다(검증기는 설정 화면에서 쓴다). 따라서 "레포를 따르는 채택"이 아니라 HYD가 새로 고안하는 기능이다. 또 Codex 경로에는 이미 `required` 서버 기동 실패가 있다.

### 읽지 않은 것
models.py, api.py 120-264(단일 서버·예시 엔드포인트), README.

---

## process-gpt-llm-factory (a32e57e 2025-09-18, 스냅샷 대비: 동일)

### 이 레포가 하는 방식
`LLM_PROVIDER`(기본 openai)마다 LangChain 객체를 만든다(`factory.py:45-58`). 키가 없으면 바로 ValueError(86-87, 104-105, 121-123). 기본 모델명이 옛것이다(64-67). 실제 소비처는 agent-utils `deterministic_code_tool.py:104,247,643`뿐이다.

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 서술 LLM | LangChain 팩토리 | urllib/anthropic 직접 호출, 키가 없으면 템플릿(agentsvc/llm.py 10-13, 34-36, 46-79) | 다름 | 서술은 선택 기능이라 폴백이 설계 의도(docstring 1) | 아니오 |
| 기동 로그 | — | `announce()`(llm 39-43, main.py:200) | HYD 추가 | — | 아니오 |
| CLI 모델 | 해당 없음 | 정의 `agentConfig.model` > `CLI_MODEL`(settings 37, run_worker_host.sh `opus`) | — | 제품 cli-agent는 모델 미지정이면 CLI 기본값(selection 117) | 아니오 |

### 이전 주장 판정 (X08)
- "provider별 model_factory ↔ agentsvc/llm.py" → **맞음**.
- "import 시 provider·model·available 로그" → **틀림(표현)**. import 시점이 아니라 앱 기동 훅에서 찍는다(llm 39-42, agentsvc/main.py:200).
- HYD `llm.py:40`의 출처 표기 "process-gpt-utils model_factory"는 **없는 모듈**이다(agent-utils grep 0건). 실제 출처는 process-gpt-llm-factory다.

### 읽지 않은 것
setup.py·README.

---

## 출처 판정

| HYD 기능(파일:줄) | 출처 | 맞는 레포의 방식(파일:줄) |
|---|---|---|
| 폴링 루프·HTTP /health(W main.py:83-101) | 맞는 레포 따름 | SDK framework 301-332, CA server.py 44-53 |
| claim RPC(procdb 645-649, migration …018:14-55) | 맞는 레포 따름 + HYD 확장(인스턴스 잠금·claim별 consumer) | SDK function.sql 34-112 |
| **lease claim_count**(migration …018:51) | **HYD 자체 고안(SDK와 어긋남)** | SDK function.sql 99-105 |
| **lease 연장 위치·예외 처리**(runner 177-181) | **HYD 자체 고안** | SDK lease.py 94-198, framework 400-466 |
| 취소 감지(runner 228-232) | 맞는 레포 따름(더 엄격) | SDK framework 343-371 |
| **CLI·모델·권한 선택 키**(runner 79-83, context 82-91) | **HYD 자체 고안(키 이름)** | CA selection.py 30-32·86-126, activity.py 59-91, vue3 AgentSelectField.vue:327 |
| 컨텍스트 수집(context 44-79) | 맞는 레포 따름(SDK prepare_context) + 버전 고정 확장 | SDK framework 93-226, CA activity.py 94-134 |
| 프롬프트 본문·출력 계약(prompt 13-93) | 맞는 레포 따름(거의 같은 문장) | CA prompt.py 65-159 |
| 긴 프롬프트 파일로(runner 278-289) | HYD 자체 고안(A077) | CA prompt.py 247-258(잘라냄), DA executor `_offload_input_data` 906 |
| 지시문 CLAUDE.md(workspace 20-44, 97-103) | 맞는 레포 따름(정적 문장으로) | CA executor 545-571 + skills.build_bundle |
| **MCP 연결 .mcp.json(부모)**(bridge 103-141) | **맞는 레포의 옛 방식(현재 호출되지 않는 경로)** | CA subagents.py 23-126 + executor 138-147 |
| activity 서버 선택(bridge 47-59) | 다른 레포 빌림(base-agent) — 결과는 deepagents와 같음 | CA subagents 55-67, DA agent.py 298-313 |
| Codex MCP inline(bridge 107-123) | HYD 자체 고안 | CA bridge 97-120(CODEX_HOME 격리) + subagents 108-111(.codex/agents) |
| Codex 모델 서버(runner 112-117) | 다른 레포 빌림(process-gpt-codex) — 적절 | codex config.py 569-586 |
| 설정 디렉터리 격리 조건(bridge 152-159, settings 62) | 맞는 레포 따름 + 사용자 결정 | CA bridge 123-129 |
| 실행 뒤 비밀 정리(bridge 28-44, runner 72-75) | 맞는 레포 따름(부분) | CA runtime.py 10-40 |
| 자식 env 비밀 제거(env_guard) | 다른 레포 빌림(deepagents) — 반대 방향(블록리스트) | DA docker_sandbox 210-218 |
| 출력 펌프·종료코드(process_control) | 맞는 레포 따름 + 확장 | CA core/runner.py 33-106 |
| 권한 거부 멈춤(runner 200-201, 139-143) | 맞는 레포 따름 | CA executor 237-264 |
| **업무 질문 `__human_input__`**(hitl 17-37, prompt 41-46) | **HYD 자체 고안** | CA 없음 / DA hitl.py 126-187(도구 + COMPLETE 한정) |
| 재개 DB 정본(hitl 40-49, instances 603-628) | HYD 자체 고안 | CA hitl.py 112-147(작업공간 파일), vue3 hitlFeedback 127-144(feedback 배열) |
| 보류 `__deferred__`(task_deferral, runner 128-133) | HYD 자체 고안 | 없음(CA는 "모르면 모른다고", executor 557) |
| 결과 해석·검증(outcome 36-56) | 맞는 레포 따름 + 강화 | CA outcome.py 51-80 |
| 형식 교정 2회(runner 145-153) | 다른 레포 빌림(bpmn-extractor, prompt 61-62 주석) | CA 즉시 실패(executor 267-278), 같은 계열 codex `MAX_FORM_REPAIR_ATTEMPTS=1` |
| 작업공간·보존·sweep(workspace 82-148) | 맞는 레포 따름 + 다른 레포 빌림(session-router keep) | CA workspace.py |

### 빌림·자체 고안 비교

1. **lease claim_count / 연장 처리 (HYD 자체 ↔ SDK)**
   - 정확성: SDK가 낫다. HYD는 FB_REQUESTED도 세어 HITL 2회 뒤 회수 기회가 없다. 연장 예외 한 번이 실행 실패가 된다.
   - 재현성: 같다.
   - 속도·비용: 같다.
   - 실패 복구: SDK가 낫다. 일시적 DB 오류를 견디고, `not_owner`와 `not_started`를 나눈다.
   - 수업 설명: SDK 쪽이 주석까지 있어 설명하기 쉽다.
   - **판정: 레포 쪽이 낫다.**
   - 바꾸는 범위: 새 마이그레이션 1개(claim_count를 `case when w.draft_status='STARTED' then +1 else 1`로, 선택 사항으로 renew가 사유를 돌려주게). `runner.check_stop`에서 renew 예외를 잡아 로그 후 계속(연속 실패 상한은 3회). 반나절 안팎 + 회귀 테스트.
2. **CLI 선택 키 `cli` (HYD 자체 ↔ cli-agent·vue3 `agent_cli`)**
   - 정확성: 레포가 낫다. 제품 화면에서 만든 정의와 호환된다.
   - 재현성: 레포가 낫다.
   - 속도·비용: 같다.
   - 실패 복구: HYD는 다른 CLI로 바꿔도 아무 알림이 없다.
   - 수업 설명: 제품 화면과 같은 키가 쉽다.
   - **판정: 레포 쪽이 낫다.**
   - 범위: `runner.py:81` 한 줄(`agent_cli` 먼저, `cli` 뒤에 유지). 선택 사항으로 `model`·`permission` 별칭도 추가. 테스트 1건. 1시간 안쪽.
3. **MCP를 부모 `.mcp.json`에 연결 (옛 방식 ↔ 서브에이전트에만 연결)**
   - 정확성: HYD 경로는 10-06 실측으로 동작이 확인됐다. 제품 방식은 Claude의 신뢰 규칙 우회를 목적으로 한다(subagents 92-96).
   - 재현성: 비슷하다.
   - 속도·비용: HYD가 낫다. 서브에이전트 위임 턴이 없다.
   - 실패 복구: HYD가 낫다. 도구 호출이 부모 스트림에 바로 보여 events·교정 루프가 그대로 동작한다. 서브에이전트 안의 도구 호출을 cliagents 파서가 낱개로 보여 주는지는 미확인이다.
   - 수업 설명: HYD가 쉽다(".mcp.json 한 파일").
   - **판정: HYD 쪽이 낫다(차이 무해).** 단 채택표와 bridge 머리말에 "제품은 서브에이전트에만 붙이고 이 경로는 제품에서 쓰이지 않는다"는 사실을 고쳐 적어야 한다.
4. **Codex MCP inline + `codex-mcp.toml` (HYD 자체 ↔ CODEX_HOME 격리 + .codex/agents)**
   - 정확성: 비슷하다.
   - 비밀: 레포가 낫다. RuntimeLease가 파일을 되돌린다. HYD는 평문 toml이 남고 argv에도 실린다.
   - 실패 복구: HYD가 낫다. `required=True`로 기동이 실패한다.
   - 수업 설명: 비슷하다.
   - **판정: 비밀 처리만 레포 쪽이 낫다.**
   - 범위: `bridge.cleanup`이 `codex-mcp.toml`도 지우게 하거나(또는 이 파일을 쓰지 않게) 한다. 파일 1개, 1시간 안쪽. argv 노출은 Codex `-c` 방식의 한계이니 기록만 한다.
5. **env_guard 블록리스트 (빌림·반대 방향 ↔ deepagents TENANT_ID만)**
   - 정확성: 레포가 낫다. 그러나 CLI 자식 프로세스는 PATH·HOME·APPDATA·자기 로그인 키가 있어야 해서 그대로 따라 하기는 어렵다.
   - **판정: 레포 쪽이 낫다(부분).**
   - 범위: `BLOCK_SUFFIXES`에 `_TOKEN`·`_API_KEY`를 추가한다(keep으로 CLI 키 보존). 또는 허용 목록 방식으로 바꾸고 Windows 필수 키를 실측한다. 파일 1개, 1~2시간 + 기동 실측.
6. **업무 질문 `__human_input__` (HYD 자체 ↔ cli-agent 없음 / deepagents 도구)**
   - 정확성: HYD가 낫다. 제품 cli-agent에는 업무 질문 경로가 없고, 화면 답변과 재개도 맞지 않는다.
   - 실패 복구: HYD가 낫다(job_id 대조, DB 정본).
   - 수업 설명: 비슷하다.
   - **판정: HYD 쪽이 낫다.** 다만 deepagents처럼 DRAFT 모드에서 빼는 것은 사용자 결정이다.
7. **보류 `__deferred__` (HYD 자체)**
   - 정확성: HYD가 낫다. 꾸민 폼보다 낫다.
   - 수업 설명: 상태가 하나 늘어 설명 부담이 있다.
   - **판정: HYD 쪽이 낫다.** 제품 화면에는 이 상태가 없다는 점은 기록으로 남긴다.
8. **형식 교정 2회 (bpmn-extractor 빌림 ↔ cli-agent 즉시 실패 / codex 1회)**
   - **판정: 비슷하다(차이 무해).** 출처를 같은 계열인 process-gpt-codex로 적는 편이 정확하다. 비용은 최대 1턴 차이다.
9. **긴 프롬프트 파일 전달 (HYD 자체 ↔ cli-agent 8,000자 잘림)**
   - **판정: HYD 쪽이 낫다.** 제품은 주석과 코드가 다르고 입력을 잃는다.

## 조 요약
| 레포 | 핵심 차이 | 맞춰야 할 것 | 이전 기록 오류 |
|---|---|---|---|
| cli-agent | MCP를 서브에이전트에만 연결, `agent_cli` 키, 코드 변경 없음(SDK pin만) | `agent_cli` 읽기, codex-mcp.toml 비밀 정리, 알림 중복 억제, lease 상실 문구 | r13: 서브에이전트 경로를 "해당 없음"으로 분류(실제로는 MCP 연결 경로), selection.py 미열람으로 키 불일치 누락. A096 "env 제거"는 Codex에서 불완전 |
| (agent-sdk 0.10, 의존) | lease 스레드·사유 구분·재회수만 카운트·HUMAN_ASKED·FB_REQUESTED | claim_count 규칙, renew 예외 재시도 | A097 "SDK lease 반영"은 카운트·예외 처리에서 불완전 |
| cliagents | 변경 없음 | 없음 | 없음 |
| codex | 변경 없음, 테넌트 MCP 미사용, 읽기 제한 | (선택) 읽기 제한은 사용자 결정 | 모델 서버 설정 출처(config.py 569-586) 미기재 |
| deepagents | env를 TENANT_ID만, 테넌트 마운트, 워크아이템 HITL 규칙 | env_guard 접미사 보강 | A01 "화이트리스트 L52-66"은 최신 HEAD에서 낡음, HYD는 블록리스트라 같은 강도가 아님 |
| mcp-validator | 키 필터·안내 문구 추가, 설정 화면에서 호출 | 없음 | T04 "실행 전 점검"은 레포 방식이 아님(설정 시점 검사) |
| llm-factory | 변경 없음 | 없음 | X08 "import 시 로그"는 기동 훅. llm.py:40 출처 모듈명 오기 |
