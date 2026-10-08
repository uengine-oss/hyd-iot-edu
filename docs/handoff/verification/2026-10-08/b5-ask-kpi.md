# B5 · 에이전트에게 질문하기 + KPI 목표 · 관점 중요도 바꿔 보기 (2026-10-08 밤, worktree `worktree-b5-ask-kpi`)

범위: `TODO.md` 확정 TODO B의 **B5** — "질문 → 실제 도구 조회 → 근거 있는 답 또는 '답할 수 없음+이유', KPI 목표 변경 시 달성/미달 변화 ·
관점 비중 변경 시 순위 변화, 원본 불변". DECISIONS 110 결정 ⑤(질문하기 · KPI 목표 · 중요도 바꿔 보기)와 ⑧(수업 기본은 결정론 경로).
마이그레이션 없음(`20261008000045` 미사용 — 새 표가 필요 없었다). docker · compose · Supabase CLI 사용 안 함.

## 1. 원본 근거 (읽기만)

| 원본 | 파일:줄 | 원본이 하는 일 | HYD에서 한 것 · 차이 판정 |
|---|---|---|---|
| process-gpt-vue3 `867e8cf` | `src/router/MainRoutes.ts:262-263` (`/agent-chat/:id` → `AgentChat.vue`) | 에이전트 하나를 열어 탭으로 대화(학습 · 질문 · 행동) | 포털 `#/ask` 한 화면에 **답할 에이전트 고르기** + 질문. 에이전트 화면 안 탭이 아니라 질문 화면 안 선택 — 차이 있음, 유지(학생이 10초 안에 질문 칸을 찾게) |
| 같은 레포 | `src/components/AgentChatQuestion.vue:39-55` | 질문 모드: 채팅방 `${agent}-question` 하나에 메시지를 쌓고(이전 대화 기억) LLM 생성기로 답 | **질문 하나 = 처리 건 하나**(정식 정의 `ask_agent` 1.0), 이전 질문을 기억하지 않음(TODO "한 질문 → 한 답"). 답은 워커가 MCP 도구로 실제 조회한 결과로만 — 차이 있음, 유지(과정 · 근거를 처리 건의 task 상세로 보이는 것이 목적) |
| 같은 레포 | `src/components/ui/WorkItemChat.vue:35-43,101-107` | 작업 메시지를 도구(formHandler 등)별로 그림 | 질문 화면의 "도구 호출" 줄(도구 이름 · 입력 · 결과 접기, 실행 중/성공/실패)과 "처리 과정 보기"(기존 U1 task 상세 `#/instances/<id>/task/<wid>`) |
| 같은 레포 | `src/views/admin/tabs/KpiIndicatorManager.vue:121,344` | 관리 화면에서 KPI 목표값(`target_value`)을 **저장** | 목표값 **시험 판정**만(저장 없음, 지식 그래프 `Measure.target` 불변, "원래대로"). 차이 있음, 유지(스키마 · 기준 데이터 고정, DECISIONS 110 "시험 실행") |
| 같은 레포 | `src/views/strategy/StrategyBoard.vue:438,593` | 관점 → 목표 → KPI 달성률 · 가중 점수(`weighted_score`) 표시 | KPI 화면의 기존 관점 → 목표 → 지표 카드에 "시험 목표 · 원래 판정"을 덧붙임. 관점 비중은 What-if 카드 점수에 적용(전략보드에는 순위 개념이 없음) |
| HYD 회귀 검사기 | `scripts/probe_business_questions.py:45`, `probe_timeseries_questions.py:80`, `probe_rule_questions.py:90` (`definition(did)`) | 실행마다 임시 정의(`business-question-<난수>` 등)를 등록하고 처리 건을 시작해 답 · 도구 호출을 정답 SQL과 대조 | 세 정의(업무 DB · 시계열 · 규칙 질문)의 지시를 하나로 묶어 **정식 파일** `it/process/definitions/ask_agent_v1.json`으로 올림 — 기동 때 `instance_mode.build`가 등록. 검사기는 그대로 둠(정답 대조는 검사기 몫, 포털은 정답 없음) |

## 2. 구조와 데이터 리니지

