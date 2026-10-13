# 기존 조치의 효과 보상과 확인 — 재작업 전에 해결하기

재작업(새 작업 세대)은 이전 세대의 결과를 이력으로 남기고 다시 판단한다. 그런데 이전 세대가 이미 바깥 세상을 바꿨을 수 있다. 설비에 명령이 나갔고(PLC ACK), CMMS 에 작업지시가 생겼고, ERP 에 구매요청이 올라갔다. 이 문서는 그 효과를 어떻게 다루고 언제 재작업을 허용하는지 정한다.

## 원칙

제품(process-gpt-completion `compensation.py`)은 관측된 작업 이력에서 **되돌릴 수 있다고 증명되는 행위만** 정확히 역순으로 되돌리고, 하나라도 못 되돌리면 되돌리기를 저장하지 않고 재작업 전체를 에이전트에게 넘긴다. "절반만 되돌린 세상은 되돌리지 않은 세상보다 나쁘다." HYD 도 같은 규칙을 세 종류의 효과에 적용한다.

| 효과 | 처리 | 근거 |
|---|---|---|
| 업무 거래 중 기업 시스템이 **정확한 역거래**를 제공하는 것 — 작업지시(`skill:schedule-maintenance` → `skill:cancel-work-order`), 구매요청(`skill:procure-part` → `skill:cancel-purchase-request`), 오더 이관(`skill:reallocate-production` → `skill:restore-production`), 로트 격리(`skill:hold-lot` → `skill:release-hold`) | **보상**: 원거래 참조로 역거래를 요청한다. 레코드가 생성 상태를 벗어났으면(작업 착수, 발주 완료 …) 기업 시스템이 거절하고, 그 효과는 "되돌릴 수 없음"으로 바뀌어 사람 확인 대상이 된다 | enterprise-sim `state.py` `INVERSE_OF`, Supabase `ent.exec_compensation` |
| 되돌릴 수 없는 업무 거래 — 출하 승인, 대체 출하, 수요 제어 | **사람 확인**: 담당자가 효과를 보고 확인 영수증을 남긴다. 시스템은 아무것도 되돌리지 않는다 | `IRREVERSIBLE` 목록 |
| **설비 명령**(cmdId · 조치 · ACK) | **사람 확인 + 사건 재개**: 자동 역명령을 보내지 않는다. 담당자가 현재 설비 상태를 확인하고 영수증을 남기면, 재작업 시작 시 사건(Incident)이 승인 대기로 다시 열리고 이전 명령은 `superseded` 이력으로 남는다 | `machine.on_rework_reopen` |
| 원장이 확인하지 않는 기록 — 실패한 로컬 실행, 원장에 없는 작업지시 참조, 접수가 불명확한 CMMS 요청, 명령 ID 없는 조치/응답 | **사람 확인** (불명확한 기록을 자동으로 "효과 없음"으로 취급하지 않는다) | `effect_compensation.inventory` |

재작업 미리보기는 모든 효과가 **보상 영수증(기업 원장의 역거래)** 또는 **확인 영수증** 으로 해결됐을 때만 `execution_available` 이 된다. 해결되지 않으면 `effects_require_compensation_or_review` 로 보류한다. 설비 응답을 기다리는 명령(AWAITING_ACK)은 응답이 올 때까지 `incident_command_in_flight` 다. 종료된 사건(ESCALATED · CLOSED · 자연 회복 · 운전원 거부)과 해제된 경보는 다시 열지 않는다.

## 운영 흐름

