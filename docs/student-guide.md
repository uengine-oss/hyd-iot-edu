# 학생 가이드 — hyd-iot-edu를 읽고, 돌리고, 바꿔 끼우기

이 문서는 v3 설계서(`유압설비_IoT-SCADA_아키텍처_v3.pdf`)를 옆에 두고 읽는 것을 전제로 한다. 설계서가 "무엇을, 왜"라면 이 문서는 "이 저장소에서 어디를 보면 되는가"다.

## 1. 준비물

- Docker Desktop (메모리 4 GB 이상 권장, 이 스택은 약 2.5 GB를 쓴다), Python 3.12 (테스트·영상용)
- 첫 실행: `cp .env.example .env` → `docker compose up -d --build` (이미지 내려받기 포함 5~10분)
- 확인: http://localhost:8088 홈 화면의 상태 점이 모두 초록이면 준비 끝

## 2. 레이어별로 코드 찾아가기

| L | 설계서 구성요소 | 이 저장소 | 읽을 파일 (순서대로) |
|---|-----------------|-----------|----------------------|
| L1 | hyd-sim · soft-plc · 고속 DAQ | `ot/plant-sim/plantsim/` | `thermal.py`(열 모델 3식) → `plc.py`(모드·검증·인터록) → `plant.py`(3기 루프·결함 주입) → `edge.py`(MQTT) |
| L2 | EdgeX · EMQX | `edge.py` + `compose.yaml`의 `emqx` | 토픽 이름은 `common/hydcommon/topics.py` 한 곳 |
| L6(OT) | FUXA | `ot/fuxa/build_project.py` | 태그 = MQTT 토픽 + JSON 키, 알람 정의, 쓰기 태그(cmd/manual) |
| L3(DMZ) | Connect ingest / 명령 게이트웨이 | `dmz/connect-ingest/app/main.py`, `dmz/cmd-gateway/gw/validate.py` | 게이트웨이 검증 5종은 `validate()` 한 함수 |
| L3(IT) | Kafka | `it/redpanda/topics.sh` | 토픽 7개와 보존 기간 |
| L4 | Flink 특징·ONNX·CEP | `it/detector/det/features.py`, `cep.py` | `cep.evaluate()` 상태기계 = MATCH_RECOGNIZE 자리 |
| L5 | Connect sink · TimescaleDB | `it/connect-sink/app/main.py`, `it/timescaledb/init.sql` | 테이블 5개, 1분 연속 집계 |
| L6(IT) | Grafana · Prometheus | `it/grafana/build_dashboard.py`, `it/prometheus/` | 주석 SQL 3개(RAISE/CLEAR/승인 조치) |
| L7 | Neo4j · 템플릿 | `it/neo4j/seed.cypher`, `templates/t1_causes.cypher`, `t2_actions.cypher` | 그림 2 관계가 주석에 그대로 |
| L8 | LangGraph · MCP · LiteLLM · 가드레일 | `it/agent/agentsvc/` | `main.py`의 `pipeline()` 7단계 → `tools/mcp_*.py`(읽기 전용) → `card.py` → `guardrail.py` → `llm.py`(선택) |
| L9 | BPMN 엔진 · guide-app | `it/process/procsvc/definition.py`, `machine.py`, `it/portal/www/app.js` | 상태기계는 IO가 없어 `tests/test_machine.py`로 읽는 게 가장 빠르다 |
| L7~L9 전사 판단 | 온톨로지 기반 의사결정 · ERP/MES 연계 | `it/neo4j/seed_enterprise.cypher`, `it/agent/agentsvc/decision.py`, `enterprise.py`, `it/process/procsvc/decisions.py`, `it/enterprise-sim/`, `it/portal/www/enterprise.js` | 설계와 시나리오 설명은 `docs/l7-l9-ontology-decisions.md`. 판단 엔진은 IO가 없어 `tests/test_decision.py`로 읽는 게 가장 빠르다 |

