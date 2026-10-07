# 2조 — 프론트엔드: 레포 2개 (HEAD: process-gpt-vue3 9b7391e 2026-10-06 · process-gpt-analytic a6dbb1a 2026-07-26)

읽기 전용 조사. HYD 파일 수정 없음. HYD 포털 `it/portal/www/` 실제 크기는 22개 파일, 7,000줄이다(`wc -l`; 지시서의 "6,700줄"과 다름).

**결론 먼저**
1. 진행 단계 계산(`instanceSteps.js`)만 레포 코드를 그대로 옮겼다. 나머지 화면(할 일·폼·인스턴스 상세·재작업·BPMN·온톨로지·스트림)은 HYD가 직접 만든 것이다. 레포 방식을 다른 데서 빌려 온 경우는 없다. 대신 **HYD가 혼자 만든 것 두 가지가 사용자에게 틀린 정보를 보여 준다.** (a) "업무 프로세스" 탭의 BPMN은 손으로 그린 고정 SVG(`hitl.js:11-27`)라서, 실제로 등록된 정의 v21과 노드가 다르다. 정의에 있는 escalate·select-timeout·compliance·gw:recovered가 그림에는 없고, 정의에 없는 `learn`이 그림에는 있다. (b) 상태 이름표가 레포와 반대로 붙어 있다. `TODO`를 "할 일"(`ui.js:45`)로 표시하는데, 레포는 같은 값을 "예정 업무"(`StatusChip.vue:106`, ko `statusChip`)라 하고, 화면에서 "할 일"이라 부르는 건 따로 있다(`SimpleInstanceList.vue:5`). `SUBMITTED`는 "검토 요청"(`ui.js:22`)으로 나온다. 실제로는 엔진 차례라는 뜻이다.
2. 인스턴스 모드에서 이상 확인 탭의 HITL 패널(`hitl.js:135-190`)은 결정 버튼을 그대로 보여 준다. 그런데 서버는 이 요청을 409로 거절한다(`main.py:561-564` "프로세스 인스턴스의 사람 작업에서 승인·복구하세요"). 같은 카드를 두 탭에서 고를 수 있는데 한쪽에서는 결정이 안 된다(코드로 확인, 실행 미검증).
3. 이전 기록 C02가 근거로 든 "실행 중 취소 = `FormWorkItem.vue` L954-964"는 불완전하다. 그 코드는 *미완료 초안이 있을 때 사람이 제출하면 확인 후 CANCELLED로 바꾸고 제출하는* 동작이다. 실행 중 멈춤 버튼은 `AgentMonitor.vue:68`(⏹)과 `stopTask` `:1217-1229`이다. HYD A097 버튼은 이쪽과 짝이며 결론은 그대로 유효하다.

---

## process-gpt-vue3 (9b7391e 2026-10-06, 스냅샷 d88f78c 대비: 변경 4파일 — HITL 질문 문구·재개)

`diff -rq src`의 차이는 4개다. 이 가운데 `agentEventTimeline.js`, `shared/hitlFeedback/index.js`, `views/markdown/AgentMonitor.vue`는 `diff -u`로 확인했다. 나머지 1개 `hitlFeedback.test.js`는 테스트 파일로, diff 본문을 읽지 않았다(커밋 제목 기준 추정: 회귀 테스트 추가).
- `humanQuestionText(data)`: `data.text || data.question`(`hitlFeedback/index.js:115-117`). SDK 에이전트는 질문을 `question`에 담기 때문에, `text`만 읽으면 빈 카드가 된다. → HYD `renderAskPanel`은 `d.text`만 읽는다(`instances.js:173`). 다만 HYD에서 질문을 쓰는 곳은 `runner.py:249` 하나뿐이고 여기서 `text`로 쓰므로 **현재는 무해**하다. deepagents 계열 SDK 에이전트를 붙이면 결함이 된다.
- `resumePatchForAnswer`: HUMAN_ASKED일 때만 feedback을 덧붙이고 `FB_REQUESTED`로 바꾼다(`:127-144`). `AgentMonitor.vue:1033-1044`에서 화면이 직접 `putWorkItem`을 호출한다. HYD는 서버 `human_response`(`instances.py:602-`)가 job_id·중복 답변을 검사한다 → **HYD가 더 엄격**하다(이전 판정 유지).
- HUMAN_ASKED 행을 받으면 진행 표시를 내린다(`AgentMonitor.vue:932-935`).

