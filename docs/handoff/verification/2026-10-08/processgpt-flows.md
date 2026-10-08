# ProcessGPT 전체 흐름과 서비스 상호작용 — HYD 대응 (2026-10-08, 작업 A 1단계)

사용자 10-08: "래퍼 하나만 보지 말고 넓게, ProcessGPT 큰 틀 안의 마이크로서비스 상호작용을 조사해서 흐름을 파악하라." uengine-oss 레포를 세 묶음(S1 핵심 플랫폼 · S2 에이전트·도구·학습 · S3 온톨로지·데이터·전략)으로 나눠 실제 코드에서 호출 관계(주소 환경변수·HTTP·MCP·공유 DB 표·폴링·트리거)를 파일:줄로 뽑았다(부록 A~C, 각 레포 커밋은 부록 표). 메인이 핵심 주장을 원문으로 재확인했다: pg_cron `net.http_post`(process-gpt `docker-infra/volumes/db/init.sql:1719`), 에이전트 저장 `putAgent`(vue3 `ProcessGPTBackend.ts:4250`), 작업 배정 `agent_orch ← orchestration`(completion `polling_service/database.py:1223`), 피드백 → 전략 정렬(agent-feedback `core/feedback_batch_manager.py:104`), 전략 그래프 `corp_ontology`(strategy `app/config.py:34`), ontologic → ProcessGPT 프로세스 실행(robo-data-agent-scheduler `app/routers/profiles.py:900,948`), ProcessGPT 화면·엔진·배포 설정의 ontologic 호출 0건(grep). 실행 검증은 하지 않았다(코드 읽기 근거).

## 1. 한 장 요약 — 서비스는 HTTP보다 `todolist` 표의 상태 전이로 이어진다

- 사람·예약·외부 감시가 처리 건을 시작 → 엔진(completion)이 `todolist` 행을 만든다 → 폴링 서비스가 5초마다 `SUBMITTED` 행을 집어 다음 단계를 정하고, 에이전트 단계면 정의의 `orchestration`을 `agent_orch`에 적는다 → 그 값의 실행체(cli-agent·deepagents·codex·a2a…)가 SDK RPC `fetch_pending_task`로 가져가 처리하고 `SUBMITTED`로 되돌린다 → 진행·알림은 `events`·DB 트리거(`notifications`)·Realtime으로 화면(vue3)에 흐른다.
- 실행체는 작업을 맡을 때 `users`(is_agent 행 = 에이전트 정의), `tenants.mcp`(MCP 설정), 스킬 저장소(디스크·`tenant_skills`)를 읽어 실행 설정을 만든다.
- 학습 고리: `todolist.feedback` → agent-feedback(배치·분류) → 전략 서비스 정렬 근거 → 사람 승인 → 스킬 PR·DMN/BPMN 초안 판본.
- 온톨로지: ProcessGPT 안에는 전략 서비스가 쓰는 그래프(AGE `corp_ontology`, KPI·전략)와 vue3 `ontology/`의 6층 스키마가 있다. **이웃 플랫폼 ontologic(데이터 패브릭·text2sql·What-if·ontology-studio)은 ProcessGPT 본체가 부르지 않고, 반대로 ontologic의 감시 스케줄러가 ProcessGPT 프로세스를 MCP(`process-gpt-mcp` `execute_process`)로 시작한다.** ontology-studio는 ProcessGPT에 서브모듈로 등록돼 있으나 런타임 호출은 ontologic 쪽(데이터 패브릭 카탈로그·What-if)으로 나간다.

## 2. 흐름별 HYD 대응

| 흐름 | ProcessGPT에서 (서비스 → 서비스, 수단) | HYD 지금 | TODO |
|---|---|---|---|
| F1 정의 만들기·배포 | 말/문서 → deepagents 흐름 생성 스킬 또는 `process-gpt-mcp` → bpmn-extractor(`agent_orch=pdf2bpmn` 작업) → `proc_def`·초안 판본·PR → vue3 검토·배포 | 정의 JSON 등록·검사·버전·직접 시작·흐름도 있음. 경보 흐름은 파일 고정 | 그리기 → bpmn.io(외부). **배포 → 다음 경보부터 적용** 필수 |
| F2 시작 | 사람(vue3 → completion `/initiate`) · 예약(pg_cron → `/initiate`) · 외부 감시(ontologic agent-scheduler → `process-gpt-mcp` `execute_process`) | 설비 경보(detector → Kafka → start event)·직접 시작 있음 | 예약 시작은 넣지 않음 |
| F3 실행 | `todolist` 상태 전이, 폴링 엔진, 실행체 RPC 폴링, `events`·Realtime | 같은 구조(todolist·fetch_pending_task·임대·events·SSE) 있음 | — |
| F4 에이전트 정의 | vue3 `putAgent` → `users` is_agent 행 → SDK `extras.agents` → 실행체가 프로필·서브에이전트로 해석; "말 → 프로필"은 흐름 생성 스킬이 `agents/<id>.json` 작성 → 화면 저장 | users 칸은 같으나 실행에는 이름·역할 한 줄 | **에이전트 만들기** 필수 |
| F5 스킬 | deepagents `/skills`(디스크·`tenant_skills`·Git PR·평가표), `users.skills` 배정 → 실행체가 작업 폴더에 주입 | 정의 skills를 읽고 버림 | **스킬 붙이기** 필수 |
| F6 MCP | vue3가 `tenants.mcp`에 저장, mcp-validator가 연결 검사(저장 안 함), 실행체가 붙임 | `tenants.mcp`·실행 시 부착 있음, 등록·검사 없음 | **MCP 등록·검사** 필수 |
| F7 사람·알림 | `todolist.user_id` 배정, DB 트리거 → `notifications`, Realtime·푸시, 받은 함 | 역할 단위 배정, notifications 저장만 | **나에게 배정·받은 함·알림** 필수 |
| F8 학습 | `todolist.feedback` → agent-feedback → strategy `/api/ai/alignment` → 승인 → 스킬 PR·DMN/BPMN 초안 | 선례 자동 반영, 손 수정 API | **기록 → 개선 순환** 권장 |
| F9 문서 지식 | memento(문서·검색), 실행 산출물 되저장(`/process-output`, `/save-to-storage`) | 매뉴얼 → 지식 그래프·골든 질문 | 넣지 않음(회의 L242-245 "이 구조엔 문서 RAG 비중이 작다") |
| F10 전략·KPI | strategy-skill 인터뷰 → strategy(AGE `corp_ontology`) → 원천 표로 KPI 측정 → 보드 | BSC 지도 있음, 실적 없음 | **KPI 실적** 권장 |
| F11 데이터·온톨로지(ontologic) | data-fabric(MindsDB) → Neo4j 카탈로그 → analyzer·catalog 보강 → ontology-studio 설계·virtual class 바인딩 → text2sql `direct-sql`로 실데이터, domain-layer What-if; agent-scheduler가 조건을 감시해 ProcessGPT 프로세스 시작 | 지식 그래프·DDL 인제스천·입력 데이터 → 원천 링크·업무 DB 카탈로그 조회; 설비 감시 → 처리 건 시작은 detector로 있음 | **데이터 패브릭·What-if** 권장(ProcessGPT 본체 의존 아님, 회의 L63-67·L438-447 다음 확장) |
| F12 분석·분류 | analytic(병목·업무량), instance-classifier(유형) | 없음 | 넣지 않음(강의 가치 낮음) |

## 3. 원본 쪽 결함·불일치(참고 — HYD가 따라 하지 않을 것)
스키마 정본이 네 곳(meta init.sql·infra init.sql·vue3 migrations·agent-sdk function.sql)으로 갈려 meta 기준이면 최신 SDK RPC(`fetch_pending_task` 6인자·임대 함수)가 없음; 화면이 부르는데 받는 라우트가 없는 경로(`/completion/insert-sample`·`/agent-feedback/setup-agent-knowledge`·게이트웨이의 `/validate-and-improve`); 오케스트레이션 미지정 시 `crewai-deep-research`로 채워 compose에 없는 워커를 기다림; cli-agent가 http MCP를 조용히 버림; 스킬 저장소 두 갈래 동기화 없음; memento 주소 변수 이름 두 가지·운영 주소 하드코딩; ontologic 쪽 없는 경로 호출 3건, strategy가 AGE 없는 DB에 붙는 compose. 상세는 부록 각 §6.

## 부록 A — S1 핵심 플랫폼

작성: 2026-10-08, 읽기 전용 조사. 근거는 /tmp/claude-0/refs/<repo> 클론의 파일:줄.

### 0 조사 기준 (레포@커밋)

| 레포 | 커밋 | 커밋일 |
|---|---|---|
| process-gpt | 6084127 | 2026-10-08 |
| process-gpt-vue3 | a4f0a85 | 2026-10-08 |
| process-gpt-completion | b272c9a | 2026-10-01 |
| process-gpt-agent-sdk | 4d8f3b6 | 2026-10-08 |
| process-gpt-gateway | 2567edc | 2026-04-02 |
| process-gpt-infra-docker | 9e85485 | 2026-10-06 |
| process-gpt-k8s | 3022aaf | 2026-10-08 |
| process-gpt-session-router | a5edf5c | 2026-09-18 |

표기: `레포:파일:줄`. 레포 약칭 — meta=process-gpt, vue3, comp=process-gpt-completion, sdk=process-gpt-agent-sdk, gw=process-gpt-gateway, infra=process-gpt-infra-docker, k8s=process-gpt-k8s, sr=process-gpt-session-router.

#### 0.1 메타 레포 사실 (먼저 알아 둘 것)
- meta의 `docker-infra/docker-compose.yml`은 **인프라만**(litellm-db/litellm-proxy/age-postgres/Supabase 일체/neo4j) 띄운다. 마이크로서비스·nginx는 infra 레포 `docker-compose.yml`에 있다(meta:README.md:193, meta:.claude/skills/process-gpt-install/references/architecture.md:3-9).
- meta README는 `process-gpt-infra-docker`가 서브모듈이라 하지만(meta:README.md:191-199) 실제 meta `.gitmodules`에는 그 항목이 **없다**(23개 항목, 서비스 17 + 스킬 2 + 문서 1 + ontology-studio·agents.github.io·sample-app-wms). gateway·agent-sdk·session-router·k8s·infra-docker도 meta 서브모듈이 아니다.
- infra `.gitmodules`는 서비스 17개만 같은 URL로 다시 등록(infra:.gitmodules) — `build:` 용.
- age-postgres(AGE 그래프 PG16, 55433)는 strategy·bpmn-extractor 공유(meta:docker-infra/docker-compose.yml:43-50). neo4j 컨테이너는 "실제로는 미사용"이라고 메타 문서가 스스로 적는다(meta:.claude/skills/process-gpt-install/references/architecture.md 표 아래 ⚠️).
- 진입점 2개: nginx 게이트웨이 `:8088`(AI/에이전트 호출), Supabase Kong `:54321`(프런트가 Auth/REST/Realtime/Storage 직결). tenant_id는 접속 호스트명에서 파생, RLS가 JWT `app_metadata.tenant_id` 검사(meta:Process-GPT-Local-Setup-Guide.md:42-56).

### 1 서비스 표 (S1 핵심 플랫폼)

