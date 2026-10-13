# C2 실행 — 승인 뒤 시스템 처리 · 결과 확인 · 결과 보고, 업무 표 감시, 수업 버튼 (확정 TODO C2)

작성 2026-10-09. 근거: `docs/보고서/2026-10-09_HYD_시나리오_3개.md`(확정 시나리오), `TODO.md` 확정 TODO C, 코디네이터 지시(2026-10-09 최종 결정 · C1 인계 · 기존 부품 재사용).
브랜치 `worktree-agent-afbc3de09be36a2d6`(685354f 기준). 증거: `.evidence/a161-c2/`(SQL 연기 시험 · 라이브 확인 로그 · 받은 메일).

**비유 한 줄**: 담당자가 결재 도장을 한 번 찍으면, 그 뒤의 일(발주서 내기 · 메일 · 정비 기사 보내기 · 시운전 · 입고 검수 · 결과 보고)은 총무팀 키트가 알아서 하고 결과만 알려 준다.

**스스로 판정할 체크 질문**
- 세 흐름 모두 사람 task 가 "담당자 승인" 하나뿐인가? 그렇다(`test_shapes_stay_small_enough_to_draw`).
- 300만 원이 넘는 발주에 2차 승인이 붙는가? 붙지 않는다. 금액은 카드 경고로만 보인다(`test_c_one_approval_…`, `test_c_amount_and_lead_slack_…`).
- 미달 가지를 실제로 밟는가? A 냉각 미회복 · B 시운전 기준 미달 · C 납기 초과 모두 끝까지 돈다(시험 이름에 `shortfall` · `delay`).
- 수업 버튼은 원인만 만들고, 처리 건 시작은 감시기가 하는가? 그렇다(출고 −2 → `SPARE_BELOW_MIN`, +300 h → `PM_DUE`).
- 에이전트가 쓰기 도구를 가지는가? 아니다. 업무 MCP 두 서버는 읽기만, 메일 · 발주 · 계수기 리셋은 승인 뒤 시스템 task 가 한다.

---

## 1. 세 흐름 (BPMN 모양 — 시험 `tests/test_c2_execution.py` 의 그림 그대로)

레인 3개(담당자 / 에이전트 / 시스템). 사람 task 는 승인 하나.

| | 에이전트 | 담당자 (1회) | 시스템 처리 | 시스템 확인 → 분기 | 결과 보고 |
|---|---|---|---|---|---|
| **A 긴급 대응** | `task:decide` 원인 진단 · 냉각 조치 제안 | `task:select` 운전원 승인 + 점선 타이머 `PT10M` → `svc:report`(승인 지연 알림) | `task:command` 냉각 명령 | `task:reobserve` 재관측 → `recovered == True` 면 `task:work-order` 작업지시 | `svc:report` 정상 / 미달 |
| **B 정기 정비** | `task:decide` 정비 일정 제안 | `task:select` 설비보전팀장 승인 | `task:work-order`(+생산팀 메일) → `svc:maintenance`(예정된 정비 시간까지 기다렸다가 정비) | `svc:test-run` 시운전 → `passed == True` | `svc:report` 정상 / 미달 |
| **C 예비품 구매** | `task:decide` 발주안 제안 | `task:select` 구매 담당 승인 | `svc:erp-po` ERP 발주(+공급사 메일) | `svc:goods-receipt` 입고 확인 + 실선 타이머 `P6D`(납기 초과) | `svc:report` 입고 완료 / 지연 |

- A 의 작업지시는 재관측이 정상일 때 낸다. 사건 상태기계가 회복(RESOLVED) 뒤에만 작업지시를 받기 때문이다(기존 안전 규칙, 바꾸지 않음).
- 미달 가지는 사람 task 없이 "미달" 결과 보고로 끝난다. 사건은 미달이면 ESCALATED, 정상이면 CLOSED 로 닫힌다(`machine.on_result_report`).

## 2. 부품 (흐름 가져오기의 일반 부품, 매핑 `{"part": key, "config": {...}}`)

