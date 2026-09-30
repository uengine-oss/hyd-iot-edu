# HYD-01 정상 상태 데이터 — 진입점별 조회 메뉴·명령

설비 1번(HYD-01)이 정상 운전점(REMOTE_AUTO · RUN · TS1 48 ℃ · CE 84 % · 팬 60 % · 부하 90 %)에 있을 때, 같은 데이터가 L1부터 L9까지 어디에 어떤 모습으로 있는지 확인하는 방법이다. 명령은 저장소 루트(`hyd-iot-edu/`)에서 실행하며, 전부 실제로 실행해 확인했다(2026-09-28).

| L | 진입점 | 여기서 보는 HYD-01 데이터 | 메뉴 위치 (UI) | 조회 명령 (CLI / API) | 정상 상태 예 |
|---|--------|--------------------------|----------------|-----------------------|--------------|
| L1 | plant-sim (설비+soft-PLC) API | 태그 19개(TS1~TS4, PS1~PS6, EPS1, FS1~2, VS1, CE, CP, SE, FanSpeedSP, LoadSP) + PLC status(모드·상태·ACK·health·sim_t) | http://localhost:8000/docs → `GET /api/state` → Try it out | `curl localhost:8000/api/state` → `units.HYD-01.tags`, `units.HYD-01.status` | TS1 48.0, CE 84.0, CP 8.1, mode REMOTE_AUTO, state RUN, cmdId null |
| L2 | MQTT 토픽 (EMQX) | 1 Hz 태그 `plant/hyd01/tag/{name}`, 1초 파형 `plant/hyd01/wave/{PS1,EPS1,FS1}`, retained `plant/hyd01/status` | 대시보드 http://localhost:18083 → **Monitoring › Clients**(plant-sim-edge, connect-ingest, cmd-gateway, mqttjs_*=FUXA) · **Diagnose › WebSocket Client** → Subscribe `plant/hyd01/#` | 실시간: `python scripts/mqtt_tail.py 'plant/hyd01/#' 3` (또는 `'plant/hyd01/tag/TS1'`) · REST: `TOKEN=$(curl -s -X POST localhost:18083/api/v5/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"<비밀번호>"}' \| jq -r .token)` 뒤 retained `curl -H "Authorization: Bearer $TOKEN" localhost:18083/api/v5/mqtt/retainer/message/plant%2Fhyd01%2Fstatus` · 구독 `…/api/v5/clients/plant-sim-edge/subscriptions` | `{"t":"…","v":48.0,"q":"good"}` 초당 약 23건(태그 19 + 파형 3 + status) |
| L6 (OT) | FUXA 웹 SCADA | 화면 값(TS1 게이지·CE·CP·SE·VS1·PS1·팬·부하·모드·상태·마지막 ACK·IT 경보 표시등) | http://localhost:1881 → 뷰 **설비 현황** → HYD-01 컬럼 · 알람 목록: 우상단 **종 아이콘** · 편집기: 좌하단 메뉴 → Editor → Devices → emqx → Tags(`hyd01_*`) | 태그 정의: `curl "localhost:1881/api/project?views=lazy"` → `devices.emqx.tags.hyd01_TS1` 등 | 표시등 초록, 알람 0, TS1 48 |
| L3 (DMZ) | connect-ingest | OT→Kafka 복제 건수·마지막 수신 시각·큐 | http://localhost:8093/docs | `curl localhost:8093/api/ingest/stats` · `curl localhost:8093/metrics \| grep ingest_` | `mqtt:true, kafka:true, last_event_age_s≈0.1` |
| L3 (IT) | Redpanda (Kafka) | `plant.tag`(키 hyd01) · `plant.wave` · `plant.status` 메시지 원문 | Console http://localhost:8085 → **Topics › plant.tag › Messages** (필터: Key = hyd01, Value 검색 "TS1") · `plant.status`도 동일 | `docker compose exec redpanda rpk topic consume plant.tag -n 80 -f '%k %v\n' -o end \| grep '^hyd01 ' \| grep TS1` · `docker compose exec redpanda rpk topic consume plant.status -n 3 -f '%k %v\n' -o -3` | `hyd01 {"asset":"HYD-01","name":"TS1","t":"…","v":48.0,"q":"good"}` |
| L3 (DMZ) | cmd-gateway | 게이트웨이가 기억하는 HYD-01 최신 status(검증 ⑤ 모드 판단 근거), 최근 명령 결정 | http://localhost:8090/docs | `curl localhost:8090/api/gateway/status` → `plc_status.HYD-01` · `curl localhost:8090/api/gateway/log` | mode REMOTE_AUTO, 결정 로그 비어 있음 |
| L4 | detector (CEP) | 탐지 단계·TS1·CE·60초 기울기·이상 점수·트립 여부 | http://localhost:8092/docs | `curl localhost:8092/api/detector/state` → `assets.HYD-01` | `phase IDLE, ts1 48.0, ce 84.0, slope 0.0, score≈0.1` |
| L5 | connect-sink | Kafka→DB 적재 건수·오류 | http://localhost:8094/docs | `curl localhost:8094/api/sink/stats` | `db:true, kafka:true, errors 0` |
| L5 | TimescaleDB | `tag_1s`(1 Hz 태그), `feat_1s`(특징·이상 점수), `alerts`, `actions`, `audit` | Grafana **Explore** → 데이터소스 TimescaleDB → SQL | `docker compose exec timescaledb psql -U hyd -d hyd -c "SELECT name, value, time FROM tag_1s WHERE asset='HYD-01' AND name IN ('TS1','CE') ORDER BY time DESC LIMIT 4"` · `… -c "SELECT sensor, score, time FROM feat_1s WHERE asset='HYD-01' AND sensor='TS1' ORDER BY time DESC LIMIT 1"` · `… -c "SELECT * FROM alerts WHERE asset='HYD-01'"` | TS1 48.00, CE 84.00, score≈0.09, alerts 0행 |
| L6 (IT) | Grafana | 유온 추세, CE·SE, CP, 설정값, 이상 점수, 경보·조치·감사 테이블, 주석 | http://localhost:3000/d/hyd-trend → 상단 변수 **설비 = HYD-01** (기본) · 시간 범위 Last 10 minutes · 익명 조회 가능(편집은 admin/admin) | 패널 URL 직접: `http://localhost:3000/d/hyd-trend?var-asset=HYD-01&from=now-10m&to=now` · Explore SQL은 위 L5와 동일 | TS1 48 ℃ 평평한 선, 활성 경보 0 |
| L6 (IT) | Prometheus | 서비스 메트릭(탐지기의 TS1·이상 점수, 수집 지연, 게이트웨이 결정 수) | http://localhost:9090/graph → 식 입력 · **Status › Targets**(6개 up) | `curl -G localhost:9090/api/v1/query --data-urlencode 'query=detector_ts1{asset="HYD-01"}'` · `…'query=detector_anomaly_score{asset="HYD-01"}'` · `…'query=ingest_last_event_age_seconds'` | detector_ts1 48, age 0.1 s |
| L7 | Neo4j 온톨로지 | HYD-01 자산 그래프(부품 5 · 센서 17 · 구동기 3) — 정상 상태에선 Incident 노드 없음 | Neo4j Browser http://localhost:7474 (neo4j / hydpass123) → 쿼리창 | Browser: `MATCH (a:Asset {id:'HYD-01'})-[:HAS_COMPONENT]->(c)-[:MONITORED_BY]->(s) RETURN a,c,s` · CLI: `docker compose exec neo4j cypher-shell -u neo4j -p hydpass123 "MATCH (a:Asset {id:'HYD-01'})-[:HAS_COMPONENT]->(c)-[:MONITORED_BY]->(s) RETURN count(DISTINCT c), count(s)"` · 사례: `MATCH (i:Incident)-[:TRIGGERED_BY]->(al) WHERE i.asset='HYD-01' RETURN i, al` | 5, 17 · Incident 0 |
| L8 | agent | 경보별 실행 트레이스(정상 상태엔 없음) | http://localhost:8091/docs · 포탈 **이상 확인 & 조치** | `curl localhost:8091/api/agent/runs` · `curl localhost:8091/healthz`(neo4j·kafka 연결) | `[]`, `neo4j:true` |
| L9 | process (미니 BPMN) | 인시던트·감사 로그·프로세스 정의(정상 상태엔 인시던트 없음) | http://localhost:8080/docs | `curl localhost:8080/api/summary` · `curl localhost:8080/api/incidents` · `curl localhost:8080/api/audit` · `curl localhost:8080/api/definition` | `open 0, total 0`, audit `[]` |
| L9 | enterprise-sim (ERP · MES · CMMS · QMS · SCM · EMS 목업) | HYD-01의 생산오더 · 계약 · 정비 이력 · 로트 (에이전트 전사 판단의 입력) | http://localhost:8095/docs · 포탈 **업무 프로세스 · 시스템 연계** 아래 기업 시스템 현황 | `curl "localhost:8095/mes/orders?asset=HYD-01"` · `curl "localhost:8095/cmms/history?asset=HYD-01"` · `curl localhost:8095/api/transactions` | 납기 6 h, 잔량 1500, 60일 세척 3회, 트랜잭션 없음 |
| L9 | 포탈 (guide-app) | 위 전부를 한 화면에: 상태 점, HYD-01 카드(1초 갱신), 인시던트, Grafana 임베드 | http://localhost:8088 → **시스템 아키텍처 & 맵**(상태 점 13/13) · **결함 시나리오 시뮬레이션** → HYD-01 카드(TS1·CE·CP·팬·부하·health·탐지 단계·PLC 상태·마지막 ACK·PS1 파형) · **이상 확인 & 조치**(비어 있음) · **실시간 설비 모니터링** → 설비 HYD-01 | 브라우저 개발자도구 Network에서 같은 API 호출(`/api/state`, `/api/detector/state`, `/api/incidents`)을 볼 수 있다 | 카드: 48.0 ℃ · IDLE · RUN · ACK – |