```
[질문하기]
포털 #/ask (ask.js) ── POST /api/ask {question, agent, by, request_id} ──▶ procsvc/ask.start
   ├ 질문 검사(1~1000자) · 에이전트 검사(users.is_agent, 시스템 제외 — 없으면 404)
   ├ 준비 검사 readiness(worker_status()) — 워커 연결 없음 → 503 + 사유, 처리 건을 만들지 않음 (legacy 모드면 그 사실까지)
   └ rt.start_definition('ask_agent','1.0', event 'ask:<request_id>', values{question, asked_by}, role_endpoints{'답변 에이전트': 고른 에이전트})
        └ engine.new_workitem: 인스턴스 role_bindings(시작 때 고른 담당)가 정의 기본(sys:agent)을 이김 → todolist.user_id = 고른 에이전트
워커(실제 Runner) ── fetch_pending_task → context.prepare(row.user_id → 그 에이전트 프로필 · 스킬 · MCP 서버) → CLI 실행
   ├ 도구 호출마다 events(tool_usage_started/finished, todo_id) — 처리 과정 화면 · 질문 화면이 같은 행을 읽음
   └ save_task_result → 엔진 poll_once → 폼 계약 ask-answer-v1 검사(교정 루프 A077: 형식이 틀리면 같은 세션에 고쳐 달라고) → DONE → 처리 건 COMPLETED
포털 1.5초마다 GET /api/ask/{id} ── ask.view: 상태 · 도구 호출(시작/끝 짝) · 결론 verdict
   verdict: cannot_answer → 에이전트의 이유 / answered인데 성공한 MCP 조회 0 → "답할 수 없음(서버)" / 근거 질의가 실제 호출 입력에 없음 → "답할 수 없음(서버)"
            / 근거 확인 → 답 + 근거(질의 · 결과 · "실행 기록에서 확인됨")
GET /api/ask (지난 질문) · GET /api/ask/status (준비 · 에이전트 목록) · POST /api/ask/reset (끝난 질문 기록만 is_deleted)

[KPI 목표값 바꿔 보기]
포털 KPI(kpi.js) "목표값 바꿔 보기" ── POST /api/kpi/try {period, targets{지표: 숫자}} ──▶ kpi.report(targets=…)
   그래프 Measure(읽기) → check_targets(없는 지표 · 숫자 아님 → 400 사유) → 사본에만 target 교체 → 같은 실적 계산 → 시험 목표로 판정
   지표마다 original{target, status, rate}(원래 목표로 본 판정) · 보고서 trial{targets, changed[], note} · summaryOriginal
   "원인 찾기"는 POST /api/kpi/try/trace (설비별 달성/미달도 시험 목표로). 원래대로 = 시험 목표 비우고 GET /api/kpi

[What-if 관점 중요도]
POST /api/agent/whatif ── 판단 묶음 capture + 그래프 t3_perspectives(Perspective ← Objective ← Measure, 읽기) → bundle.perspectives
POST /api/agent/whatif/{id}/try {policy{perspectives{관점: 배}}} ── check_policy(없는 관점 · 0~10배 밖 → 400) → measure_weights
   → cards.evaluate(measure_weights=…): BSC 득실 무게 × 그 지표 관점의 배수 → 정책 점수의 '성과 지표' 항목 → 1순위
POST …/boundaries ── 기존 find_boundaries에 관점 축(v:<관점>, 이 판단의 득실에 나오는 관점만) 추가 → 이분 → 그 값으로 다시 계산해 1순위 변경 확인
```

- 실패 · 분기(빈 성공 없음): 워커 없음 503(처리 건 0) · 실행 실패는 워커 오류 문장 그대로("에이전트 실행이 실패했습니다: RunFailed: …") · 형식 오류는 교정 중 표시 ·
  10초 넘게 아무도 안 집으면 워커 연결을 다시 확인해 사유 · 근거 없는 답은 "답할 수 없음 + 이유"(에이전트가 낸 답은 접어서 "근거 확인 안 됨"으로만).
  KPI · What-if는 그래프를 못 읽으면 그 기능만 사유와 함께 꺼짐(관점 중요도: "지식 그래프에서 BSC 관점을 읽지 못했습니다: …").
