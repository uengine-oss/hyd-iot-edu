# U1 화면 — 실시간 처리 과정 · 승인 요약 카드 · 결과 보고 (확정 TODO C, A161)

작성 2026-10-09. 브랜치 `u1-uiux-a161`(워크트리 `.claude/worktrees/agent-aed004354f1cd7a4c`). 커밋은 2개(e6c6805 실시간 처리 과정, 이번 커밋 승인 · 결과 · 결함).
증거: `.evidence/a161-u1/` — `before/`(고치기 전), `wip/`(중간), `after/`(고친 뒤, 실제 스택 · 실제 워커 한 바퀴).

**비유 한 줄**: 처리 건 화면은 택배 배송 조회다. 지금 어느 단계인지(흐름도), 기사가 무엇을 하고 있는지(도구 호출 한 줄씩), 내가 할 일(승인 한 번), 도착 확인(결과 보고)을 새로 고침 없이 본다.

**스스로 판정할 체크 질문**
- 처리 건을 열어 두고 아무것도 누르지 않아도, 에이전트의 도구 호출과 단계 전환이 줄줄이 늘어나는가?
- 승인 화면에서 10초 안에 "무엇을 승인하는지 · 왜 이 안인지 · 누를 버튼"을 찾는가? 다른 안은 접혀 있는가?
- 승인한 뒤 시스템 단계(명령 · 작업지시 · 재관측)가 흐르고, 끝나면 "정상 / 미달" 결과 카드가 한 장 올라오는가?
- 화면 어디에도 영어 내부 이름 · 호스트 경로 · 모델 이름 · "정비창"이 보이지 않는가?

---

## 1. 처리 모양 (확정) → 화면

에이전트 판단 · 추천 하나 → 담당자 승인 한 번 → 시스템 실행 → 시스템 확인 → 결과 보고. 2차 승인 · 사람 확인 단계는 없다.

| 단계 | 화면 | 부품 |
|---|---|---|
| 에이전트가 일하는 동안 | 처리 건 상세 "진행 상황" 탭: 흐름도(지금 단계 테두리가 흐름) + 처리 과정(단계 카드 안에 도구 호출 한 줄씩, 실시간) | `trace.js` · `liveStream.js` (e6c6805) |
| 담당자 승인 | "내 차례"를 누르면 **승인 요청 카드 한 장**: 추천안 · 짧은 이유(최대 4줄) · 승인하면 시스템이 할 일 · 핵심 근거(지식 그래프 경로 + 출처 절) · [승인] | `approvalCard.js` (새로) |
| 진 안 | 같은 카드 안 접기 "다른 안 N개는 왜 졌나": 안마다 점수 · 어디서 뒤졌나(점수 항목 차이) · 예측 값 비교 · 제외 규칙, "이 안으로 바꾸기" | `approvalCard.js` |
| 시스템 실행 · 확인 | 처리 과정에 시스템 단계가 같은 모양으로 흐름(아이콘: 명령 · 메일 · 발주 · 입고 · 일정 · 작업지시 · 확인, 대기는 남은 시간) + 결과 보고 카드의 "시스템이 한 일" 목록이 하나씩 켜짐 | `trace.js` · `resultReport.js` (새로) |
| 결과 보고 | "정상 / 미달 / 확인 중" 배지 · 측정값 · 승인한 안 · 승인한 사람 · 시스템이 한 일 | `resultReport.js` |

일반화: 코드에 시나리오 이름 · task id 를 두지 않는다. 승인 카드는 판단 결과(`options · recommended · explanation`)만 읽고,
결과 보고는 처리 건 값 `result_report = {verdict, title?, summary?, values:[{name, value, unit?, limit?, ok?}]}`를 먼저 쓰고,
없으면 알려진 확인 값(`recovered` 재관측 · `test_run` 시운전 · `received`/`goods_receipt` 입고)으로 판정한다.
**C3 조립 · C2 결과 보고 부품은 `result_report` 모양으로 값을 내면 B · C 에서도 카드가 그대로 그려진다.**

## 2. 실시간 스트리밍 (최우선, e6c6805 + 이번 보강)