### 이 레포가 하는 방식 (흐름 순서, 파일:줄)
1. **진입**: 라우트 `/todolist`→`TodolistCard.vue`, `/todolist/:taskId`→`WorkItem.vue`, `/instancelist/:instId`→`InstanceCard.vue`(`router/MainRoutes.ts:28-55`). 설정 `simpleUi`를 켜면 할 일 목록이 `SimpleInstanceList`(인스턴스별로 묶은 받은편지함, `TodolistCard.vue:2`)로 바뀐다.
2. **작업 상세**: `WorkItem.vue` 로드(`:1955-1997`) — `getWorkItem`→`getRawDefinition(bpmn)`→`getActivitiesStatus`. ProcessGPT 모드면 항상 `FormWorkItem`을 쓴다(`:1985-1986`). 화면은 왼쪽 5칸 탭(프로세스=BpmnUengine 읽기 모드에 현재 활동 표시 `:174-198` / 액티비티 / 에이전트에 맡기기 / 유사 사례)과 오른쪽 7칸 폼(`:93-296`)이다. 헤더는 뒤로가기·작업명·**상태 원문 칩**(`:12-20`, `worklist.status`를 그대로 표시)·버전 칩, 오른쪽에 위임 또는 "다시 수행하기"(`:33-64`)가 있다.
3. **폼 렌더**: `DynamicForm`이 **form_def.html**(`<text-field name alias>`, `row-layout` 같은 사용자 정의 태그)을 렌더한다(`designer/DynamicForm.vue:1-60`). `fields_json`(`{text,key,type,disabled,readonly}`, `blueprint/executableForms.ts:20,103-109`)은 이전 단계 입력값 조회와 라벨에만 쓰인다(`FormWorkItem.vue:1135-1145`, `ActivityInputData.vue:155-171`).
4. **제출**: "중간 저장"·"제출 완료" 버튼이 폼 위 오른쪽에 있다(`FormWorkItem.vue:4-39`). 초안이 미완료면 확인 대화상자를 띄우고, 예를 누르면 `draft_status=CANCELLED`로 바꾼 뒤 제출한다(`:928-966`). 체크포인트를 모두 체크하지 않으면 막는다(`:973-993`). 이어서 `putWorkItemComplete`(`ProcessGPTBackend.ts:3130`)를 호출하고 `/instancelist/{id}`로 이동한다(`:904-907`). PENDING이면 `worklist.log`를 오류 경고로 보여 준다(`:45-51`).
5. **재작업**: 완료된 작업(`enableRework` `ProcessGPTBackend.ts:8380-`, COMPLETED/DONE만)에서 "다시 수행하기"를 누르면 `ReworkDialog`가 열린다. 범위는 라디오 3개(현재 단계만 / 참조하는 다음 단계 포함 / 모든 다음 단계, `ReworkDialog.vue:17-44,72-93`)이고, 활동 목록은 `/completion/get-rework-activities`에서 받는다(`WorkItem.vue:2309-2329`). 제출은 `/completion/rework-complete`(`:2330-2357`)로 간다. 반송·여기로 되돌리기는 ProcessGPT 백엔드에서 throw 또는 null을 낸다(`ProcessGPTBackend.ts:1362-1374,2745-2748`).
6. **에이전트 실행 중 멈춤**: `AgentMonitor.vue:68` ⏹ → `stopTask` `:1217-1229`(`putWorkItem({draft_status:'CANCELLED'})`, 화면이 직접 씀).
7. **인스턴스 상세**: `InstanceCard.vue` — 제목·**상태 원문 칩**(`:27-35`)·시작자·시작일시(`:88-108`). 탭은 액티비티/프로세스/칸반보드/스케줄/채팅/소스/산출물이다(`:366-373`). simpleUi는 대화(`InstanceTimeline`)와 산출물 두 칸에 크기 조절 손잡이를 둔다(`:138-176`).
8. **진행 표시**: `shared/instanceSteps.js`(328줄, 스냅샷과 동일)를 `InstanceFlow.vue`가 strip/pill/list 세 모양으로 그린다(`:1-135`). 라벨은 "내 차례"·"진행 중"·"건너뜀"·"조건에 따라 한 갈래로 진행했습니다"이다.
9. **내 차례(최신 방향)**: `InstanceTimeline.vue:32-90` — 대화 끝에 "내 차례입니다 — {작업명}", 그 자리 폼과 "제출"이 붙는다. DRAFT면 "초안 확인 후 제출해 주세요", 작업 중이면 "✻ 작업 중…" 상태 한 줄(`:14-30`).
10. **정의(BPMN) 보기**: 실제 정의의 BPMN XML을 bpmn-js 기반 `BpmnUengine`에 `isViewMode`, `currentActivities`, `taskStatus`를 넘겨 표시한다(`WorkItem.vue:174-198`).
11. **온톨로지**: `/ontology-explorer-new`→`OntologyExplorerNew.vue`. 위쪽 막대에 레이어 토글·검색·범례가 있고(`:4-43`), 그래프 상태 게이트(미설치/스키마 불호환/오류, `GraphHealthBanner.vue:1-30`), 노드가 너무 많을 때 렌더를 막는 가드(`:72-80`), NVL 계층(dagre)·force 레이아웃(`NvlCanvas.vue:58-127`), 상세/추적 패널(`:104-126`, 원인 역추적·기여 순추적 `NodeDetailPanel.vue:12-18`), 빈 레이어 칩(`:94-99`)이 있다. 저장소는 Apache AGE이고 노드 29·엣지 47종이다(`ontology/README.md`, `SCHEMA.md` §3-5). 레이어 5개는 `layerMapping.ts:47-61`.

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 진행 단계 계산 | `shared/instanceSteps.js` | `instanceSteps.js:1-231` | 같음(+세대 우선 `:152-153`) | 재작업 세대가 섞이지 않게 HYD가 확장 | 아니오 |
| 단계 표시 | `InstanceFlow.vue` strip/list, 내 차례 | `instances.js:307,327-333` 화살표 줄 | 비슷 | HYD는 `mineTaskId`를 넘기지 않아(`:303-304`) "내 차례"가 표시되지 않음 | 예(작음) |
| 할 일 목록 | 칸반 4열(예정/진행/보류·반송/완료) 또는 인스턴스별 받은편지함 | `renderTodo` `instances.js:91-113`, IN_PROGRESS만 | 다름 | HYD는 사용자 필터가 없는데 제목은 "나에게 배정된"(`index.html:160`) — 문구 틀림 | 예(문구) |
| 폼 렌더 | form_def.html → DynamicForm | `fields_json` 직접 렌더 `instances.js:125-135` | 다름 | 빌드 없는 정적 포털이라 사용자 정의 태그를 렌더할 수 없음. 필수 검사 `:149` | 아니오 |
| 이전 단계 입력 | `ActivityInputData` 읽기 전용 폼, 라벨 표시 | JSON `<pre>` 출력 `instances.js:138` | 다름 | 키 이름 그대로 나옴 → 사용자가 읽기 어려움 | 예 |
| 제출 | `putWorkItemComplete` → 인스턴스로 이동 | `/submit {output,by}` `instances.js:270-275` | 같음(역할) | HYD는 "확인자" 자유 입력(기본값 `OP-17`, `:9,140`) | 사용자 결정(로그인 없음) |
| 에이전트 질문 | AgentMonitor 질문 카드 + 선택지 + 클라이언트 재개 | `renderAskPanel` `:164-189` + 서버 재개 | 같음(화면)·HYD가 더 엄격 | `question` 필드는 읽지 않음(현재 무해) | 아니오 |
| 실행 중 멈춤 | ⏹ `AgentMonitor.vue:68,1217` | "실행 취소" `instances.js:352,379-387` + 서버 `/cancel` | 같음(역할) | HYD는 사유 기록·서버 검사 | 아니오 |
| 재작업 | 완료 작업 헤더 버튼 + 범위 3택 | 인스턴스 패널: 작업 고르기 → 영향 미리보기 → 역할·사유·확인 체크 `instanceRework.js:41-135` | 다름 | HYD 백엔드 계약(영향 미리보기·request_id 재생·효과 확인)이 더 안전. 시작 위치·선택 수는 레포가 쉬움 | 사용자 결정(진입점만) |
| 인스턴스 상세 | 탭 7개 또는 대화+산출물 | 한 페이지 13섹션 `instances.js:309-366` | 다름 | 내부 이름 노출: "변수 (variables_data)" `:363`, "작업 (todolist)" `:364`, "(events)" `:365`, draft_status·agent_orch·consumer 원문 `:351-352`, Neo4j `ROLE_BOUND`·`EXECUTES` `:499-500` | 예 |
| 상태 이름표·색 | StatusChip: TODO=예정 업무, PENDING=보류 중, 색 지정 | `ui.js:44-49`: TODO=할 일, PENDING=대기, SUBMITTED=검토 요청(`:22`). `.pill`에 인스턴스/작업 상태 색 없음(`styles.css:550-592`) | 다름 | "할 일" 두 뜻 충돌, SUBMITTED 의미 틀림, 모든 칩 회색 | 예 |
| 정의 BPMN | 실제 정의 BPMN 읽기 모드 | 고정 SVG `hitl.js:11-117`, 사건 상태로 칠함 `:30-45` | 다름 | 정의 v21과 노드 불일치(위 결론 1a) | 예 |
| HITL 결정 위치 | 작업 하나 = 화면 하나 | 이상 확인 탭 `hitl.js:135-215` + 인스턴스 탭 `instances.js:191-262` 두 곳 | 다름 | 인스턴스 모드에서 이상 확인 탭 버튼은 409 | 예 |
| 온톨로지 지도 | NVL 그래프, 레이어 5, 상태 게이트, 추적 | 레이어별 열 SVG `enterprise.js:7-14,103-186`, 이상 패턴 경로 강조 `:77-102` | 다름(자체) | 도메인 레이어(ISO 13374·DMN)가 달라 열 배치가 수업에 더 읽기 쉬움. 그래프 미적재·빈 레이어 안내 없음 | 아니오(빈 레이어 안내만 후보) |
| 실시간 이벤트 | 작업별 AgentMonitor, 도구 짝은 이름 LIFO + 폴백(`agentEventTimeline.js:160-229`) | 전역 SSE `liveStream.js:110-123`, `tool_use_id`로 짝 `:39-41,61` | 다름 | HYD 짝 맞추기가 더 정확 | 아니오 |

