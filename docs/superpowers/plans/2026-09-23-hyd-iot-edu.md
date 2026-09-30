# hyd-iot-edu 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v3 아키텍처 4쪽 구조도의 L1~L9를 학생 노트북에서 `docker compose up`으로 돌리고, 포탈에서 "쿨러 열화 → 경보 → 에이전트 가이드 → 승인 → 조치 → 회복" 시나리오를 실행·검증하며, 그 과정을 녹화한 설명 영상을 만든다.

**Architecture:** OT(plant-sim, emqx, fuxa) / DMZ(connect-ingest, cmd-gateway) / IT(redpanda, detector, connect-sink, timescaledb, grafana, neo4j, agent, process, portal) 컨테이너. 모든 파이썬 서비스는 `common/`의 토픽·스키마 모듈을 공유하고, IO 없는 순수 로직 모듈(`logic.py`)과 IO 어댑터(`main.py`)를 분리해 순수 로직만 pytest로 검증한다.

**Tech Stack:** Python 3.12 (FastAPI, uvicorn, paho-mqtt 2.x, aiokafka, psycopg[binary], neo4j driver, httpx, anthropic 선택), EMQX 5.8, FUXA 1.3, Redpanda v24.2 + Console, TimescaleDB pg16, Grafana 11, Neo4j 5.26, nginx, 정적 SPA(바닐라 JS), Playwright + edge-tts + imageio-ffmpeg(영상).

**Spec:** `docs/superpowers/specs/2026-09-23-hyd-iot-edu-design.md`

## Global Constraints

- 토픽·페이로드·모드·검증 항목 이름은 v3 문서(5.1, 5.2, 7.1, 7.2, 7.3절)와 스펙 3절을 그대로 쓴다.
- 자산 ID는 메시지 본문에서 `HYD-01`, 토픽/키에서 `hyd01`.
- `TIME_SCALE`(기본 20)은 plant-sim, detector, process가 같은 환경변수로 읽는다. 시뮬레이션 시간 = 벽시계 × TIME_SCALE.
- 파이썬 서비스는 `/healthz`(200 `{"ok":true}`)와 `/metrics`(Prometheus 텍스트)를 제공한다.
- LLM 키가 없어도 전 시나리오가 동작한다.
- 컨테이너 메모리 합계 ≤ 3 GB (redpanda 512M, neo4j heap 512M, emqx 기본, 나머지 소형).

## Review Focus

1. **plant.status retained + ACK 재전송**: process가 재시작 후 retained status를 다시 읽어 옛 cmdId를 새 ACK로 오인하지 않아야 한다 → Task 10 테스트 `test_ack_ignores_stale_cmd_id`.
2. **CLEAR가 승인 전에 오는 경우**(운전원이 늦게 승인해 이미 회복): 프로세스는 AWAITING_APPROVAL에서 CLEAR를 받으면 `RESOLVED_WITHOUT_ACTION`으로 종결해야 한다 → Task 10 `test_clear_before_approval_closes_incident`.
3. **같은 alertId RAISE 중복 수신**: 에이전트는 run을 중복 생성하지 않는다 → Task 9 `test_duplicate_raise_creates_one_run`.
4. **cmd-gateway 초당 명령 수 제한**: 2건/초 초과는 거부·audit → Task 6 `test_rate_limit_rejects_third_command_in_same_second`.
5. **PLC TRIP 중 명령**: TRIP 상태에서 FAN_BOOST는 인터록 사유 `INTERLOCK_TRIP`으로 REJECTED → Task 2 `test_command_rejected_while_tripped`.

---

## 파일 구조

```
hyd-iot-edu/
├─ compose.yaml · .env.example · .env · README.md · requirements-dev.txt · pytest.ini
├─ common/hydcommon/            # 모든 파이썬 서비스가 복사해 쓰는 공용 패키지
│   ├─ __init__.py  topics.py (MQTT/Kafka 토픽 이름·빌더)  schemas.py (페이로드 dataclass·검증)
│   ├─ mqtt.py (paho 헬퍼)  kafka.py (aiokafka 헬퍼)  metrics.py (카운터·게이지 텍스트)  timeutil.py (now_iso, parse_iso)
├─ ot/plant-sim/    Dockerfile requirements.txt app/{thermal.py, plc.py, plant.py, edge.py, main.py}
├─ ot/emqx/         (env만 사용, 파일 없음)
├─ ot/fuxa/         build_project.py (→ project.json 생성)  project.json  init.sh  Dockerfile(init)
├─ dmz/connect-ingest/  Dockerfile requirements.txt app/main.py
├─ dmz/cmd-gateway/     Dockerfile requirements.txt app/{validate.py, main.py}
├─ it/redpanda/topics.sh
├─ it/detector/     Dockerfile requirements.txt app/{features.py, cep.py, main.py}
├─ it/connect-sink/ Dockerfile requirements.txt app/main.py
├─ it/timescaledb/init.sql
├─ it/grafana/provisioning/{datasources/ds.yaml, dashboards/dash.yaml, dashboards/hyd-trend.json}
├─ it/prometheus/prometheus.yml
├─ it/neo4j/seed.cypher  templates/{t1_causes.cypher, t2_actions.cypher}  seed.sh
├─ it/agent/        Dockerfile requirements.txt app/{tools/mcp_kg.py, tools/mcp_tsdb.py, tools/mcp_prom.py, guardrail.py, card.py, llm.py, main.py}
├─ it/process/      Dockerfile requirements.txt app/{definition.py, machine.py, main.py}
├─ it/portal/       Dockerfile nginx.conf www/{index.html, app.js, styles.css, layers.js}
├─ tests/  test_thermal.py test_plc.py test_gateway.py test_cep.py test_machine.py test_guardrail.py test_card.py
├─ scripts/ scenario_test.py  smoke.ps1
├─ video/  record_demo.py  narration.py  captions.json
└─ docs/   student-guide.md  topics.md  payload-schemas/*.json  video/(narration.md, mp4)
```

