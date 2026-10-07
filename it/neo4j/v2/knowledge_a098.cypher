// A098 (2026-10-07) — 전문가 질문 3건(docs/expert-questions-a079.md)의 답. 업계 자료로 조사해 정했고 출처는 DECISIONS 94.
// instances.cypher 다음에 적용한다(seed.sh · ontology_v2.py). 멱등(MERGE).

// Q1-A: 유량(FS1) 저하는 실린더 사이클 지연 → 생산량 감소(중간). 기준은 누설 의심 8.0 l/min.
UNWIND [['sv:fs1','msr:throughput',1,'medium','FS1 < 8.0 l/min에서 사이클 지연(유량 → 액추에이터 속도)',null]] AS r
MATCH (a {id: r[0]}), (b {id: r[1]}) MERGE (a)-[i:INFLUENCES]->(b) SET i.sign = r[2], i.strength = r[3], i.condition = r[4], i.note = r[5];

// Q2-(가): 작동유 열화는 고장 유형으로 둔다. 원인 4 · 증상(정기 오일 분석, 사람 입력) · 패턴(사람 입력 경보) · 입력 · 진단 규칙.
UNWIND [['cause:oil-oxidation','고온 운전에 의한 산화',['산화','열 열화'],0.4,'fm:oil-degradation'],
        ['cause:water-ingress','수분 혼입',['수분','물 혼입','결로'],0.25,'fm:oil-degradation'],
        ['cause:particle-contamination','오염 입자 유입',['오염','마모 입자','청정도 저하'],0.25,'fm:oil-degradation'],
        ['cause:change-interval-exceeded','교환 주기 초과',['장기 사용','교환 지연'],0.1,'fm:oil-degradation']] AS r
MERGE (n:Cause {id: r[0]}) SET n.name = r[1], n.aliases = r[2], n.prior = r[3]
WITH n, r MATCH (f:FailureMode {id: r[4]}) MERGE (n)-[:CAUSES]->(f);
MERGE (sy:Symptom {id: 'sym:oil-analysis-out-of-spec'})
  SET sy.name = '오일 분석 기준 이탈', sy.aliases = ['TAN 상승','수분 2,500 ppm 초과','ISO 4406 등급 2단계 악화','점도 변화'],
      sy.note = '실시간 센서가 없다. 정기 오일 분석(점도 · 산가 TAN · 수분 Karl Fischer · 청정도 ISO 4406) 결과를 사람이 입력한다.'
WITH sy MATCH (f:FailureMode {id: 'fm:oil-degradation'}) MERGE (sy)-[:INDICATES]->(f);
MERGE (p:AnomalyPattern {id: 'pattern:oil-analysis'})
  SET p.name = '오일 분석 기준 이탈 (사람 입력)', p.code = 'OIL_ANALYSIS',
      p.rule = 'TAN delta >= 2 or water > 2500 ppm or ISO 4406 +2 codes or viscosity out of grade', p.holdSeconds = 0
WITH p MATCH (sy:Symptom {id: 'sym:oil-analysis-out-of-spec'}) MERGE (p)-[:DETECTS]->(sy)
WITH p MATCH (m:ManualSection {id: 'HM-9.4'}) MERGE (p)-[:DERIVED_FROM]->(m);
MERGE (i:InputData {id: 'in:oil-analysis'}) SET i.name = '오일 분석 결과 (기준 이탈 여부)', i.typeRef = 'boolean', i.variable = 'oil_analysis_out_of_spec'
WITH i MATCH (src:System {id: 'sys:cmms'}) MERGE (i)-[:SOURCED_FROM]->(src)
WITH i MATCH (p:AnomalyPattern {id: 'pattern:oil-analysis'}) MERGE (p)-[t:TESTS]->(i) SET t.operator = '==', t.value = true;

// Q3-A + 3-2 예: 과열 정지는 선행 고장의 결과(자체 원인 없음, 감사 Q02 기준 변경). 저압 정지 · 고진동 정지를 고장 유형 · 경보 패턴으로 등록.
UNWIND [['pattern:low-pressure-trip','저압 인터록 트립','LOW_PRESSURE_TRIP','PLC state == TRIP (PS1 < 130 bar)',0],
        ['pattern:high-vibration-trip','고진동 인터록 트립','HIGH_VIBRATION_TRIP','PLC state == TRIP (VS1 >= 2.0 mm/s)',0]] AS r
MERGE (n:AnomalyPattern {id: r[0]}) SET n.name = r[1], n.code = r[2], n.rule = r[3], n.holdSeconds = r[4]
WITH n MATCH (i:InputData {id: 'in:plc-state'}) MERGE (n)-[t:TESTS]->(i) SET t.operator = '==', t.value = 'TRIP'
WITH n MATCH (m:ManualSection {id: 'HM-9.4'}) MERGE (n)-[:DERIVED_FROM]->(m);
UNWIND [['pattern:low-pressure-trip','sym:ps1-drop'],['pattern:high-vibration-trip','sym:vs1-rise']] AS r
MATCH (p:AnomalyPattern {id: r[0]}), (s:Symptom {id: r[1]}) MERGE (p)-[:DETECTS]->(s);
UNWIND [['fm:low-pressure-trip','저압 정지','comp:pump-a','sym:ps1-drop','fm:volumetric-loss'],
        ['fm:high-vibration-trip','고진동 정지','comp:fan','sym:vs1-rise','fm:bearing-degradation']] AS r