### 이전 주장 판정 (REFERENCE_ADOPTION C02 행, r13-group4 C02 절)
- "재작업 UI = WorkItem L2294-2357 ↔ instanceRework.js L107-135" → **맞음**(HEAD도 같은 위치. 이후 바뀐 파일은 4개뿐이다). 단 화면 흐름은 다르다(위 표).
- "폼 제출 FormWorkItem L928-1015 → putWorkItemComplete L3130-3176" → **맞음**.
- "실행 중 에이전트 취소(FormWorkItem L954-964)에 대응하는 포털 버튼 없음 → A097 반영" → **불완전**. 인용한 곳은 '초안 미완료 상태의 제출 확인'이다. 멈춤 버튼은 `AgentMonitor.vue:68`, `:1217-1229`이다. A097 결과는 AgentMonitor와 짝이며 유효하다.
- "checkpoints·DRAFT·위임 보류, 반송은 제품 백엔드도 미구현" → **맞음**(`ProcessGPTBackend.ts:1362-1374,2745-2748` 그대로).
- "사람 답변 재개는 vue3가 화면에서 직접 update" → **맞음**. HEAD에서 `resumePatchForAnswer`로 옮겨 갔지만 여전히 클라이언트가 쓴다.
- HYD 주석 "단계 계산은 instanceSteps.js 그대로"(`instances.js:6`, `instanceSteps.js:2-4`) → **불완전**. 세대 우선 비교(`:152-153`)와 `status` 필드(`:169`)를 추가했다.
- HYD 주석 "ProcessGPT와 같은 event_type·crew_type·data"(`liveStream.js:3`) → **불완전**. data 키는 cli-agent 규약(`tool`·`tool_use_id`, `process-gpt-cli-agent/core/events.py:52-68`)이다. vue3 타임라인은 `data.tool_name`을 읽는다(`agentEventTimeline.js:169,182`). HYD 포털 안에서는 일관된다.