| key | tool | 하는 일 | 승인 뒤만? | config |
|---|---|---|---|---|
| `task:decide` | `formHandler:decide` | 판단 · 제안 에이전트 task 하나. 기준 `task:rank` 계약(결과 `decision` · `decision_id`)에 진단 칸(`cause` · `failure_mode` · `guide_card`, 선택)을 더함. 입력은 경보 값만 | — | 매핑 `instruction`(시나리오별 지시문) |
| `svc:erp-po` | `enterprise:PR_CREATE` | 승인이 확정한 공급사 · 수량 · 금액으로 ERP 발주(기존 `skill:procure-part`) | 예 | `mail`(선택) `{to, subject, body}` |
| `task:work-order` | `enterprise:WO_CREATE` | 기존 CMMS 작업지시(`skill:schedule-maintenance`) | 예 | `window_var`(예: `alert.evidence.night_window_id`), `mail`(선택, 생산팀 공지) |
| `svc:maintenance` | `plant:restore` | (until 이면 예정된 정비 시간까지 대기) 작업지시 완료 · 부품 소모 · 시뮬레이터 부품 복구 · 완료 알림 | 예 | `component`(cooler · pump · fan), `sop`, `until` |
| `svc:test-run` | `plant:test-run` | 안정 대기(가상 PT10M ÷ 배속) 뒤 PS1 ≥ 165 · FS1 ≥ 8 · VS1 < 1.2 판정. 통과면 계수기 리셋 · 다음 기한 기록. 값을 모르면 미달 | 예 | `criteria`, `settle`, `reset_counter` |
| `svc:goods-receipt` | `enterprise:GR_CONFIRM` | 리드타임(+공급사 지연)만큼 기다린 뒤 입고 · 검수 기록, 재고 반영, 사건 종결 | 예 | `purchase_order_var` |
| `svc:report` | `process:report` | 결과를 담당자 알림 · 처리 과정 기록으로 남기고 사건을 닫음. 사람 task 아님 | 아니오 | `outcome`(정상 · 입고 완료 · 미달 · 지연 · 알림 · 승인 지연), `title`, `summary`(값 틀, 없는 값은 "(없음)") |
| `svc:wait` | `process:wait` | 시간 대기(일반) | 아니오 | `duration` 또는 `until` |
| `svc:mcp-call` | `mcp:call` | 승인 뒤 MCP 도구 하나(일반) | 예 | `server`, `tool`, `arguments` |

- 메일은 `hyd-effects`(it/effects-mcp) `send_mail` 하나만 있다. 수업 메일함 Inbucket(SMTP 54325, 웹 54324)으로만 간다. 실제 발송 없음.
  같은 작업의 재시도는 같은 멱등 키(`<처리 건>:<작업>:notice`)라 한 통만 간다.
- 엔진: 점선(멈추지 않는, `cancelActivity="false"`) 경계 타이머를 받는다. 승인 task 는 계속 기다리고 알림 가지만 따로 흐른다(`engine.non_interrupting`).
- 기다리는 부품(시간 대기 · 입고 확인 · 정비의 until)과 거기 붙은 타이머만 수업 압축(`PROCESS_WAIT_COMPRESSION`, 기본 60)을 더 받는다.
  20배속 × 60: 예정된 정비 시간 9 h → 27초, 납기 5일 → 6분, 납기 초과 6일 → 7.2분. 설비 · 재관측 · 시운전 · 승인 타이머는 배속만.

## 3. 판단 — B · C 도 A 와 같은 경쟁 판단 경로

`evaluate_cards`(dmn-mcp) → `decide.gather_facts` → 후보 → 규정 → BSC 득실 → 순위. C2 는 사실을 업무 DB 에서 **온톨로지 변수 이름 그대로** 낸다(C1 `scenario_structure.cypher`).

| 시나리오 | 변수 (출처) | 어디서 |
|---|---|---|
| B | `hours_since_pm` · `hours_at_next_window` · `hours_at_following_window` · `pm_crew_available` · `spare_available` (sys:cmms) | `GET /cmms/pm_status` = 뷰 `ent.pm_status` 한 행 |
| B | `order_due_h` (sys:mes) | 기존 `GET /mes/orders` |
| C | `spare_gap` (sys:erp) + `need_qty` · `need_by_days` · `spare_quotes` | `GET /erp/spare_stock` + `GET /scm/quotes` |
| C | `po_amount` · `lead_slack_days` · `expected_defect_cost` (sys:agent, 카드마다) | `cards.candidate_facts` = 필요량 × 그 카드 공급사 견적 |

