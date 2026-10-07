# REPO_GAP — 제품(uengine-oss ProcessGPT) 로직 vs 내 구현 대조표

작성 2026-10-03 밤 (DECISIONS 11, 발화 19~21). 레포 클론 위치: 세션 스크래치 `refs/`(사라지면 `git clone --depth 1 https://github.com/uengine-oss/<repo>.git`).
읽은 범위는 발췌가 아니라 아래 파일 전문 또는 적힌 줄 범위다. 처리 열의 뜻: **이식** = 제품 로직을 가져와 바꾼다 · **직접** = 제품에 없어 내가 쓴다(근거 명시) · **축소** = 제품에 있으나 교육용으로 줄인다(회의 근거 있을 때만) · **후반 설명** = 구현하지 않고 "이것이 ProcessGPT"로 소개.

## 0. 통독한 제품 파일

| 레포 | 파일 (줄) | 무엇을 정의하나 |
|---|---|---|
| process-gpt (본체) | `docker-infra/volumes/db/init.sql` L68~112(enum), L273~321(proc_def·arcv·version), L361~430(bpm_proc_inst·todolist), L651~662(events), L2902(record_events_bulk) | 제품 DB의 실제 열·enum |
| process-gpt-agent-sdk | `database_schema.sql` 전문, `processgpt_agent_sdk/function.sql` 전문(fetch_pending_task·save_task_result·record_events_bulk·fetch_context_bundle), `database.py` 전문, `processgpt_agent_framework.py` 전문 | 에이전트 워커가 todolist를 집고 결과를 내는 계약 |
| process-gpt-completion | `polling_service/process_definition.py` 전문, `polling_service.py` 전문, `workitem_processor.py` L603~760·L893~1022·L1706~1995·L2143~2319·L2377~2610·L3787~4538·L4675~5365, `database.py` L909~1047·L1097~1978·L2119~2378, `tests/test_resolve_next_activities.py` 전문, `deterministic_generator.py`·`deterministic_signature.py` 머리 | 엔진: SUBMITTED를 집어 다음 작업을 만드는 실제 로직 |
| process-gpt-cli-agent | `README.md`, `server.py`, `executor.py`, `core/{runner,activity,events,outcome,bridge,hitl,prompt,workspace,settings}.py` 전문 | agent_orch=cliagents 워커의 실제 모양 |
| cliagents | `src/cliagents/{execution,providers/claude_code}.py` 전문 | Claude Code headless 호출·이벤트 파서 |
| process-gpt-agent-utils | `tools/{dmn_rule_tool,human_query_tool}.py` 전문, `safe_tool_loader.py` 머리 | 제품의 DMN 도구·사람 질문 도구 |
| process-gpt-sample-app-wms | `docs/03-processgpt-integration.md` 전문, `mcp/wms_mcp/mcp_server.py` 머리+도구 목록 | 업무 앱을 테넌트 MCP로 등록하는 방식 |
| process-gpt-vue3 | `src/shared/instanceSteps.js` 전문, `ontology/SCHEMA.md` §1~§6 | 인스턴스 화면의 단계 계산, 온톨로지 Execution 레이어 계약 |
| ontology-studio | `README.md`, `docs/ontology-mcp-server.md` | 읽기 전용 온톨로지 MCP(인용 출처) |
| process-gpt-strategy | `app/ontology_sync.py` 머리 | 증분 인제스천 구조 |

## 1. 회의 항목별 대조

### 11 · 프로세스 인스턴스 중심 — 에이전트는 태스크 (사용자 최초 질의, 원문2 L193·L434~436)

