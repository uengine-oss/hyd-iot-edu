# U5 — 나 · 내 작업함 · 포털 안 알림 (확정 TODO A3, 랩업 L20, 실라버스 4·44)

범위(메인 `TODO.md` 확정 TODO §0·§1 A3·§2 L20): "나" 선택 → 나에게 온 task → 판단까지 10초. 완료 기준: 담당자별 작업함, 권한 낮은 승인 403 유지, 알림 생성·읽음.
범위 밖(지시대로 만들지 않음): 위임·수동 재배정(vue3 `DelegateTaskForm`), 외부 알림(Mattermost — TODO §4 D, 55행), 로그인.

## 1. 원본(process-gpt-vue3)과 HYD 차이

| 원본 파일:줄 | 원본이 하는 일 | HYD에서 | 차이와 이유 |
|---|---|---|---|
| `src/router/MainRoutes.ts:27-29` `/todolist` → `TodolistCard.vue` | 내 할 일 목록 | 포털 메뉴 "내 작업함"(`#view-inbox`, `window.hydInbox.mount(el)`) | 차이 있음, 유지 — 정적 포털(vue 없음) |
| `src/components/api/ProcessGPTBackend.ts:1407-1440` `getWorkList` (`todolist` 를 `user_id like` 로 거름) | 로그인 사용자 email 로 작업을 거름 | `GET /api/inbox?user_id=` (`procsvc/inbox.py:151` `inbox_view`): 나에게 배정된 것(me) + 내 역할 공용(role) + 내 역할 처리 건의 AI 질문, 처리 건 이름·단계·경과(`elapsed_s`)·기한·링크 | HYD 에 로그인이 없어 "나"를 고른다(브라우저 `localStorage hyd.me`). 작업의 `user_id` 는 정의의 역할 바인딩(`procsvc/engine.py:324`)이라 역할 → 사람 해석이 먼저 필요했다(아래 업무분장) |
| `src/views/work-assignment/WorkAssignment.vue:122` 담당자 열 | 레인(역할)마다 담당자 | `role_members` 표(migration `20261008000029_inbox_assignment.sql`) + `GET /api/inbox/assignments`(읽기) + 작업함 접기 "업무분장 — 역할마다 사람" | 포털은 읽기만(편집 버튼은 원본도 숨김 `:155`). 바꾸는 곳은 seed/랩업 |
| `src/router/MainRoutes.ts:752-755` `/notifications`, `src/views/notifications/NotificationsPage.vue:130-150`(목록·모두 읽음), `:54,66,110`(안 읽음 표시·수), `:196-201`(누르면 읽음 + 이동) | 알림함 | 작업함 "알림" 탭: 목록·안 읽은 수·한 건 읽음(누르면 읽음 + 그 단계로)·모두 읽음, 상단 단추(`window.hydInbox.badge()`)에 안 읽은 수 | 원본 `is_checked` ↔ HYD 기존 표 `notifications.is_read`(`20261003000001_process_engine.sql:234-246`). 원본은 Supabase 실시간 구독, HYD는 같은 SSE 생성기(`instance_mode.event_stream`)로 `GET /api/inbox/notifications/stream` |
| `ProcessGPTBackend.ts:3890-3905` `setNotifications` (같은 url 미확인 일괄 읽음) | 읽음 처리 | `POST /api/inbox/notifications/read {user_id, ids?}` — 나 + 내 역할 앞으로 온 것만 바꾼다(남의 알림 id 를 주면 0건) | 같은 url 일괄은 하지 않음(한 건씩·모두) |

알림을 만드는 곳(원본은 엔진이 `notifications` 에 씀):
- 사람 단계 도착 — `inbox.apply_advance`(`procsvc/inbox.py:78`)가 흐름이 사람 단계에 닿는 다섯 자리에서 불린다: 시작 `instances.py:220`, 단계 처리 `:335`, 타이머 `:654`, 승인 전 중단·상급자 `:846`, 재작업 `rework_runtime.py:94`. 알림은 커밋 뒤(`_after_commit`)에 쓴다 — 롤백된 전이는 알림을 남기지 않는다.
- 에이전트 질문 — 기존 워커가 쓴다(`it/agent-worker/worker/runner.py:320`, 대상 `role:operator` `:385-388`). 역할 앞으로 온 알림은 그 역할 구성원 모두가 본다(`inbox.user_ids_for`). 워커 url `/todolist/<id>` 는 목록 API 가 처리 건 링크로 풀어 준다(`inbox.with_links`, 작업이 없으면 `link_error` 사유).
- 내 처리 건 종결 — 처리 건 참여자(역할은 구성원으로 펼침, "나"로 승인한 사람 포함)에게 한 번씩, 끝난 곳은 종료 이벤트 이름("끝난 곳: 종결").

## 2. 동작 규칙 (판정할 수 있게)