---

### Task 1: 공용 패키지 `common/hydcommon`

**Files:** Create `common/hydcommon/{__init__.py,topics.py,schemas.py,timeutil.py,metrics.py,mqtt.py,kafka.py}`, `requirements-dev.txt`, `pytest.ini`, `tests/test_topics.py`

**Produces:**
- `topics.mqtt_tag(asset_key, name) -> "plant/hyd01/tag/TS1"`, `mqtt_wave`, `mqtt_status`, `mqtt_mode`, `mqtt_cmd_manual`, `mqtt_cmd_auto`, `mqtt_alert`, `asset_key("HYD-01") -> "hyd01"`, `asset_id("hyd01") -> "HYD-01"`.
- Kafka 상수 `K_TAG="plant.tag", K_WAVE="plant.wave", K_STATUS="plant.status", K_FEAT="feat.1s", K_ALERTS="alerts", K_CMD="action.cmd", K_AUDIT="audit"`.
- `timeutil.now_iso() -> str`, `timeutil.parse_iso(s) -> datetime(UTC)`, `timeutil.sim_seconds(wall_seconds, scale)`.
- `metrics.Registry` with `counter(name, help).inc(labels)`, `gauge(name).set(v, labels)`, `render() -> str`.
- `mqtt.make_client(client_id, host, port) -> paho.Client` (v2 API), `kafka.producer(bootstrap)`, `kafka.consumer(bootstrap, topics, group)`.
- `schemas.validate_action_cmd(d) -> list[str]` (에러 목록, 빈 목록이면 OK), `schemas.ACTION_WHITELIST = {"FAN_BOOST","REDUCE_LOAD","RESET"}`, `schemas.ACTION_TO_WRITES = {"FAN_BOOST": ("FanSpeedSP","fan_pct"), "REDUCE_LOAD": ("LoadSP","load_pct"), "RESET": ("Reset", None)}`.

- [ ] Step 1: `tests/test_topics.py` — `asset_key("HYD-01")=="hyd01"`, `mqtt_cmd_auto("hyd01")=="plant/hyd01/cmd/auto"`, `validate_action_cmd({})` returns errors mentioning `cmdId`, valid sample from spec returns `[]`.
- [ ] Step 2: run → fail. Step 3: implement. Step 4: pass.

---

### Task 2: plant-sim 순수 로직 (`thermal.py`, `plc.py`)

**Files:** Create `ot/plant-sim/app/thermal.py`, `ot/plant-sim/app/plc.py`, `tests/test_thermal.py`, `tests/test_plc.py`

