// 이 파일은 graph.json 의 노드 36개와 관계 53개를 적힌 차례대로 그래프 DB에 넣는다(다시 실행해도 늘지 않는다).

// ── 노드 36개 ──

// Asset(설비) 3개
MERGE (n:Asset {id: 'asset:hyd-01'}) SET n.name = 'HYD-01 유압 파워팩', n.code = 'HYD-01';
MERGE (n:Asset {id: 'asset:hyd-02'}) SET n.name = 'HYD-02 유압 파워팩', n.code = 'HYD-02';
MERGE (n:Asset {id: 'asset:hyd-03'}) SET n.name = 'HYD-03 유압 파워팩', n.code = 'HYD-03';

// Component(구성 요소) 6개
MERGE (n:Component {id: 'comp:oil-cooler'}) SET n.name = '오일 쿨러', n.aliases = ['열교환기', '쿨러'];
MERGE (n:Component {id: 'comp:cooler-fan'}) SET n.name = '쿨러 팬', n.aliases = ['송풍기', '팬'];
MERGE (n:Component {id: 'comp:main-pump'}) SET n.name = '주 펌프 (A)', n.aliases = ['유압 펌프', '펌프', '주 펌프 A', 'A 펌프'];
MERGE (n:Component {id: 'comp:standby-pump'}) SET n.name = '예비 펌프 (B)', n.aliases = ['스탠바이 펌프'];
MERGE (n:Component {id: 'comp:drive-motor'}) SET n.name = '구동 모터', n.aliases = ['모터'];
MERGE (n:Component {id: 'comp:oil-tank'}) SET n.name = '작동유 탱크', n.aliases = ['리저버', '탱크'];

// Sensor(센서) 5개
MERGE (n:Sensor {id: 'sen:ts1'}) SET n.name = '유온 센서', n.tag = 'TS1', n.virtual = false;
MERGE (n:Sensor {id: 'sen:ce'}) SET n.name = '냉각 효율 (가상)', n.tag = 'CE', n.virtual = true;
MERGE (n:Sensor {id: 'sen:ps1'}) SET n.name = '토출 압력 센서', n.tag = 'PS1', n.virtual = false;
MERGE (n:Sensor {id: 'sen:fs1'}) SET n.name = '유량 센서', n.tag = 'FS1', n.virtual = false;
MERGE (n:Sensor {id: 'sen:vs1'}) SET n.name = '팬 진동 센서', n.tag = 'VS1', n.virtual = false;

// Actuator(구동기) 3개
MERGE (n:Actuator {id: 'actr:fanspeedsp'}) SET n.name = '팬 인버터', n.signal = 'FanSpeedSP', n.min = 0, n.max = 100;
MERGE (n:Actuator {id: 'actr:loadsp'}) SET n.name = '펌프 부하 설정', n.signal = 'LoadSP', n.min = 60, n.max = 100, n.note = '60 % 미만으로 내리지 않는다';
MERGE (n:Actuator {id: 'actr:pumpselect'}) SET n.name = '펌프 전환 밸브', n.signal = 'PumpSelect', n.options = ['A', 'B'];

