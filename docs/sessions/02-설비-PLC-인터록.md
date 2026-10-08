# 2. 설비 · PLC · 인터록, 구역과 보안 (1부, 180분: 설명 60 / 실습 90 / 정리 30)

## 이번에 할 것 / 끝나면 보이는 것
설비 모델의 식 세 개와 PLC가 명령을 검사하는 순서를 코드로 읽고, 수동 운전 중인 설비에는 원격 조치 카드가 규정상 전부 제외되는 것을 직접 본다.
끝나면 "조치 카드 선택" 작업에 제어 카드가 하나도 없는 화면(제외 사유 `rule:auto-mode`)과, 인터록 세 가지와 게이트웨이 검사 6종을 코드 줄로 짚은 메모가 남는다.

## 준비
- 1회차와 같은 스택(RUNBOOK). 포털 http://127.0.0.1:8088, 게이트웨이 http://127.0.0.1:8090/docs.
- 읽을 파일: `ot/plant-sim/plantsim/thermal.py`, `ot/plant-sim/plantsim/plc.py`, `dmz/cmd-gateway/gw/validate.py`.

## 실행 장면
1. [파일] `thermal.py` → [입력] `equilibrium_ts1`(72행)·`effective_leak`(78행)·`vibration`(83행) 세 함수를 찾는다 → [관찰] 유온·누설·진동이 각각 부하·팬·건강도에서 어떻게 계산되는지 → [확인] 세 식을 한 줄씩 자기 말로 적는다.
2. [파일] `plc.py` 머리말(1~8행) → [관찰] 검사 순서 "모드/출처 일치 → 만료 → 최근 32개 cmdId 중복 → 쓰기 범위 → 하드 인터록", 인터록 `TS1 > 65 OVERTEMP · PS1 < 130 LOW_PRESSURE · VS1 >= 2.0 HIGH_VIBRATION` → [확인] `check_interlock`(49행)와 `apply_command`(67행)의 `MODE_MISMATCH`(74·77행)·`INTERLOCK_TRIP`(111행)·`RESET_TOO_HOT`(113행) 줄 번호를 메모.
3. [파일] `validate.py` 머리말과 `CHECKS` → [관찰] 게이트웨이의 검사 결과 종류 `PASS | SCHEMA | WHITELIST | EXPIRED | DUPLICATE | APPROVAL | MODE | RATE_LIMIT`(통과 1 + 거절 7종; `APPROVAL`은 2026-10-08 추가 — process가 승인마다 audit 토픽에 남기는 승인 기록·명령 지문이 없는 명령은 거절) → [확인] PLC 검사와 게이트웨이 검사가 서로 다른 층에 있음을 그림으로.
4. [화면] 포털 → **결함 시뮬레이션** → HYD-02 카드 → **원격 수동** (같은 일: `curl -X POST 127.0.0.1:8000/api/mode -H 'Content-Type: application/json' -d '{"asset":"HYD-02","mode":"REMOTE_MANUAL"}'`) → [확인] `curl -s 127.0.0.1:8000/api/state`의 `units.HYD-02.status.mode`가 `REMOTE_MANUAL`.
5. [화면] 같은 카드 → **쿨러 열화 주입** → 경보(RAISED)가 뜨면 **이상 확인 · 조치 → 에이전트 트레이스**의 `cards` 단계 → [관찰] 제어 카드 3장(팬 최대 + 부하 80 % · 팬 최대 · 야간 청소 감산)이 전부 "규정상 제외", 사유 `rule:auto-mode`(원격 제어는 REMOTE_AUTO에서만); 남은 정비 요청 카드(쿨러 핀 세척)도 예측 유온이 인터록 한계를 넘어 `rule:ts1-hard`로 제외 → 쓸 수 있는 카드가 없어 **프로세스 인스턴스**의 첫 작업(원인 진단)이 "검증된 조치 대안을 만들지 못했습니다"로 **보류**되고 "조치 카드 선택" 작업은 열리지 않는다 → [확인] 제외된 카드 수를 적는다. 규정 검토(에이전트)가 첫 번째 층, 게이트웨이의 `MODE` 검사가 두 번째 층이다 — 정상 흐름에서는 첫 층에서 막혀 게이트웨이까지 가지 않는다. 조치가 없으니 약 70초 뒤 설비가 과열 트립(OVERTEMP)되고, 경보가 풀리면 사건은 "조치 전 종료"(화면 표기: RESOLVED_WITHOUT_ACTION)로 끝나며 책임자 확인 작업(생산관리자)이 열린다.
6. [명령] `curl -s 127.0.0.1:8090/api/gateway/log` → [관찰] 오늘 발행된 명령의 `check` 값(정상이면 전부 `PASS`) → [확인] 5단계에서 명령이 발행되지 않았으므로 HYD-02 거절 행이 **없다**는 것 자체가 관찰 결과다.
7. [화면] HYD-02 카드 → **원격 자동** → **결함 복구** → [확인] 모드 REMOTE_AUTO, TS1 하강. 트립(OVERTEMP)이 남아 있으므로 TS1 < 55 ℃가 된 뒤 **RESET**(수동 쓰기 `{"Reset":1}`) 또는 **전체 초기화**. 열린 사건은 정비 요청 카드를 고르거나 그대로 두고 다음 실습 전에 **전체 초기화**.

