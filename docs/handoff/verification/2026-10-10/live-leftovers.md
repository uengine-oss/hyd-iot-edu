# 라이브 3차 남은 것 6건 — 원인 확정과 근본 수정 (2026-10-10)

근거: `live-final.md` 3차(3-5 · 3-6 백엔드 보고 B-1~B-3 · 3-7 도구 결함 · 사소 출처 칩), 증거 `.evidence/a161-final/live/`.
형식: 항목마다 원인(파일:줄, 수정 전) → 분류 → 조치 → 검증(시험 · 뮤테이션). 라이브 스택은 돌리지 않음(코드 · 단위 시험만).

## 2. 버튼 기록 이름 두 번("김운전 김운전") — 결함, 고침 · 검증됨(단위)
- 원인: 생산자 `it/process/procsvc/scenario_buttons.py:129`(수정 전) `press_event` 가 `name=f"수업 버튼 [{button}] — {person['by']}"` 로 이름 칸에 사람을 넣고 `by` 칸에도 같은 사람을 실음. 소비자는 다른 기록 줄과 같은 규칙으로 name 옆에 by 를 붙임 — `caseRecord.js:725`(`<b>name</b>` + `sysDetail` :742-745 `d.by`), `trace.js:179`(title = name, text = by).
- 분류: 결함(생산자 계약 이중). 소비자는 모든 기록 줄에 같은 규칙이라 바꾸지 않음.
- 조치: 생산자 계약을 하나로 — name 은 "무엇을 눌렀나"(`수업 버튼 [버튼]`)만, 사람은 `by` 한 칸만(`scenario_buttons.py:126-131`).
- 시험: `tests/test_c3_bc_review.py::test_the_case_record_shows_the_press_and_that_the_flow_ends_in_the_business_system` — 실제 caseRecord.js(node vm)로 그린 화면 글에서 "수업 버튼 [정기 점검] 박정비" 정확히 1번, "박정비 박정비" · "김운전 김운전" 없음. 뮤테이션(name 에 사람을 되돌림) → `assert (0 == 1)` 로 실패 확인 → 되돌림.
- 남는 것: 라이브 DB 에 이미 저장된 옛 기록 줄(3차 A · B · C)은 옛 name 그대로라 계속 두 번 보인다(데이터 손 수정 안 함). 새 누름부터 한 번.

## 3. B 공지 메일 본문 "(승인 user:park-maint)" — 결함, 고침 · 검증됨(단위)
- 원인: 흐름 정의의 틀 `scripts/c3_flows.py:104`(수정 전) `"… (승인 {approved_by})"`. `approved_by` 는 승인 경로가 넣는 **사람 id**(권한 · 감사 계약 — `instances.py:701` select, `:759` approve)이고, 이름을 담은 처리 건 값은 없었다. 같은 문제 grep(`{approved_by}`): `scripts/c3_flows.py:83` A 미달 결과 보고 요약 "승인자 {approved_by}" · 같은 A 매핑 사본 `tests/test_c2_execution.py:84` · `tests/test_capstone_g1_approve.py:58`(MCP 인자 `organizer` — 기계가 받는 칸이라 id 가 맞음, 유지).
- 분류: 결함(사람에게 가는 글에 내부 id).
- 조치(서버가 이름을 아는 값으로): 승인 경로가 `approved_by_name` 을 함께 넣는다 — `inbox.person_name`(`inbox.py`, 사람 id 면 사용자 표의 이름, 이름이 없으면 id 좌표가 든 LookupError, 사람 id 가 아닌 자유 입력은 그 글이 곧 이름 — check_actor 와 같은 갈래). select(`instances.py` check_actor 바로 뒤에서 계산 → 이름이 없으면 판단 승인 훅 전에 실패, 승인 기록 payload 에도 `by_name`) · 일반 승인 approve · 보호 값(`approval_part.SERVER_VALUES`, `definition_registry.PROTECTED_OUTPUTS` — 흐름 task 가 낼 수 없음, 반려 때 같이 비움) · 재작업이 지우는 승인 값(`rework_effects.RUNTIME_CONSENT`, 같은 승인인지 대조에 이름 포함). 틀 두 곳(`c3_flows.py:83` · `:104`)과 C2 사본을 `{approved_by_name}` 으로. 포털 변수 이름표 `ui.js` `var.approved_by_name` '승인자 이름'.
- 시험: `tests/test_c3_bc_simplified.py::test_b_notice_mail_names_the_approver_by_name_not_by_user_id`(실제 c3_pm 정의 · 런타임, 사람 user:park-maint 로 승인 → 메일 본문이 "(승인 박정비)"로 끝나고 "user:" 없음, 세 흐름의 틀 어디에도 `{approved_by}` 없음) · `::test_an_approver_id_without_a_name_in_the_user_table_fails_loudly` · `test_capstone_g1_approve` 에 이름 단언 1줄. 뮤테이션(틀을 `{approved_by}` 로 되돌림) → 본문 "…(승인 user:park-maint)" 로 실패 확인 → 되돌림.