### 읽지 않은 것
`Chat.vue`(507 KB), `ChatRoomPage`, `EventTimeline.vue` 본문, `KanbanColumn*`·`InstanceOutput`·`InstanceProgress` 본문, `BpmnUengine*` 렌더러 내부, `DynamicForm` 이후 필드 컴포넌트, `ProcessDefinition*`·디자이너, `OntologyExplorer.vue`(구판)·`strategy/OntologyExplorer`, `useBusinessOntology`·`impactTrace` 본문, `SCHEMA.md`는 목차와 §3만, `FullLayout`·`VerticalSidebar` 메뉴 항목, `hitlFeedback.test.js` 본문(diff 내용 미확인), 테스트 전부. 화면은 실행하지 않았다(렌더 확인 없음).

---

## process-gpt-analytic (a6dbb1a 2026-07-26, 스냅샷 8308db5 대비: 동일 — `backend/setup.sh`만 다름)

### 이 레포가 하는 방식 (흐름 순서, 파일:줄)
1. **진입**: `main.py:18-32` lifespan → `etl_scheduler(60s)`. `/api/dashboard/timeline/{id}`(`:258-`)는 dw 사본만 읽는다(r13 그대로).
2. **타임라인 구성**: `timeline_service.get_timeline_data`(`:145-384`). 인스턴스→활동→작업(todo)→job(작업 1건=job 1개)→이벤트 순서의 트리다. 이벤트 사이 간격이 60초를 넘으면 `leadtime` 구간을 끼워 넣는다(`:17,301-310`). 이름에 `finished`가 들어간 이벤트는 `marker`(`:286-288`). EventData는 비어 있다("DW에 상세 없음" `:297`).
3. **화면**: `frontend/src/views/Timeline.vue` — 위쪽에 인스턴스 선택, **상태 원문**(`:81-91`), 총 소요, `Tasks:`/`Events:` 영어 고정(`:100-101`), Lead Time 접기/펼치기(`:120-127`). 아래는 3칸(트리 w-80 / 간트 / 상세 w-96, `:132-146`). Tailwind를 쓰고, ko.json은 OLAP 화면만 번역한다(`i18n/locales/ko.json:1-40`).
4. **결함(새로 확인)**: 모든 조회 SQL이 f-string으로 경로 인자를 끼워 넣는다(`timeline_service.py:77,94,106,120,163`). SQL 주입 위험이다.