- 원본 불변: 질문은 정의 · 에이전트 · 업무 DB를 바꾸지 않는다(조회 전용 지시 + 워커의 MCP 쓰기 차단은 기존 그대로). KPI 시험은 읽은 행의 사본, What-if는 기존 지문(fingerprint) 검사 그대로.
- 결정론 대체 모드(AGENT_BRIDGE=legacy)에서 질문하면: `instance_mode._legacy_polling`과 `legacy_assessment`는 경보 정의의 네 작업만 집으므로
  질문 작업을 아무도 집지 않는다 → 그래서 워커 연결이 없으면 처리 건을 만들지 않고 503:
  "지금은 결정론 대체 모드(AGENT_BRIDGE=legacy)입니다. 이 모드의 내장 판단은 경보 처리 건의 판단 4단계(…)만 채우고, 자유 질문에 답할 AI 일꾼(워커)은 없습니다.
  질문은 처리 건으로 만들지 않았습니다. 워커 연결 확인: <WORKER_URL> — <오류>. 워커를 켜고(scripts/run_worker_host.sh) process의 WORKER_URL이 그 워커를 가리키면 질문할 수 있습니다."
  legacy 모드여도 워커가 연결돼 있으면 질문 작업은 워커가 집는다(같은 `fetch_pending_task('cliagents')`).

## 3. 바꾼 파일

- 새 파일: `it/process/procsvc/ask.py`, `it/process/definitions/ask_agent_v1.json`, `it/portal/www/ask.js`, `it/neo4j/templates/t3_perspectives.cypher`,
  `tests/test_b5_ask.py`(16) · `tests/test_b5_kpi_targets.py`(11) · `tests/test_b5_whatif_perspectives.py`(7) · `tests/test_b5_portal.py`(3), 이 문서.
- 최소 수정(줄 추가 위주):
  - `it/process/procsvc/engine.py` — `instance_binding()`(인스턴스 role_bindings 우선, 없으면 정의) · `new_workitem` · `reach`가 그것을 씀. 새 인스턴스는 정의 바인딩을 복사하므로 기존 흐름은 같다.
  - `it/process/procsvc/instances.py` — `start_definition(..., role_endpoints=None)`(정의에 없는 역할은 400 사유).
  - `it/process/procsvc/procdb.py` — `hide_instances(tenant, def_id, ids)`(Memory · Pg, 끝난 것만 `is_deleted`).
  - `it/process/procsvc/manual_extraction.py` — 교정 루프 계약 목록에 `ask-answer-v1` + 검사 호출 2줄.
  - `it/process/procsvc/instance_mode.py` — 기동 때 질문 정의 등록 2줄. `it/process/procsvc/main.py` — `ask.register` 5줄.
  - `it/process/procsvc/kpi.py` — `check_targets` · 시험 판정 · `POST /api/kpi/try` · `/api/kpi/try/trace`. `tests/test_kpi.py` — 라우트 목록 검사에 POST 2개 추가(시험 계산, 쓰기 없음).
  - `it/agent/agentsvc/cards.py` — `evaluate(..., measure_weights=None)`(없으면 지금과 같음). `whatif.py` — 관점 읽기 · 검사 · 가중 · 경계값 축 · 카드별 관점 득실.
    `main.py` — whatif 시작 때 관점 읽기(실패는 사유) · 검사에 관점 전달 · 응답에 `perspectives`. `tools/mcp_kg.py` — `perspectives()`.
  - `it/portal/www/kpi.js` — 목표값 바꿔 보기 접기 · 카드 "시험 목표 · 원래 판정" · 시험 중 원인 찾기. `whatif.js` — 규칙 탭 "관점 중요도 바꿔 보기" · 관점 경계값 적용(`_W`·`_render` 노출은 시험용).
  - `it/portal/www/index.html` — 메뉴 버튼 1 · `#view-ask > #askView` · 스크립트 1(+ kpi · whatif 캐시 꼬리표). `ui.js` — 메뉴 이름 1줄.
  - `shell.js`는 고치지 않았다: `ask.js`가 kpi.js와 같은 방식(`#view-ask`가 열리면 스스로 mount)으로 붙는다. 메인이 셸 MOUNTS에 `ask: 'hydAsk'`를 넣어도 된다(`window.hydAsk.mount/show`).

