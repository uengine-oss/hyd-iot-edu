# 유압설비 IoT-SCADA 학생용 프로토타입 (hyd-iot-edu) 설계서

작성일: 2026-09-23 · 근거 문서: `유압설비_IoT-SCADA_아키텍처_v3.pdf` 4쪽 "3. 아키텍처 구조도"

## 1. 목적과 성공 기준

**목적.** 강의에서 학생이 자기 노트북(Docker Desktop, 4~8 GB)에 올려 놓고, v3 아키텍처의 L1~L9 레이어와 OT·DMZ·IT 경계를 눈으로 따라갈 수 있는 "설비 모니터링 및 조치 포탈" 완성본을 만든다. Process-GPT 같은 무거운 플랫폼은 학생 환경에 설치가 어렵기 때문에, 같은 레이어 구조와 메시지 계약을 지키되 구성요소를 가벼운 파이썬 서비스로 대체한 **학생용 간소화판**을 구현한다.

**성공 기준 (전부 프론트엔드에서 확인 가능해야 한다).**

| # | 기준 | 확인 위치 |
|---|------|----------|
| S1 | `docker compose up -d` 한 번으로 전체 스택이 뜨고, 포탈 홈에서 L1~L9 각 레이어의 구성요소 진입점(링크)과 상태(초록/빨강)가 보인다 | 포탈 홈 |
| S2 | 포탈 시나리오 콘솔에서 "쿨러 열화 주입"을 누르면 HYD-01 유온(TS1)이 상승하고, SCADA(FUXA)에 값 변화와 알람이 표시된다 | FUXA, 포탈 |
| S3 | 탐지기가 `alerts RAISE`를 내면 명령 게이트웨이가 OT `plant/hyd01/alert`로 중계하고 FUXA 알람 목록에 나타난다 | FUXA 알람 |
| S4 | 에이전트가 온톨로지(Neo4j)에서 원인 후보(T1)와 조치·SOP·매뉴얼 경로(T2)를 꺼내고, 시계열 증거를 대조해 가이드 카드를 만든다. 포탈에서 단계별 트레이스(신선도 → T1 → 증거 → T2 → 가드레일)가 보인다 | 포탈 경보·조치 |
| S5 | 운전원이 포탈에서 승인(파라미터 수정 가능)하면 `action.cmd` → 게이트웨이 검증 5종 → `cmd/auto` → PLC 검증 → `status ACK DONE`이 순서대로 프로세스 타임라인에 찍힌다 | 포탈 프로세스 |
| S6 | 조치 후 TS1이 내려가고 `alerts CLEAR`가 나며, 재관측 타이머 통과 후 작업지시(WO) 생성·종결된다 | 포탈, Grafana |
| S7 | Grafana 대시보드에 TS1·CE·이상점수 추세와 경보(RAISE/CLEAR)·조치(승인) 주석이 겹쳐 보여, 조치 이후 이상 징후가 감쇠하는 모습이 보인다 | Grafana |
| S8 | 부정 시나리오: PLC 모드가 REMOTE_MANUAL이면 게이트웨이가 거부하고 `audit`에 사유가 남는다. 만료된 명령은 PLC가 REJECTED로 응답한다. TS1 > 65 ℃면 인터록 트립한다 | 포탈, 감사 로그 |
| S9 | 위 흐름을 실제로 수행하면서 녹화한 설명 영상(한국어 내레이션, mp4)이 `docs/video/`에 있다 | 파일 |

## 2. 학생용 간소화 원칙

