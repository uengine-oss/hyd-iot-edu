# C2 실행 — 승인 뒤 효과 부품 · ERP 재고 감시 · 업무 DB (확정 TODO C2)

작성 2026-10-09. 근거: `TODO.md` 확정 TODO C(원칙 · 열린 결정 기본값), `scenario-research.md` §2.5 · §2.6 · §8 · §10.2(X1~X10).
증거: `.evidence/a161-c2/` (단위 시험 · SQL 연기 시험 · 라이브 확인 로그 · 받은 메일 원문).

**비유 한 줄**: 결재 도장(사람 승인)이 찍힌 뒤에 움직이는 "총무팀 업무 키트"다.
발주서 내기 · 메일 보내기 · 일정 잡기 · 기다리기 · 정비 기사 보내기 · 입고 검수를 BPMN 칸 하나씩으로 끼워 쓴다.

**스스로 판정할 체크 질문**
- 사람 승인 앞에 메일 · 발주 task 를 그리면 가져오기에서 거절되는가? 거절된다(`test_mcp_write_before_the_human_approval_is_refused`).
- 승인 전에 에이전트 도구 목록에 쓰기 도구가 보이는가? 보이지 않는다. effects-mcp 는 `tenants.mcp` 에 없고, 포털 '써 보기'도 거절한다(라이브 5d).
- 금액이 300만 원 이하면 구매팀장 task 가 열리지 않는가? 열리지 않는다(`test_purchase_under_limit_skips_the_manager`).
- 금액을 모르는 채 승인되어 팀장 분기를 건너뛸 수 있는가? 없다. 수량 · 견적을 모르면 승인 자체를 받지 않는다.
- 정비형 흐름의 "효과 재관측"이 실제로 값을 읽는가? 읽는다. 이전에는 사건이 CLOSED 라는 이유만으로 회복으로 판정했다.

> B(정비 계획)는 재정의 중이다(코디네이터 2026-10-09: "정기 정비 — 운전 시간 · 달력 주기 도래"). 그래서 B 전용 시작 패턴 · 데이터는 만들지 않았다.
> 정비창 데이터 · 작업지시 정비창 전달 · 대기 · 정비 수행 모사 · 작업지시 뒤 재관측은 **일반 부품**이라 새 B 에도 그대로 쓴다.
> "정비 주기 도래" 감시는 `business_monitor.RULES` 에 규칙 하나를 더하면 붙는다. 방법은 시험 `test_another_monitor_rule_plugs_in_without_new_loop_code` 를 본다.

---

## 1. 부품 (bpmn_import 카탈로그의 일반 부품, 시나리오에 묶이지 않음)

흐름 가져오기(B3) 매핑에서 task 에 `{"part": <key>, "config": {...}}` 로 고른다.
효과 부품은 앞 경로에 사람 승인(`formHandler:select_card`)이 있어야 등록된다. 실행할 때도 처리 건에 `approved_by` 가 없으면 거절한다(이중 확인).

| 카탈로그 key | tool | 하는 일 | 효과? | config | 내는 값 |
|---|---|---|---|---|---|
| `svc:mcp-call` | `mcp:call` | 승인 뒤 MCP 도구 하나 호출. 인자 틀의 `{값}` · `{값.안쪽}` 을 처리 건 값으로 바꾼다(없는 값이면 실패, 빈 메일 없음) | 예 | `server`, `tool`, `arguments`, `output`(기본 `mcp_receipt`) | `mcp_receipt` |
| `svc:erp-po` | `enterprise:PR_CREATE` | ERP 발주. 승인 경로가 확정한 `approved_supplier · approved_part_no · approved_qty · approved_amount` 로 낸다. ERP 가 견적 · AVL · 금액을 다시 확인한다 | 예 | 없음 | `purchase_order` (영수증: `ref`, `detail`, `after`=발주 행) |
| `svc:wait` | `process:wait` | 시간 대기. `duration`(ISO, 업무 시간) 또는 `until`(처리 건 값의 시각, 예 `work_order.after.window_starts_at`) | 아니오 | `duration` 또는 `until`, `label` | `waited` (계획 · 끝 시각) |
| `svc:maintenance` | `plant:restore` | 정비 수행 모사. 작업지시가 있으면 CMMS 완료(SOP 표준 부품 소모), plant-sim 대상 부품 복구, 참여자에게 완료 공지 | 예 | `component`(cooler·pump·fan, 비우면 전체), `sop`, `work_order_var` | `maintenance` |
| `svc:goods-receipt` | `enterprise:GR_CONFIRM` | 입고 확인. 발주 리드타임만큼 기다린 뒤 입고 · 검수 기록과 재고 반영, **사건 종결**, 참여자 공지 | 예 | `purchase_order_var` | `goods_receipt`, `received` |

