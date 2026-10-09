# C3 조립 — C1 · C2 · U1 합치기, 열린 일 닫기, 실제 워커 완주 (확정 TODO C3)

작성 2026-10-09. 브랜치 `c3-assembly`(기준 `claude/hyd-handoff-work-xziutz` 904aba7). push · 기준 브랜치 합치기는 하지 않았다(사용자 결정).
증거: `.evidence/a161-c3/`(마이그레이션 · 시드 · compose · Supabase 기동 로그).

**상태 요약**: 합치기 · 열린 일 코드 · 단위 시험 · 공용 스택 배포는 끝났다. **실제 워커로 A · B · C 완주(3번)는 하지 못했다** — 아래 5절의 워커 문제로 멈췄다.
그래서 실라버스에 넣을 실측 시간은 아직 없다.

**비유 한 줄**: 세 팀이 따로 만든 부품(지식 · 실행 · 화면)을 한 차체에 조립하고 시동 직전까지 왔다. 시동을 걸려면 다른 운전자가 켜 둔 엔진 두 대를 먼저 꺼야 한다.

**스스로 판정할 체크 질문**
- 세 브랜치의 의도가 모두 남았는가? 겹친 파일 9개가 자동 병합됐고, 합칠 때마다 전체 단위 시험이 통과했다(2절).
- B에서 담당자가 "미루기" 카드를 고르면 작업지시가 그다음 정비 시간으로 가는가? 단위 시험 `test_b_work_order_follows_the_chosen_cards_window_…`이 확인한다. 실제 스택 확인은 아직이다.
- A 결과 보고에 유온 값이 숫자로 보이는가? 단위 시험은 통과했다. 화면 확인은 실제 실행 뒤에 한다.

---

## 1. 합친 것

| 순서 | 브랜치 | 내용 | 충돌 | 합친 뒤 단위 시험 |
|---|---|---|---|---|
| 1 | `worktree-agent-a43cb88bab1647e3b` (C1 지식) | 시드 두 판, 문서 적재 확장, PREVENTED_BY(a9b7245), B 정기 정비(ed60c20) | 없음 | 1754 통과 · 4 건너뜀 |
| 2 | `worktree-agent-afbc3de09be36a2d6` (C2 실행) | 확정 흐름 부품, 판단 사실, 감시, 수업 버튼, 업무 MCP 분리, 마이그레이션 45 | 없음 | 1811 통과 · 4 건너뜀 |
| 3 | `u1-uiux-a161` (U1 화면) | SSE 이어 받기, 승인 카드, 결과 보고 카드, 수업 시나리오 버튼 | 없음 | 1814 통과 · 4 건너뜀 · 1 실패* |

\* `tests/test_mcp_check.py::test_html_page_is_not_an_mcp_endpoint`. C1 · C2 · U1 보고서에 모두 같은 흔들림이 적혀 있다(이 macOS의 로컬 HTTP 문제). 합치기와는 관계없다.

**두 브랜치가 함께 고친 파일**은 모두 git이 자동으로 합쳤다. 합친 뒤 시험으로 확인했다.

| 함께 고친 브랜치 | 파일 |
|---|---|
| C1 · C2 | `.env.example`, `compose.yaml`(SEED_EDITION과 새 MCP 서비스가 둘 다 남음), `procsvc/main.py` |
| C1 · U1 | `portal/www/enterprise.js`, `taskDetail.js`, `procsvc/manual_api.py` |
| C2 · U1 | `procsvc/instance_mode.py`, `instances.py`, `procdb.py` |

시험 환경: 이 워크트리에 `.venv`(python 3.12)를 새로 만들었다. 다른 워크트리 `.venv`와 맞추려고 아래를 더 설치했다.
- `it/agent-worker/requirements.txt`(cliagents)
- `fastmcp==2.13.0.2`, `sqlglot`
- `starlette==0.41.3`으로 되돌림. fastmcp 설치가 1.x로 올렸는데, 그러면 fastapi 0.115와 맞지 않는다.

## 2. 닫은 열린 일 (커밋 3개)