1. **레이어 이름·역할·메시지 계약은 v3 그대로.** MQTT 토픽(5.1절), Kafka 토픽(5.2절), 페이로드(7.3절), 운전 모드(7.1절), 검증 5종(7.2절)을 그대로 쓴다. 학생이 나중에 실제 제품으로 바꿔 끼울 수 있게 한다.
2. **무거운 제품은 같은 이름의 작은 파이썬 서비스로 대체한다.** 아래 표. 가벼운 실제 제품(EMQX, FUXA, Redpanda, TimescaleDB, Grafana, Neo4j)은 그대로 쓴다.
3. **컨테이너 하나 = 레이어 역할 하나.** 서비스 이름이 곧 v3 그림의 박스 이름이다.
4. **LLM 없이 동작한다.** 에이전트는 온톨로지 그래프와 SQL 증거만으로 결정론적 가이드 카드를 만들고, `ANTHROPIC_API_KEY`가 있으면 카드 설명문만 LLM이 다듬는다.
5. **시간 가속 ×20 (`TIME_SCALE`).** 시뮬레이터·재관측 타이머·CEP 시간창이 같은 배율을 읽는다.

### 2.1 v3 구성요소 ↔ 학생용 대체

| L | v3 구성요소 | 학생용 컨테이너 | 영역 | 비고 |
|---|-------------|----------------|------|------|
| L1 | hyd-sim, soft-plc, 고속 DAQ | `plant-sim` (Python) | OT | 물리 모델 3기 + soft-PLC(인터록·모드·명령 검증·CE/CP/SE) + 파형 1초 배치. EdgeX 역할(표준 토픽 발행)을 `edge.py` 모듈이 맡는다 |
| L2 | EdgeX, EMQX | `emqx` (실제) | OT | 대시보드 18083이 진입점 |
| L6 (OT) | FUXA | `fuxa` (실제) + `fuxa-init` | OT | 프로젝트 JSON 자동 주입(태그·뷰·알람) |
| L3 DMZ | Connect ingest | `connect-ingest` (Python) | DMZ | MQTT → Kafka 단방향 복제 |
| L3 DMZ | 명령 게이트웨이 | `cmd-gateway` (Python) | DMZ | 검증 5종, alerts → OT alert 중계 |
| L3 IT | Kafka | `redpanda` + `redpanda-console` (실제) | IT | Kafka API 호환, 콘솔 8085가 진입점 |
| L4 | Flink 특징·ONNX·CEP | `detector` (Python) | IT | 1초 특징, 이상 점수(z-score 기반 재구성 오차 대용), CEP 상태기계 → RAISE/CLEAR |
| L5 | Connect sink, TimescaleDB | `connect-sink` (Python), `timescaledb` (실제) | IT | upsert |
| L6 (IT) | Grafana, Prometheus | `grafana` (실제), `prometheus` (실제, 선택 프로필) | IT | 대시보드 프로비저닝 |
| L7 | Neo4j + n10s + Cypher 템플릿 | `neo4j` (실제) + `kg-seed` | IT | 그림 2 스키마 인스턴스 적재, T1/T2 템플릿 |
| L8 | LangGraph, MCP 도구, LiteLLM, 가드레일 | `agent` (Python) | IT | `tools/mcp_kg.py · mcp_tsdb.py · mcp_prom.py`(읽기 전용) + `guardrail.py` |
| L9 | BPMN 엔진 (Process GPT) | `process` (Python) | IT | 인시던트 상태기계: 승인 → action.cmd → ACK → 재관측 → WO → 종결 |
| L9 | 운전원 가이드 앱 | `portal` (nginx + 정적 SPA) | IT | 진입점 허브 + 시나리오 콘솔 + 경보·조치 + 추세 |

## 3. 아키텍처와 데이터 흐름

```
[OT · ot-net]  plant-sim ──pub tag/wave/status──▶ emqx ◀──sub tag/status/alert── fuxa
                  ▲ sub cmd/manual · cmd/auto · mode      │
[DMZ · 양쪽]      │                          connect-ingest (MQTT→Kafka ↑)   cmd-gateway (Kafka→MQTT ↓, 검증 5종)
[IT · it-net]     └────────── redpanda: plant.tag · plant.wave · plant.status · feat.1s · alerts · action.cmd · audit
                          detector(L4) ─ feat.1s / alerts ─▶ connect-sink(L5) ─▶ timescaledb ─▶ grafana
                          agent(L8): alerts ▶ mcp_prom 신선도 ▶ mcp_kg T1 ▶ mcp_tsdb 증거 ▶ mcp_kg T2 ▶ 가드레일 ▶ process API
                          process(L9): 승인 ▶ action.cmd ▶ (plant.status ACK) ▶ 재관측 ▶ (alerts CLEAR) ▶ WO ▶ 종결 · audit
                          portal: /api/* 리버스 프록시 → process · agent · plant-sim · cmd-gateway · detector
```

