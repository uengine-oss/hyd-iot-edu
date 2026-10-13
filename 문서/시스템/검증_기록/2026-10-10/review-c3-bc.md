# C3 B·C 단순화 변경분 점검 (2026-10-10)

대상: `git diff 7fa5664 c3-assembly` (c2bd5b3 … 0ab71bf), merge-preview 병합 커밋 816a4e6 위에서 점검.
점검표: A(사실·코드) B(해피패스) C(클린코드) D(프로젝트 규칙). 진행 중 — 절마다 덧붙임.

## 0. 기준선

- `git status` 깨끗, HEAD 816a4e6(병합 커밋). 관련 시험 5개 파일(test_c3_bc_simplified · test_c2_parts · test_c2_execution · test_c2_judgement · test_c3_assembly) 83 통과 — 고치기 전 기준.

## 1. 발견 (읽기 단계)

| # | 발견 | 분류 | 근거 |
|---|---|---|---|
| F1 | 처리 기록 화면(caseRecord.js, A161 쪽)이 C3 흐름과 의미 충돌: ① 블랙박스 점검 줄이 "수업 버튼(재고 출고 · 운전시간 빨리 감기)을 누른 사람과 시각은 처리 건에 없습니다"라고 단정 — C3 는 SCENARIO_BUTTON 기록을 처리 건에 남기므로 거짓이고 옛 버튼 이름 잔재. ② 버튼 기록은 `todo_id` 없는 events 행인데 `build()`가 todo 별로만 행을 붙여 화면 어디에도 안 나온다. ③ 버튼으로 연 B · C 처리 건의 시작 단계가 "업무 데이터 감시가 시작 … 발견해 처리 건을 열었습니다"로 읽힌다(감시는 기본 꺼짐). ④ '설비까지 가지 않음'이 화면 어디에도 의도로 적혀 있지 않다 | 결함 | caseRecord.js:95·161-182·638, scenario_buttons.press_event(todo_id None) |
| F2 | 버튼마다 시나리오 시각 기준점(`/api/reanchor`)을 무조건 옮긴다 — 거절(409)될 누름도, 다른 처리 건이 진행 중일 때도. 예정된 정비 시간 id 가 기준점 시각을 품어(`MW-HYD-02-N-<시작 시각>`) 진행 중인 B 처리 건이 승인 뒤 낼 작업지시의 창 id 가 사라진다 → CMMS `unknown maintenance window` 거절 | 결함 | main.py:1199·1223·1244, entsim/data.py next_windows id, state.py:319 |
| F3 | plant-sim `inject()`가 누름(origin) 없는 주입(정비 수행 모사의 복구 · 검사 스크립트)에서 지난 누름을 지우지 않는다 → 다음 센서 경보 처리 건에 지난 [쿨러 열화 주입] 누름이 잘못 붙는다(지어낸 연결) | 결함 | plant.py inject, instance_mode.py:528(origin 없는 복구) |
| F4 | 매직 넘버: `_runs(limit=60)`·`case_of_injection(limit=30)`이 테넌트 전체 최신 N건만 본다. 질문 · 시험 실행 처리 건이 그 위로 쌓이면 진행 중인 B · C 를 못 봐 중복 시작을 허용하고, 복구 누름이 연결을 잃는다 | 결함 | scenario_buttons.py:70-74·127-135 |
| F5 | 포털 `refreshBiz()`가 상태 읽기 실패를 삼켜 `state.biz=null` → 카드에 표시가 그냥 사라진다(오류 · 로딩 상태 없음) | 결함 | app.js:290-292 |
| F6 | 409 거절 글에 내부 id · 영문 코드(`c3_pm.1` 처리 건 번호, `PM_DUE`)가 화면에 그대로 나간다 | 결함 | scenario_buttons.py prepare |
| F7 | `started()`가 처리 건을 못 찾으면 `instance: None`으로 성공 응답 — 화면은 "처리 건 시작"이라고 적는다(빈 성공) | 결함 | scenario_buttons.started, app.js biz-start |
| F8 | `case_started` 훅 실패를 감사 기록(CASE_LINK_FAILED)에만 남김 — 처리 건 시작을 되돌리지 않는 선택은 정당하나, 처리 기록 화면에는 연결 실패가 안 보인다 | 결함(가시성) | instances.py:266-272 |
| F9 | `EXPERIMENT[asset] \|\| EXPERIMENT['HYD-01']` — 모르는 설비 카드에 A 버튼을 달아 HYD-01 에 주입(폴백) | 결함(경미) | app.js renderUnits |
| F10 | 카드 표시 칩 `title`(툴팁)에 처리 건 id | 결함(경미, 내부 id) | app.js bizAlertHtml |
| F11 | 문서 · 주석 잔재: c3-assembly.md:173 "enterprise-sim API(`/cmms/pm/advance` 등)는 시험 · 강사용으로 남김"(같은 문서 183행은 삭제했다고 적음), test_c2_execution.py:399 "수업 버튼 '공급사 납기 지연 +3일'", entsim/data.py `"P-PMP-SEAL"` 줄 들여쓰기 깨짐 | 결함(문서 · 정리) | 각 줄 |
| O1 | BUSINESS_MONITOR 선택 기능 | 의도된 차이(죽은 코드 아님) — 기본 0, `scan_once`·회차 키 시험(test_c2_parts) 있음, 버튼과 같은 경보 계약 공유. 켜면 시작 상태가 곧 도래라 바로 열리는 것은 문서화된 동작 | business_monitor.py, main.py:524 |
| O2 | 마이그레이션 47 ↔ 메모리 백엔드 시작값 | 일치 확인: 씰 키트 실물 3 · 예약 2 · 재주문점 2, 계수기 1500/1950/1880 h(total 9500/11950/7880), pm_alert = 도래 ∧ 오더 없음, 오더 표시 = window_id 있는 작업지시 · 먼저 등록된 것, 초기화가 plan_wo 지우고 due_since/below_since 다시 기록(메모리는 `_pm_log`·`_move`가, SQL 은 refresh_*_flag 가) | 의도대로 |
| O3 | 옛 경로 이름 검색: `/api/simulate` · `c2_live_check` · `scenarioTriggers` · `/erp/spare/issue` · `/cmms/pm/advance` · `/erp/purchase_orders/delay` 코드 0. 남은 것은 ① 바뀌지 않는 마이그레이션 45 주석, ② 날짜 박힌 2026-10-09 검증 기록(c2-execution.md), ③ 업무 거래 skill:pm-advance · issue-spare · delay-delivery(`/api/exec` 거래로 유지 — 의도), ④ F1 · F11 | 대부분 의도, F1 · F11 은 결함 |
| O4 | C 흐름에 납기 지연 가지 없음 — 감독 지시 '처리되면 끝'. 비해피 가지는 승인 뒤 업무 시스템 거절 → PENDING · 사유 보존(시험 있음), 지는 대안은 판단 카드(가격 · 납기 · AVL) | 의도된 차이 |
| O5 | 자동 병합 파일 의미 충돌: service_parts.py(즉시 입고 · 입고 뒤 재고 읽기 — A161 쪽 변경과 겹치지 않음), instances.py(case_started 훅), mcp_kg.py(liveness_check_timeout 한 줄), resultReport.js(승인자 이름), ui.js(구매 담당), compose.yaml(BUSINESS_MONITOR 기본 0) — 충돌 없음. caseRecord.js 만 F1 | F1 외 충돌 없음 |