MERGE (n:FailureMode {id: r[0]}) SET n.name = r[1]
WITH n, r MATCH (c:Component {id: r[2]}) MERGE (n)-[:OCCURS_IN]->(c)
WITH n, r MATCH (s:Symptom {id: r[3]}) MERGE (s)-[:INDICATES]->(n)
WITH n, r MATCH (prev:FailureMode {id: r[4]}) MERGE (prev)-[:LEADS_TO]->(n);

// 리셋 스킬 2종: 원인 조치 확인 → 값 복귀 확인 → 리셋 (HM-9.4 트립 후 재기동)
UNWIND [
  ['skill:reset-after-pressure','압력 복귀 후 리셋','SOP-TRIP-02','control','누설 조치(예비 펌프 전환 또는 씰 교체) 뒤 토출 압력이 130 bar 이상으로 돌아온 것을 확인하고 저압 인터록을 리셋한다.','role:prod-mgr','sys:scada',[['action:reset',1]],
    [['저압 원인 조치(예비 펌프 전환 · 씰 교체)가 끝났는지 확인한다.','HM-9.4'],['PS1이 130 bar 이상으로 회복했는지 확인한다.','HM-5.2'],['PLC를 리셋하고 재관측한다.','HM-9.4']]],
  ['skill:reset-after-vibration','진동 확인 후 리셋','SOP-TRIP-03','control','팬 감속 또는 베어링 교체 뒤 진동이 1.2 mm/s 아래로 내려온 것을 확인하고 고진동 인터록을 리셋한다.','role:prod-mgr','sys:scada',[['action:reset',1]],
    [['진동 원인 조치(팬 감속 · 베어링 교체)가 끝났는지 확인한다.','HM-9.4'],['VS1이 1.2 mm/s 미만인지 확인한다.','HM-8.1'],['PLC를 리셋하고 재관측한다.','HM-9.4']]]
] AS r
MERGE (n:Skill {id: r[0]}) SET n.name = coalesce(n.name, r[1]), n.sopId = r[2], n.kind = r[3], n.description = coalesce(n.description, r[4])
WITH n, r MATCH (ap:Role {id: r[5]}), (ex:System {id: r[6]})
FOREACH (_ IN CASE WHEN EXISTS { (n)-[:APPROVED_BY]->() } THEN [] ELSE [1] END | MERGE (n)-[:APPROVED_BY]->(ap))
MERGE (ex)-[:HAS_SKILL]->(n)
WITH n, r UNWIND range(0, size(r[7]) - 1) AS i
MATCH (a:Action {id: r[7][i][0]}) MERGE (n)-[c:CONSISTS_OF]->(a) SET c.value = r[7][i][1], c.seq = i + 1
WITH DISTINCT n, r UNWIND range(0, size(r[8]) - 1) AS j
MERGE (st:Step {id: r[2] + '/' + (j + 1)}) SET st.order = j + 1, st.text = coalesce(st.text, r[8][j][0])
MERGE (n)-[:HAS_STEP]->(st)
WITH st, r, j MATCH (m:ManualSection {id: r[8][j][1]}) MERGE (st)-[:REFERS_TO]->(m);
UNWIND [['fm:low-pressure-trip','skill:reset-after-pressure'],['fm:high-vibration-trip','skill:reset-after-vibration']] AS r
MATCH (f:FailureMode {id: r[0]}), (s:Skill {id: r[1]}) MERGE (f)-[:MITIGATED_BY]->(s);
UNWIND [['skill:reset-after-pressure','msr:availability',1,null,null,'재기동'],['skill:reset-after-vibration','msr:availability',1,null,null,'재기동']] AS r
MATCH (s:Skill {id: r[0]}), (t {id: r[1]}) MERGE (s)-[a:AFFECTS]->(t) SET a.sign = r[2], a.delta = r[3], a.unit = r[4], a.note = r[5];

// 후보 결정이 이제 경보 패턴도 입력으로 쓴다(트립 종류별 리셋 카드) — 규칙이 검사하는 입력은 결정의 REQUIRES_INPUT에 선언한다(validate 규칙).
MATCH (d:Decision {id: 'dec:action-candidates'}), (i:InputData {id: 'in:pattern'}) MERGE (d)-[:REQUIRES_INPUT]->(i);
MATCH (t:Task {id: 'task:candidates'}), (i:InputData {id: 'in:pattern'}) MERGE (t)-[:READS]->(i);

