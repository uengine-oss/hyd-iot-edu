# final-verify — 남은 구현 하나 + 합친 코드 라이브 검증 (2026-10-10 밤 ~ 10-11)

작업 브랜치 `claude/hyd-handoff-work-xziutz`에 직접(사용자 지시 "브랜치는 하나로"). 시작 커밋 `fc76db5`. push 없음.
증거: 루트 `.evidence/a164-final/`(gitignore — 이 PC에만 있다).
형식: 발견 → 분류 → 조치(파일:줄) → 검증(검증됨 / 실패 / 미검증 / 해당 없음).

## 0. 시작 상태 (10-10 23:54 실측)
- `git log -1` = fc76db5, 작업 트리 깨끗. `.evidence/LIVE_LOCK` 없음. 워커 · 검사기 프로세스 없음(10-06부터 떠 있는 주인 없는 Chrome for Testing 한 벌은 있음 — 건드리지 않음).
- 컨테이너의 compose 작업 폴더: process · agent · plant-sim · neo4j = `.claude/worktrees/F-20261010-keep`, portal · dmn-mcp · effects-mcp · enterprise-* = `merge-preview`, detector · cmd-gateway · connect-* · emqx · redpanda · fuxa · grafana = `agent-aed004354f1cd7a4c`, timescaledb = `agent-afd136e4b22934cb9`.

## 1. 결함 수정 — A 를 연달아 돌릴 수 없던 것
- **발견(결함, 원인 확인)**: [쿨러 복구](`scenario_buttons.A_BUTTONS["restore"]`)는 plant-sim 에 `{"type": "restore", "component": "cooler"}` 만 보냈다. `Plant.inject` 의 restore 는 **외란 변수**(쿨러 건전도 · 누설 · 베어링 마모 — `plant.HEALTHY`)만 정상으로 되돌린다. 승인한 조치가 PLC 에 쓴 **지령**(`plc.apply_command` — 라이브에서 추천되는 SOP-COOL-11 은 `FanSpeedSP` 100, 부하 조정 안은 `LoadSP` 80 도)은 외란이 아니라 그대로 남는다. 그 지령에서 moderate 열화(건전도 0.55)의 평형 유온은 두 경우 모두 경보선 55 ℃ 아래(팬 100 · 부하 90 에서 49.8 ℃)라 다음 [쿨러 열화 주입]이 detector 의 올림 조건(TS1 > 55 ∧ CE < 70 ∧ 상승)을 영영 채우지 못했다. 지령까지 되돌리는 것은 설비 `/api/reset` 뿐이었다.
- **조치(근본)**: 복구 버튼이 설비를 조치 이전의 평소 운전점으로 되돌린다.
  - `ot/plant-sim/plantsim/thermal.py`: 평소 운전점 상수 `NORMAL_FAN_PCT, NORMAL_LOAD_PCT = 60, 90`(`UnitState` 기본값 · `/api/reset` 이 같은 상수를 쓴다 — 숫자 세 벌이던 것을 하나로).
  - `ot/plant-sim/plantsim/plant.py` `Plant.inject(..., operating_point=False)` + `_to_operating_point`: restore 요청에 `operating_point: true` 가 오면 팬 · 부하 지령을 그 자리에서 평소 값으로(지령은 계단, 램프 아님). 응답 `setpoints: {before, after}`. restore 가 아닌 종류에 붙이면 `ValueError` → HTTP 400(조용히 무시하지 않음). `ot/plant-sim/plantsim/main.py` `FaultReq.operating_point`.
  - `it/process/procsvc/scenario_buttons.py` `A_BUTTONS["restore"]["fault"]` 에 `operating_point: True`. `it/process/procsvc/main.py` `scenario_a_button`: 바뀐 지령 전 · 후를 열화로 열린 처리 건의 누름 기록(`SCENARIO_BUTTON` data.setpoints)과 감사 기록에 남긴다(블랙박스 없음).
  - process 의 정비 복구(`instance_mode.plant_restore`, C2)는 그대로다 — 지령을 건드리지 않는다(pump-fan 흐름의 조치 지령을 정비 모사가 지우지 않게).
