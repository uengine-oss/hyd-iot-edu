// hyd-iot-edu ontology seed (L7) — labels and relationships follow v3 figure 2 (TBox).
// Idempotent: every node/edge is MERGEd on its id, so kg-seed can run on every `docker compose up`.
// Each statement ends with ';' and relationship statements always MATCH their endpoints by id
// (Cypher variables do not survive a ';').
//
//  자산     : Asset -HAS_COMPONENT-> Component -MONITORED_BY-> Sensor ; Component -ACTUATED_BY-> Actuator
//  관측     : AnomalyPattern -USES-> Sensor ; AnomalyPattern -DETECTS-> Symptom ; Symptom -OBSERVED_BY-> Sensor ; Alert -INSTANCE_OF-> AnomalyPattern
//  고장 지식: Symptom -INDICATES-> FailureMode ; Cause -CAUSES{weight}-> FailureMode ; FailureMode -OCCURS_IN-> Component ;
//             Cause -EVIDENCED_BY-> Evidence ; FailureMode -LEADS_TO-> FailureMode (연쇄: 결과를 원인으로 오인하지 않게)
//  조치 지식: Cause -MITIGATED_BY-> Action (즉시 완화) ; Cause -REMEDIED_BY-> Action (근본 조치/작업지시) ;
//             Action -REQUIRES-> Constraint ; Action -TARGETS-> Actuator ; Action -FOLLOWS-> Procedure -HAS_STEP-> Step -REFERS_TO-> ManualSection
//  사례     : Incident -TRIGGERED_BY-> Alert ; Incident -DIAGNOSED_AS-> Cause ; Incident -RESOLVED_BY-> Action   (process 서비스가 종결 시 기록)

CREATE CONSTRAINT asset_id IF NOT EXISTS FOR (n:Asset) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT component_id IF NOT EXISTS FOR (n:Component) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sensor_id IF NOT EXISTS FOR (n:Sensor) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT actuator_id IF NOT EXISTS FOR (n:Actuator) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pattern_id IF NOT EXISTS FOR (n:AnomalyPattern) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT symptom_id IF NOT EXISTS FOR (n:Symptom) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT fm_id IF NOT EXISTS FOR (n:FailureMode) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT cause_id IF NOT EXISTS FOR (n:Cause) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (n:Evidence) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT action_id IF NOT EXISTS FOR (n:Action) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT constraint_id IF NOT EXISTS FOR (n:Constraint) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT procedure_id IF NOT EXISTS FOR (n:Procedure) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT step_id IF NOT EXISTS FOR (n:Step) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT manual_id IF NOT EXISTS FOR (n:ManualSection) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT incident_id IF NOT EXISTS FOR (n:Incident) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT alert_id IF NOT EXISTS FOR (n:Alert) REQUIRE n.id IS UNIQUE;

// ---------------------------------------------------------------- assets (3 units, same structure)
UNWIND ['HYD-01','HYD-02','HYD-03'] AS aid
MERGE (a:Asset {id: aid}) SET a.name = '유압설비 ' + aid, a.type = 'HydraulicPowerUnit'
WITH a, aid
UNWIND [['Cooler','오일 쿨러'],['Pump','유압 펌프'],['Motor','구동 모터'],['Valve','메인 제어 밸브'],['Reservoir','오일 탱크']] AS c
MERGE (comp:Component {id: aid + ':' + c[0]}) SET comp.name = c[1], comp.kind = c[0], comp.asset = aid
MERGE (a)-[:HAS_COMPONENT]->(comp);

UNWIND ['HYD-01','HYD-02','HYD-03'] AS aid
UNWIND [['TS1','유온 (쿨러 입구)','C','Cooler'],['TS2','유온 (쿨러 출구)','C','Cooler'],['TS3','탱크 유온','C','Reservoir'],['TS4','캐비닛 주변 온도','C','Reservoir'],
        ['PS1','펌프 토출 압력','bar','Pump'],['PS2','메인 라인 압력','bar','Valve'],['PS3','리턴 압력','bar','Valve'],['PS4','드레인 압력','bar','Valve'],['PS5','파일럿 압력','bar','Valve'],['PS6','어큐뮬레이터 압력','bar','Valve'],
        ['EPS1','모터 전력','kW','Motor'],['FS1','펌프 유량','l/min','Pump'],['FS2','쿨러 유량','l/min','Cooler'],['VS1','펌프 진동','mm/s','Pump'],
        ['CE','냉각 효율 (가상)','%','Cooler'],['CP','냉각 능력 (가상)','kW','Cooler'],['SE','시스템 효율 (가상)','%','Pump']] AS s