- 업무 경보에는 증상이 없어 진단(T1)이 없다. dmn-mcp 새 읽기 도구 `business_causes(asset, pattern)`:
  재고는 "재주문점 아래 부품을 쓰는 원인"(Cause -INVOLVES_PART-> Part), 정기 정비는 "정비가 막는 고장의 원인"(FailureMode -PREVENTED_BY-> Skill).
  `evaluate_cards` 는 업무 경보면 이 근거로 원인을 확인한다(엉뚱한 원인은 거절). C1 인계 3번 해결.
- 정비 · 구매 카드도 지금 운전점 예측(sv:ts1)이 붙는다: `forecasting.candidates` 가 명령 없는 카드는 현재 입력 그대로 예측한다. 설비 상태가 신선하면 `rule:ts1-hard` 가 "모름"이 되지 않는다(시험이 확인). C1 인계 2번.
- 시험 `tests/test_c2_judgement.py`(실제 enterprise-sim 을 HTTP 로 부름):
  B — +300 h 뒤 사실 1950 / 1959 / 2230 h · 인원 2 · 키트 3 → 추천 "이번 정비 시간 단독", 미루기 제외(2,230 > 2,200), 지금 정지 감점, 두 대 묶기 감점. 키트 0 이면 추천 없음.
  C — 출고 −2 뒤 필요 6 → 카드별 금액 330 · 210 · 120, 납기 여유 1 · 4일, C트레이딩 AVL 제외, B-OEM 300만 원 초과 경고(표시만), A정밀 불량 기대비용 감점 → B-OEM 추천. 필요일 3일이면 B-OEM 에 결품 경고.

## 4. 업무 표 감시 · 수업 버튼

`procsvc/business_monitor.py` — 규칙 둘, 같은 루프 · 같은 경보 계약(센서 경보와 같은 원천 접수 경로).

| 패턴 | 출처 | 조건 | 회차(같은 처리 건) | 경보 id |
|---|---|---|---|---|
| `SPARE_BELOW_MIN` | ERP | 가용(현재고 − 예약 + 입고 예정) < 재주문점 | 내려간 시각 `below_since` | `ERP-SPARE_BELOW_MIN-<부품>-<시각>` |
| `PM_DUE` | CMMS | 마지막 정기 정비 뒤 운전시간 ≥ 1,950 h (주기 2,000 − 사전 알림 50) | 계수기 회차 `cycle` | `CMMS-PM_DUE-<설비>-C<회차>` |

- 한 업무 시스템이 죽어도 다른 규칙은 돈다. 환경변수 `BUSINESS_MONITOR`(1) · `BUSINESS_MONITOR_INTERVAL_S`(15).
- 수업 버튼(포털 고장 모사 화면이 부를 API, U 담당에게):

| 버튼 | process 주소 (= enterprise-sim) | 본문 (모두 선택) | 결과 |
|---|---|---|---|
| C 자재 출고 −2 | `POST /api/simulate/spare-issue` (`/erp/spare/issue`) | `{part_no: "P-PMP-SEAL", qty: 2, asset: "HYD-03", reason, request_id}` | 가용 3 → 1, 다음 감시 주기에 C 처리 건 |
| C 재고 되돌리기 | `POST /api/simulate/spare-reset` (`/erp/spare/reset`) | `{part_no}` | 시작값(실물 5 · 예약 2) |
| C 공급사 납기 지연(미달 가지) | `POST /api/simulate/delivery-delay` (`/erp/purchase_orders/delay`) | `{days: 3, ref \| part_no}` | 열린 발주의 입고 예정 +3일 → 납기 초과 타이머가 먼저 울려 "지연" 보고 |
| B 운전시간 빨리 감기 +300 h | `POST /api/simulate/pm-advance` (`/cmms/pm/advance`) | `{hours: 300, asset}` (asset 없으면 세 대) | HYD-02 1,650 → 1,950 h → PM_DUE, HYD-03 1,880 h(묶음 후보) |
| B 계수기 되돌리기 | `POST /api/simulate/pm-reset` (`/cmms/pm/reset`) | `{asset}` | 시작값 |
| 보기 | `GET /api/simulate/spare-stock?part=` · `GET /api/simulate/pm-status?asset=` | — | 재고 · 이동 원장 / 계수기 · 원장 |

