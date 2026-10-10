# F-keep — 원래 흐름 유지 + 승인 단계 일관화 (2026-10-10 밤)

갈래 `F-20261010-keep`(작업 트리 `.claude/worktrees/F-20261010-keep`, 출발 커밋 214025d, 구현 커밋 c4920d7).

## 합칠 때 옮길 것
### 사용자 결정 (2026-10-10 밤, 감독 전달 두 건)
1. 실라버스 8~10일차에 맞춰 넣었던 프로세스 변경(`F-20261010-syllabus`, 5f67aec)은 **채택하지 않는다** — 원래 결정(DECISIONS 112, NOW.md 0.1) 유지. 세 시나리오는 "버튼 → 처리 건 → 에이전트 추천 1개 → 사람 승인 1회 → 시스템 처리 → 자동 확인 → 결과"로 끝나고, B · C 는 설비까지 가지 않는다. 그 브랜치는 기록으로만 남긴다.
2. **승인 단계는 세 시나리오가 똑같다**: 담당자가 승인하거나 거절한다. 승인하지 않으면 그 단계에서 그대로 기다리고(자동 취소 · 자동 거절 없음) 기한이 지나면 지연 알림만 나간다. 거절하면 처리 없이 반려로 닫힌다. A 의 승인 뒤 조치 · 유온 재확인은 원래 그대로.

## 1. 한 일 (커밋 c4920d7 — 원래 코드 위에 필요한 것만 올림, 되돌리는 커밋 없음)
- `scripts/c3_flows.py`: A · B · C 에 같은 승인 단계(`approval_xml` · `approval_tasks`) — 부품 `task:select-or-reject`, 멈추지 않는 경계 타이머 「승인 지연」(`PT10M`, 세 흐름 같은 값) → 알림 보고 → `E_notice`, 분기 「승인?」: 승인(`approval == '승인'`) → 원래 처리, 거절(그 밖) → 결과 보고(반려) → `E_rejected`. 정상 끝은 원래대로 `E_end`. 흐름 이름 · 나머지 모양은 원래대로(B = 정비 오더 등록 · 공지 메일 → 보고, C = 발주 · 메일 → 바로 입고 → 보고).
- 조치 카드 거절(5f67aec 에서 가져옴): `bpmn_import.py`(부품 `task:select-or-reject`, 사전 검사 — 반려 경로가 효과 부품에 닿음 · 경보 흐름의 반려 경로가 결과 보고(반려) 없이 끝남 · 두 승인 부품 섞기), `instances.py`(`reject_card`, 승인 때 `approval: 승인`), `instance_mode.py`(`POST /api/todolist/{id}/reject-card`), `approval_hooks.py` · `decisions.py`(거절 권한 = 그 판단의 안을 하나라도 승인할 수 있는 역할). 사건은 결과 보고(반려)가 기존 `REJECTED_BY_OPERATOR` 로 닫는다. 기존 `task:select`(승인만) · 기준 정의는 그대로.
- 거절 뒤 업무 표시: 표시를 끄는 것은 정비 오더(B) · 입고(C)뿐이라 거절하면 켜진 채 남는다(코드 · 단위 시험 · 라이브로 확인). 끝난 처리 건은 진행 중이 아니므로 버튼으로 새 처리 건을 열 수 있다.
- 실라버스와 무관한 결함 수정: 발주 카드에 붙던 `window: 즉시 (지금 정지하고 시행)` 제거(`it/agent/agentsvc/cards.py option_window` — 정비 작업지시가 있는 작업지시 카드만).
- 가져오지 않은 것(= 되돌린 것): B · C 의 예약 대기 · 정비 · 시운전 · 메일 분리 · 입고 대기 · 입고 대조, 조치 미달 · 시운전 미달 · 납기 초과용 수업 입력 3개와 plant-sim 의 `fan_drive_fault` · `maintenance_defect` · `operating_point`, `class_inputs`, 시나리오 이름 변경, B [초기화]의 설비 복구, 처리 기록의 인계 값 줄. `tests/test_c3_bc_simplified.py` 는 살아 있다(승인 단계 task · 타이머 · 분기 수만 갱신).

