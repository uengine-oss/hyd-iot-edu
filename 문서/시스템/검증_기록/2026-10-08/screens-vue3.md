# process-gpt-vue3 화면 기준 HYD 빈 곳 판정 (2026-10-08, 읽기 전용)

기준: vue3 `refs-A/process-gpt-vue3`@867e8cf(2026-10-08) 라우터 `src/router/MainRoutes.ts`. 기존 조사(processgpt-flows.md 1~2절·processgpt-gaps.md·todo-verify.md·TODO.md 강의용 기능 목록) 재사용.
HYD 실물: `it/portal/www/*.js`·`index.html`, `it/process/procsvc/`, `it/agent-worker/worker/`, `it/agent/agentsvc/`. 코드 읽기만, 실행 안 함.

## 1. 결론 5줄
1. vue3 라우터 활성 경로 92개(`MainRoutes.ts`) 중 F1~F12에 걸리는 화면을 판정했다: 보강 표 19개 = **UI만 부족 4**(S1~S4) · **기능도 없음 15**(S5~S19), 이미 있음 17줄, 넣지 않음 16줄(관리 콘솔·편집기·분석 등).
2. 개수로는 기능 쪽이 많지만, 사용자가 짚은 "단계를 누르면 입력→도구 호출→판단→넘긴 값과 실시간 흐름"(S1·S2 = TODO 0)은 **UI 문제**다 — `GET /api/todolist/{wid}`가 입력·입력 출처·그 단계 이벤트를 이미 돌려주고(`instances.py:164-184`) SSE에도 `todo_id`가 있는데, 포털이 흐름도 클릭을 받지 않고 이 API를 "내 차례"에만 쓴다. 일꾼 현황(S3 = TODO 6)·판본 비교(S4)도 API는 있다.
3. 기능도 없음 15개 중 14개는 이미 TODO 1·2·3·4·5·11·12에 들어 있거나 그 문구에 합칠 수 있다(에이전트·스킬·MCP·결재·배정·알림·KPI·개선 순환). 기존 조사가 "서비스 연결"로 잡은 것을 화면으로 다시 봐도 빠진 큰 덩어리는 없었다.
4. 진짜 새 항목은 **1개**: S11 "끝난 단계에 좋아요/나빠요·의견 → AI 개선안 → 전·후 비교 → 고른 것만 새 판본으로"(vue3 `ProcessFeedbackDrawer`·`ProcessFeedbackCompare`). 나머지는 기존 TODO 문구 보강으로 충분하다(0: 흐름도 노드 클릭·그 단계만 실시간 / 1: 단계별 에이전트 고르기 / 4: 판본 비교는 UI만으로 먼저 / 5: 역할에 나 연결·알림 읽기·위임(선택) / 6: 원본 근거 정정 / 12: 내 피드백·병합 요청함).
5. 따라서 TODO로 보강 가능하다. 주의 2가지: vue3에도 전역 "AI 일꾼 현황" 라우트는 없고 단계별 탭뿐이라 TODO 6 원본 근거 문구를 고쳐야 하며, HYD에는 로그인·"나"가 없어 TODO 5는 역할→사람 연결(S7, 기능)이 화면(S5·S6)보다 먼저다.

## 2. 화면 단위 TODO 보강안 (화면 하나 = 한 항목)

경로 표기: vue3는 `src/` 기준(라우트는 `src/router/MainRoutes.ts:줄`), HYD는 `it/` 기준. 크기는 예상(작음 = 기존 화면에 조금 · 중간 = 새 화면/API 한 덩어리 · 큼 = 새 층).
판정: **UI만 부족** = 데이터·API는 있고 화면만 붙이면 됨 / **기능도 없음** = 저장·API·실행 경로까지 만들어야 함.