| 열린 일 (출처) | 한 것 | 파일 |
|---|---|---|
| 시나리오 에이전트 셋 (C2 §10.7, C1 §6.8) | 아래 1 | `it/supabase/seed.sql` |
| 흐름별 묶기 | 아래 2 | `scripts/c3_flows.py` |
| B 작업지시 시간이 고른 카드를 따름 (C2 §10.2) | 아래 3 | `agentsvc/cards.py`, `decide.py`, `procsvc/instances.py`, `service_parts.py`, `entsim/data.py`, 마이그레이션 46 |
| 판단 문장 한국어 (U1 §7.1) | 아래 4 | `worker/prompt.py`, `worker/workspace.py` |
| A 측정값 · 미달 표시 (U1 §7.3, C2 §10.3) | 아래 5 | `effect_parts.py`, `service_parts.py`, 포털 `resultReport.js`, `ui.js`, `instances.js` |
| 스킬 편집 PREVENTED_BY · HM-8 사본 (C1 §6.9) | 아래 6 | `hitl.js`, `ui.js`, `samples/` |
| 역할 이름 (U1 결함 13) | 아래 7 | `seed.sql`, `tests/test_inbox.py`, `tests/test_b1_agent_authoring.py` |
| B 버튼 (U1 §7.4) | 아래 8 | `scenarioTriggers.js`, `index.html` |

1. **시나리오 에이전트 셋**: 에이전트마다 목표 · SKILL · MCP 서버가 다르다.
   - `agent:cooling`: SKILL `cooling-emergency-response`, 서버 `neo4j,enterprise,hyd-dmn`(지금과 같음)
   - `agent:pm-plan`: SKILL `pm-schedule-planning`, 서버 `neo4j,hyd-dmn,enterprise-maint`
   - `agent:spare-buy`: SKILL `spare-purchase-planning`, 서버 `neo4j,hyd-dmn,enterprise-purchase`
   - SKILL 본문은 `tenant_skills`에, 묶음은 `agent_skills`에 넣었다.
   - 옛 `sys:agent`는 기준 흐름(설비 이상 조치)용으로 그대로 둔다.
2. **흐름별 묶기**: A · B · C 흐름은 모양과 부품이 C2 시험과 같다. 다른 점은 판단 · 제안 task의 `agent`와 승인 task의 `role` 두 가지다.

   | 흐름 | 에이전트 | 승인 역할 |
   |---|---|---|
   | A | `agent:cooling` | 운전원 |
   | B | `agent:pm-plan` | 설비보전팀장 |
   | C | `agent:spare-buy` | 구매 담당 |

   - `scripts/c3_flows.py check|deploy|export`가 포털 '흐름 가져오기'와 같은 API를 쓴다.
   - 실제 스택에서 사전 검사를 돌렸고 세 흐름 모두 ok다.
3. **B 작업지시 시간이 고른 카드를 따른다**: 판단 엔진이 정비 카드마다 시점(`window`)을 싣는다.
   - 판단 사실에 `windows_by_variable`을 더했다(CMMS pm_status의 이번 · 그다음 창).
   - 카드의 시점은 그 카드에만 걸린 규정이 시험하는 변수로 정한다(`option_window`).
     - 이번 정비 시간 단독 · 두 대 묶기 → 이번 창
     - 미루기 → 그다음 창(월간)
     - 창 변수가 없는 정비 카드(지금 정지) → 즉시
   - 시나리오 이름이나 SOP 번호를 코드에 쓰지 않는다.
   - 작업지시 부품은 카드의 시점을 먼저 쓴다. `window_var`는 카드에 시점이 없을 때의 기본값으로만 남는다.
   - 정비 수행 부품은 '즉시' 카드면 예정된 정비 시간까지 기다리지 않는다.
   - 마이그레이션 46은 `ent.pm_status` 뷰 끝에 `following_window_id`와 `following_window_at` 두 칸만 더한다(두 번 적용해도 안전). 메모리 백엔드도 같은 칸을 낸다.