- **역할 → 사람(업무분장)**: 역할에 사람이 한 명이면 단계가 열릴 때 그 사람(`user:*`)에게 바로 배정하고 이력(`task_assignments`, kind `auto`)과 `assignees[].resolution=sole-member` 를 남긴다. 여럿이면 역할 공용(user_id 는 역할 그대로) — 구성원 모두의 작업함에 뜨고 각자 알림. 아무도 없으면 역할 그대로 남고, 작업함 응답의 `unassigned_roles` 와 화면 문구 "담당자가 없는 역할 … 누구의 작업함에도 뜨지 않습니다"로 알린다(조용한 성공 금지).
  - 비유: 업무분장은 "부서 대표 전화". 한 명뿐인 부서는 그 사람 휴대폰으로 바로 돌리고, 여럿이면 부서 공용 전화로 울린다.
  - 체크 질문: 운전원이 2명일 때 조치 선택 단계가 김운전·최운전 둘 다의 작업함에 뜨는가? 생산관리자가 1명일 때 상급자 확인 단계의 담당이 "이생산"으로 보이는가?
- **승인자 = 나**: "나"를 골랐으면 승인 폼의 자유 입력(승인자 이름)이 "김운전 (나)"로 바뀌고 역할 선택은 내 역할만 보인다(`enterprise.js` `whoFields` → `inbox.js` `whoFields`). 서버는 두 가지를 다 본다: ① `by` 가 `user:*` 면 그 사람이 내세운 역할의 구성원인지(`inbox.check_actor`, `instances.py:480`, 아니면 403 "김운전 님은 생산관리자 역할이 아니어서 …") ② 역할 등급이 카드 승인 역할 이상인지(기존 `hooks.approve_decision`, 아니면 403 "승인 권한 …"). 자유 입력(회귀 검사기 `OP-17` 등)은 ①을 건너뛰고 ②만 — 기존 검사기 호환.
  - 체크 질문: 김운전으로 "팬 최대 + 부하 80 %"(생산관리자 승인 카드)를 결정하면 거부되고 작업이 그대로 열려 있는가? 이생산으로 바꾸면 같은 카드가 승인되고 기록에 "이생산 승인 접수"가 남는가?
- **링크**: 작업함 행·알림은 `#/instances/<처리 건 id>/task/<작업 id>` 로 간다. 셸 라우터(U7)가 없을 때도 `inbox.js` 의 `hashchange` 가 처리 건 화면을 열고 그 단계를 고른다(`instances.js:587` `hydInstancesOpenTask`). 종결 알림은 `#/instances/<id>`.
- **실시간**: `GET /api/inbox/notifications/stream?user_id=` — 나 + 내 역할 앞으로 온 알림만 DB 에서 골라 보낸다(`list_notifications_since(..., tenant_id, user_ids)`), 남의 알림은 한 줄도 보내지 않는다. 새 알림이 오면 포털이 작업함·알림·안 읽은 수를 다시 읽는다. 끊기면 "실시간 꺼짐"을 보이고 15초 뒤 다시 붙는다.
- **이름**: 사람 이름을 `UI.performers` 에 등록해 포털 전체의 "누가"(작업 담당·승인자·기록 "approval accepted by user:…")가 id 대신 이름으로 보인다.

## 3. 바꾼 파일

| 파일 | 내용 |
|---|---|
| `it/process/procsvc/inbox.py` (새) | 업무분장 해석 `resolve`, 엔진 훅 `apply_advance`, 알림 `_notify_task`·`_notify_end`, 승인자 검사 `check_actor`, 작업함 `inbox_view`, 알림 링크 `with_links`, 업무분장 보드 |
| `it/process/procsvc/inbox_api.py` (새) | `/api/inbox/users` · `/api/inbox` · `/api/inbox/assignments` · `/api/todolist/{id}/assignments` · `/api/inbox/notifications`(목록·unread-count·read·stream) |
| `it/process/procsvc/procdb.py` | Repo 계약 + Memory/Pg: role_members·task_assignments·사용자별 알림 조회·읽음·스트림 커서, `insert_notification` 이 저장 행을 돌려줌, 메모리 전이 롤백에 배정 이력 포함 |
| `it/process/procsvc/instances.py` · `rework_runtime.py` | 다섯 전이 자리에서 `inbox.apply_advance`, `select` 에서 `inbox.check_actor` + 승인한 사람을 참여자로 |
| `it/process/procsvc/instance_mode.py` | `event_stream` 이 다른 표(알림)를 흘릴 수 있게 `fetch`·`ts_key`·`history` 인자(기본값은 기존 그대로) |
| `it/process/procsvc/main.py` | `inbox_api.mount(app)` 두 줄 |
| `it/supabase/migrations/20261008000029_inbox_assignment.sql` (새) | `role_members`, `task_assignments`(처리 건 FK 로 함께 지워짐, kind `auto`), 알림 인덱스, RLS |
| `it/supabase/seed.sql` | 사람 사용자 4명(김운전·최운전 = 운전원, 이생산 = 생산관리자, 박정비 = 정비관리자)과 업무분장 — `reanchor_scenario_times()` 앞(마지막 줄 유지) |
| `it/portal/www/inbox.js` (새) | `window.hydInbox = { mount(el), badge(), me(), whoFields(), byField() }` — 나 고르기·내 작업·알림·업무분장 접기·SSE |
| `it/portal/www/index.html` | 메뉴 "내 작업함", `#view-inbox`/`#inboxView`, 상단 `#inboxBadge`, `inbox.js` 스크립트(최소) |
| `it/portal/www/enterprise.js` · `instances.js` | 승인자 칸을 "나"로(없으면 기존 자유 입력), `#tdBy`·`#decBy` 없을 때 안전, `hydInstancesOpenTask` 한 줄 |
| `tests/test_inbox.py` (새) | 10개 시험 |