### 5f67aec 안에 있던, 실라버스와 무관해 보이는 결함 수정 — 남기지 않고 보고만
- **A 를 승인으로 끝낸 뒤 [쿨러 복구]를 눌러도 팬 지령이 100 % 로 남아 다음 [쿨러 열화 주입]이 경보를 내지 못한다**(moderate 열화의 평형이 49.8 ℃). 원래부터 있던 문제다. 5f67aec 에서는 plant-sim `operating_point` 로 고쳤는데 되돌릴 목록에 들어 있어 가져오지 않았다. 지금은 A 를 다시 돌리려면 설비 `POST :8000/api/reset` 이 필요하다. 남길지 결정 필요.
- `svc:wait` 가 승인한 카드가 '즉시'일 때 예약 시각 대기를 건너뛰는 처리(지금 수업 흐름은 `svc:wait` 를 쓰지 않아 영향 없음) — 가져오지 않음.

## 2. 시험
- 새 `tests/test_approval_stage.py`(21개): 세 흐름 각각 승인 → 정상 끝 / 거절 → 반려 끝(설비 명령 · 업무 처리 0건, 사건 '운전원 거부', 판단 REJECTED) / 무응답 → 지연 알림 뒤에도 승인 대기(5시간 뒤에도 그대로) → 알림 뒤 거절 · 승인 가능. 거절 뒤 B · C 표시 켜짐과 새 처리 건 열기, 거절 권한 · 사유 · 두 번 거절 · 거절 값 없는 흐름, HTTP 경로(422 · 403 · 404 · 400), 사전 검사(세 흐름), 세 흐름의 승인 단계가 같은 모양.
- 뮤테이션 11개 모두 잡음(거절이 승인 값을 냄 · 권한 검사 없음 · 승인 값 누락 · 승인 값 안 비움 · 판단 미표시 · 사전 검사 두 종 무력화 · 지연 타이머가 승인을 끊음 · B/C 에 거절 없음 · 지연 기한이 다름 · 구매 카드에 즉시 창).
- 전체: **2097 통과 · 9 건너뜀 · 0 실패**(207초, 루트 `.venv`).

## 3. 라이브 (23:00 ~ 23:23, 잠금 F-20261010-keep) — 검증됨
- 올린 것: `process` · `agent` · `plant-sim` 을 이 작업 트리 코드(c4920d7)로 다시 빌드 · `up -d --no-deps`. 올린 뒤 확인: `/api/scenario/status` 버튼 이름 '정기 점검' · '재고 보충', `class_inputs` 없음, plant-sim 상태에 `fan_limit` 없음(= 원래 동작). process StartedAt 14:00:22Z · RestartCount 0(끝까지 같음). compose 작업 폴더는 네 컨테이너(process · agent · plant-sim · neo4j) 모두 이 작업 트리 — `F-20261010-syllabus` 를 가리키는 컨테이너 없음.
- 순서: 그래프 구조판 → `c3_flows.py deploy`(세 흐름 판 8) → 워커 1개(opus) → `scripts/approval_stage_live.py <경우>`. 화면 조작 없이 포털 버튼과 같은 process API 로 눌렀다(포털에 [거절]이 없음).
- 증거 `<루트>/.evidence/a163-restore/`: 경우마다 `*-at-approval.json` · `*-final.json` · `*-checks.json` · `*.log`(+ `B-wait-while-waiting.json`), `worker.log`, `reg-cooler.log`.

| 경우 | 처리 건 | 결과 | 확인 |
|---|---|---|---|
| A 승인 | `c3_cooling.06582d0a…` | `E_end` · 정상 "유온 정상 · 경보 해제, 작업지시 WO-1010-B07F", 명령 id 있음 · 재확인 회복, 사건 CLOSED | 10/10 |
| A 거절 | `c3_cooling.c9544798…` | `E_rejected` · 반려, 사건 REJECTED_BY_OPERATOR, 설비 명령 0건 | 11/11 |
| B 승인 | `c3_pm.85fb0ede…` | `E_end` · 정상 "정비 오더 WO-1010-64D9 등록 · 생산팀 공지", 표시 꺼짐 | 8/8 |
| B 거절 | `c3_pm.1d1a9933…` | `E_rejected` · 반려 "정비 오더를 내지 않았습니다", 표시 켜진 채 | 10/10 |
| B 무응답 → 거절 | `c3_pm.54412a37…` | 승인 대기 30초 뒤 지연 알림, 그 뒤 20초 더 두어도 처리 건 RUNNING · 승인 task 대기 · 사건 승인 대기 · 처리 0건 → 거절로 닫음 | 13/13 |
| C 승인 | `c3_spare.eb8e126d…` | `E_end` · 입고 완료 "씰 키트 6개 입고 · 검수 합격", 표시 꺼짐 | 9/9 |
| C 거절 | `c3_spare.19d18e9b…` | `E_rejected` · 반려 "발주하지 않았습니다", 표시 켜진 채 | 11/11 |
- 워커 한도(RunFailed) 없음.
- 쿨러 회귀: 기준 복원(흐름 `deploy-reset` → 그래프 원래 볼륨 → 설비 reset) 뒤 `scenario_instance_test.py --worker` → **ALL PASS 40/40**, exit 0.
- **보지 않은 것**: 포털 화면(반려 결과 · 지연 알림이 어떻게 보이는지, 캡처 없음), 무응답은 B 한 건만(A · C 는 단위 시험만), pump-fan 회귀.