OT ↔ IT를 직접 잇는 컨테이너는 `connect-ingest`, `cmd-gateway` 둘뿐이다(v3의 세 번째인 prom-agent는 선택 프로필 `monitor`에서 Prometheus가 직접 파이썬 서비스 `/metrics`를 긁는 것으로 단순화한다. 이 단순화는 문서에 명시한다).

### 3.1 MQTT 토픽 (v3 5.1절 그대로)

`plant/{asset}/tag/{name}` (1 Hz `{t,v,q}`), `plant/{asset}/wave/{sensor}` (1초 배치 `{t0,hz,v[]}`), `plant/{asset}/status` (retained), `plant/{asset}/mode`, `plant/{asset}/cmd/manual`, `plant/{asset}/cmd/auto`, `plant/{asset}/alert`. asset은 `hyd01`~`hyd03`.

### 3.2 Kafka 토픽 (v3 5.2절 그대로)

`plant.tag`, `plant.wave`, `plant.status`, `feat.1s`, `alerts`, `action.cmd`, `audit`. 키는 asset. 파티션 1(프로토타입).

### 3.3 페이로드

- **tag**: `{"t":"2026-09-23T10:12:30Z","v":48.2,"q":"good"}`
- **status** (retained): `{"asset":"HYD-01","mode":"REMOTE_AUTO","state":"RUN|TRIP","trip":null,"fan_pct":60,"load_pct":90,"cmdId":"...","result":"DONE|REJECTED","reason":"...","t":"..."}` — ACK는 status의 `cmdId/result` 갱신으로 올라간다(v3 7.3절).
- **alerts**: `{"alertId":"ALT-0923-0001","asset":"HYD-01","pattern":"COOLER_DEGRADATION","severity":"HIGH","state":"RAISE|CLEAR","t":"...","evidence":{"ts1":58.4,"ce":61.0,"ts1_slope":0.08,"score":0.83}}`
- **action.cmd**: v3 7.3절 예시 그대로 (`cmdId, asset, incident, source:"HITL", actions[], approvedBy, expiresAt`).
- **cmd/auto** (게이트웨이 변환 후): `{"cmdId","source":"HITL","expiresAt","writes":[{"res":"FanSpeedSP","v":100},{"res":"LoadSP","v":80}]}`.
- **audit**: `{"incident","t","actor":"cmd-gateway|process|agent|operator|plc","event","detail":{}}`.

## 4. 구성요소 상세

### 4.1 plant-sim (L1, OT)

- 설비 3기 `HYD-01~03`. 각 설비: 1초 시뮬레이션 스텝 × `TIME_SCALE`.
- **상태 변수**: `ts1`(유온 ℃), `ts2~ts4`(유온 파생), `ps1~ps6`(압력 bar), `eps1`(모터전력 kW), `fs1,fs2`(유량), `vs1`(진동), `fan_pct`, `load_pct`, `cooler_health`(1.0 정상), `mode`, `state`.
- **열 모델**: `dTS1/dt = (k_heat·load − k_cool·fan·cooler_health·(TS1 − T_amb)) / C`. 상수는 정상(부하 90·팬 60·health 1.0)에서 약 48 ℃ 평형, 열화(health 0.35)에서 약 20 시뮬레이션-분 뒤 65 ℃ 도달, 조치(팬 100·부하 80)에서 약 52 ℃ 평형이 되도록 정한다. 단위 테스트로 이 세 평형점을 고정한다.
- **가상 센서**: `CE = 100·cooler_health·(0.6 + 0.4·fan/100)`, `CP = k·fan·cooler_health·(TS1 − TS2)`, `SE = f(load, ps1)`.
- **결함 주입 API** (`POST /api/fault`): `cooler_degradation`(health를 목표값까지 선형 감소), `restore`, `set_time_scale`. `GET /api/state`.
- **soft-PLC 규칙**: 모드 `LOCAL / REMOTE_MANUAL / REMOTE_AUTO`(기본 REMOTE_AUTO — 데모용, 문서에 명시). `cmd/manual`은 REMOTE_MANUAL·REMOTE_AUTO에서 허용하고 REMOTE_AUTO에서 수동 조작이 오면 REMOTE_MANUAL로 자동 복귀. `cmd/auto`는 REMOTE_AUTO에서만. 검증: 출처·모드 일치 → 만료(expiresAt) → 최근 cmdId 32개 중복 → 쓰기 범위(Fan 0~100, Load 60~100) → 하드 인터록(TS1 > 65 트립, 최소 부하 60). 결과는 status로 ACK.
- **인터록**: TS1 > 65 ℃ → `state=TRIP`, 펌프 정지(load 0, eps1 0). `RESET` 쓰기는 TS1 < 55일 때만.
- **파형**: `ps1` 100 Hz 리플(펌프 회전 주파수) 1초 배치, `eps1` 100 Hz, `fs1` 10 Hz.