4. **판단 문장 한국어**: 작업 규칙(CONSTITUTION)에 '언어' 절을 넣었다. 프롬프트 맨 끝에도 같은 규칙을 다시 붙였다. 도구 호출 사이의 진행 설명("Next I'll …")까지 한국어로 쓰라고 이름을 들어 적었다.
5. **결과 보고 측정값과 미달 표시**
   - 결과 보고는 `values`(측정값 목록: 이름 · 값 · 단위 · 기준 · 통과)와 `verdict`(ok/fail/info)를 낸다. 전의 values 사전은 `facts`로 이름만 바꿨다.
   - A는 결과 보고 시점에 사건의 회복 기준 태그(유온 TS1)와 경보 해제 여부를 읽는다. 재관측 task의 출력 계약(`recovered` 하나)은 배포된 정의가 정하므로 바꾸지 않았다.
   - B는 시운전 PS1 · FS1 · VS1 값을, C는 입고 수량을 싣는다.
   - 포털: 배지 문구는 `outcome`에서 온다. 사건 ESCALATED는 "미달"(빨강)로 보인다. 처리 건 목록과 상세 머리글에 결과 칩이 붙는다.
6. **스킬 편집 PREVENTED_BY · HM-8 사본**
   - 스킬 편집 화면과 매뉴얼 미리보기의 관계 고르기에 "예방 조치"(PREVENTED_BY)를 넣었다.
   - 미리보기는 추출 제안의 관계 · 종류 · 고장 유형으로 미리 채운다.
   - 적재할 때 제안 내용(조치 값 · 대상 원인 · 승인자)이 빠지던 결함을 고쳤다.
   - 포털 샘플 HM-8을 새 판으로 바꾸고 PM-02 · PR-07 사본을 더했다(A → B → C 순서 안내 포함).
7. **역할 이름**: 시드의 `role:maint-mgr` 이름을 '정비관리자'에서 '설비보전팀장'으로 바꿨다(B 승인자, 온톨로지 · PM-02와 같은 이름). `role:purchasing` 구매 담당과 `role:purchasing-mgr` 구매팀장 역할, 사람 정구매 · 한구매를 더했다.
8. **B 버튼**: "운전시간 +300 h"를 `POST /api/simulate/pm-advance {hours:300}`에 연결했다. 접힌 "수업 도구"에 보조 버튼 셋을 넣었다(C 납기 +3일 지연, B · C 되돌리기). B 미달 가지를 만드는 법도 한 줄로 안내한다.

**시험**: `tests/test_c3_assembly.py` 12개(카드 시점 · 즉시 · 측정값 · A 미달 측정값 · B 시운전 값 · 흐름 세 개 가져오기 · 시드 · 한국어 규칙).
전체 결과는 **1826 통과 · 4 건너뜀 · 1 실패**다. 실패는 위의 같은 흔들림이다.

## 3. 공용 스택에 적용한 것 (검사기를 돌리기 전에 끝냄)

1. **마이그레이션 45 · 46과 `seed.sql`을 Supabase에 적용했다**(모두 exit 0). 확인한 것:
   - 에이전트 3개와 스킬 묶음 3개가 들어갔다.
   - tenants.mcp에 서버 5개가 있다(neo4j · hyd-dmn · enterprise · enterprise-maint · enterprise-purchase).
   - `ent.pm_status`에 그다음 창 칸이 생겼다.
2. **Inbucket을 켰다**: Supabase를 데이터를 지우지 않는 `stop` 뒤 `start`로 다시 띄웠다. `supabase_inbucket_hyd-iot-edu`(mailpit)가 healthy다.
   - **사고 하나**: 이 PC의 supabase CLI(v2.75)가 처음에 더 옛 Postgres 이미지(15.8.1.085)로 떴다. 볼륨은 15.19.0.002가 만든 것이라 collation 경고가 났다.
   - 1~2분 안에 다시 내리고, `it/supabase/.temp/*-version`(git에 들어가지 않음)으로 원래 이미지(postgres 15.19.0.002 · gotrue v2.197.0 · postgrest v16.4 · realtime v2.140.3 · pg-meta v0.99.0 · studio 2026.09.28)를 고정해 다시 띄웠다. 경고는 없어졌다.
   - 옛 이미지로 떠 있던 동안 쓰기가 있었다면 text 인덱스 정렬이 어긋났을 수 있다(가능성 낮음). 걱정되면 `REINDEX DATABASE postgres`를 하면 된다.