- **`F-20261010-syllabus` 와 다른 점**: 그 브랜치는 `operating_point` 를 별도 주입 종류로 두고 복구 버튼이 요청 셋(restore · fan-drive restore · operating_point)을 보냈다. 그러면 설비의 마지막 주입 종류가 `operating_point` 가 되어 "마지막 주입이 restore 가 아니면 다음 경보를 그 누름에 잇는다"(`main._link_injection`)에 걸린다. 여기서는 restore 요청 하나의 선택 값으로 넣어 마지막 주입이 restore 로 남는다. 그 브랜치의 `fan_drive_fault` · `maintenance_defect` · 수업 입력은 가져오지 않았다.
- **검증됨(단위)**: 새 `tests/test_cooler_restore_rerun.py` 6개 — 열화 → 경보 → 조치 지령 → 해제 → 복구 → **곧바로** 열화 → detector 실제 규칙(`det.cep.evaluate`)이 다시 RAISE(보호 정지 없음) / 운전점 없이 복구하면 6000초가 지나도 경보 0(원인 고정) / 버튼 정의 · 정비 복구는 요청하지 않음 / restore 아닌 종류 거절 · 이미 평소면 변화 없음 · 다른 설비 그대로 / HTTP 요청 → 설비, 잘못된 짝 400 / process 버튼 API → 요청 본문 → 처리 건 기록 · 감사 기록 · 마지막 주입 종류.
  뮤테이션 7개 모두 잡힘(버튼에서 값 뺌 4실패 · 부하 지령 안 되돌림 2 · 거절 없앰 2 · HTTP 가 값 안 넘김 1 · 기록에 지령 안 남김 1 · 요청 없이도 되돌림 1 · 평소 값 상수를 조치 값으로 3).
- 라이브 확인은 4절.

## 2. 수업 준비물 — bpmn.io 에서 열리는 참조 흐름 (`students/flows/`)
- 만든 것: `cooling-emergency.bpmn`(A) · `pm-planning.bpmn`(B) · `spare-purchase.bpmn`(C) — bpmn.io 가 내보내는 형태(풀 하나 · 칸 셋 · incoming/outgoing · 그림 배치 `bpmndi` · 메시지 시작), 승인 · 거절 · 승인 지연 알림이 든 지금 모양. 연결 값 `*.mapping.json`(= `c3_flows.py` 의 매핑 그대로), 한 쪽 안내 `README.md`(가져오는 순서, 시작 조건, 단계별 부품 · 담당, 분기 조건, 타이머, 화면에 칸이 없는 설정을 연결 값 파일로 넣는 법).
- 요소 id · 이름 · 선은 `c3_flows.py` 에서 읽고 자리(좌표)만 정해 그렸다 — 도구 `docs/handoff/tools/live/draw_flows.py`(`c3_flows.py` 를 고치면 다시 돌린다. 다시 돌린 결과가 커밋한 파일과 같음을 확인).
- **검증됨(bpmn.io 형식)**: bpmn.io 의 그리기 라이브러리(bpmn-js 17.11.1, process-gpt `node_modules` 를 읽기만 — K 가 쓴 방법)로 열어 경고 0 · 페이지 오류 0: A 도형 21 · 선 15, B 17 · 10, C 18 · 11. 일부러 끊은 선은 "unresolved reference" 경고로 잡힘. 그림 `.evidence/a164-final/bpmn/A-cooling.png` · `B-pm.png` · `C-spare.png` · `open.log`. A 그림은 눈으로 봤다(칸 · 선 · 점선 타이머 · 이름표). demo.bpmn.io 사이트에 직접 올려 보지는 않았다(미검증).
- **검증됨(단위)**: 새 `tests/test_student_reference_flows.py` 7개 — 흐름마다 ① 포털 가져오기가 읽은 구조(요소 종류 · 이름 · 붙은 곳 · 멈춤 여부 · 선 · 칸 · task 의 칸)가 `c3_flows` 와 같고, 연결 값 파일이 `c3_flows` 매핑과 같고, 그 둘로 사전 검사를 통과해 나온 **실행 정의가 같다**(원본 파일 칸만 제외) ② bpmn.io 형태(모든 요소 · 선에 자리, 요소가 그려진 칸 = 속한 칸, incoming/outgoing 이 선과 맞음) ③ 안내문의 표가 실제 선택과 같다(포털에 보이는 부품 이름 · 에이전트 이름 · 역할 · 시작 경보 · 조건 · 기한 · 결과 값). 뮤테이션 11개 모두 잡힘(그림의 이름 · 멈춤 여부 · 선 · 메시지 시작 · 자리 · 칸, 연결 값 파일, `c3_flows` 의 기한 · 부품, 안내문의 에이전트 · 결과 값). 안내문에 처음 `recovered == true` 로 적었던 것을 이 시험이 잡았다(시스템 표기는 `recovered == True`).
- 라이브(이 A 파일을 학생 순서로 가져와 완주)는 4절.