기존 부품도 함께 쓴다: `task:work-order`(CMMS 작업지시), `task:reobserve`(재관측), `task:select`(승인), 사람 task · 에이전트 task.

**수업용 MCP 서버 hyd-effects** (`it/effects-mcp`, 쓰기 도구 3개, 모두 `readOnlyHint=false` · `idempotency_key`):

| 도구 | 인자 | 기록 위치 |
|---|---|---|
| `send_mail` | `to`, `subject`, `body`, `cc?` | SMTP → Supabase 로컬 Inbucket(54325, 웹 54324). 실제 발송 없음 |
| `add_calendar_entry` | `asset`, `title`, `starts_at?`, `duration_h?`, `wo_ref?`, `note?` | `ent.cmms_calendar` (enterprise-sim `skill:calendar-entry`) |
| `record_case` | `title`, `body`, `asset?`, `proc_inst_id?` | `ent.case_records` (`skill:record-case`) |

process 는 `idempotency_key = <처리 건 id>:<작업 id>` 를 넣는다. 같은 키로 다시 부르면 첫 결과를 돌려준다(`replayed: true`, 라이브 5b).
학생이 등록한 MCP 서버(`tenants.mcp`, 연결 검사를 통과한 설정)도 `server` 이름으로 부를 수 있다.

## 2. 승인 경로가 내는 발주 값 — "발주서 확정" 에이전트 task 는 두지 않는다 (결정)

- 흐름에 `enterprise:PR_CREATE` 부품이 있으면 `select`(카드 승인)가 승인된 카드의 발주 값을 서버에서 확정해 처리 건 값으로 넣는다.
  - 공급사 = 카드의 `PR_CREATE` 값
  - 부품 · 수량 = 처리 건 `part_no` · `need_qty`(에이전트 산정)가 먼저, 없으면 ERP 재고 경보 근거
  - 단가 = ERP 견적 `GET /scm/quotes`
- 넣는 값: `approved_amount`(만원) · `approved_qty` · `approved_unit_price` · `approved_supplier` · `approved_part_no`.
  모두 `PROTECTED_OUTPUTS` 라 task 가 낼 수 없고, 시작 변수로도 넣을 수 없다.
- 분기 조건은 `approved_amount > 300` 이다(결정 7, 시드 값 그대로). 구매팀장은 사람 task(`approval` 승인/반려) + 배타 분기다.
- 부품 · 수량 · 견적을 확정할 수 없으면 **승인을 거절**한다. 금액 없이 승인하면 팀장 분기를 건너뛸 수 있기 때문이다.
- 이유: 에이전트가 낸 금액으로 분기하면 금액을 낮춰 팀장 승인을 피할 수 있다. 금액은 서버가 ERP 견적으로 계산한다.
  그래서 scenario-research §5.C 의 6번 task(발주서 확정)는 필요 없다.
- 승인 전달(approval delivery)은 흐름이 실행할 거래를 미룬다. `payload.deferred` 에 `WO_CREATE`, 흐름에 발주 task 가 있으면 `PR_CREATE` 를 넣는다.
  예전에는 카드의 `PR_CREATE` 가 승인 즉시 실행되어 팀장 승인 전에 발주가 나갔다. 발주 task 가 없는 기준 흐름은 전과 같다(시험).
