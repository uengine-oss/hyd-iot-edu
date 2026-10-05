# HANDOFF — 회의·참고 레포에 근거한 HYD 시스템 구현·검증

> **현재 재개 위치: §9 G → [AUDIT.md](AUDIT.md).** 2026-10-04 사용자는 회의 요구·HYD 실제 구현·uengine-oss 전체 지도를 재대조하고 필요한 재구현 및 강의 보강을 승인했다. F만 수행하고 종료하지 않는다. 최신 계약은 GOAL 상단이다. 아래 A~F/C의 수치와 '완료'는 당시 범위의 과거 기록이다. '결정론이 회의 원칙'이라는 해석은 원문 313~348행으로 입증되지 않는다(DECISIONS 15). 리소스 사용·필요한 삭제는 위임됐다. §2·§3의 상충하는 옛 규칙보다 최신 사용자 지시가 우선한다.

최종 갱신 2026-10-05 A071 (조건 재검토·새 타이머 도달; 전체982·실제24·쿨러42; 전체Goal 미완료)
**이 파일은 재개용 기록이다. 현재 사용자 지시·현행 계약·실제 상태(`git status`, 컨테이너)와 대조한다.**
**이 파일은 작업 단계마다 갱신한다. 대화 요약이 끊겨도 이 폴더만 읽으면 이어갈 수 있어야 한다(§9 진행 상태를 먼저 본다).**
폴더 구성: [GOAL.md](GOAL.md) 의도·DoD · **HANDOFF.md**(이 파일) 현재 사실·규칙·상태 · [QA.md](QA.md) 질문과 확정 답 · [DECISIONS.md](DECISIONS.md) 결정 경위·폐기 판단 · [USER_UTTERANCES.md](USER_UTTERANCES.md) 발화 대응표.

## 0. 30초 브리핑

전체 Goal은 미완료다. 회의 원문·고정 참고코드에 근거한 시스템 개발만 대상이며 교재/리허설은 제외한다. 재개점은 §9 G의 A071 후속이다. A066 47스냅샷/채택표와 A067~A070 물리 원천·현재값·명시 순위·BSC 경로/조건을 유지했다. A071은 별도 분기의 선행 검토를 새 세대에 포함하고 정확한 새 입력 생산·제어 도달을 기다리도록 연결했다. 실제 시험에서 이전 timeout 작업이 새 타이머 전에 열리는 결함도 찾아 수정했다. 전체982/6warnings, 실제HTTP·PG·kill/start·타이머·Neo4j24/24, 같은배포 쿨러42/42다. 18서비스 running/unhealthy0, worker·probe0, 실패포함6시험인스턴스 모두종결, 개인Codex설정불변. 다음은 전체미결표의 실제효과 보상 계약과 원천→의미/지식→판단의 변경 수용이며 새 엔진 기능만 확장하지 않는다. 전체 의미/실제추출·변경질의·47레포 깊은채택은 남는다. 새Codex/직접UI는 기존정책차단으로 미검증이며 우회하지 않는다.

전체 요구별 판단은 AUDIT/PROGRESS의 R01~R14를 따른다. 현재 평가62.5점은 동일 가중치 단계평가이며 공수 완료율이 아니다. 문서 추출 정확성·변경 지식의 새Codex·전체 의미 연결·효과 보상/의존 스케줄링·47레포 채택 대응 등은 미결이다. A034 실제Codex42/42는 당시 코드의 별도 증거이며 A059 레거시 검증으로 대체하지 않는다. A033 정책 거절은 danger-full-access/never에서도 발생했다. 설정명만 보고 해제됐다고 가정하거나 다른 래퍼로 우회하지 않는다.

**목적 재확인(2026-10-05):** ProcessGPT 구조를 HYD 사례로 직접 구현하는 과정이 온톨로지·에이전트 강의의 재료다. 인제스천으로 지식을 준비하고 이벤트→Start Event→인스턴스→소속 Task의 에이전트/사람/서비스 실행→종결로 연결한다. 교재 제작 제외를 교육 목적 제외로 해석하지 않는다. GOAL의 목적 재확인과 PROJECT_STATUS의 전체 흐름을 따른다. 새 제품 검증을 수행했다는 뜻은 아니다.

### 2026-10-05 보고·Git 전달 체크포인트

사용자가 최종 방향·현재까지의 결과·다음 작업을 명확하게 보고하고 PUSH까지 하라고 명시했다. [PROJECT_STATUS](../PROJECT_STATUS.md)와 `D:/work/작업보고/2026-10-05.md`에 보고를 작성했다. 이번 누적 시스템 작업의 `origin/main` push는 승인된 범위이므로 재승인을 묻지 않는다. 제품 최신 확인 검증은 A071이며 보고를 시작할 때 C03 보상 코드와 HYD 기업 실행 원장은 읽기 단계였다. 최종 Git 비교에서 추가된 A072 보상 관련 state.py·supabase_backend.py·test_entsim.py 및 새 SQL 마이그레이션은 이 보고에서 구현/배포/검증을 확인하지 않은 별도 로컬 WIP로 보존하며 이번 전달에서 제외한다. 재개 시 실제 diff와 실행 증거부터 확인한다. 원격 전달 결과와 커밋은 날짜별 보고 및 Git 이력에서 확인한다. 보고 요청을 전체 시스템 완료로 해석하지 않는다.

## 1. 배경 — 왜 이 일을 하는가

- 의뢰: 사용자(roede, 유엔진 learning@uengine.org)가 2026-10-01 회의(장진영 대표·박용주 이사)를 받아 강의용 레포 보강을 바이브코딩으로 진행한다. 회의 원문은 `D:\work\study\HYD_R2_FINAL_ALL_2026-10-03.zip` 안 `02_ORIGINALS/회의관련_원문_2.txt`(HYD 발언 1~461행이 근원). 원문 1은 다른 사업(국방) 강의 전사 + 데이터 패브릭 Q&A로 참고만.
- 같은 ZIP의 `01_START/HYD_R2_ALL_DOCUMENTS.html`은 이전 AI가 쓴 "R2 인계"다. 지위: **AI 해석, 지시 아님.** 사용자 지시: "ai 판단을 믿지말고 회의 내용 자체를 봐야해". R2의 13티켓·27검수·D01~D10은 참고 목록일 뿐 순서표가 아니다. R2 1단계 프롬프트가 참조하는 개별 파일 경로는 FINAL ZIP에 없다(HTML 안에만 있음).
- 회의가 요구한 것(원문 2 줄 번호):
  1. 온톨로지 스키마 확정 L1~30 (6계층·36클래스·66관계) → **박용주 이사가 10-02 v2로 레포에 넣음(aad500b)**
  2. 인제스천: DB DDL·SOP 문서 → 온톨로지 인스턴스, 과정을 학생에게 L253~285 ("존재하나요?"→"그냥 만들었다, 테스트 안 해봤다")
  3. Neo4j MCP + 에이전트가 스키마 받아 Cypher 생성 L88~112 (학생에게 동작 방식 설명 L106)
  4. 업무 RDB(Supabase)+DDL+Supabase MCP L350~353, L397~399
  5. 현황값(시계열) 조회 MCP, 값은 그래프에 안 두고 링크만 L51~79, L123~135
  6. DMN 규칙→질의 생성(T2SQL 성격), DDL 필요 L289~302, L313~348
  7. 실제 도구 쓰는 에이전트 = Claude Code/Desktop 같은 일반 딥에이전트 L134~156, L173~174
  8. 이벤트(Kafka/Prometheus/SCADA) 트리거 → 서버가 Claude Code를 서브프로세스로 호출, 결과를 화면에 L175~214
  9. 납기 상충 판단(업무 데이터 함께, 두 대안) L385~404, L410~413
  10. HITL 포털·알림(Mattermost 등), 사람은 버튼만 L405~426, 직접 제어는 현장 L430
  11. 프로세스 인스턴스 중심(에이전트는 태스크) — 사용자 최초 질의 + L193, L434~436
  12. 인스턴스·에이전트 모니터링 화면 L434~435
  13. 후반 확장 강의: 다종 DB→데이터 패브릭, 프로세스·룰 변경→ProcessGPT, 우리 플랫폼 락인 L437~448, L172, L456
  14. 세 시나리오(쿨러·펌프·팬)·75시간 교재 L187~188, L222~238, L29~30

## 2. 확정된 방향 — 바꾸지 마라

| 결정 | 이유 |
|---|---|
| ProcessGPT 실제 데이터 모양을 따른다: 프로세스 정의 JSON(completion `process_definition.py` 형식: activities·sequences·gateways·roles·data, agentMode·orchestration), 인스턴스·태스크는 agent-sdk `database_schema.sql`의 `todolist`·`events`·`bpm_proc_inst` 열 이름 | 사용자: "교육강의로 인해서 너무 간소화하지말고 적당하게 참고할 레포대로". 후반에 "이게 ProcessGPT다"가 성립해야 함 |
| 에이전트 워커 = process-gpt-cli-agent 구조(agent_orch='cliagents'), cliagents exec surface로 Claude Code 호출(`claude --print --output-format stream-json`), resume_session으로 한 인스턴스의 네 businessRule 태스크(diagnose·candidates·compliance·rank)를 한 세션으로 이어감 | 회의 L175~214 그대로. 비용은 한 세션분, 학생은 태스크 네 개가 각각 열리고 닫히는 걸 봄 |
| 기존 결정론 DMN 엔진 `it/agent/agentsvc/cards.py`는 버리지 않고 Claude Code가 호출하는 MCP 도구로 노출 | ProcessGPT 원칙 "반복 판단은 DMN·규칙으로 결정론화, LLM은 수집·설명". 박 이사 10-02 작업 보존 |
| 업무 DB = Supabase 로컬(`supabase start`), WMS 예제(sample-app-wms) 구조: 스키마·RLS·RPC + FastMCP 서버 | 회의가 "Supabase MCP"를 이름으로 말함. 사용자 추천 수용 |
| 6번 질의 생성은 DDL을 프롬프트에 넣어 Claude Code가 직접 SQL 생성. robo-data-text2sql은 후반 확장 설명용 | 교육용 테이블 몇 개 규모. 사용자 추천 수용 |
| 그래프 DB는 Neo4j 유지. ProcessGPT 스키마 계약(`process-gpt-vue3/ontology/SCHEMA.md`)의 Execution 레이어(ProcessInstance·WorkItem, INSTANCE_OF·IN_INSTANCE·EXECUTES·ASSIGNED_TO)를 v2에 추가 | 회의·HYD 모두 Neo4j 전제. 제품은 Apache AGE지만 모델만 따름 |
| 기존 Incident 상태기계(`it/process/procsvc/machine.py`: approve→action.cmd→게이트웨이→ACK→재관측→작업지시→종결)는 PLC 명령 경로의 서비스 태스크로 그대로 재사용 | 검증된 안전 경로. 회의 L430 "직접 제어는 현장" |
| 첫 묶음 = 쿨러 시나리오 한 바퀴가 새 구조(인스턴스→에이전트 태스크→사람 태스크→실행→종결)로 돌 때까지. 그 뒤 인제스천·Execution 레이어·펌프·팬 | 의존 순서 4→6, 3·4·5→7, 7·8→11 |
| 데이터 패브릭은 **구현하지 않고** 후반 설명만 | 회의 L63~67 "패브릭까지 안 가더라도", L447 확장 시나리오 |

## 3. 절대 규칙 — 어기면 산출물이 무효다

- 사람은 승인·거부(카드 선택)만 한다. 에이전트는 승인 없이 실행하지 않는다(10-01 확정 규칙 H007·H016, `docs/ontology/web-design-kit/03_우리목표와_확정규칙_QA.md`).
- PLC 명령은 process 서비스의 Incident 경로(action.cmd→cmd-gateway)로만 나간다. 에이전트·워커·MCP가 직접 쓰지 않는다.
- 재생·가정·예측을 실측처럼 쓰지 않는다. 데이터 없음과 조회 실패를 구분한다.
- 기존 기능을 지우지 않는다: 온톨로지 v2·템플릿·cards.py·machine.py·포털·매뉴얼 인제스천·enterprise-sim 실행 의미. 새 구조는 옆에 붙이고 `PROCESS_MODE`로 전환하되, 통합 시험이 통과하기 전에는 기존 경로(`scripts/scenario_test.py` 62/62)를 깨지 않는다.
- 유료 결제(Supabase 클라우드 등)·원격 push·기존 파일 삭제·실설비 연결은 사용자에게 묻는다.
- 회의 원문 줄 번호로 근거를 댄다. R1/R2 티켓 순서를 따르지 않는다.
- 작업 단계마다 이 파일 §9를 갱신한다. "작업보고"는 사용자가 따로 요구할 때만.

## 4. 확정 사실 — 다시 조사하지 마라

**레포 상태(2026-10-03 확인)**
- 로컬 HEAD = origin/main = `aad500b` (박용주 10-02 18:12 "온톨로지 v2로 서비스 이전", 73파일 +6,757). fast-forward 완료.
- 로컬 미커밋: `it/process/procsvc/decisions.py` reject()에 `reason=reason` 저장 1줄(사용자 변경, 보존). 미추적: `docs/ontology/web-design-kit/`, `docs/ontology/온톨로지설계_웹용_20261002.zip`, `docs/src/`, `docs/마스터_가이드.html|pdf`, `docs/회의자료/`(사용자 작업, 보존).
- 단위 테스트 145 통과: `.venv314/Scripts/python.exe -m pytest -q`(2026-10-03). 통합 `scripts/scenario_test.py`는 Docker 꺼져 미실행(커밋 메시지는 62/62).
- aad500b 커밋 메시지의 알려진 한계: 트립 리셋 카드 거부, 순위에 납기·품질 미반영, 종결 시 근본 조치 작업지시 CMMS 미발행, 자율 실행·승인 시간초과 미구현, 펌프·팬 시뮬레이터 없음.