| 주제 | 제품 로직 | 내 구현 | 차이 | 처리 |
|---|---|---|---|---|
| todolist 상태 의미 | `TODO`=예정, `IN_PROGRESS`=처리 중(사람·에이전트), `SUBMITTED`=결과 제출됨 → 엔진 차례, `DONE`=엔진이 다음 작업까지 만든 뒤, `CANCELLED`=안 간 가지·바운더리 대안, `PENDING`=서브프로세스 대기. 엔진 폴링은 SUBMITTED를 consumer로 점유(`database.py:909`), 처리 뒤 consumer 해제(`polling_service.py:101`) | SUBMITTED=에이전트 대기, 워커가 claim하며 IN_PROGRESS, 워커가 DONE | **의미가 반대** | **이식**: 제품 의미로 전부 교체 (engine·procdb·instances·worker·portal·scenario test) |
| 인스턴스 시작 | `upsert_todo_workitems`(`database.py:1787`): 도달 가능한 모든 활동을 TODO로 **사전 생성**(assignees·agent_mode·agent_orch·query·tool 기본 `formHandler:defaultForm`), 다음 활동은 `upsert_next_workitems`로 IN_PROGRESS | 흐름이 닿을 때 행을 새로 insert | 예정업무가 없어 화면에서 "앞으로 할 일"이 안 보임 | **이식**: 시작 시 전부 TODO 사전 생성, 닿으면 TODO→IN_PROGRESS로 update |
| 완료 판정 | `run_completed_determination`(`workitem_processor.py:3787`): 체크포인트·시퀀스·게이트웨이 조건으로 DONE/PENDING, `cannotProceedErrors`를 log에 | 조건 미충족이면 예외 | 제품은 PENDING + 사유 기록 | **이식**: 조건 미충족 → 작업 PENDING + log 사유 |
| 다음 활동 결정 | `resolve_next_activity_payloads`(`:4138`): XOR는 참 1개(여럿이면 priority·id 순, 없으면 default flow, 없으면 진행 안 함), inclusive/parallel은 허용 전부; `inject_boundary_events_as_next`(`:4431`)로 바운더리 이벤트를 **다음 작업 행**으로 추가(user=system) | XOR 2개 참이면 예외, default 없으면 예외; 바운더리는 due_date 열로만 | 제품은 결정론 우선순위, 이벤트도 행 | **이식**: XOR 규칙(priority·default), 바운더리 이벤트 행(activity_id=`ev:select-timeout`, user_id `sys:process`, due_date) |
| 조건 평가 | `_evaluate_sequence_conditions`(`:2377`): `conditionFunction`은 제한 eval(폼 데이터 컨텍스트), 자연어 `condition`은 LLM; 판정을 `gateway_decisions`로 워크아이템에 기록(`:2597`) | AST 화이트리스트 평가(제품의 conditionFunction과 같은 뜻), 기록 없음 | LLM 자연어 조건 없음, 판정 기록 없음 | **이식**: `gateway_decisions` 열·기록. 자연어 조건은 **축소**(회의 L313~348 결정론 원칙·DECISIONS 3: 규칙은 결정론) — 정의에 `condition`(식)만 쓴다 |
| 완료 뒤 처리 | `execute_next_activity`(`:1943`) → `_persist_process_data`(`:1904`): completed DONE+end_date, cancelled(붙은 바운더리 이벤트·이벤트의 붙은 활동 CANCELLED), next TODO→IN_PROGRESS(+query `[InputData]`), 인스턴스 upsert(current_activity_ids·participants), 타이머 등록, `_check_service_tasks`(`:1928`) serviceTask는 즉시 SUBMITTED | 서비스태스크는 dispatch에서 직접 실행 | 서비스태스크 상태 흐름이 제품과 다름 | **이식**: serviceTask 도달 → SUBMITTED → 엔진 폴링이 실행(`handle_service_workitem` 자리) → DONE, output=tool_results, log |
| 재시도 | `safe_handle_workitem`(`polling_service.py:22`): 예외 시 retry+1·consumer 해제, 3회면 DONE+log, 첫/마지막 활동이면 인스턴스 RUNNING/COMPLETED 보정(`update_instance_status_on_error`) | 워커가 3회 뒤 빈 출력으로 complete | 비슷하나 엔진 쪽 재시도가 없음 | **이식**: 엔진 폴링 재시도 3회 규칙 |
| stale consumer | 30분 지나면 consumer NULL(`database.py:1016`), 5분마다 | 15분, SUBMITTED로 되돌림 | 값·방식 | **이식**: 30분·consumer만 해제 |
| 인스턴스 열 | `bpm_proc_inst`: role_bindings jsonb, participants text[], variables_data(list `{key,name,value}`), proc_def_version, version_tag/version, project_id, is_deleted…(`init.sql:361`) | participants jsonb, variables_data dict, end_event(내 확장), role_bindings 없음 | 열·모양 | **이식**: 제품 열 전부 + variables_data는 제품 list 모양(엔진은 dict 뷰로 평가). `end_event`는 HYD 확장으로 유지(SCHEMA.md에 없음을 명시) |
| todolist 열 | `init.sql:389`: username, version_tag, version, query, draft_status, temp_feedback, project_id, feedback_status, agent_mode(DRAFT/COMPLETE, NULL=사람) | 없음; agent_mode에 'NONE' 값 | 열 누락, enum 값 틀림 | **이식**: 제품 열·enum 그대로 |
| 인스턴스 이름 | LLM `generate_semantic_name` | `{정의명} {asset}` | LLM | **축소**(교육용, 비용): 규칙 이름 |

### 7 · 실제 도구를 쓰는 에이전트 = Claude Code (L134~156) · 8 · 서버가 CLI 서브프로세스 호출 (L175~214)