MATCH (comp:Component {id: aid + ':' + s[3]})
MERGE (sen:Sensor {id: aid + ':' + s[0]}) SET sen.tag = s[0], sen.name = s[1], sen.unit = s[2], sen.asset = aid
MERGE (comp)-[:MONITORED_BY]->(sen);

UNWIND ['HYD-01','HYD-02','HYD-03'] AS aid
UNWIND [['CoolerFan','쿨러 팬','FanSpeedSP','%','Cooler'],['PumpLoad','펌프 부하 (가변 용량)','LoadSP','%','Pump'],['MainValve','메인 밸브','ValveSP','%','Valve']] AS x
MATCH (comp:Component {id: aid + ':' + x[4]})
MERGE (act:Actuator {id: aid + ':' + x[0]}) SET act.name = x[1], act.resource = x[2], act.unit = x[3], act.asset = aid
MERGE (comp)-[:ACTUATED_BY]->(act);

// ---------------------------------------------------------------- observation knowledge
MERGE (p:AnomalyPattern {id: 'pattern:cooler-degradation'})
  SET p.code = 'COOLER_DEGRADATION', p.name = '쿨러 성능 저하 패턴', p.severity = 'HIGH',
      p.rule = 'TS1 > 55 ℃ AND CE < 70 % AND dTS1/dt > 0, 60 s 지속 (MATCH_RECOGNIZE)', p.clear = 'TS1 < 52 ℃ AND dTS1/dt ≤ 0, 60 s 지속';
MERGE (p:AnomalyPattern {id: 'pattern:overheat-trip'})
  SET p.code = 'OVERHEAT_TRIP', p.name = '과열 인터록 트립', p.severity = 'CRITICAL', p.rule = 'PLC status.state = TRIP';
MERGE (s:Symptom {id: 'symptom:oil-temp-rising'}) SET s.name = '유온 상승 (TS1 ↑)';
MERGE (s:Symptom {id: 'symptom:cooling-efficiency-drop'}) SET s.name = '냉각 효율 저하 (CE ↓)';
MERGE (s:Symptom {id: 'symptom:overtemperature-trip'}) SET s.name = '과열 트립 (TS1 > 65 ℃)';
MATCH (p:AnomalyPattern {id:'pattern:cooler-degradation'}), (s:Symptom) WHERE s.id IN ['symptom:oil-temp-rising','symptom:cooling-efficiency-drop'] MERGE (p)-[:DETECTS]->(s);
MATCH (p:AnomalyPattern {id:'pattern:overheat-trip'}), (s:Symptom {id:'symptom:overtemperature-trip'}) MERGE (p)-[:DETECTS]->(s);
MATCH (p:AnomalyPattern {id:'pattern:cooler-degradation'}), (sen:Sensor) WHERE sen.tag IN ['TS1','CE'] MERGE (p)-[:USES]->(sen);
MATCH (s:Symptom {id:'symptom:oil-temp-rising'}), (sen:Sensor {tag:'TS1'}) MERGE (s)-[:OBSERVED_BY]->(sen);
MATCH (s:Symptom {id:'symptom:cooling-efficiency-drop'}), (sen:Sensor) WHERE sen.tag IN ['CE','CP'] MERGE (s)-[:OBSERVED_BY]->(sen);
MATCH (s:Symptom {id:'symptom:overtemperature-trip'}), (sen:Sensor {tag:'TS1'}) MERGE (s)-[:OBSERVED_BY]->(sen);

// ---------------------------------------------------------------- failure knowledge
MERGE (f:FailureMode {id: 'fm:cooler-performance-loss'}) SET f.name = '쿨러 냉각 성능 상실', f.description = '열교환 능력이 떨어져 발열을 못 따라감';
MERGE (f:FailureMode {id: 'fm:oil-degradation'}) SET f.name = '작동유 열화 (2차)', f.description = '고온 지속으로 점도 저하·산화 — 결과이지 원인이 아님';
MATCH (f1:FailureMode {id:'fm:cooler-performance-loss'}), (f2:FailureMode {id:'fm:oil-degradation'}) MERGE (f1)-[:LEADS_TO]->(f2);
MATCH (s:Symptom), (f:FailureMode {id:'fm:cooler-performance-loss'}) WHERE s.id IN ['symptom:oil-temp-rising','symptom:cooling-efficiency-drop','symptom:overtemperature-trip'] MERGE (s)-[:INDICATES]->(f);
MATCH (f:FailureMode {id:'fm:cooler-performance-loss'}), (c:Component {kind:'Cooler'}) MERGE (f)-[:OCCURS_IN]->(c);

