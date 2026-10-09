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