## 3. 스택을 작업 브랜치 코드로 (잠금 10-11 00:06 ~)
- 잠금 `.evidence/LIVE_LOCK` 을 쓰고 시작. 레포 루트에서 `docker compose -p hyd-iot-edu build process agent plant-sim` → `up -d --no-deps process agent plant-sim`(커밋 `4e5f535`, 작업 트리 깨끗). `.env` 는 루트 것(값은 열지 않음).
- **검증됨**: 컨테이너 안 파이썬 파일 전체의 해시가 루트와 같다(process `procsvc/*.py` · agent `agentsvc/*.py` · plant-sim `plantsim/*.py`). plant-sim `/openapi.json` 의 `FaultReq` 에 `operating_point` 가 있다. process · agent · plant-sim 모두 healthy · RestartCount 0(StartedAt 15:06:27Z).
- 이전 이미지에 꼬리표를 붙이지 못했다: zsh 가 `$s:latest` 를 변수 수정자로 읽어 `docker tag` 가 실패했고, 빌드 뒤에는 옛 이미지가 이름 없이 사라져 있었다(containerd 저장소). 필요하면 `F-20261010-keep` 작업 트리(c4920d7)에서 다시 빌드할 수 있다. 오늘 낮의 `before-f-syllabus` 꼬리표는 그대로 있다.
- neo4j 는 빌드하지 않는 이미지다. 4절에서 그래프 볼륨을 바꾸고 되돌리며 루트에서 다시 만들어지므로 compose 작업 폴더가 루트로 바뀐다(끝난 뒤 표 — 7절).
- **건드리지 않은 것**: portal(← `merge-preview` 의 `it/portal/www` 를 물고 있음) · grafana · timescaledb · fuxa · dmn-mcp · effects-mcp · enterprise-* · detector · cmd-gateway · connect-* · emqx · redpanda. 이들이 빌드된 작업 트리(`merge-preview` 693c56f, `agent-aed004354f1cd7a4c` ba4b7f2 — 둘 다 작업 트리 깨끗)와 지금 브랜치를 `git diff` 로 비교하면 `it/dmn-mcp` · `it/effects-mcp` · `it/enterprise-mcp` · `it/enterprise-sim` · `it/detector` · `dmz/cmd-gateway` · `dmz/connect-ingest` · `it/connect-sink` · `common` 모두 차이 0 이다(이미지 안 파일을 직접 대조한 것은 아니다).

## 4. 라이브 검증 — 합친 코드로 (10-11 00:07 ~ 00:34, 워커 1개 opus)
순서: 그래프 구조판(루트에서 override 로 `up -d --no-deps neo4j`) → `scripts/c3_flows.py deploy`(세 흐름 판 9, 경보 → 흐름 표에 "내가 배포한 흐름") → 워커 → `scripts/approval_stage_live.py <경우> <폴더>`.
화면 조작 없이 포털 버튼이 부르는 것과 같은 process API 로 눌렀다(포털에 [거절]이 없다). 한 번에 한 건. 워커 한도(RunFailed) 없음. process RestartCount 0.
증거 `.evidence/a164-final/live/`(경우마다 `*-at-approval.json` · `*-final.json` · `*-checks.json` · `*.log`, 무응답은 `*-while-waiting.json`, `worker.log`, `00-deploy.log`).
이번에 도구에 더한 것: 연 흐름이 기대한 흐름인지 확인, [쿨러 복구] 직후 지령 확인, 정리가 감지기 경보가 내려갈 때까지 기다림, `--flow` · `--no-settle`.