### 끝난 뒤 스택 (쉬는 상태)
그래프 = 전체판(`hyd-iot-edu_neo4j-data`), 흐름 = 기준 흐름(c3 세 흐름 판 8 은 등록돼 있고 경보 경로에서 내림 — 다음 `c3_flows.py deploy` 는 이 갈래의 승인 단계가 든 판을 올린다. 작업 브랜치의 `c3_flows.py` 로 배포하면 거절 · 지연 알림이 없는 옛 판이 된다), 워커 0, RUNNING 0, B · C 표시 켜짐, 설비 세 대 정상. **process · agent · plant-sim · neo4j 컨테이너의 compose 작업 폴더는 이 작업 트리(c4920d7)** — 스택을 루트로 옮기기 전까지 이 작업 트리를 지우지 않는다. `before-f-syllabus` 꼬리표 이미지(오늘 낮 빌드)는 남아 있다. 회귀의 `/api/reset` 이 라이브 완주의 업무 행을 보관 표로 옮겼다. 작업 트리의 `.env` 사본 지움, 잠금 지움.

## 4. 포털 작업자에게 넘길 것 (`it/portal/www/**` 미수정)
- **세 시나리오 승인 패널에 [거절] + 사유**(`instances.js renderSelectPanel`): `POST /api/todolist/{workitem_id}/reject-card` body `{decision, by, role, reason}`(reason 1~2000자). 200 `{approval: "반려", rejected: true, …}` · 400(공백 사유 · 이미 처리 · 거절 값을 내지 않는 흐름 · 판단 불일치) · 403(권한) · 404 · 422(reason 누락). 권한: `by` 가 `user:*` 면 `role` 구성원이어야 하고, `role` 은 그 판단의 안을 하나라도 승인할 수 있는 역할 — 승인할 수 있는 사람이 거절도 할 수 있다. 그 단계가 거절을 받는지는 흐름 정의의 그 활동 `outputData` 에 `approval` 이 있는지로 안다(없으면 [거절] 숨김).
- **반려 결과 표시**: 결과 보고 `outcome: "반려"`, `level: "rejected"`, 요약에 사유. 처리 기록 줄 `APPROVAL_REJECTED`(`data.name` "거절 접수", `by` · `role` · `reason` · `effects`). 끝 이벤트 `E_rejected`("거절 종결"), 사건 상태 `REJECTED_BY_OPERATOR`. `/api/scenario/status` 의 `last.outcome` 이 "반려"일 수 있다(표시는 켜진 채).
- **승인 지연 알림 표시**: B · C 에도 A 와 같은 「승인 지연」 타이머 · 「승인 지연 알림」 task(결과 보고 `outcome: "승인 지연"`, `level: "info"`)가 생겼다. 알림 뒤에도 승인 task 는 그대로 열려 있다 — A 에서 이미 그리던 방식이 B · C 에도 나오는지 확인.
- 흐름 가져오기 부품 목록에 "조치 카드 승인 · 거절"이 새로 보인다. 분기 조건 값으로 `approval`('승인' · '반려')을 고를 수 있는지 확인.
- **F-syllabus.md 4절의 인계 목록에서 빼야 할 것**: 이름 바꾸기(4.2 전부 — 원래 이름 유지), 수업 입력 버튼 3개와 `class_inputs`, `POST /api/scenario/A/{act}` 의 `plant` 목록화(원래대로 객체), 새 기록 줄 `WORK_ORDER_REGISTERED` · `PURCHASE_ORDERED` · `RECEIPT_MATCH` · `PM_COUNTER_RESET` · `PM_COUNTER_KEPT` · `WAIT_SKIPPED`, 끝 이벤트 `E_ok` · `E_fail` · `E_late`, `caseRecord.js:188` 문구 재확인. 남는 것은 위 네 항목뿐이다.