### HYD 대응 부품과 대조
| 단계/기능 | 레포 | HYD | 같음/다름 | 다르면 이유·영향 | 맞춰야 하나 |
|---|---|---|---|---|---|
| 실행 이력 원천 | 60초 ETL로 만든 dw 사본 | 원천 PG를 직접 읽고 SSE 커서로 받음(r13) | 다름 | HYD가 더 신선함 | 아니오 |
| 타임라인 트리·간트 | 활동→작업→job→이벤트 + 대기 구간 | 작업표의 시작→끝 시각(`instances.js:353`), 이벤트 목록(`:355`) | 다름 | HYD에는 소요·대기시간 집계·간트가 없음 | 사용자 결정(R12에 요구 없음) |
| 상태 표기 | 원문, 영어 고정 | 한국어 매핑(`ui.js`) | 다름 | HYD 쪽이 읽기 쉬움 | 아니오 |

### 이전 주장 판정 (REFERENCE_ADOPTION P01 행)
- "연결 주장 참(main.py:18-32,111-115,260-287)" → **맞음**(코드 동일. lifespan `:18-32`, 엔드포인트 `:258`).
- "ETL 전체 UPSERT·etl_state 부분 실패도 success·샘플 삽입" → **맞음**(동일 코드, `etl.py:1194-` 확인).
- "후보는 LAG 윈도 식뿐" → **불완전**. 화면 쪽 후보로 '대기 구간(60초 넘는 간격)' 표시 방식(`timeline_service.py:301-310`)이 하나 더 있다. 다만 원천은 HYD events를 쓰고 세대 순서로 정렬해야 한다.
- r13이 "frontend 전부 미열람"이라고 적은 범위 → 이번에 Timeline 화면·타입을 읽었다.

### 읽지 않은 것
`TimelineChartPanel.vue` 본문(leadtime 분기 `:65,112,242`만), `DetailPanel.vue` 본문, `Dashboard.vue`·`Performance.vue`, `stores/timeline.js`, `timeline_service.py:386-683`, OLAP 화면.

---