### 4.1 승인 · 거절 · 무응답 — 검증됨
| 경우 | 처리 건 | 결과 | 확인 |
|---|---|---|---|
| A 승인 | `c3_cooling.32aca7de…` | `E_end` · 정상 "유온 정상 · 경보 해제, 작업지시 WO-1010-1198", 명령 id 있음 · 재확인 회복, 사건 CLOSED | 12/12 |
| A 거절 | `c3_cooling.94a9231b…` | `E_rejected` · 반려, 사건 REJECTED_BY_OPERATOR, 설비 명령 0건 | 13/13 |
| **A 무응답 → 거절** | `c3_cooling.bede0d2e…` | 승인 대기 30초 뒤 지연 알림, 20초 더 두어도 처리 건 RUNNING · 승인 task 대기 · 사건 승인 대기 · 처리 0건 → 거절로 닫음 | 16/16 |
| B 승인 | `c3_pm.28d73c7a…` | `E_end` · 정상 "정비 오더 WO-1010-5DDD 등록 · 생산팀 공지", 표시 꺼짐 | 9/9 |
| B 거절 | `c3_pm.f5b9d031…` | `E_rejected` · 반려 "정비 오더를 내지 않았습니다", 표시 켜진 채 | 11/11 |
| C 승인 | `c3_spare.8b48bf5f…` | `E_end` · 입고 완료 "씰 키트 6개 입고 · 검수 합격 (발주 PR-1010-83F3)", 표시 꺼짐 | 10/10 |
| C 거절 | `c3_spare.52fe11af…` | `E_rejected` · 반려 "발주하지 않았습니다", 표시 켜진 채 | 12/12 |
| **C 무응답 → 거절** | `c3_spare.5a8b0ed3…` | 승인 대기 31초 뒤 지연 알림, 그 뒤에도 승인 대기 · 처리 0건 → 거절로 닫음 | 15/15 |
- B 무응답은 다시 돌리지 않았다(F-keep 에서 확인된 것 — `.evidence/a163-restore/B-wait-*`, 그때는 F-keep 빌드).
- 실측 시간(20배속, 실제 AI, 버튼 → 승인 대기): A 79~91초(연달아 돌린 회는 131초) · B 52~58초 · C 55~61초, A 승인 → 끝 64초.

### 4.2 1절 수정 확인 — A 승인 완주 → [쿨러 복구] → 곧바로 [쿨러 열화 주입] — 검증됨
- `A-approve … --no-settle`: 처리 건 `c3_cooling.32aca7de…` 이 00:25:12 에 끝남 → 00:25:13 [쿨러 복구] — 응답 `setpoints` 전 `{FanSpeedSP 100, LoadSP 90}` → 후 `{60, 90}`, 설비 태그도 그 자리에서 60 · 90(확인 통과), 그때 유온 51.15 ℃ · 감지기 경보 없음.
- 기다리지 않고 바로 다음 실행이 [쿨러 열화 주입]을 눌렀다 → **25초 뒤(00:25:38) 새 처리 건 `c3_cooling.6280d2a7…`** 이 열려 승인 → 명령 → 재확인 → 정상 종결(12/12, `live/rerun/`). 설비 `/api/reset` 은 부르지 않았다(plant-sim 은 00:06 재기동 뒤 한 번도 reset 하지 않은 상태에서 A 를 네 번 연달아 돌렸다: 거절 · 무응답 · 승인 · 승인).
- 복구 누름 기록에 지령 전 · 후가 남는다: 처리 건 events 의 `수업 버튼 [쿨러 복구]` data.setpoints `{before: {FanSpeedSP 100, LoadSP 90}, after: {60, 90}}`(`handdrawn/restore-record.txt`).
- 알아 둘 것(결함 아님): 거절 · 무응답으로 끝난 A 는 경보가 올라간 채다. [쿨러 복구] 뒤 감지기가 그 경보를 내릴 때까지(실측 약 65초) 다음 주입은 새 경보를 내지 않는다 — 같은 경보가 이어지는 것이기 때문이다.