### 4.2 emqx (L2) · fuxa (L6 OT)

- EMQX 5: 익명 허용(학생용), 대시보드 admin/public. ACL은 문서화만(선택 과제).
- FUXA: `fuxa-init`가 기동 후 `/api/project`에 프로젝트 JSON을 올린다. 내용: MQTT 디바이스(`emqx:1883`) + 설비 3기의 태그(TS1, CE, CP, SE, fan, load, mode, state, alert) + 뷰 1개(설비 3기 카드: 유온 게이지·CE·팬·부하·모드, 알람 배너) + 알람 정의(TS1 > 60 경고, TS1 > 65 트립, `alert` 태그의 RAISE 상태). FUXA에서 수동 조작(팬 슬라이더 → `cmd/manual`)과 모드 전환(`mode` 토픽) 버튼을 둔다.
- FUXA 프로젝트 형식은 구현 단계에서 이미지 내부 소스로 확인한다. 프로젝트 자동 주입이 실패하면 `fuxa/project.json`을 수동 Import하는 절차를 README에 둔다(대체 경로).

### 4.3 connect-ingest · cmd-gateway (L3 DMZ)

- **connect-ingest**: `plant/+/tag/#`, `plant/+/wave/#`, `plant/+/status` 구독 → 각각 `plant.tag`(`{asset,name,t,v,q}`), `plant.wave`, `plant.status`로 produce. 키 asset. Prometheus 메트릭 `ingest_messages_total`, `ingest_last_event_age_seconds`.
- **cmd-gateway**: `action.cmd` 소비 → 검증 5종 ① JSON 스키마 ② 액션 화이트리스트(`FAN_BOOST, REDUCE_LOAD, RESET`) ③ 만료 ④ cmdId 중복 ⑤ 최근 status의 모드가 REMOTE_AUTO + 초당 명령 수 ≤ 2 → 통과 시 `plant/{a}/cmd/auto`(retain=false), 실패 시 폐기 + `audit`에 거부 사유. `alerts` 소비 → `plant/{a}/alert`(retain=true, 표시 전용). `GET /api/gateway/log` 최근 결정 목록.

### 4.4 redpanda · redpanda-console (L3 IT)

단일 노드, `--memory 512M --overprovisioned --smp 1`. 토픽은 `topic-init` 스크립트가 생성(보존 기간은 문서 값 그대로 설정하되 프로토타입에선 의미만 둔다).

### 4.5 detector (L4)