## 3. 메시지 계약 (설계서 5·7절 그대로)

`docs/topics.md`와 `docs/payload-schemas/`에 정리했다. 핵심만:

- OT MQTT: `plant/{asset}/tag/{name}` `{t,v,q}` · `wave/{sensor}` `{t0,hz,v[]}` · `status`(retained, ACK 포함) · `mode` · `cmd/manual` · `cmd/auto` · `alert`
- Kafka: `plant.tag` `plant.wave` `plant.status` `feat.1s` `alerts` `action.cmd` `audit` (키 = asset)
- 운전 모드: `LOCAL` / `REMOTE_MANUAL` / `REMOTE_AUTO`. HITL 조치(`cmd/auto`)는 `REMOTE_AUTO`에서만. 수동 조작이 오면 `REMOTE_MANUAL`로 복귀.
- 검증: 게이트웨이 5종(스키마·화이트리스트·만료·중복·모드+속도) → PLC(모드/출처·만료·중복 32개·범위·인터록)

학생용 단순화 한 가지: FUXA는 `cmd/manual`에 `{"FanSpeedSP": 80}`처럼 값만 보낸다. PLC(`plc.normalize_manual`)가 `cmdId`(FUXA-…)와 `source:"FUXA"`를 붙인다.

## 4. 시나리오를 손으로 따라가기

1. **결함 시나리오 시뮬레이션** → HYD-01 "쿨러 열화 주입". `plant-sim`의 `cooler_health`가 300 시뮬레이션-초 동안 0.43으로 내려간다.
2. FUXA(1881)에서 TS1이 오르고 CE가 떨어지는 것을 본다. 60 ℃에서 FUXA 자체 알람(high), 65 ℃면 트립.
3. `docker compose logs -f detector`에서 `ALERT RAISE COOLER_DEGRADATION`을 본다. 조건은 `cep.py` 맨 위 주석.
4. Redpanda Console(8085) `alerts` 토픽에 메시지가 있고, `cmd-gateway` 로그에 `alert relayed`가 있다. FUXA 표시등이 빨강.
5. `docker compose logs -f agent` 또는 포탈 **이상 확인 & 조치**의 트레이스: freshness → t1_causes → evidence → rank → t2_actions → card → guardrail → submit.
6. Neo4j Browser(7474)에서 `templates/t1_causes.cypher`를 `:param pattern => 'COOLER_DEGRADATION'`, `:param asset => 'HYD-01'`로 실행해 같은 결과를 확인.
7. 포탈에서 승인. `process` 로그에 `CMD_PUBLISHED`, `cmd-gateway` 로그에 `PASS`, `plant-sim` 로그에 `cmd/auto ... DONE`.
8. Grafana(3000)에서 TS1 하강과 주석. ACK 후 45초(15분 ÷ 20)에 재관측 판정: `alerts CLEAR` 수신 ∧ TS1 < 55 ℃면 `CLOSED`, 작업지시 `WO-INC-…`. TS1은 55 ℃ 아래인데 CLEAR가 아직 안 왔으면 한 번만 15초(5분 ÷ 20) 연장한다(`REOBSERVATION_EXTENDED`).

## 5. 실습 과제 (난이도 순)

1. **임계값 바꾸기**: `cep.py`의 `RAISE_TS1`을 58로 올리면 경보가 언제 나는가? (테스트 `tests/test_cep.py`도 고쳐 보기)
2. **새 증거 규칙**: Neo4j에 `ev:cp-low`(CP < 5 kW) Evidence를 추가하고 `cause:cooler-fin-fouling`에 연결한다. 재시드는 `docker compose up -d --force-recreate kg-seed`.
3. **새 조치**: `act:valve-bypass`(밸브 개도) Action을 만들고 `schemas.ACTION_WHITELIST`·`ACTION_TO_WRITES`·`plc.WRITE_RANGES`에 추가한다. 게이트웨이 화이트리스트를 빼먹으면 어떻게 되는가?
4. **가드레일 반려 재현**: `card.py`의 `_citations()`에서 action id를 빼면 `guardrail`이 반려하고 카드가 제출되지 않는다(`REJECTED_BY_GUARDRAIL`).
5. **EMQX ACL**: FUXA 계정만 `plant/+/mode`를 발행할 수 있게 EMQX 인증/ACL을 켠다.
6. **Alertmanager + Mailpit**: `monitor` 프로필에 두 컨테이너를 추가하고 `IngestStalled` 규칙이 메일로 오게 한다(`docker compose stop connect-ingest`로 재현).