## 출처 판정
| HYD 기능(파일:줄) | 출처 | 맞는 레포의 방식(파일:줄) |
|---|---|---|
| 진행 단계 계산 `instanceSteps.js:1-231` | 맞는 레포 따름(vue3) | `shared/instanceSteps.js:1-328` |
| 단계 표시 `instances.js:307,327-333` | 맞는 레포 따름(계산), 그림은 자체 | `InstanceFlow.vue:1-135` |
| 할 일 목록 `instances.js:91-113` | HYD 자체 고안 | `TodolistCard.vue:1-37`, `SimpleInstanceList.vue:1-50` |
| 폼 렌더 `instances.js:115-155` | HYD 자체 고안 | `DynamicForm.vue`(form_def.html) |
| 이전 입력 `instances.js:138` | HYD 자체 고안 | `ActivityInputData.vue:1-40` |
| 에이전트 질문 응답 `instances.js:164-189` | 맞는 레포 따름(화면) + 서버 재개 | `AgentMonitor.vue:984-1044`, `hitlFeedback/index.js:115-144` |
| 실행 취소 `instances.js:352,379-387` | 맞는 레포 따름 | `AgentMonitor.vue:68,1217-1229` |
| 작업 닫기 `instances.js:352,370-378` | HYD 자체 고안(제품에 없음) | — |
| 재작업 `instanceRework.js:41-135` | HYD 자체 고안 | `ReworkDialog.vue:1-93`, `WorkItem.vue:52-64,2294-2357` |
| 인스턴스 상세 `instances.js:309-366` | HYD 자체 고안 | `InstanceCard.vue:1-316` 탭/simpleUi |
| 상태 이름표 `ui.js:44-49` | HYD 자체 고안(값은 제품 enum) | `StatusChip.vue:46-140`, ko `statusChip`(`ko.json:3816-`) |
| BPMN 보기 `hitl.js:11-117,221-235` | HYD 자체 고안 | `WorkItem.vue:174-198` BpmnUengine 읽기 모드 |
| HITL 결정 패널 중복 `hitl.js:135-215` | HYD 자체 고안 | 작업 하나 = 화면 하나 `/todolist/:taskId` |
| 조치 카드 선택 `instances.js:191-262` | HYD 자체(HYD 도메인, 레포 대응 없음) | — |
| 온톨로지 지도 `enterprise.js:7-220` | HYD 자체 고안 | `OntologyExplorerNew.vue:1-126`(+ontology-studio UI는 다른 조) |
| 실시간 스트림 `liveStream.js:1-143` | HYD 자체 고안(event 계약은 cli-agent 따름) | `AgentMonitor.vue` 실시간 구독 + `agentEventTimeline.js:160-229` |
| 실행 통계·타임라인 | 없음 | analytic `Timeline.vue`, `timeline_service.py:145-384` |

