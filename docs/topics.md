# 토픽과 페이로드 (v3 설계서 5.1 · 5.2 · 7.3절, 학생용 구현 기준)

자산 ID는 본문에서 `HYD-01`, 토픽과 Kafka 키에서 `hyd01` (`hydcommon.topics.asset_key`).

## OT MQTT (emqx, ot-net)

| 토픽 | 방향 | 발행 | 구독 | 페이로드 | 비고 |
|------|------|------|------|----------|------|
| `plant/{a}/tag/{name}` | ↑ | plant-sim(edge) | FUXA, connect-ingest | `{"t": ISO, "v": number, "q": "good"}` | 1 Hz. name = TS1..TS4, PS1..PS6, EPS1, FS1, FS2, VS1, CE, CP, SE, FanSpeedSP, LoadSP |
| `plant/{a}/wave/{sensor}` | ↑ | plant-sim | connect-ingest만 | `{"t0": ISO, "hz": 100, "v": [..]}` | PS1·EPS1 100 Hz, FS1 10 Hz. FUXA 구독 안 함 |
| `plant/{a}/status` | ↑ | plant-sim | FUXA, connect-ingest, cmd-gateway | `payload-schemas/status.json` | retained. ACK = `cmdId` + `result` |
| `plant/{a}/mode` | ↓ | FUXA | plant-sim | `{"mode": "REMOTE_AUTO"}` 또는 FUXA 선택값 `{"mode": 2}` (0 LOCAL, 1 REMOTE_MANUAL, 2 REMOTE_AUTO) | FUXA·현장만 |
| `plant/{a}/cmd/manual` | ↓ | FUXA | plant-sim | `{"FanSpeedSP": 80}` (학생용 단순형) 또는 v3 전체형 | retained 금지 |
| `plant/{a}/cmd/auto` | ↓ | cmd-gateway | plant-sim | `payload-schemas/cmd_auto.json` | source HITL, retained 금지 |
| `plant/{a}/alert` | ↓ | cmd-gateway | FUXA | `{"alertId","pattern","severity","state","level": 2|0,"t","text"}` | 표시 전용, retained |

## Kafka (redpanda, it-net)

| 토픽 | 생산자 → 소비자 | 값 | 보존 |
|------|-----------------|-----|------|
| `plant.tag` | connect-ingest → detector, connect-sink | `{"asset","name","t","v","q"}` | 7일 |
| `plant.wave` | connect-ingest → detector | `{"asset","sensor","t0","hz","v":[..]}` | 7일 |
| `plant.status` | connect-ingest → process(ACK), cmd-gateway는 MQTT로 직접, connect-sink | status 그대로 | 30일 |
| `feat.1s` | detector → connect-sink | `{"asset","t","sensor","mean","rms","slope","score"}` | 30일 |
| `alerts` | detector → agent, process, cmd-gateway, connect-sink | `payload-schemas/alert.json` | 1년 |
| `action.cmd` | process → cmd-gateway, connect-sink | `payload-schemas/action_cmd.json` | 1년 |
| `audit` | process · cmd-gateway → connect-sink | `{"t","incident","asset","actor","event","detail":{}}` | 5년 |

audit 이벤트 이름: `GUIDE_SUBMITTED` `GUIDE_APPROVED` `GUIDE_REJECTED` `CMD_PUBLISHED` `CMD_FORWARDED` `CMD_REJECTED` `ACK_DONE` `ACK_REJECTED` `ACK_TIMEOUT` `ALERT_CLEARED` `REOBSERVATION_EXTENDED` `REOBSERVATION` `WORK_ORDER_CREATED` `INCIDENT_CLOSED`

## TimescaleDB (it/timescaledb/init.sql)

`tag_1s(time, asset, name, value)` · `feat_1s(time, asset, sensor, mean, rms, slope, score)` · `alerts(alert_id PK, …, state, raised_at, cleared_at, evidence)` · `actions(cmd_id PK, incident, asset, actions, approved_by, issued_at, expires_at, ack_result, ack_reason, ack_at)` · `audit(id, time, incident, actor, event, detail)` · 연속 집계 `tag_1m`

## HTTP API (학생용 서비스)

| 서비스 | 포트 | 주요 엔드포인트 |
|--------|------|-----------------|
| plant-sim | 8000 | `GET /api/state` · `POST /api/fault {asset,type,target_health,ramp_sim_s}` · `POST /api/mode` · `POST /api/manual {asset,writes}` · `POST /api/time_scale` · `POST /api/reset` |
| cmd-gateway | 8090 | `GET /api/gateway/log` · `GET /api/gateway/status` |
| detector | 8092 | `GET /api/detector/state` |
| connect-ingest / sink | 8093 / 8094 | `GET /api/ingest/stats` · `GET /api/sink/stats` |
| agent | 8091 | `GET /api/agent/runs` · `GET /api/agent/runs/{id}` · `POST /api/agent/replay/{alertId}` |
| process | 8080 | `POST /api/incidents`(agent 전용) · `GET /api/incidents[/{id}]` · `POST /api/incidents/{id}/approve {approvedBy, actions[]}` · `/reject` · `GET /api/audit` · `GET /api/definition` |

모든 서비스: `GET /healthz`, `GET /metrics`(Prometheus), `GET /docs`(OpenAPI).