| 주제 | 제품 로직 | 내 구현 | 차이 | 처리 |
|---|---|---|---|---|
| 워커 폴링·점유 | `fetch_pending_task(p_agent_orch,p_consumer,p_limit,p_env)`(`function.sql:8`): status IN_PROGRESS ∧ agent_mode∈(DRAFT,COMPLETE) ∧ draft IS NULL ∧ draft_status IS NULL (또는 FB_REQUESTED) → draft_status STARTED, consumer | `claim_workitems`: SUBMITTED→IN_PROGRESS | 반대 | **이식**: RPC 이름·조건·부수효과 그대로 |
| 결과 저장 | `save_task_result(todo_id,payload,final)`(`function.sql:51`): COMPLETE면 output=payload·status SUBMITTED·draft_status COMPLETED·consumer NULL; DRAFT면 draft=payload(사람 검토 뒤 제출) | process API `/complete`로 DONE | 엔진 역할을 워커가 함 | **이식**: 워커는 DB RPC로만 결과를 내고, 엔진 폴링이 SUBMITTED를 처리 |
| 실패 | `update_task_error`: draft_status FAILED·consumer NULL + error 이벤트(`framework.py:440`) | retry·SUBMITTED 되돌림 | | **이식** |
| 취소 | 화면이 draft_status=CANCELLED → 워커 워처가 2초마다 감지해 실행 취소(`framework.py:341`) | 없음 | | **이식**(worker) |
| 컨텍스트 준비 | `prepare_context`(`framework.py:91`): form_def(tool `formHandler:<id>`→fields_json·html, 없으면 freeform), users/agents(users.is_agent), tenants.mcp(기본 MCP 병합), notify emails, proc_inst_source, 피드백 요약(LLM) | task.json(정의 inputData·previous_outputs) | 폼 계약·테넌트 MCP·에이전트 행이 없음 | **이식**: users·form_def·tenants.mcp 테이블과 같은 조회. 피드백 요약 LLM은 **축소**(피드백 원문 그대로) |
| 실행 단위 | `executor.py`: 실행마다 워크스페이스(`/workspace/<tenant>/<task_id>`), RuntimeLease, 활동의 `agentConfig/skills/tools`(`activity.py`), selection(cli·model·permission; 기본 claude-code·WORKSPACE_WRITE=acceptEdits), journal(변경 기록), bridge(테넌트 MCP → `.mcp.json`+슬래시 명령, Claude Code는 `CLAUDE_CONFIG_DIR` 격리), skills bundle(CLAUDE.md+`.claude/skills`), run timeout 1800s, 동시 3 | 인스턴스당 워크스페이스, 고정 MCP 3개, READ_ONLY(plan)+`--allowedTools`, resume 세션 파일 | 워크스페이스 단위·권한·MCP 출처·격리 | **이식**: 실행 단위 워크스페이스(제품), 테넌트 MCP를 `tenants.mcp`에서 읽음, permission은 정의 `agentConfig`(기본 acceptEdits). `--allowedTools`는 HYD 추가로 유지(headless에서 읽기 MCP 자동 허용; 제품은 permission_request를 사람 질문으로 넘김 — 둘 다 둔다). `CLAUDE_CONFIG_DIR` 격리는 **직접 판단**: 구독 로그인(이 PC)으로 돌릴 때는 격리하면 인증이 사라지므로 API 키가 있을 때만 격리(설정값) |
| 프롬프트 | `prompt.py:65`: 업무(activity_name)·지시사항(query)·참여자·입력 데이터(output/draft)·피드백·참고 자료·작업 공간·**결과 제출 형식**(폼 필드 JSON, 선택지는 허용값 그대로) | task.json + 짧은 지시 | 폼 계약 문장이 없음 | **이식**: 제품 섹션 구조 그대로. 결과 계약은 정의 `outputData`+form_def fields |
| 결과 해석 | `outcome.py:51`: 폼 있으면 JSON 객체(직접→펜스→마지막 균형 괄호), 빈 필드는 계약 위반 → 실패 | 펜스/선두 JSON만 | 균형 괄호 탐색 없음 | **이식** |
| 이벤트 | `_started`/`_complete`: `task_started`·`task_completed`(crew_type `result`, data goal/name/role/task_description), UI 이벤트 `tool_start`·`tool_end`·`text`·`thinking`·`plan_update`·`file_artifact`·`permission_request`·`usage`·`error`·`run_start`·`agent_log`(`events.py:38`); DB에는 `record_events_bulk`(id·job_id·todo_id·proc_inst_id·crew_type·event_type·data·status) | 5종 매핑, process API로 insert | event_type 값·data 모양 | **이식**: `record_events_bulk` RPC, 제품 data 모양 |
| HITL 일시정지 | `hitl.py`: permission_request → `.processgpt-pending.json`(session_id·question·fingerprint) + `human_input_required`(TaskState INPUT_REQUIRED) → draft_status HUMAN_ASKED; 답이 오면 `plan_resume`(session resume, "담당자 응답: …") | 없음 | | **이식**(worker+process API+portal) |
| 세션 이어가기 | output에 `cliagents_session_id` 저장, 다음 턴 `_session_of`로 resume(`executor.py:603`) | 인스턴스 session.json | 저장 위치 | **이식**: output에 저장(제품), 같은 인스턴스의 다음 작업은 이전 output에서 읽음 |
| Claude Code argv | `--print prompt --output-format stream-json --verbose --include-partial-messages --permission-mode {plan,acceptEdits,bypassPermissions} [--model] [--resume]`, `.mcp.json`(stdio {command,args,env}) | 같은 라이브러리 + `--mcp-config --strict-mcp-config --allowedTools` | HTTP MCP 등록은 제품 bridge가 미지원(stdio만) | **직접**: Claude Code 고유 `{type:http,url}`을 `.mcp.json`에 쓴다(Claude Code 문서상 지원). `tenants.mcp`에는 WMS 문서와 같은 `{type:url,url,transport:streamable_http}`로 적고 워커가 변환 |
| 워커 HTTP | `/health`(runs_in_flight), `/agents?check_auth=1`, `/runs/{id}/stream` 재접속 | /healthz | | **이식**(health·agents). 스트림 재접속은 **후반 설명** |