| 서비스 | 한 줄 역할 | 포트·주소 환경변수 | 나가는 호출(요약) | 들어오는 호출(요약) |
|---|---|---|---|---|
| **frontend** (process-gpt-vue3) | Vue3 SPA. Supabase에 직결(Auth/REST/Realtime/Storage), AI·에이전트 호출만 게이트웨이 경유 | 컨테이너 8080(infra:docker-compose.yml:43-53), dev vite 5199 계열. `VITE_SUPABASE_URL`=`API_EXTERNAL_URL`, `VITE_UENGINE_GATEWAY_URL`(기본 :8088), `VITE_AGENT_GATEWAY_URL`(vue3:vite.config.ts:11,17) | Supabase 표 50여 개 직접 읽기/쓰기, realtime 구독, `/completion/*`, `/memento/*`, `/process-gpt-deepagents/*`, `/feedback-proposals`, `/mcp/*`, `/strategy-service/api`, `/api/analytics`, `/instance-classifier`, `/agent-router`, `/claude-skills/*`, `/process-gpt-codex`, `/process-gpt-cli-agent` (아래 §2) | 브라우저, 게이트웨이 catch-all `/**` |
| **게이트웨이 A: nginx** (infra-docker) | 도커 설치용 단일 진입점 | `:8088`(infra:docker-compose.yml:568-582, infra:nginx/nginx.conf:18) | `/agent/chat/stream`→base-agent:8000, `/deepagents/*`→deepagents:8888, `/langchain-chat/`·`/completion/`→completion:8000, `/memento/`→memento:8005, `/robo/`→glossary:5504, `/instance-classifier/`→:8000, `/strategy-service/`→strategy:8000, `/`→frontend:8080, `/agent-router/route`→**503 고정**(nginx.conf:34-36) | 브라우저 |
| **게이트웨이 B: Spring Cloud Gateway** (vue3/gateway — 운영 정본으로 보임) | K8s 운영 진입점. Host 첫 라벨→`X-Tenant-Id`, 일부 경로 JWT 검증 | `:8080`(k8s deployments/gateway.yaml 컨테이너포트 8080, ingress `*.process-gpt.io`→gateway, k8s:ingress/gateway-ingress.yaml:36-62) | docker 프로필 라우트(vue3:gateway/src/main/resources/application.yml:166-531): `/litellm`, `/mcp/**`→mcp-proxy-service:80, `/mcp-validator`→:8800, `/completion`→completion-service:8000, `/claude-skills`→:8765, `/memento`→memento-service:8005, `/robo`→glossary:5504, `/voice`, `/api/analytics`→analytic-service:8000, `/agent-router`→:8001, `/process-gpt-deepagents`→:8888, `/process-gpt-codex`→:8891, `/process-gpt-cli-agent`→:8890, `/agent`→base-agent:8000, `/api/agent-feedback`·`/feedback-proposals`→agent-feedback-service:6789, `/vnc/*`·`/api/processgpt-browser-server-*`→browser-server-N, `/wms`, `/**`→frontend-service:5173. 인증 대상 `/completion/(set-tenant 등 제외)`, `/memento`, `/agent`, `/mcp`, `/robo`(vue3:gateway/src/main/java/shop/ForwardHostHeaderFilter.java:53-58) | 브라우저(인그레스) |
| **process-gpt-gateway** (별도 레포) | 위 B의 옛 버전(2026-04). `/execution`→:8000, `/autonomous`→:6789, `/memento`, `/voice`, `/payments`→billing:7000, `/mcp/**`, `/**`→frontend. 크레딧 검사 필터가 Supabase RPC `get_credit_balance` 호출 | `:8088`(default)/`:8080`(docker) (gw:src/main/resources/application.yml:1-2,179-180) | Supabase `/rest/v1/rpc/get_credit_balance`(gw:src/main/java/shop/filter/CreditValidationFilter.java:62) — **이 RPC는 meta·infra init.sql 어디에도 없다** | k8s 배포 이미지 태그 `0f61d8a`(k8s:deployments/gateway.yaml:34)는 이 레포 main(2567edc)에 없음 → 운영 이미지 소스 미확인 |
| **completion** (process-gpt-completion) | 실행 엔진 API: 처리 건 시작·제출(`/initiate`,`/complete`), LLM 채팅 프록시(`/langchain-chat/*`), 사용자·테넌트 관리, 피드백·재작업, 검증·회귀, 대시보드 | 8000(infra:docker-compose.yml:60). `SUPABASE_URL/KEY`, `DB_*`, `LLM_PROXY_URL`(기본 `http://litellm-proxy:4000`, comp:llm_factory.py:21), `FCM_SERVICE_URL`(기본 `http://fcm-service:8666`, comp:fcm_client.py:14), `COMPLETION_VALIDATION_ENGINE_URL`(자기 자신, comp:validate_improve.py:30-36), `API_PATH_PREFIX` | Supabase 표(todolist·bpm_proc_inst·proc_def·proc_def_version·form_def·events·users·configuration·admin_requests·chats·tenants·mcp_python_code·proc_inst_source), RPC `insert_usage_from_payload`·`get_migration_target_processes`, Supabase Auth `/auth/v1/user`·`/auth/v1/admin/users`(comp:process_db_manager.py:114,255), LLM(litellm), mem0 벡터저장(Supabase vecs `memories`, comp:mem0_agent_client.py:113-133), A2A `/.well-known/agent.json`(comp:agent_chat.py:58), FCM 서비스, 자기 자신(검증 시) | frontend, deepagents(`/complete`, `/regression-*`), pg_cron(`/initiate`), 게이트웨이 |
| **polling-service** (completion 레포 `polling_service/`) | 워크아이템 엔진 루프: SUBMITTED/PENDING todolist를 집어 다음 단계 판정(LLM)·다음 워크아이템 생성·서비스태스크(MCP/파이썬) 실행 | 8010→8000(infra:docker-compose.yml:97-100), 이미지 `process-gpt-polling-service`. `COMPLETION_SERVICE_URL`, `MEMENTO_SERVICE_URL`(infra:110-111; 코드 기본 `http://memento-service:8005`, comp:polling_service/workitem_processor.py:2125), `CONSUMER_FILTER` | todolist 폴링·점유(5초 주기, comp:polling_service/polling_service.py:119-221), bpm_proc_inst·proc_def·proc_def_version·proc_def_arcv·form_def·events·chats·users·configuration·tenants(`mcp`)·mcp_python_code·proc_inst_source, RPC `exec_sql`·`register_cron_intermidiated`, memento `POST /process-output`(workitem_processor.py:2131), 테넌트 MCP 서버(MultiServerMCPClient, mcp_processor.py:108), SMTP 메일(workitem_processor.py:693), Upstage 문서파싱(document_parser.py:25), **하드코딩 ngrok Twilio 트리거**(database.py:1704-1726) | 없음(DB 폴링만) |
| **fcm-service** (completion 레포 `fcm_service/`) | 푸시 알림: `notifications` 표 미처리 행을 consumer 점유로 집어 Firebase 전송 | 8666(comp:fcm_service/fcm_service.py:113) | Supabase `notifications`(consumer 점유, comp:fcm_service/database.py:322-357), `user_devices`, `users`; Firebase Admin `messaging` | completion `POST /send-notification`(comp:fcm_client.py:28). compose에는 없음, k8s에만(k8s:deployments/fcm-service-deployment.yaml) |
| **process-gpt-agent-sdk** (라이브러리) | 에이전트 공통 계약: todolist 폴링·점유·lease·이벤트·결과 저장·채팅 SSE 라우트 | 서버 아님. `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `CONSUMER_ID`, `LLM_PROXY_URL`(sdk:processgpt_agent_sdk/integrations/llm_proxy.py:32-34) | RPC `fetch_pending_task`(6인자)·`renew_task_lease`·`release_task_lease`·`save_task_result`·`record_events_bulk`, 표 todolist·events·chats·form_def·users·tenants(mcp)·proc_inst_source·chat_rooms·env(browser_use)·`agent_sessions`+버킷 `agent-sessions`(sdk:processgpt_agent_sdk/database.py:164-833, session.py:21-39), memento `POST /save-to-storage`(sdk:artifacts/store.py:68-69) | 이를 쓰는 에이전트(→S2 deepagents·codex·crewai-action·a2a-orch·bpmn-extractor 등)가 `/chat/stream`·`/chat/stream/attach`·`/chat/stop`·`/chat/steer`를 노출(sdk:processgpt_agent_framework.py:878-930) |
| **session-router** (Go) | 대화(conversation_id)마다 런너 Pod를 띄워 채팅을 그 Pod로 붙이고 유휴 TTL 회수 | `ROUTER_ADDR` :8080, `ROUTER_SESSION_PATHS`(기본 `/chat/stream`,`/chat/stream/attach`,`/chat/stop`), `ROUTER_FALLBACK_UPSTREAM`, `ROUTER_RUNNER_PORT`(sr:internal/config/config.go:60-71) | K8s API(Pod 생성/라벨/삭제), 런너 Pod `/health`·세션경로 프록시, 비채팅 경로→fallback Deployment(sr:README.md "동작" 1-5) | 게이트웨이 B가 `process-gpt-codex`/`process-gpt-deepagents` Service로 보내면 그 Service 셀렉터가 라우터를 가리킴(k8s:deployments/session-router.yaml:4-8, 79-97, 146-161) |
| **infra-docker** | 로컬·단일서버 설치: compose 1개(인프라+서비스 17+nginx) | — | 서비스 env로 연결 정의(§2) | — |
| **k8s** | 운영 매니페스트(deployments 46개, KEDA, ingress, rbac) | — | KEDA가 Postgres에 직접 todolist 질의로 스케일(k8s:keda/keda-scaled-objects.yaml:21-29, keda/pdf2bpmn-scaledjob.yaml:125-129) | — |
| **Supabase(db/kong/auth/rest/realtime/storage)** | 정본 저장소·인증·실시간 | Kong 54321, db 54322(호스트) | **pg_cron→completion `/initiate`**(net.http_post, meta:docker-infra/volumes/db/init.sql:1708-1723), 트리거로 notifications 생성 | 모든 서비스 |
| **litellm-proxy** | LLM 프록시 | 4000(내부), 호스트 `LITELLM_PORT`(기본 4010) | 외부 LLM | completion·polling·memento·a2a·analytic·office-mcp·deep-research·runner 등 |

### 2 연결 목록 (출발→도착, 방식, 근거)

레포@커밋은 §0 표. "→S2/S3"는 다른 묶음이 이어서 본다.

#### 2.1 프런트엔드(vue3@a4f0a85) 발신
| # | 출발→도착 | 방식 | 근거 |
|---|---|---|---|
| F1 | frontend→Supabase(REST/PostgREST) | 표 직접 읽기/쓰기: proc_def(48곳)·users·configuration·proc_def_version·todolist·bpm_proc_inst·form_def·lock·notifications·tenants·tenant_git_config·resource_pull_requests·agent_skills·env·events·chats·proc_inst_source 외 50여 개 | `grep from()/storage.putObject` 집계; 예 vue3:src/components/api/ProcessGPTBackend.ts:3135(todolist 읽기), 3191(chats 쓰기), 616(proc_def 쓰기) |
| F2 | frontend→Supabase RPC | `register_cron_job`·`delete_cron_job`·`get_cron_jobs`(일정 시작), `ontology_business_graph`·`ontology_execution_rollup`·`ontology_graph_health`(→S3), 멤버십·감사 RPC | ProcessGPTBackend.ts:7392,7429; `grep .rpc(` |
| F3 | frontend←Supabase Realtime | 구독: bpm_proc_inst(3310,3345)·todolist(3371,7514 UPDATE)·chats(3773)·tenant_skills(3813)·notifications(3831)·events(7500 INSERT `todo_id=eq.`)·feedback_proposals(8805)·proc_def_approval_state(views/review-board/*) | ProcessGPTBackend.ts 해당 줄 |
| F4 | frontend→completion | HTTP `/completion/complete`·`/vision-complete`(처리 건 시작·제출), `/generate-name`, `/role-binding`, `/process-search`, `/set-tenant`·`/create-user`·`/invite-user`·`/update-user`, `/get-feedback`·`/get-feedback-diff`·`/get-rework-activities`·`/rework-complete`, `/mcp-tools`, `/process-definition/start-activity`, `/test/initiate`, `/multi-agent/fetch-data`, `/langchain-chat/messages`(AIGenerator 30여 종), `/langchain-chat/embeddings` | ProcessGPTBackend.ts:897,899,922,3744,4033,4697,4803,4830,4863,8107,8130,8353,8369,7223,11622,11647,4467,5311; vue3:src/components/ai/AIGenerator.js:76 |
| F5 | frontend→completion `/insert-sample` | HTTP POST | ProcessGPTBackend.ts:5685 — **completion 레포에 이 경로 없음**(끊긴 고리) |
| F6 | frontend→memento(→S3) | `/memento/process`·`/process/status`·`/process/drive/status`·`/save-to-storage`·`/save-to-drive`·`/auth/google/*` | ProcessGPTBackend.ts:4955,4993,5048,5127,5190,5219,5260,5269 |
| F7 | frontend→deepagents(→S2) | `/process-gpt-deepagents/skills*`(목록·업로드·파일·커밋·브랜치·PR·병합·동기화), `/resources/{bpmn,dmn}/{id}/verification/scenarios`, 채팅 `DeepAgentRouterService.js` | ProcessGPTBackend.ts:8657,8739,9059,9085,9167; vue3:src/services/DeepAgentRouterService.js:10 |
| F8 | frontend→agent-feedback(→S2/S3) | `/feedback-proposals`(목록·my-feedback·targets 결정), `/agent-feedback/setup-agent-knowledge` | ProcessGPTBackend.ts:8772,8793,8838,4477 |
| F9 | frontend→mcp-proxy(→S2) | `/mcp/tools`, `/mcp/configmaps`, `/mcp/secrets`(K8s ConfigMap/Secret CRUD) | ProcessGPTBackend.ts:7785-7855,7932 |
| F10 | frontend→claude-skills(→S2) | `/claude-skills/skills/check` | ProcessGPTBackend.ts:8698 |
| F11 | frontend→strategy(→S3) | `/strategy-service/api` | vue3:src/stores/strategy/strategyStore.ts:7 |
| F12 | frontend→analytic(→S3) | `/api/analytics/*`(대시보드·contribution) | vue3:src/services/analyticsApi.ts:8, strategyStore.ts:190 |
| F13 | frontend→instance-classifier(→S3) | `/instance-classifier` | vue3:src/utils/instanceClassifier.ts:8 |
| F14 | frontend→agent-router(→S2) | `/agent-router/*`(warmup·route) | vue3:src/services/AgentRouterService.js:14 |
| F15 | frontend→mcp-validator(→S2) | `/mcp-validator/*` | vue3:src/services/McpValidatorService.js |
| F16 | frontend→codex / cli-agent(→S2) | `/process-gpt-codex/*`, `/process-gpt-cli-agent/*` | vue3:src/services/agentProxyRules.js:23-26; src/components/ui/field/AgentSelectField.vue |
| F17 | frontend→PAL 백엔드(범위 밖) | `/pi-system-backend/langchain-chat/generate-bpmn/stream` 등(PAL 모드) | vue3:src/services/bpmnGenerationService.ts:22,151,179,330 — 대상 레포 미확인 |
| F18 | frontend→uEngine(Java BPM) 백엔드 | `/definition`,`/instance`,`/work-item`,`/worklist`,`/dry-run`,`/business-rules`… (uEngine 모드일 때 `UEngineBackend`) | vue3:vite.config.ts:265-325; vue3:src/components/api/BackendFactory.ts:119-128 |

#### 2.2 게이트웨이
| # | 출발→도착 | 방식 | 근거 |
|---|---|---|---|
| G1 | nginx→base-agent/deepagents/completion/memento/glossary/instance-classifier/strategy/frontend | HTTP 리버스 프록시(경로 접두 제거) | infra:nginx/nginx.conf:22-161 |
| G2 | nginx `/agent-router/route` | 503 고정(라우터 미사용) | infra:nginx/nginx.conf:34-36 |
| G3 | Spring 게이트웨이(vue3/gateway)→litellm·mcp-proxy·mcp-validator·completion·claude-skills·memento·glossary·voice·analytic·agent-router·deepagents·codex·cli-agent·base-agent·agent-feedback·browser-server(vnc/api)·wms·frontend | HTTP(RewritePath), `X-Tenant-Id`=Host 첫 라벨, 일부 경로 Supabase JWT 검증 | vue3:gateway/src/main/resources/application.yml:166-531; vue3:gateway/src/main/java/shop/ForwardHostHeaderFilter.java:48-98 |
| G4 | process-gpt-gateway(옛)→execution:8000/autonomous:6789/memento/voice/billing:7000/mcp-proxy/frontend | HTTP | gw:src/main/resources/application.yml:72-155 |
| G5 | process-gpt-gateway→Supabase RPC `get_credit_balance` | 크레딧 검사 필터 | gw:src/main/java/shop/filter/CreditValidationFilter.java:34-62 (RPC 정의 미발견) |
| G6 | Ingress `*.process-gpt.io`→gateway(http·vnc·api 포트), `insurance.process-gpt.io`→insurance-backoffice | K8s Ingress | k8s:ingress/gateway-ingress.yaml:24-62 |
| G7 | gateway→session-router→런너 Pod | Service 셀렉터를 라우터로 돌려 세션 경로만 Pod로, 나머지 `ROUTER_FALLBACK_UPSTREAM`(`process-gpt-codex-shared:8891`, `process-gpt-deepagents-shared:8888`) | k8s:deployments/session-router.yaml:4-11,83-89,150-155 |
| G8 | session-router→K8s API / 런너 `/health` | Pod 생성(PodTemplate `agent-runner-<type>`)·라벨·회수 | sr:README.md "동작" 3·5, sr:internal/session/kube.go; k8s:deployments/agent-runner-templates.yaml:19,135 |

#### 2.3 completion(API, b272c9a) 발신
| # | 출발→도착 | 방식 | 근거 |
|---|---|---|---|
| C1 | completion→Supabase | 표 쓰기: bpm_proc_inst(시작 시 `RUNNING`/`NEW`), todolist(`/initiate`→`TODO`, `/complete`→`SUBMITTED`) | comp:process_engine.py:112-123, 298, 348, 374, 545-559 |
| C2 | completion→Supabase Auth | `/auth/v1/user`(토큰 검증), `/auth/v1/admin/users`(사용자 조회) | comp:process_db_manager.py:114-120, 255-260 |
| C3 | completion→LLM(litellm) | LangChain 체인(`/complete` 판정, 피드백, 이름짓기, langchain-chat) | comp:llm_factory.py:21; process_engine.py:598-637 |
| C4 | completion→Supabase vecs `memories` | mem0(`/multi-agent/chat` 학습 모드) | comp:mem0_agent_client.py:113-133; agent_chat.py:16,37 |
| C5 | completion→외부 A2A 에이전트 | GET `{agent_url}/.well-known/agent.json` | comp:agent_chat.py:53-60 |
| C6 | completion→fcm-service | POST `/send-notification`, GET `/device-token/{id}` | comp:fcm_client.py:14,28-40,68 |
| C7 | completion→자기 자신 | 초안 검증 시 실행 엔진 구동 | comp:validate_improve.py:30-36; process_validator.py:842-853 |
| C8 | completion→테넌트 MCP 서버 | `tenants.mcp`로 도구 색인(보상 처리) | comp:compensation_handler.py:29; mcp_tool_index.py:72 |
| C9 | completion `/mcp-tools` | 로컬 `mcp.json` 반환(DB 아님) | comp:mcp_config_api.py:5-14 |

#### 2.4 polling-service 발신
| # | 출발→도착 | 방식 | 근거 |
|---|---|---|---|
| P1 | polling→todolist | 폴링 5초: `status=SUBMITTED AND consumer IS NULL` 10건을 consumer=hostname으로 조건부 UPDATE 점유, `PENDING` 5건; 30분 넘은 consumer 해제 | comp:polling_service/database.py:909-1045; polling_service.py:119-221 |
| P2 | polling→LLM | 완료 판정·다음 활동·조건식·역할바인딩(`run_prompt_and_parse`) | comp:polling_service/workitem_processor.py:4926-5000 |
| P3 | polling→todolist(다음 워크아이템) | 다음 활동 행 생성: `agent_mode`(활동 설정 또는 담당자 유형으로 결정: 사람+에이전트=DRAFT, 에이전트만=COMPLETE), `agent_orch`(활동 `orchestration`, 비면 `crewai-deep-research`; 서브프로세스 adhoc은 `deepagents`) | comp:polling_service/database.py:1491-1494, 1538-1543, 1639-1662, 2323-2360; workitem_processor.py:1391-1392,1635-1636 |
| P4 | polling→bpm_proc_inst / chats / events | 인스턴스 상태·완료, 시스템 메시지 | comp:polling_service/database.py:673 등 |
| P5 | polling→proc_def `prod_version` | 배포 승인 활동(isDeploy)이 승인되면 갱신 | comp:polling_service/workitem_processor.py:5004-5011 |
| P6 | polling→memento(→S3) | POST `/process-output` {workitem_id, tenant_id} — 매 처리 끝(finally) | comp:polling_service/workitem_processor.py:2125-2136, 5017-5019 |
| P7 | polling→테넌트 MCP 서버 | 서비스태스크: `tenants.mcp`의 서버로 MultiServerMCPClient 실행 | comp:polling_service/mcp_processor.py:58-111, 129-205; workitem_processor.py:5141 |
| P8 | polling→mcp_python_code / 파이썬 실행 | 결정적 코드 재실행 | comp:polling_service/workitem_processor.py:1677 |
| P9 | polling→pg_cron | 타이머 중간이벤트: RPC `register_cron_intermidiated` → cron이 `update_todolist_status`로 todolist를 SUBMITTED로 | comp:polling_service/workitem_processor.py:1880-1901; meta init.sql:2140-2203 |
| P10 | polling→SMTP | 외부 고객 이메일(외부 폼 링크 `https://{tenant}.process-gpt.io/external-forms`) | comp:polling_service/workitem_processor.py:637-701 |
| P11 | polling→Upstage | 첨부 문서 파싱 | comp:polling_service/document_parser.py:25,52 |
| P12 | polling→ngrok Twilio 호출 | **하드코딩 테스트 코드**: 특정 이메일 담당 워크아이템 생성 시 외부 URL POST | comp:polling_service/database.py:1702-1729 |

#### 2.5 agent-sdk(4d8f3b6) — 에이전트 쪽 계약
| # | 출발→도착 | 방식 | 근거 |
|---|---|---|---|
| A1 | 에이전트(sdk)→todolist | RPC `fetch_pending_task(p_agent_orch, p_consumer, 1, p_env, p_lease_seconds, p_max_claims)`: `IN_PROGRESS` + (`agent_mode∈{DRAFT,COMPLETE}` 미착수 또는 `draft_status=FB_REQUESTED`) → `draft_status=STARTED`, consumer 기록 | sdk:processgpt_agent_sdk/database.py:164-174; sdk:processgpt_agent_sdk/function.sql:34-114 |
| A2 | 에이전트→todolist lease | RPC `renew_task_lease`·`release_task_lease` | sdk:database.py:224-250 |
| A3 | 에이전트→todolist 결과 | RPC `save_task_result(final)`: COMPLETE면 `output`·`status=SUBMITTED`, DRAFT면 `draft`만 | sdk:database.py:401; meta init.sql:2421-2455 |
| A4 | 에이전트→todolist 상태 | `HUMAN_ASKED`(질문 남김), `FAILED` | sdk:database.py:479-533 |
| A5 | 에이전트→events | RPC `record_events_bulk`(실패 시 표 직접 insert) | sdk:database.py:333,351,374; meta init.sql:2902-2917 |
| A6 | 에이전트→chats | upsert(on_conflict uuid) | sdk:database.py:447,457 |
| A7 | 에이전트→컨텍스트 조회 | form_def, users(담당·에이전트), tenants.mcp, proc_inst_source, 알림 이메일 | sdk:processgpt_agent_framework.py:98-125 |
| A8 | 에이전트→env | `browser-automation-agent`일 때 `env.key='browser_use'` 비밀값 | sdk:database.py:191-200 |
| A9 | 에이전트→memento(→S3) | POST `/save-to-storage`(산출물) | sdk:artifacts/store.py:21-69 |
| A10 | 에이전트→agent_sessions 표·`agent-sessions` 버킷 | 대화 상태 복원(Pod 회수 후 이어가기) | sdk:session.py:21-39 |

#### 2.6 DB 내부(트리거·pg_cron·Realtime)
| # | 출발→도착 | 방식 | 근거 |
|---|---|---|---|
| D1 | todolist INSERT/UPDATE(→`IN_PROGRESS`)→notifications | 트리거 `todolist_change_trigger`/`handle_todolist_change` | meta:docker-infra/volumes/db/init.sql:1037-1086,1384 |
| D2 | todolist UPDATE→notifications.user_id 갱신, DELETE→알림 삭제 | 트리거 | init.sql:1088-1108,1390-1401 |
| D3 | chats INSERT→notifications(채팅방에 5분 내 접속 없는 참가자) | 트리거 `chat_insert_trigger` | init.sql:1110-1168,1403 |
| D4 | notifications→fcm-service→Firebase | 폴링 점유(consumer) | comp:fcm_service/database.py:299-380 |
| D5 | pg_cron `register_cron_job`→`start_process_scheduled`→**completion `/initiate`** | `net.http_post('http://host.docker.internal:8000/initiate')` + `cron_job_run_log` | init.sql:1708-1790 |
| D6 | pg_cron 타이머→todolist SUBMITTED | `register_cron_intermidiated`→`update_todolist_status_with_year`→`update_todolist_status` | init.sql:2109-2203 |
| D7 | pg_cron 정리 잡 | 삭제 테넌트·인스턴스 정리 | init.sql:1826-1910, 1914-2015 |
| D8 | auth.users INSERT→public.users | 트리거 `on_auth_user_created` | init.sql:183-230 |
| D9 | Realtime 발행 표 | chats·notifications·todolist·bpm_proc_inst·proc_def·project·events | init.sql:1668-1692 |
| D10 | KEDA→todolist COUNT | `IN_PROGRESS AND agent_orch='browser-automation-agent'`/`'pdf2bpmn'`이면 워커 확장 | k8s:keda/keda-scaled-objects.yaml:21-29; keda/pdf2bpmn-scaledjob.yaml:36-37,125-129 |

#### 2.7 설정으로 확인되는 서비스 간 주소(배포 매니페스트)
| # | 출발→도착 | 근거 |
|---|---|---|
| E1 | polling→completion(`COMPLETION_SERVICE_URL`)·memento | infra:docker-compose.yml:110-111; k8s:deployments/polling-service-deployment.yaml:60-63 (코드에서 COMPLETION_SERVICE_URL 사용처는 polling 안에 없음 — 미사용 설정으로 보임) |
| E2 | deepagents(→S2)→completion `/complete`·`/regression-run`·`/regression-scenarios` | k8s:deployments/process-gpt-deepagents-config.yaml:40; process-gpt-deepagents@faedeaa core/bpm/tools.py:46,531; core/skills/regression_client.py:21-34; comp:regression/api.py:181-182 |
| E3 | deepagents(→S2)→office-mcp·memento·claude-skills·redis | infra:docker-compose.yml:471-473; k8s:deployments/process-gpt-deepagents-config.yaml:33-39 |
| E4 | agent-feedback(→S2/S3)→deepagents 스킬 API·claude-skills MCP·computer-use MCP | k8s:deployments/agent-feedback.yaml:83-94 |
| E5 | crewai-deep-research(→S2)→memento | k8s:deployments/crewai-deep-research-deployment.yaml:90-91 |
| E6 | 거의 모든 LLM 사용 서비스→litellm-proxy:4000 | k8s deployments 다수(completion-deployment.yaml:27-28 등), infra compose |
| E7 | agent-router→`http://agent-{agent_id}:8000`(K8s Pod 생성) | infra:docker-compose.yml:214-232; k8s:deployments/agent-router-deployment.yaml:32-33 |
| E8 | strategy·bpmn-extractor→age-postgres(55433) | meta:docker-infra/docker-compose.yml:43-50 |

### 3 공유 표 (누가 쓰고 누가 읽나)

S1 서비스는 코드 근거로, S2/S3 레포는 `grep`으로 표 이름이 코드(.py/.ts/.js/.go)에 나오는 레포만 적었다(읽기/쓰기 구분은 →S2/S3 확인).

| 표 | 쓰는 쪽(S1) | 읽는 쪽(S1) | 다른 묶음에서 이 표를 만지는 레포 | 비고 |
|---|---|---|---|---|
| **todolist** (워크아이템=작업 큐) | completion(`/initiate` TODO, `/complete` SUBMITTED), polling(다음 활동 생성·consumer 점유·DONE), sdk 에이전트(STARTED/HUMAN_ASKED/FAILED, draft/output, SUBMITTED via `save_task_result`), frontend(temp_feedback, FB_REQUESTED, 위임), pg_cron(`update_todolist_status`) | polling, sdk(`fetch_pending_task`), frontend(Realtime), KEDA, fcm(간접) | a2a-orch, agent-feedback, agent-utils, analytic, bpmn-extractor, codex, crewai-deep-research, deep-research, deepagents, instance-classifier, memento, openai-deep-research, react-voice-agent | **상태 기계가 서비스 사이 핸드오프의 중심.** 열 status(TODO/IN_PROGRESS/SUBMITTED/PENDING/DONE…)·draft_status(STARTED/COMPLETED/FB_REQUESTED/HUMAN_ASKED/CANCELLED/FAILED)·agent_mode(DRAFT/COMPLETE)·agent_orch·consumer·lease_until |
| **bpm_proc_inst** (처리 건) | completion(시작 시 insert), polling(진행·완료 갱신), frontend(삭제·수정) | 전부 | bpmn-generation-skill, agent-feedback, analytic, bpmn-extractor, deepagents, instance-classifier, react-voice-agent | Realtime 발행. 삭제 시 트리거로 연관 데이터 정리(init.sql:1914-1940) |
| **events** (에이전트 실행 로그) | sdk 에이전트(`record_events_bulk`), polling, frontend(human_response 기록, AgentMonitor.vue:985) | frontend(Realtime `todo_id=eq.`) | a2a-orch, agent-feedback, agent-utils, crewai-deep-research, deep-research, deepagents, openai-deep-research | event_type enum 13종(init.sql:91-105) — **infra init.sql은 10종**(waiting_for_user·task_cancelled·human_feedback_submitted 없음) |
| **proc_def / proc_def_version / proc_def_arcv / form_def** (정의) | frontend(저장·버전), completion(upsert_process_definition), polling(prod_version) | polling·completion(실행), sdk(form_def) | bpmn-generation-skill, agent-feedback, agent-utils, analytic, base-agent, bpmn-extractor, cli-agent, deepagents, react-voice-agent(proc_def) / form_def는 S2 대부분 | proc_def는 Realtime 발행 |
| **users** (사람+에이전트 한 표, `is_agent`·`agent_type`·`goal`) | auth 트리거(D8), completion(create/invite/update-user), frontend | polling(담당자 유형→agent_mode), sdk, fcm | 거의 모든 S2 + memento·analytic | 에이전트 정의가 users 행 → S2 |
| **tenants** (`mcp` jsonb) | frontend | polling(MCP 서비스태스크), completion(보상·도구색인), sdk(컨텍스트) | agent-feedback, agent-utils, analytic, base-agent, bpmn-extractor, crewai-deep-research, deepagents | **테넌트 MCP 설정 = 실행 시 도구 목록의 출처** |
| **tenant_skills / agent_skills** | frontend(agent_skills 삭제 등) | frontend(Realtime tenant_skills) | deepagents(tenant_skills), agent-feedback·bpmn-extractor(agent_skills) | 스킬 본문은 deepagents 스토어(→S2) |
| **chats / chat_rooms** | frontend(인스턴스 채팅), sdk 에이전트(upsert), polling | frontend(Realtime — 채팅 렌더 필수) | react-voice-agent | chats INSERT→알림 트리거 |
| **notifications** | DB 트리거(todolist·chats), frontend | fcm-service(점유), frontend(Realtime) | agent-utils | |
| **configuration** (조직도 등) | frontend | polling(organization chart), completion | bpmn-generation-skill, bpmn-extractor, deepagents, react-voice-agent | |
| **proc_inst_source** | frontend, completion | polling, sdk | deep-research | 첨부·원천 자료 |
| **feedback_proposals** | (S2/S3 agent-feedback), RPC `decide_feedback_proposal_target` | frontend(Realtime·목록) | agent-feedback | 상태 COLLECTING→PROPOSED→APPROVED/REJECTED… |
| **resource_pull_requests / resource_pr_reviews / tenant_git_config** | frontend | frontend | (deepagents 스킬 PR — →S2) | 스킬·BPMN·DMN 변경을 PR로 관리 |
| **knowledge_files / documents / document_pages** | (memento →S3) | (에이전트) | memento | match_documents RPC(init.sql:664) |
| **mcp_python_code** | completion | polling(결정적 실행) | — | **CREATE TABLE이 meta·infra init/migration 어디에도 없음**(openspec e2e seed에만) |
| **env** | frontend | sdk(browser_use) | — | 테넌트 비밀값 |
| **agent_sessions** + 버킷 `agent-sessions` | sdk 런너 | sdk 런너 | codex(`codex_threads`) | **meta·infra init.sql에 없음**, sdk:database_schema.sql에만 |

### 4 끝에서 끝까지 흐름 (시나리오별 화살표)

표기: `[서비스]` —(방식)→ `[서비스/표]`. ✔=코드로 확인, ?=미확인, →S2/S3=다른 묶음이 이어 봄.

#### ① 말·문서로 프로세스 정의 만들기 → 저장 → 검토·배포
경로가 넷이다.
- (a) 가벼운 채팅 생성 ✔: `[frontend ProcessDefinitionGenerator 등 AIGenerator 서브클래스]` —(XHR 스트리밍 `/completion/langchain-chat/messages`)→ `[completion→litellm]` → 응답 JSON을 프런트가 부분 파싱 → `putRawDefinition` —(Supabase REST)→ `form_def`·`proc_def`(upsert on id,tenant_id)·`proc_def_version`, `lock` 해제 (vue3:src/components/ai/AIGenerator.js:76; ProcessGPTBackend.ts:467-700 중 503-690)
- (b) 에이전트 생성 →S2: `[frontend ChatRoomPage]` —(SSE `/process-gpt-deepagents/chat/stream`, K8s면 session-router가 대화별 Pod로)→ `[deepagents + bpmn-process-generation-skill]` → 결과(`type:'process-definition-result'`)를 **프런트가** `saveGeneratedProcessArtifacts`로 proc_def·form_def 저장 (ProcessGPTBackend.ts:8484-8500). 생성 중 deepagents가 completion `/complete`·`/regression-*`로 실제 구동 검증(E2).
- (c) PDF→BPMN →S2/S3: 워크아이템 `agent_orch='pdf2bpmn'`(IN_PROGRESS) → KEDA ScaledJob이 todolist COUNT로 워커 기동(k8s:keda/pdf2bpmn-scaledjob.yaml:125-129) → bpmn-extractor(sdk 폴링) → age-postgres·proc_def. 프런트는 `pdf2bpmn-events-{taskId}` Realtime 채널로 진행 표시.
- (d) PAL 모드 `/pi-system-backend/langchain-chat/generate-bpmn/stream` — 대상 서비스 레포 미확인.
- 검증·개선 ✔(경로 의심): `[frontend validateAndImproveDraft]` —(POST `/validate-and-improve`)→ `[completion]` —(자기 자신 `/initiate`·`/complete` 구동 + LLM)→ 개선안 (ProcessGPTBackend.ts:341-362; comp:validate_improve.py:30-36,295). 운영 Spring 게이트웨이에는 `/validate-and-improve` 라우트가 없어 catch-all(frontend)로 떨어질 수 있음 ?.
- 검토·배포 ✔/?: 검토 보드 `proc_def_approval_state`·`proc_def_comments`(vue3 Realtime, 표 정의는 vue3:supabase/migrations/20260130000001_proc_def_comments_approval.sql) → 배포 승인용 BPMN 활동(isDeploy)이 승인으로 끝나면 `[polling]`이 `proc_def.prod_version` 갱신(comp:polling_service/workitem_processor.py:4538-4600, 5004-5011). 스킬·BPMN·DMN 변경 PR은 `resource_pull_requests`(+deepagents `/skills/{name}/pull-requests/*` →S2).

#### ② 처리 건 시작 → 워크아이템 → 에이전트가 집어 처리 → 사람 승인 → 다음 단계 → 종료
```
[사람] frontend ──POST /completion/complete (process_instance_id:"new")──▶ [completion]
[일정] frontend ──RPC register_cron_job──▶ pg_cron ──net.http_post host.docker.internal:8000/initiate──▶ [completion]
[이벤트·타이머] polling ──RPC register_cron_intermidiated──▶ pg_cron ──update_todolist_status──▶ todolist.status=SUBMITTED
        │
        ▼ completion: bpm_proc_inst insert(RUNNING/NEW) + todolist 첫 활동(/initiate→TODO, /complete→SUBMITTED)
        ▼
[polling-service] 5초 폴링: todolist SUBMITTED & consumer NULL → consumer=hostname 점유
        │  proc_def(버전) 로드 → 활동 유형 분기
        │   ├ userTask/scriptTask/manualTask/callActivity → handle_workitem: LLM 완료판정·조건식·역할바인딩
        │   └ serviceTask → MCP(tenants.mcp) / 파이썬 코드 실행
        │  다음 활동 todolist 생성: status(IN_PROGRESS/TODO), agent_mode(DRAFT/COMPLETE/None), agent_orch
        │  finally → memento POST /process-output (→S3)
        ▼
DB 트리거: todolist IN_PROGRESS → notifications insert ──▶ fcm-service(점유) ──▶ Firebase 푸시
                                                       └──▶ frontend Realtime(notifications, todolist)
        ▼ (agent_mode가 있는 IN_PROGRESS 행)
[에이전트 (sdk)] RPC fetch_pending_task(agent_orch) → draft_status=STARTED, lease
        │  컨텍스트: form_def·users·tenants.mcp·proc_inst_source / 진행: events(record_events_bulk) ──Realtime──▶ frontend
        │  산출물 → memento /save-to-storage (→S3)
        ├ COMPLETE: save_task_result(final) → output, status=SUBMITTED ─────────────┐
        ├ DRAFT:    save_task_result(final) → draft, draft_status=COMPLETED          │
        │           → [사람] 초안 확인 후 frontend putWorkItemComplete → /completion/complete → SUBMITTED ┤
        └ 질문:     draft_status=HUMAN_ASKED → [사람] 답 → frontend가 FB_REQUESTED로 → 에이전트 재집기 │
                                                                                     ▼
                                                     [polling] 다시 SUBMITTED를 집어 다음 단계 … endEvent → bpm_proc_inst 완료
서브프로세스: 부모 워크아이템 PENDING → polling handle_pending_workitem이 자식 인스턴스 전부 COMPLETED면 부모 DONE
```
근거: §2 C1, P1-P12, A1-A6, D1-D6; vue3:ProcessGPTBackend.ts:821-900, 3130-3176, 7373-7398; vue3:src/shared/hitlFeedback/index.js:7,122-142; comp:polling_service/workitem_processor.py:5276-5352.
- 확장(K8s) ✔: browser-automation-agent·pdf2bpmn 워커는 KEDA가 todolist COUNT로 띄움(D10).
- ? agent_orch 기본값 불일치: 활동에 orchestration이 없고 COMPLETE면 polling이 `crewai-deep-research`로 채움(comp:polling_service/database.py:1493-1494,1542-1543). 그 값을 집는 워커(crewai-deep-research, →S2)가 떠 있지 않으면 행이 IN_PROGRESS로 남는다. 도커 compose에는 crewai-deep-research 서비스가 없다(infra:docker-compose.yml 서비스 목록).

#### ③ 에이전트 생성·스킬·MCP 설정 → 실행에 반영
- 에이전트 = `users` 행(`is_agent`, `agent_type`, `goal`, 모델·도구 열) ✔ — frontend가 Supabase에 직접 쓴다(`putObject('users')`).
- 스킬: `tenant_skills`(테넌트 목록) ↔ `agent_skills`(에이전트별 연결) ✔ 표; 스킬 파일·버전·PR은 `/process-gpt-deepagents/skills/*` →S2.
- MCP: 테넌트 MCP 설정은 `tenants.mcp`(jsonb) ✔. 실행 시 (i) polling 서비스태스크가 MultiServerMCPClient로 직접 호출(P7), (ii) sdk 에이전트가 컨텍스트로 받아 사용(A7) →S2. K8s에서는 MCP 서버를 `/mcp/configmaps`·`/mcp/secrets`로 mcp-proxy-service가 띄움(F9, G3) →S2. completion `/mcp-tools`는 레포 내 `mcp.json`만 준다(C9) — 테넌트 설정과 별개.
- 에이전트 초기 지식: RPC `agent_needing_knowledge_setup`(goal 있는 에이전트 중 `agent_knowledge_setup_log`에 없는 것, init.sql:3219-3240)과 frontend `/agent-feedback/setup-agent-knowledge`(ProcessGPTBackend.ts:4477) — **호출하는 워커·엔드포인트를 클론들에서 못 찾음 ?**.
- 실행 반영 시점: sdk가 작업을 집을 때마다 users·tenants.mcp·form_def를 새로 읽는다(sdk:processgpt_agent_framework.py:98-125) → 설정 변경은 다음 작업부터 반영 ✔.

#### ④ 실행 기록 → 피드백 → 스킬·규칙 개정
- 작업 단위 피드백 ✔: frontend `saveFeedback`(todolist.temp_feedback) → `/completion/get-feedback`(LLM 개선점)·`/get-feedback-diff`(활동 속성 전후안) → 적용 `applyFeedback` → 재작업 `/get-rework-activities`·`/rework-complete` (ProcessGPTBackend.ts:8105-8144,8351-8380; comp:process_engine.py:575-806, 1043-1046).
- HITL 재실행 ✔: HUMAN_ASKED → 답 → FB_REQUESTED → `fetch_pending_task`가 다시 집음(A1); sdk는 피드백을 LLM으로 요약해 컨텍스트에 넣음(sdk:processgpt_agent_framework.py:200-205 부근 `summarize_feedback`).
- 묶음 개정 →S2/S3: `feedback_proposals`(COLLECTING→PROPOSED, `targets[]`) — 수집·규칙 추출은 agent-feedback. 사람 결정은 frontend `/feedback-proposals/{batch}/targets/{type}/{action}`(ProcessGPTBackend.ts:8838) + RPC `decide_feedback_proposal_target`(init.sql:3470). 승인된 스킬 변경은 agent-feedback→deepagents 스킬 API(`SKILL_API_BASE_URL`, k8s:deployments/agent-feedback.yaml:83-84) → 스킬 PR/커밋 →S2.
- mem0 학습 ✔: `/completion/multi-agent/chat` 학습 모드가 Supabase vecs `memories`에 저장(C4).

#### ⑤ 실행 → 온톨로지 투영 → 전략·KPI·분석 (→S3)
- 그래프 정본 설명: vue3:ontology/INTEGRATION.md:9-24 — Apache AGE 그래프 `process_gpt`(supabase-db 안)에 Strategy·Definition·Organization·Execution·Knowledge 레이어, 원천 표(proc_def·form_def·users·bpm_proc_inst·todolist·tenant_skills·knowledge_files)에서 **파생 projection**, 쓰기는 "outbox 워커·재구축 함수·strategy pull 워커"만(INTEGRATION.md:108).
- `graph_sync_outbox` 표는 vue3:ontology/schema/00-init.sql:72-83에만 정의 — **outbox에 넣는 트리거와 배치 MERGE 워커를 S1 클론들에서 못 찾음 ?** →S3.
- 메타 compose 주석은 "Supabase postgres에는 AGE가 없어 별도 age-postgres를 둔다"(meta:docker-infra/docker-compose.yml:43-46)고 하고, vue3 INTEGRATION.md는 AGE 그래프가 `supabase-db` 안에 있다고 한다(INTEGRATION.md:28-34) — **두 문서가 충돌** →S3 확인.
- 읽기 ✔: frontend RPC `ontology_business_graph`·`ontology_execution_rollup`·`ontology_graph_health`(vue3:supabase/migrations/20260710_ontology_explorer_rpc.sql).
- 전략·KPI·분석 →S3: frontend `/strategy-service/api`(strategy: MEASURE 60초·SURVEY 30초 주기, infra:docker-compose.yml:550-552), `/api/analytics/*`(analytic: ETL 60초, infra:349-350), instance-classifier(POLLING 10초, infra:527). 셋 다 DB를 직접 읽는 주기 작업 → 실행 결과가 들어가는 고리는 "DB 폴링"이다.

#### ⑥ 알림·채팅
- 작업 알림 ✔: todolist→`notifications`(트리거 D1) → (a) frontend Realtime(ProcessGPTBackend.ts:3831) (b) fcm-service 점유 폴링→Firebase(D4) (c) completion이 직접 `/send-notification`(C6).
- 채팅 알림 ✔: chats INSERT→참가자 중 최근 5분 해당 방 미접속자에게 notifications(D3, `user_devices.access_page`).
- 외부 고객 ✔: polling이 SMTP 메일 + 외부 폼 링크(P10).
- 인스턴스 채팅 ✔: frontend `updateInstanceChat`→`chats`(ProcessGPTBackend.ts:3181-3192) ↔ 에이전트 sdk chats upsert(A6) ↔ Realtime 렌더(realtime 컨테이너 없으면 "생각 중"에서 멈춤, meta:.claude/skills/process-gpt-install/references/architecture.md "전체 그림").
- 에이전트 채팅(대화형) →S2: frontend SSE `/process-gpt-deepagents|codex/chat/stream`(+attach/stop/steer, sdk 계약) — K8s는 session-router가 대화별 Pod, 도커는 nginx `/deepagents/chat/stream`→deepagents:8888.

### 5 CONNECTIONS.md(67개)에 없던 새 연결

CONNECTIONS.md는 서브모듈 등록·vite 프록시·README 수준이다. 실제 코드·SQL·매니페스트에서 더 나온 것:

| # | 출발→도착 | 방식 | 근거 | 왜 중요한가 |
|---|---|---|---|---|
| N1 | **polling-service**(completion 레포 안 별도 서비스)→Supabase todolist | 5초 폴링·consumer 점유 | comp:polling_service/database.py:909-1045 | 실행 엔진의 심장인데 목록에 서비스 자체가 없다 |
| N2 | polling→에이전트들(간접) | todolist `agent_mode`·`agent_orch`를 써서 넘김 → sdk `fetch_pending_task`가 집음 → `save_task_result`가 SUBMITTED로 돌려줌 | comp:polling_service/database.py:1538-1662; sdk:function.sql:34-114; meta init.sql:2421-2455 | 엔진↔에이전트는 HTTP가 아니라 **DB 상태 기계**로 이어진다 |
| N3 | polling→memento `/process-output` | HTTP | comp:polling_service/workitem_processor.py:2131 | 실행 산출물 지식화 고리(→S3) |
| N4 | polling→테넌트 MCP 서버 | MCP(MultiServerMCPClient, `tenants.mcp`) | comp:polling_service/mcp_processor.py:63,108 | 서비스태스크가 MCP를 직접 부른다 |
| N5 | polling→pg_cron(`register_cron_intermidiated`) | RPC | comp:polling_service/workitem_processor.py:1901 | 타이머 이벤트 |
| N6 | pg_cron→completion `/initiate` | `net.http_post`(주소 `host.docker.internal:8000` 하드코딩) | meta init.sql:1719-1723 | DB가 서비스를 부르는 유일한 고리 |
| N7 | frontend→pg_cron(`register_cron_job`/`delete_cron_job`/`get_cron_jobs`) | RPC | vue3 ProcessGPTBackend.ts:7392,7429 | 일정 시작 |
| N8 | todolist·chats 트리거→notifications→**fcm-service**→Firebase | 트리거 + 폴링 점유 | init.sql:1037-1168; comp:fcm_service/database.py:322-357 | fcm-service도 목록에 없다 |
| N9 | completion→fcm-service `/send-notification` | HTTP | comp:fcm_client.py:28 | |
| N10 | sdk 에이전트→events(`record_events_bulk`)→frontend Realtime | RPC + Realtime | sdk:database.py:333; ProcessGPTBackend.ts:7500 | 에이전트 진행 표시 경로 |
| N11 | sdk 에이전트→memento `/save-to-storage` | HTTP | sdk:artifacts/store.py:68-69 | CONNECTIONS는 SDK→memento가 없음 |
| N12 | sdk 런너→`agent_sessions` 표·`agent-sessions` 버킷 | Supabase | sdk:session.py:21-39 | Pod 회수 후 대화 복원(session-router 전제) |
| N13 | deepagents→completion `/complete`, `/regression-run`, `/regression-scenarios` | HTTP | process-gpt-deepagents@faedeaa core/bpm/tools.py:531; core/skills/regression_client.py:34; k8s:deployments/process-gpt-deepagents-config.yaml:40 | 에이전트가 엔진을 거꾸로 구동(검증·회귀) |
| N14 | **vue3/gateway(Spring)**가 운영 게이트웨이 | 라우트 30여 개 | vue3:gateway/src/main/resources/application.yml:166-531 | CONNECTIONS의 C04 process-gpt-gateway는 옛 버전(2026-04)이고, vue3 주석도 "gateway application.yml prod 프로파일"을 vue3 쪽으로 가리킨다(vite.config.ts:240-247) |
| N15 | gateway→mcp-proxy-service, frontend→`/mcp/configmaps`·`/mcp/secrets` | HTTP | vue3 gateway yml:177-208; ProcessGPTBackend.ts:7785-7855 | MCP 서버를 K8s 자원으로 띄우는 경로 |
| N16 | gateway→browser-server-N(vnc 6080, api 5001), ingress `/vnc` | HTTP/WS | vue3 gateway yml:345-515; k8s:ingress/gateway-ingress.yaml:48-54 | 브라우저 에이전트 화면 |
| N17 | gateway→analytic `/api/analytics`, agent-feedback `/api/agent-feedback`·`/feedback-proposals`, mcp-validator, litellm | HTTP | vue3 gateway yml:212-341 | |
| N18 | session-router→K8s API·PodTemplate `agent-runner-{codex,deepagents}`·fallback `*-shared` | K8s API + HTTP | k8s:deployments/session-router.yaml:83-155; agent-runner-templates.yaml:19,135 | CONNECTIONS는 "선택 라우팅"만 적음 |
| N19 | KEDA→todolist COUNT(browser-automation-agent, pdf2bpmn) | Postgres 직접 질의 | k8s:keda/keda-scaled-objects.yaml:21-29; pdf2bpmn-scaledjob.yaml:125-129 | 큐 길이로 워커 확장 |
| N20 | completion→Supabase Auth admin API | HTTP | comp:process_db_manager.py:114,255 | |
| N21 | completion→Supabase vecs `memories`(mem0) | pgvector | comp:mem0_agent_client.py:113-133 | |
| N22 | completion→외부 A2A 에이전트 `/.well-known/agent.json` | HTTP | comp:agent_chat.py:58 | |
| N23 | completion→자기 자신(검증 엔진) | HTTP | comp:validate_improve.py:30-36 | |
| N24 | polling→SMTP·Upstage·**ngrok Twilio 하드코딩** | SMTP/HTTP | comp:polling_service/workitem_processor.py:693; document_parser.py:25; database.py:1704-1726 | 마지막 것은 테스트 코드가 운영 경로에 남음 |
| N25 | process-gpt-gateway→Supabase RPC `get_credit_balance` | HTTP | gw:CreditValidationFilter.java:62 | RPC 정의 없음 |
| N26 | frontend→ontology RPC 3종 | RPC | vue3:supabase/migrations/20260710_ontology_explorer_rpc.sql | →S3 |
| N27 | agent-feedback→claude-skills MCP·computer-use MCP | 설정 | k8s:deployments/agent-feedback.yaml:85-94 | →S2/S3 |
| N28 | deepagents→redis·claude-skills | 설정 | k8s:deployments/process-gpt-deepagents-config.yaml:33-34 | →S2 |
| N29 | crewai-deep-research→memento | 설정 | k8s:deployments/crewai-deep-research-deployment.yaml:90-91 | →S2 |
| N30 | completion CI→k8s 레포(이미지 태그 yq 갱신, GitOps) | CI | comp:.github/workflows/deploy-prod.yaml:176-192 | polling·completion 이미지가 같은 커밋 태그(b272c9a)로 배포됨(k8s:deployments/polling-service-deployment.yaml:99, completion-deployment.yaml:99) |
| N31 | frontend→PAL `/pi-system-backend`, uEngine 모드 `/definition`·`/instance`·`/work-item`… | HTTP | vue3:src/services/bpmnGenerationService.ts:22; vite.config.ts:178-183,265-325 | 백엔드가 모드별로 바뀐다(BackendFactory) |

### 6 미확인·끊긴 고리

| # | 내용 | 근거 | 영향 |
|---|---|---|---|
| U1 | 운영 gateway 이미지 `process-gpt-gateway:0f61d8a`의 소스 커밋을 못 찾음(process-gpt-gateway main=2567edc). vue3/gateway가 정본인지, 별도 레포인지 미확인 | k8s:deployments/gateway.yaml:34 | 운영 라우트 표를 vue3 yml로 추정 |
| U2 | `get_credit_balance` RPC 정의 없음(meta·infra init.sql) | gw:CreditValidationFilter.java:62 | 옛 게이트웨이 크레딧 검사는 현재 스키마와 안 맞음 |
| U3 | frontend `/completion/insert-sample` — completion에 라우트 없음 | ProcessGPTBackend.ts:5685 | 호출 시 404 예상 |
| U4 | frontend `/agent-feedback/setup-agent-knowledge` — 게이트웨이는 `/api/agent-feedback/**`만 라우팅, vite에도 프록시 없음; RPC `agent_needing_knowledge_setup` 사용처 못 찾음 | ProcessGPTBackend.ts:4477; vue3 gateway yml:323-341; init.sql:3219 | 에이전트 초기 지식 셋업 고리 끊김 의심 |
| U5 | frontend `/validate-and-improve`(접두 없음) — vite는 completion(8099)으로, 운영 Spring 게이트웨이·nginx에는 라우트 없음 | ProcessGPTBackend.ts:351-352; vite.config.ts:143-146 | 배포 환경에서 SPA로 떨어질 수 있음 |
| U6 | 도커 nginx에는 `/process-gpt-deepagents/`·`/process-gpt-codex/`·`/feedback-proposals`·`/api/analytics`·`/mcp-validator/`·`/claude-skills/`·`/mcp/` 라우트가 없다(있는 것은 `/deepagents/`). frontend는 `/process-gpt-deepagents` 고정 접두를 쓴다 | infra:nginx/nginx.conf; vue3:src/services/DeepAgentRouterService.js:10 | 도커 설치에서 스킬·피드백·분석 화면 호출이 SPA로 떨어질 가능성. 실제 동작 미검증(환경 없음) |
| U7 | `graph_sync_outbox`에 넣는 트리거·MERGE 워커, strategy pull 워커를 S1 클론에서 못 찾음 | vue3:ontology/schema/00-init.sql:72-83; INTEGRATION.md:108 | →S3 |
| U8 | AGE 그래프 위치 충돌: meta compose "supabase엔 AGE 없음→age-postgres" vs vue3 INTEGRATION "supabase-db 안 `process_gpt` 그래프" | meta:docker-infra/docker-compose.yml:43-46; vue3:ontology/INTEGRATION.md:28-34 | →S3 |
| U9 | 스키마 원천이 셋으로 갈림: meta init.sql, infra init.sql(이벤트 enum 10종·lease RPC 있음), vue3 supabase/migrations(proc_def_approval_state·tb_bpmn_*·systems·kpi_* 등 50여 표), sdk function.sql/database_schema.sql(agent_sessions). meta init.sql에는 sdk가 부르는 6인자 `fetch_pending_task`·`renew_task_lease`·`release_task_lease`가 없다 | meta init.sql:2679-2723(4인자); infra:volumes/db/init.sql(lease 있음); sdk:function.sql:34-114 | meta 기준으로 DB를 만들면 최신 sdk 에이전트가 작업을 못 집는다(RPC 시그니처 불일치) |
| U10 | `mcp_python_code` 표 CREATE 없음(openspec e2e seed에만) | comp:polling_service/workitem_processor.py:1677 계열; meta/openspec/specs/*/seed.sql | 결정적 실행 경로 신선 설치 시 실패 가능 |
| U11 | pg_cron 일정 시작 주소 `http://host.docker.internal:8000/initiate` 하드코딩 — K8s(매니지드 Supabase)에서 이 주소가 닿는지 미확인 | init.sql:1719-1721 | 운영에서 일정 시작이 안 될 수 있음 |
| U12 | `agent_orch` 기본값 `crewai-deep-research`를 집는 워커가 도커 compose에 없음 | comp:polling_service/database.py:1493-1494; infra compose 서비스 목록 | 오케스트레이션 미지정 COMPLETE 작업이 IN_PROGRESS로 남을 수 있음 |
| U13 | polling `COMPLETION_SERVICE_URL` 설정은 있으나 polling 코드에서 사용처 없음 | infra:docker-compose.yml:110; k8s polling-service-deployment.yaml:60-61 | 설정만 있는 연결 |
| U14 | agent-router 이미지(`ghcr.io/uengine-oss/agent-router`)·agent-runtime-template 소스 레포 미확인; nginx는 `/agent-router/route`를 503으로 막음 | infra:docker-compose.yml:214-222; nginx.conf:34-36 | 도커에선 사실상 비활성 |
| U15 | `/pi-system-backend`(PAL 모드) 백엔드 레포, uEngine(Java) 백엔드 레포 | vue3:vite.config.ts:178-183,265-325 | S1 범위 밖, 미확인 |
| U16 | 실제 실행 검증 없음 — 이 문서는 코드·SQL·매니페스트 정적 읽기만. 런타임 활성 여부는 모두 미검증 | — | — |

### 결론 한 줄
ProcessGPT 핵심 플랫폼의 서비스 간 결합은 HTTP보다 **Supabase 표 `todolist`의 상태 기계**(completion/pg_cron이 넣고 → polling이 SUBMITTED를 집어 다음 활동을 IN_PROGRESS+agent_orch로 쓰고 → sdk 에이전트가 RPC로 집어 결과를 SUBMITTED로 되돌림)와 **Realtime·트리거**(notifications·events·chats)로 이뤄진다. HTTP는 frontend→게이트웨이→completion/memento/deepagents 쪽과 polling→memento·MCP, deepagents→completion 정도다.

## 부록 B — S2 에이전트·도구·학습

조사일 2026-10-08. 클론 위치 `/tmp/claude-0/refs/<repo>`(기존 클론 사용, 22개 모두 있음). 근거 표기는 `레포@커밋 파일:줄`이다. 같은 레포 안에서는 레포명을 줄였다.
경계: S1(process-gpt-vue3·completion·agent-sdk·gateway), S3(strategy·bpmn-extractor·robo·온톨로지)로 넘어가는 호출은 "→S1/S3 서비스명"으로 끝냈다. SDK(S1)의 동작은 흐름을 닫는 데 필요한 만큼만 확인했다(process-gpt-agent-sdk@4d8f3b6).

### 0. 결론 먼저

1. **실행체는 모두 Supabase `todolist`를 폴링하는 워커다.** HTTP로 일을 넘기지 않는다. completion(S1)이 액티비티의 `orchestration` 값을 `todolist.agent_orch`에 쓰고(process-gpt-completion@b272c9a polling_service/database.py:1223-1262), 실행체는 자기 agent_orch 값으로 RPC를 불러 lease를 잡는다. SDK 계열은 `fetch_pending_task`, 구형 실행체는 `openai_deep_*`·`deep_research_*`·`crewai_deep_*` 같은 자체 RPC를 쓴다.
2. **에이전트 정의 = `users` 행(is_agent).** vue3(S1)가 저장하고(ProcessGPTBackend.ts:4250-4287), SDK가 `todolist.user_id`로 그 행을 읽어 `extras.agents`에 싣는다(agent-sdk processgpt_agent_framework.py:110-216). 실행체마다 해석이 다르다. deepagents는 루트 프로필과 서브에이전트로 쓰고, a2a는 `endpoint`, crewai는 CrewAI Agent, cli-agent는 CLI 서브에이전트, base-agent는 is_agent 첫 행으로 쓴다.
3. **MCP 설정 = `tenants.mcp`(mcpServers JSON) 하나다.** vue3가 쓰고(ProcessGPTBackend.ts:7257-7260), mcp-validator는 검사만 한다(DB 없음). 실행체마다 붙이는 범위가 다르다. cli-agent는 **stdio 서버만** 붙이고(http 서버는 버림), codex는 **전혀 안 쓴다**. deepagents는 process-gpt-mcp를 자동으로 끼워 넣는다.
4. **스킬 저장소가 둘로 갈라져 있다.**
   - (A) deepagents의 `/skills` API: 디스크 `{SKILLS_DIRS}/{tenant}/…`에 두고, `tenant_skills` 표, 테넌트 Git(`tenant_git_config`)·PR·평가표(`resource_eval_*`)를 함께 쓴다. deepagents와 cli-agent가 디스크에서 읽는다.
   - (B) process-gpt-claude-skills 서비스: PVC 파일과 MCP 도구로 운영한다. base-agent는 HTTP로, crewai-action은 MCP로 읽는다.
   - 둘을 동기화하는 코드는 찾지 못했다.
   - 에이전트별 할당은 `users.skills`(콤마 문자열)에 있다.
5. **학습 고리는 agent-feedback 한 곳에서 닫힌다.**
   - 흐름: `todolist.feedback` → 7초 수집 → `feedback_proposals` 배치 → 900초마다 LLM 분류 → strategy 정렬 검사(→S3) → 사람 승인 → 반영.
   - SKILL 개정은 **deepagents `/skills/{name}/commit`로 브랜치와 PR**을 만든다.
   - DMN·BPMN 개정은 **draft `proc_def_version`과 `resource_pull_requests`**만 만들고, 라이브 반영은 vue3(S1) 몫이다.
   - 에이전트 프로필(role·goal·persona)을 고치는 target은 없다.
6. **memento는 문서 지식의 단일 창구다.** 다만 주소가 제각각이다: `MEMENTO_BASE_URL`(deepagents·codex·base-agent), `MEMENTO_SERVICE_URL`(office-mcp·deep-research·crewai-dr·completion), agent-utils는 외부 `https://memento.process-gpt.io/api/retrieve` 하드코딩. 실행체마다 쓰는 엔드포인트도 다르다(/search·/catalog… vs /retrieve).

### 1. 서비스 표

| ID | 서비스@커밋 | 한 줄 역할 | 포트·주소 환경변수 | 일 받는 방식(agent_orch) | 들어오는 호출 |
|---|---|---|---|---|---|
| A01 | process-gpt-deepagents@faedeaa | LangGraph deepagents 실행체 겸 스킬 생성·평가·PR 서버 | PORT=8888, DEEPAGENTS_PROCESS_POLLING, SKILLS_DIRS, SKILLS_HOST, SKILL_REPO_URLS, MEMENTO_BASE_URL(127.0.0.1:8005), COMPLETION_SERVICE_URL(localhost:8000), PROCESS_GPT_OFFICE_MCP_URL(localhost:1192/mcp/), STRATEGY_SERVICE_URL, DB_*(체크포인트), REDIS_URL, GITHUB/GITLAB/GITEA_* | SDK `deepagents` + /chat/stream | vue3(채팅·/skills/*·PR 검증·merge), agent-feedback(/skills/upload·commit·files) |
| A02 | process-gpt-base-agent-langchain-react@e566a60 (+process-gpt-mcp) | ReAct "Work Assistant" | PORT=8008, MCP_CONFIG_PATH, CLAUDE_SKILLS_BASE_URL(http://claude-skills:8000), MEMENTO_BASE_URL(http://memento:8005) | SDK `langchain-react` + /chat/stream | vue3 /agent/(CONNECTIONS) |
| A03 | process-gpt-a2a-orch@ad5e937 | 외부 A2A 에이전트 중계 + 웹훅 수신기 | WEBHOOK_RECEIVER_PORT=9000, WEBHOOK_PUBLIC_BASE_URL | SDK `a2a` | 외부 A2A 에이전트 → POST /webhook/a2a/todolist/{id} |
| A04 | process-gpt-codex@cede40e | Codex app-server 대화별 실행체 | PORT=8891, CODEX_PROCESS_POLLING, MEMENTO_BASE_URL, CODEX_PROVIDER_* | SDK `codex` + /chat/stream·/chat·/route | vue3·session-router(CONNECTIONS) |
| A05 | process-gpt-cli-agent@0a0e3d3 | Claude Code·Codex CLI 실행체 | PORT=8890, CLIAGENTS_DEFAULT_CLI(claude-code), CLIAGENTS_MAX_CONCURRENT_RUNS=3, SKILLS_DIRS, CLIAGENTS_SYSTEM_SKILLS_DIR | SDK `cliagents` + /chat/stream | vue3(/agents·/skills·/runs/*) |
| A06 | cliagents@7c7a392 | CLI별 파일 규약 추상화 라이브러리(무의존) | — | — | cli-agent가 import |
| A07 | process-gpt-openai-deep-research@49ddcd9 | OpenAI Responses deep research 보고서 | PORT=8000 | 자체 RPC `openai_deep_fetch_pending_task(_dev)` / `openai-deep-research` | — |
| A08 | process-gpt-deep-research@8a343e2 | Tavily+memento 리서치 → HWPX/DOCX/슬라이드 | MEMENTO_SERVICE_URL(memento-service:8005), PROCESS_GPT_OFFICE_MCP_URL(process-gpt-office-mcp-service:1192/mcp), POLLING_TENANT_ID | 자체 RPC `deep_research_fetch_pending_task(_dev)` / `deep-research-custom` | /api/chat·/api/report/*(자체 화면) |
| A09 | process-gpt-react-voice-agent@999ca2b | OpenAI Realtime 음성 조회 에이전트 | 3000, WS /ws·/ws/realtime | 폴링 없음 | 브라우저 WebSocket |
| T01 | process-gpt-memento@659ab9f | 문서 인제스천·RAG·문서 탐색 | 8005, VECTOR_BACKEND(chroma/qdrant), ROBO_GLOSSARY_API_BASE_URL | — | 실행체 대부분, vue3, completion, SDK artifacts |
| T03 | process-gpt-office-mcp@7e95c6e | HWPX·DOCX·슬라이드 생성 MCP | 1192 /mcp, MEMENTO_SERVICE_URL | — | deepagents(JSON-RPC 직접), deep-research(FastMCP), base-agent(mcp_config) |
| T04 | process-gpt-mcp-validator@cf220bf | MCP 설정 연결 검사(무상태) | 8800 | — | vue3(CONNECTIONS) |
| T07 | process-gpt-claude-skills@456d56f | 스킬 파일 저장소 + 스킬 검색 MCP | 8765, SKILLS_STORAGE_PATH(PVC) | — | base-agent(HTTP), crewai-action(MCP via tenants.mcp), vue3 |
| T08 | process-gpt-computer-use@174adf6 | 세션별 K8s Pod 셸 MCP | 8888(run_server) / 8000(k8s svc) | — | tenants.mcp 등록 시 crewai-action 등 |
| P04 | process-gpt-agent-feedback@84d2a0e | 피드백 → 개정안 → 승인 → 반영 | PORT=6789, SKILL_API_BASE_URL(localhost:8888), STRATEGY_SERVICE_URL(localhost:8014), FEEDBACK_BATCH_TRIGGER_INTERVAL=900 | 자체 RPC `agent_feedback_task` | vue3 /feedback-proposals·/api/skills/{s}/contributors |
| X03 | process-gpt-crewai-action@ecdf8de | CrewAI 동적 크루 실행체 | 헬스 8000 | SDK `crewai-action` | — |
| X04 | process-gpt-crewai-deep-research@49e2b12 | CrewAI 보고서·폼·슬라이드 | 8000, MEMENTO_SERVICE_URL | 자체 RPC `crewai_deep_fetch_pending_task(_dev)` | — |
| X05 | process-gpt-langchain-react@16e1f38 | 구형 ReAct(구 SDK) | 8000, PGPT_WORK_DIR | 구 SDK `langchain-react`(A02와 같은 값) | — |
| X06 | process-gpt-browser-use@6aeaa42 | browser-use 브라우저 자동화 | AGENT_ORCH, STORAGE_BUCKET=browser_use | SDK `browser-automation-agent` | — |
| X07 | process-gpt-agent-utils@5dbd7e0 | CrewAI용 공통 도구(mem0·memento·human_asked·dmn_rule·A2A) | DB_*(vecs 직접), A2A_{KEY}_URL | 라이브러리 | crewai-action |
| X08 | process-gpt-llm-factory@a32e57e | LLM 공급자 팩토리 | LLM_PROVIDER 등 | 라이브러리 | a2a-orch·agent-utils·agent-feedback·crewai-action·crewai-dr |
| D04 | process-gpt-agents.github.io@cdc78f0 | 소개·마켓플레이스 정적 사이트 | — | — | 런타임 상호작용 없음(formspree만) |

### 2. 연결 목록 (출발 → 도착, 방식, 근거)

방식 약어: **RPC/표**=Supabase PostgREST(RPC·테이블 읽기R/쓰기W), **HTTP**=REST, **MCP-stdio/MCP-http**, **A2A**, **SSE/WS**, **디스크**=공유 파일시스템.

#### 2.1 일 받기(폴링)와 실행 결과
| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| L01 | completion(S1) → todolist.agent_orch | 표W: 액티비티 `orchestration` 값으로 워크아이템 생성 | process-gpt-completion@b272c9a polling_service/database.py:1223-1262 |
| L02 | deepagents·base-agent·codex·cli-agent·a2a-orch·crewai-action·browser-use → todolist | RPC `fetch_pending_task(p_agent_orch, p_consumer, p_lease_seconds…)` (SDK) | agent-sdk@4d8f3b6 database.py:133-187; deepagents server.py:63-69,98; base-agent server.py:47,58; codex app/main.py:27,82,109; cli-agent server.py:86, core/settings.py:19; a2a-orch src/a2a_agent_executor/server.py:137-139; crewai-action crewai_action_server.py:27; browser-use processgpt_browser_server.py:49,140-142 |
| L03 | SDK → users·tenants.mcp·form_def·proc_inst_source | 표R: todolist.user_id의 users 행을 `extras.agents`, tenants.mcp를 `extras.tenant_mcp`에 실음 | agent-sdk processgpt_agent_framework.py:110-216, database.py:630-760 |
| L04 | 모든 SDK 실행체 → events, todolist | RPC `record_events_bulk`, `save_task_result`; HITL 시 todolist.draft_status=HUMAN_ASKED | agent-sdk database.py:333,401,496-527; event_queue_process.py:22-27 |
| L05 | openai-deep-research → todolist·events·users·form_def | RPC `openai_deep_fetch_pending_task(_dev)`·`fetch_done_data`·`save_task_result`, events insert | openai-deep-research@49ddcd9 core/database.py:60-77,121,185-195,283; function.sql:50; utils/event_logger.py:52 |
| L06 | deep-research → todolist·proc_inst_source·events·users | RPC `deep_research_fetch_pending_task(_dev)` p_agent_orch=`deep-research-custom` | deep-research@8a343e2 src/db.py:26-48,102,197,217-243; function.sql:4-53 |
| L07 | crewai-deep-research → todolist·tenants.mcp·users | RPC `crewai_deep_fetch_pending_task(_dev)`·`fetch_done_data`·`save_task_result` | crewai-deep-research@49e2b12 core/database.py:199-275,307-314; function.sql:51,155 |
| L08 | langchain-react(구형) → todolist | 구 SDK agent_orch=`langchain-react`(**A02와 같은 큐**) | process-gpt-langchain-react@16e1f38 langchain_react/server.py:309-312 |
| L09 | browser-use(SDK 경유) → env 표 | 표R key='browser_use' → sensitive_data | agent-sdk database.py:190-197 |

#### 2.2 에이전트 정의·배정
| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| L10 | vue3(S1) → users | 표W putAgent: role·goal·persona·endpoint·tools·skills(콤마)·model·agent_type·alias, is_agent | process-gpt-vue3@a4f0a85 src/components/api/ProcessGPTBackend.ts:4250-4287 |
| L11 | deepagents(프로세스 생성 스킬) → 샌드박스 `agents/<id>.json` → vue3 저장 | 디스크·SSE 산출물. 스킬은 DB에 직접 쓰지 않음 | deepagents system-skills/process-gpt-system/bpmn-process-generation-skill/references/05-agents.md:1-40; scripts/save_to_supabase.py:1-12 |
| L12 | deepagents → proc_def.definition | 표R: 액티비티 tools·skills·rootAgent, 서브프로세스 에이전트 | deepagents core/chat/activity.py:11-27,77-147,260-310; executor.py:1240-1270,1696-1765 |
| L13 | a2a-orch → 외부 A2A 에이전트(users.endpoint) | A2A: AgentCard 조회 → push 지원이면 웹훅, 아니면 동기 send_message | a2a-orch src/a2a_agent_executor/executor.py:121-211,290-334,476-488 |
| L14 | 외부 A2A 에이전트 → a2a webhook receiver | HTTP POST /webhook/a2a/todolist/{id} | a2a-orch src/a2a_agent_webhook_receiver/server.py:52,155 |
| L15 | a2a webhook receiver → events·todolist | SDK ProcessGPTEventQueue, events 조회 | a2a-orch src/a2a_agent_webhook_receiver/processor.py:9,101-145; database.py:44,92 |
| L16 | cli-agent → proc_def | 표R: 액티비티 agent_config(agent_cli) | cli-agent core/activity.py:107; core/selection.py:30,86-127 |

#### 2.3 MCP
| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| L17 | vue3(S1) → tenants.mcp | 표W setMCPByTenant | process-gpt-vue3 ProcessGPTBackend.ts:7233,7257-7260 |
| L18 | vue3 → mcp-validator | HTTP POST /validate·/validate-server(DB 없음) | mcp-validator@cf220bf src/mcp_validator/api.py:85-160 (호출 근거는 CONNECTIONS) |
| L19 | deepagents → tenants.mcp 서버들 | 표R 후 MultiServerMCPClient(stdio·streamable_http·sse·websocket), users.tools·액티비티 tools·tool_filters로 고름 | deepagents executor.py:1357-1376; core/llm/mcp.py:15-100; core/agents/agent.py:298-325 |
| L20 | deepagents → process-gpt-mcp | MCP-stdio `uvx process-gpt-mcp` 자동 주입. pdf2bpmn·컨설팅 워크아이템 도구는 막음 | deepagents core/llm/mcp.py:11-14,103-136 |
| L21 | base-agent → process-gpt-mcp, office-mcp | MCP-stdio `process-gpt-mcp`, MCP-http http://process-gpt-office-mcp-service:1192/mcp | base-agent mcp_config.json:3-10; runtime.py:32 |
| L22 | base-agent → tenants.mcp | 표R | base-agent src/work_assistant_agent/database.py:444-462; executor.py:854-860 |
| L23 | cli-agent → tenants.mcp(stdio만) → CLI | `.mcp.json`(Claude Code) / `$CODEX_HOME/config.toml`(Codex) | cli-agent core/bridge.py:134-160; executor.py:138-146; cliagents providers/claude_code.py:62,158, providers/codex.py:8 |
| L24 | crewai-action → tenants.mcp(extras) | agent-utils SafeToolLoader(stdio) | crewai-action crewai_action_executor.py:281; crew_factory.py:348-349; agent-utils tools/safe_tool_loader.py:150-210 |
| L25 | codex → 내부 `processgpt_knowledge` MCP | MCP-stdio(config.toml에 씀). tenants.mcp 미사용 | codex app/config.py:592-602 |
| L26 | process-gpt-mcp → Supabase | HTTP REST users·proc_def·form_def·bpm_proc_inst·todolist·configuration | base-agent process-gpt-mcp/src/process_gpt_mcp/server.py:1019-2103 |
| L27 | process-gpt-mcp → todolist(agent_orch=`pdf2bpmn`) | 표W 워크아이템 생성 → S3/S1 bpmn-extractor 폴링 | process-gpt-mcp server.py:1156-1178,2014-2051 |
| L28 | process-gpt-mcp → gateway→completion | HTTP POST https://{tenant}.process-gpt.io/completion/complete (PROCESS_GPT_API_BASE_URL로 바꿀 수 있음) →S1 | process-gpt-mcp server.py:90-100,1513 |

#### 2.4 스킬
| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| L29 | deepagents → 디스크 {SKILLS_DIRS}/{tenant}/{provider_config_id 또는 local}/ | 디스크R/W, 샌드박스에 /skills 마운트 | deepagents core/skills/skills.py:46-108; core/agents/agent.py:38-39,275,432-452 |
| L30 | deepagents → tenant_skills | 표W(publish·register·upload 시) | deepagents core/api/skills_router.py:310-331; core/skills/tools.py:644-716,3162-3250 |
| L31 | deepagents → tenant_git_config + GitHub/GitLab/Gitea | 표R, Git API(레포·브랜치·커밋·PR) | deepagents core/skills/git_providers/factory.py:18-56; git_providers/{github,gitlab,gitea}.py |
| L32 | deepagents → github.com/anthropics/skills | git prefetch(SKILL_REPO_URLS) | deepagents core/skills/git_skill_fetcher.py:44,92,141 |
| L33 | deepagents → resource_pull_requests, resource_eval_suites/cases/runs/results | 표W(스킬 PR·평가 회차) | deepagents core/api/skills_router.py:397,721; core/skills/eval_tools.py:621-889; core/skills/pr_verification.py:458-866 |
| L34 | deepagents → completion | HTTP POST /regression-run(DMN·BPMN 회귀 재생) →S1 | deepagents core/skills/regression_client.py:21,34-50,92 |
| L35 | vue3 → deepagents | HTTP /process-gpt-deepagents/skills/{n}/pull-requests/{pr}/verification·files·merge | process-gpt-vue3 ProcessGPTBackend.ts:8995-9241 |
| L36 | cli-agent → 디스크 {SKILLS_DIRS}/{tenant}·/local + 번들 + git_skills | 디스크R → `.claude/skills`·`.agents/skills`에 배치 | cli-agent core/skills.py:137-160; executor.py:147-170,593-600; cliagents providers/claude_code.py:51-55, codex.py:47-49 |
| L37 | base-agent → claude-skills | HTTP GET /skills/{name}/files/SKILL.md·mcp_config.json?tenant_id= | base-agent src/work_assistant_agent/agent.py:2250-2352,2566 |
| L38 | crewai-action → claude-skills·computer-use | MCP(tenants.mcp에 `claude-skills`·`computer-use` 이름으로 등록 가정), users.skills로 우선순위 | crewai-action crew_factory.py:14-31,59-90 |
| L39 | codex → managed_skills(레포 내장) | 디스크 복사(CODEX_HOME/skills) | codex app/config.py:19,471-473 |

#### 2.5 지식·메모리(memento·mem0)
| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| L40 | deepagents → memento | HTTP GET /search·/catalog·/document/grep·/document/page·/summarize·/documents/full-text | deepagents core/rag/memento.py:1-9,22,87,178,236,281,329 |
| L41 | codex → memento | HTTP GET 15종(/catalog·/folders/*·/document/*·/sections/search·/glossary/terms…) + POST /process-session-file | codex app/knowledge/memento.py:43-185 |
| L42 | base-agent → memento | HTTP POST /save-to-storage(도구 결과 저장), GET /retrieve(room_id, 모든 LLM 호출 앞) | base-agent memory.py:36-45,101-103,218-223 |
| L43 | office-mcp → memento | HTTP GET /retrieve | office-mcp office_mcp/memento.py:85,147; config.py:51 |
| L44 | deep-research → memento | HTTP GET /retrieve·/documents/chunks-metadata·/documents/list, POST /retrieve-by-indices | deep-research src/services/memento.py:56-166 |
| L45 | crewai-deep-research → memento | HTTP /retrieve | crewai-deep-research tools/knowledge_manager.py:32,193 |
| L46 | agent-utils(crewai-action) → memento **외부 운영 주소** | HTTP GET https://memento.process-gpt.io/api/retrieve | agent-utils tools/knowledge_manager.py:269-271 |
| L47 | agent-utils·crewai-dr → Postgres vecs `memories`(mem0) | DB 직접(DB_*), search만 | agent-utils tools/knowledge_manager.py:21-25,162-198; crewai-dr tools/knowledge_manager.py:98,114 |
| L48 | completion(S1) → memento | HTTP POST /process-output(폼 산출물 → 문서, todolist.output_url W) | process-gpt-completion polling_service/workitem_processor.py:2125-2131; memento app/api/ingest.py:253-324 |
| L49 | agent-sdk 산출물(S1) → memento | HTTP POST /save-to-storage | agent-sdk artifacts/store.py:89-97 |
| L50 | memento → robo glossary | HTTP GET {ROBO_GLOSSARY_API_BASE_URL}/glossary/terms/search →S3 robo | memento app/services/glossary.py:10-32 |

#### 2.6 문서 생성·HITL·기타 도구
| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| L51 | deepagents → office-mcp | MCP 클라이언트 없이 JSON-RPC tools/call `store_and_render_hwpx` | deepagents executor.py:171-215,230-290,462-505 |
| L52 | deep-research → office-mcp | FastMCP call_tool generate_hwpx·generate_docx·generate_slides(slides는 IMAGE_GENERATION_ENABLED일 때만 있음) | deep-research src/services/mcp_client.py:40,113,145; office-mcp mcp_server.py:1097-1110 |
| L53 | office-mcp·codex·computer-use → Supabase Storage `files` | Storage 업로드 | office-mcp mcp_server.py:232-240; codex app/workspace/folder_store.py:21,80-143; computer-use src/mcp_server.py:32-41 |
| L54 | computer-use → Kubernetes API | Pod 생성·exec | computer-use src/pod_manager.py; src/mcp_server.py:90-121 |
| L55 | deepagents → completion | HTTP POST /complete(채팅에서만 execute_process) →S1 | deepagents core/bpm/tools.py:46,473-531; agent.py:247-250 |
| L56 | deepagents → Postgres 체크포인트 | LangGraph AsyncPostgresSaver(DB_*) — HITL 재개 | deepagents core/storage/checkpointer.py:96-150; server.py:55 |
| L57 | deepagents → mcp_python_code·todolist·events | 결정적 재실행(먼저 확인) | deepagents core/deterministic/replay.py:176,404-420,830-845; executor.py:1477-1480 |
| L58 | agent-utils → mcp_python_code | 표R/W upsert | agent-utils utils/database.py:289-321; tools/deterministic_code_tool.py:620,745 |
| L59 | agent-utils → events·notifications | human_asked 기록 + 알림(url=/todolist/{id}) 후 events 폴링 | agent-utils tools/human_query_tool.py:126-241; utils/database.py:180-250 |
| L60 | agent-utils → proc_def(type='dmn', owner=user_id) | 표R → DMN XML 파싱 → LLM 판정 | agent-utils tools/dmn_rule_tool.py:83-160 |
| L61 | agent-utils → 외부 A2A(A2A_{KEY}_URL) | A2A 도구 | agent-utils tools/safe_tool_loader.py:132-135,533-536; tools/a2a_client_tool.py:112-247 |
| L62 | deepagents → strategy | HTTP /api/objectives·/api/kpis·/api/map·/api/canvas — **도구 부착 주석 처리로 비활성** | deepagents core/strategy/tools.py:23-481; core/agents/agent.py:265 |
| L63 | react-voice-agent → Supabase·OpenAI Realtime | 표R proc_def·proc_def_arcv·form_def·bpm_proc_inst·todolist·configuration·chats·users / WSS | react-voice-agent server/database.py:62-635; langchain_openai_voice/__init__.py:18-19 |
| L64 | langchain-react → mcp-python-code-interpreter | MCP-stdio `uvx` 고정 | process-gpt-langchain-react langchain_react/server.py:133-142 |

#### 2.7 피드백·학습
| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| L65 | agent-feedback → todolist | RPC `agent_feedback_task`(DONE + feedback, 7초 주기), feedback_collected_count W | agent-feedback core/database.py:38-50,161-169; core/feedback_batch_manager.py:122-200 |
| L66 | agent-feedback → feedback_proposals | RPC `append_workitem_feedback_to_batch`, 상태 COLLECTING→CLASSIFYING→PROPOSED/DISCARDED | agent-feedback core/database.py:391-575 |
| L67 | agent-feedback → strategy | HTTP POST /api/ai/alignment →S3 process-gpt-strategy | agent-feedback core/feedback_batch_manager.py:83-104 |
| L68 | vue3 → agent-feedback | HTTP GET /feedback-proposals·/my-feedback, POST /{id}/targets/{type}/approve·reject → RPC `decide_feedback_proposal_target(_at)` | agent-feedback core/feedback_proposal_routes.py:50,100-450; core/database.py:608-651 |
| L69 | agent-feedback → deepagents | HTTP POST /skills/upload·/skills/{n}/commit(브랜치·PR), GET /skills·/skills/{n}/files | agent-feedback core/skill_api_client.py:25,195,212-274,308,366,450 |
| L70 | agent-feedback → users.skills·tenants.skills·agent_skills·skill_contributions | 표W | agent-feedback core/database.py:224-352; core/learning_committers/skill_committer.py:33,68 |
| L71 | agent-feedback → proc_def_version(draft)·resource_pull_requests | 표W DMN·BPMN 병합 요청(라이브 proc_def 불변) | agent-feedback core/feedback_batch_manager.py:653-730,798-870; core/database.py:1299,1346,1521 |
| L72 | vue3 → resource_pull_requests·resource_pr_reviews | 표W 범용 리소스 PR 워크플로 →S1 | process-gpt-vue3 ProcessGPTBackend.ts:9339-9382 |

### 3. 공유 표·저장소 (누가 쓰고 누가 읽나)

| 공유 자원 | 쓰는 쪽 | 읽는 쪽 | 근거(대표) |
|---|---|---|---|
| `todolist` | completion(생성·agent_orch, S1), SDK(save_task_result·draft_status·lease), process-gpt-mcp(pdf2bpmn 워크아이템), agent-feedback(feedback_collected_count), memento(output_url), 화면(feedback·FB_REQUESTED, S1) | 모든 폴러(RPC), codex(이전 단계 output), deepagents(자식 액티비티·재실행), agent-feedback, a2a webhook, voice | L01-L08, L27, L48, L65 |
| `events` | SDK record_events_bulk(SDK 실행체 전부), agent-utils human_asked, openai-dr·deep-research·crewai-dr(직접 insert), a2a webhook | agent-utils(답 폴링), agent-feedback, a2a webhook(job_id 재사용), deepagents 재실행, vue3(S1) | L04, L15, L59 |
| `users`(is_agent) | vue3 putAgent(S1), agent-feedback(skills 콤마 문자열) | SDK→extras.agents, openai-dr·deep-research·crewai-dr(직접), process-gpt-mcp, deepagents bpm 도구, voice, agent-feedback | L03, L10, L70 |
| `tenants.mcp` | vue3 setMCPByTenant(S1) | SDK, deepagents, base-agent, crewai-dr(직접) | L17, L19-L24 |
| `tenants.skills`(text[]) | agent-feedback | **S2 레포에서 읽는 코드 없음**(미확인) | agent-feedback core/database.py:274-296 |
| `tenant_skills` | deepagents | deepagents(skills_router.py:310) | L30 |
| `agent_skills`, `skill_contributions` | agent-feedback | agent-feedback(/api/skills/{s}/contributors) | L70 |
| `tenant_git_config` | (쓰는 쪽 S2에 없음 → S1 vue3 추정, 미확인) | deepagents | L31 |
| `resource_pull_requests` | deepagents(스킬 PR), agent-feedback(DMN·BPMN·스킬 귀속), vue3 | deepagents(검증), vue3 | L33, L71, L72 |
| `resource_eval_suites/cases/runs/results` | deepagents | deepagents(PR 검증) | L33 |
| `feedback_proposals` | agent-feedback(RPC 포함) | agent-feedback, vue3(경유 API) | L66, L68 |
| `proc_def` / `proc_def_version` | proc_def_version draft: agent-feedback | proc_def: deepagents·cli-agent·base-agent·agent-feedback·agent-utils(dmn)·voice·process-gpt-mcp | L12, L16, L60, L71 |
| `mcp_python_code` | agent-utils(upsert) | deepagents(먼저 확인), agent-utils | L57, L58 |
| `chat_rooms` | deepagents, base-agent(context) | 같은 서비스, vue3 | deepagents core/chat/chat_room.py:258-406; base-agent database.py:193-257 |
| `agent_sessions` | codex | codex | codex app/runtime/threads.py:37,105 |
| `notifications` | agent-utils | vue3(S1) | L59 |
| `env`(browser_use) | 미확인(S1) | SDK→browser-use | L09 |
| vecs `memories`(mem0) | **미확인** | agent-utils, crewai-dr | L47 |
| memento 표(knowledge_files·documents·document_pages/sections/blocks/images·knowledge_doc_cards·knowledge_folder_cards·processed_files·glossary_terms·tenant_oauth) + 벡터(chroma/qdrant) | memento | memento(다른 서비스는 HTTP로만 접근) | memento app/core/config.py:165-173 |
| Storage 버킷 `files` | office-mcp, codex, computer-use(/pod_mcp) | 화면·memento | L53 |
| Storage 버킷 `browser_use`, `task-image` | browser-use, agent-utils(image_manager) | 화면 | browser-use browser_use_agent_executor.py:124; agent-utils tools/image_manager.py:26 |
| 디스크 `{SKILLS_DIRS}` | deepagents(업로드·발행·시스템 스킬 시딩), cli-agent(/skills/upload·시딩) | deepagents, cli-agent | L29, L36 |
| claude-skills PVC `/app/skills` | claude-skills(/skills/upload) | base-agent(HTTP), crewai-action(MCP) | L37, L38 |

### 4. 끝에서 끝까지 흐름

비유 한 줄: `todolist`는 **공용 작업 게시판**, `users`의 에이전트 행은 **직원 카드**, `tenants.mcp`는 **회사 공구함 목록**, 스킬 디렉터리는 **업무 매뉴얼 서랍**, memento는 **사내 도서관**이다. 실행체는 게시판에서 자기 부서 쪽지(agent_orch)를 떼 가는 직원이다.

#### ① 에이전트 생성(말 → 프로필) → 저장 → 업무 배정 → 실행
```
사용자 "○○ 프로세스 만들어줘"(채팅)
 → vue3 /chat/stream (S1)                                    [CONNECTIONS C02→A01]
 → deepagents: bpmn-process-generation 스킬 05-agents 절차가
   agents/<id>.json{name,role,goal,persona,description} + process-definition.json(activity.agent, roles.endpoint)를 샌드박스에 씀  [L11]
 → 산출물 패널(file_artifact SSE) → 사용자가 '저장'
 → vue3 putAgent → users 행(is_agent, role·goal·persona·tools·skills·endpoint·agent_type·alias·model)   [L10]
   (화면에서 직접 만들 때도 같은 putAgent. pdf2bpmn(S3) 경로는 05-agents.md:5가 출처라고만 적음 — 미확인)
 → 프로세스 실행 시 completion이 todolist 생성: user_id=에이전트 id, agent_orch=activity.orchestration   [L01]
 → 실행체 폴링 RPC fetch_pending_task(p_agent_orch)   [L02]
 → SDK가 users 행 → extras.agents, tenants.mcp → extras.tenant_mcp   [L03]
 → 실행체별 해석:
    deepagents: rootAgent(액티비티 정의) 또는 metadata.agent_profile → 루트 프롬프트, 나머지는 서브에이전트   [L12]
    a2a: agents[0].endpoint로 외부 A2A 호출   [L13]
    crewai-action: 에이전트마다 CrewAI Agent, 첫째가 매니저
    cli-agent: role/goal/persona → CLI 네이티브 서브에이전트, CLI 종류는 agent_config.agent_cli   [L16]
    base-agent: is_agent 첫 행(액티비티 tools만 있으면 가상 프로필)
    openai-dr·deep-research·crewai-dr: users를 직접 다시 조회
```

#### ② 스킬 작성·업로드·평가 → 실행 시 주입
```
[작성] 채팅 "~하는 스킬 만들어줘" → deepagents 루트가 직접 6단계:
   SKILL.md 작성 → evals/evals.json → plan_skill_eval → test-runner(with/without skill) → evaluator 채점
   → complete_skill_creation(시나리오·채점을 resource_eval_* 저장, 통과 전 완료 보고 금지)   [deepagents core/agents/agent.py:84-120, L33]
 → 사용자 '저장' → publish_skill / register_skill_as_tenant
   → 디스크 {SKILLS_DIRS}/{tenant}/{provider_config_id|local}/<skill> + tenant_skills + (Git 연결 시) 테넌트 레포 push   [L29-L31; tools.py:3004,3162]
[업로드] vue3 → deepagents POST /skills/upload(zip)·/skills/upload-from-git   [skills_router.py:2047-2048]
        vue3 → cli-agent POST /skills/upload → {SKILLS_DIRS[0]}/{tenant}/   [cli-agent api/skills.py:22-31,90]
        (별도) claude-skills POST /skills/upload → PVC                          [L37 쪽 저장소]
[평가·개정 검증] 스킬 PR → vue3 → deepagents /skills/{n}/pull-requests/{pr}/verification
        → 변경 전/후 시나리오 재실행(resource_eval_runs/results), DMN·BPMN은 completion /regression-run   [L33-L35]
        → vue3 → /merge → Git 병합 후 auto_sync로 디스크 갱신(skills_router.py:652-710)   [L35]
[주입]
  deepagents: _get_skills(tenant, provider_config_id) → 샌드박스 /skills 마운트
              → 액티비티 skills ∪ users.skills(root_profile) ∪ '/스킬명' 슬래시로 FilteredSkillsMiddleware 필터   [L29; executor.py:1405-1424,1748-1769; agent.py:288-292,442-452]
  cli-agent: 같은 디스크 규칙 → cliagents가 .claude/skills/<n>/SKILL.md(+CLAUDE.md) 또는 .agents/skills/(+AGENTS.md)에 씀   [L36]
  base-agent: claude-skills HTTP로 SKILL.md 받아 시스템 프롬프트에 붙이고, 스킬별 mcp_config.json이 있으면 MCP 서버 동적 연결   [L37]
  crewai-action: users.skills 이름 → claude-skills·computer-use MCP 도구 우선순위   [L38]
  codex: 레포 내장 managed_skills만(테넌트 스킬 주입 없음)   [L39]
```

#### ③ MCP 등록·검사 → 실행 시 연결
```
vue3 MCP 설정 화면 → mcp-validator POST /validate(연결해 도구 목록 확인, 저장 안 함)   [L18]
 → vue3 setMCPByTenant → tenants.mcp = {mcpServers:{이름:{command,args,env}|{url,type,headers}}}   [L17]
 → 에이전트·액티비티는 '서버 이름'으로 고름: users.tools(콤마), 액티비티 tools, tool_filters
 → 실행 시:
    SDK가 tenants.mcp → extras.tenant_mcp   [L03]
    deepagents: tenants.mcp 재조회 + process-gpt-mcp(uvx) 자동 주입 → 채팅은 전체 서버, 워크아이템은 지정 서버만 → MultiServerMCPClient   [L19, L20]
    cli-agent: command 있는 stdio만 → .mcp.json / config.toml (http 서버는 조용히 빠짐)   [L23]
    crewai-action: SafeToolLoader(stdio)   [L24]
    base-agent: tenants.mcp + 로컬 mcp_config.json(process-gpt-mcp, office-mcp) + 스킬 mcp_config.json   [L21, L22, L37]
    codex: tenants.mcp 미사용, 내부 processgpt_knowledge만   [L25]
```

#### ④ 워크아이템 → 실행체 선택 → 실행 → 이벤트·결과 → 사람 질문(HITL)
```
completion(S1): 액티비티 orchestration → todolist.agent_orch (deepagents | cliagents | codex | a2a | crewai-action | langchain-react |
               browser-automation-agent | openai-deep-research | deep-research-custom | crewai-deep-research | pdf2bpmn …)   [L01]
 → 해당 실행체가 lease를 잡고 가져감(SDK: fetch_pending_task, 구형: 자체 RPC)   [L02, L05-L08]
 → 실행 중 events(record_events_bulk: task_started·도구 사용·task_completed·error) → 화면(S1)이 읽음   [L04]
 → 결과 save_task_result(output/draft, p_final) → completion이 다음 단계 진행(S1)
 → 채팅 경로는 같은 executor를 /chat/stream SSE로 직접 부름(SDK mount_chat_routes)
HITL(deepagents, 워크아이템은 agent_mode=COMPLETE일 때만 도구 부여):
   request_human_input → LangGraph interrupt → SDK가 INPUT_REQUIRED를 events.human_asked + todolist.draft_status=HUMAN_ASKED(lease 해제)로 기록   [deepagents core/chat/hitl.py:126-186; L04]
 → 사람이 답 → 화면이 feedback 추가 + draft_status=FB_REQUESTED(S1, SDK 주석 database.py:504-506) → 다시 폴링됨
 → workitem_resume_answer: feedback 마지막 항목을 답으로 Postgres 체크포인트에서 interrupt 재개   [hitl.py:189-210; L56]
HITL(crewai 경로): agent-utils human_asked → events + notifications → events 폴링으로 답 감지   [L59]
A2A: 외부 에이전트가 push 지원 → 웹훅 수신기가 결과를 events·todolist로 옮김   [L13-L15]
```

#### ⑤ 실행 기록·사용자 피드백 → 개정안 → 승인 → 스킬/DMN/정의 반영
```
사람이 완료 워크아이템에 피드백(todolist.feedback, S1 화면)
 → agent-feedback 7초: RPC agent_feedback_task → 새 항목만 → RPC append_workitem_feedback_to_batch
   → feedback_proposals(COLLECTING, tenant·proc_def·activity 단위)   [L65, L66]
 → 900초 트리거: CLASSIFYING 점유 → LLM 분류(SKILL / DMN_RULE / PROCESS_DEFINITION) → strategy /api/ai/alignment 근거 첨부(→S3)
   → PROPOSED 또는 DISCARDED   [L66, L67]
 → vue3 /feedback-proposals 화면 → approve → RPC decide_feedback_proposal_target → run_target_apply   [L68]
   SKILL: Deep Agent가 스킬 수정 → deepagents POST /skills/{n}/commit(브랜치·PR, resource_pull_requests 귀속)
          → users.skills·tenants.skills·agent_skills·skill_contributions 갱신   [L69, L70]
          → vue3 PR 화면 → deepagents 검증(이전 시나리오 재실행) → merge   [L35]
   DMN_RULE / PROCESS_DEFINITION: draft proc_def_version + resource_pull_requests만 생성   [L71]
          → vue3 범용 리소스 PR 워크플로(resource_pr_reviews)에서 검토·병합 → 라이브 proc_def 반영(S1, 세부 미확인)   [L72]
   (에이전트 프로필 role·goal·persona·tools 개정 target 없음, mem0 기록 없음)
```

#### ⑥ 문서 지식(memento) → 에이전트 참조
```
[적재] vue3 → memento /knowledge/files/upload·/process(Drive)   [CONNECTIONS C02→T01, memento app/api/knowledge_admin.py:207, ingest.py:38]
       completion → memento /process-output(폼 산출물 문서화, todolist.output_url)   [L48]
       SDK 산출물 → /save-to-storage, base-agent 도구 결과 → /save-to-storage(room 범위)   [L49, L42]
       codex 첨부 → /process-session-file(skip_vector_index)   [L41]
       → 파싱·청킹·임베딩 → chroma/qdrant + knowledge_*·document_* 표; 용어는 robo glossary 조회(→S3)   [L50]
[참조]
  deepagents: search_documents 등 도구 → /search·/catalog·/document/grep·/document/page·/summarize   [L40]
  codex: processgpt_knowledge MCP → 15개 탐색 엔드포인트   [L25, L41]
  base-agent: 모든 LLM 호출 앞에서 /retrieve(room_id)   [L42]
  office-mcp list_reference_documents, deep-research, crewai-dr → /retrieve 계열   [L43-L45]
  crewai-action(agent-utils) → 외부 운영 memento /api/retrieve   [L46]
[개인 메모리] mem0 vecs.memories는 검색만 확인, 누가 쓰는지는 미확인   [L47]
```

### 5. CONNECTIONS.md에 없던 새 연결 (코드로 확인)

CONNECTIONS.md(67개)에는 S2 서비스 사이의 **런타임 데이터 연결**(Supabase 표·RPC, MCP, A2A)이 거의 없다. 아래는 이번에 코드로 새로 확인한 연결이다(번호는 2절).

| # | 출발 → 도착 | 종류 | 왜 중요한가 |
|---|---|---|---|
| N01 | completion → todolist.agent_orch → 각 실행체 폴링 | 호출(표·RPC) | 실행체 선택의 실제 배선이다. HTTP가 아니다 (L01, L02) |
| N02 | SDK → users·tenants.mcp → extras | 호출(표) | 에이전트 정의·MCP가 실행체에 도착하는 길 (L03) |
| N03 | vue3 → users(putAgent), vue3 → tenants.mcp | 호출(표) | 에이전트·MCP 정의의 유일한 작성자 (L10, L17) |
| N04 | a2a-orch → 외부 A2A 에이전트(users.endpoint) / 외부 → a2a-webhook-receiver | A2A·HTTP | A2A 경로 전체. 수신기는 별도 프로세스(포트 9000) (L13-L15) |
| N05 | process-gpt-mcp → todolist(agent_orch=pdf2bpmn) → bpmn-extractor(S3/S1) | 호출(표) | ReAct 에이전트가 PDF→BPMN 워커를 깨움. deepagents는 이 도구를 막음 (L27, L20) |
| N06 | process-gpt-mcp → https://{tenant}.process-gpt.io/completion/complete | 호출(HTTP) | 로컬에서도 운영 도메인으로 나갈 수 있음(PROCESS_GPT_API_BASE_URL로 덮어씀) (L28) |
| N07 | base-agent → claude-skills(HTTP /skills/{n}/files/…) | 호출 | claude-skills를 실행 시점에 쓰는 실제 소비자 (L37) |
| N08 | crewai-action → claude-skills·computer-use(MCP, tenants.mcp 경유) | 호출 | computer-use를 소비하는 코드상 유일한 근거 (L38) |
| N09 | deepagents → completion /complete·/regression-run | 호출(HTTP) | 프로세스 시작과 스킬·DMN 회귀 검증이 completion에 의존 (L34, L55) |
| N10 | deepagents → tenant_git_config·GitHub/GitLab/Gitea·anthropics/skills | 호출 | 스킬의 원천과 PR이 외부 Git에 있음 (L31, L32) |
| N11 | deepagents → resource_eval_*·resource_pull_requests·tenant_skills | 호출(표) | 스킬 평가·PR 기록 (L30, L33) |
| N12 | deepagents·cli-agent ↔ 디스크 {SKILLS_DIRS}/{tenant} | 공유 구성(디스크) | 두 실행체가 같은 디렉터리 규칙을 씀. 볼륨 공유는 배포에 달림 (L29, L36) |
| N13 | agent-feedback → strategy /api/ai/alignment (→S3) | 호출 | 피드백 개정안의 전략 정렬 게이트 (L67) |
| N14 | agent-feedback → deepagents /skills/upload·/commit·/files (코드 경로 확정) | 호출 | CONNECTIONS에는 vite.config 근거만 있었음. 실제 클라이언트·경로를 확인 (L69) |
| N15 | agent-feedback → feedback_proposals·proc_def_version·resource_pull_requests·users.skills·tenants.skills·agent_skills·skill_contributions | 호출(표) | 학습 결과가 쌓이는 곳 (L66, L70, L71) |
| N16 | agent-utils → memento **외부 운영 주소** https://memento.process-gpt.io/api/retrieve | 호출 | 사내 배포에서도 외부로 나감. 다른 실행체의 내부 주소와 불일치 (L46) |
| N17 | agent-utils·crewai-dr → Postgres vecs.memories(mem0) | 호출(DB 직접) | Supabase REST가 아니라 DB 직접 연결 (L47) |
| N18 | agent-utils·deepagents ↔ mcp_python_code | 공유 표 | CrewAI가 만든 결정적 코드를 deepagents가 먼저 재사용 (L57, L58) |
| N19 | memento → robo glossary(→S3) | 호출 | memento가 robo 계열에 의존 (L50) |
| N20 | completion → memento /process-output, SDK → memento /save-to-storage | 호출 | 실행 산출물이 문서 지식으로 되돌아오는 길 (L48, L49) |
| N21 | codex → memento(15개 엔드포인트) + 내부 processgpt_knowledge MCP | 호출 | CONNECTIONS의 "자료 조회"보다 넓다 (L25, L41) |
| N22 | deep-research → office-mcp generate_slides | 호출 | office-mcp에서 IMAGE_GENERATION_ENABLED가 꺼지면 도구가 없어 실패 가능 (L52) |
| N23 | office-mcp → memento /retrieve, office-mcp·codex·computer-use → Storage `files` | 호출 | (L43, L53) |
| N24 | openai-dr·deep-research·crewai-dr → 자체 RPC(*_fetch_pending_task) | 호출(RPC) | SDK를 거치지 않는 구형 폴링 3종 (L05-L07) |
| N25 | langchain-react(구형)와 base-agent가 같은 agent_orch=`langchain-react` | 공유 큐 | 둘 다 켜면 일을 나눠 가짐 (L08) |
| N26 | browser-use ← SDK가 env(browser_use) 민감정보 주입 | 호출(표) | (L09) |
| N27 | react-voice-agent → Supabase 읽기 + OpenAI Realtime | 호출 | CONNECTIONS에는 등록 관계만 있음 (L63) |
| N28 | computer-use → Kubernetes API | 호출 | (L54) |
| N29 | X08 llm-factory ← a2a-orch·agent-utils·agent-feedback·crewai-action·crewai-dr | 의존 | (1절 X08) |

### 6. 미확인

1. **mem0 `memories`에 쓰는 주체**: agent-utils·crewai-dr은 검색만 하고 agent-feedback에도 쓰기 코드가 없다(grep 0건). S1·S3 쪽 확인이 필요하다.
2. **스킬 저장소 두 갈래의 동기화**: deepagents 디스크·tenant_skills와 claude-skills PVC 사이에 동기화 코드가 없다. base-agent·crewai-action은 claude-skills만 보고, deepagents·cli-agent는 디스크만 본다. 같은 스킬이 양쪽에 있는지는 운영 데이터를 봐야 안다.
3. **deepagents와 cli-agent의 `{SKILLS_DIRS}` 볼륨 공유**: 코드는 같은 규칙을 쓰지만, 같은 볼륨을 마운트하는지는 배포 설정(process-gpt-infra-docker·k8s, S1)에 달려 있다.
4. **DMN·BPMN 병합 요청의 라이브 반영**: agent-feedback은 draft proc_def_version과 resource_pull_requests까지만 만든다. 병합 후 proc_def에 반영하는 코드는 vue3(ProcessGPTBackend.ts:9339~) 쪽으로 보이지만 세부는 확인하지 않았다(S1).
5. (확인함) 스킬 PR merge 뒤 디스크 반영: deepagents `/merge`가 Git provider로 병합하고, auto_sync(기본 true)면 기본 브랜치 트리를 받아 `{SKILLS_DIRS}`의 스킬 디렉터리에 다시 쓴다(deepagents core/api/skills_router.py:652-710). cli-agent가 같은 볼륨을 보는지는 3번과 같이 미확인이다.
6. **tenants.skills(text[])를 읽는 쪽**: S2 레포에는 없다.
7. **tenant_git_config·env(browser_use)를 쓰는 쪽**: S2 레포에는 없다(S1 vue3로 추정).
8. **HITL 답을 화면이 FB_REQUESTED로 바꾸는 코드**: SDK 주석(database.py:504-506)만 확인했다(S1 vue3).
9. **events를 화면이 읽는 방식**(Realtime 구독 또는 폴링): S1.
10. **pdf2bpmn(bpmn-extractor)의 에이전트 프로필 생성 `_llm_generate_agent_profile`**: 05-agents.md:5가 출처라고만 적혀 있다(S3).
11. **computer-use의 실제 포트·등록 주소**: run_server.py는 8888, k8s service는 8000이다. tenants.mcp에 어떤 URL로 등록되는지는 운영 데이터를 봐야 안다.
12. **base-agent의 CLAUDE_SKILLS_BASE_URL 기본값 :8000 vs claude-skills 기본 포트 8765**: 운영 환경변수로 맞추는지 미확인.
13. **codex `/route`**: 항상 자기 자신을 고른다(main.py `/route`). 이 라우트를 누가 부르는지(session-router·gateway, S1)는 미확인.
14. 비공개 레포 거부는 없었다(22개 모두 로컬 클론 있음). process-gpt-base-agent-langchain-react 안의 process-gpt-mcp는 서브모듈이 아니라 일반 디렉터리로 들어 있다.

---

### 부록: 서비스별 근거 메모 (조사 원본)
#### A01 process-gpt-deepagents@faedeaa
- 역할: LangGraph deepagents 실행체. 채팅(/chat/stream SSE)과 todolist 폴링(agent_orch=`deepagents`) 둘 다. 스킬 생성·평가·PR 검증 API도 이 서비스가 가진다.
- 포트 PORT=8888 (server.py:39). 폴링 끄기 DEEPAGENTS_PROCESS_POLLING (server.py:47).
- 나가는 호출: Supabase tenants.mcp(executor.py:1360-1374), proc_def.definition 읽어 액티비티 tools/skills/rootAgent·서브프로세스 에이전트(core/chat/activity.py:19,77,125,260), chat_rooms(core/chat/chat_room.py:273,348,356), tenant_skills insert(core/api/skills_router.py:329, core/skills/tools.py:702,3244), tenant_git_config(core/skills/git_providers/factory.py:34), resource_pull_requests(skills_router.py:397), resource_eval_suites/cases/runs/results(core/skills/eval_tools.py:621-889, pr_verification.py:458-866), mcp_python_code·todolist·events(core/deterministic/replay.py:176,420,845), users/proc_def/form_def/bpm_proc_inst/todolist/configuration 조회(core/bpm/tools.py:111-432)
- HTTP: memento GET /search·/catalog·/document/grep·/document/page·/summarize (core/rag/memento.py:22,87,178,236,281,329; MEMENTO_BASE_URL 기본 http://127.0.0.1:8005) / completion POST /complete(프로세스 시작, core/bpm/tools.py:46,531) · POST /regression-run(core/skills/regression_client.py:21,92) / office-mcp JSON-RPC tools/call store_and_render_hwpx (executor.py:171-215,276; PROCESS_GPT_OFFICE_MCP_URL 기본 http://localhost:1192/mcp/) / strategy /api/objectives·/api/kpis·/api/map (core/strategy/tools.py:23,103-481) — 단 agent.py:265에서 주석 처리돼 에이전트에 붙지 않음
- MCP: tenants.mcp.mcpServers → langchain-mcp-adapters MultiServerMCPClient (core/llm/mcp.py:15-100). process-gpt-mcp를 `uvx process-gpt-mcp` stdio로 자동 주입(core/llm/mcp.py ensure_process_gpt_mcp)
- 스킬: 파일시스템 {SKILLS_DIRS}/{tenant}/{provider_config_id|local}/{skill}/SKILL.md + 전역 컬렉션(core/skills/skills.py:46-108). Git 스킬 prefetch SKILL_REPO_URLS(기본 github anthropics/skills, git_skill_fetcher.py:44,92). 번들 시스템 스킬 시딩(local_system_skills.py:39). Docker 샌드박스에 /skills로 마운트(agent.py:38-39,432-440)
- HITL: request_human_input → LangGraph interrupt(core/chat/hitl.py:126-136); 워크아이템은 COMPLETE 모드에서만(hitl.py:173-186), 재개 답은 todolist.feedback 마지막 항목(hitl.py:189-210). 체크포인트 Postgres DB_*(core/storage/checkpointer.py:96-150)
- 들어오는 호출: vue3 → /chat/stream, /skills/* (CONNECTIONS), agent-feedback → /skills/* (아래 확인)

#### A02 process-gpt-base-agent-langchain-react@e566a60 (+ 내장 process-gpt-mcp)
- 역할: LangChain ReAct "Work Assistant". SDK 폴링 agent_type=`langchain-react`(src/work_assistant_agent/server.py:47,58) + /chat/stream SSE(server.py:84). PORT 기본 8008(server.py:93).
- 에이전트 프로필: SDK가 실어 준 extras.agents(=users 행) 중 is_agent==True 첫 번째(executor.py:143-148,895-915). 액티비티 tools가 있으면 가상 프로필 "work-assistant-fallback"(executor.py:902-912).
- MCP: tenants.mcp 조회(database.py:444-462, executor.py:854-860) + 로컬 mcp_config.json(MCP_CONFIG_PATH, runtime.py:32) — 기본 `work-assistant`=process-gpt-mcp(stdio), `process-gpt-office-mcp`=http://process-gpt-office-mcp-service:1192/mcp (mcp_config.json:3-10)
- 스킬: **claude-skills 서비스에서 HTTP로 받음** — GET {CLAUDE_SKILLS_BASE_URL 기본 http://claude-skills:8000}/skills/{name}/files/SKILL.md?tenant_id= (agent.py:2263,2283-2297) → 시스템 프롬프트에 붙임(agent.py:2304-2330). 같은 경로로 스킬별 mcp_config.json을 받아 MCP 서버 동적 연결(agent.py:2333-2352,2566). 스킬 이름은 metadata.agent_profile.skills 또는 AGENT_SKILLS_JSON(agent.py:2250-2260)
- memento: POST /save-to-storage(도구 결과·대화 저장, memory.py:101-103), GET /retrieve(room_id·top_k, 모든 LLM 호출 앞단, memory.py:218-223). MEMENTO_BASE_URL 기본 http://memento:8005(memory.py:41-45)
- DB: chat_rooms.context(database.py:204-257), proc_def.definition(database.py:430), tenants.mcp(database.py:462)
- 내장 process-gpt-mcp(MCP 서버, stdio): Supabase REST 직접 — users(server.py:1019), todolist insert agent_orch=`pdf2bpmn`(create_consulting_process_workitem·create_pdf2bpmn_workitem, server.py:1156-1178, 2014-2051 → S3/S1 bpmn-extractor 폴링 대상), proc_def·form_def·bpm_proc_inst·todolist·configuration 조회(server.py:1222-2103); execute_process → POST https://{tenant}.process-gpt.io/completion/complete (PROCESS_GPT_API_BASE_URL로 덮어씀, server.py:90-100,1513) → S1 gateway→completion. OCR: Synap OCR(SYNAP_OCR_BASE_URL)·OpenAI vision

#### A04 process-gpt-codex@cede40e
- 역할: OpenAI Codex app-server를 대화별로 띄워 실행하는 실행체. SDK agent_type=`codex`(app/main.py:27,82), 폴링은 CODEX_PROCESS_POLLING(settings.process_polling_enabled, main.py:109). PORT 기본 8891(app/config.py:278).
- 들어오는 HTTP: /chat/stream·/{agent_id}/chat/stream·/health(SDK, main.py:225-230), POST /chat(232), /session/folder GET·POST·DELETE(240-311), POST /route(항상 자기 선택, 185-199), POST /{agent_id}/warmup(201)
- 나가는 호출: memento GET /catalog·/folders/tree·/folders/open·/document/grep·/document/page·/search·/summarize·/documents/full-text·/document/raw·/sections/search·/documents/outlines·/document/outline·/document/section·/document/locate·/glossary/terms, POST /process-session-file(skip_vector_index) (app/knowledge/memento.py:48-185; MEMENTO_BASE_URL 기본 http://127.0.0.1:8005 config.py:344). 이 memento 클라이언트를 내부 MCP 서버 `processgpt_knowledge`(stdio, app/knowledge/mcp_server.py)로 감싸 Codex config.toml에 넣는다(config.py:592-602)
- DB: todolist 같은 인스턴스 이전 단계 output 조회(app/process/run.py:74), agent_sessions(대화↔codex thread 매핑, app/runtime/threads.py:37,105), Supabase Storage 버킷 `files`(app/workspace/folder_store.py:21,80-143)
- 스킬: 저장소 안 managed_skills/를 CODEX_HOME/skills로 복사(config.py:19,471-473). **테넌트 스킬(tenant_skills)·tenants.mcp를 읽는 코드 없음**(grep 0건)
- 에이전트 프로필: metadata.agent_profile은 채팅 저장 시 이름·아이콘에만 사용(app/chat/persistence.py:32-54)

#### A05 process-gpt-cli-agent@0a0e3d3 + A06 cliagents@7c7a392
- 역할: Claude Code·Codex CLI를 작업공간에서 띄워 워크아이템/채팅 처리. SDK agent_type=`cliagents`(core/settings.py:19, server.py:86). PORT 기본 8890, 동시 실행 CLIAGENTS_MAX_CONCURRENT_RUNS=3, 기본 CLI CLIAGENTS_DEFAULT_CLI=claude-code(core/settings.py)
- 들어오는 HTTP: GET /agents(api/availability.py:28), /skills GET·/skills/upload POST·/skills/{name} DELETE(api/skills.py:89-91), /runs/{id}/stream·status(api/chat_attach.py:60-61), /runs/{id}/files·download(api/files.py:59-60), /runs/{id}/journal·replay·undo(api/replay.py:68-70), /chat/stream(server.py:90)
- CLI 선택: row·extras·액티비티 agent_config의 agent_cli/agentCli/cli_agent 키(core/selection.py:30,86-127); 액티비티 선언은 proc_def.definition 조회(core/activity.py:107)
- MCP: SDK가 준 extras.tenant_mcp(=tenants.mcp)에서 **command 있는 stdio 서버만** 사용(core/bridge.py:134-160 — url만 있는 http 서버는 건너뜀) → CLI 네이티브 서브에이전트에 부착(executor.py:138-146). cliagents가 Claude Code는 프로젝트 `.mcp.json`, Codex는 `$CODEX_HOME/config.toml`에 씀(cliagents providers/claude_code.py:62,158; providers/codex.py:8)
- 스킬: 번들 system-skills + {SKILLS_DIRS}/{tenant}·{tenant}/local + 워크아이템 git_skills(core/skills.py:137-160, executor.py:593-600) → cliagents가 `.claude/skills/{name}/SKILL.md`·CLAUDE.md 또는 `.agents/skills/{name}/SKILL.md`·AGENTS.md로 배치(claude_code.py:51-55, codex.py:47-49). **tenant_skills 표는 읽지 않음**(디스크 공유 전제, 볼륨 공유는 배포 설정 몫 — 미확인)
- 에이전트 프로필: extras.agents(=users 행) → role/goal/persona로 CLI 서브에이전트 정의(core/subagents.py:45, executor.py:141-146)
- 실행: claude `--print --output-format stream-json --permission-mode … --resume`(claude_code.py:82-98)

#### A03 process-gpt-a2a-orch@ad5e937
- 역할: 외부 A2A 에이전트로 워크아이템을 넘기는 중계 실행체. SDK agent_type=`a2a`(src/a2a_agent_executor/server.py:137-139), HTTP 서버 없음(폴링만).
- 대상 결정: SDK extras.agents[0](=todolist.user_id가 가리키는 users 행)의 `endpoint` 필드(executor.py:121-122,476-488) → AgentCard 조회 후 push_notifications 지원이면 웹훅 모드(executor.py:131-160), 아니면 동기 send_message(executor.py:188-211)
- 웹훅 리시버(별도 프로세스·Pod): POST /webhook/a2a/todolist/{todolist_id}(src/a2a_agent_webhook_receiver/server.py:52), 포트 WEBHOOK_RECEIVER_PORT 기본 9000(server.py:155), 외부 주소 WEBHOOK_PUBLIC_BASE_URL(예 http://a2a-webhook-receiver:9000, executor.py:53). 받은 결과를 SDK ProcessGPTEventQueue로 events·todolist에 기록(processor.py:9,101-145), events에서 task_started job_id 재사용 조회(database.py:92)
- 폼 매핑: a2a_form_processor가 form_def·todolist 읽고 LLM(LLM_PROXY_URL)으로 output JSON 생성(a2a_form_processor/database.py:35,46; processor.py:134)

#### X07 process-gpt-agent-utils@5dbd7e0 (라이브러리, 사용처: crewai-action)
- 역할: CrewAI 계열 실행체의 공통 도구 묶음. SafeToolLoader가 로컬 도구 mem0·memento·human_asked·dmn_rule + mcp_config.mcpServers(stdio) 도구를 이름으로 만든다(tools/safe_tool_loader.py:34-39,93-210). agent_type=='a2a'이면 A2A_{KEY}_URL 환경변수로 A2A 도구 생성(safe_tool_loader.py:132-135,533-536)
- memento: **하드코딩** GET https://memento.process-gpt.io/api/retrieve?query&tenant_id&proc_inst_id (tools/knowledge_manager.py:269-271) — 다른 실행체(MEMENTO_BASE_URL 내부 주소)와 다름
- mem0 개인지식: Supabase Postgres(DB_USER/HOST… 직접 연결) vecs 컬렉션 `memories`, agent_id=에이전트 user_id로 search(knowledge_manager.py:21-25,162-198). 이 레포에는 search만 있음(쓰기 주체는 agent-feedback — 아래)
- human_asked: events에 event_type=human_asked 기록 + notifications insert(url=/todolist/{task_id}) 후 events를 폴링해 답 감지(tools/human_query_tool.py:126-241; utils/database.py:180-250)
- dmn_rule: proc_def where owner=user_id,type='dmn' 읽어 DMN XML 파싱 후 LLM 판정(tools/dmn_rule_tool.py:83-160)
- 결정적 코드: mcp_python_code(proc_def_id·activity_id·tenant_id) 조회·upsert(utils/database.py:289-321, tools/deterministic_code_tool.py:620,745) — deepagents도 같은 표를 먼저 확인(deepagents core/deterministic/replay.py:845)
- 그 외 DB: events insert, tenants, todolist, form_def (utils/database.py:180-325)

#### X08 process-gpt-llm-factory@a32e57e (라이브러리)
- 역할: LLM_PROVIDER(openai·azure·anthropic·ollama)로 LangChain 챗 모델 생성(llm_factory/factory.py:45-205). 네트워크 호출은 LLM 공급자뿐.
- 사용처(import·의존성 근거): a2a-orch(src/a2a_form_processor/llm.py), agent-utils(tools/deterministic_code_tool.py), agent-feedback(core/llm.py), crewai-action(llm.py), crewai-deep-research(crews/*.py, utils/context_manager.py)

#### T01 process-gpt-memento@659ab9f
- 역할: 문서 인제스천·RAG·문서 탐색 서버(FastAPI, 포트 8005 main.py:13). 벡터 백엔드 VECTOR_BACKEND 기본 chroma, qdrant 선택(app/core/config.py:165-173)
- 들어오는 HTTP(app/api/*): 검색 /search·/retrieve·/retrieve-by-indices·/documents/list·/documents/full-text(retrieve.py:82-585), 탐색 /catalog·/glossary/terms·/document/grep·/document/page·/document/raw(navigator.py:132-615), /folders/tree·card·open(folders.py), /sections/search·/document/outline·/documents/outlines·/document/section(sections.py), /document/blocks·page-image·locate(citations.py), /summarize(summary.py:76), 적재 /process·/process-session-file·/process-output·/save-to-storage·/artifact-url(ingest.py:38-636), 관리 /knowledge/files/*·/knowledge/folders/*(knowledge_admin.py), Google Drive /auth/google/*·/save-to-drive
- DB: knowledge_files·knowledge_folders·documents·document_pages·document_sections·document_blocks·document_images·knowledge_doc_cards·knowledge_folder_cards·processed_files·files·tenant_oauth·glossary_terms(위 grep 집계), todolist 읽기·output_url 쓰기 + form_def 읽기(/process-output, ingest.py:259-324)
- 나가는 호출: robo glossary GET {ROBO_GLOSSARY_API_BASE_URL 기본 http://127.0.0.1:5504/robo}/glossary/terms/search(app/services/glossary.py:10-32) → S3 robo 계열, LLM·임베딩(MEMENTO_LLM_PROVIDER/EMBEDDING_PROVIDER, LLM_PROXY_URL 레거시, config.py:105-271), Google Drive
- 호출자(코드 확인): deepagents(core/rag/memento.py), base-agent(memory.py /retrieve·/save-to-storage), codex(app/knowledge/memento.py), agent-utils(외부 https://memento.process-gpt.io/api/retrieve), deep-research·office-mcp(아래)

#### T03 process-gpt-office-mcp@7e95c6e
- 역할: HWPX·DOCX 생성·편집·HTML 렌더 MCP 서버(FastMCP streamable-http, stateless·json_response, main.py:132-140). 포트 1192(office_mcp/config.py:112). REST 보조 /api/edit-slide-image·/api/enhance-image(main.py:127-128, Gemini 이미지)
- MCP 도구: list_reference_documents, generate_hwpx, store_and_render_hwpx, save_hwpx_from_html, edit_hwpx_page_html, generate_docx, edit_docx_page_html, save_docx_from_html(office_mcp/mcp_server.py:364-1036)
- 나가는 호출: memento GET /retrieve(office_mcp/memento.py:85,147; MEMENTO_SERVICE_URL 기본 http://memento-service:8005 config.py:51), Supabase Storage 업로드 hwpx/…(mcp_server.py:232-240), LLM(office_mcp/agent)
- 호출자(코드 확인): deepagents가 MCP 클라이언트 없이 bare JSON-RPC로 store_and_render_hwpx 호출(deepagents executor.py:184-215,276), base-agent mcp_config.json의 `process-gpt-office-mcp`(http://process-gpt-office-mcp-service:1192/mcp)

#### T04 process-gpt-mcp-validator@cf220bf
- 역할: MCP 서버 설정 하나를 실제로 붙여 보고 도구 목록을 돌려주는 무상태 검사기(FastAPI, 포트 8800 main.py:15). POST /validate·/validate-server, GET /server-info/{name}·/examples·/health(src/mcp_validator/api.py:43-189). transport stdio·streamable_http·sse(api.py:199-220)
- DB·다른 서비스 호출 없음(grep 0건). 검사 통과 설정을 tenants.mcp에 저장하는 주체는 이 레포에 없음 → S1 process-gpt-vue3(미확인)

#### T07 process-gpt-claude-skills@456d56f
- 역할: 스킬 저장·검색 서버 겸 MCP 서버. FastMCP streamable-http(/mcp, packages/backend/src/claude_skills_mcp_backend/http_server.py:2319,2391) + REST. 포트 8765(Dockerfile:30, k8s/service.yaml:13). 저장소 SKILLS_STORAGE_PATH(=PVC claude-skills-storage /app/skills, http_server.py:126; k8s/deployment.yaml:37-76)
- MCP 도구: find_helpful_skills, read_skill_document, list_skills(mcp_handlers.py:148-229)
- REST: /skills/upload·/skills/upload-from-github·/skills/download·/skills/list·/skills/list-builtin·/skills/check·/skills/{name} DELETE·/skills/{name}/files GET·/skills/{name}/files/{path} GET·PUT·DELETE(http_server.py:2336-2385). tenant_id·agent_id로 스킬 범위를 나눔(http_server.py:153-190). **DB(tenant_skills) 미사용** — 파일 저장소만
- 호출자(코드 확인): base-agent-langchain-react가 GET /skills/{name}/files/SKILL.md·mcp_config.json (base-agent agent.py:2263-2352; 기본 주소 http://claude-skills:8000 — 서비스 기본 포트 8765와 다름, 환경변수로 맞춘다고 봐야 함)
- 주의: deepagents·cli-agent는 이 서비스를 쓰지 않고 자기 /skills API + 디스크 + tenant_skills로 따로 관리 → **스킬 저장소가 두 갈래**

#### T08 process-gpt-computer-use@174adf6
- 역할: 세션마다 Kubernetes Pod를 만들어 셸·Node 실행을 스트리밍하는 MCP 서버(FastMCP streamable-http, run_server.py:33 포트 8888; k8s/service.yaml:12 포트 8000 — 서로 다름)
- MCP 도구: create_session, delete_session, list_sessions, extend_session, get_session_status, list_files, create_file, delete_file, upload_file, run_node, run_shell(src/mcp_server.py)
- 나가는 호출: Kubernetes API(POD_NAMESPACE·IN_CLUSTER, src/pod_manager.py, mcp_server.py:90-121), Supabase Storage 버킷 files 접두 /pod_mcp(mcp_server.py:32-41)
- ProcessGPT 쪽에서 이 서버 주소를 박아 둔 코드 없음 → tenants.mcp에 http 서버로 등록해 쓰는 구조로 추정(미확인). cli-agent는 http MCP를 건너뛰므로 cli 경로에선 못 씀(cli-agent core/bridge.py:149-150)

#### P04 process-gpt-agent-feedback@84d2a0e
- 역할: 완료된 워크아이템의 사람 피드백을 모아 개정안(SKILL·DMN_RULE·PROCESS_DEFINITION)을 만들고, 승인되면 반영 요청을 만든다. FastAPI 포트 PORT 기본 6789(main.py 끝)
- 백그라운드 2개(main.py lifespan): ① 7초 수집 — RPC `agent_feedback_task`(DONE+feedback 행, core/database.py:38-50) → 새 피드백만 잘라 RPC `append_workitem_feedback_to_batch`(tenant·proc_def_id·activity_id 단위 배치, database.py:391-415) → todolist.feedback_collected_count 갱신(database.py:161-169) ② FEEDBACK_BATCH_TRIGGER_INTERVAL(기본 900초) — feedback_proposals COLLECTING→CLASSIFYING 점유(database.py:427-471) → LLM 분류 classify_and_extract_proposal(feedback_batch_manager.py:401-410) → 전략 정렬 근거 POST {STRATEGY_SERVICE_URL 기본 http://localhost:8014}/api/ai/alignment(feedback_batch_manager.py:83-104 → S3 process-gpt-strategy) → PROPOSED 또는 DISCARDED(database.py:497-575)
- 들어오는 HTTP: GET /feedback-proposals·/feedback-proposals/my-feedback·/{id}, POST /feedback-proposals/{id}/targets/{type}/approve·reject(core/feedback_proposal_routes.py:50,100-449), GET /api/skills/{skill}/contributors(core/skill_contributor_routes.py:14-17). 승인 → RPC decide_feedback_proposal_target(_at)(database.py:608-651) → run_target_apply(feedback_proposal_routes.py:382-450)
- 반영(feedback_batch_manager.py:945-1000):
  - SKILL → Deep Agent(core/deep_agent.py)가 스킬 수정 → **deepagents 스킬 API** POST /skills/upload·POST /skills/{name}/commit(브랜치+PR, resource_pull_requests 귀속)·GET /skills·/skills/{name}/files (core/skill_api_client.py:25,195,258,308,366,450; SKILL_API_BASE_URL 기본 http://localhost:8888) → users.skills(콤마 문자열)·tenants.skills(text[])·agent_skills upsert·skill_contributions insert(database.py:224-352, learning_committers/skill_committer.py:33,68)
  - DMN_RULE / PROCESS_DEFINITION → 라이브 proc_def는 건드리지 않고 draft proc_def_version 행 + resource_pull_requests 병합 요청만 생성(feedback_batch_manager.py:653-900 중 54-96,141-232행대)
- 읽기: todolist·events·users(is_agent·agent_type='agent')·bpm_proc_inst·proc_def(definition·bpmn)(database.py:57-260, 755-1000)
- mem0 `memories`에 쓰는 코드 없음(grep 0건) → agent-utils Mem0Tool의 쓰기 주체 **미확인**

#### A07 process-gpt-openai-deep-research@49ddcd9
- 역할: OpenAI Responses API deep research(web_search_preview, research/api_deep_research.py:23)로 보고서 작성. **SDK 미사용 자체 폴링**: RPC openai_deep_fetch_pending_task(운영)·openai_deep_fetch_pending_task_dev(p_tenant_id='uengine')(core/database.py:60-77), 정의 function.sql:50,153 agent_orch='openai-deep-research'. 포트 PORT 기본 8000(main.py:103)
- DB: users(에이전트 프로필 role/goal/persona/tools/model, core/database.py:185-195), todolist, form_def(253), RPC fetch_done_data(이전 산출물, 121) · save_task_result(283), events insert(utils/event_logger.py:52)
- memento·MCP·스킬 사용 없음(grep 0건)

#### A08 process-gpt-deep-research@8a343e2
- 역할: 다단계 리서치(Tavily 웹검색·memento 문서) 후 HWPX·DOCX·슬라이드 보고서 생성. 자체 폴링 RPC deep_research_fetch_pending_task(_dev) p_agent_orch=`deep-research-custom`(src/db.py:26-48, function.sql:4-53), consumer_id는 SDK 함수 재사용(db.py:30). dev는 POLLING_TENANT_ID 한정
- 나가는 호출: memento GET /retrieve·/documents/chunks-metadata·/documents/list, POST /retrieve-by-indices(src/services/memento.py:56-166; MEMENTO_SERVICE_URL 기본 http://memento-service:8005 config.py:55) / office-mcp FastMCP 클라이언트 call_tool generate_hwpx·generate_docx·generate_slides(src/services/mcp_client.py:40,113,145; PROCESS_GPT_OFFICE_MCP_URL 기본 http://process-gpt-office-mcp-service:1192/mcp config.py:58) — generate_slides는 office-mcp에서 IMAGE_GENERATION_ENABLED일 때만 등록(office-mcp mcp_server.py:1097-1110) / Tavily(TAVILY_API_KEY) / LLM(DEEP_RESEARCH_LLM_PROVIDER: openai·openrouter·custom)
- DB: proc_inst_source(첨부, db.py:102), todolist, form_def, events insert(db.py:197), users(에이전트 프로필 is_agent, db.py:217-243)

#### X03 process-gpt-crewai-action@ecdf8de
- 역할: CrewAI 동적 크루로 워크아이템 수행. SDK agent_type=`crewai-action`(crewai_action_server.py:27), 헬스 서버 포트 8000(crewai_action_server.py:19)
- 에이전트: extras.agents(=users 행)마다 CrewAI Agent 생성, 첫째가 매니저(crew_factory.py:328-390), agents[0].tool_priority_order로 도구 순서(crewai_action_executor.py:262-274)
- 도구: agent-utils SafeToolLoader(mcp_config=extras.tenant_mcp, crew_factory.py:348-349; crewai_action_executor.py:281) → mem0·memento·human_asked·dmn_rule + tenants.mcp 서버
- 스킬: users.skills 이름을 **tenants.mcp에 등록된 MCP 서버 `claude-skills`·`computer-use`의 도구로 사용**(crew_factory.py:14-31) → T07 claude-skills(find_helpful_skills·read_skill_document)·T08 computer-use(run_shell 등)

#### X04 process-gpt-crewai-deep-research@49e2b12
- 역할: CrewAI 매칭·계획·보고서·폼·슬라이드 크루(crews/*). 자체 폴링 RPC crewai_deep_fetch_pending_task(_dev), function.sql:51,155 agent_orch='crewai-deep-research'. RPC fetch_done_data·save_task_result. 포트 8000(main.py:77)
- 도구: 자체 safe_tool_loader(agent-utils 이전 사본) mem0·memento·image_gen + tenants.mcp(core/database.py:313-314; tools/safe_tool_loader.py:10,40-63). memento POST/GET {MEMENTO_SERVICE_URL 기본 http://memento-service:8005}/retrieve(tools/knowledge_manager.py:32,193), mem0 컬렉션 memories(knowledge_manager.py:98,114)
- DB: users(is_agent 에이전트 전체·프로필, core/database.py:199-275), todolist, tenants, form_def, events, document_images

#### X05 process-gpt-langchain-react@16e1f38 (구형)
- 역할: 구형 SDK(`processgpt_agent_sdk.server`, executor= / agent_orch= 인자) 기반 ReAct. **agent_orch=`langchain-react`** — A02 base-agent-langchain-react와 같은 값으로 폴링(langchain_react/server.py:309-312 vs base-agent server.py:47) → 둘 다 떠 있으면 같은 큐를 나눠 가짐
- MCP: 고정 stdio `uvx mcp-python-code-interpreter --dir PGPT_WORK_DIR`(server.py:133-142) + 이미지 생성 도구. tenants.mcp·스킬·memento 미사용. 헬스 포트 8000(main.py:33)

#### X06 process-gpt-browser-use@6aeaa42
- 역할: browser-use + Playwright 브라우저 자동화. SDK agent_type=AGENT_ORCH 기본 `browser-automation-agent`(processgpt_browser_server.py:49,140-142). SDK가 이 agent_orch일 때만 env 표(key='browser_use', tenant_id)에서 sensitive_data(로그인 정보)를 실어 줌(agent-sdk database.py:190-197)
- DB·저장: form_def(browser_use_agent_executor.py:220), Storage 버킷 browser_use(녹화, :124). 저장소 안에 자체 Supabase 스키마·get_next_task 함수(supabase/init/01-init-schema.sql:214-232)와 단독 실행용 서버 변형(processgpt_browser_server_standalone.py 등)

#### A09 process-gpt-react-voice-agent@999ca2b
- 역할: OpenAI Realtime(wss://api.openai.com/v1/realtime, gpt-realtime; langchain_openai_voice/__init__.py:18-19) 음성 ReAct. Starlette WebSocket 서버 포트 3000(server/app.py 끝). 폴링 없음
- 도구(server/tools.py): proc_def·proc_def_arcv·form_def·bpm_proc_inst·todolist·configuration(organization)·chats·users를 Supabase에서 **읽기만**(server/database.py:62-635). 프로세스 시작·completion 호출 없음

#### D04 process-gpt-agents.github.io@cdc78f0
- 역할: 소개·마켓플레이스 정적 사이트(Vue). 외부 호출은 formspree 문의 폼(src/views/sections/ContactFormModal.vue:162)뿐. 템플릿은 샘플 데이터("나중에 supabase 연동", marketplace/PopularTemplates.vue:26). 런타임 상호작용 없음

## 부록 C — S3 온톨로지·데이터·전략·분석

작성 2026-10-08. 읽기 전용 조사(레포 수정 없음). 근거는 `레포@커밋 파일:줄`. 확인 못 한 고리는 "미확인".
조사한 클론: `/tmp/claude-0/refs/<repo>` (ontologic 서브모듈 중 비어 있던 것은 같은 위치에 새로 클론).

| 레포 | 커밋(날짜) | 비고 |
|---|---|---|
| ontologic | e72adf1 | 서브모듈 포인터: data-fabric af48f15, domain-layer 2e88db1, neo4j-text2sql 33401a6, robo-data-catalog 96ba7d3, robo-data-glossary b6fac84, agent-scheduler 8196e5c, node-local 8043aae, antlr-code-parser 86672b5, process-gpt-bpmn-extractor c7992ce, ontology-studio 6a229be |
| ontology-studio | 20afcde (2026-10-08) | 최상위 클론(서브모듈 6a229be보다 새것) |
| ontologic/data-fabric (jinyoung/robo-data-fabric) | af48f15 | |
| neo4j-text2sql | 25ab12a (2026-05-13) | ontologic 포인터 33401a6(2026-03-11)보다 새것 |
| robo-insight-domain-layer | 11de767 (2026-04-09), 포인터 2e88db1도 확인 | |
| robo-data-catalog | cf41148 (2026-09-22) | |
| robo-data-analyzer | 3039549 (2026-09-22, main) | .gitmodules는 `branch = refactor` 지정 — 공개 원격에 refactor 브랜치 없음 |
| ontologic/robo-data-glossary | b6fac84 | |
| robo-data-security-guard (= data-secure-guard) | a3b7707 | |
| robo-data-agent-scheduler | 8196e5c | |
| robo-node-local-agent-scheduler | 8043aae | |
| antlr-code-parser | 86672b5 | |
| ontologic/api-gateway, data-platform-olap, what-if-simulator | e72adf1 (ontologic 본체 폴더) | |
| robo-data-frontend, robo-data-platform(=infra) | — | 비공개(클론 거부) → 미확인 |

### 0. 결론 먼저

1. **ProcessGPT 본체(vue3·completion·gateway·infra-docker·k8s)에서 ontology-studio·ontologic 서비스로 가는 런타임 호출은 코드에 0건이다.** process-gpt `.gitmodules`에 `services/ontology-studio`가 등록돼 있을 뿐이다(process-gpt@6084127 `.gitmodules:61-63`). vue3 vite 프록시, infra-docker compose, nginx에 ontology-studio·data-fabric·text2sql·domain-layer 경로가 없다. 두 플랫폼은 **두 개의 다른 그래프**를 쓴다. ontologic 쪽은 Neo4j 카탈로그·온톨로지 그래프이고, ProcessGPT 쪽은 Supabase Postgres 안의 Apache AGE 그래프다.
2. **ontologic → ProcessGPT 방향은 있다.** 감시(watch) 계열이 조건을 만족하면 ProcessGPT 프로세스를 MCP로 실행한다: agent-scheduler → `pipx run process-gpt-mcp`(stdio MCP, Supabase) `execute_process`. text2sql 이벤트 규칙 → `uvx work-assistant-mcp`. node-local-agent-scheduler → agent-scheduler `/profiles/processgpt/execute`. ProcessGPT로 들어가는 문은 이것뿐이다.
3. **ontologic 안의 축은 공유 Neo4j다.** data-fabric이 카탈로그(`:DataSource/:Schema/:Table/:Column`)를 쓰는 **유일한 writer**다. text2sql·domain-layer·ontology-studio·data-platform-olap·security-guard가 그것을 읽는다. 실데이터는 text2sql `POST /text2sql/direct-sql`(→MindsDB)로만 읽는다.
4. **메타데이터 보강(robo-data-catalog/analyzer) → 온톨로지 고리는 공개 코드에서 끊겨 있다.** analyzer·catalog는 대문자 라벨 `TABLE/COLUMN/PROCEDURE`(코드 분석 그래프)에 description·FK를 쓴다. 반면 ontology-studio가 읽는 `Table.description`은 data-fabric의 `:Table`이다. 둘을 잇는 `catalog_projection.py`(ontologic spec 008:220)는 공개 analyzer main에 없다 → 미확인.
5. **AGE 그래프는 둘이다.** strategy 서비스가 실제로 쓰는 그래프의 기본 이름은 `corp_ontology`다(strategy@1db85d3 `app/config.py:34`). 과업 문구의 `process_gpt` 그래프는 vue3 `ontology/` 스키마 패키지와 읽기 RPC에만 있고, **그 그래프에 쓰는 동기화 코드(백필 ETL, outbox 워커, strategy pull 워커)는 로드맵**이다(vue3@a4f0a85 `ontology/README.md` "다음 단계"). vue3 RPC 주석이 지목한 writer `scripts/seed-ontology-graph.mjs`도 저장소에 없다.
6. ontology-studio → domain-layer `POST /whatif/analyze-matrix`(인과 분석 위임)는 ontology-studio 코드에 있다. 그러나 **공개 domain-layer(main 11de767, 포인터 2e88db1 모두)에 그 엔드포인트가 없다** → 상대편 미공개.

### 1. 서비스 표

포트는 코드 기본값이다. 실행 문서·게이트웨이 값이 다르면 함께 적는다. "나가는/들어오는"의 번호는 2절 연결 번호다.

#### 1-A. ontologic 플랫폼 (O02, 별도 플랫폼)

| 서비스 | 한 줄 역할 | 포트·주소 환경변수 | 나가는 호출 | 들어오는 호출 |
|---|---|---|---|---|
| **ontology-studio** (O01) | 온톨로지 설계·인스턴스 적재·가상 클래스 바인딩·답변/구축 에이전트·MCP 표면 | `BACKEND_PORT` 8000(installation.md 실측 8010), `MCP_PORT` 8100(`/mcp`, 읽기 전용), `/mcp/agent-bridge`(쓰기 포함, 모드별), `NEO4J_URI` 7687, `DATAFABRIC_BASE_URL` 8004, `TEXT2SQL_BASE_URL` 8020, `DOMAIN_LAYER_URL`/`WHATIF_API_URL` 8001, `OLLAMA_BASE_URL` 11434, `ER_RERANK_URL` 8095, `ONTOLOGICAL_ADMIN_DEV/PROD_URL` 7481/7482 | N01~N13 | 외부 MCP 클라이언트(Claude Code·Codex 등, 사람이 설정), 자체 프론트(5173). ProcessGPT 쪽 호출자 없음 |
| **data-fabric** (jinyoung/robo-data-fabric) | 데이터소스 등록(MindsDB + Neo4j), 소스 DB introspect → Neo4j 카탈로그 적재, MindsDB 질의 대리 | 8004(installation.md), `NEO4J_URI`, `MINDSDB_URL`/`MINDSDB_HOST`:`MINDSDB_API_PORT` 47334, `MINDSDB_REPLACE_LOCALHOST` | N14~N17 | ontology-studio(N01,N02), robo-data-catalog(N24), api-gateway(N46) |
| **neo4j-text2sql** | NL→SQL(ReAct), `direct-sql` 실행 관문(가드·행 상한), 카탈로그 메타 조회, 감시 이벤트 규칙 | `API_PORT` 8000(installation 실측 8020), `TARGET_DB_*` = MindsDB MySQL 47335, `NEO4J_URI`, `CEP_SERVICE_URL` 8088, 라우터 접두사 `/text2sql` | N18~N22 | ontology-studio(N03,N04), domain-layer(N25~N27), agent-scheduler(N36), api-gateway |
| **domain-layer** (robo-insight-domain-layer) | 문서/스키마 → 온톨로지 생성(LLM·결정적), ObjectType·Behavior·What-if 시뮬레이션·인과 분석, Agents.md 저장 | `PORT` 8002(installation 실측 8001, 게이트웨이 8002), `NEO4J_URI`, `TEXT2SQL_URL` 8000, `PDF2BPMN_URL` 8001, `MINDSDB_HOST`, `POSTGRES_*`, `REDIS_URL` | N25~N31 | ontology-studio(N05), agent-scheduler(N37), node-local scheduler(N39), api-gateway |
| **robo-data-catalog** | 코드 분석 그래프(`TABLE/COLUMN/PROCEDURE`)의 설명·FK 추론·리니지·샘플 문맥 API | `PORT` 15503(게이트웨이 5503), `NEO4J_URI`, `DATA_FABRIC_URL`, 접두사 `/robo` | N23, N24 | robo-data-analyzer(N32), api-gateway |
| **robo-data-analyzer** | 레거시 소스(DDL·프로시저·코드) 분석 → 제품 그래프 적재, 의미 검색, MCP `robo-cluster` | 15502(게이트웨이 5502), `ROBO_NEO4J_*`, `ROBO_CATALOG_BASE_URL`, `ROBO_DATA_DIR`, MCP `/robo/mcp/` | N32~N34 | api-gateway, 외부 MCP 클라이언트(아키텍트 `.mcp.json` 주석) |
| **antlr-code-parser** | ANTLR 파서 + LLM 수리. 산출물을 형제 `data/` 폴더에 쌓음 | 8081(start script) | N35(파일 공유) | api-gateway `/antlr/**` |
| **robo-data-glossary** | 용어집·영업일 달력 (Neo4j `Glossary/Term/BusinessCalendar`) | `PORT` 5504, `NEO4J_URI` | Neo4j 쓰기 | api-gateway `/robo/**` |
| **robo-data-security-guard** (data-secure-guard) | RBAC API(8006) + Go MySQL wire 프록시(3306, MindsDB 앞단) | `API_PORT` 8006, `MINDSDB_HOST/PORT` 47335, `NEO4J_URI` | N40, N41 | api-gateway `/api/security/**` |
| **agent-scheduler** (robo-data-agent-scheduler) | 감시 프로필 주기 실행(LangGraph): SQL 감시 → 조건 → ProcessGPT 프로세스 실행 | 8089(게이트웨이), `NEO4J_URI`, `TEXT2SQL_BASE_URL`(접두사 포함), `SUPABASE_URL/ANON_KEY/USER_JWT/TENANT_ID`, domain-layer 8002 하드코딩 | N36~N38 | node-local scheduler(N39b), api-gateway |
| **node-local-agent-scheduler** | `:Table:ObjectType` 노드의 `agentMdContent`(Agents.md)를 폴링해 DeepAgent 하위 프로세스로 실행 | `API_PORT` 8091, `NEO4J_URI`, `DOMAIN_LAYER_URL` 8002, `AGENT_SCHEDULER_URL` 8089 | N39, N39b | api-gateway |
| **api-gateway** (Spring Cloud Gateway) | ontologic 서비스 경로 라우팅 | 9000 | N46(라우트 표) | robo-data-frontend(비공개, 미확인) |
| **data-platform-olap** (AI Pivot Studio) | Mondrian 피벗·NL 질의, Neo4j 카탈로그로 ETL 설계, Airflow | 8002(start script) / 8007(게이트웨이), `neo4j_uri`, `AIRFLOW_HOST` 8080, `OLTP_DB_*` | N42, N43 | api-gateway `/olap/**` |
| what-if-simulator (ontologic 폴더) | 환율→KPI 인과 시뮬레이션 프로토타입 | 8001(run_api.py) / 게이트웨이 8005 | N44 | api-gateway `/whatif/**` |
| ontological-db / -enterprise-custom (O03/O04) | Postgres 확장형 Cypher 그래프 DB + Bolt 게이트웨이(Neo4j 드라이버 호환) | Bolt `OG_BOLT_LISTEN` 7687, PG 28816, portal 7474 | — | ontology-studio(N11, Bolt로 Neo4j 대체) |
| robo-data-frontend, infra(robo-data-platform) | — | 3000(start script) | 미확인(비공개) | — |

#### 1-B. ProcessGPT 쪽 S3 서비스

| 서비스 | 한 줄 역할 | 포트·주소 환경변수 | 나가는 호출 | 들어오는 호출 |
|---|---|---|---|---|
| **process-gpt-strategy** (P03) | BSC 전략맵·KPI·실행과제 CRUD, KPI 자동 측정, 설문 워크아이템, 플랫폼 원천 → AGE 온톨로지 동기화, 기여도·영향 분석 | 컨테이너 8000 → 호스트 8014(infra), `DB_*`, `GRAPH_DB_*`(기본 DB_* 상속), `GRAPH_STORE=age`, `GRAPH_NAME=corp_ontology`, `SKILLS_API_URL`, `OPENAI_*` | N50~N56 | vue3(N57), deepagents 전략 도구(N58), agent-feedback(N59), analytic(N62) |
| **process-gpt-strategy-skill** (D02) | BSC 인터뷰 스킬(SKILL.md). 서버 없음 | — | 도구 이름으로 strategy 저장 요구(N58 경유) | deepagents 시스템 스킬로 이미지에 동봉(N60) |
| **process-gpt-analytic** (P01) | OLTP(Supabase) → `dw` 스타 스키마 ETL, 대시보드·타임라인·NL 질의, 기여도 대시보드 | 8000 → 호스트 8009(infra), vue3 dev 프록시 8899, `DB_*`, `STRATEGY_SERVICE_URL` 8014, `AGENT_FEEDBACK_SERVICE_URL` 6789 | N61~N63 | vue3 `/api/analytics`(N64) |
| **process-gpt-instance-classifier** (P02) | 완료 인스턴스 임베딩·HDBSCAN 군집 → VOC 토픽, 유사 인스턴스 | 8000 → 8013, `DB_*`, `SUPABASE_URL/KEY`, `EMBEDDING_*`, `POLLING_INTERVAL` | N65, N66 | vue3 `/instance-classifier/`(N67) |
| **process-gpt-bpmn-extractor** (T02, ontologic에도 서브모듈) | 문서(PDF·docx·이미지) → BPMN/DMN/폼 추출. agent-sdk 폴링 워커 + 그래프 조회 API | 워커 8012(infra), API `run.py api` 기본 8000, `MEMENTO_BASE_URL` 8005, `AGE_DSN`·`AGE_GRAPH_NAME=pdf2bpmn`, `NEO4J_*`(호환 이름만) , `SUPABASE_*` | N70~N74 | process-gpt-mcp `create_pdf2bpmn_workitem`(N75), domain-layer(N28) |
| **bpmn-process-generation-skill** (D01) | 컨설팅→프로세스 정의 JSON→스킬·DMN·폼 생성 스킬 + `save_to_supabase.py` | — | N76, N77 | deepagents 시스템 스킬 동봉(N60) |
| **process-gpt-visionparser** (T05) | VLM OCR + LangExtract 구조화 추출 워커 | agent-sdk 폴링(`agent_type="visionparse"`), `SUPABASE_URL/ANON_KEY/STORAGE_BUCKET`, `REDIS_URL` | N78, N79 | vue3 프로세스 시작·워크아이템(N80) |
| **process-gpt-glossary** (T06) | robo-data-glossary를 Supabase Postgres로 옮긴 standalone 용어집 | 5504, `SUPABASE_DB_*`, `SUPABASE_URL` | N81 | nginx `/robo/`(N82). vue3는 자체 `glossary_terms`를 쓰므로 실제 호출자는 미확인 |
| process-gpt-knowledge-graph (O05) | README만 있음(2024-02-15) | — | — | — |
| **process-gpt-sample-app-wms** (D05) | WMS 데모(Supabase `wms` 스키마·RPC) + `wms-mcp` | MCP 8199(`/mcp`), 프론트 5273, `SUPABASE_*` | N85 | ProcessGPT 폴링 실행체가 `tenants.mcp`를 읽어 접속(N86) |

### 2. 연결 목록 (출발 → 도착, 방식, 근거)

레포 약칭과 커밋: OS=ontology-studio@20afcde, DF=ontologic/data-fabric@af48f15(`backend/app/` 아래), T2S=neo4j-text2sql@25ab12a, DL=robo-insight-domain-layer@11de767, CAT=robo-data-catalog@cf41148, ANA=robo-data-analyzer@3039549, GLO=ontologic/robo-data-glossary@b6fac84, SEC=robo-data-security-guard@a3b7707, ASCH=robo-data-agent-scheduler@8196e5c(`app/` 아래), NLAS=robo-node-local-agent-scheduler@8043aae, ONT=ontologic@e72adf1(api-gateway·data-platform-olap·what-if-simulator·docs), STR=process-gpt-strategy@1db85d3(`app/` 아래), ANL=process-gpt-analytic@a6dbb1a(`backend/app/` 아래), CLS=process-gpt-instance-classifier@384a6ff, BEX=process-gpt-bpmn-extractor@c7992ce, BGS=bpmn-process-generation-skill@f8c4b6d, SSK=process-gpt-strategy-skill@f4d050d, VP=process-gpt-visionparser@8cf53d3, PGG=process-gpt-glossary@6a29cd9, WMS=process-gpt-sample-app-wms@8ba09f4. 경계 밖: VUE=process-gpt-vue3@a4f0a85, INF=process-gpt-infra-docker@9e85485, DA=process-gpt-deepagents@faedeaa, PGM=process-gpt-base-agent-langchain-react@e566a60 `process-gpt-mcp/src/process_gpt_mcp/server.py`, AF=process-gpt-agent-feedback@84d2a0e, CMP=process-gpt-completion@b272c9a, SDK=process-gpt-agent-sdk@4d8f3b6, PG=process-gpt@6084127.

#### 2-A. ontology-studio

| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| N01 | OS → DF | HTTP GET `/api/datasources`, `/{name}`, `/{name}/health`, `/{name}/schemas`, `/{name}/tables`, `/{name}/tables/{t}/schema`, `/{name}/tables/{t}/sample` (TTL 캐시 300초) | OS `backend/src/modules/ontology/datafabric_client.py:194,204,213,234,254,295,309`, `backend/src/shared/kernel/settings.py:203-205`; 과업 확인분 `ontology/tools.py:1014` datasource_list |
| N02 | OS → DF → MindsDB | HTTP POST `/api/query` (MindsDB view 관리 statement) | OS `ontology/datasource_exec.py:762` |
| N03 | OS → T2S | HTTP POST `/text2sql/direct-sql` (가상 클래스 behavior가 실제 SQL로 확장돼 실행. 행 상한 `DATASOURCE_MAX_ROWS` 500) | OS `ontology/datasource_exec.py:559`, `settings.py:211-219` |
| N04 | OS → T2S | HTTP GET `/text2sql/meta/tables/{t}/columns` (컬럼 조회. 실패 시 DF `/tables/{t}/schema`로 폴백) | OS `ontology/datafabric_client.py:284,295` |
| N05 | OS → DL | HTTP POST `/whatif/analyze-matrix` (전략 2 인과 발견. 통계는 위임하고 온톨로지 쓰기는 OS가 단독으로 함) | OS `ontology/causal_client.py:25-40,93`, `settings.py:224-231`; ONT `specs/003-ontology-build-strategies/tasks.md:128`. **DL 공개 코드에 엔드포인트 없음** |
| N06 | OS → Neo4j(카탈로그 읽기) | Bolt Cypher: `MATCH (t:Table)…(c:Column)`, `REFERENCES`/`FK_TO_TABLE` (테이블 → 클래스 결정적 생성) | OS `ontology/schema_ontology.py:112,132,141,160` |
| N07 | OS → Neo4j(온톨로지 쓰기) | Bolt: `MERGE (n:_Entity:<Class>)` 인스턴스, `Document`/`Chunk` 문서 색인. 스키마·바인딩·behavior는 SQLite | OS `ontology/tools.py:552,688`, `ontology/tools.py:401`(sqlite 스키마) |
| N08 | OS → Ollama | HTTP POST `/api/embed` (임베딩) | OS `ontology/embedding.py:80` |
| N09 | OS → reranker(자체 `services/reranker`) | HTTP POST `{ER_RERANK_URL}/rerank` 8095 | OS `ontology_runtime/entity_resolution.py:41,115` |
| N10 | OS → Ontological 관리 API(dev 7481 / prod 7482) | HTTP `/api/schema-snapshot`, `/api/schema-changes`, `/api/releases`, `/api/release/export·plan·apply`, `/api/timeline`, `/api/schema-change` | OS `ontological_admin/client.py:7-20`, `release/api.py:101-183`. **서버 구현은 ontological-db 두 레포 어디에도 없음** → 미확인 |
| N11 | OS → ontological-db | Bolt(같은 Neo4j 드라이버로 URI만 바꿈). 서브모듈 `ontological-db` | OS `.gitmodules`, `docker-compose.ontological.yml:28-45`, `.env.example`(NEO4J_URI 설명); ontological-db@3179cc7 `bolt/README.md` |
| N12 | OS → cliagents(외부 CLI: claude-code·codex) → OS `/mcp/agent-bridge` | 라이브러리 호출 + MCP(streamable-http). `AGENT_BACKEND=cliagents`일 때만 | OS `agent_session/cliagents_backend.py:28`, `agent_bridge_mcp/server.py:29`, `agent_bridge_mcp/router.py:26-33` → **S2 cliagents(A06)** |
| N13 | OS backend → OS mcp 컨테이너 | MCP http `http://mcp:8100/mcp` (답변 모드·board 도구가 MCP를 거침. 카탈로그 라벨 차단·PII 제거) | OS `docker-compose.yml:56-62` |

#### 2-B. data-fabric · text2sql · domain-layer

| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| N14 | DF → Neo4j(카탈로그 쓰기, 유일 writer) | Bolt `MERGE (:DataSource)`(평문 자격증명 포함), `:Schema`·`:Table`·`:Column`·`[:REFERENCES]` | DF `services/neo4j_service.py:68`, `services/schema_introspection.py:985-1063`; ONT `docs/catalog-schema.md` "누가 쓰고 누가 읽는가" |
| N15 | DF → MindsDB | HTTP `/api/sql/query`, `/api/databases/` (데이터소스 등록·질의) | DF `services/mindsdb_service.py:31,166` |
| N16 | DF → 원천 DB | 직접 접속(asyncpg / psycopg2 / MySQL)으로 introspect | DF `services/schema_introspection.py:281-293`, `routers/datasources.py:552` `extract-metadata-sync` |
| N17 | DF 등록 순서 | `POST /api/datasources?register_to=both`: Neo4j 노드 먼저, 다음 MindsDB(연결 검증은 MindsDB) | DF `routers/datasources.py:247-275` |
| N18 | T2S → MindsDB | MySQL wire 47335(`TARGET_DB_*`) | T2S `app/config.py:36-44` |
| N19 | T2S → Neo4j | 부팅 때 제약·벡터 인덱스 생성, 카탈로그 읽기, `Table.text_to_sql_*` 벡터 쓰기, `Query/QueryTemplate/ValueMapping/Feedback` 노드 | T2S `app/core/neo4j_bootstrap.py:85-92`, `app/core/text2sql_table_vectorizer.py:345` |
| N20 | T2S(이벤트 규칙) → ProcessGPT "work-assistant" MCP | stdio MCP `uvx work-assistant-mcp`(env SUPABASE_URL/ANON_KEY), 도구 `search_processes`, `execute_process` | T2S `app/core/mcp_client.py:4-18,287-289,322,373`, `app/routers/events.py:460-480,980` → **S2**(`work-assistant-mcp` 패키지 소스는 어느 클론에도 없음. 같은 계열 PGM에는 `search_processes`가 없다 → 미확인) |
| N21 | T2S → CEP 서비스 | HTTP `{CEP_SERVICE_URL}`(8088) `/api/rules*`, `/api/events/send*` | T2S `app/core/cep_client.py:20,74-146`. 대상 레포 미확인(8088은 ProcessGPT nginx 포트와 겹침) |
| N22 | T2S → LLM·임베딩 | OpenAI 호환·OpenRouter·Google | T2S `app/core/llm_factory.py:286-376` |
| N25 | DL → T2S | HTTP GET `/text2sql/meta/datasources`, `…/schemas`, `…/tables`, `/text2sql/meta/tables/{t}/columns` | DL `app/services/datasource_service.py:24,66`, `app/routers/whatif.py:92-107`, `app/services/data_source_linker.py:143` |
| N26 | DL → T2S | HTTP POST `/text2sql/ask` (자동 데이터소스 링크) | DL `app/services/data_source_linker.py:430` |
| N27 | DL → T2S | HTTP POST `/text2sql/direct-sql`(인스턴스 조회·피처 뷰), `/execute-ddl`(MV) | DL `app/services/instance_fetcher.py:88`, `data_source_linker.py:569`, `feature_view_builder.py:546`, `materialized_view_service.py:92`. `/execute-ddl`은 T2S 라우터에 없음 → 결함 의심 |
| N28 | DL → BEX(PDF2BPMN API) | HTTP `/api/health`, `/api/upload`, `/api/process/{job}`, `/api/jobs/{job}`, `/api/processes`, `/api/files/bpmn/content` (문서 → 프로세스 레이어 온톨로지) | DL `app/config.py:71`, `app/services/bpmn_client.py:146-332`, 호출부 `app/services/schema_generator.py:573-599` |
| N29 | DL → Neo4j | 카탈로그 읽기(`schema_extractor`) + 자체 온톨로지 쓰기(`OntologySchema`, `OntologyType`, `OntologyNode`, `OntologyBehavior`, `Behavior`, `Instance`, `WhatIfScenarioProfile`) + ObjectType에 `agentMdContent` | DL `app/services/neo4j_service.py:58`, `app/services/schema_store.py:351`, `app/routers/ontology.py:7598-7658` |
| N30 | DL → MindsDB | HTTP 47334 `/api/sql/query` (What-if 예측 모델 학습·예측) | DL `app/services/whatif/mindsdb_model_factory.py:32-36`, `app/routers/whatif.py:746` |
| N31 | DL → 외부 | Tavily 검색, Postgres(asyncpg), Redis LLM 캐시 | DL `app/services/web_search.py:14`, `app/routers/ontology.py:1462`, `app/services/llm_cache.py:89-95` |

#### 2-C. robo-data-catalog · analyzer · antlr · glossary · security · OLAP

| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| N23 | CAT → Neo4j | Bolt: 대문자 라벨 `TABLE/COLUMN/PROCEDURE`에 `description` 쓰기, `[:FK]` 추론 관계(`confidence`·`overlap_ratio`), 리니지(`READS`) | CAT `graph/schema_commands.py:111-146`, `enrichment/description.py:201-237`, `enrichment/foreign_keys.py:24-35` |
| N24 | CAT → DF | HTTP `/api/query`, `/api/query/status`, `/api/datasources/{ds}/tables`, 테이블 스키마 (샘플 행으로 FK 추론·설명 보강) | CAT `integrations/data_fabric.py:16-18,66,106,246`, `shared/config/settings.py:89` |
| N32 | ANA → CAT | HTTP GET `/robo/tables/discovery`, POST `/robo/tables/sample-context`, `/robo/tables/resolve-context` | ANA `integrations/catalog_client.py:70,96`, `pipeline/stages/ddl/discover_datasource_step.py:44`, `shared/config/app_settings.py:280` |
| N33 | ANA → Neo4j | Bolt: 제품 그래프 `MERGE (node:{label} {_id})`(TABLE·COLUMN·PROCEDURE…), `[:FK]` 등 | ANA `graph/product_writer.py:100-136`, `pipeline/publication/product_graph.py:215`, `shared/config/app_settings.py:225` (`ROBO_NEO4J_URI`) |
| N34 | 외부 MCP 클라이언트 → ANA | MCP streamable-http `/robo/mcp/` (`robo-cluster`: `cluster_retrieve`, `node_detail`) | ANA `api/mcp_app.py:1-30` |
| N35 | antlr-code-parser ↔ ANA | 파일 공유(형제 `data/` 폴더에 source/ddl/analysis) | ANA `shared/config/app_settings.py:354-357` |
| N40 | SEC(Go 프록시) → MindsDB | MySQL wire 47335 | SEC `internal/config/config.go:47-50` |
| N41 | SEC → Neo4j | `User/Role/AccessRule/AuditLog` + `[:CAN_ACCESS]→(:Table)` (**카탈로그 `:Table`을 읽음**. 헌법은 "직접 읽지 않음"이라 적었다) | SEC `internal/authz/policy_engine.go:346,377`, `api/routers/tables.py:16-17` |
| N42 | OLAP → Neo4j | `:Table`·`:Column`·`[:FK_TO_TABLE]` 읽기(ETL 설계) | ONT `data-platform-olap/backend/app/services/neo4j_client.py:78,112,127` |
| N43 | OLAP → Airflow, OLTP Postgres | HTTP `AIRFLOW_HOST` 8080, psycopg | ONT `data-platform-olap/backend/app/services/airflow_service.py:21-23,103-107` |
| N44 | what-if-simulator → Neo4j, MindsDB | Bolt, HTTP 47334 | ONT `what-if-simulator/config.py:54-62`, `ontology_loader.py:16` |
| N45 | GLO → Neo4j | `Glossary/Term/Domain/Owner/Tag/BusinessCalendar` | GLO `config/settings.py:16-18` |

#### 2-D. 감시·스케줄러 (ontologic → ProcessGPT 실행 문)

| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| N36 | ASCH → T2S | HTTP POST `{TEXT2SQL_BASE_URL}/direct-sql`(감시 SQL), `/watch-agent/profiles/{id}/record-execution` | ASCH `integrations/text2sql_client.py:37,77`. `record-execution`은 T2S `watch_agent.py`에 없음 → 결함 의심 |
| N37 | ASCH → DL | HTTP GET `/whatif/scenarios`, `/whatif/scenarios/{id}`, POST `/whatif/scenarios/{id}/run` (기본 8002 하드코딩) | ASCH `integrations/whatif_client.py:13,45,60,86` |
| N38 | ASCH → ProcessGPT | stdio MCP `pipx run process-gpt-mcp`(env SUPABASE_URL·ANON_KEY·USER_JWT·TENANT_ID): `get_process_list`, `get_process_detail`, `execute_process`. Supabase REST 직접 호출은 안 함 | ASCH `integrations/processgpt_mcp_client.py:34,55-58,408,430`, `integrations/processgpt_client.py:1-6`, `env.example` → **S2 process-gpt-mcp** (PGM `server.py:1204,1246,1402`) → Supabase `todolist`/`bpm_proc_inst` |
| N38b | ASCH → Neo4j | `WatchAgentProfile`, `WatchAgent`, `AgentStep` 읽기·쓰기 | ASCH `integrations/neo4j_client.py` (라벨 grep) |
| N39 | NLAS → Neo4j / DL | `:Table:ObjectType`의 `agentMdContent`·`agentEnabled` 폴링(30초). 하위 프로세스(deepagents CLI)가 DL `POST /ontology/object-types/{t}/visual-effects`, `GET …/data`, `POST …/execute-query` 호출 | NLAS `README.md` "Neo4j Property Contract", `app/runner/run_deepagent.py:28,61-99,125,134`. Agents.md 작성 쪽은 DL `routers/ontology.py:7598-7658`. `execute-query`는 DL에 없음 → 결함 의심 |
| N39b | NLAS → ASCH | HTTP `/profiles/processgpt/processes`, POST `/profiles/processgpt/execute` | NLAS `app/runner/run_deepagent.py:140,164,174`; ASCH `routers/profiles.py:862,899` |
| N46 | api-gateway(9000) → 각 서비스 | Spring Cloud Gateway 라우트: `/api/gateway/data-fabric/**`→8004, `/api/gateway/text2sql/**`·`/text2sql/**`→`ROBO_TEXT2SQL_URL`, `/api/gateway/ontology/**`·`/ontology/**`→8002(domain-layer), `/api/gateway/domain-whatif/**`→8002 `/whatif`, `/api/gateway/whatif/**`·`/whatif/**`→8005, `/api/gateway/agent-scheduler/**`→8089, `/api/gateway/node-agent-scheduler/**`→8091, `/api/security/**`→8006, `/robo/analyze/**`→5502, `/robo/glossary/**`·`/robo/business-calendar/**`→5503, `/robo/**`→5504, `/olap/**`→8007, `/architect/**`→8001, `/risk-calculator/**`→8003, `/**`→3000. **ontology-studio 라우트는 없다**(헌법 VI: 30초 타임아웃 때문에 게이트웨이를 거치지 않음) | ONT `api-gateway/src/main/resources/application.yml:46-354` |

#### 2-E. ProcessGPT 쪽 S3

| # | 출발 → 도착 | 방식 | 근거 |
|---|---|---|---|
| N50 | STR → Supabase 원천 표(읽기) | SQL: `bpm_proc_inst`(KPI 실적), `todolist`(완료 워크아이템 집계), `proc_def`, `users`, `configuration`, `agent_skills`, `skills` | STR `measurement.py:4,144,160,183,250`, `ontology_sync.py:176,193,239,350,445,457,545,705` |
| N51 | STR → Supabase(쓰기) | `strategy_kpi_measurements`, `strategy_survey_requests`, `strategy_sync_state`, **`todolist` INSERT**(설문 워크아이템을 사람에게 배정) | STR `measurement.py:227`, `survey.py:36,111,169`, `ontology_sync.py:102` |
| N52 | STR → AGE 그래프 `corp_ontology` | `ag_catalog.create_graph`, Cypher MERGE: 전략층(Strategy/KPI…) + 원천 투영(Process/Task/User/Agent/Team/Skill, `CONTAINS_TASK/PERFORMS/USES_SKILL/INHERITS/REFERENCES/HAS_SUB_TEAM/MEMBER_OF`). 주기 `ONTOLOGY_SYNC_INTERVAL_SECONDS` 60 | STR `config.py:17-34`, `graph/age_adapter.py:58,145-183`, `ontology_sync.py:1-16` |
| N53 | STR → claude-skills | HTTP GET `{SKILLS_API_URL}/skills/list`, `/skills/{name}/files/SKILL.md` (스킬 관계 추출) | STR `ontology_sync.py:470-511` → **S2 process-gpt-claude-skills(T07)** |
| N54 | STR → 외부 기록 시스템 | HTTP GET `kpi.source_url` + JSON 경로 `source_field` (KPI 외부 측정) | STR `measurement.py:117-127` |
| N55 | STR → LLM | KPI↔프로세스 매핑, 설문 문항, 스킬 관계 추출, 전략 채팅 | STR `config.py:36-39`, `ai.py`, `chat.py` |
| N56 | STR ontology_agent → STR 자기 API | HTTP `STRATEGY_SELF_URL` | STR `ontology_agent/tools.py:23` |
| N57 | VUE → STR | HTTP `/strategy-service/api/*`(map, objectives, kpis, measurements, measure/run, ontology/graph, neighbors, contribution, impact, ai/suggest·alignment, import-bscard, surveys) | VUE `vite.config.ts:118-120`, `src/stores/strategy/strategyStore.ts:6-7`; INF `nginx/nginx.conf:158-161` |
| N58 | DA(전략 도구) → STR | HTTP `/api/objectives`, `/api/kpis`(PUT 포함), `/api/canvas/blocks`, `/api/map`, `/api/canvas`, `/api/ai/alignment`; `link_kpi_to_process` | DA `core/strategy/tools.py:23,43,70-458` (← **S2**) |
| N59 | AF → STR | HTTP POST `/api/ai/alignment` | AF `core/feedback_batch_manager.py:83,104` (← **S2**) |
| N60 | PG/DA ← SSK·BGS | git 서브모듈(`skills/bsc-strategy-interview`, `skills/bpmn-process-generation-skill`) + deepagents 이미지에 시스템 스킬로 동봉 | PG `.gitmodules:52-57`; DA `system-skills/process-gpt-system/{bsc-strategy-interview,bpmn-process-generation-skill}`, `core/skills/local_system_skills.py:11,30`; SSK `README.md`(설치 절) |
| N61 | ANL → Supabase OLTP → `dw` 스키마 | SQL ETL(60초): `public.todolist/bpm_proc_inst/proc_def/users/departments/usage/tenants` → `dw.dim_*`, `dw.fact_process_instance/fact_task/fact_event/fact_usage` | ANL `etl.py:1-6,51,660,879` |
| N62 | ANL → STR | HTTP GET `/api/map`, `/api/contribution/strategy/{id}`, `/api/impact/strategy/{id}` (기여도 대시보드) | ANL `contribution_dashboard.py:25,51,56,62` |
| N63 | ANL → AF | HTTP GET `/api/skills/{name}/contributors` | ANL `contribution_dashboard.py:26,68` → **S2** |
| N64 | VUE → ANL | HTTP `/api/analytics/*` → 8899(dev). infra는 8009 | VUE `vite.config.ts:92-95`, `src/services/analyticsApi.ts:8`; INF `docker-compose.yml:336-345` |
| N65 | CLS → Supabase | 읽기 `bpm_proc_inst`·`todolist`·`form_def`(폴링 10초), 쓰기 `voc_instances`(pgvector)·`voc_topics` | CLS `app/source_reader.py:1,42,59`, `sql/schema.sql:11,24,38` |
| N66 | CLS → 임베딩·LLM | OpenAI 호환(`EMBEDDING_BASE_URL`/`LLM_PROXY_URL`), 토픽 이름 짓기 | CLS `app/config.py:54-56`; INF `docker-compose.yml:504-530` |
| N67 | VUE → CLS | HTTP `/instance-classifier/` `proc-defs`, `toplist`, `topics/…/instances`, `similar`, `recluster` | VUE `vite.config.ts:110-111`, `src/utils/instanceClassifier.ts:8,39-75` |
| N70 | BEX 워커 ← agent-sdk 폴링 | `todolist`에서 `agent_orch="pdf2bpmn"` 작업을 가져감 | BEX `pdf2bpmn_agent_server.py:45,76,160-162` → **S1 agent-sdk(C07)** |
| N71 | BEX → memento | HTTP GET `/documents/chunks-with-embeddings` (청크·임베딩을 메멘토가 단일 원천으로 제공) | BEX `pdf2bpmn_agent_executor.py:2653,2668-2713`, `src/pdf2bpmn/config.py:39-43` → **S2 memento(T01)** |
| N72 | BEX → Supabase | `proc_def`·`form_def`·`configuration`·`users`·`agent_skills`·`tenants` 쓰기, HITL용 `todolist` 갱신 | BEX `pdf2bpmn_agent_executor.py:1012-1036` 외, `src/pdf2bpmn/hitl.py:244,310` |
| N73 | BEX → AGE 그래프(테넌트별, 기본 `pdf2bpmn`) | psycopg + AGE Cypher(이름은 `Neo4jClient`인 호환 클래스). infra는 `NEO4J_*`도 주입하지만 코드는 AGE | BEX `src/pdf2bpmn/config.py:44-54`, `src/pdf2bpmn/graph/neo4j_client.py:1,63-93`; INF `docker-compose.yml:364-402` |
| N74 | BEX → LLM·OCR | OpenAI(vision OCR)·Synap OCR | BEX `src/pdf2bpmn/config.py:21-30,77-88` |
| N75 | PGM `create_pdf2bpmn_workitem` → Supabase `todolist` | REST INSERT(`proc_def_id/agent_orch = "pdf2bpmn"`) → N70이 가져감 | PGM `server.py:1774,2014,2051` (← **S2**) |
| N76 | BGS → Supabase | `scripts/save_to_supabase.py`: `proc_def`(flattened)·`configuration`·`form_def`·`users`(agent)·`agent_skills`·`tenants.skills` upsert | BGS `scripts/save_to_supabase.py:4-9,259-264`, `scripts/README.md:13,59-61` |
| N77 | BGS(deepagents 실행 시) → STR | 지시문으로 `link_kpi_to_process` 호출 요구(실제 HTTP는 N58) | BGS `references/12-deepagents-execution.md:143` |
| N78 | VP ← agent-sdk 폴링 | `agent_type="visionparse"` | VP `main.py:21-23` → **S1** |
| N79 | VP → Supabase | Storage 업로드(JSONL·HTML), 이벤트 즉시 저장 | VP `executors/executor.py:21-23,110-117`, `pipelines/final_output_pipeline.py:93-104` |
| N80 | VUE → VP(간접) | 프로세스 시작·워크아이템에서 `visionparse` 에이전트를 고름 → todolist → N78 | VUE `src/shared/processStart/index.js:33`, `src/components/apps/todolist/WorkItem.vue:862,1560` |
| N81 | PGG → Supabase Postgres | `glossaries`·`terms`·`domains`·`owners`·`tags`·`business_calendars` 등(Neo4j판 robo-data-glossary를 옮긴 것) | PGG `backend/config/settings.py:22-45`, `supabase/init/10-app-schema.sql` |
| N82 | INF nginx → PGG | `/robo/` → `robo-data-glossary-backend:5504`(이미지 `process-gpt-glossary-backend`) | INF `nginx/nginx.conf:118-122`, `docker-compose.yml:150-152` |
| N85 | WMS `wms-mcp` → Supabase | RPC `wms_*`(재고·RFQ·PO·입고·품질·WCS) | WMS `mcp/wms_mcp/mcp_server.py:39-77,103-129` |
| N86 | WMS 설치 스크립트 → ProcessGPT Supabase | `tenants.mcp.mcpServers.wms` 병합, 에이전트(users) 1명, `proc_def`(wms_replenishment_process), 폼 3개 upsert. 실행 시 ProcessGPT 폴링 실행체가 `tenants.mcp`를 읽어 MCP 8199에 접속 | WMS `scripts/install_processgpt_integration.py:6-8,591-605,638`, `README.md`(4단계); 읽는 쪽 CMP `polling_service/database.py:2393-2412`, SDK `processgpt_agent_sdk/database.py:740` → **S1** |
| N87 | VUE → AGE 그래프 `process_gpt`(읽기 전용) | supabase-js `.rpc('ontology_graph_health' / 'ontology_business_graph' / 'ontology_execution_rollup')` | VUE `src/services/ontologyAgeGraphService.ts:51,79,108`, `supabase/migrations/20260710_ontology_explorer_rpc.sql:1-16`, `ontology/schema/00-init.sql:72-83`(outbox 표) |
| N88 | INF가 STR을 띄우는 방식 | `GRAPH_NAME`·`GRAPH_DB_*`를 주지 않음 → Supabase DB(`supabase/postgres:15.8.1.060`) 안의 `corp_ontology`. STR은 기동 때 AGE 확장이 없으면 `RuntimeError`로 **기동이 중단**된다. 따라서 이 compose 그대로면 strategy가 뜨지 않을 수 있다(결함 의심, 미실행) | INF `docker-compose.yml:537-556,829-831`; STR `main.py:76-81`, `graph/age_adapter.py:125-140`, `docker-compose.age.yml:1-11` |

### 3. 공유 저장소

#### 3-1. ontologic 공유 Neo4j (루트 `.env` 하나, 기본 bolt 7687 / installation 실측 7688)

비유: **도서관 목록 카드함 하나를 여러 부서가 같이 쓰는 것**과 같다. 카드는 data-fabric만 새로 만든다. 다른 부서는 카드를 읽기만 하거나, 자기 서랍(다른 라벨)에 따로 적는다.

| 라벨 묶음 | 쓰는 쪽 | 읽는 쪽 | 근거 |
|---|---|---|---|
| 카탈로그 `:DataSource`(평문 자격증명) `-[:HAS_SCHEMA]→:Schema-[:HAS_TABLE]→:Table-[:HAS_COLUMN]→:Column`, `[:REFERENCES]` | **data-fabric(유일 writer)** | text2sql, domain-layer, ontology-studio, data-platform-olap(`FK_TO_TABLE`도 읽음), security-guard(`CAN_ACCESS→:Table`) | ONT `docs/catalog-schema.md`, `.specify/memory/constitution.md` I~V; N06·N14·N41·N42 |
| `:Table`의 `text_to_sql_*` 벡터·프로파일, 제약·벡터 인덱스 | text2sql | text2sql. ontology-studio 참조 0건(spec 008:84) | N19 |
| 코드 분석 제품 그래프 `TABLE/COLUMN/PROCEDURE`(대문자), `[:FK]` 추론, `READS` 리니지, `description` | robo-data-analyzer(노드), robo-data-catalog(설명·FK·리니지) | robo-data-catalog, analyzer MCP | N23·N33. 접속 변수가 `ROBO_NEO4J_*`로 달라 **같은 DB인지는 배포에 달림**. spec 008:217-220에는 analyzer가 카탈로그 `:Table`에 함께 쓰다가 카탈로그를 지운 사고와 그 수정(`catalog_projection.py`)이 기록돼 있으나, 그 파일은 공개 main에 없음 |
| 온톨로지 인스턴스 `(:_Entity:<Class>)`, `Document`, `Chunk`(+ 벡터 인덱스 `entity_embedding_vector`, `chunk_embedding_vector`) | ontology-studio | ontology-studio, MCP 표면 | N07 |
| domain-layer 온톨로지 `OntologySchema/OntologyType/OntologyNode/OntologyBehavior/Behavior/Instance/WhatIfScenarioProfile`, `:Table:ObjectType.agentMdContent` | domain-layer, node-local(상태 `agentLast*`) | domain-layer, node-local-agent-scheduler | N29·N39 |
| `Glossary/Term/BusinessCalendar…` | robo-data-glossary | 같은 서비스 | N45 |
| `User/Role/AccessRule/AuditLog/SecurityPolicy` | security-guard | security-guard(Go 프록시 정책 엔진) | N41 |
| `WatchAgentProfile/WatchAgent/AgentStep` | agent-scheduler | agent-scheduler | N38b |

ontology-studio의 바인딩·behavior·스키마 그룹은 **SQLite**에 있다(헌법 IV). Neo4j를 지워도 남는다.
`ontology-studio`는 Neo4j 대신 **ontological-db**(Postgres 확장 + Bolt 게이트웨이)에 붙을 수 있다. 이때도 URI만 바뀐다(N11).

**사용자가 스스로 판정할 체크 질문**
- data-fabric이 꺼진 상태에서 ontology-studio가 테이블 → 클래스를 만들 수 있는가? (Neo4j 카탈로그가 이미 있으면 가능하다. 샘플·실행은 불가)
- `MATCH (t:TABLE) WHERE t.description IS NOT NULL`과 `MATCH (t:Table) WHERE t.description IS NOT NULL`의 개수가 같은가? 다르면 보강 결과가 온톨로지에 닿지 않는 것이다.

#### 3-2. ProcessGPT 쪽 Apache AGE 그래프 (Supabase Postgres 안)

비유: **같은 건물 안에 서로 다른 칠판이 두 개 걸려 있는 것**과 같다. strategy가 매일 쓰는 칠판(`corp_ontology`)이 하나 있다. 다른 하나(`process_gpt`)는 칸만 그려져 있고, 적어 넣는 사람(동기화 워커)은 아직 배정되지 않았다.

| 그래프 | 쓰는 쪽 | 읽는 쪽 | 근거 |
|---|---|---|---|
| `corp_ontology`(기본 `GRAPH_NAME`) — 전략(Objective/KPI/Initiative…) + 원천 투영 Process/Task/User/Agent/Team/Skill | **process-gpt-strategy**(60초 동기화 + 전략 CRUD) | strategy API → vue3 `StrategyBoard.vue`·`OntologyExplorer.vue`(`/strategy-service/api/ontology/graph`), analytic(N62) | N52·N57 |
| `process_gpt`(스키마 0.2.0, 노드 29·엣지 47) | 스키마·시드만 `ontology/schema/00~03.sql`. **런타임 writer 없음**(백필 ETL·`graph_project_proc_def()` 트리거·strategy pull 워커가 로드맵. `graph_sync_outbox` 표만 있음) | vue3 RPC 3종(N87) | VUE `ontology/README.md`, `ontology/ontology-spec.yaml:9-30` |
| 테넌트별 그래프(기본 `pdf2bpmn`) | process-gpt-bpmn-extractor | bpmn-extractor `/api/graph/*` | N73 |

#### 3-3. Supabase 표 (ProcessGPT 공용 DB)

| 표 | S3 쓰기 | S3 읽기 |
|---|---|---|
| `todolist` | strategy(설문 워크아이템), bpmn-extractor(HITL output), process-gpt-mcp(pdf2bpmn 워크아이템, S2) | strategy, analytic ETL, instance-classifier, agent-sdk 폴링(bpmn-extractor·visionparser, S1) |
| `bpm_proc_inst` | (S1 completion) | strategy KPI 측정, analytic ETL, instance-classifier |
| `proc_def`, `form_def`, `configuration` | bpmn-extractor, bpmn-process-generation-skill 스크립트, WMS 설치 스크립트 | strategy 동기화, analytic ETL, instance-classifier(`form_def`) |
| `users`, `agent_skills`, `skills`, `tenants`(`mcp`, `skills`) | bpmn-extractor, BGS 스크립트, WMS 설치 스크립트(`tenants.mcp`) | strategy 동기화, completion·agent-sdk(`tenants.mcp`, S1) |
| `strategy_*` (`kpi_measurements`, `survey_requests`, `sync_state`, `objectives`…) | strategy | strategy |
| `dw.*`(스타 스키마) | analytic ETL | analytic API |
| `voc_instances`(pgvector), `voc_topics` | instance-classifier | instance-classifier |
| `glossaries`, `terms`… | process-gpt-glossary | process-gpt-glossary |
| vue3 자체 `glossary_terms` | vue3 | vue3(`src/stores/glossary.ts:7`). process-gpt-glossary 표와 **별개** |
| `wms.*` + RPC | wms-mcp, wms-frontend | 같은 앱 |
| Storage 버킷 | visionparser(JSONL·HTML) | (S1 화면) |

### 4. 끝에서 끝까지 흐름 (시나리오 단위)

표기: `A ─(방식)→ B`. [미확인]은 코드로 고리를 확인하지 못한 곳이다. 번호는 2절 연결 번호다.

#### ① 데이터 소스 등록 → 카탈로그 → 보강 → 온톨로지 → 가상 클래스 → 에이전트 MCP 질의

```
운영자/robo-data-frontend[미확인·비공개] 또는 curl
  ─HTTP POST /api/datasources?register_to=both→ data-fabric(8004)            N17
      ├─Bolt MERGE (:DataSource 평문 자격증명)→ 공유 Neo4j                    N14
      └─HTTP /api/databases/→ MindsDB(47334)  (연결 검증은 MindsDB)            N15
  ─HTTP POST /api/datasources/{ds}/extract-metadata-sync→ data-fabric
      ─직접 접속 introspect→ 원천 DB                                          N16
      ─Bolt MERGE :Schema/:Table/:Column/[:REFERENCES]→ 공유 Neo4j             N14
  (선택) text2sql 부팅·색인 ─Bolt→ 제약·벡터 인덱스·Table.text_to_sql_*          N19

메타데이터 보강(별도 그래프 층)
  antlr-code-parser ─파일 data/→ robo-data-analyzer                           N35
  robo-data-analyzer ─HTTP /robo/tables/discovery·sample-context·resolve-context→ robo-data-catalog   N32
  robo-data-catalog ─HTTP /api/query·/api/datasources/{ds}/tables→ data-fabric ─→ MindsDB   N24
  robo-data-analyzer ─Bolt MERGE TABLE/COLUMN/PROCEDURE→ Neo4j(ROBO_NEO4J_*)  N33
  robo-data-catalog ─Bolt SET TABLE.description, [:FK]→ Neo4j                 N23
  ✗ 보강 결과(대문자 TABLE)를 카탈로그 :Table로 옮기는 투영 [미확인 — spec 008의 catalog_projection.py가 공개 코드에 없음]

온톨로지 설계·적재 (ontology-studio)
  사용자(스튜디오 UI 5173 / 구축 에이전트)
  ─Bolt MATCH :Table/:Column/REFERENCES→ 공유 Neo4j (LLM 없이 결정적 생성)      N06
  ─HTTP /api/datasources/*, /text2sql/meta/tables/{t}/columns→ data-fabric·text2sql   N01·N04
  ─SQLite: 클래스·바인딩·behavior 저장 / Bolt MERGE (:_Entity:<Class>) (가상 클래스는 0건)   N07
  문서 입력이면 ─Ollama /api/embed→ Chunk 벡터                                 N08
  전략 2(인과)면 ─HTTP POST /whatif/analyze-matrix→ domain-layer [상대편 미공개]   N05

질의 시점
  외부 AI 클라이언트 / 스튜디오 답변 모드
  ─MCP streamable-http /mcp (ontology_query, ontology_list_entities, ontology_query_datasource_sql …)→ ontology-studio mcp(8100)   N13
      가상 클래스 behavior ─HTTP POST /text2sql/direct-sql→ neo4j-text2sql ─MySQL wire→ MindsDB ─→ 원천 DB   N03·N18
      (MCP_ALLOW_DATASOURCE_EXPANSION=false가 기본이라 외부 클라이언트의 실데이터 조회는 막혀 있음 — OS .env.example)
  외부 CLI 구축 모드 ─cliagents→ claude/codex ─MCP /mcp/agent-bridge→ 같은 도구 함수   N12
  ProcessGPT 에이전트가 이 MCP를 쓰는 설정 [코드에 없음 — tenants.mcp에 사람이 넣어야 함, 미확인]
```

#### ② 문서(PDF·이미지) → visionparser / bpmn-extractor → 프로세스 정의·지식

```
ProcessGPT 채팅(vue3) ─(S2) deepagents/base-agent 도구 create_pdf2bpmn_workitem→ Supabase todolist(agent_orch=pdf2bpmn)   N75
  ─(S1) agent-sdk 폴링→ bpmn-extractor 워커(8012)                              N70
      ─HTTP GET /documents/chunks-with-embeddings→ memento(8005, S2)           N71
      ─LLM·OCR→ 프로세스·태스크·역할·결정 추출                                    N74
      ─AGE(테넌트별 그래프)→ 추출 그래프 저장                                     N73
      ─(HITL) todolist output 갱신 → vue3 Chat.vue 결과 카드                    N72
      ─Supabase upsert proc_def / form_def / configuration / users / agent_skills   N72
  → 이후 실행은 S1(completion)이 proc_def를 소비

이미지·서식 추출: vue3 프로세스 시작·워크아이템에서 visionparse 선택 ─todolist→
  (S1) agent-sdk 폴링 → visionparser ─VLM OCR·LangExtract→ Supabase Storage(JSONL·HTML) + events   N78·N79·N80
  → 결과가 프로세스 정의·지식으로 이어지는 고리 [미확인 — 결과는 워크아이템 output으로 끝남]

ontologic 쪽 별도 경로: domain-layer ─HTTP /api/upload·/api/process/{job}·/api/files/bpmn/content→ bpmn-extractor API
  ─→ 프로세스 레이어 온톨로지(Neo4j OntologyType…)                            N28·N29

대체 경로(사람 + Claude Code): bpmn-process-generation-skill
  ─.bpmn/ 산출물→ scripts/save_to_supabase.py ─supabase-py→ proc_def/form_def/configuration/users/agent_skills   N76
```

#### ③ BSC 인터뷰 → 전략·KPI → 실행 결과로 KPI 측정 → 대시보드

```
사용자 ─ProcessGPT 채팅→ deepagents(S2) + 시스템 스킬 bsc-strategy-interview(SKILL.md)   N60
  ─HTTP GET /api/map·/api/canvas (기존 전략 확인) → POST /api/objectives·/api/kpis·/api/canvas/blocks
   → (프로세스 연결) link_kpi_to_process → strategy(8014)                     N58·N77
strategy ─AGE MERGE→ corp_ontology(전략층 Objective/KPI/Initiative)            N52
strategy 60초 루프
  ├─ ontology_sync: Supabase proc_def/users/agent_skills/skills/todolist ─→ AGE(Process/Task/User/Agent/Team/Skill)   N50·N52
  │     + claude-skills SKILL.md ─LLM 관계 추출→ USES_SKILL 등                 N53·N55
  ├─ measurement: KPI 노드(AGE)에서 연결 프로세스 조회 → bpm_proc_inst(proc_def_id 기준 집계) 또는 kpi.source_url(HTTP GET)
  │     ─→ KPI 노드 current_value + strategy_kpi_measurements + (Process)-[:IMPACTS_KPI]->(KPI) 엣지 속성   N50·N54·N51
  └─ survey watch: bpm_proc_inst 새 COMPLETED 감지 → 연결된 survey_score KPI가 있으면 참여자에게
        todolist INSERT(activity_id='kpi_survey') → 응답 → strategy_survey_requests → 실적   N51
대시보드
  vue3 StrategyBoard·KPIDashboard·OntologyExplorer ─/strategy-service/api/map·kpis/{id}/measurements·ontology/graph·impact·contribution→ strategy   N57
  analytic 기여도 대시보드 ─/api/map·/api/contribution/strategy/{id}·/api/impact/strategy/{id}→ strategy
                         ─/api/skills/{name}/contributors→ agent-feedback(S2)   N62·N63
  agent-feedback(S2) ─/api/ai/alignment→ strategy (피드백 배치의 전략 정렬 검사)   N59
  ✗ process_gpt AGE 그래프로 "strategy-service pull 동기화" [로드맵 — 코드 없음]
```

#### ④ What-if / 인과 분석 (domain-layer) ← 온톨로지

```
경로 A (ontology-studio 전략 2): 데이터소스 열 행렬 ─HTTP POST /whatif/analyze-matrix→ domain-layer(무상태)
  ─Granger·BH 보정 결과→ ontology-studio가 INFLUENCES_* (hypothesis:true) 관계로 기록, 사람 승인 뒤 확정   N05 [DL 공개 코드에 엔드포인트 없음]
경로 B (domain-layer 단독): ObjectType(Neo4j) + behavior ─/text2sql/direct-sql→ 시계열
  ─/whatif/discover-edges·correlation-matrix·build-model-graph·train-models→ MindsDB 모델 학습(47334)
  ─/whatif/simulate·compare-scenarios·scenarios/{id}/run→ 결과(WhatIfScenarioProfile)   N27·N29·N30
  ─/ontology/schemas/{id}/nodes/{node}/causal-analysis(/stream)→ 노드 인과 분석
경로 C (감시와 연결): agent-scheduler ─/whatif/scenarios/{id}/run→ domain-layer   N37
경로 D (프로토타입): ontologic what-if-simulator ─Neo4j + MindsDB→ 환율→KPI 시뮬레이션(게이트웨이 /whatif/** → 8005)   N44·N46
✗ ProcessGPT strategy의 /api/impact/* 는 자체 AGE 그래프 기반이며 domain-layer를 부르지 않는다(STR에 domain-layer URL 없음).
```

#### ⑤ 실행 기록 → 분석(analytic) · 분류(instance-classifier)

```
(S1) completion이 bpm_proc_inst·todolist 기록
  ├─ analytic ETL(60초) ─SQL→ dw.dim_* / dw.fact_process_instance·fact_task·fact_event·fact_usage   N61
  │     ─/api/dashboard/*·/api/analytics/*·/api/timeline/*·/api/query/natural→ vue3 /api/analytics   N64
  │     (analytic/olap/ = ontologic data-platform-olap와 같은 AI Pivot Studio 코드 사본)
  ├─ instance-classifier 폴링(10초) ─SQL bpm_proc_inst·todolist·form_def→ 임베딩 → voc_instances(pgvector)
  │     ─HDBSCAN 재군집·LLM 이름 짓기→ voc_topics                               N65·N66
  │     ─/toplist·/similar·/topics/…/instances→ vue3 InstanceTopList·SimilarInstancesPanel   N67
  └─ strategy measurement ─SQL bpm_proc_inst→ KPI 실적                         N50
```

#### ⑥ 업무 앱(sample-app-wms) → MCP → 에이전트

```
WMS 설치 스크립트 ─PostgREST upsert→ ProcessGPT Supabase: tenants.mcp.mcpServers.wms = http://host.docker.internal:8199/mcp,
                   에이전트 1명(users, 허용 MCP=wms), proc_def wms_replenishment_process, form_def 3개   N86
ProcessGPT 인스턴스 실행 → 에이전트 태스크 → (S1) completion polling_service / agent-sdk ─fetch_tenant_mcp→ tenants.mcp   N86
  ─MCP http→ wms-mcp(8199) ─supabase rpc wms_check_stock·RFQ·PO·입고·품질·WCS→ wms 스키마   N85
  → 사람 HITL(구매 승인 폼) → PO → 입고 → 품질 → 적치/폐기 (README의 흐름)
같은 문법의 ontologic 문: 감시 에이전트(agent-scheduler·text2sql 이벤트·node-local) ─stdio MCP process-gpt-mcp / work-assistant-mcp→
  ProcessGPT execute_process → todolist/bpm_proc_inst                         N20·N38·N39b
```

### 5. CONNECTIONS.md(67건)에 없던 새 연결

CONNECTIONS.md에 S3 관련으로 이미 있는 것: vue3→analytic·instance-classifier·strategy(호출), ontologic→ontology-studio·bpmn-extractor(공유 구성), ontological-db↔enterprise-custom(관련 기술), infra-docker→glossary(배포), k8s→visionparser(배포 정의), process-gpt→S3 레포 등록. 아래는 모두 그 표에 없다. 종류는 CONNECTIONS.md 용어를 따른다.

| 출발 | 도착 | 종류 | 의미 | 근거(2절) |
|---|---|---|---|---|
| O01 ontology-studio | ontologic data-fabric | 호출 | 카탈로그 탐색·샘플·MindsDB view 관리 | N01·N02 |
| O01 ontology-studio | ontologic neo4j-text2sql | 호출 | 가상 클래스 SQL 실행 관문(`/text2sql/direct-sql`), 컬럼 메타 | N03·N04 |
| O01 ontology-studio | ontologic domain-layer | 호출 | 인과 발견 위임 `/whatif/analyze-matrix`(상대편 미공개) | N05 |
| O01 ontology-studio | O03 ontological-db | 의존(선택) | 서브모듈 + Bolt로 Neo4j 대체 저장소 | N11 |
| O01 ontology-studio | Ontological 관리 API(7481/7482) | 호출 | 스키마 스냅샷·릴리스 plan/apply(서버 미확인) | N10 |
| O01 ontology-studio | A06 cliagents | 의존 | `AGENT_BACKEND=cliagents`일 때 외부 CLI 구동, 도구는 `/mcp/agent-bridge` | N12 |
| ontologic data-fabric | MindsDB / 원천 DB / 공유 Neo4j | 호출·공유 | 등록과 카탈로그 적재(유일 writer) | N14~N17 |
| ontologic neo4j-text2sql | ProcessGPT `work-assistant-mcp`(S2) | 호출(MCP stdio) | 이벤트 규칙이 맞으면 프로세스 검색·실행 | N20 |
| ontologic neo4j-text2sql | CEP 서비스(8088) | 호출 | 규칙 동기화·이벤트 전송(대상 미확인) | N21 |
| ontologic domain-layer | T02 process-gpt-bpmn-extractor | 호출 | PDF → BPMN 추출 API 사용 | N28 |
| ontologic domain-layer | ontologic neo4j-text2sql | 호출 | 메타·`ask`·`direct-sql`·`execute-ddl` | N25~N27 |
| ontologic domain-layer | MindsDB | 호출 | What-if 예측 모델 학습·예측 | N30 |
| robo-data-analyzer | robo-data-catalog | 호출 | 테이블 발견·샘플 문맥·객체 해석 | N32 |
| robo-data-catalog | ontologic data-fabric | 호출 | 샘플 행 질의(FK 추론) | N24 |
| antlr-code-parser | robo-data-analyzer | 공유 구성(파일) | 형제 `data/` 폴더 | N35 |
| agent-scheduler | A02 base-agent-langchain-react 안 `process-gpt-mcp` 패키지(S2) | 호출(MCP stdio) | 감시 조건 충족 → `execute_process` | N38 |
| agent-scheduler | domain-layer / neo4j-text2sql | 호출 | 시나리오 실행 / 감시 SQL | N36·N37 |
| node-local-agent-scheduler | domain-layer / agent-scheduler / 공유 Neo4j | 호출·공유 | Agents.md(ObjectType 노드) 실행 → 시각 효과·데이터 조회 → ProcessGPT 실행 위임 | N39·N39b |
| security-guard·data-platform-olap | 공유 Neo4j 카탈로그 `:Table` | 공유 | 카탈로그 읽기(헌법 문구와 다름) | N41·N42 |
| P03 strategy | Supabase 원천 표 + AGE `corp_ontology` | 공유 | 원천 → 그래프 60초 동기화, KPI 측정, 설문 todolist INSERT | N50~N52 |
| P03 strategy | T07 process-gpt-claude-skills | 호출 | `SKILLS_API_URL` SKILL.md 읽기 | N53 |
| A01 deepagents | P03 strategy | 호출 | BSC 저장 도구 6종 | N58 |
| P04 agent-feedback | P03 strategy | 호출 | `/api/ai/alignment` | N59 |
| P01 analytic | P03 strategy, P04 agent-feedback | 호출 | 기여도 대시보드 | N62·N63 |
| D02 strategy-skill, D01 bpmn-generation-skill | A01 deepagents | 배포(동봉) | 시스템 스킬로 이미지에 포함 | N60 |
| D01 bpmn-generation-skill | Supabase `proc_def`… / P03 strategy | 호출 | 저장 스크립트, `link_kpi_to_process` 지시 | N76·N77 |
| T02 bpmn-extractor | C07 agent-sdk / T01 memento / Supabase / AGE | 의존·호출 | 폴링 워커, 청크 원천, 정의 저장, 추출 그래프 | N70~N73 |
| A02 process-gpt-mcp(`create_pdf2bpmn_workitem`) | T02 bpmn-extractor | 호출(todolist 경유) | 문서 → 프로세스 작업 생성 | N75 |
| T05 visionparser | C07 agent-sdk / Supabase Storage | 의존·호출 | `visionparse` 폴링 워커 | N78·N79 |
| C02 vue3 | AGE `process_gpt` | 공유(읽기 RPC) | 온톨로지 탐색기 | N87 |
| D05 sample-app-wms | C03 completion·C07 agent-sdk | 설정 연결 | `tenants.mcp`에 wms MCP 등록 → 실행체가 접속 | N86 |
| P01 analytic(`olap/`) | ontologic data-platform-olap | 공유 구성(코드 사본) | 같은 AI Pivot Studio | 5절 근거: ANL `olap/backend/README.md:1` |

### 6. 미확인 · 결함 의심

#### 6-1. 코드로 고리를 확인하지 못한 것 (미확인)

| 항목 | 상태 |
|---|---|
| robo-data-frontend, robo-data-platform(infra) | 비공개 저장소(클론 시 자격 요구). ontologic UI가 어떤 경로를 부르는지 확인 못 함 |
| domain-layer `POST /whatif/analyze-matrix` | ontology-studio와 ontologic spec 003(tasks T023 체크됨)에만 있음. 공개 domain-layer main(11de767)과 ontologic 포인터(2e88db1) 모두에 없음 → 미푸시 또는 다른 원격 |
| analyzer `catalog_projection.py`(보강 설명을 카탈로그 `:Table`로 투영) | ontologic spec 008:217-220에만 있음. 공개 analyzer main에 없음, `.gitmodules`의 `branch = refactor`도 공개 원격에 없음 |
| Ontological 관리 API(7481/7482) 서버 | ontology-studio 클라이언트만 있음. ontological-db·enterprise-custom 어디에도 `schema-change`/`release` HTTP 서버 없음 |
| `work-assistant-mcp`(text2sql이 `uvx`로 실행) | 패키지 소스 없음. 같은 계열 `process-gpt-mcp`에는 `search_processes` 도구가 없음 |
| CEP 서비스(text2sql `CEP_SERVICE_URL` 8088) | 어느 레포인지 불명 |
| robo-architect(8001), risk-calculator(8003) | 게이트웨이·start 스크립트에만 등장, 소스 없음 |
| `process_gpt` AGE 그래프 writer | 스키마·RPC만 있음. 백필 ETL·트리거·strategy pull 워커는 로드맵. vue3 RPC 주석의 `scripts/seed-ontology-graph.mjs`도 없음 |
| visionparser 결과 → 프로세스 정의·지식 | 결과는 워크아이템 output과 Storage 파일로 끝남. 정의·지식으로 이어지는 소비자는 확인 못 함 |
| process-gpt-glossary를 부르는 ProcessGPT 화면 | nginx `/robo/`는 있지만 vue3는 자체 `glossary_terms` 표를 씀 |
| ProcessGPT 에이전트가 ontology-studio MCP(8100) 또는 analyzer MCP(`/robo/mcp/`)를 쓰는 설정 | 코드·시드에 없음. 사람이 `tenants.mcp`에 넣어야 가능(추정, 미검증) |
| process-gpt-knowledge-graph(O05) | README만 있음 |
| 실행 검증 | 이번 조사는 정적 읽기만 했다. 어떤 연결도 실제로 돌려 보지 않았다(컨테이너 미기동) |

#### 6-2. 코드끼리 어긋나는 곳 (결함 의심, 미실행)

| 어긋남 | 근거 |
|---|---|
| node-local 하위 프로세스가 domain-layer `POST /ontology/object-types/{t}/execute-query`를 부르지만 domain-layer에 그 경로가 없다(`visual-effects`, `data`는 있음) | NLAS `app/runner/run_deepagent.py:125`; DL `app/routers/ontology.py` 경로 목록 |
| agent-scheduler가 text2sql `/watch-agent/profiles/{id}/record-execution`을 부르지만 text2sql watch_agent 라우터에 없다 | ASCH `integrations/text2sql_client.py:77`; T2S `app/routers/watch_agent.py:23,196-349` |
| domain-layer가 `{TEXT2SQL_URL}/execute-ddl`(접두사 없음)을 부르지만 text2sql에 그 경로가 없다 | DL `app/services/materialized_view_service.py:92`; T2S `app/main.py:283-311` |
| infra-docker는 strategy를 AGE 없는 `supabase/postgres:15.8.1.060` DB에 붙인다. strategy는 AGE가 없으면 기동 중 `RuntimeError` | INF `docker-compose.yml:537-556,829-831`; STR `main.py:76-81`, `graph/age_adapter.py:125-140` |
| 포트 기본값이 문서마다 다르다: domain-layer 8002(코드·게이트웨이) / 8001(installation.md·ontology-studio 기본), text2sql 8000(코드·게이트웨이 기본) / 8020(installation 실측), catalog·analyzer 15503/15502(코드) / 5503/5502(게이트웨이), OLAP 8002(start) / 8007(게이트웨이), what-if-simulator 8001(run_api) / 8005(게이트웨이), bpmn-extractor API 8000(run.py) vs domain-layer 기대 8001 | 각 config·`application.yml`·`installation.md:465-474` |
| 게이트웨이 라우트 id와 포트가 엇갈린다: `robo-catalog-service`(5503)가 `/robo/glossary/**`·`/robo/business-calendar/**`를 받고, `robo-glossary-service`(5504)가 `/robo/**` 전체를 받는다. 그런데 catalog도 `/robo` 접두사를 쓴다 | ONT `api-gateway/src/main/resources/application.yml:207-224`; CAT `shared/config/settings.py:122`; GLO `api/glossary_router.py:32` |
| 헌법은 "security-guard 등은 카탈로그를 직접 읽지 않는다"고 쓰지만 security-guard·data-platform-olap은 `:Table`을 직접 읽는다 | ONT `.specify/memory/constitution.md`(서두); N41·N42 |
| 과업 문구의 "strategy가 동기화하는 AGE 그래프 `process_gpt`"는 코드와 다르다. strategy 기본값은 `corp_ontology`이고 `process_gpt`는 vue3 스키마 패키지의 그래프다 | STR `config.py:34`; VUE `ontology/ontology-spec.yaml:12` |