## 4. `scripts/c3_flows.py` 가 모르는 명령을 배포로 처리 — 결함, 고침 · 검증됨(단위)
- 원인: `scripts/c3_flows.py:157-177`(수정 전) `main` 이 export 만 따로 보고 나머지는 모두 import → check → (`cmd == "check"` 가 아니면) register → deploy. 그래서 `deploy-reset` 이 판 5 를 다시 배포했다(live-final 3-7). 같은 자리의 덜 보이는 결함: 사전 검사 문제가 있어도 종료 코드 0(조용한 실패), 인자 없으면 말없이 check.
- 분류: 결함(도구).
- 조치: 명령 표(`(이름, 인자 수)` → 함수)로 정확히 하나만 받는다 — `check` · `deploy` · `export DIR` · `deploy-reset BY`(새 명시 명령, `POST /api/flows/deploy-reset` 를 부름). 모르는 명령 · 인자 수 틀림 · 빈 인자는 사용법을 stderr 에 쓰고 종료 2, API 를 하나도 부르지 않는다. 사전 검사 문제가 하나라도 있으면 종료 1. 머리 주석의 사용법에 deploy-reset 추가.
- 시험: `tests/test_c3_assembly.py` 새 3개 — 모르는 명령 6가지(`deploy-reset` 인자 없음 · `deploy_reset x` · `depoly` · `export` 인자 없음 · `check extra` · 빈 인자) 모두 2 · API 호출 0 · 사용법 출력, `deploy-reset 강사` 는 reset API 하나만 by 와 함께, `check` 는 등록 · 배포를 안 부르고 검사 실패면 1. 뮤테이션(모르는 명령을 배포로 넘기는 옛 동작) → 4개 실패 확인 → 되돌림.