- `plant.tag`·`plant.wave` 소비. 설비별 1초 특징: 파형 `mean·rms·slope`, 태그 `ts1_slope`(60 시뮬레이션-초 이동 기울기), `ce`.
- **이상 점수(오토인코더 대용)**: 정상 기준 통계(처음 60초 또는 고정 baseline)에 대한 TS1·CE·VS1 z-score의 RMS를 0~1로 정규화. 학생 문서에 "ONNX 오토인코더 자리"로 명시.
- **CEP (MATCH_RECOGNIZE 대용 상태기계)**: `COOLER_DEGRADATION` RAISE 조건 = TS1 > 55 AND CE < 70 AND ts1_slope > 0 이 60 시뮬레이션-초 지속. CLEAR 조건 = TS1 < 52 AND ts1_slope ≤ 0 이 60 시뮬레이션-초 지속. `OVERHEAT_TRIP` = status.state == TRIP 즉시 RAISE, RUN 복귀 시 CLEAR.
- `feat.1s`, `alerts` produce. `GET /api/detector/state`.

### 4.6 connect-sink · timescaledb (L5)

테이블: `tag_1s(time, asset, name, value)` hypertable, `feat_1s(time, asset, sensor, mean, rms, slope, score)` hypertable, `alerts(alert_id PK, asset, pattern, severity, state, raised_at, cleared_at, evidence jsonb)` upsert, `actions(cmd_id PK, incident, asset, actions jsonb, approved_by, issued_at, ack_result, ack_at)` upsert, `audit(id, time, incident, actor, event, detail jsonb)`. 1분 연속 집계 뷰 `tag_1m`.

### 4.7 grafana (L6 IT)

프로비저닝: 데이터소스 TimescaleDB, 대시보드 "HYD 설비 추세" (변수 asset): TS1(임계 60/65 선), CE, 팬·부하 SP, 이상 점수, 경보 상태 타임라인; 주석 소스 `alerts`(RAISE 빨강/CLEAR 초록), `actions`(승인 파랑). 익명 Viewer + iframe 임베드 허용(포탈 추세 탭에 임베드).

### 4.8 neo4j + kg-seed (L7)

그림 2 스키마 라벨·관계를 그대로 쓴다. 시드 인스턴스(HYD-01 기준, 02·03은 동일 구조):
- Asset HYD-01 → Component Cooler, Pump, Motor, Valve, Reservoir; Sensor TS1~4, PS1~6, EPS1, FS1~2, VS1, CE, CP, SE; Actuator CoolerFan(`FanSpeedSP`), PumpLoad(`LoadSP`).
- AnomalyPattern COOLER_DEGRADATION → INDICATES Symptom OilTempRising, CoolerEfficiencyDrop → FailureMode CoolerPerformanceLoss → CAUSES Cause: CoolerFinFouling(가중 0.5), FanUnderperformance(0.3), HighAmbient(0.1), HydraulicOverload(0.1). 각 Cause EVIDENCED_BY Evidence(SQL 템플릿 + 기대 조건). 예: CoolerFinFouling → "CE < 70 AND CP 감소 AND 팬 정상 회전(fan_pct ≥ 50)", FanUnderperformance → "fan_pct 지시값 대비 CP 급감".
- Cause MITIGATED_BY Action: FAN_BOOST(paramRange fan_pct 80~100), REDUCE_LOAD(load_pct 60~90), COOLER_CLEAN_WO(작업지시), Action REQUIRES Constraint(TS1max 65, LoadMin 60), Action FOLLOWS Procedure SOP-COOL-01 HAS_STEP Step 1~4, Step REFERS_TO ManualSection(예: "HM-7.3 쿨러 팬 속도 상향", "HM-9.1 부하 저감").
- Incident 노드는 process가 종결 시 기록(TRIGGERED_BY Alert, DIAGNOSED_AS Cause, RESOLVED_BY Action).
- 템플릿 T1/T2는 `it/neo4j/templates/*.cypher`에 두고 `mcp_kg`가 읽는다. Neo4j Browser(7474)가 진입점.

### 4.9 agent (L8)

