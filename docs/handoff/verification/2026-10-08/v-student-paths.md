# V — 학생 동선 4시나리오 라이브 검사기 작성 메모 (2026-10-08, A160 ⑤)

검사기: `scripts/probe_v_student_paths.py` (작성만 함 — 라이브 실행은 메인이 한 번).
근거 결정: DECISIONS §110 ①~⑤ · §111 ④, TODO "확정 TODO B" B1~B7 · V 행, HANDOFF A158 · A159 · A160.

원칙
- 브라우저 클릭 대신 **포털 JS가 부르는 것과 같은 HTTP API를 같은 본문으로** 순서대로 부른다(아래 표의 "포털 근거" 열).
  예외: 고장 주입(`plant-sim /api/fault`)과 설비 · 감지기 상태 읽기는 포털이 아니라 강사 시나리오 조작 · 관찰 경로다(기존
  `scenario_instance_test.py` · `scenario_pump_fan_test.py` 와 같은 호출).
- 정답 하드코딩 없음: 쿨러 1순위는 판단의 사실 · 순위 정책으로 다시 계산(`scenario_instance_test.policy_top` import),
  그림의 task id 는 등록된 정의의 `bpmnImport.mapping.tasks`(그림 id → 고른 부품)에서 읽는다(`flow_ids`). 펌프 · 팬 · 가림의
  기대(원인 · 추천 · 제외 카드 · 재관측 기준)는 `scenario_pump_fan_test.py` 와 같다.
- 증거: `--out` 폴더에 단계별 JSON(`<단계번호>-<이름>.json`), `checks.json`, `failures.json`(단계 · 요청 method/url/body ·
  응답 상태 · 앞 300자), `probe.log`, 작동유는 `4-oil/`(probe_b7_oil_live 증거 그대로).
- 마지막 줄 `ALL PASS — n/n checks` 또는 `k FAILED — m/n checks`(실패 목록은 그 앞 줄들) — `scripts/run_regression.py`
  PASS_PATTERNS 첫 식과 맞음(오프라인 자기 시험으로 확인).

## 실행

```
.venv/bin/python scripts/probe_v_student_paths.py --expect worker --out .evidence/a160/v-worker   # AGENT_BRIDGE=off + 호스트 워커 1~2
.venv/bin/python scripts/probe_v_student_paths.py --expect legacy --out .evidence/a160/v-legacy   # AGENT_BRIDGE=legacy + 워커 정지
  --only cooler|pump|fan|oil|bundle (쉼표로 여러 개)   --no-reset-start   --keep-config
  --mcp-url http://dmn-mcp:8198/mcp (정상 등록할 주소)   --whatif-asset/--whatif-pattern (기본 HYD-01 · COOLER_DEGRADATION)
```
`--only pump|fan|bundle` 단독은 앞 실행이 남긴 학생 구성(배포된 `my_cooler` + 원인 진단 배정)을 다시 쓰고(`load_existing`),
없으면 B1~B4 를 먼저 만든다. 시작 전 "기준으로 되돌리기"는 전체 실행 · `--only cooler` 에서만(끄려면 `--no-reset-start`).

## 학생 동선 표 (단계 · 부르는 API · 기대 · 근거 파일:줄)