### 4 · 업무 RDB=Supabase+DDL+MCP (L350~353·L397~399) · 10 · HITL 포털 (L405~426)

| 주제 | 제품 로직 | 내 구현 | 차이 | 처리 |
|---|---|---|---|---|
| 테넌트 MCP 등록 | `tenants.mcp` JSONB `mcpServers:{name:{command,args,env}|{type:url,url,transport}}`(WMS 문서 L18~35), 워커가 읽어 등록 | compose env 고정 | | **이식**: tenants.mcp에 neo4j(stdio)·enterprise(http)·hyd-dmn(http) 등록, 워커는 거기서 읽음 |
| 업무 앱 MCP 모양 | FastMCP 단일 인스턴스, `@mcp.tool` async, `{result:"ok"|"error", document, error_kind}` envelope, RPC 호출 전용·RLS로 역할 제한(`mcp_server.py:1~120`) | FastMCP, `{system,facts,records}` | envelope | **이식**: `result:"ok"/"error"` envelope로 통일 |
| 사람 작업 제출 | 폼(form_def.fields_json) 제출 → output + status SUBMITTED; 승인 RPC는 로그인 사용자 역할로 RLS(WMS 10.5) | `/select`(결정·역할 검사 403) → DONE | 제출=SUBMITTED, 엔진이 DONE | **이식**: `/api/todolist/{id}/submit`(output) → SUBMITTED. 카드 선택은 폼 `select_card`의 output. 역할 검사(403)는 HYD 규칙 유지(승인 역할은 온톨로지 APPROVED_BY) |
| 내 할일 | 제품 화면: 나에게 배정된 IN_PROGRESS(처리 중) 행 | status=TODO 조회 | 반대 | **이식** |
| 알림 | notifications 테이블(`/todolist/{id}` url), human_asked 시 저장 | 없음 | | **이식**(테이블+행; Mattermost 등 외부 연동은 **후반 설명**, L405~426 "알림" 범위) |

### 1·3 · 온톨로지 스키마·Neo4j MCP (L1~30·L88~112)

| 주제 | 제품 로직 | 내 구현 | 차이 | 처리 |
|---|---|---|---|---|
| Execution 레이어 | SCHEMA.md §4.4: ProcessInstance{id,tenant_id,name,status,start/end/due,execution_scope,current_activity_ids,version}, WorkItem{id,activity_id,activity_name,status,tool,agent_mode,agent_orch,draft_status,dates,duration,rework_count,retry,adhoc}; §5.4 INSTANCE_OF(version), IN_INSTANCE, EXECUTES, ASSIGNED_TO(kind), ROLE_BOUND(role_name), SUB_OF, DEPENDS_ON | INSTANCE_OF·IN_INSTANCE·EXECUTES·ASSIGNED_TO + HYD 확장 ON_ASSET·HANDLES | 속성 일부·ROLE_BOUND 없음 | **이식**: 속성 전부·ROLE_BOUND. ON_ASSET·HANDLES는 HYD 확장으로 유지(설비·인시던트는 제품 스키마에 없음) |
| 그래프 원칙 | 그래프는 원천(RDB)의 파생 투영; vue3 d88f78ca의 graph-ontology-apache-age.md §5.1 및 ontology/schema/00-init.sql은 outbox 설계/DDL 제공 | A043 PG 원천 트리거·영속 대기·일관 snapshot·재시도·revision fence | SQLite Incident/DecisionCase와 선행 연결 복구는 남음 | 과거 '교육용이므로 outbox 대신 즉시 MERGE' 판단 폐기. 실제 PG/Neo4j14, 서비스/API4 검증. 참고의 설계/DDL을 실행 워커 구현 확인으로 과장하지 않는다. [운영 계약](../execution-projection.md) |
| Neo4j MCP | 제품은 AGE; HYD는 공식 `mcp-neo4j-cypher`(회의 L88~112 전제) | 동일 | — | 유지 |