3. **이미지 빌드 · 기동**: process · dmn-mcp · enterprise-mcp · enterprise-mcp-maint · enterprise-mcp-purchase · effects-mcp · enterprise-sim · plant-sim · agent를 빌드하고 portal과 함께 올렸다.
   - 스택은 이제 이 워크트리에서 돈다(portal도 이 워크트리 `it/portal/www`를 연결한다).
   - process StartedAt `2026-10-09T07:52:47Z`, RestartCount 0.
   - kg-seed가 구조판으로 한 번 돌았다. MERGE만 하므로 지금 그래프(전체판 지식)는 그대로다.
4. 흐름 세 개는 **사전 검사만** 했다(초안 c3_cooling · c3_pm · c3_spare 저장). 등록 · 배포는 하지 않았다. 배포하면 쿨러 경보가 기준 흐름 대신 A 흐름으로 가서 회귀 검사기를 가린다. 그래서 완주 직전에 배포하고 완주 뒤 `deploy-reset`으로 되돌릴 계획이다.

## 4. 실제 워커 완주 — 하지 못함

계획(구조판 → 실제 LLM 추출로 A → B → C 적재 → A · B · C 각 1회 완주 + 미달 · 지연 가지 각 1회 → 실시간 화면 캡처 → 회귀 검사기)은 시작하지 못했다. 위 3절까지만 했다.

- **구조판 계획**: 지금 neo4j 볼륨은 전체판 지식이 든 상태다(FailureMode 7 · Cause 8). 프로젝트 데이터 볼륨은 지우지 않는다. 대신 compose 덮어쓰기 파일로 neo4j만 새 볼륨(예: `neo4j-data-c3`)에 붙여 구조판으로 띄우고, 완주 뒤 원래 볼륨으로 되돌려 회귀 검사기를 전체판에서 돌린다.
- 실측 시간(실라버스용): **없음**. 완주를 해야 나온다.

## 5. 막힌 이유 — 다른 에이전트의 호스트 워커 둘

| PID | 명령 | 작업 디렉터리 | 비고 |
|---|---|---|---|
| 41145 | `python -m worker.main` | U1 워크트리 `.claude/worktrees/agent-aed004354f1cd7a4c` | 약 1시간 전 시작, 포트 없음 — 코디네이터가 말한 남은 워커 |
| 69612 | `python -m worker.main` | 같은 U1 워크트리 | 약 2시간 전 시작, 8097 포트 |

- 두 워커 모두 U1 브랜치 코드로 돈다. C2의 워커 변경(보전용 · 구매용 MCP 주소 바꾸기 · 허용 도구 목록)과 이번 한국어 규칙이 없다.
- 같은 테넌트의 에이전트 작업을 가져가므로, 내 워커를 따로 띄워도 작업이 셋 중 아무 워커에게나 간다. 그러면 "학생 1명 · 처리 건 1건 · 1회" 완주가 성립하지 않는다.
- 두 워커는 내가 띄운 것이 아니다. 지시에 따라 멈추지 않았다. 일시 정지(SIGSTOP)를 시도했지만 권한 확인에서 거절됐다.

**필요한 결정**: 두 워커를 멈춰도 되는지 사용자 확인. 확인되면 이어서 할 일은 아래와 같다.
1. 두 워커를 멈추고 포트 8097/8098이 내려갔는지 본다.
2. 이 워크트리에서 `bash scripts/run_worker_host.sh`로 워커 하나를 띄운다.
3. neo4j를 새 볼륨의 구조판으로 띄운다.
4. 포털 지식 관리에서 HM-8 → PM-02 → PR-07을 실제 추출 · 검토 · 적재한다.
5. `scripts/c3_flows.py deploy`로 흐름을 배포한다.
6. 포털 버튼으로 A · B · C를 완주하고, 미달 · 지연 가지를 한 번씩 돌린다. 캡처는 `.evidence/a161-c3/`에 남긴다.
7. 흐름 `deploy-reset`, neo4j를 원래 볼륨으로 되돌리고, 설비 · 재고 · 계수기를 되돌린다.
8. 단위 시험과 회귀 검사기(`scenario_instance_test.py --worker` · `scenario_pump_fan_test.py`)를 돌린다.
9. 내가 띄운 워커를 멈춘다.

## 6. 남은 것