// StateVariable(상태 변수) 8개
MERGE (n:StateVariable {id: 'sv:ts1'}) SET n.name = '유온', n.aliases = ['오일 온도', '작동유 온도'], n.unit = '℃', n.normal = 48, n.limit = 65, n.limit_note = '65 ℃에서 인터록', n.limit_direction = 'upper';
MERGE (n:StateVariable {id: 'sv:ce'}) SET n.name = '냉각 효율', n.aliases = ['쿨러 효율'], n.unit = '%', n.normal = 84;
MERGE (n:StateVariable {id: 'sv:ps1'}) SET n.name = '토출 압력', n.aliases = ['펌프 압력'], n.unit = 'bar', n.normal = 182, n.limit = 130, n.limit_note = '130 bar 미만에서 저압 인터록', n.limit_direction = 'lower';
MERGE (n:StateVariable {id: 'sv:fs1'}) SET n.name = '유량', n.aliases = ['토출 유량'], n.unit = 'l/min', n.normal = 9;
MERGE (n:StateVariable {id: 'sv:vs1'}) SET n.name = '팬 진동', n.aliases = ['진동'], n.unit = 'mm/s', n.normal = 0.6, n.limit = 2.0, n.limit_note = '2.0 mm/s 이상에서 진동 인터록', n.limit_direction = 'upper';
MERGE (n:StateVariable {id: 'sv:fan-speed'}) SET n.name = '팬 속도', n.aliases = ['팬 회전수'], n.unit = '%', n.normal = 60;
MERGE (n:StateVariable {id: 'sv:pump-load'}) SET n.name = '펌프 부하', n.aliases = ['부하'], n.unit = '%', n.normal = 90;
MERGE (n:StateVariable {id: 'sv:running-pump-selection'}) SET n.name = '운전 펌프 선택', n.aliases = ['펌프 전환'];

// Part(부품) 3개
MERGE (n:Part {id: 'part:p-clr-core'}) SET n.name = '쿨러 코어', n.part_no = 'P-CLR-CORE';
MERGE (n:Part {id: 'part:p-pmp-seal'}) SET n.name = '펌프 축 씰 키트', n.part_no = 'P-PMP-SEAL';
MERGE (n:Part {id: 'part:p-fan-brg'}) SET n.name = '팬 베어링', n.part_no = 'P-FAN-BRG';

// Symptom(증상) 2개
MERGE (n:Symptom {id: 'sym:oil-temperature-rise'}) SET n.name = '유온 상승';
MERGE (n:Symptom {id: 'sym:cooling-efficiency-drop'}) SET n.name = '냉각 효율 저하';

// FailureMode(고장 유형) 1개
MERGE (n:FailureMode {id: 'fm:cooler-cooling-performance-loss'}) SET n.name = '쿨러 냉각 성능 상실';

// Cause(원인) 1개
MERGE (n:Cause {id: 'cause:cooler-fin-fouling'}) SET n.name = '쿨러 핀 오염';

// Skill(조치) 1개
MERGE (n:Skill {id: 'skill:fan-maximum-run'}) SET n.name = '팬 최대 운전';

// Supplier(공급사) 3개
MERGE (n:Supplier {id: 'sup:a'}) SET n.name = 'A정밀 (저가)', n.approved = true, n.grade = '저가';
MERGE (n:Supplier {id: 'sup:b'}) SET n.name = 'B-OEM (순정)', n.approved = true, n.grade = '순정';
MERGE (n:Supplier {id: 'sup:c'}) SET n.name = 'C트레이딩 (최저가 · 비승인)', n.approved = false, n.grade = '최저가';

// ── 관계 53개 ──

// HAS_COMPONENT(설비는 구성 요소를 가진다) 18개
MATCH (a:Asset {id: 'asset:hyd-01'}), (b:Component {id: 'comp:oil-cooler'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-01'}), (b:Component {id: 'comp:cooler-fan'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-01'}), (b:Component {id: 'comp:main-pump'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-01'}), (b:Component {id: 'comp:standby-pump'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-01'}), (b:Component {id: 'comp:drive-motor'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-01'}), (b:Component {id: 'comp:oil-tank'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-02'}), (b:Component {id: 'comp:oil-cooler'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-02'}), (b:Component {id: 'comp:cooler-fan'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-02'}), (b:Component {id: 'comp:main-pump'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-02'}), (b:Component {id: 'comp:standby-pump'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-02'}), (b:Component {id: 'comp:drive-motor'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-02'}), (b:Component {id: 'comp:oil-tank'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-03'}), (b:Component {id: 'comp:oil-cooler'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-03'}), (b:Component {id: 'comp:cooler-fan'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-03'}), (b:Component {id: 'comp:main-pump'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-03'}), (b:Component {id: 'comp:standby-pump'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-03'}), (b:Component {id: 'comp:drive-motor'}) MERGE (a)-[:HAS_COMPONENT]->(b);
MATCH (a:Asset {id: 'asset:hyd-03'}), (b:Component {id: 'comp:oil-tank'}) MERGE (a)-[:HAS_COMPONENT]->(b);