- `alerts`(state=RAISE) 소비 → 실행(run) 생성. 단계와 산출물을 `runs[run_id].steps[]`에 기록해 `GET /api/agent/runs/{id}`로 노출.
  1. `mcp_prom.freshness(asset)` — TSDB 최신 tag 시각과 ingest 메트릭. 60 s 초과면 "데이터 신뢰 불가" 카드 제출 후 종료.
  2. `mcp_kg.t1_causes(pattern)` — 원인 후보 + Evidence 규칙.
  3. `mcp_tsdb.evaluate(evidence)` — SQL 템플릿 실행 → 각 증거 pass/fail·값. 원인 점수 = 가중치 × 증거 통과율.
  4. `mcp_kg.t2_actions(cause)` — 조치(paramRange) → SOP 단계 → 매뉴얼 절.
  5. 가이드 카드 조립: `{incident, alert, causes[{id,name,score,evidence[]}], recommended[{code,params,paramRange,sop_steps[],manual[]}], citations[]}`. LLM 있으면 `summary` 문장 생성.
  6. `guardrail.check(card)` — 모든 cause/action에 노드 id 인용, 파라미터가 paramRange 안, 카드에 명령 필드 없음. 실패면 반려(run.status=REJECTED_BY_GUARDRAIL)하고 제출하지 않는다.
  7. `POST process/api/incidents` (에이전트의 유일한 쓰기).
- LLM: `llm.py` — `ANTHROPIC_API_KEY` 없으면 템플릿 문장. 있으면 Claude에게 카드 JSON을 주고 운전원용 3문장 요약을 받는다.

### 4.10 process (L9)

- 인시던트 상태기계: `GUIDE_RECEIVED → AWAITING_APPROVAL → CMD_ISSUED → AWAITING_ACK → ACKED → RE_OBSERVING → RESOLVED → WORK_ORDER_CREATED → CLOSED`, 실패 경로 `ACK_TIMEOUT / REJECTED / MITIGATION_FAILED → ESCALATED`, 운전원 거부 `REJECTED_BY_OPERATOR`.
- `POST /api/incidents/{id}/approve {approvedBy, actions[{code,params}]}` — 파라미터를 카드의 paramRange로 재검증, `expiresAt = now + 120 s`, `action.cmd` produce, `audit`.
- `plant.status` 소비로 ACK 대조(30 s 타임아웃), `alerts` 소비로 CLEAR 대조. 재관측 타이머 `15 min / TIME_SCALE`. 통과 조건: CLEAR 수신 + 최신 TS1 < 55.
- 종결 시 `COOLER_CLEAN_WO` 작업지시 생성(카드에 WO 액션이 있을 때), Neo4j에 Incident 노드 기록, `audit`.
- 프로세스 정의는 `process/definition.py`에 BPMN 요소(태스크·게이트웨이·타이머)를 목록으로 적어 포탈이 그대로 그린다("학생용 미니 BPMN").

### 4.11 portal (L9 guide-app)

nginx가 정적 SPA를 서빙하고 `/api/process, /api/agent, /api/plant, /api/gateway, /api/detector`를 각 서비스로, `/grafana/`를 Grafana로 프록시한다. 탭:
1. **아키텍처·진입점**: L9→L1 스택. 각 레이어 카드에 구성요소, 영역 배지(OT/DMZ/IT), 진입점 링크(FUXA 1881, EMQX 18083, Redpanda Console 8085, Grafana 3000, Neo4j 7474, Prometheus 9090, 각 파이썬 서비스 `/docs`), 상태 점(헬스 폴링).
2. **시나리오 콘솔**: 설비 3기 미니 HMI(TS1·CE·팬·부하·모드·상태·PS1 파형 스파크라인), 버튼: 쿨러 열화 주입 / 복구 / 모드 전환 / 시간 배율 / 수동 명령 / 부정 시나리오(REMOTE_MANUAL 거부, 만료 명령).
3. **경보·조치**: 경보 목록, 인시던트 카드(에이전트 트레이스 스테퍼, 원인 순위와 증거, 권장 조치·SOP·매뉴얼 인용, 승인/수정/거부), 프로세스 타임라인(미니 BPMN 레인에 현재 단계 하이라이트), 감사 로그.
4. **추세**: Grafana 패널 iframe.
5. `?present=1`이면 하단 자막 바를 켜고 `window.setCaption(text)`로 제어(영상 녹화용).

### 4.12 monitor (선택 프로필)