### 6 · DMN 규칙 (L289~302·L313~348)

| 제품 | `dmn_rule_tool.py`: proc_def(type=dmn)의 DMN XML을 파싱해 LLM이 규칙 매칭표를 쓰고, 키 없으면 결정론 폴백(규칙 나열) | 내 구현 | `dmn-mcp`: 박용주 v2 `cards.py` 결정론 엔진을 도구로 | 처리 | **유지**(DECISIONS 3). 제품 도구는 **후반 설명**("ProcessGPT는 DMN을 LLM 추론 도구로도 제공"). **A113 정정(r14 D):** "제품 DMN = LLM 도구"는 불완전 — 제품에도 결정론 평가기(deterministic)가 있다. HYD 엔진 유지 결정은 그대로이며, HYD 안 불일치 2건(hitPolicy 선언 PRIORITY↔코드 "정확히 하나", 진단 규칙 미실행인데 안내문은 적용한다고 씀)은 A115 A11로 수정(UNIQUE 선언·다른 선언은 평가 거부·안내문 정정) |

### 5 · 현황값 MCP (L51~79) · 2 · 인제스천 (L253~285) · 9 · 납기 (L385~404) · 12 · 모니터링 (L434) · 13 · 후반 (L437~448) · 14 · 시나리오·교재

| 항목 | 제품 참조 | 처리 |
|---|---|---|
| 5 현황값 | 제품에 없음(WMS는 RPC 읽기) | **직접**: enterprise-mcp에 시계열 읽기 도구(값은 그래프에 안 둠, 회의 L123~135) — C 묶음 |
| 2 인제스천 | `ontology_sync.py`(증분 폴링 → apply_* → MERGE 멱등), ontology-studio(문서→엔티티) | C1: 같은 "변경분 적재 → apply → MERGE" 구조로 DDL·SOP 인제스천 실습 |
| 9 납기 상충 | WMS `get_availability`→`create_rfq`→HITL 승인 흐름 | C3: task:rank가 enterprise MCP로 납기·계약을 읽어 순위에 반영(aad500b 한계) |
| 12 모니터링 | vue3 `instanceSteps.js`(TODO 사전 생성 전제, 안 간 가지 skipped, 분기 묶음, 요약) | **이식**: 포털에 그대로 옮긴다(ES module → 전역 IIFE) |
| 13 후반 | 고착화(`deterministic_generator.py`), 스티어링, 채팅 재접속, DMN LLM 도구, 데이터 패브릭 | **후반 설명** 자료(C5) |
| 14 교재 | — | C5 |

## 2. D3 이식 순서 (의존 순)

1. **스키마** `it/supabase/migrations/20261003000001_process_engine.sql` 재작성: 제품 enum·열 전부, `users`(is_agent)·`form_def`·`notifications`·`tenants.mcp` 시드, RPC `fetch_pending_task`·`save_task_result`·`record_events_bulk`·`fetch_context_bundle`(축소판) + 엔진용 `claim_submitted_workitems`·`cleanup_stale_consumers`. seed: 사용자(운전원·생산관리자·정비관리자)·에이전트(sys:agent)·폼(select_card·escalate)·tenants.mcp.
2. **엔진** `engine.py`: 예정업무 사전 생성, TODO→IN_PROGRESS, SUBMITTED 처리(완료 판정 DONE/PENDING, XOR priority/default, 바운더리 이벤트 행, CANCELLED, gateway_decisions, variables_data list 모양, participants).
3. **DB층** `procdb.py`: 새 열, `claim_submitted`, RPC 래퍼, users/form_def/tenants 읽기.
4. **런타임** `instances.py`·`instance_mode.py`: 엔진 폴링 루프(SUBMITTED 처리·재시도·stale), 서비스태스크를 SUBMITTED에서 실행, `/submit`·`/select`(폼 제출)·`/human-response` API, 워커 API 제거(워커는 DB RPC).
5. **워커** `it/agent-worker`: cli-agent 모양(컨텍스트 준비·실행 단위 워크스페이스·bridge from tenants.mcp·프롬프트·outcome·이벤트·HITL·취소·세션 output 저장·/health·/agents).
6. **포털** `instances.js`+`instanceSteps.js`: 제품 단계 계산, 내 할일=IN_PROGRESS, 폼 제출, human_asked 패널.
7. **온톨로지** Execution 투영 속성·ROLE_BOUND.
8. **시험**: 단위(엔진·DB·워커) + `scenario_instance_test.py` 상태 기대값 교체 + 레거시 회귀. 컨테이너는 사용자가 허락할 때.

