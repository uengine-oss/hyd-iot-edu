// Capability seats only. Source procedures/rules and actual work orders are not seeded here.
MERGE (a:Action {id:'action:reschedule-work-order'})
SET a.name='기존 PM 정비 오더 일정 변경',a.code='WO_RESCHEDULE',a.kind='transaction'
WITH a MATCH (s:System {id:'sys:cmms'}) MERGE (a)-[:TARGETS]->(s);
MERGE (i:InputData {id:'in:production-running'})
SET i.name='현재 설비 생산 오더 가동 여부',i.typeRef='boolean',i.variable='production_running'
WITH i MATCH (s:System {id:'sys:mes'}) MERGE (i)-[:SOURCED_FROM]->(s)
WITH i MATCH (d:Decision {id:'dec:compliance'}),(t:Task {id:'task:compliance'})
MERGE (d)-[:REQUIRES_INPUT]->(i) MERGE (t)-[:READS]->(i);