- `select` 응답에 `purchase` (위 값 + 견적)가 실린다. 승인 **전** 화면에 금액을 보이려면 U 쪽 작업이 필요하다(§8).

## 3. 정비창 → 작업지시 · 작업지시 뒤 재관측 (실행 3)

- `task:work-order` 가 처리 건 값 `maintenance_window` 를 CMMS 요청의 `window` 로 넘긴다. 값 이름은 활동의 `service.window_var` 로 바꿀 수 있다.
  받는 모양: 정비창 id `MW-…` · `{id, label, starts_at}` · 글 라벨.
  - id 이면 ERP/CMMS 가 그 설비의 다가오는 창인지 확인하고 라벨 · 시작 시각을 작업지시에 적는다(`window_id`, `window_starts_at`).
  - 값이 없으면 전과 같다(카드 id 로 '야간 정비창'/'즉시').
- 작업지시 영수증 `work_order.after.window_starts_at` 을 `svc:wait` 의 `until` 로 쓰면 "정비창까지 대기"가 된다.
- **작업지시로 닫힌 사건의 재관측**(설비 명령 없음, 사건 CLOSED):
  - 이전: `task:reobserve` 가 사건 상태만 보고 `recovered=True` 를 바로 냈다. 실제 관측이 없었다.
  - 이제: 재관측 창(15 시뮬레이션 분 ÷ 배속)을 기다린 뒤 사건 회복 기준 태그의 최신값과 경보 해제(CLEAR)를 읽는다.
  - 기준 안이고 해제됐으면 회복, 값은 기준 안인데 해제가 아직이면 창의 3분의 1씩 최대 3번 늘린다(machine 과 같은 규칙).
  - 사건 갱신 콜백도 그 사이에 회복을 내지 않는다(`instances._apply_incident_update` 보강).

## 4. 시간 — 배속과 수업 압축 (결정 4)

- 실제 대기 = 업무 시간 ÷ (`TIME_SCALE` × `PROCESS_WAIT_COMPRESSION`). 기본값 20 × 60 이다.
  - 납기 5일 → 6분, 정비창 9 h → 27초, 납기 초과 타이머 P7D → 8.4분.
- 압축은 `process:wait` · `enterprise:GR_CONFIRM` 과 **그 부품에 붙은 경계 타이머에만** 적용한다(`engine.timer_scale`).
- 설비 물리 · 감지기 · 재관측 · 사람 응답 타이머(PT10M 등)는 배속만 쓴다. CLAUDE.md §3 의 20배속 규칙을 바꾸지 않는다.
- 대기 끝 시각은 작업 행의 `draft.wait` · `due_date` 에 저장된다. 재시작해도 같은 시각에 끝나고, 폴링(2초)이 다시 본다.

## 5. ERP 재고 감시 · 수업 원인 버튼 (실행 2)

- `procsvc/business_monitor.py` 가 `ERP_STOCK_MONITOR_INTERVAL_S`(15초)마다 `GET /erp/spare_stock` 을 읽는다.
  - 조건: 가용(실물 − 예약) < 재주문점.
  - 감지기 · 사람 입력 경보와 같은 계약의 경보를 만든다: `source: "erp"`, 패턴 `SPARE_BELOW_MIN`, 설비 = 예약 설비(HYD-03), 근거 = 부품 · 가용 · 재주문점 · 필요량.
  - 경보는 같은 원천 접수 경로(`_admit_human_alert` → source_inbox → 경보 정책 → 처리 건 · 사건)로 들어간다.
- 회차: 같은 이탈은 같은 `alertId`(`ERP-SPARE_BELOW_MIN-<부품>-<below_since>`)라 처리 건이 하나다. 회복했다가 다시 내려가면 새 처리 건이다.
  해제(CLEAR) 경보는 보내지 않는다. 처리 건은 입고 확인으로 닫힌다.