## 3. 이식하며 둔 편차 (제품과 다른 점, 근거)

| 편차 | 제품 | 여기 | 이유 |
|---|---|---|---|
| XOR 기본 흐름 | 조건 없는 흐름도 "참"으로 세고 priority 로 고름(`_sequence_condition_state` 빈 값=참) | 조건 없는 흐름(또는 properties.default)은 참인 조건이 없을 때만 (BPMN 기본 흐름) | 교육에서 BPMN 의미를 그대로 보여 주려고. `gateway_decisions` 에는 판정한 흐름만 기록(제품과 같음), 기본 흐름은 `default` 키 |
| 서비스태스크 완료 뒤 | `handle_service_workitem` 이 DONE 으로 쓰고 다음 serviceTask 만 SUBMITTED 로 잇는다 | 서비스 결과도 submit → `process_submitted` 를 지나 다음 활동(사람 작업 포함)을 연다 | 제품은 다음이 userTask 면 예정 업무가 TODO 로 남는다(화면에서 시작). HYD 흐름(command→reobserve→work-order→끝)은 자동 연결이 필요 |
| 타이머 | pg_cron `register_cron_intermidiated` | 이벤트 행의 due_date 를 엔진 폴링 루프가 본다 | 로컬 Supabase 에 cron 확장 없이도 동작 |
| 완료 판정 체크포인트 | 코드상 주석 처리(평가 안 함) | 평가 안 함(같음) | — |
| 권한 거부 이벤트 | 스트림 UI 이벤트 permission_request + 일시정지 시 human_asked | 스트림은 기록하지 않고 일시정지가 human_asked 행 하나(job_id·signature) | 같은 질문이 두 행으로 남지 않게 |
| 엔진 폴링 간격 | 5 s, stale 5 분마다 | 2 s(`ENGINE_POLL_INTERVAL_S`), stale ≈5 분 | 수업 체감 |
| 워커 재시도 | agent-sdk: 실패 즉시 FAILED(재시도 없음) | 같음 | — |
| `--allowedTools` | 없음(permission_request → 사람 질문) | 읽기 MCP·Read·Glob·Grep 을 미리 허용, 나머지는 사람 질문 | headless 에서 매 도구마다 멈추지 않게 (DECISIONS 12) |
| MCP_HOST_REWRITE | 없음 | tenants.mcp 의 컨테이너 호스트명을 호스트 실행 시 바꿈 | 강사 PC 의 구독 로그인 Claude Code 로 워커를 돌리는 수업 구성 |

## 5. 제품 규모 대비 HYD 깊이 — 실측 대조 (A092, 2026-10-07)

사용자 질문: "레포 참고해서 품질이 정말 되는 건가, 문서 수천 줄 수준의 실제 처리인가, 장난감 수준 아닌가". 고정 커밋을 다시 받아 코드 규모와 기능으로 대조했다. 아래는 코드에서 센 값이며, HYD 쪽은 실제 실행 증거가 있는 것만 "됨"으로 적는다.