## 2. 조치 (근본 수정)

| # | 조치 | 파일 |
|---|---|---|
| F1 | 시작 단계가 버튼으로 연 처리 건(`evidence.trigger`)을 "수업 버튼으로 시작"으로 그리고, 누른 사람 · 시각을 들어온 값 맨 위에 둔다. 처리 건에 붙은 기록(todo 없는 `SCENARIO_BUTTON` · `CASE_LINK_FAILED`)을 시작 단계의 "수업 버튼 기록 N줄"로 보인다(A 센서 처리 건의 [쿨러 열화 주입] 연결도). 업무 경보로 시작하고 설비에 닿는 단계(`plant:*` · `incident:command/reobserve`)가 없는 흐름은 칩 "설비 명령 없음"과 칸 "이 흐름의 끝"(업무 시스템에서 끝남 — 흐름 설계)을 보인다. 거짓 블랙박스 줄을 지우고, 버튼 근거는 있는데 기록 줄이 없을 때 · 연결 실패일 때만 적는다 | `it/portal/www/caseRecord.js` (상수 PLANT · CASE_LEVEL, startStep, gapsOf) |
| F2 | 시각 기준점은 설비 처리 건(설비 값이 있는 RUNNING 처리 건)이 없을 때만 옮긴다 — `scenario_buttons.may_reanchor`, `main._reanchor_if_idle`. 버튼 시작 · 초기화 · [쿨러 열화 주입] 모두 이 경로. 옮겼는지(`reanchored`)를 응답 · 감사 기록에 싣고, 포털 기록 줄에 "시나리오 시각 기준점은 그대로(진행 중인 처리 건이 있음)"를 보인다 | `scenario_buttons.py`, `main.py` scenario_start · scenario_reset · scenario_a_button, `app.js` anchorNote |
| F3 | `inject()`는 마지막 요청의 누름만 남긴다 — 누름 없는 주입이면 `injection=None`(바뀌면 상태 다시 발행) | `ot/plant-sim/plantsim/plant.py` inject |
| F4 | 저장소 `list_instances`에 `asset` 거르기(메모리 · PG 둘 다, PG 는 incident 거르기와 같은 `variables_data @>`). `_runs`는 그 설비 처리 건 전부에서 버튼 경보 접두로 거르고, `case_of_injection`은 그 설비 처리 건을 최신부터 보되 주입 시각보다 먼저 열린 처리 건에서 멈춘다(건수 자르기 없음) | `procdb.py` Repo · MemoryRepo · PgRepo, `scenario_buttons.py` |
| F5 | `refreshBiz` 실패를 `{failed: 사유}`로 남기고 카드에 "표시를 읽지 못함"(툴팁 사유), 첫 읽기 전에는 "표시 확인 중…", 실패 상태면 다음 주기에 다시 읽는다 | `app.js` bizAlertHtml · refreshBiz · refreshSlow |
| F6 | 거절 글: "HYD-02 정기 정비 처리 건이 이미 진행 중입니다 — 카드의 '처리 중' 표시를 눌러 그 처리 건을 보세요", "'정기 점검 도래' 경보로 시작하는 정기 정비 흐름이 배포되어 있지 않습니다" | `scenario_buttons.prepare` |
| F7 | 처리 건을 못 찾으면 `NotStarted` → HTTP 500(경보 id · 흐름 id 좌표), 감사 기록에 `error` | `scenario_buttons.started`, `main.scenario_start` |
| F8 | 훅 실패 시 감사 기록에 더해 처리 건 events 에 `CASE_LINK_FAILED`(error) 한 줄 — F1 이 시작 단계에 보인다. 이 줄마저 못 쓰면(저장소 장애) 예외가 호출자로 간다(경보 재전송은 같은 처리 건을 찾는다). 지식 투영(`_project`)은 훅 앞으로 옮겨 훅 실패와 무관하게 한다 | `instances.py` start_definition |
| F9 | 실험 버튼이 없는 설비 카드에는 버튼을 달지 않는다 | `app.js` renderUnits |
| F10 | 칩 툴팁의 처리 건 id → "처리 건 화면에서 보기" | `app.js` bizAlertHtml |
| F11 | c3-assembly.md:173 문구를 183행(삭제)과 맞춤, test_c2_execution.py:399 주석, data.py 들여쓰기 | 각 파일 |
| — | 바뀐 스크립트 캐시 번호 `app.js` · `caseRecord.js` → `20261010-c3rv` | `it/portal/www/index.html` |