- 이 패턴을 받는 배포 흐름이 없으면 기준 흐름의 `unsupported` → 사람 검토(alert_triage)로 간다. 기존 규칙과 같다.
- 흐름 가져오기의 경보 패턴 목록에 `SPARE_BELOW_MIN` 이 보인다(`catalog.business_patterns`). 회복 기준 계약은 `ERP_SPARE_BELOW_MIN < 1`(이탈 표시)이다.
- 새 감시 규칙(예: 정비 주기 도래)은 `MonitorRule`(읽을 이름 · 조건 · 회차 · 대상 · 설비 · 근거) 하나와 `PATTERNS` 계약 하나로 붙는다.

**수업 원인 버튼 (U 에이전트가 고장 모사 화면에 붙일 API)**

| 방법 | 주소 | 본문 | 결과 |
|---|---|---|---|
| POST | process `/api/simulate/spare-issue` (= enterprise-sim `/erp/spare/issue`) | `{"part_no": "P-PMP-SEAL", "qty": 1, "asset": "HYD-03", "by": "<누가>", "reason": "<사유>", "request_id": "<선택: 재전송 중복 방지>"}` 모두 선택, 기본 씰 키트 1개 | `{"transaction": {ref: "GI-…", detail}, "stock": {facts: {available, reorder_point, below_reorder_point, need_qty, …}, movements}}` · 재고 부족은 400 |
| POST | process `/api/simulate/spare-reset` (= `/erp/spare/reset`) | `{"part_no": "<선택>"}` | 기준 재고로 복원, 재고 이동에 RESET 기록 |
| GET | process `/api/simulate/spare-stock?part=` (= `/erp/spare_stock`) | — | 재고 · 최근 이동 20건 |

기준 재고는 씰 키트 실물 4 · 예약 2(HYD-03 예방 교체) · 재주문점 2 · 목표 7 이다. 출고 1개 → 가용 1 < 2 → 다음 주기에 C 처리 건이 열린다(필요량 6).
정비 수행 모사가 작업지시(SOP-PMP-04)를 완료해도 씰 키트 1개가 소모된다(정비 → 구매로 이어지는 자연 경로).

## 6. 업무 DB · 시스템 (마이그레이션 `it/supabase/migrations/20261009000045_c2_execution.sql`)

추가만 했다. 다시 적용해도 안전하다(if not exists · on conflict · create or replace, 두 번 적용 확인).

| 무엇 | 표 · 함수 |
|---|---|
| 예비품 재고 · 이동 원장 | `ent.spare_stock`(실물 · 예약 · 입고 예정 · 재주문점 · 목표 · `below_since`), `ent.stock_movements`(ISSUE · CONSUME · RECEIPT · RESET) |
| 부품별 견적 | `ent.part_quotes`: 씰 키트 sup:a 35/0.12/2 · sup:b 55/0.02/5 · sup:c 20/0.30/1(비AVL), 팬 베어링 sup:a 18 · sup:b 28. 온톨로지 SUPPLIED_BY 와 같다. 쿨러 코어는 `ent.suppliers` 를 그대로 읽는다(`ent.quote_rows`) |
| 정비창 | `ent.maintenance_window_rules`(야간 +9 h/24 h/4 h · 주말 +105 h/168 h/24 h, 설비별) → `ent.next_maintenance_windows(asset, n)`. id 는 `MW-<설비>-<N\|W>-<UTC 시작>` |
| 발주 · 입고 | `purchase_requests` + `part_no · qty · unit_price · amount · lead_d · expected_at · received_at`, `ent.goods_receipts` |
| 작업지시 · 일정 · 기록 | `work_orders` + `window_id · window_starts_at · completed_at`, `ent.cmms_calendar`, `ent.case_records` |
| 읽기 RPC | `ent.spare_stock_read`, `ent.part_quotes_read`, `ent.maintenance_windows_read`, `ent.purchase_order_read` (전용 읽기 계정 허용) |
| 실행 `ent.exec_skill` | `procure-part` 에 부품 번호가 있으면 견적 · AVL · 금액(=단가×수량)을 재확인하고 입고 예정을 올린다. 새 스킬: `receive-goods` · `complete-maintenance` · `calendar-entry` · `record-case` · `issue-spare` |
| 초기화 | `ent.reset_spare_stock(part)`, `reset_executions`(새 표 포함) · `reanchor_scenario_times`(정비창 규칙 포함) |