- B 미달 가지를 수업에서 보이려면: "정비 완료" 알림이 뜬 뒤 시운전 안정 대기(약 30초) 동안 기존 "펌프 누설" 고장 주입을 누른다 → PS1 · FS1 기준 미달 → "미달" 보고.

## 5. 업무 DB (마이그레이션 `it/supabase/migrations/20261009000045_c2_execution.sql`, 메모리 백엔드 같은 규칙)

**기존 것은 그대로 쓴다**(사용자 지시): CMMS 작업지시 `skill:schedule-maintenance`(+취소), ERP 구매요청 `skill:procure-part`(+취소), MES 오더 · CMMS 이력 · SCM 공급사 읽기, `/api/exec` · `/api/transactions` · `/api/reset`. 두 거래에는 칸만 보탰다(예정된 정비 시간 id · 시작 시각, 부품 번호 · 수량 · 금액 · 입고 예정).
기본 작업지시 문구는 이제 "예정된 정비 시간 (야간)"이다(옛 문구 교체).

**새로 보탠 것(없던 것만)**

| 무엇 | 표 · 함수 · 거래 |
|---|---|
| C 시작: 예비품 재고 · 이동 원장 | `ent.spare_stock`(+`need_by_days`) · `ent.stock_movements`(ISSUE · CONSUME · ORDER · RECEIPT · RESET), 거래 `skill:issue-spare` |
| C 견적(씰 키트 · 팬 베어링) | `ent.part_quotes` — 기존 `ent.suppliers` 는 공급사 하나에 부품 하나(쿨러 코어)라 씰 키트 견적을 둘 곳이 없었다 |
| C 입고 · 지연 | `ent.goods_receipts`, 거래 `skill:receive-goods` · `skill:delay-delivery`(수업 버튼) |
| B 시작: 운전시간 계수기 · 계획 | `ent.pm_settings`(2,000 h ± 10 %, 알림 50 h, 키트 씰 1) · `ent.pm_counters` · `ent.pm_counter_log`, 뷰 `ent.pm_status`, 거래 `skill:pm-advance`(버튼) · `skill:pm-reset`(시운전 통과 뒤) |
| B 예정된 정비 시간 | `ent.maintenance_window_rules`(야간 +9 h · 2명, 주말 +105 h · 4명, 월간 +280 h · 6명) → `ent.next_maintenance_windows` |
| B 정비 완료 | 거래 `skill:complete-maintenance`(작업지시 완료 + SOP 표준 부품 소모) |
| 읽기 RPC | `spare_stock_read` · `part_quotes_read` · `pm_status_read` · `maintenance_windows_read` · `purchase_order_read` |

- 추가만 하고, 두 번 적용해도 안전하다(if not exists · on conflict · 바뀐 함수는 drop 뒤 생성). 버리는 DB 에서 전부 적용 + 다시 적용 확인.
- 제거: 이전 작업자가 만든 CMMS 일정 · 처리 건 기록 표와 거래, effects-mcp 의 일정 · 기록 도구(기존 부품 재사용 지시).

## 6. 업무 MCP 둘로 나누기

같은 서버 코드(`it/enterprise-mcp`)를 `ENTERPRISE_MCP_TOOLSET` 으로 띄운다. 모두 읽기 전용(readOnlyHint=true).

