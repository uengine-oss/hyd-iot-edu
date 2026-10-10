# final-verify — 남은 구현 하나 + 합친 코드 라이브 검증 (2026-10-10 밤 ~ 10-11)

작업 브랜치 `claude/hyd-handoff-work-xziutz`에 직접(사용자 지시 "브랜치는 하나로"). 시작 커밋 `fc76db5`. push 없음.
증거: 루트 `.evidence/a164-final/`(gitignore — 이 PC에만 있다).
형식: 발견 → 분류 → 조치(파일:줄) → 검증(검증됨 / 실패 / 미검증 / 해당 없음).

## 0. 시작 상태 (10-10 23:54 실측)
- `git log -1` = fc76db5, 작업 트리 깨끗. `.evidence/LIVE_LOCK` 없음. 워커 · 검사기 프로세스 없음(10-06부터 떠 있는 주인 없는 Chrome for Testing 한 벌은 있음 — 건드리지 않음).
- 컨테이너의 compose 작업 폴더: process · agent · plant-sim · neo4j = `.claude/worktrees/F-20261010-keep`, portal · dmn-mcp · effects-mcp · enterprise-* = `merge-preview`, detector · cmd-gateway · connect-* · emqx · redpanda · fuxa · grafana = `agent-aed004354f1cd7a4c`, timescaledb = `agent-afd136e4b22934cb9`.

## 1. 결함 수정 — A 를 연달아 돌릴 수 없던 것
- **발견(결함, 원인 확인)**: [쿨러 복구](`scenario_buttons.A_BUTTONS["restore"]`)는 plant-sim 에 `{"type": "restore", "component": "cooler"}` 만 보냈다. `Plant.inject` 의 restore 는 **외란 변수**(쿨러 건전도 · 누설 · 베어링 마모 — `plant.HEALTHY`)만 정상으로 되돌린다. 승인한 조치가 PLC 에 쓴 **지령**(`FanSpeedSP` 100 · `LoadSP` 80, `plc.apply_command`)은 외란이 아니라 그대로 남는다. 그 지령에서 moderate 열화(건전도 0.55)의 평형 유온은 경보선 55 ℃ 아래(`thermal.equilibrium_ts1(80, 100, 0.55)`)라 다음 [쿨러 열화 주입]이 detector 의 올림 조건(TS1 > 55 ∧ CE < 70 ∧ 상승)을 영영 채우지 못했다. 지령까지 되돌리는 것은 설비 `/api/reset` 뿐이었다.
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
