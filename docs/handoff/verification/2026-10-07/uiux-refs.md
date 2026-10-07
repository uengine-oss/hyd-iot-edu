# UI/UX 참고 조사 — 규칙 12개와 출처 (A121, 2026-10-07)

계약: `docs/handoff/UIUX.md`(조사 범위·인수 조건 1~6). 화면별 적용안은 `docs/handoff/UIUX_PLAN.md`.
이 문서는 "어디서 무엇을 빌려 오는가"만 적는다. 제 취향으로 정한 값은 없고, 값마다 파일:줄 또는 URL을 붙였다.

## 0. 조사한 대상과 근거 위치

| 대상 | 버전·시각 | 읽은 방법 | 캡처 |
|---|---|---|---|
| process-gpt-vue3 최신 HEAD | `9b7391e` 2026-10-06 14:17 +0900 (`.evidence/reaudit/references-latest/process-gpt-vue3`, `git log -1`) | 코드 직접 읽음: `src/ds/README.md`, `src/ds/styles/tokens.css`, `src/ds/components/Pg{Card,Chip,Field,TextField,Tabs,AppShell,Alert,Button}.vue`, `src/components/ui/common/StatusChip.vue`, `src/components/apps/todolist/{SimpleInstanceList,TodoTaskItemCard,WorkItem,FormWorkItem,InstanceTimeline}.vue`, `src/components/ui/ActivityInputData.vue`, `src/components/BpmnUengineViewer.vue`, `src/components/customBpmn/dsPalette.js`, `src/utils/locales/ko.json` | 의존 서비스(Supabase·백엔드) 없이 화면을 띄울 수 없어 **캡처 없음** — 코드 수치로 대체 |
| Dify 실행 기록(History & Logs) | 문서 페이지 2026-10-07 열람 | WebFetch 본문 + 문서의 이미지 5장 저장 | `.evidence/a121/refs/dify-history-logs-1..5.png` |
| Camunda Tasklist | 문서 페이지 2026-10-07 열람 | WebFetch 본문 + 이미지 4장 저장 | `.evidence/a121/refs/camunda-{tasklist-page,task-tile,task-details-form,task-details-process}.png` |
| Temporal Web UI 타임라인 | 문서·블로그 2026-10-07 열람 | WebFetch 본문 + 블로그 이미지 3장 저장 | `.evidence/a121/refs/temporal-{full-timeline,parallel,retries}.png` |
| LangSmith 추적 | 문서 페이지 2026-10-07 열람 | WebFetch 본문(페이지에 화면 이미지 없음 — 로고뿐) | 캡처 없음 |
| 현재 포털 | 10탭 × 1440·1024, 각 탭 전체 길이 | `scripts/ui_capture_all_tabs.py` + 보조 스크립트 | `.evidence/a121/current/` (뒤 §3) |

출처 URL: Dify https://docs.dify.ai/en/guides/workflow/debug-and-preview/history-and-logs · Camunda https://docs.camunda.io/docs/components/tasklist/userguide/using-tasklist/ · Temporal https://docs.temporal.io/web-ui , https://temporal.io/blog/lets-visualize-a-workflow · LangSmith https://docs.langchain.com/langsmith/view-traces · process-gpt-vue3 https://github.com/uengine-oss/process-gpt-vue3

## 1. 규칙 12개 (번호는 UIUX_PLAN.md에서 R1~R12로 인용)

### R1 · 폭과 셸: 사이드바 고정 + 본문 가변, 본문 읽기 폭 상한
- process-gpt DS: 사이드바 272px, 본문 `minmax(0,1fr)`, 선택적 오른쪽 패널 565px, 상단바 52px (`PgAppShell.vue:33-41, 69-75`; `tokens.css:126-127` `--app-sidebar-w: 272px`, `--app-content-max: 768px`).
- 간소화 받은편지함은 목록 폭 상한 860px (`SimpleInstanceList.vue:295`).
- 현재 포털: rail 236px + 헤더 72px + 하단 64px (`styles.css:17-18`), `.view` 상한 1400px (`styles.css:342`).
- **적용**: 셸 치수는 유지(수업 화면이 이미 1440 기준으로 검증됨)하되, 글이 긴 패널(설명·요약·폼)은 768px 상한을 둔다. 1400px 전체 폭으로 글이 흐르는 현재 요약 문단(캡처 `decision-1440-full` p0)이 읽기 어렵다.