- 서버: `GET /api/events/stream` 프레임마다 `id`(이벤트 시각). 브라우저가 다시 붙으면 `Last-Event-ID` 부터 받는다. 처리 건 view 는 최신 1,500건(가장 오래된 500건을 주던 결함 수정).
- 포털 버스(`liveStream.js`): 스트림 하나를 열어 처리 건 상세 · task 상세 · 질문하기 · 머리글 한 줄에 나눠 준다. 같은 id 는 한 번만(최근 5,000개), 서버가 닫으면 2·4·8…30초 간격 재연결, 2초 다시 읽기가 스트림보다 10초 넘게 새로우면 스트림을 다시 연다(지킴이).
- 그리기(`trace.js`): 단계 카드 + 도구 행, 키 단위 부분 갱신 — 펼친 상자가 다시 그려져 닫히지 않는다(결함 15). 도구 시작 → 끝을 `tool_use_id` 로 짝지어 소요 시간 한 줄.
- 읽기 쉽게: 모델 사용량 · 실행 시작 줄 숨김(결함 3), 호스트 경로 → 파일 이름, 모델 이름 → "AI 모델", 결과가 잘림 · 안전 장치가 막음은 칩으로 구분(결함 4 · 5).
- 이번 보강: 서버가 잘라 보낸 JSON 결과는 짧은 값만 골라 한 줄(원문은 펼친 상자에만), 코딩 에이전트의 영문 결과 문구("File created successfully …")를 화면 말로.

## 3. 화면별 바뀐 것과 참고한 화면

| 화면 | 바뀐 것 | 참고한 화면(file:line 또는 URL) |
|---|---|---|
| 처리 건 상세 · 진행 상황 | 요약 카드(상태 · 걸린 시간 · 단계 · 도구 호출), 흐름도 지금 단계 흐르는 테두리, 처리 과정 단계 카드 · 도구 행 | Dify `web/app/components/workflow/run/status.tsx` · `tracing-panel.tsx` · `node.tsx` (github.com/langgenius/dify); process-gpt-vue3 `src/components/ui/EventTimeline.vue`, `src/ds/components/PgToolSteps.vue` · `PgToolStep.vue`, `src/assets/css/globalStyle.css` running-animation (/Users/uengine/process-gpt/services/frontend) |
| 승인 요청 카드 | 카드 한 장 · 추천 · 이유 · 근거 · 승인 한 버튼, 진 안 접기 | Camunda Tasklist 작업 상세 https://docs.camunda.io/docs/components/tasklist/userguide/using-tasklist/ ; process-gpt-vue3 `src/components/apps/todolist/WorkItem.vue`, `DefaultWorkItem.vue:33,92`(하단 주 버튼 하나), `src/ds/components/PgCard.vue` · `PgAlert.vue` · `PgChip.vue` |
| 결과 보고 카드 | 정상/미달 배지 · 측정값 · 시스템이 한 일 | Dify `workflow/run/status.tsx`; n8n 실행 목록 성공/실패 배지 https://docs.n8n.io/workflows/executions/ ; process-gpt-vue3 `src/components/apps/todolist/InstanceOutput.vue` |
| 처리 건 목록 | 목록 ↔ 상세 두 칸, 선택 행 왼쪽 막대, 끝난 건 값 한국어(answered → 답함) | Camunda Operate 인스턴스 목록 https://docs.camunda.io/docs/components/operate/userguide/basic-operate-navigation/ ; Linear 이슈 목록(얇은 경계 · 32px 행) |
| task 상세 | 넓은 표 숫자 안 쪼개짐(결함 2), 넘긴 값 받는 단계는 실제로 받은 단계만(결함 6 · 7), 펼친 칸 유지(결함 15) | process-gpt-vue3 `src/components/apps/todolist/WorkItem.vue`(작업 탭 · 입력/출력) |
| 에이전트에게 질문 | 입력 칸 한 번만 그리고 대화 · 처리 과정만 갱신, 같은 실시간 추적 | Dify `web/app/components/base/chat/chat/answer/tool-detail.tsx`; process-gpt-vue3 `src/components/ui/WorkItemChat.vue` |
| 결함 시뮬레이션 | 맨 위 "수업 시나리오 시작" 카드 3장(A 쿨러 열화 주입 · B 운전시간 +300 h · C 자재 출고 −2). 백엔드가 없는 버튼은 "준비 중" | n8n 수동 실행 카드; Linear 빈 상태 카드 |
| 셸 · 공통 | 색 · 글자 · 버튼 · 칩 · 탭 · 접기 · 폼 토큰(`theme.css`) | process-gpt-vue3 `src/ds/styles/tokens.css` · `motion.css`, `src/ds/components/PgButton.vue` · `PgTextField.vue` · `PgField.vue` · `PgCard.vue`, `src/ds/vuetify-bridge/overrides.css`, `src/layouts/full/vertical-sidebar/` |
| 흐름 가져오기 | 입력 칸 한 줄 문법 대신 칸마다 행(값 이름 · 화면 이름 · 종류 · 고를 값)(결함 6) | process-gpt-vue3 폼 정의 편집(칸 목록) |
| 흐름 판본 배포 | 정의 선택에 내부 id 숨김, 비교 결과의 `ev:`/`task:` id → 이름, 파일 고르기 한국어(결함 11) | — (기존 화면 정리) |
| 담당 배정 | 칩 안 작은 ×(겹침 없음, 결함 9), 역할 이름 화면 말로 통일(결함 13) | Linear 라벨 칩 × |
| 도구(MCP) | 제목 두 번 없앰, 기준 서버는 "기본 에이전트가 쓰는 서버", 워커 PC 에서 뜨는 명령형 서버는 "워커에서 실행"(결함 10) | — |
| 판단 채점 | 안내의 내부 API 경로 제거, 제목 두 번 없앰(결함 18) | — |
| 지식 관리 | 골든 보고 없을 때 콘솔 404 없음(`?optional=1`, 결함 12) | — |