## 6. 출처 칩 "PR-7.6 PR-7.6 발주 절차" — 결함(생산자 계약 모호), 고침 · 검증됨(단위), 라이브 화면은 재추출 뒤
- 원인: 화면은 칩 = 절 번호(`manual.ref`) + 굵은 제목(`manual.title`)으로 그린다(`caseRecord.js:313`, `approvalCard.js:45-47`). 저장된 값이 `ref "PR-7.6"`, `title "PR-7.6 발주 절차"`(`C-decision.json` steps[].manual) — 제목에 번호가 이미 들어 있다. 추출 계약 `it/process/procsvc/manual_extraction.py:21`(수정 전) `{"ref":"문서 내 유일한 절 ID","title":"절 제목"}` 이 번호를 넣을지 정하지 않아, 같은 형식(`## XX-N.N 제목`)의 세 문서 중 HM-8 · PR-07 추출은 번호를 넣고 PM-02 는 뺐다(B 기록 "PM-2.5 시행 시점과 범위 정하기"는 한 번). 시드(`it/neo4j/v2/instances.cypher:195-203`)와 스키마(`docs/ontology/schema-v2.md:171` ref! · title!)는 번호 없는 제목.
- 분류: 결함(추출 계약 모호 → 생산자마다 다른 값). 화면에서 중복을 지우는 것은 소비자 땜빵이라 하지 않음.
- 조치: 추출 계약 2.2 — 지시문에 "ref 는 절 번호, title 은 그 번호를 뺀 제목(예: `## PR-7.6 발주 절차` → ref `PR-7.6`, title `발주 절차`)", 에이전트 제출 검사 `check_section_titles`(번호를 품은 제목이면 사유와 고친 예를 담아 같은 task 교정 루프로 돌려보냄). 검사는 제출 때(`validate_result`)만 — 이미 저장된 2.1 이전 제안은 판의 계약대로 계속 읽힌다(`validate_proposal` 은 구조 검사 그대로). `VERSION` 2.1 → 2.2(지시문이 바뀌면 판을 올리는 기존 관례).
- 시험: `tests/test_manual_extraction.py::test_a_section_title_carrying_its_own_number_goes_back_to_the_agent`(실제 추출 정의 · 런타임: 번호 든 제목 제출 → `FB_REQUESTED` + 사유 "절 번호", 번호 없는 제목 통과, 옛 저장본 구조 검사 통과, 지시문 예시) · `test_c1_knowledge` 판 2.2. 뮤테이션(제출 검사 제거) → `COMPLETED != FB_REQUESTED` 실패 확인 → 되돌림.
- 남는 것: 라이브 그래프의 HM-8 · PR-07 절 제목은 옛 추출 값이라 칩이 계속 두 번 보인다. 그래프 손 수정은 하지 않음 — 두 문서를 2.2 로 다시 추출 · 검토 · 적재하면 사라진다(라이브 확인 항목).

## 5. C 처리 건에 판단 id DEC-1010-005-cc60(GET 404)이 하나 더 — 원인 확정: 읽기 평가의 id 종류 결함, 고침 · 검증됨(단위)
- 먼저 정정: 3-5 의 "처리 건 **변수**에 보임"은 오해다. `C-instance.json` 전체를 훑으면 005 는 변수에 없고 `events[30].data.full_output.summary` 한 곳 — 에이전트의 `evaluate_cards` 도구 호출(11:21:42, 원문 87,520자 보관) 결과 원문 머리에만 있다. 변수 `decision_id` 는 `submit_decision`(11:21:54)이 돌려준 006. A(001 평가 → 002 제출) · B(003 → 004)도 같은 꼴 — 에이전트가 평가 한 번, 제출 한 번 하는 정상 순서이고 판단을 두 번 낸 것이 아니다.
- 원인: `it/agent/agentsvc/decide.py:233`(수정 전) `decide()` 가 제출 여부와 무관하게 `registry.new_id()` → `DEC-mmdd-seq-xxxx` 를 매긴다. `evaluate_cards`(`it/dmn-mcp/dmn_mcp/tools.py:166`, `do_submit=False`)의 결과는 dmn-mcp 프로세스 메모리 기록일 뿐 process 에 저장되지 않으므로 같은 모양의 id 가 GET /api/decisions 에서 404. 읽기 평가 id 가 저장 판단으로 다시 쓰이는 길은 없다(옛 경로 `legacy_assessment.py:135` 는 `DEC-EVAL-…` 로 새로 매김).
- 분류: 평가 → 제출 순서는 의도, **읽기 평가가 저장 판단과 같은 id 종류를 받는 것은 결함**(저장되지 않은 기록이 판단 id 를 입음).
- 조치: `DecisionRegistry.new_id(kind)` — `DEC`(제출되는 판단) · `EVAL`(제출하지 않는 읽기 평가 · 가정 실험), 다른 종류는 ValueError. `decide()` 는 `do_submit` 으로 종류를 고른다. 화면 쪽 감추기는 하지 않음(원문은 원문대로, 이제 EVAL- 로 보여 판단과 구별됨).
- 시험: `tests/test_forecast_cards.py::test_runtime_decide_saves_dynamic_context_and_keeps_what_if_read_only` 에 단언 — 제출한 판단 id = 보낸 payload id 이고 `DEC-`, 읽기 평가는 `EVAL-`, 모르는 종류 거절. 뮤테이션(항상 DEC) → 실패 확인 → 되돌림.
- 남는 것: `do_submit=True` 인데 가드레일 거절 · 후보 없음으로 제출되지 않은 기록은 여전히 `DEC-` 이고 404 다(상태 칸 REJECTED_BY_GUARDRAIL · NO_FEASIBLE_OPTION 이 같이 돌아감). 이번 범위 밖, 보고만.