1. 4 · 5절의 실제 완주, 캡처, 실측 시간, 회귀 검사기.
2. 실제 LLM이 정기 정비 · 구매 카드에 대해 B · C 판단을 `business_causes` → `evaluate_cards` → `submit_decision` 순서로 해내는지는 완주에서 확인해야 한다(C1 §6.2 · 6.3).
3. 반려 버튼은 없다. 서버에 반려 API가 없다(U1 §7.2). 확정 흐름(승인 1회)에서는 그리지 않았다.
4. `scripts/ui_regression.py`는 구조판에서 줄 파서 미리보기로 HM-8을 적재하면 고장 유형(`fm:cooling-loss`)이 없어 막힐 수 있다. 전체판에서 돌린다.
5. 시험 잔재: Supabase에 흐름 초안 3개(c3_*)가 남아 있다. 완주 때 쓴다. 쓰지 않을 거면 `/api/flows/reset`으로 지운다.

---

## 7. B · C 단순화와 실제 워커 완주 (2026-10-09 밤)

**지시**(코디네이터 전달, 감독 발화): 포털 "결함 실험" 버튼 [쿨러 열화 주입][쿨러 복구] | [정기 점검][초기화] | [재고 보충][초기화].
처음 화면에 HYD-02 "정기 점검 도래" · HYD-03 "재고 보충 필요"가 기본으로 뜬다. B · C는 **설비까지 가지 않는다**(처리되면 끝).
5절의 워커 문제는 해소됐다(남의 워커 없음, 이 워크트리 워커 1개, PID 51665).

**비유 한 줄**: 정비 · 구매 담당 책상 위에 "할 일" 쪽지가 미리 붙어 있고, 버튼을 누르면 AI가 안을 가져오고, 담당자가 도장을 찍으면 총무팀이 오더 · 발주를 내고 쪽지를 뗀다.

**스스로 판정할 체크 질문**
- 화면을 처음 열면 HYD-02 · HYD-03 위에 표시가 있는가? 있다(`B-1-start-1440.png`).
- B · C 흐름에 예정된 정비 시간 대기 · 정비 수행 · 시운전 · 납기 타이머가 남아 있는가? 없다(`test_b_and_c_are_small_three_lane_flows…`).
- 처리 건이 끝나면 표시가 꺼지고 [초기화]로 다시 켜지는가? 그렇다(`B-5-after`, `R-after-reset`).
- 누가 언제 눌렀는지가 처리 건 자체에 남는가? 남는다(처리 기록 `SCENARIO_BUTTON`, 시작 경보 근거 `requested_by · requested_at`).

### 7.1 바뀐 것

