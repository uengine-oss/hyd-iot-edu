// 시나리오 B(정기 정비)의 실행 자리만 둔다 — scenario_structure.cypher 다음에 적재한다(seed.sh). 원문 절차 · 규칙 · 실제 작업지시는 넣지 않는다(PM-02 적재 · 업무 DB).
// 기존 PM 정비 오더의 일정을 옮기는 원자 조치(PM-02 「다음 정비 시간으로 미룬다」 시행 방식이 쓴다)와 생산 오더 가동 여부 입력.
MERGE (a:Action {id:'action:reschedule-work-order'})
SET a.name='기존 PM 정비 오더 일정 변경',a.code='WO_RESCHEDULE',a.kind='transaction'
WITH a MATCH (s:System {id:'sys:cmms'}) MERGE (a)-[:TARGETS]->(s);
MERGE (i:InputData {id:'in:production-running'})
SET i.name='현재 설비 생산 오더 가동 여부',i.typeRef='boolean',i.variable='production_running'
WITH i MATCH (s:System {id:'sys:mes'}) MERGE (i)-[:SOURCED_FROM]->(s)
WITH i MATCH (d:Decision {id:'dec:compliance'}) MERGE (d)-[:REQUIRES_INPUT]->(i);