### 4.3 `close_agent_task` — 검증됨 (K 의 재현과 멈춘 경위가 다름)
- 흐름: 시작(직접) → 에이전트 → 사람 확인 → 결과 보고 → 끝(`close/probe.bpmn` · `probe.mapping.json`, 흐름 id `fv_close_probe` — 포털 가져오기 API 로 등록).
- 직접 시작 → 워커가 에이전트 단계를 집음(닿지 않은 두 단계는 TODO) → 사람이 실행 취소(`POST /api/todolist/{id}/cancel`) → 워커가 2초 뒤 놓음(단계 IN_PROGRESS · 실행 CANCELLED, 처리 건 RUNNING) → **단계 닫기**(`POST /api/todolist/{id}/close`) → 응답 `instance_ended: true`, 처리 건 **COMPLETED · 끝 이벤트 `closed-by-human`**, 세 단계 모두 CANCELLED, 결과 보고 없음, 처리 기록에 "에이전트 작업 닫음". 확인 6/6 — `close/close.log` · `close-final.json`.
- K 의 재현(5.3 1회)은 에이전트가 스스로 보류(PENDING)한 단계를 닫은 것이고, 여기서는 사람이 취소해 멈춘 단계를 닫았다. 닫기 뒤 "닿지 않은 TODO 단계 때문에 RUNNING 으로 남는가"를 재는 것은 같다(닫을 수 있는 멈춘 상태 둘 중 다른 쪽). PENDING 쪽은 단위 시험(`tests/test_close_agent_task.py`)만 있다 — 라이브 미검증.

### 4.4 손으로 그린 흐름 사본으로 A 완주 — 검증됨
- 파일: `students/flows/cooling-emergency.bpmn`(2절 — bpmn.io 형태, 그림 배치 포함, 메시지 시작). 학생 순서대로 포털의 흐름 가져오기 API 를 불렀다(`tools/handdrawn_import.py`, 응답 `handdrawn/1-import.json` ~ `6-deploy-reset.json`, `import-deploy.log`):
  1. `POST /api/flows/import`(흐름 id `my_cooling`) → task 9 · 분기 2 · 경계 타이머 1 · 칸 셋 · 메시지 시작, 그림 문제 0. 처음 연결 값은 시작 = 감지기 경보 셋 · 고른 부품 0 → 사전 검사 14건("부품을 고르세요", 분기 조건 없음, "시간 초과 기간을 정하세요").
  2. `PUT /api/flows/my_cooling/mapping`(`cooling-emergency.mapping.json` — 시작 조건 쿨러 경보 하나, 에이전트 = 냉각 긴급 대응 에이전트, 승인 = 운전원, 시스템 부품 여섯) → 사전 검사 통과.
  3. `POST …/register` → 판본 1. 4. `POST /api/process/definitions/my_cooling/deploy` → 배포.
- 경보 → 흐름 표(`GET /api/flows/deployments`): 배포 전 `COOLER_DEGRADATION → c3_cooling 판 9`, 배포 뒤 **`→ my_cooling 판 1 (내가 배포한 흐름)`**, `c3_cooling` 은 "가려진 경보"로 내려감.
- [쿨러 열화 주입] → **`my_cooling.795d6572…`**(연 흐름 확인 통과) → 에이전트 79초 → 승인 → 냉각 명령(`CMD-1010-0003-539d`) → 재관측 회복 → 작업지시 WO-1010-BB30 → 정상 종결 `E_end`, 사건 CLOSED — 12/12(`handdrawn/A-approve-*`).
- "기준 흐름으로 되돌리기"(`POST /api/flows/deploy-reset`) → 학생 흐름 넷(`my_cooling` · `c3_*`) 내림, 표가 `COOLER_DEGRADATION → anomaly_response 2.2 (기준 흐름)` · 배포된 학생 흐름 0. 되돌린 뒤 실제로 기준 흐름이 여는지는 5절 쿨러 회귀가 본다.
- **포털 화면으로는 하지 않았다**(API 만). 화면에 시스템 부품 설정 칸이 없어 2번은 화면만으로 끝낼 수 없다(NOW 3.2) — 연결 값 파일을 API 로 넣는 길을 `students/flows/README.md` 에 적었다.

