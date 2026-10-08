# U7 포털 셸 (A5) — 메뉴 묶음 · 상단바 · 해시 주소 · 새 화면 mount 계약

범위: 메인 `TODO.md` 확정 TODO §0·§1의 화면 이름, **A5**(포털 정리: 메뉴 묶음·주소 유지·토스트·확인 대화상자·빈/로딩/오류 통일).
기존 화면 로직은 바꾸지 않았다. 셸은 `selectTab`을 한 번 더 감싸고, 새 화면은 컨테이너만 둔다.

## 1. 원본 대조 (process-gpt-vue3, 데이터로만 읽음)

| 원본 파일:줄 | 원본이 하는 일 | HYD에서 한 것 | 차이 |
|---|---|---|---|
| `src/router/MainRoutes.ts:28-59` | `/todolist`, `/todolist/:taskId`, `/instancelist/:instId` — 경로가 화면과 대상(작업·인스턴스)을 정한다 | `#/<화면>`, `#/instances/<id>`, `#/instances/<id>/task/<taskId>` | 빌드 없는 정적 포털이라 vue-router 대신 해시. task는 처리 건 아래에 둔다(사건 한 건 = 인스턴스 하나, 그 안의 task) |
| `src/layouts/full/vertical-sidebar/VerticalSidebar.vue:115-117` | 머리글(header) 묶음 + 항목(NavGroup/NavItem) | `.navgroup` 머리글 7개 + 버튼 | 접기 없는 한 줄 목록(23항목, 넓은 화면은 34px 행) |
| `src/layouts/full/vertical-header/VerticalHeader.vue:359-368` | 상단 오른쪽 검색 · 알림(NotificationDD) · 프로필(ProfileDD) | 상단 오른쪽 시뮬레이션 시각 · "나" 자리 · 알림 종 | 검색 없음(화면 수가 적음). 프로필 → "나"(U5가 채움) |
| `VerticalHeader.vue:146,224` | `update-notification-badge` 이벤트로 배지 즉시 갱신 | `hyd:badge` 이벤트 + 5초 주기 | 같은 방식 |

## 2. 메뉴 (수강생 동선) — 순서 = 이전/다음 화면 순서

| 묶음 | 화면(메뉴 키 → 주소) | 상태 |
|---|---|---|
| 작업 | 내 작업함 `inbox` · 처리 건 `instances` | inbox는 새 자리(U5) |
| 설비 | 결함 시뮬레이션 `scenario` · 이상 확인 · 조치 `incidents` · 실시간 모니터링 `trends` | 기존 |
| 판단 | 조치 판단 규칙 `decision` · 손익 · What-if `whatif` · 승인과 실행 `process` | whatif 새 자리(U12) |
| 지식 | 지식 지도 `ontology` · 조치 방법 `skills` · 지식 관리 `knowledge` · 데이터 연결 `fabric` | fabric 새 자리(U13) |
| AI 구성 | 에이전트 `agents` · 도구(MCP) `mcp` · 시험 비교 `compare` · 판단 채점 `eval` | 새 자리(U2 · U2 · A10 · A4) |
| 성과 | KPI `kpi` | 새 자리(U11) |
| 시스템 | 홈 `main` · 시스템 구성 `home` · 관리 `admin` | 기존 |

기존 12개 탭은 모두 키를 그대로 두고 새 묶음으로만 옮겼다(`data-tab` 불변 → `selectTab('<키>')`, `main.js` 바로가기, 녹화 훅 그대로).
"이상 확인 · 조치"는 기존 화면 이름을 유지했다(용어 `nav.incidents`).

## 3. 새 화면 mount 계약 (다른 단위가 지킬 것)

컨테이너: `index.html`에 이미 있다. 단위는 **새 파일 하나**(예: `inbox.js`)를 만들고 `index.html`의 `shell.js` 줄 **위**에 `<script>`만 더한다.

| 메뉴 키 | 섹션 | 컨테이너 id | 전역 |
|---|---|---|---|
| inbox | `#view-inbox` | `inboxView` | `window.hydInbox` |
| agents | `#view-agents` | `agentsView` | `window.hydAgents` |
| mcp | `#view-mcp` | `mcpView` | `window.hydMcp` |
| compare | `#view-compare` | `compareView` | `window.hydCompare` |
| eval | `#view-eval` | `evalView` | `window.hydEval` |
| whatif | `#view-whatif` | `whatifView` | `window.hydWhatif` |
| kpi | `#view-kpi` | `kpiView` | `window.hydKpi` |
| fabric | `#view-fabric` | `fabricView` | `window.hydFabric` |