**Produces:**
```python
# thermal.py
@dataclass
class UnitState: ts1=48.0; ts2=44.0; ts3=40.0; ts4=42.0; ps1=160.0; ps2=150; ps3=2.0; ps4=1.5; ps5=8.5; ps6=8.2
               eps1=2.8; fs1=9.0; fs2=10.0; vs1=0.6; fan_pct=60.0; load_pct=90.0; cooler_health=1.0
               ce=100.0; cp=1.5; se=60.0; t_amb=25.0
K_HEAT=0.080; K_COOL=0.00135; C=1.0   # dTS1/dt (℃/s, 시뮬레이션 초)
def step(s: UnitState, dt: float, running: bool) -> UnitState   # in-place 갱신 후 반환
def equilibrium_ts1(load, fan, health, t_amb=25) -> float        # = t_amb + K_HEAT*load/(K_COOL*fan*health)
```
평형 검증: (90,60,1.0)→ ≈ 25+7.2/0.081 = 113? → 상수를 다시 맞춘다. 요구: 정상 ≈ 48, 열화(0.35) ≈ 90+ (65 트립 넘김), 조치(팬100·부하80·0.35) ≈ 52. 식 `TS1_eq = t_amb + K_HEAT*load / (K_COOL*fan*health)`: 정상: 23 = K_HEAT*90/(K_COOL*60) → K_HEAT/K_COOL = 15.33. 조치: 27 = K_HEAT*80/(K_COOL*100*0.35) → K_HEAT/K_COOL = 11.8. 두 값이 다르므로 냉각 항에 상수 냉각 `K_BASE`를 추가: `cool = (K_BASE + K_COOL*fan*health)*(TS1 - t_amb)`. 정상: 23·(K_BASE+60·K_COOL·1)=K_HEAT·90; 조치: 27·(K_BASE+35·K_COOL)=K_HEAT·80; 열화(팬60·부하90·0.35): TS1_eq = 25 + K_HEAT·90/(K_BASE+21·K_COOL) 이 ≥ 70이어야 함. K_HEAT=0.05로 두면 정상: K_BASE+60K_COOL=0.1957, 조치: K_BASE+35K_COOL=0.1481 → K_COOL=0.001904, K_BASE=0.0815 → 열화: 25+4.5/(0.0815+0.040)=25+37=62 (65 미달). 열화 목표 health를 0.25로: 조치(팬100·0.25): 27·(K_BASE+25K_COOL)=4 → 시스템 다시 풀기: 정상 0.1957=K_BASE+60K, 조치 0.1481=K_BASE+25K → K=0.00136, K_BASE=0.1141 → 열화(팬60·0.25): 25+4.5/(0.1141+0.0204)=25+33.4=58.4. 여전히 65 미달. **결론: 열화 시 fan 열화도 함께 반영**(쿨러 오염은 냉각 계수에 제곱으로 작용): `cool=(K_BASE + K_COOL*fan*health**2)*(TS1-t_amb)`. health=0.35: health²=0.1225. 정상: K_BASE+60K=0.1957; 조치(팬100·0.1225): K_BASE+12.25K=0.1481 → K=0.000997, K_BASE=0.1359 → 열화(팬60·0.1225): 25+4.5/(0.1359+0.00733)=25+31.4=56.4. 미달. 
**최종 선택(단순·검증 가능):** 열 발생을 부하 제곱에 비례시키고 냉각은 선형: `heat = K_HEAT*(load/100)**2`, `cool = (K_BASE + K_COOL*(fan/100)*health)*(TS1 - t_amb)`. 미지수 3개, 조건 3개(정상 48, 조치 52, 열화 ≥ 68):
 - 정상: 23·(K_BASE+0.6·K_COOL) = 0.81·K_HEAT
 - 조치(팬1.0, 부하0.8, h=0.35): 27·(K_BASE+0.35·K_COOL) = 0.64·K_HEAT
 - 열화(팬0.6, 부하0.9, h=0.35): 25 + 0.81·K_HEAT/(K_BASE+0.21·K_COOL) ≥ 68 → K_BASE+0.21K_COOL ≤ 0.81K_HEAT/43
 K_HEAT=1로 두면: K_BASE+0.6K_COOL=0.03522, K_BASE+0.35K_COOL=0.02370 → K_COOL=0.04608, K_BASE=0.007572 → 열화: K_BASE+0.21K_COOL=0.01725 → TS1_eq = 25+0.81/0.01725 = 72.0 ✔ (65 트립 넘김). 시간상수 C: 열화 후 65 ℃ 도달을 약 20 시뮬레이션-분(1200 s)으로 → dTS1/dt=(heat−cool)/C, 초기 기울기 (0.81−0.01725·23)/C = 0.413/C ℃/s → 17 ℃ 상승에 1200 s면 평균 0.014 ℃/s → C≈25 (지수 접근이라 C=20으로 두고 테스트로 900~1500 s 범위 확인).
 **채택 상수:** `K_HEAT=1.0, K_COOL=0.04608, K_BASE=0.007572, C=20.0, T_AMB=25`.
- 가상 센서: `ce = 100*health*(0.6+0.4*fan/100)` (정상 팬60 → 84, 열화 팬60·0.35 → 29.4, 조치 팬100·0.35 → 35). CE<70 조건이 열화 즉시 성립 → CEP는 TS1>55 AND slope>0도 함께 요구하므로 문제 없음. `cp = (K_BASE + K_COOL*fan/100*health)*(ts1-t_amb)*10` (kW 상당), `se = 100*(1 - 0.35*(load/100)**2)*(1 - max(0,(ts1-50))/100)`.
- 파생: `ts2 = t_amb + (ts1-t_amb)*0.85`, `ts3 = t_amb+(ts1-t_amb)*0.6`, `ts4 = ts2-1`, `ps1 = 155 + 0.3*load + noise`, `eps1 = 0.032*load + 0.0004*(ts1-48)`, `vs1 = 0.55 + 0.004*max(0,ts1-48) + noise`, `fs1 = 10*load/100`, `fs2 = fs1*1.02`. running=False(TRIP): load 0, eps1 0, fs 0, 열 발생 0.

```python
# plc.py
MODES = ("LOCAL","REMOTE_MANUAL","REMOTE_AUTO")
TRIP_TS1 = 65.0; RESET_TS1 = 55.0; LOAD_MIN = 60.0; DEDUP_N = 32
@dataclass
class PlcState: mode="REMOTE_AUTO"; state="RUN"; trip: str|None=None; recent_cmd_ids: deque(maxlen=32); last_cmd_id=None; last_result=None; last_reason=None
@dataclass
class CmdResult: cmd_id: str; result: str  # "DONE"|"REJECTED"; reason: str|None; writes_applied: dict
def check_interlock(plc, unit) -> None            # TS1>65 → state TRIP, trip="OVERTEMP"
def apply_command(plc, unit, cmd: dict, source: str, now) -> CmdResult
    # 순서: 1 모드·출처 (cmd/auto는 REMOTE_AUTO만, cmd/manual은 LOCAL 아님) → "MODE_MISMATCH"
    #       2 만료 expiresAt<now → "EXPIRED"  3 cmdId in recent → "DUPLICATE"
    #       4 쓰기 범위 FanSpeedSP 0..100, LoadSP 60..100, Reset 1 → "OUT_OF_RANGE"
    #       5 인터록: state TRIP이고 Reset 아님 → "INTERLOCK_TRIP"; Reset인데 TS1≥55 → "RESET_TOO_HOT"
    #       통과: unit.fan_pct/load_pct 갱신, Reset → state RUN; manual in REMOTE_AUTO → mode REMOTE_MANUAL
def set_mode(plc, mode, requester) -> bool        # requester in ("FUXA","LOCAL")만 허용
def status_payload(asset, plc, unit, now_iso) -> dict   # 스펙 3.3 status
```
FUXA 단순 페이로드 `{"FanSpeedSP": 80}`는 `normalize_manual(payload) -> cmd dict` 가 `{"cmdId":"FUXA-<epoch ms>","source":"FUXA","writes":[{"res":"FanSpeedSP","v":80}]}`로 바꾼다(만료 없음).