**환경(2026-10-03)**
- Windows 애플리케이션 제어 정책이 `C:\Users\roede\AppData\Roaming\uv\python\*` 파이썬 전부 차단(os error 4551). 기존 `.venv` 불능. 공식 `C:\Users\roede\AppData\Local\Programs\Python\Python314\python.exe`(3.14.7)만 실행됨 → `.venv314` 생성(`.git/info/exclude` 등록). requirements 고정 버전(psycopg 3.2.3, pydantic 2.10.4)은 3.14 휠 없어 상위 호환 설치. Docker 이미지는 3.12라 영향 없음.
- Docker 엔진 29.7.2 동작 중, 사용자가 2026-10-03 저녁 컨테이너·볼륨·이미지를 전부 비웠다(첫 compose 빌드·Supabase 기동은 이미지 내려받기로 수 분). 리소스 기동·정리는 에이전트가 직접 한다. supabase CLI 2.119.0 설치됨(`npm i -g supabase`, 2026-10-03). claude 2.1.250, codex 0.151.0, node 24, uv 0.12.5 있음. gh 없음.
- 참고 레포 clone은 세션 스크래치(`C:\Users\roede\AppData\Local\Temp\claude\d--work-study\<세션>\scratchpad\refs\`)에 있어 세션이 끝나면 사라질 수 있다. 다시 필요하면 `git clone --depth 1 https://github.com/uengine-oss/<repo>.git`(전부 공개).

**레포에 이미 있는 것(재사용, 재구현 금지)**
- 온톨로지 v2: `it/neo4j/v2/schema.json`(단일 원본) → `constraints.cypher`·`ontology-schema.ttl`·`schema_prompt.md`(에이전트용 DDL)·`queries.cypher`(정답 Cypher)·`instances.cypher`; `scripts/ontology_v2.py gen|load|validate|queries`; `docs/ontology/schema-v2.md`. BPMN 프로세스 노드 15개: ev:alert(message start, correlationKey asset) → task:diagnose/candidates/compliance/rank(businessRule, sys:agent) → task:select(user, role:operator, boundary timer ev:select-timeout PT10M → task:escalate role:prod-mgr) → gw:control → task:command(service sys:scada) → task:reobserve(service sys:process) → gw:recovered → task:work-order(service sys:cmms) → ev:closed / ev:escalated.
- 템플릿 `it/neo4j/templates/t0~t3*.cypher`(T3: dmn·inputs·skills·tradeoffs·forecasts·precedents·roles·suppliers).
- 에이전트 `it/agent/agentsvc/`: main.py(Kafka alerts 구독→pipeline), card.py(원인 순위·가이드 카드), cards.py(DMN 평가·순위, pure), decide.py(사실 수집 gather_facts: InputData -SOURCED_FROM-> 출처별 조회, 결정 제출), guardrail.py, llm.py(요약문만), tools/mcp_kg.py(템플릿 화이트리스트, MCP 서버 아님)·mcp_tsdb.py·mcp_ent.py·mcp_prom.py.
- 프로세스 `it/process/procsvc/`: machine.py(Incident 상태기계), definition.py(STEPS), decisions.py(카드 승인 권한), store.py(SQLite 스냅샷), kgadmin.py(매뉴얼→SOP 파서), main.py(API: /api/incidents, /api/decisions, /api/incidents/{id}/decide, /api/kg/*, /api/plant/{asset}/status).
- 기업 목업 `it/enterprise-sim/entsim/`: data.py(MES·ERP·CMMS·QMS·SCM·EMS 딕셔너리), state.py(실행 멱등), main.py(GET /mes/orders 등, POST /api/exec).
- 포털 `it/portal/www/`(정적 JS: app.js·hitl.js·enterprise.js·main.js), compose.yaml(프로필 ot·backbone·detect·knowledge·agent·enterprise·process).

**참고 레포 조사 결과(README·핵심 파일 읽음, 2026-10-03)**
- process-gpt-completion `polling_service/`: 5초마다 `todolist` status=SUBMITTED(consumer null) 조회→consumer=pod 점유→activity type별 처리→DONE; 다음 액티비티 workitem 생성(user task는 TODO). `process_definition.py` ProcessActivity 필드: id,name,type,role,instruction,inputData,outputData,checkpoints,tool,agent,agentMode,orchestration.
- process-gpt-agent-sdk `database_schema.sql`: todolist(id uuid, user_id, proc_inst_id, proc_def_id, activity_id, activity_name, start/end/due_date, description, tool, tenant_id, assignees jsonb, output jsonb, retry, consumer, log, status, agent_mode, agent_orch, draft_status, root_proc_inst_id, execution_scope, rework_count), events(id, job_id, todo_id, proc_inst_id, data jsonb, event_type enum: task_started/task_completed/tool_usage_started/tool_usage_finished/human_asked/error…).
- cliagents(`src/cliagents/execution.py`, `providers/claude_code.py`): `ExecRequest(prompt, workdir, model, permission, resume_session)`, `stream_exec/run_exec` → ExecEvent(run_start·assistant_text·tool_start·tool_end·result·error…); Claude Code argv `--print <prompt> --output-format stream-json --verbose --include-partial-messages --permission-mode plan|acceptEdits|bypassPermissions [--resume id]`; MCP는 프로젝트 `.mcp.json`(install_bridge가 멱등 병합). pip: `pip install git+https://github.com/uengine-oss/cliagents`, 의존성 0.
- process-gpt-cli-agent: `core/{selection,availability,workspace,prompt,skills,bridge,events,outcome,hitl,journal,runner}.py`, executor는 a2a AgentExecutor. 워커 1개(런 레지스트리 메모리).
- sample-app-wms: `supabase/config.toml`(포트 55321~), 스키마 `wms.*` + RLS + RPC, `mcp/wms_mcp/mcp_server.py` FastMCP(`@mcp.tool`, RPC 호출), `docs/03-processgpt-integration.md`(테넌트 mcp JSON에 `{"type":"url","url":"http://wms-mcp:8199/mcp","transport":"streamable_http"}` 등록, 에이전트 허용 도구 목록).
- ontology-studio `docs/ontology-mcp-server.md`: 읽기 MCP 4도구 `ontology_query/list_entities/list_schemas/get_schema`, 답에 sources(node_id·labels·excerpt). process-gpt-vue3 `ontology/SCHEMA.md`: Execution 레이어 정의(ProcessInstance{id,status NEW|RUNNING|COMPLETED,…}, WorkItem{id,activity_id,status,agent_mode,agent_orch,…}, INSTANCE_OF·IN_INSTANCE·EXECUTES·ASSIGNED_TO). process-gpt-strategy `ontology_sync.py`: 원천 테이블→그래프 증분 MERGE, dangling 정책.
- robo-data-text2sql: Neo4j에 Table/Column/FK 그래프 + ReAct SQL 생성(큰 서비스). ontological-db 연구용. process-gpt-knowledge-graph 빈 레포.

## 5. 폐기된 판단 — [DECISIONS.md](DECISIONS.md) 로 이동

## 6. 미결정 — 무엇을 보고 정하나

- 학생 실습 깊이·시수(원문 75시간 미확정): 쿨러 한 바퀴가 돌고 파일럿으로 시간을 재서 정한다.
- 알림 채널(Mattermost 등 vs 포털 내 할일 목록만): 첫 묶음은 포털 할일 목록(todolist TODO)으로 하고, 외부 알림은 후속.
- Execution 레이어를 그래프에 쓰는 시점·방식(이벤트마다 MERGE vs 종결 시 일괄): process 서비스가 기존 record_incident처럼 종결·승인 시점에 MERGE하는 것으로 시작, 모니터링 화면 요구가 생기면 늘린다.
- ~~펌프·팬 결함 시뮬레이터(plant-sim에 없음)~~ → 10-04 C4 로 구현(§9 C4). 남은 결정: 실제 완주 뒤 시나리오별 실습 시수.

## 7. 외부 대기 — 우리가 못 정하는 것

- 컨테이너 안 Claude Code가 쓸 `ANTHROPIC_API_KEY`(통합 시험용). 사용자에게 요청 예정. 교육 배포 시 학생 키 정책도 사용자 결정.
- Docker 데몬 기동(사용자 PC). 켜지면 B11을 바로 진행한다(supabase CLI는 설치 끝).

## 8. 자산 지도 — 무엇이 어디 있고 언제 여는가

| 언제 | 열 것 |
|---|---|
| 회의가 뭘 요구했는지 | `D:\work\study\HYD_R2_FINAL_ALL_2026-10-03.zip` → `02_ORIGINALS/회의관련_원문_2.txt` (줄 번호는 §1과 동일 파일 기준) |
| 10-01 확정 규칙(사람은 승인만 등) | `docs/ontology/web-design-kit/03_우리목표와_확정규칙_QA.md` |
| 온톨로지 v2 설계·BPMN 노드 | `docs/ontology/schema-v2.md`, `it/neo4j/v2/instances.cypher` 5절 |
| 에이전트에게 줄 스키마 설명 | `it/neo4j/v2/schema_prompt.md` |
| 현재 HITL 흐름 | `it/process/procsvc/main.py`(hitl_decide), `machine.py` |
| 통합 시험 기준 | `scripts/scenario_test.py` |
| 이전 AI 인계(참고만) | ZIP의 `01_START/HYD_R2_ALL_DOCUMENTS.html` |
| 오늘 작업보고 | `D:\work\작업보고\2026-10-03.md` |
| 사용자 발화 원문(이 작업) | [USER_UTTERANCES.md](USER_UTTERANCES.md) |

## 9. 진행 상태 — 여기부터 이어간다 (매 단계 갱신)

**08:01 추가:** 새 승인 전달 모듈3개/migration00005/실제Pg·SQLite·HTTP 강제종료 검사기는 작성했지만 runtime 연결·migration 적용 전이다. expanded red는11실패다. 실제Codex 전체 재관측이 끝난 뒤 연결한다. 현재코드6개와SHA를 `a025-before-wiring/`에 보존했다.

**07:55 추가:** 수정 후 실제 Codex 네 작업248초·MCP18건 시작/종료·오류0, 사람 역할검사/PLC ACK까지 통과했고600초 재관측 중이다. 최종 판정 전이다. A025 승인 저장 결함의 실패검사7개를 추가했다(`a025-red.xml`, 일부는 신규 복구 인터페이스 수용조건). [승인 복구 설계](APPROVAL_RECOVERY.md)를 작성했으며 가동 구현은 아직 변경하지 않았다.

**G. 전체 요구·레포·HYD 재대조 및 구현 (현재 작업)**

**사용자 최신 범위 정정:** 회의·실제 레포를 근거로 HYD 시스템을 개발하고 실제 동작을 검증하는 일이다. 교재·슬라이드·75시간 시수·강사/학생 리허설은 하지 않는다. 과거 아래 기록의 강의 산출물 미결을 현재 완료 조건으로 가져오지 않는다. 시스템 기능·실행 검증·사용/운영 문서·요구/레포/결정/증거/인계 기록은 범위에 남는다. GOAL 상단 및 REBUILD §4에 반영했다. 이미 수정한 교재는 과거 이력으로 보존하고 추가 작업하지 않는다.

**세션 전환(2026-10-05 06:55): Claude Code 세션이 이어받음(사용자 "이어서 가능한가?"). Codex 세션은 06:49 A071 기록을 끝으로 중지된 것으로 간주한다. 두 세션을 같은 폴더에서 동시에 돌리지 않는다.**

**현재 재개 — A071: 별도 경로의 조건 재검토·새 입력 대기·새 경계 타이머를 연결했고 실제24항목을 검증했다. 동일배포 쿨러42/42도 확인했으며 전체Goal 미완료다.**

### A071 조건 재검토와 경계 이벤트의 실제 도달

회의2 19~24/434~436 및 사용자 정의/데이터 변경 요구를 고정 C03 completion `b272c9ab` process_engine.py978~1034, workitem_processor.py4431~4535와 대조했다(`a071-reference-read.json`,2파일HEAD행내용일치). 제품은 시작/후행 상태의 새 작업과 보상 생성 호출, 부착 이벤트의 시스템 후보를 만든다. HYD의 정확한 세대·생산자·PG거래·도달 대기를 동일 제품 구현이나 실제 효과 보상으로 주장하지 않는다.

기존 재작업은 별도 경로의 조건·gateway·boundary가 있으면 일괄 보류했다. 이제 바뀐 조건 변수에서 분기 앞의 실제 검토 작업까지 영향 범위를 확장하고, 해당 검토를 새로운 작업 세대에 포함한다. inputData에 없어도 시퀀스 조건에 쓰는 새 값은 정확한 생산자 UUID/세대/DONE/출력 근거를 기다린다. `[ConditionData]`와 flow_state.condition_snapshots에 값/출처를 남기고 실제 새 제출 뒤 분기를 판단한다. 누락된 새 값은 기본 분기로 보내지 않으며 검토 자신의 필수 조건출력 누락은 PENDING이다. 타이머는 새 검토의 실제 도달 시점에 새 UUID/기간으로 생성된다. activity_arrivals는 실제 열린 UUID/세대를 보존해 시간초과로 취소된 검토의 재개 근거와 단순 TODO 생성시각을 구분한다.

최초6실패(`a071-red.log`) 뒤 관련45, 추가누락/조건범위 검사와 최초전체981를 확인했다. 실제 첫 실행 `a071-live-first/`은 gateway/PG/kill-start/재시도/세대2/graph15통과 뒤 타이머 이전에는 late 작업이 아직 없다는 검사기 계약을 놓쳐 KeyError/exit1. 원래 사례의 실제 timeout후속을 정상제출해 종결하고 실패원문을 보존했다. 다음 `a071-live-final/`에서는 이전 timeout 후속 작업이 새 타이머 전에 열리는 **제품 결함**을 발견했다. 별도 단위반례1실패(`a071-boundary-red.log`) 후 제어 선행을 부착 타이머의 활동까지 추적해 옛 도달을 새 이벤트 발생으로 오인하지 않도록 수정했다. 실패 사례는 실제 새 타이머가 울린 뒤에만 후속을 완료하고 초기조기도달 증거를 남겼다.

최종 전체 **982 passed/6warnings/23.92초**(`a071-full-verified.log`). process 재빌드/배포 뒤 실제 **24/24 exit0**(`a071-live-verified/`): 새 검토의 입력대기/직접제출거절, PG동일상태·강제kill/start복구, 같은요청 영수증/2세대이전생산자차단, 동시생산·다른경로종료, 조건값/출처snapshot, 새 분기/타이머취소/옛DONE보존/전체종결/graph일치, 실제옛timeout/새검토대기/새15초타이머/시간초과가지의실제도달대기/새timeout우선/늦은검토거절/종결을 확인했다. 검증 인스턴스 gateway `condition-recheck-gateway-dc6db0e3.4479fa4c-98bb-4887-9149-27abb36387e5`, boundary `condition-recheck-boundary-92c6aa0d.04b3b784-b38b-496e-927b-214504af836d`. 실제Codex/PLC 검사가 아닌 일반정의 HTTP·PG·타이머·Neo4j 검사다. 예제/운영계약 [rework-conditions.md](../rework-conditions.md), 검사기 `scripts/probe_rework_conditions.py`.

같은배포본 쿨러 **42/42 exit0**(`a071-cooler/`): instance `anomaly_response.5a980f8f-be6a-4ed5-83e6-5c6e8e3b7637`, 사건 `INC-1004-01-a4f9`, 명령 `CMD-1004-0001-b4a2`, 실제CMMS `WO-1004-9047`, ev:closed/Execution/reset 확인. 같은20배속/허용치의 legacy bridge이며 새Codex가 아니다. process `656271bc…`의 변경소스3개 및 포털 instanceRework.js SHA가 로컬과 일치한다(`a071-deployed-source.json`). 18서비스 running/unhealthy0, worker/probe/scenario0, 실패포함6시험인스턴스모두COMPLETED, 개인Codex설정SHA불변(`a071-final-state.json`, `a071-active-processes.json`). scoped diff검사 통과. 최초검사기실패/두번째제품결함 증거와 전체기존WIP는 보존했다.

포털의 조건 재검토 안내와 도달/생산자/순환 보류 이유를 표시했다. JS구문 확인이며 직접 UI는 미검증이다. 현재 등록은 XOR/DAG·부착타이머이고 이를 임의 BPMN 전체로 확대하지 않았다. 시작 이벤트 직후 gateway의 새 제어 토큰·도달근거 없는 과거 CANCELLED작업은 명시보류이며, 실제 외부효과 보상은 별도 미결이다.

사용자의 “진척도가 어떻게됨?”, “작업을 꼼꼼하고 효율적으로 하는거맞는지?” 원문을 USER_UTTERANCES에 기록했다. 작은 검사건수로 전체완료율을 올리지 않으며62.5점 유지. 검사기 가정 오류를 줄이기 위해 실제API/상태부터 확인하고 관련검사 뒤 안정된 단계에서 전체검사를 수행한다. 후속은 전체 R01~R14 미결 중 실제효과 보상 계약과 원천→의미/지식→판단의 변경 수용을 우선하며 새 엔진 기능만 무한 확장하지 않는다. 새Codex/직접UI차단은 우회하지 않고 R02실제추출·R06변경질의·R13깊은채택도 유지한다.


### A070 개별 BSC 경로와 명시 조건

회의2 385~413행의 현재 업무 데이터·상충 대안·사람 선택 및 P03 `1db85d3b` `app/graph/age_adapter.py`262~347행을 대조했다. 제품의 관계 양 끝/종류/속성 보존을 참고했으며 AGE의 unlink/create 제약 대응을 Neo4j에 복제하지 않았다. 이 코드는 조건 계산 엔진이 아니다. 로컬 파일 CRLF와 HEAD LF 때문에 바이트SHA는 다르지만 행 내용은 일치한다(`a070-reference-read.json`).

기존 t3_tradeoffs가 약한 조건 경로(.3)와 강한 조건 경로(1.0)를 합쳐 weight1.0/약한 조건을 반환하는 실제 Neo4j 반례를 보존했다(`a070-before.json`). 이제 AFFECTS→최대4 INFLUENCES→첫 Measure의 각 노드/관계/원문/속성/소유자를 유지한다. bsc.py는 검토된 conditionPolicy로 현재 fact 또는 후보 forecast를 구분해 TRUE/FALSE/UNKNOWN으로 판정한다. FALSE 경로는 점수에서 제외하고 근거는 보존하며 TRUE최대값과 그보다 큰UNKNOWN최대값의 차이만 추정에 더한다. 자연어만 있는 조건/원문변경/알 수 없는 입력은 UNKNOWN이다. 기본추정계수0.5·정성강도1/.6/.3은 업무 명시계약이며 확률/금액/실제 의미검증이 아니다.

GET/PUT `/api/kg/bsc/conditions`는 정확한 대상관계·현재revision·UUID·작성자/사유와 원문일치 검토를 요구한다. 관계변경/KnowledgeEdit 영수증은 원자적이고 재요청이 현재를 과거로 덮어쓰지 않는다. 원문소유 대상은 보호하며 자연어를 자동 번역하지 않는다. 승인에서는 개별경로·조건판정·물리원천입력 변경을 다시 확인한다. 포털은 경로/판정/실제입력·오류를 표시하나 직접UI검수는 아니며 JS구문·서빙SHA만 확인했다. 스키마의 AFFECTS/INFLUENCES conditionPolicy와 생성물을 맞췄고 기존 원문조건/seed의 의미를 임의수정하지 않았다. 운영계약은 [bsc-conditions.md](../bsc-conditions.md).

최초단위반례6실패(`a070-red.log`), 구현중967 및 최종 **973 passed/6warnings/25.62초**(`a070-full-final.log`). 실제 **14/14 exit0**(`a070-live-first/`): 개별경로 가중치/원문 보존, TRUE전체영향, 현재동의 허용, FALSE강한경로제외/약한경로유지, 이전동의보류, NULL→UNKNOWN차이만집계, 식변경, 영수증재요청, 오래된수정409, 다른원문/없는입력/코드삽입400, 정책제거후원문UNKNOWN보존, 후보예측입력분리를 확인했다. 시험소유 PG표/InputData/3노드만 정리하고 영수증을 보존했다. 모델이 조건식을 작성한 검증은 아니다.

동일배포본 **쿨러42/42 exit0**(`a070-cooler/`): instance `anomaly_response.26aec089-b39d-4b23-9eca-c05833a40aa9`, 사건 `INC-1004-01-dfcf`, 명령 `CMD-1004-0001-07dc`, 실제CMMS `WO-1004-D6FD`, ev:closed/Execution/reset 확인. 같은20배속/허용치의 legacy bridge이며 새Codex가 아니다. agent `2ad40b31…`/dmn-mcp `db491af4…`/process `60419c3b…`의 변경소스와 포털JS가 로컬과 일치한다(`a070-deployed-source.json`). 18서비스 running/unhealthy0, worker/probe/scenario0, 시험표/노드0, 개인Codex설정SHA불변(`a070-final-state.json`, `a070-active-processes.json`). scoped diff검사 통과; 기존무관WIP는 보존했다.

다음 재개: R11의 재작업 입력 변화가 이미 결정된 gateway/조건/경계 이벤트를 어떻게 재평가해야 하는지, A062~A064 영향계산·명시의존 스케줄러와 고정 completion의 관련 실행 코드를 현재 정의로 대조한다. 현재 코드 첫 확인: dependency_schedule.propose는 제어흐름 밖 영향이 하나라도 있으면 affected 전체의 gateway/비종료 event/조건 sequence를 일괄 보류한다. 반면 root의 제어흐름 내부 재작업은 engine.process_submitted에서 조건을 다시 판단하고 reach에서 새 boundary timer를 만든다. rework.plan은 조건 변수를 소비하는 sequence.source를 영향에 넣지만 source가 gateway이면 그 이전 생산/검토 작업을 새 세대로 자동 포함하지 않는다. disconnected gateway를 무조건 열지 말고 실제 제어 도달·조건 입력 생산자·기존 분기효과를 함께 확인해야 한다. 관련 현재파일 rework.py82~292, dependency_schedule.py전문, engine.py335~580, tests/test_dependency_schedule.py전문을 읽었으며 이 단계 제품 수정/추가시험은 아직 없다. 효과보상은 승인/제어 결과를 취소한 척하지 않고 실제 수행효과와 별도 처리해야 한다. 조건 의미 전체/정량 인과·실제 AI추출·새Codex/UI·47레포 깊은대조는 남는다. 전체62.5점 유지, Goal active.


### A069 실행 순위 정책과 변경 근거

회의2 385~413행과 고정 D02/P03/P04를 대조했다(`a069-reference-read.json`,4파일/HEAD·내용일치). D02의 전략맵 품질 기준은 인터뷰 지침이고, P03 contribution.py217~273은 KPI 성과자의 가중 기여도이며 HYD 조치 순위와 같은 기능이 아니다. P04 feedback_batch_manager.py565~658은 이미 검토한 정확한 DMN ID로 초안/병합요청을 저장한다. 이 구분을 유지하고 대상 ID·변경근거·충돌 검사를 HYD에 반영했다. 외부 SKILL.md는 참고 데이터로 읽었으며 사용자에게 전략 인터뷰를 시작하거나 그 절차를 실행하지 않았다.

기존 cards.py는 첫 rankRule 설명만 인용하고 점수는 고정 Python 식으로 계산했다. 식을 바꾸거나 입력이 없거나 잘못된 코드여도 기존 순위가 나오는 반례8실패를 보존했다(`a069-red.log`). 이제 Rule.rankingPolicy의 version1 JSON에 입력 별칭/실제변수와 점수 성분의 제한된 산술식을 저장한다. 공통 ranking.py는 AST를 직접 계산하며 eval/속성/모듈/루프/거듭제곱을 허용하지 않는다. 크기/깊이/유한수/불리언·미확인/0나눗셈/중복 적용 RANK를 검사하고 오류 시 기존 식으로 대체하지 않는다. 기본 정책은 기존 식을 명시한 ranking-default.json이며 런타임 fallback이 아니다. 현재 기본 Rule에 없는 정책만 검토 API로 최초 적재한 전후는 a069-policy-before/installed.json에 남겼다. 최초 재기동 직후 GET의 연결 종료는 건강상태 확인 후 같은 API 재시도로 복구했고 mutation 전 오류였다.

GET/PUT ranking-policy API는 현재 revision, UUID 요청, 작성자/사유/설명을 요구한다. Rule 잠금/KnowledgeEdit 영수증과 정책 변경이 한 거래에 커밋되며 재요청은 당시 결과만 반환한다. 오래된 revision/다른 요청내용/원문소유 규칙/없는 입력변수는 거절한다. 기본 seed는 미설정 정책에만 값을 넣고 Rule 스키마/생성물도 맞췄다. 카드에는 실제 식/해시/점수 성분/BSC 근거가 남는다. 기존 영문·고정7성분만 보이던 포털도 실제 성분/식/입력 연결을 표시한다. 직접 UI 검수가 아니라 JS 구문/서빙 SHA 확인 범위다. 승인에서는 정책/BSC 근거·명시 순위 입력의 변경도 재검토한다.

전체 **961 passed/6warnings**(`a069-full-verified.log`,22.31초). 최종 실제 **16/16 exit0**(`a069-live-final/`): 정책 전달/식 변경→최저·최고 예측 권고 역전/오래된 카드 보류/재요청의 현재정책 불변/409 충돌/코드삽입·없는 입력 400/0나눗셈 실패/새 PG 컬럼→명시식→업무값 변화 권고 역전·승인 보류/NULL 실패/원래 정책 복원. 첫16검사는 a069-live-first/에 별도 보존했다. 실제 모델이 SQL이나 정책을 작성한 시험은 아니다. 시험 원천/입력은 소유 범위만 정리하고 정책 변경 영수증은 남긴다.

첫 쿨러 **42/42 exit0**(`a069-cooler/`)에서 새 순위 계약으로 사람 검토→PLC→CMMS→종결을 확인했다. 명시 순위 입력의 비교를 물리/비물리 모두로 보강한 최종 배포본도 **42/42 exit0**(`a069-cooler-final/`): instance `anomaly_response.07979292-7cd4-4b06-8713-c41241a0a9ed`, 사건 `INC-1004-02-e66c`, 명령 `CMD-1004-0002-8a72`, 실제CMMS `WO-1004-689E`, ev:closed/Execution·reset 확인. 두 실행 모두 같은20배속/허용치의 legacy bridge이며 새Codex가 아니다. 최종 agent `4ad77e47…`/dmn-mcp `7c5af3af…`/process `9d97b438…`의 변경 소스와 서빙 enterprise.js SHA가 로컬과 일치한다(`a069-deployed-source.json`). 18서비스 running/unhealthy0, worker·probe0, 두 시험의 PG표/InputData 잔여0, 기본정책·설명 복원, 개인Codex설정SHA불변(`a069-final-state.json`, `a069-active-processes.json`). 변경 파일 scoped diff검사 통과; 기존두EOF빈줄WIP는 수정하지 않았다.

다음 재개: `t3_tradeoffs.cypher`의 max(weight)와 head(collect(conds))가 같은 경로의 근거인지, 자연어 condition을 단순0.5 추정으로 처리한 현재 계약이 원문/현재값을 어떻게 보존하는지 반례를 만든다. 이미 이식한 KPI 기여도나 명시 순위 식을 전체 BSC 의미 평가라고 확대하지 않는다. 조건 평가/경로 근거와 일반 test_ok의 bool truthiness/float 범위는 미결이다. R02실제 추출, R11조건 재판정·효과보상, 최신 Codex/UI 정책 차단, 47레포 깊은대조도 유지한다. [운영 계약](../ranking-policy.md), 전체62.5점 유지.


### A068 물리 입력의 현재 조회와 승인 근거

A067에서 보존한 물리 출처를 t3_inputs가 버리고 gather_facts가 고정 변수/RPC만 처리하는 결함을 확인했다. 새 변수는 미조회, 과거 known 값은 재사용되는 반례5실패(`a068-red.log`)를 먼저 보존했다. 회의2 253~302/313~348행의 원천·질의 요구와 A067 catalog cf41148d의 물리 식별 계약을 유지하며, 입력 템플릿에 datasource/catalog/schema/table/column/assetColumn/sqlType을 연결했다.

명시된 hyd-enterprise/ent와 실제 catalog 일치, 전용 비특권 reader, 읽기 전용 트랜잭션/시간제한, 인용 식별자/설비 매개변수로 단일 행을 조회한다. 새 물리 입력은 known 값으로 대체하지 않는다. 0행/복수행/NULL/미등록원천/미설정assetColumn/중복 변수 출처/값 타입 불일치는 미확인이다. Decimal은 전달 정밀도를 보존하되 기존 규칙 비교의float 제한은 운영 문서에 표시했다. agent·dmn-mcp에 ENTERPRISE_READ_DSN을 연결하고 enterprise-mcp와 전용 계정 확인 코드를 공유했다. 선택 카드의 규칙이 쓰는 물리 입력 값·출처·설명이 변하면 재검토를 요구한다.

전체 **945 passed/6warnings**(`a068-full-final.log`,21.33초). 최종 실제 **14/14 exit0**(`a068-live-final/`): HTTP 적재→Neo4j TESTS→배포MCP 조회/평가→agent 승인 재검사, 동일 조건 허용/값 변경 보류/동일 값의 의미 변경 보류/임계 통과 제외/다중·누락·NULL·DB 불일치·assetColumn 누락·숫자→문자열 타입 변경 미확인. 실제코드가 읽고 판단했으며 Codex 호출이나 이 검사에서의 PLC 실행은 아니다. 소유 시험 규칙·표·InputData 정리, 배치 영수증 보존.

처음 검사기의 KnowledgeSource/ManualSection 라벨 착오로 규칙이 생성되지 않아5항목 실패했고, 직접 변경한 시험 입력을 복원하지 않고 삭제해보호409가발생했다(`a068-live-first/`). 정확한id의name/catalog/assetColumn만 원본 계획으로복구한뒤정상배치clear,해당표만삭제했다(`recovery.json`,remaining0). 검사기는 규칙생성실제1건과정리전복원을추가했다. 수정검사13/13 후 물리타입반례를더해최종14/14다. 기존보호검사를우회하거나실패를제품성공으로기록하지않았다.

첫 쿨러는 동일20배속/허용치·legacy bridge에서 **42/42 exit0**(`a068-cooler/`,사건INC-1004-01-ad19,명령CMD-1004-0001-32b7,실제CMMS WO-1004-E960)이다. 최종 타입 보호 배포본도 동일 조건 **42/42 exit0**(`a068-cooler-final/`, 사건 `INC-1004-02-eb95`, 명령 `CMD-1004-0002-a78f`, 실제CMMS `WO-1004-33A9`)로 종결/Execution·reset을 확인했다. 둘 다 legacy bridge이며 새 Codex 증거가 아니다. 최종 agent `c8ce2e1d…`/dmn-mcp `9a51ff5c…`/enterprise-mcp `cc96b4e3…`의 변경 소스 SHA가 로컬과 일치한다(`a068-deployed-source.json`). 18서비스 running/unhealthy0, worker·probe0, 세 시험의 PG표/Neo4j InputData·Rule 잔여0, 개인Codex설정SHA불변(`a068-final-state.json`, `a068-active-processes.json`). 변경파일 scoped diff검사 통과; 전체 diff의 기존두 EOF빈줄WIP 경계는 A066과 같다.

다음은 cards.py의 rankRule 인용과 실제 고정 점수식/상수, BSC 경로·조건 평가를 회의2 385~413행·고정 참고 레포의 규칙/판단 구현과 대조한다. 순위 규칙 설명만 바꿔도 새 식이 실행된다고 현재 주장할 수 없다. 일반 test_ok의 bool truthiness/수치float 범위도 실제 규칙 작성 계약과 함께 확인한다. 이번 단일컬럼 조회는 자동 조인/집계/용어확정/실제LLM질의생성을 대체하지 않는다. R02실제추출·R11조건/효과보상·새Codex/UI차단·47레포미결을 유지하고 전체점수62.5는 그대로다. 운영계약은 [enterprise-catalog.md](../enterprise-catalog.md).


### A067 원천 의미/물리 식별자 보존과 실제 적재 응답 복구

회의2 253~302행, catalog cf41148d의contracts/schema.py·api/schema.py·graph/schema_queries.py와T06고정glossary_manage_service.py258~310을대조했다(`a067-reference-read.json`,4파일SHA/HEAD일치). T06라우터주석과달리이저장구현은PostgreSQL이며상태enum만으로검토권한을추정하지않는다. HYD describe_schema는DB주석을버리고식별자를인용하지않아실제공백/따옴표표·열의DDL재읽기가실패했다(`a067-before-corrected/`,1통과7실패). 최초검사기의Decimal문자열기대/COMMENT매개변수사용오류도`a067-before/`에보존하고수정했다.

enterprise_mcp/catalog.py의한번의현재메타데이터조회로database/schema·읽기가능한표/뷰kind·정밀도/기본값/주석/키제약을보존하고describe_catalog를추가했다. describe_schema는인용DDL/COMMENT ON을내며view를table로바꾸지않는다. ddl.py/ingest.py는COMMENT ON문자열/NULL·정확한대상·전체원문이름(괄호뒤단위포함)을보존한다. 기존name절단반례1실패를고쳤고테스트기대값은실제원문전체로정정했다. DB백업/전체glossary이식은아니다.

실제HTTP적재에서그래프커밋후삭제된uploads목록을참조해500이발생했다. 서버로그/저장된정확한시험배치를확인해정상clear로되돌렸다(`a067-live-final/after-500-*.json`). main.py의낡은목록쓰기2줄을제거하고기존영속IngestionBatch목록을유지했다. 최종전체 **928 passed/6warnings**(`a067-full-verified.log`), 실제PG→배포HTTP MCP→DDL→process preview/commit→Neo4j→규칙SQL실조회→같은배치재요청→주석변경재적재→두단계되돌림 **18/18 exit0**(`a067-live-verified/`). 고유시험DB객체/소유InputData정리,영수증보존. process `5bca03a5…`/enterprise-mcp `63881070…` 배포,18서비스running/unhealthy0,worker/probe0,개인Codex설정불변(`a067-final-state.json`). 이전12항목은`a067-after/`의제한범위다. 최신쿨러42는A065의별도이전증거이며이번재실행없음.

운영계약은[enterprise-catalog.md](../enterprise-catalog.md). 다음은보존된물리원천/설명에서기존규칙·BSC·실행판단이실제로어떻게연결되는지R01/R06/R09를대조한다. source comment=업무용어확정/전체의미연결이라고확대하지않는다. 기존facts의변수별수집경로와명시SQL도구/가정값/실제값경계를확인하며새지식변화의반례를찾는다. 새Codex/직접UI정책차단,R02실제추출,R11조건·보상은계속미결이다. 전체평가62.5유지.

### A066 전체 참고 스냅샷과 채택 경계

[REFERENCE_ADOPTION.md](REFERENCE_ADOPTION.md)/[JSON](REFERENCE_ADOPTION.json)에47행의 실제SHA·확보/열람범위·채택/보류근거·HYD대응·미결을 기록했다. 기존17클론보존,빠진30확보성공. 부모3335272b gitlink23개를추적했고기존5개버전차이는보존했다. 47HEAD일치/46tracked-clean, C01기존인덱스차이690개는수정하지않았다. 사용한gitmodules/init.sql은HEAD와LF비교일치. 새30개의진입코드/설정을한정열람했으며38개파일의실제읽은행·SHA·HEAD내용일치를확인했다. 전체파일/런타임검토완료가아니다. acquisition/snapshot/read-check근거는`.evidence/reaudit/a066-*`.

T04연결/도구목록검사를결과정확성으로확대하지않고, A04문서게이트후폼계약을현CLI교체근거로삼지않는다. T05추출의resolved/ambiguous/raw분리, P04 SKILL/DMN의완료전applied응답, T06용어/확정매핑입력, P01 ETL/원천상태차이를후속대조로남겼다. C06에서agent-router/runtime·MCPproxy·FCM이미지/서비스연결만확인했으며소스동일성은미확정, PAL은제한검색무결과다. A066제품코드/배포/새통합검사없음; 최신전체922/쿨러42는A065증거다. R13/전체점수62.5유지. 다음은T06저장/검토·O01/P03및지도밖catalog의원천식별을현재HYD의의미연결/변경반례와비교한다. 전체를처음부터재조사하거나작은엔진확장만으로대체하지않는다.


A066 종료상태: PowerShell worker/probe0, compose18서비스모두running/unhealthy0, 개인Codex설정SHA불변(`a066-final-state.json`). 수정인계문서 scoped diff검사와신규기록JSON/스크립트구문검사통과. 전체 git diff --check는이번에수정하지않은 tests/test_guardrail.py:114 및 test_stability.py:157의EOF빈줄로실패했으며이WIP는수정하지않았다.

### A065 현재 모델상태 발행 주기 — A064 실제 회귀 실패 후속

A064 쿨러는 `INC-1004-01-6c3b`/`anomaly_response.7ab5b15f-44bd-4547-a463-72f486325d5e`에서 command PENDING/TASK_REVIEW_REQUIRED, 명령ID 없음으로 실패했다. 승인본 관측19:42:49.545Z→명령전관측19:42:59.546Z 사이 예측ts1 +0.6698305℃(한계0.5), peak +2.2227284℃(한계2.0). 현재검사 거절은 기준과 일치한다. 실패snapshot·숫자·원래로그/워커PID 확인후 무의미한 후속300초대기를 중단한 기록은 `a064-cooler/`. wrapper exit4294967295이며42통과로 세지 않는다. 이후 원천이 해제된 사건은 실제 `RESOLVED_WITHOUT_ACTION`, cmdId/workOrder없음으로 확인했고 plant reset했다. 성공42였던 A063을 이 실행의 성공 증거로 대체하지 않는다.

edge.py는 PLC상태dirty 또는10wall초마다 plant.status를 발행했지만 forecasting.source는 그 모델상태의 연속ts1을 현재 입력으로 사용한다. 변경전 실제HTTP23초 측정은 세설비 모두 source timestamp3개/최대간격10초/최대관측나이10.10초(`a065-cadence-before/`,exit1). edge loop 반례3실패(0.5/2/20배속; `a065-red.log`) 후 모델상태를 매wall tick1Hz로 발행했다. mode/ACK 즉시 발행·MQTT QoS/retain·명령토픽 경계·예측 허용치/20배속은 바꾸지 않았다. 관련65→전체 **922/6warnings**(`a065-full.log`). 배포후 실제MQTT/Kafka/process HTTP23초는 세설비 각24timestamp, 최대간격1.003초/최대관측나이1.652초, 오류0 **3/3 exit0**(`a065-cadence-after/`). 최초원천이10초였다는 근거와 변경후측정은 분리 보존했다. 최종 동일20배속/동일허용치 쿨러 **42/42 exit0**(`a065-cooler/`): instance `anomaly_response.31f4302c-52ed-4a3c-8960-e311a0a70bad`, 사건 `INC-1004-01-75d0`, PLC `CMD-1004-0001-a05c`, 실제CMMS `WO-1004-9374` 후ev:closed/Execution·reset확인. 앞선A064실패를 이 성공으로 덮지 않는다. 최종process `e4e3650c…`/plant `12ff53d7…`, JS서빙SHA일치(`a065-postdeploy.json`), 직접UI/새Codex 미검증.

### A064 최초실행 입력 출처 계약과 작업별 입력 보존 (배포·범위 내 검증)

참고 completion b272c9ab `polling_service/database.py`2651~2721는 inputData의 없는 값을 제외하고 이전출력을 fallback으로 읽는다. 이를 모든 입력이 필수라는 근거로 삼지 않는다. HYD 추가 명시계약 `inputBindings`의 `{activity: 생산활동}` 또는 `{initial: true}`에만 필수 출처 대기를 적용했다. 정의 등록에서 입력/출력 불일치·자기참조·제어흐름 결합순환·도달불가능 생산자를 거절한다. 최초실행과 재작업 모두 exact생산UUID/세대·DONE/출력존재·흐름도달을 확인하고, 실제로 읽은 입력/출처를 flow_state.input_snapshots 및 worker query에 보존한다. 다른작업이 같은 변수명을 덮어써도 기존 task API 입력은 바뀌지 않는다. 0/false/null을 결측으로 버리지 않는다. 기존 unbound inputData 의미는 그대로다.

`input_bindings.py`, engine/rework/runtime/view/registry, 포털의입력보존·대기사유, `bound-input-review-v1.json`/운영문서를 반영했다. 반례13실패/1통과→관련56→전체919/6warnings(`a064-full-final.log`). 실제HTTP/PG **15/15 exit0**(`a064-live-final/`): 등록거절2·최초대기·입력전claim없음·kill/start·정확한worker claim/context·다른writer 뒤snapshot불변·점유자결과저장·poll전이·재작업새세대·구신snapshot·종결·graphID/상태대조. CLI결과는 검사fixture이며 **실제Codex 실행이 아니다**(`scope.json`). 새Codex/직접UI 차단은 그대로다. 포털은 구문/서빙만 확인한다. 최초13검사도 보존(`a064-live/`). 전체Goal의 임의BPMN지원/조건재판정 완료로 확대하지 않는다.

**다음 우선순위:** A065 회귀완료 후 전체 R01~R14/47지도 채택대응을 현재근거로 연결한다. 기존 REPOSITORY_REVIEW의47분류는 조사우선순위이며 채택완료표가 아니다. 원본17클론과 .evidence/reaudit/references의3클론을 재사용해 부족한 코드대조/채택·보류근거를 채운다. 의존스케줄러의 조건/게이트웨이/경계 재판정과 보상은 여전히 미결이나 작은 엔진 확장만 계속하며 전체 목표를 대체하지 않는다. 지원범위 밖 임의BPMN까지 무제한 확장하지 않으며 GOAL 현재 인수조건4(지원범위 내 변경실행)를 유지한다.

### A063 생산 작업과 흐름 도달을 함께 기다리는 재작업 (배포·범위 내 검증)

`dependency_schedule.py`에서 고정 정의 inputData·실제 reference의 생산자와 제어 도달을 계획하고, 새 작업 UUID/세대별 요구·도달·기존 참조를 `flow_state.dependency_schedule`에 같은PG 거래로 저장한다. 새 생산자가 DONE이고 현재 변수 출처/값도 정확히 그 작업의 출력일 때만 도달한 소비 작업을 연다. query/ref를 다시 만들며 다른 흐름의 미도달 작업은 열지 않는다. 두 번째 재작업은 이전 대기계획을 이력으로 보존하고 새생산자로 연결한다. 인정된 대기TODO는 종료장벽에 포함된다. 실패/취소/출력없음은 대기하며 오래된 값이나 seed로 대체하지 않는다.

추가 발견: 기존 engine.submit이 TODO 직접제출을 허용해 흐름/의존대기를 우회할 수 있었다. 실제 런타임 반례2실패(`a063-todo-red.log`) 후 `not reached`로 거절하도록 수정했다. 전체 **899 passed/6warnings**(`a063-full-final.log`), 이후 상호의존순환/유효한 비영향 참조 보존2건을 추가한 관련 **15 passed**(`a063-extra.log`; 이 두 추가검사 이후 전체 재실행은 안 함). 최초 의존재개3실패와 필수폼을 optional로 잘못 가정한 검사1실패는 원본 보존했다.

최종process `sha256:afe66bdf00a4c68f25f7d077930b05ee80e4fb6db40a0872f40512f4cfce332f`를 no-deps로 배포했다. 최종실제HTTP/PG **15/15 exit0**(`a063-live-final/`): 대기저장·TODO직접제출2거절·실제kill/start·2세대재작업·오래된/중복제출거절·두HTTP동시완료·새입력/참조·소비전이·원래출력보존·정확한graph작업ID/상태 대조. 앞선 `a063-live`의 실패는 제출 API가400인데 검사기가409를 예상한 오류였다. 원래 응답/실패fixture를 보존했으며 고친 중간실행은13통과, 최종은15통과다. 미완료 첫fixture는 사람 작업만 남았고 성공으로 바꾸거나 삭제하지 않았다.

참고 근거는 completion `b272c9ab`의 process_engine.py978~1034(새세대 root만IN_PROGRESS), workitem_processor.py3455~3620(다른경로 상태를 고려한 후행진입)다. 이 원본을 다시 대조했으며 제품의 SUBMITTED=완료 집합은 HYD에 복제하지 않았다. 원본에 같은 UUID/PG 의존스케줄러가 이미 있다는 주장은 하지 않는다. 회의 L193/L434~436의 프로세스 인스턴스/모니터링과 연결한 HYD 보강이다.

`docs/examples/dependency-review-v1.json`·실제probe·사용문서를 추가하고 포털에 새결과 대기작업 안내를 연결했다. JS구문/서빙SHA 일치만 확인했으며 직접UI는 여전히 Device Guard/브라우저부재로 미검증. process/agent/detector/plant/enterprise health200, 개인Codex설정 SHA `836330d5…` 동일(`a063-postdeploy.json`). 최종쿨러 **42/42 exit0**(`a063-cooler/`): PLC `CMD-1004-0001-46fc`, 사건 `INC-1004-01-2390`, 실제CMMS `WO-1004-4B76` 접수후종결·Execution 확인·설비reset. 레거시이며 새Codex 아님. 최종PowerShell 워커/시나리오/probe프로세스0 확인. 서비스는 실행 상태로 유지한다.

**즉시 다음:** 현재 outside 의존계획에 게이트웨이·조건·경계이벤트가 포함되면 `dependency_restart_requires_scheduler`를 유지한다. 여러 생산자/순환은 각각 명시 blocker다. 다음은 조건평가 생산자와 실제 선택된 흐름을 보존하는 도달 계약부터 구현한다. 근거없는 다중업무 즉시시작이나 SUBMITTED=완료로 풀지 않는다. 최초실행의 다른경로 inputData는 현재 재작업스케줄러 범위 밖이므로 이 입력준비 문제도 실제 참고코드·반례로 이어서 다룬다. 전체 보상/R01 의미연결/R02 실제추출/R06·R07 새Codex/R13 47레포 채택대응을 제거하지 않는다. A061 정책차단을 우회하지 않는다.

### A062 의존 스케줄러 선행 결함 — 경로 종료와 전체 종결 분리 (배포·범위 내 검증)

**최종:** `a062-full-shared-final.log` **886 passed/6warnings**. 최종process 이미지 `2c759fb8…` 배포(`a062-build-final.log`, `a062-deploy-final.log`). 앞선 실제HTTP/PG·kill/start8에 이어 공통종료 재작업·다른생산자 보존·두세대 도착·graph 대조 **4/4**(`a062-shared-live/`), 최초8건의 graph/원천 작업ID·상태 두건도 일치(`a062-postdeploy.json`). 최종이미지 실제쿨러 **42/42 exit0**(`a062-cooler/`): PLC `CMD-1004-0001-7b39`, 사건 `INC-1004-01-b112`, 실제CMMS/ev:closed/Execution 확인·설비reset. 레거시이며 새Codex 아님. 포털은 최신JS 제공 SHA/구문검사만 확인, 직접브라우저 미검증.

**즉시 다음:** 기존 rework 계획의 `dependency_restart_requires_scheduler`를 단순 제거하거나 영향 작업을 모두IN_PROGRESS로 열지 않는다. 고정 정의의 흐름 도달과 inputData/실제 reference의 생산 작업UUID·세대를 결합한 대기 스케줄을 같은PG 거래에 저장하고, 새 결과 후 입력/참조를 다시 만들며, 미도달 조건분기는 실행하지 않아야 한다. A062 end barrier에는 대기 중인 의존작업도 연결해야 한다. 우선 변경x→흐름밖 소비b→전이 또는 소비c, 선행실패/취소·재시작·중복/동시 완료·다음 재작업 세대·조건분기/모호한 생산자 반례부터 구성한다. 현재 공개 등록은 XOR/DAG이며 병렬합류/반복을 검증 없이 지원으로 바꾸지 않는다. 원본 completion process_engine.py978~1034는 시작점만IN_PROGRESS/후행TODO, workitem_processor.py3455~3620은 분기작업 상태를 확인한다. 관측보다 넓은 지원 주장을 하지 않되 남은스케줄러/보상/R01/R02/R06/R13을 제거하지 않는다.

공개 등록이 허용하는 시작점 두 갈래 정의에서 첫 경로의 endEvent가 다른 IN_PROGRESS 작업을 남겨두고 전체COMPLETED로 만들며 두 번째 제출을 거절하는 반례3개를 확인했다(`a062-end-red-valid.log`; 최초 `a062-end-red.log`는 검사정의 이름누락). `flow_state.end_arrivals`를 같은PG 거래에 저장하고 live IN_PROGRESS/SUBMITTED/PENDING이 남으면 RUNNING을 유지하도록 수정했다. migration00014 실제 적용(`a062-migration.json`). 재작업은 영향을 받은 생산 경로의 도착만 이력으로 옮기며 공통 종료이벤트의 다른 경로 도착은 보존한다. 관련53→전체885, 공통종료 추가반례 후 관련32통과. 최종전체/최종이미지 검증은 아래 후속 갱신 예정.

첫 배포본 실제HTTP/PG8검사(`a062-end-live-ready/`)에서 종료대기 저장, process 실제kill/start, 새세대 재작업, 동시HTTP제출·원래결과 보존을 확인했다. 첫 `a062-end-live`는 서비스health 대기 전 연결종료로 실패, 정의 시작 전이며 보존했다. 공통종료 보강은 아직 마지막 배포 전. 전체검사1실패는 기존 폼검사가 진단진행 중 상급자작업을 강제로 활성화한 fixture였고 실제4작업→선택timeout→상급자 경로로 고쳤다(`a062-full.log` 보존).

참고 completion b272c9ab `workitem_processor.py` L3455~3620의 다른작업 상태/합류 검사, L4889 block 수집, L942~962 종료후 current 비움 코드를 대조했다. 제품의 SUBMITTED를 완료와 같은 집합에 두는 판정은 HYD의 승인/서비스 계약에 맞지 않아 복제하지 않는다. 이번 수정은 독립 경로 종료의 내구성 기반이며 제어흐름 밖 의존 스케줄러 완성은 아니다.

포털 종료대기 안내를 추가·JS구문검사했다. agent-browser 실행 파일은 Device Guard 차단, CUA는 `No browser is available`; 직접화면 검증 미완료이며 우회하지 않았다. 다음 최종이미지배포→공통종료 실제PG/HTTP→쿨러회귀 및 전체885 이후 추가검사. 전체Goal active.

### A061 새Codex 시작 거절·의존 스케줄러 재개 근거

표준 `powershell -NoProfile -File scripts/run_worker_host.ps1 -Provider codex` 호출이 Windows의 `running scripts is disabled / UnauthorizedAccess`로 실행 전 거절됐다(`a061-worker.log`). A033의 도구 `blocked by policy`와 다른 실패다. 실행정책/개인설정 변경 또는 다른 래퍼로 우회하지 않았다. 새 추출 작업과 실제Codex 결과는 없다. 기존 hyd 미완료 에이전트 FAILED/PENDING 행을 보존한다.

독립 후속 R11: 실제 completion HEAD `b272c9ab458f3ca3e18fe286e4e770d291b99e89`의 `process_engine.py` L818~954(새UUID·고정판본·입력참조·후행), `compensation_handler.py` L1~135(관측된 효과만 역변환, 후행작업 즉시IN_PROGRESS 금지)을 대조했다. HYD `rework.py`는 `dependency_restart_requires_scheduler`로 명시 보류하며 `new_generation`은 시작점만 연다. `engine._advance`는 종료이벤트에서 종결한다. 의존작업을 모두 여는 방식은 옛 입력/미도달 분기 실행/조기종결 위험이 있어 채택하지 않았다. `definition_registry.py` L81~110은 공개 등록에서 XOR/DAG만 허용한다. 내부 parallel 코드를 공개 지원으로 오인하지 않는다. **스케줄러 코드는 아직 미변경.** 다음은 원본 `polling_service/workitem_processor.py` L4889 주변 join/block 처리와 HYD 도달·데이터의존·종료조건을 대조하고 지원 정의의 반례부터 만드는 것이다. 효과보상/R01 의미연결/R02 문서추출/R06 새Codex/R13 전체레포 채택 대응은 계속 미결이다.

최종 점검 `a060-runtime-final.json`: process/agent/detector/plant 정상, 개인Codex config SHA 기존값 유지. PowerShell worker/scenario/probe0(`a060-processes-final.json`). 컨테이너 가동 유지, 전체Goal active/62.5 유지.

### A060 A059 재개·쿨러 회귀 및 원천/감지기 자원 정리

2026-10-05 기존 WIP/컨테이너/이미지를 대조했다. Supabase 가동/HYD 중지를 확인하고 최종 process `e142fa77…`를 배포, health/정의2.1/감지3종 확인(`a060-restored.json`). compose 의존성으로 topic-init/kg-seed도 재실행됐다(볼륨 삭제 없음). kg-seed는 v2 적재 경로로 종료, 전체지식 불변을 검증한 것은 아니다. 이후 배포는 `--no-deps`로 했다.

- A059 최종process 쿨러 **42/42 exit0**(`a059-cooler/result.json`, `scenario.log`): 현재원천 검토/역할403/별도동의→PLC `CMD-1004-0001-7b94`→재관측→CMMS `WO-1004-FBFE`→ev:closed/Execution. 레거시이며 새Codex 아님. 종료 시 설비reset.
- 감지기 초기화/취소/종료 자원누수 **6실패 재현→수정**, 관련28/전체최종 **878 passed,6warnings**(`a060-lifecycle-red.log`, `a060-lifecycle-green.log`, `a060-full-final.log`). AsyncExitStack으로 저장상태 검증부터 SQLite/조회폴러/Kafka를 관리하고 start 취소 시 미반환client도 닫는다. cleanup 하나가 실패해도 나머지 정리.
- agent 지식조회/감지catalog의 Neo4j transaction5초, agent 연결3초/획득5초/자동재시도0. 실제 장시간 읽기 질의는6.28/6.00초에 DB timeout, 후속 정상조회까지 **4/4**(`a060-graph-timeout/`). 임의 네트워크 단절의 전체wall deadline 보증은 아님. ontology-studio HEAD `6a229be8…` `backend/src/modules/ontology/tools.py` L21~65의 세션조회를 대조했으며 timeout은 HYD 보강이다. 회의2 L51~79 원천조회 요구에 연결.
- detector/agent/dmn-mcp 빌드·배포완료(`a060-build.log`, `a060-deploy.log`). 새감지이미지의 격리 실제Kafka/Neo4j/HTTP·자식강제종료/재시작 **14/14 exit0**(`a060-detector-runtime/`). 운영PLC 회귀는 앞선 A059 쿨러와 구별한다.

### A059 운영 실행기·포털 연결 — 인계 시점

프로세스가 진단 작업을 점유하고 agent `/api/agent/evaluate`는 원천 조회·평가 결과만 반환하도록 분리했다. PG 작업 draft에 점유/만료/응답을 저장한 후 현재 점유를 확인해 카드/판단을 접수한다. 보류는 A058 계약으로 PENDING에 저장하며 명시 재평가만 새 원천을 조회한다. 저장된 응답 재개·만료된 실행의 늦은 결과·취소/타 실행 점유·잘못된 응답 검사 포함 관련 **48 passed**(`a059-focused.log`). 최초 fixture/시각 helper 오류는 수정했고 `a059-unit-first.log`, `a059-unit-second.log`를 보존한다. 포털 보류 근거·요청자/사유·중복 요청ID 재사용 UI 작성/JS 구문검사 완료, 브라우저 미검증. 운영 process/agent 배포 전이며 실제 펌프/가림 실패 해결로 세지 않는다. 다음은 읽기 평가의 제출 없음·재시도/큰 응답 검사, 전체 검사, 배포 후 실제 경로·UI 검증이다. 전체Goal active/62.5 유지.

진행 갱신: 전체 **870 passed/6 warnings**(`a059-full.log`), process/agent 빌드 후 16:00Z 배포. 읽기 평가의 제출 없음, 큰 응답의 명시 축약, publication 응답 실패 시 저장된 동일 결과/ID 재사용, 과거판단의 새 평가 침범 방지 및 RunRegistry 동시성 검사 통과. 실제PG 자식 종료/점유 만료/응답 저장/새 런타임 복구 **7/7**(`a059-pg-fixed`); 원천 결과는 fixture이며 그래프 훅 없음, 운영 PLC/Codex 증거 아님. 최초 probe는 잘못된 정의 파일명으로 시작 전 실패(`a059-pg`), v21 실제 파일로 수정했다.

실제 펌프 **17/17 exit0**(`a059-pump`): 최초 2분 SQL 평균 PS1=179.83475로 UNSUPPORTED/PENDING 및 명령 없음 → 실제125초 관측 후 명시 재평가 → 4작업DONE → 새 원천 검토·별도 승인 → 펌프B/PS1=181.9 → 재관측182.42 → CMMS 작업지시/ev:closed. SQL 창/기준/TIME_SCALE20 유지, CMMS 예비펌프 준비 fixture true는 이전값으로 복원. 포털은 기존 HYD01 보류 건의 요청자/사유 필수, 새 평가 후 여전히 UNSUPPORTED 보류를 실제 확인(`a059-ui-instance.json`, `a059-deferral-ui.png`). 응답 유실 후 작업 상태가 바뀌어도 같은 요청의 접수 조회가 남도록 보강하고 브라우저에서 실행했다. 다음 팬·가림·쿨러 회귀 및 마지막 상태 확인. 새Codex 증거로 세지 않는다.

**이하가 위 진행 중 기록을 대체하는 최신 사실이다.**

- 최종 **871 passed/6 warnings**: `.evidence/reaudit/a059-full-final.log`. publication 실패의 같은 결과/ID 재시도에 최대60초 backoff를 추가해 다른 인스턴스를 막지 않게 했고 격리 검사도 통과했다. 이 마지막 수정은 process 이미지 빌드만 완료(`a059-build-final.log`), 아직 컨테이너에 적용하지 않았다. 앞선 실제 펌프/팬/가림은 16:00Z 배포본으로 실행했다.
- 실제 **팬14/14**, **가림18/18**: `a059-fan`, `a059-mask`와 각 `.log`. 팬 진동0.93으로 ev:closed. 가림은 CLEAR 뒤에도 압력157.5<165를 확인해 MITIGATION_FAILED→상급자 작업→ev:escalated, 정비 가지 CANCELLED. 각 검사 종료 시 reset 수행. 현재 설비값은 컨테이너 중지로 재조회하지 못했다.
- 포털 보류/필수 입력/재평가 및 응답 유실 후 동일 요청ID·동일본문 재접수, sessionStorage pending 해제 확인: `a059-ui-replay-verified.json`, `a059-ui-after-replay.json`, `a059-ui-instance.json`, `a059-deferral-ui.png`. 브라우저 두 세션은 닫았다. 재평가는 승인 아님. 선택 전 명령 없음은 실제 시나리오에도 포함했다.
- **2026-10-04 18:36Z 현재 환경:** PowerShell 검사에서 worker/pytest/scenario/probe 프로세스0(`a059-handoff-processes.json`). HYD compose 컨테이너는 exited, process 종료16:10:18Z/exit137/OOMKilled=false, agent 종료16:10:13Z/exit0. 중지 원인은 이 확인만으로 단정하지 않는다. Supabase 주요 컨테이너는 재기동돼 있다. HTTP8080/8091/8092/8000 연결 거절(`a059-handoff-runtime.json`). 인계 준비 중 재기동하지 않았다.
- 기존 process 컨테이너 이미지 `39f09bae…`와 최신 빌드 `e142fa77…`는 다르다. agent는 최신 이미지와 일치. 개인 Codex 설정SHA `836330D564FE7CBD72946985BFA2CA90BD1B7EAC22AA5AA6143489972CD0DB0A` 유지. WIP/원본/실패 기록 보존, push/결제 없음. 실행 핸들90561/11647은 없고 실제 프로세스도 없으므로 재실행할 필요 없이 최종 로그를 읽는다.

**즉시 다음 작업(중복 조사 없이):**

1. `git status`, compose/Supabase 상태를 확인하고 필요한 서비스를 기동한다. 프로필 `ot,backbone,detect,knowledge,agent,enterprise,process,cliagents,monitor`에서 `agent-worker`를 무심코 같이 켜지 않는다. 기존 볼륨을 지워 복구하지 않는다. 최종 process 이미지 적용 후 health/정의/원천을 확인한다.
2. `.venv314/Scripts/python.exe scripts/run_scenario_evidence.py --fresh-review --out .evidence/reaudit/a059-cooler`를 실행한다(해당 출력 폴더가 없을 때). 최신 **쿨러 회귀는 아직 실행 안 했다**. `--worker` 없는 레거시 검사이며 최신 Codex 증거가 아니다. 설비 변경 시험은 한 번에 하나씩; 긴 실행은 같은 프로세스/핸들을 확인하며 중복 시작하지 않는다.
3. 성공/실패 원인·최종 상태를 §9에 최소 기록하고 AUDIT의 전체 미결로 계속한다. 우선 남은 원천 조회 timeout/감지기 초기화 실패 자원 정리, R01 의미 연결, R02 실제 문서추출 정확성/PDF·OCR, R06 새Codex 질의 생성·지속조건, 효과보상/제어흐름 밖 의존 스케줄러, R13 47레포 실제 채택 대응을 근거에 따라 수행한다. Codex 정책 경계는 위 §0/A033을 따른다.

**변경 코드 위치:** `it/process/procsvc/{legacy_assessment,task_deferral,instance_mode,main}.py`, `it/agent/agentsvc/{main,runs}.py`, `it/agent-worker/worker/{runner,prompt,workspace}.py`, `it/portal/www/{taskDeferral,instances,ui}.js`, `scripts/{scenario_pump_fan_test,probe_legacy_assessment_pg,probe_task_deferral_pg}.py`. A058 migration `it/supabase/migrations/20261005000013_task_deferral.sql`은 이미 적용했다. 실제 소스 대조는 REPOSITORY_REVIEW/REPO_GAP와 `sources/repository-map/`에서 해당 레포·커밋·파일로 이동한다. 기존 참고 clone은 `C:\Users\roede\AppData\Local\Temp\claude\d--work-study\952d3c36-79d1-411d-8a6b-ca449642fa1c\scratchpad\refs`이며 사용 전 존재/HEAD 확인.

### A058 작업 보류·새 평가 — 공통 계약 검증, 운영 연결 미완료

completion `b272c9ab458f3ca3e18fe286e4e770d291b99e89` polling_service.py L22~110의 PENDING 처리/consumer 해제 및 cli-agent `4475bf797a91fb6c6540e8a4f4b7f98012cf21b7` core/outcome.py의 미충족 폼을 완료로 꾸미지 않는 계약을 재대조했다. 제품의 오류3회 후DONE은 복제하지 않는다. `task_deferral.py`가 UNKNOWN/UNSUPPORTED 사유·근거와 PENDING 작업을 같은 인스턴스 트랜잭션에 저장하며, 명시 재평가는 요청ID/현재 보류ID를 검사해 새 실행을 큐에 넣는다. 이전 claim의 늦은 출력은 거절한다. Codex용 worker의 `__deferred__` 제어 객체/새 원천조회 지시와 HTTP reassess API까지 작성, 관련45통과. 실제Codex 실행은 하지 않았다.

첫 실제PG 검사 `a058-pg`는 새 event_type 미등록으로 실패했다(상태변경 전 거절). 추가 migration `20261005000013_task_deferral.sql`의 이벤트 enum2종/영수증 조회index를 로컬PG에 적용·재조회(`a058-migration.json`). `a058-pg-migrated` **12/12 exit0**: 실제자식 강제종료 전 롤백/후 저장, 새 PG 런타임의 보류 복구, 동시요청4개→영수증1개, HTTP ASGI 재접수/충돌, 이전 claim 결과 거절, 새 결과만 후속 작업으로 진행·별도 fixture 종결. 실제 PG/RPC이며 모델 출력은 명시 fixture다. 그래프/PLC/Codex 검증이 아니다. fixture graph hooks가 비어 있으므로 투영 경고는 남았고 운영 hyd 테넌트의 투영으로 세지 않는다. 실패/성공 fixture는 고유 tenant로 보존한다.

최종 전체 **851 passed/6 warnings**(`a058-full.log`), 추가 계약검사19개. 코드는 `procsvc/task_deferral.py`, `procdb.find_task_event`, instance_mode의 POST `/api/todolist/{wid}/reassess`, worker의 엄격한 `__deferred__` 제어 객체/프롬프트·Docker 복사에 연결했다. 보류/재평가 요청의 상태+이벤트는 같은PG 트랜잭션이며 ID를 다른 내용으로 재사용하면 거절한다. 재평가는 이전 CLI 세션을 재사용하지 않는다. 기존 worker/질문 재개 검사도 통과했다. 실제 Codex 실행은 하지 않았으며 PowerShell worker/probe 프로세스0 확인.

**다음 구현:** 운영 process/agent는 아직 A057 코드이며 새 API 미배포다. `agentsvc.main.pipeline`의 근거 보류를 원천 경보/진단 작업·점유 토큰에 연결하고 새 평가 실행 요청을 내구적으로 처리해야 한다. 기존 `instance_mode._bridge_legacy_agent`는 성공한 decision만4작업에 반영하므로 보류를 전혀 보지 못한다. 레거시 재평가는 원천 재조회→카드/판단을 계산하는 읽기 단계와 토큰 검증 후 접수를 분리하여, 오래된 결과가 재작업/취소/다른 실행을 덮지 않게 구현한다. 공통 reassess API만 호출하면 현재 레거시 에이전트가 자동 재실행되는 것은 아니다. 실행기 연결 뒤 포털 보류 사유/새 평가 요청·실제 펌프/가림을 검증한다. 이 단계만으로 A057 실패가 해결됐다고 쓰지 않는다.

참고 범위 정정: 제품 `handle_pending_workitem` L5276~5365는 자식 프로세스 종결 대기용이다. 여기 구현한 센서 UNKNOWN/UNSUPPORTED·명시 재평가 계약은 HYD 보강이며 제품에 그대로 존재한다고 주장하지 않는다. CLI outcome의 미충족 결과 거절과 상태/점유/이벤트 분리는 참고한 실제 계약이다. 전체Goal active/62.5 유지, 교재·리허설 제외.

### A057 운영 Kafka 연결·재시작 복구 — 배포·쿨러/팬 통과, 펌프/가림 미완료

main의 고정3패턴 실행을 Runtime/Neo4j source로 교체했다. 최초 로드/잘못된 갱신은 health503·새 경보 보류, 기존 발생 경보는 고정 정의로 계속 해제 가능하다. 15초 갱신/명시 reload·정의SHA/오류 API, 배포별 detectorScope(권한 경계 아님), SQLite 체크포인트+처리offset+경보outbox를 넣었다. 재시작은 관측/hold를 초기화하되 경보ID/정의·미전송 이벤트를 복구하며 broker ACK 뒤offset커밋한다. 최종 전체 **832 passed/6 warnings**(`a057-full-final.log`). 실제 별도 Kafka 토픽·Neo4j scope·HTTP·프로세스 kill/restart **14/14**(`a057-kafka-ready`): 정의 변경/오류, 기존 경보 같은ID 해제, 새 발생 보류, 원천 복구와 outbox 전달. 실패 원본 `a057-kafka`(sync API SQLite 스레드 오류), `a057-kafka-fixed`(재시작 Kafka 할당 전 준비 판정)를 보존하고 async API 및 assignment/position 확인으로 수정했다.

2026-10-04T15:10:34Z detector만 새 이미지로 배포, detector-data 영속 볼륨 및 메모리256MiB 적용. 배포 전3설비 모든패턴IDLE/비트립(`a057-before-deploy.json`), 배포 후 source ready/3정의(`a057-deployed-catalog.json`). 실제 회귀 `a057-scenarios` 진행 중: 팬은 현재 검토/승인→PLC 팬40·부하80→동일ID CLEAR→VS1 .935 재관측→ev:closed 통과. 펌프/가림은2분 실제 SQL 평균에 정상 구간이 포함되어 근거FAIL→에이전트WITHHELD; 진단 보류가 프로세스에 전달되지 않아 task:diagnose IN_PROGRESS로 남는다(`a057-RUN-0004.json`, `a057-RUN-0006.json`). 경보60sim초와 근거2wall분은 서로 다른 조건이다. 임계값을 낮춰 성공 처리하지 않으며 재평가/보류 전달을 후속 수정한다. 실행은 legacy 브리지/LLM 템플릿 대체이며 새 Codex 증거가 아니다.

회귀 종료: `a057-scenarios` **20/22, exit1**(펌프/가림 진단2건 실패), 별도 `a057-cooler` **42/42, exit0**(현재 검토/역할 거절·승인·PLC ACK·재관측·CMMS·Neo4j 투영). 실패 당시 원시 DB를120초 뒤 구간으로 읽으면 각 태그120표본, 펌프 PS1평균162.454/FS1 7.644, 가림162.414/7.639로 두 조건 모두 만족했다(`a057-withheld-window-analysis.json`). 이는 과거 원시데이터 재조회이며 실제 재시도 성공이 아니다. 검사기는 이미 끝난 WITHHELD/FAILED/PENDING을 즉시 보고하도록 수정(구문/diff 확인), 같은 이유로150초를 반복 대기하지 않는다. 이 검사기 수정 후 실제 펌프 재실행은 아직 하지 않았다.

15:21:31Z 운영 원천ready/outbox0·process/agent health정상, 설비3기 RUN/팬60/부하90/고장0로 복원. PowerShell worker/probe/scenario 프로세스0, config SHA `836330D564FE7CBD72946985BFA2CA90BD1B7EAC22AA5AA6143489972CD0DB0A` 불변(`a057-runtime-final.json`, `a057-process-check.json`). process 재시작 수2·기동14:28:27Z로 A055 이후 증가 없음. 실패 인스턴스·이벤트는 보존한다.

**다음 A058:** 실제 참고 레포의 작업 보류/재평가 계약과 대조해 `agentsvc.main.pipeline`의 WITHHELD가 `instance_mode`/진단 작업에 이유와 실행 근거를 내구적으로 전달되게 수정한다. 근거가 나중에 충족될 때 새 평가를 수행하는 복구 경로와 중복/동시작업/재시작 경계를 검증한다. FAIL→PASS를 임의 변경하거나 SQL2분을 가속시계로 몰래 축소하지 않는다. 이후 펌프·가림을 새 실행으로 검증한다. detector source query의 실행 시간 제한과 bootstrap 예외 시 store 정리도 후속 견고성 항목이다. 새Codex 정책거절(A033)은 같은 danger-full-access/never에서 발생한 기록이며 현재 설정만으로 해제됐다고 판단해 우회 재시도하지 않는다. 전체Goal active, 점수62.5 유지.

### A056 정의 기반 감지 실행부 — 원천 검증, 운영 연결 미완료

회의2 L299~348, 실제 스키마 및 completion `b272c9ab458f3ca3e18fe286e4e770d291b99e89`의 `regression/dmn_replay.py` L218~279(데이터 조건·규칙ID·미일치), `polling_service/workitem_processor.py` L4223~4250(미평가를 true로 취급하는 경계)을 대조했다. 후자의 기본 허용을 센서 판정에 복제하지 않는다. schema.json에서 rule은 설명문, TESTS는 AND 조건이다. 처음 고려한 설명문 직접 실행을 버리고 TESTS를 실행 정본으로 사용한다.

`det/patterns.py`는 TESTS·명시 clearRule 제한 AST·수치/입력/보고주기·해상도·고유ID/카탈로그를 검증하고 정의SHA를 만든다. `pattern_runtime.py`는 새 패턴 코드·임계값·발생/해제 지속시간을 같은 엔진으로 평가한다. 후보의 정의 변경은 hold 초기화, 발생 경보는 제거/변경 후에도 원래 정의로 해제한다. 잘못된 카탈로그 교체는 원자 거절, 결측/불량·과거/미래 입력·부족한 경사 창은 UNKNOWN이다. TS1 평가 시계와 현재 DAQ 지원 태그/변수 범위이며 lite에서 시간조건 태그가 매초 보고되지 않으면 full/DAQ 변경을 요구한다.

`pattern_source.py`는 실제 Neo4j의 held/TESTS를 한 트랜잭션으로 읽는다. `detector-patterns.cypher`/`migrate_detector_patterns.py`로3패턴 누락 해제·시간 메타데이터와 펌프 RUN TESTS를 추가했다. 기존 편집값은 coalesce/ON CREATE로 보존, 커밋 전 전체 정의 검증, 변경 전/후 원천은 `a056-migration-fixed/`. 최초 snapshot ORDER BY 집계 오류는 DB 변경 전 실패(`a056-migration.log`). schema 정본/생성물 및 신규 load 파일 목록 동기화; 새 빈DB 전체 load는 미실행.

전체 **823 passed/6 warnings**(`a056-full.log`), 실제 Neo4j→새 엔진 **12/12**(`a056-live`): 별도 UUID 패턴의 임계값/60→100sim초 변경, 이전 경보 정의 고정 해제, 새 조건/hold 적용, 잘못된 TESTS 거절, UNKNOWN 유지/복구. 관측은 명시 합성 입력이며 운영 Kafka/PLC/프로세스에는 보내지 않았다. own fixture3노드만 제거하고 기존 카탈로그 동일을 재조회했다. **운영 det.main은 아직 기존 실행부다.** 이 검사를 운영 연결이나 새 Codex 성공으로 세지 않는다.

**다음:** 운영 Kafka 경로에 연결하고 최초 원천 로드 실패·갱신 거절·적용 정의/경보SHA를 노출한다. 기존3패턴/PLC트립·UNKNOWN 회귀와 실제 정의 변경→Kafka→프로세스 경로, 재시작 시 상태 복구·새 패턴 라우팅을 확인한다. 새 Codex/문서 추출/47레포 대응/효과보상 등 전체 Goal 미결은 유지. 사용자21시간 진척 질문: 요구 기준62.5/100(공수 완료율 아님) 유지.

### A055 DAQ 시간조건 입력 해상도·팬 해제 — 배포 및 범위 내 검증 완료

기존 lite는 VS1/PS1/FS1/LoadSP를 deadband로 생략해 경사 창의 관측이 부족하거나 작은 임계값 왕복을 놓칠 수 있었다. 공유 DAQ 계약의 매초 태그를 TS1·CE·PS1·FS1·VS1·LoadSP로 확장했다. 비시간조건 태그의 deadband/heartbeat와 full/waves 계약은 유지한다. 감지기 허용 나이도 같은 계약을 사용한다. 실제 추가4태그×3설비가60초 각60관측으로 저장됐다(`a055-daq-samples.json`). 배포 전3설비 기본 정상/진행 명령 없음(`a055-plant-before-deploy.json`); plant 재생성은 sim_t/RNG/마지막 명령 표시를 초기화하므로 상태 보존으로 주장하지 않는다.

관련45/전체794 passed 후 plant·detector 배포. 세설비 세패턴 입력VALID, 실제 팬 경보16초→instance→현재 검토/승인→PLC 팬40·부하80 ACK→VS1 .924까지 확인했다. 이후 process가14:28:27Z 예기치 않게 재시작되어 `INC-1004-01-f83c`는 PROCESS_RESTART_REVIEW/사람 검토로 넘어갔다. 완주 실패이며 사람 작업을 정상 종결로 바꾸지 않는다. 실행은 legacy bridge/LLM HTTPError 템플릿 대체였다. process160MiB 상한 근처 실제145.9MiB·회수/스왑 발생을 확인해 기본상한512MiB로 조정한다. OOM 원인 확정은 아니다(재시작 후 oom_kill0, 이전 종료 이벤트 근거 없음). 첫 검사 결과를 보존한 뒤 새 실행으로 검증한다.

첫 실행12/13 exit1(`a055-fan`), 두 번째도12/13 exit1(`a055-fan-rerun`): 이번은 재시작 없이 VS1 .915인데 경보 미해제로 MITIGATION_FAILED였다. 실제60관측 범위 .908~.974(`a055-failed-clear-samples.json`). 결정13.4는 fan CLEAR를 VS1<1.1 히스테리시스로 정했지만 cep.py가 추가로 slope<=0의 연속 유지를 요구했다. 정상 범위의 변동도 hold를 취소하는 반례2실패(`a055-fan-clear-red-final.log`)를 확인하고 CLEAR는 원래 하한/60sim초 연속 유지로 수정·배포했다. 발생 조건의 상승경사·임계값, 입력품질/공백, 실제 재관측 기준은 유지한다. 이전 실패2건은 사람 검토 상태로 보존한다.

최종 전체 **796 passed/6 deprecation warnings**(`a055-full-final.log`), 수정 후 실제 팬 **14/14 exit0**(`a055-fan-fixed`): ALT-hyd03-0001-4d0c→현재 검토/승인→PLC 팬40·부하80→경보 해제→VS1 .937/재관측 통과→CMMS WO-1004-5A13→ev:closed. 인스턴스 `anomaly_response.60e69b8d-5098-4194-8d08-45662139fd20`, 사건 `INC-1004-02-673a`. legacy 브리지 검증이며 새 Codex 성공이 아니다. 실패 두 사건 `INC-1004-01-f83c`/`INC-1004-01-cef1`의 검토 작업은 미완료 그대로다. 검사 종료 후 설비3기 기본 정상 복원,14:40:17Z 서비스health 정상/PowerShell worker·probe0/config SHA불변(`a055-runtime-final.json`). process 메모리 상한은 실행 중512MiB로 적용했고 Compose 기본도512MiB다. 원래 예기치 않은 재시작 원인은 미확정이다.

**다음/미결:** `it/neo4j/v2/instances.cypher`의 AnomalyPattern.condition/holdSeconds/TESTS와 `det/cep.py` 상수·`PATTERN_INPUTS`가 아직 분리돼 있다. 회의·실제 레포의 규칙 실행 구조와 대조해 정의 변경이 수집 요구·실행·검증까지 연결되도록 진행한다. 최신 쿨러/펌프/가림 통합 회귀, 실제 문서/질의 생성·변경지식의 새 Codex, 전체47레포 대응, 의미 연결/효과보상은 남았다. 표본 사이 연속성/임의 배율 해상도 자동 설계는 미구현이며 점수62.5 유지.

### A054 CEP 관측 공백·입력 품질 — 배포·실제 검증, 팬 관측 해상도 미결

`a054-gap-before.json`에600초 입력 공백 뒤 즉시 RAISE,599초 공백 뒤 CLEAR를 실제 기존 함수로 재현했다(명시 합성 관측). wall/event 시간과 TIME_SCALE을 분리하고 필요한 입력의 원천 시각·품질을 검사한다. DAQ cadence 상수는 `common/hydcommon/daq_contract.py`로 공유하되 lite/full 보고 동작은 바꾸지 않았다. 허용 공백을 넘기면 지속시간 후보를 초기화하고 이미 발생한 경보는 데이터 없음을 이유로 CLEAR하지 않는다. 오래된/중복/충돌/미래 관측, 잘못된 PLC 상태도 구분한다. VS1 경사 창은 새 VS1이 없어도 만료시키며2관측 미만이면 UNKNOWN이다. 이벤트에는 실제 시간 배율·보고 프로필·원천별 나이가 남는다.

전체 **791 passed/6 deprecation warnings**(`a054-full-final.log`), 기존 DAQ/3패턴 회귀와 새 원천 품질·1/2/20배속/경보 유지·복구를 확인했다. 별도 컨테이너·Kafka 토픽/consumer group의 실제 `det.main.run()`으로 **11/11**(`a054-kafka/checks.json`): 공백 뒤 보류→새 구간 RAISE→복구 공백 뒤 기존ID 유지→새 구간 동일ID CLEAR, 과거/불량/없는 입력, 출력토픽의2이벤트와 시간계약. 명시 합성 입력이며 운영 plant.tag/alerts에는 보내지 않았다. 시험 토픽 이름과1시간 retention은 result.json에 보존했고 컨테이너/클라이언트는 종료했다. 검사기의 최초 latest-offset 확정 전 송신 실패는 `a054-kafka-initial-offset-failure.log`; 실제 position 확인 후 통과했다.

배포 전3설비 모든 패턴 IDLE/트립false(`a054-detector-before.json`)를 확인하고 detector만 재생성했다. plant-sim/PLC는 재시작·reset하지 않았다. 가동3설비 관측·profile lite/20배속을 확인했다(`a054-detector-deployed.json`). 최초 준비 대기는 PowerShell Properties.Count 배열 해석 오류로 실패했으나 재기동 없이 실제809건 관측/HTTP200을 확인했고 배열 Count를 명시해 재검증했다.14:18:47Z detector/plant/process health 정상·워커/검사기0·개인config SHA 불변(`a054-runtime-final.json`).

**중요 미결/다음:** 가동3설비 쿨러·펌프 입력VALID, 팬은 `VS1_SLOPE: INSUFFICIENT_WINDOW`였다. lite VS1 heartbeat10wall초와20배속60sim초 경사 창(3wall초)이 불일치한다. 오래된 경사를 재사용하던 성공을 복원하지 말고, 실제 필요한 관측 주기를 DAQ 계약에 반영하고 상태 보존을 고려해 배포한 뒤 팬 발생/복구를 실제 검증한다. deadband 근처 지속조건의 불확실성, 규칙 holdSeconds/TESTS와 실행 CEP의 일반화, 새 Codex 생성·보류 재개 및 전체 Goal 미결도 유지한다. 이번은 Flink 엔진 이식이 아니라 기존 HYD 감지기의 결함 수정이다. [Flink CEP 시간/늦은 이벤트 원문](https://nightlies.apache.org/flink/flink-docs-stable/docs/libs/cep/#handling-lateness-in-event-time)과 대조했으며 watermark 정렬/side-output을 구현했다고 주장하지 않는다. 점수62.5 유지.

### A053 관측 근거 UNKNOWN 보존 — 배포·실제 검증

R05/R06 지속조건 조사에서 기존 Evidence 경로의 오류/빈 값→passed=false 변환, rank_causes에서 오류 소거, 수동 판단의 원천 실패 후 임의 원인 선택을 발견했다. 7개 실패를 `a053-red.log`에 재현했다. WMS reference `8ba09f4420ba04d094a0fc4a05c72bc38b0b8a52` `mcp/wms_mcp/mcp_server.py` L93~116의 오류 봉투/성공 문서 구분과 HYD를 대조했다. 이 레포가 HYD 원인 순위 알고리즘의 정답을 제공한다고 주장하지 않는다.

`mcp_tsdb.evaluate`는 단일 유한 수치만 비교하고 PASS/FAIL/UNKNOWN을 구분한다. 빈/NULL은 NO_DATA, 잘못된 SQL/형식/NaN/Inf 등은 오류 근거를 남긴다. 비교 전 소수3자리 반올림을 제거했다. `card.rank_causes`가 오류를 보존하고 미확인 점수는null이다. 알려지지 않은 대안이 있거나 전체 후보에 지지 근거가 없으면 MCP diagnose·레거시 pipeline·수동 판단은 후속 조치 추천을 보류한다. 수동 cause override도 조회 실패를 우회하지 않는다. UI는 미확인을 조건 미충족과 구분하고 새 요청 실패 때 옛 성공 판단을 남기지 않는다.

전체 **775 passed/4 deprecation warnings**(`a053-full.log`), 실제 reader/Neo4j/MCP/HTTP **22/22**(`a053-live/checks.json`): 실제DB null/0/NaN/Inf/다중행/열/문자/비교 정밀도, 별도 시험 그래프의 SQL오류→보류·오류보존→빈 관측 보류→규칙 수정 후 같은 패턴 복구, 수동 override409·전체불일치 UNSUPPORTED, 기존 진단 회귀. 시험은 명시된 합성 규칙이며 수집 데이터·설비 명령을 바꾸지 않았다. 자신의 fixture7노드만 제거하고0을 확인했다. 검사기 최초 문자열 문법 오류는 `a053-live.log`, 수정 후 결과는 `a053-live-fixed.log`다.

실제 수동 일반 경로 EVALUATED/3카드(`a053-manual-normal.json`)와 포털에서 HYD-02/PUMP_LEAKAGE 정상 운전 관측의 보류 사유→HYD-01/COOLER_DEGRADATION3카드→다시 보류를 직접 확인했다. `a053-ui-final.json`은 사유 표시/이전결과null/카드0/가로넘침false, JS오류없음이다. 값 반올림은 화면에만 적용한다. agent/dmn 배포 후14:00Z health 정상·PowerShell worker0/config SHA 불변(`a053-runtime-final.json`), 전용 browser 종료.

미결: Evidence 평균 SQL이 구간 전체·허용 간격·신선도를 증명하는 것은 아니다. DAQ lite의 변화보고, CEP의 시뮬레이션 시간/이벤트 누락과 규칙 holdSeconds를 대조해 지속조건 경로를 계속 고친다. 이번은 diagnose/레거시/수동 판단 보류 검증이며 새 Codex가 보류 결과로 사람 확인·재시도하는 실행, 직접 evaluate_cards 인수의 진단 출처 강제까지 증명하지 않는다. 실제효과 보상·의존 스케줄러·문서추출·47레포 채택과 전체 Goal은 계속 미결/점수62.5다.

### A052 Prometheus 실제 메타데이터·PromQL — 배포·실제 검증

회의2 L299~348/현재 prometheus.yml을 재대조했다. 기존 mcp_prom.freshness는 Timescale/ingest health 검사다. 새 읽기 클라이언트 `agentsvc/tools/prometheus.py`와 MCP `prometheus_metadata/series/query`를 연결했다. 공식 HTTP API https://prometheus.io/docs/prometheus/latest/querying/api/ 를 확인하고 실제2.55.1 응답으로 호환성을 검증했다. 참고클론 py/ts에서 PromQL 구현 검색 결과는 없었으나 전체47레포 부재 주장으로 확대하지 않는다. 기존 HYD DmnTools의 봉투 계약을 재사용하며 reference 제품의 PromQL을 이식했다고 주장하지 않는다.

실제 metadata는9종이며 플랫폼 상태 외 `detector_ts1`/`detector_anomaly_score`도 있다. `it/detector/det/main.py` L24~27/L78~84와 일치한다. A051의 "플랫폼 지표" 설명을 구체화한다. VS1 지표는 현재 exporter에서 노출하지 않는다. scrape 시각은 마지막 센서 이벤트 시각을 보증하지 않으므로 온도 지표의 최근 scrape만으로 원천 신선도/지속시간을 판정하지 않는다.

전체 **766 passed/2 warnings**(`a052-full-final.log`), 가동 MCP **17/17**(`a052-mcp/checks.json`): 실제 metadata/레이블→지표 선택→같은 시점의 임계값 변경 참/거짓,6개 job·구간행렬,0/빈벡터/NaN,잘못된 PromQL/구간,닫힌 포트 오류,관측시각,기존 Timescale schema/diagnose 회귀. 실제 Prometheus 중지→가동 MCP UNKNOWN→재시작 후6시리즈 복구(`a052-mcp/outage.json`)도 확인했다. 질의는 검사기가 작성했으며 Codex 생성 증거가 아니다. 응답 경고/정보와 NaN/Inf 보존·한도/잘못된 봉투의 분류는 단위 검증이다.

최종 빌드/배포 뒤 준비 전에 MCP에 접속한 실패(`a052-mcp-startup-failure.log`, `a052-mcp-final.log`)를 보존하고 health 확인 후17항목을 다시 통과했다(`a052-mcp-ready-final.log`). 13:46:37Z 최종 `a052-runtime-final.json`: dmn/process health 정상,Prometheus2.55.1 가동,PowerShell 워커/검사기0,개인 config SHA 불변. 이번에 기동한 Prometheus는 조회 서비스로 유지하며 설비/업무 데이터 변경은 하지 않았다.

다음: 센서/Prometheus의 관측 시각·DAQ 변화보고·규칙 duration/gap 계약을 실제 코드와 연결하고 누락/오래된 관측의 참/거짓/미확인을 검증한다. 일반문서 새 Codex 추출, 변경 지식/규칙의 실제 Codex 질의 생성, 실제효과 보상·의존 스케줄러·47레포 채택 및 전체 회귀는 계속 남는다. 이전 Codex 자동 심사 거절을 우회하거나 이번 MCP를 새 Codex 결과로 세지 않는다. 전체 Goal active/점수62.5 유지.

### A051 센서 메타데이터와 생성 SQL 실행 — 배포·실제 검증

회의2 L299~348은 원천 메타데이터를 LLM에 제공해 규칙에 맞는 SQL/시계열 질의를 생성·실행하라는 요구다. 현재 Prometheus 구성은 플랫폼6서비스 지표이며 센서 진동은 TimescaleDB 원천이다. 참고 클론의 py/ts/md 검색에 PromQL 구현은 발견되지 않았으며 전체47레포 부재 판정으로 확대하지 않는다. neo4j-text2sql HEAD `25ab12a8b9129b99fa3e83519214e71e12962a9d` `app/core/sql_guard.py` L1~155를 재대조했다. 기존 HYD enterprise AST 계약을 common으로 공유하고 TSDB3표/전용 reader/읽기세션·시간제한, 실제 schema/최근 태그와 생성 SELECT 도구를 연결 중이다.

실제 가동 dmn-mcp의 TSDB 연결은 주석과 달리 role=hyd, tag_1s INSERT 권한=true, default_transaction_read_only=off였다(`a051-reader-before.json`; 조회 확인, 쓰기 수행 안 함). `reader.sql`을 기존 DB에 reset 없이 적용하고 초기 DB 마운트에 추가했다. agent/dmn-mcp는 전용 reader를 사용하고 시계열3표 AST/읽기세션/5초 제한을 적용한다. `timeseries_schema`는 실제 열과 최근5분 관측 태그, `timeseries_query`는 에이전트가 제공한 SQL의 실제 결과를 반환한다. enterprise guard도 common AST 계약으로 공유했다.

검증: 최종 전체 **743 passed/2 warnings**(`a051-full.log`), 실제 TimescaleDB **13/13**(`a051-timeseries-live/checks.json`) — reader 권한·스키마·실제 진동 구간의 임계값 변경 참/거짓·관측 간격/신선도·0행·잘못된 열·원천 밖/쓰기/함수 거절·연결 실패·time_bucket·기존 Evidence 매개변수 조회. 가동 FastMCP **9/9**(`a051-mcp/checks.json`) — 새 도구 노출/실행·빈값과 오류 구분·실제 reader·기존 diagnose·기업SQL 복합조건 회귀. 생성 SQL은 검사기가 작성했으며 실제 Codex 실행이 아니다.

실패 보존: SQLGlot가 AND를 Func로 표현해 기존 guard가 정상 복합조건을 거절한1실패/47통과(`a051-focused.log`), BOOL_AND의 정규화명 LOGICAL_AND 거절(`a051-timeseries-live.log`). 논리 연산과 집계의 AST 이름을 반영해 재검증했다. 최초 compose `--profile cliagents`가 기본 프로필을 대체해 process 의존성이 빠졌으므로 전체 기존 프로필+cliagents로 명시하고 지정3서비스만 재생성했다. worker 컨테이너는 올리지 않았다.

최종 환경변수 적용 후 reader=hyd_timeseries_reader/read_only=on/INSERT=false/실제1행 재확인(`a051-deployed-final-reader.json`), agent/dmn/enterprise health 정상·PowerShell 워커/검사기0·개인config SHA 불변(`a051-runtime-final.json`). 설비 조치·데이터 삭제·개인설정 변경 없음. 사용 계약은 `docs/sensor-queries.md`. R06 PromQL 메타데이터/실행, 규칙의 지속시간/누락 의미와 새 Codex 생성 경로는 미검증이다. A050 실제 문서 추출 및 전체 Goal 미결을 유지하며 평가62.5를 올리지 않는다.

### A050 일반문서 추출 작업 연결 — 계약·가동 검증, 실제 Codex 추출 미검증

회의2 L253~327, ontology-studio `6a229be8dcce2aeb533ecdba360b5b4564ffb777` `agent_session/service.py` L71~250의 고정 스키마/세 가지 추출 패턴/실제 질의 검증, bpmn-extractor `c7992ce95e90492647411980a3034653784137e6` `extractors/entity_extractor.py` L1~200의 원문 근거·조건/순서 보존을 재대조했다. 제품의 임의 클래스 추가·2000자 절단·별도 Skill 추출 금지까지 HYD에 그대로 적용하지 않는다. HYD는 회의의 기존 스키마에 맞는 ManualSection/Skill/Step 제안을 먼저 연결한다.

기존 일반 문장은 structured-lines-v2에서 절차0개이며 실제 에이전트 추출 연결이 없었다. `manual_extraction.py`의 고정 정의 `manual_source_extraction@1.0`→기존 cliagents Codex 작업→엔진 원문 인용/페이지 검토 구조검사→별도 사람 검토/적재 API와 포털 동선을 구현·배포했다. 전체 원문은 시작 변수/query에 고정한다. 8000자 절단은 query 원문이 아니라 별도의 output/draft 입력이었음을 확인하고 이 제한을 제거했다. 작업 공간 task.json에도 query/draft/output을 보존한다. 작업 결과의 source/좌표/순서/전체 페이지 검토 목록을 엔진 완료 전에 검증하며 의미 정확성은 사람 검토로 남긴다. 적재 원장에는 실제 생산 작업/세대/세션 연결과 검토 기록을 저장한다. 문서별 서버 실행 이력은 tenant·원문 판본 범위에서 페이지 조회하며 브라우저 저장소 없이 기존 결과를 다시 선택한다.

검증: 영향54 후 최종 전체 **728 passed/2 warnings**(`a050-full-final.log`). 실제 HTTP/SQLite/PG/Neo4j 계약 **13/13**(`a050-live/938C3763FE/checks.json`): 11751자 일반 원문 전체 보관·중복 요청·미실행 대기·다른 문서 결과 거절·PG 원문말미 보존·합성 출력의 엔진 완료·검토/위조 인용/위조 생산 작업 거절·멱등 적재·되돌림·process 재시작. **검사기가 출력 proposal을 작성해 worker RPC로 제출했으며 Codex 실행이 아니다.** 추가 실제 PG 페이지 이력/포털 생성 작업 계약 **5/5**(`a050-ui-fixture.json`). 실제 Neo4j에서2단계 원문·FailureMode/REFERS_TO/PART_OF 관계·적재 원장의 작업 출처를 조회하고 해당 배치만 rollback했다(`a050-graph-final.json`). 원문과 두 완료된 검사 인스턴스는 보존했다.

포털: 보관 원문 재검토→브라우저 요청 이력 없이 서버 결과 선택, 새 추출 요청→IN_PROGRESS 표시→합성 결과 수신→인용/단계 검토 폼을 직접 확인했다. `a050-ui-pending.png`, `a050-ui-result.png` 직접 검토/가로넘침없음/JS오류없음/브라우저종료. 검토 체크는 결과를 읽어도 false이며 고장 유형은 사람이 선택한다. 숨김 버튼 CSS 충돌과 긴 절 본문 펼침을 수정해 재확인했다. 포털에서 최종 적재 클릭은 이번에 수행하지 않았으며 적재/되돌림은 실제 API로 확인했다. 최종 PowerShell 워커/검사기0·health정상·개인config불변(`a050-runtime-final.json`), 배포 전 일관 백업 `a050-final-deploy/before.sqlite3`.

미검증: 새 Codex가 실제 일반 텍스트/PDF를 읽고 추출하는 의미 정확성, 큰 입력의 CLI 전달 한계·OCR/표, 사람 편집/재작업과 변경 지식 전체 회귀. 과거 시작 명령의 자동 심사 차단을 우회하지 않았으며 A050에서 새 실행을 재시도하지 않았다. 기존 실제 A034 Codex 검증과 합산하지 않는다. 전체 Goal active/평가62.5 유지. 다음 독립 작업은 R06 회의2 L299~348과 실제 SQL/시계열 질의 레포/현재 HYD 코드 대조다. R02의 실제 Codex 추출은 미결로 유지한다.

### A049 실제 반영 영수증과 명시적 복구 — 배포·실제 검증

실제 SQLite 백업 복원 및 격리 PG/Neo4j 불일치에서 **거절된 쓰기를 양쪽 모두 완료로 기록**, **복원한 SQLite의 동일 revision으로 다른 내용 덮어쓰기** 3건을 재현했다(`a049-red/a049-66d38a1810`). payload hash와 정확한 반영 영수증을 확인하고 충돌 원천의 자동 전송을 보류한다. 새 큐 행도 보류를 우회하지 않는다. 원천·그래프·고정 정의·의존 판단을 비교한 계획으로만 높은 revision을 명시 등록하며, 요청/결과 원장을 큐와 함께 저장한다. migration00012 적용·등록, 서비스 배포 완료. 참고 strategy의 증분/해시/보류와 별개로 HYD 두 원천 저장소에 맞춘 복구 계약이다.

검증: 전체 **713 passed/2 warnings**(`a049-full-dependent.log`), 실제 SQLite/PG/Neo4j **11/11**(`a049-live/a049-52590cab01`, `a049-live-dependents.log`), 기존 지식 변경 회귀 **10/10**(`a049-knowledge-regression.log`). 초기5/5와 확장10/10은 중간 증거다. 첫 실제 검사 DateTime 직렬화 오류는 롤백 후 수정했고, 첫 전체검사의2실패는 영수증을 반환하지 않던 가짜 그래프 훅을 계약에 맞게 수정했다(`a049-live-first.log`, `a049-full-first.log` 보존).

가동 CLI **9/9**(`a049-deployed-final/checks.json`): 완료 인스턴스 `knowledge_a048_56296646.b1e7fb00-7995-4cc3-91d3-ebfc286b8fc4`의 거절된 전송 보류, 사건 `INC-1004-01-4ff2`의 파생 그래프 전체 삭제→복구 및 원래 incoming DecisionCase/ProcessInstance 관계 복원, 실제 업무 원문·작업·사건 불변, 서비스 재시작 후 동일 요청 재전송/원장1행을 확인했다. 앞선8/8(`a049-deployed/`)은 간선만 훼손한 시험이다. 포털 충돌 보류 화면 `a049-ui-quarantine.png` 직접 확인, 가로 넘침/JS오류 없음, 복구 후 선택 실행/사건 pending0 확인, 브라우저 종료. 배포 전 일관 SQLite 백업 `a049-final-deploy/before.sqlite3` 보존.

경계: SQLite는 실제 백업 복원, PG는 격리 그래프 fence를 앞세운 불일치 시험이다. PG 전체 백업/여러 업무 DB 재해 복구·투영 단독 훼손 자동탐지는 미검증이다. 새 Codex·PLC 시험으로 세지 않는다. 운영 명령은 `docs/execution-projection.md`. 전체Goal active/평가62.5 유지. 다음은 회의2 L253~327과 관련 레포의 문서 추출·질의 생성 실제 코드를 R02/R06에 대조해 구현 차이를 좁힌다. 47레포 채택 검증/전체 의미 연결/효과보상·의존스케줄러/변경지식 새Codex 등 기존 미결도 유지한다.

최종 PowerShell 확인(13:02:45Z): 워커/검사기0, process health 정상, 사건/판단 pending0·선택 실행 pending0/오류없음, 개인config SHA256 불변(`a049-runtime-final.json`). 검사/배포 명령은 모두 exit0, 변경 범위 diff check 통과. 다른 tenant의 전체 대기0이나 전체 시스템 완료를 뜻하지 않는다.

### A048 지식 연결 변경의 재투영 — 배포·실제 검증

실제 SQLite/PG/Neo4j에서 지식 노드가 나중에 생겨도 CHOSE 관계가 복구되지 않고, Process/HAS_NODE를 제거한 뒤 재투영해도 오래된 MAPS_TO가 남는 **2건 실패**를 확인했다(`a048-red/`). strategy HEAD `1db85d3b0ab7acf50204360b8115e14fcb4ffb25` `app/ontology_sync.py`의 증분/해시/보류 구현을 재대조했다. HYD의 SQLite/PG 두 저장소 재등록은 HYD 고유 보강이다.

`knowledge_projection.py`가15초 간격으로 실제 지식 조인 대상의 식별자/실물 노드/의미 멤버십을 확인한다. 변경 시 PG 실행 원천 재등록→SQLite 사건/판단 outbox와 체크포인트 동시 커밋, 중간 중단은 재전송한다. 현재 tenant의 알려진 삭제 원천도 재등록하며 투영 소유 노드는 감시에서 제외한다. MAPS_TO는 현재 멤버십에 맞게 교체하고 누락 경고를 API/포털에 표시한다. 기존 판단·승인·업무 상태는 바꾸지 않는다. 현재는 해당 tenant의 알려진 원천 전체를20건 배치로 재투영하며 변경 영향만 선별하는 최적화는 후속이다.

검증: 전체 **700 passed/2 warnings**(`a048-full.log`); 실제 SQLite/PG/Neo4j **10/10**(`a048-live/a048-f6cf2f759d`), PG 등록 뒤 실제 검사 프로세스 exit73→새 처리기 재개 포함. 가동 HTTP 등록 인스턴스 `knowledge_a048_56296646.b1e7fb00-7995-4cc3-91d3-ebfc286b8fc4`에서 늦은 Process/의미 노드 추가→자동 연결, 멤버십 제거→오래된 연결 삭제/경고, 복원→경고 해제, 업무 원문 불변, 정상 사람 폼 제출로 종결 **6/6**. 서비스 재시작 후 체크포인트/원문/관계·health **4/4**(`a048-deployed/knowledge_a048_56296646/restart.json`). 포털 `a048-ui.png` 직접 확인/가로 넘침없음/JS오류없음/브라우저종료. 이름 붙인 완료 시험 인스턴스·정의·의미 노드는 근거로 보존했다. 새Codex/설비조치 증거가 아니다.

실패도 보존: 첫 수정 시험 Cypher SET/CALL 사이 WITH 누락(`a048-live-first.log`), 첫 배포 검사기 process 응답을 문자열로 가정한 오류(`a048-deployed.log`, `checks-attempt1.json`). 각각 수정하고 동일 실제 인스턴스로 재개했다. PowerShell 워커/검사기0·개인config불변 `a048-process-check.json`, 배포 전 일관 백업 `a048-deploy/before.sqlite3`.

**다음 A049:** 지식 변경 없이 투영 관계만 훼손되거나 서로 다른 시점의 원천/그래프 백업을 복원하면 기존 digest/fence 때문에 대기0이어도 불일치가 남을 수 있다. 실제 격리 복원으로 재현하고 원천 권위·삭제 tombstone·오래된 전송 방어를 함께 만족하는 복구 계약을 구현한다. 전체 의미 연결/일반문서AI추출/변경지식 새Codex/효과보상·의존스케줄러/47레포 채택 검증 등은 그대로 남으며 Goal active/평가62.5 유지.

### A047 지식 편집의 원자성·수정 충돌 — 배포·실제 검증

strategy `app/ontology_sync.py`와 ontology-studio `backend/src/modules/ontology/tools.py` 실제 증분 동기화/출처 적재 코드를 대조했다. 지식 변경 전파에 앞서 기존 HYD 스킬 편집의 속성 수정→승인 관계 삭제→새 관계 생성이 별도 커밋임을 발견했다. 실제 Neo4j 격리 스킬에서 없는 역할 입력은 200/승인관계 소실, 중간 저장의 명시적 오류 주입은 일부 수정 잔류로 **기준 검사 2/2 실패**(`a047-skill-baseline/`). 참고 레포가 동일 원자성 계약을 보장한다고 주장하지 않는다.

`skill_graph.py`와 API/포털을 수정했다. 속성·단계·관계·KnowledgeEdit 영수증이 같은 Neo4j 트랜잭션에서 커밋된다. 조회 revision으로 동시 수정/오래된 초안을 거절하고, 요청 UUID 재전송은 저장된 결과를 반환한다. SOP 단계 순서를 요청 식별에서 보존한다. 원문 소유 스킬은 문서 개정·검토로 연결하고 다른 SOP/단계 ID를 교체하지 않는다. 초안의 최초 revision과 응답 미확인 요청을 sessionStorage에 보존한다.

검증: 전체 **693 passed/2 warnings**(`a047-full.log`), 실제 Neo4j **14/14**(`a047-skill-atomic/A047-11BD1ED641`), 배포 API **6/6**(`a047-skill-http/checks.json`). 실제 화면 저장 후 서버200 응답을 클라이언트에서 명시적으로 버림→브라우저 새로고침+process 재시작→동일 UUID 재확인: 생성1/수정2 영수증만 존재했다. 별도 편집자가 수정한 뒤 오래된 초안을 다시 열어 저장하면409, 현재 내용 다시 읽기로 복구했다. 실제 문서 적재 스킬의 직접 수정409 및 해당 source/document/previous_batch를 갖는 문서 검토 화면 이동을 확인했다. 네트워크 자연 장애·새Codex·PLC 시험으로 확대하지 않는다. 브라우저 조작 중 화면 밖 요소 클릭은 적용되지 않아 중앙으로 스크롤 후 실행했고 실제 저장/영수증으로 판정했다.

격리 시험 노드·영수증은 정확한 ID/관계 확인 후 정리했고, 원문 시험은 공식 rollback으로 그래프만 되돌려 파일/검토 이력을 보존했다. 화면/영수증/정리/health 최종 교차 검사 **7/7**(`a047-skill-http/final-checks.json`). 일관된 배포 전 SQLite 백업 `a047-deploy/before.sqlite3`, PowerShell 워커/검사기0·health정상·개인config불변 `a047-runtime-final.json`. **다음 A048:** 지식 변경 시 기존 Case/Execution 의미 관계의 누락·오래된 연결을 실제 변경으로 재현하고 동기화 계약을 수정한다. A047은 작성 경로의 정합성 보강이며 R01/R02의 전체 전파나 일반문서AI추출 완료가 아니다. 전체Goal/점수62.5 유지.

### A046 조건 변경 보류 → 새 판단/동의 → 실제 조치

현재조건의 명시적 거절도 세 번 재시도하던 반례(`a046-baseline-red.log`:1실패/5통과)를 `ApprovalReviewRequired`로 분리했다. 첫 거절에서 PENDING, 전체 검사결과/새판단·동의 필요를 TASK_REVIEW_REQUIRED에 저장하고 포털에 안내한다. 원천 연결 오류/불완전 응답은 제한 재시도이며 명령 허용으로 해석하지 않는다. 최종 전체 **691 passed/경고2** (`a046-full-first.log`), JS/변경범위 diff-check통과. UI에서 새 이벤트 이름이 일반 오류에 가려진 것을 고쳐 실제 재조회/화면 확인(`a046-ui/screenshot-1791114416051.png`), 브라우저종료.

참고 completion HEAD `b272c9ab458f3ca3e18fe286e4e770d291b99e89`: process_engine.py L818~900/L954~1033의 새 작업/고정 판본/의존 재작업, compensation_handler.py L1~140의 관측 이력·불가역 효과 구분을 재대조했다. vue3 WorkItem.vue L2294~2358의 영향 작업 선택도 대조. HYD의 PLC 현재조건 거절 타입은 제품에 같은 구현이 있다는 주장이 아닌 도메인 보강이다. 보상/의존 스케줄러의 미완료 범위를 축소하지 않는다.

실제 `incident_rework_ui_77515c97.da158413-6874-44d9-a09b-d3fe7c215074`/`INC-1004-01-4ff2`: 일시 proxy가 **실제 MES 납기6→36시간**을 명령검사 직전에 변경했고, 실제 agent 응답은 수정 없이 전달했다. 접수/전달 검사allowed=true, 세 번째 명령검사false, retry1/PENDING/cmdId없음. 전체 원장 무효과 확인→새 세대→실제DMN MCP 새 판단→별도 승인→실제 `CMD-1004-0001-624f` ACK DONE→재관측→CMMS/ev:closed **8/8**. 재기동 후 원판단/거절근거 보존·옛판단 실행0/새판단 작업지시1·MES/설비설정복구·proxy중지/정상route복원·graph대기0 **11/11**. 근거 `a046-command-live/`/`a046-deploy/`와 `scripts/probe_command_review_live.py`.

검증 경계: 경보는 명시 synthetic이며 진단~compliance 3작업은 A034 기록 출력이다. 새Codex나 실제고장 주입 시험으로 세지 않는다. 첫 실행은 Docker→PG 순간 연결오류로 조회500/exit1(`a046-process-failure.log`, `a046-deploy/prepare.log`). PG/프로세스 상태 재조회에서 같은 rank DONE/selection IN_PROGRESS를 확인하고 **동일 인스턴스**에서 --resume하여 완료했다. 실행 재시작이나 원본 덮어쓰기로 실패를 감추지 않았다. PowerShell 워커/검사기0,health정상,개인config불변 (`a046-runtime-final.json`).

다음: R01/R02의 지식/원천 변경 및 기존 실행 의미 연결을 ontology-studio/strategy 실제 코드와 재대조하여 수정·검증한다. A045 취소 응답유실의 요청ID보존, 실제효과 보상/의존 스케줄러, 일반문서Codex추출, 변경지식 새Codex 실행 및 전체시스템 회귀 등은 계속 미완료. 새Codex 실행의 기존 정책거절을 우회하지 않았다. 전체Goal active,교재/리허설제외. 사용자 최신 원문 "실제 레포 등등 효율적으로 작업하자 니맘대로 막 간소화 등등하지말고 신중히"를 따른다.

사용자 진척률 질의에 대한 현재 평가: **약60%**. AUDIT 14영역 동일 가중치 단계점수는62.5/100이며 공수 실측 완료율은 아니다. 산정 기준·각 점수·미완료 근거는 [PROGRESS.md](PROGRESS.md)에 고정했다. 교재/리허설 제외, 테스트 통과율과 전체 진척은 구분한다.

### A044 SQLite 사건·판단 투영 — 검증 및 가동, 실제 경로 실패 분리

참고 strategy HEAD `1db85d3b0ab7acf50204360b8115e14fcb4ffb25`의 `app/ontology_sync.py` L1~18 증분 원천/멱등 반영/보류 구분을 대조했다. vue3 outbox 설계에 이어 HYD SQLite 소유권에 맞춰 구현했으며 제품에 같은 SQLite 구현이 있다고 주장하지 않는다.

`Store.save` 동일 트랜잭션의 snapshot/outbox/hash, 기존 snapshot 초기 등록, 감사 로그만 변경 시 중복 제외, 삭제 tombstone 및 의존 판단 관계 재시도, 저장 payload만 사용하는 `CaseProjector`, legacy/instance 공통 복구 loop를 구현했다. CaseProjection revision fence와 고유 제약은 오래된 쓰기/삭제 뒤 부활을 막고, 같은 revision 재전송은 누락 관계를 복구한다. 활성 Incident 상태와 승인 판단의 실제 상태를 투영한다. 기준 Decision의 필수MATCH로 다른 관계까지 중단되던 쿼리를 OPTIONAL MATCH+warnings로 고쳤다. PG 연결 재투영 등록까지 성공해야 사건 outbox를 ack한다. GET /api/graph-projections와 포털 「그래프 반영 상태」는 선택 실행/전체 사건·판단 대기 및 오류를 구분한다. [운영 계약](../execution-projection.md).

증거: `a044-baseline-red.log`는 기존 큐/복구 인터페이스 부재 수용검사2실패(네트워크 반례가 아님). 수정 후 **전체666 passed/기존 경고2**(`a044-full-first.log`). `scripts/probe_case_projection.py` 실제 SQLite/PG/Neo4j **16/16 exit0**(`a044-live-first/`): 실제 거절 Bolt 연결/새Store 복구, 먼저 만들어진 PG 실행의 HANDLES 복구, audit 중복 제외, 상태/진단관계 제거, 지연 쓰기 거절, 그래프 commit 직후 별도process os._exit(73), 재시작 복구, 없는 사건을 만들지 않고 대기, 뒤늦은 사건 도착/삭제/복원 및 의존 판단/실행 관계 복구. 시험 소유 source/graph/PG fixture 보존, 마지막양쪽queue0.

가동 전 SQLite consistent backup `a044-deploy/before.sqlite3`, 빌드/배포4명령 exit0. 기존 source 자동투영 뒤 가동 **API/graph6/6**(`a044-service/checks.json`): 현재사건120건 전부 실제 graph와상태일치, caseworker실행/queue0, 실제 명령실패PENDING과원천명령없음, DecisionCase의APPROVED와실행완료구분. UI1440×1100/390×844 직접확인(`a044-ui/`),390 overflow=false,JS문법통과,전용브라우저종료. 첫브라우저 click의PS @ref 인수해석으로조회대기timeout; 인수를인용해실제화면확인한도구사용실패이며제품성공증거로세지않는다.

**실제 쿨러 회귀는 실패다.** `a044-instance/`의 `scenario_instance_test.py --fresh-review`는 **legacy bridge**였다. 실제 고장→경보→4작업→새예측검토→운전원403/생산관리자선택→승인원장DELIVERED1회를지났으나,명령직전현재예측ts1/ts1_peak악화가검출되어command가3회실패후PENDING이됐다. cmdId없음,PLC/CMMS완주아님. 내가중간에'재관측중'이라고알린것은잘못이었고실제상태확인직후정정했다.

실행 `anomaly_response.fb12836b-0cec-4741-b084-5d386bc23448`, 사건`INC-1004-01-67ce`, 판단`DEC-1004-006-0e84`, 승인작업`975affd0-2fae-4ac9-b4a7-6a035ce937f0`, command작업`2912ecc0-8af0-4db5-ae69-4500d27b3ffa`. 별도 OVERHEAT_TRIP은 `alert_triage.11bedb75-17e4-4921-b6fe-465dcbe4b580`/`INC-1004-02-f441`로사람검토중. 첫PS JSON저장의한국어깨짐은별도원시UTF8 HTTP `failure-*.json`으로다시보존했다.

source/graph/approval/audit/plant증거저장→명령없음확인→시험설비reset→확인된검사기PID8876만PowerShell종료. runner는자식종료코드`4294967295`를남기고종료했다(`result.json`,11:04:04UTC). 정상테스트exit1이나완주가아니다. 자동으로진행할수없는PENDING을기다리는검사기만중지했고업무실행은성공으로바꾸지않았다. 두실행은검토상태로보존했다.

### A045 승인 전달 뒤 미실행 명령 복구 — 구현·배포, 활성 실제경로 후속

`rework_effects.py`는 전체 사건/모든 판단의 기업 원장과 로컬 실행 흔적을 재조회한다. 승인·선택작업·현재 세대/판본·현재변수·판단 소유권이 같고, 알려진 `incident:command`가 PENDING이며 발행 흔적이 없을 때만 새 판단/새 승인을 허용한다. 진행 중 명령, 다른 서비스, 실제·불명 효과는 계속 차단한다. 원래 승인/판단은 보존하고 새 세대 영수증에 동의 폐기를 기록한다. 종료 사건은 역할 검토 후 CANCELLED로 종결한다. 이전 명령이 취소된 경우에도 불변 영수증과 정확히 같은 취소 로그만 다음 재작업에서 인정한다.

검증: 최초수용2실패/7통과 → 최종 **685 passed, 경고2** (`a045-full-final.log`). 첫집중검사의 새 판단 fixture가 이전 승인 소유자를 복사한 문제와 세대불변 저장소에 잘못 주입한 반례를 수정했고 실패로그도 보존했다. 실제 PG/SQLite/기업 원장 조회 **13/13 재작업 + 10/10 종료** (`a045-rework-pg-first/`, `a045-discard-pg-first/`): commit 전/후 별도 process 강제종료, 롤백/재시작, 동시4요청, 원문보존, 이전 워커 결과 거부, 효과 후 재작업 차단. 이 검사에서 현재조건/PLC는 명시적 대역이다.

가동: consistent SQLite backup+build/up 4명령 exit0 (`a045-deploy/`). A044 실제 실패 실행 `anomaly_response.fb12836b-0cec-4741-b084-5d386bc23448`을 포털에서 생산관리자 역할로 효과 확인 후 취소했다. 운전원403, preview 무변경, 완료작업/원래승인/사건/판단불변, cmdId/actions/ack없음, 남은작업취소 및 graph대기0 **9/9**. process 재시작 후 같은9항목통과 (`a045-live/after-restart-checks.json`). 화면1280×720/390×844 직접확인 (`a045-ui/`), JS오류없음, 브라우저종료. PowerShell 워커/검사기0, process health정상, 개인config해시불변 (`a045-runtime-final.json`). 범위내 diff-check/JS문법통과. 전체 diff-check는 이번에 수정하지 않은 tests/test_guardrail.py:114, tests/test_stability.py:157의 EOF빈줄 경고로실패하여 해당WIP보존.

**다음 A046:** 활성 사건에서 실제 현재조건 변경→새 판단→새 승인→설비조치 경로 확인. 조건 거절과 일시 전송실패를 구분하는 명시적 복구 상태, 포털 취소 응답유실의 요청ID 보존도 이어서 검토한다. 실제 미지원 OVERHEAT_TRIP `alert_triage.11bedb75-17e4-4921-b6fe-465dcbe4b580`은 별도 사람검토 대기다. A045의 실제 검증은 종료된 사건의 취소이며 새Codex/활성사건PLC완주 증거가 아니다. 기존 전체미결(지식변경 연결/백업불일치복구/새Codex/효과보상/의존스케줄러/일반문서AI추출 등) 유지, Goal active.

최신 사용자 원문: "작업보고나 문서에 집중하지말고 시스템 설계에 집중 완벽하게", "해피패스 알지? 등등 지침 기억하지?" — 시스템 설계·구현·변경/실패/복구 검증 우선, 기록은 근거와 재개 위치만 유지한다. 교재/리허설 제외.

### A043 실행 그래프 내구성 — PG 범위 검증, SQLite 후속

2026-10-04. vue3 실제 HEAD d88f78ca0b60d979d9de4988f0cd2969949f7ece의 `docs/specs/graph-ontology-apache-age.md` L514~542, `ontology/schema/00-init.sql` L73~83/L109~116에서 원천 트리거/outbox 설계와 DDL/권한을 대조했다. 검색 범위에서 실제 실행 워커 구현은 확인하지 못했으므로 설계/DDL과 가동 구현을 구분한다. REPO_GAP의 교육용 즉시MERGE 예외를 폐기했다.

`a043-baseline-red.log`: 그래프 연결 실패 후 새 런타임에서도 미복구, 오래된 호출 snapshot으로 RUNNING 역행 두 반례 실패. `projection_repo.py`/migration00011은 원천 트랜잭션과 같은 append outbox, repeatable-read snapshot, 별도 전달 advisory lock, 처리한 정확한 행 ID ack,5초 재시도/오류 기록을 추가했다. 네트워크 IO 중 업무 행 잠금 없음. `_project`는 전달받은 옛 상태 대신 원천을 다시 읽으며 poll_once에서도 복구한다. Neo4j revision fence/고유 제약은 지연 쓰기와 삭제 후 부활을 막는다. 소프트삭제/삭제된 작업 정리, 원천 변경 시 이전 자산/사건 링크 제거도 포함한다. 그래프 API의 projection 상태와 실제 graph revision을 구분한다. [운영 계약](../execution-projection.md).

검증: 관련23 passed 후 첫 전체656 passed/생성파일1실패; 생성기 정합성 수정 후 **전체657 passed/기존 경고2** (`a043-full-final.log`). 첫 실제 PG 검사는 실패 기록 SQL의 `%s is null` 타입불명으로 exit1(`a043-live-first.log`); 명시 text cast 수정 후 **실제 PG/Neo4j14/14 exit0** (`a043-live-second/`). 실제 거절된 Bolt 연결, 새 저장소 복구, 원천 rollback, 직접SQL 작업 변경, 전송 중 새 commit, 번호가 작은 늦은 commit 보존, 늦은 그래프 쓰기 거절, 그래프 commit 직후 별도 Python process os._exit(73), 재복구, softdelete/지연 부활 차단/원천 복원, 중복 작업 없음. 첫 실패 fixture는 원문 보존 후 별도 닫고 재투영(`recovered-closed-fixture.json`). 새Codex/PLC 증거 아님.

00011과Neo4j고유제약 실제 적용,process 빌드/배포 성공. 현재hyd backfill+검사132행 처리/pending0. 실제process restart/API 검사는 **4/4** (`a043-service/`). 첫 확인은 모든 원천 열 동일을 요구해서updated_at만 다른1항목 실패했다. 변경 열을 확인하고 'DB 갱신시각만 변경,업무 열 보존'으로 정확히 고쳐 재검사; 첫실패checks도보존. 다른 tenant의 과거fixture 대기는 해당tenant poller 미가동으로 남기며 삭제/완료처리하지 않았다.

**다음:** SQLite Incident/DecisionCase의 같은 저장 트랜잭션 outbox 및 활성 사건 투영, 선행 원천 복구 후 HANDLES/DecisionCase 링크 재조정. 현재pending0은 의미 연결/전체graph완료가 아니다. 포털의 새projection 대기상태 표시는 API/SQL 운영 확인과 구분해 후속으로 남긴다. 변경 지식의 새Codex/실제고장,효과보상,의존스케줄러,일반문서AI추출 등 기존 전체 미결 유지. 강의자료/리허설 제외.

19:48 최종 배포 뒤 health/Kafka/Supabase 정상,20×/instance/legacy. PowerShell worker/scenario/probe0, 개인config SHA불변(`a043-runtime-final.json`). 최종 변경파일 diff --check 통과. PG전용 시험의 첫실패 fixture도 원문 보존 후 닫고 실제 재투영했다. 전체Goal은active다.

### A042 변경 업무 데이터와 Incident 포털 경로

MES6→36h는 기존카드400/새세대점수3.85→3.40,6→0h는 권고를 팬100+부하80에서 팬만100(4.02>4.00)으로 실제 변경했다. 포털의 선택만재작업 보류·rank재작업·역할403·새동의·효과후 재작업보류를 확인했다. 새세대 실제PLC ACK/합성CLEAR/재관측/실제CMMS/ev:closed도 별도 두번째 사례에서 확인했다. 카드 UI의 누락된 납기/품질 점수기여를 표시했다.

**검증 경계:** 합성경보/앞3작업 기록출력/실제DMNMCP다. 첫 사례는 CLEAR 누락으로 MITIGATION_FAILED→사람검토 ev:escalated(처음 finish exit1). 두번째는 검사기 nullable ACK 결함/조기 source복원으로 승인FAILED(처음 finish exit1) 뒤 수정·정확한원천재적용·포털동일승인재전달로 finish exit0다. 처음부터 무실패 전체완주나 새Codex/실제고장 검증이라 하지 않는다. 원시 a042-incident-ui/,a042-incident-clear/ 및 경위는 [REWORK A042](REWORK.md). 최종 원문/현재API·PG/원장 대조 **17/17 exit0**.

19:27 환경: health/Kafka/Supabase ok,20×/instance/legacy,PowerShell worker/scenario/probe0,개인config불변,전용브라우저종료. 실제PG 납기6/대상HYD-01 fan60/load90/pumpA/REMOTE_AUTO 복원 재확인. 두 사건/새 정의/결정/실패원문은 보존했다.

다음은 전체 요구표의 구조 미결을 진행한다. 새 지식/원천의 진단부터 새Codex 경로는 기존 정책 거절을 우회하지 않고 미검증으로 유지한다. 효과확인/보상·의존스케줄러·일반문서AI추출·전체graph outbox/복구와 남은 의미 연결이 있다. 강의자료/리허설은 수행하지 않는다.


### A041 포털 재작업 요청과 불명확 응답 복구

instanceRework.js의 영향/효과 확인·요청자/역할/사유·명시 확인·정확한 요청 ID 재시도와 sessionStorage 복구를 연결했다. 실제 브라우저에서 app.js의 삭제된 approve 함수 export가 초기화를 중단하는 오류를 찾아 제거했고 input/change 양쪽 상태 반영을 보강했다. 재작업 때문에 폐기된 승인과 인스턴스 종료를 구분해 표시한다.

가동 브라우저/HTTP **13/13 exit0**: 전송 전 연결 실패→새로고침→동일본문 재시도→세대1 한 번, 유효 선행7 복원/옛 DONE 원문 보존, 새 점수8/확인 제출로 정상 완료; 접수 후 응답 유실은 receipt 조회로 재전송 없이 복구; 실제 동시 사람 제출200 후 옛 미리보기 요청409/재검토; 390px 폼 넘침 없음/확인 후 제출 활성화; 초기 오류4건 외 추가브라우저 오류 없음. JS3개 구문 검사0. 상세와 주입기 자체의 최초 실패는 [REWORK A041](REWORK.md), 원시 증거 `.evidence/reaudit/a041-ui/`. 두 일반 정의 fixture는 정상 완료한 채 보존했다. Python 변경이 없어 A040 전체652를 불필요하게 재실행하지 않았다.

실제 Incident의 보류/이전 승인 폐기/새 판단 대기를 포털에서 직접 조작한 증거와 변경 원천/지식의 새 Codex→새 승인→PLC는 아직 없다. 다음은 그 시스템 연결과 효과 보상/의존 작업/AI문서추출/graph outbox이며 교재나 리허설로 넘어가지 않는다.

18:42 환경 확인: `a040-runtime-final.json`에서20배속/instance/legacy,healthz ok·Kafka/Supabase 연결,PowerShell 워커/시나리오/검사/배포 프로세스0,개인config SHA836330D5…불변. 가동 시험 사건은 원문을 보존한 채 정상 사람 검토 경로로 종료됐다. 별도 PG fixture는 운영 hyd tenant와 분리돼 있으며 실제 효과를 내지 않았다.

### A040 활성 사건 재작업 — 배포 및 실제 검증

원래 Incident/모든 관련 판단/기업 전체 원장을 대조하고, 효과 없는 승인 대기 사건에 새 판단 세대를 연결했다. PENDING/FAILED 원래 승인은 역할 검사 뒤 같은 PG 거래에서 폐기하되 payload/error/history와 SQLite 원문은 보존한다. 새 세대의 새 판단·새 사람 승인이 필수이며, 기존 효과가 있으면 보상 검토로 남긴다. 현재 인스턴스의 decision_id로 명령 대상을 선택한다.

최종전체652passed/경고2,process build/deploy0. 실제PG/SQLite/기업HTTP13/13(강제종료/rollback/동시replay/옛판단거절/새승인;PLC대역), 가동HTTP/PG/DMNMCP/Neo4j18/18(실제 세대1 새판단·별도사람선택대기·옛카드거절·정상검토종료;앞3작업기록출력). 실제Codex/세대1PLC완주는미검증. 첫PG9검사뒤의반복재작업결함과수정/원본은 [REWORK A040](REWORK.md)에 기록했다. 증거 a040-final-tests.*, a040-incident-pg-retry/, a040-incident-live/.

다음은 포털의 재작업 요청·영향/효과 검토와 실패/새판단 대기를 실제 사용 동선에 연결하고, 진단부터 변경 원천을 읽는 실제 실행을 확인한다. 효과 보상/의존 작업 스케줄러/일반문서AI추출/그래프 outbox도 남는다. 새Codex의 기존 도구 정책 거절은 우회하지 않았으며 가동MCP 검사를 Codex 성공으로 세지 않는다. 시스템 작업이며 교재·시수·강의리허설은 제외한다.


**A040 선행 구현 기록(이후 배포/실측은 위 참조):** 활성 Incident의 전체 원문/모든 판단/결정별 전체 기업 원장을 읽는 rework_effects를 연결했다. 효과·종료·미확인 기록이 있으면 보류하고, 새 decision 생산 활동을 포함한 영향 범위만 새 세대로 접수한다. PENDING/FAILED 기존 승인은 역할 재검사 뒤 같은 PG 거래에서 DISCARDED로 남기며 원래 payload/error/history와 SQLite 카드/사건을 보존한다. 승인에서 유래했다고 확인한 runtime 명령/선택 변수만 제거한다. 새 세대 사람 선택은 완료된 새 생산 작업의 decision_id를 요구하고 명령 발행도 현재 인스턴스 판단만 선택한다. 첫 관련42passed/기존경고2(a040-incident-first), 이후 미추적 승인 방어 1검사 추가. **미배포**, 전체회귀/실제PG·MCP 재작업 검증 대기. 효과가 이미 있는 사례의 보상과 의존 작업 스케줄러까지 완료한 것은 아니다.

18:24 최종 환경 `a039-runtime-final.json`: healthz ok/Kafka·Supabase 연결,20배속/instance/legacy,PowerShell 워커·시나리오·A039 검사 프로세스0,개인config SHA836330D5…불변. A039 가동 검사 인스턴스는 정상 사람 검토 제출로 종료하고 원문을 보존했다. 다음은 시스템 기능의 활성 Incident 재작업 연결이며 강의자료/리허설로 넘어가지 않는다.

### A039 판단 생산 작업 연결 — 가동 HTTP/PG/MCP 확인

종료된 프로세스의 Incident가 AWAITING_APPROVAL로 남은 경우 무scope 새 판단을 받는 반례를 추가 재현했다(1failed/23passed, a039-ended-red). 새 판단은409로 막고 기존 판단 ID의 중복 재전달은 원문/상태를 보존한다. 최종 전체 **632passed/기존 경고2, exit0**(a039-final-full.log/xml). process/dmn-mcp build 및 deploy 종료0이다. 최초 --profile cliagents 지정이 기본 프로필을 대체해 process 의존성 누락으로 build1이었고, .env 기본 프로필에 cliagents를 더한 환경으로 수정했다. 원래 실패 로그 a039-build.log는 보존했다.

가동 검사 a039-scope-live: MCP tools/list에 process_scope 노출, tenant/instance/generation/consumer/version/생산 작업 불일치6종409·저장없음, 실제 DMN MCP의 현재 원천 평가→새 판단 제출→정확한 scope 저장, 같은 live claim 중복 원문 보존, 다른 claim 중복 거절, legacy bridge 미개입, 실제 PG save_task_result→사람 선택 대기, 완료 claim의 늦은 새 판단 거절을 확인했다. 앞3작업은 A034 기록 출력의 명시 시험 재사용이다. 새 Codex 실행이나 활성 Incident 재작업 검증이 아니다. 실제 접수는 generation0이며 generation>0은 단위검사 범위다.

첫 검사 실행은 호스트 fastmcp 미설치로 인스턴스 생성 전에 종료1이었다. 서버 이미지의 설치된 fastmcp Client로 실제 HTTP MCP endpoint를 호출하도록 바꿨다. 다음 실행은9검사 통과 후 사람 폼에 허용되지 않는 escalated 필드를 넣어400/종료1이었다. note만 허용하는 정의 계약을 유지하고 검사기를 수정했다. 같은 보존 인스턴스에서 note만 제출한 후속 종료0으로 남은2검사를 확인했다. **합계11/11은 원래9검사+수정 후 동일 사례2검사의 합산이며 전체 검사기 단일 exit0 재실행을 뜻하지 않는다.** 실패 로그/전후 응답/수정 후 result-with-corrected-finish.json을 모두 보존했다.

instance anomaly_response.e3dfb2bb-e2ef-410d-b8c0-120e18bc9d36, Incident INC-1004-01-fe3d. 명시 시험 CLEAR가 실제 Kafka 접수 경로로 반영됐고 정의의 선택 시간초과→사람 검토 제출로 COMPLETED가 됐다. 명령/작업지시 없음, 종료 인스턴스의 새 무scope 판단409를 확인했다. 시험 원문은 삭제하지 않았다. 다음은 활성 Incident의 실제 효과·기존 승인 snapshot·새 판단/새 사람 승인을 재작업 세대에 연결하는 일이다. 의존 작업 스케줄링·전체 그래프 outbox·일반문서 AI 추출·남은 시스템 UI 검증도 남는다. 교재·시수·강의 리허설은 최신 사용자 지시로 범위 밖이다.


### A039 선행 기록 — 당시 단위/회귀 검증, 현재 배포 결과는 위 참조

활성 Incident 재작업의 선행 조건으로 `decision_scope.py`를 추가했다. 워커 task.json/context/prompt에서 tenant·instance·workitem UUID·generation·정의 판본·consumer를 전달하고 DMN MCP `submit_decision`이 origin.process_scope에 연결한다. process는 인스턴스 거래 안에서 현재 세대/판본/생산 작업/유효 claim을 대조한다. 새 세대의 rank 결과는 같은 작업이 새로 제출한 PENDING_APPROVAL 판단만 받으며, 기존 판단 ID를 다른 scope로 재사용하면409다. consumer 검사는 claim 경계이며 사용자 인증이 아니다.

레거시 replay/bridge는 새 세대나 명시 scope 판단에 개입하지 않는다. 기존 bridge 결과 저장에도 expected_consumer를 넣어 취소된 옛 claim이 결과를 덮지 못하게 했다. 세대0의 기존 무scope 레거시 호환은 유지한다. 재작업 세대 fixture를 직접 구성한 단위검사이며 활성 Incident 재작업 기능을 개방한 것이 아니다. `incident_rework_effect_contract_pending` 제한은 유지된다.

관련68passed/경고2(`a039-decision-scope-unit.log/xml`)에 이어 전체 **630passed/기존 경고2, exit0**(`a039-decision-scope-full.log/xml`)를 실제 실행했다. 범위: scope 불일치/옛 세대/비활성 claim/다른 생산 활동/기존 판단 재사용 거절, worker→MCP 전달, legacy replay 제외와 claim 취소 경합. 새 코드 **미배포**, 가동 HTTP/PG/MCP 및 새 Codex/PLC 경로 **미검증**이다. 이 결과로 실제 실행 성공을 주장하지 않는다.

다음: A039 process/dmn-mcp 배포 전에 종료 인스턴스의 무scope 접수와 중복 판단 호환 경계를 확인한다. 가동 HTTP/PG에서 명시 시험 입력으로 올바른 생산 작업 접수/잘못된 scope 거절/원문 보존을 검증하고 MCP 도구 schema를 확인한다. 이후 활성 Incident 효과 조회·이전 승인·새 판단/새 사람 승인을 연결한다. A033 Codex 실행의 정책 거절은 그대로 미해결이며 동일 경로 우회는 하지 않는다.

18:11 PowerShell Get-CimInstance에서 worker.main/scenario_instance_test.py 대상 Python/Codex 프로세스0을 확인했다. 현재 명령 승인 설정은 never/danger-full-access다. 사용자가 자리를 비워도 허용된 로컬 작업은 계속하며, 유료 결제·push·기존 개인 설정 변경은 사전 동의 없이 진행하지 않는다. 전체 Goal은 active다.

18:02 최종 환경: `a038-runtime-final.json`에서20배속/instance/legacy,healthz ok·PG/Kafka 연결,PowerShell 워커/검사/렌더 프로세스0,개인config SHA 불변을 확인했다. 포털 브라우저도 종료했다. 다음 단계는 아래 A038 미결부터 이어간다.

### A038 일반 정의의 새 작업 세대 — 실제 PG/HTTP/그래프 검증

migration00010은 인스턴스의 rework_generation/현재 요청 UUID, 작업의 generation/rework_request_id/supersedes_id, 불변 process_rework_receipt를 추가했다. 요청 UUID·미리보기 token·담당자/정의의 사람 역할/사유를 확인하고 같은 인스턴스 거래에서 재검사한다. 완료된 옛 행·출력은 보존하며 영향받는 live/TODO 행·타이머는 CANCELLED로 남기고 새 UUID와 세대를 만든다. 새 입력·query·선행 참조를 재구성하고 옛 claim/제출은 취소 상태로 차단한다. 세대 식별 정보와 요청 원문은 DB trigger로 변경을 거절한다. 같은 요청 재전달은 같은 접수 결과, 다른 내용 재사용/관측 후 상태변화는409, 정의 밖 역할은403이다. 역할 문자열 검사는 운영 신원 인증을 의미하지 않는다.

중간 작업이 같은 변수 이름을 덮어쓰는 반례도 처리했다. seed2→측정7→검토9에서 검토를 다시 하면 유효 선행 결과7을 복원한다. seed2를 항상 쓰거나 현재9를 재사용하면 잘못된다. 여러 선행 생산자가 순서상 비교되지 않으면 추측하지 않고 명시 검토로 남긴다. engine/rework planner/timeline/포털 단계는 generation 우선이며 rework_count는 기존 CMMS 동일요청 재전달 횟수와 혼동하지 않는다. 새 타이머도 요청과 세대를 이어받는다. Execution 투영은 모든 작업 UUID의 세대/이전작업/요청 ID를 보존한다.

관련24passed→전체608passed/기존경고2, 최종 그래프·타이머 보강 후 전체608 재확인(`a038-generation-first/full/final.log/xml`). migration00010 적용 및 process build/deploy 종료0(`a038-migration`, `a038-build/deploy.log`). 원문/기존 인스턴스는 삭제하지 않았다.

실제PG **10/10 exit0**(`a038-generation-pg/`): 자식 프로세스가 마지막 쓰기 후 commit 전에 os._exit(73)하면 작업/receipt/event 전체 rollback, commit 직후 os._exit(74)하면 새runtime에서 같은 결과 재개. 네 PG runtime의 replay가 한 receipt/이벤트를 반환했고 실제 old-worker RPC 결과는 거절됐다. 새 claim UUID→명시 시험 출력→다음 작업 참조→종결, SQL 세대/요청 변조 거절도 확인했다. 별도 retained tenant의 명시 시험 payload이며 Codex/PLC/그래프 대역 실행을 실제 에이전트 판단으로 쓰지 않는다.

가동HTTP/PG/Neo4j **11/11 exit0**(`a038-generation-http/`): 새3작업 정의 등록,2→7→9,검토부터 재작업입력7,옛DONE/선행작업 원문 보존,새timer/UUID,취소된옛사람제출400,잘못된역할403,요청ID다른내용409,동일요청4개 동시접수1회/같은결과,서로다른요청2개 동시접수200+409,process 실제restart뒤 전체행/receipt 동일,세대2에서11제출→COMPLETED. Neo4j에서 모든 UUID의 상태/세대/이전 작업 ID와 인스턴스 세대2를 실제 조회했다. 인스턴스 `rework_inspection_5ebe5c93.17f3683e-663e-42a9-a373-4012347095a8`은 보존됐다. 이는 Codex/활성 Incident 재작업 완주가 아니다.

포털에 현재 세대·작업별 세대/이전 작업 ID·재작업 요청 이력을 표시했다. 실제 인스턴스 탭→요청 연결 펼치기→1280×900/390×844 화면을 직접 확인했다(`screenshot-1791104272841.png`, `screenshot-1791104282402.png`).390 가로 넘침false,브라우저 종료. 첫 inline geometry 평가가 셸 quoting으로 실패해 base64 평가로 실제390/390을 다시 확인했다. 포털 요청 버튼은 아직 없으며 API로 요청한다. 예제정의/definition-authoring/교재13 `rework-generation-contract` 동기화,구조검사0문제,변경절1280/390 렌더 직접확인·넘침false(`a038-book-check`, `book-render/a038-*`). 전체 학생 리허설이 아니다.

남은 연결: 활성 Incident의 원래 효과/종료 여부, 이전 승인 snapshot과 runtime 명령 변수 무효화, 새 decision 생성·기존 decision 재사용 차단·새 사람 승인, 실제 Codex/MCP, 포털 재작업 요청 동선. 현재 Incident/기존 승인·효과가 있거나 시작점의 제어 흐름 밖 의존 활동이 필요한 계획은 명시 보류한다. 이 제한을 최종 범위 축소로 확정하지 않으며 실제 효과 확인/보상 계약과 의존 작업 스케줄러를 이어 구현한다. 전체 그래프 outbox·일반문서 AI 추출·전체 강의/리허설도 미결이다. 이전 Codex 실제 시나리오 도구 정책 거부를 우회하지 않았다.

### A037 재작업 영향 계산 — 실제 HTTP/PG 미리보기 검증

`procsvc/rework.py`와 `GET /api/instances/{id}/rework-preview?workitem_id=...`를 연결했다. 서버는 고정 정의의 모든 후행 가지, input/output 의존성, 분기 조건의 변수, boundary timer와 실제 reference_ids를 닫힌 범위가 될 때까지 추적한다. HYD 활동 이름을 고정하지 않는다. 같은 인스턴스 잠금에서 정의·작업·변수·승인을 읽고 상태를 바꾸지 않는다. 시작 snapshot과 비영향 DONE 생산자의 실제 UUID/판본/출력값을 대조해 재사용 후보를 만들며, 무효 출력과 같은 이름의 시작 입력이 있으면 그 원문을 복원 후보로 표시한다. 출처 불명·옛 입력 NULL·종료 인스턴스·동시각 최신 행 모호·기존 승인·시작된 서비스는 사유로 남는다. `snapshot_token`은 로컬 계획 근거의 해시이며 외부 효과가 없다는 증명이나 승인 토큰이 아니다.

ProcessGPT completion의 새 UUID·입출력 참조 코드(고정 HEAD b272c9ab…/process_engine.py818~927)를 다시 읽었다. 원문 열람을 원본 서비스 실행으로 쓰지 않는다. HYD의 `rework_count`는 `retry_work_order`에서 동일 CMMS 요청 재전달에도 증가하므로 새 세대 순서로 사용하지 않았다. 새 세대 식별자/접수 receipt/옛 작업 fencing은 다음 구현이며 현재 미리보기는 `execution_available=false`다. 권한 승인, 실제 효과 조회·보상, 새 Codex 실행, UI 버튼은 이 단계에서 수행하지 않았다.

신규16passed→전체600passed/기존 경고2(`a037-planner-unit/full.log/xml`). 전이 의존성, 분기조건만 참조하는 변수, 정의 밖 실제 reference, 잘못된 생산자/판본/값/상태, tenant/인스턴스 혼입, 타이머, 승인/서비스 기록, 같은 시각 행과 읽기 전후 불변을 검사했다. build/deploy 모두 종료0(`a037-build/deploy.log`). 실제 HTTP/PG **10/10 exit0**(`a037-planner-live/`)에서 새2단계 일반 정의를 등록하고 score2→사람 결과7→다음 작업의 입력을 확인했다. 미리보기는 원래2/무효화7/취소 대상인 현재 후행 작업을 구분하고 이전 DONE 결과·이벤트·변수를 변경하지 않았다. 외부 작업 ID는409, 기존 취소 사건은 원문없음/종료 상태를 유지했다. 일반 진행으로 score8을 제출해 accepted/COMPLETED로 끝냈으며 시험용 인스턴스 `rework_plan_b8b09342f5.3a79f1f1-884f-4b2c-9350-63ede5e960c5`와 원문을 보존했다. 새 세대 재실행 증거는 아니다.

최종20배속/instance/legacy,healthz ok/PG·Kafka 연결,PowerShell 워커/검사 프로세스0,개인config SHA 불변(`a037-runtime-final.json`). 최초 상태 확인 명령은 잘못된 `/health`로404였고 실제 계약 `/healthz`로 재확인했다. 서비스 장애나 기능검사 실패로 해석하지 않는다.

다음: 재작업 receipt와 명시 generation을 저장하고 동일 인스턴스 거래에서 관측 token/작업 ID를 재검사한다. 완료된 옛 행/출력은 보존하고 살아 있는 영향 작업·타이머는 fence하며 새 UUID와 유효 선행 참조를 연결한다. 기존 승인/runtime 변수는 원래 효과·권한 계약을 다시 확인한 뒤 폐기/새 판단에 연결해야 한다. 활성 사건의 실제 Codex/MCP→새 결정→새 사람 승인까지 미완료이며 이전 도구 정책 거부 경로는 우회하지 않았다. 일반문서 AI 추출·전체 그래프 outbox·전체 강의/학생 리허설도 계속 남는다.

### A036 시작 입력 보존과 변수 생산 작업 — 실제 기반 연결

재작업에서 누적 결과를 최초 입력으로 오인하지 않도록 `initial_variables`와 `variable_sources`를 연결했다. engine.new_instance가 전달받은 시작 입력을 깊은 복사로 보존한다. 업무 결과가 변수를 만들면 실제 workitem UUID/활동/정의 판본을 출처로 저장하고, 별도 서버 갱신은 runtime으로 구분한다. migration00009의 DB trigger와 MemoryRepo는 저장된 시작 입력의 교체/제거를 거절한다. 기존 인스턴스는 NULL로 남기며 누적 결과로 시작 입력을 추측하지 않는다. 이는 현재 값의 마지막 기록 출처이며 모든 외부 사실의 진실성/전체 변수 변경 이력까지 증명하지 않는다.

신규4검사 red 재현→관련51passed→전체584passed/경고2. 최초 red 중 World.items 검사기 오타를 World.rows로 수정한 뒤 기능4실패를 다시 확인했고 두 원본을 보존했다. 이미지 build/deploy는 subprocess에서 종료0을 확인했다. 실제 새 비HYD 정의를 HTTP로 등록/시작/제출한 **8/8**에서 입력score2→업무결과7→accepted, 시작2 보존, 생산 작업9d47b2bd… 연결, 실제PG 입력 변조/제거 거절, 기존 사건 입력NULL을 확인했다. 증거 `a036-provenance-live/`, `a036-provenance-unit/full`, `a036-migration.json`이다. 인스턴스 `provenance_a463e4c7a1.92497170-0dee-42ba-b072-a159463c50ce`를 보존했다. Codex/PLC를 수행한 검사는 아니다.

포털에 시작 입력 펼쳐보기와 현재 변수의 출처를 연결했다. 실제 클릭으로 score2/현재7/작업ID를 확인하고1280·390 화면을 직접 봤다.390 가로 넘침false. 최종 화면 screenshot-1791102680901/1791102664456이며 이전 인스턴스의 원문 없음 안내는 old-input-panel.txt로 기록했다. 브라우저 종료 확인. `docs/definition-authoring.md`도 같은 계약으로 갱신했다. 전체 교재/학생 리허설 검증을 뜻하지 않는다.

현재20배속/instance/legacy·health ok,PowerShell 워커/검사 프로세스0/개인 config 불변(`a036-runtime-final.json`). 이번 단계는 일반 재작업의 입력 기반이며 재작업 요청 API/새 작업 세대/재진단/새 승인까지 구현한 것은 아니다. 다음은 고정 정의의 흐름·input/output 의존성으로 영향 범위를 계산하고, 이 snapshot/생산 작업 ID에 근거해 재사용·무효화할 변수를 결정하는 계획기와 원자적 재작업 접수/세대 전이를 연결한다. 이전 입력이 없는 인스턴스에는 임의 seed를 채우지 않는다. A035 실패승인 폐기와 효과 확인 계약을 재사용하되 활성 사건을 CANCELLED로 끝내는 것으로 재작업을 대체하지 않는다.


### A035 실패 승인 폐기 — 실제 연결·검증, 일반 재작업은 미완료

승인 snapshot/error/history를 보존한 `DISCARDED`와 성공 완료와 구분되는 인스턴스 `CANCELLED`를 migration00008에 추가했다. 폐기 미리보기/실행은 동일 인스턴스 잠금에서 tenant·원래 승인 역할·FAILED/SUBMITTED·다른 승인/서비스 상태를 확인한다. 종료 사건이라도 명령/작업지시/기업 실행 또는 불명확한 기록이 있으면 거절한다. 요청자/역할/사유/요청 ID/효과 조회를 이력과 PG 이벤트로 함께 저장한다. 같은 요청은 같은 결과, 다른 요청은 충돌이며 폐기 후 재전달은 불가하다. 이전 DONE 작업과 원래 Incident/decision은 덮지 않는다. 이 로컬 역할 입력을 운영 신원 인증 구현으로 설명하지 않는다.

효과 조회에 최근300건 거래 목록을 쓰면 오래된 거래를 놓칠 수 있어 enterprise API에 결정 ID별 전체 원장 조회를 연결했다. PG는 decision_id 조건을 쓰고 목록 한도를 적용하지 않으며, 메모리 backend는 영속 멱등 원장을 읽는다. 조회 오류/잘못된 응답은 빈 결과로 바꾸지 않는다. 실제 기존 효과를 보상하는 기능은 아직 추가하지 않았고 해당 사례는 명시 보류한다.

신규검사 최초10실패→관련42passed→전체580passed/경고2. `a035-discard-red/unit/full` 로그/XML. 실제 PG/SQLite/기업HTTP **9/9**에서 마지막 쓰기 실패 rollback, 네 dispatcher 동시 요청 한 번 반영, 저장소 재개/멱등 응답과 명령0을 확인했다(`a035-discard-pg/`). 이 별도 tenant의 종료 사건/PLC/그래프는 명시 시험 대역이며 실제 HYD 실행으로 확대하지 않는다. fixture tenant와 원문은 보존했다.

가동 enterprise/process를 배포하고 과거 실제 실패 인스턴스 d6a2392c…를 포털에서 선택했다. 담당자/역할/사유 누락 안내→생산관리자 조회→기업 원장0건/종료 사건/남은5작업 확인→명시 폐기를 실제 클릭했다. 사전API **4/4**, 사후API **8/8**: 원래 승인·오류·Incident 원문 불변, CANCELLED/DISCARDED, 남은 작업 종료, 같은 요청 replay, 재전달409, 폐기 이벤트1건, Neo4j 취소/작업 상태 일치. `a035-discard-live/`에 전후와 실제 화면을 보존했다. 그래프에는 기존 사건 원천 누락 경고 `incident source not projected: INC-1004-07-b30f`가 남아 있어 전체 그래프 정합 완료는 아니다.

포털 폐기 상태의 실제 데스크톱/390 화면을 직접 확인했고 390 가로 넘침은 false였다. 앞 element 캡처는 고정 헤더에 일부 가려져 viewport 캡처 screenshot-1791101939468/9811을 최종 화면 근거로 쓴다. 브라우저 종료 확인. 교재13 `approval-discard-contract`에 필요성·원장 전체 조회·담당자 판단·동작과 재작업의 구분을 반영했다. 구조0문제, 변경절1280/390 렌더 직접확인/넘침없음(`a035-book-check`, `book-render/a035-*`). 전체 학생 리허설은 아니다.

process 실제 restart 뒤에도 CANCELLED/DISCARDED가 유지됐고 health ok,20배속/instance/legacy,PowerShell 워커/검사 프로세스0,개인 config SHA 불변이다(`a035-restart-final.json`). 최초 build 명령은 PowerShell stderr 취급으로 NativeCommandError/종료1이었지만 로그에는 두 이미지 Built가 있었고 그 이미지의 실제 recreate/API/재시작으로 배포를 확인했다. 실패 출력은 지우지 않았다.

다음은 REWORK 계약의 활성 사건/새 일반 정의에서 새 작업 UUID·세대·시작 입력/출력 출처·변경 원천 조회·새 판단/승인으로 이어가는 구현이다. 이번 명시 취소 기능을 일반 재작업 완료로 축소하지 않는다. 새 A033 이후 Codex 전체 실행은 기존 도구 정책 차단으로 미검증이며 우회 시도하지 않았다. 일반 문서 AI 추출·전체 그래프 outbox·전체 강의 검수도 남는다.


### A033 DB 연결 중단과 여러 설비의 접수 복구 — 15/15

`probe_source_connection_failure.py`를 실제 실행했다. process에만 시험 전용 TCP 중계기 DSN을 적용하고 중계기를 중지했다. 공유 PostgreSQL/Kafka는 계속 가동했다. handler에서 실제 Connection refused, receiver에서 DNS 접속 오류가 관측됐고 health ok=false였다. 세 설비의 서로 다른 경보와 동일 경보 중복 한 건이 Kafka에 발행됐으나 접수/사건은 생기지 않았으며, 두 시점의 process 그룹 committed offset은 네 원문을 넘어가지 않았다.

중계기를 다시 켜자 **process 컨테이너 재시작 없이** 세 원문 HANDLED/세 고유 인스턴스와 중복 한 건 DUPLICATE로 처리됐다. 네 Kafka 좌표가 보존된 뒤 offset이 전진했다. 세 사건은 원래 미지원 경보의 사람검토 경로로 갔으며 PLC 명령은 없었다. 명시 검토 결과까지 저장했다. 총15/15 exit0. 증거 `.evidence/reaudit/a033-connection-failure/`의 result/health-outage/offsets-outage/recovered-receipts/offsets-recovered 및 설비별 instance 원문이다.

finally에서 process의 원래 환경변수 전체가 같음을 확인하고 20배속/instance/legacy·health ok로 복원했다. 시험 label을 대조한 중계기는 제거했고 잔여0이다. PowerShell 워커/시나리오/검사 프로세스0와 개인 config SHA 불변은 `a033-connection-process-check.json`에 기록했다. 공유 DB 서버 자체의 장애·모든 네트워크 분할 유형·새 Codex 실행을 증명하지 않는다. 최신 A033 Codex 시작은 기존 정책 차단으로 계속 미검증이다.

다음은 CURRENT_APPROVAL의 완료 태스크 재작업 및 실패 승인 폐기/새 판단 경로를 ProcessGPT 원본과 대조해 설계·구현하는 것이다. 원천 접수 장애 검사만으로 전체 Goal을 완료하지 않는다.


### A033 저장 실패와 CLEAR·ACK 완료 경계 — 실제 검증

`probe_source_persistence_failure.py` 재검사 **10/10**: 시험 경보 한 건에만 PG INSERT 예외를 주입했다. 원문이 저장되지 않은 동안 실제 Kafka process 그룹의 committed offset이 경보를 넘어가지 않았고, 오류 제거 뒤 동일 좌표·원문으로 처리됐다. health에도 실패/회복이 나타났다. CLEAR 반영 후 접수 완료 SQL이 대기 중임을 확인하고 process SIGKILL과 해당 DB 연결 종료를 수행했다. 원래 접수가 2시도로 이어졌고 사건은 ESCALATED를 유지했다. 증거 `a033-persistence-failure-retry/`. 이것은 DB 전체 접속 장애가 아닌 범위를 한정한 실제 쓰기 오류다.

첫 `a033-persistence-failure/`는 7통과 뒤 2시도를 기대한 검사 1개가 실패했다. 앱을 죽인 뒤에도 DB가 이미 받은 완료 쓰기를 끝내 1시도 HANDLED가 됐다. 원본 실패/관측값은 보존했고 시험 사건은 명시 검토로 종료했다. 앱 종료가 DB 거래 중단과 같다는 가정을 폐기했다. 재검사는 대기 중인 정확한 완료 SQL/backend를 기록하고 그 연결까지 종료한 범위를 명시한다.

`probe_source_ack_recovery.py` **9/9** 및 설정 단계4/4: 실제 HYD-03 팬 결함→legacy 에이전트→사람 승인→팬40/부하80→PLC ACK 뒤 같은 완료 경계를 끊었다. 재시작 후 같은 ACK/명령 ID를 재처리했고 PROCESS_RESTART_REVIEW를 유지했다. Kafka action.cmd에서 CMD-1004-0001-28bd는 partition0/offset43의 **1회 발행**으로 확인했다. 사람 검토→ev:escalated, CMMS 가지 CANCELLED. instance39edd9a3…, Incident INC-1004-01-32e7. `a033-ack-recovery/`에 실제 command 메시지·접수·사건·결과를 보존했다. Codex를 쓴 검사는 아니다.

범위를 한정한 DB trigger/function은 모두 제거됐고, `a033-worker-preflight.json`에서 잔여 시험 함수0/기존 워커 대상 작업0을 확인했다. 첫 실패 원문을 성공으로 덮지 않는다. 이 단계는 수신 완료 거래의 재시도를 검증하며 Kafka의 모든 장애 유형이나 모든 외부 효과의 원자성을 증명하지 않는다.

### 최신 Codex 경로 — 실행 도구 차단으로 미실행

2배속/off로 바꾸고 Codex 워커 PID1916은 실제 기동됐다. 그러나 상태조회와 `run_scenario_evidence.py --worker --fresh-review --out .evidence/reaudit/a033-codex` 시작을 포함한 명령이 실행 도구의 `blocked by policy`로 거절됐다. 구체적인 사유는 제공되지 않았다. 현재 danger-full-access/never여도 이 거절이 발생했으며 사용자 승인 요청이나 우회 실행을 하지 않았다. `a033-codex` 결과 폴더도 생성되지 않았다. A03442/42를 새 A033 Codex 성공으로 재사용하지 않는다.

켜진 워커1916과 확인된 자식23512/21896을 종료했고 PowerShell로 remainingWorkers0/remainingTree0을 확인했다(`a033-worker-stop.json`). 개인 config SHA는836330D5…불변. process/plant/detector를20배속/instance/legacy로 복원했다. 다음은 독립적인 DB 접속 실패 검사 준비, 남은 일반 재작업/문서 추출/강의 요구 대조다. 같은 차단된 Codex 시작 명령은 정책 변화나 허용 확인 없이 반복하지 않는다. 전체 Goal은 active이며 이 차단 하나가 독립 작업 전체를 막지는 않는다.

**아래는 앞 단계별 실행 근거다. 현재 재개는 위를 따른다.**

A034 실제 Codex 경로는 **42/42, exit 0**이다. 네 작업 321초, MCP 시작/종료 25쌍, 명시 오류 0을 확인했고 사람 승인→PLC ACK→재관측→CMMS→종결/그래프까지 이어졌다. 원본 실패 A032 26/27은 별도 보존했다. 워커 종료 PowerShell 0과 개인 config 해시 불변도 확인했다(a034-codex/, a034-worker-stop.json).

A033은 public migration00007과 수신/처리/API를 배포했다. 전체563검사, 실제PG/SQLite+ASGI12/12, 실제Kafka·process 강제종료/재시작22/22(a033-kafka-recovery-retry/)를 확인했다. 접수 직후·claim 중·Incident만 저장된 경계를 검사했고, 중복/충돌/지연 CLEAR와 동일 사건 재연결을 확인했다. 첫 검사기의 상세조회 오류는 a033-kafka-recovery/에 보존한다.

배포 후 펌프·팬·경보 가림은20배속 legacy bridge에서 **37/37**이다(a033-pump-fan/checks.json, stdout.log). PowerShell에서 검사 프로세스와 워커가 남아 있지 않음을 확인했다. CMMS standby_ready는 원래 NULL로 복원됐다. Codex를 쓴 A034 경로와 새 A033 수신기를 쓴 이 회귀는 서로 다른 실행 증거다.

쿨러는5배속/instance/legacy에서 **42/42, exit0**(a033-cooler/)이다. 승인DELIVERED1회→CMD-1004-0001-2be1/ACK→재관측181초→CMMS WO-1004-F54F→ev:closed/그래프를 확인했다. 추가로 PG 인스턴스 저장 후 접수완료 쓰기를 막고 실제process를kill/start한 **10/10**(a033-kafka-after-instance/)도 통과했다. 같은 접수·사건·인스턴스로 복구됐고 추가PLC명령은없었다.

포털은 agent-browser 실제클릭으로 충돌3건 조회, FAILED의 담당자/이유 필수입력, 같은접수503/562재시도→HANDLED, 원문/정의/hash유지와실제triage생성을 확인했다(a033-source-ui/). 이 UI 시험의 실패는 명시 주입이며 실제DB장애가 아니다. 재시도후목록에옛실패표시가남는결함을수정하고 선택접수새로고침·모바일입력배치를 재검증했다. 390폭가로넘침없음/1280상세화면을직접봤다. 시험사건두건은원문보존후사람검토API로종결, PLC명령0. 브라우저종료확인. 세션중 errors 명령의 빈 오류 출력은 원인확인되지않았으므로 브라우저콘솔오류0이라고 주장하지않는다.

교재 정본은 D:/work/study/시스템교재/13_확장_ProcessGPT.html이다(docs/src/master_body.html 아님). source-receipt-contract 절에 접수/업무/회복구분·상태표·화면재시도·장애실험판단을추가했다. 구조검사0문제, 변경절1280/390렌더 직접확인/넘침없음(a033-book-check,book-render/a033-*). 전체교재직접검수나학생리허설완료가아니다.

최종runtime20배속/instance/legacy·health ok, PowerShell 워커/시나리오/복구검사프로세스0(a033-runtime-after-ui.json,a033-process-stop-check.json). 소스수정은문법검사와실제브라우저로검증했다. git diff --check는 기존 tests/test_guardrail.py:114, test_stability.py:157의 EOF빈줄을보고한다. 이번영향파일외기존WIP는고치지않았다.

남은 A033 경계: ACK/CLEAR 처리 중 hard kill, Kafka 접수 전 DB 실패, 새 수신기에서 실제 Codex 완주. 전체 강의 검수·일반 재작업·일반문서 AI 추출·전체 그래프 outbox 등 전체 Goal 미결은 계속 유지한다. 최신 권한은 danger-full-access/never이며 사용자 부재 중 일반 명령 승인을 요청하지 않는다. 새 결제·push·개인 설정 기존내용 변경은 별도 계약이다.

**아래는 단계별 과거 기록이며 현재 상태는 위를 따른다.**

**A033 연결 코드 작성(아직 미배포):** 원본Kafka bytes/tombstone 보존, HTTP의실제출처식별(가짜offset없음), timestamp기준최신상태보존, 같은접수정책으로InstanceRuntime 재진입, CLEAR/ACK 상관·재시작검토보존, 수신commit후offset확인, 접수API/명시재시도까지작성했다. 원천19단위·실제PG34/34(a033-wire-live), 연결26단위, 실제PG/SQLite7/7(a033-delivery-live) 확인. ASGI API추가검사(a033-delivery-api-live)와전체회귀 실행중이다. **migration00007은 운영 public에 미적용이며 가동process는A034이미지다.** 현재 실제Codex가 RE_OBSERVING이므로 서비스재생성/배포금지. 같은실행b9a9245a…/INC-1004-01-0765, 승인DELIVERED1회·CMD-1004-0001-76b3·ACK 통과, 종료/CMMS아직미정. a034-codex/result.json 최종판정과워커16124정리후 A033 운영migration→배포→Kafka/강제종료/재시작실측을이어간다. 원천API는작성했지만포털담당자화면미연결이다.


**15:15 현재 재개 — A034 배포 후 새 Codex 검사 실행 중:** 전체549passed/기존경고3(a034-regression.xml), 실제Pg+SQLite7/7 exit0(a034-guide-live). 기록된실제Codex출력을재사용해SQLite쓰기실패→PG진행정지, SQLite성공뒤PG실패→DONE롤백, 저장소재연결/새runtime→동일출력완료를확인했다. 실제Codex/PLC완주증거는아니다. process이미지262f6252…로배포했고2배속/off 상태다. 새워커PID16124/read_only/handled0 확인 후독립runner3044(실제Python21596)/scenario10252가15:14:01부터검사중이다. **a034-codex/scenario.log 및 result.json**을읽고동일실행을이어간다. 코드/서비스를검사중교체하거나새시나리오를중복실행하지않는다. 완료후원시trace·Incident·승인·CMMS·graph수집→워커16124자식종료/PowerShell0확인→20배속/instance/legacy/3설비정상복원이필요하다. 이전A032실패26/27은보존했다.


**현재 A034 — 실제 Codex 가이드 연결 결함 수정 중:** A032 독립실행9c8ee1ba…는4작업/MCP21시작·21종료 후 명시검토까지 통과했지만 `action FAN_SET is not on the guide card`로26/27 exit1이었다(`a032-codex-durable/result.json`). 실제 진단 가이드에는 commands가 있었지만 alertId가 없는 부분 경보를 hook이 거절했고, PG DONE 뒤 post-commit 예외만 기록해 빈 Incident 카드가 남았다. 승인/명령은0. 실패 원본·4세션 보존, 원래 사건과 후속 OVERHEAT 경보는 시험 reset/검토메모로 각 ev:escalated/ev:review-recorded 종결했다. 워커6932 자식 종료 및 PowerShell0·config불변 확인(`a032-durable-worker-stop.json`). 현재가동은 아직 수정 전2배속/off다.

A034 신규검사에서4실패를재현(a034-guide-red.xml)한뒤, 부분진단경보는기존원문에결합하되명시충돌/없는사건은거절하고가이드저장성공을PG DONE보다앞에두었다. 영향77passed/기존경고2(a034-guide-unit.xml). 전체검사 실행 중; 실제Pg/SQLite 경계검증 및 배포/새Codex완주는미검증. 변경전4파일a034-before보존.

A033 추가: 처리owner/lease/token·설비별단일claim·지연CLEAR/ACK·실패한도·명시재시도를추가했다. 독립실제PG28/28 exit0(`a033-claims-live`, schema a033_receipts_4651858ff42e). 운영수신루프/offset/runtime/API연결과강제종료복구는여전히미구현이다. A034 실제업무차단을먼저닫고EVENT_INBOX를이어간다.


**15:01 관측:** 새 독립 실행은 anomaly_response.9c8ee1ba-e7e3-41e3-a73d-e3823c721269 / INC-1004-04-1147이다. 진단 DONE/COMPLETED, 후보 조회 IN_PROGRESS/STARTED를 실제 API로 확인했다(`a032-codex-durable/current-instance.json`). 기존 검사 runner20504/scenario21500/worker6932를 유지하고 scenario.log 및 result.json을 읽어 이어간다. 성공을 미리 판정하거나 새 시나리오를 중복 실행하지 않는다. 완료 뒤 증거 수집/정상 환경 복원/PowerShell worker0 확인이 남아 있다.

**14:54 재개 상태:** 독립 검사 래퍼 PID5908(실제 Python20504), 자식 scenario21500이 14:50:11부터 기존 `scenario_instance_test.py --worker --fresh-review`를 실행한다. `.evidence/reaudit/a032-codex-durable/started.json`, `scenario.log`, 완료 시 `result.json`의 exit_code로 판정한다. 워커6932 유지/2배속/off이며 검사 종료 전 서비스를 재생성하지 않는다. 직전 시간초과 인스턴스의 실제 네 세션·MCP20시작/20종료·명시오류0은 `a032-codex-interrupted/`에 보존했고 업무 종결은 ev:escalated다. 아래 ‘재검증 준비’는 이전 단계 기록이다.

**A033 원천 접수 저장 단계:** source_inbox.py, migration00007, 검사기/단위검사를 추가했다. 단위12passed(`a033-source-unit.xml`), 실제 PostgreSQL 독립 schema에서14/14 exit0(`a033-receipts-live/`)로 같은 Kafka좌표/업무중복/원문충돌/tenant분리/CLEAR/ACK/8동시접수/새연결재조회/바깥거래내접수거부를 확인했다. 시험 schema a033_receipts_f706f0943c8b는 보존했다. public 운영 table에 migration 미적용, claim/retry/수신루프/offset/API 연결 미구현이므로 A033 전체는 미완료다. 자세한 다음 경계는 EVENT_INBOX.


**현재 재개 A032 — 검사 프로세스 종료/승인 시간초과 확인:** 두 번째 실제 Codex c7639223…는 네 agent task DONE/COMPLETED까지 도달했다. 도구 handle35976이 사라진 뒤 PowerShell에서 scenario_instance_test.py 프로세스 없음, worker PID6932/자식17776 생존을 확인했다. 승인 미제출로 14:43:54 KST 타이머가 DONE, task:select CANCELLED, task:escalate IN_PROGRESS였다. 원본 a032-codex-retry-after-deadline.json 및 a032-codex-interrupted-review.json에 보존하고 명령없음 확인→시험 설비reset→명시적인 검토 메모 제출로 ev:escalated 종결했다. 완주 성공으로 세지 않는다. 같은 검사기를 숨김 독립 프로세스로 실행하고 종료코드를 파일에 기록하여 도구 handle 수명과 분리하는 재검증을 준비한다. 현재2배속/off, worker6932 실행 중. Codex 단독3MCP/resume 성공과 첫 Neo4j initialize timeout은 별도 증거다. A033 source_inbox.py/migration00007/단위검사 초안은 파일 작성만 완료했으며 미검증·미배포·Kafka 미연결이다.

**A032 MCP 단독 원인 분리:** 동일 설정의 uvx stdio initialize는17.18초에 실제응답했다(a032-neo4j-stdio.json). 진단은 응답 확인 후 종료했으므로 child exit1/Windows async pipe 정리 경고도 원본으로 남긴다. 이를 Codex 도구 호출 성공으로 세지 않는다. Codex 자체의 세 MCP 조회/동일 세션 재개 검사를 새폴더a032-codex-standalone에 실행 중이며 결과미정이다. probe_codex_worker.py에--out을추가하고기존폴더덮어쓰기를거부하도록해과거증거를보호했다.

**A032 새 Codex 첫 실행 실패:** worker 자체 기동/claim은 확인했지만 첫 task:diagnose가 Neo4j MCP initialize60초 timeout으로 FAILED였다. 인스턴스1985ece4…/사건INC-1004-01-8e48, tool실행0/CLI세션0이며 a032-codex-first-failure와a032-codex-direct.stderr.log를 보존했다. 성공/완주로 세지 않는다. 완료 대기 검사는 실제FAILED 확인 후 종료(exit-1), 워커PID21744와시험 자식 종료·PowerShell0 확인(a032-codex-failed-stop). 설비는reset했다. 동일 테넌트uvx/fastmcp2.13.0.2/mcp-neo4j-cypher0.4.1의 stdio initialize 단독 측정 중(a032-neo4j-stdio). Windows 실행정책이나개인config는변경하지않았다. 포털연결도구는No browser is available을반환해직접클릭미검증이다.

**A032 실제 Codex 재검증 실행 중:** 승인 환경 변경 후 Start-Process 명령은 허용됐다. 첫 .ps1 래퍼는 Windows 실행정책으로 로드 실패(a032-codex-worker.stderr.log)했으며 정책을 바꾸지 않았다. 같은 환경의 Python worker.main 직접 기동은 새 승인 검토를 통과했고 health=ok/cli=codex/read_only/handled0을 확인했다(a032-codex-preflight.json). 기존 IN_PROGRESS7개는 모두draft_status FAILED여서 실제 claim 조건에서 제외됐고 재실행되지 않았다. 현재 plant/detector/process2배속, agent/process bridge off, `scenario_instance_test.py --worker --fresh-review` 실행 중(a032-codex-scenario.log). Python worker PID21744. 완료/실패 후 원시 세션·업무 결과를 보존하고 PowerShell로 워커 자식까지 종료 확인, 기본20배속/legacy/설비 정상으로 복원해야 한다. 개인config 변경 없음.

**A032 정상 회귀37/37 exit0:** `a032-pump-fan/run.log`, cases 및 fixture-before/after. 20배속 펌프/팬은 PS1·VS1 회복→실제CMMS→ev:closed, mask는 CLEAR 뒤 PS1=156.99<165여서 MITIGATION_FAILED→사람확인→ev:escalated/작업지시취소였다. standby_ready 시험값은 원래NULL로 복원됐다. 그래프 시험 부수경보 한 건도 원문 보존 뒤 사람확인으로 정리했다(a032-graph-live-fixture-review). PowerShell worker0/configSHA불변(a032-pre-codex-host). 새Codex 기동 전 기존 IN_PROGRESS cliagents 행7개를 발견해 작업 상태/claim 조건을 확인 중이다. 기존 작업을 무작정 실행하거나 없애지 않는다.

**현재 A032 — 새 실제 경보/그래프49/49 exit0:** `a032-triage-graph-live/`. 미지원 Kafka 경보와 세 PLC 고장→정확한 원문/사유→사람 검토→Process/Incident/Asset/WorkItem 연결을 확인했다. 기존 누락 네 건도 실제 원천으로 복구/재조회했다(`a032-graph-repaired.json`). 기본20배속/instance/legacy로 복원해 펌프·팬·mask 회귀 검사 중이며 그 결과는 아직 미정이다. 정상 쿨러5배속42/42, 전체528검사 후 추가 그래프 관련50검사 통과. 새 Codex 실행/포털 클릭 및 EVENT_INBOX·일반 재작업은 남아 있다. 아래 A032 항목의 진행 중/미배포 표현은 각 단계 당시 기록이다.

**A032 그래프 연결 수정 배포:** 관련50passed/경고2(`a032-graph-unit.xml`). Process seed에 proc:alert-triage와 안전목표를 추가하고 사건 생성/부분완료 재접수 시 원천 Incident를 먼저 기록한다. sourcePattern/sourceTrip/sourceAlert를 보존하고 INSTANCE_Q에서 사건 연결 누락도 경고한다. process 재빌드 및 plant/detector/process 20배속 재생성 exit0. 과거 네 시험의 실제 원문/PG 이력으로 그래프를 복구하고 새 Kafka/PLC 실행에서 연결까지 검증하는 단계다. 이 투영은 여전히 best effort이며 전체 graph outbox는 미구현이다.

**A032 정상 5배속 경로 42/42 exit0:** `a032-normal-scale5.log` 및 `a032-normal-scale5-final.json`. 인스턴스 20a901d3…는 현재 검토 REV-512f729f…→승인 DELIVERED→PLC CMD-1004-0001-958b→ACK→재관측→실제 CMMS WO-1004-B2B5→ev:closed를 확인했다. plant/detector/process 모두5배속이며 legacy bridge 실행이다. 앞선20배속 실패를 대체하지 않는다. 추가 그래프 검사에서 미지원 경보 네 건의 Process/Incident 연결 누락을 발견했다(`a032-triage-graph.json`). 새 정의의 ontology Process seed와 사건 생성 시 원천 Incident 투영, 누락 경고를 수정 중이며 아직 검증 완료가 아니다. 현재 승인환경은 workspace-write/auto_review로 바뀌었으나 새 Codex 기동 성공은 아직 확인하지 않았다.

**A032 실제 미지원 경보/PLC 검증 45/45 exit0:** 저장 동시성 수정 후 `a032-triage-fixed`에서 Kafka 미지원 경보·중복·늦은 가이드/결정 거절·SIGKILL/start 복구·사람 검토를 통과했다. 세 설비에 고장을 함께 주입해 LOW_PRESSURE_TRIP/HIGH_VIBRATION_TRIP/OVERHEAT_TRIP의 실제 PLC 사유→경보→사람 작업 원문을 확인했다. agent는 alert_policy 단계에서 WITHHELD였고 네 에이전트 작업/명령/CMMS는 생기지 않았다. reset 후 같은 ID/패턴의 CLEAR를 detector 로그와 사건 기록으로 확인했고, 사람 검토 완료도 사건 ESCALATED를 정상 회복으로 바꾸지 않았다. 다음은 새 2.1 정의의 정상 설비 회복 경로 회귀 검사다. 이 검사는 legacy bridge/API 경로이며 Codex/포털 클릭 증거가 아니다.

**A032 정상 경로 첫 검사 24/25 exit1:** `a032-normal-instance.log`에서 2.1 정의/네 legacy 에이전트 작업/역할검사까지 통과했지만 가열 중 기존 카드의 TS1/peak 예측이 악화되어 현재 승인 검사가 보류했다. 명령 ID는 없었다(`a032-normal-first-failure.json`). 이를 회복 성공으로 세지 않는다. 보호 기준을 완화하지 않고 `scenario_instance_test.py --fresh-review`로 현재 조건의 검토본을 먼저 저장·확인한 뒤 같은 SOP 값에 명시 승인하도록 검사를 확장했다. 재검사 결과 대기. HYD-02 CMMS standby_ready는 현재 null이므로 펌프 정상 시험은 명시 true fixture를 사용한 뒤 null로 복원할 예정이다.

**A032 20배속 새 검토 실행도 전달 FAILED:** `a032-normal-reviewed.log`/`a032-normal-review-failure.json`. 검토 REV-66c31643-83c5-4d02-8ed9-6c4f971258bc 접수 뒤 현재 TS1 예측 악화로 승인 전달이 실패했다. Incident INC-1004-07-b30f/인스턴스 d6a2392c…에는 명령이 없다. 완료 대기가 무의미한 실패 검사는 원본 보존 후 정확한 Python PID만 종료하고 PowerShell 0개를 확인했다. 검사기도 전달 실패 시 즉시 실패하도록 변경했다. 이 보류 승인/작업은 임의 DONE 처리하지 않고 실제 미결 사례로 유지한다. 실패 승인의 폐기/재검토는 일반 재작업 구현에 포함한다. 다음 정상 시험은 plant/detector/process 모두 5배속으로 고정해 수행한 뒤20으로복원한다. 원천 이벤트 유실 경계는 [EVENT_INBOX](EVENT_INBOX.md)에 미구현 설계로 기록했고 일반 재작업보다 우선 조사한다.

**A032 배포/실행 단계:** 전체 527 passed(경고 3), 포털 JS 구문 통과 후 agent/dmn-mcp/process/detector 재빌드·기동 exit0. HTTP 현재 정의 2.1을 확인했다. 계약은 [ALERT_ROUTING](ALERT_ROUTING.md). `probe_alert_triage.py` 실제 Kafka 미지원 경보/중복/늦은 결과/프로세스 재시작/세 PLC 원인별 TRIP·CLEAR·사람 검토 검사가 진행 중이며 결과 미정이다. 새 Codex/포털 직접 클릭의 미검증 상태는 유지한다.

**A032 첫 실제 실행 exit1 보존:** `a032-triage-live/`에서 Kafka 미지원 경보/중복/늦은 가이드·결정 거부/process SIGKILL-start/사람 검토 종결과 세 물리 고장 주입 15개 검사는 통과했다. 목록 API의 card=null을 검사기가 경보 원문으로 읽어 물리 TRIP 확인이 timeout됐다. 설비는 finally reset됐다. 제품 실패나 전체 통과로 쓰지 않는다. 상세 API로 수정한 `a032-triage-verified/` 재검사 진행 중. 첫 물리 시험의 검토 작업은 원본을 보존한 뒤 명시 사람 검토로 종결할 예정이다.

**A032 재검사 실제 결함:** `a032-triage-verified`는 16개 확인 후 exit1. 동시 PLC 경보 중 SQLite snapshot 직렬화가 `dictionary changed size during iteration`으로 실패하여 저압 Incident만 생기고 PG 인스턴스 생성은 rollback됐다. 제품 결함으로 기록한다(`a032-concurrent-process-failure.log`). 두 스레드로 사건 저장 중 새 사건을 추가하는 `test_store_concurrency`도 같은 오류 1 failed를 재현했다(a032-store-red). Store 저장 락 안에서 목록 멤버십을 먼저 복사하고 직렬화/저장을 순서화하도록 수정, 재검증 중이다. 일반 시작 이벤트의 durable inbox/재시도는 아직 없으므로 이 수정만으로 전체 이벤트 유실 복구가 완료됐다고 쓰지 않는다. 이번 orphan 원문/ID를 보존해 명시 재접수하고 사람 검토로 정리할 예정이다.

**A032 저장 수정 배포 후:** 전체528passed 후 사건 목록 조회/카운터 보강 관련66passed, process 재배포 exit0. 실패 시험의 10건을 원문/이전상태와 함께 `a032-failed-fixtures-before/review.json`에 보존했다. orphan 저압 INC-1004-01-973f는 같은 원문으로 명시 재접수하여 사람 검토로 종결했다. 다른 미지원 사건도 ev:review-recorded, 두 정상 패턴의 시험 잔여 건은 ev:escalated로 종결했으며 실제 회복/설비 명령 승인을 주장하지 않는다. 새 실제 검사 `a032-triage-fixed/` 진행 중. 교재13 새 미지원경보 절 구조0문제, 1280/390 정적렌더 확인. 첫 캡처의 sticky header 겹침은 캡처 viewport/스크롤을 수정하여 재확인했고 포털 직접 클릭은 하지 않았다.

**진행 A032 — 관련 단위 검사 65 passed, 미배포:** 모든 PLC TRIP을 OVERHEAT_TRIP으로 발행하고 없는 사유를 OVERTEMP로 채우던 결함, 미지원/누락 패턴에도 TS1<55를 적용하던 결함을 수정했다. 새 정의 anomaly_response 2.1에 세 지원 패턴의 회복 기준과 alert_triage 1.0 사람 검토 경로를 명시했고 2.0은 보존했다. 사건은 생성 당시 회복 기준을 저장한다. 미지원 경보의 원문을 사람 작업 입력으로 제공하며 늦은 가이드/결정은 원천 경보와 검토 상태를 바꿀 수 없다. 원천 CLEAR 수신은 기록하지만 사람 검토/ESCALATED를 정상 회복으로 바꾸지 않는다. 첫 전체 검사 a032-first는 501 passed/4 failed(종전 잘못된 기본값 검사 2개, 패턴 없는 정의 버전 fixture 2개), 수정 후 관련 검사 a032-targeted는 65 passed다. 새 경보 정의/저장 복구/원천 보존/명령 없는 검토를 포함한다. 다음은 전체 검사와 서비스 배포, 실제 Kafka 미지원 경보 및 PLC 원인별 TRIP, 기존 정상 경로 확인이다. 현재 배포 환경은 아직 A031이다.

**재개 위치 A031 12:52 — 변경조치 검토의 구현/검증 범위 완료, 전체 Goal active:** `DECISION_REVIEWS.md`가 현재 계약이다. 전체505passed(경고3), legacy 우회차단 preview 추가 관련20passed, JS순수컴포넌트10/10. 실제5배속 instance24/24(WO-1004-19B2), 검토저장뒤process SIGKILL/start28/28(WO-1004-400F), legacy HITL17/17(WO-1004-70CE). 모두95/78의PLC/재관측/실제CMMS종결을확인했다. 70/90의온도제외,다른값94/권한/facts override/수동모드/완료후재사용거부를포함한다. 20배속첫실패와legacy준비전연결종료 원본은그대로남겼다. 성공조건을20배속이라고바꿔적지않는다.

**다음 구현/확인:** 미지원경보(TRIP 등)가쿨러회복기준으로기본처리되는경계를고치고, 현재선택검토와구분되는일반완료태스크재작업을설계/구현한다. 완료이력/승인outbox/이미발행한PLC를덮지말고원본처럼새작업ID/회차를만들어야한다. `CURRENT_APPROVAL.md`에추가원본열람을기록했다: completion b272c9a compensation_handler1~132/compensation1~178 전체, process_engine818~1033. 자료복사/SHA는a031-reference-review. 이식전효과소유권/업무취소/동시성/정의고정을확인한다. 원본보상분기의관측없는파일삭제나SQL역변환을PLC보상으로사용하지않는다. 일반문서Codex추출/참조중SOP판본/전체outbox와claim복구/실제포털클릭/75시간강의검수도남아있다. 새Codex는이전기동자동심사거절후미실행이며우회하지않는다.

**복원/전달 증거:** a031-runtime-final(12:51)에서instance/20×/legacy,설비3RUN/REMOTE_AUTO/열화0,PowerShell worker.main0,개인config SHA불변. a031-fixture-cleanup은이번실패의5d571f12/f4c24194만원본보존뒤관리자확인/ev:escalated로정리했다. 교재13현재승인/예측/변경안3절은구조0문제와1280/390정적렌더6개직접확인. 포털문법/순수컴포넌트검사는실제브라우저클릭을대체하지않는다. 작업중서비스/검사프로세스는남기지않았으며서비스스택은다음작업을위해기동상태다. 집계는a031-summary.json,관련29파일SHA는a031-files.json이다. diff --check의두EOF빈줄은이전test_guardrail.py/test_stability.py이며A031에서새로발생한것이아니다.


**검증 A031 12:42 — 실제 검토 저장/강제종료 복구 28/28:** 5배속 새 사건에서 검토 생성 뒤 process SIGKILL/start를 실행했다(a031-review-restart/). 검토본이 남고 사람 선택은 IN_PROGRESS/명령 없음, 같은 review ID의 명시 승인 뒤 실제fan95/load78·ACK·재관측·CMMS·ev:closed까지28/28 exit0다. 앞선 일반 변경안24/24(a031-review-scale5, WO-1004-19B2)와 구분한다. 다음은 legacy HITL의같은계약을검사하기위해 process만legacy로잠시전환하며, 종료뒤instance/20배속/legacy bridge로복원한다. 교재13의현재승인/예측/변경안3절은구조0문제와1280/390정적렌더6개를직접확인했다. 원본completion보상본문추가열람은CURRENT_APPROVAL과a031-reference-review/manifest에기록했다. 실제새Codex/포털클릭/일반재작업은여전히미완료다.

**진행 A031 12:33 — 변경값 실제 PLC ACK, 재관측 중:** 추가 가드레일을 포함한 Linux 전체 **505 passed**(경고3, a031-container-all-final). 5배속 실제시험(a031-review-scale5)은 기본100/80과별개인95/78 검토 저장,70/90 예측차이/온도규칙제외,수동모드에서기존검토거절,선택유지/무명령,복원뒤새검토의명시승인과실제PLC ACK까지 통과했다. 실제설비status도HITL/fan95/load78로확인했다. 현재재관측/CMMS종결대기다. 포털 JS 문법/실제응답을쓴순수컴포넌트10검사 통과(a031-review-component), 브라우저렌더/클릭은아니다. 계약과미완료범위는 DECISION_REVIEWS.md. 다음은최종종결과검토저장뒤실제process강제종료/재시작후같은검토승인검사다.

**반례 A031 12:25 — 첫 실제 통합 실패를 보존:** `a031-review-instance/`는 검토 생성/원본 보존/다른 값400/낮은 역할403/facts override409/두 입력별 예측 변화까지 확인했다. 모델 키를 `model`로 오기한 검사 1건은 실제 계약 `model_id`로 수정한다. 여러 반례를 연속 수행하는 동안 20배속 사람기한30초를 넘겼고, stale select 클라이언트20초 요청이 시간초과(exit1)됐다. 서버 감사에는 REMOTE_MANUAL 및 예측 악화에 따른 allowed=false가 남았으며 승인/outbox/명령은 생성되지 않았다. `a031-review-timeout-window.log`와 원본을 보존했다. 후속은 명시적으로 plant/detector/process를5배속으로 맞춰 사람기한120초 조건에서 재검토/실행을 시험한다. 규칙·인터록·예측 허용차는 완화하지 않는다. 시험 후20배속 복원한다. 생성된 주 사건5d571f12와 TRIP 후속f4c24194는 이 실패의 fixture이며 원시상태 보존 후 관리자확인만 정리한다.

**진행 A031 — 변경 조치의 새 검토 구현, 아직 미배포:** 팬/부하 변경값을 현재 원천·모델·규칙으로 다시 평가하고, 원래 결정과 별개인 불변 review를 SQLite에 저장한 후 사람이 그 review를 승인하도록 연결했다. review는 인스턴스/작업/결정/선택지와 원래 결정 SHA에 묶이며, 승인·전달·최종 명령에서 현재 조건과 정확한 조치값을 다시 검사한다. 기존 SOP 원문은 보존한다. Linux 격리 단위시험 **503 passed, 경고3**(`a031-container-all-second.xml/log`). Windows 기존 psycopg DLL 로딩이 앱 제어에 막혀 최초 수집 exit2, 첫 Linux 검사도 httpx 누락으로 수집 실패했으며 두 원본을 보존했다. 보안 설정은 변경하지 않았다. 포털 입력/검토 연결을 마무리한 후 배포·실제 변경값/오래된 검토/완주 검사를 진행한다. 일반 완료작업 재작업과 실제 새 Codex 워커 검증은 별개이며 미완료다.

**재개 위치 11:51 — A030 기본조치의 동적예측 연결 검증, Goal active:** 현재코드는단위491passed(기존경고2), 실제legacy bridge쿨러40/40·펌프13/13·팬12/12·mask14/14, 변경값/모드거부8/8이다. mask는PS1 157.17bar로경보만꺼져도MITIGATION_FAILED→관리자확인→ev:escalated였고작업지시분기는취소됐다. 상수Forecast를runtime fallback으로쓰지않고Asset 명시모델을적용한다. `FORECAST_MODEL.md`가현재계약/실행표다. 종료상태발행누락과검사기의ACK동시성/모드복원가정실패로그를보존했다.

**A030 당시 다음 구현(이후 A031 기록은 위 참조):** 변경fan/load→해당조치로새예측·규칙검사→사람이새카드를검토→그불변스냅샷과정확히같은명령을선택/전달/발행하는경로를연결한다. 지금 `instances.select`/legacy HITL은기존카드와다른값을거부한다. 이거부를제거해곧바로실행하거나facts override로우회하지말것. 원SOP의범위/정책과검토한effective actions를구분하고UI에서도기본예측을변경값예측처럼보이지않게한다. 현재cardHtml에는예측입력/범위/구간최대를추가했고JS문법만검사했다. 새카드보관/선택스냅샷의원자성·재시작은설계후실제로검증해야한다. 일반재작업은원본completion의compensation_handler본문/권한·동시성과HYD승인소유권을더읽고완료된작업/승인outbox를덮어쓰지않는새workitem으로설계한다. FORECAST_MODEL의필수작업3·4후속이며1·2와기본값실행만현재검증범위다.

**종료상태/증거:** `a030-card-runtime-final.json`(11:49)에서instance/20×/legacy·3RUN/REMOTE_AUTO/열화0·PowerShellworker0·configSHA불변. 알려진이번시험용확인작업4건은원본보존뒤사람확인으로ev:escalated종료(`a030-fixture-cleanup.json`). 세정상실행의결정/승인/outbox/CMMS원문은`a030-card-executions.json`, 관련파일SHA는`a030-card-files.json`. 교재13의forecast/current-approval두절은구조0문제와1280/390렌더직접확인했으나실제포털클릭/새Codex완주를대체하지않는다. 자동승인거절의우회·개인설정변경·결제·push는없다. git diff --check의기존EOF2건(test_guardrail/test_stability)은남겨뒀다.


**승인반례 11:47 — A030 변경조치/모드8/8:** 실제fan95는기본100카드예측으로접수되지않고선택유지/무명령, 수동모드도거부했다. 최초6/7은모드를복원하면반드시허용된다는옛검사가실패했다(a030-stale-actions): 그사이모델입력유온54.713→57.235℃로악화해원래재검토기준을넘었다. 허용차를늘리지않았다. 복원된모드제외해제와남아있는예측악화를구분하고현재원천으로새읽기판단을요청해평가허용을확인했다(a030-stale-actions-final8/8). 기존선택을새카드로교체/승인한검사가아니다. 팬도12/12·CMMS WO-1004-88A9·종결완료. mask(경보해제와실제압력미회복의구분)검사는현재진행중이다.


**실제경로 11:42 — A030 펌프13/13:** 종료상태즉시발행수정과압력수집관찰후 `a030-pump-final/`13/13 exit0. CMMS준비=true를명시적시험조건으로설정하고원값복원했다. 실제PUMP_SELECT B,0.54초뒤181.93bar,PS1재관측181.68bar,CMMS WO-1004-56AE,ev:closed. 쿨러는앞서40/40(legacy bridge). 관련규칙/스킬SHA도현재배포돼변경후새검토를강제한다. 최초6/8·수정뒤12/13 실패는그대로보존한다. 전체491검사, 교재13구조0문제/1280·390정적렌더직접확인. 팬실행중이며조치값변경미리보기/일반재작업/새Codex는미완료다.


**반례/수정 11:35 — A030 실제펌프6/8 실패:** 쿨러새모델기본값경로는40/40으로실제CMMS영수증WO-1004-BB6C후종결했다(a030-card-instance.log). 그러나펌프기본300sim초램프는끝났는데plant.status10초heartbeat전까지이전진행중목록이남아3후보모두제외됐다(a030-pump-instance/원본카드·설비·사건보존). CMMS true명시fixture도원값복원했다. Plant.inject/_apply_fault의시작/종료에dirty_status를표시하는수정을추가했고, 예측실패에도원천스냅샷/조치/출처를남기도록보강했다. 관련규칙/스킬SHA를카드에저장하여아직발동하지않은임계값변경도재검토한다. 이추가수정은재배포/재검사대기다. 펌프성공으로표시하지않는다.


**진행 11:30 — A030 카드/현재승인 연결 배포·경계검증:** 단위489passed(기존경고2), 배포HTTP/MCP/Neo4j경계9/9, 현재업무원천7/7, bound forecast도구8/8 exit0. 펌프온도는현재모델에서계산되며명시적CMMS준비=true이면현재승인검사를통과하고false/null이면거부한다. 모델판본불일치·진행중램프는상수fallback없이제외, 복합냉각/베어링에서는온도예측이안전해도HIGH_VIBRATION으로제외했다. 실제MCP submit의facts덮어쓰기는INVALID이며결정무생성. 증거 a030-card-all-fixed, a030-cards-live, a030-card-sources, a030-bound-tools. 최초전체검사2실패는변경값95즉시실행을기대하던옛검사와스키마파생파일누락이며원본로그보존후수정했다. 아직실제경보/승인/PLC완주는이코드에서검증전이다. 변경값미리보기/재작업미완료도그대로다.


**진행 11:25 — A030 카드 연결 구현 중(미배포):** Asset 모델ID/판본/범위/예측시간을 명시하고 단일 원천 스냅샷으로 카드별 예측을 계산하도록 연결했다. decide·MCP·현재승인검사가 같은 제공자를 쓰며, 원천/모델 실패와 예측 인터록은 카드를 제외한다. live submit의 가정 facts 덮어쓰기를 거부한다. 승인한 카드와 실제 명령값 일치 검사를 추가했다. 변경값의 새 카드 미리보기는 아직 연결 전이므로 이 단계에서는 다른 값의 실행을 거부하며, 이를 범용 작업 완료로 세지 않는다. 검사와 실제 배포는 다음 단계다. 예측 시각/TS1 변화는 명시한 재검토 정책으로 판정하고 모델·조치·열화/운전설정 변화는 재검토 대상이다.


**환경·교재 확인 11:11:** `a030-runtime-final.json`에서instance/20×/legacy, 설비3기RUN/REMOTE_AUTO/열화0, PowerShellworker0, 개인config SHA불변을 확인했다. 교재13 `forecast-input-contract`에 입력/가정/조치변경/예측-관측 비교 실습을 추가했고 구조0문제·1280/390 정적렌더직접확인했다. 모델과판단카드의연결미완료를본문에도표시했다. git diff --check는기존test_guardrail/test_stability EOF2건만남는다. 새글로벌설정/결제/push는없다. 다음은FORECAST_MODEL의카드/승인연결5조건이며독립조회검사를완료판정으로확대하지않는다.

**진행 11:08 — A030 독립 예측/API/MCP 검증:** 전체471passed(기존경고2), 실제3설비로컬패널/600sim초 관측16/16 exit0, 실제HTTP+MCP호출8/8 exit0. 온도오차는각0.00295/0.00393/0.00374℃이며범위는교육용시뮬레이터다. 모든모델입력/가정/버전/조치/원천시점을반환한다. `forecast_actions`는읽기만하고설비/결정을변경하지않음도확인했다. 새Codex실행은아니다. [FORECAST_MODEL.md](FORECAST_MODEL.md)의5개연결조건이후속이다. **카드/승인은아직정적Forecast를사용하므로펌프보류가해소되지않았다.** 모델을관측가능하게검증한단계이며, 다음은모델바인딩/동일제공자/변경제어값미리보기·재검토다. 자동심사거절은우회하지않는다.

**진행 11:00 — A030 독립 모델 구현:** 회의386~404의설비/업무현재입력요구와열평형/압력/진동실제식을대조했다. common/hydcommon/forecast.py는SOP/패턴정답표없이현재부하·팬·냉각성능·누설·베어링·펌프·주변온도·선택조치에서시간후온도/압력/진동을계산한다. 모든입력/모델ID/진행중열화/미지원명령을검증하며 WO요청을물리정비완료로해석하지않는다. PLC상태에모델ID·동일시점TS1·주변온도·열화진행필드를추가했다. 독립시뮬레이터시간적분과24조합을비교한관련56검사는통과했다. **아직카드/승인/MCP에연결하지않았으며펌프보류는해소되지않았다.** 이제실제시뮬레이터3설비의로컬패널조치/응답을모델과비교한다. 예측성공을HITL전체성공으로표시하지않는다.

**환경 확인 10:52:** `a027-runtime-final.json`에서instance/20×/legacy·PowerShell worker.main 0·개인config SHA불변을 확인했다. 정상실행의현재조건검사감사3개는 `a027-instance-current-checks.json`, 최종Instance/Incident/CMMS ref는 `a027-instance-final-*.json`에 보존했다. 이번실험의고정5인스턴스만원시상태저장후열린fixture검토4개를종결했고모두COMPLETED(`a027-fixture-cleanup.json`); 다른인스턴스는변경하지않았다. 교재렌더는정적HTML추가절이며포털클릭검증이아니다. 남은diff --check EOF2건은기존test_guardrail/test_stability이며이번에수정한test_cards의EOF는정리했다. 다음세션은CURRENT_APPROVAL의A030/재작업/미지원경보부터이어간다.

**진행 10:49 — A027 현재승인 실제 검증 / A030 미해결:** 전체431passed(기존경고2), 실제 모드 변경·복원5/5(`a027-stale-final/`), 실제legacy bridge 인스턴스40/40 exit0(`a027-instance-fixed.log`, instance e9966fde-ac15-42a4-9b02-91bbd204e592, INC-1004-03-b84f, CMMS WO-1004-98F6) 확인. 첫정상실행39/40은 선택응답직후 동기명령발행 가정만실패했고 물리경로는종결했다. 원본보존후30초한도관찰로검사기를수정했다. 현재조건 불명확한 EXCLUDE/PENALTY는보류, WARN불명확은카드에공개하여기존동의내용과비교한다. 원천실제변경7/7은MES납기/CMMS true·false·null/복원검사이며 **펌프완주가아니다**. 펌프의필수forecast_ts1이없어 NO_FEASIBLE_OPTION인 A030을발견했다. 첫원천시험exit1도보존. [CURRENT_APPROVAL.md](CURRENT_APPROVAL.md)에계약·근거·한계를정리했다. 교재13 current-approval-contract 1280/390 직접렌더확인·구조0문제. 다음은 정의/승인/실행이력을보존하는재작업설계, 예측입력·유효조건, 미지원경보 회복기준이다. 새Codex는자동심사거절로미실행이며우회하지않는다.

**진행 10:33 — A027 연결 / 단위 검증:** 현재조건 API→process fail-closed 어댑터→선택·전달·명령 직전 검사 연결. 기존 raw approve는409로 닫고 포털의 원자 명령 승인 버튼을 제거했다. CMMS standby_ready를 nullable 원천 필드로 추가했으며 기존DB의NULL을 임의True로 채우지 않았다. QMS 누락 수량도0으로 간주하지 않는다. 신규 상태변경/전달전변경/최종명령/우회방지 검사와 전체430passed(기존경고2) 확인(`a027-all-tests-fixed.xml`). 초기 전체3실패는 기존 fake CMMS 응답과 receipt 테스트의 명시적 원천대역 누락이었고 원본로그 보존. 이제 실제배포/반례재시험 단계이며 성공판정 전이다.

**진행 10:25 — A029 실제 복구 / A027 실제 반례 확정:** process 재배포 뒤 기존 정지 인스턴스의 rank DONE·select IN_PROGRESS·agent task_started 4개를 확인했다(`a029-recovered-instance.json`). 동일 판단을 새로 제출한 결과가 아니다. 두 번째 stale 승인 시험은 실제 REMOTE_MANUAL 상태에서도 HTTP 성공·CMD-1004-0001-f47a 생성·선택 소비로 **0/3, exit1**이다(`a027-stale-second/`, 원본 응답/설비/게이트웨이/감사 보존). PLC 후단 거절과 사전 승인 차단은 구분한다. 현재조건 도우미16검사 통과는 API 연결 전 증거다. 선택 접수·승인 전달·명령 직전 연결을 수정 중이며 새 배포 결과는 아직 없다. 원자 명령만 보내는 옛 승인 API도 SOP/역할 검사를 우회하지 않도록 폐쇄하고 포털 경로를 맞춘다.

**진행 10:17 — A027 시험에서 A029 발견:** `probe_stale_approval.py` 첫 실제 실행은 선택 작업까지 가지 못해 exit1이다. legacy 판단 DEC-1004-001-5411은 제출됐지만 instance7b7dab8f-0d0f-4a52-ace5-5d7ccabb2e1a의 rank가 IN_PROGRESS로 남았다. 원시DB/API/로그는 `a027-stale-first/`. 현재 승인 방어 통과로 표시하지 않는다. 브리지의 일시적인 빈 claim 뒤 재개 경로가 없었고, 저장된 판단과 전체 task_started 출처를 읽어 재개하는 poll 경로를 추가했다. Codex 출처는 legacy로 인수하지 않으며 이벤트500건 한도도 사용하지 않는다. 신규반례2실패→관련10검사통과(`a029-unit-final.xml`), 실제배포복구는 다음 단계다. `agentsvc/approval.py`는 현재조건 재검증 설계 초안이며 API/실행 연결 전이다. 워커 시작 정책거절은 우회하지 않는다.

**환경·다음 조사 확인 (2026-10-04 10:01):** `a026-runtime-final.json`에서 instance/20×/legacy, PowerShell worker0, 세 설비RUN, 개인config SHA불변을 확인했다. `a026-graph-cleanup.json`의 문서 시험 소유노드는0이고 원문·배치 이력은 보존했다. 최신 교재구조검사도0문제다. git diff --check는 이번 단계에서 건드리지 않은 기존 test_cards/test_guardrail/test_stability의 EOF빈줄3건 때문에 깨끗하지 않다. 다음 A027 조사 시작점은 `approval_hooks.DecisionDelivery.validate`다. 현재 본문은 Incident/asset/state와 action범위만 검사한다. 최신 설비·업무·규칙 조건의 재검증 필요성을 실제 반례로 검증해야 하며 아직 A027 완료가 아니다. 새 Codex 시작과 포털 직접클릭의 정책 제약은 유지된다.


**현재 재개점 09:56:** A026 API/원문/검토/원자적적재/최신판본부터되돌리기 배포검증. 전체403후 파서3자리단계 개선 영향40passed, 실제Neo4j/SQLite17/17·HTTP21/21(실제서버재시작)·기존매뉴얼시나리오7/7·105단계HTTP4/4·형식거절3/3. 문서/코드/증거는 MANUAL_INGESTION. 첫scenario harness는7검사뒤summary()없음exit1,105단계 첫조회는지원하지않는GET개별경로405로3/4; 두오류수정후실제재실행/원본실패로그 모두보존. 교재13장구조0/추가절1280·390직접확인,JS문법통과; 포털직접클릭은아니다. 원문과배치이력보존,시험그래프는되돌림. worker0/기본20×legacy/instance이며 Codex실행거절을다른호출로우회하지않았다.

**이어갈 일:** A026 실제일반문서 에이전트추출→원문좌표검증→사람검토 연결은 아직없다. 현재파서는구조화문서만다룬다. 정책거절이해소되지않아도 A027현재조건/오래된승인·미지원경보, 일반claim/outbox등의독립조사·구현은계속할수있다. 전체Goal이blocked/complete인것은아니다. 새Codex실행결과가없는상태에서A025이전성공을신규코드증거로재사용하지않는다.


**A026 연결 단계 09:40 (당시 상태):** 원문 인용 검증/검토 플랜(`manual_review.py`)과 문서소유 그래프의 원자적 개정·최신판본부터 되돌리기(`manual_graph.py`)를 추가했다. 독립 원문+검토35검사, 전체398passed/기존경고2. 실제Neo4j/SQLite17/17(`manual-graph-live/629F7E5CBE/report.json`), 시험소유노드0으로 정리했다. 중간실패/두문서 같은절/다른SOP소유권/외부규칙/속성변경/개정복원/8경쟁자를 포함한다. 구형부분저장API를 새`manual_api.py`로 교체했고 보관원문/재검토/개정/되돌리기 UI를 작성했으나 아직 배포·HTTP실측·JS검사 전이다. 실제Codex 일반문서추출/포털직접클릭은 미검증이며 구조화번호문서 파서를 LLM추출이라 부르지 않는다. 변경전5파일은 `a026-connect-before/manifest.json`에 보존했다.

**현재 진행 09:25:** A028 실제20× 인스턴스40/40·직접legacy48/48 모두 exit0. 실제영수증/종결시각은 `legacy-receipts/`와 `a028-instance/receipt-check.json`4/4에 보존했다. 전체382검사·실제Pg/SQLite/HTTP6/6·JS문법통과, 교재13장1280/390 정적렌더 확인. 새 Codex 실행은 숨김 PowerShell worker 시작 명령이 자동 승인 심사에서 `blocked by policy`로 거절돼 미실행이며 우회하지 않았다. instance/20×/legacy·설비3기RUN·PowerShell worker0·개인config불변 복구(`a028-restored.json`). 다음은 A026 원문/검토/원자적적재 연결이며 포털직접클릭/A027/전체강의 검수도 미완료다. [WORK_ORDER_RECOVERY.md](WORK_ORDER_RECOVERY.md) 참조. 아래08~09시 기록은 당시 상태다.

**A028 구현 단계 (배포 전):** 실제 불일치2/4를 보존하고 신규수용검사7실패를 재현했다(`a028-red.xml`). 재관측은RESOLVED에서멈추며 실제CMMS ref로만WORK_ORDER_CREATED/CLOSED를 기록하도록 수정했다. 승인옵션의actions를버리던선택변수도고쳐명시된WO내용을보존한다. 새`work_orders.py`는원문요청을SQLite에먼저보존하고동일요청재시도/실제응답저장실패복구를담당한다. 레거시도실제CMMS와동일내용재시도API를연결했고WO-only를거부로종결하지않도록수정했다. 관련13검사통과(`a028-api.xml`), 직전전체374검사는추가6검사전이다. 실제Pg/SQLite/HTTP 장애시험·컨테이너배포·물리경로/교재/UI 확인은이어갈일이다. 가동컨테이너는아직이전A025이미지/20×legacy다.

**현재 재개점 (2026-10-04 08:36 KST):** A025 승인전달 실제Codex38/38 exit0, 원시trace/네세션/승인·Incident·CMMS·graph 보존(`a025-codex/`). worker/자식0, 기본20×/legacy·3설비RUN 복구. A026 원문 모듈19검사/전체367은 서비스 연결 전이다. 새 실제 결함 A028을 우선 추적한다: `machine.on_timer`가 실제 CMMS 응답 전에 임시 작업지시를 만들어 Incident를 닫고, `instances._run_work_order`는 별도 실제 작업지시를 낸다. 승인된 후속 정비 입력/실제 응답/Incident·인스턴스의 종결/실패·재시도 경계를 함께 고칠 필요가 있다. 증거 `a028-work-order-observation.json`; 아직 A028 코드는 바꾸지 않았다. [문서 계약](MANUAL_INGESTION.md)의 A026 연결·원자 적재·개정/되돌리기·실제추출은 이어갈 일이다. Goal active; 이전단계는보존본/AUDIT.

**08:28 진행:** A025 새 실행666d3935-cd1b-4b15-bf3b-e82b2d4dfcd1은 실제Codex 네 작업269초, 승인DELIVERED/attempts1, PLC ACK 뒤 재관측 중이다. 최종 판정 전이며 가동 코드는 바꾸지 않았다. A026 [문서 계약](MANUAL_INGESTION.md)과 독립 `manual_sources.py`를 작성해 원문/개정/페이지/인용/tenant/동시저장/롤백19검사 통과(`a026-sources.xml`), 전체367검사/기존경고2개(`a026-source-regression.xml`). 생성한 두 페이지 PDF는 렌더 직접 확인했다. PDF는 좌표 검사용 합성자료이며 현장 매뉴얼 정확도 증거가 아니다. 원천 모듈은 아직 API/graph/실제Codex 추출에 연결하지 않았다.

**08:40 추가 검사:** `probe_work_order_consistency.py`로 실제 API/CMMS를 읽어 **2/4, exit1** (`a028-closure-first.json/log`). 실제 CMMS 존재·태스크 완료시각은 통과, Incident 참조 일치·실제 CMMS 뒤 종결은 실패다. 새 검사는 읽기 전용이며 기존 실패를 재현했다. 다음 구현에서 이 두 실패와 CMMS 장애/재시도·WO-only·legacy를 함께 고친다. 아직 가동 구현 변경 없음.

**08:36 결과:** 위 A025 실행은38/38 exit0. MCP 시작20/종료20, 네 raw ExecEvent와Codex rollout의명시오류0, 실제모델gpt-5.6-sol4세션. 450초첫관측TS1=52.71/CLEARfalse→150초연장→51.49/CLEARtrue, 총601초후ev:closed다. 승인전달1회·실제CMMS1건을 확인했다. 단, A028 실제값/시간 불일치가 추가로 확인돼 전체 업무 종결정합성 통과로 확대하지 않는다. 개인config SHA256 836330d564fe7cbd72946985bfa2ca90bd1b7eac22aa5aa6143489972cd0db0a 불변.

- **A021 첫 수정:** 실행용 timer/service SQL조회, 인스턴스별 원자 전이/만료 승인/콜백재조회. 단위326, 실제Pg11/11(FakeHooks), 실제PLC ACK 후 process kill/start38/38→PROCESS_RESTART_REVIEW/명령1회/사람확인/ev:escalated. 실행 ac514778-4e59-49c4-b60b-69884d9fb597, `a021-live-restart.log`.
- **실제 Codex가 드러낸 교착:** c1cabf20-7981-44a7-bef9-dc6c8f731fef의 compliance 결과저장 FAILED. todolist AFTER UPDATE 부모갱신트리거와 부모→자식 엔진잠금이 반대였다. 이 실행은 실패 그대로 보존(`a021-deadlock/`, `a021-codex-worker.stderr.log`). 중단worker0/자식0/설비reset 기록 `a021-deadlock-stop.json`. 첫 Pg검사가 이 경로를 놓쳤다는 사실을 유지한다.
- **교착 수정/배포:** migration20261004000004와 PgRepo에 부모먼저 잠금을 통일했다. 이전코드7경로교착재현→수정후7/7, 기존claim범위7/7, Pg복구11/11, 질문Pg4/4, 전체334 passed/기존경고2. `process-lock-order*.json`, `a021-lock-process-build.log`. 일반stale30분/5분점검과 외부state/outbox 원자성은 남아 있다.
- **A024 실제 Codex 질문 두 건:** codex-human-355872d8 동일정의의 A/B. 각 HUMAN_ASKED→worker PowerShell종료0→pending파일이름변경으로cache부재→새worker→답변API→기존CLI세션→실제enterprise SELECT→DONE. A HYD-02/pump, B HYD-03/fan. 잘못된질문ID409/답변200/중복409. 질문/세션/event/알림 원자DB저장·DB세션재개·명시업무질문제어응답을 구현했다. `codex-human-355872d8/report.json`, raw session-evidence-A/B. 모델gpt-5.6-sol. 역할승인/CLI권한확대와 구분한다.
- **A024 UI 경계:** 포털선택지와설명을수정하고 JS문법검사는통과했다. 자동승인검사가 agent-browser 명령을 거절했고 CUA에사용가능브라우저가없어 직접클릭검증은미완료다. 답변API는테스트드라이버가호출했다. 사용자재승인문제로오해하지않는다.
- **A021 수정 후 실제 검증/정리 완료:** `a021-lock-codex-scenario.log`36/36 exit0, 2884980d-60ed-4882-8b9f-a9bbe76cfb08/INC-1003-01-1844/CMD-1003-0001-d45c/WO-1003-53C4. 4작업248초·4CLI gpt-5.6-sol·MCP18시작18종료/오류0. 450초 첫판정52.61℃/CLEAR아님→150초연장→51.42℃/CLEAR/종결. `a021-lock-codex/`에4원시CLI·4ExecEvent·최종instance/graph/Incident/audit/enterprise 보존. 08:03 PowerShell worker0/자식0,20×/legacy·3기RUN복구,사용자configSHA불변. A022의 과거36/36과 별도 실행이다.
- **후속 A025 반례:** MemoryRepo+실제decision/hooks에 승인 직후 instance저장실패를 주입하니 decision APPROVED/선택 IN_PROGRESS로 갈라지고 재시도는 decision is APPROVED로거절됐다. `approval-atomicity-observation.json`; 실제DB/PLC장애는아니다. decision/Incident/외부조치/outbox 계약, 오래된 승인/미지원TRIP, SOP/나머지회의요구·레포·교재검수는계속진행한다. 이번관찰로가동중코드를변경하지않았다.
- **후속 A026 SOP 반례:** 다른문서의같은절ref가동일ID가되고, 잘못된스킬검증400전에절MERGE가호출됨을순수함수/가짜_q로관찰했다(`manual-ingest-observation.json`). 실제Neo4j변경은하지않았고미수정이다. 원문/판본/절위치와A004배치소유권을연결할후속근거를AUDIT/REPOSITORY_REVIEW에기록했다.

**A004 첫 수정 결과(04:09 KST):** `ddl.py` SQLGlot AST, ingest 물리 ID/변수·schema/datasource/catalog보존, 입력 검증, 매개변수 SQL, 원천별 query 분리, API 한 그래프 트랜잭션, 포털 원천 연결/DB입력 추가. 수정 전 신규 반례4failed → 관련10passed → 전체 **275passed,2warnings**. 실제 배포 API→Neo4j→PostgreSQL **8/8**: 두 다른 schema의 동일 quoted표/열이 분리되고 값2/20에 대해 조건<8 결과가1행/0행. 변조된ID·불법연산자400. 시험7노드·임시schema2개만 정리(`ingest-identity-live.json`). build로그상 이미지/기동 완료·현재healthy지만 PowerShell 래퍼 exit1도 기록해 성공종료로 바꾸어 쓰지 않음. 포털 원천입력 실제 UI검수 및 배치 재적재/되돌리기 소유권은 다음. API실측으로 A004 핵심충돌은 해결했으나 전체인제스천완료는 아님.

- [x] G0 목표 등록·원문 보존: GOAL 현재 계약 갱신. 원문 2 전체 559행 읽음(HYD 1~461행). ZIP 지도 47개·67관계·내부 경로 8·미확정 4 확인. `scripts/audit_source_inventory.py` 실행: 원자료 56파일 해시 보존, 기존 참고 레포 17개 커밋·상태 확보, 이번 사용자 발화 10개 + 환경 컨텍스트 1개 보존(C01은 발화가 아님, 번호 유지). 증거 `.evidence/reaudit/2026-10-04-baseline/`, 원문 `docs/handoff/sources/`. 이것은 코드 전수 검토나 실행 검증 완료가 아니다.
- [~] G1 요구·관련성·현재 구현 대조: AUDIT.md를 작업 원장으로 사용. 기존 REPO_GAP는 이전 담당자의 대조 기록으로 유지하며 새 확인과 구분한다. 다음: 47개 관련성 분류 → 온톨로지/인제스천/실제 질의/프로세스 실행의 코드 경로 대조 → 반례 시험으로 현재 결함 확정.
  - G1 진행: `REPOSITORY_REVIEW.md`에 47개 전체 조사 목적 분류(코드 전수검토 아님). ontology-studio 구축/적재 루프와 completion 서비스 실행 원본을 커밋 고정해 읽음(AUDIT 읽기 범위). 이번 기준 단위 **259 passed, 2 warnings**. 추가 인메모리 반례 **0/5 기대 충족**: DDL 스키마 식별 충돌, service task ID 변경 시 정지, 다른 정의의 ontologyRef 무시, 완료 뒤 경보 중복 시작, 작업지시 실패에도 성공 종결. 결함 A004~A008, 원시 JSON 및 명령은 AUDIT에 기록. 앱 수정 전 원본 계약·다운스트림 영향 조사 중.
- [~] G2 확인된 결함을 관련 레포의 계약과 구현에 맞춰 교체·보강. 첫 묶음: instances.py의 서비스/선택폼/Incident 콜백을 tool 계약으로 전환, ontologyRef·tenant를 투영에 사용, 작업지시 실패 결과를 error 이벤트에 보존하고 재시도 3회 뒤 PENDING으로 차단(DECISIONS 16). 수정 전 계약 검사 5 failed/11 passed → 수정 후 관련 22 passed → 전체 **263 passed, 2 warnings**. `tests/test_instances.py` 신규 4개 및 기존 오류 상태 기대 1개 교정. A005/A006/A008의 함수 수준 확인이며 DB/PLC 통합은 다음 줄 결과를 기다린다. A004/A007은 미수정.
  - process 재빌드/기동 성공(`.evidence/reaudit/process-build.log`). `scenario_instance_test.py` 레거시 다리 회귀 **35/35 PASS, exit 0**(`.evidence/reaudit/service-contract-instance.log`). 실제 승인·PLC ACK·57초 재관측·CMMS WO-1003-AEFB·Execution 투영 확인. Codex 워커 실행 증거가 아니다.
  - F 1~3 진행: 설치 cliagents의 McpServer는 stdio 전용(기존 F의 HTTP 지원 설명 정정). bridge에 Codex 호출별 TOML override(stdio+HTTP) 추가, 사용자 config는 읽지 않되 기존 인증/세션 저장소 유지. Claude만 allowedTools 전달. upstream parser의 thread.started.session_id 확인; Codex 0.151 resume 앞에 exec 옵션을 두는 adapter 추가. 테스트/실행 결과는 후속 기록.
  - F 1~4 추가: 워커 단위 16 passed, 전체 265 passed. 최초 실제 단독 실행 실패: 두 HTTP MCP는 fastmcp/uvicorn websockets-sansio 충돌, Neo4j stdio는 fastmcp API 변경으로 기동 실패. fastmcp 2.13.0.2 고정·HTTP ws none·tenant neo4j uvx 의존성만 변경 후 HTTP healthy. 다음 실행에서는 session 재개/사용자 config SHA256 불변 확인했으나 실제 도구 3개 실패(APOC 없음/approval never) — 성공으로 판정하지 않음. 실패 원시 `codex-mcp-startup-failure.log`, `codex-tools-first-failure.jsonl`. APOC 설정 및 tenant 도구 승인 설정 수정 후 재검증 중.
  - F 4 완료: `scripts/probe_codex_worker.py` exit 0. 세 MCP 실제 호출 성공·실패 0, Neo4j 라벨 38, 동일 session `01a102ef-d0bc-7c63-afbd-5712fc28f0a7` 재개 확인. 사용자 config SHA256 `836330d564fe7cbd72946985bfa2ca90bd1b7eac22aa5aa6143489972cd0db0a` 전후 동일. `.evidence/reaudit/codex-probe/{events.jsonl,summary.json}`. 오류 RESULT/시작 stderr 검증 추가 후 워커 18 passed. F 5 시작: process AGENT_BRIDGE=off, WORKER_URL=host.docker.internal:8097, 호스트 Codex worker(read_only), 로그 `codex-worker.log`. 실제 시나리오 결과 대기.
  - F 5 첫 실행은 진단 기록으로 중단: 레거시 agent가 여전히 같은 경보에 카드 제출함, 작업 run이 상위 개발용 AGENTS를 상속해 인계 문서를 찾음. diagnose는 실제 Codex MCP로 DONE, 이후 테스트/워커 트리를 PowerShell로 종료 확인(remainingWorkers=0, `worker-stop-first.json`), 플랜트 reset. 첫 인스턴스 `anomaly_response.d2e44432-de92-4663-93d0-5a6e049e53ad`/이벤트는 `codex-first-instance.json` 보존; 중단된 candidates는 FAILED로 보존(자동 재수행 방지). agent consumer는 instance+bridge off에서 레거시 자동 파이프라인을 건너뛰도록 수정; Codex project_doc_max_bytes=0 + 업무 지침/스키마를 프롬프트에 직접 제공. 새 clean 실행 중: `codex-worker-clean.log`, `codex-instance-clean.log`. PowerShell 호스트 스크립트는 프로세스 한정 `-ExecutionPolicy Bypass -File scripts/run_worker_host.ps1`로 시작(시스템 정책 변경 없음). 전체 **267 passed, 2 warnings**.
- [~] G3 Codex 실제 워커와 세 MCP, 변경 정의·데이터·지식 및 오류/승인/복구 경로 실행. F의 2배속 쿨러 경로 35/35 완료(아래 결과). 정의·데이터 변경과 예외/복구를 포함한 전체 G3는 미완료.
  - F 5 두 번째 20배속 시도: 실제 에이전트 지연 중 OVERTEMP TRIP 및 정지 유량을 누설로 오인한 후속 경보로 큐가 증가. 완료 아님. PowerShell 워커 종료 0 확인(`worker-stop-second.json`), plant reset, 이번 진단 6개 instance snapshot/중단 이벤트 보존(AUDIT A011). 2배속으로 plant/detector/process를 함께 재기동; 시나리오 physical timeout은 scale 비례, 성공 기준 유지. 다음 실행 로그 `codex-instance-scale2.log`, `codex-worker-scale2.log`; worker reasoning low 명시. 남은 안전/지연/중복 경보 계약은 이 성공 여부와 별도 해결 대상.
  - A011 코드 수정(현재 실행 컨테이너에는 아직 미반영): 펌프 CEP에 running 조건을 전달, STOP/TRIP/UNKNOWN에서는 새 누설 RAISE/기존 누설 CLEAR 모두 금지, 미발행 후보는 취소. 원본 온톨로지 condition도 동기화. 실제 관측값(PS1=155.47, FS1=0, LoadSP=90, leak=0) 반례 및 기존 누설 유지/재기동 회복 테스트 추가. 펌프+워커 관련 **37 passed**(`pump-stopped-unit.xml`). 통합 시험 중 detector를 재시작하지 않으며 이후 별도 실제 검증 필요.
  - 실행 중 추가 수정(아직 컨테이너/호스트 워커 재기동 안 함): 명령 없음/명령 ValueError/응답 cmdId 없음은 명령 DONE 대신 서비스 오류·PENDING으로 처리, 관련 17 passed(`command-failure-unit.xml`). worker에는 UI 요약 외 원시 cliagents 이벤트 JSONL 파일을 보존하도록 추가(테스트 확인). 직전 전체 검사 268 passed는 명령 수정 이전 결과다. 현재 2배속 instance `anomaly_response.1dfcaa53-0ba0-4d6d-844d-3a9ad4bb6035`, incident `INC-1003-01-fd51`; diagnose/candidates/compliance 실제 제출 확인, rank 진행 중.
  - F 종료 후 실제 배포: process/detector/agent/plant 재빌드·healthy, 기본20배속/legacy 복구. 완료 이벤트 재전송 HTTP409, 실제 PLC STOP→유량0→400모의초 관찰 중 누설 IDLE, plant reset **4/4 검사 통과**(`post-codex-live.json`). Neo4j pump rule도 RUN 조건으로 좁게 갱신(`pump-graph-rule.json`). 명령 오류와 이벤트 중복 방지 코드 배포됨. 신규 원시 worker JSONL 보존은 단위 검증이며 재실행 통합 검증은 아직 없다.
  - A007: 실제 PostgreSQL 16동시 요청/롤백/재시도/테넌트 분리 등 **7/7**, 전체 단위 **271 passed, 2 warnings**. 마이그레이션 20/20 기존 사건 ID backfill·중복0; 위 HTTP409도 배포 후 확인. Incident/graph 외부 저장까지 exactly-once 보증한 것은 아니다(DECISIONS18).
  - A004 배치 소유권: 기존 첫 생성자 `ingest_batch` + DETACH DELETE를 제거하고 원천 속성·출처 관계의 활성 배치 이력 및 이전 상태를 한 Neo4j 트랜잭션으로 저장. 동일 배치 내용 재전송은 멱등, 내용 변경/되돌린 ID 재사용409, 최신 배치 취소 시 이전 상태 복원, 앞 배치 취소 시 후속 배치 유지. 다른 규칙의 참조/수동 속성 변경/구버전 무이력 배치는 충돌로 보존한다. 실제 Neo4j `probe_ingest_ownership.py` **15/15 PASS**: 중복/수정/역순 복원/기존 관계 속성 보존/중간 실패 전체 롤백/8개 동시 적재·삭제. 시험 정확한 ID만 정리(remaining0). `.evidence/reaudit/ingest-ownership-live.json`. 마지막 외부 속성·레이블 보호 보강은 추가 검증 예정. schema.json2.4.0에 물리 원천·이력·기술 기록 클래스2개를 명시하고 파생 스키마 재생성. API/포털 배포와 전체 회귀는 다음.
  - A004 완료 범위 추가(04:35 KST): 최종 Neo4j 소유권 검사 **18/18**(활성 journal canonical schema 포함), 배포 HTTP **12/12**, 새 구현에서 실제 PostgreSQL 질의 **8/8**, 전체 단위 **276passed/2warnings**. process 최종 build/start exit0(`ingest-ownership-build-final.log`). 포털 실제 업로드→적재→외부 속성 수정→되돌리기409/데이터 유지→시험 속성 해제→되돌리기5노드 삭제 확인. 화면 `ingest-ownership-ui-{conflict,clear}.png`, 브라우저 세션 종료. 배치 영수증은 설계대로 CLEARED로 보존한다. 교재13장 §6도 물리 identity/공유 소유권/복원으로 수정하고 SQL생성API와 미완성 LLM동적 실행을 구분했다. check_book0문제,1280/390 hscroll·broken·console error0; 변경된 그림/표 직접 확인. A004를 SOP 적재/임의 원천의 자동 연결까지 완료했다는 뜻으로 확대하지 않는다.
  - A013 발견/교정: 실제 그래프 535노드/1574관계에서 Execution 클래스·관계가 canonical schema에 빠져 **1195검증위반**(반복된 계약 누락) 확인. ProcessGPT vue3 `d88f78c` SCHEMA.md §1/4.2/4.4/5.4를 대조해 HYD Process·Task·Role/System 어댑터 의미를 명시하고 schema2.4.1에 ProcessInstance/WorkItem/관계 선언. EXECUTES/INSTANCE_OF의 source·target을 단순 합집합으로 완화하지 않고 endpointPairs로 교차 오연결 거부. 실제 전체 그래프 **schema0/integrity0**, 단위276passed. 원시 전후 `ingest-schema-validation.json`, `execution-schema-live.json`. 이는 데이터 의미의 진실/정의 버전 격리/투영 완전성까지 입증한 것이 아니다.
  - 정의 버전 고정 1차(A014): 변경 전 반례4failed → 관련50passed → 전체280passed/2warnings. `proc_def_version(version_tag=hyd-immutable)`에 tenant/definition/version별 내용 불변 저장, 현재 proc_def와 분리. 런타임의 submit/poll/timer/tool/화면/투영 및 worker capabilities는 인스턴스/작업의 고정 버전을 정확히 조회한다. 없는 버전은 최신 정의로 대체하지 않는다. 실제 PostgreSQL8/8: 기존/새 버전 실행, 기존 워커 모델 설정, 내용 덮어쓰기 거절, 누락 버전,16개 동시 등록의 한 내용만 승리, 다른 정의를 같은 런타임이 처리. 시작이벤트 DB7/7 재회귀. `supabase migration up --local` exit0로 20261004000001/000002 이력까지 적용. 현재 정의1개를 legacy-current로 백필했으며 과거 실행 당시 바이트가 같았다고 증명할 수 없다. 실패로 보존한 기존 인스턴스6개는 RUNNING + agent draft FAILED(consumer없음)이고 자동 성공 처리하지 않았다. 새 process build/start exit0, API 기동/실제 시나리오 후속 확인 필요. graph task ID 버전격리/빈 bindings, 정의 등록·시작 API/UI, 폼 계약 버전 고정은 아직 후속이다.
  - A014 배포 후 검증: `definition-deployed-api.json` healthy/instance/PgRepo/legacy20×, 기존 F 성공 인스턴스 COMPLETED·timeline9 확인. `definition-legacy-scenario.log` **35/35 PASS, exit0**: 네 작업(legacy 다리)→운전원403→관리자승인→CMD-1003-0001-8ec5 ACK→재관측→CMMS WO-1003-C837→COMPLETED. Incident INC-1003-01-40d3, 그래프 WorkItem10/Task참조9, 역할6. 시험 끝 설비reset. 이는 새 코드의 실제 서비스 경로 회귀이며 Codex를 다시 호출한 시험이 아니다. 원본 completion `workitem_processor.py`4660~4726 추가 열람: workitem version 우선, 없으면 instance archive 참조하는 실제 호출부까지 확인.
  - A015 버전별 실행 그래프: 수정 전6검사 중5실패 → 실제13/13. ProcessVersion + scoped FlowNode, WorkItem→Task/Event, 업무 노드 MAPS_TO. 역할0개/ontologyRef 없음에도 작업 투영, 없는 업무 노드는 경고·가짜 노드 없음, 이전 담당자 관계 제거, 동일 endpoint의 두 역할 보존,8동시 재투영 커밋8/8. canonical schema2.5.0/41클래스72관계. 업무 지도에서 버전 snapshot/기술 노드 제외, 실행은 인스턴스 화면으로 분리. DECISIONS23은 제품 head-only 방식과 HYD 확장 차이를 명시한다.
  - A015 배포 실측: process/agent build exit0. localhost 첫 실제23/28 exit1(관리자 제출 전에30실초 승인타이머 만료), 원시 실패/인스턴스 보존. 요청당localhost2.056~2.072초 대127.0.0.1 0.003~0.017초 실측 후 Compose IPv4 주소로 시험 교정. 같은20배속 재실행 **35/35 exit0**: instance anomaly_response.85bd6268-2fbd-455d-803f-30fbde4fad93, INC-1003-01-3090, CMD-1003-0001-6823, WO-1003-D0F1, ev:closed. graph10작업 모두 버전별노드/경계Event 연결 확인. 전체599노드1791관계 schema0/integrity0, 실제 지도313노드815관계 runtime혼입0/없는끝점0. 증거 execution-scope-{live,deployed-graph,success-instance}.json, execution-scope-scenario{-ipv4,}.log. 전체280passed/2기존warning. 이전 실패 실행은 자동 완료 처리하지 않았다.
  - A015 자료/정리: 교재13장 §5 그림·질의·설명과 제품 비교 갱신, checker0,1280/390렌더 broken0/hscrollfalse/errors0, §5 직접 확인. 포털 긴식별자는 펼치기로 옮기고 정의/버전·Event 표시 직접 확인, 데스크톱 수평넘침0. 원시 캡처 execution-version-ui-final.png, book-render/execution-version-s5.png. 새Codex 호출시험은 이 묶음에 없으며 F 실측과 구분한다. 기본20배속/legacy 유지, 시험끝설비reset, PowerShell remainingWorkersOrProbes0. 타이머 실패 probe는 자체exit1로 종료되어 실제강제종료0.
- [~] G4 포털·교재·실습·시수 동기화, 전체 요구 추적 검수, 재개 문서 대역 시험. F 관련 교재13장·시수표에서 CLI별 설정, 네 작업의 독립 세션, 실패PENDING, Codex HITL 미검증, 2배속 조건을 교정. 교재 구조 검사0문제,1280/390 넘침/콘솔오류/깨진이미지0. 전체 장 의미 재감사·학생 배포본/강사 리허설·대역 시험은 아직 미완료.

**최신 자원 권한:** 사용자는 '컴퓨터의 모든 리소스는 맘대로 사용, 삭제까지 허용'했다. 기동·중지·정리/삭제에 반복 승인을 받지 않는다. 작업 대상과 영향을 확인하고 실행 기록을 남긴다. 결제·원격 push는 별도다. 워커는 PowerShell 프로세스 조회로 종료를 확인한다.

**현재 코드 기준:** HYD HEAD `aad500b47c928d0fc2d6bb65bc20dadc5ccd3f5d`, 작업 시작 시 Git 상태 항목 74개(미추적 디렉터리 포함, 파일 수가 아님). 기존 WIP 보존. 과거 테스트 259개 통과를 이번 실행 결과로 보고하지 않는다.

범례: [x] 완료·검증 / [~] 진행 중 / [ ] 미착수. 각 항목에 검증 근거를 적는다.

**A. 선행(완료)**
- [x] ZIP·회의 원문·R2 통독, 14항목 도출 (2026-10-03)
- [x] 참고 레포 17개 README·핵심 파일 읽기 (§4)
- [x] 로컬 fast-forward → aad500b, 미커밋 1줄 보존, 단위 145 통과
- [x] 이 HANDOFF 작성

**B. 첫 묶음: 쿨러 한 바퀴를 인스턴스·태스크 구조로**
- [x] B1 프로세스 정의 JSON `it/process/definitions/anomaly_response.json` — v2 BPMN 15노드(태스크 9·게이트웨이 2·이벤트 4·흐름 15)를 ProcessGPT 정의 형식으로. 게이트웨이 조건은 `condition`(안전 평가 식) + `name`(표시문). 검증: `tests/test_engine.py::test_definition_matches_ontology_v2_flow_nodes` (2026-10-03)
- [~] B2 Supabase 프로젝트 `it/supabase/` — 작성 완료, **DB 미기동으로 SQL 실행 미검증**(B11에서 `supabase start`로 검증). `config.toml`(포트 54321~), `migrations/20261003000001_process_engine.sql`(enum 5종, tenants·proc_def·bpm_proc_inst·todolist·events, RPC `claim_workitems`(FOR UPDATE SKIP LOCKED)·`release_stale_workitems`, RLS 허용 정책), `migrations/20261003000002_enterprise.sql`(ent 스키마 16테이블, 읽기 RPC `ent.mes_orders|erp_contract|erp_inventory|cmms_history|qms_lots|scm_suppliers|ems_demand` — enterprise-sim의 {system,facts,records} 계약 유지, 쓰기 RPC `ent.exec_skill(jsonb)` — state.py 7스킬 의미·멱등 키(decision,skill)·fingerprint 충돌 그대로, `ent.reset_executions`), `seed.sql`(data.py 값).
- [x] B3 엔진 `it/process/procsvc/engine.py`(pure): Definition.load/validate, new_instance, start, complete(outputData 선언 밖 출력 거부), fire_boundary(선택 시간초과→CANCELLED→escalate), 게이트웨이(exclusive 조건 1개만 참, 기본 흐름, 불일치 시 예외), ast 화이트리스트 조건 평가, ISO 기간, timeline 뷰. workitem: user→TODO(user_id=역할 endpoint), 자동→SUBMITTED(agent_orch=cliagents|hyd-process), due_date=PT10M/time_scale. 검증: `tests/test_engine.py` 15 passed (`.venv314/Scripts/python.exe -m pytest tests/test_engine.py`, 2026-10-03)
- [x] B4 DB 접근 `it/process/procsvc/procdb.py` — Repo 프로토콜, `MemoryRepo`(테스트·DB 없이 실행), `PgRepo`(psycopg3, `SUPABASE_DSN` 기본 `postgresql://postgres:postgres@host.docker.internal:54322/postgres`), `make_repo()`(`PROCESS_REPO=memory|pg`). 검증: `tests/test_procdb_memory.py` 5 passed(claim 1회성·라운드트립·events·복사 반환). PgRepo는 DB 미기동으로 미검증.
- [x] B5 process 서비스 인스턴스 모드 — 모듈 분리: `procsvc/instances.py`(InstanceRuntime: on_alert_raise→인스턴스+Incident 생성, complete, select(역할 검사→gw:control), fire_timeouts, 서비스 태스크 디스패치 task:command→machine.on_approve / task:reobserve 대기 / task:work-order→enterprise WO_CREATE, on_incident_update로 Incident 상태→태스크 완료 매핑, 종결 시 Execution 레이어 Cypher MERGE `INSTANCE_Q`), `procsvc/instance_mode.py`(ProcessContext로 main 의존 주입, hooks, 하우스키핑 5s, AGENT_BRIDGE=legacy 다리, 라우트 `/api/process/mode|definition`, `/api/instances[/{id}|/start]`, `/api/todolist[/{id}|/complete|/select|/events]`, `/api/events`), `main.py`는 4곳만 호출(mount·start·on_incident_update·on_alert_raise·bridge). `_after`·`_audit`가 워커 스레드에서도 안전하게 전역 loop 사용. Dockerfile에 definitions 복사, compose·.env.example에 PROCESS_MODE·PROCESS_REPO·SUPABASE_DSN·AGENT_BRIDGE. 검증: 단위 전체 177 passed(`tests/test_instance_mode.py` 4개는 실제 machine·decisions와 MemoryRepo로 경보→다리→선택(403 포함)→action.cmd→ACK→재관측→WO→ev:closed·에스컬레이션까지). 실제 Kafka·Supabase·enterprise-sim 연동은 B11.
- [x] B6 워커 `it/agent-worker/worker/` — settings(env)·workspace(인스턴스별 디렉터리: CLAUDE.md 규칙, `.mcp.json`, context/task.json·schema_prompt.md·previous_outputs.json, session.json으로 Claude Code 세션 resume)·mcp(neo4j uvx mcp-neo4j-cypher 읽기 전용, enterprise·hyd-dmn HTTP)·prompt(task.json + 프롬프트)·outcome(최종 JSON 블록만 인정, 선언 키 외 버림, 없으면 실패)·events(ExecEvent→ProcessGPT event_type)·process_api(정의·인스턴스·events·complete)·runner(claim→prepare→stream_exec READ_ONLY+`--mcp-config --strict-mcp-config --allowedTools`→trace→parse→complete; 실패 시 claim 반납·retry, max_retries 뒤 빈 출력+사유로 완료)·main(폴링 루프 + /healthz 8097). Dockerfile(python3.12+node22+claude-code+uv+cliagents, procdb·schema_prompt 복사). 검증: `tests/test_worker.py` 9 passed(가짜 CLI로 세션 resume·실패 재시도·오류 결과 처리). 실제 Claude Code 실행은 B11(ANTHROPIC_API_KEY 필요).
- [x] B7 MCP 서버 — `it/enterprise-mcp/enterprise_mcp/`(FastMCP HTTP 8199: 읽기 RPC 도구 7종 + `describe_schema`(DDL형 텍스트) + `query`(SELECT 전용, `sql_guard.py`: 단일 문장·쓰기/세션/시스템 스키마 거절·LIMIT 200·읽기 전용 트랜잭션·statement_timeout), `/healthz`), `it/dmn-mcp/dmn_mcp/`(FastMCP HTTP 8198: agentsvc 재사용 — `diagnose`(신선도→T1→증거→순위→T2→카드), `dmn_rules`, `inputs`, `gather_facts`, `evaluate_cards`(제출 없음), `submit_decision`(process /api/decisions, 유일한 쓰기), `precedents`, `tradeoffs`; Dockerfile이 agentsvc·templates 복사). 워커 `.mcp.json`: neo4j(uvx mcp-neo4j-cypher 읽기 전용)·enterprise·hyd-dmn. 검증: `tests/test_enterprise_mcp.py` 15, `tests/test_dmn_mcp.py` 3 passed(가짜 연결·가짜 그래프). FastMCP 실제 기동은 B11.
- [x] B8 enterprise-sim 백엔드 선택 — `entsim/main.py` 재구성(MemoryEnterprise = data.py+state.py, `ENTERPRISE_BACKEND=supabase` → `entsim/supabase_backend.py`: ent 읽기 RPC·`ent.exec_skill`·transactions·snapshot·`reset_executions`), HTTP 계약 동일(scenario_test 영향 없음). 검증: `tests/test_entsim_backends.py` 5 passed(가짜 연결). **전체 단위 209 passed (2026-10-03, `.venv314/Scripts/python.exe -m pytest -q`).**
- [x] B9 compose — process에 PROCESS_MODE·PROCESS_REPO·SUPABASE_DSN·AGENT_BRIDGE + extra_hosts, enterprise-sim에 ENTERPRISE_BACKEND·SUPABASE_DSN, 새 프로필 `cliagents`(enterprise-mcp 8199 · dmn-mcp 8198 · agent-worker 8097, worker-data 볼륨, healthcheck /healthz). 기본 COMPOSE_PROFILES에는 넣지 않음(Supabase·API 키 필요). `.env.example` 갱신. Supabase는 CLI가 별도로 띄우므로 DSN은 `host.docker.internal:54322`.
- [x] B10 포털 — `it/portal/www/instances.js|css`, index.html에 탭 "프로세스 인스턴스"(`view-instances`): 모드 배너(legacy면 켜는 방법 안내), 내 할일(TODO: task:select 카드 선택 폼 — hydCards 재사용·역할·팬/부하·사유 → `/api/todolist/{id}/select`; task:escalate 확인 → `/complete`), 인스턴스 목록, 상세(작업 흐름 9단계 타임라인·변수·todolist 표·events 기록). ui.js에 NEW/TODO/IN_PROGRESS/PENDING/CANCELLED/COMPLETED 라벨. 검증: `node --check` 통과. 브라우저 렌더·실제 데이터 확인은 B11(Docker).
- [~] B11 통합 — 시험 스크립트 작성 완료 `scripts/scenario_instance_test.py`(모드·헬스 → 주입 → 인스턴스/Incident 생성 → 에이전트 4태스크(다리 또는 `--worker`) → 운전원 403 → 생산관리자 선택 → task:command ACK → reobserve → WO → ev:closed → Execution 레이어 Cypher → 레거시 API 보존). **실행은 Docker 기동 뒤:**
  1. Docker Desktop 켜기 → `cd it/supabase && supabase start` (마이그레이션 2개 + seed 적용 확인; 다시 적용은 `supabase db reset`). Studio http://127.0.0.1:54323
  2. `.env`에 `PROCESS_MODE=instance`, `ENTERPRISE_BACKEND=supabase`, `AGENT_BRIDGE=legacy` → `docker compose up -d --build` → `python scripts/scenario_instance_test.py`
  3. 레거시 회귀: `PROCESS_MODE=legacy`로 `python scripts/scenario_test.py --quick` (62/62 유지)
  4. 워커 경로: `ANTHROPIC_API_KEY` 넣고 `AGENT_BRIDGE=off`, `COMPOSE_PROFILES`에 `cliagents` 추가 → `docker compose up -d --build enterprise-mcp dmn-mcp agent-worker` → `python scripts/scenario_instance_test.py --worker`. 포털 `프로세스 인스턴스` 탭에서 눈으로 확인.
  진행 기록: 2026-10-03 21:30 `.env`에 PROCESS_MODE=instance·ENTERPRISE_BACKEND=supabase·AGENT_BRIDGE=legacy 추가 → `supabase start`(로그 `.evidence/supabase_start.log`)와 `docker compose build`(`.evidence/compose_build.log`) 백그라운드 시작(빈 Docker라 이미지 내려받기). 22:40 둘 다 exit 0: `supabase start`가 `20261003000001_process_engine.sql`·`20261003000002_enterprise.sql`·`seed.sql`을 오류 없이 적용 → psql로 확인: public 5테이블·ent 16테이블, RPC 12개(claim_workitems·release_stale_workitems·ent.exec_skill·ent.reset_executions·읽기 7종), seed 행 assets 3·production_orders 3·sales_contracts 3·suppliers 3·maintenance_history 4·fg_inventory 3·parts 1·energy_demand 1·profiles 3+3, tenants 1(**마이그레이션 SQL·seed 검증됨**). compose 이미지 7개 빌드 완료. `docker compose up -d`는 기반 이미지 pull로 5분 초과 → 백그라운드(`.evidence/compose_up.log`). 22:52 compose 18컨테이너 기동, process는 instance·PgRepo·legacy 다리로 기동 확인. 결함 1: enterprise-sim 재시작 반복 — `it/enterprise-sim/requirements.txt`에 psycopg 없음 → `psycopg[binary]==3.2.3` 추가·재빌드 → healthy(backend=supabase). 결함 2(1차 시험 FAIL): 경보 RAISED 뒤 인스턴스 미생성 — `procsvc/store.py`의 SQLite 연결을 인스턴스 런타임 워커 스레드에서 써서 `ProgrammingError`(같은 스레드만 허용) → `check_same_thread=False`+`threading.Lock`으로 수정, `tests/test_stability.py::test_store_save_from_another_thread` 추가(수정 전 코드에서 ProgrammingError 재현 확인). 결함 3: 시험 스크립트가 치명 단계 실패 시 TypeError로 죽음 → `require()`·`summary()` 추가. **23:05 2차 시험 `scripts/scenario_instance_test.py` ALL PASS 29/29**(로그 `.evidence/scenario_instance_test.log`): 인스턴스 `anomaly_response.63ffcc33…`, Incident INC-1003-01-35b2, 에이전트 4태스크 DONE(consumer=legacy-agent, 7s), 운전원 403, 생산관리자 선택 → CMD ACK → RE_OBSERVING → ev:closed(55s), 8태스크 DONE, WO-1003-AC8E, Neo4j `proc:anomaly-response, 8, 8`·HANDLES/DIAGNOSED_AS. **GOAL DoD 1·2·3 검증됨.** Supabase 직접 조회: bpm_proc_inst 1(COMPLETED, ev:closed, recovered=true)·todolist 8 DONE(에이전트 4 consumer=legacy-agent, select user=role:operator, command/reobserve/work-order=hyd-process)·events task_started 4+task_completed 4·ent.work_orders 1(WO-1003-AC8E, 배정됨, 이생산)·ent.transactions 1. 단위 전체 210 passed. 23:20 포털 눈 검수(Playwright+설치된 Edge headless, `.evidence/portal_instances_tab.png`): 탭에 실제 데이터(배너·인스턴스 목록·작업 흐름 9단계·변수·todolist 표) 렌더, 잘림·겹침 없음. 결함 4: 작업 흐름이 BFS라 '정비 작업지시'가 '재관측'보다 앞에 그려짐 → `engine._topological`을 Kahn 위상 정렬(바운더리 이벤트는 붙은 작업 뒤, 동률은 sequence 순)로 교체, `test_engine.py::test_timeline_lists_every_activity_in_flow_order` 기대 순서 수정 → API·화면 모두 command→reobserve→work-order→escalate 확인. **DoD 5 검증됨.** 관찰(이번 변경 무관, 미수정): 포털이 기본 프로필에 없는 127.0.0.1:9090(Prometheus)·8085 상태 프로브로 콘솔에 ERR_CONNECTION_REFUSED를 남김(기존 동작).
  미검증 목록(DB 없이 못 본 것): Supabase 마이그레이션 SQL 실행, PgRepo, ent RPC, FastMCP 기동, Claude Code 실제 호출(allowedTools·plan 모드에서 MCP 도구 허용 여부 — 막히면 Permission.WORKSPACE_WRITE + allowedTools로 조정), uvx mcp-neo4j-cypher 버전(0.4.1 가정).

**D. 레포 로직 이식 · 실제 워커 환경 (2026-10-03 밤 사용자 지시, DECISIONS 11) — C보다 먼저**
- 2026-10-03 23:40 사용자 요청으로 `docker compose stop` + `supabase stop`(backup=true, 데이터 보존). 다시 올릴 때: `cd it/supabase && supabase start` → `docker compose up -d`. Supabase에 인스턴스 1건·todolist 8행이 남아 있다.
- 발화 21(10-03 밤): 방향은 새로울 것 없음(발화 3·4·8과 동일). 새로 드러난 것은 내 구현의 결함 3가지 — ① todolist 상태 의미가 제품과 반대(제품: IN_PROGRESS=처리 중 → SUBMITTED=결과 제출, 엔진이 SUBMITTED를 집어 다음 작업 생성 후 DONE; 에이전트는 fetch_pending_task로 IN_PROGRESS+agent_mode 행을 잡고 save_task_result로 SUBMITTED) ② todolist·bpm_proc_inst 열 부분집합(agent_mode·draft·draft_status·query·assignees·participants·role_bindings·proc_def_version·log·retry·rework_count 없음) ③ 워커 계약 얕음(워크스페이스·저널·폼 계약·human_input_required 일시정지·세션 저장).
- [x] D1 레포 통독 완료(10-03 밤, 컨테이너 없이): 읽은 파일·줄 범위는 `docs/handoff/REPO_GAP.md` §0. 클론은 스크래치에 그대로 있었음(이름 `process-gpt-completion`·`process-gpt-agent-sdk`·`process-gpt-sample-app-wms`).
- [ ] (기록용 원문) D1 레포 재클론·통독: completion(process_definition.py·polling·execution) · agent-sdk(database_schema.sql 전체) · cliagents · process-gpt-cli-agent(claim·events·resume) · sample-app-wms(mcp 서버·RPC) · process-gpt-vue3(instance·todolist 화면) · ontology-studio(MCP) · process-gpt-strategy(ontology_sync). 클론 위치: 세션 스크래치 `refs/`(사라지면 다시 clone).
- [x] D2 대조표 `docs/handoff/REPO_GAP.md` 작성(회의 항목별: 제품 로직·내 구현·차이·처리). 핵심: todolist 상태 의미 반대(이식), 예정업무 사전 생성, 완료 판정 DONE/PENDING, XOR priority/default, 바운더리 이벤트 행, 제품 열·enum 전부, 워커는 fetch_pending_task/save_task_result RPC, 컨텍스트(form_def·users·tenants.mcp), HITL 일시정지, 포털 instanceSteps 이식, Execution 레이어 속성·ROLE_BOUND. 축소는 LLM 자연어 조건·LLM 인스턴스 이름·피드백 요약뿐(회의 결정론 원칙·비용).
- [~] D3 레포 로직으로 교체 — 2026-10-04 새벽, 컨테이너 없이 진행. **단위 223 passed.** 바뀐 파일: `it/supabase/migrations/20261003000001_process_engine.sql`(제품 enum·열 전부, users·form_def·notifications·proc_inst_source·proc_def_version, RPC fetch_pending_task·save_task_result·record_events_bulk·fetch_context_bundle + 엔진용 claim_submitted_workitems·cleanup_stale_consumers) · `seed.sql`(tenants.mcp 3서버·users 7·form_def 6) · `procsvc/engine.py`(예정업무 TODO 사전 생성 → reach IN_PROGRESS[서비스는 SUBMITTED] → submit → process_submitted DONE/PENDING, XOR priority/default, 바운더리 이벤트 행, 안 간 가지 CANCELLED, gateway_decisions, variables_data list) · `procdb.py`(제품 열·RPC) · `instances.py`(submit·process_workitem·poll_once 재시도 3·select=폼 제출·human_response·fire_timeouts·서비스태스크 SUBMITTED 실행·Execution 투영 매 변경) · `instance_mode.py`(엔진 폴링 루프, /submit·/select·/human-response·/users·/forms, 레거시 다리는 fetch_pending_task→save_task_result→poll_once) · 정의 JSON(attachedEvents·formHandler 도구) · 워커 전면(`settings`·`context`·`workspace`·`bridge`·`prompt`·`outcome`·`events`·`hitl`·`runner`·`main`; process_api·mcp 제거) · 포털 `instanceSteps.js`(제품 모듈 이식)+`instances.js`(내 할일=IN_PROGRESS, 폼 제출, 에이전트 질문 답변, 분기 묶음)+css+index · compose/.env.example(CLIAGENTS_* 변수, tenants.mcp 출처) · `scripts/run_worker_host.sh`(구독 로그인 워커, MCP_HOST_REWRITE) · enterprise-mcp 봉투 `{result, document}`. 테스트 파일 5개 교체(test_engine 17·test_procdb_memory 9·test_instances 11·test_instance_mode 4·test_worker 11).
  D3 컨테이너 없이 할 수 있는 것은 끝(10-04 00:40): dmn-mcp 봉투 통일 · `scripts/scenario_instance_test.py` 교체 · REPO_GAP §3 편차 기록 · **단위 224 passed**(엔진 17·DB층 9·런타임 11·배선 4·워커 12·enterprise-mcp 15·dmn-mcp 4·기타). **미검증(컨테이너 필요, 사용자가 컨테이너를 멈춰 둔 상태)**: ① `cd it/supabase && supabase db reset`(새 마이그레이션·seed 적용 — 기존 로컬 인스턴스 1건은 사라짐) ② `docker compose up -d --build process enterprise-sim enterprise-mcp dmn-mcp` ③ `python scripts/scenario_instance_test.py`(레거시 다리) ④ 포털 탭 캡처 ⑤ 워커: `bash scripts/run_worker_host.sh`(로그인된 Claude Code) + `AGENT_BRIDGE=off` 로 process 재기동 + `scenario_instance_test.py --worker` ⑥ 레거시 회귀.
- [ ] (기록용 원문) D3 차이를 레포 로직으로 교체(엔진 실행 의미 → 워커 claim·events → 스키마 열 → 화면 → MCP 구조), 단위·통합 시험 유지.
- [ ] D4 실제 워커 경로: 로그인된 Claude Code CLI로 agent-worker 실행(AGENT_BRIDGE=off, 프로필 cliagents), `scenario_instance_test.py --worker` PASS, events에 tool_usage_*·MCP 호출 확인 (GOAL DoD 4).
- [ ] D5 레거시 회귀 `PROCESS_MODE=legacy` + `scenario_test.py --quick`(사용자가 10-03 밤 실행 거부 → 미검증, D3 뒤 다시).

**E. 컨테이너 검증(2026-10-04 아침, 사용자 "진행해봐")** — 실측 기록. 자세한 출력은 세션 스크래치 tasks/*.output.
- Supabase: 어제 B11 볼륨이 PostgreSQL 15 데이터인데 CLI(2.119)가 17 이미지를 올려 재시작 반복 → `supabase stop --no-backup`(볼륨 삭제, 10-03 시험 인스턴스 1건 소실) → 재기동 15.19, 마이그레이션 2개·seed 적용(사용자 7·폼 6·tenants.mcp 3·ent 테이블 16). `docker compose build` 전체 + `up -d` 16 서비스 healthy.
- [x] D3 통합: `scenario_instance_test.py` **34/35** → 실패 1건 = participants 에 승인한 생산관리자 없음 → `instances.select()` 가 승인 역할을 participants 에 추가(테스트 보강) → 단위 256. (재실행은 펌프·팬 뒤)
- [x] C1 실측: enterprise DDL 미리보기 16테이블 → 커밋 System 2(sys:db-ent·sys:ems 신규, 기존 sys:mes 는 배치 표시 없음)·InputData 98 → `/api/kg/ingests` 배치 1 → `/api/kg/rules/sql` 2질의 → DELETE 배치 100 노드 삭제, 기존 System 10·InputData 26 그대로. (curl 로 한글 쿼리를 날리면 "Invalid HTTP request" — 포털·python 처럼 URL 인코딩 필요, 코드 결함 아님)
- [x] C3 실측: `/api/agent/decide` 쿨러 → ERP·QMS 사실(보상 120·OEM·고온 로트 800/3000) 수집됨. **결함**: 생산 영향을 BSC 손실로 판정해 세 카드 전부 "정지"(−1.12). 수정: 카드의 명령으로 판정(STOP=정지, LOAD_SET<90=감산, 그 외 명령=유지, 명령 없는 작업지시 카드만 BSC 폴백) → 팬 최대 유지 +1.12·품질 −1.5(3위), 팬 최대+부하 80 감산 +0.45(1위). test_cards 보강.
- [~] C4 실측: 첫 실행에서 **결함** — 가드레일이 `PUMP_SELECT`(값 'B', 범위 없음)를 "lacks paramRange/value" 로 거부해 에이전트 run REJECTED_BY_GUARDRAIL, 인스턴스가 task:diagnose 에 멈춤(anomaly_response.…9c7cde9f, 기록으로 남김). 수정: 범주형 값은 범위 불요, 숫자 값만 범위 요구(`guardrail.py`, test_guardrail +1). 에이전트 재빌드 뒤 `scripts/scenario_pump_fan_test.py`(펌프·팬·가림) 재실행 중 — 결과는 아래 줄에.
- [x] C4 결과(`scripts/scenario_pump_fan_test.py`, 10-04 01:10~01:25): 두 번째 실행에서 **결함** 하나 더 — 레거시 다리가 `fetch_pending_task`(인스턴스 필터 없음)로 다른 인스턴스의 작업까지 집어 두 HYD-02 인스턴스가 서로의 출력을 받음 → `_claim_own()`: 자기 인스턴스 행만 쓰고 남은 행은 draft_status·consumer NULL 로 반납(test_instance_mode +1). 세 번째 실행 **33/34**: 펌프(HYD-02: RAISE 19 s → dx-pump → 압력 상향 제외·예비 펌프 전환 권고 → PUMP_SELECT ACK → pump B·PS1 182 → 재관측 "PS1 >= 165.0" 통과 → 씰 교체 WO → ev:closed 45 s)·팬(HYD-03: RAISE 19 s → dx-fan → fan-slow-derate → VS1 0.918 → "VS1 < 1.2" 통과 → ev:closed 42 s) 전부 PASS. 가림(HYD-01 derate-70): 경보 CLEAR(load 70·PS1 156) → 재관측 cleared=true·PS1 156.9 실패 → MITIGATION_FAILED·ESCALATED PASS, 실패 1건은 스크립트 기대가 틀림 — gw:recovered=no 뒤 **상급자 호출(생산관리자 사람 작업)** 이 열려 인스턴스가 기다린다(설계대로). 메모 제출 → ev:escalated·work-order CANCELLED 확인, 스크립트를 그 흐름으로 고침. 다리 결함 때 생긴 낡은 HYD-02 인스턴스 2건은 SQL 로 작업 CANCELLED·인스턴스 COMPLETED 처리(워커가 집어 가지 않도록).
- [x] 레거시 회귀 `PROCESS_MODE=legacy scenario_test.py --quick` **46/46 ALL PASS**(170 s), 인스턴스 모드 복귀.
- [x] 포털 캡처(`시스템교재/img/hyd/capture_c4_{scenario,instances,ontology,incidents}.png`, 1440×2600): 결함 시뮬레이션(버튼 3+복구·PS1/FS1/VS1·운전 펌프 B(예비)·현재 상태 문장), 인스턴스 탭(배너·에이전트 현황·인스턴스 6·8/8 단계 분기 묶음·변수·작업표·events), 온톨로지 DDL 섹션, 인시던트 목록(추가 확인 필요·종결·자연 회복). 첫 캡처가 빈 화면이었던 것은 process 재시작과 겹친 타이밍(코드 결함 아님, 재캡처로 확인).
- [~] D4 워커(이 PC 로그인 Claude Code): `run_worker_host.sh` Windows 수정(PYTHONPATH ';'·`pwd -W`). 첫 실행 **결함** — cliagents 가 `shutil.which` 로 찾아 놓고 argv 엔 맨 이름 `claude` 를 넣어 CreateProcess 가 `claude.cmd` 를 못 찾음(WinError 2) → `runner._resolve_provider` 가 전체 경로를 provider.executable 에 넣음(test_worker +1, 원래 코드의 `Surface` 미임포트도 수정). 단위 **259**. process 를 `AGENT_BRIDGE=off WORKER_URL=http://host.docker.internal:8097` 로 재기동, `scenario_instance_test.py --worker` 실행 중 — 결과는 아래 줄에.
- [~] D4 결과(10-04 01:40, Claude Code 워커): 옛 워커 프로세스가 TaskStop 뒤에도 살아 있어(exec 된 python 4개) 패치 전 코드로 작업을 집어 WinError 2 를 반복 → 전부 종료 후 새 워커 1개. 새 워커의 첫 실행은 Claude Code 가 **실제로 돌았고**(WinError 해결) "결과가 요구된 출력 형식과 맞지 않음: 에이전트가 결과를 반환하지 않음"으로 실패. 작업 폴더(.evidence/workspace/hyd/<id>: .mcp.json·CLAUDE.md·context/)에서 수동 헤드리스 실행은 정상("OK", stream-json). 발견: ① enterprise-mcp·dmn-mcp 컨테이너가 프로필 cliagents 에만 묶여 **떠 있지 않음**(빈 응답의 유력 원인, `docker compose --profile cliagents up -d enterprise-mcp dmn-mcp` 로 올리면 됨) ② Claude Code 응답에 **플랜 7일 사용률 97 %** 경고 → 추가 실행은 사용자 결정(DECISIONS 11). 워커·시험 중지, 실패 인스턴스(…8f68c13e)는 기록으로 남김. 다음: 사용자 허락 시 MCP 2개 기동 → `--worker` 1회.

**F. D4 를 Codex 워커로 — Codex 세션이 이어서 할 일 (2026-10-04 02:00, 발화 26~28)**

배경: Claude Code 플랜은 7일 사용률 97 %, Codex 플랜은 미사용(100 % 남음). 회의는 특정 CLI 를 고집하지 않았다(원문2 L154~156 "클로드 코드든 클로드 데스크톱이든 우리가 말하는 종류의 에이전트면 된다"). cliagents 에 `codex` 프로바이더가 있고 이 PC 에 codex-cli 0.151 이 설치돼 워커 `/agents` 에 `installed: true` 로 잡힌다. **이 세션(Claude)은 여기서 멈추고, 아래를 Codex 세션이 수행한다.** 컨테이너 16개와 Supabase 는 켜 둔 상태, 워커 프로세스 0, 실행 중 인스턴스 0, 설비 3기 정상 운전점.

확인된 사실(코드를 읽은 것, 추측 아님):
- cliagents codex 프로바이더(`.venv314/Lib/site-packages/cliagents/providers/codex.py`): argv = `codex exec [resume <session>] --json --skip-git-repo-check --sandbox <mode> --cd <workdir> [--model …] <extra_args> <prompt>`. permission → `_SANDBOX_MODES` 매핑이 있다. MCP 서버는 **`$CODEX_HOME/config.toml` 의 `[mcp_servers.<name>]`**(stdio: command/args/env, HTTP: url)이며 프로바이더의 `install_bridge(..., mcp_servers=[McpServer…])` 가 codex CLI 로 멱등 등록한다(다른 섹션 보존). `codex_home(env)` 는 `CODEX_HOME` 없으면 `~/.codex`. 사용자의 `~/.codex/config.toml` 에는 이미 `[mcp_servers.openaiDeveloperDocs]`·`[mcp_servers.node_repl]` 가 있다 — **지우지 말 것**.
- 워커 브리지(`it/agent-worker/worker/bridge.py`)는 Claude 전용(`.mcp.json` 쓰기, `CLAUDE_CONFIG_DIR` 격리). codex 분기가 없다. `runner.py:89` 의 `--allowedTools` extra_args 는 Claude 전용이라 codex 에 넘기면 argv 오류.
- 워커는 `CLIAGENTS_DEFAULT_CLI` 로 프로바이더를 고른다(`settings.cli_agent`). `run_worker_host.sh` 는 Windows 수정(PYTHONPATH ';'·pwd -W) 끝.
- enterprise-mcp·dmn-mcp 컨테이너는 compose 프로필 `cliagents` 에만 묶여 **지금 떠 있지 않다**: `docker compose --profile cliagents up -d enterprise-mcp dmn-mcp`(agent-worker 컨테이너는 올리지 말 것 — API 키 경로). 호스트 워커는 MCP_HOST_REWRITE 로 127.0.0.1:8199·8198·7687 을 쓴다.
- TaskStop/Ctrl-C 로 워커를 멈춰도 exec 된 python 이 살아남는다. 반드시 PowerShell `Get-CimInstance Win32_Process | ? CommandLine -like '*worker.main*' | Stop-Process -Force` 로 확인·종료.
- 로그는 cp949 섞임: `open(..., 'rb').read().decode('utf-8', errors='replace')` 로 읽는다.

할 일(순서대로, 단계마다 이 파일 갱신):
1. `bridge.install()` 에 `provider_id == "codex"` 분기: tenants.mcp → `McpServer` 목록으로 바꿔 `provider.install_bridge(workdir, env, mcp_servers=…)` 호출(stdio neo4j: command uvx, args, env; HTTP enterprise·hyd-dmn: url). `McpServer` 필드는 `cliagents/providers/codex.py` 와 `cliagents/provider.py` 에서 읽을 것. 되돌림: 세션 끝에 추가한 `[mcp_servers.neo4j|enterprise|hyd-dmn]` 섹션만 제거(사용자 섹션 보존). 단위 테스트는 `tests/test_worker.py` 의 브리지 테스트 양식을 따른다(실제 codex 실행 없이 생성된 toml/인수 검사).
2. `runner.py` extra_args 를 프로바이더별로: claude-code 만 `--allowedTools`. codex 는 없음(샌드박스로 제한; 쓰기 MCP 도구가 없으니 읽기 전용).
3. 세션 이어가기: 워커가 output 에 저장하는 `cliagents_session_id` 가 codex 의 `--json` 스트림에서도 채워지는지(`_CodexParser` 가 session id 를 어떤 이벤트로 내는지) 확인. 안 채워지면 네 작업이 각각 새 세션으로 돈다(동작은 하되 비용 ↑) — 사실대로 기록.
4. 단독 확인(사용량 작음): 작업 폴더 하나에서 `codex exec --json --skip-git-repo-check --sandbox read-only --cd <ws> "neo4j MCP 의 get_neo4j_schema 를 호출해 라벨 수를 말하라"` 로 MCP 가 붙는지 본다. 안 붙으면 config.toml 등록부터 고친다.
5. 실제 경로: MCP 컨테이너 2개 기동 → process 를 `AGENT_BRIDGE=off WORKER_URL=http://host.docker.internal:8097 docker compose up -d process` → `CLIAGENTS_DEFAULT_CLI=codex bash scripts/run_worker_host.sh > .evidence/worker/codex.log 2>&1 &` → `python scripts/scenario_instance_test.py --worker`(네 작업 대기 900 s). 판정: 네 작업 DONE, events 에 task_started·tool_usage_*·task_completed 와 MCP 호출(neo4j·enterprise·hyd-dmn) 포함, task:select 가 IN_PROGRESS 로 열림. 결과(PASS 수·실패 원인)를 이 블록 아래에 적는다.
6. 끝나면: 워커 종료(PowerShell 확인), process 를 `.env` 설정(legacy 다리)으로 복귀(`docker compose up -d process`), 실패로 남은 인스턴스는 SQL 로 작업 CANCELLED·인스턴스 COMPLETED(E 블록의 예와 같이), 설비 `/api/reset`. 성공하면 교재 13장·시수표의 "Claude Code" 표현을 "범용 코딩 에이전트(Claude Code · Codex)"로 맞춘다(lecture-sync).

**F 실행 결과 — 현재 Codex 세션(2026-10-04, 위의 기존 설치안 정정 포함)**

- 1~2 완료: Codex 호출별 MCP TOML override + Claude 전용 allowedTools 분리. 설치 cliagents는 HTTP McpServer 미지원이라 global install_bridge 대신 native `-c` 사용(DECISIONS 17). 사용자 config 변경 없음.
- 3~4 완료: thread.started의 session id 보존, 같은 세션 재개 CLI 옵션 보정. 실제 세 MCP 조회 성공(Neo4j 라벨 38), 단독 재개 성공, config 해시 동일. 네 업무 작업은 각각 새 세션으로 실행됨(**세션 간 자동 이어붙이기 구현 아님**). 실측 model gpt-5.6-sol, effort low.
- 5 완료(조건 명시): 20배속 첫 두 시험은 혼합 레거시 실행/과열 트립/후속 오경보로 완료하지 못했다. 2배속 별도 시험 **35/35 PASS, exit 0**. 네 작업 DONE(287초), task_started 4 / task_completed 4 / MCP 시작·종료 각 23 / MCP 오류 0. Neo4j 7회, enterprise 3회, hyd-dmn 13회. 운전원 403 → 생산관리자 승인 → PLC ACK → 재관측 594초 → CMMS WO-1003-3389 → ev:closed/COMPLETED. instance `anomaly_response.1dfcaa53-0ba0-4d6d-844d-3a9ad4bb6035`, incident `INC-1003-01-fd51`, command `CMD-1003-0001-0881`. 실제 Execution 투영 및 역할/원인 관계 확인. `codex-instance-scale2.log`, `codex-scale2/{instance.json,summary.json,rollout*.jsonl}`. 이 성공은 20배속 지연/트립 문제의 해결이나 전체 회의 요구 완료를 뜻하지 않는다.
- 6 완료: 03:44 KST PowerShell 종료 검사 **remainingWorkers=0**(`worker-stop-scale2.json`). 최종 API/세션 4개 증거 보존, 기본20배속/legacy 복구, 설비reset 확인. 사용자 config SHA256 단독 검사와 동일. 교재13장·시수표 CLI/세션/실패/시간배율 설명 동기화. **실패 인스턴스를 성공 COMPLETED로 바꾸지 않는다**. 이번 중단 시험 6개는 snapshot/오류 이벤트/FAILED 작업을 보존했다(§9 G, AUDIT).
- [x] F 결과: 단독 MCP·동일 세션 재개·2배속 실제 워커 완주·자원정리 검증됨. 20배속 실패와 변경 시나리오/일반화는 전체 G에서 계속 진행한다.
- 2.0 후속(A020,06:35 KST): 실제4작업270초/PLC ACK/재관측601초/WO-1003-7972/ev:closed까지 확인. 원본35/36 exit1은 추가폼검사기의 id metadata 비교오류이며 수정검사 같은인스턴스5/5, 수정후전체재실행은미실행. 도구시작17/종료16·로컬읽기정책실패1건 보존(A023). 기본20×legacy·설비reset·PowerShellworker/자식0 확인. 최신판정은G/AUDIT A020~A023을따른다.
- 2.0 새 실행(A022,07:14 KST): 실제 Codex 경로 **36/36, exit0**. 경보322초/네작업246초/재관측600초/WO-1003-DC51/ev:closed. 새 전용읽기MCP로 실행했으며 이전35/36로그는보존한다. 최종증거 reader-hyd-v2/ 및 reader-hyd-v2-scenario.log, 기본복구/PowerShell워커0 확인. A023 앱제외는별도3서버읽기와변경후두정의로검증했다. 최신재개는G/AUDIT이다.

**C. 다음 묶음(D 완료 뒤)**
- [~] C1 인제스천 실습(2번, 원문2 L253~293) — 10-04 01:30 코드 완료·컨테이너 미검증: `procsvc/ingest.py`(DDL 파서 → System·InputData 계획 → 멱등 MERGE Cypher(ON CREATE SET ingest_batch·source_id) → 배치 되돌리기(L284) → 규칙 TESTS→SQL(회의 6번 L301~302)), main.py 라우트 `/api/kg/ddl/preview|commit`·`/api/kg/ingests`(GET·DELETE)·`/api/kg/rules/sql`, 포털 온톨로지 탭에 'DDL 로 입력 데이터 만들기' 섹션(미리보기에서 출처 시스템·열 선택, 배치 이력·되돌리기), `tests/test_ingest.py` 6개(실제 enterprise 마이그레이션 16테이블 파싱). SOP 문서 쪽은 기존 kgadmin(매뉴얼→SOP) 그대로. 미검증: Neo4j 에 실제 MERGE·clear, 포털 렌더.
- [x] 회의 5번 현황값 MCP(L51~79): 이미 있음 — dmn-mcp `gather_facts` 가 InputData -SOURCED_FROM-> 출처(센서는 TimescaleDB 최신값, sys:scada 는 plant.status, sys:mes 는 enterprise)에서 값을 가져오고 provenance 를 같이 준다(그래프엔 링크만, 값은 DB). 새로 만들지 않음.
- [~] C2 Execution 레이어 조회·모니터링 보강(12번, 원문2 L434~435 "어떤 에이전트들이 지금 동작하고 있다 … 프로세스 인스턴스들 모니터링") — 10-04 04:40 코드 완료·컨테이너 미검증. `instances.py` `Hooks.query_cypher`(읽기) + `EXECUTION_Q`(ProcessInstance -INSTANCE_OF-> Process · ON_ASSET · HANDLES · ROLE_BOUND · WorkItem -IN_INSTANCE-> · EXECUTES · ASSIGNED_TO 를 한 행으로) + `format_execution()` + `InstanceRuntime.execution_view()`; `instance_mode.py` 라우트 `GET /api/instances/{id}/graph`(Cypher·params 를 함께 돌려 학생이 Neo4j 브라우저에서 재현), `GET /api/agents/status`(워커 `/health`·`/agents` 조회, 응답 없음은 상태로 보고) + `WORKER_URL`(compose·.env.example); 포털 인스턴스 탭에 "에이전트 현황" 배너(워커 상태·실행 중·처리 수·설치 CLI, 없으면 다리/대기 설명)와 인스턴스 상세에 "온톨로지 Execution 레이어" 표(WorkItem→EXECUTES Task→ASSIGNED_TO, Cypher 펼치기). 테스트 test_instances +1(투영 읽기·미투영 None)·test_instance_mode +1(워커 unreachable/ok). 미검증: 실제 Neo4j 투영 뒤 `/graph` 결과, 워커 띄운 상태의 배너.
- [~] C3 납기·품질을 순위에 반영(9번, 원문2 L385~404; aad500b 알려진 한계) — 10-04 02:10 코드 완료·컨테이너 미검증: `agentsvc/cards.py`에 delivery(MES order_due_h × ERP order_penalty_per_h 긴급도 × 생산 영향 keep/reduce/stop, BSC 손실 msr:availability·throughput 으로 판별) · quality(QMS 고온 로트 클레임 위험, 예측 유온 ≥ 55 카드만) 점수 항과 설명 문장, `decide.gather_facts`에 sys:erp(/erp/contract)·sys:qms(/qms/lots) 출처 분기(시스템당 1회 호출), 온톨로지 `instances.cypher`에 sys:qms System · InputData 4(in:order-penalty·in:order-tier·in:hot-lot-claim·in:hot-lot-qty, REPRESENTS msr:penalty·msr:quality-claim) · dec:rank-actions REQUIRES_INPUT · task:rank READS · rule:rank-value 주석에 식 추가. 테스트: test_cards 2개(긴급 OEM 오더에서 생산 유지 카드 가산 1.12 / 정지 카드 −1.12, 고온 로트 3000만원 → 55.4 ℃ 카드 −1.5)·test_decide_facts 3개. **단위 235 passed.** 미검증: Neo4j 재적재(`scripts/ontology_v2.py load`) 뒤 실제 카드 결과 변화(쿨러 시나리오: OEM 납기 6 h·보상 120 → fan-max-derate 가산, 고온 로트 800개 → fan-max 감산 예상).
- [~] C4 펌프·팬 시나리오(14번, 원문2 L187~188·L222~238; aad500b 알려진 한계 "펌프·팬 결함 시뮬레이터 없음") — 10-04 04:00 코드 완료·**단위 254 passed**·컨테이너 미검증. 온톨로지(instances.cypher)가 이미 가진 pattern:pump-leakage(PS1<165 ∧ FS1<8.0 ∧ LoadSP≥80)·pattern:fan-vibration(VS1>1.2 ∧ 상승)·원인·증거 SQL·스킬·예측(fc:pump-switch 182 bar, fc:fan-slow-vs1 1.0)·순위 규칙을 정답으로 삼아 그 아래층을 만들었다(DECISIONS 13).
  - 설비 `ot/plant-sim`: `thermal.py` 상태 `leak`(sv:leak, 펌프 A만)·`bearing_wear`(sv:bearing-wear)·`pump`(A|B) 추가, PS1 = 155+0.3·load−130·leak, FS1 = 10·load/100·(1−leak), VS1 = 0.55+0.004·(TS1−48)⁺+1.0·wear·(fan/60)²(AFFECTS "팬이 빠를수록 진동이 크다"), 누설 열 K_LEAK; 기본 목표 누설 0.15 → PS1 ≈162·FS1 ≈7.65, 마모 0.8 → VS1 ≈1.35(팬 40 % → ≈0.9, 팬 100 % → ≈2.8 인터록). `plant.py` Fault 일반화(`faults: dict[attr]`, kind cooler_degradation|pump_leakage|fan_vibration|restore, snapshot `faults`·`disturbances`). `plc.py` 쓰기 `PumpSelect`(0=A,1=B)·`Stop`(상태 STOP, Reset 으로 재기동), 인터록 OVERTEMP(TS1>65)·LOW_PRESSURE(PS1<130)·HIGH_VIBRATION(VS1≥2.0)(온톨로지 sv:ps1·sv:vs1 limit), status 에 leak·bearing_wear·pump. `main.py` `/api/fault` type 3종+restore(`target` 일반화, `target_health` 호환), `/api/reset` 전부 정상. `daq.py` FS1 을 AUX(30 s) → 데드밴드 0.1(CEP 입력).
  - 명령 경로: `hydcommon/schemas.py` 허용 목록 + PUMP_SELECT·STOP, `PUMP_CODES` A/B→0/1; PRESSURE_SET 은 계속 거부(규정 금지 구 절차, PLC 에 압력 SP 없음). 게이트웨이·포털·Grafana 경보 라벨에 펌프·팬 패턴.
  - 탐지기 `det/cep.py` 4단계 기계를 `_step` 으로 공유, `evaluate_pump`(clear: PS1≥168 ∧ FS1≥8.0 또는 LoadSP<80 — 부하 저감은 가림, 회복 아님)·`evaluate_fan`(clear: VS1<1.1 ∧ 기울기≤0); `det/main.py` 자산마다 pump/fan 상태·VS1 기울기 창, TS1 틱마다 세 패턴 평가, `/api/detector/state` 에 `patterns`.
  - 프로세스: `definition.RECOVERY` 패턴별 회복 기준(TS1<55 · PS1≥165 · VS1<1.2)·`recovered()`, `machine.on_timer` 가 인시던트 경보 패턴의 태그 값으로 판정(감사 detail 에 tag·value·criterion), `main.latest_tag(asset, tag)`(기존 `latest_ts1` 유지). `instances.py` 는 변경 없음(Incident 경로 그대로).
  - 포털: 결함 시뮬레이션 카드에 PS1·FS1·VS1·운전 펌프 표시, 버튼 쿨러 열화/펌프 누설/팬 베어링 마모/결함 복구, 패턴별 탐지 단계, 결함 진행·현재 교란 상태 문장; 카드 선택 폼에 운전 펌프 → B 안내; `card.py` 요약 문장 패턴 한글·패턴별 관측값.
  - 테스트 `tests/test_pump_fan.py` 19개(열모델 설계점·누설·펌프 B 복구·derate-70 가림·마모·팬 속도 증폭/인터록 · PLC 쓰기·인터록·status · 플랜트 램프·restore·레거시 계약 · CEP 펌프/팬 raise·clear·가림 · schemas/게이트웨이 PUMP_SELECT 통과·PRESSURE_SET 거부·PLC 적용 · 회복 기준·펌프 인시던트 종결/가림 실패·팬 연장) + test_daq FS1 1개.
  - 승인 시간초과 boundary timer 는 D3 에서 이미 구현(ev:select-timeout 행·`fire_timeouts`).
  - **미검증(컨테이너 필요)**: ① `docker compose up -d --build plant-sim detector process agent cmd-gateway portal`(+grafana 대시보드 재적재) ② 포털에서 HYD-02 펌프 누설 주입 → PUMP_LEAKAGE RAISE → 에이전트 카드(rule:dx-pump → cause:pump-seal-wear, rule:cand-pump, rule:no-pressure-raise 제외, 권고 switch-standby-pump) → 선택 → action.cmd PUMP_SELECT → PLC pump B → PS1 182 → CLEAR → 재관측 PS1≥165 → 작업지시 SOP-PMP-04 ③ HYD-03 팬 마모 → FAN_VIBRATION → dx-fan(ts1<52) → fan-slow-derate → VS1 <1.2 → 종결 ④ derate-70 선택 시 가림(CLEAR) 뒤 MITIGATION_FAILED 에스컬레이션 확인 ⑤ `scripts/scenario_test.py --quick` 회귀(쿨러) ⑥ 시나리오 스크립트에 펌프·팬 흐름 추가는 실제 실행 가능할 때 작성(검증 없는 스크립트는 만들지 않음) ⑦ 포털 캡처.
- [~] C5 후반 확장 강의 자료(13번, 원문2 L437~448·L172·L456)·교재·시수(14번, L187~188·L222~238) — 10-04 06:30 초안 완료.
  - 시수표 `docs/curriculum-75h.md`: 3시간×25회=75시간, 6부(L1~L6 12h · 온톨로지·인제스천 15h · 에이전트 15h · 프로세스·HITL 12h · 세 시나리오 15h · 확장·평가 6h). 회차마다 "왜 지금"(L236~238 시나리오 기반+딥다이브)·학생 행동·관찰·확인·교재·코드·분 배분(**전부 예상**, 자동 실행시간≠수업시간 명시). 회의 항목↔설계 대응표, 미결(학생 Claude Code 인증·펌프·팬 완주·인제스천 Neo4j·평가 방식) 표.
  - 교재 13장 `D:\work\study\시스템교재\13_확장_ProcessGPT.html`(5부 확장, index·12장 nav 연결): 인스턴스·todolist 상태 의미 → 워커(cliagents·tenants.mcp·폼·세션) → 사람 작업(폼·403·PT10M) → Execution 레이어(EXECUTION_Q) → 인제스천(DDL→System·InputData, 배치 되돌리기, 규칙→SQL) → 세 시나리오 비교표(함정 2건) → ProcessGPT 대응표(제품만 있는 것: 고착화·스티어링·정의 편집) → 데이터 패브릭 개념도(예시 표시). 설명 그림 6(실제 화면 0 — 새 기능 미기동이라 넣지 않음). 집필지침 준수: check_book 문제 0(checker는 `<code>` 안 단어 제외하도록 1줄 수정), render 1280/390 넘침 없음, 그림 전부 눈으로 확인(겹침 5건 고침).
  - 남은 것: 교재 11장에 펌프·팬 실습 절(실제 완주 캡처 뒤), 시수 실측 조정(강사 완주 뒤), 교재 작업 담당(박용주 이사·집필진)에게 초안 전달은 사용자 결정.

## 10. 새 세션용 복붙 대사

```
D:\work\study\hyd-iot-edu 작업을 전체 Goal로 이어가세요.
공유 CLAUDE.md와 로컬 AGENTS.md를 확인하고 docs/handoff/GOAL.md의 현재 계약 → HANDOFF.md §0·§9 G의 A071 후속 → QA.md 현재 답 → DECISIONS.md 최신 결정 → AUDIT.md·PROGRESS.md를 읽으세요.
목표는 회의 원문과 실제 uengine-oss 레포를 근거로 정의·온톨로지·규칙·현재 데이터가 바뀌어도 지원 계약에 맞게 동작하는 HYD 시스템을 구현·검증하는 것입니다. F 블록이나 고정 해피패스만 끝내는 목표가 아닙니다. 필요한 재설계를 하되 임의 간소화하지 말고, 교재·슬라이드·강의 리허설은 하지 마세요.
A066의47스냅샷/채택표와 A067~A070 원천/순위/BSC 검증을 유지하고 A071 별도 분기 조건의 새 검토·생산자 대기·타이머 도달을 연결했습니다(전체982/실제24/동일배포쿨러42, 새Codex 아님). 실패2종과 복구·배포·프로세스 상태는 §9A071을 확인하세요. 다음은 전체미결표 기준 R10/R11 실제효과 보상 계약을 C03 compensation_handler.py와 HYD rework_effects/승인·명령·기업영수증으로 대조하고, R01/R02/R06 원천→의미/지식→판단 변경수용을 이어가는 일입니다. 엔진 밖 전체 요구와47레포 채택을 빠뜨리지 마세요. 시작gateway/과거도달 미확인·실제추출·새Codex/UI 미결도 유지합니다. 검사기는 실제 API/시간계약부터 확인하고 관련검사 뒤 안정된 단계에서 전체검사를 수행하세요. 정책차단을 우회하거나 이미 통과한 동일 검사를 이유 없이 반복하지 마세요.
한국어로 답하고 시스템 구현·실행에 집중하며 단계별 최소 근거만 §9에 갱신하세요. 컴퓨터 리소스 기동·중지·필요한 삭제는 위임됐으나 WIP/원본은 보존합니다. 유료 결제·개인 Codex 기존 설정 변경은 묻습니다. 2026-10-05 보고 요청에서 이번 누적 작업의 origin/main push는 명시 승인됐으므로 재승인을 묻지 않습니다. A033의 실행 정책 거절은 다른 래퍼로 우회하지 말고 새Codex 검증과 레거시 검증을 구분하세요. 워커 종료는 PowerShell로 확인하세요.
```