| 서버 이름(tenants.mcp) | 컨테이너 · 포트 | 도구 | 붙이는 에이전트 |
|---|---|---|---|
| `enterprise-maint` (보전용) | `enterprise-mcp-maint:8196` | `pm_status`(계획 · 계수기 · 키트 영향) · `maintenance_windows` · `cmms_history`(작업지시 · 백로그) · `mes_orders` | B 정기 정비 계획 에이전트 |
| `enterprise-purchase` (구매용) | `enterprise-mcp-purchase:8195` | `spare_stock`(ERP 재고) · `part_quotes` · `scm_suppliers`(SCM · 공급사) | C 예비품 구매 에이전트 |
| `enterprise` (기존, 전부) | `enterprise-mcp:8199` | 위 전부 + 자유 SQL `query` · `describe_*` | A · 랩업 |

- 두 서버의 도구는 겹치지 않고, 나눈 서버에는 자유 SQL 이 없다(경계를 SQL 이 넘지 않게). 시험 `test_business_mcp_is_split_…`.
- 기준 서버 목록 · 시드 tenants.mcp · 워커 기본 허용 목록 · compose(프로필 cliagents) · 호스트 워커 주소 바꾸기(`MCP_HOST_REWRITE`)에 등록했다.
- 에이전트별로 붙이는 것은 사용자(에이전트) 행의 `tools` 칸이다(예: B 에이전트 `neo4j,hyd-dmn,enterprise-maint`). 에이전트 행 만들기는 C3 몫.

## 7. 설정 키

| 키 | 기본 | 뜻 |
|---|---|---|
| `PROCESS_WAIT_COMPRESSION` | 60 | 기다리는 부품과 그 타이머의 수업 압축 |
| `PLANT_SIM_URL` | `http://host.docker.internal:8000` | 정비 수행 모사(시뮬레이터 부품 복구) |
| `EFFECT_MCP_SERVERS` | hyd-effects = `effects-mcp:8197` | 승인 뒤 메일 서버 |
| `BUSINESS_MONITOR` · `BUSINESS_MONITOR_INTERVAL_S` | 1 · 15 | 업무 표 감시 |
| `EFFECTS_SMTP_HOST` · `EFFECTS_SMTP_PORT` | `host.docker.internal` · 54325 | Inbucket |
| `ENTERPRISE_MCP_TOOLSET` | all | enterprise-mcp 도구 묶음(maintenance · purchasing) |
| `it/supabase/config.toml [inbucket] enabled` | true | 다음 `supabase start` 부터 메일함 |

## 8. 시험 · 확인

- 단위: 전체 `.venv/bin/python -m pytest -q` → **1754 passed, 4 skipped, 실패 0**(마지막 실행). 이전 실행에서는 `test_mcp_check.py::test_html_page_is_not_an_mcp_endpoint` 가 한 번씩 실패했다 — 작업 전 기준선에서도 같은 흔들림(이 macOS 의 로컬 HTTP).
  - `test_c2_execution.py` 29: A 정상 · 미달 · 승인 지연 알림, B 정상 · 시운전 미달 · 값 모름, C 입고 · 납기 지연, 그림 크기 · 레인 · 사람 task 1개, 점선 타이머 가져오기, 설정 오류 7종, 승인 기록 없는 효과 거절, 작업지시 뒤 재관측.
  - `test_c2_parts.py` 23: 감시 규칙 둘(회차 · 한 시스템 실패), 업무 DB 메모리 백엔드(출고 · 발주 · 입고 · 소모 · 지연 · 계수기), HTTP 버튼, 메일 멱등.
  - `test_c2_judgement.py` 5: §3.
- SQL: `scripts/c2_scratch_db.sh`(로컬 Supabase 안 버리는 DB) + `scripts/c2_sql_smoke.sql` → `.evidence/a161-c2/sql-smoke.txt`. 끝나고 DB 삭제.
- 라이브: `scripts/c2_live_in_container.sh` → `.evidence/a161-c2/live-check.log` · `live-check.json` · `live-mail.eml`(18단계 모두 통과, 실제 Postgres):
  출고 −2 → 경보 1건(같은 회차 0) → 금액 330 → 비AVL 거절 · 발주 → 메일 1통(재호출 replayed) · 포털 경로 거절 → 지연 +3일 → 입고(재고 9 / 가용 7) → 읽기 계정 →
  +300 h → PM_DUE 1건(HYD-02, 1950 / 1959 / 2230 h) → 리셋(0 h, 회차 2) → 새 경보 없음. 끝나고 임시 역할 · DB 삭제.