## 4. 시험 결과

- `tests/test_inbox.py` 10 통과: 해석 규칙(한 명 → 사람, 여럿 → 역할 공용, 없음) · 역할 공용 작업이 두 운전원 작업함에 모두 + 각자 알림 · 생산관리자 1명 → 상급자 확인 단계가 이생산에게 + 자동 배정 이력 · **업무분장이 바뀌면 그 사람 작업함에만**(최운전을 빼면 김운전에게만, 최운전·이생산 작업함은 비어 있음) · 구성원 없는 역할은 `unassigned_roles` 로 보고 · **"나"로 남의 역할 승인 403, 내 역할이어도 등급이 낮으면 403**(작업 그대로 열림, 승인 행 0) · 종결 알림이 참여자에게 한 번씩(정비관리자는 받지 않음) · 알림 읽음(한 건·모두·이미 읽음 0건, 역할 앞 알림 공유) · HTTP 경로(404·405·400·남의 알림 읽음 0건·링크 풀이·403 두 가지) · SSE 가 연결 뒤 새로 생긴 내 알림만 보내고 남의 것은 보내지 않음.
- 일부러 깨뜨리기: `check_actor` 를 무조건 통과로, 한 명 → 사람 해석을 끄면 5개 시험이 실패(복구 뒤 10 통과).
- 전체 `pytest -q`: **1294 passed**(worktree, 2026-10-08).
- `node --check`: `inbox.js` · `enterprise.js` · `instances.js` 통과.
- 화면(도커 없이 메모리 저장소로 process API 를 127.0.0.2:8080 에 띄우고 Playwright, 증거 `.evidence/A3-u5-inbox/`): 나 고르기 → 내 작업 1건("조치 선택 · 역할 공용 · 운전원 · 설비 이상 조치 HYD-01 · 방금 · 기한") · 상단 "김운전 알림 1" → 에이전트 질문 알림을 서버에 넣으면 새로 고치지 않아도 "알림 2"(SSE) → 알림을 누르면 읽음(안 읽음 2 → 1) + `#/instances/…/task/…` 로 처리 건 화면의 그 단계 → 새로 고쳐도 나 기억 → 김운전 승인 시 "승인 권한이 부족합니다: 생산관리자 이상이 승인해야 합니다"(작업 그대로) → 이생산으로 바꾸면 역할 선택 "생산관리자", 승인 성공(`approved_by=user:lee-prod`, 참여자에 이생산). 화면 영문 id 0, 페이지 오류 0.
  - 시험용 결정(카드 2장)은 시험 서버가 만든 것이다(`stub_process.py`) — 실제 카드·등급 검사는 통합 검증에서 확인.

## 5. 미검증 · 남은 일

- **PostgreSQL 실물 미검증**: 이 세션에서 임시 PG 를 띄우지 못했다(권한). `PgRepo` 의 새 SQL(role_members·task_assignments·알림 조회/읽음/스트림)과 migration 000029·seed 는 합친 뒤 `supabase start` 에서 확인 필요 — `select * from role_members`, 경보 1건 뒤 `select kind,to_user_id from task_assignments`, `select user_id,type,is_read from notifications order by created_at`.
- 워커의 질문 알림은 여전히 `role:operator` 고정(`runner.py:385-388`) — 처리 건 역할을 따르게 바꾸는 것은 워커 단위 범위.
- 역할 앞으로 온 알림(워커 질문)은 역할 공용 한 행이라 한 사람이 읽으면 역할 전체가 읽은 것으로 보인다(개인별 읽음 표는 두지 않음).
- 승인과 실행 탭의 옛 결정 승인(`/api/decisions/{id}/approve`, legacy 전용)은 ① 구성원 검사를 하지 않는다(② 등급 검사만). 강의 배포본(instance)은 `/select` 경로라 ①②가 모두 걸린다.
- 역할 이름 표기: 포털 사전은 `role:maint-mgr` = "설비보전팀장", DB 역할 사용자 이름은 "정비관리자" — 기존 불일치, 이 단위는 포털 사전을 따랐다.
- 셸 재편(U7)이 메뉴·상단을 옮길 때 `#inboxView` 와 `hydInbox.badge()` 를 그대로 쓰면 된다.
