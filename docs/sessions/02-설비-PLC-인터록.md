# 2. 설비 · PLC · 인터록, 구역과 보안 (1부, 180분: 설명 60 / 실습 90 / 정리 30)

## 이번에 할 것 / 끝나면 보이는 것
설비 모델의 식 세 개와 PLC가 명령을 검사하는 순서를 코드로 읽고, 수동 운전 중인 설비에는 승인한 명령이 거절되는 것을 직접 본다.
끝나면 "최근 제어 요청 결과"에 거절 1건(`MODE`)이 있고, 인터록 세 가지를 코드 줄로 짚은 메모가 남는다.

## 준비
- 1회차와 같은 스택(RUNBOOK). 포털 http://127.0.0.1:8088, 게이트웨이 http://127.0.0.1:8090/docs.
- 읽을 파일: `ot/plant-sim/plantsim/thermal.py`, `ot/plant-sim/plantsim/plc.py`, `dmz/cmd-gateway/gw/validate.py`.

## 실행 장면
1. [파일] `thermal.py` → [입력] `equilibrium_ts1`(72행)·`effective_leak`(78행)·`vibration`(83행) 세 함수를 찾는다 → [관찰] 유온·누설·진동이 각각 부하·팬·건강도에서 어떻게 계산되는지 → [확인] 세 식을 한 줄씩 자기 말로 적는다.
2. [파일] `plc.py` 머리말(1~8행) → [관찰] 검사 순서 "모드/출처 일치 → 만료 → 최근 32개 cmdId 중복 → 쓰기 범위 → 하드 인터록", 인터록 `TS1 > 65 OVERTEMP · PS1 < 130 LOW_PRESSURE · VS1 >= 2.0 HIGH_VIBRATION` → [확인] `check_interlock`(49행)와 `apply_command`(67행)의 `MODE_MISMATCH`(74·77행)·`INTERLOCK_TRIP`(111행)·`RESET_TOO_HOT`(113행) 줄 번호를 메모.
3. [파일] `validate.py` 26행 → [관찰] 게이트웨이의 검사 5종 `SCHEMA | WHITELIST | EXPIRED | DUPLICATE | MODE` → [확인] PLC 검사와 게이트웨이 검사가 서로 다른 층에 있음을 그림으로.
4. [화면] 포털 → **결함 시뮬레이션** → HYD-02 카드 → **원격 수동** (같은 일: `curl -X POST 127.0.0.1:8000/api/mode -H 'Content-Type: application/json' -d '{"asset":"HYD-02","mode":"REMOTE_MANUAL"}'`) → [확인] 카드 모드가 REMOTE_MANUAL.
5. [화면] 같은 카드 → **쿨러 열화 주입** → 경보가 뜨면 **프로세스 인스턴스 → 내 할일 → 조치 카드 선택**(생산관리자) → [관찰] 결함 시뮬레이션 탭 **최근 제어 요청 결과**에 `REJECT · MODE — PLC mode is REMOTE_MANUAL` → [확인] 30초(ACK 대기 한도, `machine.py` 233행) 뒤 사건이 **ESCALATED(ACK_TIMEOUT)**.
6. [명령] `curl -s 127.0.0.1:8090/api/gateway/log` → [확인] 같은 거절이 `check:"MODE"`로 기록돼 있다.
7. [화면] HYD-02 카드 → **원격 자동** → **결함 복구** → [확인] 모드 REMOTE_AUTO, TS1 하강.

## 막혔을 때
- 거절이 아니라 PASS가 나온다: 4단계 모드 전환이 적용되기 전에 주입했다. `curl 127.0.0.1:8000/api/state`의 `units.HYD-02.status.mode` 확인.
- 경보가 안 뜬다: 1회차 "막혔을 때"와 같다.
- 사건이 ESCALATED로 남는다: 정상이다(실패 사례). 다음 실습 전에 **전체 초기화**로 설비만 되돌리고, 사건 기록은 남겨 둔다.

## 증거
- 제작자 증거: `.evidence/reaudit/reg-a116/cooler-42/scenario.log` 안의 부정 사례(수동 운전 설비 거절·ACK_TIMEOUT)는 `scripts/scenario_instance_test.py`가 돌린 것이며 학생 완주 증거가 아니다. 과거 레거시 경로 증거 `.evidence/scenario_test_legacy_quick.log`.
- `.evidence/sessions/02/`: **미검증**.