## 막혔을 때
- 제외가 아니라 제어 카드가 그대로 나온다: 4단계 모드 전환이 적용되기 전에 주입했다. `curl 127.0.0.1:8000/api/state`의 `units.HYD-02.status.mode` 확인.
- 경보가 안 뜬다: 1회차 "막혔을 때"와 같다.
- 책임자 확인 작업이 "내 할일"에 남는다: 정상이다(조치 없이 끝난 사건을 사람이 확인하는 작업). 다음 실습 전에 **전체 초기화**로 설비만 되돌리고, 실행 기록은 수업 뒤 RUNBOOK §3 잔재 정리로 지운다.
- ACK가 30초 안에 안 오면(명령이 발행된 뒤 설비가 수동으로 바뀐 경우) 사건은 `ESCALATED(ACK_TIMEOUT)`(`machine.py` 233행).

## 증거
- `.evidence/sessions/02/`(2026-10-07 제작자, `run.py`·`commands.md`): 1~3단계 줄 번호 대조·4단계 모드 조회·6단계 게이트웨이 로그 조회 **검증됨**.
- 2차 `run2.py`(같은 `commands.md` 아래): 4 `POST /api/mode` → HYD-02 `REMOTE_MANUAL` · 5 쿨러 주입 → RAISED 34.4 s → 에이전트 실행 `RUN-0028` WITHHELD, `cards` 단계에서 제어 카드 3장 `rule:auto-mode` 제외 · 쿨러 핀 세척 `rule:ts1-hard` 제외(`05_agent_run_RUN-0028.json`) → 원인 진단 보류("검증된 조치 대안을 만들지 못했습니다"), 선택 작업 열리지 않음 → 과열 트립 뒤 사건 RESOLVED_WITHOUT_ACTION, 책임자 확인 IN_PROGRESS(생산관리자) · 6 이 실행 뒤 HYD-02 게이트웨이 행 0건 · 7 원격 자동 + 결함 복구(트립 OVERTEMP 남음, TS1 45.32) → 전체 초기화로 정상 운전점 — **검증됨**(포털 화면 대신 같은 API). 절차의 원래 기대(선택 작업에 정비 요청 카드만 남음)는 현재 배포본에서 나오지 않아 5단계를 실제 동작으로 고쳤다.
- 이전 제작자 증거(레거시 경로): `scripts/scenario_test.py` `negative_manual_mode` 기록 `.evidence/scenario_test_legacy_quick.log` 52행.