// 후보 · 진단 규칙. 기존 rule:cand-trip은 과열 트립에만 쓰도록 instances.cypher에서 조건을 좁혔다.
UNWIND [
  ['rule:cand-trip-lp','dt:action-candidates',6,"plc_state == 'TRIP' and pattern == 'LOW_PRESSURE_TRIP'",'SELECT',null,'저압 트립이면 누설 조치 확인 뒤 압력 복귀 후 리셋',['skill:reset-after-pressure'],['HM-9.4'],
    [['in:plc-state','==','TRIP',null],['in:pattern','==','LOW_PRESSURE_TRIP',null]]],
  ['rule:cand-trip-hv','dt:action-candidates',7,"plc_state == 'TRIP' and pattern == 'HIGH_VIBRATION_TRIP'",'SELECT',null,'고진동 트립이면 진동 조치 확인 뒤 리셋',['skill:reset-after-vibration'],['HM-9.4'],
    [['in:plc-state','==','TRIP',null],['in:pattern','==','HIGH_VIBRATION_TRIP',null]]],
  ['rule:dx-oil','dt:diagnose-cause',4,"pattern == 'OIL_ANALYSIS'",'SELECT',null,'오일 분석 기준 이탈이면 산화가 1순위, 수분 · 오염 입자 · 교환 주기는 분석 항목으로 구분 (사람 입력)',['cause:oil-oxidation','cause:water-ingress','cause:particle-contamination','cause:change-interval-exceeded'],['HM-9.4'],
    [['in:pattern','==','OIL_ANALYSIS',null]]]
] AS r
MERGE (n:Rule {id: r[0]}) SET n.order = r[2], n.when = r[3], n.effect = r[4], n.penalty = r[5], n.annotation = r[6]
WITH n, r MATCH (t:DecisionTable {id: r[1]}) MERGE (t)-[:HAS_RULE]->(n)
WITH n, r UNWIND r[7] AS sid MATCH (s {id: sid}) WHERE s:Skill OR s:Cause MERGE (n)-[:OUTPUTS]->(s)
WITH DISTINCT n, r UNWIND r[8] AS src MATCH (x {id: src}) WHERE x:KnowledgeSource OR x:ManualSection MERGE (n)-[:DERIVED_FROM]->(x)
WITH DISTINCT n, r UNWIND r[9] AS tst MATCH (i:InputData {id: tst[0]}) MERGE (n)-[c:TESTS]->(i) SET c.operator = tst[1], c.value = tst[2], c.unit = tst[3];

// 고장 유형으로 판정된 트립에도 같은 리셋 카드(과열 트립의 rule:cand-trip-fm과 같은 모양; Q22: 고장 유형의 조치는 failure_mode 규칙이 내놓는다).
UNWIND [['rule:cand-trip-lp-fm',8,"failure_mode == 'fm:low-pressure-trip'",'저압 정지로 판정되면 압력 복귀 후 리셋','fm:low-pressure-trip','skill:reset-after-pressure'],
        ['rule:cand-trip-hv-fm',9,"failure_mode == 'fm:high-vibration-trip'",'고진동 정지로 판정되면 진동 확인 후 리셋','fm:high-vibration-trip','skill:reset-after-vibration']] AS r
MERGE (n:Rule {id: r[0]}) SET n.order = r[1], n.when = r[2], n.effect = 'SELECT', n.annotation = r[3]
WITH n, r MATCH (t:DecisionTable {id: 'dt:action-candidates'}) MERGE (t)-[:HAS_RULE]->(n)
WITH n, r MATCH (i:InputData {id: 'in:failure-mode'}) MERGE (n)-[c:TESTS]->(i) SET c.operator = '==', c.value = r[4]
WITH n, r MATCH (m:ManualSection {id: 'HM-9.4'}) MERGE (n)-[:DERIVED_FROM]->(m)
WITH n, r MATCH (s:Skill {id: r[5]}) MERGE (n)-[:OUTPUTS]->(s);

// 작동유 열화의 조치 후보 규칙: 매뉴얼 HM-9에서 적재한 스킬(SOP-OIL-21 교환 · HM-9.2 점검)을 내놓는다(A075·Q22: 온톨로지에 있는 조치는 후보 규칙이 내놓아야 판단에 닿는다).
// 스킬 노드는 적재 파이프라인이 만들므로(문서 적재 전에는 없음) 있는 것만 잇는다 — 적재 뒤 다시 적용하면 채워진다.
MERGE (n:Rule {id: 'rule:cand-oil'}) SET n.order = 8, n.when = "failure_mode == 'fm:oil-degradation'", n.effect = 'SELECT',
  n.annotation = '작동유 열화로 판정되면 작동유 교환(SOP-OIL-21) · 열화 점검 절차를 후보로 (A098, 사람 입력 오일 분석)'
WITH n MATCH (t:DecisionTable {id: 'dt:action-candidates'}) MERGE (t)-[:HAS_RULE]->(n)
WITH n MATCH (i:InputData {id: 'in:failure-mode'}) MERGE (n)-[c:TESTS]->(i) SET c.operator = '==', c.value = 'fm:oil-degradation'
WITH n MATCH (m:ManualSection {id: 'HM-9.4'}) MERGE (n)-[:DERIVED_FROM]->(m)
WITH n MATCH (f:FailureMode {id: 'fm:oil-degradation'})-[:REMEDIED_BY|MITIGATED_BY]->(s:Skill) MERGE (n)-[:OUTPUTS]->(s);