| 무엇 | 내용 | 파일 |
|---|---|---|
| 시작 상태 = 기본값 | 마이그레이션 47: HYD-02 1,950 h · HYD-03 1,880 h · HYD-01 1,500 h, 씰 키트 실물 3 − 예약 2 = 가용 1 < 재주문점 2. 판단 사실은 C2와 같다(1,950 / 1,959 / 2,230 h, 필요량 6). 메모리 백엔드 같은 값 | `it/supabase/migrations/20261009000047_c3_bc_simplified.sql`, `entsim/data.py · state.py` |
| B 표시가 꺼지는 때 | `ent.pm_status.pm_alert` = 도래 · 이번 회차 정비 오더 없음. 도래 설비에 **예정된 정비 시간(window_id)으로 잡힌** 작업지시가 오더로 남는다(트리거). 고장 대응 즉시 작업지시(펌프 회귀의 예비 펌프 전환)는 오더가 아니다 — 처음 판은 이것까지 셌다가 회귀 뒤 표시가 꺼져 고침 | 같은 마이그레이션 |
| 버튼 API | `GET /api/scenario/status`, `POST /api/scenario/{B,C}/start`(업무 감시와 같은 경보 계약 · 같은 접수 경로, 표시 없음 · 진행 중 · 흐름 미배포는 409), `POST /api/scenario/{B,C}/reset`, `POST /api/scenario/A/{degrade,restore}` | `procsvc/scenario_buttons.py`, `main.py` |
| 옛 원인 버튼 | +300 h · 출고 −2 · 납기 지연을 포털 · process 에서 없앰. enterprise-sim API(`/cmms/pm/advance` 등)는 시험 · 강사용으로 남김. 업무 감시 기본 끔(`BUSINESS_MONITOR=0`) — 켜 두면 시작 상태가 곧 도래라 바로 처리 건이 열린다 | `compose.yaml`, `.env.example` |
| 흐름 | B: 제안 → 설비보전팀장 승인 → 정비 오더 등록 · 공지 메일 → 결과 보고(task 4). C: 제안 → 구매 담당 승인 → ERP 발주 · 공급사 메일 → 입고 · 재고 반영(`immediate`) → 결과 보고(task 5). 레인 3, 분기 · 타이머 없음 | `scripts/c3_flows.py`, `service_parts.py`, `effect_parts.py` |
| 결과 보고 값 | B: 정비 오더 · 정비 시점 · 공지 메일. C: 입고 수량 · 현재고 · 가용 재고(기준 ≥ 재주문점) · 공급사 메일 | `effect_parts.report_values` |
| 포털 | 설비 카드마다 시나리오 하나, 카드 머리 표시(도래 · 필요 · 처리 중 → · 처리됨), 위쪽 원인 버튼 패널 삭제, 결과 카드 줄바꿈 · 승인자 이름 · '구매 담당' 역할 이름 | `app.js`, `resultReport.js`, `ui.js`, `names.json`, `theme.css` |
| 누른 사람 · 때 | 포털이 고른 '나'(이름 · id · 역할)를 보냄 → 시작 경보 근거 + 처리 기록 `SCENARIO_BUTTON`, 모든 누름은 감사 기록 `SCENARIO_BUTTON`. 설비 카드 버튼 아래 "마지막: [버튼] 누가 · 때"(처리 건이 없는 [초기화]도 보인다, `/api/scenario/status presses`) | `scenario_buttons.py`, `main.py`, `app.js` |
| A 누름 → 처리 건 연결 | 누름 id(`PRESS-…`)를 plant-sim 주입 요청 `origin`에 싣는다 → 설비 상태(plant.status `injection`)에 남는다 → 그 주입이 낸 경보로 처리 건이 열릴 때 `case_started` 훅이 같은 id 로 기록을 붙인다. [쿨러 복구]는 지금 주입 id 로 연결된 처리 건에 기록한다. 시간 창 추정 없음(라이브 3차: `injection_id` 가 처리 건 기록에 남음 확인) | `ot/plant-sim/plantsim/plant.py · main.py`, `instances.py Hooks.case_started`, `main.py _link_injection` |
| A 열화 세기 | 포털 버튼은 moderate(쿨러 0.55, 평형 62.5 ℃ — 경보만, 보호 정지 없음) = 시나리오 A "서기 전에 식힌다"의 설정(A146 열모델 · 회귀 기본과 같음). high(0.43)는 평형 70 ℃라 주입 뒤 시뮬레이션 약 30분에 보호 정지한다. 20배속은 설비 물리만 빠르게 하고 에이전트 판단(실측 46~79초 = 시뮬레이션 15~26분)은 줄이지 못하므로 high 는 "판단이 늦어 서 버린" 장면이다(라이브 2회 `live/failed-high-severity/`). 이름 있는 상수 `scenario_buttons.A_SEVERITY` | `scenario_buttons.py` |
| 시나리오 시각 기준점 | `ent.reanchor_scenario_times()`(생산 오더 납기 · 예정된 정비 시간 · 출하)를 버튼 시작(A · B · C) · [초기화] · enterprise-sim 시작 때 다시 맞춘다(`POST /api/reanchor`). 전에는 업무 실행 초기화 때만 돌아 C 판단에 "OEM 오더 납기까지 −1.27 h"가 나왔다 | `entsim/main.py · supabase_backend.py`, `procsvc/main.py` |
| 업무 초기화가 기록을 지움 | `ent.reset_executions()`가 작업지시 · 발주 · 입고 · 원장을 지우기 전에 `ent.execution_archive`(초기화 회차 · 표 · ref · 판단 id · 행)로 옮긴다. 운영 상태(진행 중 오더 · 재고 · 계수기 · 시각)는 전과 같이 시작값이라 검사기의 출발점은 같다. `GET /api/archive?ref=` 로 따라간다. 메모리 백엔드 같은 규칙 | 마이그레이션 47, `entsim/state.py` |
| neo4j 재시작 뒤 끊긴 연결 | 볼륨 교체로 neo4j 가 다시 뜬 뒤 agent 서비스 풀의 끊긴 연결이 승인 조건 검사를 ServiceUnavailable 로 실패시켰다(회귀 2차 cooler 24/25). 드라이버에 `liveness_check_timeout=0`(쓰기 전 연결 확인) | `agentsvc/tools/mcp_kg.py`, `procsvc/main.py _kg` |
| 옛 수업 버튼 경로 삭제 | enterprise-sim `/erp/spare/issue` · `/cmms/pm/advance` · `/erp/purchase_orders/delay` · process `/api/simulate/*` 삭제, `scripts/c2_live_check.py` · `c2_live_in_container.sh` 삭제(C2 시작값 기준 검사 — 이 7절 완주 · `test_c3_bc_simplified` 가 대신한다). 업무 거래 skill:issue-spare · pm-advance · delay-delivery 는 ERP · CMMS 거래로 남는다(`/api/exec`) | 위 파일 |
| **결함 수정: 시나리오 에이전트가 실제로 쓰이지 않음** | 흐름 가져오기가 task 에 고른 에이전트(agent:pm-plan · agent:spare-buy)가 담당자(user_id)가 아니라 역할 기본(sys:agent)이었다. 워커는 담당자 프로필로 도구를 정하므로 B · C 에이전트가 전체 `enterprise` 서버로 돌았다(1차 완주 `live/run1-default-agent/`). `engine.new_workitem` 이 활동의 `agent` 를 담당자로 둔다 → 2차 완주에서 `enterprise-maint` · `enterprise-purchase` 만 씀 | `engine.py` |