Prometheus가 `connect-ingest, cmd-gateway, detector, agent, process`의 `/metrics`를 긁는다. 규칙 1개(ingest 지연 > 30 s). Alertmanager·Mailpit은 학생 확장 과제로 README에 남긴다.

## 5. Compose 프로필과 구현 순서 (v3 11절 대응)

| 단계 | 프로필 | 컨테이너 | 완료 기준 |
|------|--------|----------|-----------|
| M1 | ot | plant-sim, emqx, fuxa, fuxa-init | FUXA에 1 Hz 값, 수동 조작으로 팬 변경, 65 ℃ 트립 |
| M2 | backbone | redpanda, redpanda-console, topic-init, connect-ingest, connect-sink, timescaledb, grafana | Grafana에 tag_1s 추세, plant.wave는 Kafka에만 |
| M3 | detect | detector, cmd-gateway | 열화 주입 → alerts RAISE → FUXA 알람, 복구 → CLEAR |
| M4 | monitor | prometheus | 서비스 메트릭 수집 |
| M5 | knowledge | neo4j, kg-seed | T1 원인 후보, T2 조치 경로 |
| M6 | agent | agent | 근거 인용 가이드 카드, 인용 빠지면 가드레일 반려 |
| M7 | process | process, portal | 승인 → cmd/auto → ACK → 하강 → 재관측 → 종결, REMOTE_MANUAL 거부 |

`.env`의 `COMPOSE_PROFILES=ot,backbone,detect,monitor,knowledge,agent,process`로 기본은 전체 기동.

## 6. 테스트

- **단위(pytest)**: plant 열 모델 평형점 3개, PLC 명령 검증(모드·만료·중복·범위·인터록), 게이트웨이 검증 5종, 탐지기 CEP 상태기계(RAISE/CLEAR 시점), 프로세스 상태기계(정상·ACK 타임아웃·거부), 가드레일(인용 누락 반려). IO 없는 순수 모듈로 분리해 테스트한다.
- **통합(`scripts/scenario_test.py`)**: 스택 기동 후 API로 시나리오를 돌리며 단계마다 assert: RAISE 발생, FUXA alert 태그 갱신(EMQX 구독으로 확인), 가이드 카드 생성, 승인, ACK DONE, TS1 하강, CLEAR, CLOSED, tag_1s·alerts·actions 행 존재. 부정 시나리오 2개 포함.
- **영상(`video/record_demo.py`)**: Playwright가 통합 시나리오를 포탈에서 실제 수행하며 녹화. 자막 + 한국어 내레이션(edge-tts, 오프라인 대체 Windows Heami) → ffmpeg(imageio-ffmpeg) 합성 → `docs/video/hyd-iot-edu-demo.mp4`. 내레이션 대본 `docs/video/narration.md`.

## 7. 저장소 구조

```
hyd-iot-edu/
├─ compose.yaml  .env.example  README.md
├─ ot/   plant-sim/  emqx/  fuxa/(project.json, init.sh)
├─ dmz/  connect-ingest/  cmd-gateway/
├─ it/   redpanda/(topics.sh)  detector/  connect-sink/  timescaledb/(init.sql)
│        grafana/(provisioning)  prometheus/  neo4j/(seed.cypher, templates/)  agent/  process/  portal/
├─ common/  (공유 파이썬: 토픽 이름, 페이로드 스키마, kafka/mqtt 헬퍼)  — 각 서비스 Dockerfile이 복사
├─ tests/   (pytest 단위)   scripts/ (scenario_test.py, smoke.sh)   video/ (record_demo.py)
└─ docs/    student-guide.md  topics.md  payload-schemas/  video/
```

## 8. 범위 밖 (문서에 명시)

EdgeX/Modbus 실제 연동, Flink/ONNX 실제 모델, Kafka Connect 커넥터, LangGraph/MCP 서버 프로세스 분리, LiteLLM, Process-GPT/Flowable, EMQX ACL 강제, MinIO, Alertmanager/Mailpit, prom-agent. 각각 "실제 제품으로 바꾸려면" 절에서 연결 지점을 설명한다.