## 1. C(· B) 카드 머리말이 "예측 평형 유온 48°C · 토출 압력 182bar" — 표시 층 결함, 고침 · 검증됨(단위 · 고치기 전 코드와 A 대조)
### 1-1. 엔진이 모든 카드에 예측을 붙이는 것은 정당한가 — 예, 엔진은 고치지 않음
- 순위 성분: `rankRule.rankingPolicy.components.forecast = clamp((55 − forecast_ts1)/3, ±2)`, `quality` 도 `forecast_ts1 ≥ 55` 를 본다(`C-decision.json` rankRule, 계산 `it/agent/agentsvc/cards.py:153-163` score_option). C 세 카드 모두 forecast 성분 2.0 — 순서에는 영향 없지만 점수의 일부다.
- 규정 · 제외: 예측 모델을 못 쓰면 `forecast:model-unavailable` EXCLUDE, 예측 구간 인터록이면 EXCLUDE(`cards.py:228-236`), 규칙이 `in:forecast-ts1` 을 검사(예: A `rule:cool-forecast-warn`).
- 승인 순간 재확인: `forecasting.consent_changes` 가 카드의 forecastContext 를 다시 대조.
- 그래서 층은 화면이다. C 의 예측은 "설비 명령 없음 → 지금 설비 그대로"(`method …; constant inputs`, 세 카드 48.001 · 182)라 고르는 근거가 아닌데 머리말을 차지했다.
### 1-2. 원인(파일:줄, 수정 전)과 조치
- `it/portal/www/approvalCard.js:27-28` reasons 첫 줄이 무조건 예측, `:59-60` 진 이유에 "평형 유온 48℃ (추천 48℃)"; `it/portal/www/caseRecord.js:342` fc 줄이 모든 안에 "예측 …"; `it/portal/www/enterprise.js:267-271 · :290` 조치 판단 카드 머리 줄이 `forecastLine`.
- 규칙(한 곳, `approvalCard.js` `forecastDecides` · `ownValues`): 예측을 머리말로 두는 것은 **설비를 바꾸는 안(`kind === 'control'`)이거나 같은 판단의 안마다 예측 값이 갈릴 때**. 아니면 그 안의 업무 값 — 판단 수준에서 비어 있는 카드별 사실(`facts` 의 발주 금액 · AVL · 납기 여유 · 불량률, 기존 P-3 의 칸 그대로)과, 예측이 머리말이 아닌 안이 작업지시(`actions[].code == WO_CREATE`)를 내면 카드가 실어 온 정비 시점(`window.name` · `starts_at`)과 그때의 운전시간(`facts[window.basis]`). 근거는 카드 칸(kind · forecast · facts · actions · window)뿐, 시나리오 이름 없음.
  - 왜 "kind control 만"이 아닌가: A 의 `쿨러 핀 세척`(SOP-COOL-14)은 `kind work_order` 인데 예측 62.5 ℃ 가 바로 진 이유다(다른 안 44.6~49.8 ℃). kind 만으로 가르면 A 화면이 바뀐다 — 지시의 "A 불변"과 충돌하므로 "예측이 안마다 갈리면 고르는 근거"를 함께 둔다.
  - 발주 카드에도 `window: 즉시 (지금 정지하고 시행)` 이 붙어 있으나(아래 1-4) 작업지시를 내지 않으므로 정비 시점은 보이지 않는다.