// MOUNTED_ON(센서와 구동기는 구성 요소에 붙어 있다) 9개
MATCH (a:Sensor {id: 'sen:ts1'}), (b:Component {id: 'comp:oil-cooler'}) MERGE (a)-[:MOUNTED_ON]->(b);
MATCH (a:Sensor {id: 'sen:ce'}), (b:Component {id: 'comp:oil-cooler'}) MERGE (a)-[:MOUNTED_ON]->(b);
MATCH (a:Sensor {id: 'sen:ps1'}), (b:Component {id: 'comp:main-pump'}) MERGE (a)-[:MOUNTED_ON]->(b);
MATCH (a:Sensor {id: 'sen:fs1'}), (b:Component {id: 'comp:main-pump'}) MERGE (a)-[:MOUNTED_ON]->(b);
MATCH (a:Sensor {id: 'sen:vs1'}), (b:Component {id: 'comp:cooler-fan'}) MERGE (a)-[:MOUNTED_ON]->(b);
MATCH (a:Actuator {id: 'actr:fanspeedsp'}), (b:Component {id: 'comp:cooler-fan'}) MERGE (a)-[:MOUNTED_ON]->(b);
MATCH (a:Actuator {id: 'actr:loadsp'}), (b:Component {id: 'comp:drive-motor'}) MERGE (a)-[:MOUNTED_ON]->(b);
MATCH (a:Actuator {id: 'actr:pumpselect'}), (b:Component {id: 'comp:main-pump'}) MERGE (a)-[:MOUNTED_ON]->(b);
MATCH (a:Actuator {id: 'actr:pumpselect'}), (b:Component {id: 'comp:standby-pump'}) MERGE (a)-[:MOUNTED_ON]->(b);

// MEASURES(센서는 상태 변수를 잰다) 5개
MATCH (a:Sensor {id: 'sen:ts1'}), (b:StateVariable {id: 'sv:ts1'}) MERGE (a)-[:MEASURES]->(b);
MATCH (a:Sensor {id: 'sen:ce'}), (b:StateVariable {id: 'sv:ce'}) MERGE (a)-[:MEASURES]->(b);
MATCH (a:Sensor {id: 'sen:ps1'}), (b:StateVariable {id: 'sv:ps1'}) MERGE (a)-[:MEASURES]->(b);
MATCH (a:Sensor {id: 'sen:fs1'}), (b:StateVariable {id: 'sv:fs1'}) MERGE (a)-[:MEASURES]->(b);
MATCH (a:Sensor {id: 'sen:vs1'}), (b:StateVariable {id: 'sv:vs1'}) MERGE (a)-[:MEASURES]->(b);

// CONTROLS(구동기는 상태 변수를 바꾼다) 3개
MATCH (a:Actuator {id: 'actr:fanspeedsp'}), (b:StateVariable {id: 'sv:fan-speed'}) MERGE (a)-[:CONTROLS]->(b);
MATCH (a:Actuator {id: 'actr:loadsp'}), (b:StateVariable {id: 'sv:pump-load'}) MERGE (a)-[:CONTROLS]->(b);
MATCH (a:Actuator {id: 'actr:pumpselect'}), (b:StateVariable {id: 'sv:running-pump-selection'}) MERGE (a)-[:CONTROLS]->(b);

// USES_PART(구성 요소는 부품을 쓴다) 3개
MATCH (a:Component {id: 'comp:oil-cooler'}), (b:Part {id: 'part:p-clr-core'}) MERGE (a)-[:USES_PART]->(b);
MATCH (a:Component {id: 'comp:main-pump'}), (b:Part {id: 'part:p-pmp-seal'}) MERGE (a)-[:USES_PART]->(b);
MATCH (a:Component {id: 'comp:cooler-fan'}), (b:Part {id: 'part:p-fan-brg'}) MERGE (a)-[:USES_PART]->(b);