### R2 · 간격 토큰: 8px 격자, 카드 안쪽 16px, 카드 사이 8~12px
- `PgCard`: 헤더 `padding: 16px 16px 0`, 본문 `padding: 16px`, 푸터 `0 16px 16px`, 헤더 요소 gap 12px (`PgCard.vue:77-119`).
- 행 높이 32px, 행 간격 8px (`tokens.css:128-130` `--row-h`, `--row-gap`, `--row-px`).
- 받은편지함 행 `padding: 15px 13px`, gap 10px (`SimpleInstanceList.vue:218-221`).
- 현재 포털 토큰 `--s1..--s12`(4~48px), `--panel-pad: 24px`, `--row-pad: 16px` (`tokens.css:3-13`).
- **적용**: 포털 토큰은 유지하고 카드 안쪽을 `--s4(16px)`, 카드 사이를 `--s2~--s3(8~12px)`로 통일한다. 한 화면 안에서 24px·16px·10px가 섞인 곳(인스턴스 상세 `instances.js:356-366`, 조치 판단 결과 `enterprise.js:316-334`)을 없앤다.

### R3 · 카드: 제목 15px/semibold + 부제 13px muted + 본문 + 푸터, 테두리 0.5px, 모서리 8px
- `PgCard.vue:40-62`: `border-radius: var(--cds-radius)`(8px, `tokens.css:108`), 배경 `--cds-surface-2`(#fff), 기본 `hairline` = `0.5px solid var(--cds-border)`; `raised`는 그림자 `--cds-shadow-sm`; 클릭 가능한 카드는 `<button>`으로 렌더하고 hover에 테두리 진해짐 (`:63-71`).
- 제목 `--cds-font-size-heading` 15px / `--cds-font-weight-semibold` 580, 부제 footnote 13px muted (`PgCard.vue:88-97`; `tokens.css:92-104`).
- 업무 카드 구성 = 제목 / 분류 칩 / 인스턴스명 캡션 / 담당·날짜 / 설명 (`TodoTaskItemCard.vue:7-92`).
- Camunda 작업 카드도 같은 순서: 작업명 → 프로세스명 → 보조 설명 → 담당자·우선순위 → 생성일·기한 (캡처 `camunda-task-tile.png`, 문서 "task name, process name, context description, assignee, priority, creation date, due date").
- **적용**: 인수 조건 2의 "제목·핵심 값·상태 칩·한 줄 보조"를 이 순서로 고정한다. 현재 포털 `.item`(목록 행)과 `.hopt`(조치 카드)·`.ucard`(설비)·`.step`(단계)가 각기 다른 위계를 쓴다(`styles.css`, `hitl.css:225-267`).

### R4 · 상태 칩: 높이 24px, 모서리 6px, 톤 5종, 상태→색 대응표는 레포 그대로
- `PgChip.vue:39-84`: 높이 24px(sm 20px), 패딩 0 8px, radius `--cds-radius--xs` 6px, 톤 neutral/accent/success/warning/danger/brand = 배경 `--cds-bg-*` + 글자 `--cds-text-*`.
- 값: `--cds-bg-accent #cde2fb`/`--cds-text-accent #184f95`, `--cds-bg-success #caeac7`/`#006300`, `--cds-bg-warning #f9dca4`/`#734500`, `--cds-bg-danger #fad6d6`/`#8e2626`, neutral `hsl(0 0% 4.3% / 5%)`/`#52514e` (`tokens.css:49-69`).
- 상태→색 (`StatusChip.vue:46-82`): task `TODO grey · IN_PROGRESS blue · PENDING yellow · SKIPPED grey · CANCELLED red · DONE green`; instance `NEW grey · IN_PROGRESS blue · PENDING orange · DONE/COMPLETED green · CANCELLED red`.
- 상태→이름 (`ko.json` `statusChip` 절): `TODO=예정 업무 · IN_PROGRESS=진행 중 · PENDING=보류 중 · CANCELLED=취소 · DONE/COMPLETED=완료 · SKIPPED=건너뜀`. 아이콘 `mdi-circle / progress-clock / clock-outline / skip-next / check-circle / close-circle` (`StatusChip.vue:150-182`).
- Dify 실행 상태 띠: `STATUS ● SUCCESS` 초록 배경 띠에 소요 시간·토큰을 나란히 (캡처 `dify-history-logs-3.png`, `-4.png`). Temporal: 완료 초록 · 실패 빨강 (블로그 "green for Completed and red for Failed").
- **적용**: 현재 `.pill`은 사건 상태만 색이 있고 작업 상태는 모두 회색(`styles.css:550-592`, `instances.css:20-21`). 위 표를 그대로 옮기고 `SUBMITTED`(레포에 없음)는 "엔진 차례"라는 뜻이므로 IN_PROGRESS와 같은 파랑 계열로 둔다(r14-g2 §6 판정).

### R5 · 폼: 라벨 위·입력 아래, 라벨 13px medium, 필수 `*` 빨강, 도움말 1줄 12px, 입력 높이 34px
- `PgField.vue:1-10, 47-75`: label(13px, `--cds-text-secondary`, weight 500) → 슬롯(입력) → error(role=alert, danger) 또는 hint(12px muted); 세로 gap 6px.
- `PgTextField.vue:81-125`: 입력 높이 34px, 패딩 0 10px, radius 8px, 테두리는 `box-shadow 0 0 0 0.5px --cds-border-strong`, focus 1.5px accent.
- `PgButton.vue:72-95, 149-158`: 높이 32px(sm 28, lg 38), primary = 검정 배경 흰 글자, outline/ghost/danger 변형.
- Camunda 폼: 섹션 제목(굵게) 아래 라벨 위/입력 아래, 2열 격자, **Complete Task 버튼은 패널 우하단 고정** (캡처 `camunda-tasklist-page.png`, `camunda-task-details-form.png`).
- process-gpt 작업 화면: "중간 저장"·"제출 완료"는 폼 **위 오른쪽** (`FormWorkItem.vue:4-39`); 오류 경고는 맨 위 (`:45-51`); 이전 단계 입력은 접히는 읽기 전용 폼 (`ActivityInputData.vue:1-40`); 위험 행동은 확인 대화상자.
- **적용**: 인수 조건 3대로 라벨 위·입력 아래·필수 표시·도움말 1줄. 버튼 위치는 계약이 "우하단"을 명시했으므로 Camunda 방식(우하단)을 따르고, process-gpt의 "폼 위 오른쪽"은 쓰지 않는다. 입력 2개 이하는 카드 안 인라인(계약).

### R6 · 폼 섹션: 의미 단위로 나누고 섹션 제목을 붙인다
- Camunda 폼의 "Company details / Income details" 섹션 제목 (캡처 `camunda-tasklist-page.png`).
- 사용자 지시(UIUX.md 10-07 19:30): 사건 정보 / 선택 / 사유·담당.
- **적용**: 승인·검토·에스컬레이션 폼을 ① 사건(읽기 전용) ② 선택(카드·조치값) ③ 사유·담당(입력) ④ 행동(버튼) 네 묶음으로 고정. 섹션 사이 간격은 `--s6(24px)` 하나로.

### R7 · 목록↔상세: 왼쪽 목록(카드) + 오른쪽 상세, 상세는 헤더 한 줄(뒤로·제목·상태 칩·주 행동)
- Camunda: "On the left side of the page you can see task filters and the queue of tasks. On the right side, details of the selected task are displayed." 상세 헤더 = 작업명·프로세스명·담당 배지·주 행동, 탭 `Task | Process`, 오른쪽 요약 레일(생성일·후보·우선순위·기한) (캡처 `camunda-tasklist-page.png`).
- process-gpt `WorkItem.vue:2-65`: 뒤로가기 · 작업명(h5) · 상태 칩(x-small outlined) · 버전 칩 · 오른쪽 주 행동(위임 또는 다시 수행하기); 본문 5:7 (왼쪽 맥락 탭 / 오른쪽 폼) (`:93-296`).
- 현재 포털 `.split`은 300px/1fr (`styles.css` r14-g2 메모 :827-831)로 이미 같은 구조.
- **적용**: 유지. 상세 헤더를 한 줄로 고정(제목 + 상태 칩 + 보조 1줄)하고 지금처럼 h2 안에 id·경보·명령·승인자를 이어 붙이지 않는다(`app.js:490`).

### R8 · 실행 한 건의 상세는 3탭: 결과 / 상세 / 추적
- Dify: "Result" = 최종 출력, "Detail" = 원래 입력·최종 출력·메타, "Tracing" = "which nodes ran in what order, how long each took, and where data flowed" (WebFetch 본문; 캡처 `dify-history-logs-2.png` RESULT, `-3.png` DETAIL, `-5.png` TRACING).
- Tracing 행 = 아이콘 · 노드 이름 · 오른쪽에 `토큰 · 소요` · 상태 아이콘(초록 체크), 행마다 펼침 꺾쇠 (캡처 `-5.png`). Detail 상단 = `STATUS / ELAPSED TIME / TOTAL TOKENS` 3칸 띠, 아래 INPUT·OUTPUT 코드 패널(복사·확대 버튼) (캡처 `-3.png`). 노드 설정 패널에 `SETTINGS | LAST RUN` 탭 (캡처 `-4.png`).
- LangSmith: Trajectory / Turns / Details 세 보기; Details = "inputs, outputs, timing, token counts, errors, and metadata", 자식 run은 부모 아래 중첩 (WebFetch 본문).
- process-gpt `InstanceCard.vue:181-183, 366-373`: 인스턴스 탭 = 액티비티/프로세스/칸반보드/스케줄/채팅/소스/산출물.
- **적용**(B7): 인스턴스 상세 13섹션 → **결과 · 흐름 · 기록** 3탭(이름은 §PLAN 명칭표). 결과 = 결정·조치·종결 요약 + 변수(라벨 붙인 읽기 전용), 흐름 = 단계 카드(현재 `inst-tl`) + 승인/재작업/효과 패널(접기), 기록 = 작업 표 + 이벤트 목록(Tracing 행 형식: 이름 · 소요 · 상태 아이콘 · 펼침).

### R9 · 타임라인: 관련 이벤트는 한 줄(span)로 묶고, 길이=소요, 색=결과, 단일 이벤트는 점
- Temporal: "three connected events (ActivityTaskScheduled/Started/Completed) produce a single Activity row that spans the duration", "green for Completed and red for Failed", "Markers and Signals show as points", 호버 툴팁에 시작·종료·소요 (블로그 본문; 캡처 `temporal-full-timeline.png`: 행 라벨 왼쪽 열 + 시간축 + 초록 둥근 span + 점). 보기 전환 `History | Compact | JSON`, `Fit` 버튼.
- **적용**: 실시간 스트림(`liveStream.js:86-108`)의 `tool_usage_started/finished` 쌍을 한 행으로 묶어 소요를 오른쪽에(이미 `dur` 계산 있음 `:38-42`), `human_asked/response`·`error`는 점(단일 행). 전체 가로 시간축은 2차(우선순위 낮음).

### R10 · 빈 상태: 아이콘 + 굵은 한 줄 + 보조 한 줄, 한 화면에 한 번
- `SimpleInstanceList.vue:14-18`: `mdi-checkbox-marked-circle-outline` 34px + "지금 처리할 일이 없습니다." + "새 할 일이 배정되면 여기에 표시됩니다."; CSS `padding: 80px 20px`, gap 8px (`:278-289`).
- `FormWorkItem.vue:62-75`: 폼 없음 = 64px 아이콘 + h6 + body-2.
- **적용**: 인수 조건 5 "빈 상태 문구는 한 줄"은 굵은 한 줄로, 보조 줄은 행동이 있을 때만(예: "결함을 주입하면 여기에 나타납니다"). 현재 포털의 빈 상태는 문장 2~3개짜리가 많다(`instances.js:94, 280, 311`, `app.js:229, 369, 482`).

### R11 · 용어: 화면은 사용자 말, 내부 이름은 숨기거나 접는다
- process-gpt 화면 용어(ko.json): todolist→"업무 목록"·간소화 화면 "할 일", workitem→"현재 작업", TODO→"예정 업무", PENDING→"보류 중", complete→"제출 완료", rework→"다시 수행하기" (r14-g2 UI 패턴 메모 용어표). 레포도 상태 원문을 그대로 내보내는 곳이 있으나(`WorkItem.vue:19`, `InstanceCard.vue:34`) 사용자 기준(UIUX.md 명칭 기준)이 우선.
- Dify는 내부 id(`sys.workflow_run_id` 등)를 **Detail 탭의 INPUT 코드 패널 안에만** 둔다 (캡처 `dify-history-logs-3.png`).
- **적용**: 인수 조건 1. 명칭표는 UIUX_PLAN.md §2. id·원문 JSON은 "기록" 탭 또는 `<details>` 안에만.

### R12 · 탭·접기: 밑줄형 탭(36px) 또는 세그먼트(30px), 접기는 요약 한 줄 + 꺾쇠
- `PgTabs.vue:42-126`: segmented(배경 `--cds-bg-neutral`, 선택 항목 흰 배경+그림자) / underline(높이 36px, 선택 밑줄 2px `--accent-brand`), 탭에 개수 칩 가능.
- Dify Tracing 행의 펼침 꺾쇠, Temporal의 "Input and Results" 접힘 패널 (캡처).
- **적용**: 인스턴스 상세·조치 판단 결과의 2차 정보(규칙 판정 표 25행, 입력 데이터 표 20행, 감사 로그)는 접기 또는 탭 뒤로. 한 화면의 첫 1,000px 안에 "지금 결정·확인할 것"만 남긴다(사용자 지시 10-07 19:30).

## 2. BPMN 그리기 방식 — process-gpt-vue3가 쓰는 것
- `BpmnUengineViewer.vue:140-142`: `bpmn-js` `Modeler`와 `Viewer`를 import, `package.json:80-81` `bpmn-js ^17.9.1`, `bpmn-moddle ^8.1.0`. 레인은 `bpmn:Lane` 요소를 elementRegistry에서 찾아 `flowNodeRef`로 소속을 계산하고 참여자 툴팁을 만든다(`:350-397`). 캔버스 색은 SVG 속성이라 `customBpmn/dsPalette.js:89`가 `--bpmn-*` 토큰을 읽어 hex로 넘긴다(`tokens.css:306-331` 주석).
- 현재 포털: 손으로 그린 고정 SVG(`hitl.js:11-27`, 레인 6개·노드 12개 고정). 정의 v2.2(`it/process/definitions/anomaly_response_v22.json`)는 활동 9·이벤트 4·게이트웨이 2·흐름 15.
- 두 방식의 선택지는 UIUX_PLAN.md §4(사용자 결정 2).

## 3. 현재 포털 캡처(눈으로 확인한 범위)와 기계 검사
- 기본 도구 `scripts/ui_capture_all_tabs.py` → `.evidence/a121/current/<tab>-{1440,1024}.png` 20장 + `console.json` + `layout.json`. **한계**: 포털은 `<main>`이 안에서 스크롤해서(`styles.css:332-338` `overflow:auto`) full_page 캡처가 첫 화면(900px)만 담는다.
- 보조 스크립트(스크랩패드 `capture_deep.py`, 프로젝트에 넣지 않음): `body` 높이·`main` overflow를 풀고 설비 HYD-01 선택·판단 실행(`/api/agent/decide`는 규칙 엔진만 호출, `agentsvc/decide.py`에 LLM 없음)·인스턴스 선택 후 전체 길이 캡처 → `<tab>-{1440,1024}-full.png` 20장, 1300px 조각 `crops/` 37장, `deep-{1440,1024}.json`.
- 콘솔: 20탭 모두 `Failed to load resource: net::ERR_CONNECTION_REFUSED`만 1~2건 — FUXA(1881) 헬스 프로브(`layers.js:19`, `app.js:125-137`)가 꺼져 있어서 나는 것(헤더 "응답 없음: FUXA"). 포털 코드 오류·pageerror 0.
- 가로 넘침(`layout.json`): `ontology`·`process` 탭에서 12개 — 모두 `#ontoMap`·`.bpmn-scroll` 안의 SVG `path/rect/svg`로, 의도된 가로 스크롤 영역. 문서 폭(`docW`)은 1440/1024로 넘침 없음.
- 전체 길이 캡처는 두 번 돌렸다. 1차(레이아웃 해제 CSS가 rail을 본문 위에 겹치게 해 왼쪽 236px이 가려짐 — 폐기)에서는 조치 판단이 정상 결과(카드 4장, 권고 SOP-COOL-02 점수 +3.88, 규칙 판정 표, 입력 데이터 표)를 냈고 이를 눈으로 확인했으나 **그 파일은 2차 캡처로 덮어써 남아 있지 않다.** 2차(현재 `*-full.png`·`crops/`) 도중 다른 세션이 process 컨테이너를 재기동해(`docker ps`: `hyd-iot-edu-process-1 Up 9 minutes (unhealthy)`, `/healthz` 503 `consumer_dead`) 헤더가 "응답 없음: process, FUXA"가 되고 **인스턴스 목록이 비었으며**, 조치 판단은 "실행 가능한 대안 없음 … forecast source is stale or future-dated"로 나왔다(이는 agent 서비스의 예측 신선도 판정이며 UI 결함이 아님). 재시도(`current/retry/`)도 같은 상태. 따라서 정상 판단 결과·인스턴스 상세의 "현재 파일"은 없고, 인스턴스 상세는 `.evidence/reaudit/a109-report-ui/instance-detail-1440.png`(10-07 17:12)로, 조치 판단 정상 결과의 구성은 코드(`enterprise.js:311-336`)와 1차 캡처를 본 기록으로 서술한다. process가 돌아오면 `capture_deep.py`를 `ONLY=decision,instances RUN_DECISION=1`로 다시 돌려 교체할 것.