## 5. 회귀 두 개 — **끝내지 못함(워커 구독 한도)**
- 먼저 판정(지금도 유효한 시험인가): 두 회귀는 기준 흐름 `anomaly_response`(부품 `task:select` — 승인만, 이번에 바뀌지 않음)와 전체판 그래프에서 돈다. 승인 단계 변경은 수업 흐름(`c3_*`, 부품 `task:select-or-reject`)에만 들어갔고 기준 정의 · `task:select` 는 그대로라 기대값은 달라지지 않는다. 1절 수정은 [쿨러 복구] 버튼 요청에만 붙고 회귀는 `/api/fault` · `/api/reset` 을 직접 부른다. → 유효, 고칠 것 없음(코드 읽고 판정. 실행으로는 아래까지만).
- 준비: 흐름 기준으로(4.4) → 워커 멈춤 → 그래프 전체판(루트에서 `up -d --no-deps neo4j`) → 설비 `/api/reset` → 워커 1개 다시.
- 쿨러 `scripts/scenario_instance_test.py --worker`(00:34 시작): 0 · 1단계 13개 확인 통과 — 경보 41초 뒤 올라옴, **기준 흐름 처리 건 `anomaly_response.802bf16d…` 이 열림**(= "기준 흐름으로 되돌리기" 뒤 기준 흐름이 다시 연다는 4.4 의 실측), 사건 AWAITING_APPROVAL, 에이전트 작업 셋(진단 · 후보 조회 · 규정 검토) DONE. 네 번째 `task:rank` 에서 워커가 **`RunFailed: You've hit your session limit · resets 2:40am (Asia/Seoul)`**(00:39:08, `regression/worker.log`). 지시대로 반복하지 않고 멈췄다. 로그 `regression/reg-cooler.log`(검사기는 내가 끊었다 — 판정 줄 없음).
- pump-fan `scripts/scenario_pump_fan_test.py --worker --reassess-held`: **돌리지 않음**(같은 한도).
- **미검증으로 남는 것**: 이 빌드(4e5f535)에서의 쿨러 회귀 전체 · pump-fan 회귀. 한도가 풀린 뒤(02:40 이후) 잠금을 잡고 "흐름 기준 · 그래프 전체판 · 설비 reset · 워커 1개" 상태에서 두 명령을 한 번씩 돌리면 된다(지금 쉬는 상태가 그 상태다 — 워커만 켜면 됨).

## 6. 포털에 넘길 것 (`it/portal/www/**` 미수정)
1. **[쿨러 복구] 기록에 지령 변화 표시**: 그 누름의 처리 기록 줄(`SCENARIO_BUTTON`, `data.setpoints = {before: {FanSpeedSP, LoadSP}, after: {…}}`)과 버튼 응답(`plant.setpoints`)에 값이 실린다. 화면은 아직 이 값을 읽지 않는다 — "팬 지령 100 % → 60 %, 부하 90 % 그대로"처럼 일반인 말로 보이게. 복구가 조치 지령까지 되돌린다는 것이 화면에서 읽혀야 블랙박스가 아니다.
2. **거절 · 무응답으로 끝난 A 뒤의 [쿨러 열화 주입]**: 경보가 올라간 채라 [쿨러 복구] 뒤 감지기가 경보를 내릴 때까지(실측 약 65초) 새 처리 건이 열리지 않는다. 버튼 옆 상태(감지기 단계)를 보고 누르라는 안내가 화면에 있는지 확인.
3. **흐름 가져오기**(K 가 넘긴 것과 같은 자리): 시스템 부품 설정 칸이 생기기 전까지 `students/flows/README.md` 는 연결 값 파일을 API 로 넣게 안내한다. 칸이 생기면 README 의 마지막 절을 화면 순서로 바꾼다. 가져온 직후 시작 조건에 감지기 경보 셋이 모두 체크돼 있고(학생이 둘을 꺼야 한다), 시작 조건 칸의 `PM_DUE` · `SPARE_BELOW_MIN` 은 영문 그대로, 분기 조건은 `recovered == True` 로 보인다 — 안내문은 지금 표기를 따랐다. 화면 표기를 바꾸면 `tests/test_student_reference_flows.py` 의 안내문 대조가 알려 준다.
4. F-keep 4절의 세 가지([거절] + 사유, 반려 결과, B · C 승인 지연 알림 표시)는 그대로 열려 있다. 이번 라이브는 모두 API 로 눌렀고 **포털 화면에서 반려 · 지연 알림 · 손으로 그린 흐름의 처리 건이 어떻게 보이는지는 보지 않았다**(캡처 없음).