// SHOWS(센서는 증상을 보여 준다) 2개
MATCH (a:Sensor {id: 'sen:ts1'}), (b:Symptom {id: 'sym:oil-temperature-rise'}) MERGE (a)-[:SHOWS]->(b);
MATCH (a:Sensor {id: 'sen:ce'}), (b:Symptom {id: 'sym:cooling-efficiency-drop'}) MERGE (a)-[:SHOWS]->(b);

// INDICATES(증상은 고장 유형을 가리킨다) 2개
MATCH (a:Symptom {id: 'sym:oil-temperature-rise'}), (b:FailureMode {id: 'fm:cooler-cooling-performance-loss'}) MERGE (a)-[:INDICATES]->(b);
MATCH (a:Symptom {id: 'sym:cooling-efficiency-drop'}), (b:FailureMode {id: 'fm:cooler-cooling-performance-loss'}) MERGE (a)-[:INDICATES]->(b);

// CAUSES(원인은 고장 유형을 일으킨다) 1개
MATCH (a:Cause {id: 'cause:cooler-fin-fouling'}), (b:FailureMode {id: 'fm:cooler-cooling-performance-loss'}) MERGE (a)-[:CAUSES]->(b);

// MITIGATED_BY(고장 유형은 조치로 완화된다) 1개
MATCH (a:FailureMode {id: 'fm:cooler-cooling-performance-loss'}), (b:Skill {id: 'skill:fan-maximum-run'}) MERGE (a)-[:MITIGATED_BY]->(b);

// OCCURS_IN(고장 유형은 구성 요소에서 일어난다) 1개
MATCH (a:FailureMode {id: 'fm:cooler-cooling-performance-loss'}), (b:Component {id: 'comp:oil-cooler'}) MERGE (a)-[:OCCURS_IN]->(b);

// RELATED_TO(원인은 부품과 관련된다) 1개
MATCH (a:Cause {id: 'cause:cooler-fin-fouling'}), (b:Part {id: 'part:p-clr-core'}) MERGE (a)-[:RELATED_TO]->(b);

// SUPPLIED_BY(부품은 공급사에게서 공급받는다) 7개
MATCH (a:Part {id: 'part:p-pmp-seal'}), (b:Supplier {id: 'sup:a'}) MERGE (a)-[r:SUPPLIED_BY]->(b) SET r.price = 35, r.fail_rate = 0.12, r.lead_days = 2;
MATCH (a:Part {id: 'part:p-pmp-seal'}), (b:Supplier {id: 'sup:b'}) MERGE (a)-[r:SUPPLIED_BY]->(b) SET r.price = 55, r.fail_rate = 0.02, r.lead_days = 5;
MATCH (a:Part {id: 'part:p-pmp-seal'}), (b:Supplier {id: 'sup:c'}) MERGE (a)-[r:SUPPLIED_BY]->(b) SET r.price = 20, r.fail_rate = 0.30, r.lead_days = 1;
MATCH (a:Part {id: 'part:p-fan-brg'}), (b:Supplier {id: 'sup:a'}) MERGE (a)-[r:SUPPLIED_BY]->(b) SET r.price = 18, r.fail_rate = 0.10, r.lead_days = 1;
MATCH (a:Part {id: 'part:p-fan-brg'}), (b:Supplier {id: 'sup:b'}) MERGE (a)-[r:SUPPLIED_BY]->(b) SET r.price = 28, r.fail_rate = 0.03, r.lead_days = 3;
MATCH (a:Part {id: 'part:p-clr-core'}), (b:Supplier {id: 'sup:a'}) MERGE (a)-[r:SUPPLIED_BY]->(b) SET r.price = 180, r.fail_rate = 0.12, r.lead_days = 3;
MATCH (a:Part {id: 'part:p-clr-core'}), (b:Supplier {id: 'sup:b'}) MERGE (a)-[r:SUPPLIED_BY]->(b) SET r.price = 260, r.fail_rate = 0.02, r.lead_days = 5;