- 메모리 백엔드(`entsim/data.py` · `state.py`)도 같은 규칙 · 같은 응답 모양이다.
- enterprise-sim 새 HTTP: `GET /erp/spare_stock`, `GET /scm/quotes`, `GET /cmms/windows`, `GET /erp/purchase_orders/{ref}`, `POST /erp/spare/issue`, `POST /erp/spare/reset`.
- enterprise-mcp(에이전트 읽기)에 읽기 도구 3개를 더했다: `spare_stock` · `part_quotes` · `maintenance_windows` (모두 readOnlyHint=true, 도구 13개).
- plant-sim `POST /api/fault {type: restore, component}`: 부품 하나만 복구한다(cooler · pump · fan · comp:*). 없으면 전과 같이 전체를 복구한다.

## 7. 설정 키

| 키 | 기본 | 어디 |
|---|---|---|
| `PROCESS_WAIT_COMPRESSION` | 60 | process — 기다리는 부품과 그 타이머의 수업 압축 |
| `PLANT_SIM_URL` | `http://host.docker.internal:8000` | process — 정비 수행 모사. plant-sim 은 ot-net 에만 있어 호스트 공개 포트로 간다(실습 도구, PLC 명령 경로 아님) |
| `EFFECT_MCP_SERVERS` | `{"hyd-effects": {"type":"url","url":"http://effects-mcp:8197/mcp"}}` | process — 승인 뒤 MCP 서버. 없는 이름은 `tenants.mcp` 에서 검사 통과한 서버 |
| `ERP_STOCK_MONITOR` · `ERP_STOCK_MONITOR_INTERVAL_S` | 1 · 15 | process(instance 모드) — 재고 감시 켜기 · 주기 |
| `EFFECTS_SMTP_HOST` · `EFFECTS_SMTP_PORT` | `host.docker.internal` · 54325 | effects-mcp — Inbucket |
| `it/supabase/config.toml [inbucket] enabled` | true | 다음 `supabase start` 부터 메일함이 뜬다 |

compose: 새 서비스 `effects-mcp`(profile `process`, 8197, 볼륨 `effects-data`), process 환경변수 추가. `.env.example` 에도 적었다.

## 8. BPMN 에 쓰는 법 (C 모양, 시험 `tests/test_c2_execution.py` 의 그림과 매핑 그대로)

```
시작(메시지, 패턴 SPARE_BELOW_MIN) → 진단 → 후보 → 규정 → 제안(task:rank) → 제안 승인(task:select)
 → G 300만 원 초과?  [approved_amount > 300] → 금액 초과 추가 승인(사람 task, 구매팀장, 폼 approval: 승인|반려) → G 승인? [approval == '승인'] → ERP 발주
                     [그 밖] ────────────────────────────────────────────────────────────────────────────────→ ERP 발주
                                                                                              [그 밖] → 끝(팀장 반려)
 → ERP 발주(svc:erp-po) → 공급사 메일(svc:mcp-call send_mail) → 입고 확인(svc:goods-receipt, 경계 타이머 P7D → 끝(지연 통보)) → 끝(입고 완료)
```

메일 config 예:

```json
{"server": "hyd-effects", "tool": "send_mail",
 "arguments": {"to": "supplier@hyd.local", "subject": "[발주] {approved_part_no} {approved_qty}개",
               "body": "공급사 {approved_supplier}, 금액 {approved_amount}만원, 발주 번호 {purchase_order.ref}"}}
```

정비 모양:

```
… → 승인 → task:work-order → svc:wait(until work_order.after.window_starts_at) → svc:maintenance(component, sop)
  → task:reobserve → G recovered == True → 끝 / 상급자
```

`maintenance_window` 는 앞 에이전트 task 의 결과 값이다(정비창 id).

## 9. 시험

- 단위: `tests/test_c2_execution.py` 17개, `tests/test_c2_parts.py` 20개.
  - 가져오기 → 등록 · 배포 → 실제 런타임(MemoryRepo · 실제 Incident 상태기계 · 승인 경로)으로 끝까지 돈다.
  - 금액 분기 양쪽, 팀장 반려, 수량 모름 승인 거절, 납기 초과 타이머, 승인 기록 없는 효과 거절, 정비창 전달 · 대기 · 정비 모사 · 실제 재관측(회복 · 미회복 · 해제 대기 연장)을 본다.
  - 부품 계약 · 재고 감시 회차 · 감시 규칙 끼우기 · 메모리 업무 시스템(출고 · 발주 거절 3종 · 입고 · 소모 · 정비창 · 초기화 · HTTP 버튼)도 본다.
  - hyd-effects 멱등 · 주소 검사 · 업무 실행 키, 승인 뒤 MCP 클라이언트(쓰기 도구 호출, 포털 경로는 거절), 대기 압축, 시뮬레이터 부품별 복구, 사건 업무 효과 종결, CMMS 정비창 인자도 본다.
- 바꾼 기존 시험 2개: 에이전트 도구 수 25 → 28(`test_mcp_check`), enterprise-mcp 도구 10 → 13(`test_a144_mcp_worker`).
- 전체: `.venv/bin/python -m pytest -q` → **1733 passed, 4 skipped, 실패 1**. 실패는 `test_mcp_check.py::test_html_page_is_not_an_mcp_endpoint` 이다.
  기존 흔들림으로 보고, 같은 파일만 다시 돌리면 32 passed 다. C2 전 기준선 1697 passed 에서도 `-x` 실행 한 번에 같은 실패가 났다(`.evidence/a161-c2/pytest-baseline.txt`).
- 업무 DB:
  - `scripts/c2_scratch_db.sh`: 실행 중인 로컬 Supabase 안에 버리는 DB `c2_check` 를 만들고, 마이그레이션 26개 + seed 를 적용한다. 공유 DB 는 건드리지 않는다.
  - `scripts/c2_sql_smoke.sql` 결과는 `.evidence/a161-c2/sql-smoke.txt` 에 있다.
- 라이브: `scripts/c2_live_in_container.sh` → `scripts/c2_live_check.py`. 결과는 `.evidence/a161-c2/live-check.json` · `live-check.log` · `live-mail.eml` 이다.
  - 버리는 DB 위에 enterprise-sim(Supabase 백엔드) · effects-mcp · SMTP 받는 곳을 Supabase 망 안의 임시 컨테이너에서 띄웠다.
  - 1 출고 버튼 → 2 재고 감시 경보 1건, 같은 회차 0건
  - 3 승인 금액 330
  - 4 비AVL 거절 · 발주
  - 5 MCP 메일 1통 수신, 재호출은 replayed · 일정 · 기록, 포털 경로 거절
  - 6 입고 → 재고 9/가용 7
  - 7 enterprise-mcp 읽기
  - 끝나면 임시 역할 · DB 를 지웠다.
  - 호스트에서 54322 로 붙는 비밀번호 인증이 이 PC 에서 실패해서(로그에 시도가 남지 않음) 컨테이너 안에서 돌렸다.

## 10. 참고 구현 대조 (ProcessGPT 로컬 모노레포 `/Users/uengine/process-gpt/services`, 읽기만)