## 9. 참고 구현 대조 (ProcessGPT `/Users/uengine/process-gpt/services`, 읽기만)

| 설계 선택 | 따른 참고 (파일:줄) 또는 HYD 자체(이유) |
|---|---|
| 서비스 task 도달 → SUBMITTED → 엔진이 실행, 결과 output → 다음 | `completion/polling_service/workitem_processor.py:1893-1903`(_check_service_tasks) · `:5293-5317` · `polling_service.py:40-70` |
| 경계 타이머를 다음 활동 후보로 넣음 | `workitem_processor.py:4492-4572`(inject_boundary_events_as_next). 점선(멈추지 않는) 타이머 구분은 제품에 없음 → **HYD 자체**(승인 지연은 알림만, 승인은 계속 — 확정 흐름) |
| 기다리는 부품: 끝 시각 저장 · 폴링이 도래 시 완료, 수업 압축 | 제품은 `due_date` 계산 · 저장만(`workitem_processor.py:1395-1398`) → **HYD 자체**(예정된 정비 시간 · 납기를 수업 시간에 실제로 흘려야 함) |
| 승인 뒤 MCP 호출, 서버 설정 = tenants.mcp, 인자 틀 치환 | `completion/polling_service/mcp_processor.py:64-74,111-126`, `completion/compensation_handler.py:15-40`. 정의가 도구 · 인자를 고정하는 것은 **HYD 자체**(결정론, 승인 뒤만) |
| 도구 호출 이벤트 `tool_usage_started/finished` | 이벤트 enum `frontend/docker-compose/volumes/db/init.sql:101-102`, 본문 `n8n-agent/executor.py:224,232` |
| 읽기/쓰기 표시 readOnlyHint, 연결 검사 | `mcp-hub/src/mcp_hub/conformance.py:25-26`, `mcp-validator/src/mcp_validator/validator.py:92,170` |
| 업무 MCP 를 같은 코드 · 다른 도구 묶음 두 서버로, 에이전트마다 붙이는 서버 | 실행마다 MCP 서버 목록을 넘김 `cliagents/tests/test_registry.py:45`(install_bridge mcp_servers), 서버 이름 = tenants.mcp 키(기존 A144 채택). 도구 묶음 환경변수는 **HYD 자체**(B · C 도구가 겹치지 않게 — 확정 결정 2) |
| 실패 3회 재시도 뒤 PENDING · 사유 보존 | `completion/polling_service/polling_service.py:78-95`(제품은 DONE, HYD 는 PENDING — 기존 결정) |
| 외부 효과 멱등 키(decision+skill, 메일 idempotency_key) | 제품에 없음 → **HYD 자체**(재시도 때 발주 · 메일이 두 번 나가지 않게) |
| 참여자 알림 `notifications` 삽입(결과 보고 · 정비 완료) | 열 이름 `frontend/docker-compose/volumes/db/init.sql:1105-1125`. 제품은 DB 트리거, HYD 는 앱(기존 inbox.py 방식) |
| 분기 조건 = 변수 위 식 평가(정상/미달) | `workitem_processor.py:2338,2394`(conditionFunction). 승인 값(금액)을 서버가 결정론으로 넣는 것은 **HYD 자체**(제품은 LLM mapper `:924`) |
| 판단 · 제안을 에이전트 task 하나로 | 제품 에이전트 task 는 폼 하나에 결과를 냄(`cliagents` 작업 단위 = work item 하나). 진단 + 카드 칸을 합친 폼은 **HYD 자체**(확정 흐름 "task 를 나누는 기준") |
| 업무 데이터 감시가 처리 건을 연다 | 제품에 없음 → **HYD 자체**(시작은 자동) |
| 되돌릴 수 없는 거래 사유 목록 | 제품은 되돌리기 때 보상 코드 생성(`completion/compensation_handler.py:223`). 불가역 목록은 **HYD 자체**(기존 effect_compensation) |