## 4. 시험 결과

- `tests/test_b5_ask.py` 16: 정식 정의 등록(기동 · 재등록 같은 판본, 지시에 표 · 열 · 정답 없음) / **질문 → 실제 워커 Runner(가짜 CLI) → 도구 호출 이벤트 4행 → 엔진 → COMPLETED → 근거 확인된 답** /
  고른 에이전트가 todolist 담당 · 워커 지시(프로필) · `.mcp.json`(그 에이전트 서버만)까지 닿고 기준 정의는 그대로 / 시스템 · 사람 · 없는 에이전트 · 빈 질문 · 1001자 · 없는 역할 거절 /
  cannot_answer → 에이전트 이유 / 도구 호출 0인 답 → 서버가 "답할 수 없음" / 근거 질의가 호출 기록에 없음 → 거절 / 거절된 질의(result≠ok)는 근거 아님 / 근거 없는 answered → 교정 중 /
  JSON 아닌 답 → "에이전트 실행이 실패했습니다: RunFailed: …" / **legacy · 워커 없음 → 처리 건 0 + 사유** / 대기 중 워커 사라짐 → 사유 / 같은 request_id → 같은 처리 건 / 되돌리기(끝난 것만) / HTTP 경로 / process 앱 마운트.
- `tests/test_b5_kpi_targets.py` 11: 가동률 목표 95 → 90이면 미달 → 달성(실적 90.56 그대로, 달성률 100.6, 원래 판정 옆에) · 요약 미달 −1 · 원래 요약 / 목표 없던 DOWN 지표에 목표 → 미달 / 계산 불가는 그대로 /
  역추적이 시험 목표로 설비 판정 / **원본 행 불변 · 같은 입력 같은 결과** / 잘못된 목표 5종 사유 / POST 경로 · GET 원본.
- `tests/test_b5_whatif_perspectives.py` 7: 관점 이름 · 지표 소속은 시드 `instances.cypher`에서(손으로 적지 않음), 이 판단에 쓰이는 관점만 표시 / 내부 프로세스 2배 → 관점 득실 · `bsc` 점수 2배, 쓰이지 않는 재무 5배 → 점수 그대로, 5배 → 1순위 변경 /
  **관점 경계값(3.458배)에서 다시 계산하면 1순위가 실제로 바뀌고 바로 앞은 원래 1순위** / 원본 묶음 · 정책 불변 · 같은 입력 같은 결과 / 잘못된 비중 사유 / 에이전트 API 끝까지(업무 DB 거래 0) / 그래프 없으면 사유 400.
- `tests/test_b5_portal.py` 3: node로 실제 `ui.js` + 화면 코드를 돌려 그림 — 질문 · 도구 호출 · 답 · 근거 · "실행 기록에서 확인됨" · 처리 과정 링크 · 답할 수 없음 + 이유 · legacy 사유, KPI 시험 목표 · 원래 판정 · 미달 → 달성, 관점 칸 4개 · 1순위 변경 문장. 영문 id 노출 0.
- **일부러 깨뜨리기(9건 모두 잡힘)**: ① 인스턴스 담당 무시 → 2 실패 ② 에이전트 자기 보고를 믿음(도구 대조 끔) → 3 실패 ③ 워커 없어도 준비됨 → 2 실패 ④ 거절된 질의를 성공으로 → 1 실패
  ⑤ KPI 시험이 원본 행을 고침 → 4 실패 ⑥ 시험 목표 무시 → 3 실패 ⑦ 관점 비중 무시 → 3 실패 ⑧ 관점 경계값 축 없음 → 2 실패 ⑨ 비중 범위 검사 없음 → 1 실패.