- [ ] Step 1 tests (`test_thermal.py`): `test_normal_equilibrium_about_48` (step 6000 s → 46~50), `test_degraded_reaches_trip_within_20_sim_minutes` (health 0.35, 65 ℃ 도달 시각 600~1500 s), `test_mitigation_equilibrium_about_52` (팬100·부하80·h0.35 → 50~54), `test_ce_drops_below_70_when_degraded`.
- [ ] Step 2 tests (`test_plc.py`): `test_auto_cmd_rejected_in_remote_manual`, `test_expired_cmd_rejected`, `test_duplicate_cmd_id_rejected`, `test_load_below_60_rejected`, `test_command_rejected_while_tripped`, `test_reset_allowed_below_55`, `test_manual_in_auto_reverts_mode`, `test_trip_when_ts1_over_65`, `test_normalize_manual_simple_payload`.
- [ ] Step 3 implement, Step 4 all pass.

---

### Task 3: plant-sim 서비스 (`plant.py`, `edge.py`, `main.py`) + Dockerfile

**Files:** `ot/plant-sim/app/plant.py` (3기 루프, 결함 주입, TIME_SCALE), `edge.py` (MQTT 발행/구독 = EdgeX 역할: tag 1 Hz, wave 1 s 배치, status retained; cmd/manual·cmd/auto·mode 구독 → plc.apply_command/set_mode → status 즉시 재발행), `main.py` (FastAPI: `GET /api/state`, `POST /api/fault {asset, type: cooler_degradation|restore, target_health=0.35, ramp_s=60}`, `POST /api/time_scale {scale}`, `POST /api/mode {asset, mode}`(현장 패널 역할), `GET /healthz`, `/metrics`), Dockerfile, requirements.

루프: 벽시계 1 s마다 `dt = TIME_SCALE` 시뮬레이션 초를 `thermal.step`으로 (내부 서브스텝 1 s × TIME_SCALE회) 진행, 인터록 검사, tag 발행(TS1~4, PS1~6, EPS1, FS1~2, VS1, CE, CP, SE, FanSpeedSP, LoadSP → 이름은 대문자), wave 발행(PS1 100 Hz: `160+0.3*load + 3*sin(2π·25·t)+noise`, EPS1 100 Hz, FS1 10 Hz), status retained.

- [ ] 구현 후 `docker compose --profile ot up plant-sim emqx` → `mosquitto_sub`(파이썬 paho 스크립트 `scripts/mqtt_tail.py`)로 `plant/hyd01/tag/TS1` 1 Hz 확인.

---

### Task 4: FUXA 프로젝트 생성기 + fuxa-init

**Files:** `ot/fuxa/build_project.py` → `ot/fuxa/project.json`, `ot/fuxa/init.sh`, `ot/fuxa/Dockerfile`(curlimages/curl 기반 또는 python:3.12-slim로 POST)