MERGE (c:Cause {id: 'cause:cooler-fin-fouling'}) SET c.name = '쿨러 핀 오염 (먼지·유막)', c.description = '핀 사이 오염으로 공기 유량·열전달 감소. 팬은 정상 회전하지만 CE가 떨어진다.';
MERGE (c:Cause {id: 'cause:fan-underperformance'}) SET c.name = '쿨러 팬 성능 저하 (벨트 슬립·베어링)', c.description = '팬 지시값은 정상이나 실제 풍량 부족. 진동 상승을 동반한다.';
MERGE (c:Cause {id: 'cause:high-ambient'}) SET c.name = '주변 온도 상승', c.description = '캐비닛/실내 온도가 높아 냉각 여유가 줄어든다.';
MERGE (c:Cause {id: 'cause:hydraulic-overload'}) SET c.name = '유압 과부하 운전', c.description = '부하 설정이 높아 발열이 커진다.';
MATCH (c:Cause {id:'cause:cooler-fin-fouling'}), (f:FailureMode {id:'fm:cooler-performance-loss'}) MERGE (c)-[r:CAUSES]->(f) SET r.weight = 0.5;
MATCH (c:Cause {id:'cause:fan-underperformance'}), (f:FailureMode {id:'fm:cooler-performance-loss'}) MERGE (c)-[r:CAUSES]->(f) SET r.weight = 0.25;
MATCH (c:Cause {id:'cause:high-ambient'}), (f:FailureMode {id:'fm:cooler-performance-loss'}) MERGE (c)-[r:CAUSES]->(f) SET r.weight = 0.10;
MATCH (c:Cause {id:'cause:hydraulic-overload'}), (f:FailureMode {id:'fm:cooler-performance-loss'}) MERGE (c)-[r:CAUSES]->(f) SET r.weight = 0.15;

// Evidence rules: SQL over TimescaleDB (parameter %(asset)s), single column "value", compared with expect/threshold
MERGE (e:Evidence {id: 'ev:ce-low'}) SET e.name = 'CE 평균 < 70 % (최근 30초)', e.weight = 0.4, e.expect = 'lt', e.threshold = 70,
  e.sql = "SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = 'CE' AND time > now() - interval '30 seconds'";
MERGE (e:Evidence {id: 'ev:ts1-rising'}) SET e.name = 'TS1 상승폭 > 3 ℃ (최근 5분)', e.weight = 0.3, e.expect = 'gt', e.threshold = 3,
  e.sql = "SELECT max(value) - min(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = 'TS1' AND time > now() - interval '5 minutes'";
MERGE (e:Evidence {id: 'ev:fan-commanded-normal'}) SET e.name = '팬 지시값 ≥ 50 % (팬은 정상 지시)', e.weight = 0.3, e.expect = 'gte', e.threshold = 50,
  e.sql = "SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = 'FanSpeedSP' AND time > now() - interval '2 minutes'";
MERGE (e:Evidence {id: 'ev:pump-vibration-high'}) SET e.name = '펌프/팬 진동 VS1 > 0.9 mm/s', e.weight = 0.6, e.expect = 'gt', e.threshold = 0.9,
  e.sql = "SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = 'VS1' AND time > now() - interval '2 minutes'";
MERGE (e:Evidence {id: 'ev:ambient-high'}) SET e.name = '주변 온도 TS4 > 38 ℃', e.weight = 0.8, e.expect = 'gt', e.threshold = 38,
  e.sql = "SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = 'TS4' AND time > now() - interval '2 minutes'";
MERGE (e:Evidence {id: 'ev:load-high'}) SET e.name = '부하 설정 > 95 %', e.weight = 0.8, e.expect = 'gt', e.threshold = 95,
  e.sql = "SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = 'LoadSP' AND time > now() - interval '2 minutes'";
MATCH (c:Cause {id:'cause:cooler-fin-fouling'}), (e:Evidence) WHERE e.id IN ['ev:ce-low','ev:ts1-rising','ev:fan-commanded-normal'] MERGE (c)-[:EVIDENCED_BY]->(e);
MATCH (c:Cause {id:'cause:fan-underperformance'}), (e:Evidence) WHERE e.id IN ['ev:ce-low','ev:pump-vibration-high'] MERGE (c)-[:EVIDENCED_BY]->(e);
MATCH (c:Cause {id:'cause:high-ambient'}), (e:Evidence) WHERE e.id IN ['ev:ambient-high','ev:ts1-rising'] MERGE (c)-[:EVIDENCED_BY]->(e);
MATCH (c:Cause {id:'cause:hydraulic-overload'}), (e:Evidence) WHERE e.id IN ['ev:load-high','ev:ts1-rising'] MERGE (c)-[:EVIDENCED_BY]->(e);