| 설계 선택 | 따른 참고 (파일:줄) 또는 HYD 자체 |
|---|---|
| 서비스 task 도달 → SUBMITTED → 엔진이 실행, 결과는 output → 다음 | `completion/polling_service/workitem_processor.py:1893-1903`(_check_service_tasks) · `:5293-5317`(연속 서비스 task SUBMITTED) · `polling_service.py:40-70`(타입별 분기) — 같은 모델 |
| 기다리는 부품: 행에 끝 시각(due_date) 저장, 폴링이 도래 시 완료 · 경계 타이머 압축 | 제품은 `due_date` 계산 · 저장만(`workitem_processor.py:1395-1398`, `database.py:944`)하고 시간 경과로 진행시키는 루프가 없다 → **HYD 자체**(수업에서 정비창 · 납기를 실제로 흘려야 함) |
| 승인 뒤 MCP 호출, 서버 설정 = `tenants.mcp.mcpServers`, 인자 틀 치환 | `completion/polling_service/mcp_processor.py:64-74,111-126`(tenants.mcp 읽기), `completion/compensation_handler.py:15-40`(Template.substitute → call_tool) — 같은 방향. 제품은 LLM 이 도구를 고르고, HYD 는 정의가 도구 · 인자 틀을 고정한다(결정론, 승인 뒤만) |
| 도구 호출 이벤트 `tool_usage_started/finished`(본문 tool · tool_name · args · result · is_error) | 이벤트 이름 enum `frontend/docker-compose/volumes/db/init.sql:101-102`, 본문 `n8n-agent/executor.py:224,232`. 제품 최신은 MCP 전용 `mcp_call_*` enum(`frontend/supabase/migrations/20260901b_mcp_observability.sql:12-17`) — HYD enum 에 없어 보류(§11) |
| 읽기/쓰기 구분 readOnlyHint, 연결 검사 | `mcp-hub/src/mcp_hub/conformance.py:25-26`(힌트 명시 규칙), `mcp-validator/src/mcp_validator/validator.py:92,170`(initialize) — 힌트로 실행을 막는 것은 **HYD 자체**(B2 규칙) |
| 실패 3회 재시도 뒤 PENDING · 사유 보존 | `completion/polling_service/polling_service.py:78-95` 3회 재시도. 제품은 3회 뒤 DONE, HYD 는 PENDING(REFERENCE_ADOPTION 기존 결정) |
| 외부 효과 멱등 키(decision+skill, MCP idempotency_key) | 제품에 없음(`idempot` 0건) → **HYD 자체**(재시도 때 발주 · 메일이 두 번 나가지 않게) |
| 참여자 알림 `notifications` 삽입 | 열 이름 `frontend/docker-compose/volumes/db/init.sql:1105-1125`. 제품은 DB 트리거가 넣고 HYD 는 앱이 넣는다(기존 inbox.py 와 같은 방식) |
| 분기 조건 = 변수 위 식 평가 | `workitem_processor.py:2338,2394`(conditionFunction 평가). 승인 값(금액)을 서버가 결정론으로 넣는 것은 **HYD 자체**(제품은 LLM mapper, `:924`) |
| 업무 데이터 감시가 처리 건을 연다 | 제품에 없음(스케줄러 · 트리거 시작 0건) → **HYD 자체**(TODO C "시작은 자동") |
| 되돌릴 수 없는 거래 사유 목록 | 제품은 되돌리기 때 보상 코드를 생성(`completion/compensation_handler.py:223`). 불가역 목록 노출은 **HYD 자체**(기존 effect_compensation 에 C2 거래 사유를 보탬) |

## 11. 하지 않은 것 · 열린 것

1. **공유 Supabase(postgres DB)에는 마이그레이션을 적용하지 않았다.** 다른 에이전트가 스택을 쓰고 있다.
   C3 가 적용하는 방법은 둘이다. 다시 적용해도 안전하다.
   - `docker exec -i supabase_db_hyd-iot-edu psql -U postgres -v ON_ERROR_STOP=1 < it/supabase/migrations/20261009000045_c2_execution.sql`
   - 또는 `supabase db reset`