## 7. 복원 · 끝난 뒤 스택 (10-11 00:47)
- 한도에 걸린 쿨러 회귀의 처리 건: 설비 `/api/reset` → 감지기 경보 내려감 → 사건 `RESOLVED_WITHOUT_ACTION`, 처리 건은 사람 작업 `task:escalate` 에서 RUNNING. 중단된 검사 잔재라 `scripts/cleanup_residue_instances.py`(dry-run 으로 1건뿐임을 본 뒤 `--apply`, 백업 `restore/residue/backup.json`)로 정리.
- 내 시험 흐름 둘(`my_cooling` · `fv_close_probe`)만 지움: K 가 쓴 문장(포털 '기준으로 되돌리기'와 같은 문장을 흐름 id 로 좁힌 것)에 id 만 바꿔 실행, 지우기 전 행 백업 `restore/backup-*.json` · `remove-my-flows.sql`. 학생 흐름 하나만 지우는 API 가 없어서 손으로 했다(K 11절의 열린 일 그대로). `c3_*` 초안 · 판본은 그대로.
- **남긴 것(손대지 않음)**: 구조판 그래프 볼륨(`neo4j-data-c3`)에 이번 실행의 투영(처리 건 · 흐름 판본 `c3_*@9` · `my_cooling@1` · `fv_close_probe@1`)이 남아 있다. 정의 투영을 지우는 길이 제품에 없고(K 11절), 수업 문서가 든 볼륨을 손 질의로 고치지 않았다.
- B · C [초기화] → 표시 켜짐. 워커 0(8097 듣는 것 없음). RUNNING 처리 건 0. 경보 → 흐름 표 = 기준 흐름(`at_reference: true`). 설비 세 대 정상(유온 48 · 팬 60 · 부하 90 · RUN · REMOTE_AUTO), 감지기 전부 IDLE. 그래프 = 전체판(노드 1476 · 관계 3480, 이름 공간 노드 0). process RestartCount 0. 잠금 지움. 원문 `restore/final-state.log`.
- 회귀 검사기의 시작 단계가 업무 `/api/reset` 을 불러 라이브 완주의 업무 행(WO · PR · GR)은 보관 표로 옮겨졌다(처리 건 기록은 남음 — NOW 2절에 적힌 동작).

| 컨테이너 | 코드 | compose 작업 폴더 |
|---|---|---|
| process · agent · plant-sim | **작업 브랜치 `4e5f535` 빌드**(10-11 00:06, 컨테이너 안 파일 해시 = 루트. 그 뒤 커밋은 시험 · 문서 · `students/flows` 뿐) | **레포 루트** |
| neo4j | 이미지 `neo4j:5.26-community`(빌드 없음), 볼륨 `hyd-iot-edu_neo4j-data`(전체판) | **레포 루트** |
| dmn-mcp · effects-mcp · enterprise-mcp(· maint · purchase) · enterprise-sim | 10-09 · 10-10 빌드, `merge-preview`(693c56f) 기준 — 지금 브랜치와 소스 차이 0 | `.claude/worktrees/merge-preview` |
| portal | nginx, `merge-preview` 의 `it/portal/www` · `nginx.conf` 를 **직접 물고 있음** | `.claude/worktrees/merge-preview` |
| detector · cmd-gateway · connect-ingest · connect-sink | 10-09 빌드, `agent-aed004354f1cd7a4c`(ba4b7f2) 기준 — 지금 브랜치와 소스 차이 0 | `.claude/worktrees/agent-aed004354f1cd7a4c` |
| emqx · redpanda · fuxa | 공개 이미지 | `.claude/worktrees/agent-aed004354f1cd7a4c` |
| grafana | 공개 이미지, 그 작업 트리의 `it/grafana/provisioning` 을 **직접 물고 있음** | `.claude/worktrees/agent-aed004354f1cd7a4c` |
| timescaledb | 공개 이미지, 그 작업 트리의 `init.sql` · `reader.sql` 을 **직접 물고 있음** | `.claude/worktrees/agent-afd136e4b22934cb9` |
- **`F-20261010-keep` 작업 트리를 물고 있는 컨테이너는 이제 없다.** 지우면 안 되는 작업 트리는 `merge-preview` · `agent-aed004354f1cd7a4c` · `agent-afd136e4b22934cb9` 셋으로 돌아왔다. portal 등은 이번 범위에서 건드리지 않았다.