브랜드 로고 · 그림은 쓰지 않았다(색 토큰만).

## 4. A160 화면 결함 목록 상태

| # | 내용 | 상태 |
|---|---|---|
| 1 | 되돌리기 뒤 학생 흐름 처리 건 500 | 고침(서버 404 + 사유, 화면 "이 처리 건은 열 수 없습니다") |
| 2 | task 상세 표 숫자 세로 쪼개짐 | 고침 |
| 3 | 토큰 사용량 줄 반복 · 원문 JSON · 호스트 경로 · 모델 이름 | 고침 |
| 4 | 안전 장치가 막은 명령이 빨간 줄 · `answered` 영문 | 고침("안전 장치가 막음" 칩, 값 화면 말) |
| 5 | 잘린 결과인데 "완료" 칩 | 고침("결과 잘림" 칩) |
| 6 | 넘긴 값 이름 · "받는 단계 없음" 반복 · 입력 칸 문법 노출 | 고침 |
| 7 | 받는 단계에 취소된 갈래 | 고침 |
| 8 | 끝난 처리 건에 영향 폼이 펼쳐짐 | 고침(필요할 때만 펼침) |
| 9 | 빼기 버튼이 칩과 겹침 | 고침 |
| 10 | MCP 제목 두 번 · 기준 서버 혼동 · 명령 없음 빨강 | 고침 |
| 11 | 배포 정의 선택 id · `ev:` 노출 · 영문 파일 버튼 | 고침 |
| 12 | 골든 보고 404 콘솔 오류 | 고침 |
| 13 | 역할 이름 불일치 | 화면에서는 고침(업무분장 · 작업함이 같은 이름). 시드의 사용자 행 이름 `정비관리자`(`it/supabase/seed.sql:69`)는 C1 몫이라 그대로 |
| 14 | "[검사]" 표식 | 시험 데이터 잔재 — 고치지 않음 |
| 15 | 펼친 칸이 다시 그려져 닫힘 | 고침 |
| 16 | 1회차 task 에 2회차 값 | 안내 문구 유지(구조상 처리 건 현재 값) — 남김 |
| 17 | 질문하기 근거 대조가 엄격 | 기능 판단이라 보고만(고치지 않음) |
| 18 | 채점 안내 API 경로 · 제목 두 번 | 고침. 데이터 연결의 열 이름(`설비 code/name/line`)은 DB 주석 원문이라 유지 |

## 5. 캡처 (`.evidence/a161-u1/`)

모두 1440 · 390 폭. `.evidence/` 는 git 에 넣지 않는다(로컬 증거).

