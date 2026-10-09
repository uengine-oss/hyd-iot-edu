// 확정 TODO C1 — 시나리오 구조(시드, 두 판 공통). 스키마 v2의 기존 클래스 · 관계만 쓰는 인스턴스 추가다. 멱등(MERGE).
// instances.cypher · knowledge_a098.cypher 다음에 적용한다(seed.sh · scripts/ontology_v2.py load).
// 여기에는 "문서가 기대는 자리"만 둔다: 승인 역할, 감시 패턴, 규칙이 검사할 판단 입력. 고장 · 원인 · 조치 · 규칙은 문서 적재가 만든다.
// 시나리오 B(정비 계획)의 시작 패턴 · 입력은 B 재정의 확정 뒤에 더한다.

// C 예비품 구매: 구매 담당(카드 승인 L1). 구매팀장(role:purchasing-mgr, L2)은 instances.cypher에 있다.
MERGE (n:Role {id: 'role:purchasing'}) SET n.name = '구매 담당', n.level = 1
WITH n MATCH (d:OrgUnit {id: 'dept:purchasing'}) MERGE (n)-[:MEMBER_OF]->(d);

// 판단 입력: [id, name, typeRef, variable, source, represents]. 값은 실행 중에 온다(ERP 재고 감시 · 에이전트 계산). 지식에는 자리만 둔다.
UNWIND [['in:spare-gap','예비품 가용 재고 − 재주문점 (개)','number','spare_gap','sys:erp',null],
        ['in:po-amount','발주 금액 (만원)','number','po_amount','sys:agent','msr:part-cost'],
        ['in:lead-slack-days','필요일 − 공급사 리드타임 (일)','number','lead_slack_days','sys:agent',null]] AS r
MERGE (n:InputData {id: r[0]}) SET n.name = r[1], n.typeRef = r[2], n.variable = r[3]
WITH n, r MATCH (src {id: r[4]}) MERGE (n)-[:SOURCED_FROM]->(src)
WITH n, r OPTIONAL MATCH (x:Measure {id: r[5]})
FOREACH (_ IN CASE WHEN x IS NULL THEN [] ELSE [1] END | MERGE (n)-[:REPRESENTS]->(x));

// 규정 검토가 문서 규칙으로 검사할 수 있는 입력(규칙이 검사하는 입력은 결정의 REQUIRES_INPUT · 작업의 READS로 선언한다 — validate 규칙).
UNWIND ['in:pattern','in:po-amount','in:lead-slack-days'] AS iid
MATCH (d:Decision {id: 'dec:compliance'}), (t:Task {id: 'task:compliance'}), (i:InputData {id: iid})
MERGE (d)-[:REQUIRES_INPUT]->(i) MERGE (t)-[:READS]->(i);

// 재고 기준 이탈 감시 패턴. 센서가 아니라 ERP 재고 감시(확정 TODO C2)가 경보를 낸다 — detectionMode가 없으므로 탐지기는 읽지 않는다.
// 설비 증상이 아니므로 Symptom을 잇지 않는다(seed_checks의 패턴 단언은 결정 1에 따라 설비 패턴에만 적용).
MERGE (p:AnomalyPattern {id: 'pattern:spare-below-min'})
  SET p.name = '예비품 재고 기준 이탈', p.code = 'SPARE_BELOW_MIN', p.rule = '가용 재고(현재고 − 정비 예약 + 입고 예정) < 재주문점 (ERP 재고 감시)', p.holdSeconds = 0
WITH p MATCH (i:InputData {id: 'in:spare-gap'}) MERGE (p)-[t:TESTS]->(i) SET t.operator = '<', t.value = 0, t.unit = 'ea'
WITH p MATCH (k:KnowledgeSource {id: 'ks:pr-07'}) MERGE (p)-[:DERIVED_FROM]->(k)
WITH p MATCH (e:Event {id: 'ev:alert'}) MERGE (e)-[:CORRELATES]->(p);