- 적용: 승인 카드(`reasons(o, d)` 머리 줄 · `partDiff` 의 예측 비교), 처리 기록 비교한 대안(`altHtml` — 예측 줄은 고르는 근거일 때만, 업무 값 줄, 추천안 이유 줄은 머리말이 업무 값이면 다시 적지 않음; A 처럼 예측 머리말인 안은 예전대로), 조치 판단 카드 머리 줄(`enterprise.js` `headValue`, 근거 접기 안의 예측 · 점수 성분은 그대로). `cardHtml` 은 같은 판단(`opt.decision`)이 없으면 실패한다 — 호출 8곳(`enterprise.js` 3 · `hitl.js` 4 · `instances.js` 1, 그중 검토본 카드 2곳은 `review.snapshot`)에 넘김.
### 1-3. "판정 고장 유형 펌프 체적 효율 저하 / 원인 축 씰 마모" — 의도된 연결, 이름표 고침 + 근거 기록 결함 고침
- 설계 대조(`docs/보고서/2026-10-09_HYD_시나리오_3개.md`): C 도구 "지식 그래프 (부품 · 공급사 경로)", B × C "같은 씰 키트를 가리킴. B가 쓰고 C가 채우는 연결점". 코드: `it/dmn-mcp/dmn_mcp/tools.py` `BUSINESS_CAUSES["SPARE_BELOW_MIN"]` = "재고가 모자란 부품을 쓰는 원인(Cause -INVOLVES_PART-> Part)". → 의도된 연결("왜 이 부품인가"). 고장 진단이 아니다.
- 그런데 결함 하나: `tools.py:165 · :176`(수정 전) 판단 origin 의 `cause_basis` 가 업무 경보에서도 늘 T1 문장("pattern → symptom → failure mode ← cause, same query as diagnose")이었다 — 실제로 원인을 받아 준 것은 `_diagnosed_cause` 의 업무 근거 갈래(`:219-223`). 그래서 C 기록이 "원인을 정한 근거: 지식 그래프 (경보 패턴 → 증상 → 고장 유형 ← 원인), 원인 진단과 같은 질의"라고 거짓으로 적었다(`C-7-record-text.txt` 지식 경로).
- 조치: `_diagnosed_cause` 가 `(원인, 근거)` 를 돌려주고 origin 에 실제 근거 `cause_basis` 와 종류 `cause_route`(diagnosis · part · prevention — 업무 경보 표 `BUSINESS_CAUSE_ROUTE`, 패턴별 근거 표와 같은 자리)를 적는다. 포털은 `cause_route` 로 이름표를 고른다(`plainWords.js` `W.causeWords`): part → "이 부품이 고치는 원인" · "그 원인이 일으키는 고장", 한 문장 "이 부품이 고치는 원인 ‘축 씰 마모’를 찾고", 가져온 데이터 표의 cause · failure_mode 줄 이름, 지식 경로 "추천안에 이른 길"의 마디 이름. prevention(B) → "정기 정비로 막는 원인 · 고장". diagnosis(A) · 칸 없는 옛 판단 → 예전 그대로. 모르는 값은 오류. 근거 문장 번역(`caseRecord.js` basisText)에 `-CAUSES->` · part · skill 추가.
### 1-4. 고치지 않고 보고만
- 발주 카드(C)와 A 의 작업지시 카드(SOP-COOL-14)에 `window: 즉시 (지금 정지하고 시행)` — `cards.py:127` option_window 가 일정 판단 창 값(`windows_by_variable`, B 의 규정 입력이라 모든 처리 건이 모음)이 있으면 kind work_order 카드에 모두 즉시 창을 붙인다. 발주에는 뜻이 없고 process 가 `chosen_option.window` 를 읽는다(`service_parts.py:203` · `instances.py:1048` · `main.py:770`). 이번 범위 밖 — 엔진 · 흐름 쪽 판단 필요.
- C 승인 순간 재확인도 예측 문맥(팬 · 부하 입력)을 대조한다 — 발주 승인 사이에 설비 입력이 바뀌면 "새 카드 검토 필요"로 막힐 수 있다(코드 읽기, 실측 없음).
### 1-5. 시험
- `tests/test_live_leftovers_cards.py`(새, node vm 렌더러 `tests/js/render_decision_cards.js` — 실제 ui · plainWords · approvalCard · caseRecord 파일과 enterprise.js 카드 부분): A 고정본 `tests/fixtures/a_cards_before.json` 은 **고치기 전 코드(664d06c 의 같은 파일)로 그린 글** — 지금 코드의 A 승인 카드 · 비교한 대안 · 지식 경로 · 카드 머리 줄이 글자까지 같다. C: 머리말 "이 안의 값 발주 금액 330 만원 · 승인 공급사(AVL) 예 · 납기 여유 1 일 · 공급사 불량률(비율) 0.02"가 이유보다 먼저, 승인 카드 · 대안 · 카드 머리 줄 어디에도 "예측"·"48℃" 없음, 추천 머리말 한 번, 정비 시점 없음, 점수 성분 "예측 +2.00"은 근거 접기에 남음. B: "이 안의 값 정비 시점 이번 예정된 정비 시간 (…) · 이번 정비 시간의 운전시간 1,959 h". 예측이 모두 같아도 제어 안은 예측 유지. 지식 경로 이름표(C part · B prevention · A diagnosis 그대로), 모르는 route 는 실패. 같은 픽스처로 고치기 전 코드를 돌리면 C 승인 카드가 "예측 평형 유온 48℃ · 토출 압력 182bar … 평형 유온 48℃ (추천 48℃)" — 라이브 증상 재현.
- `tests/test_c3_bc_review.py::test_c_agent_step_reads_the_cause_as_why_this_part_not_a_diagnosis`(실제 c3_spare 런타임 처리 건 + 처리 기록 build): part 면 한 문장 · 칩 · 가져온 데이터 표에 "이 부품이 고치는 원인", "판정 원인" 없음; diagnosis 면 예전 그대로.
- `tests/test_c2_judgement.py` · `tests/test_a144_mcp_worker.py`: 업무 경보 origin = 부품 근거 · route part, 센서 진단 = T1 · diagnosis.
- 뮤테이션: ① 늘 예측 → C · B 시험 3개 실패 ② kind 만(work_order 는 예측 안 봄) → A 고정본 실패 ③ route 무시 → 3개 실패 ④ dmn-mcp 가 업무 근거를 기록하지 않음 → 실패. 모두 되돌림.

