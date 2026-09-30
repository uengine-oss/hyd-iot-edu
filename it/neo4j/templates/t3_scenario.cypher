// T3-a 판단 시나리오와 필요한 정보: Scenario -NEEDS_INFO-> InfoType -HELD_IN-> System
// 에이전트는 이 결과로 "어느 시스템의 어느 엔드포인트에서 어떤 사실을 가져올지" 정한다 (데이터 위치를 코드가 아니라 온톨로지가 안다).
MATCH (s:Scenario {id: $scenario})
OPTIONAL MATCH (s)-[:NEEDS_INFO]->(i:InfoType)-[:HELD_IN]->(sys:System)
OPTIONAL MATCH (t)-[:TRIGGERS_DECISION]->(s)
RETURN s {.*} AS scenario,
       collect(DISTINCT CASE WHEN i IS NULL THEN null ELSE {id: i.id, name: i.name, endpoint: i.endpoint, prefix: i.prefix, system: sys.id, systemName: sys.name} END) AS infos,
       collect(DISTINCT CASE WHEN t IS NULL THEN null ELSE {id: t.id, name: t.name} END) AS triggers