1. 인스턴스 상세의 **기존 조치의 효과** 패널(또는 `GET /api/instances/{id}/effects`)에서 효과 목록·처리 방법·해결 상태·영수증을 읽는다. 조회는 상태를 바꾸지 않는다.
2. 되돌릴 수 있는 거래가 있으면 **보상 요청** (`POST /api/instances/{id}/effects/compensate`, body `request_id`(UUID)·`by`·`role`·`reason`, 선택적으로 `effects` 목록). 담당 역할은 정의의 사람 업무 역할이면서 **기존 승인 역할 이상**이어야 한다. 영수증은 PENDING 으로 먼저 저장되고 기업 시스템 호출 뒤 DELIVERED 또는 FAILED 가 된다. 실패해도 영수증과 오류가 남으며, 같은 `request_id` 로 재전달하면 남은 항목부터 이어간다. 다른 내용으로 같은 ID 를 쓰면 409.
3. 되돌릴 수 없는 효과(설비 명령 포함)는 체크해 **확인 기록** (`POST …/effects/review`, body 에 `effects` ID 목록 필수). 되돌릴 수 있는 거래를 확인으로 넘기려 하면 거절한다. 확인 영수증에는 그 시점의 사건 상태·명령·응답이 함께 남는다.
4. 작업 다시 수행에서 영향 범위를 다시 조회한다. 효과가 모두 해결됐고 사건이 승인 대기가 아니면 `reopen_incident: true` 가 표시된다. 새 세대를 요청하면 같은 거래 안에서 사건이 재개되고(이전 명령·작업지시는 `superseded` 로 보존), 이전 승인은 효과 요약과 함께 폐기(DISCARDED)되며, 새 에이전트 작업이 시작된다. 새 조치는 다시 사람 승인을 거쳐 설비로 간다.
5. 재개된 사건이 새 세대의 조치 전에 끝나면(경보 자연 해제 → `RESOLVED_WITHOUT_ACTION`, 운전원 거부, 에스컬레이션) 세대 0과 같은 A074 결말이다: 새 세대의 열린 작업을 취소하고 `task:escalate` 검토에서 사람이 결과를 기록해 `ev:escalated` 로 끝난다. "조치 전" 판정은 사건이 지금 섬기는 세대 기준이다 — 사건에 현재 `cmdId` 가 있으면 조치이고, 없으면 현재 세대의 제어 경로 행만 센다. `superseded` 로 물러난 이전 명령은 확인 영수증과 사건 이력에 그대로 남고 새 세대의 조치로 세지 않는다(`instances._command_never_issued`, A156 55번 INC-1008-04-ea38).

## 영수증

`public.process_effect_receipt`(migration 20261005000016): tenant · 인스턴스 · `request_id` 로 유일. `kind=compensation` 은 PENDING → DELIVERED | FAILED, `kind=review` 는 RECORDED 로 불변. 요청 내용과 효과 스냅숏은 트리거로 변경이 막힌다. 기업 쪽 역거래는 `ent.transactions` 에 `compensates`(원거래 ID)와 함께 남고 `(decision, skill, ref)` 로 멱등하다.

## 지원 범위와 한계

- 보상은 기업 시스템이 역거래를 제공하는 네 가지에 한한다. 새 거래 종류를 추가할 때는 역거래를 함께 정의하거나 `IRREVERSIBLE` 에 넣어야 한다. 양쪽 표는 단위 테스트가 대조한다.
- 설비 명령은 어떤 경우에도 자동으로 되돌리지 않는다. 사람 확인은 "설비 상태를 보았다"는 기록이지 설비가 원래대로 돌아갔다는 보장이 아니다.
- 역거래의 실제 업무 의미(취소된 작업지시의 후속, 발주 취소 통지)는 기업 시스템의 책임이며 이 목업은 상태 변경과 원장 기록만 한다.
- 실제 검증 범위는 HANDOFF §9 A072 에 적는다. 단위 테스트(메모리 저장소·가짜 기업 호출)와 실제 PG/HTTP 검사를 구분한다.

## 실제 검증과 거기서 고친 것 (2026-10-06)

`scripts/probe_effect_compensation.py`(`.evidence/reaudit/a072-live-5/`, 후속 포함 22검사)로 실제 쿨러 고장 → 팬 단독 카드 승인 → 실제 PLC ACK → 효과 조회 → 재작업 차단 → 확인 영수증 → Incident 재개 → 세대 1 새 판단(실제 DMN MCP, 대역 워커) → 새 승인 → 두 번째 PLC ACK → 실제 CMMS 작업지시로 종결, 그리고 실제 Supabase 백엔드에서 그 작업지시의 역거래(1회·멱등 재전달·상태 변경 후 거절·원장 `compensates`)를 확인했다. Codex/Claude Code 실행은 아니다.

- 영수증 응답은 저장된 행이다. 첫 응답과 같은 `request_id` 재전달 응답은 `created_at`/`updated_at`까지 같다.
- Incident 타이머(ACK 30 s, 재관측 45 s)는 그것을 건 명령에 묶인다. 재작업으로 명령이 `superseded` 된 뒤 발화하는 타이머는 `TIMER_IGNORED` 감사만 남기고 새 명령의 창을 판정하지 않는다.
- 승인은 판단 시점 예측과 승인 시점 예측의 차이를 재검사한다. 시간이 지나면 `decision-preview` 로 현재 조건을 다시 검토한 뒤 `review_id` 와 함께 승인해야 하며, 이는 보상과 무관한 기존 계약이다.
- Execution 그래프 투영은 outbox 가 PG 행 뒤에 적용한다. 종결 직후 한 번 읽은 그래프가 행과 다를 수 있으므로 검사기는 수렴을 기다린다.