- 기존 관련 시험: `test_instance_mode` · `test_worker` · `test_kpi` · `test_whatif` · `test_cards` 통과. 전체 `pytest -q`: 아래 §4-1.
- 화면(Playwright, docker 없이 하네스 — 실제 `ask.register`/`kpi.register`/`instance_mode.mount` + MemoryRepo + 진짜 워커 Runner(가짜 CLI, 도구 호출 사이 1~1.5초) + 실제 agent 앱(What-if)을
  18080 · 18091 · 18088에 띄움, 메인 스택 포트와 겹치지 않게 `layers.js` 포트만 하네스에서 바꿔 냄): 메뉴 "에이전트에게 질문" → 학생 에이전트 고름 → 보내기 → **도구 호출이 한 줄씩 실시간**(2개째 실행 중 캡처) →
  답 + 근거 1개 확인 · 처리 과정 링크 `#/instances/ask_agent.<id>/task/<wid>` → 환율 질문 Enter → 답할 수 없음 + 이유 → 워커 끔 → 보내기 → legacy 사유 · 처리 건 0 /
  KPI 목표 가동률 90 · 전력 150 → "설비 가동률 … 목표 95 → 90 · 미달 → 달성", "전력 사용량 … 목표 없음 → 150 · 목표 없음 → 미달", 전력 원인 찾기(시험 목표 150 기준) → 원래대로 → 배너 사라짐, API 원본 목표 95 /
  What-if 규칙 탭 관점 4칸(재무 · 고객 · 내부 프로세스 · 학습과 성장) · 내부 5배 → "판단 1순위가 '팬 최대 + 부하 80 %'에서 바뀌었습니다 · 가치의 상충", 경계값 "관점 '내부 프로세스' 중요도 1 배 → 3.458 배 이상이면 1순위 '팬 최대'".
  화면 오류 0 · 영문 id 0. 증거 `.evidence/b5-ask-kpi/`(gitignore): `ask_1_live_tool_calls.png` · `ask_2_answer_evidence.png` · `ask_3_cannot_answer.png` · `ask_4_no_worker_reason.png` ·
  `kpi_1_trial_targets.png` · `kpi_2_trace_under_trial.png` · `whatif_1_perspective_weight.png` · `walkthrough.json/log` · `mutations.log` · `pytest_full.log`. 하네스 · 스크립트는 세션 scratchpad(`b5_live.py` · `b5_shots.py`), 끈 것 확인.

### 4-1. 전체 시험
`pytest -q` 전체(작업 기준 3f6c9c0 위): **1545 passed · 1 skipped** (B5 새 시험 37개 포함). 첫 전체 실행에서 `test_kpi.py::test_portal_screen_renders…` 1건이 실패 —
그 시험은 새 상태 칸(targets) 없이 `_render`를 부르는데 시험 목표 패널이 그것을 읽어 터졌음 → `trialPanel`이 빈 칸을 기본값으로 채우게 고친 뒤 통과(옛 호출자도 깨지지 않음). `node --check` ask.js · kpi.js · whatif.js 통과. 로그 `.evidence/b5-ask-kpi/pytest_full.log`.

## 5. 메인이 라이브로 확인할 경로 (합친 뒤)

1. process 재기동 뒤 `curl -s localhost:8080/api/process/definitions | grep ask_agent` → `ask_agent 1.0` 등록. `curl -s localhost:8080/api/ask/status` → `ready`(워커 연결) · `agents`.
2. **수업 기본(AGENT_BRIDGE=legacy, 워커 없음)**: 포털 `#/ask` → 배너 "지금은 답할 일꾼이 없습니다 … AGENT_BRIDGE=legacy …" → 보내기 → 같은 사유, `GET /api/ask` 빈 목록(처리 건 0).
3. **실제 워커**(`.env` `WORKER_URL=http://host.docker.internal:8097`, `bash scripts/run_worker_host.sh`): `#/ask` → "완제품 재고가 가장 적은 설비와 그 수량은?" → 도구 호출(enterprise describe_catalog → query)이 한 줄씩 →
   답 + 근거 "실행 기록에서 확인됨" → "처리 과정 보기"로 task 상세(같은 도구 호출 · SQL) → 워커 콘솔 `[도구 시작]` 줄. 쓰기 0: `curl localhost:8095/api/transactions` 늘지 않음.
   데이터 밖 질문(예: 다음 달 환율) → "답할 수 없음 + 이유". 다른 에이전트(B1에서 만든 학생 에이전트)를 골라 같은 질문 → 처리 과정의 담당이 그 에이전트, 도구가 그 에이전트 서버로 한정.