## 10. 하지 않은 것 · 열린 것

1. **공유 Supabase · 메인 스택에는 적용하지 않았다**(다른 에이전트 소유). C3 가 할 일:
   `docker exec -i supabase_db_hyd-iot-edu psql -U postgres -v ON_ERROR_STOP=1 < it/supabase/migrations/20261009000045_c2_execution.sql`(또는 `supabase db reset`),
   seed.sql 의 tenants.mcp 갱신(두 서버 추가), 이미지 빌드 · 기동 `effects-mcp`(profile process) · `enterprise-mcp-maint` · `enterprise-mcp-purchase`(profile cliagents), Inbucket 켜기(Supabase 재시작), process 재배포.
2. **B 카드와 예정된 정비 시간의 연결**: 작업지시의 정비 시간은 `window_var`(B 그림은 `alert.evidence.night_window_id` = 이번 야간)로 정한다. 담당자가 "미루기" 같은 다른 시점의 카드를 고르면
   정비 시간이 카드를 따라가지 않는다. 카드별 시점이 필요하면 C1/C3 가 카드에 시점 값을 싣는 방법을 정해야 한다(지금 B 는 추천이 "이번 정비 시간 단독"이라 수업 흐름은 맞다).
3. **사건(Incident)의 결과 보고 종결**: 미달은 ESCALATED 로 닫는다. 사건 화면이 이 상태를 "미달"로 보이는지는 U 확인 몫.
4. **Linux 수업 서버의 `PLANT_SIM_URL`**: plant-sim 포트가 127.0.0.1 에만 열리면 컨테이너에서 닿지 않아 정비 · 시운전이 PENDING 이 된다(맥 · 윈도 Docker Desktop 은 됨).
5. **시운전 값의 신선도**: `latest_tag` 는 최신값을 읽지만 시각을 보지 않는다. 시뮬레이터가 멈춰 있으면 옛 값으로 판정할 수 있다.
6. **씰 키트 시작 재고**: C 를 단독으로 돌릴 때 330만 원(6개)이 나오도록 가용 3 으로 두었다. 그래서 B 단독에서는 "씰 키트 3개 미만 → 구매 경보 예정" 경고(C1 rule:pm-spare-warn)가 뜨지 않는다. B → C 로 이어 돌리면 B 가 1개를 써서 가용 2 가 된다.
7. 에이전트 행(시나리오 에이전트 3개, `tools` 칸에 붙일 서버) · 실제 워커로 A · B · C 완주는 C3 몫.
8. 제품 최신 MCP 관측 이벤트(`mcp_call_*`)는 HYD enum 에 없어 `tool_usage_*` 를 쓴다(전과 같음).

## 11. C3 조립 에이전트가 알아야 할 계약

- 시작 경보: `ERP-SPARE_BELOW_MIN-<부품>-<시각>`(asset HYD-03, evidence: part_no · available · spare_gap · need_qty …),
  `CMMS-PM_DUE-<설비>-C<회차>`(evidence: hours_since_pm · hours_at_next_window · hours_at_following_window · pm_crew_available · spare_available · night_window_id …).
  흐름 가져오기의 경보 패턴 목록에 둘 다 보인다(`catalog.business_patterns`).
- 에이전트: `task:decide` 하나. 업무 경보면 먼저 dmn-mcp `business_causes` 로 원인 · 고장 유형을 얻어 `evaluate_cards` · `submit_decision` 에 넘긴다.
- C 카드: 발주 SOP 스킬은 `PR_CREATE`(값 = 공급사 id). 금액은 승인 순간 서버가 ERP 견적으로 확정(`approved_amount` 등, task 가 낼 수 없음). 수량 · 부품을 모르면 승인 거절.
- B: 작업지시 `config: {"window_var": "alert.evidence.night_window_id", "mail": {...}}`, 정비 `{"component": "pump", "sop": "SOP-PMP-04", "until": "work_order.after.window_starts_at"}`.
  계수기 리셋은 시운전 통과 때 시스템이 한다(`PM_RESET` → `skill:pm-reset`).
- C1 적재 순서 A → B → C (C 만 먼저 넣으면 409).