| 단계 | 부르는 API (본문) | 기대 | 포털 근거 | 서버 근거 |
|---|---|---|---|---|
| 0 준비 | GET /api/process/mode · /healthz · 워커 :8097/:8098 /health | instance · AGENT_BRIDGE(worker=off, legacy=legacy) · TIME_SCALE 20 · 워커 상태가 모드와 맞음 | — | instance_mode.py:666-671 |
| 0 | GET /api/config/export → 저장, POST /api/config/reset {by} | 시작 상태 보관 · 학생 구성 정리(열린 처리 건이면 409 사유로 멈춤) | configBundle.js:50 · :120 | config_bundle.py:867-883, :242-262(409 조건) |
| 1 B1 | GET /api/agents · /api/agents/sys:agent · /api/agent-authoring/options | 기본 에이전트 origin=seed · editable=false, 실행 설정 스냅숏 | agents.js:47 · :69 | agents_api.py:85-115 |
| 1 B1 | PUT /api/agents/sys:agent | 403 + "복제해서 고치기" | agents.js:261 | agent_authoring.py:105-109 · :161-163 |
| 1 B1 | POST /api/agents/sys:agent/clone {} → PUT /api/agents/{id} {name, role, goal, persona, model, tools[], skills[]} | 사본 origin=user, 이름 바꿈 | agents.js:335 · :261 | agent_authoring_api.py:102 · :112, agent_authoring.py:171-188 |
| 1 B1 | POST /api/skills {skill_name, description, content(SKILL.md)} → POST /api/agents/{id}/skills {skill_name} | 201 · 붙은 스킬 목록 | agents.js:262 · :398 | agent_authoring.py:264-274 · :299-307 |
| 1 B1 | POST /api/role-members {role_id: role:operator, user_id: user:lee-prod} | 201 · 구성원에 포함(역할 구성원이 이미 둘 → 배정은 역할 공용 그대로) | agents.js:322 | agent_authoring.py:424-435, inbox.py:52-63 |
| 1 B2 | POST /api/mcp/servers {name, transport, url=잘못된 주소, timeout, by} | 422 "연결 검사 실패로 등록하지 않았습니다 — …", 목록에 없음 | mcp.js:371-373 | mcp_registry.py:415-434 |
| 1 B2 | POST /api/mcp/servers {name: my-dmn, url: http://dmn-mcp:8198/mcp …} → POST …/{name}/check {timeout, by} → GET /api/mcp/selectable | 201 · 검사 ok · 도구 목록, 읽기 표시 도구만 선택 가능 · 쓰기(submit_decision)는 사유와 함께 불가 | mcp.js:306 · :371 | mcp_registry.py:341-375 · :470-488, dmn_mcp/server.py:28-29 · :107 |
| 1 B1 | GET /api/agents/sys:agent (다시) | 기본 에이전트 instructions · settings 불변 | — | agents_api.py:107-113 |
| 1 B3 | GET /api/flows/catalog → POST /api/flows/import {xml, file_name, definition_id: my_cooler} | 가져온 직후 사전 검사 실패(부품 미선택, 칸 위치 · 사유) | flows.js:84 · :99 | flows_api.py:88-109, bpmn_import.py:331-362 |
| 1 B3 | PUT /api/flows/my_cooler/mapping {mapping} (그림 task 이름 = 부품 이름으로 고름 + 조건 선 4개) → POST …/register {mapping} | 사전 검사 ok → 판본 1 등록(deployed=false), 명령 앞 승인(그림 id) | flows.js:265 · :277 | flows_api.py:140-189, tests/test_bpmn_import.py:53-62(같은 매핑) |
| 1 B3 | GET /api/flows/my_cooler/versions/1/bpmn | 가져온 원본 그대로 | flows.js:296 | flows_api.py:191-202 |
| 1 B1 | GET /api/agent-assignments → PUT /api/agent-assignments {definition_id, activity_id: 그림의 원인 진단 id, agent_id} | 배정 표에 my_cooler 원인 진단(기본 sys:agent), 배정 뒤 assigned, 모드 안내 | agents.js:73 · :311 | agent_authoring.py:329-385 · :368-370 |
| 1 B1 | GET /api/agents/{내 에이전트} | run.steps 에 (my_cooler, 원인 진단) — settings.id = 내 에이전트, skills ⊇ 붙인 스킬 | agents.js:340 | agents_api.py:107-113, agents_store.py:150, agent-worker runner.py:114(워커가 같은 함수) |
| 1 B4 | POST /api/process/definitions/my_cooler/deploy {version, by, reason} → GET /api/flows/deployments · /api/flows/deploy-compare?definition&version | COOLER · PUMP · FAN 경보 → my_cooler@1("내가 배포한 흐름"), 기준 대비 추가 0 · 삭제 0 | definitionDeploy.js:132 · :12 · :92 | instance_mode.py:700-708, flow_deploy.py:57-63 · :66-90 · :117-134 |
| 1 쿨러 | plant /api/reset · enterprise /api/reset · /api/fault {HYD-01, cooler_degradation, moderate} → detector state → GET /api/instances?limit=40 | 경보 → 처리 건 proc_def_id=my_cooler · 판본 1 · 사건 AWAITING_APPROVAL | (강사 조작) | scenario_instance_test.py:236-250 |
| 1 쿨러 | GET /api/instances/{pid} 폴링 | 에이전트 4작업 DONE → 조치 카드 선택 IN_PROGRESS, 원인 진단 user_id = 내 에이전트 + assignees resolution=agent-map, 모드별 실행 주체(아래) | instances.js | agent_authoring.py:394-420, inbox.py:78-82 |
| 1 쿨러 | GET /api/decisions/{id} | 1순위 = policy_top 재계산 · fan-max-derate 가능 | instances.js | scenario_instance_test.py:35-55 |
| 1 쿨러 | POST /api/todolist/{sel}/select (운전원) → POST …/decision-preview {decision, option, parameters} → POST …/select {decision, option, review_id, by, role, reason} | 운전원 403, 생산관리자 승인 accepted · DELIVERED, 그 뒤에만 cmdId | instances.js:247 · :257 | instance_mode.py:924-950 |
| 1 쿨러 | GET /api/incidents/{id} · /api/instances/{pid} · /api/audit | ACK → 재관측 → 작업지시 WO- → COMPLETED(그림의 종결 끝 Event_0clsd8k), 상급자 호출 CANCELLED | instances.js | main.py:605 · :665 |
| 2 펌프 | /api/fault {HYD-02, pump_leakage} → 처리 건 → (보류면) POST /api/todolist/{원인 진단}/reassess {deferral_id, request_id, by, reason} | 보류: UNSUPPORTED/UNKNOWN · 사유 · cmdId 없음 · decision_id 없음 → 재평가 접수 → 카드: 예비 펌프 전환 추천 · 압력 상향 제외 → 승인 → 펌프 B · PS1≥165 → 재관측 PS1 기준 → 종결. 보류가 안 나면 `(기록)` 한 줄 + `2-pump-hold-branch.json` | taskDeferral.js:24 · instances.js:247/257 | instance_mode.py:1002-1011, scenario_pump_fan_test.py:105-165 · :200-229, run_scenario_pump_fan_evidence.py:215-256 |
| 3 What-if | AGENT POST /api/agent/whatif {asset, pattern} → …/{id}/try {values:{}, policy:{weights:{}, penalties:{}, perspectives:{쓰는 관점: 3}}} → 안 쓰는 관점 ×5 → …/try {} | 관점 ×3 → 카드 점수 변화, 원본 지문 같음(unchanged), 안 쓰는 관점은 점수 그대로, 원래대로 = 기준 1순위 | whatif.js:31 · :44 · :249 · :49 | agentsvc/main.py:360-371 · :395-414, tests/test_b5_whatif_perspectives.py:33-52 |
| 3 KPI | GET /api/kpi?period=24h → POST /api/kpi/try {period, targets:{지표: 시험 목표}} → GET /api/kpi | 판정이 뒤집힘(trial.changed before/after), 다시 읽은 목표 그대로 | kpi.js:175-176 | kpi.py:877-894 · :582-630 |
| 3 질문 | GET /api/ask/status · /api/ask → POST /api/ask {question, agent: 내 에이전트, by, request_id} → GET /api/ask/{id} 폴링 | worker: 201 · 끝나면 도구 호출 ≥1 · 근거 있는 답(verified≥1) 또는 답할 수 없음+이유 / legacy: 503 + "AGENT_BRIDGE=legacy" 사유 · 기록 늘지 않음 | ask.js:17 · :37 · :57 | ask.py:109-127 · :146-160 · :333-360 |
| 3 팬 | /api/fault {HYD-03, fan_vibration} → … → 팬 감속+부하 저감 승인 | 원인 팬 베어링 마모 · 팬 SOP 카드 · ACK · VS1<1.2 · 재관측 VS1 기준 · 종결 | instances.js | scenario_pump_fan_test.py:232-251 |
| 3 가림 | /api/fault {HYD-01, pump_leakage} → 운전원 부하 70 % → POST /api/todolist/{상급자 호출}/submit {output:{note}, by} | 경보 해제 · PS1<165 · ESCALATED MITIGATION_FAILED · 상급자 호출 → 생산관리자(또는 구성원) · 끝 Event_1escd0t · 작업지시 CANCELLED | instances.js:271 | instance_mode.py:884-898, scenario_pump_fan_test.py:254-286 |
| 4 작동유 | probe_b7_oil_live.run(ns{out, expect, def_id=my_oil_v}) — 그 파일 그대로 import | b7-oil.md 순서 1~8(사람 입력 → 정비형 흐름 → 두 바퀴 → 종결 · 명령 0) | oilInput.js:16 · :33, flows.js | probe_b7_oil_live.py:159-349 |
| 5 B6 | GET /api/config/export → POST /api/config/reset {by} → GET export(비었나) · /api/flows/deployments(at_reference) → POST /api/config/import {bundle, secrets:{}, skip_missing_secrets:false, by} → GET export | 7칸(mcp_servers · skills · agents · role_members · flows · assignments · deployments) 비교 같음(출처 · 이름 · 패턴 칸 제외 = config_bundle._comparable), 경보 표 다시 학생 흐름 | configBundle.js:50 · :94 · :120 | config_bundle.py:170-239 · :691-701 · :781-819 |
| 5 끝 | POST /api/config/reset {by} | 200(학생 구성 정리) — 열린 처리 건이면 409 사유가 FAIL 좌표로 | configBundle.js:120 | config_bundle.py:303-314 |

## 모드별 차이 (코드 근거)

| 항목 | worker (AGENT_BRIDGE=off + 워커) | legacy (AGENT_BRIDGE=legacy, 워커 정지) | 근거 |
|---|---|---|---|
| 단계 배정의 반영 | 작업 행 user_id = 내 에이전트 → 워커가 그 user_id 로 프로필을 읽고(agent_settings: 모델 · 도구 · 스킬) 실행 | 작업 행 user_id = 내 에이전트(같은 apply_agent_map)지만 내장 결정론 판단이 task 를 채움 | agent_authoring.py:394-420(모드 무관), agent-worker context.py:70-81 · runner.py:114, instance_mode.py:443-472 · :475-481(`_legacy_key` 로 그림 id 도 채움) |
| 검사 | `check_performer`: user_id · assignees(agent-map) + 원인 진단 task_started 가 "legacy agent" 아님 + tool_usage 이벤트 ≥1 | user_id · assignees(agent-map) + task_started 이름 "legacy agent" | worker events.py:75-78, instance_mode.py:463 |
| 배정 표 안내 | bridge_note 없음 | bridge_note("판단은 내장 경로") | agent_authoring.py:367-370 |
| 실행 설정 화면 | run.steps 에 배정 · 스킬 — 워커가 실제로 쓰는 값 | 같은 값이 보이지만 실행에는 쓰이지 않음(안내로 구분) | agents_api.py:107-113 |
| 에이전트 대기 | 900 s(4작업 연속, A158 기준), 작동유 1500 s | 150 s, 작동유 300 s | scenario_instance_test.py:261, probe_b7_oil_live.py:146 |
| 보류(펌프) | 실제 워커가 근거 부족이면 UNSUPPORTED(A158) | 내장 판단의 WITHHELD → 보류 task(PENDING + _deferral) | run_scenario_pump_fan_evidence.py:226-256 |
| 질문하기 | 201 · 처리 건 하나 · 답/답할 수 없음 | 503(워커 없음) + 사유, 처리 건 0 | ask.py:109-127 · :146-152 |

## 코드에서 확인 못 한 것 · 실행 전 주의

1. **작동유 재사용 검사의 거짓 실패 가능성(worker)**: `probe_b7_oil_live.py` 끝의 "원인 진단을 실제 워커(cliagents)가 수행"은
   DONE 작업 행의 `consumer` 에 "worker" 가 있기를 기대하지만, 결과 저장이 점유를 비운다 — `procdb.py:419`(메모리) ·
   `procdb.py:862-869`(PG, `consumer=case when final then null`) · migration `20261004000004_process_lock_order.sql:62`
   (`consumer=null`). 그대로면 worker 모드에서 그 한 줄이 FAIL 로 나올 것으로 보인다(그 파일은 고치지 않았다 — 메인 판단).
   대안: `task_started` 이벤트 이름(legacy agent 아님) + 도구 호출 이벤트로 본다(이 검사기 `check_performer` 방식).
2. B2 정상 등록 주소 `http://dmn-mcp:8198/mcp` 는 compose 프로필 `cliagents` 서비스다(compose.yaml:442-444). legacy 실행에서도
   떠 있어야 B2 · B6 불러오기(MCP 연결 재검사)가 통과한다. 다른 주소는 `--mcp-url`.
3. What-if 기본은 HYD-01 · COOLER_DEGRADATION(A159 라이브에서 내부 프로세스 관점 사용 확인). 팬 패턴에서 쓰는 관점이 있는지는
   코드 · 시험으로 확인하지 못했다(도구로 `--whatif-asset HYD-03 --whatif-pattern FAN_VIBRATION` 가능).
4. 펌프 "예비 펌프 전환 추천" 기대는 CMMS `standby_ready` 가 true 인 DB(새 seed)를 전제한다 — 옛 DB 는 NULL 일 수 있다
   (run_scenario_pump_fan_evidence.py:19-21). 이 검사기는 DB 를 고치지 않는다.
5. 실제 워커가 내 에이전트의 스킬을 작업 폴더에 넣었는지는 HTTP 로 보이지 않는다(워커 로그 `skills in the workspace`,
   runner.py:127-128). 검사기는 실행 설정(run.steps.settings.skills)과 작업 행 담당까지만 본다 — 필요하면 워커 로그 grep.
6. 질문하기의 legacy 503 은 bridge 가 아니라 **워커 연결**로 정해진다(ask.py:109-127). legacy 실행 전제(워커 정지)가 깨지면 이
   검사가 실패한다.
7. 역할 → 사람 배정(role:operator ← user:lee-prod)은 구성원이 이미 둘이라 할당 결과가 바뀌지 않게 골랐다(inbox 규칙:
   한 명이면 그 사람, 여럿이면 역할 공용 — inbox.py:52-63, migration 20261008000029:4).
8. 시작 · 끝의 "기준으로 되돌리기"는 앞 세션이 남긴 학생 구성(my_oil 등)도 지운다(DECISIONS §103 — 묻지 않고 정리). 학생 흐름의
   RUNNING 처리 건이 있으면 409 로 멈춘다 → 먼저 닫거나 `--no-reset-start`.
9. 쿨러 시작에 enterprise-sim `/api/reset` 을 부른다(scenario_instance_test.py:238 과 같음).
10. 작동유 단계(b7.run)는 `docker exec`(cypher-shell · psql) · `docker logs` 를 쓴다 — 이 검사기 나머지는 HTTP 만.

## 오프라인 자기 시험 (라이브 스택 접속 없음)

- 문법: `.venv/bin/python -m py_compile scripts/probe_v_student_paths.py` 통과.
- B1~B4 준비 + B6 단계: 메모리 저장소 + FastAPI TestClient(main.py 와 같은 마운트 순서: instance_mode · agents_api ·
  agent_authoring_api · mcp_api · mcp_registry · flows_api · config_bundle)에 이 검사기의 HTTP 호출을 그대로 돌림, MCP 는
  B2 시험의 가짜 HTTP 서버(임의 포트) → **44/44**. 매핑 함수 결과 = tests/test_bpmn_import.py redraw_mapping(tasks · flows 동일),
  그림 id(원인 진단 Activity_0diag4n · 타이머 Event_0tmot5y · 종결 Event_0clsd8k · 에스컬레이션 Event_1escd0t).
- 보류 → 명시 재평가 → 선택 열림(가짜 view), 담당 검사 일부러 깨뜨리기(기본 에이전트 담당 · legacy 이름 없음 → FAIL),
  요약 줄이 run_regression PASS_PATTERNS 와 맞음 · 실패 줄은 맞지 않음, `--only` 검증.
- 자기 시험 파일은 scratchpad(`vprobe/selftest_v.py` · `selftest_flow.py`) — 저장소에 넣지 않음.