// ---------------------------------------------------------------- action knowledge
MERGE (k:Constraint {id: 'cons:ts1-max'}) SET k.name = '유온 상한 65 ℃ (하드 인터록 트립)', k.expr = 'TS1 <= 65';
MERGE (k:Constraint {id: 'cons:load-min'}) SET k.name = '최소 펌프 부하 60 %', k.expr = 'LoadSP >= 60';
MERGE (k:Constraint {id: 'cons:fan-range'}) SET k.name = '팬 속도 0~100 %', k.expr = '0 <= FanSpeedSP <= 100';
MERGE (k:Constraint {id: 'cons:mode-remote-auto'}) SET k.name = 'PLC 운전 모드 REMOTE_AUTO에서만 자동 조치 허용', k.expr = 'mode == REMOTE_AUTO';

MERGE (a:Action {id: 'act:fan-boost'}) SET a.code = 'FAN_BOOST', a.name = '쿨러 팬 속도 상향', a.kind = 'command', a.priority = 1,
  a.param = 'fan_pct', a.min = 80, a.max = 100, a.default = 100, a.description = '팬 풍량을 올려 열교환량을 즉시 늘린다.';
MERGE (a:Action {id: 'act:reduce-load'}) SET a.code = 'REDUCE_LOAD', a.name = '펌프 부하 저감', a.kind = 'command', a.priority = 2,
  a.param = 'load_pct', a.min = 60, a.max = 90, a.default = 80, a.description = '발열원(펌프 손실)을 줄인다. 생산 영향이 있으므로 60 % 아래로는 내리지 않는다.';
MERGE (a:Action {id: 'act:cooler-clean-wo'}) SET a.code = 'COOLER_CLEAN_WO', a.name = '쿨러 핀 세척 작업지시', a.kind = 'work_order', a.priority = 3,
  a.description = '완화 후 근본 조치. 정비 작업지시(WO)를 발행한다.';
MERGE (a:Action {id: 'act:fan-inspect-wo'}) SET a.code = 'FAN_INSPECT_WO', a.name = '쿨러 팬 점검 작업지시', a.kind = 'work_order', a.priority = 3,
  a.description = '벨트 장력·베어링 점검.';
MERGE (a:Action {id: 'act:ventilation-wo'}) SET a.code = 'VENTILATION_WO', a.name = '캐비닛 환기 개선 작업지시', a.kind = 'work_order', a.priority = 3,
  a.description = '환기 팬 증설·배치 개선.';
MATCH (c:Cause {id:'cause:cooler-fin-fouling'}), (a:Action) WHERE a.id IN ['act:fan-boost','act:reduce-load'] MERGE (c)-[:MITIGATED_BY]->(a);
MATCH (c:Cause {id:'cause:cooler-fin-fouling'}), (a:Action {id:'act:cooler-clean-wo'}) MERGE (c)-[:REMEDIED_BY]->(a);
MATCH (c:Cause {id:'cause:fan-underperformance'}), (a:Action {id:'act:reduce-load'}) MERGE (c)-[:MITIGATED_BY]->(a);
MATCH (c:Cause {id:'cause:fan-underperformance'}), (a:Action {id:'act:fan-inspect-wo'}) MERGE (c)-[:REMEDIED_BY]->(a);
MATCH (c:Cause {id:'cause:high-ambient'}), (a:Action {id:'act:fan-boost'}) MERGE (c)-[:MITIGATED_BY]->(a);
MATCH (c:Cause {id:'cause:high-ambient'}), (a:Action {id:'act:ventilation-wo'}) MERGE (c)-[:REMEDIED_BY]->(a);
MATCH (c:Cause {id:'cause:hydraulic-overload'}), (a:Action {id:'act:reduce-load'}) MERGE (c)-[:MITIGATED_BY]->(a);
MATCH (a:Action {id:'act:fan-boost'}), (k:Constraint) WHERE k.id IN ['cons:fan-range','cons:mode-remote-auto','cons:ts1-max'] MERGE (a)-[:REQUIRES]->(k);
MATCH (a:Action {id:'act:reduce-load'}), (k:Constraint) WHERE k.id IN ['cons:load-min','cons:mode-remote-auto','cons:ts1-max'] MERGE (a)-[:REQUIRES]->(k);
MATCH (a:Action {id:'act:fan-boost'}), (x:Actuator {resource:'FanSpeedSP'}) MERGE (a)-[:TARGETS]->(x);
MATCH (a:Action {id:'act:reduce-load'}), (x:Actuator {resource:'LoadSP'}) MERGE (a)-[:TARGETS]->(x);