프로젝트 JSON(연구 결과 형식):
- `devices.emqx = {id:"emqx", name:"EMQX-OT", type:"MQTTclient", enabled:true, property:{address:"mqtt://emqx:1883", clientId:"fuxa-ot"}, tags:{...}}`
- 태그(설비 3기 × [TS1, CE, CP, SE, FanSpeedSP, LoadSP, VS1, PS1]): `{id:"hyd01_TS1", name:"HYD-01 TS1", type:"json", address:"plant/hyd01/tag/TS1", memaddress:"v", options:{subs:["v"]}}`
- status 태그: `{id:"hyd01_mode", type:"json", address:"plant/hyd01/status", memaddress:"mode", options:{subs:["mode"]}}`, 같은 식으로 `state`, `result`.
- alert 태그: `{id:"hyd01_alert", type:"json", address:"plant/hyd01/alert", memaddress:"level", options:{subs:["level"]}}` — cmd-gateway가 `plant/{a}/alert`에 `{alertId, pattern, state, level: 2|0, text}`를 retained로 발행(level 2=RAISE, 0=CLEAR).
- 쓰기 태그(FUXA→plant): `{id:"hyd01_cmd_fan", type:"json", address:"plant/hyd01/cmd/manual", memaddress:"FanSpeedSP", options:{subs:["FanSpeedSP"], retain:false}}` (FUXA는 `{FanSpeedSP: v}`를 발행 → plc.normalize_manual), `hyd01_cmd_load` (LoadSP), `hyd01_cmd_reset` (Reset), `hyd01_mode_set` → `plant/hyd01/mode` memaddress `mode`(값 문자열).
- 뷰 1개 "설비 현황" 1280×720: 설비 3기 컬럼. 컬럼당: 제목 텍스트, `svg-ext-gauge_progress`(TS1, ranges minmax 0~100, 색 #4f8df5), `svg-ext-value`(TS1 ℃, CE %, CP, SE, FanSpeedSP, LoadSP, mode, state, result), `svg-ext-gauge_semaphore`(alert: ranges 0→#38c172, 2→#e3342f), `svg-ext-html_input`(팬 설정 → hyd01_cmd_fan), `svg-ext-html_input`(부하 설정 → hyd01_cmd_load), `svg-ext-html_button`(RESET → onSetValue 1 on hyd01_cmd_reset), `svg-ext-html_select`(모드 → hyd01_mode_set, steps REMOTE_MANUAL/REMOTE_AUTO). SVG는 연구에서 얻은 마크업 템플릿을 그대로 좌표만 바꿔 생성한다. item `property.variableId = "emqx^~^hyd01_TS1"`, `variableSrc:"emqx"`, `variable: name`.
- 알람: `{name:"HYD-01 TS1 HIGH", property:{variableId:"emqx^~^hyd01_TS1"}, high:{enabled:true, checkdelay:1, min:60, max:65, text:"HYD-01 유온 높음", group:"HYD-01", bkcolor:"#f6ad55", color:"#000", ackmode:0}, highhigh:{enabled:true, checkdelay:1, min:65, max:200, text:"HYD-01 유온 트립 구간", group:"HYD-01", bkcolor:"#e3342f", color:"#fff", ackmode:0}, low:{enabled:false}, info:{enabled:false}, actions:{enabled:false}}` + `{name:"HYD-01 IT ALERT", property:{variableId:"emqx^~^hyd01_alert"}, highhigh:{enabled:true, checkdelay:1, min:2, max:2, text:"IT 경보: 쿨러 성능 저하 (Flink CEP)", group:"HYD-01"}}`.
- `hmi.layout = {start: view_id, navigation:{mode:"fix", type:"inline", items:[{icon:"home", view: view_id, text:"설비 현황"}]}, header:{}}`; 상단 알람 표시는 FUXA 기본 헤더 알람 아이콘.
- `init.sh`: FUXA `/api/settings`가 200 될 때까지 대기 → `POST /api/project` (Content-Type json) → 로그. 멱등: FUXA 데이터 볼륨을 쓰지 않고 매 기동마다 다시 올린다.

- [ ] `python ot/fuxa/build_project.py` → project.json; `docker compose --profile ot up` → FUXA 1881에서 값·알람·팬 입력 동작 확인(플레이라이트 스크린샷).

---

### Task 5: 백본 — Redpanda·토픽·connect-ingest·TimescaleDB·connect-sink·Grafana

**Files:** `it/redpanda/topics.sh`(rpk topic create 7개), `dmz/connect-ingest/app/main.py`, `it/timescaledb/init.sql`, `it/connect-sink/app/main.py`, `it/grafana/provisioning/*`, compose 서비스.

- ingest: paho 구독 `plant/+/tag/+`, `plant/+/wave/+`, `plant/+/status` → aiokafka produce(키 asset_key). 메시지 변환: tag → `{"asset":"HYD-01","name":"TS1","t":...,"v":...,"q":...}`; wave → `{"asset","sensor","t0","hz","v":[...]}`; status → 원본 + asset. 메트릭 `ingest_messages_total{topic}`, `ingest_last_age_seconds`.
- init.sql: 스펙 4.6 테이블 + `CREATE EXTENSION timescaledb` + hypertable + 연속 집계 `tag_1m` + Grafana 읽기 계정 `grafana/grafana`.
- sink: consume `plant.tag, feat.1s, alerts, plant.status, action.cmd, audit` → 배치 INSERT(tag_1s 100행/0.5 s), alerts upsert(RAISE insert, CLEAR update cleared_at·state), actions upsert(action.cmd insert; plant.status에 cmdId·result 있으면 ack 갱신), audit insert.
- Grafana: env `GF_AUTH_ANONYMOUS_ENABLED=true`, `GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer`, `GF_SECURITY_ALLOW_EMBEDDING=true`, `GF_SERVER_ROOT_URL=http://localhost:3000`. 대시보드 `hyd-trend.json` (uid `hyd-trend`): 변수 `asset`(query `SELECT DISTINCT asset FROM tag_1s`), 패널: ① TS1 (thresholds 60 주황, 65 빨강) ② CE·CP ③ FanSpeedSP·LoadSP ④ 이상 점수(feat_1s score, sensor='TS1') ⑤ 경보 상태 타임라인(state-timeline, alerts) ⑥ 감사 로그 테이블. 주석: `alerts`(RAISE 빨강/CLEAR 초록, 텍스트 pattern), `actions`(파랑, 텍스트 actions::text). 새로고침 5 s, 기본 범위 now-15m.

- [ ] `docker compose --profile ot --profile backbone up -d` → Redpanda Console(8085)에서 plant.tag 흐름, Grafana에서 TS1 추세 확인.

---

### Task 6: cmd-gateway (`validate.py` 순수 + `main.py`)

**Files:** `dmz/cmd-gateway/app/validate.py`, `app/main.py`, `tests/test_gateway.py`

```python
# validate.py
@dataclass
class GatewayState: seen_cmd_ids: deque(maxlen=256); last_status: dict[str, dict]; per_second: dict[int, int]
class Decision(NamedTuple): ok: bool; check: str; reason: str|None; mqtt_payload: dict|None
def validate(cmd: dict, st: GatewayState, now: datetime) -> Decision
  # ① schema (schemas.validate_action_cmd) → check="SCHEMA"
  # ② 액션 화이트리스트 → "WHITELIST"
  # ③ 만료 expiresAt<=now → "EXPIRED"
  # ④ cmdId 중복 → "DUPLICATE"
  # ⑤ last_status[asset].mode != "REMOTE_AUTO" → "MODE"; 초당 2건 초과 → "RATE_LIMIT"
  # ok → mqtt_payload = {"cmdId","source":"HITL","expiresAt","writes":[{"res":"FanSpeedSP","v":100},...]} (ACTION_TO_WRITES 사용)
def alert_to_ot(alert: dict) -> dict   # {"alertId","pattern","state","level": 2 if RAISE else 0,"text"}
```
main: consume `action.cmd` → validate → ok면 MQTT publish cmd/auto(retain False) 아니면 audit produce `{incident, actor:"cmd-gateway", event:"CMD_REJECTED", detail:{check, reason, cmdId}}`; consume `alerts` → publish `plant/{a}/alert` retained; subscribe `plant/+/status` → last_status 갱신; `GET /api/gateway/log` 최근 100 결정; `/metrics` `gateway_decisions_total{result,check}`.

- [ ] tests: `test_valid_cmd_passes_and_maps_writes`, `test_expired_rejected`, `test_duplicate_rejected`, `test_manual_mode_rejected`, `test_unknown_action_rejected`, `test_rate_limit_rejects_third_command_in_same_second`, `test_alert_to_ot_levels`.

---

### Task 7: detector (`features.py`, `cep.py` 순수 + `main.py`)

**Files:** `it/detector/app/{features.py,cep.py,main.py}`, `tests/test_cep.py`

```python
# features.py
def wave_features(v: list[float]) -> dict   # mean, rms, slope(선형회귀 기울기/샘플)
class Baseline: 처음 N=30개 값의 mean/std를 고정(최소 std 0.5); z(x)
def anomaly_score(z_ts1, z_ce, z_vs1) -> float   # min(1, sqrt(mean(z²))/4)
class SlopeWindow(window_sim_s=60): push(t_sim, v) → slope ℃/s
# cep.py
@dataclass
class CepState: phase="IDLE"|"CANDIDATE"|"RAISED"|"CLEARING"; since_sim: float|None; alert_id: str|None; seq: int
def evaluate(st: CepState, asset: str, t_sim: float, ts1: float, ce: float, slope: float, hold_s=60) -> dict|None
  # IDLE: cond(ts1>55 and ce<70 and slope>0) → CANDIDATE(since)  ; CANDIDATE 60 s 유지 → RAISED, return RAISE alert
  # RAISED: clear_cond(ts1<52 and slope<=0) → CLEARING(since); CLEARING 60 s 유지 → IDLE, return CLEAR alert(같은 alertId)
  # 조건 깨지면 CANDIDATE→IDLE, CLEARING→RAISED
def trip_alert(asset, tripped: bool, prev: bool, seq) -> dict|None   # OVERHEAT_TRIP RAISE/CLEAR
```
alertId 형식 `ALT-{asset_key}-{seq:04d}`. main: consume plant.tag(TS1, CE, VS1, FanSpeedSP, LoadSP), plant.wave(PS1), plant.status(state); t_sim = 누적(벽시계 × TIME_SCALE) 또는 tag의 t를 시뮬레이션 시각으로 사용 — plant-sim이 tag `t`를 **시뮬레이션 시각(ISO)**으로 찍고 status에 `sim_t`도 넣는다. detector는 `t`로 슬로프·hold를 계산한다. feat.1s 1초마다 produce `{asset, t, sensor:"TS1", mean, rms, slope, score}` + 파형 특징 `{sensor:"PS1", mean, rms, slope, score:null}`. `GET /api/detector/state`.

- [ ] tests: `test_raise_after_hold_period`, `test_candidate_resets_if_condition_breaks`, `test_clear_after_recovery_hold`, `test_trip_alert_raise_and_clear`, `test_wave_features_slope_positive_for_ramp`.

---

### Task 8: Neo4j 시드와 템플릿

**Files:** `it/neo4j/seed.cypher`, `it/neo4j/templates/t1_causes.cypher`, `t2_actions.cypher`, `it/neo4j/seed.sh`(kg-seed 컨테이너: neo4j 이미지 + cypher-shell, 준비 대기 후 실행, 멱등 MERGE), `docs/topics.md`

스펙 4.8 인스턴스. 노드는 모두 `id` 속성(예 `cause:cooler-fin-fouling`), 라벨은 그림 2. Evidence 노드 속성: `id, name, sql, expect ("lt"|"gt"|"true"), threshold, weight, description`. SQL 템플릿은 `:asset`, `:since` 파라미터 사용, 결과 단일 컬럼 `value`.
- ev:ce-low: `SELECT avg(value) AS value FROM tag_1s WHERE asset=:asset AND name='CE' AND time > now()-interval '2 minutes'` expect lt 70 (w 0.4)
- ev:ts1-rising: `SELECT (max(value)-min(value)) FROM tag_1s WHERE asset=:asset AND name='TS1' AND time>now()-interval '5 minutes'` expect gt 3 (w 0.3)
- ev:fan-normal: `SELECT avg(value) FROM tag_1s WHERE asset=:asset AND name='FanSpeedSP' AND time>now()-interval '2 minutes'` expect gt 50 (w 0.3) → CoolerFinFouling 지지 / FanUnderperformance는 expect lt 50
- ev:load-high: `LoadSP avg > 95` expect gt 95 (HydraulicOverload)
- ev:ambient-high: `TS4 avg > 40` (HighAmbient) — 데모에서 false
Action 속성: `id, code, name, param, min, max, default, kind ("command"|"work_order")`. Step: `id, order, text`. ManualSection: `id, ref, title, excerpt`. Constraint: `id, name, expr`.
T1 (`$pattern`): `MATCH (p:AnomalyPattern {code:$pattern})-[:INDICATES]->(s:Symptom)<-[:CAUSES]-(fm:FailureMode)<-[:CAUSES]-(c:Cause) OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(e:Evidence) RETURN c, fm, collect(e) AS evidence, p.prior AS prior` — 관계 방향 확정: `(c:Cause)-[:CAUSES]->(fm:FailureMode)-[:CAUSES]->(s:Symptom)`, `(p)-[:INDICATES]->(s)`, `(c)-[:EVIDENCED_BY]->(e)`, prior는 관계 속성 `[:CAUSES {weight}]`.
T2 (`$cause`): `MATCH (c:Cause {id:$cause})-[:MITIGATED_BY]->(a:Action) OPTIONAL MATCH (a)-[:REQUIRES]->(k:Constraint) OPTIONAL MATCH (a)-[:FOLLOWS]->(pr:Procedure)-[:HAS_STEP]->(st:Step) OPTIONAL MATCH (st)-[:REFERS_TO]->(m:ManualSection) RETURN a, collect(DISTINCT k) AS constraints, pr, collect(DISTINCT st) AS steps, collect(DISTINCT m) AS manuals ORDER BY a.priority`.

- [ ] `docker compose --profile knowledge up` → Neo4j Browser에서 T1 실행 시 원인 4개, T2 실행 시 FAN_BOOST·REDUCE_LOAD·COOLER_CLEAN_WO와 SOP 4단계·매뉴얼 3절.

---

### Task 9: agent (tools, card, guardrail, llm, main)

**Files:** `it/agent/app/tools/{mcp_kg.py,mcp_tsdb.py,mcp_prom.py}`, `card.py`, `guardrail.py`, `llm.py`, `main.py`, `tests/test_guardrail.py`, `tests/test_card.py`

```python
# card.py (순수)
def rank_causes(t1_rows: list[dict], evidence_results: dict[str, dict]) -> list[dict]
  # score = prior * (Σ w_pass / Σ w) ; evidence_results[ev_id] = {"value", "passed"}
def build_card(incident_id, alert, causes, t2_rows, freshness) -> dict
  # {"incident","alert","freshness","causes":[{"id","name","score","evidence":[{"id","name","value","passed","weight"}]}],
  #  "recommended":[{"code","actionId","name","param","value":default,"paramRange":[min,max],"kind","constraints":[],"sop":{"id","steps":[{"order","text","manual":{"ref","title"}}]}}],
  #  "citations":[node ids], "summary": str}
# guardrail.py (순수)
def check(card) -> list[str]   # 위반 목록: 원인/조치에 id 없음, value가 paramRange 밖, 카드에 "writes"/"cmdId" 키 존재(명령 권한 없음), citations 비어 있음
```
main: consume `alerts` (RAISE만, alertId 중복 무시) → run 생성 → 단계 실행(각 단계 `{"name","status","started","ended","output"}` 기록) → `POST {PROCESS_URL}/api/incidents` → run 완료. `GET /api/agent/runs`, `/api/agent/runs/{id}`, `POST /api/agent/replay/{alertId}`(데모용 재실행). `mcp_prom.freshness(asset)`: TSDB `SELECT max(time) FROM tag_1s WHERE asset=…` 나이 ≤ 60 s면 ok. `llm.summarize(card) -> str`: `ANTHROPIC_API_KEY` 없으면 템플릿 문장, 있으면 anthropic SDK(`claude-sonnet-5`) 3문장.

- [ ] tests: `test_rank_causes_weights_by_passed_evidence`, `test_guardrail_rejects_missing_citation`, `test_guardrail_rejects_out_of_range_value`, `test_guardrail_rejects_command_fields`, `test_build_card_includes_sop_and_manual`, `test_duplicate_raise_creates_one_run` (main의 `RunRegistry.create_if_new(alert_id)`).

---

### Task 10: process (definition, machine 순수, main)

**Files:** `it/process/app/{definition.py,machine.py,main.py}`, `tests/test_machine.py`

```python
# definition.py: BPMN 요소 목록(포탈이 그린다)
STEPS = [("GUIDE_RECEIVED","가이드 카드 수신","event"),("AWAITING_APPROVAL","운전원 승인","userTask"),("CMD_ISSUED","action.cmd 발행","serviceTask"),
 ("AWAITING_ACK","PLC ACK 대기 (30 s)","receiveTask"),("ACKED","ACK DONE","event"),("RE_OBSERVING","15분 재관측","timer"),
 ("RESOLVED","완화 확인","gateway"),("WORK_ORDER_CREATED","작업지시 생성","serviceTask"),("CLOSED","종결","endEvent")]
TERMINAL = {"CLOSED","ESCALATED","REJECTED_BY_OPERATOR","RESOLVED_WITHOUT_ACTION"}
# machine.py
@dataclass
class Incident: id; asset; alert_id; card; state="GUIDE_RECEIVED"; history: list[dict]; cmd_id=None; expires_at=None; approved_by=None; actions=[]; ack=None; reobs_until=None; cleared=False; work_order=None
class Effects: emit_cmd(cmd: dict); emit_audit(evt: dict); set_timer(name, seconds)
def on_card(inc) -> None                          # → AWAITING_APPROVAL
def on_approve(inc, approved_by, actions, now, fx) -> None   # paramRange 검증 → cmd 생성(expiresAt=now+120 s) → CMD_ISSUED → AWAITING_ACK, 타이머 ack 30 s
def on_reject(inc, by, reason, fx) -> None
def on_status(inc, status: dict, now, fx) -> None  # status.cmdId == inc.cmd_id 일 때만: DONE → ACKED → RE_OBSERVING(timer reobs = 900/TIME_SCALE); REJECTED → ESCALATED
def on_alert(inc, alert: dict, fx) -> None         # CLEAR & same alertId: cleared=True; AWAITING_APPROVAL이면 RESOLVED_WITHOUT_ACTION
def on_timer(inc, name, now, latest_ts1: float|None, fx) -> None  # "ack" → AWAITING_ACK면 ESCALATED(ACK_TIMEOUT); "reobs" → cleared and ts1<55 → RESOLVED → WORK_ORDER_CREATED(WO 생성 if card has work_order action) → CLOSED else ESCALATED(MITIGATION_FAILED)
```
main: `POST /api/incidents`(에이전트), `GET /api/incidents`, `GET /api/incidents/{id}`, `POST /api/incidents/{id}/approve`, `/reject`, `GET /api/audit`, `GET /api/definition`, `GET /api/summary`(포탈 홈 상태). Kafka: produce action.cmd·audit, consume plant.status·alerts. 타이머는 asyncio task. 종결 시 Neo4j에 Incident 노드 MERGE(TRIGGERED_BY/DIAGNOSED_AS/RESOLVED_BY) — neo4j 미가동이면 경고만.

- [ ] tests: `test_happy_path_to_closed`, `test_ack_timeout_escalates`, `test_plc_rejected_escalates`, `test_ack_ignores_stale_cmd_id`, `test_clear_before_approval_closes_incident`, `test_reobserve_fails_when_hot`, `test_approve_rejects_out_of_range`.

---

### Task 11: portal (nginx + SPA)

**Files:** `it/portal/nginx.conf`(정적 + `/api/process/ → process:8080/api/`, `/api/agent/ → agent:8091/api/agent/`, `/api/plant/ → plant-sim:8000/api/`, `/api/gateway/ → cmd-gateway:8090/api/gateway/`, `/api/detector/ → detector:8092/api/detector/`, `/health/{svc}` 프록시), `www/index.html`, `app.js`, `layers.js`(L9→L1 레이어 정의: 이름, 역할, 영역, 구성요소, 진입점 URL(localhost 포트), 헬스 URL), `styles.css`. frontend-design 스킬 적용.

탭 4개(스펙 4.11) + `?present=1` 자막 바(`window.setCaption`). 폴링 1 s: `/api/plant/state`, `/api/process/incidents`, `/api/agent/runs`, `/api/gateway/log`, 5 s: 헬스. 승인 다이얼로그에서 파라미터 슬라이더(paramRange). 프로세스 타임라인은 `definition` STEPS를 가로 레인으로 그리고 현재 state 강조 + history 시각.

- [ ] Playwright 스크린샷으로 4개 탭 렌더 확인.

---

### Task 12: compose.yaml · .env · README · student-guide · 통합 시나리오 테스트

**Files:** `compose.yaml`(프로필 ot/backbone/detect/monitor/knowledge/agent/process, 네트워크 ot-net/it-net, 헬스체크, depends_on), `.env.example`(TIME_SCALE=20, COMPOSE_PROFILES=all 목록, ANTHROPIC_API_KEY=), `scripts/scenario_test.py`(httpx로 스펙 6절 assert), `README.md`, `docs/student-guide.md`, `docs/topics.md`, `docs/payload-schemas/*.json`.

- [ ] `docker compose up -d --build` → `python scripts/scenario_test.py` 전 단계 PASS (출력 저장 `docs/test-report.md`).

---

### Task 13: 설명 영상

**Files:** `video/captions.json`(장면: 이동 URL, 자막, 내레이션, 대기 조건), `video/narration.py`(edge-tts `ko-KR-SunHiNeural`, 실패 시 PowerShell SAPI Heami), `video/record_demo.py`(Playwright chromium 1280×720 `record_video_dir`, 장면 실행: 포탈 홈 → FUXA → 열화 주입 → FUXA 알람 → 포탈 인시던트(트레이스) → Neo4j 브라우저 → 승인 → 프로세스 타임라인 → Grafana 감쇠 → 종결; 각 장면 내레이션 길이만큼 대기), 합성: 장면별 mp4(webm→mp4) + wav concat → `docs/video/hyd-iot-edu-demo.mp4`, `docs/video/narration.md`.

- [ ] 영상 파일 생성, 길이·재생 확인(ffprobe), 대표 프레임 3장 추출해 검토.

---

## Self-Review 결과
- 스펙 S1~S9 ↔ Task 11/3/4/6/7/8/9/10/12/13 매핑 확인. S8 부정 시나리오는 Task 12 scenario_test에 포함.
- Review Focus 5개 모두 해당 Task 테스트명으로 고정.
- 타입/이름 일관성: `asset_key/asset_id`, `ACTION_TO_WRITES`, `validate()`, `evaluate()`, `on_*` 이름을 본문 전체에서 동일하게 사용.