```js
window.hydMcp = {
  mount(el) { /* 처음 열 때 한 번. el 은 비어 있다. 반환이 Promise 면 reject 시 셸이 오류 블록 + 다시 시도 */ },
  show(el)  { /* 선택: 두 번째 방문부터 매번(새로 읽기) */ },
};
```

- 화면 제목(`<h1>`)은 셸 섹션에 이미 있다. `mount`는 그 아래 컨테이너만 채운다.
- 전역이 없거나 `mount`가 없으면 셸이 "준비 중" 빈 블록을 둔다(뒤가 빈 버튼 없음). 나중에 정의되면 다음 방문 때 mount한다.
- `mount`가 던지거나 reject하면 "화면을 그리지 못했습니다 + 사유 + 다시 시도"를 보인다(폴백 성공 없음).
- 주기 갱신은 `state.tab === '<키>'`일 때만(기존 화면과 같은 방식).
- 내 작업함 전용: `hydInbox.badge()` → 숫자 또는 Promise<숫자>(새 알림 수, 0이면 배지 숨김), `hydInbox.mountMe(el)` → 상단 "나" 자리(`#shellMe`)를 채움.
  읽음 처리 뒤 `window.dispatchEvent(new Event('hyd:badge'))`로 배지를 바로 갱신한다.

## 4. 해시 주소

| 주소 | 열리는 곳 |
|---|---|
| `#/` · `#/main` | 홈 |
| `#/<키>` | 메뉴의 그 화면 (§2) |
| `#/instances/<처리 건 id>` | 처리 건 화면에서 그 처리 건 선택 |
| `#/instances/<처리 건 id>/task/<task id>` | 그 처리 건 + 그 task |

- 메뉴 · 이전/다음 · 코드에서 `selectTab()`을 부르면 주소가 바뀌고(기록 추가) 뒤로 가기가 된다. 새로고침하면 같은 화면이 열린다.
- 처리 건 화면 안에서 고른 처리 건 · task는 1초마다 주소에 반영된다(기록을 쌓지 않고 바꿔 씀) → 그 주소를 복사해 링크로 보낼 수 있다.
- 없는 화면 주소는 홈으로 바꾸고 토스트로 알린다. `#/`로 시작하지 않는 해시(본문 건너뛰기 `#content`)는 주소로 보지 않는다.
- 다른 화면에서 링크를 만들 때: `<a href="#/instances/${id}/task/${taskId}">` 또는 `hydShell.href({tab:'instances', inst:id, task:taskId})`, 코드 이동은 `hydShell.navigate('#/instances/…')`.
  (U2 MCP 호출 기록 작업본의 `link`도 이 형식을 쓴다.)

### task 경로 → `window.hydInstances` 훅 (A1이 붙일 것)

셸은 다음 순서로 처리 건 화면에 넘긴다(`shell.js` `openInstance` · `instanceRoute`):

1. `hydInstances.openTask(instId, taskId|null)`가 있으면 → `selectTab('instances')` 뒤 이것만 부른다. A1이 task 상세(입력 · 판단 · 도구 호출 · 출력 · 넘긴 값)를 연다.
2. 없으면 → `hydInstances.I.sel = instId; I.taskSel = taskId`를 맞춘 뒤 `selectTab('instances')`(기존 `load(true)`). 지금 화면에서 taskSel은 "내 차례" task 선택에 쓰인다.
3. 주소 반영: `hydInstances.route()`가 `{inst, task}`를 주면 그것을, 없으면 `{inst: I.sel, task: I.taskSel}`을 읽는다.
   A1이 task 상세를 별도 상태(예: `I.stepSel`)로 두면 `route()`를 같이 주어야 새로고침 때 그 task가 다시 열린다.

## 5. 공통 UI (ui.js 끝에 덧붙임, 위 UI 객체는 그대로)