2. **effects-mcp 이미지 빌드 · 기동, Inbucket 켜기(Supabase 재시작 필요), process 재배포는 하지 않았다.** compose 를 건드리지 말라는 지시 때문이다. C3 가 할 일이다.
3. **Linux 클라우드에서 `PLANT_SIM_URL`**: plant-sim 포트가 `127.0.0.1:8000` 에만 열려 컨테이너에서 닿지 않을 수 있다.
   이 경우 정비 수행 모사가 사유를 남기고 실패한다(3회 뒤 PENDING). Docker Desktop(맥 · 윈도)은 닿는다.
   수업 서버에서는 plant-sim 포트를 호스트 게이트웨이에 열거나 시뮬레이터 조작 중계가 필요하다(아키텍처 결정이라 손대지 않음).
4. **C 반려 경로의 사건**: 팀장 반려로 처리 건이 끝나도 사건(Incident)은 승인 대기로 남는다. 입고 확인만 사건을 닫는다.
   반려 종결을 사건에 반영할지(예: `machine.on_reject`)는 C3 · 사용자가 정한다.
5. **승인 전 금액 보이기**: 금액은 승인 순간에 확정되어 `select` 응답 · 처리 건 값으로 나온다.
   카드별 예상 금액을 승인 화면에 미리 보이는 미리보기 API · UI 는 없다(U 에이전트 몫). 에이전트가 같은 견적(`part_quotes`)으로 카드 설명에 적을 수는 있다.
6. B 전용 시작 패턴(`PUMP_DEGRADATION_EARLY`) · B 데이터 · 정비 주기 도래 감시는 만들지 않았다(B 재정의 대기). 감시는 규칙 하나로 붙는다(§5).
7. 에이전트 시험 실행 시나리오 목록 확장(X11)과 시나리오별 MCP 도구 거르기(X12)는 C3 몫이다.
8. 제품 최신 MCP 관측 이벤트(`mcp_call_started/finished/failed`)는 HYD `event_type_enum` 에 없다. 그래서 `tool_usage_*` 를 쓰고 본문 키만 제품에 맞췄다.
9. 고친 기존 결함 하나: 경계 타이머가 **끝 이벤트로 바로** 가는 흐름(납기 초과 → 지연 통보)이 끝나지 않았다.
   발화 처리에서 타이머 행 사본이 IN_PROGRESS 로 남았기 때문이다(`instances._fire_timeout`). 기준 흐름은 타이머 → 사람 task 라 드러나지 않았다.

## 12. C3 조립 에이전트가 알아야 할 계약

- 시작: ERP 경보 `{alertId: "ERP-SPARE_BELOW_MIN-<부품>-<시각>", asset: "HYD-03", pattern: "SPARE_BELOW_MIN", source: "erp", evidence: {part_no, available, reorder_point, target_stock, on_order, need_qty, below_since}}`.
  처리 건 값 `alert.evidence` 로 읽힌다. 흐름 가져오기에서 경보 패턴 `SPARE_BELOW_MIN` 을 고른다.
- C 카드: 발주 SOP 스킬은 `PR_CREATE` 동작(값 = 공급사 id, `sup:a|sup:b|sup:c`)을 가져야 금액이 확정된다(온톨로지 `CONSISTS_OF {value: sup:x}` 그대로).
  수량은 에이전트 결과 `need_qty`(에이전트 task 출력 이름을 `need_qty` 로)가 먼저, 없으면 경보 근거 `need_qty` 다.
- 분기: `approved_amount > 300` → 구매팀장 사람 task(역할은 users 에 `role:purchasing-mgr` 가 있어야 카탈로그 역할 목록에 뜬다 — C1 시드 몫).
- 정비 시점: 에이전트 결과 값 `maintenance_window` = `maintenance_windows` 도구의 id. 작업지시 → `svc:wait until work_order.after.window_starts_at`.
- 메일 주소는 config 의 인자 틀에 적는다. 수업에서는 Inbucket 이 모든 주소를 받는다.
- 원인 버튼: `POST /api/simulate/spare-issue` (§5 표).