## 8. 전체 단위 시험
`.venv/bin/python -m pytest -q -p no:cacheprovider` → **2149 통과 · 9 건너뜀 · 0 실패**(211초, 커밋 `d07b298` 의 코드 · 시험). 합친 뒤 처음 돌린 전체 시험이다. 로그 `.evidence/a164-final/pytest-full.log`.

## 9. 사용자 확인이 필요한 것
1. 회귀 두 개(쿨러 · pump-fan)를 한도가 풀린 뒤(02:40 이후) 다시 돌릴지 — 이 빌드로는 통과 기록이 없다(5절).
2. `students/flows/` 에 연결 값 파일(`*.mapping.json`)을 같이 둔 것 — 포털에 시스템 부품 설정 칸이 생기면 뺄지. 흐름 이름은 `c3_flows.py` 그대로("냉각 긴급 대응" · "정기 정비" · "예비품 구매")라 시나리오 이름(긴급 대응 · 정기 점검 · 재고 보충)과 낱말이 다르다 — 고친 실라버스를 받으면 대조.
3. 구조판 그래프 볼륨에 남은 이번 실행의 투영(7절)을 둘지 — 그 볼륨의 삭제 여부(NOW 4절)와 같이 정하면 된다.
4. `F-20261010-keep` 작업 트리는 이제 스택과 무관하다 — 다른 끝난 작업 트리와 함께 정리할지.
5. 이전(F-keep) 이미지 꼬리표가 없다(3절). 되돌릴 일이 있으면 그 작업 트리에서 다시 빌드해야 한다.
6. push 는 하지 않았다.

## 10. 회귀 두 개 — 한도가 풀린 뒤 이어서 (10-11 02:42 ~ 03:07) — **검증됨**
5절에서 미완으로 남긴 것만 했다. 시작 상태 실측: 잠금 없음 · 워커 0 · RUNNING 0 · 기준 흐름 · 그래프 전체판 · 설비 정상 · process 는 00:06 빌드(`4e5f535`) 그대로(RestartCount 0). 잠금 → 워커 1개(opus) → 두 명령. 검사기 · 기대값은 고치지 않았다.
- 쿨러 `scripts/scenario_instance_test.py --worker` → **ALL PASS 40/40**, exit 0(경보 42초, 에이전트 작업 넷 234초).
- pump-fan `scripts/scenario_pump_fan_test.py --worker --reassess-held` → **ALL PASS 43/43**, exit 0(펌프 누설 → 예비 펌프 전환 종결 / 팬 베어링 마모 → 종결 / 가림: 경보는 꺼지지만 PS1 미회복 → 에스컬레이션). 보류된 진단의 재평가는 이번 회에 일어나지 않았다(`reassessments.json` 빈 목록).
- 워커 한도(RunFailed) 없음. 증거 `.evidence/a164-final/regression2/`(`reg-cooler.log` · `reg-pump-fan.log` · `worker.log` · `pump-fan/` · `final-state.log`).
- 끝난 뒤(03:07 실측): 워커 멈춤(8097 듣는 것 0) → 설비 `/api/reset` → B · C [초기화] → 잠금 지움. 잠금 없음 · 워커 0 · RUNNING 0 · 기준 흐름(`at_reference: true`) · B · C 표시 켜짐 · 설비 세 대 정상 · 감지기 전부 IDLE · 그래프 전체판 · process RestartCount 0. 컨테이너별 코드 · 작업 폴더는 7절 표 그대로(compose 는 건드리지 않았다).
- 이로써 5절 "미검증으로 남는 것"과 9절 1번은 닫혔다.