| 장면 | 고치기 전 | 고친 뒤 |
|---|---|---|
| 에이전트 작업 중 실시간(도구 호출이 한 줄씩) | `before/case-running-stream-*.png` | `after/live-agent1-*.png` · `live-agent2-*.png` |
| 승인 화면 | `before/case-running-*.png`(카드 4장 나열 · 폼) | `after/approve-*.png`(요약 카드 한 장) |
| 승인 뒤 시스템 실행 실시간 · 결과 보고 "확인 중" | — (없던 화면) | `after/live-system1~3-*.png` |
| 끝난 처리 건 · 결과 보고 "정상" | `before/case-done-flow-*.png` | `after/done-progress-*.png` · `done-result-*.png` |
| task 상세 | `before/task-diagnose-*.png` | `wip/case-live2-*.png` |
| 결함 시뮬레이션(수업 시나리오 시작 카드) | — | `after/pages/scenario-*.png` |
| 나머지 화면(홈 · 작업함 · 이상 확인 · 판단 규칙 · 흐름 · 지식 관리 · 질문 · 에이전트 · MCP · 채점) | `before/<화면>-*.png` | `after/pages/<화면>-*.png` |

실제 스택(이 워크트리 포털을 nginx 가 서빙) · 실제 워커(Claude Code)로 쿨러 처리 건 두 바퀴(`after/run1/` 첫 바퀴, `after/` 둘째 바퀴: `anomaly_response.6ab13e9c…`, 추천안 승인 → 정상 종결).
자동 점검(`after/pages/report.json`, `after/live-run.out`): 22개 화면 + 처리 건 장면 모두 페이지 오류 0 · 콘솔 오류 0 · 가로 넘침 0 · "정비창" 0.
캡처 스크립트: `after/live.py`(원인 주입 → 장면별 캡처 → 추천안 API 승인), `after/pages.py`, `after/preview.py`.

## 6. 시험 · 빌드

- 단위 시험 전체: `.venv/bin/python -m pytest -q` → **1,700 통과 · 4 건너뜀**, 실패 1(`tests/test_mcp_check.py::test_html_page_is_not_an_mcp_endpoint`, 고치기 전 `pytest-before.log` 에서도 같은 실패 — U1 과 무관, C2 보고서에도 같은 기록). 로그 `.evidence/a161-u1/pytest-after.log`.
- 포털 JS 문법: `node --check it/portal/www/*.js` 모두 통과. 포털은 빌드 단계가 없다(nginx 가 폴더를 그대로 서빙, 캐시 무효화는 `index.html` 의 `?v=` 값).

## 7. 남은 것

1. **에이전트의 혼잣말이 영어**로 흐른다("Next I'll look up …"). 화면이 아니라 워커 지시(언어) 문제 — 워커 프롬프트에 "판단 문장은 한국어"를 넣어야 한다(에이전트 · 워커 담당).
2. **반려 버튼이 없다.** 지금 서버에는 승인(select)만 있고 반려 API 가 없다. 확정 흐름(승인 1회)에서 반려 가지를 그릴지 C3 조립에서 정하면, 카드 아래 버튼 하나로 붙인다.
3. **결과 보고의 측정값**: A 흐름은 재관측이 `recovered` 참/거짓만 남겨 측정값(유온 등)이 카드에 없다. C2 의 결과 보고 부품이 `result_report.values` 로 내면 그대로 보인다.
4. **B 원인 버튼**(운전시간 +300 h)은 백엔드 주소가 아직 없어 "준비 중". C(자재 출고 −2)는 C2 의 `POST /api/simulate/spare-issue` 가 스택에 올라오면 저절로 켜진다(openapi 로 확인).
5. 시나리오 데이터 원문의 "정비창"(카드 설명 · 작업지시 문구)은 화면에서 "예정된 정비 시간"으로 바꿔 보인다(`UI.words`). 원문 자체는 C1 · C2 몫.
6. 결함 16(1회차 task 에 현재 값) · 17(질문하기 근거 대조 엄격)은 남김.
7. 시험 잔재: 캡처용 쿨러 처리 건 2건(사유 "[U1 화면 캡처] 추천안 승인")이 처리 건 목록에 남는다. 설비는 끝에 `/api/reset` 으로 되돌렸다.
