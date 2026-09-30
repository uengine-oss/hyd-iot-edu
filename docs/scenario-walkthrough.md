# 경보 주입 → 확인 → 조치: 순서대로 따라가기 (HYD-01 기준)

시간 배율 ×20 기준의 소요 시간이다. 포탈(http://localhost:8088)로 하는 방법과 API로 하는 방법을 나란히 적었다. 명령은 `hyd-iot-edu/` 폴더에서 실행한다.

## 0. 준비 — 정상 상태 확인

- 포탈 → **결함 시나리오 시뮬레이션** → "전체 초기화 (정상 운전점)". 또는 `curl -X POST localhost:8000/api/reset`
- 확인: HYD-01 카드가 `REMOTE_AUTO · RUN · 48.0 ℃ · CE 84 % · 탐지 단계 IDLE`, 상단 "열린 인시던트 0". 상태 점이 13/13 정상.
- 승인할 시간을 넉넉히 갖고 싶으면 시간 배율을 10으로 낮춘다(콘솔 상단 셀렉트 또는 `curl -X POST localhost:8000/api/time_scale -H 'Content-Type: application/json' -d '{"scale":10}'`). 배율은 plant-sim의 물리 속도만 바꾼다.

## 1. 경보 주입 (결함 주입)

| 방법 | 조작 |
|---|---|
| 포탈 | 결함 시나리오 시뮬레이션 → HYD-01 카드 → **쿨러 열화 주입** |
| API | `curl -X POST localhost:8000/api/fault -H 'Content-Type: application/json' -d '{"asset":"HYD-01","type":"cooler_degradation"}'` (옵션 `"target_health":0.43, "ramp_sim_s":300`) |

무엇이 일어나는가
- 쿨러 상태(health)가 300 시뮬레이션-초(=15초) 동안 1.0 → 0.43으로 내려간다. 카드에 "결함 진행 중: cooler_degradation"이 뜬다.
- CE가 84 → 36 %로 떨어지고 TS1이 오른다. 55 ℃를 넘고 CE < 70 %, 기울기 > 0이 60 시뮬레이션-초(=3초) 유지되면 L4 탐지기가 `alerts RAISE`를 낸다. **주입 후 약 30~40초.**
- 아무 조치도 안 하면 약 80초 뒤 65 ℃ 인터록 트립(펌프 정지, OVERHEAT_TRIP 경보).

## 2. 경보 확인

순서대로 아래 위치에서 같은 경보를 볼 수 있다.

1. **포탈 결함 시나리오 시뮬레이션**: HYD-01 카드 "탐지 단계"가 IDLE → CANDIDATE → **RAISED** + `ALT-hyd01-…`. 상단 "열린 인시던트 1".
2. **FUXA (http://localhost:1881)**: HYD-01 "IT 경보" 표시등이 빨강, 컬럼 하단에 `RAISE COOLER_DEGRADATION (ALT-…)`. TS1이 60 ℃를 넘으면 FUXA 자체 알람(우상단 종 아이콘)도 뜬다. 이 표시는 cmd-gateway가 `plant/hyd01/alert`로 중계한 경보를 FUXA가 구독해 보여 주는 것이다.
3. **API / 메시지**
   - 탐지기: `curl localhost:8092/api/detector/state` → `assets.HYD-01.phase = RAISED`
   - OT 토픽: `python scripts/mqtt_tail.py 'plant/hyd01/alert' 2` → `{"state":"RAISE","level":2,…}`
   - Kafka: Redpanda Console(8085) → Topics › alerts · 게이트웨이 중계 수 `curl localhost:8090/healthz` → `alerts_relayed`
   - DB: `docker compose exec timescaledb psql -U hyd -d hyd -c "SELECT alert_id, state, raised_at FROM alerts WHERE asset='HYD-01' ORDER BY raised_at DESC LIMIT 1"`
   - Grafana(3000): "활성 경보 1", TS1 패널에 빨간 점선 주석
4. **에이전트 결과(가이드 카드)**: 경보 후 1초 안에 만들어진다.
   - 포탈 → **이상 확인 & 조치** → 붉은 테두리가 된 HYD-01 도식을 클릭(경보 설비를 누르면 그 설비의 프로세스가 아래에 나타난다). 목록의 `INC-… AWAITING_APPROVAL`을 눌러도 된다.
   - 위쪽 미니 BPMN 레인이 "운전원 승인·수정·거부"에서 멈춰 있다.
   - **에이전트 트레이스**: freshness → t1_causes → evidence → rank → t2_actions → card → guardrail → submit 순서로 각 단계 출력이 보인다.
   - **가이드 카드**: 원인 후보 4개와 점수(1위 쿨러 핀 오염 0.5), 증거 SQL 값(CE 36 < 70 통과 등), 권장 조치 FAN_BOOST(80~100)·REDUCE_LOAD(60~90)·COOLER_CLEAN_WO(작업지시), SOP-COOL-01 단계 4개, 매뉴얼 HM-3.2/7.3/9.1/7.5 인용.
   - API: `curl localhost:8091/api/agent/runs` · `curl localhost:8080/api/incidents` · 카드 전체 `curl localhost:8080/api/incidents/<INC-ID>`

## 3. 조치 (승인 → 실행 → 회복 → 종결)

### 3-1. 승인

| 방법 | 조작 |
|---|---|
| 포탈 | 이상 확인 & 조치 → 경보 설비 도식 클릭 → 카드의 슬라이더로 fan_pct(80~100)·load_pct(60~90) 조정 → **승인 → action.cmd 발행**. 거부하려면 사유를 쓰고 **거부**. |
| API | `curl -X POST localhost:8080/api/incidents/<INC-ID>/approve -H 'Content-Type: application/json' -d '{"approvedBy":"OP-17","actions":[{"code":"FAN_BOOST","fan_pct":100},{"code":"REDUCE_LOAD","load_pct":80}]}'` |

범위 밖 값(예: load_pct 50)은 프로세스가 400으로 거절한다. 승인은 사람만 한다. 에이전트는 카드 제출까지만 할 수 있다.

### 3-2. 명령이 PLC에 닿았는지 확인 (승인 후 1~2초)

- 포탈 레인: CMD_ISSUED → AWAITING_ACK → ACKED → **RE_OBSERVING**. 아래에 `PLC ACK: DONE · 인터록 PASS`.
- 게이트웨이 결정: 결함 시나리오 시뮬레이션 하단 "최근 명령 게이트웨이 결정"에 `PASS · CMD-…` (또는 `curl localhost:8090/api/gateway/log`).
- 설비: HYD-01 카드 팬 100 % · 부하 80 %, 마지막 ACK `CMD-… → DONE`. FUXA에도 팬/부하 값과 마지막 명령 ACK DONE.
- 메시지 경로를 직접 보려면: Redpanda Console `action.cmd` 토픽 → `python scripts/mqtt_tail.py 'plant/hyd01/cmd/auto' 5`(승인 직전에 켜 둘 것) → `plant.status`의 cmdId/result.

### 3-3. 회복과 경보 해제 (승인 후 약 35~50초)

- TS1이 내려간다(63 → 52 ℃). Grafana TS1 패널에 파란 점선(승인 조치) 뒤로 하강 곡선.
- 52 ℃ 아래로 60 시뮬레이션-초 유지되면 `alerts CLEAR`: 탐지 단계 IDLE, FUXA 표시등 초록·`CLEAR COOLER_DEGRADATION`, Grafana 초록 주석, DB alerts 행의 `cleared_at` 채워짐.
- 이상 점수는 높게 남는다. CE가 여전히 낮기 때문이며, 근본 원인(핀 오염)이 남아 있다는 뜻이다.

### 3-4. 재관측과 종결 (ACK 후 45초, 필요하면 15초 한 번 연장)

- 15분 재관측(÷20 = 45초) 타이머가 끝나면 판정: `CLEAR 수신 ∧ TS1 < 55 ℃` → RESOLVED → WORK_ORDER_CREATED → **CLOSED**. TS1은 55 ℃ 아래인데 CLEAR가 아직이면 15초 한 번 연장(`REOBSERVATION_EXTENDED`).
- 확인: 포탈 레인 끝 "종결", `작업지시 WO-INC-…: 쿨러 핀 세척 작업지시 (SOP-COOL-02)`, 감사 로그 9~10줄(GUIDE_SUBMITTED … INCIDENT_CLOSED).
- 온톨로지에 사례가 남는다: Neo4j Browser에서 `MATCH (i:Incident)-[:TRIGGERED_BY]->(al) RETURN i, al`.
- 판정 실패(CLEAR 없음 또는 TS1 ≥ 55)면 ESCALATED(MITIGATION_FAILED)로 끝나고 재시도하지 않는다.

### 3-5. 뒷정리

CLOSED 뒤에도 health는 0.43이라 팬 100 %로 버티는 상태다. HYD-01 카드 **복구**(`{"type":"restore"}`)로 health를 1.0으로 되돌리거나 **전체 초기화**를 누른다.

## 4. 부정 시나리오 (선택)

- **수동 운전 중인 설비**: HYD-02 카드 **REMOTE_MANUAL** → 쿨러 열화 주입 → 카드 승인 → 게이트웨이 결정에 `REJECT · MODE — PLC mode is REMOTE_MANUAL` → 30초 뒤 인시던트 ESCALATED(ACK_TIMEOUT). 감사 로그(DB `audit`)에 `CMD_REJECTED` 사유. 다시 자동 조치를 받으려면 **REMOTE_AUTO** 버튼(또는 FUXA 모드 선택).
- **방치 → 트립**: 주입 후 승인하지 않으면 65 ℃에서 PLC 상태 TRIP(OVERTEMP), OVERHEAT_TRIP 경보, FUXA highhigh 알람. **복구** 후 TS1 < 55 ℃가 되면 **RESET**(그 전엔 RESET_TOO_HOT로 거부).
- **FUXA 수동 조작 우선**: FUXA에서 팬 입력란에 80 → PLC가 REMOTE_MANUAL로 내려가고, 이후 자동 조치는 위와 같이 거부된다.

## 5. 전부 자동으로 돌리기

```
python scripts/scenario_test.py --quick   # 0~5절 (정상 경로), 약 2분
python scripts/scenario_test.py           # + DB 확인 + 부정 시나리오 2건, 약 5분, 42 checks
```

## 6. 온톨로지(Neo4j)에서 확인하기

Neo4j에는 실시간 값이 없다. 들어 있는 것은 **지식**(경보 패턴 → 증상 → 고장모드 → 원인 → 증거 규칙, 원인 → 조치 → SOP → 단계 → 매뉴얼)과, 종결된 뒤 process가 써 넣는 **사례**(Incident)다. 에이전트는 이 지식을 `it/neo4j/templates/t1_causes.cypher`, `t2_actions.cypher` 두 템플릿으로만 읽으므로, 같은 쿼리를 손으로 돌리면 카드와 똑같은 결과가 나온다.

접속: http://localhost:7474 → Connect URL `neo4j://localhost:7687`, 사용자 `neo4j`, 비밀번호 `hydpass123`. 왼쪽 위 쿼리창에 아래를 붙여 넣고 Ctrl+Enter. 결과 그래프는 노드를 클릭하면 속성이 보인다. CLI는 `docker compose exec neo4j cypher-shell -u neo4j -p hydpass123 "<쿼리>"`.

### 6-1. 경보 전: 지식이 어떻게 연결돼 있나

```cypher
// 스키마 한눈에 (그림 2)
CALL db.schema.visualization()

// 이 설비의 부품·센서·구동기
MATCH (a:Asset {id:'HYD-01'})-[:HAS_COMPONENT]->(c)-[r:MONITORED_BY|ACTUATED_BY]->(x) RETURN a, c, x

// T1: 경보 패턴 → 증상 → 고장모드 ← 원인(사전확률)   ※ 에이전트 1단계
MATCH p = (:AnomalyPattern {code:'COOLER_DEGRADATION'})-[:DETECTS]->(:Symptom)-[:INDICATES]->(:FailureMode)<-[:CAUSES]-(:Cause) RETURN p

// 원인별 증거 규칙과 SQL (에이전트가 TimescaleDB에서 실행하는 문장 그대로)
MATCH (c:Cause)-[:EVIDENCED_BY]->(e:Evidence) RETURN c.name, e.id, e.expect, e.threshold, e.weight, e.sql ORDER BY c.name

// T2: 원인 → 조치(파라미터 범위) → SOP → 단계 → 매뉴얼   ※ 에이전트 4단계
MATCH p = (:Cause {id:'cause:cooler-fin-fouling'})-[:MITIGATED_BY|REMEDIED_BY]->(:Action)-[:FOLLOWS]->(:Procedure)-[:HAS_STEP]->(:Step)-[:REFERS_TO]->(:ManualSection) RETURN p

// 조치의 제약(인터록·최소 부하·모드)
MATCH (a:Action)-[:REQUIRES]->(k:Constraint) RETURN a.code, a.min, a.max, collect(k.name)

// 연쇄(LEADS_TO): 결과를 원인으로 오인하지 않게 하는 관계 — T1은 이 방향을 따라가지 않는다
MATCH (f1:FailureMode)-[:LEADS_TO]->(f2:FailureMode) RETURN f1.name, f2.name
```

템플릿 파일을 그대로 실행하려면 파라미터를 먼저 넣는다.

```cypher
:param pattern => 'COOLER_DEGRADATION'
:param asset => 'HYD-01'
// 이어서 it/neo4j/templates/t1_causes.cypher 내용을 붙여 넣기
:param cause => 'cause:cooler-fin-fouling'
// 이어서 t2_actions.cypher 내용을 붙여 넣기
```

### 6-2. 경보 중: 카드의 인용을 그래프에서 대조

포탈 카드의 인용 목록(`cause:cooler-fin-fouling`, `ev:ce-low`, `act:fan-boost`, `SOP-COOL-01/2`, `HM-7.3` …)은 전부 노드 `id`다. 아무 id나 골라 확인한다.

```cypher
MATCH (n) WHERE n.id IN ['cause:cooler-fin-fouling','ev:ce-low','act:fan-boost','SOP-COOL-01/2','HM-7.3'] RETURN labels(n)[0], n.id, n.name, n.text, n.title
```

가드레일은 카드의 모든 원인·조치가 이 그래프의 id를 인용하는지, 조치 값이 `Action.min~max` 안인지 검사한다.

### 6-3. 종결 후: 사례가 남았는지

```cypher
// 종결된 인시던트 → 경보 → 패턴, 진단 원인, 실행 조치
MATCH (i:Incident)-[:TRIGGERED_BY]->(al:Alert)
OPTIONAL MATCH (al)-[:INSTANCE_OF]->(p:AnomalyPattern)
OPTIONAL MATCH (i)-[:DIAGNOSED_AS]->(c:Cause)
OPTIONAL MATCH (i)-[:RESOLVED_BY]->(a:Action)
RETURN i.id, i.asset, i.state, i.approvedBy, i.closed, al.id, p.code, c.name, collect(a.code) ORDER BY i.closed DESC

// 같은 것을 그래프로
MATCH p = (i:Incident)-[]->() RETURN p

// 원인별 사례 수 (다음 진단의 사전확률을 조정할 근거)
MATCH (i:Incident)-[:DIAGNOSED_AS]->(c:Cause) RETURN c.name, count(i) ORDER BY count(i) DESC
```

Incident 노드는 CLOSED 때만 기록된다(ESCALATED·거부는 audit 테이블에만 남는다). 지식만 다시 적재하려면 `docker compose up -d --force-recreate kg-seed`(MERGE라 사례 노드는 유지된다). 사례까지 지우려면 `MATCH (n) WHERE n:Incident OR n:Alert DETACH DELETE n`.