## 데이터가 흐르는 순서로 다시 보면

1. plant-sim이 1초마다 MQTT에 발행 (L1→L2) — `mqtt_tail.py`로 원문 확인.
2. FUXA는 그 토픽을 바로 구독해 표시 (L2→L6 OT) — IT가 꺼져도 유지.
3. connect-ingest가 같은 메시지를 Kafka로 복제 (L2→L3) — Redpanda Console `plant.tag`.
4. detector가 Kafka에서 읽어 특징·점수·CEP 계산 (L3→L4) — `/api/detector/state`, `feat.1s`.
5. connect-sink가 Kafka를 TimescaleDB에 적재 (L3→L5) — `psql`, Grafana.
6. Prometheus는 서비스 `/metrics`를 긁는다 (L6 감시) — 설비 값이 아니라 파이프라인 상태를 본다.
7. Neo4j·agent·process는 정상 상태에선 "비어 있음"이 정상이다 — 경보가 나야 채워진다.

## 자주 쓰는 한 줄 점검

```
python scripts/mqtt_tail.py 'plant/hyd01/tag/TS1' 2          # OT에서 1 Hz로 나오는가
curl -s localhost:8092/api/detector/state | jq .assets.HYD-01 # IT가 같은 값을 보고 있는가
docker compose exec timescaledb psql -U hyd -d hyd -c "SELECT max(time), max(value) FROM tag_1s WHERE asset='HYD-01' AND name='TS1'"
```