// SOPs, steps, manual sections
MERGE (m:ManualSection {id: 'HM-3.1'}) SET m.ref = 'HM-3.1', m.title = '정비를 위한 LOCAL 전환', m.excerpt = '정비 작업 전 현장 패널에서 LOCAL로 전환하고 원격 명령을 차단한다.';
MERGE (m:ManualSection {id: 'HM-3.2'}) SET m.ref = 'HM-3.2', m.title = '운전 모드와 원격 조치 권한', m.excerpt = 'REMOTE_AUTO에서만 IT 승인 조치(cmd/auto)를 받는다. 수동 조작이 들어오면 REMOTE_MANUAL로 복귀한다.';
MERGE (m:ManualSection {id: 'HM-7.3'}) SET m.ref = 'HM-7.3', m.title = '쿨러 팬 속도 상향', m.excerpt = '팬 속도는 80~100 %로 올릴 수 있다. 100 % 연속 운전은 24시간 이내로 제한한다.';
MERGE (m:ManualSection {id: 'HM-7.5'}) SET m.ref = 'HM-7.5', m.title = '냉각 회복 판정', m.excerpt = '조치 후 15분 재관측에서 TS1 < 55 ℃ 이고 경보가 CLEAR이면 완화 성공으로 본다.';
MERGE (m:ManualSection {id: 'HM-7.6'}) SET m.ref = 'HM-7.6', m.title = '쿨러 핀 세척', m.excerpt = '설비 정지·LOCAL 전환 후 압축공기로 핀을 세척한다. 세척 후 CE 80 % 이상 복귀를 확인한다.';
MERGE (m:ManualSection {id: 'HM-9.1'}) SET m.ref = 'HM-9.1', m.title = '펌프 부하 저감', m.excerpt = '부하 설정은 60 % 아래로 내리지 않는다(최소 유량 인터록). 10 %씩 단계적으로 낮춘다.';

MERGE (pr:Procedure {id: 'SOP-COOL-01'}) SET pr.name = '과열 완화 표준 절차 (즉시 조치)';
MERGE (st:Step {id: 'SOP-COOL-01/1'}) SET st.order = 1, st.text = 'PLC 운전 모드가 REMOTE_AUTO인지 확인한다 (아니면 FUXA에서 전환 요청).', st.manual = 'HM-3.2';
MERGE (st:Step {id: 'SOP-COOL-01/2'}) SET st.order = 2, st.text = '쿨러 팬 속도를 80~100 %로 상향한다 (FAN_BOOST).', st.manual = 'HM-7.3';
MERGE (st:Step {id: 'SOP-COOL-01/3'}) SET st.order = 3, st.text = '펌프 부하를 60~90 %로 저감한다 (REDUCE_LOAD). 최소 부하 60 % 인터록.', st.manual = 'HM-9.1';
MERGE (st:Step {id: 'SOP-COOL-01/4'}) SET st.order = 4, st.text = '15분 재관측: TS1 < 55 ℃ 이고 경보 CLEAR이면 완화 성공, 아니면 에스컬레이션.', st.manual = 'HM-7.5';
MERGE (pr:Procedure {id: 'SOP-COOL-02'}) SET pr.name = '쿨러 핀 세척 정비 절차 (근본 조치)';
MERGE (st:Step {id: 'SOP-COOL-02/1'}) SET st.order = 1, st.text = '설비를 정지하고 현장 패널에서 LOCAL 모드로 전환한다.', st.manual = 'HM-3.1';
MERGE (st:Step {id: 'SOP-COOL-02/2'}) SET st.order = 2, st.text = '쿨러 핀을 압축공기로 세척한다.', st.manual = 'HM-7.6';
MERGE (st:Step {id: 'SOP-COOL-02/3'}) SET st.order = 3, st.text = '재가동 후 CE 80 % 이상 복귀를 확인하고 작업지시를 종결한다.', st.manual = 'HM-7.5';
MATCH (pr:Procedure), (st:Step) WHERE st.id STARTS WITH pr.id + '/' MERGE (pr)-[:HAS_STEP]->(st);
MATCH (st:Step), (m:ManualSection {id: st.manual}) MERGE (st)-[:REFERS_TO]->(m);
MATCH (a:Action), (pr:Procedure {id:'SOP-COOL-01'}) WHERE a.id IN ['act:fan-boost','act:reduce-load'] MERGE (a)-[:FOLLOWS]->(pr);
MATCH (a:Action {id:'act:cooler-clean-wo'}), (pr:Procedure {id:'SOP-COOL-02'}) MERGE (a)-[:FOLLOWS]->(pr);