4. KPI `#/kpi` → "목표값 바꿔 보기" → 지표 하나 목표 입력 → 시험 판정 → 배너의 "미달 → 달성/달성 → 미달" · 카드 "원래 목표 · 원래 판정" → 원인 찾기 → 원래대로. `GET /api/kpi` 목표 그대로.
5. What-if `#/whatif` → 불러오기 → 규칙 바꿔 보기 → 관점 중요도 칸 이름이 그래프 관점 4개인지, 이 판단 득실에 나오는 관점 표시 → 비중 바꿔 다시 계산 → 1순위 변화 · "규칙마다 1순위가 바뀌는 값"에 관점 경계값 → "이 값으로 계산".
   (`t3_perspectives.cypher`는 agent 이미지의 `/srv/templates`로 들어가므로 agent 이미지 재빌드 필요)

## 6. 남은 위험 · 미검증

- 라이브 Neo4j · Supabase · 실제 Claude Code/Codex 워커로는 돌리지 않았다(docker 금지). 실제 CLI가 근거 `query`를 호출 입력과 **같은 문자열**로 적는지가 근거 대조의 전제 —
  공백 · 대소문자 · 끝 `;`만 정규화한다. 다르게 적으면(예: 다른 SQL을 근거로 적음) "답할 수 없음(서버)"이 되며, 그것이 의도(근거 확인 불가)지만 실측으로 빈도를 봐야 한다.
- `instance_binding`은 인스턴스 role_bindings를 우선한다. 기존 인스턴스는 정의 바인딩 사본이라 같지만, B1(task → 에이전트 매핑)이 같은 자리(`engine.new_workitem`)를 고치면 합칠 때 우선순위를 정해야 한다
  (제안: 시작 때 고른 담당 > B1 매핑 > 정의 기본).
- 되돌리기(`POST /api/ask/reset`)는 bpm_proc_inst `is_deleted`만 켠다. Neo4j 실행 계층 투영(ProcessInstance 노드)은 지우지 않는다(정리 스크립트 A115와 달리). 진행 중인 질문은 남긴다.
- 실제 시드 그래프에서 쿨러 · 펌프 · 팬 카드의 득실이 여러 관점에 걸치는지는 라이브에서 확인 필요(시험 묶음은 내부 프로세스 관점만 — 그래서 시험은 "쓰이지 않는 관점은 그대로"도 본다).
- 관점 경계값은 같은 값이 카드별로 여러 줄 나온다(기존 U12 경계값 표시 방식 그대로, 중복 줄 정리는 UI/UX 단계).
- HANDOFF §9 · 실라버스 갱신은 메인이 합칠 때(동시 작업 충돌 회피).

## 7. 비유와 스스로 판정할 체크 질문

- 비유: 질문 하나 = **민원 접수증 한 장**. 담당자(고른 에이전트)가 서류철(MCP 도구)을 실제로 뒤진 기록이 접수증 뒤에 붙고, 기록에 없는 서류를 근거라고 적으면 접수창구(서버)가 "확인 불가"로 돌려준다.
  목표값 바꿔 보기는 **시험지 채점 기준만 바꿔 보는 연필 메모**(답안 · 원래 기준표는 그대로), 관점 중요도는 **저울 접시마다 다른 추**를 올려 보는 것.
- 체크 질문: ① 답 옆 근거의 SQL이 "처리 과정 보기"의 도구 호출 입력과 같은가? ② 데이터 밖 질문에 지어낸 답 대신 "답할 수 없음 + 이유"가 나오나? ③ 워커 없이 보내면 처리 건이 생기지 않고 사유가 보이나?
  ④ 목표만 바꿨을 때 실적 숫자는 그대로이고 판정만 바뀌나, "원래대로" 뒤 지식 그래프 목표가 그대로인가? ⑤ 관점 비중을 경계값 바로 위 · 아래로 넣었을 때 1순위가 실제로 갈리나?