## 검증 요약
- 관련 시험 → 전체 스위트 1회: **2076 passed · 9 skipped**(195초, `../agent-afd136e4b22934cb9/.venv/bin/python -m pytest -q -p no:cacheprovider`). `node --check` 포털 JS 전부 · `tests/js/*.js` 통과. 포털 캐시 `20261010-lo1`(ui · enterprise · hitl · approvalCard · plainWords · caseRecord · instances).
- 검증됨: 단위 · 런타임(MemoryRepo) · node vm 렌더. **미검증: 라이브 스택**(빌드 · 배포 · 워커 금지 지시 — 아래는 라이브에서 볼 것).

## 라이브에서 확인할 것
1. process · agent · dmn-mcp · portal 재빌드 뒤 C 한 번: 승인 카드 첫 줄 "이 안의 값 발주 금액 330 만원 …", 처리 기록 대안 3개에 "예측" 없음, 지식 경로 "이 부품이 고치는 원인 축 씰 마모", "원인을 정한 근거"가 부품 경로 문장. A 화면이 3차 캡처와 같은지(1440 · 390).
2. B 한 번: 카드 머리말 정비 시점 · 운전시간, 공지 메일 본문 "(승인 박정비)".
3. 버튼 기록 줄 "수업 버튼 [재고 보충] 정구매"(이름 한 번) — 새 누름부터. 옛 처리 건 기록은 옛 글 그대로.
4. 에이전트 도구 원문의 평가 id 가 `EVAL-…`, 처리 건 `decision_id` 는 `DEC-…` 하나.
5. `scripts/c3_flows.py deploy-reset 강사` 로 기준 흐름 되돌리기, 모르는 명령은 종료 2.
6. 출처 칩 번호 중복은 HM-8 · PR-07 을 추출 2.2 로 다시 추출 · 검토 · 적재해야 사라진다(지금 그래프 값은 옛 제목).