### 자체 고안 항목 비교 (정확성 · 재현성 · 속도·비용 · 실패 시 복구 · 사용자 이해)
- **BPMN 보기** — 레포는 실제 정의를 그대로 그려 정확하다. HYD는 고정 그림이라 정의를 바꿔도 그림이 따라 바뀌지 않고, v21과 이미 다르다. 재현성·속도는 차이가 없다. 사용자 이해: 그림과 실제 단계(인스턴스 탭의 단계 줄)가 달라 혼란을 준다. → **레포 쪽이 낫다.** 바꾸는 범위: `hitl.js` `bpmnSvg`를 정의 JSON(activities·events·gateways·sequences, 레인은 role)에서 자동 배치하도록 바꾸고, 사건 상태로 칠하던 것을 workitem 상태로 칠하게 한다. 약 1~2일. bpmn-js UMD를 쓰려면 정의→BPMN XML 변환이 더 필요하다.
- **상태 이름표·색** — 정확성: HYD의 `TODO`="할 일"은 "내 할일"(IN_PROGRESS)과 충돌하고, `SUBMITTED`="검토 요청"은 사람 검토로 오해하게 만든다. 레포는 예정 업무/보류 중으로 구분하고 색을 준다. → **레포 쪽이 낫다.** 범위: `ui.js:22,45,47` 문구 3개, `styles.css`에 상태 색 6줄 정도. 0.5시간. SUBMITTED는 레포에 이름표가 없어 HYD가 정해야 한다(예: "엔진 처리 중").
- **인스턴스 상세** — 정확성·복구 정보는 HYD가 더 많다(출처·세대·승인 전달·효과). 사용자 이해는 레포가 낫다. 탭으로 나누거나 대화+산출물로 묶고, 내부 이름(variables_data·todolist·events·ROLE_BOUND·draft_status 원문)을 숨긴다. → **화면 구성은 레포 쪽이 낫다**(내용은 유지). 범위: `instances.js:309-366`을 섹션 접기 또는 탭으로 나누고, 원문 값은 `<details>` 안으로 옮긴다. 1~2일.
- **HITL 결정 중복** — 인스턴스 모드에서 이상 확인 탭 결정은 실패한다(409). 레포는 작업 화면 하나에서만 결정한다. → **레포 쪽이 낫다.** 범위: `hitl.js` `renderHitl`에서 `/api/process/mode`가 instance면 버튼 대신 "프로세스 인스턴스 작업에서 결정" 이동 링크를 둔다. 0.5일.
- **이전 입력 표시** — JSON 원문 대 라벨이 붙은 읽기 전용 폼. → **레포 쪽이 낫다.** 범위: `instances.js:138`에서 생산 작업 폼의 `fields_json` 라벨로 키·값 목록을 만든다. 0.5일.
- **재작업** — 정확성·재현성·복구는 HYD가 낫다(영향 미리보기, `snapshot_token`, request_id 재전송, 효과 확인 대기). 사용자 이해는 레포가 낫다(완료된 작업에서 바로 누르고, 범위 3택). → **비슷하다/사용자 결정.** 진입점만 바꾸는 안: 단계 줄·작업 행에 "다시 수행" 버튼을 달아 `rwStart`를 미리 채운다. 0.5일.
- **폼 렌더(fields_json)** — 빌드 없는 정적 포털에서는 사용자 정의 태그 렌더가 불가능하다. 필수·타입 변환은 HYD가 직접 검사한다. → **HYD 쪽이 낫다**(이 환경에서).
- **할 일 목록** — 차이는 표시 범위뿐이다(예정·보류 열 없음). 문구 "나에게 배정된"은 틀렸다. → **비슷하다**(문구만 수정, 10분).
- **온톨로지 지도** — HYD 도메인 레이어(ISO 13374 진단·DMN)에 맞춘 열 배치는 결정적이라 수업에서 재현하기 쉽다. 레포의 상태 게이트·빈 레이어 안내만 쓸 만하다. → **비슷하다(차이 무해).**
- **실시간 스트림** — `tool_use_id`로 짝을 맞추는 HYD가 이름 LIFO 방식보다 정확하다. → **HYD 쪽이 낫다.**

---

## 조 요약
| 레포 | 핵심 차이 | 맞춰야 할 것 | 이전 기록 오류 |
|---|---|---|---|
| process-gpt-vue3 | 단계 계산만 이식. 상세·BPMN·상태 이름표는 HYD 자체이고, BPMN은 정의와 불일치 | ① BPMN을 정의에서 렌더 ② 상태 이름표(TODO·SUBMITTED·PENDING)·색 ③ 인스턴스 모드 HITL 결정 중복 정리 | C02 취소 근거 위치(FormWorkItem→AgentMonitor), "instanceSteps 그대로", "events data 같음" 불완전 |
| process-gpt-analytic | 스냅샷과 동일. 타임라인 트리·대기 구간 화면이 있음. SQL f-string 주입 위험 | 없음(대기 구간 표시는 사용자 결정) | P01 "후보는 LAG 식뿐" 불완전(대기 구간 표시) |