### 7.2 실제 워커 완주 (포털 버튼, 한 번에 한 건, 20배속)

준비: neo4j를 새 볼륨 `hyd-iot-edu_neo4j-data-c3`(구조판)로 띄움(기존 볼륨 그대로) → `scripts/c3_ingest.py`로 HM-8 → PM-02 → PR-07 실제 추출 · 적재(192 · 227 · 161초, 절차 7 · 7 · 3, 규칙 8 · 9 · 5) → `c3_flows.py deploy`.

4차(근본 수정 뒤, 2026-10-10 00:28~00:36 UTC+9 새벽, `durations.json`):

| | 처리 건 | 버튼 → 처리 건 | 에이전트 | 승인 대기 | 시스템 | 버튼 → 끝 | 결과 |
|---|---|---|---|---|---|---|---|
| A | c3_cooling (agent:cooling) | 45초 | 106초 (도구 11) | 7초 | 명령 0.8 · 재관측 60 · 작업지시 0.5초 | 219초 | 정상. 누름 `PRESS-…` 기록 · 복구 기록 같은 처리 건 |
| B | c3_pm.5fccea88… (agent:pm-plan) | 1.6초 | 47초 (enterprise-maint 3개 도구) | 12초 | 오더 · 메일 0.6초 | 64초 | 정상, 표시 꺼짐 → [초기화]로 다시 켜짐 |
| C | c3_spare.50e1d3d4… (agent:spare-buy) | 1.6초 | 49초 (enterprise-purchase 3개 도구) | 12초 | 발주 · 메일 0.3 · 입고 0.5초 | 67초 | 입고 완료, 가용 7 ≥ 2, 표시 꺼짐 → [초기화]로 다시 켜짐 |

- 판단 사실의 납기: A 5.98 h · B 19.99 h · C 2.99 h(기준점 다시 맞춘 뒤 — 2차에서는 −1.27 h).
- 1~3차는 `live/run1-default-agent/`(기본 에이전트) · `run2-before-rootfix/` · `run3-hostgap/`(호스트가 17분씩 두 번 멈춰 센서 데이터 공백 — 진단이 공백을 보고 기다림, 무효)에 남겼다.
- B 경쟁: 추천 "이번 예정된 정비 시간 단독". 지금 정지 → 오더 손실 감점, 미루기 → 허용 한계 초과 제외, 두 대 묶기 → 씰 키트 부족 제외 + 인원 감점, 넷 다 씰 키트 부족 경고(C와 이어짐).
- C 경쟁: 추천 "최단 납기 긴급 발주"(210만 원). OEM 표준 발주(330만 원)는 전결 경고. **설계와 다르다** — 8절.
- 판단 기록 provenance: A · B · C 모두 35개(값 · 시스템 · 읽은 방법). 카드마다 달라지는 값(발주 금액 · 납기 여유)은 결정 수준에서 "후보마다 계산"으로 비어 있고, 각 카드의 facts 에 값이 있다.
- 끝난 처리 건(A 1건, B · C 각 2건 — 1차는 기본 에이전트)은 지우지 않았다. 실패한 A 시도 2건과 그때 생긴 사람 검토(미지원 경보) 2건, 옛 감시기가 만든 사람 검토 2건은 `cleanup_residue_instances.py`로 숨겼다(백업 `.evidence/a161-c3/residue-*`).
- 화면: `.evidence/a161-c3/live/` — `X-1-start`(처음) · `X-3-approval`(승인 대기) · `X-4-result`(결과) · `X-5-after`(표시 꺼짐) · `X-6-*-390`(휴대폰 결과 카드 · 처리 과정) · `R-after-reset-*`(초기화 뒤).