| # | 화면(vue3 이름·경로) | 흐름 | 이 화면에서 사용자가 하는 것(쉬운 말) | 판정 | HYD 지금(파일:줄) | vue3 근거(파일:줄) | 누가·왜 강의에 필요 | 크기 | 기존 TODO와의 관계 |
|---|---|---|---|---|---|---|---|---|---|
| S1 | 처리 건 상세 › 프로세스 탭에서 단계 누르기 (InstanceCard `/instancelist/:instId` → InstanceProgress + ProcessFeedbackDrawer, MainRoutes.ts:54-55) | F3 | 흐름도에서 끝난 단계를 눌러 그 단계가 낸 결과를 옆 창으로 본다 | UI만 부족 | 흐름 탭 흐름도는 단계 상태 색만(`portal/www/flow.js:80-97`), 클릭 처리는 "맞춤" 버튼뿐(`flow.js:187-191`). 단계 행을 펼치면 시각·한 줄 기록·출력 JSON 원문(`portal/www/instances.js:308-323`) | 완료 노드 더블클릭 → `openFeedbackPanel`(`components/BpmnUengineViewer.vue:988-1003`), 드로어 연결(`components/apps/todolist/InstanceProgress.vue:17-44`), 드로어의 "이 단계 산출물"(`components/ui/ProcessFeedbackDrawer.vue:26-45`) | 수강생 — "처리 건 = 단계가 값을 넘기며 이어진다"를 흐름도에서 바로 확인(사용자 10-08 "태스크마다 클릭했을 때") | 작음 | **TODO 0 포함** — 진입점 "흐름도 노드 클릭"을 문구에 명시 |
| S2 | 단계(워크아이템) 상세 › 입력 탭 + 에이전트 모니터 탭 (WorkItem `/todolist/:taskId`, MainRoutes.ts:39-40) | F3 | 단계 하나를 열어 ① 받은 입력(앞 단계 값) ② 그 단계가 부른 도구와 받은 결과·AI 질문을 시간순으로 ③ 진행 중이면 실시간으로 본다 | UI만 부족 | 백엔드 있음: `GET /api/todolist/{wid}`가 `inputs`·`input_sources`·`input_state`·`events`(그 단계 todo_id만)를 돌려줌(`process/procsvc/instances.py:164-184`, 라우트 `process/procsvc/instance_mode.py:721-730`), `GET /api/events?todo_id=`(`instance_mode.py:870-882`), SSE 이벤트에 `todo_id` 있음(`portal/www/liveStream.js:22-30`), 값→만든 단계 `variable_sources`(`instances.js:377-380`). 화면: 포털은 이 API를 "내 차례" 작업에만 부름(`instances.js:43-45`), 도구 호출은 처리 건 전체 기록 탭에 섞여 나옴(`instances.js:458-480`) | 입력 데이터 `ActivityInputData`(`components/apps/todolist/FormWorkItem.vue:54`, 값 수집 `:1116-1154`), 탭 구성(`components/apps/todolist/WorkItem.vue:974-1011`), 에이전트 모니터 탭(`WorkItem.vue:242-255`) → `EventTimeline`(`views/markdown/AgentMonitor.vue:7-28`), 그 단계 todo_id로 `tool_usage_started/finished`·`human_asked` 실시간 구독(`AgentMonitor.vue:862-877`) | 수강생 — 에이전트 Task가 "입력 → 도구 호출 → 판단 → 넘긴 값"으로 도는 것을 단계 단위로 관찰(회의 L202-214, L434-436) | 중간 | **TODO 0 포함 + 합침** — "그 단계만 실시간으로" 문구 추가, "넘긴 값"은 `variable_sources`로 계산(새 API 불필요) |
| S3 | 지금 일하는 AI 일꾼 (vue3에 전역 화면 라우트 없음 — 단계별 "대기 중/작업 시작" 표시와 채팅방 에이전트 상태만) | F3 | 경보 하나에 어떤 일꾼이 떠서 무슨 단계를 잡고 있는지 본다 | UI만 부족 | `GET /api/agents/status`(`instance_mode.py:689-692` → `worker_status`), 포털 호출 0(`grep agents/status it/portal/www` 결과 없음), 배너는 진행 중·내 차례·질문 3칸(`instances.js:69-84`) | 단계 대기 표시 `isQueued`(`views/markdown/AgentMonitor.vue:44-58`), 채팅방 에이전트 상태 `agentStatuses`(`components/AgentChatRooms.vue:237,472`). 전역 모니터 라우트는 MainRoutes.ts에 없음 | 수강생·강사 — 워커가 실제로 작업을 집어 가는지(todolist 임대) 눈으로 확인(회의 L434-435) | 작음 | **TODO 6 포함** — 원본 근거 "vue3 에이전트 모니터"는 단계별 탭임을 정정 |
| S4 | 판본 비교 (`/version-comparison` VersionComparison, MainRoutes.ts:680-681) | F1 | 같은 흐름의 두 판본을 나란히 놓고 더해진·빠진 단계를 본다 | UI만 부족 | 판본별 정의 조회 `GET /api/process/definitions/{id}?version=`(`instance_mode.py:579-585`), 불변 판본 등록(`instance_mode.py:587-597`). 포털은 고르기·불러오기·등록·실행만(`portal/www/definitionRegistry.js:45-62`) | 두 BPMN 뷰어(`views/process-hierarchy/VersionComparison.vue:82-149`), 차이 요약(`:200-270`) | 수강생 — 흐름을 바꾼 뒤 "무엇이 바뀌었나"를 보고 배포 판단(회의 L448) | 작음~중간 | **TODO 4 포함** — 승인·배포(기능)보다 먼저 UI만으로 가능하다고 분리 표시 |
| S5 | 내 할 일 (`/todolist` TodolistCard, MainRoutes.ts:28-29) | F7 | 내게 배정된 단계만 모아 정렬해 보고 연다 | 기능도 없음 | "내 차례"는 모든 사람 단계 IN_PROGRESS(`instances.js:35-36`), 작업 `user_id`는 정의의 역할 바인딩 끝점(`process/procsvc/engine.py:324`, 예 role:prod-mgr), `GET /api/todolist?user_id=` 필터는 있음(`instance_mode.py:715-719`). 로그인·"나"가 없고 승인자 이름은 자유 입력(`I.form.by`) | 내 업무 조회 `getWorkList`(`components/apps/todolist/TodolistCard.vue:178`) | 수강생 — "담당자인 나에게 배정"(TODO 방향 문장, 회의 L405-406·L413) | 중간 | **TODO 5 포함** |
| S6 | 알림 (`/notifications` NotificationsPage, MainRoutes.ts:754-755) | F7 | 알림 목록을 보고 읽음 처리, 눌러서 해당 단계로 간다 | 기능도 없음 | `notifications`는 쓰기만(`process/procsvc/procdb.py:760`, 에이전트 질문 때), 읽기 API 없음(`instance_mode.py` 라우트 562~889에 없음), 화면 없음 | 목록·모두 읽음(`views/notifications/NotificationsPage.vue:134-148`), 읽음 표시(`:199`) | 수강생 — 사람 단계가 오면 알림으로 받아 버튼만 누름(회의 L417-426) | 작음 | **TODO 5 포함** |
| S7 | 업무분장 (`/work-assignment` WorkAssignment, MainRoutes.ts:507-508) | F7 | 흐름의 역할(레인)마다 팀·담당자를 표로 보고 정한다 | 기능도 없음 | 역할 바인딩은 정의 JSON 안(`engine.py:324`), 승인 역할은 질의 보기·API로 읽기만(`portal/www/index.html:210` t3_roles, `agent/agentsvc/main.py:260-262` `/api/ontology/roles`). 역할→사람 연결 저장 없음 | 담당자 열(`views/work-assignment/WorkAssignment.vue:122`), 편집 버튼은 원본도 숨김(`:155`), 저장 로직(`:1050-1120`) | 수강생 — "역할 = 나"로 연결해야 S5·S6이 의미를 가짐 | 중간 | **TODO 5에 합침** — "역할에 나를 연결하는 화면"을 문구에 추가 |
| S8 | 단계 위임 (WorkItem 담당자 아바타 → DelegateTaskForm) | F7 | 내게 온 단계를 다른 담당자에게 넘긴다 | 기능도 없음 | 포털 `grep 위임\|delegate` 0건, 담당자 변경 API 없음 | 위임 진입(`components/apps/todolist/WorkItem.vue:170-188`), 폼 `components/apps/todolist/DelegateTaskForm.vue` | 수강생(선택) — 부재·권한 밖 건 넘기기. 강의 가치 중하 | 작음 | **TODO 5에 합침(선택)** |
| S9 | 결재함 (`/my-inbox` MyInbox: 승인함·개선 요청함·내 상신함, MainRoutes.ts:744-745) | F1 | 흐름 변경 요청을 받아 승인·반려하고, 내가 올린 요청 상태를 본다 | 기능도 없음 | 정의 등록 즉시 판본 확정(`instance_mode.py:587-597`), 검토 상태 없음, 경보가 여는 흐름은 파일 하나로 고정(`instance_mode.py:39,128`) | 탭(`views/review-board/MyInbox.vue:450,562,621`), 승인·반려(`:205,234`) | 수강생 — 흐름 변경을 초안→승인→배포 순서로(회의 L448) | 중간 | **TODO 4 포함** |
| S10 | 검토 게시판·검토 상세 (`/review-board`, `/review-board/:reviewId` ProcessReviewBoard·ProcessReviewDetail, MainRoutes.ts:720-740) | F1 | 바뀐 흐름 전·후와 변경 요약, 결재 이력을 보고 승인하면 배포된다 | 기능도 없음 | S9와 같음. 경보 → 흐름 연결은 고정 파일(`instance_mode.py:39`) | 전·후 BPMN·변경 요약(`views/review-board/ProcessReviewDetail.vue:1000-1139`), 결재 이력·버튼(`:1139-1253`) | 수강생 — "배포하면 다음 경보부터 새 흐름"을 직접 확인 | 중간~큼 | **TODO 4 포함** |
| S11 | 단계 평가 → 개선안 전·후 비교 → 적용 (처리 건 프로세스 탭 드로어의 피드백 + ProcessFeedbackCompare) | F8 | 끝난 단계에 좋아요/나빠요와 의견을 남기면 AI가 흐름 개선안을 내고, 전·후를 나란히 보고 고른 변경만 새 판본으로 적용한다 | 기능도 없음 | `todolist.feedback` 칸은 있음(`supabase/migrations/20261003000001_process_engine.sql:185`)이나 HYD는 검증 재시도·사람 답변에만 씀(`instances.py:378-382,625`). 사람 평가 쓰기 API·화면 없음(포털 `grep feedback` 0건) | Good/Bad·의견(`components/ui/ProcessFeedbackDrawer.vue:47-80`), 전·후 비교 화면(`components/apps/todolist/InstanceProgress.vue:4-15`), 적용 → 새 proc_def_version(`InstanceProgress.vue:162-189`) | 수강생 — 결과를 사람이 평가해 개선으로 잇는 순환의 사람 쪽 입구(회의 L7-8·L448) | 중간~큼(개선안 생성은 TODO 12와 공유) | **새로** — TODO 12의 "사람 평가 입구"로 넣거나 12에 합침 |
| S12 | 내 피드백 (`/my-feedback` MyFeedback, MainRoutes.ts:759-760) | F8 | 내가 평가한 처리 건·단계와 그것이 개선에 반영됐는지 회차별로 본다 | 기능도 없음 | 없음(S11 전제) | 목록·상세·회차(`views/feedback/MyFeedback.vue:318-440`) | 수강생 — 내 평가가 다음 판단을 바꿨는지 확인 | 작음(S11 뒤) | **TODO 12에 합침** |
| S13 | 병합 요청함 (`/merge-requests` MergeRequestBoard, MainRoutes.ts:749-750) + 사이드바 대기 개선안 배지 | F8 | AI가 낸 스킬·규칙·흐름 변경 요청을 모아 검토하고 병합한다 | 기능도 없음 | 사람 손 수정 API만(순위 정책·BSC 조건 — todo-verify #17), 개선 요청 묶음·검토 큐 없음. 선례는 승인 없이 순위에 반영(`agent/agentsvc/cards.py:133,188`) | 목록·필터(`views/review-board/MergeRequestBoard.vue:397-483`), 대기 개선안 배지(`layouts/full/vertical-sidebar/VerticalSidebar.vue:779-803`) | 수강생 — "사람이 승인해야만 반영"(HANDOFF 원칙) | 중간 | **TODO 12 포함** |
| S14 | 조직도·에이전트 추가 (`/organization` OrganizationChartChat, MainRoutes.ts:93-97) | F4 | 조직도에 사람·AI 에이전트를 더하고, 설명 한 줄로 설정 초안을 받는다 | 기능도 없음 | users 시드만(`supabase/seed.sql:66-74`), 생성 API·화면 없음, 실행 프롬프트는 이름·역할 한 줄(`agent-worker/worker/prompt.py:156-160`) | 라우트(MainRoutes.ts:93-97), `AgentField.vue:45-170`·`OrganizationAgentGenerator.js`(TODO 1 근거 재사용) | 수강생 — 에이전트를 직접 만들어 단계에 배정(회의 L146-156) | 중간 | **TODO 1 포함** |
| S15 | 에이전트 상세 (`/agent-chat/:id` AgentChat + AgentChatInfo, MainRoutes.ts:262-263) | F4 | 에이전트의 목표·성격·도구·스킬·모델을 고쳐 저장하고, 대화 탭에서 시험한다 | 기능도 없음 | S14와 같음 | 목표(`components/AgentChatInfo.vue:82`)·성격(`:102`)·도구(`:122`)·스킬(`:205`)·모델(`:219`), 대화·학습·질문·지식 탭(`:430-434`) | 수강생 — 프로필이 실제 실행(지시문·모델·도구)에 반영되는지 확인 | 중간 | **TODO 1 포함**(대화로 시험은 TODO "랩업으로") |
| S16 | 단계 담당 에이전트 고르기 (WorkItem 에이전트 모니터의 AgentSelectField) | F4 | 이 단계를 어느 에이전트가 맡을지 골라 실행한다 | 기능도 없음 | 워커는 정의 활동의 `agentConfig`·`tools`만 읽음(`agent-worker/worker/context.py:87-90`) — 바꾸려면 정의 새 판본뿐, 단계별 지정 경로 없음 | `views/markdown/AgentMonitor.vue:41-43`(AgentSelectField `is-execute`), import `components/apps/todolist/WorkItem.vue:547` | 수강생 — 만든 에이전트를 단계에 붙여 결과 차이 보기 | 작음~중간 | **TODO 1에 합침**("단계에 배정"의 화면) |
| S17 | 스킬 관리 (`/skills`, `/skills/:id` SkillsManagement·SkillDetail, MainRoutes.ts:216-222) | F5 | 스킬 문서를 올리고 고치며, 어떤 에이전트가 쓰는지 본다 | 기능도 없음 | 정의 `skills`를 워커가 읽고 버림(`agent-worker/worker/context.py:89`) | 업로드 탭(`components/SkillsManagement.vue:83`), 내장 탭(`:413`), 저장소 URL 추가(`:526`), 트리(`components/SkillDetail.vue:95`), 사용 중 에이전트(`:250`) | 수강생 — 스킬을 붙이면 AI 조회 순서가 바뀌는 것 확인(회의 L132-135) | 중간 | **TODO 2 포함** |
| S18 | MCP 서버 등록·검사 (계정 설정 › MCP-Servers, `views/pages/account-settings/AccountSettings.vue:31` + `components/pages/account-settings/MCPServer.vue`) | F6 | 내가 만든 도구 서버를 등록하고, 붙이기 전에 연결·도구 목록을 검사한다 | 기능도 없음 | `tenants.mcp`는 SQL 손편집(`supabase/seed.sql:57-63`), 등록 API·검사 없음(강사용 검사 스크립트만, todo-verify #11) | 검사 호출(`services/McpValidatorService.js:23-38`) | 수강생 — 랩업에서 만든 MCP를 실제 에이전트에 붙이기(회의 L88-96·L123-138) | 중간 | **TODO 3 포함** |
| S19 | KPI·전략 보드 (`/analytics/kpi` KPIDashboard, `/strategy-board` StrategyBoard, 관리 › kpi-targets; MainRoutes.ts:573-574,695-706) | F10 | 목표 대비 KPI 달성률을 보고, 전략맵에서 목표·지표 연결을 본다 | 기능도 없음 | 지표에 목표값·식 문자열만, 계산 코드 0(`neo4j/v2/instances.cypher:29-56`). BSC 지도 보기는 지식 지도에 있음 | 목표 달성도·KPI·파이프라인(`views/analytics/KPIDashboard.vue:268-379`), 전략맵(`views/strategy/StrategyBoard.vue:619-678`) | 수강생 — 처리 결과가 지표에 어떻게 쌓이는지(회의 L5-10) | 중간 | **TODO 11 포함** |

- vue3 화면이 없는 기존 TODO: 7(워커 콘솔 로그 — 화면이 아니라 터미널), 8(AI 판단 채점 — 원본은 ontology-studio 골든 퀘스천), 9·10(이웃 플랫폼 ontologic). 이 보강안과 무관하게 그대로 둔다.

## 3. 이미 있음 (TODO 제외, 한 줄씩 근거)

- 처리 건 목록·진행 중/완료 거르기 (`/instancelist/running` ProcessInstanceRunning, `/list-pages/completed`, 관리 › exec-instances) — HYD 처리 건 목록과 상태 선택(`portal/www/index.html:136`, `instances.js:277-296`). 진행 중 단계의 실시간 로그는 S2.
- 처리 건 결과 (InstanceCard 산출물 탭 InstanceOutput) — 결과 탭 결정·설비 응답·효과 확인·정비 요청 카드와 값·출처(`instances.js:353-388`).
- 처리 건 활동 기록 (InstanceCard 활동 탭 InstanceWorkHistory) — 기록 탭 단계 표 + 이벤트(도구 호출·소요시간)(`instances.js:458-480`).
- 흐름도에 진행 상태 색칠 (InstanceProgress·WorkItem 진행 탭의 BPMN 상태) — 흐름 탭 흐름도(`flow.js:80-97`, `instances.js:347-350`), 분기 가지 표시(`instanceSteps.js:144-201`, vue3 `src/shared/instanceSteps.js` 이식).
- 처리 건 읽기 전용 이력 (`/instance-viewer/:instId` InstanceHistoryViewer) — 같은 상세 화면(`instances.js:325-345`).
- 사람 단계 입력·제출 (FormWorkItem) — "내 차례" 카드 선택·미리보기·승인·제출(`instances.js:195-275`).
- 에이전트 질문에 답하기 (EventTimeline의 human_asked) — 질문 패널 → `POST /api/todolist/{id}/human-response`(`instances.js:166-193`).
- 다시 실행 (WorkItem "다시 실행" ReworkDialog) — 재처리 패널(`portal/www/instanceRework.js`, `POST /api/instances/{id}/rework` `instance_mode.py:675`), 재판단(`taskDeferral.js`).
- 규칙 시험 실행 (BusinessRuleDefinitions "테스트 실행", `components/business-rules/BusinessRuleDefinitions.vue:454`) — 조치 판단 규칙 탭에서 조건 값을 바꿔 다시 판단(`portal/www/enterprise.js:318-328` → `agent/agentsvc/main.py:293` `/api/agent/decide`).
- 온톨로지 탐색 (`/ontology-explorer`, `/analytics/ontology`) — 지식 지도 탭(`index.html:27,66`).
- BSC 지도 보기 (`/bscard` BSCard) — 지식 지도의 BSC 층(`neo4j/v2/instances.cypher:8-57`). 실적 계산은 S19.
- 감사 기록 (관리 › audit-trail AuditTrail) — 사건별 기록 접기(`portal/www/app.js:508-509`, `/api/audit` `:561`).
- 시스템·외부 연동 상태 (`/systems` SystemManagement, `/external-api-health` ExternalApiHealth) — 시스템 구성 탭 구성 요소별 상태 점(`app.js:102-145`).
- 홈 (`/dashboard`) — 홈 탭 연결 도식·바로가기(`index.html:49-57`). 내용은 다름(설비 사례 중심), 유지.
- 정의 목록·등록·선택 판본으로 실행 (정의 화면의 판본 고르기·실행 부분) — 관리 › 프로세스 정의 등록(`index.html:238-255`, `definitionRegistry.js:45-62`). 승인·배포는 S9·S10.
- 문서 지식 등록 (`/knowledge` KnowledgeBasePage) — 지식 관리 › 매뉴얼 등록(`index.html:181`). F9 memento 방식은 TODO에서 "넣지 않음", HYD 대응은 있음.
- 데이터 소스 연결 (계정 설정 › ConnectionInfo, `AccountSettings.vue:46-47`) — 지식 관리 › 업무 데이터 연결(DDL)(`index.html:193`). vue3 탭 내부 기능은 미확인.

## 4. 넣지 않음 (한 줄씩)

- 칸반·간트·처리 건 채팅·달력·채팅방 (InstanceCard 칸반/간트/채팅 탭 `InstanceCard.vue:366-373`, `/calendar`, `/chats`, `/chat`) — TODO "넣지 않음"(칸반·간트·채팅·달력).
- 처리 건 첨부 파일 (InstanceCard 소스 탭 InstanceSource) — 사례에 첨부 입력 없음, 강의 가치 낮음.
- 유사 사례·처리 건 Top·분석 (WorkItem 유사 사례 탭 `WorkItem.vue:270-280`, `/instance-toplist`, `/analytics`, `/analytics/heatmap`, `/analytics/pi-flags`, `/analysis-dashboard`) — F12 넣지 않음. HYD는 판단 카드에 "과거 같은 선택"(`enterprise.js:258,273`)이 있음.
- BPMN 그리기·말로 흐름 만들기·폼 편집기·DMN 편집기 (`/definitions/*`, `/definitions-tree`, `/forms/*`, `/ui-definitions/*`, `/dmn/*`, `/business-rule` 편집부) — bpmn.io(bpmn-js·form-js·dmn-js)로 대체(TODO E1).
- 업무 체계도·하위 흐름 관리 (`/definition-map/*`, `/process-hierarchy*`, `/process-architecture`, `/call-activity-management`) — TODO "넣지 않음"(체계도·하위 흐름).
- 예약 시작 (`/schedule` ScheduleList) — TODO "넣지 않음"(정해진 때 자동 시작).
- 관리 콘솔 (`/admin-console/*`: property-schemas·option-lists·data-freeze·recycle-bin·system-operations·security-settings·usage-adoption·governance-studio·pi-flags·task-types·task-catalog·menu-settings·terminology·operation-policy, `/admin`, `/admin/:id`, `/admin/task-catalog`, `/system`) — SaaS 운영·관리. (audit-trail·exec-instances·kpi-targets는 위 3절·S19로 따로 판정)
- 로그인·테넌트·역할 요청·가입 승인 (AuthRoutes.ts, TenantRoutes.ts, `/admin-request`, `/organization?approvals=1`, `/organization-before`) — SaaS 운영. 단 S5의 "나"는 로그인 없이 담당자 선택으로 해결해야 함(TODO 5 작업 시 결정).
- 계정 설정 기타 탭 (Drive·CodeEdit·Github·MCP-Environments 비밀값·GlossaryManage·TaskCatalog, `AccountSettings.vue:22-61`) — 관리·비밀값 분리(TODO "넣지 않음").
- 용어집 (`/glossary`) — TODO "넣지 않음"(용어집·데이터 거버넌스).
- 정책 문서·에이전트별 지식 탭 (`/policy-document`, AgentChat 지식 탭 `AgentKnowledgeManagement.vue`) — F9 문서 RAG 넣지 않음(회의 L242-245).
- 에이전트 상세의 대화·학습·질문 탭 (`AgentChatInfo.vue:430-434`) — TODO "랩업(Claude Code)으로"(에이전트와 대화로 시험).
- 전략 설문 응답 (`/strategy/surveys/:requestId`) — 전략맵 인터뷰(processgpt-gaps O6)는 TODO 강의 목록에 선정되지 않음.
- 프로젝트 (`/project/:projectId`) — 사례와 무관.
- 개발용 (`/review-board-debug`, `/api/test`, `/lab/*`) — 화면 기능 아님.
- `/proposals` (Proposals·`components/ui/Proposal.vue`) — 채팅형 제안 화면, 용도 **미확인**(판정 보류, 개선안 대기 배지는 S13에서 다룸).