| 영역 | 제품(고정 커밋) | HYD 현재 | 판정 |
|---|---|---|---|
| 프로세스 엔진 규모 | process-gpt-completion b272c9a: 4.7만 줄(`workitem_processor.py` 5,550) | `procsvc` 1.07만 줄 + 워커 1,503 + 에이전트 2,073 | 제품의 1/4 규모 |
| 엔진 기능 | subProcess·adHocSubProcess·callActivity·multiInstance(foreach)·parallel/inclusive/exclusive 게이트웨이·타이머·crewai/langgraph 오케스트레이션·결정론 고착화·보상·재작업 | 사람/서비스/businessRule task·배타 게이트웨이·경계 타이머·cliagents(Claude Code·Codex)·보상·재작업·효과 영수증 (A092 당시) → **A100 병렬 분기·합류 추가, A116부터 에이전트 작업은 제품 모양 userTask+agentMode(정의 2.2; 저장된 1.0~2.1의 businessRuleTask는 불변·엔진이 그대로 실행), A115 게이트웨이 없는 분기 등록 거부** | 서브프로세스·다중 인스턴스·다른 오케스트레이션 **없음** (A041 지원 범위, 병렬은 A100으로 생김) |
| 인스턴스·todolist·이벤트 | agent-sdk e4728a2 `database_schema.sql` 그대로 + 폴링 lease/max_claims | 같은 테이블·열·RPC 이름, 폴링 claim·stale 정리 | 같음(42/42·1배속 완주로 확인) |
| 문서 인제스천 파이프라인 | process-gpt-bpmn-extractor c7992ce 3.3만 줄: PDF/OCR(최대 50쪽)·SOP 경계 탐지(LLM, 최대 30쪽)·고정/의미 청크(1,000자, 겹침 200)·메멘토 임베딩 청크·절별 추출·청크 간 병합(`test_chunk_integration` 5종)·검증기 1,315줄(엔진에 실제 실행해 추적 비교)·HITL 728줄 | (A092 당시) 문서 전체를 Claude Code **한 작업**에 넘기고(16,000자 초과는 파일로 전달) 문자 좌표 앵커·페이지 검토 전수·3회 교정 루프·커버리지·충돌 미리보기 → **현재(A117~A119, 10-07):** 앵커는 에이전트가 `{page, quote}`만 내고 좌표는 서버가 찾음(`manual_locate.py`: 정확→글자·숫자→낱말 끼어듦 40자, 모호하면 긴 인용 요청), 결과는 작업 폴더 `output/result.json` 파일(메시지 JSON은 하위 호환), 구간 기준 80,000자(정의 1.8) | A093: 제목 경계 40,000자 구간 → 구간별 Claude Code 작업 → 서버 좌표 복원·결정적 병합 → 전체 계약 재검증(제품의 청크→추출→병합과 같은 모양, 임베딩 청크는 없음). 실측 2,294줄(구간 3, 1,443 s, 7/8)·6,785줄·24만 자(구간 7, 82분, 7/8, 절 198·SOP 193 전부, 중복 0)·실제 다이킨 EHU40 80쪽 PDF(구간 4, HANDOFF A094). **A119: EHU40 1.8은 구간 2·612 s·교정 0·10/10(1.6은 구간 4·902 s), 1.6↔1.8 SOP Jaccard 0.711·공통 단계 27/27·유사도 0.901 → B4 코드 파서 혼합은 하지 않음. A118: 문서별 골든 퀘스천 보고(에이전트 답 + 서버가 문서 노드 인용 대조, HM-9 3문항 라이브)** |
| 지식 문서 색인 | ontology-studio 6a229be `document_indexing` 878줄: OCR·토큰 기준 청크(1,200/150)·임베딩·Neo4j 풀텍스트+벡터 인덱스 | 없음(그래프에 원문 청크·벡터 인덱스 없음, 매뉴얼은 SQLite 보관+절/단계 노드) | 없음 |
| 온톨로지 MCP | ontology-studio 읽기 4도구 + 출처(sources) | hyd-dmn 13도구(진단·규칙·입력·시계열·PromQL·카드·예측·제출)·enterprise MCP·Neo4j MCP | HYD가 넓음(실측 다수) |

실측(수천 줄 문서): `scripts/make_large_manual.py`로 만든 교육용 매뉴얼 2,294줄·80,502자·158 KB·절 69·SOP 61(+폐지 1)을 실제 Claude Code 워커로 추출 — 결과는 HANDOFF A092. 통문서 1작업: DONE 1,180 s·내용 검사 전부 통과, 단 출력 160 KB를 한 메시지로 내는 구조(크기 상한). A093 구간 추출: 같은 문서 DONE 1,443 s·7/8(발췌 선택 4절 차이), 3배 문서(6,785줄·470 KB) 실측은 HANDOFF A093.

주의: 위 "수천 줄"은 내가 생성기로 만든 교육용 문서 크기이며 현업 대표 크기의 근거가 아니다. 참고 레포 안에는 인제스천용 실제 샘플 문서가 없고(bpmn-extractor `output_bpmn/`은 결과 BPMN 2종 22~43 KB, 입력 문서는 없음; ontology-studio는 스펙 docx 72 KB), 코드의 상한(OCR 50쪽·SOP 경계 30쪽·청크 1,000자)만 있다. 현업 매뉴얼 크기 조사는 별도(HANDOFF A094 예정).

## 6. r14 재확인 뒤 상태 — 결함 A1~A12·구조 변경 B1~B8 (2026-10-07 A113~A119)

사용자 기준(10-07): 레포 대조는 "정답이 있는데 또 만드는 낭비"를 막기 위한 것이다. 현 구현이 회의 요구를 만족하고 더 견고하면 그것이 정답이며, 단 제3자 입장에서 결과·효율·안정성·범용성 네 기준으로 양쪽을 적대적으로 판정한다(DECISIONS 100). 판정 원문은 `verification/2026-10-07/r14-summary.md`, 수정 근거는 HANDOFF §9 A114~A119.