## UI 패턴 메모
- **디자인 시스템·토큰 위치**: vue3는 Vuetify 3.4.10(`package.json:156`)에서 자체 DS `Pg*` 31종으로 옮겨 가는 중이다(`src/ds/README.md:1-60`). 토큰은 `src/ds/styles/tokens.css`(`--app-sidebar-w` 272px, `--app-content-max` 768px, `--row-h` 32px `:126-128`, 표면 `#f9f9f7` `:42`), Vuetify 테마 다리는 `src/ds/vuetify-bridge/theme.ts`, `src/theme/LightTheme.ts:1-23`, scss는 `src/scss/_variables.scss`. analytic은 Tailwind(`frontend/tailwind.config.js`). HYD는 `tokens.css:1-51`(간격 4~48, `--accent #3859d6`, radius 8/12/18)과 `styles.css`.
- **레이아웃**: vue3 사이드바 275px(rail 70, `VerticalSidebar.vue:26-37`), PgAppShell은 사이드바+본문+선택적 오른쪽 패널 565px(`PgAppShell.vue:33-41`). HYD는 rail 236px + 헤더 72px + 아래 64px 그리드(`styles.css:17-18`), 본문 최대 1400px(`:342`), 목록·상세 300px/1fr(`:827-831`).
- **작업 화면**: 헤더 한 줄(뒤로·작업명·상태 칩·버전 칩·오른쪽 주 행동) `WorkItem.vue:2-65`, 본문 5:7(왼쪽 맥락 탭 / 오른쪽 폼) `:93-296`.
- **폼**: 제출·중간 저장은 폼 위 오른쪽(`FormWorkItem.vue:4-39`). 오류 경고(PENDING 사유)가 맨 위(`:45-51`), 이전 단계 입력은 접히는 읽기 전용 폼(`ActivityInputData.vue:1-40`), 체크포인트는 폼 아래(`:113-118`), 위험 행동은 확인 대화상자(`:196-214`). HYD는 라벨에 `*`/`(선택)`(`instances.js:134`), 제출 버튼은 폼 끝(`:141`).
- **목록·카드**: 업무 카드 = 제목 / 분류 칩 / 인스턴스명 캡션 / 아바타+"내 업무"+날짜 / 설명. 마감 임박·지남은 테두리 색(`TodoTaskItemCard.vue:7-12,16-92`). 받은편지함 행 = 아이콘 / 제목+"새 할 일 n" 배지 / 최근 업무 / 상태 칩+상대 시각+"할 일 n개" / 꺾쇠(`SimpleInstanceList.vue:20-50`).
- **상태 칩**: `StatusChip.vue:46-140` — 진행 중 파랑, 보류 주황/노랑, 완료 초록, 취소 빨강, 예정 회색. 아이콘은 `:150-182`. HYD `.pill`은 사건 상태만 색이 있다(`styles.css:550-592`).
- **빈 상태**: 아이콘 + 굵은 한 줄 + 보조 한 줄("지금 처리할 일이 없습니다." / "새 할 일이 배정되면 여기에 표시됩니다." `SimpleInstanceList.vue:13-17`), 폼 없음 64px 아이콘(`FormWorkItem.vue:62-75`), 온톨로지 "적재된 데이터 없음" 칩(`OntologyExplorerNew.vue:94-99`).
- **진행 표시**: 가로 띠/한 줄 알약(끝난 수/전체)/세로 체크리스트, 분기는 "또는"으로 이은 갈래(`InstanceFlow.vue:1-135`). 내 차례 블록은 대화 끝(`InstanceTimeline.vue:32-90`).
- **용어표(내부 → 화면, vue3 ko.json 절)**: todolist → "업무 목록"(`todoList.title` `ko.json:513-`)·간소화 "할 일"(`SimpleInstanceList.vue:5`) / workitem → "워크 아이템"(`InstanceCard` `:2974-`)·"현재 작업"(`WorkItem.resultInput` `:2585-`) / activity → "액티비티" / instance → "인스턴스" / TODO → "예정 업무" / IN_PROGRESS → "진행 중" / PENDING → "보류 중"·"보류/반송" / DONE → "완료" / CANCELLED → "취소" / SKIPPED → "건너뜀"(`statusChip` `:3816-`) / complete → "제출 완료"·save → "중간 저장"(`FormWorkItem` `:4086-`) / rework → "다시 수행하기"·"재작업 범위 설정"(`ReworkDialog` `:4266-`) / agent run → "에이전트에 맡기기" / checkpoints → "체크포인트" / delegate → "위임하기" / output → "산출물". 레포도 상태 원문을 그대로 노출하는 곳이 있다(`WorkItem.vue:19`, `InstanceCard.vue:34`, analytic `Timeline.vue:90`).
- **HYD 용어 현황**: "내 할일 · todolist · IN_PROGRESS"(`index.html:160`), "변수 (variables_data)", "작업 (todolist)", "(events)"(`instances.js:363-365`), "온톨로지 Execution 레이어"·`ROLE_BOUND`·`EXECUTES`·`ASSIGNED_TO`(`:485,499-500`), 배너 `agent_orch=cliagents`·`fetch_pending_task`(`:86`), "다리"(`:84`). 수업용 해설이 목적이라면 원문은 `<details>` 안에 두고, 겉에는 화면 이름을 쓰는 것을 권고한다.