## 3. 검증

- 새 시험 `tests/test_c3_bc_review.py` 8개 + 실제 caseRecord.js 를 node vm 에 올려 `hydRecord.build`를 돌리는 `tests/js/render_case_record.js`. 기존 `test_c3_bc_simplified.py`의 시험 대역(FakeRt)을 저장소 서명에 맞추고 `case_of_injection` 호출을 주입 dict 로 바꿈.
- 관련 시험 11개 파일(test_c3_bc_review · test_c3_bc_simplified · test_c2_parts · test_c2_execution · test_c2_judgement · test_c3_assembly · test_instance_mode · test_instances · test_definition_registry · test_u1_task_detail · test_source_delivery): **172 통과** — 검증됨(단위 · 실제 런타임 MemoryRepo).
- 뮤테이션 10회(일부러 되돌린 뒤 해당 시험만 실행, 끝나고 원복): F3 · F4a(`_runs` 최신 60건) · F4b(주입 연결 30건) · F2(기준점 항상 옮김) · F7(빈 성공) · F6(거절 글에 id) · F8(훅 실패 기록 안 함) · F1a(시작 제목) · F1b(버튼 기록 줄 없음) · F1c('이 흐름의 끝' 없음) — **10/10 잡힘**. 스크립트: 세션 스크래치 `mutate.py`.
- 미검증: ① PgRepo `list_instances(asset=…)` SQL 은 실제 PostgreSQL 에서 돌리지 않음(메모리 저장소로만 — 같은 꼴의 incident 거르기를 따름), ② 포털 app.js 의 F5 · F9 · F10 · 기준점 문구는 문법 검사(`node --check`)만, 화면 미확인, ③ 라이브 스택 완주(버튼 → 처리 건 → 표시 꺼짐 → 초기화)는 메인 몫.

## 4. 남은 것 · 별건

- 별건(A161 쪽, 이번에 고치지 않음): `EFFECT_COMPENSATION` · `EFFECT_REVIEW`도 todo 없는 events 라 처리 기록 화면에 안 나온다(F1 과 같은 원인). 이번 수정은 처리 건 단위 기록 중 버튼 · 연결 실패만 시작 단계에 붙였다.
- 근거 부족: B · C 처리 건이 진행 중일 때 그 시나리오 [초기화]를 누르면 업무 값만 되돌리고 처리 건은 계속 간다(이번 수정으로 기준점은 안 옮김). 진행 중 초기화를 거절할지는 감독 지시에 없음 — 기록만.
- 같은 작업 트리에서 다른 담당이 고치는 파일(이번 점검과 무관, 손대지 않음): `it/agent/agentsvc/cards.py`, `it/neo4j/v2/scenario_structure.cypher`, `it/process/procsvc/manual_extraction.py`, `scripts/probe_c1_knowledge.py`, `tests/c1_fixtures.py`, `tests/test_c1_knowledge.py`, `tests/test_c2_judgement.py`, `docs/handoff/verification/2026-10-10/c-knowledge-gap.md`.