| # | 결함/구조 | 판정 | 반영 | 증거 |
|---|---|---|---|---|
| A1~A5 | 임대 횟수·연장 예외·CLI 선택 키·Codex toml 비밀·env 접미사 차단 | 레포가 나음 → 고침 | A114: 마이그레이션 21(claim_count는 회수만 +1)·`LeaseLost`·`agent_cli` 계열 키·`codex-mcp.toml` 삭제·`*_TOKEN/*_API_KEY` 차단 | 단위 1,108, 라이브 임대 `a114-lease-1/` 6/6 |
| A6 | 게이트웨이 없는 분기 등록 통과·합류 활동 2회 실행 | 레포 규칙(uncontrolled_split)이 나음, HYD는 WARNING이 아니라 등록 거부로 | A115: `definition_registry._gatewayless_splits` 400, 시험 정의·예시 8개를 `fork` 병렬 게이트웨이로 | `.evidence/a115/a6_live.out` |
| A7 | 보상 함수 행 잠금 없음·unknown 입력·재생 키 | wms가 나음 | A115: 마이그레이션 22(for update·advisory lock·INVALID·`ent.tx_response`) | `a7_probe.out`, 동시 취소 2건→1건 `a7_race.out` |
| A8 | legacy 평가 경로 lease 잔존 | infra-docker 10-06이 나음 | A115: 점유 직후 `clear_task_lease` | 회귀 `reg-a115c` |
| A9 | 에이전트 SQL 규칙이 상시 지시에 없음 | text2sql이 나음 | A115: `workspace.CONSTITUTION` 4줄 | 지시 파일 시험; 에이전트 준수는 LLM 실행 미검증 |
| A10 | DB 주석 변경 미감지·형식 매핑 부분 문자열 | HYD 자체 결함 | A115: `COMMENT_CHANGED`(기준은 적재 뒤 첫 동기화의 실제 DB 주석)·정확 대조 | `ddl-drift-4` 8/8 |
| A11 | hitPolicy 선언≠동작·진단 규칙 안내문 | DMN 표준 | A115: UNIQUE·다른 선언 평가 거부·안내문 정정·kg-seed 재적재 | `a11_live.out` |
| A12 | 사람 질문 카드 `text`만 읽음 | vue3 10-06 | A115: `humanQuestionText`(text→question) | node 함수 시험, 화면 미검증 |
| B5 | 에이전트 활동 유형(businessRuleTask ↔ userTask+agentMode) | 양방향 불통 → **한다** | A116: 정규화 등록기·정의 2.2·투영 속성·`definition-authoring.md` | 단위 1,161, 제품 pydantic 파싱 무시 0, `b5_live.out` PASS |
| B2 | 인용 위치를 서버가 찾기 | 결정적·즉시 → **한다** | A117: `manual_locate.py`, 앵커 page+quote | `.evidence/a117/replay_locate.json` 265/267·231/233 |
| B3 | 문서별 골든 퀘스천 보고 | 수업 장면(L253~285) → **한다** | A118: `manual_golden.py`·`manual_golden_check` 1.0·API 2개·commit 연동 | 단위 21, 라이브 `.evidence/a118/golden_report.json` 3문항 |
| B1 | 인제스천 결과를 파일로 | 마지막 메시지 JSON 잘림 위험 → **한다** | A119: `output/result.json`·정의 1.8·구간 80,000자 | 단위 1,198, EHU40 1.8 612 s 10/10 |
| B4 | 구조는 코드 파서·절차는 LLM 혼합 | 재현성 측정 뒤 결정 → **하지 않음** | A119 1.6↔1.8 비교: Jaccard 0.711·공통 SOP 단계 27/27·유사도 0.901, 흔들림은 범위·인용 끊는 위치·점검표 펼침(파서가 고칠 성질 아님) | `.evidence/a119/compare.md`; 범위 고정 원하면 정의에 "SOP로 삼을 장" 명시(사용자) |
| B6·B7 | BPMN을 정의에서 그리기·인스턴스 상세 정리 | UI/UX로 편입 | A121 정리안: BPMN B안(정의 JSON→자체 SVG, 레인 3)·상태 색 StatusChip·명칭표; 구현은 A122 | `UIUX_PLAN.md`, `.evidence/a121/` |
| B8 | InputData 동의어·OCR·본문 검색 | 선택 | 미착수 | — |
| C | 타이머·인스턴스 잠금·실패 PENDING·멱등 키·SQL 검사·DDL 드리프트·BSC 상충·사람 질문 DB 재개·폼 렌더러·실시간 스트림 | HYD가 나음 → 유지 | 변경 없음 | r14-summary §C |

A115에서 먼저 "B는 전부 안 한다"고 했던 판정은 한쪽으로 기운 것이라 철회했다(HANDOFF A115). 제품 엔진(completion)이 HYD 2.2 정의를 실제로 구동하는 시험은 하지 않았고 모델 파싱까지만 확인했다.