## 5-1. L7~L9 실습 과제

`docs/l7-l9-ontology-decisions.md` 6절에 다섯 가지가 있다. 가격 민감도, 전사 가중치, 규정 추가, 새 판단 시나리오, 승인 권한이다. 온톨로지 값을 바꾼 뒤 `docker compose up -d --force-recreate kg-seed`로 다시 적재하고 포탈 **전사 의사결정 시나리오**에서 다시 실행한다.

## 6. 실제 제품으로 바꾸려면 (연결 지점)

| 학생용 | 실제 제품 | 바꿀 때 지켜야 할 인터페이스 |
|--------|-----------|------------------------------|
| `plant-sim`의 `edge.py` | EdgeX device-modbus/daq + app-service | MQTT 토픽·페이로드(`docs/topics.md`). PLC는 Modbus 태그로, `cmd/*`는 core-command로 |
| `connect-ingest` | Kafka Connect MQTT Source | Kafka 키 = asset, 자산별 작업 1개 |
| `cmd-gateway` | 그대로(설계서도 자체 구현) | `validate.py`의 5종 + audit 이벤트 이름 |
| `detector` | Flink (PyFlink + ONNX) | `feat.1s`·`alerts` 페이로드. `anomaly_score()` 자리에 ONNX 추론 |
| `connect-sink` | Kafka Connect JDBC Sink (upsert) | 테이블 스키마 `init.sql` |
| `agent`의 `tools/mcp_*.py` | MCP 서버 컨테이너 3개 | 도구 이름·읽기 전용·`PROCESS_URL`만 쓰기 |
| `agent`의 `llm.py` | LiteLLM 게이트웨이 | `summarize(card)` 한 함수 |
| `process` | Process GPT / Flowable | REST 3개(`/api/incidents`, `/approve`, `/reject`)와 Kafka `action.cmd`·`audit` |
| `portal` | guide-app | 같은 REST |
| `enterprise-sim` | SAP ERP · MES · CMMS · QMS · SCM 포털 · EMS | 읽기 엔드포인트는 온톨로지 InfoType의 `endpoint`만 바꾸면 된다. 쓰기는 process의 `exec_skill()` 한 곳 |
| `agent`의 `tools/mcp_ent.py` | 기업 시스템용 MCP 서버 | 읽기 전용 GET, 엔드포인트는 온톨로지가 준다 |

## 7. 자주 막히는 곳

- FUXA 값이 `##.##`이면: `fuxa-init` 로그(`docker compose logs fuxa-init`)에 `POST /api/project -> 200`이 있는지. 없으면 `docker compose up -d --force-recreate fuxa-init`.
- 경보가 안 나면: `curl localhost:8092/api/detector/state`에서 `phase`와 `slope`. `CANDIDATE`가 60 시뮬레이션-초 유지돼야 `RAISED`.
- 승인했는데 ACK가 없으면: `curl localhost:8090/api/gateway/log`. `MODE`면 PLC가 `REMOTE_MANUAL`이다(FUXA에서 수동 조작을 하면 자동으로 바뀐다).
- 시간이 너무 빠르거나 느리면: `.env`의 `TIME_SCALE`(plant-sim·detector·process 재시작 필요) 또는 포탈의 시간 배율(plant-sim만 즉시).