| 함수 | 쓰임 |
|---|---|
| `UI.empty(title, sub)` | (기존) 빈 상태 |
| `UI.loading(text?)` | 로딩 블록 — `.empty`와 같은 자리 · 크기, 회전 표시(움직임 줄이기 설정이면 멈춤) |
| `UI.errorBlock(title, reason, {retry})` | 오류 블록 — 무엇을 못 했나 + 사람이 읽을 사유 + 선택 "다시 시도"(`[data-retry]`에 붙인다) |
| `UI.toast(msg, {tone:'ok'|'neg'|'neutral', timeout})` | 아래쪽 한 줄 알림, 같은 문구는 하나만 |
| `await UI.confirm({title, body, ok, cancel, danger})` | 확인 대화상자(`<dialog>`), true/false. Esc · 취소 = false, 기본 초점은 취소 |
| `UI.icon('inbox'|'agent'|'tool'|'compare'|'score'|'whatif'|'kpi'|'fabric'|'bell'|'user')` | 새 아이콘(기존 아이콘은 그대로) |

## 6. 반응형 · 다크모드 · 언어

- 반응형: 기존 규칙(1200/1000/720px) 그대로. 721px 이상에서만 메뉴 행을 34px로 줄였고(23항목이 한 화면), 720px 이하 서랍 메뉴는 44px 터치 높이 유지.
  "나"는 720px 이하에서 아이콘만, 토스트는 좌우 16px 꽉 차게.
- 다크모드: 현재 포털 CSS에 다크모드 규칙이 없다(`prefers-color-scheme` 0건). 셸 CSS는 `tokens.css` 색만 써서 토큰에 다크 값이 들어오면 따라간다.
- 화면 문구는 모두 한국어(`UI.terms`의 `nav.*` · `shell.*` · `dialog.*`). 주소의 메뉴 키(영문)는 화면에 나오지 않는다.

## 7. 바꾼 파일

- `it/portal/www/index.html` — 메뉴 7묶음, 상단바 `#pageGroup` · `#shellMe` · `#shellBell`, 새 화면 섹션 8개, `shell.css` · `shell.js` 연결
- `it/portal/www/ui.js` — 끝에 덧붙임(용어 · 아이콘 · loading · errorBlock · toast · confirm)
- `it/portal/www/shell.js` (새) — 라우팅 · mount · 상단바
- `it/portal/www/shell.css` (새)

## 8. 시험

- `node --check it/portal/www/*.js` — 전부 통과(새 `shell.js`, 덧붙인 `ui.js` 포함).
- 브라우저(Playwright Chromium, `python3 -m http.server`로 `it/portal/www`만 띄움 — 서비스 없음, 화면 셸만 판정).
  스크립트 · 결과 · 화면: `.evidence/A5-u7-shell/`(`check.py` → `check.json`, `shots.py` → `strip-*.png`; `.evidence`는 git 제외).

| 확인 | 결과 |
|---|---|
| 메뉴 20개(기존 12 + 새 8)를 차례로 누름 | 모두 해당 `#view-<키>` 표시, 주소 `#/<키>`, 제목 · 묶음 이름 맞음, 페이지 오류 0 |
| 새 화면 8개, 전역 없음 | "준비 중" 빈 블록 |
| `#/decision`으로 새로 열기 | 조치 판단 규칙 화면 |
| `#/instances/abc-123/task/t-9`로 새로 열기 | 처리 건 화면, `I.sel=abc-123`, `I.taskSel=t-9`, 주소 유지 |
| `#/nope` | 홈으로 바뀌고 토스트 "없는 화면 주소입니다…" |
| 본문 건너뛰기(`#content`) | 화면 그대로(주소로 보지 않음) |
| `#/kpi` → 메뉴로 판단 채점 → 뒤로 | `#/kpi`, KPI 화면 |
| `location.hash='#/agents'` | 에이전트 화면 |
| 가짜 `hydMcp.mount/show` | mount 1회, 두 번째 방문에 show 1회 |
| `mount`가 던짐(`hydCompare`) | "화면을 그리지 못했습니다 / 시험용 실패 사유 / 다시 시도" — 일부러 깨뜨려 잡힘 |
| 가짜 `hydInbox.badge()=3`, `mountMe` | 배지 3, "나" 자리에 내용 |
| `UI.confirm` Esc / 확인 | false / true |
| 1440 · 1280 · 1024 · 390px | 가로 넘침 0, 서비스 상태 줄이 길어도 알림 종 · "나"가 화면 안 |

미검증: 서비스를 띄운 실제 화면(통합 검증 때 메인이 확인). 기존 `scripts/ui_navigation.py`는 9개 탭 · "n / 9"를 가정하는 옛 스크립트라 새 순서(20개)에 맞지 않는다 — 통합 검증 때 갱신 필요.