### 7.3 기준 복원 · 시험

- 흐름 `deploy-reset`, neo4j 원래 볼륨(전체판, FailureMode 7), 설비 초기화, 업무 데이터는 새 시작값. 구조판 볼륨 `neo4j-data-c3`는 남겨 두었다(지우려면 사용자 확인).
- 단위 시험 1,835 통과 · 4 건너뜀(엔진 수정 전), 엔진 수정 뒤 관련 시험 통과.
- 회귀(실제 워커): 1차 cooler 40/40 · pump-fan 43/43. 엔진 수정 뒤 2차는 아래 보고에 적는다.
- 주의: 회귀 검사기의 `/api/reset`(업무 실행 초기화)이 완주 때 만든 업무 행(WO · PR · GR)을 지운다. 처리 건 기록은 남는다.

### 7.4 블랙박스 점검 — 기록 · 화면에 없는 곳 (근본 수정 뒤)

| 곳 | 지금 | 비고 |
|---|---|---|
| C 지식의 "불량 기대비용" | 실제 추출이 PR-7.4 비교 원칙을 판정 규칙으로 만들지 않았고, SOP-PUR-13(최단 납기)을 A정밀로 연결했다 → 추천이 설계(B-OEM)와 다름 | 원문이 "총비용으로 비교한다"는 원칙만 있고 판정할 문턱이 없다. 적재 스크립트(`c3_ingest.py`)는 검토 단계를 손대지 않고 승인했다 — 사람 검토에서 규칙 추가 · 연결 수정이 필요(C1 몫, 열림) |
| 결정 수준 provenance 의 카드별 값 | po_amount · lead_slack_days · supplier_avl 은 결정 수준에서 "후보마다 계산"(값 없음) | 값은 각 카드 facts 에 있다. 화면의 카드별 출처 표시는 확인 안 함 |
| 승인 화면 캡처 | 승인 카드(추천 · 진 안 · 근거)가 화면 아래라 캡처에 잘림 | 판단 원본 `X-decision.json` |

### 7.5 검증 상태 (2026-10-10 새벽)

- 라이브 4차 A · B · C 완주 · 표시 꺼짐 · [초기화] 복원 · 누른 사람 기록 · A 누름 id 연결: **검증됨**(7.2).
- 회귀 3차(기준 복원 뒤 — 흐름 deploy-reset · neo4j 전체판 · 설비 초기화, 워커 1개): cooler `scenario_instance_test.py --worker` **40/40**, pump-fan `--worker` 32/33(펌프 진단이 2분 평균 미충족으로 보류 — 스크립트 안내대로 실제 워커는 `--reassess-held`) → `--worker --reassess-held` **47/47**. process 재시작 0. 증거 `.evidence/a161-c3/reg3-*.log`, `reg3b-pumpfan.log`.
- 단위 시험 전체 1,842 통과 · 4 건너뜀(한 번은 1 실패 — 다시 돌리면 통과하는 흔들림).
- 워커(PID 51665, 이전 에이전트가 이 워크트리에서 띄운 것을 이어 씀) 멈춤, 8097/8098 내려감 확인.
- 회귀 2차 pump-fan(21/23)은 무효 — 검사가 도는 중에 이미지 재빌드를 했다(CLAUDE.md §3 위반, 내 실수). 같은 때 워커 LLM 이 세션 한도에 걸렸다.
